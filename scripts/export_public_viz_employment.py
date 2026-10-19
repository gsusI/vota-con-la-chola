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
PEER_AREAS = ["ESP", "DEU", "FRA", "ITA", "PRT", "EU27"]
NUTS_COUNTRY = {"ES": "ESP", "DE": "DEU", "FR": "FRA", "IT": "ITA", "PT": "PRT"}
EU27_PREFIXES = ("AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "EL", "ES", "FI", "FR", "HR", "HU", "IE", "IT", "LT", "LU",
                 "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK")
EPISODES = [(2007, 2013, "Gran Recesión y crisis del euro"), (2019, 2020, "Pandemia")]
SOURCE_PAGES = {
    "ameco_dbnomics": ("Comisión Europea · AMECO (réplica DBnomics)", "https://economy-finance.ec.europa.eu/economic-research-and-databases/economic-databases/ameco-database_en"),
    "eurostat_sdmx": ("Eurostat · Encuesta de Población Activa de la UE y contabilidad nacional", "https://ec.europa.eu/eurostat/web/lfs/database"),
    "ine_epa_tempus": ("INE · Encuesta de Población Activa (API Tempus)", "https://www.ine.es/dyngs/INEbase/es/operacion.htm?c=Estadistica_C&cid=1254736176918&idp=1254735976595"),
    "oecd_taxing_wages": ("OCDE · Taxing Wages (réplica DBnomics)", "https://db.nomics.world/OECD/DSD_TAX_WAGES_COMP@DF_TW_COMP"),
    "oecd_productivity": ("OCDE · Productivity Database (réplica DBnomics)", "https://db.nomics.world/OECD/DSD_PDB@DF_PDB"),
    "oecd_earnings": ("OCDE · Earnings, salario mínimo frente al mediano (réplica DBnomics)", "https://db.nomics.world/OECD/DSD_EARNINGS@MIN2AVE"),
    "oecd_registered_unemployment": ("OCDE · paro registrado del SEPE (réplica DBnomics)", "https://db.nomics.world/OECD/DSD_OLAB@DF_OIALAB_INDIC"),
    "ine_ipt_tempus": ("INE · Índice de Precios del Trabajo", "https://www.ine.es/dyngs/INEbase/es/operacion.htm?c=Estadistica_C&cid=1254736177027&idp=1254735976596"),
    "ine_eaes_tempus": ("INE · Encuesta Anual de Estructura Salarial", "https://www.ine.es/dyngs/INEbase/es/operacion.htm?c=Estadistica_C&cid=1254736177025&idp=1254735976596"),
    "dg_empl_lmp": ("Comisión Europea, DG EMPL · base de datos de políticas de mercado de trabajo (LMP)", "https://webgate.ec.europa.eu/empl/redisstat/databrowser/explore/all/lmp?lang=en"),
    "oecd_taxben": ("OCDE · Tax-Benefit, renta neta con el salario mínimo (réplica DBnomics)", "https://db.nomics.world/OECD/DSD_TAXBEN_IMW@DF_IMW"),
    "seg_social_pxweb": ("Seguridad Social · afiliación media y días cotizados (PX-Web)", "https://w6.seg-social.es/PXWeb/"),
    "mites_anuario": ("Ministerio de Trabajo · Anuario de Estadísticas, Movimiento Laboral Registrado", "https://www.mites.gob.es/es/estadisticas/anuarios/"),
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
    # The gap opens the first year Spain's rate is 1.2 times the European one or more; before that, «similar».
    gap_from = min(y for y, v in ratio_eu15.items() if v >= 1.2)
    before = {y: v for y, v in ratio_eu15.items() if y < gap_from}
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

    extended = build_extended(store, last_year, esp)
    extended["intermittency"] = intermittency(store)
    extended["capacity"] = capacity(store)
    reg_u_all = store.annual("eurostat_sdmx", "lfst_r_lfu3rt", "TOTAL.T.Y15-74.PC")
    extended["composition"] = composition_distribution(store, last_year, reg_u_all)
    extended["labour_policy"] = labour_policy(store, nawru, last_year)
    extended["narratives"] = narratives(store, esp, zutn, nawru, last_year, extended["intermittency"])
    extended["segments"] = segments_by_group(store)
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
            "gap_from_year": gap_from,
            "ratio_mean_before_gap": r(mean(before.values())) if before else None,
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
        **extended,
        "events": ev,
        "gaps": ev_meta.get("gaps", []),
        "blocked_hosts": ev_meta.get("blocked_hosts", []),
        "sources": sources,
    }


def pct_change(rows: dict[int, float], a: int, b: int) -> float | None:
    return (rows[b] / rows[a] - 1) * 100 if a in rows and b in rows and rows[a] else None


def rebase(rows: dict[int, float], base: int) -> dict[int, float]:
    return {y: v / rows[base] * 100 for y, v in rows.items() if y >= base} if base in rows else {}


def build_extended(store: Store, last_year: int, esp_rate: dict[int, float]) -> dict:
    """Causes, cycle amplitude, regions, wages: every figure derived from stored observations."""
    out: dict = {}

    # Registered unemployment (SEPE via OECD) against EPA-based unemployed (AMECO NUTN), thousands.
    reg = {y: v / 1000 for y, v in store.annual("oecd_registered_unemployment", "DSD_OLAB@DF_OIALAB_INDIC", "REG_UNE.A")["ESP"].items() if y <= last_year}
    epa = {y: v for y, v in store.annual("ameco_dbnomics", "NUTN", "NUTN")["ESP"].items() if y <= last_year}
    gap_years = sorted(set(reg) & set(epa))
    out["registered"] = {
        "sepe": points(reg, 1), "epa": points(epa, 1),
        "ratio": points({y: reg[y] / epa[y] * 100 for y in gap_years}, 1),
        "last": {"year": gap_years[-1], "sepe": r(reg[gap_years[-1]], 1), "epa": r(epa[gap_years[-1]], 1)},
        "max_gap": max(({"year": y, "sepe": r(reg[y], 1), "epa": r(epa[y], 1), "diff": r(epa[y] - reg[y], 1)} for y in gap_years), key=lambda x: x["diff"]),
    }

    # Cycle amplitude: GDP and employment changes in each recession (AMECO), plus Spain's annual growth.
    gdp = store.annual("ameco_dbnomics", "OVGD", "OVGD")
    emp = store.annual("ameco_dbnomics", "NETD", "NETD")
    rate = store.annual("ameco_dbnomics", "ZUTN", "ZUTN")
    episodes = []
    for a, b, label in EPISODES:
        rows = []
        for area in PEER_AREAS:
            g, e = pct_change(gdp.get(area, {}), a, b), pct_change(emp.get(area, {}), a, b)
            u = rate.get(area, {})
            rows.append({"area": area, "gdp": r(g, 1), "employment": r(e, 1),
                         "unemployment_pp": r(u[b] - u[a], 1) if a in u and b in u else None})
        episodes.append({"from": a, "to": b, "label": label, "rows": rows})
    out["cycle"] = {
        "episodes": episodes,
        "es_growth": {
            "gdp": points({y: (gdp["ESP"][y] / gdp["ESP"][y - 1] - 1) * 100 for y in gdp["ESP"] if y - 1 in gdp["ESP"] and y <= last_year}, 1),
            "employment": points({y: (emp["ESP"][y] / emp["ESP"][y - 1] - 1) * 100 for y in emp["ESP"] if y - 1 in emp["ESP"] and y <= last_year}, 1),
        },
    }

    # Who absorbed the job losses (EPA, annual means of quarters): temporary vs permanent employees.
    temporal = quarterly_to_annual(store.series("ine_epa_tempus", "EPA", "EPA416749")["ESP"])
    indefinido = quarterly_to_annual(store.series("ine_epa_tempus", "EPA", "EPA416746")["ESP"])
    out["contract_adjustment"] = [
        {"from": a, "to": b, "label": label, "temporal": r(temporal[b] - temporal[a], 1), "indefinido": r(indefinido[b] - indefinido[a], 1),
         "temporal_share_from": r(temporal[a] / (temporal[a] + indefinido[a]) * 100, 1)}
        for a, b, label in [(2007, 2013, "Gran Recesión y crisis del euro"), (2019, 2020, "Pandemia (con ERTE)")]
        if a in temporal and b in temporal
    ]

    # Sector mix: construction share of employment and the 2007-2013 losses by sector (Eurostat national accounts).
    sectors = {code: store.annual("eurostat_sdmx", "nama_10_a10_e", f"THS_PER.{code}.EMP_DC") for code in ("TOTAL", "F", "A", "C", "G-I")}
    total = sectors["TOTAL"]
    out["construction_share"] = {
        EUROSTAT_TO_AREA[geo]: points({y: v / total[geo][y] * 100 for y, v in rows.items() if y in total.get(geo, {}) and y >= 1995}, 1)
        for geo, rows in sectors["F"].items() if geo in EUROSTAT_TO_AREA
    }
    loss = {code: sectors[code]["ES"][2013] - sectors[code]["ES"][2007] for code in sectors}
    out["sector_losses_es"] = {
        "from": 2007, "to": 2013, "total": r(loss["TOTAL"], 1),
        "by_sector": {code: r(v, 1) for code, v in loss.items() if code != "TOTAL"},
        "construction_share_of_loss": r(loss["F"] / loss["TOTAL"] * 100, 1),
        "construction_peak": max(((y, v) for y, v in ((y, sectors["F"]["ES"][y] / total["ES"][y] * 100) for y in sectors["F"]["ES"])), key=lambda kv: kv[1]),
    }
    out["sector_losses_es"]["construction_peak"] = {"year": out["sector_losses_es"]["construction_peak"][0], "value": r(out["sector_losses_es"]["construction_peak"][1], 1)}

    # Long-term unemployment.
    ltu = store.annual("eurostat_sdmx", "une_ltu_a", "LTU.Y15-74.T.PC_ACT")
    ltu_h = store.annual("eurostat_sdmx", "une_ltu_a_h", "LTU.Y15-74.T.PC_ACT")
    ltu_share = store.annual("eurostat_sdmx", "une_ltu_a", "LTU.Y15-74.T.PC_UNE")
    ltu_share_h = store.annual("eurostat_sdmx", "une_ltu_a_h", "LTU.Y15-74.T.PC_UNE")
    out["long_term"] = {
        "rate": {EUROSTAT_TO_AREA[g]: points(v) for g, v in ltu.items() if g in EUROSTAT_TO_AREA},
        "rate_h": {EUROSTAT_TO_AREA[g]: points(v) for g, v in ltu_h.items() if g in EUROSTAT_TO_AREA},
        "share": {EUROSTAT_TO_AREA[g]: points(v) for g, v in ltu_share.items() if g in EUROSTAT_TO_AREA},
        "share_h": {EUROSTAT_TO_AREA[g]: points(v) for g, v in ltu_share_h.items() if g in EUROSTAT_TO_AREA},
    }

    # Education: unemployment by attainment and share of low-educated adults.
    edu_rate = {lvl: store.annual("eurostat_sdmx", "lfsa_urgaed", f"PC.T.Y25-64.{lvl}") for lvl in ("ED0-2", "ED3_4", "ED5-8", "TOTAL")}
    edu_pop = {lvl: store.annual("eurostat_sdmx", "edat_lfse_03", f"T.Y25-64.PC.{lvl}") for lvl in ("ED0-2", "ED5-8")}
    out["education"] = {
        "rate": {lvl: {EUROSTAT_TO_AREA[g]: points(v) for g, v in rows.items() if g in EUROSTAT_TO_AREA} for lvl, rows in edu_rate.items()},
        "population": {lvl: {EUROSTAT_TO_AREA[g]: points(v) for g, v in rows.items() if g in EUROSTAT_TO_AREA} for lvl, rows in edu_pop.items()},
    }

    # Firm size: share of persons employed by size class (latest year with data for every area).
    size = {cls: store.annual("eurostat_sdmx", "sbs_sc_ovw", f"EMP_NR.B-S_X_O_S94.{cls}") for cls in ("TOTAL", "0-9", "10-19", "20-49", "50-249", "GE250")}
    common = sorted(set.intersection(*(set(size[c].get(g, {})) for c in size for g in EUROSTAT_TO_AREA)))
    size_year = common[-1] if common else max(size["TOTAL"]["ES"])
    out["firm_size"] = {
        "year": size_year,
        "shares": {
            EUROSTAT_TO_AREA[g]: {cls: r(size[cls][g][size_year] / size["TOTAL"][g][size_year] * 100, 1) for cls in size if cls != "TOTAL" and size_year in size[cls].get(g, {})}
            for g in EUROSTAT_TO_AREA if size_year in size["TOTAL"].get(g, {})
        },
    }

    # Minimum wage relative to the median full-time wage.
    mw = store.annual("oecd_earnings", "DSD_EARNINGS@MIN2AVE", "MR_WG_FT.MEDIAN")
    out["minimum_wage"] = {area: points(rows, 1) for area, rows in mw.items()}

    # Real compensation per employee vs real GDP per person employed (AMECO), 1995 = 100.
    wage = store.annual("ameco_dbnomics", "RWCDC", "RWCDC")
    prod = store.annual("ameco_dbnomics", "RVGDE", "RVGDE")
    out["wages_productivity"] = {
        area: {"wage": points({y: v for y, v in rebase(wage[area], PRODUCTIVITY_BASE).items() if y <= last_year}, 1),
               "productivity": points({y: v for y, v in rebase(prod[area], PRODUCTIVITY_BASE).items() if y <= last_year}, 1)}
        for area in PEER_AREAS if area in wage and area in prod
    }

    # Regions: NUTS 2 unemployment and employment rates, dispersion across countries.
    reg_u = store.annual("eurostat_sdmx", "lfst_r_lfu3rt", "TOTAL.T.Y15-74.PC")
    reg_e = store.annual("eurostat_sdmx", "lfst_r_lfe2emprt", "PC.T.Y20-64")
    names = dict(store.conn.execute(
        "SELECT DISTINCT geography_code, geography_name FROM indicator_series_versions WHERE geography_level = 'nuts2'"
    ).fetchall())
    reg_year = max(y for g, rows in reg_u.items() if g.startswith("ES") and len(g) == 4 for y in rows)
    spain = sorted(
        ({"code": g, "name": names.get(g, g), "unemployment": r(rows[reg_year], 1), "employment": r(reg_e.get(g, {}).get(reg_year), 1),
          "unemployment_2007": r(rows.get(2007), 1), "unemployment_2013": r(rows.get(2013), 1)}
         for g, rows in reg_u.items() if g.startswith("ES") and len(g) == 4 and reg_year in rows),
        key=lambda x: -x["unemployment"],
    )
    ranges = {}
    for prefix, area in NUTS_COUNTRY.items():
        rows = [(g, v[reg_year]) for g, v in reg_u.items() if g.startswith(prefix) and len(g) == 4 and reg_year in v]
        if rows:
            lo, hi = min(rows, key=lambda kv: kv[1]), max(rows, key=lambda kv: kv[1])
            ranges[area] = {"min": {"code": lo[0], "name": names.get(lo[0], lo[0]), "value": r(lo[1], 1)},
                            "max": {"code": hi[0], "name": names.get(hi[0], hi[0]), "value": r(hi[1], 1)}, "regions": len(rows)}
    eu_regions = sorted(((g, v[reg_year]) for g, v in reg_u.items() if len(g) == 4 and g[:2] in EU27_PREFIXES and reg_year in v),
                        key=lambda kv: -kv[1])
    top20 = eu_regions[:20]
    eu_rate = store.annual("eurostat_sdmx", "une_rt_a", "Y15-74.PC_ACT.T")["EU27_2020"].get(reg_year)
    store.provenance["eurostat_sdmx"].pop()
    disp = store.annual("eurostat_sdmx", "lfst_r_lmdur", "DISP_NUTS2.T.Y15-74.PC")
    out["regions"] = {
        "year": reg_year, "spain": spain, "ranges": ranges, "eu27_rate": r(eu_rate, 1), "eu_regions": len(eu_regions),
        "spain_above_eu": sum(row["unemployment"] > eu_rate for row in spain) if eu_rate else None,
        "spanish_in_top20": sum(g.startswith("ES") for g, _ in top20),
        "eu_top20": [{"code": g, "name": names.get(g, g), "value": r(v, 1), "spanish": g.startswith("ES")} for g, v in top20],
        "dispersion": {EUROSTAT_TO_AREA[g]: points(v, 1) for g, v in disp.items() if g in EUROSTAT_TO_AREA},
    }
    return out


def intermittency(store: Store) -> dict:
    """Fijos discontinuos: affiliation in alta (monthly), days per contributor, inactive job seekers and contracts."""
    aff = {code: store.series("seg_social_pxweb", "afiliados_medios_07m", code)["ESP"] for code in ("TOTAL", "IND_TC", "IND_TP", "IND_FD")}
    months = sorted(aff["IND_FD"])
    monthly = [{"month": m, "fd": r(aff["IND_FD"][m], 0), "share": r(aff["IND_FD"][m] / aff["TOTAL"][m] * 100, 2)} for m in months if m >= "2019-01"]
    by_year: dict[int, list[float]] = defaultdict(list)
    for m in months:
        by_year[int(m[:4])].append(aff["IND_FD"][m])
    annual_fd = {y: mean(v) for y, v in by_year.items() if len(v) == 12}
    swing = {y: {"max": r(max(v), 0), "min": r(min(v), 0), "max_over_min": r(max(v) / min(v), 2)} for y, v in by_year.items() if len(v) == 12}

    days: dict[str, dict[str, float]] = {}
    for ctype in ("FD_TC", "FD_TP", "IND_TC", "IND_TP"):
        for val in ("DIAS_TOTALES", "COTIZANTES"):
            days[f"{ctype}.{val}"] = store.series("seg_social_pxweb", "dias_cotizados_cnae09", f"{ctype}.{val}")["ESP"]
    def per_contributor(prefix: str) -> dict[int, float]:
        out: dict[int, list[float]] = defaultdict(list)
        for m in days[f"{prefix}_TC.DIAS_TOTALES"]:
            d = days[f"{prefix}_TC.DIAS_TOTALES"][m] + days[f"{prefix}_TP.DIAS_TOTALES"].get(m, 0)
            c = days[f"{prefix}_TC.COTIZANTES"].get(m, 0) + days[f"{prefix}_TP.COTIZANTES"].get(m, 0)
            if c:
                out[int(m[:4])].append(d / c)
        return {y: mean(v) for y, v in out.items() if len(v) == 12}
    fd_days, ind_days = per_contributor("FD"), per_contributor("IND")

    def latest_edition(dataset_sheet: str, code: str) -> dict[int, float]:
        merged: dict[int, float] = {}
        for edition in (2023, 2024, 2025):
            try:
                rows = store.annual("mites_anuario", f"anuario_{edition}_{dataset_sheet}", code)
            except LookupError:
                continue
            merged.update(rows.get("ESP", {}))
        return merged
    seekers = latest_edition("MLR-18", "demandantes_fijos_discontinuos")
    contracts_fd = latest_edition("MLR-25", "contratos_fijos_discontinuos")
    contracts_total = latest_edition("MLR-25", "contratos_total")
    inactive_share = {y: seekers[y] / (seekers[y] + annual_fd[y]) * 100 for y in seekers if y in annual_fd}
    return {
        "monthly_affiliates": monthly,
        "annual_affiliates": points(annual_fd, 0),
        "seasonal_swing": {str(y): v for y, v in sorted(swing.items())},
        "days_per_contributor": {"fd": points(fd_days, 1), "indefinido": points(ind_days, 1)},
        "inactive_job_seekers": points(seekers, 0),
        "inactive_share_estimate": points(inactive_share, 1),
        "contracts_fd": points(contracts_fd, 0),
        "contracts_total": points(contracts_total, 0),
        "affiliates_regime": "Régimen General",
        "seekers_last_edition_year": max(seekers) if seekers else None,
    }


def narratives(store: Store, esp: dict[int, float], zutn: dict, nawru: dict, last_year: int, inter: dict) -> dict:
    """«El dato mata el relato»: (1) Spain-EU gap split into structural and cyclical parts; (2) employees by contract."""
    eu = {**{y: v for y, v in zutn["DU15"].items() if y < 1991}, **zutn["EU15"]}
    n_es = nawru["ESP"]
    n_eu = {**{y: v for y, v in nawru["DU15"].items() if y < 1991}, **nawru["EU15"]}
    rows = []
    for y in range(HYPOTHESIS_FROM, last_year + 1):
        if all(y in m for m in (esp, eu, n_es, n_eu)):
            gap, structural = esp[y] - eu[y], n_es[y] - n_eu[y]
            rows.append({"year": y, "gap": r(gap), "structural": r(structural), "cyclical": r(gap - structural),
                         "es": r(esp[y]), "eu": r(eu[y]), "nawru_es": r(n_es[y]), "nawru_eu": r(n_eu[y]),
                         "eu_ref": "UE-15 con la RFA" if y < 1991 else "UE-15"})
    cyc_min = min(rows, key=lambda x: x["cyclical"])
    cyc_max = max(rows, key=lambda x: x["cyclical"])
    structural_block = {
        "rows": rows,
        "mean_gap": r(mean(x["gap"] for x in rows)),
        "mean_structural": r(mean(x["structural"] for x in rows)),
        "structural_share": r(mean(x["structural"] for x in rows) / mean(x["gap"] for x in rows) * 100, 0),
        "cyclical_min": {"year": cyc_min["year"], "value": cyc_min["cyclical"]},
        "cyclical_max": {"year": cyc_max["year"], "value": cyc_max["cyclical"]},
        "years_cyclical_dominates": sum(abs(x["cyclical"]) > abs(x["structural"]) for x in rows),
        "structural_min": min(({"year": x["year"], "value": x["structural"]} for x in rows), key=lambda x: x["value"]),
    }

    total = store.series("ine_epa_tempus", "EPA", "EPA416745")["ESP"]
    indef = store.series("ine_epa_tempus", "EPA", "EPA416746")["ESP"]
    fd = store.series("ine_epa_tempus", "EPA", "EPA416748")["ESP"]
    temp = store.series("ine_epa_tempus", "EPA", "EPA416749")["ESP"]
    quarters = [q for q in sorted(total, key=lambda q: (int(q[:4]), int(q[5:]))) if int(q[:4]) >= 2019 and q in indef and q in fd and q in temp]
    qrows = [{"quarter": q, "ordinary": r(indef[q] - fd[q], 1), "fd": r(fd[q], 1), "temporal": r(temp[q], 1), "total": r(total[q], 1)} for q in quarters]
    def annual(series: dict[str, float]) -> dict[int, float]:
        return quarterly_to_annual({q: v for q, v in series.items()})
    a_ord = annual({q: indef[q] - fd[q] for q in indef if q in fd})
    a_fd, a_tmp, a_tot = annual(fd), annual(temp), annual(total)
    base, last = 2021, max(y for y in a_tot if y in a_ord)
    seekers = {p["year"]: p["value"] / 1000 for p in inter.get("inactive_job_seekers", [])}
    affiliates = {p["year"]: p["value"] / 1000 for p in inter.get("annual_affiliates", [])}
    reform_block = {
        "quarters": qrows,
        "base_year": base, "last_year": last,
        "annual": {str(y): {"ordinary": r(a_ord[y], 1), "fd": r(a_fd[y], 1), "temporal": r(a_tmp[y], 1), "total": r(a_tot[y], 1)}
                   for y in sorted(a_tot) if y >= 2019 and y in a_ord},
        "change": {"ordinary": r(a_ord[last] - a_ord[base], 1), "fd": r(a_fd[last] - a_fd[base], 1),
                   "temporal": r(a_tmp[last] - a_tmp[base], 1), "total": r(a_tot[last] - a_tot[base], 1)},
        "fd_inactive_seekers": points(seekers, 1),
        "fd_affiliates_in_alta": points({y: v for y, v in affiliates.items() if y >= 2019}, 1),
    }
    return {"structural_gap": structural_block, "reform": reform_block}


def segments(rows: dict[int, float], flags: dict[int, str]) -> list[dict[int, float]]:
    """Split a series at Eurostat break flags ('b'): each segment starts at a flagged year."""
    out: list[dict[int, float]] = [{}]
    for y in sorted(rows):
        if "b" in (flags.get(y) or "") and out[-1]:
            out.append({})
        out[-1][y] = rows[y]
    return out


def capacity(store: Store) -> dict:
    """Capacity lens: net pay (real, PPS), the minimum wage net and in PPS, in-work poverty."""
    hicp = store.annual("eurostat_sdmx", "prc_hicp_aind", "INX_A_AVG.CP00")
    cases = {"P1_NCH_AW100": "single_aw100", "P1_NCH_AW67": "single_aw67", "CPL_CH2_AW100": "couple2_aw100"}
    out: dict = {"cases": cases, "real_eur": {}, "pps_net": {}, "breaks": []}
    flags = store.flags("eurostat_sdmx", "earn_nt_net", "EUR.NET.P1_NCH_AW100", "ES")
    out["breaks"] = sorted(y for y, f in flags.items() if "b" in f)
    es_hicp = hicp["ES"]
    base_year = max(es_hicp)
    for ecase, key in cases.items():
        for kind in ("NET", "GRS"):
            rows = store.annual("eurostat_sdmx", "earn_nt_net", f"EUR.{kind}.{ecase}").get("ES", {})
            real = {y: v * es_hicp[base_year] / es_hicp[y] for y, v in rows.items() if y in es_hicp}
            out["real_eur"][f"{key}_{kind.lower()}"] = [points(seg, 0) for seg in segments(real, flags)]
        pps = store.annual("eurostat_sdmx", "earn_nt_net", f"PPS.NET.{ecase}")
        out["pps_net"][key] = {EUROSTAT_TO_AREA[g]: points(v, 0) for g, v in pps.items() if g in EUROSTAT_TO_AREA}
    out["real_base_year"] = base_year
    first_seg = out["real_eur"]["single_aw100_net"][0]
    gross_seg = out["real_eur"]["single_aw100_grs"][0]
    out["net_growth_first_segment"] = {
        "from": first_seg[0]["year"], "to": first_seg[-1]["year"],
        "net_pct": r((first_seg[-1]["value"] / first_seg[0]["value"] - 1) * 100, 1),
        "gross_pct": r((gross_seg[-1]["value"] / gross_seg[0]["value"] - 1) * 100, 1),
    }
    net_es = store.annual("eurostat_sdmx", "earn_nt_net", "EUR.NET.P1_NCH_AW100")["ES"]
    grs_es = store.annual("eurostat_sdmx", "earn_nt_net", "EUR.GRS.P1_NCH_AW100")["ES"]
    out["net_share_of_gross"] = points({y: net_es[y] / grs_es[y] * 100 for y in net_es if y in grs_es}, 1)

    mw = store.series("eurostat_sdmx", "earn_mw_cur", "PPS")
    mw_eur = store.series("eurostat_sdmx", "earn_mw_cur", "EUR")
    last_sem = max(mw["ES"])
    out["min_wage_pps"] = {"period": last_sem, "values": {g: r(v.get(last_sem), 0) for g, v in mw.items() if v.get(last_sem) is not None}}
    out["min_wage_es"] = {"eur": [{"period": k, "value": r(v, 0)} for k, v in sorted(mw_eur["ES"].items())],
                          "pps": [{"period": k, "value": r(v, 0)} for k, v in sorted(mw["ES"].items())]}
    net_mw = store.annual("oecd_taxben", "DSD_TAXBEN_IMW@DF_IMW", "NFI.MINW.S_C0.vs_MEDIAN")
    out["min_wage_net_vs_median"] = {area: points(rows, 1) for area, rows in net_mw.items()}

    iw = store.annual("eurostat_sdmx", "ilc_iw01", "EMP.T.Y_GE18.PC")
    out["in_work_poverty"] = {EUROSTAT_TO_AREA[g]: points(v, 1) for g, v in iw.items() if g in EUROSTAT_TO_AREA}
    return out


def labour_policy(store: Store, nawru: dict, last_year: int) -> dict:
    """Money in vs results out: spending on labour market policies per person wanting to work and % of GDP."""
    kinds = {"1": "services", "TOT2_7": "active", "TOT8_9": "passive", "TOT1_9": "total"}
    pps = {k: store.annual("dg_empl_lmp", "lmp_ind_exp", f"PPS_PWW.{code}.XTOT") for code, k in kinds.items()}
    gdp = {k: store.annual("dg_empl_lmp", "lmp_ind_exp", f"PC_GDP.{code}.XTOT") for code, k in kinds.items()}
    act = store.annual("dg_empl_lmp", "lmp_ind_actru", "RT.TOTAL.T.REG_UNE.TOT2_7")
    ltu_share = store.annual("eurostat_sdmx", "une_ltu_a", "LTU.Y15-74.T.PC_UNE")
    ltu_rate = store.annual("eurostat_sdmx", "une_ltu_a", "LTU.Y15-74.T.PC_ACT")
    year = max(y for y in pps["active"]["ES"] if all(y in pps[k].get("ES", {}) for k in pps))
    nawru_map = {"ES": "ESP", "DE": "DEU", "FR": "FRA", "IT": "ITA", "PT": "PRT", "EU27_2020": "EU27"}
    rows = []
    for geo, area in nawru_map.items():
        def v(table: dict, y: int = year) -> float | None:
            return table.get(geo, {}).get(y)
        rows.append({
            "area": area, "year": year,
            **{f"pps_{k}": r(v(pps[k]), 0) for k in kinds.values()},
            **{f"gdp_{k}": r(v(gdp[k]), 2) for k in kinds.values()},
            "activation": r(v(act), 1), "ltu_share": r(v(ltu_share), 1), "ltu_rate": r(v(ltu_rate), 1),
            "nawru": r(nawru.get(area, {}).get(year), 1),
        })
    series = {
        f"{measure}_{k}": {EUROSTAT_TO_AREA[g]: points(rows_, 2 if measure == "gdp" else 0) for g, rows_ in table[k].items() if g in EUROSTAT_TO_AREA}
        for measure, table in (("pps", pps), ("gdp", gdp)) for k in kinds.values()
    }
    return {"year": year, "rows": rows, "series": series,
            "activation": {EUROSTAT_TO_AREA[g]: points(v_, 1) for g, v_ in act.items() if g in EUROSTAT_TO_AREA}}


BASES = [1995, 2000, 2008, 2013, 2019]
NUTS2_TO_INE = {"ES11": "Galicia", "ES12": "Asturias, Principado de", "ES13": "Cantabria", "ES21": "País Vasco",
                "ES22": "Navarra, Comunidad Foral de", "ES23": "Rioja, La", "ES24": "Aragón", "ES30": "Madrid, Comunidad de",
                "ES41": "Castilla y León", "ES42": "Castilla - La Mancha", "ES43": "Extremadura", "ES51": "Cataluña",
                "ES52": "Comunitat Valenciana", "ES53": "Balears, Illes", "ES61": "Andalucía", "ES62": "Murcia, Región de",
                "ES70": "Canarias"}
SS_SECTORS = ["A", "B-E", "F", "G-I", "J", "K", "M_N", "O-Q", "R-U"]  # real estate (L) excluded: imputed rents
SECTOR_LABELS = {"A": "Agricultura", "B-E": "Industria y energía", "F": "Construcción", "G-I": "Comercio, transporte y hostelería",
                 "J": "Información y comunicaciones", "K": "Finanzas", "M_N": "Servicios profesionales y administrativos",
                 "O-Q": "Administración, educación y sanidad", "R-U": "Ocio y otros servicios", "L": "Inmobiliarias"}


def table_rows(store: Store, dataset: str, code: str) -> list[tuple[str, str, int, float]]:
    """INE table indicator: (geography, series name, year, value)."""
    source_id = "ine_eaes_tempus" if dataset == "INE_28191" else "ine_epa_tempus"
    release_id, _ = store.release(source_id, dataset, code)
    out = []
    for geo, dims, period, value in store.conn.execute(
        """
        SELECT s.geography_code, s.dimensions_json, o.period_label, o.value_decimal
        FROM indicator_observation_versions o JOIN indicator_series_versions s USING (indicator_series_version_id)
        WHERE o.indicator_release_id = ? AND o.revision_state != 'deleted' AND o.value_decimal IS NOT NULL
        """,
        (release_id,),
    ):
        out.append((geo, json.loads(dims)["nombre"], int(period), float(value)))
    return out


def growth_from(rows: dict[int, float], base: int, end: int) -> float | None:
    return (rows[end] / rows[base] - 1) * 100 if base in rows and end in rows else None


def shift_share(Y: dict, H: dict, geo: str, a: int, b: int) -> dict | None:
    secs = [x for x in SS_SECTORS if all(t in Y[x].get(geo, {}) and t in H[x].get(geo, {}) for t in (a, b))]
    if len(secs) < len(SS_SECTORS):
        return None
    ha, hb = sum(H[x][geo][a] for x in secs), sum(H[x][geo][b] for x in secs)
    pa, pb = sum(Y[x][geo][a] for x in secs) / ha, sum(Y[x][geo][b] for x in secs) / hb
    within = sum((Y[x][geo][b] / H[x][geo][b] - Y[x][geo][a] / H[x][geo][a]) * H[x][geo][a] / ha for x in secs)
    shift = sum(Y[x][geo][a] / H[x][geo][a] * (H[x][geo][b] / hb - H[x][geo][a] / ha) for x in secs)
    sectors = [{"sector": x, "label": SECTOR_LABELS[x], "hours_share_from": r(H[x][geo][a] / ha * 100, 1), "hours_share_to": r(H[x][geo][b] / hb * 100, 1),
                "productivity_growth": r((Y[x][geo][b] / H[x][geo][b]) / (Y[x][geo][a] / H[x][geo][a]) * 100 - 100, 1),
                "relative_productivity_from": r((Y[x][geo][a] / H[x][geo][a]) / pa * 100, 0)} for x in secs]
    return {"from": a, "to": b, "total": r((pb / pa - 1) * 100, 1), "within": r(within / pa * 100, 1), "shift": r(shift / pa * 100, 1),
            "interaction": r(((pb - pa) - within - shift) / pa * 100, 1), "sectors": sectors}


def composition_distribution(store: Store, last_year: int, reg_u: dict) -> dict:
    out: dict = {}
    # Base-year sensitivity.
    prod = store.annual("eurostat_sdmx", "nama_10_lp_ulc", "I15.RLPR_HW")
    p_end = min(max(v) for v in prod.values())
    wage = store.annual("ameco_dbnomics", "RWCDC", "RWCDC")
    w_end = min(max(y for y in v if y <= last_year) for k, v in wage.items() if k in PEER_AREAS)
    out["base_year"] = {
        "productivity": {"end": p_end, "rows": [{"base": b, **{EUROSTAT_TO_AREA[g]: r(growth_from(v, b, p_end), 1) for g, v in prod.items() if g in EUROSTAT_TO_AREA}} for b in BASES]},
        "real_wage": {"end": w_end, "rows": [{"base": b, **{a: r(growth_from(wage[a], b, w_end), 1) for a in PEER_AREAS if a in wage}} for b in BASES]},
    }
    # Shift-share of productivity per hour (A10, real estate excluded).
    Y = {x: store.annual("eurostat_sdmx", "nama_10_a10", f"CLV15_MEUR.{x}.B1G") for x in SS_SECTORS}
    H = {x: store.annual("eurostat_sdmx", "nama_10_a10_e", f"THS_HW.{x}.EMP_DC") for x in SS_SECTORS}
    ss_end = min(max(Y["G-I"][g]) for g in ("ES", "EU27_2020"))
    out["shift_share"] = {
        "end": ss_end,
        "periods": {str(a): {EUROSTAT_TO_AREA[g]: shift_share(Y, H, g, a, ss_end) for g in EUROSTAT_TO_AREA} for a in (1995, 2000, 2008)},
    }
    # Unemployment by nationality and the education-mix counterfactual.
    nat = {c: store.annual("eurostat_sdmx", "lfsa_urgan", f"PC.T.Y15-74.{c}") for c in ("NAT", "FOR", "TOTAL")}
    lf = {c: store.annual("eurostat_sdmx", "lfsa_agan", f"THS_PER.T.Y15-74.{c}") for c in ("FOR", "TOTAL")}
    out["nationality"] = {
        "rates": {c: {EUROSTAT_TO_AREA[g]: points(v, 1) for g, v in rows.items() if g in EUROSTAT_TO_AREA} for c, rows in nat.items()},
        "foreign_share": {EUROSTAT_TO_AREA[g]: points({y: v / lf["TOTAL"][g][y] * 100 for y, v in rows.items() if y in lf["TOTAL"].get(g, {})}, 1)
                          for g, rows in lf["FOR"].items() if g in EUROSTAT_TO_AREA},
    }
    rate = {e: store.annual("eurostat_sdmx", "lfsa_urgaed", f"PC.T.Y25-64.{e}") for e in ("ED0-2", "ED3_4", "ED5-8", "TOTAL")}
    lfe = {e: store.annual("eurostat_sdmx", "lfsa_agaed", f"THS_PER.T.Y25-64.{e}") for e in ("ED0-2", "ED3_4", "ED5-8")}
    cf_rows = []
    for y in sorted(set(rate["TOTAL"].get("ES", {})) & set(rate["TOTAL"].get("EU27_2020", {}))):
        try:
            eu_tot = sum(lfe[e]["EU27_2020"][y] for e in lfe)
            mix = sum(rate[e]["ES"][y] * lfe[e]["EU27_2020"][y] / eu_tot for e in lfe)
        except KeyError:
            continue
        cf_rows.append({"year": y, "es": r(rate["TOTAL"]["ES"][y], 1), "eu": r(rate["TOTAL"]["EU27_2020"][y], 1), "es_eu_mix": r(mix, 1)})
    out["education_counterfactual"] = cf_rows
    # Wages: fixed-composition index vs averages, deflated.
    hicp = store.annual("eurostat_sdmx", "prc_hicp_aind", "INX_A_AVG.CP00")["ES"]
    ipt = store.annual("ine_ipt_tempus", "IPT", "IPT239")["ESP"]
    ees: dict[str, dict[int, float]] = defaultdict(dict)
    ees_regions: dict[str, dict[str, dict[int, float]]] = defaultdict(lambda: defaultdict(dict))
    for geo, name, year, value in table_rows(store, "INE_28191", "28191"):
        stat = name.rstrip(".").split(".")[-1].strip()
        if geo == "ESP":
            ees[stat][year] = value
        ees_regions[geo][stat][year] = value
    base = 2008
    def real_index(rows: dict[int, float]) -> dict[int, float]:
        return {y: (v / hicp[y]) / (rows[base] / hicp[base]) * 100 for y, v in rows.items() if y in hicp and base in rows}
    out["wage_composition"] = {
        "base": base,
        "ipt": points(real_index(ipt), 1),
        "mean": points(real_index(ees["Media"]), 1),
        "median": points(real_index(ees["Mediana"]), 1),
        "p10": points(real_index(ees["Percentil 10"]), 1),
        "p90": points(real_index(ees["Percentil 90"]), 1),
        "levels": {stat: points(v, 0) for stat, v in ees.items()},
    }
    # Distribution: EPA monthly wage by decile, real index 2008 = 100.
    dec: dict[str, dict[int, float]] = defaultdict(dict)
    for _geo, name, year, value in table_rows(store, "INE_66237", "66237"):
        dec[name.split(".")[1].strip()][year] = value
    out["deciles"] = {
        "base": base,
        "real_index": {k: points(real_index(v), 1) for k, v in dec.items()},
        "levels": {k: points(v, 1) for k, v in dec.items()},
    }
    lw = store.annual("eurostat_sdmx", "earn_ses_pub1s", "PC.T.GE10")
    out["low_wage_share"] = {EUROSTAT_TO_AREA[g]: points(v, 1) for g, v in lw.items() if g in EUROSTAT_TO_AREA}
    # Territory: productivity and pay per hour by region, crossed with unemployment.
    nl = store.annual("eurostat_sdmx", "nama_10r_2nlp", "NLPR_HW.EUR")
    cw = store.annual("eurostat_sdmx", "nama_10r_2lp10", "TOTAL.D1_SAL_HW.EUR")
    names = dict(store.conn.execute("SELECT DISTINCT geography_code, geography_name FROM indicator_series_versions WHERE geography_level = 'nuts2'").fetchall())
    ty = max(y for y in nl["ES"] if y in nl.get("EU27_2020", {}) and y in cw.get("ES", {}))
    regions = []
    for g in sorted(nl):
        if g.startswith("ES") and len(g) == 4 and g != "ESZZ" and ty in nl[g]:
            eaes = ees_regions.get(NUTS2_TO_INE.get(g, ""), {})
            median = eaes.get("Mediana", {})
            regions.append({"code": g, "name": names.get(g, g), "productivity": r(nl[g][ty], 1), "pay": r(cw.get(g, {}).get(ty), 1),
                            "unemployment": r(reg_u.get(g, {}).get(ty), 1),
                            "median_wage": r(median.get(max(median)), 0) if median else None,
                            "median_wage_year": max(median) if median else None})
    main = [x for x in regions if x["code"] not in ("ES63", "ES64")]
    def disp(prefix: str) -> dict | None:
        regs = {k: v for k, v in nl.items() if k.startswith(prefix) and len(k) == 4 and not k.endswith("ZZ")}
        years = [y for y in range(ty, ty - 4, -1) if sum(y in v for v in regs.values()) > 2]
        if not years:
            return None
        vals = [v[years[0]] for v in regs.values() if years[0] in v]
        return {"year": years[0], "max_over_min": r(max(vals) / min(vals), 2), "regions": len(vals)}
    out["territory"] = {
        "year": ty, "regions": regions,
        "es": {"productivity": r(nl["ES"][ty], 1), "pay": r(cw["ES"][ty], 1)},
        "eu": {"productivity": r(nl["EU27_2020"][ty], 1), "pay": r(cw["EU27_2020"][ty], 1), "unemployment": None},
        "max_over_min_main": r(max(x["productivity"] for x in main) / min(x["productivity"] for x in main), 2),
        "dispersion_peers": {a: disp(p) for p, a in NUTS_COUNTRY.items()},
        "above_eu_productivity": sum(x["productivity"] >= nl["EU27_2020"][ty] for x in regions),
    }
    return out


# ---------------------------------------------------------------- who carries the unemployment: age x education x region

SEGMENTS_FILE = REPO_ROOT / "etl/data/manual/employment/segments_es.json"
SEG_AGES = [("Y15-24", "15 a 24"), ("Y25-34", "25 a 34"), ("Y35-44", "35 a 44"), ("Y45-54", "45 a 54"), ("Y55-64", "55 a 64")]
SEG_LEVELS = [("ED0-2", "Hasta la ESO"), ("ED3_4", "Bachillerato o FP de grado medio"), ("ED5-8", "Estudios superiores")]
UNRELIABLE = {"u", "bu", "du", "bdu"}  # Eurostat: low reliability (sample size); published empty, never imputed


def cells_with_flags(store: Store, source_id: str, dataset: str, code: str) -> dict[str, dict[int, tuple[float, str | None]]]:
    release_id, _ = store.release(source_id, dataset, code)
    out: dict[str, dict[int, tuple[float, str | None]]] = defaultdict(dict)
    for geo, period, value, status in store.conn.execute(
        """
        SELECT s.geography_code, o.period_label, o.value_decimal, o.source_status_code
        FROM indicator_observation_versions o JOIN indicator_series_versions s USING (indicator_series_version_id)
        WHERE o.indicator_release_id = ? AND o.revision_state != 'deleted' AND o.value_decimal IS NOT NULL
        """,
        (release_id,),
    ):
        out[geo][int(period)] = (float(value), status)
    return out


def temporary_by_sector(store: Store) -> dict:
    """INE EPA tables 65978/65979/65980: temporary share of employees by sector and age (both from official counts)."""
    counts: dict[tuple[str, str, int], dict[str, float]] = defaultdict(dict)
    for table, sector in (("65978", "all"), ("65979", "private"), ("65980", "public")):
        for _geo, name, year, value in table_rows(store, f"INE_{table}", table):
            parts = [x.strip() for x in name.rstrip(".").split(".")]
            counts[(sector, parts[3], year)]["temporal" if parts[4].startswith("Temporal") else "total"] = value
    share = {k: 100 * v["temporal"] / v["total"] for k, v in counts.items() if v.get("total") and "temporal" in v}
    years = sorted({y for (_, _, y) in share})
    last = years[-1]
    ages = [a for a in dict.fromkeys(a for (sec, a, y) in share if sec == "all" and y == last) if a != "16 y más años"]
    total_age = "16 y más años"
    return {
        "source_tables": ["65978", "65979", "65980"],
        "last_year": last,
        "series": {sec: points({y: share[(sec, total_age, y)] for y in years if (sec, total_age, y) in share}, 1) for sec in ("all", "private", "public")},
        "by_age_last": [
            {"age": a, **{sec: r(share.get((sec, a, last)), 1) for sec in ("all", "private", "public")},
             "public_employees_k": r(counts.get(("public", a, last), {}).get("total"), 1)}
            for a in ages
        ],
        "public_share_of_temporary": points({y: 100 * counts[("public", total_age, y)]["temporal"] / counts[("all", total_age, y)]["temporal"]
                                             for y in years if counts.get(("public", total_age, y), {}).get("temporal") and counts.get(("all", total_age, y), {}).get("temporal")}, 1),
        "public_share_of_employees": points({y: 100 * counts[("public", total_age, y)]["total"] / counts[("all", total_age, y)]["total"]
                                             for y in years if counts.get(("public", total_age, y), {}).get("total") and counts.get(("all", total_age, y), {}).get("total")}, 1),
        "_share": share,
    }


def segments_by_group(store: Store) -> dict:
    spec = json.loads(SEGMENTS_FILE.read_text(encoding="utf-8"))
    markets = spec["markets"]["groups"]
    region_market = {code: g["id"] for g in markets for code in g["regions"]}
    names = dict(store.conn.execute(
        "SELECT DISTINCT geography_code, geography_name FROM indicator_series_versions WHERE geography_level = 'nuts2' AND geography_code LIKE 'ES__'"
    ).fetchall())
    grid: dict[tuple[str, str], dict[str, dict[int, tuple[float, str | None]]]] = {}
    for lvl in [*(c for c, _ in SEG_LEVELS), "TOTAL"]:
        for age in [*(c for c, _ in SEG_AGES), "Y15-74"]:
            grid[(lvl, age)] = cells_with_flags(store, "eurostat_sdmx", "lfst_r_lfu3rt_es", f"{lvl}.T.{age}.PC")
    year = max(grid[("TOTAL", "Y15-74")]["ES"])
    regions = sorted((g for g in grid[("TOTAL", "Y15-74")] if g.startswith("ES") and len(g) == 4 and year in grid[("TOTAL", "Y15-74")][g]),
                     key=lambda g: -grid[("TOTAL", "Y15-74")][g][year][0])
    missing = [g for g in regions if g not in region_market]
    if missing:
        raise SystemExit(f"segments_es.json: regions without market group: {missing}")

    def cell(lvl: str, age: str, geo: str) -> tuple[float | None, str | None]:
        value, flag = grid[(lvl, age)].get(geo, {}).get(year, (None, None))
        if flag in UNRELIABLE:
            return None, flag
        return (r(value, 1) if value is not None else None), flag

    rows = []
    observed: list[dict] = []
    for lvl, _ in SEG_LEVELS:
        for age, _ in SEG_AGES:
            values, flags = {}, {}
            for geo in regions:
                v, f = cell(lvl, age, geo)
                values[geo] = v
                if f:
                    flags[geo] = f
                if v is not None:
                    observed.append({"geo": geo, "name": names.get(geo, geo), "age": age, "isced": lvl, "value": v})
            rows.append({"isced": lvl, "age": age, "es": cell(lvl, age, "ES")[0], "eu": cell(lvl, age, "EU27_2020")[0],
                         "es_age_total": cell("TOTAL", age, "ES")[0], "values": values, "flags": flags})
    lo = min(observed, key=lambda c: (c["value"], c["geo"]))
    hi = max(observed, key=lambda c: (c["value"], c["geo"]))
    # How much each dimension separates on its own, at national level (same table, same year).
    es_total = cell("TOTAL", "Y15-74", "ES")[0]

    temp = temporary_by_sector(store)
    share = temp.pop("_share")
    ept = store.annual("eurostat_sdmx", "lfsa_eppgai", "PC.F.Y15-64")
    jornada: dict[str, dict[int, float]] = defaultdict(dict)
    for _geo, name, wyear, value in table_rows(store, "INE_66237J", "66237J"):
        jornada[name.split(".")[0].strip()][wyear] = value

    def resolve(fig: dict) -> dict:
        m = fig["metric"]
        if m == "unemployment":
            v, f = cell(fig["isced"], fig["age"], fig["geo"])
            return {**fig, "value": v, "flag": f, "year": year, "unit": "pct", "source": "eurostat:lfst_r_lfu3rt",
                    "geo_name": "España" if fig["geo"] == "ES" else "UE-27" if fig["geo"] == "EU27_2020" else names.get(fig["geo"], fig["geo"])}
        if m == "temporary_share":
            ty = temp["last_year"]
            return {**fig, "value": r(share.get((fig["sector"], fig["age"], ty)), 1), "year": ty, "unit": "pct",
                    "source": f"ine:{ {'all': '65978', 'private': '65979', 'public': '65980'}[fig['sector']] }"}
        if m == "involuntary_part_time":
            rows_ = store.annual("eurostat_sdmx", "lfsa_eppgai", f"PC.{fig['sex']}.Y15-64")[fig["geo"]]
            py = max(rows_)
            return {**fig, "value": r(rows_[py], 1), "year": py, "unit": "pct", "source": "eurostat:lfsa_eppgai"}
        if m == "wage_by_working_time":
            rows_ = jornada[fig["working_time"]]
            wy = max(rows_)
            return {**fig, "value": r(rows_[wy], 0), "year": wy, "unit": "eur_month", "source": "ine:66237"}
        raise SystemExit(f"segments_es.json: unknown metric {m}")

    cases = [{**{k: v for k, v in c.items() if k not in ("figures", "national")},
              "figures": [resolve(f) for f in c["figures"]], "national": [resolve(f) for f in c["national"]]} for c in spec["cases"]]
    for c in cases:
        for f in [*c["figures"], *c["national"]]:
            if f["value"] is None:
                raise SystemExit(f"segments case {c['id']}: no value for {f}")
    yr = store.annual("eurostat_sdmx", "yth_empl_140", "T.Y15-24.PC")
    return {
        "year": year,
        "definitions": "etl/data/manual/employment/segments_es.json",
        "ages": [{"code": c, "label": l} for c, l in SEG_AGES],
        "levels": [{"code": c, "label": l} for c, l in SEG_LEVELS],
        "markets": {"criterion": spec["markets"]["criterion"], "groups": [{"id": g["id"], "label": g["label"]} for g in markets]},
        "regions": [{"code": g, "name": names.get(g, g), "market": region_market[g], "total": cell("TOTAL", "Y15-74", g)[0]} for g in regions],
        "es_total": es_total,
        "eu_total": cell("TOTAL", "Y15-74", "EU27_2020")[0],
        "rows": rows,
        "extremes": {"min": lo, "max": hi, "ratio": r(hi["value"] / lo["value"], 1)},
        "cells_observed": len(observed),
        "cells_unreliable": sum(1 for row in rows for f in row["flags"].values() if f in UNRELIABLE),
        "cells_missing": sum(1 for row in rows for g, v in row["values"].items() if v is None and row["flags"].get(g) not in UNRELIABLE),
        "cases": cases,
        "temporary_by_sector": temp,
        "youth_population_ratio": {EUROSTAT_TO_AREA[g]: points(v, 1) for g, v in yr.items() if g in EUROSTAT_TO_AREA},
        "involuntary_part_time_women": {EUROSTAT_TO_AREA[g]: points(v, 1) for g, v in ept.items() if g in EUROSTAT_TO_AREA},
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
    ext = data
    if ext.get("registered"):
        add("oecd_registered_unemployment", "paro_registrado_miles", {"ESP": ext["registered"]["sepe"]})
        add("ameco_dbnomics", "parados_epa_miles", {"ESP": ext["registered"]["epa"]})
    for ep in (ext.get("cycle") or {}).get("episodes", []):
        for row in ep["rows"]:
            rows.append(("ameco_dbnomics", f"pib_variacion_{ep['from']}_{ep['to']}", row["area"], ep["to"], row["gdp"]))
            rows.append(("ameco_dbnomics", f"empleo_variacion_{ep['from']}_{ep['to']}", row["area"], ep["to"], row["employment"]))
    if ext.get("cycle"):
        add("ameco_dbnomics", "pib_crecimiento_anual", {"ESP": ext["cycle"]["es_growth"]["gdp"]})
        add("ameco_dbnomics", "empleo_crecimiento_anual", {"ESP": ext["cycle"]["es_growth"]["employment"]})
    for a in ext.get("contract_adjustment", []):
        rows.append(("ine_epa_tempus", f"variacion_temporales_miles_{a['from']}_{a['to']}", "ESP", a["to"], a["temporal"]))
        rows.append(("ine_epa_tempus", f"variacion_indefinidos_miles_{a['from']}_{a['to']}", "ESP", a["to"], a["indefinido"]))
    if ext.get("construction_share"):
        add("eurostat_sdmx:nama_10_a10_e", "construccion_pct_empleo", ext["construction_share"])
    if ext.get("long_term"):
        add("eurostat_sdmx:une_ltu_a", "paro_larga_duracion_pct_activos", ext["long_term"]["rate"])
        add("eurostat_sdmx:une_ltu_a_h", "paro_larga_duracion_pct_activos", ext["long_term"]["rate_h"])
        add("eurostat_sdmx:une_ltu_a", "paro_larga_duracion_pct_parados", ext["long_term"]["share"])
    if ext.get("education"):
        for lvl, by_area in ext["education"]["rate"].items():
            add("eurostat_sdmx:lfsa_urgaed", f"tasa_paro_25_64_{lvl}", by_area)
        for lvl, by_area in ext["education"]["population"].items():
            add("eurostat_sdmx:edat_lfse_03", f"poblacion_25_64_pct_{lvl}", by_area)
    if ext.get("firm_size"):
        for area, shares in ext["firm_size"]["shares"].items():
            rows.extend(("eurostat_sdmx:sbs_sc_ovw", f"empleo_pct_empresas_{cls}", area, ext["firm_size"]["year"], v) for cls, v in shares.items())
    if ext.get("minimum_wage"):
        add("oecd_earnings", "salario_minimo_pct_mediano", ext["minimum_wage"])
    for area, pair in (ext.get("wages_productivity") or {}).items():
        rows.extend(("ameco_dbnomics", "remuneracion_real_asalariado_1995_100", area, p["year"], p["value"]) for p in pair["wage"])
        rows.extend(("ameco_dbnomics", "pib_por_ocupado_1995_100", area, p["year"], p["value"]) for p in pair["productivity"])
    if ext.get("regions"):
        rg = ext["regions"]
        rows.extend(("eurostat_sdmx:lfst_r_lfu3rt", "tasa_paro_region", f"{r['code']} {r['name']}", rg["year"], r["unemployment"]) for r in rg["spain"])
        rows.extend(("eurostat_sdmx:lfst_r_lfe2emprt", "tasa_empleo_20_64_region", f"{r['code']} {r['name']}", rg["year"], r["employment"]) for r in rg["spain"])
        add("eurostat_sdmx:lfst_r_lmdur", "dispersion_paro_regional", rg["dispersion"])
    cap = ext.get("capacity")
    if cap:
        for key, segs in cap["real_eur"].items():
            for seg in segs:
                rows.extend(("eurostat_sdmx:earn_nt_net", f"{key}_eur_constantes_{cap['real_base_year']}", "ES", p["year"], p["value"]) for p in seg)
        for key, by_area in cap["pps_net"].items():
            add("eurostat_sdmx:earn_nt_net", f"{key}_neto_pps", by_area)
        rows.extend(("eurostat_sdmx:earn_mw_cur", f"salario_minimo_pps_{cap['min_wage_pps']['period']}", g, cap["min_wage_pps"]["period"][:4], v)
                    for g, v in cap["min_wage_pps"]["values"].items())
        add("oecd_taxben", "salario_minimo_neto_pct_neto_mediano", cap["min_wage_net_vs_median"])
        add("eurostat_sdmx:ilc_iw01", "pobreza_laboral_pct_ocupados", cap["in_work_poverty"])
    comp = ext.get("composition")
    if comp:
        for row in comp["base_year"]["productivity"]["rows"]:
            rows.extend(("eurostat_sdmx:nama_10_lp_ulc", f"productividad_hora_crecimiento_desde_{row['base']}_hasta_{comp['base_year']['productivity']['end']}", a, row["base"], v)
                        for a, v in row.items() if a != "base")
        for a_from, by_area in comp["shift_share"]["periods"].items():
            for area, res in by_area.items():
                if res:
                    for part in ("total", "within", "shift", "interaction"):
                        rows.append(("eurostat_sdmx:nama_10_a10", f"productividad_hora_{part}_{a_from}_{res['to']}", area, res["to"], res[part]))
        for c_, by_area in comp["nationality"]["rates"].items():
            add("eurostat_sdmx:lfsa_urgan", f"tasa_paro_{c_.lower()}", by_area)
        add("eurostat_sdmx:lfsa_agan", "extranjeros_pct_poblacion_activa", comp["nationality"]["foreign_share"])
        for row in comp["education_counterfactual"]:
            rows.append(("eurostat_sdmx:lfsa_urgaed+lfsa_agaed", "tasa_paro_25_64_espana_con_composicion_educativa_ue", "ES", row["year"], row["es_eu_mix"]))
        for key in ("ipt", "mean", "median", "p10", "p90"):
            add("ine", f"salario_real_{key}_2008_100", {"ESP": comp["wage_composition"][key]})
        for k, pts in comp["deciles"]["real_index"].items():
            add("ine_epa_tempus:66237", f"salario_real_decil_{k}_2008_100", {"ESP": pts})
        add("eurostat_sdmx:earn_ses_pub1s", "asalariados_salario_bajo_pct", comp["low_wage_share"])
        ty = comp["territory"]["year"]
        for reg in comp["territory"]["regions"]:
            rows.append(("eurostat_sdmx:nama_10r_2nlp", "productividad_nominal_hora_eur", f"{reg['code']} {reg['name']}", ty, reg["productivity"]))
            rows.append(("eurostat_sdmx:nama_10r_2lp10", "remuneracion_hora_eur", f"{reg['code']} {reg['name']}", ty, reg["pay"]))
    lp = ext.get("labour_policy")
    if lp:
        for key, by_area in lp["series"].items():
            add("dg_empl_lmp:lmp_ind_exp", f"gasto_lmp_{key}", by_area)
        add("dg_empl_lmp:lmp_ind_actru", "activacion_parados_registrados", lp["activation"])
    nar = ext.get("narratives")
    if nar:
        for row in nar["structural_gap"]["rows"]:
            rows.append(("ameco_dbnomics", "brecha_paro_espana_menos_ue15_puntos", "ESP", row["year"], row["gap"]))
            rows.append(("ameco_dbnomics", "brecha_estructural_nawru_puntos", "ESP", row["year"], row["structural"]))
            rows.append(("ameco_dbnomics", "brecha_ciclica_puntos", "ESP", row["year"], row["cyclical"]))
        for q in nar["reform"]["quarters"]:
            rows.append(("ine_epa_tempus", "asalariados_indefinidos_ordinarios_miles", "ESP", q["quarter"], q["ordinary"]))
            rows.append(("ine_epa_tempus", "asalariados_fijos_discontinuos_miles", "ESP", q["quarter"], q["fd"]))
            rows.append(("ine_epa_tempus", "asalariados_temporales_miles", "ESP", q["quarter"], q["temporal"]))
    it = ext.get("intermittency")
    if it:
        rows.extend(("seg_social_pxweb", "afiliados_fijos_discontinuos_mensual", "ESP", m["month"], m["fd"]) for m in it["monthly_affiliates"])
        add("seg_social_pxweb", "afiliados_fijos_discontinuos_media_anual", {"ESP": it["annual_affiliates"]})
        add("seg_social_pxweb", "dias_cotizados_por_cotizante_fijo_discontinuo", {"ESP": it["days_per_contributor"]["fd"]})
        add("seg_social_pxweb", "dias_cotizados_por_cotizante_indefinido_ordinario", {"ESP": it["days_per_contributor"]["indefinido"]})
        add("mites_anuario", "demandantes_fijos_discontinuos_media_anual", {"ESP": it["inactive_job_seekers"]})
        add("mites_anuario", "contratos_fijos_discontinuos", {"ESP": it["contracts_fd"]})
        add("mites_anuario", "contratos_total", {"ESP": it["contracts_total"]})
    seg = ext.get("segments")
    if seg:
        reg_names = {reg["code"]: reg["name"] for reg in seg["regions"]}
        for row in seg["rows"]:
            serie = f"tasa_paro_{row['age'].lower().replace('y', '')}_{row['isced']}"
            rows.append(("eurostat_sdmx:lfst_r_lfu3rt", serie, "ES", seg["year"], row["es"]))
            rows.append(("eurostat_sdmx:lfst_r_lfu3rt", serie, "EU27", seg["year"], row["eu"]))
            # unreliable (u) or missing cells are written empty, never imputed
            rows.extend(("eurostat_sdmx:lfst_r_lfu3rt", serie, f"{g} {reg_names[g]}", seg["year"], "" if v is None else v)
                        for g, v in row["values"].items())
        ts = seg["temporary_by_sector"]
        for sec, label in (("all", "todos"), ("private", "sector_privado"), ("public", "sector_publico")):
            add(f"ine_epa_tempus:{ {'all': '65978', 'private': '65979', 'public': '65980'}[sec] }", f"temporales_pct_asalariados_{label}", {"ESP": ts["series"][sec]})
            rows.extend((f"ine_epa_tempus:{ {'all': '65978', 'private': '65979', 'public': '65980'}[sec] }", f"temporales_pct_asalariados_{label}_{a['age']}", "ESP", ts["last_year"], a[sec])
                        for a in ts["by_age_last"])
        add("ine_epa_tempus:65978+65980", "sector_publico_pct_temporales", {"ESP": ts["public_share_of_temporary"]})
        add("eurostat_sdmx:yth_empl_140", "parados_15_24_pct_poblacion", seg["youth_population_ratio"])
        add("eurostat_sdmx:lfsa_eppgai", "parcial_involuntaria_mujeres_pct", seg["involuntary_part_time_women"])
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
