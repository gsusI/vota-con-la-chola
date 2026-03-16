import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.export_political_positions_snapshot import (
    PARTY_TRAJECTORIES_FILENAME,
    PERSON_DEFAULT_ROWS_FILENAME,
    PERSON_SEARCH_INDEX_FILENAME,
    PERSON_SORT_PREVIEW_DIRNAME,
    PERSON_TRAJECTORY_CHUNK_DIRNAME,
    PERSON_TRAJECTORIES_FILENAME,
    TOPIC_PERSON_ROWS_DIRNAME,
    TOPIC_SEARCH_INDEX_FILENAME,
    build_person_search_index,
    build_person_trajectory_chunks,
    build_evidence_sample_payload,
    build_person_default_rows,
    build_person_detail_payloads,
    build_topic_search_index,
    build_topic_person_row_payloads,
    compact_person_chunk_manifest,
    build_person_sort_preview_payloads,
    compact_payload_for_static_publish,
    point_detail_key,
    write_person_default_rows_payload,
    write_person_search_index_payload,
    write_person_sort_preview_payloads,
    write_topic_search_index_payload,
    write_topic_person_row_payloads,
    write_trajectory_payloads,
)


class PoliticalPositionsSnapshotTest(unittest.TestCase):
    def test_build_evidence_sample_payload_keeps_only_rendered_fields(self):
        sample = build_evidence_sample_payload(
            {
                "evidence_id": 42,
                "evidence_type": "revealed:vote",
                "evidence_date": "2026-02-01",
                "title": "Fallback title",
                "excerpt": "",
                "stance": "support",
                "confidence": 0.75,
                "source_id": "congreso_votaciones",
                "source_url": "",
                "source_record_pk": "abc-123",
            },
            {
                ("congreso_votaciones", "abc-123"): {
                    "status": "resolved",
                    "note": "unused in static payload",
                }
            },
        )

        self.assertEqual(sample["evidence_id"], 42)
        self.assertEqual(sample["excerpt"], "Fallback title")
        self.assertEqual(sample["confidence"], 0.75)
        self.assertEqual(sample["review"], {"status": "resolved"})
        self.assertNotIn("source_record_pk", sample)
        self.assertNotIn("title", sample)
        self.assertNotIn("source_url", sample)

    def test_compact_payload_for_static_publish_drops_repeated_fields_and_empty_dicts(self):
        payload = {
            "person_trajectories": {
                "10": [
                    {
                        "person_id": 10,
                        "topic_id": 7,
                        "topic_label": "Tema",
                        "topic_key": "topic-key",
                        "as_of_date": "2026-02-12",
                        "window_days": 0,
                        "computed_method": "combined",
                        "computed_version": "v1",
                        "stance": "no_signal",
                        "score": 0.0,
                        "confidence": 0.0,
                        "evidence_count": 0,
                        "last_evidence_date": "",
                        "party_id": 2,
                        "party_label": "PP",
                        "evidence_breakdown": {"declared": 0, "revealed": 0, "other": 0},
                        "review_summary": {"pending": 0, "resolved": 0, "ignored": 0},
                        "evidence_samples": [],
                    }
                ]
            },
            "party_trajectories": {
                "2": [
                    {
                        "party_id": 2,
                        "party_name": "PP",
                        "party_acronym": "PP",
                        "topic_id": 7,
                        "topic_label": "Tema",
                        "topic_key": "topic-key",
                        "as_of_date": "2026-02-12",
                        "computed_method": "combined",
                        "stance": "unclear",
                    }
                ]
            },
        }

        compacted = compact_payload_for_static_publish(payload)
        person_point = compacted["person_trajectories"]["10"][0]
        party_point = compacted["party_trajectories"]["2"][0]

        for key in ("person_id", "topic_label", "topic_key", "party_label", "computed_version", "window_days", "evidence_count", "last_evidence_date", "evidence_breakdown", "review_summary", "evidence_samples"):
            self.assertNotIn(key, person_point)
        for key in ("topic_label", "topic_key", "party_name", "party_acronym"):
            self.assertNotIn(key, party_point)
        self.assertEqual(person_point["topic_id"], 7)
        self.assertEqual(person_point["party_id"], 2)
        self.assertEqual(party_point["party_id"], 2)

    def test_build_person_detail_payloads_groups_samples_by_person_and_point(self):
        payloads = build_person_detail_payloads(
            {
                "10": [
                    {
                        "topic_id": 7,
                        "as_of_date": "2026-02-12",
                        "computed_method": "combined",
                        "evidence_samples": [{"evidence_id": 1}],
                    },
                    {
                        "topic_id": 8,
                        "as_of_date": "2026-02-11",
                        "computed_method": "votes",
                        "evidence_samples": [],
                    },
                ]
            },
            snapshot_date="2026-02-12",
        )

        self.assertIn("10", payloads)
        self.assertEqual(payloads["10"]["meta"]["person_id"], 10)
        self.assertEqual(payloads["10"]["meta"]["snapshot_date"], "2026-02-12")
        self.assertEqual(
            payloads["10"]["evidence_samples_by_point"][point_detail_key(7, "2026-02-12", "combined")],
            [{"evidence_id": 1}],
        )
        self.assertNotIn(
            point_detail_key(8, "2026-02-11", "votes"),
            payloads["10"]["evidence_samples_by_point"],
        )

    def test_write_trajectory_payloads_writes_mode_companions(self):
        with TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "stances.json"
            write_trajectory_payloads(
                out_path,
                person_manifest={"meta": {"chunk_count": 1}, "chunks": [{"chunk_id": "chunk-001"}]},
                person_chunk_payloads={"chunk-001": {"10": [{"topic_id": 1}]}},
                person_search_index_payload={"meta": {"snapshot_date": "2026-02-12"}, "topic_ids": {"1": ["chunk-001"]}, "topic_tokens": {"vivienda": ["chunk-001"]}},
                topic_search_index_payload={"meta": {"snapshot_date": "2026-02-12"}, "topic_tokens": {"movilidad": [1]}},
                person_sort_preview_payloads={"confidence_desc": [{"key": "i-10-1-2026-02-01-combined"}]},
                topic_person_row_payloads={"1": [{"key": "i-10-1-2026-02-01-combined"}]},
                party_payload={"2": [{"topic_id": 1}]},
            )
            self.assertEqual(
                (out_path.parent / PERSON_TRAJECTORIES_FILENAME).read_text(),
                '{"meta":{"chunk_count":1},"chunks":[{"chunk_id":"chunk-001"}]}',
            )
            self.assertEqual(
                (out_path.parent / PERSON_TRAJECTORY_CHUNK_DIRNAME / "chunk-001.json").read_text(),
                '{"10":[{"topic_id":1}]}',
            )
            self.assertEqual(
                (out_path.parent / PERSON_SEARCH_INDEX_FILENAME).read_text(),
                '{"meta":{"snapshot_date":"2026-02-12"},"topic_ids":{"1":["chunk-001"]},"topic_tokens":{"vivienda":["chunk-001"]}}',
            )
            self.assertEqual(
                (out_path.parent / TOPIC_SEARCH_INDEX_FILENAME).read_text(),
                '{"meta":{"snapshot_date":"2026-02-12"},"topic_tokens":{"movilidad":[1]}}',
            )
            self.assertEqual(
                (out_path.parent / PERSON_SORT_PREVIEW_DIRNAME / "confidence_desc.json").read_text(),
                '[{"key":"i-10-1-2026-02-01-combined"}]',
            )
            self.assertEqual(
                (out_path.parent / TOPIC_PERSON_ROWS_DIRNAME / "1.json").read_text(),
                '[{"key":"i-10-1-2026-02-01-combined"}]',
            )
            self.assertEqual((out_path.parent / PARTY_TRAJECTORIES_FILENAME).read_text(), '{"2":[{"topic_id":1}]}')

    def test_build_person_default_rows_matches_default_person_sort(self):
        rows = build_person_default_rows(
            [
                {"person_id": 2, "full_name": "Ana B", "canonical_key": "ana-b"},
                {"person_id": 1, "full_name": "Ana A", "canonical_key": "ana-a"},
            ],
            {
                "1": [
                    {
                        "topic_id": 8,
                        "topic_label": "Beta",
                        "topic_key": "beta",
                        "as_of_date": "2026-02-01",
                        "computed_method": "votes",
                        "stance": "support",
                        "score": 0.7,
                        "confidence": 0.6,
                        "evidence_count": 3,
                        "last_evidence_date": "2026-02-01",
                        "party_id": 10,
                        "party_label": "PSOE",
                        "evidence_breakdown": {"revealed": 3},
                        "review_summary": {"resolved": 1},
                    },
                    {
                        "topic_id": 7,
                        "topic_label": "Alpha",
                        "topic_key": "alpha",
                        "as_of_date": "2026-02-02",
                        "computed_method": "combined",
                        "stance": "oppose",
                        "score": 0.2,
                        "confidence": 0.9,
                        "evidence_count": 5,
                        "last_evidence_date": "2026-02-02",
                        "party_id": 10,
                        "party_label": "PSOE",
                        "evidence_breakdown": {"revealed": 5},
                        "review_summary": {"pending": 1},
                    },
                ],
                "2": [
                    {
                        "topic_id": 7,
                        "topic_label": "Alpha",
                        "topic_key": "alpha",
                        "as_of_date": "2026-02-03",
                        "computed_method": "declared",
                        "stance": "mixed",
                        "score": 0.5,
                        "confidence": 0.4,
                        "evidence_count": 1,
                        "last_evidence_date": "2026-02-03",
                        "party_id": 11,
                        "party_label": "PP",
                        "evidence_breakdown": {"declared": 1},
                        "review_summary": {},
                    }
                ],
            },
        )

        self.assertEqual([row["personId"] for row in rows], [1, 1, 2])
        self.assertEqual([row["topicLabel"] for row in rows], ["Alpha", "Beta", "Alpha"])
        self.assertEqual(rows[0]["method"], "combined")
        self.assertEqual(rows[0]["key"], "i-1-7-2026-02-02-combined")

    def test_write_person_default_rows_payload_writes_json(self):
        with TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "stances.json"
            write_person_default_rows_payload(
                out_path,
                [{"scope": "person", "key": "i-1-7-2026-02-02-combined"}],
            )
            self.assertEqual(
                (out_path.parent / PERSON_DEFAULT_ROWS_FILENAME).read_text(),
                '[{"scope":"person","key":"i-1-7-2026-02-02-combined"}]',
            )

    def test_build_person_sort_preview_payloads_precompute_unfiltered_advanced_sorts(self):
        previews = build_person_sort_preview_payloads(
            [
                {"person_id": 1, "full_name": "Ana A", "canonical_key": "ana-a"},
                {"person_id": 2, "full_name": "Ana B", "canonical_key": "ana-b"},
            ],
            {
                "1": [
                    {
                        "topic_id": 7,
                        "topic_label": "Alpha",
                        "topic_key": "alpha",
                        "as_of_date": "2026-02-02",
                        "computed_method": "combined",
                        "stance": "oppose",
                        "score": 0.2,
                        "confidence": 0.9,
                        "evidence_count": 5,
                        "last_evidence_date": "2026-02-02",
                        "party_id": 10,
                        "party_label": "PSOE",
                        "evidence_breakdown": {"revealed": 5},
                        "review_summary": {"pending": 1},
                    },
                    {
                        "topic_id": 8,
                        "topic_label": "Beta",
                        "topic_key": "beta",
                        "as_of_date": "2026-02-01",
                        "computed_method": "votes",
                        "stance": "support",
                        "score": 0.7,
                        "confidence": 0.6,
                        "evidence_count": 3,
                        "last_evidence_date": "2026-02-01",
                        "party_id": 10,
                        "party_label": "PSOE",
                        "evidence_breakdown": {"revealed": 3},
                        "review_summary": {"resolved": 1},
                    },
                ],
                "2": [
                    {
                        "topic_id": 9,
                        "topic_label": "Gamma",
                        "topic_key": "gamma",
                        "as_of_date": "2026-02-03",
                        "computed_method": "declared",
                        "stance": "mixed",
                        "score": 0.4,
                        "confidence": 0.1,
                        "evidence_count": 1,
                        "last_evidence_date": "2026-02-03",
                        "party_id": 11,
                        "party_label": "PP",
                        "evidence_breakdown": {"declared": 1},
                        "review_summary": {},
                    }
                ],
            },
        )

        self.assertEqual(previews["confidence_desc"][0]["key"], "i-1-7-2026-02-02-combined")
        self.assertEqual(previews["as_of"][0]["key"], "i-2-9-2026-02-03-declared")
        self.assertEqual(previews["topic"][0]["topicLabel"], "Alpha")
        self.assertEqual(previews["party"][0]["partyLabel"], "PP")
        self.assertNotIn("_stable_index", previews["confidence_desc"][0])

    def test_write_person_sort_preview_payloads_writes_per_sort_json(self):
        with TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "stances.json"
            write_person_sort_preview_payloads(
                out_path,
                {
                    "confidence_desc": [{"key": "a"}],
                    "topic": [{"key": "b"}],
                },
            )
            self.assertEqual(
                (out_path.parent / PERSON_SORT_PREVIEW_DIRNAME / "confidence_desc.json").read_text(),
                '[{"key":"a"}]',
            )
            self.assertEqual(
                (out_path.parent / PERSON_SORT_PREVIEW_DIRNAME / "topic.json").read_text(),
                '[{"key":"b"}]',
            )

    def test_build_topic_person_row_payloads_groups_rows_by_topic(self):
        payloads = build_topic_person_row_payloads(
            [
                {"person_id": 1, "full_name": "Ana A", "canonical_key": "ana-a"},
                {"person_id": 2, "full_name": "Bruno B", "canonical_key": "bruno-b"},
            ],
            {
                "1": [
                    {
                        "topic_id": 7,
                        "topic_label": "Alpha",
                        "topic_key": "alpha",
                        "as_of_date": "2026-02-02",
                        "computed_method": "combined",
                        "stance": "oppose",
                        "score": 0.2,
                        "confidence": 0.9,
                        "evidence_count": 5,
                        "last_evidence_date": "2026-02-02",
                        "party_id": 10,
                        "party_label": "PSOE",
                        "evidence_breakdown": {"revealed": 5},
                        "review_summary": {"pending": 1},
                    }
                ],
                "2": [
                    {
                        "topic_id": 7,
                        "topic_label": "Alpha",
                        "topic_key": "alpha",
                        "as_of_date": "2026-02-01",
                        "computed_method": "votes",
                        "stance": "support",
                        "score": 0.7,
                        "confidence": 0.6,
                        "evidence_count": 3,
                        "last_evidence_date": "2026-02-01",
                        "party_id": 11,
                        "party_label": "PP",
                        "evidence_breakdown": {"revealed": 3},
                        "review_summary": {"resolved": 1},
                    }
                ],
            },
        )

        self.assertEqual(list(payloads.keys()), ["7"])
        self.assertEqual([row["personId"] for row in payloads["7"]], [1, 2])
        self.assertEqual(payloads["7"][0]["personName"], "Ana A")
        self.assertNotIn("_stable_index", payloads["7"][0])
        self.assertNotIn("topicId", payloads["7"][0])
        self.assertNotIn("topicLabel", payloads["7"][0])
        self.assertNotIn("scope", payloads["7"][0])

    def test_write_topic_person_row_payloads_writes_per_topic_json(self):
        with TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "stances.json"
            write_topic_person_row_payloads(
                out_path,
                {"7": [{"key": "i-1-7-2026-02-02-combined"}]},
            )
            self.assertEqual(
                (out_path.parent / TOPIC_PERSON_ROWS_DIRNAME / "7.json").read_text(),
                '[{"key":"i-1-7-2026-02-02-combined"}]',
            )

    def test_build_person_trajectory_chunks_adds_filter_metadata(self):
        persons = [
            {"person_id": 1, "point_count": 2, "full_name": "Ana Alpha", "canonical_key": "ana-alpha"},
            {"person_id": 2, "point_count": 1, "full_name": "Bruno Beta", "canonical_key": "bruno-beta"},
        ]
        chunks, payloads = build_person_trajectory_chunks(
            persons,
            {
                "1": [
                    {
                        "topic_label": "Vivienda",
                        "topic_key": "vivienda",
                        "party_label": "PSOE",
                        "computed_method": "combined",
                        "stance": "support",
                    },
                    {
                        "topic_label": "Energía",
                        "topic_key": "energia",
                        "party_label": "PSOE",
                        "computed_method": "votes",
                        "stance": "mixed",
                    },
                ],
                "2": [
                    {
                        "topic_label": "Seguridad",
                        "topic_key": "seguridad",
                        "party_label": "PP",
                        "computed_method": "declared",
                        "stance": "oppose",
                    }
                ],
            },
            chunk_size=2,
        )

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["person_ids"], [1, 2])
        self.assertEqual(chunks[0]["methods"], ["combined", "declared", "votes"])
        self.assertEqual(chunks[0]["stances"], ["mixed", "oppose", "support"])
        self.assertIn("vivienda", chunks[0]["topic_tokens"])
        self.assertIn("energia", chunks[0]["topic_tokens"])
        self.assertIn("psoe", chunks[0]["party_tokens"])
        self.assertIn("pp", chunks[0]["party_tokens"])
        self.assertNotIn("person_tokens", chunks[0])
        self.assertEqual(payloads["chunk-001"]["1"][0]["topic_label"], "Vivienda")

    def test_build_person_search_index_keeps_selective_topic_tokens_and_all_party_maps(self):
        payload = build_person_search_index(
            {
                "chunk-001": {
                    "1": [
                        {
                            "topic_id": 1,
                            "topic_label": "Vivienda social",
                            "topic_key": "vivienda-social",
                            "party_label": "UPN",
                            "computed_method": "combined",
                            "stance": "support",
                        }
                    ]
                },
                "chunk-002": {
                    "2": [
                        {
                            "topic_id": 2,
                            "topic_label": "Vivienda rural",
                            "topic_key": "vivienda-rural",
                            "party_label": "PSOE",
                            "computed_method": "votes",
                            "stance": "oppose",
                        }
                    ]
                },
            },
            snapshot_date="2026-02-12",
            generated_at="2026-03-07T18:00:00+00:00",
            max_topic_chunks=1,
        )

        self.assertEqual(payload["meta"]["snapshot_date"], "2026-02-12")
        self.assertEqual(payload["meta"]["topic_token_max_chunks"], 1)
        self.assertEqual(payload["meta"]["counts"]["topic_ids"], 2)
        self.assertEqual(payload["meta"]["counts"]["topic_tokens"], 2)
        self.assertEqual(payload["meta"]["counts"]["party_tokens"], 2)
        self.assertEqual(payload["meta"]["counts"]["methods"], 2)
        self.assertEqual(payload["meta"]["counts"]["stances"], 2)
        self.assertEqual(payload["topic_ids"]["1"], ["chunk-001"])
        self.assertEqual(payload["topic_ids"]["2"], ["chunk-002"])
        self.assertNotIn("vivienda", payload["topic_tokens"])
        self.assertIn("social", payload["topic_tokens"])
        self.assertEqual(payload["topic_tokens"]["social"], ["chunk-001"])
        self.assertEqual(payload["party_tokens"]["upn"], ["chunk-001"])
        self.assertEqual(payload["methods"]["combined"], ["chunk-001"])
        self.assertEqual(payload["stances"]["oppose"], ["chunk-002"])

    def test_build_person_search_index_drops_non_selective_exact_topic_ids(self):
        payload = build_person_search_index(
            {
                "chunk-001": {
                    "1": [
                        {
                            "topic_id": 7,
                            "topic_label": "Vivienda social",
                            "topic_key": "vivienda-social",
                            "party_label": "UPN",
                            "computed_method": "combined",
                            "stance": "support",
                        }
                    ]
                },
                "chunk-002": {
                    "2": [
                        {
                            "topic_id": 7,
                            "topic_label": "Vivienda social",
                            "topic_key": "vivienda-social",
                            "party_label": "PSOE",
                            "computed_method": "votes",
                            "stance": "oppose",
                        }
                    ]
                },
            },
            snapshot_date="2026-02-12",
            generated_at="2026-03-07T18:00:00+00:00",
            max_topic_chunks=1,
        )

        self.assertEqual(payload["meta"]["counts"]["topic_ids"], 0)
        self.assertEqual(payload["topic_ids"], {})

    def test_build_topic_search_index_keeps_only_selective_topic_tokens(self):
        payload = build_topic_search_index(
            [
                {"topic_id": 1, "topic_label": "Vivienda social", "topic_key": "vivienda-social"},
                {"topic_id": 2, "topic_label": "Vivienda rural", "topic_key": "vivienda-rural"},
                {"topic_id": 3, "topic_label": "Movilidad sostenible", "topic_key": "movilidad-sostenible"},
            ],
            snapshot_date="2026-02-12",
            generated_at="2026-03-07T18:00:00+00:00",
            max_topics=1,
        )

        self.assertEqual(payload["meta"]["snapshot_date"], "2026-02-12")
        self.assertEqual(payload["meta"]["topic_token_max_topics"], 1)
        self.assertEqual(payload["meta"]["counts"]["topic_tokens"], 4)
        self.assertNotIn("vivienda", payload["topic_tokens"])
        self.assertEqual(payload["topic_tokens"]["social"], [1])
        self.assertEqual(payload["topic_tokens"]["rural"], [2])
        self.assertEqual(payload["topic_tokens"]["movilidad"], [3])
        self.assertEqual(payload["topic_tokens"]["sostenible"], [3])

    def test_compact_person_chunk_manifest_drops_filter_arrays(self):
        manifest = compact_person_chunk_manifest(
            [
                {
                    "chunk_id": "chunk-001",
                    "person_count": 2,
                    "point_count_total": 8,
                    "person_ids": [1, 2],
                    "topic_tokens": ["vivienda"],
                    "party_tokens": ["psoe"],
                    "methods": ["combined"],
                    "stances": ["support"],
                }
            ]
        )

        self.assertEqual(
            manifest,
            [
                {
                    "chunk_id": "chunk-001",
                    "person_count": 2,
                    "point_count_total": 8,
                    "person_ids": [1, 2],
                }
            ],
        )

    def test_write_person_search_index_payload_writes_json(self):
        with TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "stances.json"
            write_person_search_index_payload(
                out_path,
                {"meta": {"snapshot_date": "2026-02-12"}, "topic_ids": {"7": ["chunk-001"]}, "topic_tokens": {"social": ["chunk-001"]}},
            )
            self.assertEqual(
                (out_path.parent / PERSON_SEARCH_INDEX_FILENAME).read_text(),
                '{"meta":{"snapshot_date":"2026-02-12"},"topic_ids":{"7":["chunk-001"]},"topic_tokens":{"social":["chunk-001"]}}',
            )

    def test_write_topic_search_index_payload_writes_json(self):
        with TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "stances.json"
            write_topic_search_index_payload(
                out_path,
                {"meta": {"snapshot_date": "2026-02-12"}, "topic_tokens": {"social": [7]}},
            )
            self.assertEqual(
                (out_path.parent / TOPIC_SEARCH_INDEX_FILENAME).read_text(),
                '{"meta":{"snapshot_date":"2026-02-12"},"topic_tokens":{"social":[7]}}',
            )


if __name__ == "__main__":
    unittest.main()
