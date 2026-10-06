# ng-postcode-mcp

MCP server for Nigeria's National Digital Alphanumeric Postcode System (NDAPS), the building-level postcode NIPOST launched in October 2026. It lets AI assistants validate postcodes offline, look them up, autocomplete them and find them by location through the [postcode.gov.ng](https://docs.postcode.gov.ng) API.

This is the Node edition of the [ng-postcode](https://github.com/Adeniyikayodee/ng-postcode) server. It registers its tools from the same contract as the Python edition, so names, descriptions and schemas are identical. The Python edition also has `resolve_address` and an HTTP transport.

<!-- mcp-name: io.github.Adeniyikayodee/ng-postcode -->

## Install

It runs over stdio with `npx` and needs Node 22.12 or later. Most clients take this entry in their MCP settings:

```json
{
  "mcpServers": {
    "ng-postcode": {
      "command": "npx",
      "args": ["-y", "ng-postcode-mcp"],
      "env": { "NG_POSTCODE_API_KEY": "nipost_live_..." }
    }
  }
}
```

Get an API key from the [NIPOST developer dashboard](https://dashboard.postcode.gov.ng). Validation works without one.

## Tools

| Tool | What it does | Needs a key | Cost |
| --- | --- | --- | --- |
| `validate_postcode` | Checks structure offline; returns canonical forms, segments and a suggested fix for look-alike characters | No | Free |
| `lookup_postcode` | Confirms a code is assigned to a building | Yes | Free |
| `lookup_postcode_details` | Adds the address (level 2), building use (level 3) and more. Offered only when `NG_POSTCODE_MAX_LEVEL` is 2 or more | Yes | Uses credits on every call |
| `autocomplete_postcode` | Suggests the next segment of a partly typed code | Yes | Free tier |
| `find_postcode_at_location` | Returns the postcode of the nearest building to a coordinate | Yes | Free tier |

Every tool is read-only except `lookup_postcode_details`, which spends credits. Errors come back as messages the model can act on.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `NG_POSTCODE_API_KEY` | none | NIPOST API key. Read from the environment only; never passed through tools. |
| `NG_POSTCODE_MAX_LEVEL` | `1` | Highest lookup level tools may request. Levels 2+ consume credits, so raise it deliberately. |
| `NG_POSTCODE_MAX_PAID_CALLS` | `25` | How many paid lookups one run of the server may make with its own key. |
| `NG_POSTCODE_BASE_URL` | `https://api.postcode.gov.ng` | Alternative API host, such as a staging stack. |

## Safety

- `lookup_postcode` is always level 1, which is free. The paid tool, `lookup_postcode_details`, does not exist for the model unless you raise `NG_POSTCODE_MAX_LEVEL`.
- The paid tool is not marked read-only or safe to retry, so a client that approves read-only tools on its own will still ask before spending.
- A mistyped code is never corrected and sent to the API silently. The server returns the suggestion and asks the model to confirm it with the user.
- Names and house addresses are withheld from location results unless the cap is 2 or more. Treat them as personal data under the Nigeria Data Protection Act.
- The key is never sent to another host: the client refuses redirects.

## License

MIT
