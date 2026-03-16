from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.prepare_fragment_measure_candidate_wave import prepare_wave


class TestPrepareFragmentMeasureCandidateWave(unittest.TestCase):
    def test_prepare_wave_limits_rows_and_writes_lf_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            queue_csv = root / "queue.csv"
            out_dir = root / "wave"

            with queue_csv.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.writer(fh, lineterminator="\n")
                writer.writerow(
                    [
                        "task_id",
                        "initiative_id",
                        "initiative_source_id",
                        "initiative_text_version_id",
                        "fragment_id",
                        "fragment_kind",
                        "fragment_label",
                        "priority",
                        "recommended_primary_vote_event_ids_json",
                        "evidence_bundle_dir",
                    ]
                )
                writer.writerow(
                    [
                        "pfrag:one",
                        "initiative-1",
                        "congreso_iniciativas",
                        "v1",
                        "pfrag:one",
                        "article",
                        "Articulo 1",
                        "100",
                        "[]",
                        "bundle/a",
                    ]
                )
                writer.writerow(
                    [
                        "pfrag:two",
                        "initiative-1",
                        "congreso_iniciativas",
                        "v1",
                        "pfrag:two",
                        "article",
                        "Articulo 2",
                        "99",
                        "[]",
                        "bundle/b",
                    ]
                )
                writer.writerow(
                    [
                        "pfrag:three",
                        "initiative-1",
                        "congreso_iniciativas",
                        "v1",
                        "pfrag:three",
                        "article",
                        "Articulo 3",
                        "98",
                        "[]",
                        "bundle/c",
                    ]
                )
                writer.writerow(
                    [
                        "pfrag:four",
                        "initiative-2",
                        "senado_iniciativas",
                        "v2",
                        "pfrag:four",
                        "disposition",
                        "Disposicion adicional",
                        "97",
                        "[]",
                        "bundle/d",
                    ]
                )

            summary = prepare_wave(
                queue_csv=queue_csv,
                out_dir=out_dir,
                limit=3,
                max_per_initiative=2,
                model="gpt-5.3-codex-spark",
                effort="high",
                max_parallel=5,
                schema_path="docs/etl/review_schemas/fragment_measure_candidate_output.schema.json",
            )

            self.assertEqual(summary["selected_rows"], 3)

            with (out_dir / "selected_queue.csv").open("r", encoding="utf-8", newline="") as fh:
                selected_rows = list(csv.DictReader(fh))
            self.assertEqual(len(selected_rows), 3)
            self.assertEqual([row["task_id"] for row in selected_rows], ["pfrag:one", "pfrag:two", "pfrag:four"])

            manifest_bytes = (out_dir / "manifest.csv").read_bytes()
            self.assertNotIn(b"\r\n", manifest_bytes)
            self.assertIn(b"pfrag-one", manifest_bytes)
            self.assertIn(b",high,", manifest_bytes)

            launch_text = (out_dir / "launch_batch.sh").read_text(encoding="utf-8")
            self.assertIn('model_reasoning_effort=\\"$effort\\"', launch_text)
            self.assertIn('MAX_PARALLEL="${MAX_PARALLEL:-5}"', launch_text)

            prompt_text = (out_dir / "prompts" / "pfrag-one.txt").read_text(encoding="utf-8")
            self.assertIn("Task id: `pfrag:one`", prompt_text)
            self.assertIn("Evidence bundle: `bundle/a`", prompt_text)


if __name__ == "__main__":
    unittest.main()
