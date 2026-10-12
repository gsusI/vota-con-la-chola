from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from etl.politicos_es import cli


class IngestAllContinuesOnSourceErrorTests(unittest.TestCase):
    def run_ingest(self, source: str, outcomes: dict[str, object]) -> tuple[int, list[str]]:
        calls: list[str] = []

        def fake_ingest(*, connector, **_kwargs):
            calls.append(connector)
            outcome = outcomes[connector]
            if isinstance(outcome, list):
                outcome = outcome.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict("os.environ", {"INGEST_RETRY_DELAY_SECONDS": "0"}), mock.patch.object(
            cli, "get_connectors", return_value={name: name for name in outcomes}
        ), mock.patch.object(cli, "ingest_one_source", side_effect=fake_ingest):
            args = cli.parse_args(["ingest", "--db", str(Path(tmp) / "t.db"), "--source", source, "--raw-dir", tmp])
            code = cli.cmd_ingest(args)
        return code, calls

    def test_all_records_failure_and_continues(self) -> None:
        code, calls = self.run_ingest(
            "all", {"a_blocked": RuntimeError("HTTP 403"), "b_ok": (3, 3, "network"), "c_ok": (1, 1, "network")}
        )
        self.assertEqual(code, 0)
        self.assertEqual(calls, ["a_blocked", "b_ok", "c_ok", "a_blocked"])

    def test_transient_failure_recovers_on_retry(self) -> None:
        code, calls = self.run_ingest(
            "all", {"a_flaky": [TimeoutError("read timed out"), (5, 5, "network")], "b_ok": (1, 1, "network")}
        )
        self.assertEqual(code, 0)
        self.assertEqual(calls, ["a_flaky", "b_ok", "a_flaky"])

    def test_all_sources_failing_returns_error(self) -> None:
        code, _ = self.run_ingest("all", {"a": RuntimeError("x"), "b": RuntimeError("y")})
        self.assertEqual(code, 1)

    def test_single_source_still_fails_hard(self) -> None:
        with self.assertRaises(RuntimeError):
            self.run_ingest("a", {"a": RuntimeError("HTTP 403")})


if __name__ == "__main__":
    unittest.main()
