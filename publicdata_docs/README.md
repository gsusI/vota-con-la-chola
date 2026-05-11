# publicdata_docs

Reusable document-recovery helpers for public-data ETL projects.

Current scope:
- HTTP status error and retry/archive status normalization
- public-safe runtime path reporting
- Playwright Node runtime fallback detection
- canonical URL, stable dedupe, gzip decompression and HTTP error helpers
- local text extraction from XML/HTML/PDF raw bytes
- deterministic local text-extraction queue building from `text_documents`
- Spanish parliamentary document recovery in `parliamentary_es`: topic-evidence document fetches, initiative document link extraction, direct/archive/browser/manual replay fallbacks, raw-byte storage, text excerpts and fetch-status accounting

Vota still owns concrete CLI commands, DB path defaults, source priority, review cadence and product reporting.
