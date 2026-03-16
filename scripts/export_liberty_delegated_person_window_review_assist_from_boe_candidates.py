#!/usr/bin/env python3
"""Build review-assist packets from delegated BOE candidates."""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

STRICT_FAIL_EXIT = 4
INSTITUTION_TOKEN_EXPANSIONS = {
    "aeat": "Agencia Estatal de Administración Tributaria",
    "dgt": "Dirección General de Tráfico",
    "itss": "Inspección de Trabajo y Seguridad Social",
    "inspeccion de trabajo y seguridad social": "Inspección de Trabajo y Seguridad Social",
    "delegaciones/subdelegaciones del gobierno": "Delegación del Gobierno",
}


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _norm_lc(value: Any) -> str:
    return _norm(value).lower()


def _fold(value: Any) -> str:
    token = unicodedata.normalize("NFKD", _norm_lc(value))
    token = token.encode("ascii", "ignore").decode("ascii")
    token = re.sub(r"\s+", " ", token).strip()
    return token


def _tokenize(value: str, *, min_len: int = 4) -> list[str]:
    raw = re.findall(rf"[a-z0-9]{{{max(1, int(min_len))},}}", _fold(value))
    out: list[str] = []
    for token in raw:
        if token not in out:
            out.append(token)
    return out


def _to_iso_date_ddmmyyyy(value: str) -> str:
    token = _norm(value)
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", token)
    if not m:
        return ""
    dd, mm, yyyy = m.groups()
    return f"{yyyy}-{mm}-{dd}"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return [{str(k or ""): str(v or "") for k, v in row.items()} for row in reader]


def _reasons_set(raw: str) -> set[str]:
    return {token for token in _norm(raw).split("|") if token}


def _overlap(tokens_a: list[str], text_b: str) -> int:
    b = _fold(text_b)
    return sum(1 for token in tokens_a if token in b)


def _institution_tokens(label: str) -> list[str]:
    folded = _fold(label)
    tokens = _tokenize(folded, min_len=3)

    expanded = INSTITUTION_TOKEN_EXPANSIONS.get(folded)
    if expanded:
        for token in _tokenize(expanded, min_len=4):
            if token not in tokens:
                tokens.append(token)
    return tokens


def _institution_overlap_min(label: str) -> int:
    folded = _fold(label)
    if "inspeccion de trabajo y seguridad social" in folded or folded == "itss":
        return 2
    return 1


def _relevance_bucket(
    *,
    candidate_score: int,
    has_person_hint: bool,
    role_overlap: int,
    institution_overlap: int,
) -> str:
    if candidate_score >= 35 and has_person_hint and role_overlap >= 1:
        return "strong"
    if candidate_score >= 25 and (has_person_hint or role_overlap >= 1 or institution_overlap >= 2):
        return "medium"
    return "weak"


def _autofill_confidence(bucket: str) -> str:
    if bucket == "strong":
        return "high"
    if bucket == "medium":
        return "medium"
    return "low"


def build_review_assist_rows(
    *,
    review_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    min_candidate_score: int,
    max_candidates_per_link: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_link: dict[str, list[dict[str, str]]] = {}
    for row in candidate_rows:
        link_key = _norm(row.get("link_key"))
        if not link_key:
            continue
        by_link.setdefault(link_key, []).append(row)

    for link_key, rows in by_link.items():
        rows.sort(
            key=lambda item: (
                -int(item.get("candidate_score") or 0),
                int(item.get("candidate_rank") or 0),
                _norm(item.get("candidate_boe_id")),
            )
        )

    out_rows: list[dict[str, Any]] = []
    links_with_candidates = 0
    strong_total = 0
    medium_total = 0
    weak_total = 0

    for review in review_rows:
        link_key = _norm(review.get("link_key"))
        if not link_key:
            continue
        reasons = _reasons_set(_norm(review.get("reasons_csv")))
        role_tokens = _tokenize(_norm(review.get("designated_role_title")))
        delegated_institution_label = _norm(review.get("delegated_institution_label"))
        inst_tokens = _institution_tokens(delegated_institution_label)
        inst_overlap_min = _institution_overlap_min(delegated_institution_label)

        candidates = by_link.get(link_key, [])
        emitted_for_link = 0
        for candidate in candidates:
            score = int(candidate.get("candidate_score") or 0)
            if score < int(min_candidate_score):
                continue
            if emitted_for_link >= int(max_candidates_per_link):
                break

            title = _norm(candidate.get("candidate_title"))
            person_hint = _norm(candidate.get("candidate_person_hint"))
            role_overlap = _overlap(role_tokens, title)
            inst_overlap = _overlap(inst_tokens, f"{_norm(candidate.get('candidate_department'))} {title}")
            inst_overlap_ok = int(inst_overlap) >= int(inst_overlap_min)
            bucket = _relevance_bucket(
                candidate_score=score,
                has_person_hint=bool(person_hint),
                role_overlap=role_overlap,
                institution_overlap=inst_overlap,
            )
            if not inst_overlap_ok:
                bucket = "weak"
            if bucket == "strong":
                strong_total += 1
            elif bucket == "medium":
                medium_total += 1
            else:
                weak_total += 1

            publication_iso = _to_iso_date_ddmmyyyy(_norm(candidate.get("candidate_publication_date")))
            suggested_actor = person_hint if "missing_designated_actor" in reasons else ""
            suggested_date = publication_iso if "missing_enforcement_evidence_date" in reasons else ""
            recommended_action = "inspect_candidate"
            if not inst_overlap_ok:
                recommended_action = "inspect_candidate_low_institution_overlap"
            elif bucket in {"strong", "medium"}:
                recommended_action = "review_for_possible_approval"

            out_rows.append(
                {
                    "link_key": link_key,
                    "fragment_id": _norm(review.get("fragment_id")),
                    "norm_id": _norm(review.get("norm_id")),
                    "boe_id_context": _norm(review.get("boe_id")),
                    "delegated_institution_label": delegated_institution_label,
                    "designated_role_title": _norm(review.get("designated_role_title")),
                    "reasons_csv": _norm(review.get("reasons_csv")),
                    "candidate_rank_for_link": emitted_for_link + 1,
                    "candidate_score": score,
                    "candidate_relevance_bucket": bucket,
                    "autofill_confidence": _autofill_confidence(bucket),
                    "candidate_boe_id": _norm(candidate.get("candidate_boe_id")),
                    "candidate_doc_url": _norm(candidate.get("candidate_doc_url")),
                    "candidate_publication_date": _norm(candidate.get("candidate_publication_date")),
                    "candidate_publication_date_iso": publication_iso,
                    "candidate_department": _norm(candidate.get("candidate_department")),
                    "candidate_title": title,
                    "candidate_person_hint": person_hint,
                    "role_token_overlap": role_overlap,
                    "institution_token_overlap": inst_overlap,
                    "institution_overlap_min": inst_overlap_min,
                    "institution_overlap_ok": "1" if inst_overlap_ok else "0",
                    "suggested_reviewed_designated_actor_label": suggested_actor,
                    "suggested_reviewed_enforcement_evidence_date": suggested_date,
                    "suggested_reviewed_source_url": _norm(candidate.get("candidate_doc_url")),
                    "suggested_reviewed_evidence_quote": title,
                    "recommended_action": recommended_action,
                    "review_status": "pending",
                    "review_note": "",
                }
            )
            emitted_for_link += 1

        if emitted_for_link > 0:
            links_with_candidates += 1

    out_rows.sort(
        key=lambda item: (
            _norm(item.get("link_key")),
            -int(item.get("candidate_score") or 0),
            int(item.get("candidate_rank_for_link") or 0),
        )
    )

    summary = {
        "status": "ok",
        "review_links_total": len([r for r in review_rows if _norm(r.get("link_key"))]),
        "review_links_with_candidates_total": links_with_candidates,
        "review_links_without_candidates_total": max(
            0,
            len([r for r in review_rows if _norm(r.get("link_key"))]) - links_with_candidates,
        ),
        "assist_rows_total": len(out_rows),
        "min_candidate_score": int(min_candidate_score),
        "max_candidates_per_link": int(max_candidates_per_link),
        "relevance_bucket_counts": {
            "strong": strong_total,
            "medium": medium_total,
            "weak": weak_total,
        },
        "rows_below_institution_overlap_min_total": len(
            [row for row in out_rows if str(row.get("institution_overlap_ok")) != "1"]
        ),
    }
    return out_rows, summary


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "link_key",
        "fragment_id",
        "norm_id",
        "boe_id_context",
        "delegated_institution_label",
        "designated_role_title",
        "reasons_csv",
        "candidate_rank_for_link",
        "candidate_score",
        "candidate_relevance_bucket",
        "autofill_confidence",
        "candidate_boe_id",
        "candidate_doc_url",
        "candidate_publication_date",
        "candidate_publication_date_iso",
        "candidate_department",
        "candidate_title",
        "candidate_person_hint",
        "role_token_overlap",
        "institution_token_overlap",
        "institution_overlap_min",
        "institution_overlap_ok",
        "suggested_reviewed_designated_actor_label",
        "suggested_reviewed_enforcement_evidence_date",
        "suggested_reviewed_source_url",
        "suggested_reviewed_evidence_quote",
        "recommended_action",
        "review_status",
        "review_note",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--review-queue-csv",
        default="docs/etl/sprints/AI-OPS-278/exports/liberty_delegated_person_window_review_queue_latest.csv",
    )
    ap.add_argument(
        "--boe-candidates-csv",
        default="docs/etl/sprints/AI-OPS-280/exports/liberty_delegated_person_window_boe_candidates_latest.csv",
    )
    ap.add_argument("--min-candidate-score", type=int, default=20)
    ap.add_argument("--max-candidates-per-link", type=int, default=3)
    ap.add_argument("--strict-min-assist-rows", type=int, default=0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary-out", required=True)
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    review_path = Path(args.review_queue_csv)
    boe_path = Path(args.boe_candidates_csv)

    review_rows = _read_csv(review_path)
    candidate_rows = _read_csv(boe_path)

    assist_rows, summary = build_review_assist_rows(
        review_rows=review_rows,
        candidate_rows=candidate_rows,
        min_candidate_score=int(args.min_candidate_score),
        max_candidates_per_link=int(args.max_candidates_per_link),
    )

    out_csv = Path(args.out)
    _write_csv(out_csv, assist_rows)

    payload = {
        "review_queue_csv": str(review_path),
        "boe_candidates_csv": str(boe_path),
        "assist_csv": str(out_csv),
        "summary": summary,
    }
    out_json = Path(args.summary_out)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if int(args.strict_min_assist_rows) > 0 and int(summary.get("assist_rows_total", 0)) < int(args.strict_min_assist_rows):
        return STRICT_FAIL_EXIT
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
