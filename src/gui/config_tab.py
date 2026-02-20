"""Configuration tab: serial port, chip, paths, environment status."""

import os
import threading
import tkinter as tk
from tkinter import filedialog, ttk

from ..esptool_wrapper import detect_chip_family, detect_serial_ports
from ..validators import VALID_CHIPS, sanitize_chip
from .theme import ERROR, FONT_BODY, FONT_HEADING, FONT_MONO_SMALL, FONT_STATUS, MUTED, OK, WARN

COMMON_BAUD_RATES = ["115200", "230400", "460800", "921600"]


class ConfigTabUI:
    """Builds and manages the Configuration tab."""

    def __init__(self, app):
        self.app = app
        self.frame = ttk.Frame(app.tabs)
        app.tabs.add(self.frame, text="  Configuration  ")

        self._chip_detect_running = False
        self._build()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build(self):
        container = ttk.Frame(self.frame, padding=20)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(container, text="Main Information", font=FONT_HEADING).pack(anchor=tk.W, pady=(0, 20))

        default_port = ""
        self.default_port = default_port
        self.port_var = tk.StringVar(value=self.app.config.port or default_port)
        self.chip_var = tk.StringVar(value=self.app.config.chip or "esp32")
        self.csv_path_var = tk.StringVar(value=self.app.config.csv_path)
        self.mklittlefs_path_var = tk.StringVar(value=self.app.config.mklittlefs_path)
        self.nvs_gen_py_var = tk.StringVar(value=self.app.config.nvs_gen_py)
        self.data_dir_var = tk.StringVar(value=self.app.config.data_dir)
        self.web_dir_var = tk.StringVar(value=self.app.config.web_dir)
        self.nvs_keys_h_var = tk.StringVar(value=self.app.config.nvs_keys_h_path)
        self.erase_fs_var = tk.BooleanVar(value=self.app.config.erase_fs)
        self.erase_nvs_var = tk.BooleanVar(value=self.app.config.erase_nvs)
        self.baud_var = tk.StringVar(value=self.app.config.esptool_baud)
        self.block_size_var = tk.StringVar(value=str(self.app.config.littlefs_block_size))
        self.page_size_var = tk.StringVar(value=str(self.app.config.littlefs_page_size))
        self.verify_var = tk.BooleanVar(value=self.app.config.verify_after_write)
        self.show_advanced_var = tk.BooleanVar(value=False)

        # Refresh status when paths change
        for var in (self.csv_path_var, self.mklittlefs_path_var, self.nvs_gen_py_var,
                    self.data_dir_var, self.web_dir_var, self.baud_var, self.block_size_var, self.page_size_var):
            var.trace_add("write", lambda *_a: self.app.root.after_idle(self.refresh_status))

        # Card 1: serial/chip/partition + tools
        card1 = ttk.LabelFrame(container, text="Connection & Tools", padding=12)
        card1.pack(fill=tk.X, pady=(0, 10))
        card1.columnconfigure(0, weight=0)
        card1.columnconfigure(1, weight=0)
        card1.columnconfigure(2, weight=1)

        ttk.Label(card1, text="Serial Port").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(card1, text="Chip Family").grid(row=0, column=1, sticky=tk.W)
        ttk.Label(card1, text="Partitions Definition (.csv)").grid(row=0, column=2, sticky=tk.W)

        self.port_combo = ttk.Combobox(card1, textvariable=self.port_var, width=16)
        self.port_combo.grid(row=1, column=0, sticky=tk.EW, padx=(0, 12), pady=(4, 10))
        self.port_combo.bind("<<ComboboxSelected>>", lambda _e: self.start_chip_detect_thread())
        self.port_combo.bind("<FocusOut>", lambda _e: self.start_chip_detect_thread())
        ttk.Combobox(
            card1, textvariable=self.chip_var, values=list(VALID_CHIPS),
            width=16,
        ).grid(row=1, column=1, sticky=tk.W, padx=(0, 12), pady=(4, 10))

        tools_grid = ttk.Frame(card1)
        tools_grid.grid(row=2, column=0, columnspan=3, sticky=tk.EW, pady=(2, 0))
        tools_grid.columnconfigure(0, weight=1)
        tools_grid.columnconfigure(1, weight=1)

        csv_row = ttk.Frame(card1)
        csv_row.grid(row=1, column=2, sticky=tk.EW, pady=(4, 10))
        csv_row.columnconfigure(0, weight=1)
        ttk.Entry(csv_row, textvariable=self.csv_path_var).grid(row=0, column=0, sticky=tk.EW)
        ttk.Button(csv_row, text="Browse", command=self._browse_csv).grid(row=0, column=1, padx=(8, 0))

        ttk.Label(tools_grid, text="Binary for mklittlefs (path)").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(tools_grid, text="Script nvs_partition_gen.py (path)").grid(row=0, column=1, sticky=tk.W, padx=(6, 0))

        mkl_row = ttk.Frame(tools_grid)
        mkl_row.grid(row=1, column=0, sticky=tk.EW, padx=(0, 6), pady=(4, 0))
        mkl_row.columnconfigure(0, weight=1)
        ttk.Entry(mkl_row, textvariable=self.mklittlefs_path_var).grid(row=0, column=0, sticky=tk.EW)
        ttk.Button(
            mkl_row, text="Browse", command=lambda: self._browse_file(self.mklittlefs_path_var, "Executable", "*")
        ).grid(row=0, column=1, padx=(8, 0))

        nvs_gen_row = ttk.Frame(tools_grid)
        nvs_gen_row.grid(row=1, column=1, sticky=tk.EW, padx=(6, 0), pady=(4, 0))
        nvs_gen_row.columnconfigure(0, weight=1)
        ttk.Entry(nvs_gen_row, textvariable=self.nvs_gen_py_var).grid(row=0, column=0, sticky=tk.EW)
        ttk.Button(
            nvs_gen_row, text="Browse", command=lambda: self._browse_file(self.nvs_gen_py_var, "Python", "*.py")
        ).grid(row=0, column=1, padx=(8, 0))

        # Advanced settings (collapsed by default)
        ttk.Checkbutton(
            card1,
            text="Show advanced parameters (baud, block size, page size)",
            variable=self.show_advanced_var,
            command=self._toggle_advanced_params,
        ).grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=(8, 0))

        self.adv_row = ttk.Frame(card1)
        self.adv_row.grid(row=4, column=0, columnspan=3, sticky=tk.EW, pady=(8, 0))
        self.adv_row.columnconfigure(0, weight=1)
        self.adv_row.columnconfigure(1, weight=1)
        self.adv_row.columnconfigure(2, weight=1)

        ttk.Label(self.adv_row, text="Esptool baud rate").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(self.adv_row, text="LittleFS block size").grid(row=0, column=1, sticky=tk.W, padx=(6, 0))
        ttk.Label(self.adv_row, text="LittleFS page size").grid(row=0, column=2, sticky=tk.W, padx=(6, 0))

        ttk.Combobox(self.adv_row, textvariable=self.baud_var, values=COMMON_BAUD_RATES, width=12).grid(
            row=1, column=0, sticky=tk.EW, pady=(4, 0)
        )
        ttk.Entry(self.adv_row, textvariable=self.block_size_var, width=12).grid(
            row=1, column=1, sticky=tk.EW, padx=(6, 0), pady=(4, 0)
        )
        ttk.Entry(self.adv_row, textvariable=self.page_size_var, width=12).grid(
            row=1, column=2, sticky=tk.EW, padx=(6, 0), pady=(4, 0)
        )
        ttk.Checkbutton(
            self.adv_row,
            text="Verify after write (slower)",
            variable=self.verify_var,
        ).grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(8, 0))
        self._toggle_advanced_params()

        # Card 2: directories + nvs keys
        card2 = ttk.LabelFrame(container, text="Paths", padding=12)
        card2.pack(fill=tk.X, pady=(0, 10))
        card2.columnconfigure(0, weight=1)
        card2.columnconfigure(1, weight=1)

        ttk.Label(card2, text="LittleFS raw files (folder)").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(card2, text="LittleFS files to gzip (folder)").grid(row=0, column=1, sticky=tk.W)

        data_row = ttk.Frame(card2)
        data_row.grid(row=1, column=0, sticky=tk.EW, padx=(0, 12), pady=(4, 10))
        data_row.columnconfigure(0, weight=1)
        ttk.Entry(data_row, textvariable=self.data_dir_var).grid(row=0, column=0, sticky=tk.EW)
        ttk.Button(data_row, text="Browse", command=lambda: self._browse_dir(self.data_dir_var)).grid(row=0, column=1, padx=(8, 0))

        web_row = ttk.Frame(card2)
        web_row.grid(row=1, column=1, sticky=tk.EW, pady=(4, 10))
        web_row.columnconfigure(0, weight=1)
        ttk.Entry(web_row, textvariable=self.web_dir_var).grid(row=0, column=0, sticky=tk.EW)
        ttk.Button(web_row, text="Browse", command=lambda: self._browse_dir(self.web_dir_var)).grid(row=0, column=1, padx=(8, 0))

        ttk.Label(card2, text="NVS consistency check - nvs_keys.h (optional)").grid(row=2, column=0, sticky=tk.W)
        nvs_keys_row = ttk.Frame(card2)
        nvs_keys_row.grid(row=3, column=0, sticky=tk.EW, padx=(0, 12), pady=(4, 0))
        nvs_keys_row.columnconfigure(0, weight=1)
        ttk.Entry(nvs_keys_row, textvariable=self.nvs_keys_h_var).grid(row=0, column=0, sticky=tk.EW)
        ttk.Button(
            nvs_keys_row, text="Browse", command=lambda: self._browse_file(self.nvs_keys_h_var, "Header", "*.h")
        ).grid(row=0, column=1, padx=(8, 0))

        # Card 3: options + status + actions
        card3 = ttk.LabelFrame(container, text="Environment & Actions", padding=12)
        card3.pack(fill=tk.X)

        status_row = ttk.Frame(card3)
        status_row.pack(fill=tk.X, pady=(0, 0))
        status_row.columnconfigure(0, weight=1)
        status_row.columnconfigure(1, weight=1)

        status_libs = ttk.LabelFrame(status_row, text="Environment Status - Libraries", padding=10)
        status_libs.grid(row=0, column=0, sticky=tk.NSEW, padx=(0, 6))
        status_files = ttk.LabelFrame(status_row, text="Environment Status - Files", padding=10)
        status_files.grid(row=0, column=1, sticky=tk.NSEW, padx=(6, 0))

        self.status_labels = {}
        for key in ("port", "mklittlefs", "nvsgen", "csv"):
            self.status_labels[key] = ttk.Label(status_libs, text="", font=FONT_BODY)
            self.status_labels[key].pack(anchor=tk.W, pady=2)
        for key in ("data", "data_files", "web", "web_files"):
            lbl = ttk.Label(status_files, text="", font=FONT_BODY)
            if key.endswith("_files"):
                lbl.configure(font=FONT_MONO_SMALL, foreground=MUTED)
                lbl.pack(anchor=tk.W, pady=(0, 4), padx=(16, 0))
            else:
                lbl.pack(anchor=tk.W, pady=2)
            self.status_labels[key] = lbl

        # Buttons
        btns = ttk.Frame(card3)
        btns.pack(fill=tk.X, pady=(16, 0))
        ttk.Button(btns, text="Refresh", command=self._on_refresh_click).pack(side=tk.LEFT)
        ttk.Button(btns, text="Save Configuration", command=self.app.save_config).pack(side=tk.LEFT, padx=(8, 0))
        self.readiness_label = ttk.Label(btns, text="", font=FONT_STATUS)
        self.readiness_label.pack(side=tk.LEFT, padx=(20, 0))

    # ------------------------------------------------------------------
    # Browse helpers
    # ------------------------------------------------------------------

    def _browse_csv(self):
        p = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if p:
            self.csv_path_var.set(p)

    def _browse_file(self, tk_var, label, pattern):
        p = filedialog.askopenfilename(filetypes=[(label, pattern), ("All", "*")])
        if p:
            tk_var.set(p)

    def _browse_dir(self, tk_var):
        p = filedialog.askdirectory()
        if p:
            tk_var.set(p)

    def _toggle_advanced_params(self):
        if self.show_advanced_var.get():
            self.adv_row.grid()
        else:
            self.adv_row.grid_remove()

    # ------------------------------------------------------------------
    # Serial port & chip detection
    # ------------------------------------------------------------------

    def refresh_serial_ports(self, announce=False):
        detected = detect_serial_ports()
        current = self.port_var.get().strip()
        values = list(detected)
        if current and current not in values and not (detected and current == self.default_port):
            values.insert(0, current)
        self.port_combo["values"] = values
        if detected and (not current or current == self.default_port):
            self.port_var.set(detected[0])
            self.start_chip_detect_thread()
        if announce:
            if detected:
                self.app.log(f">>> Detected serial ports: {', '.join(detected)}")
            else:
                self.app.log("[WARN] No serial ports detected.")

    def start_chip_detect_thread(self):
        if self._chip_detect_running:
            return
        port = self.port_var.get().strip()
        if not port:
            return
        self._chip_detect_running = True
        threading.Thread(target=self._detect_chip_family, args=(port,), daemon=True).start()

    def _detect_chip_family(self, port):
        try:
            detected = detect_chip_family(port)
            if detected and detected in VALID_CHIPS:
                self.app.root.after(0, self._set_detected_chip, detected, port)
        except Exception as exc:
            self.app.root.after(0, self.app.log, f"[WARN] Chip detection failed on {port}: {exc}")
        finally:
            self._chip_detect_running = False

    def _set_detected_chip(self, chip, port):
        if self.port_var.get().strip() != port:
            return
        if self.chip_var.get() != chip:
            self.chip_var.set(chip)
            self.app.log(f">>> Auto-detected chip family on {port}: {chip}")

    # ------------------------------------------------------------------
    # Status refresh
    # ------------------------------------------------------------------

    def _on_refresh_click(self):
        self.app._auto_detect_tools()
        self.refresh_serial_ports()
        self.refresh_status()

    def refresh_status(self) -> bool:
        """Update all status labels and return whether FS flash is ready."""
        ok_color = OK
        warn_color = WARN
        err_color = ERROR

        port_selected = bool(self.port_var.get().strip())
        checks = {
            "port": port_selected,
            "mklittlefs": os.path.isfile(self.mklittlefs_path_var.get()),
            "nvsgen": os.path.isfile(self.nvs_gen_py_var.get()),
            "csv": bool(self.csv_path_var.get() and os.path.isfile(self.csv_path_var.get())),
        }

        # Data directory
        data_dir = self.data_dir_var.get()
        data_dir_exists = bool(data_dir) and os.path.isdir(data_dir)
        data_files: list[str] = []
        if data_dir_exists:
            data_files = sorted(
                f for f in os.listdir(data_dir)
                if os.path.isfile(os.path.join(data_dir, f))
            )

        # Web directory
        web_dir = self.web_dir_var.get()
        web_dir_exists = bool(web_dir) and os.path.isdir(web_dir)
        web_files: list[str] = []
        if web_dir_exists:
            web_files = sorted(
                f for f in os.listdir(web_dir)
                if os.path.isfile(os.path.join(web_dir, f))
            )

        # Update labels
        port_text = self.port_var.get().strip() or "Not selected"
        self.status_labels["port"].config(
            text=f"Serial port: {port_text}",
            foreground=ok_color if checks["port"] else warn_color,
        )
        self.status_labels["mklittlefs"].config(
            text=f"mklittlefs: {'Found' if checks['mklittlefs'] else 'Missing'}",
            foreground=ok_color if checks["mklittlefs"] else err_color,
        )
        self.status_labels["nvsgen"].config(
            text=f"nvs_partition_gen.py: {'Found' if checks['nvsgen'] else 'Missing'}",
            foreground=ok_color if checks["nvsgen"] else err_color,
        )
        self.status_labels["csv"].config(
            text=f"partitions.csv: {'Found' if checks['csv'] else 'Not selected'}",
            foreground=ok_color if checks["csv"] else err_color,
        )

        if not data_dir:
            self.status_labels["data"].config(text="Raw data dir: Not configured", foreground=warn_color)
            self.status_labels["data_files"].config(text="")
        elif not data_dir_exists:
            self.status_labels["data"].config(text="Raw data dir: Path not found", foreground=err_color)
            self.status_labels["data_files"].config(text="")
        elif not data_files:
            self.status_labels["data"].config(text="Raw data dir: 0 files", foreground=warn_color)
            self.status_labels["data_files"].config(text="")
        else:
            label = "file" if len(data_files) == 1 else "files"
            self.status_labels["data"].config(text=f"Raw data dir: {len(data_files)} {label}", foreground=ok_color)
            self.status_labels["data_files"].config(text=", ".join(data_files))

        if not web_dir:
            self.status_labels["web"].config(text="Gzip data dir: Not configured", foreground=warn_color)
            self.status_labels["web_files"].config(text="")
        elif not web_dir_exists:
            self.status_labels["web"].config(text="Gzip data dir: Path not found", foreground=err_color)
            self.status_labels["web_files"].config(text="")
        elif not web_files:
            self.status_labels["web"].config(text="Gzip data dir: 0 files", foreground=warn_color)
            self.status_labels["web_files"].config(text="")
        else:
            label = "file" if len(web_files) == 1 else "files"
            self.status_labels["web"].config(text=f"Gzip data dir: {len(web_files)} {label}", foreground=ok_color)
            self.status_labels["web_files"].config(text=", ".join(web_files))

        fs_ready = checks["mklittlefs"] and checks["csv"]
        nvs_ready = checks["nvsgen"] and checks["csv"]

        # Update action buttons via app
        self.app.set_flash_ready(fs_ready)
        self.app.set_nvs_ready(nvs_ready)

        if fs_ready and nvs_ready and checks["port"]:
            self.readiness_label.config(text="\u2705 Ready", foreground=ok_color)
        elif fs_ready and nvs_ready:
            self.readiness_label.config(text="\u26a0\ufe0f Ready (no port selected)", foreground=warn_color)
        elif fs_ready or nvs_ready:
            missing = []
            if not checks["port"]:
                missing.append("serial port")
            if not checks["csv"]:
                missing.append("partitions.csv")
            if not checks["mklittlefs"]:
                missing.append("mklittlefs")
            if not checks["nvsgen"]:
                missing.append("nvs_partition_gen")
            scope = "LittleFS only" if fs_ready else "NVS only"
            detail = f" \u2014 missing: {', '.join(missing)}" if missing else ""
            self.readiness_label.config(text=f"\u26a0\ufe0f Partially ready ({scope}){detail}", foreground=warn_color)
        else:
            missing = []
            if not checks["port"]:
                missing.append("serial port")
            if not checks["csv"]:
                missing.append("partitions.csv")
            if not checks["mklittlefs"]:
                missing.append("mklittlefs")
            if not checks["nvsgen"]:
                missing.append("nvs_partition_gen")
            self.readiness_label.config(
                text=f"\u274c Not ready \u2014 missing: {', '.join(missing)}", foreground=err_color,
            )

        return fs_ready

    # ------------------------------------------------------------------
    # Sync to/from AppConfig
    # ------------------------------------------------------------------

    def sync_to_config(self):
        """Push current UI values into ``app.config``."""
        cfg = self.app.config
        cfg.port = self.port_var.get()
        cfg.chip = sanitize_chip(self.chip_var.get())
        cfg.csv_path = self.csv_path_var.get()
        cfg.erase_fs = self.erase_fs_var.get()
        cfg.erase_nvs = self.erase_nvs_var.get()
        cfg.verify_after_write = self.verify_var.get()
        cfg.mklittlefs_path = self.mklittlefs_path_var.get()
        cfg.nvs_gen_py = self.nvs_gen_py_var.get()
        cfg.data_dir = self.data_dir_var.get()
        cfg.web_dir = self.web_dir_var.get()
        cfg.nvs_keys_h_path = self.nvs_keys_h_var.get()
        cfg.esptool_baud = self.baud_var.get()
        try:
            cfg.littlefs_block_size = int(self.block_size_var.get())
        except ValueError:
            cfg.littlefs_block_size = 4096
        try:
            cfg.littlefs_page_size = int(self.page_size_var.get())
        except ValueError:
            cfg.littlefs_page_size = 256

    def sync_from_config(self):
        """Load ``app.config`` values into UI widgets."""
        cfg = self.app.config
        if cfg.port:
            self.port_var.set(cfg.port)
        if cfg.chip:
            self.chip_var.set(cfg.chip)
        self.csv_path_var.set(cfg.csv_path)
        self.erase_fs_var.set(cfg.erase_fs)
        self.erase_nvs_var.set(cfg.erase_nvs)
        self.verify_var.set(cfg.verify_after_write)
        self.mklittlefs_path_var.set(cfg.mklittlefs_path)
        self.nvs_gen_py_var.set(cfg.nvs_gen_py)
        self.data_dir_var.set(cfg.data_dir)
        self.web_dir_var.set(cfg.web_dir)
        self.nvs_keys_h_var.set(cfg.nvs_keys_h_path)
        self.baud_var.set(cfg.esptool_baud)
        self.block_size_var.set(str(cfg.littlefs_block_size))
        self.page_size_var.set(str(cfg.littlefs_page_size))
