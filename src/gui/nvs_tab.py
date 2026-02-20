"""NVS Editor tab."""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..littlefs import human_bytes
from ..nvs import NvsRow, flash_nvs, read_nvs_csv, validate_nvs_rows, write_nvs_csv
from ..partitions import get_partition
from .theme import ERROR, FONT_MONO_SMALL, FONT_SMALL, FONT_SUBHEADING, MUTED, OK, WARN, danger_button_style, primary_button_style


class NvsTabUI:
    """Builds and manages the NVS Editor tab."""

    def __init__(self, app):
        self.app = app
        self.frame = ttk.Frame(app.tabs)
        app.tabs.add(self.frame, text="  NVS Editor  ")

        self._nvs_consistency_issues: list[str] = []
        self._last_consistency_snapshot: tuple | None = None
        self._build()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build(self):
        container = ttk.Frame(self.frame, padding=16)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(container, text="NVS Variables", font=FONT_SUBHEADING).pack(anchor=tk.W, pady=(0, 10))

        header_path_row = ttk.LabelFrame(container, text="NVS Header path", padding=10)
        header_path_row.pack(fill=tk.X, pady=(0, 10))
        header_path_row.columnconfigure(0, weight=1)
        self.unlock_meta_var = tk.BooleanVar(value=False)
        ttk.Entry(header_path_row, textvariable=self.app.config_tab.nvs_keys_h_var).grid(row=0, column=0, sticky=tk.EW)
        ttk.Button(header_path_row, text="Browse", command=self._browse_header_path).grid(row=0, column=1, padx=(8, 0))
        ttk.Checkbutton(
            header_path_row,
            text="Expert Mode",
            variable=self.unlock_meta_var,
            command=self._apply_meta_lock_state,
        ).grid(row=0, column=2, sticky=tk.E, padx=(12, 0))
        self.app.config_tab.nvs_keys_h_var.trace_add("write", lambda *_a: self._update_consistency_label())

        # Entry fields
        top = ttk.Frame(container)
        top.pack(fill=tk.X)

        for col, label in enumerate(("Namespace", "Key", "Type", "Encoding", "Value")):
            ttk.Label(top, text=label).grid(row=0, column=col, sticky=tk.W)

        self.ns_var = tk.StringVar(value="storage")
        self.key_var = tk.StringVar()
        self.type_var = tk.StringVar(value="data")
        self.enc_var = tk.StringVar(value="string")
        self.val_var = tk.StringVar()

        self.ns_entry = ttk.Entry(top, textvariable=self.ns_var, width=20)
        self.ns_entry.grid(row=1, column=0, sticky=tk.EW, padx=(0, 8))
        self.key_entry = ttk.Entry(top, textvariable=self.key_var, width=18)
        self.key_entry.grid(row=1, column=1, sticky=tk.EW, padx=(0, 8))
        self.type_combo = ttk.Combobox(
            top, textvariable=self.type_var,
            values=["data", "namespace", "file", "key"], width=10,
        )
        self.type_combo.grid(row=1, column=2, sticky=tk.EW, padx=(0, 8))
        self.enc_combo = ttk.Combobox(
            top, textvariable=self.enc_var,
            values=["string", "u8", "i8", "u16", "u32", "i32", "base64", "hex2bin", "binary"],
            width=12,
        )
        self.enc_combo.grid(row=1, column=3, sticky=tk.EW, padx=(0, 8))
        self.val_entry = ttk.Entry(top, textvariable=self.val_var, width=36)
        self.val_entry.grid(row=1, column=4, sticky=tk.EW)
        self.val_entry.bind("<Return>", lambda _e: self._add_or_update())

        top.columnconfigure(1, weight=1)
        top.columnconfigure(3, weight=1)
        top.columnconfigure(4, weight=1)
        self._apply_meta_lock_state()

        # Treeview
        tree_frame = ttk.Frame(container)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        self.tree = ttk.Treeview(
            tree_frame,
            columns=("namespace", "key", "type", "encoding", "value"),
            show="headings", height=9,
        )
        for c, w in [("namespace", 140), ("key", 180), ("type", 90), ("encoding", 110), ("value", 420)]:
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=w, anchor=tk.W)
        scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Action buttons
        row = ttk.Frame(container)
        row.pack(fill=tk.X, pady=(12, 0))
        ttk.Button(row, text="Add / Update", command=self._add_or_update).pack(side=tk.LEFT)
        ttk.Button(row, text="Remove Selected", command=self._remove_selected).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(row, text="Clear", command=self._clear_form).pack(side=tk.LEFT, padx=(8, 0))

        for text, cmd in [("Export CSV", self._export_csv), ("Import CSV", self._import_csv)]:
            tk.Button(
                row, text=text, command=cmd,
                **primary_button_style(),
            ).pack(side=tk.LEFT, padx=(8, 0))

        # Write to device
        row_write = ttk.Frame(container)
        row_write.pack(fill=tk.X, pady=(8, 0))
        ttk.Checkbutton(
            row_write,
            text="Erase NVS before write",
            variable=self.app.config_tab.erase_nvs_var,
        ).pack(side=tk.LEFT, padx=(0, 8))
        self.write_btn = tk.Button(
            row_write, text="Write to Device",
            command=self._start_write_thread,
            **danger_button_style(),
        )
        self.write_btn.pack(side=tk.LEFT, padx=(8, 0))
        self.consistency_label = ttk.Label(row_write, text="", font=FONT_SMALL)
        self.consistency_label.pack(side=tk.LEFT, padx=(20, 0))
        self._schedule_live_consistency_refresh()

    # ------------------------------------------------------------------
    # Lock state
    # ------------------------------------------------------------------

    def _apply_meta_lock_state(self):
        editable = self.unlock_meta_var.get()
        state = "normal" if editable else "disabled"
        combo_state = "readonly" if editable else "disabled"
        self.ns_entry.config(state=state)
        self.key_entry.config(state=state)
        self.type_combo.config(state=combo_state)
        self.enc_combo.config(state=combo_state)

    # ------------------------------------------------------------------
    # Tree manipulation
    # ------------------------------------------------------------------

    def _on_select(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        self.ns_var.set(vals[0])
        self.key_var.set(vals[1])
        self.type_var.set(vals[2])
        self.enc_var.set(vals[3])
        self.val_var.set(vals[4])

    def _add_or_update(self):
        row = (
            self.ns_var.get().strip(),
            self.key_var.get().strip(),
            self.type_var.get().strip() or "data",
            self.enc_var.get().strip() or "string",
            self.val_var.get(),
        )
        if not row[0] or not row[1]:
            messagebox.showwarning("Missing fields", "Namespace and key are required.")
            return
        sel = self.tree.selection()
        if sel:
            self.tree.item(sel[0], values=row)
        else:
            self.tree.insert("", tk.END, values=row)
        self._clear_form()
        self._update_consistency_label()

    def _remove_selected(self):
        for i in self.tree.selection():
            self.tree.delete(i)
        self._update_consistency_label()

    def _clear_form(self):
        self.ns_var.set("storage")
        self.type_var.set("data")
        self.enc_var.set("string")
        self.key_var.set("")
        self.val_var.set("")
        self.tree.selection_remove(self.tree.selection())

    def _tree_rows(self) -> list[NvsRow]:
        rows: list[NvsRow] = []
        for i in self.tree.get_children():
            ns, key, typ, enc, val = self.tree.item(i, "values")
            rows.append(NvsRow(namespace=ns, key=key, type=typ, encoding=enc, value=val))
        return rows

    # ------------------------------------------------------------------
    # CSV import / export
    # ------------------------------------------------------------------

    def _browse_header_path(self):
        p = filedialog.askopenfilename(filetypes=[("Header", "*.h"), ("All", "*")])
        if p:
            self.app.config_tab.nvs_keys_h_var.set(p)

    def _export_csv(self):
        p = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not p:
            return
        write_nvs_csv(p, self._tree_rows())
        self.app.log(f">>> Exported NVS CSV: {p}")

    def _import_csv(self):
        p = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if not p:
            return
        self.app.config.nvs_csv_path = p
        self._load_csv_to_tree(p)
        self.app.log(f">>> Imported NVS CSV: {p}")
        self._update_consistency_label()

    def _load_csv_to_tree(self, csv_path: str):
        self.tree.delete(*self.tree.get_children())
        for r in read_nvs_csv(csv_path):
            self.tree.insert("", tk.END, values=(r["namespace"], r["key"], r["type"], r["encoding"], r["value"]))

    def auto_import_csv(self):
        """Auto-import the NVS CSV from config (called during startup)."""
        csv_path = self.app.config.nvs_csv_path
        if csv_path and os.path.isfile(csv_path):
            self._load_csv_to_tree(csv_path)
            self.app.log(f">>> Auto-imported NVS CSV: {csv_path}")
            self._update_consistency_label()
        elif csv_path:
            self.app.log(f"[WARN] Auto-import failed: {csv_path} not found. Using empty table.")

    # ------------------------------------------------------------------
    # Consistency check
    # ------------------------------------------------------------------

    def _update_consistency_label(self):
        h_path = self.app.config_tab.nvs_keys_h_var.get().strip()
        issues = validate_nvs_rows(self._tree_rows(), header_path=h_path)
        if issues:
            n = len(issues)
            self.consistency_label.config(
                text=f"\u274c NVS validation issues ({n} issue{'s' if n != 1 else ''})",
                foreground=ERROR,
            )
            self._nvs_consistency_issues = issues
        else:
            if h_path and os.path.isfile(h_path):
                self.consistency_label.config(text="\u2705 NVS keys consistent with nvs_keys.h", foreground=OK)
            else:
                self.consistency_label.config(text="nvs_keys.h not configured \u2014 consistency check skipped", foreground=MUTED)
            self._nvs_consistency_issues = []

    def _consistency_snapshot(self) -> tuple:
        rows = tuple(self.tree.item(i, "values") for i in self.tree.get_children())
        return rows, self.app.config_tab.nvs_keys_h_var.get().strip()

    def _schedule_live_consistency_refresh(self):
        if not self.frame.winfo_exists():
            return
        snapshot = self._consistency_snapshot()
        if snapshot != self._last_consistency_snapshot:
            self._last_consistency_snapshot = snapshot
            self._update_consistency_label()
        self.frame.after(400, self._schedule_live_consistency_refresh)

    # ------------------------------------------------------------------
    # Validation dialog
    # ------------------------------------------------------------------

    def _show_validation_dialog(self, issues: list[str]) -> bool:
        """Show a structured validation dialog. Returns True if user chooses to proceed."""
        dlg = tk.Toplevel(self.app.root)
        dlg.title("NVS Validation Warning")
        dlg.geometry("560x370")
        dlg.resizable(True, True)
        dlg.transient(self.app.root)
        dlg.grab_set()

        result = [False]

        frame = ttk.Frame(dlg, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text=f"{len(issues)} validation issue{'s' if len(issues) != 1 else ''} found:",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W, pady=(0, 8))

        text = tk.Text(frame, wrap=tk.WORD, font=("Consolas", 9), state="normal")
        text.tag_configure("header_issue", foreground=WARN)
        text.tag_configure("value_issue", foreground=ERROR)
        scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scroll.set)

        for issue in issues:
            tag = "header_issue" if issue.lstrip().startswith(("namespace", "[")) else "value_issue"
            text.insert(tk.END, f"  {issue}\n", tag)

        text.configure(state="disabled")
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        btn_row = ttk.Frame(dlg, padding=(12, 0, 12, 12))
        btn_row.pack(fill=tk.X)

        def _copy():
            dlg.clipboard_clear()
            dlg.clipboard_append("\n".join(issues))

        def _proceed():
            result[0] = True
            dlg.destroy()

        ttk.Button(btn_row, text="Copy to Clipboard", command=_copy).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="Cancel", command=dlg.destroy).pack(side=tk.RIGHT)
        ttk.Button(btn_row, text="Proceed Anyway", command=_proceed).pack(side=tk.RIGHT, padx=(0, 8))

        dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)
        dlg.wait_window()
        return result[0]

    # ------------------------------------------------------------------
    # Write to device
    # ------------------------------------------------------------------

    def _start_write_thread(self):
        rows = self._tree_rows()
        if not rows:
            messagebox.showwarning("NVS table empty", "Cannot write to device: NVS table is empty.\n\nAdd at least one key-value pair.")
            return
        h_path = self.app.config.nvs_keys_h_path
        issues = validate_nvs_rows(rows, header_path=h_path)
        if issues:
            if not self._show_validation_dialog(issues):
                return

        cfg = self.app.config
        if cfg.erase_nvs:
            try:
                nvs = get_partition(cfg.csv_path, "nvs", logger=self.app.log)
                size_str = human_bytes(nvs["size"])
                detail = (
                    f"Partition: nvs\n"
                    f"Offset: {hex(nvs['offset'])}\n"
                    f"Size: {size_str}\n\n"
                    f"This will erase the entire NVS partition before writing.\n"
                    f"Continue?"
                )
            except Exception:
                detail = "Erase NVS partition before writing?\n\n(Could not read partition details.)"
            if not messagebox.askyesno("Confirm Erase", detail):
                return

        self.app.run_background_operation(
            title="NVS Write Progress",
            worker_fn=lambda: self._write_to_device(rows),
            success_message="NVS variables written successfully.",
            error_title="NVS write failed",
        )

    def _write_to_device(self, rows: list[NvsRow]):
        cfg = self.app.config
        nvs = get_partition(cfg.csv_path, "nvs", logger=self.app.log)
        flash_nvs(
            chip=cfg.chip,
            port=cfg.port,
            nvs_gen_py=cfg.nvs_gen_py,
            rows=rows,
            offset=nvs["offset"],
            partition_size=nvs["size"],
            erase_first=cfg.erase_nvs,
            baud=cfg.esptool_baud,
            verify=cfg.verify_after_write,
            logger=self.app.log,
            progress_cb=self.app.update_progress,
        )
