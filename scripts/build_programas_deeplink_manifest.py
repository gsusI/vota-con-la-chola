#!/usr/bin/env python3
"""Build a deeplink-curated programas_partidos manifest from a base CSV."""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


POSITIVE_URL_HINTS = (
    "programa",
    "program",
    "propuestas",
    "medidas",
    "manifiesto",
    "manifesto",
    "elecciones",
    "plan",
)
NEGATIVE_URL_HINTS = (
    "cookie",
    "privacidad",
    "privacy",
    "aviso-legal",
    "contacto",
    "blog",
    "actualidad",
    "noticias",
    "news",
    "afiliate",
    "donacion",
    "donaciones",
    "transparencia",
    "noticias",
    "actualidad",
    "prensa",
    "agenda",
)
PROGRAM_VERBS = (
    "proponemos",
    "proposem",
    "proposarem",
    "proponhemos",
    "impulsaremos",
    "impulsarem",
    "promoveremos",
    "promovemos",
    "promourem",
    "apostamos por",
    "apostem per",
    "apostar per",
    "garantizaremos",
    "garantirem",
    "priorizaremos",
    "prioritzarem",
    "reduciremos",
    "reduirem",
    "mejoraremos",
    "millorarem",
    "millorar",
    "mellorar",
    "crearemos",
    "crearem",
    "crear",
    "canviarem",
    "canviar",
    "lluita contra",
    "lluitar contra",
    "combataremos",
    "combatiremos",
    "combatrem",
    "combatre",
)
POLICY_TERMS = (
    "vivienda",
    "habitatg",
    "etxebizitz",
    "alquiler",
    "lloguer",
    "alokair",
    "empleo",
    "ocupaci",
    "trabaj",
    "lan",
    "paro",
    "salario",
    "salari",
    "sanidad",
    "salud",
    "salut",
    "hospital",
    "dependenc",
    "educacion",
    "educacio",
    "hezkuntz",
    "beca",
    "beka",
    "energia",
    "energetic",
    "enerxia",
    "transporte",
    "movilidad",
    "mobilitat",
    "garrai",
    "justicia",
    "justizia",
    "seguridad",
    "seguretat",
    "corrup",
    "ustelkeri",
    "inmigr",
    "migr",
    "agric",
    "rural",
    "landa",
    "igualdad",
    "igualtat",
    "berdintasun",
    "impuesto",
    "impost",
    "zerga",
    "pensiones",
    "pensio",
    "pentsio",
)
POSITIVE_ANCHOR_HINTS = (
    "programa",
    "manifiesto",
    "propuestas",
    "medidas",
    "elecciones",
    "plan",
)
NEGATIVE_ANCHOR_HINTS = (
    "blog",
    "noticias",
    "actualidad",
    "contacto",
    "cookies",
    "privacidad",
    "transparencia",
    "noticia",
    "actualidad",
    "prensa",
    "agenda",
)
PROGRAM_TEXT_POSITIVE_HINTS = (
    "programa electoral",
    "programa de gobierno",
    "programa de govern",
    "programa de governo",
    "manifesto electoral",
    "manifiesto electoral",
    "nuestras propuestas",
    "propostes",
    "decalogo de compromisos",
)
PROGRAM_TEXT_NOISE_HINTS = (
    "noticias",
    "actualidad",
    "prensa",
    "agenda",
    "suscribete",
    "afiliate",
    "menu",
    "search",
    "buscador",
    "facebook",
    "twitter",
    "instagram",
    "youtube",
    "tiktok",
    "rss",
    "quienes somos",
    "quen somos",
    "qui som",
    "nuestras sedes",
    "sedes",
    "contacto",
    "etiqueta",
    "perfil del contratante",
    "canal etico",
    "office compliance",
    "documentacion economico financiera",
    "tribunal de cuentas",
    "fiscalizacion",
    "contabilidades",
    "informe de transparencia",
)
DEEPLINK_MARKER = "deeplink-auto-ai-ops-245"
PATH_GUESS_CANDIDATES = (
    "programa",
    "programa-electoral",
    "propuestas",
    "manifiesto",
    "programes",
    "elecciones",
    "eleccions",
    "documents",
    "documentos",
)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def strip_html(text: str) -> str:
    if not text:
        return ""
    out = re.sub(r"<script\b.*?</script>", " ", text, flags=re.I | re.S)
    out = re.sub(r"<style\b.*?</style>", " ", out, flags=re.I | re.S)
    out = re.sub(r"<[^>]+>", " ", out)
    return normalize_ws(out).lower()


def is_http_url(url: str) -> bool:
    p = urlparse(str(url or ""))
    return p.scheme in ("http", "https") and bool(p.netloc)


def host_matches(base_url: str, candidate_url: str) -> bool:
    b = (urlparse(base_url).hostname or "").lower()
    c = (urlparse(candidate_url).hostname or "").lower()
    if not b or not c:
        return False
    if b == c:
        return True
    return c.endswith(f".{b}") or b.endswith(f".{c}")


class _HrefCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[tuple[str, str]] = []
        self._in_anchor = False
        self._anchor_href = ""
        self._anchor_text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if str(tag).lower() != "a":
            return
        self._in_anchor = True
        self._anchor_href = ""
        self._anchor_text_parts = []
        for k, v in attrs:
            if str(k).lower() == "href" and v:
                self._anchor_href = str(v)

    def handle_data(self, data: str) -> None:
        if not self._in_anchor:
            return
        self._anchor_text_parts.append(str(data or ""))

    def handle_endtag(self, tag: str) -> None:
        if str(tag).lower() != "a":
            return
        href = normalize_ws(self._anchor_href)
        if href:
            self.hrefs.append((href, normalize_ws(" ".join(self._anchor_text_parts))))
        self._in_anchor = False
        self._anchor_href = ""
        self._anchor_text_parts = []


def extract_candidate_links(base_url: str, html_text: str, *, same_domain_only: bool = True) -> list[str]:
    parser = _HrefCollector()
    parser.feed(str(html_text or ""))
    out: list[str] = []
    seen: set[str] = set()
    for href, _anchor_text in parser.hrefs:
        href_norm = normalize_ws(href)
        if not href_norm:
            continue
        href_low = href_norm.lower()
        if href_low.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        resolved = normalize_ws(urljoin(base_url, href_norm))
        if not is_http_url(resolved):
            continue
        if same_domain_only and not host_matches(base_url, resolved):
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        out.append(resolved)
    return out


def score_anchor_text(anchor_text: str) -> int:
    t = normalize_ws(str(anchor_text or "")).lower()
    if not t:
        return 0
    score = 0
    for tok in POSITIVE_ANCHOR_HINTS:
        if tok in t:
            score += 4
    for tok in NEGATIVE_ANCHOR_HINTS:
        if tok in t:
            score -= 4
    return score


def extract_candidate_links_scored(
    base_url: str,
    html_text: str,
    *,
    same_domain_only: bool = True,
) -> list[dict[str, Any]]:
    parser = _HrefCollector()
    parser.feed(str(html_text or ""))
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for href, anchor_text in parser.hrefs:
        href_norm = normalize_ws(href)
        if not href_norm:
            continue
        href_low = href_norm.lower()
        if href_low.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        resolved = normalize_ws(urljoin(base_url, href_norm))
        if not is_http_url(resolved):
            continue
        if same_domain_only and not host_matches(base_url, resolved):
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        url_score = score_deeplink_url(resolved)
        anchor_score = score_anchor_text(anchor_text)
        out.append(
            {
                "url": resolved,
                "anchor_text": anchor_text,
                "url_score": int(url_score),
                "anchor_score": int(anchor_score),
                "pre_score": int(url_score + anchor_score),
            }
        )
    return out


def build_path_guess_candidates(base_url: str) -> list[dict[str, Any]]:
    p = urlparse(base_url)
    if not p.scheme or not p.netloc:
        return []
    origin = f"{p.scheme}://{p.netloc}/"
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for token in PATH_GUESS_CANDIDATES:
        guessed = normalize_ws(urljoin(origin, token))
        if not is_http_url(guessed):
            continue
        if guessed in seen:
            continue
        seen.add(guessed)
        url_score = score_deeplink_url(guessed)
        out.append(
            {
                "url": guessed,
                "anchor_text": "",
                "url_score": int(url_score),
                "anchor_score": 0,
                "pre_score": int(url_score + 1),
                "candidate_source": "path_guess",
            }
        )
    return out


def score_deeplink_url(url: str) -> int:
    u = str(url or "").lower()
    score = 0
    for tok in POSITIVE_URL_HINTS:
        if tok in u:
            score += 3
    for tok in NEGATIVE_URL_HINTS:
        if tok in u:
            score -= 4
    if u.endswith(".pdf"):
        score += 2
    year_matches = [int(y) for y in re.findall(r"(?:19|20)\d{2}", u)]
    if year_matches:
        newest = max(year_matches)
        if newest >= 2024:
            score += 3
        elif newest >= 2021:
            score += 1
        elif newest <= 2018:
            score -= 3
        else:
            score -= 1
    if re.search(r"/(?:dokumentuak|documentos?|documents?|gardentasuna)(?:/|$)", u):
        score -= 2
    if re.search(r"/(?:noticias?|actualidad|prensa|agenda)(?:/|$)", u):
        score -= 4
    if "/wp-content/" in u or "/uploads/" in u:
        score += 1
    return score


def score_programmatic_text(text: str) -> int:
    t = normalize_ws(str(text or "")).lower()
    if not t:
        return 0
    score = 0
    for tok in PROGRAM_TEXT_POSITIVE_HINTS:
        if tok in t:
            score += 4
    for tok in PROGRAM_VERBS:
        if tok in t:
            score += 2
    for tok in POLICY_TERMS:
        if tok in t:
            score += 1
    for tok in ("politica de cookies", "politica de privacidad", "aviso legal", "cookies"):
        if tok in t:
            score -= 5
    noise_hits = 0
    for tok in PROGRAM_TEXT_NOISE_HINTS:
        if tok in t:
            noise_hits += 1
            score -= 2
    if noise_hits >= 6:
        score -= 8
    if t.count("etiqueta") >= 3:
        score -= 6
    date_hits = len(
        re.findall(
            r"\b\d{1,2}\s+(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic|xan|gen|febrer|marc|abril)\b",
            t,
        )
    )
    if date_hits >= 3:
        score -= 8
    return score


def fetch_url(url: str, *, timeout: int) -> tuple[int, str, bytes]:
    req = Request(
        url=url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; vota-con-la-chola/AI-OPS-245)",
            "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.8",
        },
        method="GET",
    )
    with urlopen(req, timeout=int(timeout)) as resp:
        status = int(getattr(resp, "status", 200))
        content_type = str(resp.headers.get("Content-Type") or "").lower()
        body = resp.read()
        return status, content_type, body


def infer_format_hint(url: str, content_type: str) -> str:
    u = str(url or "").lower()
    ct = str(content_type or "").lower()
    if "application/pdf" in ct or u.endswith(".pdf"):
        return "pdf"
    if "text/html" in ct or not u.endswith((".pdf", ".xml", ".txt", ".md")):
        return "html"
    if u.endswith(".xml"):
        return "xml"
    if u.endswith(".txt"):
        return "txt"
    if u.endswith(".md"):
        return "md"
    return ""


def build_manifest(
    *,
    input_manifest: Path,
    output_manifest: Path,
    report_out: Path | None,
    timeout: int,
    min_score: int,
    max_probe_candidates: int,
) -> dict[str, Any]:
    rows: list[dict[str, str]] = []
    with input_manifest.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        for row in reader:
            rows.append({str(k): normalize_ws(v) for k, v in row.items()})
    if not rows:
        raise RuntimeError("input manifest is empty")
    if not fieldnames:
        raise RuntimeError("input manifest has no header")

    updated = 0
    kept = 0
    skipped = 0
    failures: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []

    probe_cache: dict[str, dict[str, Any]] = {}
    for row in rows:
        kind = normalize_ws(row.get("kind") or "")
        source_url = normalize_ws(row.get("source_url") or "")
        party_id = normalize_ws(row.get("party_id") or "")
        election_cycle = normalize_ws(row.get("election_cycle") or "")

        if kind != "programa" or not source_url or not is_http_url(source_url):
            skipped += 1
            continue

        probe_row: dict[str, Any] = {
            "party_id": party_id,
            "election_cycle": election_cycle,
            "source_url": source_url,
            "selected_url": source_url,
            "selected_score": 0,
            "selected_reason": "kept_original",
            "candidates_evaluated": 0,
            "error": None,
        }
        try:
            if source_url in probe_cache:
                cached = dict(probe_cache[source_url])
                best_url = normalize_ws(str(cached.get("selected_url") or source_url))
                best_score = int(cached.get("selected_score") or 0)
                best_reason = normalize_ws(str(cached.get("selected_reason") or "cache_kept_original"))
                probe_row["selected_url"] = best_url
                probe_row["selected_score"] = best_score
                probe_row["selected_reason"] = f"cache:{best_reason}"
                probe_row["candidates_evaluated"] = int(cached.get("candidates_evaluated") or 0)
                probe_row["error"] = cached.get("error")
                if best_reason in ("candidate_selected", "cache:candidate_selected") and best_url != source_url:
                    row["source_url"] = best_url
                    row["format_hint"] = infer_format_hint(best_url, "")
                    notes = normalize_ws(row.get("notes") or "")
                    row["notes"] = DEEPLINK_MARKER if not notes else f"{notes};{DEEPLINK_MARKER}"
                    updated += 1
                else:
                    kept += 1
                probes.append(probe_row)
                continue

            status, content_type, body = fetch_url(source_url, timeout=timeout)
            if status >= 400:
                raise RuntimeError(f"status={status}")
            if "text/html" not in content_type and not source_url.lower().endswith((".html", "/")):
                kept += 1
                probe_row["selected_reason"] = "non_html_source"
                probes.append(probe_row)
                continue
            html_text = body.decode("utf-8", errors="replace")
            candidates = extract_candidate_links_scored(source_url, html_text, same_domain_only=True)
            guessed_candidates = build_path_guess_candidates(source_url)
            combined_candidates: dict[str, dict[str, Any]] = {}
            for c in candidates + guessed_candidates:
                u = normalize_ws(str(c.get("url") or ""))
                if not u:
                    continue
                current = combined_candidates.get(u)
                if current is None or int(c.get("pre_score") or 0) > int(current.get("pre_score") or 0):
                    combined_candidates[u] = c
            scored = sorted(
                (
                    (
                        int(c["pre_score"]),
                        normalize_ws(str(c["url"])),
                        normalize_ws(str(c["anchor_text"])),
                        int(c["url_score"]),
                        int(c["anchor_score"]),
                        normalize_ws(str(c.get("candidate_source") or "anchor")),
                    )
                    for c in combined_candidates.values()
                ),
                key=lambda it: (-it[0], -it[3], -it[4], it[1]),
            )
            scored = [it for it in scored if it[0] >= 0][: int(max_probe_candidates)]
            best: tuple[int, str, str] = (score_deeplink_url(source_url), source_url, "source_url")
            for pre_score, candidate_url, _anchor_text, _url_score, _anchor_score, _candidate_source in scored:
                probe_row["candidates_evaluated"] = int(probe_row["candidates_evaluated"]) + 1
                try:
                    c_status, c_type, c_body = fetch_url(candidate_url, timeout=timeout)
                    if c_status >= 400:
                        continue
                    if "application/pdf" in c_type or candidate_url.lower().endswith(".pdf"):
                        content_score = 5
                    else:
                        c_text = strip_html(c_body.decode("utf-8", errors="replace"))[:20000]
                        content_score = score_programmatic_text(c_text)
                    total = int(pre_score) + int(content_score)
                    if total > best[0] or (total == best[0] and best[2] == "source_url" and candidate_url != source_url):
                        best = (total, candidate_url, "candidate")
                except Exception:
                    continue

            if best[2] == "candidate" and int(best[0]) >= int(min_score) and best[1] != source_url:
                row["source_url"] = best[1]
                row["format_hint"] = infer_format_hint(best[1], "")
                notes = normalize_ws(row.get("notes") or "")
                row["notes"] = DEEPLINK_MARKER if not notes else f"{notes};{DEEPLINK_MARKER}"
                updated += 1
                probe_row["selected_url"] = best[1]
                probe_row["selected_score"] = int(best[0])
                probe_row["selected_reason"] = "candidate_selected"
            else:
                kept += 1
                probe_row["selected_score"] = int(best[0])
                probe_row["selected_reason"] = "no_candidate_above_threshold"
            probe_cache[source_url] = {
                "selected_url": probe_row["selected_url"],
                "selected_score": int(probe_row["selected_score"]),
                "selected_reason": probe_row["selected_reason"],
                "candidates_evaluated": int(probe_row["candidates_evaluated"]),
                "error": probe_row["error"],
            }
        except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
            kept += 1
            probe_row["error"] = f"{type(exc).__name__}: {exc}"
            failures.append(
                {
                    "party_id": party_id,
                    "election_cycle": election_cycle,
                    "source_url": source_url,
                    "error": probe_row["error"],
                }
            )
            probe_cache[source_url] = {
                "selected_url": source_url,
                "selected_score": 0,
                "selected_reason": "error_keep_original",
                "candidates_evaluated": int(probe_row["candidates_evaluated"]),
                "error": probe_row["error"],
            }
        probes.append(probe_row)

    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    with output_manifest.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})

    report = {
        "generated_at": now_utc_iso(),
        "input_manifest": str(input_manifest),
        "output_manifest": str(output_manifest),
        "rows_total": len(rows),
        "rows_updated": int(updated),
        "rows_kept": int(kept),
        "rows_skipped": int(skipped),
        "failures_total": len(failures),
        "failures": failures[:100],
        "probes": probes,
        "config": {
            "timeout": int(timeout),
            "min_score": int(min_score),
            "max_probe_candidates": int(max_probe_candidates),
        },
    }
    if report_out is not None:
        report_out.parent.mkdir(parents=True, exist_ok=True)
        report_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    p = argparse.ArgumentParser(description="Build deeplink-curated programas manifest")
    p.add_argument("--input-manifest", required=True, help="Base manifest CSV")
    p.add_argument("--output-manifest", required=True, help="Output manifest CSV")
    p.add_argument("--report-out", default="", help="Optional JSON report path")
    p.add_argument("--timeout", type=int, default=20, help="HTTP timeout seconds")
    p.add_argument("--min-score", type=int, default=7, help="Minimum score to replace source_url")
    p.add_argument("--max-probe-candidates", type=int, default=5, help="Max candidate URLs fetched per row")
    args = p.parse_args()

    report = build_manifest(
        input_manifest=Path(args.input_manifest),
        output_manifest=Path(args.output_manifest),
        report_out=Path(args.report_out) if normalize_ws(args.report_out) else None,
        timeout=int(args.timeout),
        min_score=int(args.min_score),
        max_probe_candidates=int(args.max_probe_candidates),
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
