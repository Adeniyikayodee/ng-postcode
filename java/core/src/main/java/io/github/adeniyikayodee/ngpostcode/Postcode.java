package io.github.adeniyikayodee.ngpostcode;

import io.github.adeniyikayodee.ngpostcode.ParseError.InvalidCharacter;
import io.github.adeniyikayodee.ngpostcode.ParseError.InvalidSegment;
import io.github.adeniyikayodee.ngpostcode.ParseError.WrongLength;
import java.util.Arrays;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * A well-formed postcode, held in its compact upper-case form.
 *
 * <p>Well formed is not the same as assigned: only the NIPOST API knows whether a code belongs
 * to a real building. Build one with {@link #parse}; constructing it from an unchecked string
 * throws, as that is a programming error.
 */
public record Postcode(String compact) implements Parsed, Comparable<Postcode> {

    public static final int LENGTH = 11;

    private static final Map<Character, Character> TO_LETTER = Map.of('0', 'O', '1', 'I', '5', 'S', '8', 'B');
    private static final Map<Character, Character> TO_DIGIT =
            Map.of('O', '0', 'I', '1', 'L', '1', 'S', '5', 'B', '8');

    public Postcode {
        var kept = new StringBuilder();
        if (collect(compact, kept) != null || validate(kept) != null || !compact.contentEquals(kept)) {
            throw new IllegalArgumentException("not a compact upper-case postcode: " + compact);
        }
    }

    /** Parses a hyphenated, spaced or compact code in either case. */
    public static Parsed parse(String text) {
        var kept = new StringBuilder();
        ParseError error = collect(text, kept);
        if (error == null) {
            error = validate(kept);
        }
        return error != null ? error : new Postcode(kept.toString());
    }

    /**
     * Parses after swapping look-alikes that cannot occur where they stand: {@code 0 1 5 8}
     * become {@code O I S B} where a letter is required, and {@code O I L S B} become
     * {@code 0 1 1 5 8} where a digit is. The district allows both, so it is never rewritten.
     *
     * <p>The result is well formed but may not be the code the user meant, so confirm it with
     * them when {@code corrections} is not zero.
     */
    public static Lenient parseLenient(String text) {
        var raw = new StringBuilder();
        ParseError error = collect(text, raw);
        if (error != null) {
            return error;
        }
        var fixed = new StringBuilder(raw);
        int corrections = 0;
        for (Segment segment : Segment.values()) {
            Map<Character, Character> table = switch (segment) {
                case STATE, AREA -> TO_LETTER;
                case LGA, UNIT -> TO_DIGIT;
                case DISTRICT -> Map.of();
            };
            for (int i = segment.start; i < segment.end; i++) {
                Character swap = table.get(raw.charAt(i));
                if (swap != null) {
                    fixed.setCharAt(i, swap);
                    corrections++;
                }
            }
        }
        error = validate(fixed);
        return error != null ? error : new Corrected(new Postcode(fixed.toString()), corrections);
    }

    /** Builds a code from its segments, zero-filling the LGA and unit so {@code "1"} is {@code "01"}. */
    public static Parsed fromSegments(String state, String lga, String district, String area, String unit) {
        String[] values = {state, lga, district, area, unit};
        var joined = new StringBuilder();
        for (Segment segment : Segment.values()) {
            String text = trimmed(values[segment.ordinal()]);
            int width = segment.end - segment.start;
            int shortest = segment == Segment.LGA || segment == Segment.UNIT ? 1 : width;
            if (text.length() < shortest || text.length() > width || !text.chars().allMatch(Postcode::isAlphanumeric)) {
                return new InvalidSegment(segment);
            }
            joined.append("0".repeat(width - text.length())).append(text);
        }
        return parse(joined.toString());
    }

    /** Whether {@code text} is a well-formed postcode. */
    public static boolean isValid(String text) {
        return parse(text) instanceof Postcode;
    }

    /** The canonical hyphenated form, {@code EK-01-A03-FK-01}. */
    @Override
    public String toString() {
        return prefix(Segment.UNIT);
    }

    /** The form shown to people, {@code EK 01 A03 FK 01}. */
    public String spaced() {
        return joined(Segment.UNIT, " ");
    }

    public String state() {
        return segment(Segment.STATE);
    }

    public String lga() {
        return segment(Segment.LGA);
    }

    public String district() {
        return segment(Segment.DISTRICT);
    }

    public String area() {
        return segment(Segment.AREA);
    }

    public String unit() {
        return segment(Segment.UNIT);
    }

    public String segment(Segment segment) {
        return compact.substring(segment.start, segment.end);
    }

    /** The hyphenated code down to {@code through}: {@code prefix(AREA)} is {@code EK-01-A03-FK}. */
    public String prefix(Segment through) {
        return joined(through, "-");
    }

    /**
     * The code cut off after {@code through}, as a value: {@code truncate(AREA)} is the area this
     * building is in.
     */
    public Prefix truncate(Segment through) {
        return new Prefix(compact.substring(0, through.end));
    }

    @Override
    public int compareTo(Postcode other) {
        return compact.compareTo(other.compact);
    }

    private String joined(Segment through, String separator) {
        return Arrays.stream(Segment.values())
                .limit(through.ordinal() + 1)
                .map(this::segment)
                .collect(Collectors.joining(separator));
    }

    /** Fills {@code kept} with the upper-case letters and digits, or says what stopped it. */
    private static ParseError collect(String text, StringBuilder kept) {
        Scan scan = scan(text);
        kept.append(scan.kept());
        if (scan.error() != null) {
            return scan.error();
        }
        return scan.found() == LENGTH ? null : new WrongLength(scan.found());
    }

    /** The upper-case letters and digits of a text and how many there were, or what stopped it. */
    record Scan(String kept, int found, InvalidCharacter error) {}

    static Scan scan(String text) {
        // Every character is checked, but no more than a postcode's worth is held.
        var kept = new StringBuilder();
        int found = 0;
        int index = 0;
        for (int at = 0; at < text.length(); index++) {
            int point = text.codePointAt(at);
            at += Character.charCount(point);
            if (point == ' ' || point == '-') {
                continue;
            }
            if (!isAlphanumeric(point)) {
                return new Scan(kept.toString(), found, new InvalidCharacter(Character.toString(point), index));
            }
            if (found++ < LENGTH) {
                // ASCII arithmetic, so no locale can change the result.
                kept.append((char) (point >= 'a' ? point - 32 : point));
            }
        }
        return new Scan(kept.toString(), found, null);
    }

    private static ParseError validate(CharSequence compact) {
        return validate(compact, Segment.UNIT);
    }

    static ParseError validate(CharSequence compact, Segment through) {
        for (Segment segment : Arrays.copyOf(Segment.values(), through.ordinal() + 1)) {
            CharSequence part = compact.subSequence(segment.start, segment.end);
            boolean accepted = switch (segment) {
                case STATE, AREA -> part.chars().allMatch(Postcode::isUpper);
                // 00 is never issued.
                case LGA, UNIT -> part.chars().allMatch(Postcode::isDigit) && !"00".contentEquals(part);
                case DISTRICT -> true;
            };
            if (!accepted) {
                return new InvalidSegment(segment);
            }
        }
        return null;
    }

    /** Trims Unicode White_Space, as the other implementations do: strip() keeps a no-break space. */
    private static String trimmed(String text) {
        int start = 0;
        int end = text.length();
        while (start < end && isWhiteSpace(text.charAt(start))) {
            start++;
        }
        while (end > start && isWhiteSpace(text.charAt(end - 1))) {
            end--;
        }
        return text.substring(start, end);
    }

    private static boolean isWhiteSpace(int c) {
        return Character.isSpaceChar(c) || (c >= '\t' && c <= '\r') || c == 0x85;
    }

    // Explicit ranges: Character.isDigit and isLetter also accept non-ASCII scripts.
    private static boolean isDigit(int c) {
        return c >= '0' && c <= '9';
    }

    private static boolean isUpper(int c) {
        return c >= 'A' && c <= 'Z';
    }

    private static boolean isAlphanumeric(int c) {
        return isDigit(c) || isUpper(c) || (c >= 'a' && c <= 'z');
    }
}
