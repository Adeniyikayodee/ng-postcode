"""Build the bundle Smithery accepts: `mcp/bundle-python` plus each tool's input schema.

    cd mcp && uv run --group dev python ../scripts/smithery_bundle.py ng-postcode-smithery.mcpb

Smithery reads full tool definitions (input and output schemas, titles, annotations),
which the MCPB manifest schema does not allow, so they are read from the running
server and added only to this copy.
"""

from __future__ import annotations

import asyncio
import json
import sys
import zipfile
from pathlib import Path

from mcp import Client

from ng_postcode_mcp import Settings, create_server

BUNDLE = Path(__file__).resolve().parents[1] / "mcp" / "bundle-python"


async def tool_definitions() -> list[dict[str, object]]:
    async with Client(create_server(Settings(api_key=None))) as client:
        tools = (await client.list_tools()).tools
    return [tool.model_dump(mode="json", by_alias=True, exclude_none=True) for tool in tools]


def main() -> None:
    target = Path(sys.argv[1])
    manifest = json.loads((BUNDLE / "manifest.json").read_text(encoding="utf-8"))
    manifest["tools"] = asyncio.run(tool_definitions())
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        archive.write(BUNDLE / "server" / "main.py", "server/main.py")
    print(f"wrote {target} with {len(manifest['tools'])} tools")


if __name__ == "__main__":
    main()
