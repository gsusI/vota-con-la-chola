from __future__ import annotations

import sqlite3
from typing import Any, Iterable, Mapping

DEFAULT_VOTE_QUALITY_THRESHOLDS: dict[str, float] = {
    "events_with_date_pct": 0.95,
    "events_with_theme_pct": 0.95,
    "events_with_totals_pct": 0.95,
    # Linking is part of the canonical pipeline; keep a high bar to avoid silent regressions.
    "events_with_initiative_link_pct": 0.95,
    "member_votes_with_person_id_pct": 0.90,
}

DEFAULT_INITIATIVE_QUALITY_THRESHOLDS: dict[str, float] = {
    "initiatives_with_title_pct": 0.90,
    "initiatives_with_expediente_pct": 0.70,
    "initiatives_with_legislature_pct": 0.50,
    "initiatives_linked_to_votes_pct": 0.0,
}


def _normalize_source_ids(source_ids: Iterable[str]) -> tuple[str, ...]:
    normalized = sorted({str(s).strip() for s in source_ids if str(s).strip()})
    if not normalized:
        raise ValueError("source_ids vacio")
    return tuple(normalized)


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return float(numerator) / float(denominator)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (str(table),),
        ).fetchone()
        return row is not None
    except sqlite3.Error:
        return False


def _empty_source_kpis() -> dict[str, Any]:
    return {
        "events_total": 0,
        "events_with_date": 0,
        "events_with_theme": 0,
        "events_with_totals": 0,
        "events_with_nominal_vote": 0,
        "events_with_initiative_link": 0,
        "events_with_official_initiative_link": 0,
        "events_with_date_pct": 0.0,
        "events_with_theme_pct": 0.0,
        "events_with_totals_pct": 0.0,
        "events_with_nominal_vote_pct": 0.0,
        "events_with_initiative_link_pct": 0.0,
        "events_with_official_initiative_link_pct": 0.0,
        "latest_legislature": None,
        "latest_events_total": 0,
        "latest_events_with_topic_evidence": 0,
        "latest_events_with_topic_evidence_pct": 0.0,
        "member_votes_total": 0,
        "member_votes_with_person_id": 0,
        "member_votes_with_person_id_pct": 0.0,
    }


def _empty_initiative_kpis() -> dict[str, Any]:
    return {
        "initiatives_total": 0,
        "initiatives_with_title": 0,
        "initiatives_with_expediente": 0,
        "initiatives_with_legislature": 0,
        "initiatives_linked_to_votes": 0,
        "initiatives_with_title_pct": 0.0,
        "initiatives_with_expediente_pct": 0.0,
        "initiatives_with_legislature_pct": 0.0,
        "initiatives_linked_to_votes_pct": 0.0,
    }


def compute_vote_quality_kpis(
    conn: sqlite3.Connection,
    source_ids: Iterable[str] = ("congreso_votaciones", "senado_votaciones"),
) -> dict[str, Any]:
    source_ids_tuple = _normalize_source_ids(source_ids)
    placeholders = ",".join("?" for _ in source_ids_tuple)

    event_rows = conn.execute(
        f"""
        WITH selected_events AS (
          SELECT
            vote_event_id,
            source_id,
            vote_date,
            title,
            expediente_text,
            subgroup_title,
            subgroup_text,
            totals_present,
            totals_yes,
            totals_no,
            totals_abstain,
            totals_no_vote
          FROM parl_vote_events
          WHERE source_id IN ({placeholders})
        ),
        initiative_events AS (
          SELECT DISTINCT
            e.source_id,
            l.vote_event_id
          FROM selected_events e
          JOIN parl_vote_event_initiatives l
            ON l.vote_event_id = e.vote_event_id
        ),
        official_initiative_events AS (
          SELECT DISTINCT
            e.source_id,
            l.vote_event_id
          FROM selected_events e
          JOIN parl_vote_event_initiatives l
            ON l.vote_event_id = e.vote_event_id
          JOIN parl_initiatives i
            ON i.initiative_id = l.initiative_id
          WHERE i.supertype IS NULL OR TRIM(i.supertype) <> 'derived'
        ),
        nominal_events AS (
          SELECT DISTINCT vote_event_id
          FROM parl_vote_member_votes
        )
        SELECT
          e.source_id,
          COUNT(*) AS events_total,
          SUM(
            CASE
              WHEN e.vote_date IS NOT NULL AND TRIM(e.vote_date) <> '' THEN 1
              ELSE 0
            END
          ) AS events_with_date,
          SUM(
            CASE
              WHEN (
                (e.title IS NOT NULL AND TRIM(e.title) <> '')
                OR (e.expediente_text IS NOT NULL AND TRIM(e.expediente_text) <> '')
                OR (e.subgroup_title IS NOT NULL AND TRIM(e.subgroup_title) <> '')
                OR (e.subgroup_text IS NOT NULL AND TRIM(e.subgroup_text) <> '')
              ) THEN 1
              ELSE 0
            END
          ) AS events_with_theme,
          SUM(
            CASE
              WHEN (
                e.totals_present IS NOT NULL
                OR e.totals_yes IS NOT NULL
                OR e.totals_no IS NOT NULL
                OR e.totals_abstain IS NOT NULL
                OR e.totals_no_vote IS NOT NULL
              ) THEN 1
              ELSE 0
            END
          ) AS events_with_totals,
          SUM(
            CASE
              WHEN n.vote_event_id IS NOT NULL THEN 1
              ELSE 0
            END
          ) AS events_with_nominal_vote,
          SUM(
            CASE
              WHEN ie.vote_event_id IS NOT NULL THEN 1
              ELSE 0
            END
          ) AS events_with_initiative_link
          ,
          SUM(
            CASE
              WHEN oie.vote_event_id IS NOT NULL THEN 1
              ELSE 0
            END
          ) AS events_with_official_initiative_link
        FROM selected_events e
        LEFT JOIN nominal_events n ON n.vote_event_id = e.vote_event_id
        LEFT JOIN initiative_events ie ON ie.vote_event_id = e.vote_event_id
        LEFT JOIN official_initiative_events oie ON oie.vote_event_id = e.vote_event_id
        GROUP BY e.source_id
        ORDER BY e.source_id
        """,
        source_ids_tuple,
    ).fetchall()

    member_vote_rows = conn.execute(
        f"""
        SELECT
          e.source_id,
          COUNT(*) AS member_votes_total,
          SUM(
            CASE
              WHEN mv.person_id IS NOT NULL THEN 1
              ELSE 0
            END
          ) AS member_votes_with_person_id
        FROM parl_vote_member_votes mv
        JOIN parl_vote_events e ON e.vote_event_id = mv.vote_event_id
        WHERE e.source_id IN ({placeholders})
        GROUP BY e.source_id
        ORDER BY e.source_id
        """,
        source_ids_tuple,
    ).fetchall()

    latest_leg_rows = conn.execute(
        f"""
        SELECT
          source_id,
          MAX(CAST(legislature AS INTEGER)) AS latest_leg
        FROM parl_vote_events
        WHERE source_id IN ({placeholders})
          AND legislature IS NOT NULL AND TRIM(legislature) <> ''
        GROUP BY source_id
        ORDER BY source_id
        """,
        source_ids_tuple,
    ).fetchall()
    latest_leg_by_source: dict[str, str | None] = {sid: None for sid in source_ids_tuple}
    for row in latest_leg_rows:
        sid = str(row["source_id"])
        leg = row["latest_leg"]
        latest_leg_by_source[sid] = str(int(leg)) if leg is not None else None

    latest_event_rows = conn.execute(
        f"""
        WITH latest AS (
          SELECT
            source_id,
            MAX(CAST(legislature AS INTEGER)) AS latest_leg
          FROM parl_vote_events
          WHERE source_id IN ({placeholders})
            AND legislature IS NOT NULL AND TRIM(legislature) <> ''
          GROUP BY source_id
        )
        SELECT
          e.source_id,
          COUNT(*) AS latest_events_total
        FROM parl_vote_events e
        JOIN latest l
          ON l.source_id = e.source_id
         AND CAST(e.legislature AS INTEGER) = l.latest_leg
        WHERE e.source_id IN ({placeholders})
        GROUP BY e.source_id
        ORDER BY e.source_id
        """,
        source_ids_tuple + source_ids_tuple,
    ).fetchall()
    latest_events_total_by_source: dict[str, int] = {sid: 0 for sid in source_ids_tuple}
    for row in latest_event_rows:
        latest_events_total_by_source[str(row["source_id"])] = int(row["latest_events_total"] or 0)

    latest_topic_events_by_source: dict[str, int] = {sid: 0 for sid in source_ids_tuple}
    if _table_exists(conn, "topic_evidence"):
        topic_event_rows = conn.execute(
            f"""
            WITH latest AS (
              SELECT
                source_id,
                MAX(CAST(legislature AS INTEGER)) AS latest_leg
              FROM parl_vote_events
              WHERE source_id IN ({placeholders})
                AND legislature IS NOT NULL AND TRIM(legislature) <> ''
              GROUP BY source_id
            )
            SELECT
              e.source_id,
              COUNT(DISTINCT e.vote_event_id) AS latest_events_with_topic_evidence
            FROM parl_vote_events e
            JOIN latest l
              ON l.source_id = e.source_id
             AND CAST(e.legislature AS INTEGER) = l.latest_leg
            JOIN topic_evidence te
              ON te.vote_event_id = e.vote_event_id
            WHERE e.source_id IN ({placeholders})
              AND te.evidence_type = 'revealed:vote'
              AND te.topic_id IS NOT NULL
            GROUP BY e.source_id
            ORDER BY e.source_id
            """,
            source_ids_tuple + source_ids_tuple,
        ).fetchall()
        for row in topic_event_rows:
            latest_topic_events_by_source[str(row["source_id"])] = int(
                row["latest_events_with_topic_evidence"] or 0
            )

    by_source: dict[str, dict[str, Any]] = {sid: _empty_source_kpis() for sid in source_ids_tuple}

    for row in event_rows:
        sid = str(row["source_id"])
        data = by_source.setdefault(sid, _empty_source_kpis())
        data["events_total"] = int(row["events_total"] or 0)
        data["events_with_date"] = int(row["events_with_date"] or 0)
        data["events_with_theme"] = int(row["events_with_theme"] or 0)
        data["events_with_totals"] = int(row["events_with_totals"] or 0)
        data["events_with_nominal_vote"] = int(row["events_with_nominal_vote"] or 0)
        data["events_with_initiative_link"] = int(row["events_with_initiative_link"] or 0)
        data["events_with_official_initiative_link"] = int(row["events_with_official_initiative_link"] or 0)

    for row in member_vote_rows:
        sid = str(row["source_id"])
        data = by_source.setdefault(sid, _empty_source_kpis())
        data["member_votes_total"] = int(row["member_votes_total"] or 0)
        data["member_votes_with_person_id"] = int(row["member_votes_with_person_id"] or 0)

    for sid in source_ids_tuple:
        data = by_source[sid]
        data["latest_legislature"] = latest_leg_by_source.get(sid)
        data["latest_events_total"] = int(latest_events_total_by_source.get(sid, 0))
        data["latest_events_with_topic_evidence"] = int(latest_topic_events_by_source.get(sid, 0))
        events_total = int(data["events_total"])
        latest_events_total = int(data["latest_events_total"])
        member_votes_total = int(data["member_votes_total"])
        data["events_with_date_pct"] = _ratio(int(data["events_with_date"]), events_total)
        data["events_with_theme_pct"] = _ratio(int(data["events_with_theme"]), events_total)
        data["events_with_totals_pct"] = _ratio(int(data["events_with_totals"]), events_total)
        data["events_with_nominal_vote_pct"] = _ratio(int(data["events_with_nominal_vote"]), events_total)
        data["events_with_initiative_link_pct"] = _ratio(
            int(data["events_with_initiative_link"]), events_total
        )
        data["events_with_official_initiative_link_pct"] = _ratio(
            int(data["events_with_official_initiative_link"]), events_total
        )
        data["latest_events_with_topic_evidence_pct"] = _ratio(
            int(data["latest_events_with_topic_evidence"]), latest_events_total
        )
        data["member_votes_with_person_id_pct"] = _ratio(
            int(data["member_votes_with_person_id"]), member_votes_total
        )

    events_total = sum(int(by_source[sid]["events_total"]) for sid in source_ids_tuple)
    events_with_date = sum(int(by_source[sid]["events_with_date"]) for sid in source_ids_tuple)
    events_with_theme = sum(int(by_source[sid]["events_with_theme"]) for sid in source_ids_tuple)
    events_with_totals = sum(int(by_source[sid]["events_with_totals"]) for sid in source_ids_tuple)
    events_with_nominal_vote = sum(
        int(by_source[sid]["events_with_nominal_vote"]) for sid in source_ids_tuple
    )
    events_with_initiative_link = sum(
        int(by_source[sid]["events_with_initiative_link"]) for sid in source_ids_tuple
    )
    events_with_official_initiative_link = sum(
        int(by_source[sid]["events_with_official_initiative_link"]) for sid in source_ids_tuple
    )
    latest_events_total = sum(int(by_source[sid]["latest_events_total"]) for sid in source_ids_tuple)
    latest_events_with_topic_evidence = sum(
        int(by_source[sid]["latest_events_with_topic_evidence"]) for sid in source_ids_tuple
    )
    member_votes_total = sum(int(by_source[sid]["member_votes_total"]) for sid in source_ids_tuple)
    member_votes_with_person_id = sum(
        int(by_source[sid]["member_votes_with_person_id"]) for sid in source_ids_tuple
    )

    return {
        "source_ids": list(source_ids_tuple),
        "events_total": events_total,
        "events_with_date": events_with_date,
        "events_with_date_pct": _ratio(events_with_date, events_total),
        "events_with_theme": events_with_theme,
        "events_with_theme_pct": _ratio(events_with_theme, events_total),
        "events_with_totals": events_with_totals,
        "events_with_totals_pct": _ratio(events_with_totals, events_total),
        "events_with_nominal_vote": events_with_nominal_vote,
        "events_with_nominal_vote_pct": _ratio(events_with_nominal_vote, events_total),
        "events_with_initiative_link": events_with_initiative_link,
        "events_with_initiative_link_pct": _ratio(events_with_initiative_link, events_total),
        "events_with_official_initiative_link": events_with_official_initiative_link,
        "events_with_official_initiative_link_pct": _ratio(
            events_with_official_initiative_link, events_total
        ),
        "latest_events_total": latest_events_total,
        "latest_events_with_topic_evidence": latest_events_with_topic_evidence,
        "latest_events_with_topic_evidence_pct": _ratio(
            latest_events_with_topic_evidence, latest_events_total
        ),
        "member_votes_total": member_votes_total,
        "member_votes_with_person_id": member_votes_with_person_id,
        "member_votes_with_person_id_pct": _ratio(member_votes_with_person_id, member_votes_total),
        "by_source": by_source,
    }


def compute_initiative_quality_kpis(
    conn: sqlite3.Connection,
    source_ids: Iterable[str] = ("congreso_iniciativas", "senado_iniciativas"),
) -> dict[str, Any]:
    source_ids_tuple = _normalize_source_ids(source_ids)
    placeholders = ",".join("?" for _ in source_ids_tuple)

    coverage_rows = conn.execute(
        f"""
        SELECT
          i.source_id,
          COUNT(*) AS initiatives_total,
          SUM(CASE WHEN i.title IS NOT NULL AND TRIM(i.title) <> '' THEN 1 ELSE 0 END)
            AS initiatives_with_title,
          SUM(CASE WHEN i.expediente IS NOT NULL AND TRIM(i.expediente) <> '' THEN 1 ELSE 0 END)
            AS initiatives_with_expediente,
          SUM(
            CASE
              WHEN i.legislature IS NOT NULL AND TRIM(i.legislature) <> '' THEN 1
              ELSE 0
            END
          ) AS initiatives_with_legislature
        FROM parl_initiatives i
        WHERE i.source_id IN ({placeholders})
        GROUP BY i.source_id
        ORDER BY i.source_id
        """,
        source_ids_tuple,
    ).fetchall()

    linked_rows = conn.execute(
        f"""
        SELECT
          i.source_id,
          COUNT(DISTINCT l.initiative_id) AS initiatives_linked_to_votes
        FROM parl_initiatives i
        LEFT JOIN parl_vote_event_initiatives l ON l.initiative_id = i.initiative_id
        WHERE i.source_id IN ({placeholders})
        GROUP BY i.source_id
        ORDER BY i.source_id
        """,
        source_ids_tuple,
    ).fetchall()

    by_source: dict[str, dict[str, Any]] = {
        sid: _empty_initiative_kpis() for sid in source_ids_tuple
    }
    for row in coverage_rows:
        sid = str(row["source_id"])
        data = by_source.setdefault(sid, _empty_initiative_kpis())
        data["initiatives_total"] = int(row["initiatives_total"] or 0)
        data["initiatives_with_title"] = int(row["initiatives_with_title"] or 0)
        data["initiatives_with_expediente"] = int(row["initiatives_with_expediente"] or 0)
        data["initiatives_with_legislature"] = int(row["initiatives_with_legislature"] or 0)

    for row in linked_rows:
        sid = str(row["source_id"])
        data = by_source.setdefault(sid, _empty_initiative_kpis())
        data["initiatives_linked_to_votes"] = int(row["initiatives_linked_to_votes"] or 0)

    total_initiatives = 0
    total_with_title = 0
    total_with_expediente = 0
    total_with_legislature = 0
    total_with_links = 0
    for sid in source_ids_tuple:
        data = by_source[sid]
        total = int(data["initiatives_total"])
        total_initiatives += total
        total_with_title += int(data["initiatives_with_title"])
        total_with_expediente += int(data["initiatives_with_expediente"])
        total_with_legislature += int(data["initiatives_with_legislature"])
        total_with_links += int(data["initiatives_linked_to_votes"])

        data["initiatives_with_title_pct"] = _ratio(int(data["initiatives_with_title"]), total)
        data["initiatives_with_expediente_pct"] = _ratio(
            int(data["initiatives_with_expediente"]), total
        )
        data["initiatives_with_legislature_pct"] = _ratio(
            int(data["initiatives_with_legislature"]), total
        )
        data["initiatives_linked_to_votes_pct"] = _ratio(
            int(data["initiatives_linked_to_votes"]), total
        )

    return {
        "source_ids": list(source_ids_tuple),
        "initiatives_total": total_initiatives,
        "initiatives_with_title": total_with_title,
        "initiatives_with_expediente": total_with_expediente,
        "initiatives_with_legislature": total_with_legislature,
        "initiatives_linked_to_votes": total_with_links,
        "initiatives_with_title_pct": _ratio(total_with_title, total_initiatives),
        "initiatives_with_expediente_pct": _ratio(total_with_expediente, total_initiatives),
        "initiatives_with_legislature_pct": _ratio(total_with_legislature, total_initiatives),
        "initiatives_linked_to_votes_pct": _ratio(total_with_links, total_initiatives),
        "by_source": by_source,
    }


def evaluate_vote_quality_gate(
    kpis: Mapping[str, Any],
    thresholds: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    resolved_thresholds = dict(DEFAULT_VOTE_QUALITY_THRESHOLDS)
    if thresholds:
        for metric, threshold in thresholds.items():
            resolved_thresholds[str(metric)] = float(threshold)

    ordered_metrics = sorted(resolved_thresholds.keys())
    failures: list[dict[str, Any]] = []

    for metric in ordered_metrics:
        threshold = float(resolved_thresholds[metric])
        actual = float(kpis.get(metric) or 0.0)
        if actual < threshold:
            failures.append(
                {
                    "metric": metric,
                    "actual": actual,
                    "threshold": threshold,
                }
            )

    return {
        "passed": len(failures) == 0,
        "failures": failures,
        "thresholds": {metric: float(resolved_thresholds[metric]) for metric in ordered_metrics},
    }


def evaluate_initiative_quality_gate(
    kpis: Mapping[str, Any],
    thresholds: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    resolved_thresholds = dict(DEFAULT_INITIATIVE_QUALITY_THRESHOLDS)
    if thresholds:
        for metric, threshold in thresholds.items():
            resolved_thresholds[str(metric)] = float(threshold)

    ordered_metrics = sorted(resolved_thresholds.keys())
    failures: list[dict[str, Any]] = []

    for metric in ordered_metrics:
        threshold = float(resolved_thresholds[metric])
        actual = float(kpis.get(metric) or 0.0)
        if actual < threshold:
            failures.append(
                {
                    "metric": metric,
                    "actual": actual,
                    "threshold": threshold,
                }
            )

    return {
        "passed": len(failures) == 0,
        "failures": failures,
        "thresholds": {metric: float(resolved_thresholds[metric]) for metric in ordered_metrics},
    }


__all__ = [
    "DEFAULT_VOTE_QUALITY_THRESHOLDS",
    "DEFAULT_INITIATIVE_QUALITY_THRESHOLDS",
    "compute_vote_quality_kpis",
    "evaluate_vote_quality_gate",
    "compute_initiative_quality_kpis",
    "evaluate_initiative_quality_gate",
]
