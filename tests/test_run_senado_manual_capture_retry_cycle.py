from __future__ import annotations

import csv
import json
import tempfile
import textwrap
from pathlib import Path
import unittest

from scripts import run_senado_manual_capture_retry_cycle as target


class RunSenadoManualCaptureRetryCycleTests(unittest.TestCase):
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
                    "target_kind": "packet_url",
                    "cohort": "legis14",
                    "initiative_id": "senado_iniciativas:1",
                    "capture_url": capture_url,
                    "reason": "waf",
                    "suggested_label": "x",
                    "suggested_command": "python3 scripts/manual_capture_playwright.py ...",
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
        cookie_domain: str = "www.senado.es",
        ended_at: str = "2026-02-28T12:00:00+00:00",
    ) -> Path:
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
                [
                    {
                        "name": "sid",
                        "value": "x",
                        "domain": cookie_domain,
                        "path": "/",
                        "expires": 1893456000,
                    }
                ],
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return meta_path

    def test_strict_ready_fails_when_no_usable_capture(self) -> None:
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

            out = root / "cycle.json"
            progress_out = root / "progress.json"
            progress_csv = root / "progress.csv"
            rc = target.main(
                [
                    "--db",
                    str(db.relative_to(Path.cwd())),
                    "--targets-csv",
                    str(targets.relative_to(Path.cwd())),
                    "--captures-glob",
                    str((root / "*.meta.json").relative_to(Path.cwd())),
                    "--strict-ready",
                    "--out",
                    str(out.relative_to(Path.cwd())),
                    "--progress-out",
                    str(progress_out.relative_to(Path.cwd())),
                    "--progress-csv-out",
                    str(progress_csv.relative_to(Path.cwd())),
                ]
            )
            self.assertEqual(rc, target.STRICT_FAIL_EXIT)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "degraded")
            self.assertFalse(bool(payload["ready_to_retry"]))
            self.assertIn("capture_gate_not_ready", payload["strict_fail_reasons"])
            self.assertFalse(bool((payload.get("backfill") or {}).get("attempted")))

    def test_runs_backfill_when_capture_gate_ready(self) -> None:
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

                    Path({json.dumps(str(called))}).write_text(json.dumps(sys.argv, ensure_ascii=False), encoding="utf-8")
                    raise SystemExit(0)
                    """
                ),
                encoding="utf-8",
            )

            out = root / "cycle.json"
            progress_out = root / "progress.json"
            progress_csv = root / "progress.csv"
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
                    "--out",
                    str(out.relative_to(Path.cwd())),
                    "--progress-out",
                    str(progress_out.relative_to(Path.cwd())),
                    "--progress-csv-out",
                    str(progress_csv.relative_to(Path.cwd())),
                ]
            )
            self.assertEqual(rc, 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "ok")
            self.assertTrue(bool((payload.get("backfill") or {}).get("attempted")))
            self.assertEqual((payload.get("backfill") or {}).get("exit_code"), 0)

            argv = json.loads(called.read_text(encoding="utf-8"))
            self.assertIn("backfill-initiative-documents", argv)
            self.assertIn("--cookie-file", argv)

    def test_strict_backfill_fails_on_backfill_error(self) -> None:
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

            fake_ingestar = root / "fake_ingestar_fail.py"
            fake_ingestar.write_text("raise SystemExit(7)\n", encoding="utf-8")

            out = root / "cycle.json"
            progress_out = root / "progress.json"
            progress_csv = root / "progress.csv"
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
                    "--strict-backfill",
                    "--out",
                    str(out.relative_to(Path.cwd())),
                    "--progress-out",
                    str(progress_out.relative_to(Path.cwd())),
                    "--progress-csv-out",
                    str(progress_csv.relative_to(Path.cwd())),
                ]
            )
            self.assertEqual(rc, target.STRICT_FAIL_EXIT)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "failed")
            self.assertEqual((payload.get("backfill") or {}).get("exit_code"), 7)
            self.assertIn("backfill_failed", payload["strict_fail_reasons"])


if __name__ == "__main__":
    unittest.main()
