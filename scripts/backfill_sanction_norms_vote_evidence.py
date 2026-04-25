#!/usr/bin/env python3
"""Backfill sanction-responsibility evidence from parliamentary vote events."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import open_db
from etl.politicos_es.util import normalize_ws

BOE_ID_RE = re.compile(r"BOE-A-\d{4}-\d{1,6}", re.IGNORECASE)

# Conservative title/legal-reference rules to avoid over-attribution.
TITLE_MATCH_RULES: dict[str, list[tuple[str, tuple[str, ...]]]] = {
    "BOE-A-1994-8985": [
        ("rd_320_1994_trafico", ("real decreto 320/1994", "trafico")),
    ],
    "BOE-A-2000-15060": [
        (
            "rdl_5_2000_infracciones_orden_social",
            ("real decreto legislativo 5/2000", "infracciones", "orden social"),
        ),
    ],
    "BOE-A-2003-23514": [
        (
            "ley_58_2003_general_tributaria",
            ("ley 58/2003", "general tributaria"),
        ),
    ],
    "BOE-A-2004-18398": [
        (
            "rd_2063_2004_regimen_sancionador_tributario",
            ("real decreto 2063/2004", "sancionador", "tributari"),
        ),
    ],
    "BOE-A-2015-11722": [
        (
            "rdl_6_2015_trafico_seguridad_vial",
            (
                "real decreto legislativo 6/2015",
                "trafico",
                "seguridad vial",
            ),
        ),
    ],
    "BOE-A-2015-11724": [
        ("lo_4_2015_seguridad_ciudadana", ("ley organica 4/2015", "seguridad ciudadana")),
        (
            "proteccion_libertades_seguridad_ciudadana",
            ("proteccion de las libertades y seguridad ciudadana",),
        ),
    ],
}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return normalize_ws(str(v or ""))


def _fold(v: Any) -> str:
    text = _norm(v).lower()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return normalize_ws(text)


def _parse_roles(raw: str) -> list[str]:
    allowed = {"propose", "approve", "delegate", "enforce", "audit"}
    out: list[str] = []
    for token in str(raw or "").split(","):
        role = _norm(token).lower()
        if role and role in allowed and role not in out:
            out.append(role)
    return out


def _source_exists(conn: sqlite3.Connection, source_id: str) -> bool:
    sid = _norm(source_id)
    if not sid:
        return False
    row = conn.execute("SELECT 1 FROM sources WHERE source_id = ?", (sid,)).fetchone()
    return row is not None


def _iter_sanction_norm_index(conn: sqlite3.Connection) -> tuple[dict[str, str], dict[str, str]]:
    rows = conn.execute(
        """
        SELECT DISTINCT
          UPPER(TRIM(COALESCE(n.boe_id, ''))) AS boe_id,
          n.norm_id
        FROM sanction_norm_catalog c
        JOIN legal_norms n ON n.norm_id = c.norm_id
        WHERE TRIM(COALESCE(n.boe_id, '')) <> ''
        """
    ).fetchall()
    norm_by_boe: dict[str, str] = {}
    boe_by_norm: dict[str, str] = {}
    for row in rows:
        boe_id = _norm(row["boe_id"]).upper()
        norm_id = _norm(row["norm_id"])
        if not boe_id or not norm_id:
            continue
        norm_by_boe[boe_id] = norm_id
        boe_by_norm[norm_id] = boe_id
    return norm_by_boe, boe_by_norm


def _iter_lineage_relations(conn: sqlite3.Connection) -> dict[str, dict[str, str]]:
    rows = conn.execute(
        """
        SELECT
          e.norm_id,
          e.related_norm_id,
          e.relation_type
        FROM legal_norm_lineage_edges e
        JOIN sanction_norm_catalog c ON c.norm_id = e.norm_id
        WHERE TRIM(COALESCE(e.norm_id, '')) <> ''
          AND TRIM(COALESCE(e.related_norm_id, '')) <> ''
          AND TRIM(COALESCE(e.relation_type, '')) <> ''
        """
    ).fetchall()
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        norm_id = _norm(row["norm_id"])
        related_norm_id = _norm(row["related_norm_id"])
        relation_type = _norm(row["relation_type"]).lower()
        if not norm_id or not related_norm_id or not relation_type:
            continue
        out.setdefault(norm_id, {})[related_norm_id] = relation_type
    return out


def _iter_vote_link_rows(conn: sqlite3.Connection, *, limit_events: int) -> list[sqlite3.Row]:
    sql = """
        SELECT
          pve.vote_event_id,
          pve.source_id AS vote_source_id,
          pve.source_url AS vote_source_url,
          pve.source_record_pk AS vote_source_record_pk,
          pve.vote_date,
          pve.title AS vote_title,
          pve.expediente_text AS vote_expediente_text,
          pvi.initiative_id,
          pi.source_id AS initiative_source_id,
          pi.legislature AS initiative_legislature,
          pi.expediente AS initiative_expediente,
          pi.title AS initiative_title
        FROM parl_vote_event_initiatives pvi
        JOIN parl_vote_events pve ON pve.vote_event_id = pvi.vote_event_id
        LEFT JOIN parl_initiatives pi ON pi.initiative_id = pvi.initiative_id
    """
    params: list[Any] = []
    if int(limit_events) > 0:
        sql += """
        WHERE pve.vote_event_id IN (
          SELECT vote_event_id
          FROM parl_vote_events
          ORDER BY COALESCE(vote_date, '') DESC, vote_event_id DESC
          LIMIT ?
        )
        """
        params.append(int(limit_events))

    sql += """
        ORDER BY COALESCE(pve.vote_date, '') DESC, pve.vote_event_id DESC, pvi.initiative_id
    """
    return conn.execute(sql, tuple(params)).fetchall()


def _resolve_responsibilities(
    conn: sqlite3.Connection,
    *,
    boe_id: str,
    roles: list[str],
) -> list[sqlite3.Row]:
    if not roles:
        return []
    placeholders = ",".join(["?"] * len(roles))
    params: list[Any] = [boe_id, *roles]
    sql = f"""
        SELECT
          r.responsibility_id,
          r.role,
          r.fragment_id,
          n.norm_id,
          n.boe_id
        FROM legal_fragment_responsibilities r
        JOIN legal_norm_fragments f ON f.fragment_id = r.fragment_id
        JOIN legal_norms n ON n.norm_id = f.norm_id
        JOIN sanction_norm_fragment_links l ON l.fragment_id = r.fragment_id
        WHERE UPPER(TRIM(COALESCE(n.boe_id, ''))) = ?
          AND r.role IN ({placeholders})
        ORDER BY r.responsibility_id
    """
    return conn.execute(sql, tuple(params)).fetchall()


def _candidate_evidence_type(vote_source_id: str) -> str:
    src = _norm(vote_source_id).lower()
    if src.startswith("congreso_"):
        return "congreso_vote"
    if src.startswith("senado_"):
        return "senado_vote"
    return "other"


def _match_boe_ids(
    *,
    text_raw: str,
    sanction_boe_ids: set[str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    boe_tokens = {m.group(0).upper() for m in BOE_ID_RE.finditer(text_raw)}
    for boe_id in sorted(boe_tokens):
        if boe_id in sanction_boe_ids:
            out.append(
                {
                    "boe_id": boe_id,
                    "match_method": "boe_id_exact_in_vote_or_initiative_text",
                    "match_confidence": 1.0,
                    "matched_terms": [boe_id],
                }
            )
    return out


def _match_title_rules(
    *,
    text_folded: str,
    sanction_boe_ids: set[str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for boe_id, rules in TITLE_MATCH_RULES.items():
        if boe_id not in sanction_boe_ids:
            continue
        for rule_name, terms in rules:
            if all(term in text_folded for term in terms):
                out.append(
                    {
                        "boe_id": boe_id,
                        "match_method": f"title_rule:{rule_name}",
                        "match_confidence": 0.9,
                        "matched_terms": list(terms),
                    }
                )
                break
    return out


def _expand_lineage_candidates(
    *,
    candidates: list[dict[str, Any]],
    norm_by_boe: dict[str, str],
    boe_by_norm: dict[str, str],
    lineage_relations: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for cand in candidates:
        base_boe_id = _norm(cand.get("boe_id")).upper()
        base_norm_id = _norm(norm_by_boe.get(base_boe_id))
        if not base_boe_id or not base_norm_id:
            continue

        direct_payload = dict(cand)
        direct_payload.setdefault("candidate_boe_id", base_boe_id)
        direct_payload.setdefault("bridge_kind", "")
        direct_payload.setdefault("bridge_from_boe_id", "")
        direct_payload.setdefault("bridge_anchor_related_boe_id", "")
        direct_payload.setdefault("bridge_anchor_related_norm_id", "")
        out.append(direct_payload)

        base_rel = lineage_relations.get(base_norm_id, {})
        base_deroga_related = {
            rid for rid, relation in base_rel.items() if relation == "deroga" and _norm(rid)
        }
        base_confidence = float(cand.get("match_confidence") or 0.0)
        base_terms = [str(t) for t in list(cand.get("matched_terms", []))]

        for target_norm_id, target_boe_id in boe_by_norm.items():
            if target_norm_id == base_norm_id:
                continue
            if not target_boe_id:
                continue

            target_rel = lineage_relations.get(target_norm_id, {})
            bridge_kind = ""
            bridge_anchor_related_norm_id = ""
            bridge_anchor_related_boe_id = ""
            confidence_penalty = 0.0

            relation_to_base = _norm(target_rel.get(base_norm_id)).lower()
            if relation_to_base in {"desarrolla", "modifica"}:
                bridge_kind = f"lineage_target_to_vote_norm:{relation_to_base}"
                confidence_penalty = 0.15
            else:
                target_deroga_related = {
                    rid for rid, relation in target_rel.items() if relation == "deroga" and _norm(rid)
                }
                shared_deroga = sorted(base_deroga_related.intersection(target_deroga_related))
                if shared_deroga:
                    bridge_kind = "lineage_shared_deroga_related_norm"
                    bridge_anchor_related_norm_id = shared_deroga[0]
                    bridge_anchor_related_boe_id = _norm(
                        boe_by_norm.get(bridge_anchor_related_norm_id)
                    ).upper()
                    confidence_penalty = 0.2
                else:
                    shared_related_mixed: list[str] = []
                    for related_norm_id in sorted(set(base_rel.keys()).intersection(target_rel.keys())):
                        base_relation = _norm(base_rel.get(related_norm_id)).lower()
                        target_relation = _norm(target_rel.get(related_norm_id)).lower()
                        relation_pair = {base_relation, target_relation}
                        if "deroga" in relation_pair and relation_pair.intersection(
                            {"desarrolla", "modifica"}
                        ):
                            shared_related_mixed.append(related_norm_id)
                    if shared_related_mixed:
                        bridge_kind = "lineage_shared_related_norm_mixed_relation"
                        bridge_anchor_related_norm_id = shared_related_mixed[0]
                        bridge_anchor_related_boe_id = _norm(
                            boe_by_norm.get(bridge_anchor_related_norm_id)
                        ).upper()
                        confidence_penalty = 0.25

            if not bridge_kind:
                continue

            bridge_confidence = max(0.0, base_confidence - confidence_penalty)
            matched_terms = [*base_terms]
            if bridge_anchor_related_boe_id:
                matched_terms.append(f"lineage_anchor:{bridge_anchor_related_boe_id}")

            out.append(
                {
                    **cand,
                    "boe_id": target_boe_id,
                    "match_method": f"{cand['match_method']}+{bridge_kind}",
                    "match_confidence": bridge_confidence,
                    "matched_terms": matched_terms,
                    "candidate_boe_id": base_boe_id,
                    "bridge_kind": bridge_kind,
                    "bridge_from_boe_id": base_boe_id,
                    "bridge_anchor_related_boe_id": bridge_anchor_related_boe_id,
                    "bridge_anchor_related_norm_id": bridge_anchor_related_norm_id,
                }
            )
    return out


def _best_candidates_by_vote_event(
    rows: list[sqlite3.Row],
    *,
    sanction_boe_ids: set[str],
    norm_by_boe: dict[str, str],
    boe_by_norm: dict[str, str],
    lineage_relations: dict[str, dict[str, str]],
) -> tuple[dict[tuple[str, str], dict[str, Any]], int]:
    best: dict[tuple[str, str], dict[str, Any]] = {}
    rows_with_candidates = 0

    for row in rows:
        vote_event_id = _norm(row["vote_event_id"])
        vote_title = _norm(row["vote_title"])
        initiative_title = _norm(row["initiative_title"])
        vote_expediente_text = _norm(row["vote_expediente_text"])

        merged_raw = " ".join([vote_title, initiative_title, vote_expediente_text]).strip()
        merged_folded = _fold(merged_raw)

        candidates = _match_boe_ids(text_raw=merged_raw, sanction_boe_ids=sanction_boe_ids)
        if not candidates:
            candidates = _match_title_rules(text_folded=merged_folded, sanction_boe_ids=sanction_boe_ids)
        if not candidates:
            continue

        expanded_candidates = _expand_lineage_candidates(
            candidates=candidates,
            norm_by_boe=norm_by_boe,
            boe_by_norm=boe_by_norm,
            lineage_relations=lineage_relations,
        )
        if not expanded_candidates:
            continue

        rows_with_candidates += 1
        for cand in expanded_candidates:
            key = (vote_event_id, str(cand["boe_id"]))
            current = best.get(key)
            payload = {
                "vote_event_id": vote_event_id,
                "boe_id": str(cand["boe_id"]),
                "match_method": str(cand["match_method"]),
                "match_confidence": float(cand["match_confidence"]),
                "matched_terms": list(cand["matched_terms"]),
                "candidate_boe_id": _norm(cand.get("candidate_boe_id")).upper(),
                "bridge_kind": _norm(cand.get("bridge_kind")),
                "bridge_from_boe_id": _norm(cand.get("bridge_from_boe_id")).upper(),
                "bridge_anchor_related_boe_id": _norm(cand.get("bridge_anchor_related_boe_id")).upper(),
                "bridge_anchor_related_norm_id": _norm(cand.get("bridge_anchor_related_norm_id")),
                "vote_source_id": _norm(row["vote_source_id"]),
                "vote_source_url": _norm(row["vote_source_url"]),
                "vote_source_record_pk": int(row["vote_source_record_pk"])
                if row["vote_source_record_pk"] is not None
                else None,
                "vote_date": _norm(row["vote_date"]),
                "vote_title": vote_title,
                "initiative_id": _norm(row["initiative_id"]),
                "initiative_source_id": _norm(row["initiative_source_id"]),
                "initiative_legislature": _norm(row["initiative_legislature"]),
                "initiative_expediente": _norm(row["initiative_expediente"]),
                "initiative_title": initiative_title,
            }
            if current is None:
                best[key] = payload
                continue
            if float(payload["match_confidence"]) > float(current["match_confidence"]):
                best[key] = payload
                continue
            if (
                float(payload["match_confidence"]) == float(current["match_confidence"])
                and str(payload["initiative_id"]) < str(current["initiative_id"])
            ):
                best[key] = payload

    return best, rows_with_candidates


def _extract_quote(text: str, *, max_chars: int = 240) -> str:
    return _norm(str(text or "")[:max_chars])


def backfill(
    conn: sqlite3.Connection,
    *,
    roles: list[str],
    limit_events: int,
) -> dict[str, Any]:
    roles_norm = [r for r in roles if r]
    if not roles_norm:
        raise ValueError("at least one role is required")

    now_iso = now_utc_iso()
    norm_by_boe, boe_by_norm = _iter_sanction_norm_index(conn)
    sanction_boe_ids = set(norm_by_boe.keys())
    lineage_relations = _iter_lineage_relations(conn)
    vote_rows = _iter_vote_link_rows(conn, limit_events=int(limit_events))
    vote_event_ids = {str(r["vote_event_id"]) for r in vote_rows if _norm(r["vote_event_id"])}

    candidates_by_key, rows_with_candidates = _best_candidates_by_vote_event(
        vote_rows,
        sanction_boe_ids=sanction_boe_ids,
        norm_by_boe=norm_by_boe,
        boe_by_norm=boe_by_norm,
        lineage_relations=lineage_relations,
    )

    counts: dict[str, int] = {
        "vote_link_rows_scanned_total": len(vote_rows),
        "vote_events_scanned_total": len(vote_event_ids),
        "vote_rows_with_candidate_total": int(rows_with_candidates),
        "candidate_matches_total": len(candidates_by_key),
        "candidates_without_responsibility_total": 0,
        "evidence_inserted": 0,
        "evidence_updated": 0,
    }
    by_boe_id: dict[str, int] = {}
    by_method: dict[str, int] = {}
    by_evidence_type: dict[str, int] = {}
    samples: list[dict[str, Any]] = []

    for (_, boe_id), cand in sorted(candidates_by_key.items(), key=lambda item: item[0]):
        by_boe_id[boe_id] = int(by_boe_id.get(boe_id, 0)) + 1
        method = str(cand["match_method"])
        by_method[method] = int(by_method.get(method, 0)) + 1

        responsibilities = _resolve_responsibilities(conn, boe_id=boe_id, roles=roles_norm)
        if not responsibilities:
            counts["candidates_without_responsibility_total"] += 1
            if len(samples) < 20:
                samples.append(
                    {
                        "boe_id": boe_id,
                        "vote_event_id": str(cand["vote_event_id"]),
                        "initiative_id": str(cand["initiative_id"]),
                        "reason": "no_matching_responsibility_for_roles",
                        "roles": roles_norm,
                        "match_method": method,
                    }
                )
            continue

        evidence_type = _candidate_evidence_type(str(cand["vote_source_id"]))
        by_evidence_type[evidence_type] = int(by_evidence_type.get(evidence_type, 0)) + len(responsibilities)

        src_for_fk = _norm(cand["vote_source_id"])
        if not _source_exists(conn, src_for_fk):
            src_for_fk = _norm(cand["initiative_source_id"])
        if not _source_exists(conn, src_for_fk):
            src_for_fk = ""

        source_url = _norm(cand["vote_source_url"])
        evidence_date = _norm(cand["vote_date"]) or now_iso[:10]
        evidence_quote = _extract_quote(str(cand["vote_title"]))
        vote_event_id = _norm(cand["vote_event_id"])

        for resp in responsibilities:
            responsibility_id = int(resp["responsibility_id"])
            exists = conn.execute(
                """
                SELECT responsibility_evidence_id
                FROM legal_fragment_responsibility_evidence
                WHERE responsibility_id = ?
                  AND evidence_type = ?
                  AND COALESCE(json_extract(raw_payload, '$.vote_event_id'), '') = ?
                """,
                (responsibility_id, evidence_type, vote_event_id),
            ).fetchone()
            if exists is None:
                # Backward-compatible fallback for legacy rows without vote_event_id in payload.
                exists = conn.execute(
                    """
                    SELECT responsibility_evidence_id
                    FROM legal_fragment_responsibility_evidence
                    WHERE responsibility_id = ?
                      AND evidence_type = ?
                      AND COALESCE(source_url, '') = ?
                      AND COALESCE(evidence_date, '') = ?
                    """,
                    (responsibility_id, evidence_type, source_url, evidence_date),
                ).fetchone()

            payload = {
                "record_kind": "sanction_norm_vote_evidence_backfill",
                "match_method": method,
                "match_confidence": float(cand["match_confidence"]),
                "matched_terms": list(cand["matched_terms"]),
                "boe_id": boe_id,
                "candidate_boe_id": _norm(cand.get("candidate_boe_id")).upper(),
                "bridge_kind": _norm(cand.get("bridge_kind")),
                "bridge_from_boe_id": _norm(cand.get("bridge_from_boe_id")).upper(),
                "bridge_anchor_related_boe_id": _norm(cand.get("bridge_anchor_related_boe_id")).upper(),
                "bridge_anchor_related_norm_id": _norm(cand.get("bridge_anchor_related_norm_id")),
                "norm_id": _norm(resp["norm_id"]),
                "responsibility_id": responsibility_id,
                "role": _norm(resp["role"]),
                "vote_event_id": vote_event_id,
                "vote_source_id": _norm(cand["vote_source_id"]),
                "vote_title": _norm(cand["vote_title"]),
                "vote_date": evidence_date,
                "initiative_id": _norm(cand["initiative_id"]),
                "initiative_source_id": _norm(cand["initiative_source_id"]),
                "initiative_title": _norm(cand["initiative_title"]),
                "initiative_expediente": _norm(cand["initiative_expediente"]),
                "initiative_legislature": _norm(cand["initiative_legislature"]),
            }
            raw_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True)

            if exists is None:
                conn.execute(
                    """
                    INSERT INTO legal_fragment_responsibility_evidence (
                      responsibility_id,
                      evidence_type,
                      source_id,
                      source_url,
                      source_record_pk,
                      evidence_date,
                      evidence_quote,
                      raw_payload,
                      created_at,
                      updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        responsibility_id,
                        evidence_type,
                        src_for_fk or None,
                        source_url or None,
                        int(cand["vote_source_record_pk"])
                        if cand["vote_source_record_pk"] is not None
                        else None,
                        evidence_date or None,
                        evidence_quote or None,
                        raw_payload,
                        now_iso,
                        now_iso,
                    ),
                )
                counts["evidence_inserted"] += 1
            else:
                conn.execute(
                    """
                    UPDATE legal_fragment_responsibility_evidence
                    SET
                      source_id = ?,
                      source_url = ?,
                      source_record_pk = ?,
                      evidence_date = ?,
                      evidence_quote = ?,
                      raw_payload = ?,
                      updated_at = ?
                    WHERE responsibility_evidence_id = ?
                    """,
                    (
                        src_for_fk or None,
                        source_url or None,
                        int(cand["vote_source_record_pk"])
                        if cand["vote_source_record_pk"] is not None
                        else None,
                        evidence_date or None,
                        evidence_quote or None,
                        raw_payload,
                        now_iso,
                        int(exists["responsibility_evidence_id"]),
                    ),
                )
                counts["evidence_updated"] += 1

            if len(samples) < 20:
                samples.append(
                    {
                        "boe_id": boe_id,
                        "norm_id": _norm(resp["norm_id"]),
                        "responsibility_id": responsibility_id,
                        "role": _norm(resp["role"]),
                        "vote_event_id": _norm(cand["vote_event_id"]),
                        "initiative_id": _norm(cand["initiative_id"]),
                        "evidence_type": evidence_type,
                        "match_method": method,
                        "source_url": source_url,
                        "evidence_date": evidence_date,
                    }
                )

    conn.commit()
    return {
        "generated_at": now_iso,
        "roles": roles_norm,
        "limit_events": int(limit_events),
        "counts": counts,
        "by_boe_id": by_boe_id,
        "by_method": by_method,
        "by_evidence_type": by_evidence_type,
        "samples": samples,
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Backfill sanction responsibilities with congreso/senado vote evidence"
    )
    ap.add_argument("--db", required=True)
    ap.add_argument("--roles", default="approve,propose")
    ap.add_argument("--limit-events", type=int, default=0)
    ap.add_argument("--out", default="")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    roles = _parse_roles(args.roles)
    conn = open_db(Path(args.db))
    try:
        report = backfill(conn, roles=roles, limit_events=int(args.limit_events))
    finally:
        conn.close()

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if _norm(args.out):
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
