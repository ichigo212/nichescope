"""Video project endpoints: script, voiceover, scenes, clips and the rendered video."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..projects import pipeline, store
from .jobs import jobs

router = APIRouter(prefix="/api/projects", tags=["projects"])

MEDIA_TYPES = {".wav": "audio/wav", ".mp4": "video/mp4"}


class NewProject(BaseModel):
    title: str = ""
    script: str = ""
    map_id: str | None = None
    batch: str | None = None
    topic: str | None = None


class ProjectUpdate(BaseModel):
    title: str | None = None
    script: str | None = Field(None, max_length=store.SCRIPT_MAX)
    voice: str | None = None
    visual_instructions: str | None = Field(None, max_length=store.INSTRUCTIONS_MAX)
    prompt_instructions: str | None = Field(None, max_length=store.INSTRUCTIONS_MAX)
    clip_sound: int | None = Field(None, ge=0, le=100)


class SceneUpdate(BaseModel):
    visual: str | None = None
    prompt: str | None = None


class DraftRequest(BaseModel):
    minutes: int = Field(8, ge=1, le=60)


def view(p: dict) -> dict:
    base = f"/api/projects/{p['id']}/files"
    voice = p.get("voiceover")
    render = p.get("render")
    return {"id": p["id"], "title": p["title"], "createdAt": p["created_at"], "updatedAt": p.get("updated_at"),
            "source": p.get("source") or {}, "script": p["script"], "voice": p["voice"],
            "visualInstructions": p["visual_instructions"], "promptInstructions": p["prompt_instructions"],
            "clipSound": p["clip_sound"],
            "voiceover": {"url": f"{base}/{voice['file']}", "seconds": voice["seconds"], "at": voice["at"]}
            if voice else None,
            "scenes": [{"index": i, "text": s["text"], "start": s["start"], "end": s["end"],
                        "clipSeconds": s["clip_seconds"], "visual": s["visual"], "prompt": s["prompt"],
                        "clip": {"url": f"{base}/{s['clip']['file']}" if s["clip"].get("file") else None,
                                 "speech": s["clip"].get("speech", False), "error": s["clip"].get("error"),
                                 "at": s["clip"].get("at")} if s.get("clip") else None}
                       for i, s in enumerate(p["scenes"])],
            "render": {**render, "url": f"{base}/{render['file']}" if render.get("file") else None} if render else None,
            "estimate": pipeline.estimate(p)}


def _summary(p: dict) -> dict:
    clips = sum(1 for s in p["scenes"] if (s.get("clip") or {}).get("file"))
    step = ("done" if (p.get("render") or {}).get("status") == "done"
            else "clips" if p["scenes"] else "scenes" if p["voiceover"] else "script")
    return {"id": p["id"], "title": p["title"], "createdAt": p["created_at"], "updatedAt": p.get("updated_at"),
            "step": step, "scenes": len(p["scenes"]), "clips": clips, "source": p.get("source") or {}}


def _job(kind: str, label: str, project_id: str, fn) -> dict:
    store.load(project_id)
    return {"job": jobs.start(kind, label, fn, on_done=lambda _: {"project_id": project_id})}


@router.get("")
def list_projects() -> dict:
    return {"projects": [_summary(p) for p in store.all_projects()], "voices": store.VOICES}


@router.post("")
def create_project(body: NewProject) -> dict:
    if body.map_id and body.batch and body.topic:
        p = pipeline.create_from_topic(body.map_id, body.batch, body.topic)
    else:
        p = store.create(body.title, body.script)
    return view(p)


@router.get("/{project_id}")
def get_project(project_id: str) -> dict:
    return view(store.load(project_id))


@router.patch("/{project_id}")
def update_project(project_id: str, body: ProjectUpdate) -> dict:
    return view(store.update(project_id, **body.model_dump()))


@router.delete("/{project_id}")
def delete_project(project_id: str) -> dict:
    store.delete(project_id)
    return {"deleted": project_id}


@router.patch("/{project_id}/scenes/{index}")
def update_scene(project_id: str, index: int, body: SceneUpdate) -> dict:
    return view(store.update_scene(project_id, index, body.visual, body.prompt))


@router.post("/{project_id}/script")
def draft_script(project_id: str, body: DraftRequest) -> dict:
    return _job("script", "Writing the script", project_id,
                lambda report: pipeline.draft_script(project_id, body.minutes, report))


@router.post("/{project_id}/voiceover")
def make_voiceover(project_id: str) -> dict:
    return _job("voiceover", "Generating the voiceover", project_id,
                lambda report: pipeline.make_voiceover(project_id, report))


@router.post("/{project_id}/scenes")
def make_scenes(project_id: str) -> dict:
    return _job("scenes", "Generating the scenes", project_id, lambda report: pipeline.make_scenes(project_id, report))


@router.post("/{project_id}/clips")
def make_clips(project_id: str) -> dict:
    return _job("clips", "Generating clips", project_id, lambda report: pipeline.make_clips(project_id, report))


@router.post("/{project_id}/scenes/{index}/clip")
def make_clip(project_id: str, index: int) -> dict:
    return _job("clip", f"Generating clip {index + 1}", project_id,
                lambda report: pipeline.make_clip(project_id, index, report))


@router.post("/{project_id}/render")
def render(project_id: str) -> dict:
    return _job("render", "Rendering the video", project_id, lambda report: pipeline.render(project_id, report))


@router.get("/{project_id}/files/{name}")
def project_file(project_id: str, name: str) -> FileResponse:
    path = store.file(project_id, name)
    return FileResponse(path, media_type=MEDIA_TYPES.get(path.suffix, "application/octet-stream"))
