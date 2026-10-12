#!/usr/bin/env python3
"""Fail-closed validation for the real PLACSP spending sample."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DB = REPO_ROOT / "etl/data/staging/placsp-contracts-real-s1-20260811.db"
DEFAULT_DB = REPO_ROOT / "etl/data/staging/spending-placsp-mvp.db"
DEFAULT_PUBLISHED = REPO_ROOT / "etl/data/published/spending-placsp-sample.json"
DEFAULT_PUBLIC = REPO_ROOT / "ui/site/public/spending/data/placsp-sample.json"
DEFAULT_REPORT = (
    REPO_ROOT
    / "docs/etl/sprints/SPENDING-20260819/evidence/placsp-spending-validation.json"
)

NULL = "\0"
LEGAL_ENTITY_IDENTIFIER = re.compile(
    r"^[ABCDEFGHJNPQRSUVW][0-9]{7}[0-9A-J]$", re.IGNORECASE
)
NATURAL_PERSON_IDENTIFIER = re.compile(
    r"^(?:[0-9]{8}[A-Z]|[XYZ][0-9]{7}[A-Z])$", re.IGNORECASE
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-db", type=Path, default=DEFAULT_SOURCE_DB)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--published", type=Path, default=DEFAULT_PUBLISHED)
    parser.add_argument("--public", type=Path, default=DEFAULT_PUBLIC)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--frozen",
        action="store_true",
        help=(
            "The source DB is a frozen snapshot that may be archived off disk: verify the "
            "committed artifacts against the last full validation report instead."
        ),
    )
    return parser.parse_args()


def verify_frozen(args: argparse.Namespace) -> int:
    """Without the source DB, the artifacts must be byte-identical to what the last full run validated."""
    missing = [str(path) for path in (args.published, args.public, args.report_out) if not path.is_file()]
    if missing:
        raise SystemExit(f"missing frozen artifacts: {missing}")
    report = json.loads(args.report_out.read_text(encoding="utf-8"))
    published_bytes = args.published.read_bytes()
    payload = json.loads(published_bytes)
    release = payload.pop("release_id", None)
    errors: list[str] = []
    if report.get("status") != "ok":
        errors.append(f"last full validation status={report.get('status')!r}")
    if published_bytes != args.public.read_bytes():
        errors.append("published and static public JSON differ")
    if sha256_bytes(published_bytes) != report.get("artifact_sha256"):
        errors.append("artifact sha256 differs from the last full validation")
    if release != report.get("release_id") or release != sha256_bytes(canonical_json(payload).encode("utf-8")):
        errors.append("release_id does not match the artifact or the last full validation")
    print(json.dumps({"mode": "frozen", "source_db": str(args.source_db), "release_id": release, "errors": errors}, indent=2))
    return 0 if not errors else 1


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_id(kind: str, *parts: object) -> str:
    payload = NULL.join([kind, *(str(part or "") for part in parts)])
    return f"vclc:{kind}:{sha256_bytes(payload.encode('utf-8'))}"


def identity_category(identifier: object) -> str:
    value = str(identifier or "").strip().upper()
    if value and LEGAL_ENTITY_IDENTIFIER.fullmatch(value):
        return "legal_entity"
    if value and NATURAL_PERSON_IDENTIFIER.fullmatch(value):
        return "potential_natural_person"
    return "unclassified"


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        table: int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
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


def source_table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        table: int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        for table in (
            "money_contract_records",
            "money_contract_award_results",
            "money_contract_documents",
            "source_records",
            "placsp_bulk_archives",
            "placsp_bulk_members",
            "placsp_bulk_record_sightings",
        )
    }


def validate_item(
    source: sqlite3.Connection,
    materialized: sqlite3.Connection,
    item: dict[str, Any],
    errors: list[str],
) -> tuple[Decimal, Decimal]:
    item_id = str(item.get("spending_item_id") or "")
    provenance = item.get("provenance") or {}
    money = item.get("money") or {}
    dates = item.get("dates") or {}
    actors = item.get("actors") or []
    evidence = item.get("evidence") or []
    source_record_id = str(provenance.get("source_record_id") or "")
    semantic_ordinal = int(item.get("semantic_ordinal", -1))
    expected_id = stable_id(
        "spending-item",
        provenance.get("source_id"),
        source_record_id,
        "procurement_award",
        semantic_ordinal,
    )
    if item_id != expected_id:
        errors.append(f"unstable spending item ID: {item_id}")
    if item.get("spending_kind") != "procurement_award":
        errors.append(f"unexpected spending kind: {item_id}")
    if (
        item.get("phase_caveat")
        != "adjudicacion_publicada_no_prueba_contrato_pago_ni_entrega"
    ):
        errors.append(f"missing award phase caveat: {item_id}")
    if money.get("amount_semantics") != "award_amount":
        errors.append(f"invalid amount semantics: {item_id}")
    if money.get("tax_semantics") != "excluding_tax":
        errors.append(f"invalid tax semantics: {item_id}")
    if dates.get("paid_on") is not None or dates.get("delivered_on") is not None:
        errors.append(f"award falsely carries payment/delivery date: {item_id}")
    if len(actors) != 2:
        errors.append(f"item must expose authority and supplier: {item_id}")
        return Decimal(0), Decimal(0)
    if [actor.get("actor_role") for actor in actors] != [
        "contracting_authority",
        "supplier",
    ]:
        errors.append(f"actor roles differ from contract: {item_id}")
    if not evidence or evidence[0].get("evidence_state") != "captured_bytes":
        errors.append(f"primary captured evidence missing: {item_id}")

    source_row = source.execute(
        """
        SELECT
          sr.source_record_pk,
          sr.content_sha256,
          c.contract_record_id,
          c.stable_contract_id,
          c.contracting_authority,
          c.authority_identifier,
          c.source_url,
          c.published_date,
          c.entry_updated_at,
          award.contract_award_result_id,
          award.supplier_name,
          award.supplier_identifier,
          award.supplier_identifier_scheme,
          award.amount_eur_decimal,
          award.payable_amount_eur_decimal,
          award.award_date
        FROM source_records AS sr
        JOIN money_contract_records AS c ON c.source_record_pk = sr.source_record_pk
        JOIN money_contract_award_results AS award
          ON award.source_record_pk = sr.source_record_pk
         AND award.award_ordinal = ?
        WHERE sr.source_id = ? AND sr.source_record_id = ?
        """,
        (semantic_ordinal, provenance.get("source_id"), source_record_id),
    ).fetchone()
    if source_row is None:
        errors.append(f"source award missing: {item_id}")
        return Decimal(0), Decimal(0)

    latest_source_pk = source.execute(
        """
        SELECT candidate.source_record_pk
        FROM money_contract_records AS candidate
        WHERE candidate.source_id = ?
          AND COALESCE(NULLIF(candidate.stable_contract_id, ''),
                       'source:' || candidate.source_record_id) = ?
        ORDER BY
          COALESCE(NULLIF(candidate.entry_updated_at, ''),
                   NULLIF(candidate.awarded_date, ''),
                   NULLIF(candidate.published_date, ''),
                   candidate.source_snapshot_date, '') DESC,
          candidate.contract_record_id DESC
        LIMIT 1
        """,
        (provenance.get("source_id"), source_row["stable_contract_id"]),
    ).fetchone()
    if latest_source_pk is None or int(latest_source_pk[0]) != int(
        source_row["source_record_pk"]
    ):
        errors.append(f"sample uses superseded source version: {item_id}")

    supplier = actors[1]
    authority = actors[0]
    exact_pairs = (
        (
            provenance.get("source_record_sha256"),
            source_row["content_sha256"],
            "record hash",
        ),
        (provenance.get("source_url"), source_row["source_url"], "record URL"),
        (
            authority.get("source_label"),
            source_row["contracting_authority"],
            "authority name",
        ),
        (
            authority.get("source_identifier"),
            str(source_row["authority_identifier"] or "").upper() or None,
            "authority identifier",
        ),
        (supplier.get("source_label"), source_row["supplier_name"], "supplier name"),
        (
            supplier.get("source_identifier"),
            str(source_row["supplier_identifier"] or "").upper() or None,
            "supplier identifier",
        ),
        (
            supplier.get("source_identifier_scheme"),
            source_row["supplier_identifier_scheme"],
            "supplier identifier scheme",
        ),
        (money.get("amount_decimal"), source_row["amount_eur_decimal"], "award amount"),
        (
            money.get("payable_amount_decimal"),
            source_row["payable_amount_eur_decimal"],
            "payable amount",
        ),
        (dates.get("decision_on"), source_row["award_date"], "award date"),
    )
    for actual, expected, label in exact_pairs:
        if actual != expected:
            errors.append(f"{label} not retained exactly: {item_id}")

    db_item = materialized.execute(
        """
        SELECT source_record_pk, amount_decimal, payable_amount_decimal,
               spending_kind, amount_semantics, paid_on, delivered_on
        FROM spending_items WHERE spending_item_id = ?
        """,
        (item_id,),
    ).fetchone()
    if db_item is None:
        errors.append(f"materialized spending item missing: {item_id}")
    else:
        if int(db_item["source_record_pk"]) != int(source_row["source_record_pk"]):
            errors.append(f"materialized source record mismatch: {item_id}")
        if db_item["amount_decimal"] != money.get("amount_decimal"):
            errors.append(f"materialized amount mismatch: {item_id}")
        if db_item["payable_amount_decimal"] != money.get("payable_amount_decimal"):
            errors.append(f"materialized payable amount mismatch: {item_id}")
        if db_item["spending_kind"] != "procurement_award":
            errors.append(f"materialized kind mismatch: {item_id}")
        if db_item["amount_semantics"] != "award_amount":
            errors.append(f"materialized amount semantics mismatch: {item_id}")
        if db_item["paid_on"] is not None or db_item["delivered_on"] is not None:
            errors.append(f"materialized award implies payment/delivery: {item_id}")

    actor_rows = materialized.execute(
        """
        SELECT actor_role, actor_kind, source_label, source_identifier,
               source_identifier_scheme, identity_state
        FROM spending_item_actors
        WHERE spending_item_id = ?
        ORDER BY actor_ordinal
        """,
        (item_id,),
    ).fetchall()
    if len(actor_rows) != 2:
        errors.append(f"materialized actors missing: {item_id}")
    else:
        for actor, actor_row in zip(actors, actor_rows, strict=True):
            for field in (
                "actor_role",
                "actor_kind",
                "source_label",
                "source_identifier",
                "source_identifier_scheme",
                "identity_state",
            ):
                if actor.get(field) != actor_row[field]:
                    errors.append(f"materialized actor {field} mismatch: {item_id}")

    evidence_rows = materialized.execute(
        """
        SELECT evidence_role, source_url, document_url, document_label,
               document_kind, content_sha256, evidence_state
        FROM spending_item_evidence
        WHERE spending_item_id = ?
        ORDER BY evidence_ordinal
        """,
        (item_id,),
    ).fetchall()
    if len(evidence_rows) != len(evidence):
        errors.append(f"materialized evidence count mismatch: {item_id}")
    else:
        for evidence_item, evidence_row in zip(evidence, evidence_rows, strict=True):
            for field in (
                "evidence_role",
                "source_url",
                "document_url",
                "document_label",
                "document_kind",
                "content_sha256",
                "evidence_state",
            ):
                if evidence_item.get(field) != evidence_row[field]:
                    errors.append(f"materialized evidence {field} mismatch: {item_id}")

    amount = Decimal(str(money["amount_decimal"]))
    payable = (
        Decimal(str(money["payable_amount_decimal"]))
        if money.get("payable_amount_decimal") is not None
        else Decimal(0)
    )
    return amount, payable


def validate_archives(
    source: sqlite3.Connection,
    payload: dict[str, Any],
    errors: list[str],
) -> list[dict[str, Any]]:
    checked: list[dict[str, Any]] = []
    for archive in payload.get("source", {}).get("archives", []):
        source_row = source.execute(
            """
            SELECT source_url, content_sha256, bytes, raw_path, status
            FROM placsp_bulk_archives WHERE content_sha256 = ?
            """,
            (archive.get("content_sha256"),),
        ).fetchone()
        if source_row is None:
            errors.append(f"archive lineage missing: {archive.get('content_sha256')}")
            continue
        raw_path = REPO_ROOT / str(source_row["raw_path"])
        if not raw_path.is_file():
            errors.append(f"archive object missing: {source_row['raw_path']}")
            continue
        observed_sha = sha256_file(raw_path)
        observed_bytes = raw_path.stat().st_size
        if observed_sha != archive.get("content_sha256"):
            errors.append(f"archive hash mismatch: {source_row['raw_path']}")
        if observed_bytes != int(archive.get("bytes", -1)):
            errors.append(f"archive byte mismatch: {source_row['raw_path']}")
        if source_row["source_url"] != archive.get("source_url"):
            errors.append(f"archive URL mismatch: {source_row['raw_path']}")
        if source_row["status"] != "ok":
            errors.append(f"archive status is not ok: {source_row['raw_path']}")
        checked.append(
            {
                "source_url": source_row["source_url"],
                "raw_path": source_row["raw_path"],
                "bytes": observed_bytes,
                "sha256": observed_sha,
            }
        )
    return checked


def main() -> int:
    args = parse_args()
    if args.frozen and not args.source_db.is_file():
        return verify_frozen(args)
    errors: list[str] = []
    required = (args.source_db, args.db, args.published, args.public)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit(f"missing required real artifacts: {missing}")

    published_bytes = args.published.read_bytes()
    public_bytes = args.public.read_bytes()
    if published_bytes != public_bytes:
        errors.append("published and static public JSON differ")
    try:
        payload = json.loads(published_bytes)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid published JSON: {exc}") from exc

    release = payload.pop("release_id", None)
    expected_release = sha256_bytes(canonical_json(payload).encode("utf-8"))
    payload["release_id"] = release
    if release != expected_release:
        errors.append("release_id does not match canonical artifact basis")
    if payload.get("real_data_only") is not True:
        errors.append("real_data_only is not true")
    if payload.get("synthetic_or_mock") is not False:
        errors.append("synthetic_or_mock is not false")
    if payload.get("public_domain_information_policy") != "retained_exactly":
        errors.append("public-domain identity retention policy mismatch")
    if payload.get("methodology", {}).get("award_is_payment") is not False:
        errors.append("methodology does not state that award is not payment")
    if payload.get("methodology", {}).get("representative_sample") is not False:
        errors.append("bounded audit sample is mislabeled as representative")

    source = sqlite3.connect(f"file:{args.source_db.resolve()}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    materialized = sqlite3.connect(f"file:{args.db.resolve()}?mode=ro", uri=True)
    materialized.row_factory = sqlite3.Row
    try:
        observed_source_counts = source_table_counts(source)
        if observed_source_counts != payload.get("source", {}).get("corpus_counts"):
            errors.append("source corpus counts do not match current official database")
        observed_db_counts = table_counts(materialized)
        if observed_db_counts != payload.get("counts", {}).get("materialized_db"):
            errors.append("materialized table counts do not match public artifact")
        integrity = str(materialized.execute("PRAGMA integrity_check").fetchone()[0])
        fk_rows = materialized.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != "ok":
            errors.append(f"materialized integrity_check={integrity}")
        if fk_rows:
            errors.append(f"materialized foreign_key_check rows={len(fk_rows)}")

        items = payload.get("items") or []
        if len(items) != 20:
            errors.append(f"expected 20 public items, found {len(items)}")
        ids = [item.get("spending_item_id") for item in items]
        if len(ids) != len(set(ids)):
            errors.append("duplicate public spending item IDs")
        amount_total = Decimal(0)
        payable_total = Decimal(0)
        categories: Counter[str] = Counter()
        for item in items:
            item_amount, item_payable = validate_item(
                source, materialized, item, errors
            )
            amount_total += item_amount
            payable_total += item_payable
            actors = item.get("actors") or []
            if len(actors) >= 2:
                category = identity_category(actors[1].get("source_identifier"))
                categories[category] += 1
                if category != actors[1].get("source_category"):
                    errors.append(
                        f"counterparty category mismatch: {item.get('spending_item_id')}"
                    )
        amounts = payload.get("amounts") or {}
        if format(amount_total, "f") != amounts.get("award_amount_total_decimal"):
            errors.append("exact award amount total mismatch")
        if format(payable_total, "f") != amounts.get("payable_amount_total_decimal"):
            errors.append("exact payable amount total mismatch")
        expected_categories = {
            "legal_entity": int(
                payload.get("counts", {}).get("counterparty_legal_entity", -1)
            ),
            "potential_natural_person": int(
                payload.get("counts", {}).get(
                    "counterparty_potential_natural_person", -1
                )
            ),
            "unclassified": int(
                payload.get("counts", {}).get("counterparty_unclassified", -1)
            ),
        }
        if dict(categories) != expected_categories:
            errors.append("counterparty identity strata mismatch")
        archive_checks = validate_archives(source, payload, errors)
    finally:
        source.close()
        materialized.close()

    report = {
        "schema_version": "placsp_spending_validation_v1",
        "status": "ok" if not errors else "error",
        "release_id": release,
        "artifact_bytes": len(published_bytes),
        "artifact_sha256": sha256_bytes(published_bytes),
        "source_counts": observed_source_counts,
        "materialized_counts": observed_db_counts,
        "validated_items": len(payload.get("items") or []),
        "validated_actor_rows": sum(
            len(item.get("actors") or []) for item in payload.get("items") or []
        ),
        "validated_evidence_rows": sum(
            len(item.get("evidence") or []) for item in payload.get("items") or []
        ),
        "counterparty_identity_strata": dict(categories),
        "amounts": {
            "award_amount_total_decimal": format(amount_total, "f"),
            "payable_amount_total_decimal": format(payable_total, "f"),
        },
        "official_archives_verified": archive_checks,
        "checks": {
            "release_hash": release == expected_release,
            "published_public_parity": published_bytes == public_bytes,
            "real_data_only": payload.get("real_data_only") is True,
            "public_identity_retained_exactly": not any(
                "not retained exactly" in error for error in errors
            ),
            "award_not_payment": not any(
                "payment" in error or "paid" in error for error in errors
            ),
            "exact_decimal_reconciliation": not any(
                "amount total mismatch" in error for error in errors
            ),
            "integrity_check": integrity,
            "foreign_key_rows": len(fk_rows),
        },
        "errors": errors,
    }
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
