package io.github.adeniyikayodee.ngpostcode.api;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.adeniyikayodee.ngpostcode.Postcode;
import io.github.adeniyikayodee.ngpostcode.Segment;
import io.github.adeniyikayodee.ngpostcode.api.Failure.ApiError;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

/**
 * The NIPOST Postcode API as plain data: requests to send and responses to decode.
 *
 * <p>Nothing here performs I/O, so it works with any HTTP client. Assembly and disassembly are
 * not modelled: {@link Postcode} does both offline.
 */
public final class Api {

    public static final String BASE_URL = "https://api.postcode.gov.ng";

    // Responses are read as a tree and checked by hand: data binding would turn a missing
    // boolean into false, and a renamed field into "not assigned".
    private static final ObjectMapper JSON =
            new ObjectMapper().enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS);

    private Api() {}

    /**
     * Resolves a postcode. Levels are cumulative from 1 (validity only) to 5, and the API caps
     * the answer at the level granted to the key.
     *
     * @throws IllegalArgumentException for a level outside 1 to 5
     */
    public static Request<Lookup> lookup(Postcode code, int level) {
        if (level < 1 || level > 5) {
            throw new IllegalArgumentException("level must be 1 to 5, got " + level);
        }
        var query = List.of(Map.entry("code", code.toString()), Map.entry("level", String.valueOf(level)));
        return new Request<>("/v1/lookup", query, Api::readLookup);
    }

    /** A level 1 lookup: validity only. */
    public static Request<Lookup> lookup(Postcode code) {
        return lookup(code, 1);
    }

    /**
     * Suggests completions for a partial postcode such as {@code EK 01 A}.
     *
     * @throws IllegalArgumentException for a blank {@code partial}: the live API never answers one
     */
    public static Request<Autocomplete> autocomplete(String partial) {
        // Unicode White_Space, as the other implementations trim: isBlank() keeps a no-break space.
        if (partial.chars().allMatch(c -> Character.isSpaceChar(c) || (c >= '\t' && c <= '\r') || c == 0x85)) {
            throw new IllegalArgumentException("partial must not be empty");
        }
        return new Request<>("/v1/search/autocomplete", List.of(Map.entry("q", partial)), Api::readAutocomplete);
    }

    /**
     * Finds the postcode of the nearest building, within 25 m unless {@code maxDistanceM} says
     * otherwise. The API clamps it to 250 m.
     *
     * @param maxDistanceM may be {@code null}
     * @throws IllegalArgumentException for a coordinate or distance that is not a finite number
     */
    public static Request<Reverse> reverse(Coordinate at, Double maxDistanceM) {
        return new Request<>("/v1/search/reverse", around(at, "max_distance_m", maxDistanceM), Api::readReverse);
    }

    public static Request<Reverse> reverse(Coordinate at) {
        return reverse(at, null);
    }

    /**
     * Lists buildings around a point, nearest first, within 300 m unless {@code radiusM} says
     * otherwise. Empty when nothing is in range.
     *
     * @param radiusM may be {@code null}
     * @throws IllegalArgumentException for a coordinate or radius that is not a finite number
     */
    public static Request<List<NearbyUnit>> nearby(Coordinate at, Double radiusM) {
        return new Request<>("/v1/search/nearby", around(at, "radius", radiusM), Api::readNearby);
    }

    public static Request<List<NearbyUnit>> nearby(Coordinate at) {
        return nearby(at, null);
    }

    /** Decodes the response to {@code request} from its status and body. */
    public static <T> Result<T> decode(Request<T> request, int status, String body) {
        JsonNode envelope;
        try {
            envelope = JSON.readTree(body);
        } catch (JsonProcessingException error) {
            return malformed(status, "not JSON: " + error.getOriginalMessage());
        }
        if (!envelope.isObject()) {
            return malformed(status, "expected a JSON object");
        }
        JsonNode failure = envelope.path("error");
        if (failure.isObject()) {
            String code = text(failure, "code");
            String message = text(failure, "message");
            return failed(status, code != null ? code : "unknown_error", message != null ? message : "");
        }
        if (failure.isTextual()) {
            return failed(status, "unknown_error", failure.textValue());
        }
        if (status < 200 || status >= 300) {
            return malformed(status, "an error status without an error");
        }
        T data = request.read.apply(envelope.path("data"));
        return data != null ? new Result.Ok<>(data) : malformed(status, "unexpected data");
    }

    private static List<Map.Entry<String, String>> around(Coordinate at, String key, Double metres) {
        var query = new ArrayList<>(List.of(Map.entry("lat", numberText(at.lat())), Map.entry("lng", numberText(at.lng()))));
        if (metres != null) {
            query.add(Map.entry(key, numberText(metres)));
        }
        return query;
    }

    /** Plain decimals, as the other implementations write them: 100, 0.0000001, never 1.0E-7. */
    private static String numberText(double value) {
        if (!Double.isFinite(value)) {
            throw new IllegalArgumentException("expected a finite number, got " + value);
        }
        return new BigDecimal(Double.toString(value)).stripTrailingZeros().toPlainString();
    }

    private static <T> Result<T> failed(int status, String code, String message) {
        return new Result.Failed<>(new ApiError(status, code, message));
    }

    private static <T> Result<T> malformed(int status, String message) {
        return failed(status, "malformed_response", message);
    }

    private static String text(JsonNode data, String key) {
        return data.path(key).textValue();
    }

    private static String textOrEmpty(JsonNode data, String key) {
        String value = text(data, key);
        return value != null ? value : "";
    }

    private static Double number(JsonNode value) {
        return value.isNumber() ? value.doubleValue() : null;
    }

    /** Undocumented fields, as maps, lists, strings and numbers. */
    private static Object raw(JsonNode value) {
        return value.isMissingNode() || value.isNull() ? null : JSON.convertValue(value, Object.class);
    }

    private static Lookup readLookup(JsonNode data) {
        if (!data.path("valid").isBoolean()) {
            return null;
        }
        JsonNode admin = data.path("administrative_address");
        return new Lookup(
                textOrEmpty(data, "postcode"),
                data.path("valid").booleanValue(),
                admin.isObject()
                        ? new AdministrativeAddress(
                                text(admin, "state_name"),
                                text(admin, "lga_name"),
                                text(admin, "locality_name"),
                                text(admin, "zone"))
                        : null,
                text(data.path("recent_house_address"), "recent"),
                text(data, "building_use_status"),
                raw(data.path("other_building_info")),
                raw(data.path("point_geometry")),
                text(data, "status"),
                data.path("verified").isBoolean() ? data.path("verified").booleanValue() : null);
    }

    private static Autocomplete readAutocomplete(JsonNode data) {
        if (!data.isObject()) {
            return null;
        }
        var suggestions = new ArrayList<Suggestion>();
        JsonNode items = data.path("suggestions");
        // Only a list: iterating an object would read its values as suggestions.
        for (JsonNode item : items.isArray() ? items : JSON.createArrayNode()) {
            if (item.isObject()) {
                suggestions.add(new Suggestion(textOrEmpty(item, "code"), text(item, "label")));
            }
        }
        String name = text(data, "segment");
        Segment segment = Arrays.stream(Segment.values())
                .filter(s -> s.toString().equals(name))
                .findFirst()
                .orElse(null);
        return new Autocomplete(segment, List.copyOf(suggestions));
    }

    private static Reverse readReverse(JsonNode data) {
        if (!data.path("found").isBoolean()) {
            return null;
        }
        JsonNode unit = data.path("unit");
        return new Reverse(
                data.path("found").booleanValue(),
                readCoordinate(data.path("coordinate")),
                unit.isObject()
                        ? new NearestUnit(
                                textOrEmpty(unit, "postcode"),
                                textOrEmpty(unit, "display"),
                                number(unit.path("distance_m")),
                                text(unit, "confidence"),
                                text(unit, "state_name"),
                                text(unit, "lga_name"),
                                text(unit, "locality_name"),
                                text(unit, "address"))
                        : null,
                text(data, "area"),
                text(data, "district"),
                text(data, "state"),
                text(data, "message"),
                number(data.path("radius_m")),
                text(data, "depth"));
    }

    /** The API echoes points as {@code [lng, lat]}. */
    private static Coordinate readCoordinate(JsonNode value) {
        if (!value.isArray() || value.size() != 2) {
            return null;
        }
        Double lng = number(value.get(0));
        Double lat = number(value.get(1));
        return lng == null || lat == null ? null : new Coordinate(lat, lng);
    }

    private static List<NearbyUnit> readNearby(JsonNode data) {
        if (!data.isArray()) {
            return null;
        }
        var units = new ArrayList<NearbyUnit>();
        for (JsonNode item : data) {
            if (item.isObject()) {
                units.add(new NearbyUnit(
                        textOrEmpty(item, "postcode"), textOrEmpty(item, "display"), number(item.path("distance_m"))));
            }
        }
        return List.copyOf(units);
    }
}
