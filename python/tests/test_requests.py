"""Runs the shared cases in `spec/requests.json`: what each request sends, or that it is refused."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ng_postcode import Postcode
from ng_postcode.api import Coordinate, Request, autocomplete, lookup, nearby, reverse

SPEC = Path(__file__).resolve().parents[2] / "spec" / "requests.json"
CASES: list[dict[str, Any]] = (
    json.loads(SPEC.read_text(encoding="utf-8"))["cases"] if SPEC.exists() else []
)

pytestmark = pytest.mark.skipif(
    not CASES, reason="spec/requests.json lives in the repository, not the sdist"
)


def build(kind: str, args: dict[str, Any]) -> Request[Any]:
    if kind == "lookup":
        return lookup(Postcode(args["code"]), args["level"])
    if kind == "autocomplete":
        return autocomplete(args["q"])
    at = Coordinate(lat=float(args["lat"]), lng=float(args["lng"]))
    metres = float(args["metres"]) if "metres" in args else None
    return reverse(at, metres) if kind == "reverse" else nearby(at, metres)


UNTYPED: list[dict[str, Any]] = (
    json.loads(SPEC.read_text(encoding="utf-8"))["untyped"] if CASES else []
)


@pytest.mark.parametrize("case", UNTYPED, ids=[case["name"] for case in UNTYPED])
def test_refuses_an_argument_of_the_wrong_type(case: dict[str, Any]) -> None:
    with pytest.raises(TypeError):
        untyped(case["request"], case["args"], case.get("parsed", False))


def untyped(kind: str, args: dict[str, Any], parsed: bool) -> Request[Any]:
    """The request built from arguments passed exactly as the case writes them."""
    if kind == "lookup":
        return lookup(Postcode(args["code"]) if parsed else args["code"], args["level"])
    if kind == "autocomplete":
        return autocomplete(args["q"])
    return reverse(Coordinate(lat=args["lat"], lng=args["lng"]), args.get("metres"))


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_builds_the_shared_request(case: dict[str, Any]) -> None:
    try:
        request = build(case["request"], case["args"])
    except ValueError:
        sent = None
    else:
        sent = {"path": request.path, "query": [list(pair) for pair in request.params]}
    assert sent == case["sends"]
