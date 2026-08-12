from __future__ import annotations

import unittest

from scripts.discover_andalucia_2026_execution_sources import (
    alternate_resource_urls,
    build_candidate,
    equivalent_resource_urls,
    existing_source_indexes,
    resource_is_machine_readable,
    score_package_for_gap,
)


TREASURY_PACKAGE = {
    "name": "movimientos-de-la-tesoreria-general-de-la-junta-de-andalucia-2025",
    "title": "Movimientos de la Tesorería General de la Junta de Andalucía 2025",
    "notes": "Cobros, saldos y pagos de la Tesorería General.",
    "resources": [
        {
            "name": "CSV - Movimientos de la Tesorería General de la Junta de Andalucía 2025",
            "format": "CSV",
            "url": "https://example.test/transparencia-presidencia-2025t4.7z",
        }
    ],
}


class TestDiscoverAndalucia2026ExecutionSources(unittest.TestCase):
    def test_treasury_dataset_scores_as_gap_source_for_budget_execution(self) -> None:
        profile = {
            "topic_id": "campo_agua",
            "gap_id": "missing_budget_execution",
            "search_terms": ["agua", "canon"],
        }

        score = score_package_for_gap(TREASURY_PACKAGE, profile)

        self.assertGreaterEqual(score["score"], 10)
        self.assertEqual(score["match_status"], "gap_source_candidate_needs_row_filter")
        self.assertIn("pagos", score["matched_gap_terms"])
        self.assertEqual(score["machine_resources_total"], 1)

    def test_resource_detection_treats_7z_csv_dump_as_machine_readable(self) -> None:
        resource = {
            "format": "CSV",
            "url": "https://example.test/transparencia-presidencia-2025t4.7z",
        }

        self.assertTrue(resource_is_machine_readable(resource))

    def test_alternate_resource_url_maps_ckan_storage_to_main_junta_host(self) -> None:
        url = (
            "https://gdc-pdpopendata-ckan.paas.junta-andalucia.es/datosabiertos/portal/"
            "dataset/abc/resource/def/download/file.7z"
        )

        self.assertEqual(
            alternate_resource_urls(url),
            ["https://www.juntadeandalucia.es/datosabiertos/portal/dataset/abc/resource/def/download/file.7z"],
        )

    def test_equivalent_resource_urls_treat_main_and_storage_hosts_as_same_resource(self) -> None:
        main_url = (
            "https://www.juntadeandalucia.es/datosabiertos/portal/"
            "dataset/abc/resource/def/download/file.json"
        )
        storage_url = (
            "https://gdc-pdpopendata-ckan.paas.junta-andalucia.es/datosabiertos/portal/"
            "dataset/abc/resource/def/download/file.json"
        )

        self.assertEqual(equivalent_resource_urls(main_url), [storage_url, main_url])
        self.assertEqual(equivalent_resource_urls(storage_url), [storage_url, main_url])

    def test_existing_integrated_sources_are_detected_by_landing_or_resource_url(self) -> None:
        existing_by_landing, existing_by_resource = existing_source_indexes()
        package = {
            "name": "subvenciones-otorgadas-por-la-junta-de-andalucia",
            "title": "Subvenciones otorgadas por la Junta de Andalucía",
            "resources": [
                {
                    "name": "API",
                    "format": "JSON",
                    "url": "https://www.juntadeandalucia.es/datosabiertos/portal/dataset/subvenciones-otorgadas-por-la-junta-de-andalucia",
                }
            ],
        }
        profile = {
            "topic_id": "educacion",
            "gap_id": "missing_budget_execution",
            "search_terms": ["universidad"],
        }

        candidate = build_candidate(
            package,
            profile,
            query_ids=["grants"],
            skip_resource_probe=True,
            existing_by_landing=existing_by_landing,
            existing_by_resource=existing_by_resource,
        )

        self.assertTrue(candidate["already_integrated"])
        self.assertIn("junta_subvenciones_programas_prioritarios", candidate["existing_source_ids"])
        self.assertEqual(candidate["next_action"], "already_integrated_keep_refreshing")

    def test_integrated_contract_dump_is_detected_through_storage_host_equivalent(self) -> None:
        existing_by_landing, existing_by_resource = existing_source_indexes()
        package = {
            "name": "contratacion-menor-plataforma-de-contratacion-andalucia-2025",
            "title": "Contratación Menor en 2025 publicada en la Plataforma de Contratación de la Junta de Andalucía",
            "resources": [
                {
                    "name": "JSON - Contratación Menor en 2025",
                    "format": "JSON",
                    "url": (
                        "https://gdc-pdpopendata-ckan.paas.junta-andalucia.es/datosabiertos/portal/"
                        "dataset/00510697-b39d-4e19-b142-14565baafabd/resource/"
                        "33d80321-3ffc-4b3c-8b27-5e073bab8419/download/menores_2025_v1_20260122.json"
                    ),
                }
            ],
        }
        profile = {
            "topic_id": "campo_agua",
            "gap_id": "missing_budget_execution",
            "search_terms": ["agua"],
        }

        candidate = build_candidate(
            package,
            profile,
            query_ids=["contracts_minor_2025"],
            skip_resource_probe=True,
            existing_by_landing=existing_by_landing,
            existing_by_resource=existing_by_resource,
        )

        self.assertTrue(candidate["already_integrated"])
        self.assertIn("junta_contratos_menores_2025", candidate["existing_source_ids"])
        self.assertEqual(candidate["next_action"], "already_integrated_keep_refreshing")


if __name__ == "__main__":
    unittest.main()
