"""Pure decisions: no I/O, and the same evidence always gives the same answer.

The rule throughout is that an answer is never more precise than its evidence.
A landmark's own building is not the building "behind" it, and the middle of a
road is not any house on it.
"""

from __future__ import annotations

import re

from ng_postcode import Postcode, Segment, parse
from ng_postcode.api import Reverse

from .models import Geocoded, Landmark, Level, Method, ParsedAddress, Precision, Resolution

BUILDING_RADIUS_M = 25.0
"""A building this close to the point is taken to be the place itself."""

SEARCH_RADIUS_M: dict[Precision, float | None] = {
    "building": 50.0,
    "street": 250.0,
    "locality": None,
}

DEFAULT_QUESTION = "Can you share a location pin, or the street and a nearby landmark?"

_LEVEL_SEGMENT = {
    "building": Segment.UNIT,
    "area": Segment.AREA,
    "district": Segment.DISTRICT,
    "lga": Segment.LGA,
}

_CANDIDATE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"[A-Za-z]{2}[ -]?\d{2}[ -]?[A-Za-z0-9]{3}[ -]?[A-Za-z]{2}[ -]?\d{2}"
    r"(?![A-Za-z0-9])"
)


def find_typed_postcode(text: str) -> Postcode | None:
    """The first well-formed postcode written in the text. Look-alikes are not corrected."""
    codes = (parse(match.group()) for match in _CANDIDATE.finditer(text))
    return next((code for code in codes if isinstance(code, Postcode)), None)


def written_as_code(text: str, code: Postcode) -> bool:
    """Whether the code stands hyphenated or compact. A spaced match can be ordinary
    words, as in "No 12 Oba St 45"."""
    upper = text.upper()
    return str(code) in upper or code.compact in upper


def precision_of(place_rank: int) -> Precision:
    """Nominatim ranks buildings and named places 30, roads 26 to 27, and areas lower."""
    if place_rank >= 28:
        return "building"
    return "street" if place_rank >= 26 else "locality"


def landmark_for(query: str, parsed: ParsedAddress | None) -> Landmark | None:
    """The landmark a successful map query was about, if any."""
    if parsed is None:
        return None
    text = query.casefold()
    return next((lm for lm in parsed.landmarks if lm.name.casefold() in text), None)


def is_the_place(landmark: Landmark | None, parsed: ParsedAddress | None) -> bool:
    """Whether the map match is the address itself rather than something near it.

    Without a reading there is no telling "Fabian Hotel" from "back of Fabian
    Hotel", and a landmark the query did not name may still be the one matched.
    A reading with no landmarks needs a house number to count.
    """
    if landmark is not None:
        return landmark.relation == "at"
    if parsed is None:
        return False
    if not parsed.landmarks:
        return parsed.house_number is not None
    return all(lm.relation == "at" for lm in parsed.landmarks)


def code_at(postcode: str | None, level: Level) -> str | None:
    """The code of the enclosing `level` for a full postcode."""
    code = parse(postcode or "")
    return code.prefix(_LEVEL_SEGMENT[level]) if isinstance(code, Postcode) else None


def from_typed(code: Postcode, assigned: bool | None, note: str) -> Resolution:
    if assigned is False:
        return Resolution(
            status="unresolved",
            code=None,
            level=None,
            confidence=None,
            method="typed",
            question=f"NIPOST says {code} is not assigned to a building. Can you check it?",
            evidence=[f"Postcode {code} is written in the address.", note],
        )
    return Resolution(
        status="resolved",
        code=str(code),
        level="building",
        confidence="high" if assigned else "medium",
        method="typed",
        question=None,
        evidence=[f"Postcode {code} is written in the address.", note],
    )


def from_location(found: Reverse) -> Resolution:
    unit = found.unit
    if not found.found or unit is None:
        return unresolved(
            "location",
            found.message or "NIPOST found no building within the search radius.",
            "No building was found at that location. Is the pin on the building itself?",
        )
    if unit.distance_m is not None and unit.distance_m <= BUILDING_RADIUS_M:
        return Resolution(
            status="resolved",
            code=unit.postcode,
            level="building",
            confidence="high" if unit.distance_m <= 10 else "medium",
            method="location",
            question=None,
            evidence=[
                f"Nearest building to the pin is {unit.postcode}, {unit.distance_m:.0f} m away."
            ],
        )
    return Resolution(
        status="partial",
        code=code_at(unit.postcode, "area"),
        level="area",
        confidence="medium",
        method="location",
        question="The pin is not on a building. Can you move it onto the building itself?",
        evidence=[
            f"Nearest building is {unit.postcode}, {unit.distance_m or 0:.0f} m from the pin."
        ],
    )


def from_geocoded(
    found: Reverse | None, place: Geocoded, landmark: Landmark | None, exact: bool
) -> Resolution:
    if place.precision == "locality" or found is None:
        return unresolved(
            "geocoded", f"Only placed as far as {place.label}, too broad for a postcode."
        )
    unit = found.unit
    if not found.found or unit is None:
        return unresolved("geocoded", f"NIPOST found no building near {place.label}.")
    near = (
        f"Nearest building to {place.label} is {unit.postcode}, {unit.distance_m or 0:.0f} m away."
    )
    if place.precision == "street":
        return Resolution(
            status="partial",
            code=code_at(unit.postcode, "district"),
            level="district",
            confidence="low",
            method="geocoded",
            question="What is the house number, or a landmark on that street? A location pin is "
            "most reliable.",
            evidence=["The map only placed the street, not a building.", near],
        )
    close = unit.distance_m is not None and unit.distance_m <= BUILDING_RADIUS_M
    if exact and close:
        return Resolution(
            status="resolved",
            code=unit.postcode,
            level="building",
            confidence="medium",
            method="geocoded",
            question=None,
            evidence=[near],
        )
    where = f"{landmark.relation} {landmark.name}" if landmark else f"near {place.label}"
    return Resolution(
        status="partial",
        code=code_at(unit.postcode, "area"),
        level="area",
        confidence="medium",
        method="geocoded",
        question=f"Which building {where} is it? A location pin or house number would pin it down.",
        evidence=[near, f"The address is {where}, not the place the map found."],
    )


def unresolved(method: Method | None, reason: str, question: str = DEFAULT_QUESTION) -> Resolution:
    return Resolution(
        status="unresolved",
        code=None,
        level=None,
        confidence=None,
        method=method,
        question=question,
        evidence=[reason],
    )
