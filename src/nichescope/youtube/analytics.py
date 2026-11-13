"""YouTube Analytics API reports for a connected channel. These do not use Data API quota."""
from __future__ import annotations

from datetime import date, timedelta

import requests

from . import auth
from .data_api import raise_for

REPORTS = "https://youtubeanalytics.googleapis.com/v2/reports"
ROWS_PER_QUERY = 25

SOURCE_NAMES = {
    "SUBSCRIBER": "Home and subscriptions", "RELATED_VIDEO": "Suggested videos",
    "YT_SEARCH": "YouTube search", "SHORTS": "Shorts feed", "YT_OTHER_PAGE": "Other YouTube pages",
    "YT_CHANNEL": "Channel page", "NO_LINK_OTHER": "Direct or unknown", "PLAYLIST": "Playlists",
    "EXT_URL": "External websites", "NOTIFICATION": "Notifications", "END_SCREEN": "End screens",
    "SHORTS_CONTENT_LINKS": "Links from Shorts", "HASHTAGS": "Hashtag pages", "SOUND_PAGE": "Sound pages",
}


def window(days: int, today: date | None = None) -> tuple[str, str]:
    """Start and end dates covering `days` completed days."""
    end = (today or date.today()) - timedelta(days=1)
    start = end - timedelta(days=max(1, days) - 1)
    return start.isoformat(), end.isoformat()


def report(channel_id: str, days: int, doing: str, **params) -> list[list]:
    start, end = window(days)
    r = requests.get(REPORTS, params={"ids": "channel==MINE", "startDate": start, "endDate": end, **params},
                     headers=auth.headers(channel_id), timeout=60)
    if r.status_code != 200:
        raise_for(r, doing)
    return r.json().get("rows") or []


def sources(channel_id: str, days: int) -> list[dict]:
    """Where views come from: [{source, name, views, minutes, share}]."""
    rows = report(channel_id, days, "reading traffic sources", dimensions="insightTrafficSourceType",
                  metrics="views,estimatedMinutesWatched", sort="-views")
    total = sum(r[1] for r in rows) or 1
    return [{"source": r[0], "name": SOURCE_NAMES.get(r[0], r[0].replace("_", " ").title()),
             "views": int(r[1]), "minutes": int(r[2]), "share": round(r[1] / total, 3)} for r in rows]


def suggested_from(channel_id: str, days: int, video: str | None = None) -> dict[str, dict]:
    """{source video id: {views, minutes}} for views arriving through Suggested videos."""
    filters = "insightTrafficSourceType==RELATED_VIDEO" + (f";video=={video}" if video else "")
    rows = report(channel_id, days, "reading suggested traffic", dimensions="insightTrafficSourceDetail",
                  metrics="views,estimatedMinutesWatched", filters=filters, sort="-views",
                  maxResults=ROWS_PER_QUERY)
    return {r[0]: {"views": int(r[1]), "minutes": int(r[2])} for r in rows}


def retention(channel_id: str, days: int) -> dict[str, dict]:
    """{video id: {views, avg_view_sec, avg_view_pct, minutes, subs}} for the channel's videos."""
    rows = report(channel_id, days, "reading retention", dimensions="video", sort="-views", maxResults=200,
                  metrics="views,averageViewDuration,averageViewPercentage,estimatedMinutesWatched,subscribersGained")
    return {r[0]: {"views": int(r[1]), "avg_view_sec": int(r[2]), "avg_view_pct": round(float(r[3]), 1),
                   "minutes": int(r[4]), "subs": int(r[5])} for r in rows}
