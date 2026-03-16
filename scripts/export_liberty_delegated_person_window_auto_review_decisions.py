#!/usr/bin/env python3
"""Build conservative auto-review decisions from delegated BOE review-assist rows."""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

STRICT_FAIL_EXIT = 4

REASON_NEEDS_ACTOR = {"missing_designated_actor", "institutional_designated_actor"}
REASON_NEEDS_EVIDENCE_DATE = {"missing_enforcement_evidence_date"}
ROLE_TOPIC_STOPWORDS = {
    "autoridad",
    "gubernativa",
    "procedimental",
    "unidad",
    "director",
    "directora",
    "direccion",
    "general",
    "subdireccion",
    "subdirección",
    "subdirector",
    "subdirectora",
    "jefatura",
    "jefe",
    "jefa",
    "organismo",
    "estatal",
    "delegacion",
    "delegación",
    "delegaciones",
    "cargo",
    "titular",
    "servicio",
    "inspeccion",
    "inspección",
    "trabajo",
    "seguridad",
    "social",
    "agencia",
    "tributaria",
    "aeat",
    "dgt",
    "itss",
    "trafico",
    "tráfico",
    "gobierno",
}


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return [{str(k or ""): str(v or "") for k, v in row.items()} for row in reader]


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value or "").strip())
    except Exception:
        return int(default)


def _is_iso_date(value: str) -> bool:
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", _norm(value)))


def _reasons(raw: str) -> set[str]:
    return {token for token in _norm(raw).split("|") if token}


def _fold(value: str) -> str:
    token = unicodedata.normalize("NFKD", _norm(value).lower())
    token = token.encode("ascii", "ignore").decode("ascii")
    token = re.sub(r"\s+", " ", token).strip()
    return token


def _clean_person(value: str) -> str:
    token = _norm(value).strip(" ,.;:-")
    token = re.sub(r"\s+", " ", token)
    return _norm(token)


def _prepare_candidates(
    assist_rows: list[dict[str, str]],
    *,
    min_candidate_score: int,
) -> dict[str, list[dict[str, str]]]:
    by_link: dict[str, list[dict[str, str]]] = {}
    for row in assist_rows:
        link_key = _norm(row.get("link_key"))
        if not link_key:
            continue
        if _to_int(row.get("candidate_score")) < int(min_candidate_score):
            continue
        by_link.setdefault(link_key, []).append(row)

    for link_key, rows in by_link.items():
        rows.sort(
            key=lambda item: (
                -_to_int(item.get("candidate_score")),
                _to_int(item.get("candidate_rank_for_link"), default=999999),
                _norm(item.get("candidate_boe_id")),
            )
        )
    return by_link


def _contains_any_folded(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _role_topic_tokens(role_title: str) -> set[str]:
    folded = _fold(role_title)
    tokens = {token for token in re.findall(r"[a-z0-9]{4,}", folded)}
    return {token for token in tokens if token not in ROLE_TOPIC_STOPWORDS}


def _role_alignment_assessment(
    *,
    designated_role_title: str,
    candidate_title: str,
    role_overlap: int,
    institution_overlap: int,
) -> tuple[bool, str]:
    role = _fold(designated_role_title)
    title = _fold(candidate_title)

    if not role:
        if int(role_overlap) >= 1 or int(institution_overlap) >= 1:
            return True, "role_empty_overlap_fallback"
        return False, "role_empty_no_overlap"

    if "autoridad gubernativa" in role:
        if _contains_any_folded(
            title,
            [
                "delegacion del gobierno",
                "subdelegacion del gobierno",
                "delegado del gobierno",
                "subdelegado del gobierno",
                "directora insular",
                "director insular",
            ],
        ):
            return True, "authority_role_matched"
        return False, "authority_role_not_found"

    if ("direccion general" in role or "director general" in role) and (
        "subdirector" in title or "subdireccion" in title
    ):
        return False, "hierarchy_mismatch_direction_vs_subdirection"

    if "direccion general" in role or "director general" in role:
        if not bool(re.search(r"\b(director|directora) general\b", title)):
            return False, "director_general_not_found"

    if "subdireccion" in role:
        if not _contains_any_folded(title, ["subdirector", "subdireccion"]):
            return False, "subdirection_not_found"
        # Conservative alias for DGT sanction lane where historical appointments
        # use "Normativa y Recursos"/"Legislación y Recursos" wording.
        if "sancion" in role and _contains_any_folded(title, ["direccion general de trafico"]):
            if _contains_any_folded(title, ["normativa y recursos", "legislacion y recursos"]):
                return True, "dgt_sanctions_subdirection_alias_matched"

    if "jefatura" in role:
        if "jef" not in title:
            return False, "jefatura_not_found"

    if "delegacion especial" in role:
        if not _contains_any_folded(title, ["delegacion especial", "delegado ejecutivo"]):
            return False, "delegacion_especial_not_found"

    if "organismo estatal itss" in role or ("organismo estatal" in role and "itss" in role):
        if not (
            _contains_any_folded(title, ["itss", "inspeccion de trabajo"])
            and _contains_any_folded(title, ["director", "direccion"])
        ):
            return False, "itss_direction_not_found"
        if _contains_any_folded(title, ["subdirector", "subdireccion"]):
            return False, "itss_hierarchy_mismatch_subdirection"
        return True, "itss_direction_matched"

    if "unidad procedimental" in role:
        if _contains_any_folded(title, ["procedim", "sancion"]):
            return True, "procedural_unit_topic_matched"
        if int(institution_overlap) >= 3 and _contains_any_folded(
            title,
            [
                "delega el ejercicio",
                "delegacion de competencias",
                "delegación de competencias",
            ],
        ):
            return True, "procedural_unit_competence_delegation_matched"
        if int(institution_overlap) >= 3 and _contains_any_folded(
            title,
            ["director", "subdirector", "delegado", "presidencia", "jef"],
        ):
            return False, "procedural_unit_non_nominative_requires_manual"
        return False, "procedural_unit_not_found"

    topic_tokens = _role_topic_tokens(role)
    if topic_tokens and not any(token in title for token in topic_tokens):
        return False, "role_topic_overlap_zero"

    if int(role_overlap) >= 1:
        return True, "role_overlap"

    return False, "role_alignment_insufficient"


def _build_output_row(base: dict[str, str]) -> dict[str, str]:
    return {
        "link_key": _norm(base.get("link_key")),
        "fragment_id": _norm(base.get("fragment_id")),
        "norm_id": _norm(base.get("norm_id")),
        "boe_id": _norm(base.get("boe_id")),
        "delegating_actor_label": _norm(base.get("delegating_actor_label")),
        "delegated_institution_label": _norm(base.get("delegated_institution_label")),
        "designated_role_title": _norm(base.get("designated_role_title")),
        "current_designated_actor_label": _norm(base.get("current_designated_actor_label")),
        "current_appointment_start_date": _norm(base.get("current_appointment_start_date")),
        "current_appointment_end_date": _norm(base.get("current_appointment_end_date")),
        "current_enforcement_evidence_date": _norm(base.get("current_enforcement_evidence_date")),
        "current_source_url": _norm(base.get("current_source_url")),
        "current_evidence_quote": _norm(base.get("current_evidence_quote")),
        "chain_confidence": _norm(base.get("chain_confidence")),
        "reasons_csv": _norm(base.get("reasons_csv")),
        "actionability": _norm(base.get("actionability")),
        "decision": "pending",
        "reviewed_designated_actor_label": "",
        "reviewed_appointment_start_date": "",
        "reviewed_appointment_end_date": "",
        "reviewed_enforcement_evidence_date": "",
        "reviewed_source_url": "",
        "reviewed_evidence_quote": "",
        "review_note": "",
    }


def _is_non_nominative_procedural_role(role_title: str) -> bool:
    role = _fold(role_title)
    return "unidad procedimental" in role


def _non_nominative_fallback_actor_label(role_title: str, institution_label: str) -> str:
    role = _norm(role_title)
    inst = _norm(institution_label)
    if role and inst:
        return f"{role} ({inst})"
    if role:
        return role
    return inst


def _candidate_allows_non_nominative_fallback(*, candidate_title: str, institution_overlap: int) -> bool:
    if int(institution_overlap) < 3:
        return False
    title = _fold(candidate_title)
    return _contains_any_folded(
        title,
        [
            "delega el ejercicio",
            "delegacion de competencias",
            "delegación de competencias",
            "gestion tributaria",
            "gestión tributaria",
        ],
    )


def build_auto_review_rows(
    *,
    review_rows: list[dict[str, str]],
    assist_rows: list[dict[str, str]],
    min_candidate_score: int,
    max_candidates_per_link: int,
    require_role_alignment: bool = True,
    allow_non_nominative_institutional_actor_fallback: bool = False,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    by_link = _prepare_candidates(assist_rows, min_candidate_score=int(min_candidate_score))
    rows_out: list[dict[str, str]] = []

    approved_rows_total = 0
    pending_rows_total = 0
    approved_with_actor_update_total = 0
    approved_with_evidence_date_update_total = 0
    approved_with_non_nominative_actor_fallback_total = 0
    rows_missing_candidate_total = 0
    rows_missing_required_person_hint_total = 0
    rows_missing_required_evidence_date_total = 0
    rows_missing_role_alignment_total = 0
    links_with_assist_candidates: set[str] = set()

    for review in review_rows:
        out_row = _build_output_row(review)
        reasons = _reasons(_norm(review.get("reasons_csv")))
        link_key = _norm(review.get("link_key"))
        candidates = by_link.get(link_key, [])
        if candidates:
            links_with_assist_candidates.add(link_key)

        needs_actor = bool(REASON_NEEDS_ACTOR & reasons)
        needs_evidence_date = bool(REASON_NEEDS_EVIDENCE_DATE & reasons)
        non_nominative_role = _is_non_nominative_procedural_role(_norm(review.get("designated_role_title")))

        chosen: dict[str, str] | None = None
        chosen_person_hint = ""
        chosen_evidence_date = ""
        chosen_non_nominative_actor_fallback = False
        role_alignment_reasons: set[str] = set()
        person_date_eligible_total = 0
        scan_limit = max(1, int(max_candidates_per_link))
        for candidate in candidates[:scan_limit]:
            person_hint = _clean_person(_norm(candidate.get("candidate_person_hint")))
            evidence_date = _norm(candidate.get("candidate_publication_date_iso"))
            role_overlap = _to_int(candidate.get("role_token_overlap"))
            institution_overlap = _to_int(candidate.get("institution_token_overlap"))
            allows_non_nominative_actor_fallback = bool(
                allow_non_nominative_institutional_actor_fallback
                and bool(needs_actor)
                and not bool(person_hint)
                and bool(non_nominative_role)
                and _candidate_allows_non_nominative_fallback(
                    candidate_title=_norm(candidate.get("candidate_title")),
                    institution_overlap=institution_overlap,
                )
            )
            if needs_actor and not person_hint and not allows_non_nominative_actor_fallback:
                continue
            if needs_evidence_date and not _is_iso_date(evidence_date):
                continue
            person_date_eligible_total += 1

            if bool(require_role_alignment):
                role_ok, role_reason = _role_alignment_assessment(
                    designated_role_title=_norm(review.get("designated_role_title")),
                    candidate_title=_norm(candidate.get("candidate_title")),
                    role_overlap=role_overlap,
                    institution_overlap=institution_overlap,
                )
                if not role_ok:
                    role_alignment_reasons.add(_norm(role_reason) or "role_alignment_insufficient")
                    continue

            chosen = candidate
            chosen_person_hint = person_hint
            chosen_evidence_date = evidence_date
            chosen_non_nominative_actor_fallback = bool(allows_non_nominative_actor_fallback and not person_hint)
            break

        if chosen is None:
            pending_rows_total += 1
            if not candidates:
                rows_missing_candidate_total += 1
                out_row["review_note"] = "auto_assist:no_candidate_for_link"
            else:
                person_any = any(_clean_person(_norm(c.get("candidate_person_hint"))) for c in candidates[:scan_limit])
                date_any = any(_is_iso_date(_norm(c.get("candidate_publication_date_iso"))) for c in candidates[:scan_limit])
                if needs_actor and not person_any:
                    rows_missing_required_person_hint_total += 1
                    out_row["review_note"] = "auto_assist:missing_person_hint_for_required_actor"
                elif needs_evidence_date and not date_any:
                    rows_missing_required_evidence_date_total += 1
                    out_row["review_note"] = "auto_assist:missing_evidence_date_for_required_field"
                elif bool(require_role_alignment) and person_date_eligible_total > 0:
                    rows_missing_role_alignment_total += 1
                    role_reason = sorted(role_alignment_reasons)[0] if role_alignment_reasons else "role_alignment_insufficient"
                    out_row["review_note"] = f"auto_assist:role_alignment_failed:{role_reason}"
                else:
                    out_row["review_note"] = "auto_assist:no_candidate_meets_requirements"
            rows_out.append(out_row)
            continue

        person_hint = chosen_person_hint
        evidence_date = chosen_evidence_date
        source_url = _norm(chosen.get("candidate_doc_url"))
        evidence_quote = _norm(chosen.get("candidate_title"))
        candidate_boe_id = _norm(chosen.get("candidate_boe_id"))

        if needs_actor:
            if person_hint:
                out_row["reviewed_designated_actor_label"] = person_hint
            elif chosen_non_nominative_actor_fallback:
                out_row["reviewed_designated_actor_label"] = _non_nominative_fallback_actor_label(
                    _norm(review.get("designated_role_title")),
                    _norm(review.get("delegated_institution_label")),
                )
                approved_with_non_nominative_actor_fallback_total += 1
            approved_with_actor_update_total += 1
        if needs_evidence_date:
            out_row["reviewed_enforcement_evidence_date"] = evidence_date
            approved_with_evidence_date_update_total += 1
        if source_url:
            out_row["reviewed_source_url"] = source_url
        if evidence_quote:
            out_row["reviewed_evidence_quote"] = evidence_quote

        out_row["decision"] = "approved"
        if chosen_non_nominative_actor_fallback:
            out_row["review_note"] = (
                f"auto_assist:approved_non_nominative_unit_from_{candidate_boe_id}"
                if candidate_boe_id
                else "auto_assist:approved_non_nominative_unit"
            )
        else:
            out_row["review_note"] = f"auto_assist:approved_from_{candidate_boe_id}" if candidate_boe_id else "auto_assist:approved"
        approved_rows_total += 1
        rows_out.append(out_row)

    summary = {
        "status": "ok",
        "rows_total": len(rows_out),
        "rows_with_assist_candidates_total": len(links_with_assist_candidates),
        "approved_rows_total": approved_rows_total,
        "pending_rows_total": pending_rows_total,
        "approved_with_actor_update_total": approved_with_actor_update_total,
        "approved_with_evidence_date_update_total": approved_with_evidence_date_update_total,
        "approved_with_non_nominative_actor_fallback_total": approved_with_non_nominative_actor_fallback_total,
        "rows_missing_candidate_total": rows_missing_candidate_total,
        "rows_missing_required_person_hint_total": rows_missing_required_person_hint_total,
        "rows_missing_required_evidence_date_total": rows_missing_required_evidence_date_total,
        "rows_missing_role_alignment_total": rows_missing_role_alignment_total,
        "role_alignment_required": bool(require_role_alignment),
        "allow_non_nominative_institutional_actor_fallback": bool(allow_non_nominative_institutional_actor_fallback),
        "min_candidate_score": int(min_candidate_score),
        "max_candidates_per_link": int(max_candidates_per_link),
    }
    return rows_out, summary


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "link_key",
        "fragment_id",
        "norm_id",
        "boe_id",
        "delegating_actor_label",
        "delegated_institution_label",
        "designated_role_title",
        "current_designated_actor_label",
        "current_appointment_start_date",
        "current_appointment_end_date",
        "current_enforcement_evidence_date",
        "current_source_url",
        "current_evidence_quote",
        "chain_confidence",
        "reasons_csv",
        "actionability",
        "decision",
        "reviewed_designated_actor_label",
        "reviewed_appointment_start_date",
        "reviewed_appointment_end_date",
        "reviewed_enforcement_evidence_date",
        "reviewed_source_url",
        "reviewed_evidence_quote",
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
        "--review-assist-csv",
        default="docs/etl/sprints/AI-OPS-281/exports/liberty_delegated_person_window_review_assist_latest.csv",
    )
    ap.add_argument("--min-candidate-score", type=int, default=25)
    ap.add_argument("--max-candidates-per-link", type=int, default=3)
    ap.add_argument("--disable-role-alignment", action="store_true")
    ap.add_argument("--allow-non-nominative-institutional-actor-fallback", action="store_true")
    ap.add_argument("--strict-min-approved-rows", type=int, default=0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary-out", required=True)
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    review_rows = _read_csv(Path(args.review_queue_csv))
    assist_rows = _read_csv(Path(args.review_assist_csv))

    rows, summary = build_auto_review_rows(
        review_rows=review_rows,
        assist_rows=assist_rows,
        min_candidate_score=int(args.min_candidate_score),
        max_candidates_per_link=int(args.max_candidates_per_link),
        require_role_alignment=not bool(args.disable_role_alignment),
        allow_non_nominative_institutional_actor_fallback=bool(args.allow_non_nominative_institutional_actor_fallback),
    )
    out_csv = Path(args.out)
    _write_csv(out_csv, rows)

    payload = {
        "review_queue_csv": _norm(args.review_queue_csv),
        "review_assist_csv": _norm(args.review_assist_csv),
        "out_csv": str(out_csv),
        "summary": summary,
    }
    out_json = Path(args.summary_out)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if int(args.strict_min_approved_rows) > 0 and int(summary.get("approved_rows_total", 0)) < int(args.strict_min_approved_rows):
        return STRICT_FAIL_EXIT
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
