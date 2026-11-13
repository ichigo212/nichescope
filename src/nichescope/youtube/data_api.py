"""Channel and video reads.

By default (`YOUTUBE_SOURCE=public`) channel profiles and uploads come from YouTube's
public channel pages and use no quota; their numbers are rounded. With
`YOUTUBE_SOURCE=api` they come from the YouTube Data API v3, signed with
`YOUTUBE_API_KEY` or the first connected channel, and every request is counted against
the daily quota. Video details and comments always use the Data API.
"""
from __future__ import annotations

import re
import threading
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import requests

from ..config import settings
from . import auth, pages, quota

API = "https://www.googleapis.com/youtube/v3"
SHORT_MAX_SEC = 180
UPLOADS_READ = 50
BIO_KEPT = 1000
DESCRIPTION_KEPT = 600


PAGE_WORKERS = 6
PAGE_CACHE_SEC = 3600
PAGE_VIDEOS = 30

_pages: dict[str, tuple[float, int, dict]] = {}
_pages_lock = threading.Lock()


class YouTubeError(RuntimeError):
    pass


def public() -> bool:
    return settings().youtube_source != "api"


def _page(cid: str, videos: int = PAGE_VIDEOS) -> dict | None:
    """A channel's public page, cached for an hour."""
    with _pages_lock:
        hit = _pages.get(cid)
    if hit and time.time() - hit[0] < PAGE_CACHE_SEC and hit[1] >= videos:
        return hit[2]
    try:
        got = pages.channel(cid, videos)
    except (pages.ChannelNotFound, requests.RequestException):
        return None
    with _pages_lock:
        _pages[cid] = (time.time(), videos, got)
    return got


class QuotaExceeded(YouTubeError):
    pass


def _credentials(as_channel: str | None = None) -> tuple[dict, dict]:
    """(params, headers) that sign a request."""
    if as_channel:
        return {}, auth.headers(as_channel)
    key = settings().youtube_api_key
    if key:
        return {"key": key}, {}
    accounts = auth.accounts()
    if not accounts:
        raise YouTubeError("YouTube is not configured: set YOUTUBE_API_KEY in .env, "
                           "or connect a channel in Settings")
    return {}, auth.headers(accounts[0]["id"])


def raise_for(r: requests.Response, doing: str) -> None:
    try:
        err = r.json()["error"]
        reason = (err.get("errors") or [{}])[0].get("reason", "")
        message = err.get("message", "")
    except (ValueError, KeyError, TypeError):
        reason, message = "", r.text[:200]
    if reason in ("quotaExceeded", "dailyLimitExceeded"):
        raise QuotaExceeded("today's YouTube API quota is used up; it resets at midnight Pacific time")
    raise YouTubeError(f"{doing} failed ({r.status_code} {reason}): {message}")


def get(path: str, params: dict, doing: str, as_channel: str | None = None) -> dict:
    extra, headers = _credentials(as_channel)
    r = requests.get(f"{API}/{path}", params={**params, **extra}, headers=headers, timeout=60)
    quota.spend(1)
    if r.status_code != 200:
        raise_for(r, doing)
    return r.json()


def duration_seconds(iso: str | None) -> int:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


def channel_by_handle(handle: str) -> str | None:
    if public():
        return pages.channel_id(handle)
    items = get("channels", {"part": "id", "forHandle": handle}, f"looking up @{handle}").get("items") or []
    return items[0]["id"] if items else None


def channels(ids: Iterable[str]) -> dict[str, dict]:
    """Profile and statistics for many channels, 50 per request."""
    ids = list(dict.fromkeys(ids))
    out: dict[str, dict] = {}
    if public():
        with ThreadPoolExecutor(max_workers=PAGE_WORKERS) as pool:
            for cid, got in zip(ids, pool.map(_page, ids), strict=True):
                if got:
                    out[cid] = {**{k: v for k, v in got.items() if k not in ("id", "videos")}, "uploads": cid}
        return out
    for i in range(0, len(ids), 50):
        got = get("channels", {"part": "snippet,statistics,contentDetails",
                               "id": ",".join(ids[i:i + 50]), "maxResults": 50}, "reading channels")
        for it in got.get("items", []):
            sn, st = it["snippet"], it.get("statistics", {})
            out[it["id"]] = {
                "title": sn.get("title", ""),
                "handle": sn.get("customUrl", ""),
                "avatar": ((sn.get("thumbnails") or {}).get("medium") or {}).get("url", ""),
                "subscribers": int(st.get("subscriberCount") or 0),
                "started_at": sn.get("publishedAt", ""),
                "video_count": int(st.get("videoCount") or 0),
                "total_views": int(st.get("viewCount") or 0),
                "bio": (sn.get("description") or "")[:BIO_KEPT],
                "country": sn.get("country") or "",
                "language": sn.get("defaultLanguage") or "",
                "uploads": it["contentDetails"]["relatedPlaylists"]["uploads"],
            }
    return out


def _video_row(v: dict) -> dict:
    sn = v["snippet"]
    return {"id": v["id"], "title": sn.get("title", ""), "channel_id": sn.get("channelId", ""),
            "channel": sn.get("channelTitle", ""),
            "published_at": sn.get("publishedAt", ""),
            "seconds": duration_seconds(v.get("contentDetails", {}).get("duration")),
            "views": int(v.get("statistics", {}).get("viewCount") or 0),
            "likes": int(v.get("statistics", {}).get("likeCount") or 0),
            "comments": int(v.get("statistics", {}).get("commentCount") or 0),
            "thumbnail": ((sn.get("thumbnails") or {}).get("medium") or {}).get("url", ""),
            "description": (sn.get("description") or "")[:DESCRIPTION_KEPT],
            "tags": sn.get("tags", []),
            "language": sn.get("defaultAudioLanguage") or sn.get("defaultLanguage") or "",
            "public": v.get("status", {}).get("privacyStatus", "public") == "public"}


def videos(ids: Iterable[str]) -> list[dict]:
    """Full details for videos by id, in the order YouTube returns them."""
    ids = list(dict.fromkeys(ids))
    out = []
    for i in range(0, len(ids), 50):
        got = get("videos", {"part": "snippet,contentDetails,statistics,status",
                             "id": ",".join(ids[i:i + 50])}, "reading videos")
        out += [_video_row(v) for v in got.get("items", [])]
    return out


def uploads(playlist: str, n: int = UPLOADS_READ) -> list[dict]:
    """A channel's latest public long-form videos, newest first.

    `playlist` is the uploads playlist from `channels()`; with public pages it is the channel id.
    """
    if public():
        got = _page(playlist, PAGE_VIDEOS if n <= UPLOADS_READ else n)
        return [dict(v) for v in (got or {}).get("videos", [])][:n]
    ids: list[str] = []
    page = None
    while len(ids) < n:
        params: dict[str, Any] = {"part": "contentDetails", "playlistId": playlist, "maxResults": 50}
        if page:
            params["pageToken"] = page
        got = get("playlistItems", params, "listing uploads")
        ids += [i["contentDetails"]["videoId"] for i in got.get("items", [])]
        page = got.get("nextPageToken")
        if not page:
            break
    rows = [v for v in videos(ids) if v["seconds"] > SHORT_MAX_SEC and v["public"]]
    for v in rows:
        for k in ("public", "channel", "channel_id", "likes", "comments"):
            v.pop(k, None)
    return sorted(rows, key=lambda v: v["published_at"], reverse=True)


def comments(video_id: str, n: int = 25) -> list[dict]:
    got = get("commentThreads", {"part": "snippet", "videoId": video_id, "order": "relevance",
                                 "maxResults": n, "textFormat": "plainText"}, "reading comments")
    return [i["snippet"]["topLevelComment"]["snippet"] for i in got.get("items", [])]
