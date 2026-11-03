"""Constrained input types shared by request schemas.

Every text field users send has a length cap: it protects the database's storage and the
LLM's token budget, and gives the frontend one source of truth for its input limits.
"""

from typing import Annotated, Any, ClassVar, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)


def _bounded(max_length: int) -> StringConstraints:
    """Trimmed of surrounding whitespace, non-empty, at most ``max_length`` characters."""
    return StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length)


def _drop_case_insensitive_duplicates(values: list[str]) -> list[str]:
    first_spelling: dict[str, str] = {}
    for value in values:
        first_spelling.setdefault(value.casefold(), value)
    return list(first_spelling.values())


Name = Annotated[str, _bounded(80)]
Notes = Annotated[str, _bounded(1000)]
Title = Annotated[str, _bounded(120)]
MessageText = Annotated[str, _bounded(2000)]
Interest = Annotated[str, _bounded(60)]
Interests = Annotated[
    list[Interest],
    Field(max_length=20),
    AfterValidator(_drop_case_insensitive_duplicates),
]

# Whole US dollars; the cap only rejects obvious typos.
BudgetDollars = Annotated[int, Field(ge=0, le=100_000)]


class PartialUpdate(BaseModel):
    """Base for PATCH bodies: only the fields the client sent are applied.

    Subclasses list in ``required_when_present`` the fields that may be omitted but not
    set to null, because the stored value can't be empty.
    """

    model_config = ConfigDict(extra="forbid")

    required_when_present: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def _reject_nulls_for_required_fields(self) -> Self:
        for field in self.required_when_present & self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} can't be empty")
        return self

    def changes(self) -> dict[str, Any]:
        """The fields the client sent, with their new values."""
        return self.model_dump(exclude_unset=True)
