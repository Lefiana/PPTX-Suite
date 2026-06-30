"""
core/metadata_manager.py
Responsible for one file only: data/metadata.json.
Stores session-level paths and per-student processing state.
Layout / UI configuration lives in core/config_manager.py.
"""
from __future__ import annotations
import json
from pathlib import Path

DEFAULT_METADATA: dict = {
    "session": {
        "excel_path":       "",
        "template_path":    "",
        "output_pptx_path": "",
        "master_dir":       "",
        "source_dir":       "",
        "dest_dir":         "",
    },
    "students": [],
}


class MetadataManager:
    """Read/write interface for data/metadata.json."""

    def __init__(self, path: str | Path = "data/metadata.json") -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self.save_metadata(DEFAULT_METADATA)

    # ── Full document ─────────────────────────────────────────────────────────

    def load_metadata(self) -> dict:
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            data.setdefault("session", {})
            data.setdefault("students", [])
            return data
        except (json.JSONDecodeError, FileNotFoundError):
            return dict(DEFAULT_METADATA)

    def save_metadata(self, metadata: dict) -> None:
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(metadata, fh, indent=2, ensure_ascii=False)

    # ── Session helpers ───────────────────────────────────────────────────────

    def get_session(self) -> dict:
        return self.load_metadata().get("session", {})

    def update_session(self, **kwargs) -> None:
        meta = self.load_metadata()
        meta.setdefault("session", {}).update(kwargs)
        self.save_metadata(meta)

    # ── Student helpers ───────────────────────────────────────────────────────

    def get_students(self) -> list:
        return self.load_metadata().get("students", [])

    def save_students(self, students: list) -> None:
        meta = self.load_metadata()
        meta["students"] = students
        self.save_metadata(meta)

    def update_student(self, idx: int, **kwargs) -> None:
        """Patch a single student record in-place by list index."""
        meta = self.load_metadata()
        if 0 <= idx < len(meta.get("students", [])):
            meta["students"][idx].update(kwargs)
            self.save_metadata(meta)
