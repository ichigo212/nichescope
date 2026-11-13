import pytest

from nichescope.research import database, mapping, metrics, relevance, storage, topics

from .conftest import days_ago, video


def test_grade_thresholds():
    assert mapping.grade(0.5) == "close"
    assert mapping.grade(0.2) == "medium"
    assert mapping.grade(0.19) == "far"


def test_tally_counts_each_video_once_and_skips_own_channel():
    lists = [[{"channel_id": "A"}, {"channel_id": "A"}, {"channel_id": "ME"}],
             [{"channel_id": "A"}, {"channel_id": "B"}]]
    assert mapping.tally(lists, "ME") == {"A": 2, "B": 1}


def test_measure_usual_and_breakouts():
    videos = [video("new", 90000, 1)] + [video(f"v{i}", 1000, 5 + i) for i in range(10)] + [video("old", 9000, 400)]
    got = metrics.measure(videos)
    assert got["usual"] == 1000
    assert [v["id"] for v in got["breakouts"]] == ["new", "old"]
    assert got["breakout"] == 90.0


def test_measure_without_settled_videos_finds_no_breakouts():
    got = metrics.measure([video("a", 500, 1), video("b", 100, 2)])
    assert got["usual"] is None and got["breakouts"] == []


def test_relevance_by_words(sample_map):
    m = storage.load(sample_map["channel_id"])
    assert relevance.matches_niche(m, m["channels"]["UCbbbbbbbbbbbbbbbbbbbbbb"])
    assert not relevance.matches_niche(m, m["channels"]["UCcccccccccccccccccccccc"])
    assert relevance.matches_niche(m, {**m["channels"]["UCcccccccccccccccccccccc"], "added": True})


def test_measured_margin_overrides_words(sample_map):
    m = storage.load(sample_map["channel_id"])
    row = {**m["channels"]["UCbbbbbbbbbbbbbbbbbbbbbb"], "topic_margin": -0.05}
    assert not relevance.matches_niche(m, row)


def test_model_fit_wins_over_margin_and_words(sample_map):
    m = storage.load(sample_map["channel_id"])
    near, news = m["channels"]["UCbbbbbbbbbbbbbbbbbbbbbb"], m["channels"]["UCcccccccccccccccccccccc"]
    assert not relevance.matches_niche(m, {**near, "fit": "unrelated", "topic_margin": 0.2})
    assert relevance.matches_niche(m, {**news, "fit": "adjacent", "topic_margin": -0.1})
    assert not relevance.matches_niche(m, {**news, "fit": "unclear"})
    assert not relevance.matches_niche(m, {**near, "grade": "far", "fit": "unclear", "topic_margin": 0.3})
    assert relevance.matches_niche(m, {**near, "grade": "close", "fit": "unclear", "topic_margin": 0.3})
    assert relevance.matches_niche(m, {**news, "fit": "unrelated", "added": True})


def test_close_channels_are_kept_without_a_model(sample_map):
    m = storage.load(sample_map["channel_id"])
    row = {"title": "Somebody", "grade": "close", "topic_samples": [{"title": "Election night"}]}
    assert relevance.matches_niche(m, row)
    assert not relevance.matches_niche(m, {**row, "grade": "far"})
    assert relevance.matches_niche(m, {"title": "x", "grade": "far", "seen": ["Rain sounds for deep sleep"]})


def test_classify_writes_fit(sample_map, monkeypatch):
    m = storage.load(sample_map["channel_id"])
    asked = []

    def fake(parts, schema, light=False):
        asked.append(parts[0])
        return {"channels": [{"n": 1, "fit": "same"}, {"n": 2, "fit": "unrelated"}, {"n": 9, "fit": "same"}]}

    monkeypatch.setattr(relevance.ai, "available", lambda: True)
    monkeypatch.setattr(relevance.ai, "generate", fake)
    assert relevance.classify(m) == 2
    assert m["channels"]["UCbbbbbbbbbbbbbbbbbbbbbb"]["fit"] == "same"
    assert m["channels"]["UCcccccccccccccccccccccc"]["fit"] == "unrelated"
    assert "Election results tonight" in asked[0]
    assert relevance.classify(m) == 0
    assert [r["id"] for r in relevance.set_aside(m)] == ["UCcccccccccccccccccccccc"]


def test_recommended_titles_are_kept():
    lists = [[{"channel_id": "A", "title": "Rain"}, {"channel_id": "ME", "title": "Mine"}],
             [{"channel_id": "A", "title": "Rain"}, {"channel_id": "A", "title": "Storm"}]]
    rows = mapping._neighbours(lists, "ME")
    assert rows == {"A": {"appearances": 2, "coverage": 1.0, "grade": "close", "seen": ["Rain", "Storm"]}}


def test_competitor_names_match_loosely():
    assert mapping._same_name("Calm Rain Sounds", "calm rain sounds")
    assert mapping._same_name("Calm Rain Sounds TV", "Calm Rain Sounds")
    assert mapping._same_name("Kurzgesagt – In a Nutshell", "Kurzgesagt")
    assert not mapping._same_name("Rain", "Rainbow Six Siege Pro League")


def test_breakouts_only_from_relevant_channels(sample_map):
    m = storage.load(sample_map["channel_id"])
    rows = metrics.breakouts(m)
    assert [v["id"] for v in rows] == ["hit"]
    assert rows[0]["channel"] == "Storm Sleep"


def test_storage_upgrades_older_topic_fields(home, sample_map):
    m = storage.load(sample_map["channel_id"])
    m["topics"] = [{"at": days_ago(1), "topics": [{"series": "Thunder at night", "evidence": [], "confirmed": True}]}]
    storage.save(m)
    again = storage.load(m["channel_id"])
    t = again["topics"][0]["topics"][0]
    assert t["topic"] == "Thunder at night" and "series" not in t and "confirmed" not in t
    assert again["topics"][0]["id"] and again["topics"][0]["followups"] == []


def test_remove_and_restore_map(sample_map):
    kept = storage.remove(sample_map["channel_id"])
    assert storage.saved() == []
    assert storage.restore(kept) == sample_map["channel_id"]
    assert len(storage.saved()) == 1


def test_remove_channel_survives_save_and_restores(sample_map):
    cid = "UCbbbbbbbbbbbbbbbbbbbbbb"
    m = mapping.remove_channel(sample_map["channel_id"], cid)
    assert cid not in m["channels"]
    m["channels"][cid] = {"title": "back again"}
    storage.save(m)
    assert cid not in storage.load(m["channel_id"])["channels"]
    assert cid in mapping.restore_channel(m["channel_id"], cid)["channels"]


def test_store_queries(sample_map):
    database.import_maps()
    found = database.find_videos(sort="views", limit=5)
    assert found["total"] >= 1 and found["videos"][0]["id"] == "hit"
    assert database.find_videos(title_pattern="Rain * for sleep")["total"] >= 1
    assert database.find_videos(title_pattern="Thunder*")["total"] == 0
    channels = database.find_channels(near="Calm Rain", sort="closest")
    assert channels["channels"][0]["id"] == "UCbbbbbbbbbbbbbbbbbbbbbb"
    with pytest.raises(ValueError):
        database.find_videos(sort="loudness")
    with pytest.raises(ValueError):
        database.find_videos(title_regex="(")


def test_pattern_regex():
    assert database.pattern_regex("I * for * days") == r"^I\ .*\ for\ .*\ days$"
    assert database.pattern_regex("") is None


def test_points_to(sample_map):
    rows = database.points_to("UCbbbbbbbbbbbbbbbbbbbbbb")
    assert rows == [{"id": sample_map["channel_id"], "title": "Calm Rain", "real_views": None,
                     "coverage": 0.6, "maps": 1}]


def test_keep_requires_real_evidence(sample_map):
    m = storage.load(sample_map["channel_id"])
    raw = [{"topic": "Thunderstorm in a cabin", "why": "It has 20000 views. Viewers love cabins.",
            "evidence": ["hit", "made-up"], "titles": ["Cabin Storm", "cabin storm", "Night Rain"], "fit": 8,
            "reasons": {"proven": "a big hit", "risk": ""}},
           {"topic": "No proof", "why": "", "evidence": ["made-up"], "titles": ["x"]}]
    known = {v["id"]: v for v in metrics.breakouts(m)}
    kept = topics._keep(m, raw, known, set(), titles=3)
    assert len(kept) == 1
    t = kept[0]
    assert t["evidence"] == ["hit"]
    assert t["why"] == "Viewers love cabins."
    assert t["titles"] == ["Cabin Storm", "Night Rain"]
    assert t["reasons"] == {"proven": "a big hit"}
    assert t["expected_views"] == {"low": 2000, "high": 10000}


def test_settings_validation(sample_map):
    m = topics.update_settings(sample_map["channel_id"], topics=7, instructions="calm only", read_descriptions=False)
    assert topics.settings_of(m)["topics"] == 7
    assert topics.settings_of(m)["read_descriptions"] is False
    with pytest.raises(ValueError):
        topics.update_settings(sample_map["channel_id"], titles=11)


def test_marks(sample_map):
    m = topics.mark(sample_map["channel_id"], "topics", "Storm", "no")
    assert m["marks"]["topics"] == {"Storm": "no"}
    with pytest.raises(ValueError):
        topics.mark(sample_map["channel_id"], "topics", "Storm", "maybe")


def test_a_named_subject_is_searched(sample_map, monkeypatch):
    m = storage.load(sample_map["channel_id"])
    searched = []

    def fake_search(q, pages=1, **_):
        searched.append(q)
        return {"results": [
            {"id": "yt1", "title": "Rain on a tin roof cabin", "channel": "Roof Rain", "channel_id": "UCroof",
             "views": 50000, "age_days": 20, "seconds": 3600, "live": False, "snippet": "", "thumbnail": ""},
            {"id": "short", "title": "tin roof", "channel": "S", "channel_id": "UCs", "views": 9,
             "age_days": 1, "seconds": 40, "live": False}]}

    monkeypatch.setattr(topics.ai, "generate", lambda parts, schema, light=False: {
        "subject": "tin roof rain", "queries": ["tin roof rain sounds"]})
    monkeypatch.setattr(topics.web, "search", fake_search)
    idea = topics.idea_of(m, "ideas about rain on a tin roof please")
    assert idea == {"subject": "tin roof rain", "queries": ["tin roof rain sounds"]}
    rows, counts = topics.idea_videos(m, idea)
    assert searched == ["tin roof rain sounds"]
    assert [r["id"] for r in rows] == ["yt1"] and rows[0]["found"] == "youtube"
    assert counts["on_youtube"] == 1 and counts["subject"] == "tin roof rain"


def test_style_only_requests_search_nothing(sample_map, monkeypatch):
    m = storage.load(sample_map["channel_id"])
    monkeypatch.setattr(topics.ai, "generate", lambda parts, schema, light=False: {"subject": "", "queries": []})
    assert topics.idea_of(m, "shorter titles") is None
    assert topics.idea_of(m, "") is None


def test_judged_channels_are_on_the_niche_without_matching_words(sample_map):
    m = storage.load(sample_map["channel_id"])
    v = video("story", 9000, 4, title="The Duke's Second Wife", tags=())
    assert not relevance.on_topic(v, "Storm Sleep", m)
    assert relevance.on_topic(v, "Storm Sleep", m, {"fit": "same"})
    assert relevance.on_topic(v, "Storm Sleep", m, {"added": True})


def test_small_channels_judged_the_same_keep_real_breakouts():
    hit = {**video("big", 4000, 5), "outlier": 80.0}
    tiny = {**video("tiny", 300, 5), "outlier": 6.0}
    row = {"usual": 50, "breakouts": [hit, tiny]}
    assert metrics.channel_breakouts(row) == []
    assert metrics.channel_breakouts({**row, "fit": "same"}) == [hit]
    assert metrics.channel_breakouts({**row, "usual": 500}) == [hit, tiny]


def test_rescan_keeps_the_users_decisions():
    old = {"A": {"grade": "close", "added": True, "fit": "same"},
           "B": {"grade": "medium", "off": True},
           "C": {"grade": "medium", "promoted": 4, "via": "A", "step": 1}}
    fresh = {"A": {"grade": "far", "coverage": 0.1, "appearances": 1, "seen": []}}
    got = mapping._merge(old, fresh)
    assert got["A"]["grade"] == "close" and got["A"]["added"]
    assert got["B"]["off"]
    assert got["C"]["promoted"] == 4


def test_named_topics_need_the_name_in_their_evidence(sample_map, monkeypatch):
    m = storage.load(sample_map["channel_id"])
    known = {"hit": {**video("hit", 20000, 5, title="Rain over Blackwood Manor"), "outlier": 20.0},
             "other": {**video("other", 9000, 5, title="Soft rain"), "outlier": 9.0}}
    raw = [{"topic": "A night at Blackwood Manor", "evidence": ["other", "hit"], "titles": ["x"], "fit": 7,
            "name": "Blackwood Manor"},
           {"topic": "Rain sounds again", "evidence": ["other"], "titles": ["y"], "name": "Rain sounds"}]
    kept = topics._keep(m, raw, known, set(), titles=3)
    # The second names something the channel already made, so it is dropped.
    assert [t["topic"] for t in kept] == ["A night at Blackwood Manor"]
    assert kept[0]["evidence"] == ["hit"]
    def no_access(vid):
        raise RuntimeError("no key")

    monkeypatch.setattr("nichescope.youtube.data_api.comments", no_access)
    topics.confirm_names(kept, known)
    assert kept[0]["name"] == {"name": "Blackwood Manor", "source": "its title", "video": "hit"}


def test_unconfirmed_names_say_so(sample_map, monkeypatch):
    m = storage.load(sample_map["channel_id"])
    known = {"other": {**video("other", 9000, 5, title="Soft rain"), "outlier": 9.0, "channel_id": "UCx"}}
    kept = topics._keep(m, [{"topic": "Storm Keep", "evidence": ["other"], "titles": ["z"], "name": "Storm Keep"}],
                        known, set(), titles=3)
    monkeypatch.setattr("nichescope.youtube.data_api.comments",
                        lambda vid: [{"textDisplay": "loved storm keep!", "authorChannelId": {"value": "UCx"}}])
    topics.confirm_names(kept, known)
    assert kept[0]["name"]["source"] == "the channel's comment"


def test_openings_use_the_first_seconds_of_the_strongest_videos(monkeypatch):
    def fake(vid, language="en"):
        if vid == "none":
            raise LookupError("no captions")
        return {"segments": [{"start": 1.0, "text": f"{vid} opens strong"}, {"start": 55.0, "text": "much later"}]}

    monkeypatch.setattr(topics.captions, "transcript", fake)
    rows = [{"id": "a", "title": "A", "channel": "One", "outlier": 4.0},
            {"id": "none", "title": "N", "channel": "Two", "outlier": 9.0}]
    text = topics.openings(rows)
    assert "a opens strong" in text and "much later" not in text and "[Two]" not in text
    assert topics.openings([]) == ""


def test_topic_names_survive_a_reload(sample_map):
    m = storage.load(sample_map["channel_id"])
    named = {"name": "Storm Keep", "source": "its title", "video": "hit"}
    m["topics"] = [{"id": "r1", "at": days_ago(0), "topics": [
        {"topic": "A", "evidence": ["hit"], "name": named},
        {"topic": "B", "evidence": ["hit"], "name": "old plain name", "confirmed": True}]}]
    storage.save(m)
    got = storage.load(sample_map["channel_id"])["topics"][0]["topics"]
    assert got[0]["name"] == named
    assert "name" not in got[1] and "confirmed" not in got[1]


def test_a_video_read_twice_counts_once():
    videos = [video("hit", 20000, 5)] + [video(f"v{i}", 1000, 5 + i) for i in range(10)] + [video("hit", 20000, 5)]
    got = metrics.measure(videos)
    assert [v["id"] for v in got["breakouts"]] == ["hit"]
