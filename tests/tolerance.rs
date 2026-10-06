//! Runs the shared cases in `spec/tolerance.json`: bodies the live API may one day send.
#![cfg(feature = "api")]

use ng_postcode::api::{self, ApiError, Coordinate};
use serde_json::{json, Value};

const CASES: &str = include_str!("../spec/tolerance.json");
const HERE: Coordinate = Coordinate {
    lat: 7.6211,
    lng: 5.2214,
};

/// The outcome, the error code if rejected, and the facts a case may expect of the answer.
fn outcome<T>(
    decoded: Result<T, ApiError>,
    facts: impl Fn(T) -> Value,
) -> (&'static str, Option<String>, Value) {
    match decoded {
        Ok(value) => ("ok", None, facts(value)),
        Err(ApiError::Rejected { code, .. }) => ("rejected", Some(code), Value::Null),
        Err(ApiError::Malformed { .. }) => ("malformed", None, Value::Null),
        Err(other) => panic!("an error this suite does not know: {other}"),
    }
}

#[test]
fn every_case_reaches_the_shared_outcome() {
    let all: Value = serde_json::from_str(CASES).expect("tolerance.json is valid JSON");
    let code = "FC-03-B06-AG-12".parse().unwrap();
    for case in all["cases"].as_array().expect("cases") {
        let name = case["name"].as_str().expect("name");
        let status = case["status"].as_u64().expect("status") as u16;
        let body = match case["text"].as_str() {
            Some(text) => text.to_owned(),
            None => case["body"].to_string(),
        };
        let found = match case["request"].as_str().expect("request") {
            "lookup" => outcome(api::lookup(code, 1).unwrap().decode(status, &body), |_| {
                json!({})
            }),
            "autocomplete" => outcome(
                api::autocomplete("E").unwrap().decode(status, &body),
                |found| json!({ "count": found.suggestions.len() }),
            ),
            "reverse" => outcome(
                api::reverse(HERE, None).unwrap().decode(status, &body),
                |found| json!({ "unit": found.unit.is_some() }),
            ),
            "nearby" => outcome(
                api::nearby(HERE, None).unwrap().decode(status, &body),
                |units| json!({ "count": units.len() }),
            ),
            other => panic!("{name}: unknown request {other}"),
        };
        let expected = (
            case["outcome"].as_str().expect("outcome"),
            case["code"].as_str().map(str::to_owned),
        );
        assert_eq!((found.0, found.1), expected, "{name}");
        for (fact, value) in case["expect"].as_object().into_iter().flatten() {
            assert_eq!(&found.2[fact], value, "{name}: {fact}");
        }
    }
}
