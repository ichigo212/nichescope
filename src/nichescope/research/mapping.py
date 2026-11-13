"""Building niche maps from YouTube's recommendations.

Scan: read the up-next list beside a channel's latest long-form videos. A channel that
appears beside many of them is a neighbour; `coverage` is the share of videos it
appeared beside:

    close   coverage >= 0.5
    medium  coverage >= 0.2
    far     below that

Every channel keeps the titles YouTube recommended it with. The model judges from them
whether each channel makes the same kind of videos (see relevance.py); far channels
judged the same are read in full, so a small new channel breaking out shows up even
when YouTube recommended it only once.

Deepen: scan around the nearest neighbours too. A channel found around PROMOTE_AT or
more neighbours (two when judged the same) is promoted to medium if it matches the niche.

For a connected channel, analytics adds the channels that actually send it viewers
(see own.py).

Quota: watch, search and channel pages cost nothing. With YOUTUBE_SOURCE=api, channel
details cost about 2 units per channel and are reused for a day.
"""
from __future__ import annotations

import logging
import re
import time
from difflib import SequenceMatcher

import requests

from ..util import Reporter, hours_since, plain, silent, utc_now
from ..youtube import auth, data_api, quota, web
from . import database, metrics, own, relevance, storage

log = logging.getLogger(__name__)

CLOSE, MEDIUM = 0.5, 0.2
GRADES = ("close", "medium", "far")
OWN_UPLOADS_READ = 200
DETAILED_GRADES = ("close", "medium")
DETAIL_FRESH_HOURS = 24
ROOTS_PER_STEP = 8
ROOT_MIN_SUBS = 1000
PROMOTE_AT = 3
PROMOTE_READ = 15
MAX_STEPS = 5
REFRESH_HOURS = 24
REFRESH_ROOTS = 3
REFRESH_MIN_QUOTA = 3000
PROVEN_NEAR = 5
CANDIDATES_READ = 8
SEEN_KEPT = 8
FAR_READ = 40
FAR_READ_API = 10
NAME_CLOSE = 0.85
NAME_PREFIX = 6


class MapError(RuntimeError):
    pass


def grade(coverage: float) -> str:
    if coverage >= CLOSE:
        return "close"
    return "medium" if coverage >= MEDIUM else "far"


# ---------------------------------------------------------------- resolving channels

def resolve(text: str) -> str:
    """A channel id from a link, @handle, channel id or name."""
    t = (text or "").strip()
    if not t:
        raise ValueError("enter a channel name, link or @handle")
    found = re.search(r"(UC[\w-]{22})", t)
    if found:
        return found.group(1)
    found = re.search(r"youtube\.com/@([^/?#\s]+)", t) or re.fullmatch(r"@([^/?#\s]+)", t)
    if found or " " not in t:
        handle = found.group(1) if found else t
        cid = data_api.channel_by_handle(handle)
        if cid:
            return cid
        if found:
            raise ValueError(f"no channel has the handle @{handle}")
    hits = web.search_channels(t)
    if not hits:
        raise ValueError(f"no channel called {t} was found")
    return hits[0]["id"]


def _resolve_in_niche(m: dict, text: str) -> str:
    """A competitor by name, preferring a candidate that matches this map's niche."""
    t = (text or "").strip()
    if re.search(r"UC[\w-]{22}", t) or "youtube.com/" in t or t.startswith("@"):
        return resolve(t)
    ids = [h["id"] for h in web.search_channels(t)]
    if " " not in t:
        try:
            cid = data_api.channel_by_handle(t)
            if cid:
                ids.append(cid)
        except data_api.YouTubeError as e:
            log.warning("handle lookup for %r failed: %s", t, str(e)[:150])
    ids = [i for i in dict.fromkeys(ids) if i != m["channel_id"]][:CANDIDATES_READ]
    if not ids:
        raise ValueError(f"no channel called {t} was found")
    known = m.get("channels") or {}
    info = data_api.channels(ids)
    for i in ids:
        if _same_name((known.get(i) or info.get(i) or {}).get("title", ""), t):
            return i
    for i in ids:
        row = known.get(i) or {"title": (info.get(i) or {}).get("title", "")}
        if relevance.matches_niche(m, row) or relevance.name_fits(m, row.get("title", "")):
            return i
    return ids[0]


# ---------------------------------------------------------------- reading

def _read_pages(videos: list[dict], report: Reporter) -> list[list[dict]]:
    lists = []
    for i, v in enumerate(videos):
        if i:
            time.sleep(web.PAGE_GAP_SEC)
        report(f"reading recommendations beside video {i + 1} of {len(videos)}")
        try:
            rows = web.up_next(v["id"])
        except requests.RequestException as e:
            log.warning("watch page %s failed: %s", v["id"], e)
            continue
        if rows:
            lists.append(rows)
    if not lists:
        raise MapError("YouTube returned no recommendations for these videos; "
                       "it may be limiting requests from this network, so try again later")
    return lists


def tally(lists: list[list[dict]], own_id: str) -> dict[str, int]:
    """{channel id: number of videos it was recommended beside}."""
    counts: dict[str, int] = {}
    for rows in lists:
        for cid in {r["channel_id"] for r in rows} - {own_id}:
            counts[cid] = counts.get(cid, 0) + 1
    return counts


def seen_titles(lists: list[list[dict]], own_id: str) -> dict[str, list[str]]:
    """{channel id: titles of its videos that were recommended}."""
    out: dict[str, list[str]] = {}
    for rows in lists:
        for r in rows:
            if r["channel_id"] != own_id and r.get("title"):
                got = out.setdefault(r["channel_id"], [])
                if r["title"] not in got and len(got) < SEEN_KEPT:
                    got.append(r["title"])
    return out


def _with_seen(row: dict, titles: list[str]) -> None:
    row["seen"] = list(dict.fromkeys([*titles, *(row.get("seen") or [])]))[:SEEN_KEPT]


def _neighbours(lists: list[list[dict]], own_id: str) -> dict[str, dict]:
    read = len(lists)
    seen = seen_titles(lists, own_id)
    return {cid: {"appearances": n, "coverage": round(n / read, 2), "grade": grade(n / read),
                  "seen": seen.get(cid, [])}
            for cid, n in tally(lists, own_id).items()}


def _detail(rows: dict[str, dict], report: Reporter, only: list[str] | None = None,
            any_grade: bool = False) -> None:
    """Fill names for channels, and uploads and breakouts for near ones."""
    want = list(only if only is not None else rows)
    info = data_api.channels(want)
    for cid in want:
        rows[cid].update({k: v for k, v in info.get(cid, {}).items() if k not in ("uploads", "bio")})
        rows[cid].setdefault("title", cid)
    near = [c for c in want if c in info and (any_grade or rows[c].get("grade") in DETAILED_GRADES)
            and (not rows[c].get("topic_samples") or hours_since(rows[c].get("fetched_at")) >= DETAIL_FRESH_HOURS)]
    for i, cid in enumerate(near):
        report(f"reading {info[cid]['title']} ({i + 1} of {len(near)})")
        try:
            videos = data_api.uploads(info[cid]["uploads"])
        except data_api.QuotaExceeded:
            raise
        except data_api.YouTubeError as e:
            log.warning("could not read channel %s: %s", cid, e)
            continue
        rows[cid].update(metrics.measure(videos))
        database.remember(cid, info[cid], videos, rows[cid])
        rows[cid]["topic_samples"] = [{"title": v["title"], "tags": v.get("tags", []),
                                       "description": v.get("description", "")[:180]} for v in videos[:12]]
        rows[cid]["fetched_at"] = utc_now()


def _merge(old: dict | None, fresh: dict[str, dict]) -> dict[str, dict]:
    """Combine a new scan with the previous map, keeping the user's decisions."""
    out = {cid: c for cid, c in (old or {}).items()
           if c.get("added") or c.get("via") or c.get("proven") or c.get("off") or c.get("promoted")}
    kept_keys = ("off", "added", "first_seen", "fetched_at", "usual", "views_30d", "breakouts", "breakout",
                 "title", "handle", "avatar", "subscribers", "proven", "proven_videos", "topic_samples",
                 "topic", "topic_margin", "topic_from", "fit", "fit_n", "fit_read", "via", "via_coverage",
                 "step", "promoted")
    for cid, r in fresh.items():
        was = (old or {}).get(cid, {})
        out[cid] = {**{k: was[k] for k in kept_keys if k in was}, **r}
        before = was.get("grade", "far")
        if (was.get("added") or was.get("promoted")) and GRADES.index(before) < GRADES.index(r["grade"]):
            out[cid]["grade"] = before
        _with_seen(out[cid], [*(r.get("seen") or []), *(was.get("seen") or [])])
    now = utc_now()
    for c in out.values():
        c.setdefault("first_seen", now)
    return out


def _merge_own(m: dict, report: Reporter) -> None:
    """Add a connected channel's measured traffic sources to its map."""
    if not auth.is_own(m["channel_id"]):
        return
    try:
        m["own"] = own.read(m["channel_id"], m["videos"], report)
        m.pop("own_error", None)
    except (data_api.YouTubeError, auth.AuthError) as e:
        log.warning("analytics for %s failed: %s", m["title"], str(e)[:200])
        m["own_error"] = str(e)[:300]
        return
    joined = []
    for cid, c in m["channels"].items():
        if cid not in m["own"]["traffic"]:
            c.pop("proven", None)
            c.pop("proven_videos", None)
    for cid, row in m["own"]["traffic"].items():
        c = m["channels"].get(cid)
        if c is None:
            c = m["channels"][cid] = {"appearances": 0, "coverage": 0, "first_seen": utc_now(),
                                      "title": row["title"],
                                      "grade": "medium" if row["views"] >= PROVEN_NEAR else "far"}
            joined.append(cid)
        elif row["views"] >= PROVEN_NEAR and c.get("grade") == "far":
            c["grade"] = "medium"
            joined.append(cid)
        c["proven"] = row["views"]
        c["proven_videos"] = row["videos"][:5]
    if joined:
        _detail(m["channels"], report, only=joined)


def _read_far(m: dict, report: Reporter) -> None:
    """Read far channels the model judged the same, then unclear ones, most recommended
    first, and judge the unclear ones again from what was read."""
    limit = FAR_READ if data_api.public() else FAR_READ_API
    rank = {"same": 0, "unclear": 1}
    todo = [c for c, r in m["channels"].items()
            if r.get("grade") == "far" and r.get("fit") in rank and not r.get("off")
            and (not r.get("topic_samples") or hours_since(r.get("fetched_at")) >= DETAIL_FRESH_HOURS)]
    todo.sort(key=lambda c: (rank[m["channels"][c]["fit"]], -(m["channels"][c].get("appearances") or 0)))
    if todo[:limit]:
        _detail(m["channels"], report, only=todo[:limit], any_grade=True)
        relevance.classify(m, report, only=todo[:limit])


def _finish(m: dict, report: Reporter) -> dict:
    metrics.remember_history(m)
    relevance.judge(m, report)
    storage.save(m)
    return m


# ---------------------------------------------------------------- operations

def scan(text: str, report: Reporter = silent) -> dict:
    """Map a channel, or rescan it. Keeps channels the user added, removed or set aside."""
    cid = resolve(text)
    me = data_api.channels([cid]).get(cid)
    if not me:
        raise ValueError(f"YouTube has no channel {cid}")
    report(f"reading {me['title']}")
    mine = data_api.uploads(me["uploads"], OWN_UPLOADS_READ if auth.is_own(cid) else data_api.UPLOADS_READ)
    if not mine:
        raise MapError(f"{me['title']} has no long-form videos to read")
    database.remember(cid, me, mine, metrics.measure(mine))
    lists = _read_pages(mine[:metrics.VIDEOS_TO_READ], report)
    with storage.lock(cid):
        old = storage.load(cid) or {}
        rows = _merge(old.get("channels"), _neighbours(lists, cid))
        _detail(rows, report)
        m = storage._upgrade({**old, "channel_id": cid, "title": me["title"], "handle": me["handle"],
                              "avatar": me["avatar"], "subscribers": me["subscribers"],
                              "videos_read": len(lists), "scanned_at": utc_now(), "videos": mine,
                              **metrics.measure(mine), "channels": rows})
        _merge_own(m, report)
        relevance.classify(m, report)
        _read_far(m, report)
        _finish(m, report)
    log.info("mapped %s: %d videos read, %d channels", me["title"], len(lists), len(rows))
    return m


def _expand_one(m: dict, neighbour: str, report: Reporter) -> None:
    """Scan around one neighbour and join what it finds to the map (does not save)."""
    info = data_api.channels([neighbour]).get(neighbour)
    if not info:
        raise ValueError(f"YouTube has no channel {neighbour}")
    report(f"reading around {info['title']}")
    videos = data_api.uploads(info["uploads"])
    if not videos:
        return
    database.remember(neighbour, info, videos, metrics.measure(videos))
    lists = _read_pages(videos[:metrics.VIDEOS_TO_READ], lambda s: report(f"{info['title']}: {s}"))
    found = _neighbours(lists, neighbour)
    step = m["channels"][neighbour].get("step", 0) + 1
    new = {c: {"appearances": 0, "coverage": 0, "via_coverage": r["coverage"], "grade": "far",
               "via": neighbour, "step": step, "first_seen": utc_now(), "seen": r["seen"]}
           for c, r in found.items() if c not in m["channels"] and c != m["channel_id"]}
    for c, r in found.items():
        if c in m["channels"]:
            _with_seen(m["channels"][c], r["seen"])
    if new:
        for k, v in data_api.channels(new).items():
            new[k].update({a: b for a, b in v.items() if a not in ("uploads", "bio")})
        for c in new.values():
            c.setdefault("title", "")
    m["channels"].update(new)
    m["links"] = [x for x in m["links"] if x["a"] != neighbour]
    m["links"] += [{"a": neighbour, "b": c, "coverage": r["coverage"]}
                   for c, r in found.items() if c in m["channels"] and r["grade"] != "far"]
    if neighbour not in m["expanded"]:
        m["expanded"].append(neighbour)
    m["expanded_at"][neighbour] = utc_now()


def _promote(m: dict, report: Reporter) -> None:
    """Promote far channels that several neighbours point at, if they match the niche."""
    relevance.classify(m, report)
    linked: dict[str, int] = {}
    for x in m["links"]:
        linked[x["b"]] = linked.get(x["b"], 0) + 1
    candidates = [c for c, n in linked.items()
                  if m["channels"].get(c, {}).get("grade") == "far"
                  and n >= (PROMOTE_AT - 1 if m["channels"][c].get("fit") == "same" else PROMOTE_AT)]
    unread = sorted((c for c in candidates if not m["channels"][c].get("topic_samples")),
                    key=lambda c: -linked[c])[:PROMOTE_READ]
    if unread:
        _detail(m["channels"], report, only=unread, any_grade=True)
    promoted = [c for c in candidates if relevance.matches_niche(m, m["channels"][c])]
    for c in promoted:
        m["channels"][c]["grade"] = "medium"
        m["channels"][c]["promoted"] = linked[c]
    if promoted:
        _detail(m["channels"], report, only=promoted)
    _read_far(m, report)


def expand(map_id: str, neighbour: str, report: Reporter = silent) -> dict:
    """Map the channels around one neighbour as well."""
    with storage.lock(map_id):
        m = storage.require(map_id)
        if neighbour not in m["channels"]:
            raise ValueError("that channel is not on this map")
        _expand_one(m, neighbour, report)
        _promote(m, report)
        return _finish(m, report)


def _next_roots(m: dict, n: int) -> list[str]:
    rows = [(c, r) for c, r in m["channels"].items()
            if c not in m["expanded"] and not r.get("off") and relevance.matches_niche(m, r)
            and r.get("grade") in DETAILED_GRADES
            and ((r.get("subscribers") or 0) >= ROOT_MIN_SUBS or r.get("proven"))]
    rows.sort(key=lambda x: (x[1].get("proven") or 0, x[1].get("coverage") or 0,
                             x[1].get("subscribers") or 0), reverse=True)
    return [c for c, _ in rows[:n]]


def deepen(map_id: str, steps: int = 1, report: Reporter = silent) -> dict:
    """Follow recommendations outward from the nearest neighbours, up to MAX_STEPS."""
    with storage.lock(map_id):
        m = storage.require(map_id)
        for step in range(1, min(int(steps), MAX_STEPS) + 1):
            roots = _next_roots(m, ROOTS_PER_STEP)
            if not roots:
                break
            for i, root in enumerate(roots):
                report(f"step {step}: {m['channels'][root].get('title', root)} ({i + 1} of {len(roots)})")
                try:
                    _expand_one(m, root, report)
                except data_api.QuotaExceeded:
                    raise
                except (MapError, ValueError, data_api.YouTubeError) as e:
                    log.warning("could not expand %s: %s", root, str(e)[:200])
                    m["expanded"].append(root)
                storage.save(m)
            _promote(m, report)
        return _finish(m, report)


def check_size(text: str) -> dict:
    """Resolve a channel and flag one too small for its recommendations to be meaningful."""
    cid = resolve(text)
    info = data_api.channels([cid]).get(cid)
    if not info:
        raise ValueError(f"YouTube has no channel {cid}")
    small = info["subscribers"] < metrics.SMALL_SUBS or info["video_count"] < 3
    return {"id": cid, "title": info["title"], "handle": info["handle"], "avatar": info["avatar"],
            "subscribers": info["subscribers"], "videos": info["video_count"], "small": small,
            "mapped": storage.path(cid).exists()}


def recheck(map_id: str, report: Reporter = silent) -> dict:
    """Judge every channel again and read the new ones, without rescanning."""
    with storage.lock(map_id):
        m = storage.require(map_id)
        relevance.classify(m, report, again=True)
        _read_far(m, report)
        metrics.remember_history(m)
        relevance.judge(m, report)
        storage.save(m)
        return m


def map_channel(text: str, steps: int = 1, report: Reporter = silent) -> dict:
    """Scan a channel, then deepen the map `steps` steps."""
    m = scan(text, report)
    return deepen(m["channel_id"], steps, report) if int(steps) > 0 else m


def due() -> list[dict]:
    """Maps not refreshed within REFRESH_HOURS, oldest first. Empty when quota is low."""
    if quota.left() < REFRESH_MIN_QUOTA:
        return []
    rows = [r for r in storage.saved() if hours_since(r["scanned_at"]) >= REFRESH_HOURS]
    return sorted(rows, key=lambda r: r["scanned_at"])


def refresh(map_id: str, report: Reporter = silent) -> dict:
    """Rescan a map and re-read its oldest expanded neighbours."""
    m = scan(map_id, report)
    with storage.lock(map_id):
        m = storage.require(map_id)
        roots = [c for c in m["expanded"] if c in m["channels"]
                 and not m["channels"][c].get("off") and relevance.matches_niche(m, m["channels"][c])]
        for root in sorted(roots, key=lambda c: m["expanded_at"].get(c, ""))[:REFRESH_ROOTS]:
            try:
                _expand_one(m, root, report)
            except (MapError, ValueError, data_api.YouTubeError) as e:
                log.warning("refresh of %s failed: %s", root, str(e)[:200])
        _promote(m, report)
        return _finish(m, report)


def refresh_due(report: Reporter = silent) -> dict | None:
    """Refresh the most overdue map, if any."""
    rows = due()
    return refresh(rows[0]["channel_id"], report) if rows else None


# ---------------------------------------------------------------- user edits

def _add(m: dict, other: str, report: Reporter) -> None:
    if other == m["channel_id"]:
        raise ValueError("that is this map's own channel")
    back = (m.get("removed") or {}).pop(other, None)
    c = m["channels"].setdefault(other, (back or {}).get("row")
                                 or {"appearances": 0, "coverage": 0, "first_seen": utc_now()})
    c.update(added=True, grade="close")
    c.pop("off", None)
    _relink(m, other, back)
    _detail(m["channels"], report, only=[other])


def add_competitors(map_id: str, names: list[str], report: Reporter = silent) -> tuple[dict, list[str]]:
    """Add channels by name, link or @handle. -> (map, problems)

    When several are added at once, nobody reviews each match, so a bare name is accepted
    only if the channel found has nearly that name. Links and handles are exact.
    """
    names = [n.strip() for n in names if n and n.strip()]
    if not names:
        raise ValueError("enter at least one channel")
    problems = []
    with storage.lock(map_id):
        m = storage.require(map_id)
        for i, name in enumerate(names):
            report(f"adding {name} ({i + 1} of {len(names)})")
            try:
                other = _resolve_in_niche(m, name)
                exact = re.search(r"UC[\w-]{22}", name) or "youtube.com/" in name or name.startswith("@")
                if len(names) > 1 and not exact:
                    title = ((m["channels"].get(other) or {}).get("title")
                             or (data_api.channels([other]).get(other) or {}).get("title", ""))
                    if not _same_name(title, name):
                        raise ValueError(f"the closest match is {title or 'nothing'}; add it by link instead")
                if other in m["channels"] and m["channels"][other].get("added"):
                    continue
                _add(m, other, report)
            except data_api.QuotaExceeded:
                raise
            except (ValueError, data_api.YouTubeError) as e:
                problems.append(f"{name}: {e}")
        storage.save(m)
    return m, problems


def _same_name(title: str, name: str) -> bool:
    a, b = plain(title), plain(name)
    short, long_ = sorted((a, b), key=len)
    return bool(short) and (long_.startswith(short) and len(short) >= NAME_PREFIX
                            or SequenceMatcher(None, a, b).ratio() >= NAME_CLOSE)


def remove_channel(map_id: str, channel: str) -> dict:
    """Remove a channel from a map permanently. It stays off through rescans."""
    with storage.lock(map_id):
        m = storage.require(map_id)
        if channel not in m["channels"]:
            raise ValueError("that channel is not on this map")
        row = m["channels"][channel]
        m.setdefault("removed", {})[channel] = {
            "title": row.get("title", channel), "at": utc_now(), "row": row,
            "links": [x for x in m.get("links", []) if channel in (x["a"], x["b"])],
            "expanded": channel in m.get("expanded", [])}
        storage.save(m)
        return m


def restore_channel(map_id: str, channel: str) -> dict:
    with storage.lock(map_id):
        m = storage.require(map_id)
        back = (m.get("removed") or {}).pop(channel, None)
        if not back:
            raise ValueError("that channel was not removed from this map")
        m["channels"][channel] = back.get("row") or {"appearances": 0, "coverage": 0, "grade": "far",
                                                     "title": back.get("title", channel), "first_seen": utc_now()}
        _relink(m, channel, back)
        storage.save(m)
        return m


def _relink(m: dict, channel: str, back: dict | None) -> None:
    if not back:
        return
    here = {m["channel_id"], *m["channels"]}
    have = {(x["a"], x["b"]) for x in m.get("links", [])}
    m["links"] = m.get("links", []) + [x for x in back.get("links") or []
                                       if x["a"] in here and x["b"] in here and (x["a"], x["b"]) not in have]
    if back.get("expanded") and channel not in m["expanded"]:
        m["expanded"].append(channel)


def set_learning(map_id: str, channel: str, learn: bool) -> dict:
    """Include or exclude a channel from breakouts, topics and answers."""
    with storage.lock(map_id):
        m = storage.require(map_id)
        if channel not in m["channels"]:
            raise ValueError("that channel is not on this map")
        if learn:
            m["channels"][channel].pop("off", None)
        else:
            m["channels"][channel]["off"] = True
        storage.save(m)
        return m


def read_uploads(map_id: str, only: list[str] | None = None, limit: int | None = None,
                 quota_floor: int = 0, report: Reporter = silent) -> dict:
    """Read the full recent uploads of a map's channels into the research store.

    Channels with real traffic go first, then the nearest. About 2 units per channel.
    """
    m = storage.require(map_id)
    ids = {c for c in only if c in m["channels"]} if only is not None else database.near_ids(m, "near")
    rank = m["channels"]
    todo = sorted((c for c in ids if not rank[c].get("off")),
                  key=lambda c: (-(rank[c].get("proven") or 0), -(rank[c].get("coverage") or 0)))
    todo = todo[:int(limit)] if limit else todo
    done = 0
    failed = []
    for i in range(0, len(todo), 50):
        if quota.left() <= quota_floor:
            break
        info = data_api.channels(todo[i:i + 50])
        for cid in todo[i:i + 50]:
            if quota.left() <= quota_floor:
                break
            if cid not in info:
                failed.append(f"{rank[cid].get('title', cid)}: no longer on YouTube")
                continue
            try:
                videos = data_api.uploads(info[cid]["uploads"])
            except data_api.YouTubeError as e:
                failed.append(f"{info[cid]['title']}: {str(e)[:120]}")
                continue
            database.remember(cid, info[cid], videos, metrics.measure(videos))
            done += 1
            report(f"read {info[cid]['title']} ({done} of {len(todo)})")
    return {"map": m["title"], "wanted": len(todo), "read": done, "failed": failed}
