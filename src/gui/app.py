"""Main GUI application shell: tab assembly, logging, progress, config orchestration."""

import os
import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk

from ..config import (
    AppConfig,
    config_file_path,
    find_mklittlefs,
    find_nvs_gen,
    get_base_dirs,
    load_config,
    save_config,
)
from .config_tab import ConfigTabUI
from .flash_tab import FlashTabUI
from .nvs_tab import NvsTabUI
from .terminal_tab import HelpTabUI, TerminalTabUI


class ESPUploaderGUI:
    """ESP32 LittleFS + NVS Studio — main application window."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ESP32 LittleFS + NVS Studio")
        window_w, window_h = 980, 750
        screen_w = self.root.winfo_screenwidth()
        x = max(0, (screen_w - window_w) // 2)
        self.root.geometry(f"{window_w}x{window_h}+{x}+0")

        # Paths
        _bundle_dir, self._app_dir = get_base_dirs()
        self._external_lib_dir = os.path.join(self._app_dir, "external_lib")
        self._config_file = config_file_path(self._app_dir)

        # Load persisted config
        self.config = load_config(self._config_file)
        self._auto_detect_tools()

        # Progress state
        self._progress_var = tk.DoubleVar(value=0)
        self._progress_message_var = tk.StringVar(value="Ready")
        self._progress_window: tk.Toplevel | None = None
        self._progress_bar: ttk.Progressbar | None = None
        self._progress_label: ttk.Label | None = None

        # Build tabs
        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.config_tab = ConfigTabUI(self)
        self.flash_tab = FlashTabUI(self)
        self.nvs_tab = NvsTabUI(self)
        self.terminal_tab = TerminalTabUI(self)
        self.help_tab = HelpTabUI(self)

        # Theme
        import sv_ttk
        sv_ttk.set_theme("dark")

        # Finish init
        self.config_tab.sync_from_config()
        self.config_tab.refresh_serial_ports()
        self.config_tab.refresh_status()
        self.nvs_tab.auto_import_csv()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Tool auto-detection
    # ------------------------------------------------------------------

    def _auto_detect_tools(self):
        """Fill in missing tool paths from external_lib/ or PATH."""
        if not self.config.mklittlefs_path or not os.path.isfile(self.config.mklittlefs_path):
            found = find_mklittlefs(self._external_lib_dir)
            if found:
                self.config.mklittlefs_path = found

        if not self.config.nvs_gen_py or not os.path.isfile(self.config.nvs_gen_py):
            found = find_nvs_gen(self._external_lib_dir)
            if found:
                self.config.nvs_gen_py = found

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def log(self, message: str, level: str = "INFO"):
        if threading.current_thread() is not threading.main_thread():
            self.root.after(0, self.log, message, level)
            return
        log_area = self.terminal_tab.log_area
        log_area.configure(state="normal")
        lines = message.splitlines() or [message]
        for line in lines:
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted = f"[{timestamp}] [{level}] {line}"
            log_area.insert(tk.END, formatted + "\n")
        log_area.see(tk.END)
        log_area.configure(state="disabled")

    # ------------------------------------------------------------------
    # Progress window
    # ------------------------------------------------------------------

    def update_progress(self, percent: float, message: str = ""):
        if threading.current_thread() is not threading.main_thread():
            self.root.after(0, self.update_progress, percent, message)
            return
        pct = max(0.0, min(100.0, float(percent)))
        self._progress_var.set(pct)
        if message:
            self._progress_message_var.set(message)
            self.log(f"[PROGRESS] {message}")
        self.root.update_idletasks()

    def show_progress(self, title: str = "Operation Progress"):
        self._ensure_progress_window()
        self._progress_window.title(title)
        self._progress_window.update_idletasks()
        w = self._progress_window.winfo_width()
        h = self._progress_window.winfo_height()
        sw = self._progress_window.winfo_screenwidth()
        sh = self._progress_window.winfo_screenheight()
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        self._progress_window.geometry(f"{w}x{h}+{x}+{y}")
        self._progress_window.deiconify()
        self._progress_window.lift()
        self._progress_window.attributes("-topmost", True)
        self._progress_window.after(
            150,
            lambda: (
                self._progress_window.attributes("-topmost", False)
                if self._progress_window is not None and self._progress_window.winfo_exists()
                else None
            ),
        )

    def close_progress(self, delay_ms: int = 700):
        if self._progress_window is None or not self._progress_window.winfo_exists():
            return
        self._progress_window.after(delay_ms, self._progress_window.withdraw)

    def _ensure_progress_window(self):
        if self._progress_window is not None and self._progress_window.winfo_exists():
            return
        self._progress_window = tk.Toplevel(self.root)
        self._progress_window.title("Operation Progress")
        self._progress_window.geometry("420x82")
        self._progress_window.resizable(False, False)
        self._progress_window.transient(self.root)

        frame = ttk.Frame(self._progress_window, padding=8)
        frame.pack(fill=tk.BOTH, expand=True)
        self._progress_bar = ttk.Progressbar(frame, variable=self._progress_var, maximum=100, mode="determinate")
        self._progress_bar.pack(fill=tk.X)
        self._progress_label = ttk.Label(frame, textvariable=self._progress_message_var, font=("Segoe UI", 9))
        self._progress_label.pack(anchor=tk.W, pady=(4, 0))

        self._progress_window.protocol("WM_DELETE_WINDOW", self._progress_window.withdraw)

    # ------------------------------------------------------------------
    # Button state management
    # ------------------------------------------------------------------

    def set_buttons_busy(self, busy: bool):
        if busy:
            self.flash_tab.run_btn.config(state=tk.DISABLED)
            self.nvs_tab.write_btn.config(state=tk.DISABLED)
        else:
            self.config_tab.refresh_status()

    def set_flash_ready(self, ready: bool):
        self.flash_tab.run_btn.config(state=tk.NORMAL if ready else tk.DISABLED)

    def set_nvs_ready(self, ready: bool):
        self.nvs_tab.write_btn.config(state=tk.NORMAL if ready else tk.DISABLED)

    # ------------------------------------------------------------------
    # Config persistence
    # ------------------------------------------------------------------

    def save_config(self):
        self.config_tab.sync_to_config()
        save_config(self._config_file, self.config)

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def _on_close(self):
        self.save_config()
        if self._progress_window is not None and self._progress_window.winfo_exists():
            self._progress_window.destroy()
        self.root.destroy()
