#!/usr/bin/env python3
"""Export alternative institutional capture targets for delegated pending rows."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

STRICT_FAIL_EXIT = 4
BOE_REDIRECTOR = "https://www.boe.es/buscar/redirector.php?accion=Buscar&bd=boe&texto="

INSTITUTION_TARGETS = {
    "aeat": [
        ("aeat_web", "https://www.agenciatributaria.es/"),
        ("aeat_sede", "https://sede.agenciatributaria.gob.es/"),
        ("transparencia_gob", "https://transparencia.gob.es/"),
    ],
    "dgt": [
        ("dgt_web", "https://www.dgt.es/"),
        ("dgt_sede", "https://sede.dgt.gob.es/"),
        ("transparencia_gob", "https://transparencia.gob.es/"),
    ],
    "itss": [
        ("itss_web", "https://www.mites.gob.es/itss/web/"),
        ("mites_web", "https://www.mites.gob.es/"),
        ("transparencia_gob", "https://transparencia.gob.es/"),
    ],
    "delegaciones_subdelegaciones_gobierno": [
        ("administracion_gob", "https://administracion.gob.es/"),
        ("transparencia_gob", "https://transparencia.gob.es/"),
    ],
}


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return [{str(k or ""): str(v or "") for k, v in row.items()} for row in reader]


def _institution_key(label: str) -> str:
    token = _norm(label).lower()
    if "agencia estatal de administracion tributaria" in token or token == "aeat":
        return "aeat"
    if "direccion general de trafico" in token or token == "dgt":
        return "dgt"
    if "inspeccion de trabajo" in token or token == "itss":
        return "itss"
    if "delegaciones/subdelegaciones" in token:
        return "delegaciones_subdelegaciones_gobierno"
    return ""


def _default_query(row: dict[str, str]) -> str:
    role = _norm(row.get("designated_role_title"))
    inst = _norm(row.get("delegated_institution_label"))
    if role and inst:
        return f'nombramiento "{role}" "{inst}"'
    if role:
        return f'nombramiento "{role}"'
    if inst:
        return f'nombramiento "{inst}"'
    return "nombramiento"


def _boe_redirect_url(query: str) -> str:
    return f"{BOE_REDIRECTOR}{quote(_norm(query))}"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return int(default)


def _parse_top_candidates(raw: str) -> list[dict[str, Any]]:
    text = _norm(raw)
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    out: list[dict[str, Any]] = []
    for item in parsed:
        if isinstance(item, dict):
            out.append(item)
    return out


def _role_exact_query(role_title: str, institution_label: str) -> str:
    role = _norm(role_title)
    inst = _norm(institution_label)
    if role and inst:
        return f'nombramiento "{role}" "{inst}"'
    if role:
        return f'nombramiento "{role}"'
    return ""


def build_capture_targets(
    *,
    pending_rows: list[dict[str, str]],
    max_candidate_doc_targets_per_link: int,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    out_rows: list[dict[str, str]] = []
    pending_reason_counts: dict[str, int] = {}
    targets_by_label: dict[str, int] = {}
    links_with_targets: set[str] = set()
    boe_doc_candidates_emitted_total = 0

    for row in pending_rows:
        link_key = _norm(row.get("link_key"))
        decision = _norm(row.get("decision"))
        if not link_key or decision != "pending":
            continue
        links_with_targets.add(link_key)

        pending_reason = _norm(row.get("pending_reason"))
        if pending_reason:
            pending_reason_counts[pending_reason] = pending_reason_counts.get(pending_reason, 0) + 1

        primary_query = _norm(row.get("capture_query_primary")) or _default_query(row)
        secondary_query = _norm(row.get("capture_query_secondary"))
        institution_label = _norm(row.get("delegated_institution_label"))
        role_title = _norm(row.get("designated_role_title"))
        inst_key = _institution_key(institution_label)
        institution_targets = INSTITUTION_TARGETS.get(inst_key, [("transparencia_gob", "https://transparencia.gob.es/")])

        rank = 0

        def emit(
            *,
            target_group: str,
            target_label: str,
            target_url: str,
            query: str,
            candidate_boe_id: str = "",
            candidate_score: str = "",
            candidate_rank_for_link: str = "",
            candidate_publication_date_iso: str = "",
        ) -> None:
            nonlocal rank
            rank += 1
            out_rows.append(
                {
                    "link_key": link_key,
                    "pending_reason": pending_reason,
                    "delegated_institution_label": institution_label,
                    "designated_role_title": role_title,
                    "target_group": target_group,
                    "target_label": target_label,
                    "target_url": _norm(target_url),
                    "query": _norm(query),
                    "priority_rank": str(rank),
                    "candidate_boe_id": _norm(candidate_boe_id),
                    "candidate_score": _norm(candidate_score),
                    "candidate_rank_for_link": _norm(candidate_rank_for_link),
                    "candidate_publication_date_iso": _norm(candidate_publication_date_iso),
                }
            )
            targets_by_label[target_label] = targets_by_label.get(target_label, 0) + 1

        emit(
            target_group="boe_redirector_query",
            target_label="boe_redirector_primary",
            target_url=_boe_redirect_url(primary_query),
            query=primary_query,
        )
        if secondary_query and secondary_query != primary_query:
            emit(
                target_group="boe_redirector_query",
                target_label="boe_redirector_secondary",
                target_url=_boe_redirect_url(secondary_query),
                query=secondary_query,
            )

        top_candidates = _parse_top_candidates(_norm(row.get("top_candidates_json")))
        for cand in top_candidates[: max(0, int(max_candidate_doc_targets_per_link))]:
            doc_url = _norm(cand.get("candidate_doc_url"))
            boe_id = _norm(cand.get("candidate_boe_id"))
            if not doc_url:
                continue
            boe_doc_candidates_emitted_total += 1
            emit(
                target_group="boe_direct_doc",
                target_label=f"boe_direct_doc_{boe_id or 'unknown'}",
                target_url=doc_url,
                query=boe_id or _norm(cand.get("candidate_title")),
                candidate_boe_id=boe_id,
                candidate_score=str(_safe_int(cand.get("candidate_score"), 0)),
                candidate_rank_for_link=str(_safe_int(cand.get("candidate_rank_for_link"), 0)),
                candidate_publication_date_iso=_norm(cand.get("candidate_publication_date_iso")),
            )

        role_exact_query = _role_exact_query(role_title, institution_label)
        for target_label, target_url in institution_targets:
            emit(
                target_group="institutional_site",
                target_label=target_label,
                target_url=target_url,
                query=primary_query,
            )
            if role_exact_query and role_exact_query != primary_query:
                emit(
                    target_group="institutional_site",
                    target_label=f"{target_label}_role_exact",
                    target_url=target_url,
                    query=role_exact_query,
                )

    out_rows.sort(
        key=lambda item: (
            _norm(item.get("link_key")),
            int(_norm(item.get("priority_rank")) or "0"),
            _norm(item.get("target_label")),
        )
    )

    summary = {
        "status": "ok",
        "pending_links_total": len(links_with_targets),
        "target_rows_total": len(out_rows),
        "boe_doc_candidates_emitted_total": boe_doc_candidates_emitted_total,
        "max_candidate_doc_targets_per_link": int(max_candidate_doc_targets_per_link),
        "pending_reason_counts": dict(sorted(pending_reason_counts.items())),
        "targets_by_label": dict(sorted(targets_by_label.items())),
    }
    return out_rows, summary


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "link_key",
        "pending_reason",
        "delegated_institution_label",
        "designated_role_title",
        "target_group",
        "target_label",
        "target_url",
        "query",
        "priority_rank",
        "candidate_boe_id",
        "candidate_score",
        "candidate_rank_for_link",
        "candidate_publication_date_iso",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--pending-resolution-csv",
        default="docs/etl/sprints/AI-OPS-288/exports/liberty_delegated_pending_resolution_review_queue_targeted_latest.csv",
    )
    ap.add_argument("--max-candidate-doc-targets-per-link", type=int, default=3)
    ap.add_argument("--strict-min-targets-per-link", type=int, default=0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary-out", required=True)
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pending_path = Path(args.pending_resolution_csv)
    pending_rows = _read_csv(pending_path)

    target_rows, summary = build_capture_targets(
        pending_rows=pending_rows,
        max_candidate_doc_targets_per_link=int(args.max_candidate_doc_targets_per_link),
    )
    out_csv = Path(args.out)
    _write_csv(out_csv, target_rows)

    payload = {
        "pending_resolution_csv": str(pending_path),
        "targets_csv": str(out_csv),
        "summary": summary,
    }
    out_json = Path(args.summary_out)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    strict_min = int(args.strict_min_targets_per_link)
    if strict_min > 0:
        pending_links_total = int(summary.get("pending_links_total", 0))
        target_rows_total = int(summary.get("target_rows_total", 0))
        if pending_links_total > 0:
            avg_targets = target_rows_total / float(pending_links_total)
            if avg_targets < strict_min:
                return STRICT_FAIL_EXIT
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
