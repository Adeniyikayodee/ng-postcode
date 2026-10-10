"""Nigeria's National Digital Alphanumeric Postcode (NDAPS), the building-level
postcode issued by NIPOST.

Expected failures come back as values, never exceptions:

>>> from ng_postcode import Postcode, Segment, parse
>>> code = parse("ek 01 a03 fk 01")
>>> isinstance(code, Postcode)
True
>>> str(code), code.compact, code.spaced
('EK-01-A03-FK-01', 'EK01A03FK01', 'EK 01 A03 FK 01')
>>> code.prefix(Segment.AREA)
'EK-01-A03-FK'
>>> str(parse("EK-01-A03"))
'expected 11 letters and digits, found 7'
"""

from ._postcode import (
    Corrected,
    InvalidCharacter,
    InvalidSegment,
    ParseError,
    Postcode,
    Prefix,
    Segment,
    WrongLength,
    WrongPrefixLength,
    from_segments,
    is_valid,
    parse,
    parse_lenient,
    parse_prefix,
)

__all__ = [
    "Corrected",
    "InvalidCharacter",
    "InvalidSegment",
    "ParseError",
    "Postcode",
    "Prefix",
    "Segment",
    "WrongLength",
    "WrongPrefixLength",
    "from_segments",
    "is_valid",
    "parse",
    "parse_lenient",
    "parse_prefix",
]
