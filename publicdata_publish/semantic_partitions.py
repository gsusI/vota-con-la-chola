"""Bounded semantic Parquet partitions for high-volume public fact lanes."""

from __future__ import annotations

import hashlib
import json
import os
import resource
import shutil
import sqlite3
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlsplit

from .sanitize import sanitize_url_for_public


MANIFEST_SCHEMA_VERSION = "semantic_partition_manifest_v1"
TRANSFORMER_VERSION = "member_votes_public_v2"
LANE = "member_votes"

MEMBER_VOTE_SCHEMA: tuple[dict[str, Any], ...] = (
    {"name": "member_vote_id", "type": "int64", "nullable": False},
    {"name": "vote_event_id", "type": "string", "nullable": False},
    {"name": "seat", "type": "string", "nullable": True},
    {"name": "member_name", "type": "string", "nullable": True},
    {"name": "member_name_normalized", "type": "string", "nullable": True},
    {"name": "person_id", "type": "int64", "nullable": True},
    {"name": "group_code", "type": "string", "nullable": True},
    {"name": "vote_choice", "type": "string", "nullable": False},
    {"name": "source_id", "type": "string", "nullable": False},
    {"name": "source_url", "type": "string", "nullable": True},
    {"name": "source_url_scope", "type": "string", "nullable": True},
    {"name": "source_snapshot_date", "type": "string", "nullable": True},
    {"name": "parliamentary_group_id", "type": "int64", "nullable": True},
    {"name": "legislature", "type": "string", "nullable": True},
    {"name": "vote_date", "type": "string", "nullable": True},
    {"name": "vote_year", "type": "string", "nullable": False},
    {"name": "jurisdiction", "type": "string", "nullable": False},
    {"name": "event_source_record_pk", "type": "int64", "nullable": True},
)
MEMBER_VOTE_COLUMNS = tuple(str(field["name"]) for field in MEMBER_VOTE_SCHEMA)

PRIVATE_TOKENS = (
    "/" + "Users" + "/",
    "/" + "home" + "/",
    "file" + ":///",
    "Bearer ",
    "hf_",
)

MEMBER_VOTE_SQL = """
SELECT
  m.member_vote_id,
  m.vote_event_id,
  m.seat,
  m.member_name,
  m.member_name_normalized,
  m.person_id,
  m.group_code,
  m.vote_choice,
  e.source_id,
  COALESCE(NULLIF(m.source_url, ''), e.source_url, '') AS source_url,
  COALESCE(NULLIF(m.source_snapshot_date, ''), e.source_snapshot_date, '')
    AS source_snapshot_date,
  m.parliamentary_group_id,
  e.legislature,
  e.vote_date,
  CASE
    WHEN substr(COALESCE(e.vote_date, ''), 1, 4)
      GLOB '[12][0-9][0-9][0-9]'
    THEN substr(e.vote_date, 1, 4)
    ELSE 'unknown'
  END AS vote_year,
  e.source_record_pk AS event_source_record_pk,
  m.source_id AS member_source_id,
  s.default_url AS source_default_url
FROM parl_vote_member_votes AS m
JOIN parl_vote_events AS e USING (vote_event_id)
JOIN sources AS s ON s.source_id = e.source_id
ORDER BY e.source_id, vote_year, m.member_vote_id
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _schema_sha256() -> str:
    payload = json.dumps(
        MEMBER_VOTE_SCHEMA,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _peak_rss_mb() -> float:
    raw = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if sys.platform == "darwin":
        return round(raw / (1024 * 1024), 3)
    return round(raw / 1024, 3)


def _safe_component(value: str) -> str:
    out = []
    for char in value.strip():
        if char.isalnum() or char in {"-", "_", "."}:
            out.append(char)
        else:
            out.append("_")
    cleaned = "".join(out).strip("._")
    return cleaned or "unknown"


def _public_url(raw_value: Any) -> str | None:
    raw = str(raw_value or "").strip()
    if not raw:
        return None
    safe = sanitize_url_for_public(raw)
    try:
        parsed = urlsplit(safe)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return safe


def _jurisdiction(source_id: str) -> str:
    if source_id == "congreso_votaciones":
        return "es-congreso"
    if source_id == "senado_votaciones":
        return "es-senado"
    return "es-" + _safe_component(source_id)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _integer(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _public_row(row: sqlite3.Row) -> tuple[dict[str, Any], bool]:
    source_id = str(row["source_id"])
    record_url = _public_url(row["source_url"])
    source_default_url = _public_url(row["source_default_url"])
    source_url = record_url or source_default_url
    source_url_scope = (
        "record" if record_url else "source_default" if source_default_url else None
    )
    public = {
        "member_vote_id": int(row["member_vote_id"]),
        "vote_event_id": str(row["vote_event_id"]),
        "seat": _text(row["seat"]),
        "member_name": _text(row["member_name"]),
        "member_name_normalized": _text(row["member_name_normalized"]),
        "person_id": _integer(row["person_id"]),
        "group_code": _text(row["group_code"]),
        "vote_choice": str(row["vote_choice"]),
        "source_id": source_id,
        "source_url": source_url,
        "source_url_scope": source_url_scope,
        "source_snapshot_date": _text(row["source_snapshot_date"]),
        "parliamentary_group_id": _integer(row["parliamentary_group_id"]),
        "legislature": _text(row["legislature"]),
        "vote_date": _text(row["vote_date"]),
        "vote_year": str(row["vote_year"]),
        "jurisdiction": _jurisdiction(source_id),
        "event_source_record_pk": _integer(row["event_source_record_pk"]),
    }
    return public, source_id == str(row["member_source_id"])


def _partition_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row["source_id"]),
        str(row["jurisdiction"]),
        str(row["vote_year"]),
    )


def _partition_id(key: tuple[str, str, str]) -> str:
    return "|".join(key)


def _partition_dir(snapshot_date: str, key: tuple[str, str, str]) -> Path:
    source_id, jurisdiction, year = key
    return Path(
        f"lane={LANE}",
        f"snapshot_date={_safe_component(snapshot_date)}",
        f"source_id={_safe_component(source_id)}",
        f"jurisdiction={_safe_component(jurisdiction)}",
        f"year={_safe_component(year)}",
    )


def _canonical_row_bytes(row: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            [row[name] for name in MEMBER_VOTE_COLUMNS],
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def _iter_rows(db_path: Path) -> Iterator[tuple[dict[str, Any], bool]]:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        for row in conn.execute(MEMBER_VOTE_SQL):
            yield _public_row(row)
    finally:
        conn.close()


def _new_partition_scan(
    *, snapshot_date: str, key: tuple[str, str, str]
) -> dict[str, Any]:
    return {
        "partition_id": _partition_id(key),
        "values": {
            "snapshot_date": snapshot_date,
            "source_id": key[0],
            "jurisdiction": key[1],
            "year": key[2],
        },
        "relative_dir": _partition_dir(snapshot_date, key).as_posix(),
        "rows": 0,
        "min_member_vote_id": None,
        "max_member_vote_id": None,
        "source_url_rows": 0,
        "source_record_url_rows": 0,
        "source_default_url_rows": 0,
        "person_id_rows": 0,
        "event_source_record_rows": 0,
        "source_id_match_rows": 0,
        "private_token_findings": 0,
        "_digest": hashlib.sha256(),
    }


def _finish_partition_scan(partition: dict[str, Any]) -> dict[str, Any]:
    finished = dict(partition)
    finished["input_sha256"] = finished.pop("_digest").hexdigest()
    return finished


def scan_member_vote_partitions(
    db_path: Path, *, snapshot_date: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    partitions: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_key: tuple[str, str, str] | None = None
    totals = {
        "rows": 0,
        "source_url_rows": 0,
        "source_record_url_rows": 0,
        "source_default_url_rows": 0,
        "person_id_rows": 0,
        "event_source_record_rows": 0,
        "source_id_match_rows": 0,
        "private_token_findings": 0,
        "unknown_year_rows": 0,
    }
    for public_row, source_id_matches in _iter_rows(db_path):
        key = _partition_key(public_row)
        if current_key != key:
            if current is not None:
                partitions.append(_finish_partition_scan(current))
            current_key = key
            current = _new_partition_scan(snapshot_date=snapshot_date, key=key)
        assert current is not None
        row_id = int(public_row["member_vote_id"])
        current["rows"] += 1
        current["min_member_vote_id"] = (
            row_id
            if current["min_member_vote_id"] is None
            else min(int(current["min_member_vote_id"]), row_id)
        )
        current["max_member_vote_id"] = (
            row_id
            if current["max_member_vote_id"] is None
            else max(int(current["max_member_vote_id"]), row_id)
        )
        for metric, field in (
            ("source_url_rows", "source_url"),
            ("person_id_rows", "person_id"),
            ("event_source_record_rows", "event_source_record_pk"),
        ):
            if public_row[field] not in (None, ""):
                current[metric] += 1
                totals[metric] += 1
        if public_row["source_url_scope"] == "record":
            current["source_record_url_rows"] += 1
            totals["source_record_url_rows"] += 1
        elif public_row["source_url_scope"] == "source_default":
            current["source_default_url_rows"] += 1
            totals["source_default_url_rows"] += 1
        if source_id_matches:
            current["source_id_match_rows"] += 1
            totals["source_id_match_rows"] += 1
        findings = sum(
            1
            for value in public_row.values()
            if isinstance(value, str)
            for token in PRIVATE_TOKENS
            if token in value
        )
        current["private_token_findings"] += findings
        totals["private_token_findings"] += findings
        if public_row["vote_year"] == "unknown":
            totals["unknown_year_rows"] += 1
        current["_digest"].update(_canonical_row_bytes(public_row))
        totals["rows"] += 1
    if current is not None:
        partitions.append(_finish_partition_scan(current))
    return partitions, totals


def _arrow_schema():
    try:
        import pyarrow as pa  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "pyarrow is required; install the project parquet extra"
        ) from exc
    type_map = {"int64": pa.int64(), "string": pa.string()}
    fields = [
        pa.field(
            str(field["name"]),
            type_map[str(field["type"])],
            nullable=bool(field["nullable"]),
        )
        for field in MEMBER_VOTE_SCHEMA
    ]
    return pa.schema(fields).with_metadata(
        {
            b"lane": LANE.encode("ascii"),
            b"manifest_schema_version": MANIFEST_SCHEMA_VERSION.encode("ascii"),
            b"transformer_version": TRANSFORMER_VERSION.encode("ascii"),
            b"schema_sha256": _schema_sha256().encode("ascii"),
        }
    )


class _PartitionWriter:
    def __init__(
        self,
        *,
        root: Path,
        partition: dict[str, Any],
        compression: str,
        row_group_rows: int,
        max_file_rows: int,
    ) -> None:
        self.root = root
        self.partition = partition
        self.compression = None if compression == "none" else compression
        self.row_group_rows = row_group_rows
        self.max_file_rows = max_file_rows
        self.schema = _arrow_schema()
        self.columns = {name: [] for name in MEMBER_VOTE_COLUMNS}
        self.buffered = 0
        self.rows_written = 0
        self.file_index = 0
        self.file_rows = 0
        self.file_min_id: int | None = None
        self.file_max_id: int | None = None
        self.writer = None
        self.files: list[dict[str, Any]] = []

    def append(self, row: dict[str, Any]) -> None:
        for name in MEMBER_VOTE_COLUMNS:
            self.columns[name].append(row[name])
        self.buffered += 1
        if self.buffered >= self.row_group_rows:
            self._flush()

    def _open_file(self) -> None:
        import pyarrow.parquet as pq  # type: ignore

        rel_dir = Path(str(self.partition["relative_dir"]))
        rel_path = rel_dir / f"part-{self.file_index:05d}.parquet"
        abs_path = self.root / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        self.writer = pq.ParquetWriter(
            abs_path,
            self.schema,
            compression=self.compression,
            use_dictionary=True,
            write_statistics=True,
        )
        self.file_rows = 0
        self.file_min_id = None
        self.file_max_id = None

    def _close_file(self) -> None:
        if self.writer is None:
            return
        self.writer.close()
        rel_dir = Path(str(self.partition["relative_dir"]))
        rel_path = rel_dir / f"part-{self.file_index:05d}.parquet"
        abs_path = self.root / rel_path
        self.files.append(
            {
                "path": rel_path.as_posix(),
                "rows": self.file_rows,
                "bytes": int(abs_path.stat().st_size),
                "sha256": _sha256_file(abs_path),
                "min_member_vote_id": self.file_min_id,
                "max_member_vote_id": self.file_max_id,
            }
        )
        self.file_index += 1
        self.writer = None

    def _write_table(self, table) -> None:
        offset = 0
        while offset < table.num_rows:
            if self.writer is None:
                self._open_file()
            available = self.max_file_rows - self.file_rows
            take = min(available, table.num_rows - offset)
            piece = table.slice(offset, take)
            ids = piece.column("member_vote_id")
            first_id = int(ids[0].as_py())
            last_id = int(ids[len(ids) - 1].as_py())
            self.writer.write_table(piece, row_group_size=self.row_group_rows)
            self.file_rows += take
            self.rows_written += take
            self.file_min_id = (
                first_id if self.file_min_id is None else min(self.file_min_id, first_id)
            )
            self.file_max_id = (
                last_id if self.file_max_id is None else max(self.file_max_id, last_id)
            )
            offset += take
            if self.file_rows >= self.max_file_rows:
                self._close_file()

    def _flush(self) -> None:
        if not self.buffered:
            return
        import pyarrow as pa  # type: ignore

        table = pa.Table.from_pydict(self.columns, schema=self.schema)
        self._write_table(table)
        self.columns = {name: [] for name in MEMBER_VOTE_COLUMNS}
        self.buffered = 0

    def close(self) -> list[dict[str, Any]]:
        self._flush()
        self._close_file()
        expected = int(self.partition["rows"])
        if self.rows_written != expected:
            raise RuntimeError(
                f"partition {self.partition['partition_id']} wrote "
                f"{self.rows_written} rows, expected {expected}"
            )
        return self.files


def _load_previous(
    previous_manifest_path: Path | None,
) -> tuple[dict[str, Any] | None, str | None]:
    if previous_manifest_path is None:
        return None, None
    if not previous_manifest_path.is_file():
        raise FileNotFoundError(previous_manifest_path)
    payload = json.loads(previous_manifest_path.read_text(encoding="utf-8"))
    return payload, _sha256_file(previous_manifest_path)


def _previous_partition_map(
    previous: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    if not previous:
        return {}
    if previous.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        return {}
    if previous.get("transformer_version") != TRANSFORMER_VERSION:
        return {}
    if previous.get("schema_sha256") != _schema_sha256():
        return {}
    return {
        str(item["partition_id"]): item
        for item in list(previous.get("partitions") or [])
    }


def _eligible_previous_partition(
    partition: dict[str, Any],
    previous: dict[str, Any] | None,
    *,
    previous_root: Path | None,
) -> dict[str, Any] | None:
    if previous is None or previous_root is None:
        return None
    if int(previous.get("rows") or -1) != int(partition["rows"]):
        return None
    if previous.get("input_sha256") != partition.get("input_sha256"):
        return None
    files = list(previous.get("files") or [])
    if not files:
        return None
    for file_meta in files:
        source = previous_root / str(file_meta["path"])
        if not source.is_file():
            return None
        if _sha256_file(source) != str(file_meta["sha256"]):
            return None
    return previous


def _reuse_partition_files(
    *,
    previous: dict[str, Any],
    previous_root: Path,
    staging_root: Path,
    partition: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    files: list[dict[str, Any]] = []
    modes = {"hardlink": 0, "copy": 0}
    new_dir = Path(str(partition["relative_dir"]))
    for old_meta in list(previous.get("files") or []):
        source = previous_root / str(old_meta["path"])
        destination_rel = new_dir / Path(str(old_meta["path"])).name
        destination = staging_root / destination_rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(source, destination)
            modes["hardlink"] += 1
        except OSError:
            shutil.copy2(source, destination)
            modes["copy"] += 1
        file_meta = dict(old_meta)
        file_meta["path"] = destination_rel.as_posix()
        files.append(file_meta)
    return files, modes


def _database_counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    try:
        member_rows = int(
            conn.execute("SELECT COUNT(*) FROM parl_vote_member_votes").fetchone()[0]
        )
        joined_rows = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM parl_vote_member_votes AS m
                JOIN parl_vote_events AS e USING (vote_event_id)
                """
            ).fetchone()[0]
        )
        distinct_ids = int(
            conn.execute(
                "SELECT COUNT(DISTINCT member_vote_id) FROM parl_vote_member_votes"
            ).fetchone()[0]
        )
        return {
            "member_vote_rows": member_rows,
            "joined_rows": joined_rows,
            "distinct_member_vote_ids": distinct_ids,
        }
    finally:
        conn.close()


def _vote_audit_summary(vote_audit_path: Path | None) -> dict[str, Any] | None:
    if vote_audit_path is None:
        return None
    if not vote_audit_path.is_file():
        raise FileNotFoundError(vote_audit_path)
    payload = json.loads(vote_audit_path.read_text(encoding="utf-8"))
    current = dict(payload.get("current") or {})
    totals = dict(current.get("totals") or {})
    return {
        "evidence_file": vote_audit_path.name,
        "schema_version": payload.get("schema_version"),
        "events_totals_available": int(totals.get("events_totals_available") or 0),
        "events_reconciled": int(totals.get("events_reconciled") or 0),
        "events_not_reconciled": int(totals.get("events_not_reconciled") or 0),
        "events_reconciled_pct": float(totals.get("events_reconciled_pct") or 0.0),
        "foreign_key_errors": int(current.get("foreign_key_errors") or 0),
    }


def export_member_vote_partitions(
    *,
    db_path: Path,
    output_root: Path,
    snapshot_date: str,
    compression: str = "zstd",
    row_group_rows: int = 25_000,
    max_file_rows: int = 100_000,
    previous_manifest_path: Path | None = None,
    previous_root: Path | None = None,
    vote_audit_path: Path | None = None,
    min_rows: int = 1,
    max_peak_rss_mb: float = 1024.0,
    enforce: bool = False,
) -> dict[str, Any]:
    db_path = Path(db_path)
    output_root = Path(output_root)
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    if output_root.exists():
        raise FileExistsError(output_root)
    if row_group_rows <= 0 or max_file_rows <= 0:
        raise ValueError("row-group-rows and max-file-rows must be positive")
    if row_group_rows > max_file_rows:
        raise ValueError("row-group-rows cannot exceed max-file-rows")
    if (previous_manifest_path is None) != (previous_root is None):
        raise ValueError("previous-manifest and previous-root must be provided together")

    started = time.monotonic()
    scan_started = time.monotonic()
    scanned_partitions, scan_totals = scan_member_vote_partitions(
        db_path, snapshot_date=snapshot_date
    )
    scan_seconds = time.monotonic() - scan_started
    database_counts = _database_counts(db_path)
    previous_manifest, previous_manifest_sha256 = _load_previous(
        previous_manifest_path
    )
    previous_by_id = _previous_partition_map(previous_manifest)
    reusable: dict[str, dict[str, Any]] = {}
    for partition in scanned_partitions:
        previous_partition = previous_by_id.get(str(partition["partition_id"]))
        eligible = _eligible_previous_partition(
            partition,
            previous_partition,
            previous_root=previous_root,
        )
        if eligible is not None:
            reusable[str(partition["partition_id"])] = eligible

    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging_root = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.staging-", dir=output_root.parent)
    )
    hardlinks = 0
    copies = 0
    partition_by_id = {
        str(partition["partition_id"]): partition
        for partition in scanned_partitions
    }
    try:
        for partition_id, previous_partition in reusable.items():
            partition = partition_by_id[partition_id]
            files, modes = _reuse_partition_files(
                previous=previous_partition,
                previous_root=Path(previous_root),
                staging_root=staging_root,
                partition=partition,
            )
            partition["files"] = files
            partition["materialization"] = "reused"
            hardlinks += modes["hardlink"]
            copies += modes["copy"]

        export_started = time.monotonic()
        active_id: str | None = None
        active_writer: _PartitionWriter | None = None
        if len(reusable) < len(scanned_partitions):
            for public_row, _source_id_matches in _iter_rows(db_path):
                partition_id = _partition_id(_partition_key(public_row))
                if partition_id != active_id:
                    if active_writer is not None:
                        partition_by_id[str(active_id)][
                            "files"
                        ] = active_writer.close()
                        partition_by_id[str(active_id)][
                            "materialization"
                        ] = "rebuilt"
                    active_id = partition_id
                    if partition_id in reusable:
                        active_writer = None
                    else:
                        active_writer = _PartitionWriter(
                            root=staging_root,
                            partition=partition_by_id[partition_id],
                            compression=compression,
                            row_group_rows=row_group_rows,
                            max_file_rows=max_file_rows,
                        )
                if active_writer is not None:
                    active_writer.append(public_row)
        if active_writer is not None and active_id is not None:
            partition_by_id[active_id]["files"] = active_writer.close()
            partition_by_id[active_id]["materialization"] = "rebuilt"
        export_seconds = time.monotonic() - export_started

        for partition in scanned_partitions:
            partition["files_total"] = len(list(partition.get("files") or []))
            partition["bytes_total"] = sum(
                int(item["bytes"]) for item in list(partition.get("files") or [])
            )

        rows = int(scan_totals["rows"])
        source_url_coverage = (
            float(scan_totals["source_url_rows"]) / rows if rows else 0.0
        )
        person_id_coverage = (
            float(scan_totals["person_id_rows"]) / rows if rows else 0.0
        )
        lineage_coverage = (
            float(scan_totals["event_source_record_rows"]) / rows if rows else 0.0
        )
        source_match_coverage = (
            float(scan_totals["source_id_match_rows"]) / rows if rows else 0.0
        )
        peak_rss = _peak_rss_mb()
        vote_audit = _vote_audit_summary(vote_audit_path)
        reconciliation_pct = (
            float(vote_audit["events_reconciled_pct"])
            if vote_audit is not None
            else 0.0
        )
        checks = {
            "minimum_rows": rows >= int(min_rows),
            "database_rows_reconciled": (
                rows == database_counts["member_vote_rows"]
                == database_counts["joined_rows"]
            ),
            "member_vote_ids_unique": (
                rows == database_counts["distinct_member_vote_ids"]
            ),
            "bounded_peak_rss": peak_rss <= float(max_peak_rss_mb),
            "source_url_coverage_at_least_99_pct": source_url_coverage >= 0.99,
            "source_record_lineage_at_least_99_pct": lineage_coverage >= 0.99,
            "source_id_consistency": source_match_coverage == 1.0,
            "no_private_tokens": int(scan_totals["private_token_findings"]) == 0,
            "all_partitions_materialized": all(
                bool(partition.get("files")) for partition in scanned_partitions
            ),
        }
        analytical_gate_passed = all(checks.values())
        promotion_checks = {
            "analytical_partition_gate": analytical_gate_passed,
            "official_totals_reconciled_at_least_95_pct": reconciliation_pct >= 0.95,
            "external_identity_verified": False,
            "durable_public_origin_verified": False,
        }
        manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "generated_at": _now_iso(),
            "lane": LANE,
            "snapshot_date": snapshot_date,
            "transformer_version": TRANSFORMER_VERSION,
            "schema": list(MEMBER_VOTE_SCHEMA),
            "schema_sha256": _schema_sha256(),
            "partition_contract": {
                "strategy": "semantic_hive",
                "keys": ["snapshot_date", "source_id", "jurisdiction", "year"],
                "ordering": ["source_id", "year", "member_vote_id"],
                "row_group_rows": int(row_group_rows),
                "max_file_rows": int(max_file_rows),
                "compression": compression,
            },
            "incremental_contract": {
                "input_fingerprint": "sha256_canonical_public_rows",
                "reuse_key": [
                    "partition_id",
                    "input_sha256",
                    "schema_sha256",
                    "transformer_version",
                ],
                "previous_manifest_sha256": previous_manifest_sha256,
                "partitions_reused": len(reusable),
                "partitions_rebuilt": len(scanned_partitions) - len(reusable),
                "files_hardlinked": hardlinks,
                "files_copied": copies,
            },
            "source": {
                "database_file": db_path.name,
                "database_bytes": int(db_path.stat().st_size),
                "table": "parl_vote_member_votes",
                "event_table": "parl_vote_events",
                "raw_payload_published": False,
            },
            "totals": {
                **database_counts,
                **scan_totals,
                "partitions": len(scanned_partitions),
                "files": sum(
                    len(list(partition.get("files") or []))
                    for partition in scanned_partitions
                ),
                "parquet_bytes": sum(
                    int(partition["bytes_total"]) for partition in scanned_partitions
                ),
            },
            "coverage": {
                "source_url": round(source_url_coverage, 8),
                "person_id": round(person_id_coverage, 8),
                "event_source_record": round(lineage_coverage, 8),
                "source_id_match": round(source_match_coverage, 8),
            },
            "vote_audit": vote_audit,
            "identity_assurance": "observed_label_linkage_not_external_identity",
            "publication_status": "local_generated_not_published",
            "checks": checks,
            "analytical_partition_gate_passed": analytical_gate_passed,
            "promotion_checks": promotion_checks,
            "promotion_gate_passed": all(promotion_checks.values()),
            "performance": {
                "fingerprint_seconds": round(scan_seconds, 6),
                "materialize_seconds": round(export_seconds, 6),
                "total_seconds": round(time.monotonic() - started, 6),
                "rows_per_second": round(
                    rows / max(time.monotonic() - started, 0.000001), 3
                ),
                "peak_rss_mb": peak_rss,
                "max_peak_rss_mb": float(max_peak_rss_mb),
            },
            "partitions": scanned_partitions,
            "limitations": [
                "Observed-label person links are not externally verified identity.",
                "Local materialization does not prove durable public-origin publication.",
                "Vote-lane promotion remains blocked until official totals reconcile at or above 95 percent.",
            ],
        }
        if enforce and not analytical_gate_passed:
            failed = [key for key, value in checks.items() if not value]
            raise RuntimeError(
                "analytical partition gate failed: " + ", ".join(failed)
            )
        manifest_path = staging_root / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        staging_root.rename(output_root)
    except BaseException:
        shutil.rmtree(staging_root, ignore_errors=True)
        raise

    return manifest


__all__ = [
    "LANE",
    "MANIFEST_SCHEMA_VERSION",
    "MEMBER_VOTE_COLUMNS",
    "MEMBER_VOTE_SCHEMA",
    "TRANSFORMER_VERSION",
    "export_member_vote_partitions",
    "scan_member_vote_partitions",
]
