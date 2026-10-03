/** Tool behaviour through a real MCP client, in process, with the NIPOST API mocked. */

import { readFileSync } from "node:fs";
import { Client, InMemoryTransport } from "@modelcontextprotocol/client";
import { expect, test } from "vitest";
import contract from "../src/contract.generated.json" with { type: "json" };
import { createServer, type Settings, settingsFromEnv, VERSION } from "../src/server.js";

const LOOKUP = { postcode: "EK-01-A03-FK-01", valid: true, status: "valid", verified: false };
const UNIT = {
  postcode: "EK-01-A03-FK-01",
  display: "EK 01 A03 FK 01",
  distance_m: 8,
  address: "NTA ROAD",
};

function nipost(seen: URL[]): typeof fetch {
  return (async (url: URL, init: RequestInit) => {
    seen.push(url);
    const key = (init.headers as Record<string, string>)["X-API-Key"];
    if (key !== "good") {
      return Response.json({ error: { code: "invalid_api_key", message: "no" } }, { status: 401 });
    }
    if (url.pathname === "/v1/lookup") return Response.json({ data: LOOKUP });
    if (url.pathname === "/v1/search/autocomplete") {
      return Response.json({ data: { segment: "lga", suggestions: [{ code: "01" }] } });
    }
    return Response.json({ data: { found: true, unit: UNIT, area: "EK-01-A03-FK", radius_m: 25 } });
  }) as typeof fetch;
}

async function connect(settings: Partial<Settings> = {}, seen: URL[] = []) {
  const [near, far] = InMemoryTransport.createLinkedPair();
  const base = { apiKey: "good", maxLevel: 1, baseUrl: "https://api.test", fetch: nipost(seen) };
  await createServer({ ...base, ...settings }).connect(far);
  const client = new Client({ name: "test", version: "0" });
  await client.connect(near);
  return client;
}

const call = async (client: Client, name: string, args: Record<string, unknown>) => {
  const result = await client.callTool({ name, arguments: args });
  const content = result.content as Array<{ text: string }>;
  return { ...result, text: content.map((block) => block.text).join(" ") };
};

test("the bundled contract is the shared one, and every tool matches it", async () => {
  const shared = new URL("../../../../spec/mcp.json", import.meta.url);
  expect(contract).toEqual(JSON.parse(readFileSync(shared, "utf8")));

  const client = await connect();
  const { tools } = await client.listTools();
  const expected = contract.tools.filter((tool) => tool.name !== "resolve_address");
  expect(tools).toEqual(expected);
  expect(client.getInstructions()).not.toContain("resolve_address");
  expect(client.getInstructions()).toContain("validate_postcode is offline");
});

test("validates offline and suggests a look-alike fix", async () => {
  const client = await connect({ apiKey: undefined });
  const good = await call(client, "validate_postcode", { postcode: "ek 01 a03 fk 01" });
  expect(good.structuredContent).toMatchObject({ valid: true, compact: "EK01A03FK01" });
  const bad = await call(client, "validate_postcode", { postcode: "EK-O1-A03-FK-01" });
  expect(bad.structuredContent).toMatchObject({ valid: false, suggestion: "EK-01-A03-FK-01" });
});

test("looks up within the level cap and never corrects a code into a call", async () => {
  const seen: URL[] = [];
  const client = await connect({}, seen);
  const found = await call(client, "lookup_postcode", { postcode: "EK-01-A03-FK-01" });
  expect(found.structuredContent).toMatchObject({ valid: true, status: "valid" });
  expect(String(seen[0])).toBe("https://api.test/v1/lookup?code=EK-01-A03-FK-01&level=1");

  const capped = await call(client, "lookup_postcode", { postcode: "EK-01-A03-FK-01", level: 3 });
  expect([capped.isError, capped.text]).toEqual([
    true,
    expect.stringContaining("above this server's cap"),
  ]);
  const typo = await call(client, "lookup_postcode", { postcode: "EK-O1-A03-FK-01" });
  expect([typo.isError, typo.text]).toEqual([
    true,
    expect.stringContaining("Did you mean EK-01-A03-FK-01?"),
  ]);
  const range = await call(client, "lookup_postcode", { postcode: "EK-01-A03-FK-01", level: 9 });
  expect(range.isError).toBe(true);
  expect(seen).toHaveLength(1);
});

test("missing and rejected keys come back as messages without the key", async () => {
  const missing = await call(await connect({ apiKey: undefined }), "lookup_postcode", LOOKUP);
  expect([missing.isError, missing.text]).toEqual([
    true,
    expect.stringContaining("NG_POSTCODE_API_KEY"),
  ]);
  const rejected = await call(await connect({ apiKey: "s3cret" }), "lookup_postcode", LOOKUP);
  expect(rejected.text).toContain("invalid_api_key (401)");
  expect(rejected.text).not.toContain("s3cret");
});

test("autocompletes, and withholds address fields under the level cap", async () => {
  const client = await connect();
  const completed = await call(client, "autocomplete_postcode", { partial: "EK" });
  expect(completed.structuredContent).toEqual({
    segment: "lga",
    suggestions: [{ code: "01", label: null }],
  });
  const blank = await call(client, "autocomplete_postcode", { partial: "  " });
  expect(blank.isError).toBe(true);

  const here = { latitude: 7.62, longitude: 5.22 };
  const near = await call(client, "find_postcode_at_location", here);
  expect(near.structuredContent).toMatchObject({
    found: true,
    unit: { distance_m: 8, address: null },
  });
  const open = await call(await connect({ maxLevel: 2 }), "find_postcode_at_location", here);
  expect(open.structuredContent).toMatchObject({ unit: { address: "NTA ROAD" } });
  const outside = await call(client, "find_postcode_at_location", {
    latitude: 95,
    longitude: 5.22,
  });
  expect(outside.isError).toBe(true);
});

test("the reported version is the package version", () => {
  const manifest = new URL("../package.json", import.meta.url);
  expect(VERSION).toBe(JSON.parse(readFileSync(manifest, "utf8")).version);
});

test("reads settings from the environment", () => {
  expect(settingsFromEnv({})).toEqual({
    apiKey: undefined,
    maxLevel: 1,
    baseUrl: "https://api.postcode.gov.ng",
  });
  expect(settingsFromEnv({ NG_POSTCODE_API_KEY: " k ", NG_POSTCODE_MAX_LEVEL: "3" })).toMatchObject(
    {
      apiKey: "k",
      maxLevel: 3,
    },
  );
  expect(settingsFromEnv({ NG_POSTCODE_MAX_LEVEL: "9" })).toBe(
    "NG_POSTCODE_MAX_LEVEL must be 1 to 5, got '9'",
  );
});
