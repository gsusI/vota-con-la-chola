"""Shared helpers for initiative-document extraction review workflows."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping

from etl.politicos_es.util import normalize_ws, now_utc_iso, stable_json


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_SOURCE_ID = "parl_initiative_docs"
ALLOWED_STATUS = {"resolved", "ignored", "pending"}
CSV_HEADERS = [
    "source_record_pk",
    "sample_initiative_id",
    "initiative_source_id",
    "initiative_title",
    "doc_format",
    "doc_kinds_csv",
    "initiatives_count",
    "doc_refs_count",
    "extractor_version",
    "subject_method",
    "confidence",
    "needs_review",
    "extracted_subject",
    "extracted_title",
    "extracted_excerpt",
    "source_url",
    "raw_path",
    "review_status",
    "final_subject",
    "final_title",
    "final_confidence",
    "review_note",
    "reviewer",
]

LABEL_STUDIO_CONFIG_XML = """<View>
  <Header value="Revision de extraccion semantica de documentos parlamentarios"/>
  <View style="display:flex; gap: 24px;">
    <View style="width: 58%;">
      <Text name="source_text" value="$review_context"/>
      <HyperText name="source_link" value="$source_link_html"/>
    </View>
    <View style="width: 42%;">
      <Choices name="review_status" toName="source_text" choice="single-radio" required="true">
        <Choice value="resolved"/>
        <Choice value="ignored"/>
        <Choice value="pending"/>
      </Choices>
      <TextArea name="final_subject" toName="source_text" rows="3" maxSubmissions="1" placeholder="Tema final"/>
      <TextArea name="final_title" toName="source_text" rows="3" maxSubmissions="1" placeholder="Titulo final"/>
      <Number name="final_confidence" toName="source_text" minimum="0" maximum="1" step="0.01"/>
      <TextArea name="review_note" toName="source_text" rows="4" maxSubmissions="1" placeholder="Nota de revision"/>
    </View>
  </View>
</View>
"""


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def fetch_review_rows(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    only_needs_review: bool,
    limit: int,
    offset: int,
) -> list[sqlite3.Row]:
    where = ["ex.source_id = ?"]
    params: list[object] = [str(source_id)]
    if bool(only_needs_review):
        where.append("ex.needs_review = 1")

    limit_sql = ""
    limit_i = max(0, int(limit or 0))
    offset_i = max(0, int(offset or 0))
    if limit_i > 0:
        limit_sql = "LIMIT ? OFFSET ?"
        params.extend([limit_i, offset_i])
    elif offset_i > 0:
        limit_sql = "LIMIT -1 OFFSET ?"
        params.append(offset_i)

    sql = f"""
    SELECT
      ex.source_record_pk,
      ex.sample_initiative_id,
      i.source_id AS initiative_source_id,
      i.title AS initiative_title,
      ex.doc_format,
      ex.doc_kinds_csv,
      ex.initiatives_count,
      ex.doc_refs_count,
      ex.extractor_version,
      json_extract(ex.analysis_payload_json, '$.subject_method') AS subject_method,
      ex.confidence,
      ex.needs_review,
      ex.extracted_subject,
      ex.extracted_title,
      ex.extracted_excerpt,
      td.source_url,
      td.raw_path
    FROM parl_initiative_doc_extractions ex
    LEFT JOIN parl_initiatives i ON i.initiative_id = ex.sample_initiative_id
    LEFT JOIN text_documents td ON td.source_record_pk = ex.source_record_pk AND td.source_id = ex.source_id
    WHERE {' AND '.join(where)}
    ORDER BY
      ex.needs_review DESC,
      ex.confidence ASC,
      ex.source_record_pk ASC
    {limit_sql}
    """
    return conn.execute(sql, params).fetchall()


def write_review_queue_csv(rows: list[sqlite3.Row], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(CSV_HEADERS)
        for row in rows:
            writer.writerow(
                [
                    str(row["source_record_pk"] or ""),
                    str(row["sample_initiative_id"] or ""),
                    str(row["initiative_source_id"] or ""),
                    str(row["initiative_title"] or ""),
                    str(row["doc_format"] or ""),
                    str(row["doc_kinds_csv"] or ""),
                    str(row["initiatives_count"] or ""),
                    str(row["doc_refs_count"] or ""),
                    str(row["extractor_version"] or ""),
                    str(row["subject_method"] or ""),
                    str(row["confidence"] or ""),
                    str(row["needs_review"] or ""),
                    str(row["extracted_subject"] or ""),
                    str(row["extracted_title"] or ""),
                    str(row["extracted_excerpt"] or ""),
                    str(row["source_url"] or ""),
                    str(row["raw_path"] or ""),
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            )
    return len(rows)


def _parse_float(raw: str) -> float | None:
    token = normalize_ws(raw)
    if not token:
        return None
    try:
        return float(token)
    except ValueError:
        return None


def _load_payload(raw: str | None) -> dict[str, Any]:
    token = normalize_ws(str(raw or ""))
    if not token:
        return {}
    try:
        obj = json.loads(token)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    return {}


def read_review_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        if reader.fieldnames is None:
            return []
        return [{str(k or ""): str(v or "") for k, v in row.items()} for row in reader]


def apply_review_decisions(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    rows: list[dict[str, str]],
    dry_run: bool,
) -> dict[str, Any]:
    now_iso = now_utc_iso()

    seen = 0
    decision_rows = 0
    skipped_blank_status = 0
    skipped_invalid_status = 0
    skipped_missing_pk = 0
    skipped_not_found = 0
    skipped_source_mismatch = 0
    invalid_confidence = 0
    failures: list[str] = []
    updates: list[tuple[Any, ...]] = []

    for row in rows:
        seen += 1
        pk_token = normalize_ws(row.get("source_record_pk", ""))
        if not pk_token:
            skipped_missing_pk += 1
            continue
        try:
            source_record_pk = int(pk_token)
        except ValueError:
            skipped_missing_pk += 1
            continue

        status = normalize_ws(row.get("review_status", "")).lower()
        if not status:
            skipped_blank_status += 1
            continue
        if status not in ALLOWED_STATUS:
            skipped_invalid_status += 1
            continue
        decision_rows += 1

        final_subject = normalize_ws(row.get("final_subject", ""))
        final_title = normalize_ws(row.get("final_title", ""))
        final_confidence = _parse_float(row.get("final_confidence", ""))
        reviewer = normalize_ws(row.get("reviewer", ""))
        review_note = normalize_ws(row.get("review_note", ""))

        if normalize_ws(row.get("final_confidence", "")) and final_confidence is None:
            invalid_confidence += 1

        current = conn.execute(
            """
            SELECT source_id, analysis_payload_json
            FROM parl_initiative_doc_extractions
            WHERE source_record_pk = ?
            """,
            (source_record_pk,),
        ).fetchone()
        if current is None:
            skipped_not_found += 1
            continue

        row_source_id = normalize_ws(str(current["source_id"] or ""))
        if source_id and row_source_id != source_id:
            skipped_source_mismatch += 1
            continue

        payload = _load_payload(str(current["analysis_payload_json"] or ""))
        review_event: dict[str, Any] = {
            "status": status,
            "reviewer": reviewer,
            "note": review_note,
            "reviewed_at": now_iso,
        }
        if final_subject:
            review_event["final_subject"] = final_subject
        if final_title:
            review_event["final_title"] = final_title
        if final_confidence is not None:
            review_event["final_confidence"] = final_confidence

        history = payload.get("review_history")
        if not isinstance(history, list):
            history = []
        history.append(review_event)

        payload["review_status"] = status
        payload["reviewed_at"] = now_iso
        if reviewer:
            payload["reviewer"] = reviewer
        if review_note:
            payload["review_note"] = review_note
        payload["review_history"] = history[-50:]
        needs_review = 1 if status == "pending" else 0

        updates.append(
            (
                final_subject or None,
                final_title or None,
                final_confidence,
                int(needs_review),
                stable_json(payload),
                now_iso,
                source_record_pk,
            )
        )

    if updates and not dry_run:
        with conn:
            conn.executemany(
                """
                UPDATE parl_initiative_doc_extractions
                SET
                  extracted_subject = CASE
                    WHEN ? IS NOT NULL AND TRIM(?) <> '' THEN ?
                    ELSE extracted_subject
                  END,
                  extracted_title = CASE
                    WHEN ? IS NOT NULL AND TRIM(?) <> '' THEN ?
                    ELSE extracted_title
                  END,
                  confidence = COALESCE(?, confidence),
                  needs_review = ?,
                  analysis_payload_json = ?,
                  updated_at = ?
                WHERE source_record_pk = ?
                """,
                [
                    (
                        update[0],
                        update[0],
                        update[0],
                        update[1],
                        update[1],
                        update[1],
                        update[2],
                        update[3],
                        update[4],
                        update[5],
                        update[6],
                    )
                    for update in updates
                ],
            )

    return {
        "source_id": source_id,
        "dry_run": bool(dry_run),
        "rows_seen": int(seen),
        "rows_with_decision": int(decision_rows),
        "updated": int(len(updates)),
        "skipped_blank_status": int(skipped_blank_status),
        "skipped_invalid_status": int(skipped_invalid_status),
        "skipped_missing_pk": int(skipped_missing_pk),
        "skipped_not_found": int(skipped_not_found),
        "skipped_source_mismatch": int(skipped_source_mismatch),
        "invalid_confidence_values": int(invalid_confidence),
        "failures": failures,
    }


def _row_to_dict(row: sqlite3.Row | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(row, sqlite3.Row):
        return {key: row[key] for key in row.keys()}
    return {str(key): value for key, value in row.items()}


def _review_context(row: Mapping[str, Any]) -> str:
    parts = [
        f"initiative_title: {normalize_ws(str(row.get('initiative_title') or ''))}",
        f"initiative_source_id: {normalize_ws(str(row.get('initiative_source_id') or ''))}",
        f"doc_format: {normalize_ws(str(row.get('doc_format') or ''))}",
        f"doc_kinds_csv: {normalize_ws(str(row.get('doc_kinds_csv') or ''))}",
        f"extractor_version: {normalize_ws(str(row.get('extractor_version') or ''))}",
        f"subject_method: {normalize_ws(str(row.get('subject_method') or ''))}",
        f"confidence: {normalize_ws(str(row.get('confidence') or ''))}",
        "",
        "current_extracted_subject:",
        normalize_ws(str(row.get("extracted_subject") or "")),
        "",
        "current_extracted_title:",
        normalize_ws(str(row.get("extracted_title") or "")),
        "",
        "excerpt:",
        normalize_ws(str(row.get("extracted_excerpt") or "")),
    ]
    return "\n".join(parts).strip()


def export_label_studio_tasks(rows: list[sqlite3.Row | Mapping[str, Any]]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for row in rows:
        item = _row_to_dict(row)
        source_url = normalize_ws(str(item.get("source_url") or ""))
        source_link_html = (
            f'<a href="{source_url}" target="_blank" rel="noopener noreferrer">Abrir documento fuente</a>'
            if source_url
            else "<p>Sin URL fuente</p>"
        )
        task = {
            "data": {
                "source_record_pk": str(item.get("source_record_pk") or ""),
                "sample_initiative_id": str(item.get("sample_initiative_id") or ""),
                "initiative_source_id": str(item.get("initiative_source_id") or ""),
                "initiative_title": str(item.get("initiative_title") or ""),
                "doc_format": str(item.get("doc_format") or ""),
                "doc_kinds_csv": str(item.get("doc_kinds_csv") or ""),
                "extractor_version": str(item.get("extractor_version") or ""),
                "subject_method": str(item.get("subject_method") or ""),
                "confidence": str(item.get("confidence") or ""),
                "source_url": source_url,
                "raw_path": str(item.get("raw_path") or ""),
                "review_context": _review_context(item),
                "source_link_html": source_link_html,
            }
        }
        tasks.append(task)
    return tasks


def _annotation_choice(annotation: Mapping[str, Any], key: str) -> str:
    value = annotation.get("value")
    if not isinstance(value, dict):
        return ""
    choices = value.get("choices")
    if key != normalize_ws(str(annotation.get("from_name") or "")) or not isinstance(choices, list) or not choices:
        return ""
    return normalize_ws(str(choices[0] or ""))


def _annotation_text(annotation: Mapping[str, Any], key: str) -> str:
    value = annotation.get("value")
    if not isinstance(value, dict):
        return ""
    texts = value.get("text")
    if key != normalize_ws(str(annotation.get("from_name") or "")) or not isinstance(texts, list) or not texts:
        return ""
    return normalize_ws(str(texts[0] or ""))


def _annotation_number(annotation: Mapping[str, Any], key: str) -> str:
    value = annotation.get("value")
    if not isinstance(value, dict):
        return ""
    if key != normalize_ws(str(annotation.get("from_name") or "")):
        return ""
    number = value.get("number")
    if number is None:
        return ""
    return normalize_ws(str(number))


def _annotation_reviewer(annotation: Mapping[str, Any]) -> str:
    completed_by = annotation.get("completed_by")
    if isinstance(completed_by, dict):
        for key in ("email", "username", "id"):
            token = normalize_ws(str(completed_by.get(key) or ""))
            if token:
                return token
    return normalize_ws(str(completed_by or ""))


def label_studio_tasks_to_review_rows(tasks: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for task in tasks:
        data = task.get("data") if isinstance(task.get("data"), dict) else {}
        annotations = task.get("annotations") if isinstance(task.get("annotations"), list) else []
        chosen_annotation: Mapping[str, Any] | None = None
        for annotation in reversed(annotations):
            if isinstance(annotation, dict) and isinstance(annotation.get("result"), list) and annotation.get("result"):
                chosen_annotation = annotation
                break
        if chosen_annotation is None:
            rows.append(
                {
                    "source_record_pk": normalize_ws(str(data.get("source_record_pk") or "")),
                    "review_status": "",
                    "final_subject": "",
                    "final_title": "",
                    "final_confidence": "",
                    "review_note": "",
                    "reviewer": "",
                }
            )
            continue

        results = chosen_annotation.get("result") if isinstance(chosen_annotation.get("result"), list) else []
        review_status = ""
        final_subject = ""
        final_title = ""
        final_confidence = ""
        review_note = ""
        for raw_result in results:
            if not isinstance(raw_result, dict):
                continue
            review_status = review_status or _annotation_choice(raw_result, "review_status")
            final_subject = final_subject or _annotation_text(raw_result, "final_subject")
            final_title = final_title or _annotation_text(raw_result, "final_title")
            final_confidence = final_confidence or _annotation_number(raw_result, "final_confidence")
            review_note = review_note or _annotation_text(raw_result, "review_note")

        rows.append(
            {
                "source_record_pk": normalize_ws(str(data.get("source_record_pk") or "")),
                "review_status": normalize_ws(review_status).lower(),
                "final_subject": final_subject,
                "final_title": final_title,
                "final_confidence": final_confidence,
                "review_note": review_note,
                "reviewer": _annotation_reviewer(chosen_annotation),
            }
        )
    return rows


def load_label_studio_tasks(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Label Studio export must be a JSON list")
    tasks: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            tasks.append(item)
    return tasks
