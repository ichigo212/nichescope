"""Reads YouTube's public pages: the up-next list beside a video and the search page.

These requests use no API quota. They are read logged out, so they show what YouTube
offers an anonymous viewer, and they change from one visit to the next.
"""
from __future__ import annotations

import base64
import json
import logging
import re
import time
from typing import Any

import requests

log = logging.getLogger(__name__)

HEADERS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"),
           "Accept-Language": "en-US,en;q=0.9"}
COOKIES = {"CONSENT": "YES+1", "SOCS": "CAI"}
PAGE_GAP_SEC = 1.5
SEARCH_PAGES_MAX = 3

SORTS = {"relevance": 0, "date": 2, "views": 3, "rating": 1}
UPLOADED = {"any": 0, "hour": 1, "today": 2, "week": 3, "month": 4, "year": 5}
LENGTHS = {"any": 0, "short": 1, "long": 2, "medium": 3}


def _walk(node: Any, key: str, out: list) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                out.append(v)
            _walk(v, key, out)
    elif isinstance(node, list):
        for v in node:
            _walk(v, key, out)


def _find(node: Any, key: str) -> list:
    out: list = []
    _walk(node, key, out)
    return out


def page_data(html: str) -> dict | None:
    m = re.search(r"var ytInitialData\s*=\s*(\{.*?\});</script>", html, re.S)
    return json.loads(m.group(1)) if m else None


def _get(url: str, params: dict, timeout: int = 30) -> requests.Response:
    r = requests.get(url, params=params, headers=HEADERS, cookies=COOKIES, timeout=timeout)
    r.raise_for_status()
    return r


def parse_up_next(html: str) -> list[dict] | None:
    """The up-next list of a watch page: [{video_id, channel_id, title}].

    None when the page carries no data (a block or consent wall), [] when the list is empty.
    """
    data = page_data(html)
    if data is None:
        return None
    side = data.get("contents", {}).get("twoColumnWatchNextResults", {}).get("secondaryResults", {})
    out = []
    for x in _find(side, "lockupViewModel"):
        if not str(x.get("contentType", "")).endswith("_VIDEO"):
            continue
        owner = next((i for i in _find(x, "browseId") if str(i).startswith("UC")), None)
        title = x.get("metadata", {}).get("lockupMetadataViewModel", {}).get("title", {}).get("content")
        if owner and x.get("contentId"):
            out.append({"video_id": x["contentId"], "channel_id": owner, "title": title or ""})
    for x in _find(side, "compactVideoRenderer"):
        owner = next((i for i in _find(x, "browseId") if str(i).startswith("UC")), None)
        if owner and x.get("videoId"):
            out.append({"video_id": x["videoId"], "channel_id": owner,
                        "title": (x.get("title") or {}).get("simpleText", "")})
    return out


def up_next(video_id: str) -> list[dict] | None:
    return parse_up_next(_get("https://www.youtube.com/watch",
                              {"v": video_id, "hl": "en", "gl": "US"}).text)


def parse_channel_search(html: str) -> list[dict]:
    data = page_data(html)
    if data is None:
        return []
    out = []
    for r in _find(data, "channelRenderer"):
        thumbs = (r.get("thumbnail") or {}).get("thumbnails") or []
        avatar = thumbs[-1]["url"] if thumbs else ""
        detail = [(r.get("subscriberCountText") or {}).get("simpleText"),
                  (r.get("videoCountText") or {}).get("simpleText")]
        out.append({"id": r.get("channelId"),
                    "title": (r.get("title") or {}).get("simpleText", ""),
                    "avatar": ("https:" + avatar) if avatar.startswith("//") else avatar,
                    "detail": " · ".join(x for x in detail if x)})
    return [x for x in out if x["id"]]


def search_channels(query: str, limit: int = 8) -> list[dict]:
    """Channels matching a name."""
    q = (query or "").strip()
    if len(q) < 2:
        return []
    html = _get("https://www.youtube.com/results",
                {"search_query": q, "sp": "EgIQAg==", "hl": "en", "gl": "US"}, timeout=20).text
    return parse_channel_search(html)[:limit]


def _search_filter(sort: str, uploaded: str, length: str, kind: str) -> str:
    """The `sp` parameter YouTube's search page uses for its filter menu."""
    f = b"".join(bytes([tag, v]) for tag, v in ((0x08, UPLOADED[uploaded]),
                                                 (0x10, 1 if kind == "videos" else 2),
                                                 (0x18, LENGTHS[length])) if v)
    raw = (bytes([0x08, SORTS[sort]]) if SORTS[sort] else b"") + bytes([0x12, len(f)]) + f
    return base64.urlsafe_b64encode(raw).decode()


def parse_count(text: str | None) -> int | None:
    """'219,559 views', '1.2M views', 'No views' -> a number."""
    t = str(text or "").replace(",", "").strip().lower()
    if t.startswith("no "):
        return 0
    m = re.match(r"([\d.]+)\s*([kmb]?)", t)
    if not m:
        return None
    return int(float(m.group(1)) * {"": 1, "k": 1e3, "m": 1e6, "b": 1e9}[m.group(2)])


def parse_age(text: str | None) -> float | None:
    """'8 hours ago', '3 weeks ago', 'Streamed 2 days ago' -> days, approximately."""
    m = re.search(r"(\d+)\s*([a-z]+)", str(text or "").lower())
    if not m:
        return None
    u = m.group(2)
    if u.startswith("mo"):
        days = 30.4
    elif u.startswith("mi") or u == "m":
        days = 1 / 1440
    elif u.startswith("s"):
        days = 1 / 86400
    elif u.startswith("h"):
        days = 1 / 24
    elif u.startswith("d"):
        days = 1
    elif u.startswith("w"):
        days = 7
    elif u.startswith("y"):
        days = 365
    else:
        return None
    return int(m.group(1)) * days


def parse_clock(text: str | None) -> int:
    """'4:40:21' -> seconds."""
    secs = 0
    for p in (int(p) for p in str(text or "").split(":") if p.isdigit()):
        secs = secs * 60 + p
    return secs


def parse_video_search(html_or_data: str | dict | None) -> list[dict]:
    """Long-form videos on a search page or continuation. Shorts cards are skipped."""
    data = page_data(html_or_data) if isinstance(html_or_data, str) else html_or_data
    if data is None:
        return []
    out = []
    for r in _find(data, "videoRenderer"):
        owner = ((r.get("ownerText") or r.get("longBylineText") or {}).get("runs") or [{}])[0]
        snippet = " ".join(x.get("text", "") for s in r.get("detailedMetadataSnippets") or []
                           for x in (s.get("snippetText") or {}).get("runs") or [])
        age_text = (r.get("publishedTimeText") or {}).get("simpleText", "")
        vid = r.get("videoId")
        out.append({
            "id": vid,
            "title": "".join(x.get("text", "") for x in (r.get("title") or {}).get("runs") or []),
            "channel": owner.get("text", ""),
            "channel_id": ((owner.get("navigationEndpoint") or {}).get("browseEndpoint") or {}).get("browseId", ""),
            "views": parse_count((r.get("viewCountText") or {}).get("simpleText")),
            "age_text": age_text, "age_days": parse_age(age_text),
            "live": not age_text and any("LIVE" in json.dumps(b) for b in r.get("badges") or []),
            "seconds": parse_clock((r.get("lengthText") or {}).get("simpleText")),
            "snippet": snippet.strip()[:300],
            "thumbnail": f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg"})
    return [x for x in out if x["id"]]


def _config_value(html: str, key: str) -> Any:
    m = re.search(r'"' + key + r'"\s*:\s*("(?:[^"\\]|\\.)*"|\{.*?\}(?=,"[A-Z_]+":))', html, re.S)
    return json.loads(m.group(1)) if m else None


def _continuation(data: Any) -> str | None:
    return next((r.get("token") for r in _find(data, "continuationCommand") if r.get("token")), None)


def search(query: str, kind: str = "videos", sort: str = "relevance", uploaded: str = "any",
           length: str = "any", language: str = "en", region: str = "US", pages: int = 1) -> dict:
    """YouTube search as the search page shows it. -> {query, kind, pages, results[, note]}

    length: short (under 4 min), medium (4-20) or long (over 20). Each page holds about
    20 videos. Ages come from the page's own text, so they are approximate.
    """
    q = re.sub(r"\s+", " ", str(query or "")).strip()[:200]
    if len(q) < 2:
        raise ValueError("type at least two characters to search")
    for name, value, allowed in (("kind", kind, ("videos", "channels")), ("sort", sort, SORTS),
                                 ("uploaded", uploaded, UPLOADED), ("length", length, LENGTHS)):
        if value not in allowed:
            raise ValueError(f"{name} must be one of: {', '.join(allowed)}")
    language = re.sub(r"[^A-Za-z-]", "", str(language or "en"))[:12] or "en"
    region = re.sub(r"[^A-Za-z]", "", str(region or "US"))[:2].upper() or "US"
    pages = max(1, min(int(pages or 1), SEARCH_PAGES_MAX))
    r = _get("https://www.youtube.com/results",
             {"search_query": q, "sp": _search_filter(sort, uploaded, length, kind),
              "hl": language, "gl": region}, timeout=20)
    if kind == "channels":
        return {"query": q, "kind": kind, "pages": 1, "results": parse_channel_search(r.text)}
    data = page_data(r.text)
    found, read = parse_video_search(data), 1
    key = _config_value(r.text, "INNERTUBE_API_KEY")
    context = _config_value(r.text, "INNERTUBE_CONTEXT")
    token = _continuation(data)
    while read < pages and token and key and context:
        time.sleep(PAGE_GAP_SEC)
        try:
            more = requests.post("https://www.youtube.com/youtubei/v1/search", params={"key": key},
                                 json={"context": context, "continuation": token},
                                 headers=HEADERS, cookies=COOKIES, timeout=20)
            more.raise_for_status()
            got = more.json()
        except (requests.RequestException, ValueError) as e:
            log.warning("search continuation failed for %r: %s", q, str(e)[:150])
            break
        found += parse_video_search(got)
        token, read = _continuation(got), read + 1
    found = list({v["id"]: v for v in found}.values())
    if sort == "date":
        found.sort(key=lambda v: v["age_days"] if v["age_days"] is not None else 1e9)
    out: dict[str, Any] = {"query": q, "kind": kind, "pages": read, "results": found}
    if not found:
        out["note"] = ("No results for these words and filters." if "No results found" in r.text
                       else "The results page could not be read.")
    return out


def thumbnail_url(video_id: str, size: str = "max") -> str:
    names = {"max": "maxresdefault", "high": "hqdefault", "medium": "mqdefault"}
    if size not in names:
        raise ValueError("size must be max, high or medium")
    return f"https://i.ytimg.com/vi/{video_id}/{names[size]}.jpg"


def thumbnail(video_id: str) -> bytes:
    """The largest thumbnail YouTube has for a video."""
    for size in ("max", "high", "medium"):
        r = requests.get(thumbnail_url(video_id, size), timeout=30)
        if r.status_code == 200 and len(r.content) > 5000:
            return r.content
    raise LookupError("this video has no thumbnail")


def video_id(text: str) -> str:
    """The 11-character id from a video id or any YouTube video link."""
    text = str(text or "").strip()
    m = (re.search(r"(?:v=|youtu\.be/|/shorts/|/embed/|/live/)([\w-]{11})", text)
         or re.fullmatch(r"([\w-]{11})", text))
    if not m:
        raise ValueError("that is not a YouTube video link or id")
    return m.group(1)
