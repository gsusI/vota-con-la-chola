"""Reusable SQLite helpers for public-data ETL projects."""

from .core import ensure_column, open_db, table_columns, table_create_sql, table_exists
from .provenance import (
    seed_sources_from_config,
    upsert_source_record,
    upsert_source_record_for_event,
    upsert_source_records,
    upsert_source_records_with_content_sha256,
)

__all__ = [
    "ensure_column",
    "open_db",
    "seed_sources_from_config",
    "table_columns",
    "table_create_sql",
    "table_exists",
    "upsert_source_record",
    "upsert_source_record_for_event",
    "upsert_source_records",
    "upsert_source_records_with_content_sha256",
]
