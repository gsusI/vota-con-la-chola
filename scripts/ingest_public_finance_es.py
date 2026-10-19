#!/usr/bin/env python3
"""Ingest Spain's long-run public-finance series into SQLite (indicator contract v1 + legal norms).

Boundaries:
- ingest: fetch each source API, keep the raw payload under etl/data/raw/public_finance/apis/ (+ URL, retrieval time);
  `--offline` reuses that cache.
- normalize/load: every series lands in the canonical indicator tables (indicator_definitions -> indicator_releases
  -> indicator_series_versions -> indicator_observation_versions -> indicator_observation_evidence). A new raw
  payload is a new release; each observation is compared with the previous release (unchanged/changed/deleted),
  so later official revisions never overwrite what was observed before. Evidence points at the raw byte (JSON
  pointer + sha256).
- curated legal data: statutory tax rates (etl/data/manual/public_finance/statutory_rates_es.json, one citation per
  change) load as indicators too, with interval_kind='legal_validity'. BOE-derived complexity
  (tax_complexity_es.json from scripts/boe_tax_complexity.py) loads into legal_norms, legal_norm_lineage_edges
  (amending norm -> amended law) and legal_norm_text_metrics.

The published site JSON is derived from this DB by scripts/export_public_viz_fiscal.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
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

DEFAULT_DB = REPO_ROOT / "etl/data/staging/public-finance-es.db"
RAW_DIR = REPO_ROOT / "etl/data/raw/public_finance/apis"
MANUAL_DIR = REPO_ROOT / "etl/data/manual/public_finance"
USER_AGENT = "Mozilla/5.0 (compatible; vota-con-la-chola-etl/1.0; +https://votaconlachola.org)"
EXTRACTOR_VERSION = "ingest_public_finance_es/1"
NUL = "\x00"

LOCAL_SOURCES: dict[str, dict[str, str]] = {
    "imf_fpp": {
        "name": "FMI - Public Finances in Modern History (DataMapper FPP)",
        "scope": "finanzas_publicas",
        "default_url": "https://www.imf.org/external/datamapper/api/v1/",
        "format": "json",
    },
    "oecd_revenue_statistics": {
        "name": "OCDE - Revenue Statistics, tablas comparativas (réplica DBnomics)",
        "scope": "finanzas_publicas",
        "default_url": "https://db.nomics.world/OECD/DSD_REV_COMP_OECD@DF_RSOECD",
        "format": "json",
    },
    "oecd_income_distribution": {
        "name": "OCDE - Income Distribution Database (réplica DBnomics)",
        "scope": "finanzas_publicas",
        "default_url": "https://db.nomics.world/OECD/DSD_WISE_IDD@DF_IDD",
        "format": "json",
    },
    "oecd_taxing_wages": {
        "name": "OCDE - Taxing Wages, tablas comparativas (réplica DBnomics)",
        "scope": "finanzas_publicas",
        "default_url": "https://db.nomics.world/OECD/DSD_TAX_WAGES_COMP@DF_TW_COMP",
        "format": "json",
    },
    "oecd_tax_database": {
        "name": "OCDE - Tax Database, tipos del impuesto sobre la renta personal (réplica DBnomics)",
        "scope": "finanzas_publicas",
        "default_url": "https://db.nomics.world/OECD/DSD_TAX_PIT@DF_PIT_TOP_EARN_THRESH",
        "format": "json",
    },
    "worldbank_wdi": {
        "name": "Banco Mundial - World Development Indicators (API v2)",
        "scope": "finanzas_publicas",
        "default_url": "https://api.worldbank.org/v2/",
        "format": "json",
    },
    "aeat_irpf_stats": {
        "name": "AEAT - Estadística de los declarantes del IRPF (tablas por tramos y por comunidad, curado)",
        "scope": "finanzas_publicas",
        "default_url": "https://sede.agenciatributaria.gob.es/AEAT/Contenidos_Comunes/La_Agencia_Tributaria/Estadisticas/Publicaciones/sites/irpf/",
        "format": "json",
    },
    "hacienda_ccaa": {
        "name": "Ministerio de Hacienda - tributación autonómica, liquidación del sistema de financiación y presupuestos liquidados de las CCAA (curado)",
        "scope": "finanzas_publicas",
        "default_url": "https://www.hacienda.gob.es/es-ES/Areas%20Tematicas/Financiacion%20Autonomica/Paginas/Inicio.aspx",
        "format": "json",
    },
    "vclc_tax_law_rates": {
        "name": "Tipos legales de impuestos y cotizaciones (curado, una cita por cambio)",
        "scope": "finanzas_publicas",
        "default_url": "https://www.boe.es/",
        "format": "json",
    },
}

OECD_DATASET = "DSD_REV_COMP_OECD@DF_RSOECD"
OECD_AREAS = ["ESP", "OECD_REP", "DEU", "FRA", "ITA", "PRT"]
OECD_CATEGORIES = {
    "_T": "Total de impuestos y cotizaciones sociales",
    "T_1100": "Impuestos sobre la renta, beneficios y ganancias de las personas físicas",
    "T_1200": "Impuestos sobre la renta, beneficios y ganancias de las sociedades",
    "T_2100": "Cotizaciones sociales a cargo de los trabajadores",
    "T_2200": "Cotizaciones sociales a cargo de los empleadores",
    "T_2300": "Cotizaciones sociales de autónomos y no empleados",
    "T_4000": "Impuestos sobre la propiedad",
    "T_5000": "Impuestos sobre bienes y servicios",
}
OECD_UNITS = {"PT_B1GQ": "% del PIB", "XDC": "Miles de millones de moneda nacional (euros)"}
AREA_META = {
    "ESP": ("España", "ISO3166-1-alpha-3", "country"),
    "OECD": ("OCDE (media)", "OECD-aggregate", "aggregate"),
    "DEU": ("Alemania", "ISO3166-1-alpha-3", "country"),
    "FRA": ("Francia", "ISO3166-1-alpha-3", "country"),
    "ITA": ("Italia", "ISO3166-1-alpha-3", "country"),
    "PRT": ("Portugal", "ISO3166-1-alpha-3", "country"),
    "OECD_REP": ("Media OCDE (simple, miembros actuales)", "OECD-aggregate", "aggregate"),
    "ES": ("España", "NUTS", "country"),
    "EU27_2020": ("Unión Europea (27, desde 2020)", "EU-aggregate", "aggregate"),
}

RATE_DEFINITIONS = {
    "irpf_top_marginal_rate": "Tipo marginal máximo del impuesto sobre la renta de las personas físicas (estatal + autonómico desde 1999)",
    "cit_general_rate": "Tipo general del impuesto sobre beneficios de las sociedades (antes Contribución de Utilidades)",
    "ssc_general_rate_employer": "Cotización social a cargo de la empresa, régimen general, contrato indefinido",
    "ssc_general_rate_employee": "Cotización social a cargo del trabajador, régimen general",
    "vat_standard_rate": "Tipo general del impuesto sobre el consumo (IVA desde 1986; antes IGTE)",
}

LAW_TOPICS = {
    "BOE-A-2006-20764": "tributario:irpf",
    "BOE-A-2007-6820": "tributario:irpf",
    "BOE-A-1978-23326": "tributario:irpf",
    "BOE-A-1991-14391": "tributario:irpf",
    "BOE-A-1998-28472": "tributario:irpf",
    "BOE-A-2004-4347": "tributario:irpf",
    "BOE-A-2014-12328": "tributario:is",
    "BOE-A-1978-31230": "tributario:is",
    "BOE-A-1995-27752": "tributario:is",
    "BOE-A-2004-4456": "tributario:is",
    "BOE-A-1992-28740": "tributario:iva",
    "BOE-A-1992-28741": "tributario:iiee",
    "BOE-A-2004-4214": "tributario:local",
    "BOE-A-1991-14392": "tributario:patrimonio",
    "BOE-A-1987-28141": "tributario:isd",
    "BOE-A-1993-25359": "tributario:itpajd",
    "BOE-A-2003-23186": "tributario:lgt",
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
        with urllib.request.urlopen(req, timeout=90) as resp:
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

def annual(period: str) -> tuple[str, str]:
    return f"{period}-01-01", f"{period}-12-31"


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
            definition["label"], definition.get("definition"), definition.get("domain_key", "finanzas_publicas"),
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
            obs_rows.append((
                obs_id, series_id, release_id, period, obs.get("start", annual(period)[0]),
                obs.get("end", annual(period)[1]), obs.get("interval_kind", "calendar_year"), value, text,
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


def area_series(key: str, geo: str, dimensions: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any]:
    name, system, level = AREA_META.get(geo, (geo, "unknown", "unknown"))
    return {
        "key": key, "geo_code": geo, "geo_name": name, "geo_system": system, "geo_level": level,
        "dimensions": dimensions, "observations": observations,
    }


# ---------------------------------------------------------------- sources -> indicator batches

Batch = tuple[dict[str, Any], list[dict[str, Any]]]


IMF_FPP = {
    "rev": ("Ingresos públicos (% del PIB), serie histórica FMI",
            "Ingresos totales del gobierno en % del PIB (Mauro, Romeu, Binder y Zaman, 2015). Para España y años antiguos "
            "cubre el Estado central: incluye ingresos no tributarios y excluye la Seguridad Social y los entes territoriales."),
    "exp": ("Gasto público (% del PIB), serie histórica FMI",
            "Gasto total del gobierno en % del PIB (FPP). Para España, Estado central hasta los años 90 y administraciones "
            "públicas después: la cobertura cambia y no es homogénea entre 1981 y 1994."),
    "ie": ("Intereses de la deuda pública (% del PIB), serie histórica FMI",
           "Gasto en intereses del gobierno en % del PIB (FPP); misma cobertura que el gasto."),
    "d": ("Deuda pública bruta (% del PIB), serie histórica FMI",
          "Deuda bruta del gobierno en % del PIB (Historical Public Debt Database, Abbas y otros, integrada en FPP)."),
}


def parse_imf(code: str) -> Callable[[Raw], Iterable[Batch]]:
    def parse(raw: Raw) -> Iterable[Batch]:
        values = raw.data["values"][code]["ESP"]
        label, text = IMF_FPP[code]
        definition = {
            "source_id": "imf_fpp", "dataset_code": "FPP", "indicator_code": code, "frequency_code": "A",
            "frequency_label": "Anual", "unit_code": "PT_GDP", "unit_label": "% del PIB", "label": label, "definition": text,
            "methodology_url": "https://www.imf.org/external/datamapper/datasets/FPP",
            "source_url": "https://www.imf.org/external/datamapper/datasets/FPP",
        }
        obs = [{"period": year, "value": value, "pointer": pointer("values", code, "ESP", year)} for year, value in sorted(values.items())]
        yield definition, [area_series(f"FPP|{code}|ESP", "ESP", {"indicator": code, "country": "ESP"}, obs)]
    return parse


def oecd_url() -> str:
    dims = {
        "REF_AREA": OECD_AREAS, "MEASURE": ["TAX_REV"], "SECTOR": ["S13"],
        "STANDARD_REVENUE": list(OECD_CATEGORIES), "UNIT_MEASURE": list(OECD_UNITS),
    }
    return f"https://api.db.nomics.world/v22/series/OECD/{OECD_DATASET}?" + urllib.parse.urlencode(
        {"dimensions": json.dumps(dims, separators=(",", ":")), "observations": 1, "limit": 500}
    )


def parse_oecd(raw: Raw) -> Iterable[Batch]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for doc_index, doc in enumerate(raw.data["series"]["docs"]):
        area, measure, sector, category, ctry, unit, freq = doc["series_code"].split(".")
        if category not in OECD_CATEGORIES or unit not in OECD_UNITS:
            continue
        obs = [
            {"period": period, "value": value, "pointer": pointer("series", "docs", doc_index, "value", i), "cell_index": i}
            for i, (period, value) in enumerate(zip(doc["period"], doc["value"]))
            if isinstance(value, (int, float))
        ]
        dims = {"REF_AREA": area, "MEASURE": measure, "SECTOR": sector, "STANDARD_REVENUE": category,
                "CTRY_SPECIFIC_REVENUE": ctry, "UNIT_MEASURE": unit, "FREQ": freq}
        grouped.setdefault((category, unit), []).append(area_series(f"{OECD_DATASET}|{doc['series_code']}", area, dims, obs))
    for (category, unit), series in sorted(grouped.items()):
        yield {
            "source_id": "oecd_revenue_statistics", "dataset_code": OECD_DATASET,
            "indicator_code": f"TAX_REV.S13.{category}", "frequency_code": "A", "frequency_label": "Anual",
            "unit_code": unit, "unit_label": OECD_UNITS[unit],
            "label": f"{OECD_CATEGORIES[category]} — todas las administraciones públicas ({OECD_UNITS[unit]})",
            "definition": "OCDE Revenue Statistics, clasificación de ingresos tributarios de la OCDE; sector S13 "
            "(administraciones públicas). Leído de la réplica DBnomics porque sdmx.oecd.org bloquea el acceso por script.",
            "methodology_url": "https://www.oecd.org/en/topics/sub-issues/tax-revenue.html",
            "source_url": f"https://db.nomics.world/OECD/{OECD_DATASET}",
        }, series


IDD_DATASET = "DSD_WISE_IDD@DF_IDD"
IDD_MEASURES = {
    "INC_MRKT_GINI": "Gini de la renta de mercado (antes de impuestos y transferencias)",
    "INC_GROSS_GINI": "Gini de la renta bruta (después de transferencias, antes de impuestos)",
    "INC_DISP_GINI": "Gini de la renta disponible (después de impuestos y transferencias)",
}
IDD_AGES = {"_T": "toda la población", "Y18T65": "población de 18 a 65 años"}


def idd_url() -> str:
    dims = {"REF_AREA": [a for a in OECD_AREAS if a != "OECD_REP"], "MEASURE": list(IDD_MEASURES), "AGE": list(IDD_AGES),
            "METHODOLOGY": ["METH2012"], "DEFINITION": ["D_CUR"]}
    return f"https://api.db.nomics.world/v22/series/OECD/{IDD_DATASET}?" + urllib.parse.urlencode(
        {"dimensions": json.dumps(dims, separators=(",", ":")), "observations": 1, "limit": 500}
    )


def parse_oecd_idd(raw: Raw) -> Iterable[Batch]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for doc_index, doc in enumerate(raw.data["series"]["docs"]):
        dims = doc["dimensions"]
        if dims.get("MEASURE") not in IDD_MEASURES or dims.get("AGE") not in IDD_AGES:
            continue
        obs = [
            {"period": period, "value": value, "pointer": pointer("series", "docs", doc_index, "value", i), "cell_index": i}
            for i, (period, value) in enumerate(zip(doc["period"], doc["value"]))
            if isinstance(value, (int, float))
        ]
        grouped.setdefault((dims["MEASURE"], dims["AGE"]), []).append(
            area_series(f"{IDD_DATASET}|{doc['series_code']}", dims["REF_AREA"], dims, obs))
    for (measure, age), series in sorted(grouped.items()):
        yield {
            "source_id": "oecd_income_distribution", "dataset_code": IDD_DATASET, "indicator_code": f"{measure}.{age}",
            "frequency_code": "A", "frequency_label": "Anual", "unit_code": "0_TO_1", "unit_label": "Índice de Gini (0–1)",
            "label": f"{IDD_MEASURES[measure]}, {IDD_AGES[age]}",
            "definition": "OCDE Income Distribution Database, definición de renta desde 2012. Renta de mercado: salarios, rentas "
            "del trabajo autónomo y del capital; bruta: más transferencias públicas (pensiones incluidas); disponible: menos "
            "impuestos directos y cotizaciones pagadas por los hogares. Leído de la réplica DBnomics (oecd.org bloquea scripts).",
            "methodology_url": "https://www.oecd.org/en/data/datasets/income-and-wealth-distribution-database.html",
            "source_url": f"https://db.nomics.world/OECD/{IDD_DATASET}",
        }, series


TW_DATASET = "DSD_TAX_WAGES_COMP@DF_TW_COMP"
TW_LEVELS = {"AW67": "67 %", "AW100": "100 %", "AW167": "167 %"}


def tw_url() -> str:
    dims = {"REF_AREA": [a for a in OECD_AREAS if a != "OECD_REP"] + ["OECD"], "MEASURE": ["AV_TW"],
            "HOUSEHOLD_TYPE": ["S_C0"], "INCOME_PRINCIPAL": list(TW_LEVELS), "UNIT_MEASURE": ["PT_COS_LB"]}
    return f"https://api.db.nomics.world/v22/series/OECD/{TW_DATASET}?" + urllib.parse.urlencode(
        {"dimensions": json.dumps(dims, separators=(",", ":")), "observations": 1, "limit": 500}
    )


def parse_oecd_tw(raw: Raw) -> Iterable[Batch]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for doc_index, doc in enumerate(raw.data["series"]["docs"]):
        dims = doc["dimensions"]
        level = dims.get("INCOME_PRINCIPAL")
        if level not in TW_LEVELS or dims.get("HOUSEHOLD_TYPE") != "S_C0" or dims.get("MEASURE") != "AV_TW":
            continue
        obs = [
            {"period": period, "value": value, "pointer": pointer("series", "docs", doc_index, "value", i), "cell_index": i}
            for i, (period, value) in enumerate(zip(doc["period"], doc["value"]))
            if isinstance(value, (int, float))
        ]
        grouped.setdefault(level, []).append(area_series(f"{TW_DATASET}|{doc['series_code']}", dims["REF_AREA"], dims, obs))
    for level, series in sorted(grouped.items()):
        yield {
            "source_id": "oecd_taxing_wages", "dataset_code": TW_DATASET, "indicator_code": f"AV_TW.S_C0.{level}",
            "frequency_code": "A", "frequency_label": "Anual", "unit_code": "PT_COS_LB", "unit_label": "% del coste laboral",
            "label": f"Cuña fiscal media, soltero sin hijos que gana el {TW_LEVELS[level]} del salario medio",
            "definition": "OCDE Taxing Wages: impuesto sobre la renta y cotizaciones del trabajador y de la empresa, menos "
            "prestaciones en efectivo, en % del coste laboral total. Leído de la réplica DBnomics (oecd.org bloquea scripts).",
            "methodology_url": "https://www.oecd.org/en/topics/sub-issues/tax-wedge.html",
            "source_url": f"https://db.nomics.world/OECD/{TW_DATASET}",
        }, series


PIT_DATASET = "DSD_TAX_PIT@DF_PIT_TOP_EARN_THRESH"
PIT_MEASURES = {
    "TS_PIT": ("PT_WG_EARN_G", "% del salario bruto", "Tipo marginal máximo legal del impuesto sobre la renta (todas las administraciones)"),
    "TS_PIT_TH": ("FCTR_WG_A_SAL_A", "Veces el salario medio", "Umbral de renta a partir del que se aplica el tipo máximo"),
}


def pit_url() -> str:
    dims = {"REF_AREA": [a for a in OECD_AREAS if a != "OECD_REP"], "MEASURE": list(PIT_MEASURES)}
    return f"https://api.db.nomics.world/v22/series/OECD/{PIT_DATASET}?" + urllib.parse.urlencode(
        {"dimensions": json.dumps(dims, separators=(",", ":")), "observations": 1, "limit": 500}
    )


def parse_oecd_pit(raw: Raw) -> Iterable[Batch]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for doc_index, doc in enumerate(raw.data["series"]["docs"]):
        dims = doc["dimensions"]
        measure = dims.get("MEASURE")
        if measure not in PIT_MEASURES or dims.get("UNIT_MEASURE") != PIT_MEASURES[measure][0]:
            continue
        obs = [
            {"period": period, "value": value, "pointer": pointer("series", "docs", doc_index, "value", i), "cell_index": i}
            for i, (period, value) in enumerate(zip(doc["period"], doc["value"]))
            if isinstance(value, (int, float))
        ]
        grouped.setdefault(measure, []).append(area_series(f"{PIT_DATASET}|{doc['series_code']}", dims["REF_AREA"], dims, obs))
    for measure, series in sorted(grouped.items()):
        unit, unit_label, label = PIT_MEASURES[measure]
        yield {
            "source_id": "oecd_tax_database", "dataset_code": PIT_DATASET, "indicator_code": measure,
            "frequency_code": "A", "frequency_label": "Anual", "unit_code": unit, "unit_label": unit_label, "label": label,
            "definition": "OCDE Tax Database, tabla I.7: tipo marginal máximo combinado (central y subcentral) del impuesto "
            "sobre la renta personal; para España la OCDE usa la media de las escalas autonómicas. Leído de la réplica "
            "DBnomics (oecd.org bloquea scripts).",
            "methodology_url": "https://www.oecd.org/en/data/datasets/oecd-tax-database.html",
            "source_url": f"https://db.nomics.world/OECD/{PIT_DATASET}",
        }, series


EUROSTAT_API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
EUROSTAT_GEOS = ["ES", "DE", "FR", "IT", "PT", "EU27_2020"]

COFOG = ["TOTAL", "GF01", "GF0107", "GF02", "GF03", "GF04", "GF05", "GF06", "GF07", "GF08", "GF09", "GF10",
         "GF1001", "GF1002", "GF1003", "GF1004", "GF1005", "GF1006", "GF1007"]

# raw file stem, dataset, filters (a list value varies: one indicator per combination), unit_code, unit_label,
# label (may use {label} = label of the varying code), definition.
EUROSTAT_DATASETS: list[dict[str, Any]] = [
    {
        "name": "gov_10a_taxag", "dataset": "gov_10a_taxag",
        "filters": {"unit": "PC_GDP", "sector": "S13_S212", "na_item": "D2_D5_D91_D61_M_D995"},
        "unit_code": "PC_GDP", "unit_label": "% del PIB",
        "label": "Carga fiscal total (impuestos y cotizaciones sociales netas), % del PIB",
        "definition": "Impuestos sobre producción e importaciones, renta y patrimonio, de capital y cotizaciones sociales "
        "efectivas, menos impuestos y cotizaciones evaluados pero no recaudados (SEC 2010).",
    },
    {
        "name": "nama_10_pc", "dataset": "nama_10_pc", "filters": {"unit": "CP_PPS_EU27_2020_HAB", "na_item": "B1GQ"},
        "unit_code": "PPS_HAB", "unit_label": "Estándar de poder adquisitivo (UE-27) por habitante",
        "label": "PIB por habitante en paridad de poder adquisitivo",
        "definition": "Producto interior bruto a precios corrientes por habitante, en estándar de poder adquisitivo UE-27 "
        "(comparable entre países).",
    },
    {
        "name": "nama_10_pc_clv", "dataset": "nama_10_pc", "filters": {"unit": "CLV10_EUR_HAB", "na_item": "B1GQ"},
        "unit_code": "CLV10_EUR_HAB", "unit_label": "Euros encadenados de 2010 por habitante",
        "label": "PIB real por habitante (volumen encadenado, euros de 2010)",
        "definition": "Producto interior bruto en volumen encadenado (referencia 2010) por habitante: deflactado con el "
        "deflactor del PIB de cada país. Sirve para medir crecimiento real, no para comparar niveles entre países.",
    },
    {
        "name": "nama_10_pc_eur", "dataset": "nama_10_pc", "filters": {"unit": "CP_EUR_HAB", "na_item": "B1GQ"},
        "unit_code": "CP_EUR_HAB", "unit_label": "Euros corrientes por habitante",
        "label": "PIB por habitante a precios corrientes (euros)",
        "definition": "Producto interior bruto a precios corrientes por habitante, en euros.",
    },
    {
        "name": "prc_hicp_aind", "dataset": "prc_hicp_aind", "filters": {"unit": "INX_A_AVG", "coicop": "CP00"},
        "unit_code": "INX_A_AVG", "unit_label": "Índice (2015 = 100), media anual",
        "label": "Índice de precios de consumo armonizado (IPCA), general",
        "definition": "Índice de precios de consumo armonizado, todos los artículos, media anual (2015 = 100).",
    },
    {
        "name": "tec00113", "dataset": "tec00113",
        "filters": {"unit": "PPS_EU27_2020_HAB", "na_item": "B7G", "sector": "S14_S15", "direct": "PAID"},
        "unit_code": "PPS_HAB", "unit_label": "Estándar de poder adquisitivo (UE-27) por habitante",
        "label": "Renta disponible ajustada de los hogares por habitante en paridad de poder adquisitivo",
        "definition": "Renta disponible bruta ajustada de hogares e ISFLSH (incluye las transferencias sociales en especie: "
        "sanidad y educación públicas) por habitante, en estándar de poder adquisitivo UE-27.",
    },
    {
        "name": "nasa_10_ki", "dataset": "nasa_10_ki", "filters": {"unit": "PC", "na_item": "B7G_R_HAB_2010", "sector": "S14_S15"},
        "unit_code": "IDX2010", "unit_label": "Índice 2010 = 100",
        "label": "Renta disponible ajustada real de los hogares por habitante (2010 = 100)",
        "definition": "Renta disponible bruta ajustada de hogares e ISFLSH por habitante, deflactada por el deflactor del "
        "consumo final de los hogares.",
    },
    {
        "name": "ilc_di03_pps", "dataset": "ilc_di03",
        "filters": {"unit": "PPS", "age": "TOTAL", "sex": "T", "statinfo": ["MED_EI", "MEAN_EI"]},
        "unit_code": "PPS", "unit_label": "Estándar de poder adquisitivo",
        "label": "Renta neta equivalente de los hogares (EU-SILC), {label}, en PPS",
        "definition": "Renta disponible neta del hogar dividida por sus unidades de consumo (escala OCDE modificada) y asignada a "
        "cada miembro; encuesta EU-SILC. La renta se refiere al año anterior al de la encuesta en casi todos los países.",
    },
    {
        "name": "ilc_di03_nac", "dataset": "ilc_di03",
        "filters": {"unit": "NAC", "age": "TOTAL", "sex": "T", "statinfo": ["MED_EI", "MEAN_EI"]},
        "unit_code": "NAC", "unit_label": "Moneda nacional (euros)",
        "label": "Renta neta equivalente de los hogares (EU-SILC), {label}, en moneda nacional",
        "definition": "Como la serie en PPS, en euros corrientes; sirve para calcular su cambio real con el IPCA.",
    },
    {
        "name": "ilc_mded01", "dataset": "ilc_mded01", "filters": {"unit": "PC", "hhcomp": "TOTAL", "rskpovth": ["TOTAL", "B_60"]},
        "unit_code": "PC", "unit_label": "% de la renta disponible del hogar",
        "label": "Peso de los gastos de vivienda en la renta disponible de los hogares (EU-SILC), {label}",
        "definition": "Gastos de vivienda (alquiler o intereses de la hipoteca, suministros, comunidad, reparaciones, seguros e "
        "impuestos de la vivienda, netos de ayudas a la vivienda) en % de la renta disponible del hogar. "
        "B_60 = hogares en riesgo de pobreza (renta por debajo del 60 % de la mediana).",
    },
    {
        "name": "ilc_lvho07c", "dataset": "ilc_lvho07c", "filters": {"unit": "PC", "tenure": ["TOTAL", "RENT_MKT", "OWN_L"]},
        "unit_code": "PC", "unit_label": "% de la población",
        "label": "Sobrecarga del coste de la vivienda (EU-SILC): {label}",
        "definition": "Porcentaje de la población que vive en hogares cuyos gastos de vivienda netos de ayudas superan el 40 % de su "
        "renta disponible, por régimen de tenencia.",
    },
    {
        "name": "nama_10_pe", "dataset": "nama_10_pe", "filters": {"unit": "THS_PER", "na_item": ["POP_NC", "EMP_DC"]},
        "unit_code": "THS_PER", "unit_label": "Miles de personas",
        "label": "Población y empleo (contabilidad nacional): {label}",
        "definition": "Población residente total (POP_NC) y personas ocupadas en el territorio (EMP_DC), media anual, SEC 2010.",
    },
    {
        "name": "spr_pns_ben", "dataset": "spr_pns_ben",
        "filters": {"unit": "PER", "spdepm": "TOTAL", "spscheme": "TOTAL", "sex": "T", "spdepb": ["OLD_SRV", "TOTAL"]},
        "unit_code": "PER", "unit_label": "Personas",
        "label": "Personas que cobran pensión (ESSPROS): {label}",
        "definition": "Beneficiarios de pensiones a final de año; cada persona cuenta una vez aunque cobre varias pensiones del tipo.",
    },
    {
        "name": "ilc_di12", "dataset": "ilc_di12", "filters": {"age": "TOTAL", "statinfo": "GINI_HND"},
        "unit_code": "GINI", "unit_label": "Índice de Gini (0–100)",
        "label": "Gini de la renta disponible equivalente (EU-SILC)",
        "definition": "Desigualdad de la renta disponible equivalente después de impuestos y transferencias.",
    },
    {
        "name": "ilc_di12b", "dataset": "ilc_di12b", "filters": {"statinfo": "GINI_HND"},
        "unit_code": "GINI", "unit_label": "Índice de Gini (0–100)",
        "label": "Gini antes de transferencias sociales, pensiones incluidas en las transferencias (EU-SILC)",
        "definition": "Desigualdad de la renta disponible equivalente si se quitan todas las transferencias sociales, pensiones incluidas.",
    },
    {
        "name": "ilc_di12c", "dataset": "ilc_di12c", "filters": {"statinfo": "GINI_HND"},
        "unit_code": "GINI", "unit_label": "Índice de Gini (0–100)",
        "label": "Gini antes de transferencias sociales, pensiones contadas como renta (EU-SILC)",
        "definition": "Desigualdad de la renta disponible equivalente si se quitan las transferencias sociales salvo las pensiones.",
    },
    {
        "name": "gov_10a_exp", "dataset": "gov_10a_exp",
        "filters": {"unit": "PC_GDP", "sector": "S13", "na_item": "TE", "cofog99": COFOG},
        "unit_code": "PC_GDP", "unit_label": "% del PIB",
        "label": "Gasto de las administraciones públicas por función (COFOG): {label}",
        "definition": "Gasto total de las administraciones públicas (S13) clasificado por función según COFOG, en % del PIB. "
        "GF0107 (transacciones de la deuda pública) son sobre todo intereses.",
    },
    {
        "name": "gov_10a_main", "dataset": "gov_10a_main",
        "filters": {"unit": "PC_GDP", "sector": "S13", "na_item": ["TR", "TE", "B9", "D41PAY", "D1PAY"]},
        "unit_code": "PC_GDP", "unit_label": "% del PIB",
        "label": "Cuentas de las administraciones públicas: {label}",
        "definition": "Agregados principales de las administraciones públicas (S13), SEC 2010, en % del PIB.",
    },
]


def eurostat_url(dataset: str, filters: dict[str, Any]) -> str:
    query = [("geo", geo) for geo in EUROSTAT_GEOS]
    for key, value in filters.items():
        query.extend((key, v) for v in (value if isinstance(value, list) else [value]))
    return f"{EUROSTAT_API}/{dataset}?" + urllib.parse.urlencode(query)


def parse_eurostat_dataset(spec: dict[str, Any]) -> Callable[[Raw], Iterable[Batch]]:
    """JSON-stat cube: geo and time vary, plus at most one listed dimension (one indicator per value)."""
    dataset, filters = spec["dataset"], spec["filters"]
    varying = [k for k, v in filters.items() if isinstance(v, list)]
    if len(varying) > 1:
        raise ValueError(f"{dataset}: at most one list-valued filter")

    def parse(raw: Raw) -> Iterable[Batch]:
        data = raw.data
        ids, sizes = data["id"], data["size"]
        strides = [1] * len(ids)
        for i in range(len(ids) - 2, -1, -1):
            strides[i] = strides[i + 1] * sizes[i + 1]
        geo_idx = data["dimension"]["geo"]["category"]["index"]
        time_idx = data["dimension"]["time"]["category"]["index"]
        choices = [None] if not varying else [
            code for code in filters[varying[0]] if code in data["dimension"][varying[0]]["category"]["index"]
        ]
        for choice in choices:
            fixed = {**filters, **({varying[0]: choice} if varying else {})}
            base = sum(
                data["dimension"][dim]["category"]["index"][fixed[dim]] * strides[pos]
                for pos, dim in enumerate(ids) if dim not in ("geo", "time") and dim in fixed
            )
            series = []
            for geo, gi in sorted(geo_idx.items(), key=lambda kv: kv[1]):
                obs = []
                for year, ti in sorted(time_idx.items(), key=lambda kv: kv[1]):
                    flat = base + gi * strides[ids.index("geo")] + ti * strides[ids.index("time")]
                    value = data["value"].get(str(flat))
                    if value is not None:
                        obs.append({"period": year, "value": value, "pointer": pointer("value", flat), "cell_index": flat,
                                    "status": data.get("status", {}).get(str(flat))})
                key = "|".join([dataset, *(f"{k}={v}" for k, v in sorted(fixed.items())), f"geo={geo}"])
                series.append(area_series(key, geo, {**fixed, "geo": geo}, obs))
            code_label = data["dimension"][varying[0]]["category"]["label"].get(choice, choice) if varying else ""
            yield {
                "source_id": "eurostat_sdmx", "dataset_code": dataset,
                "indicator_code": ".".join(fixed[k] for k in sorted(fixed) if k != "unit"),
                "frequency_code": "A", "frequency_label": "Anual", "unit_code": spec["unit_code"],
                "unit_label": spec["unit_label"], "label": spec["label"].format(label=code_label),
                "definition": spec["definition"],
                "methodology_url": f"https://ec.europa.eu/eurostat/cache/metadata/en/{dataset}_esms.htm",
                "source_url": f"https://ec.europa.eu/eurostat/databrowser/view/{dataset}/default/table",
                "source_updated_at": data.get("updated"),
            }, series
    return parse


WB_INDICATORS = {
    "SP.POP.TOTL": ("Población total", "PERSONS", "Personas"),
    "FP.CPI.TOTL": ("Índice de precios al consumo (2010 = 100)", "IDX2010", "Índice 2010 = 100"),
}


def parse_worldbank(code: str) -> Callable[[Raw], Iterable[Batch]]:
    def parse(raw: Raw) -> Iterable[Batch]:
        label, unit, unit_label = WB_INDICATORS[code]
        obs = [
            {"period": row["date"], "value": row["value"], "pointer": pointer(1, i, "value"), "cell_index": i}
            for i, row in enumerate(raw.data[1]) if row["value"] is not None
        ]
        yield {
            "source_id": "worldbank_wdi", "dataset_code": "WDI", "indicator_code": code, "frequency_code": "A",
            "frequency_label": "Anual", "unit_code": unit, "unit_label": unit_label, "label": f"{label} — España",
            "methodology_url": f"https://data.worldbank.org/indicator/{code}?locations=ES",
            "source_url": f"https://data.worldbank.org/indicator/{code}?locations=ES",
        }, [area_series(f"WDI|{code}|ESP", "ESP", {"indicator": code, "country": "ESP"}, obs)]
    return parse


API_SOURCES: list[tuple[str, str, Callable[[Raw], Iterable[Batch]]]] = [
    *[
        (f"imf_fpp_{code}_esp.json", f"https://www.imf.org/external/datamapper/api/v1/{code}/ESP", parse_imf(code))
        for code in IMF_FPP
    ],
    ("oecd_revenue_statistics_dbnomics.json", oecd_url(), parse_oecd),
    ("oecd_income_distribution_dbnomics.json", idd_url(), parse_oecd_idd),
    ("oecd_taxing_wages_dbnomics.json", tw_url(), parse_oecd_tw),
    ("oecd_pit_top_rates_dbnomics.json", pit_url(), parse_oecd_pit),
    *[
        (f"eurostat_{spec['name']}.json", eurostat_url(spec["dataset"], spec["filters"]), parse_eurostat_dataset(spec))
        for spec in EUROSTAT_DATASETS
    ],
    *[
        (f"worldbank_{code}.json", f"https://api.worldbank.org/v2/country/ESP/indicator/{code}?format=json&per_page=200",
         parse_worldbank(code))
        for code in WB_INDICATORS
    ],
]


# ---------------------------------------------------------------- curated statutory rates

def load_rates(conn: sqlite3.Connection, snapshot_date: str) -> dict[str, int]:
    path = MANUAL_DIR / "statutory_rates_es.json"
    if not path.exists():
        return {"releases": 0, "observations": 0, "missing": 1}
    payload = path.read_bytes()
    data = json.loads(payload)
    totals = {"releases": 0, "observations": 0}
    for key, rows in sorted(data.get("series", {}).items()):
        if key not in RATE_DEFINITIONS:
            raise ValueError(f"unknown statutory rate series {key!r}; add it to RATE_DEFINITIONS")
        ordered = sorted(enumerate(rows), key=lambda item: (item[1]["from_year"], item[0]))
        obs = []
        for pos, (index, row) in enumerate(ordered):
            if row.get("value_pct") is None:
                continue
            start = row.get("from_date") or f"{row['from_year']}-01-01"
            following = ordered[pos + 1][1] if pos + 1 < len(ordered) else None
            next_start = (following.get("from_date") or f"{following['from_year']}-01-01") if following else None
            end = (date.fromisoformat(next_start) - timedelta(days=1)).isoformat() if next_start else "9999-12-31"
            obs.append({
                "period": start, "value": row["value_pct"], "start": start,
                "end": end, "interval_kind": "legal_validity",
                "pointer": pointer("series", key, index, "value_pct"), "cell_index": index,
                "evidence_url": row.get("source_url"), "raw": row,
                "status": row.get("confidence"),
                "status_labels": [{"code": row.get("confidence"), "label": f"confianza {row.get('confidence')}"}] if row.get("confidence") else [],
            })
        definition = {
            "source_id": "vclc_tax_law_rates", "dataset_code": "statutory_rates_es", "indicator_code": key,
            "frequency_code": "EVENT", "frequency_label": "Por cambio legal", "unit_code": "PC", "unit_label": "%",
            "label": RATE_DEFINITIONS[key], "extraction_method": "curated_citation",
            "definition": "Tipo legal vigente desde cada fecha según la norma o fuente citada en cada fila.",
            "methodology_url": "https://votaconlachola.org/visualizaciones/carga-fiscal/#tipos",
            "source_url": "https://www.boe.es/",
        }
        counts = load_indicator(
            conn, definition, sha256_bytes(payload), len(payload), rel(path), definition["source_url"], snapshot_date,
            {"gaps": data.get("gaps", []), "blocked_hosts": data.get("blocked_hosts", [])},
            [area_series(f"statutory_rates_es|{key}|ESP", "ESP", {"rate": key}, obs)],
        )
        for k in totals:
            totals[k] += counts[k]
    return totals


# ---------------------------------------------------------------- AEAT IRPF by income bracket and by community

IRPF_MEASURES = {
    "declarations": ("COUNT", "Declaraciones", "Número de declaraciones (liquidaciones) del IRPF"),
    "income_eur": ("EUR", "Euros", "Base imponible general + del ahorro (partidas 435 + 460)"),
    "tax_eur": ("EUR", "Euros", "Cuota resultante de la autoliquidación (partida 595)"),
}


def load_irpf(conn: sqlite3.Connection, snapshot_date: str) -> dict[str, int]:
    """AEAT declarants statistics as curated in irpf_by_bracket_es.json: one indicator per measure, series per bracket
    (Spain, common regime) and per autonomous community, evidence pointing at the AEAT table page."""
    path = MANUAL_DIR / "irpf_by_bracket_es.json"
    if not path.exists():
        return {"releases": 0, "observations": 0, "missing": 1}
    payload = path.read_bytes()
    data = json.loads(payload)
    year = str(data["tax_year"])
    totals = {"releases": 0, "observations": 0}
    for measure, (unit, unit_label, label) in IRPF_MEASURES.items():
        series = []
        for i, row in enumerate(data["brackets"]):
            series.append(area_series(
                f"irpf_by_bracket|ESP|{row['label']}", "ESP", {"bracket": row["label"], "lower_eur": row.get("lower_eur"),
                                                              "upper_eur": row.get("upper_eur"), "order": i},
                [{"period": year, "value": row[measure], "pointer": pointer("brackets", i, measure), "cell_index": i,
                  "evidence_url": data["source_url"], "raw": {"locator": row.get("locator")}}]))
        series.append(area_series(
            "irpf_by_bracket|ESP|Total", "ESP", {"bracket": "Total"},
            [{"period": year, "value": data["totals"][measure], "pointer": pointer("totals", measure),
              "evidence_url": data["source_url"], "raw": {"locator": data["totals"].get("locator")}}]))
        for i, row in enumerate((data.get("by_ccaa") or {}).get("rows", [])):
            series.append(area_series(
                f"irpf_by_ccaa|{row['name']}", row["name"], {"bracket": "Total", "ccaa": row["name"]},
                [{"period": year, "value": row[measure], "pointer": pointer("by_ccaa", "rows", i, measure), "cell_index": i,
                  "evidence_url": (row.get("source_urls") or {}).get("595") or data["source_url"]}]))
        definition = {
            "source_id": "aeat_irpf_stats", "dataset_code": "irpf_declarantes", "indicator_code": f"irpf.{measure}",
            "frequency_code": "A", "frequency_label": "Anual (ejercicio fiscal)", "unit_code": unit, "unit_label": unit_label,
            "label": f"IRPF: {label}", "extraction_method": "curated_table_cell",
            "definition": f"{label}. {data['definitions'].get('bracket', '')} Régimen común (sin País Vasco ni Navarra).",
            "methodology_url": data.get("publication_home"), "source_url": data["source_url"],
        }
        counts = load_indicator(conn, definition, sha256_bytes(payload), len(payload), rel(path), data["source_url"],
                                snapshot_date, {"retrieved_at": data.get("retrieved"), "gaps": data.get("gaps", [])}, series)
        for k in totals:
            totals[k] += counts[k]
    return totals


# ---------------------------------------------------------------- Autonomous communities (curated from Hacienda, INE)

REGIONAL = [
    # file, field, indicator_code, unit, unit_label, label, source_key
    ("regional_irpf_top_rates_2025.json", "total_top_rate_pct", "irpf_top_rate_total", "PC", "%",
     "Tipo marginal máximo del IRPF (estatal + autonómico, o foral) sobre la base general", None),
    ("regional_irpf_top_rates_2025.json", "regional_top_rate_pct", "irpf_top_rate_regional", "PC", "%",
     "Tipo marginal máximo de la escala autonómica del IRPF", None),
    ("regional_irpf_top_rates_2025.json", "threshold_eur", "irpf_top_rate_regional_threshold", "EUR", "Euros",
     "Base liquidable a partir de la que se aplica el tipo autonómico (o foral) máximo", None),
    ("regional_public_finance_es.json", "financing_per_adj_inhabitant_eur", "financing_homogeneous_per_adj_inhabitant", "EUR", "Euros por habitante ajustado",
     "Financiación a competencias homogéneas por habitante ajustado, antes de fondos de convergencia (régimen común)", "financing"),
    ("regional_public_finance_es.json", "financing_after_convergence_funds_per_adj_inhabitant_eur", "financing_after_funds_per_adj_inhabitant", "EUR",
     "Euros por habitante ajustado", "Financiación homogénea más fondos de Competitividad y Cooperación por habitante ajustado (derivado)", "financing"),
    ("regional_public_finance_es.json", "spending_per_inhabitant_eur", "spending_nonfinancial_per_inhabitant", "EUR", "Euros por habitante",
     "Gasto no financiero liquidado de la comunidad (consolidado, sin participación de entes locales ni PAC) por habitante", "spending"),
    ("regional_public_finance_es.json", "gdp_per_inhabitant_eur", "gdp_per_inhabitant", "EUR", "Euros por habitante",
     "PIB por habitante (INE, Contabilidad Regional)", "gdp"),
]


def load_regional(conn: sqlite3.Connection, snapshot_date: str) -> dict[str, int]:
    """Curated regional files (one row per community, with source URL, sha256 and locator) as indicators."""
    totals = {"releases": 0, "observations": 0}
    cache: dict[str, tuple[bytes, dict]] = {}
    for name, field, code, unit, unit_label, label, source_key in REGIONAL:
        path = MANUAL_DIR / name
        if not path.exists():
            continue
        if name not in cache:
            payload = path.read_bytes()
            cache[name] = (payload, json.loads(payload))
        payload, data = cache[name]
        year = str(data["year"])
        series = []
        for i, row in enumerate(data["rows"]):
            src = (row.get("fields_sources") or {}).get(source_key) if source_key else row
            if row.get(field) is None:
                continue
            series.append(area_series(
                f"{code}|{row['code']}", row["code"], {"name": row["name"], "regime": row["regime"]},
                [{"period": year, "value": row[field], "pointer": pointer("rows", i, field), "cell_index": i,
                  "evidence_url": (src or {}).get("source_url") or (src or {}).get("url"),
                  "status": row.get("confidence"),
                  "raw": {"locator": (src or {}).get("locator"), "sha256": (src or {}).get("sha256")}}]))
        definition = {
            "source_id": "hacienda_ccaa", "dataset_code": name.removesuffix(".json"), "indicator_code": code,
            "frequency_code": "A", "frequency_label": "Anual", "unit_code": unit, "unit_label": unit_label, "label": label,
            "extraction_method": "curated_table_cell",
            "definition": (data.get("definitions") or {}).get(field) or data.get("source_note") or label,
            "source_url": "https://www.hacienda.gob.es/es-ES/Areas%20Tematicas/Financiacion%20Autonomica/Paginas/Inicio.aspx",
        }
        counts = load_indicator(conn, definition, sha256_bytes(payload), len(payload), rel(path), definition["source_url"],
                                snapshot_date, {"gaps": data.get("gaps", [])}, series)
        for k in totals:
            totals[k] += counts[k]
    return totals


# ---------------------------------------------------------------- BOE complexity -> legal norms

def norm_id(boe_id: str) -> str:
    return f"es:{boe_id.lower()}"


def upsert_norm(conn: sqlite3.Connection, boe_id: str, title: str, published: str | None, effective: str | None,
                topic: str | None, snapshot_date: str, raw: dict[str, Any]) -> None:
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO legal_norms (
          norm_id, boe_id, title, scope, topic_hint, effective_date, published_date, source_id, source_url,
          source_snapshot_date, raw_payload, created_at, updated_at
        ) VALUES (?, ?, ?, 'estatal', ?, ?, ?, 'boe_api_legal', ?, ?, ?, ?, ?)
        ON CONFLICT(norm_id) DO UPDATE SET
          title = CASE WHEN length(excluded.title) > length(legal_norms.title) THEN excluded.title ELSE legal_norms.title END,
          topic_hint = COALESCE(excluded.topic_hint, legal_norms.topic_hint),
          effective_date = COALESCE(legal_norms.effective_date, excluded.effective_date),
          published_date = COALESCE(legal_norms.published_date, excluded.published_date),
          source_snapshot_date = excluded.source_snapshot_date,
          updated_at = excluded.updated_at
        """,
        (norm_id(boe_id), boe_id, title, topic, effective, published,
         f"https://www.boe.es/buscar/act.php?id={boe_id}", snapshot_date, canonical_json(raw), ts, ts),
    )


def relation_type(label: str) -> str:
    return "deroga" if label.upper().startswith("SE DEROGA") else "modifica"


def load_complexity(conn: sqlite3.Connection, snapshot_date: str) -> dict[str, int]:
    path = MANUAL_DIR / "tax_complexity_es.json"
    if not path.exists():
        return {"norms": 0, "edges": 0, "text_metrics": 0, "missing": 1}
    data = json.loads(path.read_bytes())
    ts = now_iso()
    edges = 0
    for law in data.get("amendments", []):
        upsert_norm(conn, law["boe_id"], law.get("title_official") or law["law"], law.get("published"),
                    law.get("enacted"), LAW_TOPICS.get(law["boe_id"]), snapshot_date,
                    {k: law.get(k) for k in ("law", "enacted", "published", "api_analisis", "relation_labels_all")})
        for amending in law.get("modifying_norms", []):
            upsert_norm(conn, amending["boe_id"], amending.get("title_short") or amending["boe_id"], amending.get("date"),
                        None, None, snapshot_date, amending)
            for kind in sorted({relation_type(label) for label in amending.get("relations", [])}):
                labels = [label for label in amending.get("relations", []) if relation_type(label) == kind]
                conn.execute(
                    """
                    INSERT INTO legal_norm_lineage_edges (
                      norm_id, related_norm_id, relation_type, relation_scope, evidence_date, source_id, source_url,
                      evidence_quote, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, 'parcial', ?, 'boe_api_legal', ?, ?, ?, ?, ?)
                    ON CONFLICT(norm_id, related_norm_id, relation_type, source_url) DO UPDATE SET
                      evidence_date = excluded.evidence_date, evidence_quote = excluded.evidence_quote,
                      raw_payload = excluded.raw_payload, updated_at = excluded.updated_at
                    """,
                    (norm_id(amending["boe_id"]), norm_id(law["boe_id"]), kind, amending.get("date"),
                     law["api_analisis"], "; ".join(labels), canonical_json(amending), ts, ts),
                )
                edges += 1
    structure = {(row["boe_id"], row["version"]): row for row in data.get("structure", [])}
    metrics = 0
    for row in data.get("law_length", []):
        upsert_norm(conn, row["boe_id"], row.get("title_official") or row["law"], row.get("published"), None,
                    LAW_TOPICS.get(row["boe_id"]) or f"tributario:{row['tax']}", snapshot_date,
                    {k: row.get(k) for k in ("law", "tax", "year", "published")})
        kind = "original" if row["version"] == "original" else "consolidated"
        version_date = row.get("published") if kind == "original" else row["version"].removeprefix("consolidated-")
        extra = structure.get((row["boe_id"], row["version"]), {})
        counts = extra.get("counts", {})
        emptied = sum((extra.get("of_which_emptied_derogated_or_no_content") or {}).values()) if extra else None
        conn.execute(
            """
            INSERT INTO legal_norm_text_metrics (
              text_metric_id, norm_id, version_kind, version_date, words, words_excl_preamble, articles,
              disp_adicionales, disp_transitorias, disp_derogatorias, disp_finales, emptied_blocks, source_id,
              source_url, method, raw_payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'boe_api_legal', ?, ?, ?, ?, ?)
            ON CONFLICT(norm_id, version_kind, version_date) DO UPDATE SET
              words = excluded.words, words_excl_preamble = excluded.words_excl_preamble,
              articles = excluded.articles, disp_adicionales = excluded.disp_adicionales,
              disp_transitorias = excluded.disp_transitorias, disp_derogatorias = excluded.disp_derogatorias,
              disp_finales = excluded.disp_finales, emptied_blocks = excluded.emptied_blocks,
              raw_payload = excluded.raw_payload, updated_at = excluded.updated_at
            """,
            (
                stable_id("legal-norm-text-metric", row["boe_id"], kind, version_date), norm_id(row["boe_id"]), kind,
                version_date, row.get("words"), row.get("words_excl_preamble"),
                counts.get("articulos", row.get("articles")), counts.get("disp_adicionales"),
                counts.get("disp_transitorias"), counts.get("disp_derogatorias"), counts.get("disp_finales"), emptied,
                row.get("source") or extra.get("source") or f"https://www.boe.es/buscar/act.php?id={row['boe_id']}",
                "scripts/boe_tax_complexity.py: XML text, tags stripped, words split on whitespace; preamble excluded "
                "in words_excl_preamble; one row per block type in counts",
                canonical_json({"law_length": row, "structure": extra}), ts, ts,
            ),
        )
        metrics += 1
    norms = conn.execute("SELECT COUNT(*) FROM legal_norms WHERE source_id = 'boe_api_legal'").fetchone()[0]
    return {"norms": norms, "edges": edges, "text_metrics": metrics}


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
        report["statutory_rates"] = load_rates(conn, args.snapshot_date)
        report["irpf_by_bracket"] = load_irpf(conn, args.snapshot_date)
        report["regional"] = load_regional(conn, args.snapshot_date)
        report["complexity"] = load_complexity(conn, args.snapshot_date)
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk:
        raise SystemExit(f"foreign_key_check failed: {fk[:5]}")
    conn.close()
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
