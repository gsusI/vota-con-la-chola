from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from typing import Any

from etl.politicos_es.util import normalize_ws, now_utc_iso, sha256_bytes, stable_json

from .db import upsert_parl_initiatives, upsert_source_records


EXPEDIENTE_RE = re.compile(r"\b(?P<tipo>\d{3})\s*/\s*(?P<num>\d{1,6})(?:\s*/\s*(?P<sub>\d{1,4}))?\b")
SENADO_EXPEDIENTE_RE = re.compile(r"\b\d{3}/\d{6}\b")
CANON_EXPEDIENTE_RE = re.compile(r"^(?P<tipo>\d{3})/(?P<num>\d{1,6})(?:/(?P<sub>\d{1,4}))?$")
CONGRESO_LEY_EXPEDIENTE_RE = re.compile(
    r"\b(?:real\s+decreto-ley|real\s+decreto\s+ley)\s+(?P<num>\d{1,3})/(?P<year>\d{4})\b",
    re.I,
)
TITLE_PREFIX_INDEX_CHARS = 24
TITLE_PREFIX_MIN_CHARS = 40
DERIVED_INITIATIVE_SUPERTYPE = "derived"


def _congreso_derived_initiative_id(*, legislature: str | None, title_key: str) -> str:
    leg = normalize_ws(str(legislature or "")) or "unknown"
    digest = sha256_bytes(title_key.encode("utf-8"))[:24]
    return f"congreso:leg{leg}:derived:{digest}"


def _asciify(value: str | None) -> str:
    txt = normalize_ws(str(value or "")).strip().lower()
    if not txt:
        return ""
    return "".join(ch for ch in unicodedata.normalize("NFD", txt) if unicodedata.category(ch) != "Mn")


def _normalize_title_key(value: str | None) -> str | None:
    txt = normalize_ws(str(value or "")).lower()
    if not txt:
        return None
    no_accents = "".join(ch for ch in unicodedata.normalize("NFD", txt) if unicodedata.category(ch) != "Mn")
    cleaned = re.sub(r"[^a-z0-9]+", " ", no_accents)
    cleaned = normalize_ws(cleaned)
    return cleaned or None


_CONGRESO_VOTE_PREFIX_PATTERNS = (
    re.compile(r"^\s*votacion de la enmienda a la totalidad de texto alternativo a\s*", re.I),
    re.compile(r"^\s*votacion de la enmienda a la totalidad de\s*", re.I),
    re.compile(r"^\s*votacion de la solicitud de avocacion por el pleno de la camara de la\s*", re.I),
    re.compile(r"^\s*votacion de la solicitud de avocacion por el pleno de la camara\s*", re.I),
    re.compile(r"^\s*votacion de\s*", re.I),
)

_CONGRESO_VOTE_GROUP_PREFIX_PATTERNS = (
    (re.compile(r"^(proposicion no de ley)\s+del grupo parlamentario\b[^,\n]+,?\s*", re.I), r"\1 "),
    (re.compile(r"^(proposicion de ley)\s+del grupo parlamentario\b[^,\n]+,?\s*", re.I), r"\1 "),
    (re.compile(r"^(mocion consecuencia de interpelacion urgente)\s+del grupo parlamentario\b[^,\n]+,?\s*", re.I), r"\1 "),
    (re.compile(r"^(mocion consecuencia de interpelacion urgente)\s+del grupo parlamentario\b.*\)", re.I), r"\1 "),
)

_CONGRESO_VOTE_SUFFIX_PATTERNS = (
    re.compile(r",\s*presentada por .*?$", re.I),
    re.compile(r",\s*presentado por .*?$", re.I),
    re.compile(r",\s*en los terminos de .*?$", re.I),
    re.compile(r"\bse vota en los terminos.*$", re.I),
)


def _congreso_vote_title_key_variants(value: str | None) -> list[str]:
    base = _asciify(value)
    if not base:
        return []

    seeds = {base}
    first_line = base.split("\n", 1)[0].strip()
    if first_line:
        seeds.add(first_line)

    variants = set(seeds)
    for seed in list(seeds):
        for pattern in _CONGRESO_VOTE_PREFIX_PATTERNS:
            stripped = normalize_ws(pattern.sub("", seed))
            if stripped:
                variants.add(stripped)

        for pattern, replacement in _CONGRESO_VOTE_GROUP_PREFIX_PATTERNS:
            replaced = normalize_ws(pattern.sub(replacement, seed))
            if replaced:
                variants.add(replaced)

        for seed2 in list(variants):
            for pattern in _CONGRESO_VOTE_SUFFIX_PATTERNS:
                stripped = normalize_ws(pattern.sub("", seed2))
                if stripped:
                    variants.add(stripped)

    keys = {_normalize_title_key(v) for v in variants}
    return sorted((key for key in keys if key is not None), reverse=True, key=len)


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
        """
    ).fetchall()
    init_exact_map: dict[tuple[str | None, str], set[str]] = {}
    init_prefix_map: dict[tuple[str | None, str], set[str]] = {}
    title_exact_map: dict[tuple[str | None, str], set[str]] = {}
    title_prefix_map: dict[tuple[str | None, str], set[str]] = {}
    init_title_key: dict[str, str] = {}

    for r in init_rows:
        leg = normalize_ws(str(r["legislature"] or "")) or None
        if not leg:
            # Keep entries with unknown legislature, as many congreso law initiatives
            # do not expose legislature in source payload.
            pass
        initiative_id = str(r["initiative_id"])
        exp = normalize_ws(str(r["expediente"] or "")) or None
        if exp:
            for map_leg in (leg, None):
                init_exact_map.setdefault((map_leg, exp), set()).add(initiative_id)
                exp_prefix = _congreso_expediente_prefix(exp)
                if exp_prefix:
                    init_prefix_map.setdefault((map_leg, exp_prefix), set()).add(initiative_id)

        title_key = _normalize_title_key(r["title"])
        if title_key:
            for map_leg in (leg, None):
                title_exact_map.setdefault((map_leg, title_key), set()).add(initiative_id)
            prefix_key = title_key[:TITLE_PREFIX_INDEX_CHARS]
            for map_leg in (leg, None):
                title_prefix_map.setdefault((map_leg, prefix_key), set()).add(initiative_id)
            init_title_key[initiative_id] = title_key

    q = """
    SELECT vote_event_id, legislature, source_url, expediente_text, subgroup_title, subgroup_text, title
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
    derived_by_id: dict[str, dict[str, Any]] = {}
    derived_sr_rows: list[dict[str, Any]] = []
    derived_created = 0

    for row in vote_rows:
        seen += 1
        vote_event_id = str(row["vote_event_id"])
        leg = row["legislature"]
        if leg is None:
            leg = None
        else:
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
                exact_candidates = init_exact_map.get((leg, exp), set())
                if len(exact_candidates) == 1:
                    initiative_id = next(iter(exact_candidates))
                elif not exact_candidates:
                    legacy_candidates = init_exact_map.get((None, exp), set())
                    if len(legacy_candidates) == 1:
                        initiative_id = next(iter(legacy_candidates))
                link_method = "expediente_regex"
                confidence = 1.0
            else:
                pref_ids = init_prefix_map.get((leg, exp), set())
                if not pref_ids:
                    pref_ids = init_prefix_map.get((None, exp), set())
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

        title_key_candidates: list[tuple[str, str]] = []
        for field, text in haystacks:
            if not text:
                continue
            for key in _congreso_vote_title_key_variants(text):
                title_key_candidates.append((field, key))

        title_key_candidates.sort(key=lambda item: len(item[1]), reverse=True)
        for field, topic_key in title_key_candidates:
            exact_ids = title_exact_map.get((leg, topic_key), set())
            if not exact_ids:
                exact_ids = title_exact_map.get((None, topic_key), set())
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
                            {"field": field, "title_key": topic_key, "legislature": leg}
                        ),
                        "created_at": now_iso,
                        "updated_at": now_iso,
                    }
                break

            if len(exact_ids) == 0 and len(topic_key) >= TITLE_PREFIX_MIN_CHARS:
                prefix_key = topic_key[:TITLE_PREFIX_INDEX_CHARS]
                candidate_ids = title_prefix_map.get((leg, prefix_key), set())
                if not candidate_ids:
                    candidate_ids = title_prefix_map.get((None, prefix_key), set())
                matched_ids: set[str] = set()
                for initiative_id in candidate_ids:
                    init_key = init_title_key.get(initiative_id)
                    if not init_key:
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
                                    "field": field,
                                    "title_key_prefix": topic_key[:TITLE_PREFIX_MIN_CHARS],
                                    "legislature": leg,
                                }
                            ),
                            "created_at": now_iso,
                            "updated_at": now_iso,
                        }
                        break

        if len(best_links) == 0 and row["expediente_text"]:
            topic_text = normalize_ws(str(row["expediente_text"]) or "")
            m = CONGRESO_LEY_EXPEDIENTE_RE.search(topic_text)
            if m:
                ley_exp = f"ley:{int(m.group('num'))}/{m.group('year')}"
                candidates = {
                    *(init_exact_map.get((leg, ley_exp), set()) or set()),
                    *(init_exact_map.get((None, ley_exp), set()) if leg is not None else set()),
                }
                if len(candidates) == 1:
                    initiative_id = next(iter(candidates))
                    prev = best_links.get(initiative_id)
                    if not prev or float(prev.get("confidence") or 0.0) < 0.9:
                        best_links[initiative_id] = {
                            "vote_event_id": vote_event_id,
                            "initiative_id": initiative_id,
                            "link_method": "congreso_law_expediente",
                            "confidence": 0.9,
                            "evidence_json": stable_json(
                                {
                                    "field": "expediente_text",
                                    "expediente": ley_exp,
                                    "legislature": leg,
                                }
                            ),
                            "created_at": now_iso,
                            "updated_at": now_iso,
                        }

        # If we couldn't link to an official initiative, derive a stable "initiative" key from
        # the most descriptive text available. This is explicit (supertype='derived') and exists
        # mainly to keep votes groupable/topic-able when Congreso OpenData doesn't publish the
        # underlying initiative dataset (e.g., PNLs, certain motions).
        if len(best_links) == 0:
            source_field = None
            best_title_key = None
            best_raw_title = None
            for field, text in haystacks:
                if not text:
                    continue
                keys = _congreso_vote_title_key_variants(text)
                if not keys:
                    continue
                source_field = field
                best_title_key = keys[0]
                best_raw_title = normalize_ws(str(text).split("\n", 1)[0])
                break

            if best_title_key:
                derived_id = _congreso_derived_initiative_id(legislature=leg, title_key=best_title_key)
                if derived_id not in derived_by_id:
                    source_url = normalize_ws(str(row["source_url"] or "")) or None
                    if not source_url:
                        if vote_event_id.startswith("url:"):
                            source_url = vote_event_id[4:]
                        elif vote_event_id.lower().startswith("http"):
                            source_url = vote_event_id

                    raw_payload = stable_json(
                        {
                            "derived_from": "congreso_votaciones",
                            "legislature": leg,
                            "source_field": source_field,
                            "title_key": best_title_key,
                        }
                    )
                    derived_sr_rows.append({"source_record_id": derived_id, "raw_payload": raw_payload})
                    derived_by_id[derived_id] = {
                        "initiative_id": derived_id,
                        "legislature": leg,
                        "expediente": f"derived:{sha256_bytes(best_title_key.encode('utf-8'))[:24]}",
                        "supertype": DERIVED_INITIATIVE_SUPERTYPE,
                        "grouping": "Derived from Congreso votaciones",
                        "type": None,
                        "title": best_raw_title or derived_id,
                        "presented_date": None,
                        "qualified_date": None,
                        "author_text": None,
                        "procedure_type": None,
                        "result_text": None,
                        "current_status": None,
                        "competent_committee": None,
                        "deadlines_text": None,
                        "rapporteurs_text": None,
                        "processing_text": None,
                        "related_initiatives_text": None,
                        "links_bocg_json": None,
                        "links_ds_json": None,
                        "source_id": "congreso_votaciones",
                        "source_url": source_url,
                        "source_record_pk": None,  # resolved below via source_records
                        "source_snapshot_date": None,
                        "raw_payload": raw_payload,
                        "created_at": now_iso,
                        "updated_at": now_iso,
                    }

                evidence = stable_json(
                    {
                        "field": source_field,
                        "title_key": best_title_key,
                        "legislature": leg,
                        "derived": True,
                    }
                )
                best_links[derived_id] = {
                    "vote_event_id": vote_event_id,
                    "initiative_id": derived_id,
                    "link_method": "derived_title_key",
                    "confidence": 1.0,
                    "evidence_json": evidence,
                    "created_at": now_iso,
                    "updated_at": now_iso,
                }

        link_rows.extend(best_links.values())

    if not dry_run and derived_by_id:
        rows = list(derived_by_id.values())
        pk_map = upsert_source_records(
            conn,
            source_id="congreso_votaciones",
            rows=derived_sr_rows,
            snapshot_date=None,
            now_iso=now_iso,
        )
        for row in rows:
            row["source_record_pk"] = pk_map.get(row["initiative_id"])
        upsert_parl_initiatives(conn, source_id="congreso_votaciones", rows=rows)
        derived_created = len(rows)

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
        "derived_initiatives": 0 if dry_run else derived_created,
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
