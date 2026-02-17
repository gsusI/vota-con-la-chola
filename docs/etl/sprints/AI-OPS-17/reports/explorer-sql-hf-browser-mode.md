# Explorer SQL en GH Pages (HF + DuckDB WASM)

Date: 2026-02-17
Status: DONE

## Goal
Make audit links usable on GitHub Pages without a Python API server by running SQL-like exploration in the browser against Parquet tables hosted on Hugging Face Datasets.

## How It Works
Explorer SQL (`ui/graph/explorer.html`) now has two backends:

1) **API mode (local)**
- Used when:
  - the host is local (`localhost`, `127.0.0.1`, etc.), or
  - `?api=<base>` is provided.
- It checks `/api/health` and uses the existing REST API if healthy.

2) **HF/browser mode (static)**
- Used when API health is not available.
- Loads:
  - DuckDB WASM (ESM) from jsDelivr
  - `latest.json` from Hugging Face to find the current `snapshot_dir`
  - `manifest.json` to discover Parquet tables and shard counts
  - Parquet parts via `read_parquet([...urls])` (views per table)
  - optional `explorer_schema.json` (schema contract with PK/FK for better navigation)

## URL Parameters
- `api`: API base override (example: `?api=http://127.0.0.1:9010`)
- `dataset`: HF dataset repo (`owner/name`)
- `hf_ref`: HF git ref (default `main`)
- `snapshot`: snapshot id override (maps to `snapshots/<snapshot>/...` in the dataset)

## HF Dataset Requirements
Publishing to HF is handled by:
- `just etl-publish-hf` (or `just etl-publish-hf-dry-run`)

Artifacts expected by HF/browser mode:
- `latest.json`
- `snapshots/<snapshot_date>/manifest.json`
- `snapshots/<snapshot_date>/parquet/<table>/part-00000.parquet` (and other parts)
- `snapshots/<snapshot_date>/explorer_schema.json` (optional but recommended; includes PK/FK contract)

## Notes / Constraints
- First load is network-bound (DuckDB WASM + Parquet reads).
- No backend means no private endpoints; everything must be public on HF/CDN.
- Explorer-Temas still needs API for coherence/reviews; Explorer SQL is the reliable audit path on GH Pages.
