//! Nigeria's NIPOST digital postcode (NDAPS) as native PostgreSQL types.
//!
//! The functions have the names and answers of `sql/postgres.sql`, so a query written for
//! that file runs here unchanged. The difference is the storage: a code is 8 bytes held by
//! value and compared as an integer, where the SQL file stores 11 characters of text.

use core::ffi::CStr;
use std::ffi::CString;

use ng_postcode::{Postcode, Segment};
use pgrx::callconv::{Arg, ArgAbi, BoxRet, FcInfo};
use pgrx::datum::Datum;
use pgrx::nullable::Nullable;
use pgrx::pgrx_sql_entity_graph::metadata::{
    ArgumentError, ReturnsError, ReturnsRef, SqlMappingRef, SqlTranslatable, TypeOrigin,
};
use pgrx::prelude::*;

::pgrx::pg_module_magic!(name, version);

const LEN: usize = 11;
/// The alphabet size at each position: letters, digits, or both.
const RADIX: [i64; LEN] = [26, 26, 10, 10, 36, 36, 36, 26, 26, 10, 10];
const SEGMENTS: [(Segment, &str, usize); 5] = [
    (Segment::State, "state", 2),
    (Segment::Lga, "lga", 4),
    (Segment::District, "district", 7),
    (Segment::Area, "area", 9),
    (Segment::Unit, "unit", 11),
];

/// A code as one number, in mixed radix, so that numbers sort as the compact text does.
/// It needs 50 bits.
#[repr(transparent)]
#[derive(Clone, Copy, PartialEq, Eq)]
pub struct Code(i64);

/// A prefix as the lowest number it contains, then three bits for how many segments it
/// holds. A prefix therefore sorts just before the longer prefixes it contains.
#[repr(transparent)]
#[derive(Clone, Copy, PartialEq, Eq)]
pub struct Prefix(i64);

/// Positions past the end of `compact` count as the lowest character.
fn pack(compact: &[u8]) -> i64 {
    RADIX.iter().enumerate().fold(0, |number, (at, &radix)| {
        let value = match (compact.get(at), radix) {
            (None, _) => 0,
            (Some(&byte @ b'0'..=b'9'), _) => (byte - b'0') as i64,
            (Some(&byte), 36) => (byte - b'A') as i64 + 10,
            (Some(&byte), _) => (byte - b'A') as i64,
        };
        number * radix + value
    })
}

fn unpack(mut number: i64) -> [u8; LEN] {
    let mut compact = [0; LEN];
    for (at, &radix) in RADIX.iter().enumerate().rev() {
        let value = (number % radix) as u8;
        number /= radix;
        compact[at] = match radix {
            26 => b'A' + value,
            36 if value >= 10 => b'A' + value - 10,
            _ => b'0' + value,
        };
    }
    compact
}

impl Code {
    fn new(code: Postcode) -> Self {
        Self(pack(code.as_str().as_bytes()))
    }

    fn compact(self) -> String {
        String::from_utf8(unpack(self.0).to_vec()).expect("ASCII")
    }
}

impl Prefix {
    fn new(prefix: ng_postcode::Prefix) -> Self {
        let level = SEGMENTS.iter().position(|(s, ..)| *s == prefix.through());
        Self(pack(prefix.as_str().as_bytes()) << 3 | level.expect("a segment") as i64)
    }

    fn compact(self) -> String {
        let length = SEGMENTS[(self.0 & 7) as usize].2;
        String::from_utf8(unpack(self.0 >> 3)[..length].to_vec()).expect("ASCII")
    }

    fn core(self) -> ng_postcode::Prefix {
        ng_postcode::Prefix::parse(&self.compact()).expect("a stored prefix is well formed")
    }
}

/// What pgrx needs to pass an `int8`-shaped type to and from SQL, under its own type name.
macro_rules! by_value {
    ($ty:ident, $sql:literal) => {
        impl IntoDatum for $ty {
            fn into_datum(self) -> Option<pg_sys::Datum> {
                self.0.into_datum()
            }

            fn type_oid() -> pg_sys::Oid {
                pgrx::wrappers::regtypein($sql)
            }
        }

        impl FromDatum for $ty {
            unsafe fn from_polymorphic_datum(
                datum: pg_sys::Datum,
                is_null: bool,
                typoid: pg_sys::Oid,
            ) -> Option<Self> {
                unsafe { i64::from_polymorphic_datum(datum, is_null, typoid).map(Self) }
            }
        }

        unsafe impl SqlTranslatable for $ty {
            const TYPE_IDENT: &'static str = pgrx::pgrx_resolved_type!($ty);
            const TYPE_ORIGIN: TypeOrigin = TypeOrigin::ThisExtension;
            const ARGUMENT_SQL: Result<SqlMappingRef, ArgumentError> =
                Ok(SqlMappingRef::literal($sql));
            const RETURN_SQL: Result<ReturnsRef, ReturnsError> =
                Ok(ReturnsRef::One(SqlMappingRef::literal($sql)));
        }

        unsafe impl<'fcx> ArgAbi<'fcx> for $ty {
            unsafe fn unbox_arg_unchecked(arg: Arg<'_, 'fcx>) -> Self {
                let index = arg.index();
                unsafe { arg.unbox_arg_using_from_datum() }
                    .unwrap_or_else(|| panic!("argument {index} must not be null"))
            }

            unsafe fn unbox_nullable_arg(arg: Arg<'_, 'fcx>) -> Nullable<Self> {
                unsafe { arg.unbox_arg_using_from_datum().into() }
            }
        }

        unsafe impl BoxRet for $ty {
            unsafe fn box_into<'fcx>(self, fcinfo: &mut FcInfo<'fcx>) -> Datum<'fcx> {
                unsafe { fcinfo.return_optional_datum(self.into_datum()) }
            }
        }
    };
}

by_value!(Code, "ng_postcode");
by_value!(Prefix, "ng_postcode_prefix");

/// Input accepts a code in any style, and refuses one that is not well formed.
#[pg_extern(immutable, strict, parallel_safe, sql = false)]
fn ng_postcode_in(input: &CStr) -> Code {
    match Postcode::parse(&input.to_string_lossy()) {
        Ok(code) => Code::new(code),
        Err(error) => error!("invalid input syntax for type ng_postcode: {error}"),
    }
}

/// Output is the compact form, the one to store and compare.
#[pg_extern(immutable, strict, parallel_safe, sql = false)]
fn ng_postcode_out(code: Code) -> CString {
    CString::new(code.compact()).expect("no NUL")
}

#[pg_extern(immutable, strict, parallel_safe, sql = false)]
fn ng_postcode_prefix_in(input: &CStr) -> Prefix {
    match ng_postcode::Prefix::parse(&input.to_string_lossy()) {
        Ok(prefix) => Prefix::new(prefix),
        Err(error) => error!("invalid input syntax for type ng_postcode_prefix: {error}"),
    }
}

#[pg_extern(immutable, strict, parallel_safe, sql = false)]
fn ng_postcode_prefix_out(prefix: Prefix) -> CString {
    CString::new(prefix.compact()).expect("no NUL")
}

// The types and their input and output functions are declared together and by hand, so
// that each type is complete before anything else mentions it.
extension_sql!(
    r#"
CREATE TYPE ng_postcode;
CREATE FUNCTION ng_postcode_in(cstring) RETURNS ng_postcode
    IMMUTABLE STRICT PARALLEL SAFE LANGUAGE c AS 'MODULE_PATHNAME', 'ng_postcode_in_wrapper';
CREATE FUNCTION ng_postcode_out(ng_postcode) RETURNS cstring
    IMMUTABLE STRICT PARALLEL SAFE LANGUAGE c AS 'MODULE_PATHNAME', 'ng_postcode_out_wrapper';
CREATE TYPE ng_postcode (INPUT = ng_postcode_in, OUTPUT = ng_postcode_out, LIKE = int8);

CREATE TYPE ng_postcode_prefix;
CREATE FUNCTION ng_postcode_prefix_in(cstring) RETURNS ng_postcode_prefix
    IMMUTABLE STRICT PARALLEL SAFE LANGUAGE c AS 'MODULE_PATHNAME', 'ng_postcode_prefix_in_wrapper';
CREATE FUNCTION ng_postcode_prefix_out(ng_postcode_prefix) RETURNS cstring
    IMMUTABLE STRICT PARALLEL SAFE LANGUAGE c AS 'MODULE_PATHNAME', 'ng_postcode_prefix_out_wrapper';
CREATE TYPE ng_postcode_prefix (
    INPUT = ng_postcode_prefix_in, OUTPUT = ng_postcode_prefix_out, LIKE = int8);
"#,
    name = "types",
    creates = [Type(Code), Type(Prefix)]
);

extension_sql_file!(
    "../sql/operators.sql",
    name = "operators",
    requires = ["types"]
);

/// The version of this extension, so that an installed copy can be told from a newer one.
#[pg_extern(immutable, parallel_safe)]
fn ng_postcode_version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

/// The letters and digits of a hyphenated, spaced or compact code, in upper case, or NULL
/// if it holds anything else.
#[pg_extern(immutable, strict, parallel_safe)]
fn ng_postcode_compact(text: &str) -> Option<String> {
    let allowed = |c: char| c.is_ascii_alphanumeric() || c == ' ' || c == '-';
    text.chars().all(allowed).then(|| {
        let kept = text.chars().filter(char::is_ascii_alphanumeric);
        kept.map(|c| c.to_ascii_uppercase()).collect()
    })
}

/// The code in any style as an `ng_postcode`, or NULL if it is not well formed.
#[pg_extern(immutable, strict, parallel_safe)]
fn ng_postcode_parse(text: &str) -> Option<Code> {
    Postcode::parse(text).ok().map(Code::new)
}

/// The prefix in any style as an `ng_postcode_prefix`, or NULL if it is not well formed.
#[pg_extern(immutable, strict, parallel_safe)]
fn ng_postcode_prefix_parse(text: &str) -> Option<Prefix> {
    ng_postcode::Prefix::parse(text).ok().map(Prefix::new)
}

/// The hyphenated form of a code or a prefix: `EK-01-A03-FK-01`, or `EK-01-A03`.
#[pg_extern(immutable, strict, parallel_safe)]
fn ng_postcode_format(prefix: Prefix) -> String {
    prefix.core().to_string()
}

/// The code cut off after a segment: 'state', 'lga', 'district', 'area' or 'unit'.
/// NULL for any other name.
#[pg_extern(immutable, strict, parallel_safe)]
fn ng_postcode_truncate(code: Code, through: &str) -> Option<Prefix> {
    let (segment, ..) = SEGMENTS.iter().find(|(_, name, _)| *name == through)?;
    let code = Postcode::parse(&code.compact()).expect("a stored code is well formed");
    Some(Prefix::new(code.truncate(*segment)))
}

/// The prefix one segment shorter, or NULL for a state.
#[pg_extern(immutable, strict, parallel_safe)]
fn ng_postcode_parent(prefix: Prefix) -> Option<Prefix> {
    prefix.core().parent().map(Prefix::new)
}

/// Whether a code starts with a prefix. Also written `code <@ prefix`.
#[pg_extern(immutable, strict, parallel_safe)]
fn ng_postcode_within(code: Code, prefix: Prefix) -> bool {
    code.compact().starts_with(&prefix.compact())
}

/// A whole code is the narrowest prefix, so a code can stand wherever a prefix is expected.
#[pg_extern(immutable, strict, parallel_safe)]
fn ng_postcode_as_prefix(code: Code) -> Prefix {
    Prefix(code.0 << 3 | 4)
}

extension_sql!(
    "CREATE CAST (ng_postcode AS ng_postcode_prefix)
         WITH FUNCTION ng_postcode_as_prefix(ng_postcode) AS IMPLICIT;
     CREATE OPERATOR <@ (
         LEFTARG = ng_postcode, RIGHTARG = ng_postcode_prefix, FUNCTION = ng_postcode_within);",
    name = "cast_and_containment",
    requires = [ng_postcode_as_prefix, ng_postcode_within],
);

#[cfg(any(test, feature = "pg_test"))]
#[pg_schema]
mod tests {
    use pgrx::prelude::*;

    fn one<T: FromDatum + IntoDatum>(sql: &str) -> Option<T> {
        Spi::get_one(sql).expect(sql)
    }

    #[pg_test]
    fn a_code_is_eight_bytes_and_prints_compact() {
        assert_eq!(
            one::<i32>("SELECT pg_column_size('ek 01 a03 fk 01'::ng_postcode)"),
            Some(8)
        );
        let text = one::<String>("SELECT 'ek 01 a03 fk 01'::ng_postcode::text");
        assert_eq!(text.as_deref(), Some("EK01A03FK01"));
        assert_eq!(
            one::<bool>("SELECT ng_postcode_parse('100001') IS NULL"),
            Some(true)
        );
    }

    #[pg_test]
    fn codes_and_prefixes_sort_as_their_text_does() {
        let sorted = one::<String>(
            "SELECT string_agg(p::text, ' ' ORDER BY p) FROM unnest(ARRAY[
                'EK01A03FK01', 'EK', 'EK01A03', 'EK01', 'EK01000', 'AB', 'EK01A03FK', 'LA11W06TC10'
             ]::ng_postcode_prefix[]) AS p",
        );
        let expected = "AB EK EK01 EK01000 EK01A03 EK01A03FK EK01A03FK01 LA11W06TC10";
        assert_eq!(sorted.as_deref(), Some(expected));
    }

    #[pg_test]
    fn an_index_serves_equality_and_ranges() {
        Spi::run(
            "CREATE TABLE b (code ng_postcode PRIMARY KEY);
             INSERT INTO b SELECT ng_postcode_parse(chr(65 + i % 26) || chr(65 + (i / 26) % 26)
                 || lpad((1 + i % 99)::text, 2, '0') || 'A03FK' || lpad((1 + (i / 99) % 99)::text, 2, '0'))
             FROM generate_series(0, 20000) i ON CONFLICT DO NOTHING;
             CREATE INDEX ON b (ng_postcode_truncate(code, 'district'));
             ANALYZE b; SET enable_seqscan = off;",
        )
        .unwrap();
        let plan = |sql: &str| {
            Spi::connect(|client| {
                let rows = client
                    .select(&format!("EXPLAIN (COSTS OFF) {sql}"), None, &[])
                    .unwrap();
                rows.map(|row| row.get::<String>(1).unwrap().unwrap())
                    .collect::<Vec<_>>()
                    .join("\n")
            })
        };
        assert!(plan("SELECT * FROM b WHERE code = 'EK01A03FK01'").contains("b_pkey"));
        let grouped = "SELECT * FROM b WHERE ng_postcode_truncate(code, 'district') = 'EK01A03'";
        assert!(plan(grouped).contains("Index"), "{}", plan(grouped));
        let same = one::<bool>(
            "SELECT (SELECT count(*) FROM b WHERE code <@ 'EK01A03') =
                    (SELECT count(*) FROM b WHERE ng_postcode_truncate(code, 'district') = 'EK01A03')",
        );
        assert_eq!(same, Some(true));
    }
}

/// Required by `cargo pgrx test`.
#[cfg(test)]
pub mod pg_test {
    pub fn setup(_options: Vec<&str>) {}

    #[must_use]
    pub fn postgresql_conf_options() -> Vec<&'static str> {
        vec![]
    }
}
