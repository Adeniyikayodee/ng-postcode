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

import anthropic
from ng_postcode.api import Coordinate
from ng_postcode.client import AsyncClient

from .geocode import PUBLIC_NOMINATIM, Nominatim
from .models import Resolution
from .parse import MODEL, ClaudeParser
from .resolve import Resolver


def main(argv: list[str] | None = None) -> None:
    cli = argparse.ArgumentParser(prog="ng-address", description=__doc__)
    cli.add_argument("address", help="Free-text address, in quotes.")
    cli.add_argument("--lat", type=float, help="Latitude of a location pin.")
    cli.add_argument("--lng", type=float, help="Longitude of a location pin.")
    args = cli.parse_args(argv)
    if (args.lat is None) != (args.lng is None):
        cli.error("give both --lat and --lng, or neither")
    location = None if args.lat is None else Coordinate(lat=args.lat, lng=args.lng)
    problem = config_problem(os.environ)
    if problem:
        sys.exit(f"ng-address: {problem}")
    result = asyncio.run(run(args.address, location, os.environ))
    print(json.dumps(result.model_dump(), indent=2))


def config_problem(env: Mapping[str, str]) -> str | None:
    url = env.get("NG_GEOCODER_URL", "").rstrip("/")
    if url == PUBLIC_NOMINATIM and not env.get("NG_GEOCODER_CONTACT"):
        return "the public Nominatim requires NG_GEOCODER_CONTACT, a URL or email identifying you"
    return None


async def run(text: str, location: Coordinate | None, env: Mapping[str, str]) -> Resolution:
    key = env.get("NG_POSTCODE_API_KEY", "").strip()
    nipost = AsyncClient(key) if key else None
    geocoder = geocoder_from(env)
    claude = claude_from()
    parser = ClaudeParser(claude, env.get("NG_ADDRESS_MODEL") or MODEL) if claude else None
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
    url = env.get("NG_GEOCODER_URL", "").rstrip("/")
    if not url:
        return None
    contact = env.get("NG_GEOCODER_CONTACT", "unknown")
    if url == PUBLIC_NOMINATIM:
        print(
            "ng-address: using the public Nominatim, for light personal use only. "
            "Map data (c) OpenStreetMap contributors.",
            file=sys.stderr,
        )
    return Nominatim(url, f"ng-address-resolver/{version('ng-address-resolver')} ({contact})")


def claude_from() -> anthropic.AsyncAnthropic | None:
    try:
        return anthropic.AsyncAnthropic()
    except anthropic.AnthropicError:
        return None
