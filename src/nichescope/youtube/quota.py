"""A local estimate of the YouTube Data API quota spent today.

The quota day resets at midnight US Pacific time.
"""
from __future__ import annotations

import calendar
import threading
import time

from ..config import settings
from ..util import read_json, write_json

_lock = threading.Lock()


def _pacific_offset(t: float) -> int:
    """UTC offset of US Pacific time at epoch `t` (-7 in daylight time, else -8)."""
    year = time.gmtime(t).tm_year

    def sunday(month: int, nth: int) -> int:
        first = calendar.weekday(year, month, 1)
        return 1 + (6 - first) % 7 + 7 * (nth - 1)

    start = calendar.timegm((year, 3, sunday(3, 2), 10, 0, 0))
    end = calendar.timegm((year, 11, sunday(11, 1), 9, 0, 0))
    return -7 if start <= t < end else -8


def quota_day(t: float | None = None) -> str:
    t = time.time() if t is None else t
    return time.strftime("%Y-%m-%d", time.gmtime(t + _pacific_offset(t) * 3600))


def spend(units: int = 1) -> int:
    """Record units spent. Returns the total used today."""
    path = settings().quota_file
    with _lock:
        d = read_json(path, {}) or {}
        day = quota_day()
        if d.get("day") != day:
            d = {"day": day, "used": 0}
        d["used"] = int(d.get("used", 0)) + units
        write_json(path, d, indent=None)
        return d["used"]


def left() -> int:
    d = read_json(settings().quota_file, {}) or {}
    used = int(d.get("used", 0)) if d.get("day") == quota_day() else 0
    return max(0, settings().quota_per_day - used)
