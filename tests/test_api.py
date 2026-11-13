import pytest
from fastapi.testclient import TestClient

from nichescope.api.app import create_app


@pytest.fixture
def client():
    with TestClient(create_app(mcp_http=False)) as c:
        yield c


def test_status_reports_missing_configuration(client):
    s = client.get("/api/status").json()
    assert s["configured"]["model"] is False
    assert s["job"] is None and s["quotaLeft"] == 10_000


def test_home_lists_maps(client, sample_map):
    home = client.get("/api/home").json()
    assert [c["title"] for c in home["cards"]] == ["Calm Rain"]
    assert home["breakouts"][0]["id"] == "hit"


def test_map_view(client, sample_map):
    m = client.get(f"/api/maps/{sample_map['channel_id']}").json()
    assert m["title"] == "Calm Rain"
    assert [c["title"] for c in m["channels"]] == ["Storm Sleep"]
    assert m["settings"]["topics"] == 5


def test_unknown_map_is_404(client):
    r = client.get("/api/maps/UCzzzzzzzzzzzzzzzzzzzzzz")
    assert r.status_code == 404 and r.json()["detail"]


def test_invalid_filter_is_400(client, sample_map):
    r = client.post("/api/research/videos", json={"views_min": "lots"})
    assert r.status_code == 400


def test_export_csv(client, sample_map):
    r = client.get(f"/api/maps/{sample_map['channel_id']}/export/channels.csv")
    assert r.status_code == 200 and "Storm Sleep" in r.text


def test_settings_update(client, sample_map):
    r = client.put(f"/api/maps/{sample_map['channel_id']}/settings", json={"titles": 4})
    assert r.json()["settings"]["titles"] == 4
    assert client.put(f"/api/maps/{sample_map['channel_id']}/settings", json={"titles": 40}).status_code == 400


def test_upload_rejects_unknown_types(client, sample_map):
    r = client.post(f"/api/maps/{sample_map['channel_id']}/files", files={"file": ("x.exe", b"MZ")})
    assert r.status_code == 400


def test_upload_and_fetch_text_file(client, sample_map):
    r = client.post(f"/api/maps/{sample_map['channel_id']}/files", files={"file": ("notes.txt", b"calm videos")})
    file_id = r.json()["id"]
    assert client.get(f"/api/maps/{sample_map['channel_id']}/files/{file_id}").content == b"calm videos"


def test_mesh(client, sample_map):
    mesh = client.get("/api/mesh", params={"center": sample_map["channel_id"]}).json()
    steps = {n["id"]: n.get("step") for n in mesh["nodes"]}
    assert steps[sample_map["channel_id"]] == 0
    assert steps["UCbbbbbbbbbbbbbbbbbbbbbb"] == 1
