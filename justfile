db_path := env_var_or_default("DB_PATH", "etl/data/staging/politicos-es.db")
snapshot_date := env_var_or_default("SNAPSHOT_DATE", "2026-02-12")
tracker_path := env_var_or_default("TRACKER_PATH", "docs/etl/e2e-scrape-load-tracker.md")
tracker_waivers_path := env_var_or_default("TRACKER_WAIVERS_PATH", "docs/etl/mismatch-waivers.json")
municipal_timeout := env_var_or_default("MUNICIPAL_TIMEOUT", "240")
galicia_manual_dir := env_var_or_default("GALICIA_MANUAL_DIR", "etl/data/raw/manual/galicia_deputado_profiles_20260212T141929Z/pages")
navarra_manual_dir := env_var_or_default("NAVARRA_MANUAL_DIR", "etl/data/raw/manual/navarra_persona_profiles_20260212T144911Z/pages")
infoelectoral_timeout := env_var_or_default("INFOELECTORAL_TIMEOUT", "30")
senado_detail_workers := env_var_or_default("SENADO_DETAIL_WORKERS", "16")
senado_detail_timeout := env_var_or_default("SENADO_DETAIL_TIMEOUT", "8")
senado_detail_max_events := env_var_or_default("SENADO_DETAIL_MAX_EVENTS", "30")
senado_detail_max_loops := env_var_or_default("SENADO_DETAIL_MAX_LOOPS", "1")
senado_detail_legislatures := env_var_or_default("SENADO_DETAIL_LEGISLATURES", "14")
senado_detail_dir := env_var_or_default("SENADO_DETAIL_DIR", "")
senado_manual_detail_dir := env_var_or_default("SENADO_MANUAL_DETAIL_DIR", "etl/data/raw/manual/senado_votaciones_ses")
senado_missing_detail_urls_file := env_var_or_default("SENADO_MISSING_DETAIL_URLS_FILE", "etl/data/raw/manual/senado_votaciones_ses/missing_detail_urls.txt")
senado_manual_download_timeout := env_var_or_default("SENADO_MANUAL_DOWNLOAD_TIMEOUT", "30")
senado_headful_channel := env_var_or_default("SENADO_HEADFUL_CHANNEL", "chrome")
senado_headful_timeout := env_var_or_default("SENADO_HEADFUL_TIMEOUT", "30")
senado_headful_user_data_dir := env_var_or_default("SENADO_HEADFUL_USER_DATA_DIR", "etl/data/raw/manual/senado_votaciones_ses/.headful-profile")
senado_headful_viewport := env_var_or_default("SENADO_HEADFUL_VIEWPORT", "1280x800")
senado_headful_wait_seconds := env_var_or_default("SENADO_HEADFUL_WAIT_SECONDS", "90")
explorer_host := env_var_or_default("EXPLORER_HOST", "127.0.0.1")
explorer_port := env_var_or_default("EXPLORER_PORT", "9010")
gh_pages_dir := env_var_or_default("GH_PAGES_DIR", "docs/gh-pages")
gh_pages_remote := env_var_or_default("GH_PAGES_REMOTE", "origin")
gh_pages_branch := env_var_or_default("GH_PAGES_BRANCH", "gh-pages")
gh_pages_tmp_branch := env_var_or_default("GH_PAGES_TMP_BRANCH", "gh-pages-tmp")
topic_taxonomy_seed := env_var_or_default("TOPIC_TAXONOMY_SEED", "etl/data/seeds/topic_taxonomy_es.json")
textdoc_limit := env_var_or_default("TEXTDOC_LIMIT", "900")
textdoc_timeout := env_var_or_default("TEXTDOC_TIMEOUT", "25")
declared_min_auto_confidence := env_var_or_default("DECLARED_MIN_AUTO_CONFIDENCE", "0.62")
code_zip_name := env_var_or_default("CODE_ZIP_NAME", "vota-con-la-chola-code.zip")
hf_dataset_repo_id := env_var_or_default("HF_DATASET_REPO_ID", "vota-con-la-chola-data")
hf_parquet_batch_rows := env_var_or_default("HF_PARQUET_BATCH_ROWS", "50000")
hf_parquet_compression := env_var_or_default("HF_PARQUET_COMPRESSION", "zstd")
hf_parquet_tables := env_var_or_default("HF_PARQUET_TABLES", "")
hf_parquet_exclude_tables := env_var_or_default("HF_PARQUET_EXCLUDE_TABLES", "raw_fetches,run_fetches,source_records,lost_and_found")
hf_allow_sensitive_parquet := env_var_or_default("HF_ALLOW_SENSITIVE_PARQUET", "0")
hf_include_sqlite_gz := env_var_or_default("HF_INCLUDE_SQLITE_GZ", "0")

default:
  @just --list

zip-code output='':
  out="{{output}}"; \
  if [ -z "$out" ]; then out="dist/{{code_zip_name}}"; fi; \
  mkdir -p "$(dirname "$out")"; \
  rm -f "$out"; \
  git ls-files \
    | rg '^(scripts/|etl/|ui/|tests/|justfile$|docker-compose\.ya?ml$|Dockerfile$|pyproject\.toml$|requirements[^/]*\.txt$)' \
    | rg -v '^etl/data/' \
    | zip -q "$out" -@; \
  echo "OK wrote $out"

etl-cli cmd:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py {{cmd}}"

py cmd:
  docker compose run --rm --build etl "python3 {{cmd}}"

parl-cli cmd:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py {{cmd}}"

etl-build:
  docker compose build etl

etl-init:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py init-db --db {{db_path}}"

etl-samples:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source congreso_diputados --from-file etl/data/raw/samples/congreso_diputados_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source cortes_aragon_diputados --from-file etl/data/raw/samples/cortes_aragon_diputados_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source senado_senadores --from-file etl/data/raw/samples/senado_senadores_sample.csv --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source europarl_meps --from-file etl/data/raw/samples/europarl_meps_sample.xml --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source municipal_concejales --from-file etl/data/raw/samples/municipal_concejales_sample.csv --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_madrid_ocupaciones --from-file etl/data/raw/samples/asamblea_madrid_ocupaciones_sample.csv --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_ceuta_diputados --from-file etl/data/raw/samples/asamblea_ceuta_diputados_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_melilla_diputados --from-file etl/data/raw/samples/asamblea_melilla_diputados_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_extremadura_diputados --from-file etl/data/raw/samples/asamblea_extremadura_diputados_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_murcia_diputados --from-file etl/data/raw/samples/asamblea_murcia_diputados_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source jgpa_diputados --from-file etl/data/raw/samples/jgpa_diputados_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_canarias_diputados --from-file etl/data/raw/samples/parlamento_canarias_diputados_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_cantabria_diputados --from-file etl/data/raw/samples/parlamento_cantabria_diputados_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlament_balears_diputats --from-file etl/data/raw/samples/parlament_balears_diputats_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_larioja_diputados --from-file etl/data/raw/samples/parlamento_larioja_diputados_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlament_catalunya_diputats --from-file etl/data/raw/samples/parlament_catalunya_diputats_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source corts_valencianes_diputats --from-file etl/data/raw/samples/corts_valencianes_diputats_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source cortes_clm_diputados --from-file etl/data/raw/samples/cortes_clm_diputados_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source cortes_cyl_procuradores --from-file etl/data/raw/samples/cortes_cyl_procuradores_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_andalucia_diputados --from-file etl/data/raw/samples/parlamento_andalucia_diputados_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_vasco_parlamentarios --from-file etl/data/raw/samples/parlamento_vasco_parlamentarios_sample.json --snapshot-date {{snapshot_date}}"

parl-init:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py init-db --db {{db_path}}"

parl-samples:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py ingest --db {{db_path}} --source congreso_votaciones --from-file etl/data/raw/samples/congreso_votaciones_sample.json --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py ingest --db {{db_path}} --source congreso_iniciativas --from-file etl/data/raw/samples/congreso_iniciativas_sample.json --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py ingest --db {{db_path}} --source senado_iniciativas --from-file etl/data/raw/samples/senado_iniciativas_sample.xml --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py ingest --db {{db_path}} --source senado_votaciones --from-file etl/data/raw/samples/senado_votaciones_sample.xml --snapshot-date {{snapshot_date}} --strict-network"

etl-stats:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py stats --db {{db_path}}"

etl-backfill-normalized:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py backfill-normalized --db {{db_path}}"

etl-backfill-territories:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py backfill-territories --db {{db_path}}"

etl-backfill-policy-events-moncloa:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py backfill-policy-events-moncloa --db {{db_path}}"

etl-backfill-policy-events-boe:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py backfill-policy-events-boe --db {{db_path}}"

etl-test:
  docker compose run --rm --build etl "python3 -m unittest discover -s tests -v"

etl-live:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source all --snapshot-date {{snapshot_date}} --timeout {{municipal_timeout}}"

etl-elecciones:
  docker compose run --rm --build etl "python3 scripts/generar_proximas_elecciones_espana.py --today {{snapshot_date}}"

etl-publish-representantes:
  docker compose run --rm --build etl "python3 scripts/publicar_representantes_es.py --db {{db_path}} --snapshot-date {{snapshot_date}}"

etl-publish-votaciones:
  docker compose run --rm --build etl "python3 scripts/publicar_votaciones_es.py --db {{db_path}} --snapshot-date {{snapshot_date}}"

etl-publish-votaciones-unmatched:
  docker compose run --rm --build etl "python3 scripts/publicar_votaciones_es.py --db {{db_path}} --snapshot-date {{snapshot_date}} --include-unmatched --unmatched-sample-limit 100"

etl-publish-infoelectoral:
  docker compose run --rm --build etl "python3 scripts/publicar_infoelectoral_es.py --db {{db_path}} --snapshot-date {{snapshot_date}}"

etl-publish-hf:
  sqlite_arg="--skip-sqlite-gz"; \
  sensitive_arg=""; \
  if [ "{{hf_include_sqlite_gz}}" = "1" ]; then sqlite_arg=""; fi; \
  if [ "{{hf_allow_sensitive_parquet}}" = "1" ]; then sensitive_arg="--allow-sensitive-parquet"; fi; \
  docker compose run --rm --build etl "python3 scripts/publicar_hf_snapshot.py --db {{db_path}} --snapshot-date {{snapshot_date}} --dataset-repo {{hf_dataset_repo_id}} --parquet-compression {{hf_parquet_compression}} --parquet-batch-rows {{hf_parquet_batch_rows}} --parquet-tables '{{hf_parquet_tables}}' --parquet-exclude-tables '{{hf_parquet_exclude_tables}}' ${sqlite_arg} ${sensitive_arg}"

etl-publish-hf-dry-run:
  sqlite_arg="--skip-sqlite-gz"; \
  sensitive_arg=""; \
  if [ "{{hf_include_sqlite_gz}}" = "1" ]; then sqlite_arg=""; fi; \
  if [ "{{hf_allow_sensitive_parquet}}" = "1" ]; then sensitive_arg="--allow-sensitive-parquet"; fi; \
  docker compose run --rm --build etl "python3 scripts/publicar_hf_snapshot.py --db {{db_path}} --snapshot-date {{snapshot_date}} --dataset-repo {{hf_dataset_repo_id}} --parquet-compression {{hf_parquet_compression}} --parquet-batch-rows {{hf_parquet_batch_rows}} --parquet-tables '{{hf_parquet_tables}}' --parquet-exclude-tables '{{hf_parquet_exclude_tables}}' --dry-run ${sqlite_arg} ${sensitive_arg}"

parl-extract-congreso-votaciones:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py ingest --db {{db_path}} --source congreso_votaciones --snapshot-date {{snapshot_date}} --strict-network"

parl-extract-congreso-iniciativas:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py ingest --db {{db_path}} --source congreso_iniciativas --snapshot-date {{snapshot_date}} --strict-network"

parl-extract-congreso-intervenciones:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py ingest --db {{db_path}} --source congreso_intervenciones --snapshot-date {{snapshot_date}} --strict-network"

parl-extract-senado-iniciativas:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py ingest --db {{db_path}} --source senado_iniciativas --snapshot-date {{snapshot_date}} --strict-network"

parl-extract-senado-votaciones:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py ingest --db {{db_path}} --source senado_votaciones --snapshot-date {{snapshot_date}} --strict-network"

parl-senado-export-missing-detail-urls:
  mkdir -p "{{senado_manual_detail_dir}}"
  python3 scripts/export_senado_missing_detail_urls.py --db {{db_path}} --mode session --legislature {{senado_detail_legislatures}} --validate --validate-timeout 5 > "{{senado_missing_detail_urls_file}}"
  @echo "OK wrote {{senado_missing_detail_urls_file}}"

parl-senado-export-missing-detail-urls-vote:
  mkdir -p "{{senado_manual_detail_dir}}"
  python3 scripts/export_senado_missing_detail_urls.py --db {{db_path}} --mode vote --legislature {{senado_detail_legislatures}} > "{{senado_missing_detail_urls_file}}"
  @echo "OK wrote {{senado_missing_detail_urls_file}}"

parl-senado-download-missing-details:
  test -f "{{senado_missing_detail_urls_file}}" || (echo "Missing SENADO_MISSING_DETAIL_URLS_FILE: {{senado_missing_detail_urls_file}}" && exit 2)
  mkdir -p "{{senado_manual_detail_dir}}"
  python3 scripts/download_senado_missing_detail_urls_headful.py \
    --urls-file "{{senado_missing_detail_urls_file}}" \
    --out-dir "{{senado_manual_detail_dir}}" \
    --timeout "{{senado_manual_download_timeout}}" \
    --headful-timeout "{{senado_headful_timeout}}" \
    --headful-wait-seconds "{{senado_headful_wait_seconds}}" \
    --channel "{{senado_headful_channel}}" \
    --user-data-dir "{{senado_headful_user_data_dir}}" \
    --cookie "${SENADO_DETAIL_COOKIE:-}" \
    --viewport "{{senado_headful_viewport}}"

parl-backfill-senado-details-manual:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-senado-details --db {{db_path}} --auto --legislature {{senado_detail_legislatures}} --max-events {{senado_detail_max_events}} --max-loops {{senado_detail_max_loops}} --timeout {{senado_detail_timeout}} --detail-workers {{senado_detail_workers}} --snapshot-date {{snapshot_date}} --senado-detail-dir {{senado_manual_detail_dir}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py quality-report --db {{db_path}} --source-ids senado_votaciones --json-out etl/data/published/votaciones-kpis-senado-{{snapshot_date}}.json"

parl-senado-manual-pipeline:
  just parl-senado-export-missing-detail-urls
  just parl-senado-download-missing-details
  just parl-backfill-senado-details-manual

parl-backfill-senado-details:
  senado_detail_arg=""; \
  if [ -n "{{senado_detail_dir}}" ]; then \
    senado_detail_arg=" --senado-detail-dir {{senado_detail_dir}}"; \
  fi; \
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-senado-details --db {{db_path}} --auto --legislature {{senado_detail_legislatures}} --max-events {{senado_detail_max_events}} --max-loops {{senado_detail_max_loops}} --timeout {{senado_detail_timeout}} --detail-workers {{senado_detail_workers}} --snapshot-date {{snapshot_date}}${senado_detail_arg}"
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py quality-report --db {{db_path}} --source-ids senado_votaciones --json-out etl/data/published/votaciones-kpis-senado-{{snapshot_date}}.json"

parl-link-votes:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py link-votes --db {{db_path}}"

parl-backfill-topic-analytics:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-topic-analytics --db {{db_path}} --as-of-date {{snapshot_date}} --taxonomy-seed {{topic_taxonomy_seed}}"

parl-backfill-text-documents:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-text-documents --db {{db_path}} --source-id congreso_intervenciones --limit {{textdoc_limit}} --only-missing --timeout {{textdoc_timeout}}"

parl-backfill-declared-stance:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-declared-stance --db {{db_path}} --source-id congreso_intervenciones --min-auto-confidence {{declared_min_auto_confidence}}"

parl-backfill-declared-positions:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-declared-positions --db {{db_path}} --source-id congreso_intervenciones --as-of-date {{snapshot_date}}"

parl-backfill-combined-positions:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-combined-positions --db {{db_path}} --as-of-date {{snapshot_date}}"

parl-review-queue:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py review-queue --db {{db_path}} --source-id congreso_intervenciones --status pending --limit 50"

parl-review-resolve evidence_id stance:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py review-decision --db {{db_path}} --source-id congreso_intervenciones --evidence-ids {{evidence_id}} --status resolved --final-stance {{stance}} --recompute --as-of-date {{snapshot_date}}"

parl-temas-pipeline:
  just parl-link-votes
  just parl-backfill-topic-analytics
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py ingest --db {{db_path}} --source congreso_intervenciones --snapshot-date {{snapshot_date}} --strict-network"
  just parl-backfill-text-documents
  just parl-backfill-declared-stance
  just parl-backfill-declared-positions
  just parl-backfill-combined-positions

parl-quality-report:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py quality-report --db {{db_path}}"

parl-quality-report-json:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py quality-report --db {{db_path}} --json-out etl/data/published/votaciones-kpis-es-{{snapshot_date}}.json"

parl-quality-report-unmatched:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py quality-report --db {{db_path}} --include-unmatched --unmatched-sample-limit 50"

parl-quality-pipeline:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-member-ids --db {{db_path}} --unmatched-sample-limit 50"
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py link-votes --db {{db_path}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-topic-analytics --db {{db_path}} --as-of-date {{snapshot_date}} --taxonomy-seed {{topic_taxonomy_seed}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py quality-report --db {{db_path}} --enforce-gate --json-out etl/data/published/votaciones-kpis-es-{{snapshot_date}}.json"

parl-publish-votaciones:
  just parl-quality-pipeline
  just etl-publish-votaciones

parl-congreso-votaciones-pipeline:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py ingest --db {{db_path}} --source congreso_votaciones --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-member-ids --db {{db_path}} --source-ids congreso_votaciones --unmatched-sample-limit 50"
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py link-votes --db {{db_path}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py quality-report --db {{db_path}} --source-ids congreso_votaciones --json-out etl/data/published/votaciones-kpis-congreso-{{snapshot_date}}.json"
  docker compose run --rm --build etl "python3 scripts/publicar_votaciones_es.py --db {{db_path}} --snapshot-date {{snapshot_date}} --source-ids congreso_votaciones --backfill-member-ids --include-unmatched --unmatched-sample-limit 100"

congreso-votaciones-download-zips:
  python3 scripts/download_congreso_votaciones_zips.py --max-workers 20 --timeout 30

senado-votaciones-download-xmls:
  python3 scripts/download_senado_votaciones_xmls.py --max-workers 20 --timeout 30

parl-backfill-member-ids:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-member-ids --db {{db_path}}"

parl-backfill-member-ids-dry-run:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-member-ids --db {{db_path}} --dry-run"

etl-smoke-e2e:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py init-db --db {{db_path}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source congreso_diputados --from-file etl/data/raw/samples/congreso_diputados_sample.json --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py ingest --db {{db_path}} --source congreso_votaciones --from-file etl/data/raw/samples/congreso_votaciones_sample.json --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/etl_smoke_e2e.py --db {{db_path}}"

etl-smoke-votes:
  python3 scripts/ingestar_parlamentario_es.py init-db --db {{db_path}}
  python3 scripts/ingestar_parlamentario_es.py ingest --db {{db_path}} --source congreso_votaciones --from-file etl/data/raw/samples/congreso_votaciones_sample.json --snapshot-date {{snapshot_date}} --strict-network
  python3 scripts/ingestar_parlamentario_es.py ingest --db {{db_path}} --source senado_votaciones --from-file etl/data/raw/samples/senado_votaciones_sample.xml --snapshot-date {{snapshot_date}} --strict-network
  python3 scripts/etl_smoke_votes.py --db {{db_path}}

etl-extract-congreso:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source congreso_diputados --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-cortes-aragon:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source cortes_aragon_diputados --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-senado:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source senado_senadores --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-europarl:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source europarl_meps --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-municipal:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source municipal_concejales --snapshot-date {{snapshot_date}} --strict-network --timeout {{municipal_timeout}}"

etl-extract-asamblea-madrid:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_madrid_ocupaciones --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-asamblea-ceuta:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_ceuta_diputados --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-asamblea-melilla:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_melilla_diputados --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-asamblea-extremadura:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_extremadura_diputados --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-asamblea-murcia:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_murcia_diputados --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-jgpa:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source jgpa_diputados --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-parlamento-canarias:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_canarias_diputados --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-parlamento-cantabria:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_cantabria_diputados --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-parlament-balears:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlament_balears_diputats --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-parlamento-larioja:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_larioja_diputados --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-parlament-catalunya:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlament_catalunya_diputats --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-corts-valencianes:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source corts_valencianes_diputats --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-cortes-clm:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source cortes_clm_diputados --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-cortes-cyl:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source cortes_cyl_procuradores --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-parlamento-andalucia:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_andalucia_diputados --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-parlamento-vasco:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_vasco_parlamentarios --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-parlamento-galicia-manual:
  test -d {{galicia_manual_dir}} || (echo "GALICIA_MANUAL_DIR no existe: {{galicia_manual_dir}}. Captura perfiles (Playwright) y exporta la ruta." && exit 2)
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_galicia_deputados --from-file {{galicia_manual_dir}} --snapshot-date {{snapshot_date}}"

etl-extract-parlamento-navarra-manual:
  test -d {{navarra_manual_dir}} || (echo "NAVARRA_MANUAL_DIR no existe: {{navarra_manual_dir}}. Captura perfiles (Playwright) y exporta la ruta." && exit 2)
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_navarra_parlamentarios_forales --from-file {{navarra_manual_dir}} --snapshot-date {{snapshot_date}}"

etl-extract-infoelectoral-descargas:
  docker compose run --rm --build etl "python3 scripts/ingestar_infoelectoral_es.py ingest --db {{db_path}} --source infoelectoral_descargas --snapshot-date {{snapshot_date}} --timeout {{infoelectoral_timeout}} --strict-network"

etl-extract-infoelectoral-procesos:
  docker compose run --rm --build etl "python3 scripts/ingestar_infoelectoral_es.py ingest --db {{db_path}} --source infoelectoral_procesos --snapshot-date {{snapshot_date}} --timeout {{infoelectoral_timeout}} --strict-network"

etl-extract-all:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source congreso_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source cortes_aragon_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source senado_senadores --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source europarl_meps --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source municipal_concejales --snapshot-date {{snapshot_date}} --strict-network --timeout {{municipal_timeout}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_madrid_ocupaciones --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_ceuta_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_melilla_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_extremadura_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_murcia_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source jgpa_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_canarias_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_cantabria_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlament_balears_diputats --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_larioja_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlament_catalunya_diputats --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source corts_valencianes_diputats --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source cortes_clm_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source cortes_cyl_procuradores --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_andalucia_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_vasco_parlamentarios --snapshot-date {{snapshot_date}} --strict-network"

etl-e2e:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py init-db --db {{db_path}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source congreso_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source cortes_aragon_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source senado_senadores --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source europarl_meps --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source municipal_concejales --snapshot-date {{snapshot_date}} --strict-network --timeout {{municipal_timeout}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_madrid_ocupaciones --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_ceuta_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_melilla_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_extremadura_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_murcia_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source jgpa_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_canarias_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_cantabria_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlament_balears_diputats --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_larioja_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlament_catalunya_diputats --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source corts_valencianes_diputats --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source cortes_clm_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source cortes_cyl_procuradores --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_andalucia_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_vasco_parlamentarios --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py stats --db {{db_path}}"

etl-poblacion-municipios-json:
  python3 etl/poblacion_municipios.py --json-out etl/data/published/poblacion_municipios_es.json

etl-poblacion-municipios-2025:
  python3 etl/poblacion_municipios.py --year 2025 --workers 20 --timeout 30 --json-out etl/data/published/poblacion_municipios_es.json

# UI: explorador de grafo (web)
graph-ui:
  DB_PATH={{db_path}} docker compose up --build graph-ui

graph-ui-bg:
  DB_PATH={{db_path}} docker compose up --build -d graph-ui

graph-ui-stop:
  docker compose stop graph-ui
  docker compose rm -f graph-ui

# UI: explorador directo (localhost, sin Docker)
# Single app serving:
# - /explorer -> interfaz clásica
# - /explorer-politico -> vista política jerárquica (radar político)
# - /explorer-sources -> panel de estado de fuentes
explorer:
  DB_PATH={{db_path}} EXPLORER_HOST={{explorer_host}} EXPLORER_PORT={{explorer_port}} python3 scripts/watch_graph_ui_server.py

explorer-watch:
  DB_PATH={{db_path}} EXPLORER_HOST={{explorer_host}} EXPLORER_PORT={{explorer_port}} python3 scripts/watch_graph_ui_server.py

explorer-bg:
  @just explorer-stop >/tmp/vota-explorer-ui-stop.log 2>&1 || true
  DB_PATH={{db_path}} nohup python3 scripts/graph_ui_server.py --db "{{db_path}}" --host {{explorer_host}} --port {{explorer_port}} >/tmp/vota-explorer-ui.log 2>&1 & echo $! >/tmp/vota-explorer-ui.pid
  @echo "Explorer corriendo en http://{{explorer_host}}:{{explorer_port}}/explorer"
  @echo "Explorer político en http://{{explorer_host}}:{{explorer_port}}/explorer-politico"
  @echo "Fuentes en http://{{explorer_host}}:{{explorer_port}}/explorer-sources"
  @echo "Ciudadanía en http://{{explorer_host}}:{{explorer_port}}/citizen"
  @echo "PID guardado en /tmp/vota-explorer-ui.pid"
  @echo "Logs en /tmp/vota-explorer-ui.log"

explorer-bg-watch:
  @just explorer-stop >/tmp/vota-explorer-ui-stop.log 2>&1 || true
  DB_PATH={{db_path}} EXPLORER_HOST={{explorer_host}} EXPLORER_PORT={{explorer_port}} nohup python3 scripts/watch_graph_ui_server.py >/tmp/vota-explorer-ui.log 2>&1 & echo $! >/tmp/vota-explorer-ui.pid
  @echo "Explorer (watch) corriendo en http://{{explorer_host}}:{{explorer_port}}/explorer"
  @echo "Explorer político en http://{{explorer_host}}:{{explorer_port}}/explorer-politico"
  @echo "Fuentes en http://{{explorer_host}}:{{explorer_port}}/explorer-sources"
  @echo "Ciudadanía en http://{{explorer_host}}:{{explorer_port}}/citizen"
  @echo "PID guardado en /tmp/vota-explorer-ui.pid"
  @echo "Logs en /tmp/vota-explorer-ui.log"

explorer-gh-pages-build:
  rm -rf {{gh_pages_dir}}/explorer-sports {{gh_pages_dir}}/explorer-politico {{gh_pages_dir}}/explorer-temas {{gh_pages_dir}}/explorer-sources/data {{gh_pages_dir}}/citizen
  mkdir -p {{gh_pages_dir}}/explorer {{gh_pages_dir}}/graph {{gh_pages_dir}}/graph/data {{gh_pages_dir}}/explorer-politico {{gh_pages_dir}}/explorer-politico/data {{gh_pages_dir}}/explorer-sources {{gh_pages_dir}}/explorer-sources/data {{gh_pages_dir}}/explorer-temas {{gh_pages_dir}}/explorer-temas/data {{gh_pages_dir}}/explorer-votaciones {{gh_pages_dir}}/explorer-votaciones/data {{gh_pages_dir}}/citizen {{gh_pages_dir}}/citizen/data
  cp ui/graph/explorers.html {{gh_pages_dir}}/index.html
  cp ui/graph/explorer.html {{gh_pages_dir}}/explorer/index.html
  cp ui/graph/index.html {{gh_pages_dir}}/graph/index.html
  cp ui/graph/explorer-sports.html {{gh_pages_dir}}/explorer-politico/index.html
  cp ui/graph/explorer-temas.html {{gh_pages_dir}}/explorer-temas/index.html
  cp ui/graph/explorer-votaciones.html {{gh_pages_dir}}/explorer-votaciones/index.html
  cp ui/graph/explorer-sources.html {{gh_pages_dir}}/explorer-sources/index.html
  cp ui/citizen/index.html {{gh_pages_dir}}/citizen/index.html
  cp ui/citizen/concerns_v1.json {{gh_pages_dir}}/citizen/data/concerns_v1.json
  python3 scripts/export_explorer_sports_snapshot.py \
    --db "{{db_path}}" \
    --snapshot-date {{snapshot_date}} \
    --out-dir "{{gh_pages_dir}}/explorer-politico/data"
  python3 scripts/export_graph_snapshot.py \
    --db "{{db_path}}" \
    --limit 350 \
    --include-inactive \
    --out "{{gh_pages_dir}}/graph/data/graph.json"
  python3 scripts/export_explorer_votaciones_snapshot.py \
    --db "{{db_path}}" \
    --limit 200 \
    --out "{{gh_pages_dir}}/explorer-votaciones/data/votes-preview.json"
  python3 scripts/export_explorer_sources_snapshot.py \
    --db "{{db_path}}" \
    --out "{{gh_pages_dir}}/explorer-sources/data/status.json"
  python3 scripts/export_explorer_temas_snapshot.py \
    --db "{{db_path}}" \
    --out "{{gh_pages_dir}}/explorer-temas/data/temas-preview.json"
  python3 scripts/export_citizen_snapshot.py \
    --db "{{db_path}}" \
    --out "{{gh_pages_dir}}/citizen/data/citizen.json" \
    --topic-set-id 1 \
    --computed-method combined \
    --max-bytes 5000000
  python3 scripts/export_citizen_snapshot.py \
    --db "{{db_path}}" \
    --out "{{gh_pages_dir}}/citizen/data/citizen_votes.json" \
    --topic-set-id 1 \
    --computed-method votes \
    --max-bytes 5000000
  python3 scripts/export_citizen_snapshot.py \
    --db "{{db_path}}" \
    --out "{{gh_pages_dir}}/citizen/data/citizen_declared.json" \
    --topic-set-id 1 \
    --computed-method declared \
    --max-bytes 5000000
  python3 scripts/validate_citizen_snapshot.py \
    --path "{{gh_pages_dir}}/citizen/data/citizen.json" \
    --max-bytes 5000000 \
    --strict-grid
  python3 scripts/validate_citizen_snapshot.py \
    --path "{{gh_pages_dir}}/citizen/data/citizen_votes.json" \
    --max-bytes 5000000 \
    --strict-grid
  python3 scripts/validate_citizen_snapshot.py \
    --path "{{gh_pages_dir}}/citizen/data/citizen_declared.json" \
    --max-bytes 5000000 \
    --strict-grid
  cp docs/ideal_sources_say_do.json "{{gh_pages_dir}}/explorer-sources/data/ideal.json"
  @echo "Build GitHub Pages listo en {{gh_pages_dir}}"

explorer-gh-pages-publish:
  remote_url=$(git config --get remote.origin.url); \
  if [ -z "$remote_url" ]; then \
    echo "No se encontró remote.origin.url"; \
    exit 1; \
  fi; \
  just explorer-gh-pages-build; \
  tmp_dir=$(mktemp -d); \
  trap 'rm -rf "$tmp_dir"' EXIT; \
  cp -R {{gh_pages_dir}} "$tmp_dir/site"; \
  cd "$tmp_dir/site"; \
  git init -q; \
  git checkout -b "{{gh_pages_branch}}"; \
  git add .; \
  git commit --allow-empty -m "Publish explorers landing and explorer-politico static snapshot" -q; \
  git remote add origin "$remote_url"; \
  git push -f "$remote_url" "{{gh_pages_branch}}:{{gh_pages_branch}}"

explorer-gh-pages:
  @just explorer-gh-pages-publish

explorer-stop:
  @pid_file=/tmp/vota-explorer-ui.pid; \
  stopped=false; \
  if [ -f "$pid_file" ]; then \
    pid=$(cat $pid_file 2>/dev/null | tr -d " \\t\\n"); \
    if [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1; then \
      kill "$pid" >/dev/null 2>&1 || true; \
      echo "Stopped by pid file: $pid"; \
      stopped=true; \
    fi; \
    rm -f $pid_file; \
  fi; \
  port_pids=$(lsof -n -iTCP:{{explorer_port}} -sTCP:LISTEN -P 2>/dev/null | awk 'NR>1 {print $2}' | sort -u | tr '\n' ' ' | tr -s ' '); \
  if [ -n "$port_pids" ]; then \
    echo "$port_pids" | tr ' ' '\n' | xargs -r kill -9 || true; \
    sleep 0.15; \
    remaining_pids=$(lsof -n -iTCP:{{explorer_port}} -sTCP:LISTEN -P 2>/dev/null | awk 'NR>1 {print $2}' | sort -u | tr '\n' ' ' | tr -s ' '); \
    if [ -n "$remaining_pids" ]; then \
      echo "Still bound to port {{explorer_port}}: $remaining_pids"; \
      echo "Run manually: kill -9 $remaining_pids (or sudo kill -9 ...)"; \
    else \
      echo "Stopped by port bind: $port_pids"; \
      stopped=true; \
    fi; \
  fi; \
  if [ "$stopped" = "false" ]; then \
    if [ -n "$port_pids" ]; then \
      echo "Could not stop the process on port {{explorer_port}} automatically (permissions)."; \
      echo "Try: sudo kill -9 $port_pids"; \
    else \
      echo "No explorer server process found"; \
    fi; \
  fi

explore: explorer

# Legacy aliases (compatibilidad):
graph-explorer: explorer
graph-explorer-bg: explorer-bg
graph-explorer-stop: explorer-stop
explorer-politico: explorer
explorer-politico-bg: explorer-bg
explorer-politico-watch: explorer-watch
explorer-politico-bg-watch: explorer-bg-watch

# Tracker: estado SQL vs checklist
etl-tracker-status:
  docker compose run --rm --build etl "python3 scripts/e2e_tracker_status.py --db {{db_path}} --tracker {{tracker_path}} --waivers {{tracker_waivers_path}}"

# Gate default estricto:
# - fail-on-mismatch (solo mismatches no waived o waivers expiradas)
# - fail-on-done-zero-real
# Usa registro canonico de waivers en docs/etl/mismatch-waivers.json (override via TRACKER_WAIVERS_PATH).
etl-tracker-gate:
  docker compose run --rm --build etl "python3 scripts/e2e_tracker_status.py --db {{db_path}} --tracker {{tracker_path}} --waivers {{tracker_waivers_path}} --fail-on-mismatch --fail-on-done-zero-real"

# Compatibilidad: gate histórico (solo DONE sin red real)
etl-tracker-gate-legacy:
  docker compose run --rm --build etl "python3 scripts/e2e_tracker_status.py --db {{db_path}} --tracker {{tracker_path}} --fail-on-done-zero-real"
