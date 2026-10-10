"""The README's examples run as written, with the network stubbed."""

from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest

README = Path(__file__).resolve().parents[1] / "README.md"
EXAMPLES = re.findall(r"```python\n(.*?)```", README.read_text(encoding="utf-8"), re.DOTALL)


def nipost(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200, json={"data": {"postcode": "FC-03-B06-AG-12", "valid": True, "status": "valid"}}
    )


def test_the_readme_has_examples() -> None:
    assert len(EXAMPLES) >= 2


@pytest.mark.parametrize("example", EXAMPLES)
def test_an_example_runs(example: str, monkeypatch: pytest.MonkeyPatch) -> None:
    real = httpx.Client
    stub = httpx.MockTransport(nipost)
    monkeypatch.setattr(httpx, "Client", lambda **options: real(transport=stub, **options))
    exec(compile(example, str(README), "exec"), {})


GROUPING = Path(__file__).resolve().parents[2] / "docs" / "group-by-place.md"


@pytest.mark.skipif(not GROUPING.exists(), reason="the page lives in the repository, not the sdist")
def test_the_grouping_page_example_runs(capsys: pytest.CaptureFixture[str]) -> None:
    page = GROUPING.read_text(encoding="utf-8")
    exec(compile(re.findall(r"```python\n(.*?)```", page, re.DOTALL)[0], str(GROUPING), "exec"), {})
    assert "'EK-01-A03': 2" in capsys.readouterr().out
