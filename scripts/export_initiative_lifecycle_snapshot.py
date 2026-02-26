#!/usr/bin/env python3
"""Exporta un snapshot estático para GH Pages con ciclo de vida e
throughput legislativo por iniciativas.

Incluye:
- Líneas de tiempo por iniciativa (registro -> votación -> estado final)
- Resumen de cuellos de botella por comité/comisión
- "Voting around a bill": trazabilidad de votaciones ligadas con confianza por método
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_OUT = Path("docs/gh-pages/initiative-lifecycle/data/lifecycle.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Exporta un snapshot de iniciativas + throughput para GH Pages"
    )
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Ruta a la base SQLite.")
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT),
        help="Ruta de salida JSON (ej. docs/gh-pages/initiative-lifecycle/data/lifecycle.json).",
    )
    parser.add_argument(
        "--max-votes-per-initiative",
        type=int,
        default=240,
        help="Máximo de votos expuestos por iniciativa (0 = sin límite).",
    )
    parser.add_argument(
        "--max-initiatives",
        type=int,
        default=0,
        help="Límite opcional de iniciativas en salida (0 = sin límite).",
    )
    parser.add_argument(
        "--min-committee-sample",
        type=int,
        default=4,
        help="Mínimo de iniciativas para incluir un comité en ranking de throughput.",
    )
    return parser.parse_args()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_text(value: Any) -> str:
    return str(value or "").strip()


def sanitize_public_url(value: Any) -> str:
    """Retain only safe, non-local public URLs for static artifacts."""
    text = safe_text(value)
    if not text:
        return ""
    if text.lower().startswith("file://"):
        return ""
    lower = text.lower()
    if not (lower.startswith("http://") or lower.startswith("https://")):
        return ""
    return text


def safe_int(value: Any) -> int:
    text = safe_text(value)
    if not text:
        return 0
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return 0


def safe_float(value: Any) -> float | None:
    text = safe_text(value)
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def clamp_01(value: float | None) -> float | None:
    if value is None:
        return None
    if math.isnan(value):
        return None
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return round(float(value), 6)


def parse_date(raw: Any) -> date | None:
    text = safe_text(raw)
    if not text:
        return None

    m = re.match(r"^\s*(\d{4})-(\d{2})-(\d{2})(?:[ T].*)?$", text)
    if m:
        year, month, day = map(int, m.groups()[:3])
        if 1700 <= year <= 2500:
            try:
                return date(year, month, day)
            except ValueError:
                pass

    normalized = text.replace("/", "-").replace(".", "-")
    m = re.match(r"^\s*(\d{8})\s*$", normalized)
    if m:
        compact = m.group(1)
        candidate = f"{compact[:4]}-{compact[4:6]}-{compact[6:]}"
        return parse_date(candidate)

    m = re.match(r"^\s*(\d{1,2})-(\d{1,2})-(\d{2,4})(?:[ T].*)?$", text)
    if m:
        day, month, year = m.groups()
        yy = int(year)
        if 0 <= yy < 100:
            yy += 2000
        if not (1700 <= yy <= 2500):
            return None
        try:
            return date(yy, int(month), int(day))
        except ValueError:
            return None

    return None


def parse_status_date(*values: Any) -> date | None:
    for text in [safe_text(v) for v in values]:
        if not text:
            continue

        for pattern in (
            r"\b(\d{4})[-/.](\d{2})[-/.](\d{2})\b",
            r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\b",
        ):
            candidates = re.findall(pattern, text)
            if not candidates:
                continue

            d1, d2, d3 = candidates[-1]
            if len(d1) == 4:
                y, m, day = int(d1), int(d2), int(d3)
            else:
                day, m, y = int(d1), int(d2), int(d3)
                if y < 100:
                    y += 2000

            try:
                return date(y, m, day)
            except ValueError:
                continue

    return None


def day_count(start: date | None, end: date | None) -> int | None:
    if not start or not end:
        return None
    delta = (end - start).days
    return delta if delta >= 0 else None


def context_from_event(
    *,
    title: str,
    subgroup_title: str,
    subgroup_text: str,
    expediente_text: str,
) -> str:
    bag = " ".join([title, subgroup_title, subgroup_text, expediente_text]).lower()
    if any(token in bag for token in ("comision", "comisiones", "comité", "comite", "subcomision")):
        return "comision"
    if any(token in bag for token in ("pleno", "plenos", "plenario", "plena", "plenary")):
        return "pleno"
    return "otro"


def vote_outcome(yes: int, no: int, abstain: int, no_vote: int) -> str:
    if yes <= 0 and no <= 0:
        return "sin_señal"
    if yes > no:
        return "aprobada"
    if no > yes:
        return "rechazada"
    return "empate"


def confidence_band(value: float | None) -> str:
    if value is None:
        return "sin_enlace"
    if value >= 0.95:
        return "alta"
    if value >= 0.85:
        return "media"
    return "baja"


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    if not 0 <= quantile <= 1:
        raise ValueError("quantile must be between 0 and 1")
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])

    idx = (len(ordered) - 1) * quantile
    low = int(math.floor(idx))
    high = int(math.ceil(idx))
    if low == high:
        return float(ordered[int(idx)])
    return float(ordered[low]) + (float(ordered[high]) - float(ordered[low])) * (idx - low)


def summarize(values: list[int | float]) -> dict[str, Any] | None:
    if not values:
        return None
    ordered = sorted(float(v) for v in values)
    count = len(ordered)
    avg = sum(ordered) / float(count)
    p50 = percentile(ordered, 0.5)
    p75 = percentile(ordered, 0.75)
    p90 = percentile(ordered, 0.9)
    return {
        "count": count,
        "min": round(ordered[0], 2),
        "max": round(ordered[-1], 2),
        "avg": round(avg, 2),
        "median": round(float(p50), 2) if p50 is not None else None,
        "p75": round(float(p75), 2) if p75 is not None else None,
        "p90": round(float(p90), 2) if p90 is not None else None,
    }


def source_bucket(source_id: str) -> str:
    sid = safe_text(source_id).lower()
    if not sid:
        return "other"
    if "congreso" in sid:
        return "congreso"
    if "senado" in sid:
        return "senado"
    return "other"


def build_initiatives_payload(conn: sqlite3.Connection, max_votes_per_initiative: int) -> tuple[
    list[dict[str, Any]], dict[str, list[dict[str, Any]]], Counter[str], Counter[str]
]:
    rows = conn.execute(
        """
        SELECT
          i.initiative_id,
          i.legislature,
          i.expediente,
          i.type,
          i.title,
          i.presented_date,
          i.qualified_date,
          i.current_status,
          i.result_text,
          i.author_text,
          i.procedure_type,
          i.competent_committee,
          i.source_id AS initiative_source_id,
          i.source_url AS initiative_url,
          vei.vote_event_id,
          vei.link_method,
          vei.confidence AS link_confidence,
          e.vote_date,
          e.title AS vote_title,
          e.expediente_text,
          e.subgroup_title,
          e.subgroup_text,
          e.session_number,
          e.vote_number,
          e.legislature AS vote_legislature,
          e.source_id AS vote_source_id,
          e.totals_yes,
          e.totals_no,
          e.totals_abstain,
          e.totals_no_vote,
          e.assentimiento,
          e.source_url AS vote_source_url
        FROM parl_initiatives i
        LEFT JOIN parl_vote_event_initiatives vei
          ON vei.initiative_id = i.initiative_id
        LEFT JOIN parl_vote_events e
          ON e.vote_event_id = vei.vote_event_id
        ORDER BY i.initiative_id ASC, e.vote_date ASC, e.vote_event_id ASC
        """
    ).fetchall()

    by_id: dict[str, dict[str, Any]] = {}
    seen_links: dict[str, set[str]] = defaultdict(set)
    global_method_counter: Counter[str] = Counter()
    global_conf_counter: Counter[str] = Counter()

    for row in rows:
        initiative_id = safe_text(row["initiative_id"])
        if not initiative_id:
            continue

        initiative = by_id.get(initiative_id)
        if initiative is None:
            initiative = {
                "initiative_id": initiative_id,
                "legislature": safe_text(row["legislature"]),
                "expediente": safe_text(row["expediente"]),
                "type": safe_text(row["type"]),
                "title": safe_text(row["title"]),
                "presented_date": safe_text(row["presented_date"]),
                "qualified_date": safe_text(row["qualified_date"]),
                "current_status": safe_text(row["current_status"]),
                "result_text": safe_text(row["result_text"]),
                "author_text": safe_text(row["author_text"]),
                "procedure_type": safe_text(row["procedure_type"]),
                "competent_committee": safe_text(row["competent_committee"]) or "Sin comité asignado",
                "source_id": safe_text(row["initiative_source_id"]),
                "source_bucket": source_bucket(safe_text(row["initiative_source_id"])),
                "initiative_url": sanitize_public_url(row["initiative_url"]),
                "votes": [],
                "link_methods": Counter(),
                "link_confidences": [],
                "confidence_buckets": Counter(),
                "outcome_summary": Counter(),
            }
            by_id[initiative_id] = initiative

        vote_id = safe_text(row["vote_event_id"])
        if not vote_id:
            continue

        vote_method = safe_text(row["link_method"]) or "sin_metodo"
        vote_conf = clamp_01(safe_float(row["link_confidence"]))
        dedupe_key = f"{vote_id}|{vote_method}|{vote_conf if vote_conf is not None else ''}"
        if dedupe_key in seen_links[initiative_id]:
            continue
        seen_links[initiative_id].add(dedupe_key)

        conf_bucket = confidence_band(vote_conf)
        yes = safe_int(row["totals_yes"])
        no = safe_int(row["totals_no"])
        abstain = safe_int(row["totals_abstain"])
        no_vote = safe_int(row["totals_no_vote"])
        context = context_from_event(
            title=safe_text(row["vote_title"]),
            subgroup_title=safe_text(row["subgroup_title"]),
            subgroup_text=safe_text(row["subgroup_text"]),
            expediente_text=safe_text(row["expediente_text"]),
        )
        by_id[initiative_id]["votes"].append(
            {
                "vote_event_id": vote_id,
                "vote_date": safe_text(row["vote_date"]),
                "vote_legislature": safe_text(row["vote_legislature"]),
                "session_number": safe_int(row["session_number"]),
                "vote_number": safe_int(row["vote_number"]),
                "source_id": safe_text(row["vote_source_id"]),
                "source_bucket": source_bucket(safe_text(row["vote_source_id"])),
                "source_url": sanitize_public_url(row["vote_source_url"]),
                "vote_title": safe_text(row["vote_title"]),
                "expediente_text": safe_text(row["expediente_text"]),
                "subgroup_title": safe_text(row["subgroup_title"]),
                "subgroup_text": safe_text(row["subgroup_text"]),
                "assentimiento": safe_text(row["assentimiento"]),
                "totals_yes": yes,
                "totals_no": no,
                "totals_abstain": abstain,
                "totals_no_vote": no_vote,
                "outcome": vote_outcome(yes, no, abstain, no_vote),
                "outcome_margin": yes - no,
                "context": context,
                "link_method": vote_method,
                "link_confidence": vote_conf,
                "link_confidence_band": conf_bucket,
            }
        )

        initiative["link_methods"][vote_method] += 1
        initiative["link_confidences"].append(vote_conf if vote_conf is not None else 0.0)
        initiative["confidence_buckets"][conf_bucket] += 1
        initiative["outcome_summary"][vote_outcome(yes, no, abstain, no_vote)] += 1
        global_method_counter[vote_method] += 1
        global_conf_counter[conf_bucket] += 1

    initiatives: list[dict[str, Any]] = []
    committee_stats: dict[str, list[dict[str, Any]]] = {}

    for item in by_id.values():
        votes = list(item["votes"])
        votes.sort(key=lambda row: (safe_text(row["vote_date"]), row["vote_event_id"]))
        linked_votes = votes if max_votes_per_initiative <= 0 else votes[:max_votes_per_initiative]
        vote_truncated = max(0, len(votes) - len(linked_votes))
        presented_date = parse_date(item["presented_date"])
        qualified_date = parse_date(item["qualified_date"])
        status_date = parse_status_date(item["result_text"], item["current_status"])
        first_vote_date = parse_date(linked_votes[0]["vote_date"]) if linked_votes else None
        last_vote_date = parse_date(linked_votes[-1]["vote_date"]) if linked_votes else None

        timeline = {
            "presented_to_qualified_days": day_count(presented_date, qualified_date),
            "presented_to_first_vote_days": day_count(presented_date, first_vote_date),
            "qualified_to_first_vote_days": day_count(qualified_date, first_vote_date),
            "first_to_last_vote_days": day_count(first_vote_date, last_vote_date),
            "presented_to_status_days": day_count(presented_date, status_date),
            "last_vote_to_status_days": day_count(last_vote_date, status_date),
        }

        conf_values = item["link_confidences"]
        if conf_values:
            conf_min = min(conf_values)
            conf_max = max(conf_values)
            conf_avg = sum(conf_values) / float(len(conf_values))
            conf_med = float(percentile(conf_values, 0.5) or conf_avg)
            dominant_method = item["link_methods"].most_common(1)[0][0]
            confidence_summary = confidence_band(conf_avg)
            low_confidence = item["confidence_buckets"].get("baja", 0)
            low_confidence_ratio = low_confidence / float(len(conf_values))
        else:
            conf_min = conf_max = conf_avg = conf_med = None
            dominant_method = ""
            confidence_summary = "sin_enlace"
            low_confidence = 0
            low_confidence_ratio = 1.0

        committee_name = item["competent_committee"] or "Sin comité asignado"
        committee_stats.setdefault(committee_name, []).append(
            {
                "initiative_id": item["initiative_id"],
                "vote_count": len(votes),
                "reg_to_qual_days": timeline["presented_to_qualified_days"],
                "reg_to_first_days": timeline["presented_to_first_vote_days"],
                "qual_to_first_days": timeline["qualified_to_first_vote_days"],
                "first_to_last_days": timeline["first_to_last_vote_days"],
                "reg_to_status_days": timeline["presented_to_status_days"],
            }
        )

        initiatives.append(
            {
                "initiative_id": item["initiative_id"],
                "legislature": item["legislature"],
                "expediente": item["expediente"],
                "type": item["type"],
                "title": item["title"],
                "procedure_type": item["procedure_type"],
                "author_text": item["author_text"],
                "source_id": item["source_id"],
                "source_bucket": item["source_bucket"],
                "initiative_url": item["initiative_url"],
                "presented_date": item["presented_date"],
                "qualified_date": item["qualified_date"],
                "current_status": item["current_status"],
                "result_text": item["result_text"],
                "status_date": status_date.isoformat() if status_date else "",
                "competent_committee": committee_name,
                "vote_count": len(votes),
                "vote_truncated": vote_truncated > 0,
                "vote_truncated_count": int(vote_truncated),
                "first_vote_date": safe_text(linked_votes[0]["vote_date"]) if linked_votes else "",
                "last_vote_date": safe_text(linked_votes[-1]["vote_date"]) if linked_votes else "",
                "timeline_days": timeline,
                "outcome_summary": {
                    "aprobada": int(item["outcome_summary"].get("aprobada", 0)),
                    "rechazada": int(item["outcome_summary"].get("rechazada", 0)),
                    "empate": int(item["outcome_summary"].get("empate", 0)),
                    "sin_señal": int(item["outcome_summary"].get("sin_señal", 0)),
                },
                "link_summary": {
                    "vote_links": len(votes),
                    "methods_count": int(sum(item["link_methods"].values())),
                    "dominant_method": dominant_method,
                    "link_confidence_min": conf_min,
                    "link_confidence_max": conf_max,
                    "link_confidence_avg": round(conf_avg, 6) if conf_avg is not None else None,
                    "link_confidence_median": round(conf_med, 6) if conf_med is not None else None,
                    "link_confidence_bucket": confidence_summary,
                    "low_confidence_links": int(low_confidence),
                    "low_confidence_ratio": round(low_confidence_ratio, 3),
                },
                "votes": linked_votes,
            }
        )

    initiatives.sort(
        key=lambda item: (
            item["vote_count"] == 0,
            -item["vote_count"],
            safe_text(item["first_vote_date"]),
            safe_text(item["presented_date"]),
            safe_text(item["title"]),
        )
    )

    return initiatives, committee_stats, global_method_counter, global_conf_counter


def build_bottleneck_payload(
    committee_stats: dict[str, list[dict[str, Any]]],
    min_sample: int,
) -> dict[str, Any]:
    committees = []

    for committee_name, entries in committee_stats.items():
        vote_counts = []
        reg_to_qual = []
        reg_to_first = []
        qual_to_first = []
        first_to_last = []
        reg_to_status = []

        for entry in entries:
            vote_counts.append(float(entry["vote_count"]))
            reg_to_qual_value = entry.get("reg_to_qual_days")
            reg_to_first_value = entry.get("reg_to_first_days")
            qual_to_first_value = entry.get("qual_to_first_days")
            first_to_last_value = entry.get("first_to_last_days")
            reg_to_status_value = entry.get("reg_to_status_days")
            if reg_to_qual_value is not None:
                reg_to_qual.append(float(reg_to_qual_value))
            if reg_to_first_value is not None:
                reg_to_first.append(float(reg_to_first_value))
            if qual_to_first_value is not None:
                qual_to_first.append(float(qual_to_first_value))
            if first_to_last_value is not None:
                first_to_last.append(float(first_to_last_value))
            if reg_to_status_value is not None:
                reg_to_status.append(float(reg_to_status_value))

        total = len(entries)
        if total < max(1, min_sample):
            continue

        no_vote_initiatives = sum(1 for entry in entries if int(entry.get("vote_count", 0)) <= 0)
        committees.append(
            {
                "committee": committee_name,
                "initiatives_total": total,
                "vote_links": total - no_vote_initiatives,
                "no_vote_initiatives": no_vote_initiatives,
                "vote_count_distribution": summarize(vote_counts),
                "stages": {
                    "presented_to_qualified_days": summarize(reg_to_qual),
                    "presented_to_first_vote_days": summarize(reg_to_first),
                    "qualified_to_first_vote_days": summarize(qual_to_first),
                    "first_to_last_vote_days": summarize(first_to_last),
                    "presented_to_status_days": summarize(reg_to_status),
                },
                "reliability": {
                    "sampled_initiatives": int(total),
                    "no_vote_pct": round((no_vote_initiatives / float(total)) * 100, 2) if total else 0.0,
                },
            }
        )

    def bottleneck_sort_key(row: dict[str, Any]) -> tuple[float, float, str]:
        stage = row["stages"].get("presented_to_first_vote_days") or {}
        median = stage.get("median") if isinstance(stage, dict) else None
        return (-(float(median) if median is not None else -1.0), -row["reliability"]["sampled_initiatives"], row["committee"])

    committees.sort(key=bottleneck_sort_key)

    return {"committee_by_throughput": committees}


def build_payload(
    conn: sqlite3.Connection,
    *,
    max_votes_per_initiative: int,
    max_initiatives: int,
    min_committee_sample: int,
) -> dict[str, Any]:
    initiatives, committee_stats, method_counter, global_conf_counter = build_initiatives_payload(
        conn,
        max_votes_per_initiative=max_votes_per_initiative,
    )

    if max_initiatives > 0:
        initiatives = initiatives[:max_initiatives]
        selected_ids = {item["initiative_id"] for item in initiatives}
        committee_stats = {
            name: [entry for entry in entries if entry["initiative_id"] in selected_ids]
            for name, entries in committee_stats.items()
        }
        committee_stats = {name: entries for name, entries in committee_stats.items() if entries}
    source_ids = sorted(set(item["source_id"] for item in initiatives if safe_text(item["source_id"])))
    committees = sorted(set(item["competent_committee"] for item in initiatives))
    legislatures = sorted(set(item["legislature"] for item in initiatives if safe_text(item["legislature"])))
    status_buckets = sorted(set(item["current_status"] for item in initiatives if safe_text(item["current_status"])))

    linked_initiatives = [item for item in initiatives if int(item.get("vote_count", 0)) > 0]
    unlinked_initiatives = [item for item in initiatives if int(item.get("vote_count", 0)) == 0]
    all_buckets = [item["link_summary"]["link_confidence_bucket"] for item in initiatives]
    confidence_distribution = Counter(all_buckets)

    return {
        "meta": {
            "generated_at": now_utc_iso(),
            "db_path": "redacted",
            "max_votes_per_initiative": int(max_votes_per_initiative),
            "max_initiatives": int(max_initiatives or 0),
            "total_initiatives": len(initiatives),
            "linked_initiatives": len(linked_initiatives),
            "unlinked_initiatives": len(unlinked_initiatives),
            "total_vote_links": int(sum(int(item.get("vote_count", 0)) for item in initiatives)),
        },
        "filters": {
            "source_ids": source_ids,
            "committees": committees,
            "legislatures": legislatures,
            "status_buckets": status_buckets,
            "link_methods": sorted(set(method_counter.keys())),
            "linking_methods": sorted(set(method_counter.keys())),
        },
        "initiative_overview": {
            "linked_initiatives": int(len(linked_initiatives)),
            "unlinked_initiatives": int(len(unlinked_initiatives)),
            "confidence_distribution": {
                "high": int(confidence_distribution.get("alta", 0)),
                "medium": int(confidence_distribution.get("media", 0)),
                "low": int(confidence_distribution.get("baja", 0)),
                "none": int(confidence_distribution.get("sin_enlace", 0)),
            },
            "link_methods": dict(method_counter),
            "global_confidence": {
                "high": int(global_conf_counter.get("alta", 0)),
                "medium": int(global_conf_counter.get("media", 0)),
                "low": int(global_conf_counter.get("baja", 0)),
                "none": int(global_conf_counter.get("sin_enlace", 0)),
            },
        },
        "bottlenecks": build_bottleneck_payload(committee_stats, min_sample=min_committee_sample),
        "initiatives": initiatives,
    }


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        print(f"ERROR: no existe la DB -> {db_path}")
        return 2

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        payload = build_payload(
            conn,
            max_votes_per_initiative=max(0, int(args.max_votes_per_initiative)),
            max_initiatives=max(0, int(args.max_initiatives)),
            min_committee_sample=max(1, int(args.min_committee_sample)),
        )
    except Exception as error:
        print(f"ERROR: fallo generando snapshot: {error}")
        return 3
    finally:
        conn.close()

    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    meta = payload["meta"]
    print(
        f"OK initiative lifecycle -> {out_path} "
        f"(initiatives={meta['total_initiatives']} linked={meta['linked_initiatives']} "
        f"votes={meta['total_vote_links']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
