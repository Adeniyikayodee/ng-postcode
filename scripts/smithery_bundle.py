"""Build the bundle Smithery accepts: `mcp/bundle-python` plus each tool's input schema.

    cd mcp && uv run --group dev python ../scripts/smithery_bundle.py ng-postcode-smithery.mcpb

Smithery needs `inputSchema` on every tool, which the MCPB manifest schema does not
allow, so the schemas are read from the running server and added only to this copy.
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


async def input_schemas() -> dict[str, object]:
    async with Client(create_server(Settings(api_key=None))) as client:
        return {tool.name: tool.input_schema for tool in (await client.list_tools()).tools}


def main() -> None:
    target = Path(sys.argv[1])
    schemas = asyncio.run(input_schemas())
    manifest = json.loads((BUNDLE / "manifest.json").read_text(encoding="utf-8"))
    manifest["tools"] = [
        tool | {"inputSchema": schemas[tool["name"]]} for tool in manifest["tools"]
    ]
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        archive.write(BUNDLE / "server" / "main.py", "server/main.py")
    print(f"wrote {target} with {len(manifest['tools'])} tools")


if __name__ == "__main__":
    main()
