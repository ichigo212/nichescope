"""Private analytics for a connected channel's map.

Public recommendations estimate who shares an audience. For a connected channel, YouTube
Analytics reports which videos actually sent viewers through Suggested videos. Those
source channels are marked `proven` on the map, and `accuracy()` measures how many of
them the public scan found on its own.
"""
from __future__ import annotations

import logging
import statistics

from ..util import Reporter, silent
from ..youtube import analytics, data_api

log = logging.getLogger(__name__)

WINDOW_DAYS = 90
TOP_VIDEOS = 60
LONG_MIN_SEC = 181
MIN_VIEWS = 20


def traffic(channel_id: str, top_videos: list[str], report: Reporter = silent) -> dict[str, dict]:
    """{source channel: {title, views, minutes, videos}} for Suggested-video traffic.

    One report returns at most 25 rows, so it is widened with one report per top video.
    A source seen in several reports keeps its largest count.
    """
    seen = dict(analytics.suggested_from(channel_id, WINDOW_DAYS))
    videos = top_videos[:TOP_VIDEOS]
    for i, vid in enumerate(videos):
        report(f"reading suggested traffic ({i + 1} of {len(videos)})")
        try:
            for src, row in analytics.suggested_from(channel_id, WINDOW_DAYS, vid).items():
                if row["views"] > seen.get(src, {"views": -1})["views"]:
                    seen[src] = row
        except data_api.YouTubeError as e:
            log.warning("suggested traffic for %s failed: %s", vid, str(e)[:150])
    out: dict[str, dict] = {}
    for v in data_api.videos(list(seen)):
        who = v["channel_id"]
        if who == channel_id:
            continue
        row = out.setdefault(who, {"title": v["channel"] or who, "views": 0, "minutes": 0, "videos": []})
        row["views"] += seen[v["id"]]["views"]
        row["minutes"] += seen[v["id"]]["minutes"]
        row["videos"].append({"id": v["id"], "title": v["title"], "views": seen[v["id"]]["views"]})
    for row in out.values():
        row["videos"].sort(key=lambda x: -x["views"])
    return out


def diagnose(rows: list[dict]) -> dict:
    """Mark each video against the channel's median retention. Changes rows in place."""
    pcts = [r["avg_view_pct"] for r in rows
            if r.get("avg_view_pct") is not None and (r.get("period_views") or 0) >= MIN_VIEWS]
    median = statistics.median(pcts) if pcts else None
    for r in rows:
        if median is None or r.get("avg_view_pct") is None or (r.get("period_views") or 0) < MIN_VIEWS:
            r["verdict"], r["note"] = "unknown", "not enough views yet"
        elif r["avg_view_pct"] >= median:
            r["verdict"], r["note"] = "holding", "viewers stay longer than on your typical video"
        else:
            r["verdict"], r["note"] = "dropping", "viewers leave sooner than on your typical video"
    return {"retention": median}


def performance(channel_id: str, videos: list[dict]) -> dict:
    kept = analytics.retention(channel_id, WINDOW_DAYS)
    rows = []
    for v in videos:
        if v.get("seconds", 0) < LONG_MIN_SEC:
            continue
        k = kept.get(v["id"], {})
        rows.append({"id": v["id"], "title": v["title"], "seconds": v["seconds"],
                     "thumbnail": v.get("thumbnail", ""), "published_at": v["published_at"],
                     "views": v["views"], "period_views": k.get("views"), "avg_view_pct": k.get("avg_view_pct"),
                     "avg_view_sec": k.get("avg_view_sec"), "subs": k.get("subs")})
    return {"videos": rows, "medians": diagnose(rows)}


def read(channel_id: str, videos: list[dict], report: Reporter = silent) -> dict:
    report("reading your channel analytics")
    perf = performance(channel_id, videos)
    busiest = sorted(perf["videos"], key=lambda v: -(v.get("period_views") or 0))
    return {"window_days": WINDOW_DAYS, "sources": analytics.sources(channel_id, WINDOW_DAYS),
            "traffic": traffic(channel_id, [v["id"] for v in busiest], report), **perf}


def accuracy(m: dict) -> dict | None:
    """How much of the measured Suggested traffic the public scan found by itself."""
    own = m.get("own") or {}
    truth = set(own.get("traffic") or {})
    if not truth:
        return None
    pointed = {x["b"] for x in m.get("links", [])}
    found = {c: r for c, r in m["channels"].items() if r.get("appearances") or r.get("via") or c in pointed}
    near = {c for c, r in found.items() if r.get("grade") in ("close", "medium")}
    rows = own["traffic"]
    return {"real": len(truth), "found": len(truth & set(found)), "near": len(truth & near),
            "mapped": len(found), "views_named": sum(r["views"] for r in rows.values()),
            "views_found": sum(r["views"] for c, r in rows.items() if c in found),
            "views_suggested": next((s["views"] for s in own.get("sources") or []
                                     if s["source"] == "RELATED_VIDEO"), None)}
