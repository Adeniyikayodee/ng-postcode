package io.github.adeniyikayodee.ngpostcode;

/** The five segments of a postcode, {@code AA-99-H77-BB-55}, widest first. */
public enum Segment {
    STATE(0, 2),
    LGA(2, 4),
    DISTRICT(4, 7),
    AREA(7, 9),
    UNIT(9, 11);

    final int start;
    final int end;

    Segment(int start, int end) {
        this.start = start;
        this.end = end;
    }

    /** The lower-case name the API uses, such as {@code lga}. */
    @Override
    public String toString() {
        return name().toLowerCase(java.util.Locale.ROOT);
    }
}
