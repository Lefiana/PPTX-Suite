"""
phases/phase1/mappings.py
Pure-data constants shared by folder_classifier.py and file_operations.py.
No tkinter, no I/O — safe to import anywhere.
"""

COLLEGE_KEYWORDS: tuple = (
    "bachelor", "associate", "bs ", "ba ", "bm ", "ab ",
    "bpe", "bpa", "bsed", "beed", "bscrim", "bsn ", "bsme",
)

SHS_KEYWORDS: tuple = (
    "senior high", "shs", "grade 11", "grade 12",
    "strand", "stem", "abm", "humss", "tvl", "gas",
)

# Maps programme_type → default destination sub-folder name
DEST_LABELS: dict[str, str] = {
    "college": "College_Graduates",
    "shs":     "SHS_Graduates",
    "other":   "Other_Graduates",
    "all":     "Graduates",
}

# Surname prefix tokens (used by name parser)
SURNAME_PREFIXES: frozenset = frozenset({
    "de", "dela", "del", "de la", "de los", "delos",
    "san", "santa", "sto", "sta",
})
