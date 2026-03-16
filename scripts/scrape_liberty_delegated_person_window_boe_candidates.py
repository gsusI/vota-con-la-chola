#!/usr/bin/env python3
"""Scrape BOE search candidates for delegated person/window backlog targets."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

STRICT_FAIL_EXIT = 4
DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; vota-con-la-chola-bot/1.0; +https://www.boe.es/)"
BOE_REDIRECTOR = "https://www.boe.es/buscar/redirector.php"
INSTITUTION_QUERY_EXPANSIONS = {
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
    token = re.sub(r"\s+", " ", token)
    return token.strip()


def _strip_html(raw: str) -> str:
    text = re.sub(r"<[^>]+>", "", raw)
    return html.unescape(text).strip()


def _clean_person_hint(value: str) -> str:
    token = _norm(value).strip(" ,.;:-")
    token = re.sub(r"\s+", " ", token)
    return _norm(token)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_query(role_title: str, institution: str) -> str:
    role = _norm(role_title)
    inst = _norm(institution)
    if role and inst:
        return f"nombramiento {role} {inst}"
    if role:
        return f"nombramiento {role}"
    if inst:
        return f"nombramiento {inst}"
    return "nombramiento"


def _role_phrase_variants(role_title: str, institution: str, institution_expanded: str) -> list[str]:
    role = _norm(role_title)
    role_fold = _fold(role)
    inst = _norm(institution)
    inst_expanded = _norm(institution_expanded)
    variants: list[str] = []
    seen: set[str] = set()

    def push(value: str) -> None:
        token = _norm(value)
        if not token:
            return
        key = _fold(token)
        if key in seen:
            return
        seen.add(key)
        variants.append(token)

    role_with_expanded_inst = role
    if "aeat" in role_fold and inst_expanded:
        role_with_expanded_inst = re.sub(r"(?i)\baeat\b", inst_expanded, role)

    inst_for_direction = inst_expanded or inst
    inst_for_direction_fold = _fold(inst_for_direction)
    if "direccion general" in role_fold:
        if "direccion general de " in inst_for_direction_fold:
            suffix = re.sub(r"(?i)^direcci[oó]n\s+general\s+de\s+", "", inst_for_direction).strip()
            if suffix:
                push(f"Director General de {suffix}")
        elif inst_for_direction:
            push(f"Director General de {inst_for_direction}")
        push(re.sub(r"(?i)direcci[oó]n\s+general", "Director General", role_with_expanded_inst))

    if "subdireccion" in role_fold:
        push(re.sub(r"(?i)subdirecci[oó]n", "Subdirector", role_with_expanded_inst))

    if "jefatura" in role_fold:
        tail = re.sub(r"(?i)jefatura\s+de\s+", "", role_with_expanded_inst).strip()
        if tail:
            push(f"Jefe de {tail}")
            push(f"Jefa de {tail}")
        push("Jefe de la Inspección de Trabajo y Seguridad Social")
        push("Jefa de la Inspección de Trabajo y Seguridad Social")

    if "organismo estatal" in role_fold and ("itss" in role_fold or "inspeccion de trabajo" in role_fold):
        push("Director del Organismo Estatal Inspección de Trabajo y Seguridad Social")
        push("Director General de Inspección de Trabajo y Seguridad Social")

    push(role_with_expanded_inst)
    return variants


def build_query_variants(role_title: str, institution: str) -> list[str]:
    role = _norm(role_title)
    inst = _norm(institution)
    variants: list[str] = []
    seen: set[str] = set()

    def push(query: str) -> None:
        token = _norm(query)
        if not token:
            return
        key = _norm_lc(token)
        if key in seen:
            return
        seen.add(key)
        variants.append(token)

    inst_key = _norm_lc(inst)
    expanded = _norm(INSTITUTION_QUERY_EXPANSIONS.get(inst_key))
    role_variants = _role_phrase_variants(role, inst, expanded)
    inst_variants: list[str] = []
    if expanded:
        inst_variants.append(expanded)
    if inst and _fold(inst) != _fold(expanded):
        inst_variants.append(inst)

    for role_phrase in role_variants:
        role_phrase_fold = _fold(role_phrase)
        for inst_phrase in inst_variants:
            inst_phrase_fold = _fold(inst_phrase)
            if inst_phrase and inst_phrase_fold and inst_phrase_fold not in role_phrase_fold:
                push(f'nombramiento "{role_phrase}" "{inst_phrase}"')
                push(f"nombramiento {role_phrase} {inst_phrase}")
        push(f'nombramiento "{role_phrase}"')
        push(f"nombramiento {role_phrase}")

    for inst_phrase in inst_variants:
        push(f'nombramiento "{inst_phrase}"')
        push(f"nombramiento {inst_phrase}")

    push(build_query(role, inst))
    if inst:
        push(f"nombramiento {inst}")
    if role:
        push(f"nombramiento {role}")
    return variants


def _extract_person_hint(title: str) -> str:
    normalized = " ".join(_norm(title).split())
    patterns = [
        re.compile(r"nombramiento de (?:don|doña|d\.\s*|dña\.\s*)(.+?)\s+como", re.IGNORECASE),
        re.compile(r"nombrar a (?:don|doña|d\.\s*|dña\.\s*)(.+?)\s+como", re.IGNORECASE),
        re.compile(
            r"nombramiento\s+como.+?\s+de\s+(?:don|doña|d\.\s*|dña\.\s*)(.+?)(?:[,.;]|$)",
            re.IGNORECASE,
        ),
        re.compile(
            r"nombramiento.*?,\s*de\s+(?:don|doña|d\.\s*|dña\.\s*)(.+?)(?:\s+como|[,.;]\s+como|[,.;]|$)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:don|doña|d\.\s*|dña\.\s*)"
            r"([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑÜáéíóúñü'’\-]+(?:\s+[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑÜáéíóúñü'’\-]+){1,5})",
            re.IGNORECASE,
        ),
    ]
    for pattern in patterns:
        m = pattern.search(normalized)
        if m:
            cleaned = _clean_person_hint(m.group(1))
            if cleaned:
                return cleaned
    return ""


@dataclass
class SearchResult:
    boe_id: str
    doc_url: str
    publication_date: str
    department: str
    title: str


def parse_boe_search_results(html_text: str) -> list[SearchResult]:
    chunks = html_text.split('<li class="resultado-busqueda">')[1:]
    results: list[SearchResult] = []
    for chunk in chunks:
        body = chunk.split("</li>", 1)[0]
        boe_match = re.search(r"doc\.php\?id=(BOE-A-\d+-\d+)", body)
        if not boe_match:
            continue
        boe_id = _norm(boe_match.group(1))

        dep_match = re.search(r'<p class="linea-dem">(.*?)</p>', body, flags=re.S)
        pub_match = re.search(r'<p class="linea-pub">(.*?)</p>', body, flags=re.S)
        title_match = re.search(r"<p>(.*?)</p>", body, flags=re.S)

        department = _strip_html(dep_match.group(1)) if dep_match else ""
        pub_line = _strip_html(pub_match.group(1)) if pub_match else ""
        title = _strip_html(title_match.group(1)) if title_match else ""

        date_match = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", pub_line)
        publication_date = _norm(date_match.group(1)) if date_match else ""

        results.append(
            SearchResult(
                boe_id=boe_id,
                doc_url=f"https://www.boe.es/buscar/doc.php?id={boe_id}",
                publication_date=publication_date,
                department=department,
                title=title,
            )
        )
    return results


def fetch_boe_search_html(query: str, timeout: int, user_agent: str) -> tuple[str, str]:
    url = (
        f"{BOE_REDIRECTOR}?accion=Buscar&bd=boe&texto={quote(query)}"
    )
    req = Request(url, headers={"User-Agent": user_agent})
    with urlopen(req, timeout=timeout) as response:
        html_text = response.read().decode("utf-8", "ignore")
        final_url = _norm(response.geturl())
    return html_text, final_url


def _has_match(tokens: list[str], haystack: str) -> bool:
    hs = _norm_lc(haystack)
    return any(token and token in hs for token in tokens)


def _build_tokens(raw: str) -> list[str]:
    tokens = re.findall(r"[a-zA-ZáéíóúñüÁÉÍÓÚÑÜ]{4,}", _norm_lc(raw))
    # Keep first 6 meaningful tokens to avoid overfitting.
    uniq: list[str] = []
    for token in tokens:
        if token not in uniq:
            uniq.append(token)
        if len(uniq) >= 6:
            break
    return uniq


def _institution_tokens(raw_institution: str) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()

    def add_many(raw: str) -> None:
        for token in _build_tokens(raw):
            if token in seen:
                continue
            seen.add(token)
            tokens.append(token)

    institution = _norm(raw_institution)
    add_many(institution)
    expanded = _norm(INSTITUTION_QUERY_EXPANSIONS.get(_norm_lc(institution)))
    if expanded:
        add_many(expanded)
    return tokens


def _priority_from_match(institution_match: bool, role_match: bool, rank: int) -> int:
    score = 0
    if institution_match:
        score += 20
    if role_match:
        score += 20
    score += max(0, 10 - rank)
    return score


def scrape_candidates(
    targets_rows: list[dict[str, str]],
    *,
    top_results_per_target: int,
    timeout: int,
    user_agent: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    query_cache: dict[str, tuple[list[SearchResult], str, bool]] = {}
    total_targets = 0
    targets_with_results = 0
    http_errors = 0
    unique_doc_ids: set[str] = set()

    for row in targets_rows:
        total_targets += 1
        link_key = _norm(row.get("link_key"))
        if not link_key:
            continue
        institution = _norm(row.get("delegated_institution_label"))
        role = _norm(row.get("designated_role_title"))
        boe_id_context = _norm(row.get("boe_id"))

        queries = build_query_variants(role, institution)
        results_with_query: list[tuple[SearchResult, str, str, int]] = []
        seen_boe_ids_for_target: set[str] = set()

        for query_idx, query in enumerate(queries, start=1):
            cache_key = _norm_lc(query)
            cached = query_cache.get(cache_key)
            if cached is None:
                try:
                    html_text, final_url = fetch_boe_search_html(query, timeout=timeout, user_agent=user_agent)
                    parsed = parse_boe_search_results(html_text)
                    query_cache[cache_key] = (parsed, final_url, False)
                except Exception:
                    http_errors += 1
                    query_cache[cache_key] = ([], "", True)
                    continue
            else:
                parsed, final_url, had_error = cached
                if had_error:
                    continue

            parsed, final_url, _ = query_cache[cache_key]
            for result in parsed:
                if result.boe_id in seen_boe_ids_for_target:
                    continue
                seen_boe_ids_for_target.add(result.boe_id)
                results_with_query.append((result, query, final_url, query_idx))
            if len(results_with_query) >= max(1, int(top_results_per_target)):
                break

        if results_with_query:
            targets_with_results += 1

        inst_tokens = _institution_tokens(institution)
        role_tokens = _build_tokens(role)

        for idx, (result, query_used, final_url, query_variant_idx) in enumerate(
            results_with_query[: max(1, int(top_results_per_target))], start=1
        ):
            unique_doc_ids.add(result.boe_id)
            match_institution = _has_match(inst_tokens, f"{result.department} {result.title}")
            match_role = _has_match(role_tokens, result.title)

            candidates.append(
                {
                    "link_key": link_key,
                    "fragment_id": _norm(row.get("fragment_id")),
                    "norm_id": _norm(row.get("norm_id")),
                    "boe_id_context": boe_id_context,
                    "delegated_institution_label": institution,
                    "designated_role_title": role,
                    "query": query_used,
                    "query_variant": query_variant_idx,
                    "search_url": final_url,
                    "candidate_rank": idx,
                    "candidate_boe_id": result.boe_id,
                    "candidate_doc_url": result.doc_url,
                    "candidate_publication_date": result.publication_date,
                    "candidate_department": result.department,
                    "candidate_title": result.title,
                    "candidate_person_hint": _extract_person_hint(result.title),
                    "match_institution": "1" if match_institution else "0",
                    "match_role": "1" if match_role else "0",
                    "candidate_score": _priority_from_match(match_institution, match_role, idx),
                }
            )

    candidates.sort(
        key=lambda item: (
            _norm(item.get("link_key")),
            -int(item.get("candidate_score") or 0),
            int(item.get("candidate_rank") or 0),
        )
    )

    summary = {
        "status": "ok",
        "targets_total": total_targets,
        "targets_with_results_total": targets_with_results,
        "targets_without_results_total": max(0, total_targets - targets_with_results),
        "candidate_rows_total": len(candidates),
        "candidate_unique_boe_ids_total": len(unique_doc_ids),
        "http_errors_total": http_errors,
        "top_results_per_target": int(top_results_per_target),
    }
    return candidates, summary


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "link_key",
        "fragment_id",
        "norm_id",
        "boe_id_context",
        "delegated_institution_label",
        "designated_role_title",
        "query",
        "query_variant",
        "search_url",
        "candidate_rank",
        "candidate_score",
        "candidate_boe_id",
        "candidate_doc_url",
        "candidate_publication_date",
        "candidate_department",
        "candidate_title",
        "candidate_person_hint",
        "match_institution",
        "match_role",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def _read_targets(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return [{str(k or ""): str(v or "") for k, v in row.items()} for row in reader]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--targets-csv",
        default="docs/etl/sprints/AI-OPS-279/exports/liberty_delegated_person_window_scrape_targets_latest.csv",
    )
    ap.add_argument("--top-results-per-target", type=int, default=5)
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    ap.add_argument("--strict-min-candidates", type=int, default=0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary-out", required=True)
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    targets_path = Path(args.targets_csv)
    targets_rows = _read_targets(targets_path)

    candidates, summary = scrape_candidates(
        targets_rows,
        top_results_per_target=int(args.top_results_per_target),
        timeout=int(args.timeout),
        user_agent=_norm(args.user_agent) or DEFAULT_USER_AGENT,
    )

    out_csv = Path(args.out)
    _write_csv(out_csv, candidates)

    payload = {
        "generated_at": now_utc_iso(),
        "targets_csv": str(targets_path),
        "candidates_csv": str(out_csv),
        "summary": summary,
    }
    out_json = Path(args.summary_out)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if int(args.strict_min_candidates) > 0 and int(summary.get("candidate_rows_total", 0)) < int(args.strict_min_candidates):
        return STRICT_FAIL_EXIT
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
