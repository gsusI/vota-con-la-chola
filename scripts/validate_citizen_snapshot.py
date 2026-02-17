#!/usr/bin/env python3

import argparse
import json
import os
import sys
from collections import Counter


ALLOWED_STANCES = {"support", "oppose", "mixed", "unclear", "no_signal"}


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(2)


def warn(msg: str) -> None:
    print(f"WARN: {msg}", file=sys.stderr)


def require_key(d: dict, key: str, ctx: str) -> None:
    if key not in d:
        die(f"Missing key {key!r} in {ctx}")


def require_type(v, t, ctx: str) -> None:
    if not isinstance(v, t):
        die(f"Expected {ctx} to be {t.__name__}, got {type(v).__name__}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Valida snapshot JSON para app ciudadana (GH Pages)")
    ap.add_argument(
        "--path",
        required=True,
        help="Ruta al citizen.json (p.ej. docs/gh-pages/citizen/data/citizen.json)",
    )
    ap.add_argument(
        "--max-bytes",
        type=int,
        default=None,
        help="Fail si el archivo supera este tamaño (bytes). Si se omite, usa meta.guards.max_bytes si existe.",
    )
    ap.add_argument(
        "--strict-grid",
        action="store_true",
        help="Fail si party_topic_positions no cubre topics x parties exactamente.",
    )
    args = ap.parse_args()

    path = args.path
    if not os.path.exists(path):
        die(f"File not found: {path}")

    size = os.path.getsize(path)
    with open(path, "rb") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            die(f"Invalid JSON: {e}")

    require_type(data, dict, "root")
    for k in ("meta", "topics", "parties", "party_topic_positions", "concerns"):
        require_key(data, k, "root")

    meta = data["meta"]
    topics = data["topics"]
    parties = data["parties"]
    positions = data["party_topic_positions"]
    concerns = data["concerns"]
    programas = data.get("party_concern_programas")

    require_type(meta, dict, "meta")
    require_type(topics, list, "topics")
    require_type(parties, list, "parties")
    require_type(positions, list, "party_topic_positions")
    require_type(concerns, dict, "concerns")
    if programas is not None:
        require_type(programas, list, "party_concern_programas")

    for k in ("topic_set_id", "as_of_date", "computed_method", "computed_version", "generated_at"):
        require_key(meta, k, "meta")

    topic_ids = []
    for i, t in enumerate(topics):
        ctx = f"topics[{i}]"
        require_type(t, dict, ctx)
        for k in ("topic_id", "label", "stakes_rank", "is_high_stakes", "links"):
            require_key(t, k, ctx)
        require_type(t["topic_id"], int, f"{ctx}.topic_id")
        require_type(t["label"], str, f"{ctx}.label")
        require_type(t["stakes_rank"], int, f"{ctx}.stakes_rank")
        require_type(t["is_high_stakes"], bool, f"{ctx}.is_high_stakes")
        require_type(t["links"], dict, f"{ctx}.links")
        topic_ids.append(t["topic_id"])

    if len(set(topic_ids)) != len(topic_ids):
        die("Duplicate topic_id values in topics[]")

    party_ids = []
    for i, p in enumerate(parties):
        ctx = f"parties[{i}]"
        require_type(p, dict, ctx)
        for k in ("party_id", "name", "acronym", "links"):
            require_key(p, k, ctx)
        require_type(p["party_id"], int, f"{ctx}.party_id")
        require_type(p["name"], str, f"{ctx}.name")
        require_type(p["acronym"], str, f"{ctx}.acronym")
        require_type(p["links"], dict, f"{ctx}.links")
        party_ids.append(p["party_id"])

    if len(set(party_ids)) != len(party_ids):
        die("Duplicate party_id values in parties[]")

    topic_id_set = set(topic_ids)
    party_id_set = set(party_ids)

    stance_counts: Counter[str] = Counter()
    bad_refs = 0
    for i, row in enumerate(positions):
        ctx = f"party_topic_positions[{i}]"
        require_type(row, dict, ctx)
        for k in ("topic_id", "party_id", "stance", "score", "confidence", "coverage", "links"):
            require_key(row, k, ctx)

        require_type(row["topic_id"], int, f"{ctx}.topic_id")
        require_type(row["party_id"], int, f"{ctx}.party_id")
        require_type(row["stance"], str, f"{ctx}.stance")
        if row["stance"] not in ALLOWED_STANCES:
            die(f"Invalid stance {row['stance']!r} at {ctx}")

        # Exporter normalizes to floats; accept int/float in case of 0 literals.
        if not isinstance(row["score"], (int, float)):
            die(f"Expected {ctx}.score to be number, got {type(row['score']).__name__}")
        if not isinstance(row["confidence"], (int, float)):
            die(f"Expected {ctx}.confidence to be number, got {type(row['confidence']).__name__}")
        require_type(row["coverage"], dict, f"{ctx}.coverage")
        require_type(row["links"], dict, f"{ctx}.links")

        if row["topic_id"] not in topic_id_set or row["party_id"] not in party_id_set:
            bad_refs += 1

        stance_counts[row["stance"]] += 1

    if bad_refs:
        die(f"{bad_refs} rows in party_topic_positions reference missing topic_id/party_id")

    expected_grid = len(topic_ids) * len(party_ids)
    if len(positions) != expected_grid:
        msg = f"party_topic_positions length={len(positions)} expected topics x parties={expected_grid}"
        if args.strict_grid:
            die(msg)
        warn(msg)

    # Optional programas grid: stances by (concern_id, party_id).
    programas_stances: Counter[str] = Counter()
    if programas is not None:
        seen_keys: set[tuple[str, int]] = set()
        bad_prog_party = 0
        for i, row in enumerate(programas):
            ctx = f"party_concern_programas[{i}]"
            require_type(row, dict, ctx)
            for k in ("concern_id", "party_id", "stance", "confidence", "links"):
                require_key(row, k, ctx)
            require_type(row["concern_id"], str, f"{ctx}.concern_id")
            require_type(row["party_id"], int, f"{ctx}.party_id")
            require_type(row["stance"], str, f"{ctx}.stance")
            if row["stance"] not in ALLOWED_STANCES:
                die(f"Invalid stance {row['stance']!r} at {ctx}")
            if not isinstance(row["confidence"], (int, float)):
                die(f"Expected {ctx}.confidence to be number, got {type(row['confidence']).__name__}")
            require_type(row["links"], dict, f"{ctx}.links")

            key = (str(row["concern_id"]), int(row["party_id"]))
            if key in seen_keys:
                die(f"Duplicate (concern_id, party_id) in party_concern_programas: {key}")
            seen_keys.add(key)

            if int(row["party_id"]) not in party_id_set:
                bad_prog_party += 1
            programas_stances[row["stance"]] += 1

        if bad_prog_party:
            die(f"{bad_prog_party} rows in party_concern_programas reference missing party_id")

    # Size guardrail: prefer explicit CLI; fallback to meta.guards.max_bytes; otherwise no check.
    meta_max = None
    guards = meta.get("guards")
    if isinstance(guards, dict):
        meta_max = guards.get("max_bytes")
    max_bytes = args.max_bytes if args.max_bytes is not None else meta_max
    if isinstance(max_bytes, int) and max_bytes > 0 and size > max_bytes:
        die(f"Snapshot too large: {size} bytes > max_bytes={max_bytes}")

    # Print compact KPI summary (machine-parseable-ish).
    print(json.dumps(
        {
            "path": path,
            "bytes": size,
            "topic_set_id": meta.get("topic_set_id"),
            "as_of_date": meta.get("as_of_date"),
            "computed_method": meta.get("computed_method"),
            "computed_version": meta.get("computed_version"),
            "topics": len(topic_ids),
            "parties": len(party_ids),
            "party_topic_positions": len(positions),
            "stances": dict(stance_counts),
            "programas_stances": dict(programas_stances) if programas is not None else None,
        },
        ensure_ascii=True,
        separators=(",", ":"),
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
