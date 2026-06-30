"""
main.py
Entry point for the Graduation Slide Automation Suite.

This module is intentionally lightweight: it only
  • performs the dependency pre-flight check,
  • builds the root window and ttk style sheet,
  • instantiates the sidebar and the phase frames,
  • and routes navigation events between them.

All business logic lives under core/ and phases/<phaseN>/.
All shared widgets live under ui/.

Run:
    python main.py

Required packages (install once):
    pip install -r requirements.txt
"""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import messagebox, ttk

# ── Dependency pre-flight ─────────────────────────────────────────────────────
_DEPS = {
    "pptx":     "python-pptx",
    "pandas":   "pandas",
    "cv2":      "opencv-python",
    "PIL":      "Pillow",
    "numpy":    "numpy",
    "openpyxl": "openpyxl",
}
_missing: list[str] = []
for _mod, _pkg in _DEPS.items():
    try:
        __import__(_mod)
    except ImportError:
        _missing.append(_pkg)

if _missing:
    _root = tk.Tk()
    _root.withdraw()
    messagebox.showerror(
        "Missing Dependencies",
        "Please install the following packages, then re-run:\n\n"
        f"pip install {' '.join(_missing)}",
    )
    sys.exit(1)

# ── Application imports (safe after dependency check) ────────────────────────
from core.config_manager import ConfigManager       # noqa: E402
from core.metadata_manager import MetadataManager   # noqa: E402
from ui.sidebar import Sidebar                       # noqa: E402

from phases.phase0.calibration_ui import CalibrationFrame   # noqa: E402
from phases.phase1.ingestor_ui import IngestorFrame         # noqa: E402
from phases.phase23.qa_controller import QASuiteFrame       # noqa: E402

# ── App-level constants (sidebar palette lives in ui/widgets.py) ────────────
APP_BG = "#f0f2f5"
ACCENT = "#2980b9"

# ── Phase registry ────────────────────────────────────────────────────────────
PHASES = [
    {"frame_class": CalibrationFrame, "icon": "⚙️", "title": "Phase 0",   "subtitle": "Manual Calibration"},
    {"frame_class": IngestorFrame,    "icon": "📁", "title": "Phase 1",   "subtitle": "Dynamic Ingestor"},
    {"frame_class": QASuiteFrame,     "icon": "🎬", "title": "Phase 2+3", "subtitle": "QA & Generation"},
]


class GraduationSuiteApp(tk.Tk):
    """Root window — hosts the sidebar and the stacked content frames."""

    def __init__(self) -> None:
        super().__init__()
        self.title("🎓  Graduation Slide Automation Suite")
        self.geometry("1440x880")
        self.minsize(1100, 700)
        self.configure(bg=APP_BG)

        # Shared services injected into every phase frame via `self.app`
        self.config_manager   = ConfigManager("config/layout_config.json")
        self.metadata_manager = MetadataManager("data/metadata.json")

        self._setup_styles()

        self.sidebar = Sidebar(self, phases=PHASES, on_select=self.show_phase)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)

        self.content_area = tk.Frame(self, bg=APP_BG)
        self.content_area.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.content_area.grid_rowconfigure(0, weight=1)
        self.content_area.grid_columnconfigure(0, weight=1)

        self.frames: dict[type, ttk.Frame] = {}
        for phase in PHASES:
            cls   = phase["frame_class"]
            frame = cls(self.content_area, self)
            self.frames[cls] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_phase(0)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    # ── TTK style sheet ───────────────────────────────────────────────────────

    def _setup_styles(self) -> None:
        s  = ttk.Style(self)
        s.theme_use("clam")
        bg = APP_BG
        s.configure("TFrame", background=bg)
        s.configure("TLabel", background=bg, font=("Segoe UI", 10))
        s.configure("TLabelframe", background=bg, bordercolor="#c5cdd6")
        s.configure("TLabelframe.Label", background=bg,
                   font=("Segoe UI", 10, "bold"), foreground="#2c3e50")
        s.configure("TEntry", font=("Segoe UI", 10), padding=4)
        s.configure("TButton", font=("Segoe UI", 10), padding=(8, 4))
        s.configure("TScrollbar", background="#c0c8d2")
        s.configure("TProgressbar", troughcolor="#dde3ea", background=ACCENT)
        s.configure("TCombobox", font=("Segoe UI", 10))
        s.configure("Treeview", font=("Segoe UI", 9), rowheight=26,
                   background="white", fieldbackground="white")
        s.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

        s.configure("Accent.TButton", font=("Segoe UI", 10, "bold"),
                   foreground="white", background=ACCENT)
        s.map("Accent.TButton",
             background=[("active", "#3498db"), ("disabled", "#a0b8c8")],
             foreground=[("disabled", "#d0d8e0")])

    # ── Navigation ────────────────────────────────────────────────────────────

    def show_phase(self, phase_id: int) -> None:
        cls = PHASES[phase_id]["frame_class"]
        self.frames[cls].tkraise()
        self.sidebar.set_active(phase_id)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = GraduationSuiteApp()
    app.mainloop()
