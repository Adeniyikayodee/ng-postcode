"""The precision rules. Pure functions, so no mocks."""

from __future__ import annotations

from typing import Any

import pytest
from ng_postcode import Postcode
from ng_postcode.api import NearestUnit, Reverse

from ng_address.core import (
    code_at,
    find_typed_postcode,
    from_geocoded,
    from_location,
    from_typed,
    landmark_for,
    precision_of,
)
from ng_address.models import Geocoded, Landmark, ParsedAddress, Precision, Relation

CODE = Postcode("EK01A03FK01")


def found(distance_m: float | None, postcode: str = "EK-01-A03-FK-01") -> Reverse:
    unit = NearestUnit(
        postcode=postcode,
        display=postcode.replace("-", " "),
        distance_m=distance_m,
        confidence="high",
        state_name=None,
        lga_name=None,
        locality_name=None,
        address=None,
    )
    return reverse_result(found=True, unit=unit, area="EK-01-A03-FK", district="EK-01-A03")


def reverse_result(**fields: Any) -> Reverse:
    base: dict[str, Any] = {
        "found": False,
        "coordinate": None,
        "unit": None,
        "area": None,
        "district": None,
        "state": None,
        "message": None,
        "radius_m": 25.0,
    }
    return Reverse(**(base | fields))


NOTHING = reverse_result(message="no unit in range")


def place(precision: Precision) -> Geocoded:
    return Geocoded(query="q", lat=7.6, lng=5.2, precision=precision, label="Somewhere, Ekiti")


def parsed(*landmarks: tuple[str, Relation]) -> ParsedAddress:
    return ParsedAddress(
        house_number=None,
        street="NTA Road",
        landmarks=[Landmark(name=n, relation=r) for n, r in landmarks],
        locality=None,
        lga=None,
        state="Ekiti",
        geocode_queries=["Fabian Hotel, Ado Ekiti"],
        question=None,
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Deliver to EK-01-A03-FK-01 please", "EK-01-A03-FK-01"),
        ("my code is ek 01 a03 fk 01.", "EK-01-A03-FK-01"),
        ("LA11W06TC10, Lekki", "LA-11-W06-TC-10"),
        ("EK-O1-A03-FK-01", None),  # look-alikes are never corrected silently
        ("Plot EK0101A03FK019", None),  # embedded in a longer token
        ("back of Fabian Hotel, Ado Ekiti", None),
    ],
)
def test_finds_only_well_formed_typed_postcodes(text: str, expected: str | None) -> None:
    code = find_typed_postcode(text)
    assert (str(code) if code else None) == expected


def test_precision_follows_nominatim_ranks() -> None:
    assert [precision_of(r) for r in (30, 28, 27, 26, 20, 0)] == [
        "building",
        "building",
        "street",
        "street",
        "locality",
        "locality",
    ]


def test_code_at_levels() -> None:
    assert code_at("EK-01-A03-FK-01", "area") == "EK-01-A03-FK"
    assert code_at("EK-01-A03-FK-01", "district") == "EK-01-A03"
    assert code_at("EK-01-A03-FK-01", "lga") == "EK-01"
    assert code_at(None, "area") is None


def test_typed_codes_are_trusted_only_as_far_as_nipost_confirms() -> None:
    assert from_typed(CODE, True, "ok").confidence == "high"
    assert from_typed(CODE, None, "no key").confidence == "medium"
    rejected = from_typed(CODE, False, "not assigned")
    assert (rejected.status, rejected.code) == ("unresolved", None)


@pytest.mark.parametrize(
    ("distance", "status", "level", "code", "confidence"),
    [
        (4.0, "resolved", "building", "EK-01-A03-FK-01", "high"),
        (20.0, "resolved", "building", "EK-01-A03-FK-01", "medium"),
        (40.0, "partial", "area", "EK-01-A03-FK", "medium"),
    ],
)
def test_location_pins(
    distance: float, status: str, level: str, code: str, confidence: str
) -> None:
    result = from_location(found(distance))
    assert (result.status, result.level, result.code, result.confidence) == (
        status,
        level,
        code,
        confidence,
    )


def test_location_with_no_building_asks_to_move_the_pin() -> None:
    result = from_location(NOTHING)
    assert (result.status, result.code) == ("unresolved", None)
    assert result.question is not None
    assert "pin" in result.question


def test_the_landmark_itself_resolves_to_its_building() -> None:
    result = from_geocoded(
        found(8.0), place("building"), Landmark(name="Fabian Hotel", relation="at")
    )
    assert (result.status, result.level, result.code) == ("resolved", "building", "EK-01-A03-FK-01")


@pytest.mark.parametrize("relation", ["behind", "opposite", "near", "beside"])
def test_a_building_near_a_landmark_only_gets_the_area(relation: Relation) -> None:
    landmark = Landmark(name="Fabian Hotel", relation=relation)
    result = from_geocoded(found(8.0), place("building"), landmark)
    assert (result.status, result.level, result.code) == ("partial", "area", "EK-01-A03-FK")
    assert result.question is not None
    assert f"{relation} Fabian Hotel" in result.question


def test_a_street_only_gets_the_district_at_low_confidence() -> None:
    result = from_geocoded(found(120.0), place("street"), None)
    assert (result.status, result.level, result.code, result.confidence) == (
        "partial",
        "district",
        "EK-01-A03",
        "low",
    )


def test_a_town_is_too_broad_for_any_code() -> None:
    result = from_geocoded(None, place("locality"), None)
    assert (result.status, result.code) == ("unresolved", None)


def test_a_far_building_is_not_the_place() -> None:
    result = from_geocoded(found(45.0), place("building"), None)
    assert (result.status, result.level) == ("partial", "area")


def test_landmark_for_matches_the_successful_query() -> None:
    address = parsed(("Fabian Hotel", "behind"))
    assert landmark_for("Fabian Hotel, Ado Ekiti", address) == Landmark(
        name="Fabian Hotel", relation="behind"
    )
    assert landmark_for("NTA Road, Ado Ekiti", address) is None
    assert landmark_for("anything", None) is None
