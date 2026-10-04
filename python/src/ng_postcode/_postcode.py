"""Offline parsing, validation and formatting. Pure: no I/O, no mutation."""

from __future__ import annotations

import string
from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias

LENGTH = 11

_LETTERS = frozenset(string.ascii_uppercase)
_DIGITS = frozenset(string.digits)
_SEPARATORS = frozenset(" -")
_TO_LETTER = str.maketrans("0158", "OISB")
_TO_DIGIT = str.maketrans("OILSB", "01158")
# Unicode White_Space, which every implementation trims. `str.strip()` alone also
# removes the separators U+001C to U+001F, which the others keep.
WHITE_SPACE = (
    "\t\n\x0b\x0c\r \x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006"
    "\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000"
)


class Segment(Enum):
    """The five segments of a postcode, `AA-99-H77-BB-55`, widest first."""

    STATE = "state"
    LGA = "lga"
    DISTRICT = "district"
    AREA = "area"
    UNIT = "unit"


_SPANS = {
    Segment.STATE: range(0, 2),
    Segment.LGA: range(2, 4),
    Segment.DISTRICT: range(4, 7),
    Segment.AREA: range(7, 9),
    Segment.UNIT: range(9, 11),
}
_ALPHA = frozenset({Segment.STATE, Segment.AREA})
_NUMERIC = frozenset({Segment.LGA, Segment.UNIT})


@dataclass(frozen=True, slots=True)
class WrongLength:
    """The input did not hold exactly 11 letters and digits."""

    found: int

    def __str__(self) -> str:
        return f"expected {LENGTH} letters and digits, found {self.found}"


@dataclass(frozen=True, slots=True)
class InvalidCharacter:
    """The input held something other than letters, digits, spaces and hyphens."""

    char: str
    index: int

    def __str__(self) -> str:
        return f"invalid character {self.char!r} at index {self.index}"


@dataclass(frozen=True, slots=True)
class InvalidSegment:
    """A segment has the wrong shape, such as digits in the state or `00` as a unit."""

    segment: Segment

    def __str__(self) -> str:
        return f"invalid {self.segment.value} segment"


ParseError: TypeAlias = WrongLength | InvalidCharacter | InvalidSegment


@dataclass(frozen=True, slots=True, order=True)
class Postcode:
    """A well-formed postcode, held in its compact upper-case form.

    Well formed is not the same as assigned: only the NIPOST API knows whether
    a code belongs to a real building. Build one with `parse`; constructing it
    from an unchecked string raises `ValueError`, as that is a programming error.
    """

    compact: str

    def __post_init__(self) -> None:
        if _collect(self.compact) != self.compact or _validate(self.compact) is not None:
            raise ValueError(f"not a compact upper-case postcode: {self.compact!r}")

    def __str__(self) -> str:
        return self.prefix(Segment.UNIT)

    def __repr__(self) -> str:
        return f"Postcode('{self}')"

    @property
    def spaced(self) -> str:
        """The form shown to people, `EK 01 A03 FK 01`."""
        return " ".join(self.segment(s) for s in Segment)

    @property
    def state(self) -> str:
        return self.segment(Segment.STATE)

    @property
    def lga(self) -> str:
        return self.segment(Segment.LGA)

    @property
    def district(self) -> str:
        return self.segment(Segment.DISTRICT)

    @property
    def area(self) -> str:
        return self.segment(Segment.AREA)

    @property
    def unit(self) -> str:
        return self.segment(Segment.UNIT)

    def segment(self, segment: Segment) -> str:
        return _part(self.compact, segment)

    def prefix(self, through: Segment) -> str:
        """The hyphenated code down to `through`: `prefix(Segment.AREA)` is `EK-01-A03-FK`."""
        order = list(Segment)
        return "-".join(self.segment(s) for s in order[: order.index(through) + 1])


@dataclass(frozen=True, slots=True)
class Corrected:
    """The result of `parse_lenient`."""

    postcode: Postcode
    corrections: int
    """How many characters were swapped for their look-alike."""


def parse(text: str) -> Postcode | ParseError:
    """Parse a hyphenated, spaced or compact code in either case.

    >>> parse("ek 01 a03 fk 01")
    Postcode('EK-01-A03-FK-01')
    >>> parse("EK-00-A03-FK-01")
    InvalidSegment(segment=<Segment.LGA: 'lga'>)
    """
    compact = _collect(text)
    if not isinstance(compact, str):
        return compact
    error = _validate(compact)
    return error if error is not None else Postcode(compact)


def parse_lenient(text: str) -> Corrected | ParseError:
    """Parse after swapping look-alikes that cannot occur where they stand: `0 1 5 8`
    become `O I S B` where a letter is required, and `O I L S B` become `0 1 1 5 8`
    where a digit is. The district allows both, so it is never rewritten.

    The result is well formed but may not be the code the user meant, so confirm
    it with them when `corrections` is not zero.

    >>> parse_lenient("EK-O1-A03-FK-0I")
    Corrected(postcode=Postcode('EK-01-A03-FK-01'), corrections=2)
    """
    raw = _collect(text)
    if not isinstance(raw, str):
        return raw
    fixed = "".join(_unconfuse(s, _part(raw, s)) for s in Segment)
    error = _validate(fixed)
    if error is not None:
        return error
    return Corrected(Postcode(fixed), sum(a != b for a, b in zip(raw, fixed, strict=True)))


def from_segments(
    state: str, lga: str, district: str, area: str, unit: str
) -> Postcode | ParseError:
    """Build a code from its segments, zero-filling the LGA and unit.

    >>> from_segments("ek", "1", "a03", "fk", "1")
    Postcode('EK-01-A03-FK-01')
    """
    values = (state, lga, district, area, unit)
    padded = [_padded(s, v) for s, v in zip(Segment, values, strict=True)]
    error = next((p for p in padded if isinstance(p, InvalidSegment)), None)
    if error is not None:
        return error
    return parse("".join(p for p in padded if isinstance(p, str)))


def is_valid(text: str) -> bool:
    """Whether `text` is a well-formed postcode."""
    return isinstance(parse(text), Postcode)


def _collect(text: str) -> str | ParseError:
    kept = [(index, char) for index, char in enumerate(text) if char not in _SEPARATORS]
    invalid = next(((i, c) for i, c in kept if not (c.isascii() and c.isalnum())), None)
    if invalid is not None:
        return InvalidCharacter(char=invalid[1], index=invalid[0])
    if len(kept) != LENGTH:
        return WrongLength(found=len(kept))
    return "".join(char for _, char in kept).upper()


def _part(compact: str, segment: Segment) -> str:
    span = _SPANS[segment]
    return compact[span.start : span.stop]


def _validate(compact: str) -> InvalidSegment | None:
    return next((InvalidSegment(s) for s in Segment if not _accepts(s, _part(compact, s))), None)


def _accepts(segment: Segment, text: str) -> bool:
    chars = set(text)
    if segment in _ALPHA:
        return chars <= _LETTERS
    if segment in _NUMERIC:
        return chars <= _DIGITS and text != "00"
    return chars <= _LETTERS | _DIGITS


def _unconfuse(segment: Segment, text: str) -> str:
    if segment in _ALPHA:
        return text.translate(_TO_LETTER)
    if segment in _NUMERIC:
        return text.translate(_TO_DIGIT)
    return text


def _padded(segment: Segment, value: str) -> str | InvalidSegment:
    text, width = value.strip(WHITE_SPACE), len(_SPANS[segment])
    shortest = 1 if segment in _NUMERIC else width
    fits = shortest <= len(text) <= width and text.isascii() and text.isalnum()
    return text.rjust(width, "0") if fits else InvalidSegment(segment)
