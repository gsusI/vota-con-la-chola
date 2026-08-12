"""Shared primitives for the project knowledge base."""

from __future__ import annotations

import re
from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, field_validator

NonEmptyStr = Annotated[str, Field(min_length=1)]


class EntryType(StrEnum):
    """Supported durable knowledge entry types."""

    DECISION = "decision"
    FACT = "fact"
    WORKFLOW = "workflow"
    GOTCHA = "gotcha"
    ASSUMPTION = "assumption"
    OPEN_QUESTION = "open_question"
    DOMAIN_CONCEPT = "domain_concept"
    REFERENCE_MAP = "reference_map"


class EntryStatus(StrEnum):
    """Lifecycle status for a KB entry."""

    CONFIRMED = "confirmed"
    ASSUMED = "assumed"
    OPEN = "open"
    SUPERSEDED = "superseded"


def _validate_kb_ref(kb_ref: str) -> str:
    parts = kb_ref.split(".")
    if len(parts) < 2 or any(not part for part in parts):
        raise ValueError(
            "KBRef must contain at least 'kind.name' and have no empty segments"
        )
    return kb_ref


KBRef = Annotated[str, AfterValidator(_validate_kb_ref)]
KBReferences = dict[NonEmptyStr, KBRef]


def to_root_type(cls: type) -> str:
    """Return the KBRef root_type for a model class."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", cls.__name__).lower()


class Evidence(BaseModel):
    """Pointer to the artifact that backs a KB entry."""

    source: NonEmptyStr
    detail: str | None = None


class BaseKBEntry(BaseModel):
    """Base model for all top-level and nested KB entries."""

    name: NonEmptyStr
    description: NonEmptyStr
    entry_type: EntryType
    status: EntryStatus = EntryStatus.CONFIRMED
    evidence: list[Evidence] = Field(default_factory=list)
    references: KBReferences = Field(default_factory=dict)
    updated_at: date | None = None

    @field_validator("name")
    @classmethod
    def name_must_not_contain_dot(cls, value: str) -> str:
        if "." in value:
            raise ValueError(
                "KB entry names cannot contain '.' because it is the KBRef delimiter"
            )
        return value
