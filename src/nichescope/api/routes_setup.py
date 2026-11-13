"""Setup endpoints: keys, credential files and model choices."""
from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from .. import setup

router = APIRouter(prefix="/api/setup", tags=["setup"])
MAX_FILE = 200_000


@router.get("")
def get_setup() -> dict:
    return setup.status()


@router.put("")
def update_setup(values: dict[str, str | None]) -> dict:
    return setup.update(values)


@router.post("/vertex")
async def upload_vertex(file: UploadFile = File(...)) -> dict:
    return setup.save_vertex(await file.read(MAX_FILE))


@router.delete("/vertex")
def remove_vertex() -> dict:
    return setup.remove_vertex()


@router.post("/oauth-client")
async def upload_oauth_client(file: UploadFile = File(...)) -> dict:
    return setup.save_oauth_client(await file.read(MAX_FILE))


@router.post("/check")
def check() -> dict:
    return setup.check()
