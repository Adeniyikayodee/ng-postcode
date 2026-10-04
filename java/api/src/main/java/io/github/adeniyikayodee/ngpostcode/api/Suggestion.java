package io.github.adeniyikayodee.ngpostcode.api;

/**
 * @param code the value of the segment being completed, such as {@code A03}, not a full prefix
 * @param label documented by NIPOST but not sent by the live API as of October 2026
 */
public record Suggestion(String code, String label) {}
