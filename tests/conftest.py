import json
from datetime import datetime, timedelta, timezone

import pytest

from nichescope import config


def days_ago(n: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=n)).strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    """Every test gets an empty project folder and no credentials."""
    for key in ("GEMINI_API_KEY", "VERTEX_CREDENTIALS", "YOUTUBE_API_KEY", "YOUTUBE_SOURCE", "NICHESCOPE_DATA_DIR"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("NICHESCOPE_HOME", str(tmp_path))
    config.settings.cache_clear()
    yield tmp_path
    config.settings.cache_clear()


def video(vid: str, views: int, age_days: float, title: str = "Rain sounds for sleep", seconds: int = 3600,
          tags: tuple[str, ...] = ("rain", "sleep")) -> dict:
    return {"id": vid, "title": title, "views": views, "published_at": days_ago(age_days), "seconds": seconds,
            "thumbnail": f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg", "description": "", "tags": list(tags)}


@pytest.fixture
def sample_map(home):
    """A small saved map: one channel and two neighbours, one of them breaking out."""
    neighbour_videos = [video(f"n{i}", 1000, 10 + i) for i in range(10)] + [video("hit", 20000, 5)]
    m = {
        "channel_id": "UCaaaaaaaaaaaaaaaaaaaaaa", "title": "Calm Rain", "handle": "@calmrain", "avatar": "",
        "subscribers": 50000, "videos_read": 10, "scanned_at": days_ago(0), "usual": 2000, "views_30d": 40000,
        "videos": [video(f"o{i}", 2000, 4 + i) for i in range(10)],
        "channels": {
            "UCbbbbbbbbbbbbbbbbbbbbbb": {"title": "Storm Sleep", "grade": "close", "coverage": 0.6, "appearances": 6,
                                         "subscribers": 80000, "usual": 1000, "views_30d": 30000,
                                         "breakouts": [{**neighbour_videos[-1], "outlier": 20.0}],
                                         "topic_samples": neighbour_videos[:5]},
            "UCcccccccccccccccccccccc": {"title": "Daily News", "grade": "far", "coverage": 0.1, "appearances": 1,
                                         "subscribers": 900000, "topic_samples": [
                                             video("x1", 5, 3, "Election results tonight", tags=("news",)),
                                             video("x2", 5, 3, "Market report", tags=("news",)),
                                             video("x3", 5, 3, "Weather and traffic", tags=("news",))]},
        },
        "links": [], "expanded": [], "topics": [], "chats": [],
    }
    path = home / "data" / "maps"
    path.mkdir(parents=True)
    (path / f"{m['channel_id']}.json").write_text(json.dumps(m), encoding="utf-8")
    return m
