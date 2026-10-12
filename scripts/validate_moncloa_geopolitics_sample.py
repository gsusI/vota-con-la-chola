#!/usr/bin/env python3
"""Validate the real-only La Moncloa geopolitical action release."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DB = REPO_ROOT / "etl/data/staging/agreements-moncloa-mvp.db"
DEFAULT_DB = REPO_ROOT / "etl/data/staging/geopolitics-moncloa-mvp.db"
DEFAULT_PUBLISHED = REPO_ROOT / "etl/data/published/geopolitics-moncloa-sample.json"
DEFAULT_PUBLIC = (
    REPO_ROOT / "ui/site/public/geopolitics/data/moncloa-sample.json"
)
DEFAULT_REPORT = (
    REPO_ROOT
    / "docs/etl/sprints/GEOPOLITICS-20260819/evidence/moncloa-geopolitics-validation.json"
)
CAPTURE_PATH = (
    REPO_ROOT
    / "etl/data/raw/moncloa_referencias/2026/02/16/"
    "moncloa_referencias_20260216T141256Z.json"
)
CAPTURE_BYTES = 21_234
CAPTURE_SHA256 = "ab08b7dc09a46c890f055e95fdeac5e7d716a5023f8792f19ce440a239271ddf"
EXPECTED_RECORD_IDS = {
    "referencia:20260113-referencia-rueda-de-prensa-ministros.aspx",
    "referencia:20260127-referencia-rueda-de-prensa-ministros.aspx",
}
EXPECTED_ACTORS = {
    "Consejo de Ministros",
    "Gobierno de España / La Moncloa",
    "Cortes Generales",
    "Reino de España",
    "Unión Europea",
    "Comunidad Europea de la Energía Atómica",
    "Sultanato de Omán",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-db", type=Path, default=DEFAULT_SOURCE_DB)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--published", type=Path, default=DEFAULT_PUBLISHED)
    parser.add_argument("--public", type=Path, default=DEFAULT_PUBLIC)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def load_database(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise RuntimeError(f"missing database: {path}")
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def main() -> int:
    args = parse_args()
    errors: list[str] = []
    for path in (args.source_db, args.db, args.published, args.public, CAPTURE_PATH):
        if not path.is_file():
            errors.append(f"missing required input: {path.name}")
    if errors:
        report = {
            "schema_version": "moncloa_geopolitics_validation_v1",
            "status": "error",
            "errors": errors,
        }
        atomic_write(args.report_out, report)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 1

    published_bytes = args.published.read_bytes()
    public_bytes = args.public.read_bytes()
    require(published_bytes == public_bytes, "published/public byte mismatch", errors)
    artifact_sha256 = sha256_bytes(published_bytes)
    artifact = json.loads(published_bytes)
    require(
        artifact.get("schema_version") == "geopolitical_actions_sample_v1",
        "schema version mismatch",
        errors,
    )
    release_id = str(artifact.get("release_id") or "")
    core = dict(artifact)
    core.pop("release_id", None)
    require(
        release_id == sha256_text(canonical_json(core)),
        "release hash mismatch",
        errors,
    )

    capture_size = CAPTURE_PATH.stat().st_size
    capture_hash = sha256_file(CAPTURE_PATH)
    require(capture_size == CAPTURE_BYTES, "official capture byte mismatch", errors)
    require(capture_hash == CAPTURE_SHA256, "official capture hash mismatch", errors)
    capture_payload = json.loads(CAPTURE_PATH.read_text(encoding="utf-8"))
    require(
        isinstance(capture_payload.get("records"), list)
        and len(capture_payload["records"]) == 20,
        "official capture record count mismatch",
        errors,
    )

    policy = artifact.get("policy") or {}
    require(policy.get("real_data_only") is True, "real-only policy missing", errors)
    require(policy.get("synthetic_or_mock") is False, "synthetic/mock policy drift", errors)
    require(
        policy.get("official_public_domain_information_retained") is True,
        "public identity retention policy missing",
        errors,
    )
    for inference_key in (
        "treaty_entry_into_force_inferred",
        "implementation_inferred",
        "alignment_inferred",
        "influence_inferred",
        "causal_outcome_inferred",
    ):
        require(policy.get(inference_key) is False, f"unsafe policy: {inference_key}", errors)

    records = artifact.get("records") or []
    require(len(records) == 2, "public artifact must contain exactly 2 actions", errors)
    coverage = artifact.get("coverage") or {}
    expected_coverage = {
        "source_records": 20,
        "qualifying_foreign_policy_records": 2,
        "actions": 2,
        "actors": 11,
        "evidence": 2,
        "topics": 4,
        "positions": 0,
        "position_evidence": 0,
        "links": 2,
        "later_observations": 0,
        "not_assessed_binding": 2,
        "not_assessed_entry_into_force": 2,
        "not_assessed_implementation": 2,
        "not_assessed_outcomes": 2,
        "explicit_positions": 0,
    }
    for key, value in expected_coverage.items():
        require(coverage.get(key) == value, f"coverage mismatch: {key}", errors)

    materialized = load_database(args.db)
    source = load_database(args.source_db)
    try:
        db_counts = {
            "actions": count(materialized, "geopolitical_actions"),
            "actors": count(materialized, "geopolitical_action_actors"),
            "evidence": count(materialized, "geopolitical_action_evidence"),
            "topics": count(materialized, "geopolitical_action_topics"),
            "positions": count(materialized, "geopolitical_positions"),
            "position_evidence": count(materialized, "geopolitical_position_evidence"),
            "links": count(materialized, "geopolitical_action_links"),
            "later_observations": count(materialized, "geopolitical_observations"),
        }
        require(db_counts == {key: expected_coverage[key] for key in db_counts}, "database counts mismatch", errors)
        fk_rows = [tuple(row) for row in materialized.execute("PRAGMA foreign_key_check")]
        integrity = str(materialized.execute("PRAGMA integrity_check").fetchone()[0])
        require(not fk_rows, f"foreign key violations: {len(fk_rows)}", errors)
        require(integrity == "ok", f"integrity check failed: {integrity}", errors)

        db_rows = materialized.execute(
            """
            SELECT ga.*, sr.raw_payload AS source_raw_payload, a.summary AS agreement_summary
            FROM geopolitical_actions AS ga
            JOIN source_records AS sr ON sr.source_record_pk = ga.source_record_pk
            JOIN agreements AS a ON a.agreement_id = ga.related_agreement_id
            ORDER BY ga.action_date, ga.source_record_id
            """
        ).fetchall()
        require(len(db_rows) == 2, "database action query mismatch", errors)
        source_ids = {str(row["source_record_id"]) for row in db_rows}
        require(source_ids == EXPECTED_RECORD_IDS, "qualifying record identity mismatch", errors)

        source_agreements = {
            str(row["source_record_id"]): row
            for row in source.execute(
                """
                SELECT source_record_id, agreement_id, summary, source_url,
                       content_sha256, adopted_on
                FROM agreements
                WHERE source_record_id IN (?, ?)
                """,
                tuple(sorted(EXPECTED_RECORD_IDS)),
            ).fetchall()
        }
        require(len(source_agreements) == 2, "source projection lost qualifying rows", errors)

        all_actor_labels: set[str] = set()
        artifact_by_id = {
            str(record.get("geopolitical_action_id")): record for record in records
        }
        for db_row in db_rows:
            action_id = str(db_row["geopolitical_action_id"])
            public_record = artifact_by_id.get(action_id)
            require(public_record is not None, f"action missing from artifact: {action_id}", errors)
            if public_record is None:
                continue
            source_record_id = str(db_row["source_record_id"])
            source_agreement = source_agreements[source_record_id]
            summary = str(db_row["summary"])
            raw_payload = json.loads(str(db_row["source_raw_payload"]))
            require(summary == raw_payload.get("summary_text"), f"raw summary mismatch: {source_record_id}", errors)
            require(summary == db_row["agreement_summary"], f"agreement summary mismatch: {source_record_id}", errors)
            require(summary == source_agreement["summary"], f"source projection summary mismatch: {source_record_id}", errors)
            require(db_row["action_kind"] == "treaty_process", f"action kind mismatch: {source_record_id}", errors)
            require(db_row["action_status"] == "authorized", f"action status mismatch: {source_record_id}", errors)
            require(
                db_row["procedure_stage"]
                == "domestic_referral_and_authorization_to_consent",
                f"procedure stage mismatch: {source_record_id}",
                errors,
            )
            require(db_row["instrument_name"] in summary, f"instrument not source-backed: {source_record_id}", errors)
            for state_column in (
                "binding_state",
                "entry_into_force_state",
                "implementation_state",
                "outcome_state",
                "position_state",
            ):
                require(db_row[state_column] == "not_assessed", f"unsafe state {state_column}: {source_record_id}", errors)
            require(db_row["source_url"] == source_agreement["source_url"], f"source URL mismatch: {source_record_id}", errors)
            require(db_row["content_sha256"] == source_agreement["content_sha256"], f"source hash mismatch: {source_record_id}", errors)
            require(db_row["action_date"] == source_agreement["adopted_on"], f"action date mismatch: {source_record_id}", errors)

            actor_rows = materialized.execute(
                """
                SELECT source_label, actor_role, resolution_method
                FROM geopolitical_action_actors
                WHERE geopolitical_action_id = ?
                ORDER BY actor_ordinal
                """,
                (action_id,),
            ).fetchall()
            for actor in actor_rows:
                label = str(actor["source_label"])
                all_actor_labels.add(label)
                if label != "Gobierno de España / La Moncloa":
                    require(label in summary, f"actor absent from evidence: {label}", errors)

            evidence = materialized.execute(
                "SELECT * FROM geopolitical_action_evidence WHERE geopolitical_action_id = ?",
                (action_id,),
            ).fetchall()
            require(len(evidence) == 1, f"evidence cardinality mismatch: {source_record_id}", errors)
            if evidence:
                item = evidence[0]
                require(item["exact_quote"] == summary, f"exact quote mismatch: {source_record_id}", errors)
                require(item["quote_sha256"] == sha256_text(summary), f"quote hash mismatch: {source_record_id}", errors)
                require(item["capture_sha256"] == CAPTURE_SHA256, f"capture hash mismatch: {source_record_id}", errors)
                require(item["capture_bytes"] == CAPTURE_BYTES, f"capture bytes mismatch: {source_record_id}", errors)
                require(not str(item["capture_path"]).startswith("/"), f"absolute capture path leaked: {source_record_id}", errors)

            topics = materialized.execute(
                """
                SELECT topic_key, assignment_kind, match_text, review_status
                FROM geopolitical_action_topics
                WHERE geopolitical_action_id = ?
                """,
                (action_id,),
            ).fetchall()
            require(len(topics) == 2, f"topic cardinality mismatch: {source_record_id}", errors)
            for topic in topics:
                require(topic["assignment_kind"] == "derived_rule", f"topic classification mismatch: {source_record_id}", errors)
                require(topic["review_status"] == "unreviewed", f"topic review state mismatch: {source_record_id}", errors)
                require(str(topic["match_text"]) in summary, f"topic match absent: {source_record_id}", errors)

            links = materialized.execute(
                "SELECT * FROM geopolitical_action_links WHERE subject_action_id = ?",
                (action_id,),
            ).fetchall()
            require(len(links) == 1, f"agreement link cardinality mismatch: {source_record_id}", errors)
            if links:
                require(links[0]["object_id"] == source_agreement["agreement_id"], f"agreement link mismatch: {source_record_id}", errors)

        require(all_actor_labels == EXPECTED_ACTORS, "public actor identity set mismatch", errors)
    finally:
        materialized.close()
        source.close()

    artifact_text = published_bytes.decode("utf-8", errors="replace").lower()
    for forbidden in (
        "/users/",
        "file:///",
        "/home/",
        "dummy",
        "synthetic record",
        "mock record",
        "lorem ipsum",
    ):
        require(forbidden not in artifact_text, f"forbidden public marker: {forbidden}", errors)

    report = {
        "schema_version": "moncloa_geopolitics_validation_v1",
        "status": "ok" if not errors else "error",
        "release_id": release_id,
        "artifact_bytes": len(published_bytes),
        "artifact_sha256": artifact_sha256,
        "official_capture": {
            "path": CAPTURE_PATH.relative_to(REPO_ROOT).as_posix(),
            "bytes": capture_size,
            "content_sha256": capture_hash,
            "records": len(capture_payload.get("records") or []),
        },
        "metrics": {
            "records": len(records),
            "actor_labels": len(EXPECTED_ACTORS),
            "database_counts": db_counts,
            "foreign_key_violations": len(fk_rows),
            "integrity_check": integrity,
            "entry_into_force_claims": 0,
            "implementation_claims": 0,
            "explicit_positions": 0,
            "geopolitical_inferences": 0,
        },
        "checks": {
            "release_hash": release_id == sha256_text(canonical_json(core)),
            "published_public_byte_parity": published_bytes == public_bytes,
            "real_data_only": policy.get("real_data_only") is True,
            "official_public_identity_retained": all_actor_labels == EXPECTED_ACTORS,
            "fact_only": policy.get("inference_level") == "fact_only",
        },
        "errors": errors,
    }
    atomic_write(args.report_out, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
