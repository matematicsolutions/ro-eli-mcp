# Constitution of ro-eli-mcp

Version: 0.1.0
Date: 2026-06-29
Licence: Apache-2.0

`ro-eli-mcp` is an MCP server for the Romanian Portal Legislativ (`legislatie.just.ro`) SOAP API.
It searches legislation and fetches full text with verifiable citations. Case law is not in this
MVP.

The 4 principles below are inherited from the `eu-legal-mcp` line Constitution (Article IV).

---

## Art. 1. Public data only

The Portal Legislativ SOAP API is the official, public channel of the Romanian Ministry of Justice
(public domain, keyless; a token is obtained via `GetToken` without registration). The server is
read-only (Search only) and sends nothing beyond the requested search criteria.

## Art. 2. Mandatory audit log

Every tool call MUST append one JSON line to `~/.matematic/audit/ro-eli-mcp.jsonl`
(ts / tool / input_hash SHA-256 / output_count_or_size / duration_ms / status). Inability to write =
the tool returns an error, it does not silently skip.

## Art. 3. Vendor neutrality

No tool hardcodes an LLM provider, assumes a model, or adds commercial telemetry. The server talks
only to `legislatie.just.ro` and the local filesystem. Authentication: a keyless `GetToken` call;
own backoff + cache.

## Art. 4. ELI citations and a human-readable citation are mandatory

Every response MUST carry three fields:
- `eli_uri`: the canonical `legislatie.just.ro` document URL (from the record's `LinkHtml`). NEVER
  invented. Romania has no `data.europa.eu` ELI for this portal, so this national URL is the stable
  identifier - every response carries an `eli_note`.
- `human_readable_citation`: the Romanian convention (e.g. "LEGE nr. 190/2018").
- `source_url`: the same `legislatie.just.ro` page.

---

## Open points

1. **National vs European ELI** - the portal exposes no `data.europa.eu` ELI; the document URL is
   the stable identifier. Flagged via `eli_note`.
2. **Disambiguation** - the same number/year exists across act types; `tip_act` disambiguates, and
   tools report `total_matches`.
3. **Pagination** - the SOAP API caps results at 10 per page; `ro_search` exposes `page`.
4. **Case law** - Romanian court decisions (ICCJ, Constitutional Court) are a later feature.

## Ewolucja konstytucji

Changes to art. 1-4 follow SEMVER + an entry in `CHANGELOG.md` + a `pyproject.toml` bump.

First version: 2026-06-29. Author: Wieslaw Mazur / MateMatic.
