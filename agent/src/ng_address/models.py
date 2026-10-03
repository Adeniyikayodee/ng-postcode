"""Plain, immutable data passed between the steps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Relation = Literal["at", "near", "opposite", "behind", "beside", "after", "before", "off", "inside"]
Precision = Literal["building", "street", "locality"]
Level = Literal["building", "area", "district", "lga"]
Confidence = Literal["high", "medium", "low"]
Status = Literal["resolved", "partial", "unresolved"]
Method = Literal["typed", "location", "geocoded"]


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Landmark(Frozen):
    name: str
    relation: Relation = Field(
        description="How the address relates to the landmark. 'at' means the address is the "
        "landmark itself; any other value means a different building nearby."
    )


class ParsedAddress(Frozen):
    """Claude's reading of the address. Every field is required so the schema is strict."""

    house_number: str | None
    street: str | None
    landmarks: list[Landmark]
    locality: str | None = Field(description="Estate, area or neighbourhood, e.g. Lekki Phase 1.")
    lga: str | None = Field(description="Local government area, if stated or certain.")
    state: str | None
    geocode_queries: list[str] = Field(
        description="Up to three map search strings, most specific first, each ending with the "
        "town and state. Prefer named places and streets over directions."
    )
    question: str | None = Field(
        description="One short question for the user if the address cannot be placed on a "
        "street or named place, else null."
    )


class Geocoded(Frozen):
    query: str
    lat: float
    lng: float
    precision: Precision
    label: str


class Resolution(Frozen):
    """The answer, never more precise than the evidence behind it."""

    status: Status
    code: str | None = Field(description="A full postcode at building level, else a prefix.")
    level: Level | None
    confidence: Confidence | None
    method: Method | None
    question: str | None = Field(description="What to ask the user to get a better answer.")
    evidence: list[str]


@dataclass(frozen=True, slots=True)
class ParseFailure:
    """Why an address could not be read into a ParsedAddress."""

    reason: str
