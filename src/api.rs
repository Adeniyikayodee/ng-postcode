//! The NIPOST Postcode API as plain data: requests to send and responses to
//! decode. Nothing here performs I/O, so it works with any HTTP client.
//!
//! Assembly and disassembly are not modelled because [`Postcode`] does both
//! offline.

use std::fmt;

use serde_json::{Map, Value};

use crate::{Postcode, Segment};

pub const BASE_URL: &str = "https://api.postcode.gov.ng";

/// A GET request whose successful response decodes to `T`.
#[derive(Clone, Debug)]
pub struct Request<T> {
    pub path: &'static str,
    pub query: Vec<(&'static str, String)>,
    read: fn(&Value) -> Option<T>,
}

/// Two requests are equal when they send the same thing.
impl<T> PartialEq for Request<T> {
    fn eq(&self, other: &Self) -> bool {
        self.path == other.path && self.query == other.query
    }
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Coordinate {
    pub lat: f64,
    pub lng: f64,
}

/// Why a request was not built. Nothing is sent.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
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
    Ok(Request::get("/v1/lookup", query, read_lookup))
}

/// Suggests completions for a partial postcode such as `EK 01 A`.
pub fn autocomplete(partial: &str) -> Result<Request<Autocomplete>, InvalidRequest> {
    if partial.trim().is_empty() {
        return Err(InvalidRequest::EmptyQuery);
    }
    let query = [("q", partial.to_owned())];
    Ok(Request::get(
        "/v1/search/autocomplete",
        query,
        read_autocomplete,
    ))
}

/// Finds the postcode of the nearest building, within 25 m unless
/// `max_distance_m` says otherwise. The API clamps it to 250 m.
pub fn reverse(
    at: Coordinate,
    max_distance_m: Option<f64>,
) -> Result<Request<Reverse>, InvalidRequest> {
    let query = around(at, "max_distance_m", max_distance_m)?;
    Ok(Request::get("/v1/search/reverse", query, read_reverse))
}

/// Lists buildings around a point, nearest first, within 300 m unless
/// `radius_m` says otherwise. Empty when nothing is in range.
pub fn nearby(
    at: Coordinate,
    radius_m: Option<f64>,
) -> Result<Request<Vec<NearbyUnit>>, InvalidRequest> {
    let query = around(at, "radius", radius_m)?;
    Ok(Request::get("/v1/search/nearby", query, read_nearby))
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
            // Adding zero writes -0.0 as "0", as the other implementations do.
            true => Ok((key, (value + 0.0).to_string())),
            false => Err(InvalidRequest::NotFinite(key)),
        })
        .collect()
}

impl<T> Request<T> {
    fn get(
        path: &'static str,
        query: impl IntoIterator<Item = (&'static str, String)>,
        read: fn(&Value) -> Option<T>,
    ) -> Self {
        Self {
            path,
            query: query.into_iter().collect(),
            read,
        }
    }

    /// Decodes the response to this request from its status and body.
    pub fn decode(&self, status: u16, body: &str) -> Result<T, ApiError> {
        let malformed = |reason: &str| ApiError::Malformed {
            status,
            reason: reason.to_owned(),
        };
        let rejected = |code: Option<String>, message: Option<String>| ApiError::Rejected {
            status,
            code: code.unwrap_or_else(|| "unknown_error".to_owned()),
            message: message.unwrap_or_default(),
        };
        // Read as a tree and checked by hand: `data` this version cannot read must not
        // hide the `error` beside it, and keys beside the two are ignored.
        let envelope: Value =
            serde_json::from_str(body).map_err(|error| malformed(&error.to_string()))?;
        let envelope = envelope
            .as_object()
            .ok_or_else(|| malformed("expected a JSON object"))?;
        match envelope.get("error") {
            Some(Value::Object(failure)) => {
                return Err(rejected(text(failure, "code"), text(failure, "message")))
            }
            Some(Value::String(message)) => return Err(rejected(None, Some(message.clone()))),
            _ => {}
        }
        if !(200..300).contains(&status) {
            return Err(malformed("an error status without an error"));
        }
        (self.read)(envelope.get("data").unwrap_or(&Value::Null))
            .ok_or_else(|| malformed("unexpected data"))
    }
}

// The readers below are strict about one thing each: the field that carries the
// answer. Any other field of the wrong type is read as absent, so a change NIPOST
// makes to one field cannot fail the whole response.

type Object = Map<String, Value>;

fn text(data: &Object, key: &str) -> Option<String> {
    data.get(key)?.as_str().map(str::to_owned)
}

fn number(data: &Object, key: &str) -> Option<f64> {
    data.get(key)?.as_f64()
}

fn object<'a>(data: &'a Object, key: &str) -> Option<&'a Object> {
    data.get(key)?.as_object()
}

/// A unit or suggestion without its code is no answer, so it is dropped.
fn coded(key: &'static str) -> impl Fn(&&Object) -> bool {
    move |item| text(item, key).is_some_and(|code| !code.is_empty())
}

fn raw(data: &Object, key: &str) -> Option<Value> {
    data.get(key).filter(|value| !value.is_null()).cloned()
}

fn read_lookup(data: &Value) -> Option<Lookup> {
    let data = data.as_object()?;
    Some(Lookup {
        postcode: text(data, "postcode").unwrap_or_default(),
        // A body without it is malformed, not an unassigned code.
        valid: data.get("valid")?.as_bool()?,
        administrative_address: object(data, "administrative_address").map(|admin| {
            AdministrativeAddress {
                state_name: text(admin, "state_name"),
                lga_name: text(admin, "lga_name"),
                locality_name: text(admin, "locality_name"),
                zone: text(admin, "zone"),
            }
        }),
        recent_house_address: object(data, "recent_house_address").map(|recent| {
            RecentHouseAddress {
                recent: text(recent, "recent"),
            }
        }),
        building_use_status: text(data, "building_use_status"),
        other_building_info: raw(data, "other_building_info"),
        point_geometry: raw(data, "point_geometry"),
        status: text(data, "status"),
        verified: data.get("verified").and_then(Value::as_bool),
    })
}

fn read_autocomplete(data: &Value) -> Option<Autocomplete> {
    let data = data.as_object()?;
    let suggestions = data.get("suggestions").and_then(Value::as_array);
    Some(Autocomplete {
        // A segment name this version does not know is `None`, not a failed response.
        segment: match data.get("segment").and_then(Value::as_str) {
            Some("state") => Some(Segment::State),
            Some("lga") => Some(Segment::Lga),
            Some("district") => Some(Segment::District),
            Some("area") => Some(Segment::Area),
            Some("unit") => Some(Segment::Unit),
            _ => None,
        },
        suggestions: suggestions
            .into_iter()
            .flatten()
            .filter_map(Value::as_object)
            .filter(coded("code"))
            .map(|item| Suggestion {
                code: text(item, "code").unwrap_or_default(),
                label: text(item, "label"),
            })
            .collect(),
    })
}

fn read_reverse(data: &Value) -> Option<Reverse> {
    let data = data.as_object()?;
    let point = data.get("coordinate").and_then(Value::as_array);
    Some(Reverse {
        // A body without it is malformed, not an empty search.
        found: data.get("found")?.as_bool()?,
        coordinate: point.and_then(|point| match point.as_slice() {
            [lng, lat] => Some(Coordinate {
                lat: lat.as_f64()?,
                lng: lng.as_f64()?,
            }),
            _ => None,
        }),
        unit: object(data, "unit")
            .filter(coded("postcode"))
            .map(|unit| NearestUnit {
                postcode: text(unit, "postcode").unwrap_or_default(),
                display: text(unit, "display").unwrap_or_default(),
                distance_m: number(unit, "distance_m"),
                confidence: text(unit, "confidence"),
                state_name: text(unit, "state_name"),
                lga_name: text(unit, "lga_name"),
                locality_name: text(unit, "locality_name"),
                address: text(unit, "address"),
            }),
        area: text(data, "area"),
        district: text(data, "district"),
        state: text(data, "state"),
        message: text(data, "message"),
        radius_m: number(data, "radius_m"),
        depth: text(data, "depth"),
    })
}

fn read_nearby(data: &Value) -> Option<Vec<NearbyUnit>> {
    let units = data.as_array()?.iter().filter_map(Value::as_object);
    Some(
        units
            .filter(coded("postcode"))
            .map(|unit| NearbyUnit {
                postcode: text(unit, "postcode").unwrap_or_default(),
                display: text(unit, "display").unwrap_or_default(),
                distance_m: number(unit, "distance_m"),
            })
            .collect(),
    )
}

#[derive(Clone, Debug, PartialEq, Eq)]
#[non_exhaustive]
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
#[derive(Clone, Debug, Default, PartialEq)]
#[non_exhaustive]
pub struct Lookup {
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

#[derive(Clone, Debug, Default, PartialEq, Eq)]
#[non_exhaustive]
pub struct AdministrativeAddress {
    pub state_name: Option<String>,
    pub lga_name: Option<String>,
    pub locality_name: Option<String>,
    pub zone: Option<String>,
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
#[non_exhaustive]
pub struct RecentHouseAddress {
    pub recent: Option<String>,
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
#[non_exhaustive]
pub struct Autocomplete {
    /// The segment the suggestions complete.
    pub segment: Option<Segment>,
    pub suggestions: Vec<Suggestion>,
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
#[non_exhaustive]
pub struct Suggestion {
    /// The value of the segment being completed, such as `A03`, not a full prefix.
    pub code: String,
    /// Documented by NIPOST but not sent by the live API as of October 2026.
    pub label: Option<String>,
}

#[derive(Clone, Debug, Default, PartialEq)]
#[non_exhaustive]
pub struct Reverse {
    /// Required: a body without it is malformed, not an empty search.
    pub found: bool,
    /// The queried point, echoed back.
    pub coordinate: Option<Coordinate>,
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

#[derive(Clone, Debug, Default, PartialEq)]
#[non_exhaustive]
pub struct NearbyUnit {
    pub postcode: String,
    pub display: String,
    pub distance_m: Option<f64>,
}

#[derive(Clone, Debug, Default, PartialEq)]
#[non_exhaustive]
pub struct NearestUnit {
    pub postcode: String,
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
        assert_eq!(units, []);

        let body = r#"{"data":{"found":true,"unit":{"postcode":"EK-01-A03-FK-01"}}}"#;
        let found = reverse(HERE, None).unwrap().decode(200, body).unwrap();
        assert_eq!(found.unit.unwrap().distance_m, None);
    }
}
