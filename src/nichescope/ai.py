"""Gemini access: structured generation and text embeddings.

Credentials come from `VERTEX_CREDENTIALS` (a service-account file, used with Vertex AI)
or `GEMINI_API_KEY` (Google AI Studio). Vertex is preferred when both are set.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Any

from .config import settings
from .util import Reporter, silent

log = logging.getLogger(__name__)

EMBED_DIMS = 768
EMBED_WORKERS = 8
CALL_TIMEOUT_MS = 300_000
RETRIES = 4


class AIError(RuntimeError):
    pass


class NotConfigured(AIError):
    pass


def _vertex_client(location: str):
    from google import genai
    from google.genai import types
    from google.oauth2.service_account import Credentials

    sa = settings().vertex_credentials
    creds = Credentials.from_service_account_file(str(sa), scopes=["https://www.googleapis.com/auth/cloud-platform"])
    project = json.loads(sa.read_text(encoding="utf-8"))["project_id"]
    return genai.Client(vertexai=True, credentials=creds, project=project, location=location,
                        http_options=types.HttpOptions(timeout=CALL_TIMEOUT_MS))


@lru_cache(maxsize=1)
def _client():
    from google import genai
    from google.genai import types

    cfg = settings()
    if cfg.vertex_credentials and cfg.vertex_credentials.is_file():
        return _vertex_client(cfg.vertex_location)
    if cfg.gemini_api_key:
        return genai.Client(api_key=cfg.gemini_api_key, http_options=types.HttpOptions(timeout=CALL_TIMEOUT_MS))
    raise NotConfigured("set GEMINI_API_KEY or VERTEX_CREDENTIALS in .env to use the model")


@lru_cache(maxsize=1)
def _video_client():
    cfg = settings()
    if not (cfg.vertex_credentials and cfg.vertex_credentials.is_file()):
        raise NotConfigured("video clips need Vertex AI: set VERTEX_CREDENTIALS in .env")
    return _vertex_client(cfg.video_location)


def video_available() -> bool:
    cfg = settings()
    return bool(cfg.vertex_credentials and cfg.vertex_credentials.is_file())


def available() -> bool:
    cfg = settings()
    return bool(cfg.gemini_api_key or (cfg.vertex_credentials and cfg.vertex_credentials.is_file()))


def _retryable(err: Exception) -> bool:
    s = str(err)
    low = s.lower()
    return any(k in s for k in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "500", "INTERNAL")) \
        or "timeout" in low or "timed out" in low or "deadline" in low


def image_part(data: bytes, mime_type: str = "image/jpeg"):
    from google.genai import types
    return types.Part.from_bytes(data=data, mime_type=mime_type)


def file_part(data: bytes, mime_type: str):
    from google.genai import types
    return types.Part.from_bytes(data=data, mime_type=mime_type)


def generate(parts: Sequence[Any], schema: dict | None = None, *, light: bool = False,
             model: str | None = None) -> Any:
    """Run one generation. With a JSON schema the parsed object is returned, else text."""
    from google.genai import types

    cfg = settings()
    chosen = model or (cfg.light_model if light else cfg.model)
    fallbacks = [m for m in dict.fromkeys([chosen, cfg.model, cfg.light_model]) if m]
    config: dict[str, Any] = {"max_output_tokens": 32768}
    if schema:
        config["response_mime_type"] = "application/json"
        config["response_json_schema"] = schema
    last: Exception | None = None
    for attempt in range(RETRIES + len(fallbacks)):
        name = fallbacks[min(attempt // 2, len(fallbacks) - 1)]
        options = dict(config)
        if name.startswith("gemini-3"):
            options["thinking_config"] = types.ThinkingConfig(thinking_level="low")
        try:
            r = _client().models.generate_content(
                model=name, contents=list(parts), config=types.GenerateContentConfig(**options))
            feedback = getattr(r, "prompt_feedback", None)
            blocked = str(getattr(feedback, "block_reason", "") or "")
            if not getattr(r, "candidates", None) and blocked and "UNSPECIFIED" not in blocked:
                raise AIError(f"the model declined the request ({blocked})")
            if not schema:
                return r.text or ""
            if not r.text:
                raise json.JSONDecodeError("empty response", "", 0)
            return json.loads(r.text)
        except NotConfigured:
            raise
        except json.JSONDecodeError as e:
            last = e
            log.warning("model returned unreadable JSON (model=%s, attempt=%d)", name, attempt + 1)
        except AIError:
            raise
        except Exception as e:  # noqa: BLE001 - the SDK raises many unrelated types
            last = e
            if not _retryable(e):
                raise AIError(f"{type(e).__name__}: {e}") from e
            wait = min(60, 5 * (attempt + 1))
            log.warning("model busy, retrying in %ss (model=%s): %s", wait, name, str(e)[:160])
            time.sleep(wait)
    raise AIError(f"the model did not answer after several attempts: {last}")


def embed(texts: Sequence[str], *, query: bool = False, report: Reporter = silent) -> list[list[float] | None]:
    """One vector per text, or None where a text could not be embedded."""
    from google.genai import types

    cfg = settings()
    items = [str(t or "").strip()[:8000] for t in texts]
    out: list[list[float] | None] = [None] * len(items)
    if not items:
        return out
    client = _client()
    config = types.EmbedContentConfig(task_type="RETRIEVAL_QUERY" if query else "RETRIEVAL_DOCUMENT",
                                      output_dimensionality=EMBED_DIMS)
    lock = threading.Lock()
    done = [0]

    def one(i: int) -> None:
        if not items[i]:
            return
        for attempt in range(6):
            try:
                r = client.models.embed_content(model=cfg.embed_model, contents=items[i], config=config)
                out[i] = list(r.embeddings[0].values)
                break
            except Exception as e:  # noqa: BLE001
                if not _retryable(e) or attempt == 5:
                    log.warning("embedding failed: %s", str(e)[:160])
                    break
                time.sleep(min(30, 2 * (attempt + 1)))
        with lock:
            done[0] += 1
            if done[0] % 100 == 0:
                report(f"embedded {done[0]} of {len(items)}")

    with ThreadPoolExecutor(max_workers=EMBED_WORKERS) as pool:
        list(pool.map(one, range(len(items))))
    return out


def speech(text: str, voice: str) -> bytes:
    """Read text aloud. Returns 16-bit mono PCM at SPEECH_RATE Hz."""
    from google.genai import types

    config = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice))))
    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            r = _client().models.generate_content(model=settings().tts_model, contents=text, config=config)
            parts = r.candidates[0].content.parts if r.candidates else []
            audio = b"".join(p.inline_data.data for p in parts if getattr(p, "inline_data", None))
            if not audio:
                raise AIError("the speech model returned no audio")
            return audio
        except NotConfigured:
            raise
        except Exception as e:  # noqa: BLE001 - the SDK raises many unrelated types
            last = e
            if not _retryable(e):
                raise AIError(f"{type(e).__name__}: {e}") from e
            time.sleep(min(60, 5 * (attempt + 1)))
    raise AIError(f"the speech model did not answer: {last}")


SPEECH_RATE = 24_000
VIDEO_POLL_SEC = 10
VIDEO_TIMEOUT_SEC = 900


def video(prompt: str, seconds: int, aspect_ratio: str = "16:9") -> bytes:
    """Generate one video clip with sound. Returns MP4 bytes."""
    from google.genai import types

    client = _video_client()
    config = types.GenerateVideosConfig(number_of_videos=1, duration_seconds=seconds, aspect_ratio=aspect_ratio,
                                        resolution="1080p", generate_audio=True)
    try:
        op = client.models.generate_videos(model=settings().video_model, prompt=prompt, config=config)
        waited = 0
        while not op.done:
            if waited >= VIDEO_TIMEOUT_SEC:
                raise AIError("the clip took too long to generate")
            time.sleep(VIDEO_POLL_SEC)
            waited += VIDEO_POLL_SEC
            op = client.operations.get(op)
    except (AIError, NotConfigured):
        raise
    except Exception as e:  # noqa: BLE001
        raise AIError(f"{type(e).__name__}: {e}") from e
    if op.error:
        raise AIError(f"the clip could not be generated: {op.error.get('message', op.error)}")
    videos = (op.response.generated_videos if op.response else None) or []
    if not videos or not videos[0].video or not videos[0].video.video_bytes:
        reasons = getattr(op.response, "rai_media_filtered_reasons", None) if op.response else None
        raise AIError(f"the clip was not returned{': ' + '; '.join(reasons) if reasons else ''}")
    return videos[0].video.video_bytes
