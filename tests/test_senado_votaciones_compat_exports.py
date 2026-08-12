from __future__ import annotations

import unittest

from etl.parlamentario_es.connectors import senado_votaciones


class TestSenadoVotacionesCompatExports(unittest.TestCase):
    def test_backfill_private_helpers_are_explicitly_exported(self) -> None:
        for name in (
            "_enrich_senado_record_with_details",
            "_find_local_session_xml",
            "_load_session_vote_info",
            "_session_vote_file_url_candidates",
            "_to_int",
        ):
            self.assertTrue(callable(getattr(senado_votaciones, name, None)), name)


if __name__ == "__main__":
    unittest.main()
