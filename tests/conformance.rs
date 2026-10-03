//! Runs the shared cases in `spec/vectors.json`, which every implementation must pass.

use ng_postcode::{ParseError, Postcode, Segment};
use serde_json::{json, Value};

const VECTORS: &str = include_str!("../spec/vectors.json");

fn vectors() -> Value {
    serde_json::from_str(VECTORS).expect("vectors.json is valid JSON")
}

fn cases<'a>(value: &'a Value, path: &str) -> &'a [Value] {
    value
        .pointer(path)
        .and_then(Value::as_array)
        .unwrap_or_else(|| panic!("missing {path}"))
}

fn text<'a>(case: &'a Value, key: &str) -> &'a str {
    case[key]
        .as_str()
        .unwrap_or_else(|| panic!("{key} in {case}"))
}

fn segment(name: &str) -> Segment {
    match name {
        "state" => Segment::State,
        "lga" => Segment::Lga,
        "district" => Segment::District,
        "area" => Segment::Area,
        "unit" => Segment::Unit,
        other => panic!("unknown segment {other}"),
    }
}

fn error_json(error: &ParseError) -> Value {
    match error {
        ParseError::Length { found } => json!({ "kind": "length", "found": found }),
        ParseError::InvalidCharacter { ch, index } => {
            json!({ "kind": "invalid_character", "char": ch.to_string(), "index": index })
        }
        ParseError::Segment(segment) => {
            json!({ "kind": "segment", "segment": format!("{segment:?}").to_lowercase() })
        }
    }
}

#[test]
fn parse() {
    let all = vectors();
    for case in cases(&all, "/parse/valid") {
        let code = Postcode::parse(text(case, "input")).unwrap();
        assert_eq!(code.to_string(), text(case, "canonical"), "{case}");
        assert_eq!(code.as_str(), text(case, "compact"), "{case}");
        assert_eq!(code.to_spaced(), text(case, "spaced"), "{case}");
    }
    for case in cases(&all, "/parse/invalid") {
        let error = Postcode::parse(text(case, "input")).unwrap_err();
        assert_eq!(error_json(&error), case["error"], "{case}");
    }
}

#[test]
fn parse_lenient() {
    for case in cases(&vectors(), "/parse_lenient") {
        match Postcode::parse_lenient(text(case, "input")) {
            Ok(fixed) => {
                assert_eq!(
                    fixed.postcode.to_string(),
                    text(case, "canonical"),
                    "{case}"
                );
                assert_eq!(json!(fixed.corrections), case["corrections"], "{case}");
            }
            Err(error) => assert_eq!(error_json(&error), case["error"], "{case}"),
        }
    }
}

#[test]
fn from_segments() {
    for case in cases(&vectors(), "/from_segments") {
        let parts: Vec<&str> = case["segments"]
            .as_array()
            .unwrap()
            .iter()
            .map(|part| part.as_str().unwrap())
            .collect();
        let [state, lga, district, area, unit] = parts[..] else {
            panic!("five segments in {case}")
        };
        match Postcode::from_segments(state, lga, district, area, unit) {
            Ok(code) => assert_eq!(code.to_string(), text(case, "canonical"), "{case}"),
            Err(error) => assert_eq!(error_json(&error), case["error"], "{case}"),
        }
    }
}

#[test]
fn prefix() {
    for case in cases(&vectors(), "/prefix") {
        let code = Postcode::parse(text(case, "input")).unwrap();
        let through = segment(text(case, "through"));
        assert_eq!(code.prefix(through), text(case, "prefix"), "{case}");
    }
}
