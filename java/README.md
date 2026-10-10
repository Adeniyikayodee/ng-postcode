# ng-postcode for Java

Java libraries for Nigeria's National Digital Alphanumeric Postcode System (NDAPS), the building-level postcode NIPOST launched in October 2026. Parse, validate and format postcodes offline, and call the [postcode.gov.ng](https://docs.postcode.gov.ng) API for lookup, autocomplete and reverse geocoding.

Part of the [ng-postcode project](https://github.com/Adeniyikayodee/ng-postcode), which has the same behaviour in Rust, Python and JavaScript. All four run the same shared test cases.

| Artifact | What it does | Dependencies |
| --- | --- | --- |
| `io.github.adeniyikayodee:ng-postcode` | Parse, validate and format codes offline | None |
| `io.github.adeniyikayodee:ng-postcode-api` | Requests, decoding and an HTTP client | The core and Jackson |

```xml
<dependency>
  <groupId>io.github.adeniyikayodee</groupId>
  <artifactId>ng-postcode-api</artifactId>
  <version>0.2.1</version>
</dependency>
```

Needs Java 17 or later. Neither library has been tested on Android, and the client cannot run there, as Android has no `java.net.http`.

## Offline

Expected failures are returned as values of a sealed type, so the compiler makes you handle them.

```java
import io.github.adeniyikayodee.ngpostcode.Postcode;
import io.github.adeniyikayodee.ngpostcode.Segment;

if (Postcode.parse("ek 01 a03 fk 01") instanceof Postcode code) {
    System.out.println(code);                      // EK-01-A03-FK-01
    System.out.println(code.compact());            // EK01A03FK01, store this
    System.out.println(code.spaced());             // EK 01 A03 FK 01
    System.out.println(code.prefix(Segment.AREA)); // EK-01-A03-FK
}
```

- `Postcode.parse` accepts hyphenated, spaced or compact input in either case, and returns a `Postcode` or a `ParseError` such as "invalid lga segment".
- `Postcode.parseLenient` first swaps look-alikes that cannot occur where they stand (`O`/`0`, `I`/`1`, `S`/`5`, `B`/`8`) and reports how many it changed.
- `Postcode.fromSegments` assembles a code from its parts and zero-fills the LGA and unit.
- `Postcode.isValid` answers yes or no.

A well-formed code is not necessarily assigned to a building. Only the API can confirm that a postcode exists.

## API

```java
import io.github.adeniyikayodee.ngpostcode.Postcode;
import io.github.adeniyikayodee.ngpostcode.api.Api;
import io.github.adeniyikayodee.ngpostcode.api.Client;
import io.github.adeniyikayodee.ngpostcode.api.Lookup;
import io.github.adeniyikayodee.ngpostcode.api.Result;

var client = new Client(System.getenv("NG_POSTCODE_API_KEY"));
Result<Lookup> found = client.send(Api.lookup(new Postcode("FC03B06AG12"), 1));

if (found instanceof Result.Ok<Lookup> ok) {
    System.out.println(ok.value().valid() + " " + ok.value().status()); // true valid
} else if (found instanceof Result.Failed<Lookup> failed) {
    System.err.println(failed.failure()); // e.g. "invalid_api_key (401): ..."
}
```

`Api` covers `lookup`, `autocomplete`, `reverse` and `nearby`. Each returns a plain `Request`, and `Api.decode` turns a status and body into a typed result, so it works with any HTTP client. A request that cannot succeed, such as a level outside 1 to 5, a blank autocomplete or a coordinate that is not finite, throws `IllegalArgumentException` before anything is sent.

The client never follows redirects, so the key is never sent to another host, and it gives up after 10 seconds. Fields the API may omit are `null`.

Get a key from the [NIPOST developer dashboard](https://dashboard.postcode.gov.ng). Level 1 lookups confirm a code is assigned; levels 2 and up return address details and consume credits.

## License

MIT
