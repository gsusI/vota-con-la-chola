#!/usr/bin/env python3
"""Export /visualizaciones/empleo/ data from the employment DB (scripts/ingest_employment_es.py).

Reads only normalized tables: the latest release of each indicator (indicator_* contract) and the curated events.
Derived figures (Spain/Europe ratios, 1995 = 100 rebasing, annual means of EPA quarters, shares of employees) are
computed here from stored values, so every published number traces to a raw payload cell. Writes the page JSON
(with per-source provenance: URL, retrieval date, sha256) and a long CSV. When the DB is missing (CI checkouts)
the committed artifact is kept.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "etl/data/staging/employment-es.db"
OUT_JSON = REPO_ROOT / "ui/site/public/visualizaciones/data/empleo.json"
OUT_CSV = REPO_ROOT / "ui/site/public/visualizaciones/data/empleo.csv"

PRODUCTIVITY_BASE = 1995
HYPOTHESIS_FROM = 1980
EUROSTAT_TO_AREA = {"ES": "ESP", "EU27_2020": "EU27", "DE": "DEU", "FR": "FRA", "IT": "ITA", "PT": "PRT"}
SOURCE_PAGES = {
    "ameco_dbnomics": ("Comisión Europea · AMECO (réplica DBnomics)", "https://economy-finance.ec.europa.eu/economic-research-and-databases/economic-databases/ameco-database_en"),
    "eurostat_sdmx": ("Eurostat · Encuesta de Población Activa de la UE y contabilidad nacional", "https://ec.europa.eu/eurostat/web/lfs/database"),
    "ine_epa_tempus": ("INE · Encuesta de Población Activa (API Tempus)", "https://www.ine.es/dyngs/INEbase/es/operacion.htm?c=Estadistica_C&cid=1254736176918"),
    "oecd_taxing_wages": ("OCDE · Taxing Wages (réplica DBnomics)", "https://db.nomics.world/OECD/DSD_TAX_WAGES_COMP@DF_TW_COMP"),
    "oecd_productivity": ("OCDE · Productivity Database (réplica DBnomics)", "https://db.nomics.world/OECD/DSD_PDB@DF_PDB"),
    "vclc_employment_events": ("Reformas laborales (BOE) y rupturas de la EPA (INE, EUR-Lex)", "https://www.boe.es/"),
}


def r(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(float(value), digits)


class Store:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.provenance: dict[str, list[dict]] = defaultdict(list)

    def release(self, source_id: str, dataset_code: str, indicator_code: str) -> tuple:
        row = self.conn.execute(
            """
            SELECT r.indicator_release_id, r.source_url, r.source_content_sha256, r.source_snapshot_date,
                   r.source_metadata_json, r.raw_path
            FROM indicator_definitions d JOIN indicator_releases r USING (indicator_id)
            WHERE d.source_id = ? AND d.dataset_code = ? AND d.indicator_code = ?
            ORDER BY r.source_snapshot_date DESC, r.created_at DESC LIMIT 1
            """,
            (source_id, dataset_code, indicator_code),
        ).fetchone()
        if row is None:
            raise LookupError(f"indicator {source_id}:{dataset_code}:{indicator_code} not loaded")
        release_id, url, sha, snapshot, meta, raw_path = row
        meta = json.loads(meta or "{}")
        self.provenance[source_id].append({
            "indicator": f"{dataset_code}:{indicator_code}", "url": url, "sha256": sha, "raw_path": raw_path,
            "snapshot_date": snapshot, "retrieved_at": meta.get("retrieved_at"),
            "source_updated_at": meta.get("source_updated_at"),
        })
        return release_id, meta

    def series(self, source_id: str, dataset_code: str, indicator_code: str, *, drop_forecast: bool = True) -> dict[str, dict[str, float]]:
        """Latest release as {geography_code: {period: value}}; deleted rows (and AMECO forecasts) are dropped."""
        release_id, _ = self.release(source_id, dataset_code, indicator_code)
        out: dict[str, dict[str, float]] = defaultdict(dict)
        for geo, period, value, status in self.conn.execute(
            """
            SELECT s.geography_code, o.period_label, o.value_decimal, o.source_status_code
            FROM indicator_observation_versions o JOIN indicator_series_versions s USING (indicator_series_version_id)
            WHERE o.indicator_release_id = ? AND o.revision_state != 'deleted' AND o.value_decimal IS NOT NULL
            ORDER BY s.geography_code, o.period_start
            """,
            (release_id,),
        ):
            if drop_forecast and status == "forecast":
                continue
            out[geo][period] = float(value)
        return out

    def annual(self, *args, **kwargs) -> dict[str, dict[int, float]]:
        return {geo: {int(p): v for p, v in rows.items()} for geo, rows in self.series(*args, **kwargs).items()}

    def flags(self, source_id: str, dataset_code: str, indicator_code: str, geo: str) -> dict[int, str]:
        release_id, _ = self.release(source_id, dataset_code, indicator_code)
        self.provenance[source_id].pop()  # same release already recorded by series()
        return {
            int(period): status
            for period, status in self.conn.execute(
                """
                SELECT o.period_label, o.source_status_code FROM indicator_observation_versions o
                JOIN indicator_series_versions s USING (indicator_series_version_id)
                WHERE o.indicator_release_id = ? AND s.geography_code = ? AND o.source_status_code IS NOT NULL
                """,
                (release_id, geo),
            )
        }


def points(mapping: dict[int, float], digits: int = 2, since: int | None = None, until: int | None = None) -> list[dict]:
    return [
        {"year": y, "value": r(v, digits)}
        for y, v in sorted(mapping.items())
        if (since is None or y >= since) and (until is None or y <= until)
    ]


def quarterly_to_annual(rows: dict[str, float]) -> dict[int, float]:
    """Mean of the four quarters, only for complete years."""
    by_year: dict[int, list[float]] = defaultdict(list)
    for period, value in rows.items():
        by_year[int(period[:4])].append(value)
    return {year: mean(values) for year, values in by_year.items() if len(values) == 4}


def ratio(a: dict[int, float], b: dict[int, float], scale: float = 100.0) -> dict[int, float]:
    return {y: a[y] / b[y] * scale for y in sorted(set(a) & set(b)) if b[y]}


def events(conn: sqlite3.Connection) -> tuple[list[dict], dict]:
    row = conn.execute(
        """
        SELECT r.indicator_release_id, r.source_metadata_json FROM indicator_definitions d
        JOIN indicator_releases r USING (indicator_id)
        WHERE d.source_id = 'vclc_employment_events'
        ORDER BY r.source_snapshot_date DESC, r.created_at DESC LIMIT 1
        """
    ).fetchone()
    if not row:
        return [], {}
    out = []
    for raw, url in conn.execute(
        """
        SELECT o.raw_value_json, e.source_url FROM indicator_observation_versions o
        JOIN indicator_observation_evidence e USING (indicator_observation_version_id)
        WHERE o.indicator_release_id = ? AND o.revision_state != 'deleted' ORDER BY o.period_start
        """,
        (row[0],),
    ):
        event = json.loads(raw)
        out.append({
            "id": event["id"], "date": event["date"], "year": int(event["date"][:4]), "kind": event["kind"],
            "label": event["label"], "source": event["source"], "source_url": url, "locator": event.get("locator"),
            "confidence": event.get("confidence"),
        })
    return out, json.loads(row[1] or "{}")


def build(conn: sqlite3.Connection) -> dict:
    store = Store(conn)

    # 1. Unemployment since 1960 (AMECO) cut at the last observed Eurostat year.
    une = store.annual("eurostat_sdmx", "une_rt_a", "Y15-74.PC_ACT.T")
    last_year = max(une["ES"])
    zutn = store.annual("ameco_dbnomics", "ZUTN", "ZUTN")
    zutn = {geo: {y: v for y, v in rows.items() if y <= last_year} for geo, rows in zutn.items()}
    nawru = store.annual("ameco_dbnomics", "ZNAWRU", "ZNAWRU")
    nawru = {geo: {y: v for y, v in rows.items() if y <= last_year} for geo, rows in nawru.items()}
    esp = zutn["ESP"]

    # Europe as AMECO publishes it: three aggregates with different coverage, never spliced.
    europe = {
        "DU15": {y: v for y, v in zutn["DU15"].items() if y <= 1991},
        "EU15": zutn["EU15"],
        "EU27": zutn["EU27"],
    }
    ratios = {key: ratio(esp, rows) for key, rows in europe.items()}
    # Spain against the longest European reference available each year: UE-15 (RFA until 1990, then unified).
    ref_eu15 = {**{y: v for y, v in europe["DU15"].items() if y < 1991}, **europe["EU15"]}
    ratio_eu15 = ratio(esp, ref_eu15, 1.0)
    since = {y: v for y, v in ratio_eu15.items() if y >= HYPOTHESIS_FROM}
    before = {y: v for y, v in ratio_eu15.items() if y < 1977}
    decades = []
    for start in range(1970, last_year + 1, 10):
        span = [v for y, v in ratio_eu15.items() if start <= y < start + 10]
        if span:
            decades.append({"decade": start, "mean_ratio": r(mean(span)), "years": len(span),
                            "es_mean": r(mean(esp[y] for y in esp if start <= y < start + 10 and y in ratio_eu15)),
                            "eu_mean": r(mean(ref_eu15[y] for y in ref_eu15 if start <= y < start + 10 and y in ratio_eu15))})
    lowest_since = min(since.items(), key=lambda kv: kv[1])
    highest = max(ratio_eu15.items(), key=lambda kv: kv[1])
    ratio_eu27 = ratio(esp, europe["EU27"], 1.0)

    # Cyclical vs structural: Spain's swings and the Commission's NAWRU.
    peaks = {"min_pre_crisis": min(((y, esp[y]) for y in esp if 2004 <= y <= 2008), key=lambda kv: kv[1]),
             "max_crisis": max(((y, esp[y]) for y in esp if 2009 <= y <= 2016), key=lambda kv: kv[1]),
             "max_1990s": max(((y, esp[y]) for y in esp if 1990 <= y <= 1999), key=lambda kv: kv[1]),
             "max_1980s": max(((y, esp[y]) for y in esp if 1980 <= y <= 1989), key=lambda kv: kv[1])}
    nawru_esp = nawru["ESP"]
    nawru_eu = {**{y: v for y, v in nawru["DU15"].items() if y < 1991}, **nawru["EU15"]}
    nawru_ratio = ratio(nawru_esp, nawru_eu, 1.0)
    nawru_since = {y: v for y, v in nawru_ratio.items() if y >= HYPOTHESIS_FROM}
    gap = {y: esp[y] - nawru_esp[y] for y in esp if y in nawru_esp}

    # Peers (AMECO): Germany = West Germany until 1990, unified Germany since 1991 (two series).
    peers = {
        "DEU_W": {y: v for y, v in zutn["D_W"].items() if y <= 1991},
        "DEU": zutn["DEU"],
        "FRA": zutn["FRA"], "ITA": zutn["ITA"], "PRT": zutn["PRT"],
    }
    since_1980_rank = {
        area: mean(v for y, v in rows.items() if y >= HYPOTHESIS_FROM)
        for area, rows in {"ESP": esp, "FRA": peers["FRA"], "ITA": peers["ITA"], "PRT": peers["PRT"],
                           "DEU": {**{y: v for y, v in peers["DEU_W"].items() if y < 1991}, **peers["DEU"]}}.items()
    }

    # EPA (INE) as the national cross-check of AMECO since 2002.
    epa_total = quarterly_to_annual(store.series("ine_epa_tempus", "EPA", "EPA452434")["ESP"])
    epa_youth = quarterly_to_annual(store.series("ine_epa_tempus", "EPA", "EPA452436")["ESP"])
    epa_gap = max(abs(epa_total[y] - esp[y]) for y in epa_total if y in esp)

    # 2. Youth unemployment (Eurostat, two vintages).
    youth = store.annual("eurostat_sdmx", "une_rt_a", "Y15-24.PC_ACT.T")
    youth_h = store.annual("eurostat_sdmx", "une_rt_a_h", "Y15-24.PC_ACT.T")
    youth_ratio = ratio(youth["ES"], youth["EU27_2020"], 1.0)

    # 3. Temporary employees (Eurostat) and the EPA split of permanent contracts (INE).
    temp = store.annual("eurostat_sdmx", "lfsa_etpgan", "PC.T.Y15-64.TOTAL")
    temp_flags = store.flags("eurostat_sdmx", "lfsa_etpgan", "PC.T.Y15-64.TOTAL", "ES")
    employees_q = store.series("ine_epa_tempus", "EPA", "EPA416745")["ESP"]
    discont_q = store.series("ine_epa_tempus", "EPA", "EPA416748")["ESP"]
    temporal_q = store.series("ine_epa_tempus", "EPA", "EPA416749")["ESP"]
    share_q = {
        p: {"temporal": temporal_q[p] / employees_q[p] * 100, "discontinuo": discont_q[p] / employees_q[p] * 100}
        for p in sorted(employees_q) if p in discont_q and p in temporal_q
    }
    temporal_a = quarterly_to_annual({p: v["temporal"] for p, v in share_q.items()})
    discont_a = quarterly_to_annual({p: v["discontinuo"] for p, v in share_q.items()})
    discont_k = quarterly_to_annual(discont_q)
    last_q = max(share_q, key=lambda p: (int(p[:4]), int(p[5:])))

    # 4. Productivity per hour (Eurostat, rebased 1995 = 100) and levels (OECD, EU27 = 100).
    prod = store.annual("eurostat_sdmx", "nama_10_lp_ulc", "I15.RLPR_HW")
    prod_idx = {geo: {y: v / rows[PRODUCTIVITY_BASE] * 100 for y, v in rows.items() if y >= PRODUCTIVITY_BASE}
                for geo, rows in prod.items() if PRODUCTIVITY_BASE in rows}
    prod_last = min(max(rows) for rows in prod_idx.values())
    growth = {EUROSTAT_TO_AREA[geo]: rows[prod_last] - 100 for geo, rows in prod_idx.items()}
    pdb = store.annual("oecd_productivity", "DSD_PDB@DF_PDB", "GDPHRS._T.LR")
    level_vs_eu = {area: ratio(rows, pdb["EU27_2020"]) for area, rows in pdb.items() if area in ("ESP", "DEU", "FRA", "ITA", "PRT")}
    level_vs_eu = {area: {y: v for y, v in rows.items() if y >= PRODUCTIVITY_BASE} for area, rows in level_vs_eu.items()}

    # 5. Tax wedge (OECD Taxing Wages).
    wedge = store.annual("oecd_taxing_wages", TW := "DSD_TAX_WAGES_COMP@DF_TW_COMP", "AV_TW.S_C0.AW100")
    wedge_low = store.annual("oecd_taxing_wages", TW, "AV_TW.S_C0.AW67")
    wedge_last = max(wedge["ESP"])

    # 6. Employment rate 20-64 (Eurostat, two vintages).
    emp = store.annual("eurostat_sdmx", "lfsi_emp_a", "EMP_LFS.T.Y20-64.PC_POP")
    emp_h = store.annual("eurostat_sdmx", "lfsi_emp_a_h", "Y20-64.PC_POP.T.EMP_LFS")

    ev, ev_meta = events(conn)
    sources = {}
    for source_id, releases in store.provenance.items():
        label, page = SOURCE_PAGES[source_id]
        retrieved = max((rel["retrieved_at"] or "" for rel in releases), default="") or None
        sources[source_id] = {"label": label, "page": page, "retrieved_at": retrieved, "releases": releases}
    if ev:
        label, page = SOURCE_PAGES["vclc_employment_events"]
        sources["vclc_employment_events"] = {"label": label, "page": page, "retrieved_at": None, "releases": []}

    def eurostat_points(rows: dict[str, dict[int, float]]) -> dict[str, list[dict]]:
        return {EUROSTAT_TO_AREA[geo]: points(v) for geo, v in rows.items() if geo in EUROSTAT_TO_AREA}

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "storage": "SQLite employment-es.db: indicator_* contract (releases, revisions, evidence per value with JSON "
        "pointer + sha256 of the raw payload); built by scripts/ingest_employment_es.py",
        "headline": {
            "first_year": min(esp),
            "last_year": last_year,
            "es_last": r(esp[last_year]),
            "eu27_last": r(europe["EU27"][last_year]),
            "eu15_last": r(europe["EU15"][last_year]),
            "ratio_eu15_last": r(ratio_eu15[last_year]),
            "ratio_eu27_last": r(ratio_eu27[last_year]),
            "hypothesis_from": HYPOTHESIS_FROM,
            "ratio_mean_since": r(mean(since.values())),
            "years_since": len(since),
            "years_ratio_ge_1_5": sum(v >= 1.5 for v in since.values()),
            "years_ratio_ge_1_8": sum(v >= 1.8 for v in since.values()),
            "years_ratio_ge_2": sum(v >= 2.0 for v in since.values()),
            "ratio_lowest_since": {"year": lowest_since[0], "value": r(lowest_since[1])},
            "ratio_highest": {"year": highest[0], "value": r(highest[1])},
            "ratio_mean_before_1977": r(mean(before.values())) if before else None,
            "before_years": [min(before), max(before)] if before else None,
            "es_mean_1960_1974": r(mean(v for y, v in esp.items() if y <= 1974)),
            "mean_since_1980": {area: r(v) for area, v in since_1980_rank.items()},
            "peaks": {k: {"year": y, "value": r(v)} for k, (y, v) in peaks.items()},
            "nawru_last": r(nawru_esp[last_year]),
            "nawru_eu15_last": r(nawru_eu[last_year]),
            "nawru_ratio_mean_since": r(mean(nawru_since.values())),
            "nawru_min_since": {"year": min(nawru_since, key=lambda y: nawru_esp[y]), "value": r(min(nawru_esp[y] for y in nawru_since))},
            "gap_max": {"year": max(gap, key=gap.get), "value": r(max(gap.values()))},
            "gap_min": {"year": min(gap, key=gap.get), "value": r(min(gap.values()))},
            "epa_vs_ameco_max_gap": r(epa_gap),
            "youth_es_last": r(youth["ES"][last_year]),
            "youth_eu_last": r(youth["EU27_2020"][last_year]),
            "youth_ratio_mean": r(mean(youth_ratio.values())),
            "youth_es_max": {"year": max(youth["ES"], key=youth["ES"].get), "value": r(max(youth["ES"].values()))},
            "temp_es_2021": r(temp["ES"].get(2021)),
            "temp_es_last": r(temp["ES"][max(temp["ES"])]),
            "temp_eu_last": r(temp["EU27_2020"][max(temp["EU27_2020"])]),
            "temp_last_year": max(temp["ES"]),
            "temp_es_max": {"year": max(temp["ES"], key=temp["ES"].get), "value": r(max(temp["ES"].values()))},
            "discont_2021": r(discont_a.get(2021)),
            "discont_last": r(discont_a[max(discont_a)]),
            "discont_k_2021": r(discont_k.get(2021), 1),
            "discont_k_last": r(discont_k[max(discont_k)], 1),
            "discont_last_year": max(discont_a),
            "last_quarter": last_q,
            "last_quarter_temporal": r(share_q[last_q]["temporal"]),
            "last_quarter_discontinuo": r(share_q[last_q]["discontinuo"]),
            "productivity_base": PRODUCTIVITY_BASE,
            "productivity_last": prod_last,
            "productivity_growth_pct": {area: r(v, 1) for area, v in growth.items()},
            "level_vs_eu_first": {area: r(rows[PRODUCTIVITY_BASE], 1) for area, rows in level_vs_eu.items() if PRODUCTIVITY_BASE in rows},
            "level_vs_eu_last": {area: r(rows[max(rows)], 1) for area, rows in level_vs_eu.items()},
            "level_last_year": max(level_vs_eu["ESP"]),
            "wedge_last_year": wedge_last,
            "wedge_last": {area: r(rows[wedge_last], 1) for area, rows in wedge.items() if wedge_last in rows},
            "wedge_low_last": {area: r(rows[wedge_last], 1) for area, rows in wedge_low.items() if wedge_last in rows},
            "wedge_first": {area: r(rows[min(rows)], 1) for area, rows in wedge.items()},
            "wedge_first_year": min(wedge["ESP"]),
            "emp_es_last": r(emp["ES"][max(emp["ES"])]),
            "emp_eu_last": r(emp["EU27_2020"][max(emp["EU27_2020"])]),
            "emp_last_year": max(emp["ES"]),
        },
        "unemployment": {
            "amecos": {"ESP": points(esp), **{k: points(v) for k, v in europe.items()}},
            "peers": {k: points(v) for k, v in peers.items()},
            "epa_annual": points(epa_total),
            "epa_youth_annual": points(epa_youth),
        },
        "ratio_es_europe": {k: points(v, 1) for k, v in ratios.items()},
        "ratio_decades": decades,
        "nawru": {
            "ESP": points(nawru_esp), "DU15": points({y: v for y, v in nawru["DU15"].items() if y <= 1991}),
            "EU15": points(nawru["EU15"]), "EU27": points(nawru["EU27"]),
            "gap_es": points(gap),
        },
        "youth": {"current": eurostat_points(youth), "historical": eurostat_points(youth_h)},
        "temporary": {
            "eurostat": eurostat_points(temp),
            "eurostat_es_flags": {str(y): f for y, f in sorted(temp_flags.items())},
            "epa_temporal_share": points(temporal_a),
            "epa_discontinuo_share": points(discont_a),
            "epa_discontinuo_thousands": points(discont_k, 1),
        },
        "productivity": {
            "index_1995": eurostat_points(prod_idx),
            "level_vs_eu27": {area: points(rows, 1) for area, rows in level_vs_eu.items()},
        },
        "tax_wedge": {"aw100": {area: points(rows) for area, rows in wedge.items()},
                      "aw67": {area: points(rows) for area, rows in wedge_low.items()}},
        "employment_rate": {"current": eurostat_points(emp), "historical": eurostat_points(emp_h)},
        "events": ev,
        "gaps": ev_meta.get("gaps", []),
        "blocked_hosts": ev_meta.get("blocked_hosts", []),
        "sources": sources,
    }


def write_csv(data: dict, path: Path) -> None:
    rows: list[tuple] = []

    def add(source: str, serie: str, by_area: dict[str, list[dict]]) -> None:
        for area, pts in by_area.items():
            rows.extend((source, serie, area, p["year"], p["value"]) for p in pts)

    add("ameco_dbnomics", "tasa_paro_pct_activos", data["unemployment"]["amecos"])
    add("ameco_dbnomics", "tasa_paro_pct_activos", data["unemployment"]["peers"])
    add("ine_epa_tempus", "tasa_paro_16_mas_media_anual", {"ESP": data["unemployment"]["epa_annual"]})
    add("ine_epa_tempus", "tasa_paro_menores_25_media_anual", {"ESP": data["unemployment"]["epa_youth_annual"]})
    add("ameco_dbnomics", "paro_espana_sobre_europa_100", data["ratio_es_europe"])
    add("ameco_dbnomics", "nawru_pct_activos", {k: v for k, v in data["nawru"].items() if k != "gap_es"})
    add("ameco_dbnomics", "paro_menos_nawru_puntos", {"ESP": data["nawru"]["gap_es"]})
    add("eurostat_sdmx:une_rt_a", "tasa_paro_15_24", data["youth"]["current"])
    add("eurostat_sdmx:une_rt_a_h", "tasa_paro_15_24", data["youth"]["historical"])
    add("eurostat_sdmx:lfsa_etpgan", "temporales_pct_asalariados_15_64", data["temporary"]["eurostat"])
    add("ine_epa_tempus", "temporales_pct_asalariados_media_anual", {"ESP": data["temporary"]["epa_temporal_share"]})
    add("ine_epa_tempus", "fijos_discontinuos_pct_asalariados_media_anual", {"ESP": data["temporary"]["epa_discontinuo_share"]})
    add("ine_epa_tempus", "fijos_discontinuos_miles_media_anual", {"ESP": data["temporary"]["epa_discontinuo_thousands"]})
    add("eurostat_sdmx:nama_10_lp_ulc", f"productividad_hora_indice_{PRODUCTIVITY_BASE}_100", data["productivity"]["index_1995"])
    add("oecd_productivity", "pib_hora_ppa_ue27_100", data["productivity"]["level_vs_eu27"])
    add("oecd_taxing_wages", "cuna_fiscal_100_salario_medio_pct_coste", data["tax_wedge"]["aw100"])
    add("oecd_taxing_wages", "cuna_fiscal_67_salario_medio_pct_coste", data["tax_wedge"]["aw67"])
    add("eurostat_sdmx:lfsi_emp_a", "tasa_empleo_20_64", data["employment_rate"]["current"])
    add("eurostat_sdmx:lfsi_emp_a_h", "tasa_empleo_20_64", data["employment_rate"]["historical"])
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["fuente", "serie", "area", "anio", "valor"])
    writer.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    if not args.db.exists():
        if OUT_JSON.exists():
            print(f"export_public_viz_employment: {args.db.name} not found; keeping committed artifact", file=sys.stderr)
            return 0
        raise SystemExit(f"missing {args.db}; run scripts/ingest_employment_es.py first")
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    data = build(conn)
    conn.close()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    write_csv(data, OUT_CSV)
    h = data["headline"]
    print(
        f"empleo: paro {h['last_year']} {h['es_last']}% (UE-27 {h['eu27_last']}%), ratio medio desde {h['hypothesis_from']} "
        f"x{h['ratio_mean_since']}; {OUT_JSON.stat().st_size // 1024} KB"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
