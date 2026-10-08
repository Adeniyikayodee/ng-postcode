# ng-postcode

Python library for Nigeria's National Digital Alphanumeric Postcode System (NDAPS), the building-level postcode NIPOST launched in October 2026. Parse, validate and format postcodes offline, and call the [postcode.gov.ng](https://docs.postcode.gov.ng) API for lookup, autocomplete and reverse geocoding.

Also available for Rust as [`ng-postcode` on crates.io](https://crates.io/crates/ng-postcode) for JavaScript as [`ng-postcode-js` on npm](https://www.npmjs.com/package/ng-postcode-js), and for Java as [`ng-postcode-api` on Maven Central](https://central.sonatype.com/artifact/io.github.adeniyikayodee/ng-postcode-api).

```sh
pip install ng-postcode            # offline core, no dependencies
pip install "ng-postcode[client]"  # adds the API client (httpx)
```

## Format

An 11-character code in five segments: state, LGA, district, area, building unit.

| Form | Example | Use it to |
| --- | --- | --- |
| Canonical | `EK-01-A03-FK-01` | Write a code and pass it between systems |
| Spaced | `EK 01 A03 FK 01` | Show a code to people |
| Compact | `EK01A03FK01` | Store and compare codes |

Compact form as a regular expression: `^[A-Z]{2}(0[1-9]|[1-9][0-9])[A-Z0-9]{3}[A-Z]{2}(0[1-9]|[1-9][0-9])$`

## Offline

Expected failures are returned as values, so the type checker makes you handle them.

```python
from ng_postcode import Postcode, Segment, parse

match parse("ek 01 a03 fk 01"):
    case Postcode() as code:
        print(code)  # EK-01-A03-FK-01
        print(code.compact)  # EK01A03FK01, store this
        print(code.spaced)  # EK 01 A03 FK 01
        print(code.prefix(Segment.AREA))  # EK-01-A03-FK
    case error:
        print(error)  # e.g. "invalid lga segment"
```

- `parse` accepts hyphenated, spaced or compact input in either case.
- `parse_lenient` first swaps look-alikes that cannot occur where they stand (`O`/`0`, `I`/`1`, `S`/`5`, `B`/`8`) and reports how many it changed.
- `from_segments` assembles a code from its parts and zero-fills the LGA and unit.
- `Postcode` is immutable, hashable and sorts by state, LGA, district, area, unit.

A well-formed code is not necessarily assigned to a building. Only the API can confirm that a postcode exists.

## API

```python
from ng_postcode import Postcode, parse
from ng_postcode.api import ApiError, lookup
from ng_postcode.client import Client, TransportError

code = parse("FC-03-B06-AG-12")
assert isinstance(code, Postcode)

with Client(api_key="nipost_live_...") as client:
    found = client.send(lookup(code, level=1))

match found:
    case ApiError() | TransportError():
        print(found)  # e.g. "invalid_api_key (401): ..."
    case _:
        print(found.valid, found.status)  # True valid
```

`send` returns the typed response, an `ApiError` (for example `auth_required` or `insufficient_credits`) or a `TransportError`. `AsyncClient` has the same interface for asyncio.

`ng_postcode.api` covers lookup, autocomplete, reverse geocoding and nearby search. Each function returns a `Request` value and `decode` turns a status and body into a typed result, so it works with any HTTP client without the `client` extra.

Get a key from the [NIPOST developer dashboard](https://dashboard.postcode.gov.ng). Level 1 lookups confirm a code is assigned; levels 2 and up return address details and consume credits.

## License

MIT
