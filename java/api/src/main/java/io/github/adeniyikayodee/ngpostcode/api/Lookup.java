package io.github.adeniyikayodee.ngpostcode.api;

/**
 * Fields above the level granted to the key are {@code null}.
 *
 * @param administrativeAddress level 2
 * @param recentHouseAddress level 2
 * @param buildingUseStatus level 3
 * @param otherBuildingInfo level 4; undocumented, so left as maps, lists, strings and numbers
 * @param pointGeometry level 5; undocumented, so left as maps, lists, strings and numbers
 * @param status {@code valid}, {@code not_found}, or {@code invalid} for a malformed code
 */
public record Lookup(
        String postcode,
        boolean valid,
        AdministrativeAddress administrativeAddress,
        String recentHouseAddress,
        String buildingUseStatus,
        Object otherBuildingInfo,
        Object pointGeometry,
        String status,
        Boolean verified) {}
