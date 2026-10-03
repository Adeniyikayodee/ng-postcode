"""The shared postcode reference schema, and that resolve_address answers fit it."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from ng_address.models import Resolution
from ng_postcode import Postcode, Segment

SCHEMA_FILE = Path(__file__).resolve().parents[2] / "docs/schemas/postcode-reference.schema.json"

pytestmark = pytest.mark.skipif(
    not SCHEMA_FILE.exists(), reason="the schema lives in the repository, not the sdist"
)


def loaded() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    return document


@pytest.fixture(scope="module")
def schema() -> Draft202012Validator:
    Draft202012Validator.check_schema(loaded())
    return Draft202012Validator(loaded())


def test_its_own_examples_are_valid(schema: Draft202012Validator) -> None:
    for example in loaded()["examples"]:
        schema.validate(example)


@pytest.mark.parametrize(
    "reference",
    [
        {"code": "EK-01-A03-FK-01"},
        {"code": "EK-01-A03-FK-01", "level": "area"},
        {"code": "EK-01-A03-FK", "level": "building"},
        {"code": "EK01A03FK01", "level": "building"},
        {"code": "ek-01-a03-fk-01", "level": "building"},
        {"code": "EK-00", "level": "lga"},
        {"code": "EK-01", "level": "street"},
        {"code": "EK-01", "level": "lga", "confidence": "certain"},
    ],
)
def test_rejects_malformed_references(
    schema: Draft202012Validator, reference: dict[str, str]
) -> None:
    assert not schema.is_valid(reference)


def test_every_prefix_of_a_code_fits_its_level(schema: Draft202012Validator) -> None:
    code = Postcode("EK01A03FK01")
    levels = {"state": Segment.STATE, "lga": Segment.LGA, "district": Segment.DISTRICT}
    levels |= {"area": Segment.AREA, "building": Segment.UNIT}
    for level, segment in levels.items():
        schema.validate({"code": code.prefix(segment), "level": level})


def test_a_resolution_is_a_reference(schema: Draft202012Validator) -> None:
    answer = Resolution(
        status="partial",
        code="EK-01-A03-FK",
        level="area",
        confidence="medium",
        method="geocoded",
        question="Which building is it?",
        evidence=[],
    )
    schema.validate(answer.model_dump())
