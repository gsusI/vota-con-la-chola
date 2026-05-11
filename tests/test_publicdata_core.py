from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from etl.parlamentario_es.types import Extracted as ParliamentaryExtracted
from etl.politicos_es.types import Extracted as PoliticosExtracted
from publicdata_core.fetch import fetch_payload
from publicdata_core.http import payload_looks_like_html, validate_network_payload
from publicdata_core.parsers import parse_csv_source, parse_json_source, xlsx_col_to_index
from publicdata_core.raw import fallback_payload_from_sample
from publicdata_core.sources import SourceDefinition, source_config_mapping, source_definitions_from_config
from publicdata_core.types import Extracted
from publicdata_core.util import normalize_key_part, sha256_bytes, stable_json
from publicdata_core.workflows import CanonicalStep, RuntimeShape, WorkflowPlan, default_publicdata_workflows
from publicdata_connectors_es.infoelectoral import SOURCE_CONFIG as INFOELECTORAL_SOURCE_CONFIG
from publicdata_connectors_es.infoelectoral import SOURCE_DEFINITIONS as INFOELECTORAL_SOURCE_DEFINITIONS


class TestPublicDataCore(unittest.TestCase):
    def test_legacy_etl_types_reexport_core_extracted_contract(self) -> None:
        self.assertIs(PoliticosExtracted, Extracted)
        self.assertIs(ParliamentaryExtracted, Extracted)

    def test_payload_html_guard_detects_html(self) -> None:
        self.assertTrue(payload_looks_like_html(b"  <html><head>x</head></html>"))
        with self.assertRaisesRegex(RuntimeError, "Respuesta HTML inesperada"):
            validate_network_payload("source_test", b"{\"ok\": true}", "text/html")

    def test_raw_fallback_uses_source_config_and_writes_provenance_payload(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sample = root / "sample.json"
            payload = b'{"ok": true}'
            sample.write_bytes(payload)
            cfg = {
                "source_test": {
                    "format": "json",
                    "fallback_file": str(sample),
                }
            }

            result = fallback_payload_from_sample(cfg, "source_test", root / "raw", "fallback")

            self.assertEqual(result["payload"], payload)
            self.assertEqual(result["content_sha256"], sha256_bytes(payload))
            self.assertTrue(Path(result["raw_path"]).exists())
            self.assertEqual(Path(result["raw_path"]).read_bytes(), payload)

    def test_fetch_payload_from_file_is_reusable_without_project_config(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sample = root / "rows.csv"
            sample.write_text("a,b\n1,2\n", encoding="utf-8")
            cfg = {"source_test": {"format": "json", "fallback_file": str(sample)}}

            result = fetch_payload(
                cfg,
                "source_test",
                "https://example.test/source",
                root / "raw",
                timeout=5,
                from_file=sample,
                strict_network=True,
            )

            self.assertEqual(result["note"], "from-file")
            self.assertEqual(result["content_type"], None)
            self.assertTrue(str(result["resolved_url"]).startswith("file://"))
            self.assertTrue(str(result["raw_path"]).endswith(".csv"))

    def test_fetch_payload_allows_html_when_source_format_is_html(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sample = root / "page.html"
            sample.write_text("<html><body>ok</body></html>", encoding="utf-8")
            cfg = {"source_html": {"format": "html", "fallback_file": str(sample)}}

            with patch(
                "publicdata_core.fetch.http_get_bytes",
                return_value=(b"<html><body>ok</body></html>", "text/html"),
            ):
                result = fetch_payload(
                    cfg,
                    "source_html",
                    "https://example.test/page",
                    root / "raw",
                    timeout=5,
                    from_file=None,
                    strict_network=True,
                )

            self.assertEqual(result["note"], "network")
            self.assertTrue(str(result["raw_path"]).endswith(".html"))

    def test_util_helpers_are_stable_for_source_records(self) -> None:
        self.assertEqual(normalize_key_part(" José-Luis/Álvarez "), "jose luis alvarez")
        self.assertEqual(stable_json({"b": 2, "a": 1}), '{"a": 1, "b": 2}')

    def test_parser_helpers_are_reusable(self) -> None:
        self.assertEqual(parse_json_source(b'{"results":[{"id":1}]}'), [{"id": 1}])
        self.assertEqual(parse_csv_source("sep=;\na;b\n1;2\n".encode("utf-8")), [{"a": "1", "b": "2"}])
        self.assertEqual(xlsx_col_to_index("AB12"), 27)

    def test_source_definition_round_trips_to_legacy_config_mapping(self) -> None:
        definition = SourceDefinition(
            source_id="source_test",
            name="Test source",
            scope="test",
            default_url="https://example.test/data.json",
            format="json",
            fallback_file="samples/source_test.json",
            min_records_loaded_strict=1,
            license="CC0-1.0",
            metadata={"extra": "kept"},
        )

        config = source_config_mapping([definition])
        self.assertEqual(config["source_test"]["default_url"], "https://example.test/data.json")
        self.assertEqual(config["source_test"]["license"], "CC0-1.0")
        self.assertEqual(config["source_test"]["extra"], "kept")
        self.assertEqual(source_definitions_from_config(config), (definition,))

    def test_infoelectoral_package_exposes_typed_source_definitions_and_legacy_config(self) -> None:
        self.assertEqual(
            set(INFOELECTORAL_SOURCE_CONFIG),
            {definition.source_id for definition in INFOELECTORAL_SOURCE_DEFINITIONS},
        )
        self.assertEqual(INFOELECTORAL_SOURCE_CONFIG["infoelectoral_descargas"]["format"], "json")

    def test_workflow_plan_enforces_five_step_contract(self) -> None:
        plan = WorkflowPlan(
            workflow_id="demo",
            label="Demo",
            runtime_shapes=(RuntimeShape.NETWORK_STRICT, RuntimeShape.SAMPLE_REPLAY),
        )
        self.assertEqual(plan.steps[0], CanonicalStep.REGISTER)
        self.assertEqual(plan.as_dict()["steps"], ["register", "acquire", "normalize", "enrich", "publish"])
        with self.assertRaisesRegex(ValueError, "<= 5"):
            WorkflowPlan(
                workflow_id="bad",
                label="Bad",
                steps=(
                    CanonicalStep.REGISTER,
                    CanonicalStep.ACQUIRE,
                    CanonicalStep.NORMALIZE,
                    CanonicalStep.ENRICH,
                    CanonicalStep.PUBLISH,
                    CanonicalStep.PUBLISH,
                ),
            )

    def test_default_publicdata_workflows_expose_runtime_shapes(self) -> None:
        workflows = {workflow.workflow_id: workflow for workflow in default_publicdata_workflows()}
        self.assertIn("parliamentary_evidence", workflows)
        self.assertIn(RuntimeShape.ARCHIVE_FALLBACK, workflows["parliamentary_evidence"].runtime_shapes)


if __name__ == "__main__":
    unittest.main()
