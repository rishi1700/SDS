#!/usr/bin/env python3
"""
GS Volume Manager GUI
Tkinter frontend wrapping gsVolClient.py and mount_services.py
"""

import sys
import threading
import json
import time
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
from types import SimpleNamespace
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr

try:
    import requests
except ImportError:
    import subprocess
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "requests", "--break-system-packages"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        import requests
    except Exception:
        pass

import gsVolClient


# ---------------------------------------------------------------------------
# PowerShell helper (Windows only)
# ---------------------------------------------------------------------------

def _run_powershell(cmd, timeout=90):
    import subprocess
    for exe in ["powershell", "pwsh"]:
        try:
            p = subprocess.run(
                [exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                capture_output=True, text=True, timeout=timeout,
            )
            return p.returncode, p.stdout, p.stderr
        except FileNotFoundError:
            continue
        except subprocess.TimeoutExpired as e:
            return 1, "", f"TimeoutExpired: {e}"
    return 1, "", "PowerShell not found"


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

PROTOCOLS = ["NFS", "CIFS", "iSCSI-Chap", "iSCSI-NoChap"]
DEFAULT_SNODE = "192.168.30.55"


class GsVolApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GS Volume Manager")
        self.resizable(True, True)

        self._busy = False

        self._build_header()
        self._build_notebook()
        self._build_log()

        # Patch stdout/stderr to also write to the log widget
        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr

    # ------------------------------------------------------------------
    # Header row
    # ------------------------------------------------------------------

    def _build_header(self):
        hdr = ttk.Frame(self)
        hdr.pack(fill="x", padx=8, pady=(8, 2))

        ttk.Label(hdr, text="Storage Node IP:").pack(side="left")
        self._snode_var = tk.StringVar(value=DEFAULT_SNODE)
        ttk.Entry(hdr, textvariable=self._snode_var, width=18).pack(side="left", padx=(4, 6))
        ttk.Button(hdr, text="Connect", command=self._on_connect).pack(side="left")
        self._status_var = tk.StringVar(value="Not connected")
        ttk.Label(hdr, textvariable=self._status_var, foreground="gray").pack(
            side="left", padx=(10, 0)
        )

    # ------------------------------------------------------------------
    # Notebook (three tabs)
    # ------------------------------------------------------------------

    def _build_notebook(self):
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=8, pady=4)

        self._build_create_tab()
        self._build_mount_tab()
        self._build_delete_tab()

    # --- Create Volume tab -------------------------------------------

    def _build_create_tab(self):
        tab = ttk.Frame(self._nb, padding=10)
        self._nb.add(tab, text="Create Volume")

        ttk.Label(tab, text="Volume Name:").grid(row=0, column=0, sticky="w", pady=3)
        self._create_name = tk.StringVar()
        ttk.Entry(tab, textvariable=self._create_name, width=30).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )

        ttk.Label(tab, text="Size (GB):").grid(row=1, column=0, sticky="w", pady=3)
        self._create_size = tk.StringVar(value="10")
        ttk.Entry(tab, textvariable=self._create_size, width=10).grid(
            row=1, column=1, sticky="w", padx=(6, 0)
        )

        ttk.Label(tab, text="Protocol:").grid(row=2, column=0, sticky="w", pady=3)
        self._create_proto = tk.StringVar(value="NFS")
        proto_cb = ttk.Combobox(
            tab, textvariable=self._create_proto, values=PROTOCOLS, state="readonly", width=16
        )
        proto_cb.grid(row=2, column=1, sticky="w", padx=(6, 0))
        proto_cb.bind("<<ComboboxSelected>>", self._on_create_proto_change)

        # Credentials frame (shown only for CIFS / iSCSI-Chap)
        self._create_cred_frame = ttk.LabelFrame(tab, text="Credentials", padding=6)
        self._create_cred_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        ttk.Label(self._create_cred_frame, text="Username:").grid(
            row=0, column=0, sticky="w", pady=2
        )
        self._create_user = tk.StringVar()
        ttk.Entry(self._create_cred_frame, textvariable=self._create_user, width=22).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )

        ttk.Label(self._create_cred_frame, text="Password:").grid(
            row=1, column=0, sticky="w", pady=2
        )
        self._create_pw = tk.StringVar()
        ttk.Entry(self._create_cred_frame, textvariable=self._create_pw, show="*", width=22).grid(
            row=1, column=1, sticky="ew", padx=(6, 0)
        )

        ttk.Button(tab, text="Create Volume", command=self._on_create).grid(
            row=4, column=0, columnspan=2, pady=(12, 0)
        )

        tab.columnconfigure(1, weight=1)
        self._create_cred_frame.columnconfigure(1, weight=1)

        # Initial visibility
        self._on_create_proto_change()

    def _on_create_proto_change(self, _event=None):
        proto = self._create_proto.get()
        if proto in ("CIFS", "iSCSI-Chap"):
            self._create_cred_frame.grid()
        else:
            self._create_cred_frame.grid_remove()

    # --- Mount / Unmount tab -----------------------------------------

    def _build_mount_tab(self):
        tab = ttk.Frame(self._nb, padding=10)
        self._nb.add(tab, text="Mount / Unmount")

        # Volume selector
        vol_row = ttk.Frame(tab)
        vol_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=3)
        ttk.Label(vol_row, text="Volume:").pack(side="left")
        self._mount_vol = tk.StringVar()
        self._mount_vol_cb = ttk.Combobox(vol_row, textvariable=self._mount_vol, width=26)
        self._mount_vol_cb.pack(side="left", padx=(6, 4))
        ttk.Button(vol_row, text="\u21ba Reload", command=lambda: self._reload_volumes("mount")).pack(
            side="left"
        )

        ttk.Label(tab, text="Protocol:").grid(row=1, column=0, sticky="w", pady=3)
        self._mount_proto = tk.StringVar(value="NFS")
        ttk.Combobox(
            tab, textvariable=self._mount_proto, values=PROTOCOLS, state="readonly", width=16
        ).grid(row=1, column=1, sticky="w", padx=(6, 0))

        # Windows-only auto-init checkbox
        self._auto_init_var = tk.BooleanVar(value=True)
        self._auto_init_chk = ttk.Checkbutton(
            tab,
            text="Auto initialize & format iSCSI disk",
            variable=self._auto_init_var,
        )
        if sys.platform.startswith("win"):
            self._auto_init_chk.grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # Mount / Unmount buttons
        btn_row = ttk.Frame(tab)
        btn_row.grid(row=3, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn_row, text="Mount", command=self._on_mount).pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="Unmount", command=self._on_unmount).pack(side="left")

        # Mount path result label
        self._mount_path_var = tk.StringVar(value="")
        ttk.Label(tab, textvariable=self._mount_path_var, foreground="blue").grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(6, 0)
        )

        tab.columnconfigure(1, weight=1)

    # --- Delete Volume tab -------------------------------------------

    def _build_delete_tab(self):
        tab = ttk.Frame(self._nb, padding=10)
        self._nb.add(tab, text="Delete Volume")

        vol_row = ttk.Frame(tab)
        vol_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=3)
        ttk.Label(vol_row, text="Volume:").pack(side="left")
        self._delete_vol = tk.StringVar()
        self._delete_vol_cb = ttk.Combobox(vol_row, textvariable=self._delete_vol, width=26)
        self._delete_vol_cb.pack(side="left", padx=(6, 4))
        ttk.Button(vol_row, text="\u21ba Reload", command=lambda: self._reload_volumes("delete")).pack(
            side="left"
        )

        ttk.Label(tab, text="Protocol:").grid(row=1, column=0, sticky="w", pady=3)
        self._delete_proto = tk.StringVar(value="NFS")
        ttk.Combobox(
            tab, textvariable=self._delete_proto, values=PROTOCOLS, state="readonly", width=16
        ).grid(row=1, column=1, sticky="w", padx=(6, 0))

        ttk.Button(tab, text="Delete Volume", command=self._on_delete).grid(
            row=2, column=0, columnspan=2, pady=(12, 0)
        )

        tab.columnconfigure(1, weight=1)

    # ------------------------------------------------------------------
    # Log area
    # ------------------------------------------------------------------

    def _build_log(self):
        frame = ttk.LabelFrame(self, text="Log", padding=4)
        frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._log = ScrolledText(
            frame, height=12, font=("Courier", 9), state="disabled", wrap="word"
        )
        self._log.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # Logging helpers
    # ------------------------------------------------------------------

    def _log_write(self, text):
        """Append text to the log widget (thread-safe)."""
        self.after(0, self._log_insert, text)

    def _log_insert(self, text):
        self._log.configure(state="normal")
        self._log.insert("end", text)
        self._log.see("end")
        self._log.configure(state="disabled")

    def _log_line(self, text):
        self._log_write(text + "\n")

    # ------------------------------------------------------------------
    # stdout/stderr redirect context manager
    # ------------------------------------------------------------------

    class _LogStream:
        def __init__(self, app):
            self._app = app

        def write(self, text):
            if text:
                self._app._log_write(text)

        def flush(self):
            pass

    # ------------------------------------------------------------------
    # Busy flag helpers
    # ------------------------------------------------------------------

    def _set_status(self, msg):
        self.after(0, self._status_var.set, msg)

    def _set_busy(self, busy, status=""):
        self._busy = busy
        if status:
            self._set_status(status)

    # ------------------------------------------------------------------
    # Connect
    # ------------------------------------------------------------------

    def _on_connect(self):
        if self._busy:
            return
        snode = self._snode_var.get().strip()
        if not snode:
            messagebox.showwarning("Input error", "Please enter a Storage Node IP.")
            return
        self._set_busy(True, "Connecting...")
        threading.Thread(target=self._connect_worker, args=(snode,), daemon=True).start()

    def _connect_worker(self, snode):
        stream = self._LogStream(self)
        with redirect_stdout(stream), redirect_stderr(stream):
            url = f"http://{snode}:4000"
            gsVolClient.URL = url
            self._log_line(f"--- Connecting to {url} ---")
            reachable = gsVolClient.is_strorge_node_reachable(url)
            if reachable:
                self._log_line("Storage node is reachable.")
                self.after(0, self._status_var.set, "Connected")
                self._reload_volumes("both")
            else:
                self._log_line(f"WARNING: Storage node at {url} did not respond.")
                self.after(0, self._status_var.set, "Unreachable (URL set)")
        self._set_busy(False)

    # ------------------------------------------------------------------
    # Volume reload
    # ------------------------------------------------------------------

    def _reload_volumes(self, target="both"):
        threading.Thread(target=self._reload_worker, args=(target,), daemon=True).start()

    def _reload_worker(self, target):
        try:
            url = gsVolClient.URL
        except AttributeError:
            self._log_line("Not connected. Please connect first.")
            return

        stream = self._LogStream(self)
        with redirect_stdout(stream), redirect_stderr(stream):
            self._log_line("--- Reloading volumes ---")
            try:
                resp = requests.get(f"{url}/sn_volumes", timeout=10)
                data = resp.json()
            except Exception as e:
                self._log_line(f"Could not fetch volumes: {e}")
                return

            names = []
            if isinstance(data, list):
                names = self._parse_volume_list(data)
            elif isinstance(data, dict):
                for key in ("volumes", "data"):
                    val = data.get(key)
                    if val and isinstance(val, list):
                        names = self._parse_volume_list(val)
                        break

            if names:
                self._log_line(f"Volumes: {', '.join(names)}")
                self.after(0, self._update_volume_combos, names, target)
            else:
                self._log_line("No volumes found or unexpected response format.")

    def _parse_volume_list(self, lst):
        names = []
        for item in lst:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                for key in ("name", "volumeName", "volume_name"):
                    if key in item:
                        names.append(str(item[key]))
                        break
            elif isinstance(item, (list, tuple)) and len(item) > 1:
                names.append(str(item[1]))
        return names

    def _update_volume_combos(self, names, target):
        if target in ("mount", "both"):
            self._mount_vol_cb["values"] = names
            if names and not self._mount_vol.get():
                self._mount_vol.set(names[0])
        if target in ("delete", "both"):
            self._delete_vol_cb["values"] = names
            if names and not self._delete_vol.get():
                self._delete_vol.set(names[0])

    # ------------------------------------------------------------------
    # Create Volume
    # ------------------------------------------------------------------

    def _on_create(self):
        if self._busy:
            return
        name = self._create_name.get().strip()
        size = self._create_size.get().strip()
        proto = self._create_proto.get()
        user = self._create_user.get().strip()
        pw = self._create_pw.get().strip()
        snode = self._snode_var.get().strip()

        if not name:
            messagebox.showwarning("Input error", "Please enter a volume name.")
            return
        if not size:
            messagebox.showwarning("Input error", "Please enter a size.")
            return
        if proto in ("CIFS", "iSCSI-Chap") and (not user or not pw):
            messagebox.showwarning("Input error", "Username and password are required for this protocol.")
            return

        self._set_busy(True, "Creating...")
        args = SimpleNamespace(name=name, size=size, protocol=proto, Snode=snode, user=user, pw=pw)
        threading.Thread(target=self._create_worker, args=(args,), daemon=True).start()

    def _create_worker(self, args):
        stream = self._LogStream(self)
        with redirect_stdout(stream), redirect_stderr(stream):
            self._log_line("--- Create Volume ---")
            try:
                gsVolClient.cmd_create_volume(args)
            except Exception as e:
                self._log_line(f"Error: {e}")
        self._set_busy(False, "Ready")

    # ------------------------------------------------------------------
    # Mount Volume
    # ------------------------------------------------------------------

    def _on_mount(self):
        if self._busy:
            return
        name = self._mount_vol.get().strip()
        proto = self._mount_proto.get()
        snode = self._snode_var.get().strip()

        if not name:
            messagebox.showwarning("Input error", "Please select or enter a volume name.")
            return

        self._set_busy(True, "Mounting...")
        self.after(0, self._mount_path_var.set, "")
        args = SimpleNamespace(name=name, protocol=proto, Snode=snode)

        # Snapshot disks before mount (Windows iSCSI)
        disk_before = set()
        if sys.platform.startswith("win") and proto.startswith("iSCSI") and self._auto_init_var.get():
            disk_before = self._get_win_disk_snapshot()

        threading.Thread(
            target=self._mount_worker, args=(args, disk_before), daemon=True
        ).start()

    def _get_win_disk_snapshot(self):
        rc, out, err = _run_powershell(
            "Get-Disk | Select-Object Number,PartitionStyle | ConvertTo-Json"
        )
        if rc != 0 or not out.strip():
            return set()
        try:
            data = json.loads(out)
            if isinstance(data, dict):
                data = [data]
            return {str(d.get("Number")) for d in data}
        except Exception:
            return set()

    def _mount_worker(self, args, disk_before):
        stream = self._LogStream(self)
        mount_path = ""
        with redirect_stdout(stream), redirect_stderr(stream):
            self._log_line("--- Mount Volume ---")
            try:
                gsVolClient.cmd_mount_volume(args)
                # Try to parse mount path from log — cmd_mount_volume prints it
                mount_path = self._last_mount_path_from_log()
            except Exception as e:
                self._log_line(f"Error: {e}")

            # Windows iSCSI auto-init
            if (
                sys.platform.startswith("win")
                and args.protocol.startswith("iSCSI")
                and self._auto_init_var.get()
            ):
                drive = self._win_iscsi_auto_init(disk_before)
                if drive:
                    mount_path = drive

        if mount_path:
            self.after(0, self._mount_path_var.set, f"Mount path: {mount_path}")
        self._set_busy(False, "Ready")

    def _last_mount_path_from_log(self):
        """Read last lines of log widget to find mount path printed by cmd_mount_volume."""
        try:
            content = self._log.get("1.0", "end")
            for line in reversed(content.splitlines()):
                if "Volume Mounted Path" in line or "mount_path" in line.lower():
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        return parts[1].strip()
        except Exception:
            pass
        return ""

    def _win_iscsi_auto_init(self, disk_before):
        self._log_line("[iSCSI auto-init] Waiting for new disk...")
        new_raw = None
        for attempt in range(5):
            time.sleep(3)
            rc, out, err = _run_powershell(
                "Update-HostStorageCache; Get-Disk | Select-Object Number,PartitionStyle | ConvertTo-Json"
            )
            if rc != 0:
                self._log_line(f"[iSCSI auto-init] Get-Disk failed: {err}")
                continue
            try:
                data = json.loads(out) if out.strip() else []
                if isinstance(data, dict):
                    data = [data]
                after = {str(d.get("Number")): d.get("PartitionStyle", "") for d in data}
            except Exception as e:
                self._log_line(f"[iSCSI auto-init] JSON parse error: {e}")
                continue

            new_nums = set(after.keys()) - disk_before
            if not new_nums:
                self._log_line(f"[iSCSI auto-init] No new disk yet (attempt {attempt + 1}/5)")
                continue

            raw_candidates = [n for n in new_nums if after.get(n) == "RAW"]
            self._log_line(f"[iSCSI auto-init] New disks: {new_nums}, RAW: {raw_candidates}")
            if len(raw_candidates) == 1:
                new_raw = raw_candidates[0]
                break
            elif len(raw_candidates) > 1:
                self._log_line("[iSCSI auto-init] Multiple RAW disks found, skipping auto-init.")
                return ""

        if new_raw is None:
            self._log_line("[iSCSI auto-init] No RAW disk found after 5 attempts.")
            return ""

        self._log_line(f"[iSCSI auto-init] Initializing disk {new_raw}...")
        ps_cmd = (
            f"$n={new_raw}; "
            "Initialize-Disk -Number $n -PartitionStyle GPT -ErrorAction Stop; "
            "$p = New-Partition -DiskNumber $n -UseMaximumSize -ErrorAction Stop; "
            "Format-Volume -Partition $p -FileSystem NTFS -Confirm:$false -ErrorAction Stop | Out-Null; "
            "$p | Add-PartitionAccessPath -AssignDriveLetter -ErrorAction Stop; "
            "$dl = (Get-Partition -DiskNumber $n | Where-Object {$_.DriveLetter} | "
            "Select-Object -First 1 -ExpandProperty DriveLetter); "
            "if ($dl) { [string]$dl + ':' } else { '' }"
        )
        rc, out, err = _run_powershell(ps_cmd)
        if rc != 0:
            self._log_line(f"[iSCSI auto-init] Init error: {err}")
            return ""
        drive = out.strip()
        if drive:
            self._log_line(f"[iSCSI auto-init] Drive letter assigned: {drive}")
            return drive
        else:
            self._log_line("[iSCSI auto-init] No drive letter returned.")
            return ""

    # ------------------------------------------------------------------
    # Unmount Volume
    # ------------------------------------------------------------------

    def _on_unmount(self):
        if self._busy:
            return
        name = self._mount_vol.get().strip()
        proto = self._mount_proto.get()
        snode = self._snode_var.get().strip()

        if not name:
            messagebox.showwarning("Input error", "Please select or enter a volume name.")
            return

        self._set_busy(True, "Unmounting...")
        args = SimpleNamespace(name=name, protocol=proto, Snode=snode)
        threading.Thread(target=self._unmount_worker, args=(args,), daemon=True).start()

    def _unmount_worker(self, args):
        stream = self._LogStream(self)
        with redirect_stdout(stream), redirect_stderr(stream):
            self._log_line("--- Unmount Volume ---")
            try:
                gsVolClient.cmd_unmount_volume(args)
            except Exception as e:
                self._log_line(f"Error: {e}")
        self.after(0, self._mount_path_var.set, "")
        self._set_busy(False, "Ready")

    # ------------------------------------------------------------------
    # Delete Volume
    # ------------------------------------------------------------------

    def _on_delete(self):
        if self._busy:
            return
        name = self._delete_vol.get().strip()
        proto = self._delete_proto.get()
        snode = self._snode_var.get().strip()

        if not name:
            messagebox.showwarning("Input error", "Please select or enter a volume name.")
            return

        if not messagebox.askyesno(
            "Confirm Delete", f"Delete volume '{name}' ({proto})?\nThis cannot be undone."
        ):
            return

        self._set_busy(True, "Deleting...")
        args = SimpleNamespace(name=name, protocol=proto, Snode=snode)
        threading.Thread(target=self._delete_worker, args=(args,), daemon=True).start()

    def _delete_worker(self, args):
        stream = self._LogStream(self)
        with redirect_stdout(stream), redirect_stderr(stream):
            self._log_line("--- Delete Volume ---")
            try:
                gsVolClient.cmd_delete_volume(args)
            except Exception as e:
                self._log_line(f"Error: {e}")
        self._set_busy(False, "Ready")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = GsVolApp()
    app.mainloop()
