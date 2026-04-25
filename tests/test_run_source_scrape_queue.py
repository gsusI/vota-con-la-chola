from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from etl.ops import source_scrape_queue as runner


def _validation(ok: bool, *, reason: str = "", run_id: int = 1, status: str = "ok", records_loaded: int = 1) -> dict[str, object]:
    return {
        "ok": ok,
        "reason": reason,
        "run_id": run_id,
        "status": status,
        "records_loaded": records_loaded,
    }


class RunSourceScrapeQueueTests(unittest.TestCase):
    def test_select_command_prefers_sample_for_from_file_mode(self) -> None:
        item = {
            "execution": {
                "preferred_mode": "from-file",
                "network_command": "python3 scripts/ingestar_politicos_es.py ingest --db <db> --source foo --strict-network",
                "sample_command": "python3 scripts/ingestar_politicos_es.py ingest --db <db> --source foo --from-file sample.json",
            }
        }
        command, chosen_mode = runner.select_command(item, mode="preferred")
        self.assertIn("--from-file sample.json", command)
        self.assertEqual(chosen_mode, "sample")

    def test_normalize_command_injects_db_and_snapshot_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "queue.db"
            tokens = runner._normalize_command(  # noqa: SLF001
                "python3 scripts/ingestar_politicos_es.py ingest --db <db> --source foo --strict-network",
                db_path=db_path,
                snapshot_date="2026-04-13",
            )
        self.assertIn(str(db_path), tokens)
        self.assertIn("--snapshot-date", tokens)
        self.assertIn("2026-04-13", tokens)

    def test_execute_queue_skips_manual_capture_when_only_repeatable_now(self) -> None:
        payload = {
            "items": [
                {
                    "source_id": "manual_one",
                    "rank": 1,
                    "execution": {
                        "repeatability_state": "manual_capture_required",
                        "preferred_mode": "manual_capture",
                        "network_command": "python3 nope",
                        "sample_command": "",
                    },
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "queue.db"
            summary = runner.execute_queue(
                db_path=db_path,
                queue_payload=payload,
                only_repeatable_now=True,
                dry_run=True,
            )
        self.assertEqual(summary["totals"]["selected_total"], 0)
        self.assertEqual(summary["totals"]["skipped_total"], 1)
        self.assertEqual(summary["results"][0]["status"], "skipped")

    @mock.patch("etl.ops.source_scrape_queue._validate_ingest_run")
    @mock.patch("etl.ops.source_scrape_queue.subprocess.run")
    def test_execute_queue_falls_back_to_sample(
        self,
        run_mock: mock.Mock,
        validate_mock: mock.Mock,
    ) -> None:
        run_mock.side_effect = [
            mock.Mock(returncode=1, stdout="net-fail", stderr="boom"),
            mock.Mock(returncode=0, stdout="sample-ok", stderr=""),
        ]
        validate_mock.side_effect = [
            _validation(False, reason="process_failed", run_id=0, status="", records_loaded=0),
            _validation(True, run_id=2, records_loaded=1),
        ]
        payload = {
            "items": [
                {
                    "source_id": "foo",
                    "rank": 1,
                    "execution": {
                        "repeatability_state": "network_verified",
                        "preferred_mode": "strict-network",
                        "network_command": "python3 scripts/ingestar_politicos_es.py ingest --db <db> --source foo --strict-network",
                        "sample_command": "python3 scripts/ingestar_politicos_es.py ingest --db <db> --source foo --from-file sample.json",
                    },
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "queue.db"
            summary = runner.execute_queue(
                db_path=db_path,
                queue_payload=payload,
                mode="preferred",
                fallback_on_failure="sample-if-available",
            )
        self.assertEqual(summary["totals"]["ok_total"], 1)
        self.assertEqual(summary["totals"]["fallback_total"], 1)
        self.assertEqual(summary["results"][0]["status"], "ok_with_fallback")

    @mock.patch("etl.ops.source_scrape_queue._validate_ingest_run")
    @mock.patch("etl.ops.source_scrape_queue.subprocess.run")
    def test_execute_queue_falls_back_after_timeout(
        self,
        run_mock: mock.Mock,
        validate_mock: mock.Mock,
    ) -> None:
        run_mock.side_effect = [
            subprocess.TimeoutExpired(cmd=["python3"], timeout=1),
            mock.Mock(returncode=0, stdout="sample-ok", stderr=""),
        ]
        validate_mock.side_effect = [
            _validation(False, reason="timeout", run_id=0, status="", records_loaded=0),
            _validation(True, run_id=2, records_loaded=1),
        ]
        payload = {
            "items": [
                {
                    "source_id": "foo",
                    "rank": 1,
                    "execution": {
                        "repeatability_state": "network_verified",
                        "preferred_mode": "strict-network",
                        "network_command": "python3 scripts/ingestar_politicos_es.py ingest --db <db> --source foo --strict-network",
                        "sample_command": "python3 scripts/ingestar_politicos_es.py ingest --db <db> --source foo --from-file sample.json",
                    },
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "queue.db"
            summary = runner.execute_queue(
                db_path=db_path,
                queue_payload=payload,
                mode="preferred",
                fallback_on_failure="sample-if-available",
                command_timeout_seconds=1,
            )
        self.assertEqual(summary["totals"]["ok_total"], 1)
        self.assertEqual(summary["totals"]["fallback_total"], 1)
        self.assertTrue(summary["results"][0]["timed_out"])
        self.assertEqual(summary["results"][0]["status"], "ok_with_fallback")

    @mock.patch("etl.ops.source_scrape_queue._validate_ingest_run")
    @mock.patch("etl.ops.source_scrape_queue.subprocess.run")
    def test_execute_queue_validation_failure_triggers_fallback_even_on_exit_zero(
        self,
        run_mock: mock.Mock,
        validate_mock: mock.Mock,
    ) -> None:
        run_mock.side_effect = [
            mock.Mock(returncode=0, stdout="net-ok", stderr=""),
            mock.Mock(returncode=0, stdout="sample-ok", stderr=""),
        ]
        validate_mock.side_effect = [
            _validation(False, reason="records_loaded_below_target", run_id=1, records_loaded=0),
            _validation(True, run_id=2, records_loaded=1),
        ]
        payload = {
            "items": [
                {
                    "source_id": "foo",
                    "rank": 1,
                    "execution": {
                        "repeatability_state": "network_verified",
                        "preferred_mode": "strict-network",
                        "strict_target": 1,
                        "network_command": "python3 scripts/ingestar_politicos_es.py ingest --db <db> --source foo --strict-network",
                        "sample_command": "python3 scripts/ingestar_politicos_es.py ingest --db <db> --source foo --from-file sample.json",
                    },
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "queue.db"
            summary = runner.execute_queue(
                db_path=db_path,
                queue_payload=payload,
                mode="preferred",
                fallback_on_failure="sample-if-available",
            )
        self.assertEqual(summary["totals"]["ok_total"], 1)
        self.assertEqual(summary["totals"]["fallback_total"], 1)
        self.assertEqual(summary["results"][0]["status"], "ok_with_fallback")
        self.assertEqual(summary["results"][0]["validation"]["reason"], "records_loaded_below_target")

    @mock.patch("etl.ops.source_scrape_queue._validate_ingest_run")
    @mock.patch("etl.ops.source_scrape_queue.subprocess.run")
    def test_execute_queue_respects_dependencies_and_pre_commands(
        self,
        run_mock: mock.Mock,
        validate_mock: mock.Mock,
    ) -> None:
        run_mock.side_effect = [
            mock.Mock(returncode=0, stdout="dep-ok", stderr=""),
            mock.Mock(returncode=0, stdout="prep-ok", stderr=""),
            mock.Mock(returncode=0, stdout="main-ok", stderr=""),
        ]
        validate_mock.side_effect = [
            _validation(True, run_id=1, records_loaded=1),
            _validation(True, run_id=2, records_loaded=1),
        ]
        payload = {
            "items": [
                {
                    "source_id": "congreso_intervenciones",
                    "rank": 2,
                    "execution": {
                        "repeatability_state": "sample_replay_only",
                        "preferred_mode": "from-file",
                        "strict_target": 1,
                        "prerequisite_source_ids": ["congreso_iniciativas"],
                        "pre_commands": [
                            "python3 scripts/ingestar_parlamentario_es.py link-votes --db <db>",
                        ],
                        "network_command": "",
                        "sample_command": "python3 scripts/ingestar_parlamentario_es.py ingest --db <db> --source congreso_intervenciones --from-file sample.json",
                    },
                },
                {
                    "source_id": "congreso_iniciativas",
                    "rank": 10,
                    "execution": {
                        "repeatability_state": "sample_replay_only",
                        "preferred_mode": "from-file",
                        "strict_target": 1,
                        "network_command": "",
                        "sample_command": "python3 scripts/ingestar_parlamentario_es.py ingest --db <db> --source congreso_iniciativas --from-file sample.json",
                    },
                },
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "queue.db"
            summary = runner.execute_queue(
                db_path=db_path,
                queue_payload=payload,
                mode="preferred",
                fallback_on_failure="none",
            )
        self.assertEqual(summary["totals"]["ok_total"], 2)
        executed = [call.kwargs["args"] if "args" in call.kwargs else call.args[0] for call in run_mock.call_args_list]
        self.assertEqual(
            executed,
            [
                [
                    "python3",
                    "scripts/ingestar_parlamentario_es.py",
                    "ingest",
                    "--db",
                    str(db_path),
                    "--source",
                    "congreso_iniciativas",
                    "--from-file",
                    "sample.json",
                ],
                [
                    "python3",
                    "scripts/ingestar_parlamentario_es.py",
                    "link-votes",
                    "--db",
                    str(db_path),
                ],
                [
                    "python3",
                    "scripts/ingestar_parlamentario_es.py",
                    "ingest",
                    "--db",
                    str(db_path),
                    "--source",
                    "congreso_intervenciones",
                    "--from-file",
                    "sample.json",
                ],
            ],
        )


if __name__ == "__main__":
    unittest.main()
