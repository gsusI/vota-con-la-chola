#!/usr/bin/env python3
"""Validate the real BNG manifesto promise database and public sample."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from ingest_manifesto_promises import (
    BNG_ACTOR_LABEL,
    BNG_BYTES,
    BNG_PAGES,
    BNG_PARTY_ACRONYM,
    BNG_PARTY_NAME,
    BNG_SHA256,
    BNG_SOURCE_URL,
    SCHEMA_VERSION,
    extract_pages,
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json_bytes(path: Path) -> tuple[bytes, dict[str, Any]]:
    data = path.read_bytes()
    payload = json.loads(data)
    if not isinstance(payload, dict):
        raise TypeError(f"{path}: root must be an object")
    return data, payload


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate_item(
    item: dict[str, Any],
    *,
    pages: list[str],
    seen_claims: set[str],
    seen_promises: set[str],
    errors: list[str],
) -> None:
    claim_id = item.get("claim_id")
    promise_id = item.get("promise_id")
    require(
        isinstance(claim_id, str) and claim_id.startswith("claim_"),
        "bad claim_id",
        errors,
    )
    require(
        isinstance(promise_id, str) and promise_id.startswith("promise_"),
        f"{claim_id}: bad promise_id",
        errors,
    )
    require(claim_id not in seen_claims, f"duplicate claim_id {claim_id}", errors)
    require(
        promise_id not in seen_promises, f"duplicate promise_id {promise_id}", errors
    )
    seen_claims.add(str(claim_id))
    seen_promises.add(str(promise_id))

    actor = item.get("actor", {})
    require(actor.get("actor_kind") == "party", f"{claim_id}: actor kind", errors)
    require(actor.get("name") == BNG_PARTY_NAME, f"{claim_id}: actor name", errors)
    require(actor.get("acronym") == BNG_PARTY_ACRONYM, f"{claim_id}: acronym", errors)
    require(
        actor.get("source_label") == BNG_ACTOR_LABEL,
        f"{claim_id}: source label",
        errors,
    )
    require(
        item.get("claim_kind") == "explicit_promise", f"{claim_id}: claim kind", errors
    )
    require(
        item.get("review", {}).get("status") == "rule_confirmed",
        f"{claim_id}: public item is not rule_confirmed",
        errors,
    )
    require(
        item.get("observation_status") == "not_assessed",
        f"{claim_id}: pilot must not invent fulfillment",
        errors,
    )

    evidence = item.get("evidence", {})
    page_start = evidence.get("page_start")
    page_end = evidence.get("page_end")
    char_start = evidence.get("char_start")
    char_end = evidence.get("char_end")
    quote = evidence.get("exact_quote")
    require(
        page_start == page_end, f"{claim_id}: pilot evidence must be one page", errors
    )
    require(
        isinstance(page_start, int) and 1 <= page_start <= BNG_PAGES,
        f"{claim_id}: invalid page",
        errors,
    )
    require(
        evidence.get("source_url") == BNG_SOURCE_URL, f"{claim_id}: source URL", errors
    )
    require(
        evidence.get("document_sha256") == BNG_SHA256, f"{claim_id}: doc hash", errors
    )
    require(
        isinstance(quote, str) and quote.startswith("•"),
        f"{claim_id}: exact quote",
        errors,
    )
    if isinstance(quote, str):
        require(
            evidence.get("quote_sha256") == sha256_bytes(quote.encode("utf-8")),
            f"{claim_id}: quote hash mismatch",
            errors,
        )
    if (
        isinstance(page_start, int)
        and 1 <= page_start <= len(pages)
        and isinstance(char_start, int)
        and isinstance(char_end, int)
        and isinstance(quote, str)
    ):
        canonical_page = "\n".join(
            line.strip() for line in pages[page_start - 1].splitlines()
        )
        require(
            canonical_page[char_start:char_end] == quote,
            f"{claim_id}: quote does not match page offsets",
            errors,
        )
    topics = item.get("topics")
    require(
        isinstance(topics, list) and len(topics) >= 1, f"{claim_id}: no topic", errors
    )
    for topic in topics if isinstance(topics, list) else []:
        require(
            str(topic.get("canonical_key", "")).startswith("promise.v1."),
            f"{claim_id}: invalid topic",
            errors,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--db", type=Path, default=Path("etl/data/staging/promises-bng-2023.db")
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=Path(
            f"etl/data/raw/text_documents/programas_partidos/{BNG_SHA256}.pdf"
        ),
    )
    parser.add_argument(
        "--published",
        type=Path,
        default=Path("etl/data/published/promises-bng-2023.json"),
    )
    parser.add_argument(
        "--public",
        type=Path,
        default=Path("ui/gh-pages-next/public/promises/data/bng-2023.json"),
    )
    parser.add_argument(
        "--report-out",
        type=Path,
        default=Path(
            "docs/etl/sprints/PROMISES-20260819/evidence/"
            "promises-bng-2023-validation.json"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors: list[str] = []
    pdf_bytes = args.pdf.read_bytes()
    require(len(pdf_bytes) == BNG_BYTES, "official PDF byte count mismatch", errors)
    require(
        sha256_bytes(pdf_bytes) == BNG_SHA256, "official PDF SHA-256 mismatch", errors
    )
    pages = extract_pages(args.pdf)
    require(len(pages) == BNG_PAGES, "official PDF page count mismatch", errors)

    published_bytes, payload = load_json_bytes(args.published)
    public_bytes, public_payload = load_json_bytes(args.public)
    require(
        published_bytes == public_bytes, "published/public artifacts differ", errors
    )
    require(payload == public_payload, "published/public payloads differ", errors)
    require(
        payload.get("schema_version") == SCHEMA_VERSION,
        "schema version mismatch",
        errors,
    )
    require(
        payload.get("real_data_only") is True, "real_data_only must be true", errors
    )
    require(
        payload.get("synthetic_or_mock") is False,
        "synthetic_or_mock must be false",
        errors,
    )
    require(
        payload.get("public_domain_information_policy") == "retained_exactly",
        "public-domain information policy mismatch",
        errors,
    )
    source = payload.get("source", {})
    require(source.get("content_sha256") == BNG_SHA256, "payload source hash", errors)
    require(source.get("bytes") == BNG_BYTES, "payload source bytes", errors)
    require(source.get("page_count") == BNG_PAGES, "payload source pages", errors)
    require(source.get("source_url") == BNG_SOURCE_URL, "payload source URL", errors)

    items = payload.get("items")
    require(isinstance(items, list), "items must be an array", errors)
    require(
        len(items) == 20 if isinstance(items, list) else False,
        "expected 20 public items",
        errors,
    )
    seen_claims: set[str] = set()
    seen_promises: set[str] = set()
    for item in items if isinstance(items, list) else []:
        validate_item(
            item,
            pages=pages,
            seen_claims=seen_claims,
            seen_promises=seen_promises,
            errors=errors,
        )

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = conn.execute("PRAGMA foreign_key_check").fetchall()
        table_counts = {
            table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in (
                "manifesto_documents",
                "claim_extraction_runs",
                "claims",
                "claim_evidence",
                "promises",
                "claim_topics",
            )
        }
        public_rows = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM claims c
                JOIN promises p ON p.claim_id=c.claim_id
                WHERE c.claim_id IN ({})
                  AND c.review_status='rule_confirmed'
                  AND c.party_id IS NOT NULL
                """.format(",".join("?" for _ in seen_claims)),
                tuple(sorted(seen_claims)),
            ).fetchone()[0]
        )
        raw_policy_rows = conn.execute(
            "SELECT raw_payload FROM source_records WHERE source_id=?",
            ("programas_partidos",),
        ).fetchall()
    finally:
        conn.close()

    require(integrity == "ok", f"SQLite integrity_check: {integrity}", errors)
    require(not foreign_keys, f"foreign key errors: {foreign_keys[:5]}", errors)
    require(
        table_counts["manifesto_documents"] == 1, "manifesto document count", errors
    )
    require(table_counts["claims"] == 266, "claim count", errors)
    require(table_counts["claim_evidence"] == 266, "claim evidence count", errors)
    require(table_counts["promises"] == 91, "promise count", errors)
    require(table_counts["claim_topics"] == 323, "claim topic count", errors)
    require(
        public_rows == len(seen_claims) == 20, "public rows not confirmed in DB", errors
    )
    for (raw_payload,) in raw_policy_rows:
        raw = json.loads(raw_payload)
        require(
            raw.get("synthetic_or_mock") is False, "source record not real-only", errors
        )

    counts = payload.get("counts", {})
    require(counts.get("segments_seen") == 266, "segments_seen mismatch", errors)
    require(counts.get("claims_loaded") == 266, "claims_loaded mismatch", errors)
    require(counts.get("promises_loaded") == 91, "promises_loaded mismatch", errors)
    require(counts.get("topic_links") == 323, "topic_links mismatch", errors)
    require(counts.get("published_promises") == 20, "published count mismatch", errors)

    report = {
        "schema_version": "manifesto_promises_validation_report_v1",
        "status": "ok" if not errors else "error",
        "validated_at": payload.get("generated_at"),
        "release_id": payload.get("release_id"),
        "artifact_sha256": sha256_bytes(published_bytes),
        "official_pdf": {
            "bytes": len(pdf_bytes),
            "content_sha256": sha256_bytes(pdf_bytes),
            "page_count": len(pages),
            "source_url": BNG_SOURCE_URL,
        },
        "table_counts": table_counts,
        "public_claims_validated": public_rows,
        "foreign_key_errors": len(foreign_keys),
        "integrity_check": integrity,
        "published_public_byte_parity": published_bytes == public_bytes,
        "quote_page_offset_matches": len(seen_claims) if not errors else None,
        "real_data_only": True,
        "synthetic_or_mock": False,
        "official_public_domain_information_retained": True,
        "errors": errors,
    }
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
