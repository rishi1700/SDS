#!/usr/bin/env python3
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading

if sys.platform.startswith("darwin"):
    os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import requests

import mount_services

APP_TITLE = "GS_VolumeManager"
DEFAULT_API_PORT = 4000
DEFAULT_STORAGE_HINT = "192.168.30.55"

PROTOCOLS = {
    "CIFS": 1,
    "NFS": 2,
    "iSCSI-Chap": 3,
    "iSCSI-NoChap": 4,
}

PROTOCOLS_BY_ID = {value: key for key, value in PROTOCOLS.items()}

VOLUME_NAME_PATTERNS = {
    "CIFS": re.compile(r"^[a-zA-Z0-9{!$ .@(~#)}&%_]*$"),
    "NFS": re.compile(r"^[a-z0-9]*$"),
    "iSCSI-Chap": re.compile(r"^[a-z0-9]*$"),
    "iSCSI-NoChap": re.compile(r"^[a-z0-9]*$"),
}

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


def _maybe_relaunch_with_privileges():
    if sys.platform.startswith("win"):
        try:
            import ctypes

            if ctypes.windll.shell32.IsUserAnAdmin():
                return

            if getattr(sys, "frozen", False):
                executable = sys.executable
                params = subprocess.list2cmdline(sys.argv[1:])
            else:
                executable = sys.executable
                params = subprocess.list2cmdline([str(Path(__file__).resolve()), *sys.argv[1:]])

            result = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                executable,
                params,
                str(Path.cwd()),
                1,
            )
            if result > 32:
                raise SystemExit(0)
        except SystemExit:
            raise
        except Exception:
            return
        return

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
        result = subprocess.run([pkexec, "env", *env_parts, *relaunch_cmd], check=False)
        raise SystemExit(result.returncode)
    except Exception:
        return


class GSVolumeManagerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1180x760")
        self.minsize(1100, 760)
        self.configure(bg=C_BG)

        self.log_queue = queue.Queue()
        self.storage_nodes = []
        self.volume_options = {}
        self.current_array_var = tk.StringVar(value="Storage: (none)")
        self.status_var = tk.StringVar(value="Ready")
        self._busy_count = 0

        self._apply_theme()
        self._build_layout()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.storage_entry.insert(0, DEFAULT_STORAGE_HINT)
        self._poll_logs()
        self._show_frame("config")
        self.after(100, self._finish_initial_render)

    def _apply_theme(self):
        style = ttk.Style(self)
        style.theme_use("aqua" if sys.platform.startswith("darwin") else "clam")
        style.configure(".", font=FONT_BODY)
        style.configure("TFrame", background=C_BG)
        style.configure("Card.TFrame", background=C_CARD)
        style.configure("TLabel", background=C_BG, foreground=C_TEXT)
        style.configure("Header.TLabel", font=FONT_TITLE, background=C_CARD, foreground=C_TEXT)
        style.configure("Muted.TLabel", font=FONT_BODY, background=C_CARD, foreground=C_MUTED)
        style.configure("Caption.TLabel", font=FONT_BODY, background=C_CARD, foreground=C_MUTED)
        style.configure("TLabelframe", background=C_CARD, foreground=C_TEXT, bordercolor=C_BORDER)
        style.configure("TLabelframe.Label", background=C_CARD, font=FONT_HEADER, foreground=C_TEXT)
        style.configure("TEntry", fieldbackground=C_CARD, background=C_CARD, foreground=C_TEXT, bordercolor=C_BORDER)
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
        )
        style.configure("TButton", font=FONT_BODY, padding=6)
        style.configure("Primary.TButton", background=C_PRIMARY, foreground="#fff", bordercolor=C_PRIMARY)
        style.map("Primary.TButton", background=[("active", C_PRIMARY_DARK), ("!active", C_PRIMARY)])
        style.configure("Ghost.TButton", background=C_CARD, foreground=C_TEXT, bordercolor=C_PRIMARY)
        style.map("Ghost.TButton", background=[("active", C_ACCENT), ("!active", C_CARD)])
        style.configure("Nav.TButton", background=C_NAV, foreground=C_TEXT, borderwidth=0, relief="flat")
        style.map("Nav.TButton", background=[("active", C_HIGHLIGHT), ("pressed", C_ACTIVE)])
        style.configure("NavActive.TButton", background=C_PRIMARY, foreground="#fff", borderwidth=0)

    def _build_layout(self):
        header = tk.Frame(self, bg=C_BG, height=70)
        header.pack(fill="x", side="top")
        header.grid_propagate(False)
        header_canvas = tk.Canvas(header, highlightthickness=0, bd=0, height=70, bg=C_BG)
        header_canvas.pack(fill="both", expand=True)
        self._header_canvas = header_canvas
        self._draw_header_gradient()
        self._header_title_label = tk.Label(
            header,
            text=f"{APP_TITLE} — {socket.gethostname()}",
            bg=C_BG,
            fg="#ffffff",
            font=FONT_TITLE,
        )
        self._header_title_label.configure(text=f"{APP_TITLE} - {socket.gethostname()}")
        self._header_title_label.place(x=20, rely=0.5, anchor="w")
        self._header_current_label = tk.Label(
            header,
            textvariable=self.current_array_var,
            bg=C_BG,
            fg=C_MUTED,
            font=FONT_HEADER,
        )
        self._header_current_label.place(relx=1.0, x=-20, rely=0.5, anchor="e")
        header.bind("<Configure>", lambda _e: self._draw_header_gradient())
        self.after(100, self._draw_header_gradient)

        body = tk.Frame(self, bg=C_BG)
        body.pack(fill="both", expand=True, padx=16, pady=16)

        nav = tk.Frame(body, bg=C_NAV)
        nav.pack(side="left", fill="y", padx=(0, 16))
        nav_header = tk.Frame(nav, bg=C_ACCENT, height=40)
        nav_header.pack(fill="x")
        nav_header.pack_propagate(False)
        tk.Label(nav_header, text="Actions", bg=C_ACCENT, fg=C_TEXT, font=FONT_HEADER).pack(anchor="w", padx=10, pady=8)
        tk.Frame(nav, bg=C_BORDER, height=1).pack(fill="x")

        self.content = tk.Frame(body, bg=C_BG)
        self.content.pack(side="left", fill="both", expand=True)
        self.content.grid_rowconfigure(0, weight=3)
        self.content.grid_rowconfigure(1, weight=1)
        self.content.grid_columnconfigure(0, weight=1)
        self.page_container = tk.Frame(self.content, bg=C_BG)
        self.page_container.grid(row=0, column=0, sticky="nsew")
        self.page_container.grid_rowconfigure(0, weight=1)
        self.page_container.grid_columnconfigure(0, weight=1)

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
            label = {
                "config": "Configuration",
                "create": "Create Volume",
                "mount": "Mount Volume",
                "unmount": "Un-mount Volume",
                "delete": "Delete Volume",
            }.get(key, label)
            btn = ttk.Button(nav, text=label, style="Nav.TButton", command=lambda k=key: self._show_frame(k))
            btn.pack(fill="x", pady=6, padx=2)
            self.nav_buttons[key] = btn

        self._build_config_frame()
        self._build_create_frame()
        self._build_mount_frame()
        self._build_unmount_frame()
        self._build_delete_frame()
        self._build_log_frame()

        statusbar = tk.Frame(self, bg=C_CARD, height=24)
        statusbar.pack(fill="x", side="bottom")
        tk.Label(statusbar, textvariable=self.status_var, anchor="w", bg=C_CARD, fg=C_MUTED, font=FONT_BODY).pack(side="left", padx=12, pady=2)

    def _draw_header_gradient(self):
        canvas = self._header_canvas
        canvas.delete("gradient")
        width = canvas.winfo_width() or 1
        height = canvas.winfo_height() or 1
        start = (8, 14, 28)
        end = (20, 52, 92)
        steps = max(height, 1)
        for i in range(steps):
            ratio = i / steps
            r = int(start[0] + ((end[0] - start[0]) * ratio))
            g = int(start[1] + ((end[1] - start[1]) * ratio))
            b = int(start[2] + ((end[2] - start[2]) * ratio))
            color = f"#{r:02x}{g:02x}{b:02x}"
            canvas.create_rectangle(0, i, width, i + 1, outline=color, fill=color, tags="gradient")
        canvas.lower("gradient")
        if getattr(self, "_header_title_label", None):
            self._header_title_label.lift()
        if getattr(self, "_header_current_label", None):
            self._header_current_label.lift()

    def _build_config_frame(self):
        frame = ttk.Frame(self.page_container, style="Card.TFrame")
        frame.grid(row=0, column=0, sticky="nsew")
        self.frames["config"] = frame

        form = ttk.LabelFrame(frame, text="Storage Node")
        form.pack(fill="x", padx=0, pady=(0, 8))

        self.storage_entry = ttk.Entry(form)
        self.storage_entry.grid(row=0, column=0, padx=8, pady=8, sticky="ew")
        ttk.Button(form, text="Add", style="Primary.TButton", command=self._add_storage).grid(row=0, column=1, padx=8, pady=8)
        ttk.Button(form, text="Delete Selected", style="Ghost.TButton", command=self._delete_storage).grid(row=0, column=2, padx=8, pady=8)
        form.columnconfigure(0, weight=1)

        list_frame = ttk.LabelFrame(frame, text="Configured Storage Nodes")
        list_frame.pack(fill="both", expand=True, padx=0, pady=8)

        self.storage_list = tk.Listbox(
            list_frame,
            bg=C_NAV,
            fg=C_TEXT,
            selectbackground=C_PRIMARY,
            selectforeground="#ffffff",
            font=FONT_BODY,
            borderwidth=0,
            highlightthickness=0,
        )
        self.storage_list.pack(fill="both", expand=True, padx=8, pady=8)
        self.storage_list.bind("<<ListboxSelect>>", lambda _e: self._sync_selected_node())

    def _build_create_frame(self):
        frame = ttk.Frame(self.page_container, style="Card.TFrame")
        frame.grid(row=0, column=0, sticky="nsew")
        self.frames["create"] = frame

        form = ttk.LabelFrame(frame, text="Create Volume")
        form.pack(fill="x", padx=0, pady=8)

        self.create_name = ttk.Entry(form)
        self.create_size = ttk.Entry(form)
        self.create_node = ttk.Combobox(form, values=[], state="readonly")
        self.create_protocol = ttk.Combobox(form, values=self._platform_protocols(), state="readonly")
        self.create_protocol.set(self._default_protocol_for_platform())
        self.create_user = ttk.Entry(form)
        self.create_pw = ttk.Entry(form, show="*")

        self._grid_row(form, 0, "Volume Name", self.create_name)
        self._grid_row(form, 1, "Size (GB)", self.create_size)
        self._grid_row(form, 2, "Storage Node", self.create_node)
        self._grid_row(form, 3, "Protocol", self.create_protocol)
        self._grid_row(form, 4, "User", self.create_user)
        self._grid_row(form, 5, "Password", self.create_pw)
        ttk.Button(form, text="Create Volume", style="Primary.TButton", command=self._on_create).grid(row=6, column=0, columnspan=2, pady=(6, 4))
        rules_frame = ttk.Frame(form, style="Card.TFrame")
        rules_frame.grid(row=7, column=0, columnspan=2, padx=8, pady=(0, 4), sticky="ew")
        rules_frame.columnconfigure(0, weight=1)
        helper_lines = [
            "Rules: volume name 1-12 chars, not 'system', no hyphen.",
            "NFS/iSCSI: lowercase letters and numbers only. CIFS: user/password required and all three values must differ.",
        ]
        for index, line in enumerate(helper_lines):
            ttk.Label(
                rules_frame,
                text=line,
                style="Muted.TLabel",
                justify="left",
            ).grid(row=index, column=0, sticky="w", pady=(0, 1))

    def _build_mount_frame(self):
        frame = ttk.Frame(self.page_container, style="Card.TFrame")
        frame.grid(row=0, column=0, sticky="nsew")
        self.frames["mount"] = frame

        form = ttk.LabelFrame(frame, text="Mount Volume (Locally on this Computer)")
        form.pack(fill="x", padx=0, pady=8)

        self.mount_name = ttk.Combobox(form, values=[], state="readonly")
        self.mount_node = ttk.Combobox(form, values=[], state="readonly")
        self._grid_row(form, 0, "Volume Name", self.mount_name)
        self._grid_row(form, 1, "Storage Node", self.mount_node)
        ttk.Button(form, text="Reload Volumes", style="Ghost.TButton", command=self._refresh_volumes).grid(row=2, column=0, pady=8)
        ttk.Button(form, text="Mount Volume", style="Primary.TButton", command=self._on_mount).grid(row=2, column=1, pady=8)

    def _build_unmount_frame(self):
        frame = ttk.Frame(self.page_container, style="Card.TFrame")
        frame.grid(row=0, column=0, sticky="nsew")
        self.frames["unmount"] = frame

        form = ttk.LabelFrame(frame, text="Un-mount Volume (Locally)")
        form.pack(fill="x", padx=0, pady=8)

        self.unmount_name = ttk.Combobox(form, values=[], state="readonly")
        self.unmount_node = ttk.Combobox(form, values=[], state="readonly")
        self._grid_row(form, 0, "Volume Name", self.unmount_name)
        self._grid_row(form, 1, "Storage Node", self.unmount_node)
        ttk.Button(form, text="Reload Volumes", style="Ghost.TButton", command=self._refresh_volumes).grid(row=2, column=0, pady=8)
        ttk.Button(form, text="Un-mount Volume", style="Primary.TButton", command=self._on_unmount).grid(row=2, column=1, pady=8)

    def _build_delete_frame(self):
        frame = ttk.Frame(self.page_container, style="Card.TFrame")
        frame.grid(row=0, column=0, sticky="nsew")
        self.frames["delete"] = frame

        form = ttk.LabelFrame(frame, text="Delete Volume")
        form.pack(fill="x", padx=0, pady=8)

        self.delete_name = ttk.Combobox(form, values=[], state="readonly")
        self.delete_node = ttk.Combobox(form, values=[], state="readonly")
        self._grid_row(form, 0, "Volume Name", self.delete_name)
        self._grid_row(form, 1, "Storage Node", self.delete_node)
        ttk.Button(form, text="Reload Volumes", style="Ghost.TButton", command=self._refresh_volumes).grid(row=2, column=0, pady=8)
        ttk.Button(form, text="Delete Volume", style="Primary.TButton", command=self._on_delete).grid(row=2, column=1, pady=8)

    def _build_log_frame(self):
        frame = ttk.LabelFrame(self.content, text="Output")
        frame.grid(row=1, column=0, sticky="nsew", pady=(16, 0))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(
            frame,
            height=10,
            bg=C_NAV,
            fg=C_TEXT,
            insertbackground=C_TEXT,
            relief="flat",
            wrap="word",
            font=FONT_MONO,
        )
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns", pady=8)
        ttk.Button(frame, text="Clear Log", style="Ghost.TButton", command=lambda: self.log_text.delete("1.0", tk.END)).grid(row=1, column=0, sticky="e", padx=8, pady=(0, 8))

    def _grid_row(self, parent, row, label, widget):
        ttk.Label(parent, text=label).grid(row=row, column=0, padx=8, pady=8, sticky="w")
        widget.grid(row=row, column=1, padx=8, pady=8, sticky="ew")
        parent.columnconfigure(1, weight=1)

    def _show_frame(self, key):
        for name, frame in self.frames.items():
            frame.tkraise() if name == key else None
            self.nav_buttons[name].configure(style="NavActive.TButton" if name == key else "Nav.TButton")

    def _finish_initial_render(self):
        self.update_idletasks()
        self._draw_header_gradient()
        self.deiconify()
        self.lift()

    def _platform_protocols(self):
        if sys.platform.startswith("win"):
            return ["CIFS", "iSCSI-Chap", "iSCSI-NoChap"]
        return ["NFS", "CIFS", "iSCSI-Chap", "iSCSI-NoChap"]

    def _default_protocol_for_platform(self):
        return "CIFS" if sys.platform.startswith("win") else "NFS"

    def _append_log(self, message):
        if not message:
            return
        self.log_text.insert(tk.END, message.rstrip() + "\n")
        self.log_text.see(tk.END)

    def _poll_logs(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                self._append_log(item)
        except queue.Empty:
            pass
        self.after(150, self._poll_logs)

    def _log(self, message):
        self.log_queue.put(message)

    def _show_info(self, title, message):
        self.lift()
        self.focus_force()
        messagebox.showinfo(title, message, parent=self)

    def _show_error(self, title, message):
        self.lift()
        self.focus_force()
        messagebox.showerror(title, message, parent=self)

    def _set_busy(self, busy, message=""):
        self._busy_count = max(0, self._busy_count + (1 if busy else -1))
        if self._busy_count > 0:
            self.status_var.set(message or "Working...")
        else:
            self.status_var.set("Ready")

    def _run_task(self, task, success_message):
        self._set_busy(True, success_message)

        def worker():
            try:
                result_message = task()
                if result_message:
                    self.after(0, lambda msg=result_message: self._show_info("Success", msg))
            except Exception as exc:
                self.after(0, lambda err=str(exc): self._show_error("Error", err))
                self._log(f"Error: {type(exc).__name__}: {exc}")
            finally:
                self.after(0, lambda: self._set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def _storage_values(self):
        return list(self.storage_nodes)

    def _refresh_node_dropdowns(self):
        values = self._storage_values()
        for cb in (self.create_node, self.mount_node, self.unmount_node, self.delete_node):
            cb.configure(values=values)
            if not cb.get() and values:
                cb.set(values[0])

    def _add_storage(self):
        node = self.storage_entry.get().strip()
        if not node:
            messagebox.showwarning("Missing node", "Enter a storage node IP or host name.")
            return
        if node not in self.storage_nodes:
            self.storage_nodes.append(node)
            self.storage_list.insert(tk.END, node)
            self._refresh_node_dropdowns()
        self.current_array_var.set(f"Storage: {node}")

    def _delete_storage(self):
        selection = self.storage_list.curselection()
        if not selection:
            return
        index = selection[0]
        node = self.storage_list.get(index)
        self.storage_list.delete(index)
        if node in self.storage_nodes:
            self.storage_nodes.remove(node)
        self._refresh_node_dropdowns()
        self.current_array_var.set(f"Storage: {self.storage_nodes[0]}" if self.storage_nodes else "Storage: (none)")

    def _sync_selected_node(self):
        selection = self.storage_list.curselection()
        if not selection:
            return
        node = self.storage_list.get(selection[0])
        self.current_array_var.set(f"Storage: {node}")
        for cb in (self.create_node, self.mount_node, self.unmount_node, self.delete_node):
            if node in cb.cget("values"):
                cb.set(node)

    def _selected_node(self, explicit_value=""):
        node = explicit_value.strip() if explicit_value else ""
        if node:
            return node
        selection = self.storage_list.curselection()
        if selection:
            return self.storage_list.get(selection[0]).strip()
        return self.storage_entry.get().strip()

    def _api_base(self, node):
        return f"http://{node}:{DEFAULT_API_PORT}"

    def _require_node(self, explicit_value=""):
        node = self._selected_node(explicit_value)
        if not node:
            raise RuntimeError("Select or add a storage node first.")
        return node

    def _check_reachable(self, node):
        url = self._api_base(node)
        self._log(f"Checking reachability of Storage Node at {url} ...")
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"Storage Node {node} is not reachable at {url}.") from exc

    def _request_json(self, method, node, path, **kwargs):
        self._check_reachable(node)
        response = requests.request(method, self._api_base(node) + path, timeout=60, **kwargs)
        response.raise_for_status()
        return response.json()

    def _storage_cgi_base(self, node):
        return f"http://{node}/cgi"

    def _read_storage_volumes(self, node):
        response = requests.get(
            self._storage_cgi_base(node) + "/cgi_VolumeManager.py",
            params={"requestType": "read_Volume", "volumeId": 0},
            timeout=30,
        )
        response.raise_for_status()
        volumes = response.json()
        if not isinstance(volumes, list):
            raise RuntimeError("Failed to fetch volumes from storage node.")

        normalized = []
        for item in volumes:
            protocol_id = int(item.get("protocolId", 0) or 0)
            normalized.append({
                "id": item.get("id"),
                "name": item.get("name"),
                "protocolId": protocol_id,
                "protocolName": PROTOCOLS_BY_ID.get(protocol_id, f"Unknown({protocol_id})"),
                "state": item.get("state"),
                "hostId": item.get("hostId"),
                "hostName": item.get("hostName"),
                "lun": item.get("lun"),
                "type": item.get("type"),
            })
        return normalized

    def _refresh_volumes(self):
        node = self._require_node(self.mount_node.get() or self.unmount_node.get() or self.delete_node.get())

        def task():
            self._check_reachable(node)
            volumes = self._read_storage_volumes(node)
            self.volume_options = {}
            display_values = []
            for item in volumes:
                protocol = item.get("protocolName") or PROTOCOLS_BY_ID.get(item.get("protocolId"), "Unknown")
                display = f"{item.get('name')} ({protocol})"
                self.volume_options[display] = item
                display_values.append(display)

            def update_ui():
                for cb in (self.mount_name, self.unmount_name, self.delete_name):
                    cb.configure(values=display_values)
                    if display_values:
                        cb.set(display_values[0])
                    else:
                        cb.set("")
                self._log("Loading volumes successful.")

            self.after(0, update_ui)

        self._run_task(task, "Loading volumes...")

    def _on_create(self):
        name = self.create_name.get().strip()
        size = self.create_size.get().strip()
        node = self._require_node(self.create_node.get())
        protocol = self.create_protocol.get().strip()
        user = self.create_user.get().strip()
        password = self.create_pw.get().strip()

        if not name or not size or not protocol:
            messagebox.showwarning("Missing fields", "Volume name, size, storage node, and protocol are required.")
            return
        if protocol in ("CIFS", "iSCSI-Chap") and (not user or not password):
            messagebox.showwarning("Missing credentials", "User and password are required for CIFS and iSCSI-Chap.")
            return
        if len(name) < 1 or len(name) > 12:
            messagebox.showwarning("Invalid volume name", "Volume name must be between 1 and 12 characters.")
            return
        if name.lower() == "system":
            messagebox.showwarning("Invalid volume name", "Volume name cannot be 'system'.")
            return
        if "-" in name:
            messagebox.showwarning("Invalid volume name", 'Volume name cannot contain "-".')
            return
        pattern = VOLUME_NAME_PATTERNS.get(protocol)
        if pattern and not pattern.match(name):
            if protocol == "CIFS":
                msg = "CIFS volume name may contain letters, numbers, spaces, underscore, and supported special characters."
            elif protocol == "NFS":
                msg = "NFS volume name may contain lowercase letters and numbers only."
            else:
                msg = "iSCSI volume name may contain lowercase letters and numbers only."
            messagebox.showwarning("Invalid volume name", msg)
            return
        if protocol == "CIFS":
            lowered = {name.lower(), user.lower(), password.lower()}
            if len(lowered) < 3:
                messagebox.showwarning(
                    "Invalid CIFS values",
                    "For CIFS, volume name, username, and password must be different values.",
                )
                return

        def task():
            self._log(f"Selected Protocol :  {protocol}")
            self._log(f"Creating volume '{name}' size {size} ...")
            payload = {
                "volumeName": name,
                "size": size,
                "protocolId": PROTOCOLS[protocol],
                "priority": 1,
                "user": user,
                "password": password,
                "remote_ip": node,
            }
            response = self._request_json("POST", node, "/sn_volume", json=payload)
            if not response.get("status"):
                raise RuntimeError(response.get("message") or "Volume creation failed.")
            pool_name = (((response.get("poolInfo") or {}).get("pool")) or {}).get("systemName", "N/A")
            self._log("Volume Created Successfully On ....")
            self._log(f"Storage Node: {node}")
            self._log(f"Pool Name: {pool_name}")
            self.after(0, self._refresh_volumes)
            return f"Volume '{name}' created successfully."

        self._run_task(task, "Creating volume...")

    def _selected_volume(self, combobox):
        display = combobox.get().strip()
        if not display or display not in self.volume_options:
            raise RuntimeError("Select a volume first, then reload volumes if needed.")
        return self.volume_options[display]

    def _on_mount(self):
        node = self._require_node(self.mount_node.get())
        volume = self._selected_volume(self.mount_name)

        def task():
            payload = {
                "volumeName": volume["name"],
                "protocol_name": volume["protocolName"],
                "protocolId": volume["protocolId"],
                "state": 6,
                "remote_ip": node,
            }
            self._log(f"Volume Name :  {volume['name']}")
            self._log(f"Selected Protocol :  {volume['protocolName']}")
            response = self._request_json("PUT", node, "/onOff_SN_Volume", json=payload)
            if not response.get("status"):
                raise RuntimeError(response.get("message") or "Volume Action Error Code: -1")

            host = response.get("host") or {}
            self._log(
                "CIFS backend host info : "
                f"user_name={host.get('user_name', '')!r}, "
                f"pw_present={'yes' if bool(host.get('pw')) else 'no'}, "
                f"iqn={host.get('iqn', '')!r}"
            )
            mount_response = mount_services.mountVolume(
                volume["name"],
                volume["protocolName"],
                node,
                host.get("user_name", ""),
                host.get("iqn", ""),
                host.get("pw", ""),
            )
            if mount_response.get("status") != "success":
                raise RuntimeError(mount_response.get("error_message") or mount_response.get("message") or "Mount process failed.")

            self._log("Volume Mounted Successfully On ....")
            self._log(f"Volume Name :  {volume['name']}")
            self._log(f"Volume Mounted Path :  {mount_response.get('mount_path')}")
            return f"Volume '{volume['name']}' mounted successfully.\nPath: {mount_response.get('mount_path')}"

        self._run_task(task, "Mounting volume...")

    def _on_unmount(self):
        node = self._require_node(self.unmount_node.get())
        volume = self._selected_volume(self.unmount_name)

        def task():
            payload = {
                "volumeName": volume["name"],
                "protocol_name": volume["protocolName"],
                "protocolId": volume["protocolId"],
                "state": 4,
                "remote_ip": node,
            }
            response = self._request_json("PUT", node, "/onOff_SN_Volume", json=payload)
            if not response.get("status"):
                raise RuntimeError(response.get("message") or "Volume Action Error Code: -1")

            unmount_response = mount_services.unmountVolume(volume["name"], node, volume["protocolName"])
            if unmount_response.get("status") != "success":
                raise RuntimeError(unmount_response.get("error_message") or unmount_response.get("message") or "Unmount process failed.")

            self._log("Volume Unmounted Successfully On ....")
            self._log(f"Volume Name :  {volume['name']}")
            self._log(f"Volume Unmounted Path :  {unmount_response.get('unmount_path')}")
            return f"Volume '{volume['name']}' unmounted successfully."

        self._run_task(task, "Unmounting volume...")

    def _on_delete(self):
        node = self._require_node(self.delete_node.get())
        volume = self._selected_volume(self.delete_name)

        confirm_message = (
            f"Delete volume '{volume['name']}'?\n\n"
            "This will delete the volume from the storage node.\n"
            "The app will also try to remove the local mount folder or drive mapping if one exists.\n\n"
            "Make sure the volume is unmounted before deleting.\n"
            "Do you want to continue?"
        )
        if not messagebox.askyesno("Delete volume", confirm_message, parent=self):
            return

        def task():
            payload = {
                "volumeName": volume["name"],
                "protocolId": volume["protocolId"],
                "remote_ip": node,
            }
            response = self._request_json("DELETE", node, "/sn_volume", json=payload)
            if not response.get("status"):
                raise RuntimeError(response.get("message") or "Volume not deleted.")

            delete_response = mount_services.deleteFolder(volume["name"], volume["protocolName"])
            self._log("Volume Deleted Successfully On ....")
            self._log(f"Volume Name :  {volume['name']}")
            self._log(f"Message :  {response.get('message')}")
            self._log(f"Folder Deleted Message :  {delete_response.get('message')}")
            self.after(0, self._refresh_volumes)
            return f"Volume '{volume['name']}' deleted successfully."

        self._run_task(task, "Deleting volume...")

    def _on_close(self):
        self.destroy()


if __name__ == "__main__":
    _maybe_relaunch_with_privileges()
    app = GSVolumeManagerApp()
    app.mainloop()
