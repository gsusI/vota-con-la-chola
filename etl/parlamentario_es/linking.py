from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from typing import Any

from etl.politicos_es.util import normalize_ws, now_utc_iso, stable_json


EXPEDIENTE_RE = re.compile(r"\b(?P<tipo>\d{3})\s*/\s*(?P<num>\d{1,6})(?:\s*/\s*(?P<sub>\d{1,4}))?\b")
SENADO_EXPEDIENTE_RE = re.compile(r"\b\d{3}/\d{6}\b")
CANON_EXPEDIENTE_RE = re.compile(r"^(?P<tipo>\d{3})/(?P<num>\d{1,6})(?:/(?P<sub>\d{1,4}))?$")
TITLE_PREFIX_INDEX_CHARS = 24
TITLE_PREFIX_MIN_CHARS = 40


def _normalize_title_key(value: str | None) -> str | None:
    txt = normalize_ws(str(value or "")).lower()
    if not txt:
        return None
    no_accents = "".join(ch for ch in unicodedata.normalize("NFD", txt) if unicodedata.category(ch) != "Mn")
    cleaned = re.sub(r"[^a-z0-9]+", " ", no_accents)
    cleaned = normalize_ws(cleaned)
    return cleaned or None


def _congreso_expediente_prefix(value: str | None) -> str | None:
    txt = normalize_ws(str(value or ""))
    if not txt:
        return None
    m = CANON_EXPEDIENTE_RE.match(txt)
    if not m:
        return None
    tipo = m.group("tipo")
    num = m.group("num").zfill(6)
    return f"{tipo}/{num}"


def _common_prefix_len(a: str, b: str) -> int:
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def link_congreso_votes_to_initiatives(
    conn: sqlite3.Connection,
    *,
    max_events: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Best-effort deterministic linking using expediente numbers embedded in vote text.

    Congreso roll-call vote JSON doesn't expose initiative IDs; sometimes the free-text
    fields contain an expediente like '121/000001/0000'. When present, we link with
    confidence 1.0 and store the evidence. As fallback, we link by unique normalized
    title match against Congreso initiatives in the same legislature.
    """
    # Preload Congreso initiatives for O(1) exact matching + bounded title fallback.
    init_rows = conn.execute(
        """
        SELECT initiative_id, legislature, expediente, title
        FROM parl_initiatives
        WHERE source_id = 'congreso_iniciativas'
          AND legislature IS NOT NULL
        """
    ).fetchall()
    init_exact_map: dict[tuple[str, str], str] = {}
    init_prefix_map: dict[tuple[str, str], set[str]] = {}
    title_exact_map: dict[tuple[str, str], set[str]] = {}
    title_prefix_map: dict[tuple[str, str], set[str]] = {}
    init_title_key: dict[str, str] = {}

    for r in init_rows:
        leg = normalize_ws(str(r["legislature"] or "")) or None
        if not leg:
            continue
        initiative_id = str(r["initiative_id"])
        exp = normalize_ws(str(r["expediente"] or "")) or None
        if exp:
            init_exact_map[(leg, exp)] = initiative_id
            exp_prefix = _congreso_expediente_prefix(exp)
            if exp_prefix:
                init_prefix_map.setdefault((leg, exp_prefix), set()).add(initiative_id)

        title_key = _normalize_title_key(r["title"])
        if title_key:
            title_exact_map.setdefault((leg, title_key), set()).add(initiative_id)
            prefix_key = title_key[:TITLE_PREFIX_INDEX_CHARS]
            title_prefix_map.setdefault((leg, prefix_key), set()).add(initiative_id)
            init_title_key[initiative_id] = title_key

    q = """
    SELECT vote_event_id, legislature, expediente_text, subgroup_title, subgroup_text, title
    FROM parl_vote_events
    WHERE source_id = 'congreso_votaciones'
    ORDER BY vote_date, session_number, vote_number
    """
    if isinstance(max_events, int) and max_events > 0:
        q += f" LIMIT {int(max_events)}"

    vote_rows = conn.execute(q).fetchall()
    seen = 0
    inserted = 0
    now_iso = now_utc_iso()
    link_rows: list[dict[str, Any]] = []

    for row in vote_rows:
        seen += 1
        vote_event_id = str(row["vote_event_id"])
        leg = row["legislature"]
        if leg is None:
            continue
        leg = str(leg)
        best_links: dict[str, dict[str, Any]] = {}

        haystacks = [
            ("expediente_text", row["expediente_text"]),
            ("subgroup_title", row["subgroup_title"]),
            ("subgroup_text", row["subgroup_text"]),
            ("title", row["title"]),
        ]
        found: list[tuple[str, str, str]] = []
        for field, text in haystacks:
            if not text:
                continue
            for m in EXPEDIENTE_RE.finditer(str(text)):
                tipo = m.group("tipo")
                num = m.group("num").zfill(6)
                sub = m.group("sub")
                if sub is not None:
                    found.append((field, "exact", f"{tipo}/{num}/{sub.zfill(4)}"))
                else:
                    found.append((field, "prefix", f"{tipo}/{num}"))

        # Deduplicate deterministically.
        seen_pairs: set[tuple[str, str, str]] = set()
        deduped: list[tuple[str, str, str]] = []
        for field, exp_kind, exp in found:
            k = (field, exp_kind, exp)
            if k in seen_pairs:
                continue
            seen_pairs.add(k)
            deduped.append(k)

        for field, exp_kind, exp in deduped:
            initiative_id = None
            link_method = None
            confidence = None
            if exp_kind == "exact":
                initiative_id = init_exact_map.get((leg, exp))
                link_method = "expediente_regex"
                confidence = 1.0
            else:
                pref_ids = init_prefix_map.get((leg, exp), set())
                if len(pref_ids) == 1:
                    initiative_id = next(iter(pref_ids))
                    link_method = "expediente_prefix_regex_unique"
                    confidence = 0.95
            if not initiative_id:
                continue
            prev = best_links.get(initiative_id)
            if prev and float(prev.get("confidence") or 0.0) >= float(confidence or 0.0):
                continue
            evidence = stable_json({"field": field, "expediente": exp, "legislature": leg})
            best_links[initiative_id] = {
                "vote_event_id": vote_event_id,
                "initiative_id": initiative_id,
                "link_method": link_method,
                "confidence": confidence,
                "evidence_json": evidence,
                "created_at": now_iso,
                "updated_at": now_iso,
            }

        topic_text = normalize_ws(str(row["expediente_text"] or "")) or None
        topic_key = _normalize_title_key(topic_text)
        if topic_key:
            exact_ids = title_exact_map.get((leg, topic_key), set())
            if len(exact_ids) == 1:
                initiative_id = next(iter(exact_ids))
                prev = best_links.get(initiative_id)
                if not prev or float(prev.get("confidence") or 0.0) < 0.85:
                    best_links[initiative_id] = {
                        "vote_event_id": vote_event_id,
                        "initiative_id": initiative_id,
                        "link_method": "title_norm_exact_unique",
                        "confidence": 0.85,
                        "evidence_json": stable_json(
                            {"field": "expediente_text", "title_key": topic_key, "legislature": leg}
                        ),
                        "created_at": now_iso,
                        "updated_at": now_iso,
                    }
            elif len(exact_ids) == 0 and len(topic_key) >= TITLE_PREFIX_MIN_CHARS:
                prefix_key = topic_key[:TITLE_PREFIX_INDEX_CHARS]
                candidate_ids = title_prefix_map.get((leg, prefix_key), set())
                matched_ids: set[str] = set()
                for initiative_id in candidate_ids:
                    init_key = init_title_key.get(initiative_id)
                    if not init_key:
                        continue
                    if not (init_key.startswith(topic_key) or topic_key.startswith(init_key)):
                        continue
                    if _common_prefix_len(init_key, topic_key) < TITLE_PREFIX_MIN_CHARS:
                        continue
                    matched_ids.add(initiative_id)
                if len(matched_ids) == 1:
                    initiative_id = next(iter(matched_ids))
                    prev = best_links.get(initiative_id)
                    if not prev or float(prev.get("confidence") or 0.0) < 0.75:
                        best_links[initiative_id] = {
                            "vote_event_id": vote_event_id,
                            "initiative_id": initiative_id,
                            "link_method": "title_norm_prefix_unique",
                            "confidence": 0.75,
                            "evidence_json": stable_json(
                                {
                                    "field": "expediente_text",
                                    "title_key_prefix": topic_key[:TITLE_PREFIX_MIN_CHARS],
                                    "legislature": leg,
                                }
                            ),
                            "created_at": now_iso,
                            "updated_at": now_iso,
                        }

        link_rows.extend(best_links.values())

    if not dry_run and link_rows:
        conn.executemany(
            """
            INSERT INTO parl_vote_event_initiatives (
              vote_event_id, initiative_id, link_method, confidence, evidence_json, created_at, updated_at
            ) VALUES (
              :vote_event_id, :initiative_id, :link_method, :confidence, :evidence_json, :created_at, :updated_at
            )
            ON CONFLICT(vote_event_id, initiative_id, link_method) DO UPDATE SET
              confidence=excluded.confidence,
              evidence_json=excluded.evidence_json,
              updated_at=excluded.updated_at
            """,
            link_rows,
        )
        inserted = len(link_rows)
        conn.commit()

    return {
        "events_seen": seen,
        "links_prepared": len(link_rows),
        "links_written": 0 if dry_run else inserted,
        "dry_run": bool(dry_run),
    }


def link_senado_votes_to_initiatives(
    conn: sqlite3.Connection,
    *,
    max_events: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Deterministic linking for Senado using exact (legislature, expediente)."""
    init_rows = conn.execute(
        """
        SELECT initiative_id, legislature, expediente
        FROM parl_initiatives
        WHERE source_id = 'senado_iniciativas'
          AND legislature IS NOT NULL
          AND expediente IS NOT NULL
        """
    ).fetchall()
    init_map: dict[tuple[str, str], str] = {}
    for r in init_rows:
        init_map[(str(r["legislature"]), str(r["expediente"]))] = str(r["initiative_id"])

    q = """
    SELECT vote_event_id, legislature, expediente_text, title, raw_payload
    FROM parl_vote_events
    WHERE source_id = 'senado_votaciones'
    ORDER BY vote_date, session_number, vote_number
    """
    if isinstance(max_events, int) and max_events > 0:
        q += f" LIMIT {int(max_events)}"

    rows = conn.execute(q).fetchall()
    seen = 0
    now_iso = now_utc_iso()
    links: list[dict[str, Any]] = []

    for row in rows:
        seen += 1
        vote_event_id = str(row["vote_event_id"])
        leg = normalize_ws(str(row["legislature"] or ""))
        if not leg:
            continue

        payload = {}
        raw_payload = row["raw_payload"]
        if raw_payload:
            try:
                parsed = json.loads(str(raw_payload))
                if isinstance(parsed, dict):
                    payload = parsed
            except Exception:  # noqa: BLE001
                payload = {}

        tipo_ex = normalize_ws(str(payload.get("tipo_expediente") or "")) or None
        num_ex = normalize_ws(str(payload.get("numero_expediente") or "")) or None
        expediente = f"{tipo_ex}/{num_ex}" if (tipo_ex and num_ex) else None

        link_method = None
        confidence = None
        evidence: dict[str, Any] = {}

        if expediente:
            link_method = "leg_expediente_payload_exact"
            confidence = 1.0
            evidence = {"field": "payload.tipo+numero", "expediente": expediente, "legislature": leg}
        else:
            for field, text in (("expediente_text", row["expediente_text"]), ("title", row["title"])):
                if not text:
                    continue
                m = SENADO_EXPEDIENTE_RE.search(str(text))
                if m:
                    expediente = m.group(0)
                    link_method = "leg_expediente_regex"
                    confidence = 0.9
                    evidence = {"field": field, "expediente": expediente, "legislature": leg}
                    break

        if not expediente or not link_method or confidence is None:
            continue
        initiative_id = init_map.get((leg, expediente))
        if not initiative_id:
            continue

        links.append(
            {
                "vote_event_id": vote_event_id,
                "initiative_id": initiative_id,
                "link_method": link_method,
                "confidence": confidence,
                "evidence_json": stable_json(evidence),
                "created_at": now_iso,
                "updated_at": now_iso,
            }
        )

    if not dry_run and links:
        conn.executemany(
            """
            INSERT INTO parl_vote_event_initiatives (
              vote_event_id, initiative_id, link_method, confidence, evidence_json, created_at, updated_at
            ) VALUES (
              :vote_event_id, :initiative_id, :link_method, :confidence, :evidence_json, :created_at, :updated_at
            )
            ON CONFLICT(vote_event_id, initiative_id, link_method) DO UPDATE SET
              confidence=excluded.confidence,
              evidence_json=excluded.evidence_json,
              updated_at=excluded.updated_at
            """,
            links,
        )
        conn.commit()

    return {
        "events_seen": seen,
        "links_prepared": len(links),
        "links_written": 0 if dry_run else len(links),
        "dry_run": bool(dry_run),
    }
