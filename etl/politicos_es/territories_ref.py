from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any

from .util import now_utc_iso, normalize_ws


DEFAULT_POPULATION_REF = Path("etl/data/published/poblacion_municipios_es.json")


def _digits(value: Any) -> str:
    return "".join(ch for ch in normalize_ws(str(value or "")) if ch.isdigit())


def _norm_ccaa_code(value: Any) -> str:
    token = _digits(value)
    if not token:
        return ""
    try:
        return str(int(token)).zfill(2)
    except ValueError:
        return ""


def _norm_province_code(value: Any) -> str:
    token = _digits(value)
    if not token:
        return ""
    return token.zfill(2)[-2:]


def _norm_municipality_code(value: Any) -> str:
    token = _digits(value)
    if not token:
        return ""
    # INE municipality codes are 5 digits, but some sources append a suffix digit.
    if len(token) == 6:
        token = token[:5]
    return token.zfill(5)[-5:]


def _upsert_territory(
    conn: sqlite3.Connection,
    *,
    code: str,
    name: str,
    level: str | None,
    parent_territory_id: int | None,
    now_iso: str,
) -> int:
    row = conn.execute(
        """
        INSERT INTO territories (code, name, level, parent_territory_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
          name=excluded.name,
          level=excluded.level,
          parent_territory_id=excluded.parent_territory_id,
          updated_at=excluded.updated_at
        RETURNING territory_id
        """,
        (code, name, level, parent_territory_id, now_iso, now_iso),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"No se pudo upsert territory code={code!r}")
    return int(row["territory_id"])


def backfill_territories_reference(
    conn: sqlite3.Connection,
    *,
    ref_path: Path = DEFAULT_POPULATION_REF,
) -> dict[str, Any]:
    """Load a pragmatic ES territory reference (country/CCAA/province/municipality).

    Notes:
    - This is an explicit backfill (not part of hot-path ingest).
    - It keeps existing territory codes intact; it just enriches `territories`
      with `name`, `level` and `parent_territory_id` for known codes.
    - Many upstream sources store municipality codes with an extra suffix digit;
      we map those by their 5-digit INE prefix when possible.
    """
    if not ref_path.exists():
        raise FileNotFoundError(f"No existe ref_path: {ref_path}")

    payload = json.loads(ref_path.read_text(encoding="utf-8"))
    municipalities = payload.get("municipalities") or []
    provinces = payload.get("provinces") or []
    autonomies = payload.get("autonomies") or []

    now_iso = now_utc_iso()

    with conn:
        es_id = _upsert_territory(
            conn,
            code="ES",
            name="España",
            level="country",
            parent_territory_id=None,
            now_iso=now_iso,
        )

        ccaa_id_by_code: dict[str, int] = {}
        for row in autonomies:
            ccaa_code = _norm_ccaa_code(row.get("ccaa_code"))
            ccaa_name = normalize_ws(str(row.get("ccaa_name") or ""))
            if not ccaa_code or not ccaa_name:
                continue
            ccaa_id_by_code[ccaa_code] = _upsert_territory(
                conn,
                code=f"CCAA{ccaa_code}",
                name=ccaa_name,
                level="ccaa",
                parent_territory_id=es_id,
                now_iso=now_iso,
            )

        prov_id_by_code: dict[str, int] = {}
        for row in provinces:
            prov_code = _norm_province_code(row.get("province_code"))
            prov_name = normalize_ws(str(row.get("province_name") or ""))
            ccaa_code = _norm_ccaa_code(row.get("ccaa_code"))
            if not prov_code or not prov_name:
                continue
            parent_ccaa_id = ccaa_id_by_code.get(ccaa_code)
            prov_id_by_code[prov_code] = _upsert_territory(
                conn,
                code=prov_code,
                name=prov_name,
                level="province",
                parent_territory_id=parent_ccaa_id,
                now_iso=now_iso,
            )

        muni_name_by_code: dict[str, str] = {}
        for row in municipalities:
            muni_code = _norm_municipality_code(row.get("municipality_code"))
            muni_name = normalize_ws(str(row.get("municipality_name") or ""))
            if not muni_code or not muni_name:
                continue
            muni_name_by_code[muni_code] = muni_name

        # Upsert 5-digit municipality codes (from ref) for future-proofing.
        muni_rows: list[tuple[str, str, str, int | None, str, str]] = []
        for muni_code, muni_name in muni_name_by_code.items():
            parent_prov_id = prov_id_by_code.get(muni_code[:2])
            muni_rows.append((muni_code, muni_name, "municipality", parent_prov_id, now_iso, now_iso))

        conn.executemany(
            """
            INSERT INTO territories (code, name, level, parent_territory_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
              name=excluded.name,
              level=excluded.level,
              parent_territory_id=excluded.parent_territory_id,
              updated_at=excluded.updated_at
            """,
            muni_rows,
        )

        # Enrich existing 6-digit municipality-like codes by their 5-digit INE prefix.
        code6_rows = conn.execute(
            """
            SELECT code
            FROM territories
            WHERE LENGTH(code) = 6 AND code GLOB '[0-9]*'
            """
        ).fetchall()
        updates: list[tuple[str, str, int | None, str, str]] = []
        updated_code6 = 0
        for r in code6_rows:
            code6 = str(r["code"] or "").strip()
            if len(code6) != 6 or not code6.isdigit():
                continue
            code5 = code6[:5]
            muni_name = muni_name_by_code.get(code5)
            if not muni_name:
                continue
            parent_prov_id = prov_id_by_code.get(code5[:2])
            updates.append((muni_name, "municipality", parent_prov_id, now_iso, code6))
            updated_code6 += 1

        if updates:
            conn.executemany(
                """
                UPDATE territories
                SET name = ?,
                    level = ?,
                    parent_territory_id = ?,
                    updated_at = ?
                WHERE code = ?
                """,
                updates,
            )

    levels_total = int((conn.execute("SELECT COUNT(*) AS c FROM territories WHERE level IS NOT NULL AND TRIM(level) <> ''").fetchone() or {"c": 0})["c"])
    muni_level_total = int((conn.execute("SELECT COUNT(*) AS c FROM territories WHERE level = 'municipality'").fetchone() or {"c": 0})["c"])

    return {
        "ref_path": str(ref_path),
        "ref_source_url": payload.get("source_url"),
        "territories_with_level": levels_total,
        "municipalities_level_total": muni_level_total,
        "updated_existing_code6": updated_code6,
        "ccaa_total": len(ccaa_id_by_code),
        "province_total": len(prov_id_by_code),
        "municipality_ref_total": len(muni_rows),
        "generated_at": now_iso,
    }

