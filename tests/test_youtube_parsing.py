import base64
import json

import pytest

from nichescope.youtube import captions, quota, web


def page(data: dict) -> str:
    return f"<html><script>var ytInitialData = {json.dumps(data)};</script></html>"


def test_parse_up_next_reads_both_card_formats():
    data = {"contents": {"twoColumnWatchNextResults": {"secondaryResults": {"results": [
        {"lockupViewModel": {"contentType": "LOCKUP_CONTENT_TYPE_VIDEO", "contentId": "vid00000001",
                             "metadata": {"lockupMetadataViewModel": {"title": {"content": "First"}}},
                             "owner": {"browseEndpoint": {"browseId": "UC1111111111111111111111"}}}},
        {"lockupViewModel": {"contentType": "LOCKUP_CONTENT_TYPE_PLAYLIST", "contentId": "PLx"}},
        {"compactVideoRenderer": {"videoId": "vid00000002", "title": {"simpleText": "Second"},
                                  "byline": {"browseEndpoint": {"browseId": "UC2222222222222222222222"}}}},
    ]}}}}
    rows = web.parse_up_next(page(data))
    assert [(r["video_id"], r["channel_id"]) for r in rows] == [
        ("vid00000001", "UC1111111111111111111111"), ("vid00000002", "UC2222222222222222222222")]


def test_parse_up_next_without_data_is_none():
    assert web.parse_up_next("<html>consent</html>") is None


@pytest.mark.parametrize("text,expected", [
    ("219,559 views", 219559), ("1.2M views", 1_200_000), ("3K views", 3000), ("No views", 0), ("", None)])
def test_parse_count(text, expected):
    assert web.parse_count(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("3 weeks ago", 21), ("Streamed 2 days ago", 2), ("1 year ago", 365), ("nothing", None)])
def test_parse_age(text, expected):
    assert web.parse_age(text) == expected


def test_parse_clock():
    assert web.parse_clock("4:40:21") == 4 * 3600 + 40 * 60 + 21
    assert web.parse_clock("12:05") == 725


def test_search_filter_encodes_video_type_and_sort():
    raw = base64.urlsafe_b64decode(web._search_filter("views", "week", "long", "videos"))
    assert raw[:2] == bytes([0x08, 3])
    assert bytes([0x08, 3, 0x10, 1, 0x18, 2]) in raw


def test_search_rejects_bad_options():
    with pytest.raises(ValueError):
        web.search("rain sounds", sort="loudest")
    with pytest.raises(ValueError):
        web.search("x")


@pytest.mark.parametrize("text", ["dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=1",
                                  "https://youtu.be/dQw4w9WgXcQ", "https://youtube.com/shorts/dQw4w9WgXcQ"])
def test_video_id(text):
    assert web.video_id(text) == "dQw4w9WgXcQ"


def test_video_id_rejects_other_text():
    with pytest.raises(ValueError):
        web.video_id("not a video")


def test_parse_srt_removes_rolling_repeats():
    raw = ("1\n00:00:00,000 --> 00:00:02,000\nhello there\n\n"
           "2\n00:00:02,000 --> 00:00:04,000\nhello there general\n\n"
           "3\n00:00:04,000 --> 00:00:06,000\n<c>kenobi</c>\n")
    assert captions.parse_srt(raw) == [{"start": 0.0, "text": "hello there"},
                                       {"start": 2.0, "text": "general"},
                                       {"start": 4.0, "text": "kenobi"}]


def test_quota_spend_and_left():
    assert quota.left() == 10_000
    quota.spend(25)
    assert quota.left() == 9_975
