#!/usr/bin/env python3
"""Recover exact document lineage from immutable Wayback captures.

Only repository-backed, evidence-derived source URLs are queried.  A relation is
published only when the replayed archive bytes exactly match the preserved local
capture by byte count and SHA-256.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_connectors_es.representatives.config import SOURCE_CONFIG

DEFAULT_INVENTORY_ROOT = Path("etl/data/raw")
DEFAULT_INVENTORY_MANIFEST = Path(
    "etl/data/manifests/real-document-format-inventory.jsonl"
)
DEFAULT_GAP_QUEUE = Path("etl/data/manifests/document-provenance-gap-queue.jsonl")
DEFAULT_STATE = Path("etl/data/staging/wayback-document-lineage.db")
DEFAULT_MANIFEST = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/wayback-document-lineage.jsonl"
)
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/wayback-document-lineage.json"
)
DEFAULT_CHECKPOINT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "wayback-document-checkpoint.jsonl"
)
DEFAULT_USER_AGENT = "vota-con-la-chola-accountability-etl/1.0"
CDX_ENDPOINT = "https://web.archive.org/cdx/search/cdx"
WAYBACK_REPLAY_PREFIX = "https://web.archive.org/web/"
EUROPARL_SOURCE_ID = "europarl_meps"
EUROPARL_SOURCE_URL = str(SOURCE_CONFIG[EUROPARL_SOURCE_ID]["default_url"])
EUROPARL_CAPTURE_PREFIX = "europarl_meps/"
SENATE_SOURCE_ID = "senado_votaciones"
SENATE_CAPTURE_RE = re.compile(
    r"^manual/senado_votaciones_ses/"
    r"legis(?P<legislature>\d+)/(?P<filename>ses_[^/]+\.xml)$"
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CDX_DIGEST_RE = re.compile(r"^[A-Z2-7]{32}$")
RETRYABLE_HTTP_CODES = {408, 429, 500, 502, 503, 504}
STATE_SCHEMA_VERSION = 1


class WaybackRecoveryError(RuntimeError):
    """Raised when archive recovery violates its evidence contract."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory-root", default=str(DEFAULT_INVENTORY_ROOT))
    parser.add_argument("--inventory-manifest", default=str(DEFAULT_INVENTORY_MANIFEST))
    parser.add_argument("--gap-queue", default=str(DEFAULT_GAP_QUEUE))
    parser.add_argument("--state", default=str(DEFAULT_STATE))
    parser.add_argument("--manifest-out", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--checkpoint-out", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--max-document-bytes", type=int, default=64 * 1024 * 1024)
    parser.add_argument("--max-captures-per-source", type=int, default=5000)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--refresh-index", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument(
        "--no-network",
        action="store_true",
        help=(
            "Rebind current real targets and export state/report/checkpoint without "
            "querying CDX or replaying archive candidates."
        ),
    )
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def safe_repo_path(value: str | Path) -> Path:
    candidate = (REPO_ROOT / value).resolve()
    try:
        candidate.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise WaybackRecoveryError(f"path escapes repository: {value}") from exc
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


def atomic_write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def target_key(source_url: str, expected_sha256: str, expected_bytes: int) -> str:
    payload = f"{source_url}\n{expected_sha256}\n{expected_bytes}".encode()
    return hashlib.sha256(payload).hexdigest()


def source_for_gap(item: dict[str, Any]) -> tuple[str, str] | None:
    capture_path = str(item.get("path") or "")
    source_group = str(item.get("source_group") or "")
    if source_group == EUROPARL_SOURCE_ID and capture_path.startswith(
        EUROPARL_CAPTURE_PREFIX
    ):
        return EUROPARL_SOURCE_ID, EUROPARL_SOURCE_URL
    senate_match = SENATE_CAPTURE_RE.fullmatch(capture_path)
    if source_group == "manual" and senate_match is not None:
        return (
            SENATE_SOURCE_ID,
            (
                "https://www.senado.es/"
                f"legis{senate_match.group('legislature')}/votaciones/"
                f"{senate_match.group('filename')}"
            ),
        )
    return None


def source_url_variants(source_url: str) -> list[str]:
    """Return exact endpoint variants; never broaden to host or prefix scope."""
    parsed = urllib.parse.urlsplit(source_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise WaybackRecoveryError(f"invalid evidence-derived source URL: {source_url}")
    host = parsed.hostname.lower()
    hosts = [host]
    if host.startswith("www."):
        hosts.append(host.removeprefix("www."))
    else:
        hosts.append(f"www.{host}")
    variants = {
        urllib.parse.urlunsplit((scheme, candidate_host, parsed.path, parsed.query, ""))
        for scheme in ("https", "http")
        for candidate_host in hosts
    }
    return sorted(variants)


def load_inventory(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise WaybackRecoveryError(
                    f"invalid inventory JSON at line {line_number}: {exc}"
                ) from exc
            item_path = str(item.get("path") or "")
            if (
                not item_path
                or PurePosixPath(item_path).is_absolute()
                or ".." in PurePosixPath(item_path).parts
            ):
                raise WaybackRecoveryError(
                    f"invalid inventory path at line {line_number}"
                )
            rows[item_path] = item
    return rows


def load_targets(
    queue_path: Path,
    *,
    inventory: dict[str, dict[str, Any]],
    inventory_root: Path,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with queue_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise WaybackRecoveryError(
                    f"invalid gap queue JSON at line {line_number}: {exc}"
                ) from exc
            source = source_for_gap(item)
            if source is None:
                continue
            capture_path = str(item.get("path") or "")
            expected_sha256 = str(item.get("sha256") or "").lower()
            expected_bytes = item.get("bytes")
            inventory_row = inventory.get(capture_path)
            local_path = (inventory_root / capture_path).resolve()
            try:
                local_path.relative_to(inventory_root.resolve())
            except ValueError as exc:
                raise WaybackRecoveryError(
                    f"gap capture escapes inventory at line {line_number}"
                ) from exc
            if (
                item.get("official_real_file") is not True
                or item.get("guessed_source_url") is not False
                or item.get("public_domain_personal_information_retained") is not True
                or not SHA256_RE.fullmatch(expected_sha256)
                or not isinstance(expected_bytes, int)
                or expected_bytes <= 0
                or inventory_row is None
                or inventory_row.get("real_data_status") != "eligible_real_capture"
                or str(inventory_row.get("sha256") or "").lower() != expected_sha256
                or inventory_row.get("bytes") != expected_bytes
                or not local_path.is_file()
                or local_path.stat().st_size != expected_bytes
                or sha256_file(local_path) != expected_sha256
            ):
                raise WaybackRecoveryError(
                    f"invalid real archive target at line {line_number}"
                )
            source_id, source_url = source
            rows.append(
                {
                    "target_key": target_key(
                        source_url, expected_sha256, expected_bytes
                    ),
                    "path": capture_path,
                    "source_group": item["source_group"],
                    "source_id": source_id,
                    "source_url": source_url,
                    "expected_sha256": expected_sha256,
                    "expected_bytes": expected_bytes,
                }
            )
    return sorted(rows, key=lambda item: item["path"])


def open_state(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;
        CREATE TABLE IF NOT EXISTS metadata (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS targets (
          target_key TEXT PRIMARY KEY,
          source_id TEXT NOT NULL,
          source_url TEXT NOT NULL,
          expected_sha256 TEXT NOT NULL,
          expected_bytes INTEGER NOT NULL,
          path_count INTEGER NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS target_paths (
          target_key TEXT NOT NULL REFERENCES targets(target_key),
          capture_path TEXT NOT NULL,
          source_group TEXT NOT NULL,
          PRIMARY KEY (target_key, capture_path)
        );
        CREATE TABLE IF NOT EXISTS cdx_queries (
          source_variant TEXT PRIMARY KEY,
          queried_at TEXT NOT NULL,
          status TEXT NOT NULL,
          attempts INTEGER NOT NULL,
          response_sha256 TEXT,
          candidate_count INTEGER NOT NULL DEFAULT 0,
          error TEXT
        );
        CREATE TABLE IF NOT EXISTS archive_candidates (
          candidate_key TEXT PRIMARY KEY,
          source_variant TEXT NOT NULL,
          timestamp TEXT NOT NULL,
          original_url TEXT NOT NULL,
          mimetype TEXT,
          statuscode INTEGER NOT NULL,
          cdx_digest TEXT NOT NULL,
          cdx_length INTEGER,
          state TEXT NOT NULL DEFAULT 'pending',
          attempts INTEGER NOT NULL DEFAULT 0,
          archive_url TEXT NOT NULL,
          final_url TEXT,
          http_status INTEGER,
          content_type TEXT,
          downloaded_bytes INTEGER,
          downloaded_sha256 TEXT,
          last_error TEXT,
          updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS archive_candidates_source_idx
          ON archive_candidates(source_variant, state);
        """
    )
    observed = connection.execute(
        "SELECT value FROM metadata WHERE key = 'schema_version'"
    ).fetchone()
    if observed is None:
        connection.execute(
            "INSERT INTO metadata(key, value) VALUES ('schema_version', ?)",
            (str(STATE_SCHEMA_VERSION),),
        )
    elif int(observed["value"]) != STATE_SCHEMA_VERSION:
        raise WaybackRecoveryError("archive worker state schema mismatch")
    connection.commit()
    return connection


def sync_targets(
    connection: sqlite3.Connection, targets: list[dict[str, Any]], *, now: str
) -> None:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in targets:
        groups.setdefault(item["target_key"], []).append(item)
    connection.execute("DELETE FROM target_paths")
    connection.execute("DELETE FROM targets")
    for key, items in sorted(groups.items()):
        first = items[0]
        connection.execute(
            """
            INSERT INTO targets(
              target_key, source_id, source_url, expected_sha256,
              expected_bytes, path_count, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key,
                first["source_id"],
                first["source_url"],
                first["expected_sha256"],
                first["expected_bytes"],
                len(items),
                now,
            ),
        )
        connection.executemany(
            """
            INSERT INTO target_paths(target_key, capture_path, source_group)
            VALUES (?, ?, ?)
            """,
            [(key, item["path"], item["source_group"]) for item in items],
        )
    connection.commit()


def request_bytes(
    url: str,
    *,
    timeout: int,
    attempts: int,
    user_agent: str,
    accept: str,
    max_bytes: int,
) -> dict[str, Any]:
    last_error = "unknown error"
    attempts_used = 0
    for attempt in range(1, max(1, attempts) + 1):
        attempts_used = attempt
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": user_agent, "Accept": accept},
            )
            with urllib.request.urlopen(request, timeout=max(1, timeout)) as response:
                status = int(getattr(response, "status", 200))
                declared_length = response.headers.get("Content-Length")
                if declared_length and int(declared_length) > max_bytes:
                    raise WaybackRecoveryError(
                        f"content length exceeds limit: {declared_length}"
                    )
                payload = bytearray()
                while True:
                    chunk = response.read(min(1024 * 1024, max_bytes + 1))
                    if not chunk:
                        break
                    payload.extend(chunk)
                    if len(payload) > max_bytes:
                        raise WaybackRecoveryError(
                            f"download exceeds limit: {len(payload)}"
                        )
                return {
                    "status": "downloaded",
                    "attempts": attempt,
                    "http_status": status,
                    "content_type": response.headers.get("Content-Type"),
                    "final_url": response.geturl(),
                    "payload": bytes(payload),
                }
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}: {exc.reason}"
            if exc.code not in RETRYABLE_HTTP_CODES or attempt >= attempts:
                break
        except (OSError, TimeoutError, ValueError, WaybackRecoveryError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt >= attempts:
                break
        time.sleep(min(8.0, float(2 ** (attempt - 1))))
    return {"status": "failed", "attempts": attempts_used, "error": last_error}


def cdx_query_url(source_variant: str, *, limit: int) -> str:
    query = urllib.parse.urlencode(
        {
            "url": source_variant,
            "output": "json",
            "fl": "timestamp,original,mimetype,statuscode,digest,length",
            "filter": "statuscode:200",
            "collapse": "digest",
            "limit": str(limit),
        }
    )
    return f"{CDX_ENDPOINT}?{query}"


def parse_cdx_payload(payload: bytes, *, source_variant: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WaybackRecoveryError(f"invalid CDX JSON for {source_variant}") from exc
    if parsed == []:
        return []
    header = ["timestamp", "original", "mimetype", "statuscode", "digest", "length"]
    if not isinstance(parsed, list) or not parsed or parsed[0] != header:
        raise WaybackRecoveryError(f"unexpected CDX schema for {source_variant}")
    rows: list[dict[str, Any]] = []
    for line_number, values in enumerate(parsed[1:], start=2):
        if not isinstance(values, list) or len(values) != len(header):
            raise WaybackRecoveryError(
                f"invalid CDX row {line_number} for {source_variant}"
            )
        item = dict(zip(header, values, strict=True))
        timestamp = str(item["timestamp"])
        original = str(item["original"])
        digest = str(item["digest"])
        try:
            statuscode = int(item["statuscode"])
            length = int(item["length"]) if str(item["length"]).isdigit() else None
        except ValueError as exc:
            raise WaybackRecoveryError(
                f"invalid CDX numeric row {line_number} for {source_variant}"
            ) from exc
        if (
            not re.fullmatch(r"\d{14}", timestamp)
            or statuscode != 200
            or not CDX_DIGEST_RE.fullmatch(digest)
        ):
            raise WaybackRecoveryError(
                f"invalid CDX evidence row {line_number} for {source_variant}"
            )
        archive_url = f"{WAYBACK_REPLAY_PREFIX}{timestamp}id_/{original}"
        candidate_key = hashlib.sha256(
            f"{timestamp}\n{original}\n{digest}".encode()
        ).hexdigest()
        rows.append(
            {
                "candidate_key": candidate_key,
                "source_variant": source_variant,
                "timestamp": timestamp,
                "original_url": original,
                "mimetype": item["mimetype"],
                "statuscode": statuscode,
                "cdx_digest": digest,
                "cdx_length": length,
                "archive_url": archive_url,
            }
        )
    return rows


def query_indexes(
    connection: sqlite3.Connection,
    source_urls: list[str],
    *,
    refresh_index: bool,
    retry_failed: bool,
    timeout: int,
    attempts: int,
    max_captures_per_source: int,
    user_agent: str,
) -> list[dict[str, Any]]:
    query_results: list[dict[str, Any]] = []
    now = datetime.now(UTC).isoformat()
    variants = sorted({v for url in source_urls for v in source_url_variants(url)})
    for variant in variants:
        prior = connection.execute(
            "SELECT * FROM cdx_queries WHERE source_variant = ?", (variant,)
        ).fetchone()
        if prior is not None and prior["status"] == "ok" and not refresh_index:
            query_results.append(
                {
                    "source_variant": variant,
                    "status": "checkpoint_reused",
                    "candidate_count": prior["candidate_count"],
                }
            )
            continue
        if (
            prior is not None
            and prior["status"] == "failed"
            and not retry_failed
            and not refresh_index
        ):
            query_results.append(
                {
                    "source_variant": variant,
                    "status": "failed_checkpoint_reused",
                    "error": prior["error"],
                }
            )
            continue
        url = cdx_query_url(variant, limit=max(1, max_captures_per_source))
        result = request_bytes(
            url,
            timeout=timeout,
            attempts=attempts,
            user_agent=user_agent,
            accept="application/json",
            max_bytes=64 * 1024 * 1024,
        )
        if result["status"] != "downloaded":
            connection.execute(
                """
                INSERT INTO cdx_queries(
                  source_variant, queried_at, status, attempts, candidate_count, error
                ) VALUES (?, ?, 'failed', ?, 0, ?)
                ON CONFLICT(source_variant) DO UPDATE SET
                  queried_at = excluded.queried_at,
                  status = excluded.status,
                  attempts = excluded.attempts,
                  candidate_count = 0,
                  error = excluded.error
                """,
                (variant, now, result["attempts"], result["error"]),
            )
            connection.commit()
            query_results.append(
                {
                    "source_variant": variant,
                    "status": "failed",
                    "error": result["error"],
                }
            )
            continue
        payload = result.pop("payload")
        try:
            candidates = parse_cdx_payload(payload, source_variant=variant)
        except WaybackRecoveryError as exc:
            connection.execute(
                """
                INSERT INTO cdx_queries(
                  source_variant, queried_at, status, attempts,
                  response_sha256, candidate_count, error
                ) VALUES (?, ?, 'failed', ?, ?, 0, ?)
                ON CONFLICT(source_variant) DO UPDATE SET
                  queried_at = excluded.queried_at,
                  status = excluded.status,
                  attempts = excluded.attempts,
                  response_sha256 = excluded.response_sha256,
                  candidate_count = 0,
                  error = excluded.error
                """,
                (
                    variant,
                    now,
                    result["attempts"],
                    hashlib.sha256(payload).hexdigest(),
                    str(exc),
                ),
            )
            connection.commit()
            query_results.append(
                {"source_variant": variant, "status": "failed", "error": str(exc)}
            )
            continue
        if len(candidates) >= max(1, max_captures_per_source):
            error = "candidate_limit_reached_requires_paginated_index_query"
            connection.execute(
                """
                INSERT INTO cdx_queries(
                  source_variant, queried_at, status, attempts,
                  response_sha256, candidate_count, error
                ) VALUES (?, ?, 'failed', ?, ?, ?, ?)
                ON CONFLICT(source_variant) DO UPDATE SET
                  queried_at = excluded.queried_at,
                  status = excluded.status,
                  attempts = excluded.attempts,
                  response_sha256 = excluded.response_sha256,
                  candidate_count = excluded.candidate_count,
                  error = excluded.error
                """,
                (
                    variant,
                    now,
                    result["attempts"],
                    hashlib.sha256(payload).hexdigest(),
                    len(candidates),
                    error,
                ),
            )
            connection.commit()
            query_results.append(
                {
                    "source_variant": variant,
                    "status": "failed",
                    "candidate_count": len(candidates),
                    "error": error,
                }
            )
            continue
        for candidate in candidates:
            connection.execute(
                """
                INSERT INTO archive_candidates(
                  candidate_key, source_variant, timestamp, original_url,
                  mimetype, statuscode, cdx_digest, cdx_length,
                  archive_url, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(candidate_key) DO NOTHING
                """,
                (
                    candidate["candidate_key"],
                    candidate["source_variant"],
                    candidate["timestamp"],
                    candidate["original_url"],
                    candidate["mimetype"],
                    candidate["statuscode"],
                    candidate["cdx_digest"],
                    candidate["cdx_length"],
                    candidate["archive_url"],
                    now,
                ),
            )
        connection.execute(
            """
            INSERT INTO cdx_queries(
              source_variant, queried_at, status, attempts,
              response_sha256, candidate_count, error
            ) VALUES (?, ?, 'ok', ?, ?, ?, NULL)
            ON CONFLICT(source_variant) DO UPDATE SET
              queried_at = excluded.queried_at,
              status = excluded.status,
              attempts = excluded.attempts,
              response_sha256 = excluded.response_sha256,
              candidate_count = excluded.candidate_count,
              error = NULL
            """,
            (
                variant,
                now,
                result["attempts"],
                hashlib.sha256(payload).hexdigest(),
                len(candidates),
            ),
        )
        connection.commit()
        query_results.append(
            {
                "source_variant": variant,
                "status": "ok",
                "candidate_count": len(candidates),
            }
        )
    return query_results


def canonical_endpoint_key(url: str) -> tuple[str, str, str]:
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    return host, parsed.path, parsed.query


def replay_candidates(
    connection: sqlite3.Connection,
    *,
    retry_failed: bool,
    timeout: int,
    attempts: int,
    max_document_bytes: int,
    user_agent: str,
) -> list[dict[str, Any]]:
    states = ["pending"] + (["failed"] if retry_failed else [])
    placeholders = ",".join("?" for _ in states)
    candidates = connection.execute(
        f"""
        SELECT * FROM archive_candidates
        WHERE state IN ({placeholders})
        ORDER BY timestamp, original_url
        """,
        states,
    ).fetchall()
    expected_by_endpoint: dict[tuple[str, str, str], list[sqlite3.Row]] = {}
    for target in connection.execute("SELECT * FROM targets"):
        expected_by_endpoint.setdefault(
            canonical_endpoint_key(str(target["source_url"])), []
        ).append(target)
    results: list[dict[str, Any]] = []
    for candidate in candidates:
        expected_targets = expected_by_endpoint.get(
            canonical_endpoint_key(str(candidate["original_url"])), []
        )
        if not expected_targets:
            continue
        result = request_bytes(
            str(candidate["archive_url"]),
            timeout=timeout,
            attempts=attempts,
            user_agent=user_agent,
            accept="*/*",
            max_bytes=max(1, max_document_bytes),
        )
        now = datetime.now(UTC).isoformat()
        if result["status"] != "downloaded":
            connection.execute(
                """
                UPDATE archive_candidates
                SET state = 'failed', attempts = attempts + ?, last_error = ?,
                    updated_at = ?
                WHERE candidate_key = ?
                """,
                (result["attempts"], result["error"], now, candidate["candidate_key"]),
            )
            connection.commit()
            results.append(
                {
                    "candidate_key": candidate["candidate_key"],
                    "status": "failed",
                    "error": result["error"],
                }
            )
            continue
        payload = result.pop("payload")
        downloaded_sha256 = hashlib.sha256(payload).hexdigest()
        downloaded_bytes = len(payload)
        exact_target_keys = sorted(
            str(target["target_key"])
            for target in expected_targets
            if target["expected_sha256"] == downloaded_sha256
            and target["expected_bytes"] == downloaded_bytes
        )
        state = "exact_match" if exact_target_keys else "rejected_mismatch"
        connection.execute(
            """
            UPDATE archive_candidates
            SET state = ?, attempts = attempts + ?, final_url = ?, http_status = ?,
                content_type = ?, downloaded_bytes = ?, downloaded_sha256 = ?,
                last_error = NULL, updated_at = ?
            WHERE candidate_key = ?
            """,
            (
                state,
                result["attempts"],
                result["final_url"],
                result["http_status"],
                result["content_type"],
                downloaded_bytes,
                downloaded_sha256,
                now,
                candidate["candidate_key"],
            ),
        )
        connection.commit()
        results.append(
            {
                "candidate_key": candidate["candidate_key"],
                "status": state,
                "downloaded_bytes": downloaded_bytes,
                "downloaded_sha256": downloaded_sha256,
                "exact_target_keys": exact_target_keys,
            }
        )
    return results


def build_manifest(
    connection: sqlite3.Connection,
    *,
    inventory_root: Path,
    manifest_out: Path,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if manifest_out.is_file():
        for line_number, line in enumerate(
            manifest_out.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise WaybackRecoveryError(
                    f"invalid existing archive manifest at line {line_number}"
                ) from exc
            capture = item.get("capture")
            archive = item.get("archive_evidence")
            if (
                item.get("schema_version") != "wayback_document_lineage_v1"
                or item.get("capture_status") != "checksum_capture_present"
                or item.get("candidate_acceptance")
                != "accepted_only_after_archive_exact_byte_match"
                or item.get("guessed_source_urls_accepted") is not False
                or item.get("synthetic_or_mock_records_counted") is not False
                or item.get("public_domain_personal_information_retained") is not True
                or item.get("remote_mutation_performed") is not False
                or not isinstance(capture, dict)
                or not isinstance(archive, dict)
                or capture.get("sha256") != archive.get("downloaded_sha256")
                or capture.get("bytes") != archive.get("downloaded_bytes")
            ):
                raise WaybackRecoveryError(
                    f"invalid existing archive evidence at line {line_number}"
                )
            capture_path = str(capture.get("path") or "").removeprefix("etl/data/raw/")
            local_path = (inventory_root / capture_path).resolve()
            try:
                local_path.relative_to(inventory_root.resolve())
            except ValueError as exc:
                raise WaybackRecoveryError(
                    f"existing archive capture escapes inventory at line {line_number}"
                ) from exc
            if (
                not local_path.is_file()
                or local_path.stat().st_size != capture.get("bytes")
                or sha256_file(local_path) != capture.get("sha256")
            ):
                raise WaybackRecoveryError(
                    f"existing archive capture changed at line {line_number}"
                )
            rows.append(item)
    verified_at = datetime.now(UTC).isoformat()
    matches = connection.execute(
        """
        SELECT * FROM archive_candidates
        WHERE state = 'exact_match'
        ORDER BY timestamp, original_url
        """
    ).fetchall()
    for candidate in matches:
        endpoint = canonical_endpoint_key(str(candidate["original_url"]))
        targets = [
            target
            for target in connection.execute("SELECT * FROM targets")
            if canonical_endpoint_key(str(target["source_url"])) == endpoint
            and target["expected_sha256"] == candidate["downloaded_sha256"]
            and target["expected_bytes"] == candidate["downloaded_bytes"]
        ]
        for target in targets:
            paths = connection.execute(
                """
                SELECT capture_path FROM target_paths
                WHERE target_key = ? ORDER BY capture_path
                """,
                (target["target_key"],),
            ).fetchall()
            for path_row in paths:
                capture_path = str(path_row["capture_path"])
                local_path = inventory_root / capture_path
                if (
                    not local_path.is_file()
                    or local_path.stat().st_size != target["expected_bytes"]
                    or sha256_file(local_path) != target["expected_sha256"]
                ):
                    raise WaybackRecoveryError(
                        f"archive manifest capture changed: {capture_path}"
                    )
                rows.append(
                    {
                        "schema_version": "wayback_document_lineage_v1",
                        "capture_status": "checksum_capture_present",
                        "capture": {
                            "path": f"etl/data/raw/{capture_path}",
                            "bytes": target["expected_bytes"],
                            "sha256": target["expected_sha256"],
                        },
                        "source_id": target["source_id"],
                        "source_url": target["source_url"],
                        "archive_evidence": {
                            "index_endpoint": CDX_ENDPOINT,
                            "timestamp": candidate["timestamp"],
                            "original_url": candidate["original_url"],
                            "cdx_digest": candidate["cdx_digest"],
                            "cdx_mimetype": candidate["mimetype"],
                            "archive_url": candidate["archive_url"],
                            "retrieved_at": candidate["updated_at"],
                            "final_url": candidate["final_url"],
                            "http_status": candidate["http_status"],
                            "content_type": candidate["content_type"],
                            "downloaded_bytes": candidate["downloaded_bytes"],
                            "downloaded_sha256": candidate["downloaded_sha256"],
                        },
                        "candidate_acceptance": (
                            "accepted_only_after_archive_exact_byte_match"
                        ),
                        "verified_at": verified_at,
                        "guessed_source_urls_accepted": False,
                        "public_domain_personal_information_retained": True,
                        "synthetic_or_mock_records_counted": False,
                        "remote_mutation_performed": False,
                    }
                )
    deduplicated = {
        (item["capture"]["path"], item["source_url"]): item for item in rows
    }
    output = [deduplicated[key] for key in sorted(deduplicated)]
    atomic_write_text(
        manifest_out,
        "".join(
            json.dumps(item, ensure_ascii=True, sort_keys=True) + "\n"
            for item in output
        ),
    )
    return output


def export_checkpoint(
    connection: sqlite3.Connection, checkpoint_out: Path
) -> int:
    rows: list[dict[str, Any]] = []
    record_queries = (
        ("metadata", "SELECT * FROM metadata ORDER BY key"),
        ("target", "SELECT * FROM targets ORDER BY target_key"),
        (
            "target_path",
            "SELECT * FROM target_paths ORDER BY target_key, capture_path",
        ),
        ("cdx_query", "SELECT * FROM cdx_queries ORDER BY source_variant"),
        (
            "archive_candidate",
            "SELECT * FROM archive_candidates ORDER BY timestamp, original_url",
        ),
    )
    for record_type, query in record_queries:
        for item in connection.execute(query):
            rows.append(
                {
                    "schema_version": "wayback_document_checkpoint_v1",
                    "record_type": record_type,
                    **dict(item),
                    "public_domain_personal_information_retained": True,
                    "synthetic_or_mock_records_counted": False,
                    "remote_mutation_performed": False,
                }
            )
    atomic_write_text(
        checkpoint_out,
        "".join(
            json.dumps(item, ensure_ascii=True, sort_keys=True) + "\n"
            for item in rows
        ),
    )
    return len(rows)


def recover(
    *,
    inventory_root: Path,
    inventory_manifest_path: Path,
    gap_queue_path: Path,
    state_path: Path,
    manifest_out: Path,
    report_out: Path,
    checkpoint_out: Path,
    timeout: int,
    attempts: int,
    max_document_bytes: int,
    max_captures_per_source: int,
    user_agent: str,
    refresh_index: bool,
    retry_failed: bool,
    no_network: bool,
) -> dict[str, Any]:
    inventory = load_inventory(inventory_manifest_path)
    targets = load_targets(
        gap_queue_path, inventory=inventory, inventory_root=inventory_root
    )
    now = datetime.now(UTC).isoformat()
    connection = open_state(state_path)
    try:
        sync_targets(connection, targets, now=now)
        source_urls = sorted({item["source_url"] for item in targets})
        if no_network:
            query_results = []
            variants = sorted(
                {variant for url in source_urls for variant in source_url_variants(url)}
            )
            for variant in variants:
                prior = connection.execute(
                    "SELECT status, candidate_count, error FROM cdx_queries "
                    "WHERE source_variant = ?",
                    (variant,),
                ).fetchone()
                if prior is None:
                    query_results.append(
                        {
                            "source_variant": variant,
                            "status": "not_queried_no_network",
                        }
                    )
                elif prior["status"] == "ok":
                    query_results.append(
                        {
                            "source_variant": variant,
                            "status": "checkpoint_reused",
                            "candidate_count": prior["candidate_count"],
                        }
                    )
                else:
                    query_results.append(
                        {
                            "source_variant": variant,
                            "status": "failed_checkpoint_reused",
                            "error": prior["error"],
                        }
                    )
            replay_results = []
        else:
            query_results = query_indexes(
                connection,
                source_urls,
                refresh_index=refresh_index,
                retry_failed=retry_failed,
                timeout=max(1, timeout),
                attempts=max(1, attempts),
                max_captures_per_source=max(1, max_captures_per_source),
                user_agent=user_agent,
            )
            replay_results = replay_candidates(
                connection,
                retry_failed=retry_failed,
                timeout=max(1, timeout),
                attempts=max(1, attempts),
                max_document_bytes=max(1, max_document_bytes),
                user_agent=user_agent,
            )
        manifest_rows = build_manifest(
            connection,
            inventory_root=inventory_root,
            manifest_out=manifest_out,
        )
        checkpoint_rows = export_checkpoint(connection, checkpoint_out)
        state_counts = {
            str(row["state"]): int(row["rows"])
            for row in connection.execute(
                """
                SELECT state, COUNT(*) AS rows
                FROM archive_candidates GROUP BY state ORDER BY state
                """
            )
        }
        cdx_counts = {
            str(row["status"]): int(row["rows"])
            for row in connection.execute(
                """
                SELECT status, COUNT(*) AS rows
                FROM cdx_queries GROUP BY status ORDER BY status
                """
            )
        }
        unique_targets = int(
            connection.execute("SELECT COUNT(*) FROM targets").fetchone()[0]
        )
        candidate_rows = int(
            connection.execute("SELECT COUNT(*) FROM archive_candidates").fetchone()[0]
        )
    finally:
        connection.close()
    recovered_paths = {str(item["capture"]["path"]) for item in manifest_rows}
    total_gap_rows = sum(
        bool(line.strip())
        for line in gap_queue_path.read_text(encoding="utf-8").splitlines()
    )
    replay_failures = sum(item["status"] == "failed" for item in replay_results)
    unqueried_no_network = sum(
        item["status"] == "not_queried_no_network" for item in query_results
    )
    report: dict[str, Any] = {
        "schema_version": "wayback_document_lineage_report_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": (
            "partial"
            if cdx_counts.get("failed", 0)
            or state_counts.get("failed", 0)
            or replay_failures
            or unqueried_no_network
            else "ok"
        ),
        "policy": {
            "official_real_files_only": True,
            "source_urls_must_be_repository_evidence_derived": True,
            "archive_queries_use_exact_url_scope_only": True,
            "archive_bytes_must_match_local_sha256_and_size": True,
            "archive_mismatches_are_rejected_and_checkpointed": True,
            "archive_index_cap_is_fail_closed": True,
            "successful_index_queries_are_not_repeated_without_refresh": True,
            "portable_checkpoint_exported": True,
            "checkpoint_only_reconciliation_supported": True,
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
        },
        "state": {
            "path": display_path(state_path),
            "schema_version": STATE_SCHEMA_VERSION,
            "sha256": sha256_file(state_path),
            "candidate_states": state_counts,
            "cdx_query_states": cdx_counts,
        },
        "checkpoint": {
            "path": display_path(checkpoint_out),
            "rows": checkpoint_rows,
            "bytes": checkpoint_out.stat().st_size,
            "sha256": sha256_file(checkpoint_out),
        },
        "execution": {
            "timeout_seconds": max(1, timeout),
            "attempts": max(1, attempts),
            "max_document_bytes": max(1, max_document_bytes),
            "max_captures_per_source": max(1, max_captures_per_source),
            "refresh_index": refresh_index,
            "retry_failed": retry_failed,
            "no_network": no_network,
            "network_requests_performed": 0 if no_network else None,
            "cdx_endpoint": CDX_ENDPOINT,
            "replay_modifier": "id_",
        },
        "totals": {
            "eligible_gap_file_instances": len(targets),
            "unique_expected_content_targets": unique_targets,
            "evidence_derived_source_urls": len(
                {item["source_url"] for item in targets}
            ),
            "unseeded_gap_file_instances": max(0, total_gap_rows - len(targets)),
            "archive_candidates_indexed": candidate_rows,
            "archive_candidates_attempted_this_run": len(replay_results),
            "archive_candidates_rejected_this_run": sum(
                item["status"] == "rejected_mismatch" for item in replay_results
            ),
            "archive_candidate_failures_this_run": replay_failures,
            "source_variants_not_queried_no_network": unqueried_no_network,
            "exact_archive_relations": len(manifest_rows),
            "exact_archive_files_recovered": len(recovered_paths),
        },
        "checks": {
            "every_target_is_real_and_checksum_verified": True,
            "only_evidence_derived_exact_source_urls_queried": True,
            "nonmatching_archive_responses_not_promoted": (
                len(manifest_rows) == len(recovered_paths)
            ),
            "manifest_rows_are_checksum_exact": True,
            "no_guessed_source_url_accepted": True,
            "public_domain_personal_information_retained": True,
            "no_remote_mutation_performed": True,
            "no_network_mode_performed_zero_requests": (
                not no_network
                or (not replay_results and all(
                    item["status"]
                    in {
                        "checkpoint_reused",
                        "failed_checkpoint_reused",
                        "not_queried_no_network",
                    }
                    for item in query_results
                ))
            ),
        },
        "index_queries": query_results,
        "replay_results": replay_results,
        "manifest": {
            "path": display_path(manifest_out),
            "rows": len(manifest_rows),
            "bytes": manifest_out.stat().st_size,
            "sha256": sha256_file(manifest_out),
        },
        "next_action": (
            "If no exact match exists, retain the gap. Refresh the archive index only "
            "after a new archived capture or exact source manifest becomes available."
        ),
    }
    atomic_write_text(
        report_out,
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.no_network and (args.refresh_index or args.retry_failed):
            raise WaybackRecoveryError(
                "--no-network cannot be combined with --refresh-index or --retry-failed"
            )
        report = recover(
            inventory_root=safe_repo_path(args.inventory_root),
            inventory_manifest_path=safe_repo_path(args.inventory_manifest),
            gap_queue_path=safe_repo_path(args.gap_queue),
            state_path=safe_repo_path(args.state),
            manifest_out=safe_repo_path(args.manifest_out),
            report_out=safe_repo_path(args.report_out),
            checkpoint_out=safe_repo_path(args.checkpoint_out),
            timeout=args.timeout,
            attempts=args.attempts,
            max_document_bytes=args.max_document_bytes,
            max_captures_per_source=args.max_captures_per_source,
            user_agent=args.user_agent,
            refresh_index=args.refresh_index,
            retry_failed=args.retry_failed,
            no_network=args.no_network,
        )
    except (OSError, sqlite3.DatabaseError, ValueError, WaybackRecoveryError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    if args.enforce and (
        report["status"] not in {"ok", "partial"} or not all(report["checks"].values())
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
