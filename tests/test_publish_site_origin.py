from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import publish_site_origin as pso  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]


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
        client.objects["site/datasets/latest.json"] = b"{}"
        for i in range(10):
            client.objects[f"site/keep{i}.txt"] = b"x"
        for i in range(10):
            (self.site / f"keep{i}.txt").write_bytes(b"x")
        client.puts.clear()
        report = run(self.site, client, "--delete")
        self.assertEqual([k for k in client.puts if not k.startswith("site/releases/")], ["site/citizen/data/a.json"])
        self.assertEqual(client.deleted, ["site/old.html"])
        self.assertIn("site/releases/r1/manifest.json", client.objects)
        self.assertIn("site/datasets/latest.json", client.objects)
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

    def test_parity_failure_suggests_rerun_when_bucket_changes_mid_sync(self) -> None:
        class RacingS3(FakeS3):
            def put_object(self, **kwargs):
                super().put_object(**kwargs)
                if kwargs["Key"] == "site/index.html":
                    self.objects["site/index.html"] = b"<h1>newer publish</h1>"

        client = RacingS3({"site/old.html": b"old", **{f"site/keep{i}.txt": b"x" for i in range(10)}})
        write_site(self.site, {f"keep{i}.txt": b"x" for i in range(10)})
        with self.assertRaises(SystemExit) as ctx:
            run(self.site, client, "--delete")
        message = str(ctx.exception)
        self.assertIn("Parity check failed for 1 objects", message)
        self.assertIn("re-run `just site-origin-publish`", message)
        self.assertEqual(client.deleted, [])


class R2SettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.env_file = self.tmp / ".env"
        self.wrangler = self.tmp / "wrangler.toml"
        self.wrangler.write_text('name = "w"\naccount_id = "abc123"\n')

    def resolve(self, environ: dict[str, str]) -> dict[str, str]:
        return pso.resolve_r2_settings(environ, env_file=self.env_file, wrangler_toml=self.wrangler)

    def test_dotenv_credentials_and_wrangler_account_fallback(self) -> None:
        self.env_file.write_text("HF_TOKEN=x\nexport R2_ACCESS_KEY_ID='key'\nR2_SECRET_ACCESS_KEY=\"secret\"\n")
        settings = self.resolve({})
        self.assertEqual(settings["R2_ACCESS_KEY_ID"], "key")
        self.assertEqual(settings["R2_SECRET_ACCESS_KEY"], "secret")
        self.assertEqual(settings["R2_ENDPOINT_URL"], "https://abc123.r2.cloudflarestorage.com")

    def test_environment_wins_over_dotenv_and_wrangler(self) -> None:
        self.env_file.write_text("R2_ACCESS_KEY_ID=file\nR2_SECRET_ACCESS_KEY=file\nR2_ACCOUNT_ID=fromfile\n")
        settings = self.resolve({"R2_ACCESS_KEY_ID": "env", "CLOUDFLARE_ACCOUNT_ID": "ignored", "R2_ACCOUNT_ID": "fromenv"})
        self.assertEqual(settings["R2_ACCESS_KEY_ID"], "env")
        self.assertEqual(settings["R2_SECRET_ACCESS_KEY"], "file")
        self.assertEqual(settings["R2_ENDPOINT_URL"], "https://fromenv.r2.cloudflarestorage.com")

    def test_missing_credentials_fail(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            self.resolve({"R2_ACCESS_KEY_ID": "k"})
        self.assertIn("R2_SECRET_ACCESS_KEY", str(ctx.exception))

    def test_repo_wrangler_toml_has_account_id(self) -> None:
        self.assertRegex(pso.wrangler_account_id(pso.WRANGLER_TOML), r"^[0-9a-f]{32}$")


class SiteOriginRecipeTests(unittest.TestCase):
    def recipe_command(self) -> str:
        recipe = (REPO_ROOT / "justfile").read_text().split("\nsite-origin-publish:\n", 1)[1]
        lines = [line.strip() for line in recipe.splitlines()]
        start = next(i for i, line in enumerate(lines) if line.startswith("report_arg=()"))
        call = re.sub(r"^.*?publish_site_origin\.py", "printf '<%s>'", lines[start + 1])
        return f"set -euo pipefail; site=S; {lines[start]}; {call}"

    def run_recipe(self, report: str | None) -> str:
        env = {k: v for k, v in os.environ.items() if k != "SITE_ORIGIN_REPORT"}
        if report is not None:
            env["SITE_ORIGIN_REPORT"] = report
        bash = "/bin/bash" if Path("/bin/bash").exists() else "bash"
        return subprocess.run([bash, "-c", self.recipe_command()], env=env, capture_output=True, text=True, check=True).stdout

    def test_report_arg_is_optional_under_set_u(self) -> None:
        self.assertEqual(self.run_recipe(None), "<--site><S><--delete>")
        self.assertEqual(self.run_recipe("out dir/r.json"), "<--site><S><--delete><--report><out dir/r.json>")


class TestSourceCommit(unittest.TestCase):
    def test_build_dir_inside_repo_reports_repo_head(self) -> None:
        head = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "scripts") as tmp:  # not a repo of its own
            self.assertEqual(pso.git_head(Path(tmp)), head)

    def test_standalone_git_checkout_reports_its_own_head(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_git = lambda *a: subprocess.run(["git", "-C", tmp, *a], capture_output=True, text=True, check=True)  # noqa: E731
            run_git("init", "-q")
            Path(tmp, "index.html").write_text("x")
            run_git("add", "index.html")
            run_git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x")
            self.assertEqual(pso.git_head(Path(tmp)), run_git("rev-parse", "HEAD").stdout.strip())

    def test_build_stamp_wins_and_is_not_published(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            (site / "index.html").write_text("x")
            (site / pso.BUILD_STAMP).write_text('{"source_commit": "abc123", "source_dirty": true}')
            self.assertEqual(pso.read_build_stamp(site)["source_commit"], "abc123")
            self.assertEqual([f.path for f in pso.scan_site(site)], ["index.html"])
            self.assertEqual(pso.read_build_stamp(site / "missing"), {})

    def test_manifest_records_dirty_sources(self) -> None:
        manifest = pso.build_manifest([], release_id="r", source_commit="abc", generated_at="t", source_dirty=True)
        self.assertTrue(manifest["source_dirty"])


class TestPublishRecipes(unittest.TestCase):
    def test_site_publish_syncs_the_build_not_gh_pages(self) -> None:
        text = (REPO_ROOT / "justfile").read_text(encoding="utf-8")
        block = text[text.index("\nsite-origin-publish:"):text.index("\nsite-dataset-mirror:")]
        self.assertIn('site="{{site_out_dir}}"', block)
        self.assertNotIn("gh-pages", block)
        publish = text[text.index("\nsite-publish:"):text.index("\nvotaconlachola-gh-pages-publish:")]
        self.assertLess(publish.index("git rev-parse HEAD"), publish.index("just cloudflare-pages-build"))
        self.assertLess(publish.index(".vclc-build.json"), publish.index("just site-origin-publish"))


if __name__ == "__main__":
    unittest.main()
