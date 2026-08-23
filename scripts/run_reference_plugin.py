#!/usr/bin/env python3
"""Run the real Congreso reference plugin through hooks and the standard SQLite loader."""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import closing
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db, seed_dimensions, seed_sources
from etl.politicos_es.pipeline import ingest_one_source
from publicdata_core.plugins import PluginContext, load_plugin

DEFAULT_MANIFEST = Path("plugins/congreso_representatives/plugin.json")
DEFAULT_ONTOLOGY = Path("docs/data-model/core-ontology-v1.json")


def run_reference_plugin(
    *,
    manifest_path: Path,
    ontology_path: Path,
    db_path: Path,
    raw_dir: Path,
    snapshot_date: str,
    network_enabled: bool = False,
    repeat: int = 1,
) -> dict[str, Any]:
    if repeat < 1:
        raise ValueError("repeat must be at least 1")
    loaded_plugin = load_plugin(
        manifest_path,
        repo_root=REPO_ROOT,
        ontology_path=ontology_path,
        verify_capture_bytes=True,
    )
    plugin = loaded_plugin.instance
    ctx = PluginContext(
        repo_root=REPO_ROOT,
        raw_dir=raw_dir,
        snapshot_date=snapshot_date,
        timeout_seconds=int(loaded_plugin.manifest["runtime"]["timeout_seconds"]),
        strict_network=True,
        network_enabled=network_enabled,
    )
    registration = dict(plugin.register())
    config_validation = dict(plugin.validate_config(ctx))
    work_items = tuple(plugin.discover(ctx))
    if len(work_items) != 1:
        raise RuntimeError(
            f"reference plugin expected one work item, got {len(work_items)}"
        )
    item = work_items[0]
    artifact = plugin.acquire(item, ctx)
    records = tuple(plugin.parse(artifact, ctx))
    fact_batch = plugin.normalize(records, ctx)
    hook_validation = dict(plugin.validate(fact_batch))
    checkpoint = dict(plugin.checkpoint(item, fact_batch))

    ingest_results: list[dict[str, Any]] = []
    with closing(open_db(db_path)) as conn:
        apply_schema(conn, DEFAULT_SCHEMA)
        seed_sources(conn)
        seed_dimensions(conn)
        for replay_number in range(1, repeat + 1):
            connector = plugin.build_connector(ctx)
            seen, loaded, note = ingest_one_source(
                conn=conn,
                connector=connector,
                raw_dir=raw_dir,
                timeout=ctx.timeout_seconds,
                from_file=None,
                url_override=None,
                snapshot_date=snapshot_date,
                strict_network=True,
            )
            ingest_results.append(
                {
                    "replay_number": replay_number,
                    "records_seen": seen,
                    "records_loaded": loaded,
                    "note": note,
                }
            )
        source_id = str(loaded_plugin.manifest["sources"][0]["source_id"])
        counts = {
            "source_records": int(
                conn.execute(
                    "SELECT COUNT(*) FROM source_records WHERE source_id = ?",
                    (source_id,),
                ).fetchone()[0]
            ),
            "mandates": int(
                conn.execute(
                    "SELECT COUNT(*) FROM mandates WHERE source_id = ?",
                    (source_id,),
                ).fetchone()[0]
            ),
            "persons_linked": int(
                conn.execute(
                    "SELECT COUNT(DISTINCT person_id) FROM mandates WHERE source_id = ?",
                    (source_id,),
                ).fetchone()[0]
            ),
            "ingestion_runs": int(
                conn.execute(
                    "SELECT COUNT(*) FROM ingestion_runs WHERE source_id = ?",
                    (source_id,),
                ).fetchone()[0]
            ),
        }
        source_urls = [
            str(row[0])
            for row in conn.execute(
                "SELECT DISTINCT source_url FROM run_fetches WHERE source_id = ? ORDER BY source_url",
                (source_id,),
            ).fetchall()
        ]
        foreign_key_failures = len(conn.execute("PRAGMA foreign_key_check").fetchall())

    cleanup = dict(plugin.cleanup(ctx))
    idempotent = (
        counts["source_records"] == fact_batch.source_records_loaded
        and counts["mandates"] == fact_batch.source_records_loaded
        and counts["persons_linked"] == fact_batch.source_records_loaded
    )
    return {
        "schema_version": "reference_plugin_run_v1",
        "status": "ok" if idempotent and foreign_key_failures == 0 else "error",
        "plugin": {
            "plugin_id": loaded_plugin.manifest["plugin_id"],
            "version": loaded_plugin.manifest["version"],
            "manifest_path": str(manifest_path),
            "registration": registration,
        },
        "policy": {
            "official_records_only": True,
            "synthetic_or_mock": False,
            "official_public_domain_personal_information_retained": True,
            "network_enabled": network_enabled,
        },
        "capture": {
            "source_id": artifact.source_id,
            "source_url": artifact.source_url,
            "content_sha256": artifact.content_sha256,
            "bytes": artifact.bytes,
            "note": artifact.note,
        },
        "hooks": {
            "config_validation": config_validation,
            "work_items": len(work_items),
            "records_parsed": len(records),
            "fact_batch_rows": fact_batch.source_records_loaded,
            "logical_sha256": fact_batch.logical_sha256,
            "validation": hook_validation,
            "checkpoint": checkpoint,
            "cleanup": cleanup,
        },
        "sqlite": {
            "db_file": db_path.name,
            "replays": ingest_results,
            "counts": counts,
            "source_urls": source_urls,
            "foreign_key_failures": foreign_key_failures,
            "idempotent": idempotent,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--ontology", default=str(DEFAULT_ONTOLOGY))
    parser.add_argument("--db", required=True)
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--snapshot-date", required=True)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument(
        "--network",
        action="store_true",
        help="Use the live official endpoint instead of the registered official capture",
    )
    parser.add_argument("--out", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_reference_plugin(
        manifest_path=Path(args.manifest),
        ontology_path=Path(args.ontology),
        db_path=Path(args.db),
        raw_dir=Path(args.raw_dir),
        snapshot_date=args.snapshot_date,
        network_enabled=args.network,
        repeat=args.repeat,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        output_path = Path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
