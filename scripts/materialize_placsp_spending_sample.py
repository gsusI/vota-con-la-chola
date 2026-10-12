#!/usr/bin/env python3
"""Materialize a deterministic real-only PLACSP award sample.

The source is the existing official H1 2025 PLACSP bulk corpus. This script does
not fetch, generate, multiply, redact, or infer records. It maps latest source
versions into the canonical spending-event tables and publishes a bounded JSON
view for direct citizen audit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DB = REPO_ROOT / "etl/data/staging/placsp-contracts-real-s1-20260811.db"
DEFAULT_SCHEMA = REPO_ROOT / "etl/load/sqlite_schema.sql"
DEFAULT_OUT_DB = REPO_ROOT / "etl/data/staging/spending-placsp-mvp.db"
DEFAULT_PUBLISHED = REPO_ROOT / "etl/data/published/spending-placsp-sample.json"
DEFAULT_PUBLIC = REPO_ROOT / "ui/site/public/spending/data/placsp-sample.json"
DEFAULT_REPORT = (
    REPO_ROOT
    / "docs/etl/sprints/SPENDING-20260819/evidence/placsp-spending-materialization.json"
)

SOURCE_ID = "placsp_sindicacion"
EXTRACTOR_METHOD = "placsp_latest_award_to_spending_item"
EXTRACTOR_VERSION = "spending_placsp_v1"
NULL = "\0"

LEGAL_ENTITY_IDENTIFIER = re.compile(
    r"^[ABCDEFGHJNPQRSUVW][0-9]{7}[0-9A-J]$", re.IGNORECASE
)
NATURAL_PERSON_IDENTIFIER = re.compile(
    r"^(?:[0-9]{8}[A-Z]|[XYZ][0-9]{7}[A-Z])$", re.IGNORECASE
)

LATEST_AWARD_SQL = """
WITH ranked_contracts AS (
  SELECT
    c.*,
    ROW_NUMBER() OVER (
      PARTITION BY c.source_id,
        COALESCE(NULLIF(c.stable_contract_id, ''), 'source:' || c.source_record_id)
      ORDER BY
        COALESCE(NULLIF(c.entry_updated_at, ''), NULLIF(c.awarded_date, ''),
                 NULLIF(c.published_date, ''), c.source_snapshot_date, '') DESC,
        c.contract_record_id DESC
    ) AS version_rank
  FROM money_contract_records AS c
  WHERE c.source_id = ?
)
SELECT
  c.contract_record_id,
  c.source_id,
  c.source_record_pk,
  c.source_record_id,
  c.source_snapshot_date,
  c.source_url,
  c.contract_id,
  c.lot_id AS contract_lot_id,
  c.notice_type,
  c.cpv_code,
  c.cpv_label,
  c.contracting_authority,
  c.procedure_type,
  c.territory_code,
  c.published_date,
  c.awarded_date AS contract_awarded_date,
  c.stable_contract_id,
  c.entry_updated_at,
  c.contract_status_code,
  c.authority_identifier,
  award.contract_award_result_id,
  award.award_ordinal,
  award.lot_id AS award_lot_id,
  award.result_code,
  award.result_description,
  award.award_date,
  award.received_tender_quantity,
  award.supplier_name,
  award.supplier_identifier,
  award.supplier_identifier_scheme,
  award.amount_eur_decimal,
  award.payable_amount_eur_decimal,
  award.currency,
  source.name AS source_name,
  source.default_url AS source_default_url,
  source.data_format AS source_data_format,
  sr.content_sha256 AS source_record_sha256,
  sr.created_at AS source_record_created_at,
  sr.updated_at AS source_record_updated_at,
  json_extract(sr.raw_payload, '$.record.title') AS title
FROM ranked_contracts AS c
JOIN money_contract_award_results AS award
  ON award.source_record_pk = c.source_record_pk
JOIN sources AS source ON source.source_id = c.source_id
JOIN source_records AS sr ON sr.source_record_pk = c.source_record_pk
WHERE c.version_rank = 1
  AND COALESCE(json_extract(sr.raw_payload, '$.record.tombstone'), 0) = 0
  AND NULLIF(TRIM(c.contracting_authority), '') IS NOT NULL
  AND NULLIF(TRIM(award.supplier_name), '') IS NOT NULL
  AND NULLIF(TRIM(award.amount_eur_decimal), '') IS NOT NULL
  AND award.currency = 'EUR'
  AND c.source_url LIKE 'https://contrataciondelestado.es/%'
ORDER BY c.contract_record_id, award.award_ordinal
"""

LINEAGE_SQL = """
SELECT
  sight.observed_at,
  member.placsp_bulk_member_id,
  member.member_name,
  member.content_sha256 AS member_content_sha256,
  archive.placsp_bulk_archive_id,
  archive.period AS archive_period,
  archive.source_url AS archive_source_url,
  archive.content_sha256 AS archive_content_sha256,
  archive.bytes AS archive_bytes,
  archive.transport_security
FROM placsp_bulk_record_sightings AS sight
JOIN placsp_bulk_members AS member
  ON member.placsp_bulk_member_id = sight.placsp_bulk_member_id
JOIN placsp_bulk_archives AS archive
  ON archive.placsp_bulk_archive_id = member.placsp_bulk_archive_id
WHERE sight.source_record_pk = ?
ORDER BY sight.observed_at, sight.placsp_bulk_record_sighting_id
LIMIT 1
"""

DOCUMENT_SQL = """
SELECT
  contract_document_id,
  document_ordinal,
  document_kind,
  document_label,
  source_url AS document_url,
  official_document_hash
FROM money_contract_documents
WHERE source_record_pk = ?
  AND source_url LIKE 'https://contrataciondelestado.es/%'
ORDER BY
  CASE
    WHEN LOWER(COALESCE(document_label, '')) LIKE '%adjudic%' THEN 0
    WHEN document_kind = 'NoticeDocumentReference' THEN 1
    ELSE 2
  END,
  document_ordinal
LIMIT 1
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-db", type=Path, default=DEFAULT_SOURCE_DB)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--out-db", type=Path, default=DEFAULT_OUT_DB)
    parser.add_argument("--sample-size", type=int, default=20)
    parser.add_argument("--published-out", type=Path, default=DEFAULT_PUBLISHED)
    parser.add_argument("--public-out", type=Path, default=DEFAULT_PUBLIC)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_id(kind: str, *parts: object) -> str:
    payload = NULL.join([kind, *(str(part or "") for part in parts)])
    return f"vclc:{kind}:{sha256_text(payload)}"


def normalized_identifier(value: object) -> str | None:
    text = str(value or "").strip()
    return text.upper() if text else None


def counterparty_kind(identifier: object) -> tuple[str, str]:
    value = normalized_identifier(identifier)
    if value and LEGAL_ENTITY_IDENTIFIER.fullmatch(value):
        return "organization", "legal_entity"
    if value and NATURAL_PERSON_IDENTIFIER.fullmatch(value):
        return "person", "potential_natural_person"
    return "unknown", "unclassified"


def sample_quotas(sample_size: int) -> dict[str, int]:
    if sample_size < 3:
        raise ValueError("sample-size must be at least 3")
    person = max(1, sample_size // 4)
    unknown = max(1, sample_size // 4)
    return {
        "legal_entity": sample_size - person - unknown,
        "potential_natural_person": person,
        "unclassified": unknown,
    }


def enrich_selected_rows(
    conn: sqlite3.Connection, rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    document_fields = (
        "contract_document_id",
        "document_ordinal",
        "document_kind",
        "document_label",
        "document_url",
        "official_document_hash",
    )
    for row in rows:
        lineage = conn.execute(LINEAGE_SQL, (row["source_record_pk"],)).fetchone()
        if lineage is None:
            raise RuntimeError(
                f"missing bulk lineage for source_record_pk={row['source_record_pk']}"
            )
        document = conn.execute(DOCUMENT_SQL, (row["source_record_pk"],)).fetchone()
        item = dict(row)
        item.update(dict(lineage))
        if document is None:
            item.update({field: None for field in document_fields})
        else:
            item.update(dict(document))
        enriched.append(item)
    return enriched


def select_rows(conn: sqlite3.Connection, sample_size: int) -> list[dict[str, Any]]:
    quotas = sample_quotas(sample_size)
    selected: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    seen_authorities: set[str] = set()
    deferred: list[dict[str, Any]] = []

    for source_row in conn.execute(LATEST_AWARD_SQL, (SOURCE_ID,)):
        row = dict(source_row)
        _actor_kind, category = counterparty_kind(row["supplier_identifier"])
        authority_key = str(row["authority_identifier"] or row["contracting_authority"])
        if counts[category] >= quotas[category] or authority_key in seen_authorities:
            deferred.append(row)
            continue
        selected.append(row)
        counts[category] += 1
        seen_authorities.add(authority_key)
        if len(selected) == sample_size:
            break

    if len(selected) < sample_size:
        selected_ids = {
            (int(row["contract_award_result_id"]), str(row["source_record_id"]))
            for row in selected
        }
        for row in deferred:
            key = (int(row["contract_award_result_id"]), str(row["source_record_id"]))
            if key in selected_ids:
                continue
            selected.append(row)
            selected_ids.add(key)
            if len(selected) == sample_size:
                break

    if len(selected) != sample_size:
        raise RuntimeError(
            f"official corpus yielded only {len(selected)} complete award rows; "
            f"required {sample_size}"
        )
    actual = Counter(
        counterparty_kind(row["supplier_identifier"])[1] for row in selected
    )
    for category, quota in quotas.items():
        if actual[category] < quota:
            raise RuntimeError(
                f"official corpus did not satisfy real identity stratum {category}: "
                f"{actual[category]}/{quota}"
            )
    return enrich_selected_rows(conn, selected)


def copy_exact_row(
    source: sqlite3.Connection,
    target: sqlite3.Connection,
    table: str,
    where_column: str,
    where_value: object,
) -> None:
    row = source.execute(
        f'SELECT * FROM "{table}" WHERE "{where_column}" = ?', (where_value,)
    ).fetchone()
    if row is None:
        raise RuntimeError(f"missing source row {table}.{where_column}={where_value}")
    columns = list(row.keys())
    names = ", ".join(f'"{column}"' for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    target.execute(
        f'INSERT INTO "{table}" ({names}) VALUES ({placeholders})',
        tuple(row[column] for column in columns),
    )


def source_counts(conn: sqlite3.Connection) -> dict[str, int]:
    tables = (
        "money_contract_records",
        "money_contract_award_results",
        "money_contract_documents",
        "source_records",
        "placsp_bulk_archives",
        "placsp_bulk_members",
        "placsp_bulk_record_sightings",
    )
    return {
        table: int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        for table in tables
    }


def canonical_item(row: dict[str, Any]) -> dict[str, Any]:
    item_id = stable_id(
        "spending-item",
        row["source_id"],
        row["source_record_id"],
        "procurement_award",
        row["award_ordinal"],
    )
    supplier_kind, supplier_category = counterparty_kind(row["supplier_identifier"])
    amount = str(row["amount_eur_decimal"])
    payable = (
        str(row["payable_amount_eur_decimal"])
        if row["payable_amount_eur_decimal"] is not None
        else None
    )
    title = str(row["title"] or row["contract_id"] or row["stable_contract_id"])
    authority = {
        "actor_role": "contracting_authority",
        "actor_kind": "public_body",
        "source_label": str(row["contracting_authority"]),
        "source_identifier": normalized_identifier(row["authority_identifier"]),
        "source_identifier_scheme": "NIF" if row["authority_identifier"] else None,
        "identity_state": "source_scoped",
    }
    supplier = {
        "actor_role": "supplier",
        "actor_kind": supplier_kind,
        "source_category": supplier_category,
        "source_label": str(row["supplier_name"]),
        "source_identifier": normalized_identifier(row["supplier_identifier"]),
        "source_identifier_scheme": row["supplier_identifier_scheme"],
        "identity_state": "source_scoped",
    }
    evidence = [
        {
            "evidence_role": "primary_record",
            "source_url": str(row["source_url"]),
            "document_url": None,
            "document_label": "PLACSP source record",
            "document_kind": "ATOM/CODICE entry",
            "content_sha256": str(row["source_record_sha256"]),
            "evidence_state": "captured_bytes",
        }
    ]
    if row["document_url"]:
        evidence.append(
            {
                "evidence_role": "context",
                "source_url": str(row["source_url"]),
                "document_url": str(row["document_url"]),
                "document_label": row["document_label"],
                "document_kind": row["document_kind"],
                "content_sha256": None,
                "official_document_hash": row["official_document_hash"],
                "evidence_state": "official_url_only",
            }
        )
    return {
        "spending_item_id": item_id,
        "spending_kind": "procurement_award",
        "phase_caveat": "adjudicacion_publicada_no_prueba_contrato_pago_ni_entrega",
        "title": title,
        "description": row["result_description"],
        "stable_object_id": str(row["stable_contract_id"]),
        "semantic_ordinal": int(row["award_ordinal"]),
        "external_contract_id": row["contract_id"],
        "lot_id": row["award_lot_id"] or row["contract_lot_id"],
        "classification": {
            "scheme": "CPV",
            "code": row["cpv_code"],
            "label": row["cpv_label"],
        },
        "procedure": {
            "notice_type": row["notice_type"],
            "procedure_code": row["procedure_type"],
            "contract_status_code": row["contract_status_code"],
            "result_code": row["result_code"],
            "received_tender_quantity": row["received_tender_quantity"],
        },
        "money": {
            "amount_decimal": amount,
            "payable_amount_decimal": payable,
            "currency": str(row["currency"]),
            "amount_semantics": "award_amount",
            "tax_semantics": "excluding_tax",
            "arithmetic_authority": "decimal_string",
        },
        "dates": {
            "published_on": row["published_date"],
            "decision_on": row["award_date"] or row["contract_awarded_date"],
            "paid_on": None,
            "delivered_on": None,
            "date_precision": "day",
        },
        "territory_code": row["territory_code"],
        "actors": [authority, supplier],
        "evidence": evidence,
        "provenance": {
            "source_id": str(row["source_id"]),
            "source_record_id": str(row["source_record_id"]),
            "source_record_sha256": str(row["source_record_sha256"]),
            "source_url": str(row["source_url"]),
            "source_snapshot_date": row["source_snapshot_date"],
            "observed_at": row["observed_at"],
            "archive_period": row["archive_period"],
            "archive_source_url": row["archive_source_url"],
            "archive_sha256": row["archive_content_sha256"],
            "archive_bytes": int(row["archive_bytes"]),
            "archive_transport_security": row["transport_security"],
            "member_name": row["member_name"],
            "member_sha256": row["member_content_sha256"],
            "extractor_method": EXTRACTOR_METHOD,
            "extractor_version": EXTRACTOR_VERSION,
        },
    }


def materialize_db(
    source: sqlite3.Connection,
    rows: list[dict[str, Any]],
    schema_path: Path,
    out_db: Path,
) -> dict[str, int]:
    out_db.parent.mkdir(parents=True, exist_ok=True)
    temp_path = out_db.with_name(f".{out_db.name}.tmp-{os.getpid()}")
    if temp_path.exists():
        temp_path.unlink()
    target = sqlite3.connect(temp_path)
    target.row_factory = sqlite3.Row
    target.execute("PRAGMA foreign_keys = ON")
    try:
        target.executescript(schema_path.read_text(encoding="utf-8"))
        copy_exact_row(source, target, "sources", "source_id", SOURCE_ID)
        copied_source_records: set[int] = set()
        copied_contracts: set[int] = set()
        copied_awards: set[int] = set()
        copied_documents: set[int] = set()

        for row in rows:
            source_record_pk = int(row["source_record_pk"])
            contract_record_id = int(row["contract_record_id"])
            award_result_id = int(row["contract_award_result_id"])
            document_id = (
                int(row["contract_document_id"])
                if row["contract_document_id"] is not None
                else None
            )
            if source_record_pk not in copied_source_records:
                copy_exact_row(
                    source,
                    target,
                    "source_records",
                    "source_record_pk",
                    source_record_pk,
                )
                copied_source_records.add(source_record_pk)
            if contract_record_id not in copied_contracts:
                copy_exact_row(
                    source,
                    target,
                    "money_contract_records",
                    "contract_record_id",
                    contract_record_id,
                )
                copied_contracts.add(contract_record_id)
            if award_result_id not in copied_awards:
                copy_exact_row(
                    source,
                    target,
                    "money_contract_award_results",
                    "contract_award_result_id",
                    award_result_id,
                )
                copied_awards.add(award_result_id)
            if document_id is not None and document_id not in copied_documents:
                copy_exact_row(
                    source,
                    target,
                    "money_contract_documents",
                    "contract_document_id",
                    document_id,
                )
                copied_documents.add(document_id)

            item = canonical_item(row)
            created_at = str(row["source_record_created_at"])
            updated_at = str(row["source_record_updated_at"])
            target.execute(
                """
                INSERT INTO spending_items (
                  spending_item_id, source_id, source_record_pk, source_record_id,
                  source_snapshot_date, source_url, content_sha256, spending_kind,
                  source_kind_label, stable_object_id, semantic_ordinal,
                  external_contract_id, lot_id, title, description,
                  classification_scheme, classification_code, procedure_code,
                  result_code, amount_decimal, payable_amount_decimal, currency,
                  amount_semantics, tax_semantics, amount_source_text,
                  published_on, decision_on, paid_on, delivered_on, date_precision,
                  territory_code, publication_state, extractor_method,
                  extractor_version, raw_payload_json, created_at, updated_at
                ) VALUES (
                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    item["spending_item_id"],
                    row["source_id"],
                    source_record_pk,
                    row["source_record_id"],
                    row["source_snapshot_date"],
                    row["source_url"],
                    row["source_record_sha256"],
                    "procurement_award",
                    row["notice_type"],
                    row["stable_contract_id"],
                    row["award_ordinal"],
                    row["contract_id"],
                    row["award_lot_id"] or row["contract_lot_id"],
                    item["title"],
                    row["result_description"],
                    "CPV",
                    row["cpv_code"],
                    row["procedure_type"],
                    row["result_code"],
                    row["amount_eur_decimal"],
                    row["payable_amount_eur_decimal"],
                    row["currency"],
                    "award_amount",
                    "excluding_tax",
                    row["amount_eur_decimal"],
                    row["published_date"],
                    row["award_date"] or row["contract_awarded_date"],
                    None,
                    None,
                    "day",
                    row["territory_code"],
                    "published",
                    EXTRACTOR_METHOD,
                    EXTRACTOR_VERSION,
                    canonical_json(
                        {
                            "contract_record_id": contract_record_id,
                            "contract_award_result_id": award_result_id,
                            "notice_type": row["notice_type"],
                            "contract_status_code": row["contract_status_code"],
                            "received_tender_quantity": row["received_tender_quantity"],
                            "archive_sha256": row["archive_content_sha256"],
                            "member_sha256": row["member_content_sha256"],
                        }
                    ),
                    created_at,
                    updated_at,
                ),
            )

            for actor_ordinal, actor in enumerate(item["actors"]):
                actor_id = stable_id(
                    "spending-actor",
                    item["spending_item_id"],
                    actor["actor_role"],
                    actor_ordinal,
                )
                target.execute(
                    """
                    INSERT INTO spending_item_actors (
                      spending_item_actor_id, spending_item_id, actor_ordinal,
                      actor_role, actor_kind, source_label, source_identifier,
                      source_identifier_scheme, identity_state, source_id,
                      source_record_pk, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        actor_id,
                        item["spending_item_id"],
                        actor_ordinal,
                        actor["actor_role"],
                        actor["actor_kind"],
                        actor["source_label"],
                        actor["source_identifier"],
                        actor["source_identifier_scheme"],
                        actor["identity_state"],
                        row["source_id"],
                        source_record_pk,
                        created_at,
                        updated_at,
                    ),
                )

            for evidence_ordinal, evidence in enumerate(item["evidence"]):
                evidence_id = stable_id(
                    "spending-evidence", item["spending_item_id"], evidence_ordinal
                )
                target.execute(
                    """
                    INSERT INTO spending_item_evidence (
                      spending_evidence_id, spending_item_id, evidence_ordinal,
                      evidence_role, source_id, source_record_pk,
                      contract_document_id, document_id, source_url, document_url,
                      document_label, document_kind, content_sha256, selector,
                      evidence_state, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        evidence_id,
                        item["spending_item_id"],
                        evidence_ordinal,
                        evidence["evidence_role"],
                        row["source_id"],
                        source_record_pk,
                        document_id if evidence_ordinal == 1 else None,
                        (
                            f"placsp-document:{document_id}"
                            if evidence_ordinal == 1 and document_id is not None
                            else f"placsp-source-record:{row['source_record_id']}"
                        ),
                        evidence["source_url"],
                        evidence["document_url"],
                        evidence["document_label"],
                        evidence["document_kind"],
                        evidence["content_sha256"],
                        (
                            f"official_document_hash:{evidence.get('official_document_hash')}"
                            if evidence.get("official_document_hash")
                            else None
                        ),
                        evidence["evidence_state"],
                        created_at,
                        updated_at,
                    ),
                )

        target.commit()
        if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("materialized database integrity_check failed")
        if target.execute("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError("materialized database foreign_key_check failed")
        counts = {
            table: int(target.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            for table in (
                "source_records",
                "money_contract_records",
                "money_contract_award_results",
                "money_contract_documents",
                "spending_items",
                "spending_item_actors",
                "spending_item_evidence",
                "spending_item_links",
            )
        }
    except Exception:
        target.close()
        if temp_path.exists():
            temp_path.unlink()
        raise
    target.close()
    os.replace(temp_path, out_db)
    return counts


def archive_inventory(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    archives: dict[str, dict[str, Any]] = {}
    for row in rows:
        digest = str(row["archive_content_sha256"])
        archives[digest] = {
            "period": row["archive_period"],
            "source_url": row["archive_source_url"],
            "content_sha256": digest,
            "bytes": int(row["archive_bytes"]),
            "transport_security": row["transport_security"],
        }
    return sorted(
        archives.values(), key=lambda item: (item["period"], item["content_sha256"])
    )


def public_payload(
    source: sqlite3.Connection,
    rows: list[dict[str, Any]],
    input_counts: dict[str, int],
    db_counts: dict[str, int],
) -> dict[str, Any]:
    items = [canonical_item(row) for row in rows]
    identities = Counter(item["actors"][1]["source_category"] for item in items)
    amount_total = sum(
        (Decimal(item["money"]["amount_decimal"]) for item in items), Decimal(0)
    )
    payable_total = sum(
        (
            Decimal(item["money"]["payable_amount_decimal"])
            for item in items
            if item["money"]["payable_amount_decimal"] is not None
        ),
        Decimal(0),
    )
    generated_from_source_at = str(
        source.execute(
            "SELECT MAX(fetched_at) FROM placsp_bulk_archives WHERE status='ok'"
        ).fetchone()[0]
    )
    payload: dict[str, Any] = {
        "schema_version": "spending_placsp_public_sample_v1",
        "generated_from_source_at": generated_from_source_at,
        "real_data_only": True,
        "synthetic_or_mock": False,
        "public_domain_information_policy": "retained_exactly",
        "source": {
            "source_id": SOURCE_ID,
            "name": str(rows[0]["source_name"]),
            "default_url": str(rows[0]["source_default_url"]),
            "format": str(rows[0]["source_data_format"]),
            "coverage": "official PLACSP H1 2025 bulk acquisition",
            "archives": archive_inventory(rows),
            "corpus_counts": input_counts,
        },
        "methodology": {
            "selection": (
                "deterministic bounded audit sample from latest non-tombstone "
                "contract versions; complete EUR awards; distinct contracting "
                "authorities where possible; stratified 50% legal entity, 25% "
                "potential natural person, 25% unclassified"
            ),
            "representative_sample": False,
            "amount_arithmetic": "exact Decimal from source decimal strings",
            "award_is_payment": False,
            "identity_resolution": "source_scoped; no name-based merge",
            "document_capture": (
                "primary ATOM/CODICE source record bytes captured; linked official "
                "documents remain official_url_only unless a content SHA-256 exists"
            ),
            "extractor_method": EXTRACTOR_METHOD,
            "extractor_version": EXTRACTOR_VERSION,
        },
        "counts": {
            "published_items": len(items),
            "published_actors": sum(len(item["actors"]) for item in items),
            "published_evidence": sum(len(item["evidence"]) for item in items),
            "counterparty_legal_entity": identities["legal_entity"],
            "counterparty_potential_natural_person": identities[
                "potential_natural_person"
            ],
            "counterparty_unclassified": identities["unclassified"],
            "materialized_db": db_counts,
        },
        "amounts": {
            "award_amount_total_decimal": format(amount_total, "f"),
            "payable_amount_total_decimal": format(payable_total, "f"),
            "currency": "EUR",
            "amount_semantics": "award_amount",
            "tax_semantics": "excluding_tax",
        },
        "cannot_answer_yet": [
            "whether each award was formalized as a signed contract",
            "whether any invoice was accepted",
            "whether any amount was paid",
            "whether the procured work or service was delivered",
            "whether an award is unethical, irregular, illegal, or corrupt",
            "whether this bounded sample represents the full PLACSP population",
        ],
        "items": items,
    }
    release_basis = canonical_json(payload)
    payload["release_id"] = sha256_text(release_basis)
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> bytes:
    data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def main() -> int:
    args = parse_args()
    if not args.source_db.is_file():
        raise SystemExit(f"missing official PLACSP source database: {args.source_db}")
    if args.source_db.resolve() == args.out_db.resolve():
        raise SystemExit("source-db and out-db must differ")
    if not args.schema.is_file():
        raise SystemExit(f"missing schema: {args.schema}")

    source = sqlite3.connect(f"file:{args.source_db.resolve()}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    try:
        rows = select_rows(source, args.sample_size)
        input_counts = source_counts(source)
        db_counts = materialize_db(source, rows, args.schema, args.out_db)
        payload = public_payload(source, rows, input_counts, db_counts)
    finally:
        source.close()

    published_bytes = write_json(args.published_out, payload)
    public_bytes = write_json(args.public_out, payload)
    if published_bytes != public_bytes:
        raise RuntimeError("published and public artifacts differ")
    report = {
        "schema_version": "placsp_spending_materialization_report_v1",
        "status": "ok",
        "release_id": payload["release_id"],
        "real_data_only": True,
        "synthetic_or_mock": False,
        "public_domain_information_policy": "retained_exactly",
        "source_database": args.source_db.name,
        "source_counts": payload["source"]["corpus_counts"],
        "source_archives": payload["source"]["archives"],
        "materialized_counts": db_counts,
        "published_counts": payload["counts"],
        "amounts": payload["amounts"],
        "artifact_bytes": len(published_bytes),
        "artifact_sha256": hashlib.sha256(published_bytes).hexdigest(),
        "checks": {
            "latest_source_versions_only": True,
            "phase_is_procurement_award": True,
            "award_is_not_payment": True,
            "exact_decimal_arithmetic": True,
            "actor_to_item_to_evidence_complete": True,
            "public_counterparty_identity_retained": True,
            "foreign_key_check": "ok",
            "integrity_check": "ok",
        },
    }
    write_json(args.report_out, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
