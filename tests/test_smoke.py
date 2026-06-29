"""Smoke tests - require internet, hit the live Romanian Portal Legislativ SOAP API.

Run manually:

    pytest tests/test_smoke.py -v
"""

from __future__ import annotations

import pytest

from ro_eli_mcp.server import ro_get_act, ro_get_text, ro_search

# Legea nr. 190/2018 - Romania's GDPR implementation law.
NUMBER, YEAR = 190, 2018


@pytest.mark.asyncio
async def test_smoke_search() -> None:
    res = await ro_search(year=YEAR, number=NUMBER)
    assert res.total >= 1
    for h in res.items:
        assert h.number == "190"
        assert h.eli_uri and h.eli_uri.startswith("https://legislatie.just.ro/")
        assert h.human_readable_citation


@pytest.mark.asyncio
async def test_smoke_get_act_law() -> None:
    act = await ro_get_act(NUMBER, YEAR, tip_act="LEGE")
    assert act.tip_act == "LEGE"
    assert act.number == "190"
    assert act.year == 2018
    assert act.eli_uri and act.eli_uri.startswith("https://legislatie.just.ro/")
    assert act.human_readable_citation.endswith("190/2018")


@pytest.mark.asyncio
async def test_smoke_get_text_law() -> None:
    text = await ro_get_text(NUMBER, YEAR, tip_act="LEGE")
    assert text.tip_act == "LEGE"
    assert text.content and len(text.content) > 500
    assert text.byte_size and text.byte_size > 500
    assert text.eli_uri and text.eli_uri.startswith("https://legislatie.just.ro/")
