Do the same here
Here is the original code:
"""
phases/phase23/qa_controller.py
Phase 2+3 — Slide Generator & Live QA Suite (orchestrator).

This module contains NO business logic and NO direct image/pptx
manipulation.  It only:
  • Wires Toolbar + PreviewPanel callbacks to SlideUpdater / MetadataService calls.
  • Holds the in-memory student list and "current selection" cursor.
  • Runs the draft-generation worker on a background thread.

Class name QASuiteFrame is preserved for backward compatibility with
the phase registry in main.py.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from ui.widgets import APP_BG, SUB_FG, make_header_bar
from ui.dialogs import pick_file, pick_dir, pick_save_file, show_error, show_info, show_warning

from phases.phase23.toolbar import Toolbar
from phases.phase23.preview_panel import PreviewPanel
from phases.phase23.slide_updater import SlideUpdater
from phases.phase23.metadata_service import MetadataService


class QASuiteFrame(ttk.Frame):
    """Phase 2+3 content pane — generation hub and live QA remote control."""

    def __init__(self, parent: tk.Widget, app) -> None:
        super().__init__(parent)
        self.app = app

        self.slide_updater  = SlideUpdater(app.config_manager)
        self.metadata_service = MetadataService(app.metadata_manager)

        # ── runtime state ────────────────────────────────────────────────────
        self._students:       list[dict]   = []
        self._current_idx:    int          = -1
        self._pending_center: tuple | None = None

        self._status_var = tk.StringVar(value="Set file paths, then click 'Load Students'.")

        self._build_ui()
        self._restore_session()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        make_header_bar(self, "🎬  Phase 2+3 — Slide Generator & Live QA Suite")

        self.toolbar = Toolbar(
            self,
            on_browse_excel=self._browse_excel,
            on_browse_template=self._browse_template,
            on_browse_master=self._browse_master,
            on_set_output=self._set_output,
            on_load_students=self._load_students,
            on_generate=self._on_generate,
            on_open_output_folder=self._on_open_output_folder,
        )
        self.toolbar.pack(fill=tk.X)

        self.preview = PreviewPanel(
            self,
            on_select=self._on_tree_select,
            on_canvas_click=self._on_canvas_click,
            on_apply=self._on_apply_override,
            on_clear=self._on_clear_override,
            on_prev=self._prev_student,
            on_next=self._next_student,
        )
        self.preview.pack(fill=tk.BOTH, expand=True)

        sb = tk.Frame(self, bg="#dde3ea", pady=3)
        sb.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Label(sb, textvariable=self._status_var,
                  background="#dde3ea", foreground=SUB_FG).pack(side=tk.LEFT, padx=12)

    # ── Path dialogs ──────────────────────────────────────────────────────────

    def _browse_excel(self) -> None:
        p = pick_file("Select Excel roster", [("Excel", "*.xlsx *.xls")])
        if p:
            self.toolbar.excel_var.set(p)
            self.metadata_service.update_session(excel_path=p)

    def _browse_template(self) -> None:
        p = pick_file("Select PPTX template", [("PowerPoint", "*.pptx")])
        if p:
            self.toolbar.template_var.set(p)
            self.metadata_service.update_session(template_path=p)

    def _browse_master(self) -> None:
        p = pick_dir("Select Master portraits directory")
        if p:
            self.toolbar.master_var.set(p)
            self.metadata_service.update_session(master_dir=p)

    def _set_output(self) -> None:
        p = pick_save_file("Save output PPTX as…", ".pptx", [("PowerPoint", "*.pptx")])
        if p:
            self.toolbar.output_var.set(p)
            self.metadata_service.update_session(output_pptx_path=p)

    # ── Session restore ───────────────────────────────────────────────────────

    def _restore_session(self) -> None:
        s = self.metadata_service.get_session()
        self.toolbar.set_paths(
            s.get("excel_path", ""), s.get("template_path", ""),
            s.get("master_dir", ""), s.get("output_pptx_path", ""),
        )

        saved = self.metadata_service.get_students()
        if saved:
            self.metadata_service.ensure_student_ids(saved)
            self.metadata_service.ensure_default_status(saved)
            self._students = saved
            self.metadata_service.save_students(self._students)
            self._rebuild_tree()
            self.toolbar.set_generate_enabled(True)
            self._status_var.set(f"Restored {len(self._students)} students from previous session.")
        self._update_review_stats()

    # ── Student loading ───────────────────────────────────────────────────────

    def _load_students(self) -> None:
        paths = self.toolbar.get_paths()
        if not paths["excel"]:
            show_error("Missing path", "Please select an Excel file.")
            return
        try:
            self._students = self.slide_updater.load_students_from_excel(
                paths["excel"], paths["master"]
            )
            self.metadata_service.ensure_student_ids(self._students)
            self.metadata_service.ensure_default_status(self._students)
            self.metadata_service.save_students(self._students)
            self._rebuild_tree()
            self.toolbar.set_generate_enabled(bool(self._students))
            self._status_var.set(f"Loaded {len(self._students)} students.")
            self._update_review_stats()
        except Exception as exc:
            show_error("Load Error", str(exc))

    # ── Tree management ───────────────────────────────────────────────────────

    def _rebuild_tree(self) -> None:
        self.preview.rebuild_tree(self._students, self._row_values)

    def _refresh_tree_row(self, idx: int) -> None:
        self.preview.refresh_row(idx, self._students[idx], self._row_values)

    def _row_values(self, s: dict) -> tuple:
        icon   = self.metadata_service.status_icon(s.get("status", "pending"))
        name   = f"{s['surname']}, {s['firstname']}"
        course = s["course"][:16] + "…" if len(s["course"]) > 16 else s["course"]
        return (icon, name, course)

    def _update_review_stats(self) -> None:
        """Pulls the latest status breakdown from disk and pushes it to the toolbar."""
        stats = self.metadata_service.get_review_statistics()
        self.toolbar.set_review_stats(
            stats.get("reviewed", 0), stats.get("total", 0), stats.get("failed", 0)
        )

    # ── Draft generation (threaded) ──────────────────────────────────────────

    def _on_generate(self) -> None:
        if not self._students:
            show_error("Nothing to do", "Load students first.")
            return
        paths = self.toolbar.get_paths()
        for key, label in [(paths["template"], "Template PPTX"), (paths["output"], "Output PPTX")]:
            if not key:
                show_error("Missing path", f"Please set {label} path.")
                return

        self.toolbar.set_generate_enabled(False)
        self._status_var.set("Generating draft PPTX…  Do not close the application.")

        def worker() -> None:
            try:
                def progress(current: int, total: int) -> None:
                    pct = current / total * 100
                    self.after(0, lambda: self.toolbar.set_progress(pct))
                    self.after(0, lambda: self.toolbar.set_progress_label(f"{current}/{total}"))

                updated = self.slide_updater.generate_draft(
                    self._students, paths["template"], paths["output"], progress
                )
                ts = self.metadata_service.now_iso()
                for s in updated:
                    s["pptx_path"]    = paths["output"]
                    s["last_updated"] = ts
                self._students = updated
                self.metadata_service.save_students(self._students)
                self.after(0, self._on_generate_done)
            except Exception as exc:
                self.after(0, lambda: show_error("Generation Error", str(exc)))
                self.after(0, lambda: self.toolbar.set_generate_enabled(True))

        threading.Thread(target=worker, daemon=True).start()

    def _on_generate_done(self) -> None:
        self._rebuild_tree()
        self.toolbar.set_generate_enabled(True)
        self.toolbar.set_progress(100)
        output = self.toolbar.get_paths()["output"]
        self._status_var.set(
            f"✅ PPTX is live at:\n{output}\n\n"
            f"Every override performed in Phase 23 updates this file directly."
        )
        self._update_review_stats()
        show_info("Done", f"Draft PPTX generated successfully!\n{output}")

    # ── Selection & navigation ────────────────────────────────────────────────

    def _on_tree_select(self) -> None:
        idx = self.preview.get_selected_index()
        if idx is None:
            return
        self._current_idx    = idx
        self._pending_center = None
        self._refresh_preview()

    def _prev_student(self) -> None:
        if self._current_idx > 0:
            self._jump_to(self._current_idx - 1)

    def _next_student(self) -> None:
        if self._current_idx < len(self._students) - 1:
            self._jump_to(self._current_idx + 1)

    def _jump_to(self, idx: int) -> None:
        self._current_idx    = idx
        self._pending_center = None
        self.preview.select_index(idx)
        self._refresh_preview()

    # ── Preview rendering ─────────────────────────────────────────────────────

    def _refresh_preview(self) -> None:
        if not (0 <= self._current_idx < len(self._students)):
            return

        s      = self._students[self._current_idx]
        center = self._pending_center or s.get("manual_face_center")

        try:
            pil = self.slide_updater.crop_preview(s["image_path"], center, (280, 380))
            self.preview.set_preview_image(pil)
        except Exception as exc:
            self.preview.set_preview_image(None, f"Preview error:\n{exc}")

        self.preview.render_original(s["image_path"], center)

        self.preview.set_info_text(
            f"{s['surname']}, {s['firstname']}  |  Slide {s.get('slide_index', '?')}  "
            f"|  {s.get('status', 'pending').upper()}"
        )
        self.preview.set_face_label(center)
        self._sync_button_states(s)

    # ── Canvas click → manual override ───────────────────────────────────────

    def _on_canvas_click(self, orig_x: int, orig_y: int) -> None:
        if self._current_idx < 0:
            return
        self._pending_center = (orig_x, orig_y)

        s = self._students[self._current_idx]
        try:
            pil = self.slide_updater.crop_preview(s["image_path"], self._pending_center, (280, 380))
            self.preview.set_preview_image(pil)
        except Exception:
            pass

        self.preview.set_face_label(self._pending_center, pending=True)
        self._sync_button_states(s)
        self._status_var.set(
            f"Face centre set at ({orig_x}, {orig_y}) — click 'Apply Override' to commit."
        )

    # ── Reusable override-application orchestrator ───────────────────────────

    def _apply_corrected_image(self, image_stream, new_status: str = "overridden") -> bool:
        """
        Applies image_stream as the new portrait for the currently selected
        student. Returns True on success, False if check fails or update errors.
        This is the method the upcoming crop/tilt editor will call.
        """
        if self._current_idx < 0:
            return False
        s = self._students[self._current_idx]
        if not self._check_pptx_ready(s):
            return False
        
        s["pptx_path"] = self.toolbar.get_paths()["output"]
        try:
            new_shape_id = self.slide_updater.update_student_slide(s, image_stream)
        except Exception as exc:
            show_error("Slide Update Failed", str(exc))
            return False
        
        s["portrait_shape_id"] = new_shape_id
        s["status"]            = new_status
        self.metadata_service.save_students(self._students)
        
        if s.get("student_id"):
            self.metadata_service.set_slide_info(s["student_id"], s["slide_index"], s["pptx_path"])
        
        self._refresh_tree_row(self._current_idx)
        self._refresh_preview()
        self._update_review_stats()
        return True

    # ── Override apply / clear ───────────────────────────────────────────────

    def _on_apply_override(self) -> None:
        if self._current_idx < 0 or self._pending_center is None:
            return
        s = self._students[self._current_idx]
        if not self._check_pptx_ready(s):
            return

        try:
            new_id = self.slide_updater.reinject_portrait(
                self.toolbar.get_paths()["output"],
                s["slide_index"], s["portrait_shape_id"],
                s["image_path"], self._pending_center,
            )
            s["manual_face_center"] = self._pending_center
            s["portrait_shape_id"]  = new_id
            s["status"]             = "overridden"
            self._pending_center    = None

            self.metadata_service.save_students(self._students)
            if s.get("student_id"):
                self.metadata_service.set_slide_info(
                    s["student_id"], s["slide_index"], self.toolbar.get_paths()["output"]
                )
            self._refresh_tree_row(self._current_idx)
            self._refresh_preview()
            self._update_review_stats()
            self._status_var.set(f"⚡  Override applied for {s['surname']}, {s['firstname']}.")
        except Exception as exc:
            show_error("Re-injection Error", str(exc))

    def _on_clear_override(self) -> None:
        if self._current_idx < 0:
            return
        s = self._students[self._current_idx]
        if not s.get("manual_face_center"):
            return
        if not self._check_pptx_ready(s):
            return

        try:
            new_id = self.slide_updater.reinject_portrait(
                self.toolbar.get_paths()["output"],
                s["slide_index"], s["portrait_shape_id"],
                s["image_path"], None,
            )
            s["manual_face_center"] = None
            s["portrait_shape_id"]  = new_id
            s["status"]             = "generated"

            self.metadata_service.save_students(self._students)
            if s.get("student_id"):
                self.metadata_service.set_slide_info(
                    s["student_id"], s["slide_index"], self.toolbar.get_paths()["output"]
                )
            self._refresh_tree_row(self._current_idx)
            self._refresh_preview()
            self._update_review_stats()
            self._status_var.set(f"🔄  Auto-crop restored for {s['surname']}, {s['firstname']}.")
        except Exception as exc:
            show_error("Clear Override Error", str(exc))

    # ── UI state helpers ──────────────────────────────────────────────────────

    def _check_pptx_ready(self, s: dict) -> bool:
        output = self.toolbar.get_paths()["output"]
        if not output or not Path(output).exists():
            show_error("PPTX not found", "Generate the draft PPTX first, or re-select the output path.")
            return False
        if s.get("slide_index", -1) < 0:
            show_error("No slide index", "This student has no assigned slide.  Generate the draft first.")
            return False
        return True

    def _sync_button_states(self, s: dict) -> None:
        output   = self.toolbar.get_paths()["output"]
        pptx_ok  = bool(output) and Path(output).exists()
        slide_ok = s.get("slide_index", -1) >= 0

        self.preview.set_apply_enabled(self._pending_center is not None and pptx_ok and slide_ok)
        self.preview.set_clear_enabled(bool(s.get("manual_face_center")) and pptx_ok and slide_ok)

    # ── Open Output Folder ────────────────────────────────────────────────────

    def _on_open_output_folder(self) -> None:
        output = self.toolbar.get_paths()["output"]
        if not output or not Path(output).exists():
            show_warning(
                "No PPTX Found",
                "No PowerPoint file has been generated yet.\n"
                "Generate the draft PPTX first, then try again."
            )
            return

        folder = Path(output).parent
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(folder))          # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception as exc:
            show_error("Could Not Open Folder", str(exc))
            
What needs to be implemented:
phases/phase23/qa_controller.py
New import:
pythonfrom PIL import Image
from phases.phase23.crop_editor import CropEditorWindow
_build_ui — wire the new callback:
python        self.preview = PreviewPanel(
            self,
            on_select=self._on_tree_select,
            on_canvas_click=self._on_canvas_click,
            on_apply=self._on_apply_override,
            on_clear=self._on_clear_override,
            on_prev=self._prev_student,
            on_next=self._next_student,
            on_crop_editor=self._open_crop_editor,
        )
New method — opens the editor:
python    def _open_crop_editor(self) -> None:
        if self._current_idx < 0:
            show_error("No Selection", "Select a student first.")
            return
        s = self._students[self._current_idx]

        layout       = self.slide_updater.cfg.load_layout_config()
        target_ratio = layout["portrait"]["width_cm"] / layout["portrait"]["height_cm"]
        fd_config    = layout.get("face_detection", {})

        saved_params = None
        if s.get("student_id"):
            saved_params = self.metadata_service.get_crop_params(s["student_id"])
        if not saved_params:
            saved_params = s.get("crop_params")   # in-memory fallback, not yet persisted

        CropEditorWindow(
            self,
            image_path=s["image_path"],
            target_ratio=target_ratio,
            image_processor=self.slide_updater.image_processor,
            fd_config=fd_config,
            initial_crop_params=saved_params,
            auto_face_center=s.get("manual_face_center"),
            student_label=f"{s['surname']}, {s['firstname']}",
            on_apply=self._on_crop_editor_apply,
        )
New method — receives the result:
python    def _on_crop_editor_apply(self, crop_params: dict, image_stream) -> None:
        if self._current_idx < 0:
            return
        s = self._students[self._current_idx]

        if not self._apply_corrected_image(image_stream, new_status="overridden"):
            return

        s["crop_params"] = crop_params
        if s.get("student_id"):
            self.metadata_service.set_crop_params(s["student_id"], crop_params)

        self._pending_center = None
        self._status_var.set(f"✏️  Manual crop applied for {s['surname']}, {s['firstname']}.")
Refactored — _on_apply_override (removes duplicated orchestration, delegates to _apply_corrected_image):
python    def _on_apply_override(self) -> None:
        if self._current_idx < 0 or self._pending_center is None:
            return
        s = self._students[self._current_idx]
        if not self._check_pptx_ready(s):
            return

        layout = self.slide_updater.cfg.load_layout_config()
        ratio  = layout["portrait"]["width_cm"] / layout["portrait"]["height_cm"]
        fd_cfg = layout.get("face_detection", {})

        try:
            stream = self.slide_updater.image_processor.crop_to_stream(
                s["image_path"], ratio, fd_cfg, self._pending_center
            )
        except Exception as exc:
            show_error("Crop Error", str(exc))
            return

        s["manual_face_center"] = self._pending_center
        s["crop_params"]        = None   # face-click override supersedes any saved manual crop
        self._pending_center    = None

        if not self._apply_corrected_image(stream, new_status="overridden"):
            return
        if s.get("student_id"):
            self.metadata_service.set_crop_params(s["student_id"], None)
        self._status_var.set(f"⚡  Override applied for {s['surname']}, {s['firstname']}.")
Refactored — _on_clear_override:
python    def _on_clear_override(self) -> None:
        if self._current_idx < 0:
            return
        s = self._students[self._current_idx]
        if not s.get("manual_face_center"):
            return
        if not self._check_pptx_ready(s):
            return

        layout = self.slide_updater.cfg.load_layout_config()
        ratio  = layout["portrait"]["width_cm"] / layout["portrait"]["height_cm"]
        fd_cfg = layout.get("face_detection", {})

        try:
            stream = self.slide_updater.image_processor.crop_to_stream(
                s["image_path"], ratio, fd_cfg, None
            )
        except Exception as exc:
            show_error("Crop Error", str(exc))
            return

        s["manual_face_center"] = None

        if not self._apply_corrected_image(stream, new_status="generated"):
            return
        self._status_var.set(f"🔄  Auto-crop restored for {s['surname']}, {s['firstname']}.")
New helper + updated _refresh_preview (crop_params take display precedence unless a face-click override is actively in progress):
python    def _get_preview_image(self, s: dict, center):
        if s.get("crop_params") and self._pending_center is None:
            layout = self.slide_updater.cfg.load_layout_config()
            ratio  = layout["portrait"]["width_cm"] / layout["portrait"]["height_cm"]
            fd_cfg = layout.get("face_detection", {})
            stream = self.slide_updater.image_processor.crop_with_params(
                s["image_path"], s["crop_params"], ratio, fd_cfg
            )
            img = Image.open(stream).convert("RGB")
            img.thumbnail((280, 380), Image.LANCZOS)
            return img
        return self.slide_updater.crop_preview(s["image_path"], center, (280, 380))

    def _refresh_preview(self) -> None:
        if not (0 <= self._current_idx < len(self._students)):
            return

        s      = self._students[self._current_idx]
        center = self._pending_center or s.get("manual_face_center")

        try:
            pil = self._get_preview_image(s, center)
            self.preview.set_preview_image(pil)
        except Exception as exc:
            self.preview.set_preview_image(None, f"Preview error:\n{exc}")

        self.preview.render_original(s["image_path"], center)

        self.preview.set_info_text(
            f"{s['surname']}, {s['firstname']}  |  Slide {s.get('slide_index', '?')}  "
            f"|  {s.get('status', 'pending').upper()}"
        )
        self.preview.set_face_label(center)
        self._sync_button_states(s)
_sync_button_states — gate the new button like the others:
python    def _sync_button_states(self, s: dict) -> None:
        output   = self.toolbar.get_paths()["output"]
        pptx_ok  = bool(output) and Path(output).exists()
        slide_ok = s.get("slide_index", -1) >= 0

        self.preview.set_apply_enabled(self._pending_center is not None and pptx_ok and slide_ok)
        self.preview.set_clear_enabled(bool(s.get("manual_face_center")) and pptx_ok and slide_ok)
        self.preview.set_crop_editor_enabled(True)
(Crop editor stays enabled whenever a student is selected — _sync_button_states is only ever called with a valid s, unlike Apply/Clear it doesn't require a generated PPTX to open, only to apply, matching _open_crop_editor's own guard.)
Everything else in qa_controller.py (_load_students, _on_generate*, _on_canvas_click, _check_pptx_ready, _apply_corrected_image, session/path handling) is unchanged.