"""
phases/phase23/slide_updater.py
Business-logic layer for Phase 2+3.  Combines core.image_processor and
core.pptx_engine into the operations the QA controller actually needs:
roster loading, draft generation, single-slide re-injection, and preview
cropping.  No tkinter imports — fully unit-testable.
"""
from __future__ import annotations
from typing import Callable, Optional
from PIL import Image

from core.image_processor import ImageProcessor
from core.pptx_engine import PPTXEngine


class SlideUpdater:
    """Stateless orchestration wrapper — construct once and reuse."""

    def __init__(self, config_manager) -> None:
        self.cfg = config_manager
        self.image_processor = ImageProcessor()
        self.pptx_engine     = PPTXEngine(self.image_processor, config_manager)

    # ── Roster ────────────────────────────────────────────────────────────────

    def load_students_from_excel(self, excel_path: str, master_dir: str) -> list[dict]:
        layout = self.cfg.load_layout_config()
        return self.pptx_engine.load_students_from_excel(excel_path, master_dir, layout)

    # ── Draft generation ──────────────────────────────────────────────────────

    def generate_draft(
        self,
        students:      list[dict],
        template_path: str,
        output_path:   str,
        on_progress:   Optional[Callable[[int, int], None]] = None,
    ) -> list[dict]:
        layout = self.cfg.load_layout_config()
        fd_cfg = layout.get("face_detection", {})
        return self.pptx_engine.generate_draft(
            students, template_path, output_path, layout, fd_cfg, on_progress
        )

    # ── Preview ───────────────────────────────────────────────────────────────

    def crop_preview(
        self,
        image_path: str,
        manual_face_center: Optional[tuple] = None,
        preview_size: tuple = (280, 380),
    ) -> Image.Image:
        layout = self.cfg.load_layout_config()
        ratio  = layout["portrait"]["width_cm"] / layout["portrait"]["height_cm"]
        fd_cfg = layout.get("face_detection", {})
        return self.image_processor.get_preview_pil(
            image_path, ratio, fd_cfg, manual_face_center, preview_size
        )

    def get_original_resized(self, image_path: str, max_size: tuple = (380, 500)):
        return self.image_processor.get_original_resized(image_path, max_size)

    def target_ratio(self) -> float:
        p = self.cfg.load_layout_config()["portrait"]
        return p["width_cm"] / p["height_cm"]

    # ── Re-injection ──────────────────────────────────────────────────────────

    def reinject_portrait(
        self,
        pptx_path:          str,
        slide_index:        int,
        portrait_shape_id:  int,
        image_path:         str,
        manual_face_center: Optional[tuple],
    ) -> int:
        """
        Crops image_path according to manual_face_center (or auto-detects if
        None), surgically replaces the portrait shape in pptx_path, and
        returns the new shape_id.
        """
        layout = self.cfg.load_layout_config()
        ratio  = layout["portrait"]["width_cm"] / layout["portrait"]["height_cm"]
        fd_cfg = layout.get("face_detection", {})

        stream = self.image_processor.crop_to_stream(
            image_path, ratio, fd_cfg, manual_face_center
        )
        return self.pptx_engine.reinject_image(
            pptx_path, slide_index, portrait_shape_id, stream, layout
        )
