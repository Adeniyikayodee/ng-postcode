"""Runs the shared cases in `spec/vectors.json` through the Polars expressions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from ng_postcode_polars import Postcodes

VECTORS = Path(__file__).resolve().parents[3] / "spec" / "vectors.json"
CASES: dict[str, Any] = json.loads(VECTORS.read_text(encoding="utf-8")) if VECTORS.exists() else {}

pytestmark = pytest.mark.skipif(
    not CASES, reason="spec/vectors.json lives in the repository, not the sdist"
)


def column(values: list[str | None], expr: pl.Expr) -> list[Any]:
    return pl.DataFrame({"v": values}, schema={"v": pl.String}).select(expr).to_series().to_list()


V = pl.col("v")
# `pl.col("v").ng` is the same object; type checkers cannot see a registered namespace.
NG = Postcodes(V)


def test_parse_and_format_follow_the_spec() -> None:
    valid = CASES["parse"]["valid"]
    inputs = [case["input"] for case in valid]
    assert column(inputs, NG.parse()) == [case["compact"] for case in valid]
    assert column(inputs, NG.format()) == [case["canonical"] for case in valid]
    assert column(inputs, NG.is_valid()) == [True] * len(valid)

    invalid = [case["input"] for case in CASES["parse"]["invalid"]]
    assert column(invalid, NG.parse()) == [None] * len(invalid)
    assert column(invalid, NG.is_valid()) == [False] * len(invalid)


def test_prefixes_follow_the_spec() -> None:
    valid = CASES["parse_prefix"]["valid"]
    inputs = [case["input"] for case in valid]
    assert column(inputs, NG.parse_prefix()) == [case["compact"] for case in valid]
    assert column(inputs, NG.format()) == [case["canonical"] for case in valid]

    invalid = [case["input"] for case in CASES["parse_prefix"]["invalid"]]
    assert column(invalid, NG.parse_prefix()) == [None] * len(invalid)


@pytest.mark.parametrize("case", CASES.get("prefix", []))
def test_truncate_follows_the_spec(case: dict[str, str]) -> None:
    cut = Postcodes(NG.truncate(case["through"])).format()  # type: ignore[arg-type]
    assert column([case["input"]], cut) == [case["prefix"]]


def test_null_stays_null_and_an_unknown_segment_is_an_error() -> None:
    for expr in (NG.parse(), NG.format(), NG.is_valid(), NG.truncate("state")):
        assert column([None], expr) == [None]
    with pytest.raises(pl.exceptions.ComputeError, match="unknown segment: zone"):
        column(["EK01A03FK01"], NG.truncate("zone"))  # type: ignore[arg-type]


def test_grouping_counts_records_by_district() -> None:
    frame = pl.DataFrame({"v": ["ek 01 a03 fk 01", "EK-01-A03-ZZ-14", "la11w06tc10", "100001"]})
    counted = frame.group_by(Postcodes(NG.truncate("district")).format().alias("district")).len()
    assert dict(counted.iter_rows()) == {"EK-01-A03": 2, "LA-11-W06": 1, None: 1}


def test_importing_the_package_registers_the_namespace() -> None:
    assert column(["ek 01 a03 fk 01"], V.ng.parse()) == ["EK01A03FK01"]  # type: ignore[attr-defined]
