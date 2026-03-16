from __future__ import annotations

import csv
import json
import tempfile
import textwrap
from pathlib import Path
import unittest

from scripts import run_senado_manual_capture_iteration_cycle as target


class RunSenadoManualCaptureIterationCycleTests(unittest.TestCase):
    def _write_targets_csv(self, path: Path, capture_url: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "target_rank",
                    "target_id",
                    "target_kind",
                    "cohort",
                    "initiative_id",
                    "capture_url",
                    "reason",
                    "suggested_label",
                    "suggested_command",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "target_rank": "1",
                    "target_id": "t1",
                    "target_kind": "seed",
                    "cohort": "seed",
                    "initiative_id": "",
                    "capture_url": capture_url,
                    "reason": "seed_homepage_for_cookie_refresh",
                    "suggested_label": "senado_cookie_refresh_test",
                    "suggested_command": "",
                }
            )

    def _write_capture(
        self,
        root: Path,
        *,
        label: str,
        final_url: str,
        title: str,
        html: str,
        ended_at: str = "2026-02-28T12:00:00+00:00",
    ) -> None:
        meta_path = root / f"{label}.meta.json"
        html_path = root / f"{label}.html"
        cookie_path = root / f"{label}.cookies.json"
        meta_path.write_text(
            json.dumps(
                {
                    "url": final_url,
                    "result": {
                        "status": "captured",
                        "title": title,
                        "final_url": final_url,
                        "ended_at": ended_at,
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        html_path.write_text(html, encoding="utf-8")
        cookie_path.write_text(
            json.dumps(
                [{"name": "sid", "value": "x", "domain": "www.senado.es", "path": "/", "expires": 1893456000}],
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def test_degraded_with_pending_queue_and_reduction_delta(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as td:
            root = Path(td)
            db = root / "db.sqlite"
            db.write_bytes(b"")
            targets = root / "targets.csv"
            self._write_targets_csv(targets, "https://www.senado.es/")
            self._write_capture(
                root,
                label="capture_denied",
                final_url="https://www.senado.es/",
                title="Access denied",
                html="You don't have permission to access this resource.",
            )

            pending_out = root / "pending.json"
            pending_out.write_text(
                json.dumps({"status": "degraded", "totals": {"pending_targets_total": 3}}, ensure_ascii=False),
                encoding="utf-8",
            )

            out = root / "iteration.json"
            rc = target.main(
                [
                    "--db",
                    str(db.relative_to(Path.cwd())),
                    "--targets-csv",
                    str(targets.relative_to(Path.cwd())),
                    "--captures-glob",
                    str((root / "*.meta.json").relative_to(Path.cwd())),
                    "--retry-out",
                    str((root / "retry.json").relative_to(Path.cwd())),
                    "--progress-out",
                    str((root / "progress.json").relative_to(Path.cwd())),
                    "--progress-csv-out",
                    str((root / "progress.csv").relative_to(Path.cwd())),
                    "--pending-out",
                    str(pending_out.relative_to(Path.cwd())),
                    "--pending-csv-out",
                    str((root / "pending.csv").relative_to(Path.cwd())),
                    "--pending-commands-out",
                    str((root / "pending.sh").relative_to(Path.cwd())),
                    "--out",
                    str(out.relative_to(Path.cwd())),
                ]
            )
            self.assertEqual(rc, 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "degraded")
            self.assertEqual(payload["totals"]["previous_pending_total"], 3)
            self.assertEqual(payload["totals"]["current_pending_total"], 1)
            self.assertEqual(payload["totals"]["pending_reduction_total"], 2)

    def test_ok_when_retry_ok_and_pending_empty(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as td:
            root = Path(td)
            db = root / "db.sqlite"
            db.write_bytes(b"")
            targets = root / "targets.csv"
            self._write_targets_csv(targets, "https://www.senado.es/")
            self._write_capture(
                root,
                label="capture_ok",
                final_url="https://www.senado.es/",
                title="Senado de España",
                html="<html><title>Senado</title></html>",
            )

            called = root / "called.json"
            fake_ingestar = root / "fake_ingestar.py"
            fake_ingestar.write_text(
                textwrap.dedent(
                    f"""\
                    import json
                    import sys
                    from pathlib import Path
                    Path({json.dumps(str(called))}).write_text(json.dumps(sys.argv, ensure_ascii=False), encoding='utf-8')
                    raise SystemExit(0)
                    """
                ),
                encoding="utf-8",
            )

            out = root / "iteration.json"
            rc = target.main(
                [
                    "--db",
                    str(db.relative_to(Path.cwd())),
                    "--targets-csv",
                    str(targets.relative_to(Path.cwd())),
                    "--captures-glob",
                    str((root / "*.meta.json").relative_to(Path.cwd())),
                    "--python-bin",
                    "python3",
                    "--ingestar-script",
                    str(fake_ingestar.relative_to(Path.cwd())),
                    "--retry-out",
                    str((root / "retry.json").relative_to(Path.cwd())),
                    "--progress-out",
                    str((root / "progress.json").relative_to(Path.cwd())),
                    "--progress-csv-out",
                    str((root / "progress.csv").relative_to(Path.cwd())),
                    "--pending-out",
                    str((root / "pending.json").relative_to(Path.cwd())),
                    "--pending-csv-out",
                    str((root / "pending.csv").relative_to(Path.cwd())),
                    "--pending-commands-out",
                    str((root / "pending.sh").relative_to(Path.cwd())),
                    "--out",
                    str(out.relative_to(Path.cwd())),
                    "--strict",
                ]
            )
            self.assertEqual(rc, 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["totals"]["current_pending_total"], 0)
            self.assertTrue((payload.get("checks") or {}).get("backfill_ok"))

    def test_strict_fails_when_pending_open(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as td:
            root = Path(td)
            db = root / "db.sqlite"
            db.write_bytes(b"")
            targets = root / "targets.csv"
            self._write_targets_csv(targets, "https://www.senado.es/")
            self._write_capture(
                root,
                label="capture_denied",
                final_url="https://www.senado.es/",
                title="Access denied",
                html="You don't have permission to access this resource.",
            )

            out = root / "iteration.json"
            rc = target.main(
                [
                    "--db",
                    str(db.relative_to(Path.cwd())),
                    "--targets-csv",
                    str(targets.relative_to(Path.cwd())),
                    "--captures-glob",
                    str((root / "*.meta.json").relative_to(Path.cwd())),
                    "--retry-out",
                    str((root / "retry.json").relative_to(Path.cwd())),
                    "--progress-out",
                    str((root / "progress.json").relative_to(Path.cwd())),
                    "--progress-csv-out",
                    str((root / "progress.csv").relative_to(Path.cwd())),
                    "--pending-out",
                    str((root / "pending.json").relative_to(Path.cwd())),
                    "--pending-csv-out",
                    str((root / "pending.csv").relative_to(Path.cwd())),
                    "--pending-commands-out",
                    str((root / "pending.sh").relative_to(Path.cwd())),
                    "--out",
                    str(out.relative_to(Path.cwd())),
                    "--strict",
                ]
            )
            self.assertEqual(rc, target.STRICT_FAIL_EXIT)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "degraded")
            self.assertIn("pending_targets_remaining", payload["strict_fail_reasons"])


if __name__ == "__main__":
    unittest.main()
