"""MCP server for Nigeria's NIPOST digital postcode.

Validation runs offline. Lookup, autocomplete and reverse geocoding call the
postcode.gov.ng API with the key in NG_POSTCODE_API_KEY, which never appears in
tool arguments or results. stdout carries the protocol, so nothing else may
print to it.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from importlib.metadata import version
from typing import Annotated, Any, Literal, TypeVar

import httpx
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from ng_postcode import Corrected, Postcode, parse, parse_lenient
from ng_postcode.api import (
    BASE_URL,
    ApiError,
    Autocomplete,
    Coordinate,
    autocomplete,
    lookup,
    reverse,
)
from ng_postcode.client import AsyncClient, TransportError
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

KEY_URL = "https://dashboard.postcode.gov.ng"

INSTRUCTIONS = """\
Tools for Nigeria's 11-character building postcode, e.g. EK-01-A03-FK-01 \
(state, LGA, district, area, building unit).
- validate_postcode is offline and free: use it first on any code a user typed.
- lookup_postcode level 1 only confirms a code exists. Levels 2 and up add the \
address and building details, consume NIPOST credits, and are capped by the \
server's NG_POSTCODE_MAX_LEVEL.
- Never substitute a suggested correction without confirming it with the user.
- Addresses returned are personal data: use them only for the user's request."""

READ_ONLY_OFFLINE = ToolAnnotations(
    read_only_hint=True, idempotent_hint=True, open_world_hint=False
)
READ_ONLY_ONLINE = ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=True)

HINTS = {
    "auth_required": f"Set NG_POSTCODE_API_KEY to a key from {KEY_URL}.",
    "invalid_api_key": f"NG_POSTCODE_API_KEY is invalid or revoked; create a new key at {KEY_URL}.",
    "insufficient_credits": "The NIPOST account is out of credits; top up or use level 1.",
}
STATUS_HINTS = {
    403: "The key lacks the scope or access level for this request.",
    429: "NIPOST rate limit reached; wait before retrying.",
}


@dataclass(frozen=True, slots=True)
class Settings:
    api_key: str | None
    max_level: int = 1
    base_url: str = BASE_URL


def settings_from_env(env: Mapping[str, str]) -> Settings | str:
    """Read settings from the environment, or describe what is wrong with them."""
    raw_level = env.get("NG_POSTCODE_MAX_LEVEL", "1").strip()
    if raw_level not in {"1", "2", "3", "4", "5"}:
        return f"NG_POSTCODE_MAX_LEVEL must be 1 to 5, got {raw_level!r}"
    return Settings(
        api_key=env.get("NG_POSTCODE_API_KEY", "").strip() or None,
        max_level=int(raw_level),
        base_url=env.get("NG_POSTCODE_BASE_URL", "").strip() or BASE_URL,
    )


class Segments(BaseModel):
    state: str
    lga: str
    district: str
    area: str
    unit: str


class Validation(BaseModel):
    valid: bool = Field(description="Whether the code is well formed. It may still be unassigned.")
    postcode: str | None = Field(description="Canonical form, e.g. EK-01-A03-FK-01.")
    compact: str | None = Field(description="Compact form for storage, e.g. EK01A03FK01.")
    spaced: str | None = Field(description="Form shown to people, e.g. EK 01 A03 FK 01.")
    segments: Segments | None
    error: str | None = Field(description="Why the code is malformed.")
    suggestion: str | None = Field(
        description="A well-formed code if look-alike characters (O/0, I/1, S/5, B/8) were the "
        "only problem. Confirm it with the user before using it."
    )


# Explicit output contracts. The SDK cannot derive schemas from the library's slotted
# dataclasses, and named fields with descriptions serve agents better anyway.
# tests/test_tools.py checks every field still exists in ng_postcode.api.


class FromLibrary(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Address(FromLibrary):
    state_name: str | None
    lga_name: str | None
    locality_name: str | None
    zone: str | None = Field(description="Geopolitical zone, e.g. SOUTH WEST.")


class PostcodeDetails(FromLibrary):
    postcode: str
    valid: bool = Field(description="Whether the code is assigned to a building.")
    administrative_address: Address | None = Field(description="Level 2 and up.")
    recent_house_address: str | None = Field(description="Level 2 and up. Personal data.")
    building_use_status: str | None = Field(description="Level 3 and up, e.g. residential.")
    other_building_info: Any = Field(default=None, description="Level 4 and up, unstructured.")
    point_geometry: Any = Field(default=None, description="Level 5, unstructured.")


class Completion(FromLibrary):
    code: str
    label: str


class Completions(BaseModel):
    segment: Literal["state", "lga", "district", "area", "unit"] | None = Field(
        description="The segment being completed."
    )
    suggestions: list[Completion]


class NearestBuilding(FromLibrary):
    postcode: str
    display: str
    distance_m: float | None
    confidence: str | None = Field(description="high, medium or low, graded by distance.")
    state_name: str | None = Field(description="Level 2 and up.")
    lga_name: str | None = Field(description="Level 2 and up.")
    locality_name: str | None = Field(description="Level 2 and up.")
    address: str | None = Field(description="Recent house address. Level 2 and up.")


class Location(FromLibrary):
    found: bool = Field(description="False when no building is within the radius.")
    unit: NearestBuilding | None
    area: str | None = Field(description="Enclosing area code, e.g. EK-01-A03-FK.")
    district: str | None
    state: str | None
    message: str | None
    radius_m: float | None = Field(description="The radius the API actually applied.")


Api = AsyncClient | None


def create_server(settings: Settings, http: httpx.AsyncClient | None = None) -> MCPServer[Api]:
    """Build the server. Pass `http` to route API calls through your own client, as tests do."""

    @asynccontextmanager
    async def lifespan(_: MCPServer[Api]) -> AsyncIterator[Api]:
        if settings.api_key is None:
            yield None
            return
        client = AsyncClient(settings.api_key, base_url=settings.base_url, http=http)
        try:
            yield client
        finally:
            await client.aclose()

    server: MCPServer[Api] = MCPServer(
        name="ng-postcode",
        title="Nigeria Postcode",
        instructions=INSTRUCTIONS,
        version=version("ng-postcode-mcp"),
        lifespan=lifespan,
    )

    @server.tool(
        title="Validate a Nigerian postcode",
        annotations=READ_ONLY_OFFLINE,
        structured_output=True,
    )
    def validate_postcode(
        postcode: Annotated[str, Field(description="Code in any style, e.g. 'ek 01 a03 fk 01'.")],
    ) -> Validation:
        """Check a postcode's structure offline and return its canonical forms and segments.

        Free and instant. Does not confirm the code is assigned to a building; use
        lookup_postcode for that.
        """
        return validation(postcode)

    @server.tool(
        title="Look up a Nigerian postcode",
        annotations=READ_ONLY_ONLINE,
        structured_output=True,
    )
    async def lookup_postcode(
        postcode: Annotated[str, Field(description="Code in any style, e.g. EK-01-A03-FK-01.")],
        ctx: Context[Api, Any],
        level: Annotated[
            int,
            Field(
                ge=1,
                le=5,
                description="1: validity only (free). 2: adds the administrative and recent "
                "house address. 3: adds building use. Levels 2+ consume NIPOST credits.",
            ),
        ] = 1,
    ) -> PostcodeDetails:
        """Confirm a postcode is assigned and, at higher levels, return its address details."""
        if level > settings.max_level:
            raise ToolError(
                f"Level {level} is above this server's cap of {settings.max_level}. Levels 2+ "
                "consume NIPOST credits; the user can raise NG_POSTCODE_MAX_LEVEL to allow it."
            )
        result = await api(ctx).send(lookup(checked(postcode), level))
        return PostcodeDetails.model_validate(unwrap(result))

    @server.tool(
        title="Autocomplete a Nigerian postcode",
        annotations=READ_ONLY_ONLINE,
        structured_output=True,
    )
    async def autocomplete_postcode(
        partial: Annotated[str, Field(description="The start of a code, e.g. 'EK 01 A'.")],
        ctx: Context[Api, Any],
    ) -> Completions:
        """Suggest completions for the next segment of a partly typed postcode."""
        result = await api(ctx).send(autocomplete(partial))
        return completions(unwrap(result))

    @server.tool(
        title="Find the postcode at a location",
        annotations=READ_ONLY_ONLINE,
        structured_output=True,
    )
    async def find_postcode_at_location(
        latitude: Annotated[float, Field(ge=-90, le=90)],
        longitude: Annotated[float, Field(ge=-180, le=180)],
        ctx: Context[Api, Any],
        max_distance_m: Annotated[
            float | None,
            Field(ge=0, le=250, description="Search radius in metres. Defaults to 25."),
        ] = None,
    ) -> Location:
        """Return the postcode of the nearest building to a coordinate in Nigeria."""
        result = await api(ctx).send(
            reverse(Coordinate(lat=latitude, lng=longitude), max_distance_m)
        )
        return Location.model_validate(unwrap(result))

    return server


def completions(found: Autocomplete) -> Completions:
    return Completions(
        segment=None if found.segment is None else found.segment.value,
        suggestions=[Completion.model_validate(s) for s in found.suggestions],
    )


def validation(text: str) -> Validation:
    match parse(text):
        case Postcode() as code:
            return Validation(
                valid=True,
                postcode=str(code),
                compact=code.compact,
                spaced=code.spaced,
                segments=Segments(
                    state=code.state,
                    lga=code.lga,
                    district=code.district,
                    area=code.area,
                    unit=code.unit,
                ),
                error=None,
                suggestion=None,
            )
        case error:
            return Validation(
                valid=False,
                postcode=None,
                compact=None,
                spaced=None,
                segments=None,
                error=str(error),
                suggestion=suggestion(text),
            )


def suggestion(text: str) -> str | None:
    fixed = parse_lenient(text)
    return str(fixed.postcode) if isinstance(fixed, Corrected) else None


def checked(text: str) -> Postcode:
    """The parsed code, or a ToolError the model can act on. Never auto-corrects a paid call."""
    match parse(text):
        case Postcode() as code:
            return code
        case error:
            hint = suggestion(text)
            maybe = f" Did you mean {hint}? Confirm with the user first." if hint else ""
            raise ToolError(f"{text!r} is not a valid postcode: {error}.{maybe}")


def api(ctx: Context[Api, Any]) -> AsyncClient:
    client = ctx.request_context.lifespan_context
    if client is None:
        raise ToolError(f"This tool needs NG_POSTCODE_API_KEY. {HINTS['auth_required']}")
    return client


def unwrap(result: T | ApiError | TransportError) -> T:
    if isinstance(result, TransportError):
        raise ToolError(f"Could not reach the NIPOST API: {result}")
    if isinstance(result, ApiError):
        hint = HINTS.get(result.code) or STATUS_HINTS.get(result.status, "")
        raise ToolError(f"NIPOST API error {result}. {hint}".strip())
    return result


def main() -> None:
    settings = settings_from_env(os.environ)
    if isinstance(settings, str):
        sys.exit(f"ng-postcode-mcp: {settings}")
    # httpx logs every request URL at INFO, which would copy postcodes into client logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    create_server(settings).run()
