"""Map endpoints: mapping channels, editing competitors, topics, saved topics and chat."""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from ..research import attachments, chat, database, export, mapping, storage, topics
from .jobs import jobs
from .views import map_view

router = APIRouter(prefix="/api/maps", tags=["maps"])


def _view(map_id: str) -> dict:
    return map_view(storage.require(map_id))


def _job(kind: str, label: str, map_id: str | None, fn) -> dict:
    return {"job": jobs.start(kind, label, fn, map_id=map_id,
                              on_done=lambda m: {"map_id": m["channel_id"]} if isinstance(m, dict) else None)}


class MapRequest(BaseModel):
    channel: str = Field(..., description="Channel name, link, @handle or id")
    steps: int = Field(1, ge=0, le=mapping.MAX_STEPS)


class StepsRequest(BaseModel):
    steps: int = Field(1, ge=1, le=mapping.MAX_STEPS)


class ChannelRequest(BaseModel):
    channel: str


class CompetitorsRequest(BaseModel):
    names: list[str] = Field(..., min_length=1, max_length=100)


class LearnRequest(BaseModel):
    learn: bool


class SettingsRequest(BaseModel):
    topics: int | None = None
    titles: int | None = None
    instructions: str | None = None
    check_youtube: bool | None = None
    read_descriptions: bool | None = None


class TopicsRequest(BaseModel):
    instructions: str = ""
    files: list[str] = Field(default_factory=list, max_length=attachments.MAX_FILES)


class FollowUpRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    files: list[str] = Field(default_factory=list, max_length=attachments.MAX_FILES)


class MarkRequest(BaseModel):
    kind: str
    key: str
    value: str | None = None


class SaveTopicRequest(BaseModel):
    batch: str
    topic: str


class SavedUpdate(BaseModel):
    status: str | None = None
    note: str | None = None
    title: str | None = None


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    chat: str | None = None
    files: list[str] = Field(default_factory=list, max_length=attachments.MAX_FILES)


@router.post("")
def create_map(body: MapRequest) -> dict:
    return _job("map", f"Mapping {body.channel}", None,
                lambda report: mapping.map_channel(body.channel, body.steps, report))


@router.get("/{map_id}")
def get_map(map_id: str) -> dict:
    return _view(map_id)


@router.delete("/{map_id}")
def remove_map(map_id: str) -> dict:
    return {"kept_as": storage.remove(map_id)}


@router.post("/removed/{file}/restore")
def restore_map(file: str) -> dict:
    return {"id": storage.restore(file)}


@router.post("/{map_id}/refresh")
def refresh(map_id: str) -> dict:
    storage.require(map_id)
    return _job("refresh", "Refreshing the map", map_id, lambda report: mapping.refresh(map_id, report))


@router.post("/{map_id}/deepen")
def deepen(map_id: str, body: StepsRequest) -> dict:
    storage.require(map_id)
    return _job("deepen", "Mapping further out", map_id, lambda report: mapping.deepen(map_id, body.steps, report))


@router.post("/{map_id}/expand")
def expand(map_id: str, body: ChannelRequest) -> dict:
    storage.require(map_id)
    return _job("expand", "Mapping around a neighbour", map_id,
                lambda report: mapping.expand(map_id, body.channel, report))


@router.post("/{map_id}/recheck")
def recheck(map_id: str) -> dict:
    storage.require(map_id)
    return _job("recheck", "Checking which channels belong", map_id,
                lambda report: mapping.recheck(map_id, report))


@router.post("/{map_id}/competitors")
def add_competitors(map_id: str, body: CompetitorsRequest) -> dict:
    storage.require(map_id)
    problems: list[str] = []

    def run(report):
        m, found = mapping.add_competitors(map_id, body.names, report)
        problems.extend(found)
        return m

    label = "Adding a competitor" if len(body.names) == 1 else f"Adding {len(body.names)} competitors"
    return {"job": jobs.start("competitors", label, run, map_id=map_id,
                              on_done=lambda m: {"map_id": map_id, "problems": problems})}


@router.delete("/{map_id}/channels/{channel}")
def remove_channel(map_id: str, channel: str) -> dict:
    return map_view(mapping.remove_channel(map_id, channel))


@router.post("/{map_id}/channels/{channel}/restore")
def restore_channel(map_id: str, channel: str) -> dict:
    return map_view(mapping.restore_channel(map_id, channel))


@router.put("/{map_id}/channels/{channel}/learning")
def set_learning(map_id: str, channel: str, body: LearnRequest) -> dict:
    return map_view(mapping.set_learning(map_id, channel, body.learn))


@router.put("/{map_id}/settings")
def update_settings(map_id: str, body: SettingsRequest) -> dict:
    return map_view(topics.update_settings(map_id, **body.model_dump()))


@router.post("/{map_id}/topics")
def generate_topics(map_id: str, body: TopicsRequest) -> dict:
    storage.require(map_id)
    return _job("topics", "Writing topics", map_id,
                lambda report: topics.suggest(map_id, body.instructions, body.files, report=report))


@router.post("/{map_id}/topics/{batch}/followups")
def follow_up(map_id: str, batch: str, body: FollowUpRequest) -> dict:
    storage.require(map_id)
    return _job("followup", "Answering", map_id,
                lambda report: topics.follow_up(map_id, batch, body.message, body.files, report))


@router.put("/{map_id}/marks")
def mark(map_id: str, body: MarkRequest) -> dict:
    return map_view(topics.mark(map_id, body.kind, body.key, body.value))


@router.post("/{map_id}/saved-topics")
def save_topic(map_id: str, body: SaveTopicRequest) -> dict:
    return map_view(topics.save_topic(map_id, body.batch, body.topic))


@router.patch("/{map_id}/saved-topics/{saved_id}")
def update_saved(map_id: str, saved_id: str, body: SavedUpdate) -> dict:
    return map_view(topics.update_saved(map_id, saved_id, **body.model_dump()))


@router.delete("/{map_id}/saved-topics/{saved_id}")
def remove_saved(map_id: str, saved_id: str) -> dict:
    return map_view(topics.remove_saved(map_id, saved_id))


@router.post("/{map_id}/chats")
def ask(map_id: str, body: AskRequest) -> dict:
    storage.require(map_id)
    return _job("ask", "Answering", map_id,
                lambda report: chat.ask(map_id, body.question, body.chat, body.files, report))


@router.post("/{map_id}/files")
async def upload(map_id: str, file: UploadFile = File(...)) -> dict:
    storage.require(map_id)
    data = await file.read(attachments.MAX_BYTES + 1)
    try:
        return attachments.save(map_id, file.filename or "", data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{map_id}/files/{file_id}")
def get_file(map_id: str, file_id: str) -> FileResponse:
    try:
        return FileResponse(attachments.path(map_id, file_id))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{map_id}/points-to")
def points_to(map_id: str) -> dict:
    return {"rows": database.points_to(map_id)[:80]}


@router.get("/{map_id}/export/{what}.csv")
def export_csv(map_id: str, what: str) -> Response:
    m = storage.require(map_id)
    if what not in ("channels", "breakouts"):
        raise HTTPException(status_code=404, detail="export channels or breakouts")
    body = export.channels_csv(m) if what == "channels" else export.breakouts_csv(m)
    name = f"{m.get('handle') or map_id}-{what}.csv".lstrip("@")
    return Response("﻿" + body, media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})
