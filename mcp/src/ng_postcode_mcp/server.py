"""MCP server for Nigeria's NIPOST digital postcode.

Validation runs offline. Lookup, autocomplete and reverse geocoding call the
postcode.gov.ng API with the key in NG_POSTCODE_API_KEY, which never appears in
tool arguments or results. Address resolution also searches the geocoder in
NG_GEOCODER_URL. Over stdio, stdout carries the protocol, so nothing else may
print to it. Over HTTP, a caller may send its own key in the X-NIPOST-API-Key
header; without one it uses the server's key, if the server has one.
"""

from __future__ import annotations

import inspect
import logging
import os
import sys
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from importlib.metadata import version
from typing import Annotated, Any, Literal, TypeVar

import httpx
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from ng_address import Landmark, Nominatim, ParsedAddress, Resolution, Resolver
from ng_address.geocode import PUBLIC_NOMINATIM
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
from ng_postcode.client import TIMEOUT, AsyncClient, TransportError
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])

KEY_URL = "https://dashboard.postcode.gov.ng"
KEY_HEADER = "x-nipost-api-key"
MAX_KEY_LENGTH = 256

INSTRUCTIONS = """\
Tools for Nigeria's 11-character building postcode, e.g. EK-01-A03-FK-01 \
(state, LGA, district, area, building unit).
- validate_postcode is offline and free: use it first on any code a user typed.
- lookup_postcode level 1 only confirms a code exists. Levels 2 and up add the \
address and building details, consume NIPOST credits, and are capped by the \
server's NG_POSTCODE_MAX_LEVEL.
- resolve_address turns a described address into a code. It answers only as \
precisely as its evidence allows: pass on its level and confidence, and ask the \
user its question instead of guessing. A location pin is the most reliable input.
- Never substitute a suggested correction without confirming it with the user.
- Addresses returned are personal data: use them only for the user's request."""

READ_ONLY_OFFLINE = ToolAnnotations(
    read_only_hint=True, idempotent_hint=True, open_world_hint=False
)
READ_ONLY_ONLINE = ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=True)

HINTS = {
    "auth_required": f"Supply a NIPOST API key from {KEY_URL}.",
    "invalid_api_key": f"The NIPOST API key is invalid or revoked; create a new key at {KEY_URL}.",
    "insufficient_credits": "The NIPOST account is out of credits; top up or use level 1.",
    "level_not_granted": "The key is not granted this lookup level; use a lower level or "
    f"request more access at {KEY_URL}.",
}
LEVEL_2_FIELDS = ("state_name", "lga_name", "locality_name", "address")
STATUS_HINTS = {
    403: "The key lacks the scope or access level for this request.",
    429: "NIPOST rate limit reached; wait before retrying.",
}


@dataclass(frozen=True, slots=True)
class Settings:
    api_key: str | None
    max_level: int = 1
    base_url: str = BASE_URL
    geocoder_url: str | None = None
    geocoder_contact: str | None = None
    transport: Literal["stdio", "http"] = "stdio"
    host: str = "127.0.0.1"
    port: int = 8000


def settings_from_env(env: Mapping[str, str]) -> Settings | str:
    """Read settings from the environment, or describe what is wrong with them."""
    raw_level = env.get("NG_POSTCODE_MAX_LEVEL", "1").strip()
    if raw_level not in {"1", "2", "3", "4", "5"}:
        return f"NG_POSTCODE_MAX_LEVEL must be 1 to 5, got {raw_level!r}"
    geocoder_url = env.get("NG_GEOCODER_URL", "").strip().rstrip("/") or None
    geocoder_contact = env.get("NG_GEOCODER_CONTACT", "").strip() or None
    if geocoder_url == PUBLIC_NOMINATIM and geocoder_contact is None:
        return "the public Nominatim requires NG_GEOCODER_CONTACT, a URL or email identifying you"
    transport = env.get("NG_POSTCODE_TRANSPORT", "stdio").strip().lower()
    if transport not in ("stdio", "http"):
        return f"NG_POSTCODE_TRANSPORT must be stdio or http, got {transport!r}"
    raw_port = env.get("NG_POSTCODE_PORT", "8000").strip()
    if not (raw_port.isdecimal() and 0 < int(raw_port) < 65536):
        return f"NG_POSTCODE_PORT must be 1 to 65535, got {raw_port!r}"
    return Settings(
        api_key=env.get("NG_POSTCODE_API_KEY", "").strip() or None,
        max_level=int(raw_level),
        base_url=env.get("NG_POSTCODE_BASE_URL", "").strip() or BASE_URL,
        geocoder_url=geocoder_url,
        geocoder_contact=geocoder_contact,
        transport="http" if transport == "http" else "stdio",
        host=env.get("NG_POSTCODE_HOST", "").strip() or "127.0.0.1",
        port=int(raw_port),
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
    status: str | None = Field(
        default=None, description="valid, not_found, or invalid for a malformed code."
    )
    verified: bool | None = None
    administrative_address: Address | None = Field(description="Level 2 and up.")
    recent_house_address: str | None = Field(description="Level 2 and up. Personal data.")
    building_use_status: str | None = Field(description="Level 3 and up, e.g. residential.")
    other_building_info: Any = Field(default=None, description="Level 4 and up, unstructured.")
    point_geometry: Any = Field(default=None, description="Level 5, unstructured.")


class Completion(FromLibrary):
    code: str = Field(description="The value of the next segment, e.g. A03, not a full prefix.")
    label: str | None = Field(
        default=None, description="A name for the code, when NIPOST sends one."
    )


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
    depth: str | None = Field(default=None, description="How deep the match goes, e.g. unit.")


@dataclass(frozen=True, slots=True)
class State:
    """What the tools share for the life of the server. `nipost` and `geocoder` may be
    unconfigured."""

    http: httpx.AsyncClient
    base_url: str
    nipost: AsyncClient | None
    geocoder: Nominatim | None


def create_server(
    settings: Settings,
    http: httpx.AsyncClient | None = None,
    geocoder_http: httpx.AsyncClient | None = None,
) -> MCPServer[State]:
    """Build the server. Pass `http` and `geocoder_http` to route calls through your own
    clients, as tests do."""

    @asynccontextmanager
    async def lifespan(_: MCPServer[State]) -> AsyncIterator[State]:
        shared = http if http is not None else httpx.AsyncClient(timeout=TIMEOUT)
        nipost = (
            AsyncClient(settings.api_key, base_url=settings.base_url, http=shared)
            if settings.api_key
            else None
        )
        geocoder = geocoder_for(settings, geocoder_http)
        try:
            yield State(shared, settings.base_url, nipost, geocoder)
        finally:
            if http is None:
                await shared.aclose()
            if geocoder:
                await geocoder.aclose()

    server: MCPServer[State] = MCPServer(
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
    @tidy
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
    @tidy
    async def lookup_postcode(
        postcode: Annotated[str, Field(description="Code in any style, e.g. EK-01-A03-FK-01.")],
        ctx: Context[State, Any],
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
    @tidy
    async def autocomplete_postcode(
        partial: Annotated[
            str, Field(min_length=1, description="The start of a code, e.g. 'EK 01 A'.")
        ],
        ctx: Context[State, Any],
    ) -> Completions:
        """Suggest completions for the next segment of a partly typed postcode."""
        if not partial.strip():
            raise ToolError("Give at least the first characters of a postcode.")
        result = await api(ctx).send(autocomplete(partial))
        return completions(unwrap(result))

    @server.tool(
        title="Find the postcode at a location",
        annotations=READ_ONLY_ONLINE,
        structured_output=True,
    )
    @tidy
    async def find_postcode_at_location(
        latitude: Annotated[
            float, Field(ge=-90, le=90, description="Latitude in decimal degrees, e.g. 7.6211.")
        ],
        longitude: Annotated[
            float, Field(ge=-180, le=180, description="Longitude in decimal degrees, e.g. 5.2214.")
        ],
        ctx: Context[State, Any],
        max_distance_m: Annotated[
            float | None,
            Field(ge=0, le=250, description="Search radius in metres. Defaults to 25."),
        ] = None,
    ) -> Location:
        """Return the postcode of the nearest building to a coordinate in Nigeria.

        Names and the house address are withheld unless NG_POSTCODE_MAX_LEVEL is 2 or more.
        """
        result = await api(ctx).send(
            reverse(Coordinate(lat=latitude, lng=longitude), max_distance_m)
        )
        return capped(Location.model_validate(unwrap(result)), settings.max_level)

    @server.tool(
        title="Resolve a Nigerian address to a postcode",
        annotations=READ_ONLY_ONLINE,
        structured_output=True,
    )
    @tidy
    async def resolve_address(
        address: Annotated[str, Field(description="The address exactly as the user gave it.")],
        ctx: Context[State, Any],
        landmarks: Annotated[
            list[Landmark] | None,
            Field(
                description="Landmarks named in the address, each with how the address relates "
                "to it. Use 'at' only when the address is the landmark itself."
            ),
        ] = None,
        geocode_queries: Annotated[
            list[str] | None,
            Field(
                max_length=3,
                description="Up to three map search strings you derive from the address: named "
                "places and streets with the town and state, most specific first, without "
                "directional words like 'back of'.",
            ),
        ] = None,
        latitude: Annotated[
            float | None,
            Field(ge=-90, le=90, description="Latitude of a location pin the user shared."),
        ] = None,
        longitude: Annotated[
            float | None,
            Field(ge=-180, le=180, description="Longitude of that pin. Give it with latitude."),
        ] = None,
    ) -> Resolution:
        """Turn a described Nigerian address into a postcode, only as precisely as the
        evidence allows.

        A full building code comes only from a postcode written in the address, a location
        pin, or a landmark that is the address itself. Otherwise the result is an area or
        district prefix with a `question` for the user. Read the address yourself and fill
        `landmarks` and `geocode_queries`; the address text is sent to the configured
        geocoder.
        """
        if (latitude is None) != (longitude is None):
            raise ToolError("Give both latitude and longitude, or neither.")
        location = (
            Coordinate(lat=latitude, lng=longitude)
            if latitude is not None and longitude is not None
            else None
        )
        geocoder = ctx.request_context.lifespan_context.geocoder
        resolver = Resolver(nipost=nipost_for(ctx), geocoder=geocoder)
        return await resolver.resolve(address, location, reading(landmarks, geocode_queries))

    return server


def tidy(tool: F) -> F:
    """Give the tool the same description on every Python: before 3.13 a docstring keeps
    its indentation."""
    tool.__doc__ = inspect.cleandoc(tool.__doc__ or "")
    return tool


def reading(landmarks: list[Landmark] | None, queries: list[str] | None) -> ParsedAddress | None:
    """The host model's reading of the address, in the resolver's terms."""
    if not landmarks and not queries:
        return None
    return ParsedAddress(
        house_number=None,
        street=None,
        landmarks=landmarks or [],
        locality=None,
        lga=None,
        state=None,
        geocode_queries=queries or [],
        question=None,
    )


def geocoder_for(settings: Settings, http: httpx.AsyncClient | None) -> Nominatim | None:
    if settings.geocoder_url is None:
        return None
    contact = settings.geocoder_contact or "unknown"
    return Nominatim(
        settings.geocoder_url,
        f"ng-postcode-mcp/{version('ng-postcode-mcp')} ({contact})",
        http=http,
    )


def capped(location: Location, max_level: int) -> Location:
    """The location without the fields a level 2 key adds, unless the cap allows them."""
    if max_level >= 2 or location.unit is None:
        return location
    unit = location.unit.model_copy(update=dict.fromkeys(LEVEL_2_FIELDS))
    return location.model_copy(update={"unit": unit})


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


def nipost_for(ctx: Context[State, Any]) -> AsyncClient | None:
    """The caller's own client when an HTTP request carries a key, else the server's."""
    state = ctx.request_context.lifespan_context
    sent = (v for k, v in (ctx.headers or {}).items() if k.lower() == KEY_HEADER)
    key = next(sent, "").strip()
    if not key:
        return state.nipost
    if not (key.isascii() and key.isprintable() and " " not in key and len(key) <= MAX_KEY_LENGTH):
        raise ToolError("The X-NIPOST-API-Key header does not hold a usable NIPOST API key.")
    return AsyncClient(key, base_url=state.base_url, http=state.http)


def api(ctx: Context[State, Any]) -> AsyncClient:
    client = nipost_for(ctx)
    if client is None:
        raise ToolError(
            "This tool needs a NIPOST API key: set NG_POSTCODE_API_KEY on the server, or over "
            f"HTTP send your own in the X-NIPOST-API-Key header. Get one at {KEY_URL}."
        )
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
    server = create_server(settings)
    if settings.transport == "http":
        server.run("streamable-http", host=settings.host, port=settings.port)
    else:
        server.run()
