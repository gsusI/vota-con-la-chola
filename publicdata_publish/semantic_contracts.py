"""Reusable typed contracts for semantic Parquet fact lanes."""

from __future__ import annotations

import hashlib
import json
import resource
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .sanitize import sanitize_url_for_public

MANIFEST_SCHEMA_VERSION = "semantic_partition_manifest_v1"

PRIVATE_TOKENS = (
    "/" + "Users" + "/",
    "/" + "home" + "/",
    "file" + ":///",
    "Bearer ",
    "hf_",
)


@dataclass(frozen=True)
class SemanticLaneContract:
    lane: str
    transformer_version: str
    schema: tuple[dict[str, Any], ...]
    id_column: str
    year_column: str

    @property
    def columns(self) -> tuple[str, ...]:
        return tuple(str(field["name"]) for field in self.schema)

    @property
    def schema_sha256(self) -> str:
        payload = json.dumps(
            self.schema,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def canonical_row_bytes(self, row: dict[str, Any]) -> bytes:
        def canonical(value: Any) -> Any:
            if isinstance(value, Decimal):
                return format(value, "f")
            if isinstance(value, dict):
                return {key: canonical(nested) for key, nested in value.items()}
            if isinstance(value, (list, tuple)):
                return [canonical(nested) for nested in value]
            return value

        return (
            json.dumps(
                [canonical(row[name]) for name in self.columns],
                ensure_ascii=True,
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
        )

    def arrow_schema(self):
        try:
            import pyarrow as pa  # type: ignore
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "pyarrow is required; install the project parquet extra"
            ) from exc
        type_map = {
            "float64": pa.float64(),
            "int64": pa.int64(),
            "decimal128_38_6": pa.decimal128(38, 6),
            # Parquet round-trips Arrow list children as ``element``. Naming the
            # child explicitly keeps independent schema equality exact.
            "list_string": pa.list_(pa.field("element", pa.string())),
            "string": pa.string(),
        }
        fields = [
            pa.field(
                str(field["name"]),
                type_map[str(field["type"])],
                nullable=bool(field["nullable"]),
            )
            for field in self.schema
        ]
        return pa.schema(fields).with_metadata(
            {
                b"lane": self.lane.encode("ascii"),
                b"manifest_schema_version": MANIFEST_SCHEMA_VERSION.encode("ascii"),
                b"transformer_version": self.transformer_version.encode("ascii"),
                b"schema_sha256": self.schema_sha256.encode("ascii"),
            }
        )


def peak_rss_mb() -> float:
    raw = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if sys.platform == "darwin":
        return round(raw / (1024 * 1024), 3)
    return round(raw / 1024, 3)


def public_http_url(raw_value: Any) -> str | None:
    raw = str(raw_value or "").strip()
    if not raw:
        return None
    safe = sanitize_url_for_public(raw)
    try:
        parsed = urlsplit(safe)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return safe


def safe_component(value: str) -> str:
    out = []
    for char in value.strip():
        if char.isalnum() or char in {"-", "_", "."}:
            out.append(char)
        else:
            out.append("_")
    cleaned = "".join(out).strip("._")
    return cleaned or "unknown"


def safe_child(root: Path, relative: str) -> Path | None:
    candidate = root / relative
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _string_values(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from _string_values(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            yield from _string_values(nested)


def private_token_findings(row: dict[str, Any]) -> int:
    return sum(
        1
        for value in row.values()
        for text in _string_values(value)
        for token in PRIVATE_TOKENS
        if token in text
    )


__all__ = [
    "MANIFEST_SCHEMA_VERSION",
    "PRIVATE_TOKENS",
    "SemanticLaneContract",
    "peak_rss_mb",
    "private_token_findings",
    "public_http_url",
    "safe_child",
    "safe_component",
    "sha256_file",
]
