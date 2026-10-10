"""Polars expressions for Nigeria's NIPOST digital postcode (NDAPS).

Importing this module adds an `ng` namespace to every expression:

>>> import polars as pl
>>> import ng_postcode_polars
>>> frame = pl.DataFrame({"postcode": ["ek 01 a03 fk 01", "LA-11-W06-TC-10", "100001"]})
>>> frame.select(pl.col("postcode").ng.parse()).to_series().to_list()
['EK01A03FK01', 'LA11W06TC10', None]

A value that is not well formed becomes null, so it can be counted and followed up.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import polars as pl
from polars.plugins import register_plugin_function

Segment = Literal["state", "lga", "district", "area", "unit"]

_LIB = Path(__file__).parent


@pl.api.register_expr_namespace("ng")
class Postcodes:
    def __init__(self, expr: pl.Expr) -> None:
        self._expr = expr

    def _call(self, name: str, **kwargs: str) -> pl.Expr:
        return register_plugin_function(
            plugin_path=_LIB,
            function_name=name,
            args=[self._expr],
            kwargs=kwargs or None,
            is_elementwise=True,
        )

    def parse(self) -> pl.Expr:
        """The compact code, `EK01A03FK01`, from a code typed in any style."""
        return self._call("parse")

    def parse_prefix(self) -> pl.Expr:
        """The compact prefix, such as `EK01A03`, from a prefix typed in any style."""
        return self._call("parse_prefix")

    def format(self) -> pl.Expr:
        """The hyphenated form of a code or a prefix, `EK-01-A03-FK-01` or `EK-01-A03`."""
        return self._call("format")

    def truncate(self, through: Segment) -> pl.Expr:
        """The compact prefix of a code, cut off after a segment: the value to group by."""
        return self._call("truncate", through=through)

    def is_valid(self) -> pl.Expr:
        """Whether the value is a well-formed code."""
        return self._call("is_valid")


__all__ = ["Postcodes", "Segment"]
