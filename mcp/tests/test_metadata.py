"""Release metadata must agree, or the registry rejects the publish."""

from __future__ import annotations

import json
from importlib.metadata import version
from pathlib import Path
from typing import Any

import pytest
from mcp import Client

from ng_postcode_mcp import Settings, create_server
from ng_postcode_mcp.server import INSTRUCTIONS

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def server_json() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
    return data


def test_versions_and_names_agree() -> None:
    server = server_json()
    package = server["packages"][0]
    assert package["identifier"] == "ng-postcode-mcp"
    assert server["version"] == package["version"] == version("ng-postcode-mcp")

    manifest = ROOT.parent / "js/packages/ng-postcode-mcp/package.json"
    if not manifest.exists():  # the Node package lives in the repository, not the sdist
        return
    node = json.loads(manifest.read_text(encoding="utf-8"))
    listed = server["packages"][1]
    assert (listed["registryType"], listed["identifier"]) == ("npm", node["name"])
    assert listed["version"] == node["version"]
    assert node["mcpName"] == server["name"]


def test_readme_proves_registry_ownership() -> None:
    marker = f"<!-- mcp-name: {server_json()['name']} -->"
    assert marker in (ROOT / "README.md").read_text(encoding="utf-8")


def test_registry_description_fits() -> None:
    assert len(server_json()["description"]) <= 100


def test_the_bundle_pins_this_version() -> None:
    bundle = ROOT / "bundle"
    if not bundle.exists():  # the bundle lives in the repository, not the sdist
        return
    released = version("ng-postcode-mcp")
    manifest: dict[str, Any] = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == released
    assert f'"ng-postcode-mcp=={released}"' in (bundle / "pyproject.toml").read_text()


def test_the_python_bundle_pins_this_version() -> None:
    bundle = ROOT / "bundle-python"
    if not bundle.exists():  # the bundle lives in the repository, not the sdist
        return
    released = version("ng-postcode-mcp")
    manifest: dict[str, Any] = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == released
    assert f'"ng-postcode-mcp=={released}"' in (bundle / "server" / "main.py").read_text()


@pytest.mark.anyio
async def test_the_shared_contract_matches_this_server() -> None:
    shared = ROOT.parent / "spec" / "mcp.json"
    if not shared.exists():  # the contract lives in the repository, not the sdist
        return
    async with Client(create_server(Settings(api_key=None))) as client:
        tools = (await client.list_tools()).tools
    live = [t.model_dump(mode="json", by_alias=True, exclude_none=True) for t in tools]
    recorded: dict[str, Any] = json.loads(shared.read_text(encoding="utf-8"))
    assert recorded == {"instructions": INSTRUCTIONS, "tools": live}, "run scripts/mcp_spec.py"
