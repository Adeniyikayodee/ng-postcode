"""Tool behaviour through a real MCP client, in process, with the NIPOST API mocked."""

from __future__ import annotations

import dataclasses
import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from mcp import Client
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult, TextContent
from ng_postcode import api
from ng_postcode.api import ApiError
from pydantic import BaseModel

from ng_postcode_mcp import Settings, create_server, settings_from_env
from ng_postcode_mcp.server import (
    Address,
    Completion,
    Location,
    NearestBuilding,
    PostcodeDetails,
    capped,
    unwrap,
)

Handler = Callable[[httpx.Request], httpx.Response]

LOOKUP = {
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


CALLS_SPEC = Path(__file__).resolve().parents[2] / "spec" / "mcp-calls.json"
# The shared calls live in the repository, not the sdist.
CALLS: list[dict[str, Any]] = (
    json.loads(CALLS_SPEC.read_text(encoding="utf-8"))["calls"] if CALLS_SPEC.exists() else []
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def nipost(seen: list[httpx.Request]) -> Handler:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.headers.get("X-API-Key") != "good":
            error = {"code": "invalid_api_key", "message": "the provided API key is invalid"}
            return httpx.Response(401, json={"error": error})
        if request.url.path == "/v1/lookup":
            return httpx.Response(200, json={"data": LOOKUP})
        if request.url.path == "/v1/search/reverse":
            return httpx.Response(200, json={"data": {"found": False, "radius_m": 25}})
        if request.url.path == "/v1/search/autocomplete":
            suggestion = {"code": "EK-01", "label": "ADO EKITI"}
            return httpx.Response(
                200, json={"data": {"segment": "lga", "suggestions": [suggestion]}}
            )
        return httpx.Response(404, json={"error": {"code": "not_found", "message": "no route"}})

    return handle


async def call(
    name: str,
    arguments: dict[str, Any],
    *,
    key: str | None = "good",
    max_level: int = 1,
    seen: list[httpx.Request] | None = None,
) -> CallToolResult:
    http = httpx.AsyncClient(
        transport=httpx.MockTransport(nipost(seen if seen is not None else []))
    )
    server = create_server(Settings(api_key=key, max_level=max_level), http=http)
    async with Client(server) as client:
        result = await client.call_tool(name, arguments)
    await http.aclose()
    return result


def text(result: CallToolResult) -> str:
    return " ".join(block.text for block in result.content if isinstance(block, TextContent))


@pytest.mark.anyio
async def test_lists_five_read_only_tools_with_schemas() -> None:
    async with Client(create_server(Settings(api_key=None))) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
        instructions = client.instructions or ""
    assert set(tools) == {
        "validate_postcode",
        "lookup_postcode",
        "autocomplete_postcode",
        "find_postcode_at_location",
        "resolve_address",
    }
    for tool in tools.values():
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert tool.description
        assert tool.output_schema is not None
    assert tools["validate_postcode"].annotations.open_world_hint is False  # type: ignore[union-attr]
    assert "lookup_postcode_details" not in instructions
    assert "ctx" not in tools["lookup_postcode"].input_schema["properties"]


@pytest.mark.anyio
async def test_a_tool_that_can_spend_is_never_marked_read_only_or_safe_to_retry() -> None:
    async with Client(create_server(Settings(api_key=None, max_level=5))) as client:
        tools = (await client.list_tools()).tools
        instructions = client.instructions or ""
    paid = [
        tool
        for tool in tools
        if tool.input_schema["properties"].get("level", {}).get("maximum", 1) > 1
    ]
    assert [tool.name for tool in paid] == ["lookup_postcode_details"]
    for tool in paid:
        assert tool.annotations is not None
        assert (tool.annotations.read_only_hint, tool.annotations.idempotent_hint) == (False, False)
    assert "lookup_postcode_details" in instructions


@pytest.mark.anyio
async def test_validate_works_offline_without_a_key() -> None:
    result = await call("validate_postcode", {"postcode": "ek 01 a03 fk 01"}, key=None)
    assert not result.is_error
    assert result.structured_content["postcode"] == "EK-01-A03-FK-01"
    assert result.structured_content["segments"]["district"] == "A03"


@pytest.mark.anyio
async def test_validate_suggests_but_does_not_apply_fixes() -> None:
    result = await call("validate_postcode", {"postcode": "EK-O1-A03-FK-01"}, key=None)
    assert not result.is_error
    data = result.structured_content
    assert (data["valid"], data["postcode"]) == (False, None)
    assert (data["error"], data["suggestion"]) == ("invalid lga segment", "EK-01-A03-FK-01")


@pytest.mark.anyio
async def test_lookup_returns_the_address_within_the_cap() -> None:
    seen: list[httpx.Request] = []
    result = await call(
        "lookup_postcode_details", {"postcode": "ek01a03fk01"}, max_level=2, seen=seen
    )
    assert not result.is_error, text(result)
    assert result.structured_content["administrative_address"]["zone"] == "SOUTH WEST"
    assert dict(seen[0].url.params) == {"code": "EK-01-A03-FK-01", "level": "2"}


@pytest.mark.anyio
async def test_lookup_refuses_paid_levels_above_the_cap_without_calling_the_api() -> None:
    seen: list[httpx.Request] = []
    above = {"postcode": "EK-01-A03-FK-01", "level": 3}
    result = await call("lookup_postcode_details", above, max_level=2, seen=seen)
    assert result.is_error
    assert "NG_POSTCODE_MAX_LEVEL" in text(result)
    assert seen == []


@pytest.mark.anyio
async def test_paid_lookups_stop_at_the_ceiling_but_a_callers_own_key_does_not() -> None:
    seen: list[httpx.Request] = []
    http = httpx.AsyncClient(transport=httpx.MockTransport(nipost(seen)))
    settings = Settings(api_key="good", max_level=2, max_paid_calls=2)
    code = {"postcode": "EK-01-A03-FK-01"}
    async with Client(create_server(settings, http=http)) as client:
        results = [await client.call_tool("lookup_postcode_details", code) for _ in range(3)]
        typo = await client.call_tool("lookup_postcode_details", {"postcode": "EK-01"})
        free = await client.call_tool("lookup_postcode", code)
    await http.aclose()
    assert [result.is_error for result in results] == [False, False, True]
    assert "NG_POSTCODE_MAX_PAID_CALLS" in text(results[2])
    assert "not a valid postcode" in text(typo)
    assert not free.is_error
    assert [request.url.params["level"] for request in seen] == ["2", "2", "1"]


@pytest.mark.anyio
async def test_lookup_never_autocorrects_before_spending() -> None:
    seen: list[httpx.Request] = []
    result = await call("lookup_postcode", {"postcode": "EK-O1-A03-FK-01"}, seen=seen)
    assert result.is_error
    assert "Did you mean EK-01-A03-FK-01? Confirm with the user first." in text(result)
    assert seen == []


@pytest.mark.anyio
async def test_online_tools_explain_a_missing_or_rejected_key() -> None:
    missing = await call("lookup_postcode", {"postcode": "EK-01-A03-FK-01"}, key=None)
    assert missing.is_error
    assert "needs a NIPOST API key" in text(missing)

    secret = "nipost_test_never_echo_me"
    rejected = await call("lookup_postcode", {"postcode": "EK-01-A03-FK-01"}, key=secret)
    assert rejected.is_error
    assert "invalid_api_key (401)" in text(rejected)
    assert "create a new key" in text(rejected)
    assert secret not in text(rejected)


@pytest.mark.anyio
async def test_autocomplete_and_reverse() -> None:
    found = await call("autocomplete_postcode", {"partial": "EK"})
    assert not found.is_error
    assert found.structured_content["suggestions"][0]["code"] == "EK-01"

    near = await call("find_postcode_at_location", {"latitude": 7.62, "longitude": 5.22})
    assert not near.is_error
    assert (near.structured_content["found"], near.structured_content["radius_m"]) == (False, 25.0)


def test_the_level_cap_withholds_names_and_addresses() -> None:
    unit = NearestBuilding(
        postcode="EK-01-A03-FK-01",
        display="EK 01 A03 FK 01",
        distance_m=8.0,
        confidence="high",
        state_name="EKITI",
        lga_name="ADO EKITI",
        locality_name="ADO EKITI",
        address="NTA ROAD",
    )
    found = Location(
        found=True, unit=unit, area=None, district=None, state=None, message=None, radius_m=25.0
    )
    assert capped(found, 2) == found
    held = capped(found, 1).unit
    assert held is not None
    assert (held.postcode, held.address, held.state_name) == ("EK-01-A03-FK-01", None, None)


def test_the_level_cap_withholds_a_field_the_unit_gains_later() -> None:
    class Tomorrow(NearestBuilding):
        occupant: str | None

    unit = Tomorrow(
        postcode="EK-01-A03-FK-01",
        display="EK 01 A03 FK 01",
        distance_m=8.0,
        confidence="high",
        state_name=None,
        lga_name=None,
        locality_name=None,
        address=None,
        occupant="A. Person",
    )
    found = Location(
        found=True, unit=unit, area=None, district=None, state=None, message=None, radius_m=25.0
    )
    held = capped(found, 1).unit
    assert isinstance(held, Tomorrow)
    assert (held.distance_m, held.occupant) == (8.0, None)


@pytest.mark.anyio
async def test_rejects_out_of_range_arguments() -> None:
    result = await call("find_postcode_at_location", {"latitude": 95, "longitude": 5.22})
    assert result.is_error


@pytest.mark.parametrize(
    ("model", "source"),
    [
        (PostcodeDetails, api.Lookup),
        (Address, api.AdministrativeAddress),
        (Completion, api.Suggestion),
        (NearestBuilding, api.NearestUnit),
        (Location, api.Reverse),
    ],
)
def test_output_models_only_use_fields_the_library_has(
    model: type[BaseModel], source: type
) -> None:
    assert set(model.model_fields) <= {field.name for field in dataclasses.fields(source)}


def test_transport_settings() -> None:
    served = settings_from_env({"NG_POSTCODE_TRANSPORT": "HTTP", "NG_POSTCODE_PORT": "9000"})
    assert isinstance(served, Settings)
    assert (served.transport, served.host, served.port) == ("http", "127.0.0.1", 9000)
    assert isinstance(settings_from_env({"NG_POSTCODE_TRANSPORT": "sse"}), str)


def test_a_server_key_is_not_shared_on_a_public_address_by_accident() -> None:
    public = {"NG_POSTCODE_TRANSPORT": "http", "NG_POSTCODE_HOST": "0.0.0.0"}
    keyed = public | {"NG_POSTCODE_API_KEY": "k"}
    refused = settings_from_env(keyed)
    assert isinstance(refused, str)
    assert "NG_POSTCODE_ALLOW_SHARED_KEY" in refused
    for allowed in (
        public,
        keyed | {"NG_POSTCODE_ALLOW_SHARED_KEY": "1"},
        keyed | {"NG_POSTCODE_HOST": "localhost"},
        keyed | {"NG_POSTCODE_TRANSPORT": "stdio"},
    ):
        assert isinstance(settings_from_env(allowed), Settings)
    assert isinstance(settings_from_env({"NG_POSTCODE_PORT": "0"}), str)


@pytest.mark.parametrize("key", ["SECRET\nPART2", "SECRET PART2", "SÉCRET", "k" * 257])
def test_an_unusable_server_key_is_refused_at_startup_without_being_echoed(key: str) -> None:
    refused = settings_from_env({"NG_POSTCODE_API_KEY": key})
    assert refused == "NG_POSTCODE_API_KEY does not hold a usable NIPOST API key"


def test_settings_from_env() -> None:
    assert settings_from_env({}) == Settings(api_key=None)
    assert settings_from_env({"NG_POSTCODE_API_KEY": " k ", "NG_POSTCODE_MAX_LEVEL": "3"}) == (
        Settings(api_key="k", max_level=3)
    )
    assert settings_from_env({"NG_POSTCODE_MAX_PAID_CALLS": "3"}) == Settings(
        api_key=None, max_paid_calls=3
    )
    assert isinstance(settings_from_env({"NG_POSTCODE_MAX_PAID_CALLS": "many"}), str)
    assert settings_from_env({"NG_POSTCODE_MAX_LEVEL": "9"}) == (
        "NG_POSTCODE_MAX_LEVEL must be 1 to 5, got '9'"
    )


@pytest.mark.anyio
async def test_a_blank_autocomplete_never_reaches_the_api() -> None:
    seen: list[httpx.Request] = []
    result = await call("autocomplete_postcode", {"partial": "  "}, seen=seen)
    assert result.is_error
    assert seen == []


def test_a_level_the_key_lacks_gets_a_specific_hint() -> None:
    error = ApiError(403, "level_not_granted", "this key is granted up to lookup level 1")
    with pytest.raises(ToolError, match="request more access"):
        unwrap(error)


def test_a_proxy_error_page_is_not_blamed_on_the_key() -> None:
    page = api.decode(api.autocomplete("E"), 403, "<html>403 Forbidden</html>")
    with pytest.raises(ToolError) as refused:
        unwrap(page)
    assert "malformed_response (403)" in str(refused.value)
    assert "key" not in str(refused.value)


@pytest.mark.anyio
@pytest.mark.parametrize("case", CALLS, ids=[case["name"] for case in CALLS])
async def test_answers_the_shared_offline_calls(case: dict[str, Any]) -> None:
    seen: list[httpx.Request] = []
    result = await call(case["tool"], case["arguments"], seen=seen)
    assert seen == []
    if "error" in case or case.get("refused"):
        assert result.is_error
        assert text(result).endswith(case.get("error", ""))
    else:
        assert result.structured_content == case["result"]


def test_building_the_server_keeps_request_urls_out_of_the_logs() -> None:
    logging.getLogger("httpx").setLevel(logging.INFO)
    create_server(Settings(api_key=None))
    assert logging.getLogger("httpx").level == logging.WARNING
