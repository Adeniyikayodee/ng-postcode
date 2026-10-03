"""resolve_address through a real MCP client, with NIPOST and the geocoder mocked."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from mcp import Client
from mcp.types import CallToolResult

from ng_postcode_mcp import Settings, create_server, settings_from_env

PLACES = {"Fabian Hotel, Ado Ekiti, Ekiti": 30, "NTA Road, Ado Ekiti, Ekiti": 26}
BEHIND_FABIAN = {
    "address": "back of Fabian Hotel, off NTA Road, Ado Ekiti",
    "landmarks": [{"name": "Fabian Hotel", "relation": "behind"}],
    "geocode_queries": ["Fabian Hotel, Ado Ekiti, Ekiti", "NTA Road, Ado Ekiti, Ekiti"],
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def nipost(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/v1/lookup":
        return httpx.Response(200, json={"data": {"postcode": "EK-01-A03-FK-01", "valid": True}})
    unit = {"postcode": "EK-01-A03-FK-01", "display": "EK 01 A03 FK 01", "distance_m": 8.0}
    data = {"found": True, "unit": unit, "area": "EK-01-A03-FK", "district": "EK-01-A03"}
    return httpx.Response(200, json={"data": data})


async def call(
    arguments: dict[str, Any],
    *,
    geocoder: bool = True,
    searched: list[httpx.Request] | None = None,
) -> CallToolResult:
    def geocode(request: httpx.Request) -> httpx.Response:
        if searched is not None:
            searched.append(request)
        query = request.url.params["q"]
        rank = PLACES.get(query)
        hit = {"lat": "7.62", "lon": "5.19", "place_rank": rank, "display_name": query}
        return httpx.Response(200, json=[hit] if rank else [])

    settings = Settings(
        api_key="good",
        geocoder_url="https://geo.example" if geocoder else None,
        geocoder_contact="ops@example.com",
    )
    nipost_http = httpx.AsyncClient(transport=httpx.MockTransport(nipost))
    geocoder_http = httpx.AsyncClient(transport=httpx.MockTransport(geocode))
    server = create_server(settings, http=nipost_http, geocoder_http=geocoder_http)
    async with Client(server) as client:
        result = await client.call_tool("resolve_address", arguments)
    await nipost_http.aclose()
    await geocoder_http.aclose()
    return result


@pytest.mark.anyio
async def test_the_host_models_reading_drives_the_answer() -> None:
    searched: list[httpx.Request] = []
    result = await call(BEHIND_FABIAN, searched=searched)
    assert not result.is_error
    answer = result.structured_content
    assert (answer["status"], answer["level"], answer["code"]) == (
        "partial",
        "area",
        "EK-01-A03-FK",
    )
    assert "behind Fabian Hotel" in answer["question"]
    assert [r.url.params["q"] for r in searched] == ["Fabian Hotel, Ado Ekiti, Ekiti"]
    assert searched[0].headers["User-Agent"].startswith("ng-postcode-mcp/")
    assert "ops@example.com" in searched[0].headers["User-Agent"]


@pytest.mark.anyio
async def test_a_typed_postcode_needs_no_geocoder() -> None:
    searched: list[httpx.Request] = []
    result = await call({"address": "deliver to ek01a03fk01"}, searched=searched)
    answer = result.structured_content
    assert (answer["status"], answer["code"], answer["confidence"]) == (
        "resolved",
        "EK-01-A03-FK-01",
        "high",
    )
    assert searched == []


@pytest.mark.anyio
async def test_a_location_pin_gives_the_building() -> None:
    result = await call({"address": "my house", "latitude": 7.62, "longitude": 5.19})
    answer = result.structured_content
    assert (answer["level"], answer["method"], answer["code"]) == (
        "building",
        "location",
        "EK-01-A03-FK-01",
    )


@pytest.mark.anyio
async def test_without_a_geocoder_it_explains_and_asks() -> None:
    result = await call(BEHIND_FABIAN, geocoder=False)
    assert not result.is_error
    answer = result.structured_content
    assert (answer["status"], answer["code"]) == ("unresolved", None)
    assert any("NG_GEOCODER_URL" in line for line in answer["evidence"])
    assert answer["question"]


@pytest.mark.anyio
async def test_half_a_coordinate_is_an_error_the_model_can_fix() -> None:
    result = await call({"address": "my house", "latitude": 7.62})
    assert result.is_error


@pytest.mark.anyio
async def test_schemas_guide_the_host_model() -> None:
    async with Client(create_server(Settings(api_key=None))) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
    tool = tools["resolve_address"]
    assert tool.input_schema["required"] == ["address"]
    relations = tool.input_schema["$defs"]["Landmark"]["properties"]["relation"]["enum"]
    assert {"at", "behind", "opposite"} <= set(relations)
    assert tool.input_schema["properties"]["geocode_queries"]["anyOf"][0]["maxItems"] == 3
    assert tool.output_schema is not None
    assert {"status", "code", "level", "confidence", "question", "evidence"} <= set(
        tool.output_schema["properties"]
    )


def test_geocoder_settings() -> None:
    public = {"NG_GEOCODER_URL": "https://nominatim.openstreetmap.org/"}
    assert settings_from_env(public) == (
        "the public Nominatim requires NG_GEOCODER_CONTACT, a URL or email identifying you"
    )
    configured = settings_from_env(public | {"NG_GEOCODER_CONTACT": "https://example.com"})
    assert isinstance(configured, Settings)
    assert configured.geocoder_url == "https://nominatim.openstreetmap.org"
    assert settings_from_env({}) == Settings(api_key=None)
