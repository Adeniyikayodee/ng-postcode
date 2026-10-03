//! The NIPOST Postcode API as plain data: requests to send and responses to
//! decode. Nothing here performs I/O, so it works with any HTTP client.
//!
//! Assembly and disassembly are not modelled because [`Postcode`] does both
//! offline.

use std::fmt;
use std::marker::PhantomData;

use serde::de::DeserializeOwned;
use serde::{Deserialize, Deserializer};

use crate::{Postcode, Segment};

pub const BASE_URL: &str = "https://api.postcode.gov.ng";

/// A GET request whose successful response decodes to `T`.
#[derive(Clone, Debug, PartialEq)]
pub struct Request<T> {
    pub path: &'static str,
    pub query: Vec<(&'static str, String)>,
    response: PhantomData<fn() -> T>,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Coordinate {
    pub lat: f64,
    pub lng: f64,
}

/// Why a request was not built. Nothing is sent.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum InvalidRequest {
    /// The lookup level is outside 1 to 5.
    Level(u8),
    /// The autocomplete text is empty, which the live API never answers.
    EmptyQuery,
    /// The named coordinate or distance is not a finite number.
    NotFinite(&'static str),
}

/// Resolves a postcode. Levels are cumulative from 1 (validity only) to 5,
/// and the API caps the answer at the level granted to the key.
pub fn lookup(code: Postcode, level: u8) -> Result<Request<Lookup>, InvalidRequest> {
    if !(1..=5).contains(&level) {
        return Err(InvalidRequest::Level(level));
    }
    let query = [("code", code.to_string()), ("level", level.to_string())];
    Ok(Request::get("/v1/lookup", query))
}

/// Suggests completions for a partial postcode such as `EK 01 A`.
pub fn autocomplete(partial: &str) -> Result<Request<Autocomplete>, InvalidRequest> {
    if partial.trim().is_empty() {
        return Err(InvalidRequest::EmptyQuery);
    }
    let query = [("q", partial.to_owned())];
    Ok(Request::get("/v1/search/autocomplete", query))
}

/// Finds the postcode of the nearest building, within 25 m unless
/// `max_distance_m` says otherwise. The API clamps it to 250 m.
pub fn reverse(
    at: Coordinate,
    max_distance_m: Option<f64>,
) -> Result<Request<Reverse>, InvalidRequest> {
    let query = around(at, "max_distance_m", max_distance_m)?;
    Ok(Request::get("/v1/search/reverse", query))
}

/// Lists buildings around a point, nearest first, within 300 m unless
/// `radius_m` says otherwise. Empty when nothing is in range.
pub fn nearby(
    at: Coordinate,
    radius_m: Option<f64>,
) -> Result<Request<Vec<NearbyUnit>>, InvalidRequest> {
    let query = around(at, "radius", radius_m)?;
    Ok(Request::get("/v1/search/nearby", query))
}

fn around(
    at: Coordinate,
    key: &'static str,
    metres: Option<f64>,
) -> Result<Vec<(&'static str, String)>, InvalidRequest> {
    [("lat", Some(at.lat)), ("lng", Some(at.lng)), (key, metres)]
        .into_iter()
        .filter_map(|(key, value)| Some((key, value?)))
        .map(|(key, value)| match value.is_finite() {
            true => Ok((key, value.to_string())),
            false => Err(InvalidRequest::NotFinite(key)),
        })
        .collect()
}

impl<T> Request<T> {
    fn get(path: &'static str, query: impl IntoIterator<Item = (&'static str, String)>) -> Self {
        Self {
            path,
            query: query.into_iter().collect(),
            response: PhantomData,
        }
    }
}

impl<T: DeserializeOwned> Request<T> {
    /// Decodes the response to this request from its status and body.
    pub fn decode(&self, status: u16, body: &str) -> Result<T, ApiError> {
        let malformed = |reason| ApiError::Malformed { status, reason };
        match serde_json::from_str(body) {
            Ok(Envelope {
                error: Some(failure),
                ..
            }) => {
                let (code, message) = match failure {
                    Failure::Detail { code, message } => (code, message),
                    Failure::Text(message) => (None, Some(message)),
                };
                Err(ApiError::Rejected {
                    status,
                    code: code.unwrap_or_else(|| "unknown_error".to_owned()),
                    message: message.unwrap_or_default(),
                })
            }
            Ok(_) if !(200..300).contains(&status) => {
                Err(malformed("an error status without an error".to_owned()))
            }
            Ok(Envelope {
                data: Some(data), ..
            }) => Ok(data),
            Ok(_) => Err(malformed("neither data nor error".to_owned())),
            Err(error) => Err(malformed(error.to_string())),
        }
    }
}

/// Keys beside `data` and `error` are ignored, so the API can add to the envelope.
#[derive(Deserialize)]
struct Envelope<T> {
    data: Option<T>,
    error: Option<Failure>,
}

#[derive(Deserialize)]
#[serde(untagged)]
enum Failure {
    Detail {
        code: Option<String>,
        message: Option<String>,
    },
    Text(String),
}

/// Reads `null` like a missing key.
fn or_default<'de, D: Deserializer<'de>, T: Deserialize<'de> + Default>(
    deserializer: D,
) -> Result<T, D::Error> {
    Option::deserialize(deserializer).map(Option::unwrap_or_default)
}

/// A segment name this version does not know is `None`, not a failed response.
fn known_segment<'de, D: Deserializer<'de>>(deserializer: D) -> Result<Option<Segment>, D::Error> {
    let name = Option::<String>::deserialize(deserializer)?;
    Ok(name.and_then(|name| Segment::deserialize(serde_json::Value::String(name)).ok()))
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ApiError {
    /// The API refused the request, for example `auth_required` (401),
    /// `insufficient_credits` (402) or a rate limit (429).
    Rejected {
        status: u16,
        code: String,
        message: String,
    },
    /// The body was not the documented JSON envelope.
    Malformed { status: u16, reason: String },
}

impl fmt::Display for ApiError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Rejected {
                status,
                code,
                message,
            } => write!(f, "{code} ({status}): {message}"),
            Self::Malformed { status, reason } => {
                write!(f, "unreadable response ({status}): {reason}")
            }
        }
    }
}

impl std::error::Error for ApiError {}

impl fmt::Display for InvalidRequest {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Level(level) => write!(f, "level must be 1 to 5, got {level}"),
            Self::EmptyQuery => f.write_str("autocomplete text must not be empty"),
            Self::NotFinite(name) => write!(f, "{name} must be a finite number"),
        }
    }
}

impl std::error::Error for InvalidRequest {}

/// Fields above the level granted to the key are `None`.
#[derive(Clone, Debug, Default, PartialEq, Deserialize)]
pub struct Lookup {
    #[serde(default)]
    pub postcode: String,
    /// Required: a body without it is malformed, not an unassigned code.
    pub valid: bool,
    /// Level 2.
    pub administrative_address: Option<AdministrativeAddress>,
    /// Level 2.
    pub recent_house_address: Option<RecentHouseAddress>,
    /// Level 3.
    pub building_use_status: Option<String>,
    /// Level 4. Undocumented, so left untyped.
    pub other_building_info: Option<serde_json::Value>,
    /// Level 5. Undocumented, so left untyped.
    pub point_geometry: Option<serde_json::Value>,
    /// `valid`, `not_found`, or `invalid` for a malformed code. Sent at every level.
    pub status: Option<String>,
    pub verified: Option<bool>,
}

#[derive(Clone, Debug, Default, PartialEq, Eq, Deserialize)]
#[serde(default)]
pub struct AdministrativeAddress {
    pub state_name: Option<String>,
    pub lga_name: Option<String>,
    pub locality_name: Option<String>,
    pub zone: Option<String>,
}

#[derive(Clone, Debug, Default, PartialEq, Eq, Deserialize)]
#[serde(default)]
pub struct RecentHouseAddress {
    pub recent: Option<String>,
}

#[derive(Clone, Debug, Default, PartialEq, Eq, Deserialize)]
#[serde(default)]
pub struct Autocomplete {
    /// The segment the suggestions complete.
    #[serde(deserialize_with = "known_segment")]
    pub segment: Option<Segment>,
    #[serde(deserialize_with = "or_default")]
    pub suggestions: Vec<Suggestion>,
}

#[derive(Clone, Debug, Default, PartialEq, Eq, Deserialize)]
#[serde(default)]
pub struct Suggestion {
    /// The value of the segment being completed, such as `A03`, not a full prefix.
    #[serde(deserialize_with = "or_default")]
    pub code: String,
    /// Documented by NIPOST but not sent by the live API as of October 2026.
    pub label: Option<String>,
}

#[derive(Clone, Debug, Default, PartialEq, Deserialize)]
pub struct Reverse {
    /// Required: a body without it is malformed, not an empty search.
    pub found: bool,
    /// The queried point, echoed back as `[lng, lat]`.
    pub coordinate: Option<[f64; 2]>,
    /// The nearest building, absent when nothing is in range.
    pub unit: Option<NearestUnit>,
    pub area: Option<String>,
    pub district: Option<String>,
    pub state: Option<String>,
    /// Set when nothing is in range.
    pub message: Option<String>,
    /// The radius the API actually applied.
    pub radius_m: Option<f64>,
    /// How deep the match goes, such as `unit`.
    pub depth: Option<String>,
}

#[derive(Clone, Debug, Default, PartialEq, Deserialize)]
#[serde(default)]
pub struct NearbyUnit {
    #[serde(deserialize_with = "or_default")]
    pub postcode: String,
    #[serde(deserialize_with = "or_default")]
    pub display: String,
    pub distance_m: Option<f64>,
}

#[derive(Clone, Debug, Default, PartialEq, Deserialize)]
#[serde(default)]
pub struct NearestUnit {
    #[serde(deserialize_with = "or_default")]
    pub postcode: String,
    #[serde(deserialize_with = "or_default")]
    pub display: String,
    pub distance_m: Option<f64>,
    /// `high`, `medium` or `low`, graded by distance.
    pub confidence: Option<String>,
    /// Level 2.
    pub state_name: Option<String>,
    /// Level 2.
    pub lga_name: Option<String>,
    /// Level 2.
    pub locality_name: Option<String>,
    /// Level 2.
    pub address: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;

    const HERE: Coordinate = Coordinate {
        lat: 7.62,
        lng: 5.22,
    };

    fn pairs<const N: usize>(query: [(&'static str, &str); N]) -> Vec<(&'static str, String)> {
        query.map(|(key, value)| (key, value.to_owned())).to_vec()
    }

    #[test]
    fn builds_requests() {
        let code: Postcode = "ek01a03fk01".parse().unwrap();
        let request = lookup(code, 3).unwrap();
        assert_eq!(request.path, "/v1/lookup");
        assert_eq!(
            request.query,
            pairs([("code", "EK-01-A03-FK-01"), ("level", "3")])
        );

        assert_eq!(lookup(code, 0), Err(InvalidRequest::Level(0)));
        assert_eq!(autocomplete(" "), Err(InvalidRequest::EmptyQuery));
        let nowhere = Coordinate {
            lat: f64::NAN,
            ..HERE
        };
        assert_eq!(nearby(nowhere, None), Err(InvalidRequest::NotFinite("lat")));

        let request = autocomplete("EK 01 A").unwrap();
        assert_eq!(request.path, "/v1/search/autocomplete");
        assert_eq!(request.query, pairs([("q", "EK 01 A")]));

        let request = reverse(HERE, Some(100.0)).unwrap();
        assert_eq!(request.path, "/v1/search/reverse");
        assert_eq!(
            request.query,
            pairs([("lat", "7.62"), ("lng", "5.22"), ("max_distance_m", "100")])
        );

        let request = nearby(HERE, None).unwrap();
        assert_eq!(request.path, "/v1/search/nearby");
        assert_eq!(request.query, pairs([("lat", "7.62"), ("lng", "5.22")]));
    }

    #[test]
    fn decodes_the_documented_lookup() {
        let body = r#"{ "data": {
            "postcode": "EK-01-A03-FK-01",
            "valid": true,
            "administrative_address": { "state_name": "EKITI", "lga_name": "ADO EKITI", "locality_name": "ADO EKITI", "zone": "SOUTH WEST" },
            "recent_house_address": { "recent": "NTA ROAD, BACK OF FABIAN HOTEL, ADO EKITI" },
            "building_use_status": "residential"
        } }"#;
        let found = lookup("EK-01-A03-FK-01".parse().unwrap(), 3)
            .unwrap()
            .decode(200, body)
            .unwrap();
        assert!(found.valid);
        assert_eq!(
            found.administrative_address.unwrap().zone.as_deref(),
            Some("SOUTH WEST")
        );
        assert_eq!(found.building_use_status.as_deref(), Some("residential"));
        assert_eq!(found.point_geometry, None);
    }

    #[test]
    fn decodes_fields_missing_below_the_granted_level() {
        let body = r#"{ "data": { "postcode": "EK-01-A03-FK-01", "valid": true } }"#;
        let found = lookup("EK-01-A03-FK-01".parse().unwrap(), 1)
            .unwrap()
            .decode(200, body)
            .unwrap();
        assert_eq!(found.administrative_address, None);
    }

    #[test]
    fn decodes_autocomplete_and_reverse() {
        let body = r#"{ "data": { "segment": "lga", "suggestions": [{ "code": "EK-01", "label": "ADO EKITI" }] } }"#;
        let found = autocomplete("EK").unwrap().decode(200, body).unwrap();
        assert_eq!(found.segment, Some(Segment::Lga));
        assert_eq!(found.suggestions[0].code, "EK-01");

        let body = r#"{ "data": { "found": false, "coordinate": [5.22, 7.62], "message": "no unit in range", "radius_m": 25 } }"#;
        let found = reverse(HERE, None).unwrap().decode(200, body).unwrap();
        assert_eq!((found.found, found.unit), (false, None));
        assert_eq!(found.radius_m, Some(25.0));
    }

    #[test]
    fn turns_error_envelopes_and_bad_bodies_into_values() {
        let request = lookup("EK-01-A03-FK-01".parse().unwrap(), 1).unwrap();

        // What the live API answered on 2 October 2026 when called without a key.
        let body = r#"{"error":{"code":"auth_required","message":"an API key is required; pass it in the X-API-Key header"}}"#;
        let expected = ApiError::Rejected {
            status: 401,
            code: "auth_required".to_owned(),
            message: "an API key is required; pass it in the X-API-Key header".to_owned(),
        };
        assert_eq!(request.decode(401, body), Err(expected));

        let malformed = request.decode(502, "<html>Bad Gateway</html>");
        assert!(matches!(
            malformed,
            Err(ApiError::Malformed { status: 502, .. })
        ));
        let empty = request.decode(200, r#"{"data":null}"#);
        assert!(matches!(empty, Err(ApiError::Malformed { .. })));
    }

    #[test]
    fn tolerates_what_the_api_may_add_or_leave_out() {
        let request = lookup("EK-01-A03-FK-01".parse().unwrap(), 1).unwrap();
        let body =
            r#"{"data":{"postcode":"EK-01-A03-FK-01","valid":true},"meta":{"request_id":"r1"}}"#;
        assert!(request.decode(200, body).unwrap().valid);

        let body = r#"{"error":{"code":"rate_limited"},"request_id":"r1"}"#;
        let expected = ApiError::Rejected {
            status: 429,
            code: "rate_limited".to_owned(),
            message: String::new(),
        };
        assert_eq!(request.decode(429, body), Err(expected));

        let body = r#"{"data":{"segment":"street","suggestions":null}}"#;
        let found = autocomplete("EK").unwrap().decode(200, body).unwrap();
        assert_eq!((found.segment, found.suggestions.len()), (None, 0));

        let body = r#"{"data":[{"postcode":null,"distance_m":3}]}"#;
        let units = nearby(HERE, None).unwrap().decode(200, body).unwrap();
        assert_eq!(
            (units[0].postcode.as_str(), units[0].distance_m),
            ("", Some(3.0))
        );

        let body = r#"{"data":{"found":true,"unit":{"postcode":"EK-01-A03-FK-01"}}}"#;
        let found = reverse(HERE, None).unwrap().decode(200, body).unwrap();
        assert_eq!(found.unit.unwrap().distance_m, None);
    }
}
