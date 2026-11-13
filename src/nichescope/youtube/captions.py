"""Video transcripts from YouTube captions: the channel's own, else the automatic track.

Transcripts are cached on disk after the first read. No API quota is used.
"""
from __future__ import annotations

import logging
import os
import re

from ..config import settings
from ..util import read_json, write_json
from .web import video_id

log = logging.getLogger(__name__)

MAX_BYTES = 6_000_000


class _QuietLogger:
    def debug(self, msg: str) -> None:
        pass

    info = warning = debug

    def error(self, msg: str) -> None:
        log.debug("yt-dlp: %s", msg[:150])


def _ydl():
    import yt_dlp

    opts = {"quiet": True, "no_warnings": True, "logger": _QuietLogger(),
            "skip_download": True, "socket_timeout": 20}
    cookies = os.environ.get("YOUTUBE_COOKIES_FILE", "")
    if cookies and os.path.isfile(cookies):
        opts["cookiefile"] = cookies
    return yt_dlp.YoutubeDL(opts)


def _seconds(stamp: str) -> float:
    h, m, rest = stamp.replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(rest)


def parse_srt(raw: str) -> list[dict]:
    """[{start, text}] from an SRT body, with the rolling repeats of auto-captions removed."""
    segments: list[dict] = []
    start = None
    lines: list[str] = []

    def flush() -> None:
        if start is not None and lines:
            text = re.sub(r"<[^>]+>", "", " ".join(lines)).strip()
            if text:
                segments.append({"start": round(start, 2), "text": text})

    for line in raw.splitlines():
        s = line.strip()
        if "-->" in s:
            flush()
            start, lines = _seconds(s.split("-->")[0].strip()), []
        elif s and not s.isdigit():
            lines.append(s)
    flush()
    out: list[dict] = []
    for seg in segments:
        if out and seg["text"] == out[-1]["text"]:
            continue
        if out and seg["text"].startswith(out[-1]["text"]):
            seg = {**seg, "text": seg["text"][len(out[-1]["text"]):].strip()}
            if not seg["text"]:
                continue
        out.append(seg)
    return out


def _dedupe_words(text: str) -> str:
    words, out = text.split(), []
    i = 0
    while i < len(words):
        for n in range(12, 2, -1):
            if words[i:i + n] and words[i:i + n] == out[-n:]:
                i += n
                break
        else:
            out.append(words[i])
            i += 1
    return " ".join(out)


def transcript(video: str, language: str = "en") -> dict:
    """-> {video, title, language, words, text, segments: [{start, text}]}"""
    vid = video_id(video)
    language = re.sub(r"[^A-Za-z-]", "", str(language or "en"))[:12] or "en"
    path = settings().transcripts_dir / f"{vid}.{language}.json"
    cached = read_json(path)
    if cached:
        return cached
    with _ydl() as y:
        info = y.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
        own, auto = info.get("subtitles") or {}, info.get("automatic_captions") or {}
        track = (own.get(language) or auto.get(f"{language}-orig") or auto.get(language)
                 or next((t for k, t in {**auto, **own}.items() if k.split("-")[0] == language), []))
        url = next((f["url"] for f in track if f.get("ext") == "srt"), None)
        if not url:
            raise LookupError(f"this video has no {language} captions")
        r = y.urlopen(url)
        try:
            raw = r.read(MAX_BYTES).decode("utf-8", "replace")
        finally:
            r.close()
    segments = parse_srt(raw)
    text = _dedupe_words(" ".join(s["text"] for s in segments))
    out = {"video": vid, "title": info.get("title", ""), "language": language,
           "words": len(text.split()), "text": text, "segments": segments}
    write_json(path, out, indent=None)
    return out
