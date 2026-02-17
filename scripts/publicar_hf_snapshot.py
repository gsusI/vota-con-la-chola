#!/usr/bin/env python3
"""Publica un snapshot de datos en un dataset público de Hugging Face."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_PUBLISHED_DIR = Path("etl/data/published")
DEFAULT_ENV_FILE = Path(".env")
DEFAULT_DATASET_NAME = "vota-con-la-chola-data"
DEFAULT_SOURCE_REPO_URL = "https://github.com/gsusI/vota-con-la-chola"
STATIC_PUBLISHED_FILES = ("proximas-elecciones-espana.json", "poblacion_municipios_es.json")
PLACEHOLDER_VALUES = {"", "your_hf_token_here", "your_hf_username_here"}
DEFAULT_PARQUET_EXCLUDE_TABLES = ("raw_fetches", "run_fetches", "source_records", "lost_and_found")
DEFAULT_SENSITIVE_PARQUET_TABLES = frozenset(DEFAULT_PARQUET_EXCLUDE_TABLES)
SENSITIVE_QUERY_KEY_TOKENS = (
    "token",
    "secret",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "key",
    "auth",
    "authorization",
    "cookie",
    "signature",
    "sig",
)
HF_TOKEN_RE = re.compile(r"\bhf_[A-Za-z0-9]{16,}\b")
BEARER_RE = re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]{12,}")
SENSITIVE_KV_RE = re.compile(
    r"(?i)\b(token|api[_-]?key|password|passwd|secret|cookie|access_token|refresh_token|client_secret)\b\s*[:=]\s*([^\s,;]+)"
)
AUTH_KV_RE = re.compile(r"(?i)\bauthorization\b\s*[:=]\s*(?!bearer\b)([^\s,;]+)")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Publicar snapshot ETL a Hugging Face Datasets")
    p.add_argument("--db", default=str(DEFAULT_DB), help="Ruta del SQLite de entrada")
    p.add_argument("--snapshot-date", required=True, help="Fecha ISO YYYY-MM-DD del snapshot")
    p.add_argument("--published-dir", default=str(DEFAULT_PUBLISHED_DIR), help="Directorio de artefactos publicados")
    p.add_argument("--env-file", default=str(DEFAULT_ENV_FILE), help="Archivo .env con credenciales")
    p.add_argument(
        "--dataset-repo",
        default="",
        help="Repo HF dataset (owner/name). Si no se define, usa HF_DATASET_REPO_ID o HF_USERNAME/vota-con-la-chola-data",
    )
    p.add_argument("--hf-token", default="", help="Token HF (override; si vacio usa env/.env)")
    p.add_argument("--hf-username", default="", help="Usuario HF (override; si vacio usa env/.env)")
    p.add_argument(
        "--dataset-name",
        default=DEFAULT_DATASET_NAME,
        help="Nombre por defecto del dataset cuando no se define dataset-repo",
    )
    p.add_argument(
        "--source-repo-url",
        default="",
        help="URL del repositorio GitHub fuente (override; si vacío usa env/.env o valor por defecto)",
    )
    p.add_argument("--snapshot-prefix", default="snapshots", help="Prefijo de carpeta en el dataset remoto")
    p.add_argument("--gzip-level", type=int, default=6, help="Nivel gzip para sqlite (0-9)")
    p.add_argument("--skip-sqlite-gz", action="store_true", help="No empaquetar el SQLite completo comprimido")
    p.add_argument("--skip-parquet", action="store_true", help="No exportar tablas a Parquet")
    p.add_argument("--parquet-prefix", default="parquet", help="Prefijo de carpeta Parquet dentro del snapshot")
    p.add_argument(
        "--parquet-batch-rows",
        type=int,
        default=50_000,
        help="Filas por lote/archivo Parquet durante la exportación",
    )
    p.add_argument(
        "--parquet-compression",
        default="zstd",
        help="Compresión Parquet (zstd, snappy, gzip, brotli, lz4, none)",
    )
    p.add_argument(
        "--parquet-tables",
        default="",
        help="Lista separada por comas de tablas a exportar (vacío = todas)",
    )
    p.add_argument(
        "--parquet-exclude-tables",
        default=",".join(DEFAULT_PARQUET_EXCLUDE_TABLES),
        help="Lista separada por comas de tablas a excluir de Parquet",
    )
    p.add_argument(
        "--allow-sensitive-parquet",
        action="store_true",
        help="Permite publicar tablas sensibles de trazabilidad cruda (no recomendado en dataset público)",
    )
    p.add_argument(
        "--private",
        action="store_true",
        help="Crear repo privado si no existe (por defecto público)",
    )
    p.add_argument("--dry-run", action="store_true", help="No sube nada; solo arma y valida el paquete")
    p.add_argument(
        "--keep-temp",
        action="store_true",
        help="Conservar carpeta temporal con el paquete generado",
    )
    p.add_argument(
        "--allow-empty-published",
        action="store_true",
        help="Permitir snapshot sin artefactos publicados por fecha",
    )
    return p.parse_args()


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
    # Preserve deterministic ordering and avoid accidental duplicates.
    unique: list[Path] = []
    seen: set[str] = set()
    for path in sorted(filtered, key=lambda p: p.name):
        if path.name in seen:
            continue
        seen.add(path.name)
        unique.append(path)
    return unique


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


def export_source_records_by_source(db_path: Path, snapshot_date: str, out_csv: Path) -> tuple[int, int]:
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
    total = sum(int(row[1]) for row in rows)
    return len(rows), total


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


def is_sensitive_query_key(name: str) -> bool:
    lowered = name.strip().lower().replace("-", "_")
    return any(token in lowered for token in SENSITIVE_QUERY_KEY_TOKENS)


def is_sensitive_query_value(value: str) -> bool:
    raw = value.strip()
    if not raw:
        return False
    lowered = raw.lower()
    if lowered.startswith("bearer "):
        return True
    if HF_TOKEN_RE.search(raw):
        return True
    return bool(re.fullmatch(r"[A-Za-z0-9._~+/=-]{32,}", raw))


def redact_sensitive_text(value: str) -> str:
    redacted = BEARER_RE.sub(r"\1 REDACTED", value)
    redacted = HF_TOKEN_RE.sub("hf_REDACTED", redacted)
    redacted = AUTH_KV_RE.sub("authorization=REDACTED", redacted)

    def repl(match: re.Match[str]) -> str:
        return f"{match.group(1)}=REDACTED"

    return SENSITIVE_KV_RE.sub(repl, redacted)


def sanitize_url_for_public(raw_url: str) -> str:
    text = raw_url.strip()
    if not text:
        return text
    try:
        parsed = urlsplit(text)
    except ValueError:
        return redact_sensitive_text(text)

    query_pairs: list[tuple[str, str]] = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if is_sensitive_query_key(key) or is_sensitive_query_value(value):
            query_pairs.append((key, "REDACTED"))
        else:
            query_pairs.append((key, redact_sensitive_text(value)))
    netloc = parsed.netloc.rsplit("@", 1)[-1]
    query = urlencode(query_pairs, doseq=True)
    safe_path = HF_TOKEN_RE.sub("hf_REDACTED", parsed.path)
    return urlunsplit((parsed.scheme, netloc, safe_path, query, ""))


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
                pq.write_table(chunk_table, snapshot_dir / rel_path, compression=compression)
                parquet_rel_paths.append(rel_path)
                part_idx += 1
                row_count += len(rows)

            if part_idx == 0:
                empty_arrays = [pa.array([], type=field.type) for field in schema]
                empty_table = pa.Table.from_arrays(empty_arrays, schema=schema)
                rel_path = table_rel_dir / "part-00000.parquet"
                pq.write_table(empty_table, snapshot_dir / rel_path, compression=compression)
                parquet_rel_paths.append(rel_path)
                part_idx = 1

            parquet_tables.append(
                {
                    "table": table_name,
                    "columns": len(col_names),
                    "rows": row_count,
                    "files": part_idx,
                    "order_by": order_label,
                    "path_glob": f"{table_rel_dir.as_posix()}/*.parquet",
                }
            )
        return parquet_rel_paths, parquet_tables
    finally:
        conn.close()


def build_dataset_readme(
    dataset_repo: str,
    snapshot_date: str,
    snapshot_rel_dir: Path,
    parquet_tables: list[dict[str, Any]],
    parquet_excluded_tables: list[str],
    include_sqlite_gz: bool,
    source_repo_url: str,
) -> str:
    lines: list[str] = [
        "---",
        "language:",
        "- es",
        "license: other",
        "task_categories:",
        "- tabular-classification",
        "pretty_name: Vota Con La Chola snapshots",
    ]
    if parquet_tables:
        lines.append("configs:")
        for table_meta in sorted(parquet_tables, key=lambda row: str(row["table"])):
            table_name = str(table_meta["table"])
            path_glob = str(table_meta["path_glob"])
            snapshot_glob = f"{snapshot_rel_dir.as_posix()}/{path_glob}"
            lines.extend(
                [
                    f"- config_name: {yaml_q(table_name)}",
                    "  data_files:",
                    "  - split: train",
                    "    path:",
                    f"    - {yaml_q(snapshot_glob)}",
                ]
            )
    lines.extend(
        [
            "---",
            "",
            "# Vota Con La Chola - Snapshots ETL",
            "",
            f"Dataset de snapshots públicos del proyecto `{dataset_repo}`.",
            "",
            f"Repositorio fuente: [{source_repo_url}]({source_repo_url})",
            "",
            "Contenido por snapshot:",
            f"- `{snapshot_rel_dir.as_posix()}/parquet/<tabla>/part-*.parquet`: tablas navegables en Data Studio.",
        ]
    )
    if include_sqlite_gz:
        lines.append("- `politicos-es.sqlite.gz`: base SQLite completa comprimida.")
    if parquet_excluded_tables:
        excluded = ", ".join(f"`{name}`" for name in parquet_excluded_tables)
        lines.append(
            f"- Tablas excluidas por privacidad (default público): {excluded}. "
            "Usa `--allow-sensitive-parquet` solo en repos privados."
        )
    lines.extend(
        [
            "- `published/*`: artefactos canónicos JSON/JSON.GZ.",
            "- `ingestion_runs.csv`: historial de corridas de ingesta.",
            "- `source_records_by_source.csv`: conteos por fuente para la fecha del snapshot.",
            "- `manifest.json` y `checksums.sha256`: trazabilidad e integridad.",
            "",
            "Ruta del último snapshot publicado en este commit:",
            f"- `{snapshot_rel_dir.as_posix()}` (snapshot_date={snapshot_date})",
            "",
            "Actualización:",
            "- `just etl-publish-hf-dry-run` para validar empaquetado.",
            "- `just etl-publish-hf` para publicar actualización.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()

    try:
        snapshot_date = ensure_iso_date(args.snapshot_date)
        if not args.skip_sqlite_gz and not 0 <= int(args.gzip_level) <= 9:
            raise ValueError("--gzip-level debe estar en rango 0..9")
        ensure_positive(int(args.parquet_batch_rows), "--parquet-batch-rows")
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB no existe: {db_path}", file=sys.stderr)
        return 2

    published_dir = Path(args.published_dir)
    published_files = collect_published_files(published_dir, snapshot_date)
    if not published_files and not args.allow_empty_published:
        print(
            "ERROR: no se encontraron artefactos publicados para el snapshot "
            f"{snapshot_date} en {published_dir}",
            file=sys.stderr,
        )
        return 2

    dotenv_values = load_dotenv(Path(args.env_file))
    hf_token = resolve_setting("HF_TOKEN", args.hf_token, dotenv_values)
    hf_username = resolve_setting("HF_USERNAME", args.hf_username, dotenv_values)
    dataset_repo = resolve_setting("HF_DATASET_REPO_ID", args.dataset_repo, dotenv_values)
    source_repo_url = resolve_setting("SOURCE_REPO_URL", args.source_repo_url, dotenv_values) or DEFAULT_SOURCE_REPO_URL

    if not dataset_repo:
        if hf_username in PLACEHOLDER_VALUES:
            if args.dry_run:
                dataset_repo = f"local/{args.dataset_name}"
            else:
                print(
                    "ERROR: define HF_DATASET_REPO_ID o un HF_USERNAME válido en .env",
                    file=sys.stderr,
                )
                return 2
        else:
            dataset_repo = f"{hf_username}/{args.dataset_name}"
    elif "/" not in dataset_repo:
        if hf_username in PLACEHOLDER_VALUES:
            print(
                "ERROR: HF_DATASET_REPO_ID sin owner y HF_USERNAME inválido",
                file=sys.stderr,
            )
            return 2
        dataset_repo = f"{hf_username}/{dataset_repo}"

    if hf_token in PLACEHOLDER_VALUES:
        if args.dry_run:
            print("WARN: HF_TOKEN vacío/placeholder. Dry run continuará sin publicar.", file=sys.stderr)
        else:
            print("ERROR: HF_TOKEN vacío o placeholder. Completa .env", file=sys.stderr)
            return 2

    temp_ctx: tempfile.TemporaryDirectory[str] | None = None
    if args.keep_temp:
        build_root = Path(tempfile.mkdtemp(prefix="hf_snapshot_publish_"))
    else:
        temp_ctx = tempfile.TemporaryDirectory(prefix="hf_snapshot_publish_")
        build_root = Path(temp_ctx.name)

    try:
        snapshot_rel_dir = Path(args.snapshot_prefix) / snapshot_date
        snapshot_dir = build_root / snapshot_rel_dir
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        tracked_files: list[Path] = []

        if not args.skip_sqlite_gz:
            db_gz_name = "politicos-es.sqlite.gz"
            db_gz_path = snapshot_dir / db_gz_name
            gzip_copy(db_path, db_gz_path, compresslevel=int(args.gzip_level))
            tracked_files.append(Path(db_gz_name))

        ingestion_runs_csv = snapshot_dir / "ingestion_runs.csv"
        ingestion_runs_rows = export_ingestion_runs_csv(db_path, ingestion_runs_csv)
        tracked_files.append(Path("ingestion_runs.csv"))

        source_records_csv = snapshot_dir / "source_records_by_source.csv"
        source_records_rows, source_records_total = export_source_records_by_source(
            db_path, snapshot_date, source_records_csv
        )
        tracked_files.append(Path("source_records_by_source.csv"))

        published_dst_dir = snapshot_dir / "published"
        published_dst_dir.mkdir(parents=True, exist_ok=True)
        published_rel_paths: list[Path] = []
        for src in published_files:
            dst = published_dst_dir / src.name
            shutil.copy2(src, dst)
            rel_path = Path("published") / src.name
            published_rel_paths.append(rel_path)
            tracked_files.append(rel_path)

        parquet_rel_paths: list[Path] = []
        parquet_tables: list[dict[str, Any]] = []
        parquet_table_filter = parse_csv_list(args.parquet_tables)
        parquet_exclude_filter = parse_csv_list(args.parquet_exclude_tables)
        sensitive_requested = sorted(parquet_table_filter & DEFAULT_SENSITIVE_PARQUET_TABLES)
        if sensitive_requested and not args.allow_sensitive_parquet:
            raise ValueError(
                "Intento de exportar tablas sensibles sin --allow-sensitive-parquet: "
                + ", ".join(sensitive_requested)
            )
        if not args.allow_sensitive_parquet:
            parquet_exclude_filter.update(DEFAULT_SENSITIVE_PARQUET_TABLES)
        if not args.skip_parquet:
            parquet_rel_paths, parquet_tables = export_parquet_tables(
                db_path=db_path,
                snapshot_dir=snapshot_dir,
                parquet_prefix=args.parquet_prefix,
                compression=args.parquet_compression,
                batch_rows=int(args.parquet_batch_rows),
                include_tables=parquet_table_filter,
                exclude_tables=parquet_exclude_filter,
            )
            tracked_files.extend(parquet_rel_paths)

        manifest_rel = Path("manifest.json")
        manifest_path = snapshot_dir / manifest_rel
        manifest = {
            "project": "vota-con-la-chola",
            "snapshot_date": snapshot_date,
            "generated_at": now_utc_iso(),
            "dataset_repo": dataset_repo,
            "snapshot_dir": snapshot_rel_dir.as_posix(),
            "db_source_path": str(db_path),
            "files": [],
            "stats": {
                "published_files_count": len(published_rel_paths),
                "ingestion_runs_rows": ingestion_runs_rows,
                "source_records_by_source_rows": source_records_rows,
                "source_records_snapshot_total": source_records_total,
                "parquet_files_count": len(parquet_rel_paths),
                "parquet_tables_count": len(parquet_tables),
                "parquet_rows_total": sum(int(item["rows"]) for item in parquet_tables),
            },
            "parquet": {
                "enabled": not args.skip_parquet,
                "prefix": args.parquet_prefix,
                "compression": args.parquet_compression,
                "batch_rows": int(args.parquet_batch_rows),
                "tables_filter": sorted(parquet_table_filter),
                "tables_excluded": sorted(parquet_exclude_filter),
                "sensitive_guard_enabled": not args.allow_sensitive_parquet,
                "tables": parquet_tables,
            },
        }
        for rel in tracked_files:
            abs_path = snapshot_dir / rel
            manifest["files"].append(
                {
                    "path": rel.as_posix(),
                    "bytes": abs_path.stat().st_size,
                    "sha256": sha256_file(abs_path),
                }
            )
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        tracked_files.append(manifest_rel)

        write_checksums(snapshot_dir, tracked_files)

        latest_payload = {
            "project": "vota-con-la-chola",
            "dataset_repo": dataset_repo,
            "snapshot_date": snapshot_date,
            "snapshot_dir": snapshot_rel_dir.as_posix(),
            "parquet_tables_count": len(parquet_tables),
            "parquet_files_count": len(parquet_rel_paths),
            "updated_at": now_utc_iso(),
        }
        (build_root / "latest.json").write_text(
            json.dumps(latest_payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

        readme_path = build_root / "README.md"
        readme_path.write_text(
            build_dataset_readme(
                dataset_repo=dataset_repo,
                snapshot_date=snapshot_date,
                snapshot_rel_dir=snapshot_rel_dir,
                parquet_tables=parquet_tables,
                parquet_excluded_tables=sorted(parquet_exclude_filter),
                include_sqlite_gz=(not args.skip_sqlite_gz),
                source_repo_url=source_repo_url,
            ),
            encoding="utf-8",
        )

        print(f"HF dataset repo: {dataset_repo}")
        print(f"Snapshot bundle: {snapshot_rel_dir.as_posix()}")
        print(f"Published files: {len(published_rel_paths)}")
        print(f"Ingestion runs rows: {ingestion_runs_rows}")
        print(f"Source records rows (by source): {source_records_rows}")
        print(f"Parquet tables: {len(parquet_tables)}")
        print(f"Parquet files: {len(parquet_rel_paths)}")
        if parquet_exclude_filter:
            print(f"Parquet excluded tables: {', '.join(sorted(parquet_exclude_filter))}")

        if args.dry_run:
            print("Dry run: no se subió nada a Hugging Face")
            print(f"Bundle local: {build_root}")
            return 0

        from huggingface_hub import HfApi  # type: ignore

        api = HfApi(token=hf_token)
        api.create_repo(
            repo_id=dataset_repo,
            repo_type="dataset",
            private=bool(args.private),
            exist_ok=True,
        )

        api.upload_folder(
            repo_id=dataset_repo,
            repo_type="dataset",
            folder_path=str(build_root),
            path_in_repo=".",
            commit_message=f"Publish snapshot {snapshot_date}",
            delete_patterns=[
                f"{snapshot_rel_dir.as_posix()}/**",
                "latest.json",
                "README.md",
            ],
        )

        print(f"OK published to https://huggingface.co/datasets/{dataset_repo}")
        return 0
    except (sqlite3.OperationalError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    finally:
        if temp_ctx is not None:
            temp_ctx.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
