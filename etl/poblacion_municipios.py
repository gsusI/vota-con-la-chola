from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any


BASE_URL = "https://www.ine.es/nomen2"
COMUNIDADES_URL = f"{BASE_URL}/comunidades.json"
PROVINCIAS_URL = f"{BASE_URL}/provincias.json"
TABLA_URL = f"{BASE_URL}/tabla.do"
SOURCE_URL = f"{BASE_URL}/index.do"

USER_AGENT = "Mozilla/5.0"
PROVINCE_NAME_RE = re.compile(r"^\s*\d{1,2}\s+\S+")
CODE_SPACE_NAME_RE = re.compile(r"^(\d+)\s+(.*)$")


def http_get_text(url: str, timeout: int = 30, params: dict[str, str] | None = None) -> str:
    final_url = url
    if params:
        final_url = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"
    request = urllib.request.Request(final_url)
    request.add_header("User-Agent", USER_AGENT)
    request.add_header("Accept", "text/html,application/json,text/plain,*/*")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def http_post(form_url: str, payload: list[tuple[str, str]], timeout: int = 30) -> str:
    request = urllib.request.Request(
        form_url,
        data=urllib.parse.urlencode(payload, doseq=True).encode("utf-8"),
        method="POST",
    )
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    request.add_header("User-Agent", USER_AGENT)
    request.add_header("Referer", SOURCE_URL)
    request.add_header("Accept", "text/html,application/xhtml+xml,*/*")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def http_get_json(url: str, timeout: int = 30, params: dict[str, str] | None = None) -> list[dict[str, str]]:
    parsed = json.loads(http_get_text(url, timeout=timeout, params=params))
    if isinstance(parsed, list):
        return parsed
    raise TypeError(f"Unexpected JSON payload shape in {url}: {type(parsed)!r}")


def normalize_ccaa_code(value: str) -> str:
    cleaned = str(value).strip()
    if cleaned.isdigit():
        return str(int(cleaned))
    return cleaned


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def normalize_name(text: str) -> str:
    return text.replace("\xa0", " ").strip()


def load_geography(timeout: int = 30) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    comunidades = {
        normalize_ccaa_code(row["codccaa"]): {"name": row["comunidad"].strip()} for row in http_get_json(COMUNIDADES_URL, timeout=timeout)
    }
    provincias: dict[str, dict[str, str]] = {}

    for ccaa_code, ccaa_meta in comunidades.items():
        rows = http_get_json(PROVINCIAS_URL, timeout=timeout, params={"ccaa": ccaa_code})
        for row in rows:
            province_code = row["codprov"].zfill(2)
            provincias[province_code] = {
                "name": normalize_name(row["provincia"]).strip(),
                "ccaa_code": ccaa_code,
                "ccaa_name": ccaa_meta["name"],
            }

    return comunidades, provincias


def detect_latest_year() -> int:
    html_text = http_get_text(SOURCE_URL, timeout=30)
    select_match = re.search(
        r'name=[\"\']aniosRapida[\"\'][^>]*>(.*?)</select>',
        html_text,
        flags=re.S | re.I,
    )
    if select_match:
        years = [int(m) for m in re.findall(r'value=[\"\']?(\d{4})[\"\']?', select_match.group(1))]
        if years:
            return max(years)

    matches = [int(m) for m in re.findall(r'value=[\"\']?(\d{4})[\"\']?', html_text)]
    if not matches:
        return datetime.now(timezone.utc).year
    return max(matches)


def parse_int_population(value: str) -> int | None:
    raw = normalize_name(value).replace(".", "")
    if not raw or raw in {"-", ".."}:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def parse_code_and_name(text: str) -> tuple[str | None, str]:
    match = CODE_SPACE_NAME_RE.match(normalize_name(text))
    if not match:
        return None, normalize_name(text)
    return match.group(1), match.group(2).strip()


class NomenclatorResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._rows: list[list[str]] = []
        self._row: list[str] = []
        self._cell_parts: list[str] = []

    @property
    def rows(self) -> list[list[str]]:
        return self._rows

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "table" and attrs_dict.get("id") == "tablaDatos":
            self._in_table = True
            return
        if not self._in_table:
            return
        if tag == "tr":
            self._in_row = True
            self._row = []
            return
        if tag in {"td", "th"} and self._in_row:
            self._in_cell = True
            self._cell_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self._in_table:
            self._in_table = False
            self._in_row = False
            return
        if not self._in_table:
            return
        if self._in_row and tag == "tr":
            if self._row:
                self._rows.append(self._row)
            self._in_row = False
            return
        if self._in_cell and tag in {"td", "th"}:
            self._row.append(normalize_text("".join(self._cell_parts)))
            self._in_cell = False

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell_parts.append(data)

    def handle_entityref(self, name: str) -> None:
        if self._in_cell:
            self._cell_parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if self._in_cell:
            self._cell_parts.append(f"&#{name};")


def extract_rows_with_headers(html_text: str) -> tuple[list[list[str]], int]:
    parser = NomenclatorResultParser()
    parser.feed(html_text)
    rows = parser.rows
    if not rows:
        return [], 0

    data_rows = [row for row in rows if len(row) >= 5 and PROVINCE_NAME_RE.match(row[0] or "")]
    return data_rows, len(rows)


def fetch_municipalities_for_province(
    province_code: str,
    community_code: str,
    year: int,
    timeout: int,
) -> list[dict[str, Any]]:
    payload = [
        ("accion", "busquedaAvanzada"),
        ("entidad_amb", "M"),
        ("comunidad", community_code),
        ("provincias", province_code),
        ("desagregacion", "S"),
        ("poblacion_amb", "T"),
        ("poblacion_op", "I"),
        ("poblacion_txt", ""),
        ("anios", str(year)),
        ("L", "0"),
    ]

    html_text = http_post(TABLA_URL, payload, timeout=timeout)
    rows, _ = extract_rows_with_headers(html_text)

    parsed: list[dict[str, Any]] = []
    for row in rows:
        if len(row) < 5:
            continue

        province_code_match = re.match(r"^(\d{1,2})\s+(.+)$", row[0].strip())
        if not province_code_match:
            continue

        municipality_text = row[1].strip()
        municipality_code, municipality_name = parse_code_and_name(municipality_text)
        if not municipality_code:
            continue

        parsed.append(
            {
                "province_code": province_code_match.group(1).zfill(2),
                "province_name": province_code_match.group(2).strip(),
                "municipality_code": f"{province_code_match.group(1).zfill(2)}{municipality_code}",
                "municipality_name": municipality_name,
                "year": year,
                "population_total": parse_int_population(row[2]),
                "population_male": parse_int_population(row[3]),
                "population_female": parse_int_population(row[4]),
            }
        )

    return parsed


def aggregate_municipal_data(
    municipalities: list[dict[str, Any]],
    province_map: dict[str, dict[str, str]],
) -> dict[str, Any]:
    provinces: dict[str, dict[str, Any]] = {}
    autonomies: dict[str, dict[str, Any]] = {}
    autonomy_province_set: dict[str, set[str]] = defaultdict(set)

    country_population = 0
    country_population_male = 0
    country_population_female = 0

    for row in municipalities:
        province_code = row["province_code"]
        province_meta = province_map.get(province_code)
        if not province_meta:
            continue

        ccaa_code = province_meta["ccaa_code"]
        ccaa_name = province_meta["ccaa_name"]

        province_entry = provinces.setdefault(
            province_code,
            {
                "province_code": province_code,
                "province_name": province_meta["name"],
                "ccaa_code": ccaa_code,
                "ccaa_name": ccaa_name,
                "municipality_count": 0,
                "population_total": 0,
                "population_male": 0,
                "population_female": 0,
            },
        )
        autonomy_entry = autonomies.setdefault(
            ccaa_code,
            {
                "ccaa_code": ccaa_code,
                "ccaa_name": ccaa_name,
                "municipality_count": 0,
                "population_total": 0,
                "population_male": 0,
                "population_female": 0,
                "province_count": 0,
            },
        )

        autonomy_province_set[ccaa_code].add(province_code)
        province_entry["municipality_count"] += 1
        autonomy_entry["municipality_count"] += 1

        population_total = row["population_total"]
        population_male = row["population_male"]
        population_female = row["population_female"]

        if population_total is not None:
            province_entry["population_total"] += population_total
            autonomy_entry["population_total"] += population_total
            country_population += population_total
        if population_male is not None:
            province_entry["population_male"] += population_male
            autonomy_entry["population_male"] += population_male
            country_population_male += population_male
        if population_female is not None:
            province_entry["population_female"] += population_female
            autonomy_entry["population_female"] += population_female
            country_population_female += population_female

    for autonomy_code, entries in autonomy_province_set.items():
        if autonomy_code in autonomies:
            autonomies[autonomy_code]["province_count"] = len(entries)

    return {
        "provinces": sorted(provinces.values(), key=lambda item: item["province_code"]),
        "autonomies": sorted(autonomies.values(), key=lambda item: item["ccaa_name"]),
        "country": {
            "municipality_count": len(municipalities),
            "province_count": len(provinces),
            "autonomy_count": len(autonomies),
            "population_total": country_population,
            "population_male": country_population_male,
            "population_female": country_population_female,
        },
    }


def run(
    year: int | None = None,
    workers: int = 16,
    timeout: int = 30,
) -> dict[str, Any]:
    if year is None:
        year = detect_latest_year()

    _, province_map = load_geography(timeout=timeout)
    municipality_rows: list[dict[str, Any]] = []
    errors: list[str] = []

    province_items = sorted(province_map.items(), key=lambda item: item[0])
    max_workers = max(1, min(workers, len(province_items)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_municipalities_for_province, province_code, meta["ccaa_code"], year, timeout): province_code
            for province_code, meta in province_items
        }
        for future in as_completed(futures):
            province_code = futures[future]
            try:
                municipality_rows.extend(future.result())
            except Exception as exc:
                errors.append(f"{province_code}: {exc}")
                print(f"[warn] No se pudo procesar provincia {province_code}: {exc}", file=sys.stderr)

    municipality_rows.sort(key=lambda item: (item["province_code"], item["municipality_code"]))
    aggregation = aggregate_municipal_data(municipality_rows, province_map)

    return {
        "year": year,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_url": SOURCE_URL,
        "errors": errors,
        "municipalities": municipality_rows,
        **aggregation,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Descarga población municipal del Nomenclátor del INE y agrega por provincia y autonomía."
        )
    )
    parser.add_argument("--year", type=int, default=None, help="Año (por defecto, el más reciente publicado)")
    parser.add_argument("--workers", type=int, default=16, help="Workers para descarga paralela")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout HTTP en segundos")
    parser.add_argument("--json-out", default="", help="Ruta de salida JSON (opcional)")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run(year=args.year, workers=args.workers, timeout=args.timeout)

    if args.json_out:
        from pathlib import Path

        path = Path(args.json_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=2)
        print(f"written: {path}")
        return 0

    # compact summary for quick validation
    print(
        json.dumps(
            {
                "year": result["year"],
                "country": result["country"],
                "errors": result["errors"],
                "provinces": len(result["provinces"]),
                "autonomies": len(result["autonomies"]),
                "municipalities": len(result["municipalities"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
