from __future__ import annotations

import sqlite3
import unittest

from scripts import export_legal_sanctions_snapshot as legal_sanctions


class TestExportLegalSanctionsSnapshot(unittest.TestCase):
    def test_build_legal_graph_returns_empty_payload_when_legal_norms_missing(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            payload = legal_sanctions.build_legal_graph(
                conn,
                max_norms=240,
                max_fragments_per_norm=6,
                max_edges=500,
            )
        finally:
            conn.close()

        self.assertEqual(
            payload,
            {
                "nodes": [],
                "edges": [],
                "node_count": 0,
                "edge_count": 0,
                "relation_types": [],
                "nodes_with_fragments": 0,
            },
        )


if __name__ == "__main__":
    unittest.main()
