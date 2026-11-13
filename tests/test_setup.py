import json

import pytest
from fastapi.testclient import TestClient

from nichescope import config, setup
from nichescope.api.app import create_app


@pytest.fixture
def client():
    with TestClient(create_app(mcp_http=False, auto_refresh=False)) as c:
        yield c


def test_update_writes_env_and_applies_it(home, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    (home / ".env").write_text("# my settings\nNICHESCOPE_PORT=9000\n", encoding="utf-8")
    got = setup.update({"GEMINI_API_KEY": "AIzaTESTKEY1234567890", "YOUTUBE_SOURCE": "public"})
    text = (home / ".env").read_text(encoding="utf-8")
    assert "# my settings" in text and "NICHESCOPE_PORT=9000" in text and "GEMINI_API_KEY=AIzaTESTKEY1234567890" in text
    assert got["geminiApiKey"] == "set, ending 7890"
    assert config.settings().gemini_api_key == "AIzaTESTKEY1234567890"
    setup.update({"GEMINI_API_KEY": ""})
    assert "GEMINI_API_KEY" not in (home / ".env").read_text(encoding="utf-8")


def test_update_rejects_bad_values(home):
    with pytest.raises(ValueError):
        setup.update({"YOUTUBE_SOURCE": "scrape"})
    with pytest.raises(ValueError):
        setup.update({"GEMINI_API_KEY": "has spaces and ; quotes"})


def test_vertex_file_is_validated(home):
    with pytest.raises(ValueError):
        setup.save_vertex(b'{"type": "authorized_user"}')
    got = setup.save_vertex(json.dumps({"type": "service_account", "project_id": "demo-project",
                                        "private_key": "not-a-real-key"}).encode())
    assert got["vertex"] == {"project": "demo-project"}
    assert (home / "credentials" / "vertex-service-account.json").exists()


def test_setup_never_returns_secrets(client, home):
    setup.update({"YOUTUBE_API_KEY": "AIzaSECRETVALUE99887766"})
    body = client.get("/api/setup").text
    assert "SECRETVALUE" not in body and "7766" in body


def test_cross_site_changes_are_refused(client):
    r = client.put("/api/setup", json={"YOUTUBE_SOURCE": "api"}, headers={"origin": "https://example.com"})
    assert r.status_code == 403
    r = client.put("/api/setup", json={"YOUTUBE_SOURCE": "api"}, headers={"origin": "http://testserver"})
    assert r.status_code == 200 and r.json()["youtubeSource"] == "api"
