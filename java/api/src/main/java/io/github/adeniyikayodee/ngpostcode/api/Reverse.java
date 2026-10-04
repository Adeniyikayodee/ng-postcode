package io.github.adeniyikayodee.ngpostcode.api;

/**
 * @param coordinate the queried point, echoed back
 * @param unit the nearest building, {@code null} when nothing is in range
 * @param message set when nothing is in range
 * @param radiusM the radius the API actually applied
 * @param depth how deep the match goes, such as {@code unit}
 */
public record Reverse(
        boolean found,
        Coordinate coordinate,
        NearestUnit unit,
        String area,
        String district,
        String state,
        String message,
        Double radiusM,
        String depth) {}
