"""
phases/phase0/calibration_ui.py
Phase 0 — Manual Calibration Engine.
Scrollable form that lets the operator edit every value in layout_config.json.
Delegates all I/O to core.config_manager.ConfigManager.
Uses shared widget helpers from ui.widgets.
"""
from __future__ import annotations
import json
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from core.config_manager import DEFAULT_LAYOUT_CONFIG
from ui.widgets import (APP_BG, CARD_BG, ACCENT, SUB_FG,
                         make_header_bar, make_scrollable_frame)


class CalibrationFrame(ttk.Frame):
    """Phase 0 content pane."""

    def __init__(self, parent: tk.Widget, app) -> None:
        super().__init__(parent)
        self.app = app
        self._entries: dict[str, ttk.Entry]      = {}
        self._mapping_rows: list[tuple]           = []
        self._build_ui()
        self._load_config()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        make_header_bar(self, "⚙️  Phase 0 — Manual Calibration Engine")

        outer = tk.Frame(self, bg=APP_BG)
        outer.pack(fill=tk.BOTH, expand=True)
        _canvas, self._scroll_frame = make_scrollable_frame(outer)

        self._build_portrait_section()
        self._build_shapes_section()
        self._build_excel_section()
        self._build_fd_section()
        self._build_mapping_section()
        self._build_json_preview()
        self._build_action_row()

    # ── Section builders ──────────────────────────────────────────────────────

    def _build_portrait_section(self) -> None:
        card = self._card("📐  Portrait Position & Size  (cm)")
        for key, label, default in [
            ("portrait.left_cm",   "Left offset  (left_cm)",    29.79),
            ("portrait.top_cm",    "Top offset   (top_cm)",      2.58),
            ("portrait.width_cm",  "Width        (width_cm)",   17.27),
            ("portrait.height_cm", "Height       (height_cm)", 23.43),
        ]:
            self._field_row(card, label, key, default)

    def _build_shapes_section(self) -> None:
        card = self._card("📝  PowerPoint Shape Names")
        for key, label, default in [
            ("shapes.surname",   "Surname text-box name",    "TextBox 6"),
            ("shapes.firstname", "First-name text-box name", "TextBox 7"),
            ("shapes.course",    "Course text-box name",     "TextBox 8"),
        ]:
            self._field_row(card, label, key, default)
        tk.Label(card,
                 text="💡  PowerPoint → right-click shape → Format Shape → Properties → Name.",
                 font=("Segoe UI", 9, "italic"), fg=SUB_FG, bg=CARD_BG, wraplength=700,
                 ).pack(anchor="w", padx=4, pady=(6, 2))

    def _build_excel_section(self) -> None:
        card = self._card("📊  Excel File Schema")
        for key, label, default in [
            ("excel.header_row",     "Header row index (0-based)",    3),
            ("excel.name_column",    "Student name column header",    "STUDENT NAME"),
            ("excel.program_column", "Programme column header",       "PROGRAM"),
        ]:
            self._field_row(card, label, key, default)

    def _build_fd_section(self) -> None:
        card = self._card("🤖  Face Detection Tuning")
        for key, label, default in [
            ("face_detection.top_padding_factor",    "Top padding  (× face height)",          0.70),
            ("face_detection.bottom_padding_factor", "Bottom padding  (× face height)",        1.80),
            ("face_detection.min_face_fraction",     "Min face size  (fraction of img width)", 0.08),
            ("face_detection.max_face_fraction",     "Max face size  (fraction of img width)", 0.80),
            ("face_detection.horizontal_margin",     "Horizontal exclusion margin",             0.15),
            ("face_detection.vertical_limit",        "Vertical search limit",                  0.60),
        ]:
            self._field_row(card, label, key, default)
        tk.Label(card,
                 text="💡  Increase bottom_padding_factor for more torso in the crop.  "
                      "Raise min_face_fraction if small buttons/badges trigger false detections.",
                 font=("Segoe UI", 9, "italic"), fg=SUB_FG, bg=CARD_BG, wraplength=700,
                 ).pack(anchor="w", padx=4, pady=(6, 2))

    def _build_mapping_section(self) -> None:
        self._map_card = self._card("🗂️  Program Code → Full Name Mapping")
        ctrl = tk.Frame(self._map_card, bg=CARD_BG)
        ctrl.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(ctrl, text="＋  Add Row", command=self._add_mapping_row).pack(side=tk.LEFT)

        self._map_inner = tk.Frame(self._map_card, bg=CARD_BG)
        self._map_inner.pack(fill=tk.X, anchor="w")
        tk.Label(self._map_inner, text="Code",  width=12, font=("Segoe UI", 9, "bold"),
                 bg=CARD_BG, anchor="w").grid(row=0, column=0, padx=4, pady=2, sticky="w")
        tk.Label(self._map_inner, text="Full Programme Name", width=55,
                 font=("Segoe UI", 9, "bold"), bg=CARD_BG, anchor="w",
                 ).grid(row=0, column=1, padx=4, pady=2, sticky="w")

    def _add_mapping_row(self, code: str = "", name: str = "") -> None:
        r  = len(self._mapping_rows) + 1
        ce = ttk.Entry(self._map_inner, width=12)
        ce.grid(row=r, column=0, padx=4, pady=2, sticky="w")
        ce.insert(0, code)
        ne = ttk.Entry(self._map_inner, width=55)
        ne.grid(row=r, column=1, padx=4, pady=2, sticky="w")
        ne.insert(0, name)
        db = ttk.Button(self._map_inner, text="✕", width=3,
                        command=lambda i=len(self._mapping_rows): self._remove_mapping_row(i))
        db.grid(row=r, column=2, padx=4, pady=2)
        self._mapping_rows.append((ce, ne, db))

    def _remove_mapping_row(self, idx: int) -> None:
        if 0 <= idx < len(self._mapping_rows):
            for w in self._mapping_rows[idx]:
                w.destroy()
            self._mapping_rows.pop(idx)
            for i, (ce, ne, db) in enumerate(self._mapping_rows):
                ce.grid(row=i + 1, column=0)
                ne.grid(row=i + 1, column=1)
                db.grid(row=i + 1, column=2)

    def _build_json_preview(self) -> None:
        card = self._card("🔍  Raw JSON Preview  (read-only)")
        self._json_preview = scrolledtext.ScrolledText(
            card, height=9, font=("Courier New", 9),
            bg="#1e1e1e", fg="#d4d4d4", state=tk.DISABLED,
        )
        self._json_preview.pack(fill=tk.X)

    def _build_action_row(self) -> None:
        row = tk.Frame(self._scroll_frame, bg=APP_BG)
        row.pack(fill=tk.X, padx=22, pady=(6, 20))
        ttk.Button(row, text="💾  Save Configuration",
                   style="Accent.TButton", command=self._save_config).pack(side=tk.LEFT, padx=4)
        ttk.Button(row, text="🔄  Reload from File",
                   command=self._load_config).pack(side=tk.LEFT, padx=4)
        ttk.Button(row, text="🔁  Reset to Defaults",
                   command=self._reset_defaults).pack(side=tk.LEFT, padx=4)

    # ── Load / Save ───────────────────────────────────────────────────────────

    def _load_config(self) -> None:
        config = self.app.config_manager.load_layout_config()
        flat   = self.app.config_manager.flatten(config)
        for key, entry in self._entries.items():
            if key in flat:
                entry.delete(0, tk.END)
                entry.insert(0, str(flat[key]))
        for ce, ne, db in self._mapping_rows:
            ce.destroy(); ne.destroy(); db.destroy()
        self._mapping_rows.clear()
        for code, name in config.get("program_mapping", {}).items():
            self._add_mapping_row(code, name)
        self._refresh_json_preview(config)

    def _save_config(self) -> None:
        try:
            flat: dict = {}
            for key, entry in self._entries.items():
                raw = entry.get().strip()
                try:
                    flat[key] = float(raw) if "." in raw else int(raw)
                except ValueError:
                    flat[key] = raw
            config = self.app.config_manager.unflatten(flat)
            config["program_mapping"] = {
                ce.get().strip().upper(): ne.get().strip()
                for ce, ne, _ in self._mapping_rows
                if ce.get().strip() and ne.get().strip()
            }
            self.app.config_manager.save_layout_config(config)
            self._refresh_json_preview(config)
            messagebox.showinfo("Saved", "layout_config.json updated successfully.")
        except Exception as exc:
            messagebox.showerror("Save Error", str(exc))

    def _reset_defaults(self) -> None:
        if messagebox.askyesno("Reset", "Restore all values to factory defaults?"):
            self.app.config_manager.save_layout_config(DEFAULT_LAYOUT_CONFIG)
            self._load_config()

    def _refresh_json_preview(self, config: dict) -> None:
        self._json_preview.configure(state=tk.NORMAL)
        self._json_preview.delete("1.0", tk.END)
        self._json_preview.insert("1.0", json.dumps(config, indent=2))
        self._json_preview.configure(state=tk.DISABLED)

    # ── Widget helpers ─────────────────────────────────────────────────────────

    def _card(self, title: str) -> tk.Frame:
        outer = tk.Frame(self._scroll_frame, bg=APP_BG)
        outer.pack(fill=tk.X, padx=18, pady=6)
        tb = tk.Frame(outer, bg=ACCENT, height=26)
        tb.pack(fill=tk.X)
        tb.pack_propagate(False)
        tk.Label(tb, text=title, font=("Segoe UI", 10, "bold"),
                 bg=ACCENT, fg="white", padx=10).pack(side=tk.LEFT, pady=3)
        body = tk.Frame(outer, bg=CARD_BG, padx=14, pady=10,
                        highlightbackground="#dde3ea", highlightthickness=1)
        body.pack(fill=tk.X)
        return body

    def _field_row(self, parent: tk.Frame, label: str, key: str, default) -> ttk.Entry:
        row = tk.Frame(parent, bg=CARD_BG)
        row.pack(fill=tk.X, pady=3)
        tk.Label(row, text=label, width=46, anchor="w",
                 font=("Segoe UI", 10), bg=CARD_BG, fg="#2c3e50").pack(side=tk.LEFT)
        entry = ttk.Entry(row, width=28)
        entry.insert(0, str(default))
        entry.pack(side=tk.LEFT, padx=6)
        self._entries[key] = entry
        return entry
