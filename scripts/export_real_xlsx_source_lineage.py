#!/usr/bin/env python3
"""Export honest official-source mappings for every observed real XLSX capture."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_ROOT = Path("etl/data/raw")
DEFAULT_INVENTORY = Path("etl/data/manifests/real-document-format-inventory.jsonl")
DEFAULT_OUT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "real-xlsx-source-lineage.jsonl"
)
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "real-xlsx-cohort.json"
)
MUNICIPAL_URL = "https://concejales.redsara.es/consulta/getConcejalesLegislatura"
ANDALUCIA_BUDGET_URL = (
    "https://www.juntadeandalucia.es/datosabiertos/portal/dataset/"
    "171ed75b-9f2c-4525-910a-c37397da4ce8/resource/"
    "50eb97e4-0da7-4f61-a426-61891fd81fde/download/partidas-de-gastos.xlsx"
)
ANDALUCIA_OUTCOMES_URL = (
    "https://www.juntadeandalucia.es/datosabiertos/portal/dataset/"
    "171ed75b-9f2c-4525-910a-c37397da4ce8/resource/"
    "da2826e1-5186-4433-b8c2-a93a18753664/download/"
    "objetivos-actuaciones-e-indicadores.xlsx"
)
MUNICIPAL_CAPTURE_RE = re.compile(
    r"^municipal_concejales/\d{4}/\d{2}/\d{2}/"
    r"municipal_concejales_(?P<stamp>\d{8}T\d{6}Z)\.xlsx$"
)
ANDALUCIA_BUDGET_NAMES = {
    "partidas-de-gastos.xlsx",
    "junta_presupuesto_2026_partidas_gastos.xlsx",
}
ANDALUCIA_OUTCOME_NAMES = {
    "objetivos-actuaciones-e-indicadores.xlsx",
    "junta_presupuesto_2026_objetivos_indicadores.xlsx",
}


class XlsxLineageError(RuntimeError):
    """Raised when real XLSX source mapping cannot be reconciled exactly."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", default=str(DEFAULT_RAW_ROOT))
    parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args()


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_child(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise XlsxLineageError(f"XLSX path escapes raw root: {relative}") from exc
    return candidate


def source_contract(relative: str) -> tuple[str, str, str | None, str, str]:
    municipal = MUNICIPAL_CAPTURE_RE.fullmatch(relative)
    if municipal:
        captured_at = datetime.strptime(
            municipal.group("stamp"), "%Y%m%dT%H%M%SZ"
        ).replace(tzinfo=UTC)
        return (
            "municipal_concejales",
            MUNICIPAL_URL,
            captured_at.isoformat().replace("+00:00", "Z"),
            "capture_timestamp_from_checksum_bound_filename",
            "inferred_from_repository_path_contract_without_retrieval_receipt",
        )
    path = Path(relative)
    if relative.startswith("elections/andalucia_2026/execution_evidence/"):
        if path.name in ANDALUCIA_BUDGET_NAMES:
            return (
                "andalucia_2026_budget_expenses",
                ANDALUCIA_BUDGET_URL,
                None,
                "capture_timestamp_not_recorded",
                "inferred_from_repository_path_contract_without_retrieval_receipt",
            )
        if path.name in ANDALUCIA_OUTCOME_NAMES:
            return (
                "andalucia_2026_budget_objectives_indicators",
                ANDALUCIA_OUTCOMES_URL,
                None,
                "capture_timestamp_not_recorded",
                "inferred_from_repository_path_contract_without_retrieval_receipt",
            )
    raise XlsxLineageError(f"official source URL not mapped for real XLSX: {relative}")


def iter_rows(inventory: Path, raw_root: Path) -> Iterator[dict[str, Any]]:
    """Yield XLSX lineage rows from a path-ordered inventory manifest."""

    previous_path: str | None = None
    with inventory.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            item = json.loads(line)
            if not isinstance(item, dict):
                raise XlsxLineageError(
                    f"invalid inventory row at line {line_number}"
                )
            relative = str(item.get("path") or "")
            if (
                not relative
                or Path(relative).is_absolute()
                or ".." in Path(relative).parts
            ):
                raise XlsxLineageError(
                    f"invalid inventory path at line {line_number}: {relative}"
                )
            if previous_path is not None and relative <= previous_path:
                raise XlsxLineageError(
                    "inventory must be strictly path-ordered for streaming export: "
                    f"line {line_number}: {relative}"
                )
            previous_path = relative
            if str(item.get("extension") or "").casefold() != "xlsx":
                continue
            raw_path = safe_child(raw_root, relative)
            (
                source_id,
                source_url,
                captured_at,
                captured_at_status,
                source_url_binding_status,
            ) = source_contract(relative)
            observed_sha = sha256_path(raw_path)
            observed_bytes = raw_path.stat().st_size
            if (
                item.get("status") != "ok"
                or item.get("accountability_eligible") is not True
                or observed_sha != item.get("sha256")
                or observed_bytes != item.get("bytes")
            ):
                raise XlsxLineageError(
                    f"XLSX inventory/raw mismatch at line {line_number}: {relative}"
                )
            yield {
                "schema_version": "official_xlsx_source_mapping_v1",
                "capture": {
                    "path": f"etl/data/raw/{relative}",
                    "bytes": observed_bytes,
                    "sha256": observed_sha,
                },
                "source_id": source_id,
                "source_url": source_url,
                "captured_at": captured_at,
                "captured_at_status": captured_at_status,
                "source_url_binding_status": source_url_binding_status,
                "synthetic_or_mock_records_counted": False,
                "official_public_domain_personal_information_retained": True,
            }


def export_jsonl_atomic(
    path: Path, rows: Iterator[dict[str, Any]]
) -> dict[str, Any]:
    """Stream one atomic manifest while keeping distinct sets on disk."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    digest = hashlib.sha256()
    row_count = 0
    raw_bytes = 0
    manifest_bytes = 0
    try:
        with tempfile.TemporaryDirectory(prefix="vota-xlsx-lineage-work-") as work:
            conn = sqlite3.connect(Path(work) / "lineage.sqlite")
            conn.row_factory = sqlite3.Row
            conn.executescript(
                """
                PRAGMA journal_mode = OFF;
                PRAGMA synchronous = OFF;
                PRAGMA temp_store = FILE;
                CREATE TABLE distinct_content (
                  sha256 TEXT PRIMARY KEY
                );
                CREATE TABLE source_counts (
                  source_id TEXT PRIMARY KEY,
                  files INTEGER NOT NULL
                );
                """
            )
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    for row in rows:
                        encoded = (
                            json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n"
                        ).encode("utf-8")
                        handle.write(encoded)
                        digest.update(encoded)
                        manifest_bytes += len(encoded)
                        row_count += 1
                        capture = dict(row["capture"])
                        content_sha256 = str(capture["sha256"])
                        raw_bytes += int(capture["bytes"])
                        conn.execute(
                            "INSERT OR IGNORE INTO distinct_content(sha256) VALUES (?)",
                            (content_sha256,),
                        )
                        conn.execute(
                            """
                            INSERT INTO source_counts(source_id, files)
                            VALUES (?, 1)
                            ON CONFLICT(source_id) DO UPDATE
                            SET files = files + 1
                            """,
                            (str(row["source_id"]),),
                        )
                        if row_count % 10_000 == 0:
                            conn.commit()
                    if row_count == 0:
                        raise XlsxLineageError(
                            "inventory contains no eligible real XLSX captures"
                        )
                    handle.flush()
                    os.fsync(handle.fileno())
                conn.commit()
                distinct_contents = int(
                    conn.execute("SELECT COUNT(*) FROM distinct_content").fetchone()[0]
                )
                by_source = {
                    str(row["source_id"]): int(row["files"])
                    for row in conn.execute(
                        "SELECT source_id, files FROM source_counts ORDER BY source_id"
                    )
                }
                os.replace(temp_name, path)
            finally:
                conn.close()
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return {
        "rows": row_count,
        "distinct_content_objects": distinct_contents,
        "raw_bytes": raw_bytes,
        "manifest_bytes": manifest_bytes,
        "manifest_sha256": digest.hexdigest(),
        "by_source_id": by_source,
    }


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def main() -> int:
    args = parse_args()
    raw_root = Path(args.raw_root)
    inventory = Path(args.inventory)
    out = Path(args.out)
    report_out = Path(args.report_out)
    try:
        export = export_jsonl_atomic(out, iter_rows(inventory, raw_root))
        by_source = dict(export["by_source_id"])
        row_count = int(export["rows"])
        distinct_contents = int(export["distinct_content_objects"])
        checks = {
            "every_observed_xlsx_has_mapped_official_url": row_count > 0,
            "every_capture_checksum_reverified": True,
            "real_municipal_identity_cohort_present": by_source.get(
                "municipal_concejales", 0
            )
            > 0,
            "real_budget_accountability_cohort_present": sum(
                count
                for source, count in by_source.items()
                if source.startswith("andalucia_2026_budget_")
            )
            > 0,
            "no_synthetic_or_mock_records": True,
            "official_public_domain_personal_information_retained": True,
        }
        report = {
            "schema_version": "real_xlsx_cohort_v2",
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "mapped_unverified" if all(checks.values()) else "partial",
            "policy": {
                "official_real_workbooks_only": True,
                "synthetic_or_mock_records_counted": False,
                "official_public_domain_personal_information_retained": True,
                "unknown_official_source_mapping_is_a_hard_failure": True,
                "path_inferred_source_urls_are_not_checksum_proven_provenance": True,
                "retrieval_receipt_required_for_provenance_promotion": True,
            },
            "inputs": {
                "inventory": {
                    "path": display_path(inventory),
                    "bytes": inventory.stat().st_size,
                    "sha256": sha256_path(inventory),
                }
            },
            "manifest": {
                "path": display_path(out),
                "rows": row_count,
                "bytes": int(export["manifest_bytes"]),
                "sha256": str(export["manifest_sha256"]),
            },
            "totals": {
                "file_instances": row_count,
                "distinct_content_objects": distinct_contents,
                "duplicate_file_instances": row_count - distinct_contents,
                "raw_bytes": int(export["raw_bytes"]),
                "source_url_mappings": row_count,
                "checksum_bound_retrieval_receipts": 0,
            },
            "by_source_id": by_source,
            "bounded_execution": {
                "inventory_input_ordering": "strict_path_order_verified",
                "lineage_rows_materialized_in_memory": False,
                "distinct_content_tracking": "sqlite_disk_backed",
                "manifest_write": "streaming_atomic_replace",
            },
            "checks": checks,
            "limitations": [
                "This cohort proves XLSX extraction only; it does not claim support for other office formats.",
                "Andalucia capture timestamps were not present in durable local metadata and remain explicitly unknown.",
                "The current real cohort contains no observed formula cells; formula handling is implemented but is not empirically validated by this cohort.",
            "Raw OOXML scalar values and typed phonetic annotations are extracted; workbook visual formatting, comments, charts, and embedded media remain outside the native-text claim.",
                "Official endpoints are mapped from repository path contracts. These rows are not promoted to checksum-proven URL lineage because durable retrieval receipts are absent.",
            ],
            "next_action": (
                "Capture immutable retrieval receipts binding source URL, retrieval "
                "time, checksum, and byte count for future XLSX downloads; retain "
                "existing mappings as inferred until equivalent primary evidence exists."
            ),
        }
        write_json_atomic(report_out, report)
        if args.enforce and report["status"] != "mapped_unverified":
            raise XlsxLineageError("real XLSX cohort checks did not pass")
    except (OSError, ValueError, json.JSONDecodeError, XlsxLineageError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2
    print(
        json.dumps(
            {
                "status": report["status"],
                "file_instances": report["totals"]["file_instances"],
                "distinct_content_objects": report["totals"][
                    "distinct_content_objects"
                ],
                "manifest": report["manifest"]["path"],
                "report": display_path(report_out),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
