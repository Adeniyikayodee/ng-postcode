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
- `parse_prefix` reads a code cut off after a segment, such as the district `EK-01-A03`, and `Postcode.truncate` cuts a code down to one. A prefix knows which codes it contains, so it groups them by state, LGA, district, or area.
- `Postcode` is immutable, hashable and sorts by state, LGA, district, area, unit.

A well-formed code is not necessarily assigned to a building. Only the API can confirm that a postcode exists.

## Convert a CSV file

The package installs an `ng-postcode` command that checks a column of postcodes and writes the file back with four columns added.

```sh
ng-postcode orders.csv --column postcode --out checked.csv
```

```text
id,postcode,postcode_compact,postcode_status,postcode_suggestion,postcode_error
1,ek 01 a03 fk 01,EK01A03FK01,valid,,
2,EK-O1-A03-FK-01,,suggested,EK-01-A03-FK-01,invalid lga segment
3,360001,,invalid,,"expected 11 letters and digits, found 6"
4,,,empty,,
```

- `valid` rows carry the compact code to store.
- `suggested` rows only parse after look-alike characters are swapped. The fix is offered for a person to confirm, and the compact column is left empty.
- `invalid` rows say what is wrong, and `empty` rows had no value.

It works offline and reads one row at a time, so the size of the file does not matter. It never writes over the file it reads, and it stops at a header that already has one of these columns or a row with more cells than the header. Add `--confirm` to ask NIPOST whether each well-formed code is assigned to a building. That needs `pip install "ng-postcode[client]"` and your own key in `NG_POSTCODE_API_KEY`, makes one free level 1 lookup for each distinct code, and adds a `postcode_assigned` column. When NIPOST's rate limit is reached it waits a minute and asks again; after any other failure the remaining rows are left unconfirmed. A test key may report an assigned code as not assigned, and the command says so when it is given one.

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
