#!/usr/bin/env python3
"""Export a CSV sheet for independent review of the voting aid statements.

One row per (statement, vote): the statement text, what was voted, which vote choice counts as
"agree", and links to the official vote and text. Reviewers fill the empty verdict columns
(`ok` / `cambiar` / `quitar`) and comments; results are applied back to the seed by hand.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SNAPSHOT = BASE_DIR / "ui/gh-pages-next/public/citizen/data/voting_aid_generales_v1.json"
DEFAULT_OUT = BASE_DIR / "etl/data/published/voting_aid_generales_v1_review_sheet.csv"

COLUMNS = [
    "statement_id",
    "statement_text",
    "vote_date",
    "vote_title",
    "vote_subgroup",
    "agree_vote",
    "vote_note",
    "official_vote_url",
    "voted_text_url",
    "parties_agree",
    "parties_disagree",
    "reviewer",
    "verdict_statement_wording",
    "verdict_agree_vote",
    "comment",
]


def rows_from_snapshot(snapshot: dict) -> list[dict[str, str]]:
    labels = {p["party_id"]: p["label"] for p in snapshot.get("parties") or []}
    rows: list[dict[str, str]] = []
    for st in snapshot.get("statements") or []:
        for vote in st.get("votes") or []:
            pv = vote.get("party_votes") or {}
            rows.append(
                {
                    "statement_id": st["statement_id"],
                    "statement_text": st["text"],
                    "vote_date": vote.get("vote_date") or "",
                    "vote_title": vote.get("title") or "",
                    "vote_subgroup": vote.get("subgroup") or "",
                    "agree_vote": vote.get("agree_vote") or "",
                    "vote_note": vote.get("note") or "",
                    "official_vote_url": vote.get("source_url") or "",
                    "voted_text_url": vote.get("text_url") or "",
                    "parties_agree": ", ".join(labels[p] for p, v in pv.items() if v.get("position") == "agree"),
                    "parties_disagree": ", ".join(labels[p] for p, v in pv.items() if v.get("position") == "disagree"),
                    "reviewer": "",
                    "verdict_statement_wording": "",
                    "verdict_agree_vote": "",
                    "comment": "",
                }
            )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    rows = rows_from_snapshot(snapshot)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    shown = out.resolve().relative_to(BASE_DIR) if out.resolve().is_relative_to(BASE_DIR) else out
    print(f"OK review sheet -> {shown} (rows={len(rows)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
