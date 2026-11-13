"""The FastAPI application: JSON API, live events, MCP over HTTP and the web client."""
from __future__ import annotations

import contextlib
import logging
import threading
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__, ai, preferences
from ..projects.store import ProjectNotFound
from ..research import mapping, study
from ..research.storage import MapNotFound
from ..youtube.auth import AuthError
from ..youtube.data_api import QuotaExceeded, YouTubeError
from . import routes_maps, routes_projects, routes_research, routes_setup, routes_system
from .jobs import Busy, jobs

log = logging.getLogger(__name__)

WEB_DIST = Path(__file__).resolve().parents[1] / "web"
REFRESH_EVERY_SEC = 3600
FIRST_REFRESH_SEC = 180


def _auto_refresh(stop: threading.Event) -> None:
    """Refresh the most overdue map about once an hour while the app runs."""
    if stop.wait(FIRST_REFRESH_SEC):
        return
    while True:
        if preferences.get()["auto_refresh"] and not jobs.busy and mapping.due():
            try:
                jobs.start("refresh", "Refreshing an overdue map", lambda report: mapping.refresh_due(report),
                           on_done=lambda m: {"map_id": m["channel_id"]} if m else None)
            except Busy:
                pass
        elif preferences.get()["auto_refresh"] and not jobs.busy and (stale := study.due()):
            try:
                jobs.start("study", "Studying the competitors again", lambda report: study.run(stale[0], report),
                           map_id=stale[0], on_done=lambda m: {"map_id": m["channel_id"]})
            except Busy:
                pass
        if stop.wait(REFRESH_EVERY_SEC):
            return


def create_app(mcp_http: bool = True, auto_refresh: bool = True) -> FastAPI:
    mcp_app = None
    if mcp_http:
        from ..mcp_server import server
        mcp_app = server.streamable_http_app(streamable_http_path="/")

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI):
        stop = threading.Event()
        if auto_refresh:
            threading.Thread(target=_auto_refresh, args=(stop,), name="auto-refresh", daemon=True).start()
        if mcp_app is not None:
            async with mcp_app.router.lifespan_context(mcp_app):
                yield
        else:
            yield
        stop.set()

    app = FastAPI(title="Nichescope", version=__version__, lifespan=lifespan,
                  docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)

    errors = ((MapNotFound, 404), (ProjectNotFound, 404), (Busy, 409), (QuotaExceeded, 429), (ai.NotConfigured, 503),
              (AuthError, 401), (YouTubeError, 502), (ai.AIError, 502), (FileNotFoundError, 404),
              (ValueError, 400), (LookupError, 404))
    for exc, code in errors:
        def handler(_: Request, e: Exception, code: int = code) -> JSONResponse:
            return JSONResponse({"detail": str(e)}, status_code=code)
        app.add_exception_handler(exc, handler)

    @app.middleware("http")
    async def same_origin(request: Request, call_next):
        # Browsers send Origin on cross-site requests; refuse changes coming from other sites.
        origin = request.headers.get("origin")
        changes = request.method not in ("GET", "HEAD", "OPTIONS")
        if changes and origin and urlparse(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "requests from other sites are not allowed"}, status_code=403)
        return await call_next(request)

    app.include_router(routes_system.router)
    app.include_router(routes_setup.router)
    app.include_router(routes_maps.router)
    app.include_router(routes_research.router)
    app.include_router(routes_projects.router)
    if mcp_app is not None:
        app.mount("/mcp", mcp_app)

    if (WEB_DIST / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets", check_dir=False), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def client(path: str) -> FileResponse:
            target = (WEB_DIST / path).resolve()
            if path and target.is_file() and WEB_DIST in target.parents:
                return FileResponse(target)
            return FileResponse(WEB_DIST / "index.html")

    return app
