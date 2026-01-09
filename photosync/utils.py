import os
from pathlib import Path


def is_hidden_path(p: str) -> bool:
    """Return True if any path component starts with a dot.

    Uses realpath() to canonicalize path; falls back to basename check on error.
    """
    if not p:
        return False
    try:
        rp = os.path.realpath(p)
        parts = Path(rp).parts
        return any(part.startswith(".") for part in parts)
    except Exception:
        return Path(p).name.startswith(".")
