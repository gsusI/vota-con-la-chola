#!/usr/bin/env python3
"""Export fragment-level measure candidate extraction queue."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db
from etl.politicos_es.util import normalize_ws, stable_json


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_INITIATIVE_SOURCE_IDS = "congreso_iniciativas,senado_iniciativas"
DEFAULT_FRAGMENT_KINDS = "article,disposition,chunk"
DEFAULT_EVIDENCE_ROOT = Path("tmp/codex-subagents/fragment-measure-candidates/evidence")
SAFE_SLUG_RE = re.compile(r"[^a-z0-9]+")
PRIORITY_TERMS = (
    ("bajas emisiones", 14),
    ("diesel", 14),
    ("diésel", 14),
    ("baliza", 14),
    ("v16", 14),
    ("peaje", 12),
    ("impuesto", 12),
    ("gravamen", 12),
    ("iva", 10),
    ("ibi", 10),
    ("energ", 10),
    ("carbur", 10),
    ("hidrocarb", 10),
    ("transporte", 9),
    ("movilidad", 9),
    ("multa", 10),
    ("sanc", 10),
    ("alcohol", 10),
    ("dependencia", 9),
    ("familia monoparental", 9),
    ("cliente financiero", 9),
    ("reclamacion", 8),
)
NEGATIVE_PRIORITY_TERMS = (
    ("entrada en vigor", 35),
    ("ambito temporal", 16),
    ("ámbito temporal", 16),
    ("sendas e hitos", 16),
    ("domos", 14),
    ("informe anual", 10),
    ("memoria anual", 10),
)
DIRECT_IMPACT_TERMS = (
    "ayuda",
    "beca",
    "bonific",
    "exención",
    "exencion",
    "impuesto",
    "gravamen",
    "multa",
    "sanc",
    "factura",
    "peaje",
    "despido",
    "derecho",
    "prestación",
    "prestacion",
    "subvención",
    "subvencion",
    "tarifa",
    "precio",
    "reclama",
    "consumidor",
    "cliente",
    "salario",
    "contrato",
)
PROCEDURAL_DOWNRANK_TERMS = (
    "competencia",
    "competencias",
    "funciones",
    "atribución",
    "atribucion",
    "cesión",
    "cesion",
    "delegación",
    "delegacion",
    "gestión de tributos",
    "gestion de tributos",
    "consejo",
    "cnmv",
    "banco de españa",
    "banco de espana",
    "informe",
    "plan estratégico",
    "plan estrategico",
    "guías de buenas prácticas",
    "guias de buenas practicas",
    "sendas",
    "hitos",
    "indicadores",
    "publicación",
    "publicacion",
    "notificaciones",
    "sede electrónica",
    "sede electronica",
    "página web",
    "pagina web",
)
TREATY_AUTH_TERMS = (
    "adenda",
    "canje de notas",
    "acuerdo sobre la sede",
    "convenio internacional",
    "tratado",
    "onu-gcm",
    "unu-gcm",
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export fragment-level measure candidate queue")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument(
        "--initiative-source-ids",
        default=DEFAULT_INITIATIVE_SOURCE_IDS,
        help="CSV of parl_initiatives.source_id values to include",
    )
    p.add_argument(
        "--fragment-kinds",
        default=DEFAULT_FRAGMENT_KINDS,
        help="CSV of parl_text_fragments.fragment_kind values to include",
    )
    p.add_argument(
        "--contains",
        action="append",
        default=[],
        help="Case-insensitive filter across initiative title, fragment label, and fragment text",
    )
    p.add_argument(
        "--contains-any",
        action="append",
        default=[],
        help="Case-insensitive OR filter across initiative title, fragment label, and fragment text",
    )
    p.add_argument("--only-unclaimed", action="store_true", help="Only export fragments without candidates yet")
    p.add_argument("--min-fragment-chars", type=int, default=120)
    p.add_argument("--max-fragment-chars", type=int, default=2400)
    p.add_argument("--min-priority", type=int, default=0, help="Minimum computed priority required to export")
    p.add_argument("--limit", type=int, default=0, help="0 means no limit")
    p.add_argument("--offset", type=int, default=0, help="Row offset for deterministic batching")
    p.add_argument(
        "--evidence-root",
        default=str(DEFAULT_EVIDENCE_ROOT),
        help="Directory where fragment evidence bundles will be materialized",
    )
    p.add_argument("--out", required=True, help="Output CSV path")
    return p.parse_args()


def _norm(value: Any) -> str:
    return normalize_ws(str(value or ""))


def _parse_csv_tokens(raw: str) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for token in str(raw or "").split(","):
        item = _norm(token)
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return tuple(out)


def _slug(value: str) -> str:
    token = SAFE_SLUG_RE.sub("-", _norm(value).lower()).strip("-")
    return token or "fragment"


def _table_exists(conn: Any, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (_norm(table_name),),
    ).fetchone()
    return row is not None


def _priority_for_fragment(
    *,
    initiative_title: str,
    fragment_kind: str,
    fragment_label: str,
    fragment_text: str,
    recommended_vote_count: int,
) -> int:
    haystack = " ".join(
        [
            _norm(initiative_title).lower(),
            _norm(fragment_label).lower(),
            _norm(fragment_text).lower(),
        ]
    )
    has_direct_impact = any(term in haystack for term in DIRECT_IMPACT_TERMS)
    score = 35 + min(max(int(recommended_vote_count or 0), 0), 10)
    for term, boost in PRIORITY_TERMS:
        if term in haystack:
            score += boost
    for term, penalty in NEGATIVE_PRIORITY_TERMS:
        if term in haystack:
            score -= penalty
    if not has_direct_impact and any(term in haystack for term in PROCEDURAL_DOWNRANK_TERMS):
        score -= 18
    if _norm(fragment_kind) in {"article", "disposition"}:
        score += 8
    if len(_norm(fragment_text)) < 180:
        score -= 8
    return max(0, min(100, score))


def _is_definitely_low_signal_fragment(
    *,
    initiative_title: str,
    fragment_label: str,
    fragment_text: str,
) -> bool:
    haystack = " ".join(
        [
            _norm(initiative_title).lower(),
            _norm(fragment_label).lower(),
            _norm(fragment_text).lower(),
        ]
    )
    if "entrada en vigor" in haystack:
        return True
    if ("se autoriza" in haystack or "autorización" in haystack or "autorizacion" in haystack) and any(
        term in haystack for term in TREATY_AUTH_TERMS
    ):
        return True
    return False


def _fetch_linked_votes(conn: Any, initiative_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          pve.vote_event_id,
          pve.vote_date,
          pve.source_id,
          pve.title,
          pve.subgroup_title,
          pve.subgroup_text,
          pve.expediente_text,
          pve.totals_yes,
          pve.totals_no,
          pve.totals_abstain
        FROM parl_vote_event_initiatives pvi
        JOIN parl_vote_events pve ON pve.vote_event_id = pvi.vote_event_id
        WHERE pvi.initiative_id = ?
        ORDER BY pve.vote_date ASC, pve.vote_event_id ASC
        """,
        (_norm(initiative_id),),
    ).fetchall()
    return [{key: row[key] for key in row.keys()} for row in rows]


def _vote_candidate_score(vote: dict[str, Any]) -> tuple[int, str, int]:
    title = _norm(vote.get("title")).lower()
    subgroup_title = _norm(vote.get("subgroup_title")).lower()
    subgroup_text = _norm(vote.get("subgroup_text")).lower()
    priority = 9
    if "convalidación" in title or "convalidacion" in title or "derogación" in title or "derogacion" in title:
        priority = 0
    elif "votación final sobre el conjunto" in subgroup_title or "votacion final sobre el conjunto" in subgroup_title:
        priority = 1
    elif "votación de conjunto" in subgroup_title or "votacion de conjunto" in subgroup_title:
        priority = 1
    elif "texto final" in subgroup_title or "texto final" in subgroup_text:
        priority = 1
    elif title.startswith("enmiendas del senado"):
        priority = 2
    elif title.startswith("toma en consideración") or title.startswith("toma en consideracion"):
        priority = 3
    elif title.startswith("debates de totalidad"):
        priority = 4
    margin = abs(int(vote.get("totals_yes") or 0) - int(vote.get("totals_no") or 0))
    return (priority, _norm(vote.get("vote_date")), margin)


def _pick_key_vote_candidates(linked_votes: list[dict[str, Any]], max_candidates: int = 6) -> list[dict[str, Any]]:
    ordered = sorted(linked_votes, key=_vote_candidate_score)
    return ordered[: max(1, int(max_candidates or 1))]


def _fetch_version_primary_votes(conn: Any, initiative_id: str, initiative_text_version_id: str) -> list[dict[str, Any]]:
    if not _table_exists(conn, "parl_vote_event_text_versions"):
        return []
    rows = conn.execute(
        """
        SELECT
          pve.vote_event_id,
          pve.vote_date,
          pve.source_id,
          pve.title,
          pve.subgroup_title,
          pve.subgroup_text,
          pve.expediente_text,
          pve.totals_yes,
          pve.totals_no,
          pve.totals_abstain,
          vt.link_method,
          vt.confidence
        FROM parl_vote_event_text_versions vt
        JOIN parl_vote_events pve ON pve.vote_event_id = vt.vote_event_id
        WHERE vt.initiative_id = ?
          AND vt.initiative_text_version_id = ?
          AND vt.is_primary = 1
        ORDER BY pve.vote_date ASC, pve.vote_event_id ASC
        """,
        (_norm(initiative_id), _norm(initiative_text_version_id)),
    ).fetchall()
    return [{key: row[key] for key in row.keys()} for row in rows]


def _fetch_context_fragments(conn: Any, initiative_text_version_id: str, fragment_order: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT fragment_id, fragment_order, fragment_kind, fragment_label, fragment_text
        FROM parl_text_fragments
        WHERE initiative_text_version_id = ?
          AND fragment_order BETWEEN ? AND ?
        ORDER BY fragment_order ASC
        """,
        (_norm(initiative_text_version_id), max(1, int(fragment_order) - 1), int(fragment_order) + 1),
    ).fetchall()
    return [{key: row[key] for key in row.keys()} for row in rows]


def _fetch_existing_measure_points(conn: Any, initiative_id: str) -> list[dict[str, Any]]:
    if not _table_exists(conn, "parl_initiative_measure_points"):
        return []
    rows = conn.execute(
        """
        SELECT measure_title, citizen_summary, primary_vote_event_ids_json
        FROM parl_initiative_measure_points
        WHERE initiative_id = ?
        ORDER BY measure_rank ASC, measure_point_id ASC
        """,
        (_norm(initiative_id),),
    ).fetchall()
    return [{key: row[key] for key in row.keys()} for row in rows]


def fetch_fragment_review_rows(
    conn: Any,
    *,
    initiative_source_ids: tuple[str, ...],
    fragment_kinds: tuple[str, ...],
    contains_terms: list[str],
    contains_any_terms: list[str],
    only_unclaimed: bool,
    min_fragment_chars: int,
    max_fragment_chars: int,
    min_priority: int,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    if not initiative_source_ids or not fragment_kinds:
        return []
    source_marks = ",".join("?" for _ in initiative_source_ids)
    kind_marks = ",".join("?" for _ in fragment_kinds)
    params: list[Any] = [
        *initiative_source_ids,
        *fragment_kinds,
        max(0, int(min_fragment_chars or 0)),
        max(0, int(max_fragment_chars or 0)) if int(max_fragment_chars or 0) > 0 else 10_000_000,
    ]
    review_join = ""
    review_select = "'' AS existing_review_status"
    review_unclaimed_sql = ""
    if _table_exists(conn, "parl_fragment_measure_reviews"):
        review_join = """
        LEFT JOIN parl_fragment_measure_reviews fr
          ON fr.fragment_id = f.fragment_id
        """
        review_select = "COALESCE(fr.status, '') AS existing_review_status"
        if only_unclaimed:
            review_unclaimed_sql = "AND COALESCE(fr.status, '') = ''"
    only_unclaimed_sql = "AND COALESCE(mc.candidate_count, 0) = 0" if only_unclaimed else ""
    rows = conn.execute(
        f"""
        SELECT
          f.fragment_id,
          f.initiative_text_version_id,
          f.initiative_id,
          f.fragment_order,
          f.fragment_kind,
          f.fragment_label,
          f.fragment_text,
          tv.chamber,
          tv.doc_kind,
          tv.document_code,
          tv.doc_series,
          tv.doc_number,
          tv.version_order,
          tv.published_date,
          tv.stage_kind,
          tv.stage_label,
          i.source_id AS initiative_source_id,
          i.expediente,
          i.title AS initiative_title,
          i.type AS initiative_type,
          i.supertype,
          i.procedure_type,
          i.current_status,
          i.source_url AS initiative_source_url,
          COALESCE(mc.candidate_count, 0) AS candidate_count,
          {review_select}
        FROM parl_text_fragments f
        JOIN parl_initiative_text_versions tv
          ON tv.initiative_text_version_id = f.initiative_text_version_id
        JOIN parl_initiatives i
          ON i.initiative_id = f.initiative_id
        LEFT JOIN (
          SELECT fragment_id, COUNT(*) AS candidate_count
          FROM parl_measure_candidates
          WHERE fragment_id IS NOT NULL
          GROUP BY fragment_id
        ) mc
          ON mc.fragment_id = f.fragment_id
        {review_join}
        WHERE i.source_id IN ({source_marks})
          AND f.fragment_kind IN ({kind_marks})
          AND LENGTH(f.fragment_text) >= ?
          AND LENGTH(f.fragment_text) <= ?
          {only_unclaimed_sql}
          {review_unclaimed_sql}
        ORDER BY i.initiative_id ASC,
                 CASE WHEN tv.published_date IS NULL OR TRIM(tv.published_date) = '' THEN 1 ELSE 0 END ASC,
                 tv.published_date ASC,
                 f.fragment_order ASC
        """,
        params,
    ).fetchall()

    contains_norm = [_norm(term).lower() for term in contains_terms if _norm(term)]
    contains_any_norm = [_norm(term).lower() for term in contains_any_terms if _norm(term)]
    out: list[dict[str, Any]] = []
    for row in rows:
        item = {key: row[key] for key in row.keys()}
        haystack = " ".join(
            [
                _norm(item["initiative_title"]).lower(),
                _norm(item["fragment_label"]).lower(),
                _norm(item["fragment_text"]).lower(),
            ]
        )
        if contains_norm and not all(term in haystack for term in contains_norm):
            continue
        if contains_any_norm and not any(term in haystack for term in contains_any_norm):
            continue
        if _is_definitely_low_signal_fragment(
            initiative_title=_norm(item["initiative_title"]),
            fragment_label=_norm(item["fragment_label"]),
            fragment_text=_norm(item["fragment_text"]),
        ):
            continue
        version_votes = _fetch_version_primary_votes(
            conn,
            _norm(item["initiative_id"]),
            _norm(item["initiative_text_version_id"]),
        )
        key_votes = (
            _pick_key_vote_candidates(version_votes)
            if version_votes
            else _pick_key_vote_candidates(_fetch_linked_votes(conn, _norm(item["initiative_id"])))
        )
        item["recommended_primary_vote_event_ids"] = [
            _norm(vote.get("vote_event_id")) for vote in key_votes if _norm(vote.get("vote_event_id"))
        ]
        item["recommended_vote_count"] = len(item["recommended_primary_vote_event_ids"])
        item["priority"] = _priority_for_fragment(
            initiative_title=_norm(item["initiative_title"]),
            fragment_kind=_norm(item["fragment_kind"]),
            fragment_label=_norm(item["fragment_label"]),
            fragment_text=_norm(item["fragment_text"]),
            recommended_vote_count=int(item["recommended_vote_count"]),
        )
        if int(item["priority"]) < max(0, int(min_priority or 0)):
            continue
        out.append(item)

    out.sort(
        key=lambda item: (
            -int(item["priority"]),
            _norm(item["initiative_title"]).lower(),
            _norm(item["fragment_id"]),
        )
    )
    offset_i = max(0, int(offset or 0))
    if offset_i:
        out = out[offset_i:]
    limit_i = max(0, int(limit or 0))
    if limit_i:
        out = out[:limit_i]
    return out


def write_fragment_bundle(conn: Any, row: dict[str, Any], *, evidence_root: Path) -> Path:
    task_id = _norm(row["fragment_id"])
    bundle_dir = evidence_root / _slug(_norm(row["initiative_source_id"])) / _slug(task_id)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    version_votes = _fetch_version_primary_votes(
        conn,
        _norm(row["initiative_id"]),
        _norm(row["initiative_text_version_id"]),
    )
    linked_votes = _fetch_linked_votes(conn, _norm(row["initiative_id"]))
    key_votes = _pick_key_vote_candidates(version_votes) if version_votes else _pick_key_vote_candidates(linked_votes)
    bundle = {
        "task_id": task_id,
        "task_type": "fragment_measure_candidate_extraction",
        "subagent_hint": {
            "preferred_model": "gpt-5.3-codex-spark",
            "reasoning_effort": "high",
            "do_not_use_reasoning_effort": "xhigh",
            "output_schema_path": "docs/etl/review_schemas/fragment_measure_candidate_output.schema.json",
        },
        "initiative": {
            "initiative_id": _norm(row["initiative_id"]),
            "source_id": _norm(row["initiative_source_id"]),
            "expediente": _norm(row["expediente"]),
            "title": _norm(row["initiative_title"]),
            "type": _norm(row["initiative_type"]),
            "supertype": _norm(row["supertype"]),
            "procedure_type": _norm(row["procedure_type"]),
            "current_status": _norm(row["current_status"]),
            "source_url": _norm(row["initiative_source_url"]),
        },
        "text_version": {
            "initiative_text_version_id": _norm(row["initiative_text_version_id"]),
            "chamber": _norm(row["chamber"]),
            "doc_kind": _norm(row["doc_kind"]),
            "document_code": _norm(row["document_code"]),
            "doc_series": _norm(row["doc_series"]),
            "doc_number": _norm(row["doc_number"]),
            "version_order": int(row["version_order"] or 0),
            "published_date": _norm(row["published_date"]),
            "stage_kind": _norm(row["stage_kind"]),
            "stage_label": _norm(row["stage_label"]),
        },
        "fragment": {
            "fragment_id": _norm(row["fragment_id"]),
            "fragment_order": int(row["fragment_order"] or 0),
            "fragment_kind": _norm(row["fragment_kind"]),
            "fragment_label": _norm(row["fragment_label"]),
            "fragment_text": _norm(row["fragment_text"]),
        },
        "context_fragments": _fetch_context_fragments(
            conn,
            _norm(row["initiative_text_version_id"]),
            int(row["fragment_order"] or 0),
        ),
        "recommended_primary_vote_event_ids": [
            _norm(vote.get("vote_event_id")) for vote in key_votes if _norm(vote.get("vote_event_id"))
        ],
        "key_vote_candidates": key_votes,
        "existing_initiative_measures": _fetch_existing_measure_points(conn, _norm(row["initiative_id"])),
    }
    (bundle_dir / "bundle.json").write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (bundle_dir / "fragment.txt").write_text(_norm(row["fragment_text"]) + "\n", encoding="utf-8")
    return bundle_dir


def export_fragment_queue(
    conn: Any,
    *,
    initiative_source_ids: tuple[str, ...],
    fragment_kinds: tuple[str, ...],
    contains_terms: list[str],
    contains_any_terms: list[str],
    only_unclaimed: bool,
    min_fragment_chars: int,
    max_fragment_chars: int,
    min_priority: int,
    limit: int,
    offset: int,
    evidence_root: Path,
    out_csv: Path,
) -> dict[str, Any]:
    rows = fetch_fragment_review_rows(
        conn,
        initiative_source_ids=initiative_source_ids,
        fragment_kinds=fragment_kinds,
        contains_terms=contains_terms,
        contains_any_terms=contains_any_terms,
        only_unclaimed=only_unclaimed,
        min_fragment_chars=min_fragment_chars,
        max_fragment_chars=max_fragment_chars,
        min_priority=min_priority,
        limit=limit,
        offset=offset,
    )
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    exported = 0
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "task_id",
                "initiative_id",
                "initiative_source_id",
                "initiative_text_version_id",
                "fragment_id",
                "fragment_kind",
                "fragment_label",
                "priority",
                "recommended_primary_vote_event_ids_json",
                "evidence_bundle_dir",
            ],
        )
        writer.writeheader()
        for row in rows:
            bundle_dir = write_fragment_bundle(conn, row, evidence_root=evidence_root)
            writer.writerow(
                {
                    "task_id": _norm(row["fragment_id"]),
                    "initiative_id": _norm(row["initiative_id"]),
                    "initiative_source_id": _norm(row["initiative_source_id"]),
                    "initiative_text_version_id": _norm(row["initiative_text_version_id"]),
                    "fragment_id": _norm(row["fragment_id"]),
                    "fragment_kind": _norm(row["fragment_kind"]),
                    "fragment_label": _norm(row["fragment_label"]),
                    "priority": int(row["priority"]),
                    "recommended_primary_vote_event_ids_json": stable_json(row["recommended_primary_vote_event_ids"]),
                    "evidence_bundle_dir": str(bundle_dir),
                }
            )
            exported += 1
    return {
        "exported_rows": exported,
        "out_csv": str(out_csv),
        "evidence_root": str(evidence_root),
        "only_unclaimed": bool(only_unclaimed),
    }


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 2

    with open_db(db_path) as conn:
        apply_schema(conn, DEFAULT_SCHEMA)
        result = export_fragment_queue(
            conn,
            initiative_source_ids=_parse_csv_tokens(args.initiative_source_ids),
            fragment_kinds=_parse_csv_tokens(args.fragment_kinds),
            contains_terms=[_norm(term) for term in (args.contains or []) if _norm(term)],
            contains_any_terms=[_norm(term) for term in (args.contains_any or []) if _norm(term)],
            only_unclaimed=bool(args.only_unclaimed),
            min_fragment_chars=max(0, int(args.min_fragment_chars or 0)),
            max_fragment_chars=max(0, int(args.max_fragment_chars or 0)),
            min_priority=max(0, int(args.min_priority or 0)),
            limit=max(0, int(args.limit or 0)),
            offset=max(0, int(args.offset or 0)),
            evidence_root=Path(args.evidence_root),
            out_csv=Path(args.out),
        )

    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
