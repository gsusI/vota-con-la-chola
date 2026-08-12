#!/usr/bin/env python3
"""Export a bounded static Evidence API from accountability ledger/dossier JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.politicos_es.util import now_utc_iso


DEFAULT_DOSSIERS = Path("etl/data/published/accountability-dossiers-latest.json")
DEFAULT_LEDGER = Path("etl/data/published/accountability-ledger-latest.json")
DEFAULT_OUT = Path("etl/data/published/accountability-evidence-api.json")
DEFAULT_ISSUE_CLUSTER_REVIEWS = Path("etl/data/seeds/accountability_issue_cluster_reviews_seed_v1.json")
DEFAULT_ISSUE_CLUSTER_ISSUE_REVIEWS = Path("etl/data/seeds/accountability_issue_cluster_issue_reviews_seed_v1.json")
DEFAULT_SOURCE_CATALOG = Path("etl/data/published/source-catalog-latest.json")

EXPECTED_DIMENSIONS = (
    ("promises", "promise"),
    ("parliamentary_actions", "parliamentary_action"),
    ("rules", "rule"),
    ("appointments", "appointment"),
    ("money", "money"),
    ("implementation", "implementation"),
    ("enforcement", "enforcement"),
    ("audits", "audit"),
    ("outcomes", "outcome"),
)

DIMENSION_LABELS = {
    "promises": "promises",
    "parliamentary_actions": "parliamentary actions",
    "rules": "rules",
    "appointments": "appointments",
    "money": "money",
    "implementation": "implementation",
    "enforcement": "enforcement",
    "audits": "audits",
    "outcomes": "outcomes",
}

NEXT_EVIDENCE_NEEDED = {
    "promises": "Manifestos, programs, party releases, and official commitments linked to the same issue IDs.",
    "parliamentary_actions": "More votes, initiatives, amendments, sponsorships, committee activity, and interventions.",
    "rules": "BOE and official-bulletin norms, decrees, orders, resolutions, competence clauses, and effective dates.",
    "appointments": "Official appointment and dismissal records with appointee, appointer, office, unit, and term dates.",
    "money": "Budget execution, contracts, grants, subsidies, staffing, and procurement documents tied to the issue.",
    "implementation": "Administrative instructions, permits, licensing workflows, service delivery, and operational acts.",
    "enforcement": "Inspection, sanction, enforcement, and competent-body records with dates and jurisdiction.",
    "audits": "Audit, court, control-body, and ombudsman findings tied to the issue and actor chain.",
    "outcomes": "Official indicators, service outputs, revisions, confounders, and methodology for causal restraint.",
}

ISSUE_CLUSTER_RULES = (
    {
        "cluster_id": "public-finance-taxation",
        "label": "Public finance, budgets, and taxation",
        "keywords": (
            "presupuesto",
            "presupuestos",
            "impuesto",
            "impuestos",
            "tributaria",
            "fiscalidad",
            "iva",
            "transacciones financieras",
            "servicios digitales",
        ),
    },
    {
        "cluster_id": "education-culture",
        "label": "Education, universities, culture, and training",
        "keywords": (
            "educacion",
            "ensenanzas",
            "formacion profesional",
            "universidad",
            "universidades",
            "bilingue",
            "cultura",
            "unesco",
        ),
    },
    {
        "cluster_id": "agriculture-food-rural",
        "label": "Agriculture, food, fishing, and rural affairs",
        "keywords": (
            "agricultura",
            "alimentacion",
            "pesca",
            "pesquero",
            "caza",
            "rural",
            "agro",
            "rio mino",
        ),
    },
    {
        "cluster_id": "health-care",
        "label": "Health, care, patients, and public health",
        "keywords": (
            "sanidad",
            "salud",
            "paciente",
            "enfermedad",
            "enfermedades",
            "medicamento",
            "medicamentos",
            "medico",
            "medicos",
            "dependencia",
            "discapacidad",
        ),
    },
    {
        "cluster_id": "climate-environment-water",
        "label": "Climate, environment, water, and territorial risk",
        "keywords": (
            "emision",
            "emisiones",
            "efecto invernadero",
            "medio ambiente",
            "mar menor",
            "agua",
            "cuenca",
            "reserva de biosfera",
            "inundable",
        ),
    },
    {
        "cluster_id": "justice-security-rights",
        "label": "Justice, security, rights, and public order",
        "keywords": (
            "justicia",
            "penal",
            "corrupcion",
            "terrorismo",
            "delito",
            "delitos",
            "seguridad",
            "derechos fundamentales",
            "proteccion de datos",
            "informacion clasificada",
            "pasajeros",
            "visados",
        ),
    },
    {
        "cluster_id": "digital-finance-technology",
        "label": "Digital services, data, technology, and financial systems",
        "keywords": (
            "digital",
            "electronicos",
            "electronicas",
            "datos",
            "tecnologia",
            "financiero",
            "financiera",
            "financieros",
            "financieras",
        ),
    },
    {
        "cluster_id": "labor-social-rights",
        "label": "Labour, social rights, youth, and households",
        "keywords": (
            "trabajo",
            "empleo",
            "laboral",
            "juventud",
            "menores",
            "vivienda",
            "familia",
            "hogar",
        ),
    },
    {
        "cluster_id": "parliamentary-procedure",
        "label": "Parliamentary procedure and institutional rules",
        "keywords": (
            "reglamento del senado",
            "avocacion",
            "dictamenes de comisiones",
            "iniciativas legislativas",
            "disposicion adicional",
        ),
    },
    {
        "cluster_id": "international-relations-treaties",
        "label": "International relations, treaties, and external agreements",
        "keywords": (
            "acuerdo",
            "tratado",
            "convenio",
            "convencion",
            "protocolo",
            "adhesion",
            "otan",
            "naciones unidas",
            "union europea",
            "reino de espana",
        ),
    },
)

FALLBACK_ISSUE_CLUSTER = {
    "cluster_id": "other-official-actions",
    "label": "Other official actions needing manual grouping",
    "keywords": (),
}

QUESTION_TEMPLATES = (
    {
        "question_id": "issue_involved_actors",
        "question": "Que actores tocaron este tema?",
        "answer_collection": "issue_answers",
        "route_kind": "issue",
        "answer_shape": "issue -> actors, roles, evidence samples, caveats",
    },
    {
        "question_id": "actor_historical_record",
        "question": "Que hizo este actor a traves del tiempo?",
        "answer_collection": "actor_answers",
        "route_kind": "actor",
        "answer_shape": "actor -> issues, roles, dates, evidence samples, caveats",
    },
    {
        "question_id": "actor_issue_record",
        "question": "Que hizo este actor en este tema concreto?",
        "answer_collection": "actor_issue_refs",
        "route_kind": "actor_issue",
        "answer_shape": "actor + issue -> role counts and date range",
    },
    {
        "question_id": "missing_evidence",
        "question": "Que dimensiones faltan antes de afirmar responsabilidad completa?",
        "answer_collection": "gap_answers, actor_answers and issue_answers",
        "route_kind": "caveat",
        "answer_shape": "missing dimension counts, gap status, sample actors/issues, next evidence needed",
    },
    {
        "question_id": "source_blocker",
        "question": "Que fuentes publicas estan bloqueadas o no son reproducibles?",
        "answer_collection": "blocker_answers",
        "route_kind": "blocker",
        "answer_shape": "source -> blocker state, evidence refs, source catalog route, next command",
    },
    {
        "question_id": "natural_language_qa",
        "question": "Que puede contestar ya la API en lenguaje natural?",
        "answer_collection": "qa_answers",
        "route_kind": "qa",
        "answer_shape": "question -> answer text, evidence basis, routes, and caveats",
    },
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export static accountability Evidence API JSON")
    p.add_argument("--dossiers", default=str(DEFAULT_DOSSIERS), help="Input accountability-dossiers JSON")
    p.add_argument("--ledger", default=str(DEFAULT_LEDGER), help="Input accountability-ledger JSON")
    p.add_argument(
        "--issue-cluster-reviews",
        default=str(DEFAULT_ISSUE_CLUSTER_REVIEWS),
        help="Optional reviewed issue-cluster decision seed JSON",
    )
    p.add_argument(
        "--issue-cluster-issue-reviews",
        default=str(DEFAULT_ISSUE_CLUSTER_ISSUE_REVIEWS),
        help="Optional reviewed issue-level cluster assignment seed JSON",
    )
    p.add_argument(
        "--source-catalog",
        default=str(DEFAULT_SOURCE_CATALOG),
        help="Optional source-catalog JSON for blocker answers",
    )
    p.add_argument("--snapshot-date", required=True, help="Snapshot date")
    p.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path")
    p.add_argument("--latest-out", default="", help="Optional latest alias output")
    p.add_argument("--max-actor-answers", type=int, default=5000, help="Max actor answer cards")
    p.add_argument("--max-issue-answers", type=int, default=5000, help="Max issue answer cards")
    p.add_argument("--max-actor-issue-refs", type=int, default=2500, help="Max actor/issue refs")
    p.add_argument(
        "--max-issue-cluster-assignment-review-items",
        type=int,
        default=250,
        help="Max unreviewed issue-level cluster assignment review items",
    )
    p.add_argument("--max-top-items", type=int, default=3, help="Max top actors/issues per answer")
    p.add_argument("--max-evidence-per-answer", type=int, default=1, help="Max evidence refs per answer")
    p.add_argument("--max-qa-answers", type=int, default=32, help="Max natural-language QA answers")
    p.add_argument("--pretty", action="store_true", help="Write indented JSON for manual inspection")
    return p.parse_args()


def _safe_array(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _load_json(path: Path) -> dict[str, Any]:
    return _safe_object(json.loads(path.read_text(encoding="utf-8")))


def _load_optional_json(path_text: str) -> dict[str, Any]:
    text = str(path_text or "").strip()
    if not text:
        return {}
    path = Path(text)
    if not path.exists():
        return {}
    return _load_json(path)


def _base36(value: int) -> str:
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value == 0:
        return "0"
    out = ""
    while value:
        value, rem = divmod(value, 36)
        out = chars[rem] + out
    return out


def _stable_hash(value: str) -> str:
    h = 5381
    for char in str(value or ""):
        h = ((h * 33) ^ ord(char)) & 0xFFFFFFFF
    return _base36(h)


def _slug(value: str) -> str:
    raw = str(value or "unknown")
    base = "".join(char.lower() if char.isalnum() else "-" for char in raw)
    while "--" in base:
        base = base.replace("--", "-")
    base = base.strip("-")[:96] or "item"
    return f"{base}-{_stable_hash(raw)}"


def _actor_route(actor: dict[str, Any]) -> str:
    return f"/accountability-dossiers/actors/{_slug(str(actor.get('actor_key') or actor.get('actor_label') or 'actor'))}/"


def _issue_route(issue: dict[str, Any]) -> str:
    return f"/accountability-dossiers/issues/{_slug(str(issue.get('issue_id') or issue.get('label') or 'issue'))}/"


def _qa_route(answer_id: str) -> str:
    return f"/accountability-evidence/questions/{_slug(answer_id)}/"


def _top_pairs(mapping: Any, limit: int) -> list[dict[str, Any]]:
    return [
        {"key": key, "count": int(value or 0)}
        for key, value in sorted(
            _safe_object(mapping).items(),
            key=lambda item: (-int(item[1] or 0), str(item[0])),
        )[:limit]
    ]


def _merge_pairs(counter: Counter[str], pairs: Any) -> None:
    for item in _safe_array(pairs):
        obj = _safe_object(item)
        key = str(obj.get("key") or "").strip()
        if not key:
            continue
        try:
            count = int(obj.get("count") or 0)
        except (TypeError, ValueError):
            count = 0
        if count > 0:
            counter[key] += count


def _clip(value: Any, limit: int = 280) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def _fold_text(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _keyword_in_text(keyword: str, haystack: str) -> bool:
    folded_keyword = _fold_text(keyword).strip()
    if not folded_keyword:
        return False
    pattern = r"(?<![a-z0-9])" + re.escape(folded_keyword) + r"(?![a-z0-9])"
    return re.search(pattern, haystack) is not None


def _present_dimensions(entry_kinds: Any) -> list[str]:
    kinds = set(_safe_object(entry_kinds))
    return [dimension for dimension, kind in EXPECTED_DIMENSIONS if kind in kinds]


def _missing_dimensions(entry_kinds: Any) -> list[str]:
    kinds = set(_safe_object(entry_kinds))
    return [dimension for dimension, kind in EXPECTED_DIMENSIONS if kind not in kinds]


def _answer_status(entry_kinds: Any, entries_total: Any) -> str:
    if int(entries_total or 0) <= 0:
        return "unanswerable"
    return "answerable" if not _missing_dimensions(entry_kinds) else "partial"


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            return None


def _best_evidence_tier(evidence_samples: list[dict[str, Any]]) -> int | None:
    tiers: list[int] = []
    for sample in evidence_samples:
        try:
            tier = int(sample.get("evidence_tier") or 0)
        except (TypeError, ValueError):
            continue
        if tier > 0:
            tiers.append(tier)
    return min(tiers) if tiers else None


def _confidence(entry_kinds: Any, entries_total: Any, evidence_samples: list[dict[str, Any]]) -> dict[str, Any]:
    total = int(entries_total or 0)
    present = _present_dimensions(entry_kinds)
    missing = _missing_dimensions(entry_kinds)
    expected_total = len(EXPECTED_DIMENSIONS)
    completeness_pct = round(len(present) / expected_total, 3) if expected_total else 1.0
    if total <= 0:
        return {
            "level": "none",
            "score": 0.0,
            "basis": ["no_entries"],
            "best_evidence_tier": None,
            "completeness": {
                "present_dimensions_total": len(present),
                "missing_dimensions_total": len(missing),
                "expected_dimensions_total": expected_total,
                "pct": completeness_pct,
            },
        }

    best_tier = _best_evidence_tier(evidence_samples)
    if best_tier == 1:
        score = 0.72
        basis = ["tier_1_primary_or_official_evidence"]
    elif best_tier == 2:
        score = 0.58
        basis = ["tier_2_official_structured_evidence"]
    elif best_tier == 3:
        score = 0.42
        basis = ["tier_3_official_communication_or_context"]
    else:
        score = 0.32
        basis = ["no_sampled_evidence_tier"]

    if total >= 100:
        score += 0.1
        basis.append("large_evidence_count")
    elif total >= 10:
        score += 0.05
        basis.append("multiple_evidence_rows")
    if missing:
        score -= 0.04
        basis.append("partial_dimension_coverage")
    score = max(0.0, min(1.0, round(score, 3)))
    if score >= 0.75:
        level = "high"
    elif score >= 0.55:
        level = "medium"
    elif score > 0:
        level = "low"
    else:
        level = "none"
    return {
        "level": level,
        "score": score,
        "basis": basis,
        "best_evidence_tier": best_tier,
        "completeness": {
            "present_dimensions_total": len(present),
            "missing_dimensions_total": len(missing),
            "expected_dimensions_total": expected_total,
            "pct": completeness_pct,
        },
    }


def _freshness(first_date: Any, last_date: Any, snapshot_date: str) -> dict[str, Any]:
    snapshot = _parse_date(snapshot_date)
    first = _parse_date(first_date)
    last = _parse_date(last_date)
    if not snapshot or not last:
        return {
            "level": "unknown",
            "age_days": None,
            "first_date": first.isoformat() if first else None,
            "last_date": last.isoformat() if last else None,
            "basis": "missing dated evidence",
        }
    age_days = max(0, (snapshot - last).days)
    if age_days <= 365:
        level = "current"
    elif age_days <= 1460:
        level = "recent"
    else:
        level = "historical"
    return {
        "level": level,
        "age_days": age_days,
        "first_date": first.isoformat() if first else None,
        "last_date": last.isoformat(),
        "basis": f"latest evidence date compared with snapshot {snapshot.isoformat()}",
    }


def _caveats(entry_kinds: Any) -> list[str]:
    missing = _missing_dimensions(entry_kinds)
    caveats: list[str] = []
    if missing:
        caveats.append("This answer is partial: missing " + ", ".join(missing) + " evidence in this cut.")
    if "parliamentary_actions" in _present_dimensions(entry_kinds):
        caveats.append("Parliamentary group and party rollups are aggregates; person-level votes remain separate evidence.")
    return caveats


def _evidence_ref(entry: dict[str, Any]) -> dict[str, Any]:
    summary = (
        entry.get("summary")
        or entry.get("title")
        or entry.get("issue_label")
        or entry.get("source_title")
    )
    return {
        "entry_id": entry.get("entry_id"),
        "issue_id": entry.get("issue_id"),
        "issue_label": entry.get("issue_label"),
        "actor_label": entry.get("actor_label"),
        "actor_kind": entry.get("actor_kind"),
        "entry_kind": entry.get("entry_kind"),
        "accountability_role": entry.get("accountability_role"),
        "event_date": entry.get("event_date"),
        "evidence_tier": entry.get("evidence_tier"),
        "title": _clip(entry.get("title"), 180),
        "source_title": entry.get("source_title"),
        "source_url": entry.get("source_url"),
        "source_locator": entry.get("source_locator"),
        "evidence_quote": _clip(entry.get("evidence_quote"), 240),
        "summary": _clip(summary, 320),
    }


def _compact_issue_ref(issue: dict[str, Any], limit: int) -> dict[str, Any]:
    return {
        "issue_id": issue.get("issue_id"),
        "entries_total": int(issue.get("entries_total") or 0),
        "role_counts": _top_pairs(issue.get("roles"), limit),
        "entry_kind_counts": _top_pairs(issue.get("entry_kinds"), limit),
        "first_date": issue.get("first_date"),
        "last_date": issue.get("last_date"),
    }


def _compact_actor_ref(actor: dict[str, Any], limit: int) -> dict[str, Any]:
    return {
        "actor_key": actor.get("actor_key"),
        "actor_label": actor.get("actor_label"),
        "actor_kind": actor.get("actor_kind"),
        "entries_total": int(actor.get("entries_total") or 0),
        "role_counts": _top_pairs(actor.get("roles"), limit),
        "entry_kind_counts": _top_pairs(actor.get("entry_kinds"), limit),
        "first_date": actor.get("first_date"),
        "last_date": actor.get("last_date"),
    }


def _summary(label: str, entries_total: Any, issues_or_actors_total: Any, roles: Any, noun: str) -> str:
    role_bits = [f"{item['key']}={item['count']}" for item in _top_pairs(roles, 3)]
    suffix = f" Main roles: {', '.join(role_bits)}." if role_bits else ""
    return f"{label} has {int(entries_total or 0)} accountability entries across {int(issues_or_actors_total or 0)} {noun}.{suffix}"


def _pairs_sentence(pairs: Any, *, label_key: str = "key", limit: int = 3) -> str:
    bits: list[str] = []
    for item in _safe_array(pairs)[:limit]:
        obj = _safe_object(item)
        label = str(obj.get(label_key) or obj.get("label") or obj.get("key") or "").strip()
        if not label:
            continue
        bits.append(f"{label}={int(obj.get('count') or 0)}")
    return ", ".join(bits) if bits else "no breakdown"


def _gap_ref(answer: dict[str, Any], *, kind: str) -> dict[str, Any]:
    if kind == "issue":
        return {
            "answer_id": answer.get("answer_id"),
            "issue_id": answer.get("issue_id"),
            "label": _clip(answer.get("issue_label"), 180),
            "entries_total": int(_safe_object(answer.get("coverage")).get("entries_total") or 0),
            "route": _safe_object(answer.get("routes")).get("dossier"),
        }
    return {
        "answer_id": answer.get("answer_id"),
        "actor_key": answer.get("actor_key"),
        "label": _clip(answer.get("actor_label"), 180),
        "actor_kind": answer.get("actor_kind"),
        "entries_total": int(_safe_object(answer.get("coverage")).get("entries_total") or 0),
        "route": _safe_object(answer.get("routes")).get("dossier"),
    }


def _gap_answers(
    actor_answers: list[dict[str, Any]],
    issue_answers: list[dict[str, Any]],
    *,
    max_samples: int = 3,
) -> list[dict[str, Any]]:
    answers: list[dict[str, Any]] = []
    total_actor_answers = len(actor_answers)
    total_issue_answers = len(issue_answers)
    for dimension, _kind in EXPECTED_DIMENSIONS:
        missing_actor_answers = [answer for answer in actor_answers if dimension in set(_safe_array(answer.get("missing_dimensions")))]
        missing_issue_answers = [answer for answer in issue_answers if dimension in set(_safe_array(answer.get("missing_dimensions")))]
        actor_answers_with_dimension = total_actor_answers - len(missing_actor_answers)
        issue_answers_with_dimension = total_issue_answers - len(missing_issue_answers)
        present_answers_total = actor_answers_with_dimension + issue_answers_with_dimension
        missing_answers_total = len(missing_actor_answers) + len(missing_issue_answers)
        answer_status = "unanswerable" if present_answers_total == 0 else ("partial" if missing_answers_total else "answerable")
        label = DIMENSION_LABELS.get(dimension, dimension.replace("_", " "))
        answers.append(
            {
                "answer_id": f"gap:{dimension}",
                "question_id": "missing_evidence",
                "answer_status": answer_status,
                "dimension": dimension,
                "dimension_label": label,
                "summary": (
                    f"{label} coverage is {answer_status}: missing in {len(missing_issue_answers)} issue answers "
                    f"and {len(missing_actor_answers)} actor answers in this cut."
                ),
                "coverage": {
                    "actor_answers_total": total_actor_answers,
                    "issue_answers_total": total_issue_answers,
                    "actor_answers_missing": len(missing_actor_answers),
                    "issue_answers_missing": len(missing_issue_answers),
                    "actor_answers_with_dimension": actor_answers_with_dimension,
                    "issue_answers_with_dimension": issue_answers_with_dimension,
                    "missing_answers_total": missing_answers_total,
                    "present_answers_total": present_answers_total,
                },
                "next_evidence_needed": NEXT_EVIDENCE_NEEDED.get(dimension, "Additional primary evidence tied to this dimension."),
                "sample_missing_issues": [_gap_ref(answer, kind="issue") for answer in missing_issue_answers[:max_samples]],
                "sample_missing_actors": [_gap_ref(answer, kind="actor") for answer in missing_actor_answers[:max_samples]],
            }
        )
    return answers


def _extract_backtick_paths(text: str) -> list[str]:
    paths: list[str] = []
    for value in re.findall(r"`([^`]+)`", str(text or "")):
        if value.startswith(("docs/", "etl/", "ui/")) and value not in paths:
            paths.append(value)
    return paths


def _extract_next_commands(text: str) -> list[str]:
    commands: list[str] = []
    for value in re.findall(r"Siguiente comando:\s*`([^`]+)`", str(text or "")):
        command = value.strip()
        if command and command not in commands:
            commands.append(command)
    return commands


def _blocker_kind(reason: str) -> str:
    text = _fold_text(reason)
    if "http 403" in text or "403" in text or "access denied" in text:
        return "http_403"
    if "anti-bot" in text or "antihtml" in text or "html anti" in text or "imperva" in text or "waf" in text:
        return "anti_bot_or_waf"
    if "http 500" in text or " 500" in text:
        return "http_500"
    if "token" in text or "contrato" in text or "contract" in text or "api_key" in text:
        return "contract_or_token"
    if "dns" in text:
        return "dns"
    return "blocked_unknown"


def _source_blocker_answers(source_catalog: dict[str, Any] | None, *, max_items: int = 100) -> list[dict[str, Any]]:
    catalog = _safe_object(source_catalog)
    answers: list[dict[str, Any]] = []
    sources = _safe_array(catalog.get("sources"))
    for source in sources:
        row = _safe_object(source)
        if str(row.get("catalog_state") or "") != "blocked":
            continue
        source_id = str(row.get("source_id") or "").strip()
        if not source_id:
            continue
        reason = str(row.get("blocker_reason") or row.get("tracker_block_note") or row.get("last_message") or "").strip()
        action_refs = [
            _safe_object(action)
            for action in _safe_array(catalog.get("actions"))
            if source_id in {str(item) for item in _safe_array(_safe_object(action).get("source_ids"))}
        ]
        action_details = "\n".join(str(action.get("details") or "") for action in action_refs)
        combined_text = "\n".join(part for part in (reason, action_details) if part)
        evidence_paths = _extract_backtick_paths(combined_text)
        commands = _extract_next_commands(combined_text)
        if not commands:
            for action in action_refs:
                commands.extend(str(command) for command in _safe_array(action.get("commands")) if str(command).strip())
        blocker_kind = _blocker_kind(combined_text)
        source_name = str(row.get("source_name") or source_id)
        summary = (
            f"{source_name} is blocked in the source catalog for {row.get('scope') or row.get('level') or 'unknown scope'}; "
            f"blocker kind: {blocker_kind}."
        )
        answers.append(
            {
                "answer_id": f"blocker:{source_id}",
                "question_id": "source_blocker",
                "answer_status": "blocked",
                "source_id": source_id,
                "source_name": source_name,
                "institution_name": row.get("institution_name"),
                "domain": row.get("domain"),
                "scope": row.get("scope") or row.get("level"),
                "catalog_state": row.get("catalog_state"),
                "tracker_status": row.get("tracker_status"),
                "sql_status": row.get("sql_status"),
                "blocker_kind": blocker_kind,
                "summary": _clip(summary, 360),
                "blocker_reason": _clip(reason or action_details, 1200),
                "evidence_refs": [{"path": path} for path in evidence_paths[:8]],
                "next_commands": commands[:3],
                "source_url": row.get("default_url"),
                "latest_snapshot": row.get("latest_snapshot") or row.get("last_seen_at"),
                "coverage": {
                    "runs_total": int(row.get("runs_total") or 0),
                    "runs_ok": int(row.get("runs_ok") or 0),
                    "last_loaded": int(row.get("last_loaded") or 0),
                    "max_loaded_network": int(row.get("max_loaded_network") or 0),
                    "network_fetches": int(row.get("network_fetches") or 0),
                    "fallback_fetches": int(row.get("fallback_fetches") or 0),
                },
                "routes": {
                    "source_catalog": "/explorer-sources/",
                    "datasets": "/methods/datasets/",
                },
                "caveats": [
                    "This is an access/blocker answer from the source catalog; it is not a responsibility claim.",
                    "Open the evidence refs and rerun the next command before treating the blocker as current.",
                ],
            }
        )
        if len(answers) >= int(max_items or 0):
            break
    return answers


def _issue_cluster_issue_review_maps(review_doc: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    cluster_defs: dict[str, dict[str, Any]] = {}
    issue_reviews: dict[str, dict[str, Any]] = {}
    for row in _safe_array(review_doc.get("cluster_definitions")):
        cluster = _safe_object(row)
        cluster_id = str(cluster.get("cluster_id") or "").strip()
        if cluster_id:
            cluster_defs[cluster_id] = cluster
    for row in _safe_array(review_doc.get("issue_reviews")):
        review = _safe_object(row)
        issue_id = str(review.get("issue_id") or "").strip()
        if issue_id:
            issue_reviews[issue_id] = review
    return cluster_defs, issue_reviews


def _reviewed_cluster_label(cluster_id: str, cluster_defs: dict[str, dict[str, Any]]) -> str:
    cluster = _safe_object(cluster_defs.get(cluster_id))
    return str(cluster.get("reviewed_label") or cluster.get("label") or cluster_id).strip()


def _issue_cluster_matches(
    issue_answer: dict[str, Any],
    *,
    cluster_defs: dict[str, dict[str, Any]] | None = None,
    issue_reviews: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    cluster_defs = cluster_defs or {}
    issue_reviews = issue_reviews or {}
    issue_id = str(issue_answer.get("issue_id") or "").strip()
    issue_review = _safe_object(issue_reviews.get(issue_id))
    decision = str(issue_review.get("decision") or "").strip().lower()
    reviewed_cluster_ids = [str(item).strip() for item in _safe_array(issue_review.get("cluster_ids")) if str(item).strip()]
    primary_cluster_id = str(issue_review.get("primary_cluster_id") or "").strip()
    if primary_cluster_id and primary_cluster_id not in reviewed_cluster_ids:
        reviewed_cluster_ids.insert(0, primary_cluster_id)
    if decision in {"set_clusters", "assign"} and reviewed_cluster_ids:
        ordered_cluster_ids: list[str] = []
        for cluster_id in reviewed_cluster_ids:
            if cluster_id not in ordered_cluster_ids:
                ordered_cluster_ids.append(cluster_id)
        return [
            {
                "cluster_id": cluster_id,
                "label": _reviewed_cluster_label(cluster_id, cluster_defs),
                "matched_keywords": [],
                "method": "issue_level_review_v1",
                "issue_review_status": "reviewed",
                "issue_review": {
                    "decision": decision,
                    "reviewer": issue_review.get("reviewer"),
                    "reviewed_at": issue_review.get("reviewed_at"),
                    "rationale": issue_review.get("rationale"),
                    "review_scope": issue_review.get("review_scope") or "source_issue_cluster_assignment",
                },
            }
            for cluster_id in ordered_cluster_ids
        ]

    haystack = _fold_text(f"{issue_answer.get('issue_label') or ''} {issue_answer.get('issue_id') or ''}")
    matches: list[dict[str, Any]] = []
    for rule in ISSUE_CLUSTER_RULES:
        hits = [keyword for keyword in rule["keywords"] if _keyword_in_text(keyword, haystack)]
        if hits:
            matches.append(
                {
                    "cluster_id": rule["cluster_id"],
                    "label": rule["label"],
                    "matched_keywords": hits[:5],
                    "method": "label_keyword_v1",
                }
            )
    if matches:
        return matches
    return [
        {
            "cluster_id": FALLBACK_ISSUE_CLUSTER["cluster_id"],
            "label": FALLBACK_ISSUE_CLUSTER["label"],
            "matched_keywords": [],
            "method": "fallback_manual_grouping_needed_v1",
        }
    ]


def _cluster_issue_ref(issue_answer: dict[str, Any]) -> dict[str, Any]:
    coverage = _safe_object(issue_answer.get("coverage"))
    return {
        "answer_id": issue_answer.get("answer_id"),
        "issue_id": issue_answer.get("issue_id"),
        "label": _clip(issue_answer.get("issue_label"), 200),
        "answer_status": issue_answer.get("answer_status"),
        "entries_total": int(coverage.get("entries_total") or 0),
        "actors_total": int(coverage.get("actors_total") or 0),
        "first_date": coverage.get("first_date"),
        "last_date": coverage.get("last_date"),
        "route": _safe_object(issue_answer.get("routes")).get("dossier"),
        "present_dimensions": _safe_array(issue_answer.get("present_dimensions")),
        "missing_dimensions": _safe_array(issue_answer.get("missing_dimensions")),
    }


def _issue_clusters(
    issue_answers: list[dict[str, Any]],
    *,
    issue_cluster_issue_reviews: dict[str, Any] | None = None,
    max_top_items: int,
    max_evidence_per_cluster: int,
) -> list[dict[str, Any]]:
    cluster_map: dict[str, dict[str, Any]] = {}
    cluster_defs, issue_reviews = _issue_cluster_issue_review_maps(_safe_object(issue_cluster_issue_reviews))

    for issue_answer in issue_answers:
        matches = _issue_cluster_matches(issue_answer, cluster_defs=cluster_defs, issue_reviews=issue_reviews)
        issue_answer["primary_issue_cluster_id"] = matches[0]["cluster_id"]
        issue_answer["issue_cluster_ids"] = [match["cluster_id"] for match in matches]
        issue_answer["issue_cluster_matches"] = matches
        reviewed_assignment = next((match for match in matches if match.get("issue_review_status") == "reviewed"), None)
        if reviewed_assignment:
            issue_answer["issue_cluster_assignment_review_status"] = "reviewed"
            issue_answer["issue_cluster_assignment_review"] = _safe_object(reviewed_assignment.get("issue_review"))

        coverage = _safe_object(issue_answer.get("coverage"))
        entries_total = int(coverage.get("entries_total") or 0)
        actors_total = int(coverage.get("actors_total") or 0)
        for match in matches:
            cluster_id = str(match["cluster_id"])
            method_id = str(match.get("method") or "label_keyword_v1")
            cluster_def = _safe_object(cluster_defs.get(cluster_id))
            cluster_review = {
                "decision": cluster_def.get("decision") or "accept",
                "review_status": cluster_def.get("review_status") or "reviewed",
                "reviewed_label": cluster_def.get("reviewed_label") or cluster_def.get("label") or match.get("label"),
                "original_label": cluster_def.get("original_label") or match.get("label"),
                "reviewer": cluster_def.get("reviewer"),
                "reviewed_at": cluster_def.get("reviewed_at"),
                "review_scope": cluster_def.get("review_scope") or "public_bucket_label",
                "rationale": cluster_def.get("rationale"),
                "caveat": cluster_def.get("caveat"),
            } if cluster_def else {}
            cluster = cluster_map.setdefault(
                cluster_id,
                {
                    "cluster_id": cluster_id,
                    "label": match.get("label"),
                    "method": {
                        "method_id": method_id,
                        "confidence": "reviewed" if method_id == "issue_level_review_v1" else "heuristic",
                        "membership_confidence": "reviewed" if method_id == "issue_level_review_v1" else "heuristic",
                        "basis": (
                            "issue-level reviewed source issue assignment"
                            if method_id == "issue_level_review_v1"
                            else "deterministic keyword match over source-native issue label and ID"
                        ),
                        "requires_review": method_id != "issue_level_review_v1",
                    },
                    "review_status": "reviewed" if method_id == "issue_level_review_v1" else "needs_review",
                    "review": cluster_review,
                    "matched_keywords": Counter(),
                    "match_method_counts": Counter(),
                    "issue_review_status_counts": Counter(),
                    "issues": [],
                    "issue_ids": set(),
                    "entries_total": 0,
                    "actors_total_sum": 0,
                    "first_date": None,
                    "last_date": None,
                    "role_counts": Counter(),
                    "entry_kind_counts": Counter(),
                    "actor_kind_counts": Counter(),
                    "present_dimensions": set(),
                    "actor_refs": {},
                    "evidence_samples": [],
                },
            )
            cluster["match_method_counts"][method_id] += 1
            cluster["issue_review_status_counts"][str(match.get("issue_review_status") or "heuristic")] += 1
            cluster["issues"].append(_cluster_issue_ref(issue_answer))
            cluster["issue_ids"].add(issue_answer.get("issue_id"))
            cluster["entries_total"] += entries_total
            cluster["actors_total_sum"] += actors_total
            first_date = coverage.get("first_date")
            last_date = coverage.get("last_date")
            if first_date and (not cluster["first_date"] or str(first_date) < str(cluster["first_date"])):
                cluster["first_date"] = first_date
            if last_date and (not cluster["last_date"] or str(last_date) > str(cluster["last_date"])):
                cluster["last_date"] = last_date
            for keyword in _safe_array(match.get("matched_keywords")):
                cluster["matched_keywords"][str(keyword)] += 1
            _merge_pairs(cluster["role_counts"], issue_answer.get("role_counts"))
            _merge_pairs(cluster["entry_kind_counts"], issue_answer.get("entry_kind_counts"))
            _merge_pairs(cluster["actor_kind_counts"], issue_answer.get("actor_kind_counts"))
            cluster["present_dimensions"].update(str(item) for item in _safe_array(issue_answer.get("present_dimensions")))
            for actor in _safe_array(issue_answer.get("top_actors"))[:max_top_items]:
                actor_obj = _safe_object(actor)
                actor_key = str(actor_obj.get("actor_key") or actor_obj.get("actor_label") or "").strip()
                if not actor_key:
                    continue
                ref = cluster["actor_refs"].setdefault(
                    actor_key,
                    {
                        "actor_key": actor_obj.get("actor_key"),
                        "actor_label": actor_obj.get("actor_label"),
                        "actor_kind": actor_obj.get("actor_kind"),
                        "entries_total": 0,
                        "role_counts": Counter(),
                    },
                )
                ref["entries_total"] += int(actor_obj.get("entries_total") or 0)
                _merge_pairs(ref["role_counts"], actor_obj.get("role_counts"))
            if len(cluster["evidence_samples"]) < max_evidence_per_cluster:
                for sample in _safe_array(issue_answer.get("evidence_samples")):
                    if len(cluster["evidence_samples"]) >= max_evidence_per_cluster:
                        break
                    cluster["evidence_samples"].append(sample)

    clusters: list[dict[str, Any]] = []
    expected_dimensions = {dimension for dimension, _kind in EXPECTED_DIMENSIONS}
    for cluster in cluster_map.values():
        present_dimensions = sorted(cluster["present_dimensions"])
        missing_dimensions = [dimension for dimension, _kind in EXPECTED_DIMENSIONS if dimension not in present_dimensions]
        answer_status = "answerable" if not missing_dimensions and cluster["entries_total"] > 0 else "partial"
        actor_refs = sorted(
            cluster["actor_refs"].values(),
            key=lambda item: (-int(item.get("entries_total") or 0), str(item.get("actor_label") or item.get("actor_key") or "")),
        )
        top_actors = [
            {
                "actor_key": ref.get("actor_key"),
                "actor_label": ref.get("actor_label"),
                "actor_kind": ref.get("actor_kind"),
                "entries_total": int(ref.get("entries_total") or 0),
                "role_counts": _top_pairs(ref.get("role_counts"), max_top_items),
            }
            for ref in actor_refs[:max_top_items]
        ]
        top_issues = sorted(
            cluster["issues"],
            key=lambda item: (-int(item.get("entries_total") or 0), str(item.get("label") or item.get("issue_id") or "")),
        )[:max_top_items]
        clusters.append(
            {
                "cluster_id": cluster["cluster_id"],
                "label": cluster["label"],
                "answer_status": answer_status,
                "summary": (
                    f"{cluster['label']} groups {len(cluster['issue_ids'])} source-native issues "
                    f"with {int(cluster['entries_total'])} accountability entries."
                ),
                "coverage": {
                    "issues_total": len(cluster["issue_ids"]),
                    "entries_total": int(cluster["entries_total"]),
                    "actors_total_sum": int(cluster["actors_total_sum"]),
                    "top_actor_refs_total": len(actor_refs),
                    "issue_membership_reviewed_links_total": int(cluster["issue_review_status_counts"].get("reviewed") or 0),
                    "issue_membership_heuristic_links_total": sum(
                        int(value or 0)
                        for key, value in cluster["issue_review_status_counts"].items()
                        if key != "reviewed"
                    ),
                    "first_date": cluster["first_date"],
                    "last_date": cluster["last_date"],
                    "source_issue_grain": "source-native issues grouped by deterministic keyword rules",
                },
                "method": cluster["method"],
                "review_status": cluster.get("review_status") or "needs_review",
                "review": cluster.get("review") or {},
                "matched_keywords": _top_pairs(cluster["matched_keywords"], max_top_items),
                "match_method_counts": _top_pairs(cluster["match_method_counts"], max_top_items),
                "issue_review_status_counts": _top_pairs(cluster["issue_review_status_counts"], max_top_items),
                "role_counts": _top_pairs(cluster["role_counts"], max_top_items),
                "entry_kind_counts": _top_pairs(cluster["entry_kind_counts"], max_top_items),
                "actor_kind_counts": _top_pairs(cluster["actor_kind_counts"], max_top_items),
                "present_dimensions": present_dimensions,
                "missing_dimensions": [dimension for dimension in missing_dimensions if dimension in expected_dimensions],
                "top_issues": top_issues,
                "top_actors": top_actors,
                "evidence_samples": cluster["evidence_samples"],
                "caveats": [
                    (
                        "Issue membership has been reviewed for this cluster."
                        if int(cluster["issue_review_status_counts"].get("reviewed") or 0) == len(cluster["issue_ids"])
                        else "Some issue membership still comes from deterministic keyword matching."
                    ),
                    "Counts can overlap across clusters when a source-native issue matches multiple public themes.",
                ],
            }
        )
    return sorted(clusters, key=lambda item: (-int(_safe_object(item.get("coverage")).get("entries_total") or 0), str(item.get("label") or "")))


def _issue_cluster_review_queue(issue_clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    review_items: list[dict[str, Any]] = []
    for cluster in issue_clusters:
        cluster_id = str(cluster.get("cluster_id") or "").strip()
        if not cluster_id:
            continue
        coverage = _safe_object(cluster.get("coverage"))
        method = _safe_object(cluster.get("method"))
        review = _safe_object(cluster.get("review"))
        review_status = str(cluster.get("review_status") or "").strip()
        requires_review = review_status != "reviewed"
        review_items.append(
            {
                "review_id": f"issue-cluster-review:{cluster_id}",
                "cluster_id": cluster_id,
                "label": cluster.get("label"),
                "review_status": review_status or ("needs_review" if requires_review else "reviewed"),
                "review_prompt": (
                    "Public bucket label reviewed; issue membership still needs issue-level adjudication."
                    if not requires_review
                    else "Accept, rename, split, merge, or reject this heuristic cluster before treating it as a reviewed public topic."
                ),
                "coverage": {
                    "issues_total": int(coverage.get("issues_total") or 0),
                    "entries_total": int(coverage.get("entries_total") or 0),
                    "first_date": coverage.get("first_date"),
                    "last_date": coverage.get("last_date"),
                },
                "method": method,
                "review": review,
                "matched_keywords": _safe_array(cluster.get("matched_keywords"))[:5],
                "sample_issues": _safe_array(cluster.get("top_issues"))[:5],
                "sample_actors": _safe_array(cluster.get("top_actors"))[:3],
                "expected_decision_fields": [
                    "decision",
                    "reviewed_label",
                    "merge_into_cluster_id",
                    "split_notes",
                    "reviewer",
                    "reviewed_at",
                ],
            }
        )
    return review_items


def _issue_cluster_match_ref(match: dict[str, Any]) -> dict[str, Any]:
    return {
        "cluster_id": match.get("cluster_id"),
        "label": match.get("label"),
        "method": match.get("method"),
        "issue_review_status": match.get("issue_review_status") or "heuristic",
        "matched_keywords": _safe_array(match.get("matched_keywords"))[:5],
    }


def _issue_cluster_assignment_review_queue(
    issue_answers: list[dict[str, Any]],
    *,
    max_items: int,
) -> tuple[list[dict[str, Any]], int]:
    candidates: list[dict[str, Any]] = []
    for answer in issue_answers:
        if answer.get("issue_cluster_assignment_review_status") == "reviewed":
            continue
        issue_id = str(answer.get("issue_id") or "").strip()
        if not issue_id:
            continue
        coverage = _safe_object(answer.get("coverage"))
        matches = [_issue_cluster_match_ref(_safe_object(match)) for match in _safe_array(answer.get("issue_cluster_matches"))]
        candidates.append(
            {
                "review_id": f"issue-cluster-assignment-review:{issue_id}",
                "issue_id": issue_id,
                "answer_id": answer.get("answer_id"),
                "label": _clip(answer.get("issue_label"), 220),
                "review_status": "needs_review",
                "review_prompt": "Confirm, replace, split, or merge this source-native issue assignment before treating membership as reviewed.",
                "primary_cluster_id": answer.get("primary_issue_cluster_id"),
                "cluster_ids": _safe_array(answer.get("issue_cluster_ids")),
                "current_matches": matches,
                "coverage": {
                    "entries_total": int(coverage.get("entries_total") or 0),
                    "actors_total": int(coverage.get("actors_total") or 0),
                    "first_date": coverage.get("first_date"),
                    "last_date": coverage.get("last_date"),
                },
                "routes": {"dossier": _safe_object(answer.get("routes")).get("dossier")},
                "expected_decision_fields": [
                    "decision",
                    "primary_cluster_id",
                    "cluster_ids",
                    "reviewer",
                    "reviewed_at",
                    "rationale",
                ],
            }
        )

    candidates.sort(
        key=lambda item: (
            -int(_safe_object(item.get("coverage")).get("entries_total") or 0),
            str(item.get("label") or item.get("issue_id") or ""),
        )
    )
    limit = max(0, int(max_items or 0))
    if limit <= 0:
        return [], len(candidates)
    return candidates[:limit], len(candidates)


def _issue_cluster_review_decisions(review_doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    decisions: dict[str, dict[str, Any]] = {}
    for row in _safe_array(review_doc.get("reviews")):
        review = _safe_object(row)
        cluster_id = str(review.get("cluster_id") or "").strip()
        if not cluster_id:
            continue
        decisions[cluster_id] = review
    return decisions


def _apply_issue_cluster_reviews(
    issue_clusters: list[dict[str, Any]],
    issue_answers: list[dict[str, Any]],
    review_doc: dict[str, Any],
) -> list[dict[str, Any]]:
    decisions = _issue_cluster_review_decisions(review_doc)
    if not decisions:
        for cluster in issue_clusters:
            if str(cluster.get("review_status") or "") != "reviewed":
                cluster["review_status"] = "needs_review"
        return issue_clusters

    for cluster in issue_clusters:
        cluster_id = str(cluster.get("cluster_id") or "").strip()
        method = _safe_object(cluster.get("method"))
        review = decisions.get(cluster_id)
        if not review:
            if str(cluster.get("review_status") or "") == "reviewed":
                continue
            cluster["review_status"] = "needs_review"
            method["requires_review"] = True
            cluster["method"] = method
            continue

        decision = str(review.get("decision") or "").strip().lower()
        reviewed_label = str(review.get("reviewed_label") or cluster.get("label") or cluster_id).strip()
        review_scope = str(review.get("review_scope") or "public_bucket_label").strip()
        review_payload = {
            "decision": decision,
            "review_status": "reviewed" if decision in {"accept", "rename"} else "needs_revision",
            "reviewed_label": reviewed_label,
            "original_label": cluster.get("label"),
            "reviewer": review.get("reviewer"),
            "reviewed_at": review.get("reviewed_at"),
            "review_scope": review_scope,
            "rationale": review.get("rationale"),
            "caveat": review.get("caveat"),
        }

        if decision in {"accept", "rename"}:
            cluster["label"] = reviewed_label
            cluster["summary"] = (
                f"{reviewed_label} groups {int(_safe_object(cluster.get('coverage')).get('issues_total') or 0)} "
                f"source-native issues with {int(_safe_object(cluster.get('coverage')).get('entries_total') or 0)} "
                "accountability entries."
            )
            cluster["review_status"] = "reviewed"
            method["confidence"] = "reviewed"
            method["membership_confidence"] = "heuristic"
            method["requires_review"] = False
            method["review_scope"] = review_scope
            method["review_decision"] = decision
            method["basis"] = "reviewed public bucket label over deterministic keyword membership"
            cluster["caveats"] = [
                "Cluster public label has been reviewed; issue membership still comes from deterministic keyword matching.",
                "Counts can overlap across clusters when a source-native issue matches multiple public themes.",
            ]
        else:
            cluster["review_status"] = "needs_revision"
            method["requires_review"] = True
        cluster["method"] = method
        cluster["review"] = review_payload

    labels_by_cluster = {str(cluster.get("cluster_id")): cluster.get("label") for cluster in issue_clusters}
    for answer in issue_answers:
        for match in _safe_array(answer.get("issue_cluster_matches")):
            obj = _safe_object(match)
            cluster_id = str(obj.get("cluster_id") or "")
            if cluster_id in labels_by_cluster:
                obj["label"] = labels_by_cluster[cluster_id]
    return issue_clusters


def _qa_base(
    *,
    answer_id: str,
    source_collection: str,
    source_answer_id: str,
    question: str,
    answer_text: str,
    answer_status: str,
    evidence_basis: dict[str, Any],
    routes: dict[str, Any] | None = None,
    caveats: list[str] | None = None,
) -> dict[str, Any]:
    route_map = dict(routes or {})
    route_map.setdefault("self", _qa_route(answer_id))
    return {
        "answer_id": answer_id,
        "question_id": "natural_language_qa",
        "source_collection": source_collection,
        "source_answer_id": source_answer_id,
        "question": _clip(question, 260),
        "answer_text": _clip(answer_text, 900),
        "answer_status": answer_status,
        "evidence_basis": evidence_basis,
        "routes": route_map,
        "caveats": list(caveats or []),
    }


def _qa_answers(
    *,
    actor_answers: list[dict[str, Any]],
    issue_answers: list[dict[str, Any]],
    actor_issue_refs: list[dict[str, Any]],
    issue_clusters: list[dict[str, Any]],
    gap_answers: list[dict[str, Any]],
    blocker_answers: list[dict[str, Any]],
    max_qa_answers: int,
) -> list[dict[str, Any]]:
    answers: list[dict[str, Any]] = []
    max_total = int(max_qa_answers or 0)
    if max_total <= 0:
        return answers

    for cluster in issue_clusters[:6]:
        if len(answers) >= max_total:
            return answers
        coverage = _safe_object(cluster.get("coverage"))
        label = str(cluster.get("label") or cluster.get("cluster_id") or "cluster")
        method = _safe_object(cluster.get("method"))
        route = ""
        top_issues = _safe_array(cluster.get("top_issues"))
        if top_issues:
            route = str(_safe_object(top_issues[0]).get("route") or "")
        answers.append(
            _qa_base(
                answer_id=f"qa:cluster:{cluster.get('cluster_id')}",
                source_collection="issue_clusters",
                source_answer_id=str(cluster.get("cluster_id") or ""),
                question=f"Que sabemos ya sobre {label}?",
                answer_text=(
                    f"{label} is answerable only as a partial cluster in this cut. It groups "
                    f"{int(coverage.get('issues_total') or 0)} source-native issues and "
                    f"{int(coverage.get('entries_total') or 0)} accountability entries. "
                    f"Main roles: {_pairs_sentence(cluster.get('role_counts'))}. "
                    f"Method: {method.get('basis') or 'deterministic grouping'}."
                ),
                answer_status=str(cluster.get("answer_status") or "partial"),
                evidence_basis={
                    "issues_total": int(coverage.get("issues_total") or 0),
                    "entries_total": int(coverage.get("entries_total") or 0),
                    "first_date": coverage.get("first_date"),
                    "last_date": coverage.get("last_date"),
                    "method_id": method.get("method_id"),
                    "source_issue_grain": coverage.get("source_issue_grain"),
                },
                routes={"primary": route} if route else {},
                caveats=_safe_array(cluster.get("caveats"))[:2],
            )
        )

    for issue in issue_answers[:4]:
        if len(answers) >= max_total:
            return answers
        coverage = _safe_object(issue.get("coverage"))
        label = str(issue.get("issue_label") or issue.get("issue_id") or "issue")
        confidence = _safe_object(issue.get("confidence"))
        freshness = _safe_object(issue.get("freshness"))
        answers.append(
            _qa_base(
                answer_id=f"qa:issue:{issue.get('issue_id')}",
                source_collection="issue_answers",
                source_answer_id=str(issue.get("answer_id") or ""),
                question=f"Que actores tocaron {label}?",
                answer_text=(
                    f"{label} has {int(coverage.get('entries_total') or 0)} accountability entries "
                    f"across {int(coverage.get('actors_total') or 0)} actors in this snapshot. "
                    f"Main roles: {_pairs_sentence(issue.get('role_counts'))}. "
                    f"Confidence is {confidence.get('level') or 'unknown'} and freshness is "
                    f"{freshness.get('level') or 'unknown'}."
                ),
                answer_status=str(issue.get("answer_status") or "partial"),
                evidence_basis={
                    "entries_total": int(coverage.get("entries_total") or 0),
                    "actors_total": int(coverage.get("actors_total") or 0),
                    "first_date": coverage.get("first_date"),
                    "last_date": coverage.get("last_date"),
                    "confidence": confidence.get("level"),
                    "freshness": freshness.get("level"),
                    "present_dimensions": _safe_array(issue.get("present_dimensions")),
                    "missing_dimensions": _safe_array(issue.get("missing_dimensions")),
                },
                routes={"primary": _safe_object(issue.get("routes")).get("dossier")},
                caveats=_safe_array(issue.get("caveats"))[:2],
            )
        )

    for actor in actor_answers[:4]:
        if len(answers) >= max_total:
            return answers
        coverage = _safe_object(actor.get("coverage"))
        label = str(actor.get("actor_label") or actor.get("actor_key") or "actor")
        confidence = _safe_object(actor.get("confidence"))
        freshness = _safe_object(actor.get("freshness"))
        answers.append(
            _qa_base(
                answer_id=f"qa:actor:{actor.get('actor_key')}",
                source_collection="actor_answers",
                source_answer_id=str(actor.get("answer_id") or ""),
                question=f"Que hizo {label} a traves del tiempo?",
                answer_text=(
                    f"{label} has {int(coverage.get('entries_total') or 0)} accountability entries "
                    f"across {int(coverage.get('issues_total') or 0)} issues. "
                    f"Main roles: {_pairs_sentence(actor.get('role_counts'))}. "
                    f"Confidence is {confidence.get('level') or 'unknown'} and freshness is "
                    f"{freshness.get('level') or 'unknown'}."
                ),
                answer_status=str(actor.get("answer_status") or "partial"),
                evidence_basis={
                    "entries_total": int(coverage.get("entries_total") or 0),
                    "issues_total": int(coverage.get("issues_total") or 0),
                    "first_date": coverage.get("first_date"),
                    "last_date": coverage.get("last_date"),
                    "confidence": confidence.get("level"),
                    "freshness": freshness.get("level"),
                    "actor_kind": actor.get("actor_kind"),
                    "present_dimensions": _safe_array(actor.get("present_dimensions")),
                    "missing_dimensions": _safe_array(actor.get("missing_dimensions")),
                },
                routes={"primary": _safe_object(actor.get("routes")).get("dossier")},
                caveats=_safe_array(actor.get("caveats"))[:2],
            )
        )

    for ref in actor_issue_refs[:4]:
        if len(answers) >= max_total:
            return answers
        actor_label = str(ref.get("actor_label") or ref.get("actor_key") or "actor")
        issue_label = str(ref.get("issue_label") or ref.get("issue_id") or "issue")
        entries_total = int(ref.get("entries_total") or 0)
        answers.append(
            _qa_base(
                answer_id=f"qa:actor_issue:{ref.get('actor_key')}:{ref.get('issue_id')}",
                source_collection="actor_issue_refs",
                source_answer_id=str(ref.get("answer_id") or ""),
                question=f"Que hizo {actor_label} en {issue_label}?",
                answer_text=(
                    f"{actor_label} has {entries_total} accountability entries on {issue_label} "
                    f"in this bounded actor-issue cut. Main roles: {_pairs_sentence(ref.get('role_counts'))}. "
                    f"Evidence dates: {ref.get('first_date') or 'unknown'} to {ref.get('last_date') or 'unknown'}."
                ),
                answer_status=str(ref.get("answer_status") or "partial"),
                evidence_basis={
                    "actor_key": ref.get("actor_key"),
                    "actor_kind": ref.get("actor_kind"),
                    "issue_id": ref.get("issue_id"),
                    "entries_total": entries_total,
                    "first_date": ref.get("first_date"),
                    "last_date": ref.get("last_date"),
                },
                routes={
                    "actor": _safe_object(ref.get("routes")).get("actor_dossier"),
                    "issue": _safe_object(ref.get("routes")).get("issue_dossier"),
                    "primary": _safe_object(ref.get("routes")).get("issue_dossier"),
                },
                caveats=["Actor-issue refs are bounded summaries; open the linked dossiers for sampled evidence."],
            )
        )

    for blocker in blocker_answers[:6]:
        if len(answers) >= max_total:
            return answers
        coverage = _safe_object(blocker.get("coverage"))
        answers.append(
            _qa_base(
                answer_id=f"qa:blocker:{blocker.get('source_id')}",
                source_collection="blocker_answers",
                source_answer_id=str(blocker.get("answer_id") or ""),
                question=f"Que bloquea la fuente {blocker.get('source_name') or blocker.get('source_id')}?",
                answer_text=(
                    f"{blocker.get('source_name') or blocker.get('source_id')} is marked blocked in the source catalog. "
                    f"Kind: {blocker.get('blocker_kind') or 'blocked_unknown'}. "
                    f"Scope: {blocker.get('scope') or 'unknown'}. "
                    f"Runs: {int(coverage.get('runs_total') or 0)}, network fetches: "
                    f"{int(coverage.get('network_fetches') or 0)}."
                ),
                answer_status="blocked",
                evidence_basis={
                    "source_id": blocker.get("source_id"),
                    "scope": blocker.get("scope"),
                    "domain": blocker.get("domain"),
                    "blocker_kind": blocker.get("blocker_kind"),
                    "evidence_refs_total": len(_safe_array(blocker.get("evidence_refs"))),
                },
                routes={"primary": _safe_object(blocker.get("routes")).get("source_catalog")},
                caveats=_safe_array(blocker.get("caveats"))[:2],
            )
        )

    prioritized_gaps = sorted(
        gap_answers,
        key=lambda answer: (
            0 if str(answer.get("answer_status") or "") == "unanswerable" else 1,
            str(answer.get("dimension") or ""),
        ),
    )
    for gap in prioritized_gaps:
        if len(answers) >= max_total:
            return answers
        coverage = _safe_object(gap.get("coverage"))
        label = str(gap.get("dimension_label") or gap.get("dimension") or "dimension")
        answers.append(
            _qa_base(
                answer_id=f"qa:gap:{gap.get('dimension')}",
                source_collection="gap_answers",
                source_answer_id=str(gap.get("answer_id") or ""),
                question=f"Que falta para contestar {label}?",
                answer_text=(
                    f"{label} is {gap.get('answer_status') or 'partial'} in this cut. It is missing in "
                    f"{int(coverage.get('issue_answers_missing') or 0)} issue answers and "
                    f"{int(coverage.get('actor_answers_missing') or 0)} actor answers. "
                    f"Next evidence needed: {gap.get('next_evidence_needed') or 'additional primary evidence'}"
                ),
                answer_status=str(gap.get("answer_status") or "partial"),
                evidence_basis={
                    "dimension": gap.get("dimension"),
                    "issue_answers_missing": int(coverage.get("issue_answers_missing") or 0),
                    "actor_answers_missing": int(coverage.get("actor_answers_missing") or 0),
                    "present_answers_total": int(coverage.get("present_answers_total") or 0),
                },
                caveats=["This is a gap answer, not a responsibility claim."],
            )
        )
    return answers


def build_evidence_api(
    dossiers: dict[str, Any],
    ledger: dict[str, Any],
    *,
    snapshot_date: str,
    issue_cluster_reviews: dict[str, Any] | None = None,
    issue_cluster_issue_reviews: dict[str, Any] | None = None,
    source_catalog: dict[str, Any] | None = None,
    max_actor_answers: int = 5000,
    max_issue_answers: int = 5000,
    max_actor_issue_refs: int = 12000,
    max_issue_cluster_assignment_review_items: int = 250,
    max_top_items: int = 12,
    max_evidence_per_answer: int = 3,
    max_qa_answers: int = 32,
    max_blocker_answers: int = 100,
) -> dict[str, Any]:
    actors = _safe_array(dossiers.get("actors"))[: int(max_actor_answers or 0) or None]
    issues = _safe_array(dossiers.get("issues"))[: int(max_issue_answers or 0) or None]
    ledger_actors = {str(actor.get("actor_key") or ""): actor for actor in _safe_array(ledger.get("actors"))}
    ledger_issues = {str(issue.get("issue_id") or ""): issue for issue in _safe_array(ledger.get("issues"))}
    status_counts: Counter[str] = Counter()

    actor_answers: list[dict[str, Any]] = []
    confidence_counts: Counter[str] = Counter()
    freshness_counts: Counter[str] = Counter()
    for actor in actors:
        actor_key = str(actor.get("actor_key") or "")
        ledger_actor = _safe_object(ledger_actors.get(actor_key))
        evidence_samples = [_evidence_ref(_safe_object(entry)) for entry in _safe_array(ledger_actor.get("sample_entries"))[:max_evidence_per_answer]]
        status = _answer_status(actor.get("entry_kinds"), actor.get("entries_total"))
        confidence = _confidence(actor.get("entry_kinds"), actor.get("entries_total"), evidence_samples)
        freshness = _freshness(actor.get("first_date"), actor.get("last_date"), snapshot_date)
        status_counts[status] += 1
        confidence_counts[str(confidence.get("level") or "unknown")] += 1
        freshness_counts[str(freshness.get("level") or "unknown")] += 1
        actor_answers.append(
            {
                "answer_id": f"actor:{actor_key}",
                "question_id": "actor_historical_record",
                "answer_status": status,
                "actor_key": actor_key,
                "actor_label": actor.get("actor_label"),
                "actor_kind": actor.get("actor_kind"),
                "summary": _summary(
                    str(actor.get("actor_label") or actor_key),
                    actor.get("entries_total"),
                    actor.get("issues_total"),
                    actor.get("roles"),
                    "issues",
                ),
                "coverage": {
                    "entries_total": int(actor.get("entries_total") or 0),
                    "issues_total": int(actor.get("issues_total") or 0),
                    "first_date": actor.get("first_date"),
                    "last_date": actor.get("last_date"),
                },
                "identity": {
                    key: actor.get(key)
                    for key in (
                        "person_id",
                        "party_id",
                        "parliamentary_group_id",
                        "institution_id",
                        "org_unit_id",
                        "position_id",
                    )
                    if actor.get(key) is not None
                },
                "role_counts": _top_pairs(actor.get("roles"), max_top_items),
                "entry_kind_counts": _top_pairs(actor.get("entry_kinds"), max_top_items),
                "present_dimensions": _present_dimensions(actor.get("entry_kinds")),
                "missing_dimensions": _missing_dimensions(actor.get("entry_kinds")),
                "confidence": confidence,
                "freshness": freshness,
                "caveats": _caveats(actor.get("entry_kinds")),
                "top_issues": [_compact_issue_ref(_safe_object(issue), max_top_items) for issue in _safe_array(actor.get("top_issues"))[:max_top_items]],
                "evidence_samples": evidence_samples,
                "routes": {"dossier": _actor_route(actor)},
            }
        )

    issue_answers: list[dict[str, Any]] = []
    for issue in issues:
        issue_id = str(issue.get("issue_id") or "")
        ledger_issue = _safe_object(ledger_issues.get(issue_id))
        evidence_samples = [
            _evidence_ref({**_safe_object(entry), "issue_id": issue_id, "issue_label": issue.get("label")})
            for entry in _safe_array(ledger_issue.get("entries"))[:max_evidence_per_answer]
        ]
        status = _answer_status(issue.get("entry_kinds"), issue.get("entries_total"))
        confidence = _confidence(issue.get("entry_kinds"), issue.get("entries_total"), evidence_samples)
        freshness = _freshness(issue.get("first_date"), issue.get("last_date"), snapshot_date)
        status_counts[status] += 1
        confidence_counts[str(confidence.get("level") or "unknown")] += 1
        freshness_counts[str(freshness.get("level") or "unknown")] += 1
        issue_answers.append(
            {
                "answer_id": f"issue:{issue_id}",
                "question_id": "issue_involved_actors",
                "answer_status": status,
                "issue_id": issue_id,
                "issue_label": issue.get("label"),
                "summary": _summary(
                    str(issue.get("label") or issue_id),
                    issue.get("entries_total"),
                    issue.get("actors_total"),
                    issue.get("roles"),
                    "actors",
                ),
                "coverage": {
                    "entries_total": int(issue.get("entries_total") or 0),
                    "actors_total": int(issue.get("actors_total") or 0),
                    "first_date": issue.get("first_date"),
                    "last_date": issue.get("last_date"),
                    "scope": issue.get("scope"),
                },
                "role_counts": _top_pairs(issue.get("roles"), max_top_items),
                "entry_kind_counts": _top_pairs(issue.get("entry_kinds"), max_top_items),
                "actor_kind_counts": _top_pairs(issue.get("actor_kinds"), max_top_items),
                "present_dimensions": _present_dimensions(issue.get("entry_kinds")),
                "missing_dimensions": _missing_dimensions(issue.get("entry_kinds")),
                "confidence": confidence,
                "freshness": freshness,
                "caveats": _caveats(issue.get("entry_kinds")),
                "top_actors": [_compact_actor_ref(_safe_object(actor), max_top_items) for actor in _safe_array(issue.get("top_actors"))[:max_top_items]],
                "evidence_samples": evidence_samples,
                "routes": {"dossier": _issue_route(issue)},
            }
        )

    issue_clusters = _issue_clusters(
        issue_answers,
        issue_cluster_issue_reviews=issue_cluster_issue_reviews,
        max_top_items=max_top_items,
        max_evidence_per_cluster=max_evidence_per_answer,
    )
    review_doc = _safe_object(issue_cluster_reviews)
    issue_clusters = _apply_issue_cluster_reviews(issue_clusters, issue_answers, review_doc)
    issue_cluster_review_queue = _issue_cluster_review_queue(issue_clusters)
    issue_cluster_review_status_counts = Counter(
        str(item.get("review_status") or "unknown") for item in issue_cluster_review_queue
    )
    fallback_cluster_id = str(FALLBACK_ISSUE_CLUSTER["cluster_id"])
    fallback_issue_answers_total = sum(
        1 for answer in issue_answers if str(answer.get("primary_issue_cluster_id") or "") == fallback_cluster_id
    )
    issue_cluster_links_total = sum(len(_safe_array(answer.get("issue_cluster_ids"))) for answer in issue_answers)
    issue_cluster_issue_reviews_applied_total = sum(
        1 for answer in issue_answers if answer.get("issue_cluster_assignment_review_status") == "reviewed"
    )
    issue_cluster_reviewed_links_total = sum(
        1
        for answer in issue_answers
        for match in _safe_array(answer.get("issue_cluster_matches"))
        if _safe_object(match).get("issue_review_status") == "reviewed"
    )
    issue_cluster_assignment_review_queue, issue_cluster_assignment_review_needed_total = (
        _issue_cluster_assignment_review_queue(
            issue_answers,
            max_items=max_issue_cluster_assignment_review_items,
        )
    )

    issue_route_by_id = {answer["issue_id"]: answer["routes"]["dossier"] for answer in issue_answers}
    actor_issue_refs: list[dict[str, Any]] = []
    for actor in actors:
        actor_key = str(actor.get("actor_key") or "")
        for issue in _safe_array(actor.get("top_issues"))[:max_top_items]:
            issue_id = str(issue.get("issue_id") or "")
            actor_issue_refs.append(
                {
                    "answer_id": f"actor_issue:{actor_key}:{issue_id}",
                    "question_id": "actor_issue_record",
                    "answer_status": _answer_status(issue.get("entry_kinds"), issue.get("entries_total")),
                    "actor_key": actor_key,
                    "actor_label": actor.get("actor_label"),
                    "actor_kind": actor.get("actor_kind"),
                    "issue_id": issue_id,
                    "issue_label": _clip(issue.get("issue_label"), 240),
                    "entries_total": int(issue.get("entries_total") or 0),
                    "role_counts": _top_pairs(issue.get("roles"), max_top_items),
                    "entry_kind_counts": _top_pairs(issue.get("entry_kinds"), max_top_items),
                    "first_date": issue.get("first_date"),
                    "last_date": issue.get("last_date"),
                    "routes": {
                        "actor_dossier": _actor_route(actor),
                        "issue_dossier": issue_route_by_id.get(issue_id),
                    },
                }
            )
            if len(actor_issue_refs) >= max_actor_issue_refs:
                break
        if len(actor_issue_refs) >= max_actor_issue_refs:
            break

    evidence_samples_total = sum(len(answer["evidence_samples"]) for answer in actor_answers) + sum(
        len(answer["evidence_samples"]) for answer in issue_answers
    )
    gap_answers = _gap_answers(actor_answers, issue_answers, max_samples=max_top_items)
    gap_status_counts = Counter(str(answer.get("answer_status") or "unknown") for answer in gap_answers)
    gap_dimension_counts = {
        str(answer.get("dimension")): int(_safe_object(answer.get("coverage")).get("missing_answers_total") or 0)
        for answer in gap_answers
    }
    blocker_answers = _source_blocker_answers(source_catalog, max_items=max_blocker_answers)
    blocker_status_counts = Counter(str(answer.get("answer_status") or "unknown") for answer in blocker_answers)
    blocker_kind_counts = Counter(str(answer.get("blocker_kind") or "blocked_unknown") for answer in blocker_answers)
    qa_answers = _qa_answers(
        actor_answers=actor_answers,
        issue_answers=issue_answers,
        actor_issue_refs=actor_issue_refs,
        issue_clusters=issue_clusters,
        gap_answers=gap_answers,
        blocker_answers=blocker_answers,
        max_qa_answers=max_qa_answers,
    )
    qa_status_counts = Counter(str(answer.get("answer_status") or "unknown") for answer in qa_answers)
    coverage = _safe_object(dossiers.get("coverage"))
    return {
        "meta": {
            "schema_version": "accountability_evidence_api_v1",
            "generated_at": now_utc_iso(),
            "snapshot_date": snapshot_date,
            "source_dossiers_schema": _safe_object(dossiers.get("meta")).get("schema_version"),
            "source_ledger_schema": _safe_object(ledger.get("meta")).get("schema_version"),
            "source_issue_cluster_reviews_schema": _safe_object(review_doc.get("meta")).get("schema_version"),
            "source_issue_cluster_issue_reviews_schema": _safe_object(_safe_object(issue_cluster_issue_reviews).get("meta")).get("schema_version"),
            "source_catalog_version": _safe_object(source_catalog).get("catalog_version"),
            "max_actor_answers": max_actor_answers,
            "max_issue_answers": max_issue_answers,
            "max_actor_issue_refs": max_actor_issue_refs,
            "max_issue_cluster_assignment_review_items": max_issue_cluster_assignment_review_items,
            "max_top_items": max_top_items,
            "max_evidence_per_answer": max_evidence_per_answer,
            "max_qa_answers": max_qa_answers,
            "max_blocker_answers": max_blocker_answers,
        },
        "snapshot_date": snapshot_date,
        "coverage": {
            "source_entries_total": int(coverage.get("entries_total") or 0),
            "source_actors_total": int(coverage.get("actors_total") or 0),
            "source_issues_total": int(coverage.get("issues_total") or 0),
            "question_templates_total": len(QUESTION_TEMPLATES),
            "actor_answers_total": len(actor_answers),
            "issue_answers_total": len(issue_answers),
            "actor_issue_refs_total": len(actor_issue_refs),
            "issue_clusters_total": len(issue_clusters),
            "issue_cluster_links_total": issue_cluster_links_total,
            "issue_cluster_review_items_total": len(issue_cluster_review_queue),
            "issue_cluster_review_status_counts": dict(sorted(issue_cluster_review_status_counts.items())),
            "issue_cluster_reviews_applied_total": sum(
                1 for cluster in issue_clusters if str(cluster.get("review_status") or "") == "reviewed"
            ),
            "issue_cluster_issue_reviews_applied_total": issue_cluster_issue_reviews_applied_total,
            "issue_cluster_reviewed_links_total": issue_cluster_reviewed_links_total,
            "issue_cluster_assignment_review_needed_total": issue_cluster_assignment_review_needed_total,
            "issue_cluster_assignment_review_queue_total": len(issue_cluster_assignment_review_queue),
            "issue_cluster_assignment_review_queue_truncated": (
                len(issue_cluster_assignment_review_queue) < issue_cluster_assignment_review_needed_total
            ),
            "issue_answers_with_primary_cluster_total": len(issue_answers),
            "fallback_issue_cluster_answers_total": fallback_issue_answers_total,
            "gap_answers_total": len(gap_answers),
            "blocker_answers_total": len(blocker_answers),
            "source_catalog_sources_total": int(_safe_object(_safe_object(source_catalog).get("summary")).get("sources_total") or 0),
            "source_catalog_blocked_total": int(_safe_object(_safe_object(source_catalog).get("summary")).get("blocked_total") or 0),
            "qa_answers_total": len(qa_answers),
            "qa_answers_with_self_route_total": sum(1 for answer in qa_answers if _safe_object(answer.get("routes")).get("self")),
            "evidence_samples_total": evidence_samples_total,
            "answer_status_counts": dict(sorted(status_counts.items())),
            "qa_answer_status_counts": dict(sorted(qa_status_counts.items())),
            "confidence_level_counts": dict(sorted(confidence_counts.items())),
            "freshness_level_counts": dict(sorted(freshness_counts.items())),
            "gap_answer_status_counts": dict(sorted(gap_status_counts.items())),
            "gap_missing_answer_counts_by_dimension": dict(sorted(gap_dimension_counts.items())),
            "blocker_answer_status_counts": dict(sorted(blocker_status_counts.items())),
            "blocker_kind_counts": dict(sorted(blocker_kind_counts.items())),
        },
        "question_templates": list(QUESTION_TEMPLATES),
        "actor_answers": actor_answers,
        "issue_answers": issue_answers,
        "actor_issue_refs": actor_issue_refs,
        "issue_clusters": issue_clusters,
        "issue_cluster_review_queue": issue_cluster_review_queue,
        "issue_cluster_assignment_review_queue": issue_cluster_assignment_review_queue,
        "gap_answers": gap_answers,
        "blocker_answers": blocker_answers,
        "qa_answers": qa_answers,
        "indexes": {
            "actor_answer_by_key": {answer["actor_key"]: answer["answer_id"] for answer in actor_answers},
            "issue_answer_by_id": {answer["issue_id"]: answer["answer_id"] for answer in issue_answers},
            "issue_cluster_by_id": {cluster["cluster_id"]: cluster["cluster_id"] for cluster in issue_clusters},
            "issue_clusters_by_issue_id": {
                answer["issue_id"]: _safe_array(answer.get("issue_cluster_ids")) for answer in issue_answers
            },
            "issue_cluster_review_by_id": {
                item["review_id"]: item["cluster_id"] for item in issue_cluster_review_queue
            },
            "issue_cluster_assignment_review_by_id": {
                item["review_id"]: item["issue_id"] for item in issue_cluster_assignment_review_queue
            },
            "gap_answer_by_dimension": {answer["dimension"]: answer["answer_id"] for answer in gap_answers},
            "blocker_answer_by_source_id": {answer["source_id"]: answer["answer_id"] for answer in blocker_answers},
            "qa_answer_by_id": {answer["answer_id"]: answer["answer_id"] for answer in qa_answers},
            "qa_route_by_id": {
                answer["answer_id"]: _safe_object(answer.get("routes")).get("self") for answer in qa_answers
            },
        },
    }


def main() -> int:
    args = parse_args()
    dossiers = _load_json(Path(args.dossiers))
    ledger = _load_json(Path(args.ledger))
    issue_cluster_reviews = _load_optional_json(str(args.issue_cluster_reviews or ""))
    issue_cluster_issue_reviews = _load_optional_json(str(args.issue_cluster_issue_reviews or ""))
    source_catalog = _load_optional_json(str(args.source_catalog or ""))
    payload = build_evidence_api(
        dossiers,
        ledger,
        snapshot_date=str(args.snapshot_date),
        issue_cluster_reviews=issue_cluster_reviews,
        issue_cluster_issue_reviews=issue_cluster_issue_reviews,
        source_catalog=source_catalog,
        max_actor_answers=int(args.max_actor_answers or 0),
        max_issue_answers=int(args.max_issue_answers or 0),
        max_actor_issue_refs=int(args.max_actor_issue_refs or 0),
        max_issue_cluster_assignment_review_items=int(args.max_issue_cluster_assignment_review_items or 0),
        max_top_items=int(args.max_top_items or 0),
        max_evidence_per_answer=int(args.max_evidence_per_answer or 0),
        max_qa_answers=int(args.max_qa_answers or 0),
    )
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if args.pretty:
        body = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    else:
        body = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n"
    out_path.write_text(body, encoding="utf-8")
    if str(args.latest_out or "").strip():
        latest_path = Path(args.latest_out)
        latest_path.parent.mkdir(parents=True, exist_ok=True)
        latest_path.write_text(body, encoding="utf-8")
    print(
        "OK accountability evidence API -> "
        + f"{out_path} (questions={payload['coverage']['question_templates_total']} "
        + f"actors={payload['coverage']['actor_answers_total']} issues={payload['coverage']['issue_answers_total']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
