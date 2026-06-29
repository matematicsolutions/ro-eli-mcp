"""Async httpx client for the Romanian Portal Legislativ SOAP API (legislatie.just.ro/apiws).

Keyless: a token is obtained via the GetToken SOAP call (no registration), then passed to Search.
Search returns up to 10 ``Legi`` records per page, full text inline. We keep our own backoff +
cache and hand-craft the SOAP envelopes (no third-party SOAP dependency).
"""

from __future__ import annotations

import html as _html
from typing import Any
from xml.etree import ElementTree as ET

import anyio
import httpx

from .cache import HttpCache

DEFAULT_ENDPOINT = "https://legislatie.just.ro/apiws/FreeWebService.svc/SOAP"
SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
SERVICE_NS = "http://tempuri.org/"
DATA_NS = "http://schemas.datacontract.org/2004/07/FreeWebService"
DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=15.0)
USER_AGENT = "ro-eli-mcp/0.1.0 (+https://github.com/matematicsolutions/ro-eli-mcp)"

_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
_MAX_ATTEMPTS = 3
API_PAGE_SIZE = 10  # the API caps results at 10 per page


class RoSoapError(RuntimeError):
    """Raised when the SOAP API cannot be used (e.g. token could not be obtained)."""


def parse_legi_records(content: bytes) -> list[dict[str, Any]]:
    """Parse the ``Legi`` records out of a SOAP Search response (offline-testable)."""
    root = ET.fromstring(content)
    records: list[dict[str, Any]] = []
    for legi in root.iter():
        if legi.tag.endswith("Legi"):
            rec: dict[str, Any] = {}
            for child in legi:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                rec[tag] = child.text or ""
            if rec:
                records.append(rec)
    return records


class RoSoapClient:
    """Async SOAP client. Use as ``async with RoSoapClient() as c: ...``."""

    def __init__(
        self,
        endpoint: str = DEFAULT_ENDPOINT,
        cache: HttpCache | None = None,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
    ) -> None:
        self.endpoint = endpoint
        self._cache = cache or HttpCache()
        self._token: str | None = None
        self._http = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Content-Type": "text/xml; charset=utf-8"},
        )

    async def __aenter__(self) -> RoSoapClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()
        self._cache.close()

    async def _post(self, envelope: str, action: str) -> bytes:
        headers = {"SOAPAction": f"{SERVICE_NS}IFreeWebService/{action}"}
        last_exc: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                resp = await self._http.post(
                    self.endpoint, content=envelope.encode("utf-8"), headers=headers
                )
                resp.raise_for_status()
                return resp.content
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code not in _RETRY_STATUS or attempt == _MAX_ATTEMPTS - 1:
                    raise
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt == _MAX_ATTEMPTS - 1:
                    raise
            await anyio.sleep(0.5 * (2**attempt))
        assert last_exc is not None
        raise last_exc

    async def get_token(self) -> str:
        if self._token:
            return self._token
        envelope = (
            f'<?xml version="1.0" encoding="utf-8"?>'
            f'<soap:Envelope xmlns:soap="{SOAP_NS}"><soap:Body>'
            f'<GetToken xmlns="{SERVICE_NS}"/></soap:Body></soap:Envelope>'
        )
        content = await self._post(envelope, "GetToken")
        root = ET.fromstring(content)
        for elem in root.iter():
            if elem.tag.endswith("GetTokenResult") and elem.text:
                self._token = elem.text
                return self._token
        raise RoSoapError("Could not obtain a token from the Romanian SOAP API.")

    @staticmethod
    def _field(value: str | None, tag: str) -> str:
        if value:
            return f"<free:{tag}>{_html.escape(value)}</free:{tag}>"
        return f"<free:{tag}/>"

    async def search(
        self,
        *,
        title: str | None = None,
        text: str | None = None,
        year: int | None = None,
        number: int | None = None,
        page: int = 1,
        results_per_page: int = API_PAGE_SIZE,
    ) -> list[dict[str, Any]]:
        """Execute a SOAP Search and return the list of ``Legi`` records as dicts."""
        token = await self.get_token()
        model = (
            f"<free:NumarPagina>{int(page)}</free:NumarPagina>"
            f"<free:RezultatePagina>{int(results_per_page)}</free:RezultatePagina>"
            f"{self._field(str(year) if year else None, 'SearchAn')}"
            f"{self._field(str(number) if number else None, 'SearchNumar')}"
            f"{self._field(text, 'SearchText')}"
            f"{self._field(title, 'SearchTitlu')}"
        )
        envelope = (
            f'<?xml version="1.0" encoding="utf-8"?>'
            f'<soap:Envelope xmlns:soap="{SOAP_NS}" xmlns:tem="{SERVICE_NS}" '
            f'xmlns:free="{DATA_NS}">'
            f"<soap:Body><tem:Search><tem:SearchModel>{model}</tem:SearchModel>"
            f"<tem:tokenKey>{token}</tem:tokenKey></tem:Search></soap:Body></soap:Envelope>"
        )
        cache_key = f"{self.endpoint}|search|{model}"
        cached = self._cache.get(cache_key)
        if cached is not None and isinstance(cached, bytes):
            content = cached
        else:
            content = await self._post(envelope, "Search")
            self._cache.set(cache_key, content, ttl=HttpCache.ttl_for("search"))

        return parse_legi_records(content)
