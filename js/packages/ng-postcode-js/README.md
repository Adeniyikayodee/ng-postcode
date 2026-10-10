# ng-postcode-js

JavaScript and TypeScript library for Nigeria's National Digital Alphanumeric Postcode System (NDAPS), the building-level postcode NIPOST launched in October 2026. Parse, validate and format postcodes offline, and call the [postcode.gov.ng](https://docs.postcode.gov.ng) API for lookup, autocomplete and reverse geocoding.

Part of the [ng-postcode project](https://github.com/Adeniyikayodee/ng-postcode), which has the same behaviour in Rust, Python and Java and an MCP server for AI assistants. All four run the same shared test cases.

```sh
npm install ng-postcode-js
```

No runtime dependencies. Needs Node 22.12 or later, or any runtime with `fetch`. It is an ES module that `require()` can also load; a TypeScript project compiled to CommonJS needs `"module": "nodenext"` for that, as `node16` rejects it.

## Offline

Expected failures are returned as values, so the type checker makes you handle them.

```ts
import { Postcode, parse } from "ng-postcode-js";

const code = parse("ek 01 a03 fk 01");
if (code instanceof Postcode) {
  console.log(String(code)); // EK-01-A03-FK-01
  console.log(code.compact); // EK01A03FK01, store this
  console.log(code.spaced); // EK 01 A03 FK 01
  console.log(code.prefix("area")); // EK-01-A03-FK
} else {
  console.log(String(code)); // e.g. "invalid lga segment"
}
```

- `parse` accepts hyphenated, spaced or compact input in either case.
- `parseLenient` first swaps look-alikes that cannot occur where they stand (`O`/`0`, `I`/`1`, `S`/`5`, `B`/`8`) and reports how many it changed.
- `fromSegments` assembles a code from its parts and zero-fills the LGA and unit.
- `parsePrefix` reads a code cut off after a segment, such as the district `EK-01-A03`, and `truncate` cuts a code down to one. A prefix knows which codes it contains, so it groups them by state, LGA, district, or area.
- `isValid` answers yes or no.

A well-formed code is not necessarily assigned to a building. Only the API can confirm that a postcode exists.

## API

```ts
import { Postcode, parse } from "ng-postcode-js";
import { ApiError, lookup } from "ng-postcode-js/api";
import { Client, TransportError } from "ng-postcode-js/client";

const code = parse("FC-03-B06-AG-12");
if (!(code instanceof Postcode)) throw new Error(String(code));

const client = new Client(process.env.NG_POSTCODE_API_KEY ?? "");
const found = await client.send(lookup(code, 1));

if (found instanceof ApiError || found instanceof TransportError) {
  console.error(String(found)); // e.g. "invalid_api_key (401): ..."
} else {
  console.log(found.valid, found.status); // true valid
}
```

`ng-postcode-js/api` covers `lookup`, `autocomplete`, `reverse` and `nearby`. Each returns a plain `Request`, and `decode` turns a status and body into a typed result, so it works with any HTTP client. A request that cannot succeed, such as a level outside 1 to 5, an empty autocomplete or a coordinate that is not finite, throws `RangeError` before anything is sent.

The client refuses redirects, so the key is never sent to another host. Response fields keep the API's own names, such as `administrative_address`.

Get a key from the [NIPOST developer dashboard](https://dashboard.postcode.gov.ng). Level 1 lookups confirm a code is assigned; levels 2 and up return address details and consume credits.

## License

MIT
