#!/usr/bin/env python3
"""Discover official Andalucia execution/outcome datasets worth wiring next.

This is an automation assist, not a claim generator. It searches the Junta open
data CKAN API, scores machine-readable datasets against the Andalucia 2026
execution-evidence gaps, and writes a bounded report for the next source-loader
slice.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.export_andalucia_2026_accountability_snapshot import (
    EXECUTION_EVIDENCE_SOURCE_CANDIDATES,
    ISSUE_EXECUTION_EVIDENCE_PLANS,
    normalize_label,
    stable_slug,
    write_json,
)


CKAN_ACTION_BASE = "https://www.juntadeandalucia.es/datosabiertos/portal/api/3/action"
CKAN_DATASET_BASE = "https://www.juntadeandalucia.es/datosabiertos/portal/dataset"
DEFAULT_OUT = Path("etl/data/published/andalucia-2026-execution-source-discovery.json")
DEFAULT_ROWS_PER_QUERY = 5
DEFAULT_MAX_TOPIC_TERMS = 2
DEFAULT_MAX_CANDIDATES = 60
DEFAULT_RESOURCE_PROBE_TIMEOUT = 5
DEFAULT_MAX_RESOURCE_PROBES = 12

MACHINE_READABLE_FORMATS = {
    "7z",
    "api",
    "csv",
    "json",
    "jsonld",
    "ods",
    "tsv",
    "xls",
    "xlsx",
    "xml",
    "zip",
}

GAP_SIGNAL_TERMS = {
    "missing_budget_execution": (
        "adjudicacion",
        "beneficiario",
        "contratacion",
        "contrato",
        "ejecucion",
        "importe",
        "movimientos",
        "pago",
        "pagos",
        "presupuesto",
        "subvencion",
        "subvenciones",
        "tesoreria",
    ),
    "missing_outcomes": (
        "estadistica",
        "ieca",
        "indicador",
        "indicadores",
        "ods",
        "resultado",
        "serie",
    ),
    "missing_execution_owner": (
        "competencias",
        "consejeria",
        "direccion general",
        "estructura organica",
        "organigrama",
    ),
}

BASE_DISCOVERY_QUERIES = (
    ("treasury_2025", "Movimientos de la Tesorería General de la Junta de Andalucía 2025"),
    ("payments_2025", "pagos Junta Andalucía 2025"),
    ("budget_execution_2025", "ejecución presupuestaria Andalucía 2025"),
    ("budget_2026", "Presupuesto de la Comunidad Autónoma de Andalucía 2026"),
    ("contracts_minor_2025", "contratación menor Junta Andalucía 2025"),
    ("grants", "subvenciones otorgadas Junta Andalucía"),
    ("ieca_ods", "IECA ODS Andalucía indicadores"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Discover official source candidates for Andalucia 2026 execution evidence"
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="JSON report output path")
    parser.add_argument("--rows-per-query", type=int, default=DEFAULT_ROWS_PER_QUERY)
    parser.add_argument("--max-topic-terms", type=int, default=DEFAULT_MAX_TOPIC_TERMS)
    parser.add_argument("--max-candidates", type=int, default=DEFAULT_MAX_CANDIDATES)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--probe-timeout", type=int, default=DEFAULT_RESOURCE_PROBE_TIMEOUT)
    parser.add_argument("--max-resource-probes", type=int, default=DEFAULT_MAX_RESOURCE_PROBES)
    parser.add_argument("--skip-resource-probe", action="store_true", help="Do not HEAD-probe resource URLs")
    return parser.parse_args()


def now_utc_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def ckan_action_url(action: str, params: dict[str, Any]) -> str:
    return f"{CKAN_ACTION_BASE}/{action}?" + urllib.parse.urlencode(params)


def fetch_json_url(url: str, *, timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "vota-source-discovery/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def ckan_package_search(query: str, *, rows: int, timeout: int) -> list[dict[str, Any]]:
    payload = fetch_json_url(ckan_action_url("package_search", {"q": query, "rows": rows}), timeout=timeout)
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    packages = result.get("results") if isinstance(result.get("results"), list) else []
    return [package for package in packages if isinstance(package, dict)]


def portal_dataset_url(package: dict[str, Any]) -> str:
    name = str(package.get("name") or "").strip()
    return f"{CKAN_DATASET_BASE}/{name}" if name else ""


def resource_format(resource: dict[str, Any]) -> str:
    return normalize_label(resource.get("format") or resource.get("mimetype") or "")


def resource_is_machine_readable(resource: dict[str, Any]) -> bool:
    fmt = resource_format(resource)
    url = normalize_label(resource.get("url") or "")
    return any(fmt == value or fmt.endswith(value) or url.endswith(f".{value}") for value in MACHINE_READABLE_FORMATS)


def alternate_resource_urls(url: str) -> list[str]:
    parsed = urllib.parse.urlparse(str(url or ""))
    if parsed.netloc == "gdc-pdpopendata-ckan.paas.junta-andalucia.es" and parsed.path.startswith(
        "/datosabiertos/portal/dataset/"
    ):
        return [urllib.parse.urlunparse(parsed._replace(netloc="www.juntadeandalucia.es"))]
    return []


def equivalent_resource_urls(url: str) -> list[str]:
    parsed = urllib.parse.urlparse(str(url or ""))
    if not parsed.scheme or not parsed.netloc:
        return []
    equivalents = {urllib.parse.urlunparse(parsed)}
    if parsed.path.startswith("/datosabiertos/portal/dataset/"):
        if parsed.netloc == "gdc-pdpopendata-ckan.paas.junta-andalucia.es":
            equivalents.add(urllib.parse.urlunparse(parsed._replace(netloc="www.juntadeandalucia.es")))
        elif parsed.netloc == "www.juntadeandalucia.es":
            equivalents.add(
                urllib.parse.urlunparse(parsed._replace(netloc="gdc-pdpopendata-ckan.paas.junta-andalucia.es"))
            )
    return sorted(equivalents)


def package_text(package: dict[str, Any]) -> str:
    parts: list[str] = [
        str(package.get("name") or ""),
        str(package.get("title") or ""),
        str(package.get("notes") or ""),
    ]
    for tag in package.get("tags") or []:
        if isinstance(tag, dict):
            parts.append(str(tag.get("name") or tag.get("display_name") or ""))
    for resource in package.get("resources") or []:
        if isinstance(resource, dict):
            parts.extend(
                [
                    str(resource.get("name") or ""),
                    str(resource.get("description") or ""),
                    str(resource.get("format") or ""),
                    str(resource.get("url") or ""),
                ]
            )
    return normalize_label(" ".join(parts))


def package_year(package: dict[str, Any]) -> int:
    years = [
        int(match)
        for match in re.findall(r"\b(20\d{2})\b", " ".join(str(package.get(key) or "") for key in ("name", "title", "notes")))
    ]
    return max(years) if years else 0


def existing_source_indexes() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    by_landing: dict[str, list[str]] = {}
    by_resource: dict[str, list[str]] = {}
    for source_id, source in EXECUTION_EVIDENCE_SOURCE_CANDIDATES.items():
        landing_url = str(source.get("landing_url") or "").strip()
        source_url = str(source.get("source_url") or "").strip()
        if landing_url:
            by_landing.setdefault(landing_url, []).append(source_id)
        if source_url:
            for equivalent_url in equivalent_resource_urls(source_url):
                by_resource.setdefault(equivalent_url, []).append(source_id)
    return by_landing, by_resource


def compact_resource(resource: dict[str, Any]) -> dict[str, Any]:
    url = clean_text(resource.get("url"))
    return {
        "name": clean_text(resource.get("name")),
        "format": clean_text(resource.get("format")),
        "url": url,
        "alternate_urls": alternate_resource_urls(url),
        "mimetype": clean_text(resource.get("mimetype")),
        "machine_readable": resource_is_machine_readable(resource),
    }


def probe_resource_url(url: str, *, timeout: int) -> dict[str, Any]:
    if not url:
        return {"probe_status": "missing_url"}
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "vota-source-discovery/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {
                "probe_status": f"http_{int(response.status)}",
                "http_status": int(response.status),
                "content_type": clean_text(response.headers.get("content-type")),
                "content_length_bytes": int(response.headers.get("content-length") or 0),
            }
    except urllib.error.HTTPError as exc:
        return {
            "probe_status": f"http_{int(exc.code)}",
            "http_status": int(exc.code),
            "content_type": clean_text(exc.headers.get("content-type") if exc.headers else ""),
            "content_length_bytes": int(exc.headers.get("content-length") or 0) if exc.headers else 0,
        }
    except Exception as exc:  # pragma: no cover - network failures vary by host/runtime
        return {"probe_status": "resource_probe_failed", "error": f"{type(exc).__name__}: {exc}"}


def probe_resource_with_alternates(resource: dict[str, Any], *, timeout: int) -> dict[str, Any]:
    urls = [str(resource.get("url") or "")] + [str(url) for url in resource.get("alternate_urls") or [] if url]
    first_failure: dict[str, Any] | None = None
    for index, url in enumerate(dict.fromkeys(urls)):
        result = probe_resource_url(url, timeout=timeout)
        http_status = int(result.get("http_status") or 0)
        if 200 <= http_status < 400:
            result["effective_url"] = url
            if index > 0:
                result["primary_probe_status"] = (first_failure or {}).get("probe_status") or ""
                result["used_alternate_url"] = True
            else:
                result["used_alternate_url"] = False
            return result
        if first_failure is None:
            first_failure = dict(result)
    return first_failure or {"probe_status": "missing_url"}


def iter_gap_profiles(max_topic_terms: int) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for topic_id, plans in ISSUE_EXECUTION_EVIDENCE_PLANS.items():
        for plan in plans:
            gap_id = str(plan.get("gap_id") or "")
            terms = [str(term) for term in plan.get("search_terms") or [] if str(term).strip()]
            profiles.append(
                {
                    "topic_id": topic_id,
                    "gap_id": gap_id,
                    "topic_label": plan.get("evidence_need") or "",
                    "search_terms": terms[:max(0, max_topic_terms)],
                }
            )
    return profiles


def discovery_queries(max_topic_terms: int) -> list[dict[str, str]]:
    queries: list[dict[str, str]] = [
        {"query_id": query_id, "query": query, "source": "base"} for query_id, query in BASE_DISCOVERY_QUERIES
    ]
    seen = {normalize_label(row["query"]) for row in queries}
    for profile in iter_gap_profiles(max_topic_terms):
        gap_id = str(profile.get("gap_id") or "")
        suffixes = {
            "missing_budget_execution": ("pagos Junta Andalucía", "subvenciones contratos Junta Andalucía"),
            "missing_outcomes": ("indicadores IECA Andalucía", "ODS Andalucía"),
            "missing_execution_owner": ("competencias consejería Junta Andalucía",),
        }.get(gap_id, ("Junta Andalucía",))
        for term in profile.get("search_terms") or []:
            for suffix in suffixes:
                query = f"{term} {suffix}"
                key = normalize_label(query)
                if key in seen:
                    continue
                seen.add(key)
                queries.append(
                    {
                        "query_id": stable_slug(f"{profile.get('topic_id')}:{gap_id}:{query}"),
                        "query": query,
                        "source": "topic_gap",
                    }
                )
    return queries


def matched_terms(text: str, terms: tuple[str, ...] | list[str]) -> list[str]:
    out: list[str] = []
    for term in terms:
        normalized = normalize_label(term)
        if normalized and normalized in text:
            out.append(str(term))
    return out


def score_package_for_gap(package: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    text = package_text(package)
    topic_terms = matched_terms(text, profile.get("search_terms") or [])
    gap_terms = matched_terms(text, GAP_SIGNAL_TERMS.get(str(profile.get("gap_id") or ""), ()))
    machine_resources = [
        resource for resource in package.get("resources") or [] if isinstance(resource, dict) and resource_is_machine_readable(resource)
    ]
    score = (len(topic_terms) * 4) + (len(gap_terms) * 2)
    if machine_resources:
        score += 3
    title = normalize_label(package.get("title") or package.get("name") or "")
    if "movimientos de la tesoreria" in title:
        score += 6
    if "contratacion menor" in title or "subvenciones otorgadas" in title:
        score += 5
    if "presupuesto" in title:
        score += 3
    if "ods" in title or "indicador" in title:
        score += 3
    if topic_terms:
        match_status = "topic_gap_candidate"
    elif gap_terms:
        match_status = "gap_source_candidate_needs_row_filter"
    else:
        match_status = "weak_candidate"
    return {
        "score": score,
        "match_status": match_status,
        "matched_topic_terms": topic_terms,
        "matched_gap_terms": gap_terms,
        "machine_resources_total": len(machine_resources),
    }


def candidate_next_action(candidate: dict[str, Any]) -> str:
    if candidate.get("already_integrated"):
        return "already_integrated_keep_refreshing"
    if not candidate.get("machine_resources_total"):
        return "manual_review_or_skip_non_machine_readable"
    probe_statuses = {
        str(resource.get("probe_status") or "")
        for resource in candidate.get("resources") or []
        if resource.get("machine_readable")
    }
    if "resource_probe_failed" in probe_statuses:
        return "fix_resource_access_or_find_alternate_download_url"
    return "wire_source_loader_and_candidate_mapping"


def build_candidate(
    package: dict[str, Any],
    profile: dict[str, Any],
    *,
    query_ids: list[str],
    skip_resource_probe: bool,
    existing_by_landing: dict[str, list[str]],
    existing_by_resource: dict[str, list[str]],
) -> dict[str, Any]:
    score = score_package_for_gap(package, profile)
    landing_url = portal_dataset_url(package)
    resources = [compact_resource(resource) for resource in package.get("resources") or [] if isinstance(resource, dict)]
    existing_ids = set(existing_by_landing.get(landing_url, []))
    for resource in resources:
        for resource_url in [str(resource.get("url") or "")] + [
            str(url) for url in resource.get("alternate_urls") or [] if url
        ]:
            for equivalent_url in equivalent_resource_urls(resource_url):
                existing_ids.update(existing_by_resource.get(equivalent_url, []))
    candidate = {
        "candidate_id": stable_slug(
            f"andalucia-2026-source:{profile.get('topic_id')}:{profile.get('gap_id')}:{package.get('name')}"
        ),
        "topic_id": profile.get("topic_id") or "",
        "gap_id": profile.get("gap_id") or "",
        "score": int(score["score"]),
        "match_status": score["match_status"],
        "matched_topic_terms": score["matched_topic_terms"],
        "matched_gap_terms": score["matched_gap_terms"],
        "package_name": clean_text(package.get("name")),
        "package_title": clean_text(package.get("title")),
        "package_year": package_year(package),
        "landing_url": landing_url,
        "notes": clean_text(package.get("notes")),
        "query_ids": sorted(set(query_ids)),
        "resources": resources[:5],
        "resources_total": len(resources),
        "machine_resources_total": int(score["machine_resources_total"]),
        "existing_source_ids": sorted(existing_ids),
        "already_integrated": bool(existing_ids),
    }
    candidate["next_action"] = candidate_next_action(candidate)
    return candidate


def apply_resource_probes(
    candidates: list[dict[str, Any]],
    *,
    timeout: int,
    max_resource_probes: int,
) -> int:
    probe_cache: dict[str, dict[str, Any]] = {}
    probes_attempted = 0
    for candidate in candidates:
        for resource in candidate.get("resources") or []:
            if not isinstance(resource, dict) or not resource.get("machine_readable"):
                continue
            url = str(resource.get("url") or "")
            if not url:
                continue
            if url not in probe_cache:
                if max_resource_probes >= 0 and probes_attempted >= max_resource_probes:
                    continue
                probe_cache[url] = probe_resource_with_alternates(resource, timeout=timeout)
                probes_attempted += 1
            resource.update(probe_cache[url])
        candidate["next_action"] = candidate_next_action(candidate)
    return len(probe_cache)


def discover_source_candidates(
    *,
    rows_per_query: int = DEFAULT_ROWS_PER_QUERY,
    max_topic_terms: int = DEFAULT_MAX_TOPIC_TERMS,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
    timeout: int = 30,
    probe_timeout: int = DEFAULT_RESOURCE_PROBE_TIMEOUT,
    max_resource_probes: int = DEFAULT_MAX_RESOURCE_PROBES,
    skip_resource_probe: bool = False,
) -> dict[str, Any]:
    query_rows = discovery_queries(max_topic_terms)
    package_by_name: dict[str, dict[str, Any]] = {}
    query_ids_by_package: dict[str, list[str]] = {}
    query_reports: list[dict[str, Any]] = []
    for query in query_rows:
        try:
            packages = ckan_package_search(str(query["query"]), rows=rows_per_query, timeout=timeout)
            status = "ok"
            error = ""
        except Exception as exc:  # pragma: no cover - network failures vary by host/runtime
            packages = []
            status = "error"
            error = f"{type(exc).__name__}: {exc}"
        query_reports.append(
            {
                "query_id": query["query_id"],
                "query": query["query"],
                "source": query["source"],
                "status": status,
                "packages_total": len(packages),
                "error": error,
            }
        )
        for package in packages:
            name = str(package.get("name") or "").strip()
            if not name:
                continue
            package_by_name.setdefault(name, package)
            query_ids_by_package.setdefault(name, []).append(str(query["query_id"]))

    existing_by_landing, existing_by_resource = existing_source_indexes()
    candidates: list[dict[str, Any]] = []
    for package_name, package in package_by_name.items():
        for profile in iter_gap_profiles(max_topic_terms):
            score = score_package_for_gap(package, profile)
            if int(score["score"]) < 5:
                continue
            candidates.append(
                build_candidate(
                    package,
                    profile,
                    query_ids=query_ids_by_package.get(package_name, []),
                    skip_resource_probe=skip_resource_probe,
                    existing_by_landing=existing_by_landing,
                    existing_by_resource=existing_by_resource,
                )
            )

    candidates.sort(
        key=lambda row: (
            bool(row.get("already_integrated")),
            -int(row.get("score") or 0),
            -int(row.get("package_year") or 0),
            str(row.get("gap_id") or ""),
            str(row.get("package_title") or ""),
            str(row.get("topic_id") or ""),
        )
    )
    if max_candidates > 0:
        candidates = candidates[:max_candidates]
    unique_resource_probes_total = 0
    if not skip_resource_probe:
        unique_resource_probes_total = apply_resource_probes(
            candidates,
            timeout=probe_timeout,
            max_resource_probes=max_resource_probes,
        )
    next_action_counts = Counter(str(row.get("next_action") or "") for row in candidates)
    return {
        "schema_version": "andalucia_2026_execution_source_discovery_v1",
        "generated_at": now_utc_iso(),
        "source": {
            "ckan_action_base": CKAN_ACTION_BASE,
            "portal_dataset_base": CKAN_DATASET_BASE,
        },
        "parameters": {
            "rows_per_query": rows_per_query,
            "max_topic_terms": max_topic_terms,
            "max_candidates": max_candidates,
            "probe_timeout": probe_timeout,
            "max_resource_probes": max_resource_probes,
            "skip_resource_probe": bool(skip_resource_probe),
            "unique_resource_probes_total": unique_resource_probes_total,
        },
        "summary": {
            "queries_total": len(query_reports),
            "query_errors_total": sum(1 for row in query_reports if row.get("status") != "ok"),
            "packages_seen_total": len(package_by_name),
            "candidates_total": len(candidates),
            "new_candidates_total": sum(1 for row in candidates if not row.get("already_integrated")),
            "already_integrated_total": sum(1 for row in candidates if row.get("already_integrated")),
            "wire_source_loader_candidates_total": next_action_counts.get("wire_source_loader_and_candidate_mapping", 0),
            "resource_access_candidates_total": next_action_counts.get(
                "fix_resource_access_or_find_alternate_download_url", 0
            ),
            "next_action_counts": dict(next_action_counts),
        },
        "queries": query_reports,
        "candidates": candidates,
    }


def main() -> int:
    args = parse_args()
    report = discover_source_candidates(
        rows_per_query=max(1, args.rows_per_query),
        max_topic_terms=max(0, args.max_topic_terms),
        max_candidates=max(0, args.max_candidates),
        timeout=max(1, args.timeout),
        probe_timeout=max(1, args.probe_timeout),
        max_resource_probes=max(0, args.max_resource_probes),
        skip_resource_probe=bool(args.skip_resource_probe),
    )
    write_json(Path(args.out), report)
    summary = report["summary"]
    print(
        "queries={queries_total} packages={packages_seen_total} candidates={candidates_total} "
        "new={new_candidates_total} wire={wire_source_loader_candidates_total} access_fix={resource_access_candidates_total}".format(
            **summary
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
