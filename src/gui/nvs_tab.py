"""NVS Editor tab."""

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..nvs import NvsRow, flash_nvs, read_nvs_csv, validate_nvs_rows, write_nvs_csv
from ..partitions import get_partition


class NvsTabUI:
    """Builds and manages the NVS Editor tab."""

    def __init__(self, app):
        self.app = app
        self.frame = ttk.Frame(app.tabs)
        app.tabs.add(self.frame, text="  NVS Editor  ")

        self._nvs_consistency_issues: list[str] = []
        self._build()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build(self):
        container = ttk.Frame(self.frame, padding=16)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(container, text="NVS Variables", font=("Segoe UI", 15, "bold")).pack(anchor=tk.W, pady=(0, 10))

        # Entry fields
        top = ttk.Frame(container)
        top.pack(fill=tk.X)

        self.unlock_meta_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            top, text="Unlock namespace/key/type/encoding (at your own risk)",
            variable=self.unlock_meta_var, command=self._apply_meta_lock_state,
        ).grid(row=0, column=0, columnspan=6, sticky=tk.W, pady=(0, 8))

        for col, label in enumerate(("Namespace", "Key", "Type", "Encoding", "Value")):
            ttk.Label(top, text=label).grid(row=1, column=col, sticky=tk.W)

        self.ns_var = tk.StringVar(value="storage")
        self.key_var = tk.StringVar()
        self.type_var = tk.StringVar(value="data")
        self.enc_var = tk.StringVar(value="string")
        self.val_var = tk.StringVar()

        self.ns_entry = ttk.Entry(top, textvariable=self.ns_var, width=20)
        self.ns_entry.grid(row=2, column=0, sticky=tk.EW, padx=(0, 8))
        self.key_entry = ttk.Entry(top, textvariable=self.key_var, width=18)
        self.key_entry.grid(row=2, column=1, sticky=tk.EW, padx=(0, 8))
        self.type_combo = ttk.Combobox(
            top, textvariable=self.type_var,
            values=["data", "namespace", "file", "key"], width=10,
        )
        self.type_combo.grid(row=2, column=2, sticky=tk.EW, padx=(0, 8))
        self.enc_combo = ttk.Combobox(
            top, textvariable=self.enc_var,
            values=["string", "u8", "i8", "u16", "u32", "i32", "base64", "hex2bin", "binary"],
            width=12,
        )
        self.enc_combo.grid(row=2, column=3, sticky=tk.EW, padx=(0, 8))
        self.val_entry = ttk.Entry(top, textvariable=self.val_var)
        self.val_entry.grid(row=2, column=4, sticky=tk.EW)
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
            show="headings", height=13,
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
                bg="#2e79d1", fg="#ffffff",
                activebackground="#2667b3", activeforeground="#ffffff",
                relief=tk.FLAT, bd=0, padx=10, pady=4, cursor="hand2",
            ).pack(side=tk.LEFT, padx=(8, 0))

        # Write to device
        row_write = ttk.Frame(container)
        row_write.pack(fill=tk.X, pady=(8, 0))
        self.write_btn = tk.Button(
            row_write, text="Write to Device",
            command=self._start_write_thread,
            bg="#d64b4b", fg="#ffffff",
            activebackground="#be3f3f", activeforeground="#ffffff",
            relief=tk.FLAT, bd=0, padx=12, pady=4, cursor="hand2",
        )
        self.write_btn.pack(side=tk.LEFT, padx=(8, 0))
        self.consistency_label = ttk.Label(row_write, text="", font=("Segoe UI", 9))
        self.consistency_label.pack(side=tk.LEFT, padx=(20, 0))

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
        h_path = self.app.config.nvs_keys_h_path
        issues = validate_nvs_rows(self._tree_rows(), header_path=h_path)
        if issues:
            n = len(issues)
            self.consistency_label.config(
                text=f"\u274c NVS validation issues ({n} issue{'s' if n != 1 else ''})",
                foreground="#e05555",
            )
            self._nvs_consistency_issues = issues
        else:
            if h_path and os.path.isfile(h_path):
                self.consistency_label.config(text="\u2705 NVS keys consistent with nvs_keys.h", foreground="#4ec969")
            else:
                self.consistency_label.config(text="nvs_keys.h not configured \u2014 consistency check skipped", foreground="#888888")
            self._nvs_consistency_issues = []

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
            msg = "NVS validation issues:\n\n" + "\n".join(issues) + "\n\nProceed anyway?"
            if not messagebox.askyesno("NVS Validation Warning", msg):
                return
        self.app.show_progress("NVS Write Progress")
        self.app.set_buttons_busy(True)
        threading.Thread(target=self._write_to_device, args=(rows,), daemon=True).start()

    def _write_to_device(self, rows: list[NvsRow]):
        try:
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
                logger=self.app.log,
                progress_cb=self.app.update_progress,
            )
            self.app.log("[SUCCESS] NVS partition flashed successfully.")
            self.app.root.after(0, messagebox.showinfo, "Success", "NVS variables written successfully.")
        except Exception as e:
            self.app.log(f"[ERROR] {e}")
            self.app.root.after(0, messagebox.showerror, "NVS write failed", str(e))
        finally:
            self.app.root.after(0, self.app.close_progress)
            self.app.root.after(0, self.app.set_buttons_busy, False)
