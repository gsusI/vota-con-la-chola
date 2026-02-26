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
LIBERTY_ATLAS_RELEASE_LATEST_FILE = "liberty-restrictions-atlas-release-latest.json"
PLACEHOLDER_VALUES = {"", "your_hf_token_here", "your_hf_username_here"}
DEFAULT_PARQUET_EXCLUDE_TABLES = ("raw_fetches", "run_fetches", "source_records", "lost_and_found")
DEFAULT_SENSITIVE_PARQUET_TABLES = frozenset(DEFAULT_PARQUET_EXCLUDE_TABLES)
LEGAL_REVIEWED_ON = "2026-02-21"
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
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
LOCAL_USER_SEGMENT_RE = re.compile(r"/Users/[^/\s]+")
LOCAL_HOME_SEGMENT_RE = re.compile(r"/home/[^/\s]+")


DEFAULT_LEGAL_OBLIGATIONS = (
    "No desnaturalizar ni tergiversar la información de origen.",
    "Citar la fuente institucional de forma visible.",
    "Indicar fecha de última actualización/extracción cuando conste.",
    "No sugerir patrocinio o respaldo institucional.",
    "Conservar metadatos relevantes de actualización y condiciones de reutilización.",
)

CC_BY_4_OBLIGATIONS = (
    "Atribuir la fuente conforme a CC BY 4.0.",
    "Indicar si hubo cambios, transformaciones o elaboración propia.",
)

CC_BY_3_ES_OBLIGATIONS = (
    "Atribuir la fuente conforme a CC BY 3.0 ES.",
    "Indicar públicamente cambios/adaptaciones cuando existan.",
)

BDE_OBLIGATIONS = (
    "No alterar contenido ni metadatos de origen cuando se redistribuyen como mirror.",
    "Atribuir la fuente (Banco de España) e indicar fecha de actualización.",
    "Si hay elaboración propia, indicarla explícitamente.",
    "No intentar reidentificación de personas ni circular datos personales identificables.",
)

EUROSTAT_OBLIGATIONS = (
    "Reconocer la fuente Eurostat en redistribución/transformación.",
    "Indicar cambios/adaptaciones cuando existan.",
    "Revisar excepciones de material de terceros antes de habilitar reutilización comercial.",
)

DEFAULT_LEGAL_PROFILE = {
    "verification_status": "pending_review",
    "reuse_basis": "Sin verificación documental específica en este snapshot",
    "terms_url": "",
    "obligations": (
        "Verificar aviso legal/licencia del dominio de origen antes de redistribución comercial.",
    ),
    "notes": "Estado pendiente: falta evidencia legal consolidada por fuente.",
    "personal_data_notes": (
        "Si existen datos personales, aplicar minimización, evitar reidentificación y atender solicitudes de derechos."
    ),
}

LEGAL_PROFILE_BY_SOURCE: dict[str, dict[str, Any]] = {
    "congreso_diputados": {
        "verification_status": "verified",
        "reuse_basis": "Aviso legal del Congreso (reutilización autorizada con condiciones)",
        "terms_url": "https://www.congreso.es/es/avisoLegal",
        "obligations": DEFAULT_LEGAL_OBLIGATIONS,
        "notes": "Para mirror, conservar integridad/atribución; para derivados, marcar elaboración propia.",
        "personal_data_notes": "Datos de representantes: publicar solo campos necesarios para transparencia.",
    },
    "congreso_votaciones": {
        "verification_status": "verified",
        "reuse_basis": "Aviso legal del Congreso (reutilización autorizada con condiciones)",
        "terms_url": "https://www.congreso.es/es/avisoLegal",
        "obligations": DEFAULT_LEGAL_OBLIGATIONS,
        "notes": "Para mirror, conservar integridad/atribución; para derivados, marcar elaboración propia.",
        "personal_data_notes": "Datos de representantes: publicar solo campos necesarios para transparencia.",
    },
    "congreso_iniciativas": {
        "verification_status": "verified",
        "reuse_basis": "Aviso legal del Congreso (reutilización autorizada con condiciones)",
        "terms_url": "https://www.congreso.es/es/avisoLegal",
        "obligations": DEFAULT_LEGAL_OBLIGATIONS,
        "notes": "Para mirror, conservar integridad/atribución; para derivados, marcar elaboración propia.",
        "personal_data_notes": "Datos de representantes: publicar solo campos necesarios para transparencia.",
    },
    "congreso_intervenciones": {
        "verification_status": "verified",
        "reuse_basis": "Aviso legal del Congreso (reutilización autorizada con condiciones)",
        "terms_url": "https://www.congreso.es/es/avisoLegal",
        "obligations": DEFAULT_LEGAL_OBLIGATIONS,
        "notes": "Para mirror, conservar integridad/atribución; para derivados, marcar elaboración propia.",
        "personal_data_notes": "Datos de representantes: publicar solo campos necesarios para transparencia.",
    },
    "senado_senadores": {
        "verification_status": "verified",
        "reuse_basis": "CC BY 4.0 (datos abiertos del Senado)",
        "terms_url": "https://www.senado.es/web/relacionesciudadanos/datosabiertos/catalogodatos/index.html",
        "obligations": CC_BY_4_OBLIGATIONS,
        "notes": "Redistribución y transformación permitidas con atribución.",
        "personal_data_notes": "Datos de representantes: publicar solo campos necesarios para transparencia.",
    },
    "senado_votaciones": {
        "verification_status": "verified",
        "reuse_basis": "CC BY 4.0 (datos abiertos del Senado)",
        "terms_url": "https://www.senado.es/web/relacionesciudadanos/datosabiertos/catalogodatos/index.html",
        "obligations": CC_BY_4_OBLIGATIONS,
        "notes": "Redistribución y transformación permitidas con atribución.",
        "personal_data_notes": "Datos de representantes: publicar solo campos necesarios para transparencia.",
    },
    "senado_iniciativas": {
        "verification_status": "verified",
        "reuse_basis": "CC BY 4.0 (datos abiertos del Senado)",
        "terms_url": "https://www.senado.es/web/relacionesciudadanos/datosabiertos/catalogodatos/index.html",
        "obligations": CC_BY_4_OBLIGATIONS,
        "notes": "Redistribución y transformación permitidas con atribución.",
        "personal_data_notes": "Datos de representantes: publicar solo campos necesarios para transparencia.",
    },
    "boe_api_legal": {
        "verification_status": "verified",
        "reuse_basis": "Aviso legal BOE (reutilización autorizada con condiciones y excepciones de terceros)",
        "terms_url": "https://www.boe.es",
        "obligations": (
            "Atribuir la fuente BOE y enlazar al origen cuando sea posible.",
            "Indicar cambios/adaptaciones cuando existan.",
            "Excluir o segregar materiales con restricciones de terceros (p. ej. NC/ND).",
        ),
        "notes": "Aplicar exclusiones de terceros cuando correspondan.",
        "personal_data_notes": "No publicar campos personales innecesarios.",
    },
    "moncloa_referencias": {
        "verification_status": "verified",
        "reuse_basis": "Aviso legal La Moncloa (reproducción/modificación/distribución autorizadas)",
        "terms_url": "https://www.lamoncloa.gob.es/Paginas/avisolegal.aspx",
        "obligations": DEFAULT_LEGAL_OBLIGATIONS,
        "notes": "Atribución explícita a La Moncloa/Ministerio de la Presidencia.",
        "personal_data_notes": "No publicar campos personales innecesarios.",
    },
    "moncloa_rss_referencias": {
        "verification_status": "verified",
        "reuse_basis": "Aviso legal La Moncloa (reproducción/modificación/distribución autorizadas)",
        "terms_url": "https://www.lamoncloa.gob.es/Paginas/avisolegal.aspx",
        "obligations": DEFAULT_LEGAL_OBLIGATIONS,
        "notes": "Atribución explícita a La Moncloa/Ministerio de la Presidencia.",
        "personal_data_notes": "No publicar campos personales innecesarios.",
    },
    "bdns_api_subvenciones": {
        "verification_status": "verified",
        "reuse_basis": "Aviso legal tipo AGE/Hacienda (reutilización abierta con condiciones)",
        "terms_url": "https://datos.gob.es/es/aviso-legal",
        "obligations": DEFAULT_LEGAL_OBLIGATIONS,
        "notes": "Riesgo adicional GDPR cuando haya beneficiarios personas físicas.",
        "personal_data_notes": "Aplicar minimización; considerar segregación/anonimización de beneficiarios personas físicas.",
    },
    "bdns_autonomico": {
        "verification_status": "verified",
        "reuse_basis": "Aviso legal tipo AGE/Hacienda (reutilización abierta con condiciones)",
        "terms_url": "https://datos.gob.es/es/aviso-legal",
        "obligations": DEFAULT_LEGAL_OBLIGATIONS,
        "notes": "Riesgo adicional GDPR cuando haya beneficiarios personas físicas.",
        "personal_data_notes": "Aplicar minimización; considerar segregación/anonimización de beneficiarios personas físicas.",
    },
    "placsp_sindicacion": {
        "verification_status": "verified",
        "reuse_basis": "PLACSP: reproducción autorizada con cita de origen; datasets vinculados a datos abiertos de Hacienda",
        "terms_url": "https://datos.gob.es/es/aviso-legal",
        "obligations": (
            "Citar el origen de la información.",
            "No desnaturalizar el contenido de origen.",
            "Conservar metadatos/condiciones de reutilización cuando existan.",
        ),
        "notes": "Si se mezcla con datasets de Hacienda, aplican además condiciones del aviso legal tipo.",
        "personal_data_notes": "No publicar campos personales innecesarios.",
    },
    "placsp_autonomico": {
        "verification_status": "verified",
        "reuse_basis": "PLACSP: reproducción autorizada con cita de origen; datasets vinculados a datos abiertos de Hacienda",
        "terms_url": "https://datos.gob.es/es/aviso-legal",
        "obligations": (
            "Citar el origen de la información.",
            "No desnaturalizar el contenido de origen.",
            "Conservar metadatos/condiciones de reutilización cuando existan.",
        ),
        "notes": "Si se mezcla con datasets de Hacienda, aplican además condiciones del aviso legal tipo.",
        "personal_data_notes": "No publicar campos personales innecesarios.",
    },
    "municipal_concejales": {
        "verification_status": "verified",
        "reuse_basis": "Portal concejales.redsara: condiciones alineadas con aviso legal tipo AGE",
        "terms_url": "https://concejales.redsara.es",
        "obligations": DEFAULT_LEGAL_OBLIGATIONS,
        "notes": "Datos de cargos electos con finalidad de transparencia.",
        "personal_data_notes": "Minimizar campos no necesarios y evitar exposición de datos de contacto personal.",
    },
    "asamblea_madrid_ocupaciones": {
        "verification_status": "verified",
        "reuse_basis": "CC BY 3.0 ES (Asamblea de Madrid, salvo indicación en contrario)",
        "terms_url": "https://www.asambleamadrid.es/datos-abiertos",
        "obligations": CC_BY_3_ES_OBLIGATIONS,
        "notes": "Atribuir explícitamente a Asamblea de Madrid.",
        "personal_data_notes": "No publicar campos personales innecesarios.",
    },
    "aemet_opendata_series": {
        "verification_status": "verified",
        "reuse_basis": "CC BY 4.0 (distribuciones AEMET en catálogo datos.gob.es)",
        "terms_url": "https://datos.gob.es/es/aviso-legal",
        "obligations": CC_BY_4_OBLIGATIONS,
        "notes": "Confirmado vía catálogo oficial; mantener atribución de fuente.",
        "personal_data_notes": "No aplica normalmente (series agregadas).",
    },
    "bde_series_api": {
        "verification_status": "verified",
        "reuse_basis": "Términos de uso estadísticos Banco de España (reutilización con integridad/atribución)",
        "terms_url": "https://www.bde.es",
        "obligations": BDE_OBLIGATIONS,
        "notes": "Cuando haya tratamiento, indicar elaboración propia con datos extraídos.",
        "personal_data_notes": "Difundir solo resultados agregados cuando exista riesgo de identificación.",
    },
    "eurostat_sdmx": {
        "verification_status": "partially_verified",
        "reuse_basis": "Política de reutilización Eurostat (permitida con reconocimiento de fuente, con excepciones)",
        "terms_url": "https://ec.europa.eu/eurostat/about/policies/copyright/",
        "obligations": EUROSTAT_OBLIGATIONS,
        "notes": "Revisar excepciones de terceros por dataset antes de etiquetar como libre comercial sin reservas.",
        "personal_data_notes": "No aplica normalmente (series agregadas).",
    },
    "infoelectoral_descargas": {
        "verification_status": "partially_verified",
        "reuse_basis": "Indicio fuerte de adopción de aviso legal tipo AGE (datos.gob.es/aviso-legal)",
        "terms_url": "https://datos.gob.es/es/aviso-legal",
        "obligations": DEFAULT_LEGAL_OBLIGATIONS,
        "notes": "No se pudo abrir el aviso legal del portal en este entorno; confirmar en próxima revisión.",
        "personal_data_notes": "No publicar campos personales innecesarios.",
    },
    "infoelectoral_procesos": {
        "verification_status": "partially_verified",
        "reuse_basis": "Indicio fuerte de adopción de aviso legal tipo AGE (datos.gob.es/aviso-legal)",
        "terms_url": "https://datos.gob.es/es/aviso-legal",
        "obligations": DEFAULT_LEGAL_OBLIGATIONS,
        "notes": "No se pudo abrir el aviso legal del portal en este entorno; confirmar en próxima revisión.",
        "personal_data_notes": "No publicar campos personales innecesarios.",
    },
    "europarl_meps": {
        "verification_status": "not_verified",
        "reuse_basis": "No verificado: falta evidencia documental específica del recurso XML de MEPs",
        "terms_url": "https://www.europarl.europa.eu/legal-notice/es/",
        "obligations": (
            "No asumir reutilización comercial hasta verificar licencia específica del recurso.",
            "Conservar evidencia de la revisión legal cuando se confirme.",
        ),
        "notes": "Estado no confirmado en esta revisión.",
        "personal_data_notes": "Aplicar minimización al redistribuir datos personales de representantes.",
    },
}


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
    p.add_argument(
        "--require-quality-report",
        action="store_true",
        help=(
            "Falla si no se encuentra quality report de votaciones-kpis para el snapshot "
            "(guardrail recomendado para publish reproducible)."
        ),
    )
    p.add_argument(
        "--require-liberty-atlas-release-latest",
        action="store_true",
        help=(
            "Falla si no existe `published/liberty-restrictions-atlas-release-latest.json` "
            "o si su `snapshot_date` no coincide con el snapshot a publicar."
        ),
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


def ensure_liberty_atlas_release_latest_for_publish(
    *,
    published_dir: Path,
    snapshot_date: str,
    require_release_latest: bool,
) -> dict[str, Any]:
    if not require_release_latest:
        return {}

    latest_path = published_dir / LIBERTY_ATLAS_RELEASE_LATEST_FILE
    if not latest_path.exists():
        raise ValueError(
            "No se encontró `published/liberty-restrictions-atlas-release-latest.json` "
            f"en {published_dir} para snapshot {snapshot_date}. "
            "Ejecuta `just parl-publish-liberty-atlas-artifacts` antes de publicar a HF."
        )

    payload = _read_json_or_gz(latest_path)
    if not payload:
        raise ValueError(
            f"`{LIBERTY_ATLAS_RELEASE_LATEST_FILE}` no contiene JSON válido."
        )

    release_status = str(payload.get("status") or "").strip().lower()
    if release_status and release_status != "ok":
        raise ValueError(
            f"`{LIBERTY_ATLAS_RELEASE_LATEST_FILE}` tiene status no válido: {release_status!r}."
        )

    release_snapshot_date = str(payload.get("snapshot_date") or "").strip()
    if release_snapshot_date != snapshot_date:
        raise ValueError(
            f"`{LIBERTY_ATLAS_RELEASE_LATEST_FILE}` apunta a snapshot_date={release_snapshot_date!r} "
            f"y no coincide con el snapshot a publicar {snapshot_date!r}."
        )

    return {
        "file_name": latest_path.name,
        "snapshot_date": release_snapshot_date,
        "status": release_status or "ok",
    }


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


def legal_status_label(status: str) -> str:
    mapping = {
        "verified": "verificado",
        "partially_verified": "parcial",
        "pending_review": "pendiente",
        "not_verified": "no verificado",
    }
    return mapping.get(status, status)


def clone_legal_profile(template: dict[str, Any]) -> dict[str, Any]:
    return {
        "verification_status": str(template.get("verification_status") or "pending_review"),
        "reuse_basis": str(template.get("reuse_basis") or ""),
        "terms_url": str(template.get("terms_url") or ""),
        "obligations": [str(item) for item in template.get("obligations", ()) if str(item).strip()],
        "notes": str(template.get("notes") or ""),
        "personal_data_notes": str(template.get("personal_data_notes") or ""),
        "reviewed_on": LEGAL_REVIEWED_ON,
    }


def resolve_source_legal_profile(source_id: str, default_url: str) -> dict[str, Any]:
    template = LEGAL_PROFILE_BY_SOURCE.get(source_id)
    if template is None:
        profile = clone_legal_profile(DEFAULT_LEGAL_PROFILE)
        profile["terms_url"] = default_url or profile["terms_url"]
        profile["notes"] = (
            "Fuente sin ficha legal específica en esta versión. "
            "Revisión manual requerida antes de redistribución comercial."
        )
        return profile
    profile = clone_legal_profile(template)
    if not profile["terms_url"]:
        profile["terms_url"] = default_url
    return profile


def export_source_legal_metadata(
    snapshot_dir: Path,
    snapshot_date: str,
    source_records_counts: dict[str, int],
    sources_catalog: dict[str, dict[str, str]],
) -> tuple[list[Path], list[dict[str, Any]]]:
    out_dir = snapshot_dir / "sources"
    out_dir.mkdir(parents=True, exist_ok=True)
    rel_paths: list[Path] = []
    readme_entries: list[dict[str, Any]] = []

    for source_id in sorted(source_records_counts):
        records = int(source_records_counts[source_id])
        source_meta = sources_catalog.get(source_id, {})
        source_name = str(source_meta.get("name") or source_id)
        scope = str(source_meta.get("scope") or "")
        default_url = sanitize_url_for_public(str(source_meta.get("default_url") or ""))
        legal_profile = resolve_source_legal_profile(source_id, default_url)

        payload = {
            "source_id": source_id,
            "source_name": source_name,
            "scope": scope,
            "default_url": default_url,
            "snapshot_date": snapshot_date,
            "records_in_snapshot": records,
            "licensing": legal_profile,
            "no_institutional_endorsement": True,
        }
        rel = Path("sources") / f"{source_id}.json"
        (snapshot_dir / rel).write_text(
            json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        rel_paths.append(rel)
        readme_entries.append(
            {
                "source_id": source_id,
                "records": records,
                "status": legal_profile["verification_status"],
                "reuse_basis": legal_profile["reuse_basis"],
                "terms_url": legal_profile["terms_url"],
            }
        )

    return rel_paths, readme_entries


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

    redacted = SENSITIVE_KV_RE.sub(repl, redacted)
    redacted = EMAIL_RE.sub("<redacted-email>", redacted)
    redacted = LOCAL_USER_SEGMENT_RE.sub("/Users/<redacted-user>", redacted)
    redacted = LOCAL_HOME_SEGMENT_RE.sub("/home/<redacted-user>", redacted)
    return redacted


def sanitize_url_for_public(raw_url: str) -> str:
    text = raw_url.strip()
    if not text:
        return text
    if text.lower().startswith("file://"):
        return ""
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
    source_legal_entries: list[dict[str, Any]],
    include_sqlite_gz: bool,
    source_repo_url: str,
    quality_summary: dict[str, Any] | None = None,
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
            "Contenido por snapshot (capa raw + capa procesada):",
            f"- `{snapshot_rel_dir.as_posix()}/published/*`: capa raw reproducible (artefactos canónicos JSON/JSON.GZ).",
            f"- `{snapshot_rel_dir.as_posix()}/parquet/<tabla>/part-*.parquet`: tablas navegables en el visor Data Studio.",
            f"- `{snapshot_rel_dir.as_posix()}/sources/<source_id>.json`: procedencia legal por fuente (licencia/aviso, obligaciones, terms_url, estado de verificación).",
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
            "- `ingestion_runs.csv`: historial de corridas de ingesta.",
            "- `source_records_by_source.csv`: conteos por fuente para la fecha del snapshot.",
            "- `explorer_schema.json`: contrato de esquema (tablas/PK/FK) para exploración en navegador.",
            "- `manifest.json` y `checksums.sha256`: trazabilidad e integridad.",
            "",
            "Licencia del repo Hugging Face:",
            "- `license: other` porque el snapshot mezcla múltiples licencias/avisos por fuente.",
            "- La licencia/condiciones aplicables están detalladas por `source_id` en `sources/*.json`.",
        ]
    )
    if quality_summary:
        quality_file_name = str(quality_summary.get("file_name") or "")
        if quality_file_name:
            lines.append(
                f"- `published/{quality_file_name}`: reporte de calidad (votos/iniciativas) usado para los gates del snapshot."
            )
    if source_legal_entries:
        lines.extend(
            [
                "",
                "Resumen legal por fuente (snapshot actual):",
                "| source_id | registros | verificación | base legal/licencia | terms_url |",
                "|---|---:|---|---|---|",
            ]
        )
        for row in sorted(source_legal_entries, key=lambda item: str(item["source_id"])):
            source_id = str(row["source_id"])
            records = int(row["records"])
            status = legal_status_label(str(row["status"]))
            reuse_basis = md_escape_table(str(row["reuse_basis"]))
            terms_url = str(row["terms_url"] or "")
            terms_cell = format_terms_cell(terms_url)
            lines.append(f"| `{source_id}` | {records} | {status} | {reuse_basis} | {terms_cell} |")
    lines.extend(
        [
            "",
            "Cautelas de cumplimiento:",
            "- Este dataset no implica respaldo institucional de las fuentes.",
            "- Cuando una fuente exige integridad/no alteración para mirror, mantener `published/*` como capa raw y declarar transformaciones en derivados.",
            "- Si hay datos personales, aplicar minimización, evitar reidentificación y revisar compatibilidad de finalidad (GDPR).",
            "- Fuentes con estado `parcial`, `pendiente` o `no verificado` requieren revisión legal adicional antes de reutilización comercial sensible.",
            "",
            "Ruta del último snapshot publicado en este commit:",
            f"- `{snapshot_rel_dir.as_posix()}` (snapshot_date={snapshot_date})",
            "",
            "Actualización:",
            "- `just etl-publish-hf-dry-run` para validar empaquetado.",
            "- `just etl-publish-hf` para publicar actualización.",
        ]
    )
    if quality_summary:
        lines.extend(["", "Resumen de calidad del snapshot:"])
        lines.append(f"- Gate de votos: {'PASS' if bool(quality_summary.get('vote_gate_passed')) else 'FAIL'}")
        if "initiative_gate_passed" in quality_summary:
            lines.append(
                f"- Gate de iniciativas: {'PASS' if bool(quality_summary.get('initiative_gate_passed')) else 'FAIL'}"
            )
        if "events_total" in quality_summary:
            lines.append(f"- Eventos analizados: {int(quality_summary.get('events_total') or 0)}")
        if "downloaded_doc_links" in quality_summary:
            lines.append(f"- Initiative doc links descargados: {int(quality_summary.get('downloaded_doc_links') or 0)}")
        if "missing_doc_links_actionable" in quality_summary:
            lines.append(
                "- Initiative doc links pendientes accionables: "
                f"{int(quality_summary.get('missing_doc_links_actionable') or 0)}"
            )
        if "extraction_coverage_pct" in quality_summary:
            lines.append(
                "- Cobertura de extracción en docs descargados: "
                f"{float(quality_summary.get('extraction_coverage_pct') or 0.0) * 100:.1f}%"
            )
        if "extraction_review_closed_pct" in quality_summary:
            lines.append(
                "- Cierre de cola de revisión de extracción: "
                f"{float(quality_summary.get('extraction_review_closed_pct') or 0.0) * 100:.1f}%"
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
    quality_summary = extract_quality_report_summary(published_files, snapshot_date)
    try:
        ensure_quality_report_for_publish(
            quality_summary,
            require_quality_report=bool(args.require_quality_report),
            snapshot_date=snapshot_date,
            published_dir=published_dir,
        )
        liberty_atlas_release_latest_summary = ensure_liberty_atlas_release_latest_for_publish(
            published_dir=published_dir,
            snapshot_date=snapshot_date,
            require_release_latest=bool(args.require_liberty_atlas_release_latest),
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
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
        source_records_rows, source_records_total, source_records_counts = export_source_records_by_source(
            db_path, snapshot_date, source_records_csv
        )
        tracked_files.append(Path("source_records_by_source.csv"))

        sources_catalog = fetch_sources_catalog(db_path)
        source_legal_rel_paths, source_legal_entries = export_source_legal_metadata(
            snapshot_dir=snapshot_dir,
            snapshot_date=snapshot_date,
            source_records_counts=source_records_counts,
            sources_catalog=sources_catalog,
        )
        tracked_files.extend(source_legal_rel_paths)

        explorer_schema_rel = export_explorer_schema_snapshot(db_path, snapshot_dir)
        tracked_files.append(explorer_schema_rel)

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
        legal_status_counts: dict[str, int] = {}
        for row in source_legal_entries:
            status = str(row["status"])
            legal_status_counts[status] = legal_status_counts.get(status, 0) + 1
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
                "source_legal_files_count": len(source_legal_rel_paths),
                "source_legal_status_counts": legal_status_counts,
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
        if quality_summary:
            manifest["quality_report"] = quality_summary
        if liberty_atlas_release_latest_summary:
            manifest["liberty_atlas_release_latest"] = liberty_atlas_release_latest_summary
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
        if quality_summary:
            latest_payload["quality_report"] = quality_summary
        if liberty_atlas_release_latest_summary:
            latest_payload["liberty_atlas_release_latest"] = liberty_atlas_release_latest_summary
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
                source_legal_entries=source_legal_entries,
                include_sqlite_gz=(not args.skip_sqlite_gz),
                source_repo_url=source_repo_url,
                quality_summary=quality_summary,
            ),
            encoding="utf-8",
        )

        print(f"HF dataset repo: {dataset_repo}")
        print(f"Snapshot bundle: {snapshot_rel_dir.as_posix()}")
        print(f"Published files: {len(published_rel_paths)}")
        print(f"Ingestion runs rows: {ingestion_runs_rows}")
        print(f"Source records rows (by source): {source_records_rows}")
        print(f"Source legal files: {len(source_legal_rel_paths)}")
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
