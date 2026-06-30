"""
phases/phase23/metadata_service.py
Phase 2+3 specific metadata semantics, layered on top of the generic
core.metadata_manager.MetadataManager.

Owns:
  • Status vocabulary (pending / generated / overridden / placeholder / error)
    and their tree-view colour + icon mapping.
  • Convenience accessors for the QA workflow's session keys.
  • Per-student patch helper that writes straight through to disk.
"""
from __future__ import annotations
from typing import Optional

# Status → (tree-tag colour, unicode icon)
STATUS_META: dict[str, tuple[str, str]] = {
    "pending":     ("#95a5a6", "⬜"),
    "generated":   ("#27ae60", "✅"),
    "overridden":  ("#e67e22", "⚡"),
    "placeholder": ("#e74c3c", "⚠️"),
    "error":       ("#c0392b", "❌"),
}

# Session keys this phase reads/writes
SESSION_KEYS = ("excel_path", "template_path", "output_pptx_path", "master_dir")


class MetadataService:
    """Thin façade restricted to what the QA controller needs."""

    def __init__(self, metadata_manager) -> None:
        self._mm = metadata_manager

    # ── Session ───────────────────────────────────────────────────────────────

    def get_session(self) -> dict:
        return self._mm.get_session()

    def update_session(self, **kwargs) -> None:
        self._mm.update_session(**kwargs)

    # ── Students ──────────────────────────────────────────────────────────────

    def get_students(self) -> list[dict]:
        return self._mm.get_students()

    def save_students(self, students: list[dict]) -> None:
        self._mm.save_students(students)

    def patch_student(self, idx: int, **kwargs) -> None:
        self._mm.update_student(idx, **kwargs)

    # ── Status helpers ────────────────────────────────────────────────────────

    @staticmethod
    def status_icon(status: str) -> str:
        return STATUS_META.get(status, ("", "⬜"))[1]

    @staticmethod
    def status_colour(status: str) -> str:
        return STATUS_META.get(status, ("#95a5a6", ""))[0]

    @staticmethod
    def all_statuses() -> list[str]:
        return list(STATUS_META.keys())

    @staticmethod
    def reviewed_count(students: list[dict]) -> tuple[int, int]:
        """Returns (reviewed, total) where 'reviewed' = any status != pending."""
        total    = len(students)
        reviewed = sum(1 for s in students if s.get("status", "pending") != "pending")
        return reviewed, total
