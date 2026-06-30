"""
phases/phase1/folder_classifier.py
Pure business-logic: no tkinter, no file I/O beyond reading the Excel roster.

Responsibilities:
  • Normalise names (strip diacritics, collapse punctuation)
  • Parse Excel name strings into surname / firstname token sets
  • Classify programme strings (college / shs / other)
  • Load the Excel roster into Student records
  • Scan a source directory into FolderEntry records
  • Run the 3-pass matching algorithm (exact → token → fuzzy)
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

import pandas as pd

from phases.phase1.mappings import COLLEGE_KEYWORDS, SHS_KEYWORDS, SURNAME_PREFIXES


# ── Domain models ─────────────────────────────────────────────────────────────

@dataclass
class Student:
    row_num:        int
    raw_name:       str
    raw_program:    str
    program_type:   str           # "college" | "shs" | "other"
    surname_raw:    str           = ""
    firstname_raw:  str           = ""
    surname_norm:   str           = ""
    surname_tokens: list          = field(default_factory=list)
    all_tokens:     frozenset     = field(default_factory=frozenset)
    full_norm:      str           = ""


@dataclass
class FolderEntry:
    path:      Path
    norm_name: str
    tokens:    frozenset
    claimed:   bool = False


@dataclass
class MatchResult:
    student:     Student
    folder:      Optional[FolderEntry]
    match_type:  str    # "exact" | "token" | "fuzzy" | "missing"
    match_score: float
    dest_path:   Optional[Path] = None


# ── Normalisation ─────────────────────────────────────────────────────────────

def normalize(text: str) -> str:
    """Strips diacritics, collapses punctuation to spaces, lowercases."""
    t = unicodedata.normalize("NFKD", str(text)).encode("ASCII", "ignore").decode("ascii")
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).lower().strip()


def tokenize(text: str) -> list[str]:
    """Returns meaningful word tokens (drops single-char tokens / initials)."""
    return [w for w in normalize(text).split() if len(w) > 1]


def sig_tokens(tokens: list[str]) -> frozenset:
    """Removes single-character tokens (middle initials) for matching."""
    return frozenset(t for t in tokens if len(t) > 1)


# ── Name parser ────────────────────────────────────────────────────────────────

def parse_student(s: Student) -> None:
    """
    Fills normalised name fields on a Student in-place.
    Handles:  "DELA CRUZ, Juan Manuel P."   →  surname="dela cruz"
              "DE LA PENA Ana Grace"         →  surname="de la pena"
    """
    raw = s.raw_name.strip()
    if "," in raw:
        last, first = raw.split(",", 1)
    else:
        parts     = raw.split()
        split_idx = len(parts) - 1
        for i in range(len(parts) - 2, -1, -1):
            if any(" ".join(parts[i:]).lower().startswith(p) for p in SURNAME_PREFIXES):
                split_idx = i; break
        last  = " ".join(parts[split_idx:])
        first = " ".join(parts[:split_idx])

    s.surname_raw   = last.strip()
    s.firstname_raw = first.strip()
    s.surname_norm  = normalize(s.surname_raw)
    s.surname_tokens = s.surname_norm.split()

    all_tok     = tokenize(s.surname_raw) + tokenize(s.firstname_raw)
    s.all_tokens = sig_tokens(all_tok)
    s.full_norm  = normalize(s.surname_raw + " " + s.firstname_raw)


# ── Programme classifier ───────────────────────────────────────────────────────

def classify_program(program: str) -> str:
    p = program.lower()
    if any(k in p for k in COLLEGE_KEYWORDS): return "college"
    if any(k in p for k in SHS_KEYWORDS):     return "shs"
    return "other"


# ── Roster loader ──────────────────────────────────────────────────────────────

def load_roster(
    excel_path:     Path,
    program_filter: str,        # "college" | "shs" | "all"
    name_col:       str = "STUDENT NAME",
    prog_col:       str = "PROGRAM",
    header_row:     int = 0,
) -> list[Student]:
    df = pd.read_excel(excel_path, header=header_row)

    col_map: dict[str, str] = {}
    for target in (name_col, prog_col):
        for col in df.columns:
            if str(col).strip().upper() == target.upper():
                col_map[target] = col; break
        if target not in col_map:
            raise ValueError(
                f"Column '{target}' not found.\nAvailable: {list(df.columns)}"
            )

    students: list[Student] = []
    for idx, row in df.iterrows():
        raw_name = str(row[col_map[name_col]]).strip()
        raw_prog = str(row[col_map[prog_col]]).strip()
        if not raw_name or raw_name.lower() in ("nan", "none", ""): continue
        if not raw_prog or raw_prog.lower() in ("nan", "none", ""): continue

        ptype = classify_program(raw_prog)
        if program_filter != "all" and ptype != program_filter:
            continue

        s = Student(
            row_num=int(idx) + header_row + 2,
            raw_name=raw_name, raw_program=raw_prog, program_type=ptype,
        )
        parse_student(s)
        students.append(s)

    return students


# ── Directory scanner ─────────────────────────────────────────────────────────

def scan_source(source_dir: Path) -> list[FolderEntry]:
    return [
        FolderEntry(
            path=c,
            norm_name=normalize(c.name),
            tokens=sig_tokens(normalize(c.name).split()),
        )
        for c in sorted(source_dir.iterdir()) if c.is_dir()
    ]


# ── Scoring functions ──────────────────────────────────────────────────────────

def token_score(student: Student, folder: FolderEntry) -> float:
    """
    Surname-priority token overlap.
    All surname tokens must be present (hard gate); firstname overlap raises
    score from 0.65 → 1.0.
    """
    s_set = frozenset(student.surname_tokens)
    if not s_set or not s_set.issubset(folder.tokens):
        return 0.0
    f_tokens = student.all_tokens - s_set
    if not f_tokens:
        return 0.65
    return 0.65 + 0.35 * (len(f_tokens & folder.tokens) / len(f_tokens))


def fuzzy_score(student: Student, folder: FolderEntry) -> float:
    return SequenceMatcher(None, student.full_norm, folder.norm_name).ratio()


# ── 3-pass matcher ────────────────────────────────────────────────────────────

def match_students(
    students:        list[Student],
    folders:         list[FolderEntry],
    fuzzy_threshold: Optional[int] = None,
) -> tuple[list[MatchResult], list[FolderEntry]]:
    """
    Pass 1 — exact normalised string match
    Pass 2 — surname-priority token overlap  (score ≥ 0.65)
    Pass 3 — difflib fuzzy ratio             (optional; threshold 0-100)

    Returns (results_per_student, unmatched_folders).
    """
    exact_map = {f.norm_name: f for f in folders}
    results: list[MatchResult] = []

    for student in students:
        # Pass 1
        f = exact_map.get(student.full_norm)
        if f and not f.claimed:
            f.claimed = True
            results.append(MatchResult(student, f, "exact", 1.0)); continue

        # Pass 2
        best_score, best_folder = 0.0, None
        for f in folders:
            if f.claimed: continue
            sc = token_score(student, f)
            if sc > best_score: best_score, best_folder = sc, f

        if best_folder and best_score >= 0.65:
            best_folder.claimed = True
            results.append(MatchResult(student, best_folder, "token", best_score)); continue

        # Pass 3
        if fuzzy_threshold is not None:
            thresh = fuzzy_threshold / 100.0
            for f in folders:
                if f.claimed: continue
                sc = fuzzy_score(student, f)
                if sc > best_score: best_score, best_folder = sc, f
            if best_folder and best_score >= thresh:
                best_folder.claimed = True
                results.append(MatchResult(student, best_folder, "fuzzy", best_score)); continue

        results.append(MatchResult(student, None, "missing", 0.0))

    return results, [f for f in folders if not f.claimed]
