#!/usr/bin/env python3
"""Export /visualizaciones/vivienda/ data from the housing DB (scripts/ingest_housing_es.py).

Reads only the indicator_* tables (latest release of each indicator, deleted rows dropped). Derived figures (years
of salary for a 90 m² home, net new households, cumulative build-vs-households balance, public housing spending in %
of GDP, purchase taxes on a typical home) are computed here from stored values only. Partial years are dropped
(quarterly series need 4 quarters, monthly series 12 months). Writes the page JSON (with per-source provenance: URL,
retrieval date, sha256) and a long CSV. When the DB is missing (CI checkouts) the committed artifact is kept.
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
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "etl/data/staging/housing-es.db"
OUT_JSON = REPO_ROOT / "ui/site/public/visualizaciones/data/vivienda.json"
OUT_CSV = REPO_ROOT / "ui/site/public/visualizaciones/data/vivienda.csv"

HOME_M2 = 90
PEERS_EUROSTAT = ["ES", "EU27_2020", "DE", "FR", "IT", "PT"]
PEERS_OECD = ["ESP", "OECD", "DEU", "FRA", "ITA", "PRT"]
REGIONS = {
    "ES61": "Andalucía", "ES24": "Aragón", "ES12": "Asturias", "ES53": "Illes Balears", "ES70": "Canarias",
    "ES13": "Cantabria", "ES41": "Castilla y León", "ES42": "Castilla-La Mancha", "ES51": "Cataluña",
    "ES52": "Comunitat Valenciana", "ES43": "Extremadura", "ES11": "Galicia", "ES30": "Comunidad de Madrid",
    "ES62": "Región de Murcia", "ES22": "Navarra", "ES21": "País Vasco", "ES23": "La Rioja", "ES63": "Ceuta", "ES64": "Melilla",
}
GAP_FROM, GAP_TO = 2013, 2025  # households measured at both ends; completions summed over GAP_FROM+1..GAP_TO
SOURCE_PAGES = {
    "mivau_boletin": ("Ministerio de Vivienda y Agenda Urbana · Boletín estadístico (valor tasado, viviendas terminadas)", "https://apps.fomento.gob.es/BoletinOnline2/"),
    "bde_indicadores_vivienda": ("Banco de España · Indicadores del mercado de la vivienda (si_1_5)", "https://www.bde.es/webbe/es/estadisticas/temas/sectores-real/vivienda.html"),
    "ine_tempus": ("INE · Encuesta Trimestral de Coste Laboral (API Tempus)", "https://www.ine.es/dyngs/INEbase/operacion.htm?c=Estadistica_C&cid=1254736045053&idp=1254735976596"),
    "oecd_dbnomics": ("OCDE · salarios medios y precios de la vivienda (réplica DBnomics)", "https://db.nomics.world/OECD"),
    "eurostat_sdmx": ("Eurostat · yth_demo_030, ilc_lvho02, gov_10a_exp, nama_10_gdp", "https://ec.europa.eu/eurostat/databrowser/"),
    "vclc_housing_curated": ("Normas y publicaciones oficiales citadas fila a fila", "https://www.boe.es/"),
}


def r(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(float(value), digits)


class Store:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.provenance: dict[str, list[dict]] = defaultdict(list)

    def raw(self, indicator_code: str, source_id: str | None = None, where: dict[str, str] | None = None) -> dict[str, dict[str, float]]:
        """Latest release of an indicator as {geography_code: {period: value}}; `where` filters on series dimensions."""
        row = self.conn.execute(
            """
            SELECT d.source_id, r.indicator_release_id, r.source_url, r.source_content_sha256, r.source_snapshot_date,
                   r.source_metadata_json, d.unit_code
            FROM indicator_definitions d JOIN indicator_releases r USING (indicator_id)
            WHERE d.indicator_code = ? AND (? IS NULL OR d.source_id = ?)
            ORDER BY r.source_snapshot_date DESC, r.created_at DESC LIMIT 1
            """,
            (indicator_code, source_id, source_id),
        ).fetchone()
        if row is None:
            raise LookupError(f"indicator {indicator_code} not loaded")
        src, release_id, url, sha, snapshot, meta, unit = row
        self.provenance[src].append({
            "indicator": f"{indicator_code} ({unit})", "url": url, "sha256": sha, "snapshot_date": snapshot,
            "retrieved_at": json.loads(meta or "{}").get("retrieved_at"),
        })
        out: dict[str, dict[str, float]] = defaultdict(dict)
        for geo, key, dims, period, value in self.conn.execute(
            """
            SELECT s.geography_code, s.stable_series_key, s.dimensions_json, o.period_label, o.value_decimal
            FROM indicator_observation_versions o JOIN indicator_series_versions s USING (indicator_series_version_id)
            WHERE o.indicator_release_id = ? AND o.revision_state != 'deleted' AND o.value_decimal IS NOT NULL
            """,
            (release_id,),
        ):
            if where and any(json.loads(dims).get(k) != v for k, v in where.items()):
                continue
            out[geo][period] = float(value)
        return out

    def optional(self, indicator_code: str) -> dict[str, dict[str, float]] | None:
        try:
            return self.raw(indicator_code)
        except LookupError:
            return None

    def curated_rows(self, indicator_code: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT s.geography_code, s.dimensions_json, o.period_label, o.value_decimal, o.raw_value_json, e.source_url
            FROM indicator_definitions d
            JOIN indicator_releases r ON r.indicator_id = d.indicator_id
            JOIN indicator_observation_versions o ON o.indicator_release_id = r.indicator_release_id
            JOIN indicator_series_versions s USING (indicator_series_version_id)
            JOIN indicator_observation_evidence e ON e.indicator_observation_version_id = o.indicator_observation_version_id
              AND e.extraction_method = 'curated_citation'
            WHERE d.source_id = 'vclc_housing_curated' AND d.indicator_code = ? AND o.revision_state != 'deleted'
              AND r.indicator_release_id = (
                SELECT r2.indicator_release_id FROM indicator_releases r2 WHERE r2.indicator_id = d.indicator_id
                ORDER BY r2.source_snapshot_date DESC, r2.created_at DESC LIMIT 1)
            ORDER BY s.geography_code, o.period_label
            """,
            (indicator_code,),
        ).fetchall()
        return [
            {"geo": geo, "dims": json.loads(dims), "period": period, "value": float(value), "row": json.loads(raw), "url": url}
            for geo, dims, period, value, raw, url in rows
        ]


def annual(values: dict[str, float], how: str = "mean") -> dict[int, float]:
    """Annual mean (quarters/months) or sum (months); only complete years. Annual series pass through."""
    groups: dict[int, list[float]] = defaultdict(list)
    kinds = set()
    for period, value in values.items():
        groups[int(period[:4])].append(value)
        kinds.add("Q" if "-Q" in period else "M" if len(period) == 7 else "A")
    need = {"Q": 4, "M": 12, "A": 1}[kinds.pop()] if len(kinds) == 1 else None
    if need is None:
        raise ValueError(f"mixed frequencies {kinds}")
    return {y: (sum(v) if how == "sum" else sum(v) / len(v)) for y, v in groups.items() if len(v) == need}


def pts(mapping: dict[int, float], digits: int = 2, since: int | None = None, until: int | None = None) -> list[dict]:
    return [
        {"year": y, "value": r(v, digits)} for y, v in sorted(mapping.items())
        if (since is None or y >= since) and (until is None or y <= until)
    ]


def index_to(mapping: dict[int, float], base: int) -> dict[int, float]:
    return {y: v / mapping[base] * 100 for y, v in mapping.items()} if base in mapping else {}


def regional(s: "Store", completed_national: dict[int, float]) -> dict:
    """Completions vs new households and years of salary by autonomous community (NUTS 2)."""
    free = s.raw("viviendas_libres_terminadas_ccaa")
    prot = s.raw("vivienda_protegida_calificaciones_definitivas_ccaa")
    households = s.raw("lfst_r_lfsd2hh._T")
    price = s.raw("valor_tasado_vivienda_libre_ccaa")
    wage = s.raw("etcl_coste_salarial_ccaa")
    rent = s.raw("ipva_indice")
    tourist = s.raw("viviendas_turisticas_pct")
    tourist_period = max(tourist["ES"])
    rows = []
    for code, name in REGIONS.items():
        years = range(GAP_FROM + 1, GAP_TO + 1)
        built = sum(free[code].get(str(y), 0.0) + prot[code].get(str(y), 0.0) for y in years)
        hh = households.get(code, {})
        h0, h1 = hh.get(str(GAP_FROM)), hh.get(str(GAP_TO))
        formed = (h1 - h0) * 1000 if h0 is not None and h1 is not None else None
        p_ann = annual(price[code])
        w_ann = {y: v * 12 for y, v in annual(wage[code]).items()} if code in wage else {}
        years_salary = {y: r(p_ann[y] * HOME_M2 / w_ann[y]) for y in (2008, 2015, GAP_TO) if y in p_ann and y in w_ann}
        rent_idx = {int(k): v for k, v in rent.get(code, {}).items()}
        rows.append({
            "code": code, "name": name, "completed": r(built, 0), "net_households": r(formed, 0),
            "households_start": r(h0 * 1000, 0) if h0 else None,
            "gap": r(formed - built, 0) if formed is not None else None,
            "gap_per_1000": r((formed - built) / (h0 * 1000) * 1000, 1) if formed is not None and h0 else None,
            # A ratio over a near-zero change in households is meaningless (Asturias: +99 households in 12 years).
            "ratio": r(built / formed, 2) if formed and h0 and formed > 0.01 * h0 * 1000 else None,
            "price_m2": r(p_ann.get(GAP_TO), 0), "wage": r(w_ann.get(GAP_TO), 0), "years_salary": years_salary,
            "rent_change_2015": r(rent_idx[max(rent_idx)] - rent_idx[2015], 1) if rent_idx and 2015 in rent_idx else None,
            "rent_last_year": max(rent_idx) if rent_idx else None,
            "tourist_pct": r(tourist.get(code, {}).get(tourist_period), 2),
        })
    built_total = sum(row["completed"] for row in rows)
    if abs(built_total - sum(completed_national[y] for y in range(GAP_FROM + 1, GAP_TO + 1))) > 1:
        raise SystemExit("regional completions do not add up to the national total")
    return {"from": GAP_FROM, "to": GAP_TO, "tourist_period": tourist_period, "tourist_es": r(tourist["ES"][tourist_period], 2),
            "tourist_es_series": [{"period": k, "value": v} for k, v in sorted(tourist["ES"].items())], "rows": rows}


def connected_story(completed: dict[int, float], net_households: dict[int, float], intercensal: list[dict],
                    years_income: dict[int, float], rate: dict[int, float], credit_growth: dict[int, float],
                    first_year: int = 1995) -> list[dict]:
    """«El dato mata el relato»: one point per year for a connected scatter.

    x = homes completed per new household (3-year window of EPA households where available, otherwise the intercensal
    average that covers the year); y = years of median household income (Banco de España, one continuous series);
    colour = growth of housing credit. Windows that include 2021, when the EPA was reweighted, are flagged."""
    story = []
    for y in range(first_year, max(completed) + 1):
        if y not in completed or y not in years_income:
            continue
        span_years = [t for t in (y - 2, y - 1, y) if t in net_households and t in completed]
        if span_years:
            built, formed = sum(completed[t] for t in span_years), sum(net_households[t] for t in span_years)
            x, basis = built / formed, "epa_2021" if 2021 in span_years else "epa"
        else:
            span = next((i for i in intercensal if i["from"] < y <= i["to"]), None)
            if span is None:
                continue
            x, basis = completed[y] / span["per_year"], f"censos {span['from']}–{span['to']}"
        story.append({"year": y, "x": r(x, 2), "y": r(years_income[y], 2), "rate": r(rate.get(y), 2),
                      "credit_growth": r(credit_growth.get(y), 1), "basis": basis, "window": span_years})
    return story


def build(conn: sqlite3.Connection) -> dict:
    s = Store(conn)

    # 1. Affordability: years of gross salary for a 90 m² home.
    price_m2 = annual(s.raw("valor_tasado_vivienda_libre")["ES"])
    bde_price = annual(s.raw("precio_m2_vivienda_libre_tasada")["ES"])
    mismatch = [y for y in price_m2 if y in bde_price and abs(price_m2[y] - bde_price[y]) > 0.5]
    if mismatch:
        raise SystemExit(f"MIVAU and Banco de España €/m² disagree in {mismatch}")
    home = {y: v * HOME_M2 for y, v in price_m2.items()}
    wage_retro = {y: v * 12 for y, v in annual(s.raw("ETCL6726")["ES"]).items()}
    wage_ine = {y: v * 12 for y, v in annual(s.raw("ETCL1527")["ES"]).items()}
    wage_oecd = {int(p): v for p, v in s.raw("WG.EUR.A.V.MEAN")["ESP"].items()}
    years_retro = {y: home[y] / w for y, w in wage_retro.items() if y in home}
    years_ine = {y: home[y] / w for y, w in wage_ine.items() if y in home}
    years_oecd = {y: home[y] / w for y, w in wage_oecd.items() if y in home}
    years_bde = annual(s.raw("precio_vivienda_renta_hogar_anios")["ES"])
    effort = annual(s.raw("esfuerzo_teorico_anual")["ES"])
    rate = annual(s.raw("tipo_prestamos_vivienda")["ES"])
    years_ine_all = {**years_retro, **years_ine}
    last = max(years_ine)
    peak_year = max(years_ine_all, key=years_ine_all.get)
    trough_year = min((y for y in years_ine_all if y > peak_year), key=years_ine_all.get)

    hp_income = s.raw("HPI_YDH_AVG")
    hp_rent = s.raw("HPI_RPI_AVG")
    hp_real = s.raw("RHP")

    # 2. Supply vs households.
    free = {int(p): v for p, v in s.raw("viviendas_libres_terminadas")["ES"].items()}
    protected = {int(p): v for p, v in s.raw("vivienda_protegida_calificaciones_definitivas")["ES"].items()}
    completed = {y: free[y] + protected.get(y, 0.0) for y in free if y in protected}
    starts = annual(s.raw("viviendas_iniciadas_total")["ES"], "sum")
    permits = annual(s.raw("visados_obra_nueva_viviendas")["ES"], "sum")
    households = {y: v * 1000 for y, v in annual(s.raw("epa_hogares")["ES"]).items()}
    net_households = {y: households[y] - households[y - 1] for y in households if y - 1 in households}
    census_hh = {int(p): v for p, v in s.raw("censo_viviendas_principales")["ES"].items()}
    census_years = sorted(census_hh)
    intercensal = [
        {"from": a, "to": b, "per_year": r((census_hh[b] - census_hh[a]) / (b - a), 0),
         "completed_per_year": r(sum(completed[y] for y in range(a + 1, b + 1)) / (b - a), 0) if all(y in completed for y in range(a + 1, b + 1)) else None}
        for a, b in zip(census_years, census_years[1:])
    ]
    first_balance = min(net_households)
    balance, running = [], 0.0
    for y in sorted(net_households):
        if y in completed:
            running += completed[y] - net_households[y]
            balance.append({"year": y, "value": r(running, 0)})

    def window(a: int, b: int) -> dict:
        ys = [y for y in range(a, b + 1) if y in completed and y in net_households]
        built, formed = sum(completed[y] for y in ys), sum(net_households[y] for y in ys)
        return {"from": ys[0], "to": ys[-1], "years": len(ys), "completed": r(built, 0), "net_households": r(formed, 0),
                "completed_per_year": r(built / len(ys), 0), "households_per_year": r(formed / len(ys), 0),
                "ratio": r(built / formed, 2)}

    census_stock = []
    stock = {k: s.raw(f"censo_viviendas_{k}")["ES"] for k in ("total", "principales", "secundarias", "desocupadas")}
    for year in census_years:
        p = str(year)
        census_stock.append({"year": year, **{k: r(v.get(p), 0) for k, v in stock.items()}})

    # 3. Leaving home.
    leave = s.raw("yth_demo_030._T")

    # 4. Tenure.
    census_tenure = {
        int(p): {"owner": v, "rent": s_rent, "other": s_other}
        for p, v in s.raw("censo_principales_propiedad_pct")["ES"].items()
        for s_rent in [s.raw("censo_principales_alquiler_pct")["ES"].get(p)]
        for s_other in [s.raw("censo_principales_cesion_pct")["ES"].get(p)]
    }
    early_census = []
    for field in ("owner_pct", "rent_pct", "other_pct"):
        for row in (s.curated_rows(f"census_tenure_{field}") if s.optional(f"census_tenure_{field}") else []):
            year = int(row["period"])
            entry = next((e for e in early_census if e["year"] == year), None)
            if entry is None:
                entry = {"year": year, "source": row["row"].get("source"), "source_url": row["url"],
                         "locator": row["row"].get("locator"), "confidence": row["row"].get("confidence"), "note": row["row"].get("note")}
                early_census.append(entry)
            entry[field.removesuffix("_pct")] = row["value"]
    survey_owner = {int(p): v for p, v in s.raw("encuesta_tenencia_propiedad_pct")["ES"].items()}
    survey_rent = {int(p): v for p, v in s.raw("encuesta_tenencia_alquiler_pct")["ES"].items()}
    silc_own = s.raw("ilc_lvho02.OWN", where={"rskpovth": "TOTAL"})
    silc_rent_mkt = s.raw("ilc_lvho02.RENT_MKT", where={"rskpovth": "TOTAL"})
    young = []
    for code in [row[0] for row in conn.execute(
        "SELECT DISTINCT indicator_code FROM indicator_definitions WHERE indicator_code LIKE 'owner_pct_by_age.%' ORDER BY 1")]:
        s.raw(code)
        for row in s.curated_rows(code):
            young.append({"source_key": code.split(".", 1)[1], "age_group": row["dims"].get("age_group"), "year": int(row["period"]),
                          "value": r(row["value"], 1), "source": row["row"].get("source"), "source_url": row["url"],
                          "locator": row["row"].get("locator"), "confidence": row["row"].get("confidence")})
    social = []
    if s.optional("social_rental_stock_pct"):
        for row in s.curated_rows("social_rental_stock_pct"):
            social.append({"country": row["geo"], "year": int(row["period"]) if row["period"].isdigit() else None, "value": r(row["value"], 1),
                           "source": row["row"].get("source"), "source_url": row["url"], "note": row["row"].get("note"),
                           "confidence": row["row"].get("confidence")})

    # 5. Purchase taxes on a typical home.
    tax_rows = []
    for (code,) in conn.execute(
        "SELECT DISTINCT indicator_code FROM indicator_definitions WHERE dataset_code = 'purchase_taxes_es' ORDER BY 1"
    ):
        s.raw(code)
        for row in s.curated_rows(code):
            cited = row["row"]
            tax_rows.append({
                "key": code, "year": int(row["period"][:4]), "scope": row["geo"], "value": row["value"],
                "unit": cited.get("unit", "pct"), "payer": cited.get("payer"), "applies_to": cited.get("applies_to"),
                "norm": cited.get("norm"), "boe_id": cited.get("boe_id"), "source_url": row["url"],
                "locator": cited.get("locator"), "quote": cited.get("quote"), "confidence": cited.get("confidence"),
                "note": cited.get("note"),
            })
    taxes = purchase_taxes(tax_rows, home, conn)

    # 6. Public spending on housing (% of GDP).
    dev = s.raw("gov_10a_exp.GF0601")
    allow = s.raw("gov_10a_exp.GF1006")
    gdp = s.raw("nama_10_gdp._T")
    spending = {}
    for geo in PEERS_EUROSTAT:
        rows = []
        for p in sorted(gdp.get(geo, {})):
            if p in dev.get(geo, {}) and p in allow.get(geo, {}):
                g = gdp[geo][p]
                rows.append({"year": int(p), "development": r(dev[geo][p] / g * 100, 3), "allowances": r(allow[geo][p] / g * 100, 3),
                             "total": r((dev[geo][p] + allow[geo][p]) / g * 100, 3)})
        spending[geo] = rows

    wage_all = {**wage_retro, **wage_ine}
    # 7. Sale prices next to appraisal values (index 2015 = 100).
    transactions = annual(s.raw("valor_medio_transacciones_vivienda_libre")["ES"])
    ipv = {int(p): v for p, v in s.raw("ipv_indice_media_anual")["ES"].items()}
    # Years of salary with transaction prices: INE IPV (hedonic, from notarial deeds) chained to the 2015 appraisal level.
    years_ipv = {y: price_m2[2015] * HOME_M2 * v / ipv[2015] / wage_all[y] for y, v in ipv.items() if y in wage_all}
    sale_prices = {
        "years_ipv_chained": pts(years_ipv),
        "appraisal_idx": pts(index_to(price_m2, 2015), 1),
        "transactions_idx": pts(index_to(transactions, 2015), 1),
        "ipv_idx": pts(index_to(ipv, 2015), 1),
        "transactions_eur": pts(transactions, 0),
        "appraisal_home_eur": pts(home, 0, since=min(transactions)),
    }

    # 8. Rents: INE IPVA against wages and prices; HICP actual rentals (real) against peers.
    ipva = {int(p): v for p, v in s.raw("ipva_indice")["ES"].items()}
    hicp_rent = s.raw("prc_hicp_aind.CP041")
    hicp_all = s.raw("prc_hicp_aind.CP00")
    es_cpi = {int(p): v for p, v in hicp_all["ES"].items()}
    rents = {
        "ipva_idx": pts(ipva, 1),
        "wage_idx": pts(index_to(wage_all, 2015), 1, since=min(ipva)),
        "cpi_idx": pts(index_to(es_cpi, 2015), 1, since=min(ipva)),
        "appraisal_idx": pts(index_to(price_m2, 2015), 1, since=min(ipva)),
        "hicp_rent_real": {
            geo: pts({int(p): v / hicp_all[geo][p] * 100 for p, v in hicp_rent.get(geo, {}).items() if p in hicp_all.get(geo, {})}, 1)
            for geo in PEERS_EUROSTAT
        },
        "hicp_rent_nominal_es": pts({int(p): v for p, v in hicp_rent["ES"].items()}, 1),
        "ipc_rent_yoy": pts(annual(s.raw("ipc_alquiler_tasa_interanual")["ES"]), 1),
        "ipva_change_pct": {str(b): r((ipva[max(ipva)] / ipva[b] - 1) * 100, 1) for b in (2011, 2015, 2019) if b in ipva},
    }

    # 9. Competing drivers: credit, population and migration, household size, short-term rentals.
    pop = s.raw("demo_gind.JAN")
    migration = s.raw("demo_gind.CNMIGRATRT")
    growth = s.raw("demo_gind.GROWRT")
    natural = s.raw("demo_gind.NATGROWRT")
    hh_size = s.raw("ilc_lvph01._T")
    nights = s.raw("tour_ce_omn12._T")
    pop_es = {int(p): v for p, v in pop["ES"].items()}
    mid_pop = {y: (pop_es[y] + pop_es[y + 1]) / 2 for y in pop_es if y + 1 in pop_es}
    d0, d1 = GAP_FROM, max(y for y in households if y in mid_pop)
    size0 = mid_pop[d0] / households[d0]
    same_size = mid_pop[d1] / size0
    decomposition = {
        "from": d0, "to": d1, "households_from": r(households[d0], 0), "households_to": r(households[d1], 0),
        "population_from": r(mid_pop[d0], 0), "population_to": r(mid_pop[d1], 0),
        "persons_per_household_from": r(size0, 3), "persons_per_household_to": r(mid_pop[d1] / households[d1], 3),
        "total": r(households[d1] - households[d0], 0),
        "population_effect": r(same_size - households[d0], 0),
        "size_effect": r(households[d1] - same_size, 0),
    }
    nights_pc = {
        geo: pts({int(p): v / pop[geo][p] for p, v in nights.get(geo, {}).items() if p in pop.get(geo, {}) and int(p) <= max(int(q) for q in pop[geo])}, 2)
        for geo in PEERS_EUROSTAT
    }
    drivers = {
        "credit_pct_gdp": pts(annual(s.raw("credito_vivienda_hogares_pct_pib")["ES"]), 1),
        "mortgage_rate_pct": pts(rate),
        "net_migration_per_1000": {geo: pts({int(p): v for p, v in migration.get(geo, {}).items()}, 1) for geo in PEERS_EUROSTAT},
        "population_growth_per_1000": {geo: pts({int(p): v for p, v in growth.get(geo, {}).items()}, 1) for geo in PEERS_EUROSTAT},
        "natural_growth_per_1000_es": pts({int(p): v for p, v in natural["ES"].items()}, 1),
        "population_es": pts(pop_es, 0),
        "household_size": {geo: pts({int(p): v for p, v in hh_size.get(geo, {}).items()}, 2) for geo in PEERS_EUROSTAT},
        "household_decomposition": decomposition,
        "platform_nights_per_capita": nights_pc,
    }

    credit_growth = annual(s.raw("credito_vivienda_hogares_tasa")["ES"])
    norms = None
    if s.optional("boe_housing_norms_per_year"):
        norms_raw = s.raw("boe_housing_norms_per_year")["ES"]
        by_scope: dict[str, dict[int, float]] = defaultdict(dict)
        for key, period, value in conn.execute(
            """
            SELECT sv.stable_series_key, o.period_label, o.value_decimal FROM indicator_definitions d
            JOIN indicator_releases r ON r.indicator_id = d.indicator_id
            JOIN indicator_series_versions sv ON sv.indicator_release_id = r.indicator_release_id
            JOIN indicator_observation_versions o ON o.indicator_series_version_id = sv.indicator_series_version_id
            WHERE d.indicator_code = 'boe_housing_norms_per_year' AND o.revision_state != 'deleted'
              AND r.indicator_release_id = (SELECT r2.indicator_release_id FROM indicator_releases r2 WHERE r2.indicator_id = d.indicator_id
                                            ORDER BY r2.source_snapshot_date DESC, r2.created_at DESC LIMIT 1)
            """
        ):
            by_scope[key.split("|")[-1]][int(period)] = float(value)
        del norms_raw
        norms = {scope: pts(values, 0) for scope, values in by_scope.items()}
        landmarks = []
        norms_file = REPO_ROOT / "etl/data/manual/housing/boe_housing_norms_es.json"
        if norms_file.exists():
            listed = json.loads(norms_file.read_text(encoding="utf-8")).get("norms", [])
            ranks = ("ley", "real_decreto_ley")
            landmarks = [
                {k: n.get(k) for k in ("boe_id", "date", "title", "scope", "rank", "url")}
                for n in listed if n.get("scope") == "estatal" and n.get("rank") in ranks
            ]
        norms["state_laws"] = landmarks

    region_block = regional(s, completed)

    # 10. Capacity lens: the same home against net, median and young earners' pay, plus burdens against peers.
    tw100 = {int(p): v for p, v in s.raw("AV_RITEESSC.S_C0.AW100")["ESP"].items()}
    tw67 = {int(p): v for p, v in s.raw("AV_RITEESSC.S_C0.AW67")["ESP"].items()}
    wedge = {int(p): v for p, v in s.raw("AV_TW.S_C0.AW100")["ESP"].items()}
    median = {int(p): v for p, v in s.raw("ees_ganancia_mediana")["ES"].items()}
    by_age_rows = conn.execute(
        """
        SELECT sv.dimensions_json, o.period_label, o.value_decimal FROM indicator_definitions d
        JOIN indicator_releases r ON r.indicator_id = d.indicator_id
        JOIN indicator_series_versions sv ON sv.indicator_release_id = r.indicator_release_id
        JOIN indicator_observation_versions o ON o.indicator_series_version_id = sv.indicator_series_version_id
        WHERE d.indicator_code = 'ees_ganancia_media_edad' AND o.revision_state != 'deleted'
          AND r.indicator_release_id = (SELECT r2.indicator_release_id FROM indicator_releases r2 WHERE r2.indicator_id = d.indicator_id
                                        ORDER BY r2.source_snapshot_date DESC, r2.created_at DESC LIMIT 1)
        """
    ).fetchall()
    s.raw("ees_ganancia_media_edad")
    young_pay = {int(period): float(value) for dims, period, value in by_age_rows if json.loads(dims).get("grupo") == "De 25 a 34 años"}
    if not young_pay:
        raise SystemExit("EES: the 25-34 age group was not found")
    ipv_price = {y: price_m2[2015] * HOME_M2 * v / ipv[2015] for y, v in ipv.items()}

    def years_with(income: dict[int, float], prices: dict[int, float] = home) -> list[dict]:
        return pts({y: prices[y] / v for y, v in income.items() if y in prices and v}, 2)

    net_avg = {y: v * (1 - tw100[y] / 100) for y, v in wage_all.items() if y in tw100}
    net_median = {y: v * (1 - tw67[y] / 100) for y, v in median.items() if y in tw67}
    net_young = {y: v * (1 - tw67[y] / 100) for y, v in young_pay.items() if y in tw67}
    burden = {
        "overburden_total": s.raw("ilc_lvho07a.TOTAL"), "overburden_young": s.raw("ilc_lvho07a.Y15-29"),
        "overburden_tenants": s.raw("ilc_lvho07c.RENT_MKT"), "overburden_mortgage": s.raw("ilc_lvho07c.OWN_L"),
        "cost_share": s.raw("ilc_mded01._T"), "rent_share_tenants": s.raw("ilc_mded02._T"),
    }
    income_pps = s.raw("ilc_di03._T")
    capacity = {
        "years_gross_avg": years_with(wage_all),
        "years_net_avg": years_with(net_avg),
        "years_gross_median": years_with(median),
        "years_net_median": years_with(net_median),
        "years_net_young": years_with(net_young),
        "years_net_median_sale_price": years_with(net_median, ipv_price),
        "years_net_young_sale_price": years_with(net_young, ipv_price),
        "net_rate_avg": pts(tw100, 1, since=2000), "net_rate_67": pts(tw67, 1, since=2000), "tax_wedge": pts(wedge, 1, since=2000),
        "pay": {"gross_avg": pts(wage_all, 0), "net_avg": pts(net_avg, 0), "gross_median": pts(median, 0),
                "net_median": pts(net_median, 0), "gross_young": pts(young_pay, 0), "net_young": pts(net_young, 0)},
        "effort_pct": pts(effort, 1),
        "peers": {key: {geo: pts({int(p): v for p, v in table.get(geo, {}).items()}, 1) for geo in PEERS_EUROSTAT} for key, table in burden.items()},
        "residual_pps": {
            geo: pts({int(p): v * (1 - burden["cost_share"][geo][p] / 100) for p, v in income_pps.get(geo, {}).items()
                      if p in burden["cost_share"].get(geo, {})}, 0)
            for geo in PEERS_EUROSTAT
        },
        "income_pps": {geo: pts({int(p): v for p, v in income_pps.get(geo, {}).items()}, 0) for geo in PEERS_EUROSTAT},
    }

    # 12. Base years: every headline is also given from the 2000 start, the 2007 peak, the 2013 trough and 2019.
    bases = (2000, 2007, 2013, 2019)
    last_y = max(home)
    def change(series: dict[int, float], base: int) -> float | None:
        return r((series[last_y] / series[base] - 1) * 100, 1) if base in series and last_y in series else None
    windows = [(2003, 2007), (2008, 2012), (2013, 2019), (2020, max(net_households))]
    base_block = {
        "last_year": last_y, "bases": list(bases),
        "years_appraisal": {str(b): r(years_ine_all.get(b), 2) for b in (*bases, last_y)},
        "years_sale": {str(b): r(years_ipv.get(b), 2) for b in (*bases, last_y) if b in years_ipv},
        "years_household_income": {str(b): r(years_bde.get(b), 2) for b in (*bases, last_y)},
        "sale_price_change_pct": {str(b): change(ipv, b) for b in bases if b in ipv},
        "appraisal_change_pct": {str(b): change(price_m2, b) for b in bases},
        "wage_change_pct": {str(b): change(wage_all, b) for b in bases if b in wage_all},
        "completed_per_household": [window(a, b) for a, b in windows],
    }

    # 13. Composition: the household-forming cohort (25-39) and what drives new households in each period.
    cohort_parts = [s.raw(f"demo_pjangroup.{age}") for age in ("Y25-29", "Y30-34", "Y35-39")]
    pop_total = s.raw("demo_pjangroup.TOTAL")
    cohort = {}
    for geo in PEERS_EUROSTAT:
        years_c = set.intersection(*(set(part.get(geo, {})) for part in cohort_parts))
        cohort[geo] = {
            "persons": pts({int(y): sum(part[geo][y] for part in cohort_parts) for y in years_c}, 0),
            "share_pct": pts({int(y): sum(part[geo][y] for part in cohort_parts) / pop_total[geo][y] * 100 for y in years_c if y in pop_total.get(geo, {})}, 2),
        }
    def decompose(a: int, b: int) -> dict | None:
        if not all(y in households and y in mid_pop for y in (a, b)):
            return None
        size_a = mid_pop[a] / households[a]
        same = mid_pop[b] / size_a
        total = households[b] - households[a]
        return {"from": a, "to": b, "total": r(total, 0), "population_effect": r(same - households[a], 0),
                "size_effect": r(households[b] - same, 0), "per_year": r(total / (b - a), 0)}
    composition = {"cohort_25_39": cohort,
                   "decomposition": [d for d in (decompose(2002, 2007), decompose(2007, 2013), decompose(2013, 2019), decompose(2019, max(y for y in households if y in mid_pop))) if d]}

    # 14. Distribution: overburden by income quintile and age, tenure above and below the poverty line.
    quint = {q: s.raw(f"ilc_lvho07b.{q}") for q in ("TOTAL", "QU1", "QU2", "QU3", "QU4", "QU5")}
    ages = {a: s.raw(f"ilc_lvho07a.{a}") for a in ("TOTAL", "Y_LT18", "Y15-29", "Y18-64", "Y_GE65")}
    tenure_pov = {(ten, pov): s.raw(f"ilc_lvho02.{ten}", where={"rskpovth": pov}) for ten in ("OWN", "RENT_MKT") for pov in ("A_60", "B_60")}
    def latest_by_geo(table: dict[str, dict[str, float]]) -> dict[str, dict]:
        return {geo: {"year": int(max(v)), "value": r(v[max(v)], 1)} for geo, v in table.items() if v}
    distribution = {
        "overburden_quintile": {q: latest_by_geo(v) for q, v in quint.items()},
        "overburden_quintile_es_series": {q: pts({int(p): x for p, x in v.get("ES", {}).items()}, 1) for q, v in quint.items()},
        "overburden_age": {a: latest_by_geo(v) for a, v in ages.items()},
        "tenure_poverty": {f"{ten}|{pov}": latest_by_geo(v) for (ten, pov), v in tenure_pov.items()},
        "rent_mkt_below_poverty_es": pts({int(p): x for p, x in tenure_pov[("RENT_MKT", "B_60")].get("ES", {}).items()}, 1),
        "rent_mkt_above_poverty_es": pts({int(p): x for p, x in tenure_pov[("RENT_MKT", "A_60")].get("ES", {}).items()}, 1),
    }

    # 15. Territory: median rent of tenants (SERPAVI, IRPF) against the region's net household income (ECV of the
    # following year, which records that year's income), and the share of households renting at market price.
    rent_reg = s.raw("serpavi_alquiler_mensual_mediano_vc")
    income_reg = s.raw("ecv_renta_neta_media_hogar")
    renters = s.raw("ecv_hogares_alquiler_mercado_pct")
    rent_rows = []
    for code, name in REGIONS.items():
        rents_c = {int(p): v for p, v in rent_reg.get(code, {}).items()}
        inc = {int(p) - 1: v for p, v in income_reg.get(code, {}).items()}  # ECV survey year t -> income of t-1
        both = sorted(y for y in rents_c if y in inc)
        if not both:
            continue
        y1 = both[-1]
        y0 = 2015 if 2015 in both else both[0]
        rent_rows.append({
            "code": code, "name": name, "year": y1, "rent_month": r(rents_c[y1], 0), "income_year": r(inc[y1], 0),
            "burden_pct": r(rents_c[y1] * 12 / inc[y1] * 100, 1), "burden_base_year": y0,
            "burden_base_pct": r(rents_c[y0] * 12 / inc[y0] * 100, 1) if y0 < y1 else None,
            "rent_change_pct": r((rents_c[y1] / rents_c[y0] - 1) * 100, 1) if y0 < y1 else None,
            "income_change_pct": r((inc[y1] / inc[y0] - 1) * 100, 1) if y0 < y1 else None,
            "renters_pct": r(renters.get(code, {}).get(str(y1 + 1)), 1),
        })
    es_income = {int(p) - 1: v for p, v in income_reg.get("ES", {}).items()}
    territory = {"rows": sorted(rent_rows, key=lambda row: -row["burden_pct"]),
                 "renters_es_pct": r(renters.get("ES", {}).get(str(max(int(p) for p in renters.get("ES", {"0": 0})))), 1),
                 "income_es": pts(es_income, 0)}

    segments_block = segments(s, conn, net_young, rate, tax_rows)

    # 11. Money in versus money out: taxes on immovable property and on its transfer vs public housing spending.
    rev = {code: s.raw(f"TAX_REV.S13.{code}") for code in ("T_4100", "T_4400", "T_4000")}
    to_eu = {"ESP": "ES", "DEU": "DE", "FRA": "FR", "ITA": "IT", "PRT": "PT", "OECD": None}
    money = []
    for geo, eu in to_eu.items():
        r41 = {int(p): v for p, v in rev["T_4100"].get(geo, {}).items()}
        r44 = {int(p): v for p, v in rev["T_4400"].get(geo, {}).items()}
        sp = {row["year"]: row for row in spending.get(eu, [])} if eu else {}
        years_common = sorted(set(r41) & set(r44) & (set(sp) if eu else set(r41)))
        if not years_common:
            continue
        last_year = years_common[-1]
        avg = lambda d, key=None: sum((d[y][key] if key else d[y]) for y in range(2015, 2020)) / 5 if all(y in d for y in range(2015, 2020)) else None  # noqa: E731
        money.append({
            "geo": geo, "year": last_year,
            "recurrent_property": r(r41[last_year], 2), "transactions": r(r44[last_year], 2),
            "collected": r(r41[last_year] + r44[last_year], 2),
            "spent": r(sp[last_year]["total"], 2) if eu else None,
            "spent_development": r(sp[last_year]["development"], 2) if eu else None,
            "spent_allowances": r(sp[last_year]["allowances"], 2) if eu else None,
            "collected_2015_2019": r((avg(r41) or 0) + (avg(r44) or 0), 2) if avg(r41) is not None and avg(r44) is not None else None,
            "spent_2015_2019": r(avg(sp, "total"), 2) if eu and avg(sp, "total") is not None else None,
            "series_collected": pts({y: r41[y] + r44[y] for y in r41 if y in r44}, 2),
        })

    story = connected_story(completed, net_households, intercensal, years_bde, rate, credit_growth)

    sources = {}
    for source_id, releases in s.provenance.items():
        label, page = SOURCE_PAGES[source_id]
        retrieved = max((rel["retrieved_at"] or "" for rel in releases), default="") or None
        unique = {rel["indicator"]: rel for rel in releases}
        sources[source_id] = {"label": label, "page": page, "retrieved_at": retrieved, "releases": list(unique.values())}

    since_2013 = window(2013, max(net_households))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "storage": "SQLite housing-es.db: indicator_* contract (releases, revisions, evidence per value with sha256); "
        "built by scripts/ingest_housing_es.py",
        "headline": {
            "home_m2": HOME_M2,
            "last_year": last,
            "years_last": r(years_ine[last]),
            "years_2000": r(years_retro.get(2000)),
            "years_peak": r(years_ine_all[peak_year]), "peak_year": peak_year,
            "years_trough": r(years_ine_all[trough_year]), "trough_year": trough_year,
            "years_oecd_1995": r(years_oecd.get(1995)),
            "home_price_last": r(home[last], 0), "wage_last": r(wage_ine[last], 0),
            "completed_last": r(completed[max(completed)], 0), "completed_last_year": max(completed),
            "completed_peak": r(max(completed.values()), 0), "completed_peak_year": max(completed, key=completed.get),
            "since_2013": since_2013,
            "boom": window(first_balance, 2007),
            "bust": window(2008, 2012),
            "since_2008": window(2008, max(net_households)),
            "balance_last": balance[-1] if balance else None,
            "balance_peak": max(balance, key=lambda b: b["value"]) if balance else None,
        },
        "affordability": {
            "price_eur_m2": pts(price_m2, 1),
            "home_price_eur": pts(home, 0),
            "wage_ine_retro_eur": pts(wage_retro, 0),
            "wage_ine_eur": pts(wage_ine, 0),
            "wage_oecd_eur": pts(wage_oecd, 0, since=1995),
            "years_ine_retro": pts(years_retro),
            "years_ine": pts(years_ine),
            "years_oecd": pts(years_oecd),
            "years_bde_household": pts(years_bde),
            "effort_pct": pts(effort, 1),
            "mortgage_rate_pct": pts(rate),
        },
        "peers_price_income": {geo: pts({int(p): v for p, v in hp_income.get(geo, {}).items()}, 1, since=1980) for geo in PEERS_OECD},
        "peers_price_rent": {geo: pts({int(p): v for p, v in hp_rent.get(geo, {}).items()}, 1, since=1980) for geo in PEERS_OECD},
        "peers_real_price": {geo: pts({int(p): v for p, v in hp_real.get(geo, {}).items()}, 1, since=1980) for geo in PEERS_OECD},
        "supply": {
            "completed_total": pts(completed, 0),
            "completed_free": pts(free, 0),
            "completed_protected": pts(protected, 0),
            "starts": pts(starts, 0, since=1991),
            "permits": pts(permits, 0),
            "households_epa": pts(households, 0),
            "net_households_epa": pts(net_households, 0),
            "census_households": pts(census_hh, 0),
            "intercensal": intercensal,
            "cumulative_balance": balance,
        },
        "census_stock": census_stock,
        "leaving_home_age": {geo: pts({int(p): v for p, v in leave.get(geo, {}).items()}, 1) for geo in PEERS_EUROSTAT},
        "tenure": {
            "census": [{"year": y, **{k: r(v, 1) for k, v in row.items()}} for y, row in sorted(census_tenure.items())],
            "census_early": sorted(early_census, key=lambda e: e["year"]),
            "survey_owner": pts(survey_owner, 1),
            "survey_rent": pts(survey_rent, 1),
            "silc_owner": {geo: pts({int(p): v for p, v in silc_own.get(geo, {}).items()}, 1) for geo in PEERS_EUROSTAT},
            "silc_rent_market": {geo: pts({int(p): v for p, v in silc_rent_mkt.get(geo, {}).items()}, 1) for geo in PEERS_EUROSTAT},
            "young": young,
        },
        "taxes": taxes,
        "public_spending_pct_gdp": spending,
        "social_rental_stock": social,
        "sale_prices": sale_prices,
        "rents": rents,
        "regions": region_block,
        "drivers": drivers,
        "story": story,
        "capacity": capacity,
        "bases": base_block,
        "composition": composition,
        "distribution": distribution,
        "territory": territory,
        "segments": segments_block,
        "money": money,
        "norms": norms,
        "sources": sources,
    }


TENURES = ["OWN_NL", "OWN_L", "RENT_MKT", "RENT_FR"]
ECV_TENURE = {"Propiedad sin hipoteca": "OWN_NL", "Propiedad con hipoteca": "OWN_L", "Alquiler a precio de mercado": "RENT_MKT",
              "Alquiler inferior al precio de mercado": "RENT_FR", "Cesión": "RENT_FR"}
ECV_AGES = ["De 16 a 29 años", "De 30 a 44 años", "De 45 a 64 años", "65 y más años"]
AGE_LABEL = {"De 16 a 29 años": "16–29", "De 30 a 44 años": "30–44", "De 45 a 64 años": "45–64", "65 y más años": "65+", "Total": "Total"}
# INE province -> (city municipality code, NUTS 2 of the province's region); the cities SERPAVI ships by municipality.
CITIES = {"28": ("28079", "ES30"), "08": ("08019", "ES51"), "07": ("07040", "ES53"), "46": ("46250", "ES52"),
          "41": ("41091", "ES61"), "29": ("29067", "ES61"), "50": ("50297", "ES24"), "48": ("48020", "ES21")}
MORTGAGE_LTV, MORTGAGE_YEARS = 0.8, 25


def mortgage_payment(principal: float, annual_rate_pct: float, years: int = MORTGAGE_YEARS) -> float:
    """Monthly payment of a fixed-rate annuity loan (French amortisation)."""
    i, n = annual_rate_pct / 100 / 12, years * 12
    return principal * i / (1 - (1 + i) ** -n) if i else principal / n


def segments(s: "Store", conn: sqlite3.Connection, net_young: dict[int, float], rate: dict[int, float], tax_rows: list[dict]) -> dict:
    """Who pays for housing: tenure x age (ECV), overburden by tenure (EU-SILC), young people still at home, rents in the big
    cities against the rest of their province (SERPAVI by municipality), and the shared typical cases of
    docs/etl/sprints/VIZ-SEGMENTOS-20261019/README.md, each with the national mean and median beside it."""
    pop = {t: s.raw(f"ilc_lvho02.{t}", where={"rskpovth": "TOTAL"}) for t in TENURES}
    over = {t: s.raw(f"ilc_lvho07c.{t}") for t in [*TENURES, "TOTAL"]}
    year = max(int(p) for p in over["TOTAL"]["ES"] if all(p in pop[t]["ES"] for t in TENURES) and all(p in over[t]["ES"] for t in TENURES))
    y = str(year)
    mean_share = s.raw("ilc_mded01._T")["ES"][y]
    median_share = s.raw("ilc_lvho08a._T")["ES"][y]
    tenure = [{"key": t, "pop_pct": r(pop[t]["ES"][y], 1), "overburden_pct": r(over[t]["ES"][y], 1),
               "overburden_eu": r(over[t].get("EU27_2020", {}).get(y), 1)} for t in TENURES]

    # Tenure by age of the household's reference person (INE ECV t=9994): latest year and 2008, before the crisis.
    rows = conn.execute(
        """
        SELECT sv.dimensions_json, o.period_label, o.value_decimal FROM indicator_definitions d
        JOIN indicator_releases r ON r.indicator_id = d.indicator_id
        JOIN indicator_series_versions sv ON sv.indicator_release_id = r.indicator_release_id
        JOIN indicator_observation_versions o ON o.indicator_series_version_id = sv.indicator_series_version_id
        WHERE d.indicator_code = ? AND o.revision_state != 'deleted' AND o.value_decimal IS NOT NULL
          AND r.indicator_release_id = (SELECT r2.indicator_release_id FROM indicator_releases r2 WHERE r2.indicator_id = d.indicator_id
                                        ORDER BY r2.source_snapshot_date DESC, r2.created_at DESC LIMIT 1)
        """, ("ecv_hogares_tenencia_edad_pct",)).fetchall()
    s.raw("ecv_hogares_tenencia_edad_pct")
    cells: dict[tuple[int, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for dims, period, value in rows:
        d = json.loads(dims)
        if d["tenencia"] in ECV_TENURE:
            cells[(int(period), d["edad"])][ECV_TENURE[d["tenencia"]]] += float(value)
    # The ECV splits owners by mortgage only from 2010: the comparison year is the first with all four groups.
    ecv_years = sorted({k[0] for k in cells if "OWN_NL" in cells[k] and "OWN_L" in cells[k]})
    ecv_last, ecv_first = ecv_years[-1], ecv_years[0]
    age_tenure = {
        "year": ecv_last, "first_year": ecv_first,
        "rows": [{"age": AGE_LABEL[a], "shares": {t: r(cells[(ecv_last, a)][t], 1) for t in TENURES},
                  "shares_first": {t: r(cells[(ecv_first, a)][t], 1) for t in TENURES}} for a in [*ECV_AGES, "Total"]],
    }

    # Young people living with their parents (EU-SILC), with the EU average beside Spain.
    home = {a: s.raw(f"ilc_lvps08.{a}") for a in ("Y16-29", "Y18-34", "Y25-34")}
    at_home = {a: {geo: {"year": int(max(v)), "value": r(v[max(v)], 1)} for geo, v in table.items() if geo in ("ES", "EU27_2020") and v}
               for a, table in home.items()}

    # Big cities against the rest of their province (SERPAVI, IRPF): the city's median and the contract-weighted mean of the
    # other municipalities' medians (a median of the rest cannot be rebuilt from municipal medians: an approximation).
    rent_m = s.raw("serpavi_alquiler_mensual_mediano_vc_municipio")
    count_m = s.raw("serpavi_viviendas_alquiladas_vc_municipio")
    wage_reg = {code: annual(v) for code, v in s.raw("etcl_coste_salarial_ccaa").items()}
    income_reg = s.raw("ecv_renta_neta_media_hogar")
    young_year = max(net_young)

    def young_net_in(region: str, yr: int) -> tuple[int, float] | None:
        """Net pay of 25-34 year-olds (Spain, EES) scaled by the region's wage level (ETCL) in the same year."""
        wy = min(yr, young_year)
        if wy not in net_young or wy not in wage_reg.get(region, {}) or wy not in wage_reg.get("ES", {}):
            return None
        return wy, net_young[wy] * wage_reg[region][wy] / wage_reg["ES"][wy]

    cities = []
    for prov, (city, region) in CITIES.items():
        if city not in rent_m:
            continue
        cy = max(int(p) for p in rent_m[city])
        rest = [(rent_m[m][str(cy)], count_m.get(m, {}).get(str(cy))) for m in rent_m
                if m != city and m.startswith(prov) and str(cy) in rent_m[m] and count_m.get(m, {}).get(str(cy))]
        rest_n = sum(n for _v, n in rest)
        pay = young_net_in(region, cy)
        row = {"province": prov, "code": city, "region": region, "year": cy,
               "rent_month": r(rent_m[city][str(cy)], 0), "rent_2019": r(rent_m[city].get("2019"), 0),
               "contracts": r(count_m.get(city, {}).get(str(cy)), 0),
               "rest_rent_month": r(sum(v * n for v, n in rest) / rest_n, 0) if rest_n else None,
               "rest_contracts": r(rest_n, 0) if rest_n else None, "rest_municipalities": len(rest)}
        if pay:
            row["young_net_year"], row["young_net"] = pay[0], r(pay[1], 0)
            row["burden_young_pct"] = r(row["rent_month"] * 12 / pay[1] * 100, 1)
            row["rest_burden_young_pct"] = r(row["rest_rent_month"] * 12 / pay[1] * 100, 1) if row["rest_rent_month"] else None
        cities.append(row)
    by_city = {row["code"]: row for row in cities}
    rent_reg = s.raw("serpavi_alquiler_mensual_mediano_vc")
    regions = []
    for code, name in REGIONS.items():
        if not rent_reg.get(code):
            continue
        ry = max(int(p) for p in rent_reg[code])
        pay = young_net_in(code, ry)
        if pay:
            regions.append({"code": code, "name": name, "year": ry, "rent_month": r(rent_reg[code][str(ry)], 0), "young_net_year": pay[0],
                            "young_net": r(pay[1], 0), "burden_young_pct": r(rent_reg[code][str(ry)] * 12 / pay[1] * 100, 1)})
    regions.sort(key=lambda row: -row["burden_young_pct"])

    # Typical cases (README §3). Survey year t of the ECV and the EU-SILC records the income of t-1; costs are of year t.
    s.raw("ecv_renta_neta_media_hogar_tenencia")
    ten_rows = conn.execute(
        """
        SELECT sv.dimensions_json, o.period_label, o.value_decimal FROM indicator_definitions d
        JOIN indicator_releases r ON r.indicator_id = d.indicator_id
        JOIN indicator_series_versions sv ON sv.indicator_release_id = r.indicator_release_id
        JOIN indicator_observation_versions o ON o.indicator_series_version_id = sv.indicator_series_version_id
        WHERE d.indicator_code = 'ecv_renta_neta_media_hogar_tenencia' AND o.revision_state != 'deleted'
          AND r.indicator_release_id = (SELECT r2.indicator_release_id FROM indicator_releases r2 WHERE r2.indicator_id = d.indicator_id
                                        ORDER BY r2.source_snapshot_date DESC, r2.created_at DESC LIMIT 1)
        """).fetchall()
    inc_t: dict[str, dict[int, float]] = defaultdict(dict)
    for dims, period, value in ten_rows:
        inc_t[json.loads(dims)["tenencia"]][int(period)] = float(value)
    t_ecv = max(inc_t["Alquiler a precio de mercado"])
    ecv_reg = lambda code: income_reg[code][str(t_ecv)] / income_reg["ES"][str(t_ecv)]  # noqa: E731
    cost = s.raw("ilc_mded03.TOTAL.TOTAL")["ES"]
    cost_own_65 = s.raw("ilc_mded03.OWN.A2_GE1_GE65")["ES"]
    ppp = s.raw("prc_ppp_ind._T")["ES"]
    t_cost = max(int(p) for p in cost if p in cost_own_65)
    ppp_y, ppp_v = max((int(p), v) for p, v in ppp.items() if int(p) <= t_cost)
    eur = lambda pps: pps * ppp_v  # noqa: E731
    over_of = lambda t: r(over[t]["ES"][y], 1)  # noqa: E731

    def case(key: str, monthly_cost: float, income_year: float, **extra) -> dict:
        return {"key": key, "cost_month": r(monthly_cost, 0), "income_year": r(income_year, 0),
                "share_pct": r(monthly_cost * 12 / income_year * 100, 1), "left_month": r(income_year / 12 - monthly_cost, 0), **extra}

    national_income = income_reg["ES"][str(t_ecv)]
    cases = [case("national", eur(cost[str(t_cost)]), national_income, mean_share_pct=r(mean_share, 1),
                  median_share_pct=r(median_share, 1), overburden_pct=over_of("TOTAL"), survey_year=t_cost)]
    madrid = by_city.get("28079")
    if madrid and madrid.get("young_net"):
        cases.append(case("p1_young_renter_madrid", madrid["rent_month"], madrid["young_net"], rent_year=madrid["year"],
                          pay_year=madrid["young_net_year"], overburden_pct=over_of("RENT_MKT")))
    if madrid and madrid.get("rest_rent_month"):
        cases.append(case("p2_family_renter_metro", madrid["rest_rent_month"], inc_t["Alquiler a precio de mercado"][t_ecv] * ecv_reg("ES30"),
                          rent_year=madrid["year"], survey_year=t_ecv, overburden_pct=over_of("RENT_MKT")))
    price_md = annual(s.raw("valor_tasado_vivienda_libre_ccaa")["ES30"])
    py = max(y_ for y_ in price_md if y_ in rate)
    price = price_md[py] * HOME_M2
    payment = mortgage_payment(price * MORTGAGE_LTV, rate[py])
    itp = [row for row in tax_rows if row["key"] == "itp_vivienda_usada" and row["scope"] == "ES-MD"]
    itp_pct = max(itp, key=lambda row: row["year"])["value"] if itp else None
    income_buyer = inc_t["Propiedad con hipoteca"][t_ecv] * ecv_reg("ES30")
    upfront = price * (1 - MORTGAGE_LTV) + (price * itp_pct / 100 if itp_pct is not None else 0)
    cases.append(case("p2_family_buyer_madrid", payment, income_buyer, price_year=py, home_price=r(price, 0), rate_pct=r(rate[py], 2),
                      ltv_pct=MORTGAGE_LTV * 100, years=MORTGAGE_YEARS, itp_pct=itp_pct, upfront=r(upfront, 0),
                      upfront_years_income=r(upfront / income_buyer, 1), survey_year=t_ecv, overburden_pct=over_of("OWN_L")))
    cases.append(case("p4_retired_owner_interior", eur(cost_own_65[str(t_cost)]), inc_t["Propiedad sin hipoteca"][t_ecv] * ecv_reg("ES41"),
                      survey_year=t_cost, overburden_pct=over_of("OWN_NL")))
    cases.append({"key": "e_living_with_parents", "at_home_pct": at_home["Y25-34"]["ES"]["value"], "at_home_eu_pct": at_home["Y25-34"]["EU27_2020"]["value"],
                  "year": at_home["Y25-34"]["ES"]["year"]})
    return {
        "year": year, "overburden_total": r(over["TOTAL"]["ES"][y], 1), "overburden_total_eu": r(over["TOTAL"].get("EU27_2020", {}).get(y), 1),
        "cost_share_mean": r(mean_share, 1), "cost_share_median": r(median_share, 1),
        "tenure": tenure, "age_tenure": age_tenure, "at_home": at_home, "cities": cities, "regions": regions,
        "young_net_es": {"year": young_year, "value": r(net_young[young_year], 0)},
        "assumptions": {"ppp_year": ppp_y, "eur_per_pps": r(ppp_v, 4), "cost_year": t_cost, "ecv_year": t_ecv},
        "cases": cases,
    }


def purchase_taxes(rows: list[dict], home: dict[int, float], conn: sqlite3.Connection) -> dict | None:
    """Buyer's taxes on a 90 m² home at the national average appraisal price of each year."""
    if not rows:
        return None
    rules = []
    for (meta,) in conn.execute(
        """
        SELECT r.source_metadata_json FROM indicator_definitions d JOIN indicator_releases r USING (indicator_id)
        WHERE d.dataset_code = 'purchase_taxes_es' ORDER BY r.source_snapshot_date DESC, r.created_at DESC LIMIT 1
        """
    ):
        rules = json.loads(meta or "{}").get("rules", [])

    def rate(key: str, year: int, scope: str) -> dict | None:
        exact = [row for row in rows if row["key"] == key and row["year"] == year and row["scope"] == scope]
        fallback = [row for row in rows if row["key"] == key and row["year"] == year and row["scope"] == "ES"]
        return (exact or fallback or [None])[0]

    scenarios = []
    for year in sorted({row["year"] for row in rows}):
        price = home.get(year) or home.get(max(y for y in home if y <= year))
        scopes = sorted({row["scope"] for row in rows if row["year"] == year} - {"ES"}) or ["ES"]
        for scope in ["ES", *[sc for sc in scopes if sc != "ES"]]:
            for kind, keys in (("nueva", ["iva_vivienda_nueva", "ajd_vivienda_nueva"]), ("usada", ["itp_vivienda_usada"])):
                parts = [rate(k, year, scope) for k in keys]
                if any(p is None for p in parts) or any(p["unit"] != "pct" for p in parts):
                    continue
                if scope != "ES" and all(p["scope"] == "ES" for p in parts):
                    continue  # nothing regional for this scope: the ES row already covers it
                pct = sum(p["value"] for p in parts)
                scenarios.append({
                    "year": year, "scope": scope, "kind": kind, "home_price": r(price, 0), "pct": r(pct, 2),
                    "eur": r(price * pct / 100, 0),
                    "parts": [{"key": p["key"], "scope": p["scope"], "pct": p["value"], "eur": r(price * p["value"] / 100, 0)} for p in parts],
                })
    return {"rates": rows, "scenarios": scenarios, "rules": rules}


def write_csv(data: dict, path: Path) -> None:
    rows: list[tuple] = []
    aff = data["affordability"]
    for key, src in (("price_eur_m2", "mivau_boletin"), ("home_price_eur", "mivau_boletin"), ("wage_ine_retro_eur", "ine_tempus"),
                     ("wage_ine_eur", "ine_tempus"), ("wage_oecd_eur", "oecd_dbnomics"), ("years_ine_retro", "mivau+ine"),
                     ("years_ine", "mivau+ine"), ("years_oecd", "mivau+oecd"), ("years_bde_household", "bde_indicadores_vivienda"),
                     ("effort_pct", "bde_indicadores_vivienda"), ("mortgage_rate_pct", "bde_indicadores_vivienda")):
        rows.extend((src, key, "ES", p["year"], p["value"]) for p in aff[key])
    for block in ("peers_price_income", "peers_price_rent", "peers_real_price"):
        for geo, points in data[block].items():
            rows.extend(("oecd_dbnomics", block, geo, p["year"], p["value"]) for p in points)
    for key, points in data["supply"].items():
        if key == "intercensal":
            rows.extend(("bde_indicadores_vivienda", f"hogares_censo_por_anio_{i['from']}_{i['to']}", "ES", i["to"], i["per_year"]) for i in points)
            continue
        src = "mivau_boletin" if key.startswith("completed") else "derivado" if key == "cumulative_balance" else "bde_indicadores_vivienda"
        rows.extend((src, key, "ES", p["year"], p["value"]) for p in points)
    for row in data["census_stock"]:
        rows.extend(("bde_indicadores_vivienda", f"censo_viviendas_{k}", "ES", row["year"], row[k]) for k in ("total", "principales", "secundarias", "desocupadas"))
    for geo, points in data["leaving_home_age"].items():
        rows.extend(("eurostat_sdmx", "edad_emancipacion", geo, p["year"], p["value"]) for p in points)
    for row in data["tenure"]["census"]:
        rows.extend(("bde_indicadores_vivienda", f"censo_tenencia_{k}_pct", "ES", row["year"], row[k]) for k in ("owner", "rent", "other"))
    for row in data["tenure"]["census_early"]:
        rows.extend(("vclc_housing_curated", f"censo_tenencia_{k}_pct", "ES", row["year"], row.get(k)) for k in ("owner", "rent", "other") if row.get(k) is not None)
    rows.extend(("bde_indicadores_vivienda", "encuesta_tenencia_propiedad_pct", "ES", p["year"], p["value"]) for p in data["tenure"]["survey_owner"])
    rows.extend(("bde_indicadores_vivienda", "encuesta_tenencia_alquiler_pct", "ES", p["year"], p["value"]) for p in data["tenure"]["survey_rent"])
    for key in ("silc_owner", "silc_rent_market"):
        for geo, points in data["tenure"][key].items():
            rows.extend(("eurostat_sdmx", key, geo, p["year"], p["value"]) for p in points)
    rows.extend(("vclc_housing_curated", f"propiedad_{y['source_key']}_{y['age_group']}", "ES", y["year"], y["value"]) for y in data["tenure"]["young"])
    for geo, points in data["public_spending_pct_gdp"].items():
        for p in points:
            rows.extend(("eurostat_sdmx", f"gasto_vivienda_{k}_pct_pib", geo, p["year"], p[k]) for k in ("development", "allowances", "total"))
    rows.extend(("vclc_housing_curated", "vivienda_social_alquiler_pct", row["country"], row["year"] or "ultimo_de_cada_pais", row["value"]) for row in data["social_rental_stock"])
    for key in ("appraisal_idx", "transactions_idx", "ipv_idx", "transactions_eur"):
        rows.extend(("mivau_boletin" if key != "ipv_idx" else "ine_tempus", f"precio_{key}", "ES", p["year"], p["value"]) for p in data["sale_prices"][key])
    for key in ("ipva_idx", "wage_idx", "cpi_idx", "ipc_rent_yoy", "hicp_rent_nominal_es"):
        rows.extend(("ine/eurostat", f"alquiler_{key}", "ES", p["year"], p["value"]) for p in data["rents"][key])
    for geo, points in data["rents"]["hicp_rent_real"].items():
        rows.extend(("eurostat_sdmx", "alquiler_real_ipca", geo, p["year"], p["value"]) for p in points)
    for row in data["regions"]["rows"]:
        for key in ("completed", "net_households", "gap", "gap_per_1000", "ratio", "price_m2", "wage", "rent_change_2015", "tourist_pct"):
            rows.append(("derivado", f"region_{key}", row["code"], data["regions"]["to"], row[key]))
        rows.extend(("mivau+ine", "region_anios_salario", row["code"], y, v) for y, v in row["years_salary"].items())
    dr = data["drivers"]
    for key in ("credit_pct_gdp", "natural_growth_per_1000_es", "population_es"):
        rows.extend(("bde/eurostat", key, "ES", p["year"], p["value"]) for p in dr[key])
    for key in ("net_migration_per_1000", "population_growth_per_1000", "household_size", "platform_nights_per_capita"):
        for geo, points in dr[key].items():
            rows.extend(("eurostat_sdmx", key, geo, p["year"], p["value"]) for p in points)
    cap = data["capacity"]
    for key in ("years_gross_avg", "years_net_avg", "years_gross_median", "years_net_median", "years_net_young",
                "years_net_median_sale_price", "years_net_young_sale_price", "net_rate_avg", "net_rate_67", "tax_wedge", "effort_pct"):
        rows.extend(("derivado", f"capacidad_{key}", "ES", p["year"], p["value"]) for p in cap[key])
    for key, by_geo in cap["peers"].items():
        for geo, points in by_geo.items():
            rows.extend(("eurostat_sdmx", f"capacidad_{key}", geo, p["year"], p["value"]) for p in points)
    for geo, points in cap["residual_pps"].items():
        rows.extend(("eurostat_sdmx", "capacidad_renta_tras_vivienda_pps", geo, p["year"], p["value"]) for p in points)
    for row in data["money"]:
        for key in ("recurrent_property", "transactions", "collected", "spent", "spent_development", "spent_allowances"):
            rows.append(("oecd+eurostat", f"dinero_{key}_pct_pib", row["geo"], row["year"], row[key]))
    for geo, block in data["composition"]["cohort_25_39"].items():
        rows.extend(("eurostat_sdmx", "cohorte_25_39_personas", geo, p["year"], p["value"]) for p in block["persons"])
        rows.extend(("eurostat_sdmx", "cohorte_25_39_pct_poblacion", geo, p["year"], p["value"]) for p in block["share_pct"])
    for q, by_geo in data["distribution"]["overburden_quintile"].items():
        rows.extend(("eurostat_sdmx", f"sobrecarga_quintil_{q}", geo, v["year"], v["value"]) for geo, v in by_geo.items())
    for a, by_geo in data["distribution"]["overburden_age"].items():
        rows.extend(("eurostat_sdmx", f"sobrecarga_edad_{a}", geo, v["year"], v["value"]) for geo, v in by_geo.items())
    for key, by_geo in data["distribution"]["tenure_poverty"].items():
        rows.extend(("eurostat_sdmx", f"tenencia_{key.replace('|', '_')}", geo, v["year"], v["value"]) for geo, v in by_geo.items())
    for row in data["territory"]["rows"]:
        rows.append(("mivau+ine", "alquiler_mediano_mes", row["code"], row["year"], row["rent_month"]))
        rows.append(("mivau+ine", "alquiler_pct_renta_hogar", row["code"], row["year"], row["burden_pct"]))
        rows.append(("ine_tempus", "hogares_alquiler_mercado_pct", row["code"], row["year"] + 1, row["renters_pct"]))
    seg = data["segments"]
    rows.append(("eurostat_sdmx", "gasto_vivienda_pct_renta_media", "ES", seg["year"], seg["cost_share_mean"]))
    rows.append(("eurostat_sdmx", "gasto_vivienda_pct_renta_mediana", "ES", seg["year"], seg["cost_share_median"]))
    for t in seg["tenure"]:
        rows.append(("eurostat_sdmx", f"poblacion_tenencia_{t['key']}_pct", "ES", seg["year"], t["pop_pct"]))
        rows.append(("eurostat_sdmx", f"sobrecarga_tenencia_{t['key']}", "ES", seg["year"], t["overburden_pct"]))
        rows.append(("eurostat_sdmx", f"sobrecarga_tenencia_{t['key']}", "EU27_2020", seg["year"], t["overburden_eu"]))
    at = seg["age_tenure"]
    for row in at["rows"]:
        for key, yr in (("shares", at["year"]), ("shares_first", at["first_year"])):
            rows.extend(("ine_tempus", f"hogares_edad_{row['age']}_tenencia_{t}_pct", "ES", yr, v) for t, v in row[key].items())
    for age, by_geo in seg["at_home"].items():
        rows.extend(("eurostat_sdmx", f"viven_con_sus_padres_{age}_pct", geo, v["year"], v["value"]) for geo, v in by_geo.items())
    for c in seg["cities"]:
        for key in ("rent_month", "rest_rent_month", "contracts", "rest_contracts", "young_net", "burden_young_pct", "rest_burden_young_pct"):
            if c.get(key) is not None:
                rows.append(("mivau+ine", f"ciudad_{key}", c["code"], c["year"], c[key]))
    for c in seg["cases"]:
        for key, value in c.items():
            if key != "key" and isinstance(value, (int, float)):
                rows.append(("derivado", f"caso_{c['key']}_{key}", "ES", c.get("survey_year") or c.get("rent_year") or c.get("year") or seg["year"], value))
    for row in data["story"]:
        rows.append(("derivado", "relato_viviendas_por_hogar_nuevo", "ES", row["year"], row["x"]))
        rows.append(("bde_indicadores_vivienda", "relato_anios_renta_hogar", "ES", row["year"], row["y"]))
    for scope, points in (data.get("norms") or {}).items():
        if scope != "state_laws":
            rows.extend(("boe_api", f"normas_vivienda_{scope}", "ES", p["year"], p["value"]) for p in points)
    for row in (data.get("taxes") or {}).get("rates", []):
        rows.append(("vclc_housing_curated", f"{row['key']}_{row['scope']}", row["scope"], row["year"], row["value"]))
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
            print(f"export_public_viz_housing: {args.db.name} not found; keeping committed artifact", file=sys.stderr)
            return 0
        raise SystemExit(f"missing {args.db}; run scripts/ingest_housing_es.py first")
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    data = build(conn)
    conn.close()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    write_csv(data, OUT_CSV)
    h = data["headline"]
    print(
        f"vivienda: {h['home_m2']} m² = {h['years_last']} años de salario en {h['last_year']} (pico {h['years_peak']} en "
        f"{h['peak_year']}); desde 2013 {h['since_2013']['completed']:.0f} terminadas vs {h['since_2013']['net_households']:.0f} "
        f"hogares; {OUT_JSON.stat().st_size // 1024} KB"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
