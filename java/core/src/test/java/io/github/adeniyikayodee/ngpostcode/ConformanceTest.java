package io.github.adeniyikayodee.ngpostcode;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.DynamicTest.dynamicTest;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import io.github.adeniyikayodee.ngpostcode.ParseError.InvalidCharacter;
import io.github.adeniyikayodee.ngpostcode.ParseError.InvalidSegment;
import io.github.adeniyikayodee.ngpostcode.ParseError.WrongLength;
import java.io.IOException;
import java.nio.file.Path;
import java.util.Locale;
import java.util.Map;
import java.util.stream.Stream;
import java.util.stream.StreamSupport;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestFactory;

/** Runs the shared cases in {@code spec/vectors.json}, which every implementation must pass. */
class ConformanceTest {

    private static final ObjectMapper JSON = new ObjectMapper();
    private static final JsonNode CASES = read();

    private static JsonNode read() {
        try {
            return JSON.readTree(Path.of("..", "..", "spec", "vectors.json").toFile());
        } catch (IOException error) {
            throw new IllegalStateException(error);
        }
    }

    /** Quoted, because a dynamic test may not have a blank name and one input is empty. */
    private static String name(JsonNode c) {
        return "'" + c.get("input").asText() + "'";
    }

    private static Stream<JsonNode> cases(JsonNode list) {
        return StreamSupport.stream(list.spliterator(), false);
    }

    private static JsonNode outcome(Object result) {
        Object value;
        if (result instanceof Postcode code) {
            value = Map.of("canonical", code.toString());
        } else if (result instanceof Corrected fixed) {
            value = Map.of("canonical", fixed.postcode().toString(), "corrections", fixed.corrections());
        } else if (result instanceof WrongLength error) {
            value = Map.of("error", Map.of("kind", "length", "found", error.found(), "message", error.toString()));
        } else if (result instanceof InvalidCharacter error) {
            value = Map.of(
                    "error",
                    Map.of(
                            "kind", "invalid_character",
                            "char", error.character(),
                            "index", error.index(),
                            "message", error.toString()));
        } else {
            String segment = ((InvalidSegment) result).segment().toString();
            value = Map.of("error", Map.of("kind", "segment", "segment", segment, "message", result.toString()));
        }
        return JSON.valueToTree(value);
    }

    private static JsonNode expected(JsonNode c) {
        return ((ObjectNode) c.deepCopy()).retain("canonical", "corrections", "error");
    }

    @TestFactory
    Stream<DynamicTest> parsesValidCodes() {
        return cases(CASES.at("/parse/valid")).map(c -> dynamicTest(name(c), () -> {
            Postcode code = (Postcode) Postcode.parse(c.get("input").asText());
            assertEquals(c.get("canonical").asText(), code.toString());
            assertEquals(c.get("compact").asText(), code.compact());
            assertEquals(c.get("spaced").asText(), code.spaced());
        }));
    }

    @TestFactory
    Stream<DynamicTest> rejectsInvalidCodes() {
        return cases(CASES.at("/parse/invalid"))
                .map(c -> dynamicTest(name(c), () -> assertEquals(
                        expected(c), outcome(Postcode.parse(c.get("input").asText())))));
    }

    @TestFactory
    Stream<DynamicTest> parsesLeniently() {
        return cases(CASES.get("parse_lenient"))
                .map(c -> dynamicTest(name(c), () -> assertEquals(
                        expected(c), outcome(Postcode.parseLenient(c.get("input").asText())))));
    }

    @TestFactory
    Stream<DynamicTest> buildsFromSegments() {
        return cases(CASES.get("from_segments")).map(c -> dynamicTest(c.get("segments").toString(), () -> {
            String[] s = JSON.treeToValue(c.get("segments"), String[].class);
            assertEquals(expected(c), outcome(Postcode.fromSegments(s[0], s[1], s[2], s[3], s[4])));
        }));
    }

    @TestFactory
    Stream<DynamicTest> prefixes() {
        return cases(CASES.get("prefix")).map(c -> dynamicTest(c.get("through").asText(), () -> {
            Postcode code = (Postcode) Postcode.parse(c.get("input").asText());
            Segment through = Segment.valueOf(c.get("through").asText().toUpperCase(Locale.ROOT));
            assertEquals(c.get("prefix").asText(), code.prefix(through));
        }));
    }

    @Test
    void aTurkishLocaleChangesNothing() {
        Locale before = Locale.getDefault();
        Locale.setDefault(Locale.forLanguageTag("tr-TR"));
        try {
            assertEquals("NI-09-J67-QC-65", Postcode.parse("ni09j67qc65").toString());
            assertEquals("lga", Segment.LGA.toString());
        } finally {
            Locale.setDefault(before);
        }
    }

    @Test
    void theConstructorRefusesAnUncheckedString() {
        assertEquals("EK-01-A03-FK-01", new Postcode("EK01A03FK01").toString());
        for (String bad : new String[] {"ek01a03fk01", "EK-01-A03-FK-01", "EK00A03FK01", ""}) {
            assertThrows(IllegalArgumentException.class, () -> new Postcode(bad));
        }
    }
}
