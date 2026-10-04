package io.github.adeniyikayodee.ngpostcode;

/** What {@link Postcode#parseLenient} returns: a {@link Corrected} code, or why there is none. */
public sealed interface Lenient permits Corrected, ParseError {}
