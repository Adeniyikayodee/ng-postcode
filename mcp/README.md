# ng-postcode-mcp

MCP server for Nigeria's National Digital Alphanumeric Postcode System (NDAPS), the building-level postcode NIPOST launched in October 2026. It lets AI assistants validate postcodes offline and look them up, autocomplete them and find them by location through the [postcode.gov.ng](https://docs.postcode.gov.ng) API.

Built on the [`ng-postcode`](https://pypi.org/project/ng-postcode/) library.

<!-- mcp-name: io.github.Adeniyikayodee/ng-postcode -->

## Tools

| Tool | What it does | Needs a key | Cost |
| --- | --- | --- | --- |
| `validate_postcode` | Checks structure offline; returns canonical forms, segments and a suggested fix for look-alike characters | No | Free |
| `lookup_postcode` | Confirms a code is assigned; level 2 adds the address, level 3 building use | Yes | Level 1 free, 2+ uses credits |
| `autocomplete_postcode` | Suggests the next segment of a partly typed code | Yes | Free tier |
| `find_postcode_at_location` | Returns the postcode of the nearest building to a coordinate | Yes | Free tier |

All tools are read-only. Errors come back as messages the model can act on, such as a missing key or an exhausted credit balance.

## Install

Requires [uv](https://docs.astral.sh/uv/). Get an API key from the [NIPOST developer dashboard](https://dashboard.postcode.gov.ng); `validate_postcode` works without one.

**Claude Code**

```sh
claude mcp add ng-postcode -e NG_POSTCODE_API_KEY=nipost_live_... -- uvx ng-postcode-mcp
```

**Claude Desktop, Cursor and other clients** that use an `mcpServers` config:

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

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `NG_POSTCODE_API_KEY` | none | NIPOST API key. Read from the environment only; never passed through tools. |
| `NG_POSTCODE_MAX_LEVEL` | `1` | Highest lookup level tools may request. Levels 2+ consume credits, so raise it deliberately. |
| `NG_POSTCODE_BASE_URL` | `https://api.postcode.gov.ng` | Alternative API host, such as a staging stack. |

## Safety

- Lookups default to level 1, which is free. A model cannot spend credits unless you raise `NG_POSTCODE_MAX_LEVEL`.
- A mistyped code is never corrected and sent to the API silently. The server returns the suggestion and asks the model to confirm it with the user.
- Levels 2 and up return house addresses. Treat them as personal data under the Nigeria Data Protection Act.

## License

MIT
