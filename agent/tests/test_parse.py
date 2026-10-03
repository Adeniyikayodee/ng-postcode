"""The Claude call, against a mocked Messages API: checks the exact request we send."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import anthropic
import httpx2
import pytest

from ng_address.cli import claude_from
from ng_address.models import ParsedAddress
from ng_address.parse import FALLBACK_BETA, MODEL, ClaudeParser, ParseFailure

PARSED = {
    "house_number": None,
    "street": "NTA Road",
    "landmarks": [{"name": "Fabian Hotel", "relation": "behind"}],
    "locality": None,
    "lga": "Ado Ekiti",
    "state": "Ekiti",
    "geocode_queries": ["Fabian Hotel, Ado Ekiti, Ekiti", "NTA Road, Ado Ekiti, Ekiti"],
    "question": None,
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def message(text: str | None, stop_reason: str = "end_turn") -> dict[str, Any]:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": MODEL,
        "content": [] if text is None else [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 10},
    }


def parser(handler: Callable[[httpx2.Request], httpx2.Response]) -> ClaudeParser:
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    return ClaudeParser(anthropic.AsyncAnthropic(api_key="test", http_client=http, max_retries=0))


@pytest.mark.anyio
async def test_sends_the_documented_request_and_returns_the_parsed_address() -> None:
    seen: list[httpx2.Request] = []

    def handle(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json=message(json.dumps(PARSED)))

    result = await parser(handle)("back of Fabian Hotel, off NTA Road, Ado Ekiti")

    assert result == ParsedAddress.model_validate(PARSED)
    body = json.loads(seen[0].content)
    assert body["model"] == "claude-opus-5-5"
    assert body["fallbacks"] == "default"
    assert body["output_config"]["effort"] == "low"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["messages"] == [
        {
            "role": "user",
            "content": "<address>back of Fabian Hotel, off NTA Road, Ado Ekiti</address>",
        }
    ]
    assert "thinking" not in body
    assert FALLBACK_BETA in seen[0].headers["anthropic-beta"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "payload", "expected"),
    [
        (200, message(None, "refusal"), "Claude declined to read this address"),
        (200, message("", "refusal"), "Claude's answer did not match the address schema"),
        (
            200,
            message('{"street": "cut off', "max_tokens"),
            "Claude's answer did not match the address schema",
        ),
        (
            401,
            {
                "type": "error",
                "error": {"type": "authentication_error", "message": "invalid x-api-key"},
            },
            "Claude credentials are missing or invalid",
        ),
        (
            529,
            {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}},
            "Claude API error 529",
        ),
    ],
)
async def test_refusals_bad_output_and_api_errors_become_values(
    status: int, payload: dict[str, Any], expected: str
) -> None:
    result = await parser(lambda request: httpx2.Response(status, json=payload))("x")
    assert result == ParseFailure(expected)


CREDENTIAL_VARS = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_PROFILE",
    "ANTHROPIC_CONFIG_DIR",
)


@pytest.mark.anyio
async def test_no_credentials_is_a_value_not_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in CREDENTIAL_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))  # no saved profile either
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(lambda r: httpx2.Response(500)))
    result = await ClaudeParser(anthropic.AsyncAnthropic(http_client=http, max_retries=0))("x")
    assert result == ParseFailure("Claude credentials are missing or invalid")


def test_a_broken_profile_disables_claude_instead_of_crashing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in CREDENTIAL_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ANTHROPIC_CONFIG_DIR", str(tmp_path / "missing"))
    assert claude_from() is None
