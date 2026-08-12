from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from pathlib import Path

from publicdata_publish.privacy import collect_findings
from scripts.sanitize_public_gzip_json import sanitize_gzip_json, sanitize_json_artifact


class TestSanitizePublicGzipJson(unittest.TestCase):
    def test_stream_sanitizes_private_references_and_preserves_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "input.json.gz"
            output = root / "output.json.gz"
            with gzip.open(source, "wt", encoding="utf-8") as handle:
                json.dump(
                    {
                        "source_url": "file:///Users/alice/private.json",
                        "contact": "alice@example.com",
                        "safe": "https://official.example/data.json",
                    },
                    handle,
                )
            report = sanitize_gzip_json(source, output)
            with gzip.open(output, "rt", encoding="utf-8") as handle:
                payload = json.load(handle)
            self.assertEqual(payload["source_url"], "<redacted-local-reference>")
            self.assertEqual(payload["contact"], "alice@example.com")
            self.assertEqual(payload["safe"], "https://official.example/data.json")
            self.assertEqual(report["local_strings_redacted"], 1)
            self.assertTrue(report["official_public_emails_retained"])
            findings, _ = collect_findings([output])
            self.assertEqual(findings, [])

    def test_stream_sanitizes_plain_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "input.json"
            output = root / "output.json"
            source.write_text(
                json.dumps({"source_url": "file:///home/alice/private.json"}),
                encoding="utf-8",
            )
            report = sanitize_json_artifact(source, output)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["source_url"], "<redacted-local-reference>")
            self.assertEqual(report["local_strings_redacted"], 1)


if __name__ == "__main__":
    unittest.main()
