#!/usr/bin/env python3
"""Ingest Spain's housing series into SQLite (indicator contract v1) for /visualizaciones/vivienda/.

Boundaries (same pattern as scripts/ingest_public_finance_es.py, copied rather than imported so each lane versions
its own extractor):
- ingest: fetch each official file/API, keep the raw payload under etl/data/raw/housing/apis/ (+ URL, retrieval
  time); `--offline` reuses that cache. Sources: Ministerio de Vivienda (MIVAU boletín estadístico, XLS), Banco de
  España (indicadores del mercado de la vivienda, CSV), INE (API Tempus), Eurostat (JSON-stat API) and OECD (read
  from the DBnomics mirror because sdmx.oecd.org blocks scripted access).
- normalize/load: every series lands in indicator_definitions -> indicator_releases -> indicator_series_versions ->
  indicator_observation_versions -> indicator_observation_evidence. A new raw payload is a new release; each
  observation is compared with the previous release (unchanged/changed/deleted). Evidence points at the raw cell
  (JSON pointer, or sheet/row/col for XLS and row/col for CSV) + sha256.
- curated values with citations (etl/data/manual/housing/*.json: purchase-tax rates per norm, 1950/1960 census
  tenure, young households' ownership, social rental stock) load as indicators too; when a curated row names the
  original document it was transcribed from, a second evidence row points at that stored file and its sha256.

MIVAU publishes legacy .xls; parsing needs xlrd: `just housing-refresh` runs this through `uv run --with xlrd`.
The published site JSON is derived from this DB by scripts/export_public_viz_housing.py.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
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

DEFAULT_DB = REPO_ROOT / "etl/data/staging/housing-es.db"
RAW_DIR = REPO_ROOT / "etl/data/raw/housing/apis"
MANUAL_DIR = REPO_ROOT / "etl/data/manual/housing"
USER_AGENT = "Mozilla/5.0 (compatible; vota-con-la-chola-etl/1.0; +https://votaconlachola.org)"
EXTRACTOR_VERSION = "ingest_housing_es/1"
DOMAIN = "vivienda"
NUL = "\x00"
XLS_MAGIC = bytes.fromhex("d0cf11e0a1b11ae1")

LOCAL_SOURCES: dict[str, dict[str, str]] = {
    "mivau_boletin": {
        "name": "Ministerio de Vivienda y Agenda Urbana - Boletín estadístico online (XLS)",
        "scope": "vivienda",
        "default_url": "https://apps.fomento.gob.es/BoletinOnline2/",
        "format": "xls",
    },
    "bde_indicadores_vivienda": {
        "name": "Banco de España - Indicadores del mercado de la vivienda (si_1_5)",
        "scope": "vivienda",
        "default_url": "https://www.bde.es/webbe/es/estadisticas/compartido/datos/csv/si_1_5.csv",
        "format": "csv",
    },
    "ine_tempus": {
        "name": "INE - API Tempus (series de la Encuesta Trimestral de Coste Laboral)",
        "scope": "vivienda",
        "default_url": "https://servicios.ine.es/wstempus/js/ES/",
        "format": "json",
    },
    "oecd_dbnomics": {
        "name": "OCDE - salarios medios y precios de la vivienda (réplica DBnomics)",
        "scope": "vivienda",
        "default_url": "https://db.nomics.world/OECD",
        "format": "json",
    },
    "eurostat_sdmx": {
        "name": "Eurostat - Indicadores outcomes (API/SDMX)",
        "scope": "outcomes",
        "default_url": "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/",
        "format": "json",
    },
    "vclc_housing_curated": {
        "name": "Vivienda: valores curados con su norma o documento oficial citado",
        "scope": "vivienda",
        "default_url": "https://www.boe.es/",
        "format": "json",
    },
}

PEERS = ["ES", "EU27_2020", "DE", "FR", "IT", "PT"]
GEO_META = {
    "ES": ("España", "NUTS", "country"),
    "ESP": ("España", "ISO3166-1-alpha-3", "country"),
    "EU27_2020": ("Unión Europea (27, desde 2020)", "EU-aggregate", "aggregate"),
    "DE": ("Alemania", "NUTS", "country"),
    "DEU": ("Alemania", "ISO3166-1-alpha-3", "country"),
    "FR": ("Francia", "NUTS", "country"),
    "FRA": ("Francia", "ISO3166-1-alpha-3", "country"),
    "IT": ("Italia", "NUTS", "country"),
    "ITA": ("Italia", "ISO3166-1-alpha-3", "country"),
    "PT": ("Portugal", "NUTS", "country"),
    "PRT": ("Portugal", "ISO3166-1-alpha-3", "country"),
    "OECD": ("OCDE", "OECD-aggregate", "aggregate"),
    "EU": ("Unión Europea", "EU-aggregate", "aggregate"),
    "ES-MD": ("Comunidad de Madrid", "ISO3166-2", "region"),
    "ES-CT": ("Cataluña", "ISO3166-2", "region"),
    "ES-AN": ("Andalucía", "ISO3166-2", "region"),
    "ES-VC": ("Comunitat Valenciana", "ISO3166-2", "region"),
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
    if value is None or value in ("NA", "_", "") or isinstance(value, bool):
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


def period_bounds(period: str) -> tuple[str, str, str]:
    """(start, end, interval_kind) for 'YYYY', 'YYYY-Qn', 'YYYY-MM' or 'YYYY-Hn'."""
    if "-Q" in period:
        year, q = period.split("-Q")
        start_m, end_m = 3 * int(q) - 2, 3 * int(q)
        return f"{year}-{start_m:02d}-01", month_end(int(year), end_m), "calendar_quarter"
    if "-H" in period:
        year, h = period.split("-H")
        return (f"{year}-01-01", f"{year}-06-30", "calendar_half") if h == "1" else (f"{year}-07-01", f"{year}-12-31", "calendar_half")
    if len(period) == 7:
        year, month = int(period[:4]), int(period[5:])
        return f"{period}-01", month_end(year, month), "calendar_month"
    return f"{period}-01-01", f"{period}-12-31", "calendar_year"


def month_end(year: int, month: int) -> str:
    days = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return f"{year}-{month:02d}-{days[month - 1]:02d}"


# ---------------------------------------------------------------- raw fetch

class Raw:
    def __init__(self, name: str, url: str, payload: bytes, retrieved_at: str):
        self.name, self.url, self.payload, self.retrieved_at = name, url, payload, retrieved_at
        self.sha256 = sha256_bytes(payload)
        self.path = RAW_DIR / name

    @property
    def data(self) -> Any:
        return json.loads(self.payload)


def check_payload(name: str, payload: bytes) -> None:
    """Never cache an HTML error page over a good payload."""
    if name.endswith(".xls"):
        if not payload.startswith(XLS_MAGIC):
            raise ValueError(f"{name}: expected a legacy .xls (OLE2) file, got {payload[:40]!r}")
    elif name.endswith(".csv"):
        if payload.lstrip()[:15].lower().startswith((b"<!doctype", b"<html")):
            raise ValueError(f"{name}: HTML page instead of CSV")
    else:
        json.loads(payload)


def fetch_raw(name: str, url: str, offline: bool) -> Raw:
    path = RAW_DIR / name
    meta_path = RAW_DIR / f"{name}.meta.json"
    if not offline:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = resp.read()
        check_payload(name, payload)
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
    prev_obs: dict[tuple[str, str], tuple[str, str | None, str | None, int, str, str, str]] = {}
    if previous_release_id:
        for key, period, obs_id, value, text, ordinal, state, start, end, kind in conn.execute(
            """
            SELECT s.stable_series_key, o.period_label, o.indicator_observation_version_id, o.value_decimal,
                   o.value_text, o.revision_ordinal, o.revision_state, o.period_start, o.period_end, o.interval_kind
            FROM indicator_observation_versions o
            JOIN indicator_series_versions s USING (indicator_series_version_id)
            WHERE o.indicator_release_id = ?
            """,
            (previous_release_id,),
        ):
            if state != "deleted":
                prev_obs[(key, period)] = (obs_id, value, text, ordinal, start, end, kind)
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
            text = None if value is not None else (None if obs["value"] in (None, "", "_") else str(obs["value"]))
            if value is None and text is None:
                continue
            period = str(obs["period"])
            if (item["key"], period) in seen:
                raise ValueError(f"duplicate observation {definition['indicator_code']} {item['key']} {period}")
            seen.add((item["key"], period))
            start, end, kind = period_bounds(period)
            prior = prev_obs.get((item["key"], period))
            if prior is None:
                state, ordinal, prev_id = "baseline", 1, None
            else:
                same = prior[1] == value and prior[2] == text
                state, ordinal, prev_id = ("unchanged" if same else "changed"), prior[3] + (0 if same else 1), prior[0]
            obs_id = stable_id("indicator-observation-version", series_id, period, value, text)
            obs_rows.append((
                obs_id, series_id, release_id, period, obs.get("start", start), obs.get("end", end),
                obs.get("interval_kind", kind), value, text, obs.get("status"),
                canonical_json(obs.get("status_labels", [])), "not_provided", ordinal, state, prev_id,
                source_metadata.get("source_updated_at"), int(obs.get("cell_index", 0)),
                canonical_json(obs.get("raw", obs["value"])), ts, ts,
            ))
            ev_rows.append((
                stable_id("indicator-observation-evidence", obs_id, raw_sha256, obs["pointer"]), obs_id,
                obs.get("evidence_url") or source_url, raw_sha256, raw_path, obs["pointer"], None,
                definition.get("extraction_method", "json_pointer"), EXTRACTOR_VERSION, ts,
            ))
            # Curated rows transcribed from an official document also point at that stored document.
            doc = obs.get("document")
            if doc and doc["sha256"] != raw_sha256:
                ev_rows.append((
                    stable_id("indicator-observation-evidence", obs_id, doc["sha256"], doc["locator"]), obs_id,
                    doc["url"], doc["sha256"], doc["path"], doc["locator"], None, "manual_transcription",
                    EXTRACTOR_VERSION, ts,
                ))
    # Observations present in the previous release and gone from this one are recorded as deleted.
    for (key, period), (prev_id, _value, _text, ordinal, start, end, kind) in prev_obs.items():
        if (key, period) in seen:
            continue
        series_id = stable_id("indicator-series-version", release_id, key)
        if not conn.execute(
            "SELECT 1 FROM indicator_series_versions WHERE indicator_series_version_id = ?", (series_id,)
        ).fetchone():
            continue
        obs_id = stable_id("indicator-observation-version", series_id, period, "deleted")
        obs_rows.append((
            obs_id, series_id, release_id, period, start, end, kind, None, None, None, "[]",
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


def geo_series(key: str, geo: str, dimensions: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any]:
    name, system, level = GEO_META.get(geo, (geo, "unknown", "unknown"))
    return {
        "key": key, "geo_code": geo, "geo_name": name, "geo_system": system, "geo_level": level,
        "dimensions": dimensions, "observations": observations,
    }


Batch = tuple[dict[str, Any], list[dict[str, Any]]]


# ---------------------------------------------------------------- MIVAU boletín (legacy XLS)

MIVAU_PAGE = "https://apps.fomento.gob.es/BoletinOnline2/?nivel=2&orden={orden}"


def xls_book(raw: Raw):
    try:
        import xlrd  # noqa: PLC0415 - optional dependency, only for MIVAU tables
    except ImportError as exc:  # pragma: no cover - environment guard
        raise SystemExit("MIVAU tables are legacy .xls: run via `just housing-refresh` (uv run --with xlrd)") from exc
    return xlrd.open_workbook(file_contents=raw.payload)


def is_national_total(cell: Any) -> bool:
    return isinstance(cell, str) and cell.strip().lower() == "total nacional"


# Autonomous communities = NUTS 2 regions in Spain. Keys are normalized label prefixes used by MIVAU and INE.
CCAA = {
    "ES61": ("Andalucía", ["andalucia"]),
    "ES24": ("Aragón", ["aragon"]),
    "ES12": ("Asturias", ["asturias"]),
    "ES53": ("Illes Balears", ["balears", "illes balears"]),
    "ES70": ("Canarias", ["canarias"]),
    "ES13": ("Cantabria", ["cantabria"]),
    "ES41": ("Castilla y León", ["castilla y leon"]),
    "ES42": ("Castilla-La Mancha", ["castilla-la mancha"]),
    "ES51": ("Cataluña", ["cataluna"]),
    "ES52": ("Comunitat Valenciana", ["comunitat valenciana", "comunidad valenciana"]),
    "ES43": ("Extremadura", ["extremadura"]),
    "ES11": ("Galicia", ["galicia"]),
    "ES30": ("Comunidad de Madrid", ["madrid"]),
    "ES62": ("Región de Murcia", ["murcia"]),
    "ES22": ("Navarra", ["navarra"]),
    "ES21": ("País Vasco", ["pais vasco"]),
    "ES23": ("La Rioja", ["rioja"]),
    "ES63": ("Ceuta", ["ceuta"]),
    "ES64": ("Melilla", ["melilla"]),
}
for _code, (_name, _keys) in CCAA.items():
    GEO_META[_code] = (_name, "NUTS", "region")


def normalize_label(text: str) -> str:
    import unicodedata  # noqa: PLC0415

    plain = "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)).lower()
    plain = plain.replace(" - ", "-").replace("(", " ").replace(")", " ").replace(",", " ")
    return " ".join(plain.split())


def ccaa_code(label: Any) -> str | None:
    if not isinstance(label, str):
        return None
    plain = normalize_label(label)
    for code, (_name, keys) in CCAA.items():
        if any(plain == key or plain.startswith(key + " ") for key in keys):
            return code
    return None


def mivau_rows(sheet: Any) -> Iterable[tuple[int, str]]:
    """(row index, 'ES' or NUTS 2 code) for the national total and the first row of each region (regions precede
    their provinces; single-province regions repeat the name, the first occurrence is the region)."""
    seen: set[str] = set()
    for r in range(sheet.nrows):
        label = sheet.cell_value(r, 1) if sheet.ncols > 1 else None
        code = "ES" if is_national_total(label) else ccaa_code(label)
        if code and code not in seen:
            seen.add(code)
            yield r, code


def mivau_batches(table: str, indicator_code: str, definition: dict[str, Any], obs_by_geo: dict[str, list[dict[str, Any]]]) -> Iterable[Batch]:
    if not obs_by_geo.get("ES"):
        raise ValueError(f"MIVAU {table}: no TOTAL NACIONAL values found")
    yield {**definition, "indicator_code": indicator_code}, [geo_series(f"{table}|{indicator_code}|ES", "ES", {"table": table}, obs_by_geo["ES"])]
    regions = sorted(code for code in obs_by_geo if code != "ES")
    if len(regions) >= 17:
        yield {**definition, "indicator_code": f"{indicator_code}_ccaa", "label": definition["label"].replace("total nacional", "por comunidad autónoma")}, [
            geo_series(f"{table}|{indicator_code}|{code}", code, {"table": table}, obs_by_geo[code]) for code in regions
        ]


def parse_mivau_annual(table: str, indicator_code: str, label: str, definition_text: str, orden: str) -> Callable[[Raw], Iterable[Batch]]:
    """Annual tables: one header row of years (floats); national total and regional rows below."""

    def parse(raw: Raw) -> Iterable[Batch]:
        book = xls_book(raw)
        obs: dict[str, list[dict[str, Any]]] = {}
        for si, sheet in enumerate(book.sheets()):
            header = None
            for r in range(sheet.nrows):
                years = {c: int(v) for c, v in enumerate(sheet.row_values(r)) if isinstance(v, float) and 1950 <= v <= 2100}
                if len(years) >= 5:
                    header = years
                    break
            if header is None:
                continue
            for r, code in mivau_rows(sheet):
                row = sheet.row_values(r)
                for c, year in header.items():
                    if c < len(row) and isinstance(row[c], float):
                        obs.setdefault(code, []).append({"period": str(year), "value": row[c], "pointer": pointer("sheets", si, "rows", r, "cols", c),
                                                         "cell_index": r * 1000 + c})
        yield from mivau_batches(table, indicator_code, {
            "source_id": "mivau_boletin", "dataset_code": table, "frequency_code": "A", "frequency_label": "Anual",
            "unit_code": "DWELLINGS", "unit_label": "Viviendas", "label": label, "definition": definition_text,
            "extraction_method": "xls_cell", "methodology_url": MIVAU_PAGE.format(orden=orden), "source_url": MIVAU_PAGE.format(orden=orden),
        }, obs)

    return parse


def parse_mivau_quarterly(table: str, indicator_code: str, unit: tuple[str, str], label: str, definition_text: str, orden: str) -> Callable[[Raw], Iterable[Batch]]:
    """Quarterly tables: one sheet per four years, 'Año YYYY' header over four quarter columns."""

    def parse(raw: Raw) -> Iterable[Batch]:
        book = xls_book(raw)
        obs: dict[str, list[dict[str, Any]]] = {}
        for si, sheet in enumerate(book.sheets()):
            col_year: dict[int, int] = {}
            col_quarter: dict[int, int] = {}
            for r in range(sheet.nrows):
                row = sheet.row_values(r)
                labels = {c: str(v).strip() for c, v in enumerate(row) if isinstance(v, str) and v.strip()}
                if not col_year and any(v.startswith("Año ") for v in labels.values()):
                    current = None
                    for c in range(len(row)):
                        text = labels.get(c, "")
                        if text.startswith("Año "):
                            current = int(text.split()[1])
                        if current:
                            col_year[c] = current
                elif col_year and sum(v[:1] in "1234" and "º" in v for v in labels.values()) >= 4:
                    col_quarter = {c: int(v[0]) for c, v in labels.items() if v[:1] in "1234" and "º" in v}
                    break
            if not col_quarter:
                continue
            for r, code in mivau_rows(sheet):
                row = sheet.row_values(r)
                for c, q in col_quarter.items():
                    if c in col_year and c < len(row) and isinstance(row[c], float):
                        obs.setdefault(code, []).append({"period": f"{col_year[c]}-Q{q}", "value": row[c],
                                                         "pointer": pointer("sheets", si, "rows", r, "cols", c), "cell_index": r * 1000 + c})
        yield from mivau_batches(table, indicator_code, {
            "source_id": "mivau_boletin", "dataset_code": table, "frequency_code": "Q", "frequency_label": "Trimestral",
            "unit_code": unit[0], "unit_label": unit[1], "label": label, "definition": definition_text, "extraction_method": "xls_cell",
            "methodology_url": MIVAU_PAGE.format(orden=orden), "source_url": MIVAU_PAGE.format(orden=orden),
        }, obs)

    return parse


parse_mivau_valor_tasado = parse_mivau_quarterly(
    "35101000", "valor_tasado_vivienda_libre", ("EUR_M2", "Euros por m²"),
    "Valor tasado medio de la vivienda libre, total nacional (€/m²)",
    "Media de las tasaciones de vivienda libre realizadas por sociedades de tasación homologadas, en euros por metro "
    "cuadrado construido. Mide el valor de tasación, no el precio de compraventa escriturado.", "35000000")
parse_mivau_transacciones = parse_mivau_quarterly(
    "34020150", "valor_medio_transacciones_vivienda_libre", ("EUR", "Euros por transacción"),
    "Valor medio de las transacciones inmobiliarias de vivienda libre, total nacional (€)",
    "Importe medio escriturado ante notario por compraventa de vivienda libre (Consejo General del Notariado, "
    "elaborado por el Ministerio). Es un precio por operación: cambia también si cambia el tamaño o la ubicación de "
    "lo que se vende.", "34000000")


# ---------------------------------------------------------------- Banco de España si_1_5 (CSV)

BDE_URL = "https://www.bde.es/webbe/es/estadisticas/compartido/datos/csv/si_1_5.csv"
BDE_PAGE = "https://www.bde.es/webbe/es/estadisticas/temas/sectores-real/vivienda.html"
MONTHS = {m: i + 1 for i, m in enumerate(["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"])}
FREQ = {"MENSUAL": ("M", "Mensual"), "TRIMESTRAL": ("Q", "Trimestral"), "SEMESTRAL": ("S", "Semestral"), "ANUAL": ("A", "Anual")}
# alias -> (indicator_code, unit_code, label)
BDE_SERIES = {
    "SI_1_5.4": ("precio_m2_vivienda_libre_tasada", "EUR_M2", "Precio medio del m² de vivienda libre tasada (MIVAU), total nacional"),
    "SI_1_5.16": ("visados_obra_nueva_viviendas", "DWELLINGS", "Visados de dirección de obra nueva: viviendas (MIVAU)"),
    "SI_1_5.17": ("viviendas_iniciadas_total", "DWELLINGS", "Viviendas iniciadas, libres y protegidas (MIVAU)"),
    "SI_1_5.36": ("epa_hogares", "THOUSANDS_HOUSEHOLDS", "Número de hogares (EPA, base 2021, INE), miles"),
    "SI_1_5.40": ("tipo_prestamos_vivienda", "PC", "Tipo de interés de los préstamos para adquisición de vivienda"),
    "SI_1_5.43": ("precio_vivienda_renta_hogar_anios", "YEARS", "Precio de la vivienda / renta bruta del hogar mediano (años)"),
    "SI_1_5.44": ("esfuerzo_teorico_anual", "PC", "Esfuerzo teórico anual sin deducciones (% de la renta del hogar)"),
    "SI_1_5.81": ("censo_viviendas_total", "DWELLINGS", "Censos: total de viviendas"),
    "SI_1_5.84": ("censo_viviendas_principales", "DWELLINGS", "Censos: viviendas principales (= hogares)"),
    "SI_1_5.85": ("censo_viviendas_secundarias", "DWELLINGS", "Censos: viviendas secundarias"),
    "SI_1_5.86": ("censo_viviendas_desocupadas", "DWELLINGS", "Censos: viviendas desocupadas y otras"),
    "SI_1_5.87": ("censo_principales_propiedad_pct", "PC", "Censos: viviendas principales en propiedad (%)"),
    "SI_1_5.88": ("censo_principales_alquiler_pct", "PC", "Censos: viviendas principales en alquiler (%)"),
    "SI_1_5.89": ("censo_principales_cesion_pct", "PC", "Censos: viviendas principales en cesión y otras formas (%)"),
    "SI_1_5.90": ("encuesta_tenencia_propiedad_pct", "PC", "Régimen de tenencia de la vivienda principal: propiedad (ECPF hasta 2004, ECV desde 2005)"),
    "SI_1_5.91": ("encuesta_tenencia_alquiler_pct", "PC", "Régimen de tenencia de la vivienda principal: alquiler (ECPF hasta 2004, ECV desde 2005)"),
    "SI_1_5.13": ("ipc_alquiler_tasa_interanual", "PC", "IPC: pagos reales de alquiler de la vivienda principal, tasa interanual (INE)"),
    "SI_1_5.56": ("credito_vivienda_hogares_pct_pib", "PC", "Crédito a los hogares para adquisición de vivienda, saldo en % del PIB"),
    "SI_1_5.55": ("credito_vivienda_hogares_tasa", "PC", "Crédito a los hogares para adquisición de vivienda, tasa interanual"),
}


def bde_period(label: str, freq: str) -> str | None:
    parts = label.split()
    if len(parts) != 2 or parts[0] not in MONTHS or not parts[1].isdigit():
        return None
    month, year = MONTHS[parts[0]], parts[1]
    if freq == "M":
        return f"{year}-{month:02d}"
    if freq == "Q":
        return f"{year}-Q{(month + 2) // 3}"
    if freq == "S":
        return f"{year}-H{1 if month <= 6 else 2}"
    return year


def parse_bde(raw: Raw) -> Iterable[Batch]:
    rows = list(csv.reader(io.StringIO(raw.payload.decode("latin-1"))))
    header = {row[0]: (ri, row) for ri, row in enumerate(rows[:8])}
    aliases = header["ALIAS DE LA SERIE"][1]
    descriptions = header["DESCRIPCIÓN DE LA SERIE"][1]
    units = header["DESCRIPCIÓN DE LAS UNIDADES"][1]
    freqs = header["FRECUENCIA"][1]
    codes = header["CÓDIGO DE LA SERIE"][1]
    footer = {row[0]: row for row in rows if row and row[0] in ("FUENTE", "NOTAS")}
    for col, alias in enumerate(aliases):
        if alias not in BDE_SERIES:
            continue
        code, unit_code, label = BDE_SERIES[alias]
        freq, freq_label = FREQ[freqs[col]]
        obs = []
        for ri, row in enumerate(rows):
            if ri < 6 or col >= len(row):
                continue
            period = bde_period(row[0], freq)
            if period is None or row[col] in ("_", ""):
                continue
            obs.append({"period": period, "value": row[col], "pointer": pointer("rows", ri, "cols", col), "cell_index": ri * 1000 + col})
        source = footer.get("FUENTE", [""] * (col + 1))[col] if col < len(footer.get("FUENTE", [])) else ""
        notes = footer.get("NOTAS", [""] * (col + 1))[col] if col < len(footer.get("NOTAS", [])) else ""
        yield {
            "source_id": "bde_indicadores_vivienda", "dataset_code": "si_1_5", "indicator_code": code,
            "frequency_code": freq, "frequency_label": freq_label, "unit_code": unit_code, "unit_label": units[col],
            "label": label, "extraction_method": "csv_cell",
            "definition": f"{descriptions[col]} (serie {codes[col]}, alias {alias}). Fuente original: {source}. {notes}".strip(),
            "methodology_url": BDE_PAGE, "source_url": BDE_PAGE,
        }, [geo_series(f"si_1_5|{alias}|ES", "ES", {"alias": alias, "bde_code": codes[col]}, obs)]


# ---------------------------------------------------------------- INE Tempus (ETCL)

INE_SERIES = {
    "ETCL6726": ("2000–2007, serie retrospectiva publicada por el INE con la CNAE-2009", "Encuesta Trimestral de Coste Laboral, tabla 6076"),
    "ETCL1527": ("2008 en adelante", "Encuesta Trimestral de Coste Laboral, tabla 6038"),
}


def ine_url(code: str) -> str:
    return f"https://servicios.ine.es/wstempus/js/ES/DATOS_SERIE/{code}?nult=200"


def parse_ine(code: str) -> Callable[[Raw], Iterable[Batch]]:
    def parse(raw: Raw) -> Iterable[Batch]:
        data = raw.data
        obs = []
        for i, row in enumerate(data["Data"]):
            period_id = int(row["FK_Periodo"])
            if not 19 <= period_id <= 22 or row.get("Valor") is None:
                raise ValueError(f"{code}: unexpected period {period_id}")
            obs.append({"period": f"{row['Anyo']}-Q{period_id - 18}", "value": row["Valor"], "pointer": pointer("Data", i, "Valor"),
                        "cell_index": i, "status": "secret" if row.get("Secreto") else None})
        span, table = INE_SERIES[code]
        yield {
            "source_id": "ine_tempus", "dataset_code": "ETCL", "indicator_code": code, "frequency_code": "Q",
            "frequency_label": "Trimestral", "unit_code": "EUR_WORKER_MONTH", "unit_label": "Euros por trabajador y mes",
            "label": f"Coste salarial total por trabajador y mes, ambas jornadas, industria, construcción y servicios ({span})",
            "definition": f"{data['Nombre'].strip()} {table}. Salario bruto pagado por la empresa (ordinario, pagos "
            "extraordinarios y atrasados), antes de impuestos y cotizaciones del trabajador; incluye tiempo parcial.",
            "methodology_url": "https://www.ine.es/dyngs/INEbase/operacion.htm?c=Estadistica_C&cid=1254736045053&idp=1254735976596",
            "source_url": f"https://www.ine.es/consul/serie.do?s={code}",
        }, [geo_series(f"ETCL|{code}|ES", "ES", {"serie": code}, obs)]

    return parse


INE_PERIOD = {**{m: f"{m:02d}" for m in range(1, 13)}, 19: "Q1", 20: "Q2", 21: "Q3", 22: "Q4", 28: "A"}


def ine_period(row: dict[str, Any]) -> str:
    code = INE_PERIOD[int(row["FK_Periodo"])]
    if code == "A":
        return str(row["Anyo"])
    return f"{row['Anyo']}-{code}" if code.startswith("Q") else f"{row['Anyo']}-{code}"


# table id -> (indicator_code, unit, label, definition, methodology page, selector(series name) -> geo or None)
def _select(suffix: str) -> Callable[[str], str | None]:
    def pick(name: str) -> str | None:
        head, _, rest = name.partition(". ")
        if not rest.strip().startswith(suffix):
            return None
        return "ES" if normalize_label(head) in ("total nacional", "nacional") else ccaa_code(head)
    return pick


INE_TABLES = {
    "59056": ("ipva_indice", ("IDX2015", "Índice 2015 = 100"), "Índice de Precios de Vivienda en Alquiler (IPVA), general",
              "INE, a partir de los alquileres declarados en el IRPF (todos los contratos vigentes, no solo los nuevos). Anual.",
              "https://www.ine.es/dyngs/INEbase/operacion.htm?c=Estadistica_C&cid=1254736177052&idp=1254735976608", _select("Total. Índice")),
    "80271": ("ipv_indice_media_anual", ("IDX2025", "Índice 2025 = 100"), "Índice de Precios de Vivienda (IPV), general, media anual",
              "INE, índice de precios de compraventa de vivienda libre (nueva y usada) a partir de las escrituras notariales, "
              "con ajuste de calidad (hedónico). Desde 2007.",
              "https://www.ine.es/dyngs/INEbase/operacion.htm?c=Estadistica_C&cid=1254736152838&idp=1254735976607", _select("Media anual. General")),
    "6061": ("etcl_coste_salarial_ccaa", ("EUR_WORKER_MONTH", "Euros por trabajador y mes"),
             "Coste salarial total por trabajador y mes por comunidad autónoma (ETCL)",
             "INE, Encuesta Trimestral de Coste Laboral, tabla 6061: coste salarial total (salario bruto), industria, construcción y servicios.",
             "https://www.ine.es/dyngs/INEbase/operacion.htm?c=Estadistica_C&cid=1254736045053&idp=1254735976596",
             _select("Industria, construcción y servicios (excepto actividades de los hogares como empleadores y de organizaciones y organismos extraterritoriales). Coste salarial total")),
    "39365": ("viviendas_turisticas_pct", ("PC", "% de las viviendas censadas"), "Viviendas turísticas sobre el total de viviendas (%)",
              "INE, estadística experimental de viviendas turísticas a partir de anuncios en plataformas (mayo y noviembre de cada año).",
              "https://www.ine.es/dyngs/INEbase/operacion.htm?c=Estadistica_C&cid=1254736177101&idp=1254735976608", _select("Porcentaje de viviendas turísticas")),
}


def ine_table_url(table: str) -> str:
    return f"https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/{table}?nult=120"


def parse_ine_table(table: str) -> Callable[[Raw], Iterable[Batch]]:
    code, unit, label, definition, page, pick = INE_TABLES[table]

    def parse(raw: Raw) -> Iterable[Batch]:
        series = []
        for si, doc in enumerate(raw.data):
            geo = pick(doc["Nombre"])
            if geo is None or any(s["geo_code"] == geo for s in series):
                continue
            obs = [{"period": ine_period(row), "value": row["Valor"], "pointer": pointer(si, "Data", i, "Valor"), "cell_index": si * 1000 + i}
                   for i, row in enumerate(doc["Data"]) if row.get("Valor") is not None]
            series.append(geo_series(f"{table}|{doc['COD']}", geo, {"serie": doc["COD"], "nombre": doc["Nombre"].strip()}, obs))
        if not any(s["geo_code"] == "ES" for s in series) and table != "6061":
            raise ValueError(f"INE {table}: national series not found")
        yield {
            "source_id": "ine_tempus", "dataset_code": f"INE-{table}", "indicator_code": code, "frequency_code": "X",
            "frequency_label": "Según la tabla", "unit_code": unit[0], "unit_label": unit[1], "label": label,
            "definition": definition, "methodology_url": page, "source_url": f"https://www.ine.es/jaxiT3/Tabla.htm?t={table}",
        }, sorted(series, key=lambda s: s["geo_code"])

    return parse


# ---------------------------------------------------------------- OECD via DBnomics

OECD_WAGE_URL = "https://api.db.nomics.world/v22/series/OECD/DSD_EARNINGS@AV_AN_WAGE/ESP.WG.EUR.A.V.MEAN._Z?observations=1"
OECD_HP_DATASET = "DSD_AN_HOUSE_PRICES@DF_HOUSE_PRICES"
OECD_HP_AREAS = ["ESP", "DEU", "FRA", "ITA", "PRT", "OECD"]
OECD_HP_MEASURES = {
    "HPI_YDH_AVG": ("PT_AVG_L_TERM", "% de la media de largo plazo", "Ratio precio de la vivienda / renta disponible por habitante, estandarizado"),
    "HPI_RPI_AVG": ("PT_AVG_L_TERM", "% de la media de largo plazo", "Ratio precio / alquiler de la vivienda, estandarizado"),
    "RHP": ("IX", "Índice 2015 = 100", "Precio real de la vivienda (deflactado con el consumo privado)"),
}


def oecd_hp_url() -> str:
    dims = {"REF_AREA": OECD_HP_AREAS, "FREQ": ["A"], "MEASURE": list(OECD_HP_MEASURES)}
    return f"https://api.db.nomics.world/v22/series/OECD/{OECD_HP_DATASET}?" + urllib.parse.urlencode(
        {"dimensions": json.dumps(dims, separators=(",", ":")), "observations": 1, "limit": 200}
    )


def dbnomics_obs(doc: dict[str, Any], doc_index: int) -> list[dict[str, Any]]:
    return [
        {"period": period, "value": value, "pointer": pointer("series", "docs", doc_index, "value", i), "cell_index": i}
        for i, (period, value) in enumerate(zip(doc["period"], doc["value"]))
        if isinstance(value, (int, float))
    ]


def parse_oecd_wage(raw: Raw) -> Iterable[Batch]:
    doc = raw.data["series"]["docs"][0]
    yield {
        "source_id": "oecd_dbnomics", "dataset_code": "DSD_EARNINGS@AV_AN_WAGE", "indicator_code": "WG.EUR.A.V.MEAN",
        "frequency_code": "A", "frequency_label": "Anual", "unit_code": "EUR", "unit_label": "Euros corrientes",
        "label": "Salario medio anual por asalariado equivalente a tiempo completo (OCDE), euros corrientes",
        "definition": "OCDE Average annual wages: remuneración de asalariados de la contabilidad nacional dividida por "
        "el número de asalariados equivalentes a tiempo completo. Leído de la réplica DBnomics (sdmx.oecd.org bloquea scripts).",
        "methodology_url": "https://www.oecd.org/en/data/indicators/average-annual-wages.html",
        "source_url": "https://db.nomics.world/OECD/DSD_EARNINGS@AV_AN_WAGE/ESP.WG.EUR.A.V.MEAN._Z",
    }, [geo_series("AV_AN_WAGE|ESP.WG.EUR.A.V.MEAN._Z", "ESP", {"series_code": doc["series_code"]}, dbnomics_obs(doc, 0))]


def parse_oecd_house_prices(raw: Raw) -> Iterable[Batch]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for i, doc in enumerate(raw.data["series"]["docs"]):
        area, freq, measure, unit = doc["series_code"].split(".")
        if measure not in OECD_HP_MEASURES or unit != OECD_HP_MEASURES[measure][0]:
            continue
        grouped.setdefault(measure, []).append(
            geo_series(f"{OECD_HP_DATASET}|{doc['series_code']}", area, {"REF_AREA": area, "MEASURE": measure, "UNIT": unit}, dbnomics_obs(doc, i))
        )
    for measure, series in sorted(grouped.items()):
        unit, unit_label, label = OECD_HP_MEASURES[measure]
        yield {
            "source_id": "oecd_dbnomics", "dataset_code": OECD_HP_DATASET, "indicator_code": measure,
            "frequency_code": "A", "frequency_label": "Anual", "unit_code": unit, "unit_label": unit_label,
            "label": f"{label} (OCDE, Analytical house price indicators)",
            "definition": "OCDE Analytical house price indicators. Los ratios estandarizados expresan el ratio de cada año "
            "en % de su media de largo plazo en ese país: comparan cada país consigo mismo, no niveles entre países.",
            "methodology_url": "https://www.oecd.org/en/data/datasets/analytical-house-prices-indicators.html",
            "source_url": f"https://db.nomics.world/OECD/{OECD_HP_DATASET}",
        }, series


# ---------------------------------------------------------------- Eurostat JSON-stat

EUROSTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"


def eurostat_url(dataset: str, **filters: list[str] | str) -> str:
    params: list[tuple[str, str]] = []
    for key, values in filters.items():
        for value in [values] if isinstance(values, str) else values:
            params.append((key, value))
    return EUROSTAT_BASE + dataset + "?" + urllib.parse.urlencode(params)


def jsonstat_cells(data: dict[str, Any]) -> Iterable[tuple[dict[str, str], int, Any]]:
    ids, sizes = data["id"], data["size"]
    inverse = {dim: {pos: code for code, pos in data["dimension"][dim]["category"]["index"].items()} for dim in ids}
    for flat_text, value in data["value"].items():
        flat, coords = int(flat_text), {}
        rest = flat
        for dim, size in zip(reversed(ids), reversed(sizes)):
            coords[dim] = inverse[dim][rest % size]
            rest //= size
        yield coords, flat, value


EUROSTAT_DEFS = {
    "yth_demo_030": {
        "label": "Edad media estimada a la que los jóvenes dejan el hogar de sus padres",
        "unit_code": "AGE_YEARS", "unit_label": "Años de edad", "split": [],
        "definition": "Eurostat, estimación a partir de la EU-SILC/EU-LFS: edad a la que al menos el 50 % de la población "
        "de cada edad ya no vive en el hogar de sus padres.",
    },
    "ilc_lvho02": {
        "label": "Población por régimen de tenencia de la vivienda (EU-SILC)",
        "unit_code": "PC", "unit_label": "% de la población", "split": ["tenure"],
        "definition": "Eurostat EU-SILC: % de la población que vive en una vivienda en propiedad (con o sin hipoteca) o "
        "de alquiler (a precio de mercado o reducido/gratuito). Mide personas, no hogares.",
    },
    "gov_10a_exp": {
        "label": "Gasto de las administraciones públicas por función (COFOG), millones de euros",
        "unit_code": "MIO_EUR", "unit_label": "Millones de euros corrientes", "split": ["cofog99"],
        "definition": "Eurostat COFOG, sector S13 (todas las administraciones), gasto total (TE). GF0601: desarrollo de "
        "la vivienda (promoción, adquisición y ayudas a la construcción). GF1006: protección social, vivienda "
        "(ayudas al alquiler y similares a hogares). Excluye beneficios fiscales (p. ej. deducción por vivienda en el IRPF).",
    },
    "lfst_r_lfsd2hh": {
        "label": "Hogares privados por región NUTS 2 (EPA/EU-LFS), miles",
        "unit_code": "THS_HH", "unit_label": "Miles de hogares", "split": [],
        "definition": "Eurostat, encuesta de población activa (en España, la EPA del INE): hogares privados por región.",
    },
    "demo_gind": {
        "label": "Población y migración", "unit_code": "MIXED", "unit_label": "Según indicador", "split": ["indic_de"],
        "units": {"JAN": ("PERSONS", "Personas"), "GROWRT": ("PER_1000", "Por 1.000 habitantes"),
                  "CNMIGRATRT": ("PER_1000", "Por 1.000 habitantes"), "NATGROWRT": ("PER_1000", "Por 1.000 habitantes")},
        "definition": "Eurostat, balance demográfico: población a 1 de enero, crecimiento total, migración neta (con ajuste "
        "estadístico) y crecimiento natural, por 1.000 habitantes.",
    },
    "ilc_lvph01": {
        "label": "Tamaño medio del hogar (EU-SILC)", "unit_code": "PERSONS_PER_HH", "unit_label": "Personas por hogar", "split": [],
        "definition": "Eurostat EU-SILC: número medio de personas por hogar privado.",
    },
    "prc_hicp_aind": {
        "label": "IPCA, índice anual (2015 = 100)", "unit_code": "IDX2015", "unit_label": "Índice 2015 = 100", "split": ["coicop"],
        "definition": "Eurostat, índice de precios de consumo armonizado. CP041: alquileres efectivos de la vivienda (todos "
        "los contratos vigentes); CP00: índice general.",
    },
    "tour_ce_omn12": {
        "label": "Pernoctaciones en alojamientos de corta estancia reservados en plataformas en línea", "unit_code": "NIGHTS",
        "unit_label": "Pernoctaciones", "split": [],
        "definition": "Eurostat, estadística experimental con datos de Airbnb, Booking, Expedia y Tripadvisor: pernoctaciones "
        "en alojamientos de corta estancia (viviendas y habitaciones) reservados en plataformas.",
    },
    "nama_10_gdp": {
        "label": "Producto interior bruto a precios corrientes, millones de euros",
        "unit_code": "CP_MEUR", "unit_label": "Millones de euros corrientes", "split": [],
        "definition": "Eurostat, cuentas nacionales anuales (SEC 2010), B1GQ.",
    },
}


def parse_eurostat(dataset: str) -> Callable[[Raw], Iterable[Batch]]:
    spec = EUROSTAT_DEFS[dataset]

    def parse(raw: Raw) -> Iterable[Batch]:
        data = raw.data
        status = data.get("status", {})
        grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
        dims_of: dict[str, dict[str, str]] = {}
        for coords, flat, value in jsonstat_cells(data):
            split = ".".join(coords[d] for d in spec["split"]) or "_T"
            dims = {k: v for k, v in coords.items() if k != "time"}
            key = f"{dataset}|" + "|".join(f"{k}={dims[k]}" for k in sorted(dims))
            dims_of[key] = dims
            grouped.setdefault(split, {}).setdefault(key, []).append({
                "period": coords["time"], "value": value, "pointer": pointer("value", flat), "cell_index": flat,
                "status": status.get(str(flat)),
            })
        for split, series_map in sorted(grouped.items()):
            unit_code, unit_label = spec.get("units", {}).get(split, (spec["unit_code"], spec["unit_label"]))
            yield {
                "source_id": "eurostat_sdmx", "dataset_code": dataset, "indicator_code": f"{dataset}.{split}",
                "frequency_code": "A", "frequency_label": "Anual", "unit_code": unit_code, "unit_label": unit_label,
                "label": f"{spec['label']} [{split}]" if split != "_T" else spec["label"],
                "definition": spec["definition"],
                "methodology_url": f"https://ec.europa.eu/eurostat/databrowser/view/{dataset}/default/table",
                "source_url": f"https://ec.europa.eu/eurostat/databrowser/view/{dataset}/default/table",
                "source_updated_at": data.get("updated"),
            }, [
                geo_series(key, dims_of[key]["geo"], dims_of[key], sorted(obs, key=lambda o: o["period"]))
                for key, obs in sorted(series_map.items())
            ]

    return parse


API_SOURCES: list[tuple[str, str, Callable[[Raw], Iterable[Batch]]]] = [
    ("mivau_35101000_valor_tasado.xls", "https://apps.fomento.gob.es/BoletinOnline2/sedal/35101000.XLS", parse_mivau_valor_tasado),
    ("mivau_32201000_libres_terminadas.xls", "https://apps.fomento.gob.es/BoletinOnline2/sedal/32201000.XLS", parse_mivau_annual(
        "32201000", "viviendas_libres_terminadas", "Viviendas libres terminadas, total nacional",
        "Viviendas libres terminadas (estimación del Ministerio a partir de los certificados de fin de obra de los "
        "Colegios de Aparejadores). Nota de la tabla: 'Datos estimados de viviendas libres terminadas'.", "32000000")),
    ("mivau_31306000_vp_calificaciones_definitivas.xls", "https://apps.fomento.gob.es/BoletinOnline2/sedal/31306000.XLS", parse_mivau_annual(
        "31306000", "vivienda_protegida_calificaciones_definitivas", "Viviendas protegidas terminadas (calificaciones definitivas), total nacional",
        "Número de calificaciones definitivas de vivienda protegida, planes estatales y autonómicos: la calificación "
        "definitiva se concede al terminar la obra, por eso se usa como viviendas protegidas terminadas.", "31000000")),
    ("mivau_34020150_valor_transacciones.xls", "https://apps.fomento.gob.es/BoletinOnline2/sedal/34020150.XLS", parse_mivau_transacciones),
    ("bde_si_1_5.csv", BDE_URL, parse_bde),
    *[(f"ine_tabla_{table}.json", ine_table_url(table), parse_ine_table(table)) for table in INE_TABLES],
    *[(f"ine_{code}.json", ine_url(code), parse_ine(code)) for code in INE_SERIES],
    ("oecd_av_an_wage_esp_dbnomics.json", OECD_WAGE_URL, parse_oecd_wage),
    ("oecd_house_prices_dbnomics.json", oecd_hp_url(), parse_oecd_house_prices),
    ("eurostat_yth_demo_030.json", eurostat_url("yth_demo_030", sex="T", unit="AVG", geo=PEERS), parse_eurostat("yth_demo_030")),
    ("eurostat_ilc_lvho02.json", eurostat_url("ilc_lvho02", hhcomp="TOTAL", rskpovth="TOTAL", unit="PC",
                                               tenure=["OWN", "OWN_L", "RENT", "RENT_MKT", "RENT_FR"], geo=PEERS), parse_eurostat("ilc_lvho02")),
    ("eurostat_gov_10a_exp_housing.json", eurostat_url("gov_10a_exp", unit="MIO_EUR", sector="S13", na_item="TE",
                                                        cofog99=["GF0601", "GF1006"], geo=PEERS), parse_eurostat("gov_10a_exp")),
    ("eurostat_nama_10_gdp.json", eurostat_url("nama_10_gdp", unit="CP_MEUR", na_item="B1GQ", geo=PEERS), parse_eurostat("nama_10_gdp")),
    ("eurostat_lfst_r_lfsd2hh.json", eurostat_url("lfst_r_lfsd2hh", unit="THS_HH", deg_urb="TOTAL", geo=["ES", *CCAA]), parse_eurostat("lfst_r_lfsd2hh")),
    ("eurostat_demo_gind.json", eurostat_url("demo_gind", indic_de=["JAN", "GROWRT", "CNMIGRATRT", "NATGROWRT"], geo=PEERS), parse_eurostat("demo_gind")),
    ("eurostat_ilc_lvph01.json", eurostat_url("ilc_lvph01", unit="AVG", geo=PEERS), parse_eurostat("ilc_lvph01")),
    ("eurostat_prc_hicp_aind.json", eurostat_url("prc_hicp_aind", unit="INX_A_AVG", coicop=["CP041", "CP00"], geo=PEERS), parse_eurostat("prc_hicp_aind")),
    ("eurostat_tour_ce_omn12.json", eurostat_url("tour_ce_omn12", unit="NR", c_resid="TOTAL", month="TOTAL", indic_to="NGT_SP", geo=PEERS), parse_eurostat("tour_ce_omn12")),
]


# ---------------------------------------------------------------- curated values with citations

def document_ref(row: dict[str, Any]) -> dict[str, str] | None:
    """The stored official document a curated value was transcribed from; its sha256 must still match."""
    raw_file, expected = row.get("raw_file"), row.get("raw_sha256")
    if not raw_file or not expected:
        return None
    path = REPO_ROOT / raw_file
    if not path.exists():
        raise FileNotFoundError(f"curated row cites {raw_file}, which is not stored")
    actual = sha256_bytes(path.read_bytes())
    if actual != expected:
        raise ValueError(f"{raw_file}: sha256 {actual} does not match the curated {expected}")
    return {"path": raw_file, "sha256": actual, "url": row.get("source_url") or "", "locator": row.get("locator") or "document"}


def curated_obs(row: dict[str, Any], value_key: str, period: str, ptr: str, index: int, **extra: Any) -> dict[str, Any]:
    return {
        "period": period, "value": row.get(value_key), "pointer": ptr, "cell_index": index, "raw": row,
        "evidence_url": row.get("source_url"), "status": row.get("confidence"), "document": document_ref(row),
        "status_labels": [{"code": row["confidence"], "label": f"confianza {row['confidence']}"}] if row.get("confidence") else [],
        **extra,
    }


def curated_definition(indicator_code: str, dataset: str, label: str, unit_code: str, unit_label: str, freq: str = "A") -> dict[str, Any]:
    return {
        "source_id": "vclc_housing_curated", "dataset_code": dataset, "indicator_code": indicator_code,
        "frequency_code": freq, "frequency_label": "Anual" if freq == "A" else "Por norma vigente en la fecha",
        "unit_code": unit_code, "unit_label": unit_label, "label": label, "extraction_method": "curated_citation",
        "definition": "Valor transcrito de la norma o publicación oficial citada en cada fila (URL, localizador y, si se "
        "guardó el documento, su sha256).",
        "methodology_url": "https://votaconlachola.org/visualizaciones/vivienda/#metodo",
        "source_url": "https://votaconlachola.org/visualizaciones/vivienda/#metodo",
    }


def load_curated(conn: sqlite3.Connection, snapshot_date: str) -> dict[str, Any]:
    report: dict[str, Any] = {}
    batches: list[tuple[Path, dict[str, Any], list[dict[str, Any]], dict[str, Any]]] = []

    taxes_path = MANUAL_DIR / "purchase_taxes_es.json"
    if taxes_path.exists():
        data = json.loads(taxes_path.read_bytes())
        by_key: dict[str, dict[str, list[dict[str, Any]]]] = {}
        units: dict[str, str] = {}
        for i, row in enumerate(data.get("rates", [])):
            period = f"{row['year']}-07-01"
            obs = curated_obs(row, "value_pct", period, pointer("rates", i, "value_pct"), i,
                              start=period, end=period, interval_kind="legal_in_force_on_date")
            by_key.setdefault(row["key"], {}).setdefault(row["scope"], []).append(obs)
            units[row["key"]] = row.get("unit", "pct")
        for key, scopes in sorted(by_key.items()):
            unit = units[key]
            definition = curated_definition(key, "purchase_taxes_es", f"Impuesto en la compra de vivienda: {key}",
                                            "PC" if unit == "pct" else "COEF", "%" if unit == "pct" else "Coeficiente", "EVENT")
            series = [geo_series(f"purchase_taxes_es|{key}|{scope}", scope, {"tax": key, "scope": scope}, obs) for scope, obs in sorted(scopes.items())]
            batches.append((taxes_path, definition, series, {"rules": data.get("rules", []), "gaps": data.get("gaps", [])}))

    long_path = MANUAL_DIR / "housing_long_run_es.json"
    if long_path.exists():
        data = json.loads(long_path.read_bytes())
        meta = {"gaps": data.get("gaps", []), "blocked_hosts": data.get("blocked_hosts", [])}
        for field, label in (("owner_pct", "propiedad"), ("rent_pct", "alquiler"), ("other_pct", "cesión y otras formas")):
            obs = [curated_obs(row, field, str(row["year"]), pointer("census_tenure", i, field), i, interval_kind="census_stock")
                   for i, row in enumerate(data.get("census_tenure", [])) if row.get(field) is not None]
            if obs:
                batches.append((long_path, curated_definition(f"census_tenure_{field}", "housing_long_run_es",
                                                              f"Censos 1950 y 1960: viviendas principales en {label} (%)", "PC", "%"),
                                [geo_series(f"census_tenure|{field}|ES", "ES", {"field": field}, obs)], meta))
        young: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for i, row in enumerate(data.get("young_ownership", [])):
            young.setdefault((row.get("source_key", "bde_eff"), row["age_group"]), []).append(
                curated_obs(row, "owner_pct", str(row["wave"]), pointer("young_ownership", i, "owner_pct"), i))
            if row.get("all_ages_owner_pct") is not None:
                young.setdefault((row.get("source_key", "bde_eff"), "total"), []).append(
                    curated_obs(row, "all_ages_owner_pct", str(row["wave"]), pointer("young_ownership", i, "all_ages_owner_pct"), i))
        for source_key in sorted({k[0] for k in young}):
            series = []
            for (sk, age), obs in sorted(young.items()):
                if sk != source_key:
                    continue
                unique = {o["period"]: o for o in obs}  # a wave reprinted in two rows keeps its own article's value (first)
                for o in reversed(obs):
                    unique.setdefault(o["period"], o)
                series.append(geo_series(f"young_ownership|{sk}|{age}", "ES", {"age_group": age}, sorted(unique.values(), key=lambda o: o["period"])))
            batches.append((long_path, curated_definition(f"owner_pct_by_age.{source_key}", "housing_long_run_es",
                                                          "Hogares con la vivienda principal en propiedad, por edad de la persona de referencia (%)", "PC", "% de hogares"),
                            series, meta))
        social: dict[str, list[dict[str, Any]]] = {}
        for i, row in enumerate(data.get("social_rental_stock", [])):
            if row.get("year"):
                obs = curated_obs(row, "pct", str(row["year"]), pointer("social_rental_stock", i, "pct"), i)
            else:  # cross-country averages of each country's latest year: no single reference year
                as_of = str(data.get("retrieved_at"))[:10]
                obs = curated_obs(row, "pct", "latest", pointer("social_rental_stock", i, "pct"), i,
                                  start=as_of, end=as_of, interval_kind="latest_available_by_country")
            social.setdefault(row["country"], []).append(obs)
        if social:
            batches.append((long_path, curated_definition("social_rental_stock_pct", "housing_long_run_es",
                                                          "Parque de vivienda social en alquiler (% del total de viviendas)", "PC", "% de las viviendas"),
                            [geo_series(f"social_rental_stock|{c}", c, {"country": c}, obs) for c, obs in sorted(social.items())], meta))

    norms_path = MANUAL_DIR / "boe_housing_norms_es.json"
    if norms_path.exists():
        data = json.loads(norms_path.read_bytes())
        series = []
        for field in ("total", "estatal", "autonomica"):
            obs = [{"period": str(row["year"]), "value": row[field], "pointer": pointer("years", i, field), "cell_index": i,
                    "raw": {k: row[k] for k in ("year", "total", "estatal", "autonomica", "by_rank") if k in row},
                    "evidence_url": f"https://www.boe.es/datosabiertos/api/boe/sumario/{row['year']}0101"}
                   for i, row in enumerate(data.get("years", [])) if row.get(field) is not None]
            series.append(geo_series(f"boe_housing_norms|{field}", "ES", {"scope": field}, obs))
        definition = curated_definition("boe_housing_norms_per_year", "boe_housing_norms_es",
                                        "Disposiciones generales sobre vivienda publicadas en el BOE por año", "COUNT", "Disposiciones")
        definition["extraction_method"] = "derived_count"
        definition["definition"] = (data.get("method") or "") + " Generado por scripts/boe_housing_norms.py a partir de los sumarios diarios del BOE guardados en etl/data/raw/housing/boe_sumarios/; la lista de normas con su identificador está en el mismo JSON."
        definition["source_url"] = "https://www.boe.es/datosabiertos/api/api.php"
        batches.append((norms_path, definition, series, {"regex": data.get("regex"), "exclusions": data.get("exclusions"), "gaps": data.get("gaps", [])}))

    for path, definition, series, meta in batches:
        payload = path.read_bytes()
        counts = load_indicator(conn, definition, sha256_bytes(payload), len(payload), rel(path), definition["source_url"],
                                snapshot_date, {"retrieved_at": json.loads(payload).get("retrieved_at"), **meta}, series)
        report[f"{definition['indicator_code']}"] = counts
    return report


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
                meta = {"retrieved_at": raw.retrieved_at, "source_updated_at": definition.pop("source_updated_at", None),
                        "download_url": raw.url}
                counts = load_indicator(conn, definition, raw.sha256, len(raw.payload), rel(raw.path), raw.url,
                                        args.snapshot_date, meta, series)
                report["indicators"][f"{definition['source_id']}:{definition['indicator_code']}:{definition['unit_code']}"] = counts
        report["curated"] = load_curated(conn, args.snapshot_date)
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk:
        raise SystemExit(f"foreign_key_check failed: {fk[:5]}")
    conn.close()
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
