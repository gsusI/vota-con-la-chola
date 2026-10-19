#!/usr/bin/env python3
"""Toolkit for the /visualizaciones/sistema/ edge catalog (one causal relation = one verifiable card).

  validate FILE...      check edge part files against the card contract (prints one line per problem)
  merge                 merge every part in etl/data/manual/system_model/edges/ into catalog.json (ids unique)
  show ID               print one card from the merged catalog
  apply-reviews         apply reviewer verdicts (reviews/<ID>.json: dotted-path corrections) to the part files

Contract: docs/etl/sprints/SISTEMA-COMPLEJO-20261019/README.md §4. Sources are fetched with
`python3 -m scripts.voting_aid_impacts_kit fetch URL -g REGEX` (shared cache, PDF -> text with page markers).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = REPO_ROOT / "etl/data/manual/system_model"
EDGES_DIR = MODEL_DIR / "edges"
CATALOG = MODEL_DIR / "catalog.json"

LAYERS = {"contable", "comportamiento", "segunda_ronda"}
GRADES = {"A", "B", "C", "D"}
SPAIN = {"si", "parcial", "no"}
REQUIRED = ["id", "from", "to", "sign", "layer", "parameter", "lag_years", "grade", "spain_evidence", "sources",
            "contrary_evidence", "debate", "derivation", "note_es"]


def problems(card: dict) -> list[str]:
    out = []
    for key in REQUIRED:
        if key not in card:
            out.append(f"missing key {key}")
    if out:
        return out
    if card["sign"] not in ("+", "-", "+/-"):
        out.append("sign must be +, - or +/-")
    if card["layer"] not in LAYERS:
        out.append(f"layer must be one of {sorted(LAYERS)}")
    if card["grade"] not in GRADES:
        out.append("grade must be A, B, C or D")
    if card["spain_evidence"] not in SPAIN:
        out.append("spain_evidence must be si, parcial or no")
    p = card["parameter"]
    for key in ("name", "unit", "low", "central", "high"):
        if p.get(key) in (None, ""):
            out.append(f"parameter.{key} empty")
    if all(isinstance(p.get(k), (int, float)) for k in ("low", "central", "high")):
        if not p["low"] <= p["central"] <= p["high"]:
            out.append("parameter must satisfy low <= central <= high")
    else:
        out.append("parameter low/central/high must be numbers")
    lag = card["lag_years"]
    if not (isinstance(lag, (int, float)) or (isinstance(lag, list) and len(lag) == 2 and lag[0] <= lag[1])):
        out.append("lag_years must be a number or [min, max]")
    if not card["sources"]:
        out.append("at least one source")
    for i, s in enumerate(card["sources"]):
        for key in ("url", "title", "authors_year", "country", "period", "method", "locator", "quote", "value_in_source"):
            if not s.get(key):
                out.append(f"sources[{i}].{key} empty")
        if s.get("url") and not re.match(r"https?://", s["url"]):
            out.append(f"sources[{i}].url not http(s)")
        if s.get("quote") and len(s["quote"].split()) > 40:
            out.append(f"sources[{i}].quote longer than 40 words")
    if card["grade"] == "A" and card["spain_evidence"] != "si":
        out.append("grade A requires spain_evidence = si")
    for i, c in enumerate(card["contrary_evidence"]):
        for key in ("url", "title", "finding"):
            if not c.get(key):
                out.append(f"contrary_evidence[{i}].{key} empty")
    if card["debate"] is not None:
        d = card["debate"]
        if not d.get("id") or len(d.get("schools") or []) < 2:
            out.append("debate needs id and at least two schools")
        for i, s in enumerate(d.get("schools") or []):
            if not s.get("label") or not isinstance(s.get("central"), (int, float)) or s.get("source_index") is None:
                out.append(f"debate.schools[{i}] needs label, central (number), source_index")
    for i, x in enumerate(card.get("extra_parameters") or []):
        for key in ("name", "unit", "low", "central", "high"):
            if x.get(key) in (None, ""):
                out.append(f"extra_parameters[{i}].{key} empty")
        if x.get("grade") is not None and x["grade"] not in GRADES:
            out.append(f"extra_parameters[{i}].grade must be A, B, C or D (optional: defaults to the card's)")
        if all(isinstance(x.get(k), (int, float)) for k in ("low", "central", "high")):
            if not x["low"] <= x["central"] <= x["high"]:
                out.append(f"extra_parameters[{i}] must satisfy low <= central <= high")
        else:
            out.append(f"extra_parameters[{i}] low/central/high must be numbers")
    if len(card["note_es"]) > 400:
        out.append("note_es longer than 400 characters")
    if re.search(r"\b(gracias a|por culpa de|provoca|causa)\b", card["note_es"], re.I) and not card["sources"]:
        out.append("causal wording without a source")
    if "TODO" in json.dumps(card, ensure_ascii=False):
        out.append("TODO left in card")
    return out


def load_part(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["edges"] if isinstance(data, dict) else data


def cmd_validate(files: list[str]) -> int:
    bad = 0
    for name in files:
        for card in load_part(Path(name)):
            for p in problems(card):
                bad += 1
                print(f"{Path(name).name} {card.get('id', '?')}: {p}")
    print("OK" if not bad else f"{bad} problem(s)")
    return 1 if bad else 0


def cmd_merge() -> int:
    cards: dict[str, dict] = {}
    for path in sorted(EDGES_DIR.glob("*.json")):
        for card in load_part(path):
            if card["id"] in cards:
                raise SystemExit(f"duplicate edge id {card['id']} in {path.name}")
            errs = problems(card)
            if errs:
                raise SystemExit(f"{path.name} {card['id']}: {errs[0]}")
            cards[card["id"]] = {**card, "part_file": path.name}
    CATALOG.write_text(json.dumps({"edges": [cards[k] for k in sorted(cards)]}, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8")
    print(f"{len(cards)} edges -> {CATALOG.relative_to(REPO_ROOT)}")
    return 0


def set_path(card: dict, path: str, value) -> None:
    keys = path.split(".")
    node = card
    for key in keys[:-1]:
        node = node[int(key)] if isinstance(node, list) else node.setdefault(key, {})
    last = keys[-1]
    if isinstance(node, list):
        idx = int(last)
        if idx == len(node):
            node.append(value)
        else:
            node[idx] = value
    else:
        node[last] = value


def cmd_apply_reviews() -> int:
    reviews = {json.loads(p.read_text(encoding="utf-8"))["id"]: json.loads(p.read_text(encoding="utf-8"))
               for p in sorted((MODEL_DIR / "reviews").glob("*.json"))}
    applied = 0
    for path in sorted(EDGES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for card in data["edges"]:
            review = reviews.get(card["id"])
            if not review:
                continue
            if review["verdict"] == "fail":
                raise SystemExit(f"{card['id']}: reviewer verdict fail; fix the card by hand")
            for dotted, value in (review.get("corrections") or {}).items():
                set_path(card, dotted, value)
            card["review"] = {"verdict": review["verdict"], "evidence": review.get("evidence", "")}
            changed = True
            applied += 1
        if changed:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{applied} reviews applied")
    return 0


def cmd_show(edge_id: str) -> int:
    for card in json.loads(CATALOG.read_text(encoding="utf-8"))["edges"]:
        if card["id"] == edge_id:
            print(json.dumps(card, ensure_ascii=False, indent=1))
            return 0
    print("not found")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate")
    v.add_argument("files", nargs="+")
    sub.add_parser("merge")
    sub.add_parser("apply-reviews")
    s = sub.add_parser("show")
    s.add_argument("id")
    args = parser.parse_args()
    if args.cmd == "validate":
        return cmd_validate(args.files)
    if args.cmd == "merge":
        return cmd_merge()
    if args.cmd == "apply-reviews":
        return cmd_apply_reviews()
    return cmd_show(args.id)


if __name__ == "__main__":
    sys.exit(main())
