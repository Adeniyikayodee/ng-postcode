"""The whole workflow with fake parser and geocoder, and a mocked NIPOST API."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from typing import Any

import httpx
import pytest
from ng_postcode.api import Coordinate
from ng_postcode.client import AsyncClient

from ng_address.geocode import GeocodeFailure
from ng_address.models import (
    Geocoded,
    Landmark,
    ParsedAddress,
    ParseFailure,
    Precision,
    Relation,
)
from ng_address.resolve import Resolver


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def nipost(distance_m: float = 6.0, *, valid: bool = True, found: bool = True) -> AsyncClient:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/lookup":
            return httpx.Response(
                200, json={"data": {"postcode": "EK-01-A03-FK-01", "valid": valid}}
            )
        data: dict[str, Any] = {
            "found": found,
            "radius_m": float(request.url.params.get("max_distance_m", 25)),
        }
        if found:
            unit = {
                "postcode": "EK-01-A03-FK-01",
                "display": "EK 01 A03 FK 01",
                "distance_m": distance_m,
            }
            data |= {"unit": unit, "area": "EK-01-A03-FK", "district": "EK-01-A03", "state": "EK"}
        return httpx.Response(200, json={"data": data})

    return AsyncClient("key", http=httpx.AsyncClient(transport=httpx.MockTransport(handle)))


def reading(relation: Relation | None, question: str | None = None) -> ParsedAddress:
    landmarks = [Landmark(name="Fabian Hotel", relation=relation)] if relation else []
    return ParsedAddress(
        house_number=None,
        street="NTA Road",
        landmarks=landmarks,
        locality=None,
        lga="Ado Ekiti",
        state="Ekiti",
        geocode_queries=["Fabian Hotel, Ado Ekiti", "NTA Road, Ado Ekiti"],
        question=question,
    )


def parser_returning(result: ParsedAddress | ParseFailure) -> Any:
    async def parse(text: str) -> ParsedAddress | ParseFailure:
        return result

    return parse


class FakeGeocoder:
    def __init__(self, places: dict[str, Precision]) -> None:
        self.places = places
        self.searched: list[str] = []

    async def __call__(self, query: str) -> Geocoded | GeocodeFailure | None:
        self.searched.append(query)
        precision = self.places.get(query)
        if precision is None:
            return None
        return Geocoded(query=query, lat=7.62, lng=5.19, precision=precision, label=query)


@pytest.mark.anyio
async def test_a_typed_postcode_short_circuits_and_is_confirmed() -> None:
    result = await Resolver(nipost=nipost()).resolve("Deliver to ek01a03fk01")
    assert (result.status, result.code, result.confidence) == (
        "resolved",
        "EK-01-A03-FK-01",
        "high",
    )

    unassigned = await Resolver(nipost=nipost(valid=False)).resolve("Deliver to ek01a03fk01")
    assert (unassigned.status, unassigned.code) == ("unresolved", None)

    unchecked = await Resolver().resolve("Deliver to ek01a03fk01")
    assert (unchecked.confidence, unchecked.evidence[-1]) == (
        "medium",
        "Not confirmed with NIPOST: no API key.",
    )


@pytest.mark.anyio
async def test_a_location_pin_gives_the_building() -> None:
    result = await Resolver(nipost=nipost(4.0)).resolve("anything", Coordinate(lat=7.62, lng=5.19))
    assert (result.status, result.level, result.method) == ("resolved", "building", "location")


@pytest.mark.anyio
async def test_behind_a_landmark_gives_only_the_area() -> None:
    resolver = Resolver(
        nipost=nipost(),
        parser=parser_returning(reading("behind")),
        geocoder=FakeGeocoder({"Fabian Hotel, Ado Ekiti": "building"}),
    )
    result = await resolver.resolve("back of Fabian Hotel, NTA Road, Ado Ekiti")
    assert (result.status, result.level, result.code) == ("partial", "area", "EK-01-A03-FK")
    assert result.evidence[0].startswith("Read the address as:")


@pytest.mark.anyio
async def test_falls_through_queries_to_the_street() -> None:
    geocode = FakeGeocoder({"NTA Road, Ado Ekiti": "street"})
    resolver = Resolver(
        nipost=nipost(140.0), parser=parser_returning(reading("behind")), geocoder=geocode
    )
    result = await resolver.resolve("back of Fabian Hotel, NTA Road, Ado Ekiti")
    assert (result.level, result.code, result.confidence) == ("district", "EK-01-A03", "low")
    assert geocode.searched == ["Fabian Hotel, Ado Ekiti", "NTA Road, Ado Ekiti"]
    assert "No map match for 'Fabian Hotel, Ado Ekiti'." in result.evidence


@pytest.mark.anyio
async def test_nothing_found_uses_claudes_question() -> None:
    resolver = Resolver(
        nipost=nipost(),
        parser=parser_returning(reading(None, question="Which street is the house on?")),
        geocoder=FakeGeocoder({}),
    )
    result = await resolver.resolve("my house")
    assert (result.status, result.question) == ("unresolved", "Which street is the house on?")


@pytest.mark.anyio
async def test_degrades_without_claude_or_nipost() -> None:
    geocode = FakeGeocoder({"NTA Road, Ado Ekiti": "street"})
    failing = parser_returning(ParseFailure("Claude credentials are missing or invalid"))
    result = await Resolver(parser=failing, geocoder=geocode).resolve("NTA Road, Ado Ekiti")
    assert geocode.searched == ["NTA Road, Ado Ekiti"]
    assert result.status == "unresolved"
    assert any("Claude credentials" in e for e in result.evidence)
    assert any("NG_POSTCODE_API_KEY" in e for e in result.evidence)


@pytest.mark.anyio
async def test_a_reading_from_the_caller_replaces_the_parser() -> None:
    async def never(text: str) -> ParsedAddress | ParseFailure:
        raise AssertionError("the parser must not run when a reading is supplied")

    resolver = Resolver(
        nipost=nipost(),
        parser=never,
        geocoder=FakeGeocoder({"Fabian Hotel, Ado Ekiti": "building"}),
    )
    result = await resolver.resolve("back of Fabian Hotel", parsed=reading("opposite"))
    assert (result.level, result.code) == ("area", "EK-01-A03-FK")
    assert result.question is not None
    assert "opposite Fabian Hotel" in result.question


def test_the_core_imports_without_the_anthropic_sdk() -> None:
    check = "import sys, ng_address, ng_address.cli; sys.exit('anthropic' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", check], check=False).returncode == 0


@pytest.mark.anyio
async def test_raw_text_matching_a_building_gives_only_the_area() -> None:
    text = "back of Fabian Hotel, NTA Road, Ado Ekiti"
    resolver = Resolver(nipost=nipost(), geocoder=FakeGeocoder({text: "building"}))
    result = await resolver.resolve(text)
    assert (result.status, result.level, result.code) == ("partial", "area", "EK-01-A03-FK")


@pytest.mark.anyio
async def test_an_unassigned_typed_code_falls_back_to_the_pin() -> None:
    resolver = Resolver(nipost=nipost(4.0, valid=False))
    result = await resolver.resolve("Deliver to ek01a03fk01", Coordinate(lat=7.62, lng=5.19))
    assert (result.status, result.level, result.method) == ("resolved", "building", "location")
    assert result.evidence[1] == "NIPOST says it is not assigned."


@pytest.mark.anyio
async def test_a_spaced_code_counts_only_when_nipost_confirms_it() -> None:
    text = "No 12 Oba St 45, Ikeja"
    for client in (nipost(valid=False), None):
        geocode = FakeGeocoder({text: "street"})
        result = await Resolver(nipost=client, geocoder=geocode).resolve(text)
        assert geocode.searched == [text]
        assert result.method == "geocoded"
        assert result.evidence[0] == "'NO 12 OBA ST 45' in the address may be a postcode."

    confirmed = await Resolver(nipost=nipost()).resolve("my code is ek 01 a03 fk 01")
    assert (confirmed.status, confirmed.method, confirmed.confidence) == (
        "resolved",
        "typed",
        "high",
    )


@pytest.mark.anyio
async def test_map_searches_stop_at_the_budget() -> None:
    async def stuck(query: str) -> Geocoded | GeocodeFailure | None:
        await asyncio.sleep(5)
        return None

    result = await Resolver(geocoder=stuck, geocode_budget_s=0.05).resolve("NTA Road")
    assert result.status == "unresolved"
    assert "Geocoding took longer than 0.05 s." in result.evidence


@pytest.mark.parametrize("pin", [["--lat", "nan", "--lng", "5"], ["--lat", "7", "--lng", "500"]])
def test_the_cli_rejects_a_pin_off_the_map(pin: list[str]) -> None:
    from ng_address.cli import main

    with pytest.raises(SystemExit) as stopped:
        main(["somewhere", *pin])
    assert stopped.value.code == 2
