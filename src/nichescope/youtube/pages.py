"""Channel profiles and uploads read from YouTube's public channel pages. Uses no API quota.

Numbers on these pages are rounded ("67K views", "15.1M subscribers") and dates are
relative ("3 weeks ago"), so values are approximate. Descriptions and tags are not shown
on the listing, so they are left empty.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta, timezone

import requests

from .web import (
    COOKIES,
    HEADERS,
    PAGE_GAP_SEC,
    _config_value,
    _continuation,
    _find,
    _get,
    page_data,
    parse_age,
    parse_clock,
    parse_count,
)

log = logging.getLogger(__name__)

SHORT_MAX_SEC = 180


class ChannelNotFound(LookupError):
    pass


def _iso_from_age(days: float | None) -> str:
    if days is None:
        return ""
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _texts(node) -> list[str]:
    return [t for t in _find(node, "content") if isinstance(t, str)]


def _video(lockup: dict) -> dict | None:
    if not str(lockup.get("contentType", "")).endswith("_VIDEO") or not lockup.get("contentId"):
        return None
    meta = (lockup.get("metadata") or {}).get("lockupMetadataViewModel") or {}
    title = (meta.get("title") or {}).get("content", "")
    views = age = None
    for part in _find(meta.get("metadata") or {}, "metadataParts"):
        for p in part:
            label = str(p.get("accessibilityLabel") or (p.get("text") or {}).get("content") or "")
            if "view" in label:
                views = parse_count(label.replace(" thousand", "K").replace(" million", "M").replace(" billion", "B"))
            elif "ago" in label:
                age = parse_age(label)
    badges = [b.get("text", "") for b in _find(lockup.get("contentImage") or {}, "thumbnailBadgeViewModel")]
    seconds = next((parse_clock(t) for t in badges if re.fullmatch(r"\d+(:\d\d)+", str(t))), 0)
    vid = lockup["contentId"]
    return {"id": vid, "title": title, "published_at": _iso_from_age(age), "seconds": seconds,
            "views": views or 0, "thumbnail": f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg",
            "description": "", "tags": [], "language": ""}


def _profile(data: dict) -> dict:
    meta = (data.get("metadata") or {}).get("channelMetadataRenderer") or {}
    texts = _texts(data.get("header") or {})
    subs = next((parse_count(t) for t in texts if "subscriber" in t), 0) or 0
    count = next((parse_count(t) for t in texts if re.search(r"\bvideos?\b", t)), 0) or 0
    handle = next((t for t in texts if t.startswith("@")), "")
    thumbs = (meta.get("avatar") or {}).get("thumbnails") or []
    return {"id": meta.get("externalId", ""), "title": meta.get("title", ""), "handle": handle,
            "avatar": thumbs[-1]["url"] if thumbs else "", "subscribers": subs, "video_count": count,
            "total_views": 0, "started_at": "", "bio": (meta.get("description") or "")[:1000],
            "country": "", "language": ""}


def channel_id(handle: str) -> str | None:
    """The channel id behind an @handle, or None."""
    try:
        data = page_data(_get(f"https://www.youtube.com/@{handle.lstrip('@')}", {"hl": "en", "gl": "US"}).text)
    except requests.HTTPError:
        return None
    return ((data or {}).get("metadata") or {}).get("channelMetadataRenderer", {}).get("externalId") or None


def channel(cid: str, videos: int = 50) -> dict:
    """A channel's profile and its latest long-form uploads (newest first)."""
    try:
        r = _get(f"https://www.youtube.com/channel/{cid}/videos", {"hl": "en", "gl": "US"})
    except requests.HTTPError as e:
        raise ChannelNotFound(f"no channel {cid}") from e
    data = page_data(r.text)
    if not data:
        raise ChannelNotFound(f"the page for {cid} could not be read")
    profile = _profile(data)
    found = [v for v in (_video(x) for x in _find(data, "lockupViewModel")) if v]
    key, context, token = _config_value(r.text, "INNERTUBE_API_KEY"), _config_value(r.text, "INNERTUBE_CONTEXT"), \
        _continuation(data)
    while len(found) < videos and token and key and context:
        time.sleep(PAGE_GAP_SEC)
        try:
            more = requests.post("https://www.youtube.com/youtubei/v1/browse", params={"key": key},
                                 json={"context": context, "continuation": token},
                                 headers=HEADERS, cookies=COOKIES, timeout=20)
            more.raise_for_status()
            got = more.json()
        except (requests.RequestException, ValueError) as e:
            log.warning("uploads continuation for %s failed: %s", cid, str(e)[:150])
            break
        page = [v for v in (_video(x) for x in _find(got, "lockupViewModel")) if v]
        if not page:
            break
        found += page
        token = _continuation(got)
    long_form = [v for v in found if v["seconds"] > SHORT_MAX_SEC or v["seconds"] == 0]
    return {**profile, "id": profile["id"] or cid, "videos": long_form[:videos]}
