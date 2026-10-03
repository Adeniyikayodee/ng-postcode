"""Resolve free-text Nigerian addresses to NIPOST digital postcodes, only as
precisely as the evidence allows.

The core needs no model. `ng_address.parse.ClaudeParser` reads addresses with
Claude and needs the `claude` extra."""

from .geocode import GeocodeFailure, Nominatim
from .models import Geocoded, Landmark, ParsedAddress, ParseFailure, Resolution
from .resolve import Resolver

__all__ = [
    "GeocodeFailure",
    "Geocoded",
    "Landmark",
    "Nominatim",
    "ParseFailure",
    "ParsedAddress",
    "Resolution",
    "Resolver",
]
