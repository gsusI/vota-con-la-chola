#!/usr/bin/env python3
"""Materialize two real La Moncloa foreign-policy actions.

Input is the validated agreements projection plus the checksum-pinned official raw
capture. The connector emits procedural facts only. It never infers alignment,
position, treaty entry into force, implementation, influence, or outcome.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DB = REPO_ROOT / "etl/data/staging/agreements-moncloa-mvp.db"
DEFAULT_SCHEMA = REPO_ROOT / "etl/load/sqlite_schema.sql"
DEFAULT_OUT_DB = REPO_ROOT / "etl/data/staging/geopolitics-moncloa-mvp.db"
DEFAULT_PUBLISHED = REPO_ROOT / "etl/data/published/geopolitics-moncloa-sample.json"
DEFAULT_PUBLIC = (
    REPO_ROOT / "ui/gh-pages-next/public/geopolitics/data/moncloa-sample.json"
)
DEFAULT_REPORT = (
    REPO_ROOT
    / "docs/etl/sprints/GEOPOLITICS-20260819/evidence/moncloa-geopolitics-materialization.json"
)

CAPTURE_PATH = Path(
    "etl/data/raw/moncloa_referencias/2026/02/16/"
    "moncloa_referencias_20260216T141256Z.json"
)
CAPTURE_BYTES = 21_234
CAPTURE_SHA256 = "ab08b7dc09a46c890f055e95fdeac5e7d716a5023f8792f19ce440a239271ddf"
SOURCE_ID = "moncloa_referencias"
EXTRACTOR_METHOD = "moncloa_international_agreement_procedure_v1"
EXTRACTOR_VERSION = "geopolitics_moncloa_v1"
TOPIC_METHOD = "moncloa_geopolitics_keyword_codebook"
TOPIC_VERSION = "geopolitics_topics_es_v1"
LINK_METHOD = "shared_source_record_exact_v1"
LINK_VERSION = "geopolitics_agreement_link_v1"
PROCEDURE_STAGE = "domestic_referral_and_authorization_to_consent"
NULL = "\0"


ACTION_RULES: dict[str, dict[str, Any]] = {
    "referencia:20260113-referencia-rueda-de-prensa-ministros.aspx": {
        "instrument_name": (
            "Acuerdo entre la Unión Europea y la Comunidad Europea de la Energía "
            "Atómica, por una parte, y el Reino de España, por otra, relativo al "
            "establecimiento del Centro Común de Investigación de la Comisión "
            "Europea en Sevilla"
        ),
        "scope_kind": "multilateral",
        "scope_match": "Unión Europea y la Comunidad Europea de la Energía Atómica",
        "actors": (
            ("Consejo de Ministros", "approving_body", "public_body"),
            ("Gobierno de España / La Moncloa", "publishing_body", "public_body"),
            ("Cortes Generales", "parliamentary_recipient", "public_body"),
            ("Reino de España", "acting_state", "state"),
            ("Unión Europea", "counterparty_organization", "international_organization"),
            (
                "Comunidad Europea de la Energía Atómica",
                "counterparty_organization",
                "international_organization",
            ),
        ),
        "topics": (
            (
                "international_relations_treaties",
                "Relaciones internacionales y tratados",
                "Acuerdo entre la Unión Europea",
            ),
            (
                "research_innovation",
                "Ciencia, investigación e innovación",
                "Centro Común de Investigación",
            ),
        ),
    },
    "referencia:20260127-referencia-rueda-de-prensa-ministros.aspx": {
        "instrument_name": (
            "Acuerdo entre el Reino de España y el Sultanato de Omán sobre exención "
            "recíproca de visados para titulares de pasaportes diplomáticos, "
            "especiales y de servicio"
        ),
        "scope_kind": "bilateral",
        "scope_match": "Reino de España y el Sultanato de Omán",
        "actors": (
            ("Consejo de Ministros", "approving_body", "public_body"),
            ("Gobierno de España / La Moncloa", "publishing_body", "public_body"),
            ("Cortes Generales", "parliamentary_recipient", "public_body"),
            ("Reino de España", "acting_state", "state"),
            ("Sultanato de Omán", "counterparty_state", "state"),
        ),
        "topics": (
            (
                "international_relations_treaties",
                "Relaciones internacionales y tratados",
                "Acuerdo entre el Reino de España y el Sultanato de Omán",
            ),
            (
                "diplomatic_mobility_visas",
                "Movilidad diplomática y visados",
                "exención recíproca de visados",
            ),
        ),
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-db", type=Path, default=DEFAULT_SOURCE_DB)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--out-db", type=Path, default=DEFAULT_OUT_DB)
    parser.add_argument("--published-out", type=Path, default=DEFAULT_PUBLISHED)
    parser.add_argument("--public-out", type=Path, default=DEFAULT_PUBLIC)
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


def stable_id(kind: str, *parts: object) -> str:
    payload = NULL.join([kind, *(str(part or "") for part in parts)])
    return f"vclc:{kind}:{sha256_text(payload)}"


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_bytes(data)
    temporary.replace(path)


def report_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def verify_capture() -> dict[str, Any]:
    capture = REPO_ROOT / CAPTURE_PATH
    if not capture.is_file():
        raise RuntimeError(f"missing official capture: {CAPTURE_PATH}")
    size = capture.stat().st_size
    digest = sha256_file(capture)
    if size != CAPTURE_BYTES or digest != CAPTURE_SHA256:
        raise RuntimeError(
            f"official capture mismatch: bytes={size} sha256={digest}"
        )
    payload = json.loads(capture.read_text(encoding="utf-8"))
    records = payload.get("records")
    if not isinstance(records, list) or len(records) != 20:
        raise RuntimeError("official capture must contain exactly 20 records")
    return {
        "path": CAPTURE_PATH.as_posix(),
        "bytes": size,
        "content_sha256": digest,
        "captured_at": "2026-02-16T14:12:56+00:00",
        "source_url": (
            "https://www.lamoncloa.gob.es/consejodeministros/referencias/"
            "paginas/index.aspx"
        ),
        "records": len(records),
    }


def clone_source_database(source_db: Path, out_db: Path, schema: Path) -> sqlite3.Connection:
    if not source_db.is_file():
        raise RuntimeError(f"missing validated agreements database: {source_db}")
    if not schema.is_file():
        raise RuntimeError(f"missing schema: {schema}")
    out_db.parent.mkdir(parents=True, exist_ok=True)
    if out_db.exists():
        out_db.unlink()
    source = sqlite3.connect(f"file:{source_db}?mode=ro", uri=True)
    target = sqlite3.connect(out_db)
    try:
        source.backup(target)
        target.executescript(schema.read_text(encoding="utf-8"))
        target.execute("PRAGMA foreign_keys = ON")
        target.row_factory = sqlite3.Row
        return target
    except Exception:
        target.close()
        raise
    finally:
        source.close()


def qualifying_rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    placeholders = ",".join("?" for _ in ACTION_RULES)
    rows = connection.execute(
        f"""
        SELECT
          a.agreement_id,
          a.source_id,
          a.source_record_pk,
          a.source_record_id,
          a.source_snapshot_date,
          a.adopted_on,
          a.published_on,
          a.observed_at,
          a.title AS source_title,
          a.summary,
          a.source_url,
          a.content_sha256,
          a.raw_payload_json,
          a.created_at,
          a.updated_at,
          sr.raw_payload AS source_raw_payload
        FROM agreements AS a
        JOIN source_records AS sr ON sr.source_record_pk = a.source_record_pk
        WHERE a.source_id = ?
          AND a.source_record_id IN ({placeholders})
          AND a.agreement_status = 'adopted'
        ORDER BY a.adopted_on, a.source_record_id
        """,
        (SOURCE_ID, *ACTION_RULES.keys()),
    ).fetchall()
    if len(rows) != 2:
        raise RuntimeError(f"expected exactly 2 qualifying actions; got {len(rows)}")
    if {row["source_record_id"] for row in rows} != set(ACTION_RULES):
        raise RuntimeError("qualifying source-record identity mismatch")
    return rows


def actor_resolution_method(source_label: str) -> str:
    if source_label == "Gobierno de España / La Moncloa":
        return "official_source_publisher_metadata"
    return "exact_source_substring_v1"


def materialize_row(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
    capture: dict[str, Any],
) -> str:
    rule = ACTION_RULES[row["source_record_id"]]
    summary = str(row["summary"])
    instrument_name = str(rule["instrument_name"])
    if instrument_name not in summary:
        raise RuntimeError(f"instrument text missing from source: {row['source_record_id']}")
    if str(rule["scope_match"]) not in summary:
        raise RuntimeError(f"scope evidence missing from source: {row['source_record_id']}")

    action_id = stable_id(
        "geopolitical-action",
        row["source_id"],
        row["source_record_id"],
        "treaty_process",
        PROCEDURE_STAGE,
        row["adopted_on"],
    )
    timestamp = str(row["observed_at"])
    connection.execute(
        """
        INSERT INTO geopolitical_actions (
          geopolitical_action_id, source_id, source_record_pk, source_record_id,
          source_snapshot_date, action_ordinal, action_kind, action_status,
          procedure_stage, title, summary, instrument_name, scope_kind,
          scope_assignment_kind, action_date, published_at, observed_at,
          date_precision, binding_state, entry_into_force_state,
          implementation_state, outcome_state, position_state,
          related_agreement_id, source_url, content_sha256, fact_state,
          extractor_method, extractor_version, raw_payload_json, created_at, updated_at
        ) VALUES (
          ?, ?, ?, ?, ?, 0, 'treaty_process', 'authorized', ?, ?, ?, ?, ?,
          'derived_rule', ?, ?, ?, 'day', 'not_assessed', 'not_assessed',
          'not_assessed', 'not_assessed', 'not_assessed', ?, ?, ?,
          'source_summary', ?, ?, ?, ?, ?
        )
        """,
        (
            action_id,
            row["source_id"],
            row["source_record_pk"],
            row["source_record_id"],
            row["source_snapshot_date"],
            PROCEDURE_STAGE,
            instrument_name,
            summary,
            instrument_name,
            rule["scope_kind"],
            row["adopted_on"],
            row["published_on"],
            row["observed_at"],
            row["agreement_id"],
            row["source_url"],
            row["content_sha256"],
            EXTRACTOR_METHOD,
            EXTRACTOR_VERSION,
            canonical_json(
                {
                    "source_agreement_id": row["agreement_id"],
                    "source_title": row["source_title"],
                    "scope_match": rule["scope_match"],
                }
            ),
            timestamp,
            timestamp,
        ),
    )

    for ordinal, (label, role, kind) in enumerate(rule["actors"]):
        if label != "Gobierno de España / La Moncloa" and label not in summary:
            raise RuntimeError(f"actor label absent from evidence: {label}")
        actor_id = stable_id("geopolitical-action-actor", action_id, role, label, ordinal)
        connection.execute(
            """
            INSERT INTO geopolitical_action_actors (
              geopolitical_action_actor_id, geopolitical_action_id, actor_ordinal,
              actor_role, actor_kind, source_label, identity_state,
              resolution_method, resolution_confidence, source_id, source_record_pk,
              raw_payload_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'source_scoped', ?, 1.0, ?, ?, '{}', ?, ?)
            """,
            (
                actor_id,
                action_id,
                ordinal,
                role,
                kind,
                label,
                actor_resolution_method(label),
                row["source_id"],
                row["source_record_pk"],
                timestamp,
                timestamp,
            ),
        )

    evidence_id = stable_id(
        "geopolitical-action-evidence",
        action_id,
        row["source_record_pk"],
        "$.summary_text",
        sha256_text(summary),
        0,
    )
    connection.execute(
        """
        INSERT INTO geopolitical_action_evidence (
          geopolitical_action_evidence_id, geopolitical_action_id,
          evidence_ordinal, evidence_role, source_id, source_record_pk,
          source_url, capture_path, capture_bytes, captured_at, capture_sha256,
          content_sha256, exact_quote, quote_sha256, selector, evidence_state,
          created_at, updated_at
        ) VALUES (?, ?, 0, 'official_action', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                  '$.summary_text', 'captured_bytes', ?, ?)
        """,
        (
            evidence_id,
            action_id,
            row["source_id"],
            row["source_record_pk"],
            row["source_url"],
            capture["path"],
            capture["bytes"],
            capture["captured_at"],
            capture["content_sha256"],
            row["content_sha256"],
            summary,
            sha256_text(summary),
            timestamp,
            timestamp,
        ),
    )

    for topic_key, topic_label, match_text in rule["topics"]:
        if match_text not in summary:
            raise RuntimeError(f"topic match absent from evidence: {match_text}")
        topic_id = stable_id(
            "geopolitical-action-topic",
            action_id,
            topic_key,
            TOPIC_METHOD,
            TOPIC_VERSION,
        )
        connection.execute(
            """
            INSERT INTO geopolitical_action_topics (
              geopolitical_action_topic_id, geopolitical_action_id, topic_key,
              topic_label, assignment_kind, assignment_method, assignment_version,
              match_text, review_status, source_id, source_record_pk,
              created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'derived_rule', ?, ?, ?, 'unreviewed', ?, ?, ?, ?)
            """,
            (
                topic_id,
                action_id,
                topic_key,
                topic_label,
                TOPIC_METHOD,
                TOPIC_VERSION,
                match_text,
                row["source_id"],
                row["source_record_pk"],
                timestamp,
                timestamp,
            ),
        )

    link_id = stable_id(
        "geopolitical-action-link",
        action_id,
        "derived_from_agreement",
        row["agreement_id"],
        LINK_METHOD,
        LINK_VERSION,
    )
    connection.execute(
        """
        INSERT INTO geopolitical_action_links (
          geopolitical_action_link_id, subject_action_id, relationship_type,
          object_type, object_id, object_agreement_id, source_id, source_record_pk,
          method, method_version, confidence, review_status, created_at, updated_at
        ) VALUES (?, ?, 'derived_from_agreement', 'agreement', ?, ?, ?, ?, ?, ?,
                  1.0, 'confirmed', ?, ?)
        """,
        (
            link_id,
            action_id,
            row["agreement_id"],
            row["agreement_id"],
            row["source_id"],
            row["source_record_pk"],
            LINK_METHOD,
            LINK_VERSION,
            timestamp,
            timestamp,
        ),
    )
    return action_id


def action_record(connection: sqlite3.Connection, action_id: str) -> dict[str, Any]:
    action = connection.execute(
        "SELECT * FROM geopolitical_actions WHERE geopolitical_action_id = ?",
        (action_id,),
    ).fetchone()
    assert action is not None
    actors = connection.execute(
        """
        SELECT geopolitical_action_actor_id, actor_ordinal, actor_role, actor_kind,
               source_label, identity_state, resolution_method
        FROM geopolitical_action_actors
        WHERE geopolitical_action_id = ?
        ORDER BY actor_ordinal
        """,
        (action_id,),
    ).fetchall()
    topics = connection.execute(
        """
        SELECT geopolitical_action_topic_id, topic_key, topic_label,
               assignment_kind, assignment_method, assignment_version,
               match_text, review_status
        FROM geopolitical_action_topics
        WHERE geopolitical_action_id = ?
        ORDER BY topic_key
        """,
        (action_id,),
    ).fetchall()
    evidence = connection.execute(
        """
        SELECT geopolitical_action_evidence_id, evidence_role, source_url,
               capture_path, capture_bytes, captured_at, capture_sha256,
               content_sha256, exact_quote, quote_sha256, selector, evidence_state
        FROM geopolitical_action_evidence
        WHERE geopolitical_action_id = ?
        ORDER BY evidence_ordinal
        """,
        (action_id,),
    ).fetchall()
    link = connection.execute(
        """
        SELECT geopolitical_action_link_id, relationship_type, object_type,
               object_id, method, method_version, confidence, review_status
        FROM geopolitical_action_links
        WHERE subject_action_id = ?
        ORDER BY relationship_type, object_id
        """,
        (action_id,),
    ).fetchall()
    return {
        "geopolitical_action_id": action["geopolitical_action_id"],
        "action_kind": action["action_kind"],
        "action_status": action["action_status"],
        "procedure_stage": action["procedure_stage"],
        "title": action["title"],
        "summary": action["summary"],
        "instrument_name": action["instrument_name"],
        "scope_kind": action["scope_kind"],
        "scope_assignment_kind": action["scope_assignment_kind"],
        "action_date": action["action_date"],
        "published_at": action["published_at"],
        "date_precision": action["date_precision"],
        "binding_state": action["binding_state"],
        "entry_into_force_state": action["entry_into_force_state"],
        "implementation_state": action["implementation_state"],
        "outcome_state": action["outcome_state"],
        "position_state": action["position_state"],
        "fact_state": action["fact_state"],
        "related_agreement_id": action["related_agreement_id"],
        "actors": [dict(item) for item in actors],
        "topics": [dict(item) for item in topics],
        "evidence": [dict(item) for item in evidence],
        "links": [dict(item) for item in link],
    }


def table_count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def main() -> int:
    args = parse_args()
    capture = verify_capture()
    connection = clone_source_database(args.source_db, args.out_db, args.schema)
    try:
        rows = qualifying_rows(connection)
        action_ids = [materialize_row(connection, row, capture) for row in rows]
        connection.commit()
        foreign_keys = [tuple(row) for row in connection.execute("PRAGMA foreign_key_check")]
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        if foreign_keys or integrity != "ok":
            raise RuntimeError(
                f"database checks failed: foreign_keys={len(foreign_keys)} integrity={integrity}"
            )

        records = [action_record(connection, action_id) for action_id in action_ids]
        counts = {
            "actions": table_count(connection, "geopolitical_actions"),
            "actors": table_count(connection, "geopolitical_action_actors"),
            "evidence": table_count(connection, "geopolitical_action_evidence"),
            "topics": table_count(connection, "geopolitical_action_topics"),
            "positions": table_count(connection, "geopolitical_positions"),
            "position_evidence": table_count(
                connection, "geopolitical_position_evidence"
            ),
            "links": table_count(connection, "geopolitical_action_links"),
            "later_observations": table_count(connection, "geopolitical_observations"),
        }
    finally:
        connection.close()

    core = {
        "schema_version": "geopolitical_actions_sample_v1",
        "generated_at": capture["captured_at"],
        "policy": {
            "real_data_only": True,
            "synthetic_or_mock": False,
            "official_public_domain_information_retained": True,
            "inference_level": "fact_only",
            "treaty_entry_into_force_inferred": False,
            "implementation_inferred": False,
            "alignment_inferred": False,
            "influence_inferred": False,
            "causal_outcome_inferred": False,
        },
        "source": {
            **capture,
            "source_id": SOURCE_ID,
            "source_name": "La Moncloa - Referencias del Consejo de Ministros",
            "projection_database": args.source_db.name,
            "extractor_method": EXTRACTOR_METHOD,
            "extractor_version": EXTRACTOR_VERSION,
        },
        "coverage": {
            "source_records": capture["records"],
            "qualifying_foreign_policy_records": len(records),
            **counts,
            "procedural_stage": {PROCEDURE_STAGE: len(records)},
            "not_assessed_binding": len(records),
            "not_assessed_entry_into_force": len(records),
            "not_assessed_implementation": len(records),
            "not_assessed_outcomes": len(records),
            "explicit_positions": counts["positions"],
        },
        "limitations": [
            "The source proves a Council of Ministers referral/authorization step, not treaty signature, ratification, entry into force, implementation, use, or impact.",
            "Counterpart labels are retained from the official source; no broader geopolitical alignment or relationship quality is inferred.",
            "No attendance, lobbying, influence, motive, corruption, legality, merit, blame, or causal outcome is assessed.",
            "This is a two-record real-source vertical slice, not historical or institutional coverage of Spanish foreign policy.",
        ],
        "records": records,
    }
    release_id = sha256_text(canonical_json(core))
    artifact = {"release_id": release_id, **core}
    artifact_bytes = (canonical_json(artifact) + "\n").encode("utf-8")
    artifact_sha256 = sha256_bytes(artifact_bytes)
    atomic_write(args.published_out, artifact_bytes)
    atomic_write(args.public_out, artifact_bytes)

    report = {
        "schema_version": "moncloa_geopolitics_materialization_v1",
        "status": "ok",
        "release_id": release_id,
        "artifact_bytes": len(artifact_bytes),
        "artifact_sha256": artifact_sha256,
        "real_data_only": True,
        "synthetic_or_mock": False,
        "official_public_domain_information_retained": True,
        "source_capture": capture,
        "counts": counts,
        "checks": {
            "qualifying_records_exact": len(records) == 2,
            "source_quotes_exact": True,
            "public_identity_retained": True,
            "foreign_key_check": "ok",
            "integrity_check": "ok",
            "positions_emitted": counts["positions"],
            "later_observations_emitted": counts["later_observations"],
            "entry_into_force_claims": 0,
            "implementation_claims": 0,
            "geopolitical_inferences": 0,
        },
        "outputs": {
            "database": report_path(args.out_db),
            "published": report_path(args.published_out),
            "public": report_path(args.public_out),
        },
    }
    atomic_write(
        args.report_out,
        (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        ),
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
