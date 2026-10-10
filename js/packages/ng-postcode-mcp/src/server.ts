/**
 * MCP server for Nigeria's NIPOST digital postcode.
 *
 * Tool names, descriptions and schemas come from `spec/mcp.json`, the contract the
 * Python server generates, so the two cannot drift. Validation runs offline; the
 * other tools call the postcode.gov.ng API with the key in NG_POSTCODE_API_KEY.
 */

import { fromJsonSchema, McpServer } from "@modelcontextprotocol/server";
import { Postcode, parse, parseLenient } from "ng-postcode-js";
import { ApiError, autocomplete, BASE_URL, lookup, reverse } from "ng-postcode-js/api";
import { Client, TransportError } from "ng-postcode-js/client";
import contract from "./contract.generated.json" with { type: "json" };

const KEY_URL = "https://dashboard.postcode.gov.ng";
const HINTS: Record<string, string> = {
  auth_required: `Supply a NIPOST API key from ${KEY_URL}.`,
  invalid_api_key: `The NIPOST API key is invalid or revoked; create a new key at ${KEY_URL}.`,
  insufficient_credits: "The NIPOST account is out of credits; top up or use level 1.",
  level_not_granted: `The key is not granted this lookup level; use a lower level or request more access at ${KEY_URL}.`,
};
const STATUS_HINTS: Record<number, string> = {
  403: "The key lacks the scope or access level for this request.",
  429: "NIPOST rate limit reached; wait before retrying.",
};
const LEVEL_1_FIELDS = ["postcode", "display", "distance_m", "confidence"];

export interface Settings {
  readonly apiKey: string | undefined;
  readonly maxLevel: number;
  /** How many paid lookups one process may make. Defaults to 25. */
  readonly maxPaidCalls?: number;
  readonly baseUrl: string;
  /** Your own `fetch`, as tests use. */
  readonly fetch?: typeof fetch;
}

/** Read settings from the environment, or describe what is wrong with them. */
export function settingsFromEnv(env: Record<string, string | undefined>): Settings | string {
  const level = (env.NG_POSTCODE_MAX_LEVEL ?? "1").trim();
  if (!/^[1-5]$/.test(level)) return `NG_POSTCODE_MAX_LEVEL must be 1 to 5, got '${level}'`;
  const paid = (env.NG_POSTCODE_MAX_PAID_CALLS ?? "25").trim();
  if (!/^[0-9]+$/.test(paid)) {
    return `NG_POSTCODE_MAX_PAID_CALLS must be a whole number, got '${paid}'`;
  }
  const apiKey = env.NG_POSTCODE_API_KEY?.trim() || undefined;
  // Refused without quoting it: a key no header can hold would surface in fetch's error.
  if (apiKey && !/^[\x21-\x7e]{1,256}$/.test(apiKey)) {
    return "NG_POSTCODE_API_KEY does not hold a usable NIPOST API key";
  }
  return {
    apiKey,
    maxLevel: Number(level),
    maxPaidCalls: Number(paid),
    baseUrl: env.NG_POSTCODE_BASE_URL?.trim() || BASE_URL,
  };
}

/** A failure the model can act on; its message becomes the tool's error text. */
class ToolError extends Error {}

type Args = Record<string, unknown>;
type Handler = (args: Args) => unknown;

export function createServer(settings: Settings): McpServer {
  const client = settings.apiKey
    ? new Client(settings.apiKey, {
        baseUrl: settings.baseUrl,
        ...(settings.fetch ? { fetch: settings.fetch } : {}),
      })
    : undefined;

  const api = (): Client => {
    if (client) return client;
    throw new ToolError(
      `This tool needs a NIPOST API key in NG_POSTCODE_API_KEY. Get one at ${KEY_URL}.`,
    );
  };

  const maxPaidCalls = settings.maxPaidCalls ?? 25;
  let paid = 0;

  const handlers: Record<string, Handler> = {
    validate_postcode: ({ postcode }) => validation(String(postcode)),

    lookup_postcode: async ({ postcode }) =>
      unwrap(await api().send(lookup(checked(String(postcode)), 1))),

    lookup_postcode_details: async ({ postcode, level = 2 }) => {
      if (Number(level) > settings.maxLevel) {
        throw new ToolError(
          `Level ${level} is above this server's cap of ${settings.maxLevel}. Levels 2+ consume NIPOST credits; the user can raise NG_POSTCODE_MAX_LEVEL to allow it.`,
        );
      }
      const [client, code] = [api(), checked(String(postcode))];
      paid += 1;
      if (paid > maxPaidCalls) {
        throw new ToolError(
          `This server has made its ${maxPaidCalls} paid lookups. The user can raise NG_POSTCODE_MAX_PAID_CALLS, or restart the server, to allow more.`,
        );
      }
      return unwrap(await client.send(lookup(code, Number(level))));
    },

    autocomplete_postcode: async ({ partial }) => {
      if (!String(partial).trim())
        throw new ToolError("Give at least the first characters of a postcode.");
      return unwrap(await api().send(autocomplete(String(partial))));
    },

    find_postcode_at_location: async ({ latitude, longitude, max_distance_m }) => {
      const at = { lat: Number(latitude), lng: Number(longitude) };
      const metres = max_distance_m == null ? undefined : Number(max_distance_m);
      const { coordinate: _, ...found } = unwrap(await api().send(reverse(at, metres)));
      return capped(found, settings.maxLevel);
    },
  };

  // Not offered at all under the default cap, so a model cannot spend by accident.
  if (settings.maxLevel < 2) delete handlers.lookup_postcode_details;

  const server = new McpServer(
    { name: "ng-postcode", title: "Nigeria Postcode", version: VERSION },
    { instructions: instructionsFor(Object.keys(handlers)) },
  );
  for (const tool of contract.tools) {
    const handler = handlers[tool.name];
    if (!handler) continue;
    server.registerTool(
      tool.name,
      {
        title: tool.title,
        description: tool.description,
        inputSchema: fromJsonSchema(tool.inputSchema),
        outputSchema: fromJsonSchema(tool.outputSchema),
        annotations: tool.annotations,
      },
      async (args) => {
        try {
          const output = (await handler(args as Args)) as Record<string, unknown>;
          return {
            content: [{ type: "text" as const, text: JSON.stringify(output, null, 2) }],
            structuredContent: output,
          };
        } catch (error) {
          if (!(error instanceof ToolError)) throw error;
          return { content: [{ type: "text" as const, text: error.message }], isError: true };
        }
      },
    );
  }
  return server;
}

export const VERSION = "0.3.0";

/** The shared instructions, without the lines about tools this server does not have. */
function instructionsFor(tools: readonly string[]): string {
  const missing = contract.tools.map((tool) => tool.name).filter((name) => !tools.includes(name));
  return contract.instructions
    .split("\n")
    .filter((line) => !missing.some((name) => line.startsWith(`- ${name} `)))
    .join("\n");
}

function validation(text: string) {
  const code = parse(text);
  if (code instanceof Postcode) {
    const { state, lga, district, area, unit } = code;
    return {
      valid: true,
      postcode: String(code),
      compact: code.compact,
      spaced: code.spaced,
      segments: { state, lga, district, area, unit },
      error: null,
      suggestion: null,
    };
  }
  return {
    valid: false,
    postcode: null,
    compact: null,
    spaced: null,
    segments: null,
    error: String(code),
    suggestion: suggestion(text),
  };
}

function suggestion(text: string): string | null {
  const fixed = parseLenient(text);
  return "postcode" in fixed ? String(fixed.postcode) : null;
}

/** The parsed code, or a ToolError the model can act on. Never auto-corrects a paid call. */
function checked(text: string): Postcode {
  const code = parse(text);
  if (code instanceof Postcode) return code;
  const hint = suggestion(text);
  const maybe = hint ? ` Did you mean ${hint}? Confirm with the user first.` : "";
  const shown = text.length <= 40 ? text : `${text.slice(0, 40)}...`;
  throw new ToolError(`'${shown}' is not a valid postcode: ${code}.${maybe}`);
}

/**
 * The location with only the unit's level 1 fields, unless the cap allows more. Any field
 * the unit gains later is withheld until it is listed as level 1.
 */
function capped<T extends { unit: object | null }>(location: T, maxLevel: number): T {
  if (maxLevel >= 2 || !location.unit) return location;
  const shown = Object.entries(location.unit).map(([field, value]) => [
    field,
    LEVEL_1_FIELDS.includes(field) ? value : null,
  ]);
  return { ...location, unit: Object.fromEntries(shown) };
}

function unwrap<T>(result: T | ApiError | TransportError): T {
  if (result instanceof TransportError) {
    throw new ToolError(`Could not reach the NIPOST API: ${result}`);
  }
  if (result instanceof ApiError) {
    // A status hint is for an answer NIPOST wrote, not for a proxy's error page.
    const answered = result.code !== "malformed_response";
    const hint = HINTS[result.code] ?? (answered ? STATUS_HINTS[result.status] : undefined) ?? "";
    throw new ToolError(`NIPOST API error ${result}. ${hint}`.trim());
  }
  return result;
}
