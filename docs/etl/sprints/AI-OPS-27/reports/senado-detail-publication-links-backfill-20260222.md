# Senado Detail Publication Links Backfill (2026-02-22)

## Objective
Use already-downloaded Senate detail XML (`tipoFich=3`) to recover additional official BOCG/DS publication URLs and download them, without depending on blocked `global_enmiendas_vetos_*` URLs.

## Changes shipped
- New script: `scripts/backfill_senado_publication_links_from_detail_docs.py`
  - Parses downloaded detail XML.
  - Extracts Senate publication PDFs under `/publicaciones/pdf/senado/bocg/` and `/publicaciones/pdf/senado/ds/`.
  - Appends discovered URLs into `parl_initiatives.links_bocg_json` / `links_ds_json`.
  - Supports `--only-initiatives-with-missing-docs`, `--limit`, and `--dry-run`.
- New just target:
  - `just parl-backfill-senado-detail-publication-links`

## Execution

Dry-run:
```bash
python3 scripts/backfill_senado_publication_links_from_detail_docs.py \
  --db etl/data/staging/politicos-es.db \
  --source-id senado_iniciativas \
  --doc-source-id parl_initiative_docs \
  --only-initiatives-with-missing-docs \
  --dry-run
```

Applied run:
```bash
python3 scripts/backfill_senado_publication_links_from_detail_docs.py \
  --db etl/data/staging/politicos-es.db \
  --source-id senado_iniciativas \
  --doc-source-id parl_initiative_docs \
  --only-initiatives-with-missing-docs
```

Evidence:
- `docs/etl/sprints/AI-OPS-27/evidence/senado_detail_publication_links_backfill_20260222T141811Z.json`

Backfill download pass after adding links:
```bash
python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --include-unlinked \
  --limit-initiatives 200 \
  --max-docs-per-initiative 25 \
  --timeout 12
```

Evidence:
- `docs/etl/sprints/AI-OPS-27/evidence/senado_detail_publication_download_20260222T141857Z.json`

Excerpt re-fill after new downloads:
```bash
python3 scripts/backfill_initiative_doc_excerpts.py \
  --db etl/data/staging/politicos-es.db \
  --source-id parl_initiative_docs \
  --initiative-source-id senado_iniciativas
```

Evidence:
- `docs/etl/sprints/AI-OPS-27/evidence/senado_excerpt_backfill_after_detail_publication_20260222T141958Z.json`

## Results
- Link enrichment:
  - initiatives seen: `8`
  - initiatives updated: `7`
  - links added: `50` (`35` BOCG + `15` DS)
- Download pass:
  - `urls_to_fetch=49`
  - `fetched_ok=49`
  - `text_documents_upserted=49`
  - no failures
- Excerpt fill:
  - `updated=49`
  - no failures

## KPI delta
Before this slice:
- overall initiative docs: `8966/9085`
- senate initiative docs: `8154/8273`

After this slice:
- overall initiative docs: `9016/9135` (`98.70%`)
- senate initiative docs: `8204/8323` (`98.57%`)
- fetch-status coverage: `100%`
- excerpt coverage on downloaded docs: `100%`

Enhanced triage after this slice remains:
- senate raw missing: `119`
- `likely_not_expected_zero_enmiendas`: `115`
- actionable unknowns: `4`

Evidence snapshots:
- `docs/etl/sprints/AI-OPS-27/evidence/initiative_doc_status_post_detail_publication_excerpt_20260222T142006Z.json`
- `docs/etl/sprints/AI-OPS-27/evidence/quality_initiatives_post_detail_publication_excerpt_20260222T142002Z.json`

## Conclusion
This slice added real Senate evidence coverage without requiring upstream unblock on `global_enmiendas_vetos_*`. Remaining blocker scope stays narrow (`4` actionable unknown URLs + `115` likely non-materialized links).
