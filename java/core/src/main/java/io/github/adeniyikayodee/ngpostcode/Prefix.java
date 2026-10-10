package io.github.adeniyikayodee.ngpostcode;

import io.github.adeniyikayodee.ngpostcode.ParseError.WrongPrefixLength;
import java.util.Arrays;
import java.util.Optional;
import java.util.stream.Collectors;

/**
 * A postcode cut off after one of its segments, such as the district {@code EK-01-A03}.
 *
 * <p>It names every code that starts with it, so it serves to group or select codes by state,
 * LGA, district or area. A whole code is the narrowest prefix. Build one with {@link #parse} or
 * {@link Postcode#truncate}; constructing it from an unchecked string throws.
 */
public record Prefix(String compact) implements ParsedPrefix, Comparable<Prefix> {

    public Prefix {
        Postcode.Scan scan = Postcode.scan(compact);
        Segment through = ending(scan.found());
        boolean clean = scan.error() == null && through != null && compact.equals(scan.kept());
        if (!clean || Postcode.validate(compact, through) != null) {
            throw new IllegalArgumentException("not a compact upper-case prefix: " + compact);
        }
    }

    /** Parses a hyphenated, spaced or compact prefix in either case. */
    public static ParsedPrefix parse(String text) {
        Postcode.Scan scan = Postcode.scan(text);
        if (scan.error() != null) {
            return scan.error();
        }
        Segment through = ending(scan.found());
        if (through == null) {
            return new WrongPrefixLength(scan.found());
        }
        ParseError error = Postcode.validate(scan.kept(), through);
        return error != null ? error : new Prefix(scan.kept());
    }

    /** The last segment the prefix holds. */
    public Segment through() {
        return ending(compact.length());
    }

    /** The prefix one segment shorter, or empty for a state. */
    public Optional<Prefix> parent() {
        int wider = through().ordinal() - 1;
        return wider < 0
                ? Optional.empty()
                : Optional.of(new Prefix(compact.substring(0, Segment.values()[wider].end)));
    }

    /** Whether {@code code} starts with this prefix. */
    public boolean contains(Postcode code) {
        return code.compact().startsWith(compact);
    }

    /** The hyphenated form, {@code EK-01-A03}. */
    @Override
    public String toString() {
        return Arrays.stream(Segment.values())
                .limit(through().ordinal() + 1)
                .map(segment -> compact.substring(segment.start, segment.end))
                .collect(Collectors.joining("-"));
    }

    /** By compact form, so a prefix sorts just before the codes it contains. */
    @Override
    public int compareTo(Prefix other) {
        return compact.compareTo(other.compact);
    }

    private static Segment ending(int length) {
        return Arrays.stream(Segment.values())
                .filter(segment -> segment.end == length)
                .findFirst()
                .orElse(null);
    }
}
