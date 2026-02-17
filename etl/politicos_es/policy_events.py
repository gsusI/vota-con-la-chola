from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from .util import now_utc_iso


MONCLOA_INSTRUMENTS: dict[str, tuple[str, str, str]] = {
    "moncloa_referencias": (
        "exec_reference",
        "Referencia del Consejo de Ministros",
        "Referencia oficial publicada por La Moncloa.",
    ),
    "moncloa_rss_referencias": (
        "exec_rss_reference",
        "RSS de referencias/resumenes del Consejo de Ministros",
        "Entrada RSS de La Moncloa relacionada con referencias o resumenes.",
    ),
}

BOE_INSTRUMENTS: dict[str, tuple[str, str, str]] = {
    "boe_legal_document": (
        "boe_legal_document",
        "Documento legal BOE",
        "Documento normativo o acto oficial publicado en BOE (referencia BOE-A/BOE-B/otros).",
    ),
    "boe_daily_summary": (
        "boe_daily_summary",
        "Sumario diario BOE",
        "Entrada de sumario diario del BOE (referencia BOE-S).",
    ),
}

BOE_REF_RE = re.compile(r"\b(BOE-[A-Z]-\d{4}-\d+)\b", flags=re.I)

MONEY_POLICY_INSTRUMENTS: dict[str, tuple[str, str, str]] = {
    "placsp_contratacion": (
        "public_contracting",
        "Contratacion publica",
        "Evento de contratacion publica derivado de PLACSP (licitacion/adjudicacion).",
    ),
    "bdns_subvenciones": (
        "public_subsidy",
        "Subvencion publica",
        "Evento de subvencion/ayuda publica derivado de BDNS/SNPSAP.",
    ),
}

PLACSP_SOURCE_IDS = ("placsp_sindicacion", "placsp_autonomico")
BDNS_SOURCE_IDS = ("bdns_api_subvenciones", "bdns_autonomico")
MONEY_SOURCE_IDS = PLACSP_SOURCE_IDS + BDNS_SOURCE_IDS


def _normalize_iso_date(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return None


def _normalize_amount(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    token = str(value).strip()
    if not token:
        return None
    token = token.replace("EUR", "").replace("eur", "").replace("€", "").replace(" ", "")
    if not token:
        return None
    if "," in token and "." in token:
        if token.rfind(",") > token.rfind("."):
            token = token.replace(".", "").replace(",", ".")
        else:
            token = token.replace(",", "")
    elif "," in token:
        parts = token.split(",")
        if len(parts) == 2 and len(parts[1]) <= 3:
            token = token.replace(".", "").replace(",", ".")
        else:
            token = token.replace(",", "")
    try:
        return float(token)
    except ValueError:
        return None


def _extract_source_url(payload: dict[str, Any]) -> str | None:
    for key in ("source_url", "guid", "link", "source_url_raw"):
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _extract_boe_ref(payload: dict[str, Any], source_record_id: str) -> str | None:
    for candidate in (
        payload.get("boe_ref"),
        source_record_id,
        payload.get("title"),
        payload.get("description"),
        payload.get("source_url"),
        payload.get("source_url_raw"),
    ):
        if candidate is None:
            continue
        text = str(candidate).strip()
        if not text:
            continue
        match = BOE_REF_RE.search(text)
        if match:
            return str(match.group(1)).upper()
    return None


def ensure_money_policy_instruments(conn: sqlite3.Connection) -> dict[str, int]:
    now_iso = now_utc_iso()
    instrument_ids: dict[str, int] = {}
    for source_id, (code, label, description) in MONEY_POLICY_INSTRUMENTS.items():
        row = conn.execute(
            """
            INSERT INTO policy_instruments (code, label, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
              label=excluded.label,
              description=excluded.description,
              updated_at=excluded.updated_at
            RETURNING policy_instrument_id
            """,
            (code, label, description, now_iso, now_iso),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"No se pudo resolver policy_instrument_id para {code}")
        instrument_ids[source_id] = int(row["policy_instrument_id"])
    return instrument_ids


def ensure_moncloa_policy_instruments(conn: sqlite3.Connection) -> dict[str, int]:
    now_iso = now_utc_iso()
    instrument_ids: dict[str, int] = {}
    for source_id, (code, label, description) in MONCLOA_INSTRUMENTS.items():
        row = conn.execute(
            """
            INSERT INTO policy_instruments (code, label, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
              label=excluded.label,
              description=excluded.description,
              updated_at=excluded.updated_at
            RETURNING policy_instrument_id
            """,
            (code, label, description, now_iso, now_iso),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"No se pudo resolver policy_instrument_id para {code}")
        instrument_ids[source_id] = int(row["policy_instrument_id"])
    return instrument_ids


def ensure_boe_policy_instruments(conn: sqlite3.Connection) -> dict[str, int]:
    now_iso = now_utc_iso()
    instrument_ids: dict[str, int] = {}
    for key, (code, label, description) in BOE_INSTRUMENTS.items():
        row = conn.execute(
            """
            INSERT INTO policy_instruments (code, label, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
              label=excluded.label,
              description=excluded.description,
              updated_at=excluded.updated_at
            RETURNING policy_instrument_id
            """,
            (code, label, description, now_iso, now_iso),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"No se pudo resolver policy_instrument_id para {code}")
        instrument_ids[key] = int(row["policy_instrument_id"])
    return instrument_ids


def backfill_moncloa_policy_events(
    conn: sqlite3.Connection,
    *,
    source_ids: tuple[str, ...] = ("moncloa_referencias", "moncloa_rss_referencias"),
) -> dict[str, Any]:
    now_iso = now_utc_iso()
    instruments = ensure_moncloa_policy_instruments(conn)

    stats: dict[str, Any] = {
        "sources": list(source_ids),
        "source_records_seen": 0,
        "source_records_mapped": 0,
        "source_records_skipped": 0,
        "policy_events_upserted": 0,
        "skips": [],
    }

    rows = conn.execute(
        f"""
        SELECT
          sr.source_record_pk,
          sr.source_id,
          sr.source_record_id,
          sr.source_snapshot_date,
          sr.raw_payload
        FROM source_records sr
        WHERE sr.source_id IN ({",".join("?" for _ in source_ids)})
        ORDER BY sr.source_id, sr.source_record_id
        """,
        source_ids,
    ).fetchall()

    for row in rows:
        stats["source_records_seen"] += 1
        source_id = str(row["source_id"])
        source_record_id = str(row["source_record_id"])
        source_record_pk = int(row["source_record_pk"])
        raw_payload = str(row["raw_payload"] or "")
        source_snapshot_date = row["source_snapshot_date"]
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "invalid_json_payload",
                }
            )
            continue
        if not isinstance(payload, dict):
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "payload_not_object",
                }
            )
            continue

        # Discovery index pages are not policy events.
        if source_record_id.endswith(":index.aspx"):
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "discovery_index_row",
                }
            )
            continue

        source_url = _extract_source_url(payload)
        if not source_url:
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "missing_source_url",
                }
            )
            continue

        # Rule: if event_date is not extractable reliably, keep published_date and leave event_date NULL.
        event_date = _normalize_iso_date(payload.get("event_date_iso"))
        published_date = _normalize_iso_date(payload.get("published_at_iso"))
        if published_date is None:
            published_date = event_date

        title = str(payload.get("title") or "").strip() or "Referencia Consejo de Ministros"
        summary_text = payload.get("summary_text")
        summary = str(summary_text).strip() if summary_text is not None else None
        if summary == "":
            summary = None

        policy_event_id = f"moncloa:{source_id}:{source_record_id}"
        instrument_id = instruments[source_id]
        conn.execute(
            """
            INSERT INTO policy_events (
              policy_event_id,
              event_date,
              published_date,
              domain_id,
              policy_instrument_id,
              title,
              summary,
              amount_eur,
              currency,
              institution_id,
              admin_level_id,
              territory_id,
              scope,
              source_id,
              source_url,
              source_record_pk,
              source_snapshot_date,
              raw_payload,
              created_at,
              updated_at
            ) VALUES (?, ?, ?, NULL, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(policy_event_id) DO UPDATE SET
              event_date=excluded.event_date,
              published_date=excluded.published_date,
              policy_instrument_id=excluded.policy_instrument_id,
              title=excluded.title,
              summary=excluded.summary,
              scope=excluded.scope,
              source_url=excluded.source_url,
              source_record_pk=excluded.source_record_pk,
              source_snapshot_date=excluded.source_snapshot_date,
              raw_payload=excluded.raw_payload,
              updated_at=excluded.updated_at
            """,
            (
                policy_event_id,
                event_date,
                published_date,
                instrument_id,
                title,
                summary,
                "ejecutivo",
                source_id,
                source_url,
                source_record_pk,
                source_snapshot_date,
                raw_payload,
                now_iso,
                now_iso,
            ),
        )
        stats["source_records_mapped"] += 1
        stats["policy_events_upserted"] += 1

    conn.commit()

    total_row = conn.execute(
        "SELECT COUNT(*) AS c FROM policy_events WHERE source_id IN ({})".format(
            ",".join("?" for _ in source_ids)
        ),
        source_ids,
    ).fetchone()
    with_url_row = conn.execute(
        "SELECT COUNT(*) AS c FROM policy_events WHERE source_id IN ({}) AND source_url IS NOT NULL AND trim(source_url) <> ''".format(
            ",".join("?" for _ in source_ids)
        ),
        source_ids,
    ).fetchone()
    null_event_with_published_row = conn.execute(
        "SELECT COUNT(*) AS c FROM policy_events WHERE source_id IN ({}) AND event_date IS NULL AND published_date IS NOT NULL".format(
            ",".join("?" for _ in source_ids)
        ),
        source_ids,
    ).fetchone()
    stats["policy_events_total"] = int(total_row["c"] if total_row else 0)
    stats["policy_events_with_source_url"] = int(with_url_row["c"] if with_url_row else 0)
    stats["policy_events_null_event_date_with_published"] = int(
        null_event_with_published_row["c"] if null_event_with_published_row else 0
    )
    return stats


def backfill_money_policy_events(
    conn: sqlite3.Connection,
    *,
    source_ids: tuple[str, ...] = MONEY_SOURCE_IDS,
) -> dict[str, Any]:
    now_iso = now_utc_iso()
    instruments = ensure_money_policy_instruments(conn)

    stats: dict[str, Any] = {
        "sources": list(source_ids),
        "source_records_seen": 0,
        "source_records_mapped": 0,
        "source_records_skipped": 0,
        "policy_events_upserted": 0,
        "skips": [],
    }

    rows = conn.execute(
        f"""
        SELECT
          sr.source_record_pk,
          sr.source_id,
          sr.source_record_id,
          sr.source_snapshot_date,
          sr.raw_payload
        FROM source_records sr
        WHERE sr.source_id IN ({",".join("?" for _ in source_ids)})
        ORDER BY sr.source_id, sr.source_record_id
        """,
        source_ids,
    ).fetchall()

    for row in rows:
        stats["source_records_seen"] += 1
        source_id = str(row["source_id"])
        source_record_id = str(row["source_record_id"])
        source_record_pk = int(row["source_record_pk"])
        raw_payload = str(row["raw_payload"] or "")
        source_snapshot_date = row["source_snapshot_date"]
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "invalid_json_payload",
                }
            )
            continue
        if not isinstance(payload, dict):
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "payload_not_object",
                }
            )
            continue

        source_url = _extract_source_url(payload)
        if not source_url:
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "missing_source_url",
                }
            )
            continue

        if source_id in PLACSP_SOURCE_IDS:
            canonical_source_id = "placsp_contratacion"
            instrument_id = instruments[canonical_source_id]
            expediente = str(payload.get("expediente") or "").strip()
            organo = str(payload.get("organo_contratacion") or "").strip()
            cpv = str(payload.get("cpv") or "").strip()
            title = str(payload.get("title") or "").strip()
            if not title:
                title = f"Contratacion publica {expediente}".strip() if expediente else "Contratacion publica"
            summary_parts = [part for part in (organo, cpv) if part]
            summary = " | ".join(summary_parts) if summary_parts else None
            event_date = None
            published_date = _normalize_iso_date(payload.get("published_at_iso")) or _normalize_iso_date(
                source_snapshot_date
            )
            amount_eur = _normalize_amount(payload.get("amount_eur"))
            currency = str(payload.get("currency") or "").strip() or ("EUR" if amount_eur is not None else None)
            policy_event_id = f"money:placsp:{source_id}:{source_record_id}"
        elif source_id in BDNS_SOURCE_IDS:
            canonical_source_id = "bdns_subvenciones"
            instrument_id = instruments[canonical_source_id]
            convocatoria = str(payload.get("convocatoria_id") or "").strip()
            concesion = str(payload.get("concesion_id") or "").strip()
            beneficiario = str(payload.get("beneficiario") or "").strip()
            title = convocatoria or concesion or "Subvencion publica"
            if beneficiario:
                title = f"{title} - {beneficiario}"
            # Ambiguous causal timing -> keep event_date NULL and rely on published_date.
            event_date = None
            published_date = _normalize_iso_date(payload.get("published_at_iso")) or _normalize_iso_date(
                source_snapshot_date
            )
            amount_eur = _normalize_amount(payload.get("importe_eur"))
            currency = str(payload.get("currency") or "").strip() or ("EUR" if amount_eur is not None else None)
            summary = str(payload.get("organo_convocante") or "").strip() or None
            policy_event_id = f"money:bdns:{source_id}:{source_record_id}"
        else:
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "unsupported_source_id",
                }
            )
            continue

        conn.execute(
            """
            INSERT INTO policy_events (
              policy_event_id,
              event_date,
              published_date,
              domain_id,
              policy_instrument_id,
              title,
              summary,
              amount_eur,
              currency,
              institution_id,
              admin_level_id,
              territory_id,
              scope,
              source_id,
              source_url,
              source_record_pk,
              source_snapshot_date,
              raw_payload,
              created_at,
              updated_at
            ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(policy_event_id) DO UPDATE SET
              event_date=excluded.event_date,
              published_date=excluded.published_date,
              policy_instrument_id=excluded.policy_instrument_id,
              title=excluded.title,
              summary=excluded.summary,
              amount_eur=excluded.amount_eur,
              currency=excluded.currency,
              scope=excluded.scope,
              source_id=excluded.source_id,
              source_url=excluded.source_url,
              source_record_pk=excluded.source_record_pk,
              source_snapshot_date=excluded.source_snapshot_date,
              raw_payload=excluded.raw_payload,
              updated_at=excluded.updated_at
            """,
            (
                policy_event_id,
                event_date,
                published_date,
                instrument_id,
                title,
                summary,
                amount_eur,
                currency,
                "dinero",
                canonical_source_id,
                source_url,
                source_record_pk,
                source_snapshot_date,
                raw_payload,
                now_iso,
                now_iso,
            ),
        )
        stats["source_records_mapped"] += 1
        stats["policy_events_upserted"] += 1

    conn.commit()

    canonical_sources = ("placsp_contratacion", "bdns_subvenciones")
    total_row = conn.execute(
        "SELECT COUNT(*) AS c FROM policy_events WHERE source_id IN (?, ?)",
        canonical_sources,
    ).fetchone()
    with_url_row = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM policy_events
        WHERE source_id IN (?, ?)
          AND source_url IS NOT NULL
          AND trim(source_url) <> ''
        """,
        canonical_sources,
    ).fetchone()
    with_pk_row = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM policy_events
        WHERE source_id IN (?, ?)
          AND source_record_pk IS NOT NULL
        """,
        canonical_sources,
    ).fetchone()
    by_source_rows = conn.execute(
        """
        SELECT source_id, COUNT(*) AS c
        FROM policy_events
        WHERE source_id IN (?, ?)
        GROUP BY source_id
        ORDER BY source_id
        """,
        canonical_sources,
    ).fetchall()
    stats["policy_events_total"] = int(total_row["c"] if total_row else 0)
    stats["policy_events_with_source_url"] = int(with_url_row["c"] if with_url_row else 0)
    stats["policy_events_with_source_record_pk"] = int(with_pk_row["c"] if with_pk_row else 0)
    stats["policy_events_by_source"] = {str(row["source_id"]): int(row["c"]) for row in by_source_rows}
    return stats


def backfill_boe_policy_events(
    conn: sqlite3.Connection,
    *,
    source_ids: tuple[str, ...] = ("boe_api_legal",),
) -> dict[str, Any]:
    now_iso = now_utc_iso()
    instruments = ensure_boe_policy_instruments(conn)

    stats: dict[str, Any] = {
        "sources": list(source_ids),
        "source_records_seen": 0,
        "source_records_mapped": 0,
        "source_records_skipped": 0,
        "policy_events_upserted": 0,
        "skips": [],
    }

    rows = conn.execute(
        f"""
        SELECT
          sr.source_record_pk,
          sr.source_id,
          sr.source_record_id,
          sr.source_snapshot_date,
          sr.raw_payload
        FROM source_records sr
        WHERE sr.source_id IN ({",".join("?" for _ in source_ids)})
        ORDER BY sr.source_id, sr.source_record_id
        """,
        source_ids,
    ).fetchall()

    for row in rows:
        stats["source_records_seen"] += 1
        source_id = str(row["source_id"])
        source_record_id = str(row["source_record_id"])
        source_record_pk = int(row["source_record_pk"])
        raw_payload = str(row["raw_payload"] or "")
        source_snapshot_date = row["source_snapshot_date"]
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "invalid_json_payload",
                }
            )
            continue
        if not isinstance(payload, dict):
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "payload_not_object",
                }
            )
            continue

        source_url = _extract_source_url(payload)
        if not source_url:
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "missing_source_url",
                }
            )
            continue

        boe_ref = _extract_boe_ref(payload, source_record_id) or ""
        title = str(payload.get("title") or "").strip() or (boe_ref or "Documento BOE")
        description = payload.get("description")
        summary = str(description).strip() if description is not None else None
        if summary == "":
            summary = None

        # Rule: keep event_date NULL for BOE feed rows unless a future deterministic
        # event-date contract is added. published_date remains the corroboration date.
        event_date = None
        published_date = _normalize_iso_date(payload.get("published_at_iso"))
        if published_date is None:
            published_date = _normalize_iso_date(source_snapshot_date)

        if boe_ref.startswith("BOE-S-") or "sumario" in title.lower():
            instrument_id = instruments["boe_daily_summary"]
        else:
            instrument_id = instruments["boe_legal_document"]

        id_suffix = boe_ref or source_record_id
        policy_event_id = f"boe:{source_id}:{id_suffix}"
        conn.execute(
            """
            INSERT INTO policy_events (
              policy_event_id,
              event_date,
              published_date,
              domain_id,
              policy_instrument_id,
              title,
              summary,
              amount_eur,
              currency,
              institution_id,
              admin_level_id,
              territory_id,
              scope,
              source_id,
              source_url,
              source_record_pk,
              source_snapshot_date,
              raw_payload,
              created_at,
              updated_at
            ) VALUES (?, ?, ?, NULL, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(policy_event_id) DO UPDATE SET
              event_date=excluded.event_date,
              published_date=excluded.published_date,
              policy_instrument_id=excluded.policy_instrument_id,
              title=excluded.title,
              summary=excluded.summary,
              scope=excluded.scope,
              source_url=excluded.source_url,
              source_record_pk=excluded.source_record_pk,
              source_snapshot_date=excluded.source_snapshot_date,
              raw_payload=excluded.raw_payload,
              updated_at=excluded.updated_at
            """,
            (
                policy_event_id,
                event_date,
                published_date,
                instrument_id,
                title,
                summary,
                "legal",
                source_id,
                source_url,
                source_record_pk,
                source_snapshot_date,
                raw_payload,
                now_iso,
                now_iso,
            ),
        )
        stats["source_records_mapped"] += 1
        stats["policy_events_upserted"] += 1

    conn.commit()

    total_row = conn.execute(
        "SELECT COUNT(*) AS c FROM policy_events WHERE source_id IN ({})".format(
            ",".join("?" for _ in source_ids)
        ),
        source_ids,
    ).fetchone()
    with_url_row = conn.execute(
        "SELECT COUNT(*) AS c FROM policy_events WHERE source_id IN ({}) AND source_url IS NOT NULL AND trim(source_url) <> ''".format(
            ",".join("?" for _ in source_ids)
        ),
        source_ids,
    ).fetchone()
    null_event_with_published_row = conn.execute(
        "SELECT COUNT(*) AS c FROM policy_events WHERE source_id IN ({}) AND event_date IS NULL AND published_date IS NOT NULL".format(
            ",".join("?" for _ in source_ids)
        ),
        source_ids,
    ).fetchone()
    stats["policy_events_total"] = int(total_row["c"] if total_row else 0)
    stats["policy_events_with_source_url"] = int(with_url_row["c"] if with_url_row else 0)
    stats["policy_events_null_event_date_with_published"] = int(
        null_event_with_published_row["c"] if null_event_with_published_row else 0
    )
    return stats
