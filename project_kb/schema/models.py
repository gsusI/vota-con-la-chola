"""Default project KB entry models."""

from pydantic import Field

from .core import BaseKBEntry, EntryStatus, EntryType, NonEmptyStr


class Decision(BaseKBEntry):
    entry_type: EntryType = EntryType.DECISION
    rationale: str | None = None
    consequences: list[NonEmptyStr] = Field(default_factory=list)


class Fact(BaseKBEntry):
    entry_type: EntryType = EntryType.FACT


class Workflow(BaseKBEntry):
    entry_type: EntryType = EntryType.WORKFLOW
    steps: list[NonEmptyStr] = Field(default_factory=list)
    validation: list[NonEmptyStr] = Field(default_factory=list)


class Gotcha(BaseKBEntry):
    entry_type: EntryType = EntryType.GOTCHA
    mitigation: str | None = None


class Assumption(BaseKBEntry):
    entry_type: EntryType = EntryType.ASSUMPTION
    status: EntryStatus = EntryStatus.ASSUMED
    validation_plan: str | None = None


class OpenQuestion(BaseKBEntry):
    entry_type: EntryType = EntryType.OPEN_QUESTION
    status: EntryStatus = EntryStatus.OPEN
    owner: str | None = None


class DomainConcept(BaseKBEntry):
    entry_type: EntryType = EntryType.DOMAIN_CONCEPT
    aliases: list[NonEmptyStr] = Field(default_factory=list)


class ReferenceMap(BaseKBEntry):
    entry_type: EntryType = EntryType.REFERENCE_MAP
    mappings: dict[NonEmptyStr, NonEmptyStr] = Field(default_factory=dict)
