"""Runs the shared cases in `spec/tolerance.json`: bodies the live API may one day send."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ng_postcode import Postcode
from ng_postcode.api import (
    ApiError,
    Coordinate,
    Request,
    autocomplete,
    decode,
    lookup,
    nearby,
    reverse,
)

SPEC = Path(__file__).resolve().parents[2] / "spec" / "tolerance.json"
CASES: list[dict[str, Any]] = (
    json.loads(SPEC.read_text(encoding="utf-8"))["cases"] if SPEC.exists() else []
)
HERE = Coordinate(lat=7.6211, lng=5.2214)
REQUESTS: dict[str, Request[Any]] = {
    "lookup": lookup(Postcode("FC03B06AG12"), 1),
    "autocomplete": autocomplete("E"),
    "reverse": reverse(HERE),
    "nearby": nearby(HERE),
}

pytestmark = pytest.mark.skipif(
    not CASES, reason="spec/tolerance.json lives in the repository, not the sdist"
)


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_reaches_the_shared_outcome(case: dict[str, Any]) -> None:
    body = case["text"] if "text" in case else json.dumps(case["body"])
    decoded = decode(REQUESTS[case["request"]], case["status"], body)
    if not isinstance(decoded, ApiError):
        found: tuple[str, str | None] = ("ok", None)
    elif decoded.code == "malformed_response":
        found = ("malformed", None)
    else:
        found = ("rejected", decoded.code)
    assert found == (case["outcome"], case.get("code"))
