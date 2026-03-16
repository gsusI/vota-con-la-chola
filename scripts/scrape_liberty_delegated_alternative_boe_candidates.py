#!/usr/bin/env python3
"""Scrape BOE candidates from delegated alternative capture targets."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from scripts.scrape_liberty_delegated_person_window_boe_candidates import (
    _build_tokens,
    _extract_person_hint,
    _has_match,
    _institution_tokens,
    _priority_from_match,
    build_query_variants,
    fetch_boe_search_html,
    parse_boe_search_results,
)

STRICT_FAIL_EXIT = 4
DEFAULT_TIMEOUT = 30
DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; vota-con-la-chola-bot/1.0; +https://www.boe.es/)"


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value or "").strip())
    except Exception:
        return int(default)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return [{str(k or ""): str(v or "") for k, v in row.items()} for row in reader]


def _parse_boe_id(value: str) -> str:
    m = re.search(r"(BOE-A-\d+-\d+)", _norm(value), flags=re.IGNORECASE)
    return _norm(m.group(1)).upper() if m else ""


def _extract_html_title(html_text: str) -> str:
    og = re.search(
        r'<meta\s+property=["\']og:title["\']\s+content=["\'](.*?)["\']',
        html_text,
        flags=re.IGNORECASE | re.S,
    )
    if og:
        return _norm(html.unescape(og.group(1)))
    m = re.search(r"<title>(.*?)</title>", html_text, flags=re.IGNORECASE | re.S)
    if not m:
        return ""
    token = re.sub(r"\s+", " ", html.unescape(m.group(1)))
    return _norm(token)


def _iso_to_ddmmyyyy(value: str) -> str:
    token = _norm(value)
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", token)
    if not m:
        return ""
    yyyy, mm, dd = m.groups()
    return f"{dd}/{mm}/{yyyy}"


def _fetch_html(url: str, *, timeout: int, user_agent: str) -> tuple[int, str, str]:
    req = Request(_norm(url), headers={"User-Agent": user_agent})
    try:
        with urlopen(req, timeout=timeout) as response:
            status = int(getattr(response, "status", 200) or 200)
            body = response.read().decode("utf-8", "ignore")
            return status, _norm(response.geturl()), body
    except HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "ignore")
        except Exception:
            body = ""
        return int(getattr(exc, "code", 0) or 0), _norm(url), body
    except (URLError, TimeoutError, OSError):
        return 0, _norm(url), ""


def _query_variants_for_row(row: dict[str, str], max_queries_per_target: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()

    def push(query: str) -> None:
        token = _norm(query)
        key = token.lower()
        if not token or key in seen:
            return
        seen.add(key)
        out.append(token)

    primary_query = _norm(row.get("query"))
    if primary_query:
        push(primary_query)
    role = _norm(row.get("designated_role_title"))
    inst = _norm(row.get("delegated_institution_label"))
    for variant in build_query_variants(role, inst):
        push(variant)
        if len(out) >= max(1, int(max_queries_per_target)):
            break
    return out[: max(1, int(max_queries_per_target))]


def build_alternative_boe_candidates(
    *,
    target_rows: list[dict[str, str]],
    top_results_per_query_target: int,
    max_queries_per_query_target: int,
    timeout: int,
    user_agent: str,
    fetcher: Callable[[str, int, str], tuple[int, str, str]] = _fetch_html,
    query_fetcher: Callable[[str, int, str], tuple[str, str]] = fetch_boe_search_html,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    targets_by_group: dict[str, int] = {}
    fetch_status_counts: dict[str, int] = {}
    fetch_ok_total = 0
    fetch_error_total = 0
    candidates_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    link_keys: set[str] = set()
    links_with_candidates: set[str] = set()
    unique_boe_ids: set[str] = set()
    boe_query_targets_total = 0
    boe_direct_doc_targets_total = 0
    cache_by_url: dict[str, tuple[int, str, str]] = {}
    direct_doc_candidates_total = 0
    query_candidates_total = 0

    for row in target_rows:
        link_key = _norm(row.get("link_key"))
        if not link_key:
            continue
        link_keys.add(link_key)

        target_group = _norm(row.get("target_group"))
        target_url = _norm(row.get("target_url"))
        if not target_url:
            continue
        targets_by_group[target_group] = targets_by_group.get(target_group, 0) + 1

        cached = cache_by_url.get(target_url)
        if cached is None:
            status, final_url, body = fetcher(target_url, timeout=int(timeout), user_agent=user_agent)
            cache_by_url[target_url] = (status, final_url, body)
        else:
            status, final_url, body = cached
        fetch_status_counts[str(status)] = fetch_status_counts.get(str(status), 0) + 1
        if 200 <= int(status) < 300:
            fetch_ok_total += 1
        else:
            fetch_error_total += 1

        institution = _norm(row.get("delegated_institution_label"))
        role = _norm(row.get("designated_role_title"))
        inst_tokens = _institution_tokens(institution)
        role_tokens = _build_tokens(role)

        if target_group == "boe_redirector_query":
            boe_query_targets_total += 1
            parsed_any: list[tuple[Any, str, str]] = []
            query_variants = _query_variants_for_row(row, int(max_queries_per_query_target))
            for query_idx, query_text in enumerate(query_variants, start=1):
                parsed = []
                final_url_for_query = ""
                try:
                    html_text, final_url_for_query = query_fetcher(query_text, int(timeout), user_agent)
                    parsed = parse_boe_search_results(html_text)
                except Exception:
                    parsed = []
                for item in parsed:
                    parsed_any.append((item, query_text, final_url_for_query))
            if not parsed_any and int(status) >= 200 and int(status) < 300:
                parsed = parse_boe_search_results(body)
                for item in parsed:
                    parsed_any.append((item, _norm(row.get("query")), final_url))
            if not parsed_any:
                continue
            rank = 0
            seen_ids_for_query_target: set[str] = set()
            for result, query_used, search_url in parsed_any:
                boe_id = _parse_boe_id(result.boe_id)
                if not boe_id or boe_id in seen_ids_for_query_target:
                    continue
                seen_ids_for_query_target.add(boe_id)
                rank += 1
                if rank > max(1, int(top_results_per_query_target)):
                    break
                unique_boe_ids.add(boe_id)
                match_institution = _has_match(inst_tokens, f"{result.department} {result.title}")
                match_role = _has_match(role_tokens, result.title)
                candidate = {
                    "link_key": link_key,
                    "fragment_id": _norm(row.get("fragment_id")),
                    "norm_id": _norm(row.get("norm_id")),
                    "boe_id_context": _norm(row.get("boe_id_context")),
                    "delegated_institution_label": institution,
                    "designated_role_title": role,
                    "query": query_used,
                    "query_variant": _norm(row.get("target_label")) or "boe_redirector_query",
                    "search_url": search_url or final_url,
                    "candidate_rank": rank,
                    "candidate_score": _priority_from_match(match_institution, match_role, rank),
                    "candidate_boe_id": boe_id,
                    "candidate_doc_url": _norm(result.doc_url),
                    "candidate_publication_date": _norm(result.publication_date),
                    "candidate_department": _norm(result.department),
                    "candidate_title": _norm(result.title),
                    "candidate_person_hint": _extract_person_hint(_norm(result.title)),
                    "match_institution": "1" if match_institution else "0",
                    "match_role": "1" if match_role else "0",
                }
                key = (link_key, boe_id)
                prev = candidates_by_key.get(key)
                if prev is None or _to_int(candidate.get("candidate_score")) > _to_int(prev.get("candidate_score")):
                    candidates_by_key[key] = candidate
            continue

        if target_group == "boe_direct_doc":
            boe_direct_doc_targets_total += 1
            if int(status) < 200 or int(status) >= 300:
                continue
            boe_id = _parse_boe_id(_norm(row.get("candidate_boe_id")) or target_url or final_url)
            if not boe_id:
                continue
            unique_boe_ids.add(boe_id)
            title = _extract_html_title(body)
            if not title:
                title = _norm(row.get("query"))
            match_institution = _has_match(inst_tokens, title)
            match_role = _has_match(role_tokens, title)
            rank = max(1, _to_int(row.get("candidate_rank_for_link"), default=1))
            base_score = _priority_from_match(match_institution, match_role, rank)
            hint_score = _to_int(row.get("candidate_score"), default=0)
            candidate = {
                "link_key": link_key,
                "fragment_id": _norm(row.get("fragment_id")),
                "norm_id": _norm(row.get("norm_id")),
                "boe_id_context": _norm(row.get("boe_id_context")),
                "delegated_institution_label": institution,
                "designated_role_title": role,
                "query": _norm(row.get("query")),
                "query_variant": _norm(row.get("target_label")) or "boe_direct_doc",
                "search_url": final_url,
                "candidate_rank": rank,
                "candidate_score": max(base_score, hint_score),
                "candidate_boe_id": boe_id,
                "candidate_doc_url": final_url or target_url,
                "candidate_publication_date": _iso_to_ddmmyyyy(_norm(row.get("candidate_publication_date_iso"))),
                "candidate_department": "",
                "candidate_title": title,
                "candidate_person_hint": _extract_person_hint(title),
                "match_institution": "1" if match_institution else "0",
                "match_role": "1" if match_role else "0",
            }
            key = (link_key, boe_id)
            prev = candidates_by_key.get(key)
            if prev is None or _to_int(candidate.get("candidate_score")) > _to_int(prev.get("candidate_score")):
                candidates_by_key[key] = candidate
            continue

    by_link: dict[str, list[dict[str, Any]]] = {}
    for row in candidates_by_key.values():
        by_link.setdefault(_norm(row.get("link_key")), []).append(row)

    out_rows: list[dict[str, Any]] = []
    for link_key, rows in by_link.items():
        rows.sort(
            key=lambda item: (
                -_to_int(item.get("candidate_score"), 0),
                _to_int(item.get("candidate_rank"), 999999),
                _norm(item.get("candidate_boe_id")),
            )
        )
        for idx, row in enumerate(rows, start=1):
            row["candidate_rank"] = idx
            out_rows.append(row)
            links_with_candidates.add(link_key)
            if _norm(row.get("query_variant")).startswith("boe_direct_doc"):
                direct_doc_candidates_total += 1
            else:
                query_candidates_total += 1

    out_rows.sort(
        key=lambda item: (
            _norm(item.get("link_key")),
            -_to_int(item.get("candidate_score"), 0),
            _to_int(item.get("candidate_rank"), 999999),
        )
    )

    summary = {
        "status": "ok",
        "targets_total": len([r for r in target_rows if _norm(r.get("link_key")) and _norm(r.get("target_url"))]),
        "targets_by_group": dict(sorted(targets_by_group.items())),
        "fetch_ok_total": fetch_ok_total,
        "fetch_error_total": fetch_error_total,
        "fetch_status_counts": dict(sorted(fetch_status_counts.items(), key=lambda item: item[0])),
        "boe_query_targets_total": boe_query_targets_total,
        "boe_direct_doc_targets_total": boe_direct_doc_targets_total,
        "links_total": len(link_keys),
        "links_with_candidates_total": len(links_with_candidates),
        "links_without_candidates_total": max(0, len(link_keys) - len(links_with_candidates)),
        "candidate_rows_total": len(out_rows),
        "candidate_unique_boe_ids_total": len(unique_boe_ids),
        "query_candidates_total": query_candidates_total,
        "direct_doc_candidates_total": direct_doc_candidates_total,
        "top_results_per_query_target": int(top_results_per_query_target),
        "max_queries_per_query_target": int(max_queries_per_query_target),
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--targets-csv",
        default="docs/etl/sprints/AI-OPS-289/exports/liberty_delegated_alternative_capture_targets_latest.csv",
    )
    ap.add_argument("--top-results-per-query-target", type=int, default=5)
    ap.add_argument("--max-queries-per-query-target", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    ap.add_argument("--strict-min-candidates", type=int, default=0)
    ap.add_argument("--strict-min-links-with-candidates", type=int, default=0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary-out", required=True)
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    targets_path = Path(args.targets_csv)
    target_rows = _read_csv(targets_path)
    candidates, summary = build_alternative_boe_candidates(
        target_rows=target_rows,
        top_results_per_query_target=int(args.top_results_per_query_target),
        max_queries_per_query_target=int(args.max_queries_per_query_target),
        timeout=int(args.timeout),
        user_agent=DEFAULT_USER_AGENT,
    )

    out_csv = Path(args.out)
    _write_csv(out_csv, candidates)

    payload = {
        "targets_csv": str(targets_path),
        "candidates_csv": str(out_csv),
        "summary": summary,
    }
    out_json = Path(args.summary_out)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if int(args.strict_min_candidates) > 0 and _to_int(summary.get("candidate_rows_total")) < int(args.strict_min_candidates):
        return STRICT_FAIL_EXIT
    if int(args.strict_min_links_with_candidates) > 0 and _to_int(summary.get("links_with_candidates_total")) < int(
        args.strict_min_links_with_candidates
    ):
        return STRICT_FAIL_EXIT
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
