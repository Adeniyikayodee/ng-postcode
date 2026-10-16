---
description: "Count or select records by Nigerian state, LGA, district or area by cutting each NIPOST postcode to a prefix, in SQL, Python or Polars."
---

# Group records by place

A Nigerian postcode says where a building is at five levels: state, LGA, district, area, and building. Cut a code off after one of those and you have a prefix that every building in that place shares. Counting customers, deliveries, or cases by district is then an ordinary group-by, with no map and no boundary files.

| Cut after | Prefix of `EK-01-A03-FK-01` |
| --- | --- |
| State | `EK` |
| LGA | `EK-01` |
| District | `EK-01-A03` |
| Area | `EK-01-A03-FK` |

## In Python

```python
from collections import Counter

from ng_postcode import Postcode, Segment, parse


def district(text: str) -> str | None:
    """The district a code is in, or None for one that is not well formed."""
    code = parse(text)
    return str(code.truncate(Segment.DISTRICT)) if isinstance(code, Postcode) else None


rows = ["EK-01-A03-FK-01", "ek 01 a03 zz 14", "LA11W06TC10", "not a code"]
print(Counter(map(district, rows)))
# Counter({'EK-01-A03': 2, 'LA-11-W06': 1, None: 1})
```

The same function works on a pandas column:

```python
frame["postcode"].map(district).value_counts(dropna=False)
```

For Polars, the [`ng-postcode-polars`](https://github.com/Adeniyikayodee/ng-postcode/tree/main/native/polars) plugin does the work in Rust in one pass over the column, with no Python call for each row:

```python
import ng_postcode_polars  # adds the `ng` namespace

table.group_by(pl.col("postcode").ng.truncate("district").ng.format()).len()
```

Rows that are not well-formed codes come out under `None`, so they are counted and visible.

## In SQL

```sql
SELECT ng_postcode_format(ng_postcode_truncate(postcode, 'district')) AS district, count(*)
FROM customers
GROUP BY 1;
```

The functions for PostgreSQL and DuckDB are in [`sql/`](https://github.com/Adeniyikayodee/ng-postcode/tree/main/sql).

## What a prefix does not tell you

A prefix groups buildings that NIPOST placed in the same district or area. It carries no name, boundary, or population. Names come from NIPOST's lookup, and a well-formed code is not necessarily assigned to a building.
