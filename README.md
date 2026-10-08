# ng-postcode

[![CI](https://github.com/Adeniyikayodee/ng-postcode/actions/workflows/ci.yml/badge.svg)](https://github.com/Adeniyikayodee/ng-postcode/actions/workflows/ci.yml)
[![crates.io](https://img.shields.io/crates/v/ng-postcode.svg)](https://crates.io/crates/ng-postcode)
[![PyPI](https://img.shields.io/pypi/v/ng-postcode.svg?label=pypi%20ng-postcode)](https://pypi.org/project/ng-postcode/)
[![MCP server](https://img.shields.io/pypi/v/ng-postcode-mcp.svg?label=pypi%20ng-postcode-mcp)](https://pypi.org/project/ng-postcode-mcp/)
[![npm](https://img.shields.io/npm/v/ng-postcode-js.svg?label=npm%20ng-postcode-js)](https://www.npmjs.com/package/ng-postcode-js)
[![npm MCP server](https://img.shields.io/npm/v/ng-postcode-mcp.svg?label=npm%20ng-postcode-mcp)](https://www.npmjs.com/package/ng-postcode-mcp)

Developer tools for Nigeria's National Digital Alphanumeric Postcode System (NDAPS), the building-level postcode NIPOST launched in October 2026: libraries for Rust, Python, JavaScript, and Java, MCP servers for AI assistants on PyPI and npm, and a resolver that turns described addresses into postcodes.

A postcode has 11 characters in five segments, written `EK-01-A03-FK-01`: state, LGA, district, area and building unit.

## Start here

| To | Use |
| --- | --- |
| Check, tidy, or format a code someone typed | The library for your language. It works offline, with no key. |
| Confirm a code is assigned to a building | The same library's API client, with a key from the [NIPOST developer dashboard](https://dashboard.postcode.gov.ng) |
| Give an AI assistant postcode tools | `ng-postcode-mcp` |
| Find the postcode for a described address or a location pin | `ng-address-resolver`, or the `resolve_address` tool of the Python MCP server (both pre-release) |
| Take postcodes at a WooCommerce checkout | [ng-postcode-woocommerce](https://github.com/Adeniyikayodee/ng-postcode-woocommerce) |

## Packages

| Package | What it does | Install | Source |
| --- | --- | --- | --- |
| `ng-postcode` (Rust) | Parse, validate and format codes offline; client for the postcode.gov.ng API | `cargo add ng-postcode` | [`src/`](src), [docs](https://docs.rs/ng-postcode) |
| `ng-postcode` (Python) | The same behaviour, with sync and async clients | `pip install ng-postcode` | [`python/`](python) |
| `ng-postcode-js` | The same behaviour for JavaScript and TypeScript, with a `fetch` client | `npm install ng-postcode-js` | [`js/packages/ng-postcode-js`](js/packages/ng-postcode-js) |
| `ng-postcode` and `ng-postcode-api` (Java) | The same behaviour for Java 17 and later; the core has no dependencies | `io.github.adeniyikayodee:ng-postcode-api` | [`java/`](java) |
| `ng-postcode-mcp` | MCP server: validate, look up, autocomplete, find by location, resolve addresses | `uvx ng-postcode-mcp` | [`mcp/`](mcp) |
| `ng-postcode-mcp` (npm) | The same server for Node, without address resolution | `npx ng-postcode-mcp` | [`js/packages/ng-postcode-mcp`](js/packages/ng-postcode-mcp) |
| `ng-address-resolver` | Resolve free-text addresses to postcodes, only as precisely as the evidence allows (pre-alpha) | `pip install ng-address-resolver` | [`agent/`](agent) |

Each package has its own README with full usage.

For online stores, [ng-postcode-woocommerce](https://github.com/Adeniyikayodee/ng-postcode-woocommerce) is a WooCommerce plugin built on the same rules and the same shared test cases: it checks and tidies the postcode at checkout, finds it from the customer's location, and makes shipping zones match on postcode prefixes.

## Quick start

Parsing and validation are offline and need no key.

**Python**

```python
from ng_postcode import Postcode, parse

match parse("ek 01 a03 fk 01"):
    case Postcode() as code:
        print(code, code.compact)  # EK-01-A03-FK-01 EK01A03FK01
    case error:
        print(error)               # e.g. "invalid lga segment"
```

**JavaScript and TypeScript**

```ts
import { Postcode, parse } from "ng-postcode-js";

const code = parse("ek 01 a03 fk 01");
if (code instanceof Postcode) {
  console.log(String(code), code.compact); // EK-01-A03-FK-01 EK01A03FK01
} else {
  console.log(String(code));               // e.g. "invalid lga segment"
}
```

**Java**

```java
import io.github.adeniyikayodee.ngpostcode.Postcode;

if (Postcode.parse("ek 01 a03 fk 01") instanceof Postcode code) {
    System.out.println(code + " " + code.compact()); // EK-01-A03-FK-01 EK01A03FK01
}
```

**Rust**

```rust
use ng_postcode::{Postcode, Segment};

let code: Postcode = "ek 01 a03 fk 01".parse()?;
assert_eq!(code.to_string(), "EK-01-A03-FK-01");
assert_eq!(code.prefix(Segment::Area), "EK-01-A03-FK");
```

**AI assistants**

The MCP server works with any MCP client. It runs over stdio as `uvx ng-postcode-mcp`, with the API key in the environment. Most clients take this entry in their MCP settings:

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

To run it with Node, use `"command": "npx"` and `"args": ["-y", "ng-postcode-mcp"]`; that edition has every tool except address resolution. Per-client steps for Cursor, VS Code, Codex, Claude and others are in the [MCP server README](mcp#install). Validation works without a key; the other tools need one from the [NIPOST developer dashboard](https://dashboard.postcode.gov.ng). The server is listed in the MCP Registry as `io.github.Adeniyikayodee/ng-postcode`.

## For coding agents

Language models trained before October 2026 expect a six-digit Nigerian postcode. To point a coding agent at the current format, paste this into your project's `AGENTS.md`, `CLAUDE.md`, or editor rules:

```text
Nigerian postcodes: since 1 October 2026 a building's postcode is NIPOST's 11-character
digital postcode (NDAPS), such as EK-01-A03-FK-01, and a six-digit pattern does not match it.
Validate and format it with ng-postcode (pip, cargo), ng-postcode-js (npm), or
io.github.adeniyikayodee:ng-postcode (Maven). On npm, ng-postcode is a different project.
Reference: https://adeniyikayodee.github.io/ng-postcode/llms.txt
```

## The format

| Segment | Example | Shape |
| --- | --- | --- |
| State | `EK` | 2 letters |
| LGA | `01` | 2 digits, 01 to 99 |
| District | `A03` | 3 letters or digits |
| Area | `FK` | 2 letters |
| Building unit | `01` | 2 digits, 01 to 99 |

| Form | Example | Use it to |
| --- | --- | --- |
| Canonical | `EK-01-A03-FK-01` | Write a code and pass it between systems |
| Spaced | `EK 01 A03 FK 01` | Show a code to people |
| Compact | `EK01A03FK01` | Store and compare codes |

Input may be hyphenated, spaced or compact, in either case. The compact form matches `^[A-Z]{2}(0[1-9]|[1-9][0-9])[A-Z0-9]{3}[A-Z]{2}(0[1-9]|[1-9][0-9])$`. A well-formed code is not necessarily assigned to a building; only the NIPOST API can confirm that.

## Passing a postcode between systems

[`docs/schemas/postcode-reference.schema.json`](docs/schemas/postcode-reference.schema.json) defines a small JSON object for handing a location from one system or AI agent to another: the code, its level (`state` to `building`), and optionally a confidence and whether NIPOST confirmed it. A resolved or partial `resolve_address` answer already fits it.

## Design

- **One behaviour, four languages:** Rust, Python, JavaScript and Java all run the cases in [`spec/`](spec), so they cannot drift apart. The Node MCP server registers its tools from [`spec/mcp.json`](spec/mcp.json), which the Python server generates.
- **Offline first:** parsing and validation never touch the network. API access is a separate, optional layer.
- **Errors are values:** expected failures, such as a malformed code or a rejected API key, come back as return values.
- **Careful with money and guesses:** the MCP server caps lookups at the free level unless told otherwise, and never corrects a mistyped code into a paid call. The resolver gives an area or district code when that is all the evidence supports.

## Status

- The NIPOST API needs a key for every endpoint, from the [developer dashboard](https://dashboard.postcode.gov.ng). Offline validation needs nothing.
- The API layer is tested against responses captured from the live API with a level 1 key, kept in [`spec/responses.json`](spec/responses.json). Run [`scripts/live_check.py`](scripts/live_check.py) with your own key to repeat the comparison. Lookup levels 2 and up need a higher-access key and are tested only against NIPOST's documented examples.
- The resolver and the `resolve_address` tool are pre-release. They work against the live API, but their accuracy on real addresses is unmeasured. Described addresses need a geocoder you run or pay for; text alone rarely identifies a building, so ask users for a location pin when the exact building matters.

### Where the live API differs from its docs

Observed on 3 October 2026:

- Every endpoint needs a key, including search, assembly and level 1 lookup, which the docs describe as public.
- Lookup also returns `status` (`valid`, `not_found`, `invalid`) and `verified`. A malformed code is answered with HTTP 200 and `status: invalid`.
- Autocomplete suggestions carry only `code`, the value of the next segment. The documented `label` is not sent.
- Reverse geocoding also returns `depth`.
- Nearby search, which the docs leave unspecified, returns a list of `postcode`, `display` and `distance_m`, nearest first.
- Asking for a level the key lacks returns `403 level_not_granted`.
- An empty autocomplete query never gets a response, so the libraries refuse to send one.
- `EK-01-A03-FK-01`, the example used throughout NIPOST's docs, is reported as not assigned.

Observed on 6 October 2026, with a level 1 test key:

- An empty autocomplete query is answered, with no suggestions. The libraries still refuse to send one.
- `FC-03-B06-AG-12`, autocomplete, reverse geocoding and nearby search all return empty answers where [`spec/responses.json`](spec/responses.json) records data. `scripts/live_check.py` lists each difference.
- A lookup level the API cannot read, or `0`, is answered at level 1.
- A latitude outside -90 to 90 returns `500 internal`.
- A request the load balancer rejects, such as a 5,000-character autocomplete query, returns `403` with an HTML body.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for the shared spec, how to add a language, and the commit standards.

```sh
cargo test --all-features                              # Rust
cd python && uv run --group dev pytest                 # Python library
cd mcp && uv run --group dev pytest                    # MCP server
cd agent && uv run --group dev pytest                  # resolver
cd js && npm ci && npm test                            # JavaScript library and Node MCP server
cd java && ./mvnw verify                               # Java libraries
```

CI runs formatting, linting, type checks and tests for every package. Releases publish from tags (`v*` to crates.io; `py-v*`, `mcp-v*` and `agent-v*` to PyPI and the MCP Registry; `js-v*` and `js-mcp-v*` to npm) through trusted publishing, so no tokens are stored. Maven Central has no trusted publishing, so `java-v*` uses a token and a signing key held as environment secrets, and the upload is published by hand. An `mcp-v*` release also creates a GitHub release, which Glama rebuilds its listing from, and republishes the Smithery bundle with a key held the same way.

## License

MIT
