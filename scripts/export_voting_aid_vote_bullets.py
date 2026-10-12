#!/usr/bin/env python3
"""Publish the «Qué se votaba» bullets of the voting aid, after validating the reviewed seed.

The seed (etl/data/seeds/voting_aid_vote_bullets_v1.json) holds, per vote_event_id, up to six plain-language
bullets written from the official text, each with a locator (article, point, section) plus the document's
URL and SHA-256. ``review.status`` says how far they were checked: ``draft`` (as written),
``agent_reviewed`` (a second AI pass checked every bullet against the official text; no human yet) or
``reviewed`` (checked by a person). Votes without an official text are
kept explicitly as ``sin_texto_oficial`` with no bullets: nothing is invented.

Validation is strict: max six bullets, locator on every bullet, URL + SHA-256 on every grounded vote, no
party or group names (bullets are shown before answering, so they must not reveal the proposer), and every
vote must belong to a question of the voting aid.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SEED = BASE_DIR / "etl/data/seeds/voting_aid_vote_bullets_v1.json"
DEFAULT_SNAPSHOT = BASE_DIR / "ui/site/public/citizen/data/voting_aid_generales_v1.json"
DEFAULT_POOL = BASE_DIR / "ui/site/public/citizen/data/voting_aid_pool_v1.json"
DEFAULT_HIGHLIGHTS = BASE_DIR / "ui/site/public/citizen/data/voting_aid_highlights_v1.json"
DEFAULT_OUT = BASE_DIR / "ui/site/public/citizen/data/voting_aid_vote_bullets_v1.json"
SEED_SCHEMA_VERSION = "voting_aid_vote_bullets_seed_v1"
SCHEMA_VERSION = "voting_aid_vote_bullets_v1"

MAX_BULLETS = 6
MAX_BULLET_CHARS = 240
STATUSES = {"ok", "sin_texto_oficial"}
REVIEW_STATUSES = {"draft", "agent_reviewed", "reviewed"}
URL_RE = re.compile(r"^https://www\.(boe|congreso)\.es/")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
# Bullets are shown before answering: they must not name who proposed or how anyone voted.
PARTY_RE = re.compile(
    r"\b(PSOE|PP|Vox|VOX|Sumar|SUMAR|Podemos|ERC|Junts|Bildu|EH Bildu|PNV|EAJ|BNG|Coalición Canaria|UPN|"
    r"Grupo Parlamentario|Grupos Parlamentarios|Partido Popular|Partido Socialista)\b"
)


def question_vote_ids(snapshot: dict[str, Any], pool: dict[str, Any]) -> set[str]:
    ids = {it["vote_event_id"] for it in pool.get("items") or []}
    for st in snapshot.get("statements") or []:
        ids.update(v["vote_event_id"] for v in st.get("votes") or [])
    return ids


def validate_seed(seed: dict[str, Any], vote_ids: set[str] | None = None, highlights: dict[str, Any] | None = None) -> list[str]:
    """Return a list of human-readable errors (empty when the seed is publishable)."""
    errors: list[str] = []
    if (seed.get("meta") or {}).get("schema_version") != SEED_SCHEMA_VERSION:
        errors.append(f"meta.schema_version debe ser {SEED_SCHEMA_VERSION}")
    hl_by_url = {d["url"]: d for d in ((highlights or {}).get("docs") or {}).values()}
    for vid, v in (seed.get("votes") or {}).items():
        where = f"{vid[-48:]}"
        if vote_ids is not None and vid not in vote_ids:
            errors.append(f"{where}: no es una votación de la ayuda al voto")
        status = v.get("status")
        if status not in STATUSES:
            errors.append(f"{where}: status inválido {status!r}")
        if (v.get("review") or {}).get("status") not in REVIEW_STATUSES:
            errors.append(f"{where}: review.status debe ser uno de {sorted(REVIEW_STATUSES)}")
        bullets = v.get("bullets") or []
        if status == "sin_texto_oficial":
            if bullets:
                errors.append(f"{where}: sin texto oficial pero con viñetas")
            continue
        if not 1 <= len(bullets) <= MAX_BULLETS:
            errors.append(f"{where}: {len(bullets)} viñetas (1..{MAX_BULLETS})")
        src = v.get("source") or {}
        if not URL_RE.match(str(src.get("url") or "")):
            errors.append(f"{where}: falta url oficial")
        if not SHA_RE.match(str(src.get("sha256") or "")):
            errors.append(f"{where}: falta sha256")
        doc = hl_by_url.get(src.get("url"))
        if doc and doc.get("sha256") != src.get("sha256"):
            errors.append(f"{where}: sha256 distinto del documento publicado en highlights")
        for i, b in enumerate(bullets, 1):
            text, loc = str(b.get("text") or "").strip(), str(b.get("locator") or "").strip()
            if not text:
                errors.append(f"{where} viñeta {i}: vacía")
            if len(text) > MAX_BULLET_CHARS:
                errors.append(f"{where} viñeta {i}: {len(text)} caracteres (máx. {MAX_BULLET_CHARS})")
            if not loc:
                errors.append(f"{where} viñeta {i}: falta localizador")
            if PARTY_RE.search(text):
                errors.append(f"{where} viñeta {i}: nombra un partido o grupo")
    return errors


def build_payload(seed: dict[str, Any], highlights: dict[str, Any] | None = None) -> dict[str, Any]:
    hl_by_url = {d["url"]: d for d in ((highlights or {}).get("docs") or {}).values()}
    by_vote: dict[str, Any] = {}
    counts = {"ok": 0, "sin_texto_oficial": 0, **{s: 0 for s in sorted(REVIEW_STATUSES)}}
    for vid, v in sorted((seed.get("votes") or {}).items()):
        counts[v["status"]] += 1
        counts[v["review"]["status"]] += 1
        if v["status"] == "sin_texto_oficial":
            by_vote[vid] = {"status": "sin_texto_oficial", "review": v["review"]["status"]}
            continue
        src = v["source"]
        doc = hl_by_url.get(src["url"]) or {}
        by_vote[vid] = {
            "status": "ok",
            "bullets": [{"text": b["text"].strip(), "locator": b["locator"].strip()} for b in v["bullets"]],
            "url": src["url"],
            "sha256": src["sha256"],
            "source": src.get("source") or doc.get("source") or ("BOE" if "boe.es" in src["url"] else "BOCG"),
            "text_status_label": src.get("text_status_label") or doc.get("text_status_label") or "",
            "review": v["review"]["status"],
        }
    return {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "method": (
                "Hasta 6 viñetas en lenguaje llano por votación, redactadas a partir del texto oficial (parte dispositiva), "
                "cada una con su localizador (artículo, punto o apartado) y la url y el sha256 del documento. "
                "Neutrales: no nombran al proponente ni dicen el resultado. Sin texto oficial no hay viñetas."
            ),
            "votes": len(by_vote),
            "with_bullets": counts["ok"],
            "without_official_text": counts["sin_texto_oficial"],
            "review": {s: counts[s] for s in sorted(REVIEW_STATUSES)},
        },
        "by_vote": by_vote,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", default=str(DEFAULT_SEED))
    parser.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    parser.add_argument("--pool", default=str(DEFAULT_POOL))
    parser.add_argument("--highlights", default=str(DEFAULT_HIGHLIGHTS))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)

    seed = json.loads(Path(args.seed).read_text(encoding="utf-8"))
    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    pool = json.loads(Path(args.pool).read_text(encoding="utf-8"))
    highlights = json.loads(Path(args.highlights).read_text(encoding="utf-8")) if Path(args.highlights).exists() else None
    vote_ids = question_vote_ids(snapshot, pool)
    errors = validate_seed(seed, vote_ids, highlights)
    if errors:
        for e in errors[:50]:
            print(f"ERROR {e}", file=sys.stderr)
        print(f"FAIL {len(errors)} errores en la semilla", file=sys.stderr)
        return 1
    payload = build_payload(seed, highlights)
    missing = sorted(vote_ids - set(payload["by_vote"]))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    m = payload["meta"]
    shown = out.resolve().relative_to(BASE_DIR) if out.resolve().is_relative_to(BASE_DIR) else out
    print(f"OK bullets -> {shown} (votes={m['votes']} with_bullets={m['with_bullets']} "
          f"sin_texto={m['without_official_text']} not_in_seed={len(missing)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
