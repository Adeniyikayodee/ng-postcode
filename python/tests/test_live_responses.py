"""Decodes the response bodies captured from the live API in `spec/responses.json`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

import pytest

from ng_postcode import Postcode, Segment
from ng_postcode.api import (
    ApiError,
    Coordinate,
    NearbyUnit,
    Request,
    autocomplete,
    decode,
    lookup,
    nearby,
    reverse,
)

T = TypeVar("T")

RESPONSES = Path(__file__).resolve().parents[2] / "spec" / "responses.json"
LIVE: dict[str, Any] = (
    json.loads(RESPONSES.read_text(encoding="utf-8")) if RESPONSES.exists() else {}
)
CODE = Postcode("FC03B06AG12")
HERE = Coordinate(lat=7.6211, lng=5.2214)

pytestmark = pytest.mark.skipif(
    not LIVE, reason="spec/responses.json lives in the repository, not the sdist"
)


def live(request: Request[T], name: str) -> T | ApiError:
    captured = LIVE[name]
    return decode(request, captured["status"], json.dumps(captured["body"]))


def test_lookup_statuses() -> None:
    valid = live(lookup(CODE), "lookup_valid")
    assert not isinstance(valid, ApiError)
    assert (valid.valid, valid.status, valid.verified) == (True, "valid", False)
    assert valid.administrative_address is None

    missing = live(lookup(CODE), "lookup_not_found")
    assert not isinstance(missing, ApiError)
    assert (missing.valid, missing.status) == (False, "not_found")

    malformed = live(lookup(CODE), "lookup_invalid")
    assert not isinstance(malformed, ApiError)
    assert (malformed.valid, malformed.status) == (False, "invalid")


def test_autocomplete_sends_segment_values_without_labels() -> None:
    states = live(autocomplete("E"), "autocomplete_state")
    assert not isinstance(states, ApiError)
    assert states.segment is Segment.STATE
    assert [(s.code, s.label) for s in states.suggestions] == [
        ("EB", None),
        ("ED", None),
        ("EK", None),
        ("EN", None),
    ]
    units = live(autocomplete("EK 01 A29 KR 3"), "autocomplete_unit_empty")
    assert not isinstance(units, ApiError)
    assert (units.segment, units.suggestions) == (Segment.UNIT, ())


def test_reverse() -> None:
    found = live(reverse(HERE), "reverse_found")
    assert not isinstance(found, ApiError)
    assert found.unit is not None
    assert (found.unit.postcode, found.unit.distance_m, found.unit.confidence) == (
        "EK-01-A29-KR-36",
        15.7,
        "high",
    )
    assert (found.area, found.district, found.state, found.depth) == (
        "EK-01-A29-KR",
        "EK-01-A29",
        "EK",
        "unit",
    )
    assert found.coordinate == HERE
    assert (found.unit.address, found.radius_m) == (None, 25.0)

    nothing = live(reverse(HERE), "reverse_not_found")
    assert not isinstance(nothing, ApiError)
    assert (nothing.found, nothing.unit) == (False, None)
    assert nothing.message == "no postcode within range of this location"


def test_nearby_is_a_list_nearest_first() -> None:
    units = live(nearby(HERE), "nearby_found")
    assert not isinstance(units, ApiError)
    assert units[0] == NearbyUnit("EK-01-A29-KR-36", "EK 01 A29 KR 36", 15.7)
    assert [u.distance_m for u in units] == [15.7, 18.3, 31.0]
    assert live(nearby(HERE), "nearby_empty") == ()


@pytest.mark.parametrize(
    ("name", "code"),
    [
        ("lookup_level_not_granted", "level_not_granted"),
        ("reverse_bad_request", "bad_request"),
        ("invalid_api_key", "invalid_api_key"),
    ],
)
def test_errors(name: str, code: str) -> None:
    error = live(lookup(CODE), name)
    assert isinstance(error, ApiError)
    assert (error.status, error.code) == (LIVE[name]["status"], code)
