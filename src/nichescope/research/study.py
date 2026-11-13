"""What the channels around a map do differently when their videos break out.

A study reads the map's near competitors (enough subscribers and views to have got going
themselves) and compares each video with its own channel's usual views:

- Titles: how often a title habit appears, and how videos with it do against those
  without, inside each channel (so a big channel cannot carry a habit on its own).
- Thumbnails: the vision model labels each competitor's best and worst videos and this
  channel's latest, so the styles can be compared.
- First breakouts: how many videos the smallest competitors needed before one reached
  ESCAPE_VIEWS.
- For a connected channel: how its openings hold against similar videos, where its long
  videos' views come from, and whether a setting holds them back.

`findings` turns those numbers into what is holding the channel back, biggest first.
A study is kept per map and refreshed weekly while the app runs.
"""
from __future__ import annotations

import logging
import re
import statistics
from collections.abc import Callable

import requests

from .. import ai
from ..config import settings
from ..util import Reporter, days_since, hours_since, read_json, silent, utc_now, write_json
from ..youtube import analytics, auth, data_api
from . import database, metrics, reach, relevance, storage

log = logging.getLogger(__name__)

CHANNELS = 30
NEAR_USUAL = 500
NEAR_SUBS = 5000
SETTLED_DAYS = 14
MIN_VIDEOS = 15
READ_VIDEOS = 60
ESCAPE_CHANNELS = 8
ESCAPE_VIEWS = 10_000
HISTORY_VIDEOS = 300
LABELLED_EACH_END = 4
OURS_LABELLED = 30
LABEL_BATCH = 20
GALLERY = 12
STALE_DAYS = 7
RISING_DAYS = 60
RECENT_OURS_DAYS = 90
OURS_MIN = 5
WINDOW_DAYS = 90
LONG_MIN_SEC = 181


def _has(pattern: str) -> Callable[[str], bool]:
    rx = re.compile(pattern, re.I)
    return lambda t: bool(rx.search(t))


def caps_words(title: str) -> int:
    return len(re.findall(r"\b[A-Z][A-Z0-9'\-]{2,}\b", title))


# Title habits, named the way the page shows them.
FEATURES: tuple[tuple[str, str, Callable[[str], bool]], ...] = (
    ("i", "Opens I, We or My", _has(r"^(i|i'm|i've|we|my|our)\b")),
    ("he", "Opens He, She or They", _has(r"^(he|she|they|his|her|their)\b")),
    ("you", "Opens You, Your or Never", _has(r"^(you|your|you're|never)\b")),
    ("what", "Opens What, Why or How", _has(r"^(what|why|how)\b")),
    ("question", "Ends in a question mark", lambda t: t.rstrip().endswith("?")),
    ("bang", "Ends in !", lambda t: t.rstrip().endswith("!")),
    ("but", "Turns on but or until", _has(r"\b(until|but)\b")),
    ("number", "Has a number", _has(r"\d")),
    ("list", "A list or ranking", _has(r"\btop \d+|\branked\b|\branking\b|tier list|\b\d+ (things|ways|reasons)\b")),
    ("challenge", "A challenge or experiment",
     _has(r"\bi (spent|tried|survived|built|lived)\b|\bfor \d+ (days|hours)\b|24 hours")),
    ("explained", "Says explained", _has(r"\bexplained\b")),
    ("parts", "Has a | or : part", lambda t: "|" in t or ":" in t),
    ("brackets", "Has brackets", _has(r"[\(\[]")),
    ("caps0", "No capitalised words", lambda t: caps_words(t) == 0),
    ("caps1", "1 or 2 capitalised words", lambda t: 1 <= caps_words(t) <= 2),
    ("caps3", "3 or more capitalised words", lambda t: caps_words(t) >= 3),
    ("short", "Under 40 characters", lambda t: len(t) < 40),
    ("long", "Over 70 characters", lambda t: len(t) > 70),
)

LABEL_SCHEMA = {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {
    "type": "object",
    "required": ["n", "face", "faces", "text_words", "background", "arrow_or_circle", "split_panels",
                 "shows_a_situation", "strong_emotion"],
    "properties": {"n": {"type": "integer"}, "face": {"type": "boolean"}, "faces": {"type": "integer"},
                   "text_words": {"type": "integer"},
                   "background": {"type": "string", "enum": ["bright", "colourful", "dark", "plain"]},
                   "arrow_or_circle": {"type": "boolean"}, "split_panels": {"type": "boolean"},
                   "shows_a_situation": {"type": "boolean"}, "strong_emotion": {"type": "boolean"}}}}}}
LABEL_ASK = (
    "These are YouTube thumbnails, numbered in order. Label each by what is plainly visible.\n"
    "face: a human face is clearly visible. faces: how many faces.\n"
    "text_words: how many words are written on it.\n"
    "background: bright (daylight or a lit place), colourful (vivid, not daylight), dark (mostly dark), "
    "plain (a flat colour).\n"
    "arrow_or_circle: an arrow or a circle is drawn on it. split_panels: divided into two or more panels.\n"
    "shows_a_situation: you can tell what is happening, not just one figure posing.\n"
    "strong_emotion: a face shows a strong emotion such as shock, fear or joy.")
STYLE_ROWS = (("face", "Shows a face"), ("strong_emotion", "A strong emotion"),
              ("shows_a_situation", "Shows a situation"),
              ("arrow_or_circle", "An arrow or circle"), ("split_panels", "Split into panels"))


def _dir():
    d = settings().data_dir / "study"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(map_id: str):
    return _dir() / f"{map_id}.json"


def _age(v: dict) -> float:
    return days_since(v.get("published_at"))


def _slim(v: dict) -> dict:
    return {k: v.get(k) for k in ("id", "title", "views", "seconds", "published_at", "thumbnail")}


# ---------------------------------------------------------------- pure parts

def pool(m: dict) -> list[str]:
    """Near competitors that got going themselves, real traffic sources first."""
    rows = {c: r for c, r in relevance.relevant_channels(m).items()
            if not r.get("off") and (r.get("grade") != "far" or r.get("fit") == "same" or r.get("proven"))
            and (r.get("usual") or 0) >= NEAR_USUAL and (r.get("subscribers") or 0) >= NEAR_SUBS}
    return sorted(rows, key=lambda c: (bool(rows[c].get("proven")), rows[c].get("coverage") or 0,
                                       rows[c].get("subscribers") or 0), reverse=True)[:CHANNELS]


def scored(channels: dict[str, dict]) -> list[dict]:
    """Every settled competitor video, with `lift`: its views over its own channel's usual."""
    rows = []
    for cid, c in channels.items():
        vs = [v for v in c["videos"] if _age(v) >= SETTLED_DAYS and v.get("title")]
        if len(vs) < MIN_VIDEOS:
            continue
        usual = statistics.median(v["views"] for v in vs)
        if usual:
            rows += [{**v, "cid": cid, "lift": v["views"] / usual} for v in vs]
    return rows


def title_table(rows: list[dict]) -> list[dict]:
    """[{key, label, count, share, with, without, up, down}], `up` and `down` counting the
    channels where the habit's videos did better or worse than the rest."""
    out = []
    ids = {r["cid"] for r in rows}
    for key, label, f in FEATURES:
        yes = [r for r in rows if f(r["title"])]
        no = [r for r in rows if not f(r["title"])]
        up = down = 0
        for cid in ids:
            a = [r["lift"] for r in yes if r["cid"] == cid]
            b = [r["lift"] for r in no if r["cid"] == cid]
            if len(a) >= 3 and len(b) >= 3:
                up += statistics.median(a) > statistics.median(b)
                down += statistics.median(a) < statistics.median(b)
        out.append({"key": key, "label": label, "count": len(yes),
                    "share": round(len(yes) / len(rows), 3) if rows else 0,
                    "with": round(statistics.median(r["lift"] for r in yes), 2) if yes else None,
                    "without": round(statistics.median(r["lift"] for r in no), 2) if no else None,
                    "up": up, "down": down})
    return out


def share_of(titles: list[str], key: str) -> float | None:
    f = next(f for k, _, f in FEATURES if k == key)
    return round(sum(bool(f(t)) for t in titles) / len(titles), 3) if titles else None


def rising(rows: list[dict], min_videos: int = 8, by: float = 0.05) -> list[dict]:
    """Title habits used more in the last RISING_DAYS than before."""
    recent = [r for r in rows if _age(r) <= RISING_DAYS]
    older = [r for r in rows if _age(r) > RISING_DAYS]
    if len(recent) < min_videos or len(older) < min_videos:
        return []
    out = []
    for key, label, f in FEATURES:
        got = sum(bool(f(r["title"])) for r in recent)
        now, was = got / len(recent), sum(bool(f(r["title"])) for r in older) / len(older)
        if got >= min_videos and now - was >= by:
            out.append({"key": key, "label": label, "was": round(was, 3), "now": round(now, 3)})
    return sorted(out, key=lambda x: x["was"] - x["now"])


def escapes(history: list[tuple[str, int, list[dict]]]) -> list[dict]:
    """For each small channel, oldest video first: which video first reached ESCAPE_VIEWS."""
    out = []
    for name, subs, vs in history:
        if not vs:
            continue
        hit = next((i for i, v in enumerate(vs) if v["views"] >= ESCAPE_VIEWS), None)
        row = {"channel": name, "subs": subs, "videos": len(vs), "hit": None, "days": None, "title": "", "views": None}
        if hit is not None:
            # Public pages give rough dates ("1 year ago"); a gap of zero means the dates cannot tell.
            days = round(days_since(vs[0]["published_at"]) - days_since(vs[hit]["published_at"]))
            row.update(hit=hit + 1, days=days if days > 0 else None, title=vs[hit]["title"], views=vs[hit]["views"])
        out.append(row)
    return out


def style_of(rows: list[dict]) -> dict | None:
    """Shares of a group's labelled thumbnails."""
    if not rows:
        return None
    n = len(rows)
    got = {k: round(sum(bool(r.get(k)) for r in rows) / n, 3) for k, _ in STYLE_ROWS}
    got.update(n=n, faces=round(statistics.mean(r.get("faces", 0) for r in rows), 1),
               words=round(statistics.mean(r.get("text_words", 0) for r in rows), 1),
               bright=round(sum(r.get("background") in ("bright", "colourful") for r in rows) / n, 3),
               dark=round(sum(r.get("background") == "dark" for r in rows) / n, 3))
    return got


def findings(m: dict, study: dict, titles: list[dict], theirs: dict | None, ours: dict | None) -> list[dict]:
    """What is holding this channel back, biggest first, from numbers only."""
    rows = []
    own = study.get("own") or {}
    shown = reach.load(m["channel_id"]) or {}
    clicks = [v["ctr"] for v in (shown.get("videos") or {}).values()
              if v.get("ctr") is not None and (v.get("impressions") or 0) >= 100]
    impressions = [v["impressions"] for v in (shown.get("videos") or {}).values() if v.get("impressions")]
    if impressions:
        ctr = statistics.median(clicks) if clicks else None
        rows.append({
            "key": "reach", "title": "How often YouTube shows your videos",
            "finding": (f"A video is shown about {round(statistics.median(impressions)):,} times"
                        + (f" and clicked {ctr:.1f}% of the time" if ctr is not None else "")
                        + f". Your usual video gets {round(m.get('usual') or 0):,} views; a usual video on these "
                          f"{study['channels']} channels gets {round(study['usual']):,}."),
            "action": ("If clicks are near the middle of the range but impressions stay low, YouTube is not widening "
                       "the test. What it reads before widening is the click and the first minutes."),
            "basis": f"Your Studio export, {len(impressions)} videos"})
    early = own.get("early")
    if early:
        low = [p for p in early["points"] if p["at"] <= 0.1]
        high = [p for p in early["points"] if p["at"] >= 0.25]
        first = statistics.median(p["against"] for p in low)
        later = statistics.median(p["against"] for p in high)
        if first < 0.5:
            rows.append({
                "key": "opening", "title": "Viewers leave in the opening",
                "finding": (f"Against videos of similar length, YouTube rates your first 10% at {first:.2f}, where "
                            f"0.50 is the middle, and the rest at {later:.2f}."),
                "action": ("The ones who stay are not the problem; the start is. Open on what the title promised, in "
                           "plain words, and save the loudest moment for later."),
                "basis": f"YouTube Analytics relative retention, {early['videos']} videos"})
    gaps = [t for t in titles if t.get("ours") is not None and t["up"] > t["down"] and t["share"] - t["ours"] >= 0.1]
    extra = [t for t in titles if t.get("ours") is not None and t["down"] > t["up"] and t["ours"] - t["share"] >= 0.1]
    if gaps or extra:
        said = "; ".join([f"{t['label'].lower()}: you {round(t['ours'] * 100)}%, them {round(t['share'] * 100)}%"
                          for t in (gaps + extra)[:4]])
        rows.append({
            "key": "titles", "title": "Your titles read unlike the ones that work here",
            "finding": said[:1].upper() + said[1:] + ".",
            "action": "Try the habits that do better inside these channels on your next few titles, and retitle a "
                      "couple of low-view videos to compare.",
            "basis": f"{study['videos']} competitor videos, each against its own channel's usual"})
    if theirs and ours:
        bits = []
        for key, label in STYLE_ROWS:
            if abs(theirs[key] - ours[key]) >= 0.15:
                bits.append(f"{label.lower()} on {round(ours[key] * 100)}% of yours "
                            f"against {round(theirs[key] * 100)}%")
        if theirs["words"] - ours["words"] >= 1.5 or ours["words"] - theirs["words"] >= 1.5:
            bits.append(f"{ours['words']} words of text on average against {theirs['words']}")
        if theirs["bright"] - ours["bright"] >= 0.15:
            bits.append(f"bright backgrounds on {round(ours['bright'] * 100)}% "
                        f"against {round(theirs['bright'] * 100)}%")
        if bits:
            rows.append({
                "key": "thumbs", "title": "Your thumbnails look unlike their best",
                "finding": "; ".join(bits)[:1].upper() + "; ".join(bits)[1:] + ".",
                "action": "Their best videos share these traits more than their worst do. Test one change at a time.",
                "basis": f"The vision model's labels, {ours['n']} of yours and {theirs['n']} of their best"})
    sources = own.get("longSources") or []
    home = next((s for s in sources if s["source"] == "SUBSCRIBER"), None)
    suggested = next((s for s in sources if s["source"] == "RELATED_VIDEO"), None)
    if home and home["share"] >= 0.3:
        rows.append({
            "key": "home", "title": "Home-page viewers leave within minutes",
            "finding": (f"{round(home['share'] * 100)}% of your long-video views come from the home page and "
                        f"subscriptions, at {home['perView']} minutes a view"
                        + (f"; suggested videos bring {round(suggested['share'] * 100)}%, at "
                           f"{suggested['perView']} minutes." if suggested else ".")),
            "action": "Most of those viewers are not subscribed: they are strangers deciding in the first minute.",
            "basis": f"YouTube Analytics, long videos, last {WINDOW_DAYS} days"})
    hits = [e for e in study.get("escapes") or [] if e["hit"]]
    if hits:
        fast = sum(e["hit"] <= 10 for e in hits)
        rows.append({
            "key": "escape", "title": "How soon small channels broke out",
            "finding": (f"{fast} of {len(study['escapes'])} small competitors reached {ESCAPE_VIEWS:,} views within "
                        f"their first ten videos. They upload {study['uploads30']:g} videos a month on the median."),
            "action": ("If you have made more than that without a breakout, change what goes out before making "
                       "more of it."),
            "basis": "Channels that never broke out are on no map, so this flatters the odds"})
    sets = own.get("settings")
    if len(m.get("videos") or []) < OURS_MIN:
        rows.append({
            "key": "few", "title": "Too few of your own videos to compare yet",
            "finding": (f"{m['title']} has {len(m.get('videos') or [])} long "
                        f"video{'' if len(m.get('videos') or []) == 1 else 's'}; comparisons with your titles and "
                        f"thumbnails start at {OURS_MIN}."),
            "action": "Until then, use the title habits and thumbnail styles of their best videos as the guide.",
            "basis": "Your public uploads"})
    if sets:
        held = sets["kids"] or sets["blocked"]
        rows.append({
            "key": "settings",
            "title": "A setting is holding videos back" if held else "No setting is holding you back",
            "finding": (f"Of {sets['read']} videos read, {sets['kids']} are marked made for kids and {sets['blocked']} "
                        f"are blocked in some countries."),
            "action": ("Made-for-kids videos lose comments, end screens and most recommendations; check those first."
                       if held else "Nothing here is a switch to flip."),
            "basis": "YouTube Data API"})
    return rows


# ---------------------------------------------------------------- reading

def _stored(cid: str) -> list[dict]:
    with database.connect() as con:
        return [dict(r) for r in con.execute(
            "SELECT id, title, views, seconds, published_at, thumbnail FROM videos WHERE channel_id = ? "
            "AND seconds >= ? ORDER BY published_at DESC LIMIT ?", (cid, LONG_MIN_SEC, READ_VIDEOS))]


def _read(ids: list[str], report: Reporter) -> dict[str, dict]:
    info = data_api.channels(ids)
    out = {}
    for i, cid in enumerate(c for c in ids if c in info):
        videos = _stored(cid)
        if len([v for v in videos if _age(v) >= SETTLED_DAYS]) < MIN_VIDEOS:
            report(f"reading {info[cid]['title']} ({i + 1} of {len(ids)})")
            try:
                fresh = data_api.uploads(info[cid]["uploads"], READ_VIDEOS)
                database.remember(cid, info[cid], fresh, metrics.measure(fresh))
                videos = [_slim(v) for v in fresh]
            except data_api.YouTubeError as e:
                log.warning("could not read %s for the study: %s", cid, str(e)[:150])
        out[cid] = {"title": info[cid]["title"], "subs": info[cid]["subscribers"], "uploads": info[cid]["uploads"],
                    "videos": videos}
    return out


def _thumb(video: dict) -> bytes | None:
    d = _dir() / "thumbs"
    d.mkdir(exist_ok=True)
    p = d / f"{video['id']}.jpg"
    if p.exists():
        return p.read_bytes()
    url = video.get("thumbnail") or f"https://i.ytimg.com/vi/{video['id']}/mqdefault.jpg"
    if not url.startswith("https://"):
        return None
    try:
        r = requests.get(url, timeout=15)
    except requests.RequestException:
        return None
    if r.ok and r.headers.get("content-type", "").startswith("image/"):
        p.write_bytes(r.content)
        return r.content
    return None


def label_thumbs(videos: list[dict], report: Reporter) -> dict[str, dict]:
    """Labels for these videos' thumbnails; ones labelled before are reused."""
    path = _dir() / "labels.json"
    labels = read_json(path, {}) or {}
    todo = [v for v in videos if v["id"] not in labels]
    for start in range(0, len(todo), LABEL_BATCH):
        report(f"looking at thumbnails ({start} of {len(todo)})")
        chunk = [(v, b) for v in todo[start:start + LABEL_BATCH] if (b := _thumb(v))]
        if not chunk:
            continue
        parts: list = []
        for i, (_, b) in enumerate(chunk):
            parts += [f"Thumbnail {i + 1}:", ai.image_part(b)]
        try:
            got = ai.generate([*parts, LABEL_ASK], LABEL_SCHEMA, light=True)
        except Exception as e:  # noqa: BLE001 - a batch without labels is skipped
            log.warning("thumbnail labels failed: %s", str(e)[:200])
            continue
        for it in got.get("items") or []:
            if 1 <= int(it.get("n") or 0) <= len(chunk):
                labels[chunk[int(it["n"]) - 1][0]["id"]] = it
        write_json(path, labels)
    return labels


def _own(cid: str, videos: list[dict], report: Reporter) -> dict:
    """Openings against similar videos, long-video sources and settings, for a connected channel."""
    out: dict = {"early": None, "longSources": [], "settings": None}
    report("reading your analytics")
    try:
        busy = analytics.report(cid, WINDOW_DAYS, "reading your videos", dimensions="video",
                                metrics="views", sort="-views", maxResults=8)
        curves = []
        for vid, _ in busy:
            rows = analytics.report(cid, WINDOW_DAYS, "reading retention", dimensions="elapsedVideoTimeRatio",
                                    metrics="audienceWatchRatio,relativeRetentionPerformance",
                                    filters=f"video=={vid}")
            if rows:
                curves.append(rows)
        if curves:
            def at(row, x):
                return min(row, key=lambda p: abs(p[0] - x))
            out["early"] = {"videos": len(curves), "points": [
                {"at": x, "watching": round(statistics.median(at(r, x)[1] for r in curves), 2),
                 "against": round(statistics.median(at(r, x)[2] for r in curves), 2)}
                for x in (0.02, 0.05, 0.1, 0.25, 0.5)]}
    except Exception as e:  # noqa: BLE001 - each part is optional
        log.warning("retention curves failed: %s", str(e)[:200])
    try:
        rows = analytics.report(cid, WINDOW_DAYS, "reading long-video traffic", dimensions="insightTrafficSourceType",
                                metrics="views,estimatedMinutesWatched", filters="creatorContentType==videoOnDemand",
                                sort="-views")
        total = sum(r[1] for r in rows) or 1
        out["longSources"] = [{"source": r[0], "views": int(r[1]), "share": round(r[1] / total, 3),
                               "perView": round(r[2] / max(r[1], 1), 1)} for r in rows]
    except Exception as e:  # noqa: BLE001
        log.warning("long-video sources failed: %s", str(e)[:200])
    try:
        out["settings"] = data_api.video_settings([v["id"] for v in videos[:30]], cid)
    except Exception as e:  # noqa: BLE001
        log.warning("video settings failed: %s", str(e)[:200])
    return out


def run(map_id: str, report: Reporter = silent) -> dict:
    """Study a map's competitors again. Replaces the saved study when it works."""
    m = storage.require(map_id)
    ids = pool(m)
    if not ids:
        raise ValueError("no near channel on this map has enough subscribers and views to learn from yet")
    channels = _read(ids, report)
    rows = scored(channels)
    if not rows:
        raise ValueError("the competitors read have too few settled videos to compare yet")
    history = []
    small = sorted(channels, key=lambda c: channels[c]["subs"] or 0)[:ESCAPE_CHANNELS]
    for i, cid in enumerate(small):
        report(f"how {channels[cid]['title']} first broke out ({i + 1} of {len(small)})")
        try:
            vs = data_api.uploads(channels[cid]["uploads"], HISTORY_VIDEOS)
            history.append((channels[cid]["title"], channels[cid]["subs"],
                            sorted(vs, key=lambda v: v["published_at"])))
        except data_api.YouTubeError as e:
            log.warning("history of %s failed: %s", cid, str(e)[:150])
    groups: dict[str, list[dict]] = {"winners": [], "losers": [], "ours": []}
    for cid in channels:
        vs = sorted((r for r in rows if r["cid"] == cid), key=lambda r: -r["lift"])
        if len(vs) >= MIN_VIDEOS:
            groups["winners"] += vs[:LABELLED_EACH_END]
            groups["losers"] += vs[-LABELLED_EACH_END:]
    groups["ours"] = [_slim(v) for v in (m.get("videos") or [])[:OURS_LABELLED]]
    if ai.available():
        label_thumbs([v for g in groups.values() for v in g], report)
    best, seen, gallery = sorted(rows, key=lambda r: -r["lift"]), set(), []
    for r in best:
        if r["cid"] not in seen and _age(r) <= 365:
            seen.add(r["cid"])
            gallery.append({**_slim(r), "outlier": round(r["lift"], 1), "channel": channels[r["cid"]]["title"],
                            "channel_id": r["cid"]})
        if len(gallery) == GALLERY:
            break
    study = {
        "at": utc_now(), "channels": len({r["cid"] for r in rows}), "videos": len(rows),
        "usual": statistics.median(statistics.median(v["views"] for v in c["videos"])
                                   for c in channels.values() if c["videos"]),
        "uploads30": statistics.median(sum(_age(v) <= 30 for v in c["videos"]) for c in channels.values()),
        "titles": title_table(rows), "rising": rising(rows), "escapes": escapes(history), "gallery": gallery,
        "groups": {k: [v["id"] for v in g] for k, g in groups.items()},
        "own": _own(map_id, m.get("videos") or [], report) if auth.is_own(map_id) else None}
    write_json(_path(map_id), study)
    return m


def saved(map_id: str) -> dict | None:
    return read_json(_path(map_id))


def due() -> list[str]:
    """Maps whose study is older than STALE_DAYS."""
    out = []
    for p in _dir().glob("*.json"):
        if p.name == "labels.json":
            continue
        got = read_json(p) or {}
        if hours_since(got.get("at")) >= STALE_DAYS * 24 and storage.path(p.stem).exists():
            out.append(p.stem)
    return out


def view(m: dict) -> dict | None:
    """The saved study as the page draws it, or None before the first run."""
    study = saved(m["channel_id"])
    if not study:
        return None
    labels = read_json(_dir() / "labels.json", {}) or {}
    recent = [v["title"] for v in m.get("videos") or [] if _age(v) <= RECENT_OURS_DAYS and v.get("title")]
    if len(recent) < OURS_MIN:
        recent = [v["title"] for v in (m.get("videos") or [])[:OURS_LABELLED] if v.get("title")]
    # Too few of the channel's own titles say nothing about its habits.
    titles = [{**t, "ours": share_of(recent, t["key"]) if len(recent) >= OURS_MIN else None}
              for t in study["titles"]]
    groups = study.get("groups") or {}

    def group(key: str) -> dict | None:
        return style_of([labels[i] for i in groups.get(key, []) if i in labels])

    winners, losers, ours = group("winners"), group("losers"), group("ours")
    if ours and ours["n"] < OURS_MIN:
        ours = None
    return {"at": study["at"], "stale": hours_since(study["at"]) >= STALE_DAYS * 24,
            "channels": study["channels"], "videos": study["videos"], "usual": study["usual"],
            "uploads30": study["uploads30"], "titles": titles, "recentTitles": len(recent),
            "rising": study.get("rising") or [], "styles": {"winners": winners, "losers": losers, "ours": ours},
            "styleRows": [{"key": k, "label": label} for k, label in STYLE_ROWS],
            "escapes": [{**e, "days": e.get("days") or None} for e in study.get("escapes") or []],
            "theirBest": study.get("gallery") or [],
            "yourLatest": [_slim(v) for v in (m.get("videos") or [])[:GALLERY]],
            "findings": findings(m, study, titles, winners, ours)}
