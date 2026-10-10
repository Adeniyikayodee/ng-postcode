package io.github.adeniyikayodee.ngpostcode;

/** Why a string is not a well-formed postcode. */
public sealed interface ParseError extends Parsed, Lenient, ParsedPrefix {

    /** The input did not hold exactly 11 letters and digits. */
    record WrongLength(int found) implements ParseError {
        @Override
        public String toString() {
            return "expected " + Postcode.LENGTH + " letters and digits, found " + found;
        }
    }

    /** The input did not end where a segment does: after 2, 4, 7, 9 or 11 letters and digits. */
    record WrongPrefixLength(int found) implements ParseError {
        @Override
        public String toString() {
            return "expected 2, 4, 7, 9 or 11 letters and digits, found " + found;
        }
    }

    /**
     * The input held something other than letters, digits, spaces and hyphens.
     *
     * @param index counted in characters, not UTF-16 units
     */
    record InvalidCharacter(String character, int index) implements ParseError {
        @Override
        public String toString() {
            return "invalid character '" + character + "' at index " + index;
        }
    }

    /** A segment has the wrong shape, such as digits in the state or {@code 00} as a unit. */
    record InvalidSegment(Segment segment) implements ParseError {
        @Override
        public String toString() {
            return "invalid " + segment + " segment";
        }
    }
}
