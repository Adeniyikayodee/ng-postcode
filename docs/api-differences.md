# Where the live API differs from its docs

What `api.postcode.gov.ng` does where [NIPOST's documentation](https://docs.postcode.gov.ng) says otherwise or says nothing. Each row gives the date it was last observed. The observations from 6 October onward were made with a level 1 test key. To repeat the comparison with your own key, run [`scripts/live_check.py`](https://github.com/Adeniyikayodee/ng-postcode/blob/main/scripts/live_check.py).

| Topic | The live API | Observed |
| --- | --- | --- |
| Keys | Every endpoint needs a key, including search, assembly and level 1 lookup, which the docs describe as public. | 3 October 2026 |
| Lookup | Also returns `status` (`valid`, `not_found`, `invalid`) and `verified`. A malformed code is answered with HTTP 200 and `status: invalid`. | 3 October 2026 |
| Lookup level | Asking for a level the key lacks returns `403 level_not_granted`. | 3 October 2026 |
| Lookup level | A level the API cannot read, or `0`, is answered at level 1. | 6 October 2026 |
| Autocomplete | Suggestions carry only `code`, the value of the next segment. The documented `label` is not sent. | 3 October 2026 |
| Autocomplete | An empty query is answered with no suggestions. On 3 October it never got a response, so the libraries refuse to send one. | 6 October 2026 |
| Reverse geocoding | Also returns `depth`. | 3 October 2026 |
| Reverse geocoding | A latitude outside -90 to 90, or a longitude outside -180 to 180, returns `500 internal`. | 9 October 2026 |
| Nearby search | Returns a list of `postcode`, `display` and `distance_m`, nearest first. The docs leave it unspecified. | 3 October 2026 |
| Load balancer | A request it rejects, such as a 5,000-character autocomplete query, returns `403` with an HTML body. | 6 October 2026 |
| Example code | `EK-01-A03-FK-01`, the example used throughout NIPOST's docs, is reported as not assigned. | 3 October 2026 |
| Test keys | With a level 1 test key, `FC-03-B06-AG-12`, autocomplete, reverse geocoding and nearby search all return empty answers where [`spec/responses.json`](https://github.com/Adeniyikayodee/ng-postcode/blob/main/spec/responses.json) records data. | 6 October 2026 |
