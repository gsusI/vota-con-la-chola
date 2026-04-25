#!/usr/bin/env python3
"""Export a bounded, deterministic JSON snapshot for the citizen GH Pages app.

Goal:
- Turn existing analytics (topic_sets/topics/topic_positions) into a user-first artifact.
- Keep it static-friendly: no API required.
- Preserve honesty: expose coverage and avoid silent imputation.

Output:
- JSON file matching `docs/etl/sprints/AI-OPS-18/reports/citizen-data-contract.md`.

This exporter is intentionally conservative: it exports aggregated party stances per topic
(with coverage) and only links out to the existing explorers for audit/evidence drill-down.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_MAX_BYTES = 5_000_000
DEFAULT_TOPIC_SET_ID = 1
DEFAULT_INSTITUTION_ID = 7  # Congreso de los Diputados
DEFAULT_PROGRAMAS_SOURCE_ID = "programas_partidos"
DEFAULT_CONCERNS_CONFIG = Path("ui/citizen/concerns_v1.json")
CONF_TIER_HIGH_MIN = 0.66
CONF_TIER_MEDIUM_MIN = 0.33
SEVERE_REGRESSION_RATIO = 0.25

_PROGRAMAS_STANCE_METHODS = ("declared:regex_v3", "declared:regex_v2", "declared:regex_v1")


@dataclass(frozen=True)
class Scope:
    topic_set_id: int
    institution_id: int
    as_of_date: str
    computed_method: str
    computed_version: str


@dataclass(frozen=True)
class ConcernDef:
    id: str
    label: str
    keywords_norm: tuple[str, ...]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Exporta snapshot JSON para app ciudadana (GH Pages)")
    p.add_argument("--db", default=str(DEFAULT_DB), help="Ruta a la base SQLite")
    p.add_argument(
        "--out",
        required=True,
        help="Ruta de salida JSON (p.ej. ui/gh-pages-next/public/citizen/data/citizen.json)",
    )
    p.add_argument("--topic-set-id", type=int, default=DEFAULT_TOPIC_SET_ID)
    p.add_argument(
        "--as-of-date",
        default="",
        help="Fecha YYYY-MM-DD. Si se omite, se infiere el max(as_of_date) para el scope.",
    )
    p.add_argument(
        "--computed-method",
        default="auto",
        choices=("auto", "combined", "votes", "declared"),
        help="Metodo de posiciones a usar (auto=combined si existe, si no votes; declared=solo evidencia declarada)",
    )
    p.add_argument("--institution-id", type=int, default=DEFAULT_INSTITUTION_ID)
    p.add_argument("--max-topics", type=int, default=200)
    p.add_argument("--max-parties", type=int, default=40)
    p.add_argument("--max-items-per-concern", type=int, default=60)
    p.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    p.add_argument(
        "--fallback-snapshot",
        default="",
        help="Snapshot JSON previo a reutilizar si el export actual colapsa por debajo del minimo util",
    )
    p.add_argument("--pretty", action="store_true", help="Escribir JSON con indent=2 (mas grande)")
    return p.parse_args()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_date_utc(value: str) -> datetime | None:
    token = str(value or "").strip()
    if not token:
        return None
    try:
        if len(token) == 10:
            return datetime.fromisoformat(f"{token}T00:00:00+00:00")
        if token.endswith("Z"):
            token = f"{token[:-1]}+00:00"
        dt = datetime.fromisoformat(token)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def strip_diacritics(s: str) -> str:
    # Keep consistent with ui/citizen/index.html (NFD + strip combining marks).
    return "".join(ch for ch in unicodedata.normalize("NFD", str(s or "")) if not unicodedata.combining(ch))


def norm(s: str) -> str:
    return strip_diacritics(str(s or "")).lower().strip()


def load_concerns(path: Path) -> list[ConcernDef]:
    if not path.exists():
        return []
    obj = json.loads(path.read_text(encoding="utf-8"))
    concerns = obj.get("concerns") or []
    if not isinstance(concerns, list):
        return []

    out: list[ConcernDef] = []
    for c in concerns:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id") or "").strip()
        if not cid:
            continue
        label = str(c.get("label") or cid).strip()
        kws = c.get("keywords") or []
        if not isinstance(kws, list):
            kws = []
        kws_norm = tuple(sorted({k for k in (norm(x) for x in kws) if k}))
        out.append(ConcernDef(id=cid, label=label, keywords_norm=kws_norm))
    return out


def compute_topic_concern_ids(label: str, concerns: list[ConcernDef]) -> list[str]:
    ln = norm(label)
    if not ln:
        return []
    ids: set[str] = set()
    for c in concerns:
        if not c.id or not c.keywords_norm:
            continue
        if any(k in ln for k in c.keywords_norm):
            ids.add(c.id)
    return sorted(ids)


def methods_available(conn: sqlite3.Connection, *, topic_set_id: int, institution_id: int, as_of_date: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT computed_method, COUNT(*) AS c
        FROM topic_positions
        WHERE topic_set_id = ?
          AND institution_id = ?
          AND as_of_date = ?
        GROUP BY computed_method
        HAVING COUNT(*) > 0
        ORDER BY computed_method ASC
        """,
        (int(topic_set_id), int(institution_id), str(as_of_date)),
    ).fetchall()
    out = [str(r["computed_method"] or "").strip() for r in rows]
    out = [m for m in out if m]
    return sorted(set(out))


def _max_as_of_date(conn: sqlite3.Connection, *, topic_set_id: int, institution_id: int, computed_method: str) -> str:
    row = conn.execute(
        """
        SELECT MAX(as_of_date) AS d
        FROM topic_positions
        WHERE topic_set_id = ?
          AND institution_id = ?
          AND computed_method = ?
        """,
        (int(topic_set_id), int(institution_id), str(computed_method)),
    ).fetchone()
    if not row:
        return ""
    return str(row["d"] or "")


def _count_positions(conn: sqlite3.Connection, *, topic_set_id: int, institution_id: int, as_of_date: str, computed_method: str) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM topic_positions
        WHERE topic_set_id = ?
          AND institution_id = ?
          AND as_of_date = ?
          AND computed_method = ?
        """,
        (int(topic_set_id), int(institution_id), str(as_of_date), str(computed_method)),
    ).fetchone()
    if not row:
        return 0
    return int(row["c"] or 0)


def _topic_set_institution_id(conn: sqlite3.Connection, *, topic_set_id: int) -> int | None:
    row = conn.execute(
        """
        SELECT institution_id
        FROM topic_sets
        WHERE topic_set_id = ?
        """,
        (int(topic_set_id),),
    ).fetchone()
    if not row or row["institution_id"] is None:
        return None
    return int(row["institution_id"])


def _max_as_of_date_any_method(conn: sqlite3.Connection, *, topic_set_id: int, institution_id: int) -> str:
    row = conn.execute(
        """
        SELECT MAX(as_of_date) AS d
        FROM topic_positions
        WHERE topic_set_id = ?
          AND institution_id = ?
        """,
        (int(topic_set_id), int(institution_id)),
    ).fetchone()
    if not row:
        return ""
    return str(row["d"] or "")


def resolve_scope(conn: sqlite3.Connection, *, args: argparse.Namespace) -> Scope:
    topic_set_id = int(args.topic_set_id)
    institution_id = int(args.institution_id)
    topic_set_institution_id = _topic_set_institution_id(conn, topic_set_id=topic_set_id)
    institution_candidates: list[int] = []
    for candidate in (institution_id, topic_set_institution_id):
        if candidate is None:
            continue
        candidate_int = int(candidate)
        if candidate_int not in institution_candidates:
            institution_candidates.append(candidate_int)
    if not institution_candidates:
        institution_candidates.append(institution_id)

    method_pref = [str(args.computed_method)]
    if str(args.computed_method) == "auto":
        method_pref = ["combined", "votes"]

    as_of_date = str(args.as_of_date or "").strip()
    resolved_institution_id = institution_id

    if as_of_date:
        # Choose method given fixed date.
        chosen_method = None
        for candidate_institution_id in institution_candidates:
            for m in method_pref:
                if (
                    _count_positions(
                        conn,
                        topic_set_id=topic_set_id,
                        institution_id=candidate_institution_id,
                        as_of_date=as_of_date,
                        computed_method=m,
                    )
                    > 0
                ):
                    chosen_method = m
                    resolved_institution_id = candidate_institution_id
                    break
            if chosen_method is not None:
                break
        if chosen_method is None:
            fallback_institution_id = next(
                (
                    candidate_institution_id
                    for candidate_institution_id in institution_candidates
                    if _max_as_of_date_any_method(
                        conn,
                        topic_set_id=topic_set_id,
                        institution_id=candidate_institution_id,
                    )
                ),
                institution_candidates[0],
            )
            resolved_institution_id = int(fallback_institution_id)
            chosen_method = method_pref[0] if method_pref else str(args.computed_method)
        computed_method = chosen_method
    else:
        # Infer latest (method-first).
        computed_method = None
        inferred_date = ""
        for m in method_pref:
            for candidate_institution_id in institution_candidates:
                d = _max_as_of_date(conn, topic_set_id=topic_set_id, institution_id=candidate_institution_id, computed_method=m)
                if d:
                    computed_method = m
                    inferred_date = d
                    resolved_institution_id = candidate_institution_id
                    break
            if inferred_date:
                break
        if not computed_method or not inferred_date:
            fallback_institution_id = next(
                (
                    candidate_institution_id
                    for candidate_institution_id in institution_candidates
                    if _max_as_of_date_any_method(
                        conn,
                        topic_set_id=topic_set_id,
                        institution_id=candidate_institution_id,
                    )
                ),
                institution_candidates[0],
            )
            resolved_institution_id = int(fallback_institution_id)
            inferred_date = _max_as_of_date_any_method(
                conn,
                topic_set_id=topic_set_id,
                institution_id=resolved_institution_id,
            )
            computed_method = method_pref[0] if method_pref else str(args.computed_method)
        as_of_date = inferred_date

    vrow = conn.execute(
        """
        SELECT computed_version, COUNT(*) AS c
        FROM topic_positions
        WHERE topic_set_id = ?
          AND institution_id = ?
          AND as_of_date = ?
          AND computed_method = ?
        GROUP BY computed_version
        ORDER BY c DESC, computed_version DESC
        LIMIT 1
        """,
        (topic_set_id, resolved_institution_id, as_of_date, computed_method),
    ).fetchone()
    computed_version = str(vrow["computed_version"] or "") if vrow else ""
    if not computed_version:
        computed_version = "no_data"

    return Scope(
        topic_set_id=topic_set_id,
        institution_id=resolved_institution_id,
        as_of_date=as_of_date,
        computed_method=computed_method,
        computed_version=computed_version,
    )


def export_topics(
    conn: sqlite3.Connection,
    *,
    scope: Scope,
    concerns: list[ConcernDef],
    max_topics: int,
    max_items_per_concern: int,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT st.topic_id,
               st.stakes_rank,
               st.is_high_stakes,
               t.label
        FROM topic_set_topics st
        JOIN topics t ON t.topic_id = st.topic_id
        WHERE st.topic_set_id = ?
        ORDER BY st.is_high_stakes DESC,
                 COALESCE(st.stakes_rank, 999999) ASC,
                 st.topic_id ASC
        """,
        (int(scope.topic_set_id),),
    ).fetchall()

    topics_all: list[dict[str, Any]] = []
    for r in rows:
        topic_id = int(r["topic_id"])
        label = str(r["label"] or "")
        concern_ids = compute_topic_concern_ids(label, concerns)
        topics_all.append(
            {
                "topic_id": topic_id,
                "label": label,
                "stakes_rank": int(r["stakes_rank"]) if r["stakes_rank"] is not None else None,
                "is_high_stakes": bool(int(r["is_high_stakes"] or 0)),
                # Optional v2 extension: server-side topic tags for concerns navigation.
                "concern_ids": concern_ids,
                "source": {"topic_set_id": int(scope.topic_set_id)},
                "links": {
                    "explorer_temas": f"../explorer-temas/?topic_set_id={scope.topic_set_id}&topic_id={topic_id}",
                    "explorer_positions": (
                        "../explorer/?t=topic_positions&tf=topic_"
                        f"&wc=topic_set_id&wv={scope.topic_set_id}"
                        f"&wc=topic_id&wv={topic_id}"
                        f"&wc=as_of_date&wv={scope.as_of_date}"
                        f"&wc=computed_method&wv={scope.computed_method}"
                        f"&wc=computed_version&wv={scope.computed_version}"
                    ),
                    "explorer_evidence": (
                        "../explorer/?t=topic_evidence&tf=topic_"
                        f"&wc=topic_set_id&wv={scope.topic_set_id}"
                        f"&wc=topic_id&wv={topic_id}"
                        f"&wc=institution_id&wv={scope.institution_id}"
                    ),
                },
            }
        )

    # Forward-compatible bounded selection: limit per concern, then take the union.
    topics_selected = topics_all
    if int(max_items_per_concern) > 0 and concerns:
        selected_ids: set[int] = set()
        for c in concerns:
            if not c.id:
                continue
            picked = 0
            for t in topics_all:
                if picked >= int(max_items_per_concern):
                    break
                if c.id in (t.get("concern_ids") or []):
                    selected_ids.add(int(t["topic_id"]))
                    picked += 1
        if selected_ids:
            topics_selected = [t for t in topics_all if int(t["topic_id"]) in selected_ids]

    # Always enforce a global cap for static budgets.
    topics_selected = topics_selected[: int(max(1, max_topics))]
    return topics_selected


def export_parties(conn: sqlite3.Connection, *, scope: Scope, max_parties: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT p.party_id,
               p.name,
               p.acronym,
               COUNT(*) AS members_total
        FROM mandates m
        JOIN parties p ON p.party_id = m.party_id
        WHERE m.institution_id = ?
          AND m.is_active = 1
          AND m.party_id IS NOT NULL
        GROUP BY p.party_id, p.name, p.acronym
        ORDER BY LOWER(p.name) ASC, p.party_id ASC
        LIMIT ?
        """,
        (int(scope.institution_id), int(max(1, max_parties))),
    ).fetchall()

    parties: list[dict[str, Any]] = []
    for r in rows:
        pid = int(r["party_id"])
        parties.append(
            {
                "party_id": pid,
                "name": str(r["name"] or ""),
                "acronym": str(r["acronym"] or ""),
                "links": {
                    "explorer_politico_party": f"../explorer-politico/?party_id={pid}",
                },
                # Keep members_total available for downstream aggregation, but don't make it
                # a top-level field contract requirement.
                "_members_total": int(r["members_total"] or 0),
            }
        )

    # Deterministic ordering already ensured by SQL.
    return parties


def derive_party_stance(
    *,
    members_total: int,
    members_with_signal: int,
    support_members: int,
    oppose_members: int,
    mixed_members: int,
    unclear_members: int,
) -> str:
    if members_with_signal <= 0:
        return "no_signal"

    # Guardrail: don't claim support/oppose/mixed when coverage is too low.
    if members_total > 0:
        min_needed = max(1, min(3, members_total), int(math.ceil(members_total * 0.20)))
        if members_with_signal < min_needed:
            return "unclear"

    clear = int(support_members) + int(oppose_members)
    if clear <= 0:
        if int(mixed_members) > 0:
            return "mixed"
        return "unclear"

    conflict = int(support_members) > 0 and int(oppose_members) > 0
    if conflict:
        maj = max(int(support_members), int(oppose_members)) / float(clear)
        if maj < 0.75:
            return "mixed"

    return "support" if int(support_members) >= int(oppose_members) else "oppose"


def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def export_party_topic_positions(
    conn: sqlite3.Connection,
    *,
    scope: Scope,
    topics: list[dict[str, Any]],
    parties: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    topic_ids = [int(t["topic_id"]) for t in topics]
    party_ids = [int(p["party_id"]) for p in parties]

    members_total_by_party = {int(p["party_id"]): int(p.get("_members_total") or 0) for p in parties}

    # Aggregate per (topic_id, party_id) directly in SQL.
    q = """
    SELECT tp.topic_id,
           m.party_id,
           SUM(CASE WHEN tp.stance != 'no_signal' THEN 1 ELSE 0 END) AS members_with_signal,
           SUM(CASE WHEN tp.stance = 'support' THEN 1 ELSE 0 END) AS support_members,
           SUM(CASE WHEN tp.stance = 'oppose' THEN 1 ELSE 0 END) AS oppose_members,
           SUM(CASE WHEN tp.stance = 'mixed' THEN 1 ELSE 0 END) AS mixed_members,
           SUM(CASE WHEN tp.stance = 'unclear' THEN 1 ELSE 0 END) AS unclear_members,
           SUM(tp.evidence_count) AS evidence_count_total,
           MAX(tp.last_evidence_date) AS last_evidence_date,
           SUM(tp.score * tp.evidence_count) * 1.0 / NULLIF(SUM(tp.evidence_count), 0) AS score_weighted,
           SUM(tp.confidence * tp.evidence_count) * 1.0 / NULLIF(SUM(tp.evidence_count), 0) AS confidence_weighted
    FROM topic_positions tp
    JOIN mandates m
      ON m.person_id = tp.person_id
     AND m.institution_id = ?
     AND m.is_active = 1
     AND m.party_id IS NOT NULL
    WHERE tp.institution_id = ?
      AND tp.topic_set_id = ?
      AND tp.as_of_date = ?
      AND tp.computed_method = ?
      AND tp.computed_version = ?
    GROUP BY tp.topic_id, m.party_id
    """

    rows = conn.execute(
        q,
        (
            int(scope.institution_id),
            int(scope.institution_id),
            int(scope.topic_set_id),
            str(scope.as_of_date),
            str(scope.computed_method),
            str(scope.computed_version),
        ),
    ).fetchall()

    stats: dict[tuple[int, int], dict[str, Any]] = {}
    for r in rows:
        tid = int(r["topic_id"])
        pid = int(r["party_id"])
        stats[(tid, pid)] = {
            "members_with_signal": int(r["members_with_signal"] or 0),
            "support_members": int(r["support_members"] or 0),
            "oppose_members": int(r["oppose_members"] or 0),
            "mixed_members": int(r["mixed_members"] or 0),
            "unclear_members": int(r["unclear_members"] or 0),
            "evidence_count_total": int(r["evidence_count_total"] or 0),
            "last_evidence_date": str(r["last_evidence_date"] or "") or None,
            "score": float(r["score_weighted"] or 0.0),
            "confidence": float(r["confidence_weighted"] or 0.0),
        }

    out: list[dict[str, Any]] = []

    # Deterministic full grid (topic x party). Missing stats => no_signal.
    for tid in sorted(topic_ids):
        for pid in sorted(party_ids):
            members_total = int(members_total_by_party.get(pid, 0) or 0)
            st = stats.get((tid, pid)) or {}
            members_with_signal = int(st.get("members_with_signal") or 0)
            support_members = int(st.get("support_members") or 0)
            oppose_members = int(st.get("oppose_members") or 0)
            mixed_members = int(st.get("mixed_members") or 0)
            unclear_members = int(st.get("unclear_members") or 0)

            stance = derive_party_stance(
                members_total=members_total,
                members_with_signal=members_with_signal,
                support_members=support_members,
                oppose_members=oppose_members,
                mixed_members=mixed_members,
                unclear_members=unclear_members,
            )

            evidence_count_total = int(st.get("evidence_count_total") or 0)
            last_evidence_date = st.get("last_evidence_date")
            score = float(st.get("score") or 0.0)
            conf_w = float(st.get("confidence") or 0.0)

            # Confidence: weighted average scaled by coverage ratio.
            coverage_ratio = (members_with_signal / float(members_total)) if members_total > 0 else 0.0
            confidence = clamp01(conf_w * coverage_ratio)

            # If we downgraded to unclear/no_signal, keep score neutral.
            if stance in ("no_signal", "unclear"):
                score = 0.0

            out.append(
                {
                    "topic_id": tid,
                    "party_id": pid,
                    "stance": stance,
                    "score": round(float(score), 6),
                    "confidence": round(float(confidence), 6),
                    "coverage": {
                        "members_total": int(members_total),
                        "members_with_signal": int(members_with_signal),
                        "evidence_count_total": int(evidence_count_total),
                        "last_evidence_date": last_evidence_date,
                    },
                    "links": {
                        "explorer_temas": f"../explorer-temas/?topic_set_id={scope.topic_set_id}&topic_id={tid}",
                        "explorer_positions": (
                            "../explorer/?t=topic_positions&tf=topic_"
                            f"&wc=topic_set_id&wv={scope.topic_set_id}"
                            f"&wc=topic_id&wv={tid}"
                            f"&wc=as_of_date&wv={scope.as_of_date}"
                            f"&wc=computed_method&wv={scope.computed_method}"
                            f"&wc=computed_version&wv={scope.computed_version}"
                        ),
                    },
                }
            )

    return out


def _load_concern_ids(path: Path) -> list[str]:
    if not path.exists():
        return []
    obj = json.loads(path.read_text(encoding="utf-8"))
    concerns = obj.get("concerns") or []
    out: list[str] = []
    if not isinstance(concerns, list):
        return out
    for c in concerns:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id") or "").strip()
        if cid:
            out.append(cid)
    return out


def export_party_concern_programas(
    conn: sqlite3.Connection,
    *,
    parties: list[dict[str, Any]],
    concerns_config_path: Path,
    source_id: str = DEFAULT_PROGRAMAS_SOURCE_ID,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Export per-party stances from party programs (programas_partidos) keyed by concern_id.

    Output is a full grid of concerns x parties (missing combos => no_signal).
    This avoids coupling program lane to Congreso mandates or initiative topic_sets.
    """
    concern_ids = _load_concern_ids(concerns_config_path)
    party_ids = [int(p["party_id"]) for p in parties]
    if not concern_ids or not party_ids:
        return None, []

    # Find the latest programas topic_set that has evidence rows.
    row = conn.execute(
        """
        SELECT e.topic_set_id AS topic_set_id,
               ts.legislature AS election_cycle,
               MAX(COALESCE(e.evidence_date, '')) AS max_evidence_date
        FROM topic_evidence e
        JOIN topic_sets ts ON ts.topic_set_id = e.topic_set_id
        WHERE e.source_id = ?
          AND e.evidence_type = 'declared:programa'
          AND e.topic_set_id IS NOT NULL
        GROUP BY e.topic_set_id, ts.legislature
        ORDER BY e.topic_set_id DESC
        LIMIT 1
        """,
        (str(source_id),),
    ).fetchone()
    if not row:
        return None, []

    topic_set_id = int(row["topic_set_id"])
    election_cycle = str(row["election_cycle"] or "") or None
    programas_as_of_date = str(row["max_evidence_date"] or "") or None

    # Map concern_id -> topic_id inside that programas topic_set.
    topic_id_by_concern: dict[str, int] = {}
    trows = conn.execute(
        """
        SELECT t.topic_id, t.canonical_key
        FROM topic_set_topics st
        JOIN topics t ON t.topic_id = st.topic_id
        WHERE st.topic_set_id = ?
        ORDER BY COALESCE(st.stakes_rank, 999999) ASC, t.topic_id ASC
        """,
        (int(topic_set_id),),
    ).fetchall()
    for r in trows:
        key = str(r["canonical_key"] or "").strip()
        if not key.startswith("concern:v1:"):
            continue
        cid = key.split(":", 2)[-1].strip()
        if cid:
            topic_id_by_concern[cid] = int(r["topic_id"])

    # Map party_id -> proxy person_id via person_identifiers(namespace='party_id').
    party_person_id: dict[int, int] = {}
    prows = conn.execute(
        """
        SELECT person_id, value
        FROM person_identifiers
        WHERE namespace = 'party_id'
        """,
    ).fetchall()
    for r in prows:
        try:
            pid = int(str(r["value"] or "").strip())
        except ValueError:
            continue
        try:
            party_person_id[pid] = int(r["person_id"])
        except Exception:  # noqa: BLE001
            continue

    # Pick the strongest evidence per (topic_id, person_id) deterministically.
    stance_ph = ",".join("?" for _ in _PROGRAMAS_STANCE_METHODS)
    erows = conn.execute(
        f"""
        SELECT
          evidence_id,
          topic_id,
          person_id,
          stance,
          confidence,
          evidence_date,
          source_url,
          source_record_pk
        FROM topic_evidence
        WHERE source_id = ?
          AND topic_set_id = ?
          AND evidence_type = 'declared:programa'
          AND stance IN ('support', 'oppose', 'mixed')
          AND stance_method IN ({stance_ph})
        ORDER BY
          topic_id ASC,
          person_id ASC,
          COALESCE(confidence, 0) DESC,
          COALESCE(evidence_date, '') DESC,
          evidence_id ASC
        """,
        (str(source_id), int(topic_set_id), *_PROGRAMAS_STANCE_METHODS),
    ).fetchall()

    best_by_key: dict[tuple[int, int], dict[str, Any]] = {}
    for r in erows:
        try:
            k = (int(r["topic_id"]), int(r["person_id"]))
        except Exception:  # noqa: BLE001
            continue
        if k in best_by_key:
            continue  # ordered query => first is best
        best_by_key[k] = {
            "evidence_id": int(r["evidence_id"]),
            "stance": str(r["stance"] or ""),
            "confidence": float(r["confidence"] or 0.0),
            "evidence_date": str(r["evidence_date"] or "") or None,
            "source_url": str(r["source_url"] or "") or None,
            "source_record_pk": int(r["source_record_pk"]) if r["source_record_pk"] is not None else None,
        }

    # Build full grid for UI convenience.
    out: list[dict[str, Any]] = []
    for cid in concern_ids:
        topic_id = topic_id_by_concern.get(cid)
        for party_id in party_ids:
            person_id = party_person_id.get(int(party_id))
            best = best_by_key.get((int(topic_id), int(person_id))) if (topic_id and person_id) else None
            stance = str(best["stance"]) if best else "no_signal"
            conf = float(best["confidence"]) if best else 0.0
            link = ""
            if topic_id and person_id:
                link = (
                    "../explorer/?t=topic_evidence&tf=topic_"
                    f"&wc=source_id&wv={source_id}"
                    f"&wc=topic_set_id&wv={topic_set_id}"
                    f"&wc=topic_id&wv={topic_id}"
                    f"&wc=person_id&wv={person_id}"
                )
            out.append(
                {
                    "concern_id": str(cid),
                    "party_id": int(party_id),
                    "stance": stance,
                    "confidence": round(float(conf), 6),
                    "evidence": {
                        "evidence_id": int(best["evidence_id"]) if best else None,
                        "evidence_date": str(best["evidence_date"]) if best and best.get("evidence_date") else None,
                        "source_record_pk": int(best["source_record_pk"]) if best and best.get("source_record_pk") else None,
                        "source_url": str(best["source_url"]) if best and best.get("source_url") else None,
                    },
                    "links": {
                        "explorer_evidence": link,
                    },
                }
            )

    # Meta/KPIs for status chips (keep it compact).
    evidence_total = int(
        (
            conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM topic_evidence
                WHERE source_id = ?
                  AND topic_set_id = ?
                  AND evidence_type = 'declared:programa'
                """,
                (str(source_id), int(topic_set_id)),
            ).fetchone()
            or {"c": 0}
        )["c"]
    )
    signal_total = int(
        (
            conn.execute(
                f"""
                SELECT COUNT(*) AS c
                FROM topic_evidence
                WHERE source_id = ?
                  AND topic_set_id = ?
                  AND evidence_type = 'declared:programa'
                  AND stance IN ('support','oppose','mixed')
                  AND stance_method IN ({stance_ph})
                """,
                (str(source_id), int(topic_set_id), *_PROGRAMAS_STANCE_METHODS),
            ).fetchone()
            or {"c": 0}
        )["c"]
    )
    review_pending = int(
        (
            conn.execute(
                "SELECT COUNT(*) AS c FROM topic_evidence_reviews WHERE source_id = ? AND status = 'pending'",
                (str(source_id),),
            ).fetchone()
            or {"c": 0}
        )["c"]
    )

    meta = {
        "source_id": str(source_id),
        "topic_set_id": int(topic_set_id),
        "election_cycle": election_cycle,
        "as_of_date": programas_as_of_date,
        "evidence_total": evidence_total,
        "signal_total": signal_total,
        "review_pending": review_pending,
    }
    return meta, out


def strip_private_fields(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: strip_private_fields(v) for k, v in obj.items() if not str(k).startswith("_")}
    if isinstance(obj, list):
        return [strip_private_fields(x) for x in obj]
    return obj


def load_snapshot_json(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def snapshot_grid_stats(payload: dict[str, Any]) -> tuple[int, int]:
    topics = payload.get("topics")
    topic_count = len(topics) if isinstance(topics, list) else 0

    meta = payload.get("meta")
    quality = meta.get("quality") if isinstance(meta, dict) else None
    cells_total = 0
    if isinstance(quality, dict):
        try:
            cells_total = int(quality.get("cells_total") or 0)
        except (TypeError, ValueError):
            cells_total = 0
    if cells_total <= 0:
        rows = payload.get("party_topic_positions")
        cells_total = len(rows) if isinstance(rows, list) else 0
    return topic_count, int(cells_total)


def fallback_snapshot_matches_request(
    fallback_payload: dict[str, Any],
    *,
    requested_method: str,
    topic_set_id: int,
) -> bool:
    meta = fallback_payload.get("meta")
    if not isinstance(meta, dict):
        return False
    try:
        fallback_topic_set_id = int(meta.get("topic_set_id"))
    except (TypeError, ValueError):
        return False
    if fallback_topic_set_id != int(topic_set_id):
        return False

    fallback_method = str(meta.get("computed_method") or "").strip()
    if requested_method == "auto" and fallback_method not in {"combined", "votes"}:
        return False
    if requested_method != "auto" and fallback_method != requested_method:
        return False

    fallback_topics, fallback_cells = snapshot_grid_stats(fallback_payload)
    return fallback_topics > 0 and fallback_cells > 0


def should_reuse_fallback_snapshot(
    current_payload: dict[str, Any],
    fallback_payload: dict[str, Any],
) -> bool:
    current_topics, current_cells = snapshot_grid_stats(current_payload)
    fallback_topics, fallback_cells = snapshot_grid_stats(fallback_payload)
    if fallback_topics <= 0 or fallback_cells <= 0:
        return False
    if current_topics <= 0 or current_cells <= 0:
        return True

    topics_ratio = float(current_topics) / float(fallback_topics)
    cells_ratio = float(current_cells) / float(fallback_cells)
    return topics_ratio < float(SEVERE_REGRESSION_RATIO) and cells_ratio < float(SEVERE_REGRESSION_RATIO)


def _confidence_tier(*, stance: str, confidence: float) -> str:
    if str(stance or "") == "no_signal":
        return "none"
    conf = float(confidence or 0.0)
    if conf <= 0.0:
        return "none"
    if conf >= float(CONF_TIER_HIGH_MIN):
        return "high"
    if conf >= float(CONF_TIER_MEDIUM_MIN):
        return "medium"
    return "low"


def summarize_snapshot_quality(rows: list[dict[str, Any]]) -> dict[str, Any]:
    stance_counts = {
        "support": 0,
        "oppose": 0,
        "mixed": 0,
        "unclear": 0,
        "no_signal": 0,
    }
    confidence_tiers = {
        "high": 0,
        "medium": 0,
        "low": 0,
        "none": 0,
    }

    confidence_sum_signal = 0.0
    confidence_n_signal = 0

    for row in rows:
        stance = str((row or {}).get("stance") or "no_signal")
        if stance not in stance_counts:
            stance = "no_signal"
        stance_counts[stance] += 1

        confidence = float((row or {}).get("confidence") or 0.0)
        if stance != "no_signal":
            confidence_sum_signal += confidence
            confidence_n_signal += 1

        tier = _confidence_tier(stance=stance, confidence=confidence)
        if tier not in confidence_tiers:
            tier = "none"
        confidence_tiers[tier] += 1

    cells_total = int(len(rows))
    clear_total = int(stance_counts["support"] + stance_counts["oppose"] + stance_counts["mixed"])
    any_signal_total = int(cells_total - stance_counts["no_signal"])
    unknown_total = int(stance_counts["unclear"] + stance_counts["no_signal"])
    confidence_avg_signal = (confidence_sum_signal / float(confidence_n_signal)) if confidence_n_signal > 0 else 0.0

    return {
        "cells_total": int(cells_total),
        "stance_counts": stance_counts,
        "clear_total": int(clear_total),
        "clear_pct": round(clamp01(clear_total / float(cells_total)) if cells_total > 0 else 0.0, 6),
        "any_signal_total": int(any_signal_total),
        "any_signal_pct": round(clamp01(any_signal_total / float(cells_total)) if cells_total > 0 else 0.0, 6),
        "unknown_total": int(unknown_total),
        "unknown_pct": round(clamp01(unknown_total / float(cells_total)) if cells_total > 0 else 0.0, 6),
        "confidence_avg_signal": round(clamp01(float(confidence_avg_signal)), 6),
        "confidence_tiers": confidence_tiers,
        "confidence_thresholds": {
            "high_min": float(CONF_TIER_HIGH_MIN),
            "medium_min": float(CONF_TIER_MEDIUM_MIN),
        },
    }


def build_snapshot_freshness(*, generated_at: str, as_of_date: str) -> dict[str, Any]:
    generated_dt = parse_date_utc(generated_at)
    as_of_dt = parse_date_utc(as_of_date)
    if generated_dt is None or as_of_dt is None:
        return {
            "freshness_version": "citizen_snapshot_freshness_v1",
            "as_of_date": str(as_of_date or "") or None,
            "generated_at": str(generated_at or "") or None,
            "data_age_days": None,
            "freshness_tier": "unknown",
            "freshness_label": "desconocida",
            "should_warn": True,
            "timeline_delta_days": None,
            "date_consistency_ok": False,
            "warning_reason": "missing_dates",
        }

    signed_delta_days = int((generated_dt.date() - as_of_dt.date()).days)
    if signed_delta_days < 0:
        return {
            "freshness_version": "citizen_snapshot_freshness_v1",
            "as_of_date": str(as_of_date or "") or None,
            "generated_at": str(generated_at or "") or None,
            "data_age_days": int(signed_delta_days),
            "freshness_tier": "future",
            "freshness_label": "futura",
            "should_warn": True,
            "timeline_delta_days": int(signed_delta_days),
            "date_consistency_ok": False,
            "warning_reason": "future_as_of_date",
        }

    age_days = int(signed_delta_days)
    if age_days <= 7:
        tier = "fresh"
        label = "reciente"
    elif age_days <= 30:
        tier = "aging"
        label = "vigente"
    else:
        tier = "stale"
        label = "antigua"
    return {
        "freshness_version": "citizen_snapshot_freshness_v1",
        "as_of_date": str(as_of_date or "") or None,
        "generated_at": str(generated_at or "") or None,
        "data_age_days": int(age_days),
        "freshness_tier": tier,
        "freshness_label": label,
        "should_warn": tier != "fresh",
        "timeline_delta_days": int(signed_delta_days),
        "date_consistency_ok": True,
        "warning_reason": "none" if tier == "fresh" else f"{tier}_snapshot",
    }


def build_snapshot_honesty_contract() -> dict[str, Any]:
    return {
        "honesty_version": "citizen_honesty_contract_v1",
        "unknown_definition": "unknown = incierto + sin_senal",
        "match_definition": "match/mismatch solo cuentan cuando hay senal clara comparable",
        "no_imputation": True,
        "audit_rule": "si ves unknown alto o confianza baja, abre la evidencia enlazada",
        "audit_links": {
            "explorer_temas": "../explorer-temas/",
            "explorer_sql": "../explorer/",
        },
    }


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        print(f"ERROR: no existe el DB -> {db_path}")
        return 2

    conn = open_db(db_path)
    try:
        scope = resolve_scope(conn, args=args)

        concerns = load_concerns(DEFAULT_CONCERNS_CONFIG)
        topics = export_topics(
            conn,
            scope=scope,
            concerns=concerns,
            max_topics=int(args.max_topics),
            max_items_per_concern=int(args.max_items_per_concern),
        )
        parties = export_parties(conn, scope=scope, max_parties=int(args.max_parties))
        party_topic_positions = export_party_topic_positions(conn, scope=scope, topics=topics, parties=parties)
        programas_meta, party_concern_programas = export_party_concern_programas(
            conn,
            parties=parties,
            concerns_config_path=DEFAULT_CONCERNS_CONFIG,
            source_id=DEFAULT_PROGRAMAS_SOURCE_ID,
        )

        payload = {
            "meta": {
                "generated_at": now_utc_iso(),
                "topic_set_id": int(scope.topic_set_id),
                "as_of_date": str(scope.as_of_date),
                "computed_method": str(scope.computed_method),
                "computed_version": str(scope.computed_version),
                "limits": {
                    "max_topics": int(args.max_topics),
                    "max_parties": int(args.max_parties),
                    "max_items_per_concern": int(args.max_items_per_concern),
                },
                "guards": {
                    "max_bytes": int(args.max_bytes),
                },
                # Optional v3 extension: explicit quality semantics for citizen rendering.
                "quality": summarize_snapshot_quality(party_topic_positions),
            },
            "concerns": {
                "version": "v1",
                "path": "data/concerns_v1.json",
            },
            "topics": topics,
            "parties": parties,
            "party_topic_positions": party_topic_positions,
            # Optional v1 extension: party programs (promises) per citizen concern.
            "party_concern_programas": party_concern_programas,
        }
        available_methods = methods_available(
            conn,
            topic_set_id=int(scope.topic_set_id),
            institution_id=int(scope.institution_id),
            as_of_date=str(scope.as_of_date),
        )
        if available_methods and str(scope.computed_version) != "no_data":
            payload["meta"]["methods_available"] = available_methods
        if programas_meta:
            payload["meta"]["programas"] = programas_meta

        payload["meta"]["freshness"] = build_snapshot_freshness(
            generated_at=str(payload["meta"]["generated_at"]),
            as_of_date=str(payload["meta"]["as_of_date"]),
        )
        payload["meta"]["honesty"] = build_snapshot_honesty_contract()

        fallback_used = False
        fallback_path = Path(str(args.fallback_snapshot or "").strip()) if str(args.fallback_snapshot or "").strip() else None
        if fallback_path is not None:
            fallback_payload = load_snapshot_json(fallback_path)
            if fallback_payload and fallback_snapshot_matches_request(
                fallback_payload,
                requested_method=str(args.computed_method),
                topic_set_id=int(scope.topic_set_id),
            ) and should_reuse_fallback_snapshot(payload, fallback_payload):
                fallback_topics, fallback_cells = snapshot_grid_stats(fallback_payload)
                current_topics, current_cells = snapshot_grid_stats(payload)
                print(
                    "WARN: citizen snapshot severe regression detected; reusing fallback "
                    + f"(current_topics={current_topics} current_cells={current_cells} "
                    + f"fallback_topics={fallback_topics} fallback_cells={fallback_cells} "
                    + f"path={fallback_path})",
                    file=sys.stderr,
                )
                payload = fallback_payload
                fallback_used = True

        payload = strip_private_fields(payload)

        if bool(args.pretty):
            out_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        else:
            out_path.write_text(json.dumps(payload, ensure_ascii=True, separators=(",", ":")), encoding="utf-8")

        size = out_path.stat().st_size
        if int(args.max_bytes) > 0 and size > int(args.max_bytes):
            print(f"ERROR: citizen snapshot demasiado grande: bytes={size} max_bytes={int(args.max_bytes)} -> {out_path}")
            return 3

        meta = payload.get("meta") if isinstance(payload, dict) else {}
        topic_set_id = meta.get("topic_set_id") if isinstance(meta, dict) else scope.topic_set_id
        as_of_date = meta.get("as_of_date") if isinstance(meta, dict) else scope.as_of_date
        computed_method = meta.get("computed_method") if isinstance(meta, dict) else scope.computed_method
        computed_version = meta.get("computed_version") if isinstance(meta, dict) else scope.computed_version
        print(
            "OK citizen snapshot -> "
            + str(out_path)
            + f" (topic_set_id={topic_set_id} as_of_date={as_of_date} method={computed_method} version={computed_version} bytes={size})"
            + (f" reused_fallback={fallback_path}" if fallback_used and fallback_path is not None else "")
        )
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
