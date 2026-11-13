"""Home, status, live events, preferences, connected channels and MCP setup."""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import time
from urllib.parse import urlparse

import requests
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel

from .. import ai, preferences
from ..config import settings
from ..research import mapping, storage
from ..youtube import auth, quota
from .jobs import jobs
from .views import cards, home_breakouts, mesh_view

IMAGE_TIMEOUT_SEC = 8
STREAM_SECONDS = 60
router = APIRouter(prefix="/api", tags=["system"])

IMAGE_HOSTS = ("yt3.ggpht.com", "yt3.googleusercontent.com", "i.ytimg.com", "lh3.googleusercontent.com")
IMAGE_MAX_BYTES = 2_000_000


class PreferencesUpdate(BaseModel):
    auto_refresh: bool | None = None


class ChannelCheck(BaseModel):
    channel: str


def status() -> dict:
    cfg = settings()
    return {"job": jobs.current, "recentJobs": list(jobs.recent)[:5], "quotaLeft": quota.left(),
            "quotaPerDay": cfg.quota_per_day, "accounts": auth.accounts(),
            "configured": {"model": ai.available(),
                           "youtube": cfg.youtube_source == "public" or bool(cfg.youtube_api_key or auth.accounts()),
                           "oauth": auth.configured()},
            "preferences": preferences.get()}


@router.get("/status")
def get_status() -> dict:
    return status()


@router.get("/home")
def home() -> dict:
    return {"cards": cards(), "breakouts": home_breakouts(), "removedMaps": storage.removed()}


@router.get("/mesh")
def mesh(center: str | None = None) -> dict:
    return mesh_view(center)


@router.post("/channels/check")
def check_channel(body: ChannelCheck) -> dict:
    """Resolve a channel and say whether it is too small to map reliably."""
    return mapping.check_size(body.channel)


@router.put("/preferences")
def update_preferences(body: PreferencesUpdate) -> dict:
    return preferences.update(**body.model_dump())


@router.get("/events")
async def events(request: Request) -> StreamingResponse:
    """Server-sent events: job progress and completion."""
    async def stream():
        last = jobs.seq
        # Each stream ends after STREAM_SECONDS and the browser reconnects, so a connection
        # the client forgot cannot hold one of its few connection slots for long.
        ends = time.monotonic() + STREAM_SECONDS
        yield f"retry: 1000\ndata: {json.dumps({'type': 'hello', 'status': status()})}\n\n"
        while time.monotonic() < ends and not await request.is_disconnected():
            got = await asyncio.to_thread(jobs.wait, last, 5.0)
            if not got:
                yield ": ping\n\n"
                continue
            for e in got:
                last = max(last, e["seq"])
                yield f"data: {json.dumps(e, default=str)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/accounts/connect")
def connect_account(request: Request) -> dict:
    redirect = str(request.url_for("oauth_callback"))
    return {"url": auth.start(redirect)}


@router.get("/accounts/callback", name="oauth_callback", response_class=HTMLResponse)
def oauth_callback(code: str = "", state: str = "", error: str = "") -> HTMLResponse:
    if error:
        message = f"Sign-in was cancelled ({error})."
    else:
        try:
            account = auth.finish(code, state)
            message = f"Connected {account['title']}. You can close this tab."
        except auth.AuthError as e:
            message = str(e)
    return HTMLResponse(f"<!doctype html><meta charset=utf-8><title>Nichescope</title>"
                        f"<body style='font:15px system-ui;padding:40px'><p>{message}</p>"
                        f"<script>setTimeout(()=>window.close(),1500)</script>")


@router.delete("/accounts/{channel_id}")
def disconnect_account(channel_id: str) -> dict:
    auth.disconnect(channel_id)
    return {"accounts": auth.accounts()}


@router.get("/mcp")
def mcp_setup(request: Request) -> dict:
    """How to connect an MCP client to this installation."""
    python = sys.executable.replace("pythonw.exe", "python.exe")
    local = {"command": python, "args": ["-m", "nichescope", "mcp"]}
    url = str(request.base_url).rstrip("/") + "/mcp"
    return {"stdio": local, "http": url,
            "claudeCode": f'claude mcp add --scope user nichescope -- "{python}" -m nichescope mcp',
            "claudeCodeHttp": f"claude mcp add --transport http nichescope {url}",
            "desktopConfig": json.dumps({"mcpServers": {"nichescope": local}}, indent=2)}


@router.get("/image")
def image(src: str = Query(..., max_length=2000)) -> Response:
    """A channel avatar or thumbnail from YouTube's image hosts, cached on disk.

    Served from this origin so the web client can draw it into WebGL textures.
    """
    url = ("https:" + src) if src.startswith("//") else src
    host = urlparse(url).hostname or ""
    if urlparse(url).scheme != "https" or host not in IMAGE_HOSTS:
        raise HTTPException(status_code=400, detail="only YouTube image URLs are served")
    folder = settings().data_dir / "cache" / "images"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / hashlib.sha1(url.encode()).hexdigest()
    if not path.exists():
        try:
            r = requests.get(url, timeout=IMAGE_TIMEOUT_SEC)
        except requests.RequestException as e:
            raise HTTPException(status_code=502, detail="the image could not be fetched") from e
        is_image = r.headers.get("content-type", "").startswith("image/")
        if r.status_code != 200 or not is_image or len(r.content) > IMAGE_MAX_BYTES:
            raise HTTPException(status_code=404, detail="no such image")
        path.write_bytes(r.content)
    return Response(path.read_bytes(), media_type="image/jpeg",
                    headers={"Cache-Control": "public, max-age=604800"})
