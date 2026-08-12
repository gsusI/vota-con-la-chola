from __future__ import annotations

import io
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from etl.politicos_es.db import apply_schema
from publicdata_connectors_es.money.placsp_bulk import (
    inspect_placsp_archive,
    iter_placsp_atom_records,
)

ATOM_FIXTURE = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
 xmlns:cbc="urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2"
 xmlns:cac="urn:dgpe:names:draft:codice:schema:xsd:CommonAggregateComponents-2"
 xmlns:ext="urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonAggregateComponents-2"
 xmlns:extb="urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonBasicComponents-2"
 xmlns:at="http://purl.org/atompub/tombstones/1.0">
  <at:deleted-entry when="2025-01-02T00:00:00+01:00" ref="urn:contract:deleted">
    <at:comment>ANULADA</at:comment>
  </at:deleted-entry>
  <entry>
    <id>urn:contract:one</id>
    <link href="https://example.test/contract/one" />
    <title>Road works</title>
    <updated>2025-01-03T10:00:00+01:00</updated>
    <ext:ContractFolderStatus>
      <cbc:ContractFolderID>EXP-1</cbc:ContractFolderID>
      <extb:ContractFolderStatusCode>ADJ</extb:ContractFolderStatusCode>
      <ext:LocatedContractingParty>
        <cac:Party>
          <cac:PartyIdentification><cbc:ID schemeName="NIF">Q0000001A</cbc:ID></cac:PartyIdentification>
          <cac:PartyName><cbc:Name>Test authority</cbc:Name></cac:PartyName>
        </cac:Party>
      </ext:LocatedContractingParty>
      <cac:ProcurementProject>
        <cbc:Name>Road works</cbc:Name>
        <cac:BudgetAmount>
          <cbc:EstimatedOverallContractAmount currencyID="EUR">1000000.50</cbc:EstimatedOverallContractAmount>
        </cac:BudgetAmount>
        <cac:RequiredCommodityClassification><cbc:ItemClassificationCode>45233120</cbc:ItemClassificationCode></cac:RequiredCommodityClassification>
        <cac:RealizedLocation><cbc:CountrySubentityCode>ES300</cbc:CountrySubentityCode></cac:RealizedLocation>
      </cac:ProcurementProject>
      <cac:TenderResult>
        <cbc:ResultCode>8</cbc:ResultCode>
        <cbc:AwardDate>2025-01-03</cbc:AwardDate>
        <cbc:ReceivedTenderQuantity>2</cbc:ReceivedTenderQuantity>
        <cac:WinningParty>
          <cac:PartyIdentification><cbc:ID schemeName="NIF">A00000001</cbc:ID></cac:PartyIdentification>
          <cac:PartyName><cbc:Name>Supplier SA</cbc:Name></cac:PartyName>
        </cac:WinningParty>
        <cac:AwardedTenderedProject>
          <cbc:ProcurementProjectLotID>1</cbc:ProcurementProjectLotID>
          <cac:LegalMonetaryTotal>
            <cbc:TaxExclusiveAmount currencyID="EUR">900000.25</cbc:TaxExclusiveAmount>
            <cbc:PayableAmount currencyID="EUR">1089000.3025</cbc:PayableAmount>
          </cac:LegalMonetaryTotal>
        </cac:AwardedTenderedProject>
      </cac:TenderResult>
      <cac:TenderingProcess><cbc:ProcedureCode>1</cbc:ProcedureCode></cac:TenderingProcess>
      <cac:LegalDocumentReference>
        <cbc:ID>terms.pdf</cbc:ID>
        <cac:Attachment><cac:ExternalReference>
          <cbc:URI>https://example.test/terms.pdf</cbc:URI>
          <cbc:DocumentHash>official-hash</cbc:DocumentHash>
        </cac:ExternalReference></cac:Attachment>
      </cac:LegalDocumentReference>
      <ext:ValidNoticeInfo>
        <extb:NoticeTypeCode>DOC_CAN_ADJ</extb:NoticeTypeCode>
        <ext:AdditionalPublicationStatus>
          <ext:AdditionalPublicationDocumentReference><cbc:IssueDate>2025-01-03</cbc:IssueDate></ext:AdditionalPublicationDocumentReference>
        </ext:AdditionalPublicationStatus>
      </ext:ValidNoticeInfo>
    </ext:ContractFolderStatus>
  </entry>
</feed>
"""


class PlacspBulkParserTests(unittest.TestCase):
    def test_stream_parser_retains_tombstones_awards_documents_and_decimals(self) -> None:
        progress = 0

        def on_progress() -> None:
            nonlocal progress
            progress += 1

        records = list(
            iter_placsp_atom_records(
                io.BytesIO(ATOM_FIXTURE),
                progress_callback=on_progress,
            )
        )
        self.assertEqual(len(records), 2)
        self.assertEqual(progress, 2)
        self.assertTrue(records[0].tombstone)
        self.assertEqual(records[0].record["contract_status_code"], "ANULADA")
        contract = records[1]
        self.assertFalse(contract.tombstone)
        self.assertEqual(contract.record["contract_id"], "EXP-1")
        self.assertEqual(contract.record["amount_eur_decimal"], "1000000.5")
        self.assertEqual(
            contract.record["amount_semantics"],
            "estimated_overall_contract_amount",
        )
        self.assertEqual(contract.record["authority_identifier"], "Q0000001A")
        self.assertEqual(contract.awards[0]["supplier_identifier"], "A00000001")
        self.assertEqual(contract.awards[0]["amount_eur_decimal"], "900000.25")
        self.assertEqual(contract.documents[0]["document_kind"], "LegalDocumentReference")
        self.assertEqual(contract.documents[0]["official_document_hash"], "official-hash")
        self.assertEqual(len(contract.source_record_id), 64)
        self.assertEqual(len(contract.entry_content_sha256), 64)

    def test_record_and_document_caps_fail_closed(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "records exceed cap"):
            list(iter_placsp_atom_records(io.BytesIO(ATOM_FIXTURE), max_records=1))
        with self.assertRaisesRegex(RuntimeError, "documents exceed cap"):
            list(
                iter_placsp_atom_records(
                    io.BytesIO(ATOM_FIXTURE),
                    max_documents_per_record=0,
                )
            )

    def test_archive_inspection_is_bounded_and_rejects_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_path = Path(tmp) / "valid.zip"
            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("feed.atom", ATOM_FIXTURE)
            inspection = inspect_placsp_archive(
                archive_path,
                max_archive_bytes=archive_path.stat().st_size,
                max_total_uncompressed_bytes=len(ATOM_FIXTURE),
                max_member_bytes=len(ATOM_FIXTURE),
                max_compression_ratio=100,
            )
            self.assertEqual(len(inspection.members), 1)
            self.assertEqual(inspection.uncompressed_bytes, len(ATOM_FIXTURE))

            unsafe_path = Path(tmp) / "unsafe.zip"
            with zipfile.ZipFile(unsafe_path, "w") as archive:
                archive.writestr("../feed.atom", ATOM_FIXTURE)
            with self.assertRaisesRegex(RuntimeError, "unsafe"):
                inspect_placsp_archive(unsafe_path)

    def test_schema_and_existing_database_compatibility(self) -> None:
        schema_path = Path("etl/load/sqlite_schema.sql")
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            apply_schema(conn, schema_path)
            columns = {
                str(row[1])
                for row in conn.execute("PRAGMA table_info(money_contract_records)")
            }
            self.assertIn("amount_eur_decimal", columns)
            self.assertIn("stable_contract_id", columns)
            run_columns = {
                str(row[1])
                for row in conn.execute("PRAGMA table_info(placsp_bulk_runs)")
            }
            self.assertIn("archive_contract_sha256", run_columns)
            self.assertIsNotNone(
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE name='placsp_bulk_members'"
                ).fetchone()
            )
        finally:
            conn.close()

if __name__ == "__main__":
    unittest.main()
