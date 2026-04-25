#!/usr/bin/env python3
"""Import responsibility explainer seed data into normalized SQLite tables."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.politicos_es.db import apply_schema, open_db
from scripts import export_responsibility_explainer_snapshot as explainer_export


DEFAULT_SEED = explainer_export.DEFAULT_CASE_SEED


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def safe_text(value: Any) -> str:
    return explainer_export.safe_text(value)


def clean_text_list(items: Any) -> list[str]:
    return explainer_export.clean_text_list(items)


def has_required_case_metadata(case_def: dict[str, Any]) -> bool:
    incident_window = case_def.get("incident_window")
    questions = case_def.get("questions")
    return bool(
        safe_text(case_def.get("case_id"))
        and safe_text(case_def.get("title"))
        and safe_text(case_def.get("short_label"))
        and safe_text(case_def.get("summary"))
        and isinstance(incident_window, dict)
        and safe_text(incident_window.get("label"))
        and isinstance(questions, list)
        and any(
            isinstance(question, dict)
            and safe_text(question.get("question_id"))
            and safe_text(question.get("prompt"))
            for question in questions
        )
    )


def build_import_case_defs(seed_map: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    builtin_cases = explainer_export.case_defs_by_id()
    ordered_ids = [safe_text(case_def.get("case_id")) for case_def in explainer_export.CASE_DEFS if safe_text(case_def.get("case_id"))]
    extra_ids = sorted(case_id for case_id in seed_map.keys() if case_id not in builtin_cases)

    imported: list[dict[str, Any]] = []
    skipped: list[str] = []
    for case_id in ordered_ids + extra_ids:
        case_def = explainer_export.merge_case_def(builtin_cases.get(case_id), seed_map.get(case_id))
        if not has_required_case_metadata(case_def):
            skipped.append(case_id)
            continue
        imported.append(case_def)
    return imported, skipped


def clear_existing_rows(conn) -> None:
    conn.executescript(
        """
        DELETE FROM responsibility_explainer_structural_evidence_rows;
        DELETE FROM responsibility_explainer_structural_audit_targets;
        DELETE FROM responsibility_explainer_structural_risk_factors;
        DELETE FROM responsibility_explainer_responsibility_links;
        DELETE FROM responsibility_explainer_administrative_acts;
        DELETE FROM responsibility_explainer_official_findings;
        DELETE FROM responsibility_explainer_governing_rules;
        DELETE FROM responsibility_explainer_warning_timeline_events;
        DELETE FROM responsibility_explainer_warning_channels;
        DELETE FROM responsibility_explainer_normative_duties;
        DELETE FROM responsibility_explainer_questions;
        DELETE FROM responsibility_explainer_cases;
        """
    )


def insert_case(conn, *, case_def: dict[str, Any], sort_order: int, now_iso: str) -> None:
    incident_window = case_def.get("incident_window") or {}
    conn.execute(
        """
        INSERT INTO responsibility_explainer_cases(
          case_id,
          title,
          short_label,
          summary,
          current_scope_note,
          geography,
          incident_window_label,
          incident_start_date,
          incident_end_date,
          initiative_ids_json,
          known_gaps_json,
          next_lanes_json,
          sort_order,
          is_active,
          raw_payload_json,
          created_at,
          updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
        """,
        (
            safe_text(case_def.get("case_id")),
            safe_text(case_def.get("title")),
            safe_text(case_def.get("short_label")),
            safe_text(case_def.get("summary")),
            safe_text(case_def.get("current_scope_note")),
            safe_text(case_def.get("geography")),
            safe_text(incident_window.get("label")),
            safe_text(incident_window.get("start_date")),
            safe_text(incident_window.get("end_date")),
            json.dumps(clean_text_list(case_def.get("initiative_ids")), ensure_ascii=True),
            json.dumps(clean_text_list(case_def.get("known_gaps")), ensure_ascii=True),
            json.dumps(clean_text_list(case_def.get("next_lanes")), ensure_ascii=True),
            int(sort_order),
            json.dumps(case_def, ensure_ascii=True),
            now_iso,
            now_iso,
        ),
    )


def import_seed(conn, *, case_defs: list[dict[str, Any]], seed_map: dict[str, dict[str, Any]], snapshot_date: str) -> dict[str, Any]:
    now_iso = now_utc_iso()
    clear_existing_rows(conn)

    counts: dict[str, int] = {
        "cases_total": 0,
        "questions_total": 0,
        "normative_duties_total": 0,
        "warning_channels_total": 0,
        "warning_timeline_events_total": 0,
        "governing_rules_total": 0,
        "official_findings_total": 0,
        "administrative_acts_total": 0,
        "responsibility_links_total": 0,
        "structural_risk_factors_total": 0,
        "structural_audit_targets_total": 0,
        "structural_evidence_rows_total": 0,
    }

    for sort_order, case_def in enumerate(case_defs, start=1):
        case_id = safe_text(case_def.get("case_id"))
        case_seed = seed_map.get(case_id)
        insert_case(conn, case_def=case_def, sort_order=sort_order, now_iso=now_iso)
        counts["cases_total"] += 1

        for question_order, question in enumerate(case_def.get("questions") or [], start=1):
            cleaned = explainer_export.clean_question_row(question) if isinstance(question, dict) else {}
            if not safe_text(cleaned.get("question_id")) or not safe_text(cleaned.get("prompt")):
                continue
            conn.execute(
                """
                INSERT INTO responsibility_explainer_questions(
                  case_question_pk,
                  case_id,
                  question_id,
                  category,
                  prompt,
                  support_rule,
                  next_evidence_needed_json,
                  question_order,
                  raw_payload_json,
                  created_at,
                  updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{case_id}:{cleaned['question_id']}",
                    case_id,
                    cleaned["question_id"],
                    safe_text(cleaned.get("category")),
                    safe_text(cleaned.get("prompt")),
                    safe_text(cleaned.get("support_rule")),
                    json.dumps(clean_text_list(cleaned.get("next_evidence_needed")), ensure_ascii=True),
                    int(question_order),
                    json.dumps(cleaned, ensure_ascii=True),
                    now_iso,
                    now_iso,
                ),
            )
            counts["questions_total"] += 1

        for duty_order, row in enumerate(explainer_export.load_normative_duties(case_seed), start=1):
            conn.execute(
                """
                INSERT INTO responsibility_explainer_normative_duties(
                  case_duty_pk,
                  case_id,
                  duty_id,
                  category,
                  actor,
                  actor_scope,
                  duty_summary,
                  why_it_matters,
                  source_title,
                  source_url,
                  source_locator,
                  source_note,
                  duty_order,
                  raw_payload_json,
                  created_at,
                  updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{case_id}:{safe_text(row.get('duty_id'))}",
                    case_id,
                    safe_text(row.get("duty_id")),
                    safe_text(row.get("category")),
                    safe_text(row.get("actor")),
                    safe_text(row.get("actor_scope")),
                    safe_text(row.get("duty_summary")),
                    safe_text(row.get("why_it_matters")),
                    safe_text(row.get("source_title")),
                    safe_text(row.get("source_url")),
                    safe_text(row.get("source_locator")),
                    safe_text(row.get("source_note")),
                    int(duty_order),
                    json.dumps(row, ensure_ascii=True),
                    now_iso,
                    now_iso,
                ),
            )
            counts["normative_duties_total"] += 1

        for channel_order, row in enumerate(explainer_export.load_warning_channels(case_seed), start=1):
            conn.execute(
                """
                INSERT INTO responsibility_explainer_warning_channels(
                  case_channel_pk,
                  case_id,
                  channel_id,
                  channel_name,
                  operator,
                  scope,
                  signal_summary,
                  why_next,
                  source_title,
                  source_url,
                  source_note,
                  channel_order,
                  raw_payload_json,
                  created_at,
                  updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{case_id}:{safe_text(row.get('channel_id'))}",
                    case_id,
                    safe_text(row.get("channel_id")),
                    safe_text(row.get("channel_name")),
                    safe_text(row.get("operator")),
                    safe_text(row.get("scope")),
                    safe_text(row.get("signal_summary")),
                    safe_text(row.get("why_next")),
                    safe_text(row.get("source_title")),
                    safe_text(row.get("source_url")),
                    safe_text(row.get("source_note")),
                    int(channel_order),
                    json.dumps(row, ensure_ascii=True),
                    now_iso,
                    now_iso,
                ),
            )
            counts["warning_channels_total"] += 1

        for event_order, row in enumerate(explainer_export.load_warning_timeline_events(case_seed), start=1):
            conn.execute(
                """
                INSERT INTO responsibility_explainer_warning_timeline_events(
                  case_timeline_event_pk,
                  case_id,
                  event_id,
                  channel_id,
                  channel_name,
                  operator,
                  event_time,
                  event_precision,
                  signal_level,
                  event_summary,
                  why_it_matters,
                  source_title,
                  source_url,
                  source_locator,
                  source_note,
                  event_order,
                  raw_payload_json,
                  created_at,
                  updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{case_id}:{safe_text(row.get('event_id'))}",
                    case_id,
                    safe_text(row.get("event_id")),
                    safe_text(row.get("channel_id")),
                    safe_text(row.get("channel_name")),
                    safe_text(row.get("operator")),
                    safe_text(row.get("event_time")),
                    safe_text(row.get("event_precision")),
                    safe_text(row.get("signal_level")),
                    safe_text(row.get("event_summary")),
                    safe_text(row.get("why_it_matters")),
                    safe_text(row.get("source_title")),
                    safe_text(row.get("source_url")),
                    safe_text(row.get("source_locator")),
                    safe_text(row.get("source_note")),
                    int(event_order),
                    json.dumps(row, ensure_ascii=True),
                    now_iso,
                    now_iso,
                ),
            )
            counts["warning_timeline_events_total"] += 1

        for rule_order, row in enumerate(explainer_export.load_governing_rules(case_seed), start=1):
            conn.execute(
                """
                INSERT INTO responsibility_explainer_governing_rules(
                  case_rule_pk,
                  case_id,
                  rule_id,
                  rule_kind,
                  title,
                  duty_summary,
                  exposure_mechanism,
                  source_title,
                  source_url,
                  source_locator,
                  source_note,
                  rule_order,
                  raw_payload_json,
                  created_at,
                  updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{case_id}:{safe_text(row.get('rule_id'))}",
                    case_id,
                    safe_text(row.get("rule_id")),
                    safe_text(row.get("rule_kind")),
                    safe_text(row.get("title")),
                    safe_text(row.get("duty_summary")),
                    safe_text(row.get("exposure_mechanism")),
                    safe_text(row.get("source_title")),
                    safe_text(row.get("source_url")),
                    safe_text(row.get("source_locator")),
                    safe_text(row.get("source_note")),
                    int(rule_order),
                    json.dumps(row, ensure_ascii=True),
                    now_iso,
                    now_iso,
                ),
            )
            counts["governing_rules_total"] += 1

        for finding_order, row in enumerate(explainer_export.load_official_findings(case_seed), start=1):
            conn.execute(
                """
                INSERT INTO responsibility_explainer_official_findings(
                  case_finding_pk,
                  case_id,
                  finding_id,
                  category,
                  entity_name,
                  finding_date,
                  finding_summary,
                  accountability_implication,
                  source_title,
                  source_url,
                  source_locator,
                  source_note,
                  finding_order,
                  raw_payload_json,
                  created_at,
                  updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{case_id}:{safe_text(row.get('finding_id'))}",
                    case_id,
                    safe_text(row.get("finding_id")),
                    safe_text(row.get("category")),
                    safe_text(row.get("entity_name")),
                    safe_text(row.get("finding_date")),
                    safe_text(row.get("finding_summary")),
                    safe_text(row.get("accountability_implication")),
                    safe_text(row.get("source_title")),
                    safe_text(row.get("source_url")),
                    safe_text(row.get("source_locator")),
                    safe_text(row.get("source_note")),
                    int(finding_order),
                    json.dumps(row, ensure_ascii=True),
                    now_iso,
                    now_iso,
                ),
            )
            counts["official_findings_total"] += 1

        for act_order, row in enumerate(explainer_export.load_administrative_acts(case_seed), start=1):
            conn.execute(
                """
                INSERT INTO responsibility_explainer_administrative_acts(
                  case_act_pk,
                  case_id,
                  act_id,
                  act_type,
                  entity_name,
                  act_date,
                  status,
                  act_summary,
                  accountability_implication,
                  source_title,
                  source_url,
                  source_locator,
                  source_note,
                  act_order,
                  raw_payload_json,
                  created_at,
                  updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{case_id}:{safe_text(row.get('act_id'))}",
                    case_id,
                    safe_text(row.get("act_id")),
                    safe_text(row.get("act_type")),
                    safe_text(row.get("entity_name")),
                    safe_text(row.get("act_date")),
                    safe_text(row.get("status")),
                    safe_text(row.get("act_summary")),
                    safe_text(row.get("accountability_implication")),
                    safe_text(row.get("source_title")),
                    safe_text(row.get("source_url")),
                    safe_text(row.get("source_locator")),
                    safe_text(row.get("source_note")),
                    int(act_order),
                    json.dumps(row, ensure_ascii=True),
                    now_iso,
                    now_iso,
                ),
            )
            counts["administrative_acts_total"] += 1

        for link_order, row in enumerate(explainer_export.load_responsibility_links(case_seed), start=1):
            conn.execute(
                """
                INSERT INTO responsibility_explainer_responsibility_links(
                  case_link_pk,
                  case_id,
                  link_id,
                  actor,
                  actor_scope,
                  linked_object_type,
                  linked_object_id,
                  role_in_chain,
                  obligation_basis,
                  accountability_question,
                  source_title,
                  source_url,
                  source_locator,
                  source_note,
                  link_order,
                  raw_payload_json,
                  created_at,
                  updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{case_id}:{safe_text(row.get('link_id'))}",
                    case_id,
                    safe_text(row.get("link_id")),
                    safe_text(row.get("actor")),
                    safe_text(row.get("actor_scope")),
                    safe_text(row.get("linked_object_type")),
                    safe_text(row.get("linked_object_id")),
                    safe_text(row.get("role_in_chain")),
                    safe_text(row.get("obligation_basis")),
                    safe_text(row.get("accountability_question")),
                    safe_text(row.get("source_title")),
                    safe_text(row.get("source_url")),
                    safe_text(row.get("source_locator")),
                    safe_text(row.get("source_note")),
                    int(link_order),
                    json.dumps(row, ensure_ascii=True),
                    now_iso,
                    now_iso,
                ),
            )
            counts["responsibility_links_total"] += 1

        for factor_order, row in enumerate(explainer_export.load_structural_risk_factors(case_seed), start=1):
            conn.execute(
                """
                INSERT INTO responsibility_explainer_structural_risk_factors(
                  case_factor_pk,
                  case_id,
                  factor_id,
                  category,
                  title,
                  risk_mechanism,
                  accountability_focus,
                  source_title,
                  source_url,
                  source_locator,
                  source_note,
                  factor_order,
                  raw_payload_json,
                  created_at,
                  updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{case_id}:{safe_text(row.get('factor_id'))}",
                    case_id,
                    safe_text(row.get("factor_id")),
                    safe_text(row.get("category")),
                    safe_text(row.get("title")),
                    safe_text(row.get("risk_mechanism")),
                    safe_text(row.get("accountability_focus")),
                    safe_text(row.get("source_title")),
                    safe_text(row.get("source_url")),
                    safe_text(row.get("source_locator")),
                    safe_text(row.get("source_note")),
                    int(factor_order),
                    json.dumps(row, ensure_ascii=True),
                    now_iso,
                    now_iso,
                ),
            )
            counts["structural_risk_factors_total"] += 1

        for target_order, row in enumerate(explainer_export.load_structural_audit_targets(case_seed), start=1):
            conn.execute(
                """
                INSERT INTO responsibility_explainer_structural_audit_targets(
                  case_target_pk,
                  case_id,
                  target_id,
                  category,
                  title,
                  geography,
                  why_priority,
                  audit_question,
                  documents_to_audit_json,
                  authority_chain,
                  next_join_needed,
                  source_title,
                  source_url,
                  source_locator,
                  source_note,
                  target_order,
                  raw_payload_json,
                  created_at,
                  updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{case_id}:{safe_text(row.get('target_id'))}",
                    case_id,
                    safe_text(row.get("target_id")),
                    safe_text(row.get("category")),
                    safe_text(row.get("title")),
                    safe_text(row.get("geography")),
                    safe_text(row.get("why_priority")),
                    safe_text(row.get("audit_question")),
                    json.dumps(clean_text_list(row.get("documents_to_audit")), ensure_ascii=True),
                    safe_text(row.get("authority_chain")),
                    safe_text(row.get("next_join_needed")),
                    safe_text(row.get("source_title")),
                    safe_text(row.get("source_url")),
                    safe_text(row.get("source_locator")),
                    safe_text(row.get("source_note")),
                    int(target_order),
                    json.dumps(row, ensure_ascii=True),
                    now_iso,
                    now_iso,
                ),
            )
            counts["structural_audit_targets_total"] += 1

        for evidence_order, row in enumerate(explainer_export.load_structural_evidence_rows(case_seed), start=1):
            conn.execute(
                """
                INSERT INTO responsibility_explainer_structural_evidence_rows(
                  case_evidence_pk,
                  case_id,
                  evidence_id,
                  target_id,
                  entity_name,
                  signal_type,
                  certainty,
                  signal_title,
                  pre_dana_reading,
                  why_it_matters,
                  source_title,
                  source_url,
                  source_locator,
                  source_note,
                  evidence_order,
                  raw_payload_json,
                  created_at,
                  updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{case_id}:{safe_text(row.get('evidence_id'))}",
                    case_id,
                    safe_text(row.get("evidence_id")),
                    safe_text(row.get("target_id")),
                    safe_text(row.get("entity_name")),
                    safe_text(row.get("signal_type")),
                    safe_text(row.get("certainty")),
                    safe_text(row.get("signal_title")),
                    safe_text(row.get("pre_dana_reading")),
                    safe_text(row.get("why_it_matters")),
                    safe_text(row.get("source_title")),
                    safe_text(row.get("source_url")),
                    safe_text(row.get("source_locator")),
                    safe_text(row.get("source_note")),
                    int(evidence_order),
                    json.dumps(row, ensure_ascii=True),
                    now_iso,
                    now_iso,
                ),
            )
            counts["structural_evidence_rows_total"] += 1

    conn.commit()
    return {
        "status": "ok",
        "snapshot_date": snapshot_date,
        "counts": counts,
        "generated_at": now_iso,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import responsibility explainer seed into normalized SQLite tables")
    parser.add_argument("--db", required=True)
    parser.add_argument("--seed", default=str(DEFAULT_SEED))
    parser.add_argument("--snapshot-date", default=today_utc_date())
    parser.add_argument("--out", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    seed_path = Path(args.seed)
    db_path = Path(args.db)
    schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"

    seed_map = explainer_export.load_case_seed_map(seed_path)
    case_defs, skipped_case_ids = build_import_case_defs(seed_map)

    conn = open_db(db_path)
    try:
        apply_schema(conn, schema_path)
        report = import_seed(
            conn,
            case_defs=case_defs,
            seed_map=seed_map,
            snapshot_date=str(args.snapshot_date),
        )
    finally:
        conn.close()

    payload = {
        "generated_at": now_utc_iso(),
        "db_path": str(db_path),
        "seed_path": str(seed_path),
        "seed_cases_total": len(seed_map),
        "import_cases_total": len(case_defs),
        "skipped_case_ids": skipped_case_ids,
        "import": report,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if safe_text(args.out):
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
