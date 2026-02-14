#!/usr/bin/env python3
"""Servidor web minimo para explorar grafo y navegar SQLite de forma generica."""

from __future__ import annotations

from datetime import datetime, timezone
import argparse
import json
import sys
import sqlite3
import unicodedata
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from functools import lru_cache
from typing import Any
from urllib.parse import parse_qs, urlparse

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8080
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
UI_INDEX = BASE_DIR / "ui" / "graph" / "index.html"
UI_EXPLORERS = BASE_DIR / "ui" / "graph" / "explorers.html"
UI_GRAPH = BASE_DIR / "ui" / "graph" / "index.html"
UI_EXPLORER = BASE_DIR / "ui" / "graph" / "explorer.html"
UI_EXPLORER_POLITICO = BASE_DIR / "ui" / "graph" / "explorer-sports.html"
UI_EXPLORER_VOTACIONES = BASE_DIR / "ui" / "graph" / "explorer-votaciones.html"
UI_EXPLORER_SOURCES = BASE_DIR / "ui" / "graph" / "explorer-sources.html"
UI_EXPLORER_TEMAS = BASE_DIR / "ui" / "graph" / "explorer-temas.html"
MUNICIPALITY_POPULATION_PATH = BASE_DIR / "etl" / "data" / "published" / "poblacion_municipios_es.json"
TRACKER_PATH = BASE_DIR / "docs" / "etl" / "e2e-scrape-load-tracker.md"
IDEAL_SOURCES_PATH = BASE_DIR / "docs" / "ideal_sources_say_do.json"

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


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def is_municipal_level(level: Any) -> bool:
    normalized = normalize_key_part(safe_text(level))
    return bool(normalized) and (
        "municipal" in normalized or "ayuntamiento" in normalized or "concejal" in normalized or "local" in normalized
    )


def normalize_municipality_code(value: Any) -> str:
    token = "".join(ch for ch in safe_text(value) if ch.isdigit())
    if len(token) == 5:
        return token
    return ""


def row_value(row: Any, key: str) -> Any:
    try:
        if hasattr(row, "get"):
            try:
                return row.get(key)
            except Exception:
                pass
        return row[key]
    except Exception:
        return None


def municipality_name_guess(name: Any, level: Any) -> str:
    text = safe_text(name)
    if text:
        return text
    normalized = normalize_key_part(level)
    if normalized:
        return normalized
    return "Sin municipio"


@lru_cache(maxsize=1)
def load_municipality_population() -> dict[str, int]:
    if not MUNICIPALITY_POPULATION_PATH.exists():
        return {}
    try:
        payload = json.loads(MUNICIPALITY_POPULATION_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    by_code: dict[str, int] = {}
    for entry in payload.get("municipalities", []):
        code = normalize_municipality_code(entry.get("municipality_code"))
        if not code:
            continue
        population = entry.get("population_total")
        if population is None:
            continue
        try:
            by_code[code] = int(population)
        except (TypeError, ValueError):
            continue
    return by_code


def extract_municipality_fields(row: sqlite3.Row, population_by_code: dict[str, int]) -> tuple[str, str, int | None]:
    candidates = [
        (row_value(row, "mandate_territory_code"), row_value(row, "mandate_territory_name"), row_value(row, "mandate_territory_level")),
        (row_value(row, "institution_territory_code"), row_value(row, "institution_territory_name"), row_value(row, "institution_territory_level")),
        (row_value(row, "person_territory_code"), row_value(row, "person_territory_name"), row_value(row, "person_territory_level")),
    ]

    for code, name, level in candidates:
        normalized = normalize_municipality_code(code)
        if normalized and is_municipal_level(level):
            return normalized, municipality_name_guess(name, level), population_by_code.get(normalized)

    for code, name, level in candidates:
        normalized = normalize_municipality_code(code)
        if normalized and population_by_code.get(normalized) is not None:
            return normalized, municipality_name_guess(name, level), population_by_code.get(normalized)

    for code, name, level in candidates:
        normalized = normalize_municipality_code(code)
        if normalized:
            return normalized, municipality_name_guess(name, level), population_by_code.get(normalized)

    return "", "", None

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


def to_int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_source_config(value: Any, *, domain: str) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}

    plan: dict[str, dict[str, Any]] = {}
    for source_id, cfg in value.items():
        if not isinstance(cfg, dict):
            continue
        sid = safe_text(source_id)
        if not sid:
            continue
        plan[sid] = {
            "source_id": sid,
            "domain": safe_text(domain),
            "name": safe_text(cfg.get("name")) or sid,
            "scope": safe_text(cfg.get("scope")),
            "default_url": safe_text(cfg.get("default_url")),
            "institution_name": safe_text(cfg.get("institution_name")),
            "role_title": safe_text(cfg.get("role_title")),
            "level": safe_text(cfg.get("level")),
            "format": safe_text(cfg.get("format")),
            "fallback_file": safe_text(cfg.get("fallback_file")),
            "min_records_loaded_strict": to_int_or_none(cfg.get("min_records_loaded_strict")),
        }
    return plan


try:
    from etl.politicos_es.config import SOURCE_CONFIG as POLITICOS_SOURCE_CONFIG
except Exception:
    POLITICOS_SOURCE_CONFIG = {}

try:
    from etl.parlamentario_es.config import SOURCE_CONFIG as PARLAMENTARIO_SOURCE_CONFIG
except Exception:
    PARLAMENTARIO_SOURCE_CONFIG = {}

try:
    from etl.infoelectoral_es.config import SOURCE_CONFIG as INFOELECTORAL_SOURCE_CONFIG
except Exception:
    INFOELECTORAL_SOURCE_CONFIG = {}


DESIRED_SOURCES: dict[str, dict[str, Any]] = {}
DESIRED_SOURCES.update(_coerce_source_config(POLITICOS_SOURCE_CONFIG, domain="politicos"))
DESIRED_SOURCES.update(_coerce_source_config(PARLAMENTARIO_SOURCE_CONFIG, domain="parlamentario"))
DESIRED_SOURCES.update(_coerce_source_config(INFOELECTORAL_SOURCE_CONFIG, domain="infoelectoral"))


TRACKER_TABLE_HEADER = "| Tipo de dato | Dominio | Fuentes objetivo | Estado | Bloque principal |"

# Mapping between tracker table rows and source_id values (docs -> code).
TRACKER_SOURCE_HINTS = {
    "Congreso OpenData Diputados": ["congreso_diputados"],
    "Congreso votaciones": ["congreso_votaciones"],
    "Congreso iniciativas": ["congreso_iniciativas"],
    "Senado votaciones/mociones": ["senado_votaciones"],
    "Senado CSV Senadores": ["senado_senadores"],
    "Senado OpenData XML": ["senado_senadores"],
    "Europarl MEP XML": ["europarl_meps"],
    "RED SARA Concejales": ["municipal_concejales"],
    "Asamblea de Madrid": ["asamblea_madrid_ocupaciones"],
    "Asamblea de Ceuta": ["asamblea_ceuta_diputados"],
    "Asamblea de Melilla": ["asamblea_melilla_diputados"],
    "Cortes de Aragon": ["cortes_aragon_diputados"],
    "Asamblea de Extremadura": ["asamblea_extremadura_diputados"],
    "Asamblea Regional de Murcia": ["asamblea_murcia_diputados"],
    "Junta General del Principado de Asturias": ["jgpa_diputados"],
    "Parlament de Catalunya": ["parlament_catalunya_diputats"],
    "Parlamento de Canarias": ["parlamento_canarias_diputados"],
    "Parlamento de Cantabria": ["parlamento_cantabria_diputados"],
    "Parlament de les Illes Balears": ["parlament_balears_diputats"],
    "Parlamento de La Rioja": ["parlamento_larioja_diputados"],
    "Corts Valencianes": ["corts_valencianes_diputats"],
    "Cortes de Castilla-La Mancha": ["cortes_clm_diputados"],
    "Cortes de Castilla y Leon": ["cortes_cyl_procuradores"],
    "Parlamento de Andalucia": ["parlamento_andalucia_diputados"],
    "Parlamento de Galicia": ["parlamento_galicia_deputados"],
    "Parlamento de Navarra": ["parlamento_navarra_parlamentarios_forales"],
    "Parlamento Vasco": ["parlamento_vasco_parlamentarios"],
    "Infoelectoral": ["infoelectoral_descargas", "infoelectoral_procesos"],
}


def _infer_tracker_source_ids(fuentes_objetivo: str) -> list[str]:
    for hint, source_ids in TRACKER_SOURCE_HINTS.items():
        if hint in fuentes_objetivo:
            return list(source_ids)

    fuentes_lower = (fuentes_objetivo or "").lower()
    matches = []
    for source_id in DESIRED_SOURCES.keys():
        if source_id.lower() in fuentes_lower:
            matches.append(source_id)
    return matches


@lru_cache(maxsize=2)
def _load_tracker_items_cached(tracker_path_str: str, mtime: float) -> list[dict[str, Any]]:
    tracker_path = Path(tracker_path_str)
    if not tracker_path.exists():
        return []

    items: list[dict[str, Any]] = []
    lines = tracker_path.read_text(encoding="utf-8").splitlines()
    in_table = False
    for line in lines:
        if line.strip() == TRACKER_TABLE_HEADER:
            in_table = True
            continue
        if not in_table:
            continue
        if not line.strip().startswith("|"):
            break
        if line.strip().startswith("|---"):
            continue

        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5:
            continue
        tipo_dato, dominio, fuentes, estado, bloque = cells[:5]
        estado_up = (estado or "").strip().upper()
        source_ids = _infer_tracker_source_ids(fuentes)
        items.append(
            {
                "tipo_dato": tipo_dato,
                "dominio": dominio,
                "fuentes_objetivo": fuentes,
                "estado": estado_up,
                "bloque": bloque,
                "source_ids": source_ids,
            }
        )
    return items


def load_tracker_items(tracker_path: Path) -> list[dict[str, Any]]:
    try:
        mtime = tracker_path.stat().st_mtime
    except FileNotFoundError:
        mtime = 0.0
    return _load_tracker_items_cached(str(tracker_path), mtime)


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
        SELECT source_id, name, scope, default_url, is_active, data_format
        FROM sources
        ORDER BY source_id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def build_sources_status_payload(db_path: Path) -> dict[str, Any]:
    meta = {
        "db_path": str(db_path),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    desired_map = DESIRED_SOURCES
    desired_ids = sorted(desired_map.keys())

    def _infer_scope_from_text(text: str) -> str:
        t = (text or "").lower()
        if not t:
            return ""
        if (
            "europarl" in t
            or "parlamento europeo" in t
            or "meps" in t
            or "eur-lex" in t
            or "cellar" in t
            or "transparency register" in t
            or "ted api" in t
            or "data.europa.eu" in t
            or "union europea" in t
            or " ue " in f" {t} "
        ):
            return "europeo"
        if (
            "congreso" in t
            or "senado" in t
            or "jec" in t
            or "junta electoral" in t
            or "boe" in t
            or "placsp" in t
            or "plataforma de contrataci" in t
            or "bdns" in t
            or "infosubvenciones" in t
            or "lamoncloa" in t
            or "moncloa" in t
            or "transparencia.gob" in t
            or "portal de transparencia" in t
        ):
            return "nacional"
        if "ayuntamiento" in t or "municip" in t:
            return "municipal"
        if "parlamento" in t or "asamblea" in t or "cortes" in t or "corts" in t:
            return "autonomico"
        if "ine" in t or "ign" in t or "rel" in t or "poblaci" in t or "territor" in t:
            # Catálogo territorial / población: cruza niveles y no es un conector “político” único.
            return "territorial"
        if "partid" in t and ("program" in t or "web" in t):
            return "nacional"
        return ""

    def _infer_tracker_item_scope(item: dict[str, Any]) -> tuple[str, bool]:
        source_ids = [safe_text(s) for s in (item.get("source_ids") or []) if safe_text(s)]
        scopes = {safe_text((desired_map.get(sid) or {}).get("scope")) for sid in source_ids if safe_text((desired_map.get(sid) or {}).get("scope"))}
        scopes.discard("")
        if len(scopes) == 1:
            return next(iter(scopes)), False
        if len(scopes) > 1:
            return "multi", False

        blob = " | ".join(
            [
                safe_text(item.get("fuentes_objetivo")),
                safe_text(item.get("tipo_dato")),
                safe_text(item.get("dominio")),
                safe_text(item.get("bloque")),
            ]
        )
        inferred = _infer_scope_from_text(blob)
        return inferred, bool(inferred)

    tracker_items_raw = load_tracker_items(TRACKER_PATH)
    tracker_items: list[dict[str, Any]] = []
    for item in tracker_items_raw:
        item2 = dict(item)
        scope, inferred = _infer_tracker_item_scope(item2)
        item2["scope"] = scope
        item2["scope_inferred"] = inferred
        tracker_items.append(item2)

    tracker_by_source: dict[str, dict[str, Any]] = {}
    for item in tracker_items:
        for source_id in item.get("source_ids") or []:
            if source_id:
                tracker_by_source[source_id] = item
    tracker_unmapped = [item for item in tracker_items if not (item.get("source_ids") or [])]

    if not db_path.exists():
        return {
            **meta,
            "error": "Base SQLite no encontrada. Ejecuta primero la ingesta ETL.",
            "summary": {
                "desired": len(desired_ids),
                "present": 0,
                "missing": len(desired_ids),
                "extra": 0,
                "tracker": {
                    "items_total": len(tracker_items),
                    "unmapped": len(tracker_unmapped),
                },
            },
            "tracker": {
                "path": str(TRACKER_PATH),
                "exists": TRACKER_PATH.exists(),
                "items": tracker_items,
                "unmapped": tracker_unmapped,
            },
            "actions": [],
            "sources": [],
            "missing": desired_ids,
        }

    def sql_status_from_metrics(metrics: dict[str, Any] | None) -> str:
        if not metrics:
            return "TODO"
        runs_total = int(metrics.get("runs_total") or 0)
        max_loaded_network = int(metrics.get("max_loaded_network") or 0)
        max_loaded_any = int(metrics.get("max_loaded_any") or 0)
        if runs_total == 0:
            return "TODO"
        if max_loaded_network > 0:
            return "DONE"
        if max_loaded_any > 0:
            return "PARTIAL"
        return "PARTIAL"

    def ops_state(expected: bool, metrics: dict[str, Any] | None, required: int | None) -> str:
        if not expected:
            return "not_in_catalog"
        if not metrics:
            return "missing"
        runs_total = int(metrics.get("runs_total") or 0)
        if runs_total == 0:
            return "not_run"
        last_status = str(metrics.get("last_status", "")).strip().lower()
        if last_status == "running":
            return "running"
        if last_status == "error":
            if int(metrics.get("runs_ok", 0) or 0) > 0:
                return "degraded"
            return "error"
        if last_status == "ok":
            loaded = int(metrics.get("last_loaded", 0) or 0)
            if required and required > 0 and loaded < required:
                return "partial"
            return "ok"
        return "unknown"

    try:
        with open_db(db_path) as conn:
            present_rows = fetch_sources(conn)
            present_map = {str(row["source_id"]): dict(row) for row in present_rows}
            metrics_rows = conn.execute(
                """
                SELECT
                  s.source_id AS source_id,
                  COUNT(DISTINCT ir.run_id) AS runs_total,
                  COUNT(DISTINCT CASE WHEN ir.status = 'ok' THEN ir.run_id END) AS runs_ok,
                  COALESCE(MAX(ir.records_loaded), 0) AS max_loaded_any,
                  COALESCE(
                    MAX(
                      CASE
                        WHEN rf.source_url LIKE 'http%' THEN ir.records_loaded
                        ELSE NULL
                      END
                    ),
                    0
                  ) AS max_loaded_network,
                  SUM(CASE WHEN rf.source_url LIKE 'http%' THEN 1 ELSE 0 END) AS network_fetches,
                  SUM(CASE WHEN rf.source_url LIKE 'file://%' THEN 1 ELSE 0 END) AS fallback_fetches,
                  COALESCE(
                    (
                      SELECT ir2.records_loaded
                      FROM ingestion_runs ir2
                      WHERE ir2.source_id = s.source_id
                      ORDER BY ir2.run_id DESC
                      LIMIT 1
                    ),
                    0
                  ) AS last_loaded,
                  COALESCE(
                    (
                      SELECT ir2.status
                      FROM ingestion_runs ir2
                      WHERE ir2.source_id = s.source_id
                      ORDER BY ir2.run_id DESC
                      LIMIT 1
                    ),
                    ''
                  ) AS last_status,
                  COALESCE(
                    (
                      SELECT ir2.started_at
                      FROM ingestion_runs ir2
                      WHERE ir2.source_id = s.source_id
                      ORDER BY ir2.run_id DESC
                      LIMIT 1
                    ),
                    ''
                  ) AS last_started_at,
                  COALESCE(
                    (
                      SELECT ir2.finished_at
                      FROM ingestion_runs ir2
                      WHERE ir2.source_id = s.source_id
                      ORDER BY ir2.run_id DESC
                      LIMIT 1
                    ),
                    ''
                  ) AS last_finished_at,
                  COALESCE(
                    (
                      SELECT ir2.source_url
                      FROM ingestion_runs ir2
                      WHERE ir2.source_id = s.source_id
                      ORDER BY ir2.run_id DESC
                      LIMIT 1
                    ),
                    ''
                  ) AS last_source_url,
                  COALESCE(
                    (
                      SELECT ir2.message
                      FROM ingestion_runs ir2
                      WHERE ir2.source_id = s.source_id
                      ORDER BY ir2.run_id DESC
                      LIMIT 1
                    ),
                    ''
                  ) AS last_message
                FROM sources s
                LEFT JOIN ingestion_runs ir ON ir.source_id = s.source_id
                LEFT JOIN raw_fetches rf ON rf.run_id = ir.run_id
                GROUP BY s.source_id
                """
            ).fetchall()

            metrics_map = {
                str(row["source_id"]): {
                    "runs_total": int(row["runs_total"] or 0),
                    "runs_ok": int(row["runs_ok"] or 0),
                    "max_loaded_any": int(row["max_loaded_any"] or 0),
                    "max_loaded_network": int(row["max_loaded_network"] or 0),
                    "network_fetches": int(row["network_fetches"] or 0),
                    "fallback_fetches": int(row["fallback_fetches"] or 0),
                    "last_loaded": int(row["last_loaded"] or 0),
                    "last_status": safe_text(row["last_status"]),
                    "last_started_at": safe_text(row["last_started_at"]),
                    "last_finished_at": safe_text(row["last_finished_at"]),
                    "last_source_url": safe_text(row["last_source_url"]),
                    "last_message": safe_text(row["last_message"]),
                }
                for row in metrics_rows
            }

            def _count_by_source(table: str) -> dict[str, int]:
                try:
                    rows = conn.execute(
                        f"SELECT source_id, COUNT(*) AS n FROM {quote_ident(table)} GROUP BY source_id"
                    ).fetchall()
                except sqlite3.Error:
                    return {}
                return {str(row["source_id"]): int(row["n"] or 0) for row in rows}

            mandates_by_source = _count_by_source("mandates")
            vote_events_by_source = _count_by_source("parl_vote_events")
            initiatives_by_source = _count_by_source("parl_initiatives")
            info_tipos_by_source = _count_by_source("infoelectoral_convocatoria_tipos")
            info_procesos_by_source = _count_by_source("infoelectoral_procesos")

            def _count_sql(sql: str, params: tuple[Any, ...] = ()) -> int:
                try:
                    row = conn.execute(sql, params).fetchone()
                    if not row:
                        return 0
                    # first column
                    return int(list(row)[0] or 0)
                except sqlite3.Error:
                    return 0

            def _count_table(table: str) -> int:
                try:
                    row = conn.execute(f"SELECT COUNT(*) AS n FROM {quote_ident(table)}").fetchone()
                    return int((row["n"] if row else 0) or 0)
                except sqlite3.Error:
                    return 0

            topics_total = _count_table("topics")
            topic_sets_total = _count_table("topic_sets")
            topic_sets_active = _count_sql("SELECT COUNT(*) FROM topic_sets WHERE is_active = 1")
            topic_set_topics_total = _count_table("topic_set_topics")
            high_stakes_total = _count_sql("SELECT COUNT(*) FROM topic_set_topics WHERE is_high_stakes = 1")
            topic_evidence_total = _count_table("topic_evidence")
            topic_evidence_with_topic = _count_sql("SELECT COUNT(*) FROM topic_evidence WHERE topic_id IS NOT NULL")
            topic_evidence_with_date = _count_sql(
                "SELECT COUNT(*) FROM topic_evidence WHERE evidence_date IS NOT NULL AND TRIM(evidence_date) <> ''"
            )
            topic_positions_total = _count_table("topic_positions")
            topic_positions_with_evidence = _count_sql("SELECT COUNT(*) FROM topic_positions WHERE evidence_count > 0")

            def _pct(n: int, d: int) -> float:
                if d <= 0:
                    return 0.0
                return float(n) / float(d)

            all_sources: list[dict[str, Any]] = []
            missing = []
            actions: list[dict[str, Any]] = []
            seen_action_keys: set[tuple[str, str]] = set()

            def ingest_cmd(domain: str, source_id: str) -> str:
                dom = safe_text(domain).lower()
                if dom == "politicos":
                    script = "scripts/ingestar_politicos_es.py"
                elif dom == "parlamentario":
                    script = "scripts/ingestar_parlamentario_es.py"
                elif dom == "infoelectoral":
                    script = "scripts/ingestar_infoelectoral_es.py"
                else:
                    script = ""
                if not script:
                    return ""
                return f"python3 {script} ingest --db {db_path} --source {source_id} --strict-network"

            tracker_cmd = f"python3 scripts/e2e_tracker_status.py --db {db_path} --tracker {TRACKER_PATH}"

            def push_action(
                kind: str,
                priority: str,
                title: str,
                details: str = "",
                *,
                scope: str = "",
                source_ids: list[str] | None = None,
                commands: list[str] | None = None,
            ) -> None:
                key = (kind, ",".join(source_ids or []) or title)
                if key in seen_action_keys:
                    return
                seen_action_keys.add(key)
                actions.append(
                    {
                        "kind": kind,
                        "priority": priority,
                        "scope": safe_text(scope),
                        "title": title,
                        "details": details,
                        "source_ids": source_ids or [],
                        "commands": commands or [],
                    }
                )

            for item in tracker_items:
                estado = (item.get("estado") or "").upper()
                if estado not in {"TODO", "PARTIAL"}:
                    continue
                priority = "P0" if estado == "TODO" else "P1"
                push_action(
                    "tracker_item",
                    priority,
                    f"{estado}: {safe_text(item.get('fuentes_objetivo')) or safe_text(item.get('tipo_dato'))}",
                    safe_text(item.get("bloque")),
                    scope=safe_text(item.get("scope")),
                    source_ids=[sid for sid in (item.get("source_ids") or []) if sid],
                )

            for source_id in desired_ids:
                cfg = desired_map[source_id]
                present = present_map.get(source_id)
                metrics = metrics_map.get(source_id)
                required = cfg.get("min_records_loaded_strict")
                loaded = int(metrics.get("last_loaded", 0) if metrics else 0)
                status = ops_state(True, metrics, required)
                sql_status = sql_status_from_metrics(metrics)
                progress = None
                if required and required > 0:
                    progress = min(100, round((loaded * 100) / required))
                tracker = tracker_by_source.get(source_id)
                tracker_status = safe_text(tracker.get("estado")) if tracker else ""
                max_net = int(metrics.get("max_loaded_network", 0) if metrics else 0)
                max_any = int(metrics.get("max_loaded_any", 0) if metrics else 0)
                net_fetches = int(metrics.get("network_fetches", 0) if metrics else 0)
                fallback_fetches = int(metrics.get("fallback_fetches", 0) if metrics else 0)
                under_threshold = bool(required and required > 0 and loaded < required and (metrics or {}).get("last_status") == "ok")
                done_zero_real = bool(tracker_status == "DONE" and max_net == 0 and max_any > 0)
                mandates_count = int(mandates_by_source.get(source_id, 0))
                vote_events_count = int(vote_events_by_source.get(source_id, 0))
                initiatives_count = int(initiatives_by_source.get(source_id, 0))
                info_tipos_count = int(info_tipos_by_source.get(source_id, 0))
                info_procesos_count = int(info_procesos_by_source.get(source_id, 0))

                primary_table = "mandates"
                primary_rows = mandates_count
                domain = safe_text(cfg.get("domain", ""))
                if domain == "parlamentario":
                    if "votaciones" in source_id:
                        primary_table = "parl_vote_events"
                        primary_rows = vote_events_count
                    elif "iniciativas" in source_id:
                        primary_table = "parl_initiatives"
                        primary_rows = initiatives_count
                elif domain == "infoelectoral":
                    if "descargas" in source_id:
                        primary_table = "infoelectoral_convocatoria_tipos"
                        primary_rows = info_tipos_count
                    elif "procesos" in source_id:
                        primary_table = "infoelectoral_procesos"
                        primary_rows = info_procesos_count

                row: dict[str, Any] = {
                    "source_id": source_id,
                    "domain": domain,
                    "source_name": cfg.get("name", source_id),
                    "scope": cfg.get("scope", ""),
                    "desired": True,
                    "in_db": bool(present),
                    "active": bool(int(present["is_active"])) if present else False,
                    "default_url": safe_text(present["default_url"]) if present else cfg.get("default_url", ""),
                    "institution_name": cfg.get("institution_name", ""),
                    "role_title": cfg.get("role_title", ""),
                    "level": cfg.get("level", ""),
                    "format": cfg.get("format", ""),
                    "fallback_file": cfg.get("fallback_file", ""),
                    "tracker": {
                        "status": tracker_status,
                        "tipo_dato": safe_text(tracker.get("tipo_dato")) if tracker else "",
                        "dominio": safe_text(tracker.get("dominio")) if tracker else "",
                        "fuentes_objetivo": safe_text(tracker.get("fuentes_objetivo")) if tracker else "",
                        "bloque": safe_text(tracker.get("bloque")) if tracker else "",
                    },
                    "sql_status": sql_status,
                    "state": status,
                    "runs_total": int(metrics.get("runs_total", 0) if metrics else 0),
                    "runs_ok": int(metrics.get("runs_ok", 0) if metrics else 0),
                    "last_status": safe_text(metrics.get("last_status")) if metrics else "",
                    "last_loaded": loaded,
                    "max_loaded_any": max_any,
                    "max_loaded_network": max_net,
                    "network_fetches": net_fetches,
                    "fallback_fetches": fallback_fetches,
                    "last_started_at": safe_text(metrics.get("last_started_at")) if metrics else "",
                    "last_seen_at": safe_text(metrics.get("last_finished_at")) if metrics else "",
                    "last_source_url": safe_text(metrics.get("last_source_url")) if metrics else "",
                    "last_message": safe_text(metrics.get("last_message")) if metrics else "",
                    "progress": {
                        "loaded": loaded,
                        "target": required or 0,
                        "percent": progress,
                    },
                    "mandates": mandates_count,
                    "warehouse": {
                        "primary_table": primary_table,
                        "primary_rows": primary_rows,
                        "counts": {
                            "mandates": mandates_count,
                            "parl_vote_events": vote_events_count,
                            "parl_initiatives": initiatives_count,
                            "infoelectoral_convocatoria_tipos": info_tipos_count,
                            "infoelectoral_procesos": info_procesos_count,
                        },
                    },
                    "flags": {
                        "under_threshold": under_threshold,
                        "done_zero_real": done_zero_real,
                        "has_network": max_net > 0,
                        "has_any": max_any > 0,
                        "blocked_note": "bloqueado" in safe_text((tracker or {}).get("bloque", "")).lower(),
                    },
                }
                all_sources.append(row)
                if not present:
                    missing.append(source_id)
                    cmds = [c for c in [ingest_cmd(row.get("domain", ""), source_id), tracker_cmd] if c]
                    push_action(
                        "missing_source",
                        "P0",
                        f"Fuente deseada no existe en BD: {source_id}",
                        f"Dominio={row.get('domain','') or 'N/A'} · scope={row.get('scope','') or 'N/A'}",
                        source_ids=[source_id],
                        commands=cmds,
                    )

                if tracker_status == "DONE" and max_net == 0 and max_any > 0:
                    cmds = [c for c in [ingest_cmd(row.get("domain", ""), source_id), tracker_cmd] if c]
                    push_action(
                        "done_zero_real",
                        "P0",
                        f"Tracker DONE pero sin ejecución reproducible (strict-network): {source_id}",
                        "Hay carga en BD pero no hay evidencia de ejecución desde red (raw_fetches http).",
                        source_ids=[source_id],
                        commands=cmds,
                    )

                if status in {"error", "degraded"}:
                    cmds = [c for c in [ingest_cmd(row.get("domain", ""), source_id), tracker_cmd] if c]
                    push_action(
                        "ingest_error",
                        "P0",
                        f"Ingesta en error: {source_id}",
                        safe_text(row.get("last_message")) or "Revisar ingestion_runs.message / raw_fetches.",
                        source_ids=[source_id],
                        commands=cmds,
                    )

                if under_threshold:
                    cmds = [c for c in [ingest_cmd(row.get("domain", ""), source_id), tracker_cmd] if c]
                    push_action(
                        "under_threshold",
                        "P1",
                        f"Por debajo del umbral minimo: {source_id}",
                        f"loaded={loaded} target={required}",
                        source_ids=[source_id],
                        commands=cmds,
                    )

            for source_id, present in present_map.items():
                if source_id in desired_map:
                    continue
                metrics = metrics_map.get(source_id)
                loaded = int(metrics.get("last_loaded", 0) if metrics else 0)
                status = ops_state(False, metrics, None)
                sql_status = sql_status_from_metrics(metrics)
                tracker = tracker_by_source.get(source_id)
                tracker_status = safe_text(tracker.get("estado")) if tracker else ""
                mandates_count = int(mandates_by_source.get(source_id, 0))
                vote_events_count = int(vote_events_by_source.get(source_id, 0))
                initiatives_count = int(initiatives_by_source.get(source_id, 0))
                info_tipos_count = int(info_tipos_by_source.get(source_id, 0))
                info_procesos_count = int(info_procesos_by_source.get(source_id, 0))
                row = {
                    "source_id": source_id,
                    "domain": "",
                    "source_name": safe_text(present["name"]) or source_id,
                    "scope": safe_text(present["scope"]),
                    "desired": False,
                    "in_db": True,
                    "active": bool(int(present["is_active"])),
                    "default_url": safe_text(present["default_url"]),
                    "institution_name": "",
                    "role_title": "",
                    "level": "",
                    "format": safe_text(present.get("data_format", "")),
                    "fallback_file": "",
                    "tracker": {
                        "status": tracker_status,
                        "tipo_dato": safe_text(tracker.get("tipo_dato")) if tracker else "",
                        "dominio": safe_text(tracker.get("dominio")) if tracker else "",
                        "fuentes_objetivo": safe_text(tracker.get("fuentes_objetivo")) if tracker else "",
                        "bloque": safe_text(tracker.get("bloque")) if tracker else "",
                    },
                    "sql_status": sql_status,
                    "state": status,
                    "runs_total": int(metrics.get("runs_total", 0) if metrics else 0),
                    "runs_ok": int(metrics.get("runs_ok", 0) if metrics else 0),
                    "last_status": safe_text(metrics.get("last_status")) if metrics else "",
                    "last_loaded": loaded,
                    "max_loaded_any": int(metrics.get("max_loaded_any", 0) if metrics else 0),
                    "max_loaded_network": int(metrics.get("max_loaded_network", 0) if metrics else 0),
                    "network_fetches": int(metrics.get("network_fetches", 0) if metrics else 0),
                    "fallback_fetches": int(metrics.get("fallback_fetches", 0) if metrics else 0),
                    "last_started_at": safe_text(metrics.get("last_started_at")) if metrics else "",
                    "last_seen_at": safe_text(metrics.get("last_finished_at")) if metrics else "",
                    "last_source_url": safe_text(metrics.get("last_source_url")) if metrics else "",
                    "last_message": safe_text(metrics.get("last_message")) if metrics else "",
                    "progress": {"loaded": loaded, "target": 0, "percent": None},
                    "mandates": mandates_count,
                    "warehouse": {
                        "primary_table": "mandates" if mandates_count else "",
                        "primary_rows": mandates_count,
                        "counts": {
                            "mandates": mandates_count,
                            "parl_vote_events": vote_events_count,
                            "parl_initiatives": initiatives_count,
                            "infoelectoral_convocatoria_tipos": info_tipos_count,
                            "infoelectoral_procesos": info_procesos_count,
                        },
                    },
                    "flags": {
                        "under_threshold": False,
                        "done_zero_real": False,
                        "has_network": int(metrics.get("max_loaded_network", 0) if metrics else 0) > 0,
                        "has_any": int(metrics.get("max_loaded_any", 0) if metrics else 0) > 0,
                        "blocked_note": "bloqueado" in safe_text((tracker or {}).get("bloque", "")).lower(),
                    },
                }
                all_sources.append(row)

            all_sources.sort(
                key=lambda x: (
                    0 if x["desired"] else 1,
                    safe_text(x["scope"]).lower(),
                    safe_text(x.get("domain", "")).lower(),
                    safe_text(x["source_name"]).lower(),
                    x["source_id"],
                )
            )

            states = [item["state"] for item in all_sources]
            sql_states = [safe_text(item.get("sql_status")) for item in all_sources if safe_text(item.get("sql_status"))]
            tracker_states = [safe_text(item.get("tracker", {}).get("status")) for item in all_sources if safe_text(item.get("tracker", {}).get("status"))]
            desired_progress_target = 0
            desired_progress_loaded = 0
            for source_id in desired_ids:
                cfg = desired_map[source_id]
                target = cfg.get("min_records_loaded_strict")
                metrics = metrics_map.get(source_id)
                if not target or target <= 0:
                    continue
                desired_progress_target += target
                desired_progress_loaded += int(metrics.get("last_loaded", 0) if metrics else 0)

            summary = {
                "desired": len(desired_ids),
                "present": len(present_rows),
                "missing": len(missing),
                "extra": len(all_sources) - len(desired_ids),
                "not_run": states.count("not_run"),
                "running": states.count("running"),
                "ok": states.count("ok"),
                "partial": states.count("partial"),
                "error": states.count("error"),
                "degraded": states.count("degraded"),
                "unknown": states.count("unknown"),
                "not_in_catalog": states.count("not_in_catalog"),
                "desired_progress": {
                    "loaded": desired_progress_loaded,
                    "target": desired_progress_target,
                    "percent": round(min(100, (desired_progress_loaded * 100) / desired_progress_target))
                    if desired_progress_target > 0
                    else None,
                },
                "states": sorted(set(states)),
                "sql": {
                    "todo": sql_states.count("TODO"),
                    "partial": sql_states.count("PARTIAL"),
                    "done": sql_states.count("DONE"),
                },
                "tracker": {
                    "items_total": len(tracker_items),
                    "unmapped": len(tracker_unmapped),
                    "todo": tracker_states.count("TODO"),
                    "partial": tracker_states.count("PARTIAL"),
                    "done": tracker_states.count("DONE"),
                },
            }

            def _priority_key(action: dict[str, Any]) -> tuple[int, str, str]:
                prio = safe_text(action.get("priority"))
                prio_rank = 9
                if prio == "P0":
                    prio_rank = 0
                elif prio == "P1":
                    prio_rank = 1
                elif prio == "P2":
                    prio_rank = 2
                return (prio_rank, safe_text(action.get("kind")), safe_text(action.get("title")))

            actions.sort(key=_priority_key)

            return {
                **meta,
                "summary": summary,
                "analytics": {
                    "topics": {
                        "topics_total": topics_total,
                        "topic_sets_total": topic_sets_total,
                        "topic_sets_active": topic_sets_active,
                        "topic_set_topics_total": topic_set_topics_total,
                        "high_stakes_total": high_stakes_total,
                    },
                    "evidence": {
                        "topic_evidence_total": topic_evidence_total,
                        "topic_evidence_with_topic": topic_evidence_with_topic,
                        "topic_evidence_with_topic_pct": _pct(topic_evidence_with_topic, topic_evidence_total),
                        "topic_evidence_with_date": topic_evidence_with_date,
                        "topic_evidence_with_date_pct": _pct(topic_evidence_with_date, topic_evidence_total),
                    },
                    "positions": {
                        "topic_positions_total": topic_positions_total,
                        "topic_positions_with_evidence": topic_positions_with_evidence,
                        "topic_positions_with_evidence_pct": _pct(
                            topic_positions_with_evidence, topic_positions_total
                        ),
                    },
                },
                "tracker": {
                    "path": str(TRACKER_PATH),
                    "exists": TRACKER_PATH.exists(),
                    "items": tracker_items,
                    "unmapped": tracker_unmapped,
                },
                "actions": actions[:120],
                "sources": all_sources,
                "missing": missing,
            }
    except sqlite3.OperationalError as exc:
        return {
            **meta,
            "error": f"SQLite error: {exc}",
            "summary": {
                "desired": len(desired_ids),
                "present": 0,
                "missing": len(desired_ids),
                "extra": 0,
                "tracker": {
                    "items_total": len(tracker_items),
                    "unmapped": len(tracker_unmapped),
                },
            },
            "tracker": {
                "path": str(TRACKER_PATH),
                "exists": TRACKER_PATH.exists(),
                "items": tracker_items,
                "unmapped": tracker_unmapped,
            },
            "actions": [],
            "sources": [],
            "missing": desired_ids,
        }


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
                  tp.name AS person_territory_name,
                  p.territory_code AS person_territory_code,
                  i.institution_id,
                  i.name AS institution_name,
                  i.level AS institution_level,
                  i.territory_code AS institution_territory_code,
                  ti.name AS institution_territory_name,
                  ti.level AS institution_territory_level,
                  pa.party_id,
                  pa.name AS party_name,
                  pa.acronym AS party_acronym
                FROM mandates m
                JOIN persons p ON p.person_id = m.person_id
                JOIN institutions i ON i.institution_id = m.institution_id
                LEFT JOIN territories tp ON tp.code = p.territory_code
                LEFT JOIN territories ti ON ti.code = i.territory_code
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
                        "territory_name": row["person_territory_name"],
                    }
                }
                nodes_by_id[institution_node_id] = {
                    "data": {
                        "id": institution_node_id,
                        "type": "institution",
                        "label": row["institution_name"],
                        "institution_id": row["institution_id"],
                        "level": row["institution_level"],
                        "territory_code": row["institution_territory_code"],
                        "territory_name": row["institution_territory_name"],
                        "territory_level": row["institution_territory_level"],
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


def build_arena_mandates_payload(
    db_path: Path,
    *,
    source_filter: str | None,
    q: str | None,
    all_data: bool,
    limit: int,
    offset: int,
    include_inactive: bool,
    include_total: bool,
) -> dict[str, Any]:
    if not db_path.exists():
        return {"error": "Base SQLite no encontrada."}

    try:
        with open_db(db_path) as conn:
            municipality_population_by_code = load_municipality_population()
            where = []
            params: list[Any] = []

            if source_filter:
                where.append("m.source_id = ?")
                params.append(source_filter)

            if not include_inactive:
                where.append("m.is_active = 1")

            if q:
                q_norm = f"%{q.strip()}%"
                where.append(
                    "("
                    "p.full_name LIKE ? OR p.given_name LIKE ? OR p.family_name LIKE ? "
                    "OR pa.name LIKE ? OR pa.acronym LIKE ? "
                    "OR m.role_title LIKE ? OR i.name LIKE ? OR m.level LIKE ? OR i.level LIKE ?"
                    ")"
                )
                params.extend([q_norm] * 9)

            where_sql = f"WHERE {' AND '.join(where)}" if where else ""
            total = None
            if include_total and not all_data:
                total_row = conn.execute(
                    f"""
                    SELECT COUNT(*) AS n
                    FROM mandates m
                    JOIN persons p ON p.person_id = m.person_id
                    JOIN institutions i ON i.institution_id = m.institution_id
                    LEFT JOIN parties pa ON pa.party_id = m.party_id
                    {where_sql}
                    """,
                    params,
                ).fetchone()
                total = int(total_row["n"] if total_row else 0)

            rows_query = f"""
                SELECT
                  m.mandate_id,
                  m.source_id,
                m.role_title,
                  m.level,
                  m.territory_code AS mandate_territory_code,
                  tm.name AS mandate_territory_name,
                  tm.level AS mandate_territory_level,
                  m.start_date,
                  m.end_date,
                  m.is_active,
                  m.person_id,
                  p.full_name,
                  p.given_name,
                  p.family_name,
                  p.territory_code AS person_territory_code,
                  ti_p.name AS person_territory_name,
                  ti_p.level AS person_territory_level,
                  m.institution_id,
                  i.name AS institution_name,
                  i.level AS institution_level,
                  i.territory_code AS institution_territory_code,
                  ti_i.name AS institution_territory_name,
                  ti_i.level AS institution_territory_level,
                  m.party_id,
                  pa.name AS party_name,
                  pa.acronym AS party_acronym
                FROM mandates m
                JOIN persons p ON p.person_id = m.person_id
                JOIN institutions i ON i.institution_id = m.institution_id
                LEFT JOIN territories tm ON tm.code = m.territory_code
                LEFT JOIN parties pa ON pa.party_id = m.party_id
                LEFT JOIN territories ti_p ON ti_p.code = p.territory_code
                LEFT JOIN territories ti_i ON ti_i.code = i.territory_code
                {where_sql}
                ORDER BY p.full_name, m.is_active DESC, m.start_date DESC, m.mandate_id DESC
                """

            if all_data:
                rows = conn.execute(rows_query, params).fetchall()
                total = len(rows) if total is None else total
            else:
                rows = conn.execute(
                    f"{rows_query} LIMIT ? OFFSET ?",
                    [*params, limit, offset],
                ).fetchall()
                if total is None:
                    total = len(rows)

            hydrated_rows = []
            for row in rows:
                payload_row = dict(row)
                municipality_code, municipality_name, municipality_population = extract_municipality_fields(
                    row,
                    municipality_population_by_code,
                )
                payload_row["municipality_code"] = municipality_code
                payload_row["municipality_name"] = municipality_name
                payload_row["municipality_population"] = municipality_population
                hydrated_rows.append(payload_row)

            return {
                "meta": {
                    "db_path": str(db_path),
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "returned": len(hydrated_rows),
                    "source_filter": source_filter or "",
                    "search": q or "",
                    "include_inactive": include_inactive,
                },
                "rows": hydrated_rows,
            }
    except sqlite3.Error as exc:
        return {"error": f"SQLite error: {exc}"}


def normalize_vote_choice(value: Any) -> str:
    raw = normalize_key_part(safe_text(value))
    if not raw:
        return "other"

    if raw in {"si", "sí", "sí", "afavor", "a favor", "favorable"}:
        return "yes"
    if raw in {"no", "en contra", "voto no"}:
        return "no"
    if raw in {"abstencion", "abstención", "abst."}:
        return "abstain"
    if raw in {"novota", "no vota", "no vota"}:
        return "no_vote"
    return raw if raw else "other"


def _build_vote_breakdown_payload(
    rows: list[sqlite3.Row],
) -> dict[str, int]:
    payload = {"yes": 0, "no": 0, "abstain": 0, "no_vote": 0, "other": 0}

    for row in rows:
        choice = normalize_vote_choice(row["vote_choice"] if isinstance(row, sqlite3.Row) else row.get("vote_choice"))
        count = int(row["count"] if isinstance(row["count"], int) else row["count"] or 0)
        if choice == "yes":
            payload["yes"] += count
        elif choice == "no":
            payload["no"] += count
        elif choice == "abstain":
            payload["abstain"] += count
        elif choice == "no_vote":
            payload["no_vote"] += count
        else:
            payload["other"] += count
    return payload


def build_vote_summary_payload(
    db_path: Path,
    *,
    source_filter: str | None,
    party_filter: str | None,
    q: str | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    if not db_path.exists():
        return {"error": "Base SQLite no encontrada."}

    if limit <= 0:
        limit = 12
    if offset < 0:
        offset = 0

    try:
        with open_db(db_path) as conn:
            source_rows = fetch_sources(conn)
            source_lookup = {row["source_id"]: row for row in source_rows}

            where = []
            params: list[Any] = []
            if source_filter:
                where.append("e.source_id = ?")
                params.append(source_filter)

            if q:
                q_norm = f"%{q.strip()}%"
                where.append(
                    "(e.title LIKE ? OR e.expediente_text LIKE ? OR e.subgroup_title LIKE ? OR e.subgroup_text LIKE ?)"
                )
                params.extend([q_norm] * 4)

            where_sql = f"WHERE {' AND '.join(where)}" if where else ""
            total = conn.execute(
                f"SELECT COUNT(*) AS n FROM parl_vote_events e {where_sql}",
                params,
            ).fetchone()

            events = conn.execute(
                f"""
                SELECT
                  e.vote_event_id,
                  e.source_id,
                  e.vote_date,
                  e.title,
                  e.expediente_text,
                  e.subgroup_title,
                  e.subgroup_text,
                  e.assentimiento,
                  e.totals_present,
                  e.totals_yes,
                  e.totals_no,
                  e.totals_abstain,
                  e.totals_no_vote,
                  e.source_url
                FROM parl_vote_events e
                {where_sql}
                ORDER BY e.vote_date DESC, e.created_at DESC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()

            event_rows = [dict(row) for row in events]
            event_ids = [row["vote_event_id"] for row in event_rows]

            if not event_ids:
                return {
                    "meta": {
                        "db_path": str(db_path),
                        "total": int(total["n"] if total else 0),
                        "limit": limit,
                        "offset": offset,
                        "returned": 0,
                        "source_filter": source_filter or "",
                        "party_filter": party_filter or "",
                        "search": q or "",
                    },
                    "events": [],
                }

            # Attach initiative metadata when we've linked votes -> initiatives.
            # This is the main path to get descriptive titles beyond generic bucket labels.
            event_placeholders = ",".join(["?"] * len(event_ids))
            initiative_rows = conn.execute(
                f"""
                SELECT
                  vi.vote_event_id,
                  vi.initiative_id,
                  COALESCE(vi.confidence, 0) AS confidence,
                  i.expediente AS initiative_expediente,
                  i.title AS initiative_title,
                  i.type AS initiative_type,
                  i.grouping AS initiative_grouping,
                  i.supertype AS initiative_supertype,
                  i.author_text AS initiative_author_text,
                  i.procedure_type AS initiative_procedure_type,
                  i.current_status AS initiative_current_status,
                  i.result_text AS initiative_result_text,
                  i.source_url AS initiative_url
                FROM parl_vote_event_initiatives vi
                JOIN parl_initiatives i ON i.initiative_id = vi.initiative_id
                WHERE vi.vote_event_id IN ({event_placeholders})
                ORDER BY vi.vote_event_id, confidence DESC
                """,
                event_ids,
            ).fetchall()

            best_initiative_by_event: dict[str, dict[str, Any]] = {}
            for row in initiative_rows:
                event_id = safe_text(row["vote_event_id"])
                if not event_id or event_id in best_initiative_by_event:
                    continue
                best_initiative_by_event[event_id] = {
                    "initiative_id": safe_text(row["initiative_id"]),
                    "expediente": safe_text(row["initiative_expediente"]),
                    "title": safe_text(row["initiative_title"]),
                    "type": safe_text(row["initiative_type"]),
                    "grouping": safe_text(row["initiative_grouping"]),
                    "supertype": safe_text(row["initiative_supertype"]),
                    "author_text": safe_text(row["initiative_author_text"]),
                    "procedure_type": safe_text(row["initiative_procedure_type"]),
                    "current_status": safe_text(row["initiative_current_status"]),
                    "result_text": safe_text(row["initiative_result_text"]),
                    "url": safe_text(row["initiative_url"]),
                    "confidence": float(row["confidence"] or 0),
                }

            all_breakdown_rows = conn.execute(
                f"""
                SELECT
                  mv.vote_event_id,
                  COALESCE(mv.group_code, '') AS group_code,
                  mv.vote_choice,
                  COUNT(*) AS count
                FROM parl_vote_member_votes mv
                WHERE mv.vote_event_id IN ({event_placeholders})
                GROUP BY mv.vote_event_id, COALESCE(mv.group_code, ''), mv.vote_choice
                """,
                event_ids,
            ).fetchall()

            breakdown_by_event: dict[str, dict[str, dict[str, Any]]] = {}
            for row in all_breakdown_rows:
                event_id = safe_text(row["vote_event_id"])
                group_code = safe_text(row["group_code"]).strip() or "Sin grupo"
                event_breakdown = breakdown_by_event.setdefault(event_id, {})
                group_bucket = event_breakdown.setdefault(
                    group_code,
                    {"group_code": group_code, "yes": 0, "no": 0, "abstain": 0, "no_vote": 0, "other": 0, "total": 0},
                )
                choice_totals = _build_vote_breakdown_payload([row])
                group_bucket["yes"] += choice_totals["yes"]
                group_bucket["no"] += choice_totals["no"]
                group_bucket["abstain"] += choice_totals["abstain"]
                group_bucket["no_vote"] += choice_totals["no_vote"]
                group_bucket["other"] += choice_totals["other"]
                group_bucket["total"] = group_bucket["yes"] + group_bucket["no"] + group_bucket["abstain"] + group_bucket["no_vote"] + group_bucket["other"]

            top_group_breakdown: dict[str, list[dict[str, Any]]] = {}
            for event_id, groups in breakdown_by_event.items():
                top_group_breakdown[event_id] = sorted(
                    groups.values(),
                    key=lambda item: item["total"],
                    reverse=True,
                )[:5]

            party_event_filter = ""
            party_params: list[Any] = []
            if party_filter:
                if party_filter == "__sin_partido__":
                    party_event_filter = "m.party_id IS NULL"
                elif party_filter == "__otros__":
                    party_event_filter = "0 = 1"
                else:
                    party_event_filter = "m.party_id = ?"
                    party_params.append(party_filter)

            party_breakdown: dict[str, dict[str, int]] = {}
            if party_event_filter:
                party_rows = conn.execute(
                    f"""
                    SELECT
                      x.vote_event_id,
                      x.vote_choice,
                      COUNT(*) AS count
                    FROM (
                      SELECT DISTINCT
                        mv.vote_event_id,
                        mv.person_id,
                        mv.vote_choice
                      FROM parl_vote_member_votes mv
                      WHERE mv.vote_event_id IN ({event_placeholders})
                        AND mv.person_id IS NOT NULL
                    ) x
                    JOIN mandates m ON m.person_id = x.person_id
                    WHERE {party_event_filter}
                    GROUP BY x.vote_event_id, x.vote_choice
                    """,
                    [*event_ids, *party_params],
                ).fetchall()
                party_grouped = {}
                for row in party_rows:
                    event_id = safe_text(row["vote_event_id"])
                    bucket = party_grouped.setdefault(event_id, {"yes": 0, "no": 0, "abstain": 0, "no_vote": 0, "other": 0})
                    norm = normalize_vote_choice(row["vote_choice"])
                    count = int(row["count"] if row["count"] is not None else 0)
                    if norm == "yes":
                        bucket["yes"] += count
                    elif norm == "no":
                        bucket["no"] += count
                    elif norm == "abstain":
                        bucket["abstain"] += count
                    elif norm == "no_vote":
                        bucket["no_vote"] += count
                    else:
                        bucket["other"] += count
                    party_grouped[event_id] = bucket
                party_breakdown = party_grouped

            payload_events = []
            for row in event_rows:
                event_id = safe_text(row["vote_event_id"])
                groups = top_group_breakdown.get(event_id, [])
                party_payload = party_breakdown.get(event_id)
                if party_payload:
                    total_party_votes = (
                        party_payload["yes"] + party_payload["no"] + party_payload["abstain"] + party_payload["no_vote"] + party_payload["other"]
                    )
                else:
                    total_party_votes = 0

                source_info = source_lookup.get(safe_text(row["source_id"]))
                initiative_info = best_initiative_by_event.get(event_id)
                payload_events.append(
                    {
                        "vote_event_id": event_id,
                        "source_id": safe_text(row["source_id"]),
                        "source_name": safe_text(source_info["name"]) if source_info else safe_text(row["source_id"]),
                        "source_url": safe_text(row["source_url"]),
                        "vote_date": safe_text(row["vote_date"]),
                        "title": safe_text(row["title"]),
                        "expediente_text": safe_text(row["expediente_text"]),
                        "subgroup_title": safe_text(row["subgroup_title"]),
                        "subgroup_text": safe_text(row["subgroup_text"]),
                        "assentimiento": safe_text(row["assentimiento"]),
                        "initiative": initiative_info,
                        "totals": {
                            "present": int(row["totals_present"] or 0),
                            "yes": int(row["totals_yes"] or 0),
                            "no": int(row["totals_no"] or 0),
                            "abstain": int(row["totals_abstain"] or 0),
                            "no_vote": int(row["totals_no_vote"] or 0),
                        },
                        "group_breakdown": groups,
                        "party_participation": (
                            {
                                "yes": party_payload["yes"],
                                "no": party_payload["no"],
                                "abstain": party_payload["abstain"],
                                "no_vote": party_payload["no_vote"],
                                "other": party_payload["other"],
                                "total": total_party_votes,
                            }
                            if party_payload is not None
                            else None
                        ),
                    }
                )

            return {
                "meta": {
                    "db_path": str(db_path),
                    "total": int(total["n"] if total else 0),
                    "limit": limit,
                    "offset": offset,
                    "returned": len(payload_events),
                    "source_filter": source_filter or "",
                    "party_filter": party_filter or "",
                    "search": q or "",
                },
                "events": payload_events,
            }
    except sqlite3.Error as exc:
        return {"error": f"SQLite error: {exc}"}


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

            if path == "/favicon.ico":
                self.send_response(HTTPStatus.NO_CONTENT)
                self.end_headers()
                return

            if path in ("/", "/index.html"):
                if not UI_EXPLORERS.exists():
                    self.write_html("<h1>UI no encontrada</h1>", status=HTTPStatus.NOT_FOUND)
                    return
                self.write_html(UI_EXPLORERS.read_text(encoding="utf-8"))
                return

            if path in ("/graph", "/graph.html"):
                if not UI_GRAPH.exists():
                    self.write_html("<h1>Graph UI no encontrada</h1>", status=HTTPStatus.NOT_FOUND)
                    return
                self.write_html(UI_GRAPH.read_text(encoding="utf-8"))
                return

            if path in ("/explorers", "/explorers.html"):
                if not UI_EXPLORERS.exists():
                    self.write_html("<h1>Landing explorers no encontrada</h1>", status=HTTPStatus.NOT_FOUND)
                    return
                self.write_html(UI_EXPLORERS.read_text(encoding="utf-8"))
                return

            if path in ("/explorer", "/explorer.html"):
                if not UI_EXPLORER.exists():
                    self.write_html("<h1>UI explorer no encontrada</h1>", status=HTTPStatus.NOT_FOUND)
                    return
                self.write_html(UI_EXPLORER.read_text(encoding="utf-8"))
                return

            if path in ("/explorer-politico", "/explorer-politico.html"):
                if not UI_EXPLORER_POLITICO.exists():
                    self.write_html("<h1>UI explorer-politico no encontrada</h1>", status=HTTPStatus.NOT_FOUND)
                    return
                self.write_html(UI_EXPLORER_POLITICO.read_text(encoding="utf-8"))
                return

            if path in ("/explorer-votaciones", "/explorer-votaciones.html"):
                if not UI_EXPLORER_VOTACIONES.exists():
                    self.write_html("<h1>UI explorer-votaciones no encontrada</h1>", status=HTTPStatus.NOT_FOUND)
                    return
                self.write_html(UI_EXPLORER_VOTACIONES.read_text(encoding="utf-8"))
                return

            if path in ("/explorer-sources", "/explorer-sources.html"):
                if not UI_EXPLORER_SOURCES.exists():
                    self.write_html("<h1>UI explorer-sources no encontrada</h1>", status=HTTPStatus.NOT_FOUND)
                    return
                self.write_html(UI_EXPLORER_SOURCES.read_text(encoding="utf-8"))
                return

            if path in ("/explorer-temas", "/explorer-temas.html"):
                if not UI_EXPLORER_TEMAS.exists():
                    self.write_html("<h1>UI explorer-temas no encontrada</h1>", status=HTTPStatus.NOT_FOUND)
                    return
                self.write_html(UI_EXPLORER_TEMAS.read_text(encoding="utf-8"))
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

            if path == "/api/arena/mandates":
                qs = parse_qs(parsed.query, keep_blank_values=False)
                source_filter = str_param(qs, "source_id", "") or None
                search = str_param(qs, "q", "") or None
                include_inactive = bool_param(qs, "include_inactive", False)
                all_data = bool_param(qs, "all", False)
                include_total = bool_param(qs, "include_total", True)
                debug = bool_param(qs, "debug", False)
                verbose = bool_param(qs, "verbose", False)
                limit = int_param(qs, "limit", 1200, min_value=10, max_value=5000)
                offset = int_param(qs, "offset", 0, min_value=0, max_value=5_000_000)
                payload = build_arena_mandates_payload(
                    config.db_path,
                    source_filter=source_filter,
                    q=search,
                    limit=limit,
                    offset=offset,
                    include_inactive=include_inactive,
                    all_data=all_data,
                    include_total=include_total,
                )
                if debug or verbose:
                    sample_row = payload.get("rows", [])
                    sample = sample_row[0] if sample_row else {}
                    ua = self.headers.get("User-Agent", "")
                    print(
                        "[arena/mandates]",
                        f"ua={ua}",
                        f"verb={1 if verbose else 0}",
                        f"source={source_filter or 'all'}",
                        f"q={search or ''}",
                        f"all={all_data}",
                        f"include_inactive={include_inactive}",
                        f"include_total={include_total}",
                        f"limit={limit}",
                        f"offset={offset}",
                        f"total={payload.get('meta', {}).get('total')}",
                        f"returned={payload.get('meta', {}).get('returned')}",
                        f"ok={'error' not in payload}",
                        f"sample_party={sample.get('party_name', '')}",
                        f"sample_level={sample.get('level', '')}",
                        f"sample_territory={sample.get('mandate_territory_name') or sample.get('mandate_territory_code', '')}",
                    )
                status = HTTPStatus.BAD_REQUEST if "error" in payload else HTTPStatus.OK
                self.write_json(payload, status=status)
                return

            if path == "/api/votes/summary":
                qs = parse_qs(parsed.query, keep_blank_values=False)
                source_filter = str_param(qs, "source_id", "") or None
                party_filter = str_param(qs, "party_id", "") or None
                search = str_param(qs, "q", "") or None
                limit = int_param(qs, "limit", 8, min_value=1, max_value=50)
                offset = int_param(qs, "offset", 0, min_value=0, max_value=5_000_000)
                payload = build_vote_summary_payload(
                    config.db_path,
                    source_filter=source_filter,
                    party_filter=party_filter,
                    q=search,
                    limit=limit,
                    offset=offset,
                )
                if payload.get("meta"):
                    payload["meta"]["requested"] = {"source_filter": source_filter or "all", "party_filter": party_filter or "", "search": search or ""}
                if "error" in payload:
                    self.write_json(payload, status=HTTPStatus.BAD_REQUEST)
                else:
                    self.write_json(payload, status=HTTPStatus.OK)
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

            if path == "/api/sources/status":
                qs = parse_qs(parsed.query, keep_blank_values=False)
                payload = build_sources_status_payload(config.db_path)
                if qs.get("debug") or qs.get("verbose"):
                    print(
                        "[api/sources/status]",
                        f"desired={payload.get('summary', {}).get('desired', 0)}",
                        f"present={payload.get('summary', {}).get('present', 0)}",
                        f"missing={payload.get('summary', {}).get('missing', 0)}",
                    )
                status = HTTPStatus.BAD_REQUEST if "error" in payload else HTTPStatus.OK
                self.write_json(payload, status=status)
                return

            if path == "/api/sources/ideal":
                try:
                    raw = IDEAL_SOURCES_PATH.read_text(encoding="utf-8")
                    data = json.loads(raw)
                except FileNotFoundError:
                    data = {"version": "", "title": "Ideal Sources Inventory", "sources": []}
                except json.JSONDecodeError as exc:
                    data = {"error": f"Invalid JSON in {IDEAL_SOURCES_PATH}: {exc}", "sources": []}
                self.write_json(
                    {
                        "meta": {
                            "path": str(IDEAL_SOURCES_PATH),
                            "exists": IDEAL_SOURCES_PATH.exists(),
                            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        },
                        **(data if isinstance(data, dict) else {"sources": []}),
                    }
                )
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
