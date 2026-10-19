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


def build(conn: sqlite3.Connection) -> dict:
    store = Store(conn)
    le = life_expectancy(store)
    spend = spending(store)
    wait = waiting(store)
    docs = doctors(store)

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
            },
        },
        "life_expectancy": le,
        "spending": spend,
        "waiting": wait,
        "doctors": docs,
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
