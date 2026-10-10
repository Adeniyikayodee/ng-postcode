//! Polars expressions over the `ng-postcode` core: one pass over a string column, no Python
//! per row. A value that is not well formed becomes null.

use ng_postcode::{Postcode, Prefix, Segment};
use polars::prelude::*;
use pyo3_polars::derive::polars_expr;
use pyo3_polars::PolarsAllocator;
use serde::Deserialize;

#[global_allocator]
static ALLOC: PolarsAllocator = PolarsAllocator::new();

fn map(inputs: &[Series], each: impl Fn(&str) -> Option<String>) -> PolarsResult<Series> {
    let column = inputs[0].str()?;
    let out: StringChunked = column.iter().map(|text| text.and_then(&each)).collect();
    Ok(out.with_name(column.name().clone()).into_series())
}

/// The compact code, `EK01A03FK01`.
#[polars_expr(output_type=String)]
fn parse(inputs: &[Series]) -> PolarsResult<Series> {
    map(inputs, |text| {
        Some(Postcode::parse(text).ok()?.as_str().to_owned())
    })
}

/// The compact prefix, such as `EK01A03`.
#[polars_expr(output_type=String)]
fn parse_prefix(inputs: &[Series]) -> PolarsResult<Series> {
    map(inputs, |text| {
        Some(Prefix::parse(text).ok()?.as_str().to_owned())
    })
}

/// The hyphenated form of a code or a prefix.
#[polars_expr(output_type=String)]
fn format(inputs: &[Series]) -> PolarsResult<Series> {
    map(inputs, |text| Some(Prefix::parse(text).ok()?.to_string()))
}

#[derive(Deserialize)]
struct Through {
    through: String,
}

/// The compact prefix of a code, cut off after a segment.
#[polars_expr(output_type=String)]
fn truncate(inputs: &[Series], kwargs: Through) -> PolarsResult<Series> {
    let through = match kwargs.through.as_str() {
        "state" => Segment::State,
        "lga" => Segment::Lga,
        "district" => Segment::District,
        "area" => Segment::Area,
        "unit" => Segment::Unit,
        other => polars_bail!(InvalidOperation: "unknown segment: {other}"),
    };
    map(inputs, |text| {
        Some(
            Postcode::parse(text)
                .ok()?
                .truncate(through)
                .as_str()
                .to_owned(),
        )
    })
}

/// Whether the value is a well-formed code. Null stays null.
#[polars_expr(output_type=Boolean)]
fn is_valid(inputs: &[Series]) -> PolarsResult<Series> {
    let column = inputs[0].str()?;
    let out: BooleanChunked = column
        .iter()
        .map(|text| text.map(ng_postcode::is_valid))
        .collect();
    Ok(out.with_name(column.name().clone()).into_series())
}
