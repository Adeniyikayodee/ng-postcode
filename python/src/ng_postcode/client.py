"""HTTP shell over `ng_postcode.api`, built on httpx: the only module that performs I/O.

Install with `pip install "ng-postcode[client]"`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TypeVar

import anyio
import httpx

from .api import BASE_URL, ApiError, Request, decode

T = TypeVar("T")

TIMEOUT = 10.0
"""Seconds allowed for a whole exchange, body included."""

UNUSABLE_KEY = "unusable API key"

MAX_BODY = 1_000_000
"""Characters of a response read before it is refused. Real answers are a few thousand."""


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
        self,
        api_key: str,
        *,
        base_url: str = BASE_URL,
        http: httpx.Client | None = None,
        timeout: float = TIMEOUT,
    ) -> None:
        self._http = http if http is not None else httpx.Client(timeout=timeout)
        self._owns_http = http is None
        self._base_url = base_url
        self._headers = _headers(api_key)
        self._timeout = timeout

    def send(self, request: Request[T]) -> T | ApiError | TransportError:
        if self._headers is None:
            return TransportError(UNUSABLE_KEY)
        url = self._base_url + request.path
        # httpx times each read, so a body that drips would never end: the deadline does.
        deadline = time.monotonic() + self._timeout
        try:
            with self._http.stream(
                "GET",
                url,
                params=request.params,
                headers=self._headers,
                follow_redirects=False,
                timeout=self._timeout,
            ) as response:
                parts, size = [], 0
                for part in response.iter_text():
                    size += len(part)
                    if time.monotonic() > deadline:
                        return TransportError("timed out")
                    if size > MAX_BODY:
                        return TransportError("response too large")
                    parts.append(part)
        except httpx.HTTPError as error:
            return _transport(error)
        return decode(request, response.status_code, "".join(parts))

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
        self,
        api_key: str,
        *,
        base_url: str = BASE_URL,
        http: httpx.AsyncClient | None = None,
        timeout: float = TIMEOUT,
    ) -> None:
        self._http = http if http is not None else httpx.AsyncClient(timeout=timeout)
        self._owns_http = http is None
        self._base_url = base_url
        self._headers = _headers(api_key)
        self._timeout = timeout

    async def send(self, request: Request[T]) -> T | ApiError | TransportError:
        if self._headers is None:
            return TransportError(UNUSABLE_KEY)
        url = self._base_url + request.path
        try:
            with anyio.fail_after(self._timeout):
                async with self._http.stream(
                    "GET",
                    url,
                    params=request.params,
                    headers=self._headers,
                    follow_redirects=False,
                ) as response:
                    parts, size = [], 0
                    async for part in response.aiter_text():
                        size += len(part)
                        if size > MAX_BODY:
                            return TransportError("response too large")
                        parts.append(part)
        except TimeoutError:
            return TransportError("timed out")
        except httpx.HTTPError as error:
            return _transport(error)
        return decode(request, response.status_code, "".join(parts))

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> AsyncClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()


def _headers(api_key: str) -> dict[str, str] | None:
    """The key header, or None for a key no header can hold. Surrounding whitespace, as read
    from a file, is dropped."""
    key = api_key.strip()
    usable = key and key.isascii() and key.isprintable() and " " not in key
    return {"X-API-Key": key} if usable else None


def _transport(error: httpx.HTTPError) -> TransportError:
    return TransportError(str(error) or type(error).__name__)
