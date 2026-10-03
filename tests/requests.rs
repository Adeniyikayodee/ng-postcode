//! Runs the shared cases in `spec/requests.json`: what each request sends, or that it is refused.
#![cfg(feature = "api")]

use ng_postcode::api::{self, Coordinate, Request};
use serde_json::{json, Value};

const CASES: &str = include_str!("../spec/requests.json");

fn number(value: &Value) -> Option<f64> {
    match value {
        Value::String(text) => text.parse().ok(),
        other => other.as_f64(),
    }
}

fn sent<T, E>(request: Result<Request<T>, E>) -> Value {
    request.map_or(Value::Null, |r| json!({"path": r.path, "query": r.query}))
}

#[test]
fn every_case_builds_the_shared_request() {
    let all: Value = serde_json::from_str(CASES).expect("requests.json is valid JSON");
    for case in all["cases"].as_array().expect("cases") {
        let (name, args) = (case["name"].as_str().expect("name"), &case["args"]);
        let at = || Coordinate {
            lat: number(&args["lat"]).expect("lat"),
            lng: number(&args["lng"]).expect("lng"),
        };
        let metres = number(&args["metres"]);
        let found = match case["request"].as_str().expect("request") {
            "lookup" => {
                let code = args["code"].as_str().expect("code").parse().expect("code");
                sent(api::lookup(
                    code,
                    args["level"].as_u64().expect("level") as u8,
                ))
            }
            "autocomplete" => sent(api::autocomplete(args["q"].as_str().expect("q"))),
            "reverse" => sent(api::reverse(at(), metres)),
            "nearby" => sent(api::nearby(at(), metres)),
            other => panic!("{name}: unknown request {other}"),
        };
        assert_eq!(found, case["sends"], "{name}");
    }
}
