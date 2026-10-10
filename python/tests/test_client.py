from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any

import httpx
import pytest

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


# spec/client.json: sends_the_key
def test_sends_the_key_and_decodes_the_answer() -> None:
    with sync_client("key", api) as client:
        found = client.send(lookup(CODE))
    assert isinstance(found, Lookup)
    assert (found.postcode, found.valid) == ("EK-01-A03-FK-01", True)


# spec/client.json: failures_are_values
def test_api_and_network_failures_are_values() -> None:
    with sync_client("wrong", api) as client:
        assert client.send(lookup(CODE)) == ApiError(
            401, "invalid_api_key", "the provided API key is invalid"
        )
    with sync_client("key", unreachable) as client:
        assert client.send(lookup(CODE)) == TransportError("connection refused")


# spec/client.json: refuses_an_unusable_key
@pytest.mark.parametrize("key", ["se\ncret", "se cret", "sécret", "", " \n"])
def test_an_unusable_key_is_refused_without_being_echoed(key: str) -> None:
    sent: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200)

    transport = httpx.MockTransport(record)
    with Client(key, http=httpx.Client(transport=transport)) as client:
        refused = client.send(lookup(CODE))

    async def run() -> Lookup | ApiError | TransportError:
        async with AsyncClient(key, http=httpx.AsyncClient(transport=transport)) as client:
            return await client.send(lookup(CODE))

    assert refused == asyncio.run(run()) == TransportError("unusable API key")
    assert sent == []


def test_whitespace_around_a_key_is_dropped() -> None:
    with sync_client(" key\n", api) as client:
        found = client.send(lookup(CODE))
    assert isinstance(found, Lookup)


# spec/client.json: refuses_redirects
def test_a_redirect_is_not_followed_even_by_a_client_that_would() -> None:
    hosts: list[str] = []

    def elsewhere(request: httpx.Request) -> httpx.Response:
        hosts.append(request.url.host)
        return httpx.Response(302, headers={"Location": "https://elsewhere.example/v1/lookup"})

    transport = httpx.MockTransport(elsewhere)
    with Client("key", http=httpx.Client(transport=transport, follow_redirects=True)) as client:
        refused = client.send(lookup(CODE))

    async def run() -> Lookup | ApiError | TransportError:
        http = httpx.AsyncClient(transport=transport, follow_redirects=True)
        async with AsyncClient("key", http=http) as client:
            return await client.send(lookup(CODE))

    for result in (refused, asyncio.run(run())):
        assert isinstance(result, ApiError)
        assert (result.status, result.code) == (302, "malformed_response")
    assert hosts == ["api.postcode.gov.ng"] * 2


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), None, "5"])
def test_a_timeout_that_is_not_a_positive_number_is_refused(timeout: Any) -> None:
    for client in (Client, AsyncClient):
        with pytest.raises(ValueError, match="timeout must be"):
            client("key", timeout=timeout)


# spec/client.json: caps_the_body
def test_a_body_over_the_cap_is_refused_without_being_read_in_full() -> None:
    served = 0

    class Flood(httpx.SyncByteStream, httpx.AsyncByteStream):
        def __iter__(self) -> Iterator[bytes]:
            nonlocal served
            while True:
                served += 65536
                yield b" " * 65536

        async def __aiter__(self) -> AsyncIterator[bytes]:
            for chunk in self:
                yield chunk

    transport = httpx.MockTransport(lambda _: httpx.Response(200, stream=Flood()))
    with Client("key", http=httpx.Client(transport=transport)) as client:
        refused = client.send(lookup(CODE))

    async def run() -> Lookup | ApiError | TransportError:
        async with AsyncClient("key", http=httpx.AsyncClient(transport=transport)) as client:
            return await client.send(lookup(CODE))

    assert refused == asyncio.run(run()) == TransportError("response too large")
    assert served < 4_000_000


# spec/client.json: times_out_a_stalled_body
def test_a_body_that_drips_is_cut_off_at_the_deadline() -> None:
    class Drip(httpx.SyncByteStream, httpx.AsyncByteStream):
        def __iter__(self) -> Iterator[bytes]:
            while True:
                time.sleep(0.01)
                yield b" "

        async def __aiter__(self) -> AsyncIterator[bytes]:
            while True:
                await asyncio.sleep(0.01)
                yield b" "

    transport = httpx.MockTransport(lambda _: httpx.Response(200, stream=Drip()))
    with Client("key", http=httpx.Client(transport=transport), timeout=0.05) as client:
        assert client.send(lookup(CODE)) == TransportError("timed out")

    async def run() -> Lookup | ApiError | TransportError:
        http = httpx.AsyncClient(transport=transport)
        async with AsyncClient("key", http=http, timeout=0.05) as client:
            return await client.send(lookup(CODE))

    assert asyncio.run(run()) == TransportError("timed out")


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
