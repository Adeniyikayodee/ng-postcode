# ng_postcode for PostgreSQL

Nigeria's NIPOST digital postcode (NDAPS) as native PostgreSQL types, written in Rust on the same core as the [`ng-postcode`](https://github.com/Adeniyikayodee/ng-postcode) libraries.

It has the function names and answers of the plain SQL file in [`sql/`](../../sql), so a query written for one runs on the other. The difference is storage. A code is held as 8 bytes and compared as an integer, where the SQL file stores 11 characters of text.

Use the SQL file on a managed service that accepts no extensions. Use this extension where you can install one and the table is large.

## What you gain

Measured on PostgreSQL 17 with one million codes, on one laptop:

| | SQL file | Extension |
| --- | --- | --- |
| Table size | 42 MB | 35 MB |
| Index size | 30 MB | 21 MB |
| Count by district | 5.6 s | 1.4 s |

Sorting and joining on the column were within a fifth of each other.

## Install

Each [release](https://github.com/Adeniyikayodee/ng-postcode/releases) tagged `pg-v` attaches a package for each PostgreSQL version from 14 to 18, for x86-64 and ARM Linux, built against the PostgreSQL project's own Debian and Ubuntu packages. Unpack the one for your version at the root of the filesystem:

```sh
sudo tar -xzf ng_postcode-0.1.0-pg17-x86_64.tar.gz -C /
```

Then, in the database:

```sql
CREATE EXTENSION ng_postcode;
```

To build from source, install [`cargo-pgrx`](https://github.com/pgcentralfoundation/pgrx) 0.19.3 and run `cargo pgrx install --release` in this directory.

## Use

```sql
CREATE TABLE customers (
    id       bigint PRIMARY KEY,
    postcode ng_postcode
);

INSERT INTO customers VALUES (1, 'ek 01 a03 fk 01'), (2, 'EK-01-A03-ZZ-14');

SELECT postcode, ng_postcode_format(postcode) FROM customers;
-- EK01A03FK01 | EK-01-A03-FK-01
-- EK01A03ZZ14 | EK-01-A03-ZZ-14
```

The type accepts a code typed in any style and refuses one that is not well formed. To turn a doubtful value into NULL without an error, pass it through `ng_postcode_parse`.

## Group and select by place

```sql
SELECT ng_postcode_format(ng_postcode_truncate(postcode, 'district')) AS district, count(*)
FROM customers
GROUP BY 1;
-- EK-01-A03 | 2
```

`code <@ prefix` tests whether a code starts with a prefix. To make selection by district use an index, index the truncated value and compare it for equality:

```sql
CREATE INDEX ON customers (ng_postcode_truncate(postcode, 'district'));

SELECT * FROM customers WHERE ng_postcode_truncate(postcode, 'district') = 'EK01A03';
```

## Types and functions

| Name | What it is |
| --- | --- |
| `ng_postcode` | A well-formed code, 8 bytes, with btree and hash index support |
| `ng_postcode_prefix` | A code cut off after a segment, such as `EK01A03`; a whole code is the narrowest prefix |
| `ng_postcode_parse(text)` | The code, or NULL |
| `ng_postcode_prefix_parse(text)` | The prefix, or NULL |
| `ng_postcode_format(code or prefix)` | The hyphenated form |
| `ng_postcode_truncate(code, segment)` | The prefix through `state`, `lga`, `district`, `area`, or `unit` |
| `ng_postcode_parent(prefix)` | The prefix one segment shorter, or NULL for a state |
| `ng_postcode_within(code, prefix)`, `code <@ prefix` | Whether the code starts with the prefix |
| `ng_postcode_version()` | The version of the installed extension |

Both types sort as their compact text does, so a prefix comes just before the codes it contains.

The extension runs the shared cases in [`spec/vectors.json`](../../spec/vectors.json) through the same script as the SQL file. A well-formed code is not necessarily assigned to a building, and only the NIPOST API can confirm that.

## License

MIT
