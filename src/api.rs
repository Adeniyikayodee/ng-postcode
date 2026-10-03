//! The NIPOST Postcode API as plain data: requests to send and responses to
//! decode. Nothing here performs I/O, so it works with any HTTP client.
//!
//! Assembly and disassembly are not modelled because [`Postcode`] does both
//! offline.

use std::fmt;
use std::marker::PhantomData;

use serde::de::DeserializeOwned;
use serde::Deserialize;

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

/// Resolves a postcode. Levels are cumulative from 1 (validity only) to 5,
/// and the API caps the answer at the level granted to the key.
pub fn lookup(code: Postcode, level: u8) -> Request<Lookup> {
    let query = [("code", code.to_string()), ("level", level.to_string())];
    Request::get("/v1/lookup", query)
}

/// Suggests completions for a partial postcode such as `EK 01 A`.
///
/// Do not send an empty `partial`: the live API never answers one.
pub fn autocomplete(partial: &str) -> Request<Autocomplete> {
    Request::get("/v1/search/autocomplete", [("q", partial.to_owned())])
}

/// Finds the postcode of the nearest building, within 25 m unless
/// `max_distance_m` says otherwise. The API clamps it to 250 m.
pub fn reverse(at: Coordinate, max_distance_m: Option<f64>) -> Request<Reverse> {
    let distance = max_distance_m.map(|metres| ("max_distance_m", metres.to_string()));
    Request::get("/v1/search/reverse", at.query().into_iter().chain(distance))
}

/// Lists buildings around a point, nearest first, within 300 m unless
/// `radius_m` says otherwise. Empty when nothing is in range.
pub fn nearby(at: Coordinate, radius_m: Option<f64>) -> Request<Vec<NearbyUnit>> {
    let radius = radius_m.map(|metres| ("radius", metres.to_string()));
    Request::get("/v1/search/nearby", at.query().into_iter().chain(radius))
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
        match serde_json::from_str(body) {
            Ok(Envelope::Data(data)) => Ok(data),
            Ok(Envelope::Error(Failure { code, message })) => Err(ApiError::Rejected {
                status,
                code,
                message,
            }),
            Err(error) => Err(ApiError::Malformed {
                status,
                reason: error.to_string(),
            }),
        }
    }
}

impl Coordinate {
    fn query(self) -> [(&'static str, String); 2] {
        [("lat", self.lat.to_string()), ("lng", self.lng.to_string())]
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "lowercase")]
enum Envelope<T> {
    Data(T),
    Error(Failure),
}

#[derive(Deserialize)]
struct Failure {
    code: String,
    message: String,
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

/// Fields above the level granted to the key are `None`.
#[derive(Clone, Debug, Default, PartialEq, Deserialize)]
#[serde(default)]
pub struct Lookup {
    pub postcode: String,
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
    pub segment: Option<Segment>,
    pub suggestions: Vec<Suggestion>,
}

#[derive(Clone, Debug, Default, PartialEq, Eq, Deserialize)]
#[serde(default)]
pub struct Suggestion {
    /// The value of the segment being completed, such as `A03`, not a full prefix.
    pub code: String,
    /// Documented by NIPOST but not sent by the live API as of October 2026.
    pub label: Option<String>,
}

#[derive(Clone, Debug, Default, PartialEq, Deserialize)]
#[serde(default)]
pub struct Reverse {
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
    pub postcode: String,
    pub display: String,
    pub distance_m: f64,
}

#[derive(Clone, Debug, Default, PartialEq, Deserialize)]
#[serde(default)]
pub struct NearestUnit {
    pub postcode: String,
    pub display: String,
    pub distance_m: f64,
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
        let code = "ek01a03fk01".parse().unwrap();
        let request = lookup(code, 3);
        assert_eq!(request.path, "/v1/lookup");
        assert_eq!(
            request.query,
            pairs([("code", "EK-01-A03-FK-01"), ("level", "3")])
        );

        let request = autocomplete("EK 01 A");
        assert_eq!(request.path, "/v1/search/autocomplete");
        assert_eq!(request.query, pairs([("q", "EK 01 A")]));

        let request = reverse(HERE, Some(100.0));
        assert_eq!(request.path, "/v1/search/reverse");
        assert_eq!(
            request.query,
            pairs([("lat", "7.62"), ("lng", "5.22"), ("max_distance_m", "100")])
        );

        let request = nearby(HERE, None);
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
            .decode(200, body)
            .unwrap();
        assert_eq!(found.administrative_address, None);
    }

    #[test]
    fn decodes_autocomplete_and_reverse() {
        let body = r#"{ "data": { "segment": "lga", "suggestions": [{ "code": "EK-01", "label": "ADO EKITI" }] } }"#;
        let found = autocomplete("EK").decode(200, body).unwrap();
        assert_eq!(found.segment, Some(Segment::Lga));
        assert_eq!(found.suggestions[0].code, "EK-01");

        let body = r#"{ "data": { "found": false, "coordinate": [5.22, 7.62], "message": "no unit in range", "radius_m": 25 } }"#;
        let found = reverse(HERE, None).decode(200, body).unwrap();
        assert_eq!((found.found, found.unit), (false, None));
        assert_eq!(found.radius_m, Some(25.0));
    }

    #[test]
    fn turns_error_envelopes_and_bad_bodies_into_values() {
        let request = lookup("EK-01-A03-FK-01".parse().unwrap(), 1);

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
    }
}
