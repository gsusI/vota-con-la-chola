from __future__ import annotations

import unittest

from etl.parlamentario_es.initdoc_review import export_label_studio_tasks, label_studio_tasks_to_review_rows


class TestInitdocLabelStudio(unittest.TestCase):
    def test_export_tasks_includes_review_context(self) -> None:
        tasks = export_label_studio_tasks(
            [
                {
                    "source_record_pk": 11,
                    "sample_initiative_id": "i1",
                    "initiative_source_id": "senado_iniciativas",
                    "initiative_title": "Titulo",
                    "doc_format": "pdf",
                    "doc_kinds_csv": "bocg",
                    "extractor_version": "v2",
                    "subject_method": "keyword_window",
                    "confidence": 0.42,
                    "source_url": "https://example.org/doc",
                    "raw_path": "etl/data/raw/doc.pdf",
                    "extracted_subject": "tema viejo",
                    "extracted_title": "titulo viejo",
                    "extracted_excerpt": "extracto",
                }
            ]
        )

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["data"]["source_record_pk"], "11")
        self.assertIn("keyword_window", tasks[0]["data"]["review_context"])
        self.assertIn("Abrir documento fuente", tasks[0]["data"]["source_link_html"])

    def test_import_tasks_maps_annotations_to_review_rows(self) -> None:
        rows = label_studio_tasks_to_review_rows(
            [
                {
                    "data": {"source_record_pk": "11"},
                    "annotations": [
                        {
                            "completed_by": {"email": "reviewer@example.org"},
                            "result": [
                                {
                                    "from_name": "review_status",
                                    "value": {"choices": ["resolved"]},
                                },
                                {
                                    "from_name": "final_subject",
                                    "value": {"text": ["tema final"]},
                                },
                                {
                                    "from_name": "final_title",
                                    "value": {"text": ["titulo final"]},
                                },
                                {
                                    "from_name": "final_confidence",
                                    "value": {"number": 0.91},
                                },
                                {
                                    "from_name": "review_note",
                                    "value": {"text": ["ajustado"]},
                                },
                            ],
                        }
                    ],
                }
            ]
        )

        self.assertEqual(
            rows,
            [
                {
                    "source_record_pk": "11",
                    "review_status": "resolved",
                    "final_subject": "tema final",
                    "final_title": "titulo final",
                    "final_confidence": "0.91",
                    "review_note": "ajustado",
                    "reviewer": "reviewer@example.org",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
