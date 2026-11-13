"""Reading and changing the installation's configuration from the app.

Values are written to `.env` in the project folder and applied to the running process.
Credential files are stored in `credentials/`. Secrets are never returned in full.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from . import ai, config

EDITABLE = {
    "GEMINI_API_KEY": "secret",
    "YOUTUBE_API_KEY": "secret",
    "YOUTUBE_SOURCE": ("public", "api"),
    "GEMINI_MODEL": "text",
    "GEMINI_LIGHT_MODEL": "text",
    "GEMINI_EMBED_MODEL": "text",
    "GEMINI_TTS_MODEL": "text",
    "VIDEO_MODEL": "text",
    "VIDEO_LOCATION": "text",
    "VIDEO_PRICE_PER_SECOND": "number",
    "VERTEX_LOCATION": "text",
}
VERTEX_FILE = "credentials/vertex-service-account.json"
OAUTH_FILE = "credentials/youtube_oauth_client.json"


def _env_path() -> Path:
    return config.settings().root / ".env"


def _mask(value: str) -> str | None:
    return f"set, ending {value[-4:]}" if value else None


def write_env(changes: dict[str, str]) -> None:
    """Set or clear variables in `.env`, keeping every other line, and apply them now."""
    path = _env_path()
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    pending = dict(changes)
    out = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        if key in pending:
            value = pending.pop(key)
            if value:
                out.append(f"{key}={value}")
            continue
        out.append(line)
    out += [f"{k}={v}" for k, v in pending.items() if v]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    for key, value in changes.items():
        if value:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)
    reload()


def reload() -> None:
    config.settings.cache_clear()
    ai._client.cache_clear()
    ai._video_client.cache_clear()


def update(values: dict[str, str | None]) -> dict:
    changes: dict[str, str] = {}
    for key, value in values.items():
        if key not in EDITABLE or value is None:
            continue
        value = str(value).strip()
        kind = EDITABLE[key]
        if isinstance(kind, tuple) and value not in kind:
            raise ValueError(f"{key} must be one of: {', '.join(kind)}")
        if kind == "number" and value:
            try:
                float(value)
            except ValueError:
                raise ValueError(f"{key} must be a number") from None
        if kind == "secret" and value and not re.fullmatch(r"[\w\-.]{10,200}", value):
            raise ValueError(f"{key} does not look like an API key")
        if kind == "text" and value and not re.fullmatch(r"[\w\-.]{1,100}", value):
            raise ValueError(f"{key} has characters that are not allowed")
        changes[key] = value
    if changes:
        write_env(changes)
    return status()


def save_vertex(data: bytes) -> dict:
    """Store a Vertex AI service-account key and point the configuration at it."""
    try:
        info = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ValueError("that file is not JSON") from None
    if info.get("type") != "service_account" or not info.get("project_id") or not info.get("private_key"):
        raise ValueError("that is not a Google Cloud service-account key file")
    path = config.settings().root / VERTEX_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    write_env({"VERTEX_CREDENTIALS": VERTEX_FILE})
    return status()


def remove_vertex() -> dict:
    path = config.settings().root / VERTEX_FILE
    path.unlink(missing_ok=True)
    write_env({"VERTEX_CREDENTIALS": ""})
    return status()


def save_oauth_client(data: bytes) -> dict:
    """Store a YouTube OAuth desktop client, used to connect channels for analytics."""
    try:
        info = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ValueError("that file is not JSON") from None
    client = info.get("installed") or info.get("web") or {}
    if not client.get("client_id") or not client.get("client_secret"):
        raise ValueError("that is not an OAuth client file; download it from Google Cloud > Credentials")
    path = config.settings().root / OAUTH_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    write_env({"YOUTUBE_OAUTH_CLIENT": OAUTH_FILE})
    return status()


def status() -> dict:
    cfg = config.settings()
    vertex = cfg.vertex_credentials if cfg.vertex_credentials and cfg.vertex_credentials.is_file() else None
    project = None
    if vertex:
        try:
            project = json.loads(vertex.read_text(encoding="utf-8")).get("project_id")
        except (OSError, ValueError):
            project = None
    oauth = cfg.oauth_client_file if cfg.oauth_client_file and cfg.oauth_client_file.is_file() else None
    return {
        "geminiApiKey": _mask(cfg.gemini_api_key),
        "vertex": {"project": project} if vertex else None,
        "youtubeApiKey": _mask(cfg.youtube_api_key),
        "youtubeSource": cfg.youtube_source,
        "oauthClient": bool(oauth),
        "models": {"GEMINI_MODEL": cfg.model, "GEMINI_LIGHT_MODEL": cfg.light_model,
                   "GEMINI_EMBED_MODEL": cfg.embed_model, "GEMINI_TTS_MODEL": cfg.tts_model,
                   "VIDEO_MODEL": cfg.video_model, "VIDEO_LOCATION": cfg.video_location,
                   "VIDEO_PRICE_PER_SECOND": str(cfg.video_price_per_second),
                   "VERTEX_LOCATION": cfg.vertex_location},
        "ready": {"model": ai.available(), "video": ai.video_available(),
                  "youtube": cfg.youtube_source == "public" or bool(cfg.youtube_api_key),
                  "analytics": bool(oauth)},
    }


def check() -> dict:
    """Try each configured service once with the smallest possible request."""
    from .youtube import pages

    results: dict[str, dict] = {}
    try:
        ai.generate(["Reply with ok."], {"type": "object", "properties": {"ok": {"type": "string"}},
                                          "required": ["ok"]}, light=True)
        results["model"] = {"ok": True}
    except Exception as e:  # noqa: BLE001 - reported to the user as-is
        results["model"] = {"ok": False, "error": str(e)[:300]}
    try:
        got = pages.channel("UCsXVk37bltHxD1rDPwtNM8Q", videos=1)
        results["youtube"] = {"ok": bool(got.get("title"))}
    except Exception as e:  # noqa: BLE001
        results["youtube"] = {"ok": False, "error": str(e)[:300]}
    if ai.video_available():
        try:
            ai._video_client().models.get(model=config.settings().video_model)
            results["video"] = {"ok": True}
        except Exception as e:  # noqa: BLE001
            results["video"] = {"ok": False, "error": str(e)[:300]}
    return results
