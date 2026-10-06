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

export type ParseError = WrongLength | InvalidCharacter | InvalidSegment;

/** Held only here, so nothing outside this module can build a `Postcode` unchecked. */
const CHECKED: unique symbol = Symbol("checked");

/**
 * A well-formed postcode, held in its compact upper-case form.
 *
 * Well formed is not the same as assigned: only the NIPOST API knows whether a
 * code belongs to a real building. Build one with `parse`.
 */
export class Postcode {
  /** @internal Callers use `parse`: only this module holds the key. */
  constructor(
    key: typeof CHECKED,
    readonly compact: string,
  ) {
    if (key !== CHECKED) throw new TypeError("build a Postcode with parse()");
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
    return part(this.compact, segment);
  }

  /** The hyphenated code down to `through`: `prefix("area")` is `EK-01-A03-FK`. */
  prefix(through: Segment): string {
    return SEGMENTS.slice(0, SEGMENTS.indexOf(through) + 1)
      .map((segment) => this.segment(segment))
      .join("-");
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
  const kept: string[] = [];
  let index = 0;
  for (const char of text) {
    if (char !== " " && char !== "-") {
      if (!isAsciiAlphanumeric(char)) return new InvalidCharacter(char, index);
      kept.push(char);
    }
    index += 1;
  }
  if (kept.length !== LENGTH) return new WrongLength(kept.length);
  return kept.join("").toUpperCase();
}

function part(compact: string, segment: Segment): string {
  const [start, end] = SPANS[segment];
  return compact.slice(start, end);
}

function validate(compact: string): InvalidSegment | undefined {
  const bad = SEGMENTS.find((segment) => !accepts(segment, part(compact, segment)));
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
  const text = trimWhiteSpace(value);
  const [start, end] = SPANS[segment];
  const width = end - start;
  const shortest = NUMERIC.has(segment) ? 1 : width;
  const fits = text.length >= shortest && text.length <= width && /^[A-Za-z0-9]+$/.test(text);
  return fits ? text.padStart(width, "0") : new InvalidSegment(segment);
}
