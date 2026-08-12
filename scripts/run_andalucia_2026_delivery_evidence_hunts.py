#!/usr/bin/env python3
"""Run bounded official searches for Andalucia 2026 delivery evidence hunts.

This is an assist artifact, not a claim generator. It executes machine-readable
or parseable official search targets created by the accountability exporter and
writes result candidates for human review. Manual-only registries stay explicit.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.discover_andalucia_2026_execution_sources import (  # noqa: E402
    ckan_package_search,
    clean_text,
    compact_resource,
    portal_dataset_url,
)
from scripts.export_andalucia_2026_accountability_snapshot import (  # noqa: E402
    normalize_label,
    stable_slug,
    write_json,
)
from publicdata_core.util import now_utc_iso  # noqa: E402


DEFAULT_SNAPSHOT = Path("etl/data/published/andalucia-2026-accountability.json")
DEFAULT_OUT = Path("etl/data/published/andalucia-2026-delivery-evidence-hunt-results.json")
DEFAULT_PUBLIC_OUT = Path("ui/gh-pages-next/public/elecciones/andalucia-2026/data/delivery-evidence-hunt-results.json")
DEFAULT_MAX_TARGETS = 40
DEFAULT_ROWS_PER_QUERY = 3
DEFAULT_TIMEOUT = 12
BOJA_SEARCH_URL = "https://www.juntadeandalucia.es/eboja/buscador/search.do"
BDNS_API_BASE = "https://www.infosubvenciones.es/bdnstrans/api"
PDC_ELASTIC_SEARCH_URL = (
    "https://www.juntadeandalucia.es/haciendayadministracionpublica/apl/pdc-front-publico/"
    "elastic/sirec_pdc_expedientes/_search?pretty"
)
PDC_DETAIL_BASE_URL = (
    "https://www.juntadeandalucia.es/haciendayadministracionpublica/apl/pdc-front-publico/"
    "perfiles-licitaciones/detalle-licitacion"
)
USER_AGENT = "vota-delivery-hunt/1.0"

MANUAL_REGISTRIES = {
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run official delivery-evidence search targets for Andalucia 2026 readiness hunts"
    )
    parser.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT), help="Accountability snapshot JSON")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Published JSON report output")
    parser.add_argument("--public-out", default=str(DEFAULT_PUBLIC_OUT), help="Static UI JSON report output")
    parser.add_argument("--max-targets", type=int, default=DEFAULT_MAX_TARGETS)
    parser.add_argument("--rows-per-query", type=int, default=DEFAULT_ROWS_PER_QUERY)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def compact_text(value: Any, *, limit: int = 420) -> str:
    text = clean_text(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def collect_search_targets(snapshot: dict[str, Any], *, max_targets: int = DEFAULT_MAX_TARGETS) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    readiness = snapshot.get("accountability_readiness") if isinstance(snapshot.get("accountability_readiness"), dict) else {}
    for issue in readiness.get("issues") or []:
        if not isinstance(issue, dict):
            continue
        topic_id = str(issue.get("topic_id") or "")
        topic_label = str(issue.get("topic_label") or "")
        for hunt in issue.get("delivery_evidence_hunts") or []:
            if not isinstance(hunt, dict):
                continue
            hunt_id = str(hunt.get("hunt_id") or "")
            for target in hunt.get("search_targets") or []:
                if not isinstance(target, dict):
                    continue
                registry = str(target.get("registry") or "")
                target_id = str(target.get("target_id") or "")
                query = clean_text(target.get("query"))
                signature = (hunt_id, registry, normalize_label(query))
                if not registry or not query or signature in seen:
                    continue
                seen.add(signature)
                row = dict(target)
                row.update(
                    {
                        "target_run_id": stable_slug(f"{topic_id}:{hunt_id}:{target_id}:{registry}:{query}"),
                        "topic_id": topic_id,
                        "topic_label": topic_label,
                        "hunt_id": hunt_id,
                        "evidence_kind": str(hunt.get("evidence_kind") or ""),
                        "reviewed_label": str(hunt.get("reviewed_label") or ""),
                        "source_id": str(hunt.get("source_id") or ""),
                        "source_locator": str(hunt.get("source_locator") or ""),
                        "contract_reference": str(hunt.get("contract_reference") or ""),
                        "grant_beneficiary": str(hunt.get("grant_beneficiary") or ""),
                        "program_code": str(hunt.get("program_code") or ""),
                    }
                )
                rows.append(row)
                if max_targets > 0 and len(rows) >= max_targets:
                    return rows
    return rows


def boja_fetch_url(query: str) -> str:
    return f"{BOJA_SEARCH_URL}?" + urllib.parse.urlencode({"q": query, "eboja": "on"})


def query_variants_for_target(target: dict[str, Any]) -> list[dict[str, str]]:
    variants: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(kind: str, query: Any) -> None:
        text = clean_text(query)
        key = normalize_label(text)
        if not key or key in seen:
            return
        seen.add(key)
        variants.append({"query_variant": kind, "query": text})

    add("exact_target_query", target.get("query"))
    reviewed_label = clean_text(target.get("reviewed_label"))
    contract_reference = clean_text(target.get("contract_reference"))
    grant_beneficiary = clean_text(target.get("grant_beneficiary"))
    program_code = clean_text(target.get("program_code"))

    if contract_reference:
        add("contract_reference", contract_reference)
    if reviewed_label:
        add("reviewed_label", reviewed_label)
    if program_code and reviewed_label:
        add("program_code_reviewed_label", f"{program_code} {reviewed_label}")
    if grant_beneficiary and reviewed_label:
        add("beneficiary_reviewed_label", f"{grant_beneficiary} {reviewed_label}")
    return variants


def fetch_text_url(url: str, *, timeout: int) -> tuple[str, int, str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        content_type = clean_text(response.headers.get("content-type"))
        charset = response.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, "replace"), int(response.status), content_type, response.geturl()


def fetch_json_url(
    url: str,
    *,
    timeout: int,
    payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int, str, str]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    data: bytes | None = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        content_type = clean_text(response.headers.get("content-type"))
        charset = response.headers.get_content_charset() or "utf-8"
        decoded = raw.decode(charset, "replace")
        parsed = json.loads(decoded)
        return parsed if isinstance(parsed, dict) else {}, int(response.status), content_type, response.geturl()


def api_url(base_url: str, endpoint: str, params: dict[str, Any]) -> str:
    clean_params = {key: value for key, value in params.items() if value not in ("", None)}
    return f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}?{urllib.parse.urlencode(clean_params)}"


def nested_text(row: dict[str, Any], *path: str) -> str:
    value: Any = row
    for key in path:
        if not isinstance(value, dict):
            return ""
        value = value.get(key)
    return clean_text(value)


def compact_number(value: Any) -> int | float | str:
    return value if isinstance(value, (int, float)) else clean_text(value)


class BojaResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._list_depth = 0
        self._anchor_href = ""
        self._anchor_chunks: list[str] = []
        self.results: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        class_name = attr.get("class", "")
        if tag == "ul" and "listado_resultados" in class_name:
            self._list_depth = 1
            return
        if self._list_depth:
            self._list_depth += 1
        if self._list_depth and tag == "a":
            self._anchor_href = attr.get("href", "")
            self._anchor_chunks = []

    def handle_endtag(self, tag: str) -> None:
        if self._list_depth and tag == "a" and self._anchor_href:
            title = clean_text(html.unescape(" ".join(self._anchor_chunks)))
            if title:
                self.results.append({"title": title, "url": self._anchor_href})
            self._anchor_href = ""
            self._anchor_chunks = []
        if self._list_depth:
            self._list_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._list_depth and self._anchor_href:
            self._anchor_chunks.append(data)


def parse_boja_results(body: str, *, base_url: str, limit: int) -> tuple[int, list[dict[str, Any]]]:
    parser = BojaResultParser()
    parser.feed(body)
    total = 0
    total_match = re.search(r"<strong>\s*([\d.]+)\s*</strong>\s+recursos disponibles", body, flags=re.IGNORECASE)
    if total_match:
        total = int(total_match.group(1).replace(".", ""))
    elif "No se han encontrado resultados" in body:
        total = 0
    else:
        total = len(parser.results)
    candidates: list[dict[str, Any]] = []
    for index, row in enumerate(parser.results[: max(0, limit)], start=1):
        url = urllib.parse.urljoin(base_url, row["url"])
        candidates.append(
            {
                "candidate_id": stable_slug(f"boja:{url}:{row['title']}"),
                "rank": index,
                "registry": "boja",
                "title": compact_text(row["title"]),
                "url": url,
                "machine_readable": False,
            }
        )
    return total, candidates


def run_junta_open_data_target(
    target: dict[str, Any],
    *,
    rows_per_query: int,
    timeout: int,
    ckan_search: Callable[..., list[dict[str, Any]]] = ckan_package_search,
) -> dict[str, Any]:
    packages = ckan_search(str(target.get("query") or ""), rows=rows_per_query, timeout=timeout)
    candidates: list[dict[str, Any]] = []
    for index, package in enumerate(packages[: max(0, rows_per_query)], start=1):
        if not isinstance(package, dict):
            continue
        resources = [compact_resource(resource) for resource in package.get("resources") or [] if isinstance(resource, dict)]
        machine_resources = [resource for resource in resources if resource.get("machine_readable")]
        candidates.append(
            {
                "candidate_id": stable_slug(f"junta-open-data:{package.get('name') or package.get('title') or index}"),
                "rank": index,
                "registry": "junta_open_data",
                "package_name": clean_text(package.get("name")),
                "title": clean_text(package.get("title") or package.get("name")),
                "url": portal_dataset_url(package),
                "notes": compact_text(package.get("notes")),
                "resources_total": len(resources),
                "machine_resources_total": len(machine_resources),
                "machine_readable": bool(machine_resources),
                "resources": resources[:3],
            }
        )
    return {
        "status": "ok" if candidates else "no_results",
        "fetch_url": "",
        "http_status": 200,
        "result_candidates_total": len(candidates),
        "result_candidates_machine_readable_total": sum(1 for row in candidates if row.get("machine_readable")),
        "result_candidates": candidates,
    }


def run_boja_target(
    target: dict[str, Any],
    *,
    rows_per_query: int,
    timeout: int,
    text_fetch: Callable[..., tuple[str, int, str, str]] = fetch_text_url,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    last_response: dict[str, Any] = {}
    for variant in query_variants_for_target(target):
        fetch_url = boja_fetch_url(variant["query"])
        try:
            body, status, content_type, final_url = text_fetch(fetch_url, timeout=timeout)
        except Exception as exc:  # pragma: no cover - network failures vary by host/runtime
            attempt = {
                "query_variant": variant["query_variant"],
                "query": variant["query"],
                "fetch_url": fetch_url,
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "result_candidates_total": 0,
            }
            attempts.append(attempt)
            last_response = attempt
            continue
        results_total, candidates = parse_boja_results(body, base_url=final_url, limit=rows_per_query)
        attempt = {
            "query_variant": variant["query_variant"],
            "query": variant["query"],
            "fetch_url": fetch_url,
            "status": "ok" if candidates else "no_results",
            "http_status": status,
            "content_type": content_type,
            "results_total": results_total,
            "result_candidates_total": len(candidates),
        }
        attempts.append(attempt)
        last_response = attempt
        if candidates:
            return {
                "status": "ok",
                "fetch_url": fetch_url,
                "http_status": status,
                "content_type": content_type,
                "query_variant": variant["query_variant"],
                "query_attempts_total": len(attempts),
                "query_attempt_errors_total": sum(1 for row in attempts if row.get("status") == "error"),
                "query_attempts": attempts,
                "results_total": results_total,
                "result_candidates_total": len(candidates),
                "result_candidates_machine_readable_total": 0,
                "result_candidates": candidates,
            }
    all_attempts_failed = bool(attempts) and all(row.get("status") == "error" for row in attempts)
    return {
        "status": "error" if all_attempts_failed else "no_results",
        "fetch_url": str(last_response.get("fetch_url") or ""),
        "http_status": int(last_response.get("http_status") or 0),
        "content_type": str(last_response.get("content_type") or ""),
        "query_variant": str(last_response.get("query_variant") or ""),
        "query_attempts_total": len(attempts),
        "query_attempt_errors_total": sum(1 for row in attempts if row.get("status") == "error"),
        "query_attempts": attempts,
        "results_total": int(last_response.get("results_total") or 0),
        "result_candidates_total": 0,
        "result_candidates_machine_readable_total": 0,
        "result_candidates": [],
    }


def bdns_query_variants_for_target(target: dict[str, Any]) -> list[dict[str, str]]:
    variants: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(kind: str, query: Any) -> None:
        text = compact_text(query, limit=190)
        key = normalize_label(text)
        if not key or key in seen:
            return
        seen.add(key)
        variants.append({"query_variant": kind, "query": text})

    target_query = clean_text(target.get("query"))
    beneficiary = clean_text(target.get("grant_beneficiary"))
    reviewed_label = clean_text(target.get("reviewed_label"))
    query_without_context = target_query
    for removable in (beneficiary, reviewed_label):
        if removable:
            query_without_context = re.sub(re.escape(removable), " ", query_without_context, flags=re.IGNORECASE)
    query_without_context = re.sub(r"\s+", " ", query_without_context).strip(" ,;-")

    add("grant_announcement_or_finality", query_without_context)
    if re.search(r"\bvalcarcel\b", target_query, flags=re.IGNORECASE):
        add("distinctive_bdns_term", "VALCARCEL")
    if re.search(r"\bpima\b", target_query, flags=re.IGNORECASE) and re.search(
        r"cambio\s+clim[aá]tico", target_query, flags=re.IGNORECASE
    ):
        add("distinctive_bdns_term", "PIMA cambio climático")
    uned_match = re.search(r"Centro\s+UNED\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)", target_query, flags=re.IGNORECASE)
    if uned_match:
        add("distinctive_bdns_term", f"Centro UNED {uned_match.group(1)}")
    add("reviewed_label", reviewed_label)
    add("exact_target_query", target_query)
    return variants


def bdns_terceros_url(query: str) -> str:
    return api_url(BDNS_API_BASE, "terceros", {"vpd": "GE", "busqueda": query})


def bdns_concesiones_url(
    *,
    beneficiary_id: str = "",
    description: str = "",
    page_size: int,
) -> str:
    return api_url(
        BDNS_API_BASE,
        "concesiones/busqueda",
        {
            "vpd": "GE",
            "beneficiario": beneficiary_id,
            "descripcion": description,
            "page": "0",
            "pageSize": str(page_size),
            "order": "fechaConcesion",
            "direccion": "desc",
        },
    )


def bdns_convocatorias_url(*, description: str, page_size: int) -> str:
    return api_url(
        BDNS_API_BASE,
        "convocatorias/busqueda",
        {
            "vpd": "GE",
            "descripcion": description,
            "page": "0",
            "pageSize": str(page_size),
            "order": "fechaRecepcion",
            "direccion": "desc",
        },
    )


def bdns_total_elements(data: dict[str, Any]) -> int:
    value = data.get("totalElements")
    if isinstance(value, int):
        return value
    rows = data.get("content")
    return len(rows) if isinstance(rows, list) else 0


def bdns_beneficiary_ids(data: dict[str, Any], *, limit: int = 3) -> list[dict[str, str]]:
    rows = data.get("terceros")
    if not isinstance(rows, list):
        return []
    ids: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        person_id = clean_text(row.get("id"))
        if not person_id or person_id in seen:
            continue
        seen.add(person_id)
        ids.append({"id": person_id, "description": clean_text(row.get("descripcion"))})
        if len(ids) >= limit:
            break
    return ids


def bdns_concession_candidate(row: dict[str, Any], *, rank: int, source_url: str) -> dict[str, Any]:
    row_id = clean_text(row.get("id") or row.get("codConcesion") or row.get("numeroConvocatoria") or rank)
    return {
        "candidate_id": stable_slug(f"bdns-concession:{row_id}"),
        "rank": rank,
        "registry": "bdns",
        "candidate_type": "concession",
        "title": compact_text(row.get("convocatoria")),
        "url": source_url,
        "api_url": source_url,
        "boja_url": clean_text(row.get("urlBR")),
        "machine_readable": True,
        "bdns_concession_id": clean_text(row.get("id")),
        "cod_concesion": clean_text(row.get("codConcesion")),
        "numero_convocatoria": clean_text(row.get("numeroConvocatoria")),
        "id_convocatoria": clean_text(row.get("idConvocatoria")),
        "fecha_concesion": clean_text(row.get("fechaConcesion")),
        "fecha_alta": clean_text(row.get("fechaAlta")),
        "beneficiario": clean_text(row.get("beneficiario")),
        "beneficiario_id": clean_text(row.get("idPersona")),
        "importe": compact_number(row.get("importe")),
        "ayuda_equivalente": compact_number(row.get("ayudaEquivalente")),
        "instrumento": clean_text(row.get("instrumento")),
        "nivel1": clean_text(row.get("nivel1")),
        "nivel2": clean_text(row.get("nivel2")),
        "nivel3": clean_text(row.get("nivel3")),
    }


def bdns_convocatoria_candidate(row: dict[str, Any], *, rank: int, source_url: str) -> dict[str, Any]:
    row_id = clean_text(row.get("id") or row.get("numeroConvocatoria") or rank)
    return {
        "candidate_id": stable_slug(f"bdns-convocatoria:{row_id}"),
        "rank": rank,
        "registry": "bdns",
        "candidate_type": "convocatoria",
        "title": compact_text(row.get("descripcion")),
        "url": source_url,
        "api_url": source_url,
        "machine_readable": True,
        "bdns_convocatoria_id": clean_text(row.get("id")),
        "numero_convocatoria": clean_text(row.get("numeroConvocatoria")),
        "fecha_recepcion": clean_text(row.get("fechaRecepcion")),
        "nivel1": clean_text(row.get("nivel1")),
        "nivel2": clean_text(row.get("nivel2")),
        "nivel3": clean_text(row.get("nivel3")),
        "mrr": bool(row.get("mrr")),
    }


def run_bdns_target(
    target: dict[str, Any],
    *,
    rows_per_query: int,
    timeout: int,
    json_fetch: Callable[..., tuple[dict[str, Any], int, str, str]] = fetch_json_url,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    seen_candidates: set[str] = set()
    beneficiary = clean_text(target.get("grant_beneficiary"))
    beneficiary_ids: list[dict[str, str]] = []

    def add_candidates(new_candidates: list[dict[str, Any]]) -> None:
        for candidate in new_candidates:
            candidate_id = clean_text(candidate.get("candidate_id"))
            if not candidate_id or candidate_id in seen_candidates:
                continue
            seen_candidates.add(candidate_id)
            candidates.append(candidate)
            if len(candidates) >= rows_per_query:
                break

    if beneficiary:
        lookup_url = bdns_terceros_url(beneficiary)
        try:
            data, status, content_type, final_url = json_fetch(lookup_url, timeout=timeout)
            beneficiary_ids = bdns_beneficiary_ids(data)
            attempts.append(
                {
                    "query_variant": "beneficiary_lookup",
                    "query": beneficiary,
                    "fetch_url": lookup_url,
                    "status": "ok" if beneficiary_ids else "no_results",
                    "http_status": status,
                    "content_type": content_type,
                    "final_url": final_url,
                    "results_total": len(data.get("terceros") or []),
                    "beneficiary_ids": beneficiary_ids,
                    "result_candidates_total": 0,
                }
            )
        except Exception as exc:  # pragma: no cover - network failures vary by host/runtime
            attempts.append(
                {
                    "query_variant": "beneficiary_lookup",
                    "query": beneficiary,
                    "fetch_url": lookup_url,
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "result_candidates_total": 0,
                }
            )

    for variant in bdns_query_variants_for_target(target):
        beneficiary_id_values = [row["id"] for row in beneficiary_ids] or [""]
        for beneficiary_id in beneficiary_id_values:
            if len(candidates) >= rows_per_query:
                break
            fetch_url = bdns_concesiones_url(
                beneficiary_id=beneficiary_id,
                description=variant["query"],
                page_size=rows_per_query,
            )
            try:
                data, status, content_type, final_url = json_fetch(fetch_url, timeout=timeout)
                rows = [row for row in data.get("content") or [] if isinstance(row, dict)]
                matched_variant = f"concession_{variant['query_variant']}"
                new_candidates = [
                    bdns_concession_candidate(row, rank=len(candidates) + index, source_url=final_url)
                    for index, row in enumerate(rows[: max(0, rows_per_query - len(candidates))], start=1)
                ]
                for candidate in new_candidates:
                    candidate["matched_query_variant"] = matched_variant
                    candidate["matched_query"] = variant["query"]
                add_candidates(new_candidates)
                attempts.append(
                    {
                        "query_variant": matched_variant,
                        "query": variant["query"],
                        "beneficiary_id": beneficiary_id,
                        "fetch_url": fetch_url,
                        "status": "ok" if new_candidates else "no_results",
                        "http_status": status,
                        "content_type": content_type,
                        "final_url": final_url,
                        "results_total": bdns_total_elements(data),
                        "result_candidates_total": len(new_candidates),
                    }
                )
            except Exception as exc:  # pragma: no cover - network failures vary by host/runtime
                attempts.append(
                    {
                        "query_variant": f"concession_{variant['query_variant']}",
                        "query": variant["query"],
                        "beneficiary_id": beneficiary_id,
                        "fetch_url": fetch_url,
                        "status": "error",
                        "error": f"{type(exc).__name__}: {exc}",
                        "result_candidates_total": 0,
                    }
                )

        if len(candidates) >= rows_per_query:
            break

        fetch_url = bdns_convocatorias_url(description=variant["query"], page_size=rows_per_query)
        try:
            data, status, content_type, final_url = json_fetch(fetch_url, timeout=timeout)
            rows = [row for row in data.get("content") or [] if isinstance(row, dict)]
            concession_numbers = {
                clean_text(row.get("numero_convocatoria"))
                for row in candidates
                if row.get("candidate_type") == "concession" and clean_text(row.get("numero_convocatoria"))
            }
            if concession_numbers:
                rows = [row for row in rows if clean_text(row.get("numeroConvocatoria")) in concession_numbers]
            new_candidates = [
                bdns_convocatoria_candidate(row, rank=len(candidates) + index, source_url=final_url)
                for index, row in enumerate(rows[: max(0, rows_per_query - len(candidates))], start=1)
            ]
            add_candidates(new_candidates)
            attempts.append(
                {
                    "query_variant": f"convocatoria_{variant['query_variant']}",
                    "query": variant["query"],
                    "fetch_url": fetch_url,
                    "status": "ok" if new_candidates else "no_results",
                    "http_status": status,
                    "content_type": content_type,
                    "final_url": final_url,
                    "results_total": bdns_total_elements(data),
                    "result_candidates_total": len(new_candidates),
                }
            )
        except Exception as exc:  # pragma: no cover - network failures vary by host/runtime
            attempts.append(
                {
                    "query_variant": f"convocatoria_{variant['query_variant']}",
                    "query": variant["query"],
                    "fetch_url": fetch_url,
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "result_candidates_total": 0,
                }
            )
        if len(candidates) >= rows_per_query:
            break

    if not candidates:
        for beneficiary_id in [row["id"] for row in beneficiary_ids]:
            fetch_url = bdns_concesiones_url(beneficiary_id=beneficiary_id, page_size=rows_per_query)
            try:
                data, status, content_type, final_url = json_fetch(fetch_url, timeout=timeout)
                rows = [row for row in data.get("content") or [] if isinstance(row, dict)]
                matched_variant = "concession_beneficiary_only"
                new_candidates = [
                    bdns_concession_candidate(row, rank=index, source_url=final_url)
                    for index, row in enumerate(rows[:rows_per_query], start=1)
                ]
                for candidate in new_candidates:
                    candidate["matched_query_variant"] = matched_variant
                    candidate["matched_query"] = beneficiary
                add_candidates(new_candidates)
                attempts.append(
                    {
                        "query_variant": "concession_beneficiary_only",
                        "query": beneficiary,
                        "beneficiary_id": beneficiary_id,
                        "fetch_url": fetch_url,
                        "status": "ok" if new_candidates else "no_results",
                        "http_status": status,
                        "content_type": content_type,
                        "final_url": final_url,
                        "results_total": bdns_total_elements(data),
                        "result_candidates_total": len(new_candidates),
                    }
                )
            except Exception as exc:  # pragma: no cover - network failures vary by host/runtime
                attempts.append(
                    {
                        "query_variant": "concession_beneficiary_only",
                        "query": beneficiary,
                        "beneficiary_id": beneficiary_id,
                        "fetch_url": fetch_url,
                        "status": "error",
                        "error": f"{type(exc).__name__}: {exc}",
                        "result_candidates_total": 0,
                    }
                )
            if candidates:
                break

    all_attempts_failed = bool(attempts) and all(row.get("status") == "error" for row in attempts)
    first_fetch = next((row for row in attempts if row.get("fetch_url")), {})
    return {
        "status": "ok" if candidates else "error" if all_attempts_failed else "no_results",
        "fetch_url": str(first_fetch.get("fetch_url") or ""),
        "http_status": int(first_fetch.get("http_status") or 0),
        "content_type": str(first_fetch.get("content_type") or ""),
        "query_variant": str(first_fetch.get("query_variant") or ""),
        "query_attempts_total": len(attempts),
        "query_attempt_errors_total": sum(1 for row in attempts if row.get("status") == "error"),
        "query_attempts": attempts,
        "beneficiary_ids": beneficiary_ids,
        "results_total": max((int(row.get("results_total") or 0) for row in attempts), default=0),
        "result_candidates_total": len(candidates),
        "result_candidates_machine_readable_total": sum(1 for row in candidates if row.get("machine_readable")),
        "result_candidates": candidates,
    }


def pdc_contract_search_terms(target: dict[str, Any]) -> list[dict[str, str]]:
    contract_reference = clean_text(target.get("contract_reference") or target.get("query"))
    terms: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(kind: str, term: str) -> None:
        value = clean_text(term)
        key = normalize_label(value)
        if not value or key in seen:
            return
        seen.add(key)
        terms.append({"query_variant": kind, "query": value})

    numeric_terms = sorted(re.findall(r"\d{6,}", contract_reference), key=len, reverse=True)
    for term in numeric_terms:
        add("contract_numeric_reference", term)
        stripped = term.lstrip("0")
        if stripped != term:
            add("contract_numeric_reference_no_leading_zeroes", stripped)
    add("contract_reference", contract_reference)
    add("reviewed_label", clean_text(target.get("reviewed_label")))
    return terms


def pdc_query_payload(query: str, *, rows_per_query: int) -> dict[str, Any]:
    return {
        "query": {
            "bool": {
                "must": [
                    {"match": {"codigoProcedimiento": "9"}},
                    {
                        "query_string": {
                            "fields": [
                                "numeroExpediente",
                                "titulo",
                                "tipoContrato.descripcion",
                                "perfilContratante.descripcion",
                                "estado.nombre",
                            ],
                            "query": f"*{query}*",
                            "default_operator": "and",
                        }
                    },
                ],
                "must_not": [{"match": {"estado.codigo": {"query": "BRR"}}}],
                "should": [],
            }
        },
        "size": rows_per_query,
        "sort": [],
        "track_total_hits": True,
        "from": 0,
    }


def pdc_hits_total(data: dict[str, Any]) -> int:
    hits = data.get("hits") if isinstance(data.get("hits"), dict) else {}
    total = hits.get("total") if isinstance(hits, dict) else {}
    if isinstance(total, dict) and isinstance(total.get("value"), int):
        return int(total["value"])
    if isinstance(total, int):
        return total
    rows = hits.get("hits") if isinstance(hits, dict) else []
    return len(rows) if isinstance(rows, list) else 0


def pdc_compact_awards(source: dict[str, Any]) -> list[dict[str, Any]]:
    rows = source.get("adjudicaciones")
    if not isinstance(rows, list):
        return []
    awards: list[dict[str, Any]] = []
    for row in rows[:3]:
        if not isinstance(row, dict):
            continue
        awards.append(
            {
                "nombre_adjudicatario": clean_text(row.get("nombreAdjudicatario")).strip("; "),
                "nif_adjudicatario": clean_text(row.get("nifAdjudicatario")).strip("; "),
                "importe_adjudicacion": compact_number(row.get("importeAdjudicacion")),
                "fecha_formalizacion": clean_text(row.get("fechaFormalizacion")),
                "fecha_resolucion": clean_text(row.get("fechaResolucion")),
                "codigo_resultado": clean_text(row.get("codigoResultado")),
            }
        )
    return awards


def pdc_candidate(hit: dict[str, Any], *, rank: int, source_url: str) -> dict[str, Any]:
    source = hit.get("_source") if isinstance(hit.get("_source"), dict) else {}
    hit_id = clean_text(hit.get("_id") or source.get("idExpediente") or rank)
    detail_url = f"{PDC_DETAIL_BASE_URL}?{urllib.parse.urlencode({'idExpediente': hit_id})}"
    return {
        "candidate_id": stable_slug(f"junta-procurement:{hit_id}"),
        "rank": rank,
        "registry": "junta_procurement_registry",
        "candidate_type": "contract",
        "title": compact_text(source.get("titulo")),
        "url": detail_url,
        "api_url": source_url,
        "machine_readable": True,
        "id_expediente": clean_text(source.get("idExpediente") or hit_id),
        "numero_expediente": clean_text(source.get("numeroExpediente")),
        "tipo_contrato": nested_text(source, "tipoContrato", "descripcion"),
        "perfil_contratante": nested_text(source, "perfilContratante", "descripcion"),
        "estado": nested_text(source, "estado", "nombre"),
        "importe_licitacion": compact_number(source.get("importeLicitacion")),
        "valor_estimado": compact_number(source.get("valorEstimado")),
        "fecha_publicacion": clean_text(source.get("fechaPublicacion")),
        "portal_gestor": bool(source.get("portalGestor")),
        "adjudicaciones_total": len(source.get("adjudicaciones") or []),
        "adjudicaciones": pdc_compact_awards(source),
    }


def run_junta_procurement_registry_target(
    target: dict[str, Any],
    *,
    rows_per_query: int,
    timeout: int,
    json_fetch: Callable[..., tuple[dict[str, Any], int, str, str]] = fetch_json_url,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    for variant in pdc_contract_search_terms(target):
        payload = pdc_query_payload(variant["query"], rows_per_query=rows_per_query)
        try:
            data, status, content_type, final_url = json_fetch(PDC_ELASTIC_SEARCH_URL, timeout=timeout, payload=payload)
            hits_container = data.get("hits") if isinstance(data.get("hits"), dict) else {}
            hits = [row for row in hits_container.get("hits") or [] if isinstance(row, dict)]
            candidates = [
                pdc_candidate(row, rank=index, source_url=final_url)
                for index, row in enumerate(hits[:rows_per_query], start=1)
            ]
            attempt = {
                "query_variant": variant["query_variant"],
                "query": variant["query"],
                "fetch_url": PDC_ELASTIC_SEARCH_URL,
                "status": "ok" if candidates else "no_results",
                "http_status": status,
                "content_type": content_type,
                "final_url": final_url,
                "results_total": pdc_hits_total(data),
                "result_candidates_total": len(candidates),
            }
            attempts.append(attempt)
            if candidates:
                return {
                    "status": "ok",
                    "fetch_url": PDC_ELASTIC_SEARCH_URL,
                    "http_status": status,
                    "content_type": content_type,
                    "query_variant": variant["query_variant"],
                    "query_attempts_total": len(attempts),
                    "query_attempt_errors_total": sum(1 for row in attempts if row.get("status") == "error"),
                    "query_attempts": attempts,
                    "results_total": pdc_hits_total(data),
                    "result_candidates_total": len(candidates),
                    "result_candidates_machine_readable_total": sum(1 for row in candidates if row.get("machine_readable")),
                    "result_candidates": candidates,
                }
        except Exception as exc:  # pragma: no cover - network failures vary by host/runtime
            attempts.append(
                {
                    "query_variant": variant["query_variant"],
                    "query": variant["query"],
                    "fetch_url": PDC_ELASTIC_SEARCH_URL,
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "result_candidates_total": 0,
                }
            )
    all_attempts_failed = bool(attempts) and all(row.get("status") == "error" for row in attempts)
    last_response = attempts[-1] if attempts else {}
    return {
        "status": "error" if all_attempts_failed else "no_results",
        "fetch_url": PDC_ELASTIC_SEARCH_URL,
        "http_status": int(last_response.get("http_status") or 0),
        "content_type": str(last_response.get("content_type") or ""),
        "query_variant": str(last_response.get("query_variant") or ""),
        "query_attempts_total": len(attempts),
        "query_attempt_errors_total": sum(1 for row in attempts if row.get("status") == "error"),
        "query_attempts": attempts,
        "results_total": int(last_response.get("results_total") or 0),
        "result_candidates_total": 0,
        "result_candidates_machine_readable_total": 0,
        "result_candidates": [],
    }


def run_target(target: dict[str, Any], *, rows_per_query: int, timeout: int) -> dict[str, Any]:
    registry = str(target.get("registry") or "")
    if registry in MANUAL_REGISTRIES:
        return {
            "status": "manual_search_landing_ready",
            "manual_reason": MANUAL_REGISTRIES[registry],
            "result_candidates_total": 0,
            "result_candidates_machine_readable_total": 0,
            "result_candidates": [],
        }
    try:
        if registry == "junta_open_data":
            return run_junta_open_data_target(target, rows_per_query=rows_per_query, timeout=timeout)
        if registry == "boja":
            return run_boja_target(target, rows_per_query=rows_per_query, timeout=timeout)
        if registry == "bdns":
            return run_bdns_target(target, rows_per_query=rows_per_query, timeout=timeout)
        if registry == "junta_procurement_registry":
            return run_junta_procurement_registry_target(target, rows_per_query=rows_per_query, timeout=timeout)
        return {
            "status": "manual_search_landing_ready",
            "manual_reason": "registry_runner_not_wired",
            "result_candidates_total": 0,
            "result_candidates_machine_readable_total": 0,
            "result_candidates": [],
        }
    except urllib.error.HTTPError as exc:
        return {
            "status": "error",
            "http_status": int(exc.code),
            "error": f"HTTPError: {exc}",
            "result_candidates_total": 0,
            "result_candidates_machine_readable_total": 0,
            "result_candidates": [],
        }
    except Exception as exc:  # pragma: no cover - network failures vary by host/runtime
        return {
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "result_candidates_total": 0,
            "result_candidates_machine_readable_total": 0,
            "result_candidates": [],
        }


def build_hunt_report(
    snapshot: dict[str, Any],
    *,
    source_snapshot_path: str,
    max_targets: int = DEFAULT_MAX_TARGETS,
    rows_per_query: int = DEFAULT_ROWS_PER_QUERY,
    timeout: int = DEFAULT_TIMEOUT,
    runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    targets = collect_search_targets(snapshot, max_targets=max_targets)
    run_rows: list[dict[str, Any]] = []
    for target in targets:
        result = runner(target) if runner else run_target(target, rows_per_query=rows_per_query, timeout=timeout)
        run_row = dict(target)
        run_row.update(result)
        run_rows.append(run_row)

    status_counts = Counter(str(row.get("status") or "") for row in run_rows)
    registry_counts = Counter(str(row.get("registry") or "") for row in run_rows)
    topics_with_candidates = {
        str(row.get("topic_id") or "")
        for row in run_rows
        if int(row.get("result_candidates_total") or 0) > 0
    }
    hunts_with_candidates = {
        str(row.get("hunt_id") or "")
        for row in run_rows
        if int(row.get("result_candidates_total") or 0) > 0
    }
    return {
        "schema_version": "andalucia_2026_delivery_evidence_hunt_results_v1",
        "generated_at": now_utc_iso(),
        "source_snapshot": source_snapshot_path,
        "parameters": {
            "max_targets": max_targets,
            "rows_per_query": rows_per_query,
            "timeout": timeout,
        },
        "summary": {
            "targets_total": len(run_rows),
            "targets_executed_total": sum(
                1 for row in run_rows if row.get("status") not in {"manual_search_landing_ready"}
            ),
            "targets_manual_total": status_counts.get("manual_search_landing_ready", 0),
            "targets_ok_total": status_counts.get("ok", 0),
            "targets_no_results_total": status_counts.get("no_results", 0),
            "query_errors_total": status_counts.get("error", 0),
            "query_attempt_errors_total": sum(int(row.get("query_attempt_errors_total") or 0) for row in run_rows),
            "result_candidates_total": sum(int(row.get("result_candidates_total") or 0) for row in run_rows),
            "result_candidates_machine_readable_total": sum(
                int(row.get("result_candidates_machine_readable_total") or 0) for row in run_rows
            ),
            "topics_with_result_candidates_total": len(topics_with_candidates),
            "hunts_with_result_candidates_total": len(hunts_with_candidates),
            "status_counts": dict(status_counts),
            "registry_counts": dict(registry_counts),
        },
        "targets": run_rows,
    }


def main() -> int:
    args = parse_args()
    snapshot_path = Path(args.snapshot)
    snapshot = read_json(snapshot_path)
    report = build_hunt_report(
        snapshot,
        source_snapshot_path=str(snapshot_path),
        max_targets=max(0, args.max_targets),
        rows_per_query=max(1, args.rows_per_query),
        timeout=max(1, args.timeout),
    )
    out = Path(args.out)
    public_out = Path(args.public_out)
    write_json(out, report)
    write_json(public_out, report)
    summary = report["summary"]
    print(
        "targets={targets_total} executed={targets_executed_total} manual={targets_manual_total} "
        "candidates={result_candidates_total} machine={result_candidates_machine_readable_total} "
        "errors={query_errors_total}".format(**summary)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
