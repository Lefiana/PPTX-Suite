"""
ui/widgets.py
Shared palette, colour constants, and widget-factory functions used by
every phase frame and the sidebar.  Import this instead of re-defining
colours in each module.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk

# ── Palette ───────────────────────────────────────────────────────────────────

PALETTE = {
    "hdr_bg":        "#1a2035",
    "hdr_fg":        "#ecf0f1",
    "sidebar_bg":    "#1a2035",
    "sidebar_active":"#2d4a7a",
    "sidebar_hover": "#253354",
    "sidebar_fg":    "#ecf0f1",
    "sidebar_dim":   "#677a90",
    "app_bg":        "#f0f2f5",
    "card_bg":       "#ffffff",
    "accent":        "#2980b9",
    "sub_fg":        "#555e6d",
    "canvas_bg":     "#2c3e50",
}

# Convenience shorthands (used throughout phases)
HDR_BG   = PALETTE["hdr_bg"]
HDR_FG   = PALETTE["hdr_fg"]
APP_BG   = PALETTE["app_bg"]
CARD_BG  = PALETTE["card_bg"]
ACCENT   = PALETTE["accent"]
SUB_FG   = PALETTE["sub_fg"]
CANVAS_BG= PALETTE["canvas_bg"]


# ── Widget factories ──────────────────────────────────────────────────────────

def make_header_bar(parent: tk.Widget, title: str) -> tk.Frame:
    """Dark navy header bar with a bold title label. Returns the Frame."""
    bar = tk.Frame(parent, bg=HDR_BG, height=56)
    bar.pack(fill=tk.X)
    bar.pack_propagate(False)
    tk.Label(
        bar, text=title,
        font=("Segoe UI", 13, "bold"),
        bg=HDR_BG, fg=HDR_FG, padx=20,
    ).pack(side=tk.LEFT, pady=14)
    return bar


def make_card(
    parent: tk.Widget,
    title: str,
    expandable: bool = False,
) -> tk.Frame:
    """
    Creates a titled card inside *parent* and returns the inner body Frame.
    expandable=True makes the card fill vertically (for the log panel).
    """
    outer = tk.Frame(parent, bg=APP_BG)
    if expandable:
        outer.pack(fill=tk.BOTH, expand=True, pady=5)
    else:
        outer.pack(fill=tk.X, pady=5)

    title_bar = tk.Frame(outer, bg=ACCENT, height=26)
    title_bar.pack(fill=tk.X)
    title_bar.pack_propagate(False)
    tk.Label(
        title_bar, text=title,
        font=("Segoe UI", 10, "bold"),
        bg=ACCENT, fg="white", padx=10,
    ).pack(side=tk.LEFT, pady=3)

    body = tk.Frame(
        outer, bg=CARD_BG, padx=14, pady=10,
        highlightbackground="#dde3ea", highlightthickness=1,
    )
    body.pack(fill=tk.BOTH if expandable else tk.X, expand=expandable)
    return body


def make_scrollable_frame(parent: tk.Widget) -> tuple[tk.Canvas, tk.Frame]:
    """
    Returns (canvas, scroll_frame).
    The caller must pack the canvas into its parent.
    """
    canvas = tk.Canvas(parent, bg=APP_BG, highlightthickness=0)
    vsb    = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    scroll_frame = tk.Frame(canvas, bg=APP_BG)

    win_id = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

    def _on_frame_configure(_e):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _on_canvas_configure(e):
        canvas.itemconfig(win_id, width=e.width)

    def _on_mousewheel(e):
        canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    scroll_frame.bind("<Configure>", _on_frame_configure)
    canvas.bind("<Configure>", _on_canvas_configure)
    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    canvas.configure(yscrollcommand=vsb.set)
    vsb.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    return canvas, scroll_frame


def make_path_row(
    parent: tk.Widget,
    label: str,
    var: tk.StringVar,
    browse_cmd,
    label_width: int = 34,
    entry_width: int = 50,
) -> None:
    """Adds a label + entry + Browse button row to *parent*."""
    row = tk.Frame(parent, bg=CARD_BG)
    row.pack(fill=tk.X, pady=4)
    tk.Label(
        row, text=label, width=label_width, anchor="w",
        font=("Segoe UI", 10), bg=CARD_BG,
    ).pack(side=tk.LEFT)
    ttk.Entry(row, textvariable=var, width=entry_width).pack(side=tk.LEFT, padx=5)
    ttk.Button(row, text="Browse…", command=browse_cmd).pack(side=tk.LEFT)
