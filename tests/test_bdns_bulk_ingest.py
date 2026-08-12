from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from collections import deque
from pathlib import Path

from publicdata_connectors_es.money.bdns_bulk import (
    build_bdns_concessions_url,
    parse_bdns_page,
)
from publicdata_core.blobstore import StoredBlob
from publicdata_ops import claim_work_items, complete_work_items
from scripts.ingest_bdns_bulk import (
    PageOutcome,
    _failure_circuit_open,
    _open_runtime,
    _persist_record_version_lineage,
    backfill_record_version_lineage,
    enqueue_bdns_pages,
    persist_bdns_page,
    report_bdns_bulk_run,
)


def _page_payload(page: int, rows: list[dict[str, object]]) -> bytes:
    return json.dumps(
        {
            "content": rows,
            "number": page,
            "size": 2,
            "numberOfElements": len(rows),
            "totalElements": 4,
            "totalPages": 2,
            "first": page == 0,
            "last": page == 1,
        },
        ensure_ascii=True,
    ).encode("utf-8")


def _row(row_id: int, *, entity_prefix: str = "G12345678") -> dict[str, object]:
    return {
        "id": row_id,
        "codConcesion": f"SB{row_id}",
        "fechaConcesion": "2026-08-10",
        "beneficiario": f"{entity_prefix} FUNDACION TEST {row_id}",
        "instrumento": "SUBVENCION",
        "importe": f"{row_id}.25",
        "numeroConvocatoria": f"C{row_id}",
        "idConvocatoria": row_id + 1000,
        "convocatoria": f"Convocatoria {row_id}",
        "nivel1": "AUTONOMICA",
        "nivel2": "ANDALUCIA",
        "nivel3": "CONSEJERIA TEST",
        "idPersona": row_id + 2000,
    }


class TestBdnsBulkIngest(unittest.TestCase):
    def test_version_lineage_preserves_changed_record_without_raw_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            conn = _open_runtime(
                Path(temp_dir) / "versions.db",
                Path("etl/load/sqlite_schema.sql"),
            )
            try:
                raw_first = [_row(1), _row(2)]
                raw_second = [_row(1), _row(2)]
                raw_second[0]["importe"] = "999.25"
                pages = [
                    parse_bdns_page(
                        _page_payload(0, rows),
                        feed_url=build_bdns_concessions_url(page=0, page_size=2),
                        content_type="application/json",
                        expected_page=0,
                        expected_page_size=2,
                    )
                    for rows in (raw_first, raw_second)
                ]
                for index, snapshot_date in enumerate(
                    ("2026-08-11", "2026-08-12"),
                    start=1,
                ):
                    cursor = conn.execute(
                        """
                        INSERT INTO money_bulk_runs (
                          pipeline_id, source_id, source_url, snapshot_date,
                          page_size, total_elements_discovered,
                          total_pages_discovered, pages_enqueued, limited_run,
                          state, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, 2, 2, 1, 1, 1, 'partial', ?, ?)
                        """,
                        (
                            f"version-run-{index}",
                            "bdns_api_subvenciones",
                            build_bdns_concessions_url(page=0, page_size=2),
                            snapshot_date,
                            f"{snapshot_date}T00:00:00+00:00",
                            f"{snapshot_date}T00:00:00+00:00",
                        ),
                    )
                    run_id = int(cursor.lastrowid)
                    cursor = conn.execute(
                        """
                        INSERT INTO money_bulk_page_fetches (
                          money_bulk_run_id, page_number, source_url, fetched_at,
                          content_sha256, content_type, bytes, raw_path,
                          api_total_elements, api_total_pages, records_seen,
                          records_loaded, created_at, updated_at
                        ) VALUES (?, 0, ?, ?, ?, 'application/json', 1, ?, 2, 1, 2, 2, ?, ?)
                        """,
                        (
                            run_id,
                            build_bdns_concessions_url(page=0, page_size=2),
                            f"{snapshot_date}T00:00:00+00:00",
                            f"{index:064x}",
                            f"page-{index}.json",
                            f"{snapshot_date}T00:00:00+00:00",
                            f"{snapshot_date}T00:00:00+00:00",
                        ),
                    )
                    page_fetch_id = int(cursor.lastrowid)
                    self.assertEqual(
                        _persist_record_version_lineage(
                            conn,
                            bulk_run_id=run_id,
                            page_fetch_id=page_fetch_id,
                            snapshot_date=snapshot_date,
                            records=pages[index - 1].records,
                            observed_at=f"{snapshot_date}T00:00:00+00:00",
                        ),
                        2,
                    )
                conn.commit()
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM money_source_record_versions"
                    ).fetchone()[0],
                    3,
                )
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM money_bulk_record_sightings"
                    ).fetchone()[0],
                    4,
                )
                version_columns = {
                    str(row[1])
                    for row in conn.execute(
                        "PRAGMA table_info(money_source_record_versions)"
                    )
                }
                self.assertNotIn("raw_payload", version_columns)
                self.assertNotIn("raw_json", version_columns)
            finally:
                conn.close()

    def test_failure_circuit_requires_sustained_rolling_window(self) -> None:
        recent: deque[bool] = deque(maxlen=20)
        recent.extend([False] * 7 + [True])
        self.assertFalse(
            _failure_circuit_open(
                recent,
                stop_failure_rate=0.5,
                window_size=20,
            )
        )
        recent.extend([False] * 2 + [True] * 10)
        self.assertTrue(
            _failure_circuit_open(
                recent,
                stop_failure_rate=0.5,
                window_size=20,
            )
        )

    def test_failure_circuit_does_not_open_on_zero_failures_at_zero_threshold(
        self,
    ) -> None:
        recent = deque([False] * 20, maxlen=20)
        self.assertFalse(
            _failure_circuit_open(
                recent,
                stop_failure_rate=0.0,
                window_size=20,
            )
        )

    def test_live_page_shape_maps_identifiers_and_metadata(self) -> None:
        url = build_bdns_concessions_url(page=0, page_size=2)
        page = parse_bdns_page(
            _page_payload(0, [_row(1), _row(2)]),
            feed_url=url,
            content_type="application/json",
            expected_page=0,
            expected_page_size=2,
        )
        self.assertEqual(page.total_elements, 4)
        self.assertEqual(len(page.records), 2)
        first = page.records[0]
        self.assertEqual(first["beneficiario"], "FUNDACION TEST 1")
        self.assertEqual(first["beneficiario_id"], "G12345678")
        self.assertEqual(first["beneficiary_entity_type"], "legal_entity")
        self.assertEqual(first["concesion_id"], "SB1")
        self.assertEqual(first["convocatoria_id"], "C1")
        self.assertIn("/concesiones/SB1", str(first["source_url"]))

    def test_page_metadata_mismatch_fails_closed(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "page mismatch"):
            parse_bdns_page(
                _page_payload(1, [_row(3), _row(4)]),
                feed_url=build_bdns_concessions_url(page=0, page_size=2),
                content_type="application/json",
                expected_page=0,
                expected_page_size=2,
            )

    def test_empty_official_page_is_valid(self) -> None:
        payload = json.dumps(
            {
                "content": [],
                "number": 0,
                "size": 1000,
                "numberOfElements": 0,
                "totalElements": 0,
                "totalPages": 0,
                "first": True,
                "last": True,
            }
        ).encode("utf-8")
        page = parse_bdns_page(
            payload,
            feed_url=build_bdns_concessions_url(page=0, page_size=1000),
            content_type="application/json",
            expected_page=0,
            expected_page_size=1000,
        )
        self.assertEqual(page.records, [])
        self.assertEqual(page.total_elements, 0)

    def test_two_page_queue_persists_and_reconciles_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "bdns.db"
            conn = _open_runtime(db_path, Path("etl/load/sqlite_schema.sql"))
            try:
                first_payload = _page_payload(0, [_row(1), _row(2)])

                def fetch_first(url: str, timeout: int) -> tuple[bytes, str]:
                    self.assertGreater(timeout, 0)
                    self.assertIn("page=0", url)
                    return first_payload, "application/json"

                initial = enqueue_bdns_pages(
                    conn,
                    pipeline_id="bdns-test",
                    snapshot_date="2026-08-11",
                    page_size=2,
                    max_pages=1,
                    timeout=10,
                    fetch_bytes=fetch_first,
                )
                self.assertEqual(initial["queue"]["inserted_total"], 1)
                self.assertTrue(initial["discovery"]["limited_run"])
                expanded = enqueue_bdns_pages(
                    conn,
                    pipeline_id="bdns-test",
                    snapshot_date="2026-08-11",
                    page_size=2,
                    max_pages=0,
                    timeout=10,
                    fetch_bytes=fetch_first,
                )
                self.assertEqual(expanded["queue"]["inserted_total"], 1)
                self.assertEqual(expanded["queue"]["pipeline_total"], 2)
                self.assertFalse(expanded["discovery"]["limited_run"])
                again = enqueue_bdns_pages(
                    conn,
                    pipeline_id="bdns-test",
                    snapshot_date="2026-08-11",
                    page_size=2,
                    max_pages=0,
                    timeout=10,
                    fetch_bytes=fetch_first,
                )
                self.assertEqual(again["queue"]["inserted_total"], 0)

                claimed = claim_work_items(
                    conn,
                    pipeline_id="bdns-test",
                    worker_id="test-worker",
                    limit=2,
                    lease_seconds=60,
                )
                self.assertEqual(len(claimed), 2)
                for item in claimed:
                    item_payload = dict(item["payload"])
                    page_number = int(item_payload["page_number"])
                    payload = _page_payload(
                        page_number,
                        [_row(page_number * 2 + 1), _row(page_number * 2 + 2)],
                    )
                    raw_path = root / f"page-{page_number}.json"
                    raw_path.write_bytes(payload)
                    parsed = parse_bdns_page(
                        payload,
                        feed_url=str(item_payload["source_url"]),
                        content_type="application/json",
                        expected_page=page_number,
                        expected_page_size=2,
                    )
                    outcome = PageOutcome(
                        work_item_id=int(item["work_item_id"]),
                        page_number=page_number,
                        source_url=str(item_payload["source_url"]),
                        stored=StoredBlob(
                            content_sha256=hashlib.sha256(payload).hexdigest(),
                            bytes=len(payload),
                            path=raw_path,
                            content_type="application/json",
                            etag=None,
                            last_modified=None,
                            deduplicated=False,
                        ),
                        page=parsed,
                        error=None,
                        retryable=True,
                    )
                    loaded = persist_bdns_page(
                        conn,
                        outcome=outcome,
                        snapshot_date="2026-08-11",
                        bulk_run_id=int(item_payload["money_bulk_run_id"]),
                    )
                    self.assertEqual(loaded, 2)
                    self.assertEqual(
                        complete_work_items(
                            conn,
                            worker_id="test-worker",
                            work_item_ids=[int(item["work_item_id"])],
                        ),
                        1,
                    )

                report = report_bdns_bulk_run(
                    conn,
                    pipeline_id="bdns-test",
                    finalize=True,
                )
                self.assertEqual(report["status"], "succeeded")
                self.assertTrue(report["analytical_ingest_gate_passed"])
                self.assertTrue(report["promotion_gate_passed"])
                self.assertEqual(report["observed"]["records_seen"], 4)
                self.assertEqual(report["observed"]["records_loaded_distinct"], 4)
                self.assertTrue(all(report["checks"].values()))
                self.assertEqual(report["record_versions"]["sightings_total"], 4)
                self.assertEqual(report["record_versions"]["versions_linked"], 4)
                self.assertFalse(report["record_versions"]["raw_payload_duplicated"])
                self.assertEqual(
                    report["publication_status"],
                    "local_raw_captured_not_published",
                )
                self.assertTrue(
                    any(
                        "retained exactly" in limitation
                        for limitation in report["limitations"]
                    )
                )
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM money_subsidy_records"
                    ).fetchone()[0],
                    4,
                )

                conn.execute("DELETE FROM money_bulk_record_sightings")
                conn.execute("DELETE FROM money_source_record_versions")
                conn.commit()
                before_backfill = report_bdns_bulk_run(
                    conn,
                    pipeline_id="bdns-test",
                    finalize=False,
                )
                self.assertFalse(before_backfill["analytical_ingest_gate_passed"])
                backfilled = backfill_record_version_lineage(
                    conn,
                    pipeline_id="bdns-test",
                )
                self.assertEqual(backfilled["version_backfill"]["pages_processed"], 2)
                self.assertEqual(backfilled["version_backfill"]["records_versioned"], 4)
                self.assertTrue(backfilled["analytical_ingest_gate_passed"])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
