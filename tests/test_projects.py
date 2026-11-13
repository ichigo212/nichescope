import pytest
from fastapi.testclient import TestClient

from nichescope import ai
from nichescope.api.app import create_app
from nichescope.projects import pipeline, store

SCRIPT = ("Rain has a sound that almost everyone finds calming. It masks sudden noises.\n\n"
          "Tonight we visit a cabin in the forest. Then we climb to a quiet rooftop in the city.")


@pytest.fixture
def fake_models(monkeypatch):
    """Silent speech of a plausible length, scene descriptions and tone clips."""
    def speech(text, voice):
        return b"\x00\x00" * int(ai.SPEECH_RATE * len(text.split()) / 2.5)

    def generate(parts, schema=None, **_):
        if "scenes" in (schema or {}).get("properties", {}):
            n = schema["properties"]["scenes"]["minItems"]
            return {"scenes": [{"visual": f"Shot {i + 1}", "prompt": f"Rain scene {i + 1}"} for i in range(n)]}
        return {"speech": False}

    def video(prompt, seconds, aspect_ratio="16:9"):
        out = store.settings().projects_dir / "tone.mp4"
        pipeline._run(["-f", "lavfi", "-i", f"testsrc2=size=640x360:rate=24:duration={seconds}", "-f", "lavfi",
                       "-i", f"sine=frequency=440:duration={seconds}", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                       "-c:a", "aac", "-shortest", str(out)])
        return out.read_bytes()

    monkeypatch.setattr(ai, "speech", speech)
    monkeypatch.setattr(ai, "generate", generate)
    monkeypatch.setattr(ai, "video", video)


def test_chunks_respect_the_size_limit():
    long = " ".join(["This is one sentence."] * 400)
    chunks = pipeline._chunks(long)
    assert len(chunks) > 1 and all(len(c) <= pipeline.SPEECH_CHUNK_CHARS for c in chunks)


def test_shots_group_sentences_up_to_the_longest_clip():
    timeline = [{"text": f"s{i}", "start": i * 2.0, "end": i * 2.0 + 2.0} for i in range(10)]
    shots = pipeline._shots(timeline)
    assert all(s["end"] - s["start"] <= pipeline.CLIP_LENGTHS[-1] for s in shots)
    assert shots[0]["start"] == 0 and shots[-1]["end"] == 20.0


def test_locks_follow_the_steps(fake_models):
    p = store.create("Rain", SCRIPT)
    store.update(p["id"], voice="Puck")
    with pytest.raises(ValueError):
        store.update(p["id"], voice="Nobody")
    pipeline.make_voiceover(p["id"])
    with pytest.raises(ValueError):
        store.update(p["id"], script="new words")
    pipeline.make_scenes(p["id"])
    with pytest.raises(ValueError):
        store.update(p["id"], visual_instructions="moody")
    assert store.update(p["id"], clip_sound=0)["clip_sound"] == 0


def test_full_pipeline_renders_a_video(fake_models):
    p = store.create("Rain", SCRIPT)
    p = pipeline.make_voiceover(p["id"])
    assert p["voiceover"]["seconds"] > 5
    p = pipeline.make_scenes(p["id"])
    assert p["scenes"] and all(s["prompt"] for s in p["scenes"])
    p = pipeline.make_clips(p["id"])
    assert all(s["clip"]["file"] and not s["clip"]["speech"] for s in p["scenes"])
    p = pipeline.render(p["id"])
    assert p["render"]["status"] == "done"
    info = pipeline._run(["-i", str(store.folder(p["id"]) / p["render"]["file"])]).stderr
    assert "1920x1080" in info and "Audio:" in info


def test_render_needs_every_clip(fake_models):
    p = store.create("Rain", SCRIPT)
    pipeline.make_voiceover(p["id"])
    pipeline.make_scenes(p["id"])
    with pytest.raises(ValueError):
        pipeline.render(p["id"])


def test_estimate_before_and_after_scenes(fake_models):
    p = store.create("Rain", SCRIPT)
    before = pipeline.estimate(p)
    assert before["scenes"] > 0 and before["video_cost"] > 0
    p = pipeline.make_scenes(pipeline.make_voiceover(p["id"])["id"])
    assert pipeline.estimate(p)["clip_seconds"] == sum(s["clip_seconds"] for s in p["scenes"])


def test_project_api(fake_models):
    with TestClient(create_app(mcp_http=False)) as c:
        made = c.post("/api/projects", json={"title": "Rain", "script": SCRIPT}).json()
        assert made["estimate"]["scenes"] > 0
        assert c.get("/api/projects").json()["projects"][0]["step"] == "script"
        assert c.patch(f"/api/projects/{made['id']}", json={"voice": "Charon"}).json()["voice"] == "Charon"
        assert c.patch(f"/api/projects/{made['id']}", json={"clip_sound": 300}).status_code == 422
        assert c.get("/api/projects/abc123def456").status_code == 404
        assert c.get(f"/api/projects/{made['id']}/files/video.mp4").status_code == 404
        assert c.delete(f"/api/projects/{made['id']}").status_code == 200
