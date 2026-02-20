"""Littlefs Upload tab."""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..littlefs import flash_littlefs, human_bytes
from ..partitions import get_partition
from .theme import FONT_BODY, FONT_HEADING, FONT_MONO_SMALL, MUTED, danger_button_style


class FlashTabUI:
    """Builds and manages the Littlefs Upload tab."""

    def __init__(self, app):
        self.app = app
        self.frame = ttk.Frame(app.tabs)
        app.tabs.add(self.frame, text="  Littlefs Upload  ")
        self._build()

    def _build(self):
        container = ttk.Frame(self.frame, padding=20)
        container.pack(fill=tk.BOTH, expand=True)

        self._line_vars: list[dict[str, tk.StringVar]] = []
        self.status_labels: dict[str, ttk.Label] = {}

        ttk.Label(
            container, text="LittleFS Operations",
            font=FONT_HEADING,
        ).pack(anchor=tk.W, pady=(0, 20))
        ttk.Label(
            container,
            text="Use Configuration tab for COM and partition/tool options. This tab manages LittleFS paths and flashing.",
            font=FONT_BODY,
        ).pack(anchor=tk.W, pady=(0, 12))

        littlefs_paths = ttk.LabelFrame(container, text="LittleFS Paths", padding=10)
        littlefs_paths.pack(fill=tk.X, pady=(0, 10))
        littlefs_paths.columnconfigure(0, weight=1)

        controls = ttk.Frame(littlefs_paths)
        controls.grid(row=0, column=0, sticky=tk.EW, pady=(0, 8))
        ttk.Button(controls, text="Add line", command=self._add_line).pack(side=tk.LEFT)
        ttk.Button(controls, text="Remove line", command=self._remove_line).pack(side=tk.LEFT, padx=(8, 0))

        header = ttk.Frame(littlefs_paths)
        header.grid(row=1, column=0, sticky=tk.EW, pady=(0, 4))
        header.columnconfigure(0, weight=3)
        header.columnconfigure(1, weight=0, minsize=90)
        header.columnconfigure(2, weight=0, minsize=220)
        header.columnconfigure(3, weight=0, minsize=90)
        ttk.Label(header, text="Folder path").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(header, text="").grid(row=0, column=1, sticky=tk.W)
        ttk.Label(header, text="Target folder").grid(row=0, column=2, sticky=tk.W)
        ttk.Label(header, text="Mode").grid(row=0, column=3, sticky=tk.W)

        self.lines_container = ttk.Frame(littlefs_paths)
        self.lines_container.grid(row=2, column=0, sticky=tk.EW)
        self.lines_container.columnconfigure(0, weight=1)

        self._load_lines_from_config()
        self._render_lines()
        ttk.Button(container, text="Save Configuration", command=self.app.save_config).pack(anchor=tk.W, pady=(0, 8))

        status_files = ttk.LabelFrame(container, text="Environement status", padding=10)
        status_files.pack(fill=tk.X, pady=(0, 10))
        self.status_labels["raw"] = ttk.Label(status_files, text="", font=FONT_BODY)
        self.status_labels["raw"].pack(anchor=tk.W, pady=2)
        self.status_labels["raw_files"] = ttk.Label(status_files, text="", font=FONT_MONO_SMALL, foreground=MUTED)
        self.status_labels["raw_files"].pack(anchor=tk.W, pady=(0, 4), padx=(16, 0))
        self.status_labels["gzip"] = ttk.Label(status_files, text="", font=FONT_BODY)
        self.status_labels["gzip"].pack(anchor=tk.W, pady=2)
        self.status_labels["gzip_files"] = ttk.Label(status_files, text="", font=FONT_MONO_SMALL, foreground=MUTED)
        self.status_labels["gzip_files"].pack(anchor=tk.W, pady=(0, 4), padx=(16, 0))
        self._sync_entries_to_config()
        self.refresh_file_status()

        btns = ttk.Frame(container)
        btns.pack(fill=tk.X, pady=(8, 0))
        ttk.Checkbutton(
            btns,
            text="Erase FS partition before flash",
            variable=self.app.config_tab.erase_fs_var,
        ).pack(side=tk.LEFT, padx=(0, 12))
        self.run_btn = tk.Button(
            btns,
            text="Build & Flash LittleFS",
            command=self._start_flash_thread,
            **danger_button_style(),
        )
        self.run_btn.pack(side=tk.LEFT)

    def _default_line(self) -> dict[str, tk.StringVar]:
        source_var = tk.StringVar(value="")
        target_var = tk.StringVar(value="")
        mode_var = tk.StringVar(value="raw")
        line = {"source": source_var, "target": target_var, "mode": mode_var}
        for var in (source_var, target_var, mode_var):
            var.trace_add("write", self._on_line_changed)
        return line

    def _load_lines_from_config(self):
        cfg = self.app.config
        entries = list(cfg.littlefs_entries or [])
        if not entries:
            entries = [{"source_dir": "", "target_dir": "", "mode": "raw"}]
        self._line_vars = []
        for item in entries:
            line = self._default_line()
            line["source"].set((item.get("source_dir") or "").strip())
            line["target"].set((item.get("target_dir") or "").strip())
            mode = (item.get("mode") or "raw").strip().lower()
            line["mode"].set(mode if mode in {"raw", "gzip"} else "raw")
            self._line_vars.append(line)

    def _render_lines(self):
        for child in self.lines_container.winfo_children():
            child.destroy()
        for idx, line in enumerate(self._line_vars):
            row = ttk.Frame(self.lines_container)
            row.grid(row=idx, column=0, sticky=tk.EW, pady=(0, 6))
            row.columnconfigure(0, weight=3)
            row.columnconfigure(1, weight=0, minsize=90)
            row.columnconfigure(2, weight=0, minsize=220)

            src_entry = ttk.Entry(row, textvariable=line["source"])
            src_entry.grid(row=0, column=0, sticky=tk.EW, padx=(0, 8))
            ttk.Button(row, text="Browse", command=lambda i=idx: self._browse_line_source(i)).grid(
                row=0, column=1, sticky=tk.W
            )
            ttk.Entry(row, textvariable=line["target"], width=18).grid(row=0, column=2, sticky=tk.EW, padx=(0, 8))
            ttk.Combobox(row, textvariable=line["mode"], values=["raw", "gzip"], width=8, state="readonly").grid(
                row=0, column=3, sticky=tk.W
            )

    def _browse_line_source(self, index: int):
        if index < 0 or index >= len(self._line_vars):
            return
        p = filedialog.askdirectory()
        if p:
            self._line_vars[index]["source"].set(p)

    def _add_line(self):
        self._line_vars.append(self._default_line())
        self._render_lines()
        self._on_line_changed()

    def _remove_line(self):
        if len(self._line_vars) <= 1:
            return
        self._line_vars.pop()
        self._render_lines()
        self._on_line_changed()

    def _collect_entries(self) -> list[dict[str, str]]:
        entries: list[dict[str, str]] = []
        for line in self._line_vars:
            source_dir = line["source"].get().strip()
            if not source_dir:
                continue
            mode = line["mode"].get().strip().lower()
            if mode not in {"raw", "gzip"}:
                mode = "raw"
            entries.append(
                {
                    "source_dir": source_dir,
                    "target_dir": line["target"].get().strip(),
                    "mode": mode,
                }
            )
        return entries

    def _on_line_changed(self, *_args):
        self._sync_entries_to_config()
        self.app.root.after_idle(self.app.config_tab.refresh_status)

    def _sync_entries_to_config(self):
        entries = self._collect_entries()
        cfg = self.app.config
        cfg.littlefs_entries = entries

    def refresh_file_status(self):
        raw_entries = [e for e in self._collect_entries() if e["mode"] == "raw"]
        gzip_entries = [e for e in self._collect_entries() if e["mode"] == "gzip"]

        def _summarize(entries: list[dict[str, str]]) -> tuple[str, str]:
            if not entries:
                return "Not configured", ""
            total_files = 0
            all_names: list[str] = []
            for item in entries:
                source_dir = item["source_dir"]
                if not os.path.isdir(source_dir):
                    return f"Path not found: {source_dir}", ""
                names = sorted(
                    f for f in os.listdir(source_dir)
                    if os.path.isfile(os.path.join(source_dir, f))
                )
                total_files += len(names)
                all_names.extend(names)
            if total_files == 0:
                return "0 files", ""
            label = "file" if total_files == 1 else "files"
            return f"{total_files} {label} across {len(entries)} line(s)", ", ".join(all_names)

        raw_summary, raw_names = _summarize(raw_entries)
        gzip_summary, gzip_names = _summarize(gzip_entries)

        self.status_labels["raw"].config(text=f"Raw: {raw_summary}")
        self.status_labels["raw_files"].config(text=raw_names)
        self.status_labels["gzip"].config(text=f"Gzip: {gzip_summary}")
        self.status_labels["gzip_files"].config(text=gzip_names)

    # ------------------------------------------------------------------

    def _start_flash_thread(self):
        self._sync_entries_to_config()
        if not self.app.config_tab.refresh_status():
            self.app.log("[ERROR] Environment checks are not ready.")
            return
        self.app.save_config()

        cfg = self.app.config
        if cfg.erase_fs:
            try:
                fs = get_partition(cfg.csv_path, "spiffs", logger=self.app.log)
                size_str = human_bytes(fs["size"])
                detail = (
                    f"Partition: spiffs\n"
                    f"Offset: {hex(fs['offset'])}\n"
                    f"Size: {size_str}\n\n"
                    f"This will erase the entire FS partition before flashing.\n"
                    f"Continue?"
                )
            except Exception:
                detail = "Erase FS partition before flashing?\n\n(Could not read partition details.)"
            if not messagebox.askyesno("Confirm Erase", detail):
                return

        self.app.run_background_operation(
            title="LittleFS Flash Progress",
            worker_fn=self._run_flash,
            success_message="Filesystem flashed successfully.",
        )

    def _run_flash(self):
        cfg = self.app.config
        fs = get_partition(cfg.csv_path, "spiffs", logger=self.app.log)
        flash_littlefs(
            chip=cfg.chip,
            port=cfg.port,
            mklittlefs_path=cfg.mklittlefs_path,
            offset=fs["offset"],
            partition_size=fs["size"],
            erase_first=cfg.erase_fs,
            block_size=cfg.littlefs_block_size,
            page_size=cfg.littlefs_page_size,
            baud=cfg.esptool_baud,
            entries=cfg.littlefs_entries,
            verify=cfg.verify_after_write,
            logger=self.app.log,
            progress_cb=self.app.update_progress,
        )
