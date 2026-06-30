"""
phases/phase23/preview_panel.py
Main work area for Phase 2+3: the student queue treeview, the cropped
portrait preview, the clickable original-image canvas, and the action
button bar (Apply / Clear / Prev / Next).

Pure UI widget — all coordinate-geometry (canvas click → original pixel)
lives here since it's a rendering concern.  Business decisions (what to
do with a click) are delegated to the controller via callbacks.
"""
from __future__ import annotations
import tkinter as tk
from typing import Callable, Optional
from tkinter import ttk

from PIL import Image, ImageOps, ImageTk

from phases.phase23.metadata_service import STATUS_META

APP_BG    = "#f0f2f5"
CARD_BG   = "#ffffff"
SUB_FG    = "#555e6d"
CANVAS_BG = "#2c3e50"

ORIG_W, ORIG_H = 340, 450   # click-canvas dimensions


class PreviewPanel(tk.Frame):
    """
    Usage::
        panel = PreviewPanel(
            parent,
            on_select=..., on_canvas_click=...,
            on_apply=..., on_clear=..., on_prev=..., on_next=...,
        )
        panel.pack(fill=tk.BOTH, expand=True)
        panel.rebuild_tree(students, row_values_fn)
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_select:       Callable[[], None],
        on_canvas_click: Callable[[int, int], None],   # (orig_x, orig_y)
        on_apply:        Callable[[], None],
        on_clear:        Callable[[], None],
        on_prev:         Callable[[], None],
        on_next:         Callable[[], None],
    ) -> None:
        super().__init__(parent, bg=APP_BG)

        self._on_select       = on_select
        self._on_canvas_click = on_canvas_click

        # Geometry state for click → original-pixel transform
        self._orig_img_size  = (1, 1)
        self._canvas_scale   = 1.0
        self._canvas_offset  = (0, 0)

        # Keep PhotoImage references alive
        self._preview_photo: Optional[ImageTk.PhotoImage] = None
        self._orig_photo:    Optional[ImageTk.PhotoImage] = None

        self._build_student_list()
        self._build_right_panel(on_apply, on_clear, on_prev, on_next)

    # ── Construction ──────────────────────────────────────────────────────────

    def _build_student_list(self) -> None:
        frm = tk.Frame(self, bg=APP_BG, width=295)
        frm.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 4), pady=10)
        frm.pack_propagate(False)

        tk.Label(frm, text="Student Queue", font=("Segoe UI", 11, "bold"),
                bg=APP_BG, fg="#2c3e50").pack(anchor="w", pady=(0, 4))

        cols = ("st", "name", "course")
        self.tree = ttk.Treeview(frm, columns=cols, show="headings",
                                 selectmode="browse", height=30)
        self.tree.heading("st", text=""); self.tree.heading("name", text="Name")
        self.tree.heading("course", text="Course")
        self.tree.column("st", width=30, stretch=False, anchor="center")
        self.tree.column("name", width=170, stretch=False)
        self.tree.column("course", width=80, stretch=True)

        vsb = ttk.Scrollbar(frm, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        for tag, (colour, _icon) in STATUS_META.items():
            self.tree.tag_configure(tag, foreground=colour)

        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._on_select())

    def _build_right_panel(self, on_apply, on_clear, on_prev, on_next) -> None:
        right = tk.Frame(self, bg=APP_BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 10), pady=10)

        panels = tk.Frame(right, bg=APP_BG)
        panels.pack(fill=tk.BOTH, expand=True)

        self._build_preview_panel(panels)
        self._build_click_panel(panels)
        self._build_action_bar(right, on_apply, on_clear, on_prev, on_next)

    def _build_preview_panel(self, parent: tk.Frame) -> None:
        card = ttk.LabelFrame(parent, text="🖼  Cropped Portrait Preview  (PPTX result)", padding=8)
        card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        self._preview_lbl = tk.Label(card, bg=CANVAS_BG,
                                     text="Select a student\nto preview",
                                     fg="#aab", font=("Segoe UI", 11))
        self._preview_lbl.pack(fill=tk.BOTH, expand=True)

        self.info_var = tk.StringVar()
        tk.Label(card, textvariable=self.info_var, font=("Segoe UI", 9),
                bg=APP_BG, fg=SUB_FG, justify=tk.CENTER).pack(pady=(4, 0))

    def _build_click_panel(self, parent: tk.Frame) -> None:
        card = ttk.LabelFrame(parent,
                              text="🎯  Click Face Centre on Original Image  (for manual override)",
                              padding=8)
        card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        self.orig_canvas = tk.Canvas(
            card, bg=CANVAS_BG, cursor="crosshair",
            width=ORIG_W, height=ORIG_H, highlightthickness=0,
        )
        self.orig_canvas.pack(fill=tk.BOTH, expand=True)
        self.orig_canvas.bind("<Button-1>", self._handle_canvas_click)

        tk.Label(card, text="Click once on the forehead/eyes area to set face centre.",
                font=("Segoe UI", 9, "italic"), fg=SUB_FG, bg=APP_BG).pack(pady=(4, 0))

        self.face_var = tk.StringVar(value="Face centre: Auto")
        tk.Label(card, textvariable=self.face_var, font=("Segoe UI", 9),
                fg="#e67e22", bg=APP_BG).pack()

    def _build_action_bar(self, parent: tk.Frame, on_apply, on_clear, on_prev, on_next) -> None:
        bar = tk.Frame(parent, bg=APP_BG)
        bar.pack(fill=tk.X, pady=(6, 0))

        self.apply_btn = ttk.Button(bar, text="⚡  Apply Override & Re-Inject",
                                    command=on_apply, state=tk.DISABLED, style="Accent.TButton")
        self.apply_btn.pack(side=tk.LEFT, padx=4)

        self.clear_btn = ttk.Button(bar, text="🔄  Clear Override (use auto)",
                                    command=on_clear, state=tk.DISABLED)
        self.clear_btn.pack(side=tk.LEFT, padx=4)

        ttk.Separator(bar, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(bar, text="◀  Prev", command=on_prev).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="Next  ▶", command=on_next).pack(side=tk.LEFT, padx=2)

    # ── Tree API ──────────────────────────────────────────────────────────────

    def rebuild_tree(self, students: list[dict], row_values_fn: Callable[[dict], tuple]) -> None:
        self.tree.delete(*self.tree.get_children())
        for i, s in enumerate(students):
            self.tree.insert("", tk.END, iid=str(i),
                             values=row_values_fn(s), tags=(s.get("status", "pending"),))

    def refresh_row(self, idx: int, student: dict, row_values_fn: Callable[[dict], tuple]) -> None:
        self.tree.item(str(idx), values=row_values_fn(student),
                       tags=(student.get("status", "pending"),))

    def get_selected_index(self) -> Optional[int]:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def select_index(self, idx: int) -> None:
        self.tree.selection_set(str(idx))
        self.tree.see(str(idx))

    # ── Preview API ───────────────────────────────────────────────────────────

    def set_preview_image(self, pil_image: Optional[Image.Image], error_text: str = "") -> None:
        if pil_image is not None:
            self._preview_photo = ImageTk.PhotoImage(pil_image)
            self._preview_lbl.configure(image=self._preview_photo, text="")
        else:
            self._preview_lbl.configure(image="", text=error_text or "No preview available")

    def render_original(self, image_path: str, active_center: Optional[tuple]) -> None:
        """Loads the original image, fits it to the canvas, draws it + optional crosshair."""
        self.orig_canvas.delete("all")
        try:
            with Image.open(image_path) as img:
                img = ImageOps.exif_transpose(img).convert("RGB")
                orig_w, orig_h = img.size

            canvas_w = self.orig_canvas.winfo_width()  or ORIG_W
            canvas_h = self.orig_canvas.winfo_height() or ORIG_H

            scale  = min(canvas_w / orig_w, canvas_h / orig_h, 1.0)
            disp_w = int(orig_w * scale)
            disp_h = int(orig_h * scale)
            off_x  = (canvas_w - disp_w) // 2
            off_y  = (canvas_h - disp_h) // 2

            self._orig_img_size = (orig_w, orig_h)
            self._canvas_scale  = scale
            self._canvas_offset = (off_x, off_y)

            with Image.open(image_path) as img2:
                img2 = ImageOps.exif_transpose(img2).convert("RGB")
                img2 = img2.resize((disp_w, disp_h), Image.LANCZOS)

            self._orig_photo = ImageTk.PhotoImage(img2)
            self.orig_canvas.create_image(off_x, off_y, image=self._orig_photo, anchor="nw")

            if active_center:
                cx = off_x + int(active_center[0] * scale)
                cy = off_y + int(active_center[1] * scale)
                self._draw_crosshair(cx, cy)

        except Exception as exc:
            self.orig_canvas.create_text(
                ORIG_W // 2, ORIG_H // 2,
                text=f"Cannot load image:\n{exc}",
                fill="white", font=("Segoe UI", 10), justify=tk.CENTER,
            )

    def redraw_crosshair_at_canvas_point(self, cx: int, cy: int) -> None:
        """Used for instant feedback right where the user clicked."""
        self.orig_canvas.delete("xhair")
        self._draw_crosshair(cx, cy)

    def _draw_crosshair(self, cx: int, cy: int, size: int = 22) -> None:
        col = "#ff3333"
        kw  = {"fill": col, "width": 2, "tags": "xhair"}
        self.orig_canvas.create_line(cx - size, cy, cx + size, cy, **kw)
        self.orig_canvas.create_line(cx, cy - size, cx, cy + size, **kw)
        self.orig_canvas.create_oval(cx - 6, cy - 6, cx + 6, cy + 6,
                                     outline=col, width=2, tags="xhair")

    def set_info_text(self, text: str) -> None:
        self.info_var.set(text)

    def set_face_label(self, center: Optional[tuple], pending: bool = False) -> None:
        if center:
            suffix = " [PENDING]" if pending else " [MANUAL]"
            self.face_var.set(f"Face centre: ({center[0]}, {center[1]}){suffix}")
        else:
            self.face_var.set("Face centre: Auto")

    def set_apply_enabled(self, enabled: bool) -> None:
        self.apply_btn.configure(state=tk.NORMAL if enabled else tk.DISABLED)

    def set_clear_enabled(self, enabled: bool) -> None:
        self.clear_btn.configure(state=tk.NORMAL if enabled else tk.DISABLED)

    # ── Click handler (geometry → callback) ──────────────────────────────────

    def _handle_canvas_click(self, event) -> None:
        ox, oy = self._canvas_offset
        scale  = self._canvas_scale
        orig_w, orig_h = self._orig_img_size

        orig_x = max(0, min(int((event.x - ox) / scale), orig_w - 1))
        orig_y = max(0, min(int((event.y - oy) / scale), orig_h - 1))

        self.redraw_crosshair_at_canvas_point(event.x, event.y)
        self._on_canvas_click(orig_x, orig_y)
