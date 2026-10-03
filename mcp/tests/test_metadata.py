"""Release metadata must agree, or the registry rejects the publish."""

from __future__ import annotations

import json
from importlib.metadata import version
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def server_json() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
    return data


def test_versions_and_names_agree() -> None:
    server = server_json()
    package = server["packages"][0]
    assert package["identifier"] == "ng-postcode-mcp"
    assert server["version"] == package["version"] == version("ng-postcode-mcp")


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
