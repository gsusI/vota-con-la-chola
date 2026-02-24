from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources as seed_parl_sources
from etl.politicos_es.util import now_utc_iso, sha256_bytes
from scripts import graph_ui_server as g


class TestGraphUiServerInitdocTail(unittest.TestCase):
    def _seed_minimal_initiative(self, conn, *, initiative_id: str, expediente: str) -> None:
        now_iso = now_utc_iso()
        conn.execute(
            """
            INSERT INTO parl_initiatives (
              initiative_id, legislature, expediente, title,
              source_id, source_url, raw_payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                initiative_id,
                "15",
                expediente,
                "Iniciativa test",
                "senado_iniciativas",
                "https://www.senado.es/",
                "{}",
                now_iso,
                now_iso,
            ),
        )

    def _insert_missing_global_doc(self, conn, *, initiative_id: str) -> str:
        now_iso = now_utc_iso()
        global_url = (
            f"https://www.senado.es/legis15/expedientes/600/enmiendas/"
            f"global_enmiendas_vetos_15_{initiative_id.split('/')[-1]}.xml"
        )
        conn.execute(
            """
            INSERT INTO parl_initiative_documents (
              initiative_id, doc_kind, doc_url, source_record_pk, created_at, updated_at
            ) VALUES (?, 'bocg', ?, NULL, ?, ?)
            """,
            (initiative_id, global_url, now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO document_fetches (
              doc_url, source_id, first_attempt_at, last_attempt_at, attempts, fetched_ok, last_http_status
            ) VALUES (?, 'parl_initiative_docs', ?, ?, 1, 0, 404)
            ON CONFLICT(doc_url) DO UPDATE SET
              last_attempt_at = excluded.last_attempt_at,
              attempts = excluded.attempts,
              fetched_ok = excluded.fetched_ok,
              last_http_status = excluded.last_http_status
            """,
            (global_url, now_iso, now_iso),
        )
        return global_url

    def _insert_redundant_alt_doc(self, conn, *, initiative_id: str) -> None:
        now_iso = now_utc_iso()
        raw_payload = '{"kind":"detail"}'
        source_record_id = f"parl_initiative_docs:{initiative_id}:detail"
        conn.execute(
            """
            INSERT INTO source_records (
              source_id, source_record_id, source_snapshot_date, raw_payload, content_sha256, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "parl_initiative_docs",
                source_record_id,
                "2026-02-22",
                raw_payload,
                sha256_bytes(raw_payload.encode("utf-8")),
                now_iso,
                now_iso,
            ),
        )
        source_record_pk = int(
            conn.execute(
                """
                SELECT source_record_pk
                FROM source_records
                WHERE source_id = 'parl_initiative_docs' AND source_record_id = ?
                """,
                (source_record_id,),
            ).fetchone()["source_record_pk"]
        )

        detail_url = (
            "https://www.senado.es/web/ficopendataservlet"
            f"?legis=15&tipoFich=3&tipoEx=600&numEx={initiative_id.split('/')[-1]}"
        )
        conn.execute(
            """
            INSERT INTO parl_initiative_documents (
              initiative_id, doc_kind, doc_url, source_record_pk, created_at, updated_at
            ) VALUES (?, 'bocg', ?, ?, ?, ?)
            """,
            (initiative_id, detail_url, source_record_pk, now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO text_documents (
              source_id, source_url, source_record_pk, fetched_at, content_type, bytes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "parl_initiative_docs",
                detail_url,
                source_record_pk,
                now_iso,
                "application/xml",
                123,
                now_iso,
                now_iso,
            ),
        )

    def _write_heartbeat_jsonl(self, path: Path, rows: list[dict[str, object]]) -> None:
        lines = [json.dumps(r) for r in rows]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _build_payload(
        self,
        db_path: Path,
        tracker_path: Path,
        *,
        heartbeat_path: Path | None = None,
        compacted_heartbeat_path: Path | None = None,
        compact_window_digest_heartbeat_path: Path | None = None,
        compact_window_digest_heartbeat_compacted_path: Path | None = None,
    ) -> dict[str, object]:
        old_tracker_path = g.TRACKER_PATH
        old_waivers_path = g.MISMATCH_WAIVERS_PATH
        old_heartbeat_path = g.DEFAULT_INITDOC_ACTIONABLE_TAIL_HEARTBEAT_PATH
        old_compacted_heartbeat_path = g.DEFAULT_INITDOC_ACTIONABLE_TAIL_HEARTBEAT_COMPACTED_PATH
        old_compact_window_digest_heartbeat_path = (
            g.DEFAULT_INITDOC_ACTIONABLE_TAIL_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_PATH
        )
        old_compact_window_digest_heartbeat_compacted_path = (
            g.DEFAULT_INITDOC_ACTIONABLE_TAIL_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACTED_PATH
        )
        try:
            g._load_tracker_items_cached.cache_clear()
            g.TRACKER_PATH = tracker_path
            g.MISMATCH_WAIVERS_PATH = tracker_path.parent / "waivers-missing.json"
            if heartbeat_path is not None:
                g.DEFAULT_INITDOC_ACTIONABLE_TAIL_HEARTBEAT_PATH = heartbeat_path
            if compacted_heartbeat_path is not None:
                g.DEFAULT_INITDOC_ACTIONABLE_TAIL_HEARTBEAT_COMPACTED_PATH = compacted_heartbeat_path
            if compact_window_digest_heartbeat_path is not None:
                g.DEFAULT_INITDOC_ACTIONABLE_TAIL_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_PATH = (
                    compact_window_digest_heartbeat_path
                )
            if compact_window_digest_heartbeat_compacted_path is not None:
                g.DEFAULT_INITDOC_ACTIONABLE_TAIL_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACTED_PATH = (
                    compact_window_digest_heartbeat_compacted_path
                )
            return g.build_sources_status_payload(db_path)
        finally:
            g.TRACKER_PATH = old_tracker_path
            g.MISMATCH_WAIVERS_PATH = old_waivers_path
            g.DEFAULT_INITDOC_ACTIONABLE_TAIL_HEARTBEAT_PATH = old_heartbeat_path
            g.DEFAULT_INITDOC_ACTIONABLE_TAIL_HEARTBEAT_COMPACTED_PATH = old_compacted_heartbeat_path
            g.DEFAULT_INITDOC_ACTIONABLE_TAIL_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_PATH = (
                old_compact_window_digest_heartbeat_path
            )
            g.DEFAULT_INITDOC_ACTIONABLE_TAIL_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACTED_PATH = (
                old_compact_window_digest_heartbeat_compacted_path
            )
            g._load_tracker_items_cached.cache_clear()

    def test_initdoc_tail_digest_failed_when_actionable_missing_exists(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "status.db"
            tracker_path = td_path / "tracker.md"
            tracker_path.write_text(
                "# Tracker\n\n"
                "| Tipo de dato | Dominio | Fuentes objetivo | Estado | Bloque principal |\n"
                "|---|---|---|---|---|\n",
                encoding="utf-8",
            )

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                initiative_id = "senado:leg15:exp:600/000901"
                self._seed_minimal_initiative(conn, initiative_id=initiative_id, expediente="600/000901")
                self._insert_missing_global_doc(conn, initiative_id=initiative_id)
                conn.commit()
            finally:
                conn.close()

            payload = self._build_payload(db_path, tracker_path)
            tail = payload.get("initdoc_actionable_tail", {})
            digest = tail.get("digest", {}) if isinstance(tail, dict) else {}
            totals = digest.get("totals", {}) if isinstance(digest, dict) else {}
            self.assertEqual(str(digest.get("status") or ""), "failed")
            self.assertEqual(int(totals.get("actionable_missing") or 0), 1)

    def test_initdoc_tail_digest_ok_when_only_redundant_missing_exists(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "status.db"
            tracker_path = td_path / "tracker.md"
            tracker_path.write_text(
                "# Tracker\n\n"
                "| Tipo de dato | Dominio | Fuentes objetivo | Estado | Bloque principal |\n"
                "|---|---|---|---|---|\n",
                encoding="utf-8",
            )

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                initiative_id = "senado:leg15:exp:600/000902"
                self._seed_minimal_initiative(conn, initiative_id=initiative_id, expediente="600/000902")
                self._insert_missing_global_doc(conn, initiative_id=initiative_id)
                self._insert_redundant_alt_doc(conn, initiative_id=initiative_id)
                conn.commit()
            finally:
                conn.close()

            payload = self._build_payload(db_path, tracker_path)
            tail = payload.get("initdoc_actionable_tail", {})
            digest = tail.get("digest", {}) if isinstance(tail, dict) else {}
            totals = digest.get("totals", {}) if isinstance(digest, dict) else {}
            self.assertEqual(str(digest.get("status") or ""), "ok")
            self.assertEqual(int(totals.get("actionable_missing") or 0), 0)
            self.assertEqual(int(totals.get("redundant_missing") or 0), 1)

    def test_initdoc_tail_heartbeat_window_embedded_in_payload(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "status.db"
            tracker_path = td_path / "tracker.md"
            heartbeat_path = td_path / "heartbeat.jsonl"
            compacted_path = td_path / "heartbeat.compacted.jsonl"
            compact_digest_heartbeat_path = td_path / "compact_digest_heartbeat.jsonl"
            compact_digest_heartbeat_compacted_path = td_path / "compact_digest_heartbeat.compacted.jsonl"
            tracker_path.write_text(
                "# Tracker\n\n"
                "| Tipo de dato | Dominio | Fuentes objetivo | Estado | Bloque principal |\n"
                "|---|---|---|---|---|\n",
                encoding="utf-8",
            )

            self._write_heartbeat_jsonl(
                heartbeat_path,
                [
                    {
                        "run_at": "2026-02-23T09:00:00+00:00",
                        "heartbeat_id": "hb-00",
                        "status": "ok",
                        "strict_fail_count": 0,
                        "strict_fail_reasons": [],
                    },
                    {
                        "run_at": "2026-02-23T09:01:00+00:00",
                        "heartbeat_id": "hb-01",
                        "status": "failed",
                        "strict_fail_count": 1,
                        "strict_fail_reasons": ["actionable_missing_exceeds_threshold:1>0"],
                    },
                ],
            )
            self._write_heartbeat_jsonl(
                compacted_path,
                [
                    {
                        "run_at": "2026-02-23T09:01:00+00:00",
                        "heartbeat_id": "hb-01",
                        "status": "failed",
                        "strict_fail_count": 1,
                        "strict_fail_reasons": ["actionable_missing_exceeds_threshold:1>0"],
                    }
                ],
            )
            self._write_heartbeat_jsonl(
                compact_digest_heartbeat_path,
                [
                    {
                        "run_at": "2026-02-23T09:00:00+00:00",
                        "heartbeat_id": "hb-cwdh-00",
                        "status": "ok",
                        "risk_level": "green",
                        "strict_fail_count": 0,
                        "risk_reason_count": 0,
                        "strict_fail_reasons": [],
                        "risk_reasons": [],
                    },
                    {
                        "run_at": "2026-02-23T09:01:00+00:00",
                        "heartbeat_id": "hb-cwdh-01",
                        "status": "failed",
                        "risk_level": "red",
                        "strict_fail_count": 1,
                        "risk_reason_count": 0,
                        "strict_fail_reasons": ["incident_missing_in_compacted"],
                        "risk_reasons": [],
                    },
                ],
            )
            self._write_heartbeat_jsonl(
                compact_digest_heartbeat_compacted_path,
                [
                    {
                        "run_at": "2026-02-23T09:01:00+00:00",
                        "heartbeat_id": "hb-cwdh-01",
                        "status": "failed",
                        "risk_level": "red",
                        "strict_fail_count": 1,
                        "risk_reason_count": 0,
                        "strict_fail_reasons": ["incident_missing_in_compacted"],
                        "risk_reasons": [],
                    }
                ],
            )

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                initiative_id = "senado:leg15:exp:600/000903"
                self._seed_minimal_initiative(conn, initiative_id=initiative_id, expediente="600/000903")
                self._insert_missing_global_doc(conn, initiative_id=initiative_id)
                self._insert_redundant_alt_doc(conn, initiative_id=initiative_id)
                conn.commit()
            finally:
                conn.close()

            payload = self._build_payload(
                db_path,
                tracker_path,
                heartbeat_path=heartbeat_path,
                compacted_heartbeat_path=compacted_path,
                compact_window_digest_heartbeat_path=compact_digest_heartbeat_path,
                compact_window_digest_heartbeat_compacted_path=compact_digest_heartbeat_compacted_path,
            )
            tail = payload.get("initdoc_actionable_tail", {})
            heartbeat_window = tail.get("heartbeat_window", {}) if isinstance(tail, dict) else {}
            compact_window = tail.get("heartbeat_compaction_window", {}) if isinstance(tail, dict) else {}
            compact_window_digest = tail.get("heartbeat_compaction_window_digest", {}) if isinstance(tail, dict) else {}
            compact_window_digest_heartbeat_window = (
                tail.get("heartbeat_compaction_window_digest_heartbeat_window", {}) if isinstance(tail, dict) else {}
            )
            compact_window_digest_heartbeat_compaction_window = (
                tail.get("heartbeat_compaction_window_digest_heartbeat_compaction_window", {})
                if isinstance(tail, dict)
                else {}
            )
            compact_window_digest_heartbeat_compaction_window_digest = (
                tail.get("heartbeat_compaction_window_digest_heartbeat_compaction_window_digest", {})
                if isinstance(tail, dict)
                else {}
            )
            self.assertEqual(int(heartbeat_window.get("entries_in_window") or 0), 2)
            self.assertEqual(str(heartbeat_window.get("status") or ""), "failed")
            status_counts = heartbeat_window.get("status_counts", {})
            self.assertEqual(int(status_counts.get("failed") or 0), 1)
            self.assertEqual(int(compact_window.get("window_raw_entries") or 0), 2)
            self.assertEqual(str(compact_window.get("status") or ""), "degraded")
            self.assertEqual(str(compact_window_digest.get("status") or ""), "degraded")
            self.assertEqual(str(compact_window_digest.get("risk_level") or ""), "amber")
            self.assertEqual(int(compact_window_digest_heartbeat_window.get("entries_in_window") or 0), 2)
            self.assertEqual(str(compact_window_digest_heartbeat_window.get("status") or ""), "failed")
            self.assertEqual(str(compact_window_digest_heartbeat_compaction_window.get("status") or ""), "degraded")
            self.assertEqual(
                str(compact_window_digest_heartbeat_compaction_window_digest.get("status") or ""),
                "degraded",
            )
            self.assertEqual(
                str(compact_window_digest_heartbeat_compaction_window_digest.get("risk_level") or ""),
                "amber",
            )


if __name__ == "__main__":
    unittest.main()
