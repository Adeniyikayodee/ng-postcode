"""The real entry point over stdio: proves nothing but protocol reaches stdout."""

from __future__ import annotations

import os
import sys

import pytest
from mcp import Client, StdioServerParameters


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_serves_over_stdio() -> None:
    env = {k: v for k, v in os.environ.items() if not k.startswith("NG_POSTCODE_")}
    params = StdioServerParameters(command=sys.executable, args=["-m", "ng_postcode_mcp"], env=env)
    async with Client(params) as client:
        names = {tool.name for tool in (await client.list_tools()).tools}
        result = await client.call_tool("validate_postcode", {"postcode": "LA11W06TC10"})
    assert "validate_postcode" in names
    assert result.structured_content["postcode"] == "LA-11-W06-TC-10"
