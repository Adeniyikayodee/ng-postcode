"""The workflow: typed postcode, then location pin, then text. Each step is optional,
and a missing one lowers precision instead of failing."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from ng_postcode import Postcode
from ng_postcode.api import ApiError, Coordinate, lookup, reverse
from ng_postcode.client import AsyncClient, TransportError

from .core import (
    SEARCH_RADIUS_M,
    find_typed_postcode,
    from_geocoded,
    from_location,
    from_typed,
    is_the_place,
    landmark_for,
    unresolved,
    written_as_code,
)
from .geocode import GeocodeFailure
from .models import Geocoded, ParsedAddress, ParseFailure, Resolution

Parser = Callable[[str], Awaitable[ParsedAddress | ParseFailure]]
Geocoder = Callable[[str], Awaitable[Geocoded | GeocodeFailure | None]]

LOCATION_RADIUS_M = 50.0
MAX_QUERIES = 3
NO_NIPOST = "NG_POSTCODE_API_KEY is not set, so NIPOST cannot be asked for the postcode."


@dataclass(frozen=True)
class Resolver:
    nipost: AsyncClient | None = None
    parser: Parser | None = None
    geocoder: Geocoder | None = None

    async def resolve(
        self,
        text: str,
        location: Coordinate | None = None,
        parsed: ParsedAddress | None = None,
    ) -> Resolution:
        """Resolve `text`. A caller that has already read the address, such as a host
        model, passes its reading as `parsed`, which replaces the parser."""
        typed = find_typed_postcode(text)
        before: list[str] = []
        if typed is not None:
            assigned, note = await self._assigned(typed)
            strict = written_as_code(text, typed)
            if assigned or (strict and (assigned is None or location is None)):
                return from_typed(typed, assigned, note)
            # An unassigned code is a typo, and an unconfirmed spaced one may be plain words.
            lead = (
                f"Postcode {typed} is written in the address."
                if strict
                else f"'{typed.spaced}' in the address may be a postcode."
            )
            before = [lead, note]
        if location is not None:
            return with_evidence(before, await self._by_location(location), None)
        return with_evidence(before, await self._by_text(text, parsed), None)

    async def _assigned(self, code: Postcode) -> tuple[bool | None, str]:
        if self.nipost is None:
            return None, "Not confirmed with NIPOST: no API key."
        result = await self.nipost.send(lookup(code, 1))
        if isinstance(result, ApiError | TransportError):
            return None, f"Not confirmed with NIPOST: {result}."
        note = (
            "NIPOST confirms it is assigned." if result.valid else "NIPOST says it is not assigned."
        )
        return result.valid, note

    async def _by_location(self, at: Coordinate) -> Resolution:
        if self.nipost is None:
            return unresolved("location", NO_NIPOST)
        found = await self.nipost.send(reverse(at, LOCATION_RADIUS_M))
        if isinstance(found, ApiError | TransportError):
            return unresolved("location", f"NIPOST reverse geocoding failed: {found}.")
        return from_location(found)

    async def _by_text(self, text: str, given: ParsedAddress | None) -> Resolution:
        parsed, evidence = (
            (given, [f"Read the address as: {describe(given)}."])
            if given is not None
            else await self._parse(text)
        )
        queries = parsed.geocode_queries if parsed and parsed.geocode_queries else [text]
        place, searched = await self._place(queries)
        evidence += searched
        question = parsed.question if parsed and parsed.question else None
        if place is None:
            return with_evidence(evidence, unresolved("geocoded", "No map match."), question)
        evidence.append(f"Map match for '{place.query}': {place.label} ({place.precision}).")
        radius = SEARCH_RADIUS_M[place.precision]
        if radius is None:
            return with_evidence(evidence, from_geocoded(None, place, None, False), question)
        if self.nipost is None:
            return with_evidence(evidence, unresolved("geocoded", NO_NIPOST), question)
        found = await self.nipost.send(reverse(Coordinate(lat=place.lat, lng=place.lng), radius))
        if isinstance(found, ApiError | TransportError):
            failure = unresolved("geocoded", f"NIPOST reverse geocoding failed: {found}.")
            return with_evidence(evidence, failure, question)
        landmark = landmark_for(place.query, parsed)
        decision = from_geocoded(found, place, landmark, is_the_place(landmark, parsed))
        return with_evidence(evidence, decision, None)

    async def _parse(self, text: str) -> tuple[ParsedAddress | None, list[str]]:
        if self.parser is None:
            return None, ["No reading of the address was available, so the raw text was searched."]
        parsed = await self.parser(text)
        if isinstance(parsed, ParseFailure):
            return None, [f"Could not read the address with Claude ({parsed.reason})."]
        return parsed, [f"Read the address as: {describe(parsed)}."]

    async def _place(self, queries: list[str]) -> tuple[Geocoded | None, list[str]]:
        if self.geocoder is None:
            return None, ["No geocoder configured (NG_GEOCODER_URL)."]
        notes: list[str] = []
        for query in queries[:MAX_QUERIES]:
            hit = await self.geocoder(query)
            if isinstance(hit, GeocodeFailure):
                return None, [*notes, f"Geocoding failed: {hit.reason}."]
            if hit is not None:
                return hit, notes
            notes.append(f"No map match for '{query}'.")
        return None, notes


def with_evidence(before: list[str], decision: Resolution, question: str | None) -> Resolution:
    """The decision with the earlier steps' evidence first, and a better question if one exists."""
    update: dict[str, object] = {"evidence": [*before, *decision.evidence]}
    if question and decision.status == "unresolved":
        update["question"] = question
    return decision.model_copy(update=update)


def describe(parsed: ParsedAddress) -> str:
    parts = [
        " ".join(p for p in (parsed.house_number, parsed.street) if p),
        *(f"{lm.relation} {lm.name}" for lm in parsed.landmarks),
        parsed.locality,
        parsed.lga,
        parsed.state,
    ]
    return ", ".join(p for p in parts if p) or "nothing placeable"
