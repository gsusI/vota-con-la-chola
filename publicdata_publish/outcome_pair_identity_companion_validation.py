"""Independent bounded validation for the real C2B identity companion."""

from __future__ import annotations

import hashlib
import heapq
import itertools
import re
import sqlite3
import stat
import tempfile
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager, nullcontext
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from .outcome_pair_identity_companion import (
    ACTION_CONTRACT,
    ACTION_ROW_CONTRACT_VERSION,
    CANONICAL_COMPRESSION,
    CANONICAL_COMPRESSION_LEVEL,
    CANONICAL_DATA_PAGE_VERSION,
    CANONICAL_DICTIONARY_PAGE_SIZE_LIMIT,
    CANONICAL_MAX_FILE_ROWS,
    CANONICAL_PARQUET_CREATED_BY,
    CANONICAL_PARQUET_FORMAT_VERSION,
    CANONICAL_PYARROW_VERSION,
    CANONICAL_ROW_GROUP_ROWS,
    CANONICAL_SOURCE_PAGE_SIZE,
    CANONICAL_WRITE_BATCH_SIZE,
    EXECUTED_ACTION_SCAN_SQL_SHA256,
    EXECUTED_MEMBER_SCAN_SQL_SHA256,
    EXPECTED_ACTION_ROWS_ROOT_SHA256,
    EXPECTED_ACTION_YEARS,
    EXPECTED_ACTIONS,
    EXPECTED_CONFIG_CANONICAL_SHA256,
    EXPECTED_CONFIG_FILE_SHA256,
    EXPECTED_MEMBER_COMPONENT_ROOT_SHA256,
    EXPECTED_MEMBER_ROWS,
    EXPECTED_MEMBER_ROWS_ROOT_SHA256,
    EXPECTED_OFFICIAL_NAMES,
    EXPECTED_OFFICIAL_NAMES_ROOT_SHA256,
    EXPECTED_PACKAGE_SEMANTIC_ROOT_SHA256,
    EXPECTED_PAIR_PLAN_DATABASE_BYTES,
    EXPECTED_PAIR_PLAN_DATABASE_SHA256,
    EXPECTED_PAIR_PLAN_PIPELINE_KEY,
    EXPECTED_SOURCE_DATABASE_BYTES,
    EXPECTED_SOURCE_DATABASE_SHA256,
    MANIFEST_SCHEMA_VERSION,
    MAX_JSON_BYTES,
    MAX_PACKAGE_PARQUET_BYTES,
    MAX_PARQUET_FILE_BYTES,
    MAXIMUM_PEAK_RSS_MB,
    MEMBER_CONTRACT,
    MEMBER_OUTPUT_ORDER_SQL,
    MEMBER_PROJECTION_FIELD_MAP,
    MEMBER_PROJECTION_FIELDS,
    MEMBER_ROW_CONTRACT_VERSION,
    PACKAGE_ROOT_CONTRACT_VERSION,
    POLICY,
    TRANSFORMER_VERSION,
    _action_from_member_join,
    _action_output_row,
    _assert_action_plan_parity,
    _member_output_row,
    _row_semantic_sha256,
    _scratch_connection,
    _source_member_from_stage,
    _stage_real_inputs,
    assert_pinned_real_input_paths,
    canonical_bytes,
    canonical_sha256,
    load_json_bytes,
    open_readonly_database,
    repo_path,
    require_canonical_pyarrow,
    stream_hash_add,
    stream_root,
    validate_config,
)
from .outcome_pair_identity_safety import (
    FileIdentity,
    assert_regular_file_stable,
    bound_regular_file,
    exact_regular_inventory,
    identity_companion_leases,
    require_bounded_finite_float,
    require_bounded_int,
    require_exact_int,
)
from .semantic_contracts import peak_rss_mb

VALIDATION_SCHEMA_VERSION = "outcome_pair_identity_companion_validation_v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CONTENT_FILE_RE = re.compile(r"^part-([0-9a-f]{64})\.parquet$")
IDENTITY_INVENTORY_MAX_FILES = 16
IDENTITY_INVENTORY_MAX_DIRECTORIES = 16
IDENTITY_INVENTORY_MAX_DEPTH = 8
IDENTITY_INVENTORY_MAX_PATH_BYTES = 512


def _manifest_root(manifest: dict[str, Any]) -> str:
    return canonical_sha256(
        {key: value for key, value in manifest.items() if key != "manifest_root_sha256"}
    )


def _is_sha256(value: Any) -> bool:
    return type(value) is str and bool(SHA256_RE.fullmatch(value))


def _exact_int(name: str, value: Any, expected: int | None = None) -> int:
    if type(value) is not int:
        raise RuntimeError(f"{name} must be an exact JSON integer")
    if expected is not None and value != expected:
        raise RuntimeError(f"{name} differs from the exact contract")
    return value


def _exact_bool(name: str, value: Any, expected: bool) -> None:
    if type(value) is not bool or value is not expected:
        raise RuntimeError(f"{name} differs from the exact boolean contract")


def _exact_senate_url(value: Any) -> bool:
    raw = str(value or "")
    if not raw or raw.strip() != raw:
        return False
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and (parsed.hostname or "").lower() == "www.senado.es"
        and parsed.username is None
        and parsed.password is None
        and not parsed.fragment
    )


def _safe_package_child(root: Path, relative: str) -> Path:
    if type(relative) is not str or not relative or "\\" in relative:
        raise RuntimeError("package relative path is non-canonical")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise RuntimeError("package relative path is unsafe")
    candidate = root.joinpath(*pure.parts)
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root.resolve(strict=True))
    except ValueError as exc:
        raise RuntimeError("package relative path escapes root") from exc
    return candidate


def _validate_member_row(row: dict[str, Any], expected_year: int) -> None:
    for name in (
        "action_id",
        "action_date",
        "action_label",
        "official_action_url",
        "action_source_page_url",
        "action_source_record_id",
        "seat",
        "member_name",
        "member_name_normalized",
        "person_id",
        "group_code",
        "vote_choice",
        "source_id",
        "member_source_url",
        "source_snapshot_date",
    ):
        if not str(row[name] or "").strip():
            raise RuntimeError("identity row has an empty official field")
    if int(row["member_vote_id"]) < 1 or int(row["action_source_record_pk"]) < 1:
        raise RuntimeError("identity row has an invalid stable ID")
    if not str(row["person_id"]).isdigit() or int(row["person_id"]) < 1:
        raise RuntimeError("identity row has an invalid official person ID")
    if int(row["action_year"]) != expected_year:
        raise RuntimeError("identity row is in the wrong year partition")
    if str(row["action_date"])[:4] != str(expected_year):
        raise RuntimeError("identity row action date and year differ")
    if not all(
        _exact_senate_url(row[name])
        for name in (
            "official_action_url",
            "action_source_page_url",
            "member_source_url",
        )
    ):
        raise RuntimeError(
            "identity row does not preserve an exact official Senate URL"
        )
    if str(row["action_id"]) != f"url:{row['official_action_url']}":
        raise RuntimeError("identity row action ID does not preserve official URL")
    if str(row["action_source_record_id"]) != str(row["action_id"]):
        raise RuntimeError("identity row source-record ID drifted")
    if not _is_sha256(row["action_source_record_content_sha256"]):
        raise RuntimeError("identity row source evidence hash is invalid")
    if str(row["source_id"]) != "senado_votaciones":
        raise RuntimeError("identity row source ID drifted")
    if str(row["source_snapshot_date"]) != "2026-02-12":
        raise RuntimeError("identity row source snapshot drifted")
    if (
        str(row["evidence_level"]) != "L0"
        or str(row["companion_state"]) != "internal_identity_companion"
        or int(row["ranking_eligible"]) != 0
        or int(row["publication_eligible"]) != 0
    ):
        raise RuntimeError("identity row internal zero-claim policy drifted")
    if row["row_semantic_sha256"] != _row_semantic_sha256(
        MEMBER_ROW_CONTRACT_VERSION,
        {key: value for key, value in row.items() if key != "row_semantic_sha256"},
    ):
        raise RuntimeError("identity row semantic digest mismatch")


def _validate_action_row(row: dict[str, Any]) -> None:
    if int(row["action_year"]) != int(str(row["action_date"])[:4]):
        raise RuntimeError("action projection date and year differ")
    if not _exact_senate_url(row["official_action_url"]):
        raise RuntimeError("action projection URL is not official")
    if not _exact_senate_url(row["action_source_page_url"]):
        raise RuntimeError("action projection page URL is not official")
    if str(row["action_id"]) != f"url:{row['official_action_url']}":
        raise RuntimeError("action projection identity drifted")
    if str(row["action_source_record_id"]) != str(row["action_id"]):
        raise RuntimeError("action projection source-record identity drifted")
    if not _is_sha256(row["action_source_record_content_sha256"]):
        raise RuntimeError("action projection source hash is invalid")
    if not _is_sha256(row["participant_projection_sha256"]):
        raise RuntimeError("action participant projection hash is invalid")
    if int(row["member_vote_count"]) < 1:
        raise RuntimeError("action projection member count is empty")
    if int(row["member_vote_count"]) != int(row["official_name_count"]):
        raise RuntimeError("action projection does not retain exact unique names")
    if (
        str(row["source_id"]) != "senado_votaciones"
        or str(row["source_snapshot_date"]) != "2026-02-12"
        or str(row["evidence_level"]) != "L0"
        or str(row["companion_state"]) != "internal_identity_companion"
        or int(row["ranking_eligible"]) != 0
        or int(row["publication_eligible"]) != 0
    ):
        raise RuntimeError("action projection zero-claim policy drifted")
    if row["row_semantic_sha256"] != _row_semantic_sha256(
        ACTION_ROW_CONTRACT_VERSION,
        {key: value for key, value in row.items() if key != "row_semantic_sha256"},
    ):
        raise RuntimeError("action projection semantic digest mismatch")


def _iter_parquet_rows(
    parquet_file: Any, contract: Any, batch_rows: int
) -> Iterator[dict[str, Any]]:
    for batch in parquet_file.iter_batches(batch_size=batch_rows, use_threads=False):
        columns = {
            name: batch.column(index).to_pylist()
            for index, name in enumerate(contract.columns)
        }
        for index in range(batch.num_rows):
            yield {name: columns[name][index] for name in contract.columns}


def _canonical_physical_replay(
    parquet_file: Any,
    contract: Any,
) -> tuple[int, str]:
    """Re-encode bounded real rows with the exact pinned writer and hash bytes."""

    import pyarrow as pa  # type: ignore
    import pyarrow.parquet as pq  # type: ignore

    with tempfile.TemporaryDirectory(prefix="identity-parquet-replay-") as temporary:
        replay_path = Path(temporary) / "canonical.parquet"
        writer = pq.ParquetWriter(
            replay_path,
            contract.arrow_schema(),
            compression=CANONICAL_COMPRESSION,
            compression_level=CANONICAL_COMPRESSION_LEVEL,
            use_dictionary=True,
            write_statistics=True,
            version=CANONICAL_PARQUET_FORMAT_VERSION,
            use_byte_stream_split=False,
            data_page_version=CANONICAL_DATA_PAGE_VERSION,
            use_compliant_nested_type=True,
            write_batch_size=CANONICAL_WRITE_BATCH_SIZE,
            dictionary_pagesize_limit=CANONICAL_DICTIONARY_PAGE_SIZE_LIMIT,
            store_schema=True,
            write_page_index=False,
            write_page_checksum=False,
            store_decimal_as_integer=False,
        )
        try:
            for batch in parquet_file.iter_batches(
                batch_size=CANONICAL_ROW_GROUP_ROWS,
                use_threads=False,
            ):
                writer.write_table(
                    pa.Table.from_batches([batch], schema=contract.arrow_schema()),
                    row_group_size=CANONICAL_ROW_GROUP_ROWS,
                )
        finally:
            writer.close()
        digest = hashlib.sha256()
        size = 0
        with replay_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
                size += len(chunk)
                digest.update(chunk)
        return size, digest.hexdigest()


@contextmanager
def _validated_parquet_file(
    *,
    root: Path,
    file_meta: dict[str, Any],
    contract: Any,
    expected_rows: int,
    batch_rows: int,
) -> Iterator[tuple[Path, Any, FileIdentity]]:
    import pyarrow.parquet as pq  # type: ignore

    if set(file_meta) != {
        "path",
        "rows",
        "bytes",
        "sha256",
        "semantic_sha256",
        "min_id",
        "max_id",
    }:
        raise RuntimeError("Parquet file metadata keys drifted")
    rows = _exact_int("Parquet file rows", file_meta["rows"], expected_rows)
    size = _exact_int("Parquet file bytes", file_meta["bytes"])
    if rows < 1 or size < 1 or size > MAX_PARQUET_FILE_BYTES:
        raise RuntimeError("Parquet file violates hard physical bounds")
    if not _is_sha256(file_meta["sha256"]) or not _is_sha256(
        file_meta["semantic_sha256"]
    ):
        raise RuntimeError("Parquet file hash metadata is invalid")
    if contract is MEMBER_CONTRACT:
        if type(file_meta["min_id"]) is not int or type(file_meta["max_id"]) is not int:
            raise RuntimeError("member Parquet ID bounds must be exact JSON integers")
    elif type(file_meta["min_id"]) is not str or type(file_meta["max_id"]) is not str:
        raise RuntimeError("action Parquet ID bounds must be JSON strings")
    relative = file_meta["path"]
    if type(relative) is not str:
        raise RuntimeError("Parquet file path must be a JSON string")
    match = CONTENT_FILE_RE.fullmatch(PurePosixPath(relative).name)
    if not match or match.group(1) != file_meta["semantic_sha256"]:
        raise RuntimeError("Parquet file is not content-addressed")
    path = _safe_package_child(root, relative)
    with bound_regular_file(path) as bound:
        if bound.identity.size != size:
            raise RuntimeError("Parquet file byte count mismatch")
        binary_sha256 = bound.sha256()
        if binary_sha256 != file_meta["sha256"]:
            raise RuntimeError("Parquet file binary checksum mismatch")
        parquet_file = pq.ParquetFile(bound.handle)
        if not parquet_file.schema_arrow.equals(
            contract.arrow_schema(), check_metadata=True
        ):
            raise RuntimeError("Parquet Arrow schema or metadata mismatch")
        metadata = parquet_file.metadata
        if str(metadata.format_version) != CANONICAL_PARQUET_FORMAT_VERSION:
            raise RuntimeError("Parquet format version drifted")
        if metadata.created_by != CANONICAL_PARQUET_CREATED_BY:
            raise RuntimeError("Parquet writer runtime metadata drifted")
        if int(metadata.num_rows) != rows:
            raise RuntimeError("Parquet file row count mismatch")
        expected_groups = (
            rows + CANONICAL_ROW_GROUP_ROWS - 1
        ) // CANONICAL_ROW_GROUP_ROWS
        if int(metadata.num_row_groups) != expected_groups:
            raise RuntimeError("Parquet row-group count is not deterministic")
        for group_index in range(expected_groups):
            group = metadata.row_group(group_index)
            expected_group_rows = (
                CANONICAL_ROW_GROUP_ROWS
                if group_index < expected_groups - 1
                else rows - CANONICAL_ROW_GROUP_ROWS * (expected_groups - 1)
            )
            if int(group.num_rows) != expected_group_rows or expected_group_rows < 1:
                raise RuntimeError("Parquet row-group segmentation drifted")
            for column_index in range(group.num_columns):
                column = group.column(column_index)
                if column.compression != CANONICAL_COMPRESSION.upper():
                    raise RuntimeError("Parquet compression metadata drifted")
                if "RLE_DICTIONARY" not in set(column.encodings):
                    raise RuntimeError("Parquet dictionary encoding is missing")
                statistics = column.statistics
                if (
                    statistics is None
                    or not statistics.has_min_max
                    or statistics.null_count != 0
                ):
                    raise RuntimeError("Parquet statistics contract drifted")
        replay_size, replay_sha256 = _canonical_physical_replay(
            parquet_file,
            contract,
        )
        if replay_size != size or replay_sha256 != binary_sha256:
            raise RuntimeError(
                "Parquet bytes differ from exact canonical writer replay"
            )
        # Exact normal path API regression gate. Non-Hive paths prevent duplicate
        # action_year partition inference.
        ordinary = pq.read_table(path, use_threads=False)
        if ordinary.num_rows != rows or not ordinary.schema.equals(
            contract.arrow_schema(), check_metadata=True
        ):
            raise RuntimeError("ordinary PyArrow read_table compatibility failed")
        del ordinary
        yield path, parquet_file, bound.identity
        if bound.sha256() != binary_sha256:
            raise RuntimeError("Parquet file changed during validation")


def _expected_file_rows(table_rows: int, file_index: int, file_count: int) -> int:
    expected_count = (
        table_rows + CANONICAL_MAX_FILE_ROWS - 1
    ) // CANONICAL_MAX_FILE_ROWS
    if file_count != expected_count or file_count < 1:
        raise RuntimeError("Parquet file count is not deterministic")
    if file_index < file_count - 1:
        return CANONICAL_MAX_FILE_ROWS
    remainder = table_rows - CANONICAL_MAX_FILE_ROWS * (file_count - 1)
    if remainder < 1 or remainder > CANONICAL_MAX_FILE_ROWS:
        raise RuntimeError("final Parquet file segmentation is invalid")
    return remainder


def _read_partition_rows(
    *,
    root: Path,
    partition: dict[str, Any],
    batch_rows: int,
) -> Iterator[dict[str, Any]]:
    import pyarrow.parquet as pq  # type: ignore

    for file_meta in partition["files"]:
        path = _safe_package_child(root, file_meta["path"])
        with bound_regular_file(path) as bound:
            if (
                bound.identity.size != file_meta["bytes"]
                or bound.sha256() != file_meta["sha256"]
            ):
                raise RuntimeError("Parquet evidence changed before source parity")
            parquet_file = pq.ParquetFile(bound.handle)
            yield from _iter_parquet_rows(parquet_file, MEMBER_CONTRACT, batch_rows)


def _member_rows_in_source_order(
    *,
    root: Path,
    partitions: list[dict[str, Any]],
    batch_rows: int,
) -> Iterator[dict[str, Any]]:
    yield from heapq.merge(
        *(
            _read_partition_rows(root=root, partition=partition, batch_rows=batch_rows)
            for partition in partitions
        ),
        key=lambda row: (str(row["action_id"]), int(row["member_vote_id"])),
    )


def _dataset_api_gate(
    *,
    root: Path,
    partitions: list[dict[str, Any]],
    member_rows: int,
    action_rows: int,
    batch_rows: int,
) -> None:
    import pyarrow.dataset as ds  # type: ignore

    member_dataset = ds.dataset(root / "member_vote_identities", format="parquet")
    if not member_dataset.schema.equals(
        MEMBER_CONTRACT.arrow_schema(), check_metadata=True
    ):
        raise RuntimeError("member PyArrow dataset schema compatibility failed")
    scanned = sum(
        batch.num_rows
        for batch in member_dataset.scanner(
            batch_size=batch_rows, use_threads=False
        ).to_batches()
    )
    if scanned != member_rows:
        raise RuntimeError("member PyArrow dataset scan count drifted")
    for partition in partitions:
        year = partition["values"]["action_year"]
        filtered = member_dataset.count_rows(filter=ds.field("action_year") == year)
        if filtered != partition["rows"]:
            raise RuntimeError("member PyArrow dataset filter count drifted")
    action_dataset = ds.dataset(
        root / "action_participant_projections", format="parquet"
    )
    if not action_dataset.schema.equals(
        ACTION_CONTRACT.arrow_schema(), check_metadata=True
    ):
        raise RuntimeError("action PyArrow dataset schema compatibility failed")
    if action_dataset.count_rows() != action_rows:
        raise RuntimeError("action PyArrow dataset count drifted")


def _root_identity(path: Path) -> tuple[int, ...]:
    value = path.lstat()
    if path.is_symlink() or not stat.S_ISDIR(value.st_mode):
        raise RuntimeError("identity companion root is missing or unsafe")
    return (
        int(value.st_dev),
        int(value.st_ino),
        int(value.st_mtime_ns),
        int(value.st_ctime_ns),
        int(value.st_nlink),
    )


def _assert_exact_inventory(
    root: Path, declared_files: set[str], declared_directories: set[str]
) -> tuple[set[str], set[str]]:
    actual_files, actual_directories = exact_regular_inventory(
        root,
        max_files=IDENTITY_INVENTORY_MAX_FILES,
        max_directories=IDENTITY_INVENTORY_MAX_DIRECTORIES,
        max_depth=IDENTITY_INVENTORY_MAX_DEPTH,
        max_path_bytes=IDENTITY_INVENTORY_MAX_PATH_BYTES,
    )
    if actual_files != declared_files or actual_directories != declared_directories:
        raise RuntimeError("package inode inventory differs from exact declaration")
    return actual_files, actual_directories


def validate_outcome_pair_identity_companion(
    *,
    root: Path,
    manifest_path: Path | None,
    source_db_path: Path,
    config_path: Path,
    pair_plan_db_path: Path,
    batch_rows: int = 5_000,
    source_page_size: int = CANONICAL_SOURCE_PAGE_SIZE,
    max_peak_rss_mb: float = MAXIMUM_PEAK_RSS_MB,
    _leases_held: bool = False,
) -> dict[str, Any]:
    """Validate inventory, physical layout, every row, and exact source parity."""
    process_peak_at_entry = peak_rss_mb()
    require_canonical_pyarrow()
    batch_rows = require_bounded_int(
        "batch_rows", batch_rows, minimum=1, maximum=CANONICAL_ROW_GROUP_ROWS
    )
    require_exact_int("source_page_size", source_page_size, CANONICAL_SOURCE_PAGE_SIZE)
    rss_limit = require_bounded_finite_float(
        "max_peak_rss_mb",
        max_peak_rss_mb,
        minimum_exclusive=0.0,
        maximum=MAXIMUM_PEAK_RSS_MB,
    )
    root_input = Path(root)
    if root_input.is_symlink():
        raise RuntimeError("identity companion root must not be a symlink")
    try:
        root = root_input.resolve(strict=True)
    except FileNotFoundError as exc:
        raise RuntimeError("identity companion root is missing") from exc
    source_db_path = Path(source_db_path)
    config_path = Path(config_path)
    pair_plan_db_path = Path(pair_plan_db_path)
    assert_pinned_real_input_paths(source_db_path, config_path, pair_plan_db_path)
    external_path = Path(manifest_path) if manifest_path is not None else None
    lease_targets = [root, source_db_path, config_path, pair_plan_db_path]
    if external_path is not None:
        lease_targets.append(external_path)
    lease_context = (
        nullcontext()
        if _leases_held
        else identity_companion_leases(lease_targets, namespace="evidence")
    )
    with lease_context, ExitStack() as evidence:
        root_identity = _root_identity(root)
        initial_files, initial_directories = exact_regular_inventory(
            root,
            max_files=IDENTITY_INVENTORY_MAX_FILES,
            max_directories=IDENTITY_INVENTORY_MAX_DIRECTORIES,
            max_depth=IDENTITY_INVENTORY_MAX_DEPTH,
            max_path_bytes=IDENTITY_INVENTORY_MAX_PATH_BYTES,
        )
        root_manifest_path = root / "manifest.json"
        root_manifest = evidence.enter_context(bound_regular_file(root_manifest_path))
        manifest_bytes = root_manifest.read_bytes(max_bytes=MAX_JSON_BYTES)
        manifest_file_sha256 = root_manifest.sha256()
        if external_path is not None:
            external_manifest = evidence.enter_context(
                bound_regular_file(external_path)
            )
            if external_manifest.read_bytes(max_bytes=MAX_JSON_BYTES) != manifest_bytes:
                raise RuntimeError("external and package manifests differ")
            external_manifest_sha256 = external_manifest.sha256()
        else:
            external_manifest = None
            external_manifest_sha256 = None
        manifest = load_json_bytes(manifest_bytes)
        if set(manifest) != {
            "schema_version",
            "transformer_version",
            "contract_date",
            "created_at",
            "scope_revision",
            "source",
            "reference_pair_plan",
            "policy",
            "layout",
            "tables",
            "counts",
            "roots",
            "parquet_bytes",
            "package_semantic_root_sha256",
            "checks",
            "publication_gate_passed",
            "ranking_gate_passed",
            "manifest_root_sha256",
        }:
            raise RuntimeError("identity companion manifest keys drifted")
        if manifest["schema_version"] != MANIFEST_SCHEMA_VERSION:
            raise RuntimeError("identity companion manifest schema drifted")
        if manifest["transformer_version"] != TRANSFORMER_VERSION:
            raise RuntimeError("identity companion transformer drifted")
        if manifest["policy"] != POLICY:
            raise RuntimeError("identity companion policy drifted")
        _exact_bool(
            "publication_gate_passed", manifest["publication_gate_passed"], False
        )
        _exact_bool("ranking_gate_passed", manifest["ranking_gate_passed"], False)
        if manifest["manifest_root_sha256"] != _manifest_root(manifest):
            raise RuntimeError("identity companion manifest root mismatch")

        config_bound = evidence.enter_context(bound_regular_file(config_path))
        source_bound = evidence.enter_context(
            bound_regular_file(source_db_path, database=True)
        )
        plan_bound = evidence.enter_context(
            bound_regular_file(pair_plan_db_path, database=True)
        )
        config_sha = config_bound.sha256()
        plan_sha = plan_bound.sha256()
        if config_sha != EXPECTED_CONFIG_FILE_SHA256:
            raise RuntimeError("C2B config file hash mismatch")
        if (plan_sha, plan_bound.identity.size) != (
            EXPECTED_PAIR_PLAN_DATABASE_SHA256,
            EXPECTED_PAIR_PLAN_DATABASE_BYTES,
        ):
            raise RuntimeError("C2B pair-plan reference bytes mismatch")
        config = load_json_bytes(config_bound.read_bytes(max_bytes=MAX_JSON_BYTES))
        validate_config(config)
        if canonical_sha256(config) != EXPECTED_CONFIG_CANONICAL_SHA256:
            raise RuntimeError("C2B config canonical root mismatch")
        if (
            manifest["contract_date"] != config["contract_date"]
            or manifest["created_at"] != f"{config['contract_date']}T00:00:00Z"
            or _exact_int("scope_revision", manifest["scope_revision"])
            != config["scope_revision"]
        ):
            raise RuntimeError("identity companion config revision binding drifted")
        expected_source = {
            "config_path": repo_path(config_bound.path),
            "config_file_bytes": config_bound.identity.size,
            "config_file_sha256": config_sha,
            "config_canonical_sha256": EXPECTED_CONFIG_CANONICAL_SHA256,
            # The manifest records the original full-file provenance. Runtime
            # equivalence is established later from exact scoped projections,
            # so unrelated additive tables cannot invalidate this package.
            "database_path": str(config["sources"]["actions"]["path"]),
            "database_bytes": int(config["sources"]["actions"]["bytes"]),
            "database_sha256": str(config["sources"]["actions"]["sha256"]),
            "source_id": "senado_votaciones",
            "source_snapshot_date": "2026-02-12",
            "executed_actions_scan_sql_sha256": EXECUTED_ACTION_SCAN_SQL_SHA256,
            "executed_members_scan_sql_sha256": EXECUTED_MEMBER_SCAN_SQL_SHA256,
            "configured_actions_keyset_sql_sha256": config["query_contract"][
                "actions_keyset_sql_sha256"
            ],
            "configured_members_keyset_sql_sha256": config["query_contract"][
                "members_keyset_sql_sha256"
            ],
        }
        if manifest["source"] != expected_source:
            raise RuntimeError("identity companion source proof drifted")
        expected_plan = {
            "database_path": repo_path(plan_bound.path),
            "database_bytes": plan_bound.identity.size,
            "database_sha256": plan_sha,
            "pipeline_key": EXPECTED_PAIR_PLAN_PIPELINE_KEY,
            "role": "read_only_per_action_projection_parity_reference",
        }
        if manifest["reference_pair_plan"] != expected_plan:
            raise RuntimeError("identity companion plan-reference proof drifted")

        if manifest["layout"] != {
            "compression": CANONICAL_COMPRESSION,
            "compression_level": CANONICAL_COMPRESSION_LEVEL,
            "row_group_rows": CANONICAL_ROW_GROUP_ROWS,
            "max_file_rows": CANONICAL_MAX_FILE_ROWS,
            "partition_key": "action_year",
            "partition_directory_contract": "member_vote_identities/by_action_year/{year}",
            "file_name_contract": "part-{semantic_sha256}.parquet",
            "content_address": "SHA-256 of ordered canonical persisted rows",
            "pyarrow_version": CANONICAL_PYARROW_VERSION,
            "parquet_created_by": CANONICAL_PARQUET_CREATED_BY,
            "parquet_format_version": CANONICAL_PARQUET_FORMAT_VERSION,
            "data_page_version": CANONICAL_DATA_PAGE_VERSION,
            "write_batch_size": CANONICAL_WRITE_BATCH_SIZE,
            "dictionary_page_size_limit_bytes": (CANONICAL_DICTIONARY_PAGE_SIZE_LIMIT),
            "dictionary_encoding": True,
            "statistics": True,
            "byte_stream_split": False,
            "compliant_nested_types": True,
            "store_arrow_schema": True,
            "page_index": False,
            "page_checksum": False,
            "decimal_as_integer": False,
        }:
            raise RuntimeError("identity companion physical layout drifted")
        tables = manifest["tables"]
        if type(tables) is not dict or set(tables) != {
            "member_vote_identities",
            "action_participant_projections",
        }:
            raise RuntimeError("identity companion table inventory drifted")
        member_table = tables["member_vote_identities"]
        action_table = tables["action_participant_projections"]
        if set(member_table) != {
            "schema",
            "schema_sha256",
            "participant_projection_fields",
            "participant_projection_field_map",
            "rows",
            "partitions",
        }:
            raise RuntimeError("member identity table metadata keys drifted")
        if (
            member_table["schema"] != list(MEMBER_CONTRACT.schema)
            or member_table["schema_sha256"] != MEMBER_CONTRACT.schema_sha256
            or member_table["participant_projection_fields"]
            != list(MEMBER_PROJECTION_FIELDS)
            or member_table["participant_projection_field_map"]
            != MEMBER_PROJECTION_FIELD_MAP
        ):
            raise RuntimeError("member projection schema or explicit field map drifted")
        member_rows_declared = _exact_int(
            "member table rows", member_table["rows"], EXPECTED_MEMBER_ROWS
        )
        if set(action_table) != {
            "schema",
            "schema_sha256",
            "rows",
            "relative_dir",
            "input_sha256",
            "files",
        }:
            raise RuntimeError("action projection table metadata keys drifted")
        if (
            action_table["schema"] != list(ACTION_CONTRACT.schema)
            or action_table["schema_sha256"] != ACTION_CONTRACT.schema_sha256
            or action_table["relative_dir"] != "action_participant_projections"
            or not _is_sha256(action_table["input_sha256"])
        ):
            raise RuntimeError("action projection table contract drifted")
        action_rows_declared = _exact_int(
            "action table rows", action_table["rows"], EXPECTED_ACTIONS
        )

        with tempfile.TemporaryDirectory(
            prefix="identity-companion-validation-"
        ) as temporary:
            scratch = _scratch_connection(Path(temporary) / "validation.sqlite3")
            scratch.executescript(
                """
                CREATE TABLE seen_member_ids(member_vote_id INTEGER PRIMARY KEY);
                CREATE TABLE package_names(member_name TEXT PRIMARY KEY) WITHOUT ROWID;
                CREATE TABLE package_action_rows(
                  action_id TEXT PRIMARY KEY,row_json TEXT NOT NULL
                ) WITHOUT ROWID;
                """
            )
            source_connection = open_readonly_database(source_bound)
            plan_connection = open_readonly_database(plan_bound)
            package_identities: dict[str, FileIdentity] = {}
            package_binary_hashes: dict[str, str] = {}
            try:
                _stage_real_inputs(
                    source_connection=source_connection,
                    plan_connection=plan_connection,
                    scratch=scratch,
                    config=config,
                    batch_rows=source_page_size,
                )
                partitions = member_table["partitions"]
                if type(partitions) is not list or len(partitions) != len(
                    EXPECTED_ACTION_YEARS
                ):
                    raise RuntimeError(
                        "member partitions must equal exact real year scope"
                    )
                declared_files = {"manifest.json"}
                declared_directories = {
                    ".",
                    "member_vote_identities",
                    "member_vote_identities/by_action_year",
                    "action_participant_projections",
                }
                member_rows = member_files = member_bytes = 0
                for partition_index, partition in enumerate(partitions):
                    if type(partition) is not dict or set(partition) != {
                        "partition_id",
                        "relative_dir",
                        "values",
                        "rows",
                        "input_sha256",
                        "files",
                    }:
                        raise RuntimeError("member partition metadata keys drifted")
                    year = EXPECTED_ACTION_YEARS[partition_index]
                    if partition["values"] != {"action_year": year}:
                        raise RuntimeError("member partition year scope drifted")
                    expected_dir = f"member_vote_identities/by_action_year/{year}"
                    if (
                        partition["partition_id"] != f"action_year={year}"
                        or partition["relative_dir"] != expected_dir
                        or not _is_sha256(partition["input_sha256"])
                    ):
                        raise RuntimeError("member partition identity drifted")
                    declared_directories.add(expected_dir)
                    partition_rows_expected = _exact_int(
                        "partition rows", partition["rows"]
                    )
                    files = partition["files"]
                    if (
                        partition_rows_expected < 1
                        or type(files) is not list
                        or not files
                    ):
                        raise RuntimeError("empty member partition is forbidden")
                    partition_digest = hashlib.sha256()
                    partition_rows = 0
                    previous_key: tuple[str, int] | None = None
                    for file_index, file_meta in enumerate(files):
                        expected_rows = _expected_file_rows(
                            partition_rows_expected, file_index, len(files)
                        )
                        with _validated_parquet_file(
                            root=root,
                            file_meta=file_meta,
                            contract=MEMBER_CONTRACT,
                            expected_rows=expected_rows,
                            batch_rows=batch_rows,
                        ) as (path, parquet_file, identity):
                            if path.parent.relative_to(root).as_posix() != expected_dir:
                                raise RuntimeError(
                                    "member Parquet file is in wrong partition"
                                )
                            relative = path.relative_to(root).as_posix()
                            if relative in declared_files:
                                raise RuntimeError("duplicate declared package path")
                            declared_files.add(relative)
                            package_identities[relative] = identity
                            package_binary_hashes[relative] = file_meta["sha256"]
                            file_digest = hashlib.sha256()
                            file_rows = 0
                            file_min: int | None = None
                            file_max: int | None = None
                            ids: list[tuple[int]] = []
                            names: list[tuple[str]] = []
                            for row in _iter_parquet_rows(
                                parquet_file, MEMBER_CONTRACT, batch_rows
                            ):
                                _validate_member_row(row, year)
                                order_key = (
                                    str(row["action_id"]),
                                    int(row["member_vote_id"]),
                                )
                                if (
                                    previous_key is not None
                                    and order_key <= previous_key
                                ):
                                    raise RuntimeError(
                                        "member partition order is not strict"
                                    )
                                previous_key = order_key
                                member_id = int(row["member_vote_id"])
                                ids.append((member_id,))
                                names.append((str(row["member_name"]),))
                                encoded = MEMBER_CONTRACT.canonical_row_bytes(row)
                                file_digest.update(encoded)
                                partition_digest.update(encoded)
                                file_min = (
                                    member_id
                                    if file_min is None
                                    else min(file_min, member_id)
                                )
                                file_max = (
                                    member_id
                                    if file_max is None
                                    else max(file_max, member_id)
                                )
                                file_rows += 1
                                if len(ids) == batch_rows:
                                    scratch.executemany(
                                        "INSERT INTO seen_member_ids VALUES(?)", ids
                                    )
                                    scratch.executemany(
                                        "INSERT OR IGNORE INTO package_names VALUES(?)",
                                        names,
                                    )
                                    ids, names = [], []
                            if ids:
                                scratch.executemany(
                                    "INSERT INTO seen_member_ids VALUES(?)", ids
                                )
                                scratch.executemany(
                                    "INSERT OR IGNORE INTO package_names VALUES(?)",
                                    names,
                                )
                            if (
                                file_rows != file_meta["rows"]
                                or file_digest.hexdigest()
                                != file_meta["semantic_sha256"]
                                or file_min != file_meta["min_id"]
                                or file_max != file_meta["max_id"]
                            ):
                                raise RuntimeError(
                                    "member Parquet semantic proof mismatch"
                                )
                            partition_rows += file_rows
                            member_files += 1
                            member_bytes += file_meta["bytes"]
                    if (
                        partition_rows != partition_rows_expected
                        or partition_digest.hexdigest() != partition["input_sha256"]
                    ):
                        raise RuntimeError("member partition semantic proof mismatch")
                    member_rows += partition_rows
                if member_rows != member_rows_declared:
                    raise RuntimeError("member table total drifted")
                if (
                    scratch.execute("SELECT COUNT(*) FROM seen_member_ids").fetchone()[
                        0
                    ]
                    != EXPECTED_MEMBER_ROWS
                ):
                    raise RuntimeError(
                        "member-vote identities are missing or duplicated"
                    )
                if (
                    scratch.execute("SELECT COUNT(*) FROM package_names").fetchone()[0]
                    != EXPECTED_OFFICIAL_NAMES
                ):
                    raise RuntimeError("exact official names are missing")

                action_files = action_table["files"]
                if type(action_files) is not list or not action_files:
                    raise RuntimeError("empty action projection table is forbidden")
                action_digest = hashlib.sha256()
                action_bytes = action_rows = 0
                previous_action_id: str | None = None
                for file_index, file_meta in enumerate(action_files):
                    expected_rows = _expected_file_rows(
                        action_rows_declared, file_index, len(action_files)
                    )
                    with _validated_parquet_file(
                        root=root,
                        file_meta=file_meta,
                        contract=ACTION_CONTRACT,
                        expected_rows=expected_rows,
                        batch_rows=batch_rows,
                    ) as (path, parquet_file, identity):
                        if (
                            path.parent.relative_to(root).as_posix()
                            != "action_participant_projections"
                        ):
                            raise RuntimeError(
                                "action Parquet file is in wrong directory"
                            )
                        relative = path.relative_to(root).as_posix()
                        if relative in declared_files:
                            raise RuntimeError("duplicate declared package path")
                        declared_files.add(relative)
                        package_identities[relative] = identity
                        package_binary_hashes[relative] = file_meta["sha256"]
                        file_digest = hashlib.sha256()
                        file_rows = 0
                        file_min: str | None = None
                        file_max: str | None = None
                        staged_actions: list[tuple[str, str]] = []
                        for row in _iter_parquet_rows(
                            parquet_file, ACTION_CONTRACT, batch_rows
                        ):
                            _validate_action_row(row)
                            action_id = str(row["action_id"])
                            if (
                                previous_action_id is not None
                                and action_id <= previous_action_id
                            ):
                                raise RuntimeError(
                                    "action projection order is not strict"
                                )
                            previous_action_id = action_id
                            encoded = ACTION_CONTRACT.canonical_row_bytes(row)
                            file_digest.update(encoded)
                            action_digest.update(encoded)
                            file_min = (
                                action_id
                                if file_min is None
                                else min(file_min, action_id)
                            )
                            file_max = (
                                action_id
                                if file_max is None
                                else max(file_max, action_id)
                            )
                            staged_actions.append(
                                (action_id, canonical_bytes(row).decode("utf-8"))
                            )
                            file_rows += 1
                        scratch.executemany(
                            "INSERT INTO package_action_rows VALUES(?,?)",
                            staged_actions,
                        )
                        if (
                            file_rows != file_meta["rows"]
                            or file_digest.hexdigest() != file_meta["semantic_sha256"]
                            or file_min != file_meta["min_id"]
                            or file_max != file_meta["max_id"]
                        ):
                            raise RuntimeError("action Parquet semantic proof mismatch")
                        action_rows += file_rows
                        action_bytes += file_meta["bytes"]
                if (
                    action_rows != action_rows_declared
                    or action_digest.hexdigest() != action_table["input_sha256"]
                ):
                    raise RuntimeError("action projection table proof mismatch")
                scratch.commit()
                actual_files, actual_directories = _assert_exact_inventory(
                    root, declared_files, declared_directories
                )
                if (
                    initial_files != actual_files
                    or initial_directories != actual_directories
                ):
                    raise RuntimeError("package inventory changed during validation")
                if member_bytes + action_bytes > MAX_PACKAGE_PARQUET_BYTES:
                    raise RuntimeError("package Parquet bytes exceed hard bound")
                if (
                    _exact_int("manifest parquet bytes", manifest["parquet_bytes"])
                    != member_bytes + action_bytes
                ):
                    raise RuntimeError("identity companion Parquet byte total mismatch")

                _dataset_api_gate(
                    root=root,
                    partitions=partitions,
                    member_rows=member_rows,
                    action_rows=action_rows,
                    batch_rows=batch_rows,
                )

                package_iter = _member_rows_in_source_order(
                    root=root, partitions=partitions, batch_rows=batch_rows
                )
                source_iter = scratch.execute(MEMBER_OUTPUT_ORDER_SQL)
                name_counts = iter(
                    scratch.execute(
                        "SELECT action_id,COUNT(*) AS names FROM action_names "
                        "GROUP BY action_id ORDER BY action_id"
                    )
                )
                package_actions = iter(
                    scratch.execute(
                        "SELECT action_id,row_json FROM package_action_rows ORDER BY action_id"
                    )
                )
                plan_actions = iter(
                    scratch.execute("SELECT * FROM plan_actions ORDER BY action_id")
                )
                next_name = next(name_counts, None)
                next_package_action = next(package_actions, None)
                next_plan_action = next(plan_actions, None)
                current_action_id: str | None = None
                current_action: dict[str, Any] | None = None
                current_hasher = hashlib.sha256()
                current_count = 0
                member_component_hasher = hashlib.sha256()
                member_package_hasher = hashlib.sha256()
                parity_rows = verified_actions = 0

                def finish_action() -> None:
                    nonlocal next_name, next_package_action, next_plan_action
                    nonlocal current_action_id, current_action, current_hasher
                    nonlocal current_count, verified_actions
                    if current_action_id is None or current_action is None:
                        return
                    if (
                        next_name is None
                        or next_package_action is None
                        or next_plan_action is None
                        or str(next_name["action_id"]) != current_action_id
                        or str(next_package_action["action_id"]) != current_action_id
                        or str(next_plan_action["action_id"]) != current_action_id
                    ):
                        raise RuntimeError("action parity streams lost alignment")
                    aggregate = {
                        "member_vote_count": current_count,
                        "official_name_count": int(next_name["names"]),
                        "participant_projection_sha256": stream_root(
                            "outcome_pair_plan_action_participant_projection_v1",
                            current_count,
                            current_hasher,
                        ),
                    }
                    if aggregate["official_name_count"] != current_count:
                        raise RuntimeError("source action has repeated official names")
                    expected_action = _action_output_row(current_action, aggregate)
                    packaged_action = load_json_bytes(
                        next_package_action["row_json"].encode()
                    )
                    if packaged_action != expected_action:
                        raise RuntimeError(
                            "action projection differs from exact real source"
                        )
                    _assert_action_plan_parity(
                        source_action=current_action,
                        aggregate=aggregate,
                        plan_action=dict(next_plan_action),
                    )
                    next_name = next(name_counts, None)
                    next_package_action = next(package_actions, None)
                    next_plan_action = next(plan_actions, None)
                    verified_actions += 1

                missing = object()
                for joined, packaged_row in itertools.zip_longest(
                    source_iter, package_iter, fillvalue=missing
                ):
                    if joined is missing or packaged_row is missing:
                        raise RuntimeError(
                            "source and packaged member row counts differ"
                        )
                    member = _source_member_from_stage(joined)
                    action_id = str(member["action_id"])
                    if current_action_id != action_id:
                        finish_action()
                        current_action_id = action_id
                        current_action = _action_from_member_join(joined)
                        current_action["source_id"] = str(member["source_id"])
                        current_hasher = hashlib.sha256()
                        current_count = 0
                    expected_member = _member_output_row(
                        member, _action_from_member_join(joined)
                    )
                    if packaged_row != expected_member:
                        raise RuntimeError(
                            "packaged identity row differs from exact real source"
                        )
                    packaged_projection = {
                        source_field: packaged_row[persisted_field]
                        for source_field, persisted_field in MEMBER_PROJECTION_FIELD_MAP.items()
                    }
                    if packaged_projection != member:
                        raise RuntimeError(
                            "explicit participant field map does not reconstruct source projection"
                        )
                    stream_hash_add(current_hasher, packaged_projection)
                    stream_hash_add(member_component_hasher, member)
                    stream_hash_add(member_package_hasher, packaged_row)
                    current_count += 1
                    parity_rows += 1
                finish_action()
                if (
                    parity_rows != EXPECTED_MEMBER_ROWS
                    or verified_actions != EXPECTED_ACTIONS
                    or next_name is not None
                    or next_package_action is not None
                    or next_plan_action is not None
                ):
                    raise RuntimeError("full source/action parity cardinality drifted")

                action_package_hasher = hashlib.sha256()
                action_root_count = 0
                for row in scratch.execute(
                    "SELECT row_json FROM package_action_rows ORDER BY action_id"
                ):
                    stream_hash_add(
                        action_package_hasher, load_json_bytes(row["row_json"].encode())
                    )
                    action_root_count += 1
                names_hasher = hashlib.sha256()
                names_count = 0
                for row in scratch.execute(
                    "SELECT member_name FROM package_names ORDER BY member_name"
                ):
                    stream_hash_add(names_hasher, {"official_name": row["member_name"]})
                    names_count += 1
                roots = {
                    "member_component_root_sha256": stream_root(
                        "outcome_pair_plan_input_members_v1",
                        parity_rows,
                        member_component_hasher,
                    ),
                    "member_rows_root_sha256": stream_root(
                        "outcome_pair_identity_companion_member_rows_v1",
                        parity_rows,
                        member_package_hasher,
                    ),
                    "action_rows_root_sha256": stream_root(
                        "outcome_pair_identity_companion_action_rows_v1",
                        action_root_count,
                        action_package_hasher,
                    ),
                    "official_names_root_sha256": stream_root(
                        "outcome_pair_identity_companion_official_names_v1",
                        names_count,
                        names_hasher,
                    ),
                }
                expected_roots = {
                    "member_component_root_sha256": EXPECTED_MEMBER_COMPONENT_ROOT_SHA256,
                    "member_rows_root_sha256": EXPECTED_MEMBER_ROWS_ROOT_SHA256,
                    "action_rows_root_sha256": EXPECTED_ACTION_ROWS_ROOT_SHA256,
                    "official_names_root_sha256": EXPECTED_OFFICIAL_NAMES_ROOT_SHA256,
                }
                if roots != expected_roots or manifest["roots"] != expected_roots:
                    raise RuntimeError("identity companion semantic roots differ")
                counts = {
                    "member_vote_rows": member_rows,
                    "distinct_official_names": names_count,
                    "actions": action_rows,
                    "member_partitions": len(partitions),
                    "member_files": member_files,
                    "action_files": len(action_files),
                    "publication_eligible_rows": 0,
                    "ranking_eligible_rows": 0,
                }
                for name, value in manifest["counts"].items():
                    _exact_int(f"manifest count {name}", value)
                if manifest["counts"] != counts:
                    raise RuntimeError("identity companion manifest counts differ")
                package_semantic_root = canonical_sha256(
                    {
                        "contract_version": PACKAGE_ROOT_CONTRACT_VERSION,
                        "counts": counts,
                        "policy": POLICY,
                        "roots": roots,
                        "schemas": {
                            "member_votes": MEMBER_CONTRACT.schema_sha256,
                            "action_projections": ACTION_CONTRACT.schema_sha256,
                        },
                    }
                )
                if (
                    package_semantic_root != EXPECTED_PACKAGE_SEMANTIC_ROOT_SHA256
                    or manifest["package_semantic_root_sha256"] != package_semantic_root
                ):
                    raise RuntimeError(
                        "identity companion package semantic root mismatch"
                    )
                expected_materialization_checks = {
                    "real_source_hash_pinned": True,
                    "config_hash_pinned": True,
                    "executed_scan_sql_hashes_pinned": True,
                    "descriptor_bound_sqlite_reads": True,
                    "source_read_only_and_stable": True,
                    "pair_plan_reference_read_only_and_stable": True,
                    "all_member_vote_rows_retained": True,
                    "all_exact_official_names_retained": True,
                    "all_official_ids_retained": True,
                    "all_official_urls_retained": True,
                    "per_action_participant_projection_parity": True,
                    "participant_projection_field_map_explicit": True,
                    "bounded_files": True,
                    "content_addressed_files": True,
                    "canonical_pyarrow_physical_writer": True,
                    "dataset_api_compatible_layout": True,
                    "publication_disabled": True,
                    "ranking_disabled": True,
                }
                if manifest["checks"] != expected_materialization_checks:
                    raise RuntimeError("identity materialization checks drifted")

                final_files, final_directories = _assert_exact_inventory(
                    root, declared_files, declared_directories
                )
                for relative, identity in package_identities.items():
                    path = _safe_package_child(root, relative)
                    assert_regular_file_stable(path, identity)
                    with bound_regular_file(path) as final_file:
                        if final_file.sha256() != package_binary_hashes[relative]:
                            raise RuntimeError("package file changed before success")
                if root_manifest.sha256() != manifest_file_sha256:
                    raise RuntimeError("package manifest changed before success")
                if external_manifest is not None and (
                    external_manifest.sha256() != external_manifest_sha256
                    or external_manifest.read_bytes(max_bytes=MAX_JSON_BYTES)
                    != manifest_bytes
                ):
                    raise RuntimeError("external manifest changed before success")
                if _root_identity(root) != root_identity:
                    raise RuntimeError("package root inode changed during validation")
                source_connection.rollback()
                plan_connection.rollback()
                source_connection.close()
                plan_connection.close()
                source_connection = plan_connection = None
                scratch.close()
            finally:
                if source_connection is not None:
                    source_connection.close()
                if plan_connection is not None:
                    plan_connection.close()
                try:
                    scratch.close()
                except sqlite3.Error:
                    pass

        process_peak = peak_rss_mb()
        incremental_peak = max(0.0, process_peak - process_peak_at_entry)
        if incremental_peak > rss_limit:
            raise RuntimeError(
                "identity validation exceeded incremental RSS limit: "
                f"{incremental_peak} > {rss_limit} MiB"
            )
        checks = {
            "manifest_contract": True,
            "inventory_exact": True,
            "all_parquet_checksums": True,
            "all_parquet_schemas": True,
            "all_files_content_addressed": True,
            "deterministic_file_segmentation": True,
            "deterministic_row_group_segmentation": True,
            "dictionary_encoding_and_statistics": True,
            "canonical_pyarrow_physical_replay": True,
            "dataset_api_compatible": True,
            "all_member_vote_rows_retained": True,
            "all_exact_official_names_retained": True,
            "all_official_ids_retained": True,
            "all_official_urls_retained": True,
            "all_rows_exact_source_parity": True,
            "per_action_participant_projection_parity": True,
            "participant_projection_field_map_explicit": True,
            "executed_scan_sql_hashes_pinned": True,
            "descriptor_bound_sqlite_reads": True,
            "source_read_only_before_after_stable": True,
            "runtime_source_exact_projection_equivalence": True,
            "pair_plan_read_only_before_after_stable": True,
            "publication_disabled": True,
            "ranking_disabled": True,
        }
        return {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "status": "ok",
            "manifest_sha256": manifest_file_sha256,
            "manifest_root_sha256": manifest["manifest_root_sha256"],
            "package_semantic_root_sha256": EXPECTED_PACKAGE_SEMANTIC_ROOT_SHA256,
            "policy": dict(POLICY),
            "counts": counts,
            "roots": roots,
            "runtime_source_equivalence": {
                "mode": "exact_scoped_projection_roots_v1",
                "runtime_database_path": repo_path(source_bound.path),
                "runtime_database_bytes": source_bound.identity.size,
                "runtime_database_sha256": None,
                "pinned_database_bytes": EXPECTED_SOURCE_DATABASE_BYTES,
                "pinned_database_sha256": EXPECTED_SOURCE_DATABASE_SHA256,
                "whole_database_identical": None,
                "whole_database_identity_status": (
                    "not_computed_projection_scoped"
                ),
                "member_component_root_sha256": roots[
                    "member_component_root_sha256"
                ],
                "member_rows_root_sha256": roots["member_rows_root_sha256"],
                "action_rows_root_sha256": roots["action_rows_root_sha256"],
                "official_names_root_sha256": roots[
                    "official_names_root_sha256"
                ],
            },
            "parquet_bytes": member_bytes + action_bytes,
            "performance": {
                "process_peak_rss_mb": process_peak,
                "process_peak_at_entry_mb": process_peak_at_entry,
                "incremental_peak_rss_mb": incremental_peak,
                "max_incremental_peak_rss_mb": rss_limit,
                "batch_rows": batch_rows,
            },
            "checks": checks,
            "publication_gate_passed": False,
            "ranking_gate_passed": False,
            "promotion_gate_passed": False,
        }


__all__ = ["VALIDATION_SCHEMA_VERSION", "validate_outcome_pair_identity_companion"]
