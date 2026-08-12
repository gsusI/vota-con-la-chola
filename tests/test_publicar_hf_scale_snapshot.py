from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.publicar_hf_scale_snapshot import (
    ScaleOriginError,
    artifact_contract_sha256,
    build_scale_origin_bundle,
    declared_artifact_files,
    publish_scale_origin_bundle,
    sha256_file,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_CAPTURE = REPO_ROOT / "etl/data/raw/samples/congreso_votaciones_sample.json"


class PublishHFScaleSnapshotTests(unittest.TestCase):
    def test_artifact_contract_ignores_release_state_but_not_data(self) -> None:
        manifest = {
            "generated_at": "2026-08-12T12:00:00Z",
            "source_evidence": {
                "registry": {"sha256": "r" * 64},
                "readiness": {"sha256": "q" * 64},
            },
            "corpora": [
                {
                    "id": "official_lane",
                    "kind": "parquet_manifest",
                    "rows": 1,
                    "files": 1,
                    "bytes": 10,
                    "promotion_gate_passed": False,
                    "source_ids": ["official_source"],
                    "official_hosts": ["official.example"],
                    "source_url_rows": 1,
                    "source_url_https_rows": 1,
                    "manifest": {"sha256": "m" * 64},
                    "validation": {"sha256": "v" * 64},
                    "extra_evidence": {},
                }
            ],
            "files": [
                {
                    "kind": "data",
                    "corpus_id": "official_lane",
                    "path": "corpora/official_lane/data/part.parquet",
                    "bytes": 10,
                    "sha256": "a" * 64,
                }
            ],
        }
        original = artifact_contract_sha256(manifest)
        release_state_changed = copy.deepcopy(manifest)
        release_state_changed["generated_at"] = "2026-08-13T12:00:00Z"
        release_state_changed["source_evidence"]["registry"]["sha256"] = "x" * 64
        release_state_changed["source_evidence"]["readiness"]["sha256"] = "y" * 64
        release_state_changed["corpora"][0]["promotion_gate_passed"] = True
        self.assertEqual(
            artifact_contract_sha256(release_state_changed),
            original,
        )

        data_changed = copy.deepcopy(manifest)
        data_changed["files"][0]["sha256"] = "b" * 64
        self.assertNotEqual(artifact_contract_sha256(data_changed), original)

    def test_publish_moves_latest_only_after_bundle_commit(self) -> None:
        calls: list[tuple[str, dict[str, object]]] = []

        class FakeApi:
            def create_commit(self, **kwargs: object) -> None:
                calls.append(("bundle", kwargs))

            def upload_file(self, **kwargs: object) -> None:
                calls.append(("latest", kwargs))

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            latest = root / "scale/latest.json"
            latest.parent.mkdir()
            latest.write_text("{}", encoding="utf-8")
            first = root / "scale/snapshots/2026-08-12/a/first.json"
            second = root / "scale/snapshots/2026-08-12/a/second.json"
            first.parent.mkdir(parents=True)
            first.write_text("{}", encoding="utf-8")
            second.write_text("{}", encoding="utf-8")
            with patch(
                "scripts.publicar_hf_scale_snapshot.UPLOAD_BATCH_FILES",
                1,
            ):
                publish_scale_origin_bundle(
                    api=FakeApi(),
                    dataset_repo="owner/data",
                    build_root=root,
                    snapshot_date="2026-08-12",
                    operation_factory=lambda **kwargs: SimpleNamespace(**kwargs),
                )

        self.assertEqual(
            [name for name, _kwargs in calls],
            ["bundle", "bundle", "latest"],
        )
        self.assertEqual(
            calls[0][1]["commit_message"],
            "Publish real scale origin snapshot 2026-08-12 (1/2)",
        )
        self.assertEqual(
            calls[0][1]["operations"][0].path_in_repo,
            "scale/snapshots/2026-08-12/a/first.json",
        )
        self.assertEqual(calls[2][1]["path_in_repo"], "scale/latest.json")

    def test_declared_vote_shards_use_manifest_checksums(self) -> None:
        declared = declared_artifact_files(
            corpus_kind="gzip_vote_shards",
            manifest={
                "entries": [
                    {
                        "shard": "snapshot/aa/item.json.gz",
                        "shard_bytes": 12,
                        "shard_sha256": "a" * 64,
                    }
                ]
            },
        )
        self.assertEqual(
            declared,
            [
                {
                    "path": "snapshot/aa/item.json.gz",
                    "bytes": 12,
                    "sha256": "a" * 64,
                }
            ],
        )

    def test_build_bundle_reconciles_registry_readiness_and_real_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            data_root.mkdir()
            part = data_root / "captured-source.json"
            shutil.copy2(OFFICIAL_CAPTURE, part)
            part_sha256 = sha256_file(part)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "partitions": [
                            {
                                "files": [
                                    {
                                        "path": part.name,
                                        "bytes": part.stat().st_size,
                                        "sha256": part_sha256,
                                    }
                                ]
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            validation_path = root / "validation.json"
            validation_path.write_text('{"status":"ok"}', encoding="utf-8")
            registry_path = root / "registry.json"
            registry_path.write_text(
                json.dumps(
                    {
                        "corpora": [
                            {
                                "id": "official_lane",
                                "kind": "parquet_manifest",
                                "root": "data",
                                "manifest": "manifest.json",
                                "validation": "validation.json",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            readiness_path = root / "readiness.json"
            readiness_path.write_text(
                json.dumps(
                    {
                        "status": "real_foundation_ready_scale_incomplete",
                        "generated_at": "2026-08-12T12:00:00Z",
                        "registry": {"sha256": sha256_file(registry_path)},
                        "corpora": [
                            {
                                "id": "official_lane",
                                "rows": 1_000_000,
                                "files": 1,
                                "bytes": part.stat().st_size,
                                "real_official_data": True,
                                "scale_gate_passed": True,
                                "promotion_gate_passed": False,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            build_root = root / "bundle"
            build_root.mkdir()
            report = build_scale_origin_bundle(
                repo_root=root,
                registry_path=registry_path,
                readiness_path=readiness_path,
                build_root=build_root,
                snapshot_date="2026-08-12",
            )

            self.assertEqual(report["status"], "ok")
            self.assertEqual(report["rows"], 1_000_000)
            self.assertEqual(report["data_files"], 1)
            self.assertEqual(report["million_scale_lanes"], 1)
            self.assertEqual(report["promoted_lanes"], 0)
            latest = json.loads(
                (build_root / "scale/latest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(latest["release_id"], report["manifest_sha256"])
            self.assertEqual(
                latest["artifact_contract_sha256"],
                report["artifact_contract_sha256"],
            )
            self.assertEqual(latest["snapshot_path"], report["snapshot_path"])
            self.assertEqual(
                latest["snapshot_path"],
                f"scale/snapshots/2026-08-12/{report['manifest_sha256']}",
            )
            staged = (
                build_root
                / latest["snapshot_path"]
                / "corpora/official_lane/data"
                / part.name
            )
            self.assertEqual(staged.read_bytes(), part.read_bytes())
            manifest = json.loads(
                (build_root / latest["snapshot_path"] / "manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(
                manifest["policy"][
                    "official_public_domain_personal_information_retained"
                ]
            )
            self.assertEqual(
                manifest["artifact_contract"]["sha256"],
                report["artifact_contract_sha256"],
            )

    def test_build_bundle_fails_closed_on_artifact_checksum_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            data_root.mkdir()
            part = data_root / "captured-source.json"
            shutil.copy2(OFFICIAL_CAPTURE, part)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "partitions": [
                            {
                                "files": [
                                    {
                                        "path": part.name,
                                        "bytes": part.stat().st_size,
                                        "sha256": "0" * 64,
                                    }
                                ]
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (root / "validation.json").write_text('{"status":"ok"}', encoding="utf-8")
            registry_path = root / "registry.json"
            registry_path.write_text(
                json.dumps(
                    {
                        "corpora": [
                            {
                                "id": "official_lane",
                                "kind": "parquet_manifest",
                                "root": "data",
                                "manifest": "manifest.json",
                                "validation": "validation.json",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            readiness_path = root / "readiness.json"
            readiness_path.write_text(
                json.dumps(
                    {
                        "status": "real_foundation_ready_scale_incomplete",
                        "generated_at": "2026-08-12T12:00:00Z",
                        "registry": {"sha256": sha256_file(registry_path)},
                        "corpora": [
                            {
                                "id": "official_lane",
                                "rows": 1,
                                "files": 1,
                                "bytes": part.stat().st_size,
                                "real_official_data": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            build_root = root / "bundle"
            build_root.mkdir()
            with self.assertRaisesRegex(ScaleOriginError, "checksum mismatch"):
                build_scale_origin_bundle(
                    repo_root=root,
                    registry_path=registry_path,
                    readiness_path=readiness_path,
                    build_root=build_root,
                    snapshot_date="2026-08-12",
                )


if __name__ == "__main__":
    unittest.main()
