#!/usr/bin/env python3
"""Apply reviewed official-upgrade decisions to liberty person identity seed."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from etl.politicos_es.util import normalize_ws
from scripts.validate_liberty_person_identity_resolution_seed import SOURCE_KIND_MANUAL, validate_seed

ALLOWED_DECISIONS = {"approved", "ignored", "pending"}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return normalize_ws(str(v or ""))


def _canonical_alias(v: Any) -> str:
    return _norm(v).lower()


def _source_record_lookup_key(source_id: Any, source_record_id: Any) -> tuple[str, str]:
    return (_norm(source_id).lower(), _norm(source_record_id).lower())


def _load_source_record_lookup(db_path: Path) -> tuple[dict[tuple[str, str], str], dict[str, Any]]:
    if not db_path.exists():
        return {}, {
            "enabled": True,
            "db_path": str(db_path),
            "loaded": False,
            "rows_total": 0,
            "error": f"db not found: {db_path}",
        }
    lookup: dict[tuple[str, str], str] = {}
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
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
        for row in rows:
            key = _source_record_lookup_key(row["source_id"], row["source_record_id"])
            lookup[key] = _norm(row["source_record_pk"])
        return lookup, {
            "enabled": True,
            "db_path": str(db_path),
            "loaded": True,
            "rows_total": len(lookup),
            "error": "",
        }
    except Exception as exc:  # pragma: no cover - defensive for runtime db failures
        return {}, {
            "enabled": True,
            "db_path": str(db_path),
            "loaded": False,
            "rows_total": 0,
            "error": str(exc),
        }
    finally:
        try:
            conn.close()  # type: ignore[name-defined]
        except Exception:
            pass


def _read_seed(seed_path: Path) -> dict[str, Any]:
    raw = json.loads(seed_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("seed root must be object")
    mappings = raw.get("mappings")
    if not isinstance(mappings, list):
        raise ValueError("seed.mappings must be list")
    return raw


def _write_seed(seed_doc: dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(seed_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_csv_rows(in_path: Path) -> list[dict[str, str]]:
    with in_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return []
        return [{str(k or ""): str(v or "") for k, v in row.items()} for row in reader]


def apply_review_decisions(
    seed_doc: dict[str, Any],
    *,
    rows: list[dict[str, str]],
    source_record_lookup: dict[tuple[str, str], str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    mappings = seed_doc.get("mappings")
    assert isinstance(mappings, list)
    by_alias: dict[str, dict[str, Any]] = {}
    for mapping in mappings:
        if not isinstance(mapping, dict):
            continue
        alias = _canonical_alias(mapping.get("actor_person_name"))
        if alias:
            by_alias[alias] = mapping

    counts: dict[str, int] = {
        "rows_seen": len(rows),
        "rows_with_decision": 0,
        "approved_rows": 0,
        "ignored_rows": 0,
        "pending_rows": 0,
        "updated_rows": 0,
        "skipped_blank_decision": 0,
        "skipped_invalid_decision": 0,
        "skipped_missing_actor": 0,
        "skipped_actor_not_found": 0,
        "skipped_downgrade_prevented": 0,
        "invalid_confidence_values": 0,
        "source_record_pk_auto_resolved": 0,
        "source_record_pk_auto_resolve_missed": 0,
        "source_record_pk_auto_resolve_skipped_missing_keys": 0,
    }
    failures: list[str] = []

    for row in rows:
        decision = _norm(row.get("decision")).lower()
        if not decision:
            counts["skipped_blank_decision"] += 1
            continue
        if decision not in ALLOWED_DECISIONS:
            counts["skipped_invalid_decision"] += 1
            continue
        counts["rows_with_decision"] += 1
        if decision == "ignored":
            counts["ignored_rows"] += 1
            continue
        if decision == "pending":
            counts["pending_rows"] += 1
            continue
        counts["approved_rows"] += 1

        actor_person_name = _norm(row.get("actor_person_name"))
        alias = _canonical_alias(actor_person_name)
        if not alias:
            counts["skipped_missing_actor"] += 1
            continue
        mapping = by_alias.get(alias)
        if mapping is None:
            counts["skipped_actor_not_found"] += 1
            continue

        current_source_kind = _norm(mapping.get("source_kind")) or SOURCE_KIND_MANUAL
        proposed_source_kind = _norm(row.get("proposed_source_kind")) or current_source_kind
        if current_source_kind != SOURCE_KIND_MANUAL and proposed_source_kind == SOURCE_KIND_MANUAL:
            counts["skipped_downgrade_prevented"] += 1
            continue

        changed = False
        if proposed_source_kind and proposed_source_kind != _norm(mapping.get("source_kind")):
            mapping["source_kind"] = proposed_source_kind
            changed = True

        person_full_name = _norm(row.get("person_full_name"))
        if person_full_name and person_full_name != _norm(mapping.get("person_full_name")):
            mapping["person_full_name"] = person_full_name
            changed = True

        for key in ("source_url", "evidence_date", "evidence_quote", "source_id", "source_record_id", "source_record_pk"):
            token = _norm(row.get(key))
            if token and token != _norm(mapping.get(key)):
                mapping[key] = token
                changed = True
        current_effective_source_kind = _norm(mapping.get("source_kind")) or SOURCE_KIND_MANUAL
        if current_effective_source_kind != SOURCE_KIND_MANUAL and not _norm(mapping.get("source_record_pk")):
            lookup_source_id = _norm(mapping.get("source_id"))
            lookup_source_record_id = _norm(mapping.get("source_record_id"))
            if not lookup_source_id or not lookup_source_record_id:
                counts["source_record_pk_auto_resolve_skipped_missing_keys"] += 1
            elif source_record_lookup is not None:
                resolved_source_record_pk = _norm(
                    source_record_lookup.get(_source_record_lookup_key(lookup_source_id, lookup_source_record_id))
                )
                if resolved_source_record_pk:
                    if resolved_source_record_pk != _norm(mapping.get("source_record_pk")):
                        mapping["source_record_pk"] = resolved_source_record_pk
                        changed = True
                    counts["source_record_pk_auto_resolved"] += 1
                else:
                    counts["source_record_pk_auto_resolve_missed"] += 1

        confidence_token = _norm(row.get("confidence"))
        if confidence_token:
            try:
                confidence_val = float(confidence_token)
                if not (0.0 <= confidence_val <= 1.0):
                    raise ValueError("confidence out of range")
            except Exception:
                counts["invalid_confidence_values"] += 1
                failures.append(f"invalid confidence for {actor_person_name!r}: {confidence_token!r}")
            else:
                if str(mapping.get("confidence", "")) != str(confidence_val):
                    mapping["confidence"] = confidence_val
                    changed = True

        review_note = _norm(row.get("review_note"))
        if review_note:
            current_note = _norm(mapping.get("note"))
            if current_note:
                merged_note = f"{current_note} | review:{review_note}"
            else:
                merged_note = f"review:{review_note}"
            if merged_note != _norm(mapping.get("note")):
                mapping["note"] = merged_note
                changed = True

        if changed:
            counts["updated_rows"] += 1

    seed_doc["generated_at"] = now_utc_iso()
    return seed_doc, {"counts": counts, "failures": failures}


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Apply official upgrade review decisions into liberty identity seed")
    ap.add_argument("--seed", default="etl/data/seeds/liberty_person_identity_resolution_seed_v1.json")
    ap.add_argument("--in", dest="in_file", required=True)
    ap.add_argument("--db", default="")
    ap.add_argument("--seed-out", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default="")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    seed_path = Path(args.seed)
    in_path = Path(args.in_file)
    db_path = Path(args.db) if _norm(args.db) else None
    seed_out_path = Path(args.seed_out) if _norm(args.seed_out) else seed_path
    out_path = Path(args.out) if _norm(args.out) else None

    if not seed_path.exists():
        raise SystemExit(f"seed not found: {seed_path}")
    if not in_path.exists():
        raise SystemExit(f"input csv not found: {in_path}")

    seed_doc = _read_seed(seed_path)
    rows = _read_csv_rows(in_path)
    source_record_lookup: dict[tuple[str, str], str] | None = None
    source_record_lookup_meta: dict[str, Any] = {"enabled": False, "db_path": "", "loaded": False, "rows_total": 0}
    if db_path is not None:
        source_record_lookup, source_record_lookup_meta = _load_source_record_lookup(db_path)
    updated_seed_doc, apply_meta = apply_review_decisions(
        seed_doc,
        rows=rows,
        source_record_lookup=source_record_lookup,
    )

    validation_report: dict[str, Any]
    with TemporaryDirectory() as td:
        candidate_path = Path(td) / "candidate_seed.json"
        _write_seed(updated_seed_doc, candidate_path)
        validation_report = validate_seed(candidate_path)

    payload = {
        "seed_path": str(seed_path),
        "seed_out_path": str(seed_out_path),
        "input_csv": str(in_path),
        "db_path": str(db_path) if db_path is not None else "",
        "dry_run": bool(args.dry_run),
        "apply": apply_meta,
        "source_record_lookup": source_record_lookup_meta,
        "validation": {
            "valid": bool(validation_report.get("valid")),
            "errors_count": int(validation_report.get("errors_count", 0)),
            "warnings_count": int(validation_report.get("warnings_count", 0)),
            "errors": list(validation_report.get("errors", [])),
            "warnings": list(validation_report.get("warnings", [])),
        },
    }

    if bool(validation_report.get("valid")) and not bool(args.dry_run):
        _write_seed(updated_seed_doc, seed_out_path)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if bool(validation_report.get("valid")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
