from __future__ import annotations

import json
import sqlite3
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable


URL_CANDIDATE_KEYS: tuple[str, ...] = (
    "detail_url",
    "profile_url",
    "ficha_url",
    "source_url",
    "url",
    "link",
    "web",
    "pagina",
)


def _parse_json_maybe(text: str) -> Any | None:
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        return None


def _first_url_in_payload(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for k in URL_CANDIDATE_KEYS:
            v = payload.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        # Shallow search for url-like keys (best-effort for new connectors).
        for k, v in payload.items():
            if not isinstance(k, str):
                continue
            if "url" not in k.lower():
                continue
            if isinstance(v, str) and v.strip():
                return v.strip()
    return None


def _sha256_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def build_representantes_snapshot(
    conn: sqlite3.Connection,
    *,
    snapshot_date: str,
    active_only: bool = True,
    exclude_levels: Iterable[str] = ("municipal",),
    limit: int | None = None,
) -> dict[str, Any]:
    exclude_levels = tuple(str(x) for x in exclude_levels if str(x).strip())

    where = ["1=1"]
    params: list[Any] = []

    if active_only:
        where.append("m.is_active = 1")
    if exclude_levels:
        where.append("m.level NOT IN (" + ",".join("?" for _ in exclude_levels) + ")")
        params.extend(exclude_levels)

    sql = f"""
        SELECT
          m.mandate_id AS mandate_id,
          m.role_title AS role_title,
          m.level AS level,
          m.territory_code AS mandate_territory_code,
          m.start_date AS start_date,
          m.end_date AS end_date,
          m.is_active AS is_active,
          m.source_id AS source_id,
          m.source_record_id AS source_record_id,
          m.source_snapshot_date AS source_snapshot_date,
          m.raw_payload AS mandate_raw_payload,

          p.person_id AS person_id,
          p.full_name AS full_name,
          p.given_name AS given_name,
          p.family_name AS family_name,
          p.gender AS gender,
          p.birth_date AS birth_date,
          p.territory_code AS person_territory_code,
          p.canonical_key AS person_canonical_key,

          i.institution_id AS institution_id,
          i.name AS institution_name,
          i.level AS institution_level,
          i.territory_code AS institution_territory_code,

          pa.party_id AS party_id,
          pa.name AS party_name,
          pa.acronym AS party_acronym,

          s.default_url AS source_default_url,

          sr.source_record_pk AS source_record_pk,
          sr.content_sha256 AS source_record_content_sha256,
          sr.raw_payload AS source_record_raw_payload
        FROM mandates m
        JOIN persons p ON p.person_id = m.person_id
        JOIN institutions i ON i.institution_id = m.institution_id
        LEFT JOIN parties pa ON pa.party_id = m.party_id
        JOIN sources s ON s.source_id = m.source_id
        LEFT JOIN source_records sr ON sr.source_record_pk = m.source_record_pk
        WHERE {" AND ".join(where)}
        ORDER BY
          m.level,
          i.name,
          p.full_name,
          m.role_title,
          m.source_id,
          m.source_record_id
    """

    if limit is not None:
        sql += "\nLIMIT ?"
        params.append(int(limit))

    rows = conn.execute(sql, params).fetchall()

    items: list[dict[str, Any]] = []
    counts_by_source: dict[str, int] = {}
    counts_by_level: dict[str, int] = {}

    for r in rows:
        payload_text = str(r["source_record_raw_payload"] or r["mandate_raw_payload"] or "")
        payload_obj = _parse_json_maybe(payload_text) if payload_text else None

        default_url = str(r["source_default_url"] or "")
        source_url = _first_url_in_payload(payload_obj) if payload_obj is not None else None
        if not source_url:
            source_url = default_url

        source_hash = str(r["source_record_content_sha256"] or "").strip()
        if not source_hash:
            source_hash = _sha256_text(payload_text)

        source_id = str(r["source_id"])
        level = str(r["level"])
        counts_by_source[source_id] = counts_by_source.get(source_id, 0) + 1
        counts_by_level[level] = counts_by_level.get(level, 0) + 1

        items.append(
            {
                "person": {
                    "person_id": int(r["person_id"]),
                    "full_name": str(r["full_name"]),
                    "given_name": r["given_name"],
                    "family_name": r["family_name"],
                    "gender": r["gender"],
                    "birth_date": r["birth_date"],
                    "territory_code": str(r["person_territory_code"] or ""),
                    "canonical_key": str(r["person_canonical_key"] or ""),
                },
                "mandate": {
                    "mandate_id": int(r["mandate_id"]),
                    "role_title": str(r["role_title"]),
                    "level": level,
                    "territory_code": str(r["mandate_territory_code"] or ""),
                    "start_date": r["start_date"],
                    "end_date": r["end_date"],
                    "is_active": int(r["is_active"]),
                },
                "institution": {
                    "institution_id": int(r["institution_id"]),
                    "name": str(r["institution_name"]),
                    "level": str(r["institution_level"]),
                    "territory_code": str(r["institution_territory_code"] or ""),
                },
                "party": (
                    None
                    if r["party_id"] is None
                    else {
                        "party_id": int(r["party_id"]),
                        "name": str(r["party_name"]),
                        "acronym": r["party_acronym"],
                    }
                ),
                "source": {
                    "source_id": source_id,
                    "source_record_id": str(r["source_record_id"]),
                    "source_snapshot_date": r["source_snapshot_date"],
                    "source_default_url": default_url,
                    "source_url": source_url,
                    "source_hash": source_hash,
                    "source_record_pk": r["source_record_pk"],
                },
            }
        )

    snapshot: dict[str, Any] = {
        "fecha_referencia": snapshot_date,
        # Deterministic timestamp for a given snapshot date.
        "generado_en": f"{snapshot_date}T00:00:00+00:00",
        "filtros": {
            "active_only": bool(active_only),
            "exclude_levels": list(exclude_levels),
        },
        "totales": {
            "items": len(items),
            "por_source_id": dict(sorted(counts_by_source.items())),
            "por_level": dict(sorted(counts_by_level.items())),
        },
        "items": items,
    }
    return snapshot


def write_json_if_changed(path: Path, obj: Any) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    if path.exists():
        old = path.read_text(encoding="utf-8")
        if old == text:
            return False
    path.write_text(text, encoding="utf-8")
    return True

