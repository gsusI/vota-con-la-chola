#!/usr/bin/env python3
"""Validate and export the reviewed Andalucía water-commitment receipt."""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED = ROOT / "etl/data/seeds/andalucia_2026_water_commitments.json"
DEFAULT_OUT = ROOT / "etl/data/published/andalucia-2026-water-commitment-receipt.json"
DEFAULT_PUBLIC_OUT = (
    ROOT
    / "ui/gh-pages-next/public/elecciones/andalucia-2026/data/water-receipt.json"
)
DEFAULT_ARCHIVE_DIR = (
    ROOT / "etl/data/published/andalucia-water-receipt/snapshots"
)
DEFAULT_PUBLIC_ARCHIVE_DIR = (
    ROOT
    / "ui/gh-pages-next/public/elecciones/andalucia-2026/data/water-receipt/snapshots"
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
DEFAULT_MAX_AGE_DAYS = 8


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

    method = payload.get("method")
    if not isinstance(method, dict):
        raise ValueError("receipt.method must be an object")
    next_check = _required_text(method, "next_check", "receipt.method")
    if next_check <= snapshot_date:
        raise ValueError("receipt.method.next_check must be after snapshot_date")

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


def _commitments_by_id(payload: dict | None) -> dict[str, dict]:
    if not isinstance(payload, dict):
        return {}
    commitments = payload.get("commitments")
    if not isinstance(commitments, list):
        return {}
    return {
        str(item.get("commitment_id")): item
        for item in commitments
        if isinstance(item, dict) and item.get("commitment_id")
    }


def _evidence_identity(item: dict) -> tuple[str, str, str]:
    return (
        str(item.get("source_id") or ""),
        str(item.get("date") or ""),
        str(item.get("evidence_kind") or ""),
    )


def build_change_summary(payload: dict, previous: dict | None) -> dict:
    current_date = str(payload["snapshot_date"])
    if not previous:
        return {
            "status": "first_snapshot",
            "current_snapshot_date": current_date,
            "previous_snapshot_date": None,
            "commitments_changed_total": 0,
            "changes_total": 0,
            "commitments": [],
        }

    previous_date = _required_text(previous, "snapshot_date", "previous_receipt")
    if previous_date >= current_date:
        raise ValueError("previous snapshot must be older than current snapshot")

    previous_by_id = _commitments_by_id(previous)
    current_by_id = _commitments_by_id(payload)
    changes: list[dict] = []
    for commitment in payload["commitments"]:
        commitment_id = commitment["commitment_id"]
        before = previous_by_id.get(commitment_id)
        if before is None:
            changes.append(
                {
                    "commitment_id": commitment_id,
                    "title": commitment["title"],
                    "change_kinds": ["commitment_added"],
                    "status_before": None,
                    "status_after": commitment["status"],
                    "evidence_added": commitment.get(
                        "post_investiture_evidence",
                        [],
                    ),
                }
            )
            continue

        change_kinds: list[str] = []
        if before.get("status") != commitment.get("status"):
            change_kinds.append("status_changed")
        if before.get("checkpoint") != commitment.get("checkpoint"):
            change_kinds.append("checkpoint_changed")
        if before.get("ownership") != commitment.get("ownership"):
            change_kinds.append("ownership_changed")
        if before.get("status_detail") != commitment.get("status_detail"):
            change_kinds.append("assessment_changed")

        previous_evidence = {
            _evidence_identity(item)
            for item in before.get("post_investiture_evidence", [])
            if isinstance(item, dict)
        }
        evidence_added = [
            item
            for item in commitment.get("post_investiture_evidence", [])
            if isinstance(item, dict)
            and _evidence_identity(item) not in previous_evidence
        ]
        if evidence_added:
            change_kinds.append("evidence_added")

        if change_kinds:
            changes.append(
                {
                    "commitment_id": commitment_id,
                    "title": commitment["title"],
                    "change_kinds": change_kinds,
                    "status_before": before.get("status"),
                    "status_after": commitment.get("status"),
                    "evidence_added": evidence_added,
                }
            )

    for commitment_id, before in previous_by_id.items():
        if commitment_id in current_by_id:
            continue
        changes.append(
            {
                "commitment_id": commitment_id,
                "title": before.get("title") or commitment_id,
                "change_kinds": ["commitment_removed"],
                "status_before": before.get("status"),
                "status_after": None,
                "evidence_added": [],
            }
        )

    return {
        "status": "changed" if changes else "no_change",
        "current_snapshot_date": current_date,
        "previous_snapshot_date": previous_date,
        "commitments_changed_total": len(changes),
        "changes_total": sum(len(item["change_kinds"]) for item in changes),
        "commitments": changes,
    }


def build_receipt(seed: dict, previous: dict | None = None) -> dict:
    payload = json.loads(json.dumps(seed, ensure_ascii=False))
    validate_receipt(payload)
    commitments = payload["commitments"]
    change_summary = build_change_summary(payload, previous)
    payload["history"] = change_summary
    if change_summary["status"] == "first_snapshot":
        changed_since_previous = "sin_corte_anterior_comparable"
    elif change_summary["status"] == "no_change":
        changed_since_previous = (
            f"sin_cambios_desde_{change_summary['previous_snapshot_date']}"
        )
    else:
        changed_since_previous = (
            f"{change_summary['commitments_changed_total']}_compromisos_con_cambios"
        )
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
        "changed_since_previous_snapshot": changed_since_previous,
    }
    return payload


def check_freshness(
    payload: dict,
    *,
    as_of_date: str,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> dict:
    snapshot = date.fromisoformat(_required_text(payload, "snapshot_date", "receipt"))
    as_of = date.fromisoformat(as_of_date)
    age_days = (as_of - snapshot).days
    if age_days < 0:
        raise ValueError("as_of_date cannot be before snapshot_date")
    if age_days > max_age_days:
        raise ValueError(
            "water receipt is stale: "
            f"snapshot_date={snapshot.isoformat()} "
            f"as_of_date={as_of.isoformat()} age_days={age_days} "
            f"max_age_days={max_age_days}"
        )
    return {
        "status": "current",
        "snapshot_date": snapshot.isoformat(),
        "as_of_date": as_of.isoformat(),
        "age_days": age_days,
        "max_age_days": max_age_days,
    }


def build_freshness_metadata(payload: dict, *, max_age_days: int) -> dict:
    snapshot = date.fromisoformat(_required_text(payload, "snapshot_date", "receipt"))
    return {
        "last_checked_date": snapshot.isoformat(),
        "next_check_date": _required_text(
            payload["method"],
            "next_check",
            "receipt.method",
        ),
        "stale_after_date": (
            snapshot + timedelta(days=max_age_days + 1)
        ).isoformat(),
        "max_age_days": max_age_days,
    }


def _encode_json(payload: dict) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _write_json(path: Path, payload: dict) -> int:
    encoded = _encode_json(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)
    return len(encoded)


def _write_immutable_json(path: Path, payload: dict) -> int:
    encoded = _encode_json(payload)
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError(
                f"immutable receipt snapshot already exists with different content: {path}"
            )
        return len(encoded)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)
    return len(encoded)


def _load_previous_snapshot(
    archive_dir: Path,
    current_snapshot_date: str,
) -> dict | None:
    candidates: list[tuple[str, Path]] = []
    if archive_dir.exists():
        for path in archive_dir.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            snapshot_date = str(payload.get("snapshot_date") or "")
            if snapshot_date and snapshot_date < current_snapshot_date:
                candidates.append((snapshot_date, path))
    if not candidates:
        return None
    _, latest_path = max(candidates, key=lambda item: item[0])
    return json.loads(latest_path.read_text(encoding="utf-8"))


def export_receipt(
    seed_path: Path,
    output_paths: list[Path],
    *,
    archive_dirs: list[Path] | None = None,
    previous_path: Path | None = None,
    as_of_date: str | None = None,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> dict:
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    previous = None
    if previous_path is not None:
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
    elif archive_dirs:
        previous = _load_previous_snapshot(
            archive_dirs[0],
            str(seed.get("snapshot_date") or ""),
        )
    payload = build_receipt(seed, previous=previous)
    if as_of_date is not None:
        check_freshness(
            payload,
            as_of_date=as_of_date,
            max_age_days=max_age_days,
        )
    payload["freshness"] = build_freshness_metadata(
        payload,
        max_age_days=max_age_days,
    )
    for output_path in output_paths:
        size = _write_json(output_path, payload)
        if size > MAX_PUBLIC_BYTES:
            raise ValueError(
                f"{output_path} exceeds public receipt budget: "
                f"{size} > {MAX_PUBLIC_BYTES} bytes"
            )
    for archive_dir in archive_dirs or []:
        archive_path = archive_dir / f"{payload['snapshot_date']}.json"
        size = _write_immutable_json(archive_path, payload)
        if size > MAX_PUBLIC_BYTES:
            raise ValueError(
                f"{archive_path} exceeds public receipt budget: "
                f"{size} > {MAX_PUBLIC_BYTES} bytes"
            )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--public-out", type=Path, default=DEFAULT_PUBLIC_OUT)
    parser.add_argument("--archive-dir", type=Path, default=DEFAULT_ARCHIVE_DIR)
    parser.add_argument(
        "--public-archive-dir",
        type=Path,
        default=DEFAULT_PUBLIC_ARCHIVE_DIR,
    )
    parser.add_argument("--previous", type=Path)
    parser.add_argument(
        "--as-of-date",
        default=date.today().isoformat(),
        help="Date used by the freshness gate (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=DEFAULT_MAX_AGE_DAYS,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = export_receipt(
        args.seed,
        [args.out, args.public_out],
        archive_dirs=[args.archive_dir, args.public_archive_dir],
        previous_path=args.previous,
        as_of_date=args.as_of_date,
        max_age_days=args.max_age_days,
    )
    summary = payload["summary"]
    history = payload["history"]
    freshness = check_freshness(
        payload,
        as_of_date=args.as_of_date,
        max_age_days=args.max_age_days,
    )
    print(
        "Andalucía water receipt exported: "
        f"{summary['commitments_total']} commitments, "
        f"{summary['post_investiture_actions_total']} post-investiture actions, "
        f"history={history['status']}, "
        f"freshness_age_days={freshness['age_days']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
