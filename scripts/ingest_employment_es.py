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
import json
import sqlite3
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

DEFAULT_DB = REPO_ROOT / "etl/data/staging/employment-es.db"
RAW_DIR = REPO_ROOT / "etl/data/raw/employment/apis"
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
                obs.get("interval_kind", "calendar_quarter" if "T" in period else "calendar_year"), value, text,
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


AMECO_CODES = {
    "ZUTN": ("Tasa de paro (% de la población activa), AMECO", "Tasa de paro armonizada por la Comisión Europea a partir de las encuestas de población activa nacionales (para España, la EPA)."),
    "ZNAWRU": ("NAWRU: paro compatible con salarios estables (% de la población activa), AMECO", "Estimación de la Comisión Europea del paro estructural (tasa de paro que no acelera los salarios), obtenida con su modelo de función de producción. Es una estimación de modelo, no una observación."),
}


def parse_ameco(code: str) -> Callable[[Raw], Iterable[Batch]]:
    def parse(raw: Raw) -> Iterable[Batch]:
        series = []
        for doc_index, doc in enumerate(raw.data["series"]["docs"]):
            geo = doc["series_code"].split(".")[0]
            if geo not in AMECO_GEOS:
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
        label, definition = AMECO_CODES[code]
        yield {
            "source_id": "ameco_dbnomics", "dataset_code": code, "indicator_code": code, "frequency_code": "A",
            "frequency_label": "Anual", "unit_code": "PC_ACT", "unit_label": "% de la población activa",
            "label": label, "definition": definition,
            "methodology_url": "https://economy-finance.ec.europa.eu/economic-research-and-databases/economic-databases/ameco-database_en",
            "source_url": f"https://db.nomics.world/AMECO/{code}",
        }, series
    return parse


EUROSTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
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
    "nama_10_lp_ulc": {
        "filters": {"na_item": ["RLPR_HW"], "unit": ["I15"]},
        "label": "Productividad real del trabajo por hora trabajada (índice 2015 = 100), Eurostat",
        "unit_label": "Índice 2015 = 100",
        "definition": "PIB en volumen (encadenado) por hora trabajada, contabilidad nacional SEC 2010.",
    },
}


def eurostat_url(dataset: str) -> str:
    params: list[tuple[str, str]] = [("geo", g) for g in EUROSTAT_GEOS]
    for dim, values in EUROSTAT_DATASETS[dataset]["filters"].items():
        params.extend((dim, v) for v in values)
    return f"{EUROSTAT_BASE}/{dataset}?" + urllib.parse.urlencode(params)


def parse_eurostat(dataset: str) -> Callable[[Raw], Iterable[Batch]]:
    """JSON-stat 2.0: one indicator per combination of non-geo dimensions, one series per geo."""

    def parse(raw: Raw) -> Iterable[Batch]:
        data = raw.data
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
                    coords = {**combo, "geo": geo, "time": year, "freq": "A"}
                    flat = sum(strides[i] * (index[d][coords[d]] if d in coords else 0) for i, d in enumerate(dims))
                    value = data["value"].get(str(flat))
                    if value is not None:
                        obs.append({"period": year, "value": value, "pointer": pointer("value", flat), "cell_index": flat,
                                    "status": status.get(str(flat))})
                if obs:
                    key = "|".join([dataset, *(combo[d] for d in fixed), geo])
                    series.append(area_series(key, geo, {**combo, "geo": geo}, obs))
            code = ".".join(combo[d] for d in fixed)
            age = labels.get("age", {}).get(combo.get("age", ""), combo.get("age", ""))
            yield {
                "source_id": "eurostat_sdmx", "dataset_code": dataset, "indicator_code": code, "frequency_code": "A",
                "frequency_label": "Anual", "unit_code": combo.get("unit", "PC"), "unit_label": cfg["unit_label"],
                "label": cfg["label"].format(age=age), "definition": cfg["definition"],
                "methodology_url": f"https://ec.europa.eu/eurostat/cache/metadata/en/{dataset.removesuffix('_h')}_esms.htm",
                "source_url": f"https://ec.europa.eu/eurostat/databrowser/view/{dataset}/default/table",
                "source_updated_at": data.get("updated"),
            }, series

    return parse


INE_SERIES = {
    "EPA452434": ("Tasa de paro, total nacional, 16 y más años (EPA)", "PC_ACT", "% de la población activa"),
    "EPA452436": ("Tasa de paro, menores de 25 años (EPA)", "PC_ACT", "% de la población activa"),
    "EPA416745": ("Asalariados, total (EPA)", "THS_PER", "Miles de personas"),
    "EPA416748": ("Asalariados con contrato indefinido discontinuo (fijos discontinuos, EPA)", "THS_PER", "Miles de personas"),
    "EPA416749": ("Asalariados con contrato temporal (EPA)", "THS_PER", "Miles de personas"),
}
INE_QUARTER = {19: 1, 20: 2, 21: 3, 22: 4}


def parse_ine(code: str) -> Callable[[Raw], Iterable[Batch]]:
    def parse(raw: Raw) -> Iterable[Batch]:
        label, unit, unit_label = INE_SERIES[code]
        obs = [
            {"period": f"{row['Anyo']}T{INE_QUARTER[row['FK_Periodo']]}", "value": row["Valor"],
             "pointer": pointer("Data", i, "Valor"), "cell_index": i}
            for i, row in enumerate(raw.data["Data"])
            if row.get("Valor") is not None and not row.get("Secreto") and row.get("FK_Periodo") in INE_QUARTER
        ]
        yield {
            "source_id": "ine_epa_tempus", "dataset_code": "EPA", "indicator_code": code, "frequency_code": "Q",
            "frequency_label": "Trimestral", "unit_code": unit, "unit_label": unit_label,
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


API_SOURCES: list[tuple[str, str, Callable[[Raw], Iterable[Batch]]]] = [
    *[(f"ameco_{code.lower()}.json", dbnomics_series_url("AMECO", code), parse_ameco(code)) for code in AMECO_CODES],
    *[(f"eurostat_{ds}.json", eurostat_url(ds), parse_eurostat(ds)) for ds in EUROSTAT_DATASETS],
    *[
        (f"ine_{code}.json", f"https://servicios.ine.es/wstempus/js/ES/DATOS_SERIE/{code}?nult=400", parse_ine(code))
        for code in INE_SERIES
    ],
    ("oecd_taxing_wages_dbnomics.json", dbnomics_series_url("OECD", TAX_WAGES_DATASET, TAX_WAGES_DIMS), parse_tax_wages),
    (
        "oecd_pdb_gdphrs_dbnomics.json",
        dbnomics_series_url("OECD", PDB_DATASET, {"MEASURE": ["GDPHRS"], "REF_AREA": PDB_AREAS, "UNIT_MEASURE": ["USD_PPP_H"]}),
        parse_pdb,
    ),
]


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
        report["events"] = load_events(conn, args.snapshot_date)
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk:
        raise SystemExit(f"foreign_key_check failed: {fk[:5]}")
    conn.close()
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
