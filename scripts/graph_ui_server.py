#!/usr/bin/env python3
"""Servidor web minimo para explorar grafo y navegar SQLite de forma generica."""

from __future__ import annotations

import argparse
import json
import sqlite3
import unicodedata
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8080
BASE_DIR = Path(__file__).resolve().parent.parent
UI_INDEX = BASE_DIR / "ui" / "graph" / "index.html"
UI_EXPLORER = BASE_DIR / "ui" / "graph" / "explorer.html"

LABEL_COLUMN_CANDIDATES = (
    "full_name",
    "name",
    "label",
    "title",
    "role_title",
    "institution_name",
    "party_name",
    "display_name",
    "acronym",
    "source_record_id",
    "descripcion",
    "description",
    "nombre",
    "code",
    "canonical_key",
    "source_id",
)

FACET_COLUMN_CANDIDATES = (
    # mandates / roles
    "role_id",
    "role_title",
    # common administrative dimensions
    "admin_level_id",
    "level",
    "scope",
    # generic low-cardinality fields
    "status",
    "type",
    "kind",
    "category",
    "territory_code",
    "territory_id",
)


@dataclass
class AppConfig:
    db_path: Path


def normalize_ws(value: str) -> str:
    return " ".join(value.strip().split())


def normalize_key_part(value: str) -> str:
    cleaned = unicodedata.normalize("NFKD", value)
    cleaned = "".join(ch for ch in cleaned if not unicodedata.combining(ch))
    cleaned = cleaned.lower()
    keep: list[str] = []
    for ch in cleaned:
        if ch.isalnum():
            keep.append(ch)
        elif ch in (" ", "-", "_", "/"):
            keep.append(" ")
    return normalize_ws("".join(keep))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="UI de navegacion de grafo + explorador SQLite")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Ruta SQLite a explorar")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host de escucha")
    parser.add_argument("--port", default=DEFAULT_PORT, type=int, help="Puerto HTTP")
    return parser.parse_args()


def open_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def str_param(qs: dict[str, list[str]], key: str, default: str = "") -> str:
    values = qs.get(key)
    if not values:
        return default
    return values[0].strip()


def int_param(qs: dict[str, list[str]], key: str, default: int, *, min_value: int, max_value: int) -> int:
    raw = str_param(qs, key, str(default))
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(min_value, min(max_value, value))


def bool_param(qs: dict[str, list[str]], key: str, default: bool = False) -> bool:
    raw = str_param(qs, key, "1" if default else "0").lower()
    return raw in {"1", "true", "yes", "y", "on"}


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def normalize_type_name(type_name: str | None) -> str:
    if not type_name:
        return ""
    return type_name.strip().upper()


def is_text_like(type_name: str | None) -> bool:
    upper = normalize_type_name(type_name)
    if upper == "":
        return True
    return any(token in upper for token in ("CHAR", "CLOB", "TEXT"))


def safe_json_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return {
            "type": "bytes",
            "length": len(value),
            "preview_hex": value[:24].hex(),
        }
    return value


def is_id_like_column(column: str) -> bool:
    col = (column or "").strip().lower()
    if not col:
        return False
    if col in {"id", "rowid", "__rowid"}:
        return True
    if col.endswith("_id") or col.endswith("_pk"):
        return True
    return False


def fetch_sources(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT source_id, name, scope
        FROM sources
        ORDER BY source_id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def build_graph_payload(
    db_path: Path,
    *,
    source_filter: str | None,
    q: str | None,
    limit: int,
    include_inactive: bool,
) -> dict[str, Any]:
    if not db_path.exists():
        return {
            "meta": {
                "db_path": str(db_path),
                "error": "Base SQLite no encontrada. Ejecuta primero la ingesta ETL.",
            },
            "nodes": [],
            "edges": [],
        }

    try:
        with open_db(db_path) as conn:
            source_rows = fetch_sources(conn)
            source_map = {row["source_id"]: row for row in source_rows}

            where = []
            params: list[Any] = []

            if source_filter:
                where.append("m.source_id = ?")
                params.append(source_filter)

            if q:
                needle = normalize_key_part(q)
                if needle:
                    where.append("p.canonical_key LIKE ?")
                    params.append(f"%{needle}%")

            if not include_inactive:
                where.append("m.is_active = 1")

            where_sql = f"WHERE {' AND '.join(where)}" if where else ""
            params.append(limit)

            rows = conn.execute(
                f"""
                SELECT
                  m.mandate_id,
                  m.source_id,
                  m.role_title,
                  m.is_active,
                  m.start_date,
                  m.end_date,
                  p.person_id,
                  p.full_name,
                  p.given_name,
                  p.family_name,
                  p.territory_code AS person_territory_code,
                  i.institution_id,
                  i.name AS institution_name,
                  i.level AS institution_level,
                  pa.party_id,
                  pa.name AS party_name,
                  pa.acronym AS party_acronym
                FROM mandates m
                JOIN persons p ON p.person_id = m.person_id
                JOIN institutions i ON i.institution_id = m.institution_id
                LEFT JOIN parties pa ON pa.party_id = m.party_id
                {where_sql}
                ORDER BY p.full_name, m.mandate_id
                LIMIT ?
                """,
                params,
            ).fetchall()

            nodes_by_id: dict[str, dict[str, Any]] = {}
            edges: list[dict[str, Any]] = []
            source_person_edges: set[tuple[str, str]] = set()

            for row in rows:
                source_id = row["source_id"]
                source_node_id = f"source:{source_id}"
                person_node_id = f"person:{row['person_id']}"
                institution_node_id = f"institution:{row['institution_id']}"

                source_info = source_map.get(source_id, {"name": source_id, "scope": ""})

                nodes_by_id[source_node_id] = {
                    "data": {
                        "id": source_node_id,
                        "type": "source",
                        "label": source_info["name"],
                        "source_id": source_id,
                        "scope": source_info.get("scope", ""),
                    }
                }
                nodes_by_id[person_node_id] = {
                    "data": {
                        "id": person_node_id,
                        "type": "person",
                        "label": row["full_name"],
                        "person_id": row["person_id"],
                        "full_name": row["full_name"],
                        "given_name": row["given_name"],
                        "family_name": row["family_name"],
                        "territory_code": row["person_territory_code"],
                    }
                }
                nodes_by_id[institution_node_id] = {
                    "data": {
                        "id": institution_node_id,
                        "type": "institution",
                        "label": row["institution_name"],
                        "institution_id": row["institution_id"],
                        "level": row["institution_level"],
                    }
                }

                if row["party_id"] is not None:
                    party_node_id = f"party:{row['party_id']}"
                    nodes_by_id[party_node_id] = {
                        "data": {
                            "id": party_node_id,
                            "type": "party",
                            "label": row["party_name"],
                            "party_id": row["party_id"],
                            "party_name": row["party_name"],
                            "party_acronym": row["party_acronym"],
                        }
                    }
                    edges.append(
                        {
                            "data": {
                                "id": f"mandate-party:{row['mandate_id']}",
                                "type": "party_affiliation",
                                "source": person_node_id,
                                "target": party_node_id,
                                "source_id": source_id,
                                "is_active": row["is_active"],
                            }
                        }
                    )

                edge_key = (source_node_id, person_node_id)
                if edge_key not in source_person_edges:
                    edges.append(
                        {
                            "data": {
                                "id": f"source-person:{source_id}:{row['person_id']}",
                                "type": "source_person",
                                "source": source_node_id,
                                "target": person_node_id,
                            }
                        }
                    )
                    source_person_edges.add(edge_key)

                edges.append(
                    {
                        "data": {
                            "id": f"mandate-institution:{row['mandate_id']}",
                            "type": "mandate",
                            "source": person_node_id,
                            "target": institution_node_id,
                            "label": row["role_title"],
                            "source_id": source_id,
                            "start_date": row["start_date"],
                            "end_date": row["end_date"],
                            "is_active": row["is_active"],
                        }
                    }
                )

            counts = {"source": 0, "person": 0, "party": 0, "institution": 0}
            for node in nodes_by_id.values():
                node_type = node["data"]["type"]
                if node_type in counts:
                    counts[node_type] += 1

            return {
                "meta": {
                    "db_path": str(db_path),
                    "rows": len(rows),
                    "limit": limit,
                    "source_filter": source_filter or "",
                    "search": q or "",
                    "include_inactive": include_inactive,
                    "node_counts": counts,
                    "sources": source_rows,
                },
                "nodes": list(nodes_by_id.values()),
                "edges": edges,
            }
    except sqlite3.Error as exc:
        return {
            "meta": {
                "db_path": str(db_path),
                "error": f"SQLite error: {exc}",
            },
            "nodes": [],
            "edges": [],
        }


def fetch_person_detail(db_path: Path, person_id: int) -> dict[str, Any] | None:
    if not db_path.exists():
        return None

    try:
        with open_db(db_path) as conn:
            person = conn.execute(
                """
                SELECT person_id, full_name, given_name, family_name, birth_date, gender, territory_code
                FROM persons
                WHERE person_id = ?
                """,
                (person_id,),
            ).fetchone()
            if not person:
                return None

            mandates = conn.execute(
                """
                SELECT
                  m.mandate_id,
                  m.source_id,
                  m.role_title,
                  m.level,
                  m.territory_code,
                  m.start_date,
                  m.end_date,
                  m.is_active,
                  i.name AS institution_name,
                  p.name AS party_name,
                  p.acronym AS party_acronym
                FROM mandates m
                JOIN institutions i ON i.institution_id = m.institution_id
                LEFT JOIN parties p ON p.party_id = m.party_id
                WHERE m.person_id = ?
                ORDER BY m.is_active DESC, m.start_date DESC, m.mandate_id DESC
                """,
                (person_id,),
            ).fetchall()

            return {
                "person": dict(person),
                "mandates": [dict(row) for row in mandates],
            }
    except sqlite3.Error:
        return None


def detect_without_rowid(sql: str | None) -> bool:
    if not sql:
        return False
    return "WITHOUT ROWID" in sql.upper()


def fetch_schema(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    table_rows = conn.execute(
        """
        SELECT name, sql
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()

    schema: dict[str, dict[str, Any]] = {}

    for tr in table_rows:
        table_name = tr["name"]
        table_q = quote_ident(table_name)

        columns_raw = conn.execute(f"PRAGMA table_info({table_q})").fetchall()
        columns: list[dict[str, Any]] = []
        for c in columns_raw:
            columns.append(
                {
                    "name": c["name"],
                    "type": c["type"] or "",
                    "notnull": bool(c["notnull"]),
                    "default": c["dflt_value"],
                    "pk_order": int(c["pk"] or 0),
                }
            )

        pk_columns = [
            c["name"]
            for c in sorted(columns, key=lambda col: col["pk_order"])
            if c["pk_order"] > 0
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
                    "to_table": fk["table"],
                    "from_columns": [],
                    "to_columns": [],
                    "on_update": fk["on_update"],
                    "on_delete": fk["on_delete"],
                    "match": fk["match"],
                },
            )
            group["from_columns"].append(fk["from"])
            group["to_columns"].append(fk["to"])

        foreign_keys_out = [fk_groups[k] for k in sorted(fk_groups)]

        search_columns = [c["name"] for c in columns if is_text_like(c["type"])]
        if not search_columns:
            search_columns = [c["name"] for c in columns]

        schema[table_name] = {
            "name": table_name,
            "sql": tr["sql"],
            "without_rowid": detect_without_rowid(tr["sql"]),
            "row_count": row_count,
            "columns": columns,
            "column_names": [c["name"] for c in columns],
            "column_types": {c["name"]: c["type"] for c in columns},
            "primary_key": pk_columns,
            "foreign_keys_out": foreign_keys_out,
            "foreign_keys_in": [],
            "search_columns": search_columns,
        }

    for source_table, meta in schema.items():
        for fk in meta["foreign_keys_out"]:
            target_table = fk["to_table"]
            target_meta = schema.get(target_table)
            if not target_meta:
                continue
            target_meta["foreign_keys_in"].append(
                {
                    "from_table": source_table,
                    "to_table": target_table,
                    "from_columns": fk["from_columns"],
                    "to_columns": fk["to_columns"],
                    "on_update": fk["on_update"],
                    "on_delete": fk["on_delete"],
                }
            )

    for meta in schema.values():
        meta["foreign_keys_in"] = sorted(meta["foreign_keys_in"], key=lambda fk: (fk["from_table"], fk["to_table"]))

    return schema


def infer_row_label(meta: dict[str, Any], row: dict[str, Any]) -> str:
    for candidate in LABEL_COLUMN_CANDIDATES:
        if candidate in row and row[candidate] not in (None, ""):
            return str(row[candidate])

    for col in meta["primary_key"]:
        if col in row and row[col] is not None:
            return f"{col}={row[col]}"

    for col in meta["column_names"]:
        value = row.get(col)
        if isinstance(value, str) and value.strip():
            return value.strip()

    for col in meta["column_names"]:
        value = row.get(col)
        if value is not None:
            return f"{col}={value}"

    return "(registro vacio)"


def enrich_row_label(meta: dict[str, Any], row: dict[str, Any], label: str, preview_display: dict[str, Any]) -> str:
    """
    Make list labels more informative using already-resolved FK labels (no extra queries).
    This keeps navigation usable for tables where the natural label is a generic role/title.
    """
    if not preview_display:
        return label

    # Heuristic: mandates-like rows benefit from surfacing person + party prominently.
    person_disp = preview_display.get("person_id")
    party_disp = preview_display.get("party_id")
    role_title = row.get("role_title") or preview_display.get("role_title")
    raw_person = row.get("person_id")
    raw_party = row.get("party_id")

    # Only treat as "resolved" if it changed away from the raw id (usually numeric).
    person_resolved = (
        isinstance(person_disp, str)
        and person_disp.strip() != ""
        and raw_person is not None
        and str(raw_person) != person_disp
    )
    party_resolved = (
        isinstance(party_disp, str)
        and party_disp.strip() != ""
        and raw_party is not None
        and str(raw_party) != party_disp
    )

    if person_resolved:
        head = person_disp.strip()
        if party_resolved:
            head = f"{head} ({party_disp.strip()})"

        if isinstance(role_title, str) and role_title.strip():
            # If the current label is basically the role/title, append it.
            if label.strip() == role_title.strip():
                return f"{head} · {role_title.strip()}"
        return head

    return label


def build_row_preview(
    meta: dict[str, Any],
    row: dict[str, Any],
    *,
    schema: dict[str, dict[str, Any]] | None = None,
    max_items: int = 6,
) -> dict[str, Any]:
    """
    Small row summary for list views.

    Rules:
    - Prefer human-friendly label-ish columns.
    - Include FK columns (even if *_id) so the UI can resolve them to labels.
    - Avoid showing unrelated ids when we already have human fields.
    """
    preferred_human = [c for c in LABEL_COLUMN_CANDIDATES if c in row and not is_id_like_column(c)]
    preferred_ids = [c for c in LABEL_COLUMN_CANDIDATES if c in row and is_id_like_column(c)]

    def has_sibling_human(prefix: str) -> bool:
        for suffix in ("_title", "_name", "_label", "_code"):
            key = f"{prefix}{suffix}"
            val = row.get(key)
            if val not in (None, ""):
                return True
        return False

    fk_infos: list[dict[str, Any]] = []
    fk_col_set: set[str] = set()
    for fk in meta.get("foreign_keys_out") or []:
        to_table = fk.get("to_table") or ""
        to_row_count = None
        if schema is not None and to_table in schema:
            to_row_count = schema[to_table].get("row_count")
        for col in fk.get("from_columns") or []:
            if col not in row or col in fk_col_set:
                continue
            fk_col_set.add(col)
            prefix = col[:-3] if col.endswith("_id") else (col[:-3] if col.endswith("_pk") else "")
            sibling_penalty = 1 if (prefix and has_sibling_human(prefix)) else 0
            source_penalty = 1 if (col.startswith("source_") or to_table in {"sources", "source_records"}) else 0
            fk_infos.append(
                {
                    "col": col,
                    "to_table": to_table,
                    "to_row_count": to_row_count,
                    "sibling_penalty": sibling_penalty,
                    "source_penalty": source_penalty,
                }
            )

    def fk_sort_key(info: dict[str, Any]) -> tuple[int, int, int, str]:
        rc = info.get("to_row_count")
        # Prefer "real entity" targets over dimensions/sources and prefer bigger targets.
        rc_int = int(rc) if isinstance(rc, int) else -1
        return (int(info["sibling_penalty"]), int(info["source_penalty"]), -rc_int, str(info["col"]))

    fk_infos.sort(key=fk_sort_key)
    # Keep list previews readable and keep FK label resolution cheap.
    max_fk_cols = min(3, max_items)
    fk_cols = [info["col"] for info in fk_infos[:max_fk_cols]]

    rest = [c for c in meta["column_names"] if c not in preferred_human and c not in preferred_ids and c not in fk_col_set]

    def rest_sort_key(col: str) -> tuple[int, str]:
        c = (col or "").lower()
        if c in {"start_date", "start_at"}:
            return (0, col)
        if c.endswith("_code") or "code" in c:
            return (1, col)
        if c in {"end_date", "end_at"}:
            return (2, col)
        # Deprioritize audit/provenance timestamps by default in list previews.
        if c in {"created_at", "updated_at", "first_seen_at", "last_seen_at"} or c.endswith("_seen_at"):
            return (10, col)
        if c == "level":
            return (9, col)
        if "date" in c or c.endswith("_at"):
            return (3, col)
        return (4, col)

    rest.sort(key=rest_sort_key)
    ordered = preferred_human + fk_cols + rest + preferred_ids

    preview: dict[str, Any] = {}
    for col in ordered:
        if col not in row:
            continue
        value = row[col]
        if value is None:
            continue
        # Prefer human-friendly columns over arbitrary ids, but keep FK ids for label resolution.
        if is_id_like_column(col) and col not in fk_col_set and len(preview) > 0:
            continue
        preview[col] = safe_json_value(value)
        if len(preview) >= max_items:
            break
    return preview


def choose_label_column(meta: dict[str, Any]) -> str | None:
    for cand in LABEL_COLUMN_CANDIDATES:
        if cand in meta["column_names"]:
            return cand
    # Fallback: first text-like column.
    for col in meta["column_names"]:
        if is_text_like(meta["column_types"].get(col)):
            return col
    return None


def resolve_fk_preview_labels(
    conn: sqlite3.Connection,
    schema: dict[str, dict[str, Any]],
    *,
    from_table: str,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Returns per-row preview_display dicts, resolving single-column FKs present in preview to
    human-friendly labels using a small number of batched queries.
    """
    from_meta = schema.get(from_table)
    if not from_meta:
        return [dict(r.get("preview") or {}) for r in rows]

    # Identify resolvable single-column FKs where target has a single-column PK.
    resolvable: list[dict[str, Any]] = []
    for fk in from_meta["foreign_keys_out"]:
        from_cols = fk.get("from_columns") or []
        to_cols = fk.get("to_columns") or []
        if len(from_cols) != 1 or len(to_cols) != 1:
            continue
        to_table = fk.get("to_table")
        to_meta = schema.get(to_table)
        if not to_meta:
            continue
        if len(to_meta["primary_key"]) != 1:
            continue
        if to_cols[0] != to_meta["primary_key"][0]:
            continue
        resolvable.append(
            {
                "from_col": from_cols[0],
                "to_table": to_table,
                "to_pk": to_meta["primary_key"][0],
                "to_label_col": choose_label_column(to_meta),
            }
        )

    if not resolvable:
        return [dict(r.get("preview") or {}) for r in rows]

    # Collect values per fk column present in previews.
    values_by_col: dict[str, set[Any]] = {}
    for r in rows:
        preview = r.get("preview") or {}
        for fk in resolvable:
            from_col = fk["from_col"]
            if from_col not in preview:
                continue
            val = preview[from_col]
            if val is None or isinstance(val, dict):
                continue
            values_by_col.setdefault(from_col, set()).add(val)

    label_maps: dict[str, dict[Any, str]] = {}
    for fk in resolvable:
        from_col = fk["from_col"]
        vals = values_by_col.get(from_col)
        if not vals:
            continue

        to_table = fk["to_table"]
        to_pk = fk["to_pk"]
        label_col = fk["to_label_col"]
        to_meta = schema.get(to_table)
        if not to_meta:
            continue

        # Batched lookup: pk -> label
        placeholders = ",".join("?" for _ in vals)
        cols = [to_pk]
        if label_col and label_col != to_pk:
            cols.append(label_col)
        cols_sql = ", ".join(quote_ident(c) for c in cols)
        table_q = quote_ident(to_table)
        pk_q = quote_ident(to_pk)
        fetched = conn.execute(
            f"SELECT {cols_sql} FROM {table_q} WHERE {pk_q} IN ({placeholders})",
            list(vals),
        ).fetchall()

        mapping: dict[Any, str] = {}
        for row in fetched:
            row_d = dict(row)
            pk_val = row_d.get(to_pk)
            if pk_val is None:
                continue
            if label_col and row_d.get(label_col) not in (None, ""):
                mapping[pk_val] = str(row_d[label_col])
            else:
                mapping[pk_val] = infer_row_label(to_meta, row_d)
        label_maps[from_col] = mapping

    displays: list[dict[str, Any]] = []
    for r in rows:
        preview = dict(r.get("preview") or {})
        preview_display = dict(preview)
        for fk in resolvable:
            from_col = fk["from_col"]
            if from_col not in preview:
                continue
            raw_val = preview[from_col]
            if raw_val is None or isinstance(raw_val, dict):
                continue
            label = label_maps.get(from_col, {}).get(raw_val)
            if label:
                preview_display[from_col] = label
        displays.append(preview_display)
    return displays


def row_identity(meta: dict[str, Any], row: dict[str, Any]) -> dict[str, Any] | None:
    if meta["primary_key"]:
        ident: dict[str, Any] = {}
        for col in meta["primary_key"]:
            if col not in row:
                return None
            ident[col] = safe_json_value(row[col])
        return ident

    if not meta["without_rowid"] and "__rowid" in row:
        return {"rowid": safe_json_value(row["__rowid"])}

    return None


def build_locator_from_query(meta: dict[str, Any], qs: dict[str, list[str]]) -> tuple[str, list[Any]]:
    if meta["primary_key"]:
        conditions: list[str] = []
        params: list[Any] = []
        for col in meta["primary_key"]:
            raw = str_param(qs, col, "")
            if raw == "":
                raise ValueError(f"missing pk field '{col}'")
            conditions.append(f"{quote_ident(col)} = ?")
            params.append(raw)
        return " AND ".join(conditions), params

    if meta["without_rowid"]:
        raise ValueError("table has no primary key and is WITHOUT ROWID")

    raw_rowid = str_param(qs, "rowid", "")
    if raw_rowid == "":
        raise ValueError("missing rowid")
    return "rowid = ?", [raw_rowid]


def relation_samples(
    conn: sqlite3.Connection,
    schema: dict[str, dict[str, Any]],
    *,
    table: str,
    where_columns: list[str],
    values: list[Any],
    sample_limit: int = 8,
) -> tuple[int, list[dict[str, Any]]]:
    meta = schema.get(table)
    if not meta:
        return 0, []

    table_q = quote_ident(table)
    where_sql = " AND ".join(f"{quote_ident(col)} = ?" for col in where_columns)

    count_row = conn.execute(
        f"SELECT COUNT(*) AS n FROM {table_q} WHERE {where_sql}",
        values,
    ).fetchone()
    total = int(count_row["n"] if count_row else 0)

    select_columns = ", ".join(quote_ident(col) for col in meta["column_names"])
    select_sql = select_columns
    if not meta["primary_key"] and not meta["without_rowid"]:
        select_sql = f"rowid AS __rowid, {select_columns}"

    rows = conn.execute(
        f"SELECT {select_sql} FROM {table_q} WHERE {where_sql} LIMIT ?",
        [*values, sample_limit],
    ).fetchall()

    sample_items: list[dict[str, Any]] = []
    row_dicts: list[dict[str, Any]] = []
    for row in rows:
        row_dict = dict(row)
        row_dicts.append(row_dict)
        ident = row_identity(meta, row_dict)
        sample_items.append(
            {
                "table": table,
                "identity": ident,
                "can_open": ident is not None,
                "label": infer_row_label(meta, row_dict),
                "preview": build_row_preview(meta, row_dict, schema=schema),
            }
        )

    preview_displays = resolve_fk_preview_labels(conn, schema, from_table=table, rows=sample_items)
    for i, disp in enumerate(preview_displays):
        sample_items[i]["preview_display"] = disp
        sample_items[i]["label"] = enrich_row_label(meta, row_dicts[i], sample_items[i]["label"], disp)

    return total, sample_items


def relation_facets(
    conn: sqlite3.Connection,
    schema: dict[str, dict[str, Any]],
    *,
    table: str,
    where_columns: list[str],
    values: list[Any],
    total: int,
    facet_limit: int = 8,
) -> dict[str, Any] | None:
    """
    Optional grouped counts for a relation, to avoid noisy repeated sample pills (e.g. "Concejal" many times).
    Returns {column, items:[{value, display?, count}]} or None.
    """
    if total < max(8, facet_limit):
        return None

    meta = schema.get(table)
    if not meta:
        return None

    facet_col = next((c for c in FACET_COLUMN_CANDIDATES if c in meta["column_names"] and c not in where_columns), None)
    if not facet_col:
        return None

    table_q = quote_ident(table)
    where_sql = " AND ".join(f"{quote_ident(col)} = ?" for col in where_columns) if where_columns else "1=1"
    facet_q = quote_ident(facet_col)

    try:
        rows = conn.execute(
            f"""
            SELECT {facet_q} AS v, COUNT(*) AS n
            FROM {table_q}
            WHERE {where_sql}
              AND {facet_q} IS NOT NULL
              AND TRIM(CAST({facet_q} AS TEXT)) != ''
            GROUP BY {facet_q}
            ORDER BY n DESC, v
            LIMIT ?
            """,
            [*values, facet_limit],
        ).fetchall()
    except sqlite3.Error:
        return None

    items: list[dict[str, Any]] = []
    for r in rows:
        v = r["v"]
        n = int(r["n"] or 0)
        if v in (None, "") or n <= 0:
            continue
        items.append({"value": safe_json_value(v), "count": n})

    if not items:
        return None

    # If everything is unique, facets are noise (e.g. grouping by full_name).
    if items[0]["count"] <= 1:
        return None

    # If facet column is a resolvable single-column FK, add "display" labels.
    if is_id_like_column(facet_col):
        fk = next(
            (
                fk
                for fk in meta.get("foreign_keys_out") or []
                if (fk.get("from_columns") or []) == [facet_col] and len(fk.get("to_columns") or []) == 1
            ),
            None,
        )
        if fk:
            to_table = fk.get("to_table")
            to_meta = schema.get(to_table) if to_table else None
            if to_meta and len(to_meta.get("primary_key") or []) == 1 and (fk.get("to_columns") or [None])[0] == to_meta["primary_key"][0]:
                to_pk = to_meta["primary_key"][0]
                label_col = choose_label_column(to_meta)
                vals = [it["value"] for it in items]
                placeholders = ",".join("?" for _ in vals)
                cols = [to_pk]
                if label_col and label_col != to_pk:
                    cols.append(label_col)
                cols_sql = ", ".join(quote_ident(c) for c in cols)
                fetched = conn.execute(
                    f"SELECT {cols_sql} FROM {quote_ident(to_table)} WHERE {quote_ident(to_pk)} IN ({placeholders})",
                    vals,
                ).fetchall()
                mapping: dict[Any, str] = {}
                for row in fetched:
                    row_d = dict(row)
                    pk_val = row_d.get(to_pk)
                    if pk_val is None:
                        continue
                    if label_col and row_d.get(label_col) not in (None, ""):
                        mapping[pk_val] = str(row_d[label_col])
                    else:
                        mapping[pk_val] = infer_row_label(to_meta, row_d)
                for it in items:
                    raw = it["value"]
                    if raw in mapping:
                        it["display"] = mapping[raw]

    return {"column": facet_col, "items": items}


def build_explorer_schema_payload(db_path: Path) -> dict[str, Any]:
    if not db_path.exists():
        return {
            "meta": {
                "db_path": str(db_path),
                "error": "Base SQLite no encontrada.",
            },
            "tables": [],
        }

    try:
        with open_db(db_path) as conn:
            schema = fetch_schema(conn)

            tables: list[dict[str, Any]] = []
            for meta in schema.values():
                tables.append(
                    {
                        "name": meta["name"],
                        "row_count": meta["row_count"],
                        "column_count": len(meta["columns"]),
                        "primary_key": meta["primary_key"],
                        "without_rowid": meta["without_rowid"],
                        "search_columns": meta["search_columns"][:8],
                        "columns": [
                            {
                                "name": c["name"],
                                "type": c["type"],
                                "notnull": c["notnull"],
                                "pk_order": c["pk_order"],
                            }
                            for c in meta["columns"]
                        ],
                        "label_column": choose_label_column(meta),
                        "foreign_keys_out": [
                            {
                                "to_table": fk["to_table"],
                                "from_columns": fk["from_columns"],
                                "to_columns": fk["to_columns"],
                            }
                            for fk in meta["foreign_keys_out"]
                        ],
                        "foreign_keys_in": [
                            {
                                "from_table": fk["from_table"],
                                "from_columns": fk["from_columns"],
                                "to_columns": fk["to_columns"],
                            }
                            for fk in meta["foreign_keys_in"]
                        ],
                    }
                )

            tables.sort(key=lambda t: ((t["row_count"] is None), -(t["row_count"] or 0), t["name"]))

            return {
                "meta": {
                    "db_path": str(db_path),
                    "table_count": len(tables),
                },
                "tables": tables,
            }
    except sqlite3.Error as exc:
        return {
            "meta": {
                "db_path": str(db_path),
                "error": f"SQLite error: {exc}",
            },
            "tables": [],
        }


def build_explorer_rows_payload(
    db_path: Path,
    *,
    table: str,
    q: str,
    where_columns: list[str],
    where_values: list[str],
    limit: int,
    offset: int,
) -> dict[str, Any]:
    if not db_path.exists():
        return {"error": "Base SQLite no encontrada."}

    if len(where_columns) != len(where_values):
        return {"error": "Parametros 'col' y 'val' deben tener la misma longitud"}

    try:
        with open_db(db_path) as conn:
            schema = fetch_schema(conn)
            meta = schema.get(table)
            if not meta:
                return {"error": f"Tabla no encontrada: {table}"}

            table_q = quote_ident(table)

            for col in where_columns:
                if col == "rowid":
                    if meta["without_rowid"]:
                        return {"error": f"Tabla {table} es WITHOUT ROWID; no se puede filtrar por rowid"}
                    continue
                if col not in meta["column_names"]:
                    return {"error": f"Columna no encontrada en {table}: {col}"}

            where_parts: list[str] = []
            where_params: list[Any] = []

            if where_columns:
                for col, val in zip(where_columns, where_values, strict=True):
                    if col == "rowid":
                        where_parts.append("rowid = ?")
                    else:
                        where_parts.append(f"{quote_ident(col)} = ?")
                    where_params.append(val)

            q_norm = q.strip()
            if q_norm:
                search_cols = meta["search_columns"][:8]
                if search_cols:
                    like_parts = [f"CAST({quote_ident(col)} AS TEXT) LIKE ?" for col in search_cols]
                    like = f"%{q_norm}%"
                    where_parts.append("(" + " OR ".join(like_parts) + ")")
                    where_params.extend([like] * len(search_cols))

            where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

            total_row = conn.execute(
                f"SELECT COUNT(*) AS n FROM {table_q} {where_sql}",
                where_params,
            ).fetchone()
            total = int(total_row["n"] if total_row else 0)

            select_columns = ", ".join(quote_ident(col) for col in meta["column_names"])
            select_sql = select_columns
            if not meta["primary_key"] and not meta["without_rowid"]:
                select_sql = f"rowid AS __rowid, {select_columns}"

            if meta["primary_key"]:
                order_sql = "ORDER BY " + ", ".join(quote_ident(col) for col in meta["primary_key"])
            elif not meta["without_rowid"]:
                order_sql = "ORDER BY rowid"
            elif meta["column_names"]:
                order_sql = f"ORDER BY {quote_ident(meta['column_names'][0])}"
            else:
                order_sql = ""

            rows = conn.execute(
                f"""
                SELECT {select_sql}
                FROM {table_q}
                {where_sql}
                {order_sql}
                LIMIT ? OFFSET ?
                """,
                [*where_params, limit, offset],
            ).fetchall()

            items: list[dict[str, Any]] = []
            row_dicts: list[dict[str, Any]] = []
            for row in rows:
                row_dict = dict(row)
                row_dicts.append(row_dict)
                ident = row_identity(meta, row_dict)
                items.append(
                    {
                        "identity": ident,
                        "can_open": ident is not None,
                        "label": infer_row_label(meta, row_dict),
                        "preview": build_row_preview(meta, row_dict, schema=schema),
                    }
                )

            preview_displays = resolve_fk_preview_labels(conn, schema, from_table=table, rows=items)
            for i, disp in enumerate(preview_displays):
                items[i]["preview_display"] = disp
                items[i]["label"] = enrich_row_label(meta, row_dicts[i], items[i]["label"], disp)

            return {
                "meta": {
                    "db_path": str(db_path),
                    "table": table,
                    "q": q_norm,
                    "where": {where_columns[i]: where_values[i] for i in range(len(where_columns))},
                    "limit": limit,
                    "offset": offset,
                    "total": total,
                    "returned": len(items),
                    "primary_key": meta["primary_key"],
                    "without_rowid": meta["without_rowid"],
                    "column_names": meta["column_names"],
                },
                "rows": items,
            }
    except sqlite3.Error as exc:
        return {"error": f"SQLite error: {exc}"}


def build_explorer_record_payload(
    db_path: Path,
    *,
    table: str,
    qs: dict[str, list[str]],
) -> dict[str, Any]:
    if not db_path.exists():
        return {"error": "Base SQLite no encontrada."}

    try:
        with open_db(db_path) as conn:
            schema = fetch_schema(conn)
            meta = schema.get(table)
            if not meta:
                return {"error": f"Tabla no encontrada: {table}"}

            try:
                where_expr, where_params = build_locator_from_query(meta, qs)
            except ValueError as exc:
                return {"error": str(exc)}

            table_q = quote_ident(table)
            select_columns = ", ".join(quote_ident(col) for col in meta["column_names"])
            select_sql = select_columns
            if not meta["primary_key"] and not meta["without_rowid"]:
                select_sql = f"rowid AS __rowid, {select_columns}"

            row = conn.execute(
                f"SELECT {select_sql} FROM {table_q} WHERE {where_expr} LIMIT 1",
                where_params,
            ).fetchone()
            if not row:
                return {"error": "Registro no encontrado"}

            row_dict = dict(row)
            row_identity_value = row_identity(meta, row_dict)

            outgoing: list[dict[str, Any]] = []
            for fk in meta["foreign_keys_out"]:
                from_cols = fk["from_columns"]
                to_cols = fk["to_columns"]
                if len(from_cols) != len(to_cols):
                    continue

                values = [row_dict.get(col) for col in from_cols]
                nullable = any(v is None for v in values)
                relation = {
                    "direction": "outgoing",
                    "from_table": table,
                    "to_table": fk["to_table"],
                    "from_columns": from_cols,
                    "to_columns": to_cols,
                    "match": {from_cols[i]: safe_json_value(values[i]) for i in range(len(from_cols))},
                    "count": 0,
                    "samples": [],
                    "nullable": nullable,
                }

                if not nullable:
                    total, samples = relation_samples(
                        conn,
                        schema,
                        table=fk["to_table"],
                        where_columns=to_cols,
                        values=values,
                    )
                    relation["count"] = total
                    relation["samples"] = samples
                    facets = relation_facets(
                        conn,
                        schema,
                        table=fk["to_table"],
                        where_columns=to_cols,
                        values=values,
                        total=total,
                    )
                    if facets:
                        relation["facets"] = facets

                outgoing.append(relation)

            incoming: list[dict[str, Any]] = []
            for fk in meta["foreign_keys_in"]:
                from_cols = fk["from_columns"]
                to_cols = fk["to_columns"]
                if len(from_cols) != len(to_cols):
                    continue

                values = [row_dict.get(col) for col in to_cols]
                nullable = any(v is None for v in values)
                relation = {
                    "direction": "incoming",
                    "from_table": fk["from_table"],
                    "to_table": table,
                    "from_columns": from_cols,
                    "to_columns": to_cols,
                    "match": {to_cols[i]: safe_json_value(values[i]) for i in range(len(to_cols))},
                    "count": 0,
                    "samples": [],
                    "nullable": nullable,
                }

                if not nullable:
                    total, samples = relation_samples(
                        conn,
                        schema,
                        table=fk["from_table"],
                        where_columns=from_cols,
                        values=values,
                    )
                    relation["count"] = total
                    relation["samples"] = samples
                    facets = relation_facets(
                        conn,
                        schema,
                        table=fk["from_table"],
                        where_columns=from_cols,
                        values=values,
                        total=total,
                    )
                    if facets:
                        relation["facets"] = facets

                incoming.append(relation)

            return {
                "meta": {
                    "db_path": str(db_path),
                    "table": table,
                    "primary_key": meta["primary_key"],
                    "without_rowid": meta["without_rowid"],
                    "label": infer_row_label(meta, row_dict),
                },
                "record": {
                    "identity": row_identity_value,
                    "values": {k: safe_json_value(v) for k, v in row_dict.items() if k != "__rowid"},
                    "preview": build_row_preview(meta, row_dict, schema=schema, max_items=8),
                },
                "relations": {
                    "outgoing": outgoing,
                    "incoming": incoming,
                },
            }
    except sqlite3.Error as exc:
        return {"error": f"SQLite error: {exc}"}


def build_explorer_related_rows_payload(
    db_path: Path,
    *,
    table: str,
    where_columns: list[str],
    where_values: list[str],
    limit: int,
    offset: int,
) -> dict[str, Any]:
    if not db_path.exists():
        return {"error": "Base SQLite no encontrada."}

    if len(where_columns) != len(where_values):
        return {"error": "Parametros 'col' y 'val' deben tener la misma longitud"}

    try:
        with open_db(db_path) as conn:
            schema = fetch_schema(conn)
            meta = schema.get(table)
            if not meta:
                return {"error": f"Tabla no encontrada: {table}"}

            for col in where_columns:
                if col not in meta["column_names"]:
                    return {"error": f"Columna no encontrada en {table}: {col}"}

            table_q = quote_ident(table)
            where_sql = " AND ".join(f"{quote_ident(col)} = ?" for col in where_columns) if where_columns else "1=1"

            total_row = conn.execute(
                f"SELECT COUNT(*) AS n FROM {table_q} WHERE {where_sql}",
                where_values,
            ).fetchone()
            total = int(total_row["n"] if total_row else 0)

            select_columns = ", ".join(quote_ident(col) for col in meta["column_names"])
            select_sql = select_columns
            if not meta["primary_key"] and not meta["without_rowid"]:
                select_sql = f"rowid AS __rowid, {select_columns}"

            if meta["primary_key"]:
                order_sql = "ORDER BY " + ", ".join(quote_ident(col) for col in meta["primary_key"])
            elif not meta["without_rowid"]:
                order_sql = "ORDER BY rowid"
            elif meta["column_names"]:
                order_sql = f"ORDER BY {quote_ident(meta['column_names'][0])}"
            else:
                order_sql = ""

            rows = conn.execute(
                f"""
                SELECT {select_sql}
                FROM {table_q}
                WHERE {where_sql}
                {order_sql}
                LIMIT ? OFFSET ?
                """,
                [*where_values, limit, offset],
            ).fetchall()

            items: list[dict[str, Any]] = []
            row_dicts: list[dict[str, Any]] = []
            for row in rows:
                row_dict = dict(row)
                row_dicts.append(row_dict)
                ident = row_identity(meta, row_dict)
                items.append(
                    {
                        "identity": ident,
                        "can_open": ident is not None,
                        "label": infer_row_label(meta, row_dict),
                        "preview": build_row_preview(meta, row_dict, schema=schema),
                    }
                )

            preview_displays = resolve_fk_preview_labels(conn, schema, from_table=table, rows=items)
            for i, disp in enumerate(preview_displays):
                items[i]["preview_display"] = disp
                items[i]["label"] = enrich_row_label(meta, row_dicts[i], items[i]["label"], disp)

            return {
                "meta": {
                    "db_path": str(db_path),
                    "table": table,
                    "where": {where_columns[i]: where_values[i] for i in range(len(where_columns))},
                    "limit": limit,
                    "offset": offset,
                    "total": total,
                    "returned": len(items),
                    "primary_key": meta["primary_key"],
                    "without_rowid": meta["without_rowid"],
                },
                "rows": items,
            }
    except sqlite3.Error as exc:
        return {"error": f"SQLite error: {exc}"}

def json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")


def create_handler(config: AppConfig) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "GraphUI/0.2"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def write_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json_bytes(payload)
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def write_html(self, html: str, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = html.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path

            if path in ("/", "/index.html"):
                if not UI_INDEX.exists():
                    self.write_html("<h1>UI no encontrada</h1>", status=HTTPStatus.NOT_FOUND)
                    return
                self.write_html(UI_INDEX.read_text(encoding="utf-8"))
                return

            if path in ("/explorer", "/explorer.html"):
                if not UI_EXPLORER.exists():
                    self.write_html("<h1>UI explorer no encontrada</h1>", status=HTTPStatus.NOT_FOUND)
                    return
                self.write_html(UI_EXPLORER.read_text(encoding="utf-8"))
                return

            if path == "/api/health":
                self.write_json(
                    {
                        "status": "ok",
                        "db_exists": config.db_path.exists(),
                        "db_path": str(config.db_path),
                    }
                )
                return

            if path == "/api/graph":
                qs = parse_qs(parsed.query, keep_blank_values=False)
                limit = int_param(qs, "limit", 350, min_value=20, max_value=2000)
                source_filter = str_param(qs, "source_id", "") or None
                search = str_param(qs, "q", "") or None
                include_inactive = bool_param(qs, "include_inactive", False)
                payload = build_graph_payload(
                    config.db_path,
                    source_filter=source_filter,
                    q=search,
                    limit=limit,
                    include_inactive=include_inactive,
                )
                self.write_json(payload)
                return

            if path.startswith("/api/person/"):
                try:
                    person_id = int(path.rsplit("/", 1)[-1])
                except ValueError:
                    self.write_json(
                        {"error": "person_id invalido"},
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return

                payload = fetch_person_detail(config.db_path, person_id)
                if payload is None:
                    self.write_json(
                        {"error": "Persona no encontrada"},
                        status=HTTPStatus.NOT_FOUND,
                    )
                    return

                self.write_json(payload)
                return

            if path == "/api/explorer/schema":
                payload = build_explorer_schema_payload(config.db_path)
                self.write_json(payload)
                return

            if path == "/api/explorer/rows":
                qs = parse_qs(parsed.query, keep_blank_values=False)
                table = str_param(qs, "table", "")
                if not table:
                    self.write_json({"error": "Parametro 'table' requerido"}, status=HTTPStatus.BAD_REQUEST)
                    return

                limit = int_param(qs, "limit", 50, min_value=1, max_value=500)
                offset = int_param(qs, "offset", 0, min_value=0, max_value=5_000_000)
                q = str_param(qs, "q", "")
                where_columns = qs.get("col", [])
                where_values = qs.get("val", [])
                payload = build_explorer_rows_payload(
                    config.db_path,
                    table=table,
                    q=q,
                    where_columns=[str(c) for c in where_columns],
                    where_values=[str(v) for v in where_values],
                    limit=limit,
                    offset=offset,
                )
                status = HTTPStatus.BAD_REQUEST if "error" in payload else HTTPStatus.OK
                self.write_json(payload, status=status)
                return

            if path == "/api/explorer/record":
                qs = parse_qs(parsed.query, keep_blank_values=False)
                table = str_param(qs, "table", "")
                if not table:
                    self.write_json({"error": "Parametro 'table' requerido"}, status=HTTPStatus.BAD_REQUEST)
                    return

                payload = build_explorer_record_payload(
                    config.db_path,
                    table=table,
                    qs=qs,
                )
                status = HTTPStatus.BAD_REQUEST if "error" in payload else HTTPStatus.OK
                self.write_json(payload, status=status)
                return

            if path == "/api/explorer/related":
                qs = parse_qs(parsed.query, keep_blank_values=False)
                table = str_param(qs, "table", "")
                if not table:
                    self.write_json({"error": "Parametro 'table' requerido"}, status=HTTPStatus.BAD_REQUEST)
                    return

                where_columns = qs.get("col", [])
                where_values = qs.get("val", [])
                limit = int_param(qs, "limit", 50, min_value=1, max_value=500)
                offset = int_param(qs, "offset", 0, min_value=0, max_value=5_000_000)
                payload = build_explorer_related_rows_payload(
                    config.db_path,
                    table=table,
                    where_columns=[str(c) for c in where_columns],
                    where_values=[str(v) for v in where_values],
                    limit=limit,
                    offset=offset,
                )
                status = HTTPStatus.BAD_REQUEST if "error" in payload else HTTPStatus.OK
                self.write_json(payload, status=status)
                return

            self.write_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    return Handler


def main() -> int:
    args = parse_args()
    config = AppConfig(db_path=Path(args.db))
    server = ThreadingHTTPServer((args.host, args.port), create_handler(config))
    print(f"Graph UI en http://{args.host}:{args.port} | db={config.db_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
