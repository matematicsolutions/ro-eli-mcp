# DISCOVERY - ro-eli-mcp (Romania / Portal Legislativ)

Date: 2026-06-29. Source selection driven by Legal Data Hunter coverage data
(`worldwidelaw/legal-sources`): Romania's `RO/LegislationDatabase` is a SOAP API, confirmed live.

## Why Romania, why SOAP

The Romanian Ministry of Justice exposes the Portal Legislativ through a public SOAP API
(`legislatie.just.ro/apiws`). Unlike the SPA-migrated portals of several EU members, a SOAP API is
a stable server-side contract - it returns the full act text inline. A token is obtained via
`GetToken` (no registration), then passed to `Search`.

## Endpoint (keyless; token via GetToken)

- SOAP endpoint: `https://legislatie.just.ro/apiws/FreeWebService.svc/SOAP`
- WSDL: `https://legislatie.just.ro/apiws/FreeWebService.svc?wsdl`
- Namespaces: envelope `schemas.xmlsoap.org/soap/envelope/`, service `tempuri.org/`, data
  `schemas.datacontract.org/2004/07/FreeWebService`.

### GetToken

POST `<GetToken xmlns="http://tempuri.org/"/>`, SOAPAction `...IFreeWebService/GetToken` ->
response carries `GetTokenResult` (the token string).

### Search

POST a `SearchModel` (`NumarPagina`, `RezultatePagina`, `SearchAn`, `SearchNumar`, `SearchText`,
`SearchTitlu`) + `tokenKey`, SOAPAction `...IFreeWebService/Search`. The response carries `Legi`
elements with children: `TipAct`, `Numar`, `Titlu`, `Text` (full text inline), `DataVigoare`,
`Emitent`, `Publicatie`, `LinkHtml`.

- The API returns **up to 10 results per page** regardless of `RezultatePagina`.
- `SearchAn` behaves as a "start-from-year" offset on full pagination, but combined with
  `SearchNumar` it returns the acts of that number/year (across types).

## Probed

`Search(year=2018, number=190)` returns 5 `Legi` of different `TipAct` (DECRET, LEGE, ...) all
numbered 190 in 2018 - confirming that `number`/`year` is not unique and `tip_act` is needed to
disambiguate. `LinkHtml` is `http://legislatie.just.ro/Public/DetaliiDocument/{internal-id}`.

## Citation contract (Art. 4)

- `eli_uri` = the record's `LinkHtml`, upgraded to https (no `data.europa.eu` ELI exists).
- `human_readable_citation` = "{TipAct} nr. {Numar}/{year}" (year from `DataVigoare`).
- `source_url` = the same `legislatie.just.ro` document URL.

## Tools (MVP)

- `ro_search(title?, text?, year?, number?, page)` - metadata-only hits (full text stripped).
- `ro_get_act(number, year, tip_act?)` - metadata of the matching act (`total_matches` reported).
- `ro_get_text(number, year, tip_act?)` - the full text the API returns inline.

## Deficiencies flagged (per WM's "some connectors may be deficient" steer)

- **National identifier, not European ELI** - the document URL stands in for the ELI.
- **Non-unique coordinates** - the same number/year spans act types; `tip_act` disambiguates.
- **10-result page cap** - large result sets need pagination.

## Deferred

- **Case law** - ICCJ / Constitutional Court (separate sources).
- **Consolidated-version history** - the API returns a document's current text; version history is
  not exposed as a tool here.

## Licence / re-use

Romanian legislation is public domain; the Portal Legislativ SOAP API is public and keyless
(token via `GetToken`, no registration). Read-only relay with attribution + `source_url`.
Distribution as a public connector is in line with the keyless tier.
