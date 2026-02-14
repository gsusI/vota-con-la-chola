#!/usr/bin/env python3
"""Exporta una instantánea mínima para la interfaz web de explorer-sports."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

from datetime import datetime, timezone


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
POPULATION_DATA_PATH = Path("etl/data/published/poblacion_municipios_es.json")
MANDATES_QUERY = """
SELECT
  m.mandate_id,
  m.source_id,
  m.role_title,
  m.level,
  m.territory_code AS mandate_territory_code,
  tm.name AS mandate_territory_name,
  tm.level AS mandate_territory_level,
  m.start_date,
  m.end_date,
  m.is_active,
  m.person_id,
  p.full_name,
  p.given_name,
  p.family_name,
  p.territory_code AS person_territory_code,
  ti_p.name AS person_territory_name,
  ti_p.level AS person_territory_level,
  m.institution_id,
  i.name AS institution_name,
  i.level AS institution_level,
  i.territory_code AS institution_territory_code,
  ti_i.name AS institution_territory_name,
  ti_i.level AS institution_territory_level,
  m.party_id,
  pa.name AS party_name,
  pa.acronym AS party_acronym
FROM mandates m
JOIN persons p ON p.person_id = m.person_id
JOIN institutions i ON i.institution_id = m.institution_id
LEFT JOIN territories tm ON tm.code = m.territory_code
LEFT JOIN parties pa ON pa.party_id = m.party_id
LEFT JOIN territories ti_p ON ti_p.code = p.territory_code
LEFT JOIN territories ti_i ON ti_i.code = i.territory_code
"""

PERSONS_WITH_MANDATES_QUERY = """
SELECT
  p.person_id,
  p.full_name,
  p.given_name,
  p.family_name,
  p.birth_date,
  p.gender,
  p.territory_code,
  m.mandate_id,
  m.source_id,
  m.role_title,
  m.level,
  m.territory_code AS mandate_territory_code,
  m.start_date,
  m.end_date,
  m.is_active,
  i.name AS institution_name,
  m.party_id AS party_id,
  pa.name AS party_name,
  pa.acronym AS party_acronym
FROM persons p
LEFT JOIN mandates m ON m.person_id = p.person_id
LEFT JOIN institutions i ON i.institution_id = m.institution_id
LEFT JOIN parties pa ON pa.party_id = m.party_id
ORDER BY
  p.person_id,
  CASE WHEN m.is_active = 1 THEN 0 ELSE 1 END,
  COALESCE(m.start_date, ''),
  COALESCE(m.mandate_id, 0) DESC
"""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Exporta snapshot para explorer-sports (GitHub Pages)")
    p.add_argument("--db", default=str(DEFAULT_DB), help="Ruta de la base SQLite")
    p.add_argument(
        "--snapshot-date",
        required=True,
        help="Fecha de snapshot (YYYY-MM-DD), usada en metadata",
    )
    p.add_argument(
        "--out-dir",
        default="docs/gh-pages/explorer-sports/data",
        help="Directorio de salida para JSON estáticos",
    )
    return p.parse_args()


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def normalize_municipality_code(value: Any) -> str:
    token = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(token) == 5:
        return token
    return ""


def is_municipal_level(value: Any) -> bool:
    normalized = str(value or "").strip().lower()
    return bool(
        normalized and (
            "municipal" in normalized
            or "ayuntamiento" in normalized
            or "concejal" in normalized
            or "local" in normalized
        )
    )


def municipality_name(value: Any, fallback: Any = "Sin municipio") -> str:
    text = str(value or "").strip()
    return text or str(fallback or "").strip() or "Sin municipio"


def load_municipality_population() -> Dict[str, int]:
    if not POPULATION_DATA_PATH.exists():
        return {}
    try:
        payload = json.loads(POPULATION_DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    by_code: Dict[str, int] = {}
    for municipality in payload.get("municipalities", []):
        code = normalize_municipality_code(municipality.get("municipality_code"))
        if not code:
            continue
        population = municipality.get("population_total")
        if population is None:
            continue
        try:
            by_code[code] = int(population)
        except (TypeError, ValueError):
            continue
    return by_code


def extract_municipality_fields(row: Dict[str, Any], population_by_code: Dict[str, int]) -> tuple[str, str, int | None]:
    candidates = [
        (row.get("mandate_territory_code"), row.get("mandate_territory_name"), row.get("mandate_territory_level")),
        (row.get("institution_territory_code"), row.get("institution_territory_name"), row.get("institution_territory_level")),
        (row.get("person_territory_code"), row.get("person_territory_name"), row.get("person_territory_level")),
    ]

    for code, name, level in candidates:
        normalized = normalize_municipality_code(code)
        if normalized and is_municipal_level(level):
            return normalized, municipality_name(name), population_by_code.get(normalized)

    for code, name, level in candidates:
        normalized = normalize_municipality_code(code)
        if normalized and population_by_code.get(normalized) is not None:
            return normalized, municipality_name(name), population_by_code.get(normalized)

    for code, name, _level in candidates:
        normalized = normalize_municipality_code(code)
        if normalized:
            return normalized, municipality_name(name), population_by_code.get(normalized)

    return "", "", None


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    out_dir = Path(args.out_dir)
    municipality_population = load_municipality_population()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        print(f"ERROR: no existe el DB -> {db_path}")
        return 2

    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row

        sources_raw = conn.execute(
            """
            SELECT source_id, name, scope, default_url
            FROM sources
            ORDER BY source_id
            """
        ).fetchall()

        mandates_raw = conn.execute(MANDATES_QUERY).fetchall()

        people_raw = conn.execute(PERSONS_WITH_MANDATES_QUERY).fetchall()
    finally:
        conn.close()

    sources = [row_to_dict(row) for row in sources_raw]
    mandates = []
    for row in mandates_raw:
        row_dict = row_to_dict(row)
        municipality_code, municipality_name, municipality_population_value = extract_municipality_fields(
            row_dict,
            municipality_population,
        )
        row_dict["municipality_code"] = municipality_code
        row_dict["municipality_name"] = municipality_name
        row_dict["municipality_population"] = municipality_population_value
        mandates.append(row_dict)
    total_person_rows = len(people_raw)

    people: Dict[str, Dict[str, Any]] = {}
    for row in people_raw:
        row_dict = row_to_dict(row)
        person_id = row["person_id"]
        if person_id is None:
            continue

        person_municipality_code, person_municipality_name, person_municipality_population = extract_municipality_fields(
            row_dict,
            municipality_population,
        )

        person_key = str(person_id)
        person = people.setdefault(
            person_key,
            {
                "person": {
                    "person_id": person_id,
                    "full_name": row_dict["full_name"],
                    "given_name": row_dict["given_name"],
                    "family_name": row_dict["family_name"],
                    "birth_date": row_dict["birth_date"],
                    "gender": row_dict["gender"],
                    "territory_code": row_dict["territory_code"],
                },
                "mandates": [],
            },
        )

        mandate_id = row["mandate_id"]
        if mandate_id is None:
            continue

        person["mandates"].append(
            {
                "mandate_id": mandate_id,
                "source_id": row["source_id"],
                "role_title": row["role_title"],
                "level": row["level"],
                "mandate_territory_code": row["mandate_territory_code"],
                "start_date": row["start_date"],
                "end_date": row["end_date"],
                "is_active": row["is_active"],
                "institution_name": row["institution_name"],
                "party_id": row["party_id"],
                "party_name": row["party_name"],
                "party_acronym": row["party_acronym"],
                "municipality_code": person_municipality_code,
                "municipality_name": person_municipality_name,
                "municipality_population": person_municipality_population,
            }
        )

    mandates_snapshot = {
        "meta": {
            "snapshot_date": str(args.snapshot_date),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "db_path": str(db_path),
            "rows": len(mandates),
            "include_inactive": True,
        },
        "rows": mandates,
    }
    sources_snapshot = {
        "meta": {
            "snapshot_date": str(args.snapshot_date),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(sources),
        },
        "sources": sources,
    }
    people_snapshot = {
        "meta": {
            "snapshot_date": str(args.snapshot_date),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "persons": len(people),
            "raw_rows": total_person_rows,
        },
        "people": people,
    }

    mandates_path = out_dir / "arena-mandates.json"
    sources_path = out_dir / "sources.json"
    people_path = out_dir / "people.json"

    mandates_path.write_text(json.dumps(mandates_snapshot, ensure_ascii=True, indent=2), encoding="utf-8")
    sources_path.write_text(json.dumps(sources_snapshot, ensure_ascii=True, indent=2), encoding="utf-8")
    people_path.write_text(json.dumps(people_snapshot, ensure_ascii=True, indent=2), encoding="utf-8")

    print(
        "OK snapshot explorer-sports exportado: "
        f"{mandates_path} ({len(mandates)} rows), "
        f"{sources_path} ({len(sources)}), "
        f"{people_path} ({len(people)} personas)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
