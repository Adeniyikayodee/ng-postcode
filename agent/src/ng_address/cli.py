"""`ng-address "back of Fabian Hotel, NTA Road, Ado Ekiti"`: prints the Resolution as JSON.

Configuration comes from the environment. Anthropic credentials are read by
the SDK as usual; NG_POSTCODE_API_KEY, NG_GEOCODER_URL, NG_GEOCODER_CONTACT
and NG_ADDRESS_MODEL are read here.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Mapping
from importlib.metadata import version
from typing import TYPE_CHECKING

from ng_postcode.api import Coordinate
from ng_postcode.client import AsyncClient

from .geocode import Nominatim, is_http, is_public
from .models import Resolution
from .resolve import Parser, Resolver

if TYPE_CHECKING:
    import anthropic


def main(argv: list[str] | None = None) -> None:
    cli = argparse.ArgumentParser(prog="ng-address", description=__doc__)
    cli.add_argument("address", help="Free-text address, in quotes.")
    cli.add_argument("--lat", type=float, help="Latitude of a location pin.")
    cli.add_argument("--lng", type=float, help="Longitude of a location pin.")
    args = cli.parse_args(argv)
    if (args.lat is None) != (args.lng is None):
        cli.error("give both --lat and --lng, or neither")
    if args.lat is not None and not (abs(args.lat) <= 90 and abs(args.lng) <= 180):
        cli.error("--lat must be within -90 to 90 and --lng within -180 to 180")
    location = None if args.lat is None else Coordinate(lat=args.lat, lng=args.lng)
    problem = config_problem(os.environ)
    if problem:
        sys.exit(f"ng-address: {problem}")
    result = asyncio.run(run(args.address, location, os.environ))
    print(json.dumps(result.model_dump(), indent=2))


def config_problem(env: Mapping[str, str]) -> str | None:
    url = env.get("NG_GEOCODER_URL", "").strip().rstrip("/")
    if url and not is_http(url):
        return "NG_GEOCODER_URL must be an http or https URL"
    if is_public(url) and not env.get("NG_GEOCODER_CONTACT", "").strip():
        return "the public Nominatim requires NG_GEOCODER_CONTACT, a URL or email identifying you"
    return None


async def run(text: str, location: Coordinate | None, env: Mapping[str, str]) -> Resolution:
    key = env.get("NG_POSTCODE_API_KEY", "").strip()
    nipost = AsyncClient(key) if key else None
    geocoder = geocoder_from(env)
    claude = claude_from()
    parser = parser_from(claude, env.get("NG_ADDRESS_MODEL"))
    try:
        return await Resolver(nipost=nipost, parser=parser, geocoder=geocoder).resolve(
            text, location
        )
    finally:
        if nipost:
            await nipost.aclose()
        if geocoder:
            await geocoder.aclose()
        if claude:
            await claude.close()


def geocoder_from(env: Mapping[str, str]) -> Nominatim | None:
    url = env.get("NG_GEOCODER_URL", "").strip().rstrip("/")
    if not url:
        return None
    contact = env.get("NG_GEOCODER_CONTACT", "").strip() or "unknown"
    if is_public(url):
        print(
            "ng-address: using the public Nominatim, for light personal use only. "
            "Map data (c) OpenStreetMap contributors.",
            file=sys.stderr,
        )
    return Nominatim(url, f"ng-address-resolver/{version('ng-address-resolver')} ({contact})")


def claude_from() -> anthropic.AsyncAnthropic | None:
    """A Claude client, or None without the `claude` extra or usable credentials."""
    try:
        import anthropic
    except ImportError:
        return None
    try:
        return anthropic.AsyncAnthropic()
    except anthropic.AnthropicError:
        return None


def parser_from(claude: anthropic.AsyncAnthropic | None, model: str | None) -> Parser | None:
    if claude is None:
        return None
    from .parse import MODEL, ClaudeParser

    return ClaudeParser(claude, model or MODEL)
