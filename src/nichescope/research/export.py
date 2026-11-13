"""CSV exports of a map's channels and breakouts."""
from __future__ import annotations

import csv
import io

from . import metrics, relevance


def channels_csv(m: dict) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["channel", "handle", "grade", "coverage", "appearances", "subscribers", "views_30d",
                "usual_views", "top_breakout", "views_sent", "added", "excluded", "url"])
    rows = sorted(relevance.relevant_channels(m).items(), key=lambda kv: -(kv[1].get("coverage") or 0))
    for cid, r in rows:
        w.writerow([r.get("title", ""), r.get("handle", ""), r.get("grade", ""), r.get("coverage", ""),
                    r.get("appearances", ""), r.get("subscribers", ""), r.get("views_30d", ""),
                    r.get("usual", ""), r.get("breakout", ""), r.get("proven", ""), bool(r.get("added")),
                    bool(r.get("off")), f"https://www.youtube.com/channel/{cid}"])
    return out.getvalue()


def breakouts_csv(m: dict) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["channel", "title", "views", "times_usual", "published", "minutes", "url"])
    for v in metrics.breakouts(m):
        w.writerow([v["channel"], v["title"], v["views"], v["outlier"], v["published_at"][:10],
                    v["seconds"] // 60, f"https://www.youtube.com/watch?v={v['id']}"])
    return out.getvalue()
