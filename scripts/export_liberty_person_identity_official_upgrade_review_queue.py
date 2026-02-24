#!/usr/bin/env python3
"""Export review queue to upgrade liberty person identity aliases to official evidence."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import open_db
from scripts.report_liberty_person_identity_resolution_queue import build_report


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _canonical_alias(v: Any) -> str:
    return _norm(v).lower()


def _source_record_lookup_key(source_id: Any, source_record_id: Any) -> tuple[str, str]:
    return (_norm(source_id).lower(), _norm(source_record_id).lower())


def _classify_actionability(actor_person_name: Any, person_full_name: Any) -> tuple[str, str]:
    actor_norm = _canonical_alias(actor_person_name)
    person_norm = _canonical_alias(person_full_name)
    if actor_norm.startswith("persona seed "):
        return ("likely_not_actionable_seed_placeholder", "actor_person_name_seed_prefix")
    if person_norm.startswith("persona seed "):
        return ("likely_not_actionable_seed_placeholder", "person_full_name_seed_prefix")
    return ("actionable", "")


def _load_source_record_lookup(conn: Any) -> dict[tuple[str, str], str]:
    rows = conn.execute(
        """
        SELECT
          TRIM(COALESCE(source_id, '')) AS source_id,
          TRIM(COALESCE(source_record_id, '')) AS source_record_id,
          COALESCE(source_record_pk, 0) AS source_record_pk
        FROM source_records
        WHERE TRIM(COALESCE(source_id, '')) <> ''
          AND TRIM(COALESCE(source_record_id, '')) <> ''
          AND COALESCE(source_record_pk, 0) >= 1
        """
    ).fetchall()
    lookup: dict[tuple[str, str], str] = {}
    for row in rows:
        lookup[_source_record_lookup_key(row["source_id"], row["source_record_id"])] = _norm(row["source_record_pk"])
    return lookup


def _read_seed(seed_path: Path) -> dict[str, Any]:
    raw = json.loads(seed_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("seed root must be object")
    return raw


def _seed_mapping_index(seed_doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mappings = seed_doc.get("mappings")
    if not isinstance(mappings, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in mappings:
        if not isinstance(row, dict):
            continue
        alias = _canonical_alias(row.get("actor_person_name"))
        if not alias:
            continue
        out[alias] = row
    return out


def _init_gap_state(actor_person_name: str) -> dict[str, Any]:
    return {
        "actor_person_name": actor_person_name,
        "person_name": "",
        "gap_flags": set(),
        "queue_keys": set(),
        "edges_total": 0,
        "fragments_total": 0,
        "first_evidence_date": "",
        "last_evidence_date": "",
        "source_kind_hint": "",
    }


def _min_date(existing: str, candidate: str) -> str:
    ex = _norm(existing)
    ca = _norm(candidate)
    if not ex:
        return ca
    if not ca:
        return ex
    return ca if ca < ex else ex


def _max_date(existing: str, candidate: str) -> str:
    ex = _norm(existing)
    ca = _norm(candidate)
    if not ex:
        return ca
    if not ca:
        return ex
    return ca if ca > ex else ex


def _merge_gap_row(
    gap_state: dict[str, Any],
    *,
    flag: str,
    queue_key: str,
    person_name: str,
    source_kind_hint: str,
    edges_total: Any,
    fragments_total: Any,
    first_evidence_date: Any,
    last_evidence_date: Any,
) -> None:
    gap_state["gap_flags"].add(flag)
    if _norm(queue_key):
        gap_state["queue_keys"].add(_norm(queue_key))
    if _norm(person_name):
        gap_state["person_name"] = _norm(person_name)
    if _norm(source_kind_hint):
        gap_state["source_kind_hint"] = _norm(source_kind_hint)
    gap_state["edges_total"] = max(int(gap_state["edges_total"] or 0), int(edges_total or 0))
    gap_state["fragments_total"] = max(int(gap_state["fragments_total"] or 0), int(fragments_total or 0))
    gap_state["first_evidence_date"] = _min_date(
        _norm(gap_state.get("first_evidence_date")),
        _norm(first_evidence_date),
    )
    gap_state["last_evidence_date"] = _max_date(
        _norm(gap_state.get("last_evidence_date")),
        _norm(last_evidence_date),
    )


def build_review_rows(
    *,
    report_doc: dict[str, Any],
    seed_doc: dict[str, Any],
    source_record_lookup: dict[tuple[str, str], str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    seed_index = _seed_mapping_index(seed_doc)
    gap_map: dict[str, dict[str, Any]] = {}

    for row in report_doc.get("manual_alias_upgrade_queue_rows", []):
        if not isinstance(row, dict):
            continue
        actor_person_name = _norm(row.get("actor_person_name"))
        alias = _canonical_alias(actor_person_name)
        if not alias:
            continue
        state = gap_map.get(alias)
        if state is None:
            state = _init_gap_state(actor_person_name)
            gap_map[alias] = state
        _merge_gap_row(
            state,
            flag="manual_upgrade",
            queue_key=_norm(row.get("queue_key")),
            person_name=_norm(row.get("person_name")),
            source_kind_hint="official_nombramiento",
            edges_total=row.get("edges_total"),
            fragments_total=row.get("fragments_total"),
            first_evidence_date=row.get("first_evidence_date"),
            last_evidence_date=row.get("last_evidence_date"),
        )

    for row in report_doc.get("official_alias_evidence_upgrade_queue_rows", []):
        if not isinstance(row, dict):
            continue
        actor_person_name = _norm(row.get("actor_person_name"))
        alias = _canonical_alias(actor_person_name)
        if not alias:
            continue
        state = gap_map.get(alias)
        if state is None:
            state = _init_gap_state(actor_person_name)
            gap_map[alias] = state
        _merge_gap_row(
            state,
            flag="official_evidence_gap",
            queue_key=_norm(row.get("queue_key")),
            person_name=_norm(row.get("person_name")),
            source_kind_hint=_norm(row.get("source_kind")),
            edges_total=row.get("edges_total"),
            fragments_total=row.get("fragments_total"),
            first_evidence_date=row.get("first_evidence_date"),
            last_evidence_date=row.get("last_evidence_date"),
        )

    for row in report_doc.get("official_alias_source_record_upgrade_queue_rows", []):
        if not isinstance(row, dict):
            continue
        actor_person_name = _norm(row.get("actor_person_name"))
        alias = _canonical_alias(actor_person_name)
        if not alias:
            continue
        state = gap_map.get(alias)
        if state is None:
            state = _init_gap_state(actor_person_name)
            gap_map[alias] = state
        _merge_gap_row(
            state,
            flag="official_source_record_gap",
            queue_key=_norm(row.get("queue_key")),
            person_name=_norm(row.get("person_name")),
            source_kind_hint=_norm(row.get("source_kind")),
            edges_total=row.get("edges_total"),
            fragments_total=row.get("fragments_total"),
            first_evidence_date=row.get("first_evidence_date"),
            last_evidence_date=row.get("last_evidence_date"),
        )

    rows: list[dict[str, Any]] = []
    missing_seed_mapping_total = 0
    source_record_pk_lookup_keys_total = 0
    source_record_pk_lookup_prefilled_total = 0
    source_record_pk_lookup_miss_total = 0
    actionable_rows_total = 0
    likely_not_actionable_rows_total = 0
    for alias, state in sorted(
        gap_map.items(),
        key=lambda it: (-int(it[1].get("edges_total", 0)), _norm(it[0])),
    ):
        mapping = seed_index.get(alias)
        if mapping is None:
            missing_seed_mapping_total += 1
            mapping = {}
        current_source_kind = _norm(mapping.get("source_kind")) or "manual_seed"
        proposed_source_kind = _norm(mapping.get("source_kind")) or _norm(state.get("source_kind_hint")) or "official_nombramiento"
        if current_source_kind == "manual_seed" and "manual_upgrade" in state.get("gap_flags", set()):
            proposed_source_kind = "official_nombramiento"
        gap_flags = sorted({str(v) for v in state.get("gap_flags", set()) if _norm(v)})
        queue_keys = sorted({str(v) for v in state.get("queue_keys", set()) if _norm(v)})
        person_full_name = _norm(mapping.get("person_full_name")) or _norm(state.get("person_name"))
        actionability, actionability_reason = _classify_actionability(state.get("actor_person_name"), person_full_name)
        if actionability == "actionable":
            actionable_rows_total += 1
        else:
            likely_not_actionable_rows_total += 1
        source_id = _norm(mapping.get("source_id"))
        source_record_id = _norm(mapping.get("source_record_id"))
        source_record_pk = _norm(mapping.get("source_record_pk"))
        source_record_pk_lookup_status = "not_applicable"
        if source_record_pk:
            source_record_pk_lookup_status = "existing"
        elif source_id and source_record_id:
            source_record_pk_lookup_keys_total += 1
            if source_record_lookup is not None:
                resolved_source_record_pk = _norm(
                    source_record_lookup.get(_source_record_lookup_key(source_id, source_record_id))
                )
                if resolved_source_record_pk:
                    source_record_pk = resolved_source_record_pk
                    source_record_pk_lookup_status = "prefilled_from_db"
                    source_record_pk_lookup_prefilled_total += 1
                else:
                    source_record_pk_lookup_status = "lookup_miss"
                    source_record_pk_lookup_miss_total += 1
            else:
                source_record_pk_lookup_status = "lookup_not_loaded"
        rows.append(
            {
                "actor_person_name": _norm(state.get("actor_person_name")),
                "person_full_name": person_full_name,
                "canonical_alias": alias,
                "queue_keys_csv": ", ".join(queue_keys),
                "gap_flags_csv": ", ".join(gap_flags),
                "edges_total": int(state.get("edges_total") or 0),
                "fragments_total": int(state.get("fragments_total") or 0),
                "first_evidence_date": _norm(state.get("first_evidence_date")),
                "last_evidence_date": _norm(state.get("last_evidence_date")),
                "current_source_kind": current_source_kind,
                "proposed_source_kind": proposed_source_kind,
                "source_url": _norm(mapping.get("source_url")),
                "evidence_date": _norm(mapping.get("evidence_date")),
                "evidence_quote": _norm(mapping.get("evidence_quote")),
                "source_id": source_id,
                "source_record_id": source_record_id,
                "source_record_pk": source_record_pk,
                "source_record_pk_lookup_status": source_record_pk_lookup_status,
                "actionability": actionability,
                "actionability_reason": actionability_reason,
                "confidence": _norm(mapping.get("confidence")),
                "note": _norm(mapping.get("note")),
                "decision": "",
                "review_note": "",
            }
        )
    summary = {
        "rows_total": len(rows),
        "manual_upgrade_rows_total": sum(1 for r in rows if "manual_upgrade" in _norm(r.get("gap_flags_csv")).split(", ")),
        "official_evidence_gap_rows_total": sum(
            1 for r in rows if "official_evidence_gap" in _norm(r.get("gap_flags_csv")).split(", ")
        ),
        "official_source_record_gap_rows_total": sum(
            1 for r in rows if "official_source_record_gap" in _norm(r.get("gap_flags_csv")).split(", ")
        ),
        "missing_seed_mapping_total": int(missing_seed_mapping_total),
        "source_record_pk_lookup_keys_total": int(source_record_pk_lookup_keys_total),
        "source_record_pk_lookup_prefilled_total": int(source_record_pk_lookup_prefilled_total),
        "source_record_pk_lookup_miss_total": int(source_record_pk_lookup_miss_total),
        "actionable_rows_total": int(actionable_rows_total),
        "likely_not_actionable_rows_total": int(likely_not_actionable_rows_total),
    }
    return rows, summary


def write_review_csv(rows: list[dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "actor_person_name",
        "person_full_name",
        "canonical_alias",
        "queue_keys_csv",
        "gap_flags_csv",
        "edges_total",
        "fragments_total",
        "first_evidence_date",
        "last_evidence_date",
        "current_source_kind",
        "proposed_source_kind",
        "source_url",
        "evidence_date",
        "evidence_quote",
        "source_id",
        "source_record_id",
        "source_record_pk",
        "source_record_pk_lookup_status",
        "actionability",
        "actionability_reason",
        "confidence",
        "note",
        "decision",
        "review_note",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Export liberty person identity official upgrade review queue CSV")
    ap.add_argument("--db", required=True)
    ap.add_argument("--seed", default="etl/data/seeds/liberty_person_identity_resolution_seed_v1.json")
    ap.add_argument("--personal-confidence-min", type=float, default=0.55)
    ap.add_argument("--personal-max-causal-distance", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only-actionable", action="store_true")
    ap.add_argument("--strict-empty-actionable", action="store_true")
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary-out", default="")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    seed_path = Path(args.seed)
    db_path = Path(args.db)
    out_path = Path(args.out)
    summary_out_path = Path(args.summary_out) if _norm(args.summary_out) else None

    if not seed_path.exists():
        raise SystemExit(f"seed not found: {seed_path}")
    if not db_path.exists():
        raise SystemExit(f"db not found: {db_path}")

    seed_doc = _read_seed(seed_path)
    conn = open_db(db_path)
    try:
        source_record_lookup = _load_source_record_lookup(conn)
        report_doc = build_report(
            conn,
            personal_confidence_min=float(args.personal_confidence_min),
            personal_max_causal_distance=int(args.personal_max_causal_distance),
            limit=int(args.limit),
        )
    finally:
        conn.close()
    rows, summary = build_review_rows(
        report_doc=report_doc,
        seed_doc=seed_doc,
        source_record_lookup=source_record_lookup,
    )
    rows_export = rows
    if bool(args.only_actionable):
        rows_export = [r for r in rows if _norm(r.get("actionability")) == "actionable"]
    write_review_csv(rows_export, out_path)

    payload = {
        "seed_path": str(seed_path),
        "db_path": str(db_path),
        "out_path": str(out_path),
        "source_record_lookup_rows_total": int(len(source_record_lookup)),
        "only_actionable": bool(args.only_actionable),
        "strict_empty_actionable": bool(args.strict_empty_actionable),
        "rows_exported_total": int(len(rows_export)),
        "summary": summary,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if summary_out_path is not None:
        summary_out_path.parent.mkdir(parents=True, exist_ok=True)
        summary_out_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    if bool(args.strict_empty_actionable) and int(summary.get("actionable_rows_total", 0)) >= 1:
        raise SystemExit(4)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
