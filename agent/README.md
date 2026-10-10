# ng-address-resolver

Resolve free-text Nigerian addresses, such as "back of Fabian Hotel, off NTA Road, Ado Ekiti", to NIPOST digital postcodes (NDAPS). It answers only as precisely as the evidence allows, and asks a question when it cannot.

**Status: pre-release.** The typed-postcode, location-pin and geocoded paths have run against the live NIPOST API and a live geocoder. The Claude reading step is tested only against a mocked API, and accuracy on real addresses is unmeasured.

## How it decides

1. **A postcode written in the text** is extracted (never auto-corrected) and confirmed with NIPOST.
2. **A location pin** is reverse-geocoded by NIPOST. This is the only route to a high-confidence building code.
3. **Text only** is read by Claude into street, landmarks and their relation ("behind", "opposite", "at"), area, LGA and state, then placed with a geocoder and reverse-geocoded by NIPOST.

| Evidence | Answer |
| --- | --- |
| Typed postcode NIPOST confirms, or a pin within 10 m of a building | Building code, high confidence |
| A pin within 25 m, or the landmark the address *is* | Building code, medium confidence |
| A building near a landmark ("behind", "opposite") | Area code, e.g. `EK-01-A03-FK` |
| A street only | District code, low confidence |
| A town only, or nothing found | No code, plus a question for the user |

Text alone rarely identifies a building: a landmark's own building is not the one behind it, and a road's map point is not any house on it. Ask users for a location pin when you need the exact building.

## Usage

```sh
ng-address "back of Fabian Hotel, off NTA Road, Ado Ekiti"
ng-address "my house" --lat 7.6211 --lng 5.2214
```

The result is JSON: `status` (`resolved`, `partial`, `unresolved`), `code`, `level`, `confidence`, `method`, `question` and the `evidence` behind it.

```python
from ng_address import Resolver

result = await Resolver(nipost=..., parser=..., geocoder=...).resolve("...")
```

The core needs no model. Install `ng-address-resolver[claude]` to let the CLI and `ng_address.parse.ClaudeParser` read addresses with Claude. A caller that has already read the address, such as the host model of an MCP server, passes its own `ParsedAddress` as `resolve(..., parsed=...)` instead.

## Configuration

| Variable | Purpose |
| --- | --- |
| Anthropic credentials | Needs the `claude` extra. Read by the Anthropic SDK (`ANTHROPIC_API_KEY` or an `ant auth login` profile). Without them the raw text is searched instead. |
| `NG_POSTCODE_API_KEY` | NIPOST API key. Without it the only postcode returned is one written in the address as a code, unconfirmed and at medium confidence. |
| `NG_GEOCODER_URL` | A Nominatim server, ideally your own. |
| `NG_GEOCODER_CONTACT` | A URL or email sent in the User-Agent to identify you. Required for the public Nominatim. |
| `NG_ADDRESS_MODEL` | Claude model. Defaults to `claude-opus-5-5`. |

The public Nominatim at `https://nominatim.openstreetmap.org` allows light personal use only. A service whose main job is geocoding must run its own instance or use a commercial geocoder. Map data © OpenStreetMap contributors.

Each address uses at most one Claude call at low effort, up to three geocoder searches, and one or two NIPOST calls.

## License

MIT
