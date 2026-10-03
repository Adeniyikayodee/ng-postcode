# ng-postcode

[![CI](https://github.com/Adeniyikayodee/ng-postcode/actions/workflows/ci.yml/badge.svg)](https://github.com/Adeniyikayodee/ng-postcode/actions/workflows/ci.yml)
[![crates.io](https://img.shields.io/crates/v/ng-postcode.svg)](https://crates.io/crates/ng-postcode)
[![PyPI](https://img.shields.io/pypi/v/ng-postcode.svg?label=pypi%20ng-postcode)](https://pypi.org/project/ng-postcode/)
[![MCP server](https://img.shields.io/pypi/v/ng-postcode-mcp.svg?label=pypi%20ng-postcode-mcp)](https://pypi.org/project/ng-postcode-mcp/)

Developer tools for Nigeria's National Digital Alphanumeric Postcode System (NDAPS), the building-level postcode NIPOST launched in October 2026: libraries for Rust and Python, an MCP server for AI assistants, and a resolver that turns described addresses into postcodes.

A postcode has 11 characters in five segments, written `EK-01-A03-FK-01`: state, LGA, district, area and building unit.

## Packages

| Package | What it does | Install | Source |
| --- | --- | --- | --- |
| `ng-postcode` (Rust) | Parse, validate and format codes offline; client for the postcode.gov.ng API | `cargo add ng-postcode` | [`src/`](src), [docs](https://docs.rs/ng-postcode) |
| `ng-postcode` (Python) | The same behaviour, with sync and async clients | `pip install ng-postcode` | [`python/`](python) |
| `ng-postcode-mcp` | MCP server: validate, look up, autocomplete, find by location, resolve addresses | `uvx ng-postcode-mcp` | [`mcp/`](mcp) |
| `ng-address-resolver` | Resolve free-text addresses to postcodes, only as precisely as the evidence allows (pre-alpha) | `pip install ng-address-resolver` | [`agent/`](agent) |

Each package has its own README with full usage.

## Quick start

**AI assistants.** The MCP server works with any MCP client. It runs over stdio as `uvx ng-postcode-mcp`, with the API key in the environment. Most clients take this entry in their MCP settings:

```json
{
  "mcpServers": {
    "ng-postcode": {
      "command": "uvx",
      "args": ["ng-postcode-mcp"],
      "env": { "NG_POSTCODE_API_KEY": "nipost_live_..." }
    }
  }
}
```

Per-client steps for Cursor, VS Code, Codex, Claude and others are in the [MCP server README](mcp#install). Validation works without a key. The server is listed in the MCP Registry as `io.github.Adeniyikayodee/ng-postcode`.

**Python**

```python
from ng_postcode import Postcode, parse

match parse("ek 01 a03 fk 01"):
    case Postcode() as code:
        print(code, code.compact)  # EK-01-A03-FK-01 EK01A03FK01
    case error:
        print(error)               # e.g. "invalid lga segment"
```

**Rust**

```rust
use ng_postcode::{Postcode, Segment};

let code: Postcode = "ek 01 a03 fk 01".parse()?;
assert_eq!(code.to_string(), "EK-01-A03-FK-01");
assert_eq!(code.prefix(Segment::Area), "EK-01-A03-FK");
```

## The format

| Segment | Example | Shape |
| --- | --- | --- |
| State | `EK` | 2 letters |
| LGA | `01` | 2 digits, 01 to 99 |
| District | `A03` | 3 letters or digits |
| Area | `FK` | 2 letters |
| Building unit | `01` | 2 digits, 01 to 99 |

Input may be hyphenated, spaced or compact, in either case. The compact form matches `^[A-Z]{2}(0[1-9]|[1-9][0-9])[A-Z0-9]{3}[A-Z]{2}(0[1-9]|[1-9][0-9])$`. A well-formed code is not necessarily assigned to a building; only the NIPOST API can confirm that.

## Design

- **One behaviour, two languages.** Rust and Python both run the cases in [`spec/vectors.json`](spec/vectors.json), so they cannot drift apart.
- **Offline first.** Parsing and validation never touch the network. API access is a separate, optional layer.
- **Errors are values.** Expected failures, such as a malformed code or a rejected API key, are returned, not raised.
- **Careful with money and guesses.** The MCP server caps lookups at the free level unless told otherwise, and never corrects a mistyped code into a paid call. The resolver gives an area or district code when that is all the evidence supports.

## Status

- The NIPOST API needs a key for every endpoint, from the [developer dashboard](https://dashboard.postcode.gov.ng). Offline validation needs nothing.
- The API layer is tested against responses captured from the live API with a level 1 key, kept in [`spec/responses.json`](spec/responses.json). Run [`scripts/live_check.py`](scripts/live_check.py) with your own key to repeat the comparison. Lookup levels 2 and up need a higher-access key and are tested only against NIPOST's documented examples.
- The resolver and the `resolve_address` tool are pre-release. They work against the live API, but their accuracy on real addresses is unmeasured. Described addresses need a geocoder you run or pay for; text alone rarely identifies a building, so ask users for a location pin when the exact building matters.

### Where the live API differs from its docs

Observed on 3 October 2026:

- Every endpoint needs a key, including search, assembly and level 1 lookup, which the docs describe as public.
- Lookup also returns `status` (`valid`, `not_found`, `invalid`) and `verified`. A malformed code is answered with HTTP 200 and `status: invalid`, not an error.
- Autocomplete suggestions carry only `code`, the value of the next segment. The documented `label` is not sent.
- Reverse geocoding also returns `depth`.
- Nearby search, which the docs leave unspecified, returns a list of `postcode`, `display` and `distance_m`, nearest first.
- Asking for a level the key lacks returns `403 level_not_granted`.
- An empty autocomplete query never gets a response, so the libraries refuse to send one.
- `EK-01-A03-FK-01`, the example used throughout NIPOST's docs, is reported as not assigned.

## Development

```sh
cargo test --all-features                              # Rust
cd python && uv run --group dev pytest                 # Python library
cd mcp && uv run --group dev pytest                    # MCP server
cd agent && uv run --group dev pytest                  # resolver
```

CI runs formatting, linting, type checks and tests for every package. Releases publish from tags (`v*` is tagged after a crates.io release; `py-v*`, `mcp-v*` and `agent-v*` publish to PyPI and the MCP Registry) through trusted publishing, so no tokens are stored.

## License

MIT
