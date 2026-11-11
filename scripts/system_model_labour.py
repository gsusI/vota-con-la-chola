#!/usr/bin/env python3
"""Slice 3 of /visualizaciones/sistema/ (employment, immigration, healthcare capacity): baseline inputs.

Rules (docs/etl/sprints/SISTEMA-COMPLEJO-20261019/README.md §14), all offline from the raw cache:
- Population by age stage, 2025-2050: Eurostat EUROPOP2023 (proj_23np), baseline `BSL` and the migration variants
  `HMIGR` / `LMIGR` (the ones the Ageing Report 2024 uses). Stages 0-15 / 16-29 / 30-44 / 45-64 / 65-79 / 80+, plus
  5-24 for schooling. The simulator scales the variant differences linearly (an assumption the page states).
- Net migration by variant (proj_23nanmig) and the age profile of the extra migrants (HMIGR - BSL, 2026-2050).
- Employment rate of foreign citizens and of everyone by stage (Eurostat LFS lfsa_ergan, latest year), each stage
  weighting its five-year bands by the extra migrants' age profile.
- Health demand by age: public health spending per person by five-year band (Funcas DT 673, 2008, the Spanish profile
  in the health page's manual file), turned into one weight per stage with the 2025 population; the demographic index
  is the population weighted by those weights. Health, long-term care and education spending baselines and the
  migration sensitivities of total age-related spending: Ageing Report 2024 annex (sheet ESc).
- Doctors (practising per 100,000, Eurostat via sanidad.json) and the surgical waiting list (SISLE stock and mean wait,
  via sanidad.json); yearly exits from Little's law (stock x 365 / mean days), an approximation the page states.
- Employees and self-employed 2025 (Eurostat national accounts nama_10_pe) and the 2019-2025 backtest of employment of
  foreign citizens (lfsa_pganws).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from ingest_employment_es import xlsx_rows, xlsx_sheet  # noqa: E402

RAW = REPO_ROOT / "etl/data/raw/system_model"
PROJ = RAW / "eurostat_proj_23np_es.json"
NMIG = RAW / "eurostat_proj_23nanmig_es.json"
ERGAN = RAW / "eurostat_lfsa_ergan_es.json"
PGANWS = RAW / "eurostat_lfsa_pganws_es.json"
NAMA_PE = RAW / "eurostat_nama_10_pe_es.json"
PROFILE = REPO_ROOT / "etl/data/manual/health/perfil_gasto_edad.json"
EUROSTAT_API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
URLS = {
    "proj_23np": EUROSTAT_API + "proj_23np?geo=ES&sex=T&unit=PER&projection=BSL&projection=HMIGR&projection=LMIGR&time=2025..2050",
    "proj_23nanmig": EUROSTAT_API + "proj_23nanmig?geo=ES&sex=T&unit=PER&projection=BSL&projection=HMIGR&projection=LMIGR&time=2025..2050",
    "lfsa_ergan": EUROSTAT_API + "lfsa_ergan?geo=ES&sex=T&unit=PC&time=2019..2025",
    "lfsa_pganws": EUROSTAT_API + "lfsa_pganws?geo=ES&sex=T&age=Y15-64&citizen=FOR&citizen=NAT&citizen=TOTAL&wstatus=EMP&wstatus=POP&unit=THS_PER",
    "nama_10_pe": EUROSTAT_API + "nama_10_pe?geo=ES&unit=THS_PER&na_item=SAL_DC&na_item=EMP_DC&na_item=SELF_DC",
}
INPUTS = [PROJ, NMIG, ERGAN, PGANWS, NAMA_PE, PROFILE]

STAGES = {"0_15": (0, 15), "16_29": (16, 29), "30_44": (30, 44), "45_64": (45, 64), "65_79": (65, 79), "80p": (80, 200)}
EXTRA_BANDS = {"5_24": (5, 24), "15_64": (15, 64)}
# Five-year LFS bands that make up each working stage (16-19 uses the 15-19 rate).
LFS_BANDS = {
    "16_29": ["Y15-19", "Y20-24", "Y25-29"],
    "30_44": ["Y30-34", "Y35-39", "Y40-44"],
    "45_64": ["Y45-49", "Y50-54", "Y55-59", "Y60-64"],
    "65_79": ["Y65-69", "Y70-74"],
}


def r(v, d=3):
    return None if v is None else round(float(v), d)


def jsonstat(path: Path) -> dict[tuple, float]:
    """{(category code per dimension, in `id` order): value} from a Eurostat JSON-stat 2.0 file."""
    d = json.loads(path.read_text(encoding="utf-8"))
    ids, size = d["id"], d["size"]
    inv = {k: {i: c for c, i in d["dimension"][k]["category"]["index"].items()} for k in ids}
    out = {}
    for key, val in d["value"].items():
        idx, coords = int(key), []
        for s in reversed(size):
            coords.append(idx % s)
            idx //= s
        out[tuple(inv[k][c] for k, c in zip(ids, reversed(coords)))] = val
    return out


def dim(path: Path, rows: dict[tuple, float], **fixed) -> list[tuple]:
    ids = json.loads(path.read_text(encoding="utf-8"))["id"]
    pos = {k: ids.index(k) for k in fixed}
    return [(k, v) for k, v in rows.items() if all(k[pos[name]] == want for name, want in fixed.items())]


def age_of(code: str) -> int | None:
    if code == "Y_LT1":
        return 0
    if code == "Y_GE100":
        return 100
    if code.startswith("Y") and code[1:].isdigit():
        return int(code[1:])
    return None


def band_sums(rows, ids, years, bands) -> dict[str, list[float]]:
    a, t = ids.index("age"), ids.index("time")
    out = {b: [0.0] * len(years) for b in bands}
    index = {str(y): j for j, y in enumerate(years)}
    for key, v in rows:
        age, j = age_of(key[a]), index.get(key[t])
        if age is None or j is None:
            continue
        for b, (lo, hi) in bands.items():
            if lo <= age <= hi:
                out[b][j] += v
    return out


def ar_sections(payload: bytes, sheet: str = "ESc") -> dict[tuple[str, str], dict[int, float]]:
    """{(section, label): {year: value}} for the Ageing Report annex sheet with health, LTC, education and totals."""
    rows = xlsx_rows(xlsx_sheet(payload, sheet))
    years: dict[str, int] = {}
    section = ""
    out: dict[tuple[str, str], dict[int, float]] = {}
    for i in sorted(rows):
        row = rows[i]
        label = str(row.get("B", "")).strip()
        cells = {k: v for k, v in row.items() if k != "B"}
        if str(row.get("D", "")).strip() in ("2022", "2022.0"):
            years = {k: int(float(v)) for k, v in cells.items() if str(v).strip().replace(".0", "").isdigit() and len(str(v).strip().replace(".0", "")) == 4}
            section = label
            continue
        if label and not any(str(v).strip() for v in cells.values()):
            continue
        vals = {}
        for k, v in cells.items():
            if k in years:
                try:
                    vals[years[k]] = float(v)
                except (TypeError, ValueError):
                    pass
        if label and vals:
            out[(section, label)] = vals
    return out


def labour_block(years: list[int], ar_payload: bytes, ar_population_m: dict[int, float], sanidad: dict,
                 gdp_meur_2025: float, cofog: dict[str, float]) -> tuple[dict, list[dict]]:
    gates = []
    ids_p = json.loads(PROJ.read_text(encoding="utf-8"))["id"]
    proj = jsonstat(PROJ)
    pop = {}
    for variant in ("BSL", "HMIGR", "LMIGR"):
        rows = dim(PROJ, proj, projection=variant)
        pop[variant] = band_sums(rows, ids_p, years, {**STAGES, **EXTRA_BANDS})
        totals = {k[ids_p.index("time")]: v for k, v in rows if k[ids_p.index("age")] == "TOTAL"}
        gap = max(abs(sum(pop[variant][s][j] for s in STAGES) - totals[str(y)]) for j, y in enumerate(years))
        gates.append({"id": f"population_stages_sum_{variant}", "ok": gap < 1.0, "value": r(gap, 1),
                      "detail": f"EUROPOP2023 {variant}: the six stages add up to the total in every year (max gap, persons)"})
    worst = max(abs(sum(pop["BSL"][s][j] for s in STAGES) / (ar_population_m[y] * 1e6) - 1) * 100 for j, y in enumerate(years))
    gates.append({"id": "europop_vs_ageing_report", "ok": worst <= 0.5, "value": r(worst, 3),
                  "detail": "EUROPOP2023 baseline population vs the Ageing Report 2024 population, max gap 2025-2050 (%, tolerance 0.5)"})

    # Net migration by variant and the age profile of the extra migrants.
    ids_m = json.loads(NMIG.read_text(encoding="utf-8"))["id"]
    nm_rows = jsonstat(NMIG)
    net = {}
    for variant in ("BSL", "HMIGR", "LMIGR"):
        tot = {k[ids_m.index("time")]: v for k, v in dim(NMIG, nm_rows, projection=variant) if k[ids_m.index("age")] == "TOTAL"}
        net[variant] = [tot.get(str(y), 0.0) / 1000 for y in years]
    cum = {v: sum(net[v][1:]) for v in net}
    scale_hi = cum["HMIGR"] / cum["BSL"] - 1
    scale_lo = cum["LMIGR"] / cum["BSL"] - 1
    profile_age: dict[int, float] = {}
    a_m, t_m = ids_m.index("age"), ids_m.index("time")
    for (key, v), sign in [(kv, 1) for kv in dim(NMIG, nm_rows, projection="HMIGR")] + [(kv, -1) for kv in dim(NMIG, nm_rows, projection="BSL")]:
        age = age_of(key[a_m])
        if age is None or int(key[t_m]) <= years[0]:
            continue
        profile_age[age] = profile_age.get(age, 0.0) + sign * v
    total_extra = sum(profile_age.values())
    mig_profile = {s: sum(v for a, v in profile_age.items() if lo <= a <= hi) / total_extra for s, (lo, hi) in STAGES.items()}

    def lfs_weight(band: str) -> float:
        lo, hi = (int(x) for x in band[1:].split("-"))
        lo = max(lo, 16) if band == "Y15-19" else lo
        return sum(v for a, v in profile_age.items() if lo <= a <= hi)

    # Employment rates by stage (latest LFS year), weighted by where the extra migrants are.
    ids_e = json.loads(ERGAN.read_text(encoding="utf-8"))["id"]
    er = jsonstat(ERGAN)
    er_year = max(int(k[ids_e.index("time")]) for k in er)
    def rate(citizen: str, band: str) -> float:
        key = {"freq": "A", "unit": "PC", "sex": "T", "age": band, "citizen": citizen, "geo": "ES", "time": str(er_year)}
        return er[tuple(key[k] for k in ids_e)] / 100
    emp_rate = {}
    for citizen in ("FOR", "NAT", "TOTAL"):
        emp_rate[citizen] = {}
        for stage, bands in LFS_BANDS.items():
            w = [lfs_weight(b) for b in bands]
            emp_rate[citizen][stage] = r(sum(rate(citizen, b) * x for b, x in zip(bands, w)) / sum(w), 4)
        emp_rate[citizen]["80p"] = 0.0
        emp_rate[citizen]["0_15"] = 0.0
    emp_rate["FOR_15_64"] = r(rate("FOR", "Y15-64"), 4)

    # Backtest: new employed foreign citizens per new foreign resident aged 15-64 (LFS), 2019 -> latest.
    ids_g = json.loads(PGANWS.read_text(encoding="utf-8"))["id"]
    pg = jsonstat(PGANWS)
    def pga(citizen, wstatus, year):
        key = {"freq": "A", "unit": "THS_PER", "sex": "T", "citizen": citizen, "age": "Y15-64", "wstatus": wstatus, "geo": "ES", "time": str(year)}
        return pg[tuple(key[k] for k in ids_g)]
    last = max(int(k[ids_g.index("time")]) for k in pg)
    backtest = {"from": 2019, "to": last,
                "for_pop_k": [r(pga("FOR", "POP", 2019), 1), r(pga("FOR", "POP", last), 1)],
                "for_emp_k": [r(pga("FOR", "EMP", 2019), 1), r(pga("FOR", "EMP", last), 1)]}
    backtest["observed_rate"] = r((backtest["for_emp_k"][1] - backtest["for_emp_k"][0]) / (backtest["for_pop_k"][1] - backtest["for_pop_k"][0]), 4)

    # Employees and self-employed (national accounts), latest year.
    ids_n = json.loads(NAMA_PE.read_text(encoding="utf-8"))["id"]
    na = jsonstat(NAMA_PE)
    na_year = max(int(k[ids_n.index("time")]) for k in na)
    def nam(item):
        key = {"freq": "A", "unit": "THS_PER", "na_item": item, "geo": "ES", "time": str(na_year)}
        return na[tuple(key[k] for k in ids_n)]

    # Health: Spanish age profile (Funcas 2008) -> one weight per stage with the 2025 single-age population.
    prof = json.loads(PROFILE.read_text(encoding="utf-8"))
    band_eur = []
    for row in prof["rows"]:
        a = row["age"]
        lo, hi = (80, 200) if a.startswith("80") else tuple(int(x) for x in a.split("a"))
        band_eur.append((lo, hi, row["euros_1998"]["2008"]))
    t0 = ids_p.index("time")
    single = {age_of(k[ids_p.index("age")]): v for k, v in dim(PROJ, proj, projection="BSL") if k[t0] == str(years[0]) and age_of(k[ids_p.index("age")]) is not None}
    eur_of = lambda age: next(e for lo, hi, e in band_eur if lo <= age <= hi)  # noqa: E731
    mean_eur = sum(single[a] * eur_of(a) for a in single) / sum(single.values())
    weights = {s: r(sum(single[a] * eur_of(a) for a in single if lo <= a <= hi) / sum(single[a] for a in single if lo <= a <= hi) / mean_eur, 4)
               for s, (lo, hi) in STAGES.items()}
    demo = [sum(pop["BSL"][s][j] * weights[s] for s in STAGES) for j in range(len(years))]
    per_capita_mix = [demo[j] / sum(pop["BSL"][s][j] for s in STAGES) for j in range(len(years))]
    mix_growth = per_capita_mix[-1] / per_capita_mix[0] - 1

    ar = ar_sections(ar_payload)
    hc = ar[("Health care spending as % of GDP", "Baseline")]
    hc_demo = ar[("Health care spending as % of GDP -  (diff. from baseline)", "Demographic scenario")]
    ar_demo_growth = (hc[years[-1]] + hc_demo[years[-1]]) / (hc[years[0]] + hc_demo.get(years[0], 0.0)) - 1
    gates.append({"id": "health_demography_vs_ageing_report", "ok": abs(mix_growth - ar_demo_growth) <= 0.05,
                  "value": r((mix_growth - ar_demo_growth) * 100, 2),
                  "detail": f"growth 2025-2050 of health spending per GDP from age alone: {mix_growth * 100:.1f} % with the Funcas profile and EUROPOP2023 vs {ar_demo_growth * 100:.1f} % in the Ageing Report demographic scenario (tolerance 5 points)"})
    edu = ar[("Education spending as % of GDP", "Baseline")]
    students = ar[("Education spending as % of GDP", "Total")]
    enrol = ar[("Education spending as % of GDP", "as % of population 5-24")]
    ltc = ar[("Long-term care spending as % of GDP", "Baseline")]
    tot_hi = ar[("Total cost of ageing as % of GDP -  (diff. from baseline)", "Higher migration (+33%)")]
    tot_lo = ar[("Total cost of ageing as % of GDP -  (diff. from baseline)", "Lower migration (-33%)")]

    # Waiting list (SISLE, through the health page) and doctors.
    head = sanidad["headline"]["waiting"]
    stock = head["surgery_patients"][-1]
    days = head["surgery_days"][-1]
    practising = [p for p in sanidad["doctors"]["practising"]["ES"] if p.get("value") is not None][-1]
    doctors_k = practising["value"] * sum(pop["BSL"][s][0] for s in STAGES) / 1e5 / 1000

    other_pct = cofog["TE"] - cofog["GF07"] - cofog["GF09"] - cofog["GF1002"] - cofog["GF1003"] - cofog["GF0107"]
    block = {
        "stages": list(STAGES),
        "pop_k": {s: [r(v / 1000, 1) for v in pop["BSL"][s]] for s in [*STAGES, *EXTRA_BANDS]},
        "mig_hi_k": {s: [r((pop["HMIGR"][s][j] - pop["BSL"][s][j]) / 1000, 2) for j in range(len(years))] for s in [*STAGES, *EXTRA_BANDS]},
        "mig_lo_k": {s: [r((pop["LMIGR"][s][j] - pop["BSL"][s][j]) / 1000, 2) for j in range(len(years))] for s in [*STAGES, *EXTRA_BANDS]},
        "net_migration_k": {v: [r(x, 1) for x in net[k]] for v, k in (("base", "BSL"), ("hi", "HMIGR"), ("lo", "LMIGR"))},
        "variant_pct": {"hi": r(scale_hi * 100, 1), "lo": r(scale_lo * 100, 1)},
        "mig_profile": {s: r(v, 4) for s, v in mig_profile.items()},
        "emp_rate": emp_rate, "emp_rate_year": er_year,
        "employees_k": r(nam("SAL_DC"), 1), "self_employed_na_k": r(nam("SELF_DC"), 1), "employment_na_k": r(nam("EMP_DC"), 1), "na_year": na_year,
        "backtest_foreign": backtest,
        "health": {
            "spend_pct": [r(hc[y], 3) for y in years], "weights": weights, "profile_year": 2008,
            "demo_index": [r(v / demo[0], 5) for v in demo], "mix_growth_2050": r(mix_growth, 4), "ar_demo_growth_2050": r(ar_demo_growth, 4),
            "spend_meur_2025": r(hc[years[0]] / 100 * gdp_meur_2025, 0),
            "ltc_pct": [r(ltc[y], 3) for y in years],
            "doctors_k": r(doctors_k, 1), "doctors_per_100k": practising["value"], "doctors_year": practising["year"],
            "list_k": r(stock / 1000, 1), "list_days": days, "list_date": sanidad["headline"]["waiting"]["last_cut"],
            "exits_k": r(stock * 365 / days / 1000, 0),
        },
        "education": {"spend_pct": [r(edu[y], 3) for y in years], "students_k": [r(students[y], 1) for y in years],
                      "enrol_ratio": r(enrol[years[0]] / 100, 4),
                      "per_student_eur": r(edu[years[0]] / 100 * gdp_meur_2025 * 1e6 / (students[years[0]] * 1000), 0)},
        "other_spending_pct": r(other_pct, 3),
        "age_related_mig_pp": {"hi": [r(tot_hi.get(y, 0.0) - tot_hi.get(years[0], 0.0), 4) for y in years],
                               "lo": [r(tot_lo.get(y, 0.0) - tot_lo.get(years[0], 0.0), 4) for y in years]},
    }
    return block, gates
