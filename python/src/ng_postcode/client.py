"""HTTP shell over `ng_postcode.api`, built on httpx: the only module that performs I/O.

Install with `pip install "ng-postcode[client]"`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

import httpx

from .api import BASE_URL, ApiError, Request, decode

T = TypeVar("T")

TIMEOUT = 10.0


@dataclass(frozen=True, slots=True)
class TransportError:
    """The request never produced a response: DNS, TLS, timeout and the like."""

    reason: str

    def __str__(self) -> str:
        return self.reason


class Client:
    """Blocking client. Pass `http` to reuse your own `httpx.Client`; it stays yours to close.
    A redirect is never followed, as it would carry the key to another host."""

    def __init__(
        self, api_key: str, *, base_url: str = BASE_URL, http: httpx.Client | None = None
    ) -> None:
        self._http = http if http is not None else httpx.Client(timeout=TIMEOUT)
        self._owns_http = http is None
        self._base_url = base_url
        self._headers = {"X-API-Key": api_key}

    def send(self, request: Request[T]) -> T | ApiError | TransportError:
        url = self._base_url + request.path
        try:
            response = self._http.get(
                url, params=request.params, headers=self._headers, follow_redirects=False
            )
        except httpx.HTTPError as error:
            return _transport(error)
        return decode(request, response.status_code, response.text)

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


class AsyncClient:
    """Async client. Pass `http` to reuse your own `httpx.AsyncClient`; it stays yours to close.
    A redirect is never followed, as it would carry the key to another host."""

    def __init__(
        self, api_key: str, *, base_url: str = BASE_URL, http: httpx.AsyncClient | None = None
    ) -> None:
        self._http = http if http is not None else httpx.AsyncClient(timeout=TIMEOUT)
        self._owns_http = http is None
        self._base_url = base_url
        self._headers = {"X-API-Key": api_key}

    async def send(self, request: Request[T]) -> T | ApiError | TransportError:
        url = self._base_url + request.path
        try:
            response = await self._http.get(
                url, params=request.params, headers=self._headers, follow_redirects=False
            )
        except httpx.HTTPError as error:
            return _transport(error)
        return decode(request, response.status_code, response.text)

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> AsyncClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()


def _transport(error: httpx.HTTPError) -> TransportError:
    return TransportError(str(error) or type(error).__name__)
