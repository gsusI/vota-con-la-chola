#!/usr/bin/env python3
"""Export a bounded, deterministic JSON snapshot for the citizen GH Pages app.

Goal:
- Turn existing analytics (topic_sets/topics/topic_positions) into a user-first artifact.
- Keep it static-friendly: no API required.
- Preserve honesty: expose coverage and avoid silent imputation.

Output:
- JSON file matching `docs/etl/sprints/AI-OPS-17/reports/citizen-data-contract.md`.

This exporter is intentionally conservative: it exports aggregated party stances per topic
(with coverage) and only links out to the existing explorers for audit/evidence drill-down.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_MAX_BYTES = 5_000_000
DEFAULT_TOPIC_SET_ID = 1
DEFAULT_INSTITUTION_ID = 7  # Congreso de los Diputados


@dataclass(frozen=True)
class Scope:
    topic_set_id: int
    institution_id: int
    as_of_date: str
    computed_method: str
    computed_version: str


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
        choices=("auto", "combined", "votes"),
        help="Metodo de posiciones a usar (auto=combined si existe, si no votes)",
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


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


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


def export_topics(conn: sqlite3.Connection, *, scope: Scope, max_topics: int) -> list[dict[str, Any]]:
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
        LIMIT ?
        """,
        (int(scope.topic_set_id), int(max(1, max_topics))),
    ).fetchall()

    topics: list[dict[str, Any]] = []
    for r in rows:
        topic_id = int(r["topic_id"])
        topics.append(
            {
                "topic_id": topic_id,
                "label": str(r["label"] or ""),
                "stakes_rank": int(r["stakes_rank"]) if r["stakes_rank"] is not None else None,
                "is_high_stakes": bool(int(r["is_high_stakes"] or 0)),
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
    return topics


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


def strip_private_fields(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: strip_private_fields(v) for k, v in obj.items() if not str(k).startswith("_")}
    if isinstance(obj, list):
        return [strip_private_fields(x) for x in obj]
    return obj


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

        topics = export_topics(conn, scope=scope, max_topics=int(args.max_topics))
        parties = export_parties(conn, scope=scope, max_parties=int(args.max_parties))
        party_topic_positions = export_party_topic_positions(conn, scope=scope, topics=topics, parties=parties)

        payload = {
            "meta": {
                "generated_at": now_utc_iso(),
                "db_path": str(db_path),
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
            },
            "concerns": {
                "version": "v1",
                "path": "data/concerns_v1.json",
            },
            "topics": topics,
            "parties": parties,
            "party_topic_positions": party_topic_positions,
        }

        payload = strip_private_fields(payload)

        if bool(args.pretty):
            out_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        else:
            out_path.write_text(json.dumps(payload, ensure_ascii=True, separators=(",", ":")), encoding="utf-8")

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
