"""Video projects: one folder per project under `<data>/projects/<id>`.

A project moves through fixed steps, and each step locks what it was made from:

    script -> voiceover (locks script and voice)
           -> scenes    (locks scene instructions)
           -> clips     (one per scene; prompts stay editable, clips can be regenerated)
           -> render    (the clips and voiceover put together)
"""
from __future__ import annotations

import shutil
import threading
import uuid
from pathlib import Path

from ..config import settings
from ..util import read_json, utc_now, write_json

SCRIPT_MAX = 60_000
INSTRUCTIONS_MAX = 2000
DEFAULT_VOICE = "Kore"
VOICES = {
    "Zephyr": "Bright", "Puck": "Upbeat", "Charon": "Informative", "Kore": "Firm", "Fenrir": "Excitable",
    "Leda": "Youthful", "Orus": "Firm", "Aoede": "Breezy", "Callirrhoe": "Easy-going", "Autonoe": "Bright",
    "Enceladus": "Breathy", "Iapetus": "Clear", "Umbriel": "Easy-going", "Algieba": "Smooth",
    "Despina": "Smooth", "Erinome": "Clear", "Algenib": "Gravelly", "Rasalgethi": "Informative",
    "Laomedeia": "Upbeat", "Achernar": "Soft", "Alnilam": "Firm", "Schedar": "Even", "Gacrux": "Mature",
    "Pulcherrima": "Forward", "Achird": "Friendly", "Zubenelgenubi": "Casual", "Vindemiatrix": "Gentle",
    "Sadachbia": "Lively", "Sadaltager": "Knowledgeable", "Sulafat": "Warm",
}

_locks: dict[str, threading.RLock] = {}
_guard = threading.Lock()


class ProjectNotFound(LookupError):
    pass


def lock(project_id: str) -> threading.RLock:
    with _guard:
        return _locks.setdefault(project_id, threading.RLock())


def folder(project_id: str) -> Path:
    if not project_id.isalnum():
        raise ProjectNotFound("no such project")
    return settings().projects_dir / project_id


def file(project_id: str, name: str) -> Path:
    p = folder(project_id) / Path(name).name
    if not p.is_file():
        raise FileNotFoundError("that file has not been made yet")
    return p


def load(project_id: str) -> dict:
    p = read_json(folder(project_id) / "project.json")
    if not p:
        raise ProjectNotFound("no such project")
    return p


def save(p: dict) -> dict:
    p["updated_at"] = utc_now()
    write_json(folder(p["id"]) / "project.json", p)
    return p


def all_projects() -> list[dict]:
    rows = [read_json(d / "project.json") for d in settings().projects_dir.iterdir() if d.is_dir()]
    return sorted((r for r in rows if r), key=lambda r: r.get("created_at", ""), reverse=True)


def create(title: str, script: str = "", source: dict | None = None) -> dict:
    title = (title or "").strip()[:200] or "Untitled video"
    pid = uuid.uuid4().hex[:12]
    folder(pid).mkdir(parents=True)
    return save({"id": pid, "title": title, "created_at": utc_now(), "source": source or {},
                 "script": script[:SCRIPT_MAX], "voice": DEFAULT_VOICE, "visual_instructions": "",
                 "prompt_instructions": "", "clip_sound": 30, "voiceover": None, "scenes": [], "render": None})


def update(project_id: str, **changes) -> dict:
    """Edit fields that are not locked by a later step."""
    with lock(project_id):
        p = load(project_id)
        if "title" in changes and changes["title"] is not None:
            p["title"] = str(changes["title"]).strip()[:200] or p["title"]
        for key in ("script", "voice"):
            if changes.get(key) is None:
                continue
            if p["voiceover"]:
                raise ValueError(f"the voiceover is made, so the {key} can no longer change")
            if key == "voice" and changes[key] not in VOICES:
                raise ValueError("unknown voice")
            p[key] = str(changes[key])[:SCRIPT_MAX]
        for key in ("visual_instructions", "prompt_instructions"):
            if changes.get(key) is None:
                continue
            if p["scenes"]:
                raise ValueError("the scenes are made, so their instructions can no longer change")
            p[key] = str(changes[key]).strip()[:INSTRUCTIONS_MAX]
        if changes.get("clip_sound") is not None:
            value = int(changes["clip_sound"])
            if not 0 <= value <= 100:
                raise ValueError("clip sound is from 0 to 100")
            p["clip_sound"] = value
        return save(p)


def update_scene(project_id: str, index: int, visual: str | None = None, prompt: str | None = None) -> dict:
    with lock(project_id):
        p = load(project_id)
        if not 0 <= index < len(p["scenes"]):
            raise ValueError("no such scene")
        scene = p["scenes"][index]
        if visual is not None:
            scene["visual"] = str(visual).strip()[:2000]
        if prompt is not None:
            scene["prompt"] = str(prompt).strip()[:4000]
        return save(p)


def delete(project_id: str) -> None:
    load(project_id)
    shutil.rmtree(folder(project_id))
