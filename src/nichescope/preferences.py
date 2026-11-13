"""User preferences stored in the data directory."""
from __future__ import annotations

from .config import settings
from .util import read_json, write_json

DEFAULTS = {"auto_refresh": True}


def get() -> dict:
    return {**DEFAULTS, **(read_json(settings().preferences_file, {}) or {})}


def update(**changes) -> dict:
    prefs = get()
    prefs.update({k: v for k, v in changes.items() if k in DEFAULTS and v is not None})
    write_json(settings().preferences_file, prefs, indent=2)
    return prefs
