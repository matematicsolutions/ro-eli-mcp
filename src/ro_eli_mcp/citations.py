"""Romanian Portal Legislativ (SOAP) parsing + citation helpers.

The Romanian Ministry of Justice publishes legislation through a SOAP API
(legislatie.just.ro/apiws). Each ``Legi`` record carries the full text inline (``Text``) plus
metadata (``TipAct``, ``Numar``, ``Titlu``, ``DataVigoare``, ``Emitent``, ``Publicatie``,
``LinkHtml``).

Romania has no data.europa.eu ELI for this portal, so ``eli_uri`` carries the canonical
legislatie.just.ro document URL (``LinkHtml``), the stable national identifier. The connector
flags this via ``eli_note``.

Citation contract:
- ``eli_uri``: the legislatie.just.ro document URL. NEVER invented - taken from the record.
- ``human_readable_citation``: the Romanian convention, e.g. "LEGE nr. 190/2018".
- ``source_url``: the same legislatie.just.ro page.
"""

from __future__ import annotations

import html as _html
import re
from typing import Any


def clean_text(text: str | None) -> str:
    """Decode entities, strip any markup, normalise whitespace (keep paragraph breaks)."""
    if not text:
        return ""
    text = _html.unescape(text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|tr)>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\r\n", "\n", text)
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.split("\n")]
    text = "\n".join(ln for ln in lines if ln)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _norm(value: str | None) -> str | None:
    if value is None:
        return None
    s = re.sub(r"\s+", " ", _html.unescape(value)).strip()
    return s or None


def _https(url: str | None) -> str | None:
    if not url:
        return None
    return re.sub(r"^http://", "https://", url.strip())


def build_record(raw: dict[str, Any], *, include_text: bool = False) -> dict[str, Any]:
    """Build a citation-bearing record from a ``Legi`` SOAP element dict."""
    tip_act = _norm(raw.get("TipAct"))
    numar = _norm(raw.get("Numar"))
    titlu = _norm(raw.get("Titlu"))
    date = _norm(raw.get("DataVigoare"))
    emitent = _norm(raw.get("Emitent"))
    publicatie = _norm(raw.get("Publicatie"))
    link = _https(raw.get("LinkHtml"))

    year = date[:4] if date and len(date) >= 4 and date[:4].isdigit() else None

    parts = []
    if tip_act:
        parts.append(tip_act)
    if numar:
        parts.append(f"nr. {numar}")
    if numar and year:
        parts[-1] = f"nr. {numar}/{year}"
    human = " ".join(parts) if parts else (titlu or link)

    record: dict[str, Any] = {
        "tip_act": tip_act,
        "number": numar,
        "year": int(year) if year else None,
        "title": titlu,
        "date_in_force": date,
        "issuer": emitent,
        "publication": publicatie,
        "eli_uri": link,
        "human_readable_citation": human,
        "source_url": link,
    }
    if include_text:
        record["text"] = clean_text(raw.get("Text"))
    return record
