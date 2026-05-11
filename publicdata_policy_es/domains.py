from __future__ import annotations

import sqlite3

from publicdata_core.util import normalize_ws


def upsert_domain(
    conn: sqlite3.Connection,
    *,
    canonical_key_value: str,
    label: str,
    description: str | None,
    tier: int | None,
    now_iso: str,
) -> int:
    key = normalize_ws(canonical_key_value)
    if not key:
        raise ValueError("canonical_key_value is required")

    row = conn.execute(
        """
        INSERT INTO domains (canonical_key, label, description, tier, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(canonical_key) DO UPDATE SET
          label=excluded.label,
          description=excluded.description,
          tier=excluded.tier,
          updated_at=excluded.updated_at
        RETURNING domain_id
        """,
        (
            key,
            normalize_ws(label) or key,
            description,
            tier,
            now_iso,
            now_iso,
        ),
    ).fetchone()
    if row is None:
        raise RuntimeError("No se pudo resolver domain_id")
    return int(row["domain_id"])
