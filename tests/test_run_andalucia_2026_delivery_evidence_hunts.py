from __future__ import annotations

import unittest

from scripts.run_andalucia_2026_delivery_evidence_hunts import (
    build_hunt_report,
    collect_search_targets,
    parse_boja_results,
    run_bdns_target,
    run_boja_target,
    run_junta_open_data_target,
    run_junta_procurement_registry_target,
)


SNAPSHOT = {
    "accountability_readiness": {
        "issues": [
            {
                "topic_id": "campo_agua",
                "topic_label": "Campo y agua",
                "delivery_evidence_hunts": [
                    {
                        "hunt_id": "hunt-agua-1",
                        "evidence_kind": "grant_award",
                        "reviewed_label": "Digitalización usos agua",
                        "source_id": "junta_subvenciones_programas_prioritarios",
                        "search_targets": [
                            {
                                "target_id": "target-open-data",
                                "registry": "junta_open_data",
                                "target_kind": "grant_open_data_detail",
                                "query": "Digitalización usos agua subvencion beneficiario",
                                "url": "https://www.juntadeandalucia.es/datosabiertos/portal/dataset/?q=agua",
                            },
                            {
                                "target_id": "target-bdns",
                                "registry": "bdns",
                                "target_kind": "grant_bdns_detail",
                                "query": "Digitalización usos agua",
                                "url": "https://www.infosubvenciones.es/bdnstrans/GE/es/convocatorias",
                            },
                        ],
                    }
                ],
            }
        ]
    }
}


class TestRunAndalucia2026DeliveryEvidenceHunts(unittest.TestCase):
    def test_collect_search_targets_flattens_hunt_context(self) -> None:
        targets = collect_search_targets(SNAPSHOT, max_targets=10)

        self.assertEqual(len(targets), 2)
        self.assertEqual(targets[0]["topic_id"], "campo_agua")
        self.assertEqual(targets[0]["topic_label"], "Campo y agua")
        self.assertEqual(targets[0]["hunt_id"], "hunt-agua-1")
        self.assertEqual(targets[0]["evidence_kind"], "grant_award")
        self.assertIn("target_run_id", targets[0])

    def test_junta_open_data_target_compacts_machine_readable_candidates(self) -> None:
        def fake_ckan_search(query: str, *, rows: int, timeout: int):
            self.assertIn("agua", query)
            self.assertEqual(rows, 2)
            self.assertEqual(timeout, 7)
            return [
                {
                    "name": "subvenciones-agua",
                    "title": "Subvenciones de agua",
                    "notes": "Ayudas y beneficiarios.",
                    "resources": [
                        {
                            "name": "CSV",
                            "format": "CSV",
                            "url": "https://example.test/subvenciones.csv",
                        }
                    ],
                }
            ]

        result = run_junta_open_data_target(
            {"query": "agua beneficiario"},
            rows_per_query=2,
            timeout=7,
            ckan_search=fake_ckan_search,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["result_candidates_total"], 1)
        self.assertEqual(result["result_candidates_machine_readable_total"], 1)
        self.assertEqual(result["result_candidates"][0]["url"].endswith("/subvenciones-agua"), True)

    def test_parse_boja_results_extracts_official_links(self) -> None:
        body = """
        <p><strong>143</strong> recursos disponibles.</p>
        <ul class="listado_resultados list-unstyled">
          <li><div><p><a href="/boja/2024/20/3">Orden de digitalización del control de usos del agua urbana</a></p></div></li>
        </ul>
        """

        total, candidates = parse_boja_results(
            body,
            base_url="https://www.juntadeandalucia.es/eboja/buscador/search.do?q=agua",
            limit=2,
        )

        self.assertEqual(total, 143)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["registry"], "boja")
        self.assertEqual(candidates[0]["url"], "https://www.juntadeandalucia.es/boja/2024/20/3")

    def test_boja_target_reports_no_results(self) -> None:
        def fake_text_fetch(url: str, *, timeout: int):
            self.assertIn("/eboja/buscador/search.do?", url)
            self.assertEqual(timeout, 9)
            return (
                "<p><strong>No se han encontrado resultados coincidentes con los criterios de búsqueda introducidos.</strong></p>",
                200,
                "text/html;charset=UTF-8",
                url,
            )

        result = run_boja_target({"query": "CONTR 2024 1"}, rows_per_query=3, timeout=9, text_fetch=fake_text_fetch)

        self.assertEqual(result["status"], "no_results")
        self.assertEqual(result["http_status"], 200)
        self.assertEqual(result["result_candidates_total"], 0)

    def test_boja_target_falls_back_to_reviewed_label_query(self) -> None:
        calls: list[str] = []

        def fake_text_fetch(url: str, *, timeout: int):
            calls.append(url)
            if "q=Digitalizaci" in url:
                return (
                    """
                    <p><strong>143</strong> recursos disponibles.</p>
                    <ul class="listado_resultados list-unstyled">
                      <li><a href="/boja/2024/20/3">Orden de digitalización del control de usos del agua urbana</a></li>
                    </ul>
                    """,
                    200,
                    "text/html;charset=UTF-8",
                    url,
                )
            return (
                "<p><strong>No se han encontrado resultados coincidentes con los criterios de búsqueda introducidos.</strong></p>",
                200,
                "text/html;charset=UTF-8",
                url,
            )

        result = run_boja_target(
            {
                "query": "EMPRESA METROPOLITANA justificacion subvencion",
                "reviewed_label": "Digitalización usos agua",
            },
            rows_per_query=3,
            timeout=9,
            text_fetch=fake_text_fetch,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["query_variant"], "reviewed_label")
        self.assertEqual(result["query_attempts_total"], 2)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["result_candidates_total"], 1)

    def test_bdns_target_uses_official_json_api_for_concessions(self) -> None:
        calls: list[str] = []

        def fake_json_fetch(url: str, *, timeout: int, payload=None):
            calls.append(url)
            self.assertEqual(timeout, 8)
            self.assertIsNone(payload)
            if "/terceros?" in url:
                return (
                    {"terceros": [{"id": 5948839, "descripcion": "P1100000G - DIPUTACION DE CADIZ"}]},
                    200,
                    "application/json",
                    url,
                )
            if "/concesiones/busqueda?" in url and "beneficiario=5948839" in url:
                return (
                    {
                        "content": [
                            {
                                "id": 141021614,
                                "codConcesion": "SB141021614",
                                "fechaConcesion": "2025-12-30",
                                "beneficiario": "P1100000G DIPUTACION DE CADIZ",
                                "importe": 3000000,
                                "ayudaEquivalente": 3000000,
                                "urlBR": "https://juntadeandalucia.es/boja/2024/251/2",
                                "numeroConvocatoria": "881761",
                                "idConvocatoria": 1083322,
                                "convocatoria": "SUBV EXCEPCIONAL A LA DIPUTACION DE CADIZ RESTAURACIÓN EDIFICIO VALCARCEL",
                                "nivel3": "CONSEJERÍA DE CULTURA Y DEPORTE",
                            }
                        ],
                        "totalElements": 1,
                    },
                    200,
                    "application/json",
                    url,
                )
            return ({"content": [], "totalElements": 0}, 200, "application/json", url)

        result = run_bdns_target(
            {
                "query": "DIPUTACION DE CADIZ SUBV EXCEPCIONAL A LA DIPUTACION DE CADIZ RESTAURACIÓN EDIFICIO VALCARCEL FOM. Y PROM. GESTION CULTURAL",
                "grant_beneficiary": "DIPUTACION DE CADIZ",
                "reviewed_label": "FOM. Y PROM. GESTION CULTURAL",
            },
            rows_per_query=2,
            timeout=8,
            json_fetch=fake_json_fetch,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["beneficiary_ids"][0]["id"], "5948839")
        self.assertEqual(result["result_candidates_machine_readable_total"], 1)
        self.assertEqual(result["result_candidates"][0]["cod_concesion"], "SB141021614")
        self.assertEqual(result["result_candidates"][0]["importe"], 3000000)
        self.assertGreaterEqual(len(calls), 2)

    def test_junta_procurement_registry_target_uses_public_elastic_endpoint(self) -> None:
        seen_payloads = []

        def fake_json_fetch(url: str, *, timeout: int, payload=None):
            self.assertIn("/elastic/sirec_pdc_expedientes/_search", url)
            self.assertEqual(timeout, 8)
            seen_payloads.append(payload)
            query = payload["query"]["bool"]["must"][1]["query_string"]["query"]
            if query == "*0001008630*":
                return (
                    {
                        "hits": {
                            "total": {"value": 1, "relation": "eq"},
                            "hits": [
                                {
                                    "_id": "740593",
                                    "_source": {
                                        "idExpediente": 740593,
                                        "numeroExpediente": "CONTR 2024 0001008630",
                                        "titulo": "Organización y descripción del archivo de oficina del SV PPH",
                                        "tipoContrato": {"descripcion": "Servicios"},
                                        "perfilContratante": {"descripcion": "Dirección General de Patrimonio Histórico"},
                                        "estado": {"nombre": "Resuelto"},
                                        "importeLicitacion": 14876,
                                        "valorEstimado": 14876,
                                        "fechaPublicacion": "2024-11-22T13:31:37+0100",
                                        "adjudicaciones": [
                                            {
                                                "nombreAdjudicatario": "MARIA PILAR LOPEZ AGUDO;",
                                                "nifAdjudicatario": "75537231X;",
                                                "importeAdjudicacion": 14760,
                                                "fechaFormalizacion": "2024-11-15T00:00:00+0100",
                                                "fechaResolucion": "2024-11-15T00:00:00+0100",
                                                "codigoResultado": "AWARD",
                                            }
                                        ],
                                    },
                                }
                            ],
                        }
                    },
                    200,
                    "application/json",
                    url,
                )
            return ({"hits": {"total": {"value": 0}, "hits": []}}, 200, "application/json", url)

        result = run_junta_procurement_registry_target(
            {
                "query": "CONTR 2024 0001008630",
                "contract_reference": "CONTR 2024 0001008630",
                "reviewed_label": "Contrato menor de organización del archivo de Protección del Patrimonio Histórico",
            },
            rows_per_query=3,
            timeout=8,
            json_fetch=fake_json_fetch,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["query_variant"], "contract_numeric_reference")
        self.assertEqual(result["result_candidates_machine_readable_total"], 1)
        self.assertEqual(result["result_candidates"][0]["numero_expediente"], "CONTR 2024 0001008630")
        self.assertEqual(result["result_candidates"][0]["adjudicaciones"][0]["nombre_adjudicatario"], "MARIA PILAR LOPEZ AGUDO")
        self.assertEqual(seen_payloads[0]["query"]["bool"]["must"][0]["match"]["codigoProcedimiento"], "9")

    def test_report_keeps_manual_registries_separate_from_executed_targets(self) -> None:
        def fake_runner(target):
            if target["registry"] == "junta_open_data":
                return {
                    "status": "ok",
                    "result_candidates_total": 1,
                    "result_candidates_machine_readable_total": 1,
                    "result_candidates": [{"candidate_id": "candidate-1", "machine_readable": True}],
                }
            return {
                "status": "manual_search_landing_ready",
                "manual_reason": "manual",
                "result_candidates_total": 0,
                "result_candidates_machine_readable_total": 0,
                "result_candidates": [],
            }

        report = build_hunt_report(
            SNAPSHOT,
            source_snapshot_path="etl/data/published/andalucia-2026-accountability.json",
            runner=fake_runner,
        )

        self.assertEqual(report["summary"]["targets_total"], 2)
        self.assertEqual(report["summary"]["targets_executed_total"], 1)
        self.assertEqual(report["summary"]["targets_manual_total"], 1)
        self.assertEqual(report["summary"]["result_candidates_total"], 1)
        self.assertEqual(report["summary"]["topics_with_result_candidates_total"], 1)


if __name__ == "__main__":
    unittest.main()
