"""
phases/phase23/crop_editor.py
Phase 2+3 — Manual Crop & Tilt Editor.

A self-contained Toplevel that lets the operator interactively rotate and
crop a single student's portrait: draggable/resizable crop box (locked to
the configured portrait aspect ratio), rotation slider, zoom slider, a
live preview pane, and Reset/Cancel/Apply actions.

This module owns NO metadata access and NO PPTX mutation. On Apply it
calls ImageProcessor.crop_with_params() to produce the final image stream,
then hands (crop_params, stream) back to the caller via the on_apply
callback — the caller (QASuiteFrame) is responsible for injecting the
stream via _apply_corrected_image() and persisting crop_params through
MetadataService, per the existing architecture.

All coordinate math (drag / resize / zoom / rotation-rescale) lives in
small @staticmethod helpers with no tkinter dependency, so it can be
unit-tested in isolation.
"""
from __future__ import annotations

import io
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from PIL import Image, ImageTk

from ui.widgets import APP_BG, CARD_BG, CANVAS_BG, SUB_FG
from ui.dialogs import show_error


class CropEditorWindow(tk.Toplevel):
    """
    Usage::
        CropEditorWindow(
            parent,
            image_path=..., target_ratio=...,
            image_processor=slide_updater.image_processor,
            fd_config=layout["face_detection"],
            initial_crop_params=saved_params,   # or None
            auto_face_center=student.get("manual_face_center"),
            student_label="DELA CRUZ, Juan",
            on_apply=lambda crop_params, stream: ...,
        )
    """

    CANVAS_W, CANVAS_H = 480, 620
    HANDLE_SIZE         = 9
    MIN_RECT_PX         = 40   # minimum crop rect width, in working-image pixels

    def __init__(
        self,
        parent: tk.Widget,
        image_path: str,
        target_ratio: float,
        image_processor,
        fd_config: dict,
        on_apply: Callable[[dict, "io.BytesIO"], None],
        initial_crop_params: Optional[dict] = None,
        auto_face_center: Optional[tuple] = None,
        student_label: str = "",
    ) -> None:
        super().__init__(parent)
        self.title(
            f"✏️  Manual Crop & Tilt Editor — {student_label}"
            if student_label else "✏️  Manual Crop & Tilt Editor"
        )
        self.configure(bg=APP_BG)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._image_path      = image_path
        self._target_ratio    = target_ratio
        self._ip               = image_processor
        self._fd_config        = fd_config
        self._on_apply         = on_apply
        self._auto_face_center = auto_face_center

        self._orig_pil    = self._ip.load_working_image(image_path, target_ratio)
        self._rotation    = 0.0
        self._zoom        = 1.0
        self._drag_mode: Optional[str] = None
        self._drag_start  = (0.0, 0.0)
        self._rect_at_drag_start = (0.0, 0.0, 0.0, 0.0)

        if initial_crop_params:
            self._rotation     = float(initial_crop_params.get("rotation", 0.0) or 0.0)
            self._working_pil  = self._rotate_image(self._orig_pil, self._rotation)
            iw, ih = self._working_pil.size
            self._base_rect = self.clamp_rect(
                float(initial_crop_params.get("x", 0)),
                float(initial_crop_params.get("y", 0)),
                float(initial_crop_params.get("w", iw)),
                float(initial_crop_params.get("h", ih)),
                iw, ih,
            )
        else:
            self._working_pil = self._orig_pil
            iw, ih = self._working_pil.size
            min_frac = fd_config.get("min_crop_fraction", 0.55)
            self._base_rect = self.initial_rect(iw, ih, target_ratio, auto_face_center, min_frac)

        self._rect = self._base_rect
        self._canvas_scale  = 1.0
        self._canvas_offset = (0, 0)

        self._build_ui()
        self._redraw_canvas_image()
        self._draw_rect()
        self._update_preview()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        main = tk.Frame(self, bg=APP_BG)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        left = tk.Frame(main, bg=APP_BG)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        tk.Label(
            left,
            text="Drag the box to move it, or drag a handle to resize.\n"
                 "Aspect ratio is locked to the slide's portrait ratio.",
            font=("Segoe UI", 9, "italic"), fg=SUB_FG, bg=APP_BG, justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 4))

        self.canvas = tk.Canvas(
            left, bg=CANVAS_BG, width=self.CANVAS_W, height=self.CANVAS_H,
            highlightthickness=0, cursor="fleur",
        )
        self.canvas.pack()
        self.canvas.bind("<ButtonPress-1>",   self._on_press)
        self.canvas.bind("<B1-Motion>",       self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        right = tk.Frame(main, bg=APP_BG, width=270)
        right.pack(side=tk.LEFT, fill=tk.Y)
        right.pack_propagate(False)

        tk.Label(right, text="Live Preview  (PPTX result)",
                 font=("Segoe UI", 10, "bold"), bg=APP_BG, fg="#2c3e50").pack(anchor="w")
        preview_card = tk.Frame(right, bg=CARD_BG, highlightbackground="#dde3ea", highlightthickness=1)
        preview_card.pack(fill=tk.X, pady=(2, 12))
        self._preview_lbl = tk.Label(
            preview_card, bg=CANVAS_BG, width=26, height=15,
            text="Loading…", fg="#aab", font=("Segoe UI", 10),
        )
        self._preview_lbl.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        tk.Label(right, text="Rotation", font=("Segoe UI", 10, "bold"),
                 bg=APP_BG, fg="#2c3e50").pack(anchor="w")
        self._rot_var = tk.DoubleVar(value=self._rotation)
        ttk.Scale(right, from_=-15, to=15, variable=self._rot_var,
                  command=self._on_rotation_change).pack(fill=tk.X)
        self._rot_lbl = tk.Label(right, text=f"{self._rotation:+.1f}°",
                                 font=("Segoe UI", 9), bg=APP_BG, fg=SUB_FG)
        self._rot_lbl.pack(anchor="e")

        tk.Label(right, text="Zoom", font=("Segoe UI", 10, "bold"),
                 bg=APP_BG, fg="#2c3e50").pack(anchor="w", pady=(10, 0))
        self._zoom_var = tk.DoubleVar(value=self._zoom)
        ttk.Scale(right, from_=0.5, to=2.0, variable=self._zoom_var,
                  command=self._on_zoom_change).pack(fill=tk.X)
        self._zoom_lbl = tk.Label(right, text=f"{self._zoom:.2f}×",
                                  font=("Segoe UI", 9), bg=APP_BG, fg=SUB_FG)
        self._zoom_lbl.pack(anchor="e")

        btns = tk.Frame(right, bg=APP_BG)
        btns.pack(fill=tk.X, side=tk.BOTTOM, pady=(16, 0))
        ttk.Button(btns, text="🔁  Reset to Auto", command=self._reset_to_auto).pack(fill=tk.X, pady=2)
        ttk.Button(btns, text="✖  Cancel", command=self.destroy).pack(fill=tk.X, pady=2)
        ttk.Button(btns, text="⚡  Apply & Re-Inject", style="Accent.TButton",
                   command=self._on_apply_clicked).pack(fill=tk.X, pady=2)

    # ── Rotation / zoom callbacks ─────────────────────────────────────────────

    def _rotate_image(self, pil_img: Image.Image, degrees: float) -> Image.Image:
        if not degrees:
            return pil_img
        return pil_img.rotate(-degrees, resample=Image.BICUBIC, expand=True, fillcolor=(255, 255, 255))

    def _on_rotation_change(self, _val) -> None:
        self._rotation = float(self._rot_var.get())
        self._rot_lbl.configure(text=f"{self._rotation:+.1f}°")

        old_iw, old_ih = self._working_pil.size
        self._working_pil = self._rotate_image(self._orig_pil, self._rotation)
        new_iw, new_ih = self._working_pil.size

        sx, sy = new_iw / old_iw, new_ih / old_ih
        x, y, w, h = self._rect
        self._rect = self.clamp_rect(x * sx, y * sy, w * sx, h * sy, new_iw, new_ih)
        self._base_rect = self._rect

        self._redraw_canvas_image()
        self._draw_rect()
        self._update_preview()

    def _on_zoom_change(self, _val) -> None:
        self._zoom = float(self._zoom_var.get())
        self._zoom_lbl.configure(text=f"{self._zoom:.2f}×")
        iw, ih = self._working_pil.size
        self._rect = self.apply_zoom(self._base_rect, self._zoom, iw, ih, self._target_ratio)
        self._draw_rect()
        self._update_preview()

    def _reset_to_auto(self) -> None:
        self._rotation = 0.0
        self._rot_var.set(0.0)
        self._rot_lbl.configure(text="+0.0°")
        self._zoom = 1.0
        self._zoom_var.set(1.0)
        self._zoom_lbl.configure(text="1.00×")

        self._working_pil = self._orig_pil
        iw, ih = self._working_pil.size
        min_frac = self._fd_config.get("min_crop_fraction", 0.55)
        self._base_rect = self.initial_rect(iw, ih, self._target_ratio, self._auto_face_center, min_frac)
        self._rect = self._base_rect

        self._redraw_canvas_image()
        self._draw_rect()
        self._update_preview()

    # ── Canvas rendering ──────────────────────────────────────────────────────

    def _redraw_canvas_image(self) -> None:
        self.canvas.delete("img")
        iw, ih = self._working_pil.size
        cw, ch = self.CANVAS_W, self.CANVAS_H
        scale  = min(cw / iw, ch / ih, 1.0)
        disp_w, disp_h = max(1, int(iw * scale)), max(1, int(ih * scale))
        off_x, off_y   = (cw - disp_w) // 2, (ch - disp_h) // 2

        self._canvas_scale, self._canvas_offset = scale, (off_x, off_y)
        disp_img = self._working_pil.resize((disp_w, disp_h), Image.LANCZOS)
        self._canvas_photo = ImageTk.PhotoImage(disp_img)
        self.canvas.create_image(off_x, off_y, image=self._canvas_photo, anchor="nw", tags="img")

    def _draw_rect(self) -> None:
        self.canvas.delete("rectbox")
        x, y, w, h = self._rect
        x0, y0 = self._image_to_canvas(x, y)
        x1, y1 = self._image_to_canvas(x + w, y + h)
        self.canvas.create_rectangle(x0, y0, x1, y1, outline="#ff3333", width=2, tags="rectbox")

        handles = {
            "nw": (x0, y0), "ne": (x1, y0), "sw": (x0, y1), "se": (x1, y1),
            "n": ((x0 + x1) / 2, y0), "s": ((x0 + x1) / 2, y1),
            "e": (x1, (y0 + y1) / 2), "w": (x0, (y0 + y1) / 2),
        }
        s = self.HANDLE_SIZE / 2
        for hx, hy in handles.values():
            self.canvas.create_rectangle(
                hx - s, hy - s, hx + s, hy + s,
                fill="#ff3333", outline="white", tags="rectbox",
            )

    def _update_preview(self) -> None:
        x, y, w, h = [int(v) for v in self._rect]
        try:
            crop = self._working_pil.crop((x, y, x + w, y + h))
            crop.thumbnail((260, 350), Image.LANCZOS)
            self._preview_photo = ImageTk.PhotoImage(crop)
            self._preview_lbl.configure(image=self._preview_photo, text="")
        except Exception:
            self._preview_lbl.configure(image="", text="Preview unavailable")

    # ── Coordinate transforms ─────────────────────────────────────────────────

    def _image_to_canvas(self, x: float, y: float) -> tuple[float, float]:
        ox, oy = self._canvas_offset
        s = self._canvas_scale
        return ox + x * s, oy + y * s

    def _canvas_to_image(self, cx: float, cy: float) -> tuple[float, float]:
        ox, oy = self._canvas_offset
        s = self._canvas_scale or 1.0
        return (cx - ox) / s, (cy - oy) / s

    @staticmethod
    def _corner_point(rect, corner: str) -> tuple[float, float]:
        x, y, w, h = rect
        return {"nw": (x, y), "ne": (x + w, y), "sw": (x, y + h), "se": (x + w, y + h)}[corner]

    @staticmethod
    def _edge_point(rect, edge: str) -> tuple[float, float]:
        x, y, w, h = rect
        return {
            "n": (x + w / 2, y), "s": (x + w / 2, y + h),
            "e": (x + w, y + h / 2), "w": (x, y + h / 2),
        }[edge]

    def _hit_test(self, ix: float, iy: float) -> Optional[str]:
        x, y, w, h = self._rect
        tol = self.HANDLE_SIZE / max(self._canvas_scale, 1e-6)
        points = {
            "nw": (x, y), "ne": (x + w, y), "sw": (x, y + h), "se": (x + w, y + h),
            "n": (x + w / 2, y), "s": (x + w / 2, y + h),
            "e": (x + w, y + h / 2), "w": (x, y + h / 2),
        }
        for name, (hx, hy) in points.items():
            if abs(ix - hx) <= tol and abs(iy - hy) <= tol:
                return name
        if x <= ix <= x + w and y <= iy <= y + h:
            return "move"
        return None

    # ── Mouse handlers ────────────────────────────────────────────────────────

    def _on_press(self, event) -> None:
        ix, iy = self._canvas_to_image(event.x, event.y)
        self._drag_mode = self._hit_test(ix, iy)
        self._drag_start = (ix, iy)
        self._rect_at_drag_start = self._rect

    def _on_drag(self, event) -> None:
        if not self._drag_mode:
            return
        ix, iy = self._canvas_to_image(event.x, event.y)
        x0, y0 = self._drag_start
        dx, dy = ix - x0, iy - y0
        iw, ih = self._working_pil.size

        if self._drag_mode == "move":
            self._rect = self.move_rect(self._rect_at_drag_start, dx, dy, iw, ih)
        elif self._drag_mode in ("nw", "ne", "sw", "se"):
            cx, cy = self._corner_point(self._rect_at_drag_start, self._drag_mode)
            self._rect = self.resize_from_corner(
                self._rect_at_drag_start, self._drag_mode, cx + dx, cy + dy,
                self._target_ratio, iw, ih, self.MIN_RECT_PX,
            )
        elif self._drag_mode in ("n", "s", "e", "w"):
            ex, ey = self._edge_point(self._rect_at_drag_start, self._drag_mode)
            self._rect = self.resize_from_edge(
                self._rect_at_drag_start, self._drag_mode, ex + dx, ey + dy,
                self._target_ratio, iw, ih, self.MIN_RECT_PX,
            )

        self._draw_rect()
        self._update_preview()

    def _on_release(self, _event) -> None:
        if self._drag_mode:
            # Any manual interaction re-baselines the zoom slider to 1.0 —
            # it now zooms relative to whatever rect the operator just set.
            self._base_rect = self._rect
            self._zoom = 1.0
            self._zoom_var.set(1.0)
            self._zoom_lbl.configure(text="1.00×")
        self._drag_mode = None

    # ── Apply / cancel ────────────────────────────────────────────────────────

    def _on_apply_clicked(self) -> None:
        x, y, w, h = self._rect
        crop_params = {"x": x, "y": y, "w": w, "h": h, "rotation": self._rotation}
        try:
            stream = self._ip.crop_with_params(
                self._image_path, crop_params, self._target_ratio, self._fd_config
            )
        except Exception as exc:
            show_error("Crop Error", str(exc))
            return
        self._on_apply(crop_params, stream)
        self.destroy()

    # ── Pure geometry helpers (no tkinter — unit-testable) ────────────────────

    @staticmethod
    def clamp_rect(x, y, w, h, img_w, img_h, min_w=10, min_h=10):
        """Clamps a rect fully inside the image, sliding before trimming."""
        w = max(min_w, min(w, img_w))
        h = max(min_h, min(h, img_h))
        x = max(0, min(x, img_w - w))
        y = max(0, min(y, img_h - h))
        return x, y, w, h

    @staticmethod
    def initial_rect(img_w, img_h, target_ratio, face_center=None, size_fraction=0.55):
        """
        Starting crop box: centred on the auto face-detection centre (or the
        image centre if none), sized as a reasonable fraction of image
        height — reuses the Chunk 3 min_crop_fraction as a sensible default
        starting framing, ratio-locked and clamped to the image.
        """
        h = img_h * size_fraction
        w = h * target_ratio
        if w > img_w:
            w = img_w
            h = w / target_ratio
        cx, cy = face_center if face_center else (img_w / 2, img_h / 2)
        x, y = cx - w / 2, cy - h / 2
        return CropEditorWindow.clamp_rect(x, y, w, h, img_w, img_h)

    @staticmethod
    def apply_zoom(base_rect, zoom, img_w, img_h, target_ratio):
        """Scales base_rect by zoom around its own centre, ratio-locked."""
        bx, by, bw, bh = base_rect
        cx, cy = bx + bw / 2, by + bh / 2
        w = bw * zoom
        h = w / target_ratio
        x, y = cx - w / 2, cy - h / 2
        return CropEditorWindow.clamp_rect(x, y, w, h, img_w, img_h)

    @staticmethod
    def resize_from_corner(rect, corner, new_x, new_y, target_ratio, img_w, img_h, min_size=20):
        """Resizes anchored at the OPPOSITE corner, preserving aspect ratio."""
        x, y, w, h = rect
        anchors = {"nw": (x + w, y + h), "ne": (x, y + h), "sw": (x + w, y), "se": (x, y)}
        ax, ay = anchors[corner]
        dir_x = 1 if new_x >= ax else -1
        dir_y = 1 if new_y >= ay else -1
        new_w = max(min_size, abs(new_x - ax))
        new_h = new_w / target_ratio
        rx = ax if dir_x > 0 else ax - new_w
        ry = ay if dir_y > 0 else ay - new_h
        return CropEditorWindow.clamp_rect(rx, ry, new_w, new_h, img_w, img_h, min_size, min_size / target_ratio)

    @staticmethod
    def resize_from_edge(rect, edge, new_x, new_y, target_ratio, img_w, img_h, min_size=20):
        """
        Resizes one dimension from the dragged edge; the other dimension
        follows via the locked aspect ratio, anchored at the opposite edge
        and centred on the perpendicular axis.
        """
        x, y, w, h = rect
        cx, cy = x + w / 2, y + h / 2
        if edge == "e":
            new_w = max(min_size, new_x - x); new_h = new_w / target_ratio
            rx, ry = x, cy - new_h / 2
        elif edge == "w":
            new_w = max(min_size, (x + w) - new_x); new_h = new_w / target_ratio
            rx, ry = (x + w) - new_w, cy - new_h / 2
        elif edge == "s":
            new_h = max(min_size / target_ratio, new_y - y); new_w = new_h * target_ratio
            rx, ry = cx - new_w / 2, y
        else:  # "n"
            new_h = max(min_size / target_ratio, (y + h) - new_y); new_w = new_h * target_ratio
            rx, ry = cx - new_w / 2, (y + h) - new_h
        return CropEditorWindow.clamp_rect(rx, ry, new_w, new_h, img_w, img_h, min_size, min_size / target_ratio)

    @staticmethod
    def move_rect(rect, dx, dy, img_w, img_h):
        """Translates rect by (dx, dy), clamped to the image bounds."""
        x, y, w, h = rect
        return CropEditorWindow.clamp_rect(x + dx, y + dy, w, h, img_w, img_h)
