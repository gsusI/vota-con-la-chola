#!/usr/bin/env python3
"""Ingest Spain's education spending, outcomes and long-run schooling series into SQLite (indicator contract v1).

Boundaries:
- ingest: fetch each official source, keep the raw payload under etl/data/raw/education/ (+ URL, retrieval time);
  `--offline` reuses that cache. Sources: Ministerio de Educación EDUCAbase (PC-Axis), Eurostat (JSON-stat), OECD
  Education at a Glance through the DBnomics mirror (oecd.org blocks scripted access with a Cloudflare challenge),
  World Bank EdStats (PISA 2000-2018) and Our World in Data (long-run literacy and years of schooling).
- normalize/load: every series lands in the canonical indicator tables (indicator_definitions -> indicator_releases
  -> indicator_series_versions -> indicator_observation_versions -> indicator_observation_evidence). A new raw
  payload is a new release; each observation is compared with the previous release (unchanged/changed/deleted).
  Evidence points at the raw cell (JSON pointer, PC-Axis DATA index or CSV row/column) + sha256 of the payload.
- curated: PISA values without an open API (2022 scores, repetition) live in
  etl/data/manual/education/pisa_curated_es.json, one document + PDF page + literal quote per value; the official
  PDFs are cached and, when pdftotext is available, every quote is checked against the cached text.

The published site JSON is derived from this DB by scripts/export_public_viz_education.py.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.politicos_es.config import DEFAULT_SCHEMA  # noqa: E402
from etl.politicos_es.db import apply_schema, seed_sources  # noqa: E402
from publicdata_sqlite import open_db  # noqa: E402
from publicdata_sqlite.provenance import seed_sources_from_config  # noqa: E402

DEFAULT_DB = REPO_ROOT / "etl/data/staging/education-es.db"
RAW_DIR = REPO_ROOT / "etl/data/raw/education"
MANUAL_DIR = REPO_ROOT / "etl/data/manual/education"
USER_AGENT = "Mozilla/5.0 (compatible; vota-con-la-chola-etl/1.0; +https://votaconlachola.org)"
EXTRACTOR_VERSION = "ingest_education_es/1"
DOMAIN = "educacion"
NUL = "\x00"

LOCAL_SOURCES: dict[str, dict[str, str]] = {
    "mefp_educabase": {
        "name": "Ministerio de Educación, FP y Deportes - EDUCAbase (series PC-Axis)",
        "scope": DOMAIN,
        "default_url": "https://estadisticas.educacion.gob.es/",
        "format": "px",
    },
    "oecd_eag_finance": {
        "name": "OCDE - Education at a Glance, gasto por estudiante (réplica DBnomics)",
        "scope": DOMAIN,
        "default_url": "https://db.nomics.world/OECD/DSD_EAG_UOE_FIN@DF_UOE_INDIC_FIN_PERSTUD",
        "format": "json",
    },
    "worldbank_edstats": {
        "name": "Banco Mundial - Education Statistics (EdStats, API v2, fuente 12)",
        "scope": DOMAIN,
        "default_url": "https://api.worldbank.org/v2/sources/12",
        "format": "json",
    },
    "ine_epf": {
        "name": "INE - Encuesta de Presupuestos Familiares (API Tempus)",
        "scope": DOMAIN,
        "default_url": "https://servicios.ine.es/wstempus/js/ES/TABLAS_OPERACION/EPF",
        "format": "json",
    },
    "owid_grapher": {
        "name": "Our World in Data - series históricas de educación (CSV del grapher)",
        "scope": DOMAIN,
        "default_url": "https://ourworldindata.org/",
        "format": "csv",
    },
    "vclc_education_curated": {
        "name": "PISA: valores citados de informes oficiales (curado, documento + página + cita)",
        "scope": DOMAIN,
        "default_url": "https://www.educacionfpydeportes.gob.es/inee/evaluaciones-internacionales/pisa.html",
        "format": "json",
    },
}

PEERS = ["ES", "EU27_2020", "DE", "FR", "IT", "PT"]
OECD_PEERS = ["ESP", "OECD", "EU25", "DEU", "FRA", "ITA", "PRT"]
AREA_META = {
    "ESP": ("España", "ISO3166-1-alpha-3", "country"),
    "DEU": ("Alemania", "ISO3166-1-alpha-3", "country"),
    "FRA": ("Francia", "ISO3166-1-alpha-3", "country"),
    "ITA": ("Italia", "ISO3166-1-alpha-3", "country"),
    "PRT": ("Portugal", "ISO3166-1-alpha-3", "country"),
    "OECD": ("Media OCDE", "OECD-aggregate", "aggregate"),
    "OED": ("Media OCDE (Banco Mundial)", "WB-aggregate", "aggregate"),
    "EU25": ("Media UE (países UE de la OCDE)", "OECD-aggregate", "aggregate"),
    "EU": ("Total UE (PISA)", "OECD-aggregate", "aggregate"),
    "ES": ("España", "NUTS", "country"),
    "DE": ("Alemania", "NUTS", "country"),
    "FR": ("Francia", "NUTS", "country"),
    "IT": ("Italia", "NUTS", "country"),
    "PT": ("Portugal", "NUTS", "country"),
    "EU27_2020": ("Unión Europea (27, desde 2020)", "EU-aggregate", "aggregate"),
}


# ---------------------------------------------------------------- helpers

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def stable_id(kind: str, *parts: object) -> str:
    payload = NUL.join([kind, *(str(p if p is not None else "") for p in parts)])
    return f"vclc:{kind}:{sha256_bytes(payload.encode('utf-8'))[:24]}"


def decimal_text(value: Any) -> str | None:
    if value is None or value == "NA" or isinstance(value, bool):
        return None
    try:
        return format(Decimal(str(value)).normalize(), "f")
    except Exception:  # noqa: BLE001 - non-numeric cell
        return None


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def pointer(*parts: object) -> str:
    return "/" + "/".join(str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def annual(period: str) -> tuple[str, str]:
    return f"{period}-01-01", f"{period}-12-31"


def school_year(label: str) -> dict[str, str]:
    """'2023-24' -> period 2023-24, 1 Sep 2023 to 31 Aug 2024."""
    start = int(label[:4])
    return {"start": f"{start}-09-01", "end": f"{start + 1}-08-31", "interval_kind": "school_year"}


def area_series(key: str, geo: str, dimensions: dict[str, Any], observations: list[dict[str, Any]],
                name: str | None = None, system: str | None = None, level: str | None = None) -> dict[str, Any]:
    meta = AREA_META.get(geo, (geo, "unknown", "unknown"))
    return {
        "key": key, "geo_code": geo, "geo_name": name or meta[0], "geo_system": system or meta[1],
        "geo_level": level or meta[2], "dimensions": dimensions, "observations": observations,
    }


# ---------------------------------------------------------------- raw fetch

class Raw:
    def __init__(self, name: str, url: str, payload: bytes, retrieved_at: str):
        self.name, self.url, self.payload, self.retrieved_at = name, url, payload, retrieved_at
        self.sha256 = sha256_bytes(payload)
        self.path = RAW_DIR / name

    def json(self) -> Any:
        return json.loads(self.payload)


def validate(name: str, payload: bytes) -> None:
    """Never cache an HTML error page over a good payload."""
    if name.endswith(".json"):
        json.loads(payload)
    elif name.endswith(".px"):
        if b"DATA=" not in payload:
            raise ValueError(f"{name}: not a PC-Axis file")
    elif name.endswith(".csv"):
        if payload.lstrip()[:1] == b"<":
            raise ValueError(f"{name}: HTML instead of CSV")
    elif name.endswith(".pdf") and not payload.startswith(b"%PDF"):
        raise ValueError(f"{name}: not a PDF")


def fetch_raw(name: str, url: str, offline: bool, reuse: bool = False) -> Raw:
    path = RAW_DIR / name
    meta_path = RAW_DIR / f"{name}.meta.json"
    if not offline and not (reuse and path.exists()):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = resp.read()
        validate(name, payload)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        meta_path.write_text(canonical_json({"url": url, "retrieved_at": now_iso()}), encoding="utf-8")
    if not path.exists():
        raise FileNotFoundError(f"missing raw cache {rel(path)}; run without --offline")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return Raw(name, meta["url"], path.read_bytes(), meta["retrieved_at"])


# ---------------------------------------------------------------- indicator contract loader

def load_indicator(
    conn: sqlite3.Connection,
    definition: dict[str, Any],
    raw_sha256: str,
    raw_bytes: int,
    raw_path: str,
    source_url: str,
    snapshot_date: str,
    source_metadata: dict[str, Any],
    series: list[dict[str, Any]],
) -> dict[str, int]:
    """Insert one release of one indicator, comparing every observation with the previous release."""
    ts = now_iso()
    indicator_id = stable_id(
        "indicator", definition["source_id"], definition["dataset_code"], definition["indicator_code"],
        definition["frequency_code"], definition["unit_code"],
    )
    conn.execute(
        """
        INSERT INTO indicator_definitions (
          indicator_id, source_id, dataset_code, indicator_code, label, definition, domain_key,
          frequency_code, frequency_label, unit_code, unit_label, methodology_version, methodology_url,
          revision_policy, license_url, source_url, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(indicator_id) DO UPDATE SET
          label=excluded.label, definition=excluded.definition, unit_label=excluded.unit_label,
          methodology_url=excluded.methodology_url, source_url=excluded.source_url, updated_at=excluded.updated_at
        """,
        (
            indicator_id, definition["source_id"], definition["dataset_code"], definition["indicator_code"],
            definition["label"], definition.get("definition"), definition.get("domain_key", DOMAIN),
            definition["frequency_code"], definition.get("frequency_label"), definition["unit_code"],
            definition.get("unit_label"), definition.get("methodology_version"), definition.get("methodology_url"),
            "append_new_release_and_compare_every_observation", definition.get("license_url"),
            definition["source_url"], ts, ts,
        ),
    )
    release_id = stable_id("indicator-release", indicator_id, raw_sha256)
    if conn.execute("SELECT 1 FROM indicator_releases WHERE indicator_release_id = ?", (release_id,)).fetchone():
        return {"releases": 0, "observations": 0}
    previous = conn.execute(
        """
        SELECT indicator_release_id FROM indicator_releases WHERE indicator_id = ?
        ORDER BY source_snapshot_date DESC, created_at DESC LIMIT 1
        """,
        (indicator_id,),
    ).fetchone()
    previous_release_id = previous[0] if previous else None
    prev_obs: dict[tuple[str, str], tuple[str, str | None, str | None, int]] = {}
    if previous_release_id:
        for key, period, obs_id, value, text, ordinal, state in conn.execute(
            """
            SELECT s.stable_series_key, o.period_label, o.indicator_observation_version_id, o.value_decimal,
                   o.value_text, o.revision_ordinal, o.revision_state
            FROM indicator_observation_versions o
            JOIN indicator_series_versions s USING (indicator_series_version_id)
            WHERE o.indicator_release_id = ?
            """,
            (previous_release_id,),
        ):
            if state != "deleted":
                prev_obs[(key, period)] = (obs_id, value, text, ordinal)
    conn.execute(
        """
        INSERT INTO indicator_releases (
          indicator_release_id, indicator_id, source_snapshot_date, source_updated_at, source_url,
          source_content_sha256, source_bytes, raw_path, source_metadata_json, comparison_state,
          previous_indicator_release_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            release_id, indicator_id, snapshot_date, source_metadata.get("source_updated_at"), source_url,
            raw_sha256, raw_bytes, raw_path, canonical_json(source_metadata),
            "compared" if previous_release_id else "baseline", previous_release_id, ts, ts,
        ),
    )
    obs_rows, ev_rows, seen = [], [], set()
    for item in series:
        series_id = stable_id("indicator-series-version", release_id, item["key"])
        conn.execute(
            """
            INSERT INTO indicator_series_versions (
              indicator_series_version_id, indicator_id, indicator_release_id, stable_series_key,
              geography_code, geography_name, geography_system, geography_level, geography_version,
              territory_id, dimensions_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?)
            """,
            (
                series_id, indicator_id, release_id, item["key"], item["geo_code"], item["geo_name"],
                item["geo_system"], item["geo_level"], canonical_json(item.get("dimensions", {})), ts, ts,
            ),
        )
        for obs in item["observations"]:
            value = decimal_text(obs["value"])
            text = None if value is not None else (None if obs["value"] is None else str(obs["value"]))
            if value is None and text is None:
                continue
            period = str(obs["period"])
            seen.add((item["key"], period))
            prior = prev_obs.get((item["key"], period))
            if prior is None:
                state, ordinal, prev_id = "baseline", 1, None
            else:
                same = prior[1] == value and prior[2] == text
                state, ordinal, prev_id = ("unchanged" if same else "changed"), prior[3] + (0 if same else 1), prior[0]
            obs_id = stable_id("indicator-observation-version", series_id, period, value, text)
            default_start, default_end = annual(period) if period.isdigit() else (period, period)
            obs_rows.append((
                obs_id, series_id, release_id, period, obs.get("start", default_start),
                obs.get("end", default_end), obs.get("interval_kind", "calendar_year"), value, text,
                obs.get("status"), canonical_json(obs.get("status_labels", [])), "not_provided", ordinal, state,
                prev_id, source_metadata.get("source_updated_at"), int(obs.get("cell_index", 0)),
                canonical_json(obs.get("raw", obs["value"])), ts, ts,
            ))
            ev_rows.append((
                stable_id("indicator-observation-evidence", obs_id, raw_sha256, obs["pointer"]), obs_id,
                obs.get("evidence_url") or source_url, raw_sha256, raw_path, obs["pointer"],
                obs.get("status_pointer"), definition.get("extraction_method", "json_pointer"), EXTRACTOR_VERSION, ts,
            ))
    # Observations present in the previous release and gone from this one are recorded as deleted.
    for (key, period), (prev_id, _value, _text, ordinal) in prev_obs.items():
        if (key, period) in seen:
            continue
        series_id = stable_id("indicator-series-version", release_id, key)
        if not conn.execute(
            "SELECT 1 FROM indicator_series_versions WHERE indicator_series_version_id = ?", (series_id,)
        ).fetchone():
            continue
        obs_id = stable_id("indicator-observation-version", series_id, period, "deleted")
        start, end = annual(period) if period.isdigit() else (period, period)
        obs_rows.append((
            obs_id, series_id, release_id, period, start, end, "calendar_year", None, None, None, "[]",
            "not_applicable", ordinal + 1, "deleted", prev_id, None, 0, "null", ts, ts,
        ))
    conn.executemany(
        """
        INSERT INTO indicator_observation_versions (
          indicator_observation_version_id, indicator_series_version_id, indicator_release_id, period_label,
          period_start, period_end, interval_kind, value_decimal, value_text, source_status_code,
          source_status_labels_json, uncertainty_state, revision_ordinal, revision_state,
          previous_observation_version_id, source_published_at, raw_cell_index, raw_value_json,
          created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        obs_rows,
    )
    conn.executemany(
        """
        INSERT INTO indicator_observation_evidence (
          indicator_observation_evidence_id, indicator_observation_version_id, source_url,
          source_content_sha256, raw_path, value_json_pointer, status_json_pointer, extraction_method,
          extractor_version, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ev_rows,
    )
    return {"releases": 1, "observations": len(obs_rows)}


Batch = tuple[dict[str, Any], list[dict[str, Any]]]


# ---------------------------------------------------------------- Ministerio de Educación (PC-Axis)

EDUCABASE = "https://estadisticas.educacion.gob.es/EducaJaxiPx/files/_px/es/px"
EDUCABASE_TABLE = "https://estadisticas.educacion.gob.es/EducaJaxiPx/Tabla.htm?path={path}/l0/&file={file}&L=0"


def parse_px(payload: bytes) -> dict[str, Any]:
    """Minimal PC-Axis reader: keywords, VALUES per variable, STUB/HEADING order and the flat DATA array."""
    text = payload.decode("iso-8859-15")
    head, _, data = text.partition("DATA=")
    keys: dict[str, Any] = {}
    for match in re.finditer(r'(?ms)^([A-Z-]+)(\("([^"]*)"\))?=(.*?);\s*$', head):
        key, var, raw_value = match.group(1), match.group(3), match.group(4)
        values = re.findall(r'"((?:[^"]|"")*)"', raw_value.replace('"\r\n"', "").replace('"\n"', ""))
        if var is not None:
            keys.setdefault(key, {})[var] = [v.strip() for v in re.findall(r'"([^"]*)"', raw_value)]
        else:
            keys[key] = [v for v in values] if values else raw_value.strip()
    cells = [c for c in re.split(r"[\s;]+", data.strip()) if c]
    variables = keys["STUB"] + keys["HEADING"]
    return {
        "title": " ".join(keys.get("TITLE", [])) if isinstance(keys.get("TITLE"), list) else keys.get("TITLE"),
        "units": " ".join(keys.get("UNITS", [])) if isinstance(keys.get("UNITS"), list) else keys.get("UNITS"),
        "notes": keys.get("NOTE"),
        "variables": variables,
        "values": {var: keys["VALUES"][var] for var in variables},
        "data": cells,
    }


def px_cells(px: dict[str, Any]) -> Iterable[tuple[int, dict[str, str], str]]:
    """Yield (flat index, {variable: value}, raw cell) in PC-Axis order (last variable varies fastest)."""
    variables = px["variables"]
    sizes = [len(px["values"][v]) for v in variables]
    for index, cell in enumerate(px["data"]):
        rest, coords = index, {}
        for var, size in zip(reversed(variables), reversed(sizes)):
            coords[var] = px["values"][var][rest % size]
            rest //= size
        yield index, coords, cell


def px_number(cell: str) -> float | None:
    cell = cell.strip('"')
    if cell in {"", ".", "..", "...", "-", ":"}:
        return None
    try:
        return float(cell)
    except ValueError:
        return None


CCAA_TOTAL = {"TOTAL", "TODOS LOS CENTROS"}


def px_geo(region: str | None) -> tuple[str, str, str, str]:
    if region is None or region == "TOTAL":
        return "ES", "España", "NUTS", "country"
    return f"ES-CCAA:{region}", region, "es-ccaa-name", "region"


def parse_mefp(table: str, path: str, file: str, indicator_code: str, label: str, unit_code: str,
               definition_text: str, keep: Callable[[dict[str, str]], bool], period_var: str,
               region_var: str | None, school: bool) -> Callable[[Raw], Iterable[Batch]]:
    def parse(raw: Raw) -> Iterable[Batch]:
        px = parse_px(raw.payload)
        grouped: dict[str, dict[str, Any]] = {}
        for index, coords, cell in px_cells(px):
            if not keep(coords):
                continue
            value = px_number(cell)
            if value is None:
                continue
            period_label = coords[period_var].split(" ")[0]
            dims = {k: v for k, v in coords.items() if k != period_var}
            region = coords.get(region_var) if region_var else None
            geo, name, system, level = px_geo(region)
            key = f"{table}|" + "|".join(f"{k}={v}" for k, v in sorted(dims.items()))
            item = grouped.setdefault(key, area_series(key, geo, dims, [], name, system, level))
            obs = {"period": period_label, "value": value, "pointer": pointer("DATA", index), "cell_index": index,
                   "raw": cell, "status": "provisional" if "(*)" in coords[period_var] else None}
            if school:
                obs.update(school_year(period_label))
            item["observations"].append(obs)
        yield {
            "source_id": "mefp_educabase", "dataset_code": table, "indicator_code": indicator_code,
            "frequency_code": "A" if not school else "SY", "frequency_label": "Anual" if not school else "Curso escolar",
            "unit_code": unit_code, "unit_label": px["units"], "label": label,
            "definition": f"{definition_text} Tabla: {px['title']}", "extraction_method": "pcaxis_data_index",
            "methodology_url": EDUCABASE_TABLE.format(path=path, file=file),
            "source_url": EDUCABASE_TABLE.format(path=path, file=file),
        }, list(grouped.values())
    return parse


def mefp_source(table: str, path: str, file: str, **kwargs: Any) -> tuple[str, str, Callable[[Raw], Iterable[Batch]]]:
    return (f"mefp_{table}.px", f"{EDUCABASE}{path}/l0/{file}?nocab=1", parse_mefp(table, path, file, **kwargs))


def mefp_multi_source(table: str, path: str, file: str, *variants: dict[str, Any]) -> tuple[str, str, Callable[[Raw], Iterable[Batch]]]:
    """Several indicators from one PC-Axis file (one download, one raw cache entry)."""
    parsers = [parse_mefp(table, path, file, **kwargs) for kwargs in variants]
    return (f"mefp_{table}.px", f"{EDUCABASE}{path}/l0/{file}?nocab=1", lambda raw: (b for parse in parsers for b in parse(raw)))


GASTO = "/economicas/gasto/series"
MEFP_SOURCES = [
    mefp_source(
        "gasto_series_01", GASTO, "series_01.px", indicator_code="gasto_publico_educacion_total",
        label="Gasto público en educación, total (miles de euros corrientes)", unit_code="KEUR",
        definition_text="Gasto de todas las administraciones públicas en educación, incluidos capítulos financieros. "
        "Estadística del Gasto Público en Educación (Ministerio).",
        keep=lambda c: c["Cobertura económica"].startswith("Inclu"), period_var="periodo",
        region_var=None, school=False,
    ),
    mefp_source(
        "gasto_series_02", GASTO, "series_02.px", indicator_code="gasto_publico_instituciones_no_universitarias",
        label="Gasto público en instituciones de educación no universitaria (miles de euros corrientes)",
        unit_code="KEUR",
        definition_text="Gasto público en centros de enseñanza no universitaria (no incluye becas), incluidos "
        "capítulos financieros.",
        keep=lambda c: c["Cobertura económica"].startswith("Inclu"), period_var="periodo",
        region_var=None, school=False,
    ),
    mefp_source(
        "gasto_series_08", GASTO, "series_08.px", indicator_code="gasto_publico_educacion_pct_pib",
        label="Gasto público en educación en relación al PIB (%)", unit_code="PC_GDP",
        definition_text="Gasto público total en educación dividido por el PIB (Ministerio).",
        keep=lambda c: all(v == "TOTAL" or "Inclu" in v or k == "periodo" for k, v in c.items()),
        period_var="periodo", region_var=None, school=False,
    ),
    mefp_source(
        "alumnado_1_01", "/no-universitaria/alumnado/matriculado/series/AlumnadoGen", "alumnado_1_01.px",
        indicator_code="alumnado_regimen_general", label="Alumnado de Enseñanzas de Régimen General (todos los centros)",
        unit_code="PERSONS",
        definition_text="Alumnos matriculados en enseñanzas de régimen general (Infantil, Primaria, ESO, Bachillerato, "
        "FP, Educación Especial), centros públicos y privados.",
        keep=lambda c: c["Titularidad del centro"] == "TODOS LOS CENTROS" and c["Comunidad autónoma"] == "TOTAL",
        period_var="periodo", region_var="Comunidad autónoma", school=True,
    ),
    mefp_source(
        "alumnado_1_01", "/no-universitaria/alumnado/matriculado/series/AlumnadoGen", "alumnado_1_01.px",
        indicator_code="alumnado_regimen_general_por_ccaa",
        label="Alumnado de Enseñanzas de Régimen General por comunidad autónoma (todos los centros)", unit_code="PERSONS",
        definition_text="Alumnos matriculados en enseñanzas de régimen general, centros públicos y privados, por comunidad.",
        keep=lambda c: c["Titularidad del centro"] == "TODOS LOS CENTROS",
        period_var="periodo", region_var="Comunidad autónoma", school=True,
    ),
    mefp_multi_source(
        "aban_1_08", "/laborales/epa/aban", "aban_1_08.px",
        dict(
            indicator_code="abandono_por_formacion_madre",
            label="Abandono temprano de la educación-formación por nivel de formación de la madre (%)", unit_code="PC",
            definition_text="Población de 18 a 24 años que abandona prematuramente los estudios, según el nivel de formación de la "
            "madre (explotación de la EPA del Ministerio).",
            keep=lambda c: c["Tipo de indicador"].startswith("Tasa de abandono") and c["Sexo"] == "AMBOS SEXOS",
            period_var="periodo", region_var=None, school=False,
        ),
        dict(
            indicator_code="abandono_peso_formacion_madre",
            label="Jóvenes con abandono temprano según el nivel de formación de la madre (distribución, %)", unit_code="PC_LEAVERS",
            definition_text="Distribución porcentual de los jóvenes de 18 a 24 años con abandono temprano según el nivel de "
            "formación de la madre (columna «Peso del nivel de la madre»; suma 100 sobre el total de jóvenes que abandonan).",
            keep=lambda c: c["Tipo de indicador"].startswith("Peso del nivel") and c["Sexo"] == "AMBOS SEXOS",
            period_var="periodo", region_var=None, school=False,
        ),
    ),
    mefp_source(
        "idoneidad_05", "/no-universitaria/alumnado/matriculado/series/gen-idoneidad", "idoneidad_05.px",
        indicator_code="tasa_idoneidad_15", label="Tasa de idoneidad a los 15 años (% en el curso teórico, 4.º ESO)",
        unit_code="PC",
        definition_text="Porcentaje del alumnado de 15 años matriculado en el curso que corresponde a su edad; el resto "
        "va retrasado, casi siempre por haber repetido.",
        keep=lambda c: c["Sexo"] == "AMBOS SEXOS", period_var="periodo", region_var="Comunidad autónoma", school=True,
    ),
]


# ---------------------------------------------------------------- Eurostat (JSON-stat)

EUROSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"


def eurostat_url(dataset: str, params: dict[str, Any]) -> str:
    return EUROSTAT + dataset + "?" + urllib.parse.urlencode(params, doseq=True)


def parse_eurostat(dataset: str, indicator_code: str, unit_code: str, unit_label: str, label: str, definition_text: str,
                   geo_filter: Callable[[str], bool] = lambda g: True) -> Callable[[Raw], Iterable[Batch]]:
    def parse(raw: Raw) -> Iterable[Batch]:
        data = raw.json()
        dims = data["id"]
        sizes = data["size"]
        index = {d: data["dimension"][d]["category"]["index"] for d in dims}
        labels = {d: data["dimension"][d]["category"].get("label", {}) for d in dims}
        inverse = {d: {i: code for code, i in index[d].items()} for d in dims}
        grouped: dict[str, dict[str, Any]] = {}
        for flat_text, value in data["value"].items():
            flat, rest, coords = int(flat_text), int(flat_text), {}
            for d, size in zip(reversed(dims), reversed(sizes)):
                coords[d] = inverse[d][rest % size]
                rest //= size
            geo = coords["geo"]
            if not geo_filter(geo):
                continue
            series_dims = {d: coords[d] for d in dims if d != "time"}
            key = f"{dataset}|" + "|".join(series_dims[d] for d in dims if d != "time")
            meta = AREA_META.get(geo)
            item = grouped.setdefault(key, area_series(
                key, geo, series_dims, [], name=None if meta else labels["geo"].get(geo, geo),
                system=None if meta else "NUTS", level=None if meta else "region",
            ))
            status = data.get("status", {}).get(flat_text)
            item["observations"].append({
                "period": coords["time"], "value": value, "pointer": pointer("value", flat_text), "cell_index": flat,
                "status": status, "status_pointer": pointer("status", flat_text) if status else None,
                "status_labels": [{"code": status, "label": data.get("extension", {}).get("status", {}).get("label", {}).get(status, status)}] if status else [],
            })
        for item in grouped.values():
            item["observations"].sort(key=lambda o: o["period"])
        yield {
            "source_id": "eurostat_sdmx", "dataset_code": dataset, "indicator_code": indicator_code,
            "frequency_code": "A", "frequency_label": "Anual", "unit_code": unit_code, "unit_label": unit_label,
            "label": label, "definition": definition_text,
            "methodology_url": f"https://ec.europa.eu/eurostat/cache/metadata/en/{dataset.split('_')[0]}_esms.htm",
            "source_url": f"https://ec.europa.eu/eurostat/databrowser/view/{dataset}/default/table",
            "source_updated_at": data.get("updated"),
        }, sorted(grouped.values(), key=lambda s: s["key"])
    return parse


EUROSTAT_SOURCES = [
    (
        "eurostat_edat_lfse_14.json",
        eurostat_url("edat_lfse_14", {"sex": "T", "wstatus": "POP", "age": "Y18-24", "unit": "PC", "geo": PEERS}),
        parse_eurostat(
            "edat_lfse_14", "early_leavers_18_24.T.POP", "PC", "% de la población de 18 a 24 años",
            "Abandono temprano de la educación y la formación (18-24 años)",
            "Personas de 18 a 24 años con como mucho la primera etapa de secundaria (ISCED 0-2) que no siguen ninguna "
            "educación o formación. Encuesta de Población Activa (LFS); las banderas 'b' marcan rupturas de serie.",
        ),
    ),
    (
        "eurostat_edat_lfse_16.json",
        eurostat_url("edat_lfse_16", {"sex": "T", "age": "Y18-24", "unit": "PC"}),
        parse_eurostat(
            "edat_lfse_16", "early_leavers_18_24.T.NUTS2", "PC", "% de la población de 18 a 24 años",
            "Abandono temprano de la educación y la formación por región NUTS 2",
            "Mismo indicador que edat_lfse_14, por región NUTS 2 (comunidades y ciudades autónomas de España).",
            geo_filter=lambda g: g.startswith("ES") and len(g) == 4,
        ),
    ),
    (
        "eurostat_lfsa_eoqgan.json",
        eurostat_url("lfsa_eoqgan", {"sex": "T", "citizen": "TOTAL", "age": "Y20-64", "unit": "PC", "geo": PEERS}),
        parse_eurostat(
            "lfsa_eoqgan", "overqualification_rate.Y20-64", "PC", "% de los ocupados con estudios superiores",
            "Tasa de sobrecualificación (20-64 años, ocupados con estudios superiores)",
            "Ocupados con educación terciaria (ISCED 5-8) que trabajan en ocupaciones que no la requieren "
            "(ISCO 4-9), en % de todos los ocupados con educación terciaria.",
        ),
    ),
    (
        "eurostat_gov_10a_exp_gf09.json",
        eurostat_url("gov_10a_exp", {"cofog99": "GF09", "na_item": "TE", "sector": "S13", "unit": "PC_GDP", "geo": PEERS}),
        parse_eurostat(
            "gov_10a_exp", "GF09.TE.S13", "PC_GDP", "% del PIB",
            "Gasto de las administraciones públicas en educación (COFOG 09), % del PIB",
            "Gasto total de las administraciones públicas en la función educación (COFOG 09), contabilidad nacional SEC 2010.",
        ),
    ),
    (
        "eurostat_educ_uoe_fine09.json",
        eurostat_url("educ_uoe_fine09", {"unit": "PPS", "isced11": "ED02-8", "geo": PEERS}),
        parse_eurostat(
            "educ_uoe_fine09", "public_exp_per_student.ED02-8", "PPS", "Estándar de poder adquisitivo (PPS) por alumno",
            "Gasto público en educación por alumno a tiempo completo equivalente, de Infantil (2.º ciclo) a universidad",
            "Gasto público en educación (UOE) dividido por el alumnado equivalente a tiempo completo, en PPS corrientes.",
        ),
    ),
    (
        "eurostat_educ_uoe_perp04.json",
        eurostat_url("educ_uoe_perp04", {"unit": "RT", "isced11": ["ED1", "ED2", "ED3"], "geo": PEERS}),
        parse_eurostat(
            "educ_uoe_perp04", "pupil_teacher_ratio", "RT", "Alumnos por profesor",
            "Alumnos por profesor (equivalentes a tiempo completo), por etapa",
            "Ratio de alumnos y estudiantes por profesor y personal académico, en equivalentes a tiempo completo (UOE).",
        ),
    ),
    (
        "eurostat_educ_uoe_enrs04.json",
        eurostat_url("educ_uoe_enrs04", {"unit": "NR", "worktime": "TOTAL", "sector": "TOT_SEC", "sex": "T",
                                         "isced11": ["ED3", "ED35"], "geo": PEERS}),
        parse_eurostat(
            "educ_uoe_enrs04", "upper_secondary_enrolment", "PERSONS", "Alumnos",
            "Alumnado de secundaria superior (ISCED 3) total y en programas profesionales (FP de grado medio y equivalentes)",
            "Alumnos matriculados en secundaria superior por orientación del programa (UOE).",
        ),
    ),
    (
        "eurostat_edat_lfse_24.json",
        eurostat_url("edat_lfse_24", {"sex": "T", "age": "Y20-34", "duration": "Y1-3", "unit": "PC",
                                      "isced11": ["ED34_44", "ED35_45", "ED5-8"], "geo": PEERS}),
        parse_eurostat(
            "edat_lfse_24", "recent_graduates_employment_rate", "PC", "% de ocupados",
            "Tasa de empleo de titulados recientes (20-34 años, 1-3 años después de terminar, sin seguir estudiando)",
            "Ocupados entre los jóvenes de 20 a 34 años que terminaron su nivel más alto hace 1 a 3 años y no siguen estudiando, "
            "por nivel y orientación (general o profesional). Encuesta de Población Activa.",
        ),
    ),
    (
        "eurostat_edat_lfse_03.json",
        eurostat_url("edat_lfse_03", {"sex": "T", "age": "Y25-34", "unit": "PC",
                                      "isced11": ["ED0-2", "ED3_4", "ED5-8"], "geo": PEERS}),
        parse_eurostat(
            "edat_lfse_03", "attainment_25_34", "PC", "% de la población de 25 a 34 años",
            "Nivel de estudios alcanzado, población de 25 a 34 años",
            "Población de 25 a 34 años por nivel máximo de estudios terminado (ISCED 2011). Encuesta de Población Activa.",
        ),
    ),
    (
        "eurostat_edat_lfse_03_by_age.json",
        eurostat_url("edat_lfse_03", {"sex": "T", "age": ["Y25-34", "Y35-44", "Y45-54", "Y55-64"], "unit": "PC",
                                      "isced11": ["ED0-2", "ED3_4", "ED5-8"], "geo": ["ES", "EU27_2020"]}),
        parse_eurostat(
            "edat_lfse_03", "attainment_by_age", "PC", "% de la población de cada grupo de edad",
            "Nivel de estudios alcanzado por grupo de edad (25-34, 35-44, 45-54 y 55-64 años)",
            "Población de cada grupo de edad por nivel máximo de estudios terminado (ISCED 2011). Encuesta de Población "
            "Activa. Cada grupo de edad es una generación distinta, no la misma persona a lo largo del tiempo.",
        ),
    ),
    (
        "eurostat_edat_lfse_02.json",
        eurostat_url("edat_lfse_02", {"sex": "T", "wstatus": "POP", "age": "Y18-24", "unit": "PC",
                                      "c_birth": ["NAT", "FOR"], "geo": ["ES", "EU27_2020"]}),
        parse_eurostat(
            "edat_lfse_02", "early_leavers_18_24.by_birth", "PC", "% de la población de 18 a 24 años",
            "Abandono temprano de la educación y la formación (18-24 años) por país de nacimiento",
            "Mismo indicador que edat_lfse_14, separado entre nacidos en el país (NAT) y nacidos en el extranjero (FOR). "
            "Encuesta de Población Activa; las banderas 'b' marcan rupturas de serie y 'u' baja fiabilidad.",
        ),
    ),
    (
        "eurostat_educ_uoe_fine01.json",
        eurostat_url("educ_uoe_fine01", {"unit": "MIO_EUR", "sector": ["S1", "S1D", "S13"], "isced11": ["ED02-8", "ED5-8"], "geo": PEERS}),
        parse_eurostat(
            "educ_uoe_fine01", "education_expenditure_by_source", "MIO_EUR", "Millones de euros",
            "Gasto total en educación por origen de los fondos (total, administraciones públicas, sector privado no educativo)",
            "Gasto en educación (UOE) por fuente inicial de los fondos: total de la economía (S1), administraciones públicas "
            "(S13) y sector privado no educativo, principalmente hogares (S1D).",
        ),
    ),
    (
        "eurostat_nama_10_co3_p3_cp10.json",
        eurostat_url("nama_10_co3_p3", {"coicop": "CP10", "unit": "PC_TOT", "geo": PEERS}),
        parse_eurostat(
            "nama_10_co3_p3", "household_consumption_education", "PC_TOT", "% del consumo final de los hogares",
            "Gasto de los hogares en educación (COICOP 10), % de su consumo final",
            "Consumo final de los hogares por finalidad (contabilidad nacional): enseñanza, en % del consumo total.",
        ),
    ),
    (
        "eurostat_edat_lfse_20.json",
        eurostat_url("edat_lfse_20", {"sex": "T", "age": "Y15-29", "training": "NO_FE_NO_NFE", "wstatus": "NEMP", "unit": "PC", "geo": PEERS}),
        parse_eurostat(
            "edat_lfse_20", "neet_15_29", "PC", "% de la población de 15 a 29 años",
            "Jóvenes de 15 a 29 años que ni trabajan ni estudian ni se forman (ninis)",
            "Jóvenes sin empleo que no siguen ninguna educación o formación, formal o no formal. Encuesta de Población Activa.",
        ),
    ),
    (
        "eurostat_lfsa_ergaed.json",
        eurostat_url("lfsa_ergaed", {"sex": "T", "age": "Y25-64", "unit": "PC", "isced11": ["ED0-2", "ED3_4", "ED5-8"], "geo": PEERS}),
        parse_eurostat(
            "lfsa_ergaed", "employment_rate_by_attainment_25_64", "PC", "% de ocupados",
            "Tasa de empleo de 25 a 64 años por nivel de estudios",
            "Ocupados en % de la población de 25 a 64 años, por nivel máximo de estudios. Encuesta de Población Activa.",
        ),
    ),
    (
        "eurostat_nama_10_gdp_deflator.json",
        eurostat_url("nama_10_gdp", {"na_item": "B1GQ", "unit": "PD20_NAC", "geo": "ES"}),
        parse_eurostat(
            "nama_10_gdp", "B1GQ.PD20_NAC", "PD20_NAC", "Índice 2020 = 100",
            "Deflactor implícito del PIB de España (2020 = 100)",
            "Índice de precios implícito del PIB, moneda nacional. Se usa para pasar el gasto a euros constantes.",
        ),
    ),
]


# ---------------------------------------------------------------- OECD Education at a Glance (DBnomics mirror)

OECD_EAG_DATASET = "DSD_EAG_UOE_FIN@DF_UOE_INDIC_FIN_PERSTUD"


def oecd_eag_url() -> str:
    dims = {
        "REF_AREA": OECD_PEERS, "MEASURE": ["FIN_PERSTUD"], "EDUCATION_LEV": ["ISCED11_1T8", "ISCED11_1T4"],
        "EXP_SOURCE": ["S13"], "EXP_DESTINATION": ["INST_EDU"], "EXPENDITURE_TYPE": ["DIR_EXP"],
        "PRICE_BASE": ["Q", "V"], "UNIT_MEASURE": ["USD_PPP_ST"],
    }
    return f"https://api.db.nomics.world/v22/series/OECD/{OECD_EAG_DATASET}?" + urllib.parse.urlencode(
        {"dimensions": json.dumps(dims, separators=(",", ":")), "observations": 1, "limit": 500}
    )


OECD_SAL_DATASET = "DSD_EAG_SAL_TREND@DF_TCH_STA"
SAL_LEVELS = {"ISCED11_1": "Primaria", "ISCED11_24": "Secundaria inferior (ESO)", "ISCED11_34": "Secundaria superior (Bachillerato)"}


def oecd_salary_url() -> str:
    dims = {
        "REF_AREA": OECD_PEERS, "MEASURE": ["SAL_STA"], "UNIT_MEASURE": ["IX"], "INST_TYPE_EDU": ["INST_EDU_PUB"],
        "EDUCATION_LEV": list(SAL_LEVELS), "PERS_TYPE": ["TE"], "PERS_QUAL_LEV": ["TYP_EXP"], "PERS_EXP_LEV": ["EXP0", "EXP15"],
    }
    return f"https://api.db.nomics.world/v22/series/OECD/{OECD_SAL_DATASET}?" + urllib.parse.urlencode(
        {"dimensions": json.dumps(dims, separators=(",", ":")), "observations": 1, "limit": 500}
    )


def parse_oecd_salaries(raw: Raw) -> Iterable[Batch]:
    order = ["REF_AREA", "MEASURE", "UNIT_MEASURE", "INST_TYPE_EDU", "EDUCATION_LEV", "AGE", "SEX", "PERS_TYPE",
             "PERS_QUAL_LEV", "PERS_EXP_LEV", "PRICE_BASE"]
    series = []
    for doc_index, doc in enumerate(raw.json()["series"]["docs"]):
        dims = dict(zip(order, doc["series_code"].split(".")))
        obs = [
            {"period": period, "value": value, "pointer": pointer("series", "docs", doc_index, "value", i), "cell_index": i}
            for i, (period, value) in enumerate(zip(doc["period"], doc["value"]))
            if isinstance(value, (int, float))
        ]
        series.append(area_series(f"{OECD_SAL_DATASET}|{doc['series_code']}", dims["REF_AREA"], dims, obs))
    yield {
        "source_id": "oecd_eag_finance", "dataset_code": OECD_SAL_DATASET, "indicator_code": "SAL_STA.TE.TYP_EXP",
        "frequency_code": "A", "frequency_label": "Anual", "unit_code": "IX2015", "unit_label": "Índice 2015 = 100, precios constantes",
        "label": "Salario legal del profesorado en centros públicos, en términos reales (índice 2015 = 100)",
        "definition": "OCDE Education at a Glance: salario anual bruto legal del profesorado con la titulación más habitual, al "
        "inicio de la carrera y con 15 años de experiencia, deflactado (índice 2015 = 100). Leído de la réplica DBnomics.",
        "methodology_url": "https://www.oecd.org/en/topics/sub-issues/teachers-salaries.html",
        "source_url": f"https://db.nomics.world/OECD/{OECD_SAL_DATASET}",
    }, sorted(series, key=lambda s: s["key"])


OECD_EARN_DATASET = "DSD_EAG_LSO_EA@DF_LSO_EARN_REL_UPPER"


def oecd_earnings_url() -> str:
    return f"https://api.db.nomics.world/v22/series/OECD/{OECD_EARN_DATASET}?" + urllib.parse.urlencode(
        {"dimensions": json.dumps({"REF_AREA": OECD_PEERS, "SEX": ["_T"], "AGE": ["Y25T64"],
                                   "ATTAINMENT_LEV": ["ISCED11A_0T2", "ISCED11A_3", "ISCED11A_5T8"],
                                   "WORK_TIME_ARNGMNT": ["FT"]}, separators=(",", ":")), "observations": 1, "limit": 1000}
    )


def parse_oecd_earnings(raw: Raw) -> Iterable[Batch]:
    """Full-time workers aged 25-64, both sexes: earnings relative to upper-secondary graduates (= 100)."""
    series = []
    for doc_index, doc in enumerate(raw.json()["series"]["docs"]):
        parts = doc["series_code"].split(".")
        if parts[1] != "_T" or parts[2] != "Y25T64" or ".FT." not in doc["series_code"]:
            continue
        if parts[3] not in ("ISCED11A_0T2", "ISCED11A_3", "ISCED11A_5T8"):
            continue
        obs = [
            {"period": period, "value": value, "pointer": pointer("series", "docs", doc_index, "value", i), "cell_index": i}
            for i, (period, value) in enumerate(zip(doc["period"], doc["value"]))
            if isinstance(value, (int, float))
        ]
        series.append(area_series(f"{OECD_EARN_DATASET}|{doc['series_code']}", parts[0],
                                  {"series_code": doc["series_code"], "ATTAINMENT_LEV": parts[3], "SEX": parts[1], "AGE": parts[2],
                                   "WORK_TIME": "FT"}, obs))
    yield {
        "source_id": "oecd_eag_finance", "dataset_code": OECD_EARN_DATASET, "indicator_code": "EARN_REL_UPPER.Y25T64.FT",
        "frequency_code": "A", "frequency_label": "Anual", "unit_code": "PT_EARN_WR_ISCED11A_3",
        "unit_label": "Ingresos relativos (secundaria superior = 100)",
        "label": "Ingresos laborales relativos por nivel de estudios, trabajadores a tiempo completo de 25 a 64 años",
        "definition": "OCDE Education at a Glance: ingresos de los trabajadores a tiempo completo con cada nivel de estudios en % "
        "de los de quienes tienen secundaria superior. Leído de la réplica DBnomics.",
        "methodology_url": "https://www.oecd.org/en/topics/sub-issues/education-and-earnings.html",
        "source_url": f"https://db.nomics.world/OECD/{OECD_EARN_DATASET}",
    }, sorted(series, key=lambda s: s["key"])


INE_EPF = {
    73828: ("epf_education_by_spending_quintile", "Gasto de los hogares en servicios de educación por quintil de gasto total del hogar (EPF)",
            lambda name: "educaci" in name.lower()),
    73809: ("epf_education_by_income_band", "Gasto de los hogares en servicios de educación por ingresos mensuales netos del hogar (EPF)",
            lambda name: "educaci" in name.lower()),
    75004: ("epf_education_subgroups", "Gasto medio por hogar en enseñanza por nivel (EPF, subgrupos COICOP)",
            lambda name: name.startswith("Enseñanza") and "Dato base. Gasto total. Gasto medio por hogar" in name),
}


def parse_ine_epf(table: int) -> Callable[[Raw], Iterable[Batch]]:
    code, label, keep = INE_EPF[table]

    def parse(raw: Raw) -> Iterable[Batch]:
        series = []
        for i, item in enumerate(raw.json()):
            name = item["Nombre"].strip()
            if not keep(name):
                continue
            obs = [
                {"period": str(point["Anyo"]), "value": point["Valor"], "pointer": pointer(i, "Data", j, "Valor"), "cell_index": j}
                for j, point in enumerate(item.get("Data", [])) if point.get("Valor") is not None
            ]
            series.append(area_series(f"INE|{table}|{item.get('COD', name)}", "ES", {"nombre": name}, obs))
        yield {
            "source_id": "ine_epf", "dataset_code": f"t{table}", "indicator_code": code, "frequency_code": "A",
            "frequency_label": "Anual", "unit_code": "EPF_MIXED", "unit_label": "Euros por hogar o persona, o porcentaje, según la serie",
            "label": label, "definition": "INE, Encuesta de Presupuestos Familiares; cada serie lleva en su nombre la medida.",
            "methodology_url": "https://www.ine.es/dyngs/INEbase/es/operacion.htm?c=Estadistica_C&cid=1254736176806",
            "source_url": f"https://www.ine.es/jaxiT3/Tabla.htm?t={table}",
        }, series
    return parse


EAG_LEVELS = {"ISCED11_1T8": "Primaria a terciaria", "ISCED11_1T4": "Primaria a postsecundaria no terciaria"}
EAG_PRICES = {"Q": ("USD_PPP_2020", "Dólares PPA constantes de 2020 por estudiante"), "V": ("USD_PPP", "Dólares PPA corrientes por estudiante")}


def parse_oecd_eag(raw: Raw) -> Iterable[Batch]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for doc_index, doc in enumerate(raw.json()["series"]["docs"]):
        area, measure, level, source, dest, kind, price, unit, sheet = doc["series_code"].split(".")
        obs = [
            {"period": period, "value": value, "pointer": pointer("series", "docs", doc_index, "value", i), "cell_index": i}
            for i, (period, value) in enumerate(zip(doc["period"], doc["value"]))
            if isinstance(value, (int, float))
        ]
        dims = {"REF_AREA": area, "MEASURE": measure, "EDUCATION_LEV": level, "EXP_SOURCE": source,
                "EXP_DESTINATION": dest, "EXPENDITURE_TYPE": kind, "PRICE_BASE": price, "UNIT_MEASURE": unit}
        grouped.setdefault((level, price), []).append(area_series(f"{OECD_EAG_DATASET}|{doc['series_code']}", area, dims, obs))
    for (level, price), series in sorted(grouped.items()):
        unit_code, unit_label = EAG_PRICES[price]
        yield {
            "source_id": "oecd_eag_finance", "dataset_code": OECD_EAG_DATASET,
            "indicator_code": f"FIN_PERSTUD.{level}.S13.INST_EDU.DIR_EXP", "frequency_code": "A",
            "frequency_label": "Anual", "unit_code": unit_code, "unit_label": unit_label,
            "label": f"Gasto público en instituciones educativas por estudiante ETC — {EAG_LEVELS[level]} ({unit_label})",
            "definition": "OCDE Education at a Glance (UOE): gasto con origen en las administraciones públicas (S13) en "
            "instituciones educativas, por estudiante equivalente a tiempo completo. Precios constantes: deflactor del "
            "PIB y PPA de 2020. Leído de la réplica DBnomics porque oecd.org bloquea el acceso por script.",
            "methodology_url": "https://www.oecd.org/en/topics/sub-issues/education-financing.html",
            "source_url": f"https://db.nomics.world/OECD/{OECD_EAG_DATASET}",
        }, series


# ---------------------------------------------------------------- World Bank EdStats (PISA 2000-2018)

WB_PISA = {
    "LO.PISA.MAT": ("pisa_math_mean", "PISA: puntuación media en matemáticas"),
    "LO.PISA.REA": ("pisa_reading_mean", "PISA: puntuación media en lectura"),
    "LO.PISA.SCI": ("pisa_science_mean", "PISA: puntuación media en ciencias"),
}
WB_AREAS = ["ESP", "DEU", "FRA", "ITA", "PRT", "OED"]


def parse_worldbank(code: str) -> Callable[[Raw], Iterable[Batch]]:
    def parse(raw: Raw) -> Iterable[Batch]:
        indicator, label = WB_PISA[code]
        rows = raw.json()[1]
        grouped: dict[str, list[dict[str, Any]]] = {}
        for i, row in enumerate(rows):
            if row["value"] is None:
                continue
            area = row["countryiso3code"] or row["country"]["id"]
            grouped.setdefault(area, []).append(
                {"period": row["date"], "value": row["value"], "pointer": pointer(1, i, "value"), "cell_index": i}
            )
        yield {
            "source_id": "worldbank_edstats", "dataset_code": "EdStats", "indicator_code": indicator,
            "frequency_code": "PISA", "frequency_label": "Ciclo PISA (trienal)", "unit_code": "PISA_SCORE",
            "unit_label": "Puntos PISA", "label": f"{label} (Banco Mundial EdStats, {code})",
            "definition": "Puntuación media de los alumnos de 15 años en PISA (OCDE), recogida por el Banco Mundial.",
            "methodology_url": f"https://databank.worldbank.org/source/education-statistics-%5e-all-indicators",
            "source_url": f"https://api.worldbank.org/v2/country/ESP/indicator/{code}?source=12",
        }, [area_series(f"EdStats|{code}|{area}", area, {"indicator": code, "country": area},
                        sorted(obs, key=lambda o: o["period"])) for area, obs in sorted(grouped.items())]
    return parse


WB_SOURCES = [
    (f"worldbank_edstats_{code}.json",
     f"https://api.worldbank.org/v2/country/{';'.join(WB_AREAS)}/indicator/{code}?source=12&format=json&per_page=500&date=2000:2025",
     parse_worldbank(code))
    for code in WB_PISA
]


# ---------------------------------------------------------------- Our World in Data (long run)

OWID_AREAS = {"ESP", "FRA", "ITA", "PRT", "DEU"}
OWID = {
    "cross-country-literacy-rates": (
        "literacy_rate", "PC", "% de la población alfabetizada",
        "Tasa de alfabetización (serie histórica)",
        "Hasta 1950: censos recopilados por la UNESCO (1953, 1957), población de 10 o más años en la mayoría de "
        "países; desde 1970 aprox.: Instituto de Estadística de la UNESCO, población de 15 o más años. Recopilado por "
        "Our World in Data.",
    ),
    "mean-years-of-schooling-long-run": (
        "mean_years_schooling_15_64", "YEARS", "Años de escolarización",
        "Años medios de escolarización, población de 15 a 64 años",
        "Lee y Lee (2016), 'Human Capital in the Long Run' (1870-2010) y Barro y Lee (2015) para 2015-2020 "
        "(proyecciones), recopilados por Our World in Data.",
    ),
}


def parse_owid(slug: str) -> Callable[[Raw], Iterable[Batch]]:
    def parse(raw: Raw) -> Iterable[Batch]:
        indicator, unit_code, unit_label, label, definition_text = OWID[slug]
        reader = csv.reader(io.StringIO(raw.payload.decode("utf-8")))
        header = next(reader)
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row_index, row in enumerate(reader, start=1):
            if len(row) < 4 or row[1] not in OWID_AREAS or not row[3]:
                continue
            grouped.setdefault(row[1], []).append({
                "period": row[2], "value": float(row[3]), "pointer": pointer("rows", row_index, header[3]),
                "cell_index": row_index, "raw": row[3],
            })
        yield {
            "source_id": "owid_grapher", "dataset_code": slug, "indicator_code": indicator, "frequency_code": "IRREG",
            "frequency_label": "Irregular (censos y estimaciones)", "unit_code": unit_code, "unit_label": unit_label,
            "label": label, "definition": definition_text, "extraction_method": "csv_row_column",
            "methodology_url": f"https://ourworldindata.org/grapher/{slug}",
            "source_url": f"https://ourworldindata.org/grapher/{slug}",
        }, [area_series(f"owid|{slug}|{area}", area, {"entity": area}, sorted(obs, key=lambda o: int(o["period"])))
            for area, obs in sorted(grouped.items())]
    return parse


OWID_SOURCES = [
    (f"owid_{slug}.csv", f"https://ourworldindata.org/grapher/{slug}.csv?csvType=full&useColumnShortNames=true", parse_owid(slug))
    for slug in OWID
]

API_SOURCES: list[tuple[str, str, Callable[[Raw], Iterable[Batch]]]] = [
    *MEFP_SOURCES,
    *EUROSTAT_SOURCES,
    ("oecd_eag_per_student_dbnomics.json", oecd_eag_url(), parse_oecd_eag),
    ("oecd_eag_teacher_salaries_dbnomics.json", oecd_salary_url(), parse_oecd_salaries),
    ("oecd_eag_earnings_dbnomics.json", oecd_earnings_url(), parse_oecd_earnings),
    *[
        (f"ine_epf_t{table}.json", f"https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/{table}?nult=12", parse_ine_epf(table))
        for table in INE_EPF
    ],
    *WB_SOURCES,
    *OWID_SOURCES,
]


# ---------------------------------------------------------------- curated PISA values (document + page + quote)

CURATED_LABELS = {
    "pisa_math_mean": ("PISA_SCORE", "Puntos PISA", "PISA: puntuación media en matemáticas (informe oficial)"),
    "pisa_reading_mean": ("PISA_SCORE", "Puntos PISA", "PISA: puntuación media en lectura (informe oficial)"),
    "pisa_science_mean": ("PISA_SCORE", "Puntos PISA", "PISA: puntuación media en ciencias (informe oficial)"),
    "pisa_repeated_grade_pct": ("PC", "% del alumnado de 15 años", "PISA: alumnado que declara haber repetido curso al menos una vez"),
    "pisa_escs_gap_math": ("PISA_SCORE", "Puntos PISA", "PISA: diferencia en matemáticas entre el 25 % más aventajado y el 25 % más desaventajado (ISEC)"),
    "pisa_escs_variance_pct": ("PC", "% de la varianza", "PISA: parte de la variación en matemáticas explicada por el índice socioeconómico (ISEC)"),
    "pisa_resilient_pct": ("PC", "% del alumnado desaventajado", "PISA: alumnado desaventajado en el cuarto superior de rendimiento (resiliente)"),
    "pisa_immigrant_share_pct": ("PC", "% del alumnado de 15 años", "PISA: alumnado de origen inmigrante"),
    "pisa_immigrant_gap_math": ("PISA_SCORE", "Puntos PISA", "PISA: diferencia en matemáticas entre alumnado no inmigrante e inmigrante"),
    "pisa_immigrant_gap_math_escs_adjusted": ("PISA_SCORE", "Puntos PISA", "PISA: diferencia inmigrante en matemáticas tras descontar el ISEC"),
    "pisa_isec_above_oecd_flag": ("FLAG", "1 = ISEC medio superior a la media OCDE", "PISA: comunidades con ISEC medio superior a la media OCDE (según el informe español)"),
    "pisa_isec_mean": ("ISEC", "Índice ISEC (media OCDE = 0)", "PISA: índice medio de estatus económico, social y cultural (ISEC)"),
    "pisa_isec_r2_math_pct": ("PC", "% de la variación (R²)", "PISA: variación de la puntuación media en matemáticas explicada por el ISEC medio"),
    "piaac_literacy_by_age": ("PIAAC_SCORE", "Puntos PIAAC", "PIAAC 2023: comprensión lectora de adultos por grupo de edad"),
    "piaac_numeracy_by_age": ("PIAAC_SCORE", "Puntos PIAAC", "PIAAC 2023: matemáticas de adultos por grupo de edad"),
    "piaac_literacy_mean": ("PIAAC_SCORE", "Puntos PIAAC", "PIAAC 2023: comprensión lectora de adultos (16-65 años)"),
    "piaac_numeracy_mean": ("PIAAC_SCORE", "Puntos PIAAC", "PIAAC 2023: matemáticas de adultos (16-65 años)"),
    "piaac_literacy_tertiary": ("PIAAC_SCORE", "Puntos PIAAC", "PIAAC 2023: comprensión lectora de adultos con estudios superiores"),
    "piaac_literacy_below_upper_secondary": ("PIAAC_SCORE", "Puntos PIAAC", "PIAAC 2023: comprensión lectora de adultos sin secundaria superior"),
    "pisa_disadvantaged_immigrant_pct": ("PC", "% del alumnado inmigrante", "PISA: alumnado inmigrante socioeconómicamente desaventajado"),
    "pisa_private_gap_math": ("PISA_SCORE", "Puntos PISA", "PISA: diferencia en matemáticas entre centros privados (concertados y privados) y públicos"),
    "pisa_private_gap_math_escs_adjusted": ("PISA_SCORE", "Puntos PISA", "PISA: diferencia privados-públicos en matemáticas tras descontar el ISEC del alumno"),
    "pisa_private_gap_math_escs_school_adjusted": ("PISA_SCORE", "Puntos PISA", "PISA: diferencia privados-públicos en matemáticas tras descontar el ISEC del alumno y del centro"),
    "pisa_public_school_share_pct": ("PC", "% del alumnado de 15 años", "PISA: alumnado matriculado en centros públicos"),
    "pisa_gender_gap_math": ("PISA_SCORE", "Puntos PISA", "PISA: diferencia en matemáticas entre chicos y chicas (a favor de los chicos)"),
    "pisa_math_public_mean": ("PISA_SCORE", "Puntos PISA", "PISA: puntuación media en matemáticas del alumnado de centros públicos"),
    "pisa_math_private_mean": ("PISA_SCORE", "Puntos PISA", "PISA: puntuación media en matemáticas del alumnado de centros privados (concertados y privados)"),
    "pisa_gender_gap_reading": ("PISA_SCORE", "Puntos PISA", "PISA: diferencia en lectura entre chicas y chicos (a favor de las chicas)"),
}


def pdf_text(path: Path) -> str | None:
    if not shutil.which("pdftotext"):
        return None
    out = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, check=False)
    return re.sub(r"\s+", " ", out.stdout.decode("utf-8", errors="replace")) if out.returncode == 0 else None


def check_documents(data: dict[str, Any], offline: bool) -> dict[str, Any]:
    """Cache each cited PDF, check its sha256 and that every quote appears in its text."""
    report: dict[str, Any] = {}
    texts: dict[str, str | None] = {}
    for doc_id, doc in data["documents"].items():
        raw = fetch_raw(f"docs/{doc_id}.pdf", doc["url"], offline, reuse=True)
        if raw.sha256 != doc["sha256"]:
            raise SystemExit(f"{doc_id}: cached PDF sha256 {raw.sha256} differs from the cited {doc['sha256']}")
        texts[doc_id] = pdf_text(raw.path)
        report[doc_id] = {"sha256_ok": True, "bytes": len(raw.payload)}
    missing = []
    for key, rows in data["series"].items():
        for row in rows:
            text = texts.get(row["document"])
            if text is not None and re.sub(r"\s+", " ", row["quote"]) not in text:
                missing.append(f"{key}/{row['area']}/{row['year']}")
    if missing:
        raise SystemExit(f"quotes not found in cached PDFs: {missing}")
    report["quotes_checked"] = all(texts.values())
    return report


def load_curated(conn: sqlite3.Connection, snapshot_date: str, offline: bool) -> dict[str, Any]:
    path = MANUAL_DIR / "pisa_curated_es.json"
    payload = path.read_bytes()
    data = json.loads(payload)
    totals: dict[str, Any] = {"releases": 0, "observations": 0, "documents": check_documents(data, offline)}
    for key, rows in sorted(data["series"].items()):
        unit_code, unit_label, label = CURATED_LABELS[key]
        grouped: dict[tuple[str, str | None], list[dict[str, Any]]] = {}
        for index, row in enumerate(rows):
            doc = data["documents"][row["document"]]
            grouped.setdefault((row["area"], row.get("age")), []).append({
                "period": str(row["year"]), "value": row["value"], "pointer": pointer("series", key, index, "value"),
                "cell_index": index, "evidence_url": doc["url"], "raw": {**row, "document_sha256": doc["sha256"]},
            })
        definition = {
            "source_id": "vclc_education_curated", "dataset_code": "pisa_curated_es", "indicator_code": key,
            "frequency_code": "PISA", "frequency_label": "Ciclo PISA", "unit_code": unit_code, "unit_label": unit_label,
            "label": label, "extraction_method": "curated_citation",
            "definition": "Valor citado literalmente del documento oficial; cada fila lleva URL, SHA-256 del PDF, página y cita.",
            "methodology_url": "https://votaconlachola.org/visualizaciones/educacion/#metodo",
            "source_url": "https://www.educacionfpydeportes.gob.es/inee/evaluaciones-internacionales/pisa.html",
        }
        counts = load_indicator(
            conn, definition, sha256_bytes(payload), len(payload), rel(path), definition["source_url"], snapshot_date,
            {"documents": data["documents"], "gaps": data.get("gaps", [])},
            [
                area_series(f"pisa_curated_es|{key}|{area}" + (f"|{age}" if age else ""), area,
                            {"indicator": key, **({"age": age} if age else {})}, obs,
                            *((area.split(":", 1)[1], "es-ccaa-name", "region") if area.startswith("ES-CCAA:") else ()))
                for (area, age), obs in sorted(grouped.items(), key=lambda kv: (kv[0][0], kv[0][1] or ""))
            ],
        )
        totals["releases"] += counts["releases"]
        totals["observations"] += counts["observations"]
    return totals


# ---------------------------------------------------------------- main

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--offline", action="store_true", help="load from the raw cache without network")
    parser.add_argument("--snapshot-date", default=datetime.now(timezone.utc).date().isoformat())
    args = parser.parse_args()

    args.db.parent.mkdir(parents=True, exist_ok=True)
    conn = open_db(args.db)
    apply_schema(conn, DEFAULT_SCHEMA)
    seed_sources(conn)
    seed_sources_from_config(conn, LOCAL_SOURCES)
    conn.execute("PRAGMA foreign_keys = ON")
    report: dict[str, Any] = {"db": rel(args.db), "snapshot_date": args.snapshot_date, "indicators": {}}
    with conn:
        for name, url, parse in API_SOURCES:
            raw = fetch_raw(name, url, args.offline)
            for definition, series in parse(raw):
                meta = {"retrieved_at": raw.retrieved_at, "source_updated_at": definition.pop("source_updated_at", None)}
                counts = load_indicator(conn, definition, raw.sha256, len(raw.payload), rel(raw.path), raw.url,
                                        args.snapshot_date, meta, series)
                report["indicators"][f"{definition['source_id']}:{definition['indicator_code']}:{definition['unit_code']}"] = counts
        report["curated"] = load_curated(conn, args.snapshot_date, args.offline)
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk:
        raise SystemExit(f"foreign_key_check failed: {fk[:5]}")
    conn.close()
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
