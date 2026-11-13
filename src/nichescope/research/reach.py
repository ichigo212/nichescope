"""Impressions and click-through rate per video, from YouTube Studio's export.

The Analytics API does not report impressions for a channel's videos, so they come from
Studio: Analytics, Advanced mode, Export current view, then upload the CSV (or the zip it
comes in) here. The rows are kept per channel and joined to its videos when its map is
shown.
"""
from __future__ import annotations

import csv
import io
import re
import zipfile

from ..config import settings
from ..util import read_json, utc_now, write_json

MAX_BYTES = 5_000_000
VIDEO_ID = re.compile(r"^[\w-]{11}$")


class ReachFileError(ValueError):
    pass


def _number(text: str) -> float | None:
    t = (text or "").strip().replace(",", "").replace("%", "")
    try:
        return float(t)
    except ValueError:
        return None


def _table(data: bytes) -> str:
    """The CSV text holding per-video rows, from a CSV file or Studio's zip."""
    if data[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names = [n for n in z.namelist() if n.lower().endswith(".csv")]
                for name in sorted(names, key=lambda n: "table" not in n.lower()):
                    text = z.read(name).decode("utf-8-sig", "replace")
                    if "impressions" in text.splitlines()[0].lower():
                        return text
        except zipfile.BadZipFile:
            raise ReachFileError("that zip file could not be opened") from None
        raise ReachFileError("the zip has no table with an Impressions column")
    return data.decode("utf-8-sig", "replace")


def parse(data: bytes) -> dict[str, dict]:
    """{video id: {impressions, ctr, views}} from Studio's exported table."""
    if len(data) > MAX_BYTES:
        raise ReachFileError("that file is too large for a Studio export")
    rows = list(csv.reader(io.StringIO(_table(data))))
    if not rows:
        raise ReachFileError("the file is empty")
    head = [h.strip().lower() for h in rows[0]]

    def column(test) -> int | None:
        return next((i for i, h in enumerate(head) if test(h)), None)

    vid = column(lambda h: h in ("content", "video", "video id"))
    ctr = column(lambda h: "click-through" in h or "click through" in h)
    shown = column(lambda h: h == "impressions" or h.startswith("impressions ("))
    views = column(lambda h: h == "views")
    if vid is None or ctr is None or shown is None:
        raise ReachFileError("this is not Studio's table export: it needs Content, Impressions and "
                             "Impressions click-through rate columns. In Studio, open Analytics, Advanced "
                             "mode, add Impressions and click-through rate, then Export")
    out: dict[str, dict] = {}
    for r in rows[1:]:
        if len(r) <= max(vid, ctr, shown) or not VIDEO_ID.match(r[vid].strip()):
            continue
        out[r[vid].strip()] = {"impressions": int(_number(r[shown]) or 0), "ctr": _number(r[ctr]),
                               "views": int(_number(r[views]) or 0) if views is not None else None}
    if not out:
        raise ReachFileError("no video rows were found in the file")
    return out


def _path(channel_id: str):
    return settings().accounts_dir / f"{channel_id}.reach.json"


def save(channel_id: str, videos: dict[str, dict]) -> dict:
    got = {"at": utc_now(), "videos": videos}
    write_json(_path(channel_id), got)
    return got


def load(channel_id: str) -> dict | None:
    return read_json(_path(channel_id))
