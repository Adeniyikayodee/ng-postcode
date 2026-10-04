package io.github.adeniyikayodee.ngpostcode.api;

/**
 * @param confidence {@code high}, {@code medium} or {@code low}, graded by distance
 * @param address recent house address; this and the three names need level 2
 */
public record NearestUnit(
        String postcode,
        String display,
        Double distanceM,
        String confidence,
        String stateName,
        String lgaName,
        String localityName,
        String address) {}
