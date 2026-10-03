"""The NIPOST Postcode API as plain data: requests to send and responses to decode.

Nothing here performs I/O, so it works with any HTTP client, sync or async.
Assembly and disassembly are not modelled: `parse` and `from_segments` do both
offline.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from ._postcode import Postcode, Segment

T = TypeVar("T")

BASE_URL = "https://api.postcode.gov.ng"

Params = tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Request(Generic[T]):
    """A GET request whose successful response decodes to `T`."""

    path: str
    params: Params
    read: Callable[[Any], T | None] = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class Coordinate:
    lat: float
    lng: float


@dataclass(frozen=True, slots=True)
class ApiError:
    """The API refused the request, with `code` taken from its error envelope
    (`auth_required`, `insufficient_credits`, ...), or its answer was not the
    documented envelope, with `code` set to `malformed_response`."""

    status: int
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code} ({self.status}): {self.message}"


@dataclass(frozen=True, slots=True)
class AdministrativeAddress:
    state_name: str | None
    lga_name: str | None
    locality_name: str | None
    zone: str | None


@dataclass(frozen=True, slots=True)
class Lookup:
    """Fields above the level granted to the key are `None`."""

    postcode: str
    valid: bool
    administrative_address: AdministrativeAddress | None
    """Level 2."""
    recent_house_address: str | None
    """Level 2."""
    building_use_status: str | None
    """Level 3."""
    other_building_info: Any
    """Level 4. Undocumented, so left as raw JSON."""
    point_geometry: Any
    """Level 5. Undocumented, so left as raw JSON."""
    status: str | None = None
    """`valid`, `not_found`, or `invalid` for a malformed code. Sent at every level."""
    verified: bool | None = None


@dataclass(frozen=True, slots=True)
class Suggestion:
    code: str
    """The value of the segment being completed, such as `A03`, not a full prefix."""
    label: str | None
    """Documented by NIPOST but not sent by the live API as of October 2026."""


@dataclass(frozen=True, slots=True)
class Autocomplete:
    segment: Segment | None
    """The segment the suggestions complete."""
    suggestions: tuple[Suggestion, ...]


@dataclass(frozen=True, slots=True)
class NearestUnit:
    postcode: str
    display: str
    distance_m: float | None
    confidence: str | None
    """`high`, `medium` or `low`, graded by distance."""
    state_name: str | None
    lga_name: str | None
    locality_name: str | None
    address: str | None
    """Recent house address. This and the names above need level 2."""


@dataclass(frozen=True, slots=True)
class Reverse:
    found: bool
    coordinate: Coordinate | None
    """The queried point, echoed back."""
    unit: NearestUnit | None
    """The nearest building, absent when nothing is in range."""
    area: str | None
    district: str | None
    state: str | None
    message: str | None
    """Set when nothing is in range."""
    radius_m: float | None
    """The radius the API actually applied."""
    depth: str | None = None
    """How deep the match goes, such as `unit`."""


@dataclass(frozen=True, slots=True)
class NearbyUnit:
    postcode: str
    display: str
    distance_m: float | None


def lookup(code: Postcode, level: int = 1) -> Request[Lookup]:
    """Resolve a postcode. Levels are cumulative from 1 (validity only) to 5, and
    the API caps the answer at the level granted to the key.

    Raises `ValueError` for a level outside 1 to 5.
    """
    if level not in range(1, 6):
        raise ValueError(f"level must be 1 to 5, got {level!r}")
    return Request("/v1/lookup", (("code", str(code)), ("level", str(level))), _lookup)


def autocomplete(partial: str) -> Request[Autocomplete]:
    """Suggest completions for a partial postcode such as `EK 01 A`.

    Raises `ValueError` for an empty `partial`: the live API never answers one.
    """
    if not partial.strip():
        raise ValueError("partial must not be empty")
    return Request("/v1/search/autocomplete", (("q", partial),), _autocomplete)


def reverse(at: Coordinate, max_distance_m: float | None = None) -> Request[Reverse]:
    """Find the postcode of the nearest building, within 25 m unless `max_distance_m`
    says otherwise. The API clamps it to 250 m.

    Raises `ValueError` for a coordinate or distance that is not a finite number.
    """
    return Request("/v1/search/reverse", _around(at, "max_distance_m", max_distance_m), _reverse)


def nearby(at: Coordinate, radius_m: float | None = None) -> Request[tuple[NearbyUnit, ...]]:
    """List buildings around a point, nearest first, within 300 m unless `radius_m`
    says otherwise. Empty when nothing is in range.

    Raises `ValueError` for a coordinate or radius that is not a finite number.
    """
    return Request("/v1/search/nearby", _around(at, "radius", radius_m), _nearby)


def decode(request: Request[T], status: int, body: str) -> T | ApiError:
    """Decode the response to `request` from its status and body."""
    try:
        envelope = json.loads(body)
    except ValueError as error:
        return _malformed(status, f"not JSON: {error}")
    if not isinstance(envelope, dict):
        return _malformed(status, "expected a JSON object")
    failure = envelope.get("error")
    if isinstance(failure, dict):
        code = _text(failure, "code") or "unknown_error"
        return ApiError(status, code, _text(failure, "message") or "")
    if isinstance(failure, str):
        return ApiError(status, "unknown_error", failure)
    if not 200 <= status < 300:
        return _malformed(status, "an error status without an error")
    data = request.read(envelope.get("data"))
    return data if data is not None else _malformed(status, "unexpected data")


def _around(at: Coordinate, key: str, metres: float | None) -> Params:
    point = (("lat", _number_text(at.lat)), ("lng", _number_text(at.lng)))
    return point if metres is None else (*point, (key, _number_text(metres)))


def _number_text(value: float) -> str:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"expected a finite number, got {value!r}")
    return str(int(number)) if number.is_integer() else repr(number)


def _malformed(status: int, message: str) -> ApiError:
    return ApiError(status, "malformed_response", message)


def _object(data: Mapping[str, Any], key: str) -> Mapping[str, Any] | None:
    value = data.get(key)
    return value if isinstance(value, dict) else None


def _text(data: Mapping[str, Any], key: str) -> str | None:
    value = data.get(key)
    return value if isinstance(value, str) else None


def _number(data: Mapping[str, Any], key: str) -> float | None:
    return _float(data.get(key))


def _float(value: Any) -> float | None:
    is_number = isinstance(value, int | float) and not isinstance(value, bool)
    return float(value) if is_number else None


def _nearby(data: Any) -> tuple[NearbyUnit, ...] | None:
    if not isinstance(data, list):
        return None
    return tuple(
        NearbyUnit(
            postcode=_text(item, "postcode") or "",
            display=_text(item, "display") or "",
            distance_m=_number(item, "distance_m"),
        )
        for item in data
        if isinstance(item, dict)
    )


def _lookup(data: Any) -> Lookup | None:
    if not isinstance(data, dict):
        return None
    admin = _object(data, "administrative_address")
    recent = _object(data, "recent_house_address")
    return Lookup(
        postcode=_text(data, "postcode") or "",
        valid=data.get("valid") is True,
        administrative_address=None
        if admin is None
        else AdministrativeAddress(
            state_name=_text(admin, "state_name"),
            lga_name=_text(admin, "lga_name"),
            locality_name=_text(admin, "locality_name"),
            zone=_text(admin, "zone"),
        ),
        recent_house_address=None if recent is None else _text(recent, "recent"),
        building_use_status=_text(data, "building_use_status"),
        other_building_info=data.get("other_building_info"),
        point_geometry=data.get("point_geometry"),
        status=_text(data, "status"),
        verified=data["verified"] if isinstance(data.get("verified"), bool) else None,
    )


def _autocomplete(data: Any) -> Autocomplete | None:
    if not isinstance(data, dict):
        return None
    items = data.get("suggestions")
    suggestions = tuple(
        Suggestion(code=_text(item, "code") or "", label=_text(item, "label"))
        for item in (items if isinstance(items, list) else [])
        if isinstance(item, dict)
    )
    segment = next((s for s in Segment if s.value == data.get("segment")), None)
    return Autocomplete(segment=segment, suggestions=suggestions)


def _reverse(data: Any) -> Reverse | None:
    if not isinstance(data, dict):
        return None
    unit = _object(data, "unit")
    return Reverse(
        found=data.get("found") is True,
        coordinate=_coordinate(data.get("coordinate")),
        unit=None
        if unit is None
        else NearestUnit(
            postcode=_text(unit, "postcode") or "",
            display=_text(unit, "display") or "",
            distance_m=_number(unit, "distance_m"),
            confidence=_text(unit, "confidence"),
            state_name=_text(unit, "state_name"),
            lga_name=_text(unit, "lga_name"),
            locality_name=_text(unit, "locality_name"),
            address=_text(unit, "address"),
        ),
        area=_text(data, "area"),
        district=_text(data, "district"),
        state=_text(data, "state"),
        message=_text(data, "message"),
        radius_m=_number(data, "radius_m"),
        depth=_text(data, "depth"),
    )


def _coordinate(value: Any) -> Coordinate | None:
    """The API echoes points as `[lng, lat]`."""
    if not isinstance(value, list) or len(value) != 2:
        return None
    lng, lat = (_float(v) for v in value)
    return None if lng is None or lat is None else Coordinate(lat=lat, lng=lng)
