"""Pydantic-backed validation for citizen snapshot exports."""

from __future__ import annotations

from collections import Counter
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator


ALLOWED_STANCES = {"support", "oppose", "mixed", "unclear", "no_signal"}
ALLOWED_FRESHNESS_TIERS = {"fresh", "aging", "stale", "future", "unknown"}
ALLOWED_FRESHNESS_WARNING_REASONS = {
    "none",
    "aging_snapshot",
    "stale_snapshot",
    "future_as_of_date",
    "missing_dates",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)


class MetaQualityThresholds(StrictModel):
    high_min: float | int
    medium_min: float | int

    @model_validator(mode="after")
    def validate_thresholds(self) -> "MetaQualityThresholds":
        high_min = float(self.high_min)
        medium_min = float(self.medium_min)
        if not (0.0 <= medium_min <= high_min <= 1.0):
            raise ValueError("meta.quality.confidence_thresholds must satisfy 0 <= medium_min <= high_min <= 1")
        return self


class MetaQuality(StrictModel):
    cells_total: int
    stance_counts: dict[str, int]
    clear_total: int
    clear_pct: float | int
    any_signal_total: int
    any_signal_pct: float | int
    unknown_total: int
    unknown_pct: float | int
    confidence_avg_signal: float | int
    confidence_tiers: dict[str, int]
    confidence_thresholds: MetaQualityThresholds

    @model_validator(mode="after")
    def validate_contract(self) -> "MetaQuality":
        for key in ("cells_total", "clear_total", "any_signal_total", "unknown_total"):
            if int(getattr(self, key)) < 0:
                raise ValueError("meta.quality integer counters must be >= 0")
        for key in ("clear_pct", "any_signal_pct", "unknown_pct", "confidence_avg_signal"):
            value = float(getattr(self, key))
            if value < 0.0 or value > 1.0:
                raise ValueError(f"meta.quality.{key} must be in [0,1], got {value}")

        for stance in ALLOWED_STANCES:
            if stance not in self.stance_counts:
                raise ValueError(f"meta.quality.stance_counts missing key {stance!r}")
            if int(self.stance_counts[stance]) < 0:
                raise ValueError(f"meta.quality.stance_counts[{stance!r}] must be >= 0")
        if sum(int(self.stance_counts[stance]) for stance in ALLOWED_STANCES) != int(self.cells_total):
            raise ValueError("meta.quality.stance_counts must sum to meta.quality.cells_total")

        for tier in ("high", "medium", "low", "none"):
            if tier not in self.confidence_tiers:
                raise ValueError(f"meta.quality.confidence_tiers missing key {tier!r}")
            if int(self.confidence_tiers[tier]) < 0:
                raise ValueError(f"meta.quality.confidence_tiers[{tier!r}] must be >= 0")
        if sum(int(self.confidence_tiers[tier]) for tier in ("high", "medium", "low", "none")) != int(self.cells_total):
            raise ValueError("meta.quality.confidence_tiers must sum to meta.quality.cells_total")
        return self


class Freshness(StrictModel):
    freshness_version: str
    as_of_date: str | None
    generated_at: str | None
    data_age_days: int | None
    freshness_tier: str
    freshness_label: str
    should_warn: bool
    timeline_delta_days: int | None
    date_consistency_ok: bool
    warning_reason: str

    @model_validator(mode="after")
    def validate_freshness(self) -> "Freshness":
        freshness_tier = str(self.freshness_tier)
        if freshness_tier not in ALLOWED_FRESHNESS_TIERS:
            raise ValueError(f"Invalid meta.freshness.freshness_tier {freshness_tier!r}")
        warning_reason = str(self.warning_reason)
        if warning_reason not in ALLOWED_FRESHNESS_WARNING_REASONS:
            raise ValueError(f"Invalid meta.freshness.warning_reason {warning_reason!r}")

        data_age_days = self.data_age_days
        timeline_delta_days = self.timeline_delta_days
        if data_age_days is not None and timeline_delta_days is not None and int(data_age_days) != int(timeline_delta_days):
            raise ValueError("meta.freshness.data_age_days must equal meta.freshness.timeline_delta_days when both are present")

        if freshness_tier == "unknown":
            if bool(self.date_consistency_ok):
                raise ValueError("meta.freshness.date_consistency_ok must be false when freshness_tier='unknown'")
            if warning_reason != "missing_dates":
                raise ValueError("meta.freshness.warning_reason must be 'missing_dates' when freshness_tier='unknown'")
            if not bool(self.should_warn):
                raise ValueError("meta.freshness.should_warn must be true when freshness_tier='unknown'")
            if data_age_days is not None or timeline_delta_days is not None:
                raise ValueError("meta.freshness unknown state must not expose numeric age deltas")
            return self

        if freshness_tier == "future":
            if data_age_days is None or int(data_age_days) >= 0:
                raise ValueError("meta.freshness future state must expose negative data_age_days")
            if timeline_delta_days is None or int(timeline_delta_days) >= 0:
                raise ValueError("meta.freshness future state must expose negative timeline_delta_days")
            if bool(self.date_consistency_ok):
                raise ValueError("meta.freshness.date_consistency_ok must be false when freshness_tier='future'")
            if warning_reason != "future_as_of_date":
                raise ValueError("meta.freshness.warning_reason must be 'future_as_of_date' when freshness_tier='future'")
            if not bool(self.should_warn):
                raise ValueError("meta.freshness.should_warn must be true when freshness_tier='future'")
            return self

        if data_age_days is None or int(data_age_days) < 0:
            raise ValueError("meta.freshness non-future state must expose non-negative data_age_days")
        if timeline_delta_days is None or int(timeline_delta_days) < 0:
            raise ValueError("meta.freshness non-future state must expose non-negative timeline_delta_days")
        if not bool(self.date_consistency_ok):
            raise ValueError("meta.freshness.date_consistency_ok must be true for fresh/aging/stale states")
        expected_warning_reason = "none" if freshness_tier == "fresh" else f"{freshness_tier}_snapshot"
        if warning_reason != expected_warning_reason:
            raise ValueError(
                "meta.freshness.warning_reason mismatch for tier "
                f"{freshness_tier!r}: got {warning_reason!r}, expected {expected_warning_reason!r}"
            )
        if bool(self.should_warn) != (freshness_tier != "fresh"):
            raise ValueError("meta.freshness.should_warn must match freshness_tier semantics")
        return self


class HonestyAuditLinks(StrictModel):
    explorer_temas: str
    explorer_sql: str


class Honesty(StrictModel):
    honesty_version: str
    unknown_definition: str
    match_definition: str
    no_imputation: bool
    audit_rule: str
    audit_links: HonestyAuditLinks


class Meta(StrictModel):
    topic_set_id: int
    as_of_date: str
    computed_method: str
    computed_version: str
    generated_at: str
    freshness: Freshness
    honesty: Honesty
    methods_available: list[str] | None = None
    quality: MetaQuality | None = None
    guards: dict[str, Any] | None = None

    @field_validator("methods_available")
    @classmethod
    def validate_methods_available(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        for item in value:
            if not str(item).strip():
                raise ValueError("meta.methods_available contains empty string")
        if value != sorted(set(value)):
            raise ValueError("meta.methods_available must be sorted unique")
        return value

    @model_validator(mode="after")
    def validate_meta(self) -> "Meta":
        if self.methods_available is not None and self.computed_method not in set(self.methods_available):
            raise ValueError("meta.computed_method must be included in meta.methods_available")
        return self


class Topic(StrictModel):
    topic_id: int
    label: str
    stakes_rank: int
    is_high_stakes: bool
    links: dict[str, Any]
    concern_ids: list[str] | None = None

    @field_validator("concern_ids")
    @classmethod
    def validate_concern_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        for item in value:
            if not str(item).strip():
                raise ValueError("Empty concern_id in topic.concern_ids")
        if value != sorted(set(value)):
            raise ValueError("topic.concern_ids must be sorted unique")
        return value


class Party(StrictModel):
    party_id: int
    name: str
    acronym: str
    links: dict[str, Any]


class PartyTopicPosition(StrictModel):
    topic_id: int
    party_id: int
    stance: Literal["support", "oppose", "mixed", "unclear", "no_signal"]
    score: float | int
    confidence: float | int
    coverage: dict[str, Any]
    links: dict[str, Any]


class PartyConcernPrograma(StrictModel):
    concern_id: str
    party_id: int
    stance: Literal["support", "oppose", "mixed", "unclear", "no_signal"]
    confidence: float | int
    links: dict[str, Any]


class CitizenSnapshot(StrictModel):
    meta: Meta
    topics: list[Topic]
    parties: list[Party]
    party_topic_positions: list[PartyTopicPosition]
    concerns: dict[str, Any]
    party_concern_programas: list[PartyConcernPrograma] | None = None


def _require_unique(values: list[int], label: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"Duplicate {label} values in {label.split()[0]}[]")


def _normalise_validation_error(exc: ValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return str(exc)
    message = str(errors[0].get("msg") or str(exc))
    if message.startswith("Value error, "):
        return message[len("Value error, ") :]
    return message


def validate_snapshot_payload(
    payload: Any,
    *,
    strict_grid: bool,
    size_bytes: int,
    max_bytes: int | None = None,
) -> dict[str, Any]:
    try:
        snapshot = CitizenSnapshot.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(_normalise_validation_error(exc)) from exc

    topic_ids = [topic.topic_id for topic in snapshot.topics]
    party_ids = [party.party_id for party in snapshot.parties]
    if len(set(topic_ids)) != len(topic_ids):
        raise ValueError("Duplicate topic_id values in topics[]")
    if len(set(party_ids)) != len(party_ids):
        raise ValueError("Duplicate party_id values in parties[]")

    topic_id_set = set(topic_ids)
    party_id_set = set(party_ids)
    stance_counts: Counter[str] = Counter()
    pair_keys: set[tuple[int, int]] = set()
    bad_refs = 0
    for row in snapshot.party_topic_positions:
        if row.topic_id not in topic_id_set or row.party_id not in party_id_set:
            bad_refs += 1
        pair = (row.topic_id, row.party_id)
        if pair in pair_keys:
            raise ValueError(f"Duplicate (topic_id, party_id) in party_topic_positions: {pair}")
        pair_keys.add(pair)
        stance_counts[row.stance] += 1
    if bad_refs:
        raise ValueError(f"{bad_refs} rows in party_topic_positions reference missing topic_id/party_id")

    warnings: list[str] = []
    expected_grid = len(topic_ids) * len(party_ids)
    if len(snapshot.party_topic_positions) != expected_grid:
        message = f"party_topic_positions length={len(snapshot.party_topic_positions)} expected topics x parties={expected_grid}"
        if strict_grid:
            raise ValueError(message)
        warnings.append(message)

    programas_stances: Counter[str] = Counter()
    if snapshot.party_concern_programas is not None:
        seen_keys: set[tuple[str, int]] = set()
        bad_prog_party = 0
        for row in snapshot.party_concern_programas:
            key = (str(row.concern_id), int(row.party_id))
            if key in seen_keys:
                raise ValueError(f"Duplicate (concern_id, party_id) in party_concern_programas: {key}")
            seen_keys.add(key)
            if row.party_id not in party_id_set:
                bad_prog_party += 1
            programas_stances[row.stance] += 1
        if bad_prog_party:
            raise ValueError(f"{bad_prog_party} rows in party_concern_programas reference missing party_id")

    meta_max = None
    if isinstance(snapshot.meta.guards, dict):
        guard_max = snapshot.meta.guards.get("max_bytes")
        if isinstance(guard_max, int):
            meta_max = guard_max
    resolved_max_bytes = max_bytes if max_bytes is not None else meta_max
    if isinstance(resolved_max_bytes, int) and resolved_max_bytes > 0 and size_bytes > resolved_max_bytes:
        raise ValueError(f"Snapshot too large: {size_bytes} bytes > max_bytes={resolved_max_bytes}")

    return {
        "warnings": warnings,
        "summary": {
            "bytes": size_bytes,
            "topic_set_id": snapshot.meta.topic_set_id,
            "as_of_date": snapshot.meta.as_of_date,
            "computed_method": snapshot.meta.computed_method,
            "computed_version": snapshot.meta.computed_version,
            "freshness_tier": snapshot.meta.freshness.freshness_tier,
            "freshness_warning_reason": snapshot.meta.freshness.warning_reason,
            "date_consistency_ok": snapshot.meta.freshness.date_consistency_ok,
            "topics": len(topic_ids),
            "parties": len(party_ids),
            "party_topic_positions": len(snapshot.party_topic_positions),
            "stances": dict(stance_counts),
            "programas_stances": dict(programas_stances) if snapshot.party_concern_programas is not None else None,
        },
    }
