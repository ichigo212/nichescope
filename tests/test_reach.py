import io
import zipfile

import pytest

from nichescope.research import own, reach

STUDIO = ("Content,Video title,Video publish time,Duration,Impressions,Impressions click-through rate (%),Views\n"
          "Total,,,,\"120,000\",4.1,9000\n"
          "abcdefghijk,First,\"Nov 1, 2026\",620,50000,6.2,4000\n"
          "ABCDEFGHIJK,Second,\"Nov 3, 2026\",700,70000,2.5,5000\n")


def test_studio_csv_is_read_and_totals_skipped():
    got = reach.parse(STUDIO.encode("utf-8-sig"))
    assert got == {"abcdefghijk": {"impressions": 50000, "ctr": 6.2, "views": 4000},
                   "ABCDEFGHIJK": {"impressions": 70000, "ctr": 2.5, "views": 5000}}


def test_studio_zip_is_read():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Totals.csv", "Date,Views\n2026-11-01,5\n")
        z.writestr("Table data.csv", STUDIO)
    assert len(reach.parse(buf.getvalue())) == 2


def test_other_files_are_refused():
    with pytest.raises(reach.ReachFileError):
        reach.parse(b"name,score\nx,1\n")


def test_four_way_verdicts_with_click_through():
    rows = [{"avg_view_pct": 50, "period_views": 900, "ctr": 8.0, "impressions": 5000},
            {"avg_view_pct": 50, "period_views": 900, "ctr": 2.0, "impressions": 5000},
            {"avg_view_pct": 20, "period_views": 900, "ctr": 8.0, "impressions": 5000},
            {"avg_view_pct": 20, "period_views": 900, "ctr": 2.0, "impressions": 5000},
            {"avg_view_pct": 50, "period_views": 900}]
    medians = own.diagnose(rows)
    assert medians == {"retention": 50, "ctr": 5.0}
    assert [r["verdict"] for r in rows] == ["working", "packaging", "content", "weak", "holding"]
