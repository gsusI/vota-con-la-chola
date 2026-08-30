#!/usr/bin/env python3
"""Audit immutable native-text or OCR generation activation and restore state."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_docs.generation_manifest import (
    GenerationManifestError,
    audit_generation_lifecycle,
)

DEFAULT_REPORT_ROOT = Path("docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence")
MANIFESTS = {
    "native_text": Path("etl/data/published/real-document-text-manifest-latest.jsonl"),
    "page_ocr": Path("etl/data/published/real-document-page-ocr-manifest-latest.jsonl"),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", choices=tuple(MANIFESTS))
    parser.add_argument("--manifest", default="")
    parser.add_argument("--report-out", default="")
    parser.add_argument("--full-shard-check", action="store_true")
    parser.add_argument("--full-state-check", action="store_true")
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    dataset = str(args.dataset)
    manifest = Path(args.manifest) if args.manifest else MANIFESTS[dataset]
    report_name = (
        "real-document-text-generation-audit.json"
        if dataset == "native_text"
        else "real-document-page-ocr-generation-audit.json"
    )
    report_out = (
        Path(args.report_out) if args.report_out else DEFAULT_REPORT_ROOT / report_name
    )
    try:
        report = audit_generation_lifecycle(
            manifest,
            dataset=dataset,
            full_shard_check=bool(args.full_shard_check),
            full_state_check=bool(args.full_state_check),
        )
        try:
            report["input"]["path"] = (
                manifest.resolve().relative_to(Path.cwd().resolve()).as_posix()
            )
        except ValueError:
            report["input"]["path"] = manifest.name
        atomic_write_json(report_out, report)
    except (GenerationManifestError, OSError, ValueError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    if args.enforce and report["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
