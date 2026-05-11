"""Reusable document-recovery helpers for public-data ETL projects."""

from .extraction import extract_from_pdf, extract_from_xml_or_html, normalize_text, should_parse_as_pdf
from .extraction_queue import build_queue_rows as build_text_extraction_queue_rows
from .runtime import command_exit_code, ensure_playwright_nodejs_runtime, sanitize_runtime_path_for_public
from .statuses import HTTPStatusError, normalize_archive_fallback_http_statuses, normalize_http_status_filter
from .urls import canonical_url, dedupe_keep_order, exception_http_status, maybe_decompress_gzip_payload

__all__ = [
    "HTTPStatusError",
    "build_text_extraction_queue_rows",
    "canonical_url",
    "command_exit_code",
    "dedupe_keep_order",
    "ensure_playwright_nodejs_runtime",
    "exception_http_status",
    "extract_from_pdf",
    "extract_from_xml_or_html",
    "maybe_decompress_gzip_payload",
    "normalize_text",
    "normalize_archive_fallback_http_statuses",
    "normalize_http_status_filter",
    "sanitize_runtime_path_for_public",
    "should_parse_as_pdf",
]
