package io.github.adeniyikayodee.ngpostcode.api;

/** Why a request gave no answer. Expected failures are values, never exceptions. */
public sealed interface Failure {

    /**
     * The API refused the request, with {@code code} taken from its error envelope
     * ({@code auth_required}, {@code insufficient_credits}, ...), or its answer was not the
     * documented envelope, with {@code code} set to {@code malformed_response}.
     */
    record ApiError(int status, String code, String message) implements Failure {
        @Override
        public String toString() {
            return code + " (" + status + "): " + message;
        }
    }

    /** The request never produced a response: DNS, TLS, timeout and the like. */
    record TransportError(String reason) implements Failure {
        @Override
        public String toString() {
            return reason;
        }
    }
}
