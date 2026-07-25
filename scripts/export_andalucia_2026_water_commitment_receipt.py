#!/usr/bin/env python3
"""Validate and export the reviewed Andalucía water-commitment receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED = ROOT / "etl/data/seeds/andalucia_2026_water_commitments.json"
DEFAULT_OUT = ROOT / "etl/data/published/andalucia-2026-water-commitment-receipt.json"
DEFAULT_PUBLIC_OUT = (
    ROOT
    / "ui/gh-pages-next/public/elecciones/andalucia-2026/data/water-receipt.json"
)

ALLOWED_STATUSES = {
    "declarado",
    "acto_oficial",
    "financiado",
    "contratado",
    "entrega_observada",
    "resultado_observado",
    "sin_evidencia",
    "incierto",
}
OFFICIAL_HOST_SUFFIXES = (
    "juntadeandalucia.es",
    "parlamentodeandalucia.es",
)
MAX_PUBLIC_BYTES = 250_000


def _required_text(container: dict, key: str, location: str) -> str:
    value = str(container.get(key) or "").strip()
    if not value:
        raise ValueError(f"{location}.{key} is required")
    return value


def _validate_official_url(url: str, location: str) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        raise ValueError(f"{location} must use https")
    if not any(host == suffix or host.endswith(f".{suffix}") for suffix in OFFICIAL_HOST_SUFFIXES):
        raise ValueError(f"{location} must point to an official Andalucía host")


def validate_receipt(payload: dict) -> None:
    if payload.get("schema_version") != "andalucia_water_commitment_receipt_v1":
        raise ValueError("unsupported schema_version")

    snapshot_date = _required_text(payload, "snapshot_date", "receipt")
    _required_text(payload, "title", "receipt")
    _required_text(payload, "question", "receipt")

    scope = payload.get("scope")
    if not isinstance(scope, dict):
        raise ValueError("receipt.scope must be an object")
    window_start = _required_text(scope, "evidence_window_start", "receipt.scope")
    window_end = _required_text(scope, "evidence_window_end", "receipt.scope")
    if not (window_start <= window_end <= snapshot_date):
        raise ValueError("evidence window must end on or before snapshot_date")

    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("receipt.sources must be a non-empty array")
    source_ids: set[str] = set()
    for index, source in enumerate(sources):
        location = f"receipt.sources[{index}]"
        source_id = _required_text(source, "source_id", location)
        if source_id in source_ids:
            raise ValueError(f"duplicate source_id: {source_id}")
        source_ids.add(source_id)
        _required_text(source, "label", location)
        _required_text(source, "published_date", location)
        _required_text(source, "locator", location)
        source_url = _required_text(source, "url", location)
        _validate_official_url(source_url, f"{location}.url")

    evidence_check = payload.get("evidence_check")
    if not isinstance(evidence_check, dict):
        raise ValueError("receipt.evidence_check must be an object")
    if _required_text(evidence_check, "checked_at", "receipt.evidence_check") != snapshot_date:
        raise ValueError("evidence_check.checked_at must equal snapshot_date")
    _required_text(evidence_check, "limitation", "receipt.evidence_check")
    official_scopes = evidence_check.get("official_scopes")
    if not isinstance(official_scopes, list) or len(official_scopes) < 2:
        raise ValueError("evidence_check.official_scopes must include at least two sources")
    for index, source_scope in enumerate(official_scopes):
        scope_url = _required_text(
            source_scope,
            "url",
            f"receipt.evidence_check.official_scopes[{index}]",
        )
        _validate_official_url(
            scope_url,
            f"receipt.evidence_check.official_scopes[{index}].url",
        )

    commitments = payload.get("commitments")
    if not isinstance(commitments, list) or len(commitments) != 3:
        raise ValueError("receipt.commitments must contain exactly three items")
    commitment_ids: set[str] = set()
    for index, commitment in enumerate(commitments):
        location = f"receipt.commitments[{index}]"
        commitment_id = _required_text(commitment, "commitment_id", location)
        if commitment_id in commitment_ids:
            raise ValueError(f"duplicate commitment_id: {commitment_id}")
        commitment_ids.add(commitment_id)
        for key in (
            "title",
            "declaration",
            "source_excerpt",
            "status_label",
            "status_detail",
            "checkpoint",
            "money_and_delivery",
        ):
            _required_text(commitment, key, location)
        declared_source_id = _required_text(
            commitment,
            "declared_source_id",
            location,
        )
        if declared_source_id not in source_ids:
            raise ValueError(f"{location}.declared_source_id is unknown")
        status = _required_text(commitment, "status", location)
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"{location}.status is unsupported: {status}")
        progress_evidence = [
            item
            for item in commitment.get("post_investiture_evidence", [])
            if item.get("counts_as_progress") is True
        ]
        if status != "declarado" and not progress_evidence:
            raise ValueError(f"{location} needs evidence before advancing status")
        for key in ("unknowns", "limitations"):
            values = commitment.get(key)
            if not isinstance(values, list) or not any(str(value).strip() for value in values):
                raise ValueError(f"{location}.{key} must be a non-empty array")
        ownership = commitment.get("ownership")
        if not isinstance(ownership, dict):
            raise ValueError(f"{location}.ownership must be an object")
        _required_text(ownership, "executive", f"{location}.ownership")
        _required_text(ownership, "legislature", f"{location}.ownership")


def build_receipt(seed: dict) -> dict:
    payload = json.loads(json.dumps(seed, ensure_ascii=False))
    validate_receipt(payload)
    commitments = payload["commitments"]
    payload["summary"] = {
        "commitments_total": len(commitments),
        "declared_only_total": sum(
            1 for commitment in commitments if commitment["status"] == "declarado"
        ),
        "post_investiture_actions_total": sum(
            1
            for commitment in commitments
            if any(
                item.get("counts_as_progress") is True
                for item in commitment["post_investiture_evidence"]
            )
        ),
        "changed_since_previous_snapshot": "sin_corte_anterior_comparable",
    }
    return payload


def _write_json(path: Path, payload: dict) -> int:
    encoded = (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)
    return len(encoded)


def export_receipt(seed_path: Path, output_paths: list[Path]) -> dict:
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    payload = build_receipt(seed)
    for output_path in output_paths:
        size = _write_json(output_path, payload)
        if size > MAX_PUBLIC_BYTES:
            raise ValueError(
                f"{output_path} exceeds public receipt budget: "
                f"{size} > {MAX_PUBLIC_BYTES} bytes"
            )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--public-out", type=Path, default=DEFAULT_PUBLIC_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = export_receipt(args.seed, [args.out, args.public_out])
    summary = payload["summary"]
    print(
        "Andalucía water receipt exported: "
        f"{summary['commitments_total']} commitments, "
        f"{summary['post_investiture_actions_total']} post-investiture actions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
