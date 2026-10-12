from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import mirror_dataset_snapshot as mds  # noqa: E402
from test_publish_site_origin import FakeS3  # noqa: E402

SNAP = "snapshots/2026-08-12"


def fake_hf(files: dict[str, bytes], checksums: dict[str, str] | None = None):
    sums = checksums if checksums is not None else {rel: hashlib.sha256(body).hexdigest() for rel, body in files.items()}
    tree = {f"{SNAP}/{rel}": body for rel, body in files.items()}
    tree[f"{SNAP}/checksums.sha256"] = "".join(f"{h}  {rel}\n" for rel, h in sums.items()).encode()
    latest = json.dumps({"snapshot_dir": SNAP}).encode()

    def fetch(url: str) -> bytes:
        if "/api/datasets/" in url:
            return json.dumps([{"type": "file", "path": p} for p in tree] + [{"type": "directory", "path": f"{SNAP}/parquet"}]).encode()
        rel = url.split("/resolve/main/", 1)[1]
        return latest if rel == "latest.json" else tree[rel]

    return fetch


class MirrorDatasetSnapshotTests(unittest.TestCase):
    def test_mirrors_verified_snapshot_and_writes_latest_last(self) -> None:
        client = FakeS3()
        fetch = fake_hf({"manifest.json": b"{}", "parquet/t/part-00000.parquet": b"PAR1"})
        self.assertEqual(mds.main([], client=client, fetch=fetch), 0)
        self.assertEqual(client.objects[f"site/datasets/{SNAP}/parquet/t/part-00000.parquet"], b"PAR1")
        self.assertEqual(client.puts[-1], "site/datasets/latest.json")
        client.puts.clear()
        mds.main([], client=client, fetch=fetch)
        self.assertEqual(client.puts, ["site/datasets/latest.json"])

    def test_checksum_mismatch_aborts_before_upload(self) -> None:
        client = FakeS3()
        fetch = fake_hf({"parquet/t/part-00000.parquet": b"PAR1"}, {"parquet/t/part-00000.parquet": "0" * 64})
        with self.assertRaises(SystemExit):
            mds.main([], client=client, fetch=fetch)
        self.assertEqual(client.puts, [])

    def test_parquet_without_checksum_aborts(self) -> None:
        fetch = fake_hf({"parquet/t/part-00000.parquet": b"PAR1"}, {})
        with self.assertRaises(SystemExit):
            mds.main(["--dry-run"], fetch=fetch)


if __name__ == "__main__":
    unittest.main()
