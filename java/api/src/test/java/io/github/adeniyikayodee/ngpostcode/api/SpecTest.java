package io.github.adeniyikayodee.ngpostcode.api;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;
import static org.junit.jupiter.api.DynamicTest.dynamicTest;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.adeniyikayodee.ngpostcode.Postcode;
import io.github.adeniyikayodee.ngpostcode.Segment;
import io.github.adeniyikayodee.ngpostcode.api.Failure.ApiError;
import java.io.IOException;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;
import java.util.stream.StreamSupport;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestFactory;

/** Runs the shared cases in {@code spec/}: requests, captured live responses and tolerance. */
class SpecTest {

    private static final ObjectMapper JSON = new ObjectMapper();
    private static final Postcode CODE = new Postcode("FC03B06AG12");
    private static final Coordinate HERE = new Coordinate(7.6211, 5.2214);
    private static final JsonNode LIVE = spec("responses");

    private static JsonNode spec(String name) {
        try {
            return JSON.readTree(Path.of("..", "..", "spec", name + ".json").toFile());
        } catch (IOException error) {
            throw new IllegalStateException(error);
        }
    }

    private static Stream<JsonNode> cases(String name) {
        return StreamSupport.stream(spec(name).get("cases").spliterator(), false);
    }

    /** Numbers that JSON cannot hold are written as text. */
    private static double number(JsonNode value) {
        return switch (value.asText()) {
            case "nan" -> Double.NaN;
            case "inf" -> Double.POSITIVE_INFINITY;
            case "-inf" -> Double.NEGATIVE_INFINITY;
            default -> value.doubleValue();
        };
    }

    private static Request<?> build(String kind, JsonNode args) {
        if (kind.equals("lookup")) {
            return Api.lookup(new Postcode(args.get("code").asText()), args.get("level").intValue());
        }
        if (kind.equals("autocomplete")) {
            return Api.autocomplete(args.get("q").asText());
        }
        var at = new Coordinate(number(args.get("lat")), number(args.get("lng")));
        Double metres = args.has("metres") ? number(args.get("metres")) : null;
        return kind.equals("reverse") ? Api.reverse(at, metres) : Api.nearby(at, metres);
    }

    @TestFactory
    Stream<DynamicTest> buildsTheSharedRequests() {
        return cases("requests").map(c -> dynamicTest(c.get("name").asText(), () -> {
            JsonNode sent;
            try {
                Request<?> request = build(c.get("request").asText(), c.get("args"));
                var query = request.query().stream().map(p -> List.of(p.getKey(), p.getValue())).toList();
                sent = JSON.valueToTree(Map.of("path", request.path(), "query", query));
            } catch (IllegalArgumentException refused) {
                sent = JSON.nullNode();
            }
            assertEquals(c.get("sends"), sent);
        }));
    }

    private static final Map<String, Request<?>> REQUESTS = Map.of(
            "lookup", Api.lookup(CODE),
            "autocomplete", Api.autocomplete("E"),
            "reverse", Api.reverse(HERE),
            "nearby", Api.nearby(HERE));

    @TestFactory
    Stream<DynamicTest> reachesTheSharedOutcome() {
        return cases("tolerance").map(c -> dynamicTest(c.get("name").asText(), () -> {
            String body = c.has("text") ? c.get("text").asText() : c.get("body").toString();
            Result<?> decoded = Api.decode(REQUESTS.get(c.get("request").asText()), c.get("status").intValue(), body);
            String outcome = "ok";
            String code = null;
            if (decoded instanceof Result.Failed<?> failed) {
                String found = ((ApiError) failed.failure()).code();
                outcome = found.equals("malformed_response") ? "malformed" : "rejected";
                code = outcome.equals("rejected") ? found : null;
            }
            assertEquals(c.get("outcome").asText(), outcome);
            assertEquals(c.path("code").textValue(), code);
        }));
    }

    private static <T> Result<T> live(Request<T> request, String name) {
        JsonNode captured = LIVE.get(name);
        return Api.decode(request, captured.get("status").intValue(), captured.get("body").toString());
    }

    private static <T> T ok(Result<T> result) {
        if (result instanceof Result.Ok<T> ok) {
            return ok.value();
        }
        return fail(result.toString());
    }

    @Test
    void lookupStatuses() {
        Lookup valid = ok(live(Api.lookup(CODE), "lookup_valid"));
        assertTrue(valid.valid());
        assertEquals("valid", valid.status());
        assertEquals(false, valid.verified());
        assertNull(valid.administrativeAddress());

        Lookup missing = ok(live(Api.lookup(CODE), "lookup_not_found"));
        assertFalse(missing.valid());
        assertEquals("not_found", missing.status());
        assertEquals("invalid", ok(live(Api.lookup(CODE), "lookup_invalid")).status());
    }

    @Test
    void autocompleteSendsSegmentValuesWithoutLabels() {
        Autocomplete states = ok(live(Api.autocomplete("E"), "autocomplete_state"));
        assertEquals(Segment.STATE, states.segment());
        assertEquals(
                List.of("EB", "ED", "EK", "EN"),
                states.suggestions().stream().map(Suggestion::code).toList());
        assertTrue(states.suggestions().stream().allMatch(s -> s.label() == null));

        Autocomplete units = ok(live(Api.autocomplete("EK 01 A29 KR 3"), "autocomplete_unit_empty"));
        assertEquals(new Autocomplete(Segment.UNIT, List.of()), units);
    }

    @Test
    void suggestionsThatAreNotAListAreIgnored() {
        String body = "{\"data\": {\"segment\": \"state\", \"suggestions\": {\"a\": {\"code\": \"X\"}}}}";
        assertEquals(new Autocomplete(Segment.STATE, List.of()), ok(Api.decode(Api.autocomplete("E"), 200, body)));
    }

    @Test
    void reverse() {
        Reverse found = ok(live(Api.reverse(HERE), "reverse_found"));
        assertEquals(
                new NearestUnit("EK-01-A29-KR-36", "EK 01 A29 KR 36", 15.7, "high", null, null, null, null),
                found.unit());
        assertEquals(
                List.of("EK-01-A29-KR", "EK-01-A29", "EK", "unit"),
                List.of(found.area(), found.district(), found.state(), found.depth()));
        assertEquals(HERE, found.coordinate());
        assertEquals(25.0, found.radiusM());

        Reverse nothing = ok(live(Api.reverse(HERE), "reverse_not_found"));
        assertFalse(nothing.found());
        assertNull(nothing.unit());
        assertEquals("no postcode within range of this location", nothing.message());
    }

    @Test
    void nearbyIsAListNearestFirst() {
        List<NearbyUnit> units = ok(live(Api.nearby(HERE), "nearby_found"));
        assertEquals(new NearbyUnit("EK-01-A29-KR-36", "EK 01 A29 KR 36", 15.7), units.get(0));
        assertEquals(List.of(15.7, 18.3, 31.0), units.stream().map(NearbyUnit::distanceM).toList());
        assertEquals(List.of(), ok(live(Api.nearby(HERE), "nearby_empty")));
    }

    @Test
    void errors() {
        var expected = Map.of(
                "lookup_level_not_granted", "level_not_granted",
                "reverse_bad_request", "bad_request",
                "invalid_api_key", "invalid_api_key");
        expected.forEach((name, code) -> {
            var failed = (Result.Failed<Lookup>) live(Api.lookup(CODE), name);
            var error = (ApiError) failed.failure();
            assertEquals(LIVE.get(name).get("status").intValue(), error.status());
            assertEquals(code, error.code());
        });
    }
}
