from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts import report_senado_manual_capture_target_progress as target


class ReportSenadoManualCaptureTargetProgressTests(unittest.TestCase):
    def _write_targets_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        fieldnames = [
            "target_rank",
            "target_id",
            "target_kind",
            "cohort",
            "initiative_id",
            "capture_url",
            "reason",
            "suggested_label",
            "suggested_command",
        ]
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k, "") for k in fieldnames})

    def _write_capture(
        self,
        root: Path,
        stem: str,
        *,
        final_url: str,
        title: str,
        html: str,
        cookies: list[dict],
    ) -> Path:
        meta = {
            "result": {
                "status": "captured",
                "title": title,
                "final_url": final_url,
                "ended_at": "2026-02-28T20:00:00+00:00",
                "html_len": len(html),
            }
        }
        meta_path = root / f"{stem}.meta.json"
        html_path = root / f"{stem}.html"
        cookies_path = root / f"{stem}.cookies.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        html_path.write_text(html, encoding="utf-8")
        cookies_path.write_text(json.dumps(cookies, ensure_ascii=False), encoding="utf-8")
        return meta_path

    def test_ok_with_exact_and_path_matches(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            targets_csv = root / "targets.csv"
            out_json = root / "out.json"
            out_csv = root / "out.csv"

            self._write_targets_csv(
                targets_csv,
                [
                    {
                        "target_rank": "1",
                        "target_id": "target_01",
                        "target_kind": "seed",
                        "cohort": "seed",
                        "capture_url": "https://www.senado.es/",
                        "reason": "seed",
                    },
                    {
                        "target_rank": "2",
                        "target_id": "target_02",
                        "target_kind": "cohort_primary",
                        "cohort": "leg14:tipo621",
                        "capture_url": "https://www.senado.es/web/actividadparlamentaria/iniciativas/detalleiniciativa/index.html?legis=14&id2=000006&id1=621",
                        "reason": "top_row_in_cohort",
                    },
                ],
            )

            self._write_capture(
                root,
                "cap_seed",
                final_url="https://www.senado.es/",
                title="Senado",
                html="<html><title>Senado</title></html>",
                cookies=[{"name": "JSESSIONID", "domain": "www.senado.es", "expires": -1}],
            )
            self._write_capture(
                root,
                "cap_detalle",
                final_url="https://www.senado.es/web/actividadparlamentaria/iniciativas/detalleiniciativa/index.html?id1=621&id2=000006&legis=14",
                title="Detalle",
                html="<html><title>Detalle</title></html>",
                cookies=[{"name": "TS", "domain": "www.senado.es", "expires": -1}],
            )

            rc = target.main(
                [
                    "--targets-csv",
                    str(targets_csv),
                    "--captures-glob",
                    str(root / "*.meta.json"),
                    "--strict-min-covered-targets",
                    "2",
                    "--strict-min-usable-targets",
                    "2",
                    "--strict",
                    "--out",
                    str(out_json),
                    "--csv-out",
                    str(out_csv),
                ]
            )
            self.assertEqual(rc, 0)
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(int(payload["totals"]["matched_targets_total"]), 2)
            self.assertEqual(int(payload["totals"]["usable_targets_total"]), 2)

    def test_degraded_when_usable_below_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            targets_csv = root / "targets.csv"
            out_json = root / "out.json"
            out_csv = root / "out.csv"

            self._write_targets_csv(
                targets_csv,
                [
                    {
                        "target_rank": "1",
                        "target_id": "target_01",
                        "target_kind": "cohort_primary",
                        "cohort": "leg14:tipo621",
                        "capture_url": "https://www.senado.es/x",
                        "reason": "top",
                    }
                ],
            )
            self._write_capture(
                root,
                "cap_bad",
                final_url="https://www.senado.es/x",
                title="Access Denied",
                html="<html>Access Denied</html>",
                cookies=[],
            )

            rc = target.main(
                [
                    "--targets-csv",
                    str(targets_csv),
                    "--captures-glob",
                    str(root / "*.meta.json"),
                    "--strict-min-covered-targets",
                    "1",
                    "--strict-min-usable-targets",
                    "1",
                    "--strict",
                    "--out",
                    str(out_json),
                    "--csv-out",
                    str(out_csv),
                ]
            )
            self.assertEqual(rc, 4)
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "degraded")
            reasons = payload.get("strict_fail_reasons") or []
            self.assertIn("usable_targets_below_min", reasons)

    def test_degraded_when_targets_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            targets_csv = root / "targets.csv"
            out_json = root / "out.json"
            out_csv = root / "out.csv"

            self._write_targets_csv(targets_csv, [])

            rc = target.main(
                [
                    "--targets-csv",
                    str(targets_csv),
                    "--captures-glob",
                    str(root / "*.meta.json"),
                    "--strict",
                    "--out",
                    str(out_json),
                    "--csv-out",
                    str(out_csv),
                ]
            )
            self.assertEqual(rc, 4)
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "degraded")
            self.assertIn("no_targets", payload.get("strict_fail_reasons") or [])


if __name__ == "__main__":
    unittest.main()
