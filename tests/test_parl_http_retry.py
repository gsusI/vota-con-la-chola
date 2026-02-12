from __future__ import annotations

import unittest
import urllib.error
from unittest.mock import MagicMock, call, patch

from etl.parlamentario_es.http import http_get_bytes


def _http_error(code: int, *, retry_after: str | None = None) -> urllib.error.HTTPError:
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    return urllib.error.HTTPError(
        url="https://example.test/api",
        code=code,
        msg=f"HTTP {code}",
        hdrs=headers,
        fp=None,
    )


def _response_ctx(payload: bytes, content_type: str) -> MagicMock:
    response = MagicMock()
    response.read.return_value = payload
    response.headers.get.return_value = content_type

    ctx = MagicMock()
    ctx.__enter__.return_value = response
    ctx.__exit__.return_value = False
    return ctx


class TestParlHttpRetry(unittest.TestCase):
    def test_retry_then_success(self) -> None:
        with (
            patch(
                "etl.parlamentario_es.http.urllib.request.urlopen",
                side_effect=[_http_error(503, retry_after="3"), _response_ctx(b"ok", "application/json")],
            ) as mock_urlopen,
            patch("etl.parlamentario_es.http.time.sleep") as mock_sleep,
            patch("etl.parlamentario_es.http.random.uniform") as mock_jitter,
        ):
            body, content_type = http_get_bytes("https://example.test/api", timeout=5)

        self.assertEqual(body, b"ok")
        self.assertEqual(content_type, "application/json")
        self.assertEqual(mock_urlopen.call_count, 2)
        mock_sleep.assert_called_once_with(3.0)
        mock_jitter.assert_not_called()

    def test_non_retryable_http_error_fast_fails(self) -> None:
        with (
            patch(
                "etl.parlamentario_es.http.urllib.request.urlopen",
                side_effect=_http_error(404),
            ) as mock_urlopen,
            patch("etl.parlamentario_es.http.time.sleep") as mock_sleep,
        ):
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                http_get_bytes("https://example.test/not-found", timeout=5)

        self.assertEqual(ctx.exception.code, 404)
        self.assertEqual(mock_urlopen.call_count, 1)
        mock_sleep.assert_not_called()

    def test_retryable_errors_exhaust_and_raise(self) -> None:
        side_effect = [_http_error(503), _http_error(408), _http_error(502)]
        with (
            patch(
                "etl.parlamentario_es.http.urllib.request.urlopen",
                side_effect=side_effect,
            ) as mock_urlopen,
            patch("etl.parlamentario_es.http.time.sleep") as mock_sleep,
            patch("etl.parlamentario_es.http.random.uniform", return_value=0.0),
        ):
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                http_get_bytes("https://example.test/flaky", timeout=5)

        self.assertEqual(ctx.exception.code, 502)
        self.assertEqual(mock_urlopen.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_has_calls([call(1.0), call(2.0)])


if __name__ == "__main__":
    unittest.main()
