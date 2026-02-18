# ESP32 LittleFS + NVS Studio

A standalone desktop GUI application for flashing **LittleFS filesystem images** and **NVS (Non-Volatile Storage) key-value data** to ESP32 microcontrollers.

Built with Python and Tkinter, this tool provides a visual interface for operations that typically require command-line tools and manual partition offset calculations.

---

## Features

### LittleFS Flash Operations
- **Data file staging** — copies raw files from a user-selected data directory into the filesystem image
- **Web file staging with automatic gzip** — copies all files from a web directory and gzip-compresses each one to save flash space
- **Image building** — creates a LittleFS binary image using `mklittlefs`, sized to match the SPIFFS partition from your `partitions.csv`
- **One-click flash** — uploads the image to the device at the correct partition offset via `esptool`
- **Optional erase-before-flash** — erases the filesystem partition before writing

### NVS Editor
- **Visual table editor** — add, edit, and remove NVS key-value pairs grouped by namespace
- **CSV import/export** — load and save NVS data in the standard ESP-IDF CSV format (`key,type,encoding,value`)
- **Auto-import on startup** — the last-used NVS CSV is automatically reloaded when the app opens
- **Binary generation** — converts the CSV to an NVS binary partition using `nvs_partition_gen.py`
- **Flash to device** — writes the generated NVS binary to the correct NVS partition offset
- **Optional erase-before-write** — erases the NVS partition before writing
- **Lock/unlock metadata fields** — namespace, key, type, and encoding fields are locked by default to prevent accidental edits; unlock them with a checkbox

### NVS Validation
- **Header consistency check** — compares NVS editor data against a C++ `nvs_keys.h` header file to detect missing or extra keys per namespace
- **Value validation** — checks that pin numbers (0-48), baud rates (standard rates), IPv4 addresses, port numbers (1-65535), and boolean values (0/1) are well-formed
- **Pre-flash warnings** — validation issues are shown before writing to device, with an option to proceed anyway

### Configuration & Auto-Detection
- **Serial port auto-detection** — scans available COM ports (Windows) or `/dev/tty*` devices (Linux/macOS)
- **Chip family auto-detection** — queries the connected device via `esptool chip_id` and sets the chip type automatically
- **Tool auto-detection** — finds `mklittlefs` and `nvs_partition_gen.py` in `external_lib/` or on the system PATH
- **Persistent configuration** — all paths, port, chip, and options are saved to `uploaderGUI.json` and restored on next launch
- **Dark theme** — uses the `sv-ttk` Sun Valley theme for a modern dark-mode interface

---

## Supported Chips

`esp32` | `esp32s2` | `esp32s3` | `esp32c2` | `esp32c3` | `esp32c6` | `esp32h2` | `esp32p4` | `esp8266`

---

## Requirements

- **Python 3.10+** (uses `match`-compatible syntax and `X | Y` union types)
- **Tkinter** (included with most Python installations)

### Python Packages

Install the dependencies:

```bash
pip install -r requirements.txt
```

Contents of `requirements.txt`:

| Package | Purpose |
|---------|---------|
| `esptool` | Flashing LittleFS and NVS partition images to ESP devices |
| `sv-ttk` | Sun Valley dark theme for Tkinter |
| `pyserial` | Serial port detection and access |
| `esp_idf_nvs_partition_gen` | NVS binary generation support |

### External Tools

These tools are **not** Python packages — they are standalone binaries/scripts that must be placed in `external_lib/` or be available on your system PATH:

| Tool | Location | Source |
|------|----------|--------|
| `mklittlefs` | `external_lib/mklittlefs/mklittlefs[.exe]` | [earlephilhower/mklittlefs](https://github.com/earlephilhower/mklittlefs/releases) |
| `nvs_partition_gen.py` | `external_lib/nvs/nvs_partition_gen.py` | [ESP-IDF nvs_partition_generator](https://github.com/espressif/esp-idf/tree/master/components/nvs_flash/nvs_partition_generator) |

> The app will also search for these tools on the system PATH. If auto-detection fails, you can browse to them manually in the Configuration tab.

---

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/<your-org>/arduino-uploader.git
   cd arduino-uploader
   ```

2. **Install Python dependencies** (or let the app install them on first launch):

   ```bash
   pip install -r requirements.txt
   ```

3. **Download external tools:**

   - Download the `mklittlefs` binary for your platform from [the releases page](https://github.com/earlephilhower/mklittlefs/releases) and place it in `external_lib/mklittlefs/`
   - Download `nvs_partition_gen.py` from the [ESP-IDF repository](https://github.com/espressif/esp-idf/tree/master/components/nvs_flash/nvs_partition_generator) and place it in `external_lib/nvs/`

4. **Launch the application:**

   ```bash
   python uploaderGUI.py
   ```

   If dependencies are missing, the app prompts for confirmation and can run:
   `python -m pip install -r requirements.txt` automatically.

---

## Usage

### First Launch

1. Open the **Configuration** tab
2. The serial port and chip family are auto-detected if a device is connected
3. In **Connection & Tools**, select your **partitions.csv** and verify `mklittlefs` / `nvs_partition_gen.py`
4. In **Paths**, select your **data directory** (raw files for LittleFS), **web directory** (all files gzipped), and optional `nvs_keys.h`
5. Verify status indicators are green
6. Click **Save Configuration** to persist all paths

### Flashing a LittleFS Image

1. Ensure the Configuration tab shows **Ready** status
2. Go to the **Littlefs Upload** tab
3. Click **Build & Flash LittleFS**
4. A progress window tracks: staging data files, staging web files, building image, flashing

The tool automatically:
- Reads the SPIFFS partition offset and size from your `partitions.csv`
- Copies all files from the data directory
- Copies all files from the web directory (gzipping each file)
- Builds a LittleFS image sized to match the partition
- Flashes at the correct offset

### Managing NVS Variables

1. Go to the **NVS Editor** tab
2. **Import** an existing NVS CSV file, or add entries manually
3. Edit values in the table (select a row to load it into the edit fields)
4. **Export** to save your changes to a CSV file
5. Click **Write to Device** to generate the NVS binary and flash it

### NVS Consistency Checking

If your project uses a `nvs_keys.h` header file to define NVS constants:

1. In the **Configuration** tab, browse to your `nvs_keys.h` file
2. The NVS Editor tab will show a consistency status label:
   - **Green check** — all keys in the editor match the header
   - **Red X with issue count** — mismatches detected (missing keys, extra keys, invalid values)
3. Before writing to device, validation issues trigger a confirmation dialog

---

## Input File Formats

### Partition Table CSV (`partitions.csv`)

Standard ESP-IDF partition table format. The tool looks for partitions with subtype `spiffs` (for LittleFS) and `nvs` (for NVS data):

```csv
# Name,     Type,  SubType,  Offset,   Size,     Flags
nvs,        data,  nvs,      0x9000,   0x6000,
app0,       app,   factory,  0x10000,  0x300000,
spiffs,     data,  spiffs,   0x310000, 0x40000,
coredump,   data,  coredump, 0x350000, 0x1000,
```

### NVS CSV (`nvs_keys.csv`)

Standard ESP-IDF NVS CSV format with `key,type,encoding,value` columns. Namespace rows have `type=namespace` and no value:

```csv
key,type,encoding,value
gnss,namespace,,
rx_pin,data,i32,18
tx_pin,data,i32,17
baud,data,u32,9600
wifi,namespace,,
ssid,data,string,YOUR_WIFI_SSID
pass,data,string,YOUR_WIFI_PASSWORD
dhcp,data,u8,1
ip,data,string,192.168.1.50
```

Supported encodings: `string`, `u8`, `i8`, `u16`, `u32`, `i32`, `base64`, `hex2bin`, `binary`

### NVS Header (`nvs_keys.h`) — Optional

A C++ header file declaring NVS namespace and key constants. Used for consistency validation only:

```cpp
#pragma once

namespace nvs_keys {

namespace gnss {
constexpr const char* kNamespace = "gnss";
constexpr const char* kRxPin = "rx_pin";
constexpr const char* kTxPin = "tx_pin";
constexpr const char* kBaud = "baud";
}  // namespace gnss

namespace wifi {
constexpr const char* kNamespace = "wifi";
constexpr const char* kSsid = "ssid";
// ...
}  // namespace wifi

}  // namespace nvs_keys
```

The parser extracts the `kNamespace = "..."` value to identify the NVS namespace, and all other `constexpr const char*` declarations as expected keys within that namespace. Nested C++ namespaces (e.g. `ntrip::lockout`) are supported.

---

## Project Structure

```
arduino-uploader/
├── uploaderGUI.py              # Entry point (thin launcher)
├── requirements.txt            # Python dependencies
├── .gitignore
│
├── example/                    # Example input files
│   ├── partitions.csv          # Sample ESP32 partition table
│   ├── nvs_keys.csv            # Sample NVS key-value data
│   └── nvs_keys.h              # Sample C++ NVS header
│
├── external_lib/               # External tool binaries (user-provided)
│   ├── mklittlefs/             # Place mklittlefs binary here
│   │   └── .gitkeep
│   └── nvs/                    # Place nvs_partition_gen.py here
│       └── .gitkeep
│
└── src/                        # Application source code
    ├── __init__.py
    ├── config.py               # AppConfig dataclass, JSON persistence, tool finder
    ├── validators.py           # Input validation (IPv4, baud, pin, port, boolean)
    ├── partitions.py           # Partition table CSV parsing
    ├── esptool_wrapper.py      # Subprocess runners, serial/chip detection
    ├── littlefs.py             # LittleFS staging, image building, flashing
    ├── nvs.py                  # NVS CSV I/O, header parsing, validation, flashing
    │
    └── gui/                    # Tkinter GUI layer
        ├── __init__.py
        ├── app.py              # Main window, tab assembly, logging, progress
        ├── config_tab.py       # Configuration tab (ports, paths, status)
        ├── flash_tab.py        # Littlefs Upload tab
        ├── nvs_tab.py          # NVS Editor tab (table, import/export, write)
        └── terminal_tab.py     # Terminal Output + System Setup (Help) tabs
```

### Architecture

The codebase is split into two layers:

- **Business logic** (`src/*.py`) — pure Python modules with no GUI dependency. All external interactions (logging, progress updates) use optional callbacks, making the logic testable and reusable independently of the GUI.

- **GUI layer** (`src/gui/*.py`) — Tkinter widgets and event handling. Each tab is its own module. The GUI delegates all operations to the business logic layer and passes `logger` / `progress_cb` callbacks for feedback.

---

## Configuration Persistence

All settings are saved to `uploaderGUI.json` in the application directory. The file is automatically created on first save and loaded on startup.

Persisted fields:

| Field | Description |
|-------|-------------|
| `port` | Serial port (e.g. `COM3`, `/dev/ttyUSB0`) |
| `chip` | Chip family (e.g. `esp32s3`) |
| `csv_path` | Path to `partitions.csv` |
| `nvs_csv_path` | Path to last-used NVS CSV (auto-imported on startup) |
| `erase_fs` | Erase FS partition before flash (boolean) |
| `erase_nvs` | Erase NVS partition before write (boolean) |
| `mklittlefs_path` | Path to `mklittlefs` binary |
| `nvs_gen_py` | Path to `nvs_partition_gen.py` |
| `data_dir` | Path to data directory for LittleFS |
| `web_dir` | Path to web directory for LittleFS |
| `nvs_keys_h_path` | Path to `nvs_keys.h` (optional) |

---

## Troubleshooting

### "Missing dependencies" dialog on startup

The app can install dependencies automatically from `requirements.txt` after confirmation.
You can also install them manually:

```bash
pip install -r requirements.txt
```

### mklittlefs or nvs_partition_gen.py not found

1. Download the tools (see [External Tools](#external-tools) above)
2. Place them in `external_lib/mklittlefs/` and `external_lib/nvs/` respectively
3. Or browse to their location manually in the Configuration tab

### No serial ports detected

- Ensure the ESP32 is connected via USB
- Install the appropriate USB-to-serial driver (CP2102, CH340, etc.)
- Install `pyserial`: `pip install pyserial`

### Partition subtype 'spiffs' not found

Your `partitions.csv` must contain a partition with `subtype = spiffs` for LittleFS operations, and `subtype = nvs` for NVS operations. See the [example file](example/partitions.csv).

### Flash fails with timeout or connection error

- Check that no other program (serial monitor, IDE) is using the serial port
- Try a lower baud rate by editing `ESPTOOL_BAUD` in `src/esptool_wrapper.py` (default: `921600`)
- Hold the BOOT button on the ESP32 while flashing

---

## License

This project is provided as-is. See the repository for license details.
