package io.github.adeniyikayodee.ngpostcode;

/**
 * A code parsed after swapping look-alike characters.
 *
 * @param corrections how many characters were swapped for their look-alike
 */
public record Corrected(Postcode postcode, int corrections) implements Lenient {}
