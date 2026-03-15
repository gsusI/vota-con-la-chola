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
LINEAGE_POSITION_SAMPLE_MAX = 3
LINEAGE_EVIDENCE_SAMPLE_MAX = 2
RANK_ROBUSTNESS_MIN_PAIR_COMPARABLE = 5
RANK_ROBUSTNESS_THIN_MARGIN_MAX = 0.08
RANK_ROBUSTNESS_COMPETITIVE_MARGIN_MAX = 0.2

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
        help="Ruta de salida JSON (p.ej. docs/gh-pages/citizen/data/citizen.json)",
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


def resolve_scope(conn: sqlite3.Connection, *, args: argparse.Namespace) -> Scope:
    topic_set_id = int(args.topic_set_id)
    institution_id = int(args.institution_id)

    method_pref = [str(args.computed_method)]
    if str(args.computed_method) == "auto":
        method_pref = ["combined", "votes"]

    as_of_date = str(args.as_of_date or "").strip()

    if as_of_date:
        # Choose method given fixed date.
        chosen_method = None
        for m in method_pref:
            if _count_positions(conn, topic_set_id=topic_set_id, institution_id=institution_id, as_of_date=as_of_date, computed_method=m) > 0:
                chosen_method = m
                break
        if chosen_method is None:
            raise SystemExit(
                f"No hay topic_positions para topic_set_id={topic_set_id} institution_id={institution_id} as_of_date={as_of_date} computed_method in {method_pref}"
            )
        computed_method = chosen_method
    else:
        # Infer latest (method-first).
        computed_method = None
        inferred_date = ""
        for m in method_pref:
            d = _max_as_of_date(conn, topic_set_id=topic_set_id, institution_id=institution_id, computed_method=m)
            if d:
                computed_method = m
                inferred_date = d
                break
        if not computed_method or not inferred_date:
            raise SystemExit(
                f"No se pudo inferir as_of_date: no hay topic_positions para topic_set_id={topic_set_id} institution_id={institution_id} computed_method in {method_pref}"
            )
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
        (topic_set_id, institution_id, as_of_date, computed_method),
    ).fetchone()
    computed_version = str(vrow["computed_version"] or "") if vrow else ""
    if not computed_version:
        raise SystemExit(
            f"No se pudo resolver computed_version para topic_set_id={topic_set_id} institution_id={institution_id} as_of_date={as_of_date} computed_method={computed_method}"
        )

    return Scope(
        topic_set_id=topic_set_id,
        institution_id=institution_id,
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


def position_grid_key(topic_id: int, party_id: int) -> tuple[int, int]:
    return (int(topic_id), int(party_id))


def _topic_links(*, scope: Scope, topic_id: int) -> dict[str, str]:
    return {
        "explorer_temas": f"../explorer-temas/?topic_set_id={scope.topic_set_id}&topic_id={int(topic_id)}",
        "explorer_positions": (
            "../explorer/?t=topic_positions&tf=topic_"
            f"&wc=topic_set_id&wv={scope.topic_set_id}"
            f"&wc=topic_id&wv={int(topic_id)}"
            f"&wc=as_of_date&wv={scope.as_of_date}"
            f"&wc=computed_method&wv={scope.computed_method}"
            f"&wc=computed_version&wv={scope.computed_version}"
        ),
        "explorer_evidence": (
            "../explorer/?t=topic_evidence&tf=topic_"
            f"&wc=topic_set_id&wv={scope.topic_set_id}"
            f"&wc=topic_id&wv={int(topic_id)}"
            f"&wc=institution_id&wv={scope.institution_id}"
        ),
    }


def _minimum_signal_members(members_total: int) -> int:
    total = max(0, int(members_total or 0))
    if total <= 0:
        return 1
    return max(1, min(3, total), int(math.ceil(total * 0.20)))


def _comparability_reason(
    *,
    stance: str,
    members_total: int,
    members_with_signal: int,
    support_members: int,
    oppose_members: int,
    mixed_members: int,
    unclear_members: int,
) -> tuple[str, str]:
    stance_token = str(stance or "no_signal")
    clear_members = int(support_members or 0) + int(oppose_members or 0)
    min_needed = _minimum_signal_members(int(members_total or 0))

    if stance_token == "support":
        return ("clear_support", "senal comparable a favor")
    if stance_token == "oppose":
        return ("clear_oppose", "senal comparable en contra")
    if int(members_with_signal or 0) <= 0:
        return ("no_signal", "sin senal observable")
    if int(members_with_signal or 0) < int(min_needed):
        return ("low_signal_coverage", "cobertura insuficiente para comparar")
    if int(mixed_members or 0) > 0 and clear_members <= 0:
        return ("mixed_only", "senal solo mixta")
    if int(support_members or 0) > 0 and int(oppose_members or 0) > 0:
        return ("split_signal", "senal dividida entre apoyo y rechazo")
    if int(unclear_members or 0) > 0 and clear_members <= 0:
        return ("unclear_signal", "senal incierta")
    if stance_token == "mixed":
        return ("mixed_signal", "senal mixta")
    return ("not_comparable", "no comparable con la senal actual")


def _companion_out_path(out_path: Path, kind: str) -> Path:
    stem = str(out_path.stem)
    if stem.startswith("citizen"):
        suffix = stem[len("citizen") :]
        return out_path.with_name(f"citizen_{kind}{suffix}.json")
    return out_path.with_name(f"{stem}_{kind}.json")


def _resolve_scope_for_explicit_date(
    conn: sqlite3.Connection,
    *,
    topic_set_id: int,
    institution_id: int,
    as_of_date: str,
    computed_method: str,
) -> Scope | None:
    if _count_positions(
        conn,
        topic_set_id=int(topic_set_id),
        institution_id=int(institution_id),
        as_of_date=str(as_of_date),
        computed_method=str(computed_method),
    ) <= 0:
        return None

    row = conn.execute(
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
        (int(topic_set_id), int(institution_id), str(as_of_date), str(computed_method)),
    ).fetchone()
    if not row:
        return None
    computed_version = str(row["computed_version"] or "").strip()
    if not computed_version:
        return None

    return Scope(
        topic_set_id=int(topic_set_id),
        institution_id=int(institution_id),
        as_of_date=str(as_of_date),
        computed_method=str(computed_method),
        computed_version=computed_version,
    )


def _previous_as_of_date(
    conn: sqlite3.Connection,
    *,
    topic_set_id: int,
    institution_id: int,
    computed_method: str,
    as_of_date: str,
) -> str:
    row = conn.execute(
        """
        SELECT MAX(as_of_date) AS d
        FROM topic_positions
        WHERE topic_set_id = ?
          AND institution_id = ?
          AND computed_method = ?
          AND as_of_date < ?
        """,
        (int(topic_set_id), int(institution_id), str(computed_method), str(as_of_date)),
    ).fetchone()
    if not row:
        return ""
    return str(row["d"] or "")


def collect_party_topic_stats(
    conn: sqlite3.Connection,
    *,
    scope: Scope,
    topics: list[dict[str, Any]],
    parties: list[dict[str, Any]],
) -> dict[tuple[int, int], dict[str, Any]]:
    topic_ids = [int(t["topic_id"]) for t in topics]
    if not topic_ids or not parties:
        return {}

    topic_placeholders = ",".join("?" for _ in topic_ids)

    # Aggregate per (topic_id, party_id) directly in SQL.
    q = f"""
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
      AND tp.topic_id IN ({topic_placeholders})
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
            *topic_ids,
        ),
    ).fetchall()

    stats: dict[tuple[int, int], dict[str, Any]] = {}
    for r in rows:
        tid = int(r["topic_id"])
        pid = int(r["party_id"])
        stats[position_grid_key(tid, pid)] = {
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
    return stats


def export_party_topic_positions(
    conn: sqlite3.Connection,
    *,
    scope: Scope,
    topics: list[dict[str, Any]],
    parties: list[dict[str, Any]],
    stats: dict[tuple[int, int], dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    topic_ids = [int(t["topic_id"]) for t in topics]
    party_ids = [int(p["party_id"]) for p in parties]

    members_total_by_party = {int(p["party_id"]): int(p.get("_members_total") or 0) for p in parties}
    resolved_stats = stats if stats is not None else collect_party_topic_stats(conn, scope=scope, topics=topics, parties=parties)

    out: list[dict[str, Any]] = []

    # Deterministic full grid (topic x party). Missing stats => no_signal.
    for tid in sorted(topic_ids):
        for pid in sorted(party_ids):
            members_total = int(members_total_by_party.get(pid, 0) or 0)
            st = resolved_stats.get(position_grid_key(tid, pid)) or {}
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
                    "links": _topic_links(scope=scope, topic_id=tid),
                }
            )

    return out


def export_party_topic_comparability(
    *,
    scope: Scope,
    topics: list[dict[str, Any]],
    parties: list[dict[str, Any]],
    positions: list[dict[str, Any]],
    stats: dict[tuple[int, int], dict[str, Any]],
) -> dict[str, Any]:
    members_total_by_party = {int(p["party_id"]): int(p.get("_members_total") or 0) for p in parties}
    rows: list[dict[str, Any]] = []
    comparable_ok_total = 0

    for row in positions:
        tid = int(row["topic_id"])
        pid = int(row["party_id"])
        members_total = int(members_total_by_party.get(pid, 0) or 0)
        st = stats.get(position_grid_key(tid, pid)) or {}
        members_with_signal = int(st.get("members_with_signal") or 0)
        support_members = int(st.get("support_members") or 0)
        oppose_members = int(st.get("oppose_members") or 0)
        mixed_members = int(st.get("mixed_members") or 0)
        unclear_members = int(st.get("unclear_members") or 0)
        no_signal_members = max(0, members_total - members_with_signal)
        comparable_members = int(support_members) + int(oppose_members)
        comparable_ratio = (comparable_members / float(members_total)) if members_total > 0 else 0.0
        coverage_ratio = (members_with_signal / float(members_total)) if members_total > 0 else 0.0
        stance = str(row.get("stance") or "no_signal")
        comparable_ok = stance in ("support", "oppose")
        if comparable_ok:
            comparable_ok_total += 1
        reason_code, reason_label = _comparability_reason(
            stance=stance,
            members_total=members_total,
            members_with_signal=members_with_signal,
            support_members=support_members,
            oppose_members=oppose_members,
            mixed_members=mixed_members,
            unclear_members=unclear_members,
        )
        rows.append(
            {
                "topic_id": tid,
                "party_id": pid,
                "stance": stance,
                "members_total": int(members_total),
                "members_with_signal": int(members_with_signal),
                "support_members": int(support_members),
                "oppose_members": int(oppose_members),
                "mixed_members": int(mixed_members),
                "unclear_members": int(unclear_members),
                "no_signal_members": int(no_signal_members),
                "unknown_total": int(unclear_members + no_signal_members),
                "comparable_members": int(comparable_members),
                "minimum_signal_members": int(_minimum_signal_members(members_total)),
                "coverage_ratio": round(clamp01(coverage_ratio), 6),
                "comparable_ratio": round(clamp01(comparable_ratio), 6),
                "comparable_ok": bool(comparable_ok),
                "reason_code": str(reason_code),
                "reason_label": str(reason_label),
                "evidence_count_total": int((row.get("coverage") or {}).get("evidence_count_total") or 0),
                "last_evidence_date": (row.get("coverage") or {}).get("last_evidence_date"),
                "links": dict(row.get("links") or {}),
            }
        )

    return {
        "meta": {
            "artifact_version": "citizen_comparability_v1",
            "topic_set_id": int(scope.topic_set_id),
            "institution_id": int(scope.institution_id),
            "as_of_date": str(scope.as_of_date),
            "computed_method": str(scope.computed_method),
            "computed_version": str(scope.computed_version),
            "rows_total": int(len(rows)),
            "comparable_ok_total": int(comparable_ok_total),
        },
        "rows": rows,
    }


def _lineage_evidence_where(scope: Scope) -> tuple[str, tuple[Any, ...], str]:
    method = str(scope.computed_method or "")
    if method == "votes":
        return ("AND e.evidence_type = ?", ("revealed:vote",), "revealed_only")
    if method == "declared":
        return ("AND e.evidence_type LIKE ?", ("declared:%",), "declared_only")
    return ("AND (e.evidence_type = ? OR e.evidence_type LIKE ?)", ("revealed:vote", "declared:%"), "mixed")


def export_party_topic_lineage(
    conn: sqlite3.Connection,
    *,
    scope: Scope,
    topics: list[dict[str, Any]],
    parties: list[dict[str, Any]],
    positions: list[dict[str, Any]],
    stats: dict[tuple[int, int], dict[str, Any]],
) -> dict[str, Any]:
    topic_ids = [int(t["topic_id"]) for t in topics]
    if not topic_ids or not parties:
        return {
            "meta": {
                "artifact_version": "citizen_lineage_v1",
                "topic_set_id": int(scope.topic_set_id),
                "institution_id": int(scope.institution_id),
                "as_of_date": str(scope.as_of_date),
                "computed_method": str(scope.computed_method),
                "computed_version": str(scope.computed_version),
                "rows_total": 0,
            },
            "rows": [],
        }

    topic_placeholders = ",".join("?" for _ in topic_ids)
    pos_rows = conn.execute(
        f"""
        SELECT tp.topic_id,
               m.party_id,
               tp.position_id,
               tp.person_id,
               tp.mandate_id,
               tp.stance,
               tp.confidence,
               tp.evidence_count,
               tp.last_evidence_date
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
          AND tp.topic_id IN ({topic_placeholders})
        ORDER BY tp.topic_id ASC,
                 m.party_id ASC,
                 tp.evidence_count DESC,
                 tp.confidence DESC,
                 tp.person_id ASC
        """,
        (
            int(scope.institution_id),
            int(scope.institution_id),
            int(scope.topic_set_id),
            str(scope.as_of_date),
            str(scope.computed_method),
            str(scope.computed_version),
            *topic_ids,
        ),
    ).fetchall()

    position_lineage: dict[tuple[int, int], dict[str, Any]] = {}
    for r in pos_rows:
        key = position_grid_key(int(r["topic_id"]), int(r["party_id"]))
        slot = position_lineage.setdefault(
            key,
            {
                "total_positions": 0,
                "stance_counts": {"support": 0, "oppose": 0, "mixed": 0, "unclear": 0, "no_signal": 0},
                "samples": [],
            },
        )
        slot["total_positions"] += 1
        stance = str(r["stance"] or "no_signal")
        if stance in slot["stance_counts"]:
            slot["stance_counts"][stance] += 1
        if len(slot["samples"]) < int(LINEAGE_POSITION_SAMPLE_MAX):
            slot["samples"].append(
                {
                    "position_id": int(r["position_id"]),
                    "person_id": int(r["person_id"]),
                    "mandate_id": int(r["mandate_id"]) if r["mandate_id"] is not None else None,
                    "stance": stance,
                    "confidence": round(float(r["confidence"] or 0.0), 6),
                    "evidence_count": int(r["evidence_count"] or 0),
                    "last_evidence_date": str(r["last_evidence_date"] or "") or None,
                }
            )

    evidence_where, evidence_params, lineage_mode = _lineage_evidence_where(scope)
    ev_rows = conn.execute(
        f"""
        SELECT *
        FROM (
          SELECT e.topic_id,
                 m.party_id,
                 e.evidence_id,
                 e.evidence_type,
                 e.evidence_date,
                 e.source_id,
                 e.source_url,
                 e.confidence,
                 e.stance,
                 COUNT(*) OVER (PARTITION BY e.topic_id, m.party_id) AS evidence_rows_total,
                 ROW_NUMBER() OVER (
                   PARTITION BY e.topic_id, m.party_id
                   ORDER BY
                     CASE WHEN e.evidence_type = 'revealed:vote' THEN 0 ELSE 1 END,
                     COALESCE(e.evidence_date, '') DESC,
                     COALESCE(e.confidence, 0) DESC,
                     e.evidence_id ASC
                 ) AS rn
          FROM topic_evidence e
          JOIN mandates m
            ON m.person_id = e.person_id
           AND m.institution_id = ?
           AND m.is_active = 1
           AND m.party_id IS NOT NULL
          WHERE e.institution_id = ?
            AND e.topic_set_id = ?
            AND e.topic_id IN ({topic_placeholders})
            {evidence_where}
        )
        WHERE rn <= ?
        ORDER BY topic_id ASC, party_id ASC, rn ASC
        """,
        (
            int(scope.institution_id),
            int(scope.institution_id),
            int(scope.topic_set_id),
            *topic_ids,
            *evidence_params,
            int(LINEAGE_EVIDENCE_SAMPLE_MAX),
        ),
    ).fetchall()

    evidence_lineage: dict[tuple[int, int], dict[str, Any]] = {}
    for r in ev_rows:
        key = position_grid_key(int(r["topic_id"]), int(r["party_id"]))
        slot = evidence_lineage.setdefault(
            key,
            {
                "evidence_rows_total": int(r["evidence_rows_total"] or 0),
                "source_ids": [],
                "sample_evidence": [],
            },
        )
        source_id = str(r["source_id"] or "").strip()
        if source_id and source_id not in slot["source_ids"]:
            slot["source_ids"].append(source_id)
        if len(slot["sample_evidence"]) < int(LINEAGE_EVIDENCE_SAMPLE_MAX):
            slot["sample_evidence"].append(
                {
                    "evidence_id": int(r["evidence_id"]),
                    "evidence_type": str(r["evidence_type"] or ""),
                    "stance": str(r["stance"] or "") or None,
                    "confidence": round(float(r["confidence"] or 0.0), 6),
                    "evidence_date": str(r["evidence_date"] or "") or None,
                    "source_id": source_id or None,
                    "source_url": str(r["source_url"] or "") or None,
                }
            )

    rows: list[dict[str, Any]] = []
    for row in positions:
        tid = int(row["topic_id"])
        pid = int(row["party_id"])
        key = position_grid_key(tid, pid)
        pos_lineage = position_lineage.get(key) or {
            "total_positions": 0,
            "stance_counts": {"support": 0, "oppose": 0, "mixed": 0, "unclear": 0, "no_signal": 0},
            "samples": [],
        }
        ev_lineage = evidence_lineage.get(key) or {"evidence_rows_total": 0, "source_ids": [], "sample_evidence": []}
        rows.append(
            {
                "topic_id": tid,
                "party_id": pid,
                "aggregate": {
                    "stance": str(row.get("stance") or "no_signal"),
                    "score": round(float(row.get("score") or 0.0), 6),
                    "confidence": round(float(row.get("confidence") or 0.0), 6),
                    "computed_method": str(scope.computed_method),
                    "computed_version": str(scope.computed_version),
                    "as_of_date": str(scope.as_of_date),
                },
                "coverage": dict(row.get("coverage") or {}),
                "positions": {
                    "total_positions": int(pos_lineage["total_positions"]),
                    "stance_counts": dict(pos_lineage["stance_counts"]),
                    "sample_positions": list(pos_lineage["samples"]),
                },
                "evidence": {
                    "lineage_mode": str(lineage_mode),
                    "evidence_rows_total": int(ev_lineage["evidence_rows_total"]),
                    "source_ids": list(ev_lineage["source_ids"]),
                    "sample_evidence": list(ev_lineage["sample_evidence"]),
                },
                "links": dict(row.get("links") or {}),
            }
        )

    return {
        "meta": {
            "artifact_version": "citizen_lineage_v1",
            "topic_set_id": int(scope.topic_set_id),
            "institution_id": int(scope.institution_id),
            "as_of_date": str(scope.as_of_date),
            "computed_method": str(scope.computed_method),
            "computed_version": str(scope.computed_version),
            "lineage_mode": str(lineage_mode),
            "rows_total": int(len(rows)),
        },
        "rows": rows,
    }


def export_party_topic_snapshot_diff(
    conn: sqlite3.Connection,
    *,
    scope: Scope,
    topics: list[dict[str, Any]],
    parties: list[dict[str, Any]],
    positions: list[dict[str, Any]],
    stats: dict[tuple[int, int], dict[str, Any]],
) -> dict[str, Any]:
    previous_date = _previous_as_of_date(
        conn,
        topic_set_id=int(scope.topic_set_id),
        institution_id=int(scope.institution_id),
        computed_method=str(scope.computed_method),
        as_of_date=str(scope.as_of_date),
    )
    if not previous_date:
        return {
            "meta": {
                "artifact_version": "citizen_snapshot_diff_v1",
                "topic_set_id": int(scope.topic_set_id),
                "institution_id": int(scope.institution_id),
                "computed_method": str(scope.computed_method),
                "current_as_of_date": str(scope.as_of_date),
                "previous_as_of_date": None,
                "rows_total": 0,
                "changed_rows_total": 0,
            },
            "party_summary": [],
            "rows": [],
        }

    previous_scope = _resolve_scope_for_explicit_date(
        conn,
        topic_set_id=int(scope.topic_set_id),
        institution_id=int(scope.institution_id),
        as_of_date=str(previous_date),
        computed_method=str(scope.computed_method),
    )
    if previous_scope is None:
        return {
            "meta": {
                "artifact_version": "citizen_snapshot_diff_v1",
                "topic_set_id": int(scope.topic_set_id),
                "institution_id": int(scope.institution_id),
                "computed_method": str(scope.computed_method),
                "current_as_of_date": str(scope.as_of_date),
                "previous_as_of_date": None,
                "rows_total": 0,
                "changed_rows_total": 0,
            },
            "party_summary": [],
            "rows": [],
        }

    previous_stats = collect_party_topic_stats(conn, scope=previous_scope, topics=topics, parties=parties)
    previous_positions = export_party_topic_positions(
        conn,
        scope=previous_scope,
        topics=topics,
        parties=parties,
        stats=previous_stats,
    )
    previous_by_key = {position_grid_key(int(r["topic_id"]), int(r["party_id"])): r for r in previous_positions}

    rows: list[dict[str, Any]] = []
    party_summary_map: dict[int, dict[str, Any]] = {}
    for row in positions:
        tid = int(row["topic_id"])
        pid = int(row["party_id"])
        previous = previous_by_key.get(position_grid_key(tid, pid)) or {}
        previous_stance = str(previous.get("stance") or "no_signal")
        current_stance = str(row.get("stance") or "no_signal")
        previous_confidence = round(float(previous.get("confidence") or 0.0), 6)
        current_confidence = round(float(row.get("confidence") or 0.0), 6)
        previous_cov = previous.get("coverage") or {}
        current_cov = row.get("coverage") or {}
        previous_evidence_count = int(previous_cov.get("evidence_count_total") or 0)
        current_evidence_count = int(current_cov.get("evidence_count_total") or 0)
        previous_signal = int(previous_cov.get("members_with_signal") or 0)
        current_signal = int(current_cov.get("members_with_signal") or 0)
        previous_comparable_ok = previous_stance in ("support", "oppose")
        current_comparable_ok = current_stance in ("support", "oppose")

        stance_changed = current_stance != previous_stance
        comparable_changed = bool(current_comparable_ok) != bool(previous_comparable_ok)
        confidence_delta = round(float(current_confidence - previous_confidence), 6)
        evidence_count_delta = int(current_evidence_count - previous_evidence_count)
        signal_delta = int(current_signal - previous_signal)
        changed = bool(
            stance_changed
            or comparable_changed
            or abs(confidence_delta) > 0.000001
            or evidence_count_delta != 0
            or signal_delta != 0
        )
        if not changed:
            continue

        if stance_changed:
            primary_change = "stance_changed"
        elif comparable_changed:
            primary_change = "comparability_changed"
        elif evidence_count_delta != 0:
            primary_change = "evidence_changed"
        elif signal_delta != 0:
            primary_change = "signal_changed"
        else:
            primary_change = "confidence_changed"

        entry = {
            "topic_id": tid,
            "party_id": pid,
            "primary_change": str(primary_change),
            "stance_changed": bool(stance_changed),
            "comparability_changed": bool(comparable_changed),
            "current_stance": current_stance,
            "previous_stance": previous_stance,
            "current_comparable_ok": bool(current_comparable_ok),
            "previous_comparable_ok": bool(previous_comparable_ok),
            "current_confidence": float(current_confidence),
            "previous_confidence": float(previous_confidence),
            "confidence_delta": float(confidence_delta),
            "current_evidence_count_total": int(current_evidence_count),
            "previous_evidence_count_total": int(previous_evidence_count),
            "evidence_count_delta": int(evidence_count_delta),
            "current_members_with_signal": int(current_signal),
            "previous_members_with_signal": int(previous_signal),
            "signal_delta": int(signal_delta),
            "links": dict(row.get("links") or {}),
        }
        rows.append(entry)

        party_slot = party_summary_map.setdefault(
            pid,
            {
                "party_id": int(pid),
                "changed_topics_total": 0,
                "stance_changed_total": 0,
                "comparability_changed_total": 0,
                "evidence_delta_total": 0,
                "signal_delta_total": 0,
                "top_changes": [],
            },
        )
        party_slot["changed_topics_total"] += 1
        if stance_changed:
            party_slot["stance_changed_total"] += 1
        if comparable_changed:
            party_slot["comparability_changed_total"] += 1
        party_slot["evidence_delta_total"] += evidence_count_delta
        party_slot["signal_delta_total"] += signal_delta
        if len(party_slot["top_changes"]) < 3:
            party_slot["top_changes"].append(
                {
                    "topic_id": int(tid),
                    "primary_change": str(primary_change),
                    "current_stance": current_stance,
                    "previous_stance": previous_stance,
                }
            )

    party_summary = sorted(party_summary_map.values(), key=lambda x: (-(int(x["changed_topics_total"])), int(x["party_id"])))
    rows.sort(key=lambda x: (int(x["party_id"]), int(x["topic_id"])))
    return {
        "meta": {
            "artifact_version": "citizen_snapshot_diff_v1",
            "topic_set_id": int(scope.topic_set_id),
            "institution_id": int(scope.institution_id),
            "computed_method": str(scope.computed_method),
            "current_as_of_date": str(scope.as_of_date),
            "previous_as_of_date": str(previous_scope.as_of_date),
            "previous_computed_version": str(previous_scope.computed_version),
            "rows_total": int(len(positions)),
            "changed_rows_total": int(len(rows)),
        },
        "party_summary": party_summary,
        "rows": rows,
    }


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


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / float(len(values))


def _is_clear_stance(value: str) -> bool:
    return str(value or "") in ("support", "oppose")


def _ranking_band(
    *,
    comparable_topics_total: int,
    closest_gap: float | None,
    driver_topics_needed: int | None,
) -> tuple[str, str, str, str]:
    comparable_total = int(max(0, comparable_topics_total))
    if closest_gap is None:
        return (
            "unknown",
            "sin base",
            "missing_neighbor",
            "No hay vecino comparable suficiente para auditar la fragilidad del puesto.",
        )
    if comparable_total < int(RANK_ROBUSTNESS_MIN_PAIR_COMPARABLE):
        return (
            "fragile",
            "fragil",
            "low_pair_comparable_topics",
            f"Solo hay {comparable_total} temas comparables con el vecino critico.",
        )
    if float(closest_gap) <= float(RANK_ROBUSTNESS_THIN_MARGIN_MAX):
        return (
            "fragile",
            "fragil",
            "thin_margin",
            "La distancia media con el vecino critico es muy estrecha.",
        )
    if (
        driver_topics_needed is not None
        and int(driver_topics_needed) <= 2
        and float(closest_gap) <= float(RANK_ROBUSTNESS_COMPETITIVE_MARGIN_MAX)
    ):
        return (
            "competitive",
            "competido",
            "gap_concentrated_in_few_topics",
            "Pocos temas concretos concentran la ventaja actual.",
        )
    return (
        "stable",
        "estable",
        "distributed_margin",
        "La ventaja se reparte en varios temas comparables.",
    )


def export_party_ranking_robustness(
    *,
    scope: Scope,
    topics: list[dict[str, Any]],
    parties: list[dict[str, Any]],
    positions: list[dict[str, Any]],
) -> dict[str, Any]:
    party_by_id = {int(p["party_id"]): p for p in parties}
    positions_by_key = {position_grid_key(int(r["topic_id"]), int(r["party_id"])): r for r in positions}

    metrics_by_party: dict[int, dict[str, Any]] = {}
    for party in parties:
        pid = int(party["party_id"])
        party_rows = [r for r in positions if int(r["party_id"]) == pid]
        clear_rows = [r for r in party_rows if _is_clear_stance(str(r.get("stance") or ""))]
        clear_scores = [float(r.get("score") or 0.0) for r in clear_rows]
        high_conf_scores = [float(r.get("score") or 0.0) for r in clear_rows if float(r.get("confidence") or 0.0) >= float(CONF_TIER_HIGH_MIN)]
        mean_score = _avg(clear_scores)
        high_conf_mean = _avg(high_conf_scores)
        high_conf_drift = None
        if mean_score is not None and high_conf_mean is not None:
            high_conf_drift = abs(float(high_conf_mean) - float(mean_score))
        metrics_by_party[pid] = {
            "mean_score_clear": round(float(mean_score), 6) if mean_score is not None else None,
            "comparable_topics_total": int(len(clear_rows)),
            "high_conf_topics_total": int(len(high_conf_scores)),
            "high_conf_share": round((len(high_conf_scores) / float(len(clear_rows))) if clear_rows else 0.0, 6),
            "high_conf_mean_score": round(float(high_conf_mean), 6) if high_conf_mean is not None else None,
            "high_conf_drift": round(float(high_conf_drift), 6) if high_conf_drift is not None else None,
        }

    ranked_party_ids = [int(p["party_id"]) for p in parties]
    ranked_party_ids.sort(
        key=lambda pid: (
            metrics_by_party[pid]["mean_score_clear"] is None,
            -(metrics_by_party[pid]["mean_score_clear"] if metrics_by_party[pid]["mean_score_clear"] is not None else -9999.0),
            -int(metrics_by_party[pid]["comparable_topics_total"]),
            str((party_by_id.get(pid) or {}).get("name") or ""),
            int(pid),
        )
    )

    def _neighbor_gap(base_pid: int, other_pid: int) -> float | None:
        base_mean = metrics_by_party.get(int(base_pid), {}).get("mean_score_clear")
        other_mean = metrics_by_party.get(int(other_pid), {}).get("mean_score_clear")
        if base_mean is None or other_mean is None:
            return None
        return abs(float(base_mean) - float(other_mean))

    rows: list[dict[str, Any]] = []
    for index, pid in enumerate(ranked_party_ids):
        metric = metrics_by_party.get(pid) or {}
        prev_pid = ranked_party_ids[index - 1] if index > 0 else None
        next_pid = ranked_party_ids[index + 1] if index + 1 < len(ranked_party_ids) else None
        gap_to_prev = _neighbor_gap(pid, prev_pid) if prev_pid is not None else None
        gap_to_next = _neighbor_gap(pid, next_pid) if next_pid is not None else None

        closest_neighbor_pid = None
        closest_gap = None
        relation = "none"
        if gap_to_prev is not None and gap_to_next is not None:
            if float(gap_to_next) <= float(gap_to_prev):
                closest_neighbor_pid = int(next_pid)
                closest_gap = float(gap_to_next)
                relation = "holding_above"
            else:
                closest_neighbor_pid = int(prev_pid)
                closest_gap = float(gap_to_prev)
                relation = "chasing"
        elif gap_to_next is not None:
            closest_neighbor_pid = int(next_pid)
            closest_gap = float(gap_to_next)
            relation = "holding_above"
        elif gap_to_prev is not None:
            closest_neighbor_pid = int(prev_pid)
            closest_gap = float(gap_to_prev)
            relation = "chasing"

        focus_pair: dict[str, Any] = {
            "against_party_id": int(closest_neighbor_pid) if closest_neighbor_pid is not None else None,
            "against_party_name": (
                str((party_by_id.get(int(closest_neighbor_pid)) or {}).get("name") or "") or None
                if closest_neighbor_pid is not None
                else None
            ),
            "relation": str(relation),
            "comparable_topics_total": 0,
            "mean_gap": round(float(closest_gap), 6) if closest_gap is not None else None,
            "driver_topics_needed": None,
            "driver_topics": [],
            "reason_label": "Sin vecino comparable suficiente." if closest_neighbor_pid is None else "",
        }

        if closest_neighbor_pid is not None:
            leader_pid = int(pid) if relation == "holding_above" else int(closest_neighbor_pid)
            runner_pid = int(closest_neighbor_pid) if relation == "holding_above" else int(pid)
            pair_diffs: list[dict[str, Any]] = []
            for topic in topics:
                tid = int(topic["topic_id"])
                leader_row = positions_by_key.get(position_grid_key(tid, leader_pid))
                runner_row = positions_by_key.get(position_grid_key(tid, runner_pid))
                if not leader_row or not runner_row:
                    continue
                leader_stance = str(leader_row.get("stance") or "no_signal")
                runner_stance = str(runner_row.get("stance") or "no_signal")
                if not _is_clear_stance(leader_stance) or not _is_clear_stance(runner_stance):
                    continue
                score_gap = float(leader_row.get("score") or 0.0) - float(runner_row.get("score") or 0.0)
                pair_diffs.append(
                    {
                        "topic_id": int(tid),
                        "topic_label": str(topic.get("label") or ""),
                        "stakes_rank": int(topic.get("stakes_rank")) if topic.get("stakes_rank") is not None else None,
                        "is_high_stakes": bool(topic.get("is_high_stakes")),
                        "score_gap": float(score_gap),
                        "leader_stance": leader_stance,
                        "runner_stance": runner_stance,
                        "links": dict((topic.get("links") or {})),
                    }
                )

            positive_drivers = [d for d in pair_diffs if float(d["score_gap"]) > 0]
            positive_drivers.sort(
                key=lambda item: (
                    -float(item["score_gap"]),
                    -(1 if bool(item["is_high_stakes"]) else 0),
                    int(item["stakes_rank"]) if item["stakes_rank"] is not None else 999999,
                    int(item["topic_id"]),
                )
            )
            pair_comparable_topics_total = int(len(pair_diffs))
            required_gap_sum = float(closest_gap or 0.0) * float(pair_comparable_topics_total)
            driver_topics_needed = None
            if pair_comparable_topics_total > 0 and required_gap_sum > 0 and positive_drivers:
                acc = 0.0
                for pos, item in enumerate(positive_drivers, start=1):
                    acc += float(item["score_gap"])
                    if acc + 1e-9 >= required_gap_sum:
                        driver_topics_needed = int(pos)
                        break
                if driver_topics_needed is None:
                    driver_topics_needed = int(len(positive_drivers))

            focus_pair = {
                "against_party_id": int(closest_neighbor_pid),
                "against_party_name": str((party_by_id.get(int(closest_neighbor_pid)) or {}).get("name") or "") or None,
                "relation": str(relation),
                "comparable_topics_total": int(pair_comparable_topics_total),
                "mean_gap": round(float(closest_gap), 6) if closest_gap is not None else None,
                "driver_topics_needed": int(driver_topics_needed) if driver_topics_needed is not None else None,
                "driver_topics": [
                    {
                        "topic_id": int(item["topic_id"]),
                        "topic_label": str(item["topic_label"]),
                        "score_gap": round(float(item["score_gap"]), 6),
                        "leader_stance": str(item["leader_stance"]),
                        "runner_stance": str(item["runner_stance"]),
                        "is_high_stakes": bool(item["is_high_stakes"]),
                        "links": dict(item["links"]),
                    }
                    for item in positive_drivers[:3]
                ],
                "reason_label": (
                    "Sin temas comparables claros entre ambos partidos."
                    if pair_comparable_topics_total <= 0
                    else (
                        f"{driver_topics_needed} tema(s) explican la ventaja media actual."
                        if driver_topics_needed is not None
                        else "No hay drivers positivos suficientes para explicar la ventaja."
                    )
                ),
            }

        band_id, band_label, reason_code, reason_label = _ranking_band(
            comparable_topics_total=int(focus_pair.get("comparable_topics_total") or 0),
            closest_gap=(float(closest_gap) if closest_gap is not None else None),
            driver_topics_needed=(
                int(focus_pair["driver_topics_needed"]) if focus_pair.get("driver_topics_needed") is not None else None
            ),
        )

        rows.append(
            {
                "party_id": int(pid),
                "party_name": str((party_by_id.get(pid) or {}).get("name") or ""),
                "rank": int(index + 1),
                "mean_score_clear": metric.get("mean_score_clear"),
                "comparable_topics_total": int(metric.get("comparable_topics_total") or 0),
                "high_conf_topics_total": int(metric.get("high_conf_topics_total") or 0),
                "high_conf_share": float(metric.get("high_conf_share") or 0.0),
                "high_conf_mean_score": metric.get("high_conf_mean_score"),
                "high_conf_drift": metric.get("high_conf_drift"),
                "gap_to_prev_rank": round(float(gap_to_prev), 6) if gap_to_prev is not None else None,
                "gap_to_next_rank": round(float(gap_to_next), 6) if gap_to_next is not None else None,
                "closest_neighbor_party_id": int(closest_neighbor_pid) if closest_neighbor_pid is not None else None,
                "closest_neighbor_party_name": (
                    str((party_by_id.get(int(closest_neighbor_pid)) or {}).get("name") or "") or None
                    if closest_neighbor_pid is not None
                    else None
                ),
                "closest_gap": round(float(closest_gap), 6) if closest_gap is not None else None,
                "rank_band": {
                    "id": str(band_id),
                    "label": str(band_label),
                    "reason_code": str(reason_code),
                    "reason_label": str(reason_label),
                },
                "focus_pair": focus_pair,
                "links": {
                    "explorer_politico_party": str(((party_by_id.get(pid) or {}).get("links") or {}).get("explorer_politico_party") or ""),
                },
            }
        )

    return {
        "meta": {
            "artifact_version": "citizen_ranking_robustness_v1",
            "topic_set_id": int(scope.topic_set_id),
            "institution_id": int(scope.institution_id),
            "as_of_date": str(scope.as_of_date),
            "computed_method": str(scope.computed_method),
            "computed_version": str(scope.computed_version),
            "rows_total": int(len(rows)),
            "thresholds": {
                "min_pair_comparable_topics": int(RANK_ROBUSTNESS_MIN_PAIR_COMPARABLE),
                "thin_margin_max": float(RANK_ROBUSTNESS_THIN_MARGIN_MAX),
                "competitive_margin_max": float(RANK_ROBUSTNESS_COMPETITIVE_MARGIN_MAX),
                "high_confidence_min": float(CONF_TIER_HIGH_MIN),
            },
        },
        "rows": rows,
    }


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
        party_topic_stats = collect_party_topic_stats(conn, scope=scope, topics=topics, parties=parties)
        party_topic_positions = export_party_topic_positions(
            conn,
            scope=scope,
            topics=topics,
            parties=parties,
            stats=party_topic_stats,
        )
        party_topic_comparability = export_party_topic_comparability(
            scope=scope,
            topics=topics,
            parties=parties,
            positions=party_topic_positions,
            stats=party_topic_stats,
        )
        party_topic_lineage = export_party_topic_lineage(
            conn,
            scope=scope,
            topics=topics,
            parties=parties,
            positions=party_topic_positions,
            stats=party_topic_stats,
        )
        party_topic_snapshot_diff = export_party_topic_snapshot_diff(
            conn,
            scope=scope,
            topics=topics,
            parties=parties,
            positions=party_topic_positions,
            stats=party_topic_stats,
        )
        party_ranking_robustness = export_party_ranking_robustness(
            scope=scope,
            topics=topics,
            parties=parties,
            positions=party_topic_positions,
        )
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
                # Optional v2 extension: allow honest labeling and future method toggles.
                "methods_available": methods_available(
                    conn,
                    topic_set_id=int(scope.topic_set_id),
                    institution_id=int(scope.institution_id),
                    as_of_date=str(scope.as_of_date),
                ),
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
        if programas_meta:
            payload["meta"]["programas"] = programas_meta

        payload["meta"]["freshness"] = build_snapshot_freshness(
            generated_at=str(payload["meta"]["generated_at"]),
            as_of_date=str(payload["meta"]["as_of_date"]),
        )
        payload["meta"]["honesty"] = build_snapshot_honesty_contract()

        payload = strip_private_fields(payload)
        party_topic_comparability = strip_private_fields(party_topic_comparability)
        party_topic_lineage = strip_private_fields(party_topic_lineage)
        party_topic_snapshot_diff = strip_private_fields(party_topic_snapshot_diff)
        party_ranking_robustness = strip_private_fields(party_ranking_robustness)

        if bool(args.pretty):
            out_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        else:
            out_path.write_text(json.dumps(payload, ensure_ascii=True, separators=(",", ":")), encoding="utf-8")

        comparability_out_path = _companion_out_path(out_path, "comparability")
        lineage_out_path = _companion_out_path(out_path, "lineage")
        diff_out_path = _companion_out_path(out_path, "snapshot_diff")
        robustness_out_path = _companion_out_path(out_path, "ranking_robustness")
        if bool(args.pretty):
            comparability_out_path.write_text(json.dumps(party_topic_comparability, ensure_ascii=True, indent=2), encoding="utf-8")
            lineage_out_path.write_text(json.dumps(party_topic_lineage, ensure_ascii=True, indent=2), encoding="utf-8")
            diff_out_path.write_text(json.dumps(party_topic_snapshot_diff, ensure_ascii=True, indent=2), encoding="utf-8")
            robustness_out_path.write_text(json.dumps(party_ranking_robustness, ensure_ascii=True, indent=2), encoding="utf-8")
        else:
            comparability_out_path.write_text(
                json.dumps(party_topic_comparability, ensure_ascii=True, separators=(",", ":")),
                encoding="utf-8",
            )
            lineage_out_path.write_text(
                json.dumps(party_topic_lineage, ensure_ascii=True, separators=(",", ":")),
                encoding="utf-8",
            )
            diff_out_path.write_text(
                json.dumps(party_topic_snapshot_diff, ensure_ascii=True, separators=(",", ":")),
                encoding="utf-8",
            )
            robustness_out_path.write_text(
                json.dumps(party_ranking_robustness, ensure_ascii=True, separators=(",", ":")),
                encoding="utf-8",
            )

        size = out_path.stat().st_size
        if int(args.max_bytes) > 0 and size > int(args.max_bytes):
            print(f"ERROR: citizen snapshot demasiado grande: bytes={size} max_bytes={int(args.max_bytes)} -> {out_path}")
            return 3

        print(
            "OK citizen snapshot -> "
            + str(out_path)
            + f" (topic_set_id={scope.topic_set_id} as_of_date={scope.as_of_date} method={scope.computed_method} version={scope.computed_version} bytes={size})"
        )
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
