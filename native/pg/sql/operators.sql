-- Comparison, sorting and hashing for both types. Each value is an int8 whose order is the
-- order of the compact text, so PostgreSQL's own int8 functions do the work.

CREATE FUNCTION ng_postcode_eq(ng_postcode, ng_postcode) RETURNS boolean IMMUTABLE STRICT PARALLEL SAFE LANGUAGE internal AS 'int8eq';
CREATE FUNCTION ng_postcode_ne(ng_postcode, ng_postcode) RETURNS boolean IMMUTABLE STRICT PARALLEL SAFE LANGUAGE internal AS 'int8ne';
CREATE FUNCTION ng_postcode_lt(ng_postcode, ng_postcode) RETURNS boolean IMMUTABLE STRICT PARALLEL SAFE LANGUAGE internal AS 'int8lt';
CREATE FUNCTION ng_postcode_le(ng_postcode, ng_postcode) RETURNS boolean IMMUTABLE STRICT PARALLEL SAFE LANGUAGE internal AS 'int8le';
CREATE FUNCTION ng_postcode_gt(ng_postcode, ng_postcode) RETURNS boolean IMMUTABLE STRICT PARALLEL SAFE LANGUAGE internal AS 'int8gt';
CREATE FUNCTION ng_postcode_ge(ng_postcode, ng_postcode) RETURNS boolean IMMUTABLE STRICT PARALLEL SAFE LANGUAGE internal AS 'int8ge';
CREATE FUNCTION ng_postcode_cmp(ng_postcode, ng_postcode) RETURNS integer IMMUTABLE STRICT PARALLEL SAFE LANGUAGE internal AS 'btint8cmp';
CREATE FUNCTION ng_postcode_hash(ng_postcode) RETURNS integer IMMUTABLE STRICT PARALLEL SAFE LANGUAGE internal AS 'hashint8';
CREATE FUNCTION ng_postcode_hash_extended(ng_postcode, bigint) RETURNS bigint IMMUTABLE STRICT PARALLEL SAFE LANGUAGE internal AS 'hashint8extended';

CREATE OPERATOR = (LEFTARG = ng_postcode, RIGHTARG = ng_postcode, FUNCTION = ng_postcode_eq, COMMUTATOR = =, NEGATOR = <>,
    RESTRICT = eqsel, JOIN = eqjoinsel, HASHES, MERGES);
CREATE OPERATOR <> (LEFTARG = ng_postcode, RIGHTARG = ng_postcode, FUNCTION = ng_postcode_ne, COMMUTATOR = <>, NEGATOR = =,
    RESTRICT = neqsel, JOIN = neqjoinsel);
CREATE OPERATOR < (LEFTARG = ng_postcode, RIGHTARG = ng_postcode, FUNCTION = ng_postcode_lt, COMMUTATOR = >, NEGATOR = >=,
    RESTRICT = scalarltsel, JOIN = scalarltjoinsel);
CREATE OPERATOR <= (LEFTARG = ng_postcode, RIGHTARG = ng_postcode, FUNCTION = ng_postcode_le, COMMUTATOR = >=, NEGATOR = >,
    RESTRICT = scalarlesel, JOIN = scalarlejoinsel);
CREATE OPERATOR > (LEFTARG = ng_postcode, RIGHTARG = ng_postcode, FUNCTION = ng_postcode_gt, COMMUTATOR = <, NEGATOR = <=,
    RESTRICT = scalargtsel, JOIN = scalargtjoinsel);
CREATE OPERATOR >= (LEFTARG = ng_postcode, RIGHTARG = ng_postcode, FUNCTION = ng_postcode_ge, COMMUTATOR = <=, NEGATOR = <,
    RESTRICT = scalargesel, JOIN = scalargejoinsel);

CREATE OPERATOR CLASS ng_postcode_btree_ops DEFAULT FOR TYPE ng_postcode USING btree AS
    OPERATOR 1 <, OPERATOR 2 <=, OPERATOR 3 =, OPERATOR 4 >=, OPERATOR 5 >,
    FUNCTION 1 ng_postcode_cmp(ng_postcode, ng_postcode);
CREATE OPERATOR CLASS ng_postcode_hash_ops DEFAULT FOR TYPE ng_postcode USING hash AS
    OPERATOR 1 =, FUNCTION 1 ng_postcode_hash(ng_postcode), FUNCTION 2 ng_postcode_hash_extended(ng_postcode, bigint);

CREATE FUNCTION ng_postcode_prefix_eq(ng_postcode_prefix, ng_postcode_prefix) RETURNS boolean IMMUTABLE STRICT PARALLEL SAFE LANGUAGE internal AS 'int8eq';
CREATE FUNCTION ng_postcode_prefix_ne(ng_postcode_prefix, ng_postcode_prefix) RETURNS boolean IMMUTABLE STRICT PARALLEL SAFE LANGUAGE internal AS 'int8ne';
CREATE FUNCTION ng_postcode_prefix_lt(ng_postcode_prefix, ng_postcode_prefix) RETURNS boolean IMMUTABLE STRICT PARALLEL SAFE LANGUAGE internal AS 'int8lt';
CREATE FUNCTION ng_postcode_prefix_le(ng_postcode_prefix, ng_postcode_prefix) RETURNS boolean IMMUTABLE STRICT PARALLEL SAFE LANGUAGE internal AS 'int8le';
CREATE FUNCTION ng_postcode_prefix_gt(ng_postcode_prefix, ng_postcode_prefix) RETURNS boolean IMMUTABLE STRICT PARALLEL SAFE LANGUAGE internal AS 'int8gt';
CREATE FUNCTION ng_postcode_prefix_ge(ng_postcode_prefix, ng_postcode_prefix) RETURNS boolean IMMUTABLE STRICT PARALLEL SAFE LANGUAGE internal AS 'int8ge';
CREATE FUNCTION ng_postcode_prefix_cmp(ng_postcode_prefix, ng_postcode_prefix) RETURNS integer IMMUTABLE STRICT PARALLEL SAFE LANGUAGE internal AS 'btint8cmp';
CREATE FUNCTION ng_postcode_prefix_hash(ng_postcode_prefix) RETURNS integer IMMUTABLE STRICT PARALLEL SAFE LANGUAGE internal AS 'hashint8';
CREATE FUNCTION ng_postcode_prefix_hash_extended(ng_postcode_prefix, bigint) RETURNS bigint IMMUTABLE STRICT PARALLEL SAFE LANGUAGE internal AS 'hashint8extended';

CREATE OPERATOR = (LEFTARG = ng_postcode_prefix, RIGHTARG = ng_postcode_prefix, FUNCTION = ng_postcode_prefix_eq, COMMUTATOR = =, NEGATOR = <>,
    RESTRICT = eqsel, JOIN = eqjoinsel, HASHES, MERGES);
CREATE OPERATOR <> (LEFTARG = ng_postcode_prefix, RIGHTARG = ng_postcode_prefix, FUNCTION = ng_postcode_prefix_ne, COMMUTATOR = <>, NEGATOR = =,
    RESTRICT = neqsel, JOIN = neqjoinsel);
CREATE OPERATOR < (LEFTARG = ng_postcode_prefix, RIGHTARG = ng_postcode_prefix, FUNCTION = ng_postcode_prefix_lt, COMMUTATOR = >, NEGATOR = >=,
    RESTRICT = scalarltsel, JOIN = scalarltjoinsel);
CREATE OPERATOR <= (LEFTARG = ng_postcode_prefix, RIGHTARG = ng_postcode_prefix, FUNCTION = ng_postcode_prefix_le, COMMUTATOR = >=, NEGATOR = >,
    RESTRICT = scalarlesel, JOIN = scalarlejoinsel);
CREATE OPERATOR > (LEFTARG = ng_postcode_prefix, RIGHTARG = ng_postcode_prefix, FUNCTION = ng_postcode_prefix_gt, COMMUTATOR = <, NEGATOR = <=,
    RESTRICT = scalargtsel, JOIN = scalargtjoinsel);
CREATE OPERATOR >= (LEFTARG = ng_postcode_prefix, RIGHTARG = ng_postcode_prefix, FUNCTION = ng_postcode_prefix_ge, COMMUTATOR = <=, NEGATOR = <,
    RESTRICT = scalargesel, JOIN = scalargejoinsel);

CREATE OPERATOR CLASS ng_postcode_prefix_btree_ops DEFAULT FOR TYPE ng_postcode_prefix USING btree AS
    OPERATOR 1 <, OPERATOR 2 <=, OPERATOR 3 =, OPERATOR 4 >=, OPERATOR 5 >,
    FUNCTION 1 ng_postcode_prefix_cmp(ng_postcode_prefix, ng_postcode_prefix);
CREATE OPERATOR CLASS ng_postcode_prefix_hash_ops DEFAULT FOR TYPE ng_postcode_prefix USING hash AS
    OPERATOR 1 =, FUNCTION 1 ng_postcode_prefix_hash(ng_postcode_prefix), FUNCTION 2 ng_postcode_prefix_hash_extended(ng_postcode_prefix, bigint);
