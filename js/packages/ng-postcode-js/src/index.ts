/**
 * Nigeria's National Digital Alphanumeric Postcode (NDAPS), the building-level
 * postcode issued by NIPOST.
 *
 * Expected failures come back as values, never exceptions:
 *
 * ```ts
 * import { Postcode, parse } from "ng-postcode-js";
 *
 * const code = parse("ek 01 a03 fk 01");
 * if (code instanceof Postcode) {
 *   console.log(String(code), code.compact); // EK-01-A03-FK-01 EK01A03FK01
 * } else {
 *   console.log(String(code)); // e.g. "invalid lga segment"
 * }
 * ```
 */

export {
  type Corrected,
  fromSegments,
  InvalidCharacter,
  InvalidSegment,
  isValid,
  LENGTH,
  type ParseError,
  Postcode,
  Prefix,
  parse,
  parseLenient,
  parsePrefix,
  SEGMENTS,
  type Segment,
  WrongLength,
  WrongPrefixLength,
} from "./postcode.js";
