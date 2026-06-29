"""Offline parse tests - SOAP Legi parsing + build_record against a committed fixture."""

from __future__ import annotations

from pathlib import Path

from ro_eli_mcp.citations import build_record, clean_text
from ro_eli_mcp.client import parse_legi_records

FIX = Path(__file__).parent / "fixtures"


def _content() -> bytes:
    return (FIX / "search_2018_190.xml").read_bytes()


def test_parse_legi_records():
    records = parse_legi_records(_content())
    assert len(records) >= 1
    r0 = records[0]
    assert "TipAct" in r0 and "Numar" in r0 and "LinkHtml" in r0
    assert r0["Numar"] == "190"


def test_build_record_citation_and_eli():
    records = parse_legi_records(_content())
    rec = build_record(records[0])
    assert rec["number"] == "190"
    assert rec["year"] == 2018
    assert rec["tip_act"]
    assert rec["eli_uri"].startswith("https://legislatie.just.ro/")  # http upgraded to https
    assert rec["source_url"] == rec["eli_uri"]
    assert rec["human_readable_citation"].endswith("190/2018")


def test_build_record_includes_text_when_asked():
    records = parse_legi_records(_content())
    rec = build_record(records[0], include_text=True)
    assert "text" in rec and len(rec["text"]) > 50


def test_clean_text():
    assert clean_text("<p>a&amp;b</p><br>c") == "a&b\nc"
    assert clean_text(None) == ""
