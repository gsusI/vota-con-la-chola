#!/usr/bin/env python3
"""Audit scale readiness using only captured records from official sources."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
DISALLOWED_HOSTS = {"example.com", "example.org", "localhost", "127.0.0.1", "0.0.0.0"}


class ReadinessError(RuntimeError):
    """Raised when evidence cannot support a real-data readiness claim."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(file_path: Path, chunk_bytes: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        while chunk := handle.read(chunk_bytes):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(file_path: Path) -> dict[str, Any]:
    if not file_path.is_file():
        raise ReadinessError(f"missing evidence file: {file_path.relative_to(REPO_ROOT)}")
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReadinessError(f"invalid JSON evidence: {file_path.relative_to(REPO_ROOT)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReadinessError(f"evidence must be a JSON object: {file_path.relative_to(REPO_ROOT)}")
    return payload


def repo_path(value: str) -> Path:
    candidate = (REPO_ROOT / value).resolve()
    try:
        candidate.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise ReadinessError(f"evidence path escapes repository: {value}") from exc
    return candidate


def evidence_reference(file_path: Path) -> dict[str, Any]:
    return {
        "path": file_path.relative_to(REPO_ROOT).as_posix(),
        "bytes": file_path.stat().st_size,
        "sha256": sha256_file(file_path),
    }


def reject_disallowed_evidence(value: Any, location: str = "root") -> None:
    """Reject metadata markers that describe generated or loopback-only evidence."""
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered.endswith("_capacity_only") and child is True:
                raise ReadinessError(f"generated-only evidence marker at {location}.{key}")
            if lowered in {"controlled_local_http_only", "fixture_only", "mock_only"} and child is True:
                raise ReadinessError(f"non-official evidence marker at {location}.{key}")
            reject_disallowed_evidence(child, f"{location}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            reject_disallowed_evidence(child, f"{location}[{index}]")
        return
    if isinstance(value, str):
        lowered = value.lower()
        if any(token in lowered for token in ("example.org", "example.com", "localhost", "127.0.0.1")):
            raise ReadinessError(f"non-official endpoint at {location}")


def checks_pass(payload: dict[str, Any], *, require_status: bool) -> bool:
    checks = payload.get("checks")
    if not isinstance(checks, dict) or not checks or not all(value is True for value in checks.values()):
        return False
    return not require_status or payload.get("status") == "ok"


def official_host(url: str, allowed_hosts: set[str]) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host or host in DISALLOWED_HOSTS:
        raise ReadinessError(f"source URL is not an official HTTP origin: {url}")
    if host not in allowed_hosts:
        raise ReadinessError(f"source URL host is outside registry allowlist: {host}")
    return host


def manifest_files(manifest: dict[str, Any]) -> Iterable[dict[str, Any]]:
    partitions = manifest.get("partitions")
    if not isinstance(partitions, list):
        raise ReadinessError("semantic manifest has no partitions array")
    for partition in partitions:
        if not isinstance(partition, dict) or not isinstance(partition.get("files"), list):
            raise ReadinessError("semantic manifest partition has no files array")
        yield from partition["files"]


def validate_semantic_files(
    root: Path,
    manifest: dict[str, Any],
    *,
    allowed_source_ids: set[str],
    allowed_hosts: set[str],
    inspect_provenance: bool,
) -> dict[str, Any]:
    try:
        import pyarrow.parquet as parquet
    except ImportError as exc:
        raise ReadinessError("pyarrow is required for full real-row validation") from exc

    if not root.is_dir():
        raise ReadinessError(f"missing semantic artifact root: {root.relative_to(REPO_ROOT)}")

    declared_paths: set[str] = set()
    observed_sources: set[str] = set()
    observed_hosts: set[str] = set()
    total_rows = 0
    source_url_https_rows = 0
    total_bytes = 0
    total_files = 0

    for file_spec in manifest_files(manifest):
        relative = str(file_spec.get("path") or "")
        if not relative or relative in declared_paths:
            raise ReadinessError(f"missing or duplicate semantic file path: {relative!r}")
        declared_paths.add(relative)
        file_path = (root / relative).resolve()
        try:
            file_path.relative_to(root.resolve())
        except ValueError as exc:
            raise ReadinessError(f"semantic file escapes artifact root: {relative}") from exc
        if not file_path.is_file():
            raise ReadinessError(f"missing semantic file: {file_path.relative_to(REPO_ROOT)}")
        observed_bytes = file_path.stat().st_size
        if observed_bytes != int(file_spec.get("bytes", -1)):
            raise ReadinessError(f"semantic file byte mismatch: {relative}")
        if sha256_file(file_path) != file_spec.get("sha256"):
            raise ReadinessError(f"semantic file checksum mismatch: {relative}")

        parquet_file = parquet.ParquetFile(file_path)
        file_rows = parquet_file.metadata.num_rows
        if file_rows != int(file_spec.get("rows", -1)):
            raise ReadinessError(f"semantic file row mismatch: {relative}")
        total_rows += file_rows
        total_bytes += observed_bytes
        total_files += 1

        if not inspect_provenance:
            continue
        names = set(parquet_file.schema_arrow.names)
        if not {"source_id", "source_url"}.issubset(names):
            raise ReadinessError(f"semantic file lacks provenance columns: {relative}")
        for batch in parquet_file.iter_batches(columns=["source_id", "source_url"], batch_size=65_536):
            source_ids = batch.column(0).to_pylist()
            source_urls = batch.column(1).to_pylist()
            for source_id, source_url in zip(source_ids, source_urls, strict=True):
                if source_id not in allowed_source_ids:
                    raise ReadinessError(f"unregistered source_id {source_id!r} in {relative}")
                if not isinstance(source_url, str) or not source_url:
                    raise ReadinessError(f"missing source_url in {relative}")
                observed_sources.add(source_id)
                observed_hosts.add(official_host(source_url, allowed_hosts))
                if urlparse(source_url).scheme == "https":
                    source_url_https_rows += 1

    actual_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*.parquet")
        if path.is_file()
    }
    if actual_paths != declared_paths:
        missing = sorted(declared_paths - actual_paths)[:3]
        extra = sorted(actual_paths - declared_paths)[:3]
        raise ReadinessError(f"semantic file inventory mismatch; missing={missing}, extra={extra}")

    totals = manifest.get("totals") or {}
    expected = {
        "rows": total_rows,
        "files": total_files,
        "parquet_bytes": total_bytes,
    }
    for key, observed in expected.items():
        if int(totals.get(key, -1)) != observed:
            raise ReadinessError(f"semantic manifest total mismatch for {key}: {totals.get(key)} != {observed}")

    return {
        "rows": total_rows,
        "source_url_rows": total_rows,
        "source_url_https_rows": source_url_https_rows if inspect_provenance else total_rows,
        "files": total_files,
        "bytes": total_bytes,
        "source_ids": sorted(observed_sources),
        "official_hosts": sorted(observed_hosts),
    }


def validate_member_vote_shard(
    file_path: Path,
    entry: dict[str, Any],
    *,
    allowed_source_ids: set[str],
    allowed_hosts: set[str],
) -> tuple[int, int, int, set[str], set[str]]:
    if file_path.stat().st_size != int(entry.get("shard_bytes", -1)):
        raise ReadinessError(f"vote shard byte mismatch: {file_path.relative_to(REPO_ROOT)}")
    if sha256_file(file_path) != entry.get("shard_sha256"):
        raise ReadinessError(f"vote shard checksum mismatch: {file_path.relative_to(REPO_ROOT)}")
    try:
        with gzip.open(file_path, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ReadinessError(f"invalid vote shard: {file_path.relative_to(REPO_ROOT)}: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("member_votes"), list):
        raise ReadinessError(f"vote shard has invalid payload contract: {file_path.relative_to(REPO_ROOT)}")
    member_votes = payload["member_votes"]
    if len(member_votes) != int(entry.get("member_votes", -1)):
        raise ReadinessError(f"vote shard member count mismatch: {file_path.relative_to(REPO_ROOT)}")

    source_ids: set[str] = set()
    hosts: set[str] = set()
    source_url_rows = 0
    source_url_https_rows = 0
    event = payload.get("event") or {}
    event_source_id = event.get("source_id")
    if event_source_id:
        if event_source_id not in allowed_source_ids:
            raise ReadinessError(f"unregistered vote source_id {event_source_id!r}")
        source_ids.add(event_source_id)
    for member_vote in member_votes:
        source = member_vote.get("source") if isinstance(member_vote, dict) else None
        if not isinstance(source, dict):
            raise ReadinessError(f"vote member lacks source lineage: {file_path.relative_to(REPO_ROOT)}")
        source_id = source.get("source_id")
        source_url = source.get("source_url")
        source_record_id = source.get("source_record_id")
        if source_id not in allowed_source_ids or not source_record_id:
            raise ReadinessError(f"vote member has invalid source lineage: {file_path.relative_to(REPO_ROOT)}")
        source_ids.add(source_id)
        if source_url:
            hosts.add(official_host(str(source_url), allowed_hosts))
            source_url_rows += 1
            if urlparse(str(source_url)).scheme == "https":
                source_url_https_rows += 1
    return len(member_votes), source_url_rows, source_url_https_rows, source_ids, hosts


def validate_member_vote_corpus(
    root: Path,
    manifest: dict[str, Any],
    *,
    allowed_source_ids: set[str],
    allowed_hosts: set[str],
) -> dict[str, Any]:
    if not root.is_dir():
        raise ReadinessError(f"missing vote artifact root: {root.relative_to(REPO_ROOT)}")
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ReadinessError("vote manifest has no entries")
    rows = 0
    source_url_rows = 0
    source_url_https_rows = 0
    total_bytes = 0
    sources: set[str] = set()
    hosts: set[str] = set()
    declared: set[str] = set()
    for entry in entries:
        relative = str(entry.get("shard") or "")
        if not relative or relative in declared:
            raise ReadinessError(f"missing or duplicate vote shard path: {relative!r}")
        declared.add(relative)
        file_path = (root / relative).resolve()
        try:
            file_path.relative_to(root.resolve())
        except ValueError as exc:
            raise ReadinessError(f"vote shard escapes artifact root: {relative}") from exc
        if not file_path.is_file():
            raise ReadinessError(f"missing vote shard: {relative}")
        shard_rows, shard_source_url_rows, shard_https_rows, shard_sources, shard_hosts = validate_member_vote_shard(
            file_path,
            entry,
            allowed_source_ids=allowed_source_ids,
            allowed_hosts=allowed_hosts,
        )
        rows += shard_rows
        source_url_rows += shard_source_url_rows
        source_url_https_rows += shard_https_rows
        total_bytes += file_path.stat().st_size
        sources.update(shard_sources)
        hosts.update(shard_hosts)
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*.json.gz")
        if path.is_file()
    }
    if actual != declared:
        raise ReadinessError("vote shard file inventory does not match manifest")
    if rows != int(manifest.get("member_votes_total", -1)):
        raise ReadinessError("vote manifest row total does not match actual payloads")
    if total_bytes != int(manifest.get("shard_bytes_total", -1)):
        raise ReadinessError("vote manifest byte total does not match actual files")
    if len(entries) != int(manifest.get("events_total", -1)):
        raise ReadinessError("vote manifest event total does not match entries")
    lineage = manifest.get("lineage") or {}
    expected_source_url_rows = int(lineage.get("member_votes", -1)) - int(
        lineage.get("public_source_url_unresolved", -1)
    )
    if source_url_rows != expected_source_url_rows:
        raise ReadinessError("vote manifest public source URL total does not match actual payloads")
    return {
        "rows": rows,
        "source_url_rows": source_url_rows,
        "source_url_https_rows": source_url_https_rows,
        "files": len(entries),
        "bytes": total_bytes,
        "source_ids": sorted(sources),
        "official_hosts": sorted(hosts),
    }


def validate_replay(corpus: dict[str, Any], *, allowed_source_ids: set[str], allowed_hosts: set[str]) -> dict[str, Any]:
    incremental_manifest_path = repo_path(corpus["incremental_manifest"])
    incremental_validation_path = repo_path(corpus["incremental_validation"])
    replay_root = repo_path(corpus["replay_root"])
    incremental_manifest = load_json(incremental_manifest_path)
    incremental_validation = load_json(incremental_validation_path)
    reject_disallowed_evidence(incremental_manifest, corpus["incremental_manifest"])
    reject_disallowed_evidence(incremental_validation, corpus["incremental_validation"])
    if not checks_pass(incremental_manifest, require_status=False):
        raise ReadinessError(f"incremental manifest checks failed: {corpus['id']}")
    if not checks_pass(incremental_validation, require_status=True):
        raise ReadinessError(f"incremental validation checks failed: {corpus['id']}")
    observed = validate_semantic_files(
        replay_root,
        incremental_manifest,
        allowed_source_ids=allowed_source_ids,
        allowed_hosts=allowed_hosts,
        inspect_provenance=False,
    )
    contract = incremental_manifest.get("incremental_contract") or {}
    expected_partitions = int((incremental_manifest.get("totals") or {}).get("partitions", -1))
    replay_ok = (
        int(contract.get("partitions_reused", -1)) == expected_partitions
        and int(contract.get("partitions_rebuilt", -1)) == 0
        and int(contract.get("files_hardlinked", -1)) == observed["files"]
        and int(contract.get("files_copied", -1)) == 0
    )
    if not replay_ok:
        raise ReadinessError(f"unchanged replay contract failed: {corpus['id']}")
    return {
        "passed": True,
        "root": replay_root.relative_to(REPO_ROOT).as_posix(),
        "manifest": evidence_reference(incremental_manifest_path),
        "validation": evidence_reference(incremental_validation_path),
        "partitions_reused": expected_partitions,
        "files_hardlinked": observed["files"],
    }


def audit_corpus(corpus: dict[str, Any]) -> dict[str, Any]:
    corpus_id = str(corpus.get("id") or "")
    allowed_source_ids = set(corpus.get("official_source_ids") or [])
    allowed_hosts = set(corpus.get("official_hosts") or [])
    if not corpus_id or not allowed_source_ids or not allowed_hosts:
        raise ReadinessError(f"corpus registry entry lacks identity/origin allowlists: {corpus_id!r}")
    root = repo_path(corpus["root"])
    manifest_path = repo_path(corpus["manifest"])
    validation_path = repo_path(corpus["validation"])
    manifest = load_json(manifest_path)
    validation = load_json(validation_path)
    reject_disallowed_evidence(manifest, corpus["manifest"])
    reject_disallowed_evidence(validation, corpus["validation"])
    if not checks_pass(manifest, require_status=False):
        raise ReadinessError(f"manifest checks failed: {corpus_id}")
    if not checks_pass(validation, require_status=True):
        raise ReadinessError(f"validation checks failed: {corpus_id}")

    if corpus["kind"] == "parquet_manifest":
        observed = validate_semantic_files(
            root,
            manifest,
            allowed_source_ids=allowed_source_ids,
            allowed_hosts=allowed_hosts,
            inspect_provenance=True,
        )
    elif corpus["kind"] == "gzip_vote_shards":
        observed = validate_member_vote_corpus(
            root,
            manifest,
            allowed_source_ids=allowed_source_ids,
            allowed_hosts=allowed_hosts,
        )
    else:
        raise ReadinessError(f"unsupported corpus kind: {corpus['kind']}")

    validation_rows = int((validation.get("totals") or {}).get("rows", (validation.get("totals") or {}).get("member_votes", -1)))
    if validation_rows != observed["rows"]:
        raise ReadinessError(f"validation row total mismatch: {corpus_id}")
    min_rows = int(corpus["minimum_real_rows"])
    scale_gate_passed = observed["rows"] >= min_rows
    replay = None
    if all(corpus.get(key) for key in ("replay_root", "incremental_manifest", "incremental_validation")):
        replay = validate_replay(corpus, allowed_source_ids=allowed_source_ids, allowed_hosts=allowed_hosts)

    promotion_checks = {
        "minimum_real_rows": scale_gate_passed,
        "complete_public_source_url": observed["source_url_rows"] == observed["rows"],
        "https_source_urls_only": observed["source_url_https_rows"] == observed["source_url_rows"],
        "representative_scope": corpus.get("representative_scope") is True,
        "durable_public_origin": corpus.get("durable_public_origin") is True,
        "clean_room_restore": corpus.get("clean_room_restore") is True,
        "corrections_workflow": corpus.get("corrections_workflow") is True,
    }
    return {
        "id": corpus_id,
        "label": corpus["label"],
        "kind": corpus["kind"],
        "status": "validated_real_artifact",
        "real_official_data": True,
        "root": root.relative_to(REPO_ROOT).as_posix(),
        "rows": observed["rows"],
        "source_url_rows": observed["source_url_rows"],
        "source_url_https_rows": observed["source_url_https_rows"],
        "source_url_coverage": round(observed["source_url_rows"] / observed["rows"], 8) if observed["rows"] else 0.0,
        "files": observed["files"],
        "bytes": observed["bytes"],
        "minimum_real_rows": min_rows,
        "scale_gate_passed": scale_gate_passed,
        "source_ids": observed["source_ids"],
        "official_hosts": observed["official_hosts"],
        "manifest": evidence_reference(manifest_path),
        "validation": evidence_reference(validation_path),
        "unchanged_replay": replay,
        "promotion_checks": promotion_checks,
        "promotion_gate_passed": all(promotion_checks.values()),
        "limitations": list(corpus.get("limitations") or []),
        "next_gate": corpus["next_gate"],
    }


def build_report(registry_path: Path) -> dict[str, Any]:
    registry = load_json(registry_path)
    reject_disallowed_evidence(registry, registry_path.relative_to(REPO_ROOT).as_posix())
    registry_policy = registry.get("policy")
    required_true_policy = {
        "official_real_records_only",
        "synthetic_or_mock_records_forbidden",
        "every_row_requires_source_lineage",
        "official_public_domain_personal_information_retained",
        "classification_never_suppresses_public_domain_identity",
        "secrets_workstation_traces_and_non_public_data_forbidden",
        "promotion_requires_representative_scope",
        "promotion_requires_durable_public_origin",
        "promotion_requires_clean_room_restore",
    }
    if not isinstance(registry_policy, dict):
        raise ReadinessError("real corpus registry has no policy object")
    missing_policy = sorted(
        key for key in required_true_policy if registry_policy.get(key) is not True
    )
    if missing_policy:
        raise ReadinessError(
            "real corpus registry policy is missing mandatory true gates: "
            + ", ".join(missing_policy)
        )
    corpora = registry.get("corpora")
    if not isinstance(corpora, list) or not corpora:
        raise ReadinessError("real corpus registry has no corpora")
    audited = [audit_corpus(corpus) for corpus in corpora]
    gaps = registry.get("gaps") or []
    for gap in gaps:
        if gap.get("status") in {"complete", "promoted"}:
            raise ReadinessError(f"open gap cannot claim completion: {gap.get('id')}")
    million_lanes = sum(1 for corpus in audited if corpus["rows"] >= 1_000_000)
    promoted_lanes = sum(1 for corpus in audited if corpus["promotion_gate_passed"])
    foundation_ready = all(corpus["status"] == "validated_real_artifact" for corpus in audited)
    report = {
        "schema_version": "real-scale-readiness-v1",
        "generated_at": utc_now(),
        "status": "real_foundation_ready_scale_incomplete" if foundation_ready else "not_ready",
        "policy": {
            "official_real_records_only": True,
            "synthetic_or_mock_records_forbidden": True,
            "generated_test_records_count_toward_readiness": False,
            "loopback_network_results_count_toward_readiness": False,
            "official_public_domain_personal_information_retained": True,
            "classification_never_suppresses_public_domain_identity": True,
            "secrets_workstation_traces_and_non_public_data_forbidden": True,
            "promotion_requires_public_origin_and_clean_restore": True,
        },
        "registry": evidence_reference(registry_path),
        "summary": {
            "registered_real_corpora": len(audited),
            "validated_real_corpora": sum(1 for corpus in audited if corpus["real_official_data"]),
            "real_million_scale_lanes": million_lanes,
            "promoted_lanes": promoted_lanes,
            "open_gaps": len(gaps),
        },
        "foundation": {
            "ready": foundation_ready,
            "meaning": "Every registered current artifact is independently reconciled to official source provenance; societal-scale coverage remains open.",
        },
        "corpora": audited,
        "gaps": gaps,
    }
    if promoted_lanes == len(audited):
        report["status"] = "promoted_real_scale_ready"
    return report


def atomic_write_json(output_path: Path, payload: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{output_path.name}.", dir=output_path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, output_path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, help="Repository-relative real corpus registry JSON")
    parser.add_argument("--out", required=True, help="Repository-relative readiness report JSON")
    parser.add_argument("--enforce-foundation", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    registry_path = repo_path(args.registry)
    output_path = repo_path(args.out)
    try:
        report = build_report(registry_path)
        atomic_write_json(output_path, report)
    except ReadinessError as exc:
        print(f"scale readiness failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if args.enforce_foundation and not report["foundation"]["ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
