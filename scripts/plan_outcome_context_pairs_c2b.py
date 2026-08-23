#!/usr/bin/env python3
"""Materialize the bounded real C2B ES* strict pre/post discovery universe.

Rows are internal L0 discovery pairs only. They make no association, causal,
effect, ranking, publication, merit, blame, or corruption claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import quote

import plan_outcome_context_pairs as shared


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "etl/data/manual/outcome_links/planner_scope_c2b_v1.json"
DEFAULT_SCHEMA = REPO_ROOT / "etl/load/sqlite_schema.sql"
DEFAULT_OUT_DB = REPO_ROOT / "etl/data/staging/outcome-context-pair-plan-c2b-v1.db"
DEFAULT_REPORT = REPO_ROOT / "etl/data/staging/outcome-context-pair-plan-c2b-v1-report.json"
DEFAULT_MANIFEST = REPO_ROOT / "etl/data/staging/outcome-context-pair-plan-c2b-v1-manifest.json"
PLAN_CONTRACT = "outcome_context_sparse_pair_planner_c2b_v1"
REPORT_SCHEMA = "outcome_context_pair_plan_c2b_report_v1"
MANIFEST_SCHEMA = "outcome_context_pair_plan_c2b_manifest_v1"


def validate_config(config: dict[str, Any]) -> None:
    if set(config) != {
        "format_version",
        "scope_revision",
        "planner_contract_version",
        "checkpoint_contract_version",
        "contract_date",
        "canonicalization",
        "policy",
        "sources",
        "query_contract",
        "expected",
    }:
        raise RuntimeError("C2B planner config root keys do not match contract")
    if config["format_version"] != "outcome_context_pair_planner_scope_c2b_v1":
        raise RuntimeError("unsupported C2B config format")
    if config["planner_contract_version"] != PLAN_CONTRACT:
        raise RuntimeError("unsupported C2B planner contract")
    required_policy = {
        "real_data_only": True,
        "official_public_identities_retained": True,
        "evidence_level": "L0",
        "link_state": "internal_discovery_pair",
        "association_assessment": "not_assessed",
        "causal_assessment": "not_assessed",
        "effect_estimate_state": "not_computed",
        "political_merit_or_blame": "not_assessed",
        "corruption_assessment": "not_assessed",
        "ranking_eligible": False,
        "publication_eligible": False,
    }
    if config["policy"] != required_policy:
        raise RuntimeError("C2B policy is not the mandatory internal L0 zero-claim policy")
    if config["sources"]["indicators"]["geography_code"] != "ES*":
        raise RuntimeError("C2B geography selector must be the pinned ES* cohort")
    query = config["query_contract"]
    for name in ("actions", "members", "series", "points"):
        sql = query[f"{name}_keyset_sql_utf8"]
        if " OFFSET " in f" {sql.upper()} ":
            raise RuntimeError(f"{name} query uses OFFSET")
        if shared.sha256_bytes(sql.encode("utf-8")) != query[f"{name}_keyset_sql_sha256"]:
            raise RuntimeError(f"{name} query hash mismatch")
    if " GLOB ? " not in f" {query['series_keyset_sql_utf8']} ":
        raise RuntimeError("C2B series query is not the pinned geography glob")
    if " GLOB ? " not in f" {query['points_keyset_sql_utf8']} ":
        raise RuntimeError("C2B point query is not the pinned geography glob")
    expected = config["expected"]
    if expected["dated_actions"] * expected["eligible_es_annual_series"] != expected[
        "selected_product"
    ]:
        raise RuntimeError("C2B selected product is internally inconsistent")
    if expected["eligible_pairs"] < 1_000_000:
        raise RuntimeError("C2B scope does not cross the physical million-pair gate")


def partition_component(value: Any) -> str:
    return quote(str(value), safe="-._~")


def materialize_pairs(
    *,
    target: sqlite3.Connection,
    pipeline_key: str,
    config: dict[str, Any],
    roots: dict[str, str],
    batch_size: int,
    limiter: shared.RunLimiter,
) -> bool:
    checkpoint = shared.ensure_checkpoint(
        target,
        pipeline_key=pipeline_key,
        stage="pairs",
        config=config,
        roots=roots,
    )
    if checkpoint["completed"]:
        return False
    last = shared.load_json_value(checkpoint["last_key_json"], "C2B pair checkpoint key")
    last_action, last_series = (last if last else [0, 0])
    written = checkpoint["rows_written"]
    chain = checkpoint["semantic_chain_sha256"]
    batches = checkpoint["batches_committed"]
    series_count = config["expected"]["eligible_es_annual_series"]
    total_products = config["expected"]["selected_product"]
    scanned = 0
    if last_action:
        scanned = (last_action - 1) * series_count + last_series
    while True:
        cursor = target.execute(
            """
            SELECT a.action_plan_pk,a.action_id,a.action_year,
                   a.source_id AS action_source_id,
                   s.series_plan_pk,s.canonical_key,s.dataset_code,
                   s.source_id AS indicator_source_id,s.country_code,
                   s.geography_code,s.observation_years_json
            FROM outcome_pair_plan_actions a
            CROSS JOIN outcome_pair_plan_series s
            WHERE a.pipeline_key=? AND s.pipeline_key=?
              AND (a.action_plan_pk>? OR
                   (a.action_plan_pk=? AND s.series_plan_pk>?))
            ORDER BY a.action_plan_pk,s.series_plan_pk
            LIMIT ?
            """,
            (pipeline_key, pipeline_key, last_action, last_action, last_series, batch_size),
        )
        inserts: list[Sequence[Any]] = []
        page_rows = 0
        for row in cursor:
            page_rows += 1
            years = shared.load_json_value(
                row["observation_years_json"], "C2B series years"
            )
            action_year = row["action_year"]
            pre = [year for year in years if year < action_year]
            post = [year for year in years if year > action_year]
            last_action, last_series = row["action_plan_pk"], row["series_plan_pk"]
            scanned += 1
            if not pre or not post:
                continue
            identity = {
                "identity_contract_version": "outcome_pair_plan_identity_v1",
                "action_id": row["action_id"],
                "indicator_series_canonical_key": row["canonical_key"],
                "eligibility": "strict_pre_and_strict_post_annual_observations",
            }
            identity_sha = shared.sha256_bytes(shared.canonical_bytes(identity))
            pair_id = f"vclc:outcome-pair-plan:{identity_sha[:24]}"
            pair_bucket = identity_sha[:2]
            base_partition = (
                f"action_source={partition_component(row['action_source_id'])}/"
                f"year={action_year}/"
                f"indicator_source={partition_component(row['indicator_source_id'])}/"
                f"dataset={partition_component(row['dataset_code'])}/"
                f"country={partition_component(row['country_code'])}/"
                f"geography={partition_component(row['geography_code'])}"
            )
            persisted = {
                "pair_plan_id": pair_id,
                "pipeline_key": pipeline_key,
                "base_partition_key": base_partition,
                "pair_bucket": pair_bucket,
                "partition_key": f"{base_partition}/bucket={pair_bucket}",
                "action_plan_pk": row["action_plan_pk"],
                "series_plan_pk": row["series_plan_pk"],
                "action_year": action_year,
                "dataset_code": row["dataset_code"],
                "strict_pre_latest_date": f"{max(pre):04d}-01-01",
                "strict_post_earliest_date": f"{min(post):04d}-01-01",
                "evidence_level": config["policy"]["evidence_level"],
                "link_state": config["policy"]["link_state"],
                "association_assessment": config["policy"]["association_assessment"],
                "causal_assessment": config["policy"]["causal_assessment"],
                "effect_estimate_state": config["policy"]["effect_estimate_state"],
                "political_merit_or_blame": config["policy"]["political_merit_or_blame"],
                "corruption_assessment": config["policy"]["corruption_assessment"],
                "ranking_eligible": int(config["policy"]["ranking_eligible"]),
                "publication_eligible": int(config["policy"]["publication_eligible"]),
            }
            row_sha = shared.persisted_row_sha256(
                "outcome_pair_plan_pair_row_v2", persisted
            )
            chain = shared.chain_add(chain, row_sha)
            written += 1
            inserts.append(
                tuple(persisted[key] for key in shared.PAIR_ROW_COLUMNS) + (row_sha,)
            )
        cursor.close()
        if page_rows == 0:
            if scanned != total_products:
                raise RuntimeError(
                    f"C2B pair product scan incomplete: {scanned} != {total_products}"
                )
            target.execute("BEGIN IMMEDIATE")
            target.execute(
                "UPDATE pipeline_keyset_checkpoints SET completed=1,updated_at=? "
                "WHERE pipeline_key=? AND stage='pairs' AND partition_key=''",
                (f"{config['contract_date']}T00:00:00Z", pipeline_key),
            )
            target.commit()
            return False
        batches += 1
        completed = scanned == total_products
        should_stop = shared.commit_checkpoint_batch(
            target,
            limiter=limiter,
            pipeline_key=pipeline_key,
            stage="pairs",
            inserts_sql=(
                "INSERT INTO outcome_pair_plan_pairs VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
            ),
            inserts=inserts,
            last_key=[last_action, last_series],
            rows_written=written,
            batches_committed=batches,
            semantic_chain=chain,
            completed=completed,
            updated_at=f"{config['contract_date']}T00:00:00Z",
            scanned_pairs=page_rows,
            eligible_pairs=len(inserts),
        )
        if completed:
            return False
        if should_stop:
            return True


def distribution_summary(
    connection: sqlite3.Connection,
    *,
    pipeline_key: str,
    column: str,
    contract_version: str,
) -> dict[str, Any]:
    hasher = hashlib.sha256()
    partition_count = 0
    row_count = 0
    minimum_rows: int | None = None
    maximum_rows = 0
    if column == "partition_key":
        cursor = connection.execute(
            "SELECT base_partition_key,pair_bucket,COUNT(*) "
            "FROM outcome_pair_plan_pairs WHERE pipeline_key=? "
            "GROUP BY base_partition_key,pair_bucket "
            "ORDER BY base_partition_key,pair_bucket",
            (pipeline_key,),
        )
        rows_iter = (
            (f"{base_partition_key}/bucket={pair_bucket}", rows)
            for base_partition_key, pair_bucket, rows in cursor
        )
    else:
        cursor = connection.execute(
            f"SELECT {column},COUNT(*) FROM outcome_pair_plan_pairs "
            f"WHERE pipeline_key=? GROUP BY {column} ORDER BY {column}",
            (pipeline_key,),
        )
        rows_iter = cursor
    for partition_key, rows in rows_iter:
        rows = int(rows)
        shared.stream_hash_add(
            hasher, {"partition_key": partition_key, "row_count": rows}
        )
        partition_count += 1
        row_count += rows
        minimum_rows = rows if minimum_rows is None else min(minimum_rows, rows)
        maximum_rows = max(maximum_rows, rows)
    cursor.close()
    return {
        "partition_count": partition_count,
        "row_count": row_count,
        "minimum_rows": minimum_rows or 0,
        "maximum_rows": maximum_rows,
        "distribution_root_sha256": shared.stream_root(
            contract_version, partition_count, hasher
        ),
    }


def output_summary(
    connection: sqlite3.Connection,
    *,
    pipeline_key: str,
    roots: dict[str, str],
    config: dict[str, Any],
) -> dict[str, Any]:
    counts = {
        "actions": connection.execute(
            "SELECT COUNT(*) FROM outcome_pair_plan_actions WHERE pipeline_key=?",
            (pipeline_key,),
        ).fetchone()[0],
        "series": connection.execute(
            "SELECT COUNT(*) FROM outcome_pair_plan_series WHERE pipeline_key=?",
            (pipeline_key,),
        ).fetchone()[0],
        "pairs": connection.execute(
            "SELECT COUNT(*) FROM outcome_pair_plan_pairs WHERE pipeline_key=?",
            (pipeline_key,),
        ).fetchone()[0],
    }
    base_distribution = distribution_summary(
        connection,
        pipeline_key=pipeline_key,
        column="base_partition_key",
        contract_version="outcome_pair_plan_base_partition_distribution_c2b_v1",
    )
    bucket_distribution = distribution_summary(
        connection,
        pipeline_key=pipeline_key,
        column="partition_key",
        contract_version="outcome_pair_plan_bucket_partition_distribution_c2b_v1",
    )
    checkpoints = []
    for row in connection.execute(
        "SELECT stage,last_key_json,rows_written,batches_committed,"
        "semantic_chain_sha256,completed FROM pipeline_keyset_checkpoints "
        "WHERE pipeline_key=? ORDER BY stage",
        (pipeline_key,),
    ):
        checkpoints.append(
            {
                "stage": row["stage"],
                "last_key": shared.load_json_value(
                    row["last_key_json"], "C2B checkpoint key"
                ),
                "rows_written": row["rows_written"],
                "batches_committed": row["batches_committed"],
                "semantic_chain_sha256": row["semantic_chain_sha256"],
                "completed": bool(row["completed"]),
            }
        )
    chains = {row["stage"]: row["semantic_chain_sha256"] for row in checkpoints}
    semantic_root = shared.sha256_bytes(
        shared.canonical_bytes(
            {
                "contract_version": "outcome_pair_plan_semantic_root_c2b_v1",
                **roots,
                "counts": counts,
                "base_partition_distribution": base_distribution,
                "bucket_partition_distribution": bucket_distribution,
                "stage_semantic_chains": chains,
                "policy": config["policy"],
            }
        )
    )
    return {
        "counts": counts,
        "base_partition_distribution": base_distribution,
        "bucket_partition_distribution": bucket_distribution,
        "checkpoints": checkpoints,
        "semantic_root_sha256": semantic_root,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--actions-db", type=Path)
    parser.add_argument("--indicators-db", type=Path)
    parser.add_argument("--out-db", type=Path, default=DEFAULT_OUT_DB)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--batch-size", type=int, default=25_000)
    parser.add_argument("--source-batch-size", type=int, default=25_000)
    parser.add_argument("--max-batches", type=int)
    parser.add_argument("--fault-before-checkpoint-batch", type=int)
    return parser.parse_args()


def run(args: argparse.Namespace) -> dict[str, Any]:
    started = time.monotonic()
    if args.batch_size < 1 or args.source_batch_size < 1:
        raise RuntimeError("batch sizes must be positive")
    if args.max_batches is not None and args.max_batches < 1:
        raise RuntimeError("max-batches must be positive")
    if args.fault_before_checkpoint_batch is not None and args.fault_before_checkpoint_batch < 1:
        raise RuntimeError("fault batch must be positive")
    config = shared.load_json(args.config)
    validate_config(config)
    if args.batch_size != config["expected"]["materialization_batch_size"]:
        raise RuntimeError("C2B materialization batch size differs from pinned contract")
    if args.source_batch_size != config["expected"]["source_batch_size"]:
        raise RuntimeError("C2B source batch size differs from pinned contract")
    config_sha = shared.sha256_bytes(shared.canonical_bytes(config))
    schema_block, schema_root = shared.extract_schema_block(args.schema)
    actions_path = args.actions_db or shared.resolve_config_path(
        config["sources"]["actions"]["path"]
    )
    indicators_path = args.indicators_db or shared.resolve_config_path(
        config["sources"]["indicators"]["path"]
    )
    action_fact, action_identity = shared.file_sha256_stable(actions_path)
    indicator_fact, indicator_identity = shared.file_sha256_stable(indicators_path)
    shared.check_source_fact(action_fact, config["sources"]["actions"], "actions")
    shared.check_source_fact(
        indicator_fact, config["sources"]["indicators"], "indicators"
    )
    with tempfile.TemporaryDirectory(prefix="vclc-outcome-pair-c2b-input-") as temp_dir:
        cache = shared.init_input_cache(Path(temp_dir) / "input-cache.db")
        actions = shared.open_source(actions_path)
        indicators = shared.open_source(indicators_path)
        try:
            inputs = shared.hydrate_real_inputs(
                config=config,
                actions=actions,
                indicators=indicators,
                cache=cache,
                source_batch_size=args.source_batch_size,
            )
            if actions.total_changes or indicators.total_changes:
                raise RuntimeError("read-only C2B source connection reports writes")
            actions.commit()
            indicators.commit()
        finally:
            actions.close()
            indicators.close()
        shared.assert_source_stable(actions_path, action_identity)
        shared.assert_source_stable(indicators_path, indicator_identity)
        geographies = cache.execute(
            "SELECT COUNT(DISTINCT geography_code) FROM series_inputs"
        ).fetchone()[0]
        datasets = cache.execute(
            "SELECT COUNT(DISTINCT dataset_code) FROM series_inputs"
        ).fetchone()[0]
        if geographies != config["expected"]["geographies"]:
            raise RuntimeError(f"C2B geography count mismatch: {geographies}")
        if datasets != config["expected"]["datasets"]:
            raise RuntimeError(f"C2B dataset count mismatch: {datasets}")
        roots = {
            "config_sha256": config_sha,
            "input_root_sha256": inputs["input_root_sha256"],
            "schema_root_sha256": schema_root,
        }
        pipeline_digest = shared.sha256_bytes(
            shared.canonical_bytes(
                {
                    "contract_version": "outcome_pair_plan_pipeline_identity_c2b_v1",
                    **roots,
                }
            )
        )
        pipeline_key = f"vclc:outcome-pair-plan-c2b-pipeline:{pipeline_digest[:24]}"
        target_existed = args.out_db.exists() and args.out_db.stat().st_size > 0
        target = shared.open_target(args.out_db, schema_block, roots)
        limiter = shared.RunLimiter(args.max_batches, args.fault_before_checkpoint_batch)
        try:
            existing_stage_states = {
                row["stage"]: bool(row["completed"])
                for row in target.execute(
                    "SELECT stage,completed FROM pipeline_keyset_checkpoints "
                    "WHERE pipeline_key=? AND partition_key=''",
                    (pipeline_key,),
                )
            }
            pre_complete = all(
                existing_stage_states.get(stage, False) for stage in shared.STAGES
            )
            interrupted = shared.materialize_actions(
                target=target,
                cache=cache,
                pipeline_key=pipeline_key,
                config=config,
                roots=roots,
                batch_size=args.batch_size,
                limiter=limiter,
            )
            if not interrupted:
                interrupted = shared.materialize_series(
                    target=target,
                    cache=cache,
                    pipeline_key=pipeline_key,
                    config=config,
                    roots=roots,
                    batch_size=args.batch_size,
                    limiter=limiter,
                )
            if not interrupted:
                interrupted = materialize_pairs(
                    target=target,
                    pipeline_key=pipeline_key,
                    config=config,
                    roots=roots,
                    batch_size=args.batch_size,
                    limiter=limiter,
                )
            summary = output_summary(
                target, pipeline_key=pipeline_key, roots=roots, config=config
            )
            foreign_key_errors = sum(1 for _ in target.execute("PRAGMA foreign_key_check"))
        finally:
            target.close()
            cache.close()
    completed = len(summary["checkpoints"]) == 3 and all(
        row["completed"] for row in summary["checkpoints"]
    )
    expected = config["expected"]
    if completed:
        if summary["counts"] != {
            "actions": expected["dated_actions"],
            "series": expected["eligible_es_annual_series"],
            "pairs": expected["eligible_pairs"],
        }:
            raise RuntimeError(f"completed C2B plan count mismatch: {summary['counts']!r}")
        if summary["base_partition_distribution"] != expected[
            "base_partition_distribution"
        ]:
            raise RuntimeError("completed C2B base-partition closure mismatch")
        if summary["bucket_partition_distribution"] != expected[
            "bucket_partition_distribution"
        ]:
            raise RuntimeError("completed C2B bucket-partition closure mismatch")
    status = "interrupted" if interrupted else "passed"
    execution = "resumed_or_new"
    if completed and pre_complete and limiter.committed == 0:
        execution = "replayed_noop"
    elif target_existed:
        execution = "resumed"
    else:
        execution = "fresh"
    database_bytes = args.out_db.stat().st_size
    database_sha = sha256_file(args.out_db)
    manifest: dict[str, Any] | None = None
    if completed:
        manifest_payload = {
            "schema_version": MANIFEST_SCHEMA,
            "contract_date": config["contract_date"],
            "pipeline_key": pipeline_key,
            "roots": {
                **roots,
                "semantic_root_sha256": summary["semantic_root_sha256"],
                "input_component_roots": inputs["component_roots"],
            },
            "counts": {
                **summary["counts"],
                "member_votes": inputs["counts"]["members"],
                "official_names": inputs["counts"]["distinct_official_names"],
                "observations": inputs["counts"]["points"],
                "geographies": geographies,
            },
            "base_partition_distribution": summary["base_partition_distribution"],
            "bucket_partition_distribution": summary["bucket_partition_distribution"],
            "policy": config["policy"],
            "shards": [
                {
                    "shard_id": "sqlite-00000",
                    "logical_name": args.out_db.name,
                    "bytes": database_bytes,
                    "sha256": database_sha,
                    "pair_rows": summary["counts"]["pairs"],
                }
            ],
            "local_origin_state": "immutable_content_manifest_only_not_durable_public_origin",
        }
        manifest = {
            **manifest_payload,
            "manifest_root_sha256": shared.sha256_bytes(
                shared.canonical_bytes(manifest_payload)
            ),
        }
        shared.atomic_write_json(args.manifest_out, manifest)
    elapsed = time.monotonic() - started
    report = {
        "schema_version": REPORT_SCHEMA,
        "status": status,
        "execution": execution,
        "pipeline_key": pipeline_key,
        "contract_date": config["contract_date"],
        "policy": config["policy"],
        "roots": {
            **roots,
            "semantic_root_sha256": summary["semantic_root_sha256"],
            "input_component_roots": inputs["component_roots"],
            "manifest_root_sha256": manifest["manifest_root_sha256"] if manifest else None,
        },
        "source_facts": {
            "actions": action_fact,
            "indicators": indicator_fact,
            "read_only_transactions": True,
            "non_empty_wal_rejected": True,
        },
        "source_counts": {
            **inputs["counts"],
            "geographies": geographies,
            "datasets": datasets,
        },
        "plan_counts": {
            **summary["counts"],
            "selected_product": expected["selected_product"],
            "global_unfiltered_product": expected["global_unfiltered_product"],
            "base_partitions": summary["base_partition_distribution"]["partition_count"],
            "bucket_partitions": summary["bucket_partition_distribution"]["partition_count"],
            "max_bucket_partition_rows": summary["bucket_partition_distribution"]["maximum_rows"],
        },
        "base_partition_distribution": summary["base_partition_distribution"],
        "bucket_partition_distribution": summary["bucket_partition_distribution"],
        "checkpoints": summary["checkpoints"],
        "integrity": {
            "foreign_key_errors": foreign_key_errors,
            "config_input_schema_roots_pin_resume": True,
            "batch_rows_and_checkpoint_atomic": True,
            "streaming_keyset_no_offset": True,
            "bounded_memory_distribution_roots": True,
            "full_geography_partition_key": True,
            "official_names_source_resolvable": inputs["counts"]["distinct_official_names"],
            "member_votes_source_resolvable": inputs["counts"]["members"],
            "single_shard_manifest_sha256": database_sha if completed else None,
        },
        "performance": {
            "batch_size": args.batch_size,
            "source_batch_size": args.source_batch_size,
            "batches_attempted_this_run": limiter.attempted,
            "batches_committed_this_run": limiter.committed,
            "elapsed_seconds": round(elapsed, 6),
            "max_rss_bytes": shared.max_rss_bytes(),
            "eligible_pairs_processed_this_run": limiter.eligible_pairs_processed,
            "scanned_pairs_processed_this_run": limiter.scanned_pairs_processed,
            "eligible_pairs_per_second": round(
                limiter.eligible_pairs_processed / elapsed, 3
            ) if limiter.eligible_pairs_processed else None,
            "scanned_pairs_per_second": round(
                limiter.scanned_pairs_processed / elapsed, 3
            ) if limiter.scanned_pairs_processed else None,
            "compute_cost_proxy_seconds_per_1000_eligible_pairs": round(
                elapsed / (limiter.eligible_pairs_processed / 1000), 6
            ) if limiter.eligible_pairs_processed else None,
            "output_database_bytes": database_bytes,
            "retries": 0,
            "dead_letters": 0,
        },
        "artifacts": {
            "database": shared.repo_path(args.out_db),
            "report": shared.repo_path(args.report_out),
            "manifest": shared.repo_path(args.manifest_out) if completed else None,
        },
        "unresolved_gates": {
            "durable_remote_origin": False,
            "public_release": False,
            "publication_eligible_rows": 0,
        },
    }
    shared.atomic_write_json(args.report_out, report)
    return report


def main() -> int:
    args = parse_args()
    try:
        report = run(args)
    except Exception as exc:
        failure = {
            "schema_version": REPORT_SCHEMA,
            "status": "failed",
            "error_code": "c2b_pair_plan_failed_fail_closed",
            "error_type": type(exc).__name__,
            "success_report_invalidated": True,
            "publication_eligible_rows": 0,
        }
        shared.atomic_write_json(args.report_out, failure)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
