from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.inventory_document_corpus import (
    _count_pdf_page_text,
    _size_bucket,
    inspect_document,
    inspect_markup,
    run_inventory,
)


class TestInventoryDocumentCorpus(unittest.TestCase):
    def test_markup_inventory_uses_relative_paths_and_visible_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "official" / "record.html"
            path.parent.mkdir()
            path.write_text(
                "<html><body>Public evidence 123</body></html>", encoding="utf-8"
            )
            item = inspect_markup(path, root)
            self.assertEqual(item["path"], "official/record.html")
            self.assertEqual(item["source_group"], "official")
            self.assertEqual(item["quality_class"], "markup_with_text")
            self.assertGreater(item["text_chars"], 0)
            self.assertEqual(len(item["sha256"]), 64)

    def test_inventory_aggregates_real_formats_without_promoting_100k(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "source").mkdir()
            (root / "source" / "a.xml").write_text(
                "<root>alpha</root>", encoding="utf-8"
            )
            (root / "source" / "b.pdf").write_bytes(b"%PDF-fixture")
            fake_pdf = {
                "path": "source/b.pdf",
                "source_group": "source",
                "extension": "pdf",
                "mime_type": "application/pdf",
                "bytes": 12,
                "sha256": "a" * 64,
                "status": "ok",
                "real_data_status": "eligible_real_capture",
                "accountability_eligible": True,
                "eligibility_reason": "accountability_document",
                "page_count": 2,
                "text_chars": 400,
                "text_density_chars_per_page": 200.0,
                "quality_class": "pdf_digital_text",
                "page_text_quality": {
                    "segments": 2,
                    "pages_with_text": 2,
                    "pages_empty": 0,
                    "pages_sparse_ocr_candidate": 0,
                    "ocr_candidate_pages": [],
                },
                "error": None,
            }
            with mock.patch(
                "scripts.inventory_document_corpus.inspect_pdf",
                return_value=fake_pdf,
            ):
                items, report = run_inventory(
                    root=root,
                    workers=2,
                    pdf_timeout=1,
                )
            self.assertEqual(len(items), 2)
            self.assertEqual(report["totals"]["files"], 2)
            self.assertEqual(report["totals"]["distinct_content_objects"], 2)
            self.assertEqual(report["totals"]["pdf_pages"], 2)
            self.assertEqual(report["totals"]["pdf_pages_with_text"], 2)
            self.assertTrue(report["checks"]["all_files_accounted"])
            self.assertTrue(report["checks"]["repo_relative_manifest_paths"])
            self.assertFalse(report["checks"]["s1_100k_reached"])

    def test_inventory_reuses_unchanged_checksum_verified_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "official").mkdir()
            (root / "official" / "record.xml").write_text(
                "<root>official public record</root>", encoding="utf-8"
            )
            first_items, _ = run_inventory(root=root, workers=1, pdf_timeout=1)
            previous_manifest = root / "previous.jsonl"
            previous_manifest.write_text(
                "".join(
                    json.dumps(item, sort_keys=True) + "\n" for item in first_items
                ),
                encoding="utf-8",
            )
            with mock.patch(
                "scripts.inventory_document_corpus.inspect_document"
            ) as inspect_document_mock:
                second_items, second_report = run_inventory(
                    root=root,
                    workers=1,
                    pdf_timeout=1,
                    previous_manifest_path=previous_manifest,
                )
            inspect_document_mock.assert_not_called()
            self.assertEqual(second_items, first_items)
            self.assertEqual(
                second_report["incremental_reuse"][
                    "unchanged_file_instances_reused"
                ],
                1,
            )
            self.assertEqual(
                second_report["incremental_reuse"]["file_instances_reinspected"],
                0,
            )

    def test_inventory_excludes_fixture_paths_and_explicit_synthetic_captures(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "official").mkdir()
            (root / "official" / "real.xml").write_text(
                "<root>official public record</root>",
                encoding="utf-8",
            )
            (root / "samples").mkdir()
            (root / "samples" / "fixture.xml").write_text(
                "<root>Programa (synthetic)</root>",
                encoding="utf-8",
            )
            (root / "official" / "copied-fixture.xml").write_text(
                "<root>Programa (synthetic)</root>",
                encoding="utf-8",
            )
            (root / "official" / "synthetic.html").write_text(
                "<title>Programa (synthetic)</title>",
                encoding="utf-8",
            )

            items, report = run_inventory(root=root, workers=2, pdf_timeout=1)

            self.assertEqual([item["path"] for item in items], ["official/real.xml"])
            self.assertEqual(report["totals"]["excluded_non_real_files"], 3)
            self.assertEqual(
                report["non_real_exclusions"]["by_reason"]["fixture_or_sample_path"],
                1,
            )
            copied_reasons = report["non_real_exclusions"]["by_reason"]
            self.assertEqual(
                sum(
                    count
                    for reason, count in copied_reasons.items()
                    if reason.startswith("sample_content_fingerprint:")
                ),
                1,
            )
            self.assertTrue(report["checks"]["fixture_or_sample_paths_excluded"])
            self.assertTrue(report["checks"]["sample_content_fingerprints_excluded"])

    def test_real_transport_failure_is_retained_but_not_counted_as_document(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "official").mkdir()
            (root / "official" / "record.xml").write_text(
                "<root>Official public record</root>", encoding="utf-8"
            )
            # Exact structure and wording from the retained Senate Akamai denial capture.
            (root / "official" / "denied.html").write_text(
                "<html><head><title>Access Denied</title></head>"
                "<body><h1>Access Denied</h1>"
                "You don't have permission to access this server."
                "</body></html>",
                encoding="utf-8",
            )

            items, report = run_inventory(root=root, workers=2, pdf_timeout=1)

            self.assertEqual([item["path"] for item in items], ["official/record.xml"])
            self.assertEqual(
                report["totals"]["excluded_non_accountability_capture_files"], 1
            )
            self.assertEqual(
                report["accountability_exclusions"]["by_reason"][
                    "transport_failure:access_denied"
                ],
                1,
            )
            self.assertTrue(
                report["checks"][
                    "transport_failures_excluded_from_accountability_scale"
                ]
            )

    def test_markup_text_count_ignores_script_and_style_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "official.html"
            path.write_text(
                "<html><head><style>ignored style</style></head>"
                "<body><script>ignored script</script>Visible evidence</body></html>",
                encoding="utf-8",
            )

            item = inspect_markup(path, root)

            self.assertEqual(item["text_chars"], len("Visibleevidence"))

    def test_pdf_magic_overrides_incorrect_html_extension(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "captured-program.html"
            path.write_bytes(b"%PDF-1.4\n")
            expected = {"format_detection": "content_magic_pdf"}
            with mock.patch(
                "scripts.inventory_document_corpus.inspect_pdf",
                return_value=expected,
            ) as inspect_pdf:
                item = inspect_document(path, root, 1)

            self.assertEqual(item, expected)
            inspect_pdf.assert_called_once_with(
                path,
                root,
                1,
                detected_suffix=".pdf",
            )

    def test_size_buckets_are_stable(self) -> None:
        self.assertEqual(_size_bucket(9_999), "lt_10kb")
        self.assertEqual(_size_bucket(10_000), "10kb_to_100kb")
        self.assertEqual(_size_bucket(100_000), "100kb_to_1mb")
        self.assertEqual(_size_bucket(1_000_000), "1mb_to_10mb")
        self.assertEqual(_size_bucket(10_000_000), "gte_10mb")

    def test_pdf_page_counter_preserves_blank_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pages.txt"
            path.write_text("first page\f\fthird page\f", encoding="utf-8")
            self.assertEqual(_count_pdf_page_text(path, 3), [9, 0, 9])


if __name__ == "__main__":
    unittest.main()
