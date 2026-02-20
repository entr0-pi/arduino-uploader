"""Application configuration: dataclass, persistence, and tool auto-detection."""

import json
import os
import platform
import shutil
import sys
from dataclasses import dataclass, fields


@dataclass
class AppConfig:
    """All user-configurable settings, persisted as JSON."""

    port: str = ""
    chip: str = "esp32"
    csv_path: str = ""
    nvs_csv_path: str = ""
    erase_fs: bool = False
    erase_nvs: bool = False
    mklittlefs_path: str = ""
    nvs_gen_py: str = ""
    data_dir: str = ""
    web_dir: str = ""
    nvs_keys_h_path: str = ""
    esptool_baud: str = "921600"
    littlefs_block_size: int = 4096
    littlefs_page_size: int = 256
    littlefs_raw_target_dir: str = ""
    littlefs_gzip_target_dir: str = ""
    verify_after_write: bool = False


def _is_path_field(field_name: str) -> bool:
    return field_name.endswith("_path") or field_name.endswith("_dir")


def _normalize_path(value: str) -> str:
    """Normalize a filesystem path for consistent JSON persistence."""
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return text
    norm = os.path.normpath(text)
    if len(norm) >= 2 and norm[1] == ":" and norm[0].isalpha():
        norm = norm[0].upper() + norm[1:]
    return norm


def get_base_dirs() -> tuple[str, str]:
    """Return ``(bundle_dir, app_dir)``.

    *bundle_dir* is ``sys._MEIPASS`` when frozen (PyInstaller), otherwise the
    directory containing this package's parent (the repo root).
    *app_dir* is the directory of the executable when frozen, else same as
    *bundle_dir*.
    """
    if getattr(sys, "frozen", False):
        bundle_dir = sys._MEIPASS  # type: ignore[attr-defined]
        app_dir = os.path.dirname(sys.executable)
    else:
        # src/config.py -> repo root
        bundle_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_dir = bundle_dir
    return bundle_dir, app_dir


def find_tool(
    name: str,
    external_lib_dir: str,
    subfolder: str | None = None,
    binary_name: str | None = None,
) -> str:
    """Auto-detect a tool binary or script.

    Search order:
    1. ``external_lib/<subfolder>/<binary_name>``
    2. System PATH via ``shutil.which(binary_name)``

    Returns the path if found, otherwise ``""``.
    """
    if subfolder is None:
        subfolder = name
    if binary_name is None:
        binary_name = name

    # 1. external_lib/<subfolder>/
    candidate = os.path.join(external_lib_dir, subfolder, binary_name)
    if os.path.isfile(candidate):
        return candidate

    # 2. System PATH
    found = shutil.which(binary_name)
    if found:
        return found

    return ""


def find_mklittlefs(external_lib_dir: str) -> str:
    """Find the mklittlefs binary."""
    binary = "mklittlefs.exe" if platform.system() == "Windows" else "mklittlefs"
    return find_tool("mklittlefs", external_lib_dir, binary_name=binary)


def find_nvs_gen(external_lib_dir: str) -> str:
    """Find nvs_partition_gen.py."""
    return find_tool(
        "nvs_partition_gen",
        external_lib_dir,
        subfolder="nvs",
        binary_name="nvs_partition_gen.py",
    )


def config_file_path(app_dir: str) -> str:
    """Return the default config file path."""
    return os.path.join(app_dir, "uploaderGUI.json")


def load_config(config_file: str) -> AppConfig:
    """Load config from JSON. Returns defaults for missing/corrupt files."""
    cfg = AppConfig()
    if not os.path.isfile(config_file):
        return cfg
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        valid_fields = {fld.name for fld in fields(AppConfig)}
        for key, value in data.items():
            if key in valid_fields:
                if _is_path_field(key) and isinstance(value, str):
                    value = _normalize_path(value)
                setattr(cfg, key, value)
    except Exception:
        pass
    return cfg


def save_config(config_file: str, cfg: AppConfig) -> None:
    """Persist config to JSON."""
    data = {}
    for fld in fields(AppConfig):
        value = getattr(cfg, fld.name)
        if _is_path_field(fld.name) and isinstance(value, str):
            value = _normalize_path(value)
            setattr(cfg, fld.name, value)
        data[fld.name] = value
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass
