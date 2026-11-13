"""Map files: one JSON document per mapped channel, under `<data>/maps`."""
from __future__ import annotations

import hashlib
import logging
import threading
import uuid
from datetime import datetime
from pathlib import Path

from ..config import settings
from ..util import read_json, write_json

log = logging.getLogger(__name__)

_locks: dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()


class MapNotFound(LookupError):
    pass


def lock(channel_id: str) -> threading.RLock:
    """A per-map lock for read-modify-write sequences."""
    with _locks_guard:
        return _locks.setdefault(channel_id, threading.RLock())


def path(channel_id: str) -> Path:
    return settings().maps_dir / f"{channel_id}.json"


def _upgrade(m: dict) -> dict:
    """Fill defaults and migrate fields from older map files."""
    m.setdefault("channels", {})
    m.setdefault("links", [])
    m.setdefault("expanded", [])
    m.setdefault("expanded_at", {})
    m.setdefault("topics", [])
    m.setdefault("saved_topics", [])
    m.setdefault("chats", [])
    m.setdefault("marks", {"topics": {}, "titles": {}})
    m.setdefault("first_scan", m.get("scanned_at"))
    if "answers" in m:
        m["chats"] += [{"id": uuid.uuid4().hex[:12], "at": a["at"], "messages": [
            {"role": "user", "content": a["question"], "images": [], "at": a["at"]},
            {"role": "model", "content": a["answer"], "images": [], "at": a["at"]}]}
            for a in m.pop("answers")]
    for batch in m["topics"]:
        batch.setdefault("id", hashlib.sha1(batch["at"].encode()).hexdigest()[:12])
        batch.setdefault("followups", [])
        batch.setdefault("files", [])
        for t in batch.get("topics", []):
            if "series" in t:
                t["topic"] = t.pop("series")
            for k in ("confirmed", "name"):
                t.pop(k, None)
    for s in m["saved_topics"]:
        if "series" in s:
            s["topic"] = s.pop("series")
        for k in ("confirmed", "name"):
            s.pop(k, None)
    for c in m["channels"].values():
        if c.get("via") and c.get("coverage"):
            c["via_coverage"] = c["coverage"]
            c["coverage"] = c["appearances"] = 0
    return m


def load(channel_id: str) -> dict | None:
    data = read_json(path(channel_id))
    return _upgrade(data) if data else None


def require(channel_id: str) -> dict:
    m = load(channel_id)
    if not m:
        raise MapNotFound("this channel has not been mapped yet")
    return m


def save(m: dict) -> None:
    """Write a map. Channels the user removed are dropped here, whatever added them back."""
    gone = m.get("removed") or {}
    if gone:
        m["channels"] = {c: r for c, r in m["channels"].items() if c not in gone}
        m["links"] = [x for x in m.get("links", []) if x["a"] not in gone and x["b"] not in gone]
        m["expanded"] = [c for c in m.get("expanded", []) if c not in gone]
    write_json(path(m["channel_id"]), m)


def saved() -> list[dict]:
    """Every map, newest scan first: [{channel_id, title, avatar, scanned_at}]."""
    out = []
    for p in settings().maps_dir.glob("*.json"):
        m = read_json(p)
        if not m or "channel_id" not in m:
            log.warning("unreadable map file %s", p.name)
            continue
        out.append({"channel_id": m["channel_id"], "title": m.get("title", ""),
                    "avatar": m.get("avatar", ""), "scanned_at": m.get("scanned_at", "")})
    return sorted(out, key=lambda r: r["scanned_at"], reverse=True)


def all_maps() -> list[dict]:
    return [m for m in (load(s["channel_id"]) for s in saved()) if m]


def find(name: str, maps: list[dict] | None = None) -> dict:
    """A map by channel id, @handle or title."""
    maps = maps if maps is not None else all_maps()
    want = str(name or "").strip().lower().lstrip("@")
    for m in maps:
        if want in (m["channel_id"].lower(), (m.get("handle") or "").lower().lstrip("@"), m["title"].lower()):
            return m
    hits = [m for m in maps if want and want in m["title"].lower()]
    if len(hits) == 1:
        return hits[0]
    names = ", ".join(m["title"] for m in maps) or "none yet"
    raise MapNotFound(f"no map is called {name!r}. Maps: {names}")


def remove(channel_id: str) -> str:
    """Move a map to the removed folder. Returns the file name it was kept under."""
    p = path(channel_id)
    if not p.exists():
        raise MapNotFound("there is no map for that channel")
    out = settings().removed_dir / f"{channel_id}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    p.replace(out)
    return out.name


def removed() -> list[dict]:
    """Removed maps, newest first: [{file, channel_id, title, avatar, at}]."""
    out = []
    for p in settings().removed_dir.glob("*.json"):
        m = read_json(p)
        try:
            when = datetime.strptime(p.stem.rsplit(".", 1)[-1], "%Y%m%d_%H%M%S").astimezone()
        except ValueError:
            continue
        if m and "channel_id" in m:
            out.append({"file": p.name, "channel_id": m["channel_id"], "title": m.get("title", ""),
                        "avatar": m.get("avatar", ""), "at": when.isoformat(timespec="seconds")})
    return sorted(out, key=lambda r: r["at"], reverse=True)


def restore(file: str) -> str:
    """Put a removed map back. Returns its channel id."""
    p = settings().removed_dir / Path(str(file)).name
    m = read_json(p)
    if not m:
        raise MapNotFound("that removed map no longer exists")
    if path(m["channel_id"]).exists():
        raise ValueError("this channel has been mapped again since; remove the newer map first")
    p.replace(path(m["channel_id"]))
    return m["channel_id"]
