#!/usr/bin/env python3
"""Audit vote source URL transport and checksum-backed local captures."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sqlite3
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = Path("etl/data/derived/member-vote-shards")
DEFAULT_MANIFEST = Path("etl/data/published/member-vote-shard-manifest-latest.json")
DEFAULT_CAPTURE_ROOT = Path("etl/data/raw/manual/senado_votaciones_ses")
DEFAULT_URL_MANIFEST = Path("etl/data/manifests/member-vote-source-url-lineage.jsonl")
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "member-vote-source-url-lineage-20260812.json"
)
SENATE_LEGACY_PATH_RE = re.compile(
    r"^/legis(?P<legislature>\d+)/votaciones/(?P<filename>ses_[^/]+\.xml)$"
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_RESPONSE_HEADERS = {
    "cache-control",
    "cf-mitigated",
    "content-length",
    "content-type",
    "date",
    "location",
    "server",
}


class VoteUrlAuditError(RuntimeError):
    """Raised when vote source lineage cannot be audited safely."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--capture-root", default=str(DEFAULT_CAPTURE_ROOT))
    parser.add_argument("--url-manifest-out", default=str(DEFAULT_URL_MANIFEST))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--probe-url", action="append", default=[])
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--max-probe-bytes", type=int, default=5 * 1024 * 1024)
    parser.add_argument("--enforce-integrity", action="store_true")
    return parser.parse_args(argv)


def safe_repo_path(value: str | Path, *, repo_root: Path) -> Path:
    candidate = (repo_root / value).resolve()
    try:
        candidate.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise VoteUrlAuditError(f"path escapes repository: {value}") from exc
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
        raise VoteUrlAuditError(f"invalid JSON object {path.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise VoteUrlAuditError(f"JSON root must be an object: {path.name}")
    return payload


def https_candidate(source_url: str) -> str:
    parsed = urlparse(source_url)
    if parsed.scheme.lower() != "http" or not parsed.hostname:
        raise VoteUrlAuditError(f"probe URL is not a public HTTP URL: {source_url}")
    return urlunparse(parsed._replace(scheme="https"))


def capture_path_for_url(source_url: str, capture_root: Path) -> Path | None:
    parsed = urlparse(source_url)
    if (parsed.hostname or "").lower() != "www.senado.es":
        return None
    match = SENATE_LEGACY_PATH_RE.fullmatch(parsed.path)
    if not match:
        return None
    return capture_root / f"legis{match.group('legislature')}" / match.group("filename")


def create_work_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        PRAGMA journal_mode = OFF;
        PRAGMA synchronous = OFF;
        CREATE TABLE urls (
          source_url TEXT PRIMARY KEY,
          scheme TEXT NOT NULL,
          host TEXT NOT NULL,
          rows_total INTEGER NOT NULL DEFAULT 0
        ) WITHOUT ROWID;
        CREATE TABLE url_scopes (
          source_url TEXT NOT NULL,
          source_id TEXT NOT NULL,
          legislature TEXT NOT NULL,
          rows_total INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY(source_url, source_id, legislature)
        ) WITHOUT ROWID;
        CREATE TABLE url_lineage (
          source_url TEXT NOT NULL,
          source_record_id TEXT NOT NULL,
          source_hash TEXT NOT NULL,
          PRIMARY KEY(source_url, source_record_id, source_hash)
        ) WITHOUT ROWID;
        """
    )
    return connection


def valid_public_url(value: Any) -> tuple[str, str, str]:
    source_url = str(value or "").strip()
    parsed = urlparse(source_url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    if scheme not in {"http", "https"} or not host:
        raise VoteUrlAuditError(f"vote row has no public HTTP(S) source URL: {value!r}")
    return source_url, scheme, host


def ingest_vote_shards(
    work: sqlite3.Connection,
    *,
    root: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise VoteUrlAuditError("vote shard manifest has no entries")
    totals: Counter[str] = Counter()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise VoteUrlAuditError(f"invalid shard manifest entry {index}")
        relative = Path(str(entry.get("shard") or ""))
        if relative.is_absolute() or ".." in relative.parts:
            raise VoteUrlAuditError(f"unsafe shard path: {relative}")
        shard_path = (root / relative).resolve()
        try:
            shard_path.relative_to(root.resolve())
        except ValueError as exc:
            raise VoteUrlAuditError(f"shard path escapes root: {relative}") from exc
        if not shard_path.is_file():
            raise VoteUrlAuditError(f"missing shard: {relative}")
        observed_bytes = shard_path.stat().st_size
        if observed_bytes != int(entry.get("shard_bytes", -1)):
            raise VoteUrlAuditError(f"shard byte mismatch: {relative}")
        if sha256_file(shard_path) != entry.get("shard_sha256"):
            raise VoteUrlAuditError(f"shard checksum mismatch: {relative}")
        try:
            with gzip.open(shard_path, "rt", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise VoteUrlAuditError(f"invalid shard payload {relative}: {exc}") from exc
        member_votes = payload.get("member_votes")
        if not isinstance(member_votes, list):
            raise VoteUrlAuditError(f"shard has no member_votes array: {relative}")
        if len(member_votes) != int(entry.get("member_votes", -1)):
            raise VoteUrlAuditError(f"shard member count mismatch: {relative}")
        event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
        parent_source = (
            payload.get("source") if isinstance(payload.get("source"), dict) else {}
        )
        source_id_default = str(
            event.get("source_id") or entry.get("source_id") or "unknown"
        )
        legislature = str(
            event.get("legislature") or entry.get("legislature") or "unknown"
        )
        per_url: Counter[tuple[str, str, str, str, str]] = Counter()
        per_lineage: set[tuple[str, str, str]] = set()
        for member_vote in member_votes:
            if not isinstance(member_vote, dict):
                raise VoteUrlAuditError(f"non-object member vote: {relative}")
            source = (
                member_vote.get("source")
                if isinstance(member_vote.get("source"), dict)
                else parent_source
            )
            source_url, scheme, host = valid_public_url(source.get("source_url"))
            source_id = str(source.get("source_id") or source_id_default)
            source_record_id = str(source.get("source_record_id") or "")
            source_hash = str(source.get("source_hash") or "").lower()
            if not source_record_id or not SHA256_RE.fullmatch(source_hash):
                raise VoteUrlAuditError(
                    f"vote row lacks source record/hash lineage: {relative}"
                )
            per_url[(source_url, scheme, host, source_id, legislature)] += 1
            per_lineage.add((source_url, source_record_id, source_hash))
        work.executemany(
            """
            INSERT OR IGNORE INTO url_lineage(source_url, source_record_id, source_hash)
            VALUES (?, ?, ?)
            """,
            per_lineage,
        )
        for (source_url, scheme, host, source_id, leg), rows in per_url.items():
            work.execute(
                """
                INSERT INTO urls(source_url, scheme, host, rows_total)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(source_url) DO UPDATE SET rows_total = rows_total + excluded.rows_total
                """,
                (source_url, scheme, host, rows),
            )
            work.execute(
                """
                INSERT INTO url_scopes(source_url, source_id, legislature, rows_total)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(source_url, source_id, legislature)
                DO UPDATE SET rows_total = rows_total + excluded.rows_total
                """,
                (source_url, source_id, leg, rows),
            )
            totals[f"rows_{scheme}"] += rows
            totals["member_votes"] += rows
        totals["shards"] += 1
        totals["shard_bytes"] += observed_bytes
        if totals["shards"] % 500 == 0:
            work.commit()
    work.commit()
    return dict(totals)


def read_bounded_response(response: Any, max_bytes: int) -> tuple[bytes, bool]:
    payload = response.read(max_bytes + 1)
    return payload[:max_bytes], len(payload) > max_bytes


def safe_headers(headers: Any) -> dict[str, str]:
    return {
        key.lower(): str(value)
        for key, value in headers.items()
        if key.lower() in SAFE_RESPONSE_HEADERS
    }


def probe_https_url(
    source_url: str, *, timeout: float, max_bytes: int
) -> dict[str, Any]:
    candidate = https_candidate(source_url)
    request = Request(
        candidate,
        headers={
            "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.1",
            "User-Agent": "vota-con-la-chola-accountability-audit/1.0",
        },
    )
    result: dict[str, Any] = {
        "source_http_url": source_url,
        "https_candidate_url": candidate,
        "status": "failed",
        "http_status": None,
        "final_url": candidate,
        "response_bytes": 0,
        "response_sha256": None,
        "response_truncated": False,
        "headers": {},
        "error": None,
    }
    try:
        with urlopen(request, timeout=timeout) as response:
            payload, truncated = read_bounded_response(response, max_bytes)
            result.update(
                {
                    "status": "ok" if not truncated else "response_too_large",
                    "http_status": int(response.status),
                    "final_url": str(response.geturl()),
                    "response_bytes": len(payload),
                    "response_sha256": hashlib.sha256(payload).hexdigest(),
                    "response_truncated": truncated,
                    "headers": safe_headers(response.headers),
                }
            )
    except HTTPError as exc:
        payload, truncated = read_bounded_response(exc, max_bytes)
        result.update(
            {
                "status": "http_error",
                "http_status": int(exc.code),
                "final_url": str(exc.geturl()),
                "response_bytes": len(payload),
                "response_sha256": hashlib.sha256(payload).hexdigest(),
                "response_truncated": truncated,
                "headers": safe_headers(exc.headers),
                "error": f"HTTP {exc.code}: {exc.reason}",
            }
        )
    except (OSError, URLError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def write_url_manifest(
    work: sqlite3.Connection,
    *,
    capture_root: Path,
    output_path: Path,
    repo_root: Path,
) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    totals: Counter[str] = Counter()
    capture_hash_cache: dict[Path, tuple[int, str]] = {}
    query = """
    SELECT
      u.source_url,
      u.scheme,
      u.host,
      u.rows_total,
      COUNT(DISTINCT s.source_id) AS source_ids,
      COUNT(DISTINCT s.legislature) AS legislatures,
      COUNT(DISTINCT l.source_record_id) AS source_records,
      COUNT(DISTINCT l.source_hash) AS source_hashes
    FROM urls AS u
    JOIN url_scopes AS s ON s.source_url = u.source_url
    JOIN url_lineage AS l ON l.source_url = u.source_url
    GROUP BY u.source_url
    ORDER BY u.source_url
    """
    with output_path.open("w", encoding="utf-8") as handle:
        for row in work.execute(query):
            source_url = str(row["source_url"])
            capture_path = capture_path_for_url(source_url, capture_root)
            capture_status = "not_applicable"
            capture_ref = None
            if capture_path is not None:
                if capture_path.is_file():
                    if capture_path not in capture_hash_cache:
                        capture_hash_cache[capture_path] = (
                            capture_path.stat().st_size,
                            sha256_file(capture_path),
                        )
                    capture_bytes, capture_sha256 = capture_hash_cache[capture_path]
                    capture_status = "checksum_capture_present"
                    capture_ref = {
                        "path": display_path(capture_path, repo_root=repo_root),
                        "bytes": capture_bytes,
                        "sha256": capture_sha256,
                    }
                else:
                    capture_status = "capture_missing"
            item = {
                "source_url": source_url,
                "scheme": row["scheme"],
                "host": row["host"],
                "member_vote_rows": int(row["rows_total"]),
                "source_ids": int(row["source_ids"]),
                "legislatures": int(row["legislatures"]),
                "source_records": int(row["source_records"]),
                "source_hashes": int(row["source_hashes"]),
                "capture_status": capture_status,
                "capture": capture_ref,
                "https_candidate_url": (
                    https_candidate(source_url) if row["scheme"] == "http" else None
                ),
                "source_url_rewritten": False,
            }
            handle.write(json.dumps(item, ensure_ascii=True, sort_keys=True) + "\n")
            rows = int(row["rows_total"])
            totals["urls"] += 1
            totals["rows"] += rows
            totals[f"urls_{row['scheme']}"] += 1
            totals[f"rows_{row['scheme']}"] += rows
            if row["scheme"] == "http" and capture_status == "checksum_capture_present":
                totals["http_urls_with_checksum_capture"] += 1
                totals["http_rows_with_checksum_capture"] += rows
            if row["scheme"] == "http" and capture_status == "capture_missing":
                totals["http_urls_without_checksum_capture"] += 1
                totals["http_rows_without_checksum_capture"] += rows
    return dict(totals)


def scope_summary(work: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        {
            "source_id": row["source_id"],
            "legislature": row["legislature"],
            "scheme": row["scheme"],
            "host": row["host"],
            "member_vote_rows": int(row["rows_total"]),
            "distinct_urls": int(row["distinct_urls"]),
        }
        for row in work.execute(
            """
            SELECT
              s.source_id,
              s.legislature,
              u.scheme,
              u.host,
              SUM(s.rows_total) AS rows_total,
              COUNT(*) AS distinct_urls
            FROM url_scopes AS s
            JOIN urls AS u ON u.source_url = s.source_url
            GROUP BY s.source_id, s.legislature, u.scheme, u.host
            ORDER BY s.source_id, s.legislature, u.scheme, u.host
            """
        )
    ]


def artifact_reference(path: Path, *, repo_root: Path, rows: int) -> dict[str, Any]:
    return {
        "path": display_path(path, repo_root=repo_root),
        "rows": rows,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def run_audit(
    *,
    repo_root: Path,
    root: Path,
    manifest_path: Path,
    capture_root: Path,
    url_manifest_out: Path,
    report_out: Path,
    probe_urls: list[str],
    timeout: float,
    max_probe_bytes: int,
) -> dict[str, Any]:
    manifest = read_json_object(manifest_path)
    with tempfile.TemporaryDirectory(prefix="vota-vote-url-audit-") as temp_dir:
        work = create_work_database(Path(temp_dir) / "audit.sqlite")
        try:
            observed = ingest_vote_shards(work, root=root, manifest=manifest)
            url_totals = write_url_manifest(
                work,
                capture_root=capture_root,
                output_path=url_manifest_out,
                repo_root=repo_root,
            )
            scopes = scope_summary(work)
            known_urls = {
                str(row[0]) for row in work.execute("SELECT source_url FROM urls")
            }
        finally:
            work.close()
    unknown_probes = sorted(set(probe_urls) - known_urls)
    if unknown_probes:
        raise VoteUrlAuditError(
            "probe URLs are not present in the audited corpus: "
            + ", ".join(unknown_probes)
        )
    probes = [
        probe_https_url(url, timeout=timeout, max_bytes=max_probe_bytes)
        for url in dict.fromkeys(probe_urls)
    ]
    for probe in probes:
        capture_path = capture_path_for_url(str(probe["source_http_url"]), capture_root)
        capture = None
        if capture_path is not None and capture_path.is_file():
            capture = {
                "path": display_path(capture_path, repo_root=repo_root),
                "bytes": capture_path.stat().st_size,
                "sha256": sha256_file(capture_path),
            }
        probe["historical_capture"] = capture
        probe["https_matches_historical_capture"] = bool(
            probe.get("status") == "ok"
            and capture
            and probe.get("response_sha256") == capture["sha256"]
        )
    manifest_member_votes = int(manifest.get("member_votes_total", -1))
    manifest_events = int(manifest.get("events_total", -1))
    integrity_passed = (
        observed.get("member_votes") == manifest_member_votes
        and observed.get("shards") == manifest_events
        and url_totals.get("rows") == manifest_member_votes
    )
    all_http_classified = (
        int(url_totals.get("http_rows_without_checksum_capture", 0)) == 0
    )
    https_equivalence_verified = bool(probes) and all(
        item["https_matches_historical_capture"] for item in probes
    )
    report = {
        "schema_version": "member_vote_source_url_lineage_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "ok" if integrity_passed else "failed",
        "policy": {
            "official_real_records_only": True,
            "synthetic_or_mock_records_counted": False,
            "historical_source_urls_retained_exactly": True,
            "source_urls_silently_rewritten": False,
            "https_replacement_requires_content_equivalence": True,
            "public_domain_personal_information_retained": True,
        },
        "inputs": {
            "root": display_path(root, repo_root=repo_root),
            "manifest": artifact_reference(
                manifest_path,
                repo_root=repo_root,
                rows=manifest_events,
            ),
            "capture_root": display_path(capture_root, repo_root=repo_root),
        },
        "url_manifest": artifact_reference(
            url_manifest_out,
            repo_root=repo_root,
            rows=int(url_totals.get("urls", 0)),
        ),
        "totals": {
            **url_totals,
            "shards": int(observed.get("shards", 0)),
            "shard_bytes": int(observed.get("shard_bytes", 0)),
        },
        "scopes": scopes,
        "https_probes": probes,
        "checks": {
            "manifest_event_total_matches": observed.get("shards") == manifest_events,
            "manifest_member_vote_total_matches": observed.get("member_votes")
            == manifest_member_votes,
            "url_rows_reconcile": url_totals.get("rows") == manifest_member_votes,
            "all_shard_bytes_and_checksums_valid": True,
            "integrity_passed": integrity_passed,
            "all_http_rows_have_checksum_capture": all_http_classified,
            "probed_https_content_equivalence_verified": https_equivalence_verified,
            "secure_or_immutable_replacement_gate": all_http_classified,
        },
        "limitations": [
            "Historical HTTP source URLs are evidence and remain unchanged.",
            "A local checksum capture classifies insecure transport lineage but is not a durable public origin.",
            "Uncaptured HTTP URLs remain promotion blockers until an immutable official capture or content-equivalent HTTPS endpoint is verified.",
            "A 403 response does not establish content equivalence and must not be substituted for the historical source.",
        ],
        "next_action": (
            "Recover immutable official captures for every uncaptured HTTP URL, publish them by checksum, and retry HTTPS equivalence only when a new access lever exists."
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
    if args.timeout <= 0 or args.max_probe_bytes < 1:
        print("ERROR: timeout and max-probe-bytes must be positive")
        return 2
    try:
        report = run_audit(
            repo_root=REPO_ROOT,
            root=safe_repo_path(args.root, repo_root=REPO_ROOT),
            manifest_path=safe_repo_path(args.manifest, repo_root=REPO_ROOT),
            capture_root=safe_repo_path(args.capture_root, repo_root=REPO_ROOT),
            url_manifest_out=safe_repo_path(args.url_manifest_out, repo_root=REPO_ROOT),
            report_out=safe_repo_path(args.report_out, repo_root=REPO_ROOT),
            probe_urls=args.probe_url,
            timeout=args.timeout,
            max_probe_bytes=args.max_probe_bytes,
        )
    except (OSError, sqlite3.DatabaseError, VoteUrlAuditError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2
    print(
        json.dumps(
            {
                "status": report["status"],
                "member_vote_rows": report["totals"]["rows"],
                "http_rows": report["totals"].get("rows_http", 0),
                "http_urls": report["totals"].get("urls_http", 0),
                "http_rows_with_checksum_capture": report["totals"].get(
                    "http_rows_with_checksum_capture", 0
                ),
                "http_rows_without_checksum_capture": report["totals"].get(
                    "http_rows_without_checksum_capture", 0
                ),
                "https_probe_statuses": [
                    item["http_status"] for item in report["https_probes"]
                ],
                "secure_or_immutable_replacement_gate": report["checks"][
                    "secure_or_immutable_replacement_gate"
                ],
            },
            sort_keys=True,
        )
    )
    return (
        1 if args.enforce_integrity and not report["checks"]["integrity_passed"] else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
