"""The real entry point over HTTP, on a loopback port."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time

import httpx
import pytest
from mcp import Client


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def wait_until_listening(port: int, seconds: float = 20.0) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.1)
    raise TimeoutError(f"nothing listening on port {port}")


@pytest.mark.anyio
async def test_serves_over_http() -> None:
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith("NG_POSTCODE_")}
    env |= {"NG_POSTCODE_TRANSPORT": "http", "NG_POSTCODE_PORT": str(port)}
    server = subprocess.Popen([sys.executable, "-m", "ng_postcode_mcp"], env=env)
    try:
        wait_until_listening(port)
        async with Client(f"http://127.0.0.1:{port}/mcp") as client:
            result = await client.call_tool("validate_postcode", {"postcode": "LA11W06TC10"})
        hello = httpx.post(
            f"http://127.0.0.1:{port}/mcp",
            headers={"Accept": "application/json, text/event-stream"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
    finally:
        server.terminate()
        server.wait(timeout=10)
    assert result.structured_content["postcode"] == "LA-11-W06-TC-10"
    # No session is opened, so a caller cannot pile them up.
    assert hello.status_code == 200
    assert "mcp-session-id" not in hello.headers
