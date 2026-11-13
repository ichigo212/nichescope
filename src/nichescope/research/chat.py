"""Questions about a map, answered from its channels, breakouts and analytics."""
from __future__ import annotations

import logging
import re
import uuid

import requests

from .. import ai
from ..util import Reporter, silent, utc_now
from . import attachments, briefing, metrics, storage

log = logging.getLogger(__name__)

HISTORY = 12
THUMBNAILS_SENT = 6
ANSWER_SCHEMA = {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]}
SUGGESTED_QUESTIONS = (
    "What's working lately in my niche?",
    "How are my competitors doing?",
    "How can I stand out?",
    "Which formats work best for my competitors this month?",
    "Which of my videos did best lately, and why?",
)


def _thumbnail_parts(m: dict) -> list:
    parts: list = []
    for tag, rows in (("THIS CHANNEL", m["videos"][:THUMBNAILS_SENT]),
                      ("BREAKOUT", metrics.evidence_pool(m)[:THUMBNAILS_SENT])):
        for v in rows:
            if not v.get("thumbnail"):
                continue
            try:
                r = requests.get(v["thumbnail"], timeout=20)
                r.raise_for_status()
            except requests.RequestException as e:
                log.warning("thumbnail %s failed: %s", v["id"], e)
                continue
            parts += [f"{tag}: {v['title']} ({v['views']} views)", ai.image_part(r.content)]
    return parts


def ask(map_id: str, question: str, chat_id: str | None = None, files: list[str] | None = None,
        report: Reporter = silent) -> dict:
    """Answer a question, starting a conversation or continuing `chat_id`."""
    question = (question or "").strip()
    if not question:
        raise ValueError("type a question")
    m = storage.require(map_id)
    thread = next((c for c in m["chats"] if c["id"] == chat_id), None)
    if chat_id and thread is None:
        raise ValueError("that conversation no longer exists")
    parts = attachments.parts(map_id, files or []) if files else []
    if re.search(r"thumb", question, re.I):
        report("fetching thumbnails")
        parts += _thumbnail_parts(m)
    past = ""
    if thread:
        past = "\n\nCONVERSATION SO FAR:\n" + "\n".join(
            f"{'User' if r['role'] == 'user' else 'You'}: {r['content']}" for r in thread["messages"][-HISTORY:])
    report("thinking")
    prompt = (briefing.brief(m) + past + f"\n\nThe user asks: {question}\n\n"
              "Answer only from the data above" + (" and the attached files" if parts else "")
              + ". Name channels and videos and give numbers. If the data cannot answer part of the "
              "question, say which part and why. Never invent a figure.\n\n"
              "Format the answer in Markdown for reading on screen:\n"
              "- Start with the direct answer in one or two sentences.\n"
              "- Then short ## headings over bullet lists, one point per bullet. Bold only key words.\n"
              "- Refer to videos by title, never by id, with at most three examples per point.\n"
              "- End with a next step when the question calls for one.\n"
              "- Stay under 350 words unless asked for more.")
    got = ai.generate([*parts, prompt], ANSWER_SCHEMA, light=True)
    now = utc_now()
    with storage.lock(map_id):
        m = storage.require(map_id)
        thread = next((c for c in m["chats"] if c["id"] == chat_id), None)
        if thread is None:
            thread = {"id": uuid.uuid4().hex[:12], "at": now, "messages": []}
            m["chats"].insert(0, thread)
        thread["messages"] += [
            {"role": "user", "content": question, "at": now,
             "files": [attachments.describe(map_id, f) for f in files or []]},
            {"role": "model", "content": got.get("answer", ""), "at": now, "files": []}]
        storage.save(m)
        return m
