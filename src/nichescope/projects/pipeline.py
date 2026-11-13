"""The steps that turn a script into a finished video."""
from __future__ import annotations

import logging
import math
import re
import subprocess
import wave
from pathlib import Path

from .. import ai
from ..config import settings
from ..research import briefing, metrics, storage
from ..util import Reporter, silent, utc_now
from ..youtube import captions
from . import store

log = logging.getLogger(__name__)

WORDS_PER_SECOND = 2.5
SPEECH_CHUNK_CHARS = 2500
CLIP_LENGTHS = (4, 6, 8)
SCENE_MIN_SEC = 3.0
WIDTH, HEIGHT, FPS = 1920, 1080, 30
EXAMPLE_TRANSCRIPTS = 2
EXAMPLE_WORDS = 1500

SCRIPT_SCHEMA = {"type": "object", "properties": {"script": {"type": "string"}}, "required": ["script"]}
SPEECH_SCHEMA = {"type": "object", "properties": {"speech": {"type": "boolean"}}, "required": ["speech"]}


# ---------------------------------------------------------------- script

def draft_script(project_id: str, minutes: int = 8, report: Reporter = silent) -> dict:
    """Write a narration script from the topic the project was created from."""
    p = store.load(project_id)
    if p["voiceover"]:
        raise ValueError("the voiceover is made, so the script can no longer change")
    source = p.get("source") or {}
    topic = source.get("topic") or p["title"]
    m = storage.load(source["map_id"]) if source.get("map_id") else None
    examples = []
    if m:
        by_id = {v["id"]: v for v in metrics.breakouts(m)}
        for vid in source.get("evidence", [])[:EXAMPLE_TRANSCRIPTS]:
            report("reading an example transcript")
            try:
                words = captions.transcript(vid)["text"].split()[:EXAMPLE_WORDS]
                examples.append(f"Example: {by_id.get(vid, {}).get('title', vid)}\n{' '.join(words)}")
            except (LookupError, ValueError) as e:
                log.info("no transcript for %s: %s", vid, e)
    report("writing the script")
    context = briefing.brief(m) if m else ""
    words = int(minutes * 60 * WORDS_PER_SECOND)
    prompt = (f"{context}\n\n" + ("\n\n".join(examples) + "\n\n" if examples else "")
              + f"Write the narration for a YouTube video.\nTopic: {topic}\n"
              + (f"Brief: {source['detail']}\n" if source.get("detail") else "")
              + (f"Working title: {source['title']}\n" if source.get("title") else "")
              + f"\nAbout {words} words. It is read aloud word for word, so write only the spoken words: no "
              "headings, stage directions, timestamps, sound cues or markdown. Open with a hook in the first two "
              "sentences, keep a clear structure, and end without asking viewers to like or subscribe. "
              + ("Match the pacing and tone of the example transcripts without copying their sentences." if examples
                 else ""))
    got = ai.generate([prompt], SCRIPT_SCHEMA)
    script = re.sub(r"\n{3,}", "\n\n", (got.get("script") or "").strip())
    if not script:
        raise RuntimeError("the model returned an empty script; try again")
    return store.update(project_id, script=script)


def create_from_topic(map_id: str, batch_id: str, topic: str) -> dict:
    m = storage.require(map_id)
    b = next((b for b in m.get("topics", []) if b["id"] == batch_id), None)
    t = next((t for t in (b or {}).get("topics", []) if t["topic"] == topic), None)
    if t is None:
        raise ValueError("that topic no longer exists")
    title = (t.get("titles") or [topic])[0]
    return store.create(title, source={"map_id": map_id, "batch": batch_id, "topic": topic, "title": title,
                                       "detail": t.get("detail", ""), "evidence": t.get("evidence", [])})


# ---------------------------------------------------------------- estimate

def estimate(p: dict) -> dict:
    """Expected voiceover length, scene count, clip seconds and video generation cost."""
    if p["voiceover"]:
        seconds = p["voiceover"]["seconds"]
    else:
        seconds = len(p["script"].split()) / WORDS_PER_SECOND
    scenes = len(p["scenes"]) or (math.ceil(seconds / 6) if seconds else 0)
    clip_seconds = sum(s["clip_seconds"] for s in p["scenes"]) if p["scenes"] else scenes * CLIP_LENGTHS[-1]
    return {"voice_seconds": round(seconds), "scenes": scenes, "clip_seconds": clip_seconds,
            "video_cost": round(clip_seconds * settings().video_price_per_second, 2)}


# ---------------------------------------------------------------- voiceover

def _chunks(script: str) -> list[str]:
    """Paragraph-aligned pieces short enough for one speech request."""
    out, current = [], ""
    for para in [x.strip() for x in re.split(r"\n\s*\n", script) if x.strip()]:
        pieces = [para] if len(para) <= SPEECH_CHUNK_CHARS else re.split(r"(?<=[.!?])\s+", para)
        for piece in pieces:
            if current and len(current) + len(piece) + 2 > SPEECH_CHUNK_CHARS:
                out.append(current)
                current = ""
            current = f"{current}\n\n{piece}".strip() if current else piece
    if current:
        out.append(current)
    return out


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def make_voiceover(project_id: str, report: Reporter = silent) -> dict:
    """Read the script aloud. Sentence timings are kept for splitting into scenes."""
    p = store.load(project_id)
    if p["voiceover"]:
        raise ValueError("the voiceover is already made")
    if len(p["script"].split()) < 10:
        raise ValueError("write a script first")
    chunks = _chunks(p["script"])
    audio = bytearray()
    timeline: list[dict] = []
    for i, chunk in enumerate(chunks):
        report(f"recording part {i + 1} of {len(chunks)}")
        pcm = ai.speech(chunk, p["voice"])
        start = len(audio) / 2 / ai.SPEECH_RATE
        length = len(pcm) / 2 / ai.SPEECH_RATE
        lines = sentences(chunk)
        total = sum(len(s) for s in lines) or 1
        at = start
        for s in lines:
            span = length * len(s) / total
            timeline.append({"text": s, "start": round(at, 2), "end": round(at + span, 2)})
            at += span
        audio += pcm
    path = store.folder(project_id) / "voiceover.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(ai.SPEECH_RATE)
        w.writeframes(bytes(audio))
    with store.lock(project_id):
        p = store.load(project_id)
        p["voiceover"] = {"file": path.name, "seconds": round(len(audio) / 2 / ai.SPEECH_RATE, 2),
                          "sentences": timeline, "at": utc_now()}
        return store.save(p)


# ---------------------------------------------------------------- scenes

def _shots(timeline: list[dict]) -> list[dict]:
    """Group sentences into shots no longer than the longest clip, where possible."""
    longest = CLIP_LENGTHS[-1]
    shots: list[dict] = []
    for s in timeline:
        if shots and s["end"] - shots[-1]["start"] <= longest:
            shots[-1]["end"] = s["end"]
            shots[-1]["text"] += " " + s["text"]
        else:
            shots.append(dict(s))
    merged: list[dict] = []
    for shot in shots:
        if merged and shot["end"] - shot["start"] < SCENE_MIN_SEC:
            merged[-1]["end"] = shot["end"]
            merged[-1]["text"] += " " + shot["text"]
        else:
            merged.append(shot)
    return merged


def make_scenes(project_id: str, report: Reporter = silent) -> dict:
    """Split the voiceover into shots and write a visual description and video prompt for each."""
    p = store.load(project_id)
    if not p["voiceover"]:
        raise ValueError("make the voiceover first")
    if p["scenes"]:
        raise ValueError("the scenes are already made")
    shots = _shots(p["voiceover"]["sentences"])
    schema = {"type": "object", "properties": {"scenes": {"type": "array", "minItems": len(shots),
              "maxItems": len(shots), "items": {"type": "object", "properties": {
                  "visual": {"type": "string"}, "prompt": {"type": "string"}}, "required": ["visual", "prompt"]}}},
              "required": ["scenes"]}
    listed = "\n".join(f"{i + 1}. ({s['end'] - s['start']:.1f}s) {s['text']}" for i, s in enumerate(shots))
    report(f"describing {len(shots)} scenes")
    got = ai.generate([
        f"A video titled {p['title']!r} is narrated by the voiceover below, split into {len(shots)} shots.\n\n"
        f"{listed}\n\nFor each shot, in order, write:\n"
        "- visual: one or two sentences on what the viewer sees while that line is spoken.\n"
        "- prompt: a self-contained prompt for a text-to-video model that produces that shot: subject, action, "
        "setting, camera movement, lighting and style. Keep characters and style consistent between shots. "
        "No on-screen text, no logos, and nobody speaking to camera."
        + (f"\n\nVisual description guidelines: {p['visual_instructions']}" if p["visual_instructions"] else "")
        + (f"\n\nVideo prompt guidelines: {p['prompt_instructions']}" if p["prompt_instructions"] else "")],
        schema)
    rows = got.get("scenes") or []
    if len(rows) != len(shots):
        raise RuntimeError("the model returned the wrong number of scenes; try again")
    scenes = []
    for shot, row in zip(shots, rows, strict=True):
        length = shot["end"] - shot["start"]
        scenes.append({"text": shot["text"], "start": shot["start"], "end": shot["end"],
                       "clip_seconds": next((c for c in CLIP_LENGTHS if c >= length), CLIP_LENGTHS[-1]),
                       "visual": row["visual"].strip(), "prompt": row["prompt"].strip(), "clip": None})
    with store.lock(project_id):
        p = store.load(project_id)
        p["scenes"] = scenes
        return store.save(p)


# ---------------------------------------------------------------- clips

def ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([ffmpeg(), "-hide_banner", "-y", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def has_audio(path: Path) -> bool:
    probe = _run(["-i", str(path)])
    return "Audio:" in probe.stderr


def detect_speech(path: Path) -> bool:
    """Whether a clip's sound contains spoken words. False when it has no sound."""
    if not has_audio(path):
        return False
    wav = path.with_suffix(".probe.wav")
    try:
        if _run(["-i", str(path), "-vn", "-ac", "1", "-ar", "16000", str(wav)]).returncode != 0:
            return False
        got = ai.generate([ai.file_part(wav.read_bytes(), "audio/wav"),
                           "Listen to this audio. Set speech to true only if a person says intelligible words. "
                           "Tones, beeps, music, singing without clear words, ambience, nature sounds, crowd "
                           "noise and silence are all false."],
                          SPEECH_SCHEMA)
        return bool(got.get("speech"))
    finally:
        wav.unlink(missing_ok=True)


def make_clip(project_id: str, index: int, report: Reporter = silent) -> dict:
    p = store.load(project_id)
    if not 0 <= index < len(p["scenes"]):
        raise ValueError("no such scene")
    if (p.get("render") or {}).get("status") == "rendering":
        raise ValueError("the video is rendering; wait for it to finish")
    scene = p["scenes"][index]
    report(f"generating clip {index + 1} of {len(p['scenes'])}")
    try:
        data = ai.video(scene["prompt"], scene["clip_seconds"])
        path = store.folder(project_id) / f"clip-{index + 1:03d}.mp4"
        path.write_bytes(data)
        clip = {"file": path.name, "speech": detect_speech(path), "at": utc_now(), "error": None}
    except ai.NotConfigured:
        raise
    except ai.AIError as e:
        clip = {"file": None, "speech": False, "at": utc_now(), "error": str(e)[:300]}
    with store.lock(project_id):
        p = store.load(project_id)
        p["scenes"][index]["clip"] = clip
        return store.save(p)


def make_clips(project_id: str, report: Reporter = silent) -> dict:
    """Generate every clip that is missing or failed."""
    p = store.load(project_id)
    if not p["scenes"]:
        raise ValueError("make the scenes first")
    todo = [i for i, s in enumerate(p["scenes"]) if not (s.get("clip") or {}).get("file")]
    for n, i in enumerate(todo):
        report(f"generating clip {n + 1} of {len(todo)}")
        p = make_clip(project_id, i)
    return store.load(project_id)


# ---------------------------------------------------------------- render

def render(project_id: str, report: Reporter = silent) -> dict:
    """Put the clips and voiceover together into one MP4."""
    p = store.load(project_id)
    missing = [i + 1 for i, s in enumerate(p["scenes"]) if not (s.get("clip") or {}).get("file")]
    if not p["scenes"] or missing:
        raise ValueError("every scene needs a clip before the video can be rendered")
    with store.lock(project_id):
        p = store.load(project_id)
        p["render"] = {"status": "rendering", "file": None, "at": utc_now(), "error": None}
        store.save(p)
    folder = store.folder(project_id)
    total = p["voiceover"]["seconds"]
    scenes = p["scenes"]
    inputs: list[str] = []
    graph: list[str] = []
    level = p["clip_sound"] / 100
    for i, s in enumerate(scenes):
        end = scenes[i + 1]["start"] if i + 1 < len(scenes) else total
        length = max(0.5, end - s["start"])
        clip = folder / s["clip"]["file"]
        inputs += ["-i", str(clip)]
        graph.append(f"[{i}:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
                     f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,fps={FPS},setsar=1,"
                     f"tpad=stop_mode=clone:stop_duration={length:.2f},trim=duration={length:.2f},"
                     f"setpts=PTS-STARTPTS[v{i}]")
        if level > 0 and not s["clip"].get("speech") and has_audio(clip):
            graph.append(f"[{i}:a]aresample=48000,volume={level:.2f},apad,atrim=duration={length:.2f},"
                         f"asetpts=PTS-STARTPTS[a{i}]")
        else:
            graph.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={length:.2f}[a{i}]")
    n = len(scenes)
    graph.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vid][bed]")
    graph.append(f"[{n}:a]aresample=48000[voice]")
    graph.append("[bed][voice]amix=inputs=2:duration=longest:normalize=0[mix]")
    out = folder / "video.mp4"
    script = folder / "render.filter"
    script.write_text(";\n".join(graph), encoding="utf-8")
    report(f"rendering {n} scenes")
    result = _run([*inputs, "-i", str(folder / p["voiceover"]["file"]), "-/filter_complex", str(script),
                   "-map", "[vid]", "-map", "[mix]", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                   "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)])
    script.unlink(missing_ok=True)
    with store.lock(project_id):
        p = store.load(project_id)
        if result.returncode != 0:
            p["render"] = {"status": "failed", "file": None, "at": utc_now(), "error": result.stderr[-600:]}
            store.save(p)
            raise RuntimeError("the video could not be rendered; see the project for details")
        p["render"] = {"status": "done", "file": out.name, "at": utc_now(), "error": None}
        return store.save(p)
