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

    def raw(self, indicator_code: str, source_id: str | None = None) -> dict[str, dict[str, float]]:
        """Latest release of an indicator as {geography_code: {period: value}}."""
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
        for geo, key, period, value in self.conn.execute(
            """
            SELECT s.geography_code, s.stable_series_key, o.period_label, o.value_decimal
            FROM indicator_observation_versions o JOIN indicator_series_versions s USING (indicator_series_version_id)
            WHERE o.indicator_release_id = ? AND o.revision_state != 'deleted' AND o.value_decimal IS NOT NULL
            """,
            (release_id,),
        ):
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
    silc_own = s.raw("ilc_lvho02.OWN")
    silc_rent_mkt = s.raw("ilc_lvho02.RENT_MKT")
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
        "norms": norms,
        "sources": sources,
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
