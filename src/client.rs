//! A blocking HTTP client: the only part of the crate that performs I/O.

use std::fmt;
use std::time::Duration;

use crate::api::{ApiError, Request, BASE_URL};

const TIMEOUT: Duration = Duration::from_secs(10);

/// Bytes of a response read before it is refused. Real answers are a few thousand.
const MAX_BODY_BYTES: u64 = 1_000_000;

pub struct Client {
    agent: ureq::Agent,
    base_url: String,
    api_key: String,
}

#[derive(Debug)]
#[non_exhaustive]
pub enum Error {
    Transport(TransportError),
    Api(ApiError),
}

/// The request never produced a response: DNS, TLS, timeout and the like.
///
/// Opaque, so the HTTP library behind it can change without breaking callers.
#[derive(Debug)]
pub struct TransportError(Cause);

#[derive(Debug)]
enum Cause {
    Http(ureq::Error),
    UnusableKey,
}

impl Client {
    /// Whitespace around the key, as read from a file, is dropped. A key no header can hold
    /// makes every `send` fail without a request.
    pub fn new(api_key: impl Into<String>) -> Self {
        Self {
            agent: agent(TIMEOUT),
            base_url: BASE_URL.to_owned(),
            api_key: api_key.into().trim().to_owned(),
        }
    }

    /// Allows `timeout` for a whole exchange, body included, instead of 10 seconds.
    /// Anything over a day is read as a day.
    pub fn with_timeout(self, timeout: Duration) -> Self {
        Self {
            // A deadline is the clock plus the timeout, which overflows for `Duration::MAX`.
            agent: agent(timeout.min(Duration::from_secs(86_400))),
            ..self
        }
    }

    /// Points the client at another host, such as a staging stack or a mock.
    pub fn with_base_url(self, base_url: impl Into<String>) -> Self {
        Self {
            base_url: base_url.into().trim_end_matches('/').to_owned(),
            ..self
        }
    }

    pub fn send<T>(&self, request: &Request<T>) -> Result<T, Error> {
        // A key no header can hold is refused before anything is sent.
        if !self.api_key.bytes().all(|byte| byte.is_ascii_graphic()) || self.api_key.is_empty() {
            return Err(Error::Transport(TransportError(Cause::UnusableKey)));
        }
        let call = self
            .agent
            .get(format!("{}{}", self.base_url, request.path))
            .header("X-API-Key", &self.api_key);
        let mut response = request
            .query
            .iter()
            .fold(call, |call, (key, value)| call.query(key, value))
            .call()
            .map_err(failed)?;
        let body = response
            .body_mut()
            .with_config()
            .limit(MAX_BODY_BYTES)
            .read_to_vec()
            .map_err(failed)?;
        // Lossy, so a proxy's page in another encoding keeps its status and is malformed.
        let body = String::from_utf8_lossy(&body);
        Ok(request.decode(response.status().as_u16(), &body)?)
    }
}

fn agent(timeout: Duration) -> ureq::Agent {
    ureq::Agent::config_builder()
        // Error statuses carry a JSON body that `Request::decode` reads.
        .http_status_as_error(false)
        // A redirect would carry the key to another host, so none is followed.
        .max_redirects(0)
        .timeout_global(Some(timeout))
        .build()
        .into()
}

fn failed(error: ureq::Error) -> Error {
    Error::Transport(TransportError(Cause::Http(error)))
}

impl fmt::Display for TransportError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match &self.0 {
            Cause::Http(error) => error.fmt(f),
            Cause::UnusableKey => f.write_str("unusable API key"),
        }
    }
}

// Each `Display` here prints the error it wraps, so `source` skips to that error's own
// cause: a reporter that walks the chain would otherwise print one message three times.
impl std::error::Error for TransportError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match &self.0 {
            Cause::Http(error) => error.source(),
            Cause::UnusableKey => None,
        }
    }
}

impl From<ApiError> for Error {
    fn from(error: ApiError) -> Self {
        Self::Api(error)
    }
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Transport(error) => error.fmt(f),
            Self::Api(error) => error.fmt(f),
        }
    }
}

impl std::error::Error for Error {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Transport(error) => error.source(),
            Self::Api(error) => error.source(),
        }
    }
}
