#!/usr/bin/env python3
"""Export the general-election voting aid snapshot (statements x parties) from Congreso votes.

Each statement in the seed is backed by one or more roll-call votes and the vote choice that
means "agree" (`agree_vote`). A party's position on a vote is the majority of its deputies'
Sí/No/Abstención choices; its position on a statement is derived from those votes only.
Missing votes or deputies yield `no_data`, never an imputed position.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SEED = BASE_DIR / "etl/data/seeds/voting_aid_generales_v1.json"
DEFAULT_CONCERNS = BASE_DIR / "ui/citizen/concerns_v1.json"
SNAPSHOT_SCHEMA_VERSION = "voting_aid_snapshot_v1"
SEED_SCHEMA_VERSION = "voting_aid_statements_v1"

CHOICES = {"Sí": "yes", "No": "no", "Abstención": "abstain"}
OPPOSITE = {"Sí": "No", "No": "Sí"}


def validate_seed(seed: dict[str, Any], *, concern_ids: set[str]) -> list[str]:
    errors: list[str] = []
    if seed.get("schema_version") != SEED_SCHEMA_VERSION:
        errors.append(f"schema_version debe ser {SEED_SCHEMA_VERSION}")
    party_ids: set[str] = set()
    group_owner: dict[str, str] = {}
    member_owner: dict[str, str] = {}
    for party in seed.get("parties") or []:
        pid = str(party.get("party_id") or "")
        if not pid or pid in party_ids:
            errors.append(f"party_id vacío o duplicado: {pid!r}")
        party_ids.add(pid)
        if not party.get("group_codes") and not party.get("members"):
            errors.append(f"{pid}: necesita group_codes o members")
        for code in party.get("group_codes") or []:
            if code in group_owner:
                errors.append(f"group_code {code!r} asignado a {group_owner[code]} y {pid}")
            group_owner[code] = pid
        for name in party.get("members") or []:
            if name in member_owner:
                errors.append(f"miembro {name!r} asignado a {member_owner[name]} y {pid}")
            member_owner[name] = pid
    statement_ids: set[str] = set()
    for st in seed.get("statements") or []:
        sid = str(st.get("statement_id") or "")
        if not sid or sid in statement_ids:
            errors.append(f"statement_id vacío o duplicado: {sid!r}")
        statement_ids.add(sid)
        if not str(st.get("text") or "").strip():
            errors.append(f"{sid}: falta text")
        concern = st.get("concern_id")
        if concern is not None and concern not in concern_ids:
            errors.append(f"{sid}: concern_id desconocido {concern!r}")
        votes = st.get("votes") or []
        if not votes:
            errors.append(f"{sid}: necesita al menos una votación")
        for vote in votes:
            if vote.get("agree_vote") not in OPPOSITE:
                errors.append(f"{sid}: agree_vote debe ser 'Sí' o 'No'")
            if not str(vote.get("vote_event_id") or "").strip():
                errors.append(f"{sid}: falta vote_event_id")
    if not statement_ids:
        errors.append("el seed no tiene afirmaciones")
    return errors


def party_resolver(seed: dict[str, Any]):
    by_member = {name: p["party_id"] for p in seed["parties"] for name in p.get("members") or []}
    by_group = {code: p["party_id"] for p in seed["parties"] for code in p.get("group_codes") or []}

    def resolve(member_name: str, group_code: str) -> str | None:
        # Member overrides win: deputies who changed group still vote for the party that runs.
        return by_member.get(member_name) or by_group.get(group_code)

    return resolve


def majority_choice(counts: Counter) -> str | None:
    """Majority among Sí/No/Abstención; ties or no votes give None (no clear position)."""
    ranked = [(counts.get(choice, 0), choice) for choice in CHOICES]
    ranked.sort(reverse=True)
    top_n, top_choice = ranked[0]
    if top_n == 0 or ranked[1][0] == top_n:
        return None
    return top_choice


def vote_position(choice: str | None, agree_vote: str) -> str:
    if choice is None:
        return "no_data"
    if choice == "Abstención":
        return "abstain"
    return "agree" if choice == agree_vote else "disagree"


def combine_positions(positions: list[str]) -> str:
    known = [p for p in positions if p != "no_data"]
    if not known:
        return "no_data"
    return known[0] if len(set(known)) == 1 else "mixed"


def direction_balance(statements: list[dict[str, Any]], reference: list[str]) -> dict[str, Any] | None:
    """Count statements where "agree" sides with one reference party and not the other.

    A lopsided count means answering "agree" to everything favours one bloc (acquiescence bias).
    """
    if len(reference) != 2:
        return None
    a, b = reference
    counts = {a: 0, b: 0}
    for st in statements:
        pa = st["cells"].get(a, {}).get("position")
        pb = st["cells"].get(b, {}).get("position")
        if pa == "agree" and pb != "agree":
            counts[a] += 1
        elif pb == "agree" and pa != "agree":
            counts[b] += 1
    return {"reference_parties": [a, b], "agree_sides_only_with": counts}


def explorer_member_votes_link(vote_event_id: str) -> str:
    return f"../explorer/?t=parl_vote_member_votes&wc=vote_event_id&wv={quote(vote_event_id, safe='')}"


def build_snapshot(conn: sqlite3.Connection, seed: dict[str, Any], *, generated_at: str) -> dict[str, Any]:
    conn.row_factory = sqlite3.Row
    resolve = party_resolver(seed)
    party_ids = [p["party_id"] for p in seed["parties"]]
    vote_ids = sorted({v["vote_event_id"] for st in seed["statements"] for v in st["votes"]})

    placeholders = ",".join("?" * len(vote_ids))
    events = {
        row["vote_event_id"]: row
        for row in conn.execute(
            f"""
            SELECT vote_event_id, vote_date, expediente_text, subgroup_title, subgroup_text, source_url,
                   totals_yes, totals_no, totals_abstain
            FROM parl_vote_events
            WHERE vote_event_id IN ({placeholders})
            """,
            vote_ids,
        )
    }
    tallies: dict[str, dict[str, Counter]] = {vid: {pid: Counter() for pid in party_ids} for vid in vote_ids}
    unmapped: Counter = Counter()
    for row in conn.execute(
        f"""
        SELECT vote_event_id, member_name, group_code, vote_choice
        FROM parl_vote_member_votes
        WHERE vote_event_id IN ({placeholders})
        """,
        vote_ids,
    ):
        pid = resolve(str(row["member_name"] or ""), str(row["group_code"] or ""))
        if pid is None:
            unmapped[str(row["member_name"] or "")] += 1
            continue
        tallies[row["vote_event_id"]][pid][str(row["vote_choice"] or "")] += 1

    missing_events = [vid for vid in vote_ids if vid not in events]
    statements_out: list[dict[str, Any]] = []
    cell_counts: Counter = Counter()
    for st in seed["statements"]:
        votes_out: list[dict[str, Any]] = []
        per_party_positions: dict[str, list[str]] = {pid: [] for pid in party_ids}
        for vote in st["votes"]:
            vid = vote["vote_event_id"]
            ev = events.get(vid)
            party_votes: dict[str, Any] = {}
            for pid in party_ids:
                counts = tallies[vid][pid]
                choice = majority_choice(counts)
                position = vote_position(choice, vote["agree_vote"])
                per_party_positions[pid].append(position)
                party_votes[pid] = {
                    "choice": choice,
                    "position": position,
                    "yes": counts.get("Sí", 0),
                    "no": counts.get("No", 0),
                    "abstain": counts.get("Abstención", 0),
                    "not_voting": counts.get("No vota", 0),
                }
            votes_out.append(
                {
                    "vote_event_id": vid,
                    "found": ev is not None,
                    "vote_date": ev["vote_date"] if ev else None,
                    "title": (ev["expediente_text"] if ev else None),
                    "subgroup": " ".join(x for x in ((ev["subgroup_title"] or "").strip(), (ev["subgroup_text"] or "").strip()) if x) if ev else None,
                    "totals": {"yes": ev["totals_yes"], "no": ev["totals_no"], "abstain": ev["totals_abstain"]} if ev else None,
                    "agree_vote": vote["agree_vote"],
                    "note": vote.get("note"),
                    "text_url": vote.get("text_url"),
                    "source_url": (ev["source_url"] if ev else None) or (vid[4:] if vid.startswith("url:") else None),
                    "explorer_member_votes": explorer_member_votes_link(vid),
                    "party_votes": party_votes,
                }
            )
        cells = {}
        for pid in party_ids:
            position = combine_positions(per_party_positions[pid])
            cell_counts[position] += 1
            cells[pid] = {
                "position": position,
                "votes_with_data": sum(1 for p in per_party_positions[pid] if p != "no_data"),
                "votes_total": len(per_party_positions[pid]),
            }
        statements_out.append(
            {
                "statement_id": st["statement_id"],
                "concern_id": st.get("concern_id"),
                "text": st["text"],
                "context": st.get("context"),
                "cells": cells,
                "votes": votes_out,
            }
        )

    vote_dates = sorted(ev["vote_date"] for ev in events.values() if ev["vote_date"])
    balance = direction_balance(statements_out, seed.get("balance_reference_parties") or [])
    return {
        "meta": {
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "generated_at": generated_at,
            "election": seed.get("election"),
            "legislature": seed.get("legislature"),
            "institution": seed.get("institution"),
            "review": seed.get("review"),
            "method": seed.get("method"),
            "votes_first_date": vote_dates[0] if vote_dates else None,
            "votes_last_date": vote_dates[-1] if vote_dates else None,
            "quality": {
                "statements_total": len(statements_out),
                "votes_total": len(vote_ids),
                "votes_missing": missing_events,
                "cells_total": sum(cell_counts.values()),
                "cells_by_position": dict(sorted(cell_counts.items())),
                "unmapped_member_votes": dict(sorted(unmapped.items())),
                "direction_balance": balance,
            },
            "honesty": [
                "Las posiciones salen solo de votaciones nominales del Congreso; no de programas ni declaraciones.",
                "Los partidos sin diputados en esta legislatura no tienen historial y no aparecen.",
                "Una votación puede contener más medidas que la afirmación resumida; revisa el texto enlazado.",
            ],
        },
        "parties": [
            {"party_id": p["party_id"], "label": p["label"], **({"note": p["note"]} if p.get("note") else {})}
            for p in seed["parties"]
        ],
        "unmapped_members": seed.get("unmapped_members") or [],
        "statements": statements_out,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--seed", default=str(DEFAULT_SEED))
    parser.add_argument("--concerns", default=str(DEFAULT_CONCERNS))
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-bytes", type=int, default=1_000_000)
    parser.add_argument("--allow-missing-votes", action="store_true", help="No fallar si alguna votación del seed no está en la base")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    seed = json.loads(Path(args.seed).read_text(encoding="utf-8"))
    concerns = json.loads(Path(args.concerns).read_text(encoding="utf-8"))
    concern_ids = {str(c.get("id")) for c in concerns.get("concerns") or []}
    errors = validate_seed(seed, concern_ids=concern_ids)
    if errors:
        for err in errors:
            print(f"ERROR seed: {err}", file=sys.stderr)
        return 2

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: no existe la base {db_path}", file=sys.stderr)
        return 2
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        snapshot = build_snapshot(
            conn,
            seed,
            generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        )
    finally:
        conn.close()

    missing = snapshot["meta"]["quality"]["votes_missing"]
    if missing and not args.allow_missing_votes:
        print(f"ERROR: {len(missing)} votaciones del seed no están en la base: {missing[:3]}", file=sys.stderr)
        return 3
    body = json.dumps(snapshot, ensure_ascii=False, indent=1, sort_keys=False) + "\n"
    size = len(body.encode("utf-8"))
    if size > int(args.max_bytes):
        print(f"ERROR: snapshot de {size} bytes supera --max-bytes {args.max_bytes}", file=sys.stderr)
        return 4
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    q = snapshot["meta"]["quality"]
    print(
        f"OK voting aid -> {args.out} (statements={q['statements_total']} votes={q['votes_total']} "
        f"cells={q['cells_by_position']} bytes={size})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
