# Integration notes for the NIPOST API

How `api.postcode.gov.ng` behaved on the dates given, for anyone building on it. These notes add detail to [NIPOST's documentation](https://docs.postcode.gov.ng), which remains the reference. The observations from 6 October onward were made with a level 1 test key. To repeat the comparison with your own key, run [`scripts/live_check.py`](https://github.com/Adeniyikayodee/ng-postcode/blob/main/scripts/live_check.py).

| Topic | The live API | Observed |
| --- | --- | --- |
| Keys | Every endpoint needs a key, including search, assembly and level 1 lookup. | 3 October 2026 |
| Lookup | Also returns `status` (`valid`, `not_found`, `invalid`) and `verified`. A malformed code is answered with HTTP 200 and `status: invalid`. | 3 October 2026 |
| Lookup level | Asking for a level the key lacks returns `403 level_not_granted`. | 3 October 2026 |
| Lookup level | A level the API cannot read, or `0`, is answered at level 1. | 6 October 2026 |
| Autocomplete | Suggestions carry `code`, the value of the next segment. Treat `label` as optional. | 3 October 2026 |
| Autocomplete | An empty query is answered with no suggestions. On 3 October it never got a response, so the libraries refuse to send one. | 6 October 2026 |
| Reverse geocoding | Also returns `depth`. | 3 October 2026 |
| Reverse geocoding | A latitude outside -90 to 90, or a longitude outside -180 to 180, returns `500 internal`. | 9 October 2026 |
| Nearby search | Returns a list of `postcode`, `display` and `distance_m`, nearest first. | 3 October 2026 |
| Load balancer | A request it rejects, such as a 5,000-character autocomplete query, returns `403` with an HTML body. | 6 October 2026 |
| Example code | `EK-01-A03-FK-01`, the example in NIPOST's docs, shows the format and is not an assigned building. | 3 October 2026 |
| Test keys | With a level 1 test key, `FC-03-B06-AG-12`, autocomplete, reverse geocoding and nearby search all return empty answers where [`spec/responses.json`](https://github.com/Adeniyikayodee/ng-postcode/blob/main/spec/responses.json) records data. | 6 October 2026 |
