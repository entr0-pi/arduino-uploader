"""ESP32 LittleFS + NVS Studio — entry point."""

import os
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox


def check_dependencies():
    """Install required dependencies from requirements.txt when missing."""
    missing = []
    for module, pip_name in [
        ("sv_ttk", "sv-ttk"),
        ("esptool", "esptool"),
        ("serial", "pyserial"),
        ("esp_idf_nvs_partition_gen", "esp_idf_nvs_partition_gen"),
    ]:
        try:
            __import__(module)
        except ImportError:
            missing.append(pip_name)
    if missing:
        req_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
        root = tk.Tk()
        root.withdraw()
        confirm = messagebox.askyesno(
            "Missing dependencies",
            "Missing packages detected:\n\n"
            + ", ".join(missing)
            + "\n\nInstall now from requirements.txt?",
        )
        if not confirm:
            root.destroy()
            sys.exit(1)
        if not os.path.isfile(req_path):
            messagebox.showerror("Install failed", f"requirements.txt not found:\n{req_path}")
            root.destroy()
            sys.exit(1)
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_path], check=True)
        except subprocess.CalledProcessError as exc:
            messagebox.showerror("Install failed", f"pip install failed.\n\n{exc}")
            root.destroy()
            sys.exit(1)
        messagebox.showinfo("Dependencies installed", "Dependencies installed successfully.")
        root.destroy()


if __name__ == "__main__":
    check_dependencies()
    from src.gui.app import ESPUploaderGUI

    root = tk.Tk()
    app = ESPUploaderGUI(root)
    root.mainloop()
