#!/usr/bin/env python3
"""Scaffold one dataset source for contributor onboarding."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "publicdata_connectors_es" / "contrib" / "config.py"
PARSERS_DIR = REPO_ROOT / "publicdata_connectors_es" / "contrib" / "parsers"
SAMPLES_DIR = REPO_ROOT / "etl" / "data" / "raw" / "samples"
SOURCE_DOCS_DIR = REPO_ROOT / "docs" / "etl" / "sources"

SOURCE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
DEFINITION_END_MARKER = "    # add-source:definitions:end"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create source config, sample, parser, test, and docs stubs.")
    parser.add_argument("source_id", help="Stable snake_case source id, e.g. boe_contract_awards")
    parser.add_argument("--name", required=True, help="Human source name")
    parser.add_argument("--scope", required=True, help="Scope bucket, e.g. nacional/autonomico/dinero")
    parser.add_argument("--url", required=True, help="Default source URL")
    parser.add_argument("--format", choices=("json", "csv", "xml", "html"), default="json")
    parser.add_argument("--min-records", type=int, default=1, help="Strict network minimum loaded rows")
    parser.add_argument("--institution", default="", help="Institution name metadata")
    parser.add_argument("--level", default="", help="Level metadata")
    parser.add_argument("--dry-run", action="store_true", help="Print planned files without writing")
    return parser.parse_args()


def _require_source_id(source_id: str) -> str:
    token = source_id.strip()
    if not SOURCE_ID_RE.fullmatch(token):
        raise SystemExit("source_id must be snake_case: ^[a-z][a-z0-9_]*$")
    return token


def _sample_suffix(fmt: str) -> str:
    return "json" if fmt == "html" else fmt


def _sample_text(source_id: str, fmt: str, url: str) -> str:
    if fmt in {"json", "html"}:
        return json.dumps(
            {
                "source": source_id,
                "records": [
                    {
                        "source_record_id": f"{source_id}:sample:1",
                        "source_url": url,
                        "title": "Sample record",
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        ) + "\n"
    if fmt == "csv":
        return "source_record_id,source_url,title\n" f"{source_id}:sample:1,{url},Sample record\n"
    if fmt == "xml":
        return (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            f"<records source=\"{source_id}\">\n"
            f"  <record><source_record_id>{source_id}:sample:1</source_record_id>"
            f"<source_url>{url}</source_url><title>Sample record</title></record>\n"
            "</records>\n"
        )
    raise AssertionError(fmt)


def _parser_text(source_id: str, fmt: str) -> str:
    if fmt in {"json", "html"}:
        return '''from __future__ import annotations

import json
from typing import Any


def parse_records(payload: bytes) -> list[dict[str, Any]]:
    parsed = json.loads(payload.decode("utf-8"))
    if isinstance(parsed, dict) and isinstance(parsed.get("records"), list):
        return [record for record in parsed["records"] if isinstance(record, dict)]
    if isinstance(parsed, list):
        return [record for record in parsed if isinstance(record, dict)]
    return []
'''
    if fmt == "csv":
        return '''from __future__ import annotations

import csv
import io
from typing import Any


def parse_records(payload: bytes) -> list[dict[str, Any]]:
    text = payload.decode("utf-8-sig")
    return [dict(row) for row in csv.DictReader(io.StringIO(text))]
'''
    if fmt == "xml":
        return '''from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any


def parse_records(payload: bytes) -> list[dict[str, Any]]:
    root = ET.fromstring(payload)
    rows: list[dict[str, Any]] = []
    for node in root.findall(".//record"):
        row = {child.tag: (child.text or "").strip() for child in list(node)}
        if row:
            rows.append(row)
    return rows
'''
    raise AssertionError(fmt)


def _test_text(source_id: str) -> str:
    return f'''from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA, SOURCE_CONFIG
from etl.politicos_es.db import apply_schema, open_db, seed_dimensions, seed_sources
from etl.politicos_es.pipeline import ingest_one_source
from etl.politicos_es.registry import get_connectors


class Test{source_id.title().replace("_", "")}Onboarding(unittest.TestCase):
    def test_sample_fixture_ingests_as_source_records(self) -> None:
        connector = get_connectors()["{source_id}"]
        sample_path = Path(SOURCE_CONFIG["{source_id}"]["fallback_file"])
        self.assertTrue(sample_path.exists(), f"Missing sample: {{sample_path}}")

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "source.db"
            raw_dir = Path(td) / "raw"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                seed_dimensions(conn)
                seen, loaded, note = ingest_one_source(
                    conn=conn,
                    connector=connector,
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=sample_path,
                    url_override=None,
                    snapshot_date="2026-02-12",
                    strict_network=True,
                )
                self.assertEqual(seen, 1)
                self.assertEqual(loaded, 1)
                self.assertEqual(note, "from-file")
            finally:
                conn.close()
'''


def _doc_text(source_id: str, args: argparse.Namespace, sample_rel: str, parser_rel: str) -> str:
    return f"""# {args.name}

- `source_id`: `{source_id}`
- Estado inicial: `missing` hasta primer run real.
- URL fuente: `{args.url}`
- Scope: `{args.scope}`
- Formato: `{args.format}`
- Muestra: `{sample_rel}`
- Parser: `{parser_rel}`
- Gate minimo strict-network: `{args.min_records}` registros.

## Extension path

1. Ajustar muestra con un payload pequeno y representativo.
2. Implementar `parse_records(payload)` en el parser.
3. Ejecutar `python3 -m unittest tests.test_{source_id}_source_onboarding -q`.
4. Ejecutar `just etl-contributor-gates` antes de PR.
5. Actualizar blocker/legal notes si upstream bloquea o limita reutilizacion.
"""


def _definition_block(args: argparse.Namespace, sample_rel: str) -> str:
    metadata: dict[str, str] = {}
    if args.institution.strip():
        metadata["institution_name"] = args.institution.strip()
    if args.level.strip():
        metadata["level"] = args.level.strip()
    metadata_text = f",\n        metadata={metadata!r}" if metadata else ""
    return (
        "    SourceDefinition(\n"
        f"        source_id={args.source_id!r},\n"
        f"        name={args.name!r},\n"
        f"        scope={args.scope!r},\n"
        f"        default_url={args.url!r},\n"
        f"        format={args.format!r},\n"
        f"        fallback_file={sample_rel!r},\n"
        f"        min_records_loaded_strict={int(args.min_records)}{metadata_text},\n"
        "    ),\n"
    )


def _planned_paths(source_id: str, fmt: str) -> dict[str, Path]:
    suffix = _sample_suffix(fmt)
    return {
        "config": CONFIG_PATH,
        "sample": SAMPLES_DIR / f"{source_id}_sample.{suffix}",
        "parser": PARSERS_DIR / f"{source_id}.py",
        "test": REPO_ROOT / "tests" / f"test_{source_id}_source_onboarding.py",
        "doc": SOURCE_DOCS_DIR / f"{source_id}.md",
    }


def _assert_new_files(paths: Iterable[Path]) -> None:
    existing = [path for path in paths if path.exists()]
    if existing:
        rels = ", ".join(str(path.relative_to(REPO_ROOT)) for path in existing)
        raise SystemExit(f"Refusing to overwrite existing files: {rels}")


def _insert_definition(config_path: Path, block: str) -> None:
    text = config_path.read_text(encoding="utf-8")
    if block in text:
        raise SystemExit("Source definition already present")
    if DEFINITION_END_MARKER not in text:
        raise SystemExit(f"Missing marker in {config_path}")
    text = text.replace(DEFINITION_END_MARKER, block + DEFINITION_END_MARKER)
    config_path.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    args.source_id = _require_source_id(args.source_id)
    paths = _planned_paths(args.source_id, args.format)
    sample_rel = str(paths["sample"].relative_to(REPO_ROOT))
    parser_rel = str(paths["parser"].relative_to(REPO_ROOT))
    test_rel = str(paths["test"].relative_to(REPO_ROOT))
    doc_rel = str(paths["doc"].relative_to(REPO_ROOT))

    if args.dry_run:
        print(json.dumps({key: str(path.relative_to(REPO_ROOT)) for key, path in paths.items()}, indent=2))
        return 0

    _assert_new_files([paths["sample"], paths["parser"], paths["test"], paths["doc"]])
    for path in (paths["sample"], paths["parser"], paths["test"], paths["doc"]):
        path.parent.mkdir(parents=True, exist_ok=True)

    paths["sample"].write_text(_sample_text(args.source_id, args.format, args.url), encoding="utf-8")
    paths["parser"].write_text(_parser_text(args.source_id, args.format), encoding="utf-8")
    paths["test"].write_text(_test_text(args.source_id), encoding="utf-8")
    paths["doc"].write_text(_doc_text(args.source_id, args, sample_rel, parser_rel), encoding="utf-8")
    _insert_definition(paths["config"], _definition_block(args, sample_rel))

    print("OK add-source scaffold")
    for rel in (sample_rel, parser_rel, test_rel, doc_rel):
        print(f"- {rel}")
    print(f"- config: {CONFIG_PATH.relative_to(REPO_ROOT)}")
    print(f"Next: python3 -m unittest {test_rel[:-3].replace('/', '.')} -q")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
