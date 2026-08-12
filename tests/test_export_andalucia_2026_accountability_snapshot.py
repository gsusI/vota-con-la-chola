from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts import export_andalucia_2026_accountability_snapshot as snapshot_module
from scripts.export_andalucia_2026_accountability_snapshot import (
    apply_boja_impact_reviews,
    apply_parliament_vote_reviews,
    build_issue_execution_evidence_queue,
    build_issue_readiness_report,
    build_post_change_outcome_monitor,
    build_snapshot,
    collect_boja_normative_sources,
    collect_execution_evidence_candidates,
    collect_parlamento_andalucia_activity,
    collect_program_sources,
    compact_execution_candidate_row,
    execution_candidate_match_score,
    execution_evidence_queue_csv_text,
    extract_program_measures,
    impact_review_queue_csv_text,
    issue_packet_gaps,
    load_ieca_ods_outcome_series_rows,
    load_pipe_csv_dict_rows_from_text,
    parliament_vote_review_queue_csv_text,
    parse_candidature_text,
    parse_parliament_initiatives_html,
    parse_parliament_vote_events_text,
    parse_parliament_voting_documents_html,
    public_grant_beneficiary,
    reviewed_vote_expects_boja_legal_change,
)

FIXTURE_TEXT = """
Boletín Oficial de la Junta de Andalucía
Candidaturas proclamadas a las elecciones al Parlamento de Andalucía del día
17 de mayo de 2026.

Circunscripción electoral: Almería

Candidatura núm.: 1. PARTIDO POPULAR (PP)

1. DON JUAN MANUEL MORENO BONILLA
2. DOÑA ANA TEST CANDIDATA

Suplentes

1. DON SUPLENTE UNO

Candidatura núm.: 2. POR ANDALUCÍA: IZQUIERDA UNIDA ANDALUCÍA-PODEMOS -
MOVIMIENTO SUMAR (PorA)

1. DON ANTONIO MAÍLLO CAÑADAS

Suplentes

1. DOÑA SUPLENTE DOS

Circunscripción electoral: Sevilla

Candidatura núm.: 1. PARTIDO SOCIALISTA OBRERO ESPAÑOL DE ANDALUCÍA (PSOE-A)

1. DOÑA MARÍA JESÚS MONTERO CUADRADO

Suplentes

1. DON SUPLENTE TRES
"""

VOTING_FIXTURE_TEXT = """
PARLAMENTO DE ANDALUCÍA - XII LEGISLATURA

 TÍTULO GENERAL DEL DEBATE

            12-25/PL-000011, DEBATE FINAL DEL PROYECTO DE LEY DE PATRIMONIO CULTURAL DE ANDALUCÍA



                                 11/03/2026 20:23:33

                                              VOTACIÓN Nº          2
                                              PROTOCOLO           20
                                              SESIÓN              79


                          TÍTULO PARTICULAR DEL DEBATE:


                           PRESIDE LA VOTACIÓN:    AGUIRRE MUÑOZ, JESÚS



                         TOTAL         PP         PS         VO         PA    AA _

PRESENTES                 107         058        028        014        005   002

TOTAL SI                  036         000        029        000        005   002

TOTAL NO                  072         058        000        014        000   000

TOTAL ABSTENCIONES        000         000        000        000        000   000

TOTAL BLANCOS             000         000        000        000        000   000

DIPUTADOS AUSENTES        001         000        001        000        000   000
TOTAL DIPUTADOS           109         058        030        014        005   002

                             G.P. POPULAR ANDALUZ

                                  *** NO ***

001 Aguirre Muñoz, Jesús                       015 Moreno Bonilla, Juan Manuel

                               G.P. PSOE DE ANDALUCÍA

                                     *** SÍ ***

(*)055 Castaño Diéguez, Adela

                                  *** AUSENTES ***

003 García Macías, Irene

                             G.P. VOX EN ANDALUCÍA

                                  *** NO ***

052 Gavira Florentino, Manuel

                        G.P. MIXTO-ADELANTE ANDALUCÍA

                                    *** SÍ ***

075 García Sánchez, José Ignacio
"""


class TestExportAndalucia2026AccountabilitySnapshot(unittest.TestCase):
    def test_boja_gap_only_expected_for_reviewed_votes_with_approved_legal_effects(self) -> None:
        rejected_nonbinding_vote = {
            "legal_effect_kind": "nonbinding_resolution_vote_rejected",
            "effect_outcome": "rejected_by_majority_no",
        }
        approved_law_vote = {
            "legal_effect_kind": "law_final_approval_vote_passed",
            "effect_outcome": "approved_by_majority_yes",
        }

        self.assertFalse(reviewed_vote_expects_boja_legal_change(rejected_nonbinding_vote))
        self.assertTrue(reviewed_vote_expects_boja_legal_change(approved_law_vote))
        self.assertNotIn(
            "missing_reviewed_boja_legal_change",
            issue_packet_gaps(
                program_measures_total=1,
                reviewed_vote_items_total=1,
                reviewed_vote_boja_expected_total=0,
                reviewed_boja_legal_changes_total=0,
                observed_responsibility_claims_total=1,
                issue_review={},
            ),
        )
        self.assertIn(
            "missing_reviewed_boja_legal_change",
            issue_packet_gaps(
                program_measures_total=1,
                reviewed_vote_items_total=1,
                reviewed_vote_boja_expected_total=1,
                reviewed_boja_legal_changes_total=0,
                observed_responsibility_claims_total=1,
                issue_review={},
            ),
        )

    def test_parliament_initiatives_classify_fiscal_support_decree(self) -> None:
        html = """
        <dl class="row">
          <dt>Número Expediente:</dt>
          <dd>12-26/DL-000001</dd>
          <dt>Extracto:</dt>
          <dd>Decreto-ley 1/2026, de 25 de febrero, por el que se adoptan con carácter urgente medidas de apoyo fiscal por los daños producidos por el impacto de borrascas en la Comunidad Autónoma de Andalucía.</dd>
          <dt>Proponente:</dt>
          <dd>Consejo de Gobierno de la Junta de Andalucía</dd>
          <dt>Fecha creación:</dt>
          <dd>25/02/2026</dd>
        </dl>
        """

        records = parse_parliament_initiatives_html(html)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["numexp"], "12-26/DL-000001")
        self.assertEqual(records[0]["topic_id"], "fiscalidad")
        self.assertEqual(records[0]["type_code"], "DL")

    def test_parse_candidature_text_groups_lists_and_candidates(self) -> None:
        parsed = parse_candidature_text(FIXTURE_TEXT)

        self.assertEqual(parsed["coverage"]["provinces_total"], 2)
        self.assertEqual(parsed["coverage"]["candidate_lists_total"], 3)
        self.assertEqual(parsed["coverage"]["titular_candidates_total"], 4)
        self.assertEqual(parsed["coverage"]["suplente_candidates_total"], 3)
        self.assertEqual(parsed["lists"][1]["party_acronym"], "PorA")
        self.assertIn("MOVIMIENTO SUMAR", parsed["lists"][1]["candidature_name"])
        self.assertEqual(parsed["candidates"][0]["person_name"], "JUAN MANUEL MORENO BONILLA")

    def test_build_snapshot_keeps_claims_closed_until_evidence_exists(self) -> None:
        snapshot = build_snapshot(
            candidature_text=FIXTURE_TEXT,
            candidature_source={
                "source_id": "test",
                "url": "https://example.test/candidaturas.pdf",
                "status": "from_text",
                "source_verified": True,
            },
            db_path=Path("/missing.db"),
            source_catalog_path=Path("/missing-catalog.json"),
        )

        self.assertEqual(snapshot["coverage"]["published_merit_blame_claims_total"], 0)
        self.assertEqual(snapshot["method"]["current_public_claim_status"], "candidate_identity_only")
        self.assertEqual(snapshot["db_report"]["status"], "missing_db")
        self.assertEqual(snapshot["coverage"]["distinct_party_keys_total"], 3)
        self.assertTrue(snapshot["evidence_lanes"])
        self.assertEqual(snapshot["coverage"]["candidates_with_accountability_evidence_total"], 0)
        self.assertEqual(snapshot["coverage"]["published_accountability_claims_total"], 0)
        self.assertEqual(snapshot["published_accountability_claims"]["claims_total"], 0)
        self.assertEqual(snapshot["coverage"]["issue_accountability_reviewed_issues_total"], 0)
        self.assertEqual(snapshot["coverage"]["issue_accountability_execution_owner_reviewed_total"], 0)
        self.assertEqual(snapshot["issue_accountability_reviews"]["reviews_total"], 0)
        self.assertEqual(snapshot["responsibility_comparison"]["claim_status"], "responsibility_evidence_comparison_only_no_merit_or_blame_claim")
        self.assertEqual(snapshot["coverage"]["responsibility_party_profiles_total"], 3)
        self.assertEqual(snapshot["coverage"]["responsibility_focus_candidate_profiles_total"], 5)
        self.assertEqual(snapshot["issue_accountability_packets"]["packets_total"], 0)
        self.assertEqual(snapshot["coverage"]["issue_accountability_packets_total"], 0)
        self.assertEqual(snapshot["coverage"]["issue_accountability_packets_with_observed_responsibility_total"], 0)
        self.assertEqual(snapshot["coverage"]["issue_accountability_observed_responsibility_claims_total"], 0)
        self.assertEqual(snapshot["coverage"]["issue_accountability_issue_reviews_total"], 0)

    def test_treasury_payment_aggregate_pipe_csv_rows_are_loaded(self) -> None:
        text = (
            "Año|Mes|Id_Jerarquía_1|Den_Jerarquía_1|Id_Jerarquía_2|Den_Jerarquía_2|"
            "Id_Jerarquía_3|Den_Jerarquía_3|Importe_Pago\n"
            "2025|01|NOM10|1. Nomina|NOM11|1.1. Consejerías|NOAG26|"
            "Consejería de Agricultura, Pesca, Agua y Desarrollo Rural|5022333.47 \n"
        )

        header, rows = load_pipe_csv_dict_rows_from_text(text)

        self.assertIn("Importe_Pago", header)
        self.assertEqual(rows[0]["_row_number"], 2)
        self.assertEqual(rows[0]["Mes"], "01")
        self.assertIn("Agua", rows[0]["Den_Jerarquía_3"])

    def test_treasury_payment_aggregate_candidate_has_member_locator(self) -> None:
        row = {
            "_row_number": 2,
            "Año": "2025",
            "Mes": "01",
            "Id_Jerarquía_1": "NOM10",
            "Den_Jerarquía_1": "1. Nomina",
            "Id_Jerarquía_2": "NOM11",
            "Den_Jerarquía_2": "1.1. Consejerías",
            "Id_Jerarquía_3": "NOAG26",
            "Den_Jerarquía_3": "Consejería de Agricultura, Pesca, Agua y Desarrollo Rural",
            "Importe_Pago": "5022333.47",
        }

        score, matched_terms = execution_candidate_match_score(
            source_id="junta_tesoreria_2025_pagos_agregados",
            row=row,
            search_terms=["agua"],
        )
        false_score, false_matched_terms = execution_candidate_match_score(
            source_id="junta_tesoreria_2025_pagos_agregados",
            row=row,
            search_terms=["cultura"],
        )
        candidate = compact_execution_candidate_row(
            source_id="junta_tesoreria_2025_pagos_agregados",
            topic_id="campo_agua",
            gap_id="missing_budget_execution",
            row=row,
            source_file=Path("tesoreria_2025_movimientos.7z"),
            match_score=score,
            matched_terms=matched_terms,
        )

        self.assertGreater(score, 0)
        self.assertEqual(false_score, 0)
        self.assertEqual(false_matched_terms, [])
        self.assertEqual(candidate["amount_eur"], 5022333)
        self.assertEqual(candidate["treasury_month"], "01")
        self.assertEqual(
            candidate["source_locator"],
            "tesoreria_2025_movimientos.7z:2025T4_PAGOS_4.CSV:fila 2",
        )

    def test_program_sources_are_collected_without_publishing_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed_path = root / "program_sources.json"
            raw_dir = root / "raw"
            source_id = "test_programa_pp"
            program_dir = raw_dir / "programas"
            text_dir = program_dir / "text"
            program_dir.mkdir(parents=True)
            text_dir.mkdir(parents=True)
            (program_dir / f"{source_id}.pdf").write_bytes(b"%PDF-1.4 test")
            (text_dir / f"{source_id}.txt").write_text(
                """
PROGRAMA ELECTORAL 2026 Juanma Moreno Andalucia
1. Reforzaremos la sanidad pública y reduciremos listas de espera en Atención Primaria.
2. Impulsaremos vivienda asequible para jóvenes y familias trabajadoras.
3. Mejoraremos el empleo autónomo con menos trámites.
""".strip(),
                encoding="utf-8",
            )
            seed_path.write_text(
                """
{
  "schema_version": "test",
  "sources": [
    {
      "source_id": "test_programa_pp",
      "party_key": "pp",
      "party_acronym": "PP",
      "party_name": "Partido Popular",
      "title": "Programa PP test",
      "url": "https://example.test/pp.pdf",
      "page_url": "https://example.test/",
      "source_kind": "test_pdf",
      "officiality": "party_domain",
      "format": "pdf",
      "verify_terms": ["programa electoral 2026", "juanma moreno", "andalucia"]
    }
  ]
}
""".strip(),
                encoding="utf-8",
            )

            report = collect_program_sources(
                seed_path=seed_path,
                raw_dir=raw_dir,
                timeout=1,
                no_network=True,
                strict_network=True,
            )
            snapshot = build_snapshot(
                candidature_text=FIXTURE_TEXT,
                candidature_source={"source_id": "test", "status": "from_text", "source_verified": True},
                db_path=Path("/missing.db"),
                source_catalog_path=Path("/missing-catalog.json"),
                program_report=report,
            )

        self.assertEqual(report["verified_sources_total"], 1)
        self.assertEqual(report["measures_total"], 3)
        self.assertEqual(snapshot["coverage"]["program_sources_verified_total"], 1)
        self.assertEqual(snapshot["coverage"]["program_measures_total"], 3)
        self.assertEqual(snapshot["coverage"]["published_merit_blame_claims_total"], 0)
        self.assertEqual(snapshot["coverage"]["published_accountability_claims_total"], 0)
        self.assertEqual(snapshot["coverage"]["issue_accountability_reviewed_issues_total"], 0)
        self.assertEqual(
            snapshot["method"]["current_public_claim_status"],
            "candidate_identity_and_declared_program_measures",
        )
        pp = next(party for party in snapshot["parties"] if party["party_key"] == "pp")
        self.assertEqual(pp["program_source_status"], "program_text_ready")
        self.assertEqual(pp["program_verified_sources_total"], 1)
        self.assertEqual(pp["program_measures_total"], 3)
        pp_profile = next(
            row for row in snapshot["responsibility_comparison"]["party_profiles"] if row["party_key"] == "pp"
        )
        self.assertEqual(pp_profile["declared_program_measures_total"], 3)
        self.assertEqual(pp_profile["claim_status"], "responsibility_evidence_comparison_only_no_merit_or_blame_claim")
        self.assertEqual(snapshot["coverage"]["issue_accountability_packets_total"], 3)
        self.assertEqual(snapshot["issue_accountability_packets"]["claim_status"], "issue_evidence_packet_only_no_merit_or_blame_claim")
        sanidad_packet = next(
            row for row in snapshot["issue_accountability_packets"]["packets"] if row["topic_id"] == "sanidad"
        )
        self.assertEqual(sanidad_packet["status"], "program_only")
        self.assertEqual(sanidad_packet["program_measures_total"], 1)
        self.assertEqual(sanidad_packet["observed_responsibility_claims_total"], 0)
        self.assertEqual(sanidad_packet["program_party_counts"][0]["party_key"], "pp")
        self.assertIn("missing_reviewed_vote_signal", sanidad_packet["open_gaps"])
        self.assertIn("missing_responsible_actor", sanidad_packet["open_gaps"])

    def test_extract_program_measures_keeps_declarations_as_unassessed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            text_path = Path(tmp) / "programa.txt"
            text_path.write_text(
                """
1. Blindaremos por Ley la Atención Primaria como eje de la sanidad pública.
2. Crearemos un parque público de vivienda en alquiler asequible.
3. Impulsaremos planes de agua y regadío para el campo andaluz.
""".strip(),
                encoding="utf-8",
            )
            measures = extract_program_measures(
                [
                    {
                        "source_id": "programa_test",
                        "party_key": "test",
                        "party_acronym": "TEST",
                        "party_name": "Partido Test",
                        "title": "Programa test",
                        "url": "https://example.test/programa.pdf",
                        "page_url": "https://example.test/",
                        "officiality": "party_domain",
                        "verification_status": "verified_by_text",
                        "text_path": str(text_path),
                    }
                ]
            )

        self.assertEqual(len(measures), 3)
        self.assertEqual({row["topic_id"] for row in measures}, {"sanidad", "vivienda", "campo_agua"})
        self.assertTrue(all(row["claim_status"] == "declared_program_measure_not_assessed" for row in measures))
        self.assertTrue(all(row["interpretation_status"] == "needs_review_before_impact_claim" for row in measures))

    def test_build_snapshot_links_conservative_accountability_evidence(self) -> None:
        evidence_report = {
            "status": "ok",
            "source_entries_total": 10,
            "source_actor_answers_total": 2,
            "source_issue_answers_total": 1,
            "actors_by_key": {
                "person_id:101": {
                    "actor_key": "person_id:101",
                    "actor_label": "JUAN MANUEL MORENO BONILLA",
                    "actor_kind": "person",
                    "answer_status": "partial",
                    "entries_total": 2,
                    "issues_total": 2,
                    "role_counts": [{"key": "voted_for", "count": 2}],
                    "entry_kind_counts": [{"key": "parliamentary_action", "count": 2}],
                    "present_dimensions": ["parliamentary_actions"],
                    "missing_dimensions": ["money"],
                    "dossier_route": "/accountability-dossiers/actors/person-id-101/",
                    "evidence_samples": [],
                },
                "party_id:1": {
                    "actor_key": "party_id:1",
                    "actor_label": "PP",
                    "actor_kind": "party",
                    "answer_status": "partial",
                    "entries_total": 8,
                    "issues_total": 3,
                    "role_counts": [{"key": "voted_for", "count": 6}],
                    "entry_kind_counts": [{"key": "parliamentary_action", "count": 8}],
                    "present_dimensions": ["parliamentary_actions"],
                    "missing_dimensions": ["outcomes"],
                    "dossier_route": "/accountability-dossiers/actors/party-id-1/",
                    "evidence_samples": [],
                },
            },
        }
        snapshot = build_snapshot(
            candidature_text=FIXTURE_TEXT,
            candidature_source={"source_id": "test", "status": "from_text", "source_verified": True},
            db_path=Path("/missing.db"),
            source_catalog_path=Path("/missing-catalog.json"),
            accountability_evidence_report=evidence_report,
        )
        pp = next(party for party in snapshot["parties"] if party["party_key"] == "pp")
        self.assertEqual(pp["accountability_evidence"]["status"], "linked_accountability_evidence")
        self.assertEqual(pp["accountability_evidence"]["match_scope"], "national_party_rollup")
        self.assertEqual(snapshot["coverage"]["parties_with_accountability_evidence_total"], 1)

    def test_boja_normative_sources_are_collected_as_uninterpreted_primary_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw_dir = Path(tmp) / "raw"
            boja_dir = raw_dir / "boja_normas"
            detail_dir = boja_dir / "details"
            boja_dir.mkdir(parents=True)
            detail_dir.mkdir(parents=True)
            (boja_dir / "sanidad.json").write_text(
                """
{
  "hits": 1,
  "total_hits": 12,
  "results": [
    {
      "id": "disposition.2026.62.2",
      "number": 62,
      "date": "31/03/2026",
      "titleSec": "1. Disposiciones generales",
      "organisation": "Consejería de Sanidad, Presidencia y Emergencias",
      "type": "Acuerdos",
      "summaryNoHtml": "Acuerdo de 25 de marzo de 2026, del Consejo de Gobierno, por el que se aprueba la Estrategia de Investigación e Innovación en Salud de Andalucía 2026-2027.",
      "pdf": [
        {
          "pathPdf": "BOJA26-062-00004-50001-01_00335459",
          "publicUrl": "https://juntadeandalucia.es/eboja/2026/62/BOJA26-062-00004-50001-01_00335459.pdf"
        }
      ]
    },
    {
      "id": "disposition.2026.62.3",
      "number": 62,
      "date": "31/03/2026",
      "titleSec": "1. Disposiciones generales",
      "organisation": "Consejería de Agricultura, Pesca, Agua y Desarrollo Rural",
      "type": "Resoluciones",
      "summaryNoHtml": "Resolución sobre producción integrada inscrita en el Registro de Sanidad Vegetal.",
      "pdf": [
        {
          "pathPdf": "BOJA26-062-00004-50003-01_00335460",
          "publicUrl": "https://juntadeandalucia.es/eboja/2026/62/BOJA26-062-00004-50003-01_00335460.pdf"
        }
      ]
    },
    {
      "id": "disposition.2026.62.99",
      "number": 62,
      "date": "31/03/2026",
      "titleSec": "5. Anuncios",
      "organisation": "Ayuntamientos",
      "type": "Anuncio",
      "summaryNoHtml": "Anuncio fuera de disposiciones generales."
    }
  ]
}
""".strip(),
                encoding="utf-8",
            )
            (detail_dir / "disposition-2026-62-2.json").write_text(
                """
{
  "hits": 1,
  "total_hits": 1,
  "results": [
    {
      "id": "disposition.2026.62.2",
      "date": "31/03/2026",
      "titleSec": "1. Disposiciones generales",
      "organisation": "Consejería de Sanidad, Presidencia y Emergencias",
      "type": "Acuerdos",
      "summaryNoHtml": "Acuerdo de 25 de marzo de 2026, del Consejo de Gobierno, por el que se aprueba la Estrategia de Investigación e Innovación en Salud de Andalucía 2026-2027.",
      "body": "<p>ACUERDA</p><p>Primero. Se aprueba la Estrategia de Investigación e Innovación en Salud de Andalucía 2026-2027.</p><p>Segundo. La estrategia fija líneas de actuación para potenciar la investigación en Atención Primaria y Salud Pública.</p>"
    }
  ]
}
""".strip(),
                encoding="utf-8",
            )
            report = collect_boja_normative_sources(
                raw_dir=raw_dir,
                timeout=1,
                no_network=True,
                strict_network=True,
                topic_queries={"sanidad": "sanidad"},
            )
            review_item = report["impact_review_queue"][0]
            review_report = {
                "schema_version": "andalucia_2026_boja_impact_reviews_v1",
                "status": "ok",
                "reviews_total": 1,
                "applied_reviews_total": 0,
                "reviews": [],
                "reviews_by_item_id": {
                    review_item["review_item_id"]: {
                        "review_item_id": review_item["review_item_id"],
                        "review_status": "reviewed_legal_change_only",
                        "impact_status": "legal_change_documented_outcome_pending",
                        "responsibility_status": "official_publisher_observed",
                        "candidate_direction": "unknown",
                        "claim_status": "reviewed_boja_legal_change_no_merit_claim",
                        "reviewed_legal_change_label": "Estrategia de investigacion e innovacion en salud",
                        "review_summary": "Fixture review documents only an official legal-change signal.",
                        "review_confidence": "medium",
                    }
                },
            }
            apply_boja_impact_reviews(report, review_report)
            snapshot = build_snapshot(
                candidature_text=FIXTURE_TEXT,
                candidature_source={"source_id": "test", "status": "from_text", "source_verified": True},
                db_path=Path("/missing.db"),
                source_catalog_path=Path("/missing-catalog.json"),
                boja_report=report,
            )

        self.assertEqual(report["records_total"], 1)
        self.assertEqual(report["topics_with_results_total"], 1)
        self.assertEqual(report["details_available_total"], 1)
        self.assertGreaterEqual(report["fragments_total"], 1)
        self.assertEqual(report["impact_review_queue_total"], report["fragments_total"])
        self.assertEqual(report["reviewed_impact_items_total"], 1)
        self.assertEqual(report["records"][0]["evidence_tier"], "tier_1_primary")
        self.assertEqual(report["records"][0]["claim_status"], "official_normative_record_not_interpreted")
        self.assertEqual(report["records"][0]["fragments"][0]["evidence_tier"], "tier_1_primary")
        self.assertEqual(
            report["records"][0]["fragments"][0]["claim_status"],
            "official_normative_fragment_not_interpreted",
        )
        review_item = report["impact_review_queue"][0]
        self.assertEqual(review_item["claim_status"], "reviewed_boja_legal_change_no_merit_claim")
        self.assertEqual(review_item["review_status"], "reviewed_legal_change_only")
        self.assertEqual(review_item["impact_status"], "legal_change_documented_outcome_pending")
        self.assertEqual(review_item["candidate_direction"], "unknown")
        self.assertEqual(review_item["responsibility_status"], "official_publisher_observed")
        self.assertEqual(review_item["reviewed_legal_change_label"], "Estrategia de investigacion e innovacion en salud")
        self.assertEqual(review_item["priority_rank"], 1)
        self.assertGreater(review_item["priority_score"], 0)
        self.assertEqual(review_item["review_batch_id"], "boja-impact-review-batch-001")
        self.assertIn("total=", review_item["priority_reason"])
        self.assertGreaterEqual(len(review_item["review_questions"]), 4)
        packet = report["impact_review_packet"]
        self.assertEqual(packet["status"], "partially_reviewed")
        self.assertEqual(packet["items_total"], report["impact_review_queue_total"])
        self.assertEqual(packet["reviewed_items_total"], 1)
        self.assertEqual(packet["batches_total"], 1)
        self.assertEqual(packet["batches"][0]["items_total"], report["impact_review_queue_total"])
        self.assertEqual(packet["priority_items"][0]["review_item_id"], review_item["review_item_id"])
        csv_rows = list(csv.DictReader(io.StringIO(impact_review_queue_csv_text(report["impact_review_queue"]))))
        self.assertEqual(len(csv_rows), report["impact_review_queue_total"])
        self.assertEqual(csv_rows[0]["review_item_id"], review_item["review_item_id"])
        self.assertEqual(csv_rows[0]["priority_rank"], "1")
        self.assertEqual(csv_rows[0]["review_batch_id"], "boja-impact-review-batch-001")
        self.assertEqual(csv_rows[0]["claim_status"], "reviewed_boja_legal_change_no_merit_claim")
        self.assertIn("responsible_actor", csv_rows[0]["review_questions"])
        self.assertTrue(csv_rows[0]["source_url"].startswith("https://"))
        self.assertEqual(snapshot["coverage"]["boja_norms_records_total"], 1)
        self.assertGreaterEqual(snapshot["coverage"]["boja_norms_fragments_total"], 1)
        self.assertEqual(
            snapshot["coverage"]["boja_norms_impact_review_items_total"],
            report["impact_review_queue_total"],
        )
        self.assertEqual(snapshot["coverage"]["boja_norms_impact_review_batches_total"], 1)
        self.assertEqual(
            snapshot["coverage"]["boja_norms_priority_review_items_total"],
            report["impact_review_queue_total"],
        )
        self.assertEqual(snapshot["coverage"]["boja_norms_reviewed_impact_items_total"], 1)
        self.assertEqual(snapshot["boja_norms"]["reviewed_impact_items"][0]["review_status"], "reviewed_legal_change_only")
        self.assertEqual(snapshot["coverage"]["issue_accountability_packets_with_reviewed_boja_total"], 1)
        issue_packet = next(
            row for row in snapshot["issue_accountability_packets"]["packets"] if row["topic_id"] == "sanidad"
        )
        self.assertEqual(issue_packet["status"], "reviewed_boja_only")
        self.assertEqual(issue_packet["reviewed_boja_legal_changes_total"], 1)
        self.assertEqual(
            issue_packet["reviewed_boja_samples"][0]["claim_status"],
            "reviewed_boja_legal_change_no_merit_claim",
        )
        boja_lane = next(lane for lane in snapshot["evidence_lanes"] if lane["lane_id"] == "boja_normas_modificaciones")
        self.assertEqual(boja_lane["status"], "official_impact_review_partially_reviewed")

    def test_boja_exact_records_are_added_from_detail_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw_dir = Path(tmp) / "raw"
            detail_dir = raw_dir / "boja_normas" / "details"
            detail_dir.mkdir(parents=True)
            (detail_dir / "disposition-2026-203802-1.json").write_text(
                """
{
  "id": "disposition.2026.203802.1",
  "number": 203802,
  "date": "25/02/2026",
  "titleSec": "1. Disposiciones generales",
  "organisation": "Consejería de Sanidad, Presidencia y Emergencias",
  "type": "Decretos-leyes",
  "summaryNoHtml": "Decreto-ley 1/2026, de 25 de febrero, por el que se adoptan medidas urgentes de apoyo fiscal por daños producidos por borrascas.",
  "body": "<p>El Capítulo I tiene por objeto medidas tributarias dirigidas a paliar daños por borrascas.</p><p>Se aplican al Impuesto sobre la Renta y al Impuesto sobre Transmisiones Patrimoniales y Actos Jurídicos Documentados.</p>",
  "pdf": [
    {
      "publicUrl": "https://juntadeandalucia.es/eboja/2026/203802/BOJA26-203802-00019-2764-01_00333986.pdf"
    }
  ]
}
""".strip(),
                encoding="utf-8",
            )
            report = collect_boja_normative_sources(
                raw_dir=raw_dir,
                timeout=1,
                no_network=True,
                strict_network=True,
                topic_queries={"fiscalidad": "impuesto"},
                exact_records=(
                    {
                        "topic_id": "fiscalidad",
                        "topic_query": "borrascas",
                        "boja_id": "disposition.2026.203802.1",
                        "note": "fixture exact record",
                    },
                ),
            )
            review_item = report["impact_review_queue"][0]
            apply_boja_impact_reviews(
                report,
                {
                    "schema_version": "andalucia_2026_boja_impact_reviews_v1",
                    "status": "ok",
                    "reviews_total": 1,
                    "applied_reviews_total": 0,
                    "reviews": [],
                    "reviews_by_item_id": {
                        review_item["review_item_id"]: {
                            "review_item_id": review_item["review_item_id"],
                            "review_status": "reviewed_legal_change_only",
                            "impact_status": "legal_change_documented_outcome_pending",
                            "responsibility_status": "official_publisher_observed",
                            "candidate_direction": "unknown",
                            "claim_status": "reviewed_boja_legal_change_no_merit_claim",
                            "reviewed_legal_change_label": "Decreto-ley 1/2026 de apoyo fiscal por borrascas",
                            "review_summary": "Fixture documents official BOJA publication only.",
                            "review_confidence": "high",
                        }
                    },
                },
            )

        self.assertEqual(report["records_total"], 1)
        self.assertEqual(report["records"][0]["boja_id"], "disposition.2026.203802.1")
        self.assertEqual(report["records"][0]["topic_id"], "fiscalidad")
        self.assertEqual(report["records"][0]["topic_query"], "borrascas")
        self.assertEqual(report["records"][0]["detail_status"], "cached")
        self.assertEqual(report["records"][0]["exact_record_note"], "fixture exact record")
        self.assertTrue(report["records"][0]["source_url"].endswith("00333986.pdf"))
        self.assertEqual(
            report["impact_review_queue"][0]["review_item_id"],
            "boja-impact-review-disposition-2026-203802-1-fiscalidad-f01",
        )
        self.assertEqual(report["reviewed_impact_items_total"], 1)
        self.assertEqual(report["reviewed_impact_items"][0]["review_confidence"], "high")

    def test_parliament_activity_collects_legislative_initiatives_without_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw_dir = Path(tmp) / "raw"
            parliament_dir = raw_dir / "parlamento_andalucia"
            parliament_dir.mkdir(parents=True)
            (parliament_dir / "legislative_initiatives_leg12.html").write_bytes(
                """
                <html><body>
                <dl class="row mt-3">
                  <dt>Proponente:</dt><dd>G.P. Vox en Andaluc&iacute;a</dd>
                  <dt>Extracto:</dt><dd>Proposici&oacute;n de Ley relativa a derecho a la vivienda</dd>
                  <dt>N&uacute;mero expediente:</dt><dd><a href="portipo.do?numexp=12-25/PPL-000004">12-25/PPL-000004</a></dd>
                  <dt>Fecha creaci&oacute;n:</dt><dd>01/05/2025</dd>
                </dl>
                <dl class="row mt-3">
                  <dt>Proponente:</dt><dd>Consejo de Gobierno de la Junta de Andaluc&iacute;a</dd>
                  <dt>Extracto:</dt><dd>Proyecto de Ley de Patrimonio Cultural de Andaluc&iacute;a</dd>
                  <dt>N&uacute;mero expediente:</dt><dd><a href="portipo.do?numexp=12-25/PL-000011">12-25/PL-000011</a></dd>
                  <dt>Fecha creaci&oacute;n:</dt><dd>11/09/2025</dd>
                </dl>
                </body></html>
                """.encode("iso-8859-1")
            )
            voting_results_html = """
                <html><body>
                  <a href="/webdinamica/portal-web-parlamento/pdf.do?tipodoc=diario&id=201495"
                     title="Visualiza los resultados de las votaciones">
                     Resultado votaciones de la sesi&oacute;n n.&ordm; 81, documento n.&ordm; 71 - 13/03/2026
                  </a>
                </body></html>
                """.encode("iso-8859-1")
            (parliament_dir / "voting_results.html").write_bytes(voting_results_html)
            voting_documents = parse_parliament_voting_documents_html(voting_results_html)
            vote_text_dir = parliament_dir / "vote_text"
            vote_text_dir.mkdir(parents=True)
            (vote_text_dir / f"{voting_documents[0]['document_id']}.txt").write_text(
                VOTING_FIXTURE_TEXT,
                encoding="utf-8",
            )
            report = collect_parlamento_andalucia_activity(
                raw_dir=raw_dir,
                timeout=1,
                no_network=True,
                strict_network=True,
            )
            snapshot = build_snapshot(
                candidature_text=FIXTURE_TEXT,
                candidature_source={"source_id": "test", "status": "from_text", "source_verified": True},
                db_path=Path("/missing.db"),
                source_catalog_path=Path("/missing-catalog.json"),
                parliament_report=report,
            )

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["legislative_initiatives_total"], 2)
        self.assertEqual(report["voting_documents_total"], 1)
        self.assertEqual(report["parsed_vote_events_total"], 1)
        self.assertEqual(report["vote_events_with_initiative_total"], 1)
        self.assertEqual(report["vote_events_with_official_initiative_total"], 1)
        self.assertEqual(report["member_vote_records_total"], 6)
        self.assertEqual(report["vote_events_by_party_topic"][0]["topic_id"], "cultura_patrimonio")
        self.assertEqual(report["vote_events"][0]["claim_status"], "official_vote_count_not_interpreted")
        self.assertEqual(report["vote_events"][0]["review_status"], "needs_legal_effect_actor_and_impact_review")
        self.assertEqual(report["vote_events"][0]["member_votes_total"], 6)
        self.assertEqual(report["vote_events"][0]["initiative_match_status"], "matched_official_initiative")
        self.assertEqual(report["vote_events"][0]["initiative_type_code"], "PL")
        self.assertEqual(report["vote_events"][0]["legal_effect_status"], "rule_triaged_needs_review")
        self.assertEqual(report["vote_events"][0]["legal_effect_kind"], "law_final_approval_vote_rejected")
        self.assertEqual(report["vote_events_with_legal_effect_triage_total"], 1)
        self.assertEqual(report["vote_events_by_legal_effect"][0]["vote_events_total"], 1)
        self.assertEqual(report["vote_impact_review_queue_total"], 1)
        self.assertEqual(report["vote_impact_review_batches_total"], 1)
        self.assertEqual(report["reviewed_vote_items_total"], 0)
        vote_review_item = report["vote_impact_review_queue"][0]
        self.assertEqual(vote_review_item["claim_status"], "parliament_vote_review_queue_only_no_public_claim")
        self.assertEqual(vote_review_item["review_status"], "needs_human_review")
        self.assertEqual(vote_review_item["legal_effect_status"], "rule_triaged_needs_review")
        self.assertEqual(vote_review_item["legal_effect_kind"], "law_final_approval_vote_rejected")
        self.assertEqual(vote_review_item["legal_effect_label"], "rechazo de aprobacion final de ley")
        self.assertEqual(vote_review_item["legal_effect_confidence"], "high")
        self.assertEqual(vote_review_item["responsibility_status"], "actor_not_attributed")
        self.assertEqual(vote_review_item["initiative_match_status"], "matched_official_initiative")
        self.assertEqual(vote_review_item["initiative_type_code"], "PL")
        self.assertEqual(vote_review_item["topic_id"], "cultura_patrimonio")
        self.assertEqual(vote_review_item["priority_rank"], 1)
        self.assertEqual(vote_review_item["review_batch_id"], "parliament-vote-review-batch-001")
        self.assertIn("total=", vote_review_item["priority_reason"])
        self.assertIn("PP:no", vote_review_item["party_positions_summary"])
        self.assertGreaterEqual(len(vote_review_item["review_questions"]), 4)
        vote_packet = report["vote_impact_review_packet"]
        self.assertEqual(vote_packet["status"], "needs_review")
        self.assertEqual(vote_packet["items_total"], 1)
        self.assertEqual(vote_packet["batches_total"], 1)
        self.assertEqual(vote_packet["priority_items"][0]["review_item_id"], vote_review_item["review_item_id"])
        self.assertEqual(vote_packet["legal_effect_counts"][0]["key"], "law_final_approval_vote_rejected")
        vote_csv_rows = list(
            csv.DictReader(io.StringIO(parliament_vote_review_queue_csv_text(report["vote_impact_review_queue"])))
        )
        self.assertEqual(len(vote_csv_rows), 1)
        self.assertEqual(vote_csv_rows[0]["review_item_id"], vote_review_item["review_item_id"])
        self.assertEqual(vote_csv_rows[0]["priority_rank"], "1")
        self.assertEqual(vote_csv_rows[0]["review_batch_id"], "parliament-vote-review-batch-001")
        self.assertEqual(vote_csv_rows[0]["legal_effect_kind"], "law_final_approval_vote_rejected")
        self.assertIn("legal_effect", vote_csv_rows[0]["review_questions"])
        pp_tally = report["vote_events"][0]["party_vote_totals"][0]
        self.assertEqual(pp_tally["party_key"], "pp")
        self.assertEqual(pp_tally["no"], 58)
        self.assertEqual(pp_tally["dominant_position"], "no")
        initiative = report["legislative_initiatives"][0]
        self.assertEqual(initiative["claim_status"], "official_parliamentary_initiative_not_assessed")
        self.assertEqual(initiative["evidence_tier"], "tier_1_primary")
        self.assertIn("VOX", initiative["proponent_party_keys"])
        self.assertEqual(report["legislative_initiatives_by_party_key"][0]["key"], "VOX")
        self.assertEqual(snapshot["coverage"]["parliament_andalucia_legislative_initiatives_total"], 2)
        self.assertEqual(snapshot["coverage"]["parliament_andalucia_voting_documents_total"], 1)
        self.assertEqual(snapshot["coverage"]["parliament_andalucia_parsed_vote_events_total"], 1)
        self.assertEqual(snapshot["coverage"]["parliament_andalucia_vote_events_with_official_initiative_total"], 1)
        self.assertEqual(snapshot["coverage"]["parliament_andalucia_vote_events_with_legal_effect_triage_total"], 1)
        self.assertEqual(snapshot["coverage"]["parliament_andalucia_party_topic_vote_rows_total"], 5)
        self.assertEqual(snapshot["coverage"]["parliament_andalucia_legal_effect_rows_total"], 1)
        self.assertEqual(snapshot["coverage"]["parliament_andalucia_member_vote_records_total"], 6)
        self.assertEqual(snapshot["coverage"]["parliament_andalucia_focus_candidates_with_member_votes_total"], 1)
        self.assertEqual(snapshot["coverage"]["parliament_andalucia_party_group_initiatives_total"], 1)
        self.assertEqual(snapshot["coverage"]["parliament_andalucia_vote_impact_review_items_total"], 1)
        self.assertEqual(snapshot["coverage"]["parliament_andalucia_vote_impact_review_batches_total"], 1)
        self.assertEqual(snapshot["coverage"]["parliament_andalucia_priority_vote_review_items_total"], 1)
        self.assertEqual(snapshot["coverage"]["parliament_andalucia_reviewed_vote_items_total"], 0)
        juanma = next(row for row in snapshot["focus_candidates"] if row["focus_id"] == "pp-juan-manuel-moreno-bonilla")
        self.assertEqual(juanma["parliament_vote_summary"]["no"], 1)
        self.assertEqual(snapshot["parliament_activity"]["candidate_vote_summaries_total"], 1)
        self.assertNotIn("member_votes", snapshot["parliament_activity"])
        parliament_lane = next(
            lane for lane in snapshot["evidence_lanes"] if lane["lane_id"] == "parlamento_andalucia_actividad"
        )
        self.assertEqual(parliament_lane["status"], "official_vote_review_queue")

        review_report = {
            "schema_version": "test",
            "status": "ok",
            "reviews_total": 1,
            "applied_reviews_total": 0,
            "reviews": [],
            "reviews_by_item_id": {
                vote_review_item["review_item_id"]: {
                    "review_item_id": vote_review_item["review_item_id"],
                    "vote_event_id": vote_review_item["vote_event_id"],
                    "review_status": "reviewed_vote_result_only",
                    "legal_effect_status": "observed_rejection_vote",
                    "effect_outcome": "rejected_by_majority_no",
                    "impact_status": "outcome_not_reviewed",
                    "responsibility_status": "party_positions_observed",
                    "candidate_direction": "unknown",
                    "reviewed_issue_label": "Patrimonio cultural",
                    "review_summary": "Fixture review observes only the official vote result.",
                    "review_confidence": "medium",
                }
            },
            "reviews_by_event_id": {},
        }
        apply_parliament_vote_reviews(report, review_report)
        issue_reviews_report = {
            "schema_version": "andalucia_2026_issue_reviews_v1",
            "status": "ok",
            "reviews_total": 1,
            "applied_reviews_total": 0,
            "reviews": [
                {
                    "review_id": "issue-review-cultura-fixture",
                    "topic_id": "cultura_patrimonio",
                    "topic_label": "Cultura y patrimonio",
                    "review_status": "reviewed_issue_vote_direction_and_actor_partial",
                    "claim_status": "issue_direction_actor_review_no_merit_or_blame",
                    "citizen_direction_status": "legal_direction_documented_outcome_pending",
                    "responsible_actor_status": "responsible_actor_partially_observed",
                    "budget_execution_status": "budget_execution_not_linked",
                    "outcome_status": "outcome_not_linked",
                    "review_summary": "Fixture issue review documents direction and observed actors only.",
                }
            ],
        }
        reviewed_snapshot = build_snapshot(
            candidature_text=FIXTURE_TEXT,
            candidature_source={"source_id": "test", "status": "from_text", "source_verified": True},
            db_path=Path("/missing.db"),
            source_catalog_path=Path("/missing-catalog.json"),
            parliament_report=report,
            issue_reviews_report=issue_reviews_report,
        )
        self.assertEqual(reviewed_snapshot["coverage"]["published_merit_blame_claims_total"], 0)
        self.assertEqual(reviewed_snapshot["coverage"]["published_accountability_claims_total"], 6)
        self.assertEqual(reviewed_snapshot["coverage"]["published_observed_responsibility_claims_total"], 6)
        self.assertEqual(reviewed_snapshot["coverage"]["published_party_legislative_claims_total"], 5)
        self.assertEqual(reviewed_snapshot["coverage"]["published_candidate_legislative_claims_total"], 1)
        self.assertEqual(reviewed_snapshot["published_accountability_claims"]["claims_total"], 6)
        self.assertEqual(reviewed_snapshot["published_accountability_claims"]["party_claims_total"], 5)
        self.assertEqual(reviewed_snapshot["published_accountability_claims"]["candidate_claims_total"], 1)
        self.assertEqual(
            reviewed_snapshot["published_accountability_claims"]["claim_status"],
            "published_observed_responsibility_no_merit_or_blame",
        )
        pp_claim = next(
            row
            for row in reviewed_snapshot["published_accountability_claims"]["claims"]
            if row["actor_kind"] == "party" and row["party_key"] == "pp"
        )
        self.assertEqual(pp_claim["relation_to_outcome"], "with_reviewed_outcome")
        self.assertEqual(pp_claim["claim_status"], "published_observed_responsibility_no_merit_or_blame")
        self.assertEqual(pp_claim["evidence"][0]["source_kind"], "official_vote_pdf_text")
        candidate_claim = next(
            row
            for row in reviewed_snapshot["published_accountability_claims"]["claims"]
            if row["actor_kind"] == "candidate"
        )
        self.assertEqual(candidate_claim["person_name"], "JUAN MANUEL MORENO BONILLA")
        self.assertEqual(candidate_claim["relation_to_outcome"], "with_reviewed_outcome")
        self.assertEqual(reviewed_snapshot["coverage"]["parliament_andalucia_reviewed_vote_items_total"], 1)
        self.assertEqual(reviewed_snapshot["coverage"]["parliament_andalucia_reviewed_party_vote_summaries_total"], 5)
        self.assertEqual(reviewed_snapshot["coverage"]["parliament_andalucia_reviewed_candidate_vote_summaries_total"], 1)
        self.assertEqual(
            reviewed_snapshot["coverage"]["responsibility_party_profiles_with_reviewed_vote_signals_total"],
            3,
        )
        self.assertEqual(
            reviewed_snapshot["coverage"]["responsibility_focus_candidate_profiles_with_reviewed_vote_signals_total"],
            1,
        )
        self.assertEqual(reviewed_snapshot["coverage"]["issue_accountability_packets_with_reviewed_vote_total"], 1)
        self.assertEqual(
            reviewed_snapshot["coverage"]["issue_accountability_packets_with_observed_responsibility_total"],
            1,
        )
        self.assertEqual(reviewed_snapshot["coverage"]["issue_accountability_observed_responsibility_claims_total"], 6)
        self.assertEqual(reviewed_snapshot["coverage"]["issue_accountability_issue_reviews_total"], 1)
        self.assertEqual(reviewed_snapshot["coverage"]["issue_accountability_issue_direction_reviews_total"], 1)
        self.assertEqual(reviewed_snapshot["coverage"]["issue_accountability_issue_actor_reviews_total"], 1)
        issue_packet = next(
            row
            for row in reviewed_snapshot["issue_accountability_packets"]["packets"]
            if row["topic_id"] == "cultura_patrimonio"
        )
        self.assertEqual(issue_packet["status"], "reviewed_vote_only")
        self.assertEqual(issue_packet["reviewed_vote_items_total"], 1)
        self.assertEqual(issue_packet["reviewed_vote_party_profiles_total"], 5)
        self.assertEqual(issue_packet["reviewed_vote_boja_expected_total"], 0)
        self.assertEqual(issue_packet["reviewed_vote_boja_not_expected_total"], 1)
        self.assertEqual(
            issue_packet["reviewed_vote_boja_expectation_status"],
            "boja_not_expected_for_reviewed_vote_effects",
        )
        self.assertEqual(issue_packet["reviewed_vote_samples"][0]["topic_source"], "reviewed_issue_label_seed")
        self.assertEqual(issue_packet["observed_responsibility_claims_total"], 6)
        self.assertEqual(issue_packet["observed_party_claims_total"], 5)
        self.assertEqual(issue_packet["observed_candidate_claims_total"], 1)
        self.assertEqual(issue_packet["observed_responsibility_actor_profiles_total"], 6)
        self.assertEqual(issue_packet["issue_review_status"], "reviewed_issue_vote_direction_and_actor_partial")
        self.assertIn("missing_execution_owner", issue_packet["open_gaps"])
        self.assertNotIn("missing_citizen_direction", issue_packet["open_gaps"])
        self.assertNotIn("missing_responsible_actor", issue_packet["open_gaps"])
        self.assertEqual(
            issue_packet["observed_responsibility_claim_samples"][0]["claim_status"],
            "published_observed_responsibility_no_merit_or_blame",
        )
        self.assertEqual(reviewed_snapshot["issue_accountability_reviews"]["applied_reviews_total"], 1)
        issue_review_report = {
            "schema_version": "andalucia_2026_issue_reviews_v1",
            "status": "ok",
            "reviews_total": 1,
            "applied_reviews_total": 0,
            "reviews": [
                {
                    "review_id": "test-issue-review-cultura",
                    "topic_id": "cultura_patrimonio",
                    "topic_label": "Cultura y patrimonio",
                    "review_status": "reviewed_issue_direction_and_actor_partial",
                    "claim_status": "issue_direction_actor_review_no_merit_or_blame",
                    "interpretation_status": "legal_direction_and_actor_signal_documented_outcome_pending",
                    "citizen_direction_status": "legal_direction_documented_outcome_pending",
                    "citizen_direction_label": "Fixture direction documented.",
                    "responsible_actor_status": "legislative_and_publisher_actor_observed_execution_owner_pending",
                    "responsible_actor_label": "Fixture actor signal documented.",
                    "execution_owner_status": "execution_owner_linked_budget_amount_pending",
                    "execution_owner_label": "Fixture execution owner documented.",
                    "budget_execution_status": "budget_allocation_linked_execution_pending",
                    "budget_execution_label": "Fixture budget allocation documented; execution remains pending.",
                    "outcome_status": "outcome_not_linked",
                    "merit_blame_status": "closed_pending_execution_and_outcomes",
                    "review_summary": "Fixture issue review documents direction and actor only.",
                    "review_confidence": "medium",
                    "evidence_refs": [
                        {
                            "source_kind": "official_vote_pdf_text",
                            "source_locator": "fixture.txt:1",
                            "evidence_excerpt": "Fixture official vote text.",
                        }
                    ],
                    "execution_refs": [
                        {
                            "source_kind": "official_boja_text",
                            "source_locator": "fixture.txt:2",
                            "evidence_excerpt": "Fixture execution owner text.",
                        }
                    ],
                    "budget_refs": [
                        {
                            "source_kind": "official_budget_xlsx",
                            "source_id": "junta_presupuesto_2026_partidas_gastos",
                            "source_locator": "fixture.xlsx:fila 7",
                            "source_url": "https://example.test/fixture.xlsx",
                            "program_code": "44E",
                            "program_name": "GESTION FORESTAL Y BIODIVERSIDAD",
                            "org_section": "CONSEJERIA DE SOSTENIBILIDAD Y MEDIO AMBIENTE",
                            "budget_item": "A TECNOLOGIAS Y SERVICIOS AGRARIOS S.A.",
                            "budget_project": "APOYO REDACCION LEY DE MONTES",
                            "amount_eur": 50000,
                            "review_status": "budget_allocation_candidate_reviewed_execution_pending",
                        }
                    ],
                    "open_limitations": [
                        "budget_allocation_not_execution",
                        "budget_execution_not_linked",
                        "outcome_not_linked",
                    ],
                }
            ],
            "reviews_by_topic": {},
        }
        issue_reviewed_snapshot = build_snapshot(
            candidature_text=FIXTURE_TEXT,
            candidature_source={"source_id": "test", "status": "from_text", "source_verified": True},
            db_path=Path("/missing.db"),
            source_catalog_path=Path("/missing-catalog.json"),
            parliament_report=report,
            issue_reviews_report=issue_review_report,
        )
        reviewed_issue_packet = next(
            row
            for row in issue_reviewed_snapshot["issue_accountability_packets"]["packets"]
            if row["topic_id"] == "cultura_patrimonio"
        )
        self.assertEqual(issue_reviewed_snapshot["coverage"]["issue_accountability_reviewed_issues_total"], 1)
        self.assertEqual(issue_reviewed_snapshot["coverage"]["issue_accountability_direction_reviewed_total"], 1)
        self.assertEqual(issue_reviewed_snapshot["coverage"]["issue_accountability_actor_reviewed_total"], 1)
        self.assertEqual(issue_reviewed_snapshot["coverage"]["issue_accountability_execution_owner_reviewed_total"], 1)
        self.assertEqual(issue_reviewed_snapshot["coverage"]["issue_accountability_budget_allocation_reviewed_total"], 1)
        self.assertEqual(issue_reviewed_snapshot["issue_accountability_reviews"]["applied_reviews_total"], 1)
        self.assertEqual(
            reviewed_issue_packet["issue_review_status"],
            "reviewed_issue_direction_and_actor_partial",
        )
        self.assertNotIn("missing_citizen_direction", reviewed_issue_packet["open_gaps"])
        self.assertNotIn("missing_responsible_actor", reviewed_issue_packet["open_gaps"])
        self.assertNotIn("missing_execution_owner", reviewed_issue_packet["open_gaps"])
        self.assertIn("missing_budget_execution", reviewed_issue_packet["open_gaps"])
        self.assertIn("missing_outcomes", reviewed_issue_packet["open_gaps"])
        self.assertEqual(
            reviewed_issue_packet["issue_review"]["execution_owner_status"],
            "execution_owner_linked_budget_amount_pending",
        )
        self.assertEqual(
            reviewed_issue_packet["issue_review"]["execution_refs"][0]["source_kind"],
            "official_boja_text",
        )
        self.assertEqual(
            reviewed_issue_packet["issue_review"]["budget_execution_status"],
            "budget_allocation_linked_execution_pending",
        )
        self.assertEqual(
            reviewed_issue_packet["issue_review"]["budget_refs"][0]["amount_eur"],
            50000,
        )
        pp = next(row for row in reviewed_snapshot["parties"] if row["party_key"] == "pp")
        self.assertEqual(pp["reviewed_legislative_impact_summary"]["reviewed_vote_events_total"], 1)
        self.assertEqual(pp["reviewed_legislative_impact_summary"]["supported_rejected_effect_total"], 1)
        self.assertEqual(pp["reviewed_legislative_impact_summary"]["voted_with_reviewed_outcome_total"], 1)
        self.assertEqual(pp["reviewed_legislative_impact_summary"]["observed_other"], 0)
        pp_profile = next(
            row for row in reviewed_snapshot["responsibility_comparison"]["party_profiles"] if row["party_key"] == "pp"
        )
        self.assertEqual(pp_profile["reviewed_vote_events_total"], 1)
        self.assertEqual(pp_profile["voted_with_reviewed_outcome_total"], 1)
        self.assertEqual(pp_profile["claim_status"], "responsibility_evidence_comparison_only_no_merit_or_blame_claim")
        reviewed_juanma = next(
            row for row in reviewed_snapshot["focus_candidates"] if row["focus_id"] == "pp-juan-manuel-moreno-bonilla"
        )
        self.assertEqual(
            reviewed_juanma["reviewed_legislative_impact_summary"]["supported_rejected_effect_total"],
            1,
        )
        self.assertEqual(
            reviewed_juanma["reviewed_legislative_impact_summary"]["claim_status"],
            "reviewed_legislative_vote_signal_no_merit_claim",
        )
        self.assertEqual(review_report["applied_reviews_total"], 1)

    def test_parliament_activity_collects_vote_documents_from_cached_initiative_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw_dir = Path(tmp) / "raw"
            parliament_dir = raw_dir / "parlamento_andalucia"
            parliament_dir.mkdir(parents=True)
            initiatives_html = """
                <html><body>
                <dl class="row mt-3">
                  <dt>Proponente:</dt><dd>Consejo de Gobierno de la Junta de Andaluc&iacute;a</dd>
                  <dt>Extracto:</dt><dd>Proyecto de Ley de Patrimonio Cultural de Andaluc&iacute;a</dd>
                  <dt>N&uacute;mero expediente:</dt><dd><a href="portipo.do?numexp=12-25/PL-000011">12-25/PL-000011</a></dd>
                  <dt>Fecha creaci&oacute;n:</dt><dd>11/09/2025</dd>
                </dl>
                </body></html>
                """.encode("iso-8859-1")
            (parliament_dir / "legislative_initiatives_leg12.html").write_bytes(initiatives_html)
            (parliament_dir / "voting_results.html").write_bytes(b"<html><body></body></html>")
            initiative = parse_parliament_initiatives_html(initiatives_html)[0]
            detail_html = """
                <html><body>
                  <a href="/webdinamica/portal-web-parlamento/pdf.do?tipodoc=diario&id=202020"
                     title="Visualiza el sentido del voto en una nueva ventana de navegador">
                     Sentido del voto
                  </a>
                </body></html>
                """.encode("iso-8859-1")
            detail_path = snapshot_module.parliament_initiative_detail_cache_path(parliament_dir, initiative)
            detail_path.parent.mkdir(parents=True)
            detail_path.write_bytes(detail_html)
            voting_documents = snapshot_module.parse_parliament_initiative_detail_vote_documents(
                detail_html,
                initiative,
            )
            vote_text_dir = parliament_dir / "vote_text"
            vote_text_dir.mkdir(parents=True)
            (vote_text_dir / f"{voting_documents[0]['document_id']}.txt").write_text(
                VOTING_FIXTURE_TEXT,
                encoding="utf-8",
            )

            report = collect_parlamento_andalucia_activity(
                raw_dir=raw_dir,
                timeout=1,
                no_network=True,
                strict_network=True,
            )

        self.assertEqual(report["voting_result_documents_total"], 0)
        self.assertEqual(report["initiative_detail_pages_checked_total"], 1)
        self.assertEqual(report["initiative_detail_pages_with_vote_documents_total"], 1)
        self.assertEqual(report["initiative_detail_vote_documents_total"], 1)
        self.assertEqual(report["initiative_detail_vote_documents_new_total"], 1)
        self.assertEqual(report["voting_documents_total"], 1)
        self.assertEqual(report["parsed_vote_events_total"], 1)
        self.assertEqual(report["vote_events"][0]["initiative_match_status"], "matched_official_initiative")
        self.assertEqual(report["vote_events"][0]["topic_id"], "cultura_patrimonio")
        self.assertEqual(report["vote_impact_review_queue_total"], 1)

    def test_execution_evidence_queue_plans_vote_only_topics_after_issue_review(self) -> None:
        queue = build_issue_execution_evidence_queue(
            {
                "packets": [
                    {
                        "topic_id": "sanidad",
                        "topic_label": "Sanidad",
                        "status": "reviewed_vote_only",
                        "issue_review_status": "reviewed_issue_vote_direction_and_actor_partial",
                        "open_gaps": [
                            "missing_execution_owner",
                            "missing_budget_execution",
                            "missing_outcomes",
                        ],
                    },
                    {
                        "topic_id": "vivienda",
                        "topic_label": "Vivienda",
                        "status": "reviewed_vote_only",
                        "issue_review_status": "reviewed_issue_vote_direction_and_actor_partial",
                        "open_gaps": ["missing_budget_execution", "missing_outcomes"],
                    },
                    {
                        "topic_id": "seguridad_libertades",
                        "topic_label": "Seguridad y libertades",
                        "status": "reviewed_vote_only",
                        "issue_review_status": "reviewed_issue_vote_direction_and_actor_partial",
                        "open_gaps": ["missing_budget_execution", "missing_outcomes"],
                    },
                    {
                        "topic_id": "fiscalidad",
                        "topic_label": "Fiscalidad",
                        "status": "program_vote_boja_reviewed",
                        "issue_review_status": "reviewed_issue_vote_boja_direction_actor_execution_owner_partial",
                        "open_gaps": ["missing_budget_execution", "missing_outcomes"],
                    },
                    {
                        "topic_id": "empleo",
                        "topic_label": "Empleo",
                        "status": "reviewed_vote_only",
                        "issue_review_status": "reviewed_issue_vote_direction_and_actor_partial",
                        "open_gaps": [
                            "missing_execution_owner",
                            "missing_budget_execution",
                            "missing_outcomes",
                        ],
                    },
                    {
                        "topic_id": "transparencia_corrupcion",
                        "topic_label": "Transparencia y corrupcion",
                        "status": "program_vote_boja_reviewed",
                        "issue_review_status": "reviewed_issue_vote_boja_direction_actor_partial",
                        "open_gaps": [
                            "missing_execution_owner",
                            "missing_budget_execution",
                            "missing_outcomes",
                        ],
                    },
                ]
            }
        )

        self.assertEqual(queue["topics_total"], 6)
        topic_gap_ids = {(row["topic_id"], row["gap_id"]) for row in queue["queue"]}
        self.assertIn(("sanidad", "missing_execution_owner"), topic_gap_ids)
        self.assertIn(("sanidad", "missing_budget_execution"), topic_gap_ids)
        self.assertIn(("sanidad", "missing_outcomes"), topic_gap_ids)
        self.assertIn(("vivienda", "missing_budget_execution"), topic_gap_ids)
        self.assertIn(("seguridad_libertades", "missing_outcomes"), topic_gap_ids)
        self.assertIn(("fiscalidad", "missing_budget_execution"), topic_gap_ids)
        self.assertIn(("empleo", "missing_execution_owner"), topic_gap_ids)
        self.assertIn(("empleo", "missing_budget_execution"), topic_gap_ids)
        self.assertIn(("empleo", "missing_outcomes"), topic_gap_ids)
        self.assertIn(("transparencia_corrupcion", "missing_execution_owner"), topic_gap_ids)
        self.assertIn(("transparencia_corrupcion", "missing_budget_execution"), topic_gap_ids)
        self.assertIn(("transparencia_corrupcion", "missing_outcomes"), topic_gap_ids)
        sanidad_budget = next(
            row
            for row in queue["queue"]
            if row["topic_id"] == "sanidad" and row["gap_id"] == "missing_budget_execution"
        )
        self.assertIn("junta_presupuesto_2026_partidas_gastos", sanidad_budget["source_candidate_ids"])
        self.assertIn("junta_tesoreria_2025_pagos_agregados", sanidad_budget["source_candidate_ids"])
        vivienda_outcome = next(
            row
            for row in queue["queue"]
            if row["topic_id"] == "vivienda" and row["gap_id"] == "missing_outcomes"
        )
        self.assertEqual(vivienda_outcome["source_candidate_ids"], ["junta_presupuesto_2026_objetivos_indicadores"])
        empleo_budget = next(
            row
            for row in queue["queue"]
            if row["topic_id"] == "empleo" and row["gap_id"] == "missing_budget_execution"
        )
        self.assertIn("junta_subvenciones_programas_prioritarios", empleo_budget["source_candidate_ids"])
        self.assertIn("servicio andaluz de empleo", empleo_budget["search_terms"])
        transparencia_owner = next(
            row
            for row in queue["queue"]
            if row["topic_id"] == "transparencia_corrupcion" and row["gap_id"] == "missing_execution_owner"
        )
        self.assertIn("junta_perfiles_contratante_licitaciones", transparencia_owner["source_candidate_ids"])
        self.assertIn("oficina andaluza contra el fraude", transparencia_owner["search_terms"])

    def test_execution_evidence_queue_targets_budget_and_outcome_gaps(self) -> None:
        queue = build_issue_execution_evidence_queue(
            {
                "packets": [
                    {
                        "topic_id": "campo_agua",
                        "topic_label": "Campo y agua",
                        "status": "program_vote_boja_reviewed",
                        "issue_review_status": "reviewed_issue_direction_actor_and_execution_owner_partial",
                        "open_gaps": ["missing_budget_execution", "missing_outcomes"],
                    }
                ]
            }
        )

        self.assertEqual(queue["queue_total"], 2)
        self.assertEqual(queue["topics_total"], 1)
        self.assertEqual(queue["verified_source_candidates_total"], queue["source_candidates_total"])
        budget_item = next(row for row in queue["queue"] if row["gap_id"] == "missing_budget_execution")
        self.assertIn("bdns_convocatorias", budget_item["source_candidate_ids"])
        self.assertIn("junta_presupuesto_2026_partidas_gastos", budget_item["source_candidate_ids"])
        self.assertIn("junta_contratos_menores_2024", budget_item["source_candidate_ids"])
        self.assertIn("junta_contratos_menores_2025", budget_item["source_candidate_ids"])
        outcome_item = next(row for row in queue["queue"] if row["gap_id"] == "missing_outcomes")
        self.assertEqual(
            outcome_item["source_candidate_ids"],
            ["junta_presupuesto_2026_objetivos_indicadores", "ieca_ods_agua_631_111614"],
        )

        csv_text = execution_evidence_queue_csv_text(queue["queue"])
        rows = list(csv.DictReader(io.StringIO(csv_text)))
        self.assertEqual(len(rows), 2)
        self.assertIn("junta_presupuesto_2026_partidas_gastos", rows[0]["source_candidate_ids"])

        execution_review = {
            "review_item_id": "test-budget-review",
            "candidate_row_id": "test-budget-row",
            "topic_id": "campo_agua",
            "gap_id": "missing_budget_execution",
            "source_id": "junta_presupuesto_2026_partidas_gastos",
            "source_locator": "partidas-de-gastos.xlsx:fila 2",
            "evidence_kind": "budget_plan",
            "review_status": "reviewed_budget_plan_linked_execution_pending",
            "claim_status": "official_budget_indicator_review_no_merit_or_blame",
            "interpretation_status": "budget_plan_only_execution_beneficiaries_and_outcomes_pending",
            "reviewed_label": "Saneamiento y depuracion",
            "amount_eur": 138832165,
            "review_summary": "Budget plan only; no executed spend or outcome.",
        }
        queue_with_candidates = build_issue_execution_evidence_queue(
            {
                "packets": [
                    {
                        "topic_id": "campo_agua",
                        "topic_label": "Campo y agua",
                        "status": "program_vote_boja_reviewed",
                        "issue_review_status": "reviewed_issue_direction_actor_and_execution_owner_partial",
                        "open_gaps": ["missing_budget_execution"],
                    }
                ]
            },
            {
                "candidate_rows_total": 1,
                "budget_candidate_rows_total": 1,
                "outcome_candidate_rows_total": 0,
                "source_files_total": 1,
                "source_files_cached_total": 1,
                "source_file_errors_total": 0,
                "source_files": [],
                "groups_by_key": {
                    "campo_agua:missing_budget_execution": {
                        "candidate_rows_total": 1,
                        "top_candidate_rows": [
                            {
                                "candidate_row_id": "test-budget-row",
                                "source_id": "junta_presupuesto_2026_partidas_gastos",
                                "source_locator": "partidas-de-gastos.xlsx:fila 2",
                                "summary": "Saneamiento y depuracion",
                                "amount_eur": 138832165,
                            }
                        ],
                    }
                },
            },
            {
                "reviews_total": 1,
                "reviews": [execution_review],
                "reviews_by_candidate_row_id": {"test-budget-row": execution_review},
                "reviews_by_locator": {},
                "reviews_by_topic_gap": {},
            },
        )
        item = queue_with_candidates["queue"][0]
        self.assertEqual(queue_with_candidates["status"], "reviewed_budget_plan_rows_execution_pending")
        self.assertEqual(item["status"], "reviewed_budget_plan_rows_execution_pending")
        self.assertEqual(item["official_candidate_rows_total"], 1)
        self.assertEqual(item["official_candidate_rows"][0]["amount_eur"], 138832165)
        self.assertEqual(item["reviewed_evidence_rows_total"], 1)
        self.assertEqual(item["reviewed_evidence_rows"][0]["claim_status"], "official_budget_indicator_review_no_merit_or_blame")
        self.assertEqual(queue_with_candidates["reviewed_evidence_rows_total"], 1)
        self.assertEqual(queue_with_candidates["reviewed_budget_plan_rows_total"], 1)
        self.assertEqual(queue_with_candidates["reviewed_contract_rows_total"], 0)
        self.assertEqual(queue_with_candidates["reviewed_indicator_target_rows_total"], 0)
        candidate_rows = list(csv.DictReader(io.StringIO(execution_evidence_queue_csv_text([item]))))
        self.assertEqual(candidate_rows[0]["official_candidate_rows_total"], "1")
        self.assertIn("Saneamiento y depuracion", candidate_rows[0]["top_official_candidate_rows"])
        self.assertEqual(candidate_rows[0]["reviewed_evidence_rows_total"], "1")
        self.assertIn("Saneamiento y depuracion", candidate_rows[0]["top_reviewed_evidence_rows"])

        contract_review = {
            "review_item_id": "test-contract-review",
            "candidate_row_id": "test-contract-row",
            "topic_id": "campo_agua",
            "gap_id": "missing_budget_execution",
            "source_id": "junta_contratos_menores_2025",
            "source_locator": "menores_2025_v1_20260122.json:fila 4",
            "evidence_kind": "contract_award",
            "review_status": "reviewed_contract_award_linked_outcome_pending",
            "claim_status": "official_budget_contract_indicator_review_no_merit_or_blame",
            "reviewed_label": "Contrato depuracion",
            "amount_eur": 36449,
        }
        queue_with_contract_review = build_issue_execution_evidence_queue(
            {
                "packets": [
                    {
                        "topic_id": "campo_agua",
                        "topic_label": "Campo y agua",
                        "status": "program_vote_boja_reviewed",
                        "issue_review_status": "reviewed_issue_direction_actor_and_execution_owner_partial",
                        "open_gaps": ["missing_budget_execution"],
                    }
                ]
            },
            {
                "candidate_rows_total": 1,
                "budget_candidate_rows_total": 1,
                "contract_candidate_rows_total": 1,
                "outcome_candidate_rows_total": 0,
                "source_files_total": 1,
                "source_files_cached_total": 1,
                "source_file_errors_total": 0,
                "source_files": [],
                "groups_by_key": {
                    "campo_agua:missing_budget_execution": {
                        "candidate_rows_total": 1,
                        "candidate_rows_by_source": {"junta_contratos_menores_2025": 1},
                        "top_candidate_rows": [
                            {
                                "candidate_row_id": "test-contract-row",
                                "source_id": "junta_contratos_menores_2025",
                                "source_locator": "menores_2025_v1_20260122.json:fila 4",
                                "summary": "Contrato depuracion",
                                "amount_eur": 36449,
                            }
                        ],
                    }
                },
            },
            {
                "reviews_total": 1,
                "reviews": [contract_review],
                "reviews_by_candidate_row_id": {"test-contract-row": contract_review},
                "reviews_by_locator": {},
                "reviews_by_topic_gap": {},
            },
        )
        self.assertEqual(queue_with_contract_review["status"], "reviewed_contract_rows_outcome_pending")
        self.assertEqual(queue_with_contract_review["reviewed_contract_rows_total"], 1)
        self.assertEqual(queue_with_contract_review["reviewed_budget_plan_rows_total"], 0)

        outcome_review = {
            "review_item_id": "test-outcome-review",
            "candidate_row_id": "test-outcome-row",
            "topic_id": "campo_agua",
            "gap_id": "missing_outcomes",
            "source_id": "ieca_ods_agua_631_111614",
            "source_locator": "ieca_ods_agua_631_111614.json:fila 1",
            "evidence_kind": "observed_outcome_series",
            "review_status": "reviewed_observed_outcome_baseline_post_change_pending",
            "claim_status": "official_observed_outcome_baseline_no_merit_or_blame",
            "reviewed_label": "Carga contaminante depurada adecuadamente",
            "indicator_name": "Carga contaminante depurada adecuadamente",
            "indicator_unit": "PORCENTAJE",
            "outcome_year": "2022",
            "outcome_value_format": "77,81",
        }
        queue_with_outcome_review = build_issue_execution_evidence_queue(
            {
                "packets": [
                    {
                        "topic_id": "campo_agua",
                        "topic_label": "Campo y agua",
                        "status": "program_vote_boja_reviewed",
                        "issue_review_status": "reviewed_issue_direction_actor_and_execution_owner_partial",
                        "open_gaps": ["missing_outcomes"],
                    }
                ]
            },
            {
                "candidate_rows_total": 1,
                "budget_candidate_rows_total": 0,
                "contract_candidate_rows_total": 0,
                "outcome_candidate_rows_total": 1,
                "source_files_total": 1,
                "source_files_cached_total": 1,
                "source_file_errors_total": 0,
                "source_files": [],
                "groups_by_key": {
                    "campo_agua:missing_outcomes": {
                        "candidate_rows_total": 1,
                        "candidate_rows_by_source": {"ieca_ods_agua_631_111614": 1},
                        "top_candidate_rows": [
                            {
                                "candidate_row_id": "test-outcome-row",
                                "source_id": "ieca_ods_agua_631_111614",
                                "source_locator": "ieca_ods_agua_631_111614.json:fila 1",
                                "summary": "Carga contaminante depurada adecuadamente",
                                "indicator_unit": "PORCENTAJE",
                                "outcome_territory": "Andalucía",
                                "outcome_year": "2022",
                                "outcome_value_format": "77,81",
                            }
                        ],
                    }
                },
            },
            {
                "reviews_total": 1,
                "reviews": [outcome_review],
                "reviews_by_candidate_row_id": {"test-outcome-row": outcome_review},
                "reviews_by_locator": {},
                "reviews_by_topic_gap": {},
            },
        )
        outcome_item = queue_with_outcome_review["queue"][0]
        self.assertEqual(queue_with_outcome_review["status"], "reviewed_observed_outcome_baseline_rows_post_change_pending")
        self.assertEqual(outcome_item["status"], "reviewed_observed_outcome_baseline_rows_post_change_pending")
        self.assertEqual(queue_with_outcome_review["reviewed_observed_outcome_rows_total"], 1)
        self.assertEqual(outcome_item["reviewed_evidence_rows"][0]["outcome_latest_year"], "2022")
        self.assertEqual(outcome_item["reviewed_evidence_rows"][0]["outcome_latest_value_format"], "77,81")

    def test_issue_readiness_report_classifies_blockers_without_merit_claims(self) -> None:
        queue = {
            "queue": [
                {
                    "topic_id": "campo_agua",
                    "gap_id": "missing_budget_execution",
                    "source_candidate_ids": ["junta_presupuesto_2026_partidas_gastos"],
                    "reviewed_evidence_rows": [
                        {
                            "evidence_kind": "budget_plan",
                            "review_status": "reviewed_budget_plan_linked_execution_pending",
                            "reviewed_label": "Saneamiento y depuracion",
                            "program_code": "51D",
                            "source_id": "junta_presupuesto_2026_partidas_gastos",
                            "source_locator": "partidas-de-gastos.xlsx:fila 3735",
                            "amount_eur": 138832165,
                        }
                    ],
                },
                {
                    "topic_id": "campo_agua",
                    "gap_id": "missing_outcomes",
                    "source_candidate_ids": ["ieca_ods_agua_631_111614"],
                    "reviewed_evidence_rows": [
                        {
                            "evidence_kind": "observed_outcome_series",
                            "review_status": "reviewed_observed_outcome_baseline_post_change_pending",
                            "outcome_year": "2022",
                        }
                    ],
                },
            ]
        }
        report = build_issue_readiness_report(
            {
                "packets": [
                    {
                        "topic_id": "campo_agua",
                        "topic_label": "Campo y agua",
                        "program_measures_total": 2,
                        "reviewed_vote_items_total": 1,
                        "reviewed_boja_legal_changes_total": 1,
                        "observed_responsibility_claims_total": 4,
                        "issue_review_status": "reviewed_issue_direction_actor_execution_owner_and_budget_allocation_partial",
                        "open_gaps": ["missing_budget_execution", "missing_outcomes"],
                    }
                ]
            },
            queue,
        )

        self.assertEqual(report["claim_status"], "readiness_classifier_no_merit_or_blame_claim")
        self.assertEqual(report["publishable_merit_blame_topics_total"], 0)
        self.assertEqual(report["topics_with_observed_responsibility_total"], 1)
        self.assertEqual(report["topics_with_execution_evidence_total"], 1)
        self.assertEqual(report["topics_with_observed_outcome_baseline_total"], 1)
        issue = report["issues"][0]
        self.assertEqual(
            issue["classification"],
            "responsibility_execution_and_baseline_reviewed_no_post_change_causality",
        )
        self.assertEqual(issue["primary_blocker"], "delivery_or_beneficiary_missing")
        self.assertIn("post_change_outcome_missing", issue["blockers"])
        self.assertIn("causal_link_missing", issue["blockers"])
        self.assertEqual(issue["next_action"]["action_id"], "find_delivery_or_beneficiary_evidence")
        self.assertEqual(report["delivery_evidence_hunts_total"], 1)
        self.assertEqual(report["delivery_evidence_search_targets_total"], 2)
        self.assertEqual(issue["delivery_evidence_hunts_total"], 1)
        self.assertEqual(issue["next_action"]["delivery_evidence_hunts_total"], 1)
        self.assertEqual(issue["delivery_evidence_hunts"][0]["search_targets"][0]["registry"], "junta_open_data")
        self.assertIn("51D", issue["delivery_evidence_hunts"][0]["search_targets"][0]["query"])
        self.assertEqual(issue["public_merit_blame_eligible"], False)

    def test_issue_readiness_moves_post_change_outcomes_to_causal_review(self) -> None:
        queue = {
            "queue": [
                {
                    "topic_id": "campo_agua",
                    "gap_id": "missing_budget_execution",
                    "source_candidate_ids": ["junta_presupuesto_2026_partidas_gastos"],
                    "reviewed_evidence_rows": [
                        {
                            "evidence_kind": "budget_plan",
                            "review_status": "reviewed_budget_plan_linked_execution_pending",
                            "reviewed_label": "Saneamiento y depuracion",
                        }
                    ],
                },
                {
                    "topic_id": "campo_agua",
                    "gap_id": "missing_outcomes",
                    "source_candidate_ids": ["ieca_ods_agua_631_111614"],
                    "reviewed_evidence_rows": [
                        {
                            "evidence_kind": "observed_outcome_series",
                            "review_status": "reviewed_observed_outcome_baseline_post_change_pending",
                            "outcome_post_change_status": "post_change_observed_needs_review",
                            "outcome_post_change_rows_total": 1,
                        }
                    ],
                },
            ]
        }

        report = build_issue_readiness_report(
            {
                "packets": [
                    {
                        "topic_id": "campo_agua",
                        "topic_label": "Campo y agua",
                        "program_measures_total": 2,
                        "reviewed_vote_items_total": 1,
                        "reviewed_boja_legal_changes_total": 1,
                        "observed_responsibility_claims_total": 4,
                        "issue_review_status": "reviewed_issue_direction_actor_execution_owner_and_budget_allocation_partial",
                        "open_gaps": ["missing_outcomes"],
                    }
                ]
            },
            queue,
        )

        issue = report["issues"][0]
        self.assertEqual(report["publishable_merit_blame_topics_total"], 0)
        self.assertEqual(report["topics_with_post_change_outcome_total"], 1)
        self.assertEqual(
            issue["classification"],
            "responsibility_execution_post_change_outcome_reviewed_causality_pending",
        )
        self.assertEqual(issue["primary_blocker"], "causal_link_missing")
        self.assertNotIn("post_change_outcome_missing", issue["blockers"])
        self.assertIn("merit_blame_review_missing", issue["blockers"])
        self.assertEqual(issue["next_action"]["action_id"], "review_causal_link")
        self.assertEqual(issue["public_merit_blame_eligible"], False)

    def test_execution_evidence_candidates_include_contract_json_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir)
            (raw_dir / "menores_2025_v1_20260122.json").write_text(
                """
                {
                  "Informe": [
                    {
                      "OBJETO_CONTRATO": "Servicio de depuracion y abastecimiento de agua en explotaciones agrarias",
                      "ORGANO_CONTRATACION": "Consejeria de Agricultura, Pesca, Agua y Desarrollo Rural",
                      "NUMERO_EXPEDIENTE": "CONTR-2025-AGUA-1",
                      "IMPORTE_ADJUDICACION_SIN_IVA": "12345,67",
                      "FECHA_FORMALIZACION": "12/03/2025",
                      "LUGAR_EJECUCION_DENOMINACION": "Almeria"
                    },
                    {
                      "OBJETO_CONTRATO": "Material informatico generico",
                      "ORGANO_CONTRATACION": "Consejeria de Presidencia",
                      "NUMERO_EXPEDIENTE": "CONTR-2025-GEN-1",
                      "IMPORTE_ADJUDICACION_SIN_IVA": "500"
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )
            (raw_dir / "menores_2024_v1_20250420.json").write_text(
                """
                {
                  "Informe": [
                    {
                      "OBJETO_CONTRATO": "Obra menor de saneamiento y depuracion de aguas residuales",
                      "ORGANO_CONTRATACION": "Agencia de Medio Ambiente y Agua de Andalucia",
                      "NUMERO_EXPEDIENTE": "CONTR-2024-AGUA-1",
                      "IMPORTE_ADJUDICACION_SIN_IVA": "9876,50",
                      "FECHA_FORMALIZACION": "20/11/2024",
                      "LUGAR_EJECUCION_DENOMINACION": "Malaga"
                    },
                    {
                      "OBJETO_CONTRATO": "Suministro general sin relacion",
                      "ORGANO_CONTRATACION": "Consejeria de Presidencia",
                      "NUMERO_EXPEDIENTE": "CONTR-2024-GEN-1",
                      "IMPORTE_ADJUDICACION_SIN_IVA": "100"
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )

            report = collect_execution_evidence_candidates(
                raw_dir=raw_dir,
                timeout=1,
                no_network=True,
                strict_network=False,
            )

        budget_group = report["groups_by_key"]["campo_agua:missing_budget_execution"]
        self.assertEqual(report["contract_candidate_rows_total"], 2)
        self.assertEqual(
            budget_group["candidate_rows_by_source"]["junta_contratos_menores_2025"],
            1,
        )
        self.assertEqual(
            budget_group["candidate_rows_by_source"]["junta_contratos_menores_2024"],
            1,
        )
        contract_row = next(
            row
            for row in budget_group["top_candidate_rows"]
            if row["source_id"] == "junta_contratos_menores_2025"
        )
        self.assertEqual(contract_row["contract_reference"], "CONTR-2025-AGUA-1")
        self.assertEqual(contract_row["amount_eur"], 12346)
        self.assertNotIn("NIF_ADJUDICATARIO", contract_row)
        contract_2024_row = next(
            row
            for row in budget_group["top_candidate_rows"]
            if row["source_id"] == "junta_contratos_menores_2024"
        )
        self.assertEqual(contract_2024_row["contract_reference"], "CONTR-2024-AGUA-1")
        self.assertEqual(contract_2024_row["amount_eur"], 9876)

    def test_ieca_ods_outcome_loader_handles_extra_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ieca_ods_educacion_abandono_115550.json"
            path.write_text(
                """
                {
                  "metainfo": {
                    "title": "Abandono temprano de la educación por sexo",
                    "activity": "Sistema de Indicadores de Desarrollo Sostenible de Andalucía para la Agenda 2030",
                    "periodicity": "Anual"
                  },
                  "hierarchies": [
                    {"des": "Sexo", "alias": "D_SEXO_0"},
                    {"des": "Territorio", "alias": "D_TERRITORIO_0"},
                    {"des": "Anual", "alias": "D_TEMPORAL_0"}
                  ],
                  "measures": [
                    {"des": "Serie"},
                    {"des": "Estado del dato"}
                  ],
                  "data": [
                    [{"des":"Ambos sexos"}, {"cod":["P2_04"], "des":"Almería"}, {"cod":["2022"], "des":"2022"}, {"val":"18.1", "format":"18,10"}, {"val":"", "format":""}],
                    [{"des":"Hombres"}, {"cod":["P2_C01"], "des":"Andalucía"}, {"cod":["2024"], "des":"2024"}, {"val":"17.9", "format":"17,90"}, {"val":"", "format":""}],
                    [{"des":"Ambos sexos"}, {"cod":["P2_C01"], "des":"Andalucía"}, {"cod":["2024"], "des":"2024"}, {"val":"15.3", "format":"15,30"}, {"val":"", "format":""}]
                  ]
                }
                """,
                encoding="utf-8",
            )

            header, rows = load_ieca_ods_outcome_series_rows("ieca_ods_educacion_abandono_115550", path)

        self.assertIn("outcome_dimension_context", header)
        self.assertEqual(rows[0]["territory_name"], "Andalucía")
        self.assertEqual(rows[0]["year"], "2024")
        self.assertEqual(rows[0]["outcome_value_format"], "15,30")
        self.assertEqual(rows[0]["outcome_dimension_context"], "Sexo: Ambos sexos")
        self.assertEqual(rows[0]["indicator_unit"], "Porcentaje")
        self.assertEqual(rows[0]["outcome_baseline_year"], "2024")
        self.assertEqual(rows[0]["outcome_latest_year"], "2024")
        self.assertEqual(rows[0]["outcome_post_change_status"], "waiting_for_post_change_period")
        self.assertEqual(rows[0]["outcome_next_post_change_check_year"], 2026)

    def test_ieca_ods_outcome_loader_handles_shifted_status_measure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ieca_ods_aire_pm10_85172.json"
            path.write_text(
                """
                {
                  "metainfo": {
                    "title": "Nivel medio de partículas PM10",
                    "activity": "Sistema de Indicadores de Desarrollo Sostenible de Andalucía para la Agenda 2030",
                    "periodicity": "Anual"
                  },
                  "hierarchies": [
                    {"des": "Territorio", "alias": "D_TERRITORIO_0"},
                    {"des": "Anual", "alias": "D_TEMPORAL_0"}
                  ],
                  "measures": [
                    {"des": "Estado del dato"},
                    {"des": "Nivel medio PM10"}
                  ],
                  "data": [
                    [{"cod":["P2_C01"], "des":"Andalucía"}, {"cod":["2024"], "des":"2024"}, {"val":"", "format":""}, {"val":"29.2", "format":"29,20"}]
                  ]
                }
                """,
                encoding="utf-8",
            )

            _header, rows = load_ieca_ods_outcome_series_rows("ieca_ods_aire_pm10_85172", path)

        self.assertEqual(rows[0]["outcome_value"], "29.2")
        self.assertEqual(rows[0]["outcome_value_format"], "29,20")
        self.assertEqual(rows[0]["indicator_unit"], "Microgramos por metro cubico")

    def test_post_change_outcome_monitor_flags_waiting_and_ready_series(self) -> None:
        rows = [
            {
                "indicator_title": "Indicador de agua",
                "indicator_periodicity": "Anual",
                "indicator_unit": "Porcentaje",
                "territory_name": "Andalucía",
                "year": "2025",
                "outcome_value": "77.1",
                "outcome_value_format": "77,10",
                "outcome_dimension_context": "",
            },
            {
                "indicator_title": "Indicador de agua",
                "indicator_periodicity": "Anual",
                "indicator_unit": "Porcentaje",
                "territory_name": "Andalucía",
                "year": "2026",
                "outcome_value": "78.2",
                "outcome_value_format": "78,20",
                "outcome_dimension_context": "",
            },
        ]

        monitor = build_post_change_outcome_monitor({"ieca_ods_agua_631_111614": rows})

        water = next(row for row in monitor["series"] if row["source_id"] == "ieca_ods_agua_631_111614")
        self.assertEqual(monitor["post_change_candidate_series_total"], 1)
        self.assertEqual(water["post_change_status"], "post_change_observed_needs_review")
        self.assertEqual(water["baseline_year"], "2025")
        self.assertEqual(water["latest_year"], "2026")
        self.assertEqual(water["post_change_rows_total"], 1)
        self.assertEqual(water["claim_status"], "official_outcome_monitor_no_merit_or_blame")

    def test_execution_evidence_candidates_include_ieca_ods_outcome_series_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir)
            (raw_dir / "ieca_ods_agua_631_111614.json").write_text(
                """
                {
                  "metainfo": {
                    "id": 111614,
                    "title": "Proporción de la carga contaminante correspondiente a las aglomeraciones urbanas de más de 2.000 habitantes equivalentes que depuran adecuadamente sus aguas residuales",
                    "activity": "Sistema de Indicadores de Desarrollo Sostenible de Andalucía para la Agenda 2030",
                    "periodicity": "Bienal"
                  },
                  "data": [
                    [{"cod":["P2_C01"], "des":"Andalucía"}, {"cod":["2012"], "des":"2012"}, {"val":"72.145156238", "format":"72,15"}, {"val":"", "format":""}],
                    [{"cod":["P2_C01"], "des":"Andalucía"}, {"cod":["2022"], "des":"2022"}, {"val":"77.809499219", "format":"77,81"}, {"val":"", "format":""}],
                    [{"cod":["P3_108"], "des":"España"}, {"cod":["2022"], "des":"2022"}, {"val":"90.550750589", "format":"90,55"}, {"val":"", "format":""}]
                  ]
                }
                """,
                encoding="utf-8",
            )

            report = collect_execution_evidence_candidates(
                raw_dir=raw_dir,
                timeout=1,
                no_network=True,
                strict_network=False,
            )

        outcome_group = report["groups_by_key"]["campo_agua:missing_outcomes"]
        self.assertEqual(report["outcome_candidate_rows_total"], 3)
        self.assertEqual(
            outcome_group["candidate_rows_by_source"]["ieca_ods_agua_631_111614"],
            3,
        )
        outcome_row = next(
            row
            for row in outcome_group["top_candidate_rows"]
            if row["source_id"] == "ieca_ods_agua_631_111614"
        )
        self.assertEqual(outcome_row["outcome_territory"], "Andalucía")
        self.assertEqual(outcome_row["outcome_year"], "2022")
        self.assertEqual(outcome_row["outcome_value_format"], "77,81")
        self.assertEqual(outcome_row["indicator_unit"], "Porcentaje")
        self.assertEqual(outcome_row["outcome_baseline_year"], "2022")
        self.assertEqual(outcome_row["outcome_latest_year"], "2022")
        self.assertEqual(outcome_row["outcome_post_change_status"], "waiting_for_post_change_period")
        self.assertEqual(report["outcome_series_monitor"]["series_total"], 5)
        self.assertEqual(report["outcome_series_monitor"]["waiting_series_total"], 1)
        self.assertEqual(report["outcome_series_monitor"]["missing_series_total"], 4)

    def test_execution_evidence_refreshes_cached_outcome_series_only_when_requested(self) -> None:
        stale_payload = b"""
        {
          "metainfo": {
            "id": 111614,
            "title": "Indicador de agua",
            "activity": "ODS",
            "periodicity": "Anual"
          },
          "data": [
            [{"cod":["P2_C01"], "des":"Andalucia"}, {"cod":["2025"], "des":"2025"}, {"val":"77.1", "format":"77,10"}, {"val":"", "format":""}]
          ]
        }
        """
        fresh_payload = b"""
        {
          "metainfo": {
            "id": 111614,
            "title": "Indicador de agua",
            "activity": "ODS",
            "periodicity": "Anual"
          },
          "data": [
            [{"cod":["P2_C01"], "des":"Andalucia"}, {"cod":["2025"], "des":"2025"}, {"val":"77.1", "format":"77,10"}, {"val":"", "format":""}],
            [{"cod":["P2_C01"], "des":"Andalucia"}, {"cod":["2026"], "des":"2026"}, {"val":"78.2", "format":"78,20"}, {"val":"", "format":""}]
          ]
        }
        """

        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir)
            outcome_path = raw_dir / "ieca_ods_agua_631_111614.json"
            outcome_path.write_bytes(stale_payload)
            original_files = snapshot_module.EXECUTION_EVIDENCE_RAW_FILES
            original_fetch = snapshot_module.http_get_bytes
            try:
                snapshot_module.EXECUTION_EVIDENCE_RAW_FILES = {
                    "ieca_ods_agua_631_111614": "ieca_ods_agua_631_111614.json"
                }

                def fake_fetch(_url: str, *, timeout: int, max_attempts: int) -> tuple[bytes, str]:
                    return fresh_payload, "application/json"

                snapshot_module.http_get_bytes = fake_fetch
                report = snapshot_module.collect_execution_evidence_candidates(
                    raw_dir=raw_dir,
                    timeout=1,
                    no_network=False,
                    strict_network=True,
                    refresh_outcome_series=True,
                )
            finally:
                snapshot_module.EXECUTION_EVIDENCE_RAW_FILES = original_files
                snapshot_module.http_get_bytes = original_fetch

        water = next(
            row
            for row in report["outcome_series_monitor"]["series"]
            if row["source_id"] == "ieca_ods_agua_631_111614"
        )
        self.assertEqual(report["source_files_refreshed_total"], 1)
        self.assertEqual(report["source_files"][0]["status"], "raw_file_refreshed")
        self.assertEqual(water["post_change_status"], "post_change_observed_needs_review")
        self.assertEqual(water["post_change_rows_total"], 1)
        self.assertEqual(water["latest_year"], "2026")

    def test_public_grant_beneficiary_retains_official_physical_person_identity(self) -> None:
        capture_path = Path(
            "etl/data/raw/elections/andalucia_2026/execution_evidence/"
            "junta_subvenciones_programas_prioritarios.json"
        )
        payload = json.loads(capture_path.read_text(encoding="utf-8"))
        person_row = next(
            row
            for row in payload["results"]
            if str(row.get("physical_person") or "").strip()
        )

        self.assertEqual(
            public_grant_beneficiary(person_row),
            str(person_row["beneficiary"]).strip(),
        )
        self.assertNotIn("omitido", public_grant_beneficiary(person_row).lower())
        self.assertTrue(str(person_row.get("nif_cif_public") or "").strip())

    def test_parliament_vote_text_extracts_party_tallies_without_claims(self) -> None:
        document = {
            "document_id": "test-vote-document",
            "source_url": "https://www.parlamentodeandalucia.es/test.pdf",
        }
        events = parse_parliament_vote_events_text(document, VOTING_FIXTURE_TEXT)

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["numexp"], "12-25/PL-000011")
        self.assertEqual(event["total_si"], 36)
        self.assertEqual(event["total_no"], 72)
        self.assertEqual(event["majority_side"], "no")
        self.assertEqual(event["claim_status"], "official_vote_count_not_interpreted")
        self.assertEqual(event["interpretation_status"], "needs_vote_context_and_outcome_review")
        self.assertGreaterEqual(len(event["review_questions"]), 4)
        self.assertEqual(event["member_votes_total"], 6)
        moreno = next(row for row in event["member_votes"] if row["member_name"] == "Moreno Bonilla, Juan Manuel")
        self.assertEqual(moreno["member_name_match_key"], "juan manuel moreno bonilla")
        self.assertEqual(moreno["vote_position"], "no")
        delegated = next(row for row in event["member_votes"] if row["member_name"] == "Castaño Diéguez, Adela")
        self.assertTrue(delegated["delegated_vote"])
        pp_tally = next(row for row in event["party_vote_totals"] if row["party_key"] == "pp")
        psoe_tally = next(row for row in event["party_vote_totals"] if row["party_key"] == "psoe-a")
        self.assertEqual(pp_tally["no"], 58)
        self.assertEqual(pp_tally["dominant_position"], "no")
        self.assertEqual(psoe_tally["si"], 29)
        self.assertEqual(psoe_tally["dominant_position"], "si")

    def test_parliament_vote_event_parser_extracts_party_totals(self) -> None:
        document = {
            "document_id": "doc-1",
            "source_url": "https://www.parlamentodeandalucia.es/webdinamica/portal-web-parlamento/pdf.do?id=1",
        }
        text = """
PARLAMENTO DE ANDALUCÍA - XII LEGISLATURA

 TÍTULO GENERAL DEL DEBATE

            12-25/PL-000005, DEBATE FINAL DEL PROYECTO DE LEY DE VIVIENDA DE ANDALUCÍA

                                02/12/2025 14:03:00

                                             VOTACIÓN Nº          3
                                             PROTOCOLO           20
                                             SESIÓN              74

                        TOTAL           PP       PS         VO         PA    AA _

PRESENTES                109           058     030         014        005   002

TOTAL SI                 061           052     000         009        000   000

TOTAL NO                 028           000     026         000        000   002

TOTAL ABSTENCIONES       001           000     001         000        000   000

TOTAL BLANCOS            003           003     000         000        000   000

DIPUTADOS AUSENTES       016           003     003         005        005   000
TOTAL DIPUTADOS          109           058     030         014        005   002
"""
        events = parse_parliament_vote_events_text(document, text)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["numexp"], "12-25/PL-000005")
        self.assertEqual(event["total_si"], 61)
        self.assertEqual(event["total_no"], 28)
        self.assertEqual(event["majority_side"], "si")
        pp = next(row for row in event["party_vote_totals"] if row["party_key"] == "pp")
        psoe = next(row for row in event["party_vote_totals"] if row["party_key"] == "psoe-a")
        self.assertEqual(pp["si"], 52)
        self.assertEqual(pp["blancos"], 3)
        self.assertEqual(psoe["no"], 26)
        self.assertEqual(event["claim_status"], "official_vote_count_not_interpreted")


if __name__ == "__main__":
    unittest.main()
