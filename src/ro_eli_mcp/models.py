"""Pydantic v2 models for the Romanian Portal Legislativ SOAP API + ro-eli-mcp."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

DATASET_NOTE = (
    "The Romanian Portal Legislativ (legislatie.just.ro) is served via a SOAP API (Ministry of "
    "Justice). Search by title, free text, year and/or number; the full text is returned inline. "
    "Acts of the same number can exist across types (LEGE, DECRET, HOTARARE...), so disambiguate "
    "with tip_act. The API returns up to 10 results per page. Language: Romanian."
)

ELI_NOTE = (
    "Romania has no data.europa.eu ELI for this portal. eli_uri carries the canonical "
    "legislatie.just.ro document URL (the stable national identifier), which is also the "
    "source_url."
)


class _Tolerant(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class Act(_Tolerant):
    """A Romanian legal act (metadata)."""

    tip_act: str | None = None
    number: str | None = None
    year: int | None = None
    title: str | None = None
    date_in_force: str | None = None
    issuer: str | None = None
    publication: str | None = None

    # Citation contract (Art. 4 CONSTITUTION).
    eli_uri: str | None = None
    human_readable_citation: str | None = None
    source_url: str | None = None
    eli_note: str = ELI_NOTE
    dataset_note: str = DATASET_NOTE


class LawText(_Tolerant):
    """Result of ``ro_get_text`` (full text returned inline by the SOAP API)."""

    tip_act: str | None = None
    number: str | None = None
    year: int | None = None
    title: str | None = None
    eli_uri: str | None = None
    human_readable_citation: str | None = None
    source_url: str | None = None
    format: str = "text/plain"
    content: str | None = None
    byte_size: int | None = None
    eli_note: str = ELI_NOTE
    dataset_note: str = DATASET_NOTE


class SearchHit(_Tolerant):
    """A single act in a ``ro_search`` result (metadata only, no full text)."""

    tip_act: str | None = None
    number: str | None = None
    year: int | None = None
    title: str | None = None
    date_in_force: str | None = None
    issuer: str | None = None
    eli_uri: str | None = None
    human_readable_citation: str | None = None
    source_url: str | None = None


class SearchResult(_Tolerant):
    """Result of ``ro_search``."""

    page: int
    total: int
    items: list[SearchHit] = Field(default_factory=list)
    dataset_note: str = DATASET_NOTE
