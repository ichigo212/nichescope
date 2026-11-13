"""Runtime configuration, read from environment variables and an optional `.env` file."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _path(value: str | None, default: Path, base: Path) -> Path:
    if not value:
        return default
    p = Path(value).expanduser()
    return p if p.is_absolute() else (base / p).resolve()


@dataclass(frozen=True)
class Settings:
    root: Path
    data_dir: Path
    gemini_api_key: str = ""
    vertex_credentials: Path | None = None
    vertex_location: str = "global"
    model: str = "gemini-3.5-flash"
    light_model: str = "gemini-3.5-flash-lite"
    embed_model: str = "gemini-embedding-2"
    tts_model: str = "gemini-3.8-flash-tts"
    video_model: str = "veo-3.1-fast-generate-001"
    video_location: str = "us-central1"
    video_price_per_second: float = 0.15
    youtube_api_key: str = ""
    youtube_source: str = "public"
    oauth_client_file: Path | None = None
    host: str = "127.0.0.1"
    port: int = 8765
    quota_per_day: int = 10_000
    extra: dict = field(default_factory=dict)

    @property
    def maps_dir(self) -> Path:
        return self._dir("maps")

    @property
    def removed_dir(self) -> Path:
        return self._dir("maps", "removed")

    @property
    def accounts_dir(self) -> Path:
        return self._dir("accounts")

    @property
    def transcripts_dir(self) -> Path:
        return self._dir("transcripts")

    @property
    def uploads_dir(self) -> Path:
        return self._dir("uploads")

    @property
    def projects_dir(self) -> Path:
        return self._dir("projects")

    @property
    def database(self) -> Path:
        return self.data_dir / "research.db"

    @property
    def quota_file(self) -> Path:
        return self.data_dir / "quota.json"

    @property
    def preferences_file(self) -> Path:
        return self.data_dir / "preferences.json"

    def _dir(self, *parts: str) -> Path:
        d = self.data_dir.joinpath(*parts)
        d.mkdir(parents=True, exist_ok=True)
        return d


@lru_cache(maxsize=1)
def settings() -> Settings:
    root = Path(os.environ.get("NICHESCOPE_HOME") or PROJECT_ROOT)
    load_dotenv(root / ".env", override=False)
    env = os.environ.get
    vertex = env("VERTEX_CREDENTIALS")
    oauth = env("YOUTUBE_OAUTH_CLIENT")
    default_oauth = root / "credentials" / "youtube_oauth_client.json"
    return Settings(
        root=root,
        data_dir=_path(env("NICHESCOPE_DATA_DIR"), root / "data", root),
        gemini_api_key=env("GEMINI_API_KEY", ""),
        vertex_credentials=_path(vertex, root, root) if vertex else None,
        vertex_location=env("VERTEX_LOCATION", "global"),
        model=env("GEMINI_MODEL") or "gemini-3.5-flash",
        light_model=env("GEMINI_LIGHT_MODEL") or "gemini-3.5-flash-lite",
        embed_model=env("GEMINI_EMBED_MODEL") or "gemini-embedding-2",
        tts_model=env("GEMINI_TTS_MODEL") or "gemini-3.8-flash-tts",
        video_model=env("VIDEO_MODEL") or "veo-3.1-fast-generate-001",
        video_location=env("VIDEO_LOCATION") or "us-central1",
        video_price_per_second=float(env("VIDEO_PRICE_PER_SECOND") or 0.15),
        youtube_api_key=env("YOUTUBE_API_KEY", ""),
        youtube_source="api" if (env("YOUTUBE_SOURCE") or "").strip().lower() == "api" else "public",
        oauth_client_file=_path(oauth, default_oauth, root) if oauth else default_oauth,
        host=env("NICHESCOPE_HOST", "127.0.0.1"),
        port=int(env("NICHESCOPE_PORT", "8765")),
        quota_per_day=int(env("YOUTUBE_QUOTA_PER_DAY", "10000")),
    )
