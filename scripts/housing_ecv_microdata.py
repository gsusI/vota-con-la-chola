"""Housing cost by age of the reference person x tenure x territory from the INE ECV microdata (cross-sectional files).

Closes the gap of docs/etl/sprints/VIZ-SEGMENTOS-20261019/README.md §7: no official table crosses age, tenure and region.
Pure standard library (the ingest runs on the host python); `scripts/ingest_housing_es.py` fetches the files into the raw
cache and loads the cells through the indicator_* contract, `scripts/export_public_viz_housing.py` publishes them.

Rules fixed before computing (see docs/etl/sprints/VIZ-SEGMENTOS-20261019/vivienda-microdatos.md):
- Unit: households (weight DB090), classified by the age of the reference person (HB080, the first person responsible
  for the dwelling, as in INE t=9994) at the interview (RB082). Eurostat's person-based figures are reproduced only to
  validate the files (weight DB090 x members).
- Tenure HH021: 1 owner outright, 2 owner with mortgage, 3 market rent, 4 reduced rent and 5 free use -> RENT_FR
  (the grouping of Eurostat ilc_lvho07c).
- Housing cost burden as Eurostat (ilc_mded01, ilc_lvho07c): (12 x HH070 - HY070G) / (HY020 - HY070G); a non-positive
  denominator counts as 100 %, and the ratio is capped at 100 %. Overburden: burden > 40 %. HY020 is the income of the
  year before the survey; HH070 the current monthly cost.
- Income per consumption unit: HY020 / HX240 (modified OECD scale). Left after housing: (HY020 - 12 x HH070) / HX240.
- Cells with fewer than MIN_N sample households are left empty (never imputed); cells with fewer than LOW_N are flagged.
- Standard errors: Taylor linearisation with the household as the sampling unit (with replacement, one stratum), times
  the square root of a design effect. The public file carries neither strata nor census sections (INE design: two-stage,
  sections stratified by region and municipality size), so the design effect is calibrated against the 95 % confidence
  intervals INE published for ECV 2023 (AROPE, poverty, severe material and social deprivation, low work intensity by
  sex and age): the largest ratio of INE's variance to ours, so the intervals err wide. Medians use Woodruff intervals.
"""

from __future__ import annotations

import csv
import io
import math
import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

MICRO_URL = "https://www.ine.es/ftp/microdatos/ecv/ecv_b2013/datos_{year}.zip"
MICRO_PAGE = ("https://www.ine.es/dyngs/INEbase/es/operacion.htm?c=Estadistica_C&cid=1254736176807&menu=resultados"
              "&secc=1254736195153&idp=1254735976608")
CI_DOC_URL = "https://www.ine.es/metodologia/t25/ecv_cbp_2021.pdf"
METHOD_URL = "https://www.ine.es/daco/daco42/condivi/ecv_metodo.pdf"
YEARS = (2019, 2023, 2024, 2025)
CALIBRATION_YEAR = 2023
MIN_N, LOW_N = 50, 100
Z95 = 1.959964

TENURE = {"1": "OWN_NL", "2": "OWN_L", "3": "RENT_MKT", "4": "RENT_FR", "5": "RENT_FR"}
TENURES = ("OWN_NL", "OWN_L", "RENT_MKT", "RENT_FR")
AGES = ("16-29", "30-44", "45-64", "65+")
# Territories: Spain, every region, and the two big tense markets against the rest of Spain.
REGIONS = ("ES11", "ES12", "ES13", "ES21", "ES22", "ES23", "ES24", "ES30", "ES41", "ES42", "ES43", "ES51", "ES52", "ES53",
           "ES61", "ES62", "ES63", "ES64", "ES70")
REST = "ES_RESTO"  # Spain without Madrid (ES30) and Cataluña (ES51)

# INE, «Cambio de base poblacional en las estimaciones de la ECV» (February 2025), pages 1-3: ECV 2023 with census 2011
# populations, 95 % interval. (indicator, group) -> (estimate census 2011, estimate census 2021, lower, upper).
INE_CI_2023 = {
    ("arope", "total"): (26.5, 27.1, 25.6, 27.4), ("arope", "lt18"): (34.5, 36.3, 32.6, 36.4),
    ("arope", "18-64"): (26.1, 26.6, 25.2, 27.1), ("arope", "65+"): (20.9, 21.1, 19.8, 22.1),
    ("arope", "men"): (25.5, 26.3, 24.5, 26.5), ("arope", "women"): (27.5, 28.0, 26.5, 28.4),
    ("arop", "total"): (20.2, 20.6, 19.3, 21.1), ("arop", "lt18"): (28.9, 30.6, 27.0, 30.8),
    ("arop", "18-64"): (18.5, 18.7, 17.6, 19.3), ("arop", "65+"): (18.3, 18.4, 17.2, 19.4),
    ("arop", "men"): (19.5, 20.1, 18.6, 20.5), ("arop", "women"): (20.8, 21.2, 19.9, 21.7),
    ("msd", "total"): (9.0, 9.4, 8.4, 9.6), ("msd", "lt18"): (12.3, 13.1, 11.0, 13.6),
    ("msd", "18-64"): (9.2, 9.6, 8.6, 9.8), ("msd", "65+"): (5.6, 5.7, 4.9, 6.2),
    ("msd", "men"): (8.4, 8.9, 7.7, 9.0), ("msd", "women"): (9.6, 10.0, 9.0, 10.2),
    ("lwi", "total"): (8.4, 8.5, 7.8, 8.9), ("lwi", "lt18"): (6.9, 7.3, 5.9, 7.9),
    ("lwi", "18-64"): (8.8, 8.9, 8.2, 9.3), ("lwi", "men"): (8.0, 8.3, 7.4, 8.7),
    ("lwi", "women"): (8.7, 8.8, 8.0, 9.3),
}
INE_CI_PAGES = {"arope": 1, "arop": 2, "msd": 3, "lwi": 3}


@dataclass(frozen=True)
class Household:
    hid: int
    region: str
    weight: float
    members: int
    tenure: str | None
    age: int | None
    burden: float | None
    income: float | None
    cost_year: float | None
    cu: float | None
    hhtype: str = ""

    @property
    def income_cu(self) -> float | None:
        return self.income / self.cu if self.income is not None and self.cu else None

    @property
    def left_cu(self) -> float | None:
        if self.income is None or self.cost_year is None or not self.cu:
            return None
        return (self.income - self.cost_year) / self.cu


@dataclass(frozen=True)
class Person:
    hid: int
    weight: float
    age: int | None
    sex: str
    arope: str
    msd: str
    lwi: str
    arop: str


# ---------------------------------------------------------------- reading the INE files

def _csv(outer: zipfile.ZipFile, year: int, letter: str) -> list[dict[str, str]]:
    """The comma-separated Eurostat-layout file (esudbYYx.csv; esudb19r_AROPE.csv in 2019) inside ECV_T<x>_<year>.zip
    inside datos_<year>.zip."""
    inner_name = next((n for n in outer.namelist() if re.search(rf"ECV_T{letter}_{year}\.zip$", n, re.I)), None)
    if inner_name is None:
        raise ValueError(f"ECV {year}: no ECV_T{letter} file in {outer.namelist()}")
    inner = zipfile.ZipFile(io.BytesIO(outer.read(inner_name)))
    yy = str(year)[2:]
    name = next((n for n in inner.namelist() if re.search(rf"esudb{yy}{letter.lower()}(_[a-z0-9]+)?\.csv$", n, re.I)), None)
    if name is None:
        raise ValueError(f"ECV {year}: no esudb{yy}{letter.lower()}.csv in {inner_name}")
    with inner.open(name) as fh:
        text = io.TextIOWrapper(fh, encoding="utf-8-sig", newline="")
        return [{k.strip(): (v or "").strip() for k, v in row.items() if k} for row in csv.DictReader(text)]


def _num(value: str) -> float | None:
    try:
        return float(value) if value not in ("", ".") else None
    except ValueError:
        return None


def burden_of(cost_month: float | None, allowance: float | None, income: float | None) -> float | None:
    """Eurostat housing cost burden in % (ilc_mded01): allowances off both sides, capped at 100 %."""
    if cost_month is None or income is None:
        return None
    a = allowance or 0.0
    cost, base = 12 * cost_month - a, income - a
    if base <= 0:
        return 100.0
    return min(100.0, max(0.0, cost / base * 100))


def read_year(payload: bytes, year: int) -> tuple[list[Household], list[Person]]:
    outer = zipfile.ZipFile(io.BytesIO(payload))
    d_rows = {int(r["DB030"]): r for r in _csv(outer, year, "D")}
    r_rows = _csv(outer, year, "R")
    age_of: dict[int, int | None] = {}
    persons = []
    for r in r_rows:
        pid = int(r["RB030"])
        # RB081 (age at 31 December of the income year) is missing before 2021: same definition from the birth year.
        age = _num(r.get("RB081", ""))
        if age is None and _num(r.get("RB080", "")) is not None:
            age = year - 1 - _num(r["RB080"])
        age_of[pid] = int(age) if age is not None else None
        if r.get("RB200") not in ("1", ""):
            continue  # Eurostat counts current members only
        persons.append(Person(pid // 100, float(r["RB050"]), age_of[pid], r["RB090"], r.get("vrEU2030_nuevo", ""),
                              r.get("vrMATSOCDEP", ""), r.get("vrLOWJOB_nuevo", ""), ""))
    households = []
    for h in _csv(outer, year, "H"):
        hid = int(h["HB030"])
        d = d_rows[hid]
        ref = _num(h.get("HB080", ""))
        income, cost, allowance = _num(h["HY020"]), _num(h["HH070"]), _num(h.get("HY070G", ""))
        members = int(_num(h.get("HX040", "")) or _num(h.get("HB120", "")) or 0)
        households.append(Household(
            hid, d["DB040"], float(d["DB090"]), members, TENURE.get(h.get("HH021", "")),
            age_of.get(int(ref)) if ref is not None else None, burden_of(cost, allowance, income), income,
            12 * cost if cost is not None else None, _num(h.get("HX240", "")), h.get("HX060", ""),
        ))
    poor = {h["HB030"]: h.get("vhPobreza", "") for h in _csv(outer, year, "H")}
    persons = [Person(p.hid, p.weight, p.age, p.sex, p.arope, p.msd, p.lwi, poor.get(str(p.hid), "")) for p in persons]
    households.sort(key=lambda h: h.hid)
    return households, persons


# ---------------------------------------------------------------- estimators

def age_band(age: int | None) -> str | None:
    if age is None or age < 16:
        return None
    return "16-29" if age < 30 else "30-44" if age < 45 else "45-64" if age < 65 else "65+"


def mean_se(units: list[tuple[float, float]], n_all: int) -> tuple[float, float]:
    """Weighted mean (ratio of totals) and its linearised SE, units = [(weight, value)] in the domain, n_all PSUs."""
    tw = sum(w for w, _ in units)
    m = sum(w * y for w, y in units) / tw
    z = [w * (y - m) / tw for w, y in units]
    # Domain estimation with replacement: PSUs outside the domain contribute z = 0 to the mean of z.
    zbar = sum(z) / n_all
    var = n_all / (n_all - 1) * (sum((zi - zbar) ** 2 for zi in z) + (n_all - len(z)) * zbar ** 2)
    return m, math.sqrt(var)


def weighted_quantile(units: list[tuple[float, float]], p: float) -> float:
    pairs = sorted(units, key=lambda u: u[1])
    total = sum(w for w, _ in pairs)
    acc = 0.0
    for w, y in pairs:
        acc += w
        if acc >= p * total:
            return y
    return pairs[-1][1]


def median_ci(units: list[tuple[float, float]], n_all: int, deff: float) -> tuple[float, float, float, float]:
    """Weighted median, Woodruff 95 % interval (SE of the share below the median, inflated by the design effect) and the
    implied SE (interval width / 2 / 1.96)."""
    med = weighted_quantile(units, 0.5)
    _, se_p = mean_se([(w, 1.0 if y <= med else 0.0) for w, y in units], n_all)
    half = Z95 * se_p * math.sqrt(deff)
    lo = weighted_quantile(units, max(0.0, 0.5 - half))
    hi = weighted_quantile(units, min(1.0, 0.5 + half))
    return med, lo, hi, (hi - lo) / 2 / Z95


def calibrate_deff(persons: list[Person], n_households: int) -> dict[str, Any]:
    """Design effect = (INE's published SE / our household-cluster SE)^2 for every published ECV 2023 interval."""
    clusters: dict[int, list[Person]] = defaultdict(list)
    for p in persons:
        clusters[p.hid].append(p)
    groups = {
        "total": lambda p: True, "men": lambda p: p.sex == "1", "women": lambda p: p.sex == "2",
        "lt18": lambda p: p.age is not None and p.age < 18, "18-64": lambda p: p.age is not None and 18 <= p.age < 65,
        "65+": lambda p: p.age is not None and p.age >= 65,
    }
    flags = {"arope": lambda p: p.arope, "arop": lambda p: p.arop, "msd": lambda p: p.msd, "lwi": lambda p: p.lwi}
    rows = []
    for (ind, grp), (_e11, _e21, lo, hi) in sorted(INE_CI_2023.items()):
        units = []
        for members in clusters.values():
            sel = [p for p in members if groups[grp](p) and flags[ind](p) in ("0", "1", "2")]
            if ind == "lwi":
                sel = [p for p in sel if p.age is not None and p.age < 65]
            if sel:
                w = sum(p.weight for p in sel)
                units.append((w, sum(p.weight for p in sel if flags[ind](p) == "1") / w))
        est, se = mean_se(units, n_households)
        se_ine = (hi - lo) / 2 / Z95 / 100
        rows.append({"indicator": ind, "group": grp, "estimate_pct": round(est * 100, 2), "se_srs_pct": round(se * 100, 3),
                     "se_ine_pct": round(se_ine * 100, 3), "deff": round((se_ine / se) ** 2, 3), "page": INE_CI_PAGES[ind]})
    deffs = sorted(r["deff"] for r in rows)
    return {"rows": rows, "deff": max(deffs), "deff_median": deffs[len(deffs) // 2], "deff_min": deffs[0]}


STATS = ("households_pct", "burden_mean", "burden_median", "overburden_pct", "income_cu_median", "income_cu_mean",
         "left_cu_median", "left_cu_mean")


def _stats(members: list[Household], n_all: int, deff: float) -> dict[str, dict[str, float]]:
    root = math.sqrt(deff)
    stats: dict[str, dict[str, float]] = {}
    with_burden = [(h.weight, h.burden) for h in members if h.burden is not None]
    if len(with_burden) >= MIN_N:
        m, se = mean_se(with_burden, n_all)
        stats["burden_mean"] = {"value": m, "se": se * root}
        m, se = mean_se([(w, 100.0 if b > 40 else 0.0) for w, b in with_burden], n_all)
        stats["overburden_pct"] = {"value": m, "se": se * root}
        med, lo, hi, se = median_ci(with_burden, n_all, deff)
        stats["burden_median"] = {"value": med, "se": se, "lo": lo, "hi": hi}
    for key in ("income_cu", "left_cu"):
        units = [(h.weight, getattr(h, key)) for h in members if getattr(h, key) is not None]
        if len(units) >= MIN_N:
            m, se = mean_se(units, n_all)
            stats[f"{key}_mean"] = {"value": m, "se": se * root}
            med, lo, hi, se = median_ci(units, n_all, deff)
            stats[f"{key}_median"] = {"value": med, "se": se, "lo": lo, "hi": hi}
    return stats


def _finish(stats: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    for v in stats.values():
        v.setdefault("lo", v["value"] - Z95 * v["se"])
        v.setdefault("hi", v["value"] + Z95 * v["se"])
        if v["lo"] < 0 <= v["value"]:
            v["lo"] = 0.0
    return stats


# Shared typical cases (docs/etl/sprints/VIZ-SEGMENTOS-20261019/README.md §3) as survey cells, narrowest first: the page
# uses the first definition with at least MIN_N households and says which one it is. Ages are the reference person's.
ONE_PERSON_LT65, ONE_PERSON_65 = ("1", "2", "4", "5"), ("3", "6")
COUPLE_KIDS = ("11", "12", "13")
INTERIOR = ("ES22", "ES23", "ES24", "ES41", "ES42", "ES43")  # regions without coast, Madrid aside
CASES = {
    "p1_young_renter_madrid": [
        ("25–34 años, vive sola, alquiler de mercado, Comunidad de Madrid", (25, 34), ("RENT_MKT",), ("ES30",), ONE_PERSON_LT65),
        ("25–34 años, alquiler de mercado, Comunidad de Madrid", (25, 34), ("RENT_MKT",), ("ES30",), None),
        ("16–29 años, alquiler de mercado, Comunidad de Madrid", (16, 29), ("RENT_MKT",), ("ES30",), None),
    ],
    "p2_family_renter_metro": [
        ("30–44 años, pareja con hijos, alquiler de mercado, Comunidad de Madrid", (30, 44), ("RENT_MKT",), ("ES30",), COUPLE_KIDS),
        ("30–44 años, alquiler de mercado, Comunidad de Madrid", (30, 44), ("RENT_MKT",), ("ES30",), None),
    ],
    "p2_family_buyer_madrid": [
        ("30–44 años, pareja con hijos, con hipoteca, Comunidad de Madrid", (30, 44), ("OWN_L",), ("ES30",), COUPLE_KIDS),
        ("30–44 años, con hipoteca, Comunidad de Madrid", (30, 44), ("OWN_L",), ("ES30",), None),
    ],
    "p4_retired_owner_interior": [
        ("65 años o más, vive solo, casa pagada, comunidades del interior", (65, 200), ("OWN_NL",), INTERIOR, ONE_PERSON_65),
        ("65 años o más, casa pagada, comunidades del interior", (65, 200), ("OWN_NL",), INTERIOR, None),
    ],
}


def case_cells(households: list[Household], deff: float) -> dict[str, list[dict[str, Any]]]:
    n_all = len(households)
    out: dict[str, list[dict[str, Any]]] = {}
    for key, defs in CASES.items():
        rows = []
        for label, (a0, a1), tenures, regions, types in defs:
            members = [h for h in households if h.age is not None and a0 <= h.age <= a1 and h.tenure in tenures
                       and h.region in regions and (types is None or h.hhtype in types)]
            row: dict[str, Any] = {"label": label, "n": len(members), "low_precision": MIN_N <= len(members) < LOW_N}
            if len(members) >= MIN_N:
                row["stats"] = _finish(_stats(members, n_all, deff))
            rows.append(row)
        out[key] = rows
    return out


def _territories(region: str) -> tuple[str, ...]:
    return ("ES", region) + (() if region in ("ES30", "ES51") else (REST,))


def cells(households: list[Household], deff: float) -> list[dict[str, Any]]:
    """Every age x tenure x territory cell (with 'TOTAL' margins): estimate, SE, 95 % interval and sample size."""
    n_all = len(households)
    groups: dict[tuple[str, str, str], list[Household]] = defaultdict(list)
    for h in households:
        band = age_band(h.age)
        for geo in _territories(h.region):
            for age in ("TOTAL",) + ((band,) if band else ()):
                for ten in ("TOTAL",) + ((h.tenure,) if h.tenure else ()):
                    groups[(geo, age, ten)].append(h)
    out = []
    root = math.sqrt(deff)
    for (geo, age, ten), members in sorted(groups.items()):
        n = len(members)
        row: dict[str, Any] = {"geo": geo, "age": age, "tenure": ten, "n": n, "low_precision": MIN_N <= n < LOW_N}
        if n < MIN_N:
            out.append(row)
            continue
        stats: dict[str, dict[str, float]] = {}
        # Share of the age group's households living in this tenure (t=9994 layout).
        if ten != "TOTAL":
            parent = groups[(geo, age, "TOTAL")]
            mine = {h.hid for h in members}
            m, se = mean_se([(h.weight, 100.0 if h.hid in mine else 0.0) for h in parent if h.tenure], n_all)
            stats["households_pct"] = {"value": m, "se": se * root}
        stats.update(_stats(members, n_all, deff))
        _finish(stats)
        row["stats"] = stats
        out.append(row)
    return out


# ---------------------------------------------------------------- validation against published tables

def national_checks(households: list[Household]) -> dict[str, Any]:
    """Figures INE and Eurostat publish, recomputed from the file: households by age x tenure (t=9994, %), mean net
    income per household by tenure (t=59956), and the person-based Eurostat overburden by tenure (ilc_lvho07c) and mean
    housing cost burden (ilc_mded01) and its median (ilc_lvho08a). The mean depends on the ~0.5 % of households with
    zero or negative disposable income (counted at 100 %, as here, or left out): it is reported both ways."""
    out: dict[str, Any] = {"t9994": {}, "t59956": {}, "ilc_lvho07c": {}, "ilc_mded01": None}
    for age in ("TOTAL", *AGES):
        sel = [h for h in households if h.tenure and (age == "TOTAL" or age_band(h.age) == age)]
        tw = sum(h.weight for h in sel)
        out["t9994"][age] = {t: round(sum(h.weight for h in sel if h.tenure == t) / tw * 100, 2) for t in TENURES}
    for t in ("TOTAL", *TENURES):
        sel = [h for h in households if h.income is not None and (t == "TOTAL" or h.tenure == t)]
        out["t59956"][t] = round(sum(h.weight * h.income for h in sel) / sum(h.weight for h in sel), 1)
    for t in ("TOTAL", *TENURES):
        sel = [h for h in households if h.burden is not None and (t == "TOTAL" or h.tenure == t)]
        pw = [(h.weight * h.members, h.burden) for h in sel]
        tw = sum(w for w, _ in pw)
        out["ilc_lvho07c"][t] = round(sum(w for w, b in pw if b > 40) / tw * 100, 2)
        if t == "TOTAL":
            out["ilc_mded01"] = round(sum(w * b for w, b in pw) / tw, 2)
            out["ilc_lvho08a"] = round(weighted_quantile(pw, 0.5), 2)
            pos = [(h.weight * h.members, h.burden) for h in sel if h.income is not None and h.income > 0]
            out["ilc_mded01_excl"] = round(sum(w * b for w, b in pos) / sum(w for w, _ in pos), 2)
            out["non_positive_income_pct"] = round(100 - sum(w for w, _ in pos) / tw * 100, 2)
    return out
