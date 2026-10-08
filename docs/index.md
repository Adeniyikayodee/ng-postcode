# ng-postcode

Open-source tools for Nigeria's National Digital Alphanumeric Postcode System (NDAPS), the building-level postcode issued by NIPOST. A postcode has 11 characters in five segments, written `EK-01-A03-FK-01`: state, LGA, district, area and building unit.

| Package | Install | Use it to |
| --- | --- | --- |
| [`ng-postcode` for Python](https://pypi.org/project/ng-postcode/) | `pip install ng-postcode` | Validate, parse and format codes offline; call the NIPOST API |
| [`ng-postcode` for Rust](https://crates.io/crates/ng-postcode) | `cargo add ng-postcode` | The same behaviour in Rust |
| [`ng-postcode-js`](https://www.npmjs.com/package/ng-postcode-js) | `npm install ng-postcode-js` | The same behaviour in JavaScript and TypeScript |
| [`ng-postcode` for Java](https://central.sonatype.com/artifact/io.github.adeniyikayodee/ng-postcode-api) | `io.github.adeniyikayodee:ng-postcode-api` | The same behaviour in Java 17 and later |
| [`ng-postcode-mcp`](https://pypi.org/project/ng-postcode-mcp/) | `uvx ng-postcode-mcp` or `npx ng-postcode-mcp` | Give an AI assistant postcode tools |
| [`ng-address-resolver`](https://pypi.org/project/ng-address-resolver/) | `pip install ng-address-resolver` | Turn a described address into a postcode (pre-release) |

Source and issues: [github.com/Adeniyikayodee/ng-postcode](https://github.com/Adeniyikayodee/ng-postcode). For AI agents: [llms.txt](llms.txt).

## Validate a postcode in Python

```python
from ng_postcode import Postcode, parse

match parse("ek 01 a03 fk 01"):
    case Postcode() as code:
        print(code)          # EK-01-A03-FK-01
        print(code.compact)  # EK01A03FK01, store this
    case error:
        print(error)         # e.g. "invalid lga segment"
```

Validation is offline and needs no key. `parse_lenient` also fixes look-alike characters such as `O` for `0`, and `from_segments` builds a code from its parts.

## Validate a postcode in JavaScript

```ts
import { Postcode, parse } from "ng-postcode-js";

const code = parse("ek 01 a03 fk 01");
if (code instanceof Postcode) {
  console.log(String(code), code.compact); // EK-01-A03-FK-01 EK01A03FK01
} else {
  console.log(String(code)); // e.g. "invalid lga segment"
}
```

`ng-postcode-js/api` and `ng-postcode-js/client` call the NIPOST API with `fetch`.

## Validate a postcode in Rust

```rust
use ng_postcode::{Postcode, Segment};

let code: Postcode = "ek 01 a03 fk 01".parse()?;
assert_eq!(code.to_string(), "EK-01-A03-FK-01");
assert_eq!(code.prefix(Segment::Area), "EK-01-A03-FK");
```

## Confirm a postcode exists

A well-formed code is not necessarily assigned to a building. Only the NIPOST API can confirm that, with a key from the [developer dashboard](https://dashboard.postcode.gov.ng).

```python
from ng_postcode import Postcode
from ng_postcode.api import ApiError, lookup
from ng_postcode.client import Client, TransportError  # pip install "ng-postcode[client]"

with Client(api_key="nipost_live_...") as client:
    found = client.send(lookup(Postcode("FC03B06AG12"), level=1))

match found:
    case ApiError() | TransportError():
        print(found)                      # e.g. "invalid_api_key (401): ..."
    case _:
        print(found.valid, found.status)  # True valid
```

```rust
use ng_postcode::{api, client::Client}; // features = ["client"]

let client = Client::new(std::env::var("NG_POSTCODE_API_KEY")?);
let found = client.send(&api::lookup("FC-03-B06-AG-12".parse()?, 1)?)?;
```

Level 1 confirms a code is assigned. Levels 2 and up return address details and consume credits. The API layer also covers autocomplete, reverse geocoding and nearby search.

## Use it from an AI assistant

The MCP server works with any MCP client, including Claude Code, Claude Desktop, Cursor, VS Code and Codex:

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

With Node, use `npx -y ng-postcode-mcp` in place of `uvx ng-postcode-mcp`. It offers `validate_postcode`, `lookup_postcode`, `autocomplete_postcode`, `find_postcode_at_location` and `resolve_address`. Validation works without a key. See the [MCP server README](https://github.com/Adeniyikayodee/ng-postcode/tree/main/mcp#install) for per-client steps and settings.

## Pass a postcode between systems

When one system or AI agent hands a location to another, send it as a postcode reference: the code, how precise it is, and optionally how far to trust it.

```json
{ "code": "EK-01-A03-FK", "level": "area", "confidence": "medium" }
```

`level` is one of `state`, `lga`, `district`, `area` or `building`, and `code` is the hyphenated code down to that level. Add `assigned` and `checked_at` after confirming a building code with NIPOST. The receiver can validate the reference against the [JSON Schema](schemas/postcode-reference.schema.json) and re-check the code itself. A resolved or partial answer from `resolve_address` already has this shape.

## The format

| Segment | Example | Shape |
| --- | --- | --- |
| State | `EK` | 2 letters |
| LGA | `01` | 2 digits, 01 to 99 |
| District | `A03` | 3 letters or digits |
| Area | `FK` | 2 letters |
| Building unit | `01` | 2 digits, 01 to 99 |

Compact form as a regular expression: `^[A-Z]{2}(0[1-9]|[1-9][0-9])[A-Z0-9]{3}[A-Z]{2}(0[1-9]|[1-9][0-9])$`
