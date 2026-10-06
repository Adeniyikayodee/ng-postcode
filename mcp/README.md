# ng-postcode-mcp

MCP server for Nigeria's National Digital Alphanumeric Postcode System (NDAPS), the building-level postcode NIPOST launched in October 2026. It lets AI assistants validate postcodes offline, look them up, autocomplete them and find them by location through the [postcode.gov.ng](https://docs.postcode.gov.ng) API, and resolve described addresses to postcodes.

Built on the [`ng-postcode`](https://pypi.org/project/ng-postcode/) and [`ng-address-resolver`](https://pypi.org/project/ng-address-resolver/) libraries. A Node edition with the same tools, apart from `resolve_address`, is on npm as [`ng-postcode-mcp`](https://www.npmjs.com/package/ng-postcode-mcp) and runs with `npx`.

<!-- mcp-name: io.github.Adeniyikayodee/ng-postcode -->

## Tools

| Tool | What it does | Needs a key | Cost |
| --- | --- | --- | --- |
| `validate_postcode` | Checks structure offline; returns canonical forms, segments and a suggested fix for look-alike characters | No | Free |
| `lookup_postcode` | Confirms a code is assigned to a building | Yes | Free |
| `lookup_postcode_details` | Adds the address (level 2), building use (level 3) and more. Offered only when `NG_POSTCODE_MAX_LEVEL` is 2 or more | Yes | Uses credits on every call |
| `autocomplete_postcode` | Suggests the next segment of a partly typed code | Yes | Free tier |
| `find_postcode_at_location` | Returns the postcode of the nearest building to a coordinate | Yes | Free tier |
| `resolve_address` | Turns a described address ("back of Fabian Hotel, off NTA Road") or a location pin into a postcode, only as precisely as the evidence allows | Yes, plus a geocoder for text | Free tier |

Every tool is read-only except `lookup_postcode_details`, which spends credits. Errors come back as messages the model can act on, such as a missing key or an exhausted credit balance.

### How `resolve_address` answers

The assistant reads the address and passes its landmarks and map searches to the tool; the server makes no model calls of its own. The answer is never more precise than its evidence:

| Evidence | Answer |
| --- | --- |
| A postcode written in the address, or a location pin on a building | Building code |
| A landmark the address *is* | Building code, medium confidence |
| A building near a landmark ("behind", "opposite") | Area code, plus a question for the user |
| A street only | District code, low confidence |
| A town only, or nothing found | No code, plus a question |

Text alone rarely identifies a building, so ask users for a location pin when the exact building matters. This tool is pre-release: it works against the live API, but its accuracy on real addresses is unmeasured.

## Install

Works with any MCP client. The server runs over stdio:

| Setting | Value |
| --- | --- |
| Command | `uvx` |
| Arguments | `ng-postcode-mcp` |
| Environment | `NG_POSTCODE_API_KEY` (optional for `validate_postcode`) |

It needs [uv](https://docs.astral.sh/uv/) installed. Get an API key from the [NIPOST developer dashboard](https://dashboard.postcode.gov.ng).

Most clients take this entry in their MCP settings:

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

| Client | How to add it |
| --- | --- |
| Claude Code | `claude mcp add ng-postcode -e NG_POSTCODE_API_KEY=nipost_live_... -- uvx ng-postcode-mcp` |
| Claude Desktop | The entry above, in its MCP server settings |
| Codex | `codex mcp add ng-postcode --env NG_POSTCODE_API_KEY=nipost_live_... -- uvx ng-postcode-mcp` |
| Cursor | The entry above, in `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (global) |
| VS Code | The same server object in `.vscode/mcp.json`, under a top-level `"servers"` key instead of `"mcpServers"` |
| Others | Any client that launches stdio servers: use the command, arguments and environment above |

### As a bundle

[`bundle/`](bundle) holds an MCPB manifest for clients that install `.mcpb` files, such as Claude Desktop. It runs the published package with uv and asks for the API key in the client's own settings. Build it with `npx @anthropic-ai/mcpb pack mcp/bundle ng-postcode.mcpb` from the repository root. [`bundle-python/`](bundle-python) is the same bundle for hosts that only run Python bundles, such as Smithery; it starts the server with `uvx`, so uv must be installed. `scripts/smithery_bundle.py` builds the copy Smithery accepts, which also carries each tool's input schema.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `NG_POSTCODE_API_KEY` | none | NIPOST API key. Read from the environment only; never passed through tools. |
| `NG_POSTCODE_MAX_LEVEL` | `1` | Highest lookup level tools may request. Levels 2+ consume credits, so raise it deliberately. |
| `NG_POSTCODE_MAX_PAID_CALLS` | `25` | How many paid lookups one run of the server may make with its own key. |
| `NG_POSTCODE_BASE_URL` | `https://api.postcode.gov.ng` | Alternative API host, such as a staging stack. |
| `NG_GEOCODER_URL` | none | A Nominatim server `resolve_address` uses to place described addresses. Without it, only typed postcodes and location pins resolve. |
| `NG_GEOCODER_CONTACT` | none | A URL or email sent in the User-Agent. Required for the public Nominatim. |
| `NG_POSTCODE_TRANSPORT` | `stdio` | `http` serves streamable HTTP at `/mcp` instead. |
| `NG_POSTCODE_HOST`, `NG_POSTCODE_PORT` | `127.0.0.1`, `8000` | Where the HTTP transport listens. |

The public Nominatim at `https://nominatim.openstreetmap.org` allows light personal use only; a service whose main job is geocoding must run its own instance. Map data © OpenStreetMap contributors.

## HTTP and Docker

```sh
NG_POSTCODE_TRANSPORT=http uvx ng-postcode-mcp        # http://127.0.0.1:8000/mcp
docker build -t ng-postcode-mcp . && docker run --rm -i ng-postcode-mcp   # from the repository root
```

Over HTTP a caller can send its own NIPOST key in the `X-NIPOST-API-Key` header, and that key is used for that caller's requests only. A caller that sends none uses the server's key, if `NG_POSTCODE_API_KEY` is set.

To host the server for other people, leave `NG_POSTCODE_API_KEY` unset so every caller brings a key, and serve it over HTTPS so the header is encrypted. Callers are trusting the host with their key, and all of them share the host's geocoder, which answers one search a second. Validation still works without any key. If you do set a server key, anyone who can reach the server spends its credits, so keep it on loopback or behind your own authentication. `NG_POSTCODE_MAX_LEVEL` caps every caller either way.

## Safety

- The key is read from the environment or the `X-NIPOST-API-Key` header, never from tool arguments, and never appears in results or logs.
- `lookup_postcode` is always level 1, which is free. The paid tool, `lookup_postcode_details`, does not exist for the model unless you raise `NG_POSTCODE_MAX_LEVEL`.
- The paid tool is not marked read-only or safe to retry, so a client that approves read-only tools on its own will still ask before spending.
- A mistyped code is never corrected and sent to the API silently. The server returns the suggestion and asks the model to confirm it with the user.
- Levels 2 and up return house addresses. Treat them as personal data under the Nigeria Data Protection Act.
- `resolve_address` sends the search strings to the geocoder you configure. With a third-party geocoder, that shares address text with it.

## License

MIT
