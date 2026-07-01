"""
core/config_manager.py
Responsible for one file only: layout_config.json.
Metadata (session paths, student state) lives in core/metadata_manager.py.
"""
from __future__ import annotations
import json
from pathlib import Path

DEFAULT_LAYOUT_CONFIG: dict = {
    "portrait": {
        "left_cm":   29.79,
        "top_cm":    2.58,
        "width_cm":  17.27,
        "height_cm": 23.43,
    },
    "shapes": {
        "surname":   "TextBox 6",
        "firstname": "TextBox 7",
        "course":    "TextBox 8",
    },
    "excel": {
        "header_row":     3,
        "name_column":    "STUDENT NAME",
        "program_column": "PROGRAM",
    },
    "face_detection": {
        "top_padding_factor":    0.70,
        "bottom_padding_factor": 2.80,
        "min_face_fraction":     0.08,
        "max_face_fraction":     0.80,
        "horizontal_margin":     0.15,
        "vertical_limit":        0.60,
        "min_crop_fraction":     0.55,
    },
    "program_mapping": {
        "BMMA":   "Bachelor of Multimedia Arts",
        "BSA":    "Bachelor of Science in Accountancy",
        "BSCS":   "Bachelor of Science in Computer Science",
        "BSIT":   "Bachelor of Science in Information Technology",
        "BSBA":   "Bachelor of Science in Business Administration",
        "BSED":   "Bachelor of Secondary Education",
        "BEED":   "Bachelor of Elementary Education",
        "BSCRIM": "Bachelor of Science in Criminology",
        "BSN":    "Bachelor of Science in Nursing",
        "BSME":   "Bachelor of Science in Marine Engineering",
    },
}


class ConfigManager:
    """Read/write interface for layout_config.json."""

    def __init__(self, path: str | Path = "config/layout_config.json") -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self.save_layout_config(DEFAULT_LAYOUT_CONFIG)

    # ── I/O ──────────────────────────────────────────────────────────────────

    def load_layout_config(self) -> dict:
        with open(self._path, "r", encoding="utf-8") as fh:
            data: dict = json.load(fh)
        return self._merge_defaults(data, DEFAULT_LAYOUT_CONFIG)

    @staticmethod
    def _merge_defaults(data: dict, defaults: dict) -> dict:
        """
        Recursively fills any key missing from *data* using *defaults*,
        without ever overwriting a value the user (or a prior config file)
        already set. Handles nested dicts (e.g. face_detection.*) so old
        config files transparently gain new sub-fields like min_crop_fraction.
        """
        for key, val in defaults.items():
            if key not in data:
                data[key] = val
            elif isinstance(val, dict) and isinstance(data[key], dict):
                ConfigManager._merge_defaults(data[key], val)
        return data

    def save_layout_config(self, config: dict) -> None:
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(config, fh, indent=2, ensure_ascii=False)

    # ── Flat ↔ nested helpers (used by calibration_ui) ───────────────────────

    @staticmethod
    def flatten(config: dict, prefix: str = "") -> dict:
        """{"portrait": {"left_cm": 1}} → {"portrait.left_cm": 1}"""
        result: dict = {}
        for key, value in config.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                result.update(ConfigManager.flatten(value, full_key))
            else:
                result[full_key] = value
        return result

    @staticmethod
    def unflatten(flat: dict) -> dict:
        """{"portrait.left_cm": 1} → {"portrait": {"left_cm": 1}}"""
        result: dict = {}
        for key, value in flat.items():
            parts = key.split(".")
            d = result
            for part in parts[:-1]:
                d = d.setdefault(part, {})
            d[parts[-1]] = value
        return result