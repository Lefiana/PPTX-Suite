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

        self.slide_updater   = SlideUpdater(app.config_manager)
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
            self._students = saved
            self._rebuild_tree()
            self.toolbar.set_generate_enabled(True)
            self._status_var.set(f"Restored {len(self._students)} students from previous session.")

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
            self.metadata_service.save_students(self._students)
            self._rebuild_tree()
            self.toolbar.set_generate_enabled(bool(self._students))
            self._status_var.set(f"Loaded {len(self._students)} students.")
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
        self._status_var.set(f"✅  Draft PPTX saved to: {output}")
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
            self._refresh_tree_row(self._current_idx)
            self._refresh_preview()
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
            self._refresh_tree_row(self._current_idx)
            self._refresh_preview()
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
