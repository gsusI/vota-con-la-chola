"""Housing inputs of /visualizaciones/sistema/ (slice 2), standard library only.

Everything here is read, not estimated: the baseline and the starting point come from official statistics already
published on the housing page (vivienda.json, sha256 in the model) or from the raw cache; the engine
(ui/site/app/visualizaciones/sistema/engine.mjs) adds deviations from it. Rules fixed before computing
(docs/etl/sprints/SISTEMA-COMPLEJO-20261019/README.md §13):
- Households: INE Proyección de Hogares (table 54562, households on 1 January 2026-2041); after 2041 they grow with the
  Ageing Report 2024 population at the 2041 household size. Check: INE 2026 vs EPA 2025 households within 2 %.
- Completions: held at the 2023-2025 average of the MIVAU series (free and protected separately). It is an assumption,
  not a projection: no official body projects completions.
- Dwelling stock: Censo 2021 total dwellings plus completions 2021-2025 (no demolitions). Tourist dwellings: INE
  experimental statistic, share of all dwellings in the latest period, times that stock.
- Market renters: ECV microdata cell (all ages, market-rent tenure) share of households, times EPA households.
- Young adults living with their parents: Eurostat ilc_lvps08 share of 25-34 (vivienda.json) times the population
  aged 25-34 (Eurostat demo_pjangroup); the pool is held at its last value.
- Migration context: Ageing Report net migration (thousands); the ±33 % variants move it by a third.
- Typical cases: rents, incomes and the Madrid purchase exactly as vivienda.json computes them (SERPAVI 2024 rents).
"""

from __future__ import annotations

import json
from pathlib import Path


def _pts(rows: list[dict]) -> dict[int, float]:
    return {int(p["year"]): float(p["value"]) for p in rows if p.get("value") is not None}


def _r(v, d=3):
    return None if v is None else round(float(v), d)


def ine_households(path: Path) -> dict[int, float]:
    for s in json.loads(path.read_text(encoding="utf-8")):
        if s["Nombre"].startswith("Total Nacional. Total"):
            return {int(x["Anyo"]): float(x["Valor"]) for x in s["Data"]}
    raise SystemExit("INE table 54562: national total not found")


def eurostat_value(path: Path, geo: str, age: str, year: int) -> float:
    d = json.loads(path.read_text(encoding="utf-8"))
    dims = d["id"]
    sizes = d["size"]
    pos = {"geo": geo, "age": age, "time": str(year)}
    idx = 0
    for dim, size in zip(dims, sizes):
        cat = d["dimension"][dim]["category"]["index"]
        k = cat[pos[dim]] if dim in pos else 0
        idx = idx * size + k
    return float(d["value"][str(idx)])


def housing_block(viv: dict, proh: Path, pjan: Path, ar_population: dict[int, float], ar_net_migration: dict[int, float],
                  years: list[int]) -> tuple[dict, list[dict]]:
    """Baseline, starting point and typical cases of the housing module; plus input gates."""
    base_year = years[0]
    sup = viv["supply"]
    completed = _pts(sup["completed_total"])
    protected = _pts(sup["completed_protected"])
    free = _pts(sup["completed_free"])
    epa = _pts(sup["households_epa"])
    avg_years = [base_year - 2, base_year - 1, base_year]
    q_free = sum(free[y] for y in avg_years) / 3 / 1000
    q_prot = sum(protected[y] for y in avg_years) / 3 / 1000

    ine = ine_households(proh)
    last_ine = max(ine)
    hh = []
    # Households at the end of year y = INE households on 1 January y+1 (the projection starts from the EPA).
    for y in years:
        if y + 1 in ine:
            hh.append(ine[y + 1] / 1000)
        else:
            hh.append(ine[last_ine] / 1000 * ar_population[y] / ar_population[last_ine - 1])
    gates = []
    gap = abs(ine[base_year + 1] / epa[base_year] - 1) * 100
    gates.append({"id": "households_ine_vs_epa", "ok": gap < 2.0, "value": _r(gap, 2),
                  "detail": f"INE household projection 1 Jan {base_year + 1} {ine[base_year + 1] / 1e6:.2f} M vs EPA {base_year} "
                            f"{epa[base_year] / 1e6:.2f} M"})

    census = {row["year"]: row for row in viv["census_stock"]}
    c21 = census[2021]
    stock = c21["total"] / 1000 + sum(completed[y] for y in range(2021, base_year + 1)) / 1000
    tourist_share = viv["regions"]["tourist_es"] / 100
    micro = viv["segments"]["micro"]
    cells = micro["cells"]

    def cell(geo: str, age: str, tenure: str) -> dict | None:
        return next((c for c in cells if c["geo"] == geo and c["age"] == age and c["tenure"] == tenure and c.get("s")), None)

    renters_share = cell("ES", "TOTAL", "RENT_MKT")["s"]["households_pct"][0] / 100
    at_home_share = viv["segments"]["at_home"]["Y25-34"]["ES"]["value"] / 100
    at_home_year = viv["segments"]["at_home"]["Y25-34"]["ES"]["year"]
    pop_2534 = (eurostat_value(pjan, "ES", "Y25-29", at_home_year) + eurostat_value(pjan, "ES", "Y30-34", at_home_year)) / 1000
    cases = {c["key"]: c for c in viv["segments"]["cases"]}
    p1, p2r, p2b = cases["p1_young_renter_madrid"], cases["p2_family_renter_metro"], cases["p2_family_buyer_madrid"]
    madrid = next(c for c in viv["segments"]["cities"] if c["code"] == "28079")

    # Rent effort of market renters by age, Spain and Comunidad de Madrid (ECV microdata cells with their intervals).
    ages = ["16-29", "30-44", "45-64", "65+"]
    effort = []
    for geo in ("ES", "ES30"):
        for age in ages:
            for tenure in ("RENT_MKT", "OWN_L"):
                c = next((x for x in cells if x["geo"] == geo and x["age"] == age and x["tenure"] == tenure), None)
                row = {"geo": geo, "age": age, "tenure": tenure, "n": c["n"] if c else 0}
                if c and c.get("s"):
                    row.update({"burden_mean": c["s"]["burden_mean"], "overburden_pct": c["s"]["overburden_pct"],
                                "households_pct": c["s"]["households_pct"]})
                effort.append(row)

    boom = viv["bases"]["boom"]
    credit = _pts(viv["drivers"]["credit_pct_gdp"])
    years_income = _pts(viv["affordability"]["years_ine_retro"])
    block = {
        "base_year": base_year,
        "households_k": [_r(v, 1) for v in hh],
        "households_source_last_year": last_ine,
        "completions_free_k": _r(q_free, 2),
        "completions_protected_k": _r(q_prot, 2),
        "completions_last_k": _r(completed[base_year] / 1000, 2),
        "net_households_next_k": _r((ine[base_year + 2] - ine[base_year + 1]) / 1000, 1),
        "net_households_2035_k": _r((ine[2036] - ine[2035]) / 1000, 1),
        "stock_k": _r(stock, 1),
        "stock_census_2021_k": _r(c21["total"] / 1000, 1),
        "principal_2021_k": _r(c21["principales"] / 1000, 1),
        "empty_2021_k": _r(c21["desocupadas"] / 1000, 1),
        "secondary_2021_k": _r(c21["secundarias"] / 1000, 1),
        "tourist_share": _r(tourist_share, 4),
        "tourist_period": viv["regions"]["tourist_period"],
        "tourist_k": _r(tourist_share * stock, 1),
        "renters_share": _r(renters_share, 4),
        "renters_k": _r(renters_share * epa[base_year] / 1000, 1),
        "at_home_share_2534": _r(at_home_share, 4),
        "at_home_year": at_home_year,
        "pop_2534_k": _r(pop_2534, 1),
        "at_home_k": _r(pop_2534 * at_home_share, 1),
        "net_migration_k": [_r(ar_net_migration.get(y, 0.0), 2) for y in years],
        "price_eur": viv["headline"]["home_price_last"],
        "cases": {
            "p1": {"rent_month": p1["cost_month"], "net_year": p1["income_year"], "share_pct": p1["share_pct"],
                   "rent_year": p1["rent_year"], "city_contracts": madrid["contracts"], "rent_2019": madrid["rent_2019"]},
            "p2_renter": {"rent_month": p2r["cost_month"], "net_year": p2r["income_year"], "share_pct": p2r["share_pct"],
                          "rent_year": p2r["rent_year"], "gross_year": p2r.get("gross_year")},
            "p2_buyer": {k: p2b.get(k) for k in ("cost_month", "income_year", "share_pct", "price_year", "home_price", "rate_pct",
                                                 "ltv_pct", "years", "itp_pct", "upfront", "upfront_years_income")},
        },
        "effort_cells": effort,
        "effort_year": micro["year"],
        "boom": {"from": boom["from"], "to": boom["to"], "credit_from": credit[boom["from"]], "credit_to": credit[boom["to"]],
                 "years_income_from": years_income[boom["from"]], "years_income_to": years_income[boom["to"]],
                 "completed": viv["headline"]["boom"]["completed"], "net_households": viv["headline"]["boom"]["net_households"]},
    }
    gates.append({"id": "stock_vs_households", "ok": 1.2 < stock / (epa[base_year] / 1000) < 1.5,
                  "value": _r(stock / (epa[base_year] / 1000), 3),
                  "detail": "dwellings per household (Censo 2021 + completions) between 1.2 and 1.5 (empty and secondary homes)"})
    gates.append({"id": "renters_share", "ok": 0.12 < renters_share < 0.25, "value": _r(renters_share, 3),
                  "detail": "market-rent households in the ECV microdata, share of all households"})
    return block, gates
