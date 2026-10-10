package io.github.adeniyikayodee.ngpostcode.api;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;
import io.github.adeniyikayodee.ngpostcode.Postcode;
import io.github.adeniyikayodee.ngpostcode.api.Failure.ApiError;
import io.github.adeniyikayodee.ngpostcode.api.Failure.TransportError;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.http.HttpClient;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

/** The client against a local server: no request leaves the machine. */
class ClientTest {

    private static final Postcode CODE = new Postcode("FC03B06AG12");
    private final List<HttpExchange> seen = new ArrayList<>();
    private HttpServer server;

    private Client clientFor(HttpHandler handler) throws IOException {
        // Generous: a cold runner can take over a second to answer the first request.
        return clientFor(handler, Duration.ofSeconds(30));
    }

    private Client clientFor(HttpHandler handler, Duration timeout) throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/", exchange -> {
            seen.add(exchange);
            handler.handle(exchange);
        });
        server.start();
        String base = "http://127.0.0.1:" + server.getAddress().getPort();
        return new Client("secret", base, HttpClient.newHttpClient(), timeout);
    }

    private static void reply(HttpExchange exchange, int status, String body) throws IOException {
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        exchange.sendResponseHeaders(status, bytes.length == 0 ? -1 : bytes.length);
        exchange.getResponseBody().write(bytes);
        exchange.close();
    }

    @AfterEach
    void stop() {
        server.stop(0);
    }

    // spec/client.json: sends_the_key
    @Test
    void sendsTheKeyAndQueryAndDecodesTheAnswer() throws IOException {
        Client client = clientFor(
                exchange -> reply(exchange, 200, "{\"data\": {\"postcode\": \"FC-03-B06-AG-12\", \"valid\": true}}"));
        var found = assertInstanceOf(Result.Ok.class, client.send(Api.lookup(CODE, 2)));
        assertEquals(true, ((Lookup) found.value()).valid());
        assertEquals("/v1/lookup?code=FC-03-B06-AG-12&level=2", seen.get(0).getRequestURI().toString());
        assertEquals("secret", seen.get(0).getRequestHeaders().getFirst("X-API-Key"));
    }

    // spec/client.json: refuses_redirects
    @Test
    void aRedirectIsNotFollowed() throws IOException {
        Client client = clientFor(exchange -> {
            exchange.getResponseHeaders().add("Location", "/elsewhere");
            reply(exchange, 302, "");
        });
        var failed = assertInstanceOf(Result.Failed.class, client.send(Api.lookup(CODE)));
        assertEquals(302, assertInstanceOf(ApiError.class, failed.failure()).status());
        assertEquals(1, seen.size());
        assertThrows(
                IllegalArgumentException.class,
                () -> new Client("secret", Api.BASE_URL, HttpClient.newBuilder()
                        .followRedirects(HttpClient.Redirect.NORMAL)
                        .build()));
    }

    // spec/client.json: caps_the_body
    @Test
    void aBodyOverTheCapIsRefusedWithoutBeingReadInFull() throws IOException {
        var served = new java.util.concurrent.atomic.AtomicLong();
        Client client = clientFor(exchange -> {
            exchange.sendResponseHeaders(200, 0);
            try (var out = exchange.getResponseBody()) {
                while (served.addAndGet(65536) < 64_000_000) {
                    out.write(new byte[65536]);
                }
            } catch (IOException closed) {
                // The client hung up, as it should.
            }
        });
        var failed = assertInstanceOf(Result.Failed.class, client.send(Api.lookup(CODE)));
        assertEquals(new TransportError("response too large"), failed.failure());
        assertTrue(served.get() < 64_000_000);
    }

    // spec/client.json: times_out_a_stalled_body
    @Test
    void aBodyThatStallsTimesOutToo() throws IOException {
        Client client = clientFor(
                exchange -> {
                    exchange.sendResponseHeaders(200, 100);
                    exchange.getResponseBody().write("{\"data\":".getBytes(StandardCharsets.UTF_8));
                    exchange.getResponseBody().flush();
                },
                Duration.ofMillis(300));
        var failed = assertInstanceOf(Result.Failed.class, client.send(Api.lookup(CODE)));
        assertInstanceOf(TransportError.class, failed.failure());
    }

    // spec/client.json: refuses_an_unusable_key
    @Test
    void anUnusableKeyIsRefusedWithoutBeingEchoed() throws IOException {
        clientFor(exchange -> reply(exchange, 200, "{}"));
        String base = "http://127.0.0.1:" + server.getAddress().getPort();
        for (String key : List.of("se\ncret", "se cret", "s\u00e9cret", "", " \n")) {
            var failed = assertInstanceOf(Result.Failed.class, new Client(key, base).send(Api.lookup(CODE)));
            assertEquals(new TransportError("unusable API key"), failed.failure());
        }
        assertEquals(0, seen.size());
        assertThrows(NullPointerException.class, () -> new Client(null));
    }

    @Test
    void whitespaceAroundAKeyIsDropped() throws IOException {
        clientFor(exchange -> reply(exchange, 200, "{\"data\": {\"postcode\": \"FC-03-B06-AG-12\", \"valid\": true}}"));
        String base = "http://127.0.0.1:" + server.getAddress().getPort();
        assertInstanceOf(Result.Ok.class, new Client(" secret\n", base).send(Api.lookup(CODE)));
        assertEquals("secret", seen.get(0).getRequestHeaders().getFirst("X-API-Key"));
    }

    // spec/client.json: ignores_a_trailing_slash
    @Test
    void aTrailingSlashOnTheBaseUrlIsIgnored() throws IOException {
        clientFor(exchange -> reply(exchange, 200, "{\"data\": {\"valid\": true}}"));
        String base = "http://127.0.0.1:" + server.getAddress().getPort() + "//";
        assertInstanceOf(Result.Ok.class, new Client("secret", base).send(Api.lookup(CODE)));
        assertEquals("/v1/lookup", seen.get(0).getRequestURI().getPath());
    }

    // spec/client.json: failures_are_values
    @Test
    void aSilentServerTimesOutAsAValueWithoutTheKey() throws IOException {
        Client client = clientFor(exchange -> {}, Duration.ofMillis(300));
        var failed = assertInstanceOf(Result.Failed.class, client.send(Api.lookup(CODE)));
        assertInstanceOf(TransportError.class, failed.failure());
        assertFalse(failed.failure().toString().contains("secret"));
    }
}
