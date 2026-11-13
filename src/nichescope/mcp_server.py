"""MCP server: Nichescope's research as tools for MCP clients.

Run over stdio with `python -m nichescope mcp`, or over Streamable HTTP at `/mcp` while
the web app is running. Each tool's description states whether it is free, spends
YouTube API quota or calls the language model.
"""
from __future__ import annotations

import re
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver import Image
from mcp.types import ToolAnnotations

from . import __version__
from .projects import pipeline
from .projects import store as projects_store
from .research import chat, database, mapping, metrics, own, storage, study, topics
from .youtube import auth, captions, data_api, quota, web

INSTRUCTIONS = (
    "Nichescope researches YouTube niches on the user's own machine. Start with `status` to see the "
    "mapped channels. Reading maps and searching the research store (find_videos, find_channels, "
    "get_map, get_breakouts) is free. YouTube is read from public pages by default, so "
    "youtube_search, map_channel, add_competitors, get_channel and get_transcript use no API quota; "
    "get_video always uses the Data API (1 unit). generate_topics, follow_up_topics and ask call the "
    "language model and take up to a minute. Video projects can be started and scripted here; their "
    "voiceover, clips and final video are produced in the app.")

READ = ToolAnnotations(read_only_hint=True, open_world_hint=False)
READ_WEB = ToolAnnotations(read_only_hint=True, open_world_hint=True)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=True)
DESTRUCTIVE = ToolAnnotations(read_only_hint=False, destructive_hint=True, open_world_hint=False)

VIDEO_KEYS = ("id", "title", "channel", "channel_id", "channel_subscribers", "published_at", "age_days",
              "seconds", "views", "outlier", "per_day", "gaining", "similarity", "url")
CHANNEL_KEYS = ("id", "title", "handle", "subscribers", "started_at", "video_count", "total_views", "usual",
                "views_30d", "breakout", "breakout_video", "matches", "minutes", "country", "language", "bio",
                "maps", "url")
TRANSCRIPT_WORDS = 6000

server = MCPServer(name="nichescope", title="Nichescope", instructions=INSTRUCTIONS, version=__version__)


def _pick(row: dict, keys: tuple[str, ...]) -> dict:
    return {k: row[k] for k in keys if row.get(k) not in (None, "", [])}


def _lists(value: str) -> list[str]:
    return [w.strip() for w in re.split(r"[,\n]", value or "") if w.strip()]


def _given(**kw: Any) -> dict:
    return {k: v for k, v in kw.items() if v is not None and not (isinstance(v, str) and not v.strip())}


def _channel_row(cid: str, r: dict) -> dict:
    out = {"id": cid, "title": r.get("title", cid), "grade": r.get("grade"), "coverage": r.get("coverage") or None,
           "views_sent": r.get("proven") or None, "subscribers": r.get("subscribers"),
           "views_30d": r.get("views_30d"), "usual": r.get("usual"), "breakout": r.get("breakout"),
           "steps_out": r.get("step") or None, "added_by_user": r.get("added") or None,
           "excluded": r.get("off") or None}
    return {k: v for k, v in out.items() if v is not None}


def _on_map(m: dict, channel: str, where: str = "channels") -> str:
    rows = m.get(where) or {}
    t = str(channel or "").strip()
    if t in rows:
        return t
    want = t.lower().lstrip("@")

    def names(r: dict) -> set[str]:
        r = {**(r.get("row") or {}), **{k: v for k, v in r.items() if k != "row"}}
        return {(r.get("title") or "").lower(), (r.get("handle") or "").lower().lstrip("@")} - {""}

    hits = [c for c, r in rows.items() if want and want in names(r)]
    if len(hits) == 1:
        return hits[0]
    if hits:
        raise ValueError(f"{len(hits)} channels are called {t!r}; use the channel id")
    raise ValueError(f"{t!r} is not on {m['title']}'s map")


def _summary(m: dict, grade: str = "near", limit: int = 60) -> dict:
    ids = database.near_ids(m, grade)
    rows = sorted((_channel_row(c, m["channels"][c]) for c in ids),
                  key=lambda r: (-(r.get("views_sent") or 0), -(r.get("coverage") or 0), -(r.get("views_30d") or 0)))
    out = {"id": m["channel_id"], "title": m["title"], "handle": m.get("handle", ""),
           "subscribers": m.get("subscribers"), "usual_views": m.get("usual"), "views_30d": m.get("views_30d"),
           "scanned_at": m.get("scanned_at", ""), "channels_on_map": len(m["channels"]), "grade_shown": grade,
           "matching": len(rows), "channels": rows[:max(1, min(int(limit or 60), 200))],
           "caution": metrics.confidence(m)}
    acc = own.accuracy(m)
    if acc:
        out["traffic_check"] = {"channels_sending_viewers": acc["real"], "found_by_public_scan": acc["found"]}
    return out


# ---------------------------------------------------------------- free reads

@server.tool(annotations=READ)
def status() -> dict:
    """Start here. Mapped channels, research store size, connected channels and YouTube quota left today. Free."""
    return {"maps": [{"id": s["channel_id"], "title": s["title"], "scanned_at": s["scanned_at"],
                      "own_channel": auth.is_own(s["channel_id"])} for s in storage.saved()],
            "store": database.stats(), "connected_channels": auth.accounts(),
            "youtube_quota_left_today": quota.left()}


@server.tool(annotations=READ)
def get_map(map: str, grade: str = "near", limit: int = 60) -> dict:
    """One mapped channel's neighbourhood: the channels YouTube recommends around it, closest first. map = title, @handle or id. grade: near (default), close, medium, far, proven (measured to send viewers) or any. Free."""
    return _summary(storage.find(map), grade, limit)


@server.tool(annotations=READ)
def get_breakouts(map: str, within_days: int = 30, limit: int = 30) -> dict:
    """Videos far above their channel's usual views on a map's channels, biggest first. outlier = views / the channel's usual (4.2 = 4.2x). Free."""
    m = storage.find(map)
    rows = [v for v in metrics.breakouts(m) if v["on_topic"] and metrics.is_recent(v, within_days)]
    return {"map": m["title"], "total": len(rows),
            "videos": [{**_pick(v, VIDEO_KEYS), "url": f"https://www.youtube.com/watch?v={v['id']}"}
                       for v in rows[:max(1, min(limit, 100))]]}


@server.tool(annotations=READ)
def find_videos(near: str = "", grade: str = "any", title_pattern: str = "", title_regex: str = "",
                words_any: str = "", in_channels: str = "", published_within_days: float | None = None,
                published_after: str = "", published_before: str = "", views_min: float | None = None,
                views_max: float | None = None, outlier_min: float | None = None, outlier_max: float | None = None,
                minutes_min: float | None = None, minutes_max: float | None = None,
                channel_subscribers_min: float | None = None, channel_subscribers_max: float | None = None,
                description_words: str = "", language: str = "", meaning: str = "", sort: str = "",
                limit: int = 20, offset: int = 0) -> dict:
    """Search every long-form video the maps have read. outlier = views / channel's usual; outlier_max finds underperformers (older than a week); per_day = average views a day; gaining = views a day between the last two reads. title_pattern uses * wildcards ("I * for 100 days"). near = a map's title. words_any, description_words, in_channels: comma-separated. meaning = an idea in plain words, ranked by semantic similarity. sort: meaning, outlier, flops, views, newest or per_day. Free."""
    got = database.find_videos(**_given(
        near=near, grade=grade, title_pattern=title_pattern, title_regex=title_regex,
        words_any=_lists(words_any) or None, in_channels=_lists(in_channels) or None,
        published_within_days=published_within_days, published_after=published_after,
        published_before=published_before, views_min=views_min, views_max=views_max, outlier_min=outlier_min,
        outlier_max=outlier_max, minutes_min=minutes_min, minutes_max=minutes_max,
        channel_subscribers_min=channel_subscribers_min, channel_subscribers_max=channel_subscribers_max,
        description_words=_lists(description_words) or None, language=language, meaning=meaning, sort=sort,
        limit=limit, offset=offset))
    return {"total": got["total"], "more": got["more"], "videos": [_pick(r, VIDEO_KEYS) for r in got["videos"]]}


@server.tool(annotations=READ)
def find_channels(near: str = "", near_steps: int | None = None, grade: str = "any",
                  started_within_days: float | None = None, started_after: str = "", started_before: str = "",
                  subscribers_min: float | None = None, subscribers_max: float | None = None,
                  video_count_min: float | None = None, video_count_max: float | None = None,
                  views_30d_min: float | None = None, views_30d_max: float | None = None,
                  usual_views_min: float | None = None, usual_views_max: float | None = None,
                  usual_minutes_min: float | None = None, usual_minutes_max: float | None = None,
                  breakout_min: float | None = None, breakout_within_days: float = 30, title_pattern: str = "",
                  title_regex: str = "", title_matches: int = 1, name_regex: str = "", bio_regex: str = "",
                  language: str = "", country: str = "", sort: str = "views_30d", limit: int = 20,
                  offset: int = 0) -> dict:
    """Search every channel the maps have met: by age (started_within_days), size, views in the last 30 days, usual views, typical video length in minutes, biggest recent outlier (breakout_min), title formats (title_pattern with * wildcards or title_regex, needing title_matches videos), bio_regex, language (en) and country (US). near = a map's title, near_steps limits it to that many steps out. sort: views_30d, subscribers, newest, breakout, usual, matches, or closest (needs near). Free."""
    got = database.find_channels(**_given(
        near=near, near_steps=near_steps, grade=grade, started_within_days=started_within_days,
        started_after=started_after, started_before=started_before, subscribers_min=subscribers_min,
        subscribers_max=subscribers_max, video_count_min=video_count_min, video_count_max=video_count_max,
        views_30d_min=views_30d_min, views_30d_max=views_30d_max, usual_views_min=usual_views_min,
        usual_views_max=usual_views_max, usual_minutes_min=usual_minutes_min, usual_minutes_max=usual_minutes_max,
        breakout_min=breakout_min, breakout_within_days=breakout_within_days, title_pattern=title_pattern,
        title_regex=title_regex, title_matches=title_matches, name_regex=name_regex, bio_regex=bio_regex,
        language=language, country=country, sort=sort, limit=limit, offset=offset))
    return {"total": got["total"], "more": got["more"], "channels": [_pick(r, CHANNEL_KEYS) for r in got["channels"]]}


@server.tool(annotations=READ)
def who_sends_viewers(channel: str) -> dict:
    """Channels whose videos YouTube recommends this channel beside. For a connected channel, views_sent is measured by YouTube Analytics; otherwise coverage (how often it appeared beside them) is an estimate. channel = a map's title or a channel id. Free."""
    try:
        cid = storage.find(channel)["channel_id"]
    except LookupError:
        cid = next(iter(database.channel_ids([channel])))
    rows = database.points_to(cid)
    return {"channel": cid, "total": len(rows), "channels": rows[:60]}


@server.tool(annotations=READ)
def list_topic_runs(map: str) -> dict:
    """A map's topic runs and questions, newest first, with their topics. Free."""
    m = storage.find(map)
    return {"map": m["title"], "settings": topics.settings_of(m),
            "runs": [{"run": b["id"], "at": b["at"], "instructions": b.get("instructions", ""),
                      "topics": [{"number": i + 1, "topic": t["topic"], "fit": t.get("fit"),
                                  "already_on_youtube": bool(t.get("on_youtube"))} for i, t in enumerate(b["topics"])]}
                     for b in m.get("topics", [])[:20]],
            "saved_topics": [{"topic": s["topic"], "status": s["status"]} for s in m.get("saved_topics", [])]}


@server.tool(annotations=READ)
def get_topic_run(map: str, run: str) -> dict:
    """One topic run in full: analysis, each topic's reasoning, titles, evidence videos and follow-up conversation. run = id from list_topic_runs. Free."""
    m = storage.find(map)
    b = next((b for b in m.get("topics", []) if b["id"] == run), None)
    if b is None:
        raise ValueError("no such run; call list_topic_runs")
    by_id = {v["id"]: v for v in metrics.breakouts(m)}
    return {"map": m["title"], "run": b["id"], "at": b["at"], "analysis": b.get("analysis", ""),
            "topics": [{"number": i + 1, **{k: t.get(k) for k in ("topic", "why", "detail", "reasons", "titles",
                                                                  "fit", "expected_views", "on_youtube")},
                        "evidence": [_pick(by_id[e], VIDEO_KEYS) for e in t["evidence"] if e in by_id]}
                       for i, t in enumerate(b["topics"])],
            "followups": [{"role": r["role"], "content": r["content"]} for r in b.get("followups", [])]}


# ---------------------------------------------------------------- YouTube reads

@server.tool(annotations=READ_WEB)
def youtube_search(query: str, kind: str = "videos", sort: str = "relevance", uploaded: str = "any",
                   length: str = "any", language: str = "en", region: str = "US", pages: int = 1) -> dict:
    """Search YouTube live. kind videos or channels; sort relevance, date, views or rating; uploaded any, hour, today, week, month or year; length any, short (<4 min), medium or long (>20 min); pages 1-3 (about 20 results each). Ages are approximate. Uses no API quota."""
    got = web.search(query, kind=kind, sort=sort, uploaded=uploaded, length=length,
                     language=language, region=region, pages=pages)
    return {**{k: got[k] for k in ("query", "kind", "pages")}, **({"note": got["note"]} if got.get("note") else {}),
            "results": [{k: v for k, v in r.items() if k not in ("thumbnail", "avatar") and v not in (None, "", [])}
                        for r in got["results"]]}


@server.tool(annotations=READ_WEB)
def get_channel(channel: str, live: bool = False) -> dict:
    """Any YouTube channel: profile, latest and most viewed long-form videos and biggest outliers. From the research store by default (free; channel must have been read). live=true reads it from YouTube now and stores it. channel = link, @handle, id or name."""
    if live:
        cid = mapping.resolve(channel)
        info = data_api.channels([cid]).get(cid)
        if not info:
            raise ValueError("YouTube has no such channel")
        videos = data_api.uploads(info["uploads"])
        database.remember(cid, info, videos, metrics.measure(videos))
        channel = cid
    p = database.channel_profile(channel)
    out = _pick(p, CHANNEL_KEYS)
    for k in ("latest_videos", "popular_videos", "biggest_outliers"):
        out[k] = [_pick(r, ("id", "title", "published_at", "views", "outlier", "per_day", "seconds")) for r in p[k]]
    out["points_to"] = p["points_to"]
    return out


@server.tool(annotations=READ_WEB)
def get_video(video: str, transcript: bool = False) -> dict:
    """A video's exact numbers, description and tags (1 quota unit), and optionally its transcript (no quota). video = link or id."""
    vid = web.video_id(video)
    rows = data_api.videos([vid])
    if not rows:
        raise ValueError("YouTube has no such video")
    out = {k: v for k, v in rows[0].items() if k != "public"}
    out["url"] = f"https://www.youtube.com/watch?v={vid}"
    if transcript:
        try:
            out["transcript"] = captions.transcript(vid)["text"][:40_000]
        except LookupError as e:
            out["transcript_error"] = str(e)
    return out


@server.tool(annotations=READ_WEB)
def get_transcript(video: str, language: str = "en", start_word: int = 0, max_words: int = TRANSCRIPT_WORDS,
                   timestamps: bool = False) -> dict:
    """What a video says, from its captions. Long transcripts come in parts: call again with start_word = next_start_word. timestamps=true returns timed lines instead. Uses no quota."""
    t = captions.transcript(video, language)
    if timestamps:
        return {"video": t["video"], "title": t["title"], "language": t["language"], "lines": t["segments"][:2000]}
    words = t["text"].split()
    start = max(0, int(start_word or 0))
    n = max(100, min(int(max_words or TRANSCRIPT_WORDS), 20000))
    part = words[start:start + n]
    more = start + len(part) < len(words)
    return {"video": t["video"], "title": t["title"], "language": t["language"], "words": len(words),
            "start_word": start, "text": " ".join(part), "next_start_word": start + len(part) if more else None}


@server.tool(annotations=READ_WEB)
def get_thumbnail(video: str) -> Image:
    """A video's thumbnail image, the largest available. Uses no quota."""
    return Image(data=web.thumbnail(web.video_id(video)), format="jpeg")


# ---------------------------------------------------------------- changing maps

@server.tool(annotations=WRITE)
def map_channel(channel: str, steps: int = 1, anyway: bool = False) -> dict:
    """Map a channel's niche: read its latest videos, who YouTube recommends beside them, then go `steps` steps further out (0-5). Takes a few minutes; uses no API quota unless the installation reads YouTube through the Data API. Very small channels are refused unless anyway=true, because their recommendations are mostly noise. channel = link, @handle, id or name."""
    check = mapping.check_size(channel)
    if check["small"] and not anyway:
        return {"refused": f"{check['title']} has {check['subscribers']} subscribers; YouTube's recommendations "
                           "around it are unreliable. Map a larger competitor, or call again with anyway=true."}
    before = quota.left()
    m = mapping.map_channel(check["id"], steps)
    return {**_summary(m, "near", 40), "quota_spent": before - quota.left()}


@server.tool(annotations=WRITE)
def add_competitors(map: str, names: str) -> dict:
    """Add channels the map did not find, comma or line separated (names, links or @handles). Channels that cannot be found are reported; the rest are added."""
    m = storage.find(map)
    before = set(m["channels"])
    m, problems = mapping.add_competitors(m["channel_id"], _lists(names))
    return {"map": m["title"], "added": [_channel_row(c, m["channels"][c]) for c in m["channels"] if c not in before],
            "not_added": problems}


@server.tool(annotations=DESTRUCTIVE)
def remove_competitor(map: str, channel: str, restore: bool = False) -> dict:
    """Remove a channel from a map for good (it stays off through rescans), or restore=true to bring a removed one back. Free. Confirm with the user first."""
    m = storage.find(map)
    if restore:
        cid = _on_map(m, channel, "removed")
        m = mapping.restore_channel(m["channel_id"], cid)
    else:
        cid = _on_map(m, channel)
        m = mapping.remove_channel(m["channel_id"], cid)
    return {"map": m["title"], "restored" if restore else "removed": cid, "channels_on_map": len(m["channels"])}


@server.tool(annotations=READ)
def get_study(map: str) -> dict:
    """The competitor study of a map: what is holding the channel back, title habits that go with breakouts, thumbnail styles of competitors' best and worst videos against this channel's, and how soon small competitors broke out. Free; run_study makes or refreshes it."""
    m = storage.find(map)
    got = study.view(m)
    if not got:
        return {"map": m["title"], "study": None, "note": "no study yet; run_study makes one"}
    return {"map": m["title"], **{k: got[k] for k in ("at", "channels", "videos", "findings", "rising", "escapes")},
            "titles": [t for t in got["titles"] if t["up"] or t["down"]], "styles": got["styles"]}


@server.tool(annotations=WRITE)
def run_study(map: str) -> dict:
    """Study a map's near competitors again (takes a few minutes). Public reads use no quota; thumbnail labels use the model."""
    m = storage.find(map)
    study.run(m["channel_id"])
    return get_study(m["channel_id"])


@server.tool(annotations=WRITE)
def recheck_map(map: str) -> dict:
    """Judge again which channels on a map make the same kind of videos, set aside the rest and read the new ones, without rescanning. Uses the model; public reads use no quota."""
    m = storage.find(map)
    m = mapping.recheck(m["channel_id"])
    fits: dict[str, int] = {}
    for r in m["channels"].values():
        fits[r.get("fit") or "not judged"] = fits.get(r.get("fit") or "not judged", 0) + 1
    return {"map": m["title"], "channels": len(m["channels"]), "fit": fits}


@server.tool(annotations=DESTRUCTIVE)
def remove_map(map: str = "", restore: str = "") -> dict:
    """Remove a whole map (it is kept aside and can be restored), or pass restore with the file name from list_removed_maps to bring one back. Confirm with the user before removing."""
    if restore:
        cid = storage.restore(restore)
        return {"restored": storage.require(cid)["title"]}
    m = storage.find(map)
    return {"removed": m["title"], "kept_as": storage.remove(m["channel_id"])}


@server.tool(annotations=READ)
def list_removed_maps() -> list[dict]:
    """Maps removed earlier and kept aside, newest first, with the file name to restore each."""
    return [{k: r[k] for k in ("file", "title", "at")} for r in storage.removed()]


@server.tool(annotations=WRITE)
def set_learning(map: str, channel: str, learn: bool) -> dict:
    """Include (true) or exclude (false) a channel from breakouts, topics and answers, keeping it on the map. Free."""
    m = storage.find(map)
    m = mapping.set_learning(m["channel_id"], _on_map(m, channel), learn)
    return {"map": m["title"], "channel": channel, "learning": learn}


@server.tool(annotations=WRITE)
def topic_settings(map: str, topics_per_run: int = 0, titles_per_topic: int = 0, instructions: str | None = None,
                   check_youtube: bool | None = None, read_descriptions: bool | None = None) -> dict:
    """Read or change a map's topic settings: topics per run (1-20), titles per topic (1-10), standing instructions (up to 2000 characters; empty string clears), whether to check each topic on YouTube, and whether to read video descriptions. With only map, it just reads them. Free."""
    m = storage.find(map)
    if topics_per_run or titles_per_topic or instructions is not None or check_youtube is not None \
            or read_descriptions is not None:
        m = topics.update_settings(m["channel_id"], topics=topics_per_run or None, titles=titles_per_topic or None,
                                   instructions=instructions, check_youtube=check_youtube,
                                   read_descriptions=read_descriptions)
    return {"map": m["title"], **topics.settings_of(m)}


@server.tool(annotations=WRITE)
def mark_topic(map: str, kind: str, text: str, mark: str = "") -> dict:
    """Like ("like") or reject ("no") a topic or title so later runs learn from it; empty mark clears it. kind: topics or titles. Free."""
    m = storage.find(map)
    topics.mark(m["channel_id"], kind, text, mark or None)
    return {"map": m["title"], "kind": kind, "text": text, "mark": mark or None}


# ---------------------------------------------------------------- language model

@server.tool(annotations=WRITE)
def generate_topics(map: str, instructions: str = "", topics_per_run: int = 0, titles_per_topic: int = 0) -> dict:
    """Generate video topics for a mapped channel, each grounded in breakout videos from its niche and never repeating earlier runs. Calls the language model and takes about a minute. instructions steer this run; defaults come from topic_settings."""
    m = storage.find(map)
    m = topics.suggest(m["channel_id"], instructions, n=topics_per_run or None, titles=titles_per_topic or None)
    return get_topic_run(m["channel_id"], m["topics"][0]["id"])


@server.tool(annotations=WRITE)
def follow_up_topics(map: str, run: str, message: str) -> dict:
    """Continue a topic run: ask for more topics in a direction, more or shorter titles for topic #n, or why a topic would work. New topics and titles are added to the run. Calls the language model."""
    m = storage.find(map)
    topics.follow_up(m["channel_id"], run, message)
    return get_topic_run(m["channel_id"], run)


@server.tool(annotations=WRITE)
def ask(map: str, question: str) -> dict:
    """Ask a question about a mapped channel's niche, answered from its channels, breakouts and the user's analytics. Prefer find_videos and find_channels for searches: they are exact and free. Calls the language model."""
    m = chat.ask(storage.find(map)["channel_id"], question)
    return {"map": m["title"], "answer": m["chats"][0]["messages"][-1]["content"]}


# ---------------------------------------------------------------- video projects

@server.tool(annotations=READ)
def list_projects() -> dict:
    """Video projects and how far each has got: script, scenes, clips or done. Free."""
    return {"projects": [{"id": p["id"], "title": p["title"], "scenes": len(p["scenes"]),
                          "clips": sum(1 for s in p["scenes"] if (s.get("clip") or {}).get("file")),
                          "rendered": (p.get("render") or {}).get("status") == "done"}
                         for p in projects_store.all_projects()]}


@server.tool(annotations=READ)
def get_project(project: str) -> dict:
    """A video project: its script, voice, scenes with their visual descriptions and video prompts, and a cost estimate for generating its clips. Free."""
    p = projects_store.load(project)
    return {"id": p["id"], "title": p["title"], "script": p["script"], "voice": p["voice"],
            "voiceover_seconds": (p.get("voiceover") or {}).get("seconds"),
            "scenes": [{"number": i + 1, "text": s["text"], "visual": s["visual"], "prompt": s["prompt"],
                        "has_clip": bool((s.get("clip") or {}).get("file"))} for i, s in enumerate(p["scenes"])],
            "estimate": pipeline.estimate(p)}


@server.tool(annotations=WRITE)
def create_project(title: str = "", script: str = "", map: str = "", run: str = "", topic: str = "",
                   draft_minutes: int = 0) -> dict:
    """Start a video project, either from a topic of a topic run (map, run and topic text) or from a title and script. draft_minutes > 0 also writes the narration script with the language model. Voiceover, clips and the final video are made in the app, which shows their cost first."""
    if map and run and topic:
        p = pipeline.create_from_topic(storage.find(map)["channel_id"], run, topic)
    else:
        p = projects_store.create(title, script)
    if draft_minutes:
        p = pipeline.draft_script(p["id"], max(1, min(draft_minutes, 60)))
    return get_project(p["id"])


# ---------------------------------------------------------------- prompts

@server.prompt(title="Niche report")
def niche_report(map: str) -> str:
    """A briefing on what is working in a channel's niche right now."""
    return (f"Using the nichescope tools, write a briefing on the niche around {map}. Call get_map and "
            "get_breakouts first, then find_videos for the last 30 days sorted by outlier. Cover: who is "
            "growing, which formats and title patterns are breaking out, and three concrete video ideas with "
            "the breakouts that support each.")


@server.prompt(title="Plan the next video")
def plan_next_video(map: str, idea: str = "") -> str:
    """Plan one video for a mapped channel, grounded in its niche's breakouts."""
    about = f" about {idea}" if idea else ""
    return (f"Plan the next video{about} for {map}. Use get_breakouts and find_videos (with meaning when an "
            "idea is given) to find proven examples, read the transcripts of the two strongest with "
            "get_transcript, then propose a title, a thumbnail concept, the opening 30 seconds and an outline.")


def main() -> None:
    server.run()
