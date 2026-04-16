#!/usr/bin/env python3
import io
import queue
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import platform
import os
import shutil
import urllib.request
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from tkinter import ttk, messagebox
from types import SimpleNamespace
from pathlib import Path
import json
import urllib.parse
import traceback

try:
    from zeroconf import ServiceBrowser, Zeroconf
    try:
        from zeroconf import ServiceStateChange
    except Exception:
        ServiceStateChange = None
except Exception:
    Zeroconf = None
    ServiceBrowser = None
    ServiceStateChange = None


import sdsClient
# Optional: run compute-node mount service in-process (preferred for packaged apps)
try:
    import computenode_service_client as _compute_svc
except Exception:
    _compute_svc = None
# The SDS REST API in the original (Divya) code runs on 4000.
# Keep this as the default unless a discovered/added node explicitly overrides it.
DEFAULT_API_PORT = 4000
COMPUTE_SERVICE_URL = os.environ.get("SDS_COMPUTE_URL", "http://127.0.0.1:4002")
# The compute-node helper service must be reachable from the Storage Node over the LAN.
# The GUI can still call it via 127.0.0.1, but the server bind must be 0.0.0.0 (or a specific NIC IP).
COMPUTE_BIND_HOST = os.environ.get("SDS_COMPUTE_BIND_HOST", "0.0.0.0")
try:
    # Ensure the GUI and sdsClient agree on the default port
    sdsClient.PORT = DEFAULT_API_PORT
except Exception:
    pass

APP_TITLE = "GS_VolumeManager"


def _maybe_relaunch_linux_as_root():
    """Relaunch the GUI through pkexec on Linux so the shipped app can mount volumes.

    This keeps the user flow to a single executable: launch app -> authenticate -> app opens.
    """
    if not sys.platform.startswith("linux"):
        return
    if os.geteuid() == 0:
        return
    if os.environ.get("GSVM_ALREADY_ELEVATED") == "1":
        return

    pkexec = shutil.which("pkexec")
    if not pkexec:
        return

    if getattr(sys, "frozen", False):
        relaunch_cmd = [sys.executable]
    else:
        relaunch_cmd = [sys.executable, str(Path(__file__).resolve())]

    env_parts = [
        f"DISPLAY={os.environ.get('DISPLAY', '')}",
        f"XAUTHORITY={os.environ.get('XAUTHORITY', '')}",
        f"XDG_RUNTIME_DIR={os.environ.get('XDG_RUNTIME_DIR', '')}",
        f"DBUS_SESSION_BUS_ADDRESS={os.environ.get('DBUS_SESSION_BUS_ADDRESS', '')}",
        f"WAYLAND_DISPLAY={os.environ.get('WAYLAND_DISPLAY', '')}",
        "GSVM_ALREADY_ELEVATED=1",
    ]

    try:
        result = subprocess.run(
            [pkexec, "env", *env_parts, *relaunch_cmd],
            check=False,
        )
        raise SystemExit(result.returncode)
    except Exception:
        return

# --- Modern UI Palette and Fonts ---
C_BG = "#0b1220"
C_CARD = "#121b2d"
C_NAV = "#0f182b"
C_PRIMARY = "#2b6cbf"
C_PRIMARY_DARK = "#1f4f8b"
C_ACCENT = "#1a2a44"
C_MUTED = "#b9c7dd"
C_TEXT = "#e9f0ff"
C_BORDER = "#1f2b40"
C_HIGHLIGHT = "#1b2d4d"
C_ACTIVE = "#25406b"
C_TREE_BG = "#0f182b"
C_TREE_ALT = "#14233a"
C_TREE_SEL = "#2a4a7a"

def _platform_fonts():
    if sys.platform.startswith("darwin"):
        return {
            "title": ("SF Pro Display", 20, "bold"),
            "header": ("SF Pro Text", 12, "bold"),
            "body": ("SF Pro Text", 11),
            "mono": ("Menlo", 10),
        }
    if sys.platform.startswith("win"):
        return {
            "title": ("Segoe UI", 20, "bold"),
            "header": ("Segoe UI", 12, "bold"),
            "body": ("Segoe UI", 11),
            "mono": ("Consolas", 10),
        }
    return {
        "title": ("Helvetica", 20, "bold"),
        "header": ("Helvetica", 12, "bold"),
        "body": ("Helvetica", 11),
        "mono": ("Courier", 10),
    }


FONTS = _platform_fonts()
FONT_TITLE = FONTS["title"]
FONT_HEADER = FONTS["header"]
FONT_BODY = FONTS["body"]
FONT_MONO = FONTS["mono"]


class SDSApp(tk.Tk):
    def _platform_protocols(self):
        """Return allowed protocol names for the current OS (aligned to sdsClient.PROTOCOLS)."""
        avail = list((getattr(sdsClient, "PROTOCOLS", {}) or {}).keys())
        avail_set = set(avail)

        def keep(order):
            return [p for p in order if p in avail_set]

        if sys.platform.startswith("win"):
            # Windows: CIFS + iSCSI (chap/no-chap)
            return keep(["CIFS", "iSCSI-Chap", "iSCSI-NoChap"])

        # macOS + Linux: NFS + CIFS + iSCSI (chap/no-chap)
        return keep(["NFS", "CIFS", "iSCSI-Chap", "iSCSI-NoChap"])

    def _default_protocol_for_platform(self):
        if sys.platform.startswith("win"):
            return "CIFS"
        return "NFS"
    def __init__(self):
        super().__init__()
        self._apply_theme()
        self.title(APP_TITLE)
        self.geometry("1024x720")
        self.minsize(1024, 720)
        self.resizable(True, True)
        self.configure(bg=C_BG)

        self.storage_nodes = []  # runtime-only; populated via mDNS and manual add
        self.log_queue = queue.Queue()
        self.current_array_var = tk.StringVar(value="Storage: (none)")

        self.status_var = tk.StringVar(value="Ready")
        self._busy_count = 0
        self._busy_msg = ""
        self._busy_widgets = []
        self._progress = None
        self._completion_job = None
        self._completion_showing = False

        self.nav_buttons = {}
        self.verbose_logs = tk.BooleanVar(value=False)
        # Windows iSCSI: optionally auto-initialize/format newly connected RAW disk
        self.auto_init_iscsi = tk.BooleanVar(value=True)
        # Cache discovered volumes -> inferred metadata (node/protocol) for this session
        self.volume_meta = {}  # name -> {"node": str, "protocol": str}
        # Track the local mount target per volume (so Unmount works even after switching pages)
        self.mounted_targets = {}  # volume_name -> local mount target
        # Compute-node local service (mount/unmount helper)
        self._compute_server = None
        self._compute_thread = None

        # Persistent state (Windows/macOS/Linux)
        self._state = {
            "storage_nodes": [],
            "last_selected_node": "",
            "volume_meta": {},
            "mounted_targets": {},
            "mdns_service": "",
        }
        self._state_dirty = False
        self._state_save_job = None
        self._load_state()
        # Restore verbose_logs setting if present in state
        try:
            if "verbose_logs" in (self._state or {}):
                self.verbose_logs.set(bool(self._state.get("verbose_logs")))
        except Exception:
            pass

        # Apply persisted session data into live structures
        if self._state.get("storage_nodes"):
            self.storage_nodes = list(self._state.get("storage_nodes") or [])
        if self._state.get("volume_meta"):
            self.volume_meta = dict(self._state.get("volume_meta") or {})
        if self._state.get("mounted_targets"):
            self.mounted_targets = dict(self._state.get("mounted_targets") or {})

        self._build_layout()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._poll_logs()
    def _show_completion(self, ok: bool, message: str):
        """Show the final outcome in the processing overlay briefly after a task completes."""
        try:
            # Cancel any pending hide
            if self._completion_job is not None:
                try:
                    self.after_cancel(self._completion_job)
                except Exception:
                    pass
                self._completion_job = None

            msg = (message or ("Done" if ok else "Failed")).strip()
            title = "Completed" if ok else "Failed"

            self._completion_showing = True
            # Ensure overlay is visible
            try:
                self._busy_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
                self._busy_overlay.lift()
            except Exception:
                pass

            try:
                self._busy_title.configure(text=title)
            except Exception:
                pass
            try:
                self._busy_detail.configure(text=msg)
            except Exception:
                pass

            # Stop the spinner while showing completion
            try:
                self._busy_bar.stop()
            except Exception:
                pass

            # Auto-hide after a short delay
            self._completion_job = self.after(2500, self._hide_completion)
        except Exception:
            return

    def _hide_completion(self):
        try:
            self._completion_job = None
            self._completion_showing = False
            # Restore busy title default for next run
            try:
                self._busy_title.configure(text="Processing…")
            except Exception:
                pass
            try:
                self._busy_detail.configure(text="")
            except Exception:
                pass
            try:
                self._busy_overlay.place_forget()
            except Exception:
                pass
        except Exception:
            return

    def _apply_theme(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        # General
        style.configure(".", font=FONT_BODY)
        # Frame backgrounds
        style.configure("TFrame", background=C_BG)
        style.configure("Card.TFrame", background=C_CARD)
        # Label
        style.configure("TLabel", background=C_BG, foreground=C_TEXT)
        style.configure("Header.TLabel", font=FONT_TITLE, background=C_CARD, foreground=C_TEXT)
        style.configure("Muted.TLabel", font=FONT_BODY, background=C_CARD, foreground=C_MUTED)
        style.configure("Caption.TLabel", font=FONT_BODY, background=C_CARD, foreground=C_MUTED)
        # LabelFrame
        style.configure("TLabelframe", background=C_CARD, foreground=C_TEXT, bordercolor=C_BORDER)
        style.configure("TLabelframe.Label", background=C_CARD, font=FONT_HEADER, foreground=C_TEXT)
        # Entry
        style.configure("TEntry", fieldbackground=C_CARD, background=C_CARD, foreground=C_TEXT, bordercolor=C_BORDER)
        # Combobox
        style.configure(
            "TCombobox",
            fieldbackground=C_CARD,
            background=C_PRIMARY_DARK,
            foreground=C_TEXT,
            bordercolor=C_PRIMARY_DARK,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", C_CARD), ("!readonly", C_CARD)],
            foreground=[("readonly", C_TEXT), ("!readonly", C_TEXT)],
            background=[("readonly", C_PRIMARY_DARK), ("active", C_PRIMARY), ("!readonly", C_PRIMARY_DARK)],
            selectbackground=[("readonly", C_CARD), ("!readonly", C_CARD)],
            selectforeground=[("readonly", C_TEXT), ("!readonly", C_TEXT)],
        )
        # Buttons
        style.configure("TButton", font=FONT_BODY, padding=6)
        style.configure("Primary.TButton", background=C_PRIMARY, foreground="#fff", bordercolor=C_PRIMARY, focusthickness=2)
        style.map("Primary.TButton",
                  background=[("active", C_PRIMARY_DARK), ("!active", C_PRIMARY)],
                  foreground=[("active", "#fff")])
        style.configure("Ghost.TButton", background=C_CARD, foreground=C_TEXT, bordercolor=C_PRIMARY)
        style.map("Ghost.TButton",
                  background=[("active", C_ACCENT), ("!active", C_CARD)],
                  foreground=[("active", C_TEXT)])
        style.configure("Nav.TButton", background=C_NAV, foreground=C_TEXT, borderwidth=0, relief="flat")
        style.map("Nav.TButton", background=[("active", C_HIGHLIGHT), ("pressed", C_ACTIVE)])
        style.configure("NavActive.TButton", background=C_PRIMARY, foreground="#fff", borderwidth=0)
        # Treeview
        style.configure("Treeview",
                        font=FONT_BODY,
                        background=C_TREE_BG,
                        fieldbackground=C_TREE_BG,
                        foreground=C_TEXT,
                        rowheight=28,
                        bordercolor=C_BORDER,
                        borderwidth=1)
        style.configure("Treeview.Heading",
                        font=FONT_HEADER,
                        background=C_ACCENT,
                        foreground=C_TEXT)
        style.map("Treeview",
                  background=[("selected", C_TREE_SEL)],
                  foreground=[("selected", C_PRIMARY_DARK)])
        style.layout("Treeview", [
            ('Treeview.treearea', {'sticky': 'nswe'})
        ])

    def _build_layout(self):
        header = tk.Frame(self, bg=C_BG, height=70)
        header.pack(fill="x", side="top")
        header.grid_propagate(False)
        header_canvas = tk.Canvas(header, highlightthickness=0, bd=0, height=70, bg=C_BG)
        header_canvas.pack(fill="both", expand=True)
        self._header_canvas = header_canvas
        self._draw_header_gradient(header_canvas)
        self._header_title_id = header_canvas.create_text(
            20,
            28,
            anchor="w",
            text=f"{APP_TITLE} — {socket.gethostname()}",
            fill="#ffffff",
            font=FONT_TITLE,
        )
        self._header_current_id = header_canvas.create_text(
            0,
            28,
            anchor="e",
            text=self.current_array_var.get(),
            fill=C_MUTED,
            font=FONT_HEADER,
        )
        self.current_array_var.trace_add(
            "write",
            lambda *_: header_canvas.itemconfigure(self._header_current_id, text=self.current_array_var.get()),
        )
        header.bind("<Configure>", lambda e: self._draw_header_gradient(header_canvas))
        self.bind("<Map>", lambda e: self._draw_header_gradient(header_canvas))
        self.after(100, lambda: self._draw_header_gradient(header_canvas))

        body = tk.Frame(self, bg=C_BG)
        body.pack(fill="both", expand=True, padx=16, pady=16)

        nav = tk.Frame(body, bg=C_NAV)
        nav.pack(side="left", fill="y", padx=(0, 16))
        nav_header = tk.Frame(nav, bg=C_ACCENT, height=40)
        nav_header.pack(fill="x")
        nav_header.pack_propagate(False)
        nav_title = tk.Label(nav_header, text="Actions", bg=C_ACCENT, fg=C_TEXT, font=FONT_HEADER)
        nav_title.pack(anchor="w", padx=10, pady=8)
        nav_divider = tk.Frame(nav, bg=C_BORDER, height=1)
        nav_divider.pack(fill="x")

        self.content = tk.Frame(body, bg=C_BG)
        self.content.pack(side="left", fill="both", expand=True)
        self.content.grid_rowconfigure(0, weight=3)
        self.content.grid_rowconfigure(1, weight=1)
        self.content.grid_columnconfigure(0, weight=1)
        self.page_container = tk.Frame(self.content, bg=C_BG)
        self.page_container.grid(row=0, column=0, sticky="nsew")

        self.frames = {}
        nav_items = [
            ("⚙  Configuration", "config"),
            ("➕  Create Volume", "create"),
            ("⤴  Mount Volume", "mount"),
            ("⤵  Un-mount Volume", "unmount"),
            ("🗑  Delete Volume", "delete"),
        ]
        self.nav_buttons = {}
        for label, key in nav_items:
            btn = ttk.Button(nav, text=label, style="Nav.TButton", command=lambda k=key: self._show_frame(k))
            btn.pack(fill="x", pady=6, padx=2)
            self.nav_buttons[key] = btn

        self._build_config_frame()
        self._build_create_frame()
        self._build_mount_frame()
        self._build_unmount_frame()
        self._build_delete_frame()
        self._build_log_frame()
        self._bind_node_dropdowns()

        # Processing overlay (standard UX for long-running operations)
        self._busy_overlay = tk.Frame(self.content, bg="#000000")
        # Center card inside overlay
        self._busy_card = tk.Frame(self._busy_overlay, bg=C_CARD, highlightthickness=1, highlightbackground=C_BORDER)
        self._busy_card.place(relx=0.5, rely=0.5, anchor="center", width=420, height=140)

        self._busy_title = tk.Label(self._busy_card, text="Processing…", bg=C_CARD, fg=C_TEXT, font=FONT_HEADER)
        self._busy_title.pack(anchor="w", padx=18, pady=(16, 6))

        self._busy_detail = tk.Label(self._busy_card, text="", bg=C_CARD, fg=C_MUTED, font=FONT_BODY, wraplength=380, justify="left")
        self._busy_detail.pack(anchor="w", padx=18, pady=(0, 10))

        self._busy_bar = ttk.Progressbar(self._busy_card, mode="indeterminate", length=380)
        self._busy_bar.pack(anchor="w", padx=18, pady=(0, 16))

        # Start hidden
        self._busy_overlay.place_forget()

        # Status bar
        statusbar = tk.Frame(self, bg=C_CARD, height=24)
        statusbar.pack(fill="x", side="bottom")
        status_label = tk.Label(statusbar, textvariable=self.status_var, anchor="w", bg=C_CARD, fg=C_MUTED, font=FONT_BODY)
        status_label.pack(side="left", padx=12, pady=2)
        self._progress = ttk.Progressbar(statusbar, mode="indeterminate", length=160)
        self._progress.pack(side="right", padx=12, pady=4)
        self._progress.stop()
        self._progress.pack_forget()  # hidden until busy

        self._refresh_storage_list()
        # Auto-discover on startup is disabled; user triggers discovery manually
        # self.after(300, lambda: self._discover_storage(silent=True))
        self._refresh_storage_list()
        self._apply_persisted_selection()
        self._show_frame("config")

    def _draw_header_gradient(self, canvas):
        canvas.delete("gradient")
        width = canvas.winfo_width() or 1
        height = canvas.winfo_height() or 1
        start = (8, 14, 28)
        end = (20, 52, 92)
        steps = max(height, 1)
        r_step = (end[0] - start[0]) / steps
        g_step = (end[1] - start[1]) / steps
        b_step = (end[2] - start[2]) / steps
        for i in range(steps):
            r = int(start[0] + (r_step * i))
            g = int(start[1] + (g_step * i))
            b = int(start[2] + (b_step * i))
            color = f"#{r:02x}{g:02x}{b:02x}"
            canvas.create_rectangle(0, i, width, i + 1, outline=color, fill=color, tags="gradient")
        canvas.lower("gradient")
        if getattr(self, "_header_current_id", None):
            canvas.coords(self._header_current_id, width - 20, 28)

    def _build_config_frame(self):
        frame = ttk.Frame(self.page_container, style="Card.TFrame")
        self.frames["config"] = frame
        frame.grid(row=0, column=0, sticky="nsew")

        form = ttk.LabelFrame(frame, text="Storage Arrays (mDNS + Manual)", style="TLabelframe")
        form.pack(fill="x", pady=8)

        self.storage_entry = ttk.Entry(form)
        self.storage_entry.grid(row=0, column=0, padx=8, pady=8, sticky="ew")
        ttk.Button(form, text="Add", style="Primary.TButton", command=self._add_storage).grid(
            row=0, column=1, padx=8, pady=8
        )
        ttk.Button(form, text="Delete Selected", style="Ghost.TButton", command=self._delete_storage).grid(
            row=0, column=2, padx=8, pady=8
        )
        ttk.Button(form, text="Discover (mDNS)", style="Ghost.TButton", command=self._discover_storage).grid(
            row=0, column=3, padx=8, pady=8
        )
        ttk.Checkbutton(
            form,
            text="Verbose output",
            variable=self.verbose_logs,
            command=self._schedule_save_state,
        ).grid(row=0, column=4, padx=8, pady=8, sticky="w")
        form.columnconfigure(0, weight=1)

        self.mdns_service = ttk.Entry(form)
        self.mdns_service.insert(0, "_sdsws._tcp.local.")
        # Restore persisted mDNS service type
        try:
            persisted_srv = (self._state.get("mdns_service") or "").strip()
            if persisted_srv:
                self.mdns_service.delete(0, tk.END)
                self.mdns_service.insert(0, persisted_srv)
        except Exception:
            pass

        self.mdns_service.bind("<FocusOut>", lambda e: self._schedule_save_state())
        self.mdns_service.bind("<Return>", lambda e: self._schedule_save_state())
        self.mdns_service.grid(row=1, column=0, padx=8, pady=4, sticky="ew")
        ttk.Label(form, text="mDNS service type", style="Muted.TLabel").grid(
            row=1, column=1, padx=8, pady=4, sticky="w"
        )
        ttk.Label(form, text="Example: _sdsws._tcp.local.", style="Caption.TLabel").grid(
            row=1, column=2, padx=8, pady=4, sticky="w"
        )

        list_frame = ttk.LabelFrame(frame, text="Discovered / Added Storage Arrays", style="TLabelframe")
        list_frame.pack(fill="both", expand=True, pady=8)

        columns = ("name", "host", "port")
        self.storage_tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse", height=7)
        self.storage_tree.heading("name", text="Name")
        self.storage_tree.heading("host", text="Host")
        self.storage_tree.heading("port", text="Port")
        self.storage_tree.column("name", width=120, minwidth=100, anchor="w", stretch=True)
        self.storage_tree.column("host", width=180, minwidth=140, anchor="w", stretch=True)
        self.storage_tree.column("port", width=70, minwidth=50, anchor="center", stretch=True)
        self.storage_tree.tag_configure("odd", background=C_TREE_ALT)
        self.storage_tree.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        tree_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.storage_tree.yview)
        self.storage_tree.configure(yscroll=tree_scroll.set)
        tree_scroll.grid(row=0, column=1, sticky="ns", pady=8)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        self.storage_tree.bind("<<TreeviewSelect>>", self._on_storage_tree_select)

    def _build_create_frame(self):
        frame = ttk.Frame(self.page_container, style="Card.TFrame")
        self.frames["create"] = frame
        frame.grid(row=0, column=0, sticky="nsew")

        form = ttk.LabelFrame(frame, text="Create Volume")
        form.pack(fill="x", pady=8)

        self.create_name = ttk.Entry(form)
        self.create_size = ttk.Entry(form)
        self.create_node = ttk.Combobox(form, values=self._storage_nodes())
        self.create_protocol = ttk.Combobox(
            form, values=self._platform_protocols(), state="readonly"
        )
        self.create_user = ttk.Entry(form)
        self.create_pw = ttk.Entry(form, show="*")
        self.create_protocol.set(self._default_protocol_for_platform())

        self._grid_row(form, 0, "Volume Name", self.create_name)
        self._grid_row(form, 1, "Size (GB)", self.create_size)
        self._grid_row(form, 2, "Storage Node (Array)", self.create_node)
        self._grid_row(form, 3, "Protocol", self.create_protocol)
        self._grid_row(form, 4, "User", self.create_user)
        self._grid_row(form, 5, "Password", self.create_pw)
        ttk.Label(form, text="Credentials are required for CIFS / iSCSI-Chap.", style="Muted.TLabel").grid(
            row=6, column=0, columnspan=2, padx=8, pady=(2, 0), sticky="w"
        )

        # Bind selection change to update header and persist last selection
        self.create_node.bind(
            "<<ComboboxSelected>>",
            lambda e: (self._set_current_array(self.create_node.get()), self._schedule_save_state()),
        )

        btn = ttk.Button(form, text="Create Volume", style="Primary.TButton", command=self._on_create)
        btn.grid(row=7, column=0, columnspan=2, pady=10)
        self._action_buttons = getattr(self, "_action_buttons", [])
        self._action_buttons.append(btn)

    def _build_mount_frame(self):
        frame = ttk.Frame(self.page_container, style="Card.TFrame")
        self.frames["mount"] = frame
        frame.grid(row=0, column=0, sticky="nsew")

        form = ttk.LabelFrame(frame, text="Mount Volume (Locally on this Computer)")
        form.pack(fill="x", pady=8)

        self.mount_name = ttk.Combobox(form, values=[], state="readonly")
        self.mount_path_var = tk.StringVar(value="Mount path: -")
        self._grid_row(form, 0, "Volume Name", self.mount_name)
        self.mount_name.bind("<<ComboboxSelected>>", lambda e: self._update_inferred_for_selected_volume())

        ttk.Button(form, text="Reload Volumes", style="Ghost.TButton", command=self._refresh_volumes).grid(
            row=1, column=0, pady=8
        )
        btn_mount = ttk.Button(form, text="Mount Volume", style="Primary.TButton", command=self._on_mount)
        btn_mount.grid(row=1, column=1, pady=8)
        self._action_buttons = getattr(self, "_action_buttons", [])
        self._action_buttons.append(btn_mount)
        ttk.Label(form, textvariable=self.mount_path_var).grid(
            row=2, column=0, columnspan=2, padx=8, pady=6, sticky="w"
        )
        btn_open = ttk.Button(form, text="Open Mount Folder", style="Ghost.TButton", command=self._open_mount_folder)
        btn_open.grid(row=3, column=0, columnspan=2, pady=8)
        self._action_buttons = getattr(self, "_action_buttons", [])
        self._action_buttons.append(btn_open)
        # Windows-only: allow auto init/format for iSCSI (first time only)
        if sys.platform.startswith("win"):
            ttk.Checkbutton(
                form,
                text="Auto initialize & format iSCSI disk (first time)",
                variable=self.auto_init_iscsi,
            ).grid(row=4, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="w")

    def _prompt_credentials(self):
        dlg = tk.Toplevel(self)
        dlg.title("SMB Credentials")
        dlg.transient(self)
        dlg.grab_set()

        user = tk.StringVar()
        pw = tk.StringVar()

        ttk.Label(dlg, text="Username").grid(row=0, column=0, padx=8, pady=6)
        ttk.Entry(dlg, textvariable=user).grid(row=0, column=1, padx=8, pady=6)
        ttk.Label(dlg, text="Password").grid(row=1, column=0, padx=8, pady=6)
        ttk.Entry(dlg, textvariable=pw, show="*").grid(row=1, column=1, padx=8, pady=6)

        result = {}

        def ok():
            result['user'] = user.get()
            result['pw'] = pw.get()
            dlg.destroy()

        def cancel():
            result['user'] = None
            result['pw'] = None
            dlg.destroy()

        ttk.Button(dlg, text="OK", command=ok).grid(row=2, column=0, padx=8, pady=10, sticky="ew")
        ttk.Button(dlg, text="Cancel", command=cancel).grid(row=2, column=1, padx=8, pady=10, sticky="ew")

        dlg.protocol("WM_DELETE_WINDOW", cancel)
        dlg.columnconfigure(0, weight=1)
        dlg.columnconfigure(1, weight=1)

        dlg.wait_window()
        return result.get('user'), result.get('pw')


    def _build_unmount_frame(self):
        frame = ttk.Frame(self.page_container, style="Card.TFrame")
        self.frames["unmount"] = frame
        frame.grid(row=0, column=0, sticky="nsew")

        form = ttk.LabelFrame(frame, text="Un-mount Volume (Locally)")
        form.pack(fill="x", pady=8)

        self.unmount_name = ttk.Combobox(form, values=[], state="readonly")
        self._grid_row(form, 0, "Volume Name", self.unmount_name)
        #self.unmount_name.bind("<<ComboboxSelected>>", lambda e: self._update_inferred_for_selected_volume())
        ttk.Button(form, text="Reload Volumes", style="Ghost.TButton", command=self._refresh_volumes).grid(
            row=1, column=0, pady=8
        )
        btn_unmount = ttk.Button(form, text="Un-mount Volume", style="Primary.TButton", command=self._on_unmount)
        btn_unmount.grid(row=1, column=1, pady=8)
        self._action_buttons = getattr(self, "_action_buttons", [])
        self._action_buttons.append(btn_unmount)

    def _build_delete_frame(self):
        frame = ttk.Frame(self.page_container, style="Card.TFrame")
        self.frames["delete"] = frame
        frame.grid(row=0, column=0, sticky="nsew")

        form = ttk.LabelFrame(frame, text="Delete Volume")
        form.pack(fill="x", pady=8)

        self.delete_name = ttk.Combobox(form, values=[], state="readonly")
        self._grid_row(form, 0, "Volume Name", self.delete_name)
        #self.delete_name.bind("<<ComboboxSelected>>", lambda e: self._update_inferred_for_selected_volume())
        ttk.Button(form, text="Reload Volumes", style="Ghost.TButton", command=self._refresh_volumes).grid(
            row=1, column=0, pady=8
        )
        btn_delete = ttk.Button(form, text="Delete Volume", style="Primary.TButton", command=self._on_delete)
        btn_delete.grid(row=1, column=1, pady=8)
        self._action_buttons = getattr(self, "_action_buttons", [])
        self._action_buttons.append(btn_delete)
    def _set_current_array(self, selection):
        disp = (selection or "").strip()
        if not disp:
            self.current_array_var.set("Storage: (none)")
            return
        self.current_array_var.set(f"Storage: {disp}")
    def _vol_display(self, name: str) -> str:
        """Return a display label like 'vol1 (CIFS) [SDS]' when metadata is known."""
        n = (name or "").strip()
        if not n:
            return ""
        meta = (self.volume_meta or {}).get(n) or {}
        proto = (meta.get("protocol") or "").strip()
        scope = (meta.get("scope") or "").strip()  # 'Local' or 'SDS'

        label = n
        if proto:
            label = f"{label} ({proto})"
        if scope:
            label = f"{label} [{scope}]"
        return label

    def _vol_value_to_name(self, value: str) -> str:
        """Convert a combobox value like 'vol1 (CIFS) [SDS]' back to raw volume name 'vol1'."""
        v = (value or "").strip()
        if not v:
            return ""
        # Strip scope suffix first: ' ... [SDS]'
        if v.endswith("]") and "[" in v:
            v = v.rsplit("[", 1)[0].strip()
        # Strip protocol suffix: ' ... (CIFS)'
        if v.endswith(")") and " (" in v:
            v = v.rsplit(" (", 1)[0].strip()
        return v
    def _infer_volume_scope(self, item) -> str:
        """Best-effort infer whether a volume is Local or SDS from the volumes row."""
        try:
            if isinstance(item, dict):
                # Common keys we've seen across variants
                for k in ("localSDS", "local_sds", "scope", "source", "location", "Local/SDS"):
                    if k in item:
                        val = item.get(k)
                        if val is None:
                            continue
                        s = str(val).strip().lower()
                        if s in ("local", "l"):
                            return "Local"
                        if s in ("sds", "remote"):
                            return "SDS"
                        # Some APIs use 0/1 or True/False
                        if s in ("0", "false"):
                            return "Local"
                        if s in ("1", "true"):
                            return "SDS"
                        if "local" in s:
                            return "Local"
                        if "sds" in s:
                            return "SDS"
        except Exception:
            pass
        # Default: SDS (because the list comes from SDS DB route)
        return "SDS"
    def _build_log_frame(self):
        log_frame = ttk.LabelFrame(self.content, text="Output")
        log_frame.grid(row=1, column=0, sticky="nsew", pady=8)
        self.log_text = tk.Text(
            log_frame,
            height=10,
            wrap="word",
            state="disabled",
            font=FONT_MONO,
            bg=C_CARD,
            fg=C_TEXT,
            insertbackground=C_TEXT,
        )
        self.log_text.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscroll=log_scroll.set)
        log_scroll.pack(side="right", fill="y", pady=8)
        ttk.Button(log_frame, text="Clear Log", style="Ghost.TButton", command=self._clear_log).pack(
            side="bottom", anchor="e", padx=8, pady=(0, 8)
        )

    def _grid_row(self, parent, row, label, widget):
        ttk.Label(parent, text=label).grid(row=row, column=0, padx=8, pady=6, sticky="w")
        widget.grid(row=row, column=1, padx=8, pady=6, sticky="ew")
        parent.columnconfigure(1, weight=1)

    def _show_frame(self, key):
        frame = self.frames.get(key)
        if frame:
            frame.tkraise()
        # Nav button highlight
        for k, btn in self.nav_buttons.items():
            btn.configure(style="NavActive.TButton" if k == key else "Nav.TButton")

    def _set_busy(self, busy: bool, message: str = ""):
        """Show a standard processing indicator and temporarily disable UI while tasks run."""
        try:
            if busy:
                self._busy_count += 1
                if message:
                    self._busy_msg = message

                # Only transition UI on first busy
                if self._busy_count == 1:
                    # Show overlay (modal feel)
                    try:
                        self._busy_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
                        self._busy_overlay.lift()
                        self._busy_bar.start(12)
                    except Exception:
                        pass

                    # Also show bottom progress bar (if present)
                    if self._progress is not None:
                        try:
                            self._progress.pack(side="right", padx=12, pady=4)
                        except Exception:
                            pass
                        try:
                            self._progress.start(12)
                        except Exception:
                            pass

                    # Disable navigation/buttons to prevent double submits
                    for btn in (self.nav_buttons or {}).values():
                        try:
                            btn.state(["disabled"])
                        except Exception:
                            pass

                    # Best-effort disable action buttons if present
                    try:
                        for w in getattr(self, "_action_buttons", []):
                            try:
                                w.state(["disabled"])
                            except Exception:
                                pass
                    except Exception:
                        pass

                # Always update status + overlay message
                ui_msg = (message or self._busy_msg or "Processing...").strip()
                if not ui_msg:
                    ui_msg = "Processing..."
                try:
                    self.status_var.set(ui_msg)
                except Exception:
                    pass
                try:
                    self._busy_detail.configure(text=ui_msg)
                except Exception:
                    pass

            else:
                if self._busy_count > 0:
                    self._busy_count -= 1

                # Only restore UI on last completion
                if self._busy_count <= 0:
                    self._busy_count = 0
                    self._busy_msg = ""

                    # Hide overlay unless a completion message is currently being shown
                    try:
                        self._busy_bar.stop()
                    except Exception:
                        pass
                    if not getattr(self, "_completion_showing", False):
                        try:
                            self._busy_overlay.place_forget()
                        except Exception:
                            pass

                    # Hide bottom progress bar
                    if self._progress is not None:
                        try:
                            self._progress.stop()
                        except Exception:
                            pass
                        try:
                            self._progress.pack_forget()
                        except Exception:
                            pass

                    # Re-enable navigation/buttons
                    for btn in (self.nav_buttons or {}).values():
                        try:
                            btn.state(["!disabled"])
                        except Exception:
                            pass

                    try:
                        for w in getattr(self, "_action_buttons", []):
                            try:
                                w.state(["!disabled"])
                            except Exception:
                                pass
                    except Exception:
                        pass

                    try:
                        self.status_var.set("Ready")
                    except Exception:
                        pass
        except Exception:
            # Never let busy UI break the app
            return

    def _node_display(self, node):
        """Return display string for a node dict."""
        if isinstance(node, dict):
            name = (node.get("name") or "").strip()
            host = (node.get("host") or "").strip()
            if name and host and name != host:
                return f"{name} ({host})"
            return host or name
        if isinstance(node, str):
            return node
        return ""

    def _storage_nodes_raw(self):
        return self.storage_nodes

    def _storage_nodes_display(self):
        return [self._node_display(n) for n in self._storage_nodes_raw() if self._node_display(n)]

    def _resolve_node_host(self, selection):
        """Given a combobox/listbox selection string, return the host/ip to use for API calls."""
        sel = (selection or "").strip()
        if not sel:
            return ""
        # If it's formatted as 'name (host)', extract host
        if sel.endswith(")") and "(" in sel:
            try:
                host = sel.rsplit("(", 1)[1].rstrip(")").strip()
                if host:
                    return host
            except Exception:
                pass
        # Otherwise match against saved nodes
        for n in self._storage_nodes_raw():
            if self._node_display(n) == sel:
                if isinstance(n, dict):
                    return (n.get("host") or "").strip()
                return str(n).strip()
        # Fallback: assume it's a host/ip
        return sel
    
    def _storage_nodes(self):
        return self._storage_nodes_display()

    def _refresh_storage_list(self):
        # Populate the Treeview with name, host, port
        self.storage_tree.delete(*self.storage_tree.get_children())
        for idx, n in enumerate(self._storage_nodes_raw()):
            if isinstance(n, dict):
                name = (n.get("name") or "").strip()
                host = (n.get("host") or "").strip()
                port = str(n.get("port") or "")
                tag = "odd" if idx % 2 else ""
                self.storage_tree.insert("", "end", iid=f"node-{idx}", values=(name, host, port), tags=(tag,))
            else:
                s = str(n).strip()
                tag = "odd" if idx % 2 else ""
                self.storage_tree.insert("", "end", iid=f"node-{idx}", values=(s, s, ""), tags=(tag,))
        self._refresh_comboboxes()
        self._schedule_save_state()

    def _refresh_comboboxes(self):
        nodes = self._storage_nodes()
        self.create_node["values"] = nodes
        if nodes:
            if not self.create_node.get():
                self.create_node.set(nodes[0])
            self._set_current_array(self.create_node.get() or nodes[0])
        else:
            self.create_node.set("")
            self._set_current_array("")

    def _bind_node_dropdowns(self):
        return

    def _add_storage(self):
        value = self.storage_entry.get().strip()
        if not value:
            messagebox.showwarning("Missing value", "Enter a storage IP or name.")
            return
        raw_nodes = self._storage_nodes_raw()
        host = value

        if any(isinstance(n, dict) and (n.get("host") == host) for n in raw_nodes):
            messagebox.showinfo("Exists", "This storage entry is already saved for this session.")
            return

        raw_nodes.append({"name": host, "host": host, "port": DEFAULT_API_PORT})
        self.storage_entry.delete(0, tk.END)
        self._refresh_storage_list()
        self._schedule_save_state()
        self._apply_persisted_selection()

    def _delete_storage(self):
        selected = self.storage_tree.selection()
        if not selected:
            messagebox.showinfo("Select", "Select an entry to delete.")
            return
        item = self.storage_tree.item(selected[0])
        vals = item.get("values", [])
        host = vals[1] if len(vals) > 1 else (vals[0] if vals else "")
        host = (host or "").strip()
        raw_nodes = self._storage_nodes_raw()
        idx = None
        for i, n in enumerate(raw_nodes):
            if isinstance(n, dict) and str(n.get("host", "")).strip() == host:
                idx = i
                break
            elif isinstance(n, str) and n.strip() == host:
                idx = i
                break
        if idx is not None:
            raw_nodes.pop(idx)
            self._refresh_storage_list()
            self._schedule_save_state()

    def _on_storage_tree_select(self, event):
        sel = self.storage_tree.selection()
        if not sel:
            return
        item = self.storage_tree.item(sel[0])
        vals = item.get("values", [])
        # vals: [name, host, port]
        display = vals[0] if vals and vals[0] else (vals[1] if len(vals) > 1 else "")
        self._set_current_array(display)
        # Only Create page has a node selector now
        disp = self._node_display({"name": vals[0], "host": vals[1], "port": vals[2]}) if len(vals) > 2 else display
        try:
            self.create_node.set(disp)
        except Exception:
            pass
        self._schedule_save_state()

    def _append_log(self, message):
        if not message.strip():
            return
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, message.rstrip() + "\n")
        self.log_text.configure(state="disabled")
        self.log_text.see(tk.END)

    def _poll_logs(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self._append_log(msg)
        except queue.Empty:
            pass
        self.after(200, self._poll_logs)

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state="disabled")

    def _state_dir(self) -> Path:
        """Return platform-appropriate config directory."""
        home = Path.home()
        if sys.platform.startswith("win"):
            base = os.environ.get("APPDATA") or str(home / "AppData" / "Roaming")
            return Path(base) / "GS_VolumeManager"
        if sys.platform.startswith("darwin"):
            return home / "Library" / "Application Support" / "GS_VolumeManager"
        # Linux / other unix
        xdg = os.environ.get("XDG_CONFIG_HOME")
        if xdg:
            return Path(xdg) / "gs_volumemanager"
        return home / ".config" / "gs_volumemanager"

    def _state_path(self) -> Path:
        return self._state_dir() / "state.json"

    def _load_state(self):
        """Load persisted state from disk into self._state."""
        try:
            p = self._state_path()
            if not p.exists():
                return
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._state.update(data)
        except Exception:
            return

    def _serialize_state(self) -> dict:
        """Build a JSON-serializable state dict from current in-memory values."""
        nodes = []
        for n in self.storage_nodes:
            if isinstance(n, dict):
                nodes.append({
                    "name": str(n.get("name") or "").strip(),
                    "host": str(n.get("host") or "").strip(),
                    "port": int(n.get("port") or DEFAULT_API_PORT),
                })
            else:
                s = str(n).strip()
                if s:
                    nodes.append({"name": s, "host": s, "port": DEFAULT_API_PORT})

        # current_array_var looks like "Storage: X"
        last_sel = (self.current_array_var.get() or "").replace("Storage:", "").strip()
        if last_sel.lower() in ("(none)", "none"):
            last_sel = ""

        mdns_val = ""
        try:
            mdns_val = self.mdns_service.get().strip()
        except Exception:
            mdns_val = (self._state.get("mdns_service") or "").strip()

        try:
            verbose_val = bool(self.verbose_logs.get())
        except Exception:
            verbose_val = False

        return {
            "storage_nodes": nodes,
            "last_selected_node": last_sel,
            "volume_meta": dict(self.volume_meta or {}),
            "mounted_targets": dict(self.mounted_targets or {}),
            "mdns_service": mdns_val,
            "verbose_logs": verbose_val,
        }

    def _schedule_save_state(self):
        """Debounced save to avoid frequent disk writes."""
        self._state_dirty = True
        if self._state_save_job is not None:
            try:
                self.after_cancel(self._state_save_job)
            except Exception:
                pass
        self._state_save_job = self.after(300, self._save_state_now)

    def _save_state_now(self):
        self._state_save_job = None
        if not self._state_dirty:
            return
        try:
            self._state_dirty = False
            payload = self._serialize_state()
            d = self._state_dir()
            d.mkdir(parents=True, exist_ok=True)
            self._state_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")
            self._state = payload
        except Exception:
            return

    def _apply_persisted_selection(self):
        """After widgets exist, apply last selected node to comboboxes/header."""
        try:
            last = (self._state.get("last_selected_node") or "").strip()
            if not last:
                return

            nodes = self._storage_nodes()
            chosen = ""
            for disp in nodes:
                if disp == last:
                    chosen = disp
                    break
                if self._resolve_node_host(disp) == last:
                    chosen = disp
                    break
            if not chosen:
                chosen = last

            # Only Create page has a node selector now
            try:
                self.create_node.set(chosen)
            except Exception:
                pass
            self._set_current_array(chosen)
        except Exception:
            pass

    def _on_close(self):
        try:
            self._save_state_now()
        finally:
            try:
                if getattr(self, "_compute_server", None) is not None:
                    self._compute_server.shutdown()
            except Exception:
                pass
            self.destroy()

    def _discover_storage(self, silent=False):
        if Zeroconf is None:
            if not silent:
                messagebox.showwarning("mDNS unavailable", "Install 'zeroconf' to use discovery.")
            self.log_queue.put("mDNS discovery unavailable (missing zeroconf).")
            self.status_var.set("Discovery unavailable")
            return
        service_type = self.mdns_service.get().strip()
        # Normalise common user inputs
        if service_type and not service_type.endswith(".local."):
            # If user entered like _sdsws._tcp, make it a full zeroconf type
            if service_type.endswith("._tcp") or service_type.endswith("._udp"):
                service_type = service_type + ".local."
        if not service_type:
            if not silent:
                messagebox.showwarning("Missing service type", "Enter a service type to browse.")
            self.status_var.set("Missing service type")
            return

        self.status_var.set("Discovering...")
        def task():
            try:
                zc = Zeroconf()
                found = {}

                class Listener:
                    # Newer zeroconf versions call these methods; keep them even if empty.
                    def remove_service(self, zc_ref, srv_type, name):
                        return

                    def update_service(self, zc_ref, srv_type, name):
                        # Treat updates the same as add; refresh IP if it changes.
                        self.add_service(zc_ref, srv_type, name)

                    def add_service(self, zc_ref, srv_type, name):
                        try:
                            info = zc_ref.get_service_info(srv_type, name, timeout=2000)
                        except TypeError:
                            # Older zeroconf get_service_info without timeout kw
                            info = zc_ref.get_service_info(srv_type, name)

                        if not info or not getattr(info, "addresses", None):
                            return

                        disp_name = name.replace(srv_type, "").strip(".")
                        for addr in info.addresses:
                            if len(addr) == 4:
                                ip = socket.inet_ntoa(addr)
                                found[disp_name or ip] = ip
                                return

                listener = Listener()

                # zeroconf API compatibility: some versions expect `listeners=[...]`
                try:
                    ServiceBrowser(zc, service_type, listeners=[listener])
                except TypeError:
                    ServiceBrowser(zc, service_type, listener)

                # Give discovery a bit more time on Wi-Fi / busy networks
                time.sleep(5.0)
                zc.close()

                # Merge discoveries into the session list (avoid wiping manual entries)
                if found:
                    existing = set()
                    for n in self.storage_nodes:
                        if isinstance(n, dict):
                            if n.get("host"):
                                existing.add(str(n.get("host")).strip())
                            if n.get("name"):
                                existing.add(str(n.get("name")).strip())
                        else:
                            existing.add(str(n).strip())
                    for nname, ip in found.items():
                        if ip in existing or nname in existing:
                            continue
                        self.storage_nodes.append({"name": nname, "host": ip, "port": DEFAULT_API_PORT})

                self.after(0, self._refresh_storage_list)
                self.after(0, self._schedule_save_state)
                if found:
                    pretty = ", ".join(
                        f"{name} ({ip})" if name != ip else name for name, ip in found.items()
                    )
                    self.log_queue.put(f"Discovered nodes: {pretty}")
                    self.after(0, lambda: self.status_var.set("Ready"))
                else:
                    self.log_queue.put("Discovered nodes: none")
                    self.after(0, lambda: self.status_var.set("No arrays discovered"))
            except Exception:
                self.after(0, lambda: self.status_var.set("Discovery failed"))

        self._run_task(task, "Discovering storage arrays...")

    def _run_task(self, task, busy_message: str = "Processing..."):
        def worker():
            buffer = io.StringIO()
            self.after(0, lambda: self._set_busy(True, busy_message))
            self.after(0, lambda: self.update_idletasks())

            ok = True
            exc_text = ""
            try:
                with redirect_stdout(buffer), redirect_stderr(buffer):
                    task()
            except Exception as exc:
                ok = False
                exc_text = f"{type(exc).__name__}: {exc}"
                buffer.write(f"Error: {exc_text}\n")
                try:
                    buffer.write(traceback.format_exc() + "\n")
                except Exception:
                    pass
            finally:
                self.after(0, lambda: self._set_busy(False))

            raw_out = buffer.getvalue() or ""
            cleaned = self._clean_output(raw_out)

            # --- Filter out "Checking reachability" lines for summary ---
            info_lines = []
            cleaned_lines = []
            for ln in cleaned.splitlines():
                if "checking reachability" in ln.lower():
                    info_lines.append(ln)
                else:
                    cleaned_lines.append(ln)
            cleaned_for_summary = "\n".join(cleaned_lines).strip()

            # Decide a concise message for status + log
            fallback_success = self._success_msg_from_busy(busy_message)
            summary = self._summarise_for_user(cleaned_for_summary, fallback_success)
          # Never show reachability checks in the overlay completion message
            if summary and "reachability" in summary.lower():
                summary = fallback_success if ok else "Operation failed"

            # Update status bar with a short message
            self.after(0, lambda: self.status_var.set(summary if summary else ("Ready" if ok else "Failed")))
            # Show completion overlay message
            self.after(0, lambda: self._show_completion(ok, summary or (fallback_success if ok else "Operation failed")))

            # For success: show only meaningful output (or one-line success)
            if ok:
                # By default, show only the one-line summary. Verbose mode shows cleaned details.
                if bool(self.verbose_logs.get()):
                    if cleaned:
                        self.log_queue.put(cleaned + "\n")
                    else:
                        self.log_queue.put(fallback_success + "\n")
                else:
                    # Always show info_lines (e.g. reachability) in Output tab, even if not in summary
                    for il in info_lines:
                        self.log_queue.put(il + "\n")
                    self.log_queue.put((summary or fallback_success) + "\n")
                return

            # For failure: show a friendly message + include the cleaned details in log
            def _show_err():
                msg = summary or (exc_text or "Operation failed")
                messagebox.showerror("Operation failed", msg)

            self.after(0, _show_err)
            if bool(self.verbose_logs.get()):
                if cleaned:
                    self.log_queue.put(cleaned + "\n")
                else:
                    self.log_queue.put((summary or "Operation failed") + "\n")
            else:
                # Non-verbose still shows the concise summary, plus the last cleaned lines (includes traceback tail)
                self.log_queue.put((summary or "Operation failed") + "\n")
                if cleaned:
                    self.log_queue.put(cleaned + "\n")

        threading.Thread(target=worker, daemon=True).start()

    def _clean_output(self, text: str) -> str:
        """Remove spinner/progress noise and overly verbose debug lines, but preserve tracebacks."""
        if not text:
            return ""
        has_traceback = "Traceback (most recent call last):" in text
        cleaned = []
        for raw in text.splitlines():
            line = raw.strip("\r\n")
            if not line.strip():
                continue

            # Preserve traceback formatting lines verbatim
            if has_traceback and (line.startswith("Traceback (") or line.startswith("  File ") or line.lstrip().startswith("File ")):
                cleaned.append(line)
                continue
            # Preserve the actual code line following the File ... line
            if has_traceback and raw.startswith("    "):
                cleaned.append(raw.rstrip("\r\n"))
                continue

            # Drop spinner/progress animations
            if "SDS Volume..." in line and any(ch in line for ch in ["|", "/", "-", "\\"]):
                continue
            if line.startswith("Creating SDS Volume") or line.startswith("Mounting SDS Volume") or line.startswith("Unmounting SDS Volume") or line.startswith("Deleting SDS Volume"):
                continue

            # Drop Werkzeug request logs (compute service)
            if line.startswith("127.0.0.1 - - ["):
                continue

            # Drop very chatty debug that isn't useful to the tester
            if not bool(getattr(self, "verbose_logs", tk.BooleanVar(value=False)).get()):
                if line.startswith("ShowCifsMount") or line.startswith("mount_cifs arguments"):
                    continue
            if line.startswith("Windows cannot list CIFS shares"):
                continue
            if line.startswith("sync mount Error1:"):
                continue
            if "No Compute found for volume name" in line:
                continue

            cleaned.append(line)

        # Keep only the most relevant lines, avoid huge dumps.
        # But if a traceback is present, keep a larger tail so we retain the failing line.
        limit = 120 if has_traceback else 25
        if len(cleaned) > limit:
            cleaned = cleaned[-limit:]
        return "\n".join(cleaned).strip()

    def _summarise_for_user(self, cleaned: str, fallback_success: str) -> str:
        """Pick a short meaningful message from the cleaned output."""
        if not cleaned:
            return fallback_success

        # Prefer explicit success lines
        for key in (
            "Successfully",
            "successfully",
            "Volume Created Successfully",
            "Volume Mounted Successfully",
            "Volume Unmounted Successfully",
            "Volume Deleted Successfully",
            "Volume Action OK",
        ):
            for ln in cleaned.splitlines():
                if key in ln:
                    return ln.strip()

        # Prefer explicit error lines
        for key in ("Error:", "Failed", "not reachable", "not found", "refused", "cannot"):
            for ln in cleaned.splitlines():
                if key.lower() in ln.lower():
                    return ln.strip()

        # Otherwise, use the last non-empty line
        lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
        return (lines[-1] if lines else fallback_success)

    def _success_msg_from_busy(self, busy_message: str) -> str:
        base = (busy_message or "Operation").strip()
        base = base.replace("...", "").strip()
        if not base:
            base = "Operation"
        return f"{base} successful."

    def _prepare_array(self, node_selection):
        """Prepare connection to the storage array API (controller mode)."""
        if not node_selection:
            raise RuntimeError("Storage node is required.")

        host = self._resolve_node_host(node_selection)
        if not host or host.lower() in ("none", "(none)"):
            raise RuntimeError("Storage node is required.")

        # Determine port from saved config if available
        port = DEFAULT_API_PORT
        for n in self._storage_nodes_raw():
            if self._node_display(n) == node_selection and isinstance(n, dict):
                try:
                    port = int(n.get("port") or DEFAULT_API_PORT)
                except Exception:
                    port = DEFAULT_API_PORT
                break

        sdsClient.URL = f"http://{host}:{port}"
        if not sdsClient.is_strorge_node_reachable(sdsClient.URL):
            raise RuntimeError(f"Storage Node {host} is not reachable at {sdsClient.URL}.")

    def _on_create(self):
        name = self.create_name.get().strip()
        size = self.create_size.get().strip()
        node = self.create_node.get().strip()
        protocol = self.create_protocol.get().strip()
        user = self.create_user.get().strip()
        pw = self.create_pw.get().strip()

        if not name or not size or not node or not protocol:
            messagebox.showwarning("Missing fields", "Fill in volume name, size, node, and protocol.")
            return
        if protocol in ("CIFS", "iSCSI-Chap") and (not user or not pw):
            messagebox.showwarning("Missing credentials", "User and password are required for CIFS or iSCSI-Chap.")
            return
        # Prevent accidental duplicate names (Local or SDS)
        existing = set((self.volume_meta or {}).keys())
        if name in existing:
            meta = (self.volume_meta or {}).get(name) or {}
            scope = (meta.get("scope") or "").strip()
            proto = (meta.get("protocol") or "").strip()
            hint = ""
            if proto and scope:
                hint = f" ({proto}) [{scope}]"
            elif proto:
                hint = f" ({proto})"
            elif scope:
                hint = f" [{scope}]"
            messagebox.showwarning(
                "Volume already exists",
                f"'{name}' already exists{hint}.\n\nPlease select it from Mount/Un-mount/Delete instead of creating it again.",
            )
            return
        def task():
            self._prepare_array(node)
            host = self._resolve_node_host(node)
            args = SimpleNamespace(
                name=name,
                size=size,
                # sdsClient expects an API host/IP here (not the display string)
                Snode=host,
                protocol=protocol,
                user=user,
                pw=pw,
            )
            sdsClient.cmd_create_volume(args)
            # Refresh volumes so the newly created volume appears in dropdowns immediately
            try:
                volumes = sdsClient.readSDSVolumes() or []
                print("DEBUG volumes sample:", volumes[:1])
                proto_by_id = {}
                try:
                    proto_by_id = {v: k for k, v in (sdsClient.PROTOCOLS or {}).items()}
                except Exception:
                    proto_by_id = {}

                names_all = []
                seen = set()
                for item in volumes:
                    scope = "SDS"  # default scope if API row doesn't include it
                    if isinstance(item, dict):
                        vname = str(item.get("name") or item.get("volumeName") or item.get("vol_name") or "").strip()
                        pid = item.get("protocolId") or item.get("protocol") or item.get("protocol_id")
                        scope = self._infer_volume_scope(item)
                    elif isinstance(item, (list, tuple)) and len(item) > 2:
                        vname = str(item[1]).strip()
                        pid = item[2]
                        # tuple/list rows don't carry scope; keep default
                    else:
                        continue

                    if not vname or vname in seen:
                        continue
                    seen.add(vname)

                    try:
                        pid_int = int(pid)
                    except Exception:
                        pid_int = None
                    inferred_proto = proto_by_id.get(pid_int) or ("CIFS" if sys.platform.startswith("win") else "NFS")

                    prev = self.volume_meta.get(vname) or {}
                    state = prev.get("state")
                    self.volume_meta[vname] = {
                        "node": node,
                        "protocol": inferred_proto,
                        "scope": scope,
                        "state": state,
                    }
                    names_all.append(vname)

                names_all = sorted(names_all)
                self.after(0, lambda: self._update_volume_lists(names_all))
            except Exception:
                pass
            # Remember this volume + node for later Mount/Un-mount/Delete flows
            self.volume_meta[name] = {"node": node, "protocol": protocol, "scope": "SDS"}

            # Ensure the selected storage node is present in the saved list
            def _remember_node():
                host_ip = host
                raw_nodes = self._storage_nodes_raw()
                if not any(isinstance(n, dict) and str(n.get("host", "")).strip() == host_ip for n in raw_nodes):
                    raw_nodes.append({"name": host_ip, "host": host_ip, "port": DEFAULT_API_PORT})
                self._refresh_storage_list()
                # Only Create page has a node selector now
                try:
                    self.create_node.set(self._node_display({"name": host_ip, "host": host_ip, "port": DEFAULT_API_PORT}))
                except Exception:
                    pass
                self._set_current_array(self._node_display({"name": host_ip, "host": host_ip, "port": DEFAULT_API_PORT}))
                self._schedule_save_state()

            self.after(0, _remember_node)
            self._schedule_save_state()

        self._run_task(task, "Creating volume...")

    def _refresh_volumes(self):
        # Refresh volumes against the currently selected storage array in the header / create page.
        node = (self.create_node.get().strip() or "").strip()
        if not node:
            node = (self.current_array_var.get() or "").replace("Storage:", "").strip()
        if not node:
            messagebox.showwarning("Missing node", "Select a storage node to refresh volumes.")
            return

        def task():
            self._prepare_array(node)
            volumes = sdsClient.readSDSVolumes() or []

          # Build protocolId -> name mapping
            proto_by_id = {}
            try:
                proto_by_id = {v: k for k, v in (sdsClient.PROTOCOLS or {}).items()}
            except Exception:
                proto_by_id = {}

            names_all = []
            seen = set()

            for item in volumes:
              # Accept both tuple/list and dict rows
                scope = "SDS"  # default scope if API row doesn't include it
                if isinstance(item, dict):
                    vname = str(item.get("name") or item.get("volumeName") or item.get("vol_name") or "").strip()
                    pid = item.get("protocolId") or item.get("protocol") or item.get("protocol_id")
                    scope = self._infer_volume_scope(item)
                elif isinstance(item, (list, tuple)) and len(item) > 2:
                    vname = str(item[1]).strip()
                    pid = item[2]
                    # tuple/list rows don't carry scope; keep default
                else:
                    continue

                if not vname or vname in seen:
                    continue
                seen.add(vname)

              # Infer protocol from pid/id
                try:
                    pid_int = int(pid)
                except Exception:
                    pid_int = None
                inferred_proto = proto_by_id.get(pid_int) or ("CIFS" if sys.platform.startswith("win") else "NFS")

              # Keep any previously inferred state if present, but do not depend on it
                prev = self.volume_meta.get(vname) or {}
                state = prev.get("state")
                self.volume_meta[vname] = {
                    "node": node,
                    "protocol": inferred_proto,
                    "scope": scope,
                    "state": state,
                }

                names_all.append(vname)

            names_all = sorted(names_all)
            self.after(0, lambda: self._update_volume_lists(names_all))

        self._run_task(task, "Loading volumes...")

    def _update_volume_lists(self, names):
        # Build display values with protocol suffix when available
        names = list(names or [])
        names_display = [self._vol_display(n) for n in names]

        # Mount page: show only volumes not already mounted on this computer
        mounted_set = set(self.mounted_targets or {})
        unmounted = [n for n in names if n not in mounted_set]
        names_display = [self._vol_display(n) for n in unmounted]
        self.mount_name["values"] = names_display
        try:
          # Keep Mount combobox strictly read-only and from discovered list
            self.mount_name.configure(state="readonly")
        except Exception:
            pass
        # Un-mount page: show ONLY volumes mounted on this computer
        # Clean stale entries (e.g., iSCSI connected but never got a drive letter; app restart; manual dismount)
        try:
            if sys.platform.startswith("win"):
                for vv, lp in list((self.mounted_targets or {}).items()):
                    meta = (self.volume_meta or {}).get(vv) or {}
                    proto = (meta.get("protocol") or "").strip()
                    if proto.startswith("iSCSI"):
                        # Only keep iSCSI entries that have a real drive letter
                        if not self._is_real_windows_drive(self._normalize_windows_drive(str(lp or ""))):
                            self.mounted_targets.pop(vv, None)
            # If nothing left mounted, keep UI consistent
        except Exception:
            pass

        mounted = sorted([v for v in (self.mounted_targets or {}).keys()])
        mounted_display = [self._vol_display(v) for v in mounted]
        self.unmount_name["values"] = mounted_display

        # Delete page: show all discovered volumes
        all_display = [self._vol_display(n) for n in names]
        self.delete_name["values"] = all_display

      # Preserve existing selections if still valid, otherwise pick first item
        try:
            cur_mount = (self.mount_name.get() or "").strip()
            if names_display:
                self.mount_name.set(cur_mount if cur_mount in names_display else names_display[0])
            else:
                self.mount_name.set("")
        except Exception:
            pass

        try:
            cur_unmount = (self.unmount_name.get() or "").strip()
            if mounted_display:
                self.unmount_name.set(cur_unmount if cur_unmount in mounted_display else mounted_display[0])
            else:
                self.unmount_name.set("")
        except Exception:
            pass

        try:
            cur_delete = (self.delete_name.get() or "").strip()
            if names_display:
                self.delete_name.set(cur_delete if cur_delete in names_display else names_display[0])
            else:
                self.delete_name.set("")
        except Exception:
            pass

        self._append_log(f"Discovered volumes: {', '.join(names) if names else 'none'}")

        # If nothing is mounted locally, give a clear hint in the status bar
        if not mounted:
            try:
                self.status_var.set("No volumes mounted on this computer")
            except Exception:
                pass

        self._update_inferred_for_selected_volume()
        self._schedule_save_state()

    def _update_inferred_for_selected_volume(self):
        vol = ""
        try:
            if getattr(self, "mount_name", None) and self.mount_name.get().strip():
                vol = self._vol_value_to_name(self.mount_name.get().strip())
            elif getattr(self, "unmount_name", None) and self.unmount_name.get().strip():
                vol = self._vol_value_to_name(self.unmount_name.get().strip())
            elif getattr(self, "delete_name", None) and self.delete_name.get().strip():
                vol = self._vol_value_to_name(self.delete_name.get().strip())
        except Exception:
            vol = ""
        meta = self.volume_meta.get(vol) or {}
        node = meta.get("node") or "(unknown)"
        # Keep header aligned with selected storage when known
        if node and node != "(unknown)":
            self._set_current_array(node)
    def _compute_service_base(self):
        # Normalise URL (no trailing slash)
        return (COMPUTE_SERVICE_URL or "").rstrip("/")

    def _compute_service_alive(self) -> bool:
        base = self._compute_service_base()
        if not base:
            return False
        # Important: urllib treats HTTP 404/500 as exceptions (HTTPError),
        # but those still prove the service is reachable.
        try:
            req = urllib.request.Request(f"{base}/", method="GET")
            with urllib.request.urlopen(req, timeout=1.2) as resp:
                _ = resp.read(1)
            return True
        except urllib.error.HTTPError:
            # Service responded (even if endpoint is missing)
            return True
        except Exception:
            return False

    def _start_compute_service_inprocess(self) -> bool:
        """Start compute-node Flask app in-process using a background thread.

        Notes:
        - Requires computenode_service_client.py to be importable and to expose `app`.
        - Requires werkzeug to be present (Flask depends on it, but some packaged builds omit it).
        """
        if self._compute_server is not None:
            return True
        if _compute_svc is None:
            self.log_queue.put("Compute service: import failed (computenode_service_client not available)")
            return False

        app = getattr(_compute_svc, "app", None)
        if app is None:
            self.log_queue.put("Compute service: computenode_service_client has no 'app' attribute")
            return False

        try:
            from werkzeug.serving import make_server
        except Exception as e:
            self.log_queue.put(f"Compute service: cannot import werkzeug.make_server ({e})")
            return False

        try:
            u = urllib.parse.urlparse(self._compute_service_base())
            port = int(u.port or 4002)
        except Exception:
            port = 4002

        # IMPORTANT:
        # - The GUI calls the service on localhost (COMPUTE_SERVICE_URL defaults to 127.0.0.1)
        # - But the service must bind to a LAN-reachable interface so the Storage Node can call it too.
        #   Using 0.0.0.0 is the simplest and matches the standalone script behaviour.
        host = COMPUTE_BIND_HOST

        try:
            server = make_server(host, port, app)
        except Exception as e1:
            # If binding to non-loopback fails, fall back to loopback
            try:
                server = make_server("127.0.0.1", port, app)
            except Exception as e2:
                self.log_queue.put(f"Compute service: bind failed on {host}:{port} ({e1}); fallback 127.0.0.1:{port} failed ({e2})")
                return False

        def _serve():
            try:
                server.serve_forever()
            except Exception as e:
                self.log_queue.put(f"Compute service: server thread stopped ({e})")

        t = threading.Thread(target=_serve, daemon=True)
        t.start()

        self._compute_server = server
        self._compute_thread = t
        self.log_queue.put(
            f"Compute service: started in-process (bind {host}:{port}; local {self._compute_service_base()})"
        )
        return True

    def _start_compute_service_subprocess(self) -> bool:
        """Fallback: start computenode_service_client.py as a subprocess.

        Useful in dev mode or when in-process start is not possible.
        """
        # In a PyInstaller onefile/onedir build, sys.executable points to the frozen GUI binary.
        # Spawning it will relaunch the GUI (what you're seeing now). So we disable subprocess
        # auto-start in frozen builds and rely on the in-process server instead.
        if getattr(sys, "frozen", False):
            self.log_queue.put("Compute service: subprocess auto-start disabled in frozen build")
            return False
        try:
            base_dir = Path(__file__).resolve().parent
            svc_path = base_dir / "computenode_service_client.py"
            if not svc_path.exists():
                self.log_queue.put(f"Compute service: subprocess file not found at {svc_path}")
                return False

            if self._compute_service_alive():
                return True

            # Start hidden on Windows to avoid a console popping up
            creationflags = 0
            startupinfo = None
            if sys.platform.startswith("win"):
                try:
                    creationflags = subprocess.CREATE_NO_WINDOW
                except Exception:
                    creationflags = 0

            subprocess.Popen(
                [sys.executable, str(svc_path)],
                cwd=str(base_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
                startupinfo=startupinfo,
            )
            self.log_queue.put("Compute service: started as subprocess")
            return True
        except Exception as e:
            self.log_queue.put(f"Compute service: failed to start subprocess ({e})")
            return False

    def _ensure_compute_service(self):
        """Ensure the local compute-node service is available, else auto-start it."""
        if self._compute_service_alive():
            return

        reasons = []

        try:
            if self._start_compute_service_inprocess():
                reasons.append("started in-process")
        except Exception as e:
            reasons.append(f"in-process exception: {e}")

        # If still not alive, try subprocess (DEV mode only; disabled in frozen builds)
        if not getattr(sys, "frozen", False) and not self._compute_service_alive():
            try:
                if self._start_compute_service_subprocess():
                    reasons.append("started as subprocess")
            except Exception as e:
                reasons.append(f"subprocess exception: {e}")

        # Wait briefly for the service to come up
        for _ in range(20):
            if self._compute_service_alive():
                return
            time.sleep(0.25)

        extra = ("; ".join(reasons) if reasons else "no start attempt succeeded")
        raise RuntimeError(
            f"Compute-node service is not reachable at {self._compute_service_base()}. "
            f"Tried: {extra}. "
            "Please start computenode_service_client.py on this computer (compute node)."
        )
    def _post_json(self, url, payload, timeout=20):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status_code = getattr(resp, "status", None)
        try:
            obj = json.loads(raw)
        except Exception:
            obj = {"message": raw}
        # Always include HTTP status for debugging/decision making
        if isinstance(obj, dict) and "http_status" not in obj:
            obj["http_status"] = status_code
        return obj
    def _run_powershell(self, command: str, timeout: int = 90):
        """Run a PowerShell command on Windows and return (rc, stdout, stderr).

        Notes:
        - Prefer Windows PowerShell (powershell.exe). If not present, fall back to PowerShell 7 (pwsh).
        - Some PowerShell errors are written to stdout rather than stderr; callers should inspect (stdout+stderr).
        """
        if not sys.platform.startswith("win"):
            return 0, "", ""

        shell_exes = ["powershell", "pwsh"]
        last_err = ""

        for exe in shell_exes:
            try:
                p = subprocess.run(
                    [
                        exe,
                        "-NoProfile",
                        "-NonInteractive",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-Command",
                        command,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                stdout = (p.stdout or "")
                stderr = (p.stderr or "")
                return p.returncode, stdout, stderr
            except FileNotFoundError as e:
                # Try next PowerShell executable
                last_err = str(e)
                continue
            except subprocess.TimeoutExpired as e:
                # Return any partial output to help debugging
                out = ""
                err = ""
                try:
                    if getattr(e, "stdout", None):
                        out = e.stdout if isinstance(e.stdout, str) else e.stdout.decode("utf-8", errors="replace")
                    if getattr(e, "stderr", None):
                        err = e.stderr if isinstance(e.stderr, str) else e.stderr.decode("utf-8", errors="replace")
                except Exception:
                    pass
                return 1, out or "", (err or "") + f"\nTimeoutExpired: {e}"
            except Exception as e:
                last_err = str(e)
                break

        return 1, "", last_err

    def _windows_get_iscsi_drive_letter(self, disk_number: int) -> str:
        """Return the assigned drive letter (e.g. 'F:') for an already-formatted iSCSI disk."""
        ps = (
            f"Get-Partition -DiskNumber {disk_number} "
            "| Where-Object {$_.DriveLetter} "
            "| Select-Object -First 1 -ExpandProperty DriveLetter"
        )
        rc, out, _ = self._run_powershell(ps, timeout=15)
        if rc == 0:
            dl = (out or "").strip()
            if dl and dl.isalpha():
                return dl + ":"
        return ""

    def _windows_iscsi_snapshot_disks(self):
        """Return a dict of iSCSI disk Number -> PartitionStyle (RAW/GPT/etc)."""
        if not sys.platform.startswith("win"):
            return {}
        ps = "Get-Disk | Where-Object {$_.BusType -eq 'iSCSI'} | Select-Object Number,PartitionStyle | ConvertTo-Json"
        rc, out, err = self._run_powershell(ps, timeout=30)
        if rc != 0 or not out.strip():
            return {}
        try:
            obj = json.loads(out)
            if isinstance(obj, dict):
                obj = [obj]
            snap = {}
            for it in (obj or []):
                try:
                    num = int(it.get("Number"))
                    style = str(it.get("PartitionStyle") or "").strip()
                    snap[num] = style
                except Exception:
                    continue
            return snap
        except Exception:
            return {}

    def _windows_iscsi_auto_init_new_raw_disk(self, before: dict, after: dict):
        """If exactly one NEW iSCSI disk appears as RAW after connect, initialize + format it.

        Returns:
            str: drive letter like 'F:' if created, else ''
        """
        if not sys.platform.startswith("win"):
            return ""

        before = before or {}
        after = after or {}

        print(f"[iSCSI] disk_before={before}")
        print(f"[iSCSI] disk_after={after}")

        # Identify new disk numbers
        new_nums = [n for n in after.keys() if n not in before]
        print(f"[iSCSI] new disk numbers detected: {new_nums}")

        # If no new disk numbers, fall back to any RAW disk that wasn't RAW before
        candidates_raw = []
        candidates_formatted = []
        if new_nums:
            for n in new_nums:
                style = str(after.get(n, "")).upper()
                if style == "RAW":
                    candidates_raw.append(n)
                else:
                    candidates_formatted.append(n)
        else:
            for n, style in after.items():
                if str(before.get(n, "")).upper() != str(style).upper():
                    if str(style).upper() == "RAW":
                        candidates_raw.append(n)

        # If a new disk already appears formatted (e.g. initialized by storage-node callback),
        # just retrieve its drive letter — no need to re-format.
        if not candidates_raw and len(candidates_formatted) == 1:
            return self._windows_get_iscsi_drive_letter(candidates_formatted[0])

        print(f"[iSCSI] candidates_raw={candidates_raw}, candidates_formatted={candidates_formatted}")

        # Only auto-init when we can unambiguously pick exactly one RAW disk
        if len(candidates_raw) != 1:
            print(f"[iSCSI] Cannot auto-init: need exactly 1 RAW candidate, found {len(candidates_raw)}")
            return ""

        disk_num = candidates_raw[0]

        # Initialize + create partition + format + capture assigned drive letter
        ps = (
            f"$n={disk_num}; "
            "Initialize-Disk -Number $n -PartitionStyle GPT -ErrorAction Stop; "
            "$p = New-Partition -DiskNumber $n -UseMaximumSize -AssignDriveLetter -ErrorAction Stop; "
            "Format-Volume -Partition $p -FileSystem NTFS -Confirm:$false -ErrorAction Stop | Out-Null; "
            "$dl = ($p | Select-Object -ExpandProperty DriveLetter); "
            "if ($dl) { $dl + ':' } else { '' }"
        )

        print(f"[iSCSI] Running Initialize-Disk on disk {disk_num} ...")
        rc, out, err = self._run_powershell(ps, timeout=240)
        if rc == 0:
            dl = (out or "").strip()
            if len(dl) == 2 and dl[1] == ":" and dl[0].isalpha():
                print(f"[iSCSI] Disk {disk_num} initialized and formatted. Drive: {dl}")
                return dl
            print(f"[iSCSI] PowerShell rc=0 but unexpected drive output: {repr(dl)}")
        else:
            print(f"[iSCSI] Initialize-Disk failed: rc={rc}\n  stdout={repr(out)}\n  stderr={repr(err)}")
        return ""
    def _is_real_windows_drive(self, p: str) -> bool:
        p = (p or "").strip()
        return len(p) == 2 and p[1] == ":" and p[0].isalpha()

    def _normalize_windows_drive(self, p: str) -> str:
        p = (p or "").strip()
        if len(p) == 1 and p.isalpha():
            return f"{p.upper()}:"
        if self._is_real_windows_drive(p):
            return f"{p[0].upper()}:"
        return ""
    def _windows_iscsi_has_connected_session(self, volume_name: str) -> bool:
        """Return True if Windows reports an active iSCSI session for the given volume."""
        if not sys.platform.startswith("win"):
            return False
        vol = (volume_name or "").strip().lower()
        if not vol:
            return False
        ps = (
            "Get-IscsiSession | Where-Object { $_.IsConnected -eq $true } | "
            "Select-Object -ExpandProperty TargetNodeAddress | ConvertTo-Json"
        )
        rc, out, err = self._run_powershell(ps, timeout=25)
        if rc != 0 or not (out or "").strip():
            return False
        try:
            obj = json.loads(out)
            addrs = obj if isinstance(obj, list) else ([obj] if obj else [])
            addrs = [str(a).lower() for a in addrs if a]
            return any(vol in a for a in addrs)
        except Exception:
            # Fallback: substring match on raw output
            return vol in (out or "").lower()

    def _windows_iscsi_any_disks_present(self) -> bool:
        """Return True if Windows currently shows any iSCSI disks."""
        if not sys.platform.startswith("win"):
            return False
        ps = "Get-Disk | Where-Object {$_.BusType -eq 'iSCSI'} | Select-Object -First 1 Number | ConvertTo-Json"
        rc, out, err = self._run_powershell(ps, timeout=25)
        return bool((out or "").strip()) and rc == 0
    def _set_mount_path_display(self, volume_name: str, protocol: str, local_path: str, note: str = ""):
        """Update the Mount page label and internal mounted_targets mapping safely.

        Rules:
        - CIFS: local_path is expected to be a drive letter like 'Z:'.
        - iSCSI: local_path is only valid once Windows initializes the disk and assigns a drive letter.
        - Never store placeholders like 'iSCSI' (or empty) as a mount target.
        """
        v = (volume_name or "").strip()
        p = (protocol or "").strip()
        lp = (local_path or "").strip()
        note = (note or "").strip()

        # Normalize Windows drive letters
        if sys.platform.startswith("win"):
            lp_norm = self._normalize_windows_drive(lp)
        else:
            lp_norm = lp

        # Decide whether this is a real, usable mount target
        is_real_drive = sys.platform.startswith("win") and self._is_real_windows_drive(lp_norm)

        # iSCSI can be "connected" but not yet initialized => no drive letter yet
        if p.startswith("iSCSI"):
            if is_real_drive:
                # Store only when we have an actual drive letter
                self.mounted_targets[v] = lp_norm
                self.mount_path_var.set(f"Mount path: {lp_norm}")
                if note:
                    self.mount_path_var.set(f"Mount path: {lp_norm} — {note}")
            else:
                # Do NOT store placeholders. Show a helpful UI hint instead.
                self.mounted_targets.pop(v, None)
                hint = note or "Connected. If first use, initialize/format the new RAW iSCSI disk in Disk Management."
                self.mount_path_var.set(f"Mount path: (pending) — {hint}")
            try:
                self._schedule_save_state()
            except Exception:
                pass
            return

        # Non-iSCSI (CIFS/NFS): store the returned local path if present
        if lp_norm:
            self.mounted_targets[v] = lp_norm
            self.mount_path_var.set(f"Mount path: {lp_norm}")
            if note:
                self.mount_path_var.set(f"Mount path: {lp_norm} — {note}")
        else:
            self.mounted_targets.pop(v, None)
            self.mount_path_var.set("Mount path: -")

        try:
            self._schedule_save_state()
        except Exception:
            pass
    def _on_mount(self):
        name = self._vol_value_to_name((self.mount_name.get() or "").strip())
        meta = self.volume_meta.get(name) or {}
        node = (meta.get("node") or "").strip()
        protocol = (meta.get("protocol") or "").strip()
      # Reset the UI mount-path indicator for this attempt
        try:
            self.mount_path_var.set("Mount path: -")
        except Exception:
            pass
        if not name:
            messagebox.showwarning("Missing fields", "Select a volume.")
            return
        if not node:
            messagebox.showwarning(
                "Missing fields",
                "Select a storage array in Configuration or Create first, then Reload Volumes.",
            )
            return
        if not protocol:
            protocol = self._default_protocol_for_platform()

        # Prompt for credentials on the main thread before spawning the background task.
        # Tkinter dialogs must be created on the main thread; calling from a worker thread
        # causes the dialog to not appear or behave incorrectly.
        user = ""
        pw = ""
        if protocol in ("CIFS", "iSCSI-Chap"):
            creds = self._prompt_credentials()
            if not isinstance(creds, (tuple, list)) or len(creds) != 2:
                return
            user, pw = creds
            if user is None:
                return  # user cancelled

        def task():
            self._prepare_array(node)
            host = self._resolve_node_host(node)

            disk_before = {}
            if (
                sys.platform.startswith("win")
                and str(protocol).startswith("iSCSI")
                and bool(self.auto_init_iscsi.get())
            ):
                disk_before = self._windows_iscsi_snapshot_disks()

            # Windows CIFS: clear any previous mapping for the default drive
            # (prevents auto-reconnect/cached mount before credentials prompt)
            if sys.platform.startswith("win") and protocol == "CIFS":
                try:
                    subprocess.run(
                        ["cmd", "/c", "net", "use", "Z:", "/delete", "/y"],
                        capture_output=True,
                        text=True,
                    )
                except Exception:
                    pass

            # --- Early check: already mounted locally? ---
            def is_accessible(mount_path: str) -> bool:
                if not mount_path:
                    return False
                try:
                    if sys.platform.startswith("win"):
                        mp = mount_path.strip()
                        mp = self._normalize_windows_drive(mp) or mp
                        if self._is_real_windows_drive(mp):
                            return os.path.exists(mp + "\\")
                        return False
                    return os.path.exists(mount_path)
                except Exception:
                    return False

            mount_target = (self.mounted_targets or {}).get(name)
            if mount_target and is_accessible(mount_target):
                def _done():
                    mt = mount_target
                    if sys.platform.startswith("win"):
                        mt = self._normalize_windows_drive(mt)
                  # Show the actual mount target (drive letter) and avoid placeholders
                    self._set_mount_path_display(name, protocol, mt, note="Already mounted")
                    self._append_log(f"Volume already mounted locally: {name} -> {mt}\n")
                    self._refresh_volumes()
                    self.volume_meta[name] = {"node": node, "protocol": protocol}
                    self._schedule_save_state()
                    self._update_inferred_for_selected_volume()
                self.after(0, _done)
                return

            # Ensure the local compute-node helper service is running BEFORE
            # signalling the storage node, so its callback on port 4002 succeeds.
            self._ensure_compute_service()

            # Ensure SDS has export/share ready (best effort)
            try:
                sdsClient.cmd_mount_volume(SimpleNamespace(name=name, Snode=host, protocol=protocol))
            except Exception:
                pass

            payload = {
                "volumeName": name,
                "protocol_name": protocol,
                "remote_ip": host,
                "host_name": host,
                "user_name": user or "",
                "ip": "",
                "password": pw or "",
                "wwn": "",
                "url": getattr(sdsClient, "URL", ""),
                "auto_init_disk": bool(self.auto_init_iscsi.get())
                if (sys.platform.startswith("win") and str(protocol).startswith("iSCSI"))
                else False,
            }

            resp = self._post_json(f"{COMPUTE_SERVICE_URL}/mountVolume", payload, timeout=40) or {}

            explicit_status = str(resp.get("status") or "").lower().strip()
            http_ok = (resp.get("http_status") == 200)

            if explicit_status in ("failure", "error", "failed"):
                raise RuntimeError(resp.get("message") or "Mount process failed")
            if (explicit_status and explicit_status != "success") and not http_ok:
                raise RuntimeError(resp.get("message") or "Mount process failed")

            # Windows iSCSI: attempt deterministic init/format if enabled
            iscsi_drive = ""
            if (
                sys.platform.startswith("win")
                and str(protocol).startswith("iSCSI")
                and bool(self.auto_init_iscsi.get())
            ):
                tmp_mp = (resp.get("mount_path") or "").strip()
                tmp_mp = self._normalize_windows_drive(tmp_mp)
                if not self._is_real_windows_drive(tmp_mp):
                    # Windows may take several seconds to enumerate the iSCSI disk after session is established.
                    # Retry the snapshot until a new disk appears (up to ~16 seconds total).
                    disk_after = {}
                    for _snap_try in range(5):
                        disk_after = self._windows_iscsi_snapshot_disks()
                        if any(n not in disk_before for n in disk_after):
                            break
                        print(f"[iSCSI] Waiting for new disk to appear in Windows (attempt {_snap_try + 1}/5)...")
                        time.sleep(3)
                    iscsi_drive = self._windows_iscsi_auto_init_new_raw_disk(disk_before, disk_after)
                if iscsi_drive:
                    print(f"Windows iSCSI disk auto-initialized successfully. Drive: {iscsi_drive}")

            mount_path = (resp.get("mount_path") or resp.get("mountPoint") or resp.get("mountpoint") or "").strip()

            # iSCSI is not a filesystem path until disk is initialized/partitioned.
            # Compute-side may return a status string like 'Session Logged in successfully' — clear it.
            if str(protocol).startswith("iSCSI"):
                if iscsi_drive:
                    mount_path = iscsi_drive
                elif not self._is_real_windows_drive(mount_path):
                    mount_path = ""

            # Normalize Windows drive letters
            if sys.platform.startswith("win") and mount_path:
                mount_path = self._normalize_windows_drive(mount_path) or mount_path
                if str(protocol).startswith("iSCSI"):
                    if self._is_real_windows_drive(mount_path):
                        if not os.path.exists(mount_path + "\\"):
                            mount_path = ""
                    else:
                        mount_path = ""

            # If compute service didn't provide a mount path, infer defaults
            if not mount_path:
                if sys.platform.startswith("win"):
                    if str(protocol).startswith("iSCSI"):
                        mount_path = ""  # no drive letter until init/format
                    else:
                        mount_path = str(
                            resp.get("drive")
                            or resp.get("drive_letter")
                            or resp.get("driveLetter")
                            or "Z:"
                        ).strip()
                        mount_path = self._normalize_windows_drive(mount_path) or mount_path
                else:
                    mount_path = str(resp.get("local_path") or resp.get("localPath") or ("/mnt/" + name)).strip()

            def _done():
                if str(protocol).startswith("iSCSI"):
                    if (
                        mount_path
                        and self._is_real_windows_drive(mount_path)
                        and os.path.exists(mount_path + "\\")
                    ):
                        self.mount_path_var.set(f"Mount path: {mount_path}")
                        self.mounted_targets[name] = mount_path
                    else:
                        self.mount_path_var.set("Mount path: (iSCSI connected — disk not initialized)")
                        # Keep volume in mounted_targets with empty path so unmount is available.
                        # Windows iSCSI disconnect uses volume name matching, not a path.
                        self.mounted_targets[name] = ""
                else:
                    self.mount_path_var.set(f"Mount path: {mount_path or '-'}")
                    if mount_path:
                        self.mounted_targets[name] = mount_path

                self.volume_meta[name] = {"node": node, "protocol": protocol}
                self._schedule_save_state()
                self._update_inferred_for_selected_volume()
                try:
                    self._refresh_volumes()
                except Exception:
                    pass

            self.after(0, _done)

        self._run_task(task, "Mounting volume...")

    def _on_unmount(self):
        selection = (self.unmount_name.get() or "").strip()
        vol = self._vol_value_to_name(selection)
        if not vol:
            messagebox.showwarning("Missing volume", "Select a volume to un-mount.")
            return

        meta = (self.volume_meta or {}).get(vol) or {}
        protocol = (meta.get("protocol") or "").strip()
        node = (meta.get("node") or "").strip()

        def task():
            # Prepare API base if we know the node (not strictly required for local unmount, but keeps logs consistent)
            try:
                if node:
                    self._prepare_array(node)
            except Exception:
                pass

            local_path = str((self.mounted_targets or {}).get(vol) or "").strip()
            print(f"local_path {local_path}")

            # --- Windows paths ---
            if sys.platform.startswith("win"):
                # CIFS: unmap the drive letter (treat already-unmapped as success)
                if protocol == "CIFS":
                    drive = self._normalize_windows_drive(local_path)
                    if drive:
                        cmd = f'cmd /c net use {drive} /delete /y'
                        rc, out, err = self._run_powershell(cmd, timeout=40)  # runs via powershell but executes cmd
                        # If net use says it wasn't found (2250), it's effectively already unmounted
                        if rc != 0 and ("2250" not in (out + err)):
                            raise RuntimeError(f"Windows drive unmount failed for {drive}: {(err or out).strip()}")
                        print(f"Windows drive unmounted: {drive}")
                    else:
                        print("Windows drive already unmapped (no drive letter recorded).")

                    # Tell the storage node to turn the volume OFF
                    try:
                        host = self._resolve_node_host(node) if node else ""
                        sdsClient.cmd_unmount_volume(SimpleNamespace(name=vol, Snode=host, protocol=protocol))
                    except Exception as e:
                        print(f"Storage node OFF request failed (local unmount succeeded): {e}")
                    self.mounted_targets.pop(vol, None)
                    self._schedule_save_state()
                    return

                # iSCSI: dismount volume (if any drive letter), then disconnect iSCSI target(s)
                if protocol.startswith("iSCSI"):
                    drive = self._normalize_windows_drive(local_path)

                    # 1) If we have a drive letter, dismount it first so Disconnect-IscsiTarget won't fail "device in use"
                    if drive:
                        letter = drive[0]
                        ps_dismount = (
                            f"try {{ Dismount-Volume -DriveLetter '{letter}' -Force -ErrorAction SilentlyContinue }} catch {{}}; "
                            f"try {{ mountvol {drive} /D }} catch {{}}"
                        )
                        self._run_powershell(ps_dismount, timeout=60)

                    # 2) Disconnect any matching targets (disconnecting is idempotent; treat errors as non-fatal)
                    vol_lc = vol.lower()
                    ps_disconnect = (
                        "$targets = @(); "
                        "try { $targets = Get-IscsiTarget | Select-Object -ExpandProperty NodeAddress } catch { $targets = @() }; "
                        "$matches = @($targets | Where-Object { $_ -and ($_.ToString().ToLower().Contains('" + vol_lc + "')) }); "
                        "foreach ($t in $matches) { try { Disconnect-IscsiTarget -NodeAddress $t -Confirm:$false -ErrorAction SilentlyContinue | Out-Null } catch {} }; "
                        "try { $sess = Get-IscsiSession | Where-Object { $_.TargetNodeAddress -and ($_.TargetNodeAddress.ToString().ToLower().Contains('" + vol_lc + "')) }; "
                        "foreach ($s in $sess) { try { Unregister-IscsiSession -SessionIdentifier $s.SessionIdentifier -Confirm:$false -ErrorAction SilentlyContinue | Out-Null } catch {} } } catch {}"
                    )
                    self._run_powershell(ps_disconnect, timeout=60)

                    # 3) Tell the storage node to turn the volume OFF
                    try:
                        host = self._resolve_node_host(node) if node else ""
                        sdsClient.cmd_unmount_volume(SimpleNamespace(name=vol, Snode=host, protocol=protocol))
                    except Exception as e:
                        print(f"Storage node OFF request failed (local unmount succeeded): {e}")

                    # 4) Clear GUI state. Do not leave placeholders.
                    self.mounted_targets.pop(vol, None)
                    self._schedule_save_state()
                    return

                # Unknown protocol on Windows
                raise RuntimeError(f"Unsupported protocol for unmount on Windows: {protocol or '(unknown)'}")

            # --- Non-Windows: let the storage node callback do the real unmount ---
            # Call cmd_unmount_volume first so the storage node fires its /unmountVolume
            # callback while the volume is still mounted. The direct compute-service call
            # below then acts as a fallback (unmount_process returns success if already unmounted).
            self._ensure_compute_service()
            host = self._resolve_node_host(node) if node else ""
            try:
                sdsClient.cmd_unmount_volume(SimpleNamespace(name=vol, Snode=host, protocol=protocol))
            except Exception as e:
                print(f"Storage node OFF request failed, will try direct unmount: {e}")

            # Fallback: call compute service directly in case the callback didn't fire
            try:
                payload = {
                    "volumeName": vol,
                    "protocol_name": protocol or self._default_protocol_for_platform(),
                    "remote_ip": host,
                    "host_name": host,
                    "user_name": "",
                    "password": "",
                    "ip": "",
                }
                resp = self._post_json(f"{COMPUTE_SERVICE_URL}/unmountVolume", payload, timeout=40) or {}
                explicit_status = str(resp.get("status") or "").lower().strip()
                if explicit_status in ("failure", "error", "failed"):
                    raise RuntimeError(resp.get("message") or "Unmount process failed")
            except Exception as e:
                raise RuntimeError(f"Unmount failed: {e}")

            self.mounted_targets.pop(vol, None)
            self._schedule_save_state()

        self._run_task(task, "Un-mounting volume...")

    def _on_delete(self):
        name = self._vol_value_to_name((self.delete_name.get() or "").strip())
        meta = self.volume_meta.get(name) or {}
        node = (meta.get("node") or "").strip()
        protocol = (meta.get("protocol") or "").strip()

        if not name or not node:
            messagebox.showwarning("Missing fields", "Select a volume and a storage array, then Reload Volumes.")
            return
        if not protocol:
            protocol = self._default_protocol_for_platform()

        warn = (
            f"You are about to PERMANENTLY delete the volume '{name}'.\n\n"
            "This will remove access to all data in that volume.\n"
            "This action cannot be undone.\n\n"
            "Are you sure you want to continue?"
        )
        if not messagebox.askyesno("⚠ Confirm Permanent Delete", warn):
            return

        def task():
            self._prepare_array(node)
            host = self._resolve_node_host(node)

            # 1. Delete volume from the storage node
            sdsClient.cmd_delete_volume(
                SimpleNamespace(
                    name=name,
                    Snode=host,
                    protocol=protocol or self._default_protocol_for_platform(),
                )
            )

            # 2. Remove the /mnt directory from the compute node (best-effort)
            try:
                self._ensure_compute_service()
                vol_meta = self.volume_meta.get(name) or {}
                payload_del = {
                    "volumeName": name,
                    "node_ip": host,
                    "iqn": vol_meta.get("iqn") or "",
                    "user_name": vol_meta.get("user_name") or "",
                    "password": vol_meta.get("password") or "",
                    "protocol_name": protocol or self._default_protocol_for_platform(),
                }
                self._post_json(f"{COMPUTE_SERVICE_URL}/deleteFolder", payload_del, timeout=40)
            except Exception as e:
                print(f"Compute node folder cleanup failed (volume deleted from storage): {e}")

            # 3. Clean GUI state
            def _done():
                try:
                    self.mounted_targets.pop(name, None)
                except Exception:
                    pass
                try:
                    self.volume_meta.pop(name, None)
                except Exception:
                    pass
                self.mount_path_var.set("Mount path: -")
                self._schedule_save_state()

            self.after(0, _done)

        self._run_task(task, "Deleting volume...")

    def _open_mount_folder(self):
        path = self.mount_path_var.get().replace("Mount path: ", "").strip()
        if not path or path == "-":
            messagebox.showinfo("No mount path", "Mount a volume first to get its path.")
            return
        if sys.platform.startswith("darwin"):
            subprocess.Popen(["open", path])
        elif sys.platform.startswith("win"):
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path])


if __name__ == "__main__":
    _maybe_relaunch_linux_as_root()
    app = SDSApp()
    app.mainloop()
