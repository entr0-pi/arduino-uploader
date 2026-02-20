"""Littlefs Upload tab."""

import tkinter as tk
from tkinter import messagebox, ttk

from ..littlefs import flash_littlefs, human_bytes
from ..partitions import get_partition
from .theme import FONT_BODY, FONT_HEADING, danger_button_style


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

        self.raw_target_dir_var = tk.StringVar(value=self.app.config.littlefs_raw_target_dir)
        self.gzip_target_dir_var = tk.StringVar(value=self.app.config.littlefs_gzip_target_dir)
        self.raw_target_dir_var.trace_add("write", self._sync_target_dirs)
        self.gzip_target_dir_var.trace_add("write", self._sync_target_dirs)

        ttk.Label(
            container, text="LittleFS Operations",
            font=FONT_HEADING,
        ).pack(anchor=tk.W, pady=(0, 20))
        ttk.Label(
            container,
            text="Use Configuration tab for COM, paths, and options. This tab only runs the flash operation.",
            font=FONT_BODY,
        ).pack(anchor=tk.W, pady=(0, 12))

        targets = ttk.LabelFrame(container, text="LittleFS Target Folders", padding=10)
        targets.pack(fill=tk.X, pady=(0, 10))
        targets.columnconfigure(0, weight=1)
        targets.columnconfigure(1, weight=1)

        ttk.Label(targets, text="RAW DATA target folder (empty = /)").grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        ttk.Label(targets, text="GZIP DATA target folder (empty = /)").grid(row=0, column=1, sticky=tk.W)

        ttk.Entry(targets, textvariable=self.raw_target_dir_var).grid(row=1, column=0, sticky=tk.EW, padx=(0, 8), pady=(4, 0))
        ttk.Entry(targets, textvariable=self.gzip_target_dir_var).grid(row=1, column=1, sticky=tk.EW, pady=(4, 0))

        ttk.Checkbutton(
            container,
            text="Erase FS partition before flash",
            variable=self.app.config_tab.erase_fs_var,
        ).pack(anchor=tk.W, pady=(0, 8))

        btns = ttk.Frame(container)
        btns.pack(fill=tk.X, pady=(8, 0))
        self.run_btn = tk.Button(
            btns,
            text="Build & Flash LittleFS",
            command=self._start_flash_thread,
            **danger_button_style(),
        )
        self.run_btn.pack(side=tk.LEFT)

    def _sync_target_dirs(self, *_args):
        self.app.config.littlefs_raw_target_dir = self.raw_target_dir_var.get().strip()
        self.app.config.littlefs_gzip_target_dir = self.gzip_target_dir_var.get().strip()

    # ------------------------------------------------------------------

    def _start_flash_thread(self):
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
            data_dir=cfg.data_dir,
            web_dir=cfg.web_dir,
            offset=fs["offset"],
            partition_size=fs["size"],
            erase_first=cfg.erase_fs,
            block_size=cfg.littlefs_block_size,
            page_size=cfg.littlefs_page_size,
            baud=cfg.esptool_baud,
            raw_target_dir=cfg.littlefs_raw_target_dir,
            gzip_target_dir=cfg.littlefs_gzip_target_dir,
            verify=cfg.verify_after_write,
            logger=self.app.log,
            progress_cb=self.app.update_progress,
        )
