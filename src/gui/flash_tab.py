"""Littlefs Upload tab."""

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from ..littlefs import flash_littlefs
from ..partitions import get_partition


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

        ttk.Label(
            container, text="LittleFS Operations",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor=tk.W, pady=(0, 20))
        ttk.Label(
            container,
            text="Use Configuration tab for COM, paths, and options. This tab only runs the flash operation.",
            font=("Segoe UI", 10),
        ).pack(anchor=tk.W, pady=(0, 12))

        btns = ttk.Frame(container)
        btns.pack(fill=tk.X, pady=(8, 0))
        self.run_btn = tk.Button(
            btns,
            text="Build & Flash LittleFS",
            command=self._start_flash_thread,
            bg="#d64b4b", fg="#ffffff",
            activebackground="#be3f3f", activeforeground="#ffffff",
            relief=tk.FLAT, bd=0, padx=12, pady=6, cursor="hand2",
        )
        self.run_btn.pack(side=tk.LEFT)

    # ------------------------------------------------------------------

    def _start_flash_thread(self):
        if not self.app.config_tab.refresh_status():
            self.app.log("[ERROR] Environment checks are not ready.")
            return
        self.app.save_config()
        self.app.show_progress("LittleFS Flash Progress")
        self.app.set_buttons_busy(True)
        threading.Thread(target=self._run_flash, daemon=True).start()

    def _run_flash(self):
        try:
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
                logger=self.app.log,
                progress_cb=self.app.update_progress,
            )
            self.app.log("[SUCCESS] LittleFS flashed successfully.")
            self.app.root.after(0, messagebox.showinfo, "Success", "Filesystem flashed successfully.")
        except Exception as e:
            self.app.log(f"[ERROR] {e}")
            self.app.root.after(0, messagebox.showerror, "Error", str(e))
        finally:
            self.app.root.after(0, self.app.close_progress)
            self.app.root.after(0, self.app.set_buttons_busy, False)
