#!/usr/bin/env python3
"""Bind preserved Senate diaries to byte-identical official publication URLs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

if __package__:
    from scripts.recover_captured_document_links import download_digest
else:
    from recover_captured_document_links import download_digest

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY_ROOT = Path("etl/data/raw")
DEFAULT_INVENTORY_MANIFEST = Path(
    "etl/data/manifests/real-document-format-inventory.jsonl"
)
DEFAULT_GAP_QUEUE = Path("etl/data/manifests/document-provenance-gap-queue.jsonl")
DEFAULT_SEEDS = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "official-document-identifier-recovery-seeds.json"
)
DEFAULT_MANIFEST = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "official-document-identifier-lineage.jsonl"
)
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "official-document-identifier-lineage.json"
)
DEFAULT_USER_AGENT = "vota-con-la-chola-accountability-etl/1.0"
TARGET_SOURCE_GROUP = "text_documents/parl_initiative_docs"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
INTERNAL_IDENTIFIER_RE = re.compile(rb"DS_[PC]_\d+_\d+")
OFFICIAL_DIARY_URL_RE = re.compile(
    r"^https://www\.congreso\.es/public_oficiales/"
    r"L(?P<legislature>\d+)/SEN/DS/(?P<section>PL|CO)/"
    r"(?P<identifier>DS_(?P<kind>P|C)_(?P=legislature)_\d+)\.PDF$",
    re.IGNORECASE,
)


class OfficialIdentifierRecoveryError(RuntimeError):
    """Raised when the exact official-document evidence contract is violated."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory-root", default=str(DEFAULT_INVENTORY_ROOT))
    parser.add_argument(
        "--inventory-manifest",
        default=str(DEFAULT_INVENTORY_MANIFEST),
    )
    parser.add_argument("--gap-queue", default=str(DEFAULT_GAP_QUEUE))
    parser.add_argument("--seeds", default=str(DEFAULT_SEEDS))
    parser.add_argument("--manifest-out", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--max-document-bytes", type=int, default=128 * 1024 * 1024)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def safe_repo_path(value: str | Path) -> Path:
    candidate = (REPO_ROOT / value).resolve()
    try:
        candidate.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise OfficialIdentifierRecoveryError(
            f"path escapes repository: {value}"
        ) from exc
    return candidate


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def official_diary_url_identifier(source_url: str) -> str | None:
    """Return the identifier only for the exact official Senate diary URL shape."""
    match = OFFICIAL_DIARY_URL_RE.fullmatch(source_url)
    if match is None:
        return None
    section = match.group("section").upper()
    kind = match.group("kind").upper()
    if (section, kind) not in {("PL", "P"), ("CO", "C")}:
        return None
    return match.group("identifier").upper()


def load_inventory(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise OfficialIdentifierRecoveryError(
                    f"invalid inventory JSON at line {line_number}: {exc}"
                ) from exc
            document_path = str(item.get("path") or "")
            if (
                not document_path
                or Path(document_path).is_absolute()
                or ".." in PurePosixPath(document_path).parts
            ):
                raise OfficialIdentifierRecoveryError(
                    f"invalid inventory path at line {line_number}"
                )
            rows[document_path] = item
    if not rows:
        raise OfficialIdentifierRecoveryError("real document inventory is empty")
    return rows


def load_current_gap_keys(path: Path) -> set[tuple[str, str]]:
    if not path.is_file():
        return set()
    keys: set[tuple[str, str]] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise OfficialIdentifierRecoveryError(
                    f"invalid gap queue JSON at line {line_number}: {exc}"
                ) from exc
            if item.get("source_group") == TARGET_SOURCE_GROUP:
                keys.add(
                    (
                        str(item.get("path") or ""),
                        str(item.get("sha256") or "").lower(),
                    )
                )
    return keys


def load_seeds(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    policy = payload.get("policy")
    documents = payload.get("documents")
    if (
        payload.get("schema_version")
        != "official_document_identifier_recovery_seeds_v1"
        or not isinstance(policy, dict)
        or policy.get(
            "accept_only_after_live_official_get_matches_capture_sha256_and_bytes"
        )
        is not True
        or policy.get(
            "candidate_url_pattern_is_not_provenance_without_exact_download_match"
        )
        is not True
        or policy.get("official_real_records_only") is not True
        or policy.get("synthetic_or_mock_records_counted") is not False
        or policy.get("public_domain_personal_information_retained") is not True
        or not isinstance(documents, list)
        or not documents
    ):
        raise OfficialIdentifierRecoveryError("invalid recovery seed contract")
    rows: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    seen_urls: set[str] = set()
    for index, item in enumerate(documents, start=1):
        if not isinstance(item, dict):
            raise OfficialIdentifierRecoveryError(f"invalid seed row {index}")
        document_path = str(item.get("path") or "")
        sha256 = str(item.get("sha256") or "").lower()
        declared_bytes = item.get("bytes")
        source_url = str(item.get("source_url") or "")
        expected_identifier = str(item.get("expected_identifier") or "").upper()
        if (
            not document_path
            or Path(document_path).is_absolute()
            or ".." in PurePosixPath(document_path).parts
            or not SHA256_RE.fullmatch(sha256)
            or PurePosixPath(document_path).stem != sha256
            or not isinstance(declared_bytes, int)
            or declared_bytes <= 0
            or official_diary_url_identifier(source_url) != expected_identifier
            or document_path in seen_paths
            or source_url in seen_urls
        ):
            raise OfficialIdentifierRecoveryError(f"invalid seed row {index}")
        seen_paths.add(document_path)
        seen_urls.add(source_url)
        rows.append(
            {
                "path": document_path,
                "sha256": sha256,
                "bytes": declared_bytes,
                "source_url": source_url,
                "expected_identifier": expected_identifier,
            }
        )
    return sorted(rows, key=lambda item: item["path"])


def verify_local_captures(
    seeds: list[dict[str, Any]],
    *,
    inventory: dict[str, dict[str, Any]],
    inventory_root: Path,
) -> list[dict[str, Any]]:
    verified: list[dict[str, Any]] = []
    for seed in seeds:
        inventory_row = inventory.get(seed["path"])
        capture_path = (inventory_root / seed["path"]).resolve()
        try:
            capture_path.relative_to(inventory_root.resolve())
        except ValueError as exc:
            raise OfficialIdentifierRecoveryError(
                f"capture escapes inventory: {seed['path']}"
            ) from exc
        if (
            inventory_row is None
            or inventory_row.get("real_data_status") != "eligible_real_capture"
            or inventory_row.get("source_group") != TARGET_SOURCE_GROUP
            or str(inventory_row.get("sha256") or "").lower() != seed["sha256"]
            or inventory_row.get("bytes") != seed["bytes"]
            or not capture_path.is_file()
            or capture_path.stat().st_size != seed["bytes"]
            or sha256_file(capture_path) != seed["sha256"]
        ):
            raise OfficialIdentifierRecoveryError(
                f"seed does not match real inventory bytes: {seed['path']}"
            )
        with capture_path.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                raise OfficialIdentifierRecoveryError(
                    f"seed capture is not a PDF: {seed['path']}"
                )
            handle.seek(0)
            internal_identifiers = sorted(
                {
                    value.decode("ascii").upper()
                    for value in INTERNAL_IDENTIFIER_RE.findall(handle.read())
                }
            )
        if (
            internal_identifiers
            and seed["expected_identifier"] not in internal_identifiers
        ):
            raise OfficialIdentifierRecoveryError(
                "official identifier conflicts with preserved PDF bytes: "
                f"{seed['path']}"
            )
        verified.append({**seed, "internal_identifiers": internal_identifiers})
    return verified


def recover(
    *,
    inventory_root: Path,
    inventory_manifest_path: Path,
    gap_queue_path: Path,
    seed_path: Path,
    manifest_out: Path,
    report_out: Path,
    workers: int,
    timeout: int,
    attempts: int,
    max_document_bytes: int,
    user_agent: str,
) -> dict[str, Any]:
    inventory = load_inventory(inventory_manifest_path)
    seeds = load_seeds(seed_path)
    local_captures = verify_local_captures(
        seeds,
        inventory=inventory,
        inventory_root=inventory_root,
    )
    current_gap_keys = load_current_gap_keys(gap_queue_path)
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(
                download_digest,
                seed["source_url"],
                timeout=max(1, timeout),
                attempts=max(1, attempts),
                max_document_bytes=max(1, max_document_bytes),
                user_agent=user_agent,
            ): seed
            for seed in local_captures
        }
        for future in as_completed(futures):
            seed = futures[future]
            result = future.result()
            result["capture_path"] = seed["path"]
            result["expected_bytes"] = seed["bytes"]
            result["expected_sha256"] = seed["sha256"]
            result["expected_identifier"] = seed["expected_identifier"]
            result["internal_identifiers"] = seed["internal_identifiers"]
            content_type = str(result.get("content_type") or "").partition(";")[0]
            result["exact_capture_match"] = (
                result.get("status") == "downloaded"
                and result.get("http_status") == 200
                and content_type.strip().lower() == "application/pdf"
                and result.get("downloaded_bytes") == seed["bytes"]
                and result.get("downloaded_sha256") == seed["sha256"]
                and official_diary_url_identifier(str(result.get("final_url") or ""))
                == seed["expected_identifier"]
            )
            results.append(result)
    results.sort(key=lambda item: item["capture_path"])

    verified_at = datetime.now(UTC).isoformat()
    exact_results = [item for item in results if item["exact_capture_match"]]
    all_exact = len(exact_results) == len(local_captures)
    manifest_rows: list[dict[str, Any]] = []
    if all_exact:
        for seed, result in zip(local_captures, exact_results, strict=True):
            if seed["path"] != result["capture_path"]:
                raise OfficialIdentifierRecoveryError("result ordering mismatch")
            internal_identifiers = seed["internal_identifiers"]
            manifest_rows.append(
                {
                    "schema_version": "official_document_identifier_lineage_v1",
                    "capture_status": "checksum_capture_present",
                    "capture": {
                        "path": f"etl/data/raw/{seed['path']}",
                        "bytes": seed["bytes"],
                        "sha256": seed["sha256"],
                    },
                    "source_id": "parl_initiative_docs",
                    "source_url": seed["source_url"],
                    "identifier_evidence": {
                        "expected_identifier": seed["expected_identifier"],
                        "internal_identifiers": internal_identifiers,
                        "status": (
                            "embedded_identifier_and_exact_download_match"
                            if internal_identifiers
                            else "exact_download_match_without_embedded_identifier"
                        ),
                    },
                    "retrieval_verification": {
                        "method": "official_http_get_sha256_match",
                        "verified_at": verified_at,
                        "requested_url": seed["source_url"],
                        "final_url": result["final_url"],
                        "http_status": result["http_status"],
                        "content_type": result["content_type"],
                        "downloaded_bytes": result["downloaded_bytes"],
                        "downloaded_sha256": result["downloaded_sha256"],
                    },
                    "candidate_acceptance": "accepted_only_after_live_exact_byte_match",
                    "guessed_source_urls_accepted": False,
                    "public_domain_personal_information_retained": True,
                    "synthetic_or_mock_records_counted": False,
                    "remote_mutation_performed": False,
                }
            )
        manifest_out.parent.mkdir(parents=True, exist_ok=True)
        manifest_out.write_text(
            "".join(
                json.dumps(item, ensure_ascii=True, sort_keys=True) + "\n"
                for item in manifest_rows
            ),
            encoding="utf-8",
        )

    statuses = Counter(str(item.get("status") or "unknown") for item in results)
    report: dict[str, Any] = {
        "schema_version": "official_document_identifier_lineage_report_v1",
        "generated_at": verified_at,
        "status": "ok" if all_exact else "failed",
        "policy": {
            "official_real_records_only": True,
            "candidate_url_pattern_is_not_provenance_without_exact_download_match": True,
            "downloaded_bytes_must_match_existing_capture_sha256_and_size": True,
            "guessed_source_urls_accepted": False,
            "synthetic_or_mock_records_counted": False,
            "public_domain_personal_information_retained": True,
            "remote_mutation_performed": False,
        },
        "inputs": {
            "inventory": {
                "path": display_path(inventory_manifest_path),
                "bytes": inventory_manifest_path.stat().st_size,
                "sha256": sha256_file(inventory_manifest_path),
            },
            "gap_queue": {
                "path": display_path(gap_queue_path),
                "bytes": gap_queue_path.stat().st_size,
                "sha256": sha256_file(gap_queue_path),
            },
            "seeds": {
                "path": display_path(seed_path),
                "bytes": seed_path.stat().st_size,
                "sha256": sha256_file(seed_path),
                "rows": len(seeds),
            },
        },
        "execution": {
            "workers": max(1, workers),
            "timeout_seconds": max(1, timeout),
            "attempts": max(1, attempts),
            "max_document_bytes": max(1, max_document_bytes),
            "http_method": "GET",
        },
        "totals": {
            "seed_documents": len(seeds),
            "real_inventory_captures_verified": len(local_captures),
            "captures_in_current_gap_queue": sum(
                (seed["path"], seed["sha256"]) in current_gap_keys for seed in seeds
            ),
            "downloads_succeeded": statuses["downloaded"],
            "downloads_failed": statuses["failed"],
            "exact_official_byte_matches": len(exact_results),
            "manifest_relations": len(manifest_rows),
            "recovered_bytes": sum(
                int(item["expected_bytes"]) for item in exact_results
            ),
            "captures_with_embedded_identifier": sum(
                bool(item["internal_identifiers"]) for item in local_captures
            ),
            "captures_without_embedded_identifier": sum(
                not item["internal_identifiers"] for item in local_captures
            ),
        },
        "checks": {
            "all_seed_captures_are_verified_real_inventory_files": len(local_captures)
            == len(seeds),
            "all_official_downloads_match_capture_sha256_and_bytes": all_exact,
            "manifest_contains_every_seed_exactly_once": len(manifest_rows)
            == len(seeds),
            "no_guessed_source_url_accepted": all_exact,
            "public_domain_personal_information_retained": True,
            "no_remote_mutation_performed": True,
        },
        "manifest": {
            "path": display_path(manifest_out),
            "written": all_exact,
            "bytes": manifest_out.stat().st_size if all_exact else None,
            "sha256": sha256_file(manifest_out) if all_exact else None,
            "rows": len(manifest_rows),
        },
        "download_results": results,
        "next_action": (
            "Load the exact official-identifier lineage into the provenance audit "
            "and regenerate the residual gap queue."
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
        report = recover(
            inventory_root=safe_repo_path(args.inventory_root),
            inventory_manifest_path=safe_repo_path(args.inventory_manifest),
            gap_queue_path=safe_repo_path(args.gap_queue),
            seed_path=safe_repo_path(args.seeds),
            manifest_out=safe_repo_path(args.manifest_out),
            report_out=safe_repo_path(args.report_out),
            workers=args.workers,
            timeout=args.timeout,
            attempts=args.attempts,
            max_document_bytes=args.max_document_bytes,
            user_agent=args.user_agent,
        )
    except (
        OfficialIdentifierRecoveryError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2
    print(
        json.dumps(
            {
                "status": report["status"],
                **report["totals"],
                "report": display_path(safe_repo_path(args.report_out)),
            },
            sort_keys=True,
        )
    )
    if args.enforce and not all(report["checks"].values()):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
