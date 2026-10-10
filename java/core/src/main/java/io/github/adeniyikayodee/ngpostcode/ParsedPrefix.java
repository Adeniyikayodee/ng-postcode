package io.github.adeniyikayodee.ngpostcode;

/** What {@link Prefix#parse} returns: a {@link Prefix}, or why there is none. */
public sealed interface ParsedPrefix permits Prefix, ParseError {}
