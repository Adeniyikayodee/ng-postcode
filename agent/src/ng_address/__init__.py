"""Resolve free-text Nigerian addresses to NIPOST digital postcodes, only as
precisely as the evidence allows."""

from .geocode import GeocodeFailure, Nominatim
from .models import Geocoded, Landmark, ParsedAddress, Resolution
from .parse import ClaudeParser, ParseFailure
from .resolve import Resolver

__all__ = [
    "ClaudeParser",
    "GeocodeFailure",
    "Geocoded",
    "Landmark",
    "Nominatim",
    "ParseFailure",
    "ParsedAddress",
    "Resolution",
    "Resolver",
]
