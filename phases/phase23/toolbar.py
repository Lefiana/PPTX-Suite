"""
phases/phase23/toolbar.py
Top toolbar widget for Phase 2+3: file/folder path rows, Load Students,
Generate Draft PPTX, and the progress bar.  Pure UI — emits callbacks to
the controller and exposes simple getters/setters.  Holds no business logic.
"""
from __future__ import annotations
import tkinter as tk
from typing import Callable
from tkinter import ttk


class Toolbar(tk.Frame):
    """
    Usage::
        toolbar = Toolbar(
            parent,
            on_browse_excel=..., on_browse_template=...,
            on_browse_master=..., on_set_output=...,
            on_load_students=..., on_generate=...,
        )
        toolbar.pack(fill=tk.X)
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_browse_excel:    Callable[[], None],
        on_browse_template: Callable[[], None],
        on_browse_master:   Callable[[], None],
        on_set_output:      Callable[[], None],
        on_load_students:   Callable[[], None],
        on_generate:        Callable[[], None],
    ) -> None:
        super().__init__(parent, bg="#dde3ea", pady=5)

        self.excel_var    = tk.StringVar()
        self.template_var = tk.StringVar()
        self.master_var   = tk.StringVar()
        self.output_var   = tk.StringVar()

        self._on_load_students = on_load_students
        self._on_generate      = on_generate

        self._build_path_row(on_browse_excel, on_browse_template, on_browse_master, on_set_output)
        self._build_action_row()

    # ── Construction ──────────────────────────────────────────────────────────

    def _build_path_row(self, on_excel, on_template, on_master, on_output) -> None:
        r1 = tk.Frame(self, bg="#dde3ea")
        r1.pack(fill=tk.X, padx=12, pady=(2, 0))

        for label, var, cmd, w in [
            ("Excel:",         self.excel_var,    on_excel,    28),
            ("Template PPTX:", self.template_var, on_template, 28),
            ("Master Dir:",    self.master_var,   on_master,   28),
            ("Output PPTX:",   self.output_var,   on_output,   28),
        ]:
            tk.Label(r1, text=label, font=("Segoe UI", 9), bg="#dde3ea").pack(side=tk.LEFT)
            ttk.Entry(r1, textvariable=var, width=w).pack(side=tk.LEFT, padx=(0, 2))
            ttk.Button(r1, text="…", width=3, command=cmd).pack(side=tk.LEFT, padx=(0, 10))

    def _build_action_row(self) -> None:
        r2 = tk.Frame(self, bg="#dde3ea")
        r2.pack(fill=tk.X, padx=12, pady=(4, 2))

        ttk.Button(r2, text="📂  Load Students",
                  command=self._on_load_students).pack(side=tk.LEFT, padx=3)

        self.generate_btn = ttk.Button(
            r2, text="🚀  Generate Draft PPTX",
            command=self._on_generate, state=tk.DISABLED, style="Accent.TButton",
        )
        self.generate_btn.pack(side=tk.LEFT, padx=3)

        self.progress_var = tk.DoubleVar()
        ttk.Progressbar(r2, variable=self.progress_var, length=180, maximum=100).pack(side=tk.LEFT, padx=8)

        self.progress_lbl = tk.Label(r2, text="", font=("Segoe UI", 9), bg="#dde3ea")
        self.progress_lbl.pack(side=tk.LEFT)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_paths(self, excel: str, template: str, master: str, output: str) -> None:
        self.excel_var.set(excel)
        self.template_var.set(template)
        self.master_var.set(master)
        self.output_var.set(output)

    def get_paths(self) -> dict:
        return {
            "excel":    self.excel_var.get().strip(),
            "template": self.template_var.get().strip(),
            "master":   self.master_var.get().strip(),
            "output":   self.output_var.get().strip(),
        }

    def set_generate_enabled(self, enabled: bool) -> None:
        self.generate_btn.configure(state=tk.NORMAL if enabled else tk.DISABLED)

    def set_progress(self, pct: float) -> None:
        self.progress_var.set(pct)

    def set_progress_label(self, text: str) -> None:
        self.progress_lbl.configure(text=text)
