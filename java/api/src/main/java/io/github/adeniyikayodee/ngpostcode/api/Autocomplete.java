package io.github.adeniyikayodee.ngpostcode.api;

import io.github.adeniyikayodee.ngpostcode.Segment;
import java.util.List;

/** @param segment the segment the suggestions complete, or {@code null} if it is not a known one */
public record Autocomplete(Segment segment, List<Suggestion> suggestions) {}
