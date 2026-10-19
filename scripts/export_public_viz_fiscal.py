#!/usr/bin/env python3
"""Export /visualizaciones/carga-fiscal/ data from the public-finance DB (scripts/ingest_public_finance_es.py).

Reads only normalized tables: the latest release of each indicator (indicator_* contract), statutory rates (same
contract, interval_kind='legal_validity') and BOE complexity (legal_norms, legal_norm_lineage_edges,
legal_norm_text_metrics). Writes the page JSON (with per-source provenance: URL, retrieval date, sha256) and a long CSV.
When the DB is missing (CI checkouts) the committed artifact is kept.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import math
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "etl/data/staging/public-finance-es.db"
OUT_JSON = REPO_ROOT / "ui/site/public/visualizaciones/data/carga-fiscal.json"
OUT_CSV = REPO_ROOT / "ui/site/public/visualizaciones/data/carga-fiscal.csv"

FIRST_YEAR = 1925
OECD_AREAS = ["ESP", "OECD_REP", "DEU", "FRA", "ITA", "PRT"]
COMPOSITION = {
    "T_1100": "IRPF y otros impuestos sobre la renta de personas",
    "T_1200": "Impuesto sobre Sociedades",
    "T_2100": "Cotizaciones sociales a cargo del trabajador",
    "T_2200": "Cotizaciones sociales a cargo de la empresa",
    "T_2300": "Cotizaciones de autónomos y no empleados",
    "T_4000": "Impuestos sobre la propiedad",
    "T_5000": "Impuestos sobre bienes y servicios (IVA, especiales…)",
}
SOURCE_PAGES = {
    "imf_fpp": ("FMI · Public Finances in Modern History (Mauro, Romeu, Binder y Zaman, 2015)", "https://www.imf.org/external/datamapper/datasets/FPP"),
    "oecd_revenue_statistics": ("OCDE · Revenue Statistics, tablas comparativas (réplica DBnomics)", "https://db.nomics.world/OECD/DSD_REV_COMP_OECD@DF_RSOECD"),
    "eurostat_sdmx": ("Eurostat · contabilidad nacional: gov_10a_taxag, gov_10a_main, gov_10a_exp (COFOG), nama_10_pc, tec00113, nasa_10_ki", "https://ec.europa.eu/eurostat/databrowser/view/gov_10a_exp/default/table"),
    "oecd_income_distribution": ("OCDE · Income Distribution Database (réplica DBnomics)", "https://db.nomics.world/OECD/DSD_WISE_IDD@DF_IDD"),
    "oecd_taxing_wages": ("OCDE · Taxing Wages (réplica DBnomics)", "https://db.nomics.world/OECD/DSD_TAX_WAGES_COMP@DF_TW_COMP"),
    "oecd_tax_database": ("OCDE · Tax Database, tipo máximo del IRPF (réplica DBnomics)", "https://db.nomics.world/OECD/DSD_TAX_PIT@DF_PIT_TOP_EARN_THRESH"),
    "hacienda_ccaa": ("Ministerio de Hacienda · Tributación autonómica 2025, liquidación del sistema de financiación y presupuestos liquidados de las CCAA 2024; INE, Contabilidad Regional", "https://www.hacienda.gob.es/es-ES/Areas%20Tematicas/Financiacion%20Autonomica/Paginas/Financiacion%20Autonomica.aspx"),
    "aeat_irpf_stats": ("AEAT · Estadística de los declarantes del IRPF", "https://sede.agenciatributaria.gob.es/AEAT/Contenidos_Comunes/La_Agencia_Tributaria/Estadisticas/Publicaciones/sites/irpf/2023/home.html"),
    "worldbank_wdi": ("Banco Mundial · población (SP.POP.TOTL) e IPC (FP.CPI.TOTL)", "https://data.worldbank.org/indicator/FP.CPI.TOTL?locations=ES"),
    "vclc_tax_law_rates": ("Tipos legales: una norma o fuente citada por cambio", "https://www.boe.es/"),
    "boe_api_legal": ("BOE · API de legislación consolidada", "https://www.boe.es/datosabiertos/api/api.php"),
}


EU_AREAS = ["ES", "DE", "FR", "IT", "PT", "EU27_2020"]
EU_TO_OECD = {"ES": "ESP", "DE": "DEU", "FR": "FRA", "IT": "ITA", "PT": "PRT"}
SQUEEZE_BASE = 2000  # default base: mid-cycle, before the housing bubble's revenue peak (2007)
SQUEEZE_BASES = [2000, 2007, 2008, 2013, 2019]  # every base is published so the choice is visible
SPENDING_WINDOWS = [1995, 2000, 2007, 2013, 2019]
PENSION_WINDOWS = [2007, 2013, 2019]  # ESSPROS pension beneficiaries start in 2006
# Spending by function (COFOG). Pensions = old age + survivors; interest = public debt transactions (GF0107).
FUNCTIONS = [
    ("pensions", "Pensiones (vejez y supervivencia)", ["GF1002", "GF1003"]),
    ("social", "Resto de protección social (desempleo, incapacidad, familia, vivienda social, exclusión)", ["GF10", "-GF1002", "-GF1003"]),
    ("health", "Sanidad", ["GF07"]),
    ("education", "Educación", ["GF09"]),
    ("interest", "Intereses de la deuda", ["GF0107"]),
    ("rest", "Resto (economía, administración, defensa, seguridad, medio ambiente, cultura…)",
     ["TOTAL", "-GF10", "-GF07", "-GF09", "-GF0107"]),
]
SIBLINGS = {
    "sanidad": ("/visualizaciones/sanidad/", "Visualizaciones · Sanidad"),
    "educacion": ("/visualizaciones/educacion/", "Visualizaciones · Educación"),
    "vivienda": ("/visualizaciones/vivienda/", "Visualizaciones · Vivienda"),
}
SIBLING_DIR = REPO_ROOT / "ui/site/public/visualizaciones/data"


def r(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(float(value), digits)


class Store:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.provenance: dict[str, list[dict]] = defaultdict(list)

    def series(self, source_id: str, indicator_code: str, unit_code: str, dataset_code: str | None = None) -> dict[str, list[dict]]:
        """Latest release of an indicator as {geography_code: [observation]}; deleted rows are dropped."""
        row = self.conn.execute(
            """
            SELECT r.indicator_release_id, r.source_url, r.source_content_sha256, r.source_snapshot_date,
                   r.source_metadata_json
            FROM indicator_definitions d JOIN indicator_releases r USING (indicator_id)
            WHERE d.source_id = ? AND d.indicator_code = ? AND d.unit_code = ? AND (? IS NULL OR d.dataset_code = ?)
            ORDER BY r.source_snapshot_date DESC, r.created_at DESC LIMIT 1
            """,
            (source_id, indicator_code, unit_code, dataset_code, dataset_code),
        ).fetchone()
        if row is None:
            raise LookupError(f"indicator {source_id}:{indicator_code}:{unit_code} not loaded")
        release_id, url, sha, snapshot, meta = row
        self.provenance[source_id].append({
            "indicator": f"{dataset_code + ' ' if dataset_code else ''}{indicator_code} ({unit_code})", "url": url, "sha256": sha,
            "snapshot_date": snapshot, "retrieved_at": json.loads(meta or "{}").get("retrieved_at"),
        })
        out: dict[str, list[dict]] = defaultdict(list)
        for geo, period, value in self.conn.execute(
            """
            SELECT s.geography_code, o.period_label, o.value_decimal
            FROM indicator_observation_versions o JOIN indicator_series_versions s USING (indicator_series_version_id)
            WHERE o.indicator_release_id = ? AND o.revision_state != 'deleted' AND o.value_decimal IS NOT NULL
            ORDER BY s.geography_code, o.period_start
            """,
            (release_id,),
        ):
            out[geo].append({"period": period, "value": float(value)})
        return out

    def annual(self, source_id: str, indicator_code: str, unit_code: str, geo: str) -> dict[int, float]:
        return {int(p["period"]): p["value"] for p in self.series(source_id, indicator_code, unit_code).get(geo, [])}


def points(mapping: dict[int, float], digits: int = 2, since: int | None = None) -> list[dict]:
    return [{"year": y, "value": r(v, digits)} for y, v in sorted(mapping.items()) if since is None or y >= since]


def statutory_rates(conn: sqlite3.Connection) -> dict | None:
    rows = conn.execute(
        """
        SELECT d.indicator_code, o.period_start, o.value_decimal, o.raw_value_json, e.source_url
        FROM indicator_definitions d
        JOIN indicator_releases r ON r.indicator_id = d.indicator_id
        JOIN indicator_observation_versions o ON o.indicator_release_id = r.indicator_release_id
        JOIN indicator_observation_evidence e USING (indicator_observation_version_id)
        WHERE d.source_id = 'vclc_tax_law_rates' AND o.revision_state != 'deleted'
          AND r.indicator_release_id = (
            SELECT r2.indicator_release_id FROM indicator_releases r2 WHERE r2.indicator_id = d.indicator_id
            ORDER BY r2.source_snapshot_date DESC, r2.created_at DESC LIMIT 1)
        ORDER BY d.indicator_code, o.period_start
        """
    ).fetchall()
    if not rows:
        return None
    series: dict[str, list[dict]] = defaultdict(list)
    for code, start, value, raw, url in rows:
        cited = json.loads(raw)
        series[code].append({
            "from_year": int(start[:4]), "value_pct": float(value), "label": cited.get("label"),
            "source": cited.get("source"), "source_url": url, "locator": cited.get("locator"),
            "confidence": cited.get("confidence"), "note": cited.get("note"),
        })
    return {"series": dict(series)}


def complexity(conn: sqlite3.Connection) -> dict | None:
    laws = conn.execute(
        """
        SELECT n.norm_id, n.boe_id, n.title, n.effective_date, n.topic_hint
        FROM legal_norms n
        WHERE EXISTS (SELECT 1 FROM legal_norm_lineage_edges e WHERE e.related_norm_id = n.norm_id)
        ORDER BY n.boe_id
        """
    ).fetchall()
    if not laws:
        return None
    amendments = []
    for norm_id, boe_id, title, enacted, topic in laws:
        by_year: dict[str, int] = defaultdict(int)
        # One amending norm counts once per law, in the year it was published.
        for (year,) in conn.execute(
            """
            SELECT substr(MIN(evidence_date), 1, 4) FROM legal_norm_lineage_edges
            WHERE related_norm_id = ? GROUP BY norm_id
            """,
            (norm_id,),
        ):
            by_year[year] += 1
        amendments.append({
            "law": title, "boe_id": boe_id, "topic": topic, "enacted": enacted,
            "url": f"https://www.boe.es/buscar/act.php?id={boe_id}",
            "by_year": dict(sorted(by_year.items())), "total": sum(by_year.values()),
        })
    lengths, structure = [], []
    for boe_id, title, topic, kind, version_date, words, words_ex, arts, adic, trans, finals in conn.execute(
        """
        SELECT n.boe_id, n.title, n.topic_hint, m.version_kind, m.version_date, m.words, m.words_excl_preamble,
               m.articles, m.disp_adicionales, m.disp_transitorias, m.disp_finales
        FROM legal_norm_text_metrics m JOIN legal_norms n USING (norm_id)
        ORDER BY n.topic_hint, m.version_date
        """
    ):
        short = title.split(",")[0]
        lengths.append({
            "tax": (topic or "").removeprefix("tributario:"), "law": short, "boe_id": boe_id,
            "year": int(version_date[:4]),
            "version": "original" if kind == "original" else f"consolidated-{version_date}",
            "words": words, "words_excl_preamble": words_ex, "articles": arts,
        })
        if kind == "consolidated":
            structure.append({
                "law": short, "boe_id": boe_id, "url": f"https://www.boe.es/buscar/act.php?id={boe_id}",
                "words_excl_preamble": words_ex,
                "counts": {"articulos": arts, "disp_adicionales": adic, "disp_transitorias": trans, "disp_finales": finals},
            })
    return {"amendments": amendments, "law_length": lengths, "structure": structure}


def squeeze(store: Store) -> dict:
    """Line 1: what a person pays in taxes vs the household income left, per person, in PPS; and the real change."""
    tax = {g: {int(p["period"]): p["value"] for p in rows} for g, rows in store.series("eurostat_sdmx", "D2_D5_D91_D61_M_D995.S13_S212", "PC_GDP").items()}
    gdp = {g: {int(p["period"]): p["value"] for p in rows} for g, rows in store.series("eurostat_sdmx", "B1GQ", "PPS_HAB").items()}
    inc = {g: {int(p["period"]): p["value"] for p in rows} for g, rows in store.series("eurostat_sdmx", "PAID.B7G.S14_S15", "PPS_HAB").items()}
    eur_gdp = {g: {int(p["period"]): p["value"] for p in rows} for g, rows in store.series("eurostat_sdmx", "B1GQ", "CP_EUR_HAB").items()}
    hicp = {g: {int(p["period"]): p["value"] for p in rows} for g, rows in store.series("eurostat_sdmx", "CP00", "INX_A_AVG").items()}
    real_inc = {g: {int(p["period"]): p["value"] for p in rows} for g, rows in store.series("eurostat_sdmx", "B7G_R_HAB_2010.S14_S15", "IDX2010").items()}
    pop = {g: {int(p["period"]): p["value"] for p in rows} for g, rows in store.series("eurostat_sdmx", "POP_NC", "THS_PER").items()}
    emp = {g: {int(p["period"]): p["value"] for p in rows} for g, rows in store.series("eurostat_sdmx", "EMP_DC", "THS_PER").items()}
    year = max(set.intersection(*(set(tax[g]) & set(gdp[g]) & set(inc[g]) for g in EU_AREAS)))
    idx_last = max(set.intersection(*(set(tax[g]) & set(eur_gdp[g]) & set(hicp[g]) & set(real_inc[g]) & set(emp[g]) for g in EU_AREAS)))
    start = min(SQUEEZE_BASES)
    eu_ratio = tax["EU27_2020"][year] / gdp["EU27_2020"][year]
    areas = []
    for g in EU_AREAS:
        tax_pps = tax[g][year] / 100 * gdp[g][year]
        span = [y for y in range(start, idx_last + 1) if all(y in d[g] for d in (tax, eur_gdp, hicp, real_inc, pop, emp))]
        # Real taxes per person = tax share x GDP per person in euros / consumer prices (HICP); real income uses the
        # household consumption deflator. Both are consumer-price deflators, so the two indices are comparable.
        real_tax = {y: tax[g][y] / 100 * eur_gdp[g][y] / hicp[g][y] for y in span}
        # Per employed person: removes the part that comes from more people working (employment rate, migration).
        real_tax_worker = {y: real_tax[y] * pop[g][y] / emp[g][y] for y in span}
        index = lambda series, base: {y: v / series[base] * 100 for y, v in series.items()}  # noqa: E731
        income = {y: real_inc[g][y] for y in span}
        change = lambda series, base: r((series[idx_last] / series[base] - 1) * 100, 1)  # noqa: E731
        by_base = {
            str(b): {
                "tax": change(real_tax, b), "tax_worker": change(real_tax_worker, b), "income": change(income, b),
                "employment_rate": [r(emp[g][b] / pop[g][b] * 100, 1), r(emp[g][idx_last] / pop[g][idx_last] * 100, 1)],
                "population_change": r((pop[g][idx_last] / pop[g][b] - 1) * 100, 1),
            }
            for b in SQUEEZE_BASES if b in real_tax
        }
        areas.append({
            "area": g, "tax_pct_gdp": r(tax[g][year], 1), "gdp_pps": r(gdp[g][year], 0), "tax_pps": r(tax_pps, 0),
            "income_pps": r(inc[g][year], 0), "tax_to_income_pct": r(tax_pps / inc[g][year] * 100, 1),
            # Frank "esfuerzo fiscal": tax burden divided by GDP per person, EU-27 = 100.
            "effort_index": r(tax[g][year] / gdp[g][year] / eu_ratio * 100, 1),
            "real_tax_change_pct": by_base[str(SQUEEZE_BASE)]["tax"], "real_income_change_pct": by_base[str(SQUEEZE_BASE)]["income"],
            "real_tax_worker_change_pct": by_base[str(SQUEEZE_BASE)]["tax_worker"],
            "by_base": by_base,
            "real_tax_index": points(index(real_tax, start), 1), "real_tax_worker_index": points(index(real_tax_worker, start), 1),
            "real_income_index": points(index(income, start), 1),
        })
    # Cross-check for Spain with a different deflator: OECD revenue in euros / population / CPI.
    oecd_eur = store.annual("oecd_revenue_statistics", "TAX_REV.S13._T", "XDC", "ESP")
    wb_pop = store.annual("worldbank_wdi", "SP.POP.TOTL", "PERSONS", "ESP")
    cpi = store.annual("worldbank_wdi", "FP.CPI.TOTL", "IDX2010", "ESP")
    cpi_last = max(y for y in oecd_eur if y in wb_pop and y in cpi)
    cpi_real = lambda y: oecd_eur[y] * 1e9 / wb_pop[y] / cpi[y]  # noqa: E731
    survey = household_survey(store, year)
    return {
        "year": year, "base_year": SQUEEZE_BASE, "bases": SQUEEZE_BASES, "index_first_year": start, "index_last_year": idx_last,
        "areas": areas, "survey": survey,
        "spain_cpi_check": {"from": SQUEEZE_BASE, "to": cpi_last, "real_tax_change_pct": r((cpi_real(cpi_last) / cpi_real(SQUEEZE_BASE) - 1) * 100, 1)},
    }


# EU-SILC: what the typical household has and what housing takes from it.
SURVEY = [
    ("median_income_pps", "ilc_di03", "TOTAL.T.MED_EI", "PPS"),
    ("mean_income_pps", "ilc_di03", "TOTAL.T.MEAN_EI", "PPS"),
    ("housing_cost_share", "ilc_mded01", "TOTAL.TOTAL", "PC"),
    ("housing_cost_share_poor", "ilc_mded01", "TOTAL.B_60", "PC"),
    ("overburden", "ilc_lvho07c", "TOTAL", "PC"),
    ("overburden_renters", "ilc_lvho07c", "RENT_MKT", "PC"),
    ("overburden_mortgage", "ilc_lvho07c", "OWN_L", "PC"),
]


def household_survey(store: Store, income_year: int) -> dict:
    """Latest EU-SILC wave every area reports, preferring the wave whose income year matches the tax year."""
    data = {
        key: {g: {int(p["period"]): p["value"] for p in rows} for g, rows in store.series("eurostat_sdmx", code, unit, dataset).items()}
        for key, dataset, code, unit in SURVEY
    }
    common = set.intersection(*(set(series.get(g, {})) for series in data.values() for g in EU_AREAS))
    # EU-SILC income refers to the year before the survey (all six areas here).
    wave = income_year + 1 if income_year + 1 in common else max(common)
    return {
        "survey_year": wave, "income_year": wave - 1,
        "areas": [{"area": g, **{key: r(data[key][g][wave], 1) for key in data}} for g in EU_AREAS],
    }


def spending(store: Store) -> dict:
    """Line 2: where the money goes (COFOG by function, % of GDP and real euros per person) and the long run."""
    cofog = {}
    for code in ["TOTAL", "GF0107", "GF07", "GF09", "GF10", "GF1002", "GF1003"]:
        cofog[code] = {g: {int(p["period"]): p["value"] for p in rows} for g, rows in store.series("eurostat_sdmx", f"{code}.TE.S13", "PC_GDP").items()}
    main = {}
    for code in ["TR", "TE", "D41PAY", "D1PAY", "B9"]:
        main[code] = {g: {int(p["period"]): p["value"] for p in rows} for g, rows in store.series("eurostat_sdmx", f"{code}.S13", "PC_GDP").items()}
    real_gdp = {g: {int(p["period"]): p["value"] for p in rows} for g, rows in store.series("eurostat_sdmx", "B1GQ", "CLV10_EUR_HAB").items()}

    def parts(g: str, y: int) -> dict | None:
        out = {}
        for key, _label, codes in FUNCTIONS:
            total = 0.0
            for code in codes:
                sign, code = (-1, code[1:]) if code.startswith("-") else (1, code)
                value = cofog[code].get(g, {}).get(y)
                if value is None:
                    return None
                total += sign * value
            out[key] = total
        return out

    year = max(set.intersection(*(set(cofog["TOTAL"].get(g, {})) & set(main["TR"].get(g, {})) for g in EU_AREAS)))
    areas = []
    for g in EU_AREAS:
        first = min(y for y in cofog["TOTAL"][g])
        base_parts_year = min((y for y in sorted(cofog["TOTAL"][g]) if parts(g, y)), default=None)
        now = parts(g, year)
        base = parts(g, base_parts_year) if base_parts_year else None
        areas.append({
            "area": g, "total": r(cofog["TOTAL"][g][year], 1), "base_year": first, "base_total": r(cofog["TOTAL"][g][first], 1),
            "revenue": r(main["TR"][g][year], 1), "balance": r(main["B9"][g].get(year), 1),
            "pay": r(main["D1PAY"][g].get(year), 1),
            **{k: r(v, 1) for k, v in now.items()},
            "parts_base_year": base_parts_year,
            "parts_change": {k: r(now[k] - base[k], 1) for k in now} if base else None,
        })
    # Spain: decomposition of the change by function, in % of GDP and in real euros per person (2010 prices).
    es_parts = {y: parts("ES", y) for y in sorted(cofog["TOTAL"]["ES"]) if parts("ES", y)}
    windows = []
    for start in [y for y in SPENDING_WINDOWS if y in es_parts]:
        p0, p1 = es_parts[start], es_parts[year]
        g0, g1 = real_gdp["ES"][start], real_gdp["ES"][year]
        tr0, tr1 = main["TR"]["ES"][start], main["TR"]["ES"][year]
        te0, te1 = cofog["TOTAL"]["ES"][start], cofog["TOTAL"]["ES"][year]
        windows.append({
            "from": start, "to": year,
            "revenue_pct": [r(tr0, 1), r(tr1, 1)], "spending_pct": [r(te0, 1), r(te1, 1)],
            "balance_pct": [r(main["B9"]["ES"][start], 1), r(main["B9"]["ES"][year], 1)],
            "revenue_eur": [r(tr0 / 100 * g0, 0), r(tr1 / 100 * g1, 0)], "spending_eur": [r(te0 / 100 * g0, 0), r(te1 / 100 * g1, 0)],
            "real_gdp_pp": [r(g0, 0), r(g1, 0)],
            "functions": [
                {"key": k, "pct": [r(p0[k], 1), r(p1[k], 1)], "eur": [r(p0[k] / 100 * g0, 0), r(p1[k] / 100 * g1, 0)]}
                for k, _label, _codes in FUNCTIONS
            ],
        })
    # Pensions: % of GDP = (pensioners / population) x (spending per pensioner / GDP per person). The log split says how
    # much of the change comes from more pensioners and how much from more per pensioner relative to income.
    ben = {g: {int(p["period"]): p["value"] for p in rows} for g, rows in store.series("eurostat_sdmx", "T.OLD_SRV.TOTAL.TOTAL", "PER").items()}
    pop = {g: {int(p["period"]): p["value"] * 1000 for p in rows} for g, rows in store.series("eurostat_sdmx", "POP_NC", "THS_PER").items()}
    eur_gdp = {g: {int(p["period"]): p["value"] for p in rows} for g, rows in store.series("eurostat_sdmx", "B1GQ", "CP_EUR_HAB").items()}
    hicp = {g: {int(p["period"]): p["value"] for p in rows} for g, rows in store.series("eurostat_sdmx", "CP00", "INX_A_AVG").items()}
    pens_eur = defaultdict(dict)
    for code in ("GF1002", "GF1003"):
        for g, rows in store.series("eurostat_sdmx", f"{code}.TE.S13", "MIO_EUR", "gov_10a_exp").items():
            for p in rows:
                pens_eur[g][int(p["period"])] = pens_eur[g].get(int(p["period"]), 0.0) + p["value"]
    pens_last = max(set.intersection(*(set(ben.get(g, {})) & set(cofog["GF1002"].get(g, {})) & set(pens_eur.get(g, {})) for g in EU_AREAS)))
    pension_rows = []
    for g in EU_AREAS:
        pens = lambda y: cofog["GF1002"][g][y] + cofog["GF1003"][g][y]  # noqa: E731
        share = lambda y: ben[g][y] / pop[g][y]  # noqa: E731
        # Euros per pensioner straight from spending in euros (same table and year as the housing page's persona 4).
        per_ben = lambda y: pens_eur[g][y] * 1e6 / ben[g][y]  # noqa: E731
        windows_g = {}
        for b in PENSION_WINDOWS:
            if not all(b in d.get(g, {}) for d in (ben, cofog["GF1002"], cofog["GF1003"], pop, eur_gdp, hicp, pens_eur)):
                continue
            delta = pens(pens_last) - pens(b)
            total_log = math.log(pens(pens_last) / pens(b))
            demo_log = math.log(share(pens_last) / share(b))
            windows_g[str(b)] = {
                "pensions_pct": [r(pens(b), 1), r(pens(pens_last), 1)], "change_pts": r(delta, 2),
                "from_more_pensioners_pts": r(delta * demo_log / total_log, 2) if total_log else None,
                "from_more_per_pensioner_pts": r(delta * (1 - demo_log / total_log), 2) if total_log else None,
                "pensioners_per_100": [r(share(b) * 100, 1), r(share(pens_last) * 100, 1)],
                "real_per_pensioner_change_pct": r((per_ben(pens_last) / hicp[g][pens_last]) / (per_ben(b) / hicp[g][b]) * 100 - 100, 1),
                "real_gdp_pp_change_pct": r((eur_gdp[g][pens_last] / hicp[g][pens_last]) / (eur_gdp[g][b] / hicp[g][b]) * 100 - 100, 1),
            }
        pension_rows.append({"area": g, "per_pensioner_eur": r(per_ben(pens_last), 0), "windows": windows_g})
    imf = {code: store.annual("imf_fpp", code, "PT_GDP", "ESP") for code in ("rev", "exp", "ie", "d")}
    return {
        "year": year, "functions": [{"key": k, "label": label, "cofog": codes} for k, label, codes in FUNCTIONS],
        "areas": areas, "spain_windows": windows,
        "pension_composition": {"year": pens_last, "windows": PENSION_WINDOWS, "areas": pension_rows},
        "spain_series": {
            "revenue_pct_gdp": points(main["TR"]["ES"], 1), "spending_pct_gdp": points(main["TE"]["ES"], 1),
            "interest_pct_gdp": points(main["D41PAY"]["ES"], 1), "pay_pct_gdp": points(main["D1PAY"]["ES"], 1),
            **{f"{k}_pct_gdp": [{"year": y, "value": r(v[k], 1)} for y, v in es_parts.items()] for k, _l, _c in FUNCTIONS},
        },
        "long_run": {
            "imf_revenue_pct_gdp": points(imf["rev"], since=FIRST_YEAR),
            "imf_spending_pct_gdp": points(imf["exp"], since=FIRST_YEAR),
            "imf_interest_pct_gdp": points(imf["ie"], since=FIRST_YEAR),
            "imf_debt_pct_gdp": points(imf["d"], since=FIRST_YEAR),
        },
    }


OECD_PEERS = ["ESP", "DEU", "FRA", "ITA", "PRT"]


def distribution(store: Store) -> dict:
    """Who carries it: IRPF by income bracket (AEAT), redistribution by stage (OECD IDD), tax wedge by wage level."""
    conn = store.conn
    out: dict = {}
    # AEAT brackets: series dimensions carry the bracket label and order.
    rel_rows = {}
    for measure in ("declarations", "income_eur", "tax_eur"):
        store.series("aeat_irpf_stats", f"irpf.{measure}", {"declarations": "COUNT"}.get(measure, "EUR"))  # provenance
        for geo, dims, period, value in conn.execute(
            """
            SELECT s.geography_code, s.dimensions_json, o.period_label, o.value_decimal
            FROM indicator_definitions d JOIN indicator_releases r USING (indicator_id)
            JOIN indicator_series_versions s ON s.indicator_release_id = r.indicator_release_id
            JOIN indicator_observation_versions o ON o.indicator_series_version_id = s.indicator_series_version_id
            WHERE d.source_id = 'aeat_irpf_stats' AND d.indicator_code = ? AND o.revision_state != 'deleted'
              AND r.indicator_release_id = (SELECT r2.indicator_release_id FROM indicator_releases r2
                WHERE r2.indicator_id = d.indicator_id ORDER BY r2.source_snapshot_date DESC, r2.created_at DESC LIMIT 1)
            """,
            (f"irpf.{measure}",),
        ):
            dim = json.loads(dims)
            key = (geo, dim.get("bracket"))
            rel_rows.setdefault(key, {"geo": geo, **dim, "year": int(period)})[measure] = float(value)
    if rel_rows:
        brackets = sorted((v for (geo, b), v in rel_rows.items() if geo == "ESP" and b != "Total"), key=lambda v: v["order"])
        total = rel_rows[("ESP", "Total")]
        rate = lambda v: r(v["tax_eur"] / v["income_eur"] * 100, 1) if v["income_eur"] > 0 else None  # noqa: E731
        out["irpf"] = {
            "tax_year": total["year"],
            "brackets": [
                {"label": v["bracket"], "lower_eur": v.get("lower_eur"), "upper_eur": v.get("upper_eur"),
                 "declarations": int(v["declarations"]), "income_eur": r(v["income_eur"], 0), "tax_eur": r(v["tax_eur"], 0),
                 "effective_rate_pct": rate(v),
                 "share_declarations_pct": r(v["declarations"] / total["declarations"] * 100, 2),
                 "share_tax_pct": r(v["tax_eur"] / total["tax_eur"] * 100, 2)}
                for v in brackets
            ],
            "total": {"declarations": int(total["declarations"]), "income_eur": r(total["income_eur"], 0),
                      "tax_eur": r(total["tax_eur"], 0), "effective_rate_pct": rate(total)},
            "by_ccaa": sorted(
                [{"name": geo, "declarations": int(v["declarations"]), "income_mean_eur": r(v["income_eur"] / v["declarations"], 0),
                  "tax_mean_eur": r(v["tax_eur"] / v["declarations"], 0), "effective_rate_pct": rate(v)}
                 for (geo, b), v in rel_rows.items() if geo != "ESP"],
                key=lambda row: -row["effective_rate_pct"]),
        }
    # OECD IDD: Gini of market, gross (after transfers) and disposable income (after taxes), latest common year per country.
    stages = {}
    for age in ("_T", "Y18T65"):
        g = {m: {a: {int(p["period"]): p["value"] for p in rows} for a, rows in
                 store.series("oecd_income_distribution", f"{m}.{age}", "0_TO_1").items()}
             for m in ("INC_MRKT_GINI", "INC_GROSS_GINI", "INC_DISP_GINI")}
        rows = []
        for a in OECD_PEERS:
            years = set.intersection(*(set(g[m].get(a, {})) for m in g))
            if not years:
                continue
            y = max(years)
            m, gr, d = (g[k][a][y] * 100 for k in ("INC_MRKT_GINI", "INC_GROSS_GINI", "INC_DISP_GINI"))
            rows.append({"area": a, "year": y, "market": r(m, 1), "gross": r(gr, 1), "disposable": r(d, 1),
                         "by_transfers": r(m - gr, 1), "by_taxes": r(gr - d, 1)})
        stages[age] = rows
    out["redistribution"] = stages
    # OECD Taxing Wages: average tax wedge, single person without children, at 67 / 100 / 167 % of the average wage.
    wedge = {lvl: {a: {int(p["period"]): p["value"] for p in rows} for a, rows in
                   store.series("oecd_taxing_wages", f"AV_TW.S_C0.{lvl}", "PT_COS_LB").items()} for lvl in ("AW67", "AW100", "AW167")}
    w_last = max(set.intersection(*(set(wedge[l].get(a, {})) for l in wedge for a in OECD_PEERS)))
    w_first = min(set.intersection(*(set(wedge[l].get(a, {})) for l in wedge for a in OECD_PEERS)))
    out["tax_wedge"] = {
        "year": w_last, "first_year": w_first,
        "areas": [{"area": a, **{lvl: [r(wedge[lvl][a][w_first], 1), r(wedge[lvl][a][w_last], 1)] for lvl in wedge}} for a in OECD_PEERS],
    }
    top = {a: {int(p["period"]): p["value"] for p in rows} for a, rows in store.series("oecd_tax_database", "TS_PIT", "PT_WG_EARN_G").items()}
    thr = {a: {int(p["period"]): p["value"] for p in rows} for a, rows in store.series("oecd_tax_database", "TS_PIT_TH", "FCTR_WG_A_SAL_A").items()}
    t_last = max(set.intersection(*(set(top.get(a, {})) for a in OECD_PEERS)))
    out["top_rates"] = {"year": t_last, "areas": [
        {"area": a, "top_rate_pct": r(top[a][t_last], 1), "threshold_x_avg_wage": r(thr.get(a, {}).get(t_last), 1)} for a in OECD_PEERS]}
    return out


AEAT_CCAA = {
    "Andalucía": "AN", "Aragón": "AR", "Asturias, Principado de": "AS", "Balears, Illes": "IB", "Canarias": "CN",
    "Cantabria": "CB", "Castilla y León": "CL", "Castilla - La Mancha": "CM", "Cataluña": "CT", "Comunitat Valenciana": "VC",
    "Extremadura": "EX", "Galicia": "GA", "Madrid, Comunidad de": "MD", "Murcia, Región de": "MC", "Rioja, La": "RI",
}
STATE_TOP_THRESHOLD_EUR = 300000  # Ley 35/2006 del IRPF, art. 63.1 (escala general estatal, último tramo)
REGIONAL_FIELDS = {
    "top_rate_pct": ("irpf_top_rate_total", "PC"),
    "regional_top_rate_pct": ("irpf_top_rate_regional", "PC"),
    "regional_threshold_eur": ("irpf_top_rate_regional_threshold", "EUR"),
    "financing_per_adj_inhabitant_eur": ("financing_homogeneous_per_adj_inhabitant", "EUR"),
    "financing_after_funds_per_adj_inhabitant_eur": ("financing_after_funds_per_adj_inhabitant", "EUR"),
    "spending_per_inhabitant_eur": ("spending_nonfinancial_per_inhabitant", "EUR"),
    "gdp_per_inhabitant_eur": ("gdp_per_inhabitant", "EUR"),
}


def territory(store: Store, distribution_block: dict) -> dict | None:
    """Autonomous communities: top IRPF rate (common and foral), financing, spending and GDP per person, IRPF paid per
    return (AEAT), against the peers' top rates (OECD)."""
    rows: dict[str, dict] = {}
    years = {}
    for key, (code, unit) in REGIONAL_FIELDS.items():
        try:
            series = store.series("hacienda_ccaa", code, unit)
        except LookupError:
            return None
        for geo, obs in series.items():
            rows.setdefault(geo, {"code": geo})[key] = r(obs[-1]["value"], 2)
            years[key] = int(obs[-1]["period"])
    names = {}
    regimes = {}
    for geo, dims in store.conn.execute(
        """
        SELECT s.geography_code, s.dimensions_json FROM indicator_series_versions s
        JOIN indicator_definitions d USING (indicator_id) WHERE d.source_id = 'hacienda_ccaa'
        """
    ):
        dim = json.loads(dims)
        names[geo] = dim.get("name")
        regimes[geo] = dim.get("regime")
    for geo, row in rows.items():
        row["name"] = names.get(geo)
        row["regime"] = regimes.get(geo)
    for item in (distribution_block.get("irpf") or {}).get("by_ccaa", []):
        geo = AEAT_CCAA.get(item["name"])
        if geo in rows:
            rows[geo].update({"irpf_rate_pct": item["effective_rate_pct"], "irpf_tax_per_return_eur": item["tax_mean_eur"],
                              "irpf_income_per_return_eur": item["income_mean_eur"]})
    ordered = sorted(rows.values(), key=lambda row: -(row.get("top_rate_pct") or 0))
    common = [row for row in ordered if row["regime"] == "comun"]
    spread = lambda key: [min(row[key] for row in common if row.get(key) is not None), max(row[key] for row in common if row.get(key) is not None)]  # noqa: E731
    return {
        "years": years, "irpf_tax_year": (distribution_block.get("irpf") or {}).get("tax_year"),
        "rows": ordered,
        "spread_common": {key: spread(key) for key in ("top_rate_pct", "financing_per_adj_inhabitant_eur",
                                                       "financing_after_funds_per_adj_inhabitant_eur", "spending_per_inhabitant_eur",
                                                       "gdp_per_inhabitant_eur", "irpf_rate_pct")},
        "peers_top_rates": distribution_block.get("top_rates"),
        # State part of the common-regime top rate (combined minus regional, the same in every common community) and the
        # state scale's top bracket (Ley 35/2006, art. 63.1: from 300.000 euros of taxable base).
        "state_top_rate_pct": next(iter({r(row["top_rate_pct"] - row["regional_top_rate_pct"], 2) for row in common
                                          if row.get("regional_top_rate_pct") is not None}), None),
        "state_top_threshold_eur": STATE_TOP_THRESHOLD_EUR,
        # Share of returns above 150.000 euros (the closest AEAT bracket edge below the state top bracket).
        "returns_above_150k_pct": r(sum(b["share_declarations_pct"] for b in (distribution_block.get("irpf") or {}).get("brackets", [])
                                        if (b.get("lower_eur") or 0) >= 150000), 2),
        "financing_gdp_correlation": pearson([(row["gdp_per_inhabitant_eur"], row["financing_per_adj_inhabitant_eur"]) for row in common
                                              if row.get("gdp_per_inhabitant_eur") and row.get("financing_per_adj_inhabitant_eur")]),
        "regional_threshold_range": [
            {"name": row["name"], "threshold_eur": row["regional_threshold_eur"]}
            for row in (min(common, key=lambda x: x.get("regional_threshold_eur") or 1e12),
                        max(common, key=lambda x: x.get("regional_threshold_eur") or 0))
        ],
    }


def service_results() -> dict | None:
    """Read-only reuse of the sibling pages' published data (health, education, housing), with provenance."""
    loaded, provenance = {}, {}
    for key, (page, label) in SIBLINGS.items():
        path = SIBLING_DIR / f"{key}.json"
        if not path.exists():
            return None
        payload = path.read_bytes()
        loaded[key] = json.loads(payload)
        provenance[key] = {
            "page": page, "label": label, "file": f"/visualizaciones/data/{key}.json",
            "sha256": hashlib.sha256(payload).hexdigest(), "generated_at": loaded[key].get("generated_at"),
        }
    health, edu, housing = loaded["sanidad"], loaded["educacion"], loaded["vivienda"]
    last = lambda rows: rows[-1] if rows else None  # noqa: E731

    def by_eu(series: dict) -> dict:
        out = {}
        for g in EU_AREAS:
            row = last(series.get(g) or [])
            if row:
                out[g] = {"year": row["year"], "value": row["value"]}
        return out

    pisa = {g: last(edu["pisa"]["math"].get(EU_TO_OECD.get(g, "")) or []) for g in EU_AREAS}
    social = {row["country"]: row for row in housing.get("social_rental_stock", [])}
    waits = health["waiting"]["surgery"]["mean_days"]
    indicators = [
        {"key": "life_expectancy", "label": "Esperanza de vida al nacer", "unit": "años", "better": "higher", "page": "sanidad",
         "values": by_eu(health["life_expectancy"]["eurostat"])},
        {"key": "treatable", "label": "Mortalidad tratable (muertes evitables con atención a tiempo, por 100.000)", "unit": "por 100.000",
         "better": "lower", "page": "sanidad", "values": by_eu(health["outcomes"]["treatable"])},
        {"key": "pisa_math", "label": "PISA matemáticas (puntos)", "unit": "puntos", "better": "higher", "page": "educacion",
         "values": {g: {"year": v["year"], "value": v["value"]} for g, v in pisa.items() if v}},
        {"key": "early_leavers", "label": "Abandono escolar temprano (% de 18 a 24 años)", "unit": "%", "better": "lower",
         "page": "educacion", "values": by_eu(edu["early_leavers"]["series"])},
        {"key": "social_rental", "label": "Vivienda social en alquiler (% del parque)", "unit": "%", "better": "higher",
         "page": "vivienda", "values": {g: {"year": social[o]["year"], "value": social[o]["value"]}
                                        for g, o in EU_TO_OECD.items() if o in social}},
    ]
    spain_over_time = [
        {"key": "surgery_wait_days", "label": "Espera media para cirugía (días)", "page": "sanidad", "better": "lower",
         "from": {"date": waits[0]["date"], "value": waits[0]["value"]}, "to": {"date": waits[-1]["date"], "value": waits[-1]["value"]},
         "note": "Serie con cambios de cobertura y método en 2012, 2016 y 2018 (ver la página de sanidad)."},
        {"key": "early_leavers", "label": "Abandono escolar temprano (%)", "page": "educacion", "better": "lower",
         "from": edu["early_leavers"]["series"]["ES"][0], "to": edu["early_leavers"]["series"]["ES"][-1],
         "note": "Encuesta de Población Activa con rupturas en 2005, 2014 y 2021."},
        {"key": "treatable", "label": "Mortalidad tratable (por 100.000)", "page": "sanidad", "better": "lower",
         "from": health["outcomes"]["treatable"]["ES"][0], "to": health["outcomes"]["treatable"]["ES"][-1], "note": None},
        {"key": "pisa_math", "label": "PISA matemáticas (puntos)", "page": "educacion", "better": "higher",
         "from": next(p for p in edu["pisa"]["math"]["ESP"] if p.get("comparable")), "to": edu["pisa"]["math"]["ESP"][-1], "note": None},
    ]
    for item in spain_over_time:
        item["from"] = {k: item["from"][k] for k in ("year", "date", "value") if k in item["from"]}
        item["to"] = {k: item["to"][k] for k in ("year", "date", "value") if k in item["to"]}
    return {"indicators": indicators, "spain_over_time": spain_over_time, "provenance": provenance}


# Typical cases and age split (docs/etl/sprints/VIZ-SEGMENTOS-20261019/README.md, §2–§3). Age bands are the source's own.
AGE_BANDS = [("TOTAL", "Todas las edades"), ("Y16-24", "16 a 24"), ("Y25-49", "25 a 49"), ("Y50-64", "50 a 64"), ("Y_GE65", "65 y más")]
AGE_BASES = [2007, 2013, 2019]  # income years (survey year - 1), same starting years as the «bolsillo» figure
MADRID_CITY = "28079"


def sibling(key: str) -> tuple[dict, dict]:
    """A sibling page's published JSON with its provenance (sha256 of the exact bytes read)."""
    page, label = SIBLINGS[key]
    payload = (SIBLING_DIR / f"{key}.json").read_bytes()
    data = json.loads(payload)
    return data, {"page": page, "label": label, "file": f"/visualizaciones/data/{key}.json",
                  "sha256": hashlib.sha256(payload).hexdigest(), "generated_at": data.get("generated_at")}


def pension_per_pensioner(store: Store, geo: str, year: int) -> float:
    """Old-age and survivors' pension spending (COFOG GF1002 + GF1003, euros) per pensioner (ESSPROS), unrounded."""
    spend = sum(next(p["value"] for p in store.series("eurostat_sdmx", f"{code}.TE.S13", "MIO_EUR", "gov_10a_exp")[geo]
                     if int(p["period"]) == year) for code in ("GF1002", "GF1003"))
    ben = next(p["value"] for p in store.series("eurostat_sdmx", "T.OLD_SRV.TOTAL.TOTAL", "PER")[geo] if int(p["period"]) == year)
    return spend * 1e6 / ben


def pearson(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 3:
        return None
    xs, ys = zip(*pairs)
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxy = sum((x - mx) * (y - my) for x, y in pairs)
    sxx, syy = sum((x - mx) ** 2 for x in xs), sum((y - my) ** 2 for y in ys)
    return r(sxy / math.sqrt(sxx * syy), 2) if sxx and syy else None


def interp(points_: list[tuple[float, float]], x: float) -> float:
    """Linear interpolation (and extrapolation from the nearest segment) through sorted (x, y) points."""
    pts = sorted(points_)
    i = 1
    while i < len(pts) - 1 and x > pts[i][0]:
        i += 1
    (x0, y0), (x1, y1) = pts[i - 1], pts[i]
    return y0 + (x - x0) / (x1 - x0) * (y1 - y0)


def segments(store: Store, pension_per_pensioner: float, pension_year: int) -> dict | None:
    """Income by age (EU-SILC, real), housing split and five typical households (taxes, housing, what is left)."""
    try:
        housing, housing_prov = sibling("vivienda")
    except FileNotFoundError:
        return None
    hs = housing.get("segments") or {}
    conn = store.conn

    # ---- income by age: median equivalised disposable income, real euros of the last income year (HICP)
    def silc(code: str) -> dict[str, dict[int, tuple[float, str | None]]]:
        dataset = "ilc_di03"
        store.series("eurostat_sdmx", code, "NAC", dataset)  # provenance
        out: dict[str, dict[int, tuple[float, str | None]]] = defaultdict(dict)
        for geo, period, value, status in conn.execute(
            """
            SELECT s.geography_code, o.period_label, o.value_decimal, o.source_status_code
            FROM indicator_definitions d JOIN indicator_releases r USING (indicator_id)
            JOIN indicator_series_versions s ON s.indicator_release_id = r.indicator_release_id
            JOIN indicator_observation_versions o ON o.indicator_series_version_id = s.indicator_series_version_id
            WHERE d.source_id = 'eurostat_sdmx' AND d.dataset_code = ? AND d.indicator_code = ? AND d.unit_code = 'NAC'
              AND o.revision_state != 'deleted' AND o.value_decimal IS NOT NULL
              AND r.indicator_release_id = (SELECT r2.indicator_release_id FROM indicator_releases r2
                WHERE r2.indicator_id = d.indicator_id ORDER BY r2.source_snapshot_date DESC, r2.created_at DESC LIMIT 1)
            """,
            (dataset, code),
        ):
            out[geo][int(period)] = (float(value), status)
        return out

    hicp = {g: {int(p["period"]): p["value"] for p in rows} for g, rows in store.series("eurostat_sdmx", "CP00", "INX_A_AVG").items()}
    by_age = {age: silc(f"{age}.T.MED_EI") for age, _ in AGE_BANDS}
    es_last = max(by_age["TOTAL"]["ES"])
    breaks = sorted({y for age in by_age for y, (_v, st) in by_age[age]["ES"].items() if st == "b"})
    first_survey = max([y for y in breaks if y <= es_last] or [min(by_age["TOTAL"]["ES"])])  # never cross a flagged break
    price_year = es_last - 1

    def age_rows(geo: str) -> list[dict]:
        rows = []
        geo_last = max(by_age["TOTAL"].get(geo, {}) or [0])
        geo_price = geo_last - 1
        for age, label in AGE_BANDS:
            series = by_age[age].get(geo, {})
            if geo_last not in series or geo_price not in hicp.get(geo, {}):
                continue
            # Each country starts after its own last flagged break (no change is computed across a break).
            geo_breaks = [y for a in by_age for y, (_v, st) in by_age[a].get(geo, {}).items() if st == "b" and y <= geo_last]
            geo_first = max(geo_breaks or [min(series)])
            real = {s - 1: v * hicp[geo][geo_price] / hicp[geo][s - 1] for s, (v, _st) in series.items()
                    if s >= geo_first and s - 1 in hicp.get(geo, {})}
            last = real[geo_price]
            rows.append({
                "age": age, "label": label, "survey_year": geo_last, "first_survey": geo_first, "income_year": geo_price, "nominal_last": r(series[geo_last][0], 0),
                "real": {str(y): r(v, 0) for y, v in sorted(real.items()) if y in AGE_BASES or y == geo_price},
                "change": {str(b): r((last / real[b] - 1) * 100, 1) if b in real else None for b in AGE_BASES},
                "vs_total_first": None,
            })
        total = next((row for row in rows if row["age"] == "TOTAL"), None)
        for row in rows:
            first = str(min(AGE_BASES))
            if total and row["real"].get(first) and total["real"].get(first):
                row["vs_total_first"] = r(row["real"][first] / total["real"][first] * 100, 0)
                row["vs_total_last"] = r(row["real"][str(row["income_year"])] / total["real"][str(row["income_year"])] * 100, 0)
        return rows

    income_by_age = {
        "survey_year": es_last, "income_year": price_year, "first_survey": first_survey, "breaks_es": breaks,
        "bases": AGE_BASES, "price_year": price_year,
        "areas": {geo: age_rows(geo) for geo in ("ES", "DE", "FR", "IT", "PT")},
    }

    # ---- housing split (own DB + the housing page's published figures)
    def latest(code: str, unit: str, dataset: str, geo: str = "ES") -> tuple[int, float]:
        rows = store.series("eurostat_sdmx", code, unit, dataset).get(geo, [])
        return int(rows[-1]["period"]), rows[-1]["value"]

    y_mean, mean_share = latest("TOTAL.TOTAL", "PC", "ilc_mded01")
    y_rent, rent_share = latest("TOTAL.TOTAL", "PC", "ilc_mded02")
    _y, rent_share_single = latest("A1_LT65.TOTAL", "PC", "ilc_mded02")
    tenure = {row["key"]: row for row in hs.get("tenure", [])}
    age_tenure = {row["age"]: row["shares"] for row in (hs.get("age_tenure") or {}).get("rows", [])}
    housing_split = {
        "year": y_mean, "cost_share_mean": r(mean_share, 1), "cost_share_median": hs.get("cost_share_median"),
        "rent_share_renters": r(rent_share, 1), "rent_share_single_lt65": r(rent_share_single, 1), "rent_year": y_rent,
        "overburden": {k: tenure[k]["overburden_pct"] for k in ("OWN_NL", "OWN_L", "RENT_MKT", "RENT_FR") if k in tenure},
        "population": {k: tenure[k]["pop_pct"] for k in ("OWN_NL", "OWN_L", "RENT_MKT", "RENT_FR") if k in tenure},
        "young_rent_mkt": (age_tenure.get("16–29") or {}).get("RENT_MKT"), "young_own_nl": (age_tenure.get("16–29") or {}).get("OWN_NL"),
        "old_own_nl": (age_tenure.get("65+") or {}).get("OWN_NL"), "old_rent_mkt": (age_tenure.get("65+") or {}).get("RENT_MKT"),
        "at_home_25_34": ((hs.get("at_home") or {}).get("Y25-34") or {}).get("ES"),
    }

    # ---- five households: OECD Taxing Wages (same year as the rents), EU-SILC housing costs, Eurostat VAT experimental
    def tw(measure: str, hh: str, level: str, spouse: str, unit: str, geo: str = "ESP") -> dict[int, float]:
        return store.annual("oecd_taxing_wages", f"{measure}.{hh}.{level}.{spouse}", unit, geo)

    madrid = next((row for row in hs.get("cities", []) if row.get("code") == MADRID_CITY), None)
    pay = (housing.get("capacity") or {}).get("pay") or {}
    if not madrid or not pay.get("gross_young") or not hs.get("young_net_es"):
        return {"income_by_age": income_by_age, "housing": housing_split, "provenance": {"vivienda": housing_prov}}
    year = min(madrid["year"], max(tw("GEBT", "S_C0", "AW100", "_Z", "XDC")))
    aw = tw("GEBT", "S_C0", "AW100", "_Z", "XDC")[year]
    single = {
        key: [(m, store.annual("oecd_taxing_wages", f"{measure}.S_C0.{lvl}" + ("" if measure == "AV_TW" else "._Z"), unit, "ESP")[year])
              for lvl, m in (("AW67", 0.67), ("AW100", 1.0), ("AW167", 1.67))]
        for key, (measure, unit) in {"npatr": ("NPATR", "PT_WG_EARN_G"), "wedge": ("AV_TW", "PT_COS_LB"),
                                      "ssc": ("AV_R_EMPEE_SSC", "PT_WG_EARN_G")}.items()
    }
    ppp_year, ppp = max((int(p["period"]), p["value"]) for p in store.series("eurostat_sdmx", "PPP_EU27_2020.A01", "EUR_PER_PPS").get("ES", []))
    cost = {}
    for code in ("A1_DCH.TOTAL.RENT", "A1_GE65.TOTAL.OWN", "A1_LT65.TOTAL.OWN"):
        cy, pps = latest(code, "PPS", "ilc_mded03")
        cost[code] = (cy, pps)
    vat = {}
    for hh in ("TOTAL", "A1", "A1_DCH", "A2_DCH"):
        vat[hh] = latest(f"{hh}.MED", "PC", "icw_tax_02")
    vat_q = {q: latest(f"{q}.MED", "PC", "icw_tax_03") for q in ("TOTAL", "QU1", "QU2", "QU3", "QU4", "QU5")}
    vat_year = vat["TOTAL"][0]
    nat_income = by_age["TOTAL"]["ES"][es_last][0]
    median_share = hs.get("cost_share_median")

    def household(key: str, gross: float, npatr: float, wedge: float | None, housing_year: float, uc: float, vat_hh: str,
                  ssc: float | None = None, **extra) -> dict:
        direct = gross * (npatr - (ssc or 0)) / 100 if ssc is not None else gross * npatr / 100
        net = gross - direct
        employer = net / (1 - wedge / 100) - gross if wedge is not None else None
        left = net - housing_year
        return {
            "key": key, "gross": r(gross, 0), "direct_taxes": r(direct, 0), "direct_rate_pct": r(direct / gross * 100, 1),
            "employer_ssc": r(employer, 0), "net": r(net, 0), "housing": r(housing_year, 0),
            "housing_share_pct": r(housing_year / net * 100, 1), "left": r(left, 0), "uc": uc, "left_per_uc": r(left / uc, 0),
            "vat": r(gross * vat[vat_hh][1] / 100, 0), "vat_share_pct": r(vat[vat_hh][1], 1), "vat_household": vat_hh,
            "vs_median_pct": r(left / uc / (nat_income * (1 - median_share / 100)) * 100, 0) if median_share else None, **extra,
        }

    # Persona 1's pay is the housing page's: its published net (Spain's 25-34 gross pay x Madrid's wage level, minus the
    # worker's rate at that pay). Recover the gross with the same OECD schedule so both pages show the same net.
    gross_young = next(p["value"] for p in pay["gross_young"] if p["year"] == madrid["young_net_year"])
    net_of = lambda g: g * (1 - interp(single["npatr"], g / aw) / 100)  # noqa: E731
    lo_g, hi_g = madrid["young_net"], madrid["young_net"] * 2
    for _ in range(60):
        mid_g = (lo_g + hi_g) / 2
        lo_g, hi_g = (mid_g, hi_g) if net_of(mid_g) < madrid["young_net"] else (lo_g, mid_g)
    g1 = (lo_g + hi_g) / 2
    if abs(net_of(g1) - madrid["young_net"]) > 1:
        raise SystemExit("persona 1: could not match the housing page's net pay")
    young_factor = g1 / gross_young
    m1 = g1 / aw
    pension = pension_per_pensioner
    m4 = pension / aw
    cases = [
        household("p1_young_renter_madrid", g1, interp(single["npatr"], m1), interp(single["wedge"], m1), madrid["rent_month"] * 12, 1.0, "A1",
                  aw_multiple=r(m1, 2), rent_month=madrid["rent_month"], rent_year=madrid["year"], pay_year=madrid["young_net_year"],
                  madrid_wage_factor=r(young_factor, 3)),
        household("p2_family_renter_metro", tw("GEBT", "C_C2", "AW100", "AW67", "XDC")[year], tw("NPATR", "C_C2", "AW100", "AW67", "PT_WG_EARN_G")[year],
                  tw("AV_TW", "C_C2", "AW100", "AW67", "PT_COS_LB")[year], madrid["rest_rent_month"] * 12, 2.1, "A2_DCH",
                  rent_month=madrid["rest_rent_month"], rent_year=madrid["year"]),
        household("c_single_parent_renter", tw("GEBT", "S_C2", "AW67", "_Z", "XDC")[year], tw("NPATR", "S_C2", "AW67", "_Z", "PT_WG_EARN_G")[year],
                  tw("AV_TW", "S_C2", "AW67", "_Z", "PT_COS_LB")[year], cost["A1_DCH.TOTAL.RENT"][1] * ppp * 12, 1.6, "A1_DCH",
                  cost_month=r(cost["A1_DCH.TOTAL.RENT"][1] * ppp, 0), cost_year=cost["A1_DCH.TOTAL.RENT"][0]),
        household("p4_retired_owner_interior", pension, interp(single["npatr"], m4), None, cost["A1_GE65.TOTAL.OWN"][1] * ppp * 12, 1.0, "A1",
                  ssc=interp(single["ssc"], m4), aw_multiple=r(m4, 2), pension_year=pension_year,
                  cost_month=r(cost["A1_GE65.TOTAL.OWN"][1] * ppp, 0), cost_year=cost["A1_GE65.TOTAL.OWN"][0]),
        household("p5_professional_madrid", tw("GEBT", "S_C0", "AW167", "_Z", "XDC")[year], tw("NPATR", "S_C0", "AW167", "_Z", "PT_WG_EARN_G")[year],
                  store.annual("oecd_taxing_wages", "AV_TW.S_C0.AW167", "PT_COS_LB", "ESP")[year], cost["A1_LT65.TOTAL.OWN"][1] * ppp * 12, 1.0, "A1",
                  cost_month=r(cost["A1_LT65.TOTAL.OWN"][1] * ppp, 0), cost_year=cost["A1_LT65.TOTAL.OWN"][0]),
    ]
    # Family relief against the peers: single at the average wage vs one-earner couple with two children; lone parent's net rate.
    peers = []
    for area in ("ESP", "DEU", "FRA", "ITA", "PRT"):
        single_w = store.annual("oecd_taxing_wages", "AV_TW.S_C0.AW100", "PT_COS_LB", area).get(year)
        couple_w = tw("AV_TW", "C_C2", "AW100", "NOEARN_UNEMP", "PT_COS_LB", area).get(year)
        lone = tw("NPATR", "S_C2", "AW67", "_Z", "PT_WG_EARN_G", area).get(year)
        single67 = tw("NPATR", "S_C0", "AW67", "_Z", "PT_WG_EARN_G", area).get(year)
        peers.append({"area": area, "single_aw100_wedge": r(single_w, 1), "couple2_one_earner_wedge": r(couple_w, 1),
                      "relief_pts": r(single_w - couple_w, 1) if single_w is not None and couple_w is not None else None,
                      "single_parent_aw67_net_rate": r(lone, 1), "single_aw67_net_rate": r(single67, 1)})
    return {
        "income_by_age": income_by_age,
        "housing": housing_split,
        "cases": {
            "year": year, "average_wage": r(aw, 0), "median_wage": next((r(p["value"], 0) for p in pay.get("gross_median", []) if p["year"] == year), None),
            "single_aw100_wedge": r(store.annual("oecd_taxing_wages", "AV_TW.S_C0.AW100", "PT_COS_LB", "ESP")[year], 1), "ppp_year": ppp_year, "eur_per_pps": r(ppp, 4), "vat_year": vat_year,
            "national": {"income_per_uc": r(nat_income, 0), "survey_year": es_last, "median_housing_share_pct": median_share,
                         "after_housing_per_uc": r(nat_income * (1 - median_share / 100), 0) if median_share else None},
            "rows": cases,
            "vat_by_quintile": {q: r(v, 1) for q, (_y, v) in vat_q.items()},
            "family_relief": peers,
        },
        "provenance": {"vivienda": housing_prov},
    }


def implicit_interest(store: Store) -> dict | None:
    """Implicit interest rate on general government debt: interest of the year / debt at the end of the previous year,
    both from Eurostat's EDP table (same source and coverage), in euros."""
    try:
        debt = store.annual("eurostat_sdmx", "GD.S13", "MIO_EUR", "ES")
        interest = {int(p["period"]): p["value"] for p in store.series("eurostat_sdmx", "D41PAY.S13", "MIO_EUR", "gov_10dd_edpt1").get("ES", [])}
        debt_pc = {int(p["period"]): p["value"] for p in store.series("eurostat_sdmx", "GD.S13", "PC_GDP", "gov_10dd_edpt1").get("ES", [])}
    except LookupError:
        return None
    rate = {y: interest[y] / debt[y - 1] * 100 for y in sorted(interest) if y - 1 in debt and debt[y - 1]}
    if not rate:
        return None
    first, last = min(rate), max(rate)
    peak = max(rate, key=lambda y: rate[y])
    low = min(rate, key=lambda y: rate[y])
    point = lambda y: {"year": y, "rate_pct": r(rate[y], 1), "debt_prev_pct_gdp": r(debt_pc.get(y - 1), 1),  # noqa: E731
                       "interest_meur": r(interest[y], 0), "debt_prev_meur": r(debt[y - 1], 0)}
    return {"source": "eurostat gov_10dd_edpt1 (S13, D41PAY / GD del año anterior)", "first": point(first), "peak": point(peak),
            "low": point(low), "last": point(last), "series": points(rate, 2)}


def build(conn: sqlite3.Connection) -> dict:
    store = Store(conn)
    imf = store.annual("imf_fpp", "rev", "PT_GDP", "ESP")
    oecd = {code: store.series("oecd_revenue_statistics", f"TAX_REV.S13.{code}", "PT_B1GQ") for code in ["_T", *COMPOSITION]}
    oecd_eur = store.annual("oecd_revenue_statistics", "TAX_REV.S13._T", "XDC", "ESP")
    eurostat = store.series("eurostat_sdmx", "D2_D5_D91_D61_M_D995.S13_S212", "PC_GDP")
    pop = store.annual("worldbank_wdi", "SP.POP.TOTL", "PERSONS", "ESP")
    cpi = store.annual("worldbank_wdi", "FP.CPI.TOTL", "IDX2010", "ESP")

    def annual(code: str, area: str) -> dict[int, float]:
        return {int(p["period"]): p["value"] for p in oecd[code].get(area, [])}

    esp = {code: annual(code, "ESP") for code in oecd}
    years = sorted(esp["_T"])
    last_year = years[-1]
    # Revenue per person in constant euros of the last CPI year available within the revenue series.
    base_year = max(y for y in cpi if y <= last_year)
    per_capita = [
        {"year": y, "value": r(oecd_eur[y] * 1e9 / pop[y] * cpi[base_year] / cpi[y], 0)}
        for y in years if y in oecd_eur and y in pop and y in cpi
    ]
    by_payer = [
        {
            "year": y,
            "households": r(sum(esp[c].get(y, 0.0) for c in ("T_1100", "T_2100", "T_2300"))),
            "companies": r(sum(esp[c].get(y, 0.0) for c in ("T_1200", "T_2200"))),
            "consumption": r(esp["T_5000"].get(y)),
            "property": r(esp["T_4000"].get(y)),
        }
        for y in years
    ]
    eu = {geo: {int(p["period"]): p["value"] for p in rows} for geo, rows in eurostat.items()}

    # Consolidated figure: who pays, per country, in the latest year every area reports every category,
    # against each country's 1965 total.
    by_area = {area: {code: annual(code, area) for code in oecd} for area in OECD_AREAS}
    comp_year = max(set.intersection(*(set(series) for area in by_area.values() for series in area.values())))
    first_year = years[0]
    peers_composition = []
    for area, cat in by_area.items():
        total = cat["_T"][comp_year]
        parts = {
            "households": sum(cat[c][comp_year] for c in ("T_1100", "T_2100", "T_2300")),
            "companies": sum(cat[c][comp_year] for c in ("T_1200", "T_2200")),
            "consumption": cat["T_5000"][comp_year],
            "property": cat["T_4000"][comp_year],
        }
        parts["other"] = max(0.0, total - sum(parts.values()))
        peers_composition.append({
            "area": area, "total": r(total), "base_total": r(cat["_T"].get(first_year)),
            **{k: r(v) for k, v in parts.items()},
        })
    rates = statutory_rates(conn)
    comp = complexity(conn)
    squeeze_block = squeeze(store)
    spending_block = spending(store)
    distribution_block = distribution(store)
    territory_block = territory(store, distribution_block)
    results = service_results()
    pc = spending_block.get("pension_composition") or {}
    segments_block = segments(store, pension_per_pensioner(store, "ES", pc["year"]), pc["year"]) if pc.get("year") else None

    sources = {}
    for source_id, releases in store.provenance.items():
        label, page = SOURCE_PAGES[source_id]
        retrieved = max((rel["retrieved_at"] or "" for rel in releases), default="") or None
        sources[source_id] = {"label": label, "page": page, "retrieved_at": retrieved, "releases": releases}
    for key, present in (("vclc_tax_law_rates", rates), ("boe_api_legal", comp)):
        if present:
            label, page = SOURCE_PAGES[key]
            sources[key] = {"label": label, "page": page, "retrieved_at": None, "releases": []}

    first_oecd = esp["_T"][years[0]]
    # Revenue per person split by who hands it in (OECD classification): households directly (personal income tax, employee
    # and self-employed contributions), firms (corporate tax, employer contributions), consumption, property (not split).
    pc_last = per_capita[-1]
    payer_last = next(row for row in by_payer if row["year"] == pc_last["year"])
    total_last = esp["_T"][pc_last["year"]]
    per_capita_payers = {"year": pc_last["year"], "total_eur": pc_last["value"], **{
        key: {"pct_of_total": r(payer_last[key] / total_last * 100, 1), "eur": r(pc_last["value"] * payer_last[key] / total_last, 0)}
        for key in ("households", "companies", "consumption", "property")
    }}
    debt_interest = implicit_interest(store)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "storage": "SQLite public-finance-es.db: indicator_* contract (releases, revisions, evidence per value), "
        "legal_norms, legal_norm_lineage_edges, legal_norm_text_metrics; built by scripts/ingest_public_finance_es.py",
        "headline": {
            "first_year": FIRST_YEAR,
            "first_value_imf": r(imf[FIRST_YEAR]),
            "oecd_first_year": years[0],
            "oecd_first_value": r(first_oecd),
            "last_year": last_year,
            "last_value": r(esp["_T"][last_year]),
            "multiple_oecd": r(esp["_T"][last_year] / first_oecd),
            "per_capita_first": per_capita[0],
            "per_capita_last": per_capita[-1],
            "per_capita_base_year": base_year,
        },
        "long_run": {
            "imf_revenue_pct_gdp": points(imf, since=FIRST_YEAR),
            "oecd_tax_pct_gdp": points(esp["_T"]),
        },
        "per_capita_real_eur": per_capita,
        "per_capita_payers": per_capita_payers,
        "debt_interest": debt_interest,
        "composition_pct_gdp": {code: points(esp[code]) for code in COMPOSITION},
        "composition_labels": COMPOSITION,
        "by_payer_pct_gdp": by_payer,
        "peers_pct_gdp": {area: points(annual("_T", area)) for area in OECD_AREAS},
        "peers_composition": {"year": comp_year, "base_year": first_year, "areas": peers_composition},
        "eu27_pct_gdp": [
            {"year": y, "es": r(eu.get("ES", {}).get(y)), "eu27": r(v)} for y, v in sorted(eu.get("EU27_2020", {}).items())
        ],
        "squeeze": squeeze_block,
        "spending": spending_block,
        "service_results": results,
        "distribution": distribution_block,
        "segments": segments_block,
        "territory": territory_block,
        "statutory_rates": rates,
        "complexity": comp,
        "sources": sources,
    }


def write_csv(data: dict, path: Path) -> None:
    rows: list[tuple] = []
    for row in data["long_run"]["imf_revenue_pct_gdp"]:
        rows.append(("imf_fpp", "ingresos_publicos_pct_pib", "ESP", row["year"], row["value"]))
    for area, pts in data["peers_pct_gdp"].items():
        rows.extend(("oecd_revenue_statistics", "_T_pct_pib", area, p["year"], p["value"]) for p in pts)
    for code, pts in data["composition_pct_gdp"].items():
        rows.extend(("oecd_revenue_statistics", f"{code}_pct_pib", "ESP", p["year"], p["value"]) for p in pts)
    for row in data["eu27_pct_gdp"]:
        rows.append(("eurostat_sdmx", "carga_fiscal_pct_pib", "ES", row["year"], row["es"]))
        rows.append(("eurostat_sdmx", "carga_fiscal_pct_pib", "EU27_2020", row["year"], row["eu27"]))
    base = data["headline"]["per_capita_base_year"]
    rows.extend(
        ("oecd+worldbank", f"recaudacion_por_habitante_eur_{base}", "ESP", p["year"], p["value"]) for p in data["per_capita_real_eur"]
    )
    sq = data["squeeze"]
    for row in sq["areas"]:
        for field in ("tax_pps", "income_pps", "tax_to_income_pct", "effort_index"):
            rows.append(("eurostat_sdmx", field, row["area"], sq["year"], row[field]))
        for field in ("real_tax_index", "real_income_index"):
            rows.extend(("eurostat_sdmx", f"{field}_{sq['base_year']}_100", row["area"], p["year"], p["value"]) for p in row[field])
    sv = sq["survey"]
    for row in sv["areas"]:
        rows.extend(("eurostat_sdmx", f"eu_silc_{key}", row["area"], sv["survey_year"], row[key]) for key, *_ in SURVEY)
    sp = data["spending"]
    for row in sp["areas"]:
        for field in ("total", "revenue", "balance", "pay", *(f["key"] for f in sp["functions"])):
            rows.append(("eurostat_sdmx", f"gasto_{field}_pct_pib" if field not in ("revenue", "balance") else f"{field}_pct_pib",
                         row["area"], sp["year"], row[field]))
    for key, pts in sp["spain_series"].items():
        rows.extend(("eurostat_sdmx", key, "ES", p["year"], p["value"]) for p in pts)
    for key, pts in sp["long_run"].items():
        rows.extend(("imf_fpp", key, "ESP", p["year"], p["value"]) for p in pts)
    for row in (data.get("territory") or {}).get("rows", []):
        for key in REGIONAL_FIELDS:
            if row.get(key) is not None:
                rows.append(("hacienda_ccaa", key, row["code"], data["territory"]["years"].get(key), row[key]))
    for b in (data.get("distribution") or {}).get("irpf", {}).get("brackets", []):
        rows.append(("aeat_irpf_stats", f"irpf_tipo_efectivo_{b['label']}", "ESP", data["distribution"]["irpf"]["tax_year"], b["effective_rate_pct"]))
    seg = data.get("segments") or {}
    age = seg.get("income_by_age") or {}
    for geo, age_rows_ in (age.get("areas") or {}).items():
        for row in age_rows_:
            rows.extend(("eurostat_sdmx", f"renta_mediana_real_eur_{age['price_year']}_{row['age']}", geo, int(y), v) for y, v in row["real"].items())
    for key, value in (seg.get("housing") or {}).items():
        if isinstance(value, (int, float)) and key != "year":
            rows.append(("eurostat_sdmx+visualizaciones/vivienda", f"vivienda_{key}", "ES", seg["housing"]["year"], value))
    cases = seg.get("cases") or {}
    for case in cases.get("rows", []):
        for field in ("gross", "direct_taxes", "employer_ssc", "net", "housing", "left", "left_per_uc", "vat"):
            if case.get(field) is not None:
                rows.append(("caso_tipo_ilustrativo", f"{case['key']}_{field}_eur", "ES", cases["year"], case[field]))
    for ind in (data.get("service_results") or {}).get("indicators", []):
        rows.extend((f"visualizaciones/{ind['page']}", ind["key"], g, v["year"], v["value"]) for g, v in ind["values"].items())
    for key, changes in (data.get("statutory_rates") or {}).get("series", {}).items():
        rows.extend(("vclc_tax_law_rates", f"{key}_desde", "ESP", c["from_year"], c["value_pct"]) for c in changes)
    for law in (data.get("complexity") or {}).get("amendments", []):
        rows.extend(("boe_api_legal", f"normas_modificadoras_{law['boe_id']}", "ESP", int(y), n) for y, n in law["by_year"].items())
    for row in (data.get("complexity") or {}).get("law_length", []):
        rows.append(
            ("boe_api_legal", f"palabras_sin_preambulo_{row['boe_id']}_{row['version']}", "ESP", row["year"], row["words_excl_preamble"])
        )
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
            print(f"export_public_viz_fiscal: {args.db.name} not found; keeping committed artifact", file=sys.stderr)
            return 0
        raise SystemExit(f"missing {args.db}; run scripts/ingest_public_finance_es.py first")
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    data = build(conn)
    conn.close()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    # Same inputs, same file: keep the previous timestamp when nothing else changed (offline reruns are byte-identical).
    if OUT_JSON.exists():
        previous = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        if {**previous, "generated_at": None} == {**data, "generated_at": None}:
            data["generated_at"] = previous["generated_at"]
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    write_csv(data, OUT_CSV)
    h = data["headline"]
    print(
        f"carga-fiscal: {h['oecd_first_year']} {h['oecd_first_value']}% -> {h['last_year']} {h['last_value']}% PIB "
        f"(x{h['multiple_oecd']}); {OUT_JSON.stat().st_size // 1024} KB"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
