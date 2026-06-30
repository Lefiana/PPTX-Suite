"""
ui/sidebar.py
Self-contained Sidebar widget.  Emits a phase-change callback when the
operator clicks a navigation item; the main window never needs to know
about individual button widgets.
"""
from __future__ import annotations
import tkinter as tk
from typing import Callable
from ui.widgets import PALETTE

C = PALETTE   # short alias


class Sidebar(tk.Frame):
    """
    Dark left-hand navigation panel.

    Usage::
        sidebar = Sidebar(root, phases=PHASES, on_select=app.show_phase)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.set_active(0)
    """

    def __init__(
        self,
        parent: tk.Widget,
        phases: list[dict],
        on_select: Callable[[int], None],
    ) -> None:
        super().__init__(parent, bg=C["sidebar_bg"], width=215)
        self.pack_propagate(False)
        self._on_select = on_select
        self._nav_items: list[dict] = []   # {bg_frame, inner, top_row}

        self._build_logo()
        self._build_divider()
        self._build_nav(phases)
        self._build_footer()

    # ── Construction ──────────────────────────────────────────────────────────

    def _build_logo(self) -> None:
        area = tk.Frame(self, bg=C["sidebar_bg"])
        area.pack(fill=tk.X, pady=(22, 4))
        tk.Label(area, text="🎓", font=("Segoe UI Emoji", 38),
                 bg=C["sidebar_bg"], fg=C["sidebar_fg"]).pack()
        tk.Label(area, text="Graduation\nAutomation Suite",
                 font=("Segoe UI", 12, "bold"),
                 bg=C["sidebar_bg"], fg=C["sidebar_fg"],
                 justify=tk.CENTER).pack(pady=(2, 0))

    def _build_divider(self) -> None:
        tk.Frame(self, bg=C["sidebar_dim"], height=1).pack(fill=tk.X, padx=18, pady=14)

    def _build_nav(self, phases: list[dict]) -> None:
        host = tk.Frame(self, bg=C["sidebar_bg"])
        host.pack(fill=tk.X, padx=6)

        for idx, phase in enumerate(phases):
            bg_frm = tk.Frame(host, bg=C["sidebar_bg"])
            bg_frm.pack(fill=tk.X, pady=2)

            inner = tk.Frame(bg_frm, bg=C["sidebar_bg"], padx=14, pady=8)
            inner.pack(fill=tk.X)

            top_row = tk.Frame(inner, bg=C["sidebar_bg"])
            top_row.pack(fill=tk.X)
            tk.Label(top_row, text=phase["icon"],
                     font=("Segoe UI Emoji", 13),
                     bg=C["sidebar_bg"], fg=C["sidebar_fg"]).pack(side=tk.LEFT)
            tk.Label(top_row, text=f"  {phase['title']}",
                     font=("Segoe UI", 11, "bold"),
                     bg=C["sidebar_bg"], fg=C["sidebar_fg"]).pack(side=tk.LEFT)
            tk.Label(inner, text=phase["subtitle"],
                     font=("Segoe UI", 8),
                     bg=C["sidebar_bg"], fg=C["sidebar_dim"]).pack(anchor="w")

            self._nav_items.append({
                "bg": bg_frm, "inner": inner, "top": top_row,
            })

            # Bind click + hover on every descendant widget
            for w in self._all_children(bg_frm):
                w.bind("<Button-1>", lambda _e, i=idx: self._on_select(i))
                w.bind("<Enter>",    lambda _e, f=bg_frm: self._hover(f, True))
                w.bind("<Leave>",    lambda _e, f=bg_frm: self._hover(f, False))

    def _build_footer(self) -> None:
        tk.Frame(self, bg=C["sidebar_dim"], height=1).pack(fill=tk.X, padx=18, pady=(20, 6))
        tk.Label(self, text="v2.0  |  python-pptx engine",
                 font=("Segoe UI", 8),
                 bg=C["sidebar_bg"], fg=C["sidebar_dim"]).pack(pady=4)

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_active(self, phase_id: int) -> None:
        """Highlights the active nav item and resets all others."""
        for i, item in enumerate(self._nav_items):
            colour = C["sidebar_active"] if i == phase_id else C["sidebar_bg"]
            for w in self._all_children(item["bg"]):
                try:
                    w.configure(bg=colour)
                except tk.TclError:
                    pass

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _hover(self, bg_frm: tk.Frame, hovering: bool) -> None:
        if bg_frm.cget("bg") == C["sidebar_active"]:
            return   # never dim the active item on hover-leave
        colour = C["sidebar_hover"] if hovering else C["sidebar_bg"]
        for w in self._all_children(bg_frm):
            try:
                w.configure(bg=colour)
            except tk.TclError:
                pass

    @staticmethod
    def _all_children(widget: tk.Widget):
        yield widget
        for child in widget.winfo_children():
            yield from Sidebar._all_children(child)
