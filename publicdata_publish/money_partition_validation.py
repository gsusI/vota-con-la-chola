"""Independent full-row validation for public-money Parquet."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .money_partitions import (
    LEGAL_ENTITY_IDENTIFIER,
    MONEY_FACT_CONTRACT,
    NATURAL_PERSON_IDENTIFIER,
)
from .semantic_contracts import (
    MANIFEST_SCHEMA_VERSION,
    peak_rss_mb,
    private_token_findings,
    safe_child,
    safe_component,
    sha256_file,
)

VALIDATION_SCHEMA_VERSION = "public_money_partition_validation_v1"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _is_public_url(value: Any) -> bool:
    try:
        parsed = urlsplit(str(value or ""))
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _expected_jurisdiction(source_id: str, territory_code: Any) -> str:
    if "autonomico" in source_id.strip().lower():
        return "es-autonomic"
    if str(territory_code or "").strip():
        return "es-territorial"
    return "es-national"


def _expected_year(row: dict[str, Any]) -> str:
    for value in (
        row["effective_date"],
        row["published_date"],
        row["source_snapshot_date"],
    ):
        text = str(value or "")
        if len(text) >= 4 and text[:4].isdigit() and text[0] in {"1", "2"}:
            return text[:4]
    return "unknown"


def _counterparty_policy_valid(row: dict[str, Any]) -> bool:
    fact_kind = str(row["fact_kind"])
    name = row["counterparty_name"]
    identifier = row["counterparty_identifier"]
    entity_type = str(row["counterparty_entity_type"])
    publication_state = str(row["counterparty_publication_state"])
    resolution_state = str(row["counterparty_resolution_state"])
    if fact_kind == "contract_notice":
        return (
            name in (None, "")
            and identifier in (None, "")
            and entity_type == "not_available"
            and publication_state == "not_materialized"
            and resolution_state == "not_materialized_in_source_table"
        )
    if publication_state == "published_legal_entity":
        identifier_text = str(identifier or "").upper()
        return (
            entity_type == "legal_entity"
            and bool(identifier_text)
            and LEGAL_ENTITY_IDENTIFIER.fullmatch(identifier_text) is not None
            and resolution_state == "official_identifier_present_unresolved"
        )
    if publication_state == "published_natural_person":
        identifier_text = str(identifier or "").upper()
        return (
            entity_type == "potential_natural_person"
            and bool(identifier_text)
            and NATURAL_PERSON_IDENTIFIER.fullmatch(identifier_text) is not None
            and resolution_state == "official_identifier_present_unresolved"
        )
    if publication_state == "published_unclassified":
        return (
            entity_type == "unclassified"
            and (name not in (None, "") or identifier not in (None, ""))
            and resolution_state
            in {"official_identifier_present_unresolved", "name_only_unresolved"}
        )
    if publication_state == "not_available":
        return (
            name in (None, "")
            and identifier in (None, "")
            and entity_type == "unclassified"
            and resolution_state == "missing_counterparty"
        )
    return False


def _expected_spend_semantics(fact_kind: str) -> str:
    if fact_kind == "contract_notice":
        return "published_contract_notice_not_payment"
    if fact_kind == "contract_award":
        return "published_contract_award_not_payment"
    return "published_subsidy_amount_not_disbursement"


def _amount_semantics_valid(row: dict[str, Any]) -> bool:
    fact_kind = str(row["fact_kind"])
    value = str(row["amount_semantics"])
    if fact_kind == "contract_award":
        return value == "awarded_tax_exclusive_amount"
    if fact_kind == "subsidy_record":
        return value == "published_subsidy_amount"
    return value in {
        "estimated_overall_contract_amount",
        "budget_tax_exclusive_amount",
        "budget_total_amount",
        "published_contract_amount_unspecified",
    }


def _expected_relative_dir(manifest: dict[str, Any], values: dict[str, Any]) -> str:
    return Path(
        f"lane={MONEY_FACT_CONTRACT.lane}",
        f"snapshot_date={safe_component(str(manifest.get('snapshot_date') or ''))}",
        f"fact_kind={safe_component(str(values.get('fact_kind') or ''))}",
        f"source_id={safe_component(str(values.get('source_id') or ''))}",
        f"jurisdiction={safe_component(str(values.get('jurisdiction') or ''))}",
        f"year={safe_component(str(values.get('year') or ''))}",
    ).as_posix()


def validate_money_partitions(
    *,
    root: Path,
    manifest_path: Path | None = None,
    batch_rows: int = 10_000,
    min_rows: int = 1,
    max_peak_rss_mb: float = 1024.0,
) -> dict[str, Any]:
    try:
        import pyarrow.parquet as pq  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "pyarrow is required; install the project parquet extra"
        ) from exc

    if batch_rows <= 0:
        raise ValueError("batch-rows must be positive")
    root = Path(root)
    manifest_path = Path(manifest_path) if manifest_path else root / "manifest.json"
    if not root.is_dir():
        raise FileNotFoundError(root)
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_schema = MONEY_FACT_CONTRACT.arrow_schema()

    expected_paths: set[str] = set()
    seen_ids: set[str] = set()
    seen_source_records: set[int] = set()
    duplicate_paths = 0
    duplicate_ids = 0
    files_present = True
    checksums_valid = True
    schemas_valid = True
    file_rows_valid = True
    file_minmax_valid = True
    partition_rows_valid = True
    partition_hashes_valid = True
    partition_values_valid = True
    ids_sorted = True
    urls_public = True
    row_semantics_valid = True
    amount_types_valid = True
    rows_total = 0
    files_total = 0
    bytes_total = 0
    contract_notice_rows = 0
    contract_award_rows = 0
    subsidy_record_rows = 0
    source_url_rows = 0
    source_record_rows = 0
    amount_rows = 0
    nonnegative_amount_rows = 0
    eur_rows = 0
    counterparty_name_rows = 0
    counterparty_identifier_rows = 0
    counterparty_published_rows = 0
    counterparty_published_legal_entity_rows = 0
    counterparty_published_natural_person_rows = 0
    counterparty_published_unclassified_rows = 0
    counterparty_not_available_rows = 0
    unknown_year_rows = 0
    private_findings = 0
    amount_total = Decimal(0)
    amount_by_kind: dict[str, Decimal] = {}
    partition_reports: list[dict[str, Any]] = []

    for partition in list(manifest.get("partitions") or []):
        digest = hashlib.sha256()
        partition_rows = 0
        partition_min_id: str | None = None
        partition_max_id: str | None = None
        partition_previous_id: str | None = None
        partition_amount = Decimal(0)
        values = dict(partition.get("values") or {})
        expected_relative_dir = _expected_relative_dir(manifest, values)
        expected_partition_id = "|".join(
            str(values.get(key) or "")
            for key in ("fact_kind", "source_id", "jurisdiction", "year")
        )
        if str(partition.get("relative_dir") or "") != expected_relative_dir:
            partition_values_valid = False
        if str(partition.get("partition_id") or "") != expected_partition_id:
            partition_values_valid = False
        if str(values.get("snapshot_date") or "") != str(
            manifest.get("snapshot_date") or ""
        ):
            partition_values_valid = False
        partition_metrics = {
            "source_url_rows": 0,
            "source_record_rows": 0,
            "amount_rows": 0,
            "nonnegative_amount_rows": 0,
            "eur_rows": 0,
            "counterparty_name_rows": 0,
            "counterparty_identifier_rows": 0,
            "counterparty_published_rows": 0,
            "counterparty_published_legal_entity_rows": 0,
            "counterparty_published_natural_person_rows": 0,
            "counterparty_published_unclassified_rows": 0,
            "counterparty_not_available_rows": 0,
            "private_token_findings": 0,
        }
        partition_file_reports: list[dict[str, Any]] = []
        for file_meta in list(partition.get("files") or []):
            relative = str(file_meta.get("path") or "")
            if relative in expected_paths:
                duplicate_paths += 1
            expected_paths.add(relative)
            if Path(relative).parent.as_posix() != expected_relative_dir:
                partition_values_valid = False
            file_path = safe_child(root, relative)
            files_total += 1
            if file_path is None or not file_path.is_file():
                files_present = False
                continue
            actual_bytes = int(file_path.stat().st_size)
            actual_sha256 = sha256_file(file_path)
            bytes_total += actual_bytes
            if actual_bytes != int(file_meta.get("bytes") or -1):
                checksums_valid = False
            if actual_sha256 != str(file_meta.get("sha256") or ""):
                checksums_valid = False
            parquet_file = pq.ParquetFile(file_path)
            if not parquet_file.schema_arrow.equals(
                expected_schema, check_metadata=True
            ):
                schemas_valid = False
            expected_file_rows = int(file_meta.get("rows") or 0)
            if int(parquet_file.metadata.num_rows) != expected_file_rows:
                file_rows_valid = False
            file_rows = 0
            file_min_id: str | None = None
            file_max_id: str | None = None
            for batch in parquet_file.iter_batches(batch_size=batch_rows):
                columns = {
                    name: batch.column(index).to_pylist()
                    for index, name in enumerate(MONEY_FACT_CONTRACT.columns)
                }
                for row_index in range(batch.num_rows):
                    row = {
                        name: columns[name][row_index]
                        for name in MONEY_FACT_CONTRACT.columns
                    }
                    money_fact_id = str(row["money_fact_id"])
                    if money_fact_id in seen_ids:
                        duplicate_ids += 1
                    seen_ids.add(money_fact_id)
                    seen_source_records.add(int(row["source_record_pk"]))
                    if (
                        partition_previous_id is not None
                        and money_fact_id <= partition_previous_id
                    ):
                        ids_sorted = False
                    partition_previous_id = money_fact_id
                    file_min_id = (
                        money_fact_id
                        if file_min_id is None
                        else min(file_min_id, money_fact_id)
                    )
                    file_max_id = (
                        money_fact_id
                        if file_max_id is None
                        else max(file_max_id, money_fact_id)
                    )
                    partition_min_id = (
                        money_fact_id
                        if partition_min_id is None
                        else min(partition_min_id, money_fact_id)
                    )
                    partition_max_id = (
                        money_fact_id
                        if partition_max_id is None
                        else max(partition_max_id, money_fact_id)
                    )
                    for field, key in (
                        ("fact_kind", "fact_kind"),
                        ("source_id", "source_id"),
                        ("jurisdiction", "jurisdiction"),
                        ("fact_year", "year"),
                    ):
                        if str(row[field]) != str(values.get(key)):
                            partition_values_valid = False
                    fact_kind = str(row["fact_kind"])
                    if fact_kind == "contract_notice":
                        contract_notice_rows += 1
                    elif fact_kind == "contract_award":
                        contract_award_rows += 1
                    elif fact_kind == "subsidy_record":
                        subsidy_record_rows += 1
                    else:
                        row_semantics_valid = False
                    if not money_fact_id.startswith(fact_kind + ":"):
                        row_semantics_valid = False
                    if row["jurisdiction"] != _expected_jurisdiction(
                        str(row["source_id"]), row["territory_code"]
                    ):
                        row_semantics_valid = False
                    if row["fact_year"] != _expected_year(row):
                        row_semantics_valid = False
                    if _is_public_url(row["source_url"]):
                        source_url_rows += 1
                        partition_metrics["source_url_rows"] += 1
                    else:
                        urls_public = False
                    if row["source_url_scope"] not in {"record", "source_default"}:
                        row_semantics_valid = False
                    if row["source_record_pk"] is not None:
                        source_record_rows += 1
                        partition_metrics["source_record_rows"] += 1
                    if row["lineage_state"] != "source_record":
                        row_semantics_valid = False
                    if not _counterparty_policy_valid(row):
                        row_semantics_valid = False
                    if row["spend_semantics"] != _expected_spend_semantics(fact_kind):
                        row_semantics_valid = False
                    if not _amount_semantics_valid(row):
                        row_semantics_valid = False
                    if row["counterparty_name"] not in (None, ""):
                        counterparty_name_rows += 1
                        partition_metrics["counterparty_name_rows"] += 1
                    if row["counterparty_identifier"] not in (None, ""):
                        counterparty_identifier_rows += 1
                        partition_metrics["counterparty_identifier_rows"] += 1
                    publication_state = str(row["counterparty_publication_state"])
                    if publication_state == "published_legal_entity":
                        counterparty_published_rows += 1
                        partition_metrics["counterparty_published_rows"] += 1
                        counterparty_published_legal_entity_rows += 1
                        partition_metrics[
                            "counterparty_published_legal_entity_rows"
                        ] += 1
                    elif publication_state == "published_natural_person":
                        counterparty_published_rows += 1
                        partition_metrics["counterparty_published_rows"] += 1
                        counterparty_published_natural_person_rows += 1
                        partition_metrics[
                            "counterparty_published_natural_person_rows"
                        ] += 1
                    elif publication_state == "published_unclassified":
                        counterparty_published_rows += 1
                        partition_metrics["counterparty_published_rows"] += 1
                        counterparty_published_unclassified_rows += 1
                        partition_metrics[
                            "counterparty_published_unclassified_rows"
                        ] += 1
                    elif publication_state == "not_available":
                        counterparty_not_available_rows += 1
                        partition_metrics["counterparty_not_available_rows"] += 1
                    amount = row["amount_eur"]
                    if amount is not None:
                        if not isinstance(amount, Decimal):
                            amount_types_valid = False
                        else:
                            amount_rows += 1
                            partition_metrics["amount_rows"] += 1
                            amount_total += amount
                            partition_amount += amount
                            amount_by_kind[fact_kind] = (
                                amount_by_kind.get(fact_kind, Decimal(0)) + amount
                            )
                            if amount >= 0:
                                nonnegative_amount_rows += 1
                                partition_metrics["nonnegative_amount_rows"] += 1
                        expected_amount_state = (
                            "present_nonnegative"
                            if isinstance(amount, Decimal) and amount >= 0
                            else "present_negative"
                        )
                    else:
                        expected_amount_state = "missing"
                    if row["amount_state"] != expected_amount_state:
                        row_semantics_valid = False
                    if row["currency"] == "EUR":
                        eur_rows += 1
                        partition_metrics["eur_rows"] += 1
                    if amount is None and row["currency"] not in (None, ""):
                        row_semantics_valid = False
                    if amount is not None and row["currency"] != "EUR":
                        row_semantics_valid = False
                    if row["fact_year"] == "unknown":
                        unknown_year_rows += 1
                    row_private_findings = private_token_findings(row)
                    private_findings += row_private_findings
                    partition_metrics["private_token_findings"] += row_private_findings
                    digest.update(MONEY_FACT_CONTRACT.canonical_row_bytes(row))
                    file_rows += 1
                    partition_rows += 1
                    rows_total += 1
            if file_rows != expected_file_rows:
                file_rows_valid = False
            if file_min_id != file_meta.get("min_id"):
                file_minmax_valid = False
            if file_max_id != file_meta.get("max_id"):
                file_minmax_valid = False
            partition_file_reports.append(
                {
                    "path": relative,
                    "rows": file_rows,
                    "bytes": actual_bytes,
                    "sha256": actual_sha256,
                }
            )
        if partition_rows != int(partition.get("rows") or 0):
            partition_rows_valid = False
        if partition_min_id != partition.get("min_id"):
            partition_rows_valid = False
        if partition_max_id != partition.get("max_id"):
            partition_rows_valid = False
        if format(partition_amount, "f") != str(
            partition.get("amount_eur_total") or ""
        ):
            partition_rows_valid = False
        if any(
            key not in partition or int(partition.get(key) or 0) != value
            for key, value in partition_metrics.items()
        ):
            partition_rows_valid = False
        actual_input_sha256 = digest.hexdigest()
        if actual_input_sha256 != str(partition.get("input_sha256") or ""):
            partition_hashes_valid = False
        partition_reports.append(
            {
                "partition_id": partition.get("partition_id"),
                "rows": partition_rows,
                "files": partition_file_reports,
                "input_sha256": actual_input_sha256,
                "amount_eur_total": format(partition_amount, "f"),
            }
        )

    actual_paths = {
        path.relative_to(root).as_posix() for path in root.rglob("*.parquet")
    }
    amount_by_kind_text = {
        key: format(value, "f") for key, value in sorted(amount_by_kind.items())
    }
    calculated_totals: dict[str, Any] = {
        "contract_table_rows": contract_notice_rows,
        "contract_award_table_rows": contract_award_rows,
        "subsidy_table_rows": subsidy_record_rows,
        "money_table_rows": rows_total,
        "joined_rows": rows_total,
        "distinct_source_records": len(seen_source_records),
        "rows": rows_total,
        "contract_notice_rows": contract_notice_rows,
        "contract_award_rows": contract_award_rows,
        "subsidy_record_rows": subsidy_record_rows,
        "source_url_rows": source_url_rows,
        "source_record_rows": source_record_rows,
        "amount_rows": amount_rows,
        "nonnegative_amount_rows": nonnegative_amount_rows,
        "eur_rows": eur_rows,
        "counterparty_name_rows": counterparty_name_rows,
        "counterparty_identifier_rows": counterparty_identifier_rows,
        "counterparty_published_rows": counterparty_published_rows,
        "counterparty_published_legal_entity_rows": (
            counterparty_published_legal_entity_rows
        ),
        "counterparty_published_natural_person_rows": (
            counterparty_published_natural_person_rows
        ),
        "counterparty_published_unclassified_rows": (
            counterparty_published_unclassified_rows
        ),
        "counterparty_not_available_rows": counterparty_not_available_rows,
        "unknown_year_rows": unknown_year_rows,
        "private_token_findings": private_findings,
        "amount_eur_total": format(amount_total, "f"),
        "amount_eur_by_fact_kind": amount_by_kind_text,
        "partitions": len(partition_reports),
        "files": files_total,
        "parquet_bytes": bytes_total,
    }
    expected_coverage = {
        "source_url": round(source_url_rows / rows_total, 8) if rows_total else 0.0,
        "source_record": round(source_record_rows / rows_total, 8)
        if rows_total
        else 0.0,
        "amount": round(amount_rows / rows_total, 8) if rows_total else 0.0,
        "counterparty_name": round(counterparty_name_rows / rows_total, 8)
        if rows_total
        else 0.0,
        "counterparty_identifier": round(counterparty_identifier_rows / rows_total, 8)
        if rows_total
        else 0.0,
        "counterparty_publication_state": round(
            (counterparty_published_rows + counterparty_not_available_rows)
            / (subsidy_record_rows + contract_award_rows),
            8,
        )
        if subsidy_record_rows + contract_award_rows
        else 1.0,
    }
    totals = dict(manifest.get("totals") or {})
    peak_rss = peak_rss_mb()
    checks = {
        "manifest_schema": manifest.get("schema_version") == MANIFEST_SCHEMA_VERSION,
        "lane": manifest.get("lane") == MONEY_FACT_CONTRACT.lane,
        "transformer_version": manifest.get("transformer_version")
        == MONEY_FACT_CONTRACT.transformer_version,
        "schema_sha256": manifest.get("schema_sha256")
        == MONEY_FACT_CONTRACT.schema_sha256,
        "manifest_schema_definition": manifest.get("schema")
        == list(MONEY_FACT_CONTRACT.schema),
        "minimum_rows": rows_total >= int(min_rows),
        "all_files_present": files_present,
        "no_duplicate_manifest_paths": duplicate_paths == 0,
        "no_extra_parquet_files": actual_paths == expected_paths,
        "checksums_and_bytes": checksums_valid,
        "parquet_schemas": schemas_valid,
        "file_rows": file_rows_valid,
        "file_minmax": file_minmax_valid,
        "partition_rows_and_money": partition_rows_valid,
        "partition_hashes": partition_hashes_valid,
        "partition_values": partition_values_valid,
        "money_fact_ids_sorted_within_partitions": ids_sorted,
        "money_fact_ids_unique": duplicate_ids == 0 and len(seen_ids) == rows_total,
        "manifest_metric_totals": all(
            key in totals and totals[key] == value
            for key, value in calculated_totals.items()
        ),
        "manifest_coverage": manifest.get("coverage") == expected_coverage,
        "source_urls_complete_and_public": urls_public
        and source_url_rows == rows_total,
        "source_records_complete": source_record_rows == rows_total,
        "row_semantics_consistent": row_semantics_valid,
        "decimal_amount_types": amount_types_valid,
        "amount_states_explicit": amount_rows <= rows_total,
        "amounts_nonnegative": nonnegative_amount_rows == amount_rows,
        "currency_eur_for_amounts": eur_rows == amount_rows,
        "no_private_tokens": private_findings == 0,
        "public_domain_counterparty_retention_complete": (
            counterparty_published_rows + counterparty_not_available_rows
            == subsidy_record_rows + contract_award_rows
        ),
        "counterparty_names_retained_exactly": int(
            totals.get("source_counterparty_name_rows") or 0
        )
        == counterparty_name_rows,
        "counterparty_identifiers_retained_exactly": int(
            totals.get("source_counterparty_identifier_rows") or 0
        )
        == counterparty_identifier_rows,
        "counterparty_publication_assurance": manifest.get(
            "counterparty_publication_assurance"
        )
        == (
            "all_official_public_domain_names_and_identifiers_retained;"
            "entity_type_is_classification_not_suppression"
        ),
        "bounded_peak_rss": peak_rss <= float(max_peak_rss_mb),
    }
    status = "ok" if all(checks.values()) else "failed"
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "status": status,
        "manifest_file": manifest_path.name,
        "root_name": root.name,
        "checks": checks,
        "totals": calculated_totals,
        "coverage": expected_coverage,
        "performance": {
            "peak_rss_mb": peak_rss,
            "max_peak_rss_mb": float(max_peak_rss_mb),
            "batch_rows": int(batch_rows),
        },
        "money_assurance": manifest.get("money_assurance"),
        "counterparty_publication_assurance": manifest.get(
            "counterparty_publication_assurance"
        ),
        "publication_status": manifest.get("publication_status"),
        "analytical_partition_gate_passed": all(checks.values()),
        "promotion_gate_passed": bool(manifest.get("promotion_gate_passed"))
        and all(checks.values()),
        "partitions": partition_reports,
    }


__all__ = ["VALIDATION_SCHEMA_VERSION", "validate_money_partitions"]
