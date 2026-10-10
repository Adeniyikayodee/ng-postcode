/** Runs the shared cases in `spec/`, which every implementation must pass. */

import { readFileSync } from "node:fs";
import { expect, test } from "vitest";
import {
  ApiError,
  autocomplete,
  type Coordinate,
  decode,
  lookup,
  nearby,
  type Request,
  reverse,
} from "../src/api.js";
import {
  fromSegments,
  InvalidCharacter,
  InvalidSegment,
  Postcode,
  parse,
  parseLenient,
  type Segment,
  WrongLength,
} from "../src/postcode.js";

type Case = any;
const spec = (name: string): Case =>
  JSON.parse(readFileSync(new URL(`../../../../spec/${name}.json`, import.meta.url), "utf8"));

const CODE = parse("FC03B06AG12") as Postcode;
const HERE: Coordinate = { lat: 7.6211, lng: 5.2214 };

function outcome(result: unknown): Case {
  if (result instanceof Postcode) return { canonical: String(result) };
  const message = String(result);
  if (result instanceof WrongLength)
    return { error: { kind: "length", found: result.found, message } };
  if (result instanceof InvalidCharacter) {
    const { char, index } = result;
    return { error: { kind: "invalid_character", char, index, message } };
  }
  if (result instanceof InvalidSegment)
    return { error: { kind: "segment", segment: result.segment, message } };
  const { postcode, corrections } = result as { postcode: Postcode; corrections: number };
  return { canonical: String(postcode), corrections };
}

const expected = ({ canonical, corrections, error }: Case): Case =>
  JSON.parse(JSON.stringify({ canonical, corrections, error }));

const vectors = spec("vectors");

test.each(vectors.parse.valid as Case[])("parse valid $input", (c) => {
  const code = parse(c.input) as Postcode;
  expect([String(code), code.compact, code.spaced]).toEqual([c.canonical, c.compact, c.spaced]);
});

test.each(vectors.parse.invalid as Case[])("parse invalid $input", (c) => {
  expect(outcome(parse(c.input))).toEqual(expected(c));
});

test.each(vectors.parse_lenient as Case[])("parse lenient $input", (c) => {
  expect(outcome(parseLenient(c.input))).toEqual(expected(c));
});

test.each(vectors.from_segments as Case[])("from segments $segments", (c) => {
  const [state, lga, district, area, unit] = c.segments as string[];
  expect(
    outcome(fromSegments(state ?? "", lga ?? "", district ?? "", area ?? "", unit ?? "")),
  ).toEqual(expected(c));
});

test.each(vectors.prefix as Case[])("prefix $input through $through", (c) => {
  expect((parse(c.input) as Postcode).prefix(c.through as Segment)).toBe(c.prefix);
});

function build(kind: string, args: Case): Request<unknown> {
  if (kind === "lookup") return lookup(parse(args.code) as Postcode, args.level);
  if (kind === "autocomplete") return autocomplete(args.q);
  const at = { lat: Number(args.lat), lng: Number(args.lng) };
  const metres = "metres" in args ? Number(args.metres) : undefined;
  return kind === "reverse" ? reverse(at, metres) : nearby(at, metres);
}

test.each(spec("requests").cases as Case[])("request $name", (c) => {
  let sent: Case = null;
  try {
    const request = build(c.request, c.args);
    sent = { path: request.path, query: request.params };
  } catch (error) {
    expect(error).toBeInstanceOf(RangeError);
  }
  expect(sent).toEqual(c.sends);
});

test.each(spec("requests").untyped as Case[])("untyped $name", (c) => {
  const { code, level, q, lat, lng, metres } = c.args;
  expect(() => {
    if (c.request === "lookup") lookup(c.parsed ? parse(code) : code, level);
    else if (c.request === "autocomplete") autocomplete(q);
    else reverse({ lat, lng }, metres);
  }).toThrow(/must be|expected/);
});

test("a Postcode cannot be built without parse", () => {
  const build = Postcode as unknown as new (...args: unknown[]) => Postcode;
  expect(() => new build("EK01A03FK01")).toThrow(TypeError);
  expect(() => new build(Symbol("checked"), "EK01A03FK01")).toThrow(TypeError);
  expect("unchecked" in Postcode).toBe(false);
});

test("text that was never checked cannot reach a lookup", () => {
  const code = parse("EK01A03FK01") as Postcode;
  expect(() => Object.assign(code, { compact: "../admin?x=1" })).toThrow(TypeError);
  expect(() => Object.defineProperty(code, "compact", { value: "x" })).toThrow(TypeError);
  expect(code.compact).toBe("EK01A03FK01");
  const forged = Object.create(Postcode.prototype, { compact: { value: "not a code!" } });
  expect(() => lookup(forged)).toThrow(TypeError);
});

const REQUESTS: Record<string, Request<unknown>> = {
  lookup: lookup(CODE),
  autocomplete: autocomplete("E"),
  reverse: reverse(HERE),
  nearby: nearby(HERE),
};

test.each(spec("tolerance").cases as Case[])("tolerance $name", (c) => {
  const body = "text" in c ? c.text : JSON.stringify(c.body);
  const decoded = decode(REQUESTS[c.request] as Request<unknown>, c.status, body);
  const found = !(decoded instanceof ApiError)
    ? ["ok", undefined]
    : decoded.code === "malformed_response"
      ? ["malformed", undefined]
      : ["rejected", decoded.code];
  expect(found).toEqual([c.outcome, c.code]);
  expect(facts(decoded)).toMatchObject(c.expect ?? {});
});

/** What a case may expect of the answer. */
function facts(decoded: unknown): Record<string, unknown> {
  if (Array.isArray(decoded)) return { count: decoded.length };
  const found = decoded as { suggestions?: unknown[]; found?: boolean; unit?: unknown };
  if (found.suggestions) return { count: found.suggestions.length };
  return "found" in found ? { unit: found.unit !== null } : {};
}

const live = <T>(request: Request<T>, name: string): T => {
  const captured = spec("responses")[name];
  const decoded = decode(request, captured.status, JSON.stringify(captured.body));
  if (decoded instanceof ApiError) throw decoded;
  return decoded;
};

test("decodes the responses captured from the live API", () => {
  expect(live(lookup(CODE), "lookup_valid")).toMatchObject({
    valid: true,
    status: "valid",
    verified: false,
  });
  expect(live(lookup(CODE), "lookup_not_found")).toMatchObject({
    valid: false,
    status: "not_found",
  });
  expect(live(lookup(CODE), "lookup_invalid")).toMatchObject({ valid: false, status: "invalid" });

  const states = live(autocomplete("E"), "autocomplete_state");
  expect([states.segment, states.suggestions.map((s) => s.code)]).toEqual([
    "state",
    ["EB", "ED", "EK", "EN"],
  ]);
  expect(live(autocomplete("EK 01 A29 KR 3"), "autocomplete_unit_empty")).toEqual({
    segment: "unit",
    suggestions: [],
  });

  const found = live(reverse(HERE), "reverse_found");
  expect(found.unit).toMatchObject({
    postcode: "EK-01-A29-KR-36",
    distance_m: 15.7,
    confidence: "high",
  });
  expect([found.coordinate, found.area, found.depth]).toEqual([HERE, "EK-01-A29-KR", "unit"]);
  expect(live(reverse(HERE, 250), "reverse_not_found")).toMatchObject({ found: false, unit: null });

  expect(live(nearby(HERE), "nearby_found").map((u) => u.distance_m)).toEqual([15.7, 18.3, 31]);
  expect(live(nearby(HERE), "nearby_empty")).toEqual([]);
});

test.each([
  ["lookup_level_not_granted", 403, "level_not_granted"],
  ["reverse_bad_request", 400, "bad_request"],
  ["invalid_api_key", 401, "invalid_api_key"],
])("live error %s", (name, status, code) => {
  expect(() => live(lookup(CODE), name)).toThrow(expect.objectContaining({ status, code }));
});
