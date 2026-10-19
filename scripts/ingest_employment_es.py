#!/usr/bin/env python3
"""Ingest Spain's employment series and European peers into SQLite (indicator contract v1).

Boundaries:
- ingest: fetch each source API, keep the raw payload under etl/data/raw/employment/apis/ (+ URL, retrieval time);
  `--offline` reuses that cache.
- normalize/load: every series lands in the canonical indicator tables (indicator_definitions -> indicator_releases
  -> indicator_series_versions -> indicator_observation_versions -> indicator_observation_evidence). A new raw
  payload is a new release; each observation is compared with the previous release (unchanged/changed/deleted),
  so later official revisions never overwrite what was observed before. Evidence points at the raw byte (JSON
  pointer + sha256).
- sources: AMECO (European Commission, via the DBnomics mirror) for unemployment since 1960 and the NAWRU; Eurostat
  (LFS and national accounts) for unemployment by age, temporary employees, employment rate and productivity per
  hour; INE Tempus (EPA) for the national figures since 2002, including «fijos discontinuos»; OECD Taxing Wages and
  Productivity Database via DBnomics, because sdmx.oecd.org answers scripted requests with HTTP 403.
- curated events: labour reforms and EPA series breaks (etl/data/manual/employment/events_es.json, one citation
  each) load as an indicator with interval_kind='event'.

The published site JSON is derived from this DB by scripts/export_public_viz_employment.py.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sqlite3
import ssl
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta, timezone
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

DEFAULT_DB = REPO_ROOT / "etl/data/staging/employment-es.db"
RAW_DIR = REPO_ROOT / "etl/data/raw/employment/apis"
FILES_DIR = REPO_ROOT / "etl/data/raw/employment/files"
MANUAL_DIR = REPO_ROOT / "etl/data/manual/employment"
USER_AGENT = "Mozilla/5.0 (compatible; vota-con-la-chola-etl/1.0; +https://votaconlachola.org)"
EXTRACTOR_VERSION = "ingest_employment_es/1"
DOMAIN = "empleo"
NUL = "\x00"

LOCAL_SOURCES: dict[str, dict[str, str]] = {
    "ameco_dbnomics": {
        "name": "Comisión Europea - AMECO (réplica DBnomics)",
        "scope": DOMAIN,
        "default_url": "https://db.nomics.world/AMECO",
        "format": "json",
    },
    "eurostat_sdmx": {
        "name": "Eurostat - API de difusión (JSON-stat)",
        "scope": "estadistica_europea",
        "default_url": "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/",
        "format": "json",
    },
    "ine_epa_tempus": {
        "name": "INE - Encuesta de Población Activa (API Tempus)",
        "scope": DOMAIN,
        "default_url": "https://servicios.ine.es/wstempus/js/ES/",
        "format": "json",
    },
    "oecd_taxing_wages": {
        "name": "OCDE - Taxing Wages, indicadores comparativos (réplica DBnomics)",
        "scope": DOMAIN,
        "default_url": "https://db.nomics.world/OECD/DSD_TAX_WAGES_COMP@DF_TW_COMP",
        "format": "json",
    },
    "oecd_productivity": {
        "name": "OCDE - Productivity Database (réplica DBnomics)",
        "scope": DOMAIN,
        "default_url": "https://db.nomics.world/OECD/DSD_PDB@DF_PDB",
        "format": "json",
    },
    "oecd_earnings": {
        "name": "OCDE - Earnings: salario mínimo frente al mediano (réplica DBnomics)",
        "scope": DOMAIN,
        "default_url": "https://db.nomics.world/OECD/DSD_EARNINGS@MIN2AVE",
        "format": "json",
    },
    "oecd_registered_unemployment": {
        "name": "OCDE - Infra-annual labour statistics: paro registrado (réplica DBnomics, origen SEPE)",
        "scope": DOMAIN,
        "default_url": "https://db.nomics.world/OECD/DSD_OLAB@DF_OIALAB_INDIC",
        "format": "json",
    },
    "ine_ipt_tempus": {
        "name": "INE - Índice de Precios del Trabajo (API Tempus)",
        "scope": DOMAIN,
        "default_url": "https://www.ine.es/dyngs/INEbase/es/operacion.htm?c=Estadistica_C&cid=1254736177025",
        "format": "json",
    },
    "ine_eaes_tempus": {
        "name": "INE - Encuesta Anual de Estructura Salarial (API Tempus)",
        "scope": DOMAIN,
        "default_url": "https://www.ine.es/dyngs/INEbase/es/operacion.htm?c=Estadistica_C&cid=1254736177039",
        "format": "json",
    },
    "dg_empl_lmp": {
        "name": "Comisión Europea, DG EMPL - base de datos de políticas de mercado de trabajo (LMP)",
        "scope": DOMAIN,
        "default_url": "https://webgate.ec.europa.eu/empl/redisstat/",
        "format": "json",
    },
    "oecd_taxben": {
        "name": "OCDE - Tax-Benefit: ingresos netos de quien cobra el salario mínimo (réplica DBnomics)",
        "scope": DOMAIN,
        "default_url": "https://db.nomics.world/OECD/DSD_TAXBEN_IMW@DF_IMW",
        "format": "json",
    },
    "seg_social_pxweb": {
        "name": "Seguridad Social - estadísticas de afiliación y días cotizados (PX-Web)",
        "scope": DOMAIN,
        "default_url": "https://w6.seg-social.es/PXWeb/",
        "format": "px",
    },
    "mites_anuario": {
        "name": "Ministerio de Trabajo - Anuario de Estadísticas, Movimiento Laboral Registrado",
        "scope": DOMAIN,
        "default_url": "https://www.mites.gob.es/es/estadisticas/anuarios/",
        "format": "xlsx",
    },
    "vclc_employment_events": {
        "name": "Reformas laborales y rupturas de la EPA (curado, una cita por hecho)",
        "scope": DOMAIN,
        "default_url": "https://www.boe.es/",
        "format": "json",
    },
}

AREA_META = {
    "ESP": ("España", "ISO3166-1-alpha-3", "country"),
    "DEU": ("Alemania", "ISO3166-1-alpha-3", "country"),
    "D_W": ("Alemania Occidental (RFA)", "AMECO", "country"),
    "FRA": ("Francia", "ISO3166-1-alpha-3", "country"),
    "ITA": ("Italia", "ISO3166-1-alpha-3", "country"),
    "PRT": ("Portugal", "ISO3166-1-alpha-3", "country"),
    "EU27": ("Unión Europea (27)", "AMECO", "aggregate"),
    "EU15": ("Unión Europea (15)", "AMECO", "aggregate"),
    "DU15": ("Unión Europea (15, con la RFA)", "AMECO", "aggregate"),
    "EA20": ("Zona del euro (20)", "AMECO", "aggregate"),
    "ES": ("España", "NUTS", "country"),
    "DE": ("Alemania", "NUTS", "country"),
    "FR": ("Francia", "NUTS", "country"),
    "IT": ("Italia", "NUTS", "country"),
    "PT": ("Portugal", "NUTS", "country"),
    "EU27_2020": ("Unión Europea (27, desde 2020)", "EU-aggregate", "aggregate"),
    "EA20_ES": ("Zona del euro (20)", "EU-aggregate", "aggregate"),
    "OECD_REP": ("Media OCDE (simple)", "OECD-aggregate", "aggregate"),
    "EU22OECD": ("Media de los 22 países de la UE en la OCDE", "OECD-aggregate", "aggregate"),
    "OECD": ("OCDE (agregado)", "OECD-aggregate", "aggregate"),
}

AMECO_GEOS = ["ESP", "EU27", "EU15", "DU15", "EA20", "DEU", "D_W", "FRA", "ITA", "PRT"]
EUROSTAT_GEOS = ["ES", "EU27_2020", "DE", "FR", "IT", "PT"]
OECD_AREAS = ["ESP", "OECD_REP", "EU22OECD", "DEU", "FRA", "ITA", "PRT"]
PDB_AREAS = ["ESP", "EU27_2020", "OECD", "DEU", "FRA", "ITA", "PRT"]


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


def period_bounds(period: str) -> tuple[str, str]:
    """Annual '2024' or quarterly '2024T3' -> ISO start/end."""
    if "T" in period:
        year, quarter = period.split("T")
        q = int(quarter)
        end_month = q * 3
        end_day = {3: 31, 6: 30, 9: 30, 12: 31}[end_month]
        return f"{year}-{end_month - 2:02d}-01", f"{year}-{end_month:02d}-{end_day}"
    if len(period) == 10:
        return period, period
    if len(period) == 7 and period[5] == "S":
        return (f"{period[:4]}-01-01", f"{period[:4]}-06-30") if period[6] == "1" else (f"{period[:4]}-07-01", f"{period[:4]}-12-31")
    if len(period) == 7 and period[4] == "-":
        year, month = int(period[:4]), int(period[5:])
        nxt = f"{year + month // 12}-{month % 12 + 1:02d}-01"
        end = (datetime.fromisoformat(nxt) - timedelta(days=1)).date().isoformat()
        return f"{period}-01", end
    return f"{period}-01-01", f"{period}-12-31"


# ---------------------------------------------------------------- raw fetch

class Raw:
    def __init__(self, name: str, url: str, payload: bytes, retrieved_at: str):
        self.name, self.url, self.payload, self.retrieved_at = name, url, payload, retrieved_at
        self.sha256 = sha256_bytes(payload)
        self.path = RAW_DIR / name
        self.data = json.loads(payload)


def fetch_raw(name: str, url: str, offline: bool) -> Raw:
    path = RAW_DIR / name
    meta_path = RAW_DIR / f"{name}.meta.json"
    if not offline:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = resp.read()
        json.loads(payload)  # never cache an HTML error page over a good payload
        RAW_DIR.mkdir(parents=True, exist_ok=True)
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
            definition["label"], definition.get("definition"), DOMAIN,
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
            start, end = period_bounds(period)
            obs_rows.append((
                obs_id, series_id, release_id, period, obs.get("start", start), obs.get("end", end),
                obs.get("interval_kind", "calendar_quarter" if "T" in period else "calendar_half" if "-S" in period else "calendar_month" if len(period) == 7 else "calendar_year"), value, text,
                obs.get("status"), canonical_json(obs.get("status_labels", [])), "not_provided", ordinal, state,
                prev_id, source_metadata.get("source_updated_at"), int(obs.get("cell_index", 0)),
                canonical_json(obs.get("raw", obs["value"])), ts, ts,
            ))
            ev_rows.append((
                stable_id("indicator-observation-evidence", obs_id, raw_sha256, obs["pointer"]), obs_id,
                obs.get("evidence_url") or source_url, raw_sha256, raw_path, obs["pointer"], None,
                definition.get("extraction_method", "json_pointer"), EXTRACTOR_VERSION, ts,
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
        start, end = period_bounds(period)
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


def area_series(key: str, geo: str, dimensions: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any]:
    name, system, level = AREA_META.get(geo, (geo, "unknown", "unknown"))
    return {
        "key": key, "geo_code": geo, "geo_name": name, "geo_system": system, "geo_level": level,
        "dimensions": dimensions, "observations": observations,
    }


# ---------------------------------------------------------------- sources -> indicator batches

Batch = tuple[dict[str, Any], list[dict[str, Any]]]


def dbnomics_series_url(provider: str, dataset: str, dimensions: dict[str, list[str]] | None = None) -> str:
    params: dict[str, Any] = {"observations": 1, "limit": 1000}
    if dimensions:
        params["dimensions"] = json.dumps(dimensions, separators=(",", ":"))
    return f"https://api.db.nomics.world/v22/series/{provider}/{urllib.parse.quote(dataset)}?" + urllib.parse.urlencode(params)


AMECO_CODES: dict[str, dict[str, str]] = {
    "ZUTN": {"variant": "1.0.0.0", "unit": "PC_ACT", "unit_label": "% de la población activa",
             "label": "Tasa de paro (% de la población activa), AMECO",
             "definition": "Tasa de paro armonizada por la Comisión Europea a partir de las encuestas de población activa nacionales (para España, la EPA)."},
    "ZNAWRU": {"variant": "1.0.0.0", "unit": "PC_ACT", "unit_label": "% de la población activa",
               "label": "NAWRU: paro compatible con salarios estables (% de la población activa), AMECO",
               "definition": "Estimación de la Comisión Europea del paro estructural (tasa de paro que no acelera los salarios), obtenida con su modelo de función de producción. Es una estimación de modelo, no una observación."},
    "NUTN": {"variant": "1.0.0.0", "unit": "THS_PER", "unit_label": "Miles de personas",
             "label": "Parados (miles de personas), AMECO",
             "definition": "Número de parados según la definición de la OIT (encuesta de población activa)."},
    "NETD": {"variant": "1.0.0.0", "unit": "THS_PER", "unit_label": "Miles de personas",
             "label": "Ocupados, total de la economía (miles de personas, contabilidad nacional), AMECO",
             "definition": "Empleo total en el concepto de contabilidad nacional (interior)."},
    "OVGD": {"variant": "1.1.0.0", "unit": "VOL_NAC", "unit_label": "Miles de millones en volumen (precios de 2015)",
             "label": "PIB en volumen, AMECO",
             "definition": "Producto interior bruto a precios constantes de 2015."},
    "RVGDE": {"variant": "1.1.0.0", "unit": "VOL_NAC_PER", "unit_label": "Miles en volumen por ocupado (precios de 2015)",
              "label": "PIB en volumen por ocupado, AMECO",
              "definition": "Productividad aparente del trabajo por persona ocupada, precios de 2015."},
    "RWCDC": {"variant": "3.1.0.0", "unit": "I20", "unit_label": "Índice 2020 = 100",
              "label": "Remuneración real por asalariado (deflactor del consumo privado), AMECO",
              "definition": "Remuneración de asalariados (salario bruto más cotizaciones de la empresa) por asalariado, deflactada con los precios del consumo privado: mide el poder de compra del coste salarial."},
}


def parse_ameco(code: str) -> Callable[[Raw], Iterable[Batch]]:
    def parse(raw: Raw) -> Iterable[Batch]:
        series = []
        for doc_index, doc in enumerate(raw.data["series"]["docs"]):
            geo, *rest = doc["series_code"].split(".")
            if geo not in AMECO_GEOS or ".".join(rest[:4]) != AMECO_CODES[code]["variant"]:
                continue
            indexed_year = int(str(doc.get("indexed_at") or raw.retrieved_at)[:4])
            obs = [
                {
                    "period": period, "value": value, "pointer": pointer("series", "docs", doc_index, "value", i),
                    "cell_index": i,
                    # AMECO ships the Commission forecast for the vintage year and the next one.
                    "status": "forecast" if int(period) >= indexed_year else None,
                }
                for i, (period, value) in enumerate(zip(doc["period"], doc["value"]))
                if isinstance(value, (int, float))
            ]
            series.append(area_series(f"AMECO|{doc['series_code']}", geo, {"series_code": doc["series_code"]}, obs))
        cfg = AMECO_CODES[code]
        yield {
            "source_id": "ameco_dbnomics", "dataset_code": code, "indicator_code": code, "frequency_code": "A",
            "frequency_label": "Anual", "unit_code": cfg["unit"], "unit_label": cfg["unit_label"],
            "label": cfg["label"], "definition": cfg["definition"],
            "methodology_url": "https://economy-finance.ec.europa.eu/economic-research-and-databases/economic-databases/ameco-database_en",
            "source_url": f"https://db.nomics.world/AMECO/{code}",
        }, series
    return parse


EUROSTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
A10_SECTORS = ["TOTAL", "A", "B-E", "C", "F", "G-I", "J", "K", "L", "M_N", "O-Q", "R-U"]
EUROSTAT_DATASETS: dict[str, dict[str, Any]] = {
    "une_rt_a": {
        "filters": {"age": ["Y15-74", "Y15-24"], "sex": ["T"], "unit": ["PC_ACT"]},
        "label": "Tasa de paro ({age}), Eurostat EPA armonizada", "unit_label": "% de la población activa",
        "definition": "Encuesta de Población Activa de la UE (LFS), media anual. Serie vigente desde 2003.",
    },
    "une_rt_a_h": {
        "filters": {"age": ["Y15-74", "Y15-24"], "sex": ["T"], "unit": ["PC_ACT"]},
        "label": "Tasa de paro ({age}), Eurostat, serie histórica 1992-2020", "unit_label": "% de la población activa",
        "definition": "Serie histórica de la LFS, cerrada en 2020 con la metodología anterior al reglamento IESS. "
        "No se empalma con une_rt_a: ambas se guardan y se muestran por separado.",
    },
    "lfsa_etpgan": {
        "filters": {"age": ["Y15-64"], "sex": ["T"], "citizen": ["TOTAL"], "unit": ["PC"]},
        "label": "Asalariados con contrato temporal ({age}), % del total de asalariados", "unit_label": "% de asalariados",
        "definition": "Encuesta de Población Activa de la UE (LFS). Los fijos discontinuos cuentan como indefinidos.",
    },
    "lfsi_emp_a": {
        "filters": {"age": ["Y20-64"], "sex": ["T"], "indic_em": ["EMP_LFS"], "unit": ["PC_POP"]},
        "label": "Tasa de empleo ({age}), Eurostat", "unit_label": "% de la población de esa edad",
        "definition": "Ocupados de 20 a 64 años sobre la población de esa edad (LFS). Serie vigente desde 2003.",
    },
    "lfsi_emp_a_h": {
        "filters": {"age": ["Y20-64"], "sex": ["T"], "indic_em": ["EMP_LFS"], "unit": ["PC_POP"]},
        "label": "Tasa de empleo ({age}), Eurostat, serie histórica 1992-2020", "unit_label": "% de la población de esa edad",
        "definition": "Serie histórica de la LFS cerrada en 2020; no se empalma con lfsi_emp_a.",
    },
    "une_ltu_a": {
        "filters": {"indic_em": ["LTU"], "age": ["Y15-74"], "sex": ["T"], "unit": ["PC_ACT", "PC_UNE"]},
        "label": "Paro de larga duración (12 meses o más), Eurostat", "unit_label": "% (ver unidad)",
        "definition": "Parados que llevan 12 meses o más buscando empleo: PC_ACT sobre la población activa, PC_UNE sobre el total de parados. Serie vigente desde 2003.",
    },
    "une_ltu_a_h": {
        "filters": {"indic_em": ["LTU"], "age": ["Y15-74"], "sex": ["T"], "unit": ["PC_ACT", "PC_UNE"]},
        "label": "Paro de larga duración, Eurostat, serie histórica 1996-2020", "unit_label": "% (ver unidad)",
        "definition": "Serie histórica de la LFS cerrada en 2020; no se empalma con une_ltu_a.",
    },
    "lfsa_urgaed": {
        "filters": {"age": ["Y25-64"], "sex": ["T"], "isced11": ["ED0-2", "ED3_4", "ED5-8", "TOTAL"], "unit": ["PC"]},
        "label": "Tasa de paro por nivel educativo ({age}), Eurostat", "unit_label": "% de la población activa",
        "definition": "ED0-2: hasta la ESO; ED3_4: bachillerato y FP de grado medio; ED5-8: estudios superiores (CINE 2011). Eurostat marca rupturas de serie (flag b); en 2014 cambia la clasificación de CINE 1997 a CINE 2011.",
    },
    "edat_lfse_03": {
        "filters": {"age": ["Y25-64"], "sex": ["T"], "isced11": ["ED0-2", "ED5-8"], "unit": ["PC"]},
        "label": "Población de {age} años por nivel educativo alcanzado, Eurostat", "unit_label": "% de la población de esa edad",
        "definition": "Porcentaje de la población de 25 a 64 años cuyo máximo nivel es ED0-2 (hasta la ESO) o ED5-8 (superiores).",
    },
    "nama_10_a10_e": {
        "filters": {"nace_r2": A10_SECTORS, "na_item": ["EMP_DC"], "unit": ["THS_PER", "THS_HW"]},
        "label": "Ocupados por rama de actividad (contabilidad nacional), Eurostat", "unit_label": "Miles de personas",
        "definition": "Empleo total por rama NACE Rev. 2 (A10): F = construcción, A = agricultura, C = industria manufacturera, G-I = comercio, transporte y hostelería.",
    },
    "sbs_sc_ovw": {
        "filters": {"indic_sbs": ["EMP_NR"], "nace_r2": ["B-S_X_O_S94"], "size_emp": ["TOTAL", "0-9", "10-19", "20-49", "50-249", "GE250"]},
        "label": "Personas ocupadas por tamaño de empresa (economía empresarial), Eurostat", "unit_label": "Personas",
        "definition": "Estadísticas estructurales de empresas: personas ocupadas en la economía de mercado no financiera y financiera (NACE B-S sin O ni S94), por tramo de ocupados de la empresa.",
    },
    "lfst_r_lfu3rt": {
        "geo_level": "nuts2",
        "filters": {"age": ["Y15-74"], "sex": ["T"], "isced11": ["TOTAL"], "unit": ["PC"]},
        "label": "Tasa de paro por región NUTS 2 ({age}), Eurostat", "unit_label": "% de la población activa",
        "definition": "Encuesta de Población Activa de la UE por región NUTS 2; en España, NUTS 2 = comunidades y ciudades autónomas.",
    },
    "lfst_r_lfe2emprt": {
        "geo_level": "nuts2",
        "filters": {"age": ["Y20-64"], "sex": ["T"], "unit": ["PC"]},
        "label": "Tasa de empleo por región NUTS 2 ({age}), Eurostat", "unit_label": "% de la población de esa edad",
        "definition": "Ocupados de 20 a 64 años sobre la población de esa edad, por región NUTS 2.",
    },
    "lfst_r_lmdur": {
        "filters": {"statinfo": ["DISP_NUTS2"], "age": ["Y15-74"], "sex": ["T"], "unit": ["PC"]},
        "label": "Dispersión regional de las tasas de paro (NUTS 2), Eurostat", "unit_label": "Coeficiente de variación (%)",
        "definition": "Coeficiente de variación de las tasas de paro regionales NUTS 2 de cada país, ponderado por población activa.",
    },
    "nama_10_a10": {
        "filters": {"nace_r2": A10_SECTORS, "na_item": ["B1G"], "unit": ["CLV15_MEUR"]},
        "label": "Valor añadido bruto en volumen por rama (A10), millones de euros encadenados de 2015, Eurostat", "unit_label": "Millones de euros de 2015",
        "definition": "VAB a precios constantes (volumen encadenado, referencia 2015) por rama NACE Rev. 2 A10; se usa con las horas trabajadas de nama_10_a10_e para la descomposición sectorial de la productividad.",
    },
    "lfsa_urgan": {
        "filters": {"age": ["Y15-74"], "sex": ["T"], "citizen": ["NAT", "FOR", "TOTAL"], "unit": ["PC"]},
        "label": "Tasa de paro por nacionalidad ({age}), Eurostat", "unit_label": "% de la población activa",
        "definition": "NAT: nacionales del país; FOR: extranjeros (de la UE y de fuera). Encuesta de Población Activa de la UE.",
    },
    "lfsa_agan": {
        "filters": {"age": ["Y15-74"], "sex": ["T"], "citizen": ["NAT", "FOR", "TOTAL"], "unit": ["THS_PER"]},
        "label": "Población activa por nacionalidad ({age}), Eurostat", "unit_label": "Miles de personas",
        "definition": "Población activa (ocupados más parados) de nacionales y extranjeros.",
    },
    "lfsa_agaed": {
        "filters": {"age": ["Y25-64"], "sex": ["T"], "isced11": ["ED0-2", "ED3_4", "ED5-8", "TOTAL"], "unit": ["THS_PER"]},
        "label": "Población activa por nivel educativo ({age}), Eurostat", "unit_label": "Miles de personas",
        "definition": "Población activa de 25 a 64 años por nivel educativo (CINE 2011); con lfsa_urgaed permite calcular el paro que tendría España con la composición educativa europea.",
    },
    "earn_ses_pub1s": {
        "filters": {"sex": ["T"], "unit": ["PC"], "sizeclas": ["GE10"]},
        "label": "Asalariados con salario bajo (menos de 2/3 del salario horario mediano nacional), Eurostat SES", "unit_label": "% de los asalariados",
        "definition": "Encuesta de Estructura Salarial europea (cada cuatro años), empresas de 10 o más asalariados, sin aprendices.",
    },
    "nama_10r_2nlp": {
        "geo_level": ["nuts2", "country", "aggregate"],
        "filters": {"na_item": ["NLPR_HW"], "unit": ["EUR"]},
        "label": "Productividad nominal por hora trabajada por región NUTS 2, Eurostat", "unit_label": "Euros por hora",
        "definition": "VAB nominal por hora trabajada en cada región (cuentas regionales).",
    },
    "nama_10r_2lp10": {
        "geo_level": ["nuts2", "country", "aggregate"],
        "filters": {"nace_r2": ["TOTAL"], "na_item": ["D1_SAL_HW"], "unit": ["EUR"]},
        "label": "Remuneración de asalariados por hora trabajada por región NUTS 2, Eurostat", "unit_label": "Euros por hora",
        "definition": "Remuneración de asalariados (sueldos y cotizaciones de la empresa) por hora trabajada por los asalariados, cuentas regionales.",
    },
    "earn_nt_net": {
        "filters": {"currency": ["EUR", "PPS"], "estruct": ["NET", "GRS"], "ecase": ["P1_NCH_AW100", "P1_NCH_AW67", "CPL_CH2_AW100"]},
        "label": "Ingresos anuales netos y brutos de un asalariado tipo, Eurostat (modelo impuestos-prestaciones OCDE)", "unit_label": "Euros o PPS al año",
        "definition": "Ingresos de un trabajador a tiempo completo del sector empresarial: P1_NCH_AW100 soltero sin hijos con el salario medio; P1_NCH_AW67 con el 67 %; CPL_CH2_AW100 pareja con dos hijos y un solo sueldo medio. NET = bruto menos IRPF y cotizaciones del trabajador más prestaciones familiares.",
    },
    "earn_mw_cur": {
        "filters": {"currency": ["EUR", "PPS"]},
        "label": "Salario mínimo mensual bruto, Eurostat", "unit_label": "Euros o PPS al mes",
        "definition": "Salario mínimo nacional bruto mensual, a 1 de enero (S1) y 1 de julio (S2). Para España, el SMI en 12 pagas (prorrateando las extraordinarias). PPS: paridad de poder de compra.",
        "geos": ["ES", "DE", "FR", "PT", "EL", "NL", "IE"],
    },
    "ilc_iw01": {
        "filters": {"wstatus": ["EMP"], "sex": ["T"], "age": ["Y_GE18"], "unit": ["PC"]},
        "label": "Tasa de riesgo de pobreza de los ocupados (18 y más años), Eurostat EU-SILC", "unit_label": "% de los ocupados",
        "definition": "Ocupados que viven en hogares con ingresos equivalentes por debajo del 60 % de la mediana nacional (después de transferencias). La renta se refiere al año anterior al de la encuesta.",
    },
    "prc_hicp_aind": {
        "filters": {"unit": ["INX_A_AVG"], "coicop": ["CP00"]},
        "label": "Índice de precios de consumo armonizado, media anual (2015 = 100), Eurostat", "unit_label": "Índice 2015 = 100",
        "definition": "IPCA general; se usa para expresar los ingresos netos en euros constantes.",
    },
    "lmp_ind_exp": {
        "base": "https://webgate.ec.europa.eu/empl/redisstat/api/dissemination/statistics/1.0/data",
        "filters": {"unit": ["PPS_PWW", "PC_GDP"], "lmp_type": ["1", "TOT2_7", "TOT8_9", "TOT1_9"], "exptype": ["XTOT"]},
        "label": "Gasto en políticas de mercado de trabajo, Comisión Europea (DG EMPL, base LMP)", "unit_label": "PPS por persona que quiere trabajar, o % del PIB",
        "definition": "Base de datos LMP: tipo 1 = servicios de empleo; TOT2_7 = medidas activas (formación, incentivos a la contratación, empleo protegido, creación directa de empleo, emprendimiento); TOT8_9 = medidas pasivas (prestaciones por desempleo y jubilación anticipada). PPS_PWW: paridad de poder de compra por persona que quiere trabajar (parados más inactivos disponibles).",
        "source_page": "https://webgate.ec.europa.eu/empl/redisstat/databrowser/explore/all/lmp?lang=en",
    },
    "lmp_ind_actru": {
        "base": "https://webgate.ec.europa.eu/empl/redisstat/api/dissemination/statistics/1.0/data",
        "filters": {"unit": ["RT"], "age": ["TOTAL"], "sex": ["T"], "regis_es": ["REG_UNE"], "lmp_type": ["TOT2_7"]},
        "label": "Activación de los parados registrados: participantes en medidas activas por cada 100 parados registrados (DG EMPL)", "unit_label": "Participantes por cada 100 parados registrados",
        "definition": "Participantes en medidas activas (tipos 2 a 7) que estaban registrados como parados, por cada 100 parados registrados más esos participantes.",
        "source_page": "https://webgate.ec.europa.eu/empl/redisstat/databrowser/explore/all/lmp?lang=en",
    },
    "nama_10_lp_ulc": {
        "filters": {"na_item": ["RLPR_HW"], "unit": ["I15"]},
        "label": "Productividad real del trabajo por hora trabajada (índice 2015 = 100), Eurostat",
        "unit_label": "Índice 2015 = 100",
        "definition": "PIB en volumen (encadenado) por hora trabajada, contabilidad nacional SEC 2010.",
    },
}


def eurostat_url(dataset: str) -> str:
    cfg = EUROSTAT_DATASETS[dataset]
    level = cfg.get("geo_level")
    levels = [level] if isinstance(level, str) else (level or [])
    params: list[tuple[str, str]] = [("geoLevel", lv) for lv in levels] if levels else [("geo", g) for g in cfg.get("geos", EUROSTAT_GEOS)]
    for dim, values in EUROSTAT_DATASETS[dataset]["filters"].items():
        params.extend((dim, v) for v in values)
    return f"{cfg.get('base', EUROSTAT_BASE)}/{dataset}?" + urllib.parse.urlencode(params)


def lower_jsonstat(data: dict[str, Any]) -> dict[str, Any]:
    """DG EMPL's redisstat names dimensions in upper case (GEO, TIME_PERIOD); map them to Eurostat's (geo, time)."""
    rename = {d: ("time" if d == "TIME_PERIOD" else d.lower()) for d in data["id"]}
    return {**data, "id": [rename[d] for d in data["id"]], "dimension": {rename.get(k, k): v for k, v in data["dimension"].items()}}


def parse_eurostat(dataset: str) -> Callable[[Raw], Iterable[Batch]]:
    """JSON-stat 2.0: one indicator per combination of non-geo dimensions, one series per geo."""

    def parse(raw: Raw) -> Iterable[Batch]:
        data = lower_jsonstat(raw.data)
        dims, sizes = data["id"], data["size"]
        strides = [1] * len(dims)
        for i in range(len(dims) - 2, -1, -1):
            strides[i] = strides[i + 1] * sizes[i + 1]
        index = {d: data["dimension"][d]["category"]["index"] for d in dims}
        labels = {d: data["dimension"][d]["category"].get("label", {}) for d in dims}
        fixed = [d for d in dims if d not in ("geo", "time", "freq")]
        combos: list[dict[str, str]] = [{}]
        for d in fixed:
            combos = [{**c, d: code} for c in combos for code in index[d]]
        cfg = EUROSTAT_DATASETS[dataset]
        status = data.get("status", {})
        for combo in combos:
            series = []
            for geo, gi in sorted(index["geo"].items(), key=lambda kv: kv[1]):
                obs = []
                for year, ti in sorted(index["time"].items(), key=lambda kv: kv[1]):
                    coords = {**combo, "geo": geo, "time": year, "freq": next(iter(index["freq"]), "A") if "freq" in index else "A"}
                    flat = sum(strides[i] * (index[d][coords[d]] if d in coords else 0) for i, d in enumerate(dims))
                    value = data["value"].get(str(flat))
                    if value is not None:
                        obs.append({"period": year, "value": value, "pointer": pointer("value", flat), "cell_index": flat,
                                    "status": status.get(str(flat))})
                if obs:
                    key = "|".join([dataset, *(combo[d] for d in fixed), geo])
                    item = area_series(key, geo, {**combo, "geo": geo}, obs)
                    if geo not in AREA_META:
                        item.update(geo_name=labels["geo"].get(geo, geo), geo_system="NUTS", geo_level="nuts2" if len(geo) == 4 else "nuts")
                    series.append(item)
            code = ".".join(combo[d] for d in fixed)
            age = combo.get("age", "").replace("Y", "").replace("-", "–")
            dg_empl = "base" in cfg
            yield {
                "source_id": "dg_empl_lmp" if dg_empl else "eurostat_sdmx", "dataset_code": dataset, "indicator_code": code,
                "frequency_code": "S" if dataset == "earn_mw_cur" else "A",
                "frequency_label": "Semestral" if dataset == "earn_mw_cur" else "Anual",
                "unit_code": combo.get("unit", combo.get("currency", "PC")), "unit_label": cfg["unit_label"],
                "label": cfg["label"].format(age=age), "definition": cfg["definition"],
                "methodology_url": cfg.get("source_page") or f"https://ec.europa.eu/eurostat/cache/metadata/en/{dataset.removesuffix('_h')}_esms.htm",
                "source_url": cfg.get("source_page") or f"https://ec.europa.eu/eurostat/databrowser/view/{dataset}/default/table",
                "source_updated_at": data.get("updated"),
            }, series

    return parse


INE_SERIES = {
    "EPA452434": ("Tasa de paro, total nacional, 16 y más años (EPA)", "PC_ACT", "% de la población activa"),
    "EPA452436": ("Tasa de paro, menores de 25 años (EPA)", "PC_ACT", "% de la población activa"),
    "EPA416745": ("Asalariados, total (EPA)", "THS_PER", "Miles de personas"),
    "EPA416746": ("Asalariados con contrato indefinido, total (EPA)", "THS_PER", "Miles de personas"),
    "IPT239": ("Índice de Precios del Trabajo, total nacional (composición fija)", "IDX", "Índice"),
    "EPA416748": ("Asalariados con contrato indefinido discontinuo (fijos discontinuos, EPA)", "THS_PER", "Miles de personas"),
    "EPA416749": ("Asalariados con contrato temporal (EPA)", "THS_PER", "Miles de personas"),
}
INE_QUARTER = {19: 1, 20: 2, 21: 3, 22: 4}
INE_TABLES = {
    "66237": {"label": "Salario medio mensual por decil del empleo principal (EPA)", "unit": "EUR_MONTH", "unit_label": "Euros brutos al mes",
              "keep": lambda name: name.startswith("Total.") and "Dato base" in name},
    "28191": {"label": "Ganancia anual por trabajador: media y percentiles por comunidad autónoma (Encuesta Anual de Estructura Salarial)",
              "unit": "EUR_YEAR", "unit_label": "Euros brutos al año", "keep": lambda name: name.startswith("Ambos sexos.") and "Dato base" in name},
}


def parse_ine_table(table: str) -> Callable[[Raw], Iterable[Batch]]:
    """A whole INE Tempus table (annual): one series per COD, name kept as dimension."""
    cfg = INE_TABLES[table]

    def parse(raw: Raw) -> Iterable[Batch]:
        series = []
        for si, item in enumerate(raw.data):
            name = item.get("Nombre", "").strip()
            if not cfg["keep"](name):
                continue
            obs = [
                {"period": str(row["Anyo"]), "value": row["Valor"], "pointer": pointer(si, "Data", i, "Valor"), "cell_index": i}
                for i, row in enumerate(item.get("Data", []))
                if row.get("Valor") is not None and not row.get("Secreto")
            ]
            parts = [p.strip() for p in name.rstrip(".").split(".")]
            region = parts[1] if table == "28191" else "Total Nacional"
            geo = "ESP" if region == "Total Nacional" else region
            entry = area_series(f"INE|{table}|{item['COD']}", geo, {"cod": item["COD"], "nombre": name}, obs)
            if geo != "ESP":
                entry.update(geo_name=region, geo_system="INE-CCAA", geo_level="region")
            series.append(entry)
        yield {
            "source_id": "ine_epa_tempus" if table == "66237" else "ine_eaes_tempus", "dataset_code": f"INE_{table}",
            "indicator_code": table, "frequency_code": "A", "frequency_label": "Anual", "unit_code": cfg["unit"],
            "unit_label": cfg["unit_label"], "label": cfg["label"],
            "definition": "Tabla completa de INE Tempus; cada serie conserva su código y nombre oficial.",
            "methodology_url": f"https://www.ine.es/jaxiT3/Tabla.htm?t={table}",
            "source_url": f"https://www.ine.es/jaxiT3/Tabla.htm?t={table}",
        }, series

    return parse


def parse_ine(code: str) -> Callable[[Raw], Iterable[Batch]]:
    def parse(raw: Raw) -> Iterable[Batch]:
        label, unit, unit_label = INE_SERIES[code]
        annual = code.startswith("IPT")
        obs = [
            {"period": str(row["Anyo"]) if annual else f"{row['Anyo']}T{INE_QUARTER[row['FK_Periodo']]}", "value": row["Valor"],
             "pointer": pointer("Data", i, "Valor"), "cell_index": i}
            for i, row in enumerate(raw.data["Data"])
            if row.get("Valor") is not None and not row.get("Secreto") and (annual or row.get("FK_Periodo") in INE_QUARTER)
        ]
        yield {
            "source_id": "ine_ipt_tempus" if annual else "ine_epa_tempus", "dataset_code": "IPT" if annual else "EPA",
            "indicator_code": code, "frequency_code": "A" if annual else "Q",
            "frequency_label": "Anual" if annual else "Trimestral", "unit_code": unit, "unit_label": unit_label,
            "label": label, "definition": raw.data.get("Nombre", "").strip(),
            "methodology_url": "https://www.ine.es/dyngs/INEbase/es/operacion.htm?c=Estadistica_C&cid=1254736176918&menu=metodologia&idp=1254735976595",
            "source_url": f"https://www.ine.es/consul/serie.do?s={code}",
        }, [area_series(f"INE|{code}", "ESP", {"cod": code}, obs)]
    return parse


TAX_WAGES_DATASET = "DSD_TAX_WAGES_COMP@DF_TW_COMP"
TAX_WAGES_DIMS = {"MEASURE": ["AV_TW"], "HOUSEHOLD_TYPE": ["S_C0"], "INCOME_PRINCIPAL": ["AW100", "AW67"]}


def parse_tax_wages(raw: Raw) -> Iterable[Batch]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for doc_index, doc in enumerate(raw.data["series"]["docs"]):
        area, measure, unit, household, income, spouse, freq = doc["series_code"].split(".")
        if area not in OECD_AREAS or measure != "AV_TW" or household != "S_C0":
            continue
        obs = [
            {"period": p, "value": v, "pointer": pointer("series", "docs", doc_index, "value", i), "cell_index": i}
            for i, (p, v) in enumerate(zip(doc["period"], doc["value"])) if isinstance(v, (int, float))
        ]
        dims = {"REF_AREA": area, "MEASURE": measure, "UNIT_MEASURE": unit, "HOUSEHOLD_TYPE": household,
                "INCOME_PRINCIPAL": income, "INCOME_SPOUSE": spouse, "FREQ": freq}
        grouped.setdefault(income, []).append(area_series(f"{TAX_WAGES_DATASET}|{doc['series_code']}", area, dims, obs))
    for income, series in sorted(grouped.items()):
        pct = income.removeprefix("AW")
        yield {
            "source_id": "oecd_taxing_wages", "dataset_code": TAX_WAGES_DATASET,
            "indicator_code": f"AV_TW.S_C0.{income}", "frequency_code": "A", "frequency_label": "Anual",
            "unit_code": "PT_COS_LB", "unit_label": "% del coste laboral",
            "label": f"Cuña fiscal media, soltero sin hijos con el {pct} % del salario medio (% del coste laboral)",
            "definition": "IRPF + cotizaciones del trabajador + cotizaciones de la empresa, menos prestaciones en "
            "efectivo, sobre el coste laboral total (OCDE Taxing Wages). Leído de la réplica DBnomics porque "
            "sdmx.oecd.org responde HTTP 403 al acceso por script.",
            "methodology_url": "https://www.oecd.org/en/publications/taxing-wages_20725124.html",
            "source_url": f"https://db.nomics.world/OECD/{TAX_WAGES_DATASET}",
        }, series


PDB_DATASET = "DSD_PDB@DF_PDB"


def parse_pdb(raw: Raw) -> Iterable[Batch]:
    series = []
    for doc_index, doc in enumerate(raw.data["series"]["docs"]):
        parts = doc["series_code"].split(".")
        area, freq, measure, activity, unit, price, transform = parts[:7]
        if area not in PDB_AREAS or unit != "USD_PPP_H" or price != "LR" or transform != "N":
            continue
        obs = [
            {"period": p, "value": v, "pointer": pointer("series", "docs", doc_index, "value", i), "cell_index": i}
            for i, (p, v) in enumerate(zip(doc["period"], doc["value"])) if isinstance(v, (int, float))
        ]
        series.append(area_series(f"{PDB_DATASET}|{doc['series_code']}", area, {"series_code": doc["series_code"]}, obs))
    yield {
        "source_id": "oecd_productivity", "dataset_code": PDB_DATASET, "indicator_code": "GDPHRS._T.LR",
        "frequency_code": "A", "frequency_label": "Anual", "unit_code": "USD_PPP_H",
        "unit_label": "Dólares por hora, PPA, volumen encadenado (rebasado)",
        "label": "PIB por hora trabajada, dólares PPA a precios constantes (OCDE)",
        "definition": "OCDE Productivity Database: PIB en volumen convertido con paridades de poder de compra, "
        "por hora trabajada. Permite comparar niveles entre países, no solo crecimientos.",
        "methodology_url": "https://www.oecd.org/en/data/datasets/productivity-database.html",
        "source_url": f"https://db.nomics.world/OECD/{PDB_DATASET}",
    }, series


MIN_WAGE_DATASET = "DSD_EARNINGS@MIN2AVE"
MIN_WAGE_AREAS = ["ESP", "DEU", "FRA", "PRT", "GRC", "NLD", "IRL", "GBR", "USA"]


def parse_min_wage(raw: Raw) -> Iterable[Batch]:
    series = []
    for doc_index, doc in enumerate(raw.data["series"]["docs"]):
        parts = doc["series_code"].split(".")
        area = parts[0]
        if area not in MIN_WAGE_AREAS or "MEDIAN" not in parts:
            continue
        obs = [
            {"period": p, "value": v, "pointer": pointer("series", "docs", doc_index, "value", i), "cell_index": i}
            for i, (p, v) in enumerate(zip(doc["period"], doc["value"])) if isinstance(v, (int, float))
        ]
        item = area_series(f"{MIN_WAGE_DATASET}|{doc['series_code']}", area, {"series_code": doc["series_code"]}, obs)
        if area not in AREA_META:
            item.update(geo_name=area, geo_system="ISO3166-1-alpha-3", geo_level="country")
        series.append(item)
    yield {
        "source_id": "oecd_earnings", "dataset_code": MIN_WAGE_DATASET, "indicator_code": "MR_WG_FT.MEDIAN",
        "frequency_code": "A", "frequency_label": "Anual", "unit_code": "PT_WG_MEDIAN",
        "unit_label": "% del salario mediano a tiempo completo",
        "label": "Salario mínimo en % del salario mediano de los trabajadores a tiempo completo (OCDE)",
        "definition": "OCDE Earnings: salario mínimo legal dividido por el salario mediano bruto de los asalariados a "
        "tiempo completo. Italia no tiene salario mínimo legal general.",
        "methodology_url": "https://www.oecd.org/en/data/datasets/minimum-wages-relative-to-median-wages.html",
        "source_url": f"https://db.nomics.world/OECD/{MIN_WAGE_DATASET}",
    }, series


IMW_DATASET = "DSD_TAXBEN_IMW@DF_IMW"
IMW_SERIES = "{area}.NFI.PT_INC_DISP_HH_TP_REF_WG_MEDIAN.S_C0.Y4_6._Z.NO.NO.FT_ISICCK.MW_DATE.A"


def parse_net_min_wage(raw: Raw) -> Iterable[Batch]:
    series = []
    for doc_index, doc in enumerate(raw.data["series"]["docs"]):
        area = doc["series_code"].split(".")[0]
        if doc["series_code"] != IMW_SERIES.format(area=area):
            continue
        obs = [
            {"period": p, "value": v, "pointer": pointer("series", "docs", doc_index, "value", i), "cell_index": i}
            for i, (p, v) in enumerate(zip(doc["period"], doc["value"])) if isinstance(v, (int, float))
        ]
        item = area_series(f"{IMW_DATASET}|{doc['series_code']}", area, {"series_code": doc["series_code"]}, obs)
        if area not in AREA_META:
            item.update(geo_name=area, geo_system="ISO3166-1-alpha-3", geo_level="country")
        series.append(item)
    yield {
        "source_id": "oecd_taxben", "dataset_code": IMW_DATASET, "indicator_code": "NFI.MINW.S_C0.vs_MEDIAN",
        "frequency_code": "A", "frequency_label": "Anual", "unit_code": "PT_NET_MEDIAN",
        "unit_label": "% de la renta neta de un soltero con el salario mediano",
        "label": "Renta neta de un soltero sin hijos con el salario mínimo a tiempo completo, en % de la de un soltero con el salario mediano (OCDE TaxBEN)",
        "definition": "Modelo de impuestos y prestaciones de la OCDE: salario mínimo bruto menos impuestos y cotizaciones del "
        "trabajador más prestaciones en efectivo, sin ayudas de vivienda ni asistencia social; referencia: salario mediano "
        "a tiempo completo (FT_ISICCK), salario mínimo vigente a la fecha (MW_DATE).",
        "methodology_url": "https://www.oecd.org/en/topics/sub-issues/minimum-wages.html",
        "source_url": f"https://db.nomics.world/OECD/{IMW_DATASET}",
    }, series


OLAB_DATASET = "DSD_OLAB@DF_OIALAB_INDIC"


def parse_registered(raw: Raw) -> Iterable[Batch]:
    series = []
    for doc_index, doc in enumerate(raw.data["series"]["docs"]):
        if doc["series_code"] != "ESP.REG_UNE.PS._Z.N.S1.A":
            continue
        obs = [
            {"period": p, "value": v, "pointer": pointer("series", "docs", doc_index, "value", i), "cell_index": i}
            for i, (p, v) in enumerate(zip(doc["period"], doc["value"])) if isinstance(v, (int, float))
        ]
        series.append(area_series(f"{OLAB_DATASET}|{doc['series_code']}", "ESP", {"series_code": doc["series_code"]}, obs))
    yield {
        "source_id": "oecd_registered_unemployment", "dataset_code": OLAB_DATASET, "indicator_code": "REG_UNE.A",
        "frequency_code": "A", "frequency_label": "Anual (media de meses)", "unit_code": "PERSONS", "unit_label": "Personas",
        "label": "Paro registrado en los servicios públicos de empleo (SEPE), media anual (OCDE)",
        "definition": "Demandantes de empleo parados inscritos en las oficinas públicas de empleo, según la OCDE "
        "(Infra-annual labour statistics), que recoge la serie del SEPE/Ministerio de Trabajo. Excluye a los demandantes "
        "con relación laboral (entre ellos, fijos discontinuos inactivos).",
        "methodology_url": "https://www.sepe.es/HomeSepe/que-es-el-sepe/estadisticas/datos-avance/paro.html",
        "source_url": f"https://db.nomics.world/OECD/{OLAB_DATASET}",
    }, series


API_SOURCES: list[tuple[str, str, Callable[[Raw], Iterable[Batch]]]] = [
    *[(f"ameco_{code.lower()}.json", dbnomics_series_url("AMECO", code), parse_ameco(code)) for code in AMECO_CODES],
    *[(f"eurostat_{ds}.json", eurostat_url(ds), parse_eurostat(ds)) for ds in EUROSTAT_DATASETS],
    *[
        (f"ine_{code}.json", f"https://servicios.ine.es/wstempus/js/ES/DATOS_SERIE/{code}?nult=400", parse_ine(code))
        for code in INE_SERIES
    ],
    *[
        (f"ine_tabla_{table}.json", f"https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/{table}?nult=40", parse_ine_table(table))
        for table in INE_TABLES
    ],
    ("oecd_taxing_wages_dbnomics.json", dbnomics_series_url("OECD", TAX_WAGES_DATASET, TAX_WAGES_DIMS), parse_tax_wages),
    (
        "oecd_pdb_gdphrs_dbnomics.json",
        dbnomics_series_url("OECD", PDB_DATASET, {"MEASURE": ["GDPHRS"], "REF_AREA": PDB_AREAS, "UNIT_MEASURE": ["USD_PPP_H"]}),
        parse_pdb,
    ),
    (
        "oecd_min2ave_dbnomics.json",
        dbnomics_series_url("OECD", MIN_WAGE_DATASET, {"REF_AREA": MIN_WAGE_AREAS}),
        parse_min_wage,
    ),
    (
        "oecd_taxben_imw_dbnomics.json",
        dbnomics_series_url("OECD", IMW_DATASET, {"REF_AREA": ["ESP", "DEU", "FRA", "PRT", "GRC", "NLD", "IRL"], "MEASURE": ["NFI"], "HOUSEHOLD_TYPE": ["S_C0"]}),
        parse_net_min_wage,
    ),
    (
        "oecd_olab_reg_une_esp_dbnomics.json",
        dbnomics_series_url("OECD", OLAB_DATASET, {"REF_AREA": ["ESP"], "MEASURE": ["REG_UNE"], "FREQ": ["A"]}),
        parse_registered,
    ),
]


# ---------------------------------------------------------------- non-JSON official files (PC-Axis, xlsx)

class RawFile:
    def __init__(self, name: str, url: str, payload: bytes, retrieved_at: str):
        self.name, self.url, self.payload, self.retrieved_at = name, url, payload, retrieved_at
        self.sha256 = sha256_bytes(payload)
        self.path = FILES_DIR / name


# Hosts whose TLS chain is incomplete for Python's verifier (curl/macOS accept it); integrity is kept by sha256.
INSECURE_TLS_HOSTS = {"www.mites.gob.es"}


def fetch_file(name: str, url: str, offline: bool) -> RawFile:
    path = FILES_DIR / name
    meta_path = FILES_DIR / f"{name}.meta.json"
    if not offline:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        host = urllib.parse.urlparse(url).hostname
        context = ssl._create_unverified_context() if host in INSECURE_TLS_HOSTS else None  # noqa: S323 - per-host
        with urllib.request.urlopen(req, timeout=180, context=context) as resp:
            payload = resp.read()
        if payload[:200].lstrip().lower().startswith((b"<!doctype", b"<html")):
            raise ValueError(f"{url} returned HTML instead of a data file")
        FILES_DIR.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        meta_path.write_text(canonical_json({"url": url, "retrieved_at": now_iso()}), encoding="utf-8")
    if not path.exists():
        raise FileNotFoundError(f"missing raw cache {rel(path)}; run without --offline")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return RawFile(name, meta["url"], path.read_bytes(), meta["retrieved_at"])


def parse_px(payload: bytes) -> tuple[list[tuple[str, list[str]]], list[str]]:
    """PC-Axis: returns ([(variable, values)] in STUB+HEADING order, flat DATA tokens). The last variable varies fastest."""
    text = payload.decode("cp1252")
    head, data = text.split("DATA=", 1)
    def keyword(name: str) -> list[str]:
        m = re.search(rf"^{name}=(.*?);", head, re.S | re.M)
        return re.findall(r'"(.*?)"', m.group(1)) if m else []
    values = {m.group(1): re.findall(r'"(.*?)"', m.group(2)) for m in re.finditer(r'^VALUES\("(.*?)"\)=(.*?);', head, re.S | re.M)}
    order = keyword("STUB") + keyword("HEADING")
    tokens = re.findall(r'"[^"]*"|[^\s;]+', data.split(";")[0])
    return [(var, values[var]) for var in order], tokens


def px_cell(dims: list[tuple[str, list[str]]], tokens: list[str], coords: dict[str, str]) -> tuple[int, float | None]:
    flat = 0
    for var, vals in dims:
        flat = flat * len(vals) + vals.index(coords[var])
    token = tokens[flat].strip('"')
    try:
        return flat, float(token)
    except ValueError:
        return flat, None


def xlsx_sheet(payload: bytes, sheet_name: str) -> dict[str, Any]:
    """Minimal xlsx reader (stdlib): {cell_ref: value} for one sheet, shared strings resolved."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
          "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
          "p": "http://schemas.openxmlformats.org/package/2006/relationships"}
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            for si in ET.fromstring(zf.read("xl/sharedStrings.xml")).findall("m:si", ns):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{ns['m']}}}t")))
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rid = next(sh.get(f"{{{ns['r']}}}id") for sh in wb.find("m:sheets", ns) if sh.get("name") == sheet_name)
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        target = next(rel.get("Target") for rel in rels.findall("p:Relationship", ns) if rel.get("Id") == rid)
        sheet = ET.fromstring(zf.read("xl/" + target.lstrip("/").removeprefix("xl/")))
    cells: dict[str, Any] = {}
    for c in sheet.iter(f"{{{ns['m']}}}c"):
        v = c.find("m:v", ns)
        if v is None:
            continue
        cells[c.get("r")] = shared[int(v.text)] if c.get("t") == "s" else v.text
    return cells


def xlsx_rows(cells: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    for ref, value in cells.items():
        m = re.match(r"([A-Z]+)(\d+)", ref)
        rows.setdefault(int(m.group(2)), {})[m.group(1)] = value
    return rows


SS_PX = "https://w6.seg-social.es/PXWeb/Resources/PX/Databases/"
SS_AFFILIATES = SS_PX + "Afiliados%20en%20alta%20laboral/Afiliados%20Medios/07m.%20Afiliados%20R.%20GENERAL%20por%20tipo%20de%20contrato%20y%20jornada,%20tramos%20de%20edad%20y%20sexo.px"
SS_DAYS = SS_PX + "Dias%20cotizados/Datos%20de%20cotizantes%20y%20d%C3%ADas%20de%20cotizaci%C3%B3n%20CNAE09%20(hasta%20dic-2025).px"
AFFILIATE_TYPES = {
    "TODAS LAS MODALIDADES DE CONTRATOS": "TOTAL",
    "INDEFINIDO-T. Completo": "IND_TC",
    "INDEFINIDO-T. Parcial": "IND_TP",
    "INDEFINIDO-Fijos Discontinuos": "IND_FD",
}
DAY_TYPES = {
    "INDEFINIDO FIJO DISCONTINUO TIEMPO COMPLETO": "FD_TC",
    "INDEFINIDO FIJO DISCONTINUO TIEMPO PARCIAL": "FD_TP",
    "INDEFINIDO TIEMPO COMPLETO": "IND_TC",
    "INDEFINIDO TIEMPO PARCIAL": "IND_TP",
}
DAY_VALUES = {"DÍAS TOTALES": "DIAS_TOTALES", "COTIZANTES": "COTIZANTES"}


def month_label(period: str) -> str:
    return f"{period[:4]}-{period[4:6]}"


def load_ss_affiliates(conn: sqlite3.Connection, raw: RawFile, snapshot_date: str) -> dict[str, int]:
    dims, tokens = parse_px(raw.payload)
    periods = dict(dims)["Periodo"]
    totals = {"releases": 0, "observations": 0}
    for label, code in AFFILIATE_TYPES.items():
        obs = []
        for period in periods:
            flat, value = px_cell(dims, tokens, {"Periodo": period, "tipo contrato": label, "Tramos de edad": "Total Edad", "Sexo": "Total Sexo"})
            if value is not None:
                obs.append({"period": month_label(period), "value": value, "pointer": pointer("DATA", flat), "cell_index": flat})
        counts = load_indicator(conn, {
            "source_id": "seg_social_pxweb", "dataset_code": "afiliados_medios_07m", "indicator_code": code,
            "frequency_code": "M", "frequency_label": "Mensual", "unit_code": "PERSONS", "unit_label": "Afiliados medios",
            "label": f"Afiliados medios al Régimen General, {label}", "extraction_method": "pcaxis_cell",
            "definition": "Media mensual de trabajadores en alta laboral en el Régimen General por tipo de contrato. Un fijo "
            "discontinuo solo figura en alta mientras trabaja: en los periodos de inactividad causa baja.",
            "methodology_url": "https://www.seg-social.es/wps/portal/wss/internet/EstadisticasPresupuestosEstudios/Estadisticas/EST8/EST10",
            "source_url": raw.url,
        }, raw.sha256, len(raw.payload), rel(raw.path), raw.url, snapshot_date, {"retrieved_at": raw.retrieved_at},
            [area_series(f"07m|{code}|ESP", "ESP", {"tipo_contrato": label, "edad": "Total Edad", "sexo": "Total Sexo"}, obs)])
        for k in totals:
            totals[k] += counts[k]
    return totals


def load_ss_days(conn: sqlite3.Connection, raw: RawFile, snapshot_date: str) -> dict[str, int]:
    dims, tokens = parse_px(raw.payload)
    periods = dict(dims)["Periodo"]
    totals = {"releases": 0, "observations": 0}
    for ctype, ccode in DAY_TYPES.items():
        for vlabel, vcode in DAY_VALUES.items():
            obs = []
            for period in periods:
                flat, value = px_cell(dims, tokens, {"Periodo": period, "Género": "TOTAL SEXO", "Sección": "TOTAL SECCION",
                                                     "Tipo de contrato": ctype, "Valores": vlabel})
                if value is not None:
                    obs.append({"period": month_label(period), "value": value, "pointer": pointer("DATA", flat), "cell_index": flat})
            counts = load_indicator(conn, {
                "source_id": "seg_social_pxweb", "dataset_code": "dias_cotizados_cnae09", "indicator_code": f"{ccode}.{vcode}",
                "frequency_code": "M", "frequency_label": "Mensual",
                "unit_code": "DAYS" if vcode != "COTIZANTES" else "PERSONS",
                "unit_label": "Días cotizados en el mes" if vcode != "COTIZANTES" else "Cotizantes con al menos un día en el mes",
                "label": f"{vlabel.capitalize()}, {ctype.lower()}", "extraction_method": "pcaxis_cell",
                "definition": "Días cotizados y cotizantes por tipo de contrato, todas las secciones de actividad. Un cotizante "
                "es quien cotiza al menos un día del mes: los meses sin actividad de un fijo discontinuo no cuentan.",
                "methodology_url": "https://www.seg-social.es/wps/portal/wss/internet/EstadisticasPresupuestosEstudios/Estadisticas",
                "source_url": raw.url,
            }, raw.sha256, len(raw.payload), rel(raw.path), raw.url, snapshot_date, {"retrieved_at": raw.retrieved_at},
                [area_series(f"dias|{ccode}|{vcode}|ESP", "ESP", {"tipo_contrato": ctype, "valores": vlabel}, obs)])
            for k in totals:
                totals[k] += counts[k]
    return totals


MLR_EDITIONS = [2023, 2024, 2025]
MLR_ROWS = {
    "MLR-18": {"Trabajadores fijos discontinuos": "demandantes_fijos_discontinuos", "AMBOS SEXOS (2)": "demandantes_no_parados_total",
               "Ocupados o con relación laboral": "demandantes_con_relacion_laboral"},
    "MLR-25": {"AMBOS SEXOS": "contratos_total", "Fijos discontinuos": "contratos_fijos_discontinuos",
               "Duración indefinida": "contratos_indefinidos", "Duración temporal": "contratos_temporales"},
}


def load_mlr(conn: sqlite3.Connection, edition: int, raw: RawFile, snapshot_date: str) -> dict[str, int]:
    """Anuario MLR: first block (ambos sexos) of MLR-18 and MLR-25, the two absolute-value year columns."""
    totals = {"releases": 0, "observations": 0}
    for sheet, wanted in MLR_ROWS.items():
        rows = xlsx_rows(xlsx_sheet(raw.payload, sheet))
        year_row = next(r for r in sorted(rows) if [str(v).strip() for v in rows[r].values()][:2] == [str(edition - 1), str(edition)])
        year_cols = [col for col, v in sorted(rows[year_row].items(), key=lambda kv: (len(kv[0]), kv[0]))][:2]
        found: dict[str, int] = {}
        for r in sorted(rows):
            if r <= year_row:
                continue
            label = str(rows[r].get("A", "") or next(iter(rows[r].values()), "")).strip()
            label = re.sub(r"\s+", " ", label)
            if label in ("HOMBRES", "HOMBRES (2)"):
                break  # only the first block (ambos sexos)
            if label in wanted and wanted[label] not in found:
                found[wanted[label]] = r
        for code, r in found.items():
            obs = []
            for col, year in zip(year_cols, (edition - 1, edition)):
                value = rows[r].get(col)
                if value not in (None, ""):
                    obs.append({"period": str(year), "value": float(value), "pointer": pointer(sheet, f"{col}{r}"), "cell_index": r})
            counts = load_indicator(conn, {
                "source_id": "mites_anuario", "dataset_code": f"anuario_{edition}_{sheet}", "indicator_code": code,
                "frequency_code": "A", "frequency_label": "Anual (media o total del año)", "unit_code": "PERSONS" if sheet == "MLR-18" else "CONTRACTS",
                "unit_label": "Personas, media anual" if sheet == "MLR-18" else "Contratos registrados en el año",
                "label": f"{code.replace('_', ' ')} (Anuario {edition}, {sheet})", "extraction_method": "xlsx_cell",
                "definition": "MLR-18: demandantes de empleo no parados, media anual (los fijos discontinuos sin actividad que se "
                "inscriben figuran aquí, no como parados). MLR-25: contratos registrados en el año por modalidad.",
                "methodology_url": "https://www.mites.gob.es/es/estadisticas/anuarios/",
                "source_url": raw.url,
            }, raw.sha256, len(raw.payload), rel(raw.path), raw.url, snapshot_date, {"retrieved_at": raw.retrieved_at, "edition": edition},
                [area_series(f"anuario_{edition}|{sheet}|{code}|ESP", "ESP", {"sheet": sheet, "row_label": code}, obs)])
            for k in totals:
                totals[k] += counts[k]
    return totals


# ---------------------------------------------------------------- curated events

def load_events(conn: sqlite3.Connection, snapshot_date: str) -> dict[str, int]:
    path = MANUAL_DIR / "events_es.json"
    if not path.exists():
        return {"releases": 0, "observations": 0, "missing": 1}
    payload = path.read_bytes()
    data = json.loads(payload)
    obs = []
    for index, event in enumerate(data.get("events", [])):
        if not event.get("source_url"):
            raise ValueError(f"event {event.get('id')!r} has no citation")
        obs.append({
            "period": event["date"], "value": event["label"], "start": event["date"], "end": event["date"],
            "interval_kind": "event", "pointer": pointer("events", index, "label"), "cell_index": index,
            "evidence_url": event["source_url"], "raw": event, "status": event.get("kind"),
            "status_labels": [{"code": event.get("kind"), "label": event.get("kind")}],
        })
    definition = {
        "source_id": "vclc_employment_events", "dataset_code": "events_es", "indicator_code": "labour_events",
        "frequency_code": "EVENT", "frequency_label": "Por hecho", "unit_code": "TEXT", "unit_label": "Texto",
        "label": "Reformas laborales y rupturas de serie de la EPA", "extraction_method": "curated_citation",
        "definition": "Cada fila cita la norma o la nota metodológica que la respalda.",
        "methodology_url": "https://votaconlachola.org/visualizaciones/empleo/#metodo",
        "source_url": "https://www.boe.es/",
    }
    return load_indicator(
        conn, definition, sha256_bytes(payload), len(payload), rel(path), definition["source_url"], snapshot_date,
        {"gaps": data.get("gaps", []), "blocked_hosts": data.get("blocked_hosts", [])},
        [area_series("events_es|ESP", "ESP", {"kind": "labour_events"}, obs)],
    )


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
                report["indicators"][f"{definition['source_id']}:{definition['dataset_code']}:{definition['indicator_code']}"] = counts
        report["seg_social_affiliates"] = load_ss_affiliates(conn, fetch_file("ss_afiliados_07m.px", SS_AFFILIATES, args.offline), args.snapshot_date)
        report["seg_social_days"] = load_ss_days(conn, fetch_file("ss_dias_cotizados_cnae09.px", SS_DAYS, args.offline), args.snapshot_date)
        for edition in MLR_EDITIONS:
            url = f"https://www.mites.gob.es/ficheros/ministerio/estadisticas/anuarios/{edition}/MLR/MLR.xlsx"
            report[f"anuario_{edition}"] = load_mlr(conn, edition, fetch_file(f"mites_anuario_{edition}_MLR.xlsx", url, args.offline), args.snapshot_date)
        report["events"] = load_events(conn, args.snapshot_date)
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk:
        raise SystemExit(f"foreign_key_check failed: {fk[:5]}")
    conn.close()
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
