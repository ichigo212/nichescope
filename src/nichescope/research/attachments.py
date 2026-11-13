"""Files attached to topic requests and chat questions: images, PDFs, Word and text files."""
from __future__ import annotations

import re
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

from .. import ai
from ..config import settings

MAX_FILES = 4
MAX_BYTES = 20 * 1024 * 1024
TEXT_CHARS = 60_000
TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
         ".pdf": "application/pdf", ".docx": "docx", ".txt": "text", ".md": "text", ".csv": "text"}


def _dir(map_id: str) -> Path:
    d = settings().uploads_dir / map_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def save(map_id: str, filename: str, data: bytes) -> dict:
    """Store an uploaded file. -> {id, name, kind}"""
    ext = Path(filename or "").suffix.lower()
    if ext not in TYPES:
        raise ValueError(f"unsupported file type {ext or '(none)'}; use images, PDF, .docx or text files")
    if len(data) > MAX_BYTES:
        raise ValueError("files are limited to 20 MB")
    file_id = f"{uuid.uuid4().hex[:16]}{ext}"
    (_dir(map_id) / file_id).write_bytes(data)
    safe_name = re.sub(r"[^\w.\- ]", "_", Path(filename).name)[:120]
    (_dir(map_id) / f"{file_id}.name").write_text(safe_name, encoding="utf-8")
    return {"id": file_id, "name": safe_name, "kind": "image" if TYPES[ext].startswith("image/") else "file"}


def path(map_id: str, file_id: str) -> Path:
    p = _dir(map_id) / Path(str(file_id)).name
    if not p.is_file() or p.suffix.lower() not in TYPES:
        raise FileNotFoundError("that attachment no longer exists")
    return p


def describe(map_id: str, file_id: str) -> dict:
    p = path(map_id, file_id)
    name_file = p.with_name(p.name + ".name")
    name = name_file.read_text(encoding="utf-8") if name_file.exists() else p.name
    return {"id": p.name, "name": name, "kind": "image" if TYPES[p.suffix.lower()].startswith("image/") else "file"}


def _docx_text(data: bytes) -> str:
    with zipfile.ZipFile(BytesIO(data)) as z:
        xml = z.read("word/document.xml")
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs = []
    for p in ElementTree.fromstring(xml).iter(f"{ns}p"):
        text = "".join(t.text or "" for t in p.iter(f"{ns}t"))
        if text.strip():
            paragraphs.append(text)
    return "\n".join(paragraphs)


def parts(map_id: str, file_ids: list[str]) -> list:
    """Model input parts for attached files, each preceded by its name."""
    if len(file_ids) > MAX_FILES:
        raise ValueError(f"attach {MAX_FILES} files at most")
    out: list = []
    for fid in file_ids:
        p = path(map_id, fid)
        name = describe(map_id, fid)["name"]
        kind = TYPES[p.suffix.lower()]
        data = p.read_bytes()
        if kind == "text":
            out.append(f"Attached file {name}:\n{data.decode('utf-8', 'replace')[:TEXT_CHARS]}")
        elif kind == "docx":
            out.append(f"Attached document {name}:\n{_docx_text(data)[:TEXT_CHARS]}")
        else:
            out += [f"Attached file {name}:", ai.file_part(data, kind)]
    return out
