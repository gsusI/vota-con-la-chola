from __future__ import annotations

import io
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import r2_publish_lock as lock  # noqa: E402


class Conditional(Exception):
    def __init__(self, status: int) -> None:
        super().__init__(f"HTTP {status}")
        self.response = {"ResponseMetadata": {"HTTPStatusCode": status}}


class FakeR2:
    """Objects dict with R2's conditional PUT (If-None-Match: *) semantics."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_object(self, *, Bucket, Key, Body, IfNoneMatch=None, ContentType=None):
        if IfNoneMatch == "*" and Key in self.objects:
            raise Conditional(412)
        self.objects[Key] = Body

    def get_object(self, *, Bucket, Key):
        if Key not in self.objects:
            raise Conditional(404)
        return {"Body": io.BytesIO(self.objects[Key])}

    def delete_object(self, *, Bucket, Key):
        self.objects.pop(Key, None)


class R2PublishLockTests(unittest.TestCase):
    def test_second_publisher_is_refused_until_release(self) -> None:
        r2 = FakeR2()
        lock.main(["acquire", "--owner", "ci"], client=r2)
        with self.assertRaises(SystemExit):
            lock.main(["acquire", "--owner", "local", "--wait-seconds", "0"], client=r2)
        lock.main(["release", "--owner", "local"], client=r2)  # not the holder: no-op
        self.assertEqual(json.loads(r2.objects[lock.LOCK_KEY])["owner"], "ci")
        lock.main(["release", "--owner", "ci"], client=r2)
        lock.main(["acquire", "--owner", "local", "--wait-seconds", "0"], client=r2)
        self.assertEqual(json.loads(r2.objects[lock.LOCK_KEY])["owner"], "local")

    def test_expired_lock_is_taken_over(self) -> None:
        r2 = FakeR2()
        past = datetime.now(timezone.utc) - timedelta(hours=3)
        r2.objects[lock.LOCK_KEY] = json.dumps(
            {"owner": "crashed", "acquired_at": past.isoformat(), "expires_at": (past + lock.TTL).isoformat()}
        ).encode()
        lock.main(["acquire", "--owner", "ci", "--wait-seconds", "0"], client=r2)
        self.assertEqual(json.loads(r2.objects[lock.LOCK_KEY])["owner"], "ci")


if __name__ == "__main__":
    unittest.main()
