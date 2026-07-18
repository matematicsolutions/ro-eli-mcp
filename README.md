# ro-eli-mcp

<!-- mcp-name: io.github.matematicsolutions/ro-eli-mcp -->

An MCP server for the Romanian **Portal Legislativ** (`legislatie.just.ro`), the Ministry of
Justice legislative database, through its public **SOAP API**. It searches Romanian legislation
and returns metadata and full text, with verifiable citations.

Part of the MateMatic `eu-legal-mcp` production line - after PL, DE, AT, ES, FI, IE, NL, SE, FR,
LU, DK, CZ, HR, LT and SK. Same citation contract, Portal Legislativ source. This connector talks
SOAP (a token obtained via `GetToken`, no registration, then `Search`).

> **Scope.** This MVP searches acts by title, free text, year and number, and returns the full
> text the API provides inline. The same number can exist across act types (LEGE, DECRET,
> HOTARARE...), so a `tip_act` disambiguates. The API returns up to 10 results per page. Language:
> Romanian. Every response carries a `dataset_note`.
>
> **ELI is national, not data.europa.eu.** Romania has no `data.europa.eu` ELI for this portal.
> `eli_uri` carries the canonical `legislatie.just.ro` document URL (the stable national
> identifier), which is also the `source_url`. Every response carries an `eli_note`.

## The tools

| Tool | What it does |
|---|---|
| `ro_search` | Search acts by title, text, year and/or number (metadata only). |
| `ro_get_act` | Metadata for an act by number + year (+ `tip_act` to disambiguate). |
| `ro_get_text` | Full text of an act by number + year (+ `tip_act`). |

Every response carries the contract: `eli_uri` (the `legislatie.just.ro` URL),
`human_readable_citation` (e.g. `LEGE nr. 190/2018`), and `source_url`.

## Install

Run it with no install step (once published to PyPI):

```bash
uvx ro-eli-mcp
```

Or from source:

```bash
cd ro-eli-mcp
pip install -e .
```

## Configure (Claude Code / any MCP client)

```json
{
  "mcpServers": {
    "ro-eli-mcp": { "command": "ro-eli-mcp" }
  }
}
```

### Windows 11 ze Smart App Control

Smart App Control blokuje niepodpisane pliki wykonywalne, a `uvx.exe`, `pip.exe`
i generowany przy instalacji `ro-eli-mcp.exe` podpisane nie sa. `python.exe`
z python.org jest podpisany przez Python Software Foundation, wiec uruchomienie
przez modul omija blokade:

```bash
python -m pip install ro-eli-mcp
python -m ro_eli_mcp
```

```json
{ "mcpServers": { "ro-eli-mcp": { "command": "python", "args": ["-m", "ro_eli_mcp"] } } }
```

Nie wylaczaj Smart App Control, zeby to obejsc - wylaczenia nie da sie cofnac
bez ponownej instalacji systemu.

Environment:

- `RO_ELI_ENDPOINT` - default `https://legislatie.just.ro/apiws/FreeWebService.svc/SOAP`
- `RO_ELI_CACHE_DIR` - default `~/.matematic/cache/ro-eli`
- `RO_ELI_AUDIT_DIR` - default `~/.matematic/audit`

No API key. The token is obtained via `GetToken` automatically (no registration).

## Governance

- **Public data only** - read-only against the Portal Legislativ; no client data leaves the machine.
- **Audit log** - every tool call appends one JSON line to `~/.matematic/audit/ro-eli-mcp.jsonl`.
- **Vendor-neutral** - talks only to `legislatie.just.ro`; no LLM provider, no telemetry.
- **Verifiable citations** - every response is independently checkable via `source_url`.

See `CONSTITUTION.md` and `DISCOVERY.md`.

## Tests

```bash
pip install -e ".[dev]"
pytest tests/test_instructions_drift.py tests/test_parse.py -v   # offline
pytest tests/test_smoke.py -v                                    # hits the live SOAP API
```

## Licence

Apache-2.0. © Matematic Solutions / Wieslaw Mazur. Romanian legislation is public domain; relayed
read-only with attribution and a `source_url`.
