from __future__ import annotations

import unittest

from scripts.scrape_liberty_delegated_alternative_boe_candidates import build_alternative_boe_candidates


SAMPLE_QUERY_HTML = """
<ul>
  <li class="resultado-busqueda">
    <p class="linea-dem">Ministerio del Interior</p>
    <p class="linea-pub">BOE 301 de 17/12/2003 - II. Autoridades y personal</p>
    <p>Orden INT/3514/2003, de 5 de diciembre, por la que se dispone el nombramiento de don Mariano Fernández Fernández como Subdirector General de Normativa y Recursos de la Dirección General de Tráfico.</p>
    <a href="../buscar/doc.php?id=BOE-A-2003-23115" class="resultado-busqueda-link-defecto">Más...</a>
  </li>
  <li class="resultado-busqueda">
    <p class="linea-dem">Ministerio del Interior</p>
    <p class="linea-pub">BOE 39 de 15/02/1997 - II. Autoridades y personal</p>
    <p>Orden de 24 de enero de 1997 por la que se dispone el nombramiento de don Ventura Hernando Barberán como Subdirector general de Legislación y Recursos de la Dirección General de Tráfico.</p>
    <a href="../buscar/doc.php?id=BOE-A-1997-2771" class="resultado-busqueda-link-defecto">Más...</a>
  </li>
</ul>
"""


SAMPLE_DOC_HTML = """
<html>
  <head>
    <title>Orden INT/3514/2003 por la que se dispone el nombramiento de don Mariano Fernández Fernández como Subdirector General</title>
  </head>
  <body>...</body>
</html>
"""


class TestScrapeLibertyDelegatedAlternativeBoeCandidates(unittest.TestCase):
    def test_build_candidates_from_redirector_and_direct_doc(self) -> None:
        targets = [
            {
                "link_key": "k-dgt",
                "fragment_id": "frag-1",
                "norm_id": "norm-1",
                "boe_id_context": "BOE-A-1994-8985",
                "delegated_institution_label": "DGT",
                "designated_role_title": "Subdireccion de Gestion de Sanciones",
                "target_group": "boe_redirector_query",
                "target_label": "boe_redirector_primary",
                "target_url": "https://www.boe.es/buscar/redirector.php?q=1",
                "query": "nombramiento Subdireccion de Gestion de Sanciones DGT",
            },
            {
                "link_key": "k-dgt",
                "fragment_id": "frag-1",
                "norm_id": "norm-1",
                "boe_id_context": "BOE-A-1994-8985",
                "delegated_institution_label": "DGT",
                "designated_role_title": "Subdireccion de Gestion de Sanciones",
                "target_group": "boe_direct_doc",
                "target_label": "boe_direct_doc_BOE-A-2003-23115",
                "target_url": "https://www.boe.es/buscar/doc.php?id=BOE-A-2003-23115",
                "query": "BOE-A-2003-23115",
                "candidate_boe_id": "BOE-A-2003-23115",
                "candidate_score": "60",
                "candidate_rank_for_link": "1",
                "candidate_publication_date_iso": "2003-12-17",
            },
        ]

        def fake_fetch(url: str, timeout: int, user_agent: str) -> tuple[int, str, str]:
            if "redirector.php" in url:
                return 200, url, SAMPLE_QUERY_HTML
            return 200, url, SAMPLE_DOC_HTML

        def fake_query_fetch(query: str, timeout: int, user_agent: str) -> tuple[str, str]:
            return SAMPLE_QUERY_HTML, f"https://www.boe.es/buscar/redirector.php?q={query}"

        rows, summary = build_alternative_boe_candidates(
            target_rows=targets,
            top_results_per_query_target=5,
            max_queries_per_query_target=4,
            timeout=10,
            user_agent="ua",
            fetcher=fake_fetch,
            query_fetcher=fake_query_fetch,
        )

        self.assertEqual(int(summary["targets_total"]), 2)
        self.assertEqual(int(summary["links_total"]), 1)
        self.assertEqual(int(summary["links_with_candidates_total"]), 1)
        self.assertEqual(int(summary["candidate_rows_total"]), 2)
        self.assertEqual(int(summary["candidate_unique_boe_ids_total"]), 2)
        self.assertEqual(int(summary["direct_doc_candidates_total"]), 1)
        self.assertEqual(int(summary["query_candidates_total"]), 1)
        self.assertEqual(int(summary["fetch_ok_total"]), 2)
        self.assertEqual(int(summary["fetch_error_total"]), 0)
        self.assertIn("200", summary["fetch_status_counts"])

        by_id = {str(row["candidate_boe_id"]): row for row in rows}
        self.assertIn("BOE-A-2003-23115", by_id)
        self.assertIn("BOE-A-1997-2771", by_id)
        self.assertEqual(int(by_id["BOE-A-2003-23115"]["candidate_score"]), 60)
        self.assertEqual(str(by_id["BOE-A-2003-23115"]["candidate_publication_date"]), "17/12/2003")
        self.assertTrue(str(by_id["BOE-A-2003-23115"]["candidate_person_hint"]).startswith("Mariano Fernández"))

    def test_build_candidates_handles_fetch_errors(self) -> None:
        targets = [
            {
                "link_key": "k-aeat",
                "delegated_institution_label": "AEAT",
                "designated_role_title": "Unidad procedimental sancionadora",
                "target_group": "boe_direct_doc",
                "target_label": "boe_direct_doc_BOE-A-2024-12397",
                "target_url": "https://www.boe.es/buscar/doc.php?id=BOE-A-2024-12397",
                "query": "BOE-A-2024-12397",
                "candidate_boe_id": "BOE-A-2024-12397",
            }
        ]

        def fake_fetch(url: str, timeout: int, user_agent: str) -> tuple[int, str, str]:
            return 403, url, ""

        def fake_query_fetch(query: str, timeout: int, user_agent: str) -> tuple[str, str]:
            raise RuntimeError("query_fetch_failed")

        rows, summary = build_alternative_boe_candidates(
            target_rows=targets,
            top_results_per_query_target=3,
            max_queries_per_query_target=4,
            timeout=10,
            user_agent="ua",
            fetcher=fake_fetch,
            query_fetcher=fake_query_fetch,
        )

        self.assertEqual(rows, [])
        self.assertEqual(int(summary["fetch_error_total"]), 1)
        self.assertEqual(int(summary["links_without_candidates_total"]), 1)
        self.assertEqual(int(summary["candidate_rows_total"]), 0)


if __name__ == "__main__":
    unittest.main()
