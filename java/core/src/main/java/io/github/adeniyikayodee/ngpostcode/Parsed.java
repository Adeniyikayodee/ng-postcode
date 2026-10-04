package io.github.adeniyikayodee.ngpostcode;

/** What {@link Postcode#parse} returns: a {@link Postcode}, or why there is none. */
public sealed interface Parsed permits Postcode, ParseError {}
