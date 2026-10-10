/**
 * The NIPOST Postcode API as plain data: requests to send and responses to decode.
 *
 * Nothing here performs I/O, so it works with any HTTP client. Assembly and
 * disassembly are not modelled: `parse` and `fromSegments` do both offline.
 * Response fields keep the API's own names.
 */

import { Postcode, SEGMENTS, type Segment, trimWhiteSpace } from "./postcode.js";

export const BASE_URL = "https://api.postcode.gov.ng";

/** A GET request whose successful response decodes to `T`. */
export interface Request<T> {
  readonly path: string;
  readonly params: ReadonlyArray<readonly [string, string]>;
  readonly read: (data: unknown) => T | undefined;
}

export interface Coordinate {
  readonly lat: number;
  readonly lng: number;
}

/**
 * The API refused the request, with `code` taken from its error envelope
 * (`auth_required`, `insufficient_credits`, ...), or its answer was not the
 * documented envelope, with `code` set to `malformed_response`.
 */
export class ApiError {
  constructor(
    readonly status: number,
    readonly code: string,
    readonly message: string,
  ) {}

  toString(): string {
    return `${this.code} (${this.status}): ${this.message}`;
  }
}

export interface AdministrativeAddress {
  readonly state_name: string | null;
  readonly lga_name: string | null;
  readonly locality_name: string | null;
  readonly zone: string | null;
}

/** Fields above the level granted to the key are `null`. */
export interface Lookup {
  readonly postcode: string;
  readonly valid: boolean;
  /** `valid`, `not_found`, or `invalid` for a malformed code. Sent at every level. */
  readonly status: string | null;
  readonly verified: boolean | null;
  /** Level 2. */
  readonly administrative_address: AdministrativeAddress | null;
  /** Level 2. */
  readonly recent_house_address: string | null;
  /** Level 3. */
  readonly building_use_status: string | null;
  /** Level 4. Undocumented, so left as raw JSON. */
  readonly other_building_info: unknown;
  /** Level 5. Undocumented, so left as raw JSON. */
  readonly point_geometry: unknown;
}

export interface Suggestion {
  /** The value of the segment being completed, such as `A03`, not a full prefix. */
  readonly code: string;
  /** Documented by NIPOST but not sent by the live API as of October 2026. */
  readonly label: string | null;
}

export interface Autocomplete {
  /** The segment the suggestions complete. */
  readonly segment: Segment | null;
  readonly suggestions: readonly Suggestion[];
}

export interface NearestUnit {
  readonly postcode: string;
  readonly display: string;
  readonly distance_m: number | null;
  /** `high`, `medium` or `low`, graded by distance. */
  readonly confidence: string | null;
  readonly state_name: string | null;
  readonly lga_name: string | null;
  readonly locality_name: string | null;
  /** Recent house address. This and the names above need level 2. */
  readonly address: string | null;
}

export interface Reverse {
  readonly found: boolean;
  /** The queried point, echoed back. */
  readonly coordinate: Coordinate | null;
  /** The nearest building, absent when nothing is in range. */
  readonly unit: NearestUnit | null;
  readonly area: string | null;
  readonly district: string | null;
  readonly state: string | null;
  /** Set when nothing is in range. */
  readonly message: string | null;
  /** The radius the API actually applied. */
  readonly radius_m: number | null;
  /** How deep the match goes, such as `unit`. */
  readonly depth: string | null;
}

export interface NearbyUnit {
  readonly postcode: string;
  readonly display: string;
  readonly distance_m: number | null;
}

/**
 * Resolve a postcode. Levels are cumulative from 1 (validity only) to 5, and
 * the API caps the answer at the level granted to the key.
 *
 * Throws `RangeError` for a level outside 1 to 5, and `TypeError` for a code that is
 * not a `Postcode`, so that text which was never validated cannot reach a paid lookup.
 */
export function lookup(code: Postcode, level = 1): Request<Lookup> {
  if (!Postcode.is(code)) throw new TypeError("code must be a Postcode from parse()");
  if (typeof level !== "number") throw new TypeError(`level must be a number, got ${level}`);
  if (!Number.isInteger(level) || level < 1 || level > 5) {
    throw new RangeError(`level must be 1 to 5, got ${level}`);
  }
  const params = [
    ["code", code.toString()],
    ["level", String(level)],
  ] as const;
  return { path: "/v1/lookup", params, read: readLookup };
}

/**
 * Suggest completions for a partial postcode such as `EK 01 A`.
 *
 * Throws `RangeError` for an empty `partial`: the live API never answers one.
 */
export function autocomplete(partial: string): Request<Autocomplete> {
  if (typeof partial !== "string") throw new TypeError("partial must be text");
  if (!trimWhiteSpace(partial)) throw new RangeError("partial must not be empty");
  return { path: "/v1/search/autocomplete", params: [["q", partial]], read: readAutocomplete };
}

/**
 * Find the postcode of the nearest building, within 25 m unless `maxDistanceM`
 * says otherwise. The API clamps it to 250 m.
 *
 * Throws `RangeError` for a coordinate off the globe, or one or a distance that is not a
 * finite number.
 */
export function reverse(at: Coordinate, maxDistanceM?: number): Request<Reverse> {
  const params = around(at, "max_distance_m", maxDistanceM);
  return { path: "/v1/search/reverse", params, read: readReverse };
}

/**
 * List buildings around a point, nearest first, within 300 m unless `radiusM`
 * says otherwise. Empty when nothing is in range.
 *
 * Throws `RangeError` for a coordinate off the globe, or one or a radius that is not a
 * finite number.
 */
export function nearby(at: Coordinate, radiusM?: number): Request<readonly NearbyUnit[]> {
  return { path: "/v1/search/nearby", params: around(at, "radius", radiusM), read: readNearby };
}

/** Decode the response to `request` from its status and body. */
export function decode<T>(request: Request<T>, status: number, body: string): T | ApiError {
  let envelope: unknown;
  try {
    envelope = JSON.parse(body.replace(/^\uFEFF/, ""), finite);
  } catch (error) {
    return malformed(status, `not JSON: ${error instanceof Error ? error.message : error}`);
  }
  if (!isObject(envelope)) return malformed(status, "expected a JSON object");
  if (!sound(envelope, MAX_DEPTH)) {
    return malformed(status, "a lone surrogate, or nesting too deep");
  }
  const failure = envelope.error;
  if (isObject(failure)) {
    return new ApiError(
      status,
      text(failure, "code") ?? "unknown_error",
      text(failure, "message") ?? "",
    );
  }
  if (typeof failure === "string") return new ApiError(status, "unknown_error", failure);
  if (status < 200 || status >= 300) return malformed(status, "an error status without an error");
  return request.read(envelope.data) ?? malformed(status, "unexpected data");
}

type Json = Record<string, unknown>;

/** A number no float can hold parses as Infinity, which the other implementations refuse. */
function finite(_key: string, value: unknown): unknown {
  if (typeof value === "number" && !Number.isFinite(value))
    throw new RangeError("number out of range");
  return value;
}

/** Levels of nesting a body may have: what serde_json, behind the Rust crate, reads. */
const MAX_DEPTH = 127;

/** No lone surrogate in any text or key, and no more than `room` levels of nesting. */
function sound(value: unknown, room: number): boolean {
  if (typeof value === "string") return !/\p{Cs}/u.test(value);
  if (typeof value !== "object" || value === null) return true;
  const inside = Array.isArray(value) ? value : Object.entries(value).flat();
  return room > 0 && inside.every((item) => sound(item, room - 1));
}

function around(at: Coordinate, key: string, metres?: number): Array<readonly [string, string]> {
  const point: Array<readonly [string, string]> = [
    ["lat", numberText(at.lat)],
    ["lng", numberText(at.lng)],
  ];
  if (Math.abs(at.lat) > 90 || Math.abs(at.lng) > 180) {
    throw new RangeError(`coordinate is off the globe: ${at.lat}, ${at.lng}`);
  }
  if (metres === undefined) return point;
  const distance = numberText(metres);
  if (metres < 0) throw new RangeError(`distance is negative: ${metres}`);
  return [...point, [key, distance]];
}

function numberText(value: number): string {
  if (typeof value !== "number") throw new TypeError(`expected a number, got ${value}`);
  if (!Number.isFinite(value)) throw new RangeError(`expected a finite number, got ${value}`);
  return plain(String(value));
}

/** Plain decimals: `String` alone writes 1e-7, which the other implementations do not. */
function plain(text: string): string {
  const [mantissa = "", exponent] = text.split("e");
  if (exponent === undefined) return text;
  const sign = mantissa.startsWith("-") ? "-" : "";
  const [whole = "", fraction = ""] = mantissa.replace("-", "").split(".");
  const shift = Number(exponent);
  return shift < 0
    ? `${sign}0.${"0".repeat(-shift - 1)}${whole}${fraction}`
    : `${sign}${whole}${fraction}${"0".repeat(shift - fraction.length)}`;
}

function malformed(status: number, message: string): ApiError {
  return new ApiError(status, "malformed_response", message);
}

function isObject(value: unknown): value is Json {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** A unit or suggestion without its code is no answer, so it is dropped. */
function coded(key: string): (item: unknown) => item is Json {
  return (item): item is Json => isObject(item) && Boolean(text(item, key));
}

function object(data: Json, key: string): Json | null {
  const value = data[key];
  return isObject(value) ? value : null;
}

function text(data: Json, key: string): string | null {
  const value = data[key];
  return typeof value === "string" ? value : null;
}

function number(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function readNearby(data: unknown): readonly NearbyUnit[] | undefined {
  if (!Array.isArray(data)) return undefined;
  return data.filter(coded("postcode")).map((item) => ({
    postcode: text(item, "postcode") ?? "",
    display: text(item, "display") ?? "",
    distance_m: number(item.distance_m),
  }));
}

function readLookup(data: unknown): Lookup | undefined {
  if (!isObject(data) || typeof data.valid !== "boolean") return undefined;
  const admin = object(data, "administrative_address");
  const recent = object(data, "recent_house_address");
  return {
    postcode: text(data, "postcode") ?? "",
    valid: data.valid,
    status: text(data, "status"),
    verified: typeof data.verified === "boolean" ? data.verified : null,
    administrative_address: admin && {
      state_name: text(admin, "state_name"),
      lga_name: text(admin, "lga_name"),
      locality_name: text(admin, "locality_name"),
      zone: text(admin, "zone"),
    },
    recent_house_address: recent && text(recent, "recent"),
    building_use_status: text(data, "building_use_status"),
    other_building_info: data.other_building_info ?? null,
    point_geometry: data.point_geometry ?? null,
  };
}

function readAutocomplete(data: unknown): Autocomplete | undefined {
  if (!isObject(data)) return undefined;
  const items = Array.isArray(data.suggestions) ? data.suggestions : [];
  const suggestions = items.filter(coded("code")).map((item) => ({
    code: text(item, "code") ?? "",
    label: text(item, "label"),
  }));
  const segment = SEGMENTS.find((name) => name === data.segment) ?? null;
  return { segment, suggestions };
}

function readReverse(data: unknown): Reverse | undefined {
  if (!isObject(data) || typeof data.found !== "boolean") return undefined;
  const unit = [object(data, "unit")].find(coded("postcode")) ?? null;
  return {
    found: data.found,
    coordinate: readCoordinate(data.coordinate),
    unit: unit && {
      postcode: text(unit, "postcode") ?? "",
      display: text(unit, "display") ?? "",
      distance_m: number(unit.distance_m),
      confidence: text(unit, "confidence"),
      state_name: text(unit, "state_name"),
      lga_name: text(unit, "lga_name"),
      locality_name: text(unit, "locality_name"),
      address: text(unit, "address"),
    },
    area: text(data, "area"),
    district: text(data, "district"),
    state: text(data, "state"),
    message: text(data, "message"),
    radius_m: number(data.radius_m),
    depth: text(data, "depth"),
  };
}

/** The API echoes points as `[lng, lat]`. */
function readCoordinate(value: unknown): Coordinate | null {
  if (!Array.isArray(value) || value.length !== 2) return null;
  const [lng, lat] = [number(value[0]), number(value[1])];
  return lng === null || lat === null ? null : { lat, lng };
}
