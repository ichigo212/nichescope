"""The research store: every channel and long-form video the maps have read, in SQLite.

Definitions used in queries:

    outlier   views divided by the channel's usual views. Not computed for videos under
              a day old, or for channels whose usual is below SMALL_USUAL.
    per_day   views divided by age in days.
    gaining   views gained per day between the two most recent reads of a video.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
import statistics
import threading
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np

from .. import ai
from ..config import settings
from ..util import Reporter, silent
from . import storage

log = logging.getLogger(__name__)

SMALL_USUAL = 100
FLOP_MIN_DAYS = 7
LIMIT_MAX = 100
MEANING_TOP = 400
MEANING_FLOOR = 0.55
MEANING_SPREAD = 0.1
GRADES = ("close", "medium", "far", "near", "proven", "any")

SCHEMA = """
CREATE TABLE IF NOT EXISTS channels (
    id TEXT PRIMARY KEY, title TEXT, handle TEXT, avatar TEXT, subscribers INTEGER,
    started_at TEXT, video_count INTEGER, total_views INTEGER, usual REAL,
    views_30d INTEGER, breakout REAL, read_at TEXT, uploads_at TEXT, facts_at TEXT,
    bio TEXT, country TEXT, language TEXT);
CREATE TABLE IF NOT EXISTS videos (
    id TEXT PRIMARY KEY, channel_id TEXT, title TEXT, published_at TEXT, seconds INTEGER,
    views INTEGER, thumbnail TEXT, description TEXT, tags TEXT, first_read TEXT,
    read_at TEXT, language TEXT);
CREATE INDEX IF NOT EXISTS videos_channel ON videos (channel_id);
CREATE INDEX IF NOT EXISTS videos_published ON videos (published_at);
CREATE INDEX IF NOT EXISTS videos_channel_seconds ON videos (channel_id, seconds);
CREATE TABLE IF NOT EXISTS reads (
    video_id TEXT, day TEXT, views INTEGER, PRIMARY KEY (video_id, day));
CREATE TABLE IF NOT EXISTS meanings (
    video_id TEXT PRIMARY KEY, model TEXT, text_hash TEXT, vec BLOB, at TEXT);
CREATE TABLE IF NOT EXISTS channel_meanings (
    channel_id TEXT PRIMARY KEY, model TEXT, text_hash TEXT, vec BLOB, at TEXT);
"""
LATER_COLUMNS = (("channels", "uploads_at"), ("channels", "facts_at"), ("channels", "bio"),
                 ("channels", "country"), ("channels", "language"), ("videos", "language"))
CHANNEL_FIELDS = ("title", "handle", "avatar", "subscribers", "started_at", "video_count",
                  "total_views", "usual", "views_30d", "breakout", "bio", "country", "language")

_ready: set[str] = set()
_vectors: dict[str, tuple] = {}
_vectors_lock = threading.Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _regexp(pattern: str, text: str | None) -> bool:
    return bool(text) and re.search(pattern, text, re.I) is not None


def connect() -> sqlite3.Connection:
    p = str(settings().database)
    con = sqlite3.connect(p, timeout=30)
    con.row_factory = sqlite3.Row
    con.create_function("regexp", 2, _regexp)
    if p not in _ready:
        con.executescript("PRAGMA journal_mode=WAL;" + SCHEMA)
        for table, col in LATER_COLUMNS:
            if col not in {r[1] for r in con.execute(f"PRAGMA table_info({table})")}:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")
        _ready.add(p)
    return con


def text_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------- writing

def _put_channel(con: sqlite3.Connection, cid: str, row: dict, at: str) -> None:
    vals = [row.get(k) for k in CHANNEL_FIELDS]
    if all(v in (None, "") for v in vals):
        return
    keep = ", ".join(f"{k} = COALESCE(NULLIF(excluded.{k}, ''), {k})" for k in CHANNEL_FIELDS)
    con.execute(f"INSERT INTO channels (id, {', '.join(CHANNEL_FIELDS)}, read_at) "
                f"VALUES (?, {', '.join('?' * len(CHANNEL_FIELDS))}, ?) "
                f"ON CONFLICT(id) DO UPDATE SET {keep}, read_at = MAX(excluded.read_at, read_at)",
                [cid, *vals, at])
    if "bio" in row:
        con.execute("UPDATE channels SET facts_at = ? WHERE id = ?", [at, cid])


def _put_videos(con: sqlite3.Connection, cid: str, videos: Iterable[dict] | None, at: str) -> None:
    for v in videos or ():
        if not v.get("id"):
            continue
        con.execute(
            "INSERT INTO videos (id, channel_id, title, published_at, seconds, views, thumbnail,"
            " description, tags, first_read, read_at, language) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET title = excluded.title, seconds = excluded.seconds,"
            " thumbnail = COALESCE(NULLIF(excluded.thumbnail, ''), thumbnail),"
            " description = COALESCE(NULLIF(excluded.description, ''), description),"
            " tags = COALESCE(NULLIF(excluded.tags, '[]'), tags),"
            " language = COALESCE(NULLIF(excluded.language, ''), language),"
            " views = CASE WHEN excluded.read_at >= read_at THEN excluded.views ELSE views END,"
            " read_at = MAX(excluded.read_at, read_at),"
            " first_read = MIN(excluded.first_read, first_read)",
            [v["id"], cid, v.get("title", ""), v.get("published_at", ""), int(v.get("seconds") or 0),
             int(v.get("views") or 0), v.get("thumbnail", ""), (v.get("description") or "")[:600],
             json.dumps(v.get("tags") or [], ensure_ascii=False), at, at, v.get("language") or ""])
        con.execute("INSERT INTO reads (video_id, day, views) VALUES (?,?,?) "
                    "ON CONFLICT(video_id, day) DO UPDATE SET views = MAX(excluded.views, views)",
                    [v["id"], at[:10], int(v.get("views") or 0)])


def remember(cid: str, info: dict | None = None, videos: list[dict] | None = None,
             measured: dict | None = None, at: str | None = None) -> None:
    """Store a channel and the videos just read. Failures are logged, never raised."""
    try:
        at = at or now_iso()
        row = {**(info or {}), **{k: (measured or {}).get(k) for k in ("usual", "views_30d", "breakout")
                                  if (measured or {}).get(k) is not None}}
        row.pop("uploads", None)
        with connect() as con:
            _put_channel(con, cid, row, at)
            _put_videos(con, cid, videos, at)
            if videos is not None:
                con.execute("UPDATE channels SET uploads_at = ? WHERE id = ?", [at, cid])
            con.execute("UPDATE channels SET language = (SELECT language FROM videos WHERE channel_id = ?1 "
                        "AND language <> '' GROUP BY language ORDER BY COUNT(*) DESC LIMIT 1) "
                        "WHERE id = ?1 AND (language IS NULL OR language = '')", [cid])
    except sqlite3.Error as e:
        log.warning("could not store channel %s: %s", cid, e)


def import_maps() -> dict:
    """Copy everything held in map files into the store. Makes no requests."""
    n_ch = n_v = 0
    with connect() as con:
        for m in storage.all_maps():
            at = m.get("scanned_at") or now_iso()
            _put_channel(con, m["channel_id"], m, at)
            _put_videos(con, m["channel_id"], m.get("videos"), at)
            n_ch += 1
            n_v += len(m.get("videos") or [])
            for cid, c in m["channels"].items():
                if not c.get("title"):
                    continue
                when = c.get("fetched_at") or at
                _put_channel(con, cid, c, when)
                _put_videos(con, cid, c.get("breakouts"), when)
                n_ch += 1
                n_v += len(c.get("breakouts") or [])
    return {"channels": n_ch, "videos": n_v}


def stats() -> dict:
    model = settings().embed_model
    with connect() as con:
        q = lambda sql, *a: con.execute(sql, a).fetchone()  # noqa: E731
        v = q("SELECT COUNT(*), MIN(published_at), MAX(read_at) FROM videos")
        return {"channels": q("SELECT COUNT(*) FROM channels")[0],
                "channels_with_videos": q("SELECT COUNT(DISTINCT channel_id) FROM videos")[0],
                "channels_read_in_full": q("SELECT COUNT(*) FROM channels WHERE uploads_at IS NOT NULL")[0],
                "videos": v[0],
                "videos_with_meaning": q("SELECT COUNT(*) FROM meanings m JOIN videos v ON v.id = m.video_id "
                                         "WHERE m.model = ?", model)[0],
                "oldest_video": (v[1] or "")[:10], "last_read": v[2] or "",
                "days_of_reads": q("SELECT COUNT(DISTINCT day) FROM reads")[0]}


# ---------------------------------------------------------------- map relationships

def near_ids(m: dict, grade: str = "any", steps: int | None = None) -> set[str]:
    """Channel ids of one map, limited to a grade and to `steps` steps from the mapped
    channel (1 = its direct neighbours). Off-niche channels are excluded."""
    from .relevance import relevant_channels

    if grade not in GRADES:
        raise ValueError(f"grade must be one of: {', '.join(GRADES)}")
    rows = {c: r for c, r in relevant_channels(m).items() if not r.get("off")}
    if grade == "proven":
        rows.update({c: r for c, r in m["channels"].items() if r.get("proven")})
    if steps:
        rows = {c: r for c, r in rows.items() if (r.get("step") or 0) < int(steps)}
    if grade == "proven":
        return {c for c, r in rows.items() if r.get("proven")}
    if grade == "near":
        return {c for c, r in rows.items() if r.get("grade") in ("close", "medium") or r.get("proven")}
    if grade == "any":
        return set(rows)
    return {c for c, r in rows.items() if r.get("grade") == grade}


def where_seen(cid: str, maps: list[dict]) -> list[dict]:
    """Which maps hold a channel, and how close each one places it."""
    out = []
    for m in maps:
        r = m["channels"].get(cid)
        if r:
            out.append({"map": m["title"], "map_id": m["channel_id"], "grade": r.get("grade"),
                        "coverage": r.get("coverage") or 0, "proven": r.get("proven") or 0,
                        "off": bool(r.get("off"))})
    return out


def points_to(cid: str, maps: list[dict] | None = None) -> list[dict]:
    """Channels whose videos YouTube recommends this channel beside, strongest first.

    For a connected channel, `real_views` is the measured number of views each source
    channel sent through Suggested videos.
    """
    maps = maps if maps is not None else storage.all_maps()
    names: dict[str, str] = {}
    seen: dict[str, dict] = {}
    for m in maps:
        names[m["channel_id"]] = m["title"]
        for c, r in m["channels"].items():
            if r.get("title"):
                names.setdefault(c, r["title"])
        pairs = [(m["channel_id"], cid, (m["channels"].get(cid) or {}).get("coverage") or 0)]
        pairs += [(x["a"], x["b"], x.get("coverage") or 0) for x in m.get("links", [])]
        for a, b, cov in pairs:
            if b != cid or a == cid or cov <= 0:
                continue
            row = seen.setdefault(a, {"id": a, "coverage": 0, "maps": set()})
            row["coverage"] = max(row["coverage"], cov)
            row["maps"].add(m["channel_id"])
        if m["channel_id"] == cid:
            for c, r in m["channels"].items():
                if r.get("proven"):
                    seen.setdefault(c, {"id": c, "coverage": 0, "maps": set()})["real_views"] = r["proven"]
    rows = [{"id": r["id"], "title": names.get(r["id"], r["id"]), "real_views": r.get("real_views"),
             "coverage": r["coverage"], "maps": len(r["maps"])} for r in seen.values()]
    return sorted(rows, key=lambda r: (-(r["real_views"] or 0), -r["coverage"], -r["maps"], r["title"]))


# ---------------------------------------------------------------- query helpers

def _regex(pattern: str | None, what: str) -> str | None:
    if pattern in (None, ""):
        return None
    if len(pattern) > 500:
        raise ValueError(f"{what} is too long (500 characters at most)")
    try:
        re.compile(pattern)
    except re.error as e:
        raise ValueError(f"{what} is not a valid regular expression: {e}") from e
    return pattern


def pattern_regex(pattern: str | None) -> str | None:
    """A title pattern with * wildcards, such as "I * for * days", as a regular expression."""
    pattern = str(pattern or "").strip()
    if not pattern:
        return None
    return "^" + ".*".join(re.escape(p) for p in pattern.split("*")) + "$"


def _words(words: Any) -> list[str]:
    if isinstance(words, str):
        return [w.strip() for w in re.split(r"[,\n]", words) if w.strip()]
    return [str(w).strip() for w in words or [] if str(w).strip()]


def _language(code: Any) -> str:
    code = str(code or "").strip().lower()
    if not re.fullmatch(r"[a-z]{2,3}(-[a-z0-9]{2,8})?", code):
        raise ValueError("language must be a code such as en, es or pt-BR")
    return code.split("-")[0]


def _language_sql(column: str) -> str:
    return f"LOWER({column}) = :lang OR LOWER({column}) LIKE :lang || '-%'"


def _page(limit: Any, offset: Any) -> tuple[int, int]:
    return max(1, min(int(limit or 20), LIMIT_MAX)), max(0, int(offset or 0))


def _since(days: Any, now: datetime) -> str:
    return (now - timedelta(days=float(days))).strftime("%Y-%m-%dT%H:%M:%SZ")


def _with_scope(con: sqlite3.Connection, ids: Iterable[str]) -> None:
    con.execute("CREATE TEMP TABLE IF NOT EXISTS scope (id TEXT PRIMARY KEY)")
    con.execute("DELETE FROM scope")
    con.executemany("INSERT OR IGNORE INTO scope VALUES (?)", [(i,) for i in ids])


def channel_facts(ids: set[str]) -> tuple[dict[str, int], dict[str, str]]:
    """({channel: median long-video minutes}, {channel: language}) for the given channels.

    Reads only the (channel, seconds) index, so it stays fast however large the store is.
    """
    by: dict[str, list[int]] = {}
    languages: dict[str, str] = {}
    with connect() as con:
        _with_scope(con, ids)
        for cid, sec in con.execute("SELECT channel_id, seconds FROM videos INDEXED BY videos_channel_seconds "
                                    "WHERE channel_id IN (SELECT id FROM scope) AND seconds > 0"):
            by.setdefault(cid, []).append(sec)
        for cid, lang in con.execute("SELECT id, language FROM channels "
                                     "WHERE id IN (SELECT id FROM scope) AND language <> ''"):
            languages[cid] = (lang or "").split("-")[0].lower()
    return {c: round(statistics.median(v) / 60) for c, v in by.items() if v}, languages


def channel_ids(names: Any) -> set[str]:
    """Channel ids for ids, @handles or exact titles of channels already in the store."""
    items = names if isinstance(names, (list, tuple, set)) else [names]
    out: set[str] = set()
    with connect() as con:
        for n in (str(x).strip() for x in items if str(x).strip()):
            if re.fullmatch(r"UC[\w-]{22}", n):
                out.add(n)
                continue
            rows = con.execute("SELECT id FROM channels WHERE id = ? OR LOWER(LTRIM(handle, '@')) = ? "
                               "OR LOWER(title) = ?", [n, n.lower().lstrip("@"), n.lower()]).fetchall()
            if not rows:
                raise ValueError(f"no channel called {n!r} has been read yet")
            out.update(r["id"] for r in rows)
    return out


def _gaining(con: sqlite3.Connection, ids: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for i in range(0, len(ids), 400):
        part = ids[i:i + 400]
        marks = ",".join("?" * len(part))
        rows = con.execute(f"SELECT video_id, day, views FROM reads WHERE video_id IN ({marks}) "
                           "ORDER BY video_id, day", part).fetchall()
        by: dict[str, list] = {}
        for r in rows:
            by.setdefault(r["video_id"], []).append(r)
        for vid, rs in by.items():
            if len(rs) >= 2:
                a, b = rs[-2], rs[-1]
                days = (datetime.fromisoformat(b["day"]) - datetime.fromisoformat(a["day"])).days
                if days > 0:
                    out[vid] = round((b["views"] - a["views"]) / days)
    return out


# ---------------------------------------------------------------- video search

VIDEO_SELECT = """
SELECT v.id, v.channel_id, v.title, v.published_at, v.seconds, v.views, v.thumbnail,
       v.read_at, c.title AS channel, c.subscribers AS channel_subscribers, c.usual AS usual,
       julianday(:now) - julianday(v.published_at) AS age_days,
       CASE WHEN c.usual >= :small AND julianday(:now) - julianday(v.published_at) >= 1
            THEN ROUND(v.views * 1.0 / c.usual, 1) END AS outlier,
       ROUND(v.views / MAX(julianday(:now) - julianday(v.published_at), 1.0)) AS per_day
FROM videos v JOIN channels c ON c.id = v.channel_id
"""
VIDEO_LANGUAGE = "COALESCE(NULLIF(v.language, ''), c.language)"
VIDEO_SORTS = {"meaning": "similarity DESC",
               "outlier": "outlier IS NULL, outlier DESC, views DESC",
               "flops": "outlier IS NULL, outlier ASC, views ASC",
               "views": "views DESC", "newest": "published_at DESC", "per_day": "per_day DESC"}


def channel_usual(ids: set[str]) -> dict[str, float]:
    """{channel id: usual views} for the given channels that are in the store."""
    ids = [i for i in ids if i]
    if not ids:
        return {}
    with connect() as con:
        return {r[0]: r[1] for r in con.execute(
            f"SELECT id, usual FROM channels WHERE usual IS NOT NULL AND id IN ({','.join('?' * len(ids))})", ids)}


def find_videos(title_pattern=None, title_regex=None, words_any=None, in_channels=None, near=None, grade="any",
                published_within_days=None, published_after=None, published_before=None,
                views_min=None, views_max=None, outlier_min=None, outlier_max=None,
                minutes_min=None, minutes_max=None, channel_subscribers_min=None,
                channel_subscribers_max=None, description_words=None, language=None,
                meaning=None, sort=None, limit=20, offset=0, now=None) -> dict:
    """Search stored long-form videos. -> {total, more, videos}

    near limits the search to one map's channels (by grade). outlier_max finds
    underperformers and skips videos younger than a week. meaning ranks by semantic
    similarity to a description, using videos whose meaning has been computed.
    """
    now = now or datetime.now(timezone.utc)
    meaning = str(meaning or "").strip()
    sort = sort or ("meaning" if meaning else "outlier")
    if sort not in VIDEO_SORTS:
        raise ValueError(f"sort must be one of: {', '.join(VIDEO_SORTS)}")
    if sort == "meaning" and not meaning:
        raise ValueError("sorting by meaning needs a meaning to search for")
    limit, offset = _page(limit, offset)
    inner: list[str] = []
    outer: list[str] = []
    args: dict[str, Any] = {"now": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "small": SMALL_USUAL}

    def add(sql: str, key: str, value: Any, into: list[str] = inner) -> None:
        into.append(sql)
        args[key] = value

    if _regex(title_regex, "title_regex"):
        add("v.title REGEXP :rx", "rx", title_regex)
    if title_pattern:
        add("v.title REGEXP :pattern", "pattern", pattern_regex(title_pattern))
    words = _words(words_any)
    if words:
        add("v.title REGEXP :words", "words", "|".join(re.escape(w) for w in words))
    dwords = _words(description_words)
    if dwords:
        add("(v.description REGEXP :dwords OR v.title REGEXP :dwords)", "dwords",
            "|".join(re.escape(w) for w in dwords))
    if language:
        add(f"({_language_sql(VIDEO_LANGUAGE)})", "lang", _language(language))
    if published_within_days is not None:
        add("v.published_at >= :within", "within", _since(published_within_days, now))
    if published_after:
        add("v.published_at >= :after", "after", str(published_after))
    if published_before:
        add("v.published_at <= :before", "before", str(published_before))
    bounds = {"views_min": ("v.views >=", views_min), "views_max": ("v.views <=", views_max),
              "channel_subscribers_min": ("c.subscribers >=", channel_subscribers_min),
              "channel_subscribers_max": ("c.subscribers <=", channel_subscribers_max)}
    for key, (sql, value) in bounds.items():
        if value is not None:
            add(f"{sql} :{key}", key, value)
    if minutes_min is not None:
        add("v.seconds >= :sec_min", "sec_min", float(minutes_min) * 60)
    if minutes_max is not None:
        add("v.seconds <= :sec_max", "sec_max", float(minutes_max) * 60)
    if outlier_min is not None:
        add("outlier >= :outlier_min", "outlier_min", outlier_min, outer)
    if outlier_max is not None:
        add("outlier <= :outlier_max AND age_days >= :flop_days", "outlier_max", outlier_max, outer)
        args["flop_days"] = FLOP_MIN_DAYS
    ids = near_ids(storage.find(near), grade) if near else None
    if in_channels:
        wanted = channel_ids(_words(in_channels) if isinstance(in_channels, str) else in_channels)
        ids = wanted if ids is None else ids & wanted
    close = None
    if meaning:
        among = None
        if ids is not None:
            with connect() as con:
                _with_scope(con, ids)
                among = {r[0] for r in con.execute("SELECT id FROM videos WHERE channel_id IN (SELECT id FROM scope)")}
        close = closest(meaning, among=among)
    with connect() as con:
        if ids is not None:
            _with_scope(con, ids)
            inner.append("v.channel_id IN (SELECT id FROM scope)")
        sql = (f"SELECT * FROM ({VIDEO_SELECT} {'WHERE ' + ' AND '.join(inner) if inner else ''}) "
               f"{'WHERE ' + ' AND '.join(outer) if outer else ''}")
        if close is not None:
            con.execute("CREATE TEMP TABLE IF NOT EXISTS meant (id TEXT PRIMARY KEY, score REAL)")
            con.execute("DELETE FROM meant")
            con.executemany("INSERT OR IGNORE INTO meant VALUES (?, ?)", close)
            sql = f"SELECT q.*, m.score AS similarity FROM ({sql}) q JOIN meant m ON m.id = q.id"
        total = con.execute(f"SELECT COUNT(*) FROM ({sql})", args).fetchone()[0]
        rows = [dict(r) for r in con.execute(
            f"{sql} ORDER BY {VIDEO_SORTS[sort]} LIMIT {limit} OFFSET {offset}", args)]
        gain = _gaining(con, [r["id"] for r in rows])
    for r in rows:
        r["age_days"] = round(r["age_days"], 1) if r["age_days"] is not None else None
        r["gaining"] = gain.get(r["id"])
        r["url"] = f"https://www.youtube.com/watch?v={r['id']}"
    return {"total": total, "more": offset + len(rows) < total, "videos": rows}


# ---------------------------------------------------------------- channel search

CHANNEL_SORTS = {"views_30d": "views_30d DESC", "subscribers": "subscribers DESC",
                 "newest": "started_at IS NULL OR started_at = '', started_at DESC",
                 "breakout": "breakout IS NULL, breakout DESC",
                 "usual": "usual DESC", "matches": "matches DESC, views_30d DESC"}


def find_channels(started_within_days=None, started_after=None, started_before=None,
                  subscribers_min=None, subscribers_max=None, video_count_min=None,
                  video_count_max=None, views_30d_min=None, views_30d_max=None,
                  usual_views_min=None, usual_views_max=None, usual_minutes_min=None,
                  usual_minutes_max=None, breakout_min=None, breakout_within_days=30,
                  title_pattern=None, title_regex=None, title_matches=1, name_regex=None,
                  bio_regex=None, language=None, country=None, near=None, near_steps=None, grade="any",
                  sort="views_30d", limit=20, offset=0, now=None) -> dict:
    """Search stored channels by age, size, recent views, breakouts and title patterns.

    breakout is the channel's largest outlier among videos published within
    breakout_within_days. title_regex counts matching titles; a channel needs
    title_matches of them; title_pattern does the same with * wildcards. near limits
    the search to one map's channels, within near_steps steps. sort "closest" orders by
    closeness on that map.
    """
    now = now or datetime.now(timezone.utc)
    if sort not in CHANNEL_SORTS and sort != "closest":
        raise ValueError(f"sort must be one of: {', '.join([*CHANNEL_SORTS, 'closest'])}")
    if sort == "closest" and not near:
        raise ValueError("sorting by closeness needs a map (near)")
    limit, offset = _page(limit, offset)
    args: dict[str, Any] = {"now": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "small": SMALL_USUAL,
                            "since": _since(max(1, min(float(breakout_within_days or 30), 3650)), now),
                            "rx": _regex(title_regex, "title_regex") or pattern_regex(title_pattern) or ""}
    inner: list[str] = []
    outer: list[str] = []

    def add(sql: str, key: str, value: Any, into: list[str] = inner) -> None:
        into.append(sql)
        args[key] = value

    if started_within_days is not None:
        add("c.started_at >= :started", "started", _since(started_within_days, now))
    if started_after:
        add("c.started_at >= :started_after", "started_after", str(started_after))
    if started_before:
        add("c.started_at <> '' AND c.started_at <= :started_before", "started_before", str(started_before))
    bounds = {"subscribers_min": ("c.subscribers >=", subscribers_min),
              "subscribers_max": ("c.subscribers <=", subscribers_max),
              "video_count_min": ("c.video_count >=", video_count_min),
              "video_count_max": ("c.video_count <=", video_count_max),
              "views_30d_min": ("c.views_30d >=", views_30d_min),
              "views_30d_max": ("c.views_30d <=", views_30d_max),
              "usual_views_min": ("c.usual >=", usual_views_min),
              "usual_views_max": ("c.usual <=", usual_views_max)}
    for key, (sql, value) in bounds.items():
        if value is not None:
            add(f"{sql} :{key}", key, value)
    if _regex(name_regex, "name_regex"):
        add("c.title REGEXP :name_rx", "name_rx", name_regex)
    if _regex(bio_regex, "bio_regex"):
        add("c.bio REGEXP :bio_rx", "bio_rx", bio_regex)
    if language:
        add(f"({_language_sql('c.language')})", "lang", _language(language))
    if country:
        if not re.fullmatch(r"[A-Za-z]{2}", str(country).strip()):
            raise ValueError("country must be a two-letter code such as US")
        add("UPPER(c.country) = :country", "country", str(country).strip().upper())
    if breakout_min is not None:
        add("breakout >= :breakout_min", "breakout_min", breakout_min, outer)
    if usual_minutes_min is not None:
        add("minutes >= :usual_minutes_min", "usual_minutes_min", usual_minutes_min, outer)
    if usual_minutes_max is not None:
        add("minutes <= :usual_minutes_max", "usual_minutes_max", usual_minutes_max, outer)
    if title_regex or title_pattern:
        add("matches >= :title_matches", "title_matches", max(1, int(title_matches or 1)), outer)
    maps = storage.all_maps()
    near_map = storage.find(near, maps) if near else None
    ids = near_ids(near_map, grade, near_steps) if near_map else None
    select = """
        SELECT c.id, c.title, c.handle, c.avatar, c.subscribers, c.started_at, c.video_count,
               c.total_views, c.usual, c.views_30d, c.read_at, c.country, c.language,
               SUBSTR(c.bio, 1, 300) AS bio,
               (SELECT COUNT(*) FROM videos v WHERE v.channel_id = c.id) AS videos_kept,
               (SELECT ROUND(AVG(v.seconds) / 60.0) FROM videos v WHERE v.channel_id = c.id) AS minutes,
               (SELECT MAX(ROUND(v.views * 1.0 / c.usual, 1)) FROM videos v
                 WHERE v.channel_id = c.id AND c.usual >= :small AND v.published_at >= :since
                   AND julianday(:now) - julianday(v.published_at) >= 1) AS breakout,
               CASE WHEN :rx = '' THEN 0 ELSE
                 (SELECT COUNT(*) FROM videos v WHERE v.channel_id = c.id AND v.title REGEXP :rx)
               END AS matches
        FROM channels c"""
    with connect() as con:
        if ids is not None:
            _with_scope(con, ids)
            inner.append("c.id IN (SELECT id FROM scope)")
        sql = (f"SELECT * FROM ({select} {'WHERE ' + ' AND '.join(inner) if inner else ''}) "
               f"{'WHERE ' + ' AND '.join(outer) if outer else ''}")
        total = con.execute(f"SELECT COUNT(*) FROM ({sql})", args).fetchone()[0]
        if sort == "closest":
            rows = [dict(r) for r in con.execute(sql, args)]
            rank = near_map["channels"]
            rows.sort(key=lambda r: (-(rank.get(r["id"], {}).get("proven") or 0),
                                     -(rank.get(r["id"], {}).get("coverage") or 0),
                                     -(r["views_30d"] or 0)))
            rows = rows[offset:offset + limit]
        else:
            rows = [dict(r) for r in con.execute(
                f"{sql} ORDER BY {CHANNEL_SORTS[sort]} LIMIT {limit} OFFSET {offset}", args)]
        for r in rows:
            top = con.execute(
                "SELECT id, title, views, published_at, thumbnail FROM videos WHERE channel_id = ? "
                "AND published_at >= ? ORDER BY views DESC LIMIT 1", [r["id"], args["since"]]).fetchone()
            r["breakout_video"] = dict(top) if top and r["breakout"] else None
    for r in rows:
        r["maps"] = where_seen(r["id"], maps)
        r["url"] = f"https://www.youtube.com/channel/{r['id']}"
    return {"total": total, "more": offset + len(rows) < total, "channels": rows}


def channel_profile(channel: str) -> dict:
    """One stored channel with its latest, most viewed and biggest-outlier videos."""
    cid = next(iter(channel_ids([channel])))
    maps = storage.all_maps()
    with connect() as con:
        row = con.execute("SELECT * FROM channels WHERE id = ?", [cid]).fetchone()
    if not row:
        raise ValueError(f"channel {channel!r} has not been read yet")
    pick = lambda sort, n: find_videos(in_channels=[cid], sort=sort, limit=n)["videos"]  # noqa: E731
    return {**dict(row), "url": f"https://www.youtube.com/channel/{cid}",
            "latest_videos": pick("newest", 30), "popular_videos": pick("views", 10),
            "biggest_outliers": pick("outlier", 10), "maps": where_seen(cid, maps),
            "points_to": points_to(cid, maps)[:20]}


# ---------------------------------------------------------------- meanings

def _meaning_text(title: str | None, description: str | None) -> str:
    return (str(title or "").strip() + "\n" + str(description or "").strip()[:600]).strip()


def fill_meanings(report: Reporter = silent, limit: int | None = None) -> dict:
    """Embed every stored video that has no meaning yet or whose text changed."""
    model = settings().embed_model
    with connect() as con:
        have = {r[0]: r[1] for r in con.execute(
            "SELECT video_id, text_hash FROM meanings WHERE model = ?", [model])}
        rows = con.execute("SELECT id, title, description FROM videos ORDER BY published_at DESC").fetchall()
    todo = []
    for r in rows:
        text = _meaning_text(r["title"], r["description"])
        if text and have.get(r["id"]) != text_hash(text):
            todo.append((r["id"], text))
    pending = len(todo)
    if limit is not None:
        todo = todo[:max(0, int(limit))]
    if todo:
        report(f"computing the meaning of {len(todo)} videos")
    done = failed = 0
    for i in range(0, len(todo), 200):
        part = todo[i:i + 200]
        vecs = ai.embed([t for _, t in part], report=report)
        at = now_iso()
        put = [(vid, model, text_hash(text), np.asarray(v, dtype=np.float32).tobytes(), at)
               for (vid, text), v in zip(part, vecs, strict=True) if v]
        failed += len(part) - len(put)
        done += len(put)
        with connect() as con:
            con.executemany("INSERT OR REPLACE INTO meanings VALUES (?, ?, ?, ?, ?)", put)
        report(f"computed {done} of {len(todo)}")
    with _vectors_lock:
        _vectors.pop(str(settings().database), None)
    return {"read": done, "failed": failed, "left": pending - done}


def matrix() -> tuple[list[str], np.ndarray]:
    """(video ids, unit vectors) of every stored meaning, cached until the store changes."""
    p = str(settings().database)
    model = settings().embed_model
    with connect() as con:
        key = tuple(con.execute("SELECT COUNT(*), MAX(at) FROM meanings WHERE model = ?", [model]).fetchone())
        with _vectors_lock:
            if p in _vectors and _vectors[p][0] == key:
                return _vectors[p][1], _vectors[p][2]
        rows = con.execute("SELECT video_id, vec FROM meanings WHERE model = ?", [model]).fetchall()
    sizes: dict[int, int] = {}
    for r in rows:
        sizes[len(r[1])] = sizes.get(len(r[1]), 0) + 1
    size = max(sizes, key=sizes.get) if sizes else 0
    rows = [r for r in rows if len(r[1]) == size]
    ids = [r[0] for r in rows]
    mat = (np.vstack([np.frombuffer(r[1], dtype=np.float32) for r in rows])
           if rows else np.zeros((0, 1), dtype=np.float32))
    if ids:
        mat = mat / np.maximum(np.linalg.norm(mat, axis=1, keepdims=True), 1e-9)
    with _vectors_lock:
        _vectors[p] = (key, ids, mat)
    return ids, mat


def closest(meaning: str, top: int = MEANING_TOP, floor: float = MEANING_FLOOR,
            among: set[str] | None = None) -> list[tuple[str, float]]:
    """[(video id, similarity)] of the videos closest in meaning to a description,
    optionally only among the given videos."""
    ids, mat = matrix()
    if not ids:
        raise ValueError("no video meanings have been computed yet; run 'Compute meanings' first")
    if among is not None:
        keep = [i for i, v in enumerate(ids) if v in among]
        if not keep:
            return []
        ids, mat = [ids[i] for i in keep], mat[keep]
    q = ai.embed([str(meaning)[:2000]], query=True)[0]
    if not q:
        raise RuntimeError("the search text could not be embedded; try again")
    vec = np.asarray(q, dtype=np.float32)
    vec = vec / max(float(np.linalg.norm(vec)), 1e-9)
    score = mat @ vec
    best = np.argsort(-score)[:max(1, int(top))]
    floor = max(floor, float(score[best[0]]) - MEANING_SPREAD)
    return [(ids[i], round(float(score[i]), 3)) for i in best if score[i] >= floor]
