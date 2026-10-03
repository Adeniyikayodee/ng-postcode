from __future__ import annotations

import asyncio
from collections.abc import Callable

import httpx

from ng_postcode import Postcode
from ng_postcode.api import ApiError, Lookup, lookup
from ng_postcode.client import AsyncClient, Client, TransportError

CODE = Postcode("EK01A03FK01")


def api(request: httpx.Request) -> httpx.Response:
    if request.headers.get("X-API-Key") != "key":
        error = {"code": "invalid_api_key", "message": "the provided API key is invalid"}
        return httpx.Response(401, json={"error": error})
    assert request.url.path == "/v1/lookup"
    assert dict(request.url.params) == {"code": "EK-01-A03-FK-01", "level": "1"}
    return httpx.Response(200, json={"data": {"postcode": "EK-01-A03-FK-01", "valid": True}})


def unreachable(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection refused", request=request)


def sync_client(key: str, handler: Callable[[httpx.Request], httpx.Response]) -> Client:
    return Client(key, http=httpx.Client(transport=httpx.MockTransport(handler)))


def test_sends_the_key_and_decodes_the_answer() -> None:
    with sync_client("key", api) as client:
        found = client.send(lookup(CODE))
    assert isinstance(found, Lookup)
    assert (found.postcode, found.valid) == ("EK-01-A03-FK-01", True)


def test_api_and_network_failures_are_values() -> None:
    with sync_client("wrong", api) as client:
        assert client.send(lookup(CODE)) == ApiError(
            401, "invalid_api_key", "the provided API key is invalid"
        )
    with sync_client("key", unreachable) as client:
        assert client.send(lookup(CODE)) == TransportError("connection refused")


def test_only_closes_the_http_client_it_created() -> None:
    http = httpx.Client(transport=httpx.MockTransport(api))
    with Client("key", http=http):
        pass
    assert not http.is_closed
    http.close()


def test_async_client() -> None:
    async def run() -> Lookup | ApiError | TransportError:
        http = httpx.AsyncClient(transport=httpx.MockTransport(api))
        async with AsyncClient("key", http=http) as client:
            return await client.send(lookup(CODE))

    found = asyncio.run(run())
    assert isinstance(found, Lookup)
    assert found.valid
