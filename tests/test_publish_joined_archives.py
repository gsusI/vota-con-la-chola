from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import publish_joined_archives as pja  # noqa: E402
from test_publish_site_origin import FakeS3  # noqa: E402

RELEASE = "a" * 64


def make_site(root: Path, parts: list[bytes], archive_sha: str | None = None) -> Path:
    release_dir = root / "spending/launch" / RELEASE
    release_dir.mkdir(parents=True)
    entries = []
    for i, body in enumerate(parts):
        name = f"placsp-launch.zip.part-{i:04d}"
        (release_dir / name).write_bytes(body)
        entries.append({"path": name, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()})
    pointer = {
        "release": RELEASE,
        "archive_sha256": archive_sha or hashlib.sha256(b"".join(parts)).hexdigest(),
        "file_parts": {"placsp-launch.zip": entries},
    }
    (root / "spending/launch/latest.json").write_text(json.dumps(pointer))
    return root


class PublishJoinedArchivesTests(unittest.TestCase):
    def test_joins_verifies_and_uploads_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = make_site(Path(tmp), [b"PK\x03\x04ab", b"cd"])
            client = FakeS3()
            pja.main(["--site", str(site)], client=client)
            key = f"site/downloads/{RELEASE}/placsp-launch.zip"
            self.assertEqual(client.objects[key], b"PK\x03\x04abcd")
            self.assertEqual(client.meta[key]["ContentType"], "application/zip")
            client.puts.clear()
            pja.main(["--site", str(site)], client=client)
            self.assertEqual(client.puts, [])

    def test_archive_hash_mismatch_aborts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = make_site(Path(tmp), [b"ab", b"cd"], archive_sha="0" * 64)
            client = FakeS3()
            with self.assertRaises(SystemExit):
                pja.main(["--site", str(site)], client=client)
            self.assertEqual(client.puts, [])

    def test_corrupt_part_aborts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = make_site(Path(tmp), [b"ab", b"cd"])
            (site / "spending/launch" / RELEASE / "placsp-launch.zip.part-0001").write_bytes(b"XX")
            with self.assertRaises(SystemExit):
                pja.main(["--site", str(site), "--dry-run"])


if __name__ == "__main__":
    unittest.main()
