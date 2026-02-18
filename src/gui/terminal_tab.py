"""Terminal Output and System Setup (Help) tabs."""

import tkinter as tk
import webbrowser
from tkinter import ttk


class TerminalTabUI:
    """Builds the Terminal Output tab and exposes the log area widget."""

    def __init__(self, app):
        self.app = app
        self.frame = ttk.Frame(app.tabs)
        app.tabs.add(self.frame, text="  Terminal Output  ")
        self._build()

    def _build(self):
        frame = ttk.Frame(self.frame, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)
        self.log_area = tk.Text(
            frame, bg="#1e1e1e", fg="#ffffff", borderwidth=0,
            font=("Consolas", 10), wrap=tk.WORD,
        )
        self.log_area.pack(fill=tk.BOTH, expand=True)
        self.log_area.configure(state="disabled")


class HelpTabUI:
    """Builds the System Setup / Help tab."""

    def __init__(self, app):
        self.app = app
        self.frame = ttk.Frame(app.tabs)
        app.tabs.add(self.frame, text="  System Setup  ")
        self._build()

    def _build(self):
        frame = ttk.Frame(self.frame, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        help_text = tk.Text(
            frame, wrap=tk.WORD, font=("Segoe UI", 10),
            bg="#1e1e1e", fg="#ffffff", borderwidth=0,
            highlightthickness=0, padx=8, pady=8,
        )
        help_text.pack(fill=tk.BOTH, expand=True)

        def _insert_link(widget, label, url):
            tag = f"link_{url}"
            widget.tag_configure(tag, foreground="#5a9fd4", underline=True)
            widget.tag_bind(tag, "<Enter>", lambda _e: widget.config(cursor="hand2"))
            widget.tag_bind(tag, "<Leave>", lambda _e: widget.config(cursor=""))
            widget.tag_bind(tag, "<Button-1>", lambda _e: webbrowser.open(url))
            widget.insert(tk.END, label, tag)

        help_text.insert(tk.END, "Uploader workflow:\n\n")
        help_text.insert(tk.END, "1) Configuration tab\n")
        help_text.insert(tk.END, "- Auto-detected COM port + chip\n")
        help_text.insert(tk.END, "- Browse to select partition CSV, data folder, and web folder\n")
        help_text.insert(tk.END, "- Install mklittlefs in external_lib/mklittlefs (from earlephilhower): ")
        _insert_link(help_text, "github.com/earlephilhower/mklittlefs",
                      "https://github.com/earlephilhower/mklittlefs")
        help_text.insert(tk.END, "\n")
        help_text.insert(tk.END, "- Install nvs_partition_gen.py in external_lib/nvs (from ESP-IDF): ")
        _insert_link(help_text, "github.com/.../nvs_partition_generator",
                      "https://github.com/espressif/esp-idf/blob/master/components/nvs_flash/nvs_partition_generator/")
        help_text.insert(tk.END, "\n")
        help_text.insert(tk.END, "- Optional: enable erase before LittleFS/NVS flashing\n")
        help_text.insert(tk.END, "- Auto-refresh status to validate environment\n\n")
        help_text.insert(tk.END, "2) Littlefs Upload tab\n")
        help_text.insert(tk.END, "- Builds LittleFS image (raw or after gzip). All files at root\n")
        help_text.insert(tk.END, "- Flashes LittleFS at the SPIFFS partition offset from partitions.csv\n\n")
        help_text.insert(tk.END, "3) NVS Editor tab\n")
        help_text.insert(tk.END, "- Import or edit NVS rows in CSV format (key,type,encoding,value)\n")
        help_text.insert(tk.END, "- Auto-imports last CSV saved in uploaderGUI.json when available\n")
        help_text.insert(tk.END, "- Export CSV for backup, then Write to Device to generate+flash NVS\n\n")
        help_text.insert(tk.END, "Required tools:\n")
        help_text.insert(tk.END, "- mklittlefs binary (in external_lib/mklittlefs/ or system PATH)\n")
        help_text.insert(tk.END, "- nvs_partition_gen.py (in external_lib/nvs/ or system PATH)\n")
        help_text.insert(tk.END, "- esp_idf_nvs_partition_gen (Python module)\n")
        help_text.insert(tk.END, "- esptool (Python module)")

        help_text.configure(state="disabled")
