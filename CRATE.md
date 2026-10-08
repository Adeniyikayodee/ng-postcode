# ng-postcode

[![crates.io](https://img.shields.io/crates/v/ng-postcode.svg)](https://crates.io/crates/ng-postcode)
[![docs.rs](https://docs.rs/ng-postcode/badge.svg)](https://docs.rs/ng-postcode)

Rust library for Nigeria's National Digital Alphanumeric Postcode System (NDAPS), the building-level postcode NIPOST launched in October 2026. Parse, validate and format postcodes offline, and call the [postcode.gov.ng](https://docs.postcode.gov.ng) API for lookup, autocomplete and reverse geocoding.

Part of the [ng-postcode project](https://github.com/Adeniyikayodee/ng-postcode), which has the same behaviour in Python, JavaScript and Java, MCP servers for AI assistants, and an address resolver.

## Format

An 11-character code in five segments: state, LGA, district, area, building unit.

| Form | Example | Use it to |
| --- | --- | --- |
| Canonical | `EK-01-A03-FK-01` | Write a code and pass it between systems |
| Spaced | `EK 01 A03 FK 01` | Show a code to people |
| Compact | `EK01A03FK01` | Store and compare codes |

Compact form as a regular expression: `^[A-Z]{2}(0[1-9]|[1-9][0-9])[A-Z0-9]{3}[A-Z]{2}(0[1-9]|[1-9][0-9])$`

## Offline

```rust
use ng_postcode::{ParseError, Postcode, Segment};

fn main() -> Result<(), ParseError> {
    // Hyphens, spaces and case are all accepted.
    let code: Postcode = "ek 01 a03 fk 01".parse()?;

    assert_eq!(code.to_string(), "EK-01-A03-FK-01"); // canonical
    assert_eq!(code.as_str(), "EK01A03FK01");        // compact, for storage
    assert_eq!(code.to_spaced(), "EK 01 A03 FK 01"); // for display

    assert_eq!(code.state(), "EK");
    assert_eq!(code.prefix(Segment::Area), "EK-01-A03-FK");
    Ok(())
}
```

- `Postcode::parse` checks the structure: 2 letters, 2 digits, 3 letters or digits, 2 letters, 2 digits, with numeric segments from 01 to 99.
- `Postcode::parse_lenient` first swaps look-alike characters that cannot occur where they stand (`O`/`0`, `I`/`1`, `S`/`5`, `B`/`8`) and reports how many it changed.
- `Postcode::from_segments` assembles a code from its parts and zero-fills the LGA and unit.
- `Postcode` is `Copy`, 11 bytes, and sorts by state, LGA, district, area, unit.

A well-formed code is not necessarily assigned to a building, and the state is not checked against a list of state codes. Only the API can confirm that a postcode exists.

## API

```sh
cargo add ng-postcode --features client
```

```rust,no_run
use ng_postcode::{api, client::Client};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let client = Client::new(std::env::var("NG_POSTCODE_API_KEY")?);
    let found = client.send(&api::lookup("FC-03-B06-AG-12".parse()?, 2)?)?;
    println!("{:?}", found.administrative_address);
    Ok(())
}
```

`api` covers lookup, autocomplete, reverse geocoding and nearby search. Each function returns a `Request` value, or `InvalidRequest` for one the API cannot answer, such as an empty autocomplete or a coordinate that is not finite, and `Request::decode` turns a status and body into a typed result, so the `api` feature alone works with any HTTP client, sync or async. The `client` feature adds a small blocking one.

## Features

| Feature | Adds |
| --- | --- |
| `serde` | `Serialize` and `Deserialize` for `Postcode` |
| `api` | Request and response types, no I/O |
| `client` | Blocking HTTP client |

## License

MIT
