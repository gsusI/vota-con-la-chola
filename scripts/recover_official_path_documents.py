#!/usr/bin/env python3
"""Recover exact Senate session lineage by live path-to-URL byte matching."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY_ROOT = Path("etl/data/raw")
DEFAULT_INVENTORY_MANIFEST = Path(
    "etl/data/manifests/real-document-format-inventory.jsonl"
)
DEFAULT_GAP_QUEUE = Path("etl/data/manifests/document-provenance-gap-queue.jsonl")
DEFAULT_MANIFEST = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "official-path-document-lineage.jsonl"
)
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "official-path-document-lineage.json"
)
DEFAULT_USER_AGENT = "vota-con-la-chola-accountability-etl/1.0"
TARGET_SOURCE_GROUP = "manual"
CAPTURE_PATH_RE = re.compile(
    r"^manual/senado_votaciones_ses/"
    r"legis(?P<legislature>\d+)/(?P<filename>ses_[^/]+\.xml)$"
)
SOURCE_URL_RE = re.compile(
    r"^https://www\.senado\.es/legis(?P<legislature>\d+)/"
    r"votaciones/(?P<filename>ses_[^/]+\.xml)$"
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RETRYABLE_HTTP_CODES = {408, 429, 500, 502, 503, 504}


class OfficialPathRecoveryError(RuntimeError):
    """Raised when official-path recovery violates its evidence contract."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory-root", default=str(DEFAULT_INVENTORY_ROOT))
    parser.add_argument(
        "--inventory-manifest",
        default=str(DEFAULT_INVENTORY_MANIFEST),
    )
    parser.add_argument("--gap-queue", default=str(DEFAULT_GAP_QUEUE))
    parser.add_argument("--manifest-out", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--max-document-bytes", type=int, default=64 * 1024 * 1024)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def safe_repo_path(value: str | Path) -> Path:
    candidate = (REPO_ROOT / value).resolve()
    try:
        candidate.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise OfficialPathRecoveryError(f"path escapes repository: {value}") from exc
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


def senate_session_source_url(capture_path: str) -> str | None:
    match = CAPTURE_PATH_RE.fullmatch(capture_path)
    if match is None:
        return None
    return (
        f"https://www.senado.es/legis{match.group('legislature')}/"
        f"votaciones/{match.group('filename')}"
    )


def source_url_capture_path(source_url: str) -> str | None:
    match = SOURCE_URL_RE.fullmatch(source_url)
    if match is None:
        return None
    return (
        "manual/senado_votaciones_ses/"
        f"legis{match.group('legislature')}/{match.group('filename')}"
    )


def load_inventory(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise OfficialPathRecoveryError(
                    f"invalid inventory JSON at line {line_number}: {exc}"
                ) from exc
            item_path = str(item.get("path") or "")
            if (
                not item_path
                or Path(item_path).is_absolute()
                or ".." in PurePosixPath(item_path).parts
            ):
                raise OfficialPathRecoveryError(
                    f"invalid inventory path at line {line_number}"
                )
            rows[item_path] = item
    return rows


def load_gap_targets(
    path: Path,
    *,
    inventory: dict[str, dict[str, Any]],
    inventory_root: Path,
) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise OfficialPathRecoveryError(
                    f"invalid gap queue JSON at line {line_number}: {exc}"
                ) from exc
            capture_path = str(item.get("path") or "")
            source_url = senate_session_source_url(capture_path)
            if item.get("source_group") != TARGET_SOURCE_GROUP or source_url is None:
                continue
            sha256 = str(item.get("sha256") or "").lower()
            declared_bytes = item.get("bytes")
            inventory_row = inventory.get(capture_path)
            local_path = (inventory_root / capture_path).resolve()
            try:
                local_path.relative_to(inventory_root.resolve())
            except ValueError as exc:
                raise OfficialPathRecoveryError(
                    f"gap capture escapes inventory at line {line_number}"
                ) from exc
            if (
                item.get("official_real_file") is not True
                or item.get("guessed_source_url") is not False
                or item.get("public_domain_personal_information_retained") is not True
                or not SHA256_RE.fullmatch(sha256)
                or not isinstance(declared_bytes, int)
                or declared_bytes <= 0
                or inventory_row is None
                or inventory_row.get("real_data_status") != "eligible_real_capture"
                or str(inventory_row.get("sha256") or "").lower() != sha256
                or inventory_row.get("bytes") != declared_bytes
                or not local_path.is_file()
                or local_path.stat().st_size != declared_bytes
                or sha256_file(local_path) != sha256
            ):
                raise OfficialPathRecoveryError(
                    f"invalid real Senate session gap at line {line_number}"
                )
            with local_path.open("rb") as capture_handle:
                if not capture_handle.read(256).lstrip().startswith(b"<?xml"):
                    raise OfficialPathRecoveryError(
                        f"Senate session capture is not XML: {capture_path}"
                    )
            targets.append(
                {
                    "path": capture_path,
                    "sha256": sha256,
                    "bytes": declared_bytes,
                    "source_url": source_url,
                }
            )
    return sorted(targets, key=lambda item: item["path"])


def load_existing_manifest(
    path: Path,
    *,
    inventory: dict[str, dict[str, Any]],
    inventory_root: Path,
) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise OfficialPathRecoveryError(
                    f"invalid existing manifest JSON at line {line_number}: {exc}"
                ) from exc
            capture = item.get("capture")
            if (
                item.get("schema_version") != "official_path_document_lineage_v1"
                or item.get("capture_status") != "checksum_capture_present"
                or item.get("candidate_acceptance")
                != "accepted_only_after_live_exact_byte_match"
                or item.get("guessed_source_urls_accepted") is not False
                or item.get("synthetic_or_mock_records_counted") is not False
                or item.get("public_domain_personal_information_retained") is not True
                or item.get("remote_mutation_performed") is not False
                or not isinstance(capture, dict)
            ):
                raise OfficialPathRecoveryError(
                    f"invalid existing manifest contract at line {line_number}"
                )
            capture_path = str(capture.get("path") or "").removeprefix("etl/data/raw/")
            source_url = str(item.get("source_url") or "")
            sha256 = str(capture.get("sha256") or "").lower()
            declared_bytes = capture.get("bytes")
            inventory_row = inventory.get(capture_path)
            local_path = inventory_root / capture_path
            if (
                source_url_capture_path(source_url) != capture_path
                or not SHA256_RE.fullmatch(sha256)
                or not isinstance(declared_bytes, int)
                or inventory_row is None
                or inventory_row.get("sha256") != sha256
                or inventory_row.get("bytes") != declared_bytes
                or not local_path.is_file()
                or sha256_file(local_path) != sha256
            ):
                raise OfficialPathRecoveryError(
                    f"existing manifest evidence mismatch at line {line_number}"
                )
            rows.append(item)
    return rows


def download_xml_digest(
    source_url: str,
    *,
    timeout: int,
    attempts: int,
    max_document_bytes: int,
    user_agent: str,
) -> dict[str, Any]:
    last_error = "unknown error"
    attempts_used = 0
    for attempt in range(1, max(1, attempts) + 1):
        attempts_used = attempt
        try:
            request = urllib.request.Request(
                source_url,
                headers={
                    "User-Agent": user_agent,
                    "Accept": "application/xml,text/xml,*/*;q=0.5",
                },
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = int(getattr(response, "status", 200))
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > max_document_bytes:
                    raise OfficialPathRecoveryError(
                        f"content length exceeds limit: {content_length}"
                    )
                digest = hashlib.sha256()
                downloaded_bytes = 0
                first_bytes = b""
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    if not first_bytes:
                        first_bytes = chunk[:256]
                    downloaded_bytes += len(chunk)
                    if downloaded_bytes > max_document_bytes:
                        raise OfficialPathRecoveryError(
                            f"download exceeds limit: {downloaded_bytes}"
                        )
                    digest.update(chunk)
                final_url = response.geturl()
                if source_url_capture_path(final_url) is None:
                    raise OfficialPathRecoveryError(
                        f"redirect left exact official Senate path: {final_url}"
                    )
                if not first_bytes.lstrip().startswith(b"<?xml"):
                    raise OfficialPathRecoveryError("response is not an XML payload")
                return {
                    "source_url": source_url,
                    "status": "downloaded",
                    "attempts": attempt,
                    "http_status": status,
                    "content_type": response.headers.get("Content-Type"),
                    "final_url": final_url,
                    "downloaded_bytes": downloaded_bytes,
                    "downloaded_sha256": digest.hexdigest(),
                }
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}: {exc.reason}"
            if exc.code not in RETRYABLE_HTTP_CODES or attempt >= attempts:
                break
        except (OfficialPathRecoveryError, OSError, TimeoutError, ValueError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt >= attempts:
                break
        time.sleep(min(8.0, float(2 ** (attempt - 1))))
    return {
        "source_url": source_url,
        "status": "failed",
        "attempts": attempts_used,
        "error": last_error,
    }


def recover(
    *,
    inventory_root: Path,
    inventory_manifest_path: Path,
    gap_queue_path: Path,
    manifest_out: Path,
    report_out: Path,
    workers: int,
    timeout: int,
    attempts: int,
    max_document_bytes: int,
    user_agent: str,
) -> dict[str, Any]:
    inventory = load_inventory(inventory_manifest_path)
    existing_rows = load_existing_manifest(
        manifest_out,
        inventory=inventory,
        inventory_root=inventory_root,
    )
    existing_paths = {
        str(item["capture"]["path"]).removeprefix("etl/data/raw/")
        for item in existing_rows
    }
    targets = [
        item
        for item in load_gap_targets(
            gap_queue_path,
            inventory=inventory,
            inventory_root=inventory_root,
        )
        if item["path"] not in existing_paths
    ]
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(
                download_xml_digest,
                target["source_url"],
                timeout=max(1, timeout),
                attempts=max(1, attempts),
                max_document_bytes=max(1, max_document_bytes),
                user_agent=user_agent,
            ): target
            for target in targets
        }
        for future in as_completed(futures):
            target = futures[future]
            result = future.result()
            result.update(
                {
                    "capture_path": target["path"],
                    "expected_bytes": target["bytes"],
                    "expected_sha256": target["sha256"],
                }
            )
            content_type = str(result.get("content_type") or "").partition(";")[0]
            result["exact_capture_match"] = (
                result.get("status") == "downloaded"
                and result.get("http_status") == 200
                and content_type.strip().lower()
                in {"application/xml", "text/xml", "application/octet-stream"}
                and result.get("downloaded_bytes") == target["bytes"]
                and result.get("downloaded_sha256") == target["sha256"]
                and result.get("final_url") == target["source_url"]
            )
            results.append(result)
    results.sort(key=lambda item: item["capture_path"])

    verified_at = datetime.now(UTC).isoformat()
    new_rows: list[dict[str, Any]] = []
    for target, result in zip(targets, results, strict=True):
        if target["path"] != result["capture_path"]:
            raise OfficialPathRecoveryError("result ordering mismatch")
        if not result["exact_capture_match"]:
            continue
        new_rows.append(
            {
                "schema_version": "official_path_document_lineage_v1",
                "capture_status": "checksum_capture_present",
                "capture": {
                    "path": f"etl/data/raw/{target['path']}",
                    "bytes": target["bytes"],
                    "sha256": target["sha256"],
                },
                "source_id": "senado_votaciones",
                "source_url": target["source_url"],
                "path_relation": {
                    "method": "exact_repository_path_projection",
                    "capture_path": target["path"],
                    "projected_source_url": target["source_url"],
                },
                "retrieval_verification": {
                    "method": "official_http_get_sha256_match",
                    "verified_at": verified_at,
                    "requested_url": target["source_url"],
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
    merged = {str(item["capture"]["path"]): item for item in existing_rows + new_rows}
    manifest_rows = sorted(
        merged.values(),
        key=lambda item: str(item["capture"]["path"]),
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
    exact_results = [item for item in results if item["exact_capture_match"]]
    report: dict[str, Any] = {
        "schema_version": "official_path_document_lineage_report_v1",
        "generated_at": verified_at,
        "status": "ok" if len(exact_results) == len(targets) else "partial",
        "policy": {
            "official_real_records_only": True,
            "path_projection_is_not_provenance_without_exact_download_match": True,
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
                "eligible_senate_session_gaps": len(targets),
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
            "existing_manifest_relations_preserved": len(existing_rows),
            "candidate_paths_probed": len(targets),
            "downloads_succeeded": statuses["downloaded"],
            "downloads_failed": statuses["failed"],
            "exact_official_byte_matches_added": len(new_rows),
            "nonmatching_official_responses": sum(
                item.get("status") == "downloaded" and not item["exact_capture_match"]
                for item in results
            ),
            "manifest_relations": len(manifest_rows),
            "recovered_bytes_added": sum(
                int(item["expected_bytes"]) for item in exact_results
            ),
        },
        "checks": {
            "manifest_preserves_only_checksum_exact_relations": len(manifest_rows)
            == len(existing_rows) + len(new_rows),
            "unmatched_candidates_not_added_to_manifest": all(
                item["exact_capture_match"]
                or f"etl/data/raw/{item['capture_path']}" not in merged
                for item in results
            ),
            "no_guessed_source_url_accepted": True,
            "public_domain_personal_information_retained": True,
            "no_remote_mutation_performed": True,
        },
        "manifest": {
            "path": display_path(manifest_out),
            "bytes": manifest_out.stat().st_size,
            "sha256": sha256_file(manifest_out),
            "rows": len(manifest_rows),
        },
        "download_results": results,
        "next_action": (
            "Load the exact official-path lineage into the document provenance "
            "audit; keep nonmatching historical captures in the residual queue."
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
            manifest_out=safe_repo_path(args.manifest_out),
            report_out=safe_repo_path(args.report_out),
            workers=args.workers,
            timeout=args.timeout,
            attempts=args.attempts,
            max_document_bytes=args.max_document_bytes,
            user_agent=args.user_agent,
        )
    except (
        OfficialPathRecoveryError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2
    print(json.dumps({"status": report["status"], **report["totals"]}, sort_keys=True))
    if args.enforce and not all(report["checks"].values()):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
