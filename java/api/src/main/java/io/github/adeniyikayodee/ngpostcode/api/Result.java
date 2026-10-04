package io.github.adeniyikayodee.ngpostcode.api;

/** The answer to a request, or the {@link Failure} that took its place. */
public sealed interface Result<T> {

    record Ok<T>(T value) implements Result<T> {}

    record Failed<T>(Failure failure) implements Result<T> {}
}
