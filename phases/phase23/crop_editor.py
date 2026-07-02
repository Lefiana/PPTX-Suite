"""
phases/phase23/crop_editor.py
Phase 2+3 — Manual Crop & Tilt Editor.

A self-contained Toplevel that lets the operator interactively rotate and
crop a single student's portrait: draggable/resizable crop box (locked to
the configured portrait aspect ratio), a PowerPoint-style rotation handle,
a zoom slider, a live preview pane, and Reset/Cancel/Apply actions.

Rendering model (Chunk A)
--------------------------
The canvas always displays the ORIGINAL (unrotated) image — it never needs
to be redrawn when rotation changes, which keeps dragging smooth. The crop
rectangle is stored, exactly as before, as an axis-aligned box (x, y, w, h)
in "rotated-space" — the coordinate system of image.rotate(-rotation,
expand=True), which is precisely what ImageProcessor.crop_with_params()
uses. This keeps crop_params (and therefore metadata.json / backward
compatibility) completely unchanged.

To draw that box (and its handles, guide line, and rotation handle) as a
genuinely rotated selection on top of the fixed, unrotated canvas image, a
small forward/inverse coordinate transform layer (to_rotated_space /
to_original_space / rotated_canvas_size) maps between the two coordinate
systems. All the existing rotated-space geometry helpers (clamp_rect,
initial_rect, apply_zoom, resize_from_corner, resize_from_edge, move_rect)
are reused completely unchanged — mouse events are converted into
rotated-space before being handed to them, exactly mirroring how they
already worked when the canvas itself displayed the rotated image.

This module owns NO metadata access and NO PPTX mutation. On Apply it
calls ImageProcessor.crop_with_params() to produce the final image stream,
then hands (crop_params, stream) back to the caller via the on_apply
callback — the caller (QASuiteFrame) is responsible for injecting the
stream via _apply_corrected_image() and persisting crop_params through
MetadataService, per the existing architecture.
"""
from __future__ import annotations

import io
import math
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
    MIN_RECT_PX         = 40    # minimum crop rect width, in rotated-space pixels
    HANDLE_OFFSET       = 36    # rotation-handle distance above the top edge, in rotated-space px
    ROTATION_MIN        = -15.0
    ROTATION_MAX        = 15.0
    ROTATION_SNAP_DEG   = 5.0
    PREVIEW_MAX_DIM     = 500   # live-preview working image is downscaled for smooth dragging

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

        self._orig_pil = self._ip.load_working_image(image_path, target_ratio)
        ow, oh = self._orig_pil.size
        self._build_preview_base()

        self._rotation = 0.0
        self._zoom     = 1.0
        self._drag_mode: Optional[str] = None
        self._drag_start = (0.0, 0.0)
        self._rect_at_drag_start = (0.0, 0.0, 0.0, 0.0)
        self._rotate_pivot_orig  = (0.0, 0.0)
        self._rotate_wh          = (0.0, 0.0)

        if initial_crop_params:
            self._rotation = float(initial_crop_params.get("rotation", 0.0) or 0.0)
            rw, rh = self.rotated_canvas_size(ow, oh, self._rotation)
            self._base_rect = self.clamp_rect(
                float(initial_crop_params.get("x", 0)),
                float(initial_crop_params.get("y", 0)),
                float(initial_crop_params.get("w", rw)),
                float(initial_crop_params.get("h", rh)),
                rw, rh,
            )
        else:
            min_frac = fd_config.get("min_crop_fraction", 0.55)
            self._base_rect = self.initial_rect(ow, oh, target_ratio, auto_face_center, min_frac)

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
            text="Drag the box to move it, or a red handle to resize.\n"
                 "Drag the green handle above the box to rotate — hold Shift "
                 "to free-rotate, double-click it to reset to 0°.",
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
        self.canvas.bind("<Double-Button-1>", self._on_double_click)

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
        self._rot_lbl = tk.Label(right, text=f"{self._rotation:+.1f}°",
                                 font=("Segoe UI", 14, "bold"), bg=APP_BG, fg="#27ae60")
        self._rot_lbl.pack(anchor="w")
        tk.Label(right, text="(drag the green handle on the canvas)",
                 font=("Segoe UI", 8, "italic"), bg=APP_BG, fg=SUB_FG).pack(anchor="w", pady=(0, 10))

        tk.Label(right, text="Zoom", font=("Segoe UI", 10, "bold"),
                 bg=APP_BG, fg="#2c3e50").pack(anchor="w")
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

    # ── Zoom / reset ──────────────────────────────────────────────────────────

    def _on_zoom_change(self, _val) -> None:
        self._zoom = float(self._zoom_var.get())
        self._zoom_lbl.configure(text=f"{self._zoom:.2f}×")
        ow, oh = self._orig_pil.size
        rot_w, rot_h = self.rotated_canvas_size(ow, oh, self._rotation)
        self._rect = self.apply_zoom(self._base_rect, self._zoom, rot_w, rot_h, self._target_ratio)
        self._draw_rect()
        self._update_preview()

    def _reset_to_auto(self) -> None:
        self._rotation = 0.0
        self._zoom     = 1.0
        self._zoom_var.set(1.0)
        self._zoom_lbl.configure(text="1.00×")
        self._rot_lbl.configure(text="+0.0°")

        ow, oh = self._orig_pil.size
        min_frac = self._fd_config.get("min_crop_fraction", 0.55)
        self._base_rect = self.initial_rect(ow, oh, self._target_ratio, self._auto_face_center, min_frac)
        self._rect = self._base_rect

        self._draw_rect()
        self._update_preview()

    # ── Canvas rendering ──────────────────────────────────────────────────────
    # The background image is drawn exactly once — it never needs to change
    # with rotation, since rotation is now expressed purely as a transform
    # applied to the rectangle/handles, not to the displayed image.

    def _redraw_canvas_image(self) -> None:
        self.canvas.delete("img")
        iw, ih = self._orig_pil.size
        cw, ch = self.CANVAS_W, self.CANVAS_H
        scale  = min(cw / iw, ch / ih, 1.0)
        disp_w, disp_h = max(1, int(iw * scale)), max(1, int(ih * scale))
        off_x, off_y   = (cw - disp_w) // 2, (ch - disp_h) // 2

        self._canvas_scale, self._canvas_offset = scale, (off_x, off_y)
        disp_img = self._orig_pil.resize((disp_w, disp_h), Image.LANCZOS)
        self._canvas_photo = ImageTk.PhotoImage(disp_img)
        self.canvas.create_image(off_x, off_y, image=self._canvas_photo, anchor="nw", tags="img")

    def _rect_corners_original(self) -> list[tuple[float, float]]:
        x, y, w, h = self._rect
        ow, oh = self._orig_pil.size
        rot = self._rotation
        pts_rot = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        return [self.to_original_space(px, py, ow, oh, rot) for px, py in pts_rot]

    def _handle_points_original(self) -> dict[str, tuple[float, float]]:
        x, y, w, h = self._rect
        ow, oh = self._orig_pil.size
        rot = self._rotation
        rotated_pts = {
            "nw": (x, y), "ne": (x + w, y), "sw": (x, y + h), "se": (x + w, y + h),
            "n": (x + w / 2, y), "s": (x + w / 2, y + h),
            "e": (x + w, y + h / 2), "w": (x, y + h / 2),
            "rotate": self._rotation_handle_point(self._rect, self.HANDLE_OFFSET),
        }
        return {name: self.to_original_space(px, py, ow, oh, rot) for name, (px, py) in rotated_pts.items()}

    def _draw_rect(self) -> None:
        self.canvas.delete("rectbox")

        corners_canvas = [self._image_to_canvas(px, py) for px, py in self._rect_corners_original()]
        flat = [c for pt in corners_canvas for c in pt]
        self.canvas.create_polygon(*flat, outline="#ff3333", fill="", width=2, tags="rectbox")

        handles_orig = self._handle_points_original()
        top_mid_canvas = self._image_to_canvas(*handles_orig["n"])
        rotate_canvas  = self._image_to_canvas(*handles_orig["rotate"])
        self.canvas.create_line(*top_mid_canvas, *rotate_canvas, fill="#ffffff", width=1, tags="rectbox")

        s = self.HANDLE_SIZE / 2
        for name, (hx, hy) in handles_orig.items():
            cx, cy = self._image_to_canvas(hx, hy)
            if name == "rotate":
                self.canvas.create_oval(cx - s - 1, cy - s - 1, cx + s + 1, cy + s + 1,
                                        fill="#27ae60", outline="white", width=1, tags="rectbox")
            else:
                self.canvas.create_rectangle(cx - s, cy - s, cx + s, cy + s,
                                             fill="#ff3333", outline="white", tags="rectbox")

        if self._drag_mode == "rotate":
            rx, ry = rotate_canvas
            self.canvas.create_text(
                rx, ry - 16, text=f"{self._rotation:+.1f}°",
                fill="#ffffff", font=("Segoe UI", 9, "bold"), tags="rectbox",
            )

    def _build_preview_base(self) -> None:
        """A downscaled copy of the original used for fast, continuous live
        previews while dragging — the authoritative, full-quality output is
        always produced by crop_with_params() at Apply time."""
        ow, oh = self._orig_pil.size
        k = min(1.0, self.PREVIEW_MAX_DIM / max(ow, oh))
        self._preview_scale = k
        if k < 1.0:
            self._preview_base = self._orig_pil.resize(
                (max(1, round(ow * k)), max(1, round(oh * k))), Image.BILINEAR
            )
        else:
            self._preview_base = self._orig_pil

    def _update_preview(self) -> None:
        try:
            k = self._preview_scale
            working = self._preview_base
            if self._rotation:
                working = working.rotate(
                    -self._rotation, resample=Image.BILINEAR, expand=True, fillcolor=(255, 255, 255)
                )
            ww, wh = working.size
            x, y, w, h = self._rect
            rx, ry = int(x * k), int(y * k)
            rw, rh = max(1, int(w * k)), max(1, int(h * k))
            rx = max(0, min(rx, ww - 1))
            ry = max(0, min(ry, wh - 1))
            rw = max(1, min(rw, ww - rx))
            rh = max(1, min(rh, wh - ry))

            crop = working.crop((rx, ry, rx + rw, ry + rh))
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

    @staticmethod
    def _rotation_handle_point(rect, offset: float) -> tuple[float, float]:
        x, y, w, h = rect
        return x + w / 2, y - offset

    def _hit_test(self, rix: float, riy: float) -> Optional[str]:
        """rix, riy must already be in ROTATED-space coordinates."""
        x, y, w, h = self._rect
        tol = self.HANDLE_SIZE / max(self._canvas_scale, 1e-6)
        rotate_tol = (self.HANDLE_SIZE + 3) / max(self._canvas_scale, 1e-6)
        points = {
            "rotate": self._rotation_handle_point(self._rect, self.HANDLE_OFFSET),
            "nw": (x, y), "ne": (x + w, y), "sw": (x, y + h), "se": (x + w, y + h),
            "n": (x + w / 2, y), "s": (x + w / 2, y + h),
            "e": (x + w, y + h / 2), "w": (x, y + h / 2),
        }
        for name, (hx, hy) in points.items():
            t = rotate_tol if name == "rotate" else tol
            if abs(rix - hx) <= t and abs(riy - hy) <= t:
                return name
        if x <= rix <= x + w and y <= riy <= y + h:
            return "move"
        return None

    # ── Mouse handlers ────────────────────────────────────────────────────────

    def _on_press(self, event) -> None:
        ow, oh = self._orig_pil.size
        ix, iy = self._canvas_to_image(event.x, event.y)
        rix, riy = self.to_rotated_space(ix, iy, ow, oh, self._rotation)

        self._drag_mode = self._hit_test(rix, riy)
        self._drag_start = (rix, riy)
        self._rect_at_drag_start = self._rect

        if self._drag_mode == "rotate":
            x, y, w, h = self._rect
            cx_rot, cy_rot = x + w / 2, y + h / 2
            self._rotate_pivot_orig = self.to_original_space(cx_rot, cy_rot, ow, oh, self._rotation)
            self._rotate_wh = (w, h)

    def _on_drag(self, event) -> None:
        if not self._drag_mode:
            return
        ow, oh = self._orig_pil.size

        if self._drag_mode == "rotate":
            self._drag_rotate(event, ow, oh)
            return

        ix, iy = self._canvas_to_image(event.x, event.y)
        rix, riy = self.to_rotated_space(ix, iy, ow, oh, self._rotation)
        x0, y0 = self._drag_start
        dx, dy = rix - x0, riy - y0
        rot_w, rot_h = self.rotated_canvas_size(ow, oh, self._rotation)

        if self._drag_mode == "move":
            self._rect = self.move_rect(self._rect_at_drag_start, dx, dy, rot_w, rot_h)
        elif self._drag_mode in ("nw", "ne", "sw", "se"):
            cx, cy = self._corner_point(self._rect_at_drag_start, self._drag_mode)
            self._rect = self.resize_from_corner(
                self._rect_at_drag_start, self._drag_mode, cx + dx, cy + dy,
                self._target_ratio, rot_w, rot_h, self.MIN_RECT_PX,
            )
        elif self._drag_mode in ("n", "s", "e", "w"):
            ex, ey = self._edge_point(self._rect_at_drag_start, self._drag_mode)
            self._rect = self.resize_from_edge(
                self._rect_at_drag_start, self._drag_mode, ex + dx, ey + dy,
                self._target_ratio, rot_w, rot_h, self.MIN_RECT_PX,
            )
        else:
            return

        self._draw_rect()
        self._update_preview()

    def _drag_rotate(self, event, ow: float, oh: float) -> None:
        ix, iy = self._canvas_to_image(event.x, event.y)
        pcx, pcy = self._rotate_pivot_orig

        mouse_angle = math.degrees(math.atan2(iy - pcy, ix - pcx))
        raw = -mouse_angle - 90.0
        raw = ((raw + 180.0) % 360.0) - 180.0   # normalize to [-180, 180)

        shift_held = bool(event.state & 0x0001)
        new_rotation = raw if shift_held else round(raw / self.ROTATION_SNAP_DEG) * self.ROTATION_SNAP_DEG
        new_rotation = max(self.ROTATION_MIN, min(self.ROTATION_MAX, new_rotation))

        self._rotation = new_rotation
        w, h = self._rotate_wh
        new_cx_rot, new_cy_rot = self.to_rotated_space(pcx, pcy, ow, oh, new_rotation)
        nw, nh = self.rotated_canvas_size(ow, oh, new_rotation)
        self._rect = self.clamp_rect(new_cx_rot - w / 2, new_cy_rot - h / 2, w, h, nw, nh)
        self._base_rect = self._rect

        self._rot_lbl.configure(text=f"{self._rotation:+.1f}°")
        self._draw_rect()
        self._update_preview()

    def _on_release(self, _event) -> None:
        resized_or_moved = self._drag_mode in ("move", "nw", "ne", "sw", "se", "n", "s", "e", "w")
        self._drag_mode = None
        if resized_or_moved:
            # Any manual move/resize re-baselines the zoom slider to 1.0 —
            # it now zooms relative to whatever rect the operator just set.
            self._base_rect = self._rect
            self._zoom = 1.0
            self._zoom_var.set(1.0)
            self._zoom_lbl.configure(text="1.00×")
        self._draw_rect()   # also clears the floating drag-angle label

    def _on_double_click(self, event) -> None:
        ow, oh = self._orig_pil.size
        ix, iy = self._canvas_to_image(event.x, event.y)
        rix, riy = self.to_rotated_space(ix, iy, ow, oh, self._rotation)
        if self._hit_test(rix, riy) != "rotate":
            return

        x, y, w, h = self._rect
        cx_rot, cy_rot = x + w / 2, y + h / 2
        pivot_orig = self.to_original_space(cx_rot, cy_rot, ow, oh, self._rotation)

        self._rotation = 0.0
        new_cx_rot, new_cy_rot = self.to_rotated_space(pivot_orig[0], pivot_orig[1], ow, oh, 0.0)
        nw, nh = self.rotated_canvas_size(ow, oh, 0.0)
        self._rect = self.clamp_rect(new_cx_rot - w / 2, new_cy_rot - h / 2, w, h, nw, nh)
        self._base_rect = self._rect

        self._rot_lbl.configure(text="+0.0°")
        self._draw_rect()
        self._update_preview()

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

    # ── Coordinate-space transform layer (no tkinter — unit-testable) ─────────
    # Mirrors exactly what ImageProcessor.crop_with_params() does internally
    # (working = original.rotate(-rotation, expand=True)), so rect
    # coordinates edited here remain valid crop_params for that pipeline.

    @staticmethod
    def rotated_canvas_size(ow: float, oh: float, rotation_deg: float) -> tuple[float, float]:
        a = math.radians(rotation_deg)
        cos_a, sin_a = abs(math.cos(a)), abs(math.sin(a))
        return ow * cos_a + oh * sin_a, oh * cos_a + ow * sin_a

    @staticmethod
    def to_rotated_space(px: float, py: float, ow: float, oh: float, rotation_deg: float) -> tuple[float, float]:
        a = math.radians(rotation_deg)
        cox, coy = ow / 2, oh / 2
        nw, nh = CropEditorWindow.rotated_canvas_size(ow, oh, rotation_deg)
        cnx, cny = nw / 2, nh / 2
        dx, dy = px - cox, py - coy
        rx = dx * math.cos(a) - dy * math.sin(a)
        ry = dx * math.sin(a) + dy * math.cos(a)
        return rx + cnx, ry + cny

    @staticmethod
    def to_original_space(rx: float, ry: float, ow: float, oh: float, rotation_deg: float) -> tuple[float, float]:
        a = math.radians(rotation_deg)
        cox, coy = ow / 2, oh / 2
        nw, nh = CropEditorWindow.rotated_canvas_size(ow, oh, rotation_deg)
        cnx, cny = nw / 2, nh / 2
        dx, dy = rx - cnx, ry - cny
        ox = dx * math.cos(a) + dy * math.sin(a)
        oy = -dx * math.sin(a) + dy * math.cos(a)
        return ox + cox, oy + coy

    # ── Pure rotated-space geometry helpers (unchanged from Chunk 4 — reused
    #    verbatim, zero duplication) ────────────────────────────────────────

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
        """Starting crop box: centred on the auto face-detection centre (or
        the image centre), sized as a fraction of image height, ratio-locked
        and clamped to the image."""
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