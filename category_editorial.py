"""Editorial copy for national shortage category pages (routes/kategori.py).

Optional, hand-maintained per-ATC-code title/intro text, read from
category_editorial.json (repo root) -- the same plain-file editorial pattern
as checker.py's PRODUCTS list, no admin UI. Johan edits the JSON file
directly to add/update entries.

Missing/corrupt file degrades to an empty dict instead of crashing the app
(this is a nice-to-have complement, not core data) -- same defensive style
as shortage.py's load_snapshot().
"""

import json
import os

_PATH = os.path.join(os.path.dirname(__file__), "category_editorial.json")

_cache = None  # module-level cache, populated on first load_editorial() call


def load_editorial():
    """Load and cache category_editorial.json. Safe to call repeatedly --
    only reads the file once per process."""
    global _cache
    if _cache is not None:
        return _cache

    try:
        with open(_PATH, encoding="utf-8") as f:
            _cache = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"  category_editorial.py: kunde inte läsa {_PATH}: {e}")
        _cache = {}

    return _cache


def get_editorial(atc_code):
    """Return the {"title": ..., "intro": ...} dict for this ATC code, or
    None if there's no editorial entry for it (the common case -- most
    categories are auto-generated from atc_term alone)."""
    return load_editorial().get(atc_code)
