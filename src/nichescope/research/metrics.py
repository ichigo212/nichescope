"""Channel and video metrics: usual views, breakouts, growth and map confidence.

A channel's *usual* is the median views of its latest settled long-form videos (at least
SETTLED_DAYS old). A *breakout* is a video with at least BREAKOUT_AT times that.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone

from ..util import days_since, utc_now
from .relevance import judged_in, matches_niche, on_topic, relevant_channels

SETTLED_DAYS = 3
RECENT_DAYS = 30
EVIDENCE_DAYS = 90
BREAKOUT_AT = 3.0
BREAKOUTS_KEPT = 5
USUAL_FROM = 30
SMALL_SUBS = 1000
SMALL_USUAL = 100
SMALL_BREAKOUT_VIEWS = 1000
HISTORY_KEPT = 60
VIDEOS_TO_READ = 10


def measure(videos: list[dict], now: datetime | None = None) -> dict:
    """-> {usual, views_30d, breakouts, breakout} for a channel's uploads, newest first.

    Keeps the biggest breakouts ever and, separately, the biggest recent ones, so an old
    hit does not hide what is working now.
    """
    now = now or datetime.now(timezone.utc)
    # Paged reads can return a video twice; each counts once.
    videos = list({v["id"]: v for v in reversed(videos)}.values())[::-1] if videos and "id" in videos[0] else videos
    settled = [v["views"] for v in videos if days_since(v["published_at"], now) >= SETTLED_DAYS][:USUAL_FROM]
    usual = statistics.median(settled) if settled else None
    views_30d = sum(v["views"] for v in videos if days_since(v["published_at"], now) <= RECENT_DAYS)
    rows = []
    if usual:
        rows = [{**v, "outlier": round(v["views"] / usual, 1)} for v in videos if v["views"] / usual >= BREAKOUT_AT]
    rows.sort(key=lambda v: v["outlier"], reverse=True)
    biggest = rows[:BREAKOUTS_KEPT]
    recent = [v for v in rows[BREAKOUTS_KEPT:] if days_since(v["published_at"], now) <= RECENT_DAYS][:BREAKOUTS_KEPT]
    rows = biggest + recent
    return {"usual": usual, "views_30d": views_30d, "breakouts": rows,
            "breakout": rows[0]["outlier"] if rows else None}


def is_recent(v: dict, days: int = RECENT_DAYS) -> bool:
    return days_since(v["published_at"]) <= days


def channel_breakouts(c: dict) -> list[dict]:
    """A channel's breakouts worth showing. A tiny channel's are noise, unless it was judged
    the same kind of channel: then those with SMALL_BREAKOUT_VIEWS or more count, so a
    new channel taking off is seen early."""
    rows = c.get("breakouts") or []
    if (c.get("usual") or 0) >= SMALL_USUAL:
        return rows
    return [v for v in rows if judged_in(c) and (v.get("views") or 0) >= SMALL_BREAKOUT_VIEWS]


def breakouts(m: dict) -> list[dict]:
    """Every relevant channel's breakouts, biggest first."""
    rows = []
    seen: set[str] = set()
    for cid, c in relevant_channels(m).items():
        if c.get("off"):
            continue
        name = c.get("title", cid)
        for v in channel_breakouts(c):
            if v.get("id") in seen:
                continue
            seen.add(v.get("id"))
            rows.append({**v, "channel_id": cid, "channel": name, "on_topic": on_topic(v, name, m, c)})
    return sorted(rows, key=lambda v: v["outlier"], reverse=True)


def evidence_pool(m: dict) -> list[dict]:
    """On-niche breakouts, recent ones first, biggest first within each group."""
    rows = [v for v in breakouts(m) if v["on_topic"]]
    return sorted(rows, key=lambda v: not is_recent(v, EVIDENCE_DAYS))


def remember_history(m: dict) -> None:
    """Keep one dated line per channel (subscribers, coverage, 30-day views)."""
    day = utc_now()[:10]
    hist = m.setdefault("history", {})
    for cid, c in m["channels"].items():
        if c.get("subscribers") is None:
            continue
        rows = hist.setdefault(cid, [])
        line = {"d": day, "subs": c["subscribers"], "cov": c.get("coverage"), "views_30d": c.get("views_30d")}
        if rows and rows[-1]["d"] == day:
            rows[-1] = line
        else:
            rows.append(line)
        del rows[:-HISTORY_KEPT]


def rising(rows: list[dict] | None) -> float | None:
    """Subscriber growth as a share between the first and last recorded day."""
    if not rows or len(rows) < 2 or not rows[0].get("subs"):
        return None
    return round((rows[-1]["subs"] - rows[0]["subs"]) / rows[0]["subs"], 3)


def confidence(m: dict) -> dict | None:
    """Reasons to treat a map with caution, with a larger nearby channel to map instead."""
    why = []
    if (m.get("subscribers") or 0) < SMALL_SUBS:
        why.append(f"{m['title']} has {m.get('subscribers') or 0} subscribers")
    if m.get("usual") is not None and m["usual"] < SMALL_USUAL:
        why.append(f"a typical video gets {round(m['usual'])} views")
    if m.get("videos_read", 0) < VIDEOS_TO_READ:
        why.append(f"only {m.get('videos_read', 0)} videos could be read")
    if not why:
        return None
    instead = [(cid, c) for cid, c in m["channels"].items()
               if c.get("grade") in ("close", "medium") and (c.get("subscribers") or 0) >= 10 * SMALL_SUBS
               and not c.get("off") and matches_niche(m, c)]
    instead.sort(key=lambda kv: (bool(kv[1].get("proven")), kv[1].get("coverage") or 0), reverse=True)
    return {"why": "; ".join(why),
            "instead": {"id": instead[0][0], "title": instead[0][1].get("title", "")} if instead else None}
