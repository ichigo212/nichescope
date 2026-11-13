"""Small helpers shared across the package."""
from __future__ import annotations

import json
import os
import re
import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

Reporter = Callable[[str], None]


def silent(_: str) -> None:
    """A progress reporter that discards messages."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def days_ago_iso(days: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=float(days))).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(iso: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def hours_since(iso: str | None, now: datetime | None = None) -> float:
    then = parse_time(iso)
    if then is None:
        return float("inf")
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return ((now or datetime.now(timezone.utc)) - then) / timedelta(hours=1)


def days_since(iso: str | None, now: datetime | None = None) -> float:
    return hours_since(iso, now) / 24


def write_json(path: Path, data: Any, indent: int | None = 1) -> None:
    """Write JSON atomically: a crash never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=indent), encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def plain(text: str | None) -> str:
    """Lowercase letters and digits only, for loose name comparison."""
    return re.sub(r"[^a-z0-9]", "", str(text or "").lower())


def clean(text: str | None) -> str:
    """Lowercase words separated by single spaces."""
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").casefold()).strip()
