#!/usr/bin/env python3
"""Export /visualizaciones/sanidad/ data from the health DB (scripts/ingest_health_es.py).

Reads only normalized tables (latest release of each indicator in the indicator_* contract): life expectancy
(Eurostat, INE, OWID long run, World Bank for the world ranking), health spending (OECD SHA via DBnomics, Eurostat
SHA, Ministerio de Sanidad EGSP by region), waiting lists (SISLE-SNS, curated from the official PDFs with series
breaks as status codes) and doctors (Eurostat). Writes the page JSON with per-source provenance (URL, retrieval
date, sha256) and a long CSV. When the DB is missing (CI checkouts) the committed artifact is kept.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "etl/data/staging/health-es.db"
OUT_JSON = REPO_ROOT / "ui/site/public/visualizaciones/data/sanidad.json"
OUT_CSV = REPO_ROOT / "ui/site/public/visualizaciones/data/sanidad.csv"

FIRST_YEAR = 1925
PEERS_ISO3 = ["ESP", "DEU", "FRA", "ITA", "PRT"]
PEERS_NUTS = ["ES", "DE", "FR", "IT", "PT", "EU27_2020"]
OECD_MEMBERS = [
    "AUS", "AUT", "BEL", "CAN", "CHL", "COL", "CRI", "CZE", "DNK", "EST", "FIN", "FRA", "DEU", "GRC", "HUN", "ISL",
    "IRL", "ISR", "ITA", "JPN", "KOR", "LVA", "LTU", "LUX", "MEX", "NLD", "NZL", "NOR", "POL", "PRT", "SVK", "SVN",
    "ESP", "SWE", "CHE", "TUR", "GBR", "USA",
]
MIN_OECD_REPORTING = 34  # an OECD simple mean is shown only for years where at least 34 of 38 members report
SOURCE_PAGES = {
    "eurostat_sdmx": ("Eurostat · demo_mlexpec, hlth_sha11_hf, hlth_rs_prs2, hlth_rs_physcat", "https://ec.europa.eu/eurostat/web/health/database"),
    "ine_wstempus": ("INE · Indicadores Demográficos Básicos, tabla 1414", "https://www.ine.es/jaxiT3/Tabla.htm?t=1414"),
    "owid_grapher": ("Our World in Data · esperanza de vida (Riley; Zijdeman et al.; HMD; ONU WPP)", "https://ourworldindata.org/grapher/life-expectancy"),
    "worldbank_wdi": ("Banco Mundial · esperanza de vida al nacimiento (SP.DYN.LE00.IN)", "https://data.worldbank.org/indicator/SP.DYN.LE00.IN"),
    "oecd_health_statistics": ("OCDE · Health Statistics, gasto sanitario SHA (réplica DBnomics)", "https://db.nomics.world/OECD/DSD_SHA@DF_SHA"),
    "minsan_sisle_sns": ("Ministerio de Sanidad · SISLE-SNS, informes semestrales de listas de espera", "https://www.sanidad.gob.es/estadEstudios/estadisticas/inforRecopilaciones/listaEspera.htm"),
    "minsan_egsp": ("Ministerio de Sanidad · Estadística de Gasto Sanitario Público 2002-2024", "https://www.sanidad.gob.es/estadEstudios/estadisticas/inforRecopilaciones/gastoSanitario2005/home.htm"),
    "minsan_barometro": ("Ministerio de Sanidad y CIS · Barómetro Sanitario", "https://www.sanidad.gob.es/estadEstudios/estadisticas/inforRecopilaciones/barometro/home.htm"),
    "funcas_perfil_gasto": ("Funcas · perfil de gasto sanitario público por edad (DT 673/2012, tabla 15)", "https://www.funcas.es/wp-content/uploads/Migracion/Publicaciones/PDF/1791.pdf"),
    "who_gho": ("OMS · Global Health Observatory, gasto catastrófico (ODS 3.8.2)", "https://www.who.int/data/gho/data/indicators/indicator-details/GHO/proportion-of-population-with-household-expenditures-on-health-greater-than-10-of-total-household-expenditure-or-income-(sdg-3-8-2)-(-)"),
    "minsan_siap": ("Ministerio de Sanidad · Sistema de Información de Atención Primaria (SIAP), resumen 2023", "https://www.sanidad.gob.es/estadEstudios/estadisticas/docs/siap/Resumen_grafico_SIAP__Datos_2023.pdf"),
}


def r(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(float(value), digits)


class Store:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.provenance: dict[str, list[dict]] = defaultdict(list)

    def series(self, source_id: str, dataset_code: str, indicator_code: str, unit_code: str) -> dict[str, list[dict]]:
        """Latest release of an indicator as {series key or geography: [observation]}; deleted rows are dropped."""
        row = self.conn.execute(
            """
            SELECT r.indicator_release_id, r.source_url, r.source_content_sha256, r.source_snapshot_date,
                   r.source_metadata_json
            FROM indicator_definitions d JOIN indicator_releases r USING (indicator_id)
            WHERE d.source_id = ? AND d.dataset_code = ? AND d.indicator_code = ? AND d.unit_code = ?
            ORDER BY r.source_snapshot_date DESC, r.created_at DESC LIMIT 1
            """,
            (source_id, dataset_code, indicator_code, unit_code),
        ).fetchone()
        if row is None:
            raise LookupError(f"indicator {source_id}:{dataset_code}:{indicator_code}:{unit_code} not loaded")
        release_id, url, sha, snapshot, meta = row
        self.last_release = release_id
        self.provenance[source_id].append({
            "indicator": f"{dataset_code} {indicator_code} ({unit_code})", "url": url, "sha256": sha,
            "snapshot_date": snapshot, "retrieved_at": json.loads(meta or "{}").get("retrieved_at"),
        })
        out: dict[str, list[dict]] = defaultdict(list)
        for geo, name, dims, period, value, status, labels in self._observations(release_id):
            key = geo if json.loads(dims).get("sex") in (None, "T") else f"{geo}:{json.loads(dims)['sex']}"
            point = {"period": period, "value": float(value), "name": name}
            if status:
                point["status"] = status
                point["labels"] = json.loads(labels)
            out[key].append(point)
        return out

    def cells(self, source_id: str, dataset_code: str, indicator_code: str, unit_code: str) -> list[dict]:
        """Latest release as flat rows with the series dimensions, for indicators whose series share one geography."""
        self.series(source_id, dataset_code, indicator_code, unit_code)  # records provenance, raises if missing
        release_id = self.last_release
        return [{"geo": geo, "name": name, "dims": json.loads(dims), "period": period, "value": float(value)}
                for geo, name, dims, period, value, _, _ in self._observations(release_id)]

    def _observations(self, release_id: str) -> list[tuple]:
        return self.conn.execute(
            """
            SELECT s.geography_code, s.geography_name, s.dimensions_json, o.period_label, o.value_decimal,
                   o.source_status_code, o.source_status_labels_json
            FROM indicator_observation_versions o JOIN indicator_series_versions s USING (indicator_series_version_id)
            WHERE o.indicator_release_id = ? AND o.revision_state != 'deleted' AND o.value_decimal IS NOT NULL
            ORDER BY s.geography_code, o.period_start
            """,
            (release_id,),
        ).fetchall()


def annual_points(rows: list[dict], digits: int = 2, since: int | None = None, flags: bool = False) -> list[dict]:
    out = []
    for p in rows:
        year = int(p["period"])
        if since is not None and year < since:
            continue
        point = {"year": year, "value": r(p["value"], digits)}
        if flags and p.get("status"):
            point["status"] = p["status"]
        out.append(point)
    return out


def rank(values: dict[str, float], code: str) -> dict:
    ordered = sorted(values.items(), key=lambda kv: -kv[1])
    position = next(i for i, (c, _) in enumerate(ordered, start=1) if c == code)
    return {"position": position, "of": len(ordered)}


def life_expectancy(store: Store) -> dict:
    eurostat = store.series("eurostat_sdmx", "demo_mlexpec", "YR.T.Y_LT1", "YR")
    ine = store.series("ine_wstempus", "IDB_1414", "esperanza_vida_nacimiento", "YR")
    owid = store.series("owid_grapher", "life-expectancy", "life_expectancy_0", "YR")
    wb = store.series("worldbank_wdi", "WDI", "SP.DYN.LE00.IN", "YR")
    # World ranking: the latest year in which at least 95% of the countries with any value report.
    years = defaultdict(dict)
    names = {}
    for code, rows in wb.items():
        names[code] = rows[0]["name"]
        for p in rows:
            years[int(p["period"])][code] = p["value"]
    n_countries = len(wb)
    rank_year = max(y for y, v in years.items() if len(v) >= 0.95 * n_countries)
    world = years[rank_year]
    ordered = sorted(world.items(), key=lambda kv: -kv[1])
    oecd = {c: v for c, v in world.items() if c in OECD_MEMBERS}
    return {
        "long_run": {code: annual_points(owid[code], 1, since=FIRST_YEAR) for code in PEERS_ISO3 if code in owid},
        "eurostat": {geo: annual_points(eurostat[geo], 1, flags=True) for geo in PEERS_NUTS if geo in eurostat},
        "ine": {
            "total": annual_points(ine["ESP"], 2),
            "men": annual_points(ine["ESP:M"], 2),
            "women": annual_points(ine["ESP:F"], 2),
        },
        "world": {
            "year": rank_year, "countries": len(world), "spain_rank": rank(world, "ESP"), "oecd_rank": rank(oecd, "ESP"),
            "top": [{"code": c, "name": names[c], "value": r(v, 1), "oecd": c in OECD_MEMBERS} for c, v in ordered[:15]],
            "spain": r(world["ESP"], 1),
            "oecd_members": [{"code": c, "name": names[c], "value": r(v, 1)} for c, v in sorted(oecd.items(), key=lambda kv: -kv[1])],
        },
    }


def oecd_mean(by_area: dict[str, list[dict]]) -> list[dict]:
    per_year: dict[int, list[float]] = defaultdict(list)
    for area in OECD_MEMBERS:
        for p in by_area.get(area, []):
            per_year[int(p["period"])].append(p["value"])
    return [{"year": y, "value": r(sum(v) / len(v)), "n": len(v)} for y, v in sorted(per_year.items()) if len(v) >= MIN_OECD_REPORTING]


def spending(store: Store) -> dict:
    sha = "DSD_SHA@DF_SHA"
    pct_gdp = store.series("oecd_health_statistics", sha, "EXP_HEALTH.HF1._Z", "PT_B1GQ")
    pct_gdp_total = store.series("oecd_health_statistics", sha, "EXP_HEALTH._T._Z", "PT_B1GQ")
    per_person_ppp = store.series("oecd_health_statistics", sha, "EXP_HEALTH.HF1.Q", "EUR_PPP_PS")
    per_person_eur = store.series("oecd_health_statistics", sha, "EXP_HEALTH.HF1.Q", "XDC_PS")
    oop_share = store.series("oecd_health_statistics", sha, "EXP_HEALTH.HF3._Z", "PT_EXP_HLTH")
    eu_pct = store.series("eurostat_sdmx", "hlth_sha11_hf", "HF1.PC_GDP", "PC_GDP")
    eu_pps = store.series("eurostat_sdmx", "hlth_sha11_hf", "HF1.PPS_HAB", "PPS_HAB")
    eu_oop = store.series("eurostat_sdmx", "hlth_sha11_hf", "HF3.PC_CHE", "PC_CHE")
    egsp = store.series("minsan_egsp", "EGSP", "gasto_sanitario_ccaa_por_habitante", "EUR_HAB")

    def latest_common(series: dict[str, list[dict]], members: list[str]) -> tuple[int, dict[str, float]]:
        years = defaultdict(dict)
        for code in members:
            for p in series.get(code, []):
                years[int(p["period"])][code] = p["value"]
        year = max(y for y, v in years.items() if "ESP" in v and len(v) >= MIN_OECD_REPORTING)
        return year, years[year]

    pc_year, pc_values = latest_common(per_person_ppp, OECD_MEMBERS)
    gdp_year, gdp_values = latest_common(pct_gdp, OECD_MEMBERS)
    eg_last = max(int(p["period"]) for p in egsp["ES-CCAA"])
    regions = sorted(
        ({"code": code, "name": rows[0]["name"], "value": next(p["value"] for p in rows if int(p["period"]) == eg_last),
          "first": rows[0]["value"]}
         for code, rows in egsp.items() if code != "ES-CCAA"),
        key=lambda row: -row["value"],
    )
    return {
        "pct_gdp_public": {area: annual_points(pct_gdp[area], 2, flags=True) for area in PEERS_ISO3},
        "pct_gdp_total_esp": annual_points(pct_gdp_total["ESP"], 2, flags=True),
        "pct_gdp_public_oecd_mean": oecd_mean(pct_gdp),
        "per_person_ppp_public": {area: annual_points(per_person_ppp[area], 0, flags=True) for area in PEERS_ISO3},
        "per_person_ppp_public_oecd_mean": oecd_mean(per_person_ppp),
        "per_person_eur2020_public_esp": annual_points(per_person_eur["ESP"], 0, flags=True),
        "oop_share_esp_long": annual_points(oop_share["ESP"], 1, flags=True),
        "eurostat_pct_gdp_public": {geo: annual_points(eu_pct[geo], 2, flags=True) for geo in PEERS_NUTS if geo in eu_pct},
        "eurostat_pps_public": {geo: annual_points(eu_pps[geo], 0, flags=True) for geo in PEERS_NUTS if geo in eu_pps},
        "eurostat_oop_share": {geo: annual_points(eu_oop[geo], 1, flags=True) for geo in PEERS_NUTS if geo in eu_oop},
        "oecd_rank_per_person": {"year": pc_year, **rank(pc_values, "ESP"), "spain": r(pc_values["ESP"], 0),
                                 "median": r(sorted(pc_values.values())[len(pc_values) // 2], 0)},
        "oecd_rank_pct_gdp": {"year": gdp_year, **rank(gdp_values, "ESP"), "spain": r(gdp_values["ESP"], 2),
                              "median": r(sorted(gdp_values.values())[len(gdp_values) // 2], 2)},
        "regions_per_person": {"year": eg_last, "first_year": int(egsp["ES-CCAA"][0]["period"]),
                               "total": r(next(p["value"] for p in egsp["ES-CCAA"] if int(p["period"]) == eg_last), 0),
                               "provisional": any(p.get("status") == "p" for p in egsp["ES-CCAA"] if int(p["period"]) == eg_last),
                               "rows": regions},
    }


def cut_points(rows: list[dict], digits: int = 1) -> list[dict]:
    out = []
    for p in rows:
        point = {"date": p["period"], "value": r(p["value"], digits)}
        for label in p.get("labels", []):
            if label["code"] == "break":
                point.setdefault("breaks", []).append(label["label"])
            elif label["code"] == "rectified":
                point["rectified"] = {"initial": label["initial_value"], "label": label["label"]}
        out.append(point)
    return out


def waiting(store: Store) -> dict:
    def total(dataset: str, code: str, unit: str, digits: int = 1) -> list[dict]:
        return cut_points(store.series("minsan_sisle_sns", dataset, code, unit)["ES"], digits)

    surgery = {
        "mean_days": total("SISLE.surgery", "dias_medios_espera_quirurgica", "DAYS", 0),
        "rate_per_1000": total("SISLE.surgery", "tasa_espera_quirurgica", "P_THAB", 2),
        "pct_over_6_months": total("SISLE.surgery", "pct_mas_6_meses_quirurgica", "PC"),
        "patients": total("SISLE.surgery", "pacientes_espera_quirurgica", "PERSONS", 0),
    }
    consultations = {
        "mean_days": total("SISLE.consultations", "dias_medios_espera_consultas", "DAYS", 0),
        "rate_per_1000": total("SISLE.consultations", "tasa_espera_consultas", "P_THAB", 2),
        "pct_over_60_days": total("SISLE.consultations", "pct_mas_60_dias_consultas", "PC"),
    }
    region_days = store.series("minsan_sisle_sns", "SISLE.surgery_selected_by_region", "dias_medios_procesos_seleccionados", "DAYS")
    region_rate = store.series("minsan_sisle_sns", "SISLE.surgery_selected_by_region", "tasa_procesos_seleccionados", "P_THAB")
    regions = []
    for code, rows in sorted(region_days.items()):
        if code == "ES":
            continue
        regions.append({
            "code": code, "name": rows[0]["name"],
            "days": [{"date": p["period"], "value": r(p["value"], 0)} for p in rows],
            "rate": [{"date": p["period"], "value": r(p["value"], 2)} for p in region_rate[code]],
        })
    national_selected = [{"date": p["period"], "value": r(p["value"], 0)} for p in region_days["ES"]]
    def breaks(series: dict) -> list[dict]:
        found = sorted({(p["date"], b) for rows in series.values() for p in rows for b in p.get("breaks", [])})
        return [{"date": d, "label": b} for d, b in found]

    return {"surgery": surgery, "consultations": consultations,
            "breaks": {"surgery": breaks(surgery), "consultations": breaks(consultations)},
            "regions_selected": regions, "national_selected_days": national_selected}


def doctors(store: Store) -> dict:
    practising = store.series("eurostat_sdmx", "hlth_rs_prs2", "PHYS.PRACT.P_HTHAB", "P_HTHAB")
    licensed = store.series("eurostat_sdmx", "hlth_rs_prs2", "PHYS.LIC.P_HTHAB", "P_HTHAB")
    gp = store.series("eurostat_sdmx", "hlth_rs_physcat", "GEN_PRAC.P_HTHAB", "P_HTHAB")
    spec = store.series("eurostat_sdmx", "hlth_rs_physcat", "SPEC.P_HTHAB", "P_HTHAB")
    paed = store.series("eurostat_sdmx", "hlth_rs_physcat", "PAED.P_HTHAB", "P_HTHAB")
    geos = ["ES", "DE", "FR", "IT", "PT"]
    return {
        "practising": {g: annual_points(practising[g], 0, flags=True) for g in geos if g in practising},
        "licensed_pt": annual_points(licensed.get("PT", []), 0, flags=True),
        "gp": {g: annual_points(gp[g], 1, flags=True) for g in geos if g in gp},
        "specialists": {g: annual_points(spec[g], 0, flags=True) for g in geos if g in spec},
        "paediatricians": {g: annual_points(paed[g], 1, flags=True) for g in geos if g in paed},
    }


def latest(rows: list[dict]) -> dict | None:
    return {"year": int(rows[-1]["period"]), "value": rows[-1]["value"]} if rows else None


def spearman(xs: list[float], ys: list[float]) -> float:
    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda i: values[i])
        out = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            for k in range(i, j + 1):
                out[order[k]] = (i + j) / 2
            i = j + 1
        return out
    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    return cov / ((sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5)


def outcomes(store: Store) -> dict:
    hly = store.series("eurostat_sdmx", "hlth_hlye", "HLY_Y0.T.YR", "YR")
    hly65 = store.series("eurostat_sdmx", "hlth_hlye", "HLY_Y65.T.YR", "YR")
    le0 = store.series("eurostat_sdmx", "hlth_hlye", "LE_Y0.T.YR", "YR")
    trt = store.series("eurostat_sdmx", "hlth_cd_apr", "TRT.T.TOTAL.RT", "RT")
    prvt = store.series("eurostat_sdmx", "hlth_cd_apr", "PRVT.T.TOTAL.RT", "RT")
    cancers = {
        "breast": store.series("oecd_health_statistics", "DSD_HCQO@DF_HCQO", "CCBRNTSR.F", "PC"),
        "colon": store.series("oecd_health_statistics", "DSD_HCQO@DF_HCQO", "CCCLNTSR._T", "PC"),
        "lung": store.series("oecd_health_statistics", "DSD_HCQO@DF_HCQO", "CCLUNTSR._T", "PC"),
    }
    return {
        "hly": {g: annual_points(hly[g], 1, flags=True) for g in PEERS_NUTS if g in hly},
        "hly_le": {g: annual_points(le0[g], 1, flags=True) for g in PEERS_NUTS if g in le0},
        "hly65": {g: latest(hly65[g]) for g in PEERS_NUTS if g in hly65},
        "treatable": {g: annual_points(trt[g], 1, flags=True) for g in PEERS_NUTS if g in trt},
        "preventable": {g: annual_points(prvt[g], 1, flags=True) for g in PEERS_NUTS if g in prvt},
        "cancer_survival": {k: {g: annual_points(v[g], 1) for g in PEERS_ISO3 if g in v} for k, v in cancers.items()},
    }


def ageing(store: Store) -> dict:
    p65 = store.series("eurostat_sdmx", "demo_pjanind", "PC_Y65_MAX", "PC")
    p80 = store.series("eurostat_sdmx", "demo_pjanind", "PC_Y80_MAX", "PC")
    return {"over65": {g: annual_points(p65[g], 1, flags=True) for g in PEERS_NUTS if g in p65},
            "over80": {g: annual_points(p80[g], 1, flags=True) for g in PEERS_NUTS if g in p80}}


def workforce(store: Store) -> dict:
    nurses = store.series("eurostat_sdmx", "hlth_rs_prs2", "NRS.PRACT.P_HTHAB", "P_HTHAB")
    doctors = store.series("eurostat_sdmx", "hlth_rs_prs2", "PHYS.PRACT.P_HTHAB", "P_HTHAB")
    total = store.series("eurostat_sdmx", "hlth_rs_phys", "TOTAL.T.NR", "NR")
    older = [store.series("eurostat_sdmx", "hlth_rs_phys", f"{age}.T.NR", "NR") for age in ("Y55-64", "Y65-74", "Y_GE75")]
    ratio, share55 = {}, {}
    for g in ("ES", "DE", "FR", "IT", "PT"):
        n = {int(p["period"]): p["value"] for p in nurses.get(g, [])}
        d = {int(p["period"]): p["value"] for p in doctors.get(g, [])}
        common = sorted(set(n) & set(d))
        if common:
            ratio[g] = {"year": common[-1], "value": r(n[common[-1]] / d[common[-1]]), "nurses": r(n[common[-1]], 0), "doctors": r(d[common[-1]], 0)}
        t = {int(p["period"]): p["value"] for p in total.get(g, [])}
        o = [{int(p["period"]): p["value"] for p in part.get(g, [])} for part in older]
        pts = [{"year": y, "value": r(100 * sum(part.get(y, 0) for part in o) / t[y], 1)}
               for y in sorted(t) if t[y] and all(y in part for part in o[:2])]
        if pts:
            share55[g] = pts
    siap = {}
    units = {"pct_medicos_familia_mas_1500": "PC"}
    for code in ("poblacion_por_medico_familia", "poblacion_por_pediatra", "poblacion_por_enfermera_ap", "pct_medicos_familia_mas_1500"):
        point = store.series("minsan_siap", "SIAP.resumen_grafico", code, units.get(code, "PERSONS"))["ES"][-1]
        raw = store.conn.execute(
            """
            SELECT o.raw_value_json FROM indicator_definitions d JOIN indicator_releases r USING (indicator_id)
            JOIN indicator_observation_versions o USING (indicator_release_id)
            WHERE d.source_id = 'minsan_siap' AND d.indicator_code = ? ORDER BY r.created_at DESC LIMIT 1
            """, (code,)).fetchone()
        cited = json.loads(raw[0])
        siap[code] = {"year": int(point["period"]), "value": point["value"], "page": cited.get("page"), "quote": cited.get("quote")}
    return {
        "nurses": {g: annual_points(nurses[g], 0, flags=True) for g in ("ES", "DE", "FR", "IT", "PT") if g in nurses},
        "nurses_per_doctor": ratio, "doctors_55plus_share": share55, "siap": siap,
    }


def insurance(store: Store) -> dict:
    total = store.series("oecd_health_statistics", "DSD_HEALTH_PROT@DF_HEALTH_PROT", "HIC.PHINTPHI", "PT_POP")
    dup = store.series("oecd_health_statistics", "DSD_HEALTH_PROT@DF_HEALTH_PROT", "HIC.PHINDUPI", "PT_POP")
    return {"voluntary": {g: annual_points(total[g], 1, flags=True) for g in PEERS_ISO3 if g in total},
            "duplicate_esp": annual_points(dup.get("ESP", []), 1)}


def primary_care(store: Store) -> dict:
    def series(code: str, unit: str) -> list[dict]:
        return annual_points(store.series("minsan_barometro", "BS.totales", code, unit)["ES"], 1)
    return {
        "same_day": series("pct_cita_mf_mismo_dia", "PC"), "next_day": series("pct_cita_mf_dia_siguiente", "PC"),
        "no_slot": series("pct_cita_mf_sin_hueco", "PC"), "mean_days": series("dias_medios_cita_mf", "DAYS"),
    }


def perception(store: Store) -> dict:
    worse = store.series("minsan_barometro", "BS.serie_1998_2025.P16", "pct_listas_empeoran", "PC")
    better = store.series("minsan_barometro", "BS.serie_1998_2025.P16", "pct_listas_mejoran", "PC")
    return {"worse": annual_points(worse["ES"], 1), "better": annual_points(better["ES"], 1),
            "worse_by_region": {g: latest(v) for g, v in worse.items() if g != "ES"}}


INTL_PROCEDURES = {"CM8151_8153": "Prótesis de cadera", "CM8154": "Prótesis de rodilla", "CM131_138": "Cataratas"}
ESP_PROCEDURES = {**INTL_PROCEDURES, "CM683_687_689": "Histerectomía"}


def waits_international(store: Store) -> dict:
    dataset = "DSD_HEALTH_PROC@DF_WAITING"
    out = {"procedures": {}, "spain_mean_on_list": {}}
    for code, label in INTL_PROCEDURES.items():
        series = store.series("oecd_health_statistics", dataset, f"WAIT_MEDIAN.{code}.WTSP", "DAYS")
        by_year: dict[int, dict[str, float]] = defaultdict(dict)
        wb_names = {g: rows[0]["name"] for g, rows in store.series("worldbank_wdi", "WDI", "SP.DYN.LE00.IN", "YR").items()}
        names = {}
        for g, rows in series.items():
            names[g] = wb_names.get(g, rows[0]["name"])
            for p in rows:
                by_year[int(p["period"])][g] = p["value"]
        year = max(y for y, v in by_year.items() if "ESP" in v and len(v) >= 8)
        rows = sorted(({"code": g, "name": names[g], "value": r(v, 0)} for g, v in by_year[year].items()), key=lambda x: -x["value"])
        out["procedures"][code] = {"label": label, "year": year, "rows": rows, "spain": annual_points(series["ESP"], 0),
                                   **rank({g: -v for g, v in by_year[year].items()}, "ESP")}
    for code, label in ESP_PROCEDURES.items():
        series = store.series("oecd_health_statistics", dataset, f"WAIT_MEAN.{code}.WTPA", "DAYS")
        out["spain_mean_on_list"][code] = {"label": label, "points": annual_points(series["ESP"], 0)}
    return out


def regions_side_by_side(store: Store, spend: dict, wait: dict, perc: dict) -> dict:
    le = store.series("ine_wstempus", "IDB_1448", "esperanza_vida_nacimiento_ccaa", "YR")
    spend_rows = {row["code"]: row["value"] for row in spend["regions_per_person"]["rows"]}
    last_cut = wait["regions_selected"][0]["days"][-1]["date"]
    rows = []
    for region in wait["regions_selected"]:
        days = next((p["value"] for p in region["days"] if p["date"] == last_cut), None)
        days18 = next((p["value"] for p in region["days"] if p["date"] == "2018-12-31"), None)
        rate = next((p["value"] for p in region["rate"] if p["date"] == last_cut), None)
        rows.append({
            "code": region["code"], "name": region["name"], "spend": spend_rows.get(region["code"]), "days": days,
            "days_2018": days18, "rate": rate, "life_expectancy": r(latest(le.get(region["code"], []))["value"], 2) if le.get(region["code"]) else None,
            "worse_pct": r(perc["worse_by_region"].get(region["code"], {}).get("value"), 1) if perc["worse_by_region"].get(region["code"]) else None,
        })
    complete = [row for row in rows if row["spend"] is not None]
    le_year = max(int(v[-1]["period"]) for v in le.values())
    return {
        "cut": last_cut, "spend_year": spend["regions_per_person"]["year"], "le_year": le_year,
        "rows": rows,
        "rho_spend_days": r(spearman([x["spend"] for x in complete], [x["days"] for x in complete])),
        "rho_spend_le": r(spearman([x["spend"] for x in complete], [x["life_expectancy"] for x in complete])),
        "rho_days_worse": r(spearman([x["days"] for x in complete if x["worse_pct"] is not None],
                                     [x["worse_pct"] for x in complete if x["worse_pct"] is not None])),
        "n": len(complete),
    }


EU_NAMES = {
    "AT": "Austria", "BE": "Bélgica", "BG": "Bulgaria", "CY": "Chipre", "CZ": "Chequia", "DE": "Alemania", "DK": "Dinamarca",
    "EE": "Estonia", "EL": "Grecia", "ES": "España", "FI": "Finlandia", "FR": "Francia", "HR": "Croacia", "HU": "Hungría",
    "IE": "Irlanda", "IT": "Italia", "LT": "Lituania", "LU": "Luxemburgo", "LV": "Letonia", "MT": "Malta", "NL": "Países Bajos",
    "PL": "Polonia", "PT": "Portugal", "RO": "Rumanía", "SE": "Suecia", "SI": "Eslovenia", "SK": "Eslovaquia",
}
STORY_TRAILS = ["ES", "DE", "FR", "IT", "PT"]


def data_vs_story(store: Store) -> dict:
    """«El dato mata el relato»: Spain among EU countries (spending vs treatable mortality, 2014 -> latest) and the
    regions (real spending vs selected-procedure waits, Dec 2018 -> Dec 2024, size = patients per 1,000)."""
    pps = {g: {int(p["period"]): p["value"] for p in v}
           for g, v in store.series("eurostat_sdmx", "hlth_sha11_hf", "HF1.PPS_HAB", "PPS_HAB").items()}
    trt = {g: {int(p["period"]): p["value"] for p in v}
           for g, v in store.series("eurostat_sdmx", "hlth_cd_apr", "TRT.T.TOTAL.RT", "RT").items()}
    eu = pps["EU27_2020"]
    common = [y for y in sorted(eu) if y in trt.get("EU27_2020", {}) and y in pps.get("ES", {}) and y in trt.get("ES", {})]
    first, last = common[0], common[-1]
    countries = []
    for g in EU_NAMES:
        if last not in pps.get(g, {}) or last not in trt.get(g, {}):
            continue
        row = {"code": g, "name": EU_NAMES[g], "x": r(100 * pps[g][last] / eu[last], 1), "y": r(trt[g][last], 1)}
        if g in STORY_TRAILS and first in pps[g] and first in trt[g]:
            row.update({"x0": r(100 * pps[g][first] / eu[first], 1), "y0": r(trt[g][first], 1)})
        countries.append(row)
    es = next(c for c in countries if c["code"] == "ES")
    eu_row = {"x": 100.0, "y": r(trt["EU27_2020"][last], 1), "x0": 100.0, "y0": r(trt["EU27_2020"][first], 1)}
    # Regions: EGSP (current euros) deflated with the price index the OCDE uses for Spain's health spending (V / Q).
    q = {int(p["period"]): p["value"] for p in store.series("oecd_health_statistics", "DSD_SHA@DF_SHA", "EXP_HEALTH.HF1.Q", "XDC_PS")["ESP"]}
    v = {int(p["period"]): p["value"] for p in store.series("oecd_health_statistics", "DSD_SHA@DF_SHA", "EXP_HEALTH.HF1.V", "XDC_PS")["ESP"]}
    egsp = {g: {int(p["period"]): p["value"] for p in rows}
            for g, rows in store.series("minsan_egsp", "EGSP", "gasto_sanitario_ccaa_por_habitante", "EUR_HAB").items()}
    days = store.series("minsan_sisle_sns", "SISLE.surgery_selected_by_region", "dias_medios_procesos_seleccionados", "DAYS")
    rate = store.series("minsan_sisle_sns", "SISLE.surgery_selected_by_region", "tasa_procesos_seleccionados", "P_THAB")
    y0, y1 = 2018, max(y for y in egsp["ES-CCAA"] if y in v and y in q)
    deflator = {y: v[y] / q[y] for y in (y0, y1)}
    cut0, cut1 = f"{y0}-12-31", f"{y1}-12-31"
    regions = []
    for code, rows in days.items():
        if code == "ES" or code not in egsp:
            continue
        d = {p["period"]: p["value"] for p in rows}
        rt = {p["period"]: p["value"] for p in rate[code]}
        if cut0 not in d or cut1 not in d:
            continue
        regions.append({
            "code": code, "name": rows[0]["name"],
            "x0": r(egsp[code][y0] / deflator[y0], 0), "x": r(egsp[code][y1] / deflator[y1], 0),
            "y0": d[cut0], "y": d[cut1], "size0": rt.get(cut0), "size": rt.get(cut1),
        })
    total = egsp["ES-CCAA"]
    return {
        "countries": {
            "first": first, "last": last, "rows": countries, "eu": eu_row, "spain": es,
            "rho": r(spearman([c["x"] for c in countries], [c["y"] for c in countries])),
            "lower_mortality": [c["name"] for c in countries if c["y"] < es["y"]],
            "cheaper_and_better": [c["name"] for c in countries if c["x"] < es["x"] and c["y"] < es["y"]],
        },
        "regions": {
            "from": y0, "to": y1, "rows": sorted(regions, key=lambda x: x["name"]),
            "deflator": {str(k): r(val, 4) for k, val in deflator.items()},
            "total": {"x0": r(total[y0] / deflator[y0], 0), "x": r(total[y1] / deflator[y1], 0)},
            "spend_up": sum(1 for x in regions if x["x"] > x["x0"]), "days_up": sum(1 for x in regions if x["y"] > x["y0"]),
            "rate_up": sum(1 for x in regions if (x["size"] or 0) > (x["size0"] or 0)), "n": len(regions),
            "rho_change": r(spearman([x["x"] / x["x0"] for x in regions], [x["y"] - x["y0"] for x in regions])),
            "rho_level": r(spearman([x["x"] for x in regions], [x["y"] for x in regions])),
        },
    }


def by_year(series: dict[str, list[dict]]) -> dict[str, dict[int, float]]:
    return {g: {int(p["period"]): p["value"] for p in v} for g, v in series.items()}


def patient_side(store: Store) -> dict:
    """Capacity lens: what the patient pays and what goes unmet, against household means."""
    hf3 = by_year(store.series("eurostat_sdmx", "hlth_sha11_hf", "HF3.MIO_EUR", "MIO_EUR"))
    cons = by_year(store.series("eurostat_sdmx", "nama_10_gdp", "P31_S14.CP_MEUR", "CP_MEUR"))
    pps = by_year(store.series("eurostat_sdmx", "hlth_sha11_hf", "HF3.PPS_HAB", "PPS_HAB"))
    share = {g: [{"year": y, "value": r(100 * hf3[g][y] / cons[g][y], 2)} for y in sorted(hf3.get(g, {})) if y in cons.get(g, {})]
             for g in PEERS_NUTS if g in hf3 and g in cons}
    pps_last = {g: {"year": max(v), "value": r(v[max(v)], 0)} for g, v in pps.items() if g in PEERS_NUTS}

    def unmet(dataset: str, code: str) -> dict[str, list[dict]]:
        return {g: annual_points(v, 1, flags=True) for g, v in store.series("eurostat_sdmx", dataset, code, "PC").items()}

    dental_q1 = unmet("hlth_silc_09", "TXP.QU1.Y_GE16.T.PC")
    dental_q5 = unmet("hlth_silc_09", "TXP.QU5.Y_GE16.T.PC")
    dental_total = unmet("hlth_silc_09", "TXP.TOTAL.Y_GE16.T.PC")
    year = max(p["year"] for p in dental_q1["ES"])
    dental_rows = sorted(
        ({"code": g, "name": EU_NAMES.get(g, "Media UE-27"), "poor": at_year(dental_q1[g], year), "rich": at_year(dental_q5.get(g, []), year)}
         for g in dental_q1 if at_year(dental_q1[g], year) is not None),
        key=lambda x: -x["poor"],
    )
    countries_only = [row for row in dental_rows if row["code"] != "EU27_2020"]
    med = {key: unmet("hlth_silc_08", f"{key}.TOTAL.Y_GE16.T.PC") for key in ("TXP_TFAR_WLIST", "TXP", "WLIST")}
    cata = store.series("who_gho", "GHO", "FINPROTECTION_CATA_TOT_10_POP", "PC_POP")
    cata25 = store.series("who_gho", "GHO", "FINPROTECTION_CATA_TOT_25_POP", "PC_POP")
    return {
        "oop_share_household_consumption": share,
        "oop_pps_per_person": pps_last,
        "dental_cost": {"year": year, "rows": dental_rows, "spain_rank": 1 + sum(1 for row in countries_only if row["poor"] > at_year(dental_q1["ES"], year)),
                        "of": len(countries_only), "spain_q1": {g: dental_q1[g] for g in PEERS_NUTS if g in dental_q1},
                        "spain_total": {g: dental_total[g] for g in PEERS_NUTS if g in dental_total}},
        "medical": {key: {g: v[g] for g in PEERS_NUTS if g in v} for key, v in med.items()},
        "catastrophic_10": {g: annual_points(v, 2) for g, v in cata.items()},
        "catastrophic_25": {g: annual_points(v, 2) for g, v in cata25.items()},
    }


def at_year(points: list[dict], year: int) -> float | None:
    return next((p["value"] for p in points if p["year"] == year), None)


def money_allocation(store: Store) -> dict:
    """Where the public health money goes: EGSP functions and inputs (Spain, 2002-2024) and providers vs peers."""
    func_rows = store.conn.execute(
        """
        SELECT json_extract(s.dimensions_json, '$.partida'), o.period_label, o.value_decimal
        FROM indicator_definitions d JOIN indicator_releases r USING (indicator_id)
        JOIN indicator_series_versions s USING (indicator_release_id)
        JOIN indicator_observation_versions o USING (indicator_series_version_id)
        WHERE d.source_id = 'minsan_egsp' AND d.dataset_code = 'EGSP.consolidado' AND d.indicator_code = ?
          AND r.indicator_release_id = (SELECT r2.indicator_release_id FROM indicator_releases r2 WHERE r2.indicator_id = d.indicator_id
                                        ORDER BY r2.source_snapshot_date DESC, r2.created_at DESC LIMIT 1)
          AND o.revision_state != 'deleted'
        """, ("clasificacion_funcional",)).fetchall()
    econ_rows = store.conn.execute(
        """
        SELECT json_extract(s.dimensions_json, '$.partida'), o.period_label, o.value_decimal
        FROM indicator_definitions d JOIN indicator_releases r USING (indicator_id)
        JOIN indicator_series_versions s USING (indicator_release_id)
        JOIN indicator_observation_versions o USING (indicator_series_version_id)
        WHERE d.source_id = 'minsan_egsp' AND d.dataset_code = 'EGSP.consolidado' AND d.indicator_code = ?
          AND r.indicator_release_id = (SELECT r2.indicator_release_id FROM indicator_releases r2 WHERE r2.indicator_id = d.indicator_id
                                        ORDER BY r2.source_snapshot_date DESC, r2.created_at DESC LIMIT 1)
          AND o.revision_state != 'deleted'
        """, ("clasificacion_economica",)).fetchall()
    store.series("minsan_egsp", "EGSP.consolidado", "clasificacion_funcional", "THS_EUR")  # provenance
    store.series("minsan_egsp", "EGSP.consolidado", "clasificacion_economica", "THS_EUR")

    def shares(rows: list, total_label: str) -> dict[str, list[dict]]:
        table: dict[str, dict[int, float]] = defaultdict(dict)
        for label, year, value in rows:
            table[label][int(year)] = float(value)
        total = table[total_label]
        return {label: [{"year": y, "value": r(100 * v / total[y], 1)} for y, v in sorted(vals.items())]
                for label, vals in table.items() if label not in ("TOTAL CONSOLIDADO", "GASTO TOTAL SECTORES")}, table

    func_shares, func_table = shares(func_rows, "TOTAL CONSOLIDADO")
    econ_shares, _ = shares(econ_rows, "GASTO TOTAL SECTORES")
    q = {int(p["period"]): p["value"] for p in store.series("oecd_health_statistics", "DSD_SHA@DF_SHA", "EXP_HEALTH.HF1.Q", "XDC_PS")["ESP"]}
    v = {int(p["period"]): p["value"] for p in store.series("oecd_health_statistics", "DSD_SHA@DF_SHA", "EXP_HEALTH.HF1.V", "XDC_PS")["ESP"]}

    def real_growth(label: str, y0: int, y1: int) -> float:
        a = func_table[label][y0] / (v[y0] / q[y0])
        b = func_table[label][y1] / (v[y1] / q[y1])
        return r(100 * (b / a - 1), 1)

    last = max(func_table["TOTAL CONSOLIDADO"])
    providers = {k: by_year(store.series("eurostat_sdmx", "hlth_sha11_hphf", f"{k}.HF1.PC_CHE", "PC_CHE")) for k in ("TOTAL", "HP1", "HP3", "HP5")}
    provider_rows = []
    for g in PEERS_NUTS:
        tot = {y: val for y, val in providers["TOTAL"].get(g, {}).items() if val and providers["HP1"].get(g, {}).get(y)}
        if not tot:
            continue
        y = max(tot)
        provider_rows.append({"code": g, "year": y, **{k: r(100 * providers[k][g].get(y, 0) / tot[y], 1) for k in ("HP1", "HP3", "HP5")}})
    return {
        "functional_shares": func_shares, "economic_shares": econ_shares, "last": last,
        "real_growth_2009": {label: real_growth(label, 2009, last) for label in ("Servicios hospitalarios y especializados", "Servicios primarios de salud", "Farmacia", "TOTAL CONSOLIDADO")},
        "providers": provider_rows,
    }


def pay_and_migration(store: Store) -> dict:
    out = {}
    for prof in ("EMPLGENP", "EMPLSPMP", "RINF"):
        ratio = store.series("oecd_health_statistics", "DSD_HEALTH_REAC_EMP@DF_REMUN", f"REMUN.{prof}", "RATIO_AVG_WAGE")
        ppp = store.series("oecd_health_statistics", "DSD_HEALTH_REAC_EMP@DF_REMUN", f"REMUN.{prof}", "USD_PPP")
        out[prof] = sorted(({"code": g, "name": rows[-1]["name"], "year": int(rows[-1]["period"]), "ratio": r(rows[-1]["value"]),
                             "ppp": r(next((p["value"] for p in ppp.get(g, []) if p["period"] == rows[-1]["period"]), None) or 0, 0),
                             "series": annual_points(rows, 2)}
                            for g, rows in ratio.items()), key=lambda x: -x["ratio"])
    abroad = store.series("oecd_health_statistics", "DSD_HEALTH_WFMI@DF_HEALTH_WFMI", "FOREIGN_TRAINED_IN_ESP.PHYS", "PS")
    wb_names = {g: rows[0]["name"] for g, rows in store.series("worldbank_wdi", "WDI", "SP.DYN.LE00.IN", "YR").items()}
    destinations = sorted(({"code": g, "name": wb_names.get(g, g), "year": int(rows[-1]["period"]), "value": r(rows[-1]["value"], 0)}
                           for g, rows in abroad.items() if rows), key=lambda x: -x["value"])
    in_spain = store.series("eurostat_sdmx", "hlth_rs_phys", "TOTAL.T.NR", "NR")["ES"][-1]
    return {"pay": out, "doctors_abroad": {"rows": destinations, "total": r(sum(x["value"] for x in destinations), 0),
                                           "doctors_in_spain": {"year": int(in_spain["period"]), "value": r(in_spain["value"], 0)}}}


AGE_BANDS = ["Y_LT5", "Y5-9", "Y10-14", "Y15-19", "Y20-24", "Y25-29", "Y30-34", "Y35-39", "Y40-44", "Y45-49", "Y50-54",
             "Y55-59", "Y60-64", "Y65-69", "Y70-74", "Y75-79", "Y_GE80"]
NUTS2_TO_INE = {"ES11": "12", "ES12": "03", "ES13": "06", "ES21": "16", "ES22": "15", "ES23": "17", "ES24": "02", "ES30": "13",
                "ES41": "07", "ES42": "08", "ES43": "11", "ES51": "09", "ES52": "10", "ES53": "04", "ES61": "01", "ES62": "14",
                "ES63": "18", "ES64": "19", "ES70": "05"}


def age_weights(store: Store) -> list[float]:
    """Relative cost per person by age band (Funcas DT 673/2012, table 15, 2008), in the order of AGE_BANDS."""
    store.series("funcas_perfil_gasto", "DT673_T15", "gasto_sanitario_publico_por_edad", "EUR1998_PER")  # provenance
    profile = store.conn.execute(
        """
        SELECT json_extract(s.dimensions_json, '$.age'), o.value_decimal
        FROM indicator_definitions d JOIN indicator_releases r USING (indicator_id)
        JOIN indicator_series_versions s USING (indicator_release_id)
        JOIN indicator_observation_versions o USING (indicator_series_version_id)
        WHERE d.source_id = 'funcas_perfil_gasto' AND o.period_label = '2008' AND o.revision_state != 'deleted'
        """
    ).fetchall()
    by_age = {age: float(v) for age, v in profile}
    order = ["0a4", "5a9", "10a14", "15a19", "20a24", "25a29", "30a34", "35a39", "40a44", "45a49", "50a54", "55a59",
             "60a64", "65a69", "70a74", "75a79", "80 y más"]
    total = by_age["total"]
    return [by_age[a] / total for a in order]


def need_index(store: Store, dataset: str) -> dict[str, dict[int, float]]:
    """Expected spending per person relative to Spain's 2008 average, given each place's age structure."""
    weights = age_weights(store)
    pops = {band: by_year(store.series("eurostat_sdmx", dataset, f"{band}.T.NR", "NR")) for band in AGE_BANDS}
    out: dict[str, dict[int, float]] = defaultdict(dict)
    geos = set.intersection(*(set(p) for p in pops.values()))
    for g in geos:
        years = set.intersection(*(set(pops[b][g]) for b in AGE_BANDS))
        for y in years:
            counts = [pops[b][g][y] for b in AGE_BANDS]
            total = sum(counts)
            if total:
                out[g][y] = sum(c / total * w for c, w in zip(counts, weights))
    return out


def age_adjusted(store: Store, story: dict, spend: dict) -> dict:
    need = need_index(store, "demo_pjangroup")
    pps = by_year(store.series("eurostat_sdmx", "hlth_sha11_hf", "HF1.PPS_HAB", "PPS_HAB"))
    eu = "EU27_2020"
    last = story["countries"]["last"]
    year = max(y for y in need["ES"] if y <= last and y in need[eu])
    adjusted = {}
    for row in story["countries"]["rows"]:
        g = row["code"]
        if g in need and year in need[g] and last in pps.get(g, {}):
            factor = need[eu][year] / need[g][year]
            adjusted[g] = {"raw": row["x"], "adjusted": r(row["x"] * factor, 1), "need": r(100 * need[g][year] / need[eu][year], 1)}
    es = adjusted["ES"]
    # Trails for the peers: adjust each end with its own year's age structure.
    first = story["countries"]["first"]
    y_first = min(y for y in need["ES"] if y >= first)
    for row in story["countries"]["rows"]:
        g = row["code"]
        if g in adjusted:
            row["x_raw"] = row["x"]
            row["x"] = adjusted[g]["adjusted"]
            if "x0" in row and y_first in need.get(g, {}):
                row["x0"] = r(row["x0"] * need[eu][y_first] / need[g][y_first], 1)
    adj_rows = [row for row in story["countries"]["rows"] if row["code"] in adjusted]
    story["countries"]["adjusted"] = True
    story["countries"]["rho"] = r(spearman([c["x"] for c in adj_rows], [c["y"] for c in adj_rows]))
    story["countries"]["spain"] = next(c for c in story["countries"]["rows"] if c["code"] == "ES")
    story["countries"]["cheaper_and_better"] = [c["name"] for c in adj_rows if c["x"] < story["countries"]["spain"]["x"] and c["y"] < story["countries"]["spain"]["y"]]
    story["countries"]["lower_mortality"] = [c["name"] for c in adj_rows if c["y"] < story["countries"]["spain"]["y"]]
    # Regions: real spending per person at Spain's age structure.
    rneed = need_index(store, "demo_r_pjangroup")
    ref = need["ES"]
    for row in story["regions"]["rows"]:
        nuts = next((k for k, v in NUTS2_TO_INE.items() if v == row["code"]), None)
        for key, yr in (("x0", story["regions"]["from"]), ("x", story["regions"]["to"])):
            y_pop = min((y for y in rneed.get(nuts, {}) if y >= yr), default=max(rneed.get(nuts, {0: 0})))
            if nuts in rneed and y_pop in rneed[nuts] and y_pop in ref:
                row[f"{key}_raw"] = row[key]
                row[key] = r(row[key] * ref[y_pop] / rneed[nuts][y_pop], 0)
    regions = story["regions"]["rows"]
    story["regions"]["adjusted"] = True
    story["regions"]["rho_level"] = r(spearman([x["x"] for x in regions], [x["y"] for x in regions]))
    story["regions"]["rho_change"] = r(spearman([x["x"] / x["x0"] for x in regions], [x["y"] - x["y0"] for x in regions]))
    story["regions"]["spend_up"] = sum(1 for x in regions if x["x"] > x["x0"])
    return {
        "year": year, "spain_raw": es["raw"], "spain_adjusted": es["adjusted"], "spain_need": es["need"],
        "rows": sorted(({"code": g, "name": EU_NAMES.get(g, g), **v} for g, v in adjusted.items()), key=lambda x: -x["adjusted"]),
        "profile_note": "Funcas DT 673/2012, tabla 15 (perfil español de 2008)",
    }


def regions_adjusted(store: Store, reg: dict, spend: dict) -> dict:
    need = need_index(store, "demo_pjangroup")
    rneed = need_index(store, "demo_r_pjangroup")
    year = spend["regions_per_person"]["year"]
    y_pop = min((y for y in need["ES"] if y >= year), default=max(need["ES"]))
    for row in reg["rows"]:
        nuts = next((k for k, v in NUTS2_TO_INE.items() if v == row["code"]), None)
        if row["spend"] is not None and nuts in rneed and y_pop in rneed[nuts]:
            row["spend_adjusted"] = r(row["spend"] * need["ES"][y_pop] / rneed[nuts][y_pop], 0)
            row["need"] = r(100 * rneed[nuts][y_pop] / need["ES"][y_pop], 1)
    complete = [row for row in reg["rows"] if row.get("spend_adjusted")]
    reg["rho_adj_spend_days"] = r(spearman([x["spend_adjusted"] for x in complete], [x["days"] for x in complete]))
    reg["rho_adj_spend_le"] = r(spearman([x["spend_adjusted"] for x in complete], [x["life_expectancy"] for x in complete]))
    reg["pop_year"] = y_pop
    return reg


def base_years(store: Store, money: dict) -> dict:
    func_rows = store.conn.execute(
        """
        SELECT json_extract(s.dimensions_json, '$.partida'), o.period_label, o.value_decimal
        FROM indicator_definitions d JOIN indicator_releases r USING (indicator_id)
        JOIN indicator_series_versions s USING (indicator_release_id)
        JOIN indicator_observation_versions o USING (indicator_series_version_id)
        WHERE d.source_id = 'minsan_egsp' AND d.dataset_code = 'EGSP.consolidado' AND d.indicator_code = 'clasificacion_funcional'
          AND o.revision_state != 'deleted'
        """).fetchall()
    table: dict[str, dict[int, float]] = defaultdict(dict)
    for label, year, value in func_rows:
        table[label][int(year)] = float(value)
    q = {int(p["period"]): p["value"] for p in store.series("oecd_health_statistics", "DSD_SHA@DF_SHA", "EXP_HEALTH.HF1.Q", "XDC_PS")["ESP"]}
    v = {int(p["period"]): p["value"] for p in store.series("oecd_health_statistics", "DSD_SHA@DF_SHA", "EXP_HEALTH.HF1.V", "XDC_PS")["ESP"]}
    labels = {"Servicios hospitalarios y especializados": "hosp", "Servicios primarios de salud": "prim", "Farmacia": "farm", "TOTAL CONSOLIDADO": "total"}
    real = {key: {y: table[label][y] / (v[y] / q[y]) for y in table[label] if y in v and y in q} for label, key in labels.items()}
    first = min(real["total"])
    index = {key: [{"year": y, "value": r(100 * val / vals[first], 1)} for y, val in sorted(vals.items())] for key, vals in real.items()}
    growth = {str(base): {key: r(100 * (vals[money["last"]] / vals[base] - 1), 1) for key, vals in real.items()} for base in (first, 2009, 2013)}
    return {"first": first, "index": index, "growth": growth}


def waits_per_older(store: Store, wait: dict) -> dict:
    p65 = by_year(store.series("eurostat_sdmx", "demo_pjanind", "PC_Y65_MAX", "PC"))["ES"]

    def per65(rows: list[dict], date: str) -> tuple[float, float, int]:
        rate = next(p["value"] for p in rows if p["date"] == date)
        year = int(date[:4]) + 1 if int(date[:4]) + 1 in p65 else int(date[:4])
        return rate, r(rate / (p65[year] / 100), 1), year

    out = {}
    for key, rows in (("surgery", wait["surgery"]["rate_per_1000"]), ("consultations", wait["consultations"]["rate_per_1000"])):
        a = per65(rows, "2018-12-31")
        b = per65(rows, rows[-1]["date"])
        out[key] = {"from": {"date": "2018-12-31", "rate": a[0], "per_1000_65": a[1], "share65_year": a[2], "share65": p65[a[2]]},
                    "to": {"date": rows[-1]["date"], "rate": b[0], "per_1000_65": b[1], "share65_year": b[2], "share65": p65[b[2]]},
                    "change_rate": r(100 * (b[0] / a[0] - 1), 1), "change_per65": r(100 * (b[1] / a[1] - 1), 1)}
    return out


def distribution(store: Store) -> dict:
    def unmet(dataset: str, code: str) -> dict[str, list[dict]]:
        return {g: annual_points(v, 1) for g, v in store.series("eurostat_sdmx", dataset, code, "PC").items()}
    med_q1 = unmet("hlth_silc_08", "TXP_TFAR_WLIST.QU1.Y_GE16.T.PC")
    med_q5 = unmet("hlth_silc_08", "TXP_TFAR_WLIST.QU5.Y_GE16.T.PC")
    year = max(p["year"] for p in med_q1["ES"])
    med_rows = sorted(({"code": g, "name": EU_NAMES.get(g, "Media UE-27"), "poor": at_year(med_q1[g], year), "rich": at_year(med_q5.get(g, []), year)}
                       for g in med_q1 if at_year(med_q1[g], year) is not None), key=lambda x: -x["poor"])
    epf = {}
    for unit in ("EUR_PER", "PC_BUDGET"):
        rows = store.conn.execute(
            """
            SELECT json_extract(s.dimensions_json, '$.quintil'), o.period_label, o.value_decimal
            FROM indicator_definitions d JOIN indicator_releases r USING (indicator_id)
            JOIN indicator_series_versions s USING (indicator_release_id)
            JOIN indicator_observation_versions o USING (indicator_series_version_id)
            WHERE d.dataset_code = 'EPF_75413' AND d.unit_code = ? AND o.revision_state != 'deleted'
            """, (unit,)).fetchall()
        table: dict[str, dict[int, float]] = defaultdict(dict)
        for quint, year_, value in rows:
            table[quint][int(year_)] = float(value)
        epf[unit] = {k: [{"year": y, "value": r(v, 2)} for y, v in sorted(vals.items())] for k, vals in table.items()}
    store.series("ine_wstempus", "EPF_75413", "gasto_sanidad_hogares_quintil", "EUR_PER")
    edu_rows = store.conn.execute(
        """
        SELECT json_extract(s.dimensions_json, '$.age'), json_extract(s.dimensions_json, '$.education'), o.period_label, o.value_decimal
        FROM indicator_definitions d JOIN indicator_releases r USING (indicator_id)
        JOIN indicator_series_versions s USING (indicator_release_id)
        JOIN indicator_observation_versions o USING (indicator_series_version_id)
        WHERE d.dataset_code = 'TM_37663' AND d.indicator_code = 'esperanza_vida_nivel_educativo' AND o.revision_state != 'deleted'
        """).fetchall()
    store.series("ine_wstempus", "TM_37663", "esperanza_vida_nivel_educativo", "YR")
    edu: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for age, level, year_, value in edu_rows:
        edu[age][level].append({"year": int(year_), "value": r(float(value), 2)})
    for age in edu:
        for level in edu[age]:
            edu[age][level].sort(key=lambda p: p["year"])
    eu_edu = {}
    for level in ("ED0-2", "ED5-8"):
        for g, rows in store.series("eurostat_sdmx", "demo_mlexpecedu", f"{level}.Y30.T.YR", "YR").items():
            eu_edu.setdefault(g, {})[level] = latest(rows)
    peers_gap = sorted(({"code": g, "name": EU_NAMES.get(g, g), "year": v["ED5-8"]["year"], "gap": r(v["ED5-8"]["value"] - v["ED0-2"]["value"], 1)}
                        for g, v in eu_edu.items() if "ED5-8" in v and "ED0-2" in v and v["ED5-8"] and v["ED0-2"] and g != "EU27_2020"),
                       key=lambda x: -x["gap"])
    return {"medical": {"year": year, "rows": med_rows}, "epf": epf,
            "life_expectancy_education": {age: dict(levels) for age, levels in edu.items()}, "education_gap_peers": peers_gap}


BS_CROSS = ("minsan_barometro", "BS.cruces_2025")
DENT_AGES = ["Y16-24", "Y25-34", "Y35-44", "Y45-64", "Y_GE65", "Y_GE75"]
DENT_AGE_LABELS = {"Y16-24": "16–24", "Y25-34": "25–34", "Y35-44": "35–44", "Y45-64": "45–64", "Y_GE65": "65+", "Y_GE75": "75+",
                   "Y_GE16": "16+"}
QUINTS = ["QU1", "QU2", "QU3", "QU4", "QU5"]


def moe95(pct: float, n: float) -> float:
    """Half-width of a 95 % interval under simple random sampling, as the Barómetro's ficha técnica computes it."""
    p = pct / 100
    return r(196 * math.sqrt(p * (1 - p) / n), 1)


def segments(store: Store, wait: dict, regions: dict) -> dict:
    """Groups instead of the average person: the gaps panel, the per-group tables and the shared typical cases.

    Barómetro groups come from one-variable cross sheets, so a typical case combines marginal cuts; the page says so.
    """
    def cross(code: str, unit: str = "PC") -> dict[str, dict[str, float]]:
        out: dict[str, dict[str, float]] = defaultdict(dict)
        for row in store.cells(*BS_CROSS, code, unit):
            out[row["dims"]["breakdown"]][row["dims"]["group"]] = row["value"]
        return out
    bs = {code: cross(code) for code in ("pct_cita_mf_mismo_dia", "pct_cita_mf_dia_siguiente", "pct_especialista_solo_privada",
                                         "pct_necesidad_salud_mental", "pct_salud_mental_seguro_privado",
                                         "pct_salud_mental_privado_sin_seguro")}
    bs_n = {code: cross(code, "N") for code in ("n_cita_mf", "n_especialista", "n_necesidad_salud_mental", "n_salud_mental_atendidos")}

    def bs_group(kind: str, breakdown: str, group: str) -> dict:
        codes, n_code = {
            "gp_quick": (("pct_cita_mf_mismo_dia", "pct_cita_mf_dia_siguiente"), "n_cita_mf"),
            "specialist_private": (("pct_especialista_solo_privada",), "n_especialista"),
            "mental_need": (("pct_necesidad_salud_mental",), "n_necesidad_salud_mental"),
            "mental_private": (("pct_salud_mental_seguro_privado", "pct_salud_mental_privado_sin_seguro"), "n_salud_mental_atendidos"),
        }[kind]
        value = sum(bs[c][breakdown][group] for c in codes)
        n = bs_n[n_code][breakdown][group]
        return {"value": r(value, 1), "n": r(n, 0), "moe": moe95(value, n)}

    # Every sheet carries the same groups for every question, so the GP block lists them for all four tables.
    groups = {breakdown: list(by_group) for breakdown, by_group in bs["pct_cita_mf_mismo_dia"].items() if breakdown != "total"}
    tables = {kind: {breakdown: [{"group": g, **bs_group(kind, breakdown, g)} for g in names] for breakdown, names in groups.items()}
              for kind in ("gp_quick", "specialist_private", "mental_need", "mental_private")}
    nat = {kind: bs_group(kind, "total", "TOTAL") for kind in tables}

    def silc(dataset: str, code: str) -> list[dict]:
        return annual_points(store.series("eurostat_sdmx", dataset, code, "PC").get("ES", []), 1)
    med = {q: silc("hlth_silc_08", f"TXP_TFAR_WLIST.{q}.Y_GE16.T.PC") for q in ("QU1", "QU5", "TOTAL")}
    dental: dict[str, dict[str, list[dict]]] = defaultdict(dict)
    for q in ["TOTAL", *QUINTS]:
        for age in [*DENT_AGES, "Y_GE16"]:
            dental[q][age] = silc("hlth_silc_09", f"TXP.{q}.{age}.T.PC")
    year = max(p["year"] for p in dental["QU1"]["Y45-64"])
    med_year = max(p["year"] for p in med["QU1"])
    d = lambda q, age: at_year(dental[q][age], year)  # noqa: E731
    dental_grid = {"year": year, "ages": [*DENT_AGES, "Y_GE16"], "age_labels": DENT_AGE_LABELS, "quintiles": ["TOTAL", *QUINTS],
                   "values": {q: {age: d(q, age) for age in [*DENT_AGES, "Y_GE16"]} for q in ["TOTAL", *QUINTS]}}
    peak_age = max(DENT_AGES, key=lambda age: d("QU1", age) or 0)

    edu: dict[tuple[str, str, str], float] = {}
    edu_year = None
    for row in store.cells("ine_wstempus", "TM_37663", "esperanza_vida_nivel_educativo_sexo", "YR"):
        edu_year = max(edu_year or 0, int(row["period"]))
    for row in store.cells("ine_wstempus", "TM_37663", "esperanza_vida_nivel_educativo_sexo", "YR"):
        if int(row["period"]) == edu_year:
            edu[(row["dims"]["age"], row["dims"]["sex_es"], row["dims"]["education"])] = r(row["value"], 2)
    totals_rows = store.conn.execute(
        """
        SELECT json_extract(s.dimensions_json, '$.age'), o.value_decimal
        FROM indicator_definitions d JOIN indicator_releases r USING (indicator_id)
        JOIN indicator_series_versions s USING (indicator_release_id)
        JOIN indicator_observation_versions o USING (indicator_series_version_id)
        WHERE d.dataset_code = 'TM_37663' AND d.indicator_code = 'esperanza_vida_nivel_educativo'
          AND json_extract(s.dimensions_json, '$.education') = 'total' AND o.period_label = ? AND o.revision_state != 'deleted'
        """, (str(edu_year),)).fetchall()
    le_total = {age: r(float(v), 2) for age, v in totals_rows}
    le_edu_sex = {"year": edu_year, "values": {f"{a}|{s}|{e}": v for (a, s, e), v in sorted(edu.items())}, "total": le_total,
                  "gap_30": r(edu[("30 años", "F", "superior")] - edu[("30 años", "M", "primaria")], 1)}

    days = {row["code"]: row["days"] for row in regions["rows"]}
    region_names = {row["code"]: row["name"] for row in regions["rows"]}
    nat_days = next(p["value"] for p in wait["national_selected_days"] if p["date"] == regions["cut"])
    bs_ccaa = {"01": "Andalucía", "08": "Castilla-La Mancha", "13": "Madrid (Comunidad de)"}

    village, city = "Menos o igual a 2.000 habitantes", "Más de 1.000.000 habitantes"
    gaps = [
        {"id": "medico", "label": "Médico: renuncia por coste, distancia o lista de espera", "dimension": "renta",
         "a": {"label": "20 % con menos ingresos", "value": at_year(med["QU1"], med_year)},
         "b": {"label": "20 % con más ingresos", "value": at_year(med["QU5"], med_year)},
         "national": at_year(med["TOTAL"], med_year), "source": f"Eurostat hlth_silc_08, {med_year}, 16 años o más"},
        {"id": "dentista", "label": "Dentista: renuncia por ser demasiado caro", "dimension": "renta",
         "a": {"label": "20 % con menos ingresos", "value": d("QU1", "Y_GE16")},
         "b": {"label": "20 % con más ingresos", "value": d("QU5", "Y_GE16")},
         "peak": {"label": f"20 % con menos ingresos de {DENT_AGE_LABELS[peak_age]} años", "value": d("QU1", peak_age)},
         "national": d("TOTAL", "Y_GE16"), "source": f"Eurostat hlth_silc_09, {year}, 16 años o más"},
        {"id": "especialista", "label": "Especialista: fue solo a la sanidad privada", "dimension": "renta",
         "a": {"label": "Clase alta y media alta", **bs_group("specialist_private", "clase", "Clase alta y media alta")},
         "b": {"label": "Clase baja o pobre", **bs_group("specialist_private", "clase", "Clase baja/pobre")},
         "national": nat["specialist_private"]["value"], "source": "Barómetro Sanitario 2025, clase social autodeclarada, 18 años o más"},
        {"id": "salud_mental", "label": "Salud mental: atendido en la privada (con seguro o pagando)", "dimension": "edad",
         "a": {"label": "18 a 24 años", **bs_group("mental_private", "edad", "De 18 a 24 años")},
         "b": {"label": "65 a 74 años", **bs_group("mental_private", "edad", "De 65 a 74 años")},
         "national": nat["mental_private"]["value"], "source": "Barómetro Sanitario 2025, de quienes necesitaron atención"},
        {"id": "cita_mf", "label": "Médico de familia: le atendió el mismo día o al siguiente", "dimension": "territorio",
         "a": {"label": "Municipios de hasta 2.000 habitantes", **bs_group("gp_quick", "municipio", village)},
         "b": {"label": "Municipios de más de un millón", **bs_group("gp_quick", "municipio", city)},
         "national": nat["gp_quick"]["value"], "source": "Barómetro Sanitario 2025, de quienes consultaron"},
    ]

    def item(label: str, value: float | None, national: float | None, unit: str, cut: str, source: str, moe: float | None = None,
             note: str | None = None) -> dict:
        out = {"label": label, "value": value, "national": national, "unit": unit, "cut": cut, "source": source}
        if moe is not None:
            out["moe"] = moe
        if note:
            out["note"] = note
        return out

    def bs_item(label: str, kind: str, breakdown: str, group: str, cut: str) -> dict:
        g = bs_group(kind, breakdown, group)
        return item(label, g["value"], nat[kind]["value"], "pct", cut, "Barómetro Sanitario 2025", g["moe"])

    def wait_item(code: str) -> dict:
        return item("Espera media para operarse (procesos más comunes)", days[code], nat_days, "days", region_names[code],
                    f"SISLE, {regions['cut'][:4]}")
    cases = [
        {"id": "persona-1", "name": "Lucía", "who": "25–29 años, asalariada, vive sola de alquiler en la ciudad de Madrid",
         "items": [
             bs_item("Necesitó atención de salud mental en el último año", "mental_need", "edad", "De 25 a 34 años", "personas de 25 a 34 años"),
             bs_item("De ellas, atendidas en la privada", "mental_private", "edad", "De 25 a 34 años", "personas de 25 a 34 años"),
             bs_item("Su médico de familia la atiende el mismo día o al siguiente", "gp_quick", "municipio", city, "municipios de más de un millón de habitantes"),
             item("Renuncia al dentista por ser demasiado caro", d("TOTAL", "Y25-34"), d("TOTAL", "Y_GE16"), "pct", "personas de 25 a 34 años",
                  f"Eurostat hlth_silc_09, {year}", note=f"{num_es(d('QU1', 'Y25-34'))} % si está en el 20 % con menos ingresos"),
             wait_item("13"),
         ]},
        {"id": "persona-3", "name": "Antonio", "who": "45–64 años, estudios primarios, trabajador manual en Andalucía",
         "items": [
             item("Esperanza de vida a los 30 años", edu[("30 años", "M", "primaria")], le_total["30 años"], "years",
                  "hombres con estudios primarios o menos", f"INE, tabla 37663, {edu_year}"),
             item("Renuncia al dentista por ser demasiado caro", d("QU1", "Y45-64"), d("TOTAL", "Y_GE16"), "pct",
                  "45 a 64 años del 20 % con menos ingresos (cruce observado)", f"Eurostat hlth_silc_09, {year}"),
             bs_item("Su médico de familia le atiende el mismo día o al siguiente", "gp_quick", "comunidad", bs_ccaa["01"], "Andalucía"),
             wait_item("01"),
         ]},
        {"id": "persona-4", "name": "Carmen", "who": "65 años o más, pensionista, propietaria sin hipoteca en un pueblo de Castilla-La Mancha",
         "items": [
             bs_item("Su médico de familia la atiende el mismo día o al siguiente", "gp_quick", "municipio", village, "municipios de hasta 2.000 habitantes"),
             wait_item("08"),
             item("Renuncia al dentista por ser demasiado caro", d("TOTAL", "Y_GE65"), d("TOTAL", "Y_GE16"), "pct", "personas de 65 años o más",
                  f"Eurostat hlth_silc_09, {year}", note=f"{num_es(d('QU1', 'Y_GE65'))} % si está en el 20 % con menos ingresos"),
             item("Años que le quedan por vivir a los 65", edu[("65 años", "F", "primaria")], le_total["65 años"], "years",
                  "mujeres con estudios primarios o menos", f"INE, tabla 37663, {edu_year}"),
         ]},
        {"id": "persona-5", "name": "Laura", "who": "45–54 años, universitaria, profesional en Madrid",
         "items": [
             bs_item("Fue al especialista solo en la privada", "specialist_private", "clase", "Clase alta y media alta", "clase alta y media alta (autodeclarada)"),
             item("Esperanza de vida a los 30 años", edu[("30 años", "F", "superior")], le_total["30 años"], "years",
                  "mujeres con estudios superiores", f"INE, tabla 37663, {edu_year}"),
             item("Renuncia al dentista por ser demasiado caro", d("QU5", "Y45-64"), d("TOTAL", "Y_GE16"), "pct",
                  "45 a 64 años del 20 % con más ingresos (cruce observado)", f"Eurostat hlth_silc_09, {year}"),
             wait_item("13"),
         ]},
    ]
    return {"gaps": gaps, "tables": tables, "national": nat, "dental_grid": dental_grid, "life_expectancy_edu_sex": le_edu_sex,
            "cases": cases, "barometro_year": 2025}


def num_es(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def build(conn: sqlite3.Connection) -> dict:
    store = Store(conn)
    le = life_expectancy(store)
    spend = spending(store)
    wait = waiting(store)
    docs = doctors(store)
    outc = outcomes(store)
    ages = ageing(store)
    staff = workforce(store)
    insur = insurance(store)
    primary = primary_care(store)
    perc = perception(store)
    intl = waits_international(store)
    regions = regions_side_by_side(store, spend, wait, perc)
    story = data_vs_story(store)
    patient = patient_side(store)
    money = money_allocation(store)
    pay = pay_and_migration(store)
    ageadj = age_adjusted(store, story, spend)
    regions = regions_adjusted(store, regions, spend)
    bases = base_years(store, money)
    older = waits_per_older(store, wait)
    dist = distribution(store)
    seg = segments(store, wait, regions)
    story["dental"] = {"year": patient["dental_cost"]["year"],
                       "rows": [row for row in patient["dental_cost"]["rows"] if row["code"] in ("ES", "DE", "FR", "IT", "PT", "EU27_2020")]}

    def at(rows: list[dict], date: str) -> float:
        return next(p["value"] for p in rows if p["date"] == date)

    last_break = max(b["date"] for b in wait["breaks"]["surgery"])
    last_cut = wait["surgery"]["mean_days"][-1]["date"]
    eu_pps = spend["eurostat_pps_public"]
    pps_year = max(p["year"] for p in eu_pps["ES"])
    pps = {g: next((p["value"] for p in eu_pps[g] if p["year"] == pps_year), None) for g in eu_pps}
    eu_gdp = spend["eurostat_pct_gdp_public"]
    gdp = {g: next((p["value"] for p in eu_gdp[g] if p["year"] == pps_year), None) for g in eu_gdp}
    le_es = le["eurostat"]["ES"][-1]
    le_eu = next(p for p in le["eurostat"]["EU27_2020"] if p["year"] == le_es["year"])
    sources = {}
    for source_id, releases in store.provenance.items():
        label, page = SOURCE_PAGES[source_id]
        retrieved = max((rel["retrieved_at"] or "" for rel in releases), default="") or None
        sources[source_id] = {"label": label, "page": page, "retrieved_at": retrieved, "releases": releases}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "storage": "SQLite health-es.db: indicator_* contract (releases, revisions, evidence per value; SISLE and EGSP "
        "values point at the page and table row of the official PDF); built by scripts/ingest_health_es.py",
        "headline": {
            "life_expectancy": {"year": le_es["year"], "es": le_es["value"], "eu27": le_eu["value"],
                                "world_rank": le["world"]["spain_rank"], "world_year": le["world"]["year"],
                                "oecd_rank": le["world"]["oecd_rank"]},
            "spending": {"year": pps_year, "pps_es": pps["ES"], "pps_eu27": pps["EU27_2020"],
                         "pct_gdp_es": gdp["ES"], "pct_gdp_eu27": gdp["EU27_2020"],
                         "oecd_rank_per_person": spend["oecd_rank_per_person"]},
            "waiting": {
                "comparable_since": last_break, "last_cut": last_cut,
                "surgery_days": [at(wait["surgery"]["mean_days"], last_break), at(wait["surgery"]["mean_days"], last_cut)],
                "surgery_rate": [at(wait["surgery"]["rate_per_1000"], last_break), at(wait["surgery"]["rate_per_1000"], last_cut)],
                "surgery_patients": [at(wait["surgery"]["patients"], last_break), at(wait["surgery"]["patients"], last_cut)],
                "consult_days": [at(wait["consultations"]["mean_days"], last_break), at(wait["consultations"]["mean_days"], last_cut)],
                "consult_rate": [at(wait["consultations"]["rate_per_1000"], last_break), at(wait["consultations"]["rate_per_1000"], last_cut)],
                "selected_days": [next(p["value"] for p in wait["national_selected_days"] if p["date"] == last_break),
                                  next(p["value"] for p in wait["national_selected_days"] if p["date"] == last_cut)],
            },
        },
        "life_expectancy": le,
        "spending": spend,
        "waiting": wait,
        "doctors": docs,
        "outcomes": outc,
        "ageing": ages,
        "workforce": staff,
        "insurance": insur,
        "primary_care": primary,
        "perception": perc,
        "waits_international": intl,
        "regions": regions,
        "data_vs_story": story,
        "patient": patient,
        "money": money,
        "pay": pay,
        "age_adjusted": ageadj,
        "base_years": bases,
        "waits_per_older": older,
        "distribution": dist,
        "segments": seg,
        "sources": sources,
    }


def write_csv(data: dict, path: Path) -> None:
    rows: list[tuple] = []
    le = data["life_expectancy"]
    for area, pts in le["long_run"].items():
        rows.extend(("owid_grapher", "esperanza_vida_anios", area, p["year"], p["value"]) for p in pts)
    for geo, pts in le["eurostat"].items():
        rows.extend(("eurostat_sdmx:demo_mlexpec", "esperanza_vida_anios", geo, p["year"], p["value"]) for p in pts)
    for sex, pts in le["ine"].items():
        rows.extend(("ine_wstempus:1414", f"esperanza_vida_anios_{sex}", "ESP", p["year"], p["value"]) for p in pts)
    for row in le["world"]["oecd_members"]:
        rows.append(("worldbank_wdi", "esperanza_vida_anios", row["code"], le["world"]["year"], row["value"]))
    sp = data["spending"]
    for key, label in (("pct_gdp_public", "gasto_publico_pct_pib"), ("per_person_ppp_public", "gasto_publico_eur_ppa_2020_por_persona")):
        for area, pts in sp[key].items():
            rows.extend(("oecd_health_statistics", label, area, p["year"], p["value"]) for p in pts)
    rows.extend(("oecd_health_statistics", "gasto_publico_pct_pib_media_ocde", "OECD_MEAN", p["year"], p["value"]) for p in sp["pct_gdp_public_oecd_mean"])
    rows.extend(("oecd_health_statistics", "gasto_publico_eur_ppa_2020_media_ocde", "OECD_MEAN", p["year"], p["value"]) for p in sp["per_person_ppp_public_oecd_mean"])
    rows.extend(("oecd_health_statistics", "gasto_publico_eur_2020_por_persona", "ESP", p["year"], p["value"]) for p in sp["per_person_eur2020_public_esp"])
    rows.extend(("oecd_health_statistics", "gasto_sanitario_total_pct_pib", "ESP", p["year"], p["value"]) for p in sp["pct_gdp_total_esp"])
    rows.extend(("oecd_health_statistics", "pago_directo_hogares_pct_gasto", "ESP", p["year"], p["value"]) for p in sp["oop_share_esp_long"])
    for key, label in (("eurostat_pct_gdp_public", "gasto_publico_pct_pib"), ("eurostat_pps_public", "gasto_publico_pps_por_habitante"),
                       ("eurostat_oop_share", "pago_directo_hogares_pct_gasto")):
        for geo, pts in sp[key].items():
            rows.extend(("eurostat_sdmx:hlth_sha11_hf", label, geo, p["year"], p["value"]) for p in pts)
    reg = sp["regions_per_person"]
    rows.extend(("minsan_egsp", "gasto_sanitario_ccaa_eur_por_habitante", row["code"], reg["year"], row["value"]) for row in reg["rows"])
    wait = data["waiting"]
    for group, series in (("quirurgica", wait["surgery"]), ("consultas", wait["consultations"])):
        for metric, pts in series.items():
            rows.extend(("minsan_sisle_sns", f"{group}_{metric}", "ES", p["date"], p["value"]) for p in pts)
    for region in wait["regions_selected"]:
        rows.extend(("minsan_sisle_sns", "procesos_seleccionados_dias", region["code"], p["date"], p["value"]) for p in region["days"])
        rows.extend(("minsan_sisle_sns", "procesos_seleccionados_tasa_1000", region["code"], p["date"], p["value"]) for p in region["rate"])
    for key, label in (("practising", "medicos_ejercicio_100k"), ("gp", "medicos_familia_100k"), ("specialists", "especialistas_100k"),
                       ("paediatricians", "pediatras_100k")):
        for geo, pts in data["doctors"][key].items():
            rows.extend(("eurostat_sdmx", label, geo, p["year"], p["value"]) for p in pts)
    out = data["outcomes"]
    for key, label in (("hly", "anios_vida_saludable"), ("treatable", "mortalidad_tratable_100k"), ("preventable", "mortalidad_prevenible_100k")):
        for geo, pts in out[key].items():
            rows.extend(("eurostat_sdmx", label, geo, p["year"], p["value"]) for p in pts)
    for cancer, by_area in out["cancer_survival"].items():
        for area, pts in by_area.items():
            rows.extend(("oecd_health_statistics", f"supervivencia_5_anios_{cancer}", area, p["year"], p["value"]) for p in pts)
    for geo, pts in data["ageing"]["over65"].items():
        rows.extend(("eurostat_sdmx:demo_pjanind", "poblacion_65_mas_pct", geo, p["year"], p["value"]) for p in pts)
    for geo, pts in data["workforce"]["nurses"].items():
        rows.extend(("eurostat_sdmx", "enfermeras_ejercicio_100k", geo, p["year"], p["value"]) for p in pts)
    for geo, pts in data["workforce"]["doctors_55plus_share"].items():
        rows.extend(("eurostat_sdmx:hlth_rs_phys", "medicos_55_mas_pct", geo, p["year"], p["value"]) for p in pts)
    for code, item in data["workforce"]["siap"].items():
        rows.append(("minsan_siap", code, "ES", item["year"], item["value"]))
    for area, pts in data["insurance"]["voluntary"].items():
        rows.extend(("oecd_health_statistics", "seguro_voluntario_pct_poblacion", area, p["year"], p["value"]) for p in pts)
    for key, pts in data["primary_care"].items():
        rows.extend(("minsan_barometro", f"cita_medico_familia_{key}", "ES", p["year"], p["value"]) for p in pts)
    for key in ("worse", "better"):
        rows.extend(("minsan_barometro", f"opinion_listas_{key}_pct", "ES", p["year"], p["value"]) for p in data["perception"][key])
    for code, item in data["waits_international"]["procedures"].items():
        rows.extend(("oecd_health_statistics", f"mediana_dias_{code}", row["code"], item["year"], row["value"]) for row in item["rows"])
    for code, item in data["waits_international"]["spain_mean_on_list"].items():
        rows.extend(("oecd_health_statistics", f"media_dias_en_lista_{code}", "ESP", p["year"], p["value"]) for p in item["points"])
    st = data["data_vs_story"]
    for c in st["countries"]["rows"]:
        rows.append(("eurostat_sdmx", "gasto_publico_pps_indice_ue100", c["code"], st["countries"]["last"], c["x"]))
        rows.append(("eurostat_sdmx", "mortalidad_tratable_100k", c["code"], st["countries"]["last"], c["y"]))
    for x in st["regions"]["rows"]:
        for year, key in ((st["regions"]["from"], "x0"), (st["regions"]["to"], "x")):
            rows.append(("minsan_egsp+oecd_deflactor", "gasto_ccaa_eur_2020_por_habitante", x["code"], year, x[key]))
    pat = data["patient"]
    for geo, pts in pat["oop_share_household_consumption"].items():
        rows.extend(("eurostat_sdmx", "bolsillo_pct_consumo_hogares", geo, p["year"], p["value"]) for p in pts)
    for row in pat["dental_cost"]["rows"]:
        rows.append(("eurostat_sdmx:hlth_silc_09", "dental_no_atendida_coste_q1_pct", row["code"], pat["dental_cost"]["year"], row["poor"]))
        rows.append(("eurostat_sdmx:hlth_silc_09", "dental_no_atendida_coste_q5_pct", row["code"], pat["dental_cost"]["year"], row["rich"]))
    for key, by_geo in pat["medical"].items():
        for geo, pts in by_geo.items():
            rows.extend(("eurostat_sdmx:hlth_silc_08", f"medica_no_atendida_{key}_pct", geo, p["year"], p["value"]) for p in pts)
    for geo, pts in pat["catastrophic_10"].items():
        rows.extend(("who_gho", "gasto_catastrofico_10_pct", geo, p["year"], p["value"]) for p in pts)
    for label, pts in data["money"]["functional_shares"].items():
        rows.extend(("minsan_egsp", f"funcional_pct_{label}", "ES", p["year"], p["value"]) for p in pts)
    for label, pts in data["money"]["economic_shares"].items():
        rows.extend(("minsan_egsp", f"economica_pct_{label}", "ES", p["year"], p["value"]) for p in pts)
    for row in data["money"]["providers"]:
        for k in ("HP1", "HP3", "HP5"):
            rows.append(("eurostat_sdmx:hlth_sha11_hphf", f"gasto_publico_pct_{k}", row["code"], row["year"], row[k]))
    for prof, items in data["pay"]["pay"].items():
        rows.extend(("oecd_health_statistics", f"retribucion_veces_salario_medio_{prof}", x["code"], x["year"], x["ratio"]) for x in items)
    for x in data["pay"]["doctors_abroad"]["rows"]:
        rows.append(("oecd_health_statistics", "medicos_formados_en_espana_en_destino", x["code"], x["year"], x["value"]))
    for row in data["regions"]["rows"]:
        rows.append(("ine_wstempus:1448", "esperanza_vida_ccaa", row["code"], data["regions"]["le_year"], row["life_expectancy"]))
    seg = data["segments"]
    for q, by_age in seg["dental_grid"]["values"].items():
        rows.extend(("eurostat_sdmx:hlth_silc_09", f"dental_no_atendida_coste_{q.lower()}_{age}_pct", "ES", seg["dental_grid"]["year"], v)
                    for age, v in by_age.items() if v is not None)
    for kind, by_breakdown in seg["tables"].items():
        for breakdown, groups in by_breakdown.items():
            rows.extend(("minsan_barometro:cruces", f"{kind}_{breakdown}_pct|{g['group']}", "ES", seg["barometro_year"], g["value"]) for g in groups)
    for key, value in seg["life_expectancy_edu_sex"]["values"].items():
        rows.append(("ine_wstempus:37663", f"esperanza_vida_{key}", "ES", seg["life_expectancy_edu_sex"]["year"], value))
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["fuente", "serie", "area", "periodo", "valor"])
    writer.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    if not args.db.exists():
        if OUT_JSON.exists():
            print(f"export_public_viz_health: {args.db.name} not found; keeping committed artifact", file=sys.stderr)
            return 0
        raise SystemExit(f"missing {args.db}; run scripts/ingest_health_es.py first")
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    data = build(conn)
    conn.close()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    write_csv(data, OUT_CSV)
    h = data["headline"]
    print(f"sanidad: {json.dumps(h, ensure_ascii=False)}; {OUT_JSON.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
