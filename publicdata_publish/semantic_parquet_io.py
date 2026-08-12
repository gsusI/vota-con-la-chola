"""Bounded Parquet file writing and verified partition reuse."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from .semantic_contracts import SemanticLaneContract, sha256_file


class PartitionWriter:
    def __init__(
        self,
        *,
        root: Path,
        partition: dict[str, Any],
        contract: SemanticLaneContract,
        compression: str,
        row_group_rows: int,
        max_file_rows: int,
    ) -> None:
        self.root = root
        self.partition = partition
        self.contract = contract
        self.compression = None if compression == "none" else compression
        self.row_group_rows = row_group_rows
        self.max_file_rows = max_file_rows
        self.schema = contract.arrow_schema()
        self.columns = {name: [] for name in contract.columns}
        self.buffered = 0
        self.rows_written = 0
        self.file_index = 0
        self.file_rows = 0
        self.file_min_id: str | int | None = None
        self.file_max_id: str | int | None = None
        self.writer = None
        self.files: list[dict[str, Any]] = []

    def append(self, row: dict[str, Any]) -> None:
        for name in self.contract.columns:
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
                "sha256": sha256_file(abs_path),
                "min_id": self.file_min_id,
                "max_id": self.file_max_id,
            }
        )
        self.file_index += 1
        self.writer = None

    def _write_table(self, table) -> None:
        import pyarrow.compute as pc  # type: ignore

        offset = 0
        while offset < table.num_rows:
            if self.writer is None:
                self._open_file()
            available = self.max_file_rows - self.file_rows
            take = min(available, table.num_rows - offset)
            piece = table.slice(offset, take)
            ids = piece.column(self.contract.id_column)
            id_bounds = pc.min_max(ids).as_py()
            piece_min_id = id_bounds["min"]
            piece_max_id = id_bounds["max"]
            self.writer.write_table(piece, row_group_size=self.row_group_rows)
            self.file_rows += take
            self.rows_written += take
            self.file_min_id = (
                piece_min_id
                if self.file_min_id is None
                else min(self.file_min_id, piece_min_id)
            )
            self.file_max_id = (
                piece_max_id
                if self.file_max_id is None
                else max(self.file_max_id, piece_max_id)
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
        self.columns = {name: [] for name in self.contract.columns}
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


def reusable_partition(
    *,
    partition: dict[str, Any],
    previous: dict[str, Any] | None,
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
        if sha256_file(source) != str(file_meta["sha256"]):
            return None
    return previous


def reuse_partition_files(
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


__all__ = ["PartitionWriter", "reusable_partition", "reuse_partition_files"]
