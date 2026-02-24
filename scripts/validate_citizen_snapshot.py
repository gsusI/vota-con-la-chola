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

    # Optional v2 extension: list of methods available for the exported scope/as_of_date.
    methods_available = meta.get("methods_available")
    if methods_available is not None:
        require_type(methods_available, list, "meta.methods_available")
        meths: list[str] = []
        for i, m in enumerate(methods_available):
            require_type(m, str, f"meta.methods_available[{i}]")
            token = str(m).strip()
            if not token:
                die("meta.methods_available contains empty string")
            meths.append(token)
        # Determinism guardrail: sorted unique.
        if meths != sorted(set(meths)):
            die("meta.methods_available must be sorted unique")
        if str(meta.get("computed_method") or "") not in set(meths):
            die("meta.computed_method must be included in meta.methods_available")

    # Optional v3 extension: aggregate quality semantics used by citizen UI status chips.
    quality = meta.get("quality")
    if quality is not None:
        require_type(quality, dict, "meta.quality")
        for k in (
            "cells_total",
            "stance_counts",
            "clear_total",
            "clear_pct",
            "any_signal_total",
            "any_signal_pct",
            "unknown_total",
            "unknown_pct",
            "confidence_avg_signal",
            "confidence_tiers",
            "confidence_thresholds",
        ):
            require_key(quality, k, "meta.quality")

        if not isinstance(quality["cells_total"], int):
            die(f"Expected meta.quality.cells_total to be int, got {type(quality['cells_total']).__name__}")
        if not isinstance(quality["clear_total"], int):
            die(f"Expected meta.quality.clear_total to be int, got {type(quality['clear_total']).__name__}")
        if not isinstance(quality["any_signal_total"], int):
            die(
                f"Expected meta.quality.any_signal_total to be int, got {type(quality['any_signal_total']).__name__}"
            )
        if not isinstance(quality["unknown_total"], int):
            die(f"Expected meta.quality.unknown_total to be int, got {type(quality['unknown_total']).__name__}")
        if quality["cells_total"] < 0 or quality["clear_total"] < 0 or quality["any_signal_total"] < 0 or quality["unknown_total"] < 0:
            die("meta.quality integer counters must be >= 0")

        for k in ("clear_pct", "any_signal_pct", "unknown_pct", "confidence_avg_signal"):
            if not isinstance(quality[k], (int, float)):
                die(f"Expected meta.quality.{k} to be number, got {type(quality[k]).__name__}")
            x = float(quality[k])
            if x < 0.0 or x > 1.0:
                die(f"meta.quality.{k} must be in [0,1], got {x}")

        require_type(quality["stance_counts"], dict, "meta.quality.stance_counts")
        stance_counts = quality["stance_counts"]
        for s in ALLOWED_STANCES:
            if s not in stance_counts:
                die(f"meta.quality.stance_counts missing key {s!r}")
            if not isinstance(stance_counts[s], int):
                die(
                    f"Expected meta.quality.stance_counts[{s!r}] to be int, got {type(stance_counts[s]).__name__}"
                )
            if int(stance_counts[s]) < 0:
                die(f"meta.quality.stance_counts[{s!r}] must be >= 0")
        if sum(int(stance_counts[s]) for s in ALLOWED_STANCES) != int(quality["cells_total"]):
            die("meta.quality.stance_counts must sum to meta.quality.cells_total")

        require_type(quality["confidence_tiers"], dict, "meta.quality.confidence_tiers")
        tiers = quality["confidence_tiers"]
        for t in ("high", "medium", "low", "none"):
            if t not in tiers:
                die(f"meta.quality.confidence_tiers missing key {t!r}")
            if not isinstance(tiers[t], int):
                die(
                    f"Expected meta.quality.confidence_tiers[{t!r}] to be int, got {type(tiers[t]).__name__}"
                )
            if int(tiers[t]) < 0:
                die(f"meta.quality.confidence_tiers[{t!r}] must be >= 0")
        if sum(int(tiers[t]) for t in ("high", "medium", "low", "none")) != int(quality["cells_total"]):
            die("meta.quality.confidence_tiers must sum to meta.quality.cells_total")

        require_type(quality["confidence_thresholds"], dict, "meta.quality.confidence_thresholds")
        thresholds = quality["confidence_thresholds"]
        for k in ("high_min", "medium_min"):
            if k not in thresholds:
                die(f"meta.quality.confidence_thresholds missing key {k!r}")
            if not isinstance(thresholds[k], (int, float)):
                die(
                    f"Expected meta.quality.confidence_thresholds[{k!r}] to be number, got {type(thresholds[k]).__name__}"
                )
        high_min = float(thresholds["high_min"])
        medium_min = float(thresholds["medium_min"])
        if not (0.0 <= medium_min <= high_min <= 1.0):
            die("meta.quality.confidence_thresholds must satisfy 0 <= medium_min <= high_min <= 1")

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

        # Optional v2 extension: server-side concern tags.
        if "concern_ids" in t:
            require_type(t["concern_ids"], list, f"{ctx}.concern_ids")
            cids: list[str] = []
            for j, cid in enumerate(t["concern_ids"]):
                require_type(cid, str, f"{ctx}.concern_ids[{j}]")
                token = str(cid).strip()
                if not token:
                    die(f"Empty concern_id at {ctx}.concern_ids[{j}]")
                cids.append(token)
            if cids != sorted(set(cids)):
                die(f"{ctx}.concern_ids must be sorted unique")

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
