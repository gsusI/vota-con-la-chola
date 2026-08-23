#!/usr/bin/env python3
"""Recover missing document lineage from exact links in preserved official pages."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urldefrag, urljoin, urlparse

if __package__:
    from scripts.audit_document_provenance import (
        HTML_HREF_RE,
        extract_official_senate_capture_urls,
        is_official_parliament_document_url,
        read_embedded_metadata_text,
    )
else:
    from audit_document_provenance import (
        HTML_HREF_RE,
        extract_official_senate_capture_urls,
        is_official_parliament_document_url,
        read_embedded_metadata_text,
    )

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY_ROOT = Path("etl/data/raw")
DEFAULT_EVIDENCE_ROOT = Path("etl/data/raw/text_documents/parl_initiative_docs")
DEFAULT_QUEUE = Path("etl/data/manifests/document-provenance-gap-queue.jsonl")
DEFAULT_SEEDS = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "initiative-document-link-recovery-seeds.json"
)
DEFAULT_MANIFEST = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "captured-link-document-lineage.jsonl"
)
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "captured-link-document-lineage.json"
)
DEFAULT_USER_AGENT = "vota-con-la-chola-accountability-etl/1.0"
TARGET_SOURCE_GROUP = "text_documents/parl_initiative_docs"
SHA256_LENGTH = 64
PDF_MAGIC = b"%PDF-"
RETRYABLE_HTTP_CODES = {408, 429, 500, 502, 503, 504}


class CapturedLinkRecoveryError(RuntimeError):
    """Raised when exact-link recovery cannot preserve its evidence contract."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory-root", default=str(DEFAULT_INVENTORY_ROOT))
    parser.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT))
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE))
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
        raise CapturedLinkRecoveryError(f"path escapes repository: {value}") from exc
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


def load_gap_targets(path: Path) -> dict[str, dict[str, Any]]:
    targets: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CapturedLinkRecoveryError(
                    f"invalid gap queue JSON at line {line_number}: {exc}"
                ) from exc
            if item.get("source_group") != TARGET_SOURCE_GROUP:
                continue
            sha256 = str(item.get("sha256") or "").lower()
            document_path = str(item.get("path") or "")
            declared_bytes = item.get("bytes")
            if (
                len(sha256) != SHA256_LENGTH
                or not document_path
                or not isinstance(declared_bytes, int)
                or declared_bytes <= 0
                or item.get("official_real_file") is not True
                or item.get("guessed_source_url") is not False
                or item.get("public_domain_personal_information_retained") is not True
            ):
                raise CapturedLinkRecoveryError(
                    f"invalid real gap target at line {line_number}"
                )
            if sha256 in targets and targets[sha256]["path"] != document_path:
                raise CapturedLinkRecoveryError(
                    f"duplicate target checksum maps to multiple paths: {sha256}"
                )
            targets[sha256] = item
    if not targets:
        raise CapturedLinkRecoveryError("no real initiative-document gaps found")
    return targets


def load_seed_keys(path: Path) -> set[tuple[str, str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        payload.get("schema_version") != "initiative_document_link_recovery_seeds_v1"
        or payload.get("synthetic_or_mock_records_counted") is not False
        or payload.get("public_domain_personal_information_retained") is not True
        or not isinstance(payload.get("initiatives"), list)
    ):
        raise CapturedLinkRecoveryError("invalid exact-link recovery seed contract")
    keys: set[tuple[str, str, str]] = set()
    for item in payload["initiatives"]:
        if not isinstance(item, dict):
            raise CapturedLinkRecoveryError("invalid initiative seed")
        key = tuple(str(item.get(field) or "") for field in ("id1", "id2", "legis"))
        if len(key) != 3 or any(not value.isdigit() for value in key):
            raise CapturedLinkRecoveryError(f"invalid initiative seed: {item!r}")
        keys.add(key)
    if not keys:
        raise CapturedLinkRecoveryError("initiative seed set is empty")
    return keys


def load_existing_manifest_rows(path: Path) -> list[dict[str, Any]]:
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
                raise CapturedLinkRecoveryError(
                    f"invalid existing lineage JSON at line {line_number}: {exc}"
                ) from exc
            capture = item.get("capture")
            if (
                item.get("schema_version") != "captured_link_document_lineage_v1"
                or item.get("synthetic_or_mock_records_counted") is not False
                or item.get("public_domain_personal_information_retained") is not True
                or not isinstance(capture, dict)
                or len(str(capture.get("sha256") or "")) != SHA256_LENGTH
                or not is_official_parliament_document_url(
                    str(item.get("source_url") or "")
                )
            ):
                raise CapturedLinkRecoveryError(
                    f"invalid existing lineage contract at line {line_number}"
                )
            rows.append(item)
    return rows


def merge_manifest_rows(
    existing_rows: list[dict[str, Any]],
    current_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged = {
        (str(item["capture"]["sha256"]), str(item["source_url"])): item
        for item in existing_rows
    }
    merged.update(
        {
            (str(item["capture"]["sha256"]), str(item["source_url"])): item
            for item in current_rows
        }
    )
    return sorted(
        merged.values(),
        key=lambda item: (item["capture"]["path"], item["source_url"]),
    )


def senate_initiative_key(source_url: str) -> tuple[str, str, str] | None:
    query = parse_qs(urlparse(source_url).query, keep_blank_values=True)
    values = tuple(
        query.get(field, [""])[0] if len(query.get(field, [])) == 1 else ""
        for field in ("id1", "id2", "legis")
    )
    return values if all(value.isdigit() for value in values) else None


def discover_exact_links(
    evidence_root: Path,
    *,
    inventory_root: Path,
    seed_keys: set[tuple[str, str, str]],
) -> tuple[dict[str, list[dict[str, str]]], dict[str, Any]]:
    candidates: dict[str, list[dict[str, str]]] = defaultdict(list)
    counts: Counter[str] = Counter()
    matched_seed_keys: set[tuple[str, str, str]] = set()
    for capture_path in sorted(evidence_root.rglob("*.html")):
        counts["html_files_scanned"] += 1
        payload, read_status = read_embedded_metadata_text(capture_path)
        counts[f"read_status_{read_status}"] += 1
        if payload is None:
            continue
        capture_urls = extract_official_senate_capture_urls(payload)
        matching_page_urls = sorted(
            source_url
            for source_url in capture_urls
            if senate_initiative_key(source_url) in seed_keys
        )
        if not matching_page_urls:
            continue
        counts["evidence_pages_matched"] += 1
        capture_relative = (
            capture_path.resolve().relative_to(inventory_root.resolve()).as_posix()
        )
        capture_sha256 = sha256_file(capture_path)
        raw_hrefs = HTML_HREF_RE.findall(payload)
        for page_url in matching_page_urls:
            key = senate_initiative_key(page_url)
            if key is not None:
                matched_seed_keys.add(key)
            for raw_href in raw_hrefs:
                decoded_href = html.unescape(raw_href).strip()
                embedded_source_url = urljoin(page_url, decoded_href)
                retrieval_url, _fragment = urldefrag(embedded_source_url)
                if not is_official_parliament_document_url(retrieval_url):
                    continue
                evidence = {
                    "capture_path": capture_relative,
                    "capture_sha256": capture_sha256,
                    "capture_page_url": page_url,
                    "raw_href": decoded_href,
                    "embedded_source_url": embedded_source_url,
                    "retrieval_url": retrieval_url,
                }
                if evidence not in candidates[retrieval_url]:
                    candidates[retrieval_url].append(evidence)
    missing_seed_keys = sorted(seed_keys - matched_seed_keys)
    if missing_seed_keys:
        raise CapturedLinkRecoveryError(
            f"seed initiatives lack exact captured pages: {missing_seed_keys}"
        )
    for evidence_rows in candidates.values():
        evidence_rows.sort(
            key=lambda item: (
                item["capture_page_url"],
                item["capture_path"],
                item["raw_href"],
            )
        )
    counts["seed_initiatives"] = len(seed_keys)
    counts["seed_initiatives_matched"] = len(matched_seed_keys)
    counts["candidate_urls"] = len(candidates)
    counts["embedded_relations"] = sum(len(rows) for rows in candidates.values())
    return dict(sorted(candidates.items())), dict(sorted(counts.items()))


def download_digest(
    source_url: str,
    *,
    timeout: int,
    attempts: int,
    max_document_bytes: int,
    user_agent: str,
) -> dict[str, Any]:
    last_error = "unknown error"
    for attempt in range(1, max(1, attempts) + 1):
        try:
            request = urllib.request.Request(
                source_url,
                headers={
                    "User-Agent": user_agent,
                    "Accept": "application/pdf,*/*;q=0.5",
                },
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = int(getattr(response, "status", 200))
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > max_document_bytes:
                    raise CapturedLinkRecoveryError(
                        f"content length exceeds limit: {content_length}"
                    )
                digest = hashlib.sha256()
                downloaded_bytes = 0
                first_chunk = b""
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    if not first_chunk:
                        first_chunk = chunk[:16]
                    downloaded_bytes += len(chunk)
                    if downloaded_bytes > max_document_bytes:
                        raise CapturedLinkRecoveryError(
                            f"download exceeds limit: {downloaded_bytes}"
                        )
                    digest.update(chunk)
                final_url, _fragment = urldefrag(response.geturl())
                if not is_official_parliament_document_url(final_url):
                    raise CapturedLinkRecoveryError(
                        f"redirect left official document allowlist: {final_url}"
                    )
                if not first_chunk.startswith(PDF_MAGIC):
                    raise CapturedLinkRecoveryError("response is not a PDF payload")
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
        except (
            CapturedLinkRecoveryError,
            OSError,
            TimeoutError,
            urllib.error.URLError,
            ValueError,
        ) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt >= attempts:
                break
        time.sleep(min(8.0, float(2 ** (attempt - 1))))
    return {
        "source_url": source_url,
        "status": "failed",
        "attempts": max(1, attempts),
        "error": last_error,
    }


def recover(
    *,
    inventory_root: Path,
    evidence_root: Path,
    queue_path: Path,
    seed_path: Path,
    manifest_out: Path,
    report_out: Path,
    workers: int,
    timeout: int,
    attempts: int,
    max_document_bytes: int,
    user_agent: str,
) -> dict[str, Any]:
    targets = load_gap_targets(queue_path)
    seed_keys = load_seed_keys(seed_path)
    existing_manifest_rows = load_existing_manifest_rows(manifest_out)
    candidate_evidence, discovery = discover_exact_links(
        evidence_root,
        inventory_root=inventory_root,
        seed_keys=seed_keys,
    )
    if not candidate_evidence:
        raise CapturedLinkRecoveryError("no exact official document links discovered")
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(
                download_digest,
                source_url,
                timeout=max(1, timeout),
                attempts=max(1, attempts),
                max_document_bytes=max(1, max_document_bytes),
                user_agent=user_agent,
            ): source_url
            for source_url in candidate_evidence
        }
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: item["source_url"])

    verified_at = datetime.now(UTC).isoformat()
    manifest_rows: list[dict[str, Any]] = []
    recovered_hashes: set[str] = set()
    for result in results:
        if result["status"] != "downloaded":
            continue
        target = targets.get(str(result["downloaded_sha256"]))
        if target is None or result["downloaded_bytes"] != target["bytes"]:
            result["target_match"] = "none"
            continue
        result["target_match"] = str(target["path"])
        recovered_hashes.add(str(target["sha256"]))
        evidence_rows = candidate_evidence[result["source_url"]]
        evidence = evidence_rows[0]
        manifest_rows.append(
            {
                "schema_version": "captured_link_document_lineage_v1",
                "capture_status": "checksum_capture_present",
                "capture": {
                    "path": f"etl/data/raw/{target['path']}",
                    "bytes": target["bytes"],
                    "sha256": target["sha256"],
                },
                "source_id": "parl_initiative_docs",
                "source_url": result["source_url"],
                "embedded_link_evidence": {
                    **evidence,
                    "capture_path": f"etl/data/raw/{evidence['capture_path']}",
                    "evidence_relations_for_url": len(evidence_rows),
                },
                "retrieval_verification": {
                    "method": "official_http_get_sha256_match",
                    "verified_at": verified_at,
                    "requested_url": result["source_url"],
                    "final_url": result["final_url"],
                    "http_status": result["http_status"],
                    "content_type": result["content_type"],
                    "downloaded_bytes": result["downloaded_bytes"],
                    "downloaded_sha256": result["downloaded_sha256"],
                },
                "public_domain_personal_information_retained": True,
                "synthetic_or_mock_records_counted": False,
                "remote_mutation_performed": False,
            }
        )
    manifest_rows = merge_manifest_rows(existing_manifest_rows, manifest_rows)
    manifest_out.parent.mkdir(parents=True, exist_ok=True)
    manifest_out.write_text(
        "".join(
            json.dumps(item, ensure_ascii=True, sort_keys=True) + "\n"
            for item in manifest_rows
        ),
        encoding="utf-8",
    )

    statuses = Counter(str(item["status"]) for item in results)
    unmatched_downloads = sum(
        1
        for item in results
        if item["status"] == "downloaded" and item.get("target_match") == "none"
    )
    report: dict[str, Any] = {
        "schema_version": "captured_link_document_lineage_report_v1",
        "generated_at": verified_at,
        "status": "ok" if recovered_hashes else "no_matches",
        "policy": {
            "official_real_records_only": True,
            "exact_embedded_links_only": True,
            "downloaded_bytes_must_match_existing_gap_sha256_and_size": True,
            "guessed_source_urls_forbidden": True,
            "synthetic_or_mock_records_counted": False,
            "public_domain_personal_information_retained": True,
            "remote_mutation_performed": False,
        },
        "inputs": {
            "queue": {
                "path": display_path(queue_path),
                "bytes": queue_path.stat().st_size,
                "sha256": sha256_file(queue_path),
                "target_rows": len(targets),
            },
            "seeds": {
                "path": display_path(seed_path),
                "bytes": seed_path.stat().st_size,
                "sha256": sha256_file(seed_path),
                "initiative_rows": len(seed_keys),
            },
        },
        "execution": {
            "workers": max(1, workers),
            "timeout_seconds": max(1, timeout),
            "attempts": max(1, attempts),
            "max_document_bytes": max(1, max_document_bytes),
            "http_method": "GET",
        },
        "discovery": discovery,
        "totals": {
            "candidate_urls": len(candidate_evidence),
            "downloads_succeeded": statuses["downloaded"],
            "downloads_failed": statuses["failed"],
            "downloaded_without_target_match": unmatched_downloads,
            "manifest_relations": len(manifest_rows),
            "existing_manifest_relations_preserved": len(existing_manifest_rows),
            "current_gap_relations_added_or_refreshed": sum(
                1
                for item in manifest_rows
                if str(item["capture"]["sha256"]) in recovered_hashes
            ),
            "distinct_gap_files_recovered": len(recovered_hashes),
            "distinct_gap_files_remaining_in_lane": len(targets)
            - len(recovered_hashes),
            "recovered_bytes": sum(
                int(targets[sha256]["bytes"]) for sha256 in recovered_hashes
            ),
        },
        "checks": {
            "all_seed_initiatives_matched_captured_pages": discovery["seed_initiatives"]
            == discovery["seed_initiatives_matched"],
            "candidate_urls_bounded": len(candidate_evidence) <= 1000,
            "at_least_one_exact_checksum_match": bool(recovered_hashes),
            "manifest_contains_only_exact_matches": all(
                item["capture"]["sha256"]
                == item["retrieval_verification"]["downloaded_sha256"]
                and item["capture"]["bytes"]
                == item["retrieval_verification"]["downloaded_bytes"]
                for item in manifest_rows
            ),
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
            "Load the checksum-exact captured-link manifest into the document "
            "provenance audit, then regenerate the residual gap queue."
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
            evidence_root=safe_repo_path(args.evidence_root),
            queue_path=safe_repo_path(args.queue),
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
        CapturedLinkRecoveryError,
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
                "report": report["manifest"]["path"].replace(
                    "captured-link-document-lineage.jsonl",
                    "captured-link-document-lineage.json",
                ),
            },
            sort_keys=True,
        )
    )
    if args.enforce and not all(report["checks"].values()):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
