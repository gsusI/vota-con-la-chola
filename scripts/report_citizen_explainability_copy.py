#!/usr/bin/env python3
"""Machine-readable explainability copy contract for /citizen."""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_UI_HTML = Path("ui/citizen/index.html")
DEFAULT_MIN_GLOSSARY_TERMS = 4
DEFAULT_MAX_DEFINITION_WORDS = 12
DEFAULT_MAX_COPY_SENTENCE_WORDS = 16
DEFAULT_FORBIDDEN_JARGON = "embedding,ontologia,bayesiano,vectorizacion,heuristica"

_TERM_BLOCK_RE = re.compile(
    r"<(?P<tag>[a-z0-9]+)\b(?P<attrs>[^>]*\bdata-explainability-term=(?P<q>['\"])(?P<term>[^'\"]+)(?P=q)[^>]*)>(?P<body>.*?)</(?P=tag)\s*>",
    flags=re.IGNORECASE | re.DOTALL,
)
_COPY_BLOCK_RE = re.compile(
    r"<(?P<tag>[a-z0-9]+)\b(?P<attrs>[^>]*\bdata-explainability-copy=(?P<q>['\"])1(?P=q)[^>]*)>(?P<body>.*?)</(?P=tag)\s*>",
    flags=re.IGNORECASE | re.DOTALL,
)
_MARKER_RE = re.compile(r"data-explainability-glossary=(['\"])1\1", flags=re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_SPLIT_SENTENCE_RE = re.compile(r"[.!?;:]+")
_WORD_RE = re.compile(r"[0-9a-zA-ZÀ-ÿ_]+")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Citizen explainability copy report")
    ap.add_argument("--ui-html", default=str(DEFAULT_UI_HTML))
    ap.add_argument("--min-glossary-terms", type=int, default=DEFAULT_MIN_GLOSSARY_TERMS)
    ap.add_argument("--max-definition-words", type=int, default=DEFAULT_MAX_DEFINITION_WORDS)
    ap.add_argument("--max-copy-sentence-words", type=int, default=DEFAULT_MAX_COPY_SENTENCE_WORDS)
    ap.add_argument(
        "--forbidden-jargon",
        default=DEFAULT_FORBIDDEN_JARGON,
        help="Comma-separated lowercased tokens that should not appear in explainability copy.",
    )
    ap.add_argument("--strict", action="store_true", help="Fail (exit 4) when status is failed")
    ap.add_argument(
        "--strict-require-complete",
        action="store_true",
        help="With --strict, also fail when status is degraded.",
    )
    ap.add_argument("--out", default="", help="Optional JSON output path")
    return ap.parse_args(argv)


def _safe_text(v: Any) -> str:
    return str(v or "").strip()


def _strip_html(raw: str) -> str:
    plain = _TAG_RE.sub(" ", str(raw or ""))
    plain = html_lib.unescape(plain)
    return " ".join(plain.replace("\xa0", " ").split())


def _word_count(raw: str) -> int:
    return len(_WORD_RE.findall(str(raw or "")))


def _attr_value(attrs: str, key: str) -> str:
    pat = re.compile(rf"\b{re.escape(key)}\s*=\s*(['\"])(.*?)\1", flags=re.IGNORECASE | re.DOTALL)
    m = pat.search(str(attrs or ""))
    if not m:
        return ""
    return _safe_text(html_lib.unescape(m.group(2)))


def _parse_forbidden_jargon(raw: str) -> list[str]:
    out: list[str] = []
    for token in str(raw or "").split(","):
        t = _safe_text(token).lower()
        if t:
            out.append(t)
    seen: set[str] = set()
    deduped: list[str] = []
    for t in out:
        if t in seen:
            continue
        seen.add(t)
        deduped.append(t)
    return deduped


def _split_sentences(text: str) -> list[str]:
    out: list[str] = []
    for part in _SPLIT_SENTENCE_RE.split(str(text or "")):
        s = _safe_text(part)
        if s:
            out.append(s)
    return out


def build_report(
    *,
    ui_html_path: Path,
    min_glossary_terms: int,
    max_definition_words: int,
    max_copy_sentence_words: int,
    forbidden_jargon: list[str],
) -> dict[str, Any]:
    html_text = ui_html_path.read_text(encoding="utf-8")
    glossary_marker_present = bool(_MARKER_RE.search(html_text))

    terms: list[dict[str, Any]] = []
    long_definition_terms: list[dict[str, Any]] = []
    jargon_hits: list[dict[str, str]] = []

    terms_total = 0
    terms_with_tooltip = 0
    terms_with_definition = 0
    max_definition_words_seen = 0

    for m in _TERM_BLOCK_RE.finditer(html_text):
        attrs = _safe_text(m.group("attrs"))
        term = _safe_text(m.group("term")).lower()
        label = _strip_html(m.group("body"))
        tooltip_flag = _safe_text(_attr_value(attrs, "data-explainability-tooltip")) == "1"
        title_copy = _attr_value(attrs, "title")
        definition = _attr_value(attrs, "data-term-definition") or title_copy
        def_words = _word_count(definition)

        terms_total += 1
        if tooltip_flag and title_copy:
            terms_with_tooltip += 1
        if definition:
            terms_with_definition += 1
        if def_words > max_definition_words_seen:
            max_definition_words_seen = def_words
        if definition and def_words > int(max_definition_words):
            long_definition_terms.append(
                {
                    "term": term or label.lower(),
                    "definition_words": int(def_words),
                }
            )
        low_copy = f"{term} {label} {definition}".lower()
        for token in forbidden_jargon:
            if token and token in low_copy:
                jargon_hits.append({"scope": f"term:{term or label}", "token": token})

        terms.append(
            {
                "term": term,
                "label": label or term,
                "has_tooltip": bool(tooltip_flag and title_copy),
                "has_definition": bool(definition),
                "definition_words": int(def_words),
            }
        )

    copy_blocks: list[str] = []
    for m in _COPY_BLOCK_RE.finditer(html_text):
        txt = _strip_html(m.group("body"))
        if txt:
            copy_blocks.append(txt)

    copy_sentences: list[str] = []
    for block in copy_blocks:
        copy_sentences.extend(_split_sentences(block))

    long_copy_sentences: list[dict[str, Any]] = []
    max_copy_sentence_words_seen = 0
    for sentence in copy_sentences:
        wc = _word_count(sentence)
        max_copy_sentence_words_seen = max(max_copy_sentence_words_seen, wc)
        if wc > int(max_copy_sentence_words):
            long_copy_sentences.append(
                {
                    "sentence": sentence,
                    "words": int(wc),
                }
            )
        low_sentence = sentence.lower()
        for token in forbidden_jargon:
            if token and token in low_sentence:
                jargon_hits.append({"scope": "copy_sentence", "token": token})

    checks = {
        "glossary_marker_present": bool(glossary_marker_present),
        "glossary_terms_meet_minimum": bool(terms_total >= int(min_glossary_terms)),
        "tooltip_present_for_all_terms": bool(terms_total > 0 and terms_with_tooltip == terms_total),
        "definitions_present_for_all_terms": bool(terms_total > 0 and terms_with_definition == terms_total),
        "definition_words_within_limit": bool(not long_definition_terms),
        "help_copy_present": bool(copy_blocks),
        "help_copy_sentence_words_within_limit": bool(not long_copy_sentences),
        "jargon_free_copy": bool(not jargon_hits),
    }

    degraded_reasons: list[str] = []
    failure_reasons: list[str] = []

    if not checks["help_copy_present"]:
        degraded_reasons.append("help_copy_missing")
    if terms_total > 0 and terms_with_tooltip < terms_total:
        degraded_reasons.append("tooltip_partial")
    if terms_total > 0 and terms_with_definition < terms_total:
        degraded_reasons.append("definition_partial")

    if not checks["glossary_marker_present"]:
        failure_reasons.append("glossary_marker_missing")
    if not checks["glossary_terms_meet_minimum"]:
        failure_reasons.append("glossary_terms_below_minimum")
    if not checks["definition_words_within_limit"]:
        failure_reasons.append("definition_words_over_limit")
    if not checks["help_copy_sentence_words_within_limit"]:
        failure_reasons.append("help_copy_sentence_words_over_limit")
    if not checks["jargon_free_copy"]:
        failure_reasons.append("forbidden_jargon_detected")

    status = "ok"
    if failure_reasons:
        status = "failed"
    elif degraded_reasons:
        status = "degraded"

    checks["contract_complete"] = bool(
        status == "ok"
        and checks["glossary_marker_present"]
        and checks["glossary_terms_meet_minimum"]
        and checks["tooltip_present_for_all_terms"]
        and checks["definitions_present_for_all_terms"]
        and checks["definition_words_within_limit"]
        and checks["help_copy_present"]
        and checks["help_copy_sentence_words_within_limit"]
        and checks["jargon_free_copy"]
    )

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "paths": {
            "ui_html": str(ui_html_path),
        },
        "metrics": {
            "glossary_terms_total": int(terms_total),
            "glossary_terms_with_tooltip": int(terms_with_tooltip),
            "glossary_terms_with_definition": int(terms_with_definition),
            "help_copy_blocks_total": len(copy_blocks),
            "help_copy_sentences_total": len(copy_sentences),
            "max_definition_words_seen": int(max_definition_words_seen),
            "max_help_copy_sentence_words_seen": int(max_copy_sentence_words_seen),
            "long_definition_terms_total": len(long_definition_terms),
            "long_help_copy_sentences_total": len(long_copy_sentences),
            "jargon_hits_total": len(jargon_hits),
        },
        "thresholds": {
            "min_glossary_terms": int(min_glossary_terms),
            "max_definition_words": int(max_definition_words),
            "max_copy_sentence_words": int(max_copy_sentence_words),
            "forbidden_jargon": forbidden_jargon,
        },
        "checks": checks,
        "degraded_reasons": sorted(set(degraded_reasons)),
        "failure_reasons": sorted(set(failure_reasons)),
        "terms": terms,
        "long_definition_terms": long_definition_terms,
        "long_help_copy_sentences": long_copy_sentences,
        "jargon_hits": jargon_hits,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ui_html_path = Path(_safe_text(args.ui_html))
    if not ui_html_path.exists():
        print(json.dumps({"error": f"ui-html not found: {ui_html_path}"}, ensure_ascii=False))
        return 2

    forbidden_jargon = _parse_forbidden_jargon(args.forbidden_jargon)

    try:
        report = build_report(
            ui_html_path=ui_html_path,
            min_glossary_terms=int(args.min_glossary_terms),
            max_definition_words=int(args.max_definition_words),
            max_copy_sentence_words=int(args.max_copy_sentence_words),
            forbidden_jargon=forbidden_jargon,
        )
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 3

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    out_path = Path(_safe_text(args.out)) if _safe_text(args.out) else None
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")

    status = _safe_text(report.get("status"))
    if bool(args.strict):
        if status == "failed":
            return 4
        if bool(args.strict_require_complete) and status != "ok":
            return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
