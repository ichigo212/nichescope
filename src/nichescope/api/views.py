"""JSON views of maps for the web client."""
from __future__ import annotations

import re

from ..research import database, metrics, own, reach, relevance, storage, topics
from ..util import hours_since
from ..youtube import auth

VIDEO_KEYS = ("id", "title", "views", "published_at", "thumbnail", "seconds", "outlier", "on_topic")
FIT_RANK = {"unclear": 1, "adjacent": 2, "same": 3}
OWN_VIDEO_KEYS = ("id", "title", "thumbnail", "published_at", "views", "period_views", "avg_view_pct",
                  "subs", "impressions", "ctr", "verdict", "note")
BREAKOUTS_SENT = 48
NEW_DAYS = 7
CARD_DOTS = 18

_cards: dict[str, tuple[float, dict]] = {}


def video(v: dict) -> dict:
    return {k: v.get(k) for k in VIDEO_KEYS}


def _store_facts(ids: set[str]) -> tuple[dict[str, int], dict[str, str]]:
    """({channel: median long-video minutes}, {channel: language}) from the research store."""
    try:
        return database.channel_facts(ids)
    except Exception:  # noqa: BLE001 - filters degrade gracefully without the store
        return {}, {}


def _channels(m: dict) -> list[dict]:
    hist = m.get("history") or {}
    minutes, languages = _store_facts(set(m["channels"]))
    settled = hours_since(m.get("first_scan")) >= NEW_DAYS * 24

    rows = [{"id": cid, "title": c.get("title") or cid, "handle": c.get("handle", ""),
             "avatar": c.get("avatar", ""), "subscribers": c.get("subscribers"),
             "views30d": c.get("views_30d"), "usual": c.get("usual"), "grade": c.get("grade", "far"),
             "appearances": c.get("appearances", 0), "coverage": c.get("coverage", 0),
             "viaCoverage": c.get("via_coverage"),
             "viaTitle": (m["channels"].get(c.get("via")) or {}).get("title"),
             "breakout": (metrics.channel_breakouts(c) or [{}])[0].get("outlier"),
             "via": c.get("via"), "step": c.get("step", 0), "promoted": c.get("promoted"),
             "proven": c.get("proven"), "provenVideos": c.get("proven_videos") or [],
             "added": bool(c.get("added")), "off": bool(c.get("off")),
             "topic": c.get("topic"), "fit": "same" if c.get("added") else c.get("fit"),
             "rising": metrics.rising(hist.get(cid)),
             "startedAt": c.get("started_at", ""),
             "isNew": settled and hours_since(c.get("first_seen")) < NEW_DAYS * 24,
             "language": (c.get("language") or "").split("-")[0].lower() or languages.get(cid, ""),
             "minutes": minutes.get(cid),
             "breakouts": [video(v) for v in metrics.channel_breakouts(c)]}
            for cid, c in m["channels"].items()]
    rows.sort(key=lambda c: (-(c["proven"] or 0), -c["coverage"]))
    return rows


def _searched(b: dict) -> dict | None:
    got = b.get("searched")
    if not got:
        return None
    return {"subject": got["subject"], "queries": got.get("queries", []), "onMap": got.get("on_map", 0),
            "onYoutube": got.get("on_youtube", 0)}


def _batches(m: dict, map_id: str) -> list[dict]:
    breakouts = {v["id"]: v for v in metrics.breakouts(m)}
    own_videos = [*(m.get("own") or {}).get("videos", []), *m.get("videos", [])]

    def closest(vid: str) -> dict | None:
        v = next((v for v in own_videos if vid and v["id"] == vid), None)
        return {k: v.get(k) for k in OWN_VIDEO_KEYS} if v else None

    def index(b: dict) -> dict[str, dict]:
        return {**b.get("videos", {}), **breakouts}

    return [{"id": b["id"], "at": b["at"], "instructions": b.get("instructions", ""), "searched": _searched(b),
             "files": _files(map_id, b.get("files")), "learnedFrom": b.get("learned_from"),
             "analysis": b.get("analysis", ""),
             "followups": [{"role": r["role"], "content": r["content"], "at": r["at"],
                            "files": _files(map_id, r.get("files")),
                            "addedTopics": r.get("added_topics", 0), "titlesFor": r.get("titles_for", [])}
                           for r in b.get("followups", [])],
             "topics": [{"topic": t["topic"], "why": t.get("why", ""), "detail": t.get("detail", ""),
                         "reasons": t.get("reasons") or {}, "expectedViews": t.get("expected_views"),
                         "titles": t.get("titles", []), "fit": t.get("fit"), "onYoutube": t.get("on_youtube"),
                         "name": t.get("name"),
                         "closestOwn": closest(t.get("closest_own", "")),
                         "evidenceLost": sum(e not in by_id for e in t["evidence"]),
                         "evidence": [{**video(by_id[e]), "channel": by_id[e]["channel"],
                                       "searched": e not in breakouts}
                                      for e in t["evidence"] if e in by_id]}
                        for t in b["topics"]]}
            for b, by_id in ((b, index(b)) for b in m.get("topics", []))]


def _files(map_id: str, files: list[dict] | None) -> list[dict]:
    return [{**f, "url": f"/api/maps/{map_id}/files/{f['id']}"} for f in files or []]


def _mentions(m: dict, text: str) -> list[dict]:
    """Channels on the map named in a piece of text, longest names first."""
    rows = [(cid, r) for cid, r in m["channels"].items()
            if len(r.get("title") or "") >= 3
            and re.search(rf"(?<!\w){re.escape(r['title'])}(?!\w)", text,
                          re.IGNORECASE if len(r["title"]) > 4 else 0)]
    rows.sort(key=lambda kv: -len(kv[1]["title"]))
    return [{"id": cid, "title": r["title"], "avatar": r.get("avatar", ""), "subscribers": r.get("subscribers"),
             "views30d": r.get("views_30d"), "breakout": r.get("breakout")} for cid, r in rows[:12]]


def _chats(m: dict, map_id: str) -> list[dict]:
    return [{"id": c["id"], "at": c["at"],
             "messages": [{"role": r["role"], "content": r["content"], "at": r["at"],
                           "files": _files(map_id, r.get("files")),
                           "mentions": _mentions(m, r["content"]) if r["role"] == "model" else []}
                          for r in c["messages"]]}
            for c in m.get("chats", [])]


def _own(m: dict) -> dict | None:
    data = m.get("own")
    if not data:
        return None
    real = sorted(data.get("traffic", {}).items(), key=lambda kv: -kv[1]["views"])[:40]
    shown = reach.load(m["channel_id"]) or {}
    videos = [{**v, **(shown.get("videos") or {}).get(v["id"], {})} for v in data.get("videos", [])]
    medians = own.diagnose(videos)
    return {"windowDays": data.get("window_days"), "sources": data.get("sources", []),
            "medians": medians, "reachAt": shown.get("at"),
            "videos": [{k: v.get(k) for k in OWN_VIDEO_KEYS} for v in videos],
            "traffic": [{"id": c, "title": r["title"], "views": r["views"], "minutes": r["minutes"],
                         "top": r["videos"][0] if r["videos"] else None} for c, r in real],
            "accuracy": own.accuracy(m)}


def _breakouts(m: dict) -> list[dict]:
    rows = metrics.breakouts(m)
    recent = [v for v in rows if metrics.is_recent(v)][:BREAKOUTS_SENT]
    ids = {v["id"] for v in recent}
    rest = [v for v in rows if v["id"] not in ids][:BREAKOUTS_SENT]
    return [{**video(v), "channel": v["channel"], "channelId": v["channel_id"]} for v in [*recent, *rest]]


def _uploads(m: dict) -> dict:
    vids = [video(v) for v in m.get("videos") or [] if v.get("id")]
    return {"recent": sorted(vids, key=lambda v: v.get("published_at") or "", reverse=True)[:12],
            "popular": sorted(vids, key=lambda v: -(v.get("views") or 0))[:12]}


def map_view(m: dict) -> dict:
    """A map as the channel page draws it."""
    map_id = m["channel_id"]
    channels = {**{c: r for c, r in m["channels"].items() if r.get("proven")}, **relevance.relevant_channels(m)}
    visible = {map_id, *channels}
    shown = {**m, "channels": channels,
             "links": [x for x in m.get("links", []) if x["a"] in visible and x["b"] in visible],
             "expanded": [c for c in m.get("expanded", []) if c in channels]}
    return {"id": map_id, "title": m["title"], "avatar": m.get("avatar", ""), "handle": m.get("handle", ""),
            "subscribers": m.get("subscribers"), "usual": m.get("usual"), "views30d": m.get("views_30d"),
            "videosRead": m.get("videos_read", 0), "scannedAt": m.get("scanned_at", ""),
            "channels": _channels(shown), "links": shown["links"], "expanded": shown["expanded"],
            "breakouts": _breakouts(m),
            "breakingOut": len({v["channel_id"] for v in metrics.breakouts(m)
                                if v["on_topic"] and metrics.is_recent(v)}),
            "batches": _batches(m, map_id), "chats": _chats(m, map_id), "marks": m.get("marks"),
            "confidence": metrics.confidence(m), "own": _own(m), "ownError": m.get("own_error"),
            "isOwn": auth.is_own(map_id), "savedTopics": m.get("saved_topics", []),
            "settings": topics.settings_of(m),
            "limits": {"topics": topics.TOPICS_MAX, "titles": topics.TITLES_MAX,
                       "instructions": topics.INSTRUCTIONS_MAX},
            "setAside": relevance.set_aside(m), "uploads": _uploads(m),
            "removed": sorted(({"id": c, "title": r.get("title", c), "at": r.get("at", "")}
                               for c, r in (m.get("removed") or {}).items()),
                              key=lambda r: r["at"], reverse=True)}


def card(channel_id: str) -> dict | None:
    """A mapped channel as the home page lists it, cached until its file changes."""
    path = storage.path(channel_id)
    try:
        modified = path.stat().st_mtime
    except OSError:
        return None
    hit = _cards.get(channel_id)
    if hit and hit[0] == modified:
        return hit[1]
    m = storage.load(channel_id)
    if not m:
        return None
    shown = relevance.relevant_channels(m)
    near = sorted(((c, r) for c, r in shown.items() if r.get("grade") != "far" and not r.get("off")),
                  key=lambda kv: (-(kv[1].get("proven") or 0), -(kv[1].get("coverage") or 0)))
    out = {"id": m["channel_id"], "title": m.get("title", ""), "avatar": m.get("avatar", ""),
           "handle": m.get("handle", ""), "subscribers": m.get("subscribers"),
           "scannedAt": m.get("scanned_at", ""), "near": len(near), "shown": len(shown),
           "isOwn": auth.is_own(m["channel_id"]),
           "dots": [{"avatar": r.get("avatar", ""), "ring": 0 if r.get("grade") == "close" else 1}
                    for _, r in near[:CARD_DOTS]]}
    _cards[channel_id] = (modified, out)
    return out


def cards() -> list[dict]:
    return [c for c in (card(r["channel_id"]) for r in storage.saved()) if c]


def mesh_view(center: str | None = None) -> dict:
    """Every map merged into one graph, with each node's distance in steps from the centre
    (the first map when no centre is given)."""
    maps = storage.all_maps()
    if maps and not center:
        center = maps[0]["channel_id"]
    minutes, languages = _store_facts({c for m in maps for c in m["channels"]} | {m["channel_id"] for m in maps})
    nodes: dict[str, dict] = {}
    weights: dict[tuple[str, str], float] = {}

    def node(cid: str, row: dict, map_id: str) -> None:
        sized = (row.get("usual") or 0) >= metrics.SMALL_USUAL
        language = (row.get("language") or "").split("-")[0].lower() or languages.get(cid, "")
        n = nodes.setdefault(cid, {"id": cid, "title": row.get("title") or cid, "avatar": row.get("avatar", ""),
                                   "handle": row.get("handle", ""), "subscribers": row.get("subscribers"),
                                   "views30d": row.get("views_30d"), "usual": row.get("usual"),
                                   "breakout": row.get("breakout") if sized else None,
                                   "startedAt": row.get("started_at", ""), "minutes": minutes.get(cid),
                                   "language": language, "maps": [], "mapped": False, "off": bool(row.get("off")),
                                   "fit": None})
        if map_id not in n["maps"]:
            n["maps"].append(map_id)
        fit = "same" if row.get("added") else row.get("fit")
        if FIT_RANK.get(fit, 0) > FIT_RANK.get(n["fit"], 0):
            n["fit"] = fit

    for m in maps:
        mid = m["channel_id"]
        node(mid, m, mid)
        nodes[mid]["mapped"] = True
        shown = {**{c: r for c, r in m["channels"].items() if r.get("proven")}, **relevance.relevant_channels(m)}
        for cid, r in shown.items():
            node(cid, r, mid)
            if r.get("coverage"):
                key = (mid, cid)
                weights[key] = max(weights.get(key, 0), r["coverage"])
        for x in m.get("links", []):
            if x["a"] in nodes and x["b"] in nodes:
                key = (x["a"], x["b"])
                weights[key] = max(weights.get(key, 0), x.get("coverage") or 0)
        for cid, r in shown.items():
            # Added and traffic channels hang from the map; channels found around a
            # neighbour hang from that neighbour.
            if r.get("via") in nodes and (r["via"], cid) not in weights:
                weights[(r["via"], cid)] = r.get("via_coverage") or 0.01
            elif not r.get("coverage") and not r.get("via") and (mid, cid) not in weights:
                weights[(mid, cid)] = 0.01
        for cid in m.get("expanded", []):
            if cid in nodes:
                nodes[cid]["mapped"] = True
    links = [{"a": a, "b": b, "coverage": w} for (a, b), w in weights.items()]
    if center and center in nodes:
        adjacent: dict[str, set[str]] = {}
        for a, b in weights:
            adjacent.setdefault(a, set()).add(b)
            adjacent.setdefault(b, set()).add(a)
        steps = {center: 0}
        frontier = [center]
        while frontier:
            nxt = []
            for cid in frontier:
                for other in adjacent.get(cid, ()):
                    if other not in steps:
                        steps[other] = steps[cid] + 1
                        nxt.append(other)
            frontier = nxt
        for cid, n in nodes.items():
            n["step"] = steps.get(cid)
    return {"center": center, "nodes": list(nodes.values()), "links": links,
            "maps": [{"id": m["channel_id"], "title": m["title"]} for m in maps]}


def home_breakouts(limit: int = 24) -> list[dict]:
    """Recent breakouts across every map, biggest first, without duplicates."""
    seen: set[str] = set()
    rows = []
    for m in storage.all_maps():
        for v in metrics.breakouts(m):
            if v["on_topic"] and metrics.is_recent(v) and v["id"] not in seen:
                seen.add(v["id"])
                rows.append({**video(v), "channel": v["channel"], "channelId": v["channel_id"],
                             "mapId": m["channel_id"], "mapTitle": m["title"]})
    return sorted(rows, key=lambda v: -(v["outlier"] or 0))[:limit]
