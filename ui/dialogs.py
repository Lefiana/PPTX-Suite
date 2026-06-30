"""
ui/dialogs.py
Thin, testable wrappers around tkinter's file-dialog and messagebox calls.
All phase modules import from here instead of calling tkinter directly,
making it straightforward to mock them in tests later.
"""
from __future__ import annotations
from tkinter import filedialog, messagebox


# ── File / directory pickers ──────────────────────────────────────────────────

def pick_file(
    title: str = "Select file",
    filetypes: list[tuple] | None = None,
) -> str:
    """Returns the chosen path string, or '' if cancelled."""
    ft = filetypes or [("All files", "*.*")]
    return filedialog.askopenfilename(title=title, filetypes=ft) or ""


def pick_save_file(
    title: str = "Save as",
    default_ext: str = "",
    filetypes: list[tuple] | None = None,
) -> str:
    ft = filetypes or [("All files", "*.*")]
    return filedialog.asksaveasfilename(
        title=title, defaultextension=default_ext, filetypes=ft
    ) or ""


def pick_dir(title: str = "Select folder") -> str:
    return filedialog.askdirectory(title=title) or ""


# ── Messageboxes ──────────────────────────────────────────────────────────────

def show_info(title: str, message: str) -> None:
    messagebox.showinfo(title, message)


def show_warning(title: str, message: str) -> None:
    messagebox.showwarning(title, message)


def show_error(title: str, message: str) -> None:
    messagebox.showerror(title, message)


def ask_yes_no(title: str, message: str) -> bool:
    return messagebox.askyesno(title, message)
