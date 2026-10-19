#!/usr/bin/env python3
"""Ingest Spain's health indicators (life expectancy, health spending, waiting lists, doctors) into SQLite.

Boundaries (same indicator contract v1 as scripts/ingest_public_finance_es.py):
- ingest: fetch each source API, keep the raw payload under etl/data/raw/health/apis/ (+ URL, retrieval time);
  `--offline` reuses that cache. `--fetch-pdfs` also downloads the Ministerio de Sanidad PDFs (SISLE waiting-list
  reports, EGSP spending series) into etl/data/raw/health/{sisle,egsp}/.
- PDF-only official data: scripts/extract_health_pdfs_es.py turns those PDFs into curated JSON with a page and a
  quoted table line per value (etl/data/manual/health/). This loader checks that each cited PDF in the raw cache
  still has the sha256 the curated file recorded, and points each value's evidence at the PDF itself.
- normalize/load: indicator_definitions -> indicator_releases -> indicator_series_versions ->
  indicator_observation_versions (revision state vs the previous release) -> indicator_observation_evidence.
  Methodology breaks and rectifications are status codes on the observation (`break`, `rectified`, OECD `B`/`E`).

The published site JSON is derived from this DB by scripts/export_public_viz_health.py.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
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

DEFAULT_DB = REPO_ROOT / "etl/data/staging/health-es.db"
RAW_ROOT = REPO_ROOT / "etl/data/raw/health"
RAW_DIR = RAW_ROOT / "apis"
MANUAL_DIR = REPO_ROOT / "etl/data/manual/health"
USER_AGENT = "Mozilla/5.0 (compatible; vota-con-la-chola-etl/1.0; +https://votaconlachola.org)"
EXTRACTOR_VERSION = "ingest_health_es/1"
NUL = "\x00"

LOCAL_SOURCES: dict[str, dict[str, str]] = {
    "ine_wstempus": {
        "name": "INE - API Tempus3 (Indicadores Demográficos Básicos)",
        "scope": "sanidad",
        "default_url": "https://servicios.ine.es/wstempus/js/ES/",
        "format": "json",
    },
    "oecd_health_statistics": {
        "name": "OCDE - Health Statistics, gasto y financiación SHA (réplica DBnomics)",
        "scope": "sanidad",
        "default_url": "https://db.nomics.world/OECD/DSD_SHA@DF_SHA",
        "format": "json",
    },
    "worldbank_wdi": {
        "name": "Banco Mundial - World Development Indicators (API v2)",
        "scope": "sanidad",
        "default_url": "https://api.worldbank.org/v2/",
        "format": "json",
    },
    "owid_grapher": {
        "name": "Our World in Data - esperanza de vida histórica (Riley; Zijdeman et al.; HMD; ONU WPP)",
        "scope": "sanidad",
        "default_url": "https://ourworldindata.org/grapher/life-expectancy",
        "format": "csv",
    },
    "minsan_sisle_sns": {
        "name": "Ministerio de Sanidad - Listas de espera del SNS (SISLE-SNS), informes semestrales",
        "scope": "sanidad",
        "default_url": "https://www.sanidad.gob.es/estadEstudios/estadisticas/inforRecopilaciones/listaEspera.htm",
        "format": "pdf",
    },
    "minsan_barometro": {
        "name": "Ministerio de Sanidad y CIS - Barómetro Sanitario",
        "scope": "sanidad",
        "default_url": "https://www.sanidad.gob.es/estadEstudios/estadisticas/BarometroSanitario/home_BS.htm",
        "format": "xlsx",
    },
    "minsan_siap": {
        "name": "Ministerio de Sanidad - Sistema de Información de Atención Primaria (SIAP)",
        "scope": "sanidad",
        "default_url": "https://www.sanidad.gob.es/estadEstudios/estadisticas/estadisticas/estMinisterio/SIAP/home.htm",
        "format": "pdf",
    },
    "minsan_egsp": {
        "name": "Ministerio de Sanidad - Estadística de Gasto Sanitario Público (EGSP)",
        "scope": "sanidad",
        "default_url": "https://www.sanidad.gob.es/estadEstudios/estadisticas/inforRecopilaciones/gastoSanitario2005/home.htm",
        "format": "pdf",
    },
}

PEERS = ["ES", "DE", "FR", "IT", "PT", "EU27_2020"]
ISO3 = {"ES": "ESP", "DE": "DEU", "FR": "FRA", "IT": "ITA", "PT": "PRT"}
AREA_META = {
    "ESP": ("España", "ISO3166-1-alpha-3", "country"),
    "DEU": ("Alemania", "ISO3166-1-alpha-3", "country"),
    "FRA": ("Francia", "ISO3166-1-alpha-3", "country"),
    "ITA": ("Italia", "ISO3166-1-alpha-3", "country"),
    "PRT": ("Portugal", "ISO3166-1-alpha-3", "country"),
    "ES": ("España", "NUTS", "country"),
    "DE": ("Alemania", "NUTS", "country"),
    "FR": ("Francia", "NUTS", "country"),
    "IT": ("Italia", "NUTS", "country"),
    "PT": ("Portugal", "NUTS", "country"),
    "EU27_2020": ("Unión Europea (27, desde 2020)", "EU-aggregate", "aggregate"),
}
# INE region codes (CODAUTO) for SISLE/EGSP labels.
REGIONS = {
    "ANDALUCÍA": ("01", "Andalucía"), "ARAGON": ("02", "Aragón"), "PDO DE ASTURIAS": ("03", "Asturias"),
    "BALEARES": ("04", "Illes Balears"), "CANARIAS": ("05", "Canarias"), "CANTABRIA": ("06", "Cantabria"),
    "CASTILLA Y LEON": ("07", "Castilla y León"), "CASTILLA-LA MANCHA": ("08", "Castilla-La Mancha"),
    "CATALUÑA": ("09", "Cataluña"), "COMUNIDAD VALENCIANA": ("10", "Comunitat Valenciana"),
    "EXTREMADURA": ("11", "Extremadura"), "GALICIA": ("12", "Galicia"), "MADRID": ("13", "Comunidad de Madrid"),
    "MURCIA": ("14", "Región de Murcia"), "C. FORAL DE NAVARRA": ("15", "Navarra"), "PAÍS VASCO": ("16", "País Vasco"),
    "RIOJA": ("17", "La Rioja"), "CEUTA": ("18", "Ceuta"), "MELILLA": ("19", "Melilla"),
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
    if value is None or value == "" or isinstance(value, bool):
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


# ---------------------------------------------------------------- raw fetch

class Raw:
    def __init__(self, name: str, url: str, payload: bytes, retrieved_at: str, kind: str):
        self.name, self.url, self.payload, self.retrieved_at = name, url, payload, retrieved_at
        self.sha256 = sha256_bytes(payload)
        self.path = RAW_DIR / name
        self.data = json.loads(payload) if kind == "json" else list(csv.DictReader(io.StringIO(payload.decode("utf-8"))))


def fetch_raw(name: str, url: str, offline: bool, kind: str = "json") -> Raw:
    path = RAW_DIR / name
    meta_path = RAW_DIR / f"{name}.meta.json"
    if not offline:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, text/csv"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = resp.read()
        if kind == "json":
            json.loads(payload)  # never cache an HTML error page over a good payload
        elif payload.lstrip()[:1] == b"<":
            raise ValueError(f"{name}: HTML where CSV was expected")
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        meta_path.write_text(canonical_json({"url": url, "retrieved_at": now_iso()}), encoding="utf-8")
    if not path.exists():
        raise FileNotFoundError(f"missing raw cache {rel(path)}; run without --offline")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return Raw(name, meta["url"], path.read_bytes(), meta["retrieved_at"], kind)


def fetch_pdf(target: Path, url: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = resp.read()
    if payload[:4] != b"%PDF":
        raise ValueError(f"{url}: not a PDF")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    target.with_name(target.name + ".meta.json").write_text(canonical_json({"url": url, "retrieved_at": now_iso()}), encoding="utf-8")


def fetch_pdfs() -> int:
    """Download every SISLE report linked from the Ministry's current and archive pages, plus the EGSP series."""
    base = "https://www.sanidad.gob.es/estadEstudios/estadisticas/inforRecopilaciones/"
    count = 0
    for page in ("listaEspera.htm", "listaEsperaInfAnt.htm"):
        req = urllib.request.Request(base + page, headers={"User-Agent": USER_AGENT})
        html = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", errors="replace")
        for href in dict.fromkeys(re.findall(r'href="([^"]+\.pdf)"', html)):
            url = urllib.parse.urljoin(base + page, href)
            target = RAW_ROOT / "sisle" / url.rsplit("/", 1)[-1]
            if not target.exists():
                fetch_pdf(target, url)
                count += 1
    fetch_pdf(RAW_ROOT / "egsp/egspGastoReal.pdf", f"{base}gastoSanitario2005/tablasEstEGSP/egspGastoReal.pdf")
    return count + 1


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
    """Insert one release of one indicator, comparing every observation with the previous release.

    Observations may carry their own evidence (`evidence_url`, `evidence_sha256`, `evidence_raw_path`, plus
    `extra_evidence` rows) when the value was read from a document other than the release payload (cited PDFs).
    """
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
            definition["label"], definition.get("definition"), "sanidad", definition["frequency_code"],
            definition.get("frequency_label"), definition["unit_code"], definition.get("unit_label"),
            definition.get("methodology_version"), definition.get("methodology_url"),
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
            start, end = (obs["start"], obs["end"]) if "start" in obs else annual(period)
            obs_rows.append((
                obs_id, series_id, release_id, period, start, end, obs.get("interval_kind", "calendar_year"), value,
                text, obs.get("status"), canonical_json(obs.get("status_labels", [])), "not_provided", ordinal, state,
                prev_id, source_metadata.get("source_updated_at"), int(obs.get("cell_index", 0)),
                canonical_json(obs.get("raw", obs["value"])), ts, ts,
            ))
            evidence = [(
                obs.get("evidence_url") or source_url, obs.get("evidence_sha256") or raw_sha256,
                obs.get("evidence_raw_path") or raw_path, obs["pointer"], obs.get("status_pointer"),
            ), *obs.get("extra_evidence", [])]
            for url, sha, path, value_pointer, status_pointer in evidence:
                ev_rows.append((
                    stable_id("indicator-observation-evidence", obs_id, sha, value_pointer), obs_id, url, sha, path,
                    value_pointer, status_pointer, definition.get("extraction_method", "json_pointer"),
                    EXTRACTOR_VERSION, ts,
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
        INSERT OR IGNORE INTO indicator_observation_evidence (
          indicator_observation_evidence_id, indicator_observation_version_id, source_url,
          source_content_sha256, raw_path, value_json_pointer, status_json_pointer, extraction_method,
          extractor_version, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ev_rows,
    )
    return {"releases": 1, "observations": len(obs_rows)}


def area_series(key: str, geo: str, dimensions: dict[str, Any], observations: list[dict[str, Any]],
                name: str | None = None, system: str | None = None, level: str | None = None) -> dict[str, Any]:
    meta = AREA_META.get(geo, (geo, "ISO3166-1-alpha-3", "country"))
    return {
        "key": key, "geo_code": geo, "geo_name": name or meta[0], "geo_system": system or meta[1],
        "geo_level": level or meta[2], "dimensions": dimensions, "observations": observations,
    }


# ---------------------------------------------------------------- sources -> indicator batches

Batch = tuple[dict[str, Any], list[dict[str, Any]]]
EUROSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"


def eurostat_url(dataset: str, filters: dict[str, list[str]]) -> str:
    return EUROSTAT + dataset + "?" + urllib.parse.urlencode([(k, v) for k, vs in filters.items() for v in vs])


def jsonstat_cells(data: dict[str, Any]) -> Iterable[tuple[dict[str, str], Any, int, str | None]]:
    """Yield (coordinates, value, flat index, status) for every non-empty JSON-stat cell."""
    dims, sizes = data["id"], data["size"]
    inverse = {d: {i: code for code, i in data["dimension"][d]["category"]["index"].items()} for d in dims}
    for flat_text, value in data["value"].items():
        flat, coords = int(flat_text), []
        for size in reversed(sizes):
            coords.append(flat % size)
            flat //= size
        coords.reverse()
        yield ({d: inverse[d][c] for d, c in zip(dims, coords)}, value, int(flat_text),
               data.get("status", {}).get(flat_text))


def eurostat_batches(raw: Raw, dataset: str, indicator_dims: list[str], label: Callable[[dict[str, str]], str],
                     unit_labels: dict[str, str], definition_text: str, unit_dim: str = "unit") -> Iterable[Batch]:
    grouped: dict[tuple[str, ...], dict[str, list[dict[str, Any]]]] = {}
    for coords, value, flat, status in jsonstat_cells(raw.data):
        ind_key = tuple(coords[d] for d in indicator_dims)
        grouped.setdefault(ind_key, {}).setdefault(coords["geo"], []).append({
            "period": coords["time"], "value": value, "pointer": pointer("value", flat), "cell_index": flat,
            "status": status, "status_pointer": pointer("status", flat) if status else None,
            "dims": {d: coords[d] for d in coords if d not in ("time",)},
        })
    for ind_key, by_geo in sorted(grouped.items()):
        coords = dict(zip(indicator_dims, ind_key))
        unit = coords.get(unit_dim) or "PC"
        series = []
        for geo, obs in sorted(by_geo.items()):
            obs.sort(key=lambda o: o["period"])
            dims = obs[0]["dims"]
            for o in obs:
                o.pop("dims")
            series.append(area_series(f"{dataset}|{'|'.join(ind_key)}|{geo}", geo, dims, obs))
        yield {
            "source_id": "eurostat_sdmx", "dataset_code": dataset, "indicator_code": ".".join(ind_key),
            "frequency_code": "A", "frequency_label": "Anual", "unit_code": unit, "unit_label": unit_labels.get(unit, unit),
            "label": label(coords), "definition": definition_text,
            "methodology_url": f"https://ec.europa.eu/eurostat/cache/metadata/en/{dataset.split('_')[0]}_{dataset.split('_')[1]}_esms.htm",
            "source_url": f"https://ec.europa.eu/eurostat/databrowser/view/{dataset}/default/table",
            "source_updated_at": raw.data.get("updated"),
        }, series


# 1. Life expectancy

LE_URL = eurostat_url("demo_mlexpec", {"sex": ["T"], "age": ["Y_LT1"], "unit": ["YR"], "geo": PEERS})


def parse_life_expectancy(raw: Raw) -> Iterable[Batch]:
    yield from eurostat_batches(
        raw, "demo_mlexpec", ["unit", "sex", "age"], lambda c: "Esperanza de vida al nacimiento (años), ambos sexos",
        {"YR": "Años"}, "Esperanza de vida al nacimiento: años que viviría de media una persona nacida ese año si se "
        "mantuvieran las tasas de mortalidad por edad de ese año (esperanza de vida del periodo).",
    )


INE_URL = "https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/1414?nult=200"


def parse_ine(raw: Raw) -> Iterable[Batch]:
    series = []
    for si, s in enumerate(raw.data):
        sex = "T" if "Ambos sexos" in s["Nombre"] else "M" if "Varones" in s["Nombre"] else "F"
        obs = [{"period": str(row["Anyo"]), "value": row["Valor"], "pointer": pointer(si, "Data", i, "Valor"), "cell_index": i}
               for i, row in enumerate(s["Data"]) if row.get("Valor") is not None and not row.get("Secreto")]
        obs.sort(key=lambda o: o["period"])
        series.append(area_series(f"INE|1414|{s['COD']}", "ESP", {"sex": sex, "ine_cod": s["COD"], "ine_nombre": s["Nombre"]}, obs))
    yield {
        "source_id": "ine_wstempus", "dataset_code": "IDB_1414", "indicator_code": "esperanza_vida_nacimiento",
        "frequency_code": "A", "frequency_label": "Anual", "unit_code": "YR", "unit_label": "Años",
        "label": "Esperanza de vida al nacimiento según sexo (INE, Indicadores Demográficos Básicos)",
        "definition": "Esperanza de vida del periodo calculada por el INE con sus tablas de mortalidad.",
        "methodology_url": "https://www.ine.es/dyngs/INEbase/es/operacion.htm?c=Estadistica_C&cid=1254736177003",
        "source_url": "https://www.ine.es/jaxiT3/Tabla.htm?t=1414",
    }, series


OWID_URL = "https://ourworldindata.org/grapher/life-expectancy.csv?v=1&csvType=full&useColumnShortNames=true"
OWID_ENTITIES = {"ESP": "España", "DEU": "Alemania", "FRA": "Francia", "ITA": "Italia", "PRT": "Portugal"}


def parse_owid(raw: Raw) -> Iterable[Batch]:
    by_code: dict[str, list[dict[str, Any]]] = {}
    for i, row in enumerate(raw.data):
        if row["code"] in OWID_ENTITIES and row["life_expectancy_0"]:
            by_code.setdefault(row["code"], []).append({
                "period": row["year"], "value": row["life_expectancy_0"], "cell_index": i,
                "pointer": f"/rows/{i}/life_expectancy_0",  # data row i (0-based, header excluded)
            })
    yield {
        "source_id": "owid_grapher", "dataset_code": "life-expectancy", "indicator_code": "life_expectancy_0",
        "frequency_code": "A", "frequency_label": "Anual", "unit_code": "YR", "unit_label": "Años",
        "label": "Esperanza de vida al nacimiento, serie larga (compilación OWID: Riley; Zijdeman et al.; HMD; ONU WPP)",
        "definition": "Esperanza de vida del periodo. Para estos países y años antiguos procede de la Human Mortality "
        "Database (HMD), cuya descarga exige registro; se lee de la compilación pública de Our World in Data.",
        "extraction_method": "csv_row_column",
        "methodology_url": "https://ourworldindata.org/grapher/life-expectancy",
        "source_url": "https://ourworldindata.org/grapher/life-expectancy",
    }, [area_series(f"owid|life_expectancy_0|{code}", code, {"entity": code}, sorted(obs, key=lambda o: int(o["period"])))
        for code, obs in sorted(by_code.items())]


WB_LE_URL = "https://api.worldbank.org/v2/country/all/indicator/SP.DYN.LE00.IN?format=json&per_page=20000&date=2015:2024"
WB_COUNTRIES_URL = "https://api.worldbank.org/v2/es/country?format=json&per_page=400"  # Spanish names


def parse_worldbank_le(raw: Raw, countries: Raw) -> Iterable[Batch]:
    real = {c["id"]: c["name"] for c in countries.data[1] if c["region"]["id"] != "NA"}
    by_area: dict[str, list[dict[str, Any]]] = {}
    for i, row in enumerate(raw.data[1]):
        if row["value"] is not None and row["countryiso3code"] in real:
            by_area.setdefault(row["countryiso3code"], []).append(
                {"period": row["date"], "value": row["value"], "pointer": pointer(1, i, "value"), "cell_index": i})
    yield {
        "source_id": "worldbank_wdi", "dataset_code": "WDI", "indicator_code": "SP.DYN.LE00.IN",
        "frequency_code": "A", "frequency_label": "Anual", "unit_code": "YR", "unit_label": "Años",
        "label": "Esperanza de vida al nacimiento, todos los países (Banco Mundial)",
        "definition": "Solo países (se excluyen agregados regionales y de renta según la lista de países de la API).",
        "methodology_url": "https://data.worldbank.org/indicator/SP.DYN.LE00.IN",
        "source_url": "https://data.worldbank.org/indicator/SP.DYN.LE00.IN",
        "source_updated_at": raw.data[0].get("lastupdated"),
    }, [area_series(f"WDI|SP.DYN.LE00.IN|{a}", a, {"country": a}, sorted(o, key=lambda x: x["period"]), name=real[a])
        for a, o in sorted(by_area.items())]


# 2. Spending

HF_LABELS = {"TOT_HF": "Gasto sanitario total", "HF1": "Gasto sanitario público y obligatorio (HF1)",
             "HF3": "Pago directo de los hogares (HF3)"}
HF_UNITS = {"PC_GDP": "% del PIB", "EUR_HAB_KP15": "Euros por habitante a precios constantes de 2015",
            "PPS_HAB": "Estándar de poder adquisitivo (PPS) por habitante", "PC_CHE": "% del gasto sanitario corriente"}
HF_URL = eurostat_url("hlth_sha11_hf", {"icha11_hf": list(HF_LABELS), "unit": list(HF_UNITS), "geo": PEERS})


def parse_hf(raw: Raw) -> Iterable[Batch]:
    yield from eurostat_batches(
        raw, "hlth_sha11_hf", ["icha11_hf", "unit"], lambda c: f"{HF_LABELS[c['icha11_hf']]} ({HF_UNITS[c['unit']]})",
        HF_UNITS, "Sistema de Cuentas de Salud (SHA 2011), gasto corriente en salud por régimen de financiación.",
    )


OECD_DATASET = "DSD_SHA@DF_SHA"
OECD_UNITS = {
    "PT_B1GQ": "% del PIB", "EUR_PPP_PS": "Euros por persona en paridad de poder adquisitivo",
    "XDC_PS": "Euros por persona", "PT_EXP_HLTH": "% del gasto sanitario corriente",
}
OECD_PRICES = {"Q": "precios constantes de 2020", "_Z": "", "V": "precios corrientes"}
OECD_SCHEMES = {"HF1": "Gasto sanitario público y obligatorio", "HF3": "Pago directo de los hogares", "_T": "Gasto sanitario total"}
OECD_MEMBERS = [
    "AUS", "AUT", "BEL", "CAN", "CHL", "COL", "CRI", "CZE", "DNK", "EST", "FIN", "FRA", "DEU", "GRC", "HUN", "ISL",
    "IRL", "ISR", "ITA", "JPN", "KOR", "LVA", "LTU", "LUX", "MEX", "NLD", "NZL", "NOR", "POL", "PRT", "SVK", "SVN",
    "ESP", "SWE", "CHE", "TUR", "GBR", "USA",
]


def oecd_url() -> str:
    dims = {
        "MEASURE": ["EXP_HEALTH"], "UNIT_MEASURE": list(OECD_UNITS), "FINANCING_SCHEME": list(OECD_SCHEMES),
        "FUNCTION": ["_T"], "PROVIDER": ["_T"], "MODE_PROVISION": ["_T"], "PRICE_BASE": ["Q", "_Z"],
    }
    return f"https://api.db.nomics.world/v22/series/OECD/{OECD_DATASET}?" + urllib.parse.urlencode(
        {"dimensions": json.dumps(dims, separators=(",", ":")), "observations": 1, "limit": 1000}
    )


def parse_oecd(raw: Raw) -> Iterable[Batch]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for doc_index, doc in enumerate(raw.data["series"]["docs"]):
        dims = doc["dimensions"]
        area, unit, scheme, price = dims["REF_AREA"], dims["UNIT_MEASURE"], dims["FINANCING_SCHEME"], dims["PRICE_BASE"]
        if unit == "XDC_PS" and area != "ESP":
            continue  # national currency only makes sense for Spain (euros)
        statuses = dict(doc.get("observations_attributes", [])).get("OBS_STATUS", [])
        obs = []
        for i, (period, value) in enumerate(zip(doc["period"], doc["value"])):
            if not isinstance(value, (int, float)):
                continue
            status = statuses[i] if i < len(statuses) and statuses[i] else None
            obs.append({
                "period": period, "value": value, "pointer": pointer("series", "docs", doc_index, "value", i), "cell_index": i,
                "status": status, "status_pointer": pointer("series", "docs", doc_index, "observations_attributes", 0, 1, i) if status else None,
                "status_labels": [{"code": status, "label": {"B": "ruptura de serie", "E": "estimación", "P": "provisional"}.get(status, status)}] if status else [],
            })
        grouped.setdefault((scheme, unit, price), []).append(
            area_series(f"{OECD_DATASET}|{doc['series_code']}", area, dims, obs, name=AREA_META.get(area, (area,))[0]))
    for (scheme, unit, price), series in sorted(grouped.items()):
        price_label = OECD_PRICES[price]
        yield {
            "source_id": "oecd_health_statistics", "dataset_code": OECD_DATASET,
            "indicator_code": f"EXP_HEALTH.{scheme}.{price}", "frequency_code": "A", "frequency_label": "Anual",
            "unit_code": unit, "unit_label": OECD_UNITS[unit] + (f", {price_label}" if price_label else ""),
            "label": f"{OECD_SCHEMES[scheme]} ({OECD_UNITS[unit]}{', ' + price_label if price_label else ''})",
            "definition": "OCDE Health Statistics, System of Health Accounts. Leído de la réplica DBnomics porque "
            "sdmx.oecd.org bloquea el acceso por script. Estado B = ruptura de serie, E = estimación.",
            "methodology_url": "https://www.oecd.org/en/data/datasets/oecd-health-statistics.html",
            "source_url": f"https://db.nomics.world/OECD/{OECD_DATASET}",
            "source_updated_at": series and raw.data["series"]["docs"][0].get("indexed_at"),
        }, series


# 4. Doctors

PRS_URL = eurostat_url("hlth_rs_prs2", {"med_spec": ["PHYS"], "unit": ["P_HTHAB"], "geo": PEERS})
PHYSCAT_URL = eurostat_url("hlth_rs_physcat", {"med_spec": ["GEN_PRAC", "GEN", "SPEC", "PAED"], "unit": ["P_HTHAB"], "geo": PEERS})
WSTATUS = {"PRACT": "en ejercicio", "PACT": "profesionalmente activos", "LIC": "colegiados o con licencia"}
SPEC = {"GEN_PRAC": "Médicos de familia (general practitioners)", "GEN": "Médicos generalistas (incluye otros generalistas)",
        "SPEC": "Médicos especialistas", "PAED": "Pediatras"}


def parse_prs(raw: Raw) -> Iterable[Batch]:
    yield from eurostat_batches(
        raw, "hlth_rs_prs2", ["med_spec", "wstatus", "unit"], lambda c: f"Médicos {WSTATUS[c['wstatus']]} por 100.000 habitantes",
        {"P_HTHAB": "Por 100.000 habitantes"}, "Personal sanitario: médicos según situación profesional.",
    )


def parse_physcat(raw: Raw) -> Iterable[Batch]:
    yield from eurostat_batches(
        raw, "hlth_rs_physcat", ["med_spec", "unit"], lambda c: f"{SPEC[c['med_spec']]} por 100.000 habitantes",
        {"P_HTHAB": "Por 100.000 habitantes"}, "Médicos por categoría. Cada país notifica en ejercicio salvo excepciones "
        "(Portugal y otros notifican colegiados), ver metadatos de Eurostat.",
    )


# 5. Outcomes, ageing and workforce beyond the first version

HLYE_URL = eurostat_url("hlth_hlye", {"unit": ["YR"], "hlth_hle": ["HLY_Y0", "LE_Y0", "HLY_Y65"], "sex": ["T"], "geo": PEERS})
APR_URL = eurostat_url("hlth_cd_apr", {"unit": ["RT"], "sex": ["T"], "icd10": ["TOTAL"], "mortalit": ["TOTAL", "PRVT", "TRT"], "geo": PEERS})
PJAN_URL = eurostat_url("demo_pjanind", {"indic_de": ["PC_Y65_MAX", "PC_Y80_MAX"], "geo": PEERS})
NRS_URL = eurostat_url("hlth_rs_prs2", {"med_spec": ["NRS"], "unit": ["P_HTHAB"], "wstatus": ["PRACT"], "geo": PEERS})
PHYS_AGE_URL = eurostat_url("hlth_rs_phys", {"sex": ["T"], "unit": ["NR"], "geo": PEERS})
HLE = {"HLY_Y0": "Años de vida saludable al nacer", "LE_Y0": "Esperanza de vida al nacer (base de los años saludables)",
       "HLY_Y65": "Años de vida saludable a los 65"}
MORT = {"TOTAL": "Mortalidad evitable total", "PRVT": "Mortalidad evitable por prevención",
        "TRT": "Mortalidad evitable por tratamiento"}
AGES = {"PC_Y65_MAX": "Población de 65 años o más (% del total)", "PC_Y80_MAX": "Población de 80 años o más (% del total)"}


def parse_hlye(raw: Raw) -> Iterable[Batch]:
    yield from eurostat_batches(
        raw, "hlth_hlye", ["hlth_hle", "sex", "unit"], lambda c: HLE[c["hlth_hle"]], {"YR": "Años"},
        "Años de vida saludable (indicador SILC de limitación de la actividad por problemas de salud). Se basa en "
        "una pregunta de autopercepción; las diferencias entre países reflejan también cómo responde cada población.",
    )


def parse_apr(raw: Raw) -> Iterable[Batch]:
    yield from eurostat_batches(
        raw, "hlth_cd_apr", ["mortalit", "sex", "icd10", "unit"], lambda c: f"{MORT[c['mortalit']]} (tasa estandarizada por 100.000)",
        {"RT": "Muertes por 100.000 habitantes (tasa estandarizada por edad)"},
        "Mortalidad evitable antes de los 75 años según la lista OCDE/Eurostat: prevenible (salud pública, hábitos) y "
        "tratable (atención sanitaria a tiempo y eficaz).",
    )


def parse_pjan(raw: Raw) -> Iterable[Batch]:
    yield from eurostat_batches(
        raw, "demo_pjanind", ["indic_de"], lambda c: AGES[c["indic_de"]], {"PC": "%"},
        "Estructura de la población a 1 de enero.", unit_dim="unit_missing",
    )


def parse_nrs(raw: Raw) -> Iterable[Batch]:
    yield from eurostat_batches(
        raw, "hlth_rs_prs2", ["med_spec", "wstatus", "unit"], lambda c: "Enfermeras en ejercicio por 100.000 habitantes",
        {"P_HTHAB": "Por 100.000 habitantes"}, "Personal de enfermería con cualificación reconocida por la UE, en ejercicio.",
    )


def parse_phys_age(raw: Raw) -> Iterable[Batch]:
    yield from eurostat_batches(
        raw, "hlth_rs_phys", ["age", "sex", "unit"], lambda c: f"Médicos por edad ({c['age']})", {"NR": "Personas"},
        "Médicos por grupo de edad (cada país notifica su categoría habitual: en ejercicio o profesionalmente activos).",
    )


INE_CCAA_URL = "https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/1448?nult=60"
INE_CCAA = {
    "Andalucía": "01", "Aragón": "02", "Asturias (Principado de)": "03", "Balears (Illes)": "04", "Canarias": "05",
    "Cantabria": "06", "Castilla y León": "07", "Castilla - La Mancha": "08", "Cataluña": "09",
    "Comunitat Valenciana": "10", "Extremadura": "11", "Galicia": "12", "Madrid (Comunidad de)": "13",
    "Murcia (Región de)": "14", "Navarra (Comunidad Foral de)": "15", "País Vasco": "16", "Rioja (La)": "17",
    "Ceuta (Ciudad Autónoma de)": "18", "Melilla (Ciudad Autónoma de)": "19", "Total Nacional": "ES",
}


def parse_ine_ccaa(raw: Raw) -> Iterable[Batch]:
    series = []
    for si, s in enumerate(raw.data):
        parts = [p.strip() for p in s["Nombre"].rstrip(".").split(".")]
        if len(parts) < 3 or parts[2] != "Ambos sexos":
            continue
        code = INE_CCAA.get(parts[1])
        if code is None:
            raise ValueError(f"INE 1448: unknown region {parts[1]!r}")
        obs = [{"period": str(row["Anyo"]), "value": row["Valor"], "pointer": pointer(si, "Data", i, "Valor"), "cell_index": i}
               for i, row in enumerate(s["Data"]) if row.get("Valor") is not None and not row.get("Secreto")]
        name = next((v[1] for k, v in REGIONS.items() if v[0] == code), "España")
        series.append(area_series(f"INE|1448|{s['COD']}", code, {"ine_cod": s["COD"], "ine_nombre": s["Nombre"]},
                                  sorted(obs, key=lambda o: o["period"]), name=name,
                                  system="INE-CODAUTO" if code != "ES" else "NUTS", level="region" if code != "ES" else "country"))
    yield {
        "source_id": "ine_wstempus", "dataset_code": "IDB_1448", "indicator_code": "esperanza_vida_nacimiento_ccaa",
        "frequency_code": "A", "frequency_label": "Anual", "unit_code": "YR", "unit_label": "Años",
        "label": "Esperanza de vida al nacimiento por comunidad autónoma, ambos sexos (INE)",
        "methodology_url": "https://www.ine.es/dyngs/INEbase/es/operacion.htm?c=Estadistica_C&cid=1254736177003",
        "source_url": "https://www.ine.es/jaxiT3/Tabla.htm?t=1448",
    }, series


def dbnomics_url(dataset: str, dims: dict[str, list[str]], limit: int = 1000) -> str:
    return f"https://api.db.nomics.world/v22/series/OECD/{dataset}?" + urllib.parse.urlencode(
        {"dimensions": json.dumps(dims, separators=(",", ":")), "observations": 1, "limit": limit}
    )


PROCEDURES = {"CM131_138": "Cataratas", "CM8151_8153": "Prótesis de cadera", "CM8154": "Prótesis de rodilla",
              "CM683_687_689": "Histerectomía", "CM603_606": "Prostatectomía transuretral", "CM361": "Bypass coronario"}
WAIT_MEASURES = {"WAIT_MEDIAN": "Mediana", "WAIT_MEAN": "Media"}
WAIT_KINDS = {"WTSP": "desde la indicación del especialista hasta la operación", "WTPA": "de los pacientes en lista"}
OECD_WAIT_URL = dbnomics_url("DSD_HEALTH_PROC@DF_WAITING", {
    "MEASURE": list(WAIT_MEASURES), "UNIT_MEASURE": ["D"], "MEDICAL_PROCEDURE": list(PROCEDURES), "WAITING_TIME": list(WAIT_KINDS),
})
OECD_PROT_URL = dbnomics_url("DSD_HEALTH_PROT@DF_HEALTH_PROT", {
    "REF_AREA": ["ESP", "DEU", "FRA", "ITA", "PRT"], "UNIT_MEASURE": ["PT_POP"],
})
CANCERS = {"CCBRNTSR": "Cáncer de mama (mujeres)", "CCCLNTSR": "Cáncer de colon", "CCLUNTSR": "Cáncer de pulmón",
           "CCRCNTSR": "Cáncer de recto"}
OECD_HCQO_URL = dbnomics_url("DSD_HCQO@DF_HCQO", {
    "REF_AREA": ["ESP", "DEU", "FRA", "ITA", "PRT"], "MEASURE": list(CANCERS),
})


def dbnomics_batches(raw: Raw, dataset: str, key_of: Callable[[dict[str, str]], tuple[str, ...] | None],
                     describe: Callable[[tuple[str, ...]], dict[str, Any]]) -> Iterable[Batch]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for doc_index, doc in enumerate(raw.data["series"]["docs"]):
        dims = doc["dimensions"]
        key = key_of(dims)
        if key is None:
            continue
        statuses = dict(doc.get("observations_attributes", [])).get("OBS_STATUS", [])
        obs = []
        for i, (period, value) in enumerate(zip(doc["period"], doc["value"])):
            if not isinstance(value, (int, float)):
                continue
            status = statuses[i] if i < len(statuses) and statuses[i] else None
            obs.append({"period": period, "value": value, "pointer": pointer("series", "docs", doc_index, "value", i),
                        "cell_index": i, "status": status})
        area = dims["REF_AREA"]
        grouped.setdefault(key, []).append(
            area_series(f"{dataset}|{doc['series_code']}", area, dims, obs, name=AREA_META.get(area, (area,))[0]))
    for key, series in sorted(grouped.items()):
        yield {
            "source_id": "oecd_health_statistics", "dataset_code": dataset, "frequency_code": "A", "frequency_label": "Anual",
            "methodology_url": "https://www.oecd.org/en/data/datasets/oecd-health-statistics.html",
            "source_url": f"https://db.nomics.world/OECD/{dataset}", **describe(key),
        }, series


def parse_oecd_wait(raw: Raw) -> Iterable[Batch]:
    yield from dbnomics_batches(
        raw, "DSD_HEALTH_PROC@DF_WAITING",
        lambda d: (d["MEASURE"], d["MEDICAL_PROCEDURE"], d["WAITING_TIME"]),
        lambda k: {
            "indicator_code": ".".join(k), "unit_code": "DAYS", "unit_label": "Días",
            "label": f"{WAIT_MEASURES[k[0]]} de días de espera {WAIT_KINDS[k[2]]}: {PROCEDURES[k[1]]}",
            "definition": "OCDE, tiempos de espera para cirugía programada (solo los países que los notifican). Para "
            "España procede del SISLE-SNS. Leído de la réplica DBnomics.",
        },
    )


def parse_oecd_prot(raw: Raw) -> Iterable[Batch]:
    labels = {"PHINTPHI": "Seguro sanitario voluntario (total)", "PHINDUPI": "Seguro voluntario duplicado (además del público)",
              "PHINCMPI": "Seguro voluntario complementario (copagos)", "PHINPMPI": "Seguro voluntario primario",
              "COVGCMED": "Cobertura pública u obligatoria"}
    yield from dbnomics_batches(
        raw, "DSD_HEALTH_PROT@DF_HEALTH_PROT",
        lambda d: (d["INSURANCE_TYPE"],) if d.get("INSURANCE_TYPE") in labels else None,
        lambda k: {
            "indicator_code": f"HIC.{k[0]}", "unit_code": "PT_POP", "unit_label": "% de la población",
            "label": f"{labels[k[0]]} (% de la población)",
            "definition": "OCDE, cobertura sanitaria de la población por tipo de seguro. Leído de la réplica DBnomics.",
        },
    )


def parse_oecd_hcqo(raw: Raw) -> Iterable[Batch]:
    yield from dbnomics_batches(
        raw, "DSD_HCQO@DF_HCQO",
        lambda d: (d["MEASURE"], d["SEX"]) if d.get("MEASURE") in CANCERS and d.get("STATISTICAL_OPERATION") == "OBS" else None,
        lambda k: {
            "indicator_code": f"{k[0]}.{k[1]}", "unit_code": "PC", "unit_label": "% de pacientes",
            "label": f"Supervivencia neta a cinco años: {CANCERS[k[0]]} ({'total' if k[1] == '_T' else k[1]})",
            "definition": "OCDE, calidad y resultados (programa CONCORD). Periodos de diagnóstico de 5 años "
            "etiquetados con su último año (2004 = 2000-2004).",
        },
    )


# 6. Barómetro Sanitario (Ministerio de Sanidad y CIS): xlsx files read cell by cell.

XLSX_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
           "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
BS_BASE = "https://www.sanidad.gob.es/estadEstudios/estadisticas/BarometroSanitario/"
BAROMETRO = {
    2022: BS_BASE + "Barom_Sanit_2022/BS_Total_Oleadas_Estudio_8822.xlsx",
    2023: BS_BASE + "Barom_Sanit_2023/Barom_Sanit_2023_totales/BS_Total_Oleadas_Estudio_8823.xlsx",
    2024: BS_BASE + "Barom_Sanit_2024/BS_2024_Totales/BS_Total_Oleadas_Estudio_8824.xlsx",
    2025: BS_BASE + "Barom_Sanit_2025/Totales/BS-Total-Oleadas-Estudio_8825.xlsx",
}
BAROMETRO_HIST = BS_BASE + "Barom_Sanit_2025/Totales/BS_1998-2025_Principales_variables_CCAA.xlsx"
BS_REGIONS = {
    "Andalucía": "01", "Aragón": "02", "Asturias": "03", "Baleares": "04", "Canarias": "05", "Cantabria": "06",
    "Castilla y León": "07", "Castilla-La Mancha": "08", "Cataluña": "09", "Comunidad Valenciana": "10",
    "Extremadura": "11", "Galicia": "12", "Madrid": "13", "Murcia": "14", "Navarra": "15", "País Vasco": "16",
    "Rioja": "17", "Ceuta": "18", "Melilla": "19", "TOTAL": "ES",
}


def read_xlsx(payload: bytes) -> dict[str, list[tuple[int, dict[str, str | None]]]]:
    """Minimal OOXML reader (stdlib only): {sheet name: [(row number, {column letter: text})]}."""
    import xml.etree.ElementTree as ET
    import zipfile

    z = zipfile.ZipFile(io.BytesIO(payload))
    m = "{%s}" % XLSX_NS["m"]
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", XLSX_NS):
            shared.append("".join(t.text or "" for t in si.iter(m + "t")))
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    sheets = {}
    for sheet in ET.fromstring(z.read("xl/workbook.xml")).find("m:sheets", XLSX_NS):
        target = rels[sheet.get("{%s}id" % XLSX_NS["r"])].lstrip("/")
        target = target if target.startswith("xl/") else "xl/" + target
        rows = []
        for row in ET.fromstring(z.read(target)).iter(m + "row"):
            cells = {}
            for c in row.findall("m:c", XLSX_NS):
                col = re.match(r"[A-Z]+", c.get("r")).group()
                v = c.find("m:v", XLSX_NS)
                if v is None:
                    inline = c.find("m:is", XLSX_NS)
                    cells[col] = "".join(t.text or "" for t in inline.iter(m + "t")) if inline is not None else None
                else:
                    cells[col] = shared[int(v.text)] if c.get("t") == "s" else v.text
            rows.append((int(row.get("r")), cells))
        sheets[sheet.get("name")] = rows
    return sheets


def fetch_binary(folder: str, url: str, offline: bool) -> tuple[Path, bytes, dict[str, str]]:
    target = RAW_ROOT / folder / url.rsplit("/", 1)[-1]
    meta_path = target.with_name(target.name + ".meta.json")
    if not offline:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = resp.read()
        if payload[:2] != b"PK":
            raise ValueError(f"{url}: not an xlsx file")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        meta_path.write_text(canonical_json({"url": url, "retrieved_at": now_iso()}), encoding="utf-8")
    if not target.exists():
        raise FileNotFoundError(f"missing raw cache {rel(target)}; run without --offline")
    return target, target.read_bytes(), json.loads(meta_path.read_text(encoding="utf-8"))


def gp_access(year: int, sheets: dict) -> list[dict[str, Any]]:
    """GP appointment question (asked since 2022): share seen the same or next day, and mean days for the rest."""
    rows = sheets["Resultados"]
    start = next(r for r, c in rows if "hasta que le/la atendió el/la médico/a de familia" in str(c.get("A") or ""))
    block = [(r, c) for r, c in rows if start < r <= start + 45]
    found = {}
    for r, c in block:
        label = str(c.get("A") or "")
        if label.startswith("Le/la atendió ese mismo día"):
            found["same_day"] = (r, c.get("B"))
        elif label.startswith("Le/la atendió al día siguiente"):
            found["next_day"] = (r, c.get("B"))
        elif label.startswith("Pasó más de un día porque no había cita antes"):
            found["no_slot"] = (r, c.get("B"))
        elif label.startswith("Media") and "mean_days" not in found:
            found["mean_days"] = (r, c.get("B"))
    if set(found) != {"same_day", "next_day", "no_slot", "mean_days"}:
        raise ValueError(f"Barómetro {year}: GP access block incomplete: {sorted(found)}")
    return [{"metric": k, "row": r, "value": float(v)} for k, (r, v) in found.items()]


def load_barometro(conn: sqlite3.Connection, snapshot_date: str, offline: bool) -> dict[str, int]:
    totals = {"releases": 0, "observations": 0}
    labels = {
        "same_day": ("pct_cita_mf_mismo_dia", "PC", "%", "Atendidos por su médico de familia el mismo día que pidieron cita"),
        "next_day": ("pct_cita_mf_dia_siguiente", "PC", "%", "Atendidos por su médico de familia al día siguiente"),
        "no_slot": ("pct_cita_mf_sin_hueco", "PC", "%", "Esperaron más de un día porque no había cita antes"),
        "mean_days": ("dias_medios_cita_mf", "DAYS", "Días", "Días de espera para el médico de familia (media de quienes esperaron más de un día)"),
    }
    per_metric: dict[str, list[tuple[int, dict, Path, bytes, dict]]] = {}
    for year, url in sorted(BAROMETRO.items()):
        path, payload, meta = fetch_binary("barometro", url, offline)
        for item in gp_access(year, read_xlsx(payload)):
            per_metric.setdefault(item["metric"], []).append((year, item, path, payload, meta))
    for metric, items in per_metric.items():
        code, unit, unit_label, label = labels[metric]
        obs = [{
            "period": str(year), "value": item["value"], "cell_index": item["row"],
            "pointer": f"xlsx:Resultados!B{item['row']}", "evidence_url": meta["url"],
            "evidence_sha256": sha256_bytes(payload), "evidence_raw_path": rel(path),
        } for year, item, path, payload, meta in items]
        bundle = "".join(sha256_bytes(p) for _, _, _, p, _ in items)
        definition = {
            "source_id": "minsan_barometro", "dataset_code": "BS.totales", "indicator_code": code,
            "frequency_code": "A", "frequency_label": "Anual (tres oleadas)", "unit_code": unit, "unit_label": unit_label,
            "label": label, "extraction_method": "xlsx_cell",
            "definition": "Barómetro Sanitario (Ministerio de Sanidad y CIS), encuesta a la población. Pregunta a quienes "
            "consultaron con su médico de familia de la sanidad pública en los últimos doce meses; existe desde 2022.",
            "methodology_url": "https://www.sanidad.gob.es/estadEstudios/estadisticas/BarometroSanitario/home_BS.htm",
            "source_url": "https://www.sanidad.gob.es/estadEstudios/estadisticas/inforRecopilaciones/barometro/home.htm",
        }
        counts = load_indicator(conn, definition, sha256_bytes(bundle.encode()), len(bundle), "etl/data/raw/health/barometro/",
                                definition["source_url"], snapshot_date,
                                {"retrieved_at": max(m["retrieved_at"] for *_, m in items)},
                                [area_series(f"bs|{code}|ES", "ES", {"scope": "nacional"}, obs, name="España", system="NUTS", level="country")])
        for k in totals:
            totals[k] += counts[k]
    # Perception of waiting lists by region, 2000-2025 (P. 16 of the historical workbook).
    path, payload, meta = fetch_binary("barometro", BAROMETRO_HIST, offline)
    rows = read_xlsx(payload)["P 16"]
    blocks, header = [], None
    for r, c in rows:
        if c.get("B") in ("1998", "1999") or (c.get("B") == "1998"):
            header = {col: v for col, v in c.items() if col != "A" and v}
            blocks.append({"header": header, "rows": []})
        elif header and c.get("A") and str(c["A"]).strip() in BS_REGIONS:
            blocks[-1]["rows"].append((r, str(c["A"]).strip(), c))
    meaning = {0: ("pct_listas_mejoran", "Creen que las listas de espera han mejorado en el último año"),
               1: ("pct_listas_empeoran", "Creen que las listas de espera han empeorado en el último año"),
               2: ("pct_listas_igual", "Creen que las listas de espera siguen igual")}
    for index, (code, label) in meaning.items():
        series = []
        for r, region, cells in blocks[index]["rows"]:
            obs = [{"period": year, "value": cells.get(col), "cell_index": r, "pointer": f"xlsx:P 16!{col}{r}"}
                   for col, year in blocks[index]["header"].items() if decimal_text(cells.get(col)) is not None]
            geo = BS_REGIONS[region]
            name = "España" if geo == "ES" else next(v[1] for v in REGIONS.values() if v[0] == geo)
            series.append(area_series(f"bs-hist|{code}|{geo}", geo, {"bs_label": region}, obs, name=name,
                                      system="NUTS" if geo == "ES" else "INE-CODAUTO", level="country" if geo == "ES" else "region"))
        definition = {
            "source_id": "minsan_barometro", "dataset_code": "BS.serie_1998_2025.P16", "indicator_code": code,
            "frequency_code": "A", "frequency_label": "Anual", "unit_code": "PC", "unit_label": "% de encuestados", "label": label,
            "extraction_method": "xlsx_cell",
            "definition": "Barómetro Sanitario, P. 16: «En general, ¿cree Ud. que, durante los últimos doce meses, el problema "
            "de las listas de espera…?». Es una opinión, no una medida de la espera. Sin encuesta en 2001, 2020 y 2021.",
            "methodology_url": "https://www.sanidad.gob.es/estadEstudios/estadisticas/BarometroSanitario/home_BS.htm",
            "source_url": meta["url"],
        }
        counts = load_indicator(conn, definition, sha256_bytes(payload), len(payload), rel(path), meta["url"], snapshot_date,
                                {"retrieved_at": meta["retrieved_at"]}, series)
        for k in totals:
            totals[k] += counts[k]
    return totals


def load_siap(conn: sqlite3.Connection, snapshot_date: str) -> dict[str, int]:
    path = MANUAL_DIR / "siap_2023.json"
    payload = path.read_bytes()
    data = json.loads(payload)
    src = data["source"]
    raw_path, _ = check_pdf(src["file"], "siap", src["sha256"])
    totals = {"releases": 0, "observations": 0}
    for index, row in enumerate(data["values"]):
        definition = {
            "source_id": "minsan_siap", "dataset_code": "SIAP.resumen_grafico", "indicator_code": row["code"],
            "frequency_code": "A", "frequency_label": "Anual", "unit_code": row["unit"], "unit_label": row["unit_label"],
            "label": row["label"], "extraction_method": "curated_citation", "definition": src["note"],
            "methodology_url": src["page"], "source_url": src["page"],
        }
        obs = [{"period": str(row["year"]), "value": row["value"], "cell_index": index, "raw": row,
                "pointer": f"pdf:page={row['page']};text={row['quote']}", "status_pointer": pointer("values", index),
                "evidence_url": src["url"], "evidence_sha256": src["sha256"], "evidence_raw_path": raw_path}]
        counts = load_indicator(conn, definition, sha256_bytes(payload), len(payload), rel(path), src["page"], snapshot_date,
                                {"retrieved_at": src["retrieved_at"]},
                                [area_series(f"siap|{row['code']}|ES", "ES", {}, obs, name="España (SNS)", system="NUTS", level="country")])
        for k in totals:
            totals[k] += counts[k]
    return totals


API_SOURCES: list[tuple[str, str, str, Callable[..., Iterable[Batch]]]] = [
    ("eurostat_demo_mlexpec.json", LE_URL, "json", parse_life_expectancy),
    ("ine_idb_1414.json", INE_URL, "json", parse_ine),
    ("owid_life_expectancy.csv", OWID_URL, "csv", parse_owid),
    ("eurostat_hlth_sha11_hf.json", HF_URL, "json", parse_hf),
    ("oecd_sha_dbnomics.json", oecd_url(), "json", parse_oecd),
    ("eurostat_hlth_rs_prs2.json", PRS_URL, "json", parse_prs),
    ("eurostat_hlth_rs_physcat.json", PHYSCAT_URL, "json", parse_physcat),
    ("eurostat_hlth_hlye.json", HLYE_URL, "json", parse_hlye),
    ("eurostat_hlth_cd_apr.json", APR_URL, "json", parse_apr),
    ("eurostat_demo_pjanind.json", PJAN_URL, "json", parse_pjan),
    ("eurostat_hlth_rs_prs2_nrs.json", NRS_URL, "json", parse_nrs),
    ("eurostat_hlth_rs_phys_age.json", PHYS_AGE_URL, "json", parse_phys_age),
    ("ine_idb_1448.json", INE_CCAA_URL, "json", parse_ine_ccaa),
    ("oecd_waiting_dbnomics.json", OECD_WAIT_URL, "json", parse_oecd_wait),
    ("oecd_health_prot_dbnomics.json", OECD_PROT_URL, "json", parse_oecd_prot),
    ("oecd_hcqo_cancer_dbnomics.json", OECD_HCQO_URL, "json", parse_oecd_hcqo),
]


# ---------------------------------------------------------------- curated PDF data (Ministerio de Sanidad)

def check_pdf(file_name: str, folder: str, expected_sha: str) -> tuple[str, int]:
    """The cited PDF must be in the raw cache with the sha256 recorded when the values were extracted."""
    path = RAW_ROOT / folder / file_name
    if path.exists():
        actual = sha256_bytes(path.read_bytes())
        if actual != expected_sha:
            raise SystemExit(f"{rel(path)} changed since extraction ({actual} != {expected_sha}); re-run "
                             "scripts/extract_health_pdfs_es.py and review the diff")
        return rel(path), path.stat().st_size
    return f"etl/data/raw/health/{folder}/{file_name}", 0


SISLE_METRICS = {
    "surgery": {
        "patients": ("pacientes_espera_quirurgica", "PERSONS", "Pacientes", "Pacientes en lista de espera estructural para cirugía"),
        "rate_per_1000": ("tasa_espera_quirurgica", "P_THAB", "Por 1.000 habitantes", "Pacientes en espera quirúrgica por 1.000 habitantes"),
        "pct_over_6_months": ("pct_mas_6_meses_quirurgica", "PC", "%", "Porcentaje de pacientes con más de 6 meses de espera quirúrgica"),
        "mean_days": ("dias_medios_espera_quirurgica", "DAYS", "Días", "Tiempo medio de espera para cirugía (días)"),
    },
    "consultations": {
        "rate_per_1000": ("tasa_espera_consultas", "P_THAB", "Por 1.000 habitantes", "Pacientes esperando primera consulta de especialista por 1.000 habitantes"),
        "mean_days": ("dias_medios_espera_consultas", "DAYS", "Días", "Tiempo medio de espera para primera consulta de especialista (días)"),
        "pct_over_60_days": ("pct_mas_60_dias_consultas", "PC", "%", "Porcentaje de pacientes con cita a más de 60 días"),
    },
    "surgery_selected_by_region": {
        "patients": ("pacientes_procesos_seleccionados", "PERSONS", "Pacientes", "Pacientes en espera de procesos quirúrgicos seleccionados (RD 605/2003)"),
        "rate_per_1000": ("tasa_procesos_seleccionados", "P_THAB", "Por 1.000 habitantes", "Pacientes en espera de procesos seleccionados por 1.000 habitantes"),
        "pct_over_6_months": ("pct_mas_6_meses_procesos_seleccionados", "PC", "%", "Porcentaje con más de 6 meses, procesos seleccionados"),
        "mean_days": ("dias_medios_procesos_seleccionados", "DAYS", "Días", "Tiempo medio de espera de procesos seleccionados (días)"),
    },
}


def load_sisle(conn: sqlite3.Connection, snapshot_date: str) -> dict[str, int]:
    path = MANUAL_DIR / "sisle_sns.json"
    payload = path.read_bytes()
    data = json.loads(payload)
    reports = {r["file"]: r for r in data["reports"]}
    for r in data["reports"]:
        check_pdf(r["file"], "sisle", r["sha256"])
    breaks: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for b in data["breaks"]:
        for target in b["series"]:
            series_name, _, metric = target.partition(":")
            breaks.setdefault((series_name, b["cut_date"]), []).append({**b, "metric": metric or None})
    revisions = {(r["series"], r["cut_date"]): r for r in data.get("revisions", [])}
    totals = {"releases": 0, "observations": 0}
    for series_name, metrics in SISLE_METRICS.items():
        for metric, (code, unit, unit_label, label) in metrics.items():
            by_geo: dict[str, list[dict[str, Any]]] = {}
            for index, row in enumerate(data[series_name]):
                if row.get(metric) is None:
                    continue
                report = reports[row["report"]]
                region = row.get("region", "TOTAL")
                labels = [
                    {"code": "break", "label": b["label"], "quote": b["quote"], "report": b["report"], "page": b["page"]}
                    for b in breaks.get((series_name, row["cut_date"]), []) if b["metric"] in (None, metric)
                ]
                extra_evidence = []
                revision = revisions.get((series_name, row["cut_date"])) if region == "TOTAL" else None
                if revision and metric in revision["initial"]:
                    labels.append({"code": "rectified", "label": revision["label"], "initial_value": revision["initial"][metric]})
                    nota = reports.get(revision["report"])
                    if nota:
                        extra_evidence.append((nota["url"], nota["sha256"], f"etl/data/raw/health/sisle/{nota['file']}",
                                               f"pdf:page={revision['quotes'][0]['page']}", None))
                for footnote in row.get("footnotes", []):
                    labels.append({"code": "footnote", "label": footnote})
                by_geo.setdefault(region, []).append({
                    "period": row["cut_date"], "start": row["cut_date"], "end": row["cut_date"], "interval_kind": "point_in_time",
                    "value": row[metric], "cell_index": index, "raw": row,
                    "status": "break" if any(l["code"] == "break" for l in labels) else ("rectified" if revision and metric in revision["initial"] else None),
                    "status_labels": labels,
                    "pointer": f"pdf:page={row['page']};row={row['quote']}",
                    "status_pointer": pointer(series_name, index),
                    "evidence_url": report["url"], "evidence_sha256": report["sha256"],
                    "evidence_raw_path": f"etl/data/raw/health/sisle/{report['file']}",
                    "extra_evidence": extra_evidence,
                })
            series = []
            for region, obs in sorted(by_geo.items()):
                if region == "TOTAL":
                    series.append(area_series(f"sisle|{series_name}|{metric}|ES", "ES", {"scope": "SNS"}, obs, name="España (SNS)", system="NUTS", level="country"))
                else:
                    ine, name = REGIONS[region]
                    series.append(area_series(f"sisle|{series_name}|{metric}|{ine}", ine, {"sisle_label": region}, obs,
                                              name=name, system="INE-CODAUTO", level="region"))
            definition = {
                "source_id": "minsan_sisle_sns", "dataset_code": f"SISLE.{series_name}", "indicator_code": code,
                "frequency_code": "S", "frequency_label": "Semestral (corte a 30 de junio y 31 de diciembre)",
                "unit_code": unit, "unit_label": unit_label, "label": label, "extraction_method": "pdftotext_layout_total_row",
                "definition": "Lista de espera estructural del SNS según el RD 605/2003, leída de la fila TOTAL de cada "
                "informe semestral «Indicadores resumen». Población de referencia: tarjeta sanitaria.",
                "methodology_url": data["source"]["page"], "source_url": data["source"]["page"],
            }
            counts = load_indicator(conn, definition, sha256_bytes(payload), len(payload), rel(path),
                                    data["source"]["page"], snapshot_date,
                                    {"retrieved_at": max(r["retrieved_at"] for r in data["reports"]), "method": data["source"]["method"]},
                                    series)
            for k in totals:
                totals[k] += counts[k]
    return totals


def load_egsp(conn: sqlite3.Connection, snapshot_date: str) -> dict[str, int]:
    path = MANUAL_DIR / "egsp_ccaa.json"
    payload = path.read_bytes()
    data = json.loads(payload)
    src = data["source"]
    raw_path, _ = check_pdf(src["file"], "egsp", src["sha256"])
    series = []
    for index, row in enumerate(data["rows"]):
        obs = [{
            "period": year, "value": value, "cell_index": index,
            "status": "p" if int(year) in src["provisional_years"] else None,
            "status_labels": [{"code": "p", "label": "cifra provisional"}] if int(year) in src["provisional_years"] else [],
            "pointer": f"pdf:page={row['page']};row={row['label']};year={year}", "status_pointer": pointer("rows", index, "values", year),
            "evidence_url": src["url"], "evidence_sha256": src["sha256"], "evidence_raw_path": raw_path, "raw": {"quote": row["quote"]},
        } for year, value in sorted(row["values"].items())]
        if row["region"] == "TOTAL":
            series.append(area_series("egsp|ccaa|TOTAL", "ES-CCAA", {"sector": "Comunidades Autónomas"}, obs,
                                      name="Comunidades autónomas (total del sector)", system="NUTS", level="country"))
        else:
            ine, name = REGIONS[row["region"]]
            series.append(area_series(f"egsp|ccaa|{ine}", ine, {"egsp_label": row["label"]}, obs, name=name,
                                      system="INE-CODAUTO", level="region"))
    definition = {
        "source_id": "minsan_egsp", "dataset_code": "EGSP", "indicator_code": "gasto_sanitario_ccaa_por_habitante",
        "frequency_code": "A", "frequency_label": "Anual", "unit_code": "EUR_HAB", "unit_label": "Euros corrientes por habitante",
        "label": "Gasto sanitario público consolidado por habitante, sector Comunidades Autónomas",
        "definition": src["table"] + ". " + src["unit"] + ". No incluye el gasto de la Administración Central, la "
        "Seguridad Social (mutualidades) ni las corporaciones locales.", "extraction_method": "pdftotext_layout_row",
        "methodology_url": src["page"], "source_url": src["page"],
    }
    return load_indicator(conn, definition, sha256_bytes(payload), len(payload), rel(path), src["page"], snapshot_date,
                          {"retrieved_at": src["retrieved_at"]}, series)


# ---------------------------------------------------------------- main

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--offline", action="store_true", help="load from the raw cache without network")
    parser.add_argument("--fetch-pdfs", action="store_true", help="also download the Ministry's SISLE/EGSP PDFs")
    parser.add_argument("--snapshot-date", default=datetime.now(timezone.utc).date().isoformat())
    args = parser.parse_args()

    if args.fetch_pdfs and not args.offline:
        print(f"fetched {fetch_pdfs()} PDFs; run scripts/extract_health_pdfs_es.py and review the diff", file=sys.stderr)
    args.db.parent.mkdir(parents=True, exist_ok=True)
    conn = open_db(args.db)
    apply_schema(conn, DEFAULT_SCHEMA)
    seed_sources(conn)
    seed_sources_from_config(conn, LOCAL_SOURCES)
    conn.execute("PRAGMA foreign_keys = ON")
    report: dict[str, Any] = {"db": rel(args.db), "snapshot_date": args.snapshot_date, "indicators": {}}
    with conn:
        countries = fetch_raw("worldbank_countries.json", WB_COUNTRIES_URL, args.offline)
        sources = [*API_SOURCES, ("worldbank_SP.DYN.LE00.IN.json", WB_LE_URL, "json", lambda raw: parse_worldbank_le(raw, countries))]
        for name, url, kind, parse in sources:
            raw = fetch_raw(name, url, args.offline, kind)
            for definition, series in parse(raw):
                meta = {"retrieved_at": raw.retrieved_at, "source_updated_at": definition.pop("source_updated_at", None)}
                counts = load_indicator(conn, definition, raw.sha256, len(raw.payload), rel(raw.path), raw.url,
                                        args.snapshot_date, meta, series)
                report["indicators"][f"{definition['source_id']}:{definition['indicator_code']}:{definition['unit_code']}"] = counts
        report["sisle"] = load_sisle(conn, args.snapshot_date)
        report["egsp"] = load_egsp(conn, args.snapshot_date)
        report["barometro"] = load_barometro(conn, args.snapshot_date, args.offline)
        report["siap"] = load_siap(conn, args.snapshot_date)
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk:
        raise SystemExit(f"foreign_key_check failed: {fk[:5]}")
    conn.close()
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
