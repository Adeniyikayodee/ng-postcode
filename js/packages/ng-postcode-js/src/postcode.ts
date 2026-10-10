/** Offline parsing, validation and formatting. Pure: no I/O, no mutation. */

export const LENGTH = 11;

/** The five segments of a postcode, `AA-99-H77-BB-55`, widest first. */
export const SEGMENTS = ["state", "lga", "district", "area", "unit"] as const;
export type Segment = (typeof SEGMENTS)[number];

const SPANS: Record<Segment, readonly [number, number]> = {
  state: [0, 2],
  lga: [2, 4],
  district: [4, 7],
  area: [7, 9],
  unit: [9, 11],
};
const ALPHA: ReadonlySet<Segment> = new Set(["state", "area"]);
const NUMERIC: ReadonlySet<Segment> = new Set(["lga", "unit"]);
const TO_LETTER: Record<string, string> = { "0": "O", "1": "I", "5": "S", "8": "B" };
const TO_DIGIT: Record<string, string> = { O: "0", I: "1", L: "1", S: "5", B: "8" };

/** The input did not hold exactly 11 letters and digits. */
export class WrongLength {
  constructor(readonly found: number) {}

  toString(): string {
    return `expected ${LENGTH} letters and digits, found ${this.found}`;
  }
}

/** The input did not end where a segment does: after 2, 4, 7, 9 or 11 letters and digits. */
export class WrongPrefixLength {
  constructor(readonly found: number) {}

  toString(): string {
    return `expected 2, 4, 7, 9 or 11 letters and digits, found ${this.found}`;
  }
}

/** The input held something other than letters, digits, spaces and hyphens. */
export class InvalidCharacter {
  constructor(
    readonly char: string,
    readonly index: number,
  ) {}

  toString(): string {
    return `invalid character '${this.char}' at index ${this.index}`;
  }
}

/** A segment has the wrong shape, such as digits in the state or `00` as a unit. */
export class InvalidSegment {
  constructor(readonly segment: Segment) {}

  toString(): string {
    return `invalid ${this.segment} segment`;
  }
}

export type ParseError = WrongLength | WrongPrefixLength | InvalidCharacter | InvalidSegment;

/** Held only here, so nothing outside this module can build a `Postcode` unchecked. */
const CHECKED: unique symbol = Symbol("checked");

/**
 * A well-formed postcode, held in its compact upper-case form.
 *
 * Well formed is not the same as assigned: only the NIPOST API knows whether a
 * code belongs to a real building. Build one with `parse`.
 */
export class Postcode {
  // Private and frozen, so no assignment can put unchecked text in a request.
  readonly #compact: string;

  /** @internal Callers use `parse`: only this module holds the key. */
  constructor(key: typeof CHECKED, compact: string) {
    if (key !== CHECKED) throw new TypeError("build a Postcode with parse()");
    this.#compact = compact;
    Object.freeze(this);
  }

  /** Whether `value` came from `parse`. A look-alike object does not pass, as it does `instanceof`. */
  static is(value: unknown): value is Postcode {
    return typeof value === "object" && value !== null && #compact in value;
  }

  /** The form to store and compare, `EK01A03FK01`. */
  get compact(): string {
    return this.#compact;
  }

  /** The canonical hyphenated form, `EK-01-A03-FK-01`. */
  toString(): string {
    return this.prefix("unit");
  }

  toJSON(): string {
    return this.toString();
  }

  /** The form shown to people, `EK 01 A03 FK 01`. */
  get spaced(): string {
    return SEGMENTS.map((segment) => this.segment(segment)).join(" ");
  }

  get state(): string {
    return this.segment("state");
  }

  get lga(): string {
    return this.segment("lga");
  }

  get district(): string {
    return this.segment("district");
  }

  get area(): string {
    return this.segment("area");
  }

  get unit(): string {
    return this.segment("unit");
  }

  segment(segment: Segment): string {
    return part(this.compact, known(segment));
  }

  /** The hyphenated code down to `through`: `prefix("area")` is `EK-01-A03-FK`. */
  prefix(through: Segment): string {
    return String(this.truncate(through));
  }

  /** The code cut off after `through`, as a value: `truncate("area")` is the area this building is in. */
  truncate(through: Segment): Prefix {
    return new Prefix(CHECKED, this.compact.slice(0, SPANS[known(through)][1]));
  }
}

/**
 * A postcode cut off after one of its segments, such as the district `EK-01-A03`.
 *
 * It names every code that starts with it, so it serves to group or select codes by
 * state, LGA, district or area. A whole code is the narrowest prefix. Build one with
 * `parsePrefix` or `Postcode.truncate`.
 */
export class Prefix {
  readonly #compact: string;

  /** @internal Callers use `parsePrefix`: only this module holds the key. */
  constructor(key: typeof CHECKED, compact: string) {
    if (key !== CHECKED) throw new TypeError("build a Prefix with parsePrefix()");
    this.#compact = compact;
    Object.freeze(this);
  }

  /** Whether `value` came from `parsePrefix` or `truncate`. */
  static is(value: unknown): value is Prefix {
    return typeof value === "object" && value !== null && #compact in value;
  }

  /** The form to store and compare, `EK01A03`. */
  get compact(): string {
    return this.#compact;
  }

  /** The last segment the prefix holds. */
  get through(): Segment {
    return SEGMENTS.find((segment) => SPANS[segment][1] === this.#compact.length) as Segment;
  }

  /** The prefix one segment shorter, or null for a state. */
  get parent(): Prefix | null {
    const wider = SEGMENTS[SEGMENTS.indexOf(this.through) - 1];
    return wider ? new Prefix(CHECKED, this.#compact.slice(0, SPANS[wider][1])) : null;
  }

  /** Whether `code` starts with this prefix. */
  contains(code: Postcode): boolean {
    return code.compact.startsWith(this.#compact);
  }

  /** The hyphenated form, `EK-01-A03`. */
  toString(): string {
    return SEGMENTS.slice(0, SEGMENTS.indexOf(this.through) + 1)
      .map((segment) => part(this.#compact, segment))
      .join("-");
  }

  toJSON(): string {
    return this.toString();
  }
}

/** The result of `parseLenient`. */
export interface Corrected {
  readonly postcode: Postcode;
  /** How many characters were swapped for their look-alike. */
  readonly corrections: number;
}

/** Parse a hyphenated, spaced or compact code in either case. */
export function parse(text: string): Postcode | ParseError {
  const compact = collect(text);
  if (typeof compact !== "string") return compact;
  return validate(compact) ?? new Postcode(CHECKED, compact);
}

/**
 * Parse after swapping look-alikes that cannot occur where they stand: `0 1 5 8`
 * become `O I S B` where a letter is required, and `O I L S B` become `0 1 1 5 8`
 * where a digit is. The district allows both, so it is never rewritten.
 *
 * The result is well formed but may not be the code the user meant, so confirm
 * it with them when `corrections` is not zero.
 */
export function parseLenient(text: string): Corrected | ParseError {
  const raw = collect(text);
  if (typeof raw !== "string") return raw;
  const fixed = SEGMENTS.map((segment) => unconfuse(segment, part(raw, segment))).join("");
  const error = validate(fixed);
  if (error) return error;
  const corrections = [...raw].filter((char, index) => char !== fixed[index]).length;
  return { postcode: new Postcode(CHECKED, fixed), corrections };
}

/** Parse a hyphenated, spaced or compact prefix in either case. */
export function parsePrefix(text: string): Prefix | ParseError {
  const scanned = scan(text);
  if (scanned instanceof InvalidCharacter) return scanned;
  const [compact, found] = scanned;
  const through = SEGMENTS.find((segment) => SPANS[segment][1] === found);
  if (!through) return new WrongPrefixLength(found);
  return validate(compact, through) ?? new Prefix(CHECKED, compact);
}

/** Build a code from its segments, zero-filling the LGA and unit. */
export function fromSegments(
  state: string,
  lga: string,
  district: string,
  area: string,
  unit: string,
): Postcode | ParseError {
  const values = [state, lga, district, area, unit];
  const padded = SEGMENTS.map((segment, index) => pad(segment, values[index] ?? ""));
  const error = padded.find((value) => value instanceof InvalidSegment);
  if (error instanceof InvalidSegment) return error;
  return parse(padded.join(""));
}

/** Whether `text` is a well-formed postcode. */
export function isValid(text: string): boolean {
  return parse(text) instanceof Postcode;
}

const WHITE_SPACE = "\\t-\\r \\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000";
const EDGES = new RegExp(`^[${WHITE_SPACE}]+|[${WHITE_SPACE}]+$`, "g");

/**
 * Trim Unicode White_Space, which every implementation trims. `trim()` alone skips
 * U+0085 and removes U+FEFF, which the others keep.
 */
export function trimWhiteSpace(text: string): string {
  return text.replace(EDGES, "");
}

function isAsciiAlphanumeric(char: string): boolean {
  return /^[A-Za-z0-9]$/.test(char);
}

function collect(text: string): string | ParseError {
  const scanned = scan(text);
  if (scanned instanceof InvalidCharacter) return scanned;
  const [compact, found] = scanned;
  return found === LENGTH ? compact : new WrongLength(found);
}

/** The letters and digits of `text` in upper case, and how many there were. */
function scan(text: string): [string, number] | InvalidCharacter {
  // Every character is checked, but no more than a postcode's worth is held.
  let kept = "";
  let found = 0;
  let index = 0;
  for (const char of text) {
    if (char !== " " && char !== "-") {
      if (!isAsciiAlphanumeric(char)) return new InvalidCharacter(char, index);
      if (found < LENGTH) kept += char;
      found += 1;
    }
    index += 1;
  }
  return [kept.toUpperCase(), found];
}

/** Untyped callers can pass any name: "Area" would otherwise give an empty prefix. */
function known(segment: Segment): Segment {
  if (!SEGMENTS.includes(segment)) throw new TypeError(`unknown segment: ${segment}`);
  return segment;
}

function part(compact: string, segment: Segment): string {
  const [start, end] = SPANS[segment];
  return compact.slice(start, end);
}

function validate(compact: string, through: Segment = "unit"): InvalidSegment | undefined {
  const bad = SEGMENTS.slice(0, SEGMENTS.indexOf(through) + 1).find(
    (segment) => !accepts(segment, part(compact, segment)),
  );
  return bad ? new InvalidSegment(bad) : undefined;
}

function accepts(segment: Segment, text: string): boolean {
  if (ALPHA.has(segment)) return /^[A-Z]*$/.test(text);
  if (NUMERIC.has(segment)) return /^[0-9]*$/.test(text) && text !== "00";
  return /^[A-Z0-9]*$/.test(text);
}

function unconfuse(segment: Segment, text: string): string {
  const table = ALPHA.has(segment) ? TO_LETTER : NUMERIC.has(segment) ? TO_DIGIT : {};
  return [...text].map((char) => table[char] ?? char).join("");
}

function pad(segment: Segment, value: string): string | InvalidSegment {
  if (typeof value !== "string") return new InvalidSegment(segment);
  const text = trimWhiteSpace(value);
  const [start, end] = SPANS[segment];
  const width = end - start;
  const shortest = NUMERIC.has(segment) ? 1 : width;
  const fits = text.length >= shortest && text.length <= width && /^[A-Za-z0-9]+$/.test(text);
  return fits ? text.padStart(width, "0") : new InvalidSegment(segment);
}
