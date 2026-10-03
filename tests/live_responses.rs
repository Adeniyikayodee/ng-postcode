//! Decodes the response bodies captured from the live API in `spec/responses.json`.
#![cfg(feature = "api")]

use ng_postcode::api::{self, ApiError, Coordinate, Request};
use ng_postcode::{Postcode, Segment};
use serde::de::DeserializeOwned;
use serde_json::Value;

const RESPONSES: &str = include_str!("../spec/responses.json");
const HERE: Coordinate = Coordinate {
    lat: 7.6211,
    lng: 5.2214,
};

fn live<T: DeserializeOwned>(request: Request<T>, name: &str) -> Result<T, ApiError> {
    let all: Value = serde_json::from_str(RESPONSES).expect("responses.json is valid JSON");
    let status = all[name]["status"].as_u64().expect("status") as u16;
    request.decode(status, &all[name]["body"].to_string())
}

fn code() -> Postcode {
    "FC-03-B06-AG-12".parse().unwrap()
}

#[test]
fn lookup_statuses() {
    let valid = live(api::lookup(code(), 1).unwrap(), "lookup_valid").unwrap();
    assert!(valid.valid);
    assert_eq!(valid.status.as_deref(), Some("valid"));
    assert_eq!(valid.verified, Some(false));
    assert_eq!(valid.administrative_address, None);

    let missing = live(api::lookup(code(), 1).unwrap(), "lookup_not_found").unwrap();
    assert_eq!(
        (missing.valid, missing.status.as_deref()),
        (false, Some("not_found"))
    );

    let malformed = live(api::lookup(code(), 1).unwrap(), "lookup_invalid").unwrap();
    assert_eq!(
        (malformed.valid, malformed.status.as_deref()),
        (false, Some("invalid"))
    );
}

#[test]
fn autocomplete_sends_segment_values_without_labels() {
    let states = live(api::autocomplete("E").unwrap(), "autocomplete_state").unwrap();
    assert_eq!(states.segment, Some(Segment::State));
    let codes: Vec<&str> = states.suggestions.iter().map(|s| s.code.as_str()).collect();
    assert_eq!(codes, ["EB", "ED", "EK", "EN"]);
    assert!(states.suggestions.iter().all(|s| s.label.is_none()));

    let units = live(
        api::autocomplete("EK 01 A29 KR 3").unwrap(),
        "autocomplete_unit_empty",
    )
    .unwrap();
    assert_eq!(
        (units.segment, units.suggestions.len()),
        (Some(Segment::Unit), 0)
    );
}

#[test]
fn reverse() {
    let found = live(api::reverse(HERE, None).unwrap(), "reverse_found").unwrap();
    let unit = found.unit.expect("a unit");
    assert_eq!(unit.postcode, "EK-01-A29-KR-36");
    assert_eq!(unit.distance_m, Some(15.7));
    assert_eq!(unit.confidence.as_deref(), Some("high"));
    assert_eq!(unit.address, None);
    assert_eq!(found.area.as_deref(), Some("EK-01-A29-KR"));
    assert_eq!(found.depth.as_deref(), Some("unit"));
    assert_eq!(found.coordinate, Some([5.2214, 7.6211]));
    assert_eq!(found.radius_m, Some(25.0));

    let nothing = live(
        api::reverse(HERE, Some(250.0)).unwrap(),
        "reverse_not_found",
    )
    .unwrap();
    assert_eq!((nothing.found, nothing.unit), (false, None));
    assert_eq!(
        nothing.message.as_deref(),
        Some("no postcode within range of this location")
    );
}

#[test]
fn nearby_is_a_list_nearest_first() {
    let units = live(api::nearby(HERE, None).unwrap(), "nearby_found").unwrap();
    assert_eq!(units[0].postcode, "EK-01-A29-KR-36");
    let distances: Vec<f64> = units.iter().filter_map(|u| u.distance_m).collect();
    assert_eq!(distances, [15.7, 18.3, 31.0]);
    assert!(live(api::nearby(HERE, None).unwrap(), "nearby_empty")
        .unwrap()
        .is_empty());
}

#[test]
fn errors() {
    for (name, status, code_) in [
        ("lookup_level_not_granted", 403, "level_not_granted"),
        ("reverse_bad_request", 400, "bad_request"),
        ("invalid_api_key", 401, "invalid_api_key"),
    ] {
        match live(api::lookup(code(), 1).unwrap(), name) {
            Err(ApiError::Rejected {
                status: s, code, ..
            }) => {
                assert_eq!((s, code.as_str()), (status, code_), "{name}")
            }
            other => panic!("{name}: expected a rejection, got {other:?}"),
        }
    }
}
