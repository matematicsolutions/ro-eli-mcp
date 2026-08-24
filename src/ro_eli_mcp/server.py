"""FastMCP entry point - Romanian Portal Legislativ (SOAP) tools.

Run:

    python -m ro_eli_mcp.server

Configuration via env:

- ``RO_ELI_CACHE_DIR`` (default ``~/.matematic/cache/ro-eli``)
- ``RO_ELI_AUDIT_DIR`` (default ``~/.matematic/audit``)
- ``RO_ELI_ENDPOINT`` (default ``https://legislatie.just.ro/apiws/FreeWebService.svc/SOAP``)
"""

from __future__ import annotations

import os

import httpx
from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .audit import AuditLogger, hash_input, timer
from .citations import build_record
from .client import DEFAULT_ENDPOINT, RoSoapClient, RoSoapError
from .models import Act, LawText, SearchHit, SearchResult
from .coverage import Coverage, build_coverage

INSTRUCTIONS = """\
This MCP server exposes the Romanian Portal Legislativ (legislatie.just.ro), the Ministry of Justice legislative database, through its public SOAP API. It searches legislation and returns metadata and full text. Every response carries a stable `eli_uri`, a `human_readable_citation` and a `source_url` (the citation contract).

## Call order

1. `ro_search` - find acts by `title`, free `text`, `year` and/or `number` (e.g. `year=2018, number=190`). Returns up to 10 hits per `page`, each with the act type (`tip_act`), number, title and `eli_uri`. This is the discovery step.
2. `ro_get_act` - metadata for a specific act by `number` + `year`, disambiguated by `tip_act` (e.g. "LEGE", "DECRET", "HOTARARE") when several types share a number.
3. `ro_get_text` - the full Romanian text of an act by `number` + `year` (+ `tip_act`).

## Hard constraints

- **Disambiguate by type** - the same `number`/`year` can exist across act types (LEGE, DECRET, HOTARARE, ORDONANTA...). When more than one matches, pass `tip_act`. Tools report `total_matches` so you know there were others.
- **ELI is national, not data.europa.eu** - Romania has no `data.europa.eu` ELI for this portal; `eli_uri` is the canonical legislatie.just.ro document URL. Relay the `eli_note`. Do not invent it.
- **Search caps at 10 per page** - paginate with `page` for more results.
- **Every response has `human_readable_citation` + `source_url`** - cite both to the user.
- **Audit log JSONL** - every tool call appends to `~/.matematic/audit/ro-eli-mcp.jsonl`.

## Error iteration

Tools return a structured error with a `[code]` prefix:
- `invalid_arg` - a parameter is missing or invalid (e.g. no search criterion, bad year, page < 1).
- `not_found` - no act matches those coordinates.
- `upstream_error` - a SOAP API error (HTTP, timeout, token failure, malformed XML). Retry once before surfacing.

## Response style

- Cite as `human_readable_citation` with the URL: "LEGE nr. 190/2018, https://legislatie.just.ro/Public/DetaliiDocument/...".
- NEVER invent a number, a year, an act type or a URL - take each from the tool output.
"""


class ToolError(Exception):
    """Structured error for ro-eli MCP tools - visible to the LLM with a [code] prefix."""

    VALID_CODES = frozenset({"invalid_arg", "not_found", "upstream_error"})

    def __init__(self, code: str, message: str):
        if code not in self.VALID_CODES:
            raise ValueError(f"Unknown ToolError code: {code}. Valid: {sorted(self.VALID_CODES)}")
        self.code = code
        super().__init__(f"[{code}] {message}")


READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    idempotentHint=True,
    destructiveHint=False,
    openWorldHint=True,
)

mcp: FastMCP = FastMCP(name="ro-eli-mcp", instructions=INSTRUCTIONS)


def _endpoint() -> str:
    return os.environ.get("RO_ELI_ENDPOINT", DEFAULT_ENDPOINT)


def _audit() -> AuditLogger:
    return AuditLogger()


def _map_upstream(exc: Exception) -> Exception:
    if isinstance(exc, RoSoapError):
        return ToolError("upstream_error", f"Romanian SOAP API: {exc}")
    if isinstance(exc, (httpx.HTTPStatusError, httpx.TransportError, httpx.TimeoutException)):
        return ToolError("upstream_error", f"legislatie.just.ro error: {type(exc).__name__}: {exc}")
    return exc


def _check_year(year: int | None) -> None:
    if year is not None and not 1850 <= year <= 2100:
        raise ToolError("invalid_arg", f"year={year} is out of range (1850..2100).")


def _match_type(records: list[dict], tip_act: str | None) -> list[dict]:
    if not tip_act:
        return records
    t = tip_act.strip().upper()
    return [r for r in records if (r.get("TipAct") or "").strip().upper() == t]


# ---------------------------------------------------------------------------
# ro_search
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def ro_search(
    title: str | None = None,
    text: str | None = None,
    year: int | None = None,
    number: int | None = None,
    page: int = 1,
) -> SearchResult:
    """Search Romanian legislation.

    Provide at least one of ``title`` / ``text`` / ``year`` / ``number``.

    Args:
        title: words matched against the act title.
        text: words matched against the full text.
        year: publication/in-force year, e.g. ``2018``.
        number: act number, e.g. ``190``.
        page: 1-based page (the API returns up to 10 hits per page).

    Returns:
        ``SearchResult`` with ``items: list[SearchHit]`` (metadata only, no full text).
    """
    audit = _audit()
    if not any([title, text, year, number]):
        raise ToolError("invalid_arg", "Provide at least one of title, text, year, number.")
    _check_year(year)
    if page < 1:
        raise ToolError("invalid_arg", "page must be >= 1.")
    if number is not None and number <= 0:
        raise ToolError("invalid_arg", "number must be positive.")
    input_hash = hash_input({"title": title, "text": text, "year": year, "number": number, "page": page})

    with timer() as t:
        try:
            async with RoSoapClient(endpoint=_endpoint()) as client:
                records = await client.search(
                    title=title, text=text, year=year, number=number, page=page
                )
        except Exception as exc:
            audit.log(tool="ro_search", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    items = []
    for raw in records:
        rec = build_record(raw)
        items.append(SearchHit(
            tip_act=rec["tip_act"], number=rec["number"], year=rec["year"], title=rec["title"],
            date_in_force=rec["date_in_force"], issuer=rec["issuer"], eli_uri=rec["eli_uri"],
            human_readable_citation=rec["human_readable_citation"], source_url=rec["source_url"],
        ))
    result = SearchResult(page=page, total=len(items), items=items)
    audit.log(tool="ro_search", input_hash=input_hash, output_count_or_size=len(items),
              duration_ms=t.duration_ms, status="ok")
    return result


# ---------------------------------------------------------------------------
# ro_get_act
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def ro_get_act(number: int, year: int, tip_act: str | None = None) -> Act:
    """Fetch Romanian act metadata by number + year (disambiguate with tip_act).

    Args:
        number: act number, e.g. ``190``.
        year: year, e.g. ``2018``.
        tip_act: act type to disambiguate (e.g. ``"LEGE"``), when several types share a number.

    Returns:
        ``Act`` with ``eli_uri``, ``human_readable_citation``, ``source_url``. ``total_matches``
        reports how many acts shared the number/year.
    """
    audit = _audit()
    _check_year(year)
    if number <= 0:
        raise ToolError("invalid_arg", "number must be positive.")
    input_hash = hash_input({"number": number, "year": year, "tip_act": tip_act})

    with timer() as t:
        try:
            async with RoSoapClient(endpoint=_endpoint()) as client:
                records = await client.search(year=year, number=number)
        except Exception as exc:
            audit.log(tool="ro_get_act", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    matched = _match_type(records, tip_act)
    if not matched:
        raise ToolError("not_found", f"No act number={number}, year={year}"
                        + (f", tip_act={tip_act!r}" if tip_act else "") + " in Portal Legislativ.")
    rec = build_record(matched[0])
    rec["total_matches"] = len(matched)
    act = Act.model_validate(rec)
    audit.log(tool="ro_get_act", input_hash=input_hash, output_count_or_size=1,
              duration_ms=t.duration_ms, status="ok")
    return act


# ---------------------------------------------------------------------------
# ro_get_text
@mcp.tool(annotations=READ_ONLY)
async def ro_coverage() -> Coverage:
    """Declare what this connector covers, how it is sourced, and what it does NOT cover.

    Call this before telling a user that the law "does not contain" something, and whenever
    a search comes back empty: the absence may be a gap in this connector rather than in the
    law. Every gap carries a fallback saying where to look instead.

    Returns:
        ``Coverage`` with families, an as-of note, and a non-empty list of known gaps.
    """
    return build_coverage()


# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def ro_get_text(number: int, year: int, tip_act: str | None = None) -> LawText:
    """Fetch the full Romanian text of an act by number + year (disambiguate with tip_act).

    Args:
        number: act number, e.g. ``190``.
        year: year, e.g. ``2018``.
        tip_act: act type to disambiguate (e.g. ``"LEGE"``).

    Returns:
        ``LawText`` with the citation contract and ``content`` (full text, returned inline by the
        SOAP API).
    """
    audit = _audit()
    _check_year(year)
    if number <= 0:
        raise ToolError("invalid_arg", "number must be positive.")
    input_hash = hash_input({"number": number, "year": year, "tip_act": tip_act})

    with timer() as t:
        try:
            async with RoSoapClient(endpoint=_endpoint()) as client:
                records = await client.search(year=year, number=number)
        except Exception as exc:
            audit.log(tool="ro_get_text", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    matched = _match_type(records, tip_act)
    if not matched:
        raise ToolError("not_found", f"No act number={number}, year={year}"
                        + (f", tip_act={tip_act!r}" if tip_act else "") + " in Portal Legislativ.")
    rec = build_record(matched[0], include_text=True)
    text = rec.get("text") or ""
    if not text:
        raise ToolError("not_found", f"Act {number}/{year} returned no text.")
    result = LawText(
        tip_act=rec["tip_act"],
        number=rec["number"],
        year=rec["year"],
        title=rec["title"],
        eli_uri=rec["eli_uri"],
        human_readable_citation=rec["human_readable_citation"],
        source_url=rec["source_url"],
        content=text,
        byte_size=len(text.encode("utf-8")),
    )
    audit.log(tool="ro_get_text", input_hash=input_hash, output_count_or_size=result.byte_size or 0,
              duration_ms=t.duration_ms, status="ok")
    return result


def main() -> None:
    """Run the MCP server over stdio (default for Claude Code)."""
    mcp.run()


if __name__ == "__main__":
    main()
