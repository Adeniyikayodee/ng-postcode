"""A caller's own NIPOST key over HTTP, against an in-process server with NIPOST mocked."""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

import httpx
import httpx2
import pytest
import uvicorn
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult

from ng_postcode_mcp import Settings, create_server

LOOKUP = {"postcode": "EK-01-A03-FK-01"}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@contextmanager
def serving(server_key: str | None, keys_seen: list[str]) -> Iterator[str]:
    """Run the server over HTTP on a loopback port; yields its URL."""

    def nipost(request: httpx.Request) -> httpx.Response:
        keys_seen.append(request.headers["X-API-Key"])
        return httpx.Response(200, json={"data": {"postcode": "EK-01-A03-FK-01", "valid": True}})

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(nipost))
    app = create_server(Settings(api_key=server_key), http=upstream).streamable_http_app()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = int(probe.getsockname()[1])
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 20
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        server.should_exit = True
        thread.join(timeout=10)


async def lookup(url: str, caller_key: str | None) -> CallToolResult:
    headers = {"X-NIPOST-API-Key": caller_key} if caller_key else {}
    async with (
        httpx2.AsyncClient(headers=headers) as http,
        Client(streamable_http_client(url, http_client=http)) as client,
    ):
        return await client.call_tool("lookup_postcode", LOOKUP)


@pytest.mark.anyio
async def test_a_callers_key_is_used_for_its_own_requests() -> None:
    seen: list[str] = []
    with serving(None, seen) as url:
        own = await lookup(url, "caller-key")
        none = await lookup(url, None)
    assert not own.is_error
    assert seen == ["caller-key"]
    assert none.is_error
    assert "X-NIPOST-API-Key" in str(none.content)


@pytest.mark.anyio
async def test_the_servers_key_is_the_fallback() -> None:
    seen: list[str] = []
    with serving("server-key", seen) as url:
        await lookup(url, None)
        await lookup(url, "caller-key")
    assert seen == ["server-key", "caller-key"]
