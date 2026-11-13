from nichescope.research import study

from .conftest import days_ago


def vid(i: int, title: str, views: int, age: float = 30) -> dict:
    return {"id": f"v{i}", "title": title, "views": views, "published_at": days_ago(age), "seconds": 600,
            "thumbnail": ""}


def test_title_habits_are_compared_inside_each_channel():
    a = [vid(i, f"What happens if {i}", 3000) for i in range(8)] + [vid(10 + i, f"Plain {i}", 1000) for i in range(10)]
    b = [vid(30 + i, f"How does {i} work", 900) for i in range(8)] + [vid(50 + i, f"Calm {i}", 300) for i in range(10)]
    rows = study.scored({"A": {"videos": a}, "B": {"videos": b}})
    what = next(t for t in study.title_table(rows) if t["key"] == "what")
    assert what["up"] == 2 and what["down"] == 0
    assert what["share"] == round(16 / 36, 3)
    assert what["with"] > what["without"]


def test_channels_with_too_few_settled_videos_are_left_out():
    rows = study.scored({"A": {"videos": [vid(i, "x", 100) for i in range(5)]},
                         "B": {"videos": [vid(i, "y", 100, age=2) for i in range(30)]}})
    assert rows == []


def test_first_breakout_is_found_oldest_first():
    vs = [vid(1, "first", 200, 300), vid(2, "second", 15000, 290), vid(3, "third", 90000, 10)]
    got = study.escapes([("Small", 900, vs), ("Empty", 10, [])])
    assert got == [{"channel": "Small", "subs": 900, "videos": 3, "hit": 2, "days": 10, "title": "second",
                    "views": 15000}]


def test_thumbnail_styles_are_shares():
    got = study.style_of([{"face": True, "faces": 2, "text_words": 3, "background": "dark"},
                          {"face": False, "faces": 0, "text_words": 1, "background": "bright"}])
    assert got["face"] == 0.5 and got["faces"] == 1.0 and got["words"] == 2.0
    assert got["dark"] == 0.5 and got["bright"] == 0.5 and got["n"] == 2
    assert study.style_of([]) is None


def test_findings_name_title_gaps(sample_map):
    titles = [{"key": "what", "label": "Opens What, Why or How", "share": 0.4, "ours": 0.0, "up": 5, "down": 1}]
    got = study.findings(sample_map, {"channels": 4, "videos": 120, "usual": 5000, "escapes": [], "own": None},
                         titles, None, None)
    assert [f["key"] for f in got] == ["titles"]
    assert "you 0%, them 40%" in got[0]["finding"]


def test_rough_dates_give_no_days():
    vs = [vid(1, "a", 200, 400), vid(2, "b", 20000, 400)]
    assert study.escapes([("Same day", 10, vs)])[0]["days"] is None


def test_a_channel_with_few_videos_is_not_compared(sample_map):
    m = {**sample_map, "videos": sample_map["videos"][:1]}
    got = study.findings(m, {"channels": 4, "videos": 120, "usual": 5000, "escapes": [], "own": None}, [], None, None)
    assert [f["key"] for f in got] == ["few"]
