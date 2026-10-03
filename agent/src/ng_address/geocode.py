"""Nominatim (OpenStreetMap) search, limited to Nigeria.

The public instance at nominatim.openstreetmap.org allows light use only and
requires an identifying User-Agent, at most one request per second and cached
results. A service whose main job is geocoding must run its own instance.
"""

from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass
from typing import Any

import httpx

from .core import precision_of
from .models import Geocoded

PUBLIC_NOMINATIM = "https://nominatim.openstreetmap.org"
CACHE_SIZE = 1024


@dataclass(frozen=True, slots=True)
class GeocodeFailure:
    reason: str


class Nominatim:
    """Caches the last `CACHE_SIZE` answers and spaces requests at least `min_interval_s` apart."""

    def __init__(
        self,
        base_url: str,
        user_agent: str,
        *,
        http: httpx.AsyncClient | None = None,
        min_interval_s: float = 1.0,
    ) -> None:
        self._http = http if http is not None else httpx.AsyncClient(timeout=10.0)
        self._owns_http = http is None
        self._url = base_url.rstrip("/") + "/search"
        self._headers = {"User-Agent": user_agent}
        self._interval = min_interval_s
        self._lock = asyncio.Lock()
        self._last = float("-inf")
        self._cache: dict[str, Geocoded | None] = {}

    async def __call__(self, query: str) -> Geocoded | GeocodeFailure | None:
        key = " ".join(query.casefold().split())
        async with self._lock:
            if key in self._cache:
                return self._cache[key]
            await asyncio.sleep(max(0.0, self._last + self._interval - time.monotonic()))
            try:
                response = await self._http.get(
                    self._url, params=_params(query), headers=self._headers
                )
            except httpx.HTTPError as error:
                return GeocodeFailure(f"geocoder unreachable: {str(error) or type(error).__name__}")
            finally:
                self._last = time.monotonic()
        if response.status_code != 200:
            return GeocodeFailure(f"geocoder answered HTTP {response.status_code}")
        try:
            place = first_place(query, response.json())
        except ValueError:
            return GeocodeFailure("geocoder answered with something other than JSON")
        if len(self._cache) >= CACHE_SIZE:
            del self._cache[next(iter(self._cache))]
        self._cache[key] = place
        return place

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()


def _params(query: str) -> dict[str, str]:
    return {"q": query, "format": "jsonv2", "countrycodes": "ng", "limit": "1"}


def first_place(query: str, data: Any) -> Geocoded | None:
    """The best match from a Nominatim jsonv2 search response, if it is usable."""
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        return None
    hit = data[0]
    try:
        lat, lng, rank = float(hit["lat"]), float(hit["lon"]), int(hit.get("place_rank", 0))
    except (KeyError, TypeError, ValueError):
        return None
    if not (math.isfinite(lat) and math.isfinite(lng)):
        return None
    label = str(hit.get("display_name") or query)
    return Geocoded(query=query, lat=lat, lng=lng, precision=precision_of(rank), label=label)
