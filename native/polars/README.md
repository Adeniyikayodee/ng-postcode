# ng-postcode-polars

Polars expressions for Nigeria's NIPOST digital postcode (NDAPS), the 11-character building code such as `EK-01-A03-FK-01`. They parse, format, and cut codes down to a state, LGA, district, or area, so that a DataFrame can be grouped by place with no map.

The work is done in Rust by the same core as the [`ng-postcode`](https://github.com/Adeniyikayodee/ng-postcode) libraries, in one pass over the column. On a million rows that is about 40 times faster than calling a Python function for each row.

```sh
pip install ng-postcode-polars
```

## Usage

Importing the package adds an `ng` namespace to every expression.

```python
import polars as pl
import ng_postcode_polars  # noqa: F401

frame = pl.DataFrame({"postcode": ["ek 01 a03 fk 01", "EK-01-A03-ZZ-14", "la11w06tc10", "100001"]})

print(
    frame.with_columns(
        code=pl.col("postcode").ng.parse(),
        ok=pl.col("postcode").ng.is_valid(),
    )
)
# postcode         code         ok
# ek 01 a03 fk 01  EK01A03FK01  true
# EK-01-A03-ZZ-14  EK01A03ZZ14  true
# la11w06tc10      LA11W06TC10  true
# 100001           null         false
```

A value that is not a well-formed code becomes null, so it can be counted and followed up.

## Group by place

```python
by_district = frame.group_by(
    pl.col("postcode").ng.truncate("district").ng.format().alias("district")
).len()
# EK-01-A03  2
# LA-11-W06  1
# null       1
```

## Expressions

| Expression | Returns |
| --- | --- |
| `.ng.parse()` | The compact code, `EK01A03FK01`, or null |
| `.ng.is_valid()` | Whether the value is a well-formed code |
| `.ng.format()` | The hyphenated form of a code or a prefix |
| `.ng.truncate(segment)` | The compact prefix through `state`, `lga`, `district`, `area`, or `unit` |
| `.ng.parse_prefix()` | The compact prefix, such as `EK01A03`, or null |

A type checker cannot see a namespace that is registered at import time. For checked code, call the class directly: `Postcodes(pl.col("postcode")).parse()`.

The expressions follow the shared cases in [`spec/vectors.json`](https://github.com/Adeniyikayodee/ng-postcode/blob/main/spec/vectors.json), as every `ng-postcode` library does. A well-formed code is not necessarily assigned to a building, and only the NIPOST API can confirm that.

## License

MIT
