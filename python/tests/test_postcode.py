"""Python-specific behaviour. Shared parsing rules live in test_conformance.py."""

from __future__ import annotations

import dataclasses

import pytest

from ng_postcode import (
    Corrected,
    InvalidCharacter,
    InvalidSegment,
    Postcode,
    Segment,
    WrongLength,
    is_valid,
    parse,
    parse_lenient,
)


def ok(text: str) -> Postcode:
    code = parse(text)
    assert isinstance(code, Postcode), code
    return code


def test_errors_are_values_with_readable_messages() -> None:
    assert parse("EK-01") == WrongLength(found=4)
    assert str(WrongLength(found=5)) == "expected 11 letters and digits, found 5"
    assert str(InvalidCharacter(char="_", index=2)) == "invalid character '_' at index 2"
    assert str(InvalidSegment(Segment.LGA)) == "invalid lga segment"


def test_exposes_segments() -> None:
    code = ok("la11w06tc10")
    assert (code.state, code.lga, code.district, code.area, code.unit) == (
        "LA",
        "11",
        "W06",
        "TC",
        "10",
    )
    assert repr(code) == "Postcode('LA-11-W06-TC-10')"


def test_postcodes_are_immutable_hashable_and_ordered() -> None:
    code = ok("EK-01-A03-FK-01")
    assert code == ok("ek 01 a03 fk 01")
    assert len({code, ok("ek01a03fk01")}) == 1
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(code, "compact", "LA11W06TC10")  # noqa: B010
    codes = [ok("LA-11-W06-TC-10"), ok("EK-01-A03-FK-02"), code]
    assert [str(c) for c in sorted(codes)] == [
        "EK-01-A03-FK-01",
        "EK-01-A03-FK-02",
        "LA-11-W06-TC-10",
    ]


@pytest.mark.parametrize("text", ["ek01a03fk01", "EK-01-A03-FK-01", "EK00A03FK01", ""])
def test_direct_construction_demands_the_compact_form(text: str) -> None:
    with pytest.raises(ValueError, match="not a compact upper-case postcode"):
        Postcode(text)


def test_lenient_counts_corrections() -> None:
    assert parse_lenient("EK-O1-A03-FK-0I") == Corrected(ok("EK-01-A03-FK-01"), 2)


def test_is_valid_agrees_with_parse() -> None:
    assert is_valid("ek 01 a03 fk 01")
    assert not is_valid("EK-01-A03")
