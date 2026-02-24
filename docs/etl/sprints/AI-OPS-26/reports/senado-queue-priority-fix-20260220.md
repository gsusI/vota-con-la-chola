# Senado Queue Priority Fix (2026-02-20)

## Problem

During sustained retries, bounded queue runs were repeatedly selecting the same blocked initiative/doc subset first, producing `fetched_ok=0` loops even when other queue segments were still recoverable.

## Change applied

File changed:
- `etl/parlamentario_es/text_documents.py`

Behavior updates in `backfill_initiative_documents_from_parl_initiatives`:
- Added fetch-status-aware initiative ordering for non-linked wide drains when `document_fetches` exists:
  - prioritize missing docs never attempted, then oldest-attempted missing docs.
- Added URL-level priority sorting:
  - hard-failed (`403/404/500` with attempts>0 and no success) URLs are de-prioritized.
  - fewer-attempt URLs are preferred before heavily retried ones.

## Why this helps

- Prevents head-of-queue starvation by recently blocked URLs.
- Improves chance to reach fetchable pockets in large mixed-quality queues.
- Keeps existing behavior backward-compatible when `document_fetches` table is absent.

## Validation signal

Post-patch probe in active window recovered non-zero throughput (`fetched_ok=34/80`) without changing external dependencies.
