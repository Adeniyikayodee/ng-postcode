package io.github.adeniyikayodee.ngpostcode.api;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.List;
import java.util.Map;
import java.util.function.Function;

/** A GET request whose successful response decodes to {@code T}. Build one with {@link Api}. */
public final class Request<T> {

    private final String path;
    private final List<Map.Entry<String, String>> query;
    final Function<JsonNode, T> read;

    Request(String path, List<Map.Entry<String, String>> query, Function<JsonNode, T> read) {
        this.path = path;
        this.query = List.copyOf(query);
        this.read = read;
    }

    public String path() {
        return path;
    }

    /** Query parameters in the order they are sent. */
    public List<Map.Entry<String, String>> query() {
        return query;
    }
}
