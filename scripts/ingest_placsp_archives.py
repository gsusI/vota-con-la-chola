#!/usr/bin/env python3
"""Durable, bounded-memory ingestion for official PLACSP archive corpora."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import shutil
import sqlite3
import sys
import urllib.error
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, BinaryIO

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.politicos_es.db import apply_schema, finish_run, seed_sources, start_run
from publicdata_connectors_es.money.placsp_bulk import (
    DEFAULT_MAX_ARCHIVE_BYTES,
    DEFAULT_MAX_ARCHIVE_MEMBERS,
    DEFAULT_MAX_COMPRESSION_RATIO,
    DEFAULT_MAX_DOCUMENTS_PER_RECORD,
    DEFAULT_MAX_MEMBER_BYTES,
    DEFAULT_MAX_RECORDS_PER_MEMBER,
    DEFAULT_MAX_TOTAL_UNCOMPRESSED_BYTES,
    PlacspAtomRecord,
    compact_record_payload,
    inspect_placsp_archive,
    iter_placsp_atom_records,
)
from publicdata_connectors_es.money.placsp_catalog import (
    DEFAULT_CATALOG_URL,
    DEFAULT_MAX_CATALOG_BYTES,
    DEFAULT_START_YEAR,
    discover_catalog,
)
from publicdata_core.blobstore import StoredBlob, download_to_content_addressed_store
from publicdata_core.util import now_utc_iso, stable_json
from publicdata_ops import (
    claim_work_items,
    complete_work_items,
    enqueue_work_items,
    ensure_work_queue_schema,
    fail_work_items,
    heartbeat_work_items,
    work_queue_observability,
)
from publicdata_sqlite import open_db, upsert_source_records_with_content_sha256

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_SCHEMA = Path("etl/load/sqlite_schema.sql")
DEFAULT_RAW_ROOT = Path("etl/data/object-origin/placsp-contracts")
DEFAULT_PIPELINE = "placsp_contract_archives"
DEFAULT_MIN_FREE_BYTES = 10 * 1024 * 1024 * 1024
SOURCE_ID = "placsp_sindicacion"


@dataclass(frozen=True)
class ArchiveOutcome:
    work_item_id: int
    stored: StoredBlob | None
    error: str | None
    retryable: bool


class _HashingReader:
    def __init__(self, stream: BinaryIO) -> None:
        self._stream = stream
        self._digest = hashlib.sha256()

    def read(self, size: int = -1) -> bytes:
        value = self._stream.read(size)
        if value:
            self._digest.update(value)
        return value

    @property
    def content_sha256(self) -> str:
        return self._digest.hexdigest()


def _peak_rss_mb() -> float:
    raw = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return raw / (1024.0 * 1024.0) if sys.platform == "darwin" else raw / 1024.0


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return path.name


def _storage_preflight(
    path: Path,
    *,
    min_free_bytes: int,
    reserve_bytes: int,
) -> dict[str, Any]:
    if min_free_bytes < 0:
        raise ValueError("min_free_bytes must be nonnegative")
    if reserve_bytes < 0:
        raise ValueError("reserve_bytes must be nonnegative")
    path.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(path)
    required_free_bytes = min_free_bytes + reserve_bytes
    free_after_reserve = int(usage.free) - reserve_bytes
    return {
        "schema_version": "storage_capacity_preflight_v1",
        "path": _display_path(path),
        "total_bytes": int(usage.total),
        "used_bytes": int(usage.used),
        "free_bytes": int(usage.free),
        "min_free_bytes": min_free_bytes,
        "reserve_bytes": reserve_bytes,
        "required_free_bytes": required_free_bytes,
        "free_after_reserve_bytes": free_after_reserve,
        "headroom_bytes": int(usage.free) - required_free_bytes,
        "ready": int(usage.free) >= required_free_bytes,
    }


def _sqlite_storage_path(conn: sqlite3.Connection) -> Path:
    for row in conn.execute("PRAGMA database_list").fetchall():
        if str(row[1]) == "main" and str(row[2] or "").strip():
            return Path(str(row[2])).resolve().parent
    return Path.cwd()


def _runtime_path(raw_path: str) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else REPO_ROOT / path


def _write_report(path: str, payload: Mapping[str, object]) -> None:
    if not str(path or "").strip():
        return
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _open_runtime(db_path: Path, schema_path: Path) -> sqlite3.Connection:
    conn = open_db(db_path)
    apply_schema(conn, schema_path)
    seed_sources(conn)
    ensure_work_queue_schema(conn)
    return conn


def _archive_pipeline(pipeline_id: str) -> str:
    return f"{pipeline_id}:archives"


def _member_pipeline(pipeline_id: str) -> str:
    return f"{pipeline_id}:members"


def _bulk_run(conn: sqlite3.Connection, pipeline_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM placsp_bulk_runs WHERE pipeline_id = ?",
        (pipeline_id,),
    ).fetchone()


def _parse_archive_specs(values: Sequence[str]) -> list[tuple[str, str]]:
    parsed: list[tuple[str, str]] = []
    seen_periods: set[str] = set()
    seen_urls: set[str] = set()
    for raw in values:
        period, separator, source_url = str(raw).partition("=")
        period = period.strip()
        source_url = source_url.strip()
        if separator != "=" or len(period) not in {4, 6, 8} or not period.isdigit():
            raise ValueError("archive must use PERIOD=https://... syntax")
        if not source_url.startswith("https://"):
            raise ValueError("PLACSP archive URL must use HTTPS")
        if period in seen_periods or source_url in seen_urls:
            raise ValueError("duplicate PLACSP archive period or URL")
        seen_periods.add(period)
        seen_urls.add(source_url)
        parsed.append((period, source_url))
    if not parsed:
        raise ValueError("at least one --archive is required")
    return sorted(parsed)


def _parse_archive_report(path: Path) -> list[tuple[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("status") != "ok":
        raise ValueError("PLACSP archive report status must be ok")
    rows = payload.get("archives")
    if not isinstance(rows, list) or not rows:
        raise ValueError("PLACSP archive report must contain archives")
    if any(
        not isinstance(row, dict) or "period" not in row or "source_url" not in row
        for row in rows
    ):
        raise ValueError("PLACSP archive report contains an invalid archive row")
    return _parse_archive_specs(
        [f"{row['period']}={row['source_url']}" for row in rows]
    )


def _archive_contract_sha256(archives: Sequence[tuple[str, str]]) -> str:
    return hashlib.sha256(
        stable_json(
            [
                {"period": period, "source_url": source_url}
                for period, source_url in archives
            ]
        ).encode()
    ).hexdigest()


def _queued_archive_specs(rows: Sequence[sqlite3.Row]) -> list[tuple[str, str]]:
    parsed: list[tuple[str, str]] = []
    for row in rows:
        payload = json.loads(str(row["payload_json"]))
        parsed.append((str(payload["period"]), str(payload["source_url"])))
    return sorted(parsed)


def enqueue_archives(
    conn: sqlite3.Connection,
    *,
    pipeline_id: str,
    snapshot_date: str,
    archives: Sequence[tuple[str, str]],
) -> dict[str, Any]:
    existing = _bulk_run(conn, pipeline_id)
    now_iso = now_utc_iso()
    contract_sha256 = _archive_contract_sha256(archives)
    if existing is None:
        ingestion_run_id = start_run(conn, SOURCE_ID, archives[0][1])
        row = conn.execute(
            """
            INSERT INTO placsp_bulk_runs (
              pipeline_id, ingestion_run_id, source_id, snapshot_date,
              archives_enqueued, archive_contract_sha256,
              state, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'running', ?, ?)
            RETURNING placsp_bulk_run_id
            """,
            (
                pipeline_id,
                ingestion_run_id,
                SOURCE_ID,
                snapshot_date,
                len(archives),
                contract_sha256,
                now_iso,
                now_iso,
            ),
        ).fetchone()
        bulk_run_id = int(row["placsp_bulk_run_id"])
        conn.commit()
    else:
        if str(existing["snapshot_date"]) != snapshot_date or int(
            existing["archives_enqueued"]
        ) != len(archives):
            raise RuntimeError("pipeline_id already has a different archive contract")
        existing_contract = str(existing["archive_contract_sha256"] or "")
        if existing_contract and existing_contract != contract_sha256:
            raise RuntimeError("pipeline_id already has a different archive contract")
        if not existing_contract:
            queue_rows = conn.execute(
                """
                SELECT payload_json
                FROM pipeline_work_items
                WHERE pipeline_id = ?
                ORDER BY item_key
                """,
                (_archive_pipeline(pipeline_id),),
            ).fetchall()
            queued_archives = _queued_archive_specs(queue_rows)
            if queued_archives != list(archives):
                raise RuntimeError(
                    "pipeline_id already has a different archive contract"
                )
            conn.execute(
                """
                UPDATE placsp_bulk_runs
                SET archive_contract_sha256 = ?, updated_at = ?
                WHERE placsp_bulk_run_id = ?
                """,
                (contract_sha256, now_iso, int(existing["placsp_bulk_run_id"])),
            )
            conn.commit()
        bulk_run_id = int(existing["placsp_bulk_run_id"])

    queue = enqueue_work_items(
        conn,
        pipeline_id=_archive_pipeline(pipeline_id),
        items=(
            {
                "item_key": f"archive:{period}",
                "partition_key": f"period:{period[:4]}",
                "payload": {
                    "placsp_bulk_run_id": bulk_run_id,
                    "period": period,
                    "snapshot_date": snapshot_date,
                    "source_url": source_url,
                },
                "max_attempts": 4,
            }
            for period, source_url in archives
        ),
    )
    return {
        "schema_version": "placsp_bulk_enqueue_v1",
        "status": "ok",
        "source_id": SOURCE_ID,
        "pipeline_id": pipeline_id,
        "placsp_bulk_run_id": bulk_run_id,
        "snapshot_date": snapshot_date,
        "archive_contract_sha256": contract_sha256,
        "archives": [{"period": period, "source_url": url} for period, url in archives],
        "archive_queue": queue,
        "archive_queue_status": work_queue_observability(
            conn,
            pipeline_id=_archive_pipeline(pipeline_id),
            top_limit=10,
        ),
        "peak_rss_mb": round(_peak_rss_mb(), 3),
    }


def _download_archive(
    conn: sqlite3.Connection,
    *,
    item: Mapping[str, object],
    worker_id: str,
    raw_root: Path,
    timeout: int,
    max_archive_bytes: int,
    download_attempts: int,
    lease_seconds: int,
    ca_bundle: Path | None,
) -> ArchiveOutcome:
    work_item_id = int(item["work_item_id"])
    payload = dict(item.get("payload") or {})
    try:
        stored = download_to_content_addressed_store(
            str(payload["source_url"]),
            store_root=raw_root,
            timeout=timeout,
            max_bytes=max_archive_bytes,
            max_attempts=download_attempts,
            ca_bundle=ca_bundle,
            headers={"Accept": "application/zip,application/octet-stream,*/*"},
            progress_callback=lambda: heartbeat_work_items(
                conn,
                worker_id=worker_id,
                work_item_ids=[work_item_id],
                lease_seconds=lease_seconds,
            ),
        )
        return ArchiveOutcome(work_item_id, stored, None, True)
    except Exception as exc:  # noqa: BLE001
        retryable = not (
            isinstance(exc, urllib.error.HTTPError)
            and exc.code in {400, 404, 410, 413, 414, 415, 422}
        )
        if "exceeds max_bytes" in str(exc):
            retryable = False
        return ArchiveOutcome(
            work_item_id,
            None,
            f"{type(exc).__name__}: {exc}"[:2_000],
            retryable,
        )


def _persist_archive(
    conn: sqlite3.Connection,
    *,
    pipeline_id: str,
    item: Mapping[str, object],
    stored: StoredBlob,
    transport_security: str,
    max_members: int,
    max_total_uncompressed_bytes: int,
    max_member_bytes: int,
    max_compression_ratio: float,
) -> int:
    payload = dict(item.get("payload") or {})
    inspection = inspect_placsp_archive(
        stored.path,
        max_archive_bytes=stored.bytes,
        max_members=max_members,
        max_total_uncompressed_bytes=max_total_uncompressed_bytes,
        max_member_bytes=max_member_bytes,
        max_compression_ratio=max_compression_ratio,
    )
    now_iso = now_utc_iso()
    conn.execute(
        """
        INSERT INTO placsp_bulk_archives (
          placsp_bulk_run_id, work_item_id, period, source_url,
          transport_security, fetched_at, content_sha256, bytes, raw_path,
          members_total, uncompressed_bytes, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ok', ?, ?)
        ON CONFLICT(placsp_bulk_run_id, source_url) DO UPDATE SET
          work_item_id=excluded.work_item_id,
          transport_security=excluded.transport_security,
          fetched_at=excluded.fetched_at,
          content_sha256=excluded.content_sha256,
          bytes=excluded.bytes,
          raw_path=excluded.raw_path,
          members_total=excluded.members_total,
          uncompressed_bytes=excluded.uncompressed_bytes,
          status='ok', error=NULL, updated_at=excluded.updated_at
        """,
        (
            int(payload["placsp_bulk_run_id"]),
            int(item["work_item_id"]),
            str(payload["period"]),
            str(payload["source_url"]),
            transport_security,
            now_iso,
            stored.content_sha256,
            stored.bytes,
            _display_path(stored.path),
            len(inspection.members),
            inspection.uncompressed_bytes,
            now_iso,
            now_iso,
        ),
    )
    archive_row = conn.execute(
        """
        SELECT placsp_bulk_archive_id
        FROM placsp_bulk_archives
        WHERE placsp_bulk_run_id = ? AND source_url = ?
        """,
        (int(payload["placsp_bulk_run_id"]), str(payload["source_url"])),
    ).fetchone()
    if archive_row is None:
        raise RuntimeError("missing persisted PLACSP archive")
    archive_id = int(archive_row[0])
    conn.executemany(
        """
        INSERT INTO placsp_bulk_members (
          placsp_bulk_archive_id, member_name, crc32, compressed_bytes,
          uncompressed_bytes, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
        ON CONFLICT(placsp_bulk_archive_id, member_name) DO UPDATE SET
          crc32=excluded.crc32,
          compressed_bytes=excluded.compressed_bytes,
          uncompressed_bytes=excluded.uncompressed_bytes,
          updated_at=excluded.updated_at
        """,
        [
            (
                archive_id,
                member.member_name,
                member.crc32,
                member.compressed_bytes,
                member.uncompressed_bytes,
                now_iso,
                now_iso,
            )
            for member in inspection.members
        ],
    )
    member_rows = conn.execute(
        """
        SELECT placsp_bulk_member_id, member_name
        FROM placsp_bulk_members
        WHERE placsp_bulk_archive_id = ?
        ORDER BY placsp_bulk_member_id
        """,
        (archive_id,),
    ).fetchall()
    conn.commit()
    enqueue_work_items(
        conn,
        pipeline_id=_member_pipeline(pipeline_id),
        items=(
            {
                "item_key": f"member:{archive_id}:{int(row['placsp_bulk_member_id'])}",
                "partition_key": f"archive:{archive_id}",
                "payload": {
                    "placsp_bulk_run_id": int(payload["placsp_bulk_run_id"]),
                    "placsp_bulk_archive_id": archive_id,
                    "placsp_bulk_member_id": int(row["placsp_bulk_member_id"]),
                    "member_name": str(row["member_name"]),
                    "raw_path": _display_path(stored.path),
                    "snapshot_date": str(payload["snapshot_date"]),
                },
                "max_attempts": 4,
            }
            for row in member_rows
        ),
    )
    return len(member_rows)


def run_archive_worker(
    conn: sqlite3.Connection,
    *,
    pipeline_id: str,
    worker_id: str,
    raw_root: Path,
    max_items: int,
    lease_seconds: int,
    timeout: int,
    max_archive_bytes: int,
    max_members: int,
    max_total_uncompressed_bytes: int,
    max_member_bytes: int,
    max_compression_ratio: float,
    min_free_bytes: int,
    download_attempts: int,
    retry_delay_seconds: int,
    ca_bundle: Path | None,
) -> dict[str, Any]:
    processed = succeeded = failed = members_enqueued = 0
    blocked_storage = False
    stop_reason = "queue_drained"
    storage_preflight: dict[str, Any] | None = None
    while max_items <= 0 or processed < max_items:
        queue_before_claim = work_queue_observability(
            conn, pipeline_id=_archive_pipeline(pipeline_id), top_limit=1
        )
        if int(queue_before_claim["unfinished_total"]) == 0:
            break
        storage_preflight = _storage_preflight(
            raw_root,
            min_free_bytes=min_free_bytes,
            reserve_bytes=max_archive_bytes,
        )
        if not storage_preflight["ready"]:
            blocked_storage = True
            stop_reason = "insufficient_free_space"
            break
        claimed = claim_work_items(
            conn,
            pipeline_id=_archive_pipeline(pipeline_id),
            worker_id=worker_id,
            limit=1,
            lease_seconds=lease_seconds,
        )
        if not claimed:
            stop_reason = "no_claimable_items"
            break
        item = claimed[0]
        outcome = _download_archive(
            conn,
            item=item,
            worker_id=worker_id,
            raw_root=raw_root,
            timeout=timeout,
            max_archive_bytes=max_archive_bytes,
            download_attempts=download_attempts,
            lease_seconds=lease_seconds,
            ca_bundle=ca_bundle,
        )
        processed += 1
        if outcome.error is not None or outcome.stored is None:
            failed += 1
            fail_work_items(
                conn,
                worker_id=worker_id,
                work_item_ids=[outcome.work_item_id],
                error=outcome.error or "archive download failed",
                retry_delay_seconds=retry_delay_seconds,
                retryable=outcome.retryable,
            )
            continue
        try:
            members_enqueued += _persist_archive(
                conn,
                pipeline_id=pipeline_id,
                item=item,
                stored=outcome.stored,
                transport_security=(
                    "verified_custom_ca"
                    if ca_bundle is not None
                    else "verified_system_ca"
                ),
                max_members=max_members,
                max_total_uncompressed_bytes=max_total_uncompressed_bytes,
                max_member_bytes=max_member_bytes,
                max_compression_ratio=max_compression_ratio,
            )
            if (
                complete_work_items(
                    conn,
                    worker_id=worker_id,
                    work_item_ids=[outcome.work_item_id],
                )
                != 1
            ):
                raise RuntimeError("lost archive lease before completion")
            succeeded += 1
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            failed += 1
            fail_work_items(
                conn,
                worker_id=worker_id,
                work_item_ids=[outcome.work_item_id],
                error=f"archive_persist_error: {type(exc).__name__}: {exc}",
                retry_delay_seconds=retry_delay_seconds,
                retryable=False,
            )
    if not blocked_storage and max_items > 0 and processed >= max_items:
        stop_reason = "max_items_reached"
    return {
        "schema_version": "placsp_archive_worker_v2",
        "status": (
            "blocked_storage" if blocked_storage else "ok" if failed == 0 else "partial"
        ),
        "pipeline_id": pipeline_id,
        "worker_id": worker_id,
        "stop_reason": stop_reason,
        "processed": processed,
        "succeeded": succeeded,
        "failed_attempts": failed,
        "members_enqueued": members_enqueued,
        "archive_queue": work_queue_observability(
            conn, pipeline_id=_archive_pipeline(pipeline_id), top_limit=10
        ),
        "member_queue": work_queue_observability(
            conn, pipeline_id=_member_pipeline(pipeline_id), top_limit=10
        ),
        "storage_preflight": storage_preflight,
        "peak_rss_mb": round(_peak_rss_mb(), 3),
    }


def _as_float(value: object) -> float | None:
    return float(Decimal(str(value))) if value is not None else None


def _persist_member_records(
    conn: sqlite3.Connection,
    *,
    item: Mapping[str, object],
    records: Sequence[PlacspAtomRecord],
    member_content_sha256: str,
) -> None:
    payload = dict(item.get("payload") or {})
    now_iso = now_utc_iso()
    source_rows = [
        {
            "source_record_id": record.source_record_id,
            "raw_payload": compact_record_payload(record),
            "content_sha256": record.entry_content_sha256,
        }
        for record in records
    ]
    pk_map = upsert_source_records_with_content_sha256(
        conn,
        source_id=SOURCE_ID,
        rows=source_rows,
        snapshot_date=str(payload["snapshot_date"]),
        now_iso=now_iso,
    )
    contract_rows: list[tuple[object, ...]] = []
    award_rows: list[tuple[object, ...]] = []
    document_rows: list[tuple[object, ...]] = []
    sighting_rows: list[tuple[object, ...]] = []
    for ordinal, parsed in enumerate(records):
        record = parsed.record
        source_record_pk = pk_map.get(parsed.source_record_id)
        if source_record_pk is None:
            raise RuntimeError(f"missing source record PK: {parsed.source_record_id}")
        award_dates = sorted(
            str(award["award_date"])
            for award in parsed.awards
            if award.get("award_date")
        )
        contract_rows.append(
            (
                SOURCE_ID,
                source_record_pk,
                parsed.source_record_id,
                str(payload["snapshot_date"]),
                record.get("source_url"),
                record.get("contract_id"),
                record.get("notice_type"),
                record.get("cpv_code"),
                record.get("contracting_authority"),
                record.get("procedure_type"),
                record.get("territory_code"),
                record.get("published_date"),
                award_dates[-1] if award_dates else None,
                _as_float(record.get("amount_eur_decimal")),
                record.get("amount_eur_decimal"),
                record.get("amount_semantics"),
                record.get("currency"),
                parsed.stable_contract_id,
                record.get("entry_updated_at"),
                record.get("contract_status_code"),
                record.get("authority_identifier"),
                stable_json(
                    {
                        "lineage": "source_records.raw_payload",
                        "tombstone": parsed.tombstone,
                    }
                ),
                now_iso,
                now_iso,
            )
        )
        for award in parsed.awards:
            award_rows.append(
                (
                    SOURCE_ID,
                    source_record_pk,
                    parsed.source_record_id,
                    parsed.stable_contract_id,
                    award["award_ordinal"],
                    award.get("lot_id"),
                    award.get("result_code"),
                    award.get("result_description"),
                    award.get("award_date"),
                    award.get("received_tender_quantity"),
                    award.get("supplier_name"),
                    award.get("supplier_identifier"),
                    award.get("supplier_identifier_scheme"),
                    award.get("amount_eur_decimal"),
                    award.get("payable_amount_eur_decimal"),
                    award.get("currency"),
                    stable_json({"lineage": "source_records.raw_payload"}),
                    now_iso,
                    now_iso,
                )
            )
        for document in parsed.documents:
            document_rows.append(
                (
                    SOURCE_ID,
                    source_record_pk,
                    parsed.source_record_id,
                    parsed.stable_contract_id,
                    document["document_ordinal"],
                    document.get("document_kind"),
                    document.get("document_label"),
                    document["source_url"],
                    document.get("official_document_hash"),
                    stable_json({"lineage": "source_records.raw_payload"}),
                    now_iso,
                    now_iso,
                )
            )
        sighting_rows.append(
            (
                int(payload["placsp_bulk_run_id"]),
                int(payload["placsp_bulk_member_id"]),
                SOURCE_ID,
                source_record_pk,
                parsed.source_record_id,
                parsed.stable_contract_id,
                parsed.entry_content_sha256,
                ordinal,
                now_iso,
            )
        )

    conn.executemany(
        """
        INSERT INTO money_contract_records (
          source_id, source_record_pk, source_record_id, source_snapshot_date,
          source_url, contract_id, notice_type, cpv_code, contracting_authority,
          procedure_type, territory_code, published_date, awarded_date,
          amount_eur, amount_eur_decimal, amount_semantics, currency,
          stable_contract_id, entry_updated_at, contract_status_code,
          authority_identifier, raw_payload, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, source_record_pk) DO UPDATE SET
          source_snapshot_date=excluded.source_snapshot_date,
          source_url=excluded.source_url,
          contract_id=excluded.contract_id,
          notice_type=excluded.notice_type,
          cpv_code=excluded.cpv_code,
          contracting_authority=excluded.contracting_authority,
          procedure_type=excluded.procedure_type,
          territory_code=excluded.territory_code,
          published_date=excluded.published_date,
          awarded_date=excluded.awarded_date,
          amount_eur=excluded.amount_eur,
          amount_eur_decimal=excluded.amount_eur_decimal,
          amount_semantics=excluded.amount_semantics,
          currency=excluded.currency,
          stable_contract_id=excluded.stable_contract_id,
          entry_updated_at=excluded.entry_updated_at,
          contract_status_code=excluded.contract_status_code,
          authority_identifier=excluded.authority_identifier,
          raw_payload=excluded.raw_payload,
          updated_at=excluded.updated_at
        """,
        contract_rows,
    )
    source_pks = sorted({int(row[1]) for row in contract_rows})
    if source_pks:
        marks = ",".join("?" for _ in source_pks)
        conn.execute(
            f"DELETE FROM money_contract_award_results WHERE source_record_pk IN ({marks})",
            source_pks,
        )
        conn.execute(
            f"DELETE FROM money_contract_documents WHERE source_record_pk IN ({marks})",
            source_pks,
        )
    conn.executemany(
        """
        INSERT INTO money_contract_award_results (
          source_id, source_record_pk, source_record_id, stable_contract_id,
          award_ordinal, lot_id, result_code, result_description, award_date,
          received_tender_quantity, supplier_name, supplier_identifier,
          supplier_identifier_scheme, amount_eur_decimal,
          payable_amount_eur_decimal, currency, raw_payload, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        award_rows,
    )
    conn.executemany(
        """
        INSERT INTO money_contract_documents (
          source_id, source_record_pk, source_record_id, stable_contract_id,
          document_ordinal, document_kind, document_label, source_url,
          official_document_hash, raw_payload, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        document_rows,
    )
    conn.executemany(
        """
        INSERT OR IGNORE INTO placsp_bulk_record_sightings (
          placsp_bulk_run_id, placsp_bulk_member_id, source_id,
          source_record_pk, source_record_id, stable_contract_id,
          entry_content_sha256, record_ordinal, observed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        sighting_rows,
    )
    conn.execute(
        """
        UPDATE placsp_bulk_members
        SET work_item_id = ?, content_sha256 = ?, records_seen = ?,
            records_loaded = ?, tombstones_seen = ?, status = 'ok',
            error = NULL, updated_at = ?
        WHERE placsp_bulk_member_id = ?
        """,
        (
            int(item["work_item_id"]),
            member_content_sha256,
            len(records),
            len(records),
            sum(record.tombstone for record in records),
            now_iso,
            int(payload["placsp_bulk_member_id"]),
        ),
    )
    conn.commit()


def _parse_member(
    conn: sqlite3.Connection,
    *,
    item: Mapping[str, object],
    worker_id: str,
    lease_seconds: int,
    max_records: int,
    max_documents_per_record: int,
) -> tuple[list[PlacspAtomRecord], str]:
    payload = dict(item.get("payload") or {})
    work_item_id = int(item["work_item_id"])
    progress_count = 0

    def progress() -> None:
        nonlocal progress_count
        progress_count += 1
        if (
            progress_count % 100 == 0
            and heartbeat_work_items(
                conn,
                worker_id=worker_id,
                work_item_ids=[work_item_id],
                lease_seconds=lease_seconds,
            )
            != 1
        ):
            raise RuntimeError("lost member lease during parse")

    archive_path = _runtime_path(str(payload["raw_path"]))
    with (
        zipfile.ZipFile(archive_path) as archive,
        archive.open(str(payload["member_name"])) as raw_stream,
    ):
        stream = _HashingReader(raw_stream)
        records = list(
            iter_placsp_atom_records(
                stream,
                max_records=max_records,
                max_documents_per_record=max_documents_per_record,
                progress_callback=progress,
            )
        )
        content_sha256 = stream.content_sha256
    if not records:
        raise RuntimeError("PLACSP member has no entries or tombstones")
    return records, content_sha256


def run_member_worker(
    conn: sqlite3.Connection,
    *,
    pipeline_id: str,
    worker_id: str,
    claim_size: int,
    max_items: int,
    lease_seconds: int,
    max_records: int,
    max_documents_per_record: int,
    max_member_bytes: int,
    min_free_bytes: int,
    retry_delay_seconds: int,
) -> dict[str, Any]:
    processed = succeeded = failed = records_loaded = 0
    blocked_storage = False
    stop_reason = "queue_drained"
    storage_preflight: dict[str, Any] | None = None
    storage_path = _sqlite_storage_path(conn)
    while max_items <= 0 or processed < max_items:
        limit = min(claim_size, max_items - processed) if max_items > 0 else claim_size
        queue_before_claim = work_queue_observability(
            conn, pipeline_id=_member_pipeline(pipeline_id), top_limit=1
        )
        if int(queue_before_claim["unfinished_total"]) == 0:
            break
        storage_preflight = _storage_preflight(
            storage_path,
            min_free_bytes=min_free_bytes,
            reserve_bytes=max_member_bytes * max(1, limit),
        )
        if not storage_preflight["ready"]:
            blocked_storage = True
            stop_reason = "insufficient_free_space"
            break
        claimed = claim_work_items(
            conn,
            pipeline_id=_member_pipeline(pipeline_id),
            worker_id=worker_id,
            limit=max(1, limit),
            lease_seconds=lease_seconds,
        )
        if not claimed:
            stop_reason = "no_claimable_items"
            break
        for item in claimed:
            processed += 1
            try:
                records, content_sha256 = _parse_member(
                    conn,
                    item=item,
                    worker_id=worker_id,
                    lease_seconds=lease_seconds,
                    max_records=max_records,
                    max_documents_per_record=max_documents_per_record,
                )
                if (
                    heartbeat_work_items(
                        conn,
                        worker_id=worker_id,
                        work_item_ids=[int(item["work_item_id"])],
                        lease_seconds=lease_seconds,
                    )
                    != 1
                ):
                    raise RuntimeError("lost member lease before persistence")
                _persist_member_records(
                    conn,
                    item=item,
                    records=records,
                    member_content_sha256=content_sha256,
                )
                if (
                    complete_work_items(
                        conn,
                        worker_id=worker_id,
                        work_item_ids=[int(item["work_item_id"])],
                    )
                    != 1
                ):
                    raise RuntimeError("lost member lease before completion")
                succeeded += 1
                records_loaded += len(records)
            except Exception as exc:  # noqa: BLE001
                conn.rollback()
                failed += 1
                fail_work_items(
                    conn,
                    worker_id=worker_id,
                    work_item_ids=[int(item["work_item_id"])],
                    error=f"member_error: {type(exc).__name__}: {exc}",
                    retry_delay_seconds=retry_delay_seconds,
                    retryable=False,
                )
    if not blocked_storage and max_items > 0 and processed >= max_items:
        stop_reason = "max_items_reached"
    report = report_bulk_run(
        conn, pipeline_id=pipeline_id, finalize=not blocked_storage
    )
    if blocked_storage:
        report["status"] = "blocked_storage"
    report["worker"] = {
        "worker_id": worker_id,
        "stop_reason": stop_reason,
        "processed": processed,
        "succeeded": succeeded,
        "failed_attempts": failed,
        "records_loaded": records_loaded,
        "claim_size": claim_size,
        "storage_preflight": storage_preflight,
    }
    return report


def report_bulk_run(
    conn: sqlite3.Connection,
    *,
    pipeline_id: str,
    finalize: bool,
) -> dict[str, Any]:
    run = _bulk_run(conn, pipeline_id)
    if run is None:
        raise RuntimeError(f"unknown PLACSP bulk pipeline: {pipeline_id}")
    bulk_run_id = int(run["placsp_bulk_run_id"])
    archive_queue = work_queue_observability(
        conn, pipeline_id=_archive_pipeline(pipeline_id), top_limit=10
    )
    member_queue = work_queue_observability(
        conn, pipeline_id=_member_pipeline(pipeline_id), top_limit=10
    )
    archive = conn.execute(
        """
        SELECT COUNT(*) AS total, COALESCE(SUM(bytes), 0) AS bytes,
               COALESCE(SUM(members_total), 0) AS members_total,
               COALESCE(SUM(uncompressed_bytes), 0) AS uncompressed_bytes,
               SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) AS ok_total
        FROM placsp_bulk_archives WHERE placsp_bulk_run_id = ?
        """,
        (bulk_run_id,),
    ).fetchone()
    member = conn.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN m.status = 'ok' THEN 1 ELSE 0 END) AS ok_total,
               COALESCE(SUM(m.records_seen), 0) AS records_seen,
               COALESCE(SUM(m.records_loaded), 0) AS records_loaded,
               COALESCE(SUM(m.tombstones_seen), 0) AS tombstones_seen,
               COALESCE(SUM(m.uncompressed_bytes), 0) AS uncompressed_bytes
        FROM placsp_bulk_members AS m
        JOIN placsp_bulk_archives AS a
          ON a.placsp_bulk_archive_id = m.placsp_bulk_archive_id
        WHERE a.placsp_bulk_run_id = ?
        """,
        (bulk_run_id,),
    ).fetchone()
    normalized = conn.execute(
        """
        SELECT COUNT(*) AS sightings,
               COUNT(DISTINCT source_record_id) AS versions,
               COUNT(DISTINCT stable_contract_id) AS contracts
        FROM placsp_bulk_record_sightings
        WHERE placsp_bulk_run_id = ?
        """,
        (bulk_run_id,),
    ).fetchone()
    child_counts = conn.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM money_contract_award_results AS r
           JOIN placsp_bulk_record_sightings AS s
             ON s.source_record_pk = r.source_record_pk
           WHERE s.placsp_bulk_run_id = ?) AS awards,
          (SELECT COUNT(*) FROM money_contract_documents AS d
           JOIN placsp_bulk_record_sightings AS s
             ON s.source_record_pk = d.source_record_pk
           WHERE s.placsp_bulk_run_id = ?) AS documents
        """,
        (bulk_run_id, bulk_run_id),
    ).fetchone()
    corpus = conn.execute(
        """
        WITH ranked AS (
          SELECT
            c.source_record_pk,
            ROW_NUMBER() OVER (
              PARTITION BY c.source_id,
                COALESCE(NULLIF(c.stable_contract_id, ''),
                         'source:' || c.source_record_id)
              ORDER BY
                COALESCE(NULLIF(c.entry_updated_at, ''),
                         NULLIF(c.awarded_date, ''),
                         NULLIF(c.published_date, ''),
                         c.source_snapshot_date, '') DESC,
                c.contract_record_id DESC
            ) AS version_rank
          FROM money_contract_records AS c
          WHERE c.source_id = ?
        )
        SELECT
          (SELECT COUNT(*) FROM placsp_bulk_runs WHERE source_id = ?) AS runs,
          (SELECT COUNT(*) FROM placsp_bulk_archives AS a
             JOIN placsp_bulk_runs AS run
               ON run.placsp_bulk_run_id = a.placsp_bulk_run_id
           WHERE run.source_id = ? AND a.status = 'ok') AS archives,
          (SELECT COUNT(*) FROM money_contract_records
           WHERE source_id = ?) AS record_versions,
          (SELECT COUNT(DISTINCT stable_contract_id)
           FROM money_contract_records
           WHERE source_id = ? AND stable_contract_id IS NOT NULL
             AND TRIM(stable_contract_id) != '') AS stable_contracts,
          (SELECT COUNT(*) FROM ranked WHERE version_rank = 1)
            AS current_contract_facts,
          (SELECT COUNT(*) FROM money_contract_award_results
           WHERE source_id = ?) AS award_result_versions,
          (SELECT COUNT(*) FROM money_contract_award_results AS award
             JOIN ranked AS current
               ON current.source_record_pk = award.source_record_pk
              AND current.version_rank = 1
           WHERE award.source_id = ?) AS current_award_facts,
          (SELECT COUNT(*) FROM money_contract_documents
           WHERE source_id = ?) AS document_sightings,
          (SELECT COUNT(DISTINCT source_url) FROM money_contract_documents
           WHERE source_id = ?) AS unique_document_urls
        """,
        (SOURCE_ID,) * 9,
    ).fetchone()
    archive_total = int(archive["total"])
    member_total = int(member["total"])
    records_seen = int(member["records_seen"])
    records_loaded = int(member["records_loaded"])
    checks = {
        "no_dead_archives": int(archive_queue["state_counts"].get("dead", 0)) == 0,
        "all_archives_succeeded": int(archive_queue["state_counts"].get("succeeded", 0))
        == int(run["archives_enqueued"]),
        "archive_rows_reconcile": archive_total == int(run["archives_enqueued"]),
        "all_archive_rows_ok": int(archive["ok_total"] or 0) == archive_total,
        "member_queue_discovered": int(member_queue["items_total"]) == member_total,
        "no_dead_members": int(member_queue["state_counts"].get("dead", 0)) == 0,
        "all_members_succeeded": int(member_queue["state_counts"].get("succeeded", 0))
        == member_total,
        "all_member_rows_ok": int(member["ok_total"] or 0) == member_total,
        "member_record_counts_reconcile": records_seen == records_loaded,
        "unique_version_lineage_present": int(normalized["versions"]) > 0,
        "archive_member_bytes_reconcile": int(member["uncompressed_bytes"])
        == int(archive["uncompressed_bytes"]),
    }
    terminal = (
        int(archive_queue["unfinished_total"]) == 0
        and int(member_queue["unfinished_total"]) == 0
    )
    all_checks = all(checks.values())
    state = str(run["state"])
    if terminal:
        state = "succeeded" if all_checks else "failed"
    if finalize and terminal:
        now_iso = now_utc_iso()
        conn.execute(
            """
            UPDATE placsp_bulk_runs
            SET state = ?, records_seen = ?, records_loaded = ?,
                updated_at = ?, finished_at = ?
            WHERE placsp_bulk_run_id = ?
            """,
            (
                state,
                records_seen,
                int(normalized["versions"]),
                now_iso,
                now_iso,
                bulk_run_id,
            ),
        )
        finish_run(
            conn,
            int(run["ingestion_run_id"]),
            "ok" if all_checks else "error",
            (
                f"PLACSP bulk {state}: archives={archive_total}; members={member_total}; "
                f"records={records_seen}; versions={int(normalized['versions'])}"
            ),
            records_seen,
            int(normalized["versions"]),
        )
    return {
        "schema_version": "placsp_bulk_run_report_v2",
        "status": state,
        "source_id": SOURCE_ID,
        "pipeline_id": pipeline_id,
        "placsp_bulk_run_id": bulk_run_id,
        "snapshot_date": str(run["snapshot_date"]),
        "observed": {
            "archives": archive_total,
            "archive_bytes": int(archive["bytes"]),
            "members": member_total,
            "uncompressed_member_bytes": int(member["uncompressed_bytes"]),
            "records_seen": records_seen,
            "record_versions": int(normalized["versions"]),
            "stable_contracts": int(normalized["contracts"]),
            "duplicate_version_sightings": records_seen - int(normalized["sightings"]),
            "tombstones": int(member["tombstones_seen"]),
            "award_results": int(child_counts["awards"]),
            "document_manifests": int(child_counts["documents"]),
            "peak_rss_mb": round(_peak_rss_mb(), 3),
        },
        "corpus": {
            "runs": int(corpus["runs"]),
            "archives": int(corpus["archives"]),
            "record_versions": int(corpus["record_versions"]),
            "stable_contracts": int(corpus["stable_contracts"]),
            "current_contract_facts": int(corpus["current_contract_facts"]),
            "award_result_versions": int(corpus["award_result_versions"]),
            "current_award_facts": int(corpus["current_award_facts"]),
            "document_sightings": int(corpus["document_sightings"]),
            "unique_document_urls": int(corpus["unique_document_urls"]),
        },
        "archive_queue": archive_queue,
        "member_queue": member_queue,
        "checks": checks,
        "analytical_ingest_gate_passed": terminal and all_checks,
        "promotion_gate_passed": False,
        "publication_status": "local_normalized_not_published",
        "limitations": [
            "The selected archive cohort is not the complete official corpus since 2012.",
            "Published contract awards are commitments, not proof of invoice or payment execution.",
            "Supplier publication requires legal-entity classification before public export.",
        ],
    }


def requeue_dead_members(
    conn: sqlite3.Connection,
    *,
    pipeline_id: str,
    error_contains: str,
) -> dict[str, Any]:
    token = str(error_contains or "").strip()
    if not token:
        raise ValueError("error_contains is required for scoped dead-item requeue")
    rows = conn.execute(
        """
        SELECT work_item_id, payload_json
        FROM pipeline_work_items
        WHERE pipeline_id = ? AND state = 'dead' AND last_error LIKE ?
        ORDER BY work_item_id
        """,
        (_member_pipeline(pipeline_id), f"%{token}%"),
    ).fetchall()
    work_item_ids = [int(row["work_item_id"]) for row in rows]
    member_ids = [
        int(json.loads(str(row["payload_json"]))["placsp_bulk_member_id"])
        for row in rows
    ]
    now_iso = now_utc_iso()
    if work_item_ids:
        marks = ",".join("?" for _ in work_item_ids)
        conn.execute(
            f"""
            UPDATE pipeline_work_items
            SET state = 'pending', available_at = ?, lease_owner = NULL,
                lease_expires_at = NULL, last_error = NULL,
                completed_at = NULL, updated_at = ?
            WHERE work_item_id IN ({marks}) AND state = 'dead'
            """,
            (now_iso, now_iso, *work_item_ids),
        )
    if member_ids:
        marks = ",".join("?" for _ in member_ids)
        conn.execute(
            f"""
            UPDATE placsp_bulk_members
            SET status = 'pending', error = NULL, updated_at = ?
            WHERE placsp_bulk_member_id IN ({marks})
            """,
            (now_iso, *member_ids),
        )
    conn.commit()
    return {
        "schema_version": "placsp_member_requeue_v1",
        "status": "ok",
        "pipeline_id": pipeline_id,
        "error_contains": token,
        "members_requeued": len(work_item_ids),
        "member_queue": work_queue_observability(
            conn, pipeline_id=_member_pipeline(pipeline_id), top_limit=10
        ),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Durable PLACSP archive ingestion")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--pipeline-id", default=DEFAULT_PIPELINE)
    parser.add_argument("--report-out", default="")
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover = subparsers.add_parser("discover-archives")
    discover.add_argument("--catalog-url", default=DEFAULT_CATALOG_URL)
    discover.add_argument("--as-of-date", required=True)
    discover.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    discover.add_argument("--timeout", type=int, default=30)
    discover.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_CATALOG_BYTES)
    discover.add_argument("--ca-bundle", default="")
    discover.add_argument("--enforce", action="store_true")

    enqueue = subparsers.add_parser("enqueue")
    enqueue.add_argument("--snapshot-date", required=True)
    archive_source = enqueue.add_mutually_exclusive_group(required=True)
    archive_source.add_argument("--archive", action="append")
    archive_source.add_argument("--archive-report")

    archives = subparsers.add_parser("work-archives")
    archives.add_argument("--raw-root", default=str(DEFAULT_RAW_ROOT))
    archives.add_argument("--worker-id", default="placsp-archive-worker")
    archives.add_argument("--max-items", type=int, default=0)
    archives.add_argument("--lease-seconds", type=int, default=900)
    archives.add_argument("--timeout", type=int, default=90)
    archives.add_argument(
        "--max-archive-bytes", type=int, default=DEFAULT_MAX_ARCHIVE_BYTES
    )
    archives.add_argument(
        "--max-members", type=int, default=DEFAULT_MAX_ARCHIVE_MEMBERS
    )
    archives.add_argument(
        "--max-total-uncompressed-bytes",
        type=int,
        default=DEFAULT_MAX_TOTAL_UNCOMPRESSED_BYTES,
    )
    archives.add_argument(
        "--max-member-bytes", type=int, default=DEFAULT_MAX_MEMBER_BYTES
    )
    archives.add_argument(
        "--max-compression-ratio", type=float, default=DEFAULT_MAX_COMPRESSION_RATIO
    )
    archives.add_argument("--min-free-bytes", type=int, default=DEFAULT_MIN_FREE_BYTES)
    archives.add_argument("--download-attempts", type=int, default=3)
    archives.add_argument("--retry-delay-seconds", type=int, default=60)
    archives.add_argument("--ca-bundle", default="")

    members = subparsers.add_parser("work-members")
    members.add_argument("--worker-id", default="placsp-member-worker")
    members.add_argument("--claim-size", type=int, default=4)
    members.add_argument("--max-items", type=int, default=0)
    members.add_argument("--lease-seconds", type=int, default=300)
    members.add_argument(
        "--max-records", type=int, default=DEFAULT_MAX_RECORDS_PER_MEMBER
    )
    members.add_argument(
        "--max-documents-per-record",
        type=int,
        default=DEFAULT_MAX_DOCUMENTS_PER_RECORD,
    )
    members.add_argument(
        "--max-member-bytes", type=int, default=DEFAULT_MAX_MEMBER_BYTES
    )
    members.add_argument("--min-free-bytes", type=int, default=DEFAULT_MIN_FREE_BYTES)
    members.add_argument("--retry-delay-seconds", type=int, default=30)

    requeue = subparsers.add_parser("requeue-dead-members")
    requeue.add_argument("--error-contains", required=True)

    report = subparsers.add_parser("report")
    report.add_argument("--finalize", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "discover-archives":
        try:
            report = discover_catalog(
                catalog_url=args.catalog_url,
                as_of_date=date.fromisoformat(args.as_of_date),
                start_year=args.start_year,
                timeout=args.timeout,
                max_bytes=args.max_bytes,
                ca_bundle=Path(args.ca_bundle) if args.ca_bundle else None,
            )
        except (OSError, RuntimeError, ValueError, urllib.error.URLError) as exc:
            print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2
        _write_report(args.report_out, report)
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
        return 1 if args.enforce and report.get("status") != "ok" else 0
    conn = _open_runtime(Path(args.db), Path(args.schema))
    try:
        if args.command == "enqueue":
            archive_specs = (
                _parse_archive_report(Path(args.archive_report))
                if args.archive_report
                else _parse_archive_specs(args.archive)
            )
            report = enqueue_archives(
                conn,
                pipeline_id=args.pipeline_id,
                snapshot_date=args.snapshot_date,
                archives=archive_specs,
            )
        elif args.command == "work-archives":
            report = run_archive_worker(
                conn,
                pipeline_id=args.pipeline_id,
                worker_id=args.worker_id,
                raw_root=Path(args.raw_root),
                max_items=args.max_items,
                lease_seconds=args.lease_seconds,
                timeout=args.timeout,
                max_archive_bytes=args.max_archive_bytes,
                max_members=args.max_members,
                max_total_uncompressed_bytes=args.max_total_uncompressed_bytes,
                max_member_bytes=args.max_member_bytes,
                max_compression_ratio=args.max_compression_ratio,
                min_free_bytes=args.min_free_bytes,
                download_attempts=args.download_attempts,
                retry_delay_seconds=args.retry_delay_seconds,
                ca_bundle=Path(args.ca_bundle) if args.ca_bundle else None,
            )
        elif args.command == "work-members":
            report = run_member_worker(
                conn,
                pipeline_id=args.pipeline_id,
                worker_id=args.worker_id,
                claim_size=args.claim_size,
                max_items=args.max_items,
                lease_seconds=args.lease_seconds,
                max_records=args.max_records,
                max_documents_per_record=args.max_documents_per_record,
                max_member_bytes=args.max_member_bytes,
                min_free_bytes=args.min_free_bytes,
                retry_delay_seconds=args.retry_delay_seconds,
            )
        elif args.command == "requeue-dead-members":
            report = requeue_dead_members(
                conn,
                pipeline_id=args.pipeline_id,
                error_contains=args.error_contains,
            )
        else:
            report = report_bulk_run(
                conn,
                pipeline_id=args.pipeline_id,
                finalize=args.finalize,
            )
    except (
        OSError,
        RuntimeError,
        ValueError,
        sqlite3.Error,
        zipfile.BadZipFile,
    ) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    finally:
        conn.close()
    _write_report(args.report_out, report)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 1 if report.get("status") in {"failed", "blocked_storage"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
