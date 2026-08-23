#!/usr/bin/env python3
"""Publish fail-closed policy-outcome status plus exact real evidence bytes.

The published status discloses one machine-audited methodological candidate:
the named Senate and Eurostat inputs were selected together. It does not turn
that candidate into a validated outcome link or make an association, causal,
effect, merit, blame, success, failure, legality, or corruption claim.

Every verification asset is copied byte-for-byte into a content-addressed
directory. The mutable status is written atomically, then the public evidence
manifest is committed last. No synthetic or mock data is accepted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_publish.snapshot_attestation import (
    SnapshotAttestationError,
    verify_signed_attestation,
)

DEFAULT_VALIDATION_REPORT = (
    REPO_ROOT
    / "docs/etl/sprints/OUTCOME-CONTEXT-20260820/evidence/"
    "outcome-context-validation.json"
)
DEFAULT_OUT = REPO_ROOT / "ui/gh-pages-next/public/policy-outcomes/data/policy-outcomes.json"
DEFAULT_SIGNED_SCALE_MANIFEST = (
    REPO_ROOT
    / "docs/etl/sprints/REPRODUCIBILITY-20260819/evidence/"
    "current-signed-scale-manifest-5d9ce557.json"
)
DEFAULT_SCALE_ATTESTATION = (
    REPO_ROOT
    / "docs/etl/sprints/REPRODUCIBILITY-20260819/evidence/"
    "current-snapshot-attestation.json"
)
DEFAULT_SCALE_ATTESTATION_SIGNATURE = DEFAULT_SCALE_ATTESTATION.with_suffix(".json.sig")
DEFAULT_SCALE_LIVE_VERIFICATION = (
    REPO_ROOT
    / "docs/etl/sprints/REPRODUCIBILITY-20260819/evidence/"
    "live-signed-snapshot-verification.json"
)
DEFAULT_SCALE_LIVE_PARITY = (
    REPO_ROOT
    / "docs/etl/sprints/REPRODUCIBILITY-20260819/evidence/"
    "live-scale-origin-parity.json"
)
DEFAULT_SCALE_ALLOWED_SIGNERS = (
    REPO_ROOT / "docs/ops/keys/vclc-snapshot-release-2026.allowed_signers"
)

SCALE_ORIGIN_SIGNER_IDENTITY = "vclc-snapshot-release-2026"
SCALE_ORIGIN_PUBLIC_KEY_FINGERPRINT = (
    "SHA256:R2B1jFbkLoigmKxObr+ExlBLrKENkaUDp0C3ip0Lj7A"
)
APPROVED_SCALE_ALLOWED_SIGNERS_SHA256 = (
    "3d38695951007449ee8f515dcd30f66c061516d4ba61ec41dccae419b8f68c65"
)

VALIDATOR_SCHEMA_VERSION = "outcome_context_validation_v1"
MATERIALIZER_SCHEMA_VERSION = "outcome_context_materialization_report_v1"
METHOD_VERSION = "outcome_linking_v1"
PUBLIC_SCHEMA_VERSION = "policy_outcomes_public_status_v3"
PUBLIC_MANIFEST_SCHEMA_VERSION = "policy_outcomes_public_evidence_manifest_v1"
PACKAGE_IDENTITY_CONTRACT_VERSION = "policy_outcomes_public_evidence_identity_v1"
PUBLIC_MATERIALIZATION_EVIDENCE_SCHEMA_VERSION = (
    "outcome_context_materialization_public_evidence_v1"
)
PUBLIC_VALIDATION_EVIDENCE_SCHEMA_VERSION = (
    "outcome_context_validation_public_evidence_v1"
)
BUNDLE_SEMANTIC_IDENTITY_CONTRACT_VERSION = "outcome_context_bundle_semantic_identity_v1"

# One approved deterministic validation-evidence identity. The operational
# validator report also records physical SQLite file facts that can change
# while its checked semantic release stays identical; those facts are verified
# locally but are explicitly excluded from this public release identity.
APPROVED_VALIDATION_EVIDENCE_SHA256 = (
    "8e97863250312acba99be9d8952febb5c5eae68993cc3fa036d6d30a4561bc8b"
)
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
HTTPS_RE = re.compile(r"^https://[^\s]+$")

CLAIM_POLICY = {
    "statistical_association_claim": "none",
    "causal_claim": "none",
    "effect_estimate": "not_computed",
    "political_merit_or_blame": "not_assessed",
    "success_or_failure_assessment": "not_assessed",
    "corruption_assessment": "not_assessed",
}

PUBLIC_IDENTITY_POLICY = (
    "retain official public identity; exclude only secrets, private session state, "
    "and workstation traces"
)


class PolicyOutcomesExportError(RuntimeError):
    """Validation or artifact-integrity failure that must stop publication."""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--validation-report",
        type=Path,
        default=DEFAULT_VALIDATION_REPORT,
        help="Passed independent outcome-context validator report.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Public status JSON output.",
    )
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=None,
        help="Evidence directory. Default: sibling policy-outcomes/evidence directory.",
    )
    return parser.parse_args(argv)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise PolicyOutcomesExportError(f"duplicate JSON key: {key!r}")
        output[key] = value
    return output


def _reject_nonfinite(value: str) -> None:
    raise PolicyOutcomesExportError(f"non-finite JSON number forbidden: {value}")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def json_file_bytes(value: dict[str, Any]) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return path.name


def strict_json_bytes(raw: bytes, label: str) -> dict[str, Any]:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise PolicyOutcomesExportError(f"UTF-8 BOM forbidden: {label}")
    try:
        payload = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PolicyOutcomesExportError(f"invalid strict JSON in {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PolicyOutcomesExportError(f"expected JSON object: {label}")
    return payload


def strict_json_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PolicyOutcomesExportError(f"required JSON file missing: {_safe_label(path)}")
    return strict_json_bytes(path.read_bytes(), _safe_label(path))


def _repo_file(path_text: Any, label: str) -> Path:
    if not isinstance(path_text, str) or not path_text:
        raise PolicyOutcomesExportError(f"{label}.path must be a repo-relative string")
    candidate = Path(path_text)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise PolicyOutcomesExportError(f"{label}.path escapes repository")
    resolved = (REPO_ROOT / candidate).resolve()
    try:
        resolved.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise PolicyOutcomesExportError(f"{label}.path escapes repository") from exc
    if not resolved.is_file():
        raise PolicyOutcomesExportError(f"{label} missing: {path_text}")
    return resolved


def _require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PolicyOutcomesExportError(f"{label} must be an object")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise PolicyOutcomesExportError(f"{label} must be an array")
    return value


def _require_int(value: Any, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise PolicyOutcomesExportError(f"{label} must be an integer >= {minimum}")
    return value


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PolicyOutcomesExportError(f"{label} must be a non-empty string")
    return value


def _require_https(value: Any, label: str) -> str:
    text = _require_string(value, label)
    if HTTPS_RE.fullmatch(text) is None:
        raise PolicyOutcomesExportError(f"{label} must be an HTTPS URL")
    return text


def _require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or HEX64_RE.fullmatch(value) is None:
        raise PolicyOutcomesExportError(f"{label} must be lowercase SHA-256")
    return value


def _expect_values(source: Any, expected: dict[str, Any], label: str) -> dict[str, Any]:
    obj = _require_object(source, label)
    for key, expected_value in expected.items():
        actual = obj.get(key)
        if actual != expected_value or type(actual) is not type(expected_value):
            raise PolicyOutcomesExportError(
                f"{label}.{key} mismatch: expected {expected_value!r}, got {actual!r}"
            )
    return obj


def _verify_reported_file(fact: Any, label: str) -> Path:
    obj = _require_object(fact, label)
    path = _repo_file(obj.get("path"), label)
    expected_bytes = _require_int(obj.get("bytes"), f"{label}.bytes", minimum=1)
    expected_sha = _require_sha256(obj.get("sha256"), f"{label}.sha256")
    if path.stat().st_size != expected_bytes:
        raise PolicyOutcomesExportError(f"{label} byte count drift")
    if sha256_file(path) != expected_sha:
        raise PolicyOutcomesExportError(f"{label} SHA-256 drift")
    return path


def _file_fact(path: Path, *, public_path: str, media_type: str, role: str) -> dict[str, Any]:
    return {
        "path": public_path,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "media_type": media_type,
        "role": role,
    }


def _bytes_fact(raw: bytes, *, public_path: str, media_type: str, role: str) -> dict[str, Any]:
    return {
        "path": public_path,
        "bytes": len(raw),
        "sha256": sha256_bytes(raw),
        "media_type": media_type,
        "role": role,
    }


def _bundle_semantic_projection(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "identity_contract_version": BUNDLE_SEMANTIC_IDENTITY_CONTRACT_VERSION,
        "method_version": bundle.get("method_version"),
        "scope_truth": bundle.get("scope_truth"),
        "policy": bundle.get("policy"),
        "counts": bundle.get("counts"),
        "scope_closures": bundle.get("scope_closures"),
        "links": bundle.get("links"),
        "link_versions": bundle.get("link_versions"),
        "observation_refs": bundle.get("observation_refs"),
        "participant_refs": bundle.get("participant_refs"),
        "evidence": bundle.get("evidence"),
        "reviews": bundle.get("reviews"),
        "releases": bundle.get("releases"),
        "release_memberships": bundle.get("release_memberships"),
    }


def _validate_zero_state(
    report: dict[str, Any], bundle: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    truth = _require_object(report.get("truth"), "validator truth")
    counts = _require_object(report.get("counts"), "validator counts")
    scope_truth = _require_object(bundle.get("scope_truth"), "bundle scope_truth")

    _expect_values(
        truth,
        {
            "scale_stage": "C0",
            "evidence_level": "L1",
            "candidate_status": "pending_human_review",
            "human_reviews": 0,
            "releases": 0,
            "release_memberships": 0,
            "publications": 0,
            "synthetic_or_mock_rows": 0,
        },
        "validator truth",
    )
    for key in (
        "bounded_candidate_pairs",
        "machine_audited_preproduction_candidates",
        "human_reviewed_pairs",
        "links",
        "versions",
        "reviews",
        "releases",
        "release_memberships",
        "publications",
        "published_links",
        "synthetic_or_mock_rows",
        "participant_refs",
        "participants",
    ):
        _require_int(counts.get(key), f"validator counts.{key}")
    if counts["links"] != 1 or counts["versions"] != 1:
        raise PolicyOutcomesExportError("exactly one pending methodological candidate required")
    if counts["machine_audited_preproduction_candidates"] != 1:
        raise PolicyOutcomesExportError("one machine-audited candidate disclosure required")
    for key in (
        "human_reviewed_pairs",
        "reviews",
        "releases",
        "release_memberships",
        "publications",
        "published_links",
        "synthetic_or_mock_rows",
    ):
        if counts[key] != 0:
            raise PolicyOutcomesExportError(f"validator counts.{key} must remain zero")
    if counts["reviews"] != truth["human_reviews"]:
        raise PolicyOutcomesExportError("review count mismatch")
    if counts["participant_refs"] != counts["participants"]:
        raise PolicyOutcomesExportError("participant count mismatch")

    _expect_values(
        scope_truth,
        {
            "scale_stage": truth["scale_stage"],
            "bounded_candidate_pairs": counts["bounded_candidate_pairs"],
            "machine_audited_preproduction_candidates": 1,
            "human_reviewed_pairs": 0,
            "published_links": 0,
            "bounded_scope_complete": True,
            "all_possible_actions_searched": False,
            "all_possible_indicators_searched": False,
            "all_possible_action_indicator_pairs_searched": False,
        },
        "bundle scope truth",
    )
    for key in ("reviews", "releases", "release_memberships"):
        if bundle.get(key) != []:
            raise PolicyOutcomesExportError(f"bundle.{key} must be empty")
    return truth, counts, scope_truth


def _validate_scope_closure(
    report: dict[str, Any], bundle: dict[str, Any], counts: dict[str, Any]
) -> dict[str, Any]:
    reconstruction = _require_object(
        report.get("source_reconstruction"), "validator source reconstruction"
    )
    action_count = _require_int(
        reconstruction.get("action_candidate_rows"),
        "source reconstruction.action_candidate_rows",
        minimum=1,
    )
    eligible_series = _require_int(
        reconstruction.get("eligible_indicator_series"),
        "source reconstruction.eligible_indicator_series",
        minimum=1,
    )
    action_bytes = _require_int(
        reconstruction.get("action_universe_canonical_bytes"),
        "source reconstruction.action_universe_canonical_bytes",
        minimum=1,
    )
    action_sha = _require_sha256(
        reconstruction.get("action_universe_sha256"),
        "source reconstruction.action_universe_sha256",
    )
    eligible_sha = _require_sha256(
        reconstruction.get("eligible_indicator_series_sha256"),
        "source reconstruction.eligible_indicator_series_sha256",
    )
    if action_count * eligible_series != counts["bounded_candidate_pairs"]:
        raise PolicyOutcomesExportError("bounded pair arithmetic mismatch")

    closures = _require_list(bundle.get("scope_closures"), "bundle scope closures")
    by_kind: dict[str, dict[str, Any]] = {}
    for index, closure in enumerate(closures):
        item = _require_object(closure, f"bundle scope closure {index}")
        kind = _require_string(item.get("scope_kind"), f"scope closure {index}.scope_kind")
        if kind in by_kind:
            raise PolicyOutcomesExportError(f"duplicate scope closure kind: {kind}")
        if item.get("bounded_scope_complete") is not True:
            raise PolicyOutcomesExportError(f"scope closure {kind} is incomplete")
        by_kind[kind] = item
    if set(by_kind) != {"action", "indicator", "actor_reference", "combined"}:
        raise PolicyOutcomesExportError("scope closure kinds mismatch")

    action = _require_object(by_kind["action"].get("canonical_preimage"), "action closure")
    indicator = _require_object(
        by_kind["indicator"].get("canonical_preimage"), "indicator closure"
    )
    combined = _require_object(
        by_kind["combined"].get("canonical_preimage"), "combined closure"
    )
    _expect_values(
        action,
        {
            "candidate_count": action_count,
            "candidate_universe_canonical_bytes": action_bytes,
            "candidate_universe_sha256": action_sha,
            "bounded_scope_complete": True,
            "all_possible_actions_searched": False,
        },
        "action closure",
    )
    _expect_values(
        indicator,
        {
            "geography_eligible_series_count": eligible_series,
            "geography_eligible_series_sha256": eligible_sha,
            "bounded_scope_complete": True,
            "all_possible_indicators_searched": False,
        },
        "indicator closure",
    )
    combined_sha = _require_sha256(
        by_kind["combined"].get("scope_closure_sha256"), "combined scope SHA-256"
    )
    _expect_values(
        combined,
        {
            "candidate_pairs_in_bounded_scope": counts["bounded_candidate_pairs"],
            "machine_audited_preproduction_candidates": 1,
            "human_reviewed_pairs": 0,
            "published_links": 0,
            "bounded_scope_complete": True,
            "all_possible_actions_searched": False,
            "all_possible_indicators_searched": False,
            "all_possible_action_indicator_pairs_searched": False,
        },
        "combined closure",
    )
    for key, kind in (
        ("action_scope_sha256", "action"),
        ("indicator_scope_sha256", "indicator"),
        ("actor_reference_scope_sha256", "actor_reference"),
    ):
        if combined.get(key) != by_kind[kind].get("scope_closure_sha256"):
            raise PolicyOutcomesExportError(f"combined closure {key} mismatch")
    return {
        "action_candidates": action_count,
        "eligible_indicator_series": eligible_series,
        "candidate_pairs": counts["bounded_candidate_pairs"],
        "action_universe_canonical_bytes": action_bytes,
        "action_universe_sha256": action_sha,
        "eligible_indicator_series_sha256": eligible_sha,
        "combined_scope_sha256": combined_sha,
        "bounded_scope_complete": True,
        "all_possible_actions_searched": False,
        "all_possible_indicators_searched": False,
        "all_possible_action_indicator_pairs_searched": False,
    }


def _read_exact_source_payload(
    database_path: Path,
    *,
    source_id: str,
    source_record_id: str,
    expected_sha256: str,
    expected_bytes: int,
) -> bytes:
    uri = f"file:{database_path.as_posix()}?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    try:
        connection.execute("PRAGMA query_only = ON")
        connection.execute("BEGIN")
        row = connection.execute(
            """
            SELECT raw_payload, content_sha256
            FROM source_records
            WHERE source_id = ? AND source_record_id = ?
            """,
            (source_id, source_record_id),
        ).fetchone()
        connection.rollback()
    finally:
        connection.close()
    if row is None:
        raise PolicyOutcomesExportError(f"source record missing: {source_id}/{source_record_id}")
    raw_payload, stored_sha = row
    if not isinstance(raw_payload, str):
        raise PolicyOutcomesExportError("source raw_payload must be SQLite TEXT")
    raw = raw_payload.encode("utf-8")
    if stored_sha != expected_sha256 or sha256_bytes(raw) != expected_sha256:
        raise PolicyOutcomesExportError("source raw_payload SHA-256 mismatch")
    if len(raw) != expected_bytes:
        raise PolicyOutcomesExportError("source raw_payload byte count mismatch")
    strict_json_bytes(raw, f"{source_id} normalized raw_payload")
    return raw


def _validate_materialization_report(
    path: Path,
    *,
    validation_report: dict[str, Any],
    artifacts: dict[str, Any],
    scope: dict[str, Any],
) -> tuple[dict[str, Any], Path, Path, Path]:
    material = strict_json_file(path)
    _expect_values(
        material,
        {
            "schema_version": MATERIALIZER_SCHEMA_VERSION,
            "method_version": METHOD_VERSION,
            "status": "passed",
            "generated_at": validation_report.get("generated_at"),
            "truth": validation_report.get("truth"),
        },
        "materialization report",
    )
    semantic = _require_object(material.get("semantic"), "materialization semantic")
    _expect_values(
        semantic,
        {
            "artifact_set_sha256": artifacts.get("artifact_set_sha256"),
            "bundle_semantic_sha256": artifacts.get("bundle_semantic_sha256"),
            "combined_scope_sha256": scope["combined_scope_sha256"],
            "counts": artifacts.get("manifest_counts"),
        },
        "materialization semantic",
    )
    outputs = _require_object(material.get("outputs"), "materialization outputs")
    output_map = {
        "latest.json": "latest",
        "manifest.json": "manifest",
        "outcome-context-candidates-v1.db": "database",
        "outcome-context-candidates-v1.json": "semantic_json",
    }
    for output_name, artifact_name in output_map.items():
        _expect_values(
            outputs.get(output_name),
            {
                "path": artifacts[artifact_name]["path"],
                "bytes": artifacts[artifact_name]["bytes"],
                "sha256": artifacts[artifact_name]["sha256"],
            },
            f"materialization outputs.{output_name}",
        )
    scale = _require_object(material.get("scale"), "materialization scale")
    _expect_values(
        scale,
        {
            "million_scale_ready": False,
            "multi_candidate_supported": False,
            "resume_or_checkpoint_supported": False,
            "semantic_json_monolithic": True,
            "source_reads_streaming": False,
            "source_reads_use_fetchall": True,
        },
        "materialization scale",
    )
    inputs = _require_object(material.get("inputs"), "materialization inputs")
    actions_database = _require_object(
        inputs.get("actions_database"), "materialization actions database"
    )
    actions_path = _repo_file(actions_database.get("path"), "actions database")
    indicator_database = _require_object(
        inputs.get("indicator_database"), "materialization indicator database"
    )
    indicator_database_path = _repo_file(
        indicator_database.get("path"), "indicator database"
    )
    indicator_raw = _require_object(
        inputs.get("indicator_raw_source"), "materialization indicator raw source"
    )
    indicator_raw_path = _repo_file(indicator_raw.get("path"), "indicator raw source")
    if indicator_raw_path.stat().st_size != _require_int(
        indicator_raw.get("bytes"), "indicator raw source.bytes", minimum=1
    ):
        raise PolicyOutcomesExportError("indicator raw source byte count drift")
    if sha256_file(indicator_raw_path) != _require_sha256(
        indicator_raw.get("sha256"), "indicator raw source.sha256"
    ):
        raise PolicyOutcomesExportError("indicator raw source SHA-256 drift")
    return material, actions_path, indicator_database_path, indicator_raw_path


def _reconstruct_scope_universe_assets(
    *,
    actions_database_path: Path,
    indicator_database_path: Path,
    bundle: dict[str, Any],
    scope: dict[str, Any],
) -> tuple[bytes, bytes]:
    closures = {
        item["scope_kind"]: item
        for item in _require_list(bundle.get("scope_closures"), "bundle scope closures")
    }
    action_preimage = _require_object(
        closures["action"].get("canonical_preimage"), "action closure preimage"
    )
    action_query = _require_object(
        action_preimage.get("query_contract"), "action closure query contract"
    )
    action_sql = _require_string(action_query.get("sql_utf8"), "action closure SQL")
    if not action_sql.lstrip().upper().startswith("SELECT ") or ";" in action_sql:
        raise PolicyOutcomesExportError("action closure SQL must be one SELECT")
    if sha256_bytes(action_sql.encode("utf-8")) != _require_sha256(
        action_query.get("sql_sha256"), "action closure SQL SHA-256"
    ):
        raise PolicyOutcomesExportError("action closure SQL identity mismatch")
    action_parameters = _require_list(
        action_query.get("parameters"), "action closure parameters"
    )
    actions = sqlite3.connect(
        f"file:{actions_database_path.as_posix()}?mode=ro&immutable=1", uri=True
    )
    actions.row_factory = sqlite3.Row
    try:
        actions.execute("PRAGMA query_only = ON")
        actions.execute("BEGIN")
        action_rows = actions.execute(action_sql, tuple(action_parameters)).fetchall()
        actions.rollback()
    finally:
        actions.close()
    action_universe: list[dict[str, Any]] = []
    for row in action_rows:
        action_universe.append(
            {
                "action_id": row["vote_event_id"],
                "initiative_id": row["initiative_id"],
                "link_method": row["link_method"],
                "link_confidence_decimal": format(row["confidence"], ".1f"),
                "link_evidence": strict_json_bytes(
                    row["evidence_json"].encode("utf-8"),
                    f"action {row['vote_event_id']} evidence_json",
                ),
                "vote_date": row["vote_date"],
                "legislature": row["legislature"],
                "session_number": row["session_number"],
                "vote_number": row["vote_number"],
                "title": row["title"],
                "totals": {
                    "present": row["totals_present"],
                    "yes": row["totals_yes"],
                    "no": row["totals_no"],
                    "abstain": row["totals_abstain"],
                    "not_voting": row["totals_no_vote"],
                    "absent_normalized": row["totals_absent"],
                    "absent_source_record": row["raw_totals_absent"],
                },
                "source_id": row["source_id"],
                "source_record_id": row["source_record_id"],
                "source_snapshot_date": row["source_snapshot_date"],
                "source_record_content_sha256": row["content_sha256"],
            }
        )
    action_bytes = canonical_json_bytes(action_universe)
    if len(action_universe) != scope["action_candidates"]:
        raise PolicyOutcomesExportError("reconstructed action-universe row count mismatch")
    if len(action_bytes) != scope["action_universe_canonical_bytes"]:
        raise PolicyOutcomesExportError("reconstructed action-universe byte count mismatch")
    if sha256_bytes(action_bytes) != scope["action_universe_sha256"]:
        raise PolicyOutcomesExportError("reconstructed action-universe SHA-256 mismatch")

    indicator_preimage = _require_object(
        closures["indicator"].get("canonical_preimage"), "indicator closure preimage"
    )
    indicator_query = _require_object(
        indicator_preimage.get("query_contract"), "indicator closure query contract"
    )
    series_sql = _require_string(
        indicator_query.get("series_sql_utf8"), "indicator series SQL"
    )
    if not series_sql.lstrip().upper().startswith("SELECT ") or ";" in series_sql:
        raise PolicyOutcomesExportError("indicator series SQL must be one SELECT")
    if sha256_bytes(series_sql.encode("utf-8")) != _require_sha256(
        indicator_query.get("series_sql_sha256"), "indicator series SQL SHA-256"
    ):
        raise PolicyOutcomesExportError("indicator series SQL identity mismatch")
    series_parameters = _require_list(
        indicator_query.get("series_parameters"), "indicator series parameters"
    )
    geography_filter = _require_object(
        indicator_preimage.get("geography_filter"), "indicator geography filter"
    )
    indicators = sqlite3.connect(
        f"file:{indicator_database_path.as_posix()}?mode=ro&immutable=1", uri=True
    )
    indicators.row_factory = sqlite3.Row
    try:
        indicators.execute("PRAGMA query_only = ON")
        indicators.execute("BEGIN")
        series_rows = indicators.execute(series_sql, tuple(series_parameters)).fetchall()
        indicators.rollback()
    finally:
        indicators.close()
    series: list[dict[str, Any]] = []
    for row in series_rows:
        record = dict(row)
        dimensions_raw = _require_string(
            record.pop("dimensions_json"), "indicator dimensions JSON"
        )
        record["dimensions"] = strict_json_bytes(
            dimensions_raw.encode("utf-8"), "indicator dimensions JSON"
        )
        series.append(record)
    eligible = [
        record
        for record in series
        if record.get("geography_code") == geography_filter.get("geography_code")
        and record.get("geography_level") == geography_filter.get("geography_level")
    ]
    eligible_bytes = canonical_json_bytes(eligible)
    if len(eligible) != scope["eligible_indicator_series"]:
        raise PolicyOutcomesExportError("reconstructed eligible-series row count mismatch")
    if len(eligible_bytes) != indicator_preimage.get(
        "geography_eligible_series_canonical_bytes"
    ):
        raise PolicyOutcomesExportError("reconstructed eligible-series byte count mismatch")
    if sha256_bytes(eligible_bytes) != scope["eligible_indicator_series_sha256"]:
        raise PolicyOutcomesExportError("reconstructed eligible-series SHA-256 mismatch")
    return action_bytes, eligible_bytes


def _public_validation_inputs(validation_report: dict[str, Any]) -> dict[str, Any]:
    inputs = _require_object(validation_report.get("inputs"), "validator inputs")
    if inputs.get("physical_database_hashes_are_semantic_identity_inputs") is not False:
        raise PolicyOutcomesExportError(
            "physical database hashes must be excluded from semantic identity"
        )
    return {
        "indicator_raw_source": _require_object(
            inputs.get("indicator_raw_source"), "validator indicator raw source"
        ),
        "manual": _require_object(inputs.get("manual"), "validator manual input"),
        "physical_database_hashes_are_semantic_identity_inputs": False,
        "physical_database_file_facts_included": False,
        "physical_database_file_facts_exclusion_reason": (
            "verified_operationally_but_not_semantic_release_identity"
        ),
    }


def _build_public_validation_evidence(
    *,
    validation_report: dict[str, Any],
    artifacts: dict[str, Any],
    scope: dict[str, Any],
) -> bytes:
    payload = {
        "schema_version": PUBLIC_VALIDATION_EVIDENCE_SCHEMA_VERSION,
        "role": "deterministic_public_projection_of_independent_validation",
        "method_version": METHOD_VERSION,
        "status": "passed",
        "generated_at": validation_report["generated_at"],
        "check_count": validation_report["check_count"],
        "checks": validation_report["checks"],
        "failed_checks": validation_report["failed_checks"],
        "deterministic_fingerprint": validation_report["deterministic_fingerprint"],
        "truth": validation_report["truth"],
        "counts": validation_report["counts"],
        "bounded_universe": scope,
        "semantic": validation_report["semantic"],
        "artifacts": artifacts,
        "inputs": _public_validation_inputs(validation_report),
        "scale_evidence": validation_report["scale_evidence"],
        "source_reconstruction": validation_report["source_reconstruction"],
        "telemetry_policy": {
            "raw_validation_report_is_public_asset": False,
            "physical_database_file_bytes_and_hashes_included": False,
            "filesystem_stat_identity_included": False,
            "reason": "stable_public_release_identity",
        },
    }
    return canonical_json_bytes(payload)


def _build_public_materialization_evidence(
    *,
    validation_report: dict[str, Any],
    validation_evidence_sha256: str,
    artifacts: dict[str, Any],
    scope: dict[str, Any],
) -> bytes:
    """Project deterministic materialization facts from the approved validator.

    The raw operational report deliberately records wall time, peak RSS and
    filesystem stat identities. Those facts are useful locally but make an
    otherwise identical public release change on every rebuild. The public
    asset therefore contains only validation-bound facts and says exactly what
    was excluded.
    """

    artifact_facts = {
        key: artifacts[key]
        for key in (
            "database",
            "database_counts",
            "immutable_bundle_path",
            "latest",
            "manifest",
            "manifest_counts",
            "manifest_sha256",
            "promotion",
            "semantic_json",
        )
    }
    materialization_contract = _require_object(
        artifacts.get("materialization_report"), "materialization report contract"
    )
    payload = {
        "schema_version": PUBLIC_MATERIALIZATION_EVIDENCE_SCHEMA_VERSION,
        "role": "deterministic_public_projection_of_approved_materialization_validation_chain",
        "method_version": METHOD_VERSION,
        "status": "passed",
        "generated_at": validation_report["generated_at"],
        "validation_binding": {
            "validation_evidence_projection_sha256": validation_evidence_sha256,
            "validation_schema_version": validation_report["schema_version"],
            "validation_check_count": validation_report["check_count"],
            "validation_deterministic_fingerprint": validation_report[
                "deterministic_fingerprint"
            ],
            "artifact_set_sha256": artifacts["artifact_set_sha256"],
            "bundle_semantic_sha256": artifacts["bundle_semantic_sha256"],
            "internal_bundle_manifest_sha256": artifacts["manifest_sha256"],
            "raw_materialization_report_schema_version": materialization_contract[
                "schema_version"
            ],
            "raw_materialization_report_status": materialization_contract["status"],
            "raw_materialization_report_whole_hash_authoritative": materialization_contract[
                "whole_report_hash_is_authoritative"
            ],
        },
        "truth": validation_report["truth"],
        "counts": validation_report["counts"],
        "bounded_universe": scope,
        "artifacts": artifact_facts,
        "inputs": _public_validation_inputs(validation_report),
        "scale_evidence": validation_report["scale_evidence"],
        "source_reconstruction": validation_report["source_reconstruction"],
        "telemetry_policy": {
            "raw_materialization_report_is_public_asset": False,
            "volatile_wall_time_seconds_included": False,
            "volatile_peak_rss_included": False,
            "filesystem_stat_identity_included": False,
            "reason": "stable_public_release_identity",
        },
    }
    return canonical_json_bytes(payload)


def _validate_signed_scale_origin() -> dict[str, Any]:
    paths = {
        "signed_scale_origin_manifest": DEFAULT_SIGNED_SCALE_MANIFEST,
        "scale_origin_attestation": DEFAULT_SCALE_ATTESTATION,
        "scale_origin_attestation_signature": DEFAULT_SCALE_ATTESTATION_SIGNATURE,
        "scale_origin_live_verification": DEFAULT_SCALE_LIVE_VERIFICATION,
        "scale_origin_live_parity": DEFAULT_SCALE_LIVE_PARITY,
        "scale_origin_allowed_signers": DEFAULT_SCALE_ALLOWED_SIGNERS,
    }
    for label, path in paths.items():
        if not path.is_file() or path.stat().st_size < 1:
            raise PolicyOutcomesExportError(f"{label} missing")
    manifest_sha = sha256_file(paths["signed_scale_origin_manifest"])
    attestation = strict_json_file(paths["scale_origin_attestation"])
    live_verification = strict_json_file(paths["scale_origin_live_verification"])
    parity = strict_json_file(paths["scale_origin_live_parity"])
    subject = _require_object(attestation.get("subject"), "scale attestation subject")
    digest = _require_object(subject.get("digest"), "scale attestation digest")
    signer = _require_object(attestation.get("signer"), "scale attestation signer")
    if digest.get("sha256") != manifest_sha:
        raise PolicyOutcomesExportError("signed scale manifest disagrees with attestation")
    _expect_values(
        signer,
        {
            "identity": SCALE_ORIGIN_SIGNER_IDENTITY,
            "key_type": "ssh-ed25519",
            "public_key_fingerprint": SCALE_ORIGIN_PUBLIC_KEY_FINGERPRINT,
            "signature_namespace": "vota-con-la-chola-snapshot-v1",
        },
        "scale attestation signer",
    )
    allowed_signers_sha = sha256_file(paths["scale_origin_allowed_signers"])
    if allowed_signers_sha != APPROVED_SCALE_ALLOWED_SIGNERS_SHA256:
        raise PolicyOutcomesExportError("scale origin allowed-signers trust root drift")
    try:
        cryptographic_verification = verify_signed_attestation(
            manifest_path=paths["signed_scale_origin_manifest"],
            attestation_path=paths["scale_origin_attestation"],
            signature_path=paths["scale_origin_attestation_signature"],
            allowed_signers_path=paths["scale_origin_allowed_signers"],
            signer_identity=SCALE_ORIGIN_SIGNER_IDENTITY,
        )
    except (OSError, SnapshotAttestationError) as exc:
        raise PolicyOutcomesExportError(
            f"scale origin cryptographic verification could not run: {exc}"
        ) from exc
    if cryptographic_verification.get("passed") is not True:
        errors = cryptographic_verification.get("errors")
        detail = "; ".join(str(item) for item in errors) if isinstance(errors, list) else "unknown failure"
        raise PolicyOutcomesExportError(
            f"scale origin cryptographic verification failed: {detail}"
        )
    cryptographic_checks = _require_object(
        cryptographic_verification.get("checks"),
        "scale origin cryptographic verification checks",
    )
    attestation_sha = sha256_file(paths["scale_origin_attestation"])
    signature_sha = sha256_file(paths["scale_origin_attestation_signature"])
    _expect_values(
        cryptographic_checks,
        {
            "manifest_sha256": manifest_sha,
            "attestation_sha256": attestation_sha,
            "signature_sha256": signature_sha,
            "signature_verified": True,
            "signer_identity": SCALE_ORIGIN_SIGNER_IDENTITY,
            "official_real_records_only": True,
            "official_public_domain_personal_information_retained": True,
            "synthetic_or_mock_records": False,
        },
        "scale origin cryptographic verification checks",
    )
    _expect_values(
        live_verification,
        {
            "status": "verified_live_signed_snapshot",
            "passed": True,
            "snapshot_date": subject.get("snapshot_date"),
        },
        "live signed-scale verification",
    )
    live_checks = _require_object(
        live_verification.get("checks"), "live signed-scale verification checks"
    )
    _expect_values(
        live_checks,
        {
            "manifest_sha256": manifest_sha,
            "attestation_sha256": attestation_sha,
            "signature_sha256": signature_sha,
            "signature_verified": True,
            "official_real_records_only": True,
            "official_public_domain_personal_information_retained": True,
            "synthetic_or_mock_records": False,
        },
        "live signed-scale verification checks",
    )
    _expect_values(
        parity,
        {
            "status": "verified_current_scale_origin",
            "passed": True,
            "snapshot_date": subject.get("snapshot_date"),
        },
        "live scale-origin parity",
    )
    parity_checks = _require_object(parity.get("checks"), "live scale parity checks")
    if parity_checks.get("downloaded_manifest_sha256") != manifest_sha:
        raise PolicyOutcomesExportError("live scale parity manifest mismatch")
    return {
        "paths": paths,
        "facts": {
            "linkage_state": "verified_upstream_scale_origin_not_attesting_this_outcome_package",
            "outcome_package_in_signed_scale_origin": False,
            "scale_origin_signature_verified": cryptographic_checks[
                "signature_verified"
            ],
            "scale_origin_live_parity_verified": True,
            "scale_origin_snapshot_date": subject.get("snapshot_date"),
            "scale_origin_signer_identity": SCALE_ORIGIN_SIGNER_IDENTITY,
            "scale_origin_public_key_fingerprint": (
                SCALE_ORIGIN_PUBLIC_KEY_FINGERPRINT
            ),
            "scale_origin_allowed_signers_sha256": allowed_signers_sha,
            "scale_origin_manifest_sha256": manifest_sha,
            "scale_origin_manifest_url": _require_https(
                subject.get("uri"), "scale attestation subject.uri"
            ),
            "scale_origin_attestation_sha256": attestation_sha,
            "scale_origin_signature_sha256": signature_sha,
        },
    }


def validate_source_contract(validation_report: Path) -> dict[str, Any]:
    """Validate approved report plus every source/artifact it authorizes."""

    report_path = validation_report.resolve()
    try:
        report_path.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise PolicyOutcomesExportError("validation report must live inside repository") from exc
    raw_report_sha = sha256_file(report_path)
    report = strict_json_file(report_path)
    _expect_values(
        report,
        {
            "schema_version": VALIDATOR_SCHEMA_VERSION,
            "method_version": METHOD_VERSION,
            "status": "passed",
            "failed_checks": [],
        },
        "validator report",
    )
    generated_at = _require_string(report.get("generated_at"), "validator generated_at")
    if not generated_at.endswith("Z"):
        raise PolicyOutcomesExportError("validator generated_at must be UTC")
    checks = _require_object(report.get("checks"), "validator checks")
    if report.get("check_count") != len(checks) or not checks:
        raise PolicyOutcomesExportError("validator check count mismatch")
    if any(value is not True for value in checks.values()):
        raise PolicyOutcomesExportError("validator contains non-passing check")
    validation_fingerprint = _require_sha256(
        report.get("deterministic_fingerprint"), "validator deterministic fingerprint"
    )

    artifacts = _require_object(report.get("artifacts"), "validator artifacts")
    latest_path = _verify_reported_file(artifacts.get("latest"), "validator latest")
    internal_manifest_path = _verify_reported_file(
        artifacts.get("manifest"), "validator internal manifest"
    )
    database_path = _verify_reported_file(artifacts.get("database"), "validator database")
    semantic_path = _verify_reported_file(
        artifacts.get("semantic_json"), "validator semantic JSON"
    )
    latest = strict_json_file(latest_path)
    internal_manifest = strict_json_file(internal_manifest_path)
    bundle = strict_json_file(semantic_path)

    artifact_set_sha = _require_sha256(
        artifacts.get("artifact_set_sha256"), "validator artifact set SHA-256"
    )
    bundle_semantic_sha = _require_sha256(
        artifacts.get("bundle_semantic_sha256"), "validator bundle semantic SHA-256"
    )
    internal_manifest_sha = _require_sha256(
        artifacts.get("manifest_sha256"), "validator internal manifest SHA-256"
    )
    if internal_manifest_sha != artifacts["manifest"].get("sha256"):
        raise PolicyOutcomesExportError("internal manifest hashes disagree")
    _expect_values(
        latest,
        {
            "format_version": "outcome_context_candidate_pointer_v1",
            "publication_state": "not_released",
            "artifact_set_sha256": artifact_set_sha,
            "bundle_semantic_sha256": bundle_semantic_sha,
            "manifest_sha256": internal_manifest_sha,
            "immutable_bundle_path": artifacts.get("immutable_bundle_path"),
            "candidate_version_id": artifacts.get("candidate_version_id"),
            "candidate_version_identity_sha256": artifacts.get(
                "candidate_version_identity_sha256"
            ),
            "generated_at": generated_at,
        },
        "internal latest pointer",
    )
    _expect_values(
        internal_manifest,
        {
            "format_version": "outcome_context_candidate_bundle_manifest_v1",
            "method_version": METHOD_VERSION,
            "artifact_role": "internal_preproduction_candidate_bundle_not_a_release",
            "artifact_set_sha256": artifact_set_sha,
            "bundle_semantic_sha256": bundle_semantic_sha,
            "human_review_completed": False,
            "release_created": False,
            "published": False,
            "generated_at": generated_at,
        },
        "internal bundle manifest",
    )
    descriptor = _require_object(
        internal_manifest.get("artifact_set_descriptor"), "artifact set descriptor"
    )
    if sha256_bytes(canonical_json_bytes(descriptor)) != artifact_set_sha:
        raise PolicyOutcomesExportError("artifact set identity mismatch")
    _expect_values(
        bundle,
        {
            "format_version": "outcome_context_candidate_bundle_v1",
            "method_version": METHOD_VERSION,
            "artifact_role": "internal_preproduction_candidate_bundle_not_a_release",
            "generated_at": generated_at,
        },
        "semantic bundle",
    )
    if sha256_bytes(canonical_json_bytes(_bundle_semantic_projection(bundle))) != bundle_semantic_sha:
        raise PolicyOutcomesExportError("semantic bundle identity mismatch")
    if bundle.get("counts") != internal_manifest.get("counts"):
        raise PolicyOutcomesExportError("semantic bundle and manifest counts disagree")
    if bundle.get("counts") != artifacts.get("manifest_counts"):
        raise PolicyOutcomesExportError("semantic bundle and validator counts disagree")

    truth, counts, _scope_truth = _validate_zero_state(report, bundle)
    scope = _validate_scope_closure(report, bundle, counts)
    policy = _require_object(bundle.get("policy"), "bundle policy")
    _expect_values(
        policy,
        {
            "real_data_only": True,
            "synthetic_or_mock_rows": 0,
            **CLAIM_POLICY,
            "directional_countable": False,
            "ranking_eligible": False,
            "public_domain_identity_policy": PUBLIC_IDENTITY_POLICY,
        },
        "bundle policy",
    )

    versions = _require_list(bundle.get("link_versions"), "bundle link versions")
    if len(versions) != 1:
        raise PolicyOutcomesExportError("one candidate version required")
    version = _require_object(versions[0], "candidate version")
    _expect_values(
        version,
        {
            "version_state": "preproduction_candidate",
            "evidence_level": truth["evidence_level"],
            "candidate_status": truth["candidate_status"],
            "machine_audit_state": "machine_validated",
            "human_review_required": True,
            "human_review_completed": False,
            "published": False,
            "directional_countable": False,
            "ranking_eligible": False,
        },
        "candidate version",
    )
    _expect_values(version.get("claim_policy"), policy, "candidate claim policy")

    action = _require_object(version.get("action"), "candidate Senate input")
    indicator = _require_object(version.get("indicator"), "candidate Eurostat input")
    participant_contract = _require_object(
        version.get("participant_contract"), "candidate participant contract"
    )
    reconstruction = _require_object(
        report.get("source_reconstruction"), "validator source reconstruction"
    )
    vote_sha = _require_sha256(
        action.get("normalized_source_record_payload_sha256"), "Senate vote record SHA-256"
    )
    initiative_sha = _require_sha256(
        action.get("initiative_normalized_source_record_payload_sha256"),
        "Senate initiative record SHA-256",
    )
    indicator_sha = _require_sha256(
        indicator.get("source_content_sha256"), "Eurostat source SHA-256"
    )
    if vote_sha != reconstruction.get("vote_source_record_content_sha256"):
        raise PolicyOutcomesExportError("Senate vote source reconstruction mismatch")
    if initiative_sha != reconstruction.get("initiative_source_record_content_sha256"):
        raise PolicyOutcomesExportError("Senate initiative source reconstruction mismatch")
    if indicator_sha != reconstruction.get("indicator_source_content_sha256"):
        raise PolicyOutcomesExportError("Eurostat source reconstruction mismatch")
    for label, value in (
        ("Senate vote page", action.get("official_vote_page_url")),
        ("Senate vote file", action.get("official_vote_file_url")),
        ("Senate initiative", action.get("official_initiative_url")),
        ("Eurostat source", indicator.get("source_url")),
    ):
        _require_https(value, label)
    original_vote_xml = _expect_values(
        action.get("original_vote_xml"),
        {
            "bytes": None,
            "capture_state": "absent_from_current_snapshot",
            "content_sha256": None,
            "normalized_source_record_is_original_bytes": False,
        },
        "original vote XML gap",
    )

    material_fact = _require_object(
        artifacts.get("materialization_report"), "materialization report fact"
    )
    material_path = _repo_file(material_fact.get("path"), "materialization report")
    (
        _material,
        actions_database_path,
        indicator_database_path,
        indicator_raw_path,
    ) = _validate_materialization_report(
        material_path,
        validation_report=report,
        artifacts=artifacts,
        scope=scope,
    )
    indicator_bytes = _require_int(indicator.get("source_bytes"), "Eurostat source bytes", minimum=1)
    if indicator_raw_path.stat().st_size != indicator_bytes or sha256_file(indicator_raw_path) != indicator_sha:
        raise PolicyOutcomesExportError("Eurostat raw capture disagrees with candidate input")

    vote_bytes_count = _require_int(
        action.get("normalized_source_record_payload_bytes"),
        "Senate vote record bytes",
        minimum=1,
    )
    initiative_bytes_count = _require_int(
        action.get("initiative_normalized_source_record_payload_bytes"),
        "Senate initiative record bytes",
        minimum=1,
    )
    vote_raw = _read_exact_source_payload(
        actions_database_path,
        source_id=_require_string(action.get("source_id"), "Senate vote source id"),
        source_record_id=_require_string(
            action.get("source_record_id"), "Senate vote source record id"
        ),
        expected_sha256=vote_sha,
        expected_bytes=vote_bytes_count,
    )
    initiative_raw = _read_exact_source_payload(
        actions_database_path,
        source_id=_require_string(
            action.get("initiative_source_id"), "Senate initiative source id"
        ),
        source_record_id=_require_string(
            action.get("initiative_source_record_id"), "Senate initiative source record id"
        ),
        expected_sha256=initiative_sha,
        expected_bytes=initiative_bytes_count,
    )

    participant_refs = _require_list(bundle.get("participant_refs"), "participant refs")
    retained_names = []
    for index, ref in enumerate(participant_refs):
        item = _require_object(ref, f"participant ref {index}")
        retained_names.append(
            _require_string(item.get("official_member_name"), f"participant ref {index} name")
        )
        if item.get("official_label_authoritative") is not True:
            raise PolicyOutcomesExportError("official participant label was not retained")
        if item.get("vote_source_record_content_sha256") != vote_sha:
            raise PolicyOutcomesExportError("participant source hash mismatch")
    official_names_retained = _require_int(
        truth.get("official_public_names_retained"),
        "truth.official_public_names_retained",
        minimum=1,
    )
    if len(participant_refs) != official_names_retained:
        raise PolicyOutcomesExportError("official participant row retention mismatch")
    if len(set(retained_names)) != official_names_retained:
        raise PolicyOutcomesExportError("official participant name retention mismatch")
    _expect_values(
        participant_contract,
        {
            "records_total": official_names_retained,
            "distinct_official_names": official_names_retained,
            "official_names_and_ballot_labels_authoritative": True,
            "pseudonymization_forbidden": True,
        },
        "participant contract",
    )

    action_universe_raw, eligible_series_raw = _reconstruct_scope_universe_assets(
        actions_database_path=actions_database_path,
        indicator_database_path=indicator_database_path,
        bundle=bundle,
        scope=scope,
    )
    validation_evidence_raw = _build_public_validation_evidence(
        validation_report=report,
        artifacts=artifacts,
        scope=scope,
    )
    validation_evidence_sha = sha256_bytes(validation_evidence_raw)
    if validation_evidence_sha != APPROVED_VALIDATION_EVIDENCE_SHA256:
        raise PolicyOutcomesExportError(
            "validation evidence is not approved release identity"
        )
    materialization_evidence_raw = _build_public_materialization_evidence(
        validation_report=report,
        validation_evidence_sha256=validation_evidence_sha,
        artifacts=artifacts,
        scope=scope,
    )

    signed_scale = _validate_signed_scale_origin()
    return {
        "report_path": report_path,
        "raw_report_sha256": raw_report_sha,
        "report_sha256": validation_evidence_sha,
        "report": report,
        "materialization_path": material_path,
        "latest_path": latest_path,
        "internal_manifest_path": internal_manifest_path,
        "database_path": database_path,
        "semantic_path": semantic_path,
        "indicator_raw_path": indicator_raw_path,
        "vote_raw": vote_raw,
        "initiative_raw": initiative_raw,
        "action_universe_raw": action_universe_raw,
        "eligible_series_raw": eligible_series_raw,
        "validation_evidence_raw": validation_evidence_raw,
        "materialization_evidence_raw": materialization_evidence_raw,
        "generated_at": generated_at,
        "validation_check_count": len(checks),
        "validation_fingerprint": validation_fingerprint,
        "artifact_set_sha256": artifact_set_sha,
        "bundle_semantic_sha256": bundle_semantic_sha,
        "internal_manifest_sha256": internal_manifest_sha,
        "truth": truth,
        "counts": counts,
        "scope": scope,
        "action": action,
        "indicator": indicator,
        "participant_contract": participant_contract,
        "official_names_retained": official_names_retained,
        "original_vote_xml": original_vote_xml,
        "signed_scale": signed_scale,
    }


def _build_asset_specs(source: dict[str, Any]) -> dict[str, dict[str, Any]]:
    scale_paths = source["signed_scale"]["paths"]
    return {
        "action_candidate_universe": {
            "filename": "action-candidate-universe.canonical.json",
            "data": source["action_universe_raw"],
            "media_type": "application/json",
            "role": "exact_canonical_bounded_action_candidate_universe",
        },
        "eligible_indicator_series_universe": {
            "filename": "eligible-indicator-series-universe.canonical.json",
            "data": source["eligible_series_raw"],
            "media_type": "application/json",
            "role": "exact_canonical_bounded_eligible_indicator_series_universe",
        },
        "senate_vote_normalized_record": {
            "filename": "senate-vote-normalized-raw-payload.json",
            "data": source["vote_raw"],
            "media_type": "application/json",
            "role": "exact_normalized_senate_vote_source_record",
        },
        "senate_initiative_normalized_record": {
            "filename": "senate-initiative-normalized-raw-payload.json",
            "data": source["initiative_raw"],
            "media_type": "application/json",
            "role": "exact_normalized_senate_initiative_source_record",
        },
        "eurostat_raw_capture": {
            "filename": "eurostat-nama_10r_3gdp-raw.json",
            "source": source["indicator_raw_path"],
            "media_type": "application/json",
            "role": "exact_original_eurostat_source_capture",
        },
        "independent_validation_evidence_projection": {
            "filename": "outcome-context-validation-evidence.json",
            "data": source["validation_evidence_raw"],
            "media_type": "application/json",
            "role": "deterministic_projection_of_independent_validation",
        },
        "materialization_evidence_projection": {
            "filename": "outcome-context-materialization-evidence.json",
            "data": source["materialization_evidence_raw"],
            "media_type": "application/json",
            "role": "deterministic_projection_of_approved_materialization_validation_chain",
        },
        "semantic_evidence": {
            "filename": "outcome-context-candidates-v1.json",
            "source": source["semantic_path"],
            "media_type": "application/json",
            "role": "exact_semantic_evidence_with_official_public_names_retained",
        },
        "sqlite_bundle": {
            "filename": "outcome-context-candidates-v1.db",
            "source": source["database_path"],
            "media_type": "application/vnd.sqlite3",
            "role": "exact_append_only_sqlite_candidate_bundle",
        },
        "internal_bundle_manifest": {
            "filename": "internal-bundle-manifest.json",
            "source": source["internal_manifest_path"],
            "media_type": "application/json",
            "role": "exact_internal_candidate_bundle_manifest",
        },
        "internal_latest_pointer": {
            "filename": "internal-latest-pointer.json",
            "source": source["latest_path"],
            "media_type": "application/json",
            "role": "exact_internal_not_released_pointer",
        },
        "signed_scale_origin_manifest": {
            "filename": "signed-scale-origin-manifest.json",
            "source": scale_paths["signed_scale_origin_manifest"],
            "media_type": "application/json",
            "role": "verified_upstream_signed_scale_origin_manifest_not_attesting_this_package",
        },
        "scale_origin_attestation": {
            "filename": "scale-origin-attestation.json",
            "source": scale_paths["scale_origin_attestation"],
            "media_type": "application/json",
            "role": "signed_scale_origin_attestation_not_covering_this_package",
        },
        "scale_origin_attestation_signature": {
            "filename": "scale-origin-attestation.json.sig",
            "source": scale_paths["scale_origin_attestation_signature"],
            "media_type": "application/octet-stream",
            "role": "ssh_ed25519_scale_origin_signature_not_covering_this_package",
        },
        "scale_origin_allowed_signers": {
            "filename": "scale-origin.allowed_signers",
            "source": scale_paths["scale_origin_allowed_signers"],
            "media_type": "text/plain",
            "role": "pinned_public_trust_root_for_upstream_scale_origin",
        },
        "scale_origin_live_verification": {
            "filename": "scale-origin-live-signed-verification.json",
            "source": scale_paths["scale_origin_live_verification"],
            "media_type": "application/json",
            "role": "live_signature_verification_for_upstream_scale_origin",
        },
        "scale_origin_live_parity": {
            "filename": "scale-origin-live-parity.json",
            "source": scale_paths["scale_origin_live_parity"],
            "media_type": "application/json",
            "role": "live_parity_verification_for_upstream_scale_origin",
        },
    }


def _asset_facts(specs: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    facts: dict[str, dict[str, Any]] = {}
    for key, spec in specs.items():
        public_path = f"assets/{spec['filename']}"
        if "data" in spec:
            facts[key] = _bytes_fact(
                spec["data"],
                public_path=public_path,
                media_type=spec["media_type"],
                role=spec["role"],
            )
        else:
            facts[key] = _file_fact(
                spec["source"],
                public_path=public_path,
                media_type=spec["media_type"],
                role=spec["role"],
            )
    return facts


def _source_inputs(source: dict[str, Any]) -> dict[str, Any]:
    action = source["action"]
    indicator = source["indicator"]
    return {
        "relationship_state": "selected_together_in_one_pending_methodological_candidate",
        "validation_state": "not_a_validated_outcome_link",
        "senate_vote": {
            "source_id": action["source_id"],
            "source_snapshot_date": action["source_snapshot_date"],
            "official_page_url": action["official_vote_page_url"],
            "official_file_url": action["official_vote_file_url"],
            "normalized_record_bytes": action["normalized_source_record_payload_bytes"],
            "normalized_record_sha256": action[
                "normalized_source_record_payload_sha256"
            ],
            "original_xml_capture_state": source["original_vote_xml"]["capture_state"],
        },
        "senate_initiative": {
            "source_id": action["initiative_source_id"],
            "source_snapshot_date": action["initiative_source_snapshot_date"],
            "official_url": action["official_initiative_url"],
            "normalized_record_bytes": action[
                "initiative_normalized_source_record_payload_bytes"
            ],
            "normalized_record_sha256": action[
                "initiative_normalized_source_record_payload_sha256"
            ],
        },
        "eurostat_indicator": {
            "source_id": indicator["source_id"],
            "dataset_code": indicator["dataset_code"],
            "source_snapshot_date": indicator["source_snapshot_date"],
            "source_updated_at": indicator["source_updated_at"],
            "official_url": indicator["source_url"],
            "source_bytes": indicator["source_bytes"],
            "source_sha256": indicator["source_content_sha256"],
            "comparison_state": indicator["comparison_state"],
        },
    }


def _validation_identity(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "passed",
        "schema_version": VALIDATOR_SCHEMA_VERSION,
        "check_count": source["validation_check_count"],
        "deterministic_fingerprint": source["validation_fingerprint"],
        "report_sha256": source["report_sha256"],
        "artifact_set_sha256": source["artifact_set_sha256"],
        "bundle_semantic_sha256": source["bundle_semantic_sha256"],
        "internal_bundle_manifest_sha256": source["internal_manifest_sha256"],
    }


def _package_identity_descriptor(
    source: dict[str, Any], asset_facts: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    return {
        "identity_contract_version": PACKAGE_IDENTITY_CONTRACT_VERSION,
        "contract_date": source["generated_at"],
        "method_version": METHOD_VERSION,
        "publication_state": (
            "one_pending_methodological_candidate_disclosed_zero_validated_outcome_links"
        ),
        "validation_identity": _validation_identity(source),
        "bounded_universe": source["scope"],
        "asset_facts": asset_facts,
        "official_public_names_retained": source["official_names_retained"],
        "signed_scale_origin_linkage": source["signed_scale"]["facts"],
    }


def build_export_plan(validation_report: Path = DEFAULT_VALIDATION_REPORT) -> dict[str, Any]:
    source = validate_source_contract(validation_report)
    specs = _build_asset_specs(source)
    assets = _asset_facts(specs)
    identity_descriptor = _package_identity_descriptor(source, assets)
    package_id = sha256_bytes(canonical_json_bytes(identity_descriptor))
    manifest_path = f"/policy-outcomes/evidence/{package_id}/manifest.json"
    source_inputs = _source_inputs(source)
    validation_identity = _validation_identity(source)
    status = {
        "schema_version": PUBLIC_SCHEMA_VERSION,
        "public_payload_kind": "pending_methodological_candidate_status_with_evidence",
        "method_version": METHOD_VERSION,
        "contract_date": source["generated_at"],
        "publication_state": (
            "one_pending_methodological_candidate_disclosed_zero_validated_outcome_links"
        ),
        "pipeline": {
            "scale_stage": source["truth"]["scale_stage"],
            "evidence_level": source["truth"]["evidence_level"],
            "pending_methodological_candidates_disclosed": 1,
            "human_reviewed_pairs": source["counts"]["human_reviewed_pairs"],
            "human_reviews": source["counts"]["reviews"],
            "validated_outcome_links": 0,
            "published_outcome_links": source["counts"]["published_links"],
            "releases": source["counts"]["releases"],
            "release_memberships": source["counts"]["release_memberships"],
            "human_review_required": True,
        },
        "bounded_universe": source["scope"],
        "selected_inputs": source_inputs,
        "claim_boundary": CLAIM_POLICY,
        "data_policy": {
            "real_data_only": True,
            "synthetic_or_mock_rows": 0,
            "official_public_identity_policy": PUBLIC_IDENTITY_POLICY,
            "official_public_names_retained_in_semantic_evidence": source[
                "official_names_retained"
            ],
            "official_public_names_removed_or_pseudonymized": 0,
            "status_contains_individual_participant_rows": False,
        },
        "validation_identity": validation_identity,
        "evidence_package": {
            "package_id": package_id,
            "manifest_path": manifest_path,
            "manifest_authentication_state": "unsigned",
            "all_assets_content_addressed": True,
        },
    }
    status_raw = json_file_bytes(status)
    status_fact = {
        "path": "/policy-outcomes/data/policy-outcomes.json",
        "bytes": len(status_raw),
        "sha256": sha256_bytes(status_raw),
        "schema_version": PUBLIC_SCHEMA_VERSION,
    }
    manifest = {
        "schema_version": PUBLIC_MANIFEST_SCHEMA_VERSION,
        "identity_contract_version": PACKAGE_IDENTITY_CONTRACT_VERSION,
        "package_id": package_id,
        "contract_date": source["generated_at"],
        "package_role": "public_verification_evidence_for_one_pending_methodological_candidate",
        "publication_state": status["publication_state"],
        "status": status_fact,
        "source_inputs": source_inputs,
        "bounded_universe": source["scope"],
        "validation_identity": validation_identity,
        "identity_retention": {
            "official_public_names_retained": source["official_names_retained"],
            "official_public_names_removed_or_pseudonymized": 0,
            "semantic_evidence_asset_key": "semantic_evidence",
            "semantic_evidence_copied_byte_for_byte": True,
        },
        "claim_boundary": CLAIM_POLICY,
        "authentication": {
            "state": "unsigned",
            "signature_algorithm": "none",
            "signer_identity": None,
            "note": "SHA-256 integrity is bound here; this public evidence manifest has no signature.",
        },
        "signed_scale_origin_linkage": source["signed_scale"]["facts"],
        "assets": assets,
    }
    return {
        "source": source,
        "specs": specs,
        "assets": assets,
        "identity_descriptor": identity_descriptor,
        "package_id": package_id,
        "status": status,
        "status_raw": status_raw,
        "manifest": manifest,
        "manifest_raw": json_file_bytes(manifest),
    }


def build_public_status(validation_report: Path = DEFAULT_VALIDATION_REPORT) -> dict[str, Any]:
    """Return deterministic v3 status without writing files."""

    return build_export_plan(validation_report)["status"]


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
        temporary_name = None
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_bytes(path, json_file_bytes(payload))


def _atomic_copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with source.open("rb") as input_handle, tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as output_handle:
            temporary_name = output_handle.name
            shutil.copyfileobj(input_handle, output_handle, length=4 * 1024 * 1024)
            output_handle.flush()
            os.fsync(output_handle.fileno())
        os.replace(temporary_name, destination)
        temporary_name = None
        directory_fd = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def _commit_immutable_bytes(path: Path, data: bytes) -> None:
    if path.exists():
        if not path.is_file() or path.read_bytes() != data:
            raise PolicyOutcomesExportError(f"immutable evidence path drift: {_safe_label(path)}")
        return
    _atomic_write_bytes(path, data)


def _commit_immutable_file(path: Path, source: Path, expected_fact: dict[str, Any]) -> None:
    if path.exists():
        if (
            not path.is_file()
            or path.stat().st_size != expected_fact["bytes"]
            or sha256_file(path) != expected_fact["sha256"]
        ):
            raise PolicyOutcomesExportError(f"immutable evidence path drift: {_safe_label(path)}")
        return
    _atomic_copy_file(source, path)
    if path.stat().st_size != expected_fact["bytes"] or sha256_file(path) != expected_fact["sha256"]:
        raise PolicyOutcomesExportError(f"copied evidence integrity failure: {_safe_label(path)}")


def default_evidence_root(out: Path) -> Path:
    if out.parent.name == "data":
        return out.parent.parent / "evidence"
    return out.parent / "evidence"


def export_public_package(
    validation_report: Path,
    out: Path,
    evidence_root: Path | None = None,
) -> dict[str, Any]:
    plan = build_export_plan(validation_report)
    root = evidence_root or default_evidence_root(out)
    package_dir = root / plan["package_id"]
    assets_dir = package_dir / "assets"

    for key, spec in plan["specs"].items():
        destination = assets_dir / spec["filename"]
        expected_fact = plan["assets"][key]
        if "data" in spec:
            _commit_immutable_bytes(destination, spec["data"])
        else:
            _commit_immutable_file(destination, spec["source"], expected_fact)
        if destination.stat().st_size != expected_fact["bytes"]:
            raise PolicyOutcomesExportError(f"evidence byte mismatch after commit: {key}")
        if sha256_file(destination) != expected_fact["sha256"]:
            raise PolicyOutcomesExportError(f"evidence hash mismatch after commit: {key}")

    # Mutable status first. Public manifest is last, so any interruption fails closed.
    _atomic_write_bytes(out, plan["status_raw"])
    _commit_immutable_bytes(package_dir / "manifest.json", plan["manifest_raw"])
    return {
        **plan,
        "out": out,
        "package_dir": package_dir,
        "manifest_path": package_dir / "manifest.json",
        "manifest_sha256": sha256_bytes(plan["manifest_raw"]),
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = export_public_package(
            args.validation_report,
            args.out,
            args.evidence_root,
        )
    except (OSError, sqlite3.Error, UnicodeError, ValueError, KeyError, PolicyOutcomesExportError) as exc:
        print(f"ERROR policy outcomes public evidence: {exc}")
        return 2
    print(
        "OK policy outcomes v3 evidence "
        f"status={_safe_label(args.out)} "
        f"status_sha256={sha256_bytes(result['status_raw'])} "
        f"manifest={_safe_label(result['manifest_path'])} "
        f"manifest_sha256={result['manifest_sha256']} "
        f"assets={len(result['assets'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
