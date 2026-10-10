-- Nigeria's NDAPS postcode for PostgreSQL (tested on 14 and 17): two domains and a few functions.
-- Plain SQL, so it loads on managed services that accept no extensions:
--
--     psql -f sql/postgres.sql
--
-- Store the compact form in an ng_postcode column. Behaviour follows spec/vectors.json,
-- as the libraries do; scripts/sql_conformance.py runs those cases against this file.

-- A well-formed code in its compact form, EK01A03FK01. Well formed is not assigned:
-- only the NIPOST API knows whether a code belongs to a building.
CREATE DOMAIN ng_postcode AS text COLLATE "C"
    CHECK (VALUE ~ '^[A-Z]{2}(0[1-9]|[1-9][0-9])[A-Z0-9]{3}[A-Z]{2}(0[1-9]|[1-9][0-9])$');

-- A code cut off after one of its segments, such as the district EK01A03. A whole code
-- is the narrowest prefix.
CREATE DOMAIN ng_postcode_prefix AS text COLLATE "C"
    CHECK (VALUE ~ '^[A-Z]{2}((0[1-9]|[1-9][0-9])([A-Z0-9]{3}([A-Z]{2}(0[1-9]|[1-9][0-9])?)?)?)?$');

-- The letters and digits of a hyphenated, spaced or compact code, in upper case, or NULL
-- if it holds anything else. translate() is used because upper() follows the locale.
CREATE FUNCTION ng_postcode_compact(text) RETURNS text
    LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT CASE WHEN $1 COLLATE "C" ~ '^[A-Za-z0-9 -]*$' THEN translate(
        $1, 'abcdefghijklmnopqrstuvwxyz -', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ') END
$$;

-- The code in any style as an ng_postcode, or NULL if it is not well formed.
CREATE FUNCTION ng_postcode_parse(text) RETURNS ng_postcode
    LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT CASE WHEN c ~ '^[A-Z]{2}(0[1-9]|[1-9][0-9])[A-Z0-9]{3}[A-Z]{2}(0[1-9]|[1-9][0-9])$'
        THEN c::ng_postcode END
    FROM (SELECT ng_postcode_compact($1) COLLATE "C") AS scanned(c)
$$;

-- The prefix in any style as an ng_postcode_prefix, or NULL if it is not well formed.
CREATE FUNCTION ng_postcode_prefix_parse(text) RETURNS ng_postcode_prefix
    LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT CASE WHEN c ~ '^[A-Z]{2}((0[1-9]|[1-9][0-9])([A-Z0-9]{3}([A-Z]{2}(0[1-9]|[1-9][0-9])?)?)?)?$'
        THEN c::ng_postcode_prefix END
    FROM (SELECT ng_postcode_compact($1) COLLATE "C") AS scanned(c)
$$;

-- The hyphenated form of a code or a prefix: EK-01-A03-FK-01, or EK-01-A03.
CREATE FUNCTION ng_postcode_format(ng_postcode_prefix) RETURNS text
    LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT concat_ws('-', substr($1, 1, 2), nullif(substr($1, 3, 2), ''),
        nullif(substr($1, 5, 3), ''), nullif(substr($1, 8, 2), ''), nullif(substr($1, 10, 2), ''))
$$;

-- The code cut off after a segment: 'state', 'lga', 'district', 'area' or 'unit'.
-- NULL for any other name.
CREATE FUNCTION ng_postcode_truncate(ng_postcode, through text) RETURNS ng_postcode_prefix
    LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT left($1, CASE through WHEN 'state' THEN 2 WHEN 'lga' THEN 4 WHEN 'district' THEN 7
        WHEN 'area' THEN 9 WHEN 'unit' THEN 11 END)::ng_postcode_prefix
$$;

-- The prefix one segment shorter, or NULL for a state.
CREATE FUNCTION ng_postcode_parent(ng_postcode_prefix) RETURNS ng_postcode_prefix
    LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT left($1, CASE length($1) WHEN 11 THEN 9 WHEN 9 THEN 7 WHEN 7 THEN 4 WHEN 4 THEN 2 END)
        ::ng_postcode_prefix
$$;

-- Whether a code starts with a prefix. In a WHERE clause, a range on the column uses its
-- index: code >= prefix AND code < prefix || '~'.
CREATE FUNCTION ng_postcode_within(ng_postcode, ng_postcode_prefix) RETURNS boolean
    LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT left($1, length($2)) = $2
$$;
