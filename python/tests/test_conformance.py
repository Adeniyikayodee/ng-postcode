"""Runs the shared cases in `spec/vectors.json`, which every implementation must pass."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ng_postcode import (
    Corrected,
    InvalidCharacter,
    InvalidSegment,
    ParseError,
    Postcode,
    Segment,
    WrongLength,
    from_segments,
    parse,
    parse_lenient,
)

VECTORS = Path(__file__).resolve().parents[2] / "spec" / "vectors.json"
CASES: dict[str, Any] = json.loads(VECTORS.read_text(encoding="utf-8")) if VECTORS.exists() else {}

pytestmark = pytest.mark.skipif(
    not CASES, reason="spec/vectors.json lives in the repository, not the sdist"
)


def outcome(result: Postcode | Corrected | ParseError) -> dict[str, Any]:
    match result:
        case Postcode():
            return {"canonical": str(result)}
        case Corrected(postcode, corrections):
            return {"canonical": str(postcode), "corrections": corrections}
        case WrongLength(found):
            error: dict[str, Any] = {"kind": "length", "found": found}
        case InvalidCharacter(char, index):
            error = {"kind": "invalid_character", "char": char, "index": index}
        case InvalidSegment(segment):
            error = {"kind": "segment", "segment": segment.value}
    return {"error": error | {"message": str(result)}}


def expected(case: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in case.items() if k in ("canonical", "corrections", "error")}


@pytest.mark.parametrize("case", CASES.get("parse", {}).get("valid", []))
def test_parse_valid(case: dict[str, Any]) -> None:
    code = parse(case["input"])
    assert isinstance(code, Postcode)
    assert (str(code), code.compact, code.spaced) == (
        case["canonical"],
        case["compact"],
        case["spaced"],
    )


@pytest.mark.parametrize("case", CASES.get("parse", {}).get("invalid", []))
def test_parse_invalid(case: dict[str, Any]) -> None:
    assert outcome(parse(case["input"])) == expected(case)


@pytest.mark.parametrize("case", CASES.get("parse_lenient", []))
def test_parse_lenient(case: dict[str, Any]) -> None:
    assert outcome(parse_lenient(case["input"])) == expected(case)


@pytest.mark.parametrize("case", CASES.get("from_segments", []))
def test_from_segments(case: dict[str, Any]) -> None:
    assert outcome(from_segments(*case["segments"])) == expected(case)


@pytest.mark.parametrize("case", CASES.get("prefix", []))
def test_prefix(case: dict[str, Any]) -> None:
    code = parse(case["input"])
    assert isinstance(code, Postcode)
    assert code.prefix(Segment(case["through"])) == case["prefix"]
