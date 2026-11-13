"""Connected YouTube channels (OAuth 2.0, installed-app flow with PKCE).

A connected channel unlocks its private analytics, and its sign-in can also be used
for public Data API reads when no `YOUTUBE_API_KEY` is configured.
"""
from __future__ import annotations

import logging
import secrets
import threading
import time
from base64 import urlsafe_b64encode
from hashlib import sha256
from urllib.parse import urlencode

import requests

from ..config import settings
from ..util import read_json, write_json

log = logging.getLogger(__name__)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/youtube/v3"
SCOPES = ("https://www.googleapis.com/auth/youtube.readonly "
          "https://www.googleapis.com/auth/yt-analytics.readonly")

_pending: dict[str, dict] = {}
_access: dict[str, tuple[str, float]] = {}
_lock = threading.Lock()


class AuthError(RuntimeError):
    pass


def _client() -> tuple[str, str]:
    path = settings().oauth_client_file
    data = read_json(path) if path else None
    if not data:
        raise AuthError("no OAuth client is configured: download a Desktop OAuth client from "
                        "Google Cloud and save it as credentials/youtube_oauth_client.json")
    data = data.get("installed") or data.get("web") or data
    if not data.get("client_id") or not data.get("client_secret"):
        raise AuthError("the OAuth client file has no client_id or client_secret")
    return data["client_id"], data["client_secret"]


def configured() -> bool:
    try:
        _client()
        return True
    except AuthError:
        return False


def accounts() -> list[dict]:
    """Connected channels, oldest first: [{id, title, handle}]."""
    out = []
    files = sorted(settings().accounts_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    for f in files:
        rec = read_json(f)
        if rec and rec.get("channel_id"):
            out.append({"id": rec["channel_id"], "title": rec.get("channel_title", ""),
                        "handle": rec.get("handle", "")})
    return out


def is_own(channel_id: str) -> bool:
    return any(a["id"] == channel_id for a in accounts())


def start(redirect_uri: str) -> str:
    """Begin a sign-in. Returns the Google consent URL to open."""
    client_id, _ = _client()
    verifier = urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    challenge = urlsafe_b64encode(sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(24)
    with _lock:
        _pending[state] = {"verifier": verifier, "redirect": redirect_uri, "at": time.time()}
    return AUTH_URL + "?" + urlencode({
        "client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code",
        "scope": SCOPES, "state": state, "code_challenge": challenge,
        "code_challenge_method": "S256", "access_type": "offline",
        "prompt": "consent select_account"})


def finish(code: str, state: str) -> dict:
    """Complete a sign-in from the OAuth redirect. Returns the connected account."""
    with _lock:
        pending = _pending.pop(state, None)
    if not pending or time.time() - pending["at"] > 900:
        raise AuthError("this sign-in has expired: start it again")
    client_id, client_secret = _client()
    r = requests.post(TOKEN_URL, data={
        "client_id": client_id, "client_secret": client_secret, "code": code,
        "code_verifier": pending["verifier"], "grant_type": "authorization_code",
        "redirect_uri": pending["redirect"]}, timeout=30)
    if r.status_code != 200:
        raise AuthError(f"Google refused the sign-in ({r.status_code})")
    tok = r.json()
    if not tok.get("refresh_token"):
        raise AuthError("Google returned no refresh token: remove the app's access in your "
                        "Google account settings and connect again")
    me = requests.get(f"{API}/channels", params={"part": "snippet", "mine": "true"},
                      headers={"Authorization": f"Bearer {tok['access_token']}"}, timeout=30).json()
    items = me.get("items") or []
    if not items:
        raise AuthError("this Google account has no YouTube channel")
    snippet = items[0]["snippet"]
    rec = {"channel_id": items[0]["id"], "channel_title": snippet.get("title", ""),
           "handle": snippet.get("customUrl", ""), "refresh_token": tok["refresh_token"],
           "connected_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    write_json(settings().accounts_dir / f"{rec['channel_id']}.json", rec, indent=2)
    _access[rec["channel_id"]] = (tok["access_token"], time.monotonic() + int(tok.get("expires_in", 3600)))
    log.info("connected channel %s", rec["channel_title"])
    return {"id": rec["channel_id"], "title": rec["channel_title"], "handle": rec["handle"]}


def disconnect(channel_id: str) -> bool:
    path = settings().accounts_dir / f"{channel_id}.json"
    _access.pop(channel_id, None)
    if path.exists():
        path.unlink()
        return True
    return False


def token(channel_id: str) -> str:
    """A fresh access token for a connected channel."""
    cached = _access.get(channel_id)
    if cached and cached[1] > time.monotonic() + 60:
        return cached[0]
    rec = read_json(settings().accounts_dir / f"{channel_id}.json")
    if not rec:
        raise AuthError(f"channel {channel_id} is not connected")
    client_id, client_secret = _client()
    r = requests.post(TOKEN_URL, data={
        "client_id": client_id, "client_secret": client_secret,
        "refresh_token": rec["refresh_token"], "grant_type": "refresh_token"}, timeout=30)
    if r.status_code != 200:
        try:
            reason = r.json().get("error", "")
        except ValueError:
            reason = ""
        raise AuthError(f"could not refresh access for {rec.get('channel_title', channel_id)} "
                        f"({r.status_code} {reason}): reconnect the channel")
    tok = r.json()
    _access[channel_id] = (tok["access_token"], time.monotonic() + int(tok.get("expires_in", 3600)))
    return tok["access_token"]


def headers(channel_id: str) -> dict:
    return {"Authorization": f"Bearer {token(channel_id)}"}
