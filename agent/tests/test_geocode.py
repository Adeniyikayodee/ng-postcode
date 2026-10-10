from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

import httpx
import pytest

from ng_address.geocode import GeocodeFailure, Nominatim, first_place

# Shape of a real answer for "NTA Road, Ado Ekiti" on 3 October 2026, trimmed.
NTA_ROAD = [
    {
        "lat": "7.6272088",
        "lon": "5.1933175",
        "category": "highway",
        "type": "tertiary",
        "place_rank": 26,
        "display_name": "NTA - Ilawe Byepass Road, Adó-Èkìtì, Ekiti, Nigeria",
    }
]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def nominatim(
    handler: Callable[[httpx.Request], httpx.Response], interval: float = 0.0
) -> Nominatim:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return Nominatim(
        "https://geo.example", "test-agent (ops@example.com)", http=http, min_interval_s=interval
    )


def test_first_place_reads_real_responses_and_rejects_junk() -> None:
    place = first_place("NTA Road, Ado Ekiti", NTA_ROAD)
    assert place is not None
    assert (place.lat, place.lng, place.precision) == (7.6272088, 5.1933175, "street")
    junk: list[object] = [[], {}, None, [{"lat": "x", "lon": "1"}], [{"lon": "1"}]]
    for data in junk:
        assert first_place("q", data) is None


@pytest.mark.anyio
async def test_identifies_itself_limits_to_nigeria_and_caches() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=NTA_ROAD)

    geocoder = nominatim(handle)
    first = await geocoder("NTA Road, Ado Ekiti")
    again = await geocoder("  nta road,   ado ekiti ")
    assert first == again
    assert len(seen) == 1
    assert seen[0].headers["User-Agent"] == "test-agent (ops@example.com)"
    assert seen[0].url.path == "/search"
    assert seen[0].url.params["countrycodes"] == "ng"


@pytest.mark.anyio
async def test_the_cache_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ng_address.geocode.CACHE_SIZE", 1)
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=NTA_ROAD)

    geocoder = nominatim(handle)
    for query in ("a", "b", "b", "a"):
        await geocoder(query)
    assert [r.url.params["q"] for r in seen] == ["a", "b", "a"]


@pytest.mark.anyio
async def test_spaces_requests_apart() -> None:
    geocoder = nominatim(lambda request: httpx.Response(200, json=[]), interval=0.2)
    start = time.monotonic()
    for query in ("a", "b", "c"):
        assert await geocoder(query) is None
    assert time.monotonic() - start >= 0.4


@pytest.mark.anyio
async def test_a_slow_answer_does_not_hold_up_other_searches() -> None:
    async def handle(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.3 if request.url.params["q"] == "slow" else 0)
        return httpx.Response(200, json=[])

    http = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    geocoder = Nominatim("https://geo.example", "test-agent", http=http, min_interval_s=0.0)
    slow = asyncio.create_task(geocoder("slow"))
    await asyncio.sleep(0)
    start = time.monotonic()
    assert await geocoder("fast") is None
    assert time.monotonic() - start < 0.2
    assert await slow is None


@pytest.mark.anyio
async def test_a_burst_is_refused_instead_of_booking_the_queue_ahead() -> None:
    sent: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(request.url.params["q"])
        return httpx.Response(200, json=[])

    http = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    geocoder = Nominatim(
        "https://geo.example", "test", http=http, min_interval_s=0.01, max_wait_s=0.05
    )
    burst = await asyncio.gather(*(geocoder(f"place {n}") for n in range(50)))
    refused = [answer for answer in burst if isinstance(answer, GeocodeFailure)]
    assert 40 <= len(refused) < 50
    assert len(sent) == 50 - len(refused)

    assert await geocoder("after the burst") is None
    assert sent[-1] == "after the burst"


@pytest.mark.anyio
async def test_a_cancelled_search_gives_up_its_place_in_the_queue() -> None:
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=[])))
    geocoder = Nominatim(
        "https://geo.example", "test", http=http, min_interval_s=0.05, max_wait_s=0.1
    )
    waiting = [asyncio.create_task(geocoder(f"place {n}")) for n in range(3)]
    await asyncio.sleep(0)
    for task in waiting[1:]:
        task.cancel()
    await asyncio.gather(*waiting, return_exceptions=True)
    start = time.monotonic()
    assert await geocoder("after") is None
    assert time.monotonic() - start < 0.1


@pytest.mark.anyio
async def test_failures_are_values() -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    assert await nominatim(lambda r: httpx.Response(503))("q") == GeocodeFailure(
        "geocoder answered HTTP 503"
    )
    failure = await nominatim(down)("q")
    assert isinstance(failure, GeocodeFailure)
    assert "refused" in failure.reason


def test_first_place_rejects_coordinates_that_are_not_numbers() -> None:
    assert first_place("q", [{"lat": "nan", "lon": "5.2", "place_rank": 30}]) is None
    assert first_place("q", [{"lat": "7.6", "lon": "inf", "place_rank": 30}]) is None
    assert first_place("q", [{"lat": "95.0", "lon": "5.2", "place_rank": 30}]) is None
    assert first_place("q", [{"lat": "7.6", "lon": "-181", "place_rank": 30}]) is None
    assert first_place("q", [{"lat": 10**400, "lon": "5.2", "place_rank": 30}]) is None
    assert first_place("q", [{"lat": "7.6", "lon": "5.2", "place_rank": float("inf")}]) is None


@pytest.mark.anyio
async def test_a_body_nested_too_deep_to_read_is_a_failure() -> None:
    deep = httpx.Response(200, content="[" * 200_000)
    assert await nominatim(lambda r: deep)("q") == GeocodeFailure(
        "geocoder answered with something other than JSON"
    )
