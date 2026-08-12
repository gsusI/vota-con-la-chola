from __future__ import annotations

import hashlib
import io
import tempfile
import unittest
from pathlib import Path

from publicdata_core.blobstore import (
    download_to_content_addressed_store,
    stream_response_to_content_addressed_store,
)


class FakeResponse(io.BytesIO):
    def __init__(self, payload: bytes, headers: dict[str, str]) -> None:
        super().__init__(payload)
        self.headers = headers
        self.read_sizes: list[int] = []

    def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        return super().read(size)


class TestPublicDataBlobStore(unittest.TestCase):
    def test_rejects_conflicting_tls_modes_before_network(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle = Path(temp_dir) / "ca.pem"
            bundle.write_text("unused", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "mutually exclusive"):
                download_to_content_addressed_store(
                    "https://example.test/data.json",
                    store_root=Path(temp_dir) / "store",
                    timeout=1,
                    ca_bundle=bundle,
                    insecure_ssl=True,
                )

    def test_streams_in_bounded_chunks_and_deduplicates_by_content(self) -> None:
        payload = (b"pdf-content-" * 10_000) + b"end"
        expected_sha = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "store"
            response = FakeResponse(
                payload,
                {
                    "Content-Type": "application/pdf",
                    "Content-Length": str(len(payload)),
                    "ETag": '"v1"',
                },
            )
            progress_calls = 0

            def record_progress() -> None:
                nonlocal progress_calls
                progress_calls += 1

            stored = stream_response_to_content_addressed_store(
                response,
                url="https://example.test/document",
                store_root=root,
                chunk_bytes=1_024,
                max_bytes=len(payload) + 1,
                progress_callback=record_progress,
            )
            self.assertEqual(stored.content_sha256, expected_sha)
            self.assertEqual(stored.bytes, len(payload))
            self.assertEqual(stored.path.read_bytes(), payload)
            self.assertEqual(stored.path.name, f"{expected_sha}.pdf")
            self.assertTrue(all(size == 1_024 for size in response.read_sizes))
            self.assertEqual(progress_calls, len(response.read_sizes) - 1)
            self.assertFalse(stored.deduplicated)

            duplicate = stream_response_to_content_addressed_store(
                FakeResponse(payload, {"Content-Type": "application/pdf"}),
                url="https://example.test/other-name.pdf",
                store_root=root,
                chunk_bytes=2_048,
                max_bytes=len(payload) + 1,
            )
            self.assertEqual(duplicate.path, stored.path)
            self.assertTrue(duplicate.deduplicated)
            self.assertEqual(list((root / ".partial").iterdir()), [])

    def test_rejects_declared_or_streamed_oversize_and_cleans_partial(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "store"
            with self.assertRaisesRegex(RuntimeError, "before transfer"):
                stream_response_to_content_addressed_store(
                    FakeResponse(b"small", {"Content-Length": "100"}),
                    url="https://example.test/file.bin",
                    store_root=root,
                    max_bytes=10,
                )

            with self.assertRaisesRegex(RuntimeError, "received"):
                stream_response_to_content_addressed_store(
                    FakeResponse(b"01234567890", {}),
                    url="https://example.test/file.bin",
                    store_root=root,
                    max_bytes=10,
                    chunk_bytes=4,
                )
            self.assertEqual(list((root / ".partial").iterdir()), [])

    def test_rejects_truncated_body_against_declared_content_length(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "store"
            with self.assertRaisesRegex(
                RuntimeError,
                "incomplete download: declared=100 received=7",
            ):
                stream_response_to_content_addressed_store(
                    FakeResponse(b"partial", {"Content-Length": "100"}),
                    url="https://example.test/truncated.pdf",
                    store_root=root,
                    max_bytes=1_000,
                    chunk_bytes=4,
                )
            self.assertEqual(list((root / ".partial").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
