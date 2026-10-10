# ng-postcode for SQL

Nigeria's NDAPS postcode as a column type in PostgreSQL and DuckDB. Both files are plain SQL with no extension to build, so they load on managed services, and both give the same answers as the libraries: [`scripts/sql_conformance.py`](../scripts/sql_conformance.py) runs the shared cases in [`spec/vectors.json`](../spec/vectors.json) against them.

```sh
psql -f sql/postgres.sql          # PostgreSQL, tested on 14 and 17
duckdb my.db < sql/duckdb.sql     # DuckDB, tested on 1.5
```

Each numbered version of the two files is attached to a [GitHub release](https://github.com/Adeniyikayodee/ng-postcode/releases) tagged `sql-v`, so you can pin the copy you load.

## Store and check

```sql
CREATE TABLE customers (
    id       bigint PRIMARY KEY,
    postcode ng_postcode            -- refuses anything that is not a compact code
);

INSERT INTO customers VALUES (1, ng_postcode_parse('ek 01 a03 fk 01'));

SELECT postcode, ng_postcode_format(postcode) FROM customers;
-- EK01A03FK01 | EK-01-A03-FK-01
```

`ng_postcode_parse` accepts a hyphenated, spaced, or compact code in either case, and returns NULL for one that is not well formed. DuckDB has no domains, so declare the column as `text` with `CHECK (ng_postcode_parse(postcode) IS NOT DISTINCT FROM postcode)`. A plain `=` would let a malformed code through, because comparing with NULL is not false.

## Group by state, LGA, district, or area

A prefix is a code cut off after one of its segments. It needs no map: every building in a district shares that district's prefix.

```sql
SELECT ng_postcode_format(ng_postcode_truncate(postcode, 'district')) AS district, count(*)
FROM customers
GROUP BY 1;
-- EK-01-A03 | 1
```

To select one district, compare a range so that the column's index is used:

```sql
SELECT * FROM customers WHERE postcode >= 'EK01A03' AND postcode < 'EK01A03' || '~';
```

## Functions

| Function | Returns |
| --- | --- |
| `ng_postcode_parse(text)` | The compact code, or NULL |
| `ng_postcode_prefix_parse(text)` | The compact prefix, such as `EK01A03`, or NULL |
| `ng_postcode_format(code or prefix)` | The hyphenated form |
| `ng_postcode_truncate(code, segment)` | The prefix through `state`, `lga`, `district`, `area`, or `unit` |
| `ng_postcode_parent(prefix)` | The prefix one segment shorter, or NULL for a state |
| `ng_postcode_within(code, prefix)` | Whether the code starts with the prefix |
| `ng_postcode_version()` | The version of the file that was loaded |

A well-formed code is not necessarily assigned to a building. Only the NIPOST API can confirm that, through one of the [libraries](../README.md).
