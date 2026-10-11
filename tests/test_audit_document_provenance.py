from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.audit_document_provenance import (
    ProvenanceAuditError,
    create_work_database,
    load_xlsx_document_lineage_manifest,
    run_audit,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REAL_EVIDENCE_ROOT = (
    PROJECT_ROOT / "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence"
)
REAL_PROVENANCE_REPORT = REAL_EVIDENCE_ROOT / "real-document-provenance-audit.json"
REAL_PROVENANCE_MANIFEST = (
    PROJECT_ROOT / "etl/data/manifests/real-document-provenance-files.jsonl"
)
REAL_XLSX_COHORT = REAL_EVIDENCE_ROOT / "real-xlsx-cohort.json"
REAL_XLSX_LINEAGE = REAL_EVIDENCE_ROOT / "real-xlsx-source-lineage.jsonl"


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class TestAuditDocumentProvenance(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp.name)
        self.raw_root = self.repo_root / "raw"
        self.raw_root.mkdir()
        self.manifest = self.repo_root / "inventory.jsonl"
        self.database = self.repo_root / "source.db"
        self.file_manifest = self.repo_root / "provenance-files.jsonl"
        self.edge_manifest = self.repo_root / "provenance-edges.jsonl"
        self.report = self.repo_root / "report.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_inventory(self, files: dict[str, bytes]) -> None:
        rows = []
        for relative, payload in files.items():
            path = self.raw_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            parts = relative.split("/")
            source_group = (
                "/".join(parts[:2]) if parts[0] == "text_documents" else parts[0]
            )
            rows.append(
                {
                    "path": relative,
                    "source_group": source_group,
                    "extension": path.suffix.lstrip("."),
                    "bytes": len(payload),
                    "sha256": digest(payload),
                    "status": "ok",
                    "real_data_status": "eligible_real_capture",
                }
            )
        self.manifest.write_text(
            "".join(json.dumps(row) + "\n" for row in rows),
            encoding="utf-8",
        )

    def create_database(self, rows: list[tuple[object, ...]]) -> None:
        connection = sqlite3.connect(self.database)
        connection.execute(
            """
            CREATE TABLE text_documents (
              raw_path TEXT,
              content_sha256 TEXT,
              source_id TEXT,
              source_url TEXT,
              fetched_at TEXT,
              bytes INTEGER,
              text_path TEXT,
              text_sha256 TEXT
            )
            """
        )
        connection.executemany(
            "INSERT INTO text_documents VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        connection.commit()
        connection.close()

    def execute_audit(
        self,
        provenance_manifests: list[Path] | None = None,
        published_capture_indexes: list[Path] | None = None,
        party_program_source_manifests: list[Path] | None = None,
        archived_document_lineage_manifests: list[Path] | None = None,
        wayback_document_lineage_manifests: list[Path] | None = None,
        boe_document_corpus_lineage_manifests: list[Path] | None = None,
        captured_link_document_lineage_manifests: list[Path] | None = None,
        official_document_identifier_lineage_manifests: list[Path] | None = None,
        official_path_document_lineage_manifests: list[Path] | None = None,
        xlsx_document_lineage_manifests: list[Path] | None = None,
    ) -> dict[str, object]:
        return run_audit(
            repo_root=self.repo_root,
            inventory_root=self.raw_root,
            inventory_manifest=self.manifest,
            database_paths=[self.database],
            provenance_manifest_paths=provenance_manifests or [],
            published_capture_index_paths=published_capture_indexes or [],
            party_program_source_manifest_paths=(party_program_source_manifests or []),
            archived_document_lineage_manifest_paths=(
                archived_document_lineage_manifests or []
            ),
            wayback_document_lineage_manifest_paths=(
                wayback_document_lineage_manifests or []
            ),
            boe_document_corpus_lineage_manifest_paths=(
                boe_document_corpus_lineage_manifests or []
            ),
            captured_link_document_lineage_manifest_paths=(
                captured_link_document_lineage_manifests or []
            ),
            official_document_identifier_lineage_manifest_paths=(
                official_document_identifier_lineage_manifests or []
            ),
            official_path_document_lineage_manifest_paths=(
                official_path_document_lineage_manifests or []
            ),
            xlsx_document_lineage_manifest_paths=(
                xlsx_document_lineage_manifests or []
            ),
            file_manifest_out=self.file_manifest,
            edge_manifest_out=self.edge_manifest,
            report_out=self.report,
        )

    def test_current_real_xlsx_mappings_remain_unverified_provenance(self) -> None:
        required = (
            REAL_PROVENANCE_REPORT,
            REAL_PROVENANCE_MANIFEST,
            REAL_XLSX_COHORT,
            REAL_XLSX_LINEAGE,
        )
        if not all(path.is_file() for path in required):
            self.skipTest(
                "real full-corpus artifacts are excluded from this test context"
            )

        report = json.loads(REAL_PROVENANCE_REPORT.read_text(encoding="utf-8"))
        cohort = json.loads(REAL_XLSX_COHORT.read_text(encoding="utf-8"))
        lineage_rows = [
            json.loads(line)
            for line in REAL_XLSX_LINEAGE.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        lineage_paths = {
            str(row["capture"]["path"]).removeprefix("etl/data/raw/")
            for row in lineage_rows
        }
        provenance_xlsx_rows = []
        with REAL_PROVENANCE_MANIFEST.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row["extension"] == "xlsx":
                    provenance_xlsx_rows.append(row)

        self.assertEqual(report["schema_version"], "real_document_provenance_audit_v13")
        self.assertEqual(report["status"], "partial")
        self.assertTrue(report["checks"]["integrity_passed"])
        self.assertFalse(report["checks"]["complete_checksum_provenance"])
        self.assertFalse(report["checks"]["promotion_ready"])
        self.assertEqual(cohort["schema_version"], "real_xlsx_cohort_v2")
        self.assertEqual(cohort["status"], "mapped_unverified")
        self.assertEqual(
            cohort["bounded_execution"]["inventory_input_ordering"],
            "strict_path_order_verified",
        )
        self.assertFalse(
            cohort["bounded_execution"]["lineage_rows_materialized_in_memory"]
        )
        self.assertEqual(
            cohort["bounded_execution"]["distinct_content_tracking"],
            "sqlite_disk_backed",
        )
        self.assertFalse(cohort["policy"]["synthetic_or_mock_records_counted"])
        self.assertTrue(
            cohort["policy"][
                "official_public_domain_personal_information_retained"
            ]
        )
        self.assertTrue(
            cohort["policy"][
                "path_inferred_source_urls_are_not_checksum_proven_provenance"
            ]
        )
        self.assertEqual(
            cohort["totals"]["checksum_bound_retrieval_receipts"], 0
        )
        self.assertEqual(len(lineage_rows), cohort["totals"]["file_instances"])
        self.assertEqual(
            len({row["capture"]["sha256"] for row in lineage_rows}),
            cohort["totals"]["distinct_content_objects"],
        )
        self.assertEqual(cohort["manifest"]["rows"], len(lineage_rows))
        self.assertEqual(cohort["manifest"]["bytes"], REAL_XLSX_LINEAGE.stat().st_size)
        self.assertEqual(
            cohort["manifest"]["sha256"], digest(REAL_XLSX_LINEAGE.read_bytes())
        )
        for row in lineage_rows:
            self.assertEqual(
                row["schema_version"], "official_xlsx_source_mapping_v1"
            )
            self.assertEqual(
                row["source_url_binding_status"],
                "inferred_from_repository_path_contract_without_retrieval_receipt",
            )
            self.assertFalse(row["synthetic_or_mock_records_counted"])
            self.assertTrue(
                row["official_public_domain_personal_information_retained"]
            )

        self.assertEqual(
            {row["path"] for row in provenance_xlsx_rows}, lineage_paths
        )
        self.assertEqual(len(provenance_xlsx_rows), len(lineage_rows))
        unlinked_xlsx_rows = 0
        for row in provenance_xlsx_rows:
            self.assertIn(
                row["provenance_status"], {"unlinked", "verified_path_checksum"}
            )
            if row["provenance_status"] == "unlinked":
                unlinked_xlsx_rows += 1
                self.assertEqual(row["provenance_edges"], 0)
                self.assertEqual(row["public_url_edges"], 0)
            else:
                self.assertGreater(row["provenance_edges"], 0)
                self.assertGreater(row["public_url_edges"], 0)
            self.assertFalse(row["checksum_conflict"])
            self.assertFalse(row["declared_bytes_conflict"])
        self.assertGreater(unlinked_xlsx_rows, 0)
        self.assertGreaterEqual(report["totals"]["unlinked"], unlinked_xlsx_rows)

        xlsx_audit = report["xlsx_document_lineage_manifests"]
        self.assertEqual(len(xlsx_audit), 1)
        self.assertEqual(xlsx_audit[0]["status"], "partial")
        self.assertEqual(xlsx_audit[0]["rows"], len(lineage_rows))
        self.assertEqual(xlsx_audit[0]["accepted_checksum_captures"], 0)
        self.assertEqual(xlsx_audit[0]["verified_retrieval_receipts"], 0)
        self.assertEqual(xlsx_audit[0]["verified_retrieval_receipt_samples"], [])
        self.assertEqual(
            xlsx_audit[0]["inferred_source_url_mappings"], len(lineage_rows)
        )
        self.assertEqual(xlsx_audit[0]["sha256"], cohort["manifest"]["sha256"])

    def test_verified_label_without_receipt_fails_closed_on_real_xlsx(self) -> None:
        if not REAL_XLSX_LINEAGE.is_file():
            self.skipTest("real XLSX lineage is excluded from this test context")
        real_row = next(
            json.loads(line)
            for line in REAL_XLSX_LINEAGE.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        real_capture = PROJECT_ROOT / str(real_row["capture"]["path"])
        if not real_capture.is_file():
            self.skipTest("real XLSX capture is excluded from this test context")
        raw_root = self.repo_root / "etl/data/raw"
        relative = str(real_row["capture"]["path"]).removeprefix("etl/data/raw/")
        copied_capture = raw_root / relative
        copied_capture.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(real_capture, copied_capture)
        corrupted_row = dict(real_row)
        corrupted_row["source_url_binding_status"] = "verified_retrieval_receipt"
        corrupted_manifest = self.repo_root / "real-xlsx-lineage-corrupted.jsonl"
        corrupted_manifest.write_text(
            json.dumps(corrupted_row, ensure_ascii=True, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        work = create_work_database(self.repo_root / "xlsx-audit.sqlite")
        try:
            with self.assertRaisesRegex(
                ProvenanceAuditError,
                "missing retrieval receipt descriptor",
            ):
                load_xlsx_document_lineage_manifest(
                    work,
                    corrupted_manifest,
                    repo_root=self.repo_root,
                    inventory_root=raw_root,
                )
        finally:
            work.close()

    def test_verified_receipt_hash_corruption_fails_closed_on_real_xlsx(
        self,
    ) -> None:
        if not REAL_XLSX_LINEAGE.is_file() or not REAL_XLSX_COHORT.is_file():
            self.skipTest("real XLSX evidence is excluded from this test context")
        real_row = next(
            json.loads(line)
            for line in REAL_XLSX_LINEAGE.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        real_capture = PROJECT_ROOT / str(real_row["capture"]["path"])
        if not real_capture.is_file():
            self.skipTest("real XLSX capture is excluded from this test context")
        raw_root = self.repo_root / "etl/data/raw"
        relative = str(real_row["capture"]["path"]).removeprefix("etl/data/raw/")
        copied_capture = raw_root / relative
        copied_capture.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(real_capture, copied_capture)
        receipt_path = self.repo_root / "evidence/real-xlsx-cohort.json"
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REAL_XLSX_COHORT, receipt_path)
        corrupted_row = dict(real_row)
        corrupted_row["source_url_binding_status"] = "verified_retrieval_receipt"
        corrupted_row["retrieval_receipt"] = {
            "path": receipt_path.relative_to(self.repo_root).as_posix(),
            "bytes": receipt_path.stat().st_size,
            "sha256": "0" * 64,
        }
        corrupted_manifest = self.repo_root / "real-xlsx-receipt-hash-corrupted.jsonl"
        corrupted_manifest.write_text(
            json.dumps(corrupted_row, ensure_ascii=True, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        work = create_work_database(self.repo_root / "xlsx-hash-audit.sqlite")
        try:
            with self.assertRaisesRegex(
                ProvenanceAuditError,
                "receipt descriptor mismatch",
            ):
                load_xlsx_document_lineage_manifest(
                    work,
                    corrupted_manifest,
                    repo_root=self.repo_root,
                    inventory_root=raw_root,
                )
        finally:
            work.close()

    def test_reconciles_exact_and_content_addressed_paths_without_hiding_gaps(
        self,
    ) -> None:
        exact = b"official-pdf"
        moved = b"official-xml"
        unlinked = b"official-html-with-missing-lineage"
        text = b"extracted official text"
        self.write_inventory(
            {
                "source/exact.pdf": exact,
                "source/moved.xml": moved,
                "source/unlinked.html": unlinked,
            }
        )
        text_path = self.repo_root / "derived" / "exact.txt.gz"
        text_path.parent.mkdir()
        with gzip.open(text_path, "wb") as handle:
            handle.write(text)
        self.create_database(
            [
                (
                    "raw/source/exact.pdf",
                    digest(exact),
                    "official_documents",
                    "https://public.example.es/exact.pdf",
                    "2026-08-12T00:00:00Z",
                    len(exact),
                    "derived/exact.txt.gz",
                    digest(text),
                ),
                (
                    "raw/old/location.xml",
                    digest(moved),
                    "official_documents",
                    "https://public.example.es/moved.xml",
                    "2026-08-12T00:00:00Z",
                    len(moved),
                    None,
                    None,
                ),
            ]
        )

        report = self.execute_audit()

        self.assertEqual(report["status"], "partial")
        self.assertTrue(report["checks"]["integrity_passed"])
        self.assertFalse(report["checks"]["promotion_ready"])
        self.assertEqual(report["totals"]["files"], 3)
        self.assertEqual(report["totals"]["verified_path_checksum"], 1)
        self.assertEqual(report["totals"]["verified_content_checksum"], 1)
        self.assertEqual(report["totals"]["unlinked"], 1)
        self.assertEqual(report["totals"]["files_with_public_url"], 2)
        self.assertEqual(report["text_artifacts"]["checksum_verified"], 1)
        file_rows = [
            json.loads(line)
            for line in self.file_manifest.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(
            [row["provenance_status"] for row in file_rows],
            [
                "verified_path_checksum",
                "verified_content_checksum",
                "unlinked",
            ],
        )

    def test_reads_exact_doc_url_from_document_fetches(self) -> None:
        payload = b"official-pdf"
        relative = "source/document.pdf"
        source_url = "https://www.congreso.es/public_oficiales/document.pdf"
        self.write_inventory({relative: payload})
        self.create_database([])
        connection = sqlite3.connect(self.database)
        connection.execute(
            """
            CREATE TABLE document_fetches (
              doc_url TEXT PRIMARY KEY,
              source_id TEXT,
              last_attempt_at TEXT,
              content_sha256 TEXT,
              bytes INTEGER,
              raw_path TEXT
            )
            """
        )
        connection.execute(
            "INSERT INTO document_fetches VALUES (?, ?, ?, ?, ?, ?)",
            (
                source_url,
                "parl_initiative_docs",
                "2026-08-12T00:00:00Z",
                digest(payload),
                len(payload),
                f"raw/{relative}",
            ),
        )
        connection.commit()
        connection.close()

        report = self.execute_audit()

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["totals"]["files_with_public_url"], 1)
        edge = json.loads(self.edge_manifest.read_text(encoding="utf-8"))
        self.assertEqual(edge["source_url"], source_url)

    def test_boe_manifest_requires_portable_document_and_summary_captures(
        self,
    ) -> None:
        document = b"<documento><metadatos><identificador>BOE-A-2026-1</identificador></metadatos></documento>"
        summary = b"<sumario><diario/></sumario>"
        document_path = "text_documents/boe_document_xml/document.xml"
        summary_path = "text_documents/boe_daily_summaries/summary.xml"
        self.write_inventory({document_path: document, summary_path: summary})
        self.create_database([])
        manifest = self.repo_root / "boe-lineage.jsonl"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": "boe_document_corpus_lineage_v2",
                    "capture_status": "checksum_capture_present",
                    "capture": {
                        "path": f"raw/{document_path}",
                        "bytes": len(document),
                        "sha256": digest(document),
                    },
                    "source_id": "boe_document_xml",
                    "source_url": "https://www.boe.es/diario_boe/xml.php?id=BOE-A-2026-1",
                    "fetched_at": "2026-08-13T00:00:00Z",
                    "content_type": "application/xml",
                    "boe_record": {"boe_ref": "BOE-A-2026-1"},
                    "source_summary": {
                        "source_url": "https://www.boe.es/datosabiertos/api/boe/sumario/20260101",
                        "fetched_at": "2026-08-13T00:00:00Z",
                        "content_type": "application/xml",
                        "path": f"raw/{summary_path}",
                        "bytes": len(summary),
                        "sha256": digest(summary),
                    },
                    "official_public_domain_personal_information_retained": True,
                    "synthetic_or_mock_records_counted": False,
                    "remote_mutation_performed": False,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        report = self.execute_audit(
            boe_document_corpus_lineage_manifests=[manifest]
        )

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["totals"]["verified_path_checksum"], 2)
        loaded = report["boe_document_corpus_lineage_manifests"][0]
        self.assertEqual(loaded["accepted_checksum_captures"], 1)

    def test_uses_exact_archived_document_lineage_manifest(self) -> None:
        payload = b"official municipal XML"
        relative = "municipal_concejales/2026/02/12/capture.xml"
        source_url = "https://concejales.redsara.es/consulta/getConcejalesLegislatura"
        self.write_inventory({relative: payload})
        self.create_database([])
        manifest = self.repo_root / "archived-lineage.jsonl"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": "archived_document_source_lineage_v1",
                    "capture_status": "checksum_capture_present",
                    "capture": {
                        "path": f"raw/{relative}",
                        "bytes": len(payload),
                        "sha256": digest(payload),
                    },
                    "metadata_sources": [
                        {
                            "database": "archive/politicos.db",
                            "database_sha256": "a" * 64,
                            "table": "raw_fetches",
                        }
                    ],
                    "source_id": "municipal_concejales",
                    "source_url": source_url,
                    "public_domain_personal_information_retained": True,
                    "synthetic_or_mock_records_counted": False,
                }
            )
            + "\n",
            encoding="utf-8",
        )

        report = self.execute_audit(archived_document_lineage_manifests=[manifest])

        self.assertEqual(report["status"], "ok")
        self.assertEqual(
            report["archived_document_lineage_manifests"][0][
                "accepted_checksum_captures"
            ],
            1,
        )
        edge = json.loads(self.edge_manifest.read_text(encoding="utf-8"))
        self.assertEqual(edge["source_url"], source_url)

    def test_checksum_conflict_fails_integrity_without_discarding_file(self) -> None:
        payload = b"official-document"
        self.write_inventory({"source/conflict.pdf": payload})
        self.create_database(
            [
                (
                    "raw/source/conflict.pdf",
                    "0" * 64,
                    "official_documents",
                    "https://public.example.es/conflict.pdf",
                    "2026-08-12T00:00:00Z",
                    len(payload),
                    None,
                    None,
                )
            ]
        )

        report = self.execute_audit()

        self.assertEqual(report["status"], "failed")
        self.assertFalse(report["checks"]["integrity_passed"])
        self.assertEqual(report["totals"]["checksum_conflict"], 1)
        self.assertEqual(report["totals"]["files_with_checksum_conflict"], 1)

    def test_recovers_exact_placsp_self_link_from_official_capture(self) -> None:
        source_url = (
            "https://contrataciondelestado.es/wps/poc?"
            "uri=deeplink:detalle_licitacion&idEvl=official%3D%3D"
        )
        payload = (
            '<html><span id="view:form:hiperenlaceId" style="display:none">'
            + source_url.replace("&", "&amp;")
            + "</span></html>"
        ).encode()
        self.write_inventory({"placsp_autonomico_detail/capture.html": payload})
        self.create_database([])

        report = self.execute_audit()

        self.assertEqual(report["status"], "ok")
        self.assertTrue(report["checks"]["promotion_ready"])
        self.assertEqual(report["totals"]["verified_embedded_url_checksum"], 1)
        self.assertEqual(report["totals"]["files_with_public_url"], 1)
        self.assertEqual(report["embedded_official_urls"]["linked"], 1)
        edge = json.loads(self.edge_manifest.read_text(encoding="utf-8"))
        self.assertEqual(edge["source_url"], source_url)
        self.assertEqual(edge["match_basis"], "embedded_url_checksum")

    def test_ambiguous_placsp_self_links_remain_unlinked(self) -> None:
        marker = '<span id="hiperenlaceId">{}</span>'
        first = (
            "https://contrataciondelestado.es/wps/poc?"
            "uri=deeplink:detalle_licitacion&amp;idEvl=first"
        )
        second = (
            "https://contrataciondelestado.es/wps/poc?"
            "uri=deeplink:detalle_licitacion&amp;idEvl=second"
        )
        self.write_inventory(
            {
                "placsp_sindicacion_detail/capture.html": (
                    marker.format(first) + marker.format(second)
                ).encode()
            }
        )
        self.create_database([])

        report = self.execute_audit()

        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["totals"]["unlinked"], 1)
        self.assertEqual(report["embedded_official_urls"]["ambiguous_self_link"], 1)

    def test_recovers_exact_senate_dc_identifier(self) -> None:
        source_url = (
            "https://www.senado.es/web/actividadparlamentaria/iniciativas/"
            "detalleiniciativa/index.html?id1=610&id2=000230&legis=6"
        )
        payload = (
            '<html><head><meta name="DC.identifier" content="'
            + source_url.replace("&", "&amp;")
            + '"/></head></html>'
        ).encode()
        self.write_inventory(
            {"text_documents/parl_initiative_docs/capture.html": payload}
        )
        self.create_database([])

        report = self.execute_audit()

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["totals"]["verified_embedded_url_checksum"], 1)
        edge = json.loads(self.edge_manifest.read_text(encoding="utf-8"))
        self.assertEqual(edge["source_url"], source_url)

    def test_recovers_exact_senate_dc_identifier_from_gzip_named_html(self) -> None:
        source_url = (
            "https://www.senado.es/web/actividadparlamentaria/iniciativas/"
            "detalleiniciativa/index.html?id1=621&id2=000130&legis=10"
        )
        html_payload = (
            '<html><head><meta name="DC.identifier" content="'
            + source_url.replace("&", "&amp;")
            + '"/></head></html>'
        ).encode()
        payload = gzip.compress(html_payload)
        self.write_inventory(
            {"text_documents/parl_initiative_docs/capture.html": payload}
        )
        self.create_database([])

        report = self.execute_audit()

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["totals"]["verified_embedded_url_checksum"], 1)
        self.assertEqual(
            report["embedded_official_urls"]["capture_read_statuses"]["gzip"],
            1,
        )
        edge = json.loads(self.edge_manifest.read_text(encoding="utf-8"))
        self.assertEqual(edge["source_url"], source_url)

    def test_recovers_exact_senate_amendment_url_from_embedded_spanish_link(
        self,
    ) -> None:
        base_url = (
            "https://www.senado.es/web/actividadparlamentaria/iniciativas/"
            "enmiendas/index.html"
        )
        source_url = base_url + "?lang=es_ES&id1=610&id2=000099&legis=10"
        detail_url = (
            "https://www.senado.es/web/actividadparlamentaria/iniciativas/"
            "detalleiniciativa/index.html?lang=es_ES&id1=610&id2=000099&legis=10"
        )
        payload = (
            '<html><head><meta name="DC.identifier" content="'
            + base_url
            + '"/></head><body><a href="?lang=es_ES&amp;id1=610&amp;id2=000099&amp;legis=10">'
            'Español</a><a href="'
            + detail_url.replace("&", "&amp;")
            + '">Detalle</a></body></html>'
        ).encode()
        self.write_inventory(
            {"text_documents/parl_initiative_docs/amendment.html": payload}
        )
        self.create_database([])

        report = self.execute_audit()

        self.assertEqual(report["status"], "ok")
        edge = json.loads(self.edge_manifest.read_text(encoding="utf-8"))
        self.assertEqual(edge["source_url"], source_url)

    def test_senate_generic_identifier_without_exact_ids_remains_unlinked(
        self,
    ) -> None:
        payload = (
            b'<html><head><meta name="DC.identifier" '
            b'content="https://www.senado.es/web/actividadparlamentaria/'
            b'iniciativas/enmiendas/index.html"/></head></html>'
        )
        self.write_inventory(
            {"text_documents/parl_initiative_docs/amendment.html": payload}
        )
        self.create_database([])

        report = self.execute_audit()

        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["totals"]["unlinked"], 1)

    def test_recovers_exact_senate_initiative_form_action(self) -> None:
        source_path = (
            "/web/actividadparlamentaria/iniciativas/detalleiniciativa/"
            "index.html?legis=10&id1=621&id2=000078"
        )
        source_url = "https://www.senado.es" + source_path
        payload = (
            '<html class="senate-initiative-capture"><body>'
            '<form action="'
            + source_path
            + '" method="POST" class="senate-initiative-capture__language-form">'
            '<input type="hidden" name="language" value="es_ES" '
            'class="senate-initiative-capture__language-input"/>'
            "</form></body></html>"
        ).encode()
        self.write_inventory(
            {"text_documents/parl_initiative_docs/capture.html": payload}
        )
        self.create_database([])

        report = self.execute_audit()

        self.assertEqual(report["status"], "ok")
        edge = json.loads(self.edge_manifest.read_text(encoding="utf-8"))
        self.assertEqual(edge["source_url"], source_url)

    def test_recovers_exact_congress_intervention_current_url(self) -> None:
        source_path = (
            "/es/busqueda-de-intervenciones?p_p_id=intervenciones"
            "&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view"
            "&_intervenciones_mode=mostrarTextoIntegro"
            "&_intervenciones_legislatura=XV"
            "&_intervenciones_id_texto=(DSCD-15-PL-62.CODI.)"
        )
        escaped_path = "".join(f"\\x{ord(char):02x}" for char in source_path)
        payload = (
            '<html><head><link rel="canonical" '
            'href="https://www.congreso.es/busqueda-de-intervenciones"/>'
            f"</head><script>Liferay.currentURL = '{escaped_path}';</script></html>"
        ).encode()
        self.write_inventory(
            {"text_documents/congreso_intervenciones/transcript.html": payload}
        )
        self.create_database([])

        report = self.execute_audit()

        self.assertEqual(report["status"], "ok")
        edge = json.loads(self.edge_manifest.read_text(encoding="utf-8"))
        self.assertEqual(edge["source_url"], "https://www.congreso.es" + source_path)

    def test_congress_generic_canonical_without_transcript_state_is_unlinked(
        self,
    ) -> None:
        payload = (
            b'<html><head><link rel="canonical" '
            b'href="https://www.congreso.es/busqueda-de-intervenciones"/>'
            b"</head></html>"
        )
        self.write_inventory(
            {"text_documents/congreso_intervenciones/transcript.html": payload}
        )
        self.create_database([])

        report = self.execute_audit()

        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["totals"]["unlinked"], 1)

    def test_rejects_non_official_dc_identifier(self) -> None:
        payload = (
            b'<html><head><meta name="DC.identifier" '
            b'content="https://example.org/index.html?id1=1&amp;id2=2&amp;legis=3"/>'
            b"</head></html>"
        )
        self.write_inventory(
            {"text_documents/parl_initiative_docs/capture.html": payload}
        )
        self.create_database([])

        report = self.execute_audit()

        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["totals"]["unlinked"], 1)

    def test_recovers_official_public_profile_without_stripping_identity(
        self,
    ) -> None:
        source_url = (
            "http://www.parlamentodegalicia.gal/Composicion/Deputados/406/"
            "maria-encarnacion-amigo-diaz"
        )
        payload = (
            '<html><head><meta property="og:url" content="'
            + source_url
            + '"/></head></html>'
        ).encode()
        self.write_inventory({"manual/public-profile.html": payload})
        self.create_database([])

        report = self.execute_audit()

        self.assertEqual(report["status"], "ok")
        edge = json.loads(self.edge_manifest.read_text(encoding="utf-8"))
        self.assertEqual(edge["source_url"], source_url)
        self.assertEqual(edge["url_kind"], "public_http")

    def test_recovers_exact_manual_capture_identifiers(self) -> None:
        galicia_url = "http://www.parlamentodegalicia.es/Composicion/Deputados"
        senate_home_url = "https://www.senado.es/web/index.html"
        senate_detail_url = (
            "https://www.senado.es/web/actividadparlamentaria/iniciativas/"
            "detalleiniciativa/index.html?id1=610&id2=000002&legis=15"
        )
        senate_amendment_url = (
            "https://www.senado.es/web/actividadparlamentaria/iniciativas/"
            "enmiendas/index.html?lang=es_ES&id1=610&id2=000005&legis=10"
        )
        senate_amendment_base = senate_amendment_url.split("?", 1)[0]
        moncloa_index_url = "https://www.lamoncloa.gob.es/paginas/varios/rss.aspx"
        files = {
            "manual/galicia.html": (
                '<html class="official-capture official-capture--galicia"><head>'
                '<meta property="og:url" content="'
                + galicia_url
                + '" class="official-capture__source-identifier"/>'
                "</head></html>"
            ).encode(),
            "manual/senate-home.html": (
                '<html class="official-capture official-capture--senate"><head>'
                '<meta name="DC.identifier" content="'
                + senate_home_url
                + '" class="official-capture__source-identifier"/>'
                "</head></html>"
            ).encode(),
            "manual/senate-detail.html": (
                '<html class="official-capture official-capture--senate"><head>'
                '<meta name="DC.identifier" content="'
                + senate_detail_url.replace("&", "&amp;")
                + '" class="official-capture__source-identifier"/>'
                "</head></html>"
            ).encode(),
            "manual/senate-amendment.html": (
                '<html class="official-capture official-capture--senate"><head>'
                '<meta name="DC.identifier" content="'
                + senate_amendment_base
                + '" class="official-capture__source-identifier"/>'
                '</head><body><a href="?lang=es_ES&amp;id1=610&amp;id2=000005'
                '&amp;legis=10" class="official-capture__language-link">Español</a>'
                "</body></html>"
            ).encode(),
            "manual/moncloa_exec/run/moncloa-index.xml": (
                '<html class="official-capture official-capture--moncloa"><head>'
                '<link rel="canonical" href="'
                + moncloa_index_url
                + '" class="official-capture__canonical-link"/>'
                "</head></html>"
            ).encode(),
        }
        self.write_inventory(files)
        self.create_database([])

        report = self.execute_audit()

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["totals"]["verified_embedded_url_checksum"], 5)
        edges = [
            json.loads(line)
            for line in self.edge_manifest.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(
            {edge["source_url"] for edge in edges},
            {
                galicia_url,
                senate_home_url,
                senate_detail_url,
                senate_amendment_url,
                moncloa_index_url,
            },
        )

    def test_recovers_moncloa_feeds_from_exact_official_index_relations(
        self,
    ) -> None:
        index_url = "https://www.lamoncloa.gob.es/paginas/varios/rss.aspx"
        feed_url = "https://www.lamoncloa.gob.es/Paginas/rss.aspx?tipo=16"
        title = "Referencias del Consejo de Ministros | La Moncloa"
        index_payload = (
            '<html class="official-capture official-capture--moncloa"><head>'
            '<link rel="canonical" href="'
            + index_url
            + '" class="official-capture__canonical-link"/>'
            '<link rel="alternate" type="application/rss+xml" title="'
            + title
            + '" href="/Paginas/rss.aspx?tipo=16" '
            'class="official-capture__rss-feed-link"/>'
            "</head></html>"
        ).encode()
        feed_payload = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<rss class="official-capture official-capture--moncloa-rss" version="2.0">'
            "<channel><title><![CDATA["
            + title
            + "]]></title><description>Official feed</description></channel></rss>"
        ).encode()
        self.write_inventory(
            {
                "manual/moncloa_exec/run/rss-main.xml": index_payload,
                "manual/moncloa_exec/run/rss-referencias.xml": feed_payload,
                "moncloa_rss_referencias/2026/02/capture.xml": feed_payload,
            }
        )
        self.create_database([])

        report = self.execute_audit()

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["totals"]["verified_checksum_files"], 3)
        self.assertEqual(report["embedded_official_urls"]["linked"], 3)
        self.assertEqual(
            report["embedded_official_urls"]["moncloa_feed_index"][
                "official_index_captures"
            ],
            1,
        )
        edges = [
            json.loads(line)
            for line in self.edge_manifest.read_text(encoding="utf-8").splitlines()
        ]
        self.assertGreaterEqual(
            sum(edge["source_url"] == feed_url for edge in edges),
            2,
        )

    def test_moncloa_feed_title_without_captured_index_remains_unlinked(self) -> None:
        payload = (
            b'<?xml version="1.0"?><rss class="official-capture '
            b'official-capture--moncloa-rss"><channel><title>'
            b"Referencias del Consejo de Ministros | La Moncloa"
            b"</title></channel></rss>"
        )
        self.write_inventory({"moncloa_rss_referencias/2026/02/capture.xml": payload})
        self.create_database([])

        report = self.execute_audit()

        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["totals"]["unlinked"], 1)

    def test_recovers_primary_party_canonical_url(self) -> None:
        source_url = "https://cup.cat/programa-10-punts-feminisme-canviar/"
        payload = (
            '<html><head><link rel="canonical" href="'
            + source_url
            + '"/></head></html>'
        ).encode()
        self.write_inventory(
            {"text_documents/programas_partidos/program.html": payload}
        )
        self.create_database([])

        report = self.execute_audit()

        self.assertEqual(report["status"], "ok")
        edge = json.loads(self.edge_manifest.read_text(encoding="utf-8"))
        self.assertEqual(edge["source_url"], source_url)

    def test_uses_content_addressed_party_program_source_manifest(self) -> None:
        payload = b"official-party-program"
        sha256 = digest(payload)
        relative = f"text_documents/programas_partidos/{sha256}.pdf"
        source_url = "https://ehbildu.eus/dokumentuak/programa.pdf"
        self.write_inventory({relative: payload})
        self.create_database([])
        manifest = self.repo_root / "programas-partidos.csv"
        manifest.write_text(
            f"party_id,source_url,local_path\n22,{source_url},raw/{relative}\n",
            encoding="utf-8",
        )

        report = self.execute_audit(party_program_source_manifests=[manifest])

        self.assertEqual(report["status"], "ok")
        self.assertEqual(
            report["party_program_source_manifests"]["accepted_unique_relations"],
            1,
        )
        edge = json.loads(self.edge_manifest.read_text(encoding="utf-8"))
        self.assertEqual(edge["source_url"], source_url)
        self.assertEqual(edge["match_basis"], "path_checksum")

    def test_rejects_local_party_program_sample_manifest(self) -> None:
        payload = b"local-sample"
        sha256 = digest(payload)
        relative = f"text_documents/programas_partidos/{sha256}.html"
        self.write_inventory({relative: payload})
        self.create_database([])
        manifest = self.repo_root / "programas-partidos.csv"
        manifest.write_text(
            "party_id,source_url,local_path\n"
            f"6,http://127.0.0.1:8765/sample.html,raw/{relative}\n",
            encoding="utf-8",
        )

        report = self.execute_audit(party_program_source_manifests=[manifest])

        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["totals"]["unlinked"], 1)
        self.assertEqual(
            report["party_program_source_manifests"][
                "skipped_non_primary_or_non_public_url"
            ],
            1,
        )

    def test_uses_checksum_backed_vote_lineage_manifest(self) -> None:
        relative = "manual/senado_votaciones_ses/legis10/ses_14_784.xml"
        payload = b"<Votaciones><Votacion>official</Votacion></Votaciones>"
        self.write_inventory({relative: payload})
        self.create_database([])
        source_url = "http://www.senado.es/legis10/votaciones/ses_14_784.xml"
        lineage_manifest = self.repo_root / "member-vote-lineage.jsonl"
        lineage_manifest.write_text(
            json.dumps(
                {
                    "source_url": source_url,
                    "capture_status": "checksum_capture_present",
                    "capture": {
                        "path": f"raw/{relative}",
                        "bytes": len(payload),
                        "sha256": digest(payload),
                    },
                    "source_url_rewritten": False,
                }
            )
            + "\n",
            encoding="utf-8",
        )

        report = self.execute_audit([lineage_manifest])

        self.assertEqual(report["status"], "ok")
        auxiliary = report["auxiliary_provenance_manifests"][0]
        self.assertEqual(auxiliary["accepted_checksum_captures"], 1)
        edge = json.loads(self.edge_manifest.read_text(encoding="utf-8"))
        self.assertEqual(edge["source_url"], source_url)
        self.assertEqual(edge["match_basis"], "path_checksum")

    def test_recovers_exact_senate_vote_url_embedded_in_its_capture(self) -> None:
        relative = "manual/senado_votaciones_ses/legis14/ses_2_4.xml"
        source_url = "http://www.senado.es/legis14/votaciones/ses_2_4.xml"
        payload = (
            '<?xml version="1.0"?><main class="senate-vote-capture">'
            '<url_votacion_xml class="senate-vote-capture__source-url">'
            + source_url
            + "</url_votacion_xml></main>"
        ).encode()
        self.write_inventory({relative: payload})
        self.create_database([])

        report = self.execute_audit()

        self.assertEqual(report["status"], "ok")
        edge = json.loads(self.edge_manifest.read_text(encoding="utf-8"))
        self.assertEqual(edge["source_url"], source_url)
        self.assertEqual(edge["match_basis"], "embedded_url_checksum")

    def test_senate_session_aggregate_with_only_child_urls_remains_unlinked(
        self,
    ) -> None:
        relative = "manual/senado_votaciones_ses/legis14/ses_2.xml"
        child_url = "http://www.senado.es/legis14/votaciones/ses_2_4.xml"
        payload = (
            '<?xml version="1.0"?><main class="senate-session-capture">'
            '<url_votacion_xml class="senate-session-capture__vote-source-url">'
            + child_url
            + "</url_votacion_xml></main>"
        ).encode()
        self.write_inventory({relative: payload})
        self.create_database([])

        report = self.execute_audit()

        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["totals"]["unlinked"], 1)

    def test_auxiliary_declared_byte_conflict_fails_integrity(self) -> None:
        relative = "manual/senado_votaciones_ses/legis10/ses_14_784.xml"
        payload = b"<Votaciones/>"
        self.write_inventory({relative: payload})
        self.create_database([])
        lineage_manifest = self.repo_root / "member-vote-lineage.jsonl"
        lineage_manifest.write_text(
            json.dumps(
                {
                    "source_url": (
                        "http://www.senado.es/legis10/votaciones/ses_14_784.xml"
                    ),
                    "capture_status": "checksum_capture_present",
                    "capture": {
                        "path": f"raw/{relative}",
                        "bytes": len(payload) + 1,
                        "sha256": digest(payload),
                    },
                    "source_url_rewritten": False,
                }
            )
            + "\n",
            encoding="utf-8",
        )

        report = self.execute_audit([lineage_manifest])

        self.assertEqual(report["status"], "failed")
        self.assertFalse(report["checks"]["integrity_passed"])
        self.assertEqual(report["totals"]["files_with_declared_bytes_conflict"], 1)

    def test_uses_exact_published_election_capture_indexes(self) -> None:
        calendar = b"official-calendar"
        candidates = b"official-candidate-list"
        initiative_index = b"official-initiative-index"
        vote_index = b"official-vote-index"
        vote_pdf = b"official-vote-pdf"
        embedded_vote_pdf = b"official-embedded-vote-pdf"
        party_program = b"real-party-program"
        press_program_copy = b"real-press-hosted-program-copy"
        raw_dir = "elections/andalucia_2026/parlamento_andalucia"
        initiative_url = (
            "https://www.parlamentodeandalucia.es/webdinamica/portal-web-parlamento/"
            "actividadparlamentaria/todaslasiniciativas/portipo.do?"
            "numexp=12-26%2FDL-000008&legislatura=12"
        )
        vote_url = (
            "https://www.parlamentodeandalucia.es/webdinamica/portal-web-parlamento/"
            "pdf.do?tipodoc=diario&id=201495"
        )
        embedded_vote_url = (
            "https://www.parlamentodeandalucia.es/webdinamica/portal-web-parlamento/"
            "pdf.do?tipodoc=diario&id=201496"
        )
        vote_name = (
            "parlamento-andalucia-votacion-https-www-parlamentodeandalucia-es-"
            "webdinamica-portal-web-parlamento-pdf-do-tipodoc-diario-id-201495.pdf"
        )
        embedded_vote_name = (
            "parlamento-andalucia-votacion-https-www-parlamentodeandalucia-es-"
            "webdinamica-portal-web-parlamento-pdf-do-tipodoc-diario-id-201496.pdf"
        )
        initiative = (
            b'<a class="initiative-detail__vote-document-link" '
            b'href="/webdinamica/portal-web-parlamento/pdf.do?tipodoc=diario&id=201496">'
            b"Sentido del voto</a>"
        )
        files = {
            "election_calendar/jec_andalucia_2026_calendario.pdf": calendar,
            "elections/andalucia_2026/candidaturas_proclamadas.pdf": candidates,
            f"{raw_dir}/legislative_initiatives_leg12.html": initiative_index,
            f"{raw_dir}/voting_results.html": vote_index,
            f"{raw_dir}/initiative_details/12-26-dl-000008.html": initiative,
            f"{raw_dir}/vote_pdfs/{vote_name}": vote_pdf,
            f"{raw_dir}/vote_pdfs/{embedded_vote_name}": embedded_vote_pdf,
            "elections/andalucia_2026/programas/andalucia_2026_programa_pp.pdf": party_program,
            "elections/andalucia_2026/programas/andalucia_2026_programa_vox.pdf": press_program_copy,
        }
        self.write_inventory(files)
        self.create_database([])
        calendar_index = self.repo_root / "calendar.json"
        calendar_index.write_text(
            json.dumps(
                {
                    "schema_version": "election-calendar.v1",
                    "scraped_sources": [
                        {
                            "raw_path": (
                                "raw/election_calendar/"
                                "jec_andalucia_2026_calendario.pdf"
                            ),
                            "url": (
                                "https://www.juntaelectoralcentral.es/cs/jec/"
                                "documentos/Andalucia_2026_calendario.pdf"
                            ),
                            "source_id": "jec_calendar",
                            "content_sha256": digest(calendar),
                            "bytes": len(calendar),
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        accountability_index = self.repo_root / "accountability.json"
        accountability_index.write_text(
            json.dumps(
                {
                    "schema_version": "andalucia_2026_accountability_snapshot_v1",
                    "sources": [
                        {
                            "raw_path": (
                                "raw/elections/andalucia_2026/"
                                "candidaturas_proclamadas.pdf"
                            ),
                            "url": (
                                "https://www.juntaelectoralcentral.es/cs/jec/"
                                "documentos/andalucia_2026_candidaturas_proclamadas.pdf"
                            ),
                            "source_id": "jec_candidates",
                            "content_sha256": digest(candidates),
                            "bytes": len(candidates),
                        }
                    ],
                    "program_sources": {
                        "by_party": {
                            "pp": [
                                {
                                    "raw_path": (
                                        "raw/elections/andalucia_2026/programas/"
                                        "andalucia_2026_programa_pp.pdf"
                                    ),
                                    "url": (
                                        "https://juanmapresidente.es/wp-content/"
                                        "uploads/2026/04/programa.pdf"
                                    ),
                                    "source_id": "andalucia_2026_programa_pp",
                                    "officiality": "campaign_domain",
                                    "status": "cached",
                                    "verification_status": "verified_by_text",
                                    "format": "pdf",
                                    "content_sha256": digest(party_program),
                                    "bytes": len(party_program),
                                }
                            ],
                            "vox": [
                                {
                                    "raw_path": (
                                        "raw/elections/andalucia_2026/programas/"
                                        "andalucia_2026_programa_vox.pdf"
                                    ),
                                    "url": (
                                        "https://www.eldebate.com/uploads/files/"
                                        "2026/05/05/programa.pdf"
                                    ),
                                    "source_id": "andalucia_2026_programa_vox",
                                    "officiality": "press_hosted_copy",
                                    "status": "cached",
                                    "verification_status": "verified_by_text",
                                    "format": "pdf",
                                    "content_sha256": digest(press_program_copy),
                                    "bytes": len(press_program_copy),
                                }
                            ],
                        }
                    },
                    "parliament_activity": {
                        "raw_dir": f"raw/{raw_dir}",
                        "initiatives_status": "cached",
                        "initiatives_url": (
                            "https://www.parlamentodeandalucia.es/webdinamica/"
                            "portal-web-parlamento/actividadparlamentaria/"
                            "todaslasiniciativas/portipo.do?legislatura=12"
                        ),
                        "voting_results_status": "cached",
                        "voting_results_url": (
                            "https://www.parlamentodeandalucia.es/webdinamica/"
                            "portal-web-parlamento/composicionyfuncionamiento/"
                            "resultadosvotaciones.do"
                        ),
                        "legislative_initiatives": [
                            {
                                "source_id": "parliament_initiatives",
                                "source_url": initiative_url,
                            }
                        ],
                        "vote_events": [{"source_url": vote_url}],
                    },
                }
            ),
            encoding="utf-8",
        )

        report = self.execute_audit(
            published_capture_indexes=[calendar_index, accountability_index]
        )

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["totals"]["verified_path_checksum"], 9)
        self.assertEqual(report["totals"]["files_with_public_url"], 9)
        self.assertEqual(report["published_capture_indexes"][0]["accepted"], 1)
        self.assertEqual(report["published_capture_indexes"][1]["accepted"], 8)
        methods = report["published_capture_indexes"][1]["accepted_by_method"]
        self.assertEqual(
            methods["published_andalucia_program_campaign_domain_capture"], 1
        )
        self.assertEqual(
            methods["published_andalucia_program_press_hosted_copy_capture"], 1
        )
        self.assertEqual(
            methods["published_andalucia_initiative_embedded_vote_document_capture"],
            1,
        )
        edges = [
            json.loads(line)
            for line in self.edge_manifest.read_text(encoding="utf-8").splitlines()
        ]
        self.assertTrue(all(edge["match_basis"] == "path_checksum" for edge in edges))
        self.assertTrue(any(edge["source_url"] == embedded_vote_url for edge in edges))

    def test_non_official_published_capture_url_remains_unlinked(self) -> None:
        payload = b"official-calendar"
        self.write_inventory(
            {"election_calendar/jec_andalucia_2026_calendario.pdf": payload}
        )
        self.create_database([])
        capture_index = self.repo_root / "calendar.json"
        capture_index.write_text(
            json.dumps(
                {
                    "schema_version": "election-calendar.v1",
                    "scraped_sources": [
                        {
                            "raw_path": (
                                "raw/election_calendar/"
                                "jec_andalucia_2026_calendario.pdf"
                            ),
                            "url": "https://example.org/fake.pdf",
                            "content_sha256": digest(payload),
                            "bytes": len(payload),
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        report = self.execute_audit(published_capture_indexes=[capture_index])

        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["totals"]["unlinked"], 1)
        self.assertEqual(
            report["published_capture_indexes"][0]["candidate_relations"], 0
        )

    def test_missing_declared_database_fails_integrity(self) -> None:
        self.write_inventory({"source/document.pdf": b"official-document"})

        report = self.execute_audit()

        self.assertEqual(report["status"], "failed")
        self.assertFalse(report["checks"]["database_inputs_readable"])
        self.assertFalse(report["checks"]["integrity_passed"])


if __name__ == "__main__":
    unittest.main()
