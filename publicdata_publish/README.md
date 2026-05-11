# publicdata_publish

Reusable publishing helpers for public-data projects.

Current scope:
- public artifact privacy scan
- sensitive text redaction
- public URL sanitization for logs and manifests
- generic HF/static snapshot packaging helpers in `hf_snapshot`: `.env` setting resolution, published artifact collection, quality/source-catalog summaries, SQLite schema payloads, ingestion/source-record CSV exports, deterministic gzip/checksums and Parquet table export

Vota still owns concrete Hugging Face dataset orchestration, source legal profiles, project README copy, domain snapshots and UI bundle layout.
