from __future__ import annotations

import hashlib
import io
import tempfile
import unittest
from pathlib import Path

from publicdata_core.object_store import (
    FilesystemObjectStore,
    S3ObjectStore,
    content_addressed_object_key,
)


class FakeNotFound(Exception):
    def __init__(self) -> None:
        self.response = {
            "ResponseMetadata": {"HTTPStatusCode": 404},
            "Error": {"Code": "NoSuchKey"},
        }


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], tuple[bytes, dict[str, str], str | None]] = {}
        self.uploads = 0

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
        try:
            body, metadata, content_type = self.objects[(Bucket, Key)]
        except KeyError as exc:
            raise FakeNotFound() from exc
        return {
            "ContentLength": len(body),
            "Metadata": metadata,
            "ContentType": content_type,
            "VersionId": "fixture-v1",
        }

    def upload_fileobj(
        self,
        handle: io.BufferedReader,
        bucket: str,
        key: str,
        *,
        ExtraArgs: dict[str, object],
    ) -> None:
        self.uploads += 1
        self.objects[(bucket, key)] = (
            handle.read(),
            dict(ExtraArgs.get("Metadata") or {}),
            str(ExtraArgs.get("ContentType") or "") or None,
        )

    def download_fileobj(self, bucket: str, key: str, writer: object) -> None:
        body = self.objects[(bucket, key)][0]
        for offset in range(0, len(body), 3):
            writer.write(body[offset : offset + 3])


class TestPublicDataObjectStore(unittest.TestCase):
    def test_filesystem_origin_upload_dedupe_and_clean_restore(self) -> None:
        payload = b"immutable official evidence"
        digest = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "cache" / "document.pdf"
            source.parent.mkdir()
            source.write_bytes(payload)
            store = FilesystemObjectStore(root / "origin")

            first = store.put_verified(
                source,
                content_sha256=digest,
                bytes_expected=len(payload),
                content_type="application/pdf",
                namespace="raw/documents",
            )
            second = store.put_verified(
                source,
                content_sha256=digest,
                bytes_expected=len(payload),
                content_type="application/pdf",
                namespace="raw/documents",
            )
            restored = store.restore_verified(
                first,
                destination=root / "clean-room" / "restored.bin",
                max_bytes=len(payload),
            )

            self.assertFalse(first.deduplicated)
            self.assertTrue(second.deduplicated)
            self.assertEqual(restored.read_bytes(), payload)
            self.assertEqual(
                first.object_key,
                content_addressed_object_key("raw/documents", digest),
            )

    def test_s3_adapter_verifies_remote_metadata_and_streamed_restore(self) -> None:
        payload = b"s3 compatible bytes"
        digest = hashlib.sha256(payload).hexdigest()
        fake = FakeS3Client()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.bin"
            source.write_bytes(payload)
            store = S3ObjectStore(bucket="evidence", client=fake)

            first = store.put_verified(
                source,
                content_sha256=digest,
                bytes_expected=len(payload),
                namespace="raw",
            )
            second = store.put_verified(
                source,
                content_sha256=digest,
                bytes_expected=len(payload),
                namespace="raw",
            )
            restored = store.restore_verified(
                first,
                destination=root / "restored.bin",
                max_bytes=len(payload),
            )

            self.assertEqual(fake.uploads, 1)
            self.assertFalse(first.deduplicated)
            self.assertTrue(second.deduplicated)
            self.assertEqual(first.version_id, "fixture-v1")
            self.assertEqual(restored.read_bytes(), payload)

    def test_restore_max_bytes_fails_before_transfer(self) -> None:
        payload = b"too large"
        digest = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.bin"
            source.write_bytes(payload)
            store = FilesystemObjectStore(root / "origin")
            replica = store.put_verified(
                source,
                content_sha256=digest,
                bytes_expected=len(payload),
            )
            destination = root / "restored.bin"
            with self.assertRaisesRegex(RuntimeError, "max_bytes"):
                store.restore_verified(
                    replica,
                    destination=destination,
                    max_bytes=len(payload) - 1,
                )
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
