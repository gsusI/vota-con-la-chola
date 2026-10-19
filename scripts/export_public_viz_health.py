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
        self.provenance[source_id].append({
            "indicator": f"{dataset_code} {indicator_code} ({unit_code})", "url": url, "sha256": sha,
            "snapshot_date": snapshot, "retrieved_at": json.loads(meta or "{}").get("retrieved_at"),
        })
        out: dict[str, list[dict]] = defaultdict(list)
        for geo, name, dims, period, value, status, labels in self.conn.execute(
            """
            SELECT s.geography_code, s.geography_name, s.dimensions_json, o.period_label, o.value_decimal,
                   o.source_status_code, o.source_status_labels_json
            FROM indicator_observation_versions o JOIN indicator_series_versions s USING (indicator_series_version_id)
            WHERE o.indicator_release_id = ? AND o.revision_state != 'deleted' AND o.value_decimal IS NOT NULL
            ORDER BY s.geography_code, o.period_start
            """,
            (release_id,),
        ):
            key = geo if json.loads(dims).get("sex") in (None, "T") else f"{geo}:{json.loads(dims)['sex']}"
            point = {"period": period, "value": float(value), "name": name}
            if status:
                point["status"] = status
                point["labels"] = json.loads(labels)
            out[key].append(point)
        return out


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
    for row in data["regions"]["rows"]:
        rows.append(("ine_wstempus:1448", "esperanza_vida_ccaa", row["code"], data["regions"]["le_year"], row["life_expectancy"]))
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
