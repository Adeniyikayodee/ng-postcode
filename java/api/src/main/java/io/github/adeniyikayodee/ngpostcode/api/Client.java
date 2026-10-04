package io.github.adeniyikayodee.ngpostcode.api;

import io.github.adeniyikayodee.ngpostcode.api.Failure.TransportError;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.stream.Collectors;

/** Blocking HTTP client over {@link Api}: the only class that performs I/O. Safe to share. */
public final class Client {

    public static final Duration TIMEOUT = Duration.ofSeconds(10);

    private final String apiKey;
    private final String baseUrl;
    private final HttpClient http;
    private final Duration timeout;

    public Client(String apiKey) {
        this(apiKey, Api.BASE_URL);
    }

    /** Points the client at another host, such as a staging stack or a mock. */
    public Client(String apiKey, String baseUrl) {
        this(apiKey, baseUrl, HttpClient.newBuilder().connectTimeout(TIMEOUT).build(), TIMEOUT);
    }

    /**
     * Uses your own {@link HttpClient}, for proxies or pooling.
     *
     * @throws IllegalArgumentException if it follows redirects, which would carry the key to
     *     another host
     */
    public Client(String apiKey, String baseUrl, HttpClient http) {
        this(apiKey, baseUrl, http, TIMEOUT);
    }

    Client(String apiKey, String baseUrl, HttpClient http, Duration timeout) {
        if (http.followRedirects() != HttpClient.Redirect.NEVER) {
            throw new IllegalArgumentException("the HttpClient must not follow redirects");
        }
        this.apiKey = apiKey;
        this.baseUrl = baseUrl;
        this.http = http;
        this.timeout = timeout;
    }

    public <T> Result<T> send(Request<T> request) {
        String query = request.query().stream()
                .map(pair -> encode(pair.getKey()) + "=" + encode(pair.getValue()))
                .collect(Collectors.joining("&"));
        HttpRequest call = HttpRequest.newBuilder(URI.create(baseUrl + request.path() + "?" + query))
                // Without this the JDK client waits for an answer forever.
                .timeout(timeout)
                .header("X-API-Key", apiKey)
                .build();
        // The request timeout stops at the response headers before Java 26, so a body that
        // stalls would hang. The deadline here covers the whole exchange.
        var pending = http.sendAsync(call, HttpResponse.BodyHandlers.ofString());
        try {
            HttpResponse<String> response = pending.get(timeout.toMillis(), TimeUnit.MILLISECONDS);
            return Api.decode(request, response.statusCode(), response.body());
        } catch (TimeoutException error) {
            pending.cancel(true);
            return failed(new TimeoutException("request timed out"));
        } catch (ExecutionException error) {
            return failed(error.getCause());
        } catch (InterruptedException error) {
            pending.cancel(true);
            Thread.currentThread().interrupt();
            return failed(error);
        }
    }

    private static String encode(String text) {
        return URLEncoder.encode(text, StandardCharsets.UTF_8);
    }

    private static <T> Result<T> failed(Throwable error) {
        String reason = error.getMessage() != null ? error.getMessage() : error.getClass().getSimpleName();
        return new Result.Failed<>(new TransportError(reason));
    }
}
