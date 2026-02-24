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
    # Only truly actionable missing initiative docs should block quality closeout.
    "actionable_doc_links_closed_pct": 1.0,
    # Initiative-document extraction is now part of the controllable pipeline.
    "extraction_coverage_pct": 0.95,
    "extraction_review_closed_pct": 0.95,
}

DEFAULT_DECLARED_QUALITY_THRESHOLDS: dict[str, float] = {
    # Declared evidence may legitimately output `unclear`/`no_signal`, but stance
    # should never be missing/blank once extracted.
    "topic_evidence_with_nonempty_stance_pct": 0.99,
    # Manual-review debt should stay mostly closed for declared sources.
    "review_closed_pct": 0.95,
    # Positions are expected only for actionable declared stances
    # (support/oppose/mixed), so this denominator excludes `unclear`.
    "declared_positions_coverage_pct": 0.95,
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


def _is_senado_global_enmiendas_url(url: str) -> bool:
    token = str(url or "").strip().lower()
    return bool(token and "senado.es" in token and "global_enmiendas_vetos_" in token)


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
        "initiatives_with_doc_links": 0,
        "initiatives_with_downloaded_docs": 0,
        "initiatives_linked_to_votes_with_downloaded_docs": 0,
        "total_doc_links": 0,
        "downloaded_doc_links": 0,
        "missing_doc_links": 0,
        "doc_links_with_fetch_status": 0,
        "doc_links_missing_fetch_status": 0,
        "downloaded_doc_links_with_excerpt": 0,
        "downloaded_doc_links_missing_excerpt": 0,
        "downloaded_doc_links_with_extraction": 0,
        "downloaded_doc_links_missing_extraction": 0,
        "extraction_needs_review_doc_links": 0,
        "missing_doc_links_status_buckets": [],
        "missing_doc_links_likely_not_expected": 0,
        "missing_doc_links_actionable": 0,
        "effective_downloaded_doc_links_pct": 0.0,
        "actionable_doc_links_closed_pct": 1.0,
        "global_enmiendas_vetos_analysis": {},
        "initiatives_with_title_pct": 0.0,
        "initiatives_with_expediente_pct": 0.0,
        "initiatives_with_legislature_pct": 0.0,
        "initiatives_linked_to_votes_pct": 0.0,
        "initiatives_with_doc_links_pct": 0.0,
        "initiatives_with_downloaded_docs_pct": 0.0,
        "initiatives_linked_to_votes_with_downloaded_docs_pct": 0.0,
        "downloaded_doc_links_pct": 0.0,
        "fetch_status_coverage_pct": 0.0,
        "excerpt_coverage_pct": 0.0,
        "extraction_coverage_pct": 0.0,
        "extraction_needs_review_pct": 0.0,
        "extraction_review_closed_pct": 0.0,
    }


def _empty_declared_kpis() -> dict[str, Any]:
    return {
        "source_records": 0,
        "text_documents": 0,
        "topic_evidence_total": 0,
        "topic_evidence_with_nonempty_stance": 0,
        "topic_evidence_with_supported_stance": 0,
        "review_total": 0,
        "review_pending": 0,
        "review_resolved": 0,
        "review_ignored": 0,
        "declared_positions_scope_total": 0,
        "declared_positions_total": 0,
        "topic_evidence_with_nonempty_stance_pct": 0.0,
        "review_closed_pct": 1.0,
        "declared_positions_coverage_pct": 1.0,
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

    has_text_documents = _table_exists(conn, "text_documents")
    has_document_fetches = _table_exists(conn, "document_fetches")
    has_initdoc_extractions = _table_exists(conn, "parl_initiative_doc_extractions")

    doc_rows: list[sqlite3.Row] = []
    doc_link_rows: list[sqlite3.Row] = []
    extraction_rows: list[sqlite3.Row] = []
    missing_status_rows: list[sqlite3.Row] = []
    linked_doc_rows: list[sqlite3.Row] = []
    senado_missing_global_rows: list[sqlite3.Row] = []
    senado_alt_downloaded_initiatives: set[str] = set()
    if _table_exists(conn, "parl_initiative_documents"):
        downloaded_ref = "d.source_record_pk IS NOT NULL"
        td_join = ""
        if has_text_documents:
            td_join = "LEFT JOIN text_documents td ON td.source_record_pk = d.source_record_pk AND td.source_id = 'parl_initiative_docs'"
            downloaded_ref = "td.source_record_pk IS NOT NULL"

        df_join = ""
        if has_document_fetches:
            df_join = "LEFT JOIN document_fetches df ON df.doc_url = d.doc_url AND df.source_id = 'parl_initiative_docs'"

        doc_rows = conn.execute(
            f"""
            SELECT
              i.source_id,
              COUNT(DISTINCT d.initiative_id) AS initiatives_with_doc_links,
              COUNT(DISTINCT CASE WHEN d.source_record_pk IS NOT NULL THEN d.initiative_id ELSE NULL END)
                AS initiatives_with_downloaded_docs
            FROM parl_initiatives i
            JOIN parl_initiative_documents d ON d.initiative_id = i.initiative_id
            WHERE i.source_id IN ({placeholders})
            GROUP BY i.source_id
            ORDER BY i.source_id
            """,
            source_ids_tuple,
        ).fetchall()

        doc_link_rows = conn.execute(
            f"""
            SELECT
              i.source_id,
              COUNT(*) AS total_doc_links,
              SUM(CASE WHEN {downloaded_ref} THEN 1 ELSE 0 END) AS downloaded_doc_links,
              SUM(CASE WHEN {downloaded_ref} THEN 0 ELSE 1 END) AS missing_doc_links,
              {"SUM(CASE WHEN df.doc_url IS NOT NULL THEN 1 ELSE 0 END)" if has_document_fetches else "0"} AS doc_links_with_fetch_status,
              {"SUM(CASE WHEN df.doc_url IS NULL THEN 1 ELSE 0 END)" if has_document_fetches else "COUNT(*)"} AS doc_links_missing_fetch_status,
              {"SUM(CASE WHEN " + downloaded_ref + " AND td.text_excerpt IS NOT NULL AND TRIM(td.text_excerpt) <> '' THEN 1 ELSE 0 END)" if has_text_documents else "0"} AS downloaded_doc_links_with_excerpt,
              {"SUM(CASE WHEN " + downloaded_ref + " AND (td.text_excerpt IS NULL OR TRIM(td.text_excerpt) = '') THEN 1 ELSE 0 END)" if has_text_documents else "0"} AS downloaded_doc_links_missing_excerpt
            FROM parl_initiatives i
            JOIN parl_initiative_documents d ON d.initiative_id = i.initiative_id
            {td_join}
            {df_join}
            WHERE i.source_id IN ({placeholders})
            GROUP BY i.source_id
            ORDER BY i.source_id
            """,
            source_ids_tuple,
        ).fetchall()

        if has_initdoc_extractions:
            extraction_rows = conn.execute(
                f"""
                SELECT
                  i.source_id,
                  SUM(CASE WHEN {downloaded_ref} AND ex.source_record_pk IS NOT NULL THEN 1 ELSE 0 END)
                    AS downloaded_doc_links_with_extraction,
                  SUM(CASE WHEN {downloaded_ref} AND ex.source_record_pk IS NULL THEN 1 ELSE 0 END)
                    AS downloaded_doc_links_missing_extraction,
                  SUM(
                    CASE
                      WHEN {downloaded_ref} AND ex.source_record_pk IS NOT NULL AND ex.needs_review = 1 THEN 1
                      ELSE 0
                    END
                  ) AS extraction_needs_review_doc_links
                FROM parl_initiatives i
                JOIN parl_initiative_documents d ON d.initiative_id = i.initiative_id
                {td_join}
                LEFT JOIN parl_initiative_doc_extractions ex
                  ON ex.source_record_pk = d.source_record_pk
                 AND ex.source_id = 'parl_initiative_docs'
                WHERE i.source_id IN ({placeholders})
                GROUP BY i.source_id
                ORDER BY i.source_id
                """,
                source_ids_tuple,
            ).fetchall()

        if has_document_fetches:
            missing_doc_condition = (
                "td.source_record_pk IS NULL" if has_text_documents else "d.source_record_pk IS NULL"
            )
            missing_status_rows = conn.execute(
                f"""
                SELECT
                  i.source_id,
                  COALESCE(df.last_http_status, 0) AS missing_status,
                  COUNT(*) AS missing_count
                FROM parl_initiatives i
                JOIN parl_initiative_documents d ON d.initiative_id = i.initiative_id
                {td_join}
                {df_join}
                WHERE i.source_id IN ({placeholders})
                  AND {missing_doc_condition}
                GROUP BY i.source_id, COALESCE(df.last_http_status, 0)
                ORDER BY i.source_id ASC, missing_count DESC, missing_status DESC
                """,
                source_ids_tuple,
            ).fetchall()

            linked_doc_rows = conn.execute(
                f"""
                SELECT
              i.source_id,
              COUNT(DISTINCT vi.initiative_id) AS initiatives_linked_to_votes_with_downloaded_docs
            FROM parl_initiatives i
            JOIN parl_vote_event_initiatives vi ON vi.initiative_id = i.initiative_id
            JOIN parl_initiative_documents d ON d.initiative_id = vi.initiative_id
            WHERE i.source_id IN ({placeholders})
              AND d.source_record_pk IS NOT NULL
            GROUP BY i.source_id
            ORDER BY i.source_id
            """,
                source_ids_tuple,
            ).fetchall()

        if has_text_documents and "senado_iniciativas" in source_ids_tuple:
            senado_missing_global_rows = conn.execute(
                """
                SELECT
                  d.initiative_id,
                  d.doc_url
                FROM parl_initiatives i
                JOIN parl_initiative_documents d ON d.initiative_id = i.initiative_id
                LEFT JOIN text_documents td ON td.source_record_pk = d.source_record_pk AND td.source_id = 'parl_initiative_docs'
                WHERE i.source_id = 'senado_iniciativas'
                  AND d.doc_kind = 'bocg'
                  AND d.doc_url LIKE '%global_enmiendas_vetos%'
                  AND td.source_record_pk IS NULL
                ORDER BY d.initiative_id ASC, d.doc_url ASC
                """
            ).fetchall()

            alt_rows = conn.execute(
                """
                SELECT DISTINCT pid.initiative_id
                FROM parl_initiative_documents pid
                JOIN parl_initiatives i2 ON i2.initiative_id = pid.initiative_id
                JOIN text_documents td ON td.source_record_pk = pid.source_record_pk
                WHERE i2.source_id = 'senado_iniciativas'
                  AND td.source_id = 'parl_initiative_docs'
                  AND pid.doc_kind = 'bocg'
                  AND (
                    pid.doc_url LIKE '%/xml/INI-3-%'
                    OR pid.doc_url LIKE '%/publicaciones/pdf/senado/bocg/%'
                    OR pid.doc_url LIKE '%tipoFich=3%'
                  )
                """
            ).fetchall()
            for row in alt_rows:
                iid = str(row["initiative_id"] or "").strip()
                if iid:
                    senado_alt_downloaded_initiatives.add(iid)

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

    for row in doc_rows:
        sid = str(row["source_id"])
        data = by_source.setdefault(sid, _empty_initiative_kpis())
        data["initiatives_with_doc_links"] = int(row["initiatives_with_doc_links"] or 0)
        data["initiatives_with_downloaded_docs"] = int(row["initiatives_with_downloaded_docs"] or 0)

    for row in doc_link_rows:
        sid = str(row["source_id"])
        data = by_source.setdefault(sid, _empty_initiative_kpis())
        data["total_doc_links"] = int(row["total_doc_links"] or 0)
        data["downloaded_doc_links"] = int(row["downloaded_doc_links"] or 0)
        data["missing_doc_links"] = int(row["missing_doc_links"] or 0)
        data["doc_links_with_fetch_status"] = int(row["doc_links_with_fetch_status"] or 0)
        data["doc_links_missing_fetch_status"] = int(row["doc_links_missing_fetch_status"] or 0)
        data["downloaded_doc_links_with_excerpt"] = int(
            row["downloaded_doc_links_with_excerpt"] or 0
        )
        data["downloaded_doc_links_missing_excerpt"] = int(
            row["downloaded_doc_links_missing_excerpt"] or 0
        )

    for row in extraction_rows:
        sid = str(row["source_id"])
        data = by_source.setdefault(sid, _empty_initiative_kpis())
        data["downloaded_doc_links_with_extraction"] = int(
            row["downloaded_doc_links_with_extraction"] or 0
        )
        data["downloaded_doc_links_missing_extraction"] = int(
            row["downloaded_doc_links_missing_extraction"] or 0
        )
        data["extraction_needs_review_doc_links"] = int(
            row["extraction_needs_review_doc_links"] or 0
        )

    for row in missing_status_rows:
        sid = str(row["source_id"])
        data = by_source.setdefault(sid, _empty_initiative_kpis())
        buckets = list(data.get("missing_doc_links_status_buckets") or [])
        buckets.append(
            {
                "status": int(row["missing_status"] or 0),
                "count": int(row["missing_count"] or 0),
            }
        )
        data["missing_doc_links_status_buckets"] = buckets

    for row in linked_doc_rows:
        sid = str(row["source_id"])
        data = by_source.setdefault(sid, _empty_initiative_kpis())
        data["initiatives_linked_to_votes_with_downloaded_docs"] = int(
            row["initiatives_linked_to_votes_with_downloaded_docs"] or 0
        )

    if "senado_iniciativas" in by_source:
        sen_data = by_source["senado_iniciativas"]
        total_global_missing = 0
        redundant_global = 0
        for row in senado_missing_global_rows:
            doc_url = str(row["doc_url"] or "")
            if not _is_senado_global_enmiendas_url(doc_url):
                continue
            total_global_missing += 1
            iid = str(row["initiative_id"] or "").strip()
            if iid and iid in senado_alt_downloaded_initiatives:
                redundant_global += 1

        likely_not_expected = min(int(sen_data["missing_doc_links"]), int(redundant_global))
        sen_data["global_enmiendas_vetos_analysis"] = {
            "total_global_enmiendas_missing": int(total_global_missing),
            "likely_not_expected_redundant_global_url": int(redundant_global),
            "likely_not_expected_total": int(redundant_global),
            "actionable_missing_count": max(0, int(total_global_missing) - int(redundant_global)),
            "classification_counts": {
                "likely_not_expected_redundant_global_url": int(redundant_global),
            },
        }
        sen_data["missing_doc_links_likely_not_expected"] = int(likely_not_expected)
        sen_data["missing_doc_links_actionable"] = max(
            0,
            int(sen_data["missing_doc_links"]) - int(likely_not_expected),
        )

    total_initiatives = 0
    total_with_title = 0
    total_with_expediente = 0
    total_with_legislature = 0
    total_with_links = 0
    total_with_doc_links = 0
    total_with_downloaded_docs = 0
    total_linked_with_downloaded_docs = 0
    total_doc_links = 0
    total_downloaded_doc_links = 0
    total_missing_doc_links = 0
    total_missing_doc_links_likely_not_expected = 0
    total_missing_doc_links_actionable = 0
    total_doc_links_with_fetch_status = 0
    total_doc_links_missing_fetch_status = 0
    total_downloaded_doc_links_with_excerpt = 0
    total_downloaded_doc_links_missing_excerpt = 0
    total_downloaded_doc_links_with_extraction = 0
    total_downloaded_doc_links_missing_extraction = 0
    total_extraction_needs_review_doc_links = 0
    overall_missing_status_buckets: dict[int, int] = {}
    for sid in source_ids_tuple:
        data = by_source[sid]
        total = int(data["initiatives_total"])
        # For now this KPI treats only known redundant Senado global_enmiendas links as
        # likely-not-expected. Other sources default to zero until additional triage rules are added.
        likely_not_expected = int(data.get("missing_doc_links_likely_not_expected") or 0)
        data["missing_doc_links_likely_not_expected"] = int(likely_not_expected)
        data["missing_doc_links_actionable"] = max(
            0,
            int(data.get("missing_doc_links") or 0) - int(likely_not_expected),
        )
        effective_den = max(0, int(data["total_doc_links"]) - int(likely_not_expected))
        data["effective_downloaded_doc_links_pct"] = _ratio(
            int(data["downloaded_doc_links"]),
            effective_den,
        )
        total_doc_links_source = int(data["total_doc_links"])
        actionable_missing_source = int(data["missing_doc_links_actionable"])
        if total_doc_links_source > 0:
            data["actionable_doc_links_closed_pct"] = _ratio(
                max(0, total_doc_links_source - actionable_missing_source),
                total_doc_links_source,
            )
        else:
            data["actionable_doc_links_closed_pct"] = 1.0

        total_initiatives += total
        total_with_title += int(data["initiatives_with_title"])
        total_with_expediente += int(data["initiatives_with_expediente"])
        total_with_legislature += int(data["initiatives_with_legislature"])
        total_with_links += int(data["initiatives_linked_to_votes"])
        total_with_doc_links += int(data["initiatives_with_doc_links"])
        total_with_downloaded_docs += int(data["initiatives_with_downloaded_docs"])
        total_linked_with_downloaded_docs += int(data["initiatives_linked_to_votes_with_downloaded_docs"])
        total_doc_links += int(data["total_doc_links"])
        total_downloaded_doc_links += int(data["downloaded_doc_links"])
        total_missing_doc_links += int(data["missing_doc_links"])
        total_missing_doc_links_likely_not_expected += int(
            data.get("missing_doc_links_likely_not_expected") or 0
        )
        total_missing_doc_links_actionable += int(data.get("missing_doc_links_actionable") or 0)
        total_doc_links_with_fetch_status += int(data["doc_links_with_fetch_status"])
        total_doc_links_missing_fetch_status += int(data["doc_links_missing_fetch_status"])
        total_downloaded_doc_links_with_excerpt += int(data["downloaded_doc_links_with_excerpt"])
        total_downloaded_doc_links_missing_excerpt += int(data["downloaded_doc_links_missing_excerpt"])
        total_downloaded_doc_links_with_extraction += int(
            data["downloaded_doc_links_with_extraction"]
        )
        total_downloaded_doc_links_missing_extraction += int(
            data["downloaded_doc_links_missing_extraction"]
        )
        total_extraction_needs_review_doc_links += int(data["extraction_needs_review_doc_links"])

        for b in list(data.get("missing_doc_links_status_buckets") or []):
            st = int(b.get("status") or 0)
            c = int(b.get("count") or 0)
            overall_missing_status_buckets[st] = int(overall_missing_status_buckets.get(st, 0)) + c

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
        data["initiatives_with_doc_links_pct"] = _ratio(int(data["initiatives_with_doc_links"]), total)
        data["initiatives_with_downloaded_docs_pct"] = _ratio(int(data["initiatives_with_downloaded_docs"]), total)
        data["initiatives_linked_to_votes_with_downloaded_docs_pct"] = _ratio(
            int(data["initiatives_linked_to_votes_with_downloaded_docs"]), int(data["initiatives_linked_to_votes"])
        )
        data["downloaded_doc_links_pct"] = _ratio(
            int(data["downloaded_doc_links"]), int(data["total_doc_links"])
        )
        data["fetch_status_coverage_pct"] = _ratio(
            int(data["doc_links_with_fetch_status"]), int(data["total_doc_links"])
        )
        data["excerpt_coverage_pct"] = _ratio(
            int(data["downloaded_doc_links_with_excerpt"]), int(data["downloaded_doc_links"])
        )
        data["extraction_coverage_pct"] = _ratio(
            int(data["downloaded_doc_links_with_extraction"]), int(data["downloaded_doc_links"])
        )
        data["extraction_needs_review_pct"] = _ratio(
            int(data["extraction_needs_review_doc_links"]),
            int(data["downloaded_doc_links_with_extraction"]),
        )
        extracted_total = int(data["downloaded_doc_links_with_extraction"])
        downloaded_total = int(data["downloaded_doc_links"])
        extraction_open = int(data["extraction_needs_review_doc_links"])
        if extracted_total > 0:
            data["extraction_review_closed_pct"] = _ratio(
                max(0, extracted_total - extraction_open),
                extracted_total,
            )
        elif downloaded_total > 0:
            data["extraction_review_closed_pct"] = 0.0
        else:
            data["extraction_review_closed_pct"] = 1.0
        data["missing_doc_links_status_buckets"] = sorted(
            list(data.get("missing_doc_links_status_buckets") or []),
            key=lambda x: (-int(x.get("count") or 0), -int(x.get("status") or 0)),
        )

    overall_buckets = [
        {"status": int(status), "count": int(count)}
        for status, count in overall_missing_status_buckets.items()
    ]
    overall_buckets.sort(key=lambda x: (-int(x["count"]), -int(x["status"])))

    return {
        "source_ids": list(source_ids_tuple),
        "initiatives_total": total_initiatives,
        "initiatives_with_title": total_with_title,
        "initiatives_with_expediente": total_with_expediente,
        "initiatives_with_legislature": total_with_legislature,
        "initiatives_linked_to_votes": total_with_links,
        "initiatives_with_doc_links": total_with_doc_links,
        "initiatives_with_downloaded_docs": total_with_downloaded_docs,
        "initiatives_linked_to_votes_with_downloaded_docs": total_linked_with_downloaded_docs,
        "total_doc_links": total_doc_links,
        "downloaded_doc_links": total_downloaded_doc_links,
        "missing_doc_links": total_missing_doc_links,
        "missing_doc_links_likely_not_expected": total_missing_doc_links_likely_not_expected,
        "missing_doc_links_actionable": total_missing_doc_links_actionable,
        "doc_links_with_fetch_status": total_doc_links_with_fetch_status,
        "doc_links_missing_fetch_status": total_doc_links_missing_fetch_status,
        "downloaded_doc_links_with_excerpt": total_downloaded_doc_links_with_excerpt,
        "downloaded_doc_links_missing_excerpt": total_downloaded_doc_links_missing_excerpt,
        "downloaded_doc_links_with_extraction": total_downloaded_doc_links_with_extraction,
        "downloaded_doc_links_missing_extraction": total_downloaded_doc_links_missing_extraction,
        "extraction_needs_review_doc_links": total_extraction_needs_review_doc_links,
        "missing_doc_links_status_buckets": overall_buckets,
        "initiatives_with_title_pct": _ratio(total_with_title, total_initiatives),
        "initiatives_with_expediente_pct": _ratio(total_with_expediente, total_initiatives),
        "initiatives_with_legislature_pct": _ratio(total_with_legislature, total_initiatives),
        "initiatives_linked_to_votes_pct": _ratio(total_with_links, total_initiatives),
        "initiatives_with_doc_links_pct": _ratio(total_with_doc_links, total_initiatives),
        "initiatives_with_downloaded_docs_pct": _ratio(total_with_downloaded_docs, total_initiatives),
        "initiatives_linked_to_votes_with_downloaded_docs_pct": _ratio(
            total_linked_with_downloaded_docs, total_with_links
        ),
        "downloaded_doc_links_pct": _ratio(total_downloaded_doc_links, total_doc_links),
        "effective_downloaded_doc_links_pct": _ratio(
            total_downloaded_doc_links,
            max(0, total_doc_links - total_missing_doc_links_likely_not_expected),
        ),
        "actionable_doc_links_closed_pct": (
            _ratio(
                max(0, total_doc_links - total_missing_doc_links_actionable),
                total_doc_links,
            )
            if total_doc_links > 0
            else 1.0
        ),
        "fetch_status_coverage_pct": _ratio(total_doc_links_with_fetch_status, total_doc_links),
        "excerpt_coverage_pct": _ratio(
            total_downloaded_doc_links_with_excerpt, total_downloaded_doc_links
        ),
        "extraction_coverage_pct": _ratio(
            total_downloaded_doc_links_with_extraction, total_downloaded_doc_links
        ),
        "extraction_needs_review_pct": _ratio(
            total_extraction_needs_review_doc_links,
            total_downloaded_doc_links_with_extraction,
        ),
        "extraction_review_closed_pct": (
            _ratio(
                max(
                    0,
                    total_downloaded_doc_links_with_extraction
                    - total_extraction_needs_review_doc_links,
                ),
                total_downloaded_doc_links_with_extraction,
            )
            if total_downloaded_doc_links_with_extraction > 0
            else (0.0 if total_downloaded_doc_links > 0 else 1.0)
        ),
        "by_source": by_source,
    }


def compute_declared_quality_kpis(
    conn: sqlite3.Connection,
    source_ids: Iterable[str] = ("congreso_intervenciones", "programas_partidos"),
) -> dict[str, Any]:
    source_ids_tuple = _normalize_source_ids(source_ids)
    placeholders = ",".join("?" for _ in source_ids_tuple)
    has_reviews = _table_exists(conn, "topic_evidence_reviews")
    has_positions = _table_exists(conn, "topic_positions")

    source_record_rows: list[sqlite3.Row] = []
    text_document_rows: list[sqlite3.Row] = []
    if _table_exists(conn, "source_records"):
        source_record_rows = conn.execute(
            f"""
            SELECT source_id, COUNT(*) AS source_records
            FROM source_records
            WHERE source_id IN ({placeholders})
            GROUP BY source_id
            ORDER BY source_id
            """,
            source_ids_tuple,
        ).fetchall()
    if _table_exists(conn, "text_documents"):
        text_document_rows = conn.execute(
            f"""
            SELECT source_id, COUNT(*) AS text_documents
            FROM text_documents
            WHERE source_id IN ({placeholders})
            GROUP BY source_id
            ORDER BY source_id
            """,
            source_ids_tuple,
        ).fetchall()

    evidence_rows = conn.execute(
        f"""
        SELECT
          source_id,
          COUNT(*) AS topic_evidence_total,
          SUM(CASE WHEN stance IS NOT NULL AND TRIM(stance) <> '' THEN 1 ELSE 0 END)
            AS topic_evidence_with_nonempty_stance,
          SUM(
            CASE
              WHEN stance IN ('support', 'oppose', 'mixed') THEN 1
              ELSE 0
            END
          ) AS topic_evidence_with_supported_stance
        FROM topic_evidence
        WHERE source_id IN ({placeholders})
          AND evidence_type LIKE 'declared:%'
        GROUP BY source_id
        ORDER BY source_id
        """,
        source_ids_tuple,
    ).fetchall()

    scope_rows = conn.execute(
        f"""
        SELECT
          scope.source_id,
          COUNT(*) AS declared_positions_scope_total
        FROM (
          SELECT
            source_id,
            topic_id,
            person_id,
            COALESCE(topic_set_id, -1) AS topic_set_key
          FROM topic_evidence
          WHERE source_id IN ({placeholders})
            AND evidence_type LIKE 'declared:%'
            AND stance IN ('support', 'oppose', 'mixed')
            AND topic_id IS NOT NULL
            AND person_id IS NOT NULL
          GROUP BY source_id, topic_id, person_id, COALESCE(topic_set_id, -1)
        ) scope
        GROUP BY scope.source_id
        ORDER BY scope.source_id
        """,
        source_ids_tuple,
    ).fetchall()

    positions_rows: list[sqlite3.Row] = []
    if has_positions:
        positions_rows = conn.execute(
            f"""
            WITH scope AS (
              SELECT
                source_id,
                topic_id,
                person_id,
                COALESCE(topic_set_id, -1) AS topic_set_key
              FROM topic_evidence
              WHERE source_id IN ({placeholders})
                AND evidence_type LIKE 'declared:%'
                AND stance IN ('support', 'oppose', 'mixed')
                AND topic_id IS NOT NULL
                AND person_id IS NOT NULL
              GROUP BY source_id, topic_id, person_id, COALESCE(topic_set_id, -1)
            )
            SELECT
              scope.source_id,
              COUNT(*) AS declared_positions_total
            FROM scope
            JOIN topic_positions tp
              ON tp.topic_id = scope.topic_id
             AND tp.person_id = scope.person_id
             AND COALESCE(tp.topic_set_id, -1) = scope.topic_set_key
            WHERE tp.computed_method = 'declared'
            GROUP BY scope.source_id
            ORDER BY scope.source_id
            """,
            source_ids_tuple,
        ).fetchall()

    review_rows: list[sqlite3.Row] = []
    if has_reviews:
        review_rows = conn.execute(
            f"""
            SELECT
              source_id,
              COUNT(*) AS review_total,
              SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS review_pending,
              SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) AS review_resolved,
              SUM(CASE WHEN status = 'ignored' THEN 1 ELSE 0 END) AS review_ignored
            FROM topic_evidence_reviews
            WHERE source_id IN ({placeholders})
            GROUP BY source_id
            ORDER BY source_id
            """,
            source_ids_tuple,
        ).fetchall()

    by_source: dict[str, dict[str, Any]] = {sid: _empty_declared_kpis() for sid in source_ids_tuple}

    for row in source_record_rows:
        sid = str(row["source_id"])
        by_source[sid]["source_records"] = int(row["source_records"] or 0)
    for row in text_document_rows:
        sid = str(row["source_id"])
        by_source[sid]["text_documents"] = int(row["text_documents"] or 0)
    for row in evidence_rows:
        sid = str(row["source_id"])
        data = by_source[sid]
        data["topic_evidence_total"] = int(row["topic_evidence_total"] or 0)
        data["topic_evidence_with_nonempty_stance"] = int(
            row["topic_evidence_with_nonempty_stance"] or 0
        )
        data["topic_evidence_with_supported_stance"] = int(
            row["topic_evidence_with_supported_stance"] or 0
        )
    for row in scope_rows:
        sid = str(row["source_id"])
        by_source[sid]["declared_positions_scope_total"] = int(
            row["declared_positions_scope_total"] or 0
        )
    for row in positions_rows:
        sid = str(row["source_id"])
        by_source[sid]["declared_positions_total"] = int(row["declared_positions_total"] or 0)
    for row in review_rows:
        sid = str(row["source_id"])
        data = by_source[sid]
        data["review_total"] = int(row["review_total"] or 0)
        data["review_pending"] = int(row["review_pending"] or 0)
        data["review_resolved"] = int(row["review_resolved"] or 0)
        data["review_ignored"] = int(row["review_ignored"] or 0)

    total_source_records = 0
    total_text_documents = 0
    total_topic_evidence = 0
    total_with_nonempty_stance = 0
    total_with_supported_stance = 0
    total_reviews = 0
    total_review_pending = 0
    total_review_resolved = 0
    total_review_ignored = 0
    total_scope = 0
    total_positions = 0

    for sid in source_ids_tuple:
        data = by_source[sid]
        topic_evidence_total = int(data["topic_evidence_total"])
        review_total = int(data["review_total"])
        review_closed = int(data["review_resolved"]) + int(data["review_ignored"])
        scope_total = int(data["declared_positions_scope_total"])
        positions_total = int(data["declared_positions_total"])

        data["topic_evidence_with_nonempty_stance_pct"] = _ratio(
            int(data["topic_evidence_with_nonempty_stance"]),
            topic_evidence_total,
        )
        data["review_closed_pct"] = (
            _ratio(review_closed, review_total) if review_total > 0 else 1.0
        )
        data["declared_positions_coverage_pct"] = (
            _ratio(positions_total, scope_total) if scope_total > 0 else 1.0
        )

        total_source_records += int(data["source_records"])
        total_text_documents += int(data["text_documents"])
        total_topic_evidence += topic_evidence_total
        total_with_nonempty_stance += int(data["topic_evidence_with_nonempty_stance"])
        total_with_supported_stance += int(data["topic_evidence_with_supported_stance"])
        total_reviews += review_total
        total_review_pending += int(data["review_pending"])
        total_review_resolved += int(data["review_resolved"])
        total_review_ignored += int(data["review_ignored"])
        total_scope += scope_total
        total_positions += positions_total

    total_review_closed = total_review_resolved + total_review_ignored

    return {
        "source_ids": list(source_ids_tuple),
        "source_records": total_source_records,
        "text_documents": total_text_documents,
        "topic_evidence_total": total_topic_evidence,
        "topic_evidence_with_nonempty_stance": total_with_nonempty_stance,
        "topic_evidence_with_supported_stance": total_with_supported_stance,
        "review_total": total_reviews,
        "review_pending": total_review_pending,
        "review_resolved": total_review_resolved,
        "review_ignored": total_review_ignored,
        "declared_positions_scope_total": total_scope,
        "declared_positions_total": total_positions,
        "topic_evidence_with_nonempty_stance_pct": _ratio(
            total_with_nonempty_stance,
            total_topic_evidence,
        ),
        "review_closed_pct": (_ratio(total_review_closed, total_reviews) if total_reviews > 0 else 1.0),
        "declared_positions_coverage_pct": (_ratio(total_positions, total_scope) if total_scope > 0 else 1.0),
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


def evaluate_declared_quality_gate(
    kpis: Mapping[str, Any],
    thresholds: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    resolved_thresholds = dict(DEFAULT_DECLARED_QUALITY_THRESHOLDS)
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
    "DEFAULT_DECLARED_QUALITY_THRESHOLDS",
    "compute_vote_quality_kpis",
    "evaluate_vote_quality_gate",
    "compute_initiative_quality_kpis",
    "evaluate_initiative_quality_gate",
    "compute_declared_quality_kpis",
    "evaluate_declared_quality_gate",
]
