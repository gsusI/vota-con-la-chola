#!/usr/bin/env python3
"""Build the immutable, paginated Evidence API v1 from current real exports."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

API_VERSION = "v1"
EXPORTER_VERSION = "1.0.0"
MAX_PAGE_SIZE = 500
DEFAULT_PAGE_SIZE = 250
COLLECTIONS = ("entities", "evidence-chains", "source-health", "question-results")
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE = (
    REPO_ROOT / "etl/data/published/accountability-evidence-api-latest.json"
)
DEFAULT_SOURCE_HEALTH = (
    REPO_ROOT / "ui/gh-pages-next/public/explorer-sources/data/status.json"
)
DEFAULT_ORIGIN = (
    REPO_ROOT
    / "docs/etl/sprints/REPRODUCIBILITY-20260819/evidence/live-scale-origin-parity.json"
)
DEFAULT_ATTESTATION = (
    REPO_ROOT
    / "docs/etl/sprints/REPRODUCIBILITY-20260819/evidence/live-signed-snapshot-verification.json"
)
DEFAULT_SCHEMA = REPO_ROOT / "docs/api/evidence-api-v1.schema.json"
DEFAULT_OUT = REPO_ROOT / "ui/gh-pages-next/public/api/v1"


def canonical_bytes(value: Any, *, pretty: bool = False) -> bytes:
    if pretty:
        text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    else:
        text = (
            json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            + "\n"
        )
    return text.encode("utf-8")


def sha256_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def atomic_write(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def repo_relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError as exc:
        raise ValueError(f"input must be inside the repository: {path}") from exc


def report_output_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return "<external-output>/index.json"


def encode_cursor(collection: str, release_id: str, after: str) -> str:
    payload = canonical_bytes(
        {"after": after, "collection": collection, "release": release_id, "version": 1},
        pretty=False,
    ).rstrip(b"\n")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> dict[str, Any]:
    padded = cursor + "=" * (-len(cursor) % 4)
    value = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    if not isinstance(value, dict):
        raise TypeError("cursor payload must be an object")
    return value


def source_artifact(path: Path, schema_version: str | None) -> dict[str, Any]:
    return {
        "path": repo_relative(path),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "schema_version": schema_version,
    }


def provenance(
    *,
    api_release_id: str,
    upstream_release_id: str,
    data_snapshot_date: str,
    artifact_sha256: str,
    source_collection: str,
    source_record_id: str,
) -> dict[str, Any]:
    return {
        "api_release_id": api_release_id,
        "upstream_scale_release_id": upstream_release_id,
        "data_snapshot_date": data_snapshot_date,
        "source_artifact_sha256": artifact_sha256,
        "source_collection": source_collection,
        "source_record_id": source_record_id,
        "official_real_record": True,
    }


def evidence_chain_id(sample: dict[str, Any]) -> str:
    natural_key = "\0".join(
        (
            str(sample.get("entry_id") or ""),
            str(sample.get("source_locator") or ""),
            str(sample.get("source_url") or ""),
        )
    )
    return "evidence-chain:" + hashlib.sha256(natural_key.encode("utf-8")).hexdigest()


def build_evidence_records(
    evidence: dict[str, Any],
    *,
    common: dict[str, Any],
    artifact_sha256: str,
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    chains: dict[str, dict[str, Any]] = {}
    answer_chain_ids: dict[str, list[str]] = {}
    for collection_name in ("actor_answers", "issue_answers"):
        for answer in evidence.get(collection_name) or []:
            answer_id = str(answer.get("answer_id") or "")
            for sample in answer.get("evidence_samples") or []:
                chain_id = evidence_chain_id(sample)
                answer_chain_ids.setdefault(answer_id, []).append(chain_id)
                if chain_id not in chains:
                    source_url = str(sample.get("source_url") or "")
                    source_locator = str(sample.get("source_locator") or "")
                    entry_id = str(sample.get("entry_id") or "")
                    chains[chain_id] = {
                        "id": chain_id,
                        "kind": "evidence_chain",
                        "entry": {
                            key: sample.get(key)
                            for key in (
                                "entry_id",
                                "entry_kind",
                                "event_date",
                                "title",
                                "summary",
                                "accountability_role",
                                "actor_kind",
                                "actor_label",
                                "issue_id",
                                "issue_label",
                            )
                        },
                        "evidence": {
                            "quote": sample.get("evidence_quote"),
                            "tier": sample.get("evidence_tier"),
                            "source_title": sample.get("source_title"),
                            "source_url": source_url or None,
                            "source_url_state": "known"
                            if source_url
                            else "not_available_in_current_export",
                            "source_locator": source_locator,
                        },
                        "chain": [
                            {"kind": "source", "ref": source_url or source_locator},
                            {"kind": "source_record", "ref": source_locator},
                            {"kind": "evidence", "ref": chain_id},
                            {"kind": "accountability_entry", "ref": entry_id},
                        ],
                        "answer_refs": [],
                        "provenance": provenance(
                            **common,
                            artifact_sha256=artifact_sha256,
                            source_collection=collection_name,
                            source_record_id=entry_id,
                        ),
                    }
                chains[chain_id]["answer_refs"].append(answer_id)
    for chain in chains.values():
        chain["answer_refs"] = sorted(set(chain["answer_refs"]))
    normalized_refs = {
        key: sorted(set(value)) for key, value in answer_chain_ids.items()
    }
    return sorted(chains.values(), key=lambda item: item["id"]), normalized_refs


def iter_entities(
    evidence: dict[str, Any],
    *,
    common: dict[str, Any],
    artifact_sha256: str,
) -> Iterator[dict[str, Any]]:
    for answer in evidence.get("actor_answers") or []:
        answer_id = str(answer.get("answer_id") or "")
        yield {
            "id": answer_id,
            "entity_type": "actor",
            "entity_kind": answer.get("actor_kind") or "unknown",
            "label": answer.get("actor_label"),
            "identifiers": answer.get("identity") or {},
            "routes": answer.get("routes") or {},
            "coverage": answer.get("coverage") or {},
            "freshness": answer.get("freshness") or {},
            "answer_status": answer.get("answer_status") or "unknown",
            "provenance": provenance(
                **common,
                artifact_sha256=artifact_sha256,
                source_collection="actor_answers",
                source_record_id=answer_id,
            ),
        }
    for answer in evidence.get("issue_answers") or []:
        answer_id = str(answer.get("answer_id") or "")
        yield {
            "id": answer_id,
            "entity_type": "issue",
            "entity_kind": "source_native_issue",
            "label": answer.get("issue_label"),
            "identifiers": {"issue_id": answer.get("issue_id")},
            "routes": answer.get("routes") or {},
            "coverage": answer.get("coverage") or {},
            "freshness": answer.get("freshness") or {},
            "answer_status": answer.get("answer_status") or "unknown",
            "provenance": provenance(
                **common,
                artifact_sha256=artifact_sha256,
                source_collection="issue_answers",
                source_record_id=answer_id,
            ),
        }


def iter_source_health(
    source_health: dict[str, Any],
    *,
    common: dict[str, Any],
    artifact_sha256: str,
) -> Iterator[dict[str, Any]]:
    for source in source_health.get("sources") or []:
        source_id = str(source.get("source_id") or "")
        yield {
            "id": f"source:{source_id}",
            "source": source,
            "provenance": provenance(
                **common,
                artifact_sha256=artifact_sha256,
                source_collection="sources",
                source_record_id=source_id,
            ),
        }


def iter_question_results(
    evidence: dict[str, Any],
    answer_chain_ids: dict[str, list[str]],
    *,
    common: dict[str, Any],
    artifact_sha256: str,
) -> Iterator[dict[str, Any]]:
    collections = (
        "actor_answers",
        "issue_answers",
        "actor_issue_refs",
        "gap_answers",
        "blocker_answers",
        "qa_answers",
    )
    for collection_name in collections:
        for answer in evidence.get(collection_name) or []:
            source_id = str(answer.get("answer_id") or "")
            result = dict(answer)
            result.pop("evidence_samples", None)
            yield {
                "id": f"question-result:{source_id}",
                "question_id": answer.get("question_id"),
                "answer_status": answer.get("answer_status") or "unknown",
                "evidence_chain_ids": answer_chain_ids.get(source_id, []),
                "result": result,
                "provenance": provenance(
                    **common,
                    artifact_sha256=artifact_sha256,
                    source_collection=collection_name,
                    source_record_id=source_id,
                ),
            }


def spool_chunks(
    records: Iterable[dict[str, Any]], page_size: int, temp_dir: Path
) -> tuple[list[Path], int]:
    database = temp_dir / "sort.sqlite"
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA synchronous=OFF")
        connection.execute(
            "CREATE TABLE items (sort_key TEXT PRIMARY KEY, body BLOB NOT NULL) WITHOUT ROWID"
        )
        for record in records:
            sort_key = str(record.get("id") or "")
            if not sort_key:
                raise ValueError("collection record id must not be empty")
            try:
                connection.execute(
                    "INSERT INTO items(sort_key, body) VALUES (?, ?)",
                    (sort_key, canonical_bytes(record)),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"duplicate collection record id: {sort_key}") from exc
        connection.commit()
        item_count = int(connection.execute("SELECT COUNT(*) FROM items").fetchone()[0])
        chunks: list[Path] = []
        cursor = connection.execute(
            "SELECT sort_key, body FROM items ORDER BY sort_key"
        )
        page_number = 0
        while True:
            rows = cursor.fetchmany(page_size)
            if not rows:
                break
            page_number += 1
            items = [json.loads(bytes(row[1]).decode("utf-8")) for row in rows]
            chunk_path = temp_dir / f"chunk-{page_number:08d}.json"
            chunk_path.write_bytes(canonical_bytes(items))
            chunks.append(chunk_path)
        return chunks, item_count
    finally:
        connection.close()


def build_collection(
    *,
    collection: str,
    records: Iterable[dict[str, Any]],
    release_dir: Path,
    release_id: str,
    page_size: int,
) -> dict[str, Any]:
    collection_dir = release_dir / collection
    pages_dir = collection_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{collection}-", dir=release_dir) as tmp:
        chunks, item_count = spool_chunks(records, page_size, Path(tmp))
        page_entries: list[dict[str, Any]] = []
        next_href: str | None = None
        for index in range(len(chunks) - 1, -1, -1):
            items = json.loads(chunks[index].read_text(encoding="utf-8"))
            first_key = str(items[0]["id"])
            last_key = str(items[-1]["id"])
            start_cursor = None
            if index > 0:
                previous_items = json.loads(
                    chunks[index - 1].read_text(encoding="utf-8")
                )
                start_cursor = encode_cursor(
                    collection, release_id, str(previous_items[-1]["id"])
                )
            has_next = next_href is not None
            end_cursor = encode_cursor(collection, release_id, last_key)
            page = {
                "schema_version": "evidence_api_collection_page_v1",
                "api_version": API_VERSION,
                "api_release_id": release_id,
                "collection": collection,
                "page_info": {
                    "page_number": index + 1,
                    "page_size": page_size,
                    "returned": len(items),
                    "has_next": has_next,
                    "start_cursor": start_cursor,
                    "end_cursor": end_cursor,
                    "next_cursor": end_cursor if has_next else None,
                    "next": next_href,
                },
                "items": items,
            }
            body = canonical_bytes(page)
            digest = sha256_bytes(body)
            filename = f"{index + 1:08d}-{digest}.json"
            path = pages_dir / filename
            path.write_bytes(body)
            href = f"/api/v1/releases/{release_id}/{collection}/pages/{filename}"
            page_entries.append(
                {
                    "page_number": index + 1,
                    "href": href,
                    "sha256": digest,
                    "bytes": len(body),
                    "item_count": len(items),
                    "first_key": first_key,
                    "last_key": last_key,
                }
            )
            next_href = href
    page_entries.sort(key=lambda item: item["page_number"])
    manifest = {
        "schema_version": "evidence_api_collection_manifest_v1",
        "api_version": API_VERSION,
        "api_release_id": release_id,
        "collection": collection,
        "sort": "id ascending, Unicode code-point order",
        "pagination": "opaque seek cursor; follow page_info.next",
        "item_count": item_count,
        "page_count": len(page_entries),
        "page_size": page_size,
        "first": page_entries[0]["href"] if page_entries else None,
        "pages": page_entries,
    }
    manifest_body = canonical_bytes(manifest, pretty=True)
    manifest_path = collection_dir / "manifest.json"
    manifest_path.write_bytes(manifest_body)
    return {
        "id": collection,
        "item_count": item_count,
        "page_count": len(page_entries),
        "page_size": page_size,
        "first": manifest["first"],
        "manifest": f"/api/v1/releases/{release_id}/{collection}/manifest.json",
        "manifest_sha256": sha256_bytes(manifest_body),
        "manifest_bytes": len(manifest_body),
    }


def same_tree(left: Path, right: Path) -> bool:
    left_files = sorted(
        path.relative_to(left) for path in left.rglob("*") if path.is_file()
    )
    right_files = sorted(
        path.relative_to(right) for path in right.rglob("*") if path.is_file()
    )
    if left_files != right_files:
        return False
    return all(
        (left / rel).read_bytes() == (right / rel).read_bytes() for rel in left_files
    )


def export_api(
    *,
    evidence_path: Path,
    source_health_path: Path,
    origin_path: Path,
    attestation_path: Path,
    schema_path: Path,
    out_root: Path,
    page_size: int,
) -> dict[str, Any]:
    if not 1 <= page_size <= MAX_PAGE_SIZE:
        raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
    evidence = read_json(evidence_path)
    source_health = read_json(source_health_path)
    origin = read_json(origin_path)
    attestation = read_json(attestation_path)
    schema = read_json(schema_path)
    origin_checks = origin.get("checks") or {}
    attestation_checks = attestation.get("checks") or {}
    release_id = str(origin_checks.get("latest_manifest_sha256") or "")
    if not origin.get("passed") or len(release_id) != 64:
        raise ValueError("scale origin verification is not passing")
    if not attestation.get("passed") or not attestation_checks.get(
        "signature_verified"
    ):
        raise ValueError("signed snapshot verification is not passing")
    if str(attestation_checks.get("manifest_sha256") or "") != release_id:
        raise ValueError("origin and attestation release IDs differ")
    if not attestation_checks.get("official_real_records_only"):
        raise ValueError("attestation does not require official real records")
    if attestation_checks.get("synthetic_or_mock_records") is not False:
        raise ValueError("attestation does not forbid generated records")
    if not attestation_checks.get(
        "official_public_domain_personal_information_retained"
    ):
        raise ValueError("attestation does not retain official public-domain identity")
    if (evidence.get("meta") or {}).get(
        "schema_version"
    ) != "accountability_evidence_api_v1":
        raise ValueError("unsupported accountability evidence input schema")
    if schema.get("$id") != "https://votaconlachola.org/api/v1/schema.json":
        raise ValueError("unexpected Evidence API schema $id")

    data_snapshot_date = str(
        evidence.get("snapshot_date")
        or (evidence.get("meta") or {}).get("snapshot_date")
        or ""
    )
    upstream_snapshot_date = str(
        origin.get("snapshot_date") or origin_checks.get("snapshot_date") or ""
    )
    artifacts = [
        source_artifact(
            evidence_path, (evidence.get("meta") or {}).get("schema_version")
        ),
        source_artifact(source_health_path, "source_status_v1"),
        source_artifact(origin_path, "scale_origin_live_verification_v1"),
        source_artifact(attestation_path, attestation.get("schema_version")),
        source_artifact(schema_path, "evidence_api_json_schema_v1"),
        source_artifact(Path(__file__), f"evidence_api_exporter_{EXPORTER_VERSION}"),
    ]
    artifacts.sort(key=lambda item: item["path"])
    build_fingerprint = {
        "api_version": API_VERSION,
        "exporter_version": EXPORTER_VERSION,
        "page_size": page_size,
        "upstream_scale_release_id": release_id,
        "data_snapshot_date": data_snapshot_date,
        "source_artifacts": [
            {"path": item["path"], "sha256": item["sha256"]} for item in artifacts
        ],
    }
    api_release_id = sha256_bytes(canonical_bytes(build_fingerprint))
    common = {
        "api_release_id": api_release_id,
        "upstream_release_id": release_id,
        "data_snapshot_date": data_snapshot_date,
    }
    evidence_sha = next(
        item["sha256"]
        for item in artifacts
        if item["path"] == repo_relative(evidence_path)
    )
    health_sha = next(
        item["sha256"]
        for item in artifacts
        if item["path"] == repo_relative(source_health_path)
    )
    evidence_records, answer_chain_ids = build_evidence_records(
        evidence,
        common=common,
        artifact_sha256=evidence_sha,
    )

    out_root.parent.mkdir(parents=True, exist_ok=True)
    staging_root = Path(
        tempfile.mkdtemp(prefix=".evidence-api-v1-", dir=out_root.parent)
    )
    try:
        release_dir = staging_root / "releases" / api_release_id
        release_dir.mkdir(parents=True)
        collection_entries = [
            build_collection(
                collection="entities",
                records=iter_entities(
                    evidence, common=common, artifact_sha256=evidence_sha
                ),
                release_dir=release_dir,
                release_id=api_release_id,
                page_size=page_size,
            ),
            build_collection(
                collection="evidence-chains",
                records=evidence_records,
                release_dir=release_dir,
                release_id=api_release_id,
                page_size=page_size,
            ),
            build_collection(
                collection="source-health",
                records=iter_source_health(
                    source_health, common=common, artifact_sha256=health_sha
                ),
                release_dir=release_dir,
                release_id=api_release_id,
                page_size=page_size,
            ),
            build_collection(
                collection="question-results",
                records=iter_question_results(
                    evidence,
                    answer_chain_ids,
                    common=common,
                    artifact_sha256=evidence_sha,
                ),
                release_dir=release_dir,
                release_id=api_release_id,
                page_size=page_size,
            ),
        ]
        policy = {
            "read_only": True,
            "official_real_records_only": True,
            "synthetic_or_mock_records": "forbidden",
            "public_domain_personal_information": "retained",
            "unknown_states_explicit": True,
        }
        release_index = {
            "schema_version": "evidence_api_release_index_v1",
            "api_version": API_VERSION,
            "api_release_id": api_release_id,
            "exporter_version": EXPORTER_VERSION,
            "data_snapshot_date": data_snapshot_date,
            "upstream_scale_release": {
                "release_id": release_id,
                "snapshot_date": upstream_snapshot_date,
                "schema_version": origin_checks.get("latest_schema_version"),
                "manifest": (origin.get("urls") or {}).get("manifest"),
                "attestation": (attestation.get("urls") or {}).get("attestation"),
                "signature_verified": True,
            },
            "source_artifacts": artifacts,
            "collections": collection_entries,
            "policy": policy,
            "compatibility": {
                "contract": "additive within v1",
                "breaking_changes": "new major path required",
                "deprecation_window_days": 180,
                "minimum_parallel_public_releases": 2,
                "pagination": "opaque seek cursor; offset pagination is not part of v1",
            },
            "links": {
                "self": f"/api/v1/releases/{api_release_id}/index.json",
                "current": "/api/v1/index.json",
                "schema": "/api/v1/schema.json",
                "documentation": "https://github.com/gsusI/vota-con-la-chola/blob/main/docs/api/evidence-api-v1.md",
            },
        }
        release_body = canonical_bytes(release_index, pretty=True)
        (release_dir / "index.json").write_bytes(release_body)
        release_index_sha = sha256_bytes(release_body)
        target_release = out_root / "releases" / api_release_id
        target_release.parent.mkdir(parents=True, exist_ok=True)
        if target_release.exists():
            if not same_tree(release_dir, target_release):
                raise ValueError(f"immutable API release collision: {api_release_id}")
        else:
            os.replace(release_dir, target_release)
        atomic_write(out_root / "schema.json", schema_path.read_bytes())
        pointer = {
            "schema_version": "evidence_api_current_pointer_v1",
            "api_version": API_VERSION,
            "current_release": {
                "api_release_id": api_release_id,
                "upstream_scale_release_id": release_id,
                "snapshot_date": upstream_snapshot_date,
                "href": f"/api/v1/releases/{api_release_id}/index.json",
                "sha256": release_index_sha,
            },
            "policy": policy,
            "links": {
                "schema": "/api/v1/schema.json",
                "documentation": "https://github.com/gsusI/vota-con-la-chola/blob/main/docs/api/evidence-api-v1.md",
            },
        }
        atomic_write(out_root / "index.json", canonical_bytes(pointer, pretty=True))
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)

    return {
        "schema_version": "evidence_api_export_report_v1",
        "status": "ok",
        "api_release_id": api_release_id,
        "upstream_scale_release_id": release_id,
        "data_snapshot_date": data_snapshot_date,
        "upstream_snapshot_date": upstream_snapshot_date,
        "page_size": page_size,
        "collections": {item["id"]: item for item in collection_entries},
        "release_index_sha256": release_index_sha,
        "pointer": report_output_path(out_root / "index.json"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-api", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--source-health", type=Path, default=DEFAULT_SOURCE_HEALTH)
    parser.add_argument("--origin-verification", type=Path, default=DEFAULT_ORIGIN)
    parser.add_argument(
        "--attestation-verification", type=Path, default=DEFAULT_ATTESTATION
    )
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = export_api(
        evidence_path=args.evidence_api,
        source_health_path=args.source_health,
        origin_path=args.origin_verification,
        attestation_path=args.attestation_verification,
        schema_path=args.schema,
        out_root=args.out_root,
        page_size=args.page_size,
    )
    body = canonical_bytes(report, pretty=True)
    if args.json_out:
        atomic_write(args.json_out, body)
    print(body.decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
