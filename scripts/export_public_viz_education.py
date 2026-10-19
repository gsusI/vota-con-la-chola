#!/usr/bin/env python3
"""Export /visualizaciones/educacion/ data from the education DB (scripts/ingest_education_es.py).

Reads only normalized tables: the latest release of each indicator (indicator_* contract). Derived figures (real
public spending per non-university student) are computed here from stored values, with the formula recorded in the
output. Writes the page JSON (with per-source provenance: URL, retrieval date, sha256) and a long CSV.
When the DB is missing (CI checkouts) the committed artifact is kept.
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
DEFAULT_DB = REPO_ROOT / "etl/data/staging/education-es.db"
OUT_JSON = REPO_ROOT / "ui/site/public/visualizaciones/data/educacion.json"
OUT_CSV = REPO_ROOT / "ui/site/public/visualizaciones/data/educacion.csv"

SOURCE_PAGES = {
    "mefp_educabase": ("Ministerio de Educación, FP y Deportes · EDUCAbase (gasto público, alumnado, idoneidad)", "https://www.educacionfpydeportes.gob.es/servicios-al-ciudadano/estadisticas/economicas/gasto/series.html"),
    "eurostat_sdmx": ("Eurostat · edat_lfse_14, edat_lfse_16, lfsa_eoqgan, gov_10a_exp, educ_uoe_fine09, nama_10_gdp", "https://ec.europa.eu/eurostat/databrowser/view/edat_lfse_14/default/table"),
    "oecd_eag_finance": ("OCDE · Education at a Glance, gasto por estudiante (réplica DBnomics)", "https://db.nomics.world/OECD/DSD_EAG_UOE_FIN@DF_UOE_INDIC_FIN_PERSTUD"),
    "worldbank_edstats": ("Banco Mundial · EdStats, puntuaciones PISA 2000-2018", "https://databank.worldbank.org/source/education-statistics-%5e-all-indicators"),
    "owid_grapher": ("Our World in Data · alfabetización (UNESCO) y años de escolarización (Lee y Lee; Barro y Lee)", "https://ourworldindata.org/global-education"),
    "vclc_education_curated": ("PISA 2022: informe español del INEE y nota de país de la OCDE (cita literal por valor)", "https://www.educacionfpydeportes.gob.es/inee/evaluaciones-internacionales/pisa/pisa-2022/pisa-2022-informes-es.html"),
}
PEERS_EU = ["ES", "EU27_2020", "DE", "FR", "IT", "PT"]
PEERS_OECD = ["ESP", "OECD", "EU25", "DEU", "FRA", "ITA", "PRT"]
PISA_AREAS = ["ESP", "OECD", "DEU", "FRA", "ITA", "PRT"]
LONG_RUN_AREAS = ["ESP", "FRA", "ITA", "PRT", "DEU"]
# PISA trend comparability (OECD): reading from 2000, mathematics from 2003, science from 2006.
PISA_FIRST_COMPARABLE = {"math": 2003, "reading": 2000, "science": 2006}


def r(value: float | None, digits: int = 1) -> float | None:
    return None if value is None else round(float(value), digits)


class Store:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.provenance: dict[str, list[dict]] = defaultdict(list)

    def series(self, source_id: str, indicator_code: str, unit_code: str, dims: dict | None = None) -> dict[str, list[dict]]:
        """Latest release of an indicator as {geography_code: [observation]}; deleted rows are dropped."""
        row = self.conn.execute(
            """
            SELECT r.indicator_release_id, r.source_url, r.source_content_sha256, r.source_snapshot_date,
                   r.source_metadata_json
            FROM indicator_definitions d JOIN indicator_releases r USING (indicator_id)
            WHERE d.source_id = ? AND d.indicator_code = ? AND d.unit_code = ?
            ORDER BY r.source_snapshot_date DESC, r.created_at DESC LIMIT 1
            """,
            (source_id, indicator_code, unit_code),
        ).fetchone()
        if row is None:
            raise LookupError(f"indicator {source_id}:{indicator_code}:{unit_code} not loaded")
        release_id, url, sha, snapshot, meta = row
        self.provenance[source_id].append({
            "indicator": f"{indicator_code} ({unit_code})", "url": url, "sha256": sha,
            "snapshot_date": snapshot, "retrieved_at": json.loads(meta or "{}").get("retrieved_at"),
        })
        out: dict[str, list[dict]] = defaultdict(list)
        for geo, geo_name, dims_json, period, value, status in self.conn.execute(
            """
            SELECT s.geography_code, s.geography_name, s.dimensions_json, o.period_label, o.value_decimal,
                   o.source_status_code
            FROM indicator_observation_versions o JOIN indicator_series_versions s USING (indicator_series_version_id)
            WHERE o.indicator_release_id = ? AND o.revision_state != 'deleted' AND o.value_decimal IS NOT NULL
            ORDER BY s.geography_code, o.period_start
            """,
            (release_id,),
        ):
            if dims and any(json.loads(dims_json).get(k) != v for k, v in dims.items()):
                continue
            out[geo].append({"period": period, "value": float(value), "status": status, "name": geo_name})
        return out

    def by_dimension(self, source_id: str, indicator_code: str, unit_code: str, dim: str,
                     fixed: dict | None = None) -> dict[tuple[str, str], dict[int, float]]:
        """Latest release as {(geography_code, value of `dim`): {year: value}} for indicators with several series per area."""
        release_id = self._release(source_id, indicator_code, unit_code)
        out: dict[tuple[str, str], dict[int, float]] = defaultdict(dict)
        for geo, dims_json, period, value in self.conn.execute(
            """
            SELECT s.geography_code, s.dimensions_json, o.period_label, o.value_decimal
            FROM indicator_observation_versions o JOIN indicator_series_versions s USING (indicator_series_version_id)
            WHERE o.indicator_release_id = ? AND o.revision_state != 'deleted' AND o.value_decimal IS NOT NULL
            """,
            (release_id,),
        ):
            dims = json.loads(dims_json)
            if fixed and any(dims.get(k) != v for k, v in fixed.items()):
                continue
            out[(geo, dims.get(dim))][int(period[:4])] = float(value)
        return out

    def _release(self, source_id: str, indicator_code: str, unit_code: str) -> str:
        row = self.conn.execute(
            """
            SELECT r.indicator_release_id, r.source_url, r.source_content_sha256, r.source_snapshot_date, r.source_metadata_json
            FROM indicator_definitions d JOIN indicator_releases r USING (indicator_id)
            WHERE d.source_id = ? AND d.indicator_code = ? AND d.unit_code = ?
            ORDER BY r.source_snapshot_date DESC, r.created_at DESC LIMIT 1
            """,
            (source_id, indicator_code, unit_code),
        ).fetchone()
        if row is None:
            raise LookupError(f"indicator {source_id}:{indicator_code}:{unit_code} not loaded")
        release_id, url, sha, snapshot, meta = row
        self.provenance[source_id].append({
            "indicator": f"{indicator_code} ({unit_code})", "url": url, "sha256": sha,
            "snapshot_date": snapshot, "retrieved_at": json.loads(meta or "{}").get("retrieved_at"),
        })
        return release_id

    def annual(self, source_id: str, indicator_code: str, unit_code: str, geo: str, dims: dict | None = None) -> dict[int, float]:
        return {int(p["period"][:4]): p["value"] for p in self.series(source_id, indicator_code, unit_code, dims).get(geo, [])}


def points(mapping: dict[int, float], digits: int = 1, since: int | None = None) -> list[dict]:
    return [{"year": y, "value": r(v, digits)} for y, v in sorted(mapping.items()) if since is None or y >= since]


def by_area(rows: dict[str, list[dict]], areas: list[str], digits: int = 1) -> dict[str, list[dict]]:
    return {area: [{"year": int(p["period"][:4]), "value": r(p["value"], digits)} for p in rows.get(area, [])] for area in areas}


def change(series: list[dict], first: int, last: int) -> float | None:
    values = {p["year"]: p["value"] for p in series}
    if first in values and last in values and values[first]:
        return r((values[last] / values[first] - 1) * 100, 0)
    return None


def build(conn: sqlite3.Connection) -> dict:
    store = Store(conn)
    total = {"Cobertura económica": "Incluídos capitulos financieros", "Tipo de administración": "TOTAL"}

    # 1. Spending ---------------------------------------------------------------------------------
    eag_q = store.series("oecd_eag_finance", "FIN_PERSTUD.ISCED11_1T4.S13.INST_EDU.DIR_EXP", "USD_PPP_2020")
    eag_q_all = store.series("oecd_eag_finance", "FIN_PERSTUD.ISCED11_1T8.S13.INST_EDU.DIR_EXP", "USD_PPP_2020")
    eag_school = by_area(eag_q, PEERS_OECD, 0)
    eag_all = by_area(eag_q_all, PEERS_OECD, 0)

    spend_nonuni = store.annual("mefp_educabase", "gasto_publico_instituciones_no_universitarias", "KEUR", "ES", total)
    spend_total = store.annual("mefp_educabase", "gasto_publico_educacion_total", "KEUR", "ES", total)
    spend_pct = store.annual("mefp_educabase", "gasto_publico_educacion_pct_pib", "PC_GDP", "ES")
    students = {
        int(p["period"][:4]): p["value"]
        for p in store.series("mefp_educabase", "alumnado_regimen_general", "PERSONS").get("ES", [])
    }
    deflator = store.annual("eurostat_sdmx", "B1GQ.PD20_NAC", "PD20_NAC", "ES")
    base_year = max(y for y in spend_nonuni if y in deflator)
    real_per_student = []
    for year, keur in sorted(spend_nonuni.items()):
        # A calendar year spans two school years: Jan-Jun of (year-1)/year and Sep-Dec of year/(year+1).
        if year in deflator and (year - 1) in students and year in students:
            enrolled = (students[year - 1] + students[year]) / 2
            real_per_student.append({
                "year": year, "value": r(keur * 1000 / enrolled * deflator[base_year] / deflator[year], 0),
                "nominal": r(keur * 1000 / enrolled, 0), "students": round(enrolled),
            })
    cofog = by_area(store.series("eurostat_sdmx", "GF09.TE.S13", "PC_GDP"), PEERS_EU)
    pps = by_area(store.series("eurostat_sdmx", "public_exp_per_student.ED02-8", "PPS"), PEERS_EU, 0)

    # 2. PISA ---------------------------------------------------------------------------------------
    pisa: dict[str, dict[str, list[dict]]] = {}
    for domain, code in (("math", "pisa_math_mean"), ("reading", "pisa_reading_mean"), ("science", "pisa_science_mean")):
        wb = store.series("worldbank_edstats", code, "PISA_SCORE")
        curated = store.series("vclc_education_curated", code, "PISA_SCORE")
        merged: dict[str, dict[int, dict]] = defaultdict(dict)
        for area in PISA_AREAS:
            for p in wb.get("OED" if area == "OECD" else area, []):
                merged[area][int(p["period"])] = {"value": r(p["value"], 0), "source": "worldbank_edstats"}
            for p in curated.get(area, []):
                merged[area][int(p["period"])] = {"value": r(p["value"], 0), "source": "vclc_education_curated"}
        first = PISA_FIRST_COMPARABLE[domain]
        pisa[domain] = {
            area: [{"year": y, **v, "comparable": y >= first} for y, v in sorted(merged[area].items())]
            for area in PISA_AREAS
        }
        pisa[f"{domain}_eu_2022"] = r(curated.get("EU", [{}])[0].get("value"), 0) if curated.get("EU") else None

    # 3. Early leavers ------------------------------------------------------------------------------
    leavers_rows = store.series("eurostat_sdmx", "early_leavers_18_24.T.POP", "PC")
    leavers = {
        area: [{"year": int(p["period"]), "value": r(p["value"]), "flag": p["status"]} for p in leavers_rows.get(area, [])]
        for area in PEERS_EU
    }
    breaks = sorted({p["year"] for p in leavers["ES"] + leavers["EU27_2020"] if p["flag"] and "b" in p["flag"]})
    regions_rows = store.series("eurostat_sdmx", "early_leavers_18_24.T.NUTS2", "PC")
    region_years: dict[str, dict[int, float]] = {
        geo: {int(p["period"]): p["value"] for p in rows} for geo, rows in regions_rows.items()
    }
    region_names = {geo: rows[0]["name"] for geo, rows in regions_rows.items() if rows}
    first_region_year = 2008
    last_region_year = max(max(v) for v in region_years.values() if v)
    regions = sorted(
        [
            {"geo": geo, "name": region_names[geo], "first": r(vals.get(first_region_year)), "last": r(vals.get(last_region_year))}
            for geo, vals in region_years.items()
            if vals.get(last_region_year) is not None
        ],
        key=lambda row: row["last"],
    )

    # 4. Grade repetition ---------------------------------------------------------------------------
    idoneidad = store.series("mefp_educabase", "tasa_idoneidad_15", "PC")
    behind = [{"year": int(p["period"][:4]) + 1, "course": p["period"], "value": r(100 - p["value"])} for p in idoneidad["ES"]]
    pisa_rep = store.series("vclc_education_curated", "pisa_repeated_grade_pct", "PC")
    repetition_pisa_series = {
        area: [{"year": int(p["period"]), "value": r(p["value"], 0)} for p in rows] for area, rows in pisa_rep.items()
    }
    repetition_pisa = {area: rows[-1]["value"] for area, rows in repetition_pisa_series.items()}

    # 5. Over-qualification -------------------------------------------------------------------------
    overq_rows = store.series("eurostat_sdmx", "overqualification_rate.Y20-64", "PC")
    overq = {
        area: [{"year": int(p["period"]), "value": r(p["value"]), "flag": p["status"]} for p in overq_rows.get(area, [])]
        for area in PEERS_EU
    }
    overq_breaks = sorted({p["year"] for p in overq["ES"] if p["flag"] and "b" in p["flag"]})

    # 6. Long run -----------------------------------------------------------------------------------
    literacy_rows = store.series("owid_grapher", "literacy_rate", "PC")
    literacy = {
        area: [{"year": int(p["period"]), "value": r(p["value"])} for p in literacy_rows.get(area, []) if int(p["period"]) >= 1860]
        for area in LONG_RUN_AREAS
    }
    schooling = by_area(store.series("owid_grapher", "mean_years_schooling_15_64", "YEARS"), LONG_RUN_AREAS, 2)

    # 7. Regions: PISA 2022 against public spending per non-university student -------------------
    consejerias = store.by_dimension("mefp_educabase", "gasto_publico_instituciones_no_universitarias", "KEUR",
                                     "Tipo de administración", {"Cobertura económica": total["Cobertura económica"]})
    regional_students = store.by_dimension("mefp_educabase", "alumnado_regimen_general_por_ccaa", "PERSONS", "Comunidad autónoma")
    students_by_region = {region: years for (_geo, region), years in regional_students.items()}
    pisa_regions = {
        p["name"]: p["value"]
        for geo, rows in store.series("vclc_education_curated", "pisa_math_mean", "PISA_SCORE").items()
        if geo.startswith("ES-CCAA:") for p in rows if p["period"] == "2022"
    }
    region_year = 2022
    regions_pisa = []
    for (_geo, admin), years in consejerias.items():
        if not admin or " - Consejería" not in admin:
            continue
        region = admin.split(" - ")[0].strip()
        enrolled = students_by_region.get(region, {})
        if region_year in years and region_year in enrolled and (region_year - 1) in enrolled:
            per_student = years[region_year] * 1000 / ((enrolled[region_year - 1] + enrolled[region_year]) / 2)
            regions_pisa.append({"region": region, "spending_per_student": r(per_student, 0), "math": pisa_regions.get(region)})
    regions_pisa.sort(key=lambda row: -(row["math"] or 0))
    paired = [row for row in regions_pisa if row["math"] is not None]
    n = len(paired)
    mx = sum(row["spending_per_student"] for row in paired) / n
    my = sum(row["math"] for row in paired) / n
    cov = sum((row["spending_per_student"] - mx) * (row["math"] - my) for row in paired)
    vx = sum((row["spending_per_student"] - mx) ** 2 for row in paired)
    vy = sum((row["math"] - my) ** 2 for row in paired)
    pearson = cov / (vx * vy) ** 0.5 if vx and vy else None
    city_scores = {name: v for name, v in pisa_regions.items() if name in ("Ceuta", "Melilla")}

    # 8. Equity and student mix (PISA, quoted) ------------------------------------------------------
    def curated(code: str, unit: str = "PC") -> dict[str, dict[int, float]]:
        return {
            geo: {int(p["period"]): p["value"] for p in rows}
            for geo, rows in store.series("vclc_education_curated", code, unit).items()
        }
    escs_gap = curated("pisa_escs_gap_math", "PISA_SCORE")
    escs_var = curated("pisa_escs_variance_pct")
    resilient = curated("pisa_resilient_pct")
    immigrant_share = curated("pisa_immigrant_share_pct")
    immigrant_gap = curated("pisa_immigrant_gap_math", "PISA_SCORE")["ESP"][2022]
    immigrant_gap_adj = curated("pisa_immigrant_gap_math_escs_adjusted", "PISA_SCORE")["ESP"][2022]
    immigrant_disadvantaged = curated("pisa_disadvantaged_immigrant_pct")["ESP"][2022]
    share_change = immigrant_share["ESP"][2022] - immigrant_share["ESP"][2012]
    es_math = {p["year"]: p["value"] for p in pisa["math"]["ESP"]}
    math_2012 = es_math.get(2012)
    composition = {
        "share_2012": immigrant_share["ESP"][2012], "share_2022": immigrant_share["ESP"][2022],
        "gap_raw": immigrant_gap, "gap_adjusted": immigrant_gap_adj,
        "effect_raw_points": r(share_change / 100 * immigrant_gap, 1),
        "effect_adjusted_points": r(share_change / 100 * immigrant_gap_adj, 1),
        "math_change_2012_2022": r(es_math.get(2022) - math_2012, 0) if math_2012 else None,
        "formula": "cambio en la proporción de alumnado inmigrante (2012→2022) × diferencia media de puntuación; "
        "aritmética ilustrativa que supone que el resto no cambia",
    }

    # 9. Teachers ------------------------------------------------------------------------------------
    salaries = store.by_dimension("oecd_eag_finance", "SAL_STA.TE.TYP_EXP", "IX2015", "EDUCATION_LEV", {"PERS_EXP_LEV": "EXP15"})
    salary_index = {
        level: {area: points(salaries.get((area, level), {}), 1) for area in PEERS_OECD if salaries.get((area, level))}
        for level in ("ISCED11_1", "ISCED11_24", "ISCED11_34")
    }
    ratios = store.by_dimension("eurostat_sdmx", "pupil_teacher_ratio", "RT", "isced11")
    pupil_teacher = {level: {geo: points(ratios.get((geo, level), {}), 1) for geo in PEERS_EU} for level in ("ED1", "ED2", "ED3")}

    # 10. Vocational training and attainment ---------------------------------------------------------
    enrol = store.by_dimension("eurostat_sdmx", "upper_secondary_enrolment", "PERSONS", "isced11")
    vocational_share = {
        geo: [{"year": y, "value": r(v / enrol[(geo, "ED3")][y] * 100)} for y, v in sorted(enrol.get((geo, "ED35"), {}).items())
              if enrol.get((geo, "ED3"), {}).get(y)]
        for geo in PEERS_EU
    }
    grads = store.by_dimension("eurostat_sdmx", "recent_graduates_employment_rate", "PC", "isced11")
    recent_grads = {level: {geo: points(grads.get((geo, level), {})) for geo in PEERS_EU} for level in ("ED34_44", "ED35_45", "ED5-8")}
    attain = store.by_dimension("eurostat_sdmx", "attainment_25_34", "PC", "isced11")
    attainment = {level: {geo: points(attain.get((geo, level), {})) for geo in PEERS_EU} for level in ("ED0-2", "ED3_4", "ED5-8")}

    sal_es = {p["year"]: p["value"] for p in salary_index["ISCED11_24"]["ESP"]}
    sal_oecd = {p["year"]: p["value"] for p in salary_index["ISCED11_24"]["OECD"]}
    sal_peak = max(sal_es, key=lambda y: sal_es[y])
    sal_last = max(sal_es)
    sal_oecd_last = max(sal_oecd)
    teachers_headline = {
        "salary_peak": {"year": sal_peak, "value": sal_es[sal_peak]}, "salary_last": {"year": sal_last, "value": sal_es[sal_last]},
        "salary_change_from_peak_pct": r((sal_es[sal_last] / sal_es[sal_peak] - 1) * 100, 0),
        "oecd_2009": sal_oecd.get(2009), "oecd_last": {"year": sal_oecd_last, "value": sal_oecd[sal_oecd_last]},
    }

    sources = {}
    for source_id, releases in store.provenance.items():
        label, page = SOURCE_PAGES[source_id]
        retrieved = max((rel["retrieved_at"] or "" for rel in releases), default="") or None
        sources[source_id] = {"label": label, "page": page, "retrieved_at": retrieved, "releases": releases}
    documents = json.loads(conn.execute(
        """
        SELECT r.source_metadata_json FROM indicator_releases r JOIN indicator_definitions d USING (indicator_id)
        WHERE d.source_id = 'vclc_education_curated' ORDER BY r.created_at DESC LIMIT 1
        """
    ).fetchone()[0])
    sources["vclc_education_curated"]["documents"] = documents["documents"]

    esp_school = {p["year"]: p["value"] for p in eag_school["ESP"]}
    oecd_school = {p["year"]: p["value"] for p in eag_school["OECD"]}
    last_eag = max(y for y in esp_school if y in oecd_school)
    peak_year = max(esp_school, key=lambda y: esp_school[y])
    trough_year = min((y for y in esp_school if y > peak_year), key=lambda y: esp_school[y])
    es_leavers = {p["year"]: p["value"] for p in leavers["ES"]}
    eu_leavers = {p["year"]: p["value"] for p in leavers["EU27_2020"]}
    last_leavers = max(es_leavers)
    math = {p["year"]: p["value"] for p in pisa["math"]["ESP"]}
    reading = {p["year"]: p["value"] for p in pisa["reading"]["ESP"]}
    science = {p["year"]: p["value"] for p in pisa["science"]["ESP"]}
    behind_by_year = {p["year"]: p["value"] for p in behind}
    overq_es = {p["year"]: p["value"] for p in overq["ES"]}
    overq_eu = {p["year"]: p["value"] for p in overq["EU27_2020"]}
    last_overq = max(y for y in overq_es if y in overq_eu)
    pps_es = {p["year"]: p["value"] for p in pps["ES"]}
    pps_eu = {p["year"]: p["value"] for p in pps["EU27_2020"]}
    last_pps = max(y for y in pps_es if y in pps_eu)
    lit_es = {p["year"]: p["value"] for p in literacy["ESP"]}
    sch_es = {p["year"]: p["value"] for p in schooling["ESP"]}
    sch_first = 1900 if 1900 in sch_es else min(sch_es)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "storage": "SQLite education-es.db: indicator_* contract (releases, revisions, evidence per value); built by "
        "scripts/ingest_education_es.py",
        "headline": {
            "spending_school_2000": esp_school.get(2000),
            "spending_school_last": esp_school[last_eag],
            "spending_school_last_year": last_eag,
            "spending_school_change_2000_pct": r((esp_school[last_eag] / esp_school[2000] - 1) * 100, 0),
            "spending_school_peak": {"year": peak_year, "value": esp_school[peak_year]},
            "spending_school_trough": {"year": trough_year, "value": esp_school[trough_year]},
            "spending_school_vs_oecd_pct": r(esp_school[last_eag] / oecd_school[last_eag] * 100, 0),
            "spending_school_vs_oecd_2005_pct": r(esp_school[2005] / oecd_school[2005] * 100, 0),
            "oecd_school_change_2005_pct": r((oecd_school[last_eag] / oecd_school[2005] - 1) * 100, 0),
            "real_per_student_base_year": base_year,
            "real_per_student_2000": next(p for p in real_per_student if p["year"] == 2000),
            "real_per_student_last": real_per_student[-1],
            "real_per_student_peak": max(real_per_student, key=lambda p: p["value"]),
            "pps_last_year": last_pps,
            "pps_es": pps_es[last_pps],
            "pps_eu": pps_eu[last_pps],
            "math_2003": math.get(2003), "math_2022": math.get(2022),
            "oecd_math_2003": next((p["value"] for p in pisa["math"]["OECD"] if p["year"] == 2003), None),
            "reading_2000": reading.get(2000), "reading_2022": reading.get(2022),
            "science_2006": science.get(2006), "science_2022": science.get(2022),
            "leavers_2008": es_leavers.get(2008), "leavers_last": es_leavers[last_leavers], "leavers_last_year": last_leavers,
            "leavers_eu_2008": eu_leavers.get(2008), "leavers_eu_last": eu_leavers.get(last_leavers),
            "leavers_breaks": breaks,
            "behind_first": behind[0], "behind_peak": max(behind, key=lambda p: p["value"]), "behind_last": behind[-1],
            "behind_2020": behind_by_year.get(2020), "behind_2021": behind_by_year.get(2021),
            "repetition_pisa_2022": repetition_pisa,
            "overq_es": overq_es[last_overq], "overq_eu": overq_eu[last_overq], "overq_year": last_overq,
            "literacy_1900": lit_es.get(1900), "literacy_last": {"year": max(lit_es), "value": lit_es[max(lit_es)]},
            "schooling_first": {"year": sch_first, "value": sch_es[sch_first]},
            "schooling_last": {"year": max(sch_es), "value": sch_es[max(sch_es)]},
        },
        "spending": {
            "eag_school_usd_ppp_2020": eag_school,
            "eag_all_usd_ppp_2020": eag_all,
            "real_per_nonuni_student_eur": real_per_student,
            "public_spending_total_keur": points(spend_total, 0),
            "public_spending_pct_gdp_mefp": points(spend_pct, 2),
            "cofog_pct_gdp": cofog,
            "pps_per_student": pps,
            "formula_real_per_student": "gasto público en instituciones no universitarias (Ministerio, miles de euros) × 1000 "
            "÷ media del alumnado de régimen general de los dos cursos que abarca el año × deflactor del PIB del año base "
            "÷ deflactor del año (Eurostat nama_10_gdp, PD20_NAC)",
        },
        "pisa": {**pisa, "first_comparable": PISA_FIRST_COMPARABLE},
        "early_leavers": {"series": leavers, "breaks": breaks, "regions": regions,
                          "regions_first_year": first_region_year, "regions_last_year": last_region_year},
        "repetition": {"behind_at_15": behind, "pisa_2022": repetition_pisa, "pisa_series": repetition_pisa_series},
        "overqualification": overq,
        "overqualification_breaks_es": overq_breaks,
        "long_run": {"literacy": literacy, "schooling": schooling},
        "regions_pisa": {"year": region_year, "rows": regions_pisa, "pearson": r(pearson, 2), "n": n, "cities": city_scores,
                         "formula": "gasto de la consejería de educación en centros no universitarios (Ministerio, miles de euros) "
                         "× 1000 ÷ media del alumnado de régimen general de los cursos 2021-22 y 2022-23"},
        "equity": {"escs_gap": escs_gap, "escs_variance": escs_var, "resilient": resilient,
                   "immigrant_share": {geo: points(v) for geo, v in immigrant_share.items()},
                   "immigrant_disadvantaged_pct": immigrant_disadvantaged, "composition": composition},
        "teachers": {"salary_index": salary_index, "pupil_teacher": pupil_teacher, "headline": teachers_headline},
        "vocational": {"share_upper_secondary": vocational_share, "recent_graduates_employment": recent_grads},
        "attainment_25_34": attainment,
        "sources": sources,
    }


def write_csv(data: dict, path: Path) -> None:
    rows: list[tuple] = []
    for area, pts in data["spending"]["eag_school_usd_ppp_2020"].items():
        rows.extend(("oecd_eag_finance", "gasto_publico_por_estudiante_primaria_a_postsecundaria_usd_ppa_2020", area, p["year"], p["value"]) for p in pts)
    for area, pts in data["spending"]["eag_all_usd_ppp_2020"].items():
        rows.extend(("oecd_eag_finance", "gasto_publico_por_estudiante_primaria_a_terciaria_usd_ppa_2020", area, p["year"], p["value"]) for p in pts)
    base = data["headline"]["real_per_student_base_year"]
    rows.extend(("mefp_educabase+eurostat_sdmx", f"gasto_publico_por_alumno_no_universitario_eur_{base}", "ES", p["year"], p["value"])
                for p in data["spending"]["real_per_nonuni_student_eur"])
    rows.extend(("mefp_educabase", "gasto_publico_educacion_miles_eur", "ES", p["year"], p["value"]) for p in data["spending"]["public_spending_total_keur"])
    rows.extend(("mefp_educabase", "gasto_publico_educacion_pct_pib", "ES", p["year"], p["value"]) for p in data["spending"]["public_spending_pct_gdp_mefp"])
    for area, pts in data["spending"]["cofog_pct_gdp"].items():
        rows.extend(("eurostat_sdmx", "gasto_aapp_educacion_cofog_pct_pib", area, p["year"], p["value"]) for p in pts)
    for area, pts in data["spending"]["pps_per_student"].items():
        rows.extend(("eurostat_sdmx", "gasto_publico_por_alumno_pps", area, p["year"], p["value"]) for p in pts)
    for domain in ("math", "reading", "science"):
        for area, pts in data["pisa"][domain].items():
            rows.extend((p["source"], f"pisa_{domain}", area, p["year"], p["value"]) for p in pts)
    for area, pts in data["early_leavers"]["series"].items():
        rows.extend(("eurostat_sdmx", "abandono_temprano_18_24_pct", area, p["year"], p["value"]) for p in pts)
    for row in data["early_leavers"]["regions"]:
        rows.append(("eurostat_sdmx", "abandono_temprano_18_24_pct", row["geo"], data["early_leavers"]["regions_first_year"], row["first"]))
        rows.append(("eurostat_sdmx", "abandono_temprano_18_24_pct", row["geo"], data["early_leavers"]["regions_last_year"], row["last"]))
    rows.extend(("mefp_educabase", "alumnado_15_anios_retrasado_pct", "ES", p["year"], p["value"]) for p in data["repetition"]["behind_at_15"])
    for area, pts in data["repetition"]["pisa_series"].items():
        rows.extend(("vclc_education_curated", "pisa_repetidores_pct", area, p["year"], p["value"]) for p in pts)
    for area, pts in data["overqualification"].items():
        rows.extend(("eurostat_sdmx", "sobrecualificacion_20_64_pct", area, p["year"], p["value"]) for p in pts)
    for area, pts in data["long_run"]["literacy"].items():
        rows.extend(("owid_grapher", "alfabetizacion_pct", area, p["year"], p["value"]) for p in pts)
    for area, pts in data["long_run"]["schooling"].items():
        rows.extend(("owid_grapher", "anios_escolarizacion_15_64", area, p["year"], p["value"]) for p in pts)
    for row in data["regions_pisa"]["rows"]:
        rows.append(("mefp_educabase", "gasto_consejeria_por_alumno_no_universitario_eur", f"ES-CCAA:{row['region']}", data["regions_pisa"]["year"], row["spending_per_student"]))
        rows.append(("vclc_education_curated", "pisa_math", f"ES-CCAA:{row['region']}", 2022, row["math"]))
    eq = data["equity"]
    for key, label in (("escs_gap", "pisa_brecha_isec_matematicas"), ("escs_variance", "pisa_varianza_isec_pct"), ("resilient", "pisa_resilientes_pct")):
        for area, years in eq[key].items():
            rows.extend(("vclc_education_curated", label, area, int(y), v) for y, v in years.items())
    for area, pts in eq["immigrant_share"].items():
        rows.extend(("vclc_education_curated", "pisa_alumnado_inmigrante_pct", area, p["year"], p["value"]) for p in pts)
    for level, areas in data["teachers"]["salary_index"].items():
        for area, pts in areas.items():
            rows.extend(("oecd_eag_finance", f"salario_real_profesorado_15_anios_indice_2015_{level}", area, p["year"], p["value"]) for p in pts)
    for level, areas in data["teachers"]["pupil_teacher"].items():
        for area, pts in areas.items():
            rows.extend(("eurostat_sdmx", f"alumnos_por_profesor_{level}", area, p["year"], p["value"]) for p in pts)
    for area, pts in data["vocational"]["share_upper_secondary"].items():
        rows.extend(("eurostat_sdmx", "fp_pct_secundaria_superior", area, p["year"], p["value"]) for p in pts)
    for level, areas in data["vocational"]["recent_graduates_employment"].items():
        for area, pts in areas.items():
            rows.extend(("eurostat_sdmx", f"empleo_titulados_recientes_{level}", area, p["year"], p["value"]) for p in pts)
    for level, areas in data["attainment_25_34"].items():
        for area, pts in areas.items():
            rows.extend(("eurostat_sdmx", f"nivel_estudios_25_34_{level}", area, p["year"], p["value"]) for p in pts)
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
            print(f"export_public_viz_education: {args.db.name} not found; keeping committed artifact", file=sys.stderr)
            return 0
        raise SystemExit(f"missing {args.db}; run scripts/ingest_education_es.py first")
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    data = build(conn)
    conn.close()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    write_csv(data, OUT_CSV)
    h = data["headline"]
    print(
        f"educacion: gasto/estudiante {h['spending_school_2000']} -> {h['spending_school_last']} USD PPA 2020 "
        f"({h['spending_school_change_2000_pct']:+}%); PISA mat {h['math_2003']} -> {h['math_2022']}; abandono "
        f"{h['leavers_2008']}% -> {h['leavers_last']}%; {OUT_JSON.stat().st_size // 1024} KB"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
