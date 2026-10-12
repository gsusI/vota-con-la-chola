from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import publish_site_origin as pso  # noqa: E402


class FakeS3:
    """In-memory S3 stand-in: ETag is the MD5 of the body, like R2 single-part uploads."""

    def __init__(self, objects: dict[str, bytes] | None = None) -> None:
        self.objects = dict(objects or {})
        self.puts: list[str] = []
        self.deleted: list[str] = []
        self.meta: dict[str, dict] = {}

    def get_paginator(self, _name: str):
        fake = self

        class Paginator:
            def paginate(self, Bucket: str, Prefix: str):
                keys = sorted(k for k in fake.objects if k.startswith(Prefix))
                for start in range(0, max(len(keys), 1), 2):
                    chunk = keys[start : start + 2]
                    yield {"Contents": [{"Key": k, "ETag": f'"{hashlib.md5(fake.objects[k]).hexdigest()}"'} for k in chunk]}

        return Paginator()

    def put_object(self, *, Bucket, Key, Body, ContentType, ContentMD5, Metadata):
        self.objects[Key] = Body
        self.puts.append(Key)
        self.meta[Key] = {"ContentType": ContentType, "Metadata": Metadata}

    def delete_objects(self, *, Bucket, Delete):
        for item in Delete["Objects"]:
            self.objects.pop(item["Key"], None)
            self.deleted.append(item["Key"])


def write_site(root: Path, files: dict[str, bytes]) -> Path:
    for rel, body in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    return root


def run(site: Path, client: FakeS3, *extra: str) -> dict:
    report = site.parent / "report.json"
    argv = ["--site", str(site), "--skip-privacy-check", "--release-id", "r1", "--source-commit", "abc", "--report", str(report), *extra]
    assert pso.main(argv, client=client) == 0
    return json.loads(report.read_text())


class PublishSiteOriginTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.site = write_site(
            Path(self.tmp.name) / "site",
            {
                "index.html": b"<h1>home</h1>",
                "citizen/data/a.json": b'{"a":1}',
                ".DS_Store": b"junk",
                ".nojekyll": b"",
            },
        )

    def test_first_sync_uploads_everything_and_publishes_manifest(self) -> None:
        client = FakeS3()
        report = run(self.site, client)
        self.assertEqual(report["uploaded"], 2)
        self.assertEqual(report["parity_verified"], 2)
        self.assertNotIn("site/.DS_Store", client.objects)
        self.assertEqual(client.meta["site/citizen/data/a.json"]["ContentType"], "application/json; charset=utf-8")
        manifest = json.loads(client.objects["site/releases/r1/manifest.json"])
        self.assertEqual(manifest["schema"], pso.MANIFEST_SCHEMA)
        self.assertEqual(
            {f["path"]: f["sha256"] for f in manifest["files"]}["index.html"],
            hashlib.sha256(b"<h1>home</h1>").hexdigest(),
        )
        latest = json.loads(client.objects["site/releases/latest.json"])
        self.assertEqual(latest["manifest_path"], "/releases/r1/manifest.json")
        self.assertEqual(latest["manifest_sha256"], hashlib.sha256(client.objects["site/releases/r1/manifest.json"]).hexdigest())

    def test_resync_uploads_only_changes_and_deletes_stale_but_keeps_releases(self) -> None:
        client = FakeS3()
        run(self.site, client)
        (self.site / "citizen/data/a.json").write_bytes(b'{"a":2}')
        client.objects["site/old.html"] = b"old"
        for i in range(10):
            client.objects[f"site/keep{i}.txt"] = b"x"
        for i in range(10):
            (self.site / f"keep{i}.txt").write_bytes(b"x")
        client.puts.clear()
        report = run(self.site, client, "--delete")
        self.assertEqual([k for k in client.puts if not k.startswith("site/releases/")], ["site/citizen/data/a.json"])
        self.assertEqual(client.deleted, ["site/old.html"])
        self.assertIn("site/releases/r1/manifest.json", client.objects)
        self.assertEqual(report["unchanged"], 11)

    def test_refuses_mass_delete(self) -> None:
        client = FakeS3({f"site/x{i}.html": b"x" for i in range(10)})
        with self.assertRaises(SystemExit):
            run(self.site, client, "--delete")
        self.assertEqual(client.deleted, [])

    def test_dry_run_needs_no_client(self) -> None:
        report = run(self.site, None, "--dry-run")  # type: ignore[arg-type]
        self.assertEqual(report["file_count"], 2)
        self.assertTrue(report["dry_run"])

    def test_reserved_releases_dir_in_build_is_rejected(self) -> None:
        write_site(self.site, {"releases/x.json": b"{}"})
        with self.assertRaises(SystemExit):
            run(self.site, FakeS3(), "--dry-run")


if __name__ == "__main__":
    unittest.main()
