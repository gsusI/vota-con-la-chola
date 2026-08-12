"""Reusable HF/static snapshot packaging helpers for public-data projects."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .sanitize import redact_sensitive_text, sanitize_url_for_public

STATIC_PUBLISHED_FILES = (
    "proximas-elecciones-espana.json",
    "poblacion_municipios_es.json",
    "source-catalog-latest.json",
    "source-scrape-queue-latest.json",
    "accountability-ledger-latest.json",
    "accountability-dossiers-latest.json",
    "accountability-evidence-api-latest.json",
    "integrity-signals-latest.json",
)
LIBERTY_ATLAS_RELEASE_LATEST_FILE = "liberty-restrictions-atlas-release-latest.json"

def load_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        out[key] = value
    return out


def resolve_setting(key: str, cli_value: str, dotenv_values: dict[str, str]) -> str:
    if cli_value.strip():
        return cli_value.strip()
    env_value = os.environ.get(key, "").strip()
    if env_value:
        return env_value
    return dotenv_values.get(key, "").strip()


def ensure_iso_date(value: str) -> str:
    cleaned = value.strip()
    try:
        datetime.strptime(cleaned, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"snapshot-date inválido: {cleaned!r}") from exc
    return cleaned


def ensure_positive(value: int, flag_name: str) -> int:
    if value <= 0:
        raise ValueError(f"{flag_name} debe ser > 0")
    return value


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def yaml_q(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def md_escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def format_terms_cell(value: str) -> str:
    terms_url = value.strip()
    if not terms_url:
        return "-"
    if terms_url.startswith("http://") or terms_url.startswith("https://"):
        return f"[link]({terms_url})"
    return f"`{md_escape_table(terms_url)}`"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def gzip_copy(src: Path, dst: Path, compresslevel: int) -> None:
    with src.open("rb") as f_in, dst.open("wb") as f_raw:
        with gzip.GzipFile(fileobj=f_raw, mode="wb", compresslevel=compresslevel, mtime=0) as f_out:
            shutil.copyfileobj(f_in, f_out, 1024 * 1024)


def collect_published_files(published_dir: Path, snapshot_date: str) -> list[Path]:
    if not published_dir.exists():
        return []
    candidates = [p for p in published_dir.iterdir() if p.is_file() and snapshot_date in p.name]
    names = {p.name for p in candidates}
    filtered: list[Path] = []
    for path in sorted(candidates):
        if path.name.endswith(".json") and f"{path.name}.gz" in names:
            continue
        filtered.append(path)
    for static_name in STATIC_PUBLISHED_FILES:
        static_path = published_dir / static_name
        if static_path.exists() and static_path.is_file():
            filtered.append(static_path)
    atlas_release_latest_path = published_dir / LIBERTY_ATLAS_RELEASE_LATEST_FILE
    if atlas_release_latest_path.exists() and atlas_release_latest_path.is_file():
        filtered.append(atlas_release_latest_path)
    # Preserve deterministic ordering and avoid accidental duplicates.
    unique: list[Path] = []
    seen: set[str] = set()
    for path in sorted(filtered, key=lambda p: p.name):
        if path.name in seen:
            continue
        seen.add(path.name)
        unique.append(path)
    return unique


def _read_json_or_gz(path: Path) -> dict[str, Any]:
    try:
        if path.suffix == ".gz":
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                obj = json.load(fh)
        else:
            obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return obj if isinstance(obj, dict) else {}


def extract_quality_report_summary(
    published_files: list[Path],
    snapshot_date: str,
) -> dict[str, Any]:
    date_token = str(snapshot_date).strip()
    preferred_names = (
        f"votaciones-kpis-es-{date_token}.json",
        f"votaciones-kpis-es-{date_token}.json.gz",
    )
    by_name = {p.name: p for p in published_files}
    candidate: Path | None = None
    for name in preferred_names:
        p = by_name.get(name)
        if p is not None:
            candidate = p
            break
    if candidate is None:
        fallback = [
            p
            for p in published_files
            if "votaciones-kpis" in p.name and date_token in p.name and p.suffix in {".json", ".gz"}
        ]
        if fallback:
            candidate = sorted(fallback, key=lambda p: p.name)[0]
    if candidate is None:
        return {}

    payload = _read_json_or_gz(candidate)
    if not payload:
        return {}

    summary: dict[str, Any] = {
        "file_name": candidate.name,
        "vote_gate_passed": bool(payload.get("gate", {}).get("passed")),
    }
    vote_kpis = payload.get("kpis", {})
    if isinstance(vote_kpis, dict):
        if "events_total" in vote_kpis:
            summary["events_total"] = int(vote_kpis.get("events_total") or 0)
        if "member_votes_with_person_id_pct" in vote_kpis:
            summary["member_votes_with_person_id_pct"] = float(
                vote_kpis.get("member_votes_with_person_id_pct") or 0.0
            )

    initiatives = payload.get("initiatives")
    if isinstance(initiatives, dict):
        summary["initiative_gate_passed"] = bool(initiatives.get("gate", {}).get("passed"))
        init_kpis = initiatives.get("kpis", {})
        if isinstance(init_kpis, dict):
            if "downloaded_doc_links" in init_kpis:
                summary["downloaded_doc_links"] = int(init_kpis.get("downloaded_doc_links") or 0)
            if "missing_doc_links_actionable" in init_kpis:
                summary["missing_doc_links_actionable"] = int(
                    init_kpis.get("missing_doc_links_actionable") or 0
                )
            if "extraction_coverage_pct" in init_kpis:
                summary["extraction_coverage_pct"] = float(
                    init_kpis.get("extraction_coverage_pct") or 0.0
                )
            if "extraction_review_closed_pct" in init_kpis:
                summary["extraction_review_closed_pct"] = float(
                    init_kpis.get("extraction_review_closed_pct") or 0.0
                )
    return summary


def extract_source_catalog_summary(
    published_files: list[Path],
    snapshot_date: str,
) -> dict[str, Any]:
    date_token = str(snapshot_date).strip()
    preferred_names = (
        f"source-catalog-{date_token}.json",
        "source-catalog-latest.json",
    )
    by_name = {p.name: p for p in published_files}
    candidate: Path | None = None
    for name in preferred_names:
        p = by_name.get(name)
        if p is not None:
            candidate = p
            break
    if candidate is None:
        return {}

    payload = _read_json_or_gz(candidate)
    if not payload:
        return {}

    summary = payload.get("summary")
    if not isinstance(summary, dict):
        return {}

    out: dict[str, Any] = {"file_name": candidate.name}
    for key in (
        "sources_total",
        "desired_total",
        "in_db_total",
        "with_network_total",
        "blocked_total",
        "mismatch_total",
    ):
        if key in summary:
            out[key] = int(summary.get(key) or 0)
    return out


def ensure_quality_report_for_publish(
    quality_summary: dict[str, Any],
    *,
    require_quality_report: bool,
    snapshot_date: str,
    published_dir: Path,
) -> None:
    if not require_quality_report:
        return
    if not quality_summary:
        raise ValueError(
            "No se encontró quality_report (votaciones-kpis) para snapshot "
            f"{snapshot_date} en {published_dir}. "
            "Genera `votaciones-kpis-es-<snapshot>.json` o desactiva --require-quality-report."
        )
    file_name = str(quality_summary.get("file_name") or "")
    if not file_name:
        raise ValueError("quality_report encontrado pero sin `file_name`.")
    if not file_name.startswith("votaciones-kpis-es-"):
        raise ValueError(f"quality_report.file_name inesperado: {file_name!r}")
    if "vote_gate_passed" not in quality_summary:
        raise ValueError("quality_report encontrado pero sin `vote_gate_passed`.")


def export_ingestion_runs_csv(db_path: Path, out_csv: Path) -> int:
    query = """
        SELECT
            run_id,
            source_id,
            started_at,
            finished_at,
            status,
            source_url,
            records_seen,
            records_loaded,
            message
        FROM ingestion_runs
        ORDER BY run_id
    """
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(query)
        columns = [str(item[0]) for item in (cur.description or ())]
        rows = cur.fetchall()
    finally:
        conn.close()
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        if columns:
            writer.writerow(columns)
        safe_rows: list[list[Any]] = []
        for row in rows:
            row_list = list(row)
            # source_url
            if len(row_list) > 5 and row_list[5] is not None:
                row_list[5] = sanitize_url_for_public(str(row_list[5]))
            # message
            if len(row_list) > 8 and row_list[8] is not None:
                row_list[8] = redact_sensitive_text(str(row_list[8]))
            safe_rows.append(row_list)
        writer.writerows(safe_rows)
    return len(rows)


def export_source_records_by_source(db_path: Path, snapshot_date: str, out_csv: Path) -> tuple[int, int, dict[str, int]]:
    query = """
        SELECT
            source_id,
            COUNT(*) AS records
        FROM source_records
        WHERE source_snapshot_date = ?
        GROUP BY source_id
        ORDER BY source_id
    """
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(query, (snapshot_date,))
        rows = cur.fetchall()
    finally:
        conn.close()
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(("source_id", "records"))
        writer.writerows(rows)
    counts = {str(row[0]): int(row[1]) for row in rows}
    total = sum(counts.values())
    return len(rows), total, counts


def fetch_sources_catalog(db_path: Path) -> dict[str, dict[str, str]]:
    query = """
        SELECT source_id, name, scope, default_url
        FROM sources
        ORDER BY source_id
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        try:
            rows = conn.execute(query).fetchall()
        except sqlite3.OperationalError:
            return {}
    finally:
        conn.close()
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        source_id = str(row["source_id"])
        out[source_id] = {
            "name": str(row["name"] or source_id),
            "scope": str(row["scope"] or ""),
            "default_url": str(row["default_url"] or ""),
        }
    return out


def write_checksums(snapshot_dir: Path, relative_paths: list[Path]) -> None:
    out_path = snapshot_dir / "checksums.sha256"
    lines = []
    for rel in sorted(relative_paths):
        digest = sha256_file(snapshot_dir / rel)
        lines.append(f"{digest}  {rel.as_posix()}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_csv_list(raw_value: str) -> set[str]:
    values = set()
    for piece in raw_value.replace("\n", ",").split(","):
        value = piece.strip()
        if value:
            values.add(value)
    return values


def sqlite_declared_kind(type_name: str | None) -> str:
    text = (type_name or "").strip().upper()
    if "BOOL" in text:
        return "bool"
    if "INT" in text:
        return "int"
    if any(token in text for token in ("REAL", "FLOA", "DOUB")):
        return "float"
    if "BLOB" in text:
        return "binary"
    if any(token in text for token in ("NUMERIC", "DECIMAL")):
        # SQLite NUMERIC es flexible; string evita errores por mezcla de tipos.
        return "string"
    return "string"


def is_text_like_sqlite(type_name: str | None) -> bool:
    text = (type_name or "").upper()
    if any(token in text for token in ("CHAR", "CLOB", "TEXT", "JSON")):
        return True
    return text == ""


def build_explorer_schema_payload(db_path: Path) -> dict[str, Any]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        table_rows = conn.execute(
            """
            SELECT name, sql
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

        schema_by_table: dict[str, dict[str, Any]] = {}
        for tr in table_rows:
            table_name = str(tr["name"])
            table_q = quote_ident(table_name)

            columns_raw = conn.execute(f"PRAGMA table_info({table_q})").fetchall()
            columns: list[dict[str, Any]] = []
            for c in columns_raw:
                columns.append(
                    {
                        "name": str(c["name"]),
                        "type": str(c["type"] or ""),
                        "notnull": bool(c["notnull"]),
                        "default": c["dflt_value"],
                        "pk_order": int(c["pk"] or 0),
                    }
                )

            pk_columns = [
                col["name"]
                for col in sorted(columns, key=lambda item: int(item["pk_order"]))
                if int(col["pk_order"]) > 0
            ]

            try:
                row_count = int(conn.execute(f"SELECT COUNT(*) AS n FROM {table_q}").fetchone()["n"])
            except sqlite3.Error:
                row_count = None

            fk_rows = conn.execute(f"PRAGMA foreign_key_list({table_q})").fetchall()
            fk_groups: dict[int, dict[str, Any]] = {}
            for fk in fk_rows:
                group_id = int(fk["id"])
                group = fk_groups.setdefault(
                    group_id,
                    {
                        "id": group_id,
                        "to_table": str(fk["table"]),
                        "from_columns": [],
                        "to_columns": [],
                        "on_update": str(fk["on_update"]),
                        "on_delete": str(fk["on_delete"]),
                        "match": str(fk["match"]),
                    },
                )
                group["from_columns"].append(str(fk["from"]))
                group["to_columns"].append(str(fk["to"]))

            foreign_keys_out = [fk_groups[key] for key in sorted(fk_groups)]
            search_columns = [col["name"] for col in columns if is_text_like_sqlite(str(col["type"]))]
            if not search_columns:
                search_columns = [col["name"] for col in columns]

            create_sql = str(tr["sql"] or "")
            schema_by_table[table_name] = {
                "name": table_name,
                "row_count": row_count,
                "column_count": len(columns),
                "columns": [
                    {
                        "name": col["name"],
                        "type": col["type"],
                        "notnull": col["notnull"],
                        "pk_order": col["pk_order"],
                    }
                    for col in columns
                ],
                "primary_key": pk_columns,
                "without_rowid": "WITHOUT ROWID" in create_sql.upper(),
                "search_columns": search_columns[:8],
                "foreign_keys_out": [
                    {
                        "to_table": fk["to_table"],
                        "from_columns": fk["from_columns"],
                        "to_columns": fk["to_columns"],
                    }
                    for fk in foreign_keys_out
                ],
                "foreign_keys_in": [],
            }

        for source_table, meta in schema_by_table.items():
            for fk in meta["foreign_keys_out"]:
                target_table = str(fk["to_table"])
                target = schema_by_table.get(target_table)
                if not target:
                    continue
                target["foreign_keys_in"].append(
                    {
                        "from_table": source_table,
                        "from_columns": list(fk["from_columns"]),
                        "to_columns": list(fk["to_columns"]),
                    }
                )

        tables = list(schema_by_table.values())
        for table_meta in tables:
            table_meta["foreign_keys_in"] = sorted(
                table_meta["foreign_keys_in"],
                key=lambda fk: (str(fk["from_table"]), str(fk["to_columns"])),
            )
        tables.sort(key=lambda t: ((t["row_count"] is None), -(int(t["row_count"] or 0)), str(t["name"])))

        return {
            "meta": {
                "db_path": str(db_path),
                "table_count": len(tables),
                "source": "sqlite_schema_snapshot",
            },
            "tables": tables,
        }
    finally:
        conn.close()


def export_explorer_schema_snapshot(db_path: Path, snapshot_dir: Path) -> Path:
    payload = build_explorer_schema_payload(db_path)
    rel_path = Path("explorer_schema.json")
    out_path = snapshot_dir / rel_path
    out_path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return rel_path


def coerce_parquet_value(value: Any, kind: str) -> Any:
    if value is None:
        return None
    if kind == "string":
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        if isinstance(value, bytearray):
            return bytes(value).decode("utf-8", errors="replace")
        if isinstance(value, memoryview):
            return bytes(value).decode("utf-8", errors="replace")
        return str(value)
    if kind == "binary":
        if isinstance(value, bytes):
            return value
        if isinstance(value, bytearray):
            return bytes(value)
        if isinstance(value, memoryview):
            return bytes(value)
        return str(value).encode("utf-8", errors="replace")
    if kind == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        text = str(value).strip().lower()
        if text in {"1", "true", "t", "y", "yes", "si", "sí"}:
            return True
        if text in {"0", "false", "f", "n", "no"}:
            return False
        return None
    if kind == "int":
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            try:
                return int(value)
            except (ValueError, OverflowError):
                return None
        text = str(value).strip()
        if not text:
            return None
        try:
            return int(text)
        except (ValueError, OverflowError):
            try:
                return int(float(text))
            except (ValueError, OverflowError):
                return None
    if kind == "float":
        if isinstance(value, bool):
            return float(int(value))
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return str(value)


def load_sqlite_table_specs(
    db_path: Path, include_tables: set[str], exclude_tables: set[str]
) -> list[dict[str, Any]]:
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            """
            SELECT name, sql
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
        found_names = {str(row[0]) for row in rows}
        missing = sorted(name for name in include_tables if name not in found_names)
        if missing:
            raise ValueError(f"--parquet-tables contiene tablas inexistentes: {', '.join(missing)}")
        table_specs: list[dict[str, Any]] = []
        for table_name_raw, create_sql_raw in rows:
            table_name = str(table_name_raw)
            if include_tables and table_name not in include_tables:
                continue
            if table_name in exclude_tables:
                continue
            cols_rows = conn.execute(f"PRAGMA table_info({quote_ident(table_name)})").fetchall()
            columns = [
                {
                    "name": str(row[1]),
                    "declared_type": str(row[2] or ""),
                    "pk_order": int(row[5]),
                }
                for row in cols_rows
            ]
            pk_cols = [col["name"] for col in sorted(columns, key=lambda c: c["pk_order"]) if col["pk_order"] > 0]
            create_sql = str(create_sql_raw or "")
            without_rowid = "WITHOUT ROWID" in create_sql.upper()
            table_specs.append(
                {
                    "table_name": table_name,
                    "columns": columns,
                    "pk_cols": pk_cols,
                    "without_rowid": without_rowid,
                }
            )
        return table_specs
    finally:
        conn.close()


def export_parquet_tables(
    db_path: Path,
    snapshot_dir: Path,
    parquet_prefix: str,
    compression: str,
    batch_rows: int,
    include_tables: set[str],
    exclude_tables: set[str],
) -> tuple[list[Path], list[dict[str, Any]]]:
    try:
        import pyarrow as pa  # type: ignore
        import pyarrow.parquet as pq  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError("pyarrow no está instalado. Añade pyarrow al entorno ETL.") from exc

    table_specs = load_sqlite_table_specs(db_path, include_tables, exclude_tables)
    if not table_specs:
        return [], []

    conn = sqlite3.connect(str(db_path))
    try:
        parquet_rel_paths: list[Path] = []
        parquet_tables: list[dict[str, Any]] = []
        for spec in table_specs:
            table_name = str(spec["table_name"])
            cols = list(spec["columns"])
            if not cols:
                continue
            col_names = [str(col["name"]) for col in cols]
            kinds = [sqlite_declared_kind(str(col["declared_type"])) for col in cols]

            fields = []
            for col_name, kind in zip(col_names, kinds):
                if kind == "int":
                    arrow_type = pa.int64()
                elif kind == "float":
                    arrow_type = pa.float64()
                elif kind == "bool":
                    arrow_type = pa.bool_()
                elif kind == "binary":
                    arrow_type = pa.binary()
                else:
                    arrow_type = pa.string()
                fields.append(pa.field(col_name, arrow_type, nullable=True))
            schema = pa.schema(fields)
            schema_contract = [
                {
                    "name": col_name,
                    "sqlite_declared_type": str(col["declared_type"]),
                    "logical_kind": kind,
                    "arrow_type": str(schema.field(index).type),
                    "nullable": True,
                }
                for index, (col_name, col, kind) in enumerate(
                    zip(col_names, cols, kinds)
                )
            ]
            schema_sha256 = hashlib.sha256(
                json.dumps(
                    schema_contract,
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()

            table_rel_dir = Path(parquet_prefix) / table_name
            table_abs_dir = snapshot_dir / table_rel_dir
            table_abs_dir.mkdir(parents=True, exist_ok=True)

            order_by_cols = [str(c) for c in spec["pk_cols"] if c]
            order_sql = ""
            order_label = ""
            if order_by_cols:
                order_sql = " ORDER BY " + ", ".join(quote_ident(col) for col in order_by_cols)
                order_label = ", ".join(order_by_cols)
            elif not bool(spec["without_rowid"]):
                order_sql = " ORDER BY rowid"
                order_label = "rowid"

            select_sql = (
                f"SELECT {', '.join(quote_ident(col) for col in col_names)} "
                f"FROM {quote_ident(table_name)}{order_sql}"
            )
            cur = conn.execute(select_sql)
            part_idx = 0
            row_count = 0
            part_manifests: list[dict[str, Any]] = []
            order_col_indexes = [col_names.index(name) for name in order_by_cols]
            while True:
                rows = cur.fetchmany(batch_rows)
                if not rows:
                    break
                arrays = []
                for col_idx, kind in enumerate(kinds):
                    values = [coerce_parquet_value(row[col_idx], kind) for row in rows]
                    arrays.append(pa.array(values, type=schema.field(col_idx).type))
                chunk_table = pa.Table.from_arrays(arrays, schema=schema)
                rel_path = table_rel_dir / f"part-{part_idx:05d}.parquet"
                abs_path = snapshot_dir / rel_path
                pq.write_table(chunk_table, abs_path, compression=compression)
                parquet_rel_paths.append(rel_path)
                min_key = (
                    [coerce_parquet_value(rows[0][idx], kinds[idx]) for idx in order_col_indexes]
                    if order_col_indexes
                    else None
                )
                max_key = (
                    [coerce_parquet_value(rows[-1][idx], kinds[idx]) for idx in order_col_indexes]
                    if order_col_indexes
                    else None
                )
                part_manifests.append(
                    {
                        "path": rel_path.as_posix(),
                        "rows": len(rows),
                        "bytes": int(abs_path.stat().st_size),
                        "sha256": sha256_file(abs_path),
                        "min_order_key": min_key,
                        "max_order_key": max_key,
                    }
                )
                part_idx += 1
                row_count += len(rows)

            if part_idx == 0:
                empty_arrays = [pa.array([], type=field.type) for field in schema]
                empty_table = pa.Table.from_arrays(empty_arrays, schema=schema)
                rel_path = table_rel_dir / "part-00000.parquet"
                pq.write_table(empty_table, snapshot_dir / rel_path, compression=compression)
                parquet_rel_paths.append(rel_path)
                abs_path = snapshot_dir / rel_path
                part_manifests.append(
                    {
                        "path": rel_path.as_posix(),
                        "rows": 0,
                        "bytes": int(abs_path.stat().st_size),
                        "sha256": sha256_file(abs_path),
                        "min_order_key": None,
                        "max_order_key": None,
                    }
                )
                part_idx = 1

            parquet_tables.append(
                {
                    "table": table_name,
                    "columns": len(col_names),
                    "rows": row_count,
                    "files": part_idx,
                    "order_by": order_label,
                    "path_glob": f"{table_rel_dir.as_posix()}/*.parquet",
                    "schema": schema_contract,
                    "schema_sha256": schema_sha256,
                    "partition_contract": {
                        "strategy": "ordered_fixed_row_batches",
                        "batch_rows": int(batch_rows),
                        "order_by": order_by_cols or (["rowid"] if order_label == "rowid" else []),
                    },
                    "parts": part_manifests,
                }
            )
        return parquet_rel_paths, parquet_tables
    finally:
        conn.close()
