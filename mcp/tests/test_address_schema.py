"""The shared address record schema, which wraps a postcode reference."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

SCHEMAS = Path(__file__).resolve().parents[2] / "docs/schemas"

pytestmark = pytest.mark.skipif(
    not SCHEMAS.exists(), reason="the schemas live in the repository, not the sdist"
)


def loaded(name: str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
    return document


@pytest.fixture(scope="module")
def schema() -> Draft202012Validator:
    address = loaded("address.schema.json")
    Draft202012Validator.check_schema(address)
    # The reference is resolved from the file beside it, never fetched.
    reference = loaded("postcode-reference.schema.json")
    registry = Registry().with_resource(reference["$id"], Resource.from_contents(reference))
    return Draft202012Validator(address, registry=registry)


def test_its_own_examples_are_valid(schema: Draft202012Validator) -> None:
    for example in loaded("address.schema.json")["examples"]:
        schema.validate(example)


BUILDING = {"code": "EK-01-A03-FK-01", "level": "building"}


@pytest.mark.parametrize(
    "address",
    [
        {"postcode": BUILDING},
        {"country": "NG"},
        {"postcode": BUILDING, "country": "Nigeria"},
        {"postcode": "EK-01-A03-FK-01", "country": "NG"},
        {"postcode": {"code": "EK-01-A03-FK", "level": "building"}, "country": "NG"},
        {"postcode": BUILDING, "country": "NG", "state": ""},
        {"postcode": BUILDING, "country": "NG", "location": {"lat": 95, "lng": 5.2}},
        {"postcode": BUILDING, "country": "NG", "location": {"lat": 7.6}},
    ],
)
def test_rejects_malformed_addresses(schema: Draft202012Validator, address: dict[str, Any]) -> None:
    assert not schema.is_valid(address)


def test_unknown_fields_are_ignored(schema: Draft202012Validator) -> None:
    schema.validate({"postcode": BUILDING, "country": "NG", "floor": "2"})
