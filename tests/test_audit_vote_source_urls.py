from __future__ import annotations

import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_vote_source_urls import VoteUrlAuditError, run_audit


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestAuditVoteSourceUrls(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.root = self.repo / "shards"
        self.root.mkdir()
        self.capture_root = self.repo / "captures"
        self.capture_root.mkdir()
        self.manifest = self.repo / "manifest.json"
        self.url_manifest = self.repo / "urls.jsonl"
        self.report = self.repo / "report.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def make_shard(
        self,
        *,
        name: str,
        source_url: str,
        source_id: str,
        legislature: str,
        rows: int,
    ) -> dict[str, object]:
        source = {
            "source_id": source_id,
            "source_url": source_url,
            "source_record_id": f"url:{source_url}",
            "source_hash": hashlib.sha256(source_url.encode()).hexdigest(),
        }
        payload = {
            "event": {"source_id": source_id, "legislature": legislature},
            "source": source,
            "member_votes": [{"source": source} for _index in range(rows)],
        }
        path = self.root / name
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump(payload, handle)
        return {
            "shard": name,
            "shard_bytes": path.stat().st_size,
            "shard_sha256": sha256(path),
            "member_votes": rows,
            "source_id": source_id,
            "legislature": legislature,
        }

    def execute(self, entries: list[dict[str, object]]) -> dict[str, object]:
        self.manifest.write_text(
            json.dumps(
                {
                    "schema_version": "member_vote_event_shards_v1",
                    "events_total": len(entries),
                    "member_votes_total": sum(
                        int(entry["member_votes"]) for entry in entries
                    ),
                    "entries": entries,
                }
            ),
            encoding="utf-8",
        )
        return run_audit(
            repo_root=self.repo,
            root=self.root,
            manifest_path=self.manifest,
            capture_root=self.capture_root,
            url_manifest_out=self.url_manifest,
            report_out=self.report,
            probe_urls=[],
            timeout=1,
            max_probe_bytes=1024,
        )

    def test_reconciles_https_and_historical_http_capture(self) -> None:
        http_url = "http://www.senado.es/legis12/votaciones/ses_3_23.xml"
        capture = self.capture_root / "legis12" / "ses_3_23.xml"
        capture.parent.mkdir()
        capture.write_bytes(b"official senate capture")
        entries = [
            self.make_shard(
                name="https.json.gz",
                source_url="https://www.congreso.es/official-vote.json",
                source_id="congreso_votaciones",
                legislature="15",
                rows=2,
            ),
            self.make_shard(
                name="http.json.gz",
                source_url=http_url,
                source_id="senado_votaciones",
                legislature="12",
                rows=3,
            ),
        ]

        report = self.execute(entries)

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["totals"]["rows"], 5)
        self.assertEqual(report["totals"]["rows_http"], 3)
        self.assertEqual(report["totals"]["http_rows_with_checksum_capture"], 3)
        self.assertTrue(report["checks"]["integrity_passed"])
        self.assertTrue(report["checks"]["secure_or_immutable_replacement_gate"])
        rows = [
            json.loads(line)
            for line in self.url_manifest.read_text(encoding="utf-8").splitlines()
        ]
        http_row = next(row for row in rows if row["scheme"] == "http")
        self.assertEqual(http_row["capture_status"], "checksum_capture_present")
        self.assertFalse(http_row["source_url_rewritten"])

    def test_rejects_shard_checksum_drift(self) -> None:
        entry = self.make_shard(
            name="vote.json.gz",
            source_url="https://www.congreso.es/official-vote.json",
            source_id="congreso_votaciones",
            legislature="15",
            rows=1,
        )
        entry["shard_sha256"] = "0" * 64

        with self.assertRaises(VoteUrlAuditError):
            self.execute([entry])


if __name__ == "__main__":
    unittest.main()
