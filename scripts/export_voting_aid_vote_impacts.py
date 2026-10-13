#!/usr/bin/env python3
"""Publish the «Ramificaciones» of the voting aid: who a vote affects, how many they are, and what may follow.

The seed (etl/data/seeds/voting_aid_vote_impacts_v1.json) holds three layers with different certainty:

- ``facts``: official figures (INE, Banco de España, Interior, CGPJ, BOE...) with period, source and URL.
  Votes and multi-vote statements point to them by id, so no number is ever written outside this table.
- ``direct_effects`` per vote: what changes for each group (tenants, owners, platforms...), with a locator in
  the official text, like the «Qué se votaba» bullets.
- ``indirect_effects`` per vote: second-order effects that someone expects or fears, each with its evidence
  (``organismo_publico``, ``estudio`` or ``debate`` with its Diario de Sesiones page). If there are any, both
  kinds must be present (``beneficio_esperado`` and ``riesgo_senalado``), so the card never argues one side.

They are shown before answering: no party or group names. ``gaps`` says what is not known.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.export_voting_aid_vote_bullets import PARTY_RE, REVIEW_STATUSES

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SEED = BASE_DIR / "etl/data/seeds/voting_aid_vote_impacts_v1.json"
DATA_DIR = BASE_DIR / "ui/site/public/citizen/data"
DEFAULT_SNAPSHOTS = [DATA_DIR / "voting_aid_generales_v1.json", DATA_DIR / "voting_aid_generales_v2.json"]
DEFAULT_POOL = DATA_DIR / "voting_aid_pool_v1.json"
DEFAULT_OUT = DATA_DIR / "voting_aid_vote_impacts_v1.json"
SEED_SCHEMA_VERSION = "voting_aid_vote_impacts_seed_v1"
SCHEMA_VERSION = "voting_aid_vote_impacts_v1"

MAX_FACTS = 3
MAX_DIRECT = 4
MAX_INDIRECT = 6
MAX_TEXT_CHARS = 260
MAX_GAPS_CHARS = 300
KINDS = ("beneficio_esperado", "riesgo_senalado")
EVIDENCE = {"organismo_publico", "estudio", "debate"}
URL_RE = re.compile(r"^https://")
# A debate argument must point at a plenary Diario de Sesiones, where anyone can read who said it.
DEBATE_URL_RE = re.compile(r"^https://www\.congreso\.es/public_oficiales/L\d+/CONG/DS/PL/DSCD-\d+-PL-\d+\.PDF$")


def known_ids(snapshots: list[dict[str, Any]], pool: dict[str, Any]) -> tuple[set[str], set[str]]:
    """Vote ids and statement ids the voting aid can show (every version, plus the endless pool)."""
    votes = {it["vote_event_id"] for it in pool.get("items") or []}
    statements: set[str] = set()
    for snap in snapshots:
        for st in snap.get("statements") or []:
            statements.add(st["statement_id"])
            votes.update(v["vote_event_id"] for v in st.get("votes") or [] if v.get("vote_event_id"))
    return votes, statements


def _text_errors(where: str, text: Any, limit: int = MAX_TEXT_CHARS) -> list[str]:
    text = str(text or "").strip()
    if not text:
        return [f"{where}: vacío"]
    errors = []
    if len(text) > limit:
        errors.append(f"{where}: {len(text)} caracteres (máx. {limit})")
    if PARTY_RE.search(text):
        errors.append(f"{where}: nombra un partido o grupo")
    return errors


def validate_seed(seed: dict[str, Any], vote_ids: set[str] | None = None, statement_ids: set[str] | None = None) -> list[str]:
    """Return a list of human-readable errors (empty when the seed is publishable)."""
    errors: list[str] = []
    if (seed.get("meta") or {}).get("schema_version") != SEED_SCHEMA_VERSION:
        errors.append(f"meta.schema_version debe ser {SEED_SCHEMA_VERSION}")
    facts = seed.get("facts") or {}
    for fid, f in facts.items():
        errors += _text_errors(f"dato {fid}", f.get("text"))
        for key in ("period", "source"):
            if not str(f.get(key) or "").strip():
                errors.append(f"dato {fid}: falta {key}")
        if not URL_RE.match(str(f.get("url") or "")):
            errors.append(f"dato {fid}: falta url https")

    def check_fact_refs(where: str, refs: Any) -> None:
        refs = refs or []
        if not 1 <= len(refs) <= MAX_FACTS:
            errors.append(f"{where}: {len(refs)} datos (1..{MAX_FACTS})")
        for ref in refs:
            if ref not in facts:
                errors.append(f"{where}: dato desconocido {ref!r}")

    for sid, st in (seed.get("statements") or {}).items():
        if statement_ids is not None and sid not in statement_ids:
            errors.append(f"afirmación {sid}: no es una pregunta de la ayuda al voto")
        check_fact_refs(f"afirmación {sid}", st.get("facts"))

    for vid, v in (seed.get("votes") or {}).items():
        where = vid[-48:]
        if vote_ids is not None and vid not in vote_ids:
            errors.append(f"{where}: no es una votación de la ayuda al voto")
        if (v.get("review") or {}).get("status") not in REVIEW_STATUSES:
            errors.append(f"{where}: review.status debe ser uno de {sorted(REVIEW_STATUSES)}")
        check_fact_refs(where, v.get("facts"))
        direct = v.get("direct_effects") or []
        if len(direct) > MAX_DIRECT:
            errors.append(f"{where}: {len(direct)} efectos directos (máx. {MAX_DIRECT})")
        for i, d in enumerate(direct, 1):
            errors += _text_errors(f"{where} efecto directo {i}", d.get("text"))
            errors += _text_errors(f"{where} efecto directo {i} (colectivo)", d.get("actor"), 90)
            if not str(d.get("locator") or "").strip():
                errors.append(f"{where} efecto directo {i}: falta localizador")
        indirect = v.get("indirect_effects") or []
        if len(indirect) > MAX_INDIRECT:
            errors.append(f"{where}: {len(indirect)} efectos indirectos (máx. {MAX_INDIRECT})")
        for i, e in enumerate(indirect, 1):
            w = f"{where} efecto indirecto {i}"
            errors += _text_errors(w, e.get("text"))
            errors += _text_errors(f"{w} (fuente)", e.get("source"), 160)
            if e.get("kind") not in KINDS:
                errors.append(f"{w}: kind debe ser uno de {list(KINDS)}")
            if e.get("evidence") not in EVIDENCE:
                errors.append(f"{w}: evidence debe ser uno de {sorted(EVIDENCE)}")
            url = str(e.get("url") or "")
            if not URL_RE.match(url):
                errors.append(f"{w}: falta url https")
            elif e.get("evidence") == "debate" and not DEBATE_URL_RE.match(url):
                errors.append(f"{w}: un argumento del debate debe enlazar al Diario de Sesiones del Pleno")
            if not str(e.get("locator") or "").strip():
                errors.append(f"{w}: falta localizador (página)")
        kinds = {e.get("kind") for e in indirect}
        if indirect and not set(KINDS) <= kinds:
            errors.append(f"{where}: efectos indirectos de un solo lado; hacen falta beneficios esperados y riesgos señalados")
        if v.get("gaps") is not None:
            errors += _text_errors(f"{where} gaps", v.get("gaps"), MAX_GAPS_CHARS)
    return errors


def build_payload(seed: dict[str, Any]) -> dict[str, Any]:
    facts = {
        fid: {k: str(f[k]).strip() for k in ("text", "period", "source", "url")}
        for fid, f in sorted((seed.get("facts") or {}).items())
    }
    by_vote: dict[str, Any] = {}
    review = {s: 0 for s in sorted(REVIEW_STATUSES)}
    evidence = {e: 0 for e in sorted(EVIDENCE)}
    for vid, v in sorted((seed.get("votes") or {}).items()):
        review[v["review"]["status"]] += 1
        for e in v.get("indirect_effects") or []:
            evidence[e["evidence"]] += 1
        by_vote[vid] = {
            "facts": list(v["facts"]),
            "direct": [{k: str(d[k]).strip() for k in ("actor", "text", "locator")} for d in v.get("direct_effects") or []],
            # Expected benefits first, then flagged risks, each in seed order.
            "indirect": [
                {k: str(e[k]).strip() for k in ("kind", "text", "evidence", "source", "locator", "url")}
                for kind in KINDS
                for e in v.get("indirect_effects") or []
                if e["kind"] == kind
            ],
            "review": v["review"]["status"],
        }
        if v.get("gaps"):
            by_vote[vid]["gaps"] = str(v["gaps"]).strip()
    return {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "method": (
                "Ramificaciones en tres capas: cifras oficiales de a quién afecta (con periodo y fuente), efectos directos por "
                "colectivo con su localizador en el texto oficial, y efectos indirectos que alguien espera o teme, cada uno con su "
                "evidencia (organismo público, estudio académico o argumento del debate con su página del Diario de Sesiones), "
                "siempre con beneficios esperados y riesgos señalados a la vez. Sin nombres de partidos."
            ),
            "votes": len(by_vote),
            "statements": len(seed.get("statements") or {}),
            "facts": len(facts),
            "indirect_by_evidence": evidence,
            "review": review,
        },
        "facts": facts,
        "by_statement": {sid: {"facts": list(st["facts"])} for sid, st in sorted((seed.get("statements") or {}).items())},
        "by_vote": by_vote,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", default=str(DEFAULT_SEED))
    parser.add_argument("--snapshot", action="append", help="voting-aid snapshot (repeatable; default: v1 and v2)")
    parser.add_argument("--pool", default=str(DEFAULT_POOL))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)

    seed = json.loads(Path(args.seed).read_text(encoding="utf-8"))
    snapshots = [json.loads(Path(p).read_text(encoding="utf-8")) for p in (args.snapshot or DEFAULT_SNAPSHOTS)]
    pool = json.loads(Path(args.pool).read_text(encoding="utf-8"))
    vote_ids, statement_ids = known_ids(snapshots, pool)
    errors = validate_seed(seed, vote_ids, statement_ids)
    if errors:
        for e in errors[:50]:
            print(f"ERROR {e}", file=sys.stderr)
        print(f"FAIL {len(errors)} errores en la semilla", file=sys.stderr)
        return 1
    payload = build_payload(seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    m = payload["meta"]
    shown = out.resolve().relative_to(BASE_DIR) if out.resolve().is_relative_to(BASE_DIR) else out
    print(f"OK impacts -> {shown} (votes={m['votes']} statements={m['statements']} facts={m['facts']} evidence={m['indirect_by_evidence']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
