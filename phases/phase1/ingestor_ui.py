"""
phases/phase1/ingestor_ui.py
Phase 1 — Records Reconciliation Ingestor (UI layer only).

All matching logic lives in folder_classifier.py.
All file-system / report logic lives in file_operations.py.
This module only wires widgets to those two modules and renders results.
"""
from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import scrolledtext, ttk

from ui.widgets import APP_BG, CARD_BG, ACCENT, SUB_FG, make_header_bar, make_path_row
from ui.dialogs import pick_file, pick_dir, show_error, show_warning, show_info, ask_yes_no

from phases.phase1.folder_classifier import load_roster, scan_source, match_students
from phases.phase1.file_operations import execute_copies, generate_report
from phases.phase1.mappings import DEST_LABELS


class IngestorFrame(ttk.Frame):
    """Phase 1 content pane — Records Reconciliation Ingestor."""

    def __init__(self, parent: tk.Widget, app) -> None:
        super().__init__(parent)
        self.app = app

        # Path variables
        self._excel_var  = tk.StringVar()
        self._source_var = tk.StringVar()
        self._dest_var   = tk.StringVar()

        # Option variables
        self._program_var     = tk.StringVar(value="college")
        self._fuzzy_enabled   = tk.BooleanVar(value=False)
        self._fuzzy_threshold = tk.IntVar(value=80)
        self._move_mode       = tk.BooleanVar(value=False)   # False = copy (safe default)

        # Excel schema variables (mirrors layout_config on load)
        self._name_col_var   = tk.StringVar(value="STUDENT NAME")
        self._prog_col_var   = tk.StringVar(value="PROGRAM")
        self._header_row_var = tk.IntVar(value=0)

        self._build_ui()
        self._restore_session()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        make_header_bar(self, "📋  Phase 1 — Records Reconciliation Ingestor")

        outer = tk.Frame(self, bg=APP_BG)
        outer.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(outer, bg=APP_BG, highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._scroll_frame = tk.Frame(canvas, bg=APP_BG)
        win_id = canvas.create_window((0, 0), window=self._scroll_frame, anchor="nw")
        self._scroll_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        self._build_files_card()
        self._build_options_card()
        self._build_schema_card()
        self._build_info_card()
        self._build_log_card()

    def _build_files_card(self) -> None:
        card = self._card("📂  File & Folder Selection")
        make_path_row(card, "Excel Graduation Roster:", self._excel_var, self._browse_excel)
        make_path_row(card, "Source  (InfoCluttered folder):", self._source_var, self._browse_source)
        make_path_row(card, "Destination  (Sorted output root):", self._dest_var, self._browse_dest)

    def _build_options_card(self) -> None:
        card = self._card("⚙️  Matching Options")

        r1 = tk.Frame(card, bg=CARD_BG); r1.pack(fill=tk.X, pady=4)
        tk.Label(r1, text="Programme filter:", width=26, anchor="w",
                 font=("Segoe UI", 10), bg=CARD_BG).pack(side=tk.LEFT)
        ttk.Combobox(r1, textvariable=self._program_var, width=16, state="readonly",
                    values=["college", "shs", "all"]).pack(side=tk.LEFT, padx=5)
        tk.Label(r1, text="(filters Excel records by programme type before matching)",
                 font=("Segoe UI", 9, "italic"), fg=SUB_FG, bg=CARD_BG).pack(side=tk.LEFT, padx=8)

        r2 = tk.Frame(card, bg=CARD_BG); r2.pack(fill=tk.X, pady=4)
        ttk.Checkbutton(r2, text="Enable fuzzy matching", variable=self._fuzzy_enabled,
                        command=self._toggle_fuzzy).pack(side=tk.LEFT)
        tk.Label(r2, text="  Threshold:", font=("Segoe UI", 10), bg=CARD_BG).pack(side=tk.LEFT)
        self._fuzzy_spin = ttk.Spinbox(r2, from_=50, to=100, textvariable=self._fuzzy_threshold,
                                       width=5, state=tk.DISABLED)
        self._fuzzy_spin.pack(side=tk.LEFT, padx=4)
        tk.Label(r2, text="% (70–90 recommended for Filipino names)",
                 font=("Segoe UI", 9, "italic"), fg=SUB_FG, bg=CARD_BG).pack(side=tk.LEFT)

        r3 = tk.Frame(card, bg=CARD_BG); r3.pack(fill=tk.X, pady=4)
        tk.Label(r3, text="Operation mode:", width=26, anchor="w",
                 font=("Segoe UI", 10), bg=CARD_BG).pack(side=tk.LEFT)
        ttk.Radiobutton(r3, text="Copy  (safe — original untouched)",
                        variable=self._move_mode, value=False).pack(side=tk.LEFT)
        ttk.Radiobutton(r3, text="Move  (after dry-run verification)",
                        variable=self._move_mode, value=True).pack(side=tk.LEFT, padx=20)

    def _build_schema_card(self) -> None:
        card = self._card("📊  Excel Schema")

        r1 = tk.Frame(card, bg=CARD_BG); r1.pack(fill=tk.X, pady=3)
        for label, var, w in [
            ("Student Name column:", self._name_col_var, 22),
            ("Programme column:",    self._prog_col_var, 22),
        ]:
            tk.Label(r1, text=label, width=24, anchor="w",
                     font=("Segoe UI", 10), bg=CARD_BG).pack(side=tk.LEFT)
            ttk.Entry(r1, textvariable=var, width=w).pack(side=tk.LEFT, padx=(0, 20))

        r2 = tk.Frame(card, bg=CARD_BG); r2.pack(fill=tk.X, pady=3)
        tk.Label(r2, text="Header row (0-based index):", width=28, anchor="w",
                 font=("Segoe UI", 10), bg=CARD_BG).pack(side=tk.LEFT)
        ttk.Spinbox(r2, from_=0, to=20, textvariable=self._header_row_var, width=5).pack(side=tk.LEFT)
        tk.Label(r2, text="  (use 3 if your Excel has a 4-row title block)",
                 font=("Segoe UI", 9, "italic"), fg=SUB_FG, bg=CARD_BG).pack(side=tk.LEFT, padx=8)

    def _build_info_card(self) -> None:
        card = self._card("ℹ️  How the Reconciliation Works")
        text = (
            "The ingestor cross-references every student name in your Excel roster against "
            "physical sub-folders in the Source directory using a 3-pass algorithm:\n\n"
            "  Pass 1 — Exact:   Normalised name strings are compared directly.\n"
            "  Pass 2 — Token:   ALL surname tokens must appear in the folder name "
            "(handles De La Pena, Del Rosario, San Pedro).\n"
            "  Pass 3 — Fuzzy:   difflib similarity ratio (enable above). Catches typos.\n\n"
            "  ✅  Match Found   → folder is COPIED/MOVED to Destination/<Programme>_Graduates/\n"
            "  ❌  No Match      → student is logged as a Missing Record\n"
            "  ⚠️   Orphan folder → exists in Source but is not in the Excel roster"
        )
        tk.Label(card, text=text, justify=tk.LEFT, font=("Segoe UI", 10),
                bg=CARD_BG, fg="#2c3e50", wraplength=820).pack(anchor="w")

    def _build_log_card(self) -> None:
        outer = tk.Frame(self._scroll_frame, bg=APP_BG)
        outer.pack(fill=tk.BOTH, expand=True, pady=5)
        title_bar = tk.Frame(outer, bg=ACCENT, height=26)
        title_bar.pack(fill=tk.X); title_bar.pack_propagate(False)
        tk.Label(title_bar, text="📋  Operation Log", font=("Segoe UI", 10, "bold"),
                bg=ACCENT, fg="white", padx=10).pack(side=tk.LEFT, pady=3)

        body = tk.Frame(outer, bg=CARD_BG, padx=14, pady=10,
                        highlightbackground="#dde3ea", highlightthickness=1)
        body.pack(fill=tk.BOTH, expand=True)

        btn_row = tk.Frame(body, bg=CARD_BG); btn_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(btn_row, text="🔍  Preview  (dry run)", command=self._dry_run).pack(side=tk.LEFT, padx=4)
        self._exec_btn = ttk.Button(btn_row, text="▶  Execute", style="Accent.TButton",
                                    command=self._execute)
        self._exec_btn.pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="🗑  Clear Log", command=self._clear_log).pack(side=tk.RIGHT, padx=4)

        self._log = scrolledtext.ScrolledText(
            body, height=18, font=("Courier New", 9),
            bg="#1e1e1e", fg="#d4d4d4", state=tk.DISABLED,
        )
        for tag, colour in [("ok", "#4ec9b0"), ("warn", "#dcdcaa"), ("error", "#f44747"),
                            ("miss", "#f44747"), ("fuzz", "#c586c0"), ("token", "#9cdcfe")]:
            self._log.tag_configure(tag, foreground=colour)
        self._log.tag_configure("head", foreground="#569cd6", font=("Courier New", 9, "bold"))
        self._log.pack(fill=tk.BOTH, expand=True)

        self._progress_var = tk.DoubleVar()
        ttk.Progressbar(body, variable=self._progress_var, maximum=100).pack(fill=tk.X, pady=(6, 2))
        self._status_var = tk.StringVar(value="Select files and run a Dry-Run Preview first.")
        ttk.Label(body, textvariable=self._status_var, foreground=SUB_FG,
                 background=CARD_BG).pack(anchor="w")

    # ── Card helper ───────────────────────────────────────────────────────────

    def _card(self, title: str) -> tk.Frame:
        outer = tk.Frame(self._scroll_frame, bg=APP_BG)
        outer.pack(fill=tk.X, pady=5)
        tb = tk.Frame(outer, bg=ACCENT, height=26)
        tb.pack(fill=tk.X); tb.pack_propagate(False)
        tk.Label(tb, text=title, font=("Segoe UI", 10, "bold"),
                bg=ACCENT, fg="white", padx=10).pack(side=tk.LEFT, pady=3)
        body = tk.Frame(outer, bg=CARD_BG, padx=14, pady=10,
                        highlightbackground="#dde3ea", highlightthickness=1)
        body.pack(fill=tk.X)
        return body

    # ── Browse handlers ────────────────────────────────────────────────────────

    def _browse_excel(self) -> None:
        p = pick_file("Select Excel roster", [("Excel", "*.xlsx *.xls")])
        if p:
            self._excel_var.set(p)
            self.app.metadata_manager.update_session(excel_path=p)

    def _browse_source(self) -> None:
        p = pick_dir("Select source (cluttered) folder")
        if p:
            self._source_var.set(p)
            self.app.metadata_manager.update_session(source_dir=p)

    def _browse_dest(self) -> None:
        p = pick_dir("Select destination root")
        if p:
            self._dest_var.set(p)
            self.app.metadata_manager.update_session(dest_dir=p)

    def _toggle_fuzzy(self) -> None:
        self._fuzzy_spin.configure(state=tk.NORMAL if self._fuzzy_enabled.get() else tk.DISABLED)

    def _restore_session(self) -> None:
        s = self.app.metadata_manager.get_session()
        self._excel_var.set(s.get("excel_path", ""))
        self._source_var.set(s.get("source_dir", ""))
        self._dest_var.set(s.get("dest_dir", ""))
        try:
            cfg = self.app.config_manager.load_layout_config()
            exc = cfg.get("excel", {})
            self._name_col_var.set(exc.get("name_column", "STUDENT NAME"))
            self._prog_col_var.set(exc.get("program_column", "PROGRAM"))
            self._header_row_var.set(int(exc.get("header_row", 0)))
        except Exception:
            pass

    # ── Log helpers ────────────────────────────────────────────────────────────

    def _log_line(self, text: str, tag: str = "") -> None:
        self._log.configure(state=tk.NORMAL)
        self._log.insert(tk.END, text + "\n", tag)
        self._log.see(tk.END)
        self._log.configure(state=tk.DISABLED)

    def _clear_log(self) -> None:
        self._log.configure(state=tk.NORMAL)
        self._log.delete("1.0", tk.END)
        self._log.configure(state=tk.DISABLED)
        self._progress_var.set(0)

    # ── Validation ────────────────────────────────────────────────────────────

    def _validate(self) -> bool:
        excel  = self._excel_var.get().strip()
        source = self._source_var.get().strip()
        dest   = self._dest_var.get().strip()
        if not excel or not Path(excel).is_file():
            show_error("Missing input", "Please select a valid Excel roster file.")
            return False
        if not source or not Path(source).is_dir():
            show_error("Missing input", "Please select a valid Source directory.")
            return False
        if not dest:
            show_error("Missing input", "Please set a Destination folder.")
            return False
        return True

    # ── Dry-run / Execute entry points ───────────────────────────────────────

    def _dry_run(self) -> None:
        if not self._validate(): return
        self._clear_log()
        self._run(dry_run=True)

    def _execute(self) -> None:
        if not self._validate(): return
        verb = "MOVE" if self._move_mode.get() else "COPY"
        if not ask_yes_no("Confirm Execute",
                          f"This will {verb} matched folders into the destination.\n"
                          "A full reconciliation report will also be generated.\n\nProceed?"):
            return
        self._clear_log()
        self._run(dry_run=False)

    # ── Threaded worker ────────────────────────────────────────────────────────

    def _run(self, dry_run: bool) -> None:
        self._exec_btn.configure(state=tk.DISABLED)
        self._status_var.set("Running reconciliation…  please wait.")
        self._progress_var.set(0)

        def worker():
            try:
                excel      = Path(self._excel_var.get().strip())
                source_dir = Path(self._source_var.get().strip())
                dest_root  = Path(self._dest_var.get().strip())
                prog       = self._program_var.get()
                fuzzy_th   = self._fuzzy_threshold.get() if self._fuzzy_enabled.get() else None
                do_move    = self._move_mode.get() and not dry_run
                timestamp  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                def ui(fn): self.after(0, fn)

                ui(lambda: self._log_line("━━━  Step 1/4  Loading Excel roster  ━━━━━━━━━━━━━━━━━━", "head"))
                students = load_roster(excel, prog, self._name_col_var.get(),
                                       self._prog_col_var.get(), self._header_row_var.get())
                ui(lambda n=len(students): self._log_line(f"  Loaded {n} student records  (filter: {prog.upper()})"))
                ui(lambda: self._progress_var.set(10))

                ui(lambda: self._log_line("\n━━━  Step 2/4  Scanning source directory  ━━━━━━━━━━━━", "head"))
                folders = scan_source(source_dir)
                ui(lambda n=len(folders): self._log_line(f"  Found {n} sub-folders in  {source_dir}"))
                ui(lambda: self._progress_var.set(20))

                ui(lambda: self._log_line("\n━━━  Step 3/4  Cross-referencing names  ━━━━━━━━━━━━━", "head"))
                if fuzzy_th:
                    ui(lambda: self._log_line(f"  Fuzzy matching enabled — threshold: {fuzzy_th}%", "fuzz"))
                results, unmatched_folders = match_students(students, folders, fuzzy_th)
                matched = [r for r in results if r.folder is not None]
                missing = [r for r in results if r.folder is None]
                ui(lambda: self._log_line(
                    f"  Matches: {len(matched)}   Missing: {len(missing)}   "
                    f"Unmatched folders: {len(unmatched_folders)}"))
                ui(lambda: self._progress_var.set(40))

                ui(lambda: self._log_line(
                    f"\n━━━  Step 4/4  {'DRY RUN preview' if dry_run else 'Copying folders'}  ━━━━━━━━━━━━━━━━━━━━", "head"))

                total = len(matched)
                op_ok = op_err = 0

                if dry_run:
                    label    = DEST_LABELS.get(prog, "Graduates")
                    dest_dir = dest_root / label
                    for i, r in enumerate(matched):
                        target = dest_dir / r.folder.path.name
                        r.dest_path = target
                        score_str = f"  [{r.match_type} {r.match_score:.0%}]"
                        ui(lambda fn=r.folder.path.name, st=score_str:
                           self._log_line(f"  [DRY RUN] Would copy  {fn}{st}", "warn"))
                        ui(lambda t=str(target): self._log_line(f"            → {t}"))
                        op_ok += 1
                        pct = 40 + ((i + 1) / max(total, 1)) * 50
                        ui(lambda p=pct: self._progress_var.set(p))
                else:
                    def on_item(r, ok, err_msg):
                        score_str = f"  [{r.match_type} {r.match_score:.0%}]"
                        if ok:
                            ui(lambda fn=r.folder.path.name, st=score_str:
                               self._log_line(f"  ✅  {fn}{st}", "ok"))
                        elif err_msg and "already exists" in err_msg:
                            ui(lambda fn=r.folder.path.name:
                               self._log_line(f"  ⚠  {fn} — destination exists, skipped.", "warn"))
                        else:
                            ui(lambda fn=r.folder.path.name, e=err_msg:
                               self._log_line(f"  ❌  ERROR {fn}: {e}", "error"))

                    op_ok, op_err = execute_copies(results, dest_root, prog, do_move, on_item)
                    ui(lambda: self._progress_var.set(90))

                if missing:
                    ui(lambda: self._log_line("\n━━━  MISSING RECORDS  ━━━━━━━━━━━━", "head"))
                    for r in missing:
                        ui(lambda n=r.student.raw_name, p=r.student.raw_program:
                           self._log_line(f"  ❌  {n:<42}  {p}", "miss"))

                if unmatched_folders:
                    ui(lambda: self._log_line("\n━━━  UNMATCHED FOLDERS  ━━━━━━━━━━━━━", "head"))
                    for f in unmatched_folders:
                        ui(lambda n=f.path.name: self._log_line(f"  ⚠   {n}", "warn"))

                xlsx_p, txt_p = generate_report(results, unmatched_folders, dest_root,
                                                prog, dry_run, timestamp)
                ui(lambda: self._progress_var.set(100))
                ui(lambda: self._on_done(len(results), len(matched), len(missing),
                                         len(unmatched_folders), op_ok, op_err,
                                         xlsx_p, txt_p, dry_run, prog))

            except Exception as exc:
                self.after(0, lambda: show_error("Error", str(exc)))
                self.after(0, lambda: self._exec_btn.configure(state=tk.NORMAL))
                self.after(0, lambda: self._status_var.set(f"Error: {exc}"))

        threading.Thread(target=worker, daemon=True).start()

    # ── Completion callback (main thread) ─────────────────────────────────────

    def _on_done(self, total, matched, missing, unmatched,
                op_ok, op_err, xlsx_p, txt_p, dry_run, prog) -> None:
        self._exec_btn.configure(state=tk.NORMAL)

        self._log_line("\n" + "━" * 62, "head")
        self._log_line(f"  SUMMARY  {'[DRY RUN]' if dry_run else '[EXECUTED]'}  |  Filter: {prog.upper()}", "head")
        self._log_line("━" * 62, "head")
        self._log_line(f"  Total Excel records  : {total}")
        self._log_line(f"  Successful matches   : {matched}", "ok" if matched else "")
        self._log_line(f"  Missing records      : {missing}", "miss" if missing else "")
        self._log_line(f"  Unmatched folders    : {unmatched}", "warn" if unmatched else "")
        if not dry_run:
            self._log_line(f"  Operations OK        : {op_ok}", "ok" if op_ok else "")
            if op_err:
                self._log_line(f"  Operation errors     : {op_err}", "error")
        self._log_line(f"\n  📊 Excel report  →  {xlsx_p}")
        self._log_line(f"  📄 Missing list  →  {txt_p}")

        mode = "DRY RUN" if dry_run else "EXECUTED"
        self._status_var.set(
            f"{mode}  |  {matched}/{total} matched  |  {missing} missing  |  Reports → {xlsx_p.parent}"
        )

        if not dry_run and op_err == 0:
            show_info("Done",
                      f"Reconciliation complete!\n\n"
                      f"  Matched & copied : {op_ok}\n"
                      f"  Missing records  : {missing}\n"
                      f"  Unmatched folders: {unmatched}\n\n"
                      f"Reports saved to:\n{xlsx_p.parent}")
        elif not dry_run:
            show_warning("Done with errors", f"{op_ok} succeeded, {op_err} failed.\nSee log for details.")
