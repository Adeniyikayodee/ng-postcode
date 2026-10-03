//! Nigeria's National Digital Alphanumeric Postcode (NDAPS), the
//! building-level postcode issued by NIPOST.
//!
//! Unofficial: not made or endorsed by NIPOST.
//!
//! The crate has a pure core and an optional shell:
//!
//! - [`Postcode`] parses, validates and formats codes offline.
//! - [`api`] (feature `api`) describes the NIPOST API as plain data: requests
//!   to send and responses to decode, with no I/O.
//! - [`client`] (feature `client`) is a small blocking HTTP client over `api`.
//!
//! ```
//! use ng_postcode::{Postcode, Segment};
//!
//! let code: Postcode = "ek 01 a03 fk 01".parse()?;
//! assert_eq!(code.to_string(), "EK-01-A03-FK-01");
//! assert_eq!(code.as_str(), "EK01A03FK01");
//! assert_eq!(code.state(), "EK");
//! assert_eq!(code.prefix(Segment::Area), "EK-01-A03-FK");
//! # Ok::<(), ng_postcode::ParseError>(())
//! ```

mod postcode;

#[cfg(feature = "api")]
pub mod api;
#[cfg(feature = "client")]
pub mod client;

pub use postcode::{is_valid, Corrected, ParseError, Postcode, Segment};
