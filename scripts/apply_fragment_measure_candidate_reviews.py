#!/usr/bin/env python3
"""Apply fragment-level measure candidate review outputs from JSON files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db
from etl.politicos_es.util import normalize_ws, now_utc_iso, sha256_bytes, stable_json
from scripts.measure_scale_layer import (
    build_measure_normalized_key,
    cluster_id_from_normalized_key,
    cluster_slug_for_title,
    purge_fragment_measure_scale_layer,
)


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
ALLOWED_STATUS = {"resolved", "ignored", "pending"}
ALLOWED_EFFECT_TYPES = {"tax", "benefit", "obligation", "restriction", "sanction", "rights", "institutional", "competence", "unknown"}
ALLOWED_RISK_LEVELS = {"low", "medium", "high"}
ALLOWED_SUPPORT_SIDE = {"yes", "no", "mixed", "unknown"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Apply fragment-level measure candidate outputs")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--in-dir", required=True, help="Directory containing JSON result files")
    p.add_argument("--source-id", default="", help="Optional fragment source_id scope")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--out", default="", help="Optional JSON summary output")
    return p.parse_args()


def _norm(value: Any) -> str:
    return normalize_ws(str(value or ""))


def _list_json_files(path: Path) -> list[Path]:
    if not path.exists() or not path.is_dir():
        return []
    return sorted(p for p in path.iterdir() if p.is_file() and p.suffix.lower() == ".json")


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _load_json_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        values = raw
    else:
        text = _norm(raw)
        if not text:
            return []
        try:
            values = json.loads(text)
        except Exception:
            return []
    if not isinstance(values, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _norm(value)
        if not item or item.lower() in seen:
            continue
        seen.add(item.lower())
        out.append(item)
    return out


def _normalize_fragment_identifier(value: Any) -> str:
    text = _norm(value)
    if text.startswith("pfrag-") and ":" not in text:
        return "pfrag:" + text[len("pfrag-") :]
    return text


def _quote_lookup_key(value: Any) -> str:
    return _norm(value).strip("\"'“”`").lower()


def _resolve_evidence_fragment_id(
    *,
    raw_fragment_id: Any,
    raw_fragment_label: Any,
    quote: str,
    default_fragment_id: str,
    allowed_fragment_texts: dict[str, str],
    allowed_fragment_labels: dict[str, str],
) -> str:
    evidence_fragment_id = _normalize_fragment_identifier(raw_fragment_id) or default_fragment_id
    if evidence_fragment_id in allowed_fragment_texts:
        return evidence_fragment_id
    label_key = _norm(raw_fragment_label).lower()
    if label_key:
        label_matches = [
            fragment_id
            for fragment_id, fragment_label in allowed_fragment_labels.items()
            if label_key == fragment_label
        ]
        if len(label_matches) == 1:
            return label_matches[0]
    lookup_quote = _quote_lookup_key(quote)
    if not lookup_quote:
        return ""
    matches = [
        fragment_id
        for fragment_id, fragment_text in allowed_fragment_texts.items()
        if lookup_quote in fragment_text
    ]
    if len(matches) == 1:
        return matches[0]
    return ""


def _candidate_id(fragment_id: str, rank: int, measure_title: str) -> str:
    token = f"{_norm(fragment_id)}|{int(rank)}|{_norm(measure_title).lower()}"
    return "mcand:" + sha256_bytes(token.encode("utf-8"))[:32]


def _review_key(candidate_id: str, review_reason: str) -> str:
    token = f"{_norm(candidate_id)}|{_norm(review_reason)}"
    return "mreview:" + sha256_bytes(token.encode("utf-8"))[:32]


def _candidate_review_reason(*, risk_level: str, effect_type: str, primary_vote_event_ids: list[str]) -> str | None:
    if not primary_vote_event_ids:
        return "missing_vote_link"
    if _norm(risk_level).lower() == "high":
        return "high_risk"
    if _norm(effect_type).lower() == "unknown":
        return "low_confidence"
    return None


def apply_fragment_review_results(
    conn: Any,
    *,
    result_files: list[Path],
    source_id: str,
    dry_run: bool,
) -> dict[str, Any]:
    now_iso = now_utc_iso()
    files_seen = 0
    fragments_updated = 0
    candidates_written = 0
    clusters_written = 0
    candidate_reviews_written = 0
    skipped_invalid_json = 0
    skipped_missing_fragment = 0
    skipped_blank_status = 0
    skipped_invalid_status = 0
    skipped_source_mismatch = 0
    skipped_invalid_candidate = 0
    purge_summary: dict[str, Any] = {
        "fragment_ids_seen": 0,
        "candidates_deleted": 0,
        "clusters_deleted": 0,
    }

    fragment_status_rows: list[tuple[Any, ...]] = []
    fragment_ids_to_purge: list[str] = []
    candidate_rows: list[tuple[Any, ...]] = []
    cluster_rows: list[tuple[Any, ...]] = []
    link_rows: list[tuple[Any, ...]] = []
    review_rows: list[tuple[Any, ...]] = []

    for path in result_files:
        files_seen += 1
        payload = _load_json(path)
        if payload is None:
            skipped_invalid_json += 1
            continue

        fragment_id = _normalize_fragment_identifier(payload.get("task_id"))
        review_status = _norm(payload.get("review_status")).lower()
        if not fragment_id:
            skipped_missing_fragment += 1
            continue
        if not review_status:
            skipped_blank_status += 1
            continue
        if review_status not in ALLOWED_STATUS:
            skipped_invalid_status += 1
            continue

        fragment_row = conn.execute(
            """
            SELECT fragment_id, initiative_id, initiative_text_version_id, source_id
            FROM parl_text_fragments
            WHERE fragment_id = ?
            """,
            (fragment_id,),
        ).fetchone()
        if fragment_row is None:
            skipped_missing_fragment += 1
            continue
        if source_id and _norm(fragment_row["source_id"]) != _norm(source_id):
            skipped_source_mismatch += 1
            continue

        candidates = payload.get("candidates")
        if not isinstance(candidates, list):
            candidates = []
        if review_status == "resolved" and not candidates:
            skipped_invalid_candidate += 1
            continue

        allowed_fragment_rows = conn.execute(
            """
            SELECT fragment_id, fragment_text, fragment_label
            FROM parl_text_fragments
            WHERE initiative_text_version_id = ?
            """,
            (_norm(fragment_row["initiative_text_version_id"]),),
        ).fetchall()
        allowed_fragment_texts = {
            _norm(row["fragment_id"]): _quote_lookup_key(row["fragment_text"])
            for row in allowed_fragment_rows
            if _norm(row["fragment_id"])
        }
        allowed_fragment_labels = {
            _norm(row["fragment_id"]): _norm(row["fragment_label"]).lower()
            for row in allowed_fragment_rows
            if _norm(row["fragment_id"])
        }

        fragment_ids_to_purge.append(fragment_id)
        fragment_status_rows.append(
            (
                fragment_id,
                _norm(fragment_row["initiative_id"]),
                _norm(fragment_row["initiative_text_version_id"]),
                _norm(fragment_row["source_id"]),
                review_status,
                _norm(payload.get("review_note")) or None,
                stable_json(
                    {
                        "reviewer": _norm(payload.get("reviewer")),
                        "review_note": _norm(payload.get("review_note")),
                        "result_file": str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path),
                        "candidates_count": len(candidates),
                    }
                ),
                now_iso,
                now_iso,
            )
        )

        invalid_fragment = False
        for rank, item in enumerate(candidates, start=1):
            if not isinstance(item, dict):
                invalid_fragment = True
                break
            measure_title = _norm(item.get("measure_title"))
            citizen_summary = _norm(item.get("citizen_summary"))
            effect_type = _norm(item.get("effect_type")).lower()
            risk_level = _norm(item.get("risk_level")).lower()
            support_side = _norm(item.get("support_side")).lower() or "unknown"
            if (
                not measure_title
                or not citizen_summary
                or effect_type not in ALLOWED_EFFECT_TYPES
                or risk_level not in ALLOWED_RISK_LEVELS
                or support_side not in ALLOWED_SUPPORT_SIDE
            ):
                invalid_fragment = True
                break

            primary_vote_event_ids = _load_json_list(item.get("primary_vote_event_ids"))
            search_terms = _load_json_list(item.get("search_terms"))
            evidence = item.get("evidence")
            if not isinstance(evidence, list):
                invalid_fragment = True
                break
            evidence_rows: list[dict[str, Any]] = []
            for ev in evidence:
                if not isinstance(ev, dict):
                    invalid_fragment = True
                    break
                quote = _norm(ev.get("quote"))
                evidence_fragment_id = _resolve_evidence_fragment_id(
                    raw_fragment_id=ev.get("fragment_id"),
                    raw_fragment_label=ev.get("fragment_label"),
                    quote=quote,
                    default_fragment_id=fragment_id,
                    allowed_fragment_texts=allowed_fragment_texts,
                    allowed_fragment_labels=allowed_fragment_labels,
                )
                if not quote or not evidence_fragment_id:
                    invalid_fragment = True
                    break
                evidence_rows.append(
                    {
                        "quote": quote,
                        "fragment_id": evidence_fragment_id,
                        "fragment_label": _norm(ev.get("fragment_label")),
                    }
                )
            if invalid_fragment:
                break

            normalized_key = build_measure_normalized_key(
                measure_title=measure_title,
                effect_type=effect_type,
                policy_area=_norm(item.get("policy_area")),
                measure_kind=_norm(item.get("measure_kind")),
            )
            candidate_id = _candidate_id(fragment_id, rank, measure_title)
            cluster_id = cluster_id_from_normalized_key(normalized_key)
            cluster_slug = cluster_slug_for_title(measure_title, normalized_key)
            review_reason = _candidate_review_reason(
                risk_level=risk_level,
                effect_type=effect_type,
                primary_vote_event_ids=primary_vote_event_ids,
            )
            publish_status = "review_required" if review_reason else "candidate"
            candidate_rows.append(
                (
                    candidate_id,
                    _norm(fragment_row["initiative_id"]),
                    _norm(fragment_row["source_id"]),
                    _norm(fragment_row["initiative_text_version_id"]),
                    fragment_id,
                    "fragment_model",
                    "fragment_worker_v1",
                    effect_type,
                    risk_level,
                    measure_title,
                    citizen_summary,
                    normalized_key,
                    _norm(item.get("affected_groups")) or None,
                    _norm(item.get("policy_area")) or None,
                    _norm(item.get("measure_kind")) or None,
                    stable_json(search_terms),
                    stable_json(primary_vote_event_ids),
                    support_side,
                    stable_json(evidence_rows),
                    0.72,
                    "candidate",
                    stable_json(
                        {
                            "reviewer": _norm(payload.get("reviewer")),
                            "review_note": _norm(payload.get("review_note")),
                            "result_file": str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path),
                            "task_status": review_status,
                            "candidate_rank": rank,
                        }
                    ),
                    now_iso,
                    now_iso,
                )
            )
            cluster_rows.append(
                (
                    cluster_id,
                    cluster_slug,
                    measure_title,
                    citizen_summary,
                    normalized_key,
                    effect_type,
                    risk_level,
                    _norm(item.get("policy_area")) or None,
                    _norm(item.get("measure_kind")) or None,
                    stable_json([measure_title]),
                    stable_json([*search_terms, measure_title]),
                    0.72,
                    publish_status,
                    stable_json(
                        {
                            "source_fragment_ids": [fragment_id],
                            "source_candidate_origins": ["fragment_model"],
                        }
                    ),
                    now_iso,
                    now_iso,
                )
            )
            link_rows.append(
                (
                    candidate_id,
                    cluster_id,
                    "title_norm_exact",
                    0.72,
                    stable_json({"fragment_id": fragment_id}),
                    now_iso,
                    now_iso,
                )
            )
            if review_reason:
                review_rows.append(
                    (
                        _review_key(candidate_id, review_reason),
                        candidate_id,
                        cluster_id,
                        review_reason,
                        "pending",
                        _norm(payload.get("review_note")) or None,
                        stable_json({"fragment_id": fragment_id, "task_status": review_status}),
                        now_iso,
                        now_iso,
                    )
                )
        if invalid_fragment:
            skipped_invalid_candidate += 1
            fragment_status_rows.pop()
            fragment_ids_to_purge.pop()
            continue

    if not dry_run and fragment_status_rows:
        with conn:
            purge_summary = purge_fragment_measure_scale_layer(
                conn,
                fragment_ids=fragment_ids_to_purge,
                dry_run=False,
            )
            conn.executemany(
                """
                INSERT INTO parl_fragment_measure_reviews (
                  fragment_id, initiative_id, initiative_text_version_id, source_id, status, note,
                  raw_payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fragment_id) DO UPDATE SET
                  initiative_id = excluded.initiative_id,
                  initiative_text_version_id = excluded.initiative_text_version_id,
                  source_id = excluded.source_id,
                  status = excluded.status,
                  note = excluded.note,
                  raw_payload_json = excluded.raw_payload_json,
                  updated_at = excluded.updated_at
                """,
                fragment_status_rows,
            )
            if candidate_rows:
                conn.executemany(
                    """
                    INSERT INTO parl_measure_candidates (
                      measure_candidate_id, initiative_id, source_id, initiative_text_version_id, fragment_id,
                      candidate_origin, extraction_method, effect_type, risk_level, measure_title,
                      citizen_summary, normalized_key, affected_groups, policy_area, measure_kind,
                      search_terms_json, primary_vote_event_ids_json, support_side, evidence_json,
                      confidence, status, raw_payload_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(measure_candidate_id) DO UPDATE SET
                      initiative_id = excluded.initiative_id,
                      source_id = excluded.source_id,
                      initiative_text_version_id = excluded.initiative_text_version_id,
                      fragment_id = excluded.fragment_id,
                      candidate_origin = excluded.candidate_origin,
                      extraction_method = excluded.extraction_method,
                      effect_type = excluded.effect_type,
                      risk_level = excluded.risk_level,
                      measure_title = excluded.measure_title,
                      citizen_summary = excluded.citizen_summary,
                      normalized_key = excluded.normalized_key,
                      affected_groups = excluded.affected_groups,
                      policy_area = excluded.policy_area,
                      measure_kind = excluded.measure_kind,
                      search_terms_json = excluded.search_terms_json,
                      primary_vote_event_ids_json = excluded.primary_vote_event_ids_json,
                      support_side = excluded.support_side,
                      evidence_json = excluded.evidence_json,
                      confidence = excluded.confidence,
                      status = excluded.status,
                      raw_payload_json = excluded.raw_payload_json,
                      updated_at = excluded.updated_at
                    """,
                    candidate_rows,
                )
                conn.executemany(
                    """
                    INSERT INTO parl_measure_clusters (
                      measure_cluster_id, cluster_slug, canonical_title, canonical_summary, normalized_key,
                      effect_type, risk_level, policy_area, measure_kind, aliases_json, search_terms_json,
                      confidence, publish_status, raw_payload_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(measure_cluster_id) DO UPDATE SET
                      cluster_slug = excluded.cluster_slug,
                      canonical_title = COALESCE(parl_measure_clusters.canonical_title, excluded.canonical_title),
                      canonical_summary = COALESCE(parl_measure_clusters.canonical_summary, excluded.canonical_summary),
                      normalized_key = excluded.normalized_key,
                      effect_type = excluded.effect_type,
                      risk_level = CASE
                        WHEN parl_measure_clusters.risk_level = 'high' OR excluded.risk_level = 'high' THEN 'high'
                        WHEN parl_measure_clusters.risk_level = 'medium' OR excluded.risk_level = 'medium' THEN 'medium'
                        ELSE excluded.risk_level
                      END,
                      policy_area = COALESCE(parl_measure_clusters.policy_area, excluded.policy_area),
                      measure_kind = COALESCE(parl_measure_clusters.measure_kind, excluded.measure_kind),
                      aliases_json = excluded.aliases_json,
                      search_terms_json = excluded.search_terms_json,
                      confidence = CASE
                        WHEN parl_measure_clusters.confidence IS NULL THEN excluded.confidence
                        ELSE MAX(parl_measure_clusters.confidence, excluded.confidence)
                      END,
                      publish_status = CASE
                        WHEN parl_measure_clusters.publish_status = 'published' THEN parl_measure_clusters.publish_status
                        WHEN parl_measure_clusters.publish_status = 'review_required' OR excluded.publish_status = 'review_required' THEN 'review_required'
                        ELSE excluded.publish_status
                      END,
                      raw_payload_json = excluded.raw_payload_json,
                      updated_at = excluded.updated_at
                    """,
                    cluster_rows,
                )
                conn.executemany(
                    """
                    INSERT INTO parl_measure_candidate_cluster_links (
                      measure_candidate_id, measure_cluster_id, link_method, confidence, is_primary,
                      raw_payload_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                    ON CONFLICT(measure_candidate_id, measure_cluster_id) DO UPDATE SET
                      link_method = excluded.link_method,
                      confidence = excluded.confidence,
                      is_primary = excluded.is_primary,
                      raw_payload_json = excluded.raw_payload_json,
                      updated_at = excluded.updated_at
                    """,
                    link_rows,
                )
            if review_rows:
                conn.executemany(
                    """
                    INSERT INTO parl_measure_candidate_reviews (
                      review_key, measure_candidate_id, measure_cluster_id, review_reason, status, note,
                      raw_payload_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(review_key) DO UPDATE SET
                      measure_candidate_id = excluded.measure_candidate_id,
                      measure_cluster_id = excluded.measure_cluster_id,
                      review_reason = excluded.review_reason,
                      status = excluded.status,
                      note = excluded.note,
                      raw_payload_json = excluded.raw_payload_json,
                      updated_at = excluded.updated_at
                    """,
                    review_rows,
                )

    fragments_updated = len(fragment_status_rows)
    candidates_written = len(candidate_rows)
    clusters_written = len(cluster_rows)
    candidate_reviews_written = len(review_rows)
    return {
        "source_id": _norm(source_id),
        "dry_run": bool(dry_run),
        "files_seen": int(files_seen),
        "fragments_updated": int(fragments_updated),
        "candidates_written": int(candidates_written),
        "clusters_written": int(clusters_written),
        "candidate_reviews_written": int(candidate_reviews_written),
        "skipped_invalid_json": int(skipped_invalid_json),
        "skipped_missing_fragment": int(skipped_missing_fragment),
        "skipped_blank_status": int(skipped_blank_status),
        "skipped_invalid_status": int(skipped_invalid_status),
        "skipped_source_mismatch": int(skipped_source_mismatch),
        "skipped_invalid_candidate": int(skipped_invalid_candidate),
        "purge_summary": purge_summary,
    }


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    in_dir = Path(args.in_dir)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 2
    if not in_dir.exists() or not in_dir.is_dir():
        print(f"ERROR: input directory not found: {in_dir}", file=sys.stderr)
        return 2

    with open_db(db_path) as conn:
        apply_schema(conn, DEFAULT_SCHEMA)
        result = apply_fragment_review_results(
            conn,
            result_files=_list_json_files(in_dir),
            source_id=_norm(args.source_id),
            dry_run=bool(args.dry_run),
        )

    if _norm(args.out):
        Path(args.out).write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
