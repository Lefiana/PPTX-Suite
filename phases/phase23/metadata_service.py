"""
phases/phase23/metadata_service.py
Phase 2+3 specific metadata semantics, layered on top of the generic
core.metadata_manager.MetadataManager.

Owns:
  • Status vocabulary (pending / generated / overridden / placeholder /
    failed / skipped) and their tree-view colour + icon mapping.
  • Convenience accessors for the QA workflow's session keys.
  • Student-ID assignment and ID-based lookup/update helpers.
  • Review statistics aggregation for the toolbar counters.
  • Persistent slide/pptx association management.

All reads/writes to metadata.json happen exclusively through this module
(via the injected MetadataManager) — no other Phase 2+3 module touches
metadata.json directly.
"""
from __future__ import annotations
import re
from datetime import datetime
from typing import Optional

# Status → (tree-tag colour, unicode icon)
STATUS_META: dict[str, tuple[str, str]] = {
    "pending":     ("#95a5a6", "⬜"),
    "generated":   ("#27ae60", "✅"),
    "overridden":  ("#e67e22", "⚡"),
    "placeholder": ("#e74c3c", "⚠️"),
    "failed":      ("#c0392b", "❌"),
    "skipped":     ("#7f8c8d", "⏭"),
}

# Statuses that count as "reviewed" for the toolbar counter
REVIEWED_STATUSES = ("generated", "overridden", "placeholder")

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

    # ── Student-ID assignment ─────────────────────────────────────────────────

    @staticmethod
    def _slugify(text: str) -> str:
        """Uppercase, alnum-and-underscore only, collapsed whitespace."""
        t = re.sub(r"[^\w\s]", "", str(text)).strip().upper()
        return re.sub(r"\s+", "_", t) or "UNKNOWN"

    @classmethod
    def compute_student_id(cls, student: dict) -> str:
        """
        Deterministic, unique ID built from surname + firstname + the
        student's original Excel row index (always present and unique
        per roster, so no collisions even for identical names).
        """
        surname   = cls._slugify(student.get("surname", ""))
        firstname = cls._slugify(student.get("firstname", ""))
        idx       = student.get("excel_index", "0")
        return f"{surname}_{firstname}_{idx}"

    @classmethod
    def ensure_student_ids(cls, students: list[dict]) -> list[dict]:
        """Populates student_id on any record missing one. Mutates in place."""
        for s in students:
            if not s.get("student_id"):
                s["student_id"] = cls.compute_student_id(s)
        return students

    @staticmethod
    def ensure_default_status(students: list[dict]) -> list[dict]:
        """Defensively sets status='pending' wherever missing. Mutates in place."""
        for s in students:
            s.setdefault("status", "pending")
        return students

    # ── ID-based lookup / update (disk-backed) ───────────────────────────────

    def get_student(self, student_id: str) -> Optional[dict]:
        for s in self._mm.get_students():
            if s.get("student_id") == student_id:
                return s
        return None

    def update_student(self, student_id: str, updates: dict) -> bool:
        """Finds the student by ID on disk, applies updates, saves. Returns success."""
        students = self._mm.get_students()
        for s in students:
            if s.get("student_id") == student_id:
                s.update(updates)
                self._mm.save_students(students)
                return True
        return False

    def set_status(self, student_id: str, status: str) -> bool:
        return self.update_student(student_id, {"status": status})

    # ── Slide mapping (persistent student → slide/pptx association) ─────────
    #
    # These accessors read/write the same flat fields already present on
    # every student record (slide_index, pptx_path, last_updated) via the
    # ID-based get_student/update_student methods above — no separate
    # sub-object, no duplicated storage.

    @staticmethod
    def now_iso() -> str:
        """Single source of truth for the timestamp format used across this service."""
        return datetime.now().isoformat(timespec="seconds")

    def get_slide_info(self, student_id: str) -> Optional[dict]:
        """Returns {'slide_index', 'pptx_path', 'last_updated'} for a student, or None."""
        s = self.get_student(student_id)
        if s is None:
            return None
        return {
            "slide_index":  s.get("slide_index", -1),
            "pptx_path":    s.get("pptx_path", ""),
            "last_updated": s.get("last_updated"),
        }

    def set_slide_info(self, student_id: str, slide_index: int, pptx_path: str) -> bool:
        """Persists slide_index + pptx_path for a student and stamps last_updated."""
        return self.update_student(student_id, {
            "slide_index":  slide_index,
            "pptx_path":    pptx_path,
            "last_updated": self.now_iso(),
        })

    def update_last_updated(self, student_id: str) -> bool:
        """Stamps last_updated to now without touching any other field."""
        return self.update_student(student_id, {"last_updated": self.now_iso()})

    # ── Review statistics ─────────────────────────────────────────────────────

    def get_review_statistics(self) -> dict:
        """
        Reads the current on-disk student list and returns a full status
        breakdown:  {reviewed, total, failed, skipped, pending,
                      generated, overridden, placeholder}
        """
        students = self._mm.get_students()
        total    = len(students)
        counts   = {status: 0 for status in STATUS_META}
        for s in students:
            status = s.get("status", "pending")
            counts[status] = counts.get(status, 0) + 1

        reviewed = sum(counts.get(st, 0) for st in REVIEWED_STATUSES)
        return {
            "reviewed": reviewed,
            "total":    total,
            **counts,
        }