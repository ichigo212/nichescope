"""The context given to the model: a channel, its recent videos and its niche's breakouts."""
from __future__ import annotations

from ..youtube import auth
from ..youtube.analytics import SOURCE_NAMES
from . import metrics, relevance, storage

DESCRIPTION_SHOWN = 300
OWN_VIDEOS_SHOWN = 30
BREAKOUTS_SHOWN = 40


def _packaging(v: dict) -> str:
    tags = ", ".join(v.get("tags", [])[:15]) or "none"
    return f"tags: {tags} | description opens: {v.get('description', '')[:DESCRIPTION_SHOWN]!r}"


def what_it_makes(m: dict) -> str:
    words = ", ".join(list(relevance.fingerprint(m))[:12])
    if words:
        return f"Its videos are about: {words}."
    return "Judge what it makes from its videos below."


def own_analytics(m: dict) -> str:
    own = m.get("own")
    if not own:
        return ""
    lines = [f"\n\nPRIVATE ANALYTICS FOR THIS CHANNEL, last {own['window_days']} days:"]
    sources = ", ".join(f"{SOURCE_NAMES.get(s['source'], s['source'])} {round(s['share'] * 100)}%"
                        for s in own.get("sources", [])[:6])
    lines.append(f"Traffic sources: {sources}")
    lines.append(f"Median share of a video watched: {(own.get('medians') or {}).get('retention')}%")
    for v in own.get("videos", [])[:60]:
        lines.append(f"- {v['title']} | id {v['id']} | {(v.get('published_at') or '')[:10]} | "
                     f"{v.get('period_views')} views | {v.get('avg_view_pct')}% watched | {v['verdict']}")
    real = sorted(own.get("traffic", {}).items(), key=lambda kv: -kv[1]["views"])[:15]
    if real:
        lines.append("Channels whose videos send this channel viewers through Suggested videos:")
        lines += [f"- {r['title']}: {r['views']} views, e.g. {r['videos'][0]['title']}" for _, r in real]
    return "\n".join(lines)


def video_line(v: dict) -> str:
    """One video the model may cite, with its id."""
    outlier = f"{v['outlier']}x its channel's usual" if v.get("outlier") else "channel's usual unknown"
    return (f"- [{v.get('channel', '')}] {v['title']} | {v['views']} views | {outlier} | "
            f"{(v.get('published_at') or '')[:10]} | {(v.get('seconds') or 0) // 60} min | id {v['id']} | "
            f"{_packaging(v)}")


def brief(m: dict, rows: list[dict] | None = None) -> str:
    """The channel, its latest videos and the niche's breakouts, with ids the model may cite."""
    own_lines = [f"- {v['title']} | {v['views']} views | {v['published_at'][:10]} | id {v['id']} | {_packaging(v)}"
                 for v in m["videos"][:OWN_VIDEOS_SHOWN]]
    pool = metrics.evidence_pool(m)[:BREAKOUTS_SHOWN] if rows is None else rows
    other_lines = [video_line(v) for v in pool]
    return (f"THE CHANNEL: {m['title']}, {m['subscribers']} subscribers. {what_it_makes(m)}"
            f"\n\nITS LATEST VIDEOS:\n" + "\n".join(own_lines)
            + "\n\nBREAKOUTS ON CHANNELS YOUTUBE RECOMMENDS ALONGSIDE IT:\n"
            + ("\n".join(other_lines) or "(none found)") + own_analytics(m))


def marks_note(m: dict) -> str:
    marks = m.get("marks") or {}
    rows = []
    for kind in ("topics", "titles"):
        for value, word in (("like", "liked"), ("no", "rejected")):
            got = [k for k, v in (marks.get(kind) or {}).items() if v == value]
            if got:
                rows.append(f"The user {word} these {kind}: " + "; ".join(got[:20]))
    return "\n\n" + "\n".join(rows) if rows else ""


def sibling_maps(m: dict) -> list[dict]:
    """Maps of the user's other connected channels."""
    others = [storage.load(a["id"]) for a in auth.accounts() if a["id"] != m["channel_id"]]
    return [o for o in others if o]


def our_videos(m: dict) -> list[dict]:
    return [v for one in [m, *sibling_maps(m)] for v in one.get("videos") or []]


def earlier_topics(m: dict) -> list[dict]:
    return [t for one in [m, *sibling_maps(m)] for b in one.get("topics") or [] for t in b["topics"]]
