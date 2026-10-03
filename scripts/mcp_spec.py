"""Write the MCP server's contract to `spec/mcp.json`: its instructions and tool definitions.

    cd mcp && uv run --group dev python ../scripts/mcp_spec.py

The Python server is the source; other implementations register tools from this
file, and a test fails when it is out of date.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from mcp import Client

from ng_postcode_mcp import Settings, create_server
from ng_postcode_mcp.server import INSTRUCTIONS

TARGET = Path(__file__).resolve().parents[1] / "spec" / "mcp.json"


async def contract() -> dict[str, Any]:
    async with Client(create_server(Settings(api_key=None))) as client:
        tools = (await client.list_tools()).tools
    definitions = [t.model_dump(mode="json", by_alias=True, exclude_none=True) for t in tools]
    return {"instructions": INSTRUCTIONS, "tools": definitions}


def main() -> None:
    TARGET.write_text(json.dumps(asyncio.run(contract()), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
