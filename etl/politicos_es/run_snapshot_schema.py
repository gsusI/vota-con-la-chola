from __future__ import annotations

import csv
import re
from datetime import date
from pathlib import Path
from typing import Any, Mapping

RUN_SNAPSHOT_SCHEMA_VERSION = "v2"

# Canonical schema used for replay/strict parity checks across all source families.
NORMALIZED_RUN_SNAPSHOT_FIELDS = (
    "schema_version",
    "source_id",
    "mode",
    "exit_code",
    "run_records_loaded",
    "snapshot_date",
    "run_id",
    "run_status",
    "run_records_seen",
    "before_records",
    "after_records",
    "delta_records",
    "run_started_at",
    "run_finished_at",
    "source_url",
    "command",
    "message",
    "source_record_id",
    "entity_id",
)

_INT_FIELDS = {
    "exit_code",
    "run_records_loaded",
    "run_id",
    "run_records_seen",
    "before_records",
    "after_records",
    "delta_records",
}

_SOURCE_ARG_RE = re.compile(r"(?:^|\s)--source\s+([^\s]+)")


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _normalize_snapshot_date(raw_value: str) -> str:
    token = (raw_value or "").strip()
    if not token:
        return ""

    if len(token) == 8 and token.isdigit():
        year = token[0:4]
        month = token[4:6]
        day = token[6:8]
        normalized = f"{year}-{month}-{day}"
        try:
            _ = date.fromisoformat(normalized)
            return normalized
        except ValueError:
            return token

    if "T" in token and len(token) >= 10:
        candidate = token[:10]
        try:
            _ = date.fromisoformat(candidate)
            return candidate
        except ValueError:
            pass

    try:
        _ = date.fromisoformat(token)
        return token
    except ValueError:
        return token


def _coerce_int_text(raw_value: str) -> str:
    token = (raw_value or "").strip()
    if not token:
        return ""
    try:
        return str(int(token))
    except ValueError:
        return ""


def _load_metric_value_snapshot(lines: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        key, sep, value = line.partition(",")
        if not sep:
            continue
        out[key.strip()] = value.strip()
    return out


def load_run_snapshot_file(path: str | Path) -> dict[str, str]:
    snapshot_path = Path(path)
    if not snapshot_path.exists():
        raise FileNotFoundError(f"Snapshot no encontrado: {snapshot_path}")

    content = snapshot_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    if not lines:
        return {}

    header = lines[0].strip().lower()
    if header == "metric,value":
        return _load_metric_value_snapshot(lines[1:])

    reader = csv.DictReader(lines)
    row = next(reader, None)
    if row is None:
        return {}
    return {str(key).strip(): _to_text(value).strip() for key, value in row.items() if key is not None}


def _infer_source_id(raw: Mapping[str, str]) -> str:
    direct = (raw.get("source_id") or "").strip()
    if direct:
        return direct
    command = (raw.get("command") or "").strip()
    if command:
        match = _SOURCE_ARG_RE.search(command)
        if match:
            return match.group(1).strip()
    return ""


def _infer_mode(raw: Mapping[str, str]) -> str:
    direct = (raw.get("mode") or "").strip()
    if direct:
        return direct

    source_url = (raw.get("source_url") or "").strip()
    if source_url.startswith("file://"):
        return "from-file"
    if source_url.startswith("http://") or source_url.startswith("https://"):
        return "network"
    return ""


def _infer_entity_id(raw: Mapping[str, str]) -> str:
    for key in ("entity_id", "series_id", "source_record_id"):
        value = (raw.get(key) or "").strip()
        if value:
            return value
    station_id = (raw.get("station_id") or "").strip()
    variable = (raw.get("variable") or "").strip()
    if station_id and variable:
        return f"station:{station_id}:var:{variable}"
    return ""


def normalize_run_snapshot_row(
    raw_row: Mapping[str, Any],
    *,
    defaults: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    combined: dict[str, str] = {
        str(key).strip(): _to_text(value).strip() for key, value in raw_row.items() if key is not None
    }
    if defaults:
        for key, value in defaults.items():
            token = _to_text(value).strip()
            if token and not combined.get(key):
                combined[key] = token

    snapshot_date = _normalize_snapshot_date(combined.get("snapshot_date") or combined.get("snapshot") or "")
    source_id = _infer_source_id(combined)
    mode = _infer_mode(combined)

    normalized: dict[str, str] = {field: "" for field in NORMALIZED_RUN_SNAPSHOT_FIELDS}
    normalized["schema_version"] = RUN_SNAPSHOT_SCHEMA_VERSION
    normalized["source_id"] = source_id
    normalized["mode"] = mode
    normalized["snapshot_date"] = snapshot_date
    normalized["run_status"] = (combined.get("run_status") or combined.get("status") or "").strip()
    normalized["run_started_at"] = (combined.get("run_started_at") or combined.get("started_at") or "").strip()
    normalized["run_finished_at"] = (combined.get("run_finished_at") or combined.get("finished_at") or "").strip()
    normalized["source_url"] = (combined.get("source_url") or "").strip()
    normalized["command"] = (combined.get("command") or "").strip()
    normalized["message"] = (combined.get("message") or combined.get("run_message") or "").strip()
    normalized["source_record_id"] = (combined.get("source_record_id") or "").strip()
    normalized["entity_id"] = _infer_entity_id(combined)

    for field in _INT_FIELDS:
        normalized[field] = _coerce_int_text(combined.get(field, ""))

    return normalized


def write_normalized_run_snapshot_csv(path: str | Path, row: Mapping[str, Any]) -> Path:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_run_snapshot_row(row)

    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=list(NORMALIZED_RUN_SNAPSHOT_FIELDS),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerow(normalized)
    return out_path


def write_legacy_metric_value_snapshot(path: str | Path, row: Mapping[str, Any]) -> Path:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_run_snapshot_row(row)

    lines = ["metric,value"]
    for field in NORMALIZED_RUN_SNAPSHOT_FIELDS:
        lines.append(f"{field},{normalized.get(field, '')}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def normalize_run_snapshot_file(
    input_path: str | Path,
    output_path: str | Path,
    *,
    defaults: Mapping[str, Any] | None = None,
    legacy_output_path: str | Path | None = None,
) -> tuple[Path, Path | None, dict[str, str]]:
    raw = load_run_snapshot_file(input_path)
    normalized = normalize_run_snapshot_row(raw, defaults=defaults)
    normalized_path = write_normalized_run_snapshot_csv(output_path, normalized)

    legacy_path: Path | None = None
    if legacy_output_path:
        legacy_path = write_legacy_metric_value_snapshot(legacy_output_path, normalized)

    return normalized_path, legacy_path, normalized

