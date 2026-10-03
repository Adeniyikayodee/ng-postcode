from __future__ import annotations

import json

import pytest

from ng_postcode import Postcode, Segment, parse
from ng_postcode.api import (
    AdministrativeAddress,
    ApiError,
    Coordinate,
    autocomplete,
    decode,
    lookup,
    nearby,
    reverse,
)

HERE = Coordinate(lat=7.62, lng=5.22)


def code(text: str) -> Postcode:
    parsed = parse(text)
    assert isinstance(parsed, Postcode)
    return parsed


def body(data: object) -> str:
    return json.dumps({"data": data})


def test_builds_requests() -> None:
    request = lookup(code("ek01a03fk01"), 3)
    assert (request.path, request.params) == (
        "/v1/lookup",
        (("code", "EK-01-A03-FK-01"), ("level", "3")),
    )
    assert autocomplete("EK 01 A").params == (("q", "EK 01 A"),)
    assert reverse(HERE, 100.0).params == (
        ("lat", "7.62"),
        ("lng", "5.22"),
        ("max_distance_m", "100"),
    )
    assert nearby(HERE).params == (("lat", "7.62"), ("lng", "5.22"))


def test_decodes_the_documented_lookup() -> None:
    data = {
        "postcode": "EK-01-A03-FK-01",
        "valid": True,
        "administrative_address": {
            "state_name": "EKITI",
            "lga_name": "ADO EKITI",
            "locality_name": "ADO EKITI",
            "zone": "SOUTH WEST",
        },
        "recent_house_address": {"recent": "NTA ROAD, BACK OF FABIAN HOTEL, ADO EKITI"},
        "building_use_status": "residential",
    }
    found = decode(lookup(code("EK-01-A03-FK-01"), 3), 200, body(data))
    assert not isinstance(found, ApiError)
    assert found.valid
    assert found.administrative_address == AdministrativeAddress(
        "EKITI", "ADO EKITI", "ADO EKITI", "SOUTH WEST"
    )
    assert found.recent_house_address == "NTA ROAD, BACK OF FABIAN HOTEL, ADO EKITI"
    assert (found.building_use_status, found.point_geometry) == ("residential", None)


def test_fields_above_the_granted_level_are_none() -> None:
    data = {"postcode": "EK-01-A03-FK-01", "valid": True}
    found = decode(lookup(code("EK-01-A03-FK-01")), 200, body(data))
    assert not isinstance(found, ApiError)
    assert (found.administrative_address, found.recent_house_address) == (None, None)


def test_decodes_documented_labels_and_echoed_coordinates() -> None:
    data = {"segment": "lga", "suggestions": [{"code": "01", "label": "ADO EKITI"}]}
    found = decode(autocomplete("EK"), 200, body(data))
    assert not isinstance(found, ApiError)
    assert found.segment is Segment.LGA
    assert (found.suggestions[0].code, found.suggestions[0].label) == ("01", "ADO EKITI")

    miss = {"found": False, "coordinate": [5.22, 7.62], "message": "none", "radius_m": 25}
    result = decode(reverse(HERE), 200, body(miss))
    assert not isinstance(result, ApiError)
    assert result.coordinate == HERE


def test_an_empty_autocomplete_is_refused_before_it_hangs_the_api() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        autocomplete("  ")


def test_error_envelopes_and_bad_bodies_become_values() -> None:
    request = lookup(code("EK-01-A03-FK-01"))
    # What the live API answered on 2 October 2026 when called without a key.
    refused = '{"error":{"code":"auth_required","message":"an API key is required"}}'
    assert decode(request, 401, refused) == ApiError(401, "auth_required", "an API key is required")
    for status, text in [(502, "<html>Bad Gateway</html>"), (200, "[]"), (200, '{"data": 1}')]:
        error = decode(request, status, text)
        assert isinstance(error, ApiError)
        assert (error.status, error.code) == (status, "malformed_response")


def test_rejects_requests_the_api_cannot_answer() -> None:
    code = Postcode("EK01A03FK01")
    for level in (0, 6):
        with pytest.raises(ValueError, match="level must be 1 to 5"):
            lookup(code, level)
    for bad in (float("nan"), float("inf")):
        with pytest.raises(ValueError, match="finite"):
            reverse(Coordinate(lat=bad, lng=5.2))
        with pytest.raises(ValueError, match="finite"):
            nearby(Coordinate(lat=7.6, lng=5.2), bad)
