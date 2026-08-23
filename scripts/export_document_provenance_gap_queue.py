#!/usr/bin/env python3
"""Export a deterministic remediation queue for real document provenance gaps."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FILE_MANIFEST = Path("etl/data/manifests/real-document-provenance-files.jsonl")
DEFAULT_AUDIT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "real-document-provenance-audit.json"
)
DEFAULT_QUEUE = Path("etl/data/manifests/document-provenance-gap-queue.jsonl")
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "document-provenance-gap-queue-20260812.json"
)
SHA256_RE_LENGTH = 64
VERIFIED_CHECKSUM_STATUSES = {
    "verified_path_checksum",
    "verified_content_checksum",
    "verified_embedded_url_checksum",
}


class GapQueueError(RuntimeError):
    """Raised when provenance inputs or queue output violate the contract."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file-manifest", default=str(DEFAULT_FILE_MANIFEST))
    parser.add_argument("--audit-report", default=str(DEFAULT_AUDIT_REPORT))
    parser.add_argument("--queue-out", default=str(DEFAULT_QUEUE))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def safe_repo_path(value: str | Path, *, repo_root: Path) -> Path:
    candidate = (repo_root / value).resolve()
    try:
        candidate.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise GapQueueError(f"path escapes repository: {value}") from exc
    return candidate


def display_path(path: Path, *, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.name


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GapQueueError(f"invalid JSON object {path.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise GapQueueError(f"JSON root must be an object: {path.name}")
    return payload


def validate_manifest_reference(
    *,
    file_manifest: Path,
    audit: dict[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    reference = audit.get("file_manifest")
    if not isinstance(reference, dict):
        raise GapQueueError("audit report has no file_manifest reference")
    observed = {
        "path": display_path(file_manifest, repo_root=repo_root),
        "bytes": file_manifest.stat().st_size,
        "sha256": sha256_file(file_manifest),
    }
    for key in ("path", "bytes", "sha256"):
        if observed[key] != reference.get(key):
            raise GapQueueError(f"file manifest {key} does not match audit report")
    if not bool((audit.get("checks") or {}).get("integrity_passed")):
        raise GapQueueError("document provenance audit integrity gate is not green")
    return {**observed, "rows": int(reference.get("rows") or 0)}


def remediation_lane(source_group: str, path: str) -> str:
    if source_group == "text_documents/parl_initiative_docs":
        return "initiative_document_source_recovery"
    if source_group == "text_documents/congreso_intervenciones":
        return "intervention_source_record_reconciliation"
    if source_group == "text_documents/programas_partidos":
        return "primary_party_manifest_recovery"
    if source_group in {"elections", "election_calendar"}:
        return "official_election_archive_manifest_recovery"
    if path.startswith("manual/senado_votaciones_ses/"):
        return "senate_session_capture_manifest_reconciliation"
    if source_group == "manual":
        return "manual_capture_sidecar_recovery"
    if source_group == "europarl_meps":
        return "europarl_source_manifest_recovery"
    return "source_manifest_recovery"


def priority_for(source_group: str) -> str:
    if source_group in {
        "elections",
        "election_calendar",
        "text_documents/congreso_intervenciones",
        "text_documents/parl_initiative_docs",
        "text_documents/programas_partidos",
    }:
        return "p0"
    if source_group == "samples":
        return "p2"
    return "p1"


def queue_id(path: str, sha256: str) -> str:
    return hashlib.sha256(f"{path}\x1f{sha256}".encode()).hexdigest()


def export_queue(
    *,
    repo_root: Path,
    file_manifest: Path,
    audit_report: Path,
    queue_out: Path,
    report_out: Path,
) -> dict[str, Any]:
    audit = read_json_object(audit_report)
    manifest_ref = validate_manifest_reference(
        file_manifest=file_manifest,
        audit=audit,
        repo_root=repo_root,
    )
    totals: Counter[str] = Counter()
    by_source_group: dict[str, Counter[str]] = defaultdict(Counter)
    by_lane: Counter[str] = Counter()
    queue_out.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with (
            file_manifest.open("r", encoding="utf-8") as source,
            tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                prefix=f".{queue_out.name}.",
                suffix=".partial",
                dir=queue_out.parent,
                delete=False,
            ) as temp_handle,
        ):
            temp_path = Path(temp_handle.name)
            for line_number, line in enumerate(source, start=1):
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise GapQueueError(
                        f"invalid provenance file manifest line {line_number}: {exc}"
                    ) from exc
                path = str(item.get("path") or "")
                sha256 = str(item.get("sha256") or "").lower()
                source_group = str(item.get("source_group") or "unknown")
                status = str(item.get("provenance_status") or "unknown")
                if (
                    not path
                    or PurePosixPath(path).is_absolute()
                    or ".." in PurePosixPath(path).parts
                    or len(sha256) != SHA256_RE_LENGTH
                    or any(character not in "0123456789abcdef" for character in sha256)
                ):
                    raise GapQueueError(
                        f"unsafe provenance row at line {line_number}: {path!r}"
                    )
                totals["files_scanned"] += 1
                needs_checksum_lineage = status not in VERIFIED_CHECKSUM_STATUSES
                needs_public_url = int(item.get("public_url_edges") or 0) == 0
                totals["checksum_lineage_gaps"] += int(needs_checksum_lineage)
                totals["public_url_gaps"] += int(needs_public_url)
                if not needs_checksum_lineage and not needs_public_url:
                    continue
                lane = remediation_lane(source_group, path)
                row = {
                    "queue_id": queue_id(path, sha256),
                    "status": "pending_provenance_recovery",
                    "priority": priority_for(source_group),
                    "remediation_lane": lane,
                    "path": path,
                    "source_group": source_group,
                    "extension": str(item.get("extension") or "unknown"),
                    "bytes": int(item.get("bytes") or 0),
                    "sha256": sha256,
                    "provenance_status": status,
                    "needs_checksum_lineage": needs_checksum_lineage,
                    "needs_public_url": needs_public_url,
                    "required_evidence": [
                        "exact_public_source_url",
                        "source_or_capture_manifest",
                        "matching_content_sha256",
                    ],
                    "guessed_source_url": False,
                    "official_real_file": True,
                    "public_domain_personal_information_retained": True,
                }
                temp_handle.write(
                    json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n"
                )
                totals["queue_rows"] += 1
                totals["queue_bytes"] += row["bytes"]
                by_source_group[source_group]["rows"] += 1
                by_source_group[source_group]["bytes"] += row["bytes"]
                by_source_group[source_group]["checksum_lineage_gaps"] += int(
                    needs_checksum_lineage
                )
                by_source_group[source_group]["public_url_gaps"] += int(
                    needs_public_url
                )
                by_lane[lane] += 1
            temp_handle.flush()
            os.fsync(temp_handle.fileno())
        os.replace(temp_path, queue_out)
    except Exception:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise

    audit_totals = audit.get("totals") or {}
    expected_files = int(audit_totals.get("files") or 0)
    expected_checksum_gaps = expected_files - int(
        audit_totals.get("verified_checksum_files") or 0
    )
    expected_public_url_gaps = expected_files - int(
        audit_totals.get("files_with_public_url") or 0
    )
    checks = {
        "input_manifest_matches_audit": True,
        "all_inventory_rows_scanned": totals["files_scanned"]
        == manifest_ref["rows"]
        == expected_files,
        "checksum_gap_count_matches_audit": totals["checksum_lineage_gaps"]
        == expected_checksum_gaps,
        "public_url_gap_count_matches_audit": totals["public_url_gaps"]
        == expected_public_url_gaps,
        "queue_rows_balance_gap_union": max(
            totals["checksum_lineage_gaps"],
            totals["public_url_gaps"],
        )
        <= totals["queue_rows"]
        <= totals["checksum_lineage_gaps"] + totals["public_url_gaps"],
        "guessed_source_urls_absent": True,
        "public_domain_personal_information_retained": True,
    }
    checks["integrity_passed"] = all(checks.values())
    report = {
        "schema_version": "document_provenance_gap_queue_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "ok" if checks["integrity_passed"] else "failed",
        "policy": {
            "official_real_files_only": True,
            "synthetic_or_mock_records_counted": False,
            "guessed_source_urls_forbidden": True,
            "public_domain_personal_information_retained": True,
        },
        "inputs": {
            "file_manifest": manifest_ref,
            "audit_report": {
                "path": display_path(audit_report, repo_root=repo_root),
                "bytes": audit_report.stat().st_size,
                "sha256": sha256_file(audit_report),
            },
        },
        "queue": {
            "path": display_path(queue_out, repo_root=repo_root),
            "rows": totals["queue_rows"],
            "empty": totals["queue_rows"] == 0,
            "bytes": queue_out.stat().st_size,
            "sha256": sha256_file(queue_out),
            "source_bytes_requiring_remediation": totals["queue_bytes"],
        },
        "totals": dict(sorted(totals.items())),
        "by_source_group": {
            key: dict(sorted(value.items()))
            for key, value in sorted(by_source_group.items())
        },
        "by_remediation_lane": dict(sorted(by_lane.items())),
        "checks": checks,
        "next_action": (
            "Process p0 lanes first; accept only exact source/capture manifests whose "
            "declared bytes and SHA-256 reconcile; then rerun the provenance audit and queue."
        ),
    }
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = export_queue(
            repo_root=REPO_ROOT,
            file_manifest=safe_repo_path(args.file_manifest, repo_root=REPO_ROOT),
            audit_report=safe_repo_path(args.audit_report, repo_root=REPO_ROOT),
            queue_out=safe_repo_path(args.queue_out, repo_root=REPO_ROOT),
            report_out=safe_repo_path(args.report_out, repo_root=REPO_ROOT),
        )
    except (GapQueueError, OSError, ValueError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2
    print(
        json.dumps(
            {
                "status": report["status"],
                "queue_rows": report["queue"]["rows"],
                "checksum_lineage_gaps": report["totals"]["checksum_lineage_gaps"],
                "public_url_gaps": report["totals"]["public_url_gaps"],
                "report": display_path(
                    safe_repo_path(args.report_out, repo_root=REPO_ROOT),
                    repo_root=REPO_ROOT,
                ),
            },
            sort_keys=True,
        )
    )
    return 1 if args.enforce and report["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
