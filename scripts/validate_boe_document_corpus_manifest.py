"""Independently validate partitioned real BOE document lineage."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = Path("etl/data/manifests/boe-document-corpus-lineage-manifest.json")
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "boe-document-corpus-lineage-validation-20260830.json"
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
BOE_REF_RE = re.compile(r"^BOE-[A-Z]-\d{4}-\d+$", flags=re.IGNORECASE)
SUMMARY_PATH_RE = re.compile(r"^/datosabiertos/api/boe/sumario/\d{8}$")


class ValidationError(RuntimeError):
    """Raised when a BOE lineage artifact violates its contract."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--full-raw-check", action="store_true")
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def repo_path(value: str | Path) -> Path:
    candidate = (REPO_ROOT / value).resolve()
    try:
        candidate.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise ValidationError(f"path escapes repository: {value}") from exc
    return candidate


def display_path(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
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


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValidationError(f"manifest missing: {display_path(path)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"manifest is invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValidationError("manifest root must be an object")
    return payload


def validate_policy(payload: dict[str, Any]) -> None:
    policy = payload.get("policy") or {}
    expected = {
        "official_boe_https_only": True,
        "checksum_and_byte_verification_required": True,
        "official_public_domain_personal_information_retained": True,
        "synthetic_or_mock_records_counted": False,
        "remote_mutation_performed": False,
    }
    if policy != expected:
        raise ValidationError("manifest policy drifted")


def validate_document_url(source_url: str) -> str:
    parsed = urlparse(source_url)
    identifiers = parse_qs(parsed.query).get("id") or []
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").lower() != "www.boe.es"
        or parsed.path != "/diario_boe/xml.php"
        or len(identifiers) != 1
        or not BOE_REF_RE.fullmatch(identifiers[0])
    ):
        raise ValidationError(f"invalid official BOE document URL: {source_url}")
    return identifiers[0].upper()


def validate_summary_url(source_url: str) -> None:
    parsed = urlparse(source_url)
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").lower() != "www.boe.es"
        or not SUMMARY_PATH_RE.fullmatch(parsed.path)
        or parsed.query
        or parsed.fragment
    ):
        raise ValidationError(f"invalid official BOE summary URL: {source_url}")


def require_capture(
    value: Any,
    *,
    expected_prefix: str,
    label: str,
    full_raw_check: bool,
) -> tuple[Path, int, str]:
    if not isinstance(value, dict):
        raise ValidationError(f"{label} capture must be an object")
    relative_path = str(value.get("path") or "")
    byte_count = value.get("bytes")
    checksum = str(value.get("sha256") or "").lower()
    if (
        not relative_path.startswith(expected_prefix)
        or not isinstance(byte_count, int)
        or byte_count <= 0
        or not SHA256_RE.fullmatch(checksum)
    ):
        raise ValidationError(f"{label} capture contract drifted")
    path = repo_path(relative_path)
    if not path.is_file() or path.stat().st_size != byte_count:
        raise ValidationError(f"{label} capture file drifted: {relative_path}")
    if full_raw_check and sha256_file(path) != checksum:
        raise ValidationError(f"{label} capture checksum drifted: {relative_path}")
    return path, byte_count, checksum


def validate_row(
    item: Any,
    *,
    full_raw_check: bool,
    work: sqlite3.Connection,
) -> tuple[str, int, str]:
    if not isinstance(item, dict):
        raise ValidationError("lineage row must be an object")
    source_url = str(item.get("source_url") or "")
    boe_ref = validate_document_url(source_url)
    boe_record = item.get("boe_record")
    if (
        item.get("schema_version") != "boe_document_corpus_lineage_v2"
        or item.get("capture_status") != "checksum_capture_present"
        or item.get("source_id") != "boe_document_xml"
        or item.get("official_public_domain_personal_information_retained") is not True
        or item.get("synthetic_or_mock_records_counted") is not False
        or item.get("remote_mutation_performed") is not False
        or not isinstance(boe_record, dict)
        or str(boe_record.get("boe_ref") or "").upper() != boe_ref
    ):
        raise ValidationError(f"BOE lineage row contract drifted: {source_url}")
    _, document_bytes, document_sha256 = require_capture(
        item.get("capture"),
        expected_prefix="etl/data/raw/text_documents/boe_document_xml/",
        label="document",
        full_raw_check=full_raw_check,
    )
    summary = item.get("source_summary")
    if not isinstance(summary, dict):
        raise ValidationError(f"BOE summary relation missing: {source_url}")
    summary_url = str(summary.get("source_url") or "")
    validate_summary_url(summary_url)
    summary_path_value = str(summary.get("path") or "")
    summary_bytes = summary.get("bytes")
    summary_sha256 = str(summary.get("sha256") or "").lower()
    existing = work.execute(
        "SELECT path, bytes, sha256 FROM summaries WHERE source_url = ?",
        (summary_url,),
    ).fetchone()
    if existing is None:
        _, checked_summary_bytes, checked_summary_sha256 = require_capture(
            summary,
            expected_prefix="etl/data/raw/text_documents/boe_daily_summaries/",
            label="summary",
            full_raw_check=full_raw_check,
        )
        work.execute(
            "INSERT INTO summaries(source_url, path, bytes, sha256) VALUES (?, ?, ?, ?)",
            (
                summary_url,
                summary_path_value,
                checked_summary_bytes,
                checked_summary_sha256,
            ),
        )
    elif tuple(existing) != (summary_path_value, summary_bytes, summary_sha256):
        raise ValidationError(f"inconsistent BOE summary capture: {summary_url}")
    work.execute(
        "INSERT OR IGNORE INTO content_hashes(sha256) VALUES (?)",
        (document_sha256,),
    )
    return source_url, document_bytes, summary_url


def validate_manifest(
    manifest_path: Path,
    *,
    full_raw_check: bool,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    if (
        manifest.get("schema_version") != "boe_document_corpus_lineage_manifest_v1"
        or manifest.get("layout") != "partitioned_jsonl_gzip_v1"
    ):
        raise ValidationError("unsupported BOE partitioned manifest schema")
    validate_policy(manifest)
    totals = manifest.get("totals") or {}
    bounds = manifest.get("bounds") or {}
    max_rows = int(bounds.get("max_rows") or 0)
    max_uncompressed_bytes = int(bounds.get("max_uncompressed_bytes") or 0)
    if max_rows < 1 or max_uncompressed_bytes < 1:
        raise ValidationError("manifest shard bounds are invalid")
    partitions = manifest.get("partitions")
    if not isinstance(partitions, list) or not partitions:
        raise ValidationError("manifest has no partitions")
    shard_root = repo_path(str(manifest.get("shard_root") or ""))
    if not shard_root.is_dir():
        raise ValidationError("manifest shard root is missing")
    logical_digest = hashlib.sha256()
    rows = 0
    document_bytes = 0
    compressed_bytes = 0
    uncompressed_bytes = 0
    previous_source_url = ""
    seen_paths: set[str] = set()
    with tempfile.TemporaryDirectory(prefix="boe-lineage-validation-") as temp_dir:
        database_path = Path(temp_dir) / "validation.sqlite"
        work = sqlite3.connect(database_path)
        work.row_factory = sqlite3.Row
        work.executescript(
            """
            PRAGMA journal_mode=OFF;
            PRAGMA synchronous=OFF;
            CREATE TABLE content_hashes (sha256 TEXT PRIMARY KEY) WITHOUT ROWID;
            CREATE TABLE summaries (
              source_url TEXT PRIMARY KEY,
              path TEXT NOT NULL,
              bytes INTEGER NOT NULL,
              sha256 TEXT NOT NULL
            ) WITHOUT ROWID;
            """
        )
        try:
            for partition_index, partition in enumerate(partitions):
                if not isinstance(partition, dict):
                    raise ValidationError("partition must be an object")
                relative_path = str(partition.get("path") or "")
                if relative_path in seen_paths:
                    raise ValidationError(f"duplicate partition path: {relative_path}")
                seen_paths.add(relative_path)
                shard_path = repo_path(relative_path)
                try:
                    shard_path.relative_to(shard_root)
                except ValueError as exc:
                    raise ValidationError(
                        f"partition escapes declared shard root: {relative_path}"
                    ) from exc
                expected_bytes = int(partition.get("bytes") or -1)
                expected_sha256 = str(partition.get("sha256") or "").lower()
                if (
                    not shard_path.is_file()
                    or shard_path.stat().st_size != expected_bytes
                    or not SHA256_RE.fullmatch(expected_sha256)
                    or sha256_file(shard_path) != expected_sha256
                ):
                    raise ValidationError(f"partition drifted: {relative_path}")
                shard_digest = hashlib.sha256()
                shard_rows = 0
                shard_uncompressed_bytes = 0
                first_source_url = ""
                last_source_url = ""
                try:
                    with gzip.open(shard_path, "rb") as handle:
                        for line_number, line in enumerate(handle, start=1):
                            if not line.strip():
                                raise ValidationError(
                                    f"blank partition row: {relative_path}:{line_number}"
                                )
                            shard_digest.update(line)
                            logical_digest.update(line)
                            shard_uncompressed_bytes += len(line)
                            try:
                                item = json.loads(line)
                            except json.JSONDecodeError as exc:
                                raise ValidationError(
                                    f"invalid partition JSON: {relative_path}:{line_number}"
                                ) from exc
                            source_url, row_bytes, _ = validate_row(
                                item,
                                full_raw_check=full_raw_check,
                                work=work,
                            )
                            if (
                                previous_source_url
                                and source_url <= previous_source_url
                            ):
                                raise ValidationError(
                                    "BOE lineage source URLs are not strictly ordered"
                                )
                            previous_source_url = source_url
                            if not first_source_url:
                                first_source_url = source_url
                            last_source_url = source_url
                            shard_rows += 1
                            rows += 1
                            document_bytes += row_bytes
                except (gzip.BadGzipFile, EOFError, OSError) as exc:
                    raise ValidationError(
                        f"cannot read partition {relative_path}: {exc}"
                    ) from exc
                if (
                    shard_rows != int(partition.get("rows") or -1)
                    or shard_rows > max_rows
                    or shard_uncompressed_bytes
                    != int(partition.get("uncompressed_bytes") or -1)
                    or shard_uncompressed_bytes > max_uncompressed_bytes
                    or shard_digest.hexdigest()
                    != str(partition.get("uncompressed_sha256") or "").lower()
                    or first_source_url != partition.get("first_source_url")
                    or last_source_url != partition.get("last_source_url")
                ):
                    raise ValidationError(
                        f"partition totals drifted at index {partition_index}"
                    )
                compressed_bytes += expected_bytes
                uncompressed_bytes += shard_uncompressed_bytes
            distinct_content_objects = int(
                work.execute("SELECT COUNT(*) FROM content_hashes").fetchone()[0]
            )
            distinct_summary_captures = int(
                work.execute("SELECT COUNT(*) FROM summaries").fetchone()[0]
            )
        finally:
            work.close()
    checks = {
        "manifest_schema_supported": True,
        "policy_retains_official_public_information": True,
        "no_synthetic_or_mock_rows": True,
        "partition_paths_unique_and_bounded": len(seen_paths) == len(partitions),
        "partition_checksums_and_rows_valid": True,
        "source_urls_strictly_ordered": True,
        "raw_captures_checksum_verified": full_raw_check,
        "totals_reconcile": (
            rows == int(totals.get("rows") or -1)
            and document_bytes == int(totals.get("document_bytes") or -1)
            and distinct_content_objects
            == int(totals.get("distinct_content_objects") or -1)
            and distinct_summary_captures
            == int(totals.get("distinct_summary_captures") or -1)
            and distinct_summary_captures
            <= int(totals.get("available_summary_captures") or -1)
            and len(partitions) == int(totals.get("shard_files") or -1)
            and compressed_bytes == int(totals.get("compressed_lineage_bytes") or -1)
            and uncompressed_bytes
            == int(totals.get("uncompressed_lineage_bytes") or -1)
            and logical_digest.hexdigest()
            == str(manifest.get("logical_sha256") or "").lower()
        ),
    }
    return {
        "schema_version": "boe_document_corpus_lineage_validation_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "ok" if all(checks.values()) else "failed",
        "input": {
            "path": display_path(manifest_path),
            "bytes": manifest_path.stat().st_size,
            "sha256": sha256_file(manifest_path),
        },
        "mode": {"full_raw_check": full_raw_check},
        "totals": {
            "rows": rows,
            "document_bytes": document_bytes,
            "distinct_content_objects": distinct_content_objects,
            "distinct_summary_captures": distinct_summary_captures,
            "shard_files": len(partitions),
            "compressed_lineage_bytes": compressed_bytes,
            "uncompressed_lineage_bytes": uncompressed_bytes,
            "logical_sha256": logical_digest.hexdigest(),
        },
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        manifest_path = repo_path(args.manifest)
        report = validate_manifest(
            manifest_path,
            full_raw_check=bool(args.full_raw_check),
        )
        atomic_write_json(repo_path(args.report_out), report)
    except (ValidationError, OSError, sqlite3.DatabaseError, ValueError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    if args.enforce and not all(report["checks"].values()):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
