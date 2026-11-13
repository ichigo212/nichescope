"""Research endpoints: the research store, live YouTube search and video tools."""
from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..research import database, storage
from ..youtube import captions, web
from .jobs import jobs

router = APIRouter(prefix="/api", tags=["research"])

NUMERIC = {"published_within_days", "views_min", "views_max", "outlier_min", "outlier_max", "minutes_min",
           "minutes_max", "channel_subscribers_min", "channel_subscribers_max", "started_within_days",
           "subscribers_min", "subscribers_max", "video_count_min", "video_count_max", "views_30d_min",
           "views_30d_max", "usual_views_min", "usual_views_max", "usual_minutes_min", "usual_minutes_max",
           "breakout_min", "breakout_within_days", "title_matches", "near_steps", "limit", "offset"}
LISTS = {"words_any", "description_words", "in_channels"}
VIDEO_FILTERS = {"title_pattern", "title_regex", "words_any", "in_channels", "near", "grade",
                 "published_within_days", "published_after", "published_before", "views_min", "views_max",
                 "outlier_min", "outlier_max", "minutes_min", "minutes_max", "channel_subscribers_min",
                 "channel_subscribers_max", "description_words", "language", "meaning", "sort", "limit", "offset"}
CHANNEL_FILTERS = {"started_within_days", "started_after", "started_before", "subscribers_min", "subscribers_max",
                   "video_count_min", "video_count_max", "views_30d_min", "views_30d_max", "usual_views_min",
                   "usual_views_max", "usual_minutes_min", "usual_minutes_max", "breakout_min",
                   "breakout_within_days", "title_pattern", "title_regex", "title_matches", "name_regex",
                   "bio_regex", "language", "country", "near", "near_steps", "grade", "sort", "limit", "offset"}


def clean_filters(raw: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
    """Drop blanks and unknown keys, convert numbers and split comma lists."""
    out: dict[str, Any] = {}
    for k, v in (raw or {}).items():
        if k not in allowed or v is None or (isinstance(v, str) and not v.strip()):
            continue
        if k in NUMERIC:
            try:
                v = float(str(v).replace(",", ""))
            except ValueError:
                raise ValueError(f"{k.replace('_', ' ')} must be a number") from None
            v = int(v) if v == int(v) else v
        elif k in LISTS and isinstance(v, str):
            v = [w.strip() for w in re.split(r"[,\n]", v) if w.strip()]
        out[k] = v
    return out


class YouTubeSearch(BaseModel):
    query: str = Field(..., min_length=2, max_length=200)
    kind: str = "videos"
    sort: str = "relevance"
    uploaded: str = "any"
    length: str = "any"
    language: str = "en"
    region: str = "US"
    pages: int = Field(1, ge=1, le=web.SEARCH_PAGES_MAX)


@router.post("/research/videos")
def find_videos(filters: dict[str, Any]) -> dict:
    return {**database.find_videos(**clean_filters(filters, VIDEO_FILTERS)), "stats": database.stats()}


@router.post("/research/channels")
def find_channels(filters: dict[str, Any]) -> dict:
    return {**database.find_channels(**clean_filters(filters, CHANNEL_FILTERS)), "stats": database.stats()}


@router.get("/research/channels/{channel}")
def channel_profile(channel: str) -> dict:
    return database.channel_profile(channel)


@router.get("/research/stats")
def stats() -> dict:
    return database.stats()


@router.post("/research/import")
def import_maps() -> dict:
    return {"imported": database.import_maps(), "stats": database.stats()}


@router.post("/research/meanings")
def compute_meanings() -> dict:
    return {"job": jobs.start("meanings", "Computing video meanings", lambda report: database.fill_meanings(report),
                              on_done=lambda r: {"result": r})}


@router.post("/youtube/search")
def youtube_search(body: YouTubeSearch) -> dict:
    """Live YouTube search, with outliers for channels already in the research store."""
    got = web.search(**body.model_dump())
    maps = storage.all_maps()
    ids = list({r.get("channel_id") or r.get("id") for r in got["results"]} - {None, ""})
    with database.connect() as con:
        known = {r["id"]: dict(r) for r in con.execute(
            f"SELECT id, subscribers, usual, views_30d, started_at FROM channels WHERE id IN "
            f"({','.join('?' * len(ids))})", ids)} if ids else {}
    for r in got["results"]:
        cid = r.get("channel_id") or r.get("id")
        c = known.get(cid) or {}
        r["maps"] = [{"map": m["title"], "mapId": m["channel_id"],
                      "grade": "own" if cid == m["channel_id"] else m["channels"][cid].get("grade")}
                     for m in maps if cid == m["channel_id"] or cid in m["channels"]]
        if got["kind"] == "channels":
            r.update(subscribers=c.get("subscribers"), usual=c.get("usual"), views_30d=c.get("views_30d"))
            continue
        usual, age, views = c.get("usual"), r.get("age_days"), r.get("views")
        r["channel_subscribers"] = c.get("subscribers")
        r["usual"] = usual
        r["outlier"] = (round(views / usual, 1) if usual and usual >= database.SMALL_USUAL and views is not None
                        and age is not None and age >= 1 else None)
        r["per_day"] = round(views / max(age, 1)) if views is not None and age is not None else None
    got["judged"] = sum(1 for r in got["results"] if r.get("usual"))
    return got


@router.get("/youtube/channels")
def channel_suggestions(q: str = Query("", max_length=200)) -> dict:
    """Autocomplete for channel names."""
    return {"rows": web.search_channels(q)}


@router.get("/videos/{video}/transcript")
def transcript(video: str, language: str = "en") -> dict:
    try:
        return captions.transcript(video, language)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/videos/{video}/thumbnail")
def thumbnail(video: str) -> Response:
    vid = web.video_id(video)
    try:
        data = web.thumbnail(vid)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return Response(data, media_type="image/jpeg",
                    headers={"Content-Disposition": f'attachment; filename="{vid}.jpg"'})
