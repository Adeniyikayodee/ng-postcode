-- Nigeria's NDAPS postcode for DuckDB: macros with the same names and answers as
-- sql/postgres.sql.
-- Version 1.0.0
--
--     .read sql/duckdb.sql
--
-- DuckDB has no domains, so keep a column to the compact form with a constraint:
-- CHECK (ng_postcode_parse(code) IS NOT DISTINCT FROM code). scripts/sql_conformance.py
-- runs the cases in spec/vectors.json against this file.

-- The version of this file, so that an installed copy can be told from a newer one.
CREATE OR REPLACE MACRO ng_postcode_version() AS '1.0.0';

-- The letters and digits of a hyphenated, spaced or compact code, in upper case, or NULL
-- if it holds anything else.
CREATE OR REPLACE MACRO ng_postcode_compact(t) AS
    CASE WHEN regexp_full_match(t, '[A-Za-z0-9 -]*') THEN translate(
        t, 'abcdefghijklmnopqrstuvwxyz -', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ') END;

-- The code in any style in its compact form, EK01A03FK01, or NULL if it is not well formed.
CREATE OR REPLACE MACRO ng_postcode_parse(t) AS
    CASE WHEN regexp_full_match(ng_postcode_compact(t),
        '[A-Z]{2}(0[1-9]|[1-9][0-9])[A-Z0-9]{3}[A-Z]{2}(0[1-9]|[1-9][0-9])')
        THEN ng_postcode_compact(t) END;

-- A code cut off after one of its segments, such as the district EK01A03, or NULL.
CREATE OR REPLACE MACRO ng_postcode_prefix_parse(t) AS
    CASE WHEN regexp_full_match(ng_postcode_compact(t),
        '[A-Z]{2}((0[1-9]|[1-9][0-9])([A-Z0-9]{3}([A-Z]{2}(0[1-9]|[1-9][0-9])?)?)?)?')
        THEN ng_postcode_compact(t) END;

-- The hyphenated form of a code or a prefix: EK-01-A03-FK-01, or EK-01-A03.
-- concat_ws() skips NULLs, so NULL is passed through by hand.
CREATE OR REPLACE MACRO ng_postcode_format(c) AS
    CASE WHEN c IS NOT NULL THEN concat_ws('-', substr(c, 1, 2), nullif(substr(c, 3, 2), ''),
        nullif(substr(c, 5, 3), ''), nullif(substr(c, 8, 2), ''), nullif(substr(c, 10, 2), '')) END;

-- The code cut off after a segment: 'state', 'lga', 'district', 'area' or 'unit'.
-- NULL for any other name.
CREATE OR REPLACE MACRO ng_postcode_truncate(c, through) AS
    left(c, CASE through WHEN 'state' THEN 2 WHEN 'lga' THEN 4 WHEN 'district' THEN 7
        WHEN 'area' THEN 9 WHEN 'unit' THEN 11 END);

-- The prefix one segment shorter, or NULL for a state.
CREATE OR REPLACE MACRO ng_postcode_parent(p) AS
    left(p, CASE length(p) WHEN 11 THEN 9 WHEN 9 THEN 7 WHEN 7 THEN 4 WHEN 4 THEN 2 END);

-- Whether a code starts with a prefix.
CREATE OR REPLACE MACRO ng_postcode_within(c, p) AS starts_with(c, p);
