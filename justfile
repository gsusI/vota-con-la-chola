db_path := env_var_or_default("DB_PATH", "etl/data/staging/politicos-es.db")
parliamentary_accountability_db_path := env_var_or_default("PARLIAMENTARY_ACCOUNTABILITY_DB_PATH", "")
initiative_measures_db_path := env_var_or_default("INITIATIVE_MEASURES_DB_PATH", "")
citizen_db_path := env_var_or_default("CITIZEN_DB_PATH", "")
accountability_ledger_db_path := env_var_or_default("ACCOUNTABILITY_LEDGER_DB_PATH", "")
responsibility_explainer_seed_path := env_var_or_default("RESPONSIBILITY_EXPLAINER_SEED_PATH", "etl/data/seeds/responsibility_explainer_cases_seed_v1.json")
responsibility_explainer_reviewed_ledger_dir := env_var_or_default("RESPONSIBILITY_EXPLAINER_REVIEWED_LEDGER_DIR", "etl/data/manual/responsibility_explainer/reviewed_ledger_batches")
dev_fixture_db_path := env_var_or_default("DEV_FIXTURE_DB_PATH", "etl/data/staging/politicos-es.dev.db")
snapshot_date := env_var_or_default("SNAPSHOT_DATE", "2026-02-12")
tracker_path := env_var_or_default("TRACKER_PATH", "docs/etl/e2e-scrape-load-tracker.md")
tracker_waivers_path := env_var_or_default("TRACKER_WAIVERS_PATH", "docs/etl/mismatch-waivers.json")
municipal_timeout := env_var_or_default("MUNICIPAL_TIMEOUT", "240")
live_parl_max_votes := env_var_or_default("LIVE_PARL_MAX_VOTES", "80")
live_parl_max_records := env_var_or_default("LIVE_PARL_MAX_RECORDS", "500")
live_parl_max_files := env_var_or_default("LIVE_PARL_MAX_FILES", "8")
live_parl_congreso_legs := env_var_or_default("LIVE_PARL_CONGRESO_LEGS", "15")
live_parl_senado_legs := env_var_or_default("LIVE_PARL_SENADO_LEGS", "15")
galicia_manual_dir := env_var_or_default("GALICIA_MANUAL_DIR", "etl/data/raw/manual/galicia_deputado_profiles_20260212T141929Z/pages")
navarra_manual_dir := env_var_or_default("NAVARRA_MANUAL_DIR", "etl/data/raw/manual/navarra_persona_profiles_20260212T144911Z/pages")
infoelectoral_timeout := env_var_or_default("INFOELECTORAL_TIMEOUT", "30")
infoelectoral_elected_store_root := env_var_or_default("INFOELECTORAL_ELECTED_STORE_ROOT", "etl/data/object-origin/infoelectoral-elected-officials")
infoelectoral_elected_manifest_root := env_var_or_default("INFOELECTORAL_ELECTED_MANIFEST_ROOT", "etl/data/raw/infoelectoral/elected-officials/manifests")
infoelectoral_elected_report := env_var_or_default("INFOELECTORAL_ELECTED_REPORT", "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/infoelectoral-elected-officials-real-20260811.json")
infoelectoral_elected_min_free_bytes := env_var_or_default("INFOELECTORAL_ELECTED_MIN_FREE_BYTES", "5368709120")
infoelectoral_candidate_pipeline_id := env_var_or_default("INFOELECTORAL_CANDIDATE_PIPELINE_ID", "infoelectoral-candidates-v1")
infoelectoral_candidate_store_root := env_var_or_default("INFOELECTORAL_CANDIDATE_STORE_ROOT", "etl/data/object-origin/restricted/infoelectoral-candidates")
infoelectoral_candidate_local_archive_dir := env_var_or_default("INFOELECTORAL_CANDIDATE_LOCAL_ARCHIVE_DIR", "")
infoelectoral_candidate_report := env_var_or_default("INFOELECTORAL_CANDIDATE_REPORT", "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/infoelectoral-candidate-archive-queue-latest.json")
infoelectoral_candidate_worker_max_items := env_var_or_default("INFOELECTORAL_CANDIDATE_WORKER_MAX_ITEMS", "1")
infoelectoral_candidate_min_free_bytes := env_var_or_default("INFOELECTORAL_CANDIDATE_MIN_FREE_BYTES", "5368709120")
andalucia_execution_source_discovery_out := env_var_or_default("ANDALUCIA_EXECUTION_SOURCE_DISCOVERY_OUT", "etl/data/published/andalucia-2026-execution-source-discovery.json")
andalucia_execution_source_query_timeout := env_var_or_default("ANDALUCIA_EXECUTION_SOURCE_QUERY_TIMEOUT", "10")
andalucia_execution_source_max_topic_terms := env_var_or_default("ANDALUCIA_EXECUTION_SOURCE_MAX_TOPIC_TERMS", "0")
andalucia_execution_source_probe_timeout := env_var_or_default("ANDALUCIA_EXECUTION_SOURCE_PROBE_TIMEOUT", "6")
andalucia_execution_source_max_resource_probes := env_var_or_default("ANDALUCIA_EXECUTION_SOURCE_MAX_RESOURCE_PROBES", "12")
andalucia_delivery_hunt_results_out := env_var_or_default("ANDALUCIA_DELIVERY_HUNT_RESULTS_OUT", "etl/data/published/andalucia-2026-delivery-evidence-hunt-results.json")
andalucia_delivery_hunt_public_out := env_var_or_default("ANDALUCIA_DELIVERY_HUNT_PUBLIC_OUT", "ui/gh-pages-next/public/elecciones/andalucia-2026/data/delivery-evidence-hunt-results.json")
andalucia_delivery_review_drafts_out := env_var_or_default("ANDALUCIA_DELIVERY_REVIEW_DRAFTS_OUT", "etl/data/published/andalucia-2026-delivery-evidence-review-drafts.json")
andalucia_delivery_review_drafts_public_out := env_var_or_default("ANDALUCIA_DELIVERY_REVIEW_DRAFTS_PUBLIC_OUT", "ui/gh-pages-next/public/elecciones/andalucia-2026/data/delivery-evidence-review-drafts.json")
andalucia_delivery_hunt_max_targets := env_var_or_default("ANDALUCIA_DELIVERY_HUNT_MAX_TARGETS", "40")
andalucia_delivery_hunt_rows_per_query := env_var_or_default("ANDALUCIA_DELIVERY_HUNT_ROWS_PER_QUERY", "3")
andalucia_delivery_hunt_timeout := env_var_or_default("ANDALUCIA_DELIVERY_HUNT_TIMEOUT", "12")
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
senado_tail_cookie_file := env_var_or_default("SENADO_TAIL_COOKIE_FILE", "etl/data/raw/manual/senado_iniciativas_cookie_seed_refresh_20260218T201301Z.cookies.json")
senado_tail_burst_limit := env_var_or_default("SENADO_TAIL_BURST_LIMIT", "120")
senado_tail_wide_limit := env_var_or_default("SENADO_TAIL_WIDE_LIMIT", "4000")
senado_tail_timeout := env_var_or_default("SENADO_TAIL_TIMEOUT", "10")
senado_tail_cooldown := env_var_or_default("SENADO_TAIL_COOLDOWN", "60")
senado_tail_active_sleep := env_var_or_default("SENADO_TAIL_ACTIVE_SLEEP", "10")
senado_tail_max_idle_rounds := env_var_or_default("SENADO_TAIL_MAX_IDLE_ROUNDS", "6")
senado_tail_max_rounds := env_var_or_default("SENADO_TAIL_MAX_ROUNDS", "0")
senado_tail_stop_on_uniform_404 := env_var_or_default("SENADO_TAIL_STOP_ON_UNIFORM_404", "1")
senado_tail_archive_fallback := env_var_or_default("SENADO_TAIL_ARCHIVE_FALLBACK", "1")
senado_tail_archive_timeout := env_var_or_default("SENADO_TAIL_ARCHIVE_TIMEOUT", "12")
explorer_host := env_var_or_default("EXPLORER_HOST", "127.0.0.1")
explorer_port := env_var_or_default("EXPLORER_PORT", "9010")
gh_pages_dir := env_var_or_default("STATIC_BUILD_DATA_DIR", "ui/gh-pages-next/.static-data")
gh_pages_remote := env_var_or_default("GH_PAGES_REMOTE", "origin")
gh_pages_branch := env_var_or_default("GH_PAGES_BRANCH", "gh-pages")
gh_pages_tmp_branch := env_var_or_default("GH_PAGES_TMP_BRANCH", "gh-pages-tmp")
gh_pages_next_app_dir := env_var_or_default("GH_PAGES_NEXT_APP_DIR", "ui/gh-pages-next")
gh_pages_next_out_dir := env_var_or_default("GH_PAGES_NEXT_OUT_DIR", "ui/gh-pages-next/out")
gh_pages_next_port := env_var_or_default("GH_PAGES_NEXT_PORT", "3000")
gh_pages_next_container := env_var_or_default("GH_PAGES_NEXT_CONTAINER", "vota-gh-pages-next")
gh_pages_next_docker_image := env_var_or_default("GH_PAGES_NEXT_DOCKER_IMAGE", "node:22-alpine")
gh_pages_next_node_modules_volume := env_var_or_default("GH_PAGES_NEXT_NODE_MODULES_VOLUME", "vota-gh-pages-next-node_modules")
gh_pages_next_next_dir_volume := env_var_or_default("GH_PAGES_NEXT_NEXT_DIR_VOLUME", "vota-gh-pages-next-nextdir")
gh_pages_next_prime_export := env_var_or_default("GH_PAGES_NEXT_PRIME_EXPORT", "1")
gh_pages_reuse_people_exports := env_var_or_default("GH_PAGES_REUSE_PEOPLE_EXPORTS", "1")
gh_pages_next_base_path := env_var_or_default("GH_PAGES_NEXT_BASE_PATH", "")
cloudflare_pages_project := env_var_or_default("CLOUDFLARE_PAGES_PROJECT", "vota-con-la-chola")
cloudflare_pages_max_file_bytes := env_var_or_default("CLOUDFLARE_PAGES_MAX_FILE_BYTES", "25000000")
vote_explainer_limit := env_var_or_default("VOTE_EXPLAINER_LIMIT", "200")
vote_explainer_allow_empty := env_var_or_default("VOTE_EXPLAINER_ALLOW_EMPTY", "0")
topic_taxonomy_seed := env_var_or_default("TOPIC_TAXONOMY_SEED", "etl/data/seeds/topic_taxonomy_es.json")
domain_taxonomy_seed := env_var_or_default("DOMAIN_TAXONOMY_SEED", "docs/domain_taxonomy_es.md")
policy_axes_tier1_seed := env_var_or_default("POLICY_AXES_TIER1_SEED", "docs/codebook_tier1_es.md")
textdoc_limit := env_var_or_default("TEXTDOC_LIMIT", "900")
textdoc_timeout := env_var_or_default("TEXTDOC_TIMEOUT", "25")
initdoc_limit := env_var_or_default("INITDOC_LIMIT", "200")
initdoc_max_per := env_var_or_default("INITDOC_MAX_PER", "3")
initdoc_timeout := env_var_or_default("INITDOC_TIMEOUT", "25")
initdoc_archive_timeout := env_var_or_default("INITDOC_ARCHIVE_TIMEOUT", "12")
initdoc_archive_http_statuses := env_var_or_default("INITDOC_ARCHIVE_HTTP_STATUSES", "404")
initdoc_excerpt_scope := env_var_or_default("INITDOC_EXCERPT_SCOPE", "senado_iniciativas")
initdoc_fetch_scope := env_var_or_default("INITDOC_FETCH_SCOPE", "")
initdoc_status_out := env_var_or_default("INITDOC_STATUS_OUT", "docs/etl/sprints/AI-OPS-27/evidence/initiative_doc_status_latest.json")
initdoc_status_missing_sample_limit := env_var_or_default("INITDOC_STATUS_MISSING_SAMPLE_LIMIT", "20")
initdoc_missing_export_source_ids := env_var_or_default("INITDOC_MISSING_EXPORT_SOURCE_IDS", "senado_iniciativas")
initdoc_missing_export_out := env_var_or_default("INITDOC_MISSING_EXPORT_OUT", "docs/etl/sprints/AI-OPS-61/exports/senado_tail_actionable_latest.csv")
initdoc_missing_export_max_per_initiative := env_var_or_default("INITDOC_MISSING_EXPORT_MAX_PER_INITIATIVE", "1")
senado_waf_profile_out := env_var_or_default("SENADO_WAF_PROFILE_OUT", "docs/etl/sprints/AI-OPS-232/evidence/senado_waf_block_profile_latest.json")
senado_waf_profile_sample_limit := env_var_or_default("SENADO_WAF_PROFILE_SAMPLE_LIMIT", "25")
senado_waf_packets_out := env_var_or_default("SENADO_WAF_PACKETS_OUT", "docs/etl/sprints/AI-OPS-298/evidence/senado_waf_cohort_packets_latest.json")
senado_waf_packets_csv_out := env_var_or_default("SENADO_WAF_PACKETS_CSV_OUT", "docs/etl/sprints/AI-OPS-298/exports/senado_waf_cohort_packets_latest.csv")
senado_waf_packets_cohort_top_n := env_var_or_default("SENADO_WAF_PACKETS_COHORT_TOP_N", "4")
senado_waf_packets_max_urls_per_cohort := env_var_or_default("SENADO_WAF_PACKETS_MAX_URLS_PER_COHORT", "25")
senado_waf_packets_max_total_rows := env_var_or_default("SENADO_WAF_PACKETS_MAX_TOTAL_ROWS", "120")
senado_waf_packets_max_zero_doc_rows := env_var_or_default("SENADO_WAF_PACKETS_MAX_ZERO_DOC_ROWS", "25")
senado_waf_packets_strict_min_packet_rows := env_var_or_default("SENADO_WAF_PACKETS_STRICT_MIN_PACKET_ROWS", "1")
senado_waf_packets_strict_min_cohorts := env_var_or_default("SENADO_WAF_PACKETS_STRICT_MIN_COHORTS", "1")
senado_retry_packet_pool_csv := env_var_or_default("SENADO_RETRY_PACKET_POOL_CSV", "docs/etl/sprints/AI-OPS-332/exports/senado_status403_actionable_pool_latest.csv")
senado_retry_packet_out := env_var_or_default("SENADO_RETRY_PACKET_OUT", "docs/etl/sprints/AI-OPS-332/evidence/senado_status403_fresh_packet_summary_latest.json")
senado_retry_packet_csv_out := env_var_or_default("SENADO_RETRY_PACKET_CSV_OUT", "docs/etl/sprints/AI-OPS-332/exports/senado_status403_fresh_packet_latest.csv")
senado_retry_packet_used_urls_out := env_var_or_default("SENADO_RETRY_PACKET_USED_URLS_OUT", "docs/etl/sprints/AI-OPS-332/evidence/senado_retry_packet_used_urls_latest.txt")
senado_retry_packet_used_refs_out := env_var_or_default("SENADO_RETRY_PACKET_USED_REFS_OUT", "docs/etl/sprints/AI-OPS-332/evidence/senado_retry_packet_used_refs_latest.txt")
senado_retry_packet_glob := env_var_or_default("SENADO_RETRY_PACKET_GLOB", "docs/etl/sprints/AI-OPS-*/exports/*fresh_packet*.csv")
senado_retry_packet_refs_file := env_var_or_default("SENADO_RETRY_PACKET_REFS_FILE", "")
senado_retry_packet_refs_only := env_var_or_default("SENADO_RETRY_PACKET_REFS_ONLY", "0")
senado_retry_packet_max_rows := env_var_or_default("SENADO_RETRY_PACKET_MAX_ROWS", "80")
senado_retry_packet_strict_min_fresh_rows := env_var_or_default("SENADO_RETRY_PACKET_STRICT_MIN_FRESH_ROWS", "1")
senado_archive_gap_retry_json_glob := env_var_or_default("SENADO_ARCHIVE_GAP_RETRY_JSON_GLOB", "docs/etl/sprints/AI-OPS-*/evidence/senado_retry_status404*.json")
senado_archive_gap_out := env_var_or_default("SENADO_ARCHIVE_GAP_OUT", "docs/etl/sprints/AI-OPS-340/evidence/senado_archive_gap_urls_latest.json")
senado_archive_gap_csv_out := env_var_or_default("SENADO_ARCHIVE_GAP_CSV_OUT", "docs/etl/sprints/AI-OPS-340/exports/senado_archive_gap_urls_latest.csv")
senado_archive_gap_strict_min_rows := env_var_or_default("SENADO_ARCHIVE_GAP_STRICT_MIN_ROWS", "1")
senado_cookie_lever_out := env_var_or_default("SENADO_COOKIE_LEVER_OUT", "docs/etl/sprints/AI-OPS-234/evidence/senado_cookie_lever_status_latest.json")
senado_cookie_lever_file := env_var_or_default("SENADO_COOKIE_LEVER_FILE", "etl/data/raw/manual/senado_iniciativas_cookie_seed_refresh_20260218T201301Z.cookies.json")
senado_cookie_lever_max_age_hours := env_var_or_default("SENADO_COOKIE_LEVER_MAX_AGE_HOURS", "24")
senado_cookie_lever_min_domain := env_var_or_default("SENADO_COOKIE_LEVER_MIN_DOMAIN_COOKIES", "1")
senado_cookie_lever_min_persistent := env_var_or_default("SENADO_COOKIE_LEVER_MIN_UNEXPIRED_PERSISTENT_COOKIES", "1")
senado_capture_validity_out := env_var_or_default("SENADO_CAPTURE_VALIDITY_OUT", "docs/etl/sprints/AI-OPS-236/evidence/senado_manual_capture_validity_latest.json")
senado_capture_validity_glob := env_var_or_default("SENADO_CAPTURE_VALIDITY_GLOB", "etl/data/raw/manual/senado*_ai_ops_235_*.meta.json")
senado_capture_validity_min := env_var_or_default("SENADO_CAPTURE_VALIDITY_MIN_CAPTURES", "1")
senado_capture_targets_packet_json := env_var_or_default("SENADO_CAPTURE_TARGETS_PACKET_JSON", "docs/etl/sprints/AI-OPS-298/evidence/senado_waf_cohort_packets_latest.json")
senado_capture_targets_packet_csv := env_var_or_default("SENADO_CAPTURE_TARGETS_PACKET_CSV", "docs/etl/sprints/AI-OPS-298/exports/senado_waf_cohort_packets_latest.csv")
senado_capture_targets_out := env_var_or_default("SENADO_CAPTURE_TARGETS_OUT", "docs/etl/sprints/AI-OPS-299/evidence/senado_manual_capture_targets_latest.json")
senado_capture_targets_csv_out := env_var_or_default("SENADO_CAPTURE_TARGETS_CSV_OUT", "docs/etl/sprints/AI-OPS-299/exports/senado_manual_capture_targets_latest.csv")
senado_capture_targets_seed_url := env_var_or_default("SENADO_CAPTURE_TARGETS_SEED_URL", "https://www.senado.es/")
senado_capture_targets_max_targets := env_var_or_default("SENADO_CAPTURE_TARGETS_MAX_TARGETS", "8")
senado_capture_targets_wait_seconds := env_var_or_default("SENADO_CAPTURE_TARGETS_WAIT_SECONDS", "120")
senado_capture_targets_label_prefix := env_var_or_default("SENADO_CAPTURE_TARGETS_LABEL_PREFIX", "senado_cookie_refresh_ai_ops_299")
senado_capture_targets_strict_min_targets := env_var_or_default("SENADO_CAPTURE_TARGETS_STRICT_MIN_TARGETS", "1")
senado_capture_target_progress_targets_csv := env_var_or_default("SENADO_CAPTURE_TARGET_PROGRESS_TARGETS_CSV", "docs/etl/sprints/AI-OPS-299/exports/senado_manual_capture_targets_latest.csv")
senado_capture_target_progress_captures_glob := env_var_or_default("SENADO_CAPTURE_TARGET_PROGRESS_CAPTURES_GLOB", "etl/data/raw/manual/senado*_cookie_refresh_*.meta.json")
senado_capture_target_progress_out := env_var_or_default("SENADO_CAPTURE_TARGET_PROGRESS_OUT", "docs/etl/sprints/AI-OPS-300/evidence/senado_manual_capture_target_progress_latest.json")
senado_capture_target_progress_csv_out := env_var_or_default("SENADO_CAPTURE_TARGET_PROGRESS_CSV_OUT", "docs/etl/sprints/AI-OPS-300/exports/senado_manual_capture_target_progress_latest.csv")
senado_capture_target_progress_min_covered := env_var_or_default("SENADO_CAPTURE_TARGET_PROGRESS_MIN_COVERED", "1")
senado_capture_target_progress_min_usable := env_var_or_default("SENADO_CAPTURE_TARGET_PROGRESS_MIN_USABLE", "1")
senado_capture_retry_cycle_out := env_var_or_default("SENADO_CAPTURE_RETRY_CYCLE_OUT", "docs/etl/sprints/AI-OPS-301/evidence/senado_manual_capture_retry_cycle_latest.json")
senado_capture_retry_cycle_progress_out := env_var_or_default("SENADO_CAPTURE_RETRY_CYCLE_PROGRESS_OUT", "docs/etl/sprints/AI-OPS-301/evidence/senado_manual_capture_target_progress_latest.json")
senado_capture_retry_cycle_progress_csv_out := env_var_or_default("SENADO_CAPTURE_RETRY_CYCLE_PROGRESS_CSV_OUT", "docs/etl/sprints/AI-OPS-301/exports/senado_manual_capture_target_progress_latest.csv")
senado_capture_retry_cycle_limit_initiatives := env_var_or_default("SENADO_CAPTURE_RETRY_CYCLE_LIMIT_INITIATIVES", "25")
senado_capture_retry_cycle_max_docs_per_initiative := env_var_or_default("SENADO_CAPTURE_RETRY_CYCLE_MAX_DOCS_PER_INITIATIVE", "1")
senado_capture_retry_cycle_timeout := env_var_or_default("SENADO_CAPTURE_RETRY_CYCLE_TIMEOUT", "15")
senado_capture_pending_progress_json := env_var_or_default("SENADO_CAPTURE_PENDING_PROGRESS_JSON", "docs/etl/sprints/AI-OPS-301/evidence/senado_manual_capture_target_progress_latest.json")
senado_capture_pending_progress_csv := env_var_or_default("SENADO_CAPTURE_PENDING_PROGRESS_CSV", "docs/etl/sprints/AI-OPS-301/exports/senado_manual_capture_target_progress_latest.csv")
senado_capture_pending_out := env_var_or_default("SENADO_CAPTURE_PENDING_OUT", "docs/etl/sprints/AI-OPS-302/evidence/senado_manual_capture_pending_targets_latest.json")
senado_capture_pending_csv_out := env_var_or_default("SENADO_CAPTURE_PENDING_CSV_OUT", "docs/etl/sprints/AI-OPS-302/exports/senado_manual_capture_pending_targets_latest.csv")
senado_capture_pending_commands_out := env_var_or_default("SENADO_CAPTURE_PENDING_COMMANDS_OUT", "docs/etl/sprints/AI-OPS-302/exports/senado_manual_capture_pending_targets_commands_latest.sh")
senado_capture_pending_max_targets := env_var_or_default("SENADO_CAPTURE_PENDING_MAX_TARGETS", "8")
senado_capture_iteration_out := env_var_or_default("SENADO_CAPTURE_ITERATION_OUT", "docs/etl/sprints/AI-OPS-303/evidence/senado_manual_capture_iteration_cycle_latest.json")
senado_capture_iteration_retry_out := env_var_or_default("SENADO_CAPTURE_ITERATION_RETRY_OUT", "docs/etl/sprints/AI-OPS-303/evidence/senado_manual_capture_retry_cycle_latest.json")
senado_capture_iteration_progress_out := env_var_or_default("SENADO_CAPTURE_ITERATION_PROGRESS_OUT", "docs/etl/sprints/AI-OPS-303/evidence/senado_manual_capture_target_progress_latest.json")
senado_capture_iteration_progress_csv_out := env_var_or_default("SENADO_CAPTURE_ITERATION_PROGRESS_CSV_OUT", "docs/etl/sprints/AI-OPS-303/exports/senado_manual_capture_target_progress_latest.csv")
senado_capture_iteration_pending_out := env_var_or_default("SENADO_CAPTURE_ITERATION_PENDING_OUT", "docs/etl/sprints/AI-OPS-303/evidence/senado_manual_capture_pending_targets_latest.json")
senado_capture_iteration_pending_csv_out := env_var_or_default("SENADO_CAPTURE_ITERATION_PENDING_CSV_OUT", "docs/etl/sprints/AI-OPS-303/exports/senado_manual_capture_pending_targets_latest.csv")
senado_capture_iteration_pending_commands_out := env_var_or_default("SENADO_CAPTURE_ITERATION_PENDING_COMMANDS_OUT", "docs/etl/sprints/AI-OPS-303/exports/senado_manual_capture_pending_targets_commands_latest.sh")
senado_capture_iteration_pending_max_targets := env_var_or_default("SENADO_CAPTURE_ITERATION_PENDING_MAX_TARGETS", "0")
senado_capture_iteration_pending_wait_seconds := env_var_or_default("SENADO_CAPTURE_ITERATION_PENDING_WAIT_SECONDS", "120")
senado_capture_iteration_strict_min_pending_reduction := env_var_or_default("SENADO_CAPTURE_ITERATION_STRICT_MIN_PENDING_REDUCTION", "0")
initdoc_actionable_contract_source_ids := env_var_or_default("INITDOC_ACTIONABLE_CONTRACT_SOURCE_IDS", "senado_iniciativas")
initdoc_actionable_contract_out := env_var_or_default("INITDOC_ACTIONABLE_CONTRACT_OUT", "docs/etl/sprints/AI-OPS-63/evidence/initdoc_actionable_tail_contract_latest.json")
initdoc_actionable_digest_out := env_var_or_default("INITDOC_ACTIONABLE_DIGEST_OUT", "docs/etl/sprints/AI-OPS-64/evidence/initdoc_actionable_tail_digest_latest.json")
initdoc_actionable_digest_max_missing := env_var_or_default("INITDOC_ACTIONABLE_DIGEST_MAX_MISSING", "0")
initdoc_actionable_digest_max_missing_pct := env_var_or_default("INITDOC_ACTIONABLE_DIGEST_MAX_MISSING_PCT", "0")
initdoc_actionable_heartbeat_path := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_PATH", "docs/etl/runs/initdoc_actionable_tail_digest_heartbeat.jsonl")
initdoc_actionable_heartbeat_out := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_OUT", "docs/etl/sprints/AI-OPS-66/evidence/initdoc_actionable_tail_digest_heartbeat_latest.json")
initdoc_actionable_heartbeat_window_last := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_WINDOW_LAST", "20")
initdoc_actionable_heartbeat_window_max_failed := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_WINDOW_MAX_FAILED", "0")
initdoc_actionable_heartbeat_window_max_failed_rate_pct := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_WINDOW_MAX_FAILED_RATE_PCT", "0")
initdoc_actionable_heartbeat_window_max_degraded := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_WINDOW_MAX_DEGRADED", "0")
initdoc_actionable_heartbeat_window_max_degraded_rate_pct := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_WINDOW_MAX_DEGRADED_RATE_PCT", "0")
initdoc_actionable_heartbeat_window_out := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-66/evidence/initdoc_actionable_tail_digest_heartbeat_window_latest.json")
initdoc_actionable_heartbeat_compact_path := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_PATH", "docs/etl/runs/initdoc_actionable_tail_digest_heartbeat.compacted.jsonl")
initdoc_actionable_heartbeat_compact_recent := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_RECENT", "20")
initdoc_actionable_heartbeat_compact_mid_span := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_MID_SPAN", "100")
initdoc_actionable_heartbeat_compact_mid_every := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_MID_EVERY", "5")
initdoc_actionable_heartbeat_compact_old_every := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_OLD_EVERY", "20")
initdoc_actionable_heartbeat_compact_min_raw := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_MIN_RAW", "25")
initdoc_actionable_heartbeat_compact_out := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_OUT", "docs/etl/sprints/AI-OPS-67/evidence/initdoc_actionable_tail_digest_heartbeat_compaction_latest.json")
initdoc_actionable_heartbeat_compact_window_last := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_WINDOW_LAST", "20")
initdoc_actionable_heartbeat_compact_window_out := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-67/evidence/initdoc_actionable_tail_digest_heartbeat_compaction_window_latest.json")
initdoc_actionable_heartbeat_compact_window_digest_out := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_WINDOW_DIGEST_OUT", "docs/etl/sprints/AI-OPS-68/evidence/initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_latest.json")
initdoc_actionable_heartbeat_compact_window_digest_heartbeat_path := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_PATH", "docs/etl/runs/initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat.jsonl")
initdoc_actionable_heartbeat_compact_window_digest_heartbeat_out := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_OUT", "docs/etl/sprints/AI-OPS-69/evidence/initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_latest.json")
initdoc_actionable_heartbeat_compact_window_digest_heartbeat_window_last := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_LAST", "20")
initdoc_actionable_heartbeat_compact_window_digest_heartbeat_window_max_failed := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_FAILED", "0")
initdoc_actionable_heartbeat_compact_window_digest_heartbeat_window_max_failed_rate_pct := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_FAILED_RATE_PCT", "0")
initdoc_actionable_heartbeat_compact_window_digest_heartbeat_window_max_degraded := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_DEGRADED", "0")
initdoc_actionable_heartbeat_compact_window_digest_heartbeat_window_max_degraded_rate_pct := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_DEGRADED_RATE_PCT", "0")
initdoc_actionable_heartbeat_compact_window_digest_heartbeat_window_out := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-69/evidence/initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_window_latest.json")
initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_path := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_PATH", "docs/etl/runs/initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat.compacted.jsonl")
initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_recent := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_RECENT", "20")
initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_mid_span := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_MID_SPAN", "100")
initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_mid_every := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_MID_EVERY", "5")
initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_old_every := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_OLD_EVERY", "20")
initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_min_raw := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_MIN_RAW", "25")
initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_out := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_OUT", "docs/etl/sprints/AI-OPS-70/evidence/initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction_latest.json")
initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_window_last := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_LAST", "20")
initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_window_out := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-70/evidence/initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_latest.json")
initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_window_digest_out := env_var_or_default("INITDOC_ACTIONABLE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_OUT", "docs/etl/sprints/AI-OPS-71/evidence/initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_latest.json")
initdoc_extract_scope := env_var_or_default("INITDOC_EXTRACT_SCOPE", "congreso_iniciativas,senado_iniciativas")
initdoc_extract_limit := env_var_or_default("INITDOC_EXTRACT_LIMIT", "0")
initdoc_extract_out := env_var_or_default("INITDOC_EXTRACT_OUT", "docs/etl/sprints/AI-OPS-28/evidence/initdoc_extractions_latest.json")
initdoc_extract_review_limit := env_var_or_default("INITDOC_EXTRACT_REVIEW_LIMIT", "0")
initdoc_extract_review_out := env_var_or_default("INITDOC_EXTRACT_REVIEW_OUT", "docs/etl/sprints/AI-OPS-28/exports/initdoc_extraction_review_queue.csv")
initdoc_extract_review_apply_file := env_var_or_default("INITDOC_EXTRACT_REVIEW_APPLY_FILE", "")
initdoc_extract_review_apply_out := env_var_or_default("INITDOC_EXTRACT_REVIEW_APPLY_OUT", "docs/etl/sprints/AI-OPS-28/evidence/initdoc_extraction_review_apply_latest.json")
initdoc_extract_review_label_studio_out := env_var_or_default("INITDOC_EXTRACT_REVIEW_LABEL_STUDIO_OUT", "docs/etl/sprints/AI-OPS-28/exports/initdoc_extraction_review_queue.label_studio.json")
initdoc_extract_review_label_studio_config_out := env_var_or_default("INITDOC_EXTRACT_REVIEW_LABEL_STUDIO_CONFIG_OUT", "docs/etl/sprints/AI-OPS-28/exports/initdoc_extraction_review_label_studio_config.xml")
initdoc_extract_review_label_studio_apply_file := env_var_or_default("INITDOC_EXTRACT_REVIEW_LABEL_STUDIO_APPLY_FILE", "")
senado_detail_links_limit := env_var_or_default("SENADO_DETAIL_LINKS_LIMIT", "0")
doc_analysis_limit := env_var_or_default("DOC_ANALYSIS_LIMIT", "0")
doc_analysis_out := env_var_or_default("DOC_ANALYSIS_OUT", "docs/etl/sprints/AI-OPS-27/exports/senado_pdf_analysis_queue.csv")
text_extraction_queue_source_ids := env_var_or_default("TEXT_EXTRACTION_QUEUE_SOURCE_IDS", "parl_initiative_docs,congreso_intervenciones,programas_partidos")
text_extraction_queue_formats := env_var_or_default("TEXT_EXTRACTION_QUEUE_FORMATS", "pdf,html,xml")
text_extraction_queue_limit := env_var_or_default("TEXT_EXTRACTION_QUEUE_LIMIT", "0")
text_extraction_queue_out := env_var_or_default("TEXT_EXTRACTION_QUEUE_OUT", "docs/etl/sprints/AI-OPS-28/exports/text_extraction_queue.csv")
text_extraction_queue_summary_out := env_var_or_default("TEXT_EXTRACTION_QUEUE_SUMMARY_OUT", "docs/etl/sprints/AI-OPS-28/evidence/text_extraction_queue_summary.json")
scale_queue_enqueue_batch_size := env_var_or_default("SCALE_QUEUE_ENQUEUE_BATCH_SIZE", "5000")
scale_queue_claim_batch_size := env_var_or_default("SCALE_QUEUE_CLAIM_BATCH_SIZE", "2000")
scale_readiness_report_out := env_var_or_default("SCALE_READINESS_REPORT_OUT", "etl/data/published/scale-readiness-latest.json")
scale_member_vote_snapshot := env_var_or_default("SCALE_MEMBER_VOTE_SNAPSHOT", "etl/data/published/votaciones-es-2026-02-25.json")
scale_member_vote_audit_out := env_var_or_default("SCALE_MEMBER_VOTE_AUDIT_OUT", "etl/data/published/member-vote-million-audit-latest.json")
scale_vote_db_audit_out := env_var_or_default("SCALE_VOTE_DB_AUDIT_OUT", "etl/data/published/vote-database-audit-latest.json")
scale_vote_db_shard_root := env_var_or_default("SCALE_VOTE_DB_SHARD_ROOT", "etl/data/derived/vote-db-shards")
scale_vote_db_shard_manifest_out := env_var_or_default("SCALE_VOTE_DB_SHARD_MANIFEST_OUT", "etl/data/published/vote-database-shard-manifest-latest.json")
scale_vote_db_shard_validation_out := env_var_or_default("SCALE_VOTE_DB_SHARD_VALIDATION_OUT", "etl/data/published/vote-database-shard-validation-latest.json")
scale_semantic_member_vote_root := env_var_or_default("SCALE_SEMANTIC_MEMBER_VOTE_ROOT", "etl/data/derived/semantic-member-votes")
scale_semantic_member_vote_manifest_out := env_var_or_default("SCALE_SEMANTIC_MEMBER_VOTE_MANIFEST_OUT", "etl/data/published/member-vote-semantic-partition-manifest-latest.json")
scale_semantic_member_vote_validation_out := env_var_or_default("SCALE_SEMANTIC_MEMBER_VOTE_VALIDATION_OUT", "etl/data/published/member-vote-semantic-partition-validation-latest.json")
scale_semantic_previous_manifest := env_var_or_default("SCALE_SEMANTIC_PREVIOUS_MANIFEST", "")
scale_semantic_previous_root := env_var_or_default("SCALE_SEMANTIC_PREVIOUS_ROOT", "")
scale_semantic_vote_audit := env_var_or_default("SCALE_SEMANTIC_VOTE_AUDIT", "")
scale_semantic_min_rows := env_var_or_default("SCALE_SEMANTIC_MIN_ROWS", "1")
scale_semantic_row_group_rows := env_var_or_default("SCALE_SEMANTIC_ROW_GROUP_ROWS", "25000")
scale_semantic_max_file_rows := env_var_or_default("SCALE_SEMANTIC_MAX_FILE_ROWS", "100000")
scale_semantic_ledger_root := env_var_or_default("SCALE_SEMANTIC_LEDGER_ROOT", "etl/data/derived/semantic-accountability-ledger")
scale_semantic_ledger_manifest_out := env_var_or_default("SCALE_SEMANTIC_LEDGER_MANIFEST_OUT", "etl/data/published/accountability-ledger-semantic-partition-manifest-latest.json")
scale_semantic_ledger_validation_out := env_var_or_default("SCALE_SEMANTIC_LEDGER_VALIDATION_OUT", "etl/data/published/accountability-ledger-semantic-partition-validation-latest.json")
scale_semantic_ledger_previous_manifest := env_var_or_default("SCALE_SEMANTIC_LEDGER_PREVIOUS_MANIFEST", "")
scale_semantic_ledger_previous_root := env_var_or_default("SCALE_SEMANTIC_LEDGER_PREVIOUS_ROOT", "")
scale_semantic_ledger_min_rows := env_var_or_default("SCALE_SEMANTIC_LEDGER_MIN_ROWS", "100000")
scale_semantic_actor_root := env_var_or_default("SCALE_SEMANTIC_ACTOR_ROOT", "etl/data/derived/semantic-actor-mandates")
scale_semantic_actor_manifest_out := env_var_or_default("SCALE_SEMANTIC_ACTOR_MANIFEST_OUT", "etl/data/published/actor-mandate-semantic-partition-manifest-latest.json")
scale_semantic_actor_validation_out := env_var_or_default("SCALE_SEMANTIC_ACTOR_VALIDATION_OUT", "etl/data/published/actor-mandate-semantic-partition-validation-latest.json")
scale_semantic_actor_incremental_manifest_out := env_var_or_default("SCALE_SEMANTIC_ACTOR_INCREMENTAL_MANIFEST_OUT", "etl/data/published/actor-mandate-semantic-partition-incremental-latest.json")
scale_semantic_actor_incremental_validation_out := env_var_or_default("SCALE_SEMANTIC_ACTOR_INCREMENTAL_VALIDATION_OUT", "etl/data/published/actor-mandate-semantic-partition-validation-incremental-latest.json")
scale_semantic_actor_previous_manifest := env_var_or_default("SCALE_SEMANTIC_ACTOR_PREVIOUS_MANIFEST", "")
scale_semantic_actor_previous_root := env_var_or_default("SCALE_SEMANTIC_ACTOR_PREVIOUS_ROOT", "")
scale_semantic_actor_min_rows := env_var_or_default("SCALE_SEMANTIC_ACTOR_MIN_ROWS", "70000")
scale_semantic_candidate_root := env_var_or_default("SCALE_SEMANTIC_CANDIDATE_ROOT", "etl/data/derived/semantic-candidate-occurrences")
scale_semantic_candidate_manifest_out := env_var_or_default("SCALE_SEMANTIC_CANDIDATE_MANIFEST_OUT", "etl/data/published/candidate-occurrence-semantic-partition-manifest-latest.json")
scale_semantic_candidate_validation_out := env_var_or_default("SCALE_SEMANTIC_CANDIDATE_VALIDATION_OUT", "etl/data/published/candidate-occurrence-semantic-partition-validation-latest.json")
scale_semantic_candidate_previous_manifest := env_var_or_default("SCALE_SEMANTIC_CANDIDATE_PREVIOUS_MANIFEST", "")
scale_semantic_candidate_previous_root := env_var_or_default("SCALE_SEMANTIC_CANDIDATE_PREVIOUS_ROOT", "")
scale_semantic_candidate_min_rows := env_var_or_default("SCALE_SEMANTIC_CANDIDATE_MIN_ROWS", "1")
scale_semantic_money_root := env_var_or_default("SCALE_SEMANTIC_MONEY_ROOT", "etl/data/derived/semantic-public-money")
scale_semantic_money_manifest_out := env_var_or_default("SCALE_SEMANTIC_MONEY_MANIFEST_OUT", "etl/data/published/public-money-semantic-partition-manifest-latest.json")
scale_semantic_money_validation_out := env_var_or_default("SCALE_SEMANTIC_MONEY_VALIDATION_OUT", "etl/data/published/public-money-semantic-partition-validation-latest.json")
scale_semantic_money_previous_manifest := env_var_or_default("SCALE_SEMANTIC_MONEY_PREVIOUS_MANIFEST", "")
scale_semantic_money_previous_root := env_var_or_default("SCALE_SEMANTIC_MONEY_PREVIOUS_ROOT", "")
scale_semantic_money_min_rows := env_var_or_default("SCALE_SEMANTIC_MONEY_MIN_ROWS", "10")
scale_semantic_indicator_root := env_var_or_default("SCALE_SEMANTIC_INDICATOR_ROOT", "etl/data/derived/semantic-indicator-observations")
scale_semantic_indicator_manifest_out := env_var_or_default("SCALE_SEMANTIC_INDICATOR_MANIFEST_OUT", "etl/data/published/indicator-observation-semantic-partition-manifest-latest.json")
scale_semantic_indicator_validation_out := env_var_or_default("SCALE_SEMANTIC_INDICATOR_VALIDATION_OUT", "etl/data/published/indicator-observation-semantic-partition-validation-latest.json")
scale_semantic_indicator_previous_manifest := env_var_or_default("SCALE_SEMANTIC_INDICATOR_PREVIOUS_MANIFEST", "")
scale_semantic_indicator_previous_root := env_var_or_default("SCALE_SEMANTIC_INDICATOR_PREVIOUS_ROOT", "")
scale_semantic_indicator_min_rows := env_var_or_default("SCALE_SEMANTIC_INDICATOR_MIN_ROWS", "1")
eurostat_indicator_registry := env_var_or_default("EUROSTAT_INDICATOR_REGISTRY", "etl/data/seeds/eurostat_indicator_registry_v1.json")
eurostat_indicator_db := env_var_or_default("EUROSTAT_INDICATOR_DB", "etl/data/staging/eurostat-indicators-real-s2.db")
eurostat_indicator_pipeline_id := env_var_or_default("EUROSTAT_INDICATOR_PIPELINE_ID", "eurostat-indicators-real-s2")
eurostat_indicator_raw_root := env_var_or_default("EUROSTAT_INDICATOR_RAW_ROOT", "etl/data/object-origin/eurostat-indicators")
eurostat_indicator_ca_bundle := env_var_or_default("EUROSTAT_INDICATOR_CA_BUNDLE", "")
eurostat_indicator_worker_max_items := env_var_or_default("EUROSTAT_INDICATOR_WORKER_MAX_ITEMS", "4")
eurostat_indicator_source_record_batch_size := env_var_or_default("EUROSTAT_INDICATOR_SOURCE_RECORD_BATCH_SIZE", "1000")
eurostat_indicator_acquisition_report := env_var_or_default("EUROSTAT_INDICATOR_ACQUISITION_REPORT", "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/eurostat-indicator-real-s2-acquisition.json")
eurostat_indicator_semantic_root := env_var_or_default("EUROSTAT_INDICATOR_SEMANTIC_ROOT", "etl/data/derived/eurostat-indicator-real-s2")
eurostat_indicator_semantic_replay_root := env_var_or_default("EUROSTAT_INDICATOR_SEMANTIC_REPLAY_ROOT", "etl/data/derived/eurostat-indicator-real-s2-replay")
eurostat_indicator_semantic_manifest := env_var_or_default("EUROSTAT_INDICATOR_SEMANTIC_MANIFEST", "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/eurostat-indicator-real-s2-semantic-manifest.json")
eurostat_indicator_semantic_validation := env_var_or_default("EUROSTAT_INDICATOR_SEMANTIC_VALIDATION", "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/eurostat-indicator-real-s2-semantic-validation.json")
eurostat_indicator_incremental_manifest := env_var_or_default("EUROSTAT_INDICATOR_INCREMENTAL_MANIFEST", "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/eurostat-indicator-real-s2-incremental-manifest.json")
eurostat_indicator_incremental_validation := env_var_or_default("EUROSTAT_INDICATOR_INCREMENTAL_VALIDATION", "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/eurostat-indicator-real-s2-incremental-validation.json")
bdns_bulk_pipeline_id := env_var_or_default("BDNS_BULK_PIPELINE_ID", "bdns-concessions-scale")
bdns_bulk_raw_root := env_var_or_default("BDNS_BULK_RAW_ROOT", "etl/data/raw/bdns/concessions-pages")
bdns_bulk_page_size := env_var_or_default("BDNS_BULK_PAGE_SIZE", "1000")
bdns_bulk_max_pages := env_var_or_default("BDNS_BULK_MAX_PAGES", "0")
bdns_bulk_date_from := env_var_or_default("BDNS_BULK_DATE_FROM", "2026-01-01")
bdns_bulk_date_to := env_var_or_default("BDNS_BULK_DATE_TO", snapshot_date)
bdns_bulk_target_records := env_var_or_default("BDNS_BULK_TARGET_RECORDS", "1000000")
bdns_bulk_max_partitions := env_var_or_default("BDNS_BULK_MAX_PARTITIONS", "366")
bdns_bulk_max_pages_per_partition := env_var_or_default("BDNS_BULK_MAX_PAGES_PER_PARTITION", "100")
bdns_bulk_expand_max_pages_per_partition := env_var_or_default("BDNS_BULK_EXPAND_MAX_PAGES_PER_PARTITION", "0")
bdns_bulk_workers := env_var_or_default("BDNS_BULK_WORKERS", "2")
bdns_bulk_claim_size := env_var_or_default("BDNS_BULK_CLAIM_SIZE", "4")
bdns_bulk_min_free_bytes := env_var_or_default("BDNS_BULK_MIN_FREE_BYTES", "10737418240")
bdns_bulk_sqlite_reserve_multiplier := env_var_or_default("BDNS_BULK_SQLITE_RESERVE_MULTIPLIER", "2.0")
bdns_bulk_request_interval := env_var_or_default("BDNS_BULK_REQUEST_INTERVAL", "2.0")
bdns_bulk_failure_window := env_var_or_default("BDNS_BULK_FAILURE_WINDOW", "20")
bdns_bulk_version_backfill_max_pages := env_var_or_default("BDNS_BULK_VERSION_BACKFILL_MAX_PAGES", "0")
bdns_bulk_enqueue_report := env_var_or_default("BDNS_BULK_ENQUEUE_REPORT", "etl/data/published/bdns-concessions-bulk-enqueue-latest.json")
bdns_bulk_run_report := env_var_or_default("BDNS_BULK_RUN_REPORT", "etl/data/published/bdns-concessions-bulk-run-latest.json")
placsp_bulk_db := env_var_or_default("PLACSP_BULK_DB", "etl/data/staging/placsp-contracts-real-s1-20260811.db")
placsp_bulk_pipeline_id := env_var_or_default("PLACSP_BULK_PIPELINE_ID", "placsp-contracts-real-s1-20260811")
placsp_bulk_latest_pipeline_id := env_var_or_default("PLACSP_BULK_LATEST_PIPELINE_ID", "placsp-contracts-real-s1-2025q2-20260811")
placsp_bulk_raw_root := env_var_or_default("PLACSP_BULK_RAW_ROOT", "etl/data/object-origin/placsp-contracts")
placsp_bulk_ca_bundle := env_var_or_default("PLACSP_BULK_CA_BUNDLE", "")
placsp_bulk_min_free_bytes := env_var_or_default("PLACSP_BULK_MIN_FREE_BYTES", "10737418240")
placsp_bulk_snapshot_date := env_var_or_default("PLACSP_BULK_SNAPSHOT_DATE", "2025-03-31")
placsp_bulk_semantic_snapshot_date := env_var_or_default("PLACSP_BULK_SEMANTIC_SNAPSHOT_DATE", "2025-06-30")
placsp_bulk_replay_snapshot_date := env_var_or_default("PLACSP_BULK_REPLAY_SNAPSHOT_DATE", "2025-07-01")
placsp_bulk_archive_args := env_var_or_default("PLACSP_BULK_ARCHIVE_ARGS", "--archive 202501=https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3_202501.zip --archive 202502=https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3_202502.zip --archive 202503=https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3_202503.zip")
placsp_bulk_enqueue_report := env_var_or_default("PLACSP_BULK_ENQUEUE_REPORT", "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-real-s1-enqueue.json")
placsp_bulk_archive_report := env_var_or_default("PLACSP_BULK_ARCHIVE_REPORT", "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-real-s1-archive-worker.json")
placsp_bulk_run_report := env_var_or_default("PLACSP_BULK_RUN_REPORT", "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-real-s1-run.json")
placsp_bulk_corpus_report := env_var_or_default("PLACSP_BULK_CORPUS_REPORT", "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-real-2025q2-run.json")
placsp_bulk_semantic_root := env_var_or_default("PLACSP_BULK_SEMANTIC_ROOT", "etl/data/derived/placsp-contracts-real-2025h1-v4")
placsp_bulk_semantic_replay_root := env_var_or_default("PLACSP_BULK_SEMANTIC_REPLAY_ROOT", "etl/data/derived/placsp-contracts-real-2025h1-v4-replay")
placsp_bulk_semantic_manifest := env_var_or_default("PLACSP_BULK_SEMANTIC_MANIFEST", "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-real-2025h1-semantic-manifest.json")
placsp_bulk_semantic_validation := env_var_or_default("PLACSP_BULK_SEMANTIC_VALIDATION", "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-real-2025h1-semantic-validation.json")
placsp_bulk_incremental_manifest := env_var_or_default("PLACSP_BULK_INCREMENTAL_MANIFEST", "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-real-2025h1-semantic-incremental-manifest.json")
placsp_bulk_incremental_validation := env_var_or_default("PLACSP_BULK_INCREMENTAL_VALIDATION", "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-real-2025h1-semantic-incremental-validation.json")
placsp_document_pipeline_id := env_var_or_default("PLACSP_DOCUMENT_PIPELINE_ID", "placsp_document_fetch_real_s1")
placsp_document_raw_root := env_var_or_default("PLACSP_DOCUMENT_RAW_ROOT", "etl/data/object-origin/placsp-contract-documents")
placsp_document_worker_max_items := env_var_or_default("PLACSP_DOCUMENT_WORKER_MAX_ITEMS", "20")
placsp_document_enqueue_report := env_var_or_default("PLACSP_DOCUMENT_ENQUEUE_REPORT", "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-real-2025h1-document-fetch-enqueue.json")
placsp_document_worker_report := env_var_or_default("PLACSP_DOCUMENT_WORKER_REPORT", "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-document-fetch-sample.json")
placsp_integrity_report := env_var_or_default("PLACSP_INTEGRITY_REPORT", "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-real-2025h1-integrity-signal-run.json")
placsp_history_pipeline_id := env_var_or_default("PLACSP_HISTORY_PIPELINE_ID", "placsp-contracts-official-history-2012-20260811")
placsp_history_snapshot_date := env_var_or_default("PLACSP_HISTORY_SNAPSHOT_DATE", "2026-08-11")
placsp_history_catalog_report := env_var_or_default("PLACSP_HISTORY_CATALOG_REPORT", "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-official-archive-catalog-20260811.json")
placsp_history_enqueue_report := env_var_or_default("PLACSP_HISTORY_ENQUEUE_REPORT", "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-official-history-enqueue-20260811.json")
placsp_history_min_free_bytes := env_var_or_default("PLACSP_HISTORY_MIN_FREE_BYTES", "107374182400")
placsp_history_archive_max_items := env_var_or_default("PLACSP_HISTORY_ARCHIVE_MAX_ITEMS", "1")
placsp_history_member_max_items := env_var_or_default("PLACSP_HISTORY_MEMBER_MAX_ITEMS", "10")
placsp_history_storage_report := env_var_or_default("PLACSP_HISTORY_STORAGE_REPORT", "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-official-history-storage-preflight-20260811.json")
placsp_history_member_report := env_var_or_default("PLACSP_HISTORY_MEMBER_REPORT", "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-official-history-member-worker-20260811.json")
scale_document_pipeline_evidence := env_var_or_default("SCALE_DOCUMENT_PIPELINE_EVIDENCE", "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/document-pipeline-scale-run.json")
scale_document_format_inventory := env_var_or_default("SCALE_DOCUMENT_FORMAT_INVENTORY", "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-format-inventory.json")
scale_pdf_ocr_routing_benchmark := env_var_or_default("SCALE_PDF_OCR_ROUTING_BENCHMARK", "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/pdf-ocr-routing-benchmark.json")
scale_document_workers := env_var_or_default("SCALE_DOCUMENT_WORKERS", "8")
scale_member_vote_shard_root := env_var_or_default("SCALE_MEMBER_VOTE_SHARD_ROOT", "etl/data/derived/member-vote-shards")
scale_member_vote_shard_manifest_out := env_var_or_default("SCALE_MEMBER_VOTE_SHARD_MANIFEST_OUT", "etl/data/published/member-vote-shard-manifest-latest.json")
scale_member_vote_shard_validation_out := env_var_or_default("SCALE_MEMBER_VOTE_SHARD_VALIDATION_OUT", "etl/data/published/member-vote-shard-validation-latest.json")
scale_member_vote_source_provenance_overrides := env_var_or_default("SCALE_MEMBER_VOTE_SOURCE_PROVENANCE_OVERRIDES", "etl/data/raw/samples/congreso_votaciones_sample.json.source.json")
scale_queue_pipeline_id := env_var_or_default("SCALE_QUEUE_PIPELINE_ID", "")
scale_queue_health_out := env_var_or_default("SCALE_QUEUE_HEALTH_OUT", "etl/data/published/pipeline-work-queue-health-latest.json")
object_store_backend := env_var_or_default("OBJECT_STORE_BACKEND", "filesystem")
object_store_filesystem_root := env_var_or_default("OBJECT_STORE_FILESYSTEM_ROOT", "etl/data/object-origin")
object_store_manifest_out := env_var_or_default("OBJECT_STORE_MANIFEST_OUT", "etl/data/manifests/content-objects-latest.jsonl")
object_store_replication_report_out := env_var_or_default("OBJECT_STORE_REPLICATION_REPORT_OUT", "etl/data/published/content-object-replication-latest.json")
object_store_restore_report_out := env_var_or_default("OBJECT_STORE_RESTORE_REPORT_OUT", "etl/data/published/object-store-restore-drill-latest.json")
object_store_replication_limit := env_var_or_default("OBJECT_STORE_REPLICATION_LIMIT", "0")
object_store_replication_workers := env_var_or_default("OBJECT_STORE_REPLICATION_WORKERS", "8")
object_store_restore_sample_size := env_var_or_default("OBJECT_STORE_RESTORE_SAMPLE_SIZE", "100")
object_store_restore_workers := env_var_or_default("OBJECT_STORE_RESTORE_WORKERS", "8")
object_store_restore_all := env_var_or_default("OBJECT_STORE_RESTORE_ALL", "0")
object_store_restore_min_free_bytes := env_var_or_default("OBJECT_STORE_RESTORE_MIN_FREE_BYTES", "10737418240")
integrity_signal_threshold_eur := env_var_or_default("INTEGRITY_SIGNAL_THRESHOLD_EUR", "15000")
integrity_signal_min_records := env_var_or_default("INTEGRITY_SIGNAL_MIN_RECORDS", "3")
integrity_signal_max_signals := env_var_or_default("INTEGRITY_SIGNAL_MAX_SIGNALS", "0")
integrity_signal_internal_report_out := env_var_or_default("INTEGRITY_SIGNAL_INTERNAL_REPORT_OUT", "tmp/integrity-signals/procurement-latest.json")
integrity_signal_public_out := env_var_or_default("INTEGRITY_SIGNAL_PUBLIC_OUT", "etl/data/published/integrity-signals-latest.json")
document_fetch_workers := env_var_or_default("DOCUMENT_FETCH_WORKERS", "8")
document_fetch_per_host_workers := env_var_or_default("DOCUMENT_FETCH_PER_HOST_WORKERS", "2")
document_fetch_claim_size := env_var_or_default("DOCUMENT_FETCH_CLAIM_SIZE", "32")
document_fetch_max_items := env_var_or_default("DOCUMENT_FETCH_MAX_ITEMS", "0")
document_fetch_max_bytes := env_var_or_default("DOCUMENT_FETCH_MAX_BYTES", "262144000")
document_fetch_report_out := env_var_or_default("DOCUMENT_FETCH_REPORT_OUT", "docs/etl/runs/document-fetch-queue-latest.json")
text_extraction_workers := env_var_or_default("TEXT_EXTRACTION_WORKERS", "4")
text_extraction_claim_size := env_var_or_default("TEXT_EXTRACTION_CLAIM_SIZE", "16")
text_extraction_max_items := env_var_or_default("TEXT_EXTRACTION_MAX_ITEMS", "0")
text_extraction_report_out := env_var_or_default("TEXT_EXTRACTION_REPORT_OUT", "docs/etl/runs/text-extraction-queue-latest.json")
declared_min_auto_confidence := env_var_or_default("DECLARED_MIN_AUTO_CONFIDENCE", "0.62")
declared_source_id := env_var_or_default("DECLARED_SOURCE_ID", "congreso_intervenciones")
declared_review_limit := env_var_or_default("DECLARED_REVIEW_LIMIT", "50")
declared_status_out := env_var_or_default("DECLARED_STATUS_OUT", "")
declared_quality_source_ids := env_var_or_default("DECLARED_QUALITY_SOURCE_IDS", "programas_partidos")
declared_quality_vote_source_ids := env_var_or_default("DECLARED_QUALITY_VOTE_SOURCE_IDS", "congreso_votaciones,senado_votaciones")
declared_quality_out := env_var_or_default("DECLARED_QUALITY_OUT", "")
declared_quality_skip_vote_gate := env_var_or_default("DECLARED_QUALITY_SKIP_VOTE_GATE", "1")
initiative_quality_actionable_scope := env_var_or_default("INITIATIVE_QUALITY_ACTIONABLE_SCOPE", "global")
programas_manifest := env_var_or_default("PROGRAMAS_MANIFEST", "docs/etl/sprints/AI-OPS-256/exports/programas_manifest_local_replay_from_db_20260228.csv")
programas_status_out := env_var_or_default("PROGRAMAS_STATUS_OUT", "docs/etl/sprints/AI-OPS-29/evidence/programas_status_latest.json")
programas_manifest_validate_out := env_var_or_default("PROGRAMAS_MANIFEST_VALIDATE_OUT", "docs/etl/sprints/AI-OPS-30/evidence/programas_manifest_validate_latest.json")
programas_manifest_require_local_path := env_var_or_default("PROGRAMAS_MANIFEST_REQUIRE_LOCAL_PATH", "0")
programas_precision_sample_parties := env_var_or_default("PROGRAMAS_PRECISION_SAMPLE_PARTIES", "BNG,VOX,FORO Asturias,PP")
programas_precision_sample_per_party_limit := env_var_or_default("PROGRAMAS_PRECISION_SAMPLE_PER_PARTY_LIMIT", "10")
programas_precision_sample_limit := env_var_or_default("PROGRAMAS_PRECISION_SAMPLE_LIMIT", "0")
programas_precision_sample_dedupe_key := env_var_or_default("PROGRAMAS_PRECISION_SAMPLE_DEDUPE_KEY", "none")
programas_precision_sample_min_unique_per_party := env_var_or_default("PROGRAMAS_PRECISION_SAMPLE_MIN_UNIQUE_PER_PARTY", "0")
programas_precision_sample_excerpt_window_words := env_var_or_default("PROGRAMAS_PRECISION_SAMPLE_EXCERPT_WINDOW_WORDS", "0")
programas_precision_sample_excerpt_window_stride := env_var_or_default("PROGRAMAS_PRECISION_SAMPLE_EXCERPT_WINDOW_STRIDE", "0")
programas_precision_sample_excerpt_window_min_words := env_var_or_default("PROGRAMAS_PRECISION_SAMPLE_EXCERPT_WINDOW_MIN_WORDS", "12")
programas_precision_sample_out := env_var_or_default("PROGRAMAS_PRECISION_SAMPLE_OUT", "docs/etl/sprints/AI-OPS-259/exports/programas_support_precision_sample_latest.csv")
programas_precision_sample_summary_out := env_var_or_default("PROGRAMAS_PRECISION_SAMPLE_SUMMARY_OUT", "docs/etl/sprints/AI-OPS-259/evidence/programas_support_precision_sample_summary_latest.json")
programas_unclear_tail_parties := env_var_or_default("PROGRAMAS_UNCLEAR_TAIL_PARTIES", "BNG,VOX")
programas_unclear_tail_excerpt_len := env_var_or_default("PROGRAMAS_UNCLEAR_TAIL_EXCERPT_LEN", "320")
programas_unclear_tail_max_duplicate_share := env_var_or_default("PROGRAMAS_UNCLEAR_TAIL_MAX_DUPLICATE_SHARE", "1.0")
programas_unclear_tail_report_out := env_var_or_default("PROGRAMAS_UNCLEAR_TAIL_REPORT_OUT", "docs/etl/sprints/AI-OPS-268/evidence/programas_unclear_tail_dedupe_report_latest.json")
programas_unclear_tail_queue_out := env_var_or_default("PROGRAMAS_UNCLEAR_TAIL_QUEUE_OUT", "docs/etl/sprints/AI-OPS-268/exports/programas_unclear_tail_deduped_queue_latest.csv")
programas_unclear_tail_profile_out := env_var_or_default("PROGRAMAS_UNCLEAR_TAIL_PROFILE_OUT", "docs/etl/sprints/AI-OPS-268/exports/programas_unclear_tail_duplicate_profile_latest.csv")
programas_unclear_ratio_parties := env_var_or_default("PROGRAMAS_UNCLEAR_RATIO_PARTIES", "BNG,VOX")
programas_unclear_ratio_min := env_var_or_default("PROGRAMAS_UNCLEAR_RATIO_MIN", "1.0")
programas_unclear_ratio_out := env_var_or_default("PROGRAMAS_UNCLEAR_RATIO_OUT", "docs/etl/sprints/AI-OPS-269/evidence/programas_support_unclear_unique_ratio_latest.json")
programas_unclear_ratio_csv_out := env_var_or_default("PROGRAMAS_UNCLEAR_RATIO_CSV_OUT", "docs/etl/sprints/AI-OPS-269/exports/programas_support_unclear_unique_ratio_latest.csv")
programas_unclear_ratio_near_duplicate_jaccard_min := env_var_or_default("PROGRAMAS_UNCLEAR_RATIO_NEAR_DUPLICATE_JACCARD_MIN", "0.42")
programas_unclear_ratio_near_duplicate_containment_min := env_var_or_default("PROGRAMAS_UNCLEAR_RATIO_NEAR_DUPLICATE_CONTAINMENT_MIN", "0.40")
programas_unclear_ratio_near_duplicate_ngram_size := env_var_or_default("PROGRAMAS_UNCLEAR_RATIO_NEAR_DUPLICATE_NGRAM_SIZE", "6")
programas_unclear_ratio_disable_near_duplicate_dedupe := env_var_or_default("PROGRAMAS_UNCLEAR_RATIO_DISABLE_NEAR_DUPLICATE_DEDUPE", "0")
programas_empleo_fiscal_audit_parties := env_var_or_default("PROGRAMAS_EMPLEO_FISCAL_AUDIT_PARTIES", "BNG,CCa,Compromis,EAJ-PNV,VOX")
programas_empleo_fiscal_audit_topic_key := env_var_or_default("PROGRAMAS_EMPLEO_FISCAL_AUDIT_TOPIC_KEY", "concern:v1:empleo")
programas_empleo_fiscal_audit_terms := env_var_or_default("PROGRAMAS_EMPLEO_FISCAL_AUDIT_TERMS", "imposto de sociedades,fiscalidad,fiscalitat,impuesto,impostos,tribut,irpf,iva,sociedades")
programas_empleo_fiscal_audit_anchor_terms := env_var_or_default("PROGRAMAS_EMPLEO_FISCAL_AUDIT_ANCHOR_TERMS", "emple,trabaj,traballo,emprego,laboral,paro,salari,ocupacion,ocupacio")
programas_empleo_fiscal_audit_max_suspicious_support := env_var_or_default("PROGRAMAS_EMPLEO_FISCAL_AUDIT_MAX_SUSPICIOUS_SUPPORT", "0")
programas_empleo_fiscal_audit_out := env_var_or_default("PROGRAMAS_EMPLEO_FISCAL_AUDIT_OUT", "docs/etl/sprints/AI-OPS-275/evidence/programas_empleo_fiscal_snippets_audit_latest.json")
programas_empleo_fiscal_audit_csv_out := env_var_or_default("PROGRAMAS_EMPLEO_FISCAL_AUDIT_CSV_OUT", "docs/etl/sprints/AI-OPS-275/exports/programas_empleo_fiscal_snippets_audit_latest.csv")
programas_precision_rotate_labels_in := env_var_or_default("PROGRAMAS_PRECISION_ROTATE_LABELS_IN", "docs/etl/sprints/AI-OPS-258/exports/programas_support_precision_stratified_sample_20260228.csv")
programas_precision_labeled_out := env_var_or_default("PROGRAMAS_PRECISION_LABELED_OUT", "docs/etl/sprints/AI-OPS-259/exports/programas_support_precision_sample_labeled_latest.csv")
programas_precision_rotate_summary_out := env_var_or_default("PROGRAMAS_PRECISION_ROTATE_SUMMARY_OUT", "docs/etl/sprints/AI-OPS-259/evidence/programas_support_precision_rotate_summary_latest.json")
programas_precision_rotate_max_unlabeled := env_var_or_default("PROGRAMAS_PRECISION_ROTATE_MAX_UNLABELED", "-1")
programas_precision_rotate_strict_max_unlabeled := env_var_or_default("PROGRAMAS_PRECISION_ROTATE_STRICT_MAX_UNLABELED", "0")
programas_precision_audit_in := env_var_or_default("PROGRAMAS_PRECISION_AUDIT_IN", "docs/etl/sprints/AI-OPS-258/exports/programas_support_precision_stratified_sample_20260228.csv")
programas_precision_audit_out := env_var_or_default("PROGRAMAS_PRECISION_AUDIT_OUT", "docs/etl/sprints/AI-OPS-259/evidence/programas_support_precision_audit_latest.json")
programas_precision_audit_breakdown_out := env_var_or_default("PROGRAMAS_PRECISION_AUDIT_BREAKDOWN_OUT", "docs/etl/sprints/AI-OPS-259/exports/programas_support_precision_audit_breakdown_latest.csv")
programas_precision_min := env_var_or_default("PROGRAMAS_PRECISION_MIN", "0.90")
programas_precision_min_reviewed := env_var_or_default("PROGRAMAS_PRECISION_MIN_REVIEWED", "30")
programas_precision_min_party := env_var_or_default("PROGRAMAS_PRECISION_MIN_PARTY", "0.85")
programas_precision_required_parties := env_var_or_default("PROGRAMAS_PRECISION_REQUIRED_PARTIES", "BNG,VOX,FORO Asturias,PP")
programas_precision_reconcile_out := env_var_or_default("PROGRAMAS_PRECISION_RECONCILE_OUT", "docs/etl/sprints/AI-OPS-259/evidence/programas_backfill_declared_stance_guardrail_latest.json")
programas_precision_declared_positions_out := env_var_or_default("PROGRAMAS_PRECISION_DECLARED_POSITIONS_OUT", "docs/etl/sprints/AI-OPS-259/evidence/programas_backfill_declared_positions_guardrail_latest.json")
programas_precision_combined_positions_out := env_var_or_default("PROGRAMAS_PRECISION_COMBINED_POSITIONS_OUT", "docs/etl/sprints/AI-OPS-259/evidence/programas_backfill_combined_positions_guardrail_latest.json")
programas_precision_status_out := env_var_or_default("PROGRAMAS_PRECISION_STATUS_OUT", "docs/etl/sprints/AI-OPS-259/evidence/programas_declared_status_guardrail_latest.json")
programas_precision_quality_out := env_var_or_default("PROGRAMAS_PRECISION_QUALITY_OUT", "docs/etl/sprints/AI-OPS-259/evidence/programas_quality_declared_guardrail_latest.json")
programas_precision_tracker_out := env_var_or_default("PROGRAMAS_PRECISION_TRACKER_OUT", "docs/etl/sprints/AI-OPS-259/evidence/tracker_status_programas_guardrail_latest.log")
sanction_norms_seed := env_var_or_default("SANCTION_NORMS_SEED", "etl/data/seeds/sanction_norms_seed_v1.json")
sanction_norms_seed_source_id := env_var_or_default("SANCTION_NORMS_SEED_SOURCE_ID", "boe_api_legal")
sanction_norms_seed_validate_out := env_var_or_default("SANCTION_NORMS_SEED_VALIDATE_OUT", "docs/etl/sprints/AI-OPS-115/evidence/sanction_norms_seed_validate_latest.json")
sanction_norms_seed_import_out := env_var_or_default("SANCTION_NORMS_SEED_IMPORT_OUT", "docs/etl/sprints/AI-OPS-115/evidence/sanction_norms_seed_import_latest.json")
sanction_norms_seed_status_out := env_var_or_default("SANCTION_NORMS_SEED_STATUS_OUT", "docs/etl/sprints/AI-OPS-115/evidence/sanction_norms_seed_status_latest.json")
sanction_norms_seed_status_sample_limit := env_var_or_default("SANCTION_NORMS_SEED_STATUS_SAMPLE_LIMIT", "20")
sanction_norms_seed_source_record_upgrade_queue_out := env_var_or_default("SANCTION_NORMS_SEED_SOURCE_RECORD_UPGRADE_QUEUE_OUT", "docs/etl/sprints/AI-OPS-160/evidence/sanction_norms_seed_source_record_upgrade_queue_latest.json")
sanction_norms_seed_source_record_upgrade_queue_csv_out := env_var_or_default("SANCTION_NORMS_SEED_SOURCE_RECORD_UPGRADE_QUEUE_CSV_OUT", "docs/etl/sprints/AI-OPS-160/exports/sanction_norms_seed_source_record_upgrade_queue_latest.csv")
sanction_norms_seed_source_record_upgrade_queue_limit := env_var_or_default("SANCTION_NORMS_SEED_SOURCE_RECORD_UPGRADE_QUEUE_LIMIT", "0")
sanction_norms_seed_source_record_upgrade_queue_seed_schema_version := env_var_or_default("SANCTION_NORMS_SEED_SOURCE_RECORD_UPGRADE_QUEUE_SEED_SCHEMA_VERSION", "sanction_norms_seed_v1")
sanction_norms_boe_backfill_out := env_var_or_default("SANCTION_NORMS_BOE_BACKFILL_OUT", "docs/etl/sprints/AI-OPS-161/evidence/sanction_norms_boe_backfill_latest.json")
sanction_norms_boe_backfill_timeout := env_var_or_default("SANCTION_NORMS_BOE_BACKFILL_TIMEOUT", "30")
sanction_norms_boe_backfill_limit := env_var_or_default("SANCTION_NORMS_BOE_BACKFILL_LIMIT", "0")
sanction_norms_source_record_upgrade_apply_out := env_var_or_default("SANCTION_NORMS_SOURCE_RECORD_UPGRADE_APPLY_OUT", "docs/etl/sprints/AI-OPS-161/evidence/sanction_norms_source_record_upgrade_apply_latest.json")
sanction_norms_source_record_upgrade_apply_limit := env_var_or_default("SANCTION_NORMS_SOURCE_RECORD_UPGRADE_APPLY_LIMIT", "0")
sanction_norms_source_record_upgrade_apply_dry_run := env_var_or_default("SANCTION_NORMS_SOURCE_RECORD_UPGRADE_APPLY_DRY_RUN", "0")
sanction_norms_parliamentary_evidence_out := env_var_or_default("SANCTION_NORMS_PARLIAMENTARY_EVIDENCE_OUT", "docs/etl/sprints/AI-OPS-162/evidence/sanction_norms_parliamentary_evidence_backfill_latest.json")
sanction_norms_parliamentary_evidence_roles := env_var_or_default("SANCTION_NORMS_PARLIAMENTARY_EVIDENCE_ROLES", "approve,propose")
sanction_norms_parliamentary_evidence_limit := env_var_or_default("SANCTION_NORMS_PARLIAMENTARY_EVIDENCE_LIMIT", "0")
sanction_norms_vote_evidence_out := env_var_or_default("SANCTION_NORMS_VOTE_EVIDENCE_OUT", "docs/etl/sprints/AI-OPS-163/evidence/sanction_norms_vote_evidence_backfill_latest.json")
sanction_norms_vote_evidence_roles := env_var_or_default("SANCTION_NORMS_VOTE_EVIDENCE_ROLES", "approve,propose")
sanction_norms_vote_evidence_limit_events := env_var_or_default("SANCTION_NORMS_VOTE_EVIDENCE_LIMIT_EVENTS", "0")
sanction_norms_vote_gap_diagnosis_out := env_var_or_default("SANCTION_NORMS_VOTE_GAP_DIAGNOSIS_OUT", "docs/etl/sprints/AI-OPS-172/evidence/sanction_norms_vote_gap_diagnosis_latest.json")
sanction_norms_vote_gap_diagnosis_roles := env_var_or_default("SANCTION_NORMS_VOTE_GAP_DIAGNOSIS_ROLES", "approve,propose,enforce,delegate")
sanction_norms_execution_evidence_out := env_var_or_default("SANCTION_NORMS_EXECUTION_EVIDENCE_OUT", "docs/etl/sprints/AI-OPS-165/evidence/sanction_norms_execution_evidence_backfill_latest.json")
sanction_norms_execution_evidence_roles := env_var_or_default("SANCTION_NORMS_EXECUTION_EVIDENCE_ROLES", "enforce,approve,propose,delegate")
sanction_norms_execution_evidence_limit := env_var_or_default("SANCTION_NORMS_EXECUTION_EVIDENCE_LIMIT", "0")
sanction_norms_execution_lineage_evidence_out := env_var_or_default("SANCTION_NORMS_EXECUTION_LINEAGE_EVIDENCE_OUT", "docs/etl/sprints/AI-OPS-166/evidence/sanction_norms_execution_lineage_evidence_backfill_latest.json")
sanction_norms_execution_lineage_evidence_roles := env_var_or_default("SANCTION_NORMS_EXECUTION_LINEAGE_EVIDENCE_ROLES", "delegate")
sanction_norms_execution_lineage_evidence_limit := env_var_or_default("SANCTION_NORMS_EXECUTION_LINEAGE_EVIDENCE_LIMIT", "0")
sanction_norms_procedural_metric_evidence_out := env_var_or_default("SANCTION_NORMS_PROCEDURAL_METRIC_EVIDENCE_OUT", "docs/etl/sprints/AI-OPS-165/evidence/sanction_norms_procedural_metric_evidence_backfill_latest.json")
sanction_norms_procedural_metric_evidence_roles := env_var_or_default("SANCTION_NORMS_PROCEDURAL_METRIC_EVIDENCE_ROLES", "enforce,approve,propose,delegate")
sanction_norms_procedural_metric_evidence_limit := env_var_or_default("SANCTION_NORMS_PROCEDURAL_METRIC_EVIDENCE_LIMIT", "0")
sanction_data_catalog_seed := env_var_or_default("SANCTION_DATA_CATALOG_SEED", "etl/data/seeds/sanction_data_catalog_seed_v1.json")
sanction_data_catalog_source_id := env_var_or_default("SANCTION_DATA_CATALOG_SOURCE_ID", "boe_api_legal")
sanction_data_catalog_validate_out := env_var_or_default("SANCTION_DATA_CATALOG_VALIDATE_OUT", "docs/etl/sprints/AI-OPS-116/evidence/sanction_data_catalog_validate_latest.json")
sanction_data_catalog_import_out := env_var_or_default("SANCTION_DATA_CATALOG_IMPORT_OUT", "docs/etl/sprints/AI-OPS-116/evidence/sanction_data_catalog_import_latest.json")
sanction_data_catalog_status_out := env_var_or_default("SANCTION_DATA_CATALOG_STATUS_OUT", "docs/etl/sprints/AI-OPS-116/evidence/sanction_data_catalog_status_latest.json")
sanction_data_catalog_status_sample_limit := env_var_or_default("SANCTION_DATA_CATALOG_STATUS_SAMPLE_LIMIT", "20")
sanction_procedural_official_review_status_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_STATUS_OUT", "docs/etl/sprints/AI-OPS-173/evidence/sanction_procedural_official_review_status_latest.json")
sanction_procedural_official_review_status_csv_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_STATUS_CSV_OUT", "docs/etl/sprints/AI-OPS-173/exports/sanction_procedural_official_review_queue_latest.csv")
sanction_procedural_official_review_status_queue_limit := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_STATUS_QUEUE_LIMIT", "0")
sanction_procedural_official_review_status_period_date := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_STATUS_PERIOD_DATE", "")
sanction_procedural_official_review_status_period_granularity := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_STATUS_PERIOD_GRANULARITY", "")
sanction_procedural_official_review_kpi_gap_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_KPI_GAP_OUT", "docs/etl/sprints/AI-OPS-185/evidence/sanction_procedural_official_review_kpi_gap_queue_latest.json")
sanction_procedural_official_review_kpi_gap_csv_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_KPI_GAP_CSV_OUT", "docs/etl/sprints/AI-OPS-185/exports/sanction_procedural_official_review_kpi_gap_queue_latest.csv")
sanction_procedural_official_review_kpi_gap_queue_limit := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_KPI_GAP_QUEUE_LIMIT", "0")
sanction_procedural_official_review_kpi_gap_period_date := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_KPI_GAP_PERIOD_DATE", "")
sanction_procedural_official_review_kpi_gap_period_granularity := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_KPI_GAP_PERIOD_GRANULARITY", "")
sanction_procedural_official_review_kpi_gap_include_ready := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_KPI_GAP_INCLUDE_READY", "0")
sanction_procedural_official_review_kpi_gap_strict_empty := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_KPI_GAP_STRICT_EMPTY", "0")
sanction_procedural_official_review_apply_from_gap_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_APPLY_FROM_GAP_OUT", "docs/etl/sprints/AI-OPS-186/exports/sanction_procedural_official_review_apply_from_gap_queue_latest.csv")
sanction_procedural_official_review_apply_from_gap_summary_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_APPLY_FROM_GAP_SUMMARY_OUT", "docs/etl/sprints/AI-OPS-186/evidence/sanction_procedural_official_review_apply_from_gap_queue_latest.json")
sanction_procedural_official_review_apply_from_gap_queue_limit := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_APPLY_FROM_GAP_QUEUE_LIMIT", "0")
sanction_procedural_official_review_apply_from_gap_period_date := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_APPLY_FROM_GAP_PERIOD_DATE", "")
sanction_procedural_official_review_apply_from_gap_period_granularity := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_APPLY_FROM_GAP_PERIOD_GRANULARITY", "")
sanction_procedural_official_review_apply_from_gap_statuses := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_APPLY_FROM_GAP_STATUSES", "missing_metric,missing_source_record,missing_evidence")
sanction_procedural_official_review_apply_from_gap_source_id := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_APPLY_FROM_GAP_SOURCE_ID", "boe_api_legal")
sanction_procedural_official_review_apply_from_gap_include_ready := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_APPLY_FROM_GAP_INCLUDE_READY", "0")
sanction_procedural_official_review_apply_from_gap_strict_actionable := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_APPLY_FROM_GAP_STRICT_ACTIONABLE", "0")
sanction_procedural_official_review_raw_packets_out_dir := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_OUT_DIR", "docs/etl/sprints/AI-OPS-188/exports/sanction_procedural_official_review_raw_packets_latest")
sanction_procedural_official_review_raw_packets_summary_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_SUMMARY_OUT", "docs/etl/sprints/AI-OPS-188/evidence/sanction_procedural_official_review_raw_packets_latest.json")
sanction_procedural_official_review_raw_packets_statuses := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_STATUSES", "missing_metric")
sanction_procedural_official_review_raw_packets_period_date := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_PERIOD_DATE", snapshot_date)
sanction_procedural_official_review_raw_packets_period_granularity := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_PERIOD_GRANULARITY", "year")
sanction_procedural_official_review_raw_packets_queue_limit := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_QUEUE_LIMIT", "0")
sanction_procedural_official_review_raw_packets_include_ready := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_INCLUDE_READY", "0")
sanction_procedural_official_review_raw_packets_source_id := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_SOURCE_ID", "boe_api_legal")
sanction_procedural_official_review_raw_packets_strict_actionable := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_STRICT_ACTIONABLE", "0")
sanction_procedural_official_review_raw_packets_progress_packets_dir := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_PROGRESS_PACKETS_DIR", "docs/etl/sprints/AI-OPS-188/exports/sanction_procedural_official_review_raw_packets_latest")
sanction_procedural_official_review_raw_packets_progress_csv_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_PROGRESS_CSV_OUT", "docs/etl/sprints/AI-OPS-190/exports/sanction_procedural_official_review_raw_packets_progress_latest.csv")
sanction_procedural_official_review_raw_packets_progress_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_PROGRESS_OUT", "docs/etl/sprints/AI-OPS-190/evidence/sanction_procedural_official_review_raw_packets_progress_latest.json")
sanction_procedural_official_review_raw_packets_progress_statuses := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_PROGRESS_STATUSES", "missing_metric")
sanction_procedural_official_review_raw_packets_progress_period_date := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_PROGRESS_PERIOD_DATE", snapshot_date)
sanction_procedural_official_review_raw_packets_progress_period_granularity := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_PROGRESS_PERIOD_GRANULARITY", "year")
sanction_procedural_official_review_raw_packets_progress_queue_limit := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_PROGRESS_QUEUE_LIMIT", "0")
sanction_procedural_official_review_raw_packets_progress_include_ready := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_PROGRESS_INCLUDE_READY", "0")
sanction_procedural_official_review_raw_packets_progress_source_id := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_PROGRESS_SOURCE_ID", "boe_api_legal")
sanction_procedural_official_review_raw_packets_progress_strict_actionable := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_PROGRESS_STRICT_ACTIONABLE", "0")
sanction_procedural_official_review_raw_packets_progress_strict_ready := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_PROGRESS_STRICT_READY", "0")
sanction_procedural_official_review_packet_fix_queue_packets_dir := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_PACKETS_DIR", "docs/etl/sprints/AI-OPS-188/exports/sanction_procedural_official_review_raw_packets_latest")
sanction_procedural_official_review_packet_fix_queue_csv_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_CSV_OUT", "docs/etl/sprints/AI-OPS-192/exports/sanction_procedural_official_review_packet_fix_queue_latest.csv")
sanction_procedural_official_review_packet_fix_queue_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_OUT", "docs/etl/sprints/AI-OPS-192/evidence/sanction_procedural_official_review_packet_fix_queue_latest.json")
sanction_procedural_official_review_packet_fix_queue_statuses := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_STATUSES", "missing_metric")
sanction_procedural_official_review_packet_fix_queue_period_date := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_PERIOD_DATE", snapshot_date)
sanction_procedural_official_review_packet_fix_queue_period_granularity := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_PERIOD_GRANULARITY", "year")
sanction_procedural_official_review_packet_fix_queue_queue_limit := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_QUEUE_LIMIT", "0")
sanction_procedural_official_review_packet_fix_queue_include_ready := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_INCLUDE_READY", "0")
sanction_procedural_official_review_packet_fix_queue_source_id := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_SOURCE_ID", "boe_api_legal")
sanction_procedural_official_review_packet_fix_queue_strict_empty := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_STRICT_EMPTY", "0")
sanction_procedural_official_review_packet_fix_ready_cycle_packets_dir := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_READY_CYCLE_PACKETS_DIR", "docs/etl/sprints/AI-OPS-188/exports/sanction_procedural_official_review_raw_packets_latest")
sanction_procedural_official_review_packet_fix_ready_cycle_fix_csv_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_READY_CYCLE_FIX_CSV_OUT", "docs/etl/sprints/AI-OPS-193/exports/sanction_procedural_official_review_packet_fix_queue_latest.csv")
sanction_procedural_official_review_packet_fix_ready_cycle_fix_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_READY_CYCLE_FIX_OUT", "docs/etl/sprints/AI-OPS-193/evidence/sanction_procedural_official_review_packet_fix_ready_cycle_fix_queue_latest.json")
sanction_procedural_official_review_packet_fix_ready_cycle_raw_in_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_READY_CYCLE_RAW_IN_OUT", "docs/etl/sprints/AI-OPS-193/exports/sanction_procedural_official_review_raw_from_packet_fix_ready_cycle_latest.csv")
sanction_procedural_official_review_packet_fix_ready_cycle_progress_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_READY_CYCLE_PROGRESS_OUT", "docs/etl/sprints/AI-OPS-193/evidence/sanction_procedural_official_review_packet_fix_ready_cycle_progress_latest.json")
sanction_procedural_official_review_packet_fix_ready_cycle_ready_cycle_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_READY_CYCLE_READY_CYCLE_OUT", "docs/etl/sprints/AI-OPS-193/evidence/sanction_procedural_official_review_packet_fix_ready_cycle_ready_cycle_latest.json")
sanction_procedural_official_review_packet_fix_ready_cycle_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_READY_CYCLE_OUT", "docs/etl/sprints/AI-OPS-193/evidence/sanction_procedural_official_review_packet_fix_ready_cycle_latest.json")
sanction_procedural_official_review_packet_fix_ready_cycle_statuses := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_READY_CYCLE_STATUSES", "missing_metric")
sanction_procedural_official_review_packet_fix_ready_cycle_period_date := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_READY_CYCLE_PERIOD_DATE", snapshot_date)
sanction_procedural_official_review_packet_fix_ready_cycle_period_granularity := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_READY_CYCLE_PERIOD_GRANULARITY", "year")
sanction_procedural_official_review_packet_fix_ready_cycle_queue_limit := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_READY_CYCLE_QUEUE_LIMIT", "0")
sanction_procedural_official_review_packet_fix_ready_cycle_include_ready := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_READY_CYCLE_INCLUDE_READY", "0")
sanction_procedural_official_review_packet_fix_ready_cycle_source_id := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_READY_CYCLE_SOURCE_ID", "boe_api_legal")
sanction_procedural_official_review_packet_fix_ready_cycle_strict_fix_empty := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_READY_CYCLE_STRICT_FIX_EMPTY", "0")
sanction_procedural_official_review_packet_fix_ready_cycle_strict_actionable := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_READY_CYCLE_STRICT_ACTIONABLE", "0")
sanction_procedural_official_review_packet_fix_ready_cycle_strict_min_ready := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_READY_CYCLE_STRICT_MIN_READY", "0")
sanction_procedural_official_review_packet_fix_ready_cycle_min_ready_packets := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_READY_CYCLE_MIN_READY_PACKETS", "1")
sanction_procedural_official_review_packet_fix_ready_cycle_strict_raw := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_READY_CYCLE_STRICT_RAW", "0")
sanction_procedural_official_review_packet_fix_ready_cycle_strict_prepare := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_READY_CYCLE_STRICT_PREPARE", "0")
sanction_procedural_official_review_packet_fix_ready_cycle_strict_readiness := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_READY_CYCLE_STRICT_READINESS", "0")
sanction_procedural_official_review_packet_fix_queue_heartbeat_fix_queue_json := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_FIX_QUEUE_JSON", "docs/etl/sprints/AI-OPS-193/evidence/sanction_procedural_official_review_packet_fix_ready_cycle_fix_queue_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_path := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_PATH", "docs/etl/runs/sanction_procedural_official_review_packet_fix_queue_heartbeat.jsonl")
sanction_procedural_official_review_packet_fix_queue_heartbeat_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_OUT", "docs/etl/sprints/AI-OPS-194/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_window := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_WINDOW", "20")
sanction_procedural_official_review_packet_fix_queue_heartbeat_window_max_failed := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_WINDOW_MAX_FAILED", "0")
sanction_procedural_official_review_packet_fix_queue_heartbeat_window_max_failed_rate_pct := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_WINDOW_MAX_FAILED_RATE_PCT", "0")
sanction_procedural_official_review_packet_fix_queue_heartbeat_window_max_degraded := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_WINDOW_MAX_DEGRADED", "1000000")
sanction_procedural_official_review_packet_fix_queue_heartbeat_window_max_degraded_rate_pct := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_WINDOW_MAX_DEGRADED_RATE_PCT", "100")
sanction_procedural_official_review_packet_fix_queue_heartbeat_window_max_nonempty_queue_runs := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_WINDOW_MAX_NONEMPTY_QUEUE_RUNS", "1000000")
sanction_procedural_official_review_packet_fix_queue_heartbeat_window_max_nonempty_queue_rate_pct := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_WINDOW_MAX_NONEMPTY_QUEUE_RATE_PCT", "100")
sanction_procedural_official_review_packet_fix_queue_heartbeat_window_max_malformed := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_WINDOW_MAX_MALFORMED", "0")
sanction_procedural_official_review_packet_fix_queue_heartbeat_window_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-194/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_window_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_path := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_PATH", "docs/etl/runs/sanction_procedural_official_review_packet_fix_queue_heartbeat.compacted.jsonl")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_recent := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_RECENT", "20")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_mid_span := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_MID_SPAN", "100")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_mid_every := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_MID_EVERY", "5")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_old_every := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_OLD_EVERY", "20")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_min_raw := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_MIN_RAW", "25")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_OUT", "docs/etl/sprints/AI-OPS-195/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_last := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_LAST", "20")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-195/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_in := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_IN", sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_out)
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_OUT", "docs/etl/sprints/AI-OPS-196/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_digest_json := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_DIGEST_JSON", sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_out)
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_path := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_PATH", "docs/etl/runs/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat.jsonl")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_OUT", "docs/etl/sprints/AI-OPS-197/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_window := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW", "20")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_window_max_failed := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_FAILED", "0")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_window_max_failed_rate_pct := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_FAILED_RATE_PCT", "0")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_window_max_degraded := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_DEGRADED", "0")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_window_max_degraded_rate_pct := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_DEGRADED_RATE_PCT", "0")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_window_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-197/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_window_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_path := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_PATH", "docs/etl/runs/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat.compacted.jsonl")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_recent := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_RECENT", "20")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_mid_span := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_MID_SPAN", "100")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_mid_every := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_MID_EVERY", "5")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_old_every := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_OLD_EVERY", "20")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_min_raw := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_MIN_RAW", "25")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_OUT", "docs/etl/sprints/AI-OPS-198/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_last := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_LAST", "20")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-198/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_OUT", "docs/etl/sprints/AI-OPS-199/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_digest_json := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_DIGEST_JSON", sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_out)
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_PATH", "docs/etl/runs/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat.jsonl")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_OUT", "docs/etl/sprints/AI-OPS-200/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW", "20")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_failed := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_FAILED", "0")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_failed_rate_pct := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_FAILED_RATE_PCT", "0")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_degraded := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_DEGRADED", "0")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_degraded_rate_pct := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_DEGRADED_RATE_PCT", "0")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-201/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_window_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_path := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_PATH", "docs/etl/runs/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat.compacted.jsonl")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_recent := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_RECENT", "20")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_mid_span := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_MID_SPAN", "100")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_mid_every := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_MID_EVERY", "5")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_old_every := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_OLD_EVERY", "20")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_min_raw := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_MIN_RAW", "25")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_OUT", "docs/etl/sprints/AI-OPS-202/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_last := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_LAST", "20")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-202/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_OUT", "docs/etl/sprints/AI-OPS-203/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_digest_json := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_DIGEST_JSON", sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_out)
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_PATH", "docs/etl/runs/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat.jsonl")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_OUT", "docs/etl/sprints/AI-OPS-204/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW", "20")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_failed := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_FAILED", "0")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_failed_rate_pct := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_FAILED_RATE_PCT", "0")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_degraded := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_DEGRADED", "0")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_degraded_rate_pct := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_DEGRADED_RATE_PCT", "0")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-205/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_window_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_path := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_PATH", "docs/etl/runs/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat.compacted.jsonl")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_recent := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_RECENT", "20")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_mid_span := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_MID_SPAN", "100")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_mid_every := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_MID_EVERY", "5")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_old_every := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_OLD_EVERY", "20")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_min_raw := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_MIN_RAW", "25")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_OUT", "docs/etl/sprints/AI-OPS-206/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_last := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_LAST", "20")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-206/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_OUT", "docs/etl/sprints/AI-OPS-207/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_digest_json := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_DIGEST_JSON", sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_out)
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_PATH", "docs/etl/runs/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat.jsonl")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_OUT", "docs/etl/sprints/AI-OPS-208/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW", "20")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_failed := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_FAILED", "0")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_failed_rate_pct := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_FAILED_RATE_PCT", "0")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_degraded := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_DEGRADED", "0")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_degraded_rate_pct := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_DEGRADED_RATE_PCT", "0")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-209/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_window_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_path := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_PATH", "docs/etl/runs/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat.compacted.jsonl")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_recent := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_RECENT", "20")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_mid_span := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_MID_SPAN", "100")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_mid_every := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_MID_EVERY", "5")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_old_every := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_OLD_EVERY", "20")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_min_raw := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_MIN_RAW", "25")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_OUT", "docs/etl/sprints/AI-OPS-210/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_last := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_LAST", "20")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-210/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_OUT", "docs/etl/sprints/AI-OPS-211/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_digest_json := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_DIGEST_JSON", sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_out)
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_PATH", "docs/etl/runs/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat.jsonl")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_OUT", "docs/etl/sprints/AI-OPS-212/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW", "20")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_failed := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_FAILED", "0")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_failed_rate_pct := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_FAILED_RATE_PCT", "0")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_degraded := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_DEGRADED", "0")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_degraded_rate_pct := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_DEGRADED_RATE_PCT", "0")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-213/evidence/ai_ops_213_heartbeat_window_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_path := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_PATH", "docs/etl/runs/ai_ops_214_heartbeat_compacted.jsonl")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_recent := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_RECENT", "20")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_mid_span := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_MID_SPAN", "100")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_mid_every := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_MID_EVERY", "5")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_old_every := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_OLD_EVERY", "20")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_min_raw := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_MIN_RAW", "25")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_OUT", "docs/etl/sprints/AI-OPS-214/evidence/ai_ops_214_heartbeat_compaction_latest.json")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_last := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_LAST", "20")
sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-214/evidence/ai_ops_214_heartbeat_compaction_window_latest.json")
sanction_procedural_official_review_packet_fix_queue_ai_ops_215_digest_in := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_AI_OPS_215_DIGEST_IN", sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_out)
sanction_procedural_official_review_packet_fix_queue_ai_ops_215_digest_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_AI_OPS_215_DIGEST_OUT", "docs/etl/sprints/AI-OPS-215/evidence/ai_ops_215_digest_latest.json")
sanction_procedural_official_review_packet_fix_queue_ai_ops_216_digest_heartbeat_digest_json := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_AI_OPS_216_DIGEST_HEARTBEAT_DIGEST_JSON", sanction_procedural_official_review_packet_fix_queue_ai_ops_215_digest_out)
sanction_procedural_official_review_packet_fix_queue_ai_ops_216_digest_heartbeat_path := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_AI_OPS_216_DIGEST_HEARTBEAT_PATH", "docs/etl/runs/ai_ops_216_digest_heartbeat.jsonl")
sanction_procedural_official_review_packet_fix_queue_ai_ops_216_digest_heartbeat_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_AI_OPS_216_DIGEST_HEARTBEAT_OUT", "docs/etl/sprints/AI-OPS-216/evidence/ai_ops_216_digest_heartbeat_latest.json")
sanction_procedural_official_review_ready_packets_cycle_packets_dir := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_READY_PACKETS_CYCLE_PACKETS_DIR", "docs/etl/sprints/AI-OPS-188/exports/sanction_procedural_official_review_raw_packets_latest")
sanction_procedural_official_review_ready_packets_cycle_raw_in_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_READY_PACKETS_CYCLE_RAW_IN_OUT", "docs/etl/sprints/AI-OPS-191/exports/sanction_procedural_official_review_raw_from_ready_packets_latest.csv")
sanction_procedural_official_review_ready_packets_cycle_progress_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_READY_PACKETS_CYCLE_PROGRESS_OUT", "docs/etl/sprints/AI-OPS-191/evidence/sanction_procedural_official_review_ready_packets_cycle_progress_latest.json")
sanction_procedural_official_review_ready_packets_cycle_cycle_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_READY_PACKETS_CYCLE_CYCLE_OUT", "docs/etl/sprints/AI-OPS-191/evidence/sanction_procedural_official_review_ready_packets_cycle_cycle_latest.json")
sanction_procedural_official_review_ready_packets_cycle_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_READY_PACKETS_CYCLE_OUT", "docs/etl/sprints/AI-OPS-191/evidence/sanction_procedural_official_review_ready_packets_cycle_latest.json")
sanction_procedural_official_review_ready_packets_cycle_statuses := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_READY_PACKETS_CYCLE_STATUSES", "missing_metric")
sanction_procedural_official_review_ready_packets_cycle_period_date := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_READY_PACKETS_CYCLE_PERIOD_DATE", snapshot_date)
sanction_procedural_official_review_ready_packets_cycle_period_granularity := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_READY_PACKETS_CYCLE_PERIOD_GRANULARITY", "year")
sanction_procedural_official_review_ready_packets_cycle_queue_limit := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_READY_PACKETS_CYCLE_QUEUE_LIMIT", "0")
sanction_procedural_official_review_ready_packets_cycle_include_ready := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_READY_PACKETS_CYCLE_INCLUDE_READY", "0")
sanction_procedural_official_review_ready_packets_cycle_source_id := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_READY_PACKETS_CYCLE_SOURCE_ID", "boe_api_legal")
sanction_procedural_official_review_ready_packets_cycle_strict_actionable := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_READY_PACKETS_CYCLE_STRICT_ACTIONABLE", "0")
sanction_procedural_official_review_ready_packets_cycle_strict_min_ready := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_READY_PACKETS_CYCLE_STRICT_MIN_READY", "0")
sanction_procedural_official_review_ready_packets_cycle_min_ready_packets := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_READY_PACKETS_CYCLE_MIN_READY_PACKETS", "1")
sanction_procedural_official_review_ready_packets_cycle_strict_raw := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_READY_PACKETS_CYCLE_STRICT_RAW", "0")
sanction_procedural_official_review_ready_packets_cycle_strict_prepare := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_READY_PACKETS_CYCLE_STRICT_PREPARE", "0")
sanction_procedural_official_review_ready_packets_cycle_strict_readiness := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_READY_PACKETS_CYCLE_STRICT_READINESS", "0")
sanction_procedural_official_review_raw_packets_cycle_packets_dir := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_CYCLE_PACKETS_DIR", "docs/etl/sprints/AI-OPS-188/exports/sanction_procedural_official_review_raw_packets_latest")
sanction_procedural_official_review_raw_packets_cycle_raw_in_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_CYCLE_RAW_IN_OUT", "docs/etl/sprints/AI-OPS-189/exports/sanction_procedural_official_review_raw_from_packets_latest.csv")
sanction_procedural_official_review_raw_packets_cycle_packets_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_CYCLE_PACKETS_OUT", "docs/etl/sprints/AI-OPS-189/evidence/sanction_procedural_official_review_raw_packets_cycle_packets_latest.json")
sanction_procedural_official_review_raw_packets_cycle_cycle_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_CYCLE_CYCLE_OUT", "docs/etl/sprints/AI-OPS-189/evidence/sanction_procedural_official_review_raw_packets_cycle_cycle_latest.json")
sanction_procedural_official_review_raw_packets_cycle_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_CYCLE_OUT", "docs/etl/sprints/AI-OPS-189/evidence/sanction_procedural_official_review_raw_packets_cycle_latest.json")
sanction_procedural_official_review_raw_packets_cycle_statuses := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_CYCLE_STATUSES", "missing_metric")
sanction_procedural_official_review_raw_packets_cycle_period_date := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_CYCLE_PERIOD_DATE", snapshot_date)
sanction_procedural_official_review_raw_packets_cycle_period_granularity := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_CYCLE_PERIOD_GRANULARITY", "year")
sanction_procedural_official_review_raw_packets_cycle_queue_limit := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_CYCLE_QUEUE_LIMIT", "0")
sanction_procedural_official_review_raw_packets_cycle_include_ready := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_CYCLE_INCLUDE_READY", "0")
sanction_procedural_official_review_raw_packets_cycle_source_id := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_CYCLE_SOURCE_ID", "boe_api_legal")
sanction_procedural_official_review_raw_packets_cycle_strict_actionable := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_CYCLE_STRICT_ACTIONABLE", "0")
sanction_procedural_official_review_raw_packets_cycle_strict_packet_coverage := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_CYCLE_STRICT_PACKET_COVERAGE", "0")
sanction_procedural_official_review_raw_packets_cycle_strict_raw := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_CYCLE_STRICT_RAW", "0")
sanction_procedural_official_review_raw_packets_cycle_strict_prepare := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_CYCLE_STRICT_PREPARE", "0")
sanction_procedural_official_review_raw_packets_cycle_strict_readiness := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_PACKETS_CYCLE_STRICT_READINESS", "0")
sanction_procedural_official_review_gap_cycle_apply_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_GAP_CYCLE_APPLY_OUT", "docs/etl/sprints/AI-OPS-187/exports/sanction_procedural_official_review_apply_from_gap_cycle_latest.csv")
sanction_procedural_official_review_gap_cycle_gap_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_GAP_CYCLE_GAP_OUT", "docs/etl/sprints/AI-OPS-187/evidence/sanction_procedural_official_review_gap_cycle_gap_latest.json")
sanction_procedural_official_review_gap_cycle_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_GAP_CYCLE_OUT", "docs/etl/sprints/AI-OPS-187/evidence/sanction_procedural_official_review_gap_cycle_latest.json")
sanction_procedural_official_review_gap_cycle_cycle_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_GAP_CYCLE_CYCLE_OUT", "docs/etl/sprints/AI-OPS-187/evidence/sanction_procedural_official_review_gap_cycle_cycle_latest.json")
sanction_procedural_official_review_gap_cycle_statuses := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_GAP_CYCLE_STATUSES", "missing_source_record")
sanction_procedural_official_review_gap_cycle_period_date := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_GAP_CYCLE_PERIOD_DATE", "")
sanction_procedural_official_review_gap_cycle_period_granularity := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_GAP_CYCLE_PERIOD_GRANULARITY", "")
sanction_procedural_official_review_gap_cycle_queue_limit := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_GAP_CYCLE_QUEUE_LIMIT", "0")
sanction_procedural_official_review_gap_cycle_include_ready := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_GAP_CYCLE_INCLUDE_READY", "0")
sanction_procedural_official_review_gap_cycle_strict_actionable := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_GAP_CYCLE_STRICT_ACTIONABLE", "0")
sanction_procedural_official_review_apply_in := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_APPLY_IN", "")
sanction_procedural_official_review_apply_source_id := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_APPLY_SOURCE_ID", "boe_api_legal")
sanction_procedural_official_review_apply_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_APPLY_OUT", "docs/etl/sprints/AI-OPS-174/evidence/sanction_procedural_official_review_apply_latest.json")
sanction_procedural_official_review_template_period_date := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_TEMPLATE_PERIOD_DATE", snapshot_date)
sanction_procedural_official_review_template_period_granularity := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_TEMPLATE_PERIOD_GRANULARITY", "year")
sanction_procedural_official_review_template_source_id := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_TEMPLATE_SOURCE_ID", "boe_api_legal")
sanction_procedural_official_review_template_only_missing := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_TEMPLATE_ONLY_MISSING", "1")
sanction_procedural_official_review_template_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_TEMPLATE_OUT", "docs/etl/sprints/AI-OPS-175/exports/sanction_procedural_official_review_apply_template_latest.csv")
sanction_procedural_official_review_template_summary_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_TEMPLATE_SUMMARY_OUT", "docs/etl/sprints/AI-OPS-175/evidence/sanction_procedural_official_review_apply_template_latest.json")
sanction_procedural_official_review_raw_in := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_IN", "")
sanction_procedural_official_review_raw_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_OUT", "docs/etl/sprints/AI-OPS-181/exports/sanction_procedural_official_review_apply_from_raw_latest.csv")
sanction_procedural_official_review_raw_rejected_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_REJECTED_OUT", "docs/etl/sprints/AI-OPS-181/exports/sanction_procedural_official_review_apply_from_raw_rejected_latest.csv")
sanction_procedural_official_review_raw_summary_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_SUMMARY_OUT", "docs/etl/sprints/AI-OPS-181/evidence/sanction_procedural_official_review_apply_from_raw_latest.json")
sanction_procedural_official_review_raw_default_source_id := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_DEFAULT_SOURCE_ID", "boe_api_legal")
sanction_procedural_official_review_raw_default_period_granularity := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_DEFAULT_PERIOD_GRANULARITY", "year")
sanction_procedural_official_review_raw_strict := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_STRICT", "0")
sanction_procedural_official_review_raw_template_period_date := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_TEMPLATE_PERIOD_DATE", snapshot_date)
sanction_procedural_official_review_raw_template_period_granularity := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_TEMPLATE_PERIOD_GRANULARITY", "year")
sanction_procedural_official_review_raw_template_source_id := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_TEMPLATE_SOURCE_ID", "boe_api_legal")
sanction_procedural_official_review_raw_template_only_missing := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_TEMPLATE_ONLY_MISSING", "1")
sanction_procedural_official_review_raw_template_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_TEMPLATE_OUT", "docs/etl/sprints/AI-OPS-183/exports/sanction_procedural_official_review_raw_template_latest.csv")
sanction_procedural_official_review_raw_template_summary_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_TEMPLATE_SUMMARY_OUT", "docs/etl/sprints/AI-OPS-183/evidence/sanction_procedural_official_review_raw_template_latest.json")
sanction_procedural_official_review_raw_cycle_apply_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_CYCLE_APPLY_OUT", "docs/etl/sprints/AI-OPS-182/exports/sanction_procedural_official_review_apply_from_raw_cycle_latest.csv")
sanction_procedural_official_review_raw_cycle_raw_rejected_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_CYCLE_RAW_REJECTED_OUT", "docs/etl/sprints/AI-OPS-182/exports/sanction_procedural_official_review_apply_from_raw_cycle_rejected_latest.csv")
sanction_procedural_official_review_raw_cycle_raw_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_CYCLE_RAW_OUT", "docs/etl/sprints/AI-OPS-182/evidence/sanction_procedural_official_review_raw_cycle_raw_latest.json")
sanction_procedural_official_review_raw_cycle_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_CYCLE_OUT", "docs/etl/sprints/AI-OPS-182/evidence/sanction_procedural_official_review_raw_prepare_apply_cycle_latest.json")
sanction_procedural_official_review_raw_cycle_cycle_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_CYCLE_CYCLE_OUT", "docs/etl/sprints/AI-OPS-182/evidence/sanction_procedural_official_review_raw_prepare_apply_cycle_cycle_latest.json")
sanction_procedural_official_review_raw_cycle_strict_raw := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_CYCLE_STRICT_RAW", "1")
sanction_procedural_official_review_prepare_in := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PREPARE_IN", sanction_procedural_official_review_template_out)
sanction_procedural_official_review_prepare_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PREPARE_OUT", "docs/etl/sprints/AI-OPS-178/exports/sanction_procedural_official_review_apply_prepared_latest.csv")
sanction_procedural_official_review_prepare_rejected_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PREPARE_REJECTED_OUT", "docs/etl/sprints/AI-OPS-178/exports/sanction_procedural_official_review_apply_rejected_latest.csv")
sanction_procedural_official_review_prepare_summary_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PREPARE_SUMMARY_OUT", "docs/etl/sprints/AI-OPS-178/evidence/sanction_procedural_official_review_apply_prepare_latest.json")
sanction_procedural_official_review_prepare_strict := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PREPARE_STRICT", "0")
sanction_procedural_official_review_readiness_in := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_READINESS_IN", sanction_procedural_official_review_template_out)
sanction_procedural_official_review_readiness_tolerance := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_READINESS_TOLERANCE", "0.01")
sanction_procedural_official_review_readiness_queue_limit := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_READINESS_QUEUE_LIMIT", "0")
sanction_procedural_official_review_readiness_csv_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_READINESS_CSV_OUT", "docs/etl/sprints/AI-OPS-176/exports/sanction_procedural_official_review_apply_readiness_queue_latest.csv")
sanction_procedural_official_review_readiness_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_READINESS_OUT", "docs/etl/sprints/AI-OPS-176/evidence/sanction_procedural_official_review_apply_readiness_latest.json")
sanction_procedural_official_review_readiness_strict := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_READINESS_STRICT", "1")
sanction_procedural_official_review_apply_cycle_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_APPLY_CYCLE_OUT", "docs/etl/sprints/AI-OPS-177/evidence/sanction_procedural_official_review_apply_cycle_latest.json")
sanction_procedural_official_review_apply_cycle_status_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_APPLY_CYCLE_STATUS_OUT", "docs/etl/sprints/AI-OPS-177/evidence/sanction_procedural_official_review_apply_cycle_status_latest.json")
sanction_procedural_official_review_prepare_cycle_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PREPARE_CYCLE_OUT", "docs/etl/sprints/AI-OPS-179/evidence/sanction_procedural_official_review_prepare_apply_cycle_latest.json")
sanction_procedural_official_review_prepare_cycle_cycle_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PREPARE_CYCLE_CYCLE_OUT", "docs/etl/sprints/AI-OPS-179/evidence/sanction_procedural_official_review_prepare_apply_cycle_cycle_latest.json")
sanction_procedural_official_review_prepare_cycle_status_out := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PREPARE_CYCLE_STATUS_OUT", "docs/etl/sprints/AI-OPS-179/evidence/sanction_procedural_official_review_prepare_apply_cycle_status_latest.json")
sanction_procedural_official_review_prepare_cycle_strict_prepare := env_var_or_default("SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PREPARE_CYCLE_STRICT_PREPARE", "1")
sanction_volume_pilot_seed := env_var_or_default("SANCTION_VOLUME_PILOT_SEED", "etl/data/seeds/sanction_volume_pilot_seed_v1.json")
sanction_volume_pilot_source_id := env_var_or_default("SANCTION_VOLUME_PILOT_SOURCE_ID", "boe_api_legal")
sanction_volume_pilot_validate_out := env_var_or_default("SANCTION_VOLUME_PILOT_VALIDATE_OUT", "docs/etl/sprints/AI-OPS-117/evidence/sanction_volume_pilot_validate_latest.json")
sanction_volume_pilot_import_out := env_var_or_default("SANCTION_VOLUME_PILOT_IMPORT_OUT", "docs/etl/sprints/AI-OPS-117/evidence/sanction_volume_pilot_import_latest.json")
sanction_volume_pilot_status_out := env_var_or_default("SANCTION_VOLUME_PILOT_STATUS_OUT", "docs/etl/sprints/AI-OPS-117/evidence/sanction_volume_pilot_status_latest.json")
sanction_volume_pilot_status_top_n := env_var_or_default("SANCTION_VOLUME_PILOT_STATUS_TOP_N", "10")
sanction_volume_pilot_status_dossier_limit := env_var_or_default("SANCTION_VOLUME_PILOT_STATUS_DOSSIER_LIMIT", "5")
sanction_volume_pilot_status_sample_limit := env_var_or_default("SANCTION_VOLUME_PILOT_STATUS_SAMPLE_LIMIT", "20")
liberty_restrictions_seed := env_var_or_default("LIBERTY_RESTRICTIONS_SEED", "etl/data/seeds/liberty_restrictions_seed_v1.json")
liberty_restrictions_source_id := env_var_or_default("LIBERTY_RESTRICTIONS_SOURCE_ID", "boe_api_legal")
liberty_restrictions_validate_out := env_var_or_default("LIBERTY_RESTRICTIONS_VALIDATE_OUT", "docs/etl/sprints/AI-OPS-118/evidence/liberty_restrictions_validate_latest.json")
liberty_restrictions_import_out := env_var_or_default("LIBERTY_RESTRICTIONS_IMPORT_OUT", "docs/etl/sprints/AI-OPS-118/evidence/liberty_restrictions_import_latest.json")
liberty_restrictions_status_out := env_var_or_default("LIBERTY_RESTRICTIONS_STATUS_OUT", "docs/etl/sprints/AI-OPS-118/evidence/liberty_restrictions_status_latest.json")
liberty_restrictions_status_top_n := env_var_or_default("LIBERTY_RESTRICTIONS_STATUS_TOP_N", "20")
liberty_restrictions_norms_classified_min := env_var_or_default("LIBERTY_RESTRICTIONS_NORMS_CLASSIFIED_MIN", "0.8")
liberty_restrictions_fragments_irlc_min := env_var_or_default("LIBERTY_RESTRICTIONS_FRAGMENTS_IRLC_MIN", "0.6")
liberty_restrictions_fragments_accountability_min := env_var_or_default("LIBERTY_RESTRICTIONS_FRAGMENTS_ACCOUNTABILITY_MIN", "0.6")
liberty_restrictions_rights_with_data_min := env_var_or_default("LIBERTY_RESTRICTIONS_RIGHTS_WITH_DATA_MIN", "1.0")
liberty_restrictions_sources_with_assessments_min_pct := env_var_or_default("LIBERTY_RESTRICTIONS_SOURCES_WITH_ASSESSMENTS_MIN_PCT", "1.0")
liberty_restrictions_scopes_with_assessments_min_pct := env_var_or_default("LIBERTY_RESTRICTIONS_SCOPES_WITH_ASSESSMENTS_MIN_PCT", "1.0")
liberty_restrictions_min_assessment_sources := env_var_or_default("LIBERTY_RESTRICTIONS_MIN_ASSESSMENT_SOURCES", "1")
liberty_restrictions_min_assessment_scopes := env_var_or_default("LIBERTY_RESTRICTIONS_MIN_ASSESSMENT_SCOPES", "1")
liberty_restrictions_sources_with_dual_coverage_min_pct := env_var_or_default("LIBERTY_RESTRICTIONS_SOURCES_WITH_DUAL_COVERAGE_MIN_PCT", "1.0")
liberty_restrictions_scopes_with_dual_coverage_min_pct := env_var_or_default("LIBERTY_RESTRICTIONS_SCOPES_WITH_DUAL_COVERAGE_MIN_PCT", "1.0")
liberty_restrictions_min_dual_coverage_sources := env_var_or_default("LIBERTY_RESTRICTIONS_MIN_DUAL_COVERAGE_SOURCES", "1")
liberty_restrictions_min_dual_coverage_scopes := env_var_or_default("LIBERTY_RESTRICTIONS_MIN_DUAL_COVERAGE_SCOPES", "1")
liberty_restrictions_accountability_primary_evidence_min_pct := env_var_or_default("LIBERTY_RESTRICTIONS_ACCOUNTABILITY_PRIMARY_EVIDENCE_MIN_PCT", "1.0")
liberty_restrictions_min_accountability_primary_evidence_edges := env_var_or_default("LIBERTY_RESTRICTIONS_MIN_ACCOUNTABILITY_PRIMARY_EVIDENCE_EDGES", "1")
liberty_restrictions_status_heartbeat_path := env_var_or_default("LIBERTY_RESTRICTIONS_STATUS_HEARTBEAT_PATH", "docs/etl/runs/liberty_restrictions_status_heartbeat.jsonl")
liberty_restrictions_status_heartbeat_out := env_var_or_default("LIBERTY_RESTRICTIONS_STATUS_HEARTBEAT_OUT", "docs/etl/sprints/AI-OPS-123/evidence/liberty_restrictions_status_heartbeat_latest.json")
liberty_restrictions_status_heartbeat_window := env_var_or_default("LIBERTY_RESTRICTIONS_STATUS_HEARTBEAT_WINDOW", "20")
liberty_restrictions_status_heartbeat_max_failed := env_var_or_default("LIBERTY_RESTRICTIONS_STATUS_HEARTBEAT_MAX_FAILED", "0")
liberty_restrictions_status_heartbeat_max_failed_rate_pct := env_var_or_default("LIBERTY_RESTRICTIONS_STATUS_HEARTBEAT_MAX_FAILED_RATE_PCT", "0")
liberty_restrictions_status_heartbeat_max_focus_gate_failed := env_var_or_default("LIBERTY_RESTRICTIONS_STATUS_HEARTBEAT_MAX_FOCUS_GATE_FAILED", "0")
liberty_restrictions_status_heartbeat_max_focus_gate_failed_rate_pct := env_var_or_default("LIBERTY_RESTRICTIONS_STATUS_HEARTBEAT_MAX_FOCUS_GATE_FAILED_RATE_PCT", "0")
liberty_restrictions_status_heartbeat_max_norms_classified_gate_failed := env_var_or_default("LIBERTY_RESTRICTIONS_STATUS_HEARTBEAT_MAX_NORMS_CLASSIFIED_GATE_FAILED", "0")
liberty_restrictions_status_heartbeat_max_fragments_irlc_gate_failed := env_var_or_default("LIBERTY_RESTRICTIONS_STATUS_HEARTBEAT_MAX_FRAGMENTS_IRLC_GATE_FAILED", "0")
liberty_restrictions_status_heartbeat_max_fragments_accountability_gate_failed := env_var_or_default("LIBERTY_RESTRICTIONS_STATUS_HEARTBEAT_MAX_FRAGMENTS_ACCOUNTABILITY_GATE_FAILED", "0")
liberty_restrictions_status_heartbeat_max_rights_with_data_gate_failed := env_var_or_default("LIBERTY_RESTRICTIONS_STATUS_HEARTBEAT_MAX_RIGHTS_WITH_DATA_GATE_FAILED", "0")
liberty_restrictions_status_heartbeat_max_source_representativity_gate_failed := env_var_or_default("LIBERTY_RESTRICTIONS_STATUS_HEARTBEAT_MAX_SOURCE_REPRESENTATIVITY_GATE_FAILED", "0")
liberty_restrictions_status_heartbeat_max_scope_representativity_gate_failed := env_var_or_default("LIBERTY_RESTRICTIONS_STATUS_HEARTBEAT_MAX_SCOPE_REPRESENTATIVITY_GATE_FAILED", "0")
liberty_restrictions_status_heartbeat_max_source_dual_coverage_gate_failed := env_var_or_default("LIBERTY_RESTRICTIONS_STATUS_HEARTBEAT_MAX_SOURCE_DUAL_COVERAGE_GATE_FAILED", "0")
liberty_restrictions_status_heartbeat_max_scope_dual_coverage_gate_failed := env_var_or_default("LIBERTY_RESTRICTIONS_STATUS_HEARTBEAT_MAX_SCOPE_DUAL_COVERAGE_GATE_FAILED", "0")
liberty_restrictions_status_heartbeat_max_accountability_primary_evidence_gate_failed := env_var_or_default("LIBERTY_RESTRICTIONS_STATUS_HEARTBEAT_MAX_ACCOUNTABILITY_PRIMARY_EVIDENCE_GATE_FAILED", "0")
liberty_restrictions_status_heartbeat_window_out := env_var_or_default("LIBERTY_RESTRICTIONS_STATUS_HEARTBEAT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-123/evidence/liberty_restrictions_status_heartbeat_window_latest.json")
liberty_focus_scope_changed_paths := env_var_or_default("LIBERTY_FOCUS_SCOPE_CHANGED_PATHS", "docs/etl/runs/liberty_focus_changed_paths.txt")
liberty_focus_scope_out := env_var_or_default("LIBERTY_FOCUS_SCOPE_OUT", "docs/etl/sprints/AI-OPS-129/evidence/liberty_focus_scope_latest.json")
liberty_restrictions_snapshot_out := env_var_or_default("LIBERTY_RESTRICTIONS_SNAPSHOT_OUT", "docs/etl/sprints/AI-OPS-118/exports/liberty_restrictions_snapshot_latest.json")
liberty_restrictions_snapshot_prev := env_var_or_default("LIBERTY_RESTRICTIONS_SNAPSHOT_PREV", "")
liberty_restrictions_snapshot_diff_out := env_var_or_default("LIBERTY_RESTRICTIONS_SNAPSHOT_DIFF_OUT", "docs/etl/sprints/AI-OPS-124/evidence/liberty_restrictions_snapshot_diff_latest.json")
liberty_restrictions_snapshot_changelog_jsonl := env_var_or_default("LIBERTY_RESTRICTIONS_SNAPSHOT_CHANGELOG_JSONL", "docs/etl/runs/liberty_restrictions_snapshot_changelog.jsonl")
liberty_restrictions_snapshot_changelog_out := env_var_or_default("LIBERTY_RESTRICTIONS_SNAPSHOT_CHANGELOG_OUT", "docs/etl/sprints/AI-OPS-124/evidence/liberty_restrictions_snapshot_changelog_latest.json")
liberty_restrictions_snapshot_irlc_parquet_out := env_var_or_default("LIBERTY_RESTRICTIONS_SNAPSHOT_IRLC_PARQUET_OUT", "docs/etl/sprints/AI-OPS-124/exports/irlc_by_fragment_latest.parquet")
liberty_restrictions_snapshot_accountability_parquet_out := env_var_or_default("LIBERTY_RESTRICTIONS_SNAPSHOT_ACCOUNTABILITY_PARQUET_OUT", "docs/etl/sprints/AI-OPS-124/exports/accountability_edges_latest.parquet")
liberty_restrictions_snapshot_parquet_compression := env_var_or_default("LIBERTY_RESTRICTIONS_SNAPSHOT_PARQUET_COMPRESSION", "zstd")
liberty_atlas_publish_snapshot_json := env_var_or_default("LIBERTY_ATLAS_PUBLISH_SNAPSHOT_JSON", "docs/etl/sprints/AI-OPS-118/exports/liberty_restrictions_snapshot_latest.json")
liberty_atlas_publish_irlc_parquet := env_var_or_default("LIBERTY_ATLAS_PUBLISH_IRLC_PARQUET", "docs/etl/sprints/AI-OPS-124/exports/irlc_by_fragment_latest.parquet")
liberty_atlas_publish_accountability_parquet := env_var_or_default("LIBERTY_ATLAS_PUBLISH_ACCOUNTABILITY_PARQUET", "docs/etl/sprints/AI-OPS-124/exports/accountability_edges_latest.parquet")
liberty_atlas_publish_diff_json := env_var_or_default("LIBERTY_ATLAS_PUBLISH_DIFF_JSON", "docs/etl/sprints/AI-OPS-124/evidence/liberty_restrictions_snapshot_diff_latest.json")
liberty_atlas_publish_changelog_entry_json := env_var_or_default("LIBERTY_ATLAS_PUBLISH_CHANGELOG_ENTRY_JSON", "docs/etl/sprints/AI-OPS-124/evidence/liberty_restrictions_snapshot_changelog_latest.json")
liberty_atlas_publish_changelog_history_jsonl := env_var_or_default("LIBERTY_ATLAS_PUBLISH_CHANGELOG_HISTORY_JSONL", "docs/etl/runs/liberty_restrictions_snapshot_changelog.jsonl")
liberty_atlas_published_dir := env_var_or_default("LIBERTY_ATLAS_PUBLISHED_DIR", "etl/data/published")
liberty_atlas_publish_gh_pages_out := env_var_or_default("LIBERTY_ATLAS_PUBLISH_GH_PAGES_OUT", "ui/gh-pages-next/public/explorer-sources/data/liberty-atlas-release.json")
liberty_atlas_publish_out := env_var_or_default("LIBERTY_ATLAS_PUBLISH_OUT", "docs/etl/sprints/AI-OPS-125/evidence/liberty_atlas_publish_latest.json")
liberty_atlas_publish_allow_missing := env_var_or_default("LIBERTY_ATLAS_PUBLISH_ALLOW_MISSING", "0")
liberty_atlas_release_latest_json := env_var_or_default("LIBERTY_ATLAS_RELEASE_LATEST_JSON", "etl/data/published/liberty-restrictions-atlas-release-latest.json")
liberty_atlas_changelog_continuity_out := env_var_or_default("LIBERTY_ATLAS_CHANGELOG_CONTINUITY_OUT", "docs/etl/sprints/AI-OPS-125/evidence/liberty_atlas_changelog_continuity_latest.json")
liberty_atlas_release_heartbeat_path := env_var_or_default("LIBERTY_ATLAS_RELEASE_HEARTBEAT_PATH", "docs/etl/runs/liberty_atlas_release_heartbeat.jsonl")
liberty_atlas_release_heartbeat_out := env_var_or_default("LIBERTY_ATLAS_RELEASE_HEARTBEAT_OUT", "docs/etl/sprints/AI-OPS-126/evidence/liberty_atlas_release_heartbeat_latest.json")
liberty_atlas_release_heartbeat_window := env_var_or_default("LIBERTY_ATLAS_RELEASE_HEARTBEAT_WINDOW", "20")
liberty_atlas_release_heartbeat_window_out := env_var_or_default("LIBERTY_ATLAS_RELEASE_HEARTBEAT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-126/evidence/liberty_atlas_release_heartbeat_window_latest.json")
liberty_atlas_release_heartbeat_window_min_run_at := env_var_or_default("LIBERTY_ATLAS_RELEASE_WINDOW_MIN_RUN_AT", "")
liberty_atlas_release_max_snapshot_age_days := env_var_or_default("LIBERTY_ATLAS_RELEASE_MAX_SNAPSHOT_AGE_DAYS", "14")
liberty_atlas_release_expected_snapshot_date := env_var_or_default("LIBERTY_ATLAS_RELEASE_EXPECTED_SNAPSHOT_DATE", "")
liberty_atlas_release_hf_json := env_var_or_default("LIBERTY_ATLAS_RELEASE_HF_JSON", "")
liberty_atlas_release_hf_latest_url := env_var_or_default("LIBERTY_ATLAS_RELEASE_HF_LATEST_URL", "")
liberty_atlas_release_hf_dataset_repo := env_var_or_default("LIBERTY_ATLAS_RELEASE_HF_DATASET_REPO", "")
liberty_atlas_release_hf_username := env_var_or_default("LIBERTY_ATLAS_RELEASE_HF_USERNAME", "")
liberty_atlas_release_hf_timeout := env_var_or_default("LIBERTY_ATLAS_RELEASE_HF_TIMEOUT", "20")
liberty_atlas_release_allow_hf_unavailable := env_var_or_default("LIBERTY_ATLAS_RELEASE_ALLOW_HF_UNAVAILABLE", "1")
liberty_atlas_release_window_max_failed := env_var_or_default("LIBERTY_ATLAS_RELEASE_WINDOW_MAX_FAILED", "0")
liberty_atlas_release_window_max_degraded := env_var_or_default("LIBERTY_ATLAS_RELEASE_WINDOW_MAX_DEGRADED", "0")
liberty_atlas_release_window_max_stale_alerts := env_var_or_default("LIBERTY_ATLAS_RELEASE_WINDOW_MAX_STALE_ALERTS", "0")
liberty_atlas_release_window_max_drift_alerts := env_var_or_default("LIBERTY_ATLAS_RELEASE_WINDOW_MAX_DRIFT_ALERTS", "0")
liberty_atlas_release_window_max_hf_unavailable := env_var_or_default("LIBERTY_ATLAS_RELEASE_WINDOW_MAX_HF_UNAVAILABLE", "0")
liberty_proportionality_seed := env_var_or_default("LIBERTY_PROPORTIONALITY_SEED", "etl/data/seeds/liberty_proportionality_seed_v1.json")
liberty_proportionality_source_id := env_var_or_default("LIBERTY_PROPORTIONALITY_SOURCE_ID", "boe_api_legal")
liberty_proportionality_validate_out := env_var_or_default("LIBERTY_PROPORTIONALITY_VALIDATE_OUT", "docs/etl/sprints/AI-OPS-119/evidence/liberty_proportionality_validate_latest.json")
liberty_proportionality_import_out := env_var_or_default("LIBERTY_PROPORTIONALITY_IMPORT_OUT", "docs/etl/sprints/AI-OPS-119/evidence/liberty_proportionality_import_latest.json")
liberty_proportionality_status_out := env_var_or_default("LIBERTY_PROPORTIONALITY_STATUS_OUT", "docs/etl/sprints/AI-OPS-119/evidence/liberty_proportionality_status_latest.json")
liberty_proportionality_target_coverage_min := env_var_or_default("LIBERTY_PROPORTIONALITY_TARGET_COVERAGE_MIN", "0.6")
liberty_proportionality_objective_defined_min := env_var_or_default("LIBERTY_PROPORTIONALITY_OBJECTIVE_DEFINED_MIN", "0.8")
liberty_proportionality_indicator_defined_min := env_var_or_default("LIBERTY_PROPORTIONALITY_INDICATOR_DEFINED_MIN", "0.6")
liberty_proportionality_alternatives_min := env_var_or_default("LIBERTY_PROPORTIONALITY_ALTERNATIVES_MIN", "0.4")
liberty_proportionality_low_score_threshold := env_var_or_default("LIBERTY_PROPORTIONALITY_LOW_SCORE_THRESHOLD", "50")
liberty_direct_accountability_scores_out := env_var_or_default("LIBERTY_DIRECT_ACCOUNTABILITY_SCORES_OUT", "docs/etl/sprints/AI-OPS-119/evidence/liberty_direct_accountability_scores_latest.json")
liberty_direct_accountability_top_n := env_var_or_default("LIBERTY_DIRECT_ACCOUNTABILITY_TOP_N", "20")
liberty_direct_accountability_coverage_min := env_var_or_default("LIBERTY_DIRECT_ACCOUNTABILITY_COVERAGE_MIN", "0.6")
liberty_direct_accountability_primary_evidence_min_pct := env_var_or_default("LIBERTY_DIRECT_ACCOUNTABILITY_PRIMARY_EVIDENCE_MIN_PCT", "1.0")
liberty_direct_accountability_min_primary_evidence_edges := env_var_or_default("LIBERTY_DIRECT_ACCOUNTABILITY_MIN_PRIMARY_EVIDENCE_EDGES", "1")
liberty_personal_accountability_scores_out := env_var_or_default("LIBERTY_PERSONAL_ACCOUNTABILITY_SCORES_OUT", "docs/etl/sprints/AI-OPS-138/evidence/liberty_personal_accountability_scores_latest.json")
liberty_personal_accountability_top_n := env_var_or_default("LIBERTY_PERSONAL_ACCOUNTABILITY_TOP_N", "20")
liberty_personal_confidence_min := env_var_or_default("LIBERTY_PERSONAL_CONFIDENCE_MIN", "0.55")
liberty_personal_max_distance := env_var_or_default("LIBERTY_PERSONAL_MAX_DISTANCE", "2")
liberty_personal_fragment_coverage_min := env_var_or_default("LIBERTY_PERSONAL_FRAGMENT_COVERAGE_MIN", "0.5")
liberty_personal_primary_evidence_min_pct := env_var_or_default("LIBERTY_PERSONAL_PRIMARY_EVIDENCE_MIN_PCT", "1.0")
liberty_personal_min_primary_evidence_edges := env_var_or_default("LIBERTY_PERSONAL_MIN_PRIMARY_EVIDENCE_EDGES", "1")
liberty_personal_indirect_window_min_pct := env_var_or_default("LIBERTY_PERSONAL_INDIRECT_WINDOW_MIN_PCT", "1.0")
liberty_personal_min_indirect_window_edges := env_var_or_default("LIBERTY_PERSONAL_MIN_INDIRECT_WINDOW_EDGES", "1")
liberty_personal_indirect_identity_resolution_min_pct := env_var_or_default("LIBERTY_PERSONAL_INDIRECT_IDENTITY_RESOLUTION_MIN_PCT", "0.0")
liberty_personal_min_indirect_identity_resolution_edges := env_var_or_default("LIBERTY_PERSONAL_MIN_INDIRECT_IDENTITY_RESOLUTION_EDGES", "1")
liberty_personal_indirect_non_manual_alias_resolution_min_pct := env_var_or_default("LIBERTY_PERSONAL_INDIRECT_NON_MANUAL_ALIAS_RESOLUTION_MIN_PCT", "0.0")
liberty_personal_min_indirect_non_manual_alias_resolution_edges := env_var_or_default("LIBERTY_PERSONAL_MIN_INDIRECT_NON_MANUAL_ALIAS_RESOLUTION_EDGES", "1")
liberty_personal_manual_alias_share_max := env_var_or_default("LIBERTY_PERSONAL_MANUAL_ALIAS_SHARE_MAX", "1.0")
liberty_personal_min_alias_rows_for_manual_share_gate := env_var_or_default("LIBERTY_PERSONAL_MIN_ALIAS_ROWS_FOR_MANUAL_SHARE_GATE", "1")
liberty_personal_official_alias_share_min_pct := env_var_or_default("LIBERTY_PERSONAL_OFFICIAL_ALIAS_SHARE_MIN_PCT", "0.0")
liberty_personal_min_alias_rows_for_official_share_gate := env_var_or_default("LIBERTY_PERSONAL_MIN_ALIAS_ROWS_FOR_OFFICIAL_SHARE_GATE", "1")
liberty_personal_official_alias_evidence_min_pct := env_var_or_default("LIBERTY_PERSONAL_OFFICIAL_ALIAS_EVIDENCE_MIN_PCT", "1.0")
liberty_personal_min_official_alias_rows_for_evidence_gate := env_var_or_default("LIBERTY_PERSONAL_MIN_OFFICIAL_ALIAS_ROWS_FOR_EVIDENCE_GATE", "1")
liberty_personal_official_alias_source_record_min_pct := env_var_or_default("LIBERTY_PERSONAL_OFFICIAL_ALIAS_SOURCE_RECORD_MIN_PCT", "1.0")
liberty_personal_min_official_alias_rows_for_source_record_gate := env_var_or_default("LIBERTY_PERSONAL_MIN_OFFICIAL_ALIAS_ROWS_FOR_SOURCE_RECORD_GATE", "1")
liberty_personal_min_persons_scored := env_var_or_default("LIBERTY_PERSONAL_MIN_PERSONS_SCORED", "1")
liberty_person_identity_seed := env_var_or_default("LIBERTY_PERSON_IDENTITY_SEED", "etl/data/seeds/liberty_person_identity_resolution_seed_v1.json")
liberty_person_identity_source_id := env_var_or_default("LIBERTY_PERSON_IDENTITY_SOURCE_ID", "boe_api_legal")
liberty_person_identity_validate_out := env_var_or_default("LIBERTY_PERSON_IDENTITY_VALIDATE_OUT", "docs/etl/sprints/AI-OPS-143/evidence/liberty_person_identity_validate_latest.json")
liberty_person_identity_import_out := env_var_or_default("LIBERTY_PERSON_IDENTITY_IMPORT_OUT", "docs/etl/sprints/AI-OPS-143/evidence/liberty_person_identity_import_latest.json")
liberty_person_identity_resolution_queue_out := env_var_or_default("LIBERTY_PERSON_IDENTITY_RESOLUTION_QUEUE_OUT", "docs/etl/sprints/AI-OPS-143/evidence/liberty_person_identity_resolution_queue_latest.json")
liberty_person_identity_resolution_queue_csv_out := env_var_or_default("LIBERTY_PERSON_IDENTITY_RESOLUTION_QUEUE_CSV_OUT", "docs/etl/sprints/AI-OPS-143/exports/liberty_person_identity_resolution_queue_latest.csv")
liberty_person_identity_manual_upgrade_queue_csv_out := env_var_or_default("LIBERTY_PERSON_IDENTITY_MANUAL_UPGRADE_QUEUE_CSV_OUT", "docs/etl/sprints/AI-OPS-144/exports/liberty_person_identity_manual_upgrade_queue_latest.csv")
liberty_person_identity_official_evidence_upgrade_queue_csv_out := env_var_or_default("LIBERTY_PERSON_IDENTITY_OFFICIAL_EVIDENCE_UPGRADE_QUEUE_CSV_OUT", "docs/etl/sprints/AI-OPS-149/exports/liberty_person_identity_official_alias_evidence_upgrade_queue_latest.csv")
liberty_person_identity_official_source_record_upgrade_queue_csv_out := env_var_or_default("LIBERTY_PERSON_IDENTITY_OFFICIAL_SOURCE_RECORD_UPGRADE_QUEUE_CSV_OUT", "docs/etl/sprints/AI-OPS-149/exports/liberty_person_identity_official_alias_source_record_upgrade_queue_latest.csv")
liberty_person_identity_official_upgrade_review_queue_out := env_var_or_default("LIBERTY_PERSON_IDENTITY_OFFICIAL_UPGRADE_REVIEW_QUEUE_OUT", "docs/etl/sprints/AI-OPS-150/exports/liberty_person_identity_official_upgrade_review_queue_latest.csv")
liberty_person_identity_official_upgrade_review_queue_summary_out := env_var_or_default("LIBERTY_PERSON_IDENTITY_OFFICIAL_UPGRADE_REVIEW_QUEUE_SUMMARY_OUT", "docs/etl/sprints/AI-OPS-150/evidence/liberty_person_identity_official_upgrade_review_queue_latest.json")
liberty_person_identity_official_upgrade_review_queue_actionable_out := env_var_or_default("LIBERTY_PERSON_IDENTITY_OFFICIAL_UPGRADE_REVIEW_QUEUE_ACTIONABLE_OUT", "docs/etl/sprints/AI-OPS-153/exports/liberty_person_identity_official_upgrade_review_queue_actionable_latest.csv")
liberty_person_identity_official_upgrade_review_queue_actionable_summary_out := env_var_or_default("LIBERTY_PERSON_IDENTITY_OFFICIAL_UPGRADE_REVIEW_QUEUE_ACTIONABLE_SUMMARY_OUT", "docs/etl/sprints/AI-OPS-153/evidence/liberty_person_identity_official_upgrade_review_queue_actionable_latest.json")
liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_path := env_var_or_default("LIBERTY_PERSON_IDENTITY_OFFICIAL_UPGRADE_REVIEW_QUEUE_ACTIONABLE_HEARTBEAT_PATH", "docs/etl/runs/liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat.jsonl")
liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_out := env_var_or_default("LIBERTY_PERSON_IDENTITY_OFFICIAL_UPGRADE_REVIEW_QUEUE_ACTIONABLE_HEARTBEAT_OUT", "docs/etl/sprints/AI-OPS-154/evidence/liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_latest.json")
liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_window := env_var_or_default("LIBERTY_PERSON_IDENTITY_OFFICIAL_UPGRADE_REVIEW_QUEUE_ACTIONABLE_HEARTBEAT_WINDOW", "20")
liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_window_max_failed := env_var_or_default("LIBERTY_PERSON_IDENTITY_OFFICIAL_UPGRADE_REVIEW_QUEUE_ACTIONABLE_HEARTBEAT_WINDOW_MAX_FAILED", "0")
liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_window_max_failed_rate_pct := env_var_or_default("LIBERTY_PERSON_IDENTITY_OFFICIAL_UPGRADE_REVIEW_QUEUE_ACTIONABLE_HEARTBEAT_WINDOW_MAX_FAILED_RATE_PCT", "0")
liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_window_max_actionable_nonempty_runs := env_var_or_default("LIBERTY_PERSON_IDENTITY_OFFICIAL_UPGRADE_REVIEW_QUEUE_ACTIONABLE_HEARTBEAT_WINDOW_MAX_ACTIONABLE_NONEMPTY_RUNS", "0")
liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_window_max_actionable_nonempty_runs_rate_pct := env_var_or_default("LIBERTY_PERSON_IDENTITY_OFFICIAL_UPGRADE_REVIEW_QUEUE_ACTIONABLE_HEARTBEAT_WINDOW_MAX_ACTIONABLE_NONEMPTY_RUNS_RATE_PCT", "0")
liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_window_out := env_var_or_default("LIBERTY_PERSON_IDENTITY_OFFICIAL_UPGRADE_REVIEW_QUEUE_ACTIONABLE_HEARTBEAT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-154/evidence/liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_window_latest.json")
liberty_person_identity_official_upgrade_reviews_in := env_var_or_default("LIBERTY_PERSON_IDENTITY_OFFICIAL_UPGRADE_REVIEWS_IN", "docs/etl/sprints/AI-OPS-150/exports/liberty_person_identity_official_upgrade_review_queue_latest.csv")
liberty_person_identity_seed_review_out := env_var_or_default("LIBERTY_PERSON_IDENTITY_SEED_REVIEW_OUT", "docs/etl/sprints/AI-OPS-150/exports/liberty_person_identity_resolution_seed_reviewed_latest.json")
liberty_person_identity_official_upgrade_apply_out := env_var_or_default("LIBERTY_PERSON_IDENTITY_OFFICIAL_UPGRADE_APPLY_OUT", "docs/etl/sprints/AI-OPS-150/evidence/liberty_person_identity_official_upgrade_apply_latest.json")
liberty_person_identity_resolution_queue_limit := env_var_or_default("LIBERTY_PERSON_IDENTITY_RESOLUTION_QUEUE_LIMIT", "0")
liberty_person_identity_resolution_min_pct := env_var_or_default("LIBERTY_PERSON_IDENTITY_RESOLUTION_MIN_PCT", "0.0")
liberty_person_identity_resolution_min_edges := env_var_or_default("LIBERTY_PERSON_IDENTITY_RESOLUTION_MIN_EDGES", "1")
liberty_person_identity_non_manual_alias_resolution_min_pct := env_var_or_default("LIBERTY_PERSON_IDENTITY_NON_MANUAL_ALIAS_RESOLUTION_MIN_PCT", "0.0")
liberty_person_identity_non_manual_alias_resolution_min_edges := env_var_or_default("LIBERTY_PERSON_IDENTITY_NON_MANUAL_ALIAS_RESOLUTION_MIN_EDGES", "1")
liberty_person_identity_manual_alias_share_max := env_var_or_default("LIBERTY_PERSON_IDENTITY_MANUAL_ALIAS_SHARE_MAX", "1.0")
liberty_person_identity_min_alias_rows_for_manual_share_gate := env_var_or_default("LIBERTY_PERSON_IDENTITY_MIN_ALIAS_ROWS_FOR_MANUAL_SHARE_GATE", "1")
liberty_person_identity_official_alias_share_min_pct := env_var_or_default("LIBERTY_PERSON_IDENTITY_OFFICIAL_ALIAS_SHARE_MIN_PCT", "0.0")
liberty_person_identity_min_alias_rows_for_official_share_gate := env_var_or_default("LIBERTY_PERSON_IDENTITY_MIN_ALIAS_ROWS_FOR_OFFICIAL_SHARE_GATE", "1")
liberty_person_identity_official_alias_evidence_min_pct := env_var_or_default("LIBERTY_PERSON_IDENTITY_OFFICIAL_ALIAS_EVIDENCE_MIN_PCT", "1.0")
liberty_person_identity_min_official_alias_rows_for_evidence_gate := env_var_or_default("LIBERTY_PERSON_IDENTITY_MIN_OFFICIAL_ALIAS_ROWS_FOR_EVIDENCE_GATE", "1")
liberty_person_identity_official_alias_source_record_min_pct := env_var_or_default("LIBERTY_PERSON_IDENTITY_OFFICIAL_ALIAS_SOURCE_RECORD_MIN_PCT", "1.0")
liberty_person_identity_min_official_alias_rows_for_source_record_gate := env_var_or_default("LIBERTY_PERSON_IDENTITY_MIN_OFFICIAL_ALIAS_ROWS_FOR_SOURCE_RECORD_GATE", "1")
liberty_enforcement_seed := env_var_or_default("LIBERTY_ENFORCEMENT_SEED", "etl/data/seeds/liberty_enforcement_seed_v1.json")
liberty_enforcement_source_id := env_var_or_default("LIBERTY_ENFORCEMENT_SOURCE_ID", "boe_api_legal")
liberty_enforcement_validate_out := env_var_or_default("LIBERTY_ENFORCEMENT_VALIDATE_OUT", "docs/etl/sprints/AI-OPS-120/evidence/liberty_enforcement_validate_latest.json")
liberty_enforcement_import_out := env_var_or_default("LIBERTY_ENFORCEMENT_IMPORT_OUT", "docs/etl/sprints/AI-OPS-120/evidence/liberty_enforcement_import_latest.json")
liberty_enforcement_status_out := env_var_or_default("LIBERTY_ENFORCEMENT_STATUS_OUT", "docs/etl/sprints/AI-OPS-120/evidence/liberty_enforcement_status_latest.json")
liberty_enforcement_top_n := env_var_or_default("LIBERTY_ENFORCEMENT_TOP_N", "20")
liberty_enforcement_sanction_spread_min := env_var_or_default("LIBERTY_ENFORCEMENT_SANCTION_SPREAD_MIN", "0.35")
liberty_enforcement_annulment_spread_min := env_var_or_default("LIBERTY_ENFORCEMENT_ANNULMENT_SPREAD_MIN", "0.08")
liberty_enforcement_delay_spread_days_min := env_var_or_default("LIBERTY_ENFORCEMENT_DELAY_SPREAD_DAYS_MIN", "45")
liberty_enforcement_target_coverage_min := env_var_or_default("LIBERTY_ENFORCEMENT_TARGET_COVERAGE_MIN", "0.6")
liberty_enforcement_multi_territory_min := env_var_or_default("LIBERTY_ENFORCEMENT_MULTI_TERRITORY_MIN", "0.6")
liberty_indirect_seed := env_var_or_default("LIBERTY_INDIRECT_SEED", "etl/data/seeds/liberty_indirect_accountability_seed_v1.json")
liberty_indirect_source_id := env_var_or_default("LIBERTY_INDIRECT_SOURCE_ID", "boe_api_legal")
liberty_indirect_validate_out := env_var_or_default("LIBERTY_INDIRECT_VALIDATE_OUT", "docs/etl/sprints/AI-OPS-120/evidence/liberty_indirect_validate_latest.json")
liberty_indirect_import_out := env_var_or_default("LIBERTY_INDIRECT_IMPORT_OUT", "docs/etl/sprints/AI-OPS-120/evidence/liberty_indirect_import_latest.json")
liberty_indirect_status_out := env_var_or_default("LIBERTY_INDIRECT_STATUS_OUT", "docs/etl/sprints/AI-OPS-120/evidence/liberty_indirect_status_latest.json")
liberty_indirect_top_n := env_var_or_default("LIBERTY_INDIRECT_TOP_N", "20")
liberty_indirect_confidence_min := env_var_or_default("LIBERTY_INDIRECT_CONFIDENCE_MIN", "0.55")
liberty_indirect_max_distance := env_var_or_default("LIBERTY_INDIRECT_MAX_DISTANCE", "2")
liberty_indirect_fragment_coverage_min := env_var_or_default("LIBERTY_INDIRECT_FRAGMENT_COVERAGE_MIN", "0.5")
liberty_indirect_person_window_min := env_var_or_default("LIBERTY_INDIRECT_PERSON_WINDOW_MIN", "1.0")
liberty_indirect_min_person_window_edges := env_var_or_default("LIBERTY_INDIRECT_MIN_PERSON_WINDOW_EDGES", "1")
liberty_delegated_seed := env_var_or_default("LIBERTY_DELEGATED_SEED", "etl/data/seeds/liberty_delegated_enforcement_seed_v1.json")
liberty_delegated_source_id := env_var_or_default("LIBERTY_DELEGATED_SOURCE_ID", "boe_api_legal")
liberty_delegated_validate_out := env_var_or_default("LIBERTY_DELEGATED_VALIDATE_OUT", "docs/etl/sprints/AI-OPS-121/evidence/liberty_delegated_validate_latest.json")
liberty_delegated_import_out := env_var_or_default("LIBERTY_DELEGATED_IMPORT_OUT", "docs/etl/sprints/AI-OPS-121/evidence/liberty_delegated_import_latest.json")
liberty_delegated_status_out := env_var_or_default("LIBERTY_DELEGATED_STATUS_OUT", "docs/etl/sprints/AI-OPS-121/evidence/liberty_delegated_status_latest.json")
liberty_delegated_top_n := env_var_or_default("LIBERTY_DELEGATED_TOP_N", "20")
liberty_delegated_target_coverage_min := env_var_or_default("LIBERTY_DELEGATED_TARGET_COVERAGE_MIN", "0.6")
liberty_delegated_designated_actor_min := env_var_or_default("LIBERTY_DELEGATED_DESIGNATED_ACTOR_MIN", "0.5")
liberty_delegated_enforcement_evidence_min := env_var_or_default("LIBERTY_DELEGATED_ENFORCEMENT_EVIDENCE_MIN", "0.7")
liberty_delegated_person_queue_out := env_var_or_default("LIBERTY_DELEGATED_PERSON_QUEUE_OUT", "docs/etl/sprints/AI-OPS-277/evidence/liberty_delegated_person_window_queue_latest.json")
liberty_delegated_person_queue_csv_out := env_var_or_default("LIBERTY_DELEGATED_PERSON_QUEUE_CSV_OUT", "docs/etl/sprints/AI-OPS-277/exports/liberty_delegated_person_window_queue_latest.csv")
liberty_delegated_person_queue_limit := env_var_or_default("LIBERTY_DELEGATED_PERSON_QUEUE_LIMIT", "0")
liberty_delegated_person_queue_max_actionable_rows := env_var_or_default("LIBERTY_DELEGATED_PERSON_QUEUE_MAX_ACTIONABLE_ROWS", "-1")
liberty_delegated_person_queue_institution_terms := env_var_or_default("LIBERTY_DELEGATED_PERSON_QUEUE_INSTITUTION_TERMS", "ministerio,direccion,dirección,agencia,delegacion,delegación,delegaciones,subdelegacion,subdelegación,subdelegaciones,inspeccion,inspección,organismo,gobierno,dgt,aeat,itss")
liberty_delegated_review_queue_out := env_var_or_default("LIBERTY_DELEGATED_REVIEW_QUEUE_OUT", "docs/etl/sprints/AI-OPS-278/exports/liberty_delegated_person_window_review_queue_latest.csv")
liberty_delegated_review_summary_out := env_var_or_default("LIBERTY_DELEGATED_REVIEW_SUMMARY_OUT", "docs/etl/sprints/AI-OPS-278/evidence/liberty_delegated_person_window_review_queue_latest.json")
liberty_delegated_review_limit := env_var_or_default("LIBERTY_DELEGATED_REVIEW_LIMIT", "0")
liberty_delegated_review_seed_out := env_var_or_default("LIBERTY_DELEGATED_REVIEW_SEED_OUT", "docs/etl/sprints/AI-OPS-278/exports/liberty_delegated_enforcement_seed_review_out_latest.json")
liberty_delegated_review_in := env_var_or_default("LIBERTY_DELEGATED_REVIEW_IN", "docs/etl/sprints/AI-OPS-278/exports/liberty_delegated_person_window_review_queue_latest.csv")
liberty_delegated_review_apply_out := env_var_or_default("LIBERTY_DELEGATED_REVIEW_APPLY_OUT", "docs/etl/sprints/AI-OPS-278/evidence/liberty_delegated_person_window_review_apply_latest.json")
liberty_delegated_scrape_targets_out := env_var_or_default("LIBERTY_DELEGATED_SCRAPE_TARGETS_OUT", "docs/etl/sprints/AI-OPS-279/exports/liberty_delegated_person_window_scrape_targets_latest.csv")
liberty_delegated_scrape_targets_summary_out := env_var_or_default("LIBERTY_DELEGATED_SCRAPE_TARGETS_SUMMARY_OUT", "docs/etl/sprints/AI-OPS-279/evidence/liberty_delegated_person_window_scrape_targets_latest.json")
liberty_delegated_scrape_targets_limit := env_var_or_default("LIBERTY_DELEGATED_SCRAPE_TARGETS_LIMIT", "0")
liberty_delegated_scrape_targets_min_priority := env_var_or_default("LIBERTY_DELEGATED_SCRAPE_TARGETS_MIN_PRIORITY", "1")
liberty_delegated_scrape_targets_strict_min_targets := env_var_or_default("LIBERTY_DELEGATED_SCRAPE_TARGETS_STRICT_MIN_TARGETS", "1")
liberty_delegated_boe_candidates_targets_csv := env_var_or_default("LIBERTY_DELEGATED_BOE_CANDIDATES_TARGETS_CSV", "docs/etl/sprints/AI-OPS-279/exports/liberty_delegated_person_window_scrape_targets_latest.csv")
liberty_delegated_boe_candidates_out := env_var_or_default("LIBERTY_DELEGATED_BOE_CANDIDATES_OUT", "docs/etl/sprints/AI-OPS-280/exports/liberty_delegated_person_window_boe_candidates_latest.csv")
liberty_delegated_boe_candidates_summary_out := env_var_or_default("LIBERTY_DELEGATED_BOE_CANDIDATES_SUMMARY_OUT", "docs/etl/sprints/AI-OPS-280/evidence/liberty_delegated_person_window_boe_candidates_latest.json")
liberty_delegated_boe_candidates_top_results := env_var_or_default("LIBERTY_DELEGATED_BOE_CANDIDATES_TOP_RESULTS", "5")
liberty_delegated_boe_candidates_timeout := env_var_or_default("LIBERTY_DELEGATED_BOE_CANDIDATES_TIMEOUT", "30")
liberty_delegated_boe_candidates_strict_min_candidates := env_var_or_default("LIBERTY_DELEGATED_BOE_CANDIDATES_STRICT_MIN_CANDIDATES", "1")
liberty_delegated_review_assist_in := env_var_or_default("LIBERTY_DELEGATED_REVIEW_ASSIST_IN", "docs/etl/sprints/AI-OPS-278/exports/liberty_delegated_person_window_review_queue_latest.csv")
liberty_delegated_review_assist_boe_candidates := env_var_or_default("LIBERTY_DELEGATED_REVIEW_ASSIST_BOE_CANDIDATES", "docs/etl/sprints/AI-OPS-280/exports/liberty_delegated_person_window_boe_candidates_latest.csv")
liberty_delegated_review_assist_out := env_var_or_default("LIBERTY_DELEGATED_REVIEW_ASSIST_OUT", "docs/etl/sprints/AI-OPS-281/exports/liberty_delegated_person_window_review_assist_latest.csv")
liberty_delegated_review_assist_summary_out := env_var_or_default("LIBERTY_DELEGATED_REVIEW_ASSIST_SUMMARY_OUT", "docs/etl/sprints/AI-OPS-281/evidence/liberty_delegated_person_window_review_assist_latest.json")
liberty_delegated_review_assist_min_candidate_score := env_var_or_default("LIBERTY_DELEGATED_REVIEW_ASSIST_MIN_CANDIDATE_SCORE", "20")
liberty_delegated_review_assist_max_candidates_per_link := env_var_or_default("LIBERTY_DELEGATED_REVIEW_ASSIST_MAX_CANDIDATES_PER_LINK", "3")
liberty_delegated_review_assist_strict_min_rows := env_var_or_default("LIBERTY_DELEGATED_REVIEW_ASSIST_STRICT_MIN_ROWS", "1")
liberty_delegated_auto_review_queue_csv := env_var_or_default("LIBERTY_DELEGATED_AUTO_REVIEW_QUEUE_CSV", "docs/etl/sprints/AI-OPS-278/exports/liberty_delegated_person_window_review_queue_latest.csv")
liberty_delegated_auto_review_assist_csv := env_var_or_default("LIBERTY_DELEGATED_AUTO_REVIEW_ASSIST_CSV", "docs/etl/sprints/AI-OPS-281/exports/liberty_delegated_person_window_review_assist_latest.csv")
liberty_delegated_auto_review_out := env_var_or_default("LIBERTY_DELEGATED_AUTO_REVIEW_OUT", "docs/etl/sprints/AI-OPS-282/exports/liberty_delegated_person_window_auto_review_decisions_latest.csv")
liberty_delegated_auto_review_summary_out := env_var_or_default("LIBERTY_DELEGATED_AUTO_REVIEW_SUMMARY_OUT", "docs/etl/sprints/AI-OPS-282/evidence/liberty_delegated_person_window_auto_review_decisions_latest.json")
liberty_delegated_auto_review_min_candidate_score := env_var_or_default("LIBERTY_DELEGATED_AUTO_REVIEW_MIN_CANDIDATE_SCORE", "25")
liberty_delegated_auto_review_max_candidates_per_link := env_var_or_default("LIBERTY_DELEGATED_AUTO_REVIEW_MAX_CANDIDATES_PER_LINK", "3")
liberty_delegated_auto_review_strict_min_approved_rows := env_var_or_default("LIBERTY_DELEGATED_AUTO_REVIEW_STRICT_MIN_APPROVED_ROWS", "1")
liberty_delegated_auto_review_qa_sample_out := env_var_or_default("LIBERTY_DELEGATED_AUTO_REVIEW_QA_SAMPLE_OUT", "docs/etl/sprints/AI-OPS-284/exports/liberty_delegated_person_window_auto_review_qa_sample_latest.csv")
liberty_delegated_auto_review_qa_summary_out := env_var_or_default("LIBERTY_DELEGATED_AUTO_REVIEW_QA_SUMMARY_OUT", "docs/etl/sprints/AI-OPS-284/evidence/liberty_delegated_person_window_auto_review_qa_sample_latest.json")
liberty_delegated_auto_review_qa_precision_out := env_var_or_default("LIBERTY_DELEGATED_AUTO_REVIEW_QA_PRECISION_OUT", "docs/etl/sprints/AI-OPS-284/evidence/liberty_delegated_person_window_auto_review_qa_precision_latest.json")
liberty_delegated_auto_review_qa_sample_size := env_var_or_default("LIBERTY_DELEGATED_AUTO_REVIEW_QA_SAMPLE_SIZE", "8")
liberty_delegated_auto_review_qa_min_reviewed_rows := env_var_or_default("LIBERTY_DELEGATED_AUTO_REVIEW_QA_MIN_REVIEWED_ROWS", "2")
liberty_delegated_auto_review_qa_min_precision_pct := env_var_or_default("LIBERTY_DELEGATED_AUTO_REVIEW_QA_MIN_PRECISION_PCT", "0")
liberty_delegated_auto_review_qa_decision_scope := env_var_or_default("LIBERTY_DELEGATED_AUTO_REVIEW_QA_DECISION_SCOPE", "approved")
liberty_delegated_non_nominative_qa_gate_auto_review_summary := env_var_or_default("LIBERTY_DELEGATED_NON_NOMINATIVE_QA_GATE_AUTO_REVIEW_SUMMARY", "docs/etl/sprints/AI-OPS-293/evidence/liberty_delegated_person_window_auto_review_decisions_alternative_latest.json")
liberty_delegated_non_nominative_qa_gate_sample_summary := env_var_or_default("LIBERTY_DELEGATED_NON_NOMINATIVE_QA_GATE_SAMPLE_SUMMARY", "docs/etl/sprints/AI-OPS-294/evidence/liberty_delegated_non_nominative_auto_review_qa_sample_latest.json")
liberty_delegated_non_nominative_qa_gate_precision_report := env_var_or_default("LIBERTY_DELEGATED_NON_NOMINATIVE_QA_GATE_PRECISION_REPORT", "docs/etl/sprints/AI-OPS-294/evidence/liberty_delegated_non_nominative_auto_review_qa_precision_latest.json")
liberty_delegated_non_nominative_qa_gate_review_note_contains := env_var_or_default("LIBERTY_DELEGATED_NON_NOMINATIVE_QA_GATE_REVIEW_NOTE_CONTAINS", "approved_non_nominative_unit")
liberty_delegated_non_nominative_qa_gate_min_reviewed_rows := env_var_or_default("LIBERTY_DELEGATED_NON_NOMINATIVE_QA_GATE_MIN_REVIEWED_ROWS", "1")
liberty_delegated_non_nominative_qa_gate_min_precision_pct := env_var_or_default("LIBERTY_DELEGATED_NON_NOMINATIVE_QA_GATE_MIN_PRECISION_PCT", "100")
liberty_delegated_non_nominative_qa_gate_out := env_var_or_default("LIBERTY_DELEGATED_NON_NOMINATIVE_QA_GATE_OUT", "docs/etl/sprints/AI-OPS-295/evidence/liberty_delegated_non_nominative_qa_gate_latest.json")
liberty_delegated_pending_resolution_queue_out := env_var_or_default("LIBERTY_DELEGATED_PENDING_RESOLUTION_QUEUE_OUT", "docs/etl/sprints/AI-OPS-286/exports/liberty_delegated_pending_resolution_review_queue_latest.csv")
liberty_delegated_pending_resolution_queue_summary_out := env_var_or_default("LIBERTY_DELEGATED_PENDING_RESOLUTION_QUEUE_SUMMARY_OUT", "docs/etl/sprints/AI-OPS-286/evidence/liberty_delegated_pending_resolution_review_queue_latest.json")
liberty_delegated_pending_resolution_top_candidates_per_link := env_var_or_default("LIBERTY_DELEGATED_PENDING_RESOLUTION_TOP_CANDIDATES_PER_LINK", "5")
liberty_delegated_alternative_capture_in := env_var_or_default("LIBERTY_DELEGATED_ALTERNATIVE_CAPTURE_IN", "docs/etl/sprints/AI-OPS-288/exports/liberty_delegated_pending_resolution_review_queue_targeted_latest.csv")
liberty_delegated_alternative_capture_out := env_var_or_default("LIBERTY_DELEGATED_ALTERNATIVE_CAPTURE_OUT", "docs/etl/sprints/AI-OPS-289/exports/liberty_delegated_alternative_capture_targets_latest.csv")
liberty_delegated_alternative_capture_summary_out := env_var_or_default("LIBERTY_DELEGATED_ALTERNATIVE_CAPTURE_SUMMARY_OUT", "docs/etl/sprints/AI-OPS-289/evidence/liberty_delegated_alternative_capture_targets_latest.json")
liberty_delegated_alternative_capture_max_candidate_docs_per_link := env_var_or_default("LIBERTY_DELEGATED_ALTERNATIVE_CAPTURE_MAX_CANDIDATE_DOCS_PER_LINK", "3")
liberty_delegated_alternative_capture_strict_min_targets_per_link := env_var_or_default("LIBERTY_DELEGATED_ALTERNATIVE_CAPTURE_STRICT_MIN_TARGETS_PER_LINK", "3")
liberty_delegated_alternative_boe_targets_in := env_var_or_default("LIBERTY_DELEGATED_ALTERNATIVE_BOE_TARGETS_IN", "docs/etl/sprints/AI-OPS-289/exports/liberty_delegated_alternative_capture_targets_latest.csv")
liberty_delegated_alternative_boe_out := env_var_or_default("LIBERTY_DELEGATED_ALTERNATIVE_BOE_OUT", "docs/etl/sprints/AI-OPS-290/exports/liberty_delegated_alternative_boe_candidates_latest.csv")
liberty_delegated_alternative_boe_summary_out := env_var_or_default("LIBERTY_DELEGATED_ALTERNATIVE_BOE_SUMMARY_OUT", "docs/etl/sprints/AI-OPS-290/evidence/liberty_delegated_alternative_boe_candidates_latest.json")
liberty_delegated_alternative_boe_top_results_per_query_target := env_var_or_default("LIBERTY_DELEGATED_ALTERNATIVE_BOE_TOP_RESULTS_PER_QUERY_TARGET", "6")
liberty_delegated_alternative_boe_max_queries_per_query_target := env_var_or_default("LIBERTY_DELEGATED_ALTERNATIVE_BOE_MAX_QUERIES_PER_QUERY_TARGET", "8")
liberty_delegated_alternative_boe_timeout := env_var_or_default("LIBERTY_DELEGATED_ALTERNATIVE_BOE_TIMEOUT", "30")
liberty_delegated_alternative_boe_strict_min_candidates := env_var_or_default("LIBERTY_DELEGATED_ALTERNATIVE_BOE_STRICT_MIN_CANDIDATES", "1")
liberty_delegated_alternative_boe_strict_min_links_with_candidates := env_var_or_default("LIBERTY_DELEGATED_ALTERNATIVE_BOE_STRICT_MIN_LINKS_WITH_CANDIDATES", "1")
accountability_actor_resolution_queue_out := env_var_or_default("ACCOUNTABILITY_ACTOR_RESOLUTION_QUEUE_OUT", "docs/etl/sprints/AI-OPS-ACCOUNTABILITY/evidence/accountability_actor_resolution_queue_latest.json")
accountability_actor_resolution_queue_csv_out := env_var_or_default("ACCOUNTABILITY_ACTOR_RESOLUTION_QUEUE_CSV_OUT", "docs/etl/sprints/AI-OPS-ACCOUNTABILITY/exports/accountability_actor_resolution_queue_latest.csv")
accountability_actor_resolution_queue_limit := env_var_or_default("ACCOUNTABILITY_ACTOR_RESOLUTION_QUEUE_LIMIT", "0")
accountability_issue_cluster_assignment_review_queue_out := env_var_or_default("ACCOUNTABILITY_ISSUE_CLUSTER_ASSIGNMENT_REVIEW_QUEUE_OUT", "docs/etl/sprints/AI-OPS-ACCOUNTABILITY/evidence/accountability_issue_cluster_assignment_review_queue_latest.json")
accountability_issue_cluster_assignment_review_queue_csv_out := env_var_or_default("ACCOUNTABILITY_ISSUE_CLUSTER_ASSIGNMENT_REVIEW_QUEUE_CSV_OUT", "docs/etl/sprints/AI-OPS-ACCOUNTABILITY/exports/accountability_issue_cluster_assignment_review_queue_latest.csv")
accountability_issue_cluster_assignment_review_queue_limit := env_var_or_default("ACCOUNTABILITY_ISSUE_CLUSTER_ASSIGNMENT_REVIEW_QUEUE_LIMIT", "0")
accountability_issue_cluster_assignment_reviews_csv := env_var_or_default("ACCOUNTABILITY_ISSUE_CLUSTER_ASSIGNMENT_REVIEWS_CSV", "docs/etl/sprints/AI-OPS-ACCOUNTABILITY/exports/accountability_issue_cluster_assignment_reviews_latest.csv")
accountability_issue_cluster_assignment_reviews_report_out := env_var_or_default("ACCOUNTABILITY_ISSUE_CLUSTER_ASSIGNMENT_REVIEWS_REPORT_OUT", "docs/etl/sprints/AI-OPS-ACCOUNTABILITY/evidence/accountability_issue_cluster_assignment_reviews_apply_report_latest.json")
accountability_min_entries := env_var_or_default("ACCOUNTABILITY_MIN_ENTRIES", "1")
accountability_min_actors := env_var_or_default("ACCOUNTABILITY_MIN_ACTORS", "1")
accountability_min_issues := env_var_or_default("ACCOUNTABILITY_MIN_ISSUES", "1")
accountability_min_evidence_api_questions := env_var_or_default("ACCOUNTABILITY_MIN_EVIDENCE_API_QUESTIONS", "6")
accountability_min_evidence_api_issue_clusters := env_var_or_default("ACCOUNTABILITY_MIN_EVIDENCE_API_ISSUE_CLUSTERS", "1")
accountability_min_evidence_api_reviewed_issue_clusters := env_var_or_default("ACCOUNTABILITY_MIN_EVIDENCE_API_REVIEWED_ISSUE_CLUSTERS", "0")
accountability_min_evidence_api_issue_cluster_issue_reviews := env_var_or_default("ACCOUNTABILITY_MIN_EVIDENCE_API_ISSUE_CLUSTER_ISSUE_REVIEWS", "0")
accountability_min_evidence_api_issue_cluster_assignment_review_needed := env_var_or_default("ACCOUNTABILITY_MIN_EVIDENCE_API_ISSUE_CLUSTER_ASSIGNMENT_REVIEW_NEEDED", "0")
accountability_max_evidence_api_issue_cluster_assignment_review_needed := env_var_or_default("ACCOUNTABILITY_MAX_EVIDENCE_API_ISSUE_CLUSTER_ASSIGNMENT_REVIEW_NEEDED", "-1")
accountability_min_evidence_api_gap_answers := env_var_or_default("ACCOUNTABILITY_MIN_EVIDENCE_API_GAP_ANSWERS", "9")
accountability_min_evidence_api_blocker_answers := env_var_or_default("ACCOUNTABILITY_MIN_EVIDENCE_API_BLOCKER_ANSWERS", "1")
accountability_min_evidence_api_qa_answers := env_var_or_default("ACCOUNTABILITY_MIN_EVIDENCE_API_QA_ANSWERS", "1")
accountability_min_resolution_pct := env_var_or_default("ACCOUNTABILITY_MIN_RESOLUTION_PCT", "1.0")
accountability_min_person_id_entries := env_var_or_default("ACCOUNTABILITY_MIN_PERSON_ID_ENTRIES", "0")
accountability_min_party_id_entries := env_var_or_default("ACCOUNTABILITY_MIN_PARTY_ID_ENTRIES", "0")
accountability_min_parliamentary_group_id_entries := env_var_or_default("ACCOUNTABILITY_MIN_PARLIAMENTARY_GROUP_ID_ENTRIES", "0")
accountability_max_ledger_bytes := env_var_or_default("ACCOUNTABILITY_MAX_LEDGER_BYTES", "5000000")
accountability_max_dossiers_bytes := env_var_or_default("ACCOUNTABILITY_MAX_DOSSIERS_BYTES", "10000000")
accountability_max_evidence_api_bytes := env_var_or_default("ACCOUNTABILITY_MAX_EVIDENCE_API_BYTES", "8000000")
accountability_ledger_max_entries_per_issue := env_var_or_default("ACCOUNTABILITY_LEDGER_MAX_ENTRIES_PER_ISSUE", "10")
accountability_ledger_max_sample_entries_per_actor := env_var_or_default("ACCOUNTABILITY_LEDGER_MAX_SAMPLE_ENTRIES_PER_ACTOR", "2")
accountability_dossiers_max_issues_per_actor := env_var_or_default("ACCOUNTABILITY_DOSSIERS_MAX_ISSUES_PER_ACTOR", "12")
accountability_dossiers_max_actors_per_issue := env_var_or_default("ACCOUNTABILITY_DOSSIERS_MAX_ACTORS_PER_ISSUE", "25")
code_zip_name := env_var_or_default("CODE_ZIP_NAME", "vota-con-la-chola-code.zip")
hf_dataset_repo_id := env_var_or_default("HF_DATASET_REPO_ID", "vota-con-la-chola-data")
hf_parquet_batch_rows := env_var_or_default("HF_PARQUET_BATCH_ROWS", "50000")
hf_parquet_compression := env_var_or_default("HF_PARQUET_COMPRESSION", "zstd")
hf_parquet_tables := env_var_or_default("HF_PARQUET_TABLES", "")
hf_parquet_exclude_tables := env_var_or_default("HF_PARQUET_EXCLUDE_TABLES", "raw_fetches,run_fetches,source_records,lost_and_found")
hf_allow_sensitive_parquet := env_var_or_default("HF_ALLOW_SENSITIVE_PARQUET", "0")
hf_include_sqlite_gz := env_var_or_default("HF_INCLUDE_SQLITE_GZ", "0")
hf_require_quality_report := env_var_or_default("HF_REQUIRE_QUALITY_REPORT", "1")
hf_require_liberty_atlas_release_latest := env_var_or_default("HF_REQUIRE_LIBERTY_ATLAS_RELEASE_LATEST", "1")
hf_raw_dataset_repo_id := env_var_or_default("HF_RAW_DATASET_REPO_ID", "vota-con-la-chola-raw")
hf_raw_max_files_per_block := env_var_or_default("HF_RAW_MAX_FILES_PER_BLOCK", "10000")
hf_raw_include_manual := env_var_or_default("HF_RAW_INCLUDE_MANUAL", "0")
hf_verify_timeout := env_var_or_default("HF_VERIFY_TIMEOUT", "20")
hf_verify_out := env_var_or_default("HF_VERIFY_OUT", "")
hf_scale_registry := env_var_or_default("HF_SCALE_REGISTRY", "docs/etl/real-corpus-registry.json")
hf_scale_readiness := env_var_or_default("HF_SCALE_READINESS", "etl/data/published/scale-readiness-latest.json")
hf_scale_report_out := env_var_or_default("HF_SCALE_REPORT_OUT", "")
hf_scale_verify_out := env_var_or_default("HF_SCALE_VERIFY_OUT", "")
hf_scale_python := env_var_or_default("HF_SCALE_PYTHON", "python3")
hf_scale_restore_destination := env_var_or_default("HF_SCALE_RESTORE_DESTINATION", "etl/data/restored/hf-scale")
hf_scale_restore_corpus_ids := env_var_or_default("HF_SCALE_RESTORE_CORPUS_IDS", "")
hf_scale_restore_snapshot_path := env_var_or_default("HF_SCALE_RESTORE_SNAPSHOT_PATH", "")
hf_scale_restore_workers := env_var_or_default("HF_SCALE_RESTORE_WORKERS", "8")
hf_scale_restore_min_free_bytes := env_var_or_default("HF_SCALE_RESTORE_MIN_FREE_BYTES", "10737418240")
hf_scale_restore_report_out := env_var_or_default("HF_SCALE_RESTORE_REPORT_OUT", "")
hf_scale_restore_validation_out := env_var_or_default("HF_SCALE_RESTORE_VALIDATION_OUT", "")
hf_scale_restore_validation_max_rss_mb := env_var_or_default("HF_SCALE_RESTORE_VALIDATION_MAX_RSS_MB", "1536")
hf_scale_rebuild_corpus_id := env_var_or_default("HF_SCALE_REBUILD_CORPUS_ID", "actor_mandates")
hf_scale_rebuild_output := env_var_or_default("HF_SCALE_REBUILD_OUTPUT", "etl/data/rebuilt/scale-origin.sqlite")
hf_scale_rebuild_report_out := env_var_or_default("HF_SCALE_REBUILD_REPORT_OUT", "")
citizen_preset_contract_fixture := env_var_or_default("CITIZEN_PRESET_CONTRACT_FIXTURE", "tests/fixtures/citizen_preset_hash_matrix.json")
citizen_preset_contract_out := env_var_or_default("CITIZEN_PRESET_CONTRACT_OUT", "")
citizen_preset_parity_source := env_var_or_default("CITIZEN_PRESET_PARITY_SOURCE", "ui/citizen/preset_codec.js")
citizen_preset_parity_published := env_var_or_default("CITIZEN_PRESET_PARITY_PUBLISHED", "ui/gh-pages-next/public/legacy/citizen/preset_codec.js")
citizen_preset_parity_out := env_var_or_default("CITIZEN_PRESET_PARITY_OUT", "")
citizen_preset_sync_source := env_var_or_default("CITIZEN_PRESET_SYNC_SOURCE", "ui/citizen/preset_codec.js")
citizen_preset_sync_published := env_var_or_default("CITIZEN_PRESET_SYNC_PUBLISHED", "ui/gh-pages-next/public/legacy/citizen/preset_codec.js")
citizen_preset_sync_out := env_var_or_default("CITIZEN_PRESET_SYNC_OUT", "")
citizen_preset_bundle_out := env_var_or_default("CITIZEN_PRESET_BUNDLE_OUT", "")
citizen_preset_bundle_history_path := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_PATH", "docs/etl/runs/citizen_preset_contract_bundle_history.jsonl")
citizen_preset_bundle_history_out := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_OUT", "")
citizen_preset_bundle_history_window := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_WINDOW", "20")
citizen_preset_bundle_history_window_out := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_WINDOW_OUT", "")
citizen_preset_bundle_history_compact_path := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_COMPACT_PATH", "docs/etl/runs/citizen_preset_contract_bundle_history.compacted.jsonl")
citizen_preset_bundle_history_compact_recent := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_COMPACT_RECENT", "20")
citizen_preset_bundle_history_compact_mid_span := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_COMPACT_MID_SPAN", "100")
citizen_preset_bundle_history_compact_mid_every := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_COMPACT_MID_EVERY", "5")
citizen_preset_bundle_history_compact_old_every := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_COMPACT_OLD_EVERY", "20")
citizen_preset_bundle_history_compact_min_raw := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_COMPACT_MIN_RAW", "25")
citizen_preset_bundle_history_compact_out := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_COMPACT_OUT", "")
citizen_preset_bundle_history_slo_window := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_WINDOW", "20")
citizen_preset_bundle_history_slo_max_regressions := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_MAX_REGRESSIONS", "0")
citizen_preset_bundle_history_slo_max_regression_rate_pct := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_MAX_REGRESSION_RATE_PCT", "0")
citizen_preset_bundle_history_slo_min_green_streak := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_MIN_GREEN_STREAK", "1")
citizen_preset_bundle_history_slo_out := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_OUT", "")
citizen_preset_bundle_history_slo_digest_out := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_OUT", "")
citizen_preset_bundle_history_slo_digest_heartbeat_path := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_PATH", "docs/etl/runs/citizen_preset_contract_bundle_history_slo_digest_heartbeat.jsonl")
citizen_preset_bundle_history_slo_digest_heartbeat_out := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_OUT", "")
citizen_preset_bundle_history_slo_digest_heartbeat_window := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_WINDOW", "20")
citizen_preset_bundle_history_slo_digest_heartbeat_max_failed := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_MAX_FAILED", "0")
citizen_preset_bundle_history_slo_digest_heartbeat_max_failed_rate_pct := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_MAX_FAILED_RATE_PCT", "0")
citizen_preset_bundle_history_slo_digest_heartbeat_window_out := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_WINDOW_OUT", "")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_path := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_PATH", "docs/etl/runs/citizen_preset_contract_bundle_history_slo_digest_heartbeat.compacted.jsonl")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_recent := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_RECENT", "20")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_mid_span := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_MID_SPAN", "100")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_mid_every := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_MID_EVERY", "5")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_old_every := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_OLD_EVERY", "20")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_min_raw := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_MIN_RAW", "25")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_out := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_OUT", "")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_window := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW", "20")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_out := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_OUT", "")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_out := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_OUT", "")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_path := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_PATH", "docs/etl/runs/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat.jsonl")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_out := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_OUT", "")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_window := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW", "20")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_max_failed := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_MAX_FAILED", "0")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_max_failed_rate_pct := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_MAX_FAILED_RATE_PCT", "0")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_max_degraded := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_MAX_DEGRADED", "0")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_max_degraded_rate_pct := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_MAX_DEGRADED_RATE_PCT", "0")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_window_out := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_OUT", "")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_compact_path := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_PATH", "docs/etl/runs/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat.compacted.jsonl")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_compact_recent := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_RECENT", "20")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_compact_mid_span := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_MID_SPAN", "100")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_compact_mid_every := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_MID_EVERY", "5")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_compact_old_every := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_OLD_EVERY", "20")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_compact_min_raw := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_MIN_RAW", "25")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_compact_out := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_OUT", "")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_compact_window := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW", "20")
citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_compact_window_out := env_var_or_default("CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_OUT", "")
citizen_product_kpi_snapshot := env_var_or_default("CITIZEN_PRODUCT_KPI_SNAPSHOT", "ui/gh-pages-next/public/citizen/data/citizen.json")
citizen_product_kpi_events := env_var_or_default("CITIZEN_PRODUCT_KPI_EVENTS", "")
citizen_product_kpi_summary := env_var_or_default("CITIZEN_PRODUCT_KPI_SUMMARY", "")
citizen_product_kpi_out := env_var_or_default("CITIZEN_PRODUCT_KPI_OUT", "docs/etl/sprints/AI-OPS-72/evidence/citizen_product_kpis_latest.json")
citizen_product_kpi_max_unknown_rate := env_var_or_default("CITIZEN_PRODUCT_KPI_MAX_UNKNOWN_RATE", "0.45")
citizen_product_kpi_max_tfa_seconds := env_var_or_default("CITIZEN_PRODUCT_KPI_MAX_TFA_SECONDS", "120")
citizen_product_kpi_min_drilldown_rate := env_var_or_default("CITIZEN_PRODUCT_KPI_MIN_DRILLDOWN_RATE", "0.20")
citizen_product_kpi_heartbeat_events := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_EVENTS", "tests/fixtures/citizen_product_kpi_events_sample.jsonl")
citizen_product_kpi_heartbeat_summary := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_SUMMARY", "")
citizen_product_kpi_heartbeat_digest := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_DIGEST", "docs/etl/sprints/AI-OPS-98/evidence/citizen_product_kpis_latest.json")
citizen_product_kpi_heartbeat_path := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_PATH", "docs/etl/runs/citizen_product_kpis_heartbeat.jsonl")
citizen_product_kpi_heartbeat_out := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_OUT", "docs/etl/sprints/AI-OPS-98/evidence/citizen_product_kpis_heartbeat_latest.json")
citizen_product_kpi_heartbeat_window_last := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_WINDOW_LAST", "20")
citizen_product_kpi_heartbeat_window_max_failed := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_WINDOW_MAX_FAILED", "0")
citizen_product_kpi_heartbeat_window_max_failed_rate_pct := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_WINDOW_MAX_FAILED_RATE_PCT", "0")
citizen_product_kpi_heartbeat_window_max_degraded := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_WINDOW_MAX_DEGRADED", "0")
citizen_product_kpi_heartbeat_window_max_degraded_rate_pct := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_WINDOW_MAX_DEGRADED_RATE_PCT", "0")
citizen_product_kpi_heartbeat_window_max_contract_incomplete := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_WINDOW_MAX_CONTRACT_INCOMPLETE", "0")
citizen_product_kpi_heartbeat_window_max_contract_incomplete_rate_pct := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_WINDOW_MAX_CONTRACT_INCOMPLETE_RATE_PCT", "0")
citizen_product_kpi_heartbeat_window_max_unknown_rate_violations := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_WINDOW_MAX_UNKNOWN_RATE_VIOLATIONS", "0")
citizen_product_kpi_heartbeat_window_max_unknown_rate_violation_rate_pct := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_WINDOW_MAX_UNKNOWN_RATE_VIOLATION_RATE_PCT", "0")
citizen_product_kpi_heartbeat_window_max_tfa_violations := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_WINDOW_MAX_TFA_VIOLATIONS", "0")
citizen_product_kpi_heartbeat_window_max_tfa_violation_rate_pct := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_WINDOW_MAX_TFA_VIOLATION_RATE_PCT", "0")
citizen_product_kpi_heartbeat_window_max_drilldown_violations := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_WINDOW_MAX_DRILLDOWN_VIOLATIONS", "0")
citizen_product_kpi_heartbeat_window_max_drilldown_violation_rate_pct := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_WINDOW_MAX_DRILLDOWN_VIOLATION_RATE_PCT", "0")
citizen_product_kpi_heartbeat_window_out := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-98/evidence/citizen_product_kpis_heartbeat_window_latest.json")
citizen_product_kpi_heartbeat_compact_path := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_COMPACT_PATH", "docs/etl/runs/citizen_product_kpis_heartbeat.compacted.jsonl")
citizen_product_kpi_heartbeat_compact_recent := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_COMPACT_RECENT", "20")
citizen_product_kpi_heartbeat_compact_mid_span := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_COMPACT_MID_SPAN", "100")
citizen_product_kpi_heartbeat_compact_mid_every := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_COMPACT_MID_EVERY", "5")
citizen_product_kpi_heartbeat_compact_old_every := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_COMPACT_OLD_EVERY", "20")
citizen_product_kpi_heartbeat_compact_min_raw := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_COMPACT_MIN_RAW", "25")
citizen_product_kpi_heartbeat_compact_out := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_COMPACT_OUT", "docs/etl/sprints/AI-OPS-107/evidence/citizen_product_kpis_heartbeat_compaction_latest.json")
citizen_product_kpi_heartbeat_compact_window_last := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_COMPACT_WINDOW_LAST", "20")
citizen_product_kpi_heartbeat_compact_window_out := env_var_or_default("CITIZEN_PRODUCT_KPI_HEARTBEAT_COMPACT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-107/evidence/citizen_product_kpis_heartbeat_compaction_window_latest.json")
citizen_mobile_perf_ui_html := env_var_or_default("CITIZEN_MOBILE_PERF_UI_HTML", "ui/citizen/index.html")
citizen_mobile_perf_ui_assets := env_var_or_default("CITIZEN_MOBILE_PERF_UI_ASSETS", "ui/citizen/preset_codec.js,ui/citizen/onboarding_funnel.js,ui/citizen/first_answer_accelerator.js,ui/citizen/unknown_explainability.js,ui/citizen/cross_method_stability.js,ui/citizen/evidence_trust_panel.js")
citizen_mobile_perf_snapshot := env_var_or_default("CITIZEN_MOBILE_PERF_SNAPSHOT", "ui/gh-pages-next/public/citizen/data/citizen.json")
citizen_mobile_perf_out := env_var_or_default("CITIZEN_MOBILE_PERF_OUT", "docs/etl/sprints/AI-OPS-76/evidence/citizen_mobile_performance_budget_latest.json")
citizen_mobile_perf_max_ui_html_bytes := env_var_or_default("CITIZEN_MOBILE_PERF_MAX_UI_HTML_BYTES", "220000")
citizen_mobile_perf_max_ui_assets_total_bytes := env_var_or_default("CITIZEN_MOBILE_PERF_MAX_UI_ASSETS_TOTAL_BYTES", "60000")
citizen_mobile_perf_max_snapshot_bytes := env_var_or_default("CITIZEN_MOBILE_PERF_MAX_SNAPSHOT_BYTES", "5000000")
citizen_mobile_obs_events := env_var_or_default("CITIZEN_MOBILE_OBS_EVENTS", "tests/fixtures/citizen_mobile_latency_events_sample.jsonl")
citizen_mobile_obs_summary := env_var_or_default("CITIZEN_MOBILE_OBS_SUMMARY", "")
citizen_mobile_obs_out := env_var_or_default("CITIZEN_MOBILE_OBS_OUT", "docs/etl/sprints/AI-OPS-83/evidence/citizen_mobile_observability_latest.json")
citizen_mobile_obs_min_samples := env_var_or_default("CITIZEN_MOBILE_OBS_MIN_SAMPLES", "20")
citizen_mobile_obs_max_p50_ms := env_var_or_default("CITIZEN_MOBILE_OBS_MAX_P50_MS", "180")
citizen_mobile_obs_max_p90_ms := env_var_or_default("CITIZEN_MOBILE_OBS_MAX_P90_MS", "450")
citizen_mobile_obs_heartbeat_digest := env_var_or_default("CITIZEN_MOBILE_OBS_HEARTBEAT_DIGEST", "docs/etl/sprints/AI-OPS-83/evidence/citizen_mobile_observability_latest.json")
citizen_mobile_obs_heartbeat_path := env_var_or_default("CITIZEN_MOBILE_OBS_HEARTBEAT_PATH", "docs/etl/runs/citizen_mobile_observability_heartbeat.jsonl")
citizen_mobile_obs_heartbeat_out := env_var_or_default("CITIZEN_MOBILE_OBS_HEARTBEAT_OUT", "docs/etl/sprints/AI-OPS-90/evidence/citizen_mobile_observability_heartbeat_latest.json")
citizen_mobile_obs_heartbeat_window_last := env_var_or_default("CITIZEN_MOBILE_OBS_HEARTBEAT_WINDOW_LAST", "20")
citizen_mobile_obs_heartbeat_window_max_failed := env_var_or_default("CITIZEN_MOBILE_OBS_HEARTBEAT_WINDOW_MAX_FAILED", "0")
citizen_mobile_obs_heartbeat_window_max_failed_rate_pct := env_var_or_default("CITIZEN_MOBILE_OBS_HEARTBEAT_WINDOW_MAX_FAILED_RATE_PCT", "0")
citizen_mobile_obs_heartbeat_window_max_degraded := env_var_or_default("CITIZEN_MOBILE_OBS_HEARTBEAT_WINDOW_MAX_DEGRADED", "0")
citizen_mobile_obs_heartbeat_window_max_degraded_rate_pct := env_var_or_default("CITIZEN_MOBILE_OBS_HEARTBEAT_WINDOW_MAX_DEGRADED_RATE_PCT", "0")
citizen_mobile_obs_heartbeat_window_max_p90_threshold_violations := env_var_or_default("CITIZEN_MOBILE_OBS_HEARTBEAT_WINDOW_MAX_P90_THRESHOLD_VIOLATIONS", "0")
citizen_mobile_obs_heartbeat_window_max_p90_threshold_violation_rate_pct := env_var_or_default("CITIZEN_MOBILE_OBS_HEARTBEAT_WINDOW_MAX_P90_THRESHOLD_VIOLATION_RATE_PCT", "0")
citizen_mobile_obs_heartbeat_window_out := env_var_or_default("CITIZEN_MOBILE_OBS_HEARTBEAT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-90/evidence/citizen_mobile_observability_heartbeat_window_latest.json")
citizen_mobile_obs_heartbeat_compact_path := env_var_or_default("CITIZEN_MOBILE_OBS_HEARTBEAT_COMPACT_PATH", "docs/etl/runs/citizen_mobile_observability_heartbeat.compacted.jsonl")
citizen_mobile_obs_heartbeat_compact_recent := env_var_or_default("CITIZEN_MOBILE_OBS_HEARTBEAT_COMPACT_RECENT", "20")
citizen_mobile_obs_heartbeat_compact_mid_span := env_var_or_default("CITIZEN_MOBILE_OBS_HEARTBEAT_COMPACT_MID_SPAN", "100")
citizen_mobile_obs_heartbeat_compact_mid_every := env_var_or_default("CITIZEN_MOBILE_OBS_HEARTBEAT_COMPACT_MID_EVERY", "5")
citizen_mobile_obs_heartbeat_compact_old_every := env_var_or_default("CITIZEN_MOBILE_OBS_HEARTBEAT_COMPACT_OLD_EVERY", "20")
citizen_mobile_obs_heartbeat_compact_min_raw := env_var_or_default("CITIZEN_MOBILE_OBS_HEARTBEAT_COMPACT_MIN_RAW", "25")
citizen_mobile_obs_heartbeat_compact_out := env_var_or_default("CITIZEN_MOBILE_OBS_HEARTBEAT_COMPACT_OUT", "docs/etl/sprints/AI-OPS-95/evidence/citizen_mobile_observability_heartbeat_compaction_latest.json")
citizen_mobile_obs_heartbeat_compact_window_last := env_var_or_default("CITIZEN_MOBILE_OBS_HEARTBEAT_COMPACT_WINDOW_LAST", "20")
citizen_mobile_obs_heartbeat_compact_window_out := env_var_or_default("CITIZEN_MOBILE_OBS_HEARTBEAT_COMPACT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-95/evidence/citizen_mobile_observability_heartbeat_compaction_window_latest.json")
citizen_tailwind_md3_tokens := env_var_or_default("CITIZEN_TAILWIND_MD3_TOKENS", "ui/citizen/tailwind_md3.tokens.json")
citizen_tailwind_md3_css := env_var_or_default("CITIZEN_TAILWIND_MD3_CSS", "ui/citizen/tailwind_md3.generated.css")
citizen_tailwind_md3_out := env_var_or_default("CITIZEN_TAILWIND_MD3_OUT", "docs/etl/sprints/AI-OPS-91/evidence/citizen_tailwind_md3_contract_latest.json")
citizen_tailwind_md3_max_css_bytes := env_var_or_default("CITIZEN_TAILWIND_MD3_MAX_CSS_BYTES", "40000")
citizen_tailwind_md3_min_card_markers := env_var_or_default("CITIZEN_TAILWIND_MD3_MIN_CARD_MARKERS", "6")
citizen_tailwind_md3_min_chip_markers := env_var_or_default("CITIZEN_TAILWIND_MD3_MIN_CHIP_MARKERS", "8")
citizen_tailwind_md3_min_button_markers := env_var_or_default("CITIZEN_TAILWIND_MD3_MIN_BUTTON_MARKERS", "20")
citizen_tailwind_md3_min_tab_markers := env_var_or_default("CITIZEN_TAILWIND_MD3_MIN_TAB_MARKERS", "6")
citizen_tailwind_md3_drift_contract := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_CONTRACT", "docs/etl/sprints/AI-OPS-96/evidence/citizen_tailwind_md3_contract_latest.json")
citizen_tailwind_md3_drift_published_tokens := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_PUBLISHED_TOKENS", "ui/gh-pages-next/public/citizen/tailwind_md3.tokens.json")
citizen_tailwind_md3_drift_published_data_tokens := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_PUBLISHED_DATA_TOKENS", "ui/gh-pages-next/public/citizen/data/tailwind_md3.tokens.json")
citizen_tailwind_md3_drift_published_css := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_PUBLISHED_CSS", "ui/gh-pages-next/public/citizen/tailwind_md3.generated.css")
citizen_tailwind_md3_drift_published_ui_html := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_PUBLISHED_UI_HTML", "ui/gh-pages-next/public/citizen/index.html")
citizen_tailwind_md3_drift_out := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_OUT", "docs/etl/sprints/AI-OPS-96/evidence/citizen_tailwind_md3_visual_drift_digest_latest.json")
citizen_tailwind_md3_drift_heartbeat_path := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_HEARTBEAT_PATH", "docs/etl/runs/citizen_tailwind_md3_visual_drift_digest_heartbeat.jsonl")
citizen_tailwind_md3_drift_heartbeat_out := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_HEARTBEAT_OUT", "docs/etl/sprints/AI-OPS-103/evidence/citizen_tailwind_md3_visual_drift_digest_heartbeat_latest.json")
citizen_tailwind_md3_drift_heartbeat_window_last := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_HEARTBEAT_WINDOW_LAST", "20")
citizen_tailwind_md3_drift_heartbeat_window_max_failed := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_HEARTBEAT_WINDOW_MAX_FAILED", "0")
citizen_tailwind_md3_drift_heartbeat_window_max_failed_rate_pct := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_HEARTBEAT_WINDOW_MAX_FAILED_RATE_PCT", "0")
citizen_tailwind_md3_drift_heartbeat_window_max_degraded := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_HEARTBEAT_WINDOW_MAX_DEGRADED", "0")
citizen_tailwind_md3_drift_heartbeat_window_max_degraded_rate_pct := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_HEARTBEAT_WINDOW_MAX_DEGRADED_RATE_PCT", "0")
citizen_tailwind_md3_drift_heartbeat_window_max_parity_mismatch := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_HEARTBEAT_WINDOW_MAX_PARITY_MISMATCH", "0")
citizen_tailwind_md3_drift_heartbeat_window_max_parity_mismatch_rate_pct := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_HEARTBEAT_WINDOW_MAX_PARITY_MISMATCH_RATE_PCT", "0")
citizen_tailwind_md3_drift_heartbeat_window_max_tokens_parity_mismatch := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_HEARTBEAT_WINDOW_MAX_TOKENS_PARITY_MISMATCH", "0")
citizen_tailwind_md3_drift_heartbeat_window_max_tokens_data_parity_mismatch := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_HEARTBEAT_WINDOW_MAX_TOKENS_DATA_PARITY_MISMATCH", "0")
citizen_tailwind_md3_drift_heartbeat_window_max_css_parity_mismatch := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_HEARTBEAT_WINDOW_MAX_CSS_PARITY_MISMATCH", "0")
citizen_tailwind_md3_drift_heartbeat_window_max_ui_html_parity_mismatch := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_HEARTBEAT_WINDOW_MAX_UI_HTML_PARITY_MISMATCH", "0")
citizen_tailwind_md3_drift_heartbeat_window_max_marker_mismatch := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_HEARTBEAT_WINDOW_MAX_MARKER_MISMATCH", "0")
citizen_tailwind_md3_drift_heartbeat_window_out := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_HEARTBEAT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-103/evidence/citizen_tailwind_md3_visual_drift_digest_heartbeat_window_latest.json")
citizen_tailwind_md3_drift_heartbeat_compact_path := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_HEARTBEAT_COMPACT_PATH", "docs/etl/runs/citizen_tailwind_md3_visual_drift_digest_heartbeat.compacted.jsonl")
citizen_tailwind_md3_drift_heartbeat_compact_recent := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_HEARTBEAT_COMPACT_RECENT", "20")
citizen_tailwind_md3_drift_heartbeat_compact_mid_span := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_HEARTBEAT_COMPACT_MID_SPAN", "100")
citizen_tailwind_md3_drift_heartbeat_compact_mid_every := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_HEARTBEAT_COMPACT_MID_EVERY", "5")
citizen_tailwind_md3_drift_heartbeat_compact_old_every := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_HEARTBEAT_COMPACT_OLD_EVERY", "20")
citizen_tailwind_md3_drift_heartbeat_compact_min_raw := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_HEARTBEAT_COMPACT_MIN_RAW", "25")
citizen_tailwind_md3_drift_heartbeat_compact_out := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_HEARTBEAT_COMPACT_OUT", "docs/etl/sprints/AI-OPS-108/evidence/citizen_tailwind_md3_visual_drift_digest_heartbeat_compaction_latest.json")
citizen_tailwind_md3_drift_heartbeat_compact_window_last := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_HEARTBEAT_COMPACT_WINDOW_LAST", "20")
citizen_tailwind_md3_drift_heartbeat_compact_window_out := env_var_or_default("CITIZEN_TAILWIND_MD3_DRIFT_HEARTBEAT_COMPACT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-108/evidence/citizen_tailwind_md3_visual_drift_digest_heartbeat_compaction_window_latest.json")
citizen_release_source_root := env_var_or_default("CITIZEN_RELEASE_SOURCE_ROOT", "ui/citizen")
citizen_release_published_root := env_var_or_default("CITIZEN_RELEASE_PUBLISHED_ROOT", "ui/gh-pages-next/out/citizen")
citizen_release_snapshot := env_var_or_default("CITIZEN_RELEASE_SNAPSHOT", "ui/gh-pages-next/public/citizen/data/citizen.json")
citizen_release_concerns := env_var_or_default("CITIZEN_RELEASE_CONCERNS", "ui/citizen/concerns_v1.json")
citizen_release_assets := env_var_or_default("CITIZEN_RELEASE_ASSETS", "index.html,preset_codec.js,onboarding_funnel.js,first_answer_accelerator.js,unknown_explainability.js,cross_method_stability.js,evidence_trust_panel.js,tailwind_md3.generated.css,tailwind_md3.tokens.json")
citizen_release_max_snapshot_bytes := env_var_or_default("CITIZEN_RELEASE_MAX_SNAPSHOT_BYTES", "5000000")
citizen_release_out := env_var_or_default("CITIZEN_RELEASE_OUT", "docs/etl/sprints/AI-OPS-81/evidence/citizen_release_hardening_latest.json")
citizen_release_trace_source := env_var_or_default("CITIZEN_RELEASE_TRACE_SOURCE", "docs/etl/sprints/AI-OPS-81/evidence/citizen_release_hardening_latest.json")
citizen_release_trace_max_age_minutes := env_var_or_default("CITIZEN_RELEASE_TRACE_MAX_AGE_MINUTES", "360")
citizen_release_trace_out := env_var_or_default("CITIZEN_RELEASE_TRACE_OUT", "docs/etl/sprints/AI-OPS-88/evidence/citizen_release_trace_digest_latest.json")
citizen_release_trace_heartbeat_digest := env_var_or_default("CITIZEN_RELEASE_TRACE_HEARTBEAT_DIGEST", "docs/etl/sprints/AI-OPS-88/evidence/citizen_release_trace_digest_latest.json")
citizen_release_trace_heartbeat_path := env_var_or_default("CITIZEN_RELEASE_TRACE_HEARTBEAT_PATH", "docs/etl/runs/citizen_release_trace_digest_heartbeat.jsonl")
citizen_release_trace_heartbeat_out := env_var_or_default("CITIZEN_RELEASE_TRACE_HEARTBEAT_OUT", "docs/etl/sprints/AI-OPS-93/evidence/citizen_release_trace_digest_heartbeat_latest.json")
citizen_release_trace_heartbeat_window_last := env_var_or_default("CITIZEN_RELEASE_TRACE_HEARTBEAT_WINDOW_LAST", "20")
citizen_release_trace_heartbeat_window_max_failed := env_var_or_default("CITIZEN_RELEASE_TRACE_HEARTBEAT_WINDOW_MAX_FAILED", "0")
citizen_release_trace_heartbeat_window_max_failed_rate_pct := env_var_or_default("CITIZEN_RELEASE_TRACE_HEARTBEAT_WINDOW_MAX_FAILED_RATE_PCT", "0")
citizen_release_trace_heartbeat_window_max_degraded := env_var_or_default("CITIZEN_RELEASE_TRACE_HEARTBEAT_WINDOW_MAX_DEGRADED", "0")
citizen_release_trace_heartbeat_window_max_degraded_rate_pct := env_var_or_default("CITIZEN_RELEASE_TRACE_HEARTBEAT_WINDOW_MAX_DEGRADED_RATE_PCT", "0")
citizen_release_trace_heartbeat_window_max_stale := env_var_or_default("CITIZEN_RELEASE_TRACE_HEARTBEAT_WINDOW_MAX_STALE", "0")
citizen_release_trace_heartbeat_window_max_stale_rate_pct := env_var_or_default("CITIZEN_RELEASE_TRACE_HEARTBEAT_WINDOW_MAX_STALE_RATE_PCT", "0")
citizen_release_trace_heartbeat_window_out := env_var_or_default("CITIZEN_RELEASE_TRACE_HEARTBEAT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-93/evidence/citizen_release_trace_digest_heartbeat_window_latest.json")
citizen_release_trace_heartbeat_compact_path := env_var_or_default("CITIZEN_RELEASE_TRACE_HEARTBEAT_COMPACT_PATH", "docs/etl/runs/citizen_release_trace_digest_heartbeat.compacted.jsonl")
citizen_release_trace_heartbeat_compact_recent := env_var_or_default("CITIZEN_RELEASE_TRACE_HEARTBEAT_COMPACT_RECENT", "20")
citizen_release_trace_heartbeat_compact_mid_span := env_var_or_default("CITIZEN_RELEASE_TRACE_HEARTBEAT_COMPACT_MID_SPAN", "100")
citizen_release_trace_heartbeat_compact_mid_every := env_var_or_default("CITIZEN_RELEASE_TRACE_HEARTBEAT_COMPACT_MID_EVERY", "5")
citizen_release_trace_heartbeat_compact_old_every := env_var_or_default("CITIZEN_RELEASE_TRACE_HEARTBEAT_COMPACT_OLD_EVERY", "20")
citizen_release_trace_heartbeat_compact_min_raw := env_var_or_default("CITIZEN_RELEASE_TRACE_HEARTBEAT_COMPACT_MIN_RAW", "25")
citizen_release_trace_heartbeat_compact_out := env_var_or_default("CITIZEN_RELEASE_TRACE_HEARTBEAT_COMPACT_OUT", "docs/etl/sprints/AI-OPS-102/evidence/citizen_release_trace_digest_heartbeat_compaction_latest.json")
citizen_release_trace_heartbeat_compact_window_last := env_var_or_default("CITIZEN_RELEASE_TRACE_HEARTBEAT_COMPACT_WINDOW_LAST", "20")
citizen_release_trace_heartbeat_compact_window_out := env_var_or_default("CITIZEN_RELEASE_TRACE_HEARTBEAT_COMPACT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-102/evidence/citizen_release_trace_digest_heartbeat_compaction_window_latest.json")
citizen_pack_quality_snapshot := env_var_or_default("CITIZEN_PACK_QUALITY_SNAPSHOT", "ui/gh-pages-next/public/citizen/data/citizen.json")
citizen_pack_quality_concerns := env_var_or_default("CITIZEN_PACK_QUALITY_CONCERNS", "ui/citizen/concerns_v1.json")
citizen_pack_quality_out := env_var_or_default("CITIZEN_PACK_QUALITY_OUT", "docs/etl/sprints/AI-OPS-78/evidence/citizen_concern_pack_quality_latest.json")
citizen_pack_quality_min_topics_per_pack := env_var_or_default("CITIZEN_PACK_QUALITY_MIN_TOPICS_PER_PACK", "10")
citizen_pack_quality_min_clear_cells_pct := env_var_or_default("CITIZEN_PACK_QUALITY_MIN_CLEAR_CELLS_PCT", "0.70")
citizen_pack_quality_max_unknown_cells_pct := env_var_or_default("CITIZEN_PACK_QUALITY_MAX_UNKNOWN_CELLS_PCT", "0.30")
citizen_pack_quality_min_confidence_avg_signal := env_var_or_default("CITIZEN_PACK_QUALITY_MIN_CONFIDENCE_AVG_SIGNAL", "0.50")
citizen_pack_quality_min_high_stakes_share := env_var_or_default("CITIZEN_PACK_QUALITY_MIN_HIGH_STAKES_SHARE", "0.12")
citizen_pack_quality_max_weak_packs := env_var_or_default("CITIZEN_PACK_QUALITY_MAX_WEAK_PACKS", "1")
citizen_pack_outcome_events := env_var_or_default("CITIZEN_PACK_OUTCOME_EVENTS", "tests/fixtures/citizen_concern_pack_outcome_events_sample.jsonl")
citizen_pack_outcome_quality := env_var_or_default("CITIZEN_PACK_OUTCOME_QUALITY", "tests/fixtures/citizen_concern_pack_quality_sample.json")
citizen_pack_outcome_out := env_var_or_default("CITIZEN_PACK_OUTCOME_OUT", "docs/etl/sprints/AI-OPS-85/evidence/citizen_concern_pack_outcomes_latest.json")
citizen_pack_outcome_min_pack_select_events := env_var_or_default("CITIZEN_PACK_OUTCOME_MIN_PACK_SELECT_EVENTS", "20")
citizen_pack_outcome_min_weak_pack_select_sessions := env_var_or_default("CITIZEN_PACK_OUTCOME_MIN_WEAK_PACK_SELECT_SESSIONS", "5")
citizen_pack_outcome_min_weak_pack_followthrough_rate := env_var_or_default("CITIZEN_PACK_OUTCOME_MIN_WEAK_PACK_FOLLOWTHROUGH_RATE", "0.30")
citizen_pack_outcome_max_unknown_pack_select_share := env_var_or_default("CITIZEN_PACK_OUTCOME_MAX_UNKNOWN_PACK_SELECT_SHARE", "0.20")
citizen_pack_outcome_heartbeat_digest := env_var_or_default("CITIZEN_PACK_OUTCOME_HEARTBEAT_DIGEST", "docs/etl/sprints/AI-OPS-85/evidence/citizen_concern_pack_outcomes_latest.json")
citizen_pack_outcome_heartbeat_path := env_var_or_default("CITIZEN_PACK_OUTCOME_HEARTBEAT_PATH", "docs/etl/runs/citizen_concern_pack_outcomes_heartbeat.jsonl")
citizen_pack_outcome_heartbeat_out := env_var_or_default("CITIZEN_PACK_OUTCOME_HEARTBEAT_OUT", "docs/etl/sprints/AI-OPS-100/evidence/citizen_concern_pack_outcomes_heartbeat_latest.json")
citizen_pack_outcome_heartbeat_window_last := env_var_or_default("CITIZEN_PACK_OUTCOME_HEARTBEAT_WINDOW_LAST", "20")
citizen_pack_outcome_heartbeat_window_max_failed := env_var_or_default("CITIZEN_PACK_OUTCOME_HEARTBEAT_WINDOW_MAX_FAILED", "0")
citizen_pack_outcome_heartbeat_window_max_failed_rate_pct := env_var_or_default("CITIZEN_PACK_OUTCOME_HEARTBEAT_WINDOW_MAX_FAILED_RATE_PCT", "0")
citizen_pack_outcome_heartbeat_window_max_degraded := env_var_or_default("CITIZEN_PACK_OUTCOME_HEARTBEAT_WINDOW_MAX_DEGRADED", "0")
citizen_pack_outcome_heartbeat_window_max_degraded_rate_pct := env_var_or_default("CITIZEN_PACK_OUTCOME_HEARTBEAT_WINDOW_MAX_DEGRADED_RATE_PCT", "0")
citizen_pack_outcome_heartbeat_window_max_contract_incomplete := env_var_or_default("CITIZEN_PACK_OUTCOME_HEARTBEAT_WINDOW_MAX_CONTRACT_INCOMPLETE", "0")
citizen_pack_outcome_heartbeat_window_max_contract_incomplete_rate_pct := env_var_or_default("CITIZEN_PACK_OUTCOME_HEARTBEAT_WINDOW_MAX_CONTRACT_INCOMPLETE_RATE_PCT", "0")
citizen_pack_outcome_heartbeat_window_max_weak_pack_followthrough_violations := env_var_or_default("CITIZEN_PACK_OUTCOME_HEARTBEAT_WINDOW_MAX_WEAK_PACK_FOLLOWTHROUGH_VIOLATIONS", "0")
citizen_pack_outcome_heartbeat_window_max_weak_pack_followthrough_violation_rate_pct := env_var_or_default("CITIZEN_PACK_OUTCOME_HEARTBEAT_WINDOW_MAX_WEAK_PACK_FOLLOWTHROUGH_VIOLATION_RATE_PCT", "0")
citizen_pack_outcome_heartbeat_window_max_unknown_pack_select_share_violations := env_var_or_default("CITIZEN_PACK_OUTCOME_HEARTBEAT_WINDOW_MAX_UNKNOWN_PACK_SELECT_SHARE_VIOLATIONS", "0")
citizen_pack_outcome_heartbeat_window_max_unknown_pack_select_share_violation_rate_pct := env_var_or_default("CITIZEN_PACK_OUTCOME_HEARTBEAT_WINDOW_MAX_UNKNOWN_PACK_SELECT_SHARE_VIOLATION_RATE_PCT", "0")
citizen_pack_outcome_heartbeat_window_out := env_var_or_default("CITIZEN_PACK_OUTCOME_HEARTBEAT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-100/evidence/citizen_concern_pack_outcomes_heartbeat_window_latest.json")
citizen_pack_outcome_heartbeat_compact_path := env_var_or_default("CITIZEN_PACK_OUTCOME_HEARTBEAT_COMPACT_PATH", "docs/etl/runs/citizen_concern_pack_outcomes_heartbeat.compacted.jsonl")
citizen_pack_outcome_heartbeat_compact_recent := env_var_or_default("CITIZEN_PACK_OUTCOME_HEARTBEAT_COMPACT_RECENT", "20")
citizen_pack_outcome_heartbeat_compact_mid_span := env_var_or_default("CITIZEN_PACK_OUTCOME_HEARTBEAT_COMPACT_MID_SPAN", "100")
citizen_pack_outcome_heartbeat_compact_mid_every := env_var_or_default("CITIZEN_PACK_OUTCOME_HEARTBEAT_COMPACT_MID_EVERY", "5")
citizen_pack_outcome_heartbeat_compact_old_every := env_var_or_default("CITIZEN_PACK_OUTCOME_HEARTBEAT_COMPACT_OLD_EVERY", "20")
citizen_pack_outcome_heartbeat_compact_min_raw := env_var_or_default("CITIZEN_PACK_OUTCOME_HEARTBEAT_COMPACT_MIN_RAW", "25")
citizen_pack_outcome_heartbeat_compact_out := env_var_or_default("CITIZEN_PACK_OUTCOME_HEARTBEAT_COMPACT_OUT", "docs/etl/sprints/AI-OPS-105/evidence/citizen_concern_pack_outcomes_heartbeat_compaction_latest.json")
citizen_pack_outcome_heartbeat_compact_window_last := env_var_or_default("CITIZEN_PACK_OUTCOME_HEARTBEAT_COMPACT_WINDOW_LAST", "20")
citizen_pack_outcome_heartbeat_compact_window_out := env_var_or_default("CITIZEN_PACK_OUTCOME_HEARTBEAT_COMPACT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-105/evidence/citizen_concern_pack_outcomes_heartbeat_compaction_window_latest.json")
citizen_trust_action_nudge_events := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_EVENTS", "tests/fixtures/citizen_trust_action_nudge_events_sample.jsonl")
citizen_trust_action_nudge_out := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_OUT", "docs/etl/sprints/AI-OPS-86/evidence/citizen_trust_action_nudges_latest.json")
citizen_trust_action_nudge_min_shown_events := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_MIN_SHOWN_EVENTS", "8")
citizen_trust_action_nudge_min_shown_sessions := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_MIN_SHOWN_SESSIONS", "5")
citizen_trust_action_nudge_min_clickthrough_rate := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_MIN_CLICKTHROUGH_RATE", "0.40")
citizen_trust_action_nudge_heartbeat_digest := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_HEARTBEAT_DIGEST", "docs/etl/sprints/AI-OPS-86/evidence/citizen_trust_action_nudges_latest.json")
citizen_trust_action_nudge_heartbeat_path := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_HEARTBEAT_PATH", "docs/etl/runs/citizen_trust_action_nudges_heartbeat.jsonl")
citizen_trust_action_nudge_heartbeat_out := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_HEARTBEAT_OUT", "docs/etl/sprints/AI-OPS-101/evidence/citizen_trust_action_nudges_heartbeat_latest.json")
citizen_trust_action_nudge_heartbeat_window_last := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_HEARTBEAT_WINDOW_LAST", "20")
citizen_trust_action_nudge_heartbeat_window_max_failed := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_HEARTBEAT_WINDOW_MAX_FAILED", "0")
citizen_trust_action_nudge_heartbeat_window_max_failed_rate_pct := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_HEARTBEAT_WINDOW_MAX_FAILED_RATE_PCT", "0")
citizen_trust_action_nudge_heartbeat_window_max_degraded := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_HEARTBEAT_WINDOW_MAX_DEGRADED", "0")
citizen_trust_action_nudge_heartbeat_window_max_degraded_rate_pct := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_HEARTBEAT_WINDOW_MAX_DEGRADED_RATE_PCT", "0")
citizen_trust_action_nudge_heartbeat_window_max_contract_incomplete := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_HEARTBEAT_WINDOW_MAX_CONTRACT_INCOMPLETE", "0")
citizen_trust_action_nudge_heartbeat_window_max_contract_incomplete_rate_pct := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_HEARTBEAT_WINDOW_MAX_CONTRACT_INCOMPLETE_RATE_PCT", "0")
citizen_trust_action_nudge_heartbeat_window_max_nudge_clickthrough_violations := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_HEARTBEAT_WINDOW_MAX_NUDGE_CLICKTHROUGH_VIOLATIONS", "0")
citizen_trust_action_nudge_heartbeat_window_max_nudge_clickthrough_violation_rate_pct := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_HEARTBEAT_WINDOW_MAX_NUDGE_CLICKTHROUGH_VIOLATION_RATE_PCT", "0")
citizen_trust_action_nudge_heartbeat_window_out := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_HEARTBEAT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-101/evidence/citizen_trust_action_nudges_heartbeat_window_latest.json")
citizen_trust_action_nudge_heartbeat_compact_path := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_HEARTBEAT_COMPACT_PATH", "docs/etl/runs/citizen_trust_action_nudges_heartbeat.compacted.jsonl")
citizen_trust_action_nudge_heartbeat_compact_recent := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_HEARTBEAT_COMPACT_RECENT", "20")
citizen_trust_action_nudge_heartbeat_compact_mid_span := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_HEARTBEAT_COMPACT_MID_SPAN", "100")
citizen_trust_action_nudge_heartbeat_compact_mid_every := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_HEARTBEAT_COMPACT_MID_EVERY", "5")
citizen_trust_action_nudge_heartbeat_compact_old_every := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_HEARTBEAT_COMPACT_OLD_EVERY", "20")
citizen_trust_action_nudge_heartbeat_compact_min_raw := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_HEARTBEAT_COMPACT_MIN_RAW", "25")
citizen_trust_action_nudge_heartbeat_compact_out := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_HEARTBEAT_COMPACT_OUT", "docs/etl/sprints/AI-OPS-106/evidence/citizen_trust_action_nudges_heartbeat_compaction_latest.json")
citizen_trust_action_nudge_heartbeat_compact_window_last := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_HEARTBEAT_COMPACT_WINDOW_LAST", "20")
citizen_trust_action_nudge_heartbeat_compact_window_out := env_var_or_default("CITIZEN_TRUST_ACTION_NUDGE_HEARTBEAT_COMPACT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-106/evidence/citizen_trust_action_nudges_heartbeat_compaction_window_latest.json")
citizen_explainability_copy_ui_html := env_var_or_default("CITIZEN_EXPLAINABILITY_COPY_UI_HTML", "ui/citizen/index.html")
citizen_explainability_copy_out := env_var_or_default("CITIZEN_EXPLAINABILITY_COPY_OUT", "docs/etl/sprints/AI-OPS-87/evidence/citizen_explainability_copy_latest.json")
citizen_explainability_copy_min_terms := env_var_or_default("CITIZEN_EXPLAINABILITY_COPY_MIN_TERMS", "4")
citizen_explainability_copy_max_definition_words := env_var_or_default("CITIZEN_EXPLAINABILITY_COPY_MAX_DEFINITION_WORDS", "12")
citizen_explainability_copy_max_copy_sentence_words := env_var_or_default("CITIZEN_EXPLAINABILITY_COPY_MAX_COPY_SENTENCE_WORDS", "16")
citizen_explainability_copy_forbidden_jargon := env_var_or_default("CITIZEN_EXPLAINABILITY_COPY_FORBIDDEN_JARGON", "embedding,ontologia,bayesiano,vectorizacion,heuristica")
citizen_explainability_outcome_events := env_var_or_default("CITIZEN_EXPLAINABILITY_OUTCOME_EVENTS", "tests/fixtures/citizen_explainability_outcome_events_sample.jsonl")
citizen_explainability_outcome_out := env_var_or_default("CITIZEN_EXPLAINABILITY_OUTCOME_OUT", "docs/etl/sprints/AI-OPS-92/evidence/citizen_explainability_outcomes_latest.json")
citizen_explainability_outcome_min_glossary_interaction_events := env_var_or_default("CITIZEN_EXPLAINABILITY_OUTCOME_MIN_GLOSSARY_INTERACTION_EVENTS", "8")
citizen_explainability_outcome_min_help_copy_interaction_events := env_var_or_default("CITIZEN_EXPLAINABILITY_OUTCOME_MIN_HELP_COPY_INTERACTION_EVENTS", "5")
citizen_explainability_outcome_min_adoption_sessions := env_var_or_default("CITIZEN_EXPLAINABILITY_OUTCOME_MIN_ADOPTION_SESSIONS", "5")
citizen_explainability_outcome_min_adoption_completeness_rate := env_var_or_default("CITIZEN_EXPLAINABILITY_OUTCOME_MIN_ADOPTION_COMPLETENESS_RATE", "0.60")
citizen_explainability_outcome_heartbeat_digest := env_var_or_default("CITIZEN_EXPLAINABILITY_OUTCOME_HEARTBEAT_DIGEST", "docs/etl/sprints/AI-OPS-92/evidence/citizen_explainability_outcomes_latest.json")
citizen_explainability_outcome_heartbeat_path := env_var_or_default("CITIZEN_EXPLAINABILITY_OUTCOME_HEARTBEAT_PATH", "docs/etl/runs/citizen_explainability_outcomes_heartbeat.jsonl")
citizen_explainability_outcome_heartbeat_out := env_var_or_default("CITIZEN_EXPLAINABILITY_OUTCOME_HEARTBEAT_OUT", "docs/etl/sprints/AI-OPS-97/evidence/citizen_explainability_outcomes_heartbeat_latest.json")
citizen_explainability_outcome_heartbeat_window_last := env_var_or_default("CITIZEN_EXPLAINABILITY_OUTCOME_HEARTBEAT_WINDOW_LAST", "20")
citizen_explainability_outcome_heartbeat_window_max_failed := env_var_or_default("CITIZEN_EXPLAINABILITY_OUTCOME_HEARTBEAT_WINDOW_MAX_FAILED", "0")
citizen_explainability_outcome_heartbeat_window_max_failed_rate_pct := env_var_or_default("CITIZEN_EXPLAINABILITY_OUTCOME_HEARTBEAT_WINDOW_MAX_FAILED_RATE_PCT", "0")
citizen_explainability_outcome_heartbeat_window_max_degraded := env_var_or_default("CITIZEN_EXPLAINABILITY_OUTCOME_HEARTBEAT_WINDOW_MAX_DEGRADED", "0")
citizen_explainability_outcome_heartbeat_window_max_degraded_rate_pct := env_var_or_default("CITIZEN_EXPLAINABILITY_OUTCOME_HEARTBEAT_WINDOW_MAX_DEGRADED_RATE_PCT", "0")
citizen_explainability_outcome_heartbeat_window_max_contract_incomplete := env_var_or_default("CITIZEN_EXPLAINABILITY_OUTCOME_HEARTBEAT_WINDOW_MAX_CONTRACT_INCOMPLETE", "0")
citizen_explainability_outcome_heartbeat_window_max_contract_incomplete_rate_pct := env_var_or_default("CITIZEN_EXPLAINABILITY_OUTCOME_HEARTBEAT_WINDOW_MAX_CONTRACT_INCOMPLETE_RATE_PCT", "0")
citizen_explainability_outcome_heartbeat_window_out := env_var_or_default("CITIZEN_EXPLAINABILITY_OUTCOME_HEARTBEAT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-97/evidence/citizen_explainability_outcomes_heartbeat_window_latest.json")
citizen_coherence_outcome_events := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_EVENTS", "tests/fixtures/citizen_coherence_drilldown_events_sample.jsonl")
citizen_coherence_outcome_out := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_OUT", "docs/etl/sprints/AI-OPS-99/evidence/citizen_coherence_drilldown_outcomes_latest.json")
citizen_coherence_outcome_min_drilldown_click_events := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_MIN_DRILLDOWN_CLICK_EVENTS", "8")
citizen_coherence_outcome_min_replay_attempt_events := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_MIN_REPLAY_ATTEMPT_EVENTS", "8")
citizen_coherence_outcome_min_replay_success_rate := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_MIN_REPLAY_SUCCESS_RATE", "0.85")
citizen_coherence_outcome_min_contract_complete_click_rate := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_MIN_CONTRACT_COMPLETE_CLICK_RATE", "0.90")
citizen_coherence_outcome_max_replay_failure_rate := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_MAX_REPLAY_FAILURE_RATE", "0.15")
citizen_coherence_outcome_heartbeat_digest := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_HEARTBEAT_DIGEST", "docs/etl/sprints/AI-OPS-99/evidence/citizen_coherence_drilldown_outcomes_latest.json")
citizen_coherence_outcome_heartbeat_path := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_HEARTBEAT_PATH", "docs/etl/runs/citizen_coherence_drilldown_outcomes_heartbeat.jsonl")
citizen_coherence_outcome_heartbeat_out := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_HEARTBEAT_OUT", "docs/etl/sprints/AI-OPS-99/evidence/citizen_coherence_drilldown_outcomes_heartbeat_latest.json")
citizen_coherence_outcome_heartbeat_window_last := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_HEARTBEAT_WINDOW_LAST", "20")
citizen_coherence_outcome_heartbeat_window_max_failed := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_HEARTBEAT_WINDOW_MAX_FAILED", "0")
citizen_coherence_outcome_heartbeat_window_max_failed_rate_pct := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_HEARTBEAT_WINDOW_MAX_FAILED_RATE_PCT", "0")
citizen_coherence_outcome_heartbeat_window_max_degraded := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_HEARTBEAT_WINDOW_MAX_DEGRADED", "0")
citizen_coherence_outcome_heartbeat_window_max_degraded_rate_pct := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_HEARTBEAT_WINDOW_MAX_DEGRADED_RATE_PCT", "0")
citizen_coherence_outcome_heartbeat_window_max_contract_incomplete := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_HEARTBEAT_WINDOW_MAX_CONTRACT_INCOMPLETE", "0")
citizen_coherence_outcome_heartbeat_window_max_contract_incomplete_rate_pct := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_HEARTBEAT_WINDOW_MAX_CONTRACT_INCOMPLETE_RATE_PCT", "0")
citizen_coherence_outcome_heartbeat_window_max_replay_success_rate_violations := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_HEARTBEAT_WINDOW_MAX_REPLAY_SUCCESS_RATE_VIOLATIONS", "0")
citizen_coherence_outcome_heartbeat_window_max_replay_success_rate_violation_rate_pct := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_HEARTBEAT_WINDOW_MAX_REPLAY_SUCCESS_RATE_VIOLATION_RATE_PCT", "0")
citizen_coherence_outcome_heartbeat_window_max_contract_click_rate_violations := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_HEARTBEAT_WINDOW_MAX_CONTRACT_CLICK_RATE_VIOLATIONS", "0")
citizen_coherence_outcome_heartbeat_window_max_contract_click_rate_violation_rate_pct := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_HEARTBEAT_WINDOW_MAX_CONTRACT_CLICK_RATE_VIOLATION_RATE_PCT", "0")
citizen_coherence_outcome_heartbeat_window_max_replay_failure_rate_violations := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_HEARTBEAT_WINDOW_MAX_REPLAY_FAILURE_RATE_VIOLATIONS", "0")
citizen_coherence_outcome_heartbeat_window_max_replay_failure_rate_violation_rate_pct := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_HEARTBEAT_WINDOW_MAX_REPLAY_FAILURE_RATE_VIOLATION_RATE_PCT", "0")
citizen_coherence_outcome_heartbeat_window_out := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_HEARTBEAT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-99/evidence/citizen_coherence_drilldown_outcomes_heartbeat_window_latest.json")
citizen_coherence_outcome_heartbeat_compact_path := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_HEARTBEAT_COMPACT_PATH", "docs/etl/runs/citizen_coherence_drilldown_outcomes_heartbeat.compacted.jsonl")
citizen_coherence_outcome_heartbeat_compact_recent := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_HEARTBEAT_COMPACT_RECENT", "20")
citizen_coherence_outcome_heartbeat_compact_mid_span := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_HEARTBEAT_COMPACT_MID_SPAN", "100")
citizen_coherence_outcome_heartbeat_compact_mid_every := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_HEARTBEAT_COMPACT_MID_EVERY", "5")
citizen_coherence_outcome_heartbeat_compact_old_every := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_HEARTBEAT_COMPACT_OLD_EVERY", "20")
citizen_coherence_outcome_heartbeat_compact_min_raw := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_HEARTBEAT_COMPACT_MIN_RAW", "25")
citizen_coherence_outcome_heartbeat_compact_out := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_HEARTBEAT_COMPACT_OUT", "docs/etl/sprints/AI-OPS-104/evidence/citizen_coherence_drilldown_outcomes_heartbeat_compaction_latest.json")
citizen_coherence_outcome_heartbeat_compact_window_last := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_HEARTBEAT_COMPACT_WINDOW_LAST", "20")
citizen_coherence_outcome_heartbeat_compact_window_out := env_var_or_default("CITIZEN_COHERENCE_OUTCOME_HEARTBEAT_COMPACT_WINDOW_OUT", "docs/etl/sprints/AI-OPS-104/evidence/citizen_coherence_drilldown_outcomes_heartbeat_compaction_window_latest.json")

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

etl-backfill-policy-events-money:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py backfill-policy-events-money --db {{db_path}}"

etl-backfill-money-staging:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py backfill-money-staging --db {{db_path}}"

etl-backfill-money-contract-records:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py backfill-money-contract-records --db {{db_path}}"

etl-backfill-money-subsidy-records:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py backfill-money-subsidy-records --db {{db_path}}"

etl-test:
  docker compose run --rm --build etl "python3 -m unittest discover -s tests -v"

add-source source_id name scope url format="json" min_records="1":
  python3 scripts/add_source.py "{{source_id}}" --name "{{name}}" --scope "{{scope}}" --url "{{url}}" --format "{{format}}" --min-records "{{min_records}}"

etl-schema-compat-check:
  python3 scripts/ingestar_politicos_es.py init-db --db /tmp/vota-schema-compat.db
  rm -f /tmp/vota-schema-compat.db

etl-contributor-gates:
  python3 -m unittest tests.test_source_onboarding_scaffold tests.test_samples_e2e -q
  just etl-schema-compat-check
  just etl-export-source-catalog
  just privacy-check-public-artifacts
  just etl-publish-hf-dry-run

etl-live:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source all --snapshot-date {{snapshot_date}} --timeout {{municipal_timeout}}"
  @just etl-live-parlamentario

etl-live-parlamentario:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py ingest --db {{db_path}} --source congreso_votaciones --snapshot-date {{snapshot_date}} --timeout {{textdoc_timeout}} --congreso-legs {{live_parl_congreso_legs}} --max-votes {{live_parl_max_votes}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py ingest --db {{db_path}} --source congreso_iniciativas --snapshot-date {{snapshot_date}} --timeout {{textdoc_timeout}} --max-files {{live_parl_max_files}} --max-records {{live_parl_max_records}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py ingest --db {{db_path}} --source senado_votaciones --snapshot-date {{snapshot_date}} --timeout {{textdoc_timeout}} --senado-legs {{live_parl_senado_legs}} --max-votes {{live_parl_max_votes}} --senado-skip-details"
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py ingest --db {{db_path}} --source senado_iniciativas --snapshot-date {{snapshot_date}} --timeout {{textdoc_timeout}} --senado-legs {{live_parl_senado_legs}} --max-records {{live_parl_max_records}}"

etl-elecciones:
  docker compose run --rm --build etl "python3 scripts/generar_proximas_elecciones_espana.py --today {{snapshot_date}} --timeout {{infoelectoral_timeout}} --public-json-out ui/gh-pages-next/public/calendario-electoral/data/election-calendar.json"

etl-publish-representantes:
  docker compose run --rm --build etl "python3 scripts/publicar_representantes_es.py --db {{db_path}} --snapshot-date {{snapshot_date}}"

etl-publish-votaciones:
  docker compose run --rm --build etl "python3 scripts/publicar_votaciones_es.py --db {{db_path}} --snapshot-date {{snapshot_date}}"

etl-publish-votaciones-unmatched:
  docker compose run --rm --build etl "python3 scripts/publicar_votaciones_es.py --db {{db_path}} --snapshot-date {{snapshot_date}} --include-unmatched --unmatched-sample-limit 100"

etl-publish-infoelectoral:
  docker compose run --rm --build etl "python3 scripts/publicar_infoelectoral_es.py --db {{db_path}} --snapshot-date {{snapshot_date}}"

etl-export-source-catalog:
  python3 scripts/export_source_catalog_snapshot.py \
    --db "{{db_path}}" \
    --snapshot-date "{{snapshot_date}}" \
    --out "{{gh_pages_dir}}/explorer-sources/data/catalog.json" \
    --published-out "etl/data/published/source-catalog-{{snapshot_date}}.json" \
    --latest-out "etl/data/published/source-catalog-latest.json"

etl-discover-andalucia-2026-execution-sources:
  python3 scripts/discover_andalucia_2026_execution_sources.py \
    --out "{{andalucia_execution_source_discovery_out}}" \
    --timeout "{{andalucia_execution_source_query_timeout}}" \
    --max-topic-terms "{{andalucia_execution_source_max_topic_terms}}" \
    --probe-timeout "{{andalucia_execution_source_probe_timeout}}" \
    --max-resource-probes "{{andalucia_execution_source_max_resource_probes}}"

etl-run-andalucia-2026-delivery-evidence-hunts:
  python3 scripts/run_andalucia_2026_delivery_evidence_hunts.py \
    --out "{{andalucia_delivery_hunt_results_out}}" \
    --public-out "{{andalucia_delivery_hunt_public_out}}" \
    --max-targets "{{andalucia_delivery_hunt_max_targets}}" \
    --rows-per-query "{{andalucia_delivery_hunt_rows_per_query}}" \
    --timeout "{{andalucia_delivery_hunt_timeout}}"

etl-generate-andalucia-2026-delivery-review-drafts:
  python3 scripts/generate_andalucia_2026_delivery_review_drafts.py \
    --hunt-results "{{andalucia_delivery_hunt_results_out}}" \
    --out "{{andalucia_delivery_review_drafts_out}}" \
    --public-out "{{andalucia_delivery_review_drafts_public_out}}"

etl-andalucia-2026-accountability-assist:
  just etl-discover-andalucia-2026-execution-sources
  python3 scripts/export_andalucia_2026_accountability_snapshot.py \
    --db "{{db_path}}" \
    --timeout "{{infoelectoral_timeout}}" \
    --refresh-outcome-series
  just etl-run-andalucia-2026-delivery-evidence-hunts
  just etl-generate-andalucia-2026-delivery-review-drafts
  python3 scripts/generate_andalucia_2026_boja_review_drafts.py
  python3 scripts/apply_andalucia_2026_boja_review_drafts.py \
    --out "etl/data/published/andalucia-2026-boja-review-apply-dry-run.json"
  python3 scripts/generate_andalucia_2026_parliament_vote_review_drafts.py
  python3 scripts/apply_andalucia_2026_parliament_vote_review_drafts.py \
    --out "etl/data/published/andalucia-2026-parliament-vote-review-apply-dry-run.json"
  python3 scripts/generate_andalucia_2026_issue_review_drafts.py
  python3 scripts/apply_andalucia_2026_issue_review_drafts.py \
    --out "etl/data/published/andalucia-2026-issue-review-apply-dry-run.json"
  python3 scripts/generate_andalucia_2026_execution_review_drafts.py
  python3 scripts/apply_andalucia_2026_execution_review_drafts.py \
    --auto-safe \
    --out "etl/data/published/andalucia-2026-execution-evidence-review-apply-dry-run.json"

etl-andalucia-2026-accountability-apply-safe:
  just etl-discover-andalucia-2026-execution-sources
  python3 scripts/export_andalucia_2026_accountability_snapshot.py \
    --db "{{db_path}}" \
    --timeout "{{infoelectoral_timeout}}" \
    --refresh-outcome-series
  just etl-run-andalucia-2026-delivery-evidence-hunts
  just etl-generate-andalucia-2026-delivery-review-drafts
  python3 scripts/generate_andalucia_2026_boja_review_drafts.py
  python3 scripts/apply_andalucia_2026_boja_review_drafts.py --apply \
    --out "etl/data/published/andalucia-2026-boja-review-apply-report.json"
  python3 scripts/generate_andalucia_2026_parliament_vote_review_drafts.py
  python3 scripts/apply_andalucia_2026_parliament_vote_review_drafts.py --apply \
    --out "etl/data/published/andalucia-2026-parliament-vote-review-apply-report.json"
  python3 scripts/generate_andalucia_2026_issue_review_drafts.py
  python3 scripts/apply_andalucia_2026_issue_review_drafts.py --apply \
    --out "etl/data/published/andalucia-2026-issue-review-apply-report.json"
  python3 scripts/generate_andalucia_2026_execution_review_drafts.py
  python3 scripts/apply_andalucia_2026_execution_review_drafts.py --apply \
    --auto-safe \
    --out "etl/data/published/andalucia-2026-execution-evidence-review-apply-report.json"
  python3 scripts/export_andalucia_2026_accountability_snapshot.py \
    --db "{{db_path}}" \
    --timeout "{{infoelectoral_timeout}}" \
    --published-out "etl/data/published/andalucia-2026-accountability.json" \
    --refresh-outcome-series

etl-andalucia-2026-accountability-apply-safe-prime:
  just etl-andalucia-2026-accountability-apply-safe
  mkdir -p "{{gh_pages_dir}}/elecciones/andalucia-2026/data"
  mkdir -p "{{gh_pages_next_app_dir}}/public/elecciones/andalucia-2026/data"
  for item in \\
    accountability.json \\
    delivery-evidence-hunt-results.json \\
    delivery-evidence-review-drafts.json \\
    boja-impact-review-queue.csv \\
    parliament-vote-impact-review-queue.csv \\
    execution-evidence-queue.csv; do \\
      src="{{gh_pages_next_app_dir}}/public/elecciones/andalucia-2026/data/$item"; \\
      fallback="{{gh_pages_dir}}/elecciones/andalucia-2026/data/$item"; \\
      if [ -f "$src" ]; then cp -f "$src" "$fallback"; \\
      elif [ -f "$fallback" ]; then :; \\
      else echo "warn: missing andalu data artifact $item"; fi; \\
    done

etl-andalucia-2026-accountability-apply-safe-prime-full:
  just etl-andalucia-2026-accountability-apply-safe-prime
  just gh-pages-next-prime

etl-andalucia-2026-accountability-full:
  just etl-andalucia-2026-accountability-apply-safe-prime-full

etl-export-source-scrape-queue:
  python3 scripts/export_source_scrape_queue_snapshot.py \
    --db "{{db_path}}" \
    --snapshot-date "{{snapshot_date}}" \
    --out "{{gh_pages_dir}}/explorer-sources/data/scrape-queue.json" \
    --published-out "etl/data/published/source-scrape-queue-{{snapshot_date}}.json" \
    --latest-out "etl/data/published/source-scrape-queue-latest.json"

etl-backfill-accountability-ledger:
  set -e; \
  accountability_db="{{db_path}}"; \
  if [ -n "{{accountability_ledger_db_path}}" ]; then accountability_db="{{accountability_ledger_db_path}}"; fi; \
  python3 scripts/backfill_persons_from_vote_member_names.py --db "$accountability_db"; \
  python3 scripts/backfill_mandates_from_vote_member_names.py --db "$accountability_db"; \
  python3 scripts/backfill_parliamentary_groups_from_vote_member_votes.py --db "$accountability_db"; \
  python3 scripts/backfill_accountability_ledger_from_parliament.py --db "$accountability_db"; \
  python3 scripts/backfill_accountability_ledger_from_legal_responsibilities.py --db "$accountability_db"; \
  python3 scripts/backfill_accountability_ledger_from_sanction_norm_catalog.py --db "$accountability_db"; \
  python3 scripts/ingestar_politicos_es.py backfill-policy-events-money --db "$accountability_db"; \
  python3 scripts/ingestar_politicos_es.py backfill-policy-events-boe --db "$accountability_db"; \
  python3 scripts/backfill_accountability_ledger_from_policy_events.py --db "$accountability_db"; \
  python3 scripts/backfill_accountability_ledger_from_boe_appointments.py --db "$accountability_db"; \
  python3 scripts/backfill_accountability_ledger_actor_ids.py --db "$accountability_db"

etl-ingest-boe-sumario-snapshot:
  set -e; \
  accountability_db="{{db_path}}"; \
  if [ -n "{{accountability_ledger_db_path}}" ]; then accountability_db="{{accountability_ledger_db_path}}"; fi; \
  boe_date="$(printf '%s' '{{snapshot_date}}' | tr -d '-')"; \
  python3 scripts/ingestar_politicos_es.py ingest \
    --db "$accountability_db" \
    --source boe_api_legal \
    --url "https://www.boe.es/datosabiertos/api/boe/sumario/${boe_date}" \
    --snapshot-date "{{snapshot_date}}" \
    --strict-network

etl-export-accountability-ledger:
  accountability_db="{{db_path}}"; \
  if [ -n "{{accountability_ledger_db_path}}" ]; then accountability_db="{{accountability_ledger_db_path}}"; fi; \
  python3 scripts/export_accountability_ledger_snapshot.py \
    --db "$accountability_db" \
    --snapshot-date "{{snapshot_date}}" \
    --out "etl/data/published/accountability-ledger-{{snapshot_date}}.json" \
    --latest-out "etl/data/published/accountability-ledger-latest.json" \
    --max-entries-per-issue "{{accountability_ledger_max_entries_per_issue}}" \
    --max-sample-entries-per-actor "{{accountability_ledger_max_sample_entries_per_actor}}"

etl-export-accountability-dossiers:
  accountability_db="{{db_path}}"; \
  if [ -n "{{accountability_ledger_db_path}}" ]; then accountability_db="{{accountability_ledger_db_path}}"; fi; \
  python3 scripts/export_accountability_dossier_snapshot.py \
    --db "$accountability_db" \
    --snapshot-date "{{snapshot_date}}" \
    --out "etl/data/published/accountability-dossiers-{{snapshot_date}}.json" \
    --latest-out "etl/data/published/accountability-dossiers-latest.json" \
    --max-issues-per-actor "{{accountability_dossiers_max_issues_per_actor}}" \
    --max-actors-per-issue "{{accountability_dossiers_max_actors_per_issue}}"

etl-export-accountability-evidence-api:
  python3 scripts/export_accountability_evidence_api_snapshot.py \
    --dossiers "etl/data/published/accountability-dossiers-{{snapshot_date}}.json" \
    --ledger "etl/data/published/accountability-ledger-{{snapshot_date}}.json" \
    --snapshot-date "{{snapshot_date}}" \
    --out "etl/data/published/accountability-evidence-api-{{snapshot_date}}.json" \
    --latest-out "etl/data/published/accountability-evidence-api-latest.json"

etl-export-accountability-actor-resolution-queue:
  accountability_db="{{db_path}}"; \
  if [ -n "{{accountability_ledger_db_path}}" ]; then accountability_db="{{accountability_ledger_db_path}}"; fi; \
  python3 scripts/export_accountability_actor_resolution_queue.py \
    --db "$accountability_db" \
    --snapshot-date "{{snapshot_date}}" \
    --out "{{accountability_actor_resolution_queue_out}}" \
    --csv-out "{{accountability_actor_resolution_queue_csv_out}}" \
    --limit "{{accountability_actor_resolution_queue_limit}}"

etl-export-accountability-issue-cluster-assignment-review-queue:
  python3 scripts/export_accountability_issue_cluster_assignment_review_queue.py \
    --evidence-api "etl/data/published/accountability-evidence-api-{{snapshot_date}}.json" \
    --snapshot-date "{{snapshot_date}}" \
    --out "{{accountability_issue_cluster_assignment_review_queue_out}}" \
    --csv-out "{{accountability_issue_cluster_assignment_review_queue_csv_out}}" \
    --limit "{{accountability_issue_cluster_assignment_review_queue_limit}}"

etl-apply-accountability-issue-cluster-assignment-reviews:
  python3 scripts/apply_accountability_issue_cluster_assignment_reviews.py \
    --csv "{{accountability_issue_cluster_assignment_reviews_csv}}" \
    --seed "etl/data/seeds/accountability_issue_cluster_issue_reviews_seed_v1.json" \
    --out "etl/data/seeds/accountability_issue_cluster_issue_reviews_seed_v1.json" \
    --report-out "{{accountability_issue_cluster_assignment_reviews_report_out}}"

etl-validate-accountability-artifacts:
  python3 scripts/validate_accountability_artifacts.py \
    --ledger "etl/data/published/accountability-ledger-{{snapshot_date}}.json" \
    --dossiers "etl/data/published/accountability-dossiers-{{snapshot_date}}.json" \
    --evidence-api "etl/data/published/accountability-evidence-api-{{snapshot_date}}.json" \
    --snapshot-date "{{snapshot_date}}" \
    --min-entries "{{accountability_min_entries}}" \
    --min-actors "{{accountability_min_actors}}" \
    --min-issues "{{accountability_min_issues}}" \
    --min-evidence-api-questions "{{accountability_min_evidence_api_questions}}" \
    --min-evidence-api-issue-clusters "{{accountability_min_evidence_api_issue_clusters}}" \
    --min-evidence-api-reviewed-issue-clusters "{{accountability_min_evidence_api_reviewed_issue_clusters}}" \
    --min-evidence-api-issue-cluster-issue-reviews "{{accountability_min_evidence_api_issue_cluster_issue_reviews}}" \
    --min-evidence-api-issue-cluster-assignment-review-needed "{{accountability_min_evidence_api_issue_cluster_assignment_review_needed}}" \
    --max-evidence-api-issue-cluster-assignment-review-needed "{{accountability_max_evidence_api_issue_cluster_assignment_review_needed}}" \
    --min-evidence-api-gap-answers "{{accountability_min_evidence_api_gap_answers}}" \
    --min-evidence-api-blocker-answers "{{accountability_min_evidence_api_blocker_answers}}" \
    --min-evidence-api-qa-answers "{{accountability_min_evidence_api_qa_answers}}" \
    --min-resolution-pct "{{accountability_min_resolution_pct}}" \
    --min-person-id-entries "{{accountability_min_person_id_entries}}" \
    --min-party-id-entries "{{accountability_min_party_id_entries}}" \
    --min-parliamentary-group-id-entries "{{accountability_min_parliamentary_group_id_entries}}" \
    --max-ledger-bytes "{{accountability_max_ledger_bytes}}" \
    --max-dossiers-bytes "{{accountability_max_dossiers_bytes}}" \
    --max-evidence-api-bytes "{{accountability_max_evidence_api_bytes}}"

etl-refresh-accountability-ledger:
  just etl-backfill-accountability-ledger
  just etl-export-accountability-ledger
  just etl-export-accountability-dossiers
  just etl-export-accountability-evidence-api
  just etl-validate-accountability-artifacts
  just etl-export-accountability-actor-resolution-queue
  just etl-export-accountability-issue-cluster-assignment-review-queue

etl-run-source-scrape-queue:
  python3 scripts/run_source_scrape_queue.py \
    --db "{{db_path}}" \
    --snapshot-date "{{snapshot_date}}" \
    --only-repeatable-now \
    --summary-out "docs/etl/runs/source-scrape-queue-run-{{snapshot_date}}.json"

etl-run-source-scrape-queue-prefect:
  python3 scripts/run_source_scrape_queue_prefect.py \
    --db "{{db_path}}" \
    --snapshot-date "{{snapshot_date}}" \
    --only-repeatable-now \
    --summary-out "docs/etl/runs/source-scrape-queue-prefect-run-{{snapshot_date}}.json"

etl-publish-hf:
  just etl-scale-readiness
  if [ "{{hf_require_quality_report}}" = "1" ]; then just parl-quality-report-hf; fi
  just etl-export-source-catalog
  just etl-export-source-scrape-queue
  just etl-export-accountability-ledger
  just etl-export-accountability-dossiers
  just etl-export-accountability-evidence-api
  just etl-validate-accountability-artifacts
  python3 scripts/check_public_privacy_leaks.py --path etl/data/published
  sqlite_arg="--skip-sqlite-gz"; \
  sensitive_arg=""; \
  quality_arg=""; \
  liberty_atlas_arg=""; \
  if [ "{{hf_include_sqlite_gz}}" = "1" ]; then sqlite_arg=""; fi; \
  if [ "{{hf_allow_sensitive_parquet}}" = "1" ]; then sensitive_arg="--allow-sensitive-parquet"; fi; \
  if [ "{{hf_require_quality_report}}" = "1" ]; then quality_arg="--require-quality-report"; fi; \
  if [ "{{hf_require_liberty_atlas_release_latest}}" = "1" ]; then liberty_atlas_arg="--require-liberty-atlas-release-latest"; fi; \
  docker compose run --rm --build etl "python3 scripts/publicar_hf_snapshot.py --db {{db_path}} --snapshot-date {{snapshot_date}} --dataset-repo {{hf_dataset_repo_id}} --parquet-compression {{hf_parquet_compression}} --parquet-batch-rows {{hf_parquet_batch_rows}} --parquet-tables '{{hf_parquet_tables}}' --parquet-exclude-tables '{{hf_parquet_exclude_tables}}' ${sqlite_arg} ${sensitive_arg} ${quality_arg} ${liberty_atlas_arg}"

etl-publish-hf-dry-run:
  just etl-scale-readiness
  if [ "{{hf_require_quality_report}}" = "1" ]; then just parl-quality-report-hf; fi
  just etl-export-source-catalog
  just etl-export-source-scrape-queue
  just etl-export-accountability-ledger
  just etl-export-accountability-dossiers
  just etl-export-accountability-evidence-api
  just etl-validate-accountability-artifacts
  python3 scripts/check_public_privacy_leaks.py --path etl/data/published
  sqlite_arg="--skip-sqlite-gz"; \
  sensitive_arg=""; \
  quality_arg=""; \
  liberty_atlas_arg=""; \
  if [ "{{hf_include_sqlite_gz}}" = "1" ]; then sqlite_arg=""; fi; \
  if [ "{{hf_allow_sensitive_parquet}}" = "1" ]; then sensitive_arg="--allow-sensitive-parquet"; fi; \
  if [ "{{hf_require_quality_report}}" = "1" ]; then quality_arg="--require-quality-report"; fi; \
  if [ "{{hf_require_liberty_atlas_release_latest}}" = "1" ]; then liberty_atlas_arg="--require-liberty-atlas-release-latest"; fi; \
  docker compose run --rm --build etl "python3 scripts/publicar_hf_snapshot.py --db {{db_path}} --snapshot-date {{snapshot_date}} --dataset-repo {{hf_dataset_repo_id}} --parquet-compression {{hf_parquet_compression}} --parquet-batch-rows {{hf_parquet_batch_rows}} --parquet-tables '{{hf_parquet_tables}}' --parquet-exclude-tables '{{hf_parquet_exclude_tables}}' --dry-run ${sqlite_arg} ${sensitive_arg} ${quality_arg} ${liberty_atlas_arg}"

etl-verify-hf-quality:
  out_arg=""; \
  if [ -n "{{hf_verify_out}}" ]; then out_arg="--json-out {{hf_verify_out}}"; fi; \
  docker compose run --rm --build etl "python3 scripts/verify_hf_snapshot_quality.py --dataset-repo {{hf_dataset_repo_id}} --snapshot-date {{snapshot_date}} --timeout {{hf_verify_timeout}} ${out_arg}"

etl-scale-origin-hf-dry-run:
  just etl-scale-readiness
  just privacy-check-public-artifacts
  out_arg=""; \
  if [ -n "{{hf_scale_report_out}}" ]; then out_arg="--report-out {{hf_scale_report_out}}"; fi; \
  {{hf_scale_python}} scripts/publicar_hf_scale_snapshot.py --registry {{hf_scale_registry}} --readiness {{hf_scale_readiness}} --snapshot-date {{snapshot_date}} --dataset-repo {{hf_dataset_repo_id}} ${out_arg}

etl-scale-origin-hf-publish:
  just etl-scale-readiness
  just privacy-check-public-artifacts
  out_arg=""; \
  if [ -n "{{hf_scale_report_out}}" ]; then out_arg="--report-out {{hf_scale_report_out}}"; fi; \
  {{hf_scale_python}} scripts/publicar_hf_scale_snapshot.py --registry {{hf_scale_registry}} --readiness {{hf_scale_readiness}} --snapshot-date {{snapshot_date}} --dataset-repo {{hf_dataset_repo_id}} --publish ${out_arg}

etl-scale-origin-hf-verify:
  out_arg=""; \
  if [ -n "{{hf_scale_verify_out}}" ]; then out_arg="--json-out {{hf_scale_verify_out}}"; fi; \
  {{hf_scale_python}} scripts/verify_hf_scale_origin.py --dataset-repo {{hf_dataset_repo_id}} --registry {{hf_scale_registry}} --readiness {{hf_scale_readiness}} --timeout {{hf_verify_timeout}} ${out_arg}

etl-scale-origin-hf-restore:
  corpus_arg=""; \
  snapshot_arg=""; \
  report_arg=""; \
  if [ -n "{{hf_scale_restore_corpus_ids}}" ]; then corpus_arg="--corpus-ids {{hf_scale_restore_corpus_ids}}"; fi; \
  if [ -n "{{hf_scale_restore_snapshot_path}}" ]; then snapshot_arg="--snapshot-path {{hf_scale_restore_snapshot_path}}"; fi; \
  if [ -n "{{hf_scale_restore_report_out}}" ]; then report_arg="--report-out {{hf_scale_restore_report_out}}"; fi; \
  python3 scripts/restore_hf_scale_origin.py --dataset-repo {{hf_dataset_repo_id}} --destination {{hf_scale_restore_destination}} --workers {{hf_scale_restore_workers}} --timeout {{hf_verify_timeout}} --min-free-bytes {{hf_scale_restore_min_free_bytes}} ${snapshot_arg} ${corpus_arg} ${report_arg}

etl-scale-origin-hf-validate-restored:
  corpus_arg=""; \
  report_arg=""; \
  if [ -n "{{hf_scale_restore_corpus_ids}}" ]; then corpus_arg="--corpus-ids {{hf_scale_restore_corpus_ids}}"; fi; \
  if [ -n "{{hf_scale_restore_validation_out}}" ]; then report_arg="--report-out {{hf_scale_restore_validation_out}}"; fi; \
  uv run --no-project --with pyarrow python scripts/validate_restored_scale_origin.py --root {{hf_scale_restore_destination}} --registry {{hf_scale_registry}} --max-peak-rss-mb {{hf_scale_restore_validation_max_rss_mb}} ${corpus_arg} ${report_arg} --enforce

etl-scale-origin-hf-restore-validate:
  just etl-scale-origin-hf-restore
  just etl-scale-origin-hf-validate-restored

etl-scale-origin-sqlite-rebuild:
  report_arg=""; \
  if [ -n "{{hf_scale_rebuild_report_out}}" ]; then report_arg="--report-out {{hf_scale_rebuild_report_out}}"; fi; \
  uv run --no-project --with pyarrow python scripts/rebuild_restored_scale_sqlite.py --root {{hf_scale_restore_destination}} --corpus-id {{hf_scale_rebuild_corpus_id}} --output {{hf_scale_rebuild_output}} --max-peak-rss-mb {{hf_scale_restore_validation_max_rss_mb}} ${report_arg}

etl-scale-origin-hf-restore-bdns:
  HF_SCALE_RESTORE_CORPUS_IDS=bdns_public_money just etl-scale-origin-hf-restore
  docker compose run --rm etl "python3 scripts/validate_semantic_partitions.py --lane public_money_facts --root {{hf_scale_restore_destination}}/corpora/bdns_public_money/data --manifest {{hf_scale_restore_destination}}/corpora/bdns_public_money/manifest.json --min-rows 1000000 --max-peak-rss-mb 1024 --enforce"

etl-publish-hf-verify:
  just etl-publish-hf
  just etl-verify-hf-quality

etl-publish-hf-raw:
  manual_arg=""; \
  if [ "{{hf_raw_include_manual}}" = "1" ]; then manual_arg="--include-manual"; fi; \
  docker compose run --rm --build etl "python3 scripts/publicar_hf_raw_blocks.py --raw-dir etl/data/raw --snapshot-date {{snapshot_date}} --dataset-repo {{hf_raw_dataset_repo_id}} --max-files-per-block {{hf_raw_max_files_per_block}} ${manual_arg}"

etl-publish-hf-raw-dry-run:
  manual_arg=""; \
  if [ "{{hf_raw_include_manual}}" = "1" ]; then manual_arg="--include-manual"; fi; \
  docker compose run --rm --build etl "python3 scripts/publicar_hf_raw_blocks.py --raw-dir etl/data/raw --snapshot-date {{snapshot_date}} --dataset-repo {{hf_raw_dataset_repo_id}} --max-files-per-block {{hf_raw_max_files_per_block}} --dry-run ${manual_arg}"

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

# Offline authoritative refresh. Requires cached XML and never attempts network.
parl-refresh-senado-local-cache:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-member-ids --db {{db_path}} --source-ids senado_votaciones --batch-size 10000 --unmatched-sample-limit 0"
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-senado-details --db {{db_path}} --snapshot-date {{snapshot_date}} --include-existing --senado-detail-dir {{senado_manual_detail_dir}} --local-cache-only --detail-workers {{senado_detail_workers}}"

parl-senado-tail-daemon:
  DB_PATH={{db_path}} \
  COOKIE_FILE={{senado_tail_cookie_file}} \
  BURST_LIMIT={{senado_tail_burst_limit}} \
  WIDE_LIMIT={{senado_tail_wide_limit}} \
  TIMEOUT_SECS={{senado_tail_timeout}} \
  COOLDOWN_SECS={{senado_tail_cooldown}} \
  ACTIVE_SLEEP_SECS={{senado_tail_active_sleep}} \
  MAX_IDLE_ROUNDS={{senado_tail_max_idle_rounds}} \
  MAX_ROUNDS={{senado_tail_max_rounds}} \
  STOP_ON_UNIFORM_404={{senado_tail_stop_on_uniform_404}} \
  ARCHIVE_FALLBACK={{senado_tail_archive_fallback}} \
  ARCHIVE_TIMEOUT={{senado_tail_archive_timeout}} \
  bash scripts/senado_tail_daemon.sh

parl-link-votes:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py link-votes --db {{db_path}}"

parl-backfill-topic-analytics:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-topic-analytics --db {{db_path}} --as-of-date {{snapshot_date}} --taxonomy-seed {{topic_taxonomy_seed}}"

parl-backfill-text-documents:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-text-documents --db {{db_path}} --source-id congreso_intervenciones --limit {{textdoc_limit}} --only-missing --timeout {{textdoc_timeout}}"

parl-backfill-initiative-links:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-initiative-links --db {{db_path}} --source-ids congreso_iniciativas,senado_iniciativas"

parl-backfill-senado-detail-publication-links:
  docker compose run --rm --build etl "python3 scripts/backfill_senado_publication_links_from_detail_docs.py --db {{db_path}} --source-id senado_iniciativas --doc-source-id parl_initiative_docs --only-initiatives-with-missing-docs --limit {{senado_detail_links_limit}}"

parl-backfill-initiative-documents:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents --db {{db_path}} --initiative-source-ids congreso_iniciativas,senado_iniciativas --raw-dir etl/data/raw --timeout {{initdoc_timeout}} --snapshot-date {{snapshot_date}} --limit-initiatives {{initdoc_limit}} --max-docs-per-initiative {{initdoc_max_per}}"

parl-backfill-initiative-documents-auto:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents --db {{db_path}} --initiative-source-ids congreso_iniciativas,senado_iniciativas --raw-dir etl/data/raw --timeout {{initdoc_timeout}} --snapshot-date {{snapshot_date}} --limit-initiatives {{initdoc_limit}} --max-docs-per-initiative {{initdoc_max_per}} --auto --max-loops 50"

parl-backfill-initiative-documents-archive:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents --db {{db_path}} --initiative-source-ids senado_iniciativas --include-unlinked --retry-forbidden --archive-fallback --archive-timeout {{initdoc_archive_timeout}} --archive-fallback-http-statuses '{{initdoc_archive_http_statuses}}' --raw-dir etl/data/raw --timeout {{initdoc_timeout}} --snapshot-date {{snapshot_date}} --limit-initiatives {{initdoc_limit}} --max-docs-per-initiative {{initdoc_max_per}}"

parl-export-initdoc-analysis-queue:
  docker compose run --rm --build etl "python3 scripts/export_pdf_analysis_queue.py --db {{db_path}} --initiative-source-id {{initdoc_excerpt_scope}} --doc-source-id parl_initiative_docs --only-missing-excerpt --limit {{doc_analysis_limit}} --out {{doc_analysis_out}}"

parl-export-text-extraction-queue:
  python3 scripts/export_text_extraction_queue.py --db {{db_path}} --source-ids '{{text_extraction_queue_source_ids}}' --formats '{{text_extraction_queue_formats}}' --dedupe-by content_sha256 --limit {{text_extraction_queue_limit}} --out {{text_extraction_queue_out}} --summary-out {{text_extraction_queue_summary_out}}

parl-export-text-extraction-queue-missing:
  python3 scripts/export_text_extraction_queue.py --db {{db_path}} --source-ids '{{text_extraction_queue_source_ids}}' --formats '{{text_extraction_queue_formats}}' --only-missing-excerpt --dedupe-by content_sha256 --limit {{text_extraction_queue_limit}} --out {{text_extraction_queue_out}} --summary-out {{text_extraction_queue_summary_out}}

# Durable high-volume queue producers. These stream references in bounded
# batches; raw bytes and source payloads are never copied into queue rows.
etl-enqueue-source-record-work:
  python3 scripts/enqueue_pipeline_work.py --db {{db_path}} --kind source-record-transform --batch-size {{scale_queue_enqueue_batch_size}}

parl-enqueue-document-fetch-work:
  python3 scripts/enqueue_pipeline_work.py --db {{db_path}} --kind document-fetch --source-ids 'congreso_iniciativas,senado_iniciativas' --only-missing --batch-size {{scale_queue_enqueue_batch_size}}

parl-run-document-fetch-work:
  python3 scripts/run_document_fetch_queue.py --db {{db_path}} --raw-root etl/data/raw/text_documents/parl_initiative_docs --workers {{document_fetch_workers}} --per-host-workers {{document_fetch_per_host_workers}} --claim-size {{document_fetch_claim_size}} --max-items {{document_fetch_max_items}} --max-bytes {{document_fetch_max_bytes}} --report-out {{document_fetch_report_out}}

parl-enqueue-text-extraction-work:
  python3 scripts/enqueue_pipeline_work.py --db {{db_path}} --kind text-extract --source-ids '{{text_extraction_queue_source_ids}}' --only-missing --batch-size {{scale_queue_enqueue_batch_size}}

parl-run-text-extraction-work:
  python3 scripts/run_text_extraction_queue.py --db {{db_path}} --text-root etl/data/derived/text --workers {{text_extraction_workers}} --claim-size {{text_extraction_claim_size}} --max-items {{text_extraction_max_items}} --report-out {{text_extraction_report_out}}

parl-document-pipeline-scale:
  just parl-enqueue-document-fetch-work
  just parl-run-document-fetch-work
  just parl-enqueue-text-extraction-work
  just parl-run-text-extraction-work

etl-scale-readiness:
  just real-data-only-check
  docker compose run --rm etl "python3 scripts/report_scale_readiness.py --registry docs/etl/real-corpus-registry.json --out {{scale_readiness_report_out}} --enforce-foundation"

real-data-only-check:
  python3 scripts/check_real_data_only.py \
    --db "{{db_path}}" \
    --path etl/data/raw \
    --path etl/data/derived \
    --path etl/data/published \
    --path "{{gh_pages_next_app_dir}}/public" \
    --out docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-data-only-validation.json \
    --enforce

# Fail closed on malformed SQLite files, FK damage, recovery residue, stale
# ingestion markers, and truncated derived text artifacts.
etl-data-integrity-audit:
  python3 scripts/audit_data_integrity.py --report-out etl/data/published/data-integrity-latest.json --enforce

etl-data-integrity-audit-all-staging:
  python3 scripts/audit_data_integrity.py --scan-staging --enforce

etl-scale-eurostat-indicators-enqueue:
  python3 scripts/ingest_eurostat_indicator_registry.py enqueue --db {{eurostat_indicator_db}} --pipeline-id {{eurostat_indicator_pipeline_id}} --registry {{eurostat_indicator_registry}} --snapshot-date {{snapshot_date}}

etl-scale-eurostat-indicators-work:
  ca_arg=""; if [ -n "{{eurostat_indicator_ca_bundle}}" ]; then ca_arg="--ca-bundle {{eurostat_indicator_ca_bundle}}"; fi; python3 scripts/ingest_eurostat_indicator_registry.py worker --db {{eurostat_indicator_db}} --pipeline-id {{eurostat_indicator_pipeline_id}} --registry {{eurostat_indicator_registry}} --snapshot-date {{snapshot_date}} --worker-id eurostat-indicator-worker --store-root {{eurostat_indicator_raw_root}} --timeout 180 --max-items {{eurostat_indicator_worker_max_items}} --source-record-batch-size {{eurostat_indicator_source_record_batch_size}} $ca_arg

etl-scale-eurostat-indicators-backfill:
  python3 scripts/ingestar_politicos_es.py init-db --db {{eurostat_indicator_db}}
  python3 scripts/ingestar_politicos_es.py backfill-indicators --db {{eurostat_indicator_db}} --source-ids eurostat_sdmx

etl-scale-eurostat-indicators-report:
  python3 scripts/ingest_eurostat_indicator_registry.py report --db {{eurostat_indicator_db}} --pipeline-id {{eurostat_indicator_pipeline_id}} --registry {{eurostat_indicator_registry}} --snapshot-date {{snapshot_date}} --out {{eurostat_indicator_acquisition_report}} --enforce

etl-scale-eurostat-indicators-export:
  # Requires project parquet extra. Output root must not already exist.
  python3 scripts/export_semantic_partitions.py --lane indicator_observations --db {{eurostat_indicator_db}} --output-root {{eurostat_indicator_semantic_root}} --snapshot-date {{snapshot_date}} --row-group-rows 25000 --max-file-rows 100000 --manifest-out {{eurostat_indicator_semantic_manifest}} --min-rows 1000000 --max-peak-rss-mb 1536 --enforce

etl-scale-eurostat-indicators-validate:
  # Requires project parquet extra.
  python3 scripts/validate_semantic_partitions.py --lane indicator_observations --root {{eurostat_indicator_semantic_root}} --manifest {{eurostat_indicator_semantic_manifest}} --report-out {{eurostat_indicator_semantic_validation}} --min-rows 1000000 --max-peak-rss-mb 1536 --enforce

etl-scale-eurostat-indicators-replay:
  # Requires project parquet extra. Replay root must not already exist.
  python3 scripts/export_semantic_partitions.py --lane indicator_observations --db {{eurostat_indicator_db}} --output-root {{eurostat_indicator_semantic_replay_root}} --snapshot-date {{snapshot_date}} --row-group-rows 25000 --max-file-rows 100000 --previous-manifest {{eurostat_indicator_semantic_manifest}} --previous-root {{eurostat_indicator_semantic_root}} --manifest-out {{eurostat_indicator_incremental_manifest}} --min-rows 1000000 --max-peak-rss-mb 1536 --enforce

etl-scale-eurostat-indicators-replay-validate:
  # Requires project parquet extra.
  python3 scripts/validate_semantic_partitions.py --lane indicator_observations --root {{eurostat_indicator_semantic_replay_root}} --manifest {{eurostat_indicator_incremental_manifest}} --report-out {{eurostat_indicator_incremental_validation}} --min-rows 1000000 --max-peak-rss-mb 1536 --enforce

etl-scale-inventory-documents:
  python3 scripts/inventory_document_corpus.py --root etl/data/raw --workers {{scale_document_workers}}

etl-scale-audit-document-provenance:
  python3 scripts/audit_document_provenance.py --enforce-integrity

etl-scale-reconcile-documents:
  just etl-scale-inventory-documents
  just etl-scale-audit-document-provenance

etl-scale-benchmark-ocr-routing:
  python3 scripts/benchmark_pdf_ocr_routing.py --root etl/data/raw --manifest etl/data/manifests/real-document-format-inventory.jsonl --workers 4 --max-pages 20

etl-scale-audit-member-votes:
  python3 scripts/audit_large_vote_snapshot.py --snapshot {{scale_member_vote_snapshot}} --shard-manifest {{scale_member_vote_shard_manifest_out}} --out {{scale_member_vote_audit_out}}

etl-scale-audit-vote-source-urls:
  python3 scripts/audit_vote_source_urls.py --report-out docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/member-vote-source-url-lineage-offline-latest.json --enforce-integrity

etl-scale-audit-vote-db:
  python3 scripts/audit_vote_database.py --db {{db_path}} --out {{scale_vote_db_audit_out}}

etl-scale-export-vote-db-shards:
  python3 scripts/export_vote_database_shards.py --db {{db_path}} --snapshot-date {{snapshot_date}} --shard-root {{scale_vote_db_shard_root}} --manifest-out {{scale_vote_db_shard_manifest_out}} --enforce

etl-scale-validate-vote-db-shards:
  python3 scripts/validate_member_vote_shards.py --manifest {{scale_vote_db_shard_manifest_out}} --shard-root {{scale_vote_db_shard_root}} --report-out {{scale_vote_db_shard_validation_out}} --enforce

etl-scale-export-semantic-member-votes:
  # Requires project parquet extra or requirements.txt environment.
  prev_args=""; if [ -n "{{scale_semantic_previous_manifest}}" ] || [ -n "{{scale_semantic_previous_root}}" ]; then prev_args="--previous-manifest {{scale_semantic_previous_manifest}} --previous-root {{scale_semantic_previous_root}}"; fi; audit_arg=""; if [ -n "{{scale_semantic_vote_audit}}" ]; then audit_arg="--vote-audit {{scale_semantic_vote_audit}}"; fi; python3 scripts/export_semantic_partitions.py --db {{db_path}} --output-root {{scale_semantic_member_vote_root}} --snapshot-date {{snapshot_date}} --row-group-rows {{scale_semantic_row_group_rows}} --max-file-rows {{scale_semantic_max_file_rows}} --manifest-out {{scale_semantic_member_vote_manifest_out}} --min-rows {{scale_semantic_min_rows}} --max-peak-rss-mb 1024 $prev_args $audit_arg --enforce

etl-scale-validate-semantic-member-votes:
  # Requires project parquet extra or requirements.txt environment.
  python3 scripts/validate_semantic_partitions.py --root {{scale_semantic_member_vote_root}} --manifest {{scale_semantic_member_vote_manifest_out}} --report-out {{scale_semantic_member_vote_validation_out}} --min-rows {{scale_semantic_min_rows}} --max-peak-rss-mb 1024 --enforce

etl-scale-export-semantic-accountability-ledger:
  # Requires project parquet extra or requirements.txt environment.
  prev_args=""; if [ -n "{{scale_semantic_ledger_previous_manifest}}" ] || [ -n "{{scale_semantic_ledger_previous_root}}" ]; then prev_args="--previous-manifest {{scale_semantic_ledger_previous_manifest}} --previous-root {{scale_semantic_ledger_previous_root}}"; fi; python3 scripts/export_semantic_partitions.py --lane accountability_ledger --db {{db_path}} --output-root {{scale_semantic_ledger_root}} --snapshot-date {{snapshot_date}} --row-group-rows {{scale_semantic_row_group_rows}} --max-file-rows {{scale_semantic_max_file_rows}} --manifest-out {{scale_semantic_ledger_manifest_out}} --min-rows {{scale_semantic_ledger_min_rows}} --max-peak-rss-mb 1024 $prev_args --enforce

etl-scale-validate-semantic-accountability-ledger:
  # Requires project parquet extra or requirements.txt environment.
  python3 scripts/validate_semantic_partitions.py --lane accountability_ledger --root {{scale_semantic_ledger_root}} --manifest {{scale_semantic_ledger_manifest_out}} --report-out {{scale_semantic_ledger_validation_out}} --min-rows {{scale_semantic_ledger_min_rows}} --max-peak-rss-mb 1024 --enforce

etl-scale-export-semantic-actor-mandates:
  prev_args=""; if [ -n "{{scale_semantic_actor_previous_manifest}}" ] || [ -n "{{scale_semantic_actor_previous_root}}" ]; then prev_args="--previous-manifest {{scale_semantic_actor_previous_manifest}} --previous-root {{scale_semantic_actor_previous_root}}"; fi; docker compose run --rm --build etl "python3 scripts/export_semantic_partitions.py --lane actor_mandates --db {{db_path}} --output-root {{scale_semantic_actor_root}} --snapshot-date {{snapshot_date}} --row-group-rows {{scale_semantic_row_group_rows}} --max-file-rows {{scale_semantic_max_file_rows}} --manifest-out {{scale_semantic_actor_manifest_out}} --min-rows {{scale_semantic_actor_min_rows}} --max-peak-rss-mb 1024 $prev_args --enforce"

etl-scale-validate-semantic-actor-mandates:
  docker compose run --rm --build etl "python3 scripts/validate_semantic_partitions.py --lane actor_mandates --root {{scale_semantic_actor_root}} --manifest {{scale_semantic_actor_manifest_out}} --report-out {{scale_semantic_actor_validation_out}} --min-rows {{scale_semantic_actor_min_rows}} --max-peak-rss-mb 1024 --enforce"

etl-scale-export-semantic-candidate-occurrences:
  prev_args=""; if [ -n "{{scale_semantic_candidate_previous_manifest}}" ] || [ -n "{{scale_semantic_candidate_previous_root}}" ]; then prev_args="--previous-manifest {{scale_semantic_candidate_previous_manifest}} --previous-root {{scale_semantic_candidate_previous_root}}"; fi; docker compose run --rm --build etl "python3 scripts/export_semantic_partitions.py --lane candidate_occurrences --db {{db_path}} --output-root {{scale_semantic_candidate_root}} --snapshot-date {{snapshot_date}} --row-group-rows {{scale_semantic_row_group_rows}} --max-file-rows {{scale_semantic_max_file_rows}} --manifest-out {{scale_semantic_candidate_manifest_out}} --min-rows {{scale_semantic_candidate_min_rows}} --max-peak-rss-mb 1024 $prev_args --enforce"

etl-scale-validate-semantic-candidate-occurrences:
  docker compose run --rm --build etl "python3 scripts/validate_semantic_partitions.py --lane candidate_occurrences --root {{scale_semantic_candidate_root}} --manifest {{scale_semantic_candidate_manifest_out}} --report-out {{scale_semantic_candidate_validation_out}} --min-rows {{scale_semantic_candidate_min_rows}} --max-peak-rss-mb 1024 --enforce"

etl-scale-export-semantic-public-money:
  # Requires project parquet extra or requirements.txt environment.
  prev_args=""; if [ -n "{{scale_semantic_money_previous_manifest}}" ] || [ -n "{{scale_semantic_money_previous_root}}" ]; then prev_args="--previous-manifest {{scale_semantic_money_previous_manifest}} --previous-root {{scale_semantic_money_previous_root}}"; fi; python3 scripts/export_semantic_partitions.py --lane public_money_facts --db {{db_path}} --output-root {{scale_semantic_money_root}} --snapshot-date {{snapshot_date}} --row-group-rows {{scale_semantic_row_group_rows}} --max-file-rows {{scale_semantic_max_file_rows}} --manifest-out {{scale_semantic_money_manifest_out}} --min-rows {{scale_semantic_money_min_rows}} --max-peak-rss-mb 1024 $prev_args --enforce

etl-scale-validate-semantic-public-money:
  # Requires project parquet extra or requirements.txt environment.
  python3 scripts/validate_semantic_partitions.py --lane public_money_facts --root {{scale_semantic_money_root}} --manifest {{scale_semantic_money_manifest_out}} --report-out {{scale_semantic_money_validation_out}} --min-rows {{scale_semantic_money_min_rows}} --max-peak-rss-mb 1024 --enforce

etl-scale-export-semantic-indicators:
  # Requires project parquet extra or requirements.txt environment.
  prev_args=""; if [ -n "{{scale_semantic_indicator_previous_manifest}}" ] || [ -n "{{scale_semantic_indicator_previous_root}}" ]; then prev_args="--previous-manifest {{scale_semantic_indicator_previous_manifest}} --previous-root {{scale_semantic_indicator_previous_root}}"; fi; python3 scripts/export_semantic_partitions.py --lane indicator_observations --db {{db_path}} --output-root {{scale_semantic_indicator_root}} --snapshot-date {{snapshot_date}} --row-group-rows {{scale_semantic_row_group_rows}} --max-file-rows {{scale_semantic_max_file_rows}} --manifest-out {{scale_semantic_indicator_manifest_out}} --min-rows {{scale_semantic_indicator_min_rows}} --max-peak-rss-mb 1024 $prev_args --enforce

etl-scale-validate-semantic-indicators:
  # Requires project parquet extra or requirements.txt environment.
  python3 scripts/validate_semantic_partitions.py --lane indicator_observations --root {{scale_semantic_indicator_root}} --manifest {{scale_semantic_indicator_manifest_out}} --report-out {{scale_semantic_indicator_validation_out}} --min-rows {{scale_semantic_indicator_min_rows}} --max-peak-rss-mb 1024 --enforce

etl-scale-bdns-bulk-enqueue:
  python3 scripts/ingest_bdns_bulk.py --db {{db_path}} --pipeline-id {{bdns_bulk_pipeline_id}} --report-out {{bdns_bulk_enqueue_report}} enqueue --snapshot-date {{snapshot_date}} --page-size {{bdns_bulk_page_size}} --max-pages {{bdns_bulk_max_pages}}

etl-scale-bdns-bulk-enqueue-daily:
  python3 scripts/ingest_bdns_bulk.py --db {{db_path}} --pipeline-id {{bdns_bulk_pipeline_id}} --report-out {{bdns_bulk_enqueue_report}} enqueue-daily --snapshot-date {{snapshot_date}} --date-from {{bdns_bulk_date_from}} --date-to {{bdns_bulk_date_to}} --page-size {{bdns_bulk_page_size}} --target-records {{bdns_bulk_target_records}} --max-partitions {{bdns_bulk_max_partitions}} --max-pages-per-partition {{bdns_bulk_max_pages_per_partition}} --request-interval-seconds {{bdns_bulk_request_interval}}

etl-scale-bdns-bulk-expand-daily:
  python3 scripts/ingest_bdns_bulk.py --db {{db_path}} --pipeline-id {{bdns_bulk_pipeline_id}} --report-out {{bdns_bulk_enqueue_report}} expand-daily --max-pages-per-partition {{bdns_bulk_expand_max_pages_per_partition}} --request-interval-seconds {{bdns_bulk_request_interval}}

etl-scale-bdns-storage-preflight:
  python3 scripts/ingest_bdns_bulk.py --db {{db_path}} --pipeline-id {{bdns_bulk_pipeline_id}} --report-out {{bdns_bulk_run_report}} storage-preflight --raw-root {{bdns_bulk_raw_root}} --claim-size {{bdns_bulk_claim_size}} --min-free-bytes {{bdns_bulk_min_free_bytes}} --sqlite-reserve-multiplier {{bdns_bulk_sqlite_reserve_multiplier}}

etl-scale-bdns-bulk-work:
  python3 scripts/ingest_bdns_bulk.py --db {{db_path}} --pipeline-id {{bdns_bulk_pipeline_id}} --report-out {{bdns_bulk_run_report}} work --raw-root {{bdns_bulk_raw_root}} --workers {{bdns_bulk_workers}} --claim-size {{bdns_bulk_claim_size}} --min-free-bytes {{bdns_bulk_min_free_bytes}} --sqlite-reserve-multiplier {{bdns_bulk_sqlite_reserve_multiplier}} --request-interval-seconds {{bdns_bulk_request_interval}} --failure-window-size {{bdns_bulk_failure_window}}

etl-scale-bdns-bulk-report:
  python3 scripts/ingest_bdns_bulk.py --db {{db_path}} --pipeline-id {{bdns_bulk_pipeline_id}} --report-out {{bdns_bulk_run_report}} report

etl-scale-bdns-bulk-version-lineage:
  python3 scripts/ingest_bdns_bulk.py --db {{db_path}} --pipeline-id {{bdns_bulk_pipeline_id}} --report-out {{bdns_bulk_run_report}} backfill-version-lineage --max-pages {{bdns_bulk_version_backfill_max_pages}}

etl-scale-placsp-archives-enqueue:
  python3 scripts/ingest_placsp_archives.py --db {{placsp_bulk_db}} --pipeline-id {{placsp_bulk_pipeline_id}} --report-out {{placsp_bulk_enqueue_report}} enqueue --snapshot-date {{placsp_bulk_snapshot_date}} {{placsp_bulk_archive_args}}

etl-scale-placsp-history-discover:
  python3 scripts/ingest_placsp_archives.py --report-out {{placsp_history_catalog_report}} discover-archives --as-of-date {{placsp_history_snapshot_date}} --start-year 2012 --enforce

etl-scale-placsp-history-enqueue:
  python3 scripts/ingest_placsp_archives.py --db {{placsp_bulk_db}} --pipeline-id {{placsp_history_pipeline_id}} --report-out {{placsp_history_enqueue_report}} enqueue --snapshot-date {{placsp_history_snapshot_date}} --archive-report {{placsp_history_catalog_report}}

etl-scale-placsp-history-archives-work:
  ca_arg=""; if [ -n "{{placsp_bulk_ca_bundle}}" ]; then ca_arg="--ca-bundle {{placsp_bulk_ca_bundle}}"; fi; python3 scripts/ingest_placsp_archives.py --db {{placsp_bulk_db}} --pipeline-id {{placsp_history_pipeline_id}} --report-out {{placsp_history_storage_report}} work-archives --raw-root {{placsp_bulk_raw_root}} --max-items {{placsp_history_archive_max_items}} --min-free-bytes {{placsp_history_min_free_bytes}} --lease-seconds 1800 --timeout 180 $ca_arg

etl-scale-placsp-history-members-work:
  python3 scripts/ingest_placsp_archives.py --db {{placsp_bulk_db}} --pipeline-id {{placsp_history_pipeline_id}} --report-out {{placsp_history_member_report}} work-members --claim-size 1 --max-items {{placsp_history_member_max_items}} --min-free-bytes {{placsp_history_min_free_bytes}} --lease-seconds 300

etl-scale-placsp-archives-work:
  ca_arg=""; if [ -n "{{placsp_bulk_ca_bundle}}" ]; then ca_arg="--ca-bundle {{placsp_bulk_ca_bundle}}"; fi; python3 scripts/ingest_placsp_archives.py --db {{placsp_bulk_db}} --pipeline-id {{placsp_bulk_pipeline_id}} --report-out {{placsp_bulk_archive_report}} work-archives --raw-root {{placsp_bulk_raw_root}} --min-free-bytes {{placsp_bulk_min_free_bytes}} --lease-seconds 1800 --timeout 180 $ca_arg

etl-scale-placsp-members-work:
  python3 scripts/ingest_placsp_archives.py --db {{placsp_bulk_db}} --pipeline-id {{placsp_bulk_pipeline_id}} --report-out {{placsp_bulk_run_report}} work-members --claim-size 4 --min-free-bytes {{placsp_bulk_min_free_bytes}} --lease-seconds 300

etl-scale-placsp-requeue-document-cap:
  python3 scripts/ingest_placsp_archives.py --db {{placsp_bulk_db}} --pipeline-id {{placsp_bulk_pipeline_id}} requeue-dead-members --error-contains 'documents exceed cap'

etl-scale-placsp-report:
  python3 scripts/ingest_placsp_archives.py --db {{placsp_bulk_db}} --pipeline-id {{placsp_bulk_pipeline_id}} --report-out {{placsp_bulk_run_report}} report

etl-scale-placsp-corpus-report:
  python3 scripts/ingest_placsp_archives.py --db {{placsp_bulk_db}} --pipeline-id {{placsp_bulk_latest_pipeline_id}} --report-out {{placsp_bulk_corpus_report}} report

etl-scale-placsp-export:
  python3 scripts/export_semantic_partitions.py --lane public_money_facts --db {{placsp_bulk_db}} --output-root {{placsp_bulk_semantic_root}} --snapshot-date {{placsp_bulk_semantic_snapshot_date}} --row-group-rows 25000 --max-file-rows 50000 --manifest-out {{placsp_bulk_semantic_manifest}} --min-rows 100000 --max-peak-rss-mb 1536 --enforce

etl-scale-placsp-validate:
  python3 scripts/validate_semantic_partitions.py --lane public_money_facts --root {{placsp_bulk_semantic_root}} --manifest {{placsp_bulk_semantic_manifest}} --report-out {{placsp_bulk_semantic_validation}} --min-rows 100000 --max-peak-rss-mb 1536 --enforce

etl-scale-placsp-replay:
  python3 scripts/export_semantic_partitions.py --lane public_money_facts --db {{placsp_bulk_db}} --output-root {{placsp_bulk_semantic_replay_root}} --snapshot-date {{placsp_bulk_replay_snapshot_date}} --row-group-rows 25000 --max-file-rows 50000 --previous-manifest {{placsp_bulk_semantic_manifest}} --previous-root {{placsp_bulk_semantic_root}} --manifest-out {{placsp_bulk_incremental_manifest}} --min-rows 100000 --max-peak-rss-mb 1536 --enforce

etl-scale-placsp-replay-validate:
  python3 scripts/validate_semantic_partitions.py --lane public_money_facts --root {{placsp_bulk_semantic_replay_root}} --manifest {{placsp_bulk_incremental_manifest}} --report-out {{placsp_bulk_incremental_validation}} --min-rows 100000 --max-peak-rss-mb 1536 --enforce

etl-scale-placsp-documents-enqueue:
  python3 scripts/enqueue_pipeline_work.py --db {{placsp_bulk_db}} --kind placsp-document-fetch --pipeline-id {{placsp_document_pipeline_id}} --source-ids placsp_sindicacion --only-missing --batch-size 5000 --max-attempts 5 --report-out {{placsp_document_enqueue_report}}

etl-scale-placsp-documents-work:
  ca_arg=""; if [ -n "{{placsp_bulk_ca_bundle}}" ]; then ca_arg="--ca-bundle {{placsp_bulk_ca_bundle}}"; fi; python3 scripts/run_document_fetch_queue.py --db {{placsp_bulk_db}} --pipeline-id {{placsp_document_pipeline_id}} --worker-id placsp-document-worker --raw-root {{placsp_document_raw_root}} --workers 2 --per-host-workers 1 --claim-size 4 --max-items {{placsp_document_worker_max_items}} --lease-seconds 900 --timeout 60 --max-bytes 262144000 --download-attempts 1 --retry-delay-seconds 300 --report-out {{placsp_document_worker_report}} $ca_arg

etl-scale-placsp-integrity-review:
  python3 scripts/detect_procurement_integrity_signals.py --db {{placsp_bulk_db}} --source-ids placsp_sindicacion --threshold-eur {{integrity_signal_threshold_eur}} --min-records {{integrity_signal_min_records}} --max-signals {{integrity_signal_max_signals}} --supersede-missing --supersede-prior-versions --report-out {{placsp_integrity_report}}

etl-scale-shard-member-votes:
  python3 scripts/shard_large_vote_snapshot.py --snapshot {{scale_member_vote_snapshot}} --shard-root {{scale_member_vote_shard_root}} --manifest-out {{scale_member_vote_shard_manifest_out}} --source-provenance-overrides {{scale_member_vote_source_provenance_overrides}} --enforce

etl-scale-validate-member-vote-shards:
  python3 scripts/validate_member_vote_shards.py --manifest {{scale_member_vote_shard_manifest_out}} --shard-root {{scale_member_vote_shard_root}} --report-out {{scale_member_vote_shard_validation_out}} --enforce

etl-scale-queue-status:
  python3 scripts/report_pipeline_work_queue.py --db {{db_path}} --pipeline-id '{{scale_queue_pipeline_id}}' --out {{scale_queue_health_out}}

etl-object-store-replicate-dry-run:
  python3 scripts/replicate_content_objects.py --db {{db_path}} --backend {{object_store_backend}} --filesystem-root {{object_store_filesystem_root}} --limit {{object_store_replication_limit}} --workers {{object_store_replication_workers}} --manifest-out {{object_store_manifest_out}} --report-out {{object_store_replication_report_out}} --dry-run

etl-object-store-replicate:
  python3 scripts/replicate_content_objects.py --db {{db_path}} --backend {{object_store_backend}} --filesystem-root {{object_store_filesystem_root}} --limit {{object_store_replication_limit}} --workers {{object_store_replication_workers}} --manifest-out {{object_store_manifest_out}} --report-out {{object_store_replication_report_out}}

etl-object-store-restore-drill:
  all_arg=""; \
  if [ "{{object_store_restore_all}}" = "1" ]; then all_arg="--all"; fi; \
  python3 scripts/verify_object_store_restore.py --manifest {{object_store_manifest_out}} --backend {{object_store_backend}} --filesystem-root {{object_store_filesystem_root}} --sample-size {{object_store_restore_sample_size}} --workers {{object_store_restore_workers}} --min-free-bytes {{object_store_restore_min_free_bytes}} --report-out {{object_store_restore_report_out}} ${all_arg}

etl-integrity-procurement-detect-dry-run:
  python3 scripts/detect_procurement_integrity_signals.py --db {{db_path}} --threshold-eur {{integrity_signal_threshold_eur}} --min-records {{integrity_signal_min_records}} --max-signals {{integrity_signal_max_signals}} --report-out {{integrity_signal_internal_report_out}} --dry-run

# Persists internal review signals only. It cannot publish or label corruption.
etl-integrity-procurement-detect:
  python3 scripts/detect_procurement_integrity_signals.py --db {{db_path}} --threshold-eur {{integrity_signal_threshold_eur}} --min-records {{integrity_signal_min_records}} --max-signals {{integrity_signal_max_signals}} --report-out {{integrity_signal_internal_report_out}}

etl-export-integrity-signals:
  python3 scripts/export_public_integrity_signals.py --db {{db_path}} --snapshot-date {{snapshot_date}} --out {{integrity_signal_public_out}}

etl-scale-gate:
  just etl-scale-readiness
  just privacy-check-public-artifacts
  just etl-tracker-gate

parl-backfill-initdoc-excerpts:
  docker compose run --rm --build etl "python3 scripts/backfill_initiative_doc_excerpts.py --db {{db_path}} --source-id parl_initiative_docs --initiative-source-id {{initdoc_excerpt_scope}}"

parl-backfill-initdoc-excerpts-all:
  docker compose run --rm --build etl "python3 scripts/backfill_initiative_doc_excerpts.py --db {{db_path}} --source-id parl_initiative_docs"

parl-backfill-initdoc-fetch-status:
  scope_arg=""; \
  if [ -n "{{initdoc_fetch_scope}}" ]; then \
    scope_arg=" --initiative-source-id {{initdoc_fetch_scope}}"; \
  fi; \
  docker compose run --rm --build etl "python3 scripts/backfill_initiative_doc_fetch_status.py --db {{db_path}} --source-id parl_initiative_docs${scope_arg}"

parl-backfill-initdoc-records-from-fetches:
  scope_arg=""; \
  if [ -n "{{initdoc_fetch_scope}}" ]; then \
    scope_arg=" --initiative-source-id {{initdoc_fetch_scope}}"; \
  fi; \
  python3 scripts/backfill_initiative_doc_records_from_fetches.py --db {{db_path}} --source-id parl_initiative_docs --snapshot-date {{snapshot_date}}${scope_arg}

parl-report-initdoc-status:
  docker compose run --rm --build etl "python3 scripts/report_initiative_doc_status.py --db {{db_path}} --initiative-source-ids congreso_iniciativas,senado_iniciativas --doc-source-id parl_initiative_docs --missing-sample-limit {{initdoc_status_missing_sample_limit}} --out {{initdoc_status_out}}"

parl-export-missing-initdoc-urls-actionable:
  python3 scripts/export_missing_initiative_doc_urls.py --db {{db_path}} --initiative-source-ids '{{initdoc_missing_export_source_ids}}' --only-actionable-missing --only-linked-to-votes --format csv --out {{initdoc_missing_export_out}}

parl-check-missing-initdoc-urls-actionable-empty:
  python3 scripts/export_missing_initiative_doc_urls.py --db {{db_path}} --initiative-source-ids '{{initdoc_missing_export_source_ids}}' --only-actionable-missing --only-linked-to-votes --strict-empty --format csv --out {{initdoc_missing_export_out}}

parl-export-missing-initdoc-urls-actionable-zero-doc:
  python3 scripts/export_missing_initiative_doc_urls.py --db {{db_path}} --initiative-source-ids '{{initdoc_missing_export_source_ids}}' --only-actionable-missing --only-linked-to-votes --only-initiatives-without-any-doc --max-urls-per-initiative {{initdoc_missing_export_max_per_initiative}} --format csv --out {{initdoc_missing_export_out}}

parl-check-missing-initdoc-urls-actionable-zero-doc-empty:
  python3 scripts/export_missing_initiative_doc_urls.py --db {{db_path}} --initiative-source-ids '{{initdoc_missing_export_source_ids}}' --only-actionable-missing --only-linked-to-votes --only-initiatives-without-any-doc --max-urls-per-initiative {{initdoc_missing_export_max_per_initiative}} --strict-empty --format csv --out {{initdoc_missing_export_out}}

parl-report-senado-waf-block-profile:
  python3 scripts/report_senado_waf_block_profile.py --db {{db_path}} --initiative-source-id senado_iniciativas --only-linked-to-votes --sample-limit {{senado_waf_profile_sample_limit}} --out {{senado_waf_profile_out}}

parl-check-senado-waf-block-profile:
  python3 scripts/report_senado_waf_block_profile.py --db {{db_path}} --initiative-source-id senado_iniciativas --only-linked-to-votes --sample-limit {{senado_waf_profile_sample_limit}} --strict --out {{senado_waf_profile_out}}

parl-export-senado-waf-cohort-packets:
  python3 scripts/export_senado_waf_cohort_packets.py --db {{db_path}} --initiative-source-id senado_iniciativas --doc-source-id parl_initiative_docs --only-linked-to-votes --cohort-top-n {{senado_waf_packets_cohort_top_n}} --max-urls-per-cohort {{senado_waf_packets_max_urls_per_cohort}} --max-total-rows {{senado_waf_packets_max_total_rows}} --include-zero-doc-priority --max-zero-doc-rows {{senado_waf_packets_max_zero_doc_rows}} --strict-min-packet-rows {{senado_waf_packets_strict_min_packet_rows}} --strict-min-cohorts {{senado_waf_packets_strict_min_cohorts}} --out {{senado_waf_packets_out}} --csv-out {{senado_waf_packets_csv_out}}

parl-check-senado-waf-cohort-packets:
  python3 scripts/export_senado_waf_cohort_packets.py --db {{db_path}} --initiative-source-id senado_iniciativas --doc-source-id parl_initiative_docs --only-linked-to-votes --cohort-top-n {{senado_waf_packets_cohort_top_n}} --max-urls-per-cohort {{senado_waf_packets_max_urls_per_cohort}} --max-total-rows {{senado_waf_packets_max_total_rows}} --include-zero-doc-priority --max-zero-doc-rows {{senado_waf_packets_max_zero_doc_rows}} --strict-min-packet-rows {{senado_waf_packets_strict_min_packet_rows}} --strict-min-cohorts {{senado_waf_packets_strict_min_cohorts}} --strict --out {{senado_waf_packets_out}} --csv-out {{senado_waf_packets_csv_out}}

parl-export-senado-retry-packet-only-dedup:
  refs_arg=""; \
  refs_only_arg=""; \
  if [ -n "{{senado_retry_packet_refs_file}}" ]; then \
    refs_arg=" --packet-csv-refs-file {{senado_retry_packet_refs_file}}"; \
  fi; \
  if [ "{{senado_retry_packet_refs_only}}" = "1" ]; then \
    refs_only_arg=" --packet-csv-refs-file-only"; \
  fi; \
  python3 scripts/export_senado_retry_packet_only_dedup.py --pool-csv {{senado_retry_packet_pool_csv}} --packet-csv-glob '{{senado_retry_packet_glob}}' --max-rows {{senado_retry_packet_max_rows}} --strict-min-fresh-rows {{senado_retry_packet_strict_min_fresh_rows}} --out {{senado_retry_packet_out}} --csv-out {{senado_retry_packet_csv_out}} --used-urls-out {{senado_retry_packet_used_urls_out}} --used-packet-refs-out {{senado_retry_packet_used_refs_out}}${refs_arg}${refs_only_arg}

parl-check-senado-retry-packet-only-dedup:
  refs_arg=""; \
  refs_only_arg=""; \
  if [ -n "{{senado_retry_packet_refs_file}}" ]; then \
    refs_arg=" --packet-csv-refs-file {{senado_retry_packet_refs_file}}"; \
  fi; \
  if [ "{{senado_retry_packet_refs_only}}" = "1" ]; then \
    refs_only_arg=" --packet-csv-refs-file-only"; \
  fi; \
  python3 scripts/export_senado_retry_packet_only_dedup.py --pool-csv {{senado_retry_packet_pool_csv}} --packet-csv-glob '{{senado_retry_packet_glob}}' --max-rows {{senado_retry_packet_max_rows}} --strict-min-fresh-rows {{senado_retry_packet_strict_min_fresh_rows}} --strict --out {{senado_retry_packet_out}} --csv-out {{senado_retry_packet_csv_out}} --used-urls-out {{senado_retry_packet_used_urls_out}} --used-packet-refs-out {{senado_retry_packet_used_refs_out}}${refs_arg}${refs_only_arg}

parl-report-senado-archive-gap-urls:
  python3 scripts/export_senado_archive_gap_urls.py --retry-json-glob '{{senado_archive_gap_retry_json_glob}}' --strict-min-rows {{senado_archive_gap_strict_min_rows}} --out {{senado_archive_gap_out}} --csv-out {{senado_archive_gap_csv_out}}

parl-check-senado-archive-gap-urls:
  python3 scripts/export_senado_archive_gap_urls.py --retry-json-glob '{{senado_archive_gap_retry_json_glob}}' --strict-min-rows {{senado_archive_gap_strict_min_rows}} --strict --out {{senado_archive_gap_out}} --csv-out {{senado_archive_gap_csv_out}}

parl-report-senado-cookie-lever-status:
  python3 scripts/report_senado_cookie_lever_status.py --cookie-file {{senado_cookie_lever_file}} --domain-contains senado.es --max-age-hours {{senado_cookie_lever_max_age_hours}} --min-domain-cookies {{senado_cookie_lever_min_domain}} --min-unexpired-persistent-cookies {{senado_cookie_lever_min_persistent}} --out {{senado_cookie_lever_out}}

parl-check-senado-cookie-lever-status:
  python3 scripts/report_senado_cookie_lever_status.py --cookie-file {{senado_cookie_lever_file}} --domain-contains senado.es --max-age-hours {{senado_cookie_lever_max_age_hours}} --min-domain-cookies {{senado_cookie_lever_min_domain}} --min-unexpired-persistent-cookies {{senado_cookie_lever_min_persistent}} --strict --out {{senado_cookie_lever_out}}

parl-report-senado-manual-capture-validity:
  python3 scripts/report_senado_manual_capture_validity.py --captures-glob '{{senado_capture_validity_glob}}' --cookie-domain-contains senado.es --min-captures {{senado_capture_validity_min}} --out {{senado_capture_validity_out}}

parl-check-senado-manual-capture-validity:
  python3 scripts/report_senado_manual_capture_validity.py --captures-glob '{{senado_capture_validity_glob}}' --cookie-domain-contains senado.es --min-captures {{senado_capture_validity_min}} --strict --out {{senado_capture_validity_out}}

parl-export-senado-manual-capture-targets:
  python3 scripts/export_senado_manual_capture_targets.py --packet-json {{senado_capture_targets_packet_json}} --packet-csv {{senado_capture_targets_packet_csv}} --include-seed-url --seed-url {{senado_capture_targets_seed_url}} --max-targets {{senado_capture_targets_max_targets}} --wait-seconds {{senado_capture_targets_wait_seconds}} --label-prefix {{senado_capture_targets_label_prefix}} --strict-min-targets {{senado_capture_targets_strict_min_targets}} --out {{senado_capture_targets_out}} --csv-out {{senado_capture_targets_csv_out}}

parl-check-senado-manual-capture-targets:
  python3 scripts/export_senado_manual_capture_targets.py --packet-json {{senado_capture_targets_packet_json}} --packet-csv {{senado_capture_targets_packet_csv}} --include-seed-url --seed-url {{senado_capture_targets_seed_url}} --max-targets {{senado_capture_targets_max_targets}} --wait-seconds {{senado_capture_targets_wait_seconds}} --label-prefix {{senado_capture_targets_label_prefix}} --strict-min-targets {{senado_capture_targets_strict_min_targets}} --strict --out {{senado_capture_targets_out}} --csv-out {{senado_capture_targets_csv_out}}

parl-report-senado-manual-capture-target-progress:
  python3 scripts/report_senado_manual_capture_target_progress.py --targets-csv {{senado_capture_target_progress_targets_csv}} --captures-glob '{{senado_capture_target_progress_captures_glob}}' --cookie-domain-contains senado.es --strict-min-covered-targets {{senado_capture_target_progress_min_covered}} --strict-min-usable-targets {{senado_capture_target_progress_min_usable}} --out {{senado_capture_target_progress_out}} --csv-out {{senado_capture_target_progress_csv_out}}

parl-check-senado-manual-capture-target-progress:
  python3 scripts/report_senado_manual_capture_target_progress.py --targets-csv {{senado_capture_target_progress_targets_csv}} --captures-glob '{{senado_capture_target_progress_captures_glob}}' --cookie-domain-contains senado.es --strict-min-covered-targets {{senado_capture_target_progress_min_covered}} --strict-min-usable-targets {{senado_capture_target_progress_min_usable}} --strict --out {{senado_capture_target_progress_out}} --csv-out {{senado_capture_target_progress_csv_out}}

parl-run-senado-manual-capture-retry-cycle:
  python3 scripts/run_senado_manual_capture_retry_cycle.py --db {{db_path}} --targets-csv {{senado_capture_target_progress_targets_csv}} --captures-glob '{{senado_capture_target_progress_captures_glob}}' --cookie-domain-contains senado.es --strict-min-covered-targets {{senado_capture_target_progress_min_covered}} --strict-min-usable-targets {{senado_capture_target_progress_min_usable}} --initiative-source-ids senado_iniciativas --limit-initiatives {{senado_capture_retry_cycle_limit_initiatives}} --max-docs-per-initiative {{senado_capture_retry_cycle_max_docs_per_initiative}} --timeout {{senado_capture_retry_cycle_timeout}} --snapshot-date {{snapshot_date}} --progress-out {{senado_capture_retry_cycle_progress_out}} --progress-csv-out {{senado_capture_retry_cycle_progress_csv_out}} --out {{senado_capture_retry_cycle_out}}

parl-check-senado-manual-capture-retry-cycle:
  python3 scripts/run_senado_manual_capture_retry_cycle.py --db {{db_path}} --targets-csv {{senado_capture_target_progress_targets_csv}} --captures-glob '{{senado_capture_target_progress_captures_glob}}' --cookie-domain-contains senado.es --strict-min-covered-targets {{senado_capture_target_progress_min_covered}} --strict-min-usable-targets {{senado_capture_target_progress_min_usable}} --initiative-source-ids senado_iniciativas --limit-initiatives {{senado_capture_retry_cycle_limit_initiatives}} --max-docs-per-initiative {{senado_capture_retry_cycle_max_docs_per_initiative}} --timeout {{senado_capture_retry_cycle_timeout}} --snapshot-date {{snapshot_date}} --strict-ready --strict-backfill --progress-out {{senado_capture_retry_cycle_progress_out}} --progress-csv-out {{senado_capture_retry_cycle_progress_csv_out}} --out {{senado_capture_retry_cycle_out}}

parl-export-senado-manual-capture-pending-targets:
  python3 scripts/export_senado_manual_capture_pending_targets.py --progress-json {{senado_capture_pending_progress_json}} --progress-csv {{senado_capture_pending_progress_csv}} --max-targets {{senado_capture_pending_max_targets}} --out {{senado_capture_pending_out}} --csv-out {{senado_capture_pending_csv_out}} --commands-out {{senado_capture_pending_commands_out}}

parl-check-senado-manual-capture-pending-targets-empty:
  python3 scripts/export_senado_manual_capture_pending_targets.py --progress-json {{senado_capture_pending_progress_json}} --progress-csv {{senado_capture_pending_progress_csv}} --max-targets 0 --out {{senado_capture_pending_out}} --csv-out {{senado_capture_pending_csv_out}} --commands-out {{senado_capture_pending_commands_out}} --strict

parl-run-senado-manual-capture-iteration-cycle:
  python3 scripts/run_senado_manual_capture_iteration_cycle.py --db {{db_path}} --targets-csv {{senado_capture_target_progress_targets_csv}} --captures-glob '{{senado_capture_target_progress_captures_glob}}' --cookie-domain-contains senado.es --strict-min-covered-targets {{senado_capture_target_progress_min_covered}} --strict-min-usable-targets {{senado_capture_target_progress_min_usable}} --initiative-source-ids senado_iniciativas --limit-initiatives {{senado_capture_retry_cycle_limit_initiatives}} --max-docs-per-initiative {{senado_capture_retry_cycle_max_docs_per_initiative}} --timeout {{senado_capture_retry_cycle_timeout}} --snapshot-date {{snapshot_date}} --pending-max-targets {{senado_capture_iteration_pending_max_targets}} --pending-wait-seconds {{senado_capture_iteration_pending_wait_seconds}} --strict-min-pending-reduction {{senado_capture_iteration_strict_min_pending_reduction}} --retry-out {{senado_capture_iteration_retry_out}} --progress-out {{senado_capture_iteration_progress_out}} --progress-csv-out {{senado_capture_iteration_progress_csv_out}} --pending-out {{senado_capture_iteration_pending_out}} --pending-csv-out {{senado_capture_iteration_pending_csv_out}} --pending-commands-out {{senado_capture_iteration_pending_commands_out}} --out {{senado_capture_iteration_out}}

parl-check-senado-manual-capture-iteration-cycle:
  python3 scripts/run_senado_manual_capture_iteration_cycle.py --db {{db_path}} --targets-csv {{senado_capture_target_progress_targets_csv}} --captures-glob '{{senado_capture_target_progress_captures_glob}}' --cookie-domain-contains senado.es --strict-min-covered-targets {{senado_capture_target_progress_min_covered}} --strict-min-usable-targets {{senado_capture_target_progress_min_usable}} --initiative-source-ids senado_iniciativas --limit-initiatives {{senado_capture_retry_cycle_limit_initiatives}} --max-docs-per-initiative {{senado_capture_retry_cycle_max_docs_per_initiative}} --timeout {{senado_capture_retry_cycle_timeout}} --snapshot-date {{snapshot_date}} --pending-max-targets {{senado_capture_iteration_pending_max_targets}} --pending-wait-seconds {{senado_capture_iteration_pending_wait_seconds}} --strict-min-pending-reduction {{senado_capture_iteration_strict_min_pending_reduction}} --retry-out {{senado_capture_iteration_retry_out}} --progress-out {{senado_capture_iteration_progress_out}} --progress-csv-out {{senado_capture_iteration_progress_csv_out}} --pending-out {{senado_capture_iteration_pending_out}} --pending-csv-out {{senado_capture_iteration_pending_csv_out}} --pending-commands-out {{senado_capture_iteration_pending_commands_out}} --out {{senado_capture_iteration_out}} --strict

parl-report-initdoc-actionable-tail-contract:
  python3 scripts/report_initdoc_actionable_tail_contract.py --db {{db_path}} --initiative-source-ids '{{initdoc_actionable_contract_source_ids}}' --out {{initdoc_actionable_contract_out}}

parl-check-initdoc-actionable-tail-contract:
  python3 scripts/report_initdoc_actionable_tail_contract.py --db {{db_path}} --initiative-source-ids '{{initdoc_actionable_contract_source_ids}}' --strict --out {{initdoc_actionable_contract_out}}

parl-report-initdoc-actionable-tail-digest:
  python3 scripts/report_initdoc_actionable_tail_contract.py --db {{db_path}} --initiative-source-ids '{{initdoc_actionable_contract_source_ids}}' --out {{initdoc_actionable_contract_out}}
  python3 scripts/report_initdoc_actionable_tail_digest.py --contract-json {{initdoc_actionable_contract_out}} --max-actionable-missing {{initdoc_actionable_digest_max_missing}} --max-actionable-missing-pct {{initdoc_actionable_digest_max_missing_pct}} --out {{initdoc_actionable_digest_out}}

parl-check-initdoc-actionable-tail-digest:
  python3 scripts/report_initdoc_actionable_tail_contract.py --db {{db_path}} --initiative-source-ids '{{initdoc_actionable_contract_source_ids}}' --out {{initdoc_actionable_contract_out}}
  python3 scripts/report_initdoc_actionable_tail_digest.py --contract-json {{initdoc_actionable_contract_out}} --max-actionable-missing {{initdoc_actionable_digest_max_missing}} --max-actionable-missing-pct {{initdoc_actionable_digest_max_missing_pct}} --strict --out {{initdoc_actionable_digest_out}}

parl-report-initdoc-actionable-tail-digest-heartbeat:
  python3 scripts/report_initdoc_actionable_tail_contract.py --db {{db_path}} --initiative-source-ids '{{initdoc_actionable_contract_source_ids}}' --out {{initdoc_actionable_contract_out}}
  python3 scripts/report_initdoc_actionable_tail_digest.py --contract-json {{initdoc_actionable_contract_out}} --max-actionable-missing {{initdoc_actionable_digest_max_missing}} --max-actionable-missing-pct {{initdoc_actionable_digest_max_missing_pct}} --out {{initdoc_actionable_digest_out}}
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat.py --digest-json {{initdoc_actionable_digest_out}} --heartbeat-jsonl {{initdoc_actionable_heartbeat_path}} --out {{initdoc_actionable_heartbeat_out}}

parl-check-initdoc-actionable-tail-digest-heartbeat:
  python3 scripts/report_initdoc_actionable_tail_contract.py --db {{db_path}} --initiative-source-ids '{{initdoc_actionable_contract_source_ids}}' --out {{initdoc_actionable_contract_out}}
  python3 scripts/report_initdoc_actionable_tail_digest.py --contract-json {{initdoc_actionable_contract_out}} --max-actionable-missing {{initdoc_actionable_digest_max_missing}} --max-actionable-missing-pct {{initdoc_actionable_digest_max_missing_pct}} --out {{initdoc_actionable_digest_out}}
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat.py --digest-json {{initdoc_actionable_digest_out}} --heartbeat-jsonl {{initdoc_actionable_heartbeat_path}} --strict --out {{initdoc_actionable_heartbeat_out}}

parl-report-initdoc-actionable-tail-digest-heartbeat-window:
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_window.py --heartbeat-jsonl {{initdoc_actionable_heartbeat_path}} --last {{initdoc_actionable_heartbeat_window_last}} --max-failed {{initdoc_actionable_heartbeat_window_max_failed}} --max-failed-rate-pct {{initdoc_actionable_heartbeat_window_max_failed_rate_pct}} --max-degraded {{initdoc_actionable_heartbeat_window_max_degraded}} --max-degraded-rate-pct {{initdoc_actionable_heartbeat_window_max_degraded_rate_pct}} --out {{initdoc_actionable_heartbeat_window_out}}

parl-check-initdoc-actionable-tail-digest-heartbeat-window:
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_window.py --heartbeat-jsonl {{initdoc_actionable_heartbeat_path}} --last {{initdoc_actionable_heartbeat_window_last}} --max-failed {{initdoc_actionable_heartbeat_window_max_failed}} --max-failed-rate-pct {{initdoc_actionable_heartbeat_window_max_failed_rate_pct}} --max-degraded {{initdoc_actionable_heartbeat_window_max_degraded}} --max-degraded-rate-pct {{initdoc_actionable_heartbeat_window_max_degraded_rate_pct}} --strict --out {{initdoc_actionable_heartbeat_window_out}}

parl-report-initdoc-actionable-tail-digest-heartbeat-compact:
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction.py --heartbeat-jsonl {{initdoc_actionable_heartbeat_path}} --compacted-jsonl {{initdoc_actionable_heartbeat_compact_path}} --keep-recent {{initdoc_actionable_heartbeat_compact_recent}} --keep-mid-span {{initdoc_actionable_heartbeat_compact_mid_span}} --keep-mid-every {{initdoc_actionable_heartbeat_compact_mid_every}} --keep-old-every {{initdoc_actionable_heartbeat_compact_old_every}} --min-raw-for-dropped-check {{initdoc_actionable_heartbeat_compact_min_raw}} --out {{initdoc_actionable_heartbeat_compact_out}}

parl-check-initdoc-actionable-tail-digest-heartbeat-compact:
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction.py --heartbeat-jsonl {{initdoc_actionable_heartbeat_path}} --compacted-jsonl {{initdoc_actionable_heartbeat_compact_path}} --keep-recent {{initdoc_actionable_heartbeat_compact_recent}} --keep-mid-span {{initdoc_actionable_heartbeat_compact_mid_span}} --keep-mid-every {{initdoc_actionable_heartbeat_compact_mid_every}} --keep-old-every {{initdoc_actionable_heartbeat_compact_old_every}} --min-raw-for-dropped-check {{initdoc_actionable_heartbeat_compact_min_raw}} --strict --out {{initdoc_actionable_heartbeat_compact_out}}

parl-report-initdoc-actionable-tail-digest-heartbeat-compact-window:
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window.py --heartbeat-jsonl {{initdoc_actionable_heartbeat_path}} --compacted-jsonl {{initdoc_actionable_heartbeat_compact_path}} --last {{initdoc_actionable_heartbeat_compact_window_last}} --out {{initdoc_actionable_heartbeat_compact_window_out}}

parl-check-initdoc-actionable-tail-digest-heartbeat-compact-window:
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window.py --heartbeat-jsonl {{initdoc_actionable_heartbeat_path}} --compacted-jsonl {{initdoc_actionable_heartbeat_compact_path}} --last {{initdoc_actionable_heartbeat_compact_window_last}} --strict --out {{initdoc_actionable_heartbeat_compact_window_out}}

parl-report-initdoc-actionable-tail-digest-heartbeat-compact-window-digest:
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window.py --heartbeat-jsonl {{initdoc_actionable_heartbeat_path}} --compacted-jsonl {{initdoc_actionable_heartbeat_compact_path}} --last {{initdoc_actionable_heartbeat_compact_window_last}} --out {{initdoc_actionable_heartbeat_compact_window_out}}
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest.py --compaction-window-json {{initdoc_actionable_heartbeat_compact_window_out}} --out {{initdoc_actionable_heartbeat_compact_window_digest_out}}

parl-check-initdoc-actionable-tail-digest-heartbeat-compact-window-digest:
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window.py --heartbeat-jsonl {{initdoc_actionable_heartbeat_path}} --compacted-jsonl {{initdoc_actionable_heartbeat_compact_path}} --last {{initdoc_actionable_heartbeat_compact_window_last}} --out {{initdoc_actionable_heartbeat_compact_window_out}}
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest.py --compaction-window-json {{initdoc_actionable_heartbeat_compact_window_out}} --strict --out {{initdoc_actionable_heartbeat_compact_window_digest_out}}

parl-report-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat:
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window.py --heartbeat-jsonl {{initdoc_actionable_heartbeat_path}} --compacted-jsonl {{initdoc_actionable_heartbeat_compact_path}} --last {{initdoc_actionable_heartbeat_compact_window_last}} --out {{initdoc_actionable_heartbeat_compact_window_out}}
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest.py --compaction-window-json {{initdoc_actionable_heartbeat_compact_window_out}} --out {{initdoc_actionable_heartbeat_compact_window_digest_out}}
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat.py --digest-json {{initdoc_actionable_heartbeat_compact_window_digest_out}} --heartbeat-jsonl {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_path}} --out {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_out}}

parl-check-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat:
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window.py --heartbeat-jsonl {{initdoc_actionable_heartbeat_path}} --compacted-jsonl {{initdoc_actionable_heartbeat_compact_path}} --last {{initdoc_actionable_heartbeat_compact_window_last}} --out {{initdoc_actionable_heartbeat_compact_window_out}}
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest.py --compaction-window-json {{initdoc_actionable_heartbeat_compact_window_out}} --out {{initdoc_actionable_heartbeat_compact_window_digest_out}}
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat.py --digest-json {{initdoc_actionable_heartbeat_compact_window_digest_out}} --heartbeat-jsonl {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_path}} --strict --out {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_out}}

parl-report-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-window:
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_window.py --heartbeat-jsonl {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_path}} --last {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_window_last}} --max-failed {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_window_max_failed}} --max-failed-rate-pct {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_window_max_failed_rate_pct}} --max-degraded {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_window_max_degraded}} --max-degraded-rate-pct {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_window_max_degraded_rate_pct}} --out {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_window_out}}

parl-check-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-window:
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_window.py --heartbeat-jsonl {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_path}} --last {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_window_last}} --max-failed {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_window_max_failed}} --max-failed-rate-pct {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_window_max_failed_rate_pct}} --max-degraded {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_window_max_degraded}} --max-degraded-rate-pct {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_window_max_degraded_rate_pct}} --strict --out {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_window_out}}

parl-report-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-compact:
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction.py --heartbeat-jsonl {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_path}} --compacted-jsonl {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_path}} --keep-recent {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_recent}} --keep-mid-span {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_mid_span}} --keep-mid-every {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_mid_every}} --keep-old-every {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_old_every}} --min-raw-for-dropped-check {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_min_raw}} --out {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_out}}

parl-check-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-compact:
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction.py --heartbeat-jsonl {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_path}} --compacted-jsonl {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_path}} --keep-recent {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_recent}} --keep-mid-span {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_mid_span}} --keep-mid-every {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_mid_every}} --keep-old-every {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_old_every}} --min-raw-for-dropped-check {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_min_raw}} --strict --out {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_out}}

parl-report-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-compact-window:
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.py --heartbeat-jsonl {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_path}} --compacted-jsonl {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_path}} --last {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_window_last}} --out {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_window_out}}

parl-check-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-compact-window:
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.py --heartbeat-jsonl {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_path}} --compacted-jsonl {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_path}} --last {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_window_last}} --strict --out {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_window_out}}

parl-report-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-compact-window-digest:
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.py --heartbeat-jsonl {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_path}} --compacted-jsonl {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_path}} --last {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_window_last}} --out {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_window_out}}
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.py --compaction-window-json {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_window_out}} --out {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_window_digest_out}}

parl-check-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-compact-window-digest:
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.py --heartbeat-jsonl {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_path}} --compacted-jsonl {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_path}} --last {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_window_last}} --out {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_window_out}}
  python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.py --compaction-window-json {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_window_out}} --strict --out {{initdoc_actionable_heartbeat_compact_window_digest_heartbeat_compact_window_digest_out}}

parl-backfill-initdoc-extractions:
  python3 scripts/backfill_initiative_doc_extractions.py --db {{db_path}} --doc-source-id parl_initiative_docs --initiative-source-ids '{{initdoc_extract_scope}}' --extractor-version heuristic_subject_v2 --limit {{initdoc_extract_limit}} --out {{initdoc_extract_out}}

parl-backfill-initdoc-extractions-missing:
  python3 scripts/backfill_initiative_doc_extractions.py --db {{db_path}} --doc-source-id parl_initiative_docs --initiative-source-ids '{{initdoc_extract_scope}}' --extractor-version heuristic_subject_v2 --only-missing --limit {{initdoc_extract_limit}} --out {{initdoc_extract_out}}

parl-export-initdoc-extraction-review-queue:
  python3 scripts/export_initdoc_extraction_review_queue.py --db {{db_path}} --source-id parl_initiative_docs --only-needs-review --limit {{initdoc_extract_review_limit}} --out {{initdoc_extract_review_out}}

parl-export-initdoc-extraction-label-studio:
  python3 scripts/export_initdoc_extraction_label_studio_tasks.py --db {{db_path}} --source-id parl_initiative_docs --only-needs-review --limit {{initdoc_extract_review_limit}} --out {{initdoc_extract_review_label_studio_out}} --config-out {{initdoc_extract_review_label_studio_config_out}}

parl-apply-initdoc-extraction-reviews:
  test -n "{{initdoc_extract_review_apply_file}}" || (echo "Set INITDOC_EXTRACT_REVIEW_APPLY_FILE=<csv_path>" && exit 2)
  python3 scripts/apply_initdoc_extraction_reviews.py --db {{db_path}} --source-id parl_initiative_docs --in "{{initdoc_extract_review_apply_file}}" --out {{initdoc_extract_review_apply_out}}

parl-apply-initdoc-extraction-reviews-dry-run:
  test -n "{{initdoc_extract_review_apply_file}}" || (echo "Set INITDOC_EXTRACT_REVIEW_APPLY_FILE=<csv_path>" && exit 2)
  python3 scripts/apply_initdoc_extraction_reviews.py --db {{db_path}} --source-id parl_initiative_docs --in "{{initdoc_extract_review_apply_file}}" --dry-run --out {{initdoc_extract_review_apply_out}}

parl-apply-initdoc-extraction-label-studio:
  test -n "{{initdoc_extract_review_label_studio_apply_file}}" || (echo "Set INITDOC_EXTRACT_REVIEW_LABEL_STUDIO_APPLY_FILE=<label_studio_json>" && exit 2)
  python3 scripts/apply_initdoc_extraction_label_studio_reviews.py --db {{db_path}} --source-id parl_initiative_docs --in "{{initdoc_extract_review_label_studio_apply_file}}" --out {{initdoc_extract_review_apply_out}}

parl-apply-initdoc-extraction-label-studio-dry-run:
  test -n "{{initdoc_extract_review_label_studio_apply_file}}" || (echo "Set INITDOC_EXTRACT_REVIEW_LABEL_STUDIO_APPLY_FILE=<label_studio_json>" && exit 2)
  python3 scripts/apply_initdoc_extraction_label_studio_reviews.py --db {{db_path}} --source-id parl_initiative_docs --in "{{initdoc_extract_review_label_studio_apply_file}}" --dry-run --out {{initdoc_extract_review_apply_out}}

parl-backfill-declared-stance:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-declared-stance --db {{db_path}} --source-id {{declared_source_id}} --min-auto-confidence {{declared_min_auto_confidence}}"

parl-backfill-declared-positions:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-declared-positions --db {{db_path}} --source-id {{declared_source_id}} --as-of-date {{snapshot_date}}"

parl-report-declared-source-status:
  out_arg=""; \
  if [ -n "{{declared_status_out}}" ]; then \
    out_arg=" --out {{declared_status_out}}"; \
  fi; \
  python3 scripts/report_declared_source_status.py --db {{db_path}} --source-id {{declared_source_id}}${out_arg}

parl-programas-status:
  python3 scripts/report_declared_source_status.py --db {{db_path}} --source-id programas_partidos --out {{programas_status_out}}

parl-export-programas-support-precision-sample:
  python3 scripts/export_programas_support_precision_sample.py --db {{db_path}} --source-id programas_partidos --parties "{{programas_precision_sample_parties}}" --per-party-limit {{programas_precision_sample_per_party_limit}} --limit {{programas_precision_sample_limit}} --dedupe-key "{{programas_precision_sample_dedupe_key}}" --min-unique-per-party {{programas_precision_sample_min_unique_per_party}} --excerpt-window-words {{programas_precision_sample_excerpt_window_words}} --excerpt-window-stride {{programas_precision_sample_excerpt_window_stride}} --excerpt-window-min-words {{programas_precision_sample_excerpt_window_min_words}} --out "{{programas_precision_sample_out}}" --summary-out "{{programas_precision_sample_summary_out}}"

parl-check-programas-support-precision-sample:
  python3 scripts/export_programas_support_precision_sample.py --db {{db_path}} --source-id programas_partidos --parties "{{programas_precision_sample_parties}}" --per-party-limit {{programas_precision_sample_per_party_limit}} --limit {{programas_precision_sample_limit}} --dedupe-key "{{programas_precision_sample_dedupe_key}}" --min-unique-per-party {{programas_precision_sample_min_unique_per_party}} --excerpt-window-words {{programas_precision_sample_excerpt_window_words}} --excerpt-window-stride {{programas_precision_sample_excerpt_window_stride}} --excerpt-window-min-words {{programas_precision_sample_excerpt_window_min_words}} --out "{{programas_precision_sample_out}}" --summary-out "{{programas_precision_sample_summary_out}}" --strict

parl-report-programas-unclear-tail-dedupe:
  python3 scripts/report_programas_unclear_tail_dedupe.py --db {{db_path}} --source-id programas_partidos --parties "{{programas_unclear_tail_parties}}" --excerpt-len {{programas_unclear_tail_excerpt_len}} --max-duplicate-share {{programas_unclear_tail_max_duplicate_share}} --out "{{programas_unclear_tail_report_out}}" --queue-out "{{programas_unclear_tail_queue_out}}" --profile-out "{{programas_unclear_tail_profile_out}}"

parl-check-programas-unclear-tail-dedupe:
  python3 scripts/report_programas_unclear_tail_dedupe.py --db {{db_path}} --source-id programas_partidos --parties "{{programas_unclear_tail_parties}}" --excerpt-len {{programas_unclear_tail_excerpt_len}} --max-duplicate-share {{programas_unclear_tail_max_duplicate_share}} --out "{{programas_unclear_tail_report_out}}" --queue-out "{{programas_unclear_tail_queue_out}}" --profile-out "{{programas_unclear_tail_profile_out}}" --strict

parl-report-programas-support-unclear-unique-ratio:
  python3 scripts/report_programas_support_unclear_unique_ratio.py --db {{db_path}} --source-id programas_partidos --parties "{{programas_unclear_ratio_parties}}" --min-support-unclear-unique-ratio {{programas_unclear_ratio_min}} --near-duplicate-jaccard-min {{programas_unclear_ratio_near_duplicate_jaccard_min}} --near-duplicate-containment-min {{programas_unclear_ratio_near_duplicate_containment_min}} --near-duplicate-ngram-size {{programas_unclear_ratio_near_duplicate_ngram_size}} $( [ "{{programas_unclear_ratio_disable_near_duplicate_dedupe}}" = "1" ] && printf '%s' "--disable-near-duplicate-dedupe" ) --out "{{programas_unclear_ratio_out}}" --csv-out "{{programas_unclear_ratio_csv_out}}"

parl-check-programas-support-unclear-unique-ratio:
  python3 scripts/report_programas_support_unclear_unique_ratio.py --db {{db_path}} --source-id programas_partidos --parties "{{programas_unclear_ratio_parties}}" --min-support-unclear-unique-ratio {{programas_unclear_ratio_min}} --near-duplicate-jaccard-min {{programas_unclear_ratio_near_duplicate_jaccard_min}} --near-duplicate-containment-min {{programas_unclear_ratio_near_duplicate_containment_min}} --near-duplicate-ngram-size {{programas_unclear_ratio_near_duplicate_ngram_size}} $( [ "{{programas_unclear_ratio_disable_near_duplicate_dedupe}}" = "1" ] && printf '%s' "--disable-near-duplicate-dedupe" ) --out "{{programas_unclear_ratio_out}}" --csv-out "{{programas_unclear_ratio_csv_out}}" --strict

parl-report-programas-empleo-fiscal-snippets-audit:
  python3 scripts/report_programas_empleo_fiscal_snippets_audit.py --db {{db_path}} --source-id programas_partidos --topic-key "{{programas_empleo_fiscal_audit_topic_key}}" --parties "{{programas_empleo_fiscal_audit_parties}}" --fiscal-terms "{{programas_empleo_fiscal_audit_terms}}" --employment-anchor-terms "{{programas_empleo_fiscal_audit_anchor_terms}}" --max-suspicious-support-rows {{programas_empleo_fiscal_audit_max_suspicious_support}} --out "{{programas_empleo_fiscal_audit_out}}" --csv-out "{{programas_empleo_fiscal_audit_csv_out}}"

parl-check-programas-empleo-fiscal-snippets-audit:
  python3 scripts/report_programas_empleo_fiscal_snippets_audit.py --db {{db_path}} --source-id programas_partidos --topic-key "{{programas_empleo_fiscal_audit_topic_key}}" --parties "{{programas_empleo_fiscal_audit_parties}}" --fiscal-terms "{{programas_empleo_fiscal_audit_terms}}" --employment-anchor-terms "{{programas_empleo_fiscal_audit_anchor_terms}}" --max-suspicious-support-rows {{programas_empleo_fiscal_audit_max_suspicious_support}} --out "{{programas_empleo_fiscal_audit_out}}" --csv-out "{{programas_empleo_fiscal_audit_csv_out}}" --strict

parl-rotate-programas-support-precision-labels:
  python3 scripts/rotate_programas_precision_labels.py --sample-in "{{programas_precision_sample_out}}" --labels-in "{{programas_precision_rotate_labels_in}}" --out "{{programas_precision_labeled_out}}" --summary-out "{{programas_precision_rotate_summary_out}}" --max-unlabeled {{programas_precision_rotate_max_unlabeled}}

parl-check-programas-support-precision-labels-rotation:
  python3 scripts/rotate_programas_precision_labels.py --sample-in "{{programas_precision_sample_out}}" --labels-in "{{programas_precision_rotate_labels_in}}" --out "{{programas_precision_labeled_out}}" --summary-out "{{programas_precision_rotate_summary_out}}" --max-unlabeled {{programas_precision_rotate_max_unlabeled}} --strict

parl-check-programas-support-precision-labels-rotation-strict:
  python3 scripts/rotate_programas_precision_labels.py --sample-in "{{programas_precision_sample_out}}" --labels-in "{{programas_precision_rotate_labels_in}}" --out "{{programas_precision_labeled_out}}" --summary-out "{{programas_precision_rotate_summary_out}}" --max-unlabeled {{programas_precision_rotate_strict_max_unlabeled}} --strict

parl-report-programas-support-precision-audit:
  python3 scripts/report_programas_support_precision_audit.py --in "{{programas_precision_audit_in}}" --min-precision {{programas_precision_min}} --min-reviewed {{programas_precision_min_reviewed}} --min-party-precision {{programas_precision_min_party}} --required-parties "{{programas_precision_required_parties}}" --out "{{programas_precision_audit_out}}" --breakdown-out "{{programas_precision_audit_breakdown_out}}"

parl-check-programas-support-precision-audit:
  python3 scripts/report_programas_support_precision_audit.py --in "{{programas_precision_audit_in}}" --min-precision {{programas_precision_min}} --min-reviewed {{programas_precision_min_reviewed}} --min-party-precision {{programas_precision_min_party}} --required-parties "{{programas_precision_required_parties}}" --out "{{programas_precision_audit_out}}" --breakdown-out "{{programas_precision_audit_breakdown_out}}" --strict

parl-programas-precision-guardrail:
  mkdir -p "$(dirname "{{programas_precision_reconcile_out}}")" "$(dirname "{{programas_precision_declared_positions_out}}")" "$(dirname "{{programas_precision_combined_positions_out}}")" "$(dirname "{{programas_precision_status_out}}")" "$(dirname "{{programas_precision_quality_out}}")" "$(dirname "{{programas_precision_tracker_out}}")"
  just parl-check-programas-support-precision-audit
  python3 scripts/ingestar_parlamentario_es.py backfill-declared-stance --db {{db_path}} --source-id programas_partidos --min-auto-confidence {{declared_min_auto_confidence}} --reconcile-no-signal > "{{programas_precision_reconcile_out}}"
  python3 scripts/ingestar_parlamentario_es.py backfill-declared-positions --db {{db_path}} --source-id programas_partidos --as-of-date {{snapshot_date}} > "{{programas_precision_declared_positions_out}}"
  python3 scripts/ingestar_parlamentario_es.py backfill-combined-positions --db {{db_path}} --as-of-date {{snapshot_date}} > "{{programas_precision_combined_positions_out}}"
  python3 scripts/report_declared_source_status.py --db {{db_path}} --source-id programas_partidos --out "{{programas_precision_status_out}}"
  skip_arg=""; \
  if [ "{{declared_quality_skip_vote_gate}}" = "1" ]; then \
    skip_arg=" --skip-vote-gate"; \
  fi; \
  python3 scripts/ingestar_parlamentario_es.py quality-report --db {{db_path}} --source-ids {{declared_quality_vote_source_ids}} --include-declared --declared-source-ids programas_partidos --enforce-gate${skip_arg} --json-out "{{programas_precision_quality_out}}"
  python3 scripts/e2e_tracker_status.py --db {{db_path}} --tracker docs/etl/e2e-scrape-load-tracker.md --fail-on-mismatch --fail-on-done-zero-real > "{{programas_precision_tracker_out}}"

parl-programas-precision-guardrail-rotated:
  mkdir -p "$(dirname "{{programas_precision_reconcile_out}}")" "$(dirname "{{programas_precision_declared_positions_out}}")" "$(dirname "{{programas_precision_combined_positions_out}}")" "$(dirname "{{programas_precision_status_out}}")" "$(dirname "{{programas_precision_quality_out}}")" "$(dirname "{{programas_precision_tracker_out}}")"
  just parl-export-programas-support-precision-sample
  just parl-check-programas-support-precision-labels-rotation-strict
  python3 scripts/report_programas_support_precision_audit.py --in "{{programas_precision_labeled_out}}" --min-precision {{programas_precision_min}} --min-reviewed {{programas_precision_min_reviewed}} --min-party-precision {{programas_precision_min_party}} --required-parties "{{programas_precision_required_parties}}" --out "{{programas_precision_audit_out}}" --breakdown-out "{{programas_precision_audit_breakdown_out}}" --strict
  python3 scripts/ingestar_parlamentario_es.py backfill-declared-stance --db {{db_path}} --source-id programas_partidos --min-auto-confidence {{declared_min_auto_confidence}} --reconcile-no-signal > "{{programas_precision_reconcile_out}}"
  python3 scripts/ingestar_parlamentario_es.py backfill-declared-positions --db {{db_path}} --source-id programas_partidos --as-of-date {{snapshot_date}} > "{{programas_precision_declared_positions_out}}"
  python3 scripts/ingestar_parlamentario_es.py backfill-combined-positions --db {{db_path}} --as-of-date {{snapshot_date}} > "{{programas_precision_combined_positions_out}}"
  python3 scripts/report_declared_source_status.py --db {{db_path}} --source-id programas_partidos --out "{{programas_precision_status_out}}"
  skip_arg=""; \
  if [ "{{declared_quality_skip_vote_gate}}" = "1" ]; then \
    skip_arg=" --skip-vote-gate"; \
  fi; \
  python3 scripts/ingestar_parlamentario_es.py quality-report --db {{db_path}} --source-ids {{declared_quality_vote_source_ids}} --include-declared --declared-source-ids programas_partidos --enforce-gate${skip_arg} --json-out "{{programas_precision_quality_out}}"
  python3 scripts/e2e_tracker_status.py --db {{db_path}} --tracker docs/etl/e2e-scrape-load-tracker.md --fail-on-mismatch --fail-on-done-zero-real > "{{programas_precision_tracker_out}}"

parl-validate-programas-manifest:
  require_local_arg=""; \
  if [ "{{programas_manifest_require_local_path}}" = "1" ]; then \
    require_local_arg=" --require-local-path"; \
  fi; \
  python3 scripts/validate_programas_manifest.py --manifest {{programas_manifest}} --out {{programas_manifest_validate_out}}${require_local_arg}

parl-validate-sanction-norms-seed:
  PYTHONPATH=. python3 scripts/validate_sanction_norms_seed.py --seed {{sanction_norms_seed}} --out {{sanction_norms_seed_validate_out}}

parl-import-sanction-norms-seed:
  PYTHONPATH=. python3 scripts/import_sanction_norms_seed.py --db {{db_path}} --seed {{sanction_norms_seed}} --snapshot-date {{snapshot_date}} --source-id {{sanction_norms_seed_source_id}} --out {{sanction_norms_seed_import_out}}

parl-report-sanction-norms-seed-status:
  PYTHONPATH=. python3 scripts/report_sanction_norms_seed_status.py --db {{db_path}} --sample-limit {{sanction_norms_seed_status_sample_limit}} --out {{sanction_norms_seed_status_out}}

parl-report-sanction-norms-vote-gap-diagnosis:
  PYTHONPATH=. python3 scripts/report_sanction_norms_vote_gap_diagnosis.py --db {{db_path}} --roles {{sanction_norms_vote_gap_diagnosis_roles}} --out {{sanction_norms_vote_gap_diagnosis_out}}

parl-export-sanction-norms-seed-source-record-upgrade-queue:
  PYTHONPATH=. python3 scripts/export_sanction_norms_seed_source_record_upgrade_queue.py --db {{db_path}} --seed-schema-version {{sanction_norms_seed_source_record_upgrade_queue_seed_schema_version}} --limit {{sanction_norms_seed_source_record_upgrade_queue_limit}} --out {{sanction_norms_seed_source_record_upgrade_queue_out}} --csv-out {{sanction_norms_seed_source_record_upgrade_queue_csv_out}}

parl-backfill-sanction-norms-boe-source-records:
  PYTHONPATH=. python3 scripts/backfill_sanction_norms_boe_source_records.py --db {{db_path}} --source-id {{sanction_norms_seed_source_id}} --seed-schema-version {{sanction_norms_seed_source_record_upgrade_queue_seed_schema_version}} --timeout {{sanction_norms_boe_backfill_timeout}} --limit {{sanction_norms_boe_backfill_limit}} --strict-network --out {{sanction_norms_boe_backfill_out}}

parl-apply-sanction-norms-source-record-upgrade:
  dry_arg=""; \
  if [ "{{sanction_norms_source_record_upgrade_apply_dry_run}}" = "1" ]; then \
    dry_arg=" --dry-run"; \
  fi; \
  PYTHONPATH=. python3 scripts/apply_sanction_norms_seed_source_record_upgrade_queue.py --db {{db_path}} --seed-schema-version {{sanction_norms_seed_source_record_upgrade_queue_seed_schema_version}} --limit {{sanction_norms_source_record_upgrade_apply_limit}} --out {{sanction_norms_source_record_upgrade_apply_out}}${dry_arg}

parl-backfill-sanction-norms-parliamentary-evidence:
  PYTHONPATH=. python3 scripts/backfill_sanction_norms_parliamentary_evidence.py --db {{db_path}} --roles {{sanction_norms_parliamentary_evidence_roles}} --limit {{sanction_norms_parliamentary_evidence_limit}} --out {{sanction_norms_parliamentary_evidence_out}}

parl-backfill-sanction-norms-vote-evidence:
  PYTHONPATH=. python3 scripts/backfill_sanction_norms_vote_evidence.py --db {{db_path}} --roles {{sanction_norms_vote_evidence_roles}} --limit-events {{sanction_norms_vote_evidence_limit_events}} --out {{sanction_norms_vote_evidence_out}}

parl-backfill-sanction-norms-execution-evidence:
  PYTHONPATH=. python3 scripts/backfill_sanction_norms_execution_evidence.py --db {{db_path}} --roles {{sanction_norms_execution_evidence_roles}} --limit {{sanction_norms_execution_evidence_limit}} --out {{sanction_norms_execution_evidence_out}}

parl-backfill-sanction-norms-execution-lineage-evidence:
  PYTHONPATH=. python3 scripts/backfill_sanction_norms_execution_lineage_evidence.py --db {{db_path}} --roles {{sanction_norms_execution_lineage_evidence_roles}} --limit {{sanction_norms_execution_lineage_evidence_limit}} --out {{sanction_norms_execution_lineage_evidence_out}}

parl-backfill-sanction-norms-procedural-metric-evidence:
  PYTHONPATH=. python3 scripts/backfill_sanction_norms_procedural_metric_evidence.py --db {{db_path}} --roles {{sanction_norms_procedural_metric_evidence_roles}} --limit {{sanction_norms_procedural_metric_evidence_limit}} --out {{sanction_norms_procedural_metric_evidence_out}}

parl-sanction-norms-seed-pipeline:
  just parl-validate-sanction-norms-seed
  just parl-import-sanction-norms-seed
  just parl-report-sanction-norms-seed-status
  just parl-export-sanction-norms-seed-source-record-upgrade-queue

parl-test-sanction-norms-seed:
  python3 -m unittest tests/test_validate_sanction_norms_seed.py tests/test_import_sanction_norms_seed.py tests/test_report_sanction_norms_seed_status.py tests/test_report_sanction_norms_vote_gap_diagnosis.py tests/test_export_sanction_norms_seed_source_record_upgrade_queue.py tests/test_backfill_sanction_norms_boe_source_records.py tests/test_apply_sanction_norms_seed_source_record_upgrade_queue.py tests/test_backfill_sanction_norms_parliamentary_evidence.py tests/test_backfill_sanction_norms_vote_evidence.py tests/test_backfill_sanction_norms_execution_evidence.py tests/test_backfill_sanction_norms_execution_lineage_evidence.py tests/test_backfill_sanction_norms_procedural_metric_evidence.py

parl-validate-sanction-data-catalog-seed:
  PYTHONPATH=. python3 scripts/validate_sanction_data_catalog_seed.py --seed {{sanction_data_catalog_seed}} --out {{sanction_data_catalog_validate_out}}

parl-import-sanction-data-catalog-seed:
  PYTHONPATH=. python3 scripts/import_sanction_data_catalog_seed.py --db {{db_path}} --seed {{sanction_data_catalog_seed}} --snapshot-date {{snapshot_date}} --source-id {{sanction_data_catalog_source_id}} --out {{sanction_data_catalog_import_out}}

parl-import-domain-taxonomy-seed:
  PYTHONPATH=. python3 scripts/import_domain_taxonomy_seed.py --db {{db_path}} --doc {{domain_taxonomy_seed}} --snapshot-date {{snapshot_date}}

parl-import-policy-axes-tier1-seed:
  PYTHONPATH=. python3 scripts/import_policy_axes_seed.py --db {{db_path}} --doc {{policy_axes_tier1_seed}} --snapshot-date {{snapshot_date}}

parl-import-public-policy-taxonomy-seed:
  just parl-import-domain-taxonomy-seed
  just parl-import-policy-axes-tier1-seed

parl-report-sanction-data-catalog-status:
  PYTHONPATH=. python3 scripts/report_sanction_data_catalog_status.py --db {{db_path}} --sample-limit {{sanction_data_catalog_status_sample_limit}} --out {{sanction_data_catalog_status_out}}

parl-report-sanction-procedural-official-review-status:
  period_args=""; \
  if [ -n "{{sanction_procedural_official_review_status_period_date}}" ]; then \
    period_args="${period_args} --period-date {{sanction_procedural_official_review_status_period_date}}"; \
  fi; \
  if [ -n "{{sanction_procedural_official_review_status_period_granularity}}" ]; then \
    period_args="${period_args} --period-granularity {{sanction_procedural_official_review_status_period_granularity}}"; \
  fi; \
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_status.py --db {{db_path}} --queue-limit {{sanction_procedural_official_review_status_queue_limit}} --csv-out {{sanction_procedural_official_review_status_csv_out}} --out {{sanction_procedural_official_review_status_out}}${period_args}

parl-export-sanction-procedural-official-review-kpi-gap-queue:
  period_args=""; \
  if [ -n "{{sanction_procedural_official_review_kpi_gap_period_date}}" ]; then \
    period_args="${period_args} --period-date {{sanction_procedural_official_review_kpi_gap_period_date}}"; \
  fi; \
  if [ -n "{{sanction_procedural_official_review_kpi_gap_period_granularity}}" ]; then \
    period_args="${period_args} --period-granularity {{sanction_procedural_official_review_kpi_gap_period_granularity}}"; \
  fi; \
  include_ready_arg=""; \
  if [ "{{sanction_procedural_official_review_kpi_gap_include_ready}}" = "1" ]; then \
    include_ready_arg=" --include-ready"; \
  fi; \
  strict_empty_arg=""; \
  if [ "{{sanction_procedural_official_review_kpi_gap_strict_empty}}" = "1" ]; then \
    strict_empty_arg=" --strict-empty"; \
  fi; \
  PYTHONPATH=. python3 scripts/export_sanction_procedural_official_review_kpi_gap_queue.py --db {{db_path}} --queue-limit {{sanction_procedural_official_review_kpi_gap_queue_limit}} --csv-out {{sanction_procedural_official_review_kpi_gap_csv_out}} --out {{sanction_procedural_official_review_kpi_gap_out}}${period_args}${include_ready_arg}${strict_empty_arg}

parl-export-sanction-procedural-official-review-apply-from-kpi-gap-queue:
  period_args=""; \
  if [ -n "{{sanction_procedural_official_review_apply_from_gap_period_date}}" ]; then \
    period_args="${period_args} --period-date {{sanction_procedural_official_review_apply_from_gap_period_date}}"; \
  fi; \
  if [ -n "{{sanction_procedural_official_review_apply_from_gap_period_granularity}}" ]; then \
    period_args="${period_args} --period-granularity {{sanction_procedural_official_review_apply_from_gap_period_granularity}}"; \
  fi; \
  include_ready_arg=""; \
  if [ "{{sanction_procedural_official_review_apply_from_gap_include_ready}}" = "1" ]; then \
    include_ready_arg=" --include-ready"; \
  fi; \
  strict_actionable_arg=""; \
  if [ "{{sanction_procedural_official_review_apply_from_gap_strict_actionable}}" = "1" ]; then \
    strict_actionable_arg=" --strict-actionable"; \
  fi; \
  PYTHONPATH=. python3 scripts/export_sanction_procedural_official_review_apply_from_kpi_gap_queue.py --db {{db_path}} --source-id {{sanction_procedural_official_review_apply_from_gap_source_id}} --queue-limit {{sanction_procedural_official_review_apply_from_gap_queue_limit}} --statuses "{{sanction_procedural_official_review_apply_from_gap_statuses}}" --out {{sanction_procedural_official_review_apply_from_gap_out}} --summary-out {{sanction_procedural_official_review_apply_from_gap_summary_out}}${period_args}${include_ready_arg}${strict_actionable_arg}

parl-export-sanction-procedural-official-review-raw-packets-from-kpi-gap-queue:
  period_args=""; \
  if [ -n "{{sanction_procedural_official_review_raw_packets_period_date}}" ]; then \
    period_args="${period_args} --period-date {{sanction_procedural_official_review_raw_packets_period_date}}"; \
  fi; \
  if [ -n "{{sanction_procedural_official_review_raw_packets_period_granularity}}" ]; then \
    period_args="${period_args} --period-granularity {{sanction_procedural_official_review_raw_packets_period_granularity}}"; \
  fi; \
  include_ready_arg=""; \
  if [ "{{sanction_procedural_official_review_raw_packets_include_ready}}" = "1" ]; then \
    include_ready_arg=" --include-ready"; \
  fi; \
  strict_actionable_arg=""; \
  if [ "{{sanction_procedural_official_review_raw_packets_strict_actionable}}" = "1" ]; then \
    strict_actionable_arg=" --strict-actionable"; \
  fi; \
  PYTHONPATH=. python3 scripts/export_sanction_procedural_official_review_raw_packets_from_kpi_gap_queue.py --db {{db_path}} --source-id {{sanction_procedural_official_review_raw_packets_source_id}} --queue-limit {{sanction_procedural_official_review_raw_packets_queue_limit}} --statuses "{{sanction_procedural_official_review_raw_packets_statuses}}" --out-dir {{sanction_procedural_official_review_raw_packets_out_dir}} --summary-out {{sanction_procedural_official_review_raw_packets_summary_out}}${period_args}${include_ready_arg}${strict_actionable_arg}

parl-report-sanction-procedural-official-review-raw-packets-progress:
  period_args=""; \
  if [ -n "{{sanction_procedural_official_review_raw_packets_progress_period_date}}" ]; then \
    period_args="${period_args} --period-date {{sanction_procedural_official_review_raw_packets_progress_period_date}}"; \
  fi; \
  if [ -n "{{sanction_procedural_official_review_raw_packets_progress_period_granularity}}" ]; then \
    period_args="${period_args} --period-granularity {{sanction_procedural_official_review_raw_packets_progress_period_granularity}}"; \
  fi; \
  include_ready_arg=""; \
  if [ "{{sanction_procedural_official_review_raw_packets_progress_include_ready}}" = "1" ]; then \
    include_ready_arg=" --include-ready"; \
  fi; \
  strict_actionable_arg=""; \
  if [ "{{sanction_procedural_official_review_raw_packets_progress_strict_actionable}}" = "1" ]; then \
    strict_actionable_arg=" --strict-actionable"; \
  fi; \
  strict_ready_arg=""; \
  if [ "{{sanction_procedural_official_review_raw_packets_progress_strict_ready}}" = "1" ]; then \
    strict_ready_arg=" --strict-ready"; \
  fi; \
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_raw_packets_progress.py --db {{db_path}} --packets-dir {{sanction_procedural_official_review_raw_packets_progress_packets_dir}} --source-id {{sanction_procedural_official_review_raw_packets_progress_source_id}} --queue-limit {{sanction_procedural_official_review_raw_packets_progress_queue_limit}} --statuses "{{sanction_procedural_official_review_raw_packets_progress_statuses}}" --csv-out {{sanction_procedural_official_review_raw_packets_progress_csv_out}} --out {{sanction_procedural_official_review_raw_packets_progress_out}}${period_args}${include_ready_arg}${strict_actionable_arg}${strict_ready_arg}

parl-export-sanction-procedural-official-review-packet-fix-queue:
  period_args=""; \
  if [ -n "{{sanction_procedural_official_review_packet_fix_queue_period_date}}" ]; then \
    period_args="${period_args} --period-date {{sanction_procedural_official_review_packet_fix_queue_period_date}}"; \
  fi; \
  if [ -n "{{sanction_procedural_official_review_packet_fix_queue_period_granularity}}" ]; then \
    period_args="${period_args} --period-granularity {{sanction_procedural_official_review_packet_fix_queue_period_granularity}}"; \
  fi; \
  include_ready_arg=""; \
  if [ "{{sanction_procedural_official_review_packet_fix_queue_include_ready}}" = "1" ]; then \
    include_ready_arg=" --include-ready"; \
  fi; \
  strict_empty_arg=""; \
  if [ "{{sanction_procedural_official_review_packet_fix_queue_strict_empty}}" = "1" ]; then \
    strict_empty_arg=" --strict-empty"; \
  fi; \
  PYTHONPATH=. python3 scripts/export_sanction_procedural_official_review_packet_fix_queue.py --db {{db_path}} --packets-dir {{sanction_procedural_official_review_packet_fix_queue_packets_dir}} --source-id {{sanction_procedural_official_review_packet_fix_queue_source_id}} --queue-limit {{sanction_procedural_official_review_packet_fix_queue_queue_limit}} --statuses "{{sanction_procedural_official_review_packet_fix_queue_statuses}}" --csv-out {{sanction_procedural_official_review_packet_fix_queue_csv_out}} --out {{sanction_procedural_official_review_packet_fix_queue_out}}${period_args}${include_ready_arg}${strict_empty_arg}

parl-run-sanction-procedural-official-review-packet-fix-ready-cycle:
  period_args=""; \
  if [ -n "{{sanction_procedural_official_review_packet_fix_ready_cycle_period_date}}" ]; then \
    period_args="${period_args} --period-date {{sanction_procedural_official_review_packet_fix_ready_cycle_period_date}}"; \
  fi; \
  if [ -n "{{sanction_procedural_official_review_packet_fix_ready_cycle_period_granularity}}" ]; then \
    period_args="${period_args} --period-granularity {{sanction_procedural_official_review_packet_fix_ready_cycle_period_granularity}}"; \
  fi; \
  include_ready_arg=""; \
  if [ "{{sanction_procedural_official_review_packet_fix_ready_cycle_include_ready}}" = "1" ]; then \
    include_ready_arg=" --include-ready"; \
  fi; \
  strict_fix_empty_arg=""; \
  if [ "{{sanction_procedural_official_review_packet_fix_ready_cycle_strict_fix_empty}}" = "1" ]; then \
    strict_fix_empty_arg=" --strict-fix-empty"; \
  fi; \
  strict_actionable_arg=""; \
  if [ "{{sanction_procedural_official_review_packet_fix_ready_cycle_strict_actionable}}" = "1" ]; then \
    strict_actionable_arg=" --strict-actionable"; \
  fi; \
  strict_min_ready_arg=""; \
  if [ "{{sanction_procedural_official_review_packet_fix_ready_cycle_strict_min_ready}}" = "1" ]; then \
    strict_min_ready_arg=" --strict-min-ready"; \
  fi; \
  strict_raw_arg=""; \
  if [ "{{sanction_procedural_official_review_packet_fix_ready_cycle_strict_raw}}" = "1" ]; then \
    strict_raw_arg=" --strict-raw"; \
  fi; \
  strict_prepare_arg=""; \
  if [ "{{sanction_procedural_official_review_packet_fix_ready_cycle_strict_prepare}}" = "1" ]; then \
    strict_prepare_arg=" --strict-prepare"; \
  fi; \
  strict_readiness_arg=""; \
  if [ "{{sanction_procedural_official_review_packet_fix_ready_cycle_strict_readiness}}" = "1" ]; then \
    strict_readiness_arg=" --strict-readiness"; \
  fi; \
  PYTHONPATH=. python3 scripts/run_sanction_procedural_official_review_packet_fix_ready_cycle.py --db {{db_path}} --packets-dir {{sanction_procedural_official_review_packet_fix_ready_cycle_packets_dir}} --source-id {{sanction_procedural_official_review_packet_fix_ready_cycle_source_id}} --queue-limit {{sanction_procedural_official_review_packet_fix_ready_cycle_queue_limit}} --statuses "{{sanction_procedural_official_review_packet_fix_ready_cycle_statuses}}" --min-ready-packets {{sanction_procedural_official_review_packet_fix_ready_cycle_min_ready_packets}} --fix-csv-out {{sanction_procedural_official_review_packet_fix_ready_cycle_fix_csv_out}} --fix-out {{sanction_procedural_official_review_packet_fix_ready_cycle_fix_out}} --raw-in-out {{sanction_procedural_official_review_packet_fix_ready_cycle_raw_in_out}} --progress-out {{sanction_procedural_official_review_packet_fix_ready_cycle_progress_out}} --ready-cycle-out {{sanction_procedural_official_review_packet_fix_ready_cycle_ready_cycle_out}} --snapshot-date {{snapshot_date}} --readiness-tolerance {{sanction_procedural_official_review_readiness_tolerance}} --readiness-queue-limit {{sanction_procedural_official_review_readiness_queue_limit}} --status-queue-limit {{sanction_procedural_official_review_status_queue_limit}} --out {{sanction_procedural_official_review_packet_fix_ready_cycle_out}}${period_args}${include_ready_arg}${strict_fix_empty_arg}${strict_actionable_arg}${strict_min_ready_arg}${strict_raw_arg}${strict_prepare_arg}${strict_readiness_arg}

parl-run-sanction-procedural-official-review-packet-fix-ready-cycle-dry-run:
  period_args=""; \
  if [ -n "{{sanction_procedural_official_review_packet_fix_ready_cycle_period_date}}" ]; then \
    period_args="${period_args} --period-date {{sanction_procedural_official_review_packet_fix_ready_cycle_period_date}}"; \
  fi; \
  if [ -n "{{sanction_procedural_official_review_packet_fix_ready_cycle_period_granularity}}" ]; then \
    period_args="${period_args} --period-granularity {{sanction_procedural_official_review_packet_fix_ready_cycle_period_granularity}}"; \
  fi; \
  include_ready_arg=""; \
  if [ "{{sanction_procedural_official_review_packet_fix_ready_cycle_include_ready}}" = "1" ]; then \
    include_ready_arg=" --include-ready"; \
  fi; \
  strict_fix_empty_arg=""; \
  if [ "{{sanction_procedural_official_review_packet_fix_ready_cycle_strict_fix_empty}}" = "1" ]; then \
    strict_fix_empty_arg=" --strict-fix-empty"; \
  fi; \
  strict_actionable_arg=""; \
  if [ "{{sanction_procedural_official_review_packet_fix_ready_cycle_strict_actionable}}" = "1" ]; then \
    strict_actionable_arg=" --strict-actionable"; \
  fi; \
  strict_min_ready_arg=""; \
  if [ "{{sanction_procedural_official_review_packet_fix_ready_cycle_strict_min_ready}}" = "1" ]; then \
    strict_min_ready_arg=" --strict-min-ready"; \
  fi; \
  strict_raw_arg=""; \
  if [ "{{sanction_procedural_official_review_packet_fix_ready_cycle_strict_raw}}" = "1" ]; then \
    strict_raw_arg=" --strict-raw"; \
  fi; \
  strict_prepare_arg=""; \
  if [ "{{sanction_procedural_official_review_packet_fix_ready_cycle_strict_prepare}}" = "1" ]; then \
    strict_prepare_arg=" --strict-prepare"; \
  fi; \
  strict_readiness_arg=""; \
  if [ "{{sanction_procedural_official_review_packet_fix_ready_cycle_strict_readiness}}" = "1" ]; then \
    strict_readiness_arg=" --strict-readiness"; \
  fi; \
  PYTHONPATH=. python3 scripts/run_sanction_procedural_official_review_packet_fix_ready_cycle.py --db {{db_path}} --packets-dir {{sanction_procedural_official_review_packet_fix_ready_cycle_packets_dir}} --source-id {{sanction_procedural_official_review_packet_fix_ready_cycle_source_id}} --queue-limit {{sanction_procedural_official_review_packet_fix_ready_cycle_queue_limit}} --statuses "{{sanction_procedural_official_review_packet_fix_ready_cycle_statuses}}" --min-ready-packets {{sanction_procedural_official_review_packet_fix_ready_cycle_min_ready_packets}} --fix-csv-out {{sanction_procedural_official_review_packet_fix_ready_cycle_fix_csv_out}} --fix-out {{sanction_procedural_official_review_packet_fix_ready_cycle_fix_out}} --raw-in-out {{sanction_procedural_official_review_packet_fix_ready_cycle_raw_in_out}} --progress-out {{sanction_procedural_official_review_packet_fix_ready_cycle_progress_out}} --ready-cycle-out {{sanction_procedural_official_review_packet_fix_ready_cycle_ready_cycle_out}} --snapshot-date {{snapshot_date}} --readiness-tolerance {{sanction_procedural_official_review_readiness_tolerance}} --readiness-queue-limit {{sanction_procedural_official_review_readiness_queue_limit}} --status-queue-limit {{sanction_procedural_official_review_status_queue_limit}} --dry-run --out {{sanction_procedural_official_review_packet_fix_ready_cycle_out}}${period_args}${include_ready_arg}${strict_fix_empty_arg}${strict_actionable_arg}${strict_min_ready_arg}${strict_raw_arg}${strict_prepare_arg}${strict_readiness_arg}

parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat.py --fix-queue-json {{sanction_procedural_official_review_packet_fix_queue_heartbeat_fix_queue_json}} --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_path}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_out}}

parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-window:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_window.py --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_path}} --last {{sanction_procedural_official_review_packet_fix_queue_heartbeat_window}} --max-failed {{sanction_procedural_official_review_packet_fix_queue_heartbeat_window_max_failed}} --max-failed-rate-pct {{sanction_procedural_official_review_packet_fix_queue_heartbeat_window_max_failed_rate_pct}} --max-degraded {{sanction_procedural_official_review_packet_fix_queue_heartbeat_window_max_degraded}} --max-degraded-rate-pct {{sanction_procedural_official_review_packet_fix_queue_heartbeat_window_max_degraded_rate_pct}} --max-nonempty-queue-runs {{sanction_procedural_official_review_packet_fix_queue_heartbeat_window_max_nonempty_queue_runs}} --max-nonempty-queue-rate-pct {{sanction_procedural_official_review_packet_fix_queue_heartbeat_window_max_nonempty_queue_rate_pct}} --max-malformed {{sanction_procedural_official_review_packet_fix_queue_heartbeat_window_max_malformed}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_window_out}}

parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction.py --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_path}} --compacted-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_path}} --keep-recent {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_recent}} --keep-mid-span {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_mid_span}} --keep-mid-every {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_mid_every}} --keep-old-every {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_old_every}} --min-raw-for-dropped-check {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_min_raw}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_out}}

parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window.py --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_path}} --compacted-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_path}} --last {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_last}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_out}}

parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest.py --compaction-window-json {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_in}} --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_out}}

parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest.py --compaction-window-json {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_in}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_out}}

parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat.py --digest-json {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_digest_json}} --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_path}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_out}}

parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-window:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_window.py --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_path}} --last {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_window}} --max-failed {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_window_max_failed}} --max-failed-rate-pct {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_window_max_failed_rate_pct}} --max-degraded {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_window_max_degraded}} --max-degraded-rate-pct {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_window_max_degraded_rate_pct}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_window_out}}

parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction.py --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_path}} --compacted-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_path}} --keep-recent {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_recent}} --keep-mid-span {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_mid_span}} --keep-mid-every {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_mid_every}} --keep-old-every {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_old_every}} --min-raw-for-dropped-check {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_min_raw}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_out}}

parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window.py --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_path}} --compacted-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_path}} --last {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_last}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_out}}

parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window.py --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_path}} --compacted-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_path}} --last {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_last}} --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_out}}
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.py --compaction-window-json {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_out}} --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_out}}

parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window.py --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_path}} --compacted-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_path}} --last {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_last}} --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_out}}
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.py --compaction-window-json {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_out}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_out}}

parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat.py --digest-json {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_digest_json}} --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_out}}

parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat.py --digest-json {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_digest_json}} --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_out}}

parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-window:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_window.py --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path}} --last {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window}} --max-failed {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_failed}} --max-failed-rate-pct {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_failed_rate_pct}} --max-degraded {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_degraded}} --max-degraded-rate-pct {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_degraded_rate_pct}} --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_out}}

parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-window:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_window.py --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path}} --last {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window}} --max-failed {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_failed}} --max-failed-rate-pct {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_failed_rate_pct}} --max-degraded {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_degraded}} --max-degraded-rate-pct {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_degraded_rate_pct}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_out}}

parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction.py --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path}} --compacted-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_path}} --keep-recent {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_recent}} --keep-mid-span {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_mid_span}} --keep-mid-every {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_mid_every}} --keep-old-every {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_old_every}} --min-raw-for-dropped-check {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_min_raw}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_out}}

parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.py --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path}} --compacted-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_path}} --last {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_last}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_out}}

parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.py --compaction-window-json {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_out}} --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_out}}

parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.py --compaction-window-json {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_out}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_out}}

parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat.py --digest-json {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_digest_json}} --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_out}}

parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat.py --digest-json {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_digest_json}} --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_out}}

parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-window:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_window.py --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path}} --last {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window}} --max-failed {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_failed}} --max-failed-rate-pct {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_failed_rate_pct}} --max-degraded {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_degraded}} --max-degraded-rate-pct {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_degraded_rate_pct}} --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_out}}

parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-window:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_window.py --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path}} --last {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window}} --max-failed {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_failed}} --max-failed-rate-pct {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_failed_rate_pct}} --max-degraded {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_degraded}} --max-degraded-rate-pct {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_degraded_rate_pct}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_out}}

parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction.py --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path}} --compacted-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_path}} --keep-recent {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_recent}} --keep-mid-span {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_mid_span}} --keep-mid-every {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_mid_every}} --keep-old-every {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_old_every}} --min-raw-for-dropped-check {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_min_raw}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_out}}

parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.py --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path}} --compacted-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_path}} --last {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_last}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_out}}

parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.py --compaction-window-json {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_out}} --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_out}}

parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.py --compaction-window-json {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_out}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_out}}

parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat.py --digest-json {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_digest_json}} --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_out}}

parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat.py --digest-json {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_digest_json}} --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_out}}

parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-window:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_window.py --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path}} --last {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window}} --max-failed {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_failed}} --max-failed-rate-pct {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_failed_rate_pct}} --max-degraded {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_degraded}} --max-degraded-rate-pct {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_degraded_rate_pct}} --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_out}}

parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-window:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_window.py --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path}} --last {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window}} --max-failed {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_failed}} --max-failed-rate-pct {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_failed_rate_pct}} --max-degraded {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_degraded}} --max-degraded-rate-pct {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_degraded_rate_pct}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_out}}

parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction.py --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path}} --compacted-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_path}} --keep-recent {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_recent}} --keep-mid-span {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_mid_span}} --keep-mid-every {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_mid_every}} --keep-old-every {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_old_every}} --min-raw-for-dropped-check {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_min_raw}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_out}}

parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.py --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path}} --compacted-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_path}} --last {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_last}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_out}}

parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.py --compaction-window-json {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_out}} --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_out}}

parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.py --compaction-window-json {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_out}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_out}}

parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat.py --digest-json {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_digest_json}} --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_out}}

parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat.py --digest-json {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_digest_json}} --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_out}}

parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-window:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_window.py --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path}} --last {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window}} --max-failed {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_failed}} --max-failed-rate-pct {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_failed_rate_pct}} --max-degraded {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_degraded}} --max-degraded-rate-pct {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_degraded_rate_pct}} --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_out}}

parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-window:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_window.py --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path}} --last {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window}} --max-failed {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_failed}} --max-failed-rate-pct {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_failed_rate_pct}} --max-degraded {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_degraded}} --max-degraded-rate-pct {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_max_degraded_rate_pct}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_window_out}}

parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_ai_ops_214_heartbeat_compaction.py --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path}} --compacted-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_path}} --keep-recent {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_recent}} --keep-mid-span {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_mid_span}} --keep-mid-every {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_mid_every}} --keep-old-every {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_old_every}} --min-raw-for-dropped-check {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_min_raw}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_out}}

parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_ai_ops_214_heartbeat_compaction_window.py --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_path}} --compacted-jsonl {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_path}} --last {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_last}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_digest_heartbeat_compact_window_out}}

parl-report-sanction-procedural-official-review-packet-fix-queue-ai-ops-215-digest:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_ai_ops_215_digest.py --compaction-window-json {{sanction_procedural_official_review_packet_fix_queue_ai_ops_215_digest_in}} --out {{sanction_procedural_official_review_packet_fix_queue_ai_ops_215_digest_out}}

parl-check-sanction-procedural-official-review-packet-fix-queue-ai-ops-215-digest:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_ai_ops_215_digest.py --compaction-window-json {{sanction_procedural_official_review_packet_fix_queue_ai_ops_215_digest_in}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_ai_ops_215_digest_out}}

parl-report-sanction-procedural-official-review-packet-fix-queue-ai-ops-216-digest-heartbeat:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_ai_ops_216_digest_heartbeat.py --digest-json {{sanction_procedural_official_review_packet_fix_queue_ai_ops_216_digest_heartbeat_digest_json}} --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_ai_ops_216_digest_heartbeat_path}} --out {{sanction_procedural_official_review_packet_fix_queue_ai_ops_216_digest_heartbeat_out}}

parl-check-sanction-procedural-official-review-packet-fix-queue-ai-ops-216-digest-heartbeat:
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_packet_fix_queue_ai_ops_216_digest_heartbeat.py --digest-json {{sanction_procedural_official_review_packet_fix_queue_ai_ops_216_digest_heartbeat_digest_json}} --heartbeat-jsonl {{sanction_procedural_official_review_packet_fix_queue_ai_ops_216_digest_heartbeat_path}} --strict --out {{sanction_procedural_official_review_packet_fix_queue_ai_ops_216_digest_heartbeat_out}}

parl-run-sanction-procedural-official-review-ready-packets-cycle:
  period_args=""; \
  if [ -n "{{sanction_procedural_official_review_ready_packets_cycle_period_date}}" ]; then \
    period_args="${period_args} --period-date {{sanction_procedural_official_review_ready_packets_cycle_period_date}}"; \
  fi; \
  if [ -n "{{sanction_procedural_official_review_ready_packets_cycle_period_granularity}}" ]; then \
    period_args="${period_args} --period-granularity {{sanction_procedural_official_review_ready_packets_cycle_period_granularity}}"; \
  fi; \
  include_ready_arg=""; \
  if [ "{{sanction_procedural_official_review_ready_packets_cycle_include_ready}}" = "1" ]; then \
    include_ready_arg=" --include-ready"; \
  fi; \
  strict_actionable_arg=""; \
  if [ "{{sanction_procedural_official_review_ready_packets_cycle_strict_actionable}}" = "1" ]; then \
    strict_actionable_arg=" --strict-actionable"; \
  fi; \
  strict_min_ready_arg=""; \
  if [ "{{sanction_procedural_official_review_ready_packets_cycle_strict_min_ready}}" = "1" ]; then \
    strict_min_ready_arg=" --strict-min-ready"; \
  fi; \
  strict_raw_arg=""; \
  if [ "{{sanction_procedural_official_review_ready_packets_cycle_strict_raw}}" = "1" ]; then \
    strict_raw_arg=" --strict-raw"; \
  fi; \
  strict_prepare_arg=""; \
  if [ "{{sanction_procedural_official_review_ready_packets_cycle_strict_prepare}}" = "1" ]; then \
    strict_prepare_arg=" --strict-prepare"; \
  fi; \
  strict_readiness_arg=""; \
  if [ "{{sanction_procedural_official_review_ready_packets_cycle_strict_readiness}}" = "1" ]; then \
    strict_readiness_arg=" --strict-readiness"; \
  fi; \
  PYTHONPATH=. python3 scripts/run_sanction_procedural_official_review_ready_packets_cycle.py --db {{db_path}} --packets-dir {{sanction_procedural_official_review_ready_packets_cycle_packets_dir}} --source-id {{sanction_procedural_official_review_ready_packets_cycle_source_id}} --queue-limit {{sanction_procedural_official_review_ready_packets_cycle_queue_limit}} --statuses "{{sanction_procedural_official_review_ready_packets_cycle_statuses}}" --min-ready-packets {{sanction_procedural_official_review_ready_packets_cycle_min_ready_packets}} --raw-in-out {{sanction_procedural_official_review_ready_packets_cycle_raw_in_out}} --progress-out {{sanction_procedural_official_review_ready_packets_cycle_progress_out}} --cycle-out {{sanction_procedural_official_review_ready_packets_cycle_cycle_out}} --snapshot-date {{snapshot_date}} --readiness-tolerance {{sanction_procedural_official_review_readiness_tolerance}} --readiness-queue-limit {{sanction_procedural_official_review_readiness_queue_limit}} --status-queue-limit {{sanction_procedural_official_review_status_queue_limit}} --out {{sanction_procedural_official_review_ready_packets_cycle_out}}${period_args}${include_ready_arg}${strict_actionable_arg}${strict_min_ready_arg}${strict_raw_arg}${strict_prepare_arg}${strict_readiness_arg}

parl-run-sanction-procedural-official-review-ready-packets-cycle-dry-run:
  period_args=""; \
  if [ -n "{{sanction_procedural_official_review_ready_packets_cycle_period_date}}" ]; then \
    period_args="${period_args} --period-date {{sanction_procedural_official_review_ready_packets_cycle_period_date}}"; \
  fi; \
  if [ -n "{{sanction_procedural_official_review_ready_packets_cycle_period_granularity}}" ]; then \
    period_args="${period_args} --period-granularity {{sanction_procedural_official_review_ready_packets_cycle_period_granularity}}"; \
  fi; \
  include_ready_arg=""; \
  if [ "{{sanction_procedural_official_review_ready_packets_cycle_include_ready}}" = "1" ]; then \
    include_ready_arg=" --include-ready"; \
  fi; \
  strict_actionable_arg=""; \
  if [ "{{sanction_procedural_official_review_ready_packets_cycle_strict_actionable}}" = "1" ]; then \
    strict_actionable_arg=" --strict-actionable"; \
  fi; \
  strict_min_ready_arg=""; \
  if [ "{{sanction_procedural_official_review_ready_packets_cycle_strict_min_ready}}" = "1" ]; then \
    strict_min_ready_arg=" --strict-min-ready"; \
  fi; \
  strict_raw_arg=""; \
  if [ "{{sanction_procedural_official_review_ready_packets_cycle_strict_raw}}" = "1" ]; then \
    strict_raw_arg=" --strict-raw"; \
  fi; \
  strict_prepare_arg=""; \
  if [ "{{sanction_procedural_official_review_ready_packets_cycle_strict_prepare}}" = "1" ]; then \
    strict_prepare_arg=" --strict-prepare"; \
  fi; \
  strict_readiness_arg=""; \
  if [ "{{sanction_procedural_official_review_ready_packets_cycle_strict_readiness}}" = "1" ]; then \
    strict_readiness_arg=" --strict-readiness"; \
  fi; \
  PYTHONPATH=. python3 scripts/run_sanction_procedural_official_review_ready_packets_cycle.py --db {{db_path}} --packets-dir {{sanction_procedural_official_review_ready_packets_cycle_packets_dir}} --source-id {{sanction_procedural_official_review_ready_packets_cycle_source_id}} --queue-limit {{sanction_procedural_official_review_ready_packets_cycle_queue_limit}} --statuses "{{sanction_procedural_official_review_ready_packets_cycle_statuses}}" --min-ready-packets {{sanction_procedural_official_review_ready_packets_cycle_min_ready_packets}} --raw-in-out {{sanction_procedural_official_review_ready_packets_cycle_raw_in_out}} --progress-out {{sanction_procedural_official_review_ready_packets_cycle_progress_out}} --cycle-out {{sanction_procedural_official_review_ready_packets_cycle_cycle_out}} --snapshot-date {{snapshot_date}} --readiness-tolerance {{sanction_procedural_official_review_readiness_tolerance}} --readiness-queue-limit {{sanction_procedural_official_review_readiness_queue_limit}} --status-queue-limit {{sanction_procedural_official_review_status_queue_limit}} --dry-run --out {{sanction_procedural_official_review_ready_packets_cycle_out}}${period_args}${include_ready_arg}${strict_actionable_arg}${strict_min_ready_arg}${strict_raw_arg}${strict_prepare_arg}${strict_readiness_arg}

parl-run-sanction-procedural-official-review-raw-packets-cycle:
  period_args=""; \
  if [ -n "{{sanction_procedural_official_review_raw_packets_cycle_period_date}}" ]; then \
    period_args="${period_args} --period-date {{sanction_procedural_official_review_raw_packets_cycle_period_date}}"; \
  fi; \
  if [ -n "{{sanction_procedural_official_review_raw_packets_cycle_period_granularity}}" ]; then \
    period_args="${period_args} --period-granularity {{sanction_procedural_official_review_raw_packets_cycle_period_granularity}}"; \
  fi; \
  include_ready_arg=""; \
  if [ "{{sanction_procedural_official_review_raw_packets_cycle_include_ready}}" = "1" ]; then \
    include_ready_arg=" --include-ready"; \
  fi; \
  strict_actionable_arg=""; \
  if [ "{{sanction_procedural_official_review_raw_packets_cycle_strict_actionable}}" = "1" ]; then \
    strict_actionable_arg=" --strict-actionable"; \
  fi; \
  strict_packet_coverage_arg=""; \
  if [ "{{sanction_procedural_official_review_raw_packets_cycle_strict_packet_coverage}}" = "1" ]; then \
    strict_packet_coverage_arg=" --strict-packet-coverage"; \
  fi; \
  strict_raw_arg=""; \
  if [ "{{sanction_procedural_official_review_raw_packets_cycle_strict_raw}}" = "1" ]; then \
    strict_raw_arg=" --strict-raw"; \
  fi; \
  strict_prepare_arg=""; \
  if [ "{{sanction_procedural_official_review_raw_packets_cycle_strict_prepare}}" = "1" ]; then \
    strict_prepare_arg=" --strict-prepare"; \
  fi; \
  strict_readiness_arg=""; \
  if [ "{{sanction_procedural_official_review_raw_packets_cycle_strict_readiness}}" = "1" ]; then \
    strict_readiness_arg=" --strict-readiness"; \
  fi; \
  PYTHONPATH=. python3 scripts/run_sanction_procedural_official_review_raw_packets_cycle.py --db {{db_path}} --packets-dir {{sanction_procedural_official_review_raw_packets_cycle_packets_dir}} --source-id {{sanction_procedural_official_review_raw_packets_cycle_source_id}} --queue-limit {{sanction_procedural_official_review_raw_packets_cycle_queue_limit}} --statuses "{{sanction_procedural_official_review_raw_packets_cycle_statuses}}" --raw-in-out {{sanction_procedural_official_review_raw_packets_cycle_raw_in_out}} --packets-out {{sanction_procedural_official_review_raw_packets_cycle_packets_out}} --cycle-out {{sanction_procedural_official_review_raw_packets_cycle_cycle_out}} --snapshot-date {{snapshot_date}} --readiness-tolerance {{sanction_procedural_official_review_readiness_tolerance}} --readiness-queue-limit {{sanction_procedural_official_review_readiness_queue_limit}} --status-queue-limit {{sanction_procedural_official_review_status_queue_limit}} --out {{sanction_procedural_official_review_raw_packets_cycle_out}}${period_args}${include_ready_arg}${strict_actionable_arg}${strict_packet_coverage_arg}${strict_raw_arg}${strict_prepare_arg}${strict_readiness_arg}

parl-run-sanction-procedural-official-review-raw-packets-cycle-dry-run:
  period_args=""; \
  if [ -n "{{sanction_procedural_official_review_raw_packets_cycle_period_date}}" ]; then \
    period_args="${period_args} --period-date {{sanction_procedural_official_review_raw_packets_cycle_period_date}}"; \
  fi; \
  if [ -n "{{sanction_procedural_official_review_raw_packets_cycle_period_granularity}}" ]; then \
    period_args="${period_args} --period-granularity {{sanction_procedural_official_review_raw_packets_cycle_period_granularity}}"; \
  fi; \
  include_ready_arg=""; \
  if [ "{{sanction_procedural_official_review_raw_packets_cycle_include_ready}}" = "1" ]; then \
    include_ready_arg=" --include-ready"; \
  fi; \
  strict_actionable_arg=""; \
  if [ "{{sanction_procedural_official_review_raw_packets_cycle_strict_actionable}}" = "1" ]; then \
    strict_actionable_arg=" --strict-actionable"; \
  fi; \
  strict_packet_coverage_arg=""; \
  if [ "{{sanction_procedural_official_review_raw_packets_cycle_strict_packet_coverage}}" = "1" ]; then \
    strict_packet_coverage_arg=" --strict-packet-coverage"; \
  fi; \
  strict_raw_arg=""; \
  if [ "{{sanction_procedural_official_review_raw_packets_cycle_strict_raw}}" = "1" ]; then \
    strict_raw_arg=" --strict-raw"; \
  fi; \
  strict_prepare_arg=""; \
  if [ "{{sanction_procedural_official_review_raw_packets_cycle_strict_prepare}}" = "1" ]; then \
    strict_prepare_arg=" --strict-prepare"; \
  fi; \
  strict_readiness_arg=""; \
  if [ "{{sanction_procedural_official_review_raw_packets_cycle_strict_readiness}}" = "1" ]; then \
    strict_readiness_arg=" --strict-readiness"; \
  fi; \
  PYTHONPATH=. python3 scripts/run_sanction_procedural_official_review_raw_packets_cycle.py --db {{db_path}} --packets-dir {{sanction_procedural_official_review_raw_packets_cycle_packets_dir}} --source-id {{sanction_procedural_official_review_raw_packets_cycle_source_id}} --queue-limit {{sanction_procedural_official_review_raw_packets_cycle_queue_limit}} --statuses "{{sanction_procedural_official_review_raw_packets_cycle_statuses}}" --raw-in-out {{sanction_procedural_official_review_raw_packets_cycle_raw_in_out}} --packets-out {{sanction_procedural_official_review_raw_packets_cycle_packets_out}} --cycle-out {{sanction_procedural_official_review_raw_packets_cycle_cycle_out}} --snapshot-date {{snapshot_date}} --readiness-tolerance {{sanction_procedural_official_review_readiness_tolerance}} --readiness-queue-limit {{sanction_procedural_official_review_readiness_queue_limit}} --status-queue-limit {{sanction_procedural_official_review_status_queue_limit}} --dry-run --out {{sanction_procedural_official_review_raw_packets_cycle_out}}${period_args}${include_ready_arg}${strict_actionable_arg}${strict_packet_coverage_arg}${strict_raw_arg}${strict_prepare_arg}${strict_readiness_arg}

parl-run-sanction-procedural-official-review-apply-from-kpi-gap-cycle:
  period_args=""; \
  if [ -n "{{sanction_procedural_official_review_gap_cycle_period_date}}" ]; then \
    period_args="${period_args} --period-date {{sanction_procedural_official_review_gap_cycle_period_date}}"; \
  fi; \
  if [ -n "{{sanction_procedural_official_review_gap_cycle_period_granularity}}" ]; then \
    period_args="${period_args} --period-granularity {{sanction_procedural_official_review_gap_cycle_period_granularity}}"; \
  fi; \
  include_ready_arg=""; \
  if [ "{{sanction_procedural_official_review_gap_cycle_include_ready}}" = "1" ]; then \
    include_ready_arg=" --include-ready"; \
  fi; \
  strict_actionable_arg=""; \
  if [ "{{sanction_procedural_official_review_gap_cycle_strict_actionable}}" = "1" ]; then \
    strict_actionable_arg=" --strict-actionable"; \
  fi; \
  strict_readiness_arg=""; \
  if [ "{{sanction_procedural_official_review_readiness_strict}}" = "1" ]; then \
    strict_readiness_arg=" --strict-readiness"; \
  fi; \
  PYTHONPATH=. python3 scripts/run_sanction_procedural_official_review_apply_from_kpi_gap_cycle.py --db {{db_path}} --statuses "{{sanction_procedural_official_review_gap_cycle_statuses}}" --source-id {{sanction_procedural_official_review_apply_source_id}} --snapshot-date {{snapshot_date}} --queue-limit {{sanction_procedural_official_review_gap_cycle_queue_limit}} --readiness-tolerance {{sanction_procedural_official_review_readiness_tolerance}} --readiness-queue-limit {{sanction_procedural_official_review_readiness_queue_limit}} --readiness-csv-out {{sanction_procedural_official_review_readiness_csv_out}} --readiness-out {{sanction_procedural_official_review_readiness_out}} --status-out {{sanction_procedural_official_review_prepare_cycle_status_out}} --gap-out {{sanction_procedural_official_review_gap_cycle_gap_out}} --apply-out {{sanction_procedural_official_review_gap_cycle_apply_out}} --cycle-out {{sanction_procedural_official_review_gap_cycle_cycle_out}} --out {{sanction_procedural_official_review_gap_cycle_out}}${period_args}${include_ready_arg}${strict_actionable_arg}${strict_readiness_arg}

parl-run-sanction-procedural-official-review-apply-from-kpi-gap-cycle-dry-run:
  period_args=""; \
  if [ -n "{{sanction_procedural_official_review_gap_cycle_period_date}}" ]; then \
    period_args="${period_args} --period-date {{sanction_procedural_official_review_gap_cycle_period_date}}"; \
  fi; \
  if [ -n "{{sanction_procedural_official_review_gap_cycle_period_granularity}}" ]; then \
    period_args="${period_args} --period-granularity {{sanction_procedural_official_review_gap_cycle_period_granularity}}"; \
  fi; \
  include_ready_arg=""; \
  if [ "{{sanction_procedural_official_review_gap_cycle_include_ready}}" = "1" ]; then \
    include_ready_arg=" --include-ready"; \
  fi; \
  strict_actionable_arg=""; \
  if [ "{{sanction_procedural_official_review_gap_cycle_strict_actionable}}" = "1" ]; then \
    strict_actionable_arg=" --strict-actionable"; \
  fi; \
  strict_readiness_arg=""; \
  if [ "{{sanction_procedural_official_review_readiness_strict}}" = "1" ]; then \
    strict_readiness_arg=" --strict-readiness"; \
  fi; \
  PYTHONPATH=. python3 scripts/run_sanction_procedural_official_review_apply_from_kpi_gap_cycle.py --db {{db_path}} --statuses "{{sanction_procedural_official_review_gap_cycle_statuses}}" --source-id {{sanction_procedural_official_review_apply_source_id}} --snapshot-date {{snapshot_date}} --queue-limit {{sanction_procedural_official_review_gap_cycle_queue_limit}} --readiness-tolerance {{sanction_procedural_official_review_readiness_tolerance}} --readiness-queue-limit {{sanction_procedural_official_review_readiness_queue_limit}} --readiness-csv-out {{sanction_procedural_official_review_readiness_csv_out}} --readiness-out {{sanction_procedural_official_review_readiness_out}} --status-out {{sanction_procedural_official_review_prepare_cycle_status_out}} --gap-out {{sanction_procedural_official_review_gap_cycle_gap_out}} --apply-out {{sanction_procedural_official_review_gap_cycle_apply_out}} --cycle-out {{sanction_procedural_official_review_gap_cycle_cycle_out}} --dry-run --out {{sanction_procedural_official_review_gap_cycle_out}}${period_args}${include_ready_arg}${strict_actionable_arg}${strict_readiness_arg}

parl-apply-sanction-procedural-official-review-metrics:
  test -n "{{sanction_procedural_official_review_apply_in}}" || (echo "Set SANCTION_PROCEDURAL_OFFICIAL_REVIEW_APPLY_IN=<csv_path>" && exit 2)
  PYTHONPATH=. python3 scripts/run_sanction_procedural_official_review_apply_cycle.py --db {{db_path}} --in "{{sanction_procedural_official_review_apply_in}}" --source-id {{sanction_procedural_official_review_apply_source_id}} --snapshot-date {{snapshot_date}} --readiness-tolerance {{sanction_procedural_official_review_readiness_tolerance}} --readiness-queue-limit {{sanction_procedural_official_review_readiness_queue_limit}} --readiness-csv-out {{sanction_procedural_official_review_readiness_csv_out}} --readiness-out {{sanction_procedural_official_review_readiness_out}} --strict-readiness --status-out {{sanction_procedural_official_review_apply_cycle_status_out}} --out {{sanction_procedural_official_review_apply_cycle_out}}

parl-apply-sanction-procedural-official-review-metrics-dry-run:
  test -n "{{sanction_procedural_official_review_apply_in}}" || (echo "Set SANCTION_PROCEDURAL_OFFICIAL_REVIEW_APPLY_IN=<csv_path>" && exit 2)
  PYTHONPATH=. python3 scripts/run_sanction_procedural_official_review_apply_cycle.py --db {{db_path}} --in "{{sanction_procedural_official_review_apply_in}}" --source-id {{sanction_procedural_official_review_apply_source_id}} --snapshot-date {{snapshot_date}} --readiness-tolerance {{sanction_procedural_official_review_readiness_tolerance}} --readiness-queue-limit {{sanction_procedural_official_review_readiness_queue_limit}} --readiness-csv-out {{sanction_procedural_official_review_readiness_csv_out}} --readiness-out {{sanction_procedural_official_review_readiness_out}} --strict-readiness --dry-run --status-out {{sanction_procedural_official_review_apply_cycle_status_out}} --out {{sanction_procedural_official_review_apply_cycle_out}}

parl-export-sanction-procedural-official-review-apply-template:
  only_missing_arg=""; \
  if [ "{{sanction_procedural_official_review_template_only_missing}}" = "1" ]; then \
    only_missing_arg=" --only-missing"; \
  fi; \
  PYTHONPATH=. python3 scripts/export_sanction_procedural_official_review_apply_template.py --db {{db_path}} --period-date {{sanction_procedural_official_review_template_period_date}} --period-granularity {{sanction_procedural_official_review_template_period_granularity}} --source-id {{sanction_procedural_official_review_template_source_id}} --out {{sanction_procedural_official_review_template_out}} --summary-out {{sanction_procedural_official_review_template_summary_out}}${only_missing_arg}

parl-export-sanction-procedural-official-review-apply-from-raw:
  test -n "{{sanction_procedural_official_review_raw_in}}" || (echo "Set SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_IN=<csv_path>" && exit 2)
  strict_arg=""; \
  if [ "{{sanction_procedural_official_review_raw_strict}}" = "1" ]; then \
    strict_arg=" --strict"; \
  fi; \
  PYTHONPATH=. python3 scripts/export_sanction_procedural_official_review_apply_from_raw_metrics.py --in "{{sanction_procedural_official_review_raw_in}}" --out {{sanction_procedural_official_review_raw_out}} --rejected-csv-out {{sanction_procedural_official_review_raw_rejected_out}} --out-json {{sanction_procedural_official_review_raw_summary_out}} --default-source-id {{sanction_procedural_official_review_raw_default_source_id}} --default-period-granularity {{sanction_procedural_official_review_raw_default_period_granularity}}${strict_arg}

parl-export-sanction-procedural-official-review-raw-template:
  only_missing_arg=""; \
  if [ "{{sanction_procedural_official_review_raw_template_only_missing}}" = "1" ]; then \
    only_missing_arg=" --only-missing"; \
  fi; \
  PYTHONPATH=. python3 scripts/export_sanction_procedural_official_review_raw_template.py --db {{db_path}} --period-date {{sanction_procedural_official_review_raw_template_period_date}} --period-granularity {{sanction_procedural_official_review_raw_template_period_granularity}} --source-id {{sanction_procedural_official_review_raw_template_source_id}} --out {{sanction_procedural_official_review_raw_template_out}} --summary-out {{sanction_procedural_official_review_raw_template_summary_out}}${only_missing_arg}

parl-run-sanction-procedural-official-review-raw-prepare-apply-cycle:
  test -n "{{sanction_procedural_official_review_raw_in}}" || (echo "Set SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_IN=<csv_path>" && exit 2)
  strict_raw_arg=""; \
  if [ "{{sanction_procedural_official_review_raw_cycle_strict_raw}}" = "1" ]; then \
    strict_raw_arg=" --strict-raw"; \
  fi; \
  strict_prepare_arg=""; \
  if [ "{{sanction_procedural_official_review_prepare_cycle_strict_prepare}}" = "1" ]; then \
    strict_prepare_arg=" --strict-prepare"; \
  fi; \
  PYTHONPATH=. python3 scripts/run_sanction_procedural_official_review_raw_prepare_apply_cycle.py --db {{db_path}} --raw-in "{{sanction_procedural_official_review_raw_in}}" --apply-out {{sanction_procedural_official_review_raw_cycle_apply_out}} --raw-rejected-csv-out {{sanction_procedural_official_review_raw_cycle_raw_rejected_out}} --raw-out-json {{sanction_procedural_official_review_raw_cycle_raw_out}} --default-source-id {{sanction_procedural_official_review_raw_default_source_id}} --default-period-granularity {{sanction_procedural_official_review_raw_default_period_granularity}} --prepare-out {{sanction_procedural_official_review_prepare_out}} --prepare-rejected-csv-out {{sanction_procedural_official_review_prepare_rejected_out}} --prepare-out-json {{sanction_procedural_official_review_prepare_summary_out}} --snapshot-date {{snapshot_date}} --readiness-tolerance {{sanction_procedural_official_review_readiness_tolerance}} --readiness-queue-limit {{sanction_procedural_official_review_readiness_queue_limit}} --readiness-csv-out {{sanction_procedural_official_review_readiness_csv_out}} --readiness-out {{sanction_procedural_official_review_readiness_out}} --strict-readiness --status-out {{sanction_procedural_official_review_prepare_cycle_status_out}} --cycle-out {{sanction_procedural_official_review_raw_cycle_cycle_out}} --out {{sanction_procedural_official_review_raw_cycle_out}}${strict_raw_arg}${strict_prepare_arg}

parl-run-sanction-procedural-official-review-raw-prepare-apply-cycle-dry-run:
  test -n "{{sanction_procedural_official_review_raw_in}}" || (echo "Set SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_IN=<csv_path>" && exit 2)
  strict_raw_arg=""; \
  if [ "{{sanction_procedural_official_review_raw_cycle_strict_raw}}" = "1" ]; then \
    strict_raw_arg=" --strict-raw"; \
  fi; \
  strict_prepare_arg=""; \
  if [ "{{sanction_procedural_official_review_prepare_cycle_strict_prepare}}" = "1" ]; then \
    strict_prepare_arg=" --strict-prepare"; \
  fi; \
  PYTHONPATH=. python3 scripts/run_sanction_procedural_official_review_raw_prepare_apply_cycle.py --db {{db_path}} --raw-in "{{sanction_procedural_official_review_raw_in}}" --apply-out {{sanction_procedural_official_review_raw_cycle_apply_out}} --raw-rejected-csv-out {{sanction_procedural_official_review_raw_cycle_raw_rejected_out}} --raw-out-json {{sanction_procedural_official_review_raw_cycle_raw_out}} --default-source-id {{sanction_procedural_official_review_raw_default_source_id}} --default-period-granularity {{sanction_procedural_official_review_raw_default_period_granularity}} --prepare-out {{sanction_procedural_official_review_prepare_out}} --prepare-rejected-csv-out {{sanction_procedural_official_review_prepare_rejected_out}} --prepare-out-json {{sanction_procedural_official_review_prepare_summary_out}} --snapshot-date {{snapshot_date}} --readiness-tolerance {{sanction_procedural_official_review_readiness_tolerance}} --readiness-queue-limit {{sanction_procedural_official_review_readiness_queue_limit}} --readiness-csv-out {{sanction_procedural_official_review_readiness_csv_out}} --readiness-out {{sanction_procedural_official_review_readiness_out}} --strict-readiness --dry-run --status-out {{sanction_procedural_official_review_prepare_cycle_status_out}} --cycle-out {{sanction_procedural_official_review_raw_cycle_cycle_out}} --out {{sanction_procedural_official_review_raw_cycle_out}}${strict_raw_arg}${strict_prepare_arg}

parl-prepare-sanction-procedural-official-review-apply-input:
  test -n "{{sanction_procedural_official_review_prepare_in}}" || (echo "Set SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PREPARE_IN=<csv_path>" && exit 2)
  strict_arg=""; \
  if [ "{{sanction_procedural_official_review_prepare_strict}}" = "1" ]; then \
    strict_arg=" --strict"; \
  fi; \
  PYTHONPATH=. python3 scripts/prepare_sanction_procedural_official_review_apply_input.py --in "{{sanction_procedural_official_review_prepare_in}}" --out {{sanction_procedural_official_review_prepare_out}} --rejected-csv-out {{sanction_procedural_official_review_prepare_rejected_out}} --out-json {{sanction_procedural_official_review_prepare_summary_out}}${strict_arg}

parl-check-sanction-procedural-official-review-apply-readiness:
  test -n "{{sanction_procedural_official_review_readiness_in}}" || (echo "Set SANCTION_PROCEDURAL_OFFICIAL_REVIEW_READINESS_IN=<csv_path>" && exit 2)
  strict_arg=""; \
  if [ "{{sanction_procedural_official_review_readiness_strict}}" = "1" ]; then \
    strict_arg=" --strict"; \
  fi; \
  PYTHONPATH=. python3 scripts/report_sanction_procedural_official_review_apply_readiness.py --db {{db_path}} --in "{{sanction_procedural_official_review_readiness_in}}" --tolerance {{sanction_procedural_official_review_readiness_tolerance}} --queue-limit {{sanction_procedural_official_review_readiness_queue_limit}} --csv-out {{sanction_procedural_official_review_readiness_csv_out}} --out {{sanction_procedural_official_review_readiness_out}}${strict_arg}

parl-run-sanction-procedural-official-review-prepare-apply-cycle:
  test -n "{{sanction_procedural_official_review_prepare_in}}" || (echo "Set SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PREPARE_IN=<csv_path>" && exit 2)
  strict_prepare_arg=""; \
  if [ "{{sanction_procedural_official_review_prepare_cycle_strict_prepare}}" = "1" ]; then \
    strict_prepare_arg=" --strict-prepare"; \
  fi; \
  PYTHONPATH=. python3 scripts/run_sanction_procedural_official_review_prepare_apply_cycle.py --db {{db_path}} --in "{{sanction_procedural_official_review_prepare_in}}" --prepare-out {{sanction_procedural_official_review_prepare_out}} --prepare-rejected-csv-out {{sanction_procedural_official_review_prepare_rejected_out}} --prepare-out-json {{sanction_procedural_official_review_prepare_summary_out}} --source-id {{sanction_procedural_official_review_apply_source_id}} --snapshot-date {{snapshot_date}} --readiness-tolerance {{sanction_procedural_official_review_readiness_tolerance}} --readiness-queue-limit {{sanction_procedural_official_review_readiness_queue_limit}} --readiness-csv-out {{sanction_procedural_official_review_readiness_csv_out}} --readiness-out {{sanction_procedural_official_review_readiness_out}} --strict-readiness --status-out {{sanction_procedural_official_review_prepare_cycle_status_out}} --cycle-out {{sanction_procedural_official_review_prepare_cycle_cycle_out}} --out {{sanction_procedural_official_review_prepare_cycle_out}}${strict_prepare_arg}

parl-run-sanction-procedural-official-review-prepare-apply-cycle-dry-run:
  test -n "{{sanction_procedural_official_review_prepare_in}}" || (echo "Set SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PREPARE_IN=<csv_path>" && exit 2)
  strict_prepare_arg=""; \
  if [ "{{sanction_procedural_official_review_prepare_cycle_strict_prepare}}" = "1" ]; then \
    strict_prepare_arg=" --strict-prepare"; \
  fi; \
  PYTHONPATH=. python3 scripts/run_sanction_procedural_official_review_prepare_apply_cycle.py --db {{db_path}} --in "{{sanction_procedural_official_review_prepare_in}}" --prepare-out {{sanction_procedural_official_review_prepare_out}} --prepare-rejected-csv-out {{sanction_procedural_official_review_prepare_rejected_out}} --prepare-out-json {{sanction_procedural_official_review_prepare_summary_out}} --source-id {{sanction_procedural_official_review_apply_source_id}} --snapshot-date {{snapshot_date}} --readiness-tolerance {{sanction_procedural_official_review_readiness_tolerance}} --readiness-queue-limit {{sanction_procedural_official_review_readiness_queue_limit}} --readiness-csv-out {{sanction_procedural_official_review_readiness_csv_out}} --readiness-out {{sanction_procedural_official_review_readiness_out}} --strict-readiness --dry-run --status-out {{sanction_procedural_official_review_prepare_cycle_status_out}} --cycle-out {{sanction_procedural_official_review_prepare_cycle_cycle_out}} --out {{sanction_procedural_official_review_prepare_cycle_out}}${strict_prepare_arg}

parl-sanction-data-catalog-pipeline:
  just parl-validate-sanction-data-catalog-seed
  just parl-import-sanction-data-catalog-seed
  just parl-report-sanction-data-catalog-status
  just parl-report-sanction-procedural-official-review-status
  just parl-export-sanction-procedural-official-review-kpi-gap-queue
  just parl-export-sanction-procedural-official-review-raw-packets-from-kpi-gap-queue
  just parl-report-sanction-procedural-official-review-raw-packets-progress
  just parl-export-sanction-procedural-official-review-packet-fix-queue
  just parl-run-sanction-procedural-official-review-packet-fix-ready-cycle-dry-run
  just parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat
  just parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction
  just parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-window
  just parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window
  just parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest
  just parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat
  just parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-window
  just parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction
  just parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window
  just parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest
  just parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat
  just parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-window
  just parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction
  just parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window
  just parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest
  just parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat
  just parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-window
  just parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction
  just parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window
  just parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest
  just parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat
  just parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-window
  just parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction
  just parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window
  just parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest
  just parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat
  just parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-window
  just parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction
  just parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window
  just parl-check-sanction-procedural-official-review-packet-fix-queue-ai-ops-215-digest
  just parl-check-sanction-procedural-official-review-packet-fix-queue-ai-ops-216-digest-heartbeat
  just parl-run-sanction-procedural-official-review-ready-packets-cycle-dry-run
  just parl-run-sanction-procedural-official-review-raw-packets-cycle-dry-run
  just parl-export-sanction-procedural-official-review-apply-from-kpi-gap-queue
  just parl-run-sanction-procedural-official-review-apply-from-kpi-gap-cycle-dry-run

parl-sanction-foundation-pipeline:
  just parl-sanction-norms-seed-pipeline
  just parl-sanction-data-catalog-pipeline

parl-test-sanction-data-catalog:
  python3 -m unittest tests/test_validate_sanction_data_catalog_seed.py tests/test_import_sanction_data_catalog_seed.py tests/test_report_sanction_data_catalog_status.py tests/test_report_sanction_procedural_official_review_status.py tests/test_export_sanction_procedural_official_review_kpi_gap_queue.py tests/test_export_sanction_procedural_official_review_raw_packets_from_kpi_gap_queue.py tests/test_report_sanction_procedural_official_review_raw_packets_progress.py tests/test_export_sanction_procedural_official_review_packet_fix_queue.py tests/test_run_sanction_procedural_official_review_packet_fix_ready_cycle.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_window.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_window.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_window.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_window.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_window.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_ai_ops_213_heartbeat_window.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_ai_ops_214_heartbeat_compaction.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_ai_ops_214_heartbeat_compaction_window.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_ai_ops_215_digest.py tests/test_report_sanction_procedural_official_review_packet_fix_queue_ai_ops_216_digest_heartbeat.py tests/test_run_sanction_procedural_official_review_ready_packets_cycle.py tests/test_run_sanction_procedural_official_review_raw_packets_cycle.py tests/test_export_sanction_procedural_official_review_apply_from_kpi_gap_queue.py tests/test_run_sanction_procedural_official_review_apply_from_kpi_gap_cycle.py tests/test_apply_sanction_procedural_official_review_metrics.py tests/test_export_sanction_procedural_official_review_apply_template.py tests/test_export_sanction_procedural_official_review_raw_template.py tests/test_export_sanction_procedural_official_review_apply_from_raw_metrics.py tests/test_prepare_sanction_procedural_official_review_apply_input.py tests/test_report_sanction_procedural_official_review_apply_readiness.py tests/test_run_sanction_procedural_official_review_apply_cycle.py tests/test_run_sanction_procedural_official_review_prepare_apply_cycle.py tests/test_run_sanction_procedural_official_review_raw_prepare_apply_cycle.py

parl-validate-sanction-volume-pilot-seed:
  PYTHONPATH=. python3 scripts/validate_sanction_volume_pilot_seed.py --seed {{sanction_volume_pilot_seed}} --out {{sanction_volume_pilot_validate_out}}

parl-import-sanction-volume-pilot-seed:
  PYTHONPATH=. python3 scripts/import_sanction_volume_pilot_seed.py --db {{db_path}} --seed {{sanction_volume_pilot_seed}} --snapshot-date {{snapshot_date}} --source-id {{sanction_volume_pilot_source_id}} --out {{sanction_volume_pilot_import_out}}

parl-report-sanction-volume-pilot-status:
  PYTHONPATH=. python3 scripts/report_sanction_volume_pilot_status.py --db {{db_path}} --top-n {{sanction_volume_pilot_status_top_n}} --dossier-limit {{sanction_volume_pilot_status_dossier_limit}} --sample-limit {{sanction_volume_pilot_status_sample_limit}} --out {{sanction_volume_pilot_status_out}}

parl-sanction-volume-pilot-pipeline:
  just parl-validate-sanction-volume-pilot-seed
  just parl-import-sanction-volume-pilot-seed
  just parl-report-sanction-volume-pilot-status

parl-sanction-citizen-pilot-pipeline:
  just parl-sanction-foundation-pipeline
  just parl-sanction-volume-pilot-pipeline

parl-test-sanction-volume-pilot:
  python3 -m unittest tests/test_validate_sanction_volume_pilot_seed.py tests/test_import_sanction_volume_pilot_seed.py tests/test_report_sanction_volume_pilot_status.py

parl-validate-liberty-restrictions-seed:
  PYTHONPATH=. python3 scripts/validate_liberty_restrictions_seed.py --seed {{liberty_restrictions_seed}} --out {{liberty_restrictions_validate_out}}

parl-import-liberty-restrictions-seed:
  PYTHONPATH=. python3 scripts/import_liberty_restrictions_seed.py --db {{db_path}} --seed {{liberty_restrictions_seed}} --snapshot-date {{snapshot_date}} --source-id {{liberty_restrictions_source_id}} --out {{liberty_restrictions_import_out}}

parl-report-liberty-restrictions-status:
  PYTHONPATH=. python3 scripts/report_liberty_restrictions_status.py --db {{db_path}} --top-n {{liberty_restrictions_status_top_n}} --norms-classified-min {{liberty_restrictions_norms_classified_min}} --fragments-irlc-min {{liberty_restrictions_fragments_irlc_min}} --fragments-accountability-min {{liberty_restrictions_fragments_accountability_min}} --rights-with-data-min {{liberty_restrictions_rights_with_data_min}} --sources-with-assessments-min-pct {{liberty_restrictions_sources_with_assessments_min_pct}} --scopes-with-assessments-min-pct {{liberty_restrictions_scopes_with_assessments_min_pct}} --min-assessment-sources {{liberty_restrictions_min_assessment_sources}} --min-assessment-scopes {{liberty_restrictions_min_assessment_scopes}} --sources-with-dual-coverage-min-pct {{liberty_restrictions_sources_with_dual_coverage_min_pct}} --scopes-with-dual-coverage-min-pct {{liberty_restrictions_scopes_with_dual_coverage_min_pct}} --min-dual-coverage-sources {{liberty_restrictions_min_dual_coverage_sources}} --min-dual-coverage-scopes {{liberty_restrictions_min_dual_coverage_scopes}} --accountability-primary-evidence-min-pct {{liberty_restrictions_accountability_primary_evidence_min_pct}} --min-accountability-primary-evidence-edges {{liberty_restrictions_min_accountability_primary_evidence_edges}} --out {{liberty_restrictions_status_out}}

parl-check-liberty-focus-gate:
  PYTHONPATH=. python3 scripts/report_liberty_restrictions_status.py --db {{db_path}} --top-n {{liberty_restrictions_status_top_n}} --norms-classified-min {{liberty_restrictions_norms_classified_min}} --fragments-irlc-min {{liberty_restrictions_fragments_irlc_min}} --fragments-accountability-min {{liberty_restrictions_fragments_accountability_min}} --rights-with-data-min {{liberty_restrictions_rights_with_data_min}} --sources-with-assessments-min-pct {{liberty_restrictions_sources_with_assessments_min_pct}} --scopes-with-assessments-min-pct {{liberty_restrictions_scopes_with_assessments_min_pct}} --min-assessment-sources {{liberty_restrictions_min_assessment_sources}} --min-assessment-scopes {{liberty_restrictions_min_assessment_scopes}} --sources-with-dual-coverage-min-pct {{liberty_restrictions_sources_with_dual_coverage_min_pct}} --scopes-with-dual-coverage-min-pct {{liberty_restrictions_scopes_with_dual_coverage_min_pct}} --min-dual-coverage-sources {{liberty_restrictions_min_dual_coverage_sources}} --min-dual-coverage-scopes {{liberty_restrictions_min_dual_coverage_scopes}} --accountability-primary-evidence-min-pct {{liberty_restrictions_accountability_primary_evidence_min_pct}} --min-accountability-primary-evidence-edges {{liberty_restrictions_min_accountability_primary_evidence_edges}} --enforce-gate --out {{liberty_restrictions_status_out}}

parl-report-liberty-focus-scope:
  PYTHONPATH=. python3 scripts/report_liberty_focus_scope_guard.py --status-json {{liberty_restrictions_status_out}} --changed-paths-file {{liberty_focus_scope_changed_paths}} --out {{liberty_focus_scope_out}}

parl-check-liberty-focus-scope:
  PYTHONPATH=. python3 scripts/report_liberty_focus_scope_guard.py --status-json {{liberty_restrictions_status_out}} --changed-paths-file {{liberty_focus_scope_changed_paths}} --strict --out {{liberty_focus_scope_out}}

parl-report-liberty-restrictions-status-heartbeat:
  PYTHONPATH=. python3 scripts/report_liberty_restrictions_status_heartbeat.py --status-json {{liberty_restrictions_status_out}} --heartbeat-jsonl {{liberty_restrictions_status_heartbeat_path}} --strict --out {{liberty_restrictions_status_heartbeat_out}}

parl-check-liberty-restrictions-status-heartbeat-window:
  PYTHONPATH=. python3 scripts/report_liberty_restrictions_status_heartbeat_window.py --heartbeat-jsonl {{liberty_restrictions_status_heartbeat_path}} --last {{liberty_restrictions_status_heartbeat_window}} --max-failed {{liberty_restrictions_status_heartbeat_max_failed}} --max-failed-rate-pct {{liberty_restrictions_status_heartbeat_max_failed_rate_pct}} --max-focus-gate-failed {{liberty_restrictions_status_heartbeat_max_focus_gate_failed}} --max-focus-gate-failed-rate-pct {{liberty_restrictions_status_heartbeat_max_focus_gate_failed_rate_pct}} --max-norms-classified-gate-failed {{liberty_restrictions_status_heartbeat_max_norms_classified_gate_failed}} --max-fragments-irlc-gate-failed {{liberty_restrictions_status_heartbeat_max_fragments_irlc_gate_failed}} --max-fragments-accountability-gate-failed {{liberty_restrictions_status_heartbeat_max_fragments_accountability_gate_failed}} --max-rights-with-data-gate-failed {{liberty_restrictions_status_heartbeat_max_rights_with_data_gate_failed}} --max-source-representativity-gate-failed {{liberty_restrictions_status_heartbeat_max_source_representativity_gate_failed}} --max-scope-representativity-gate-failed {{liberty_restrictions_status_heartbeat_max_scope_representativity_gate_failed}} --max-source-dual-coverage-gate-failed {{liberty_restrictions_status_heartbeat_max_source_dual_coverage_gate_failed}} --max-scope-dual-coverage-gate-failed {{liberty_restrictions_status_heartbeat_max_scope_dual_coverage_gate_failed}} --max-accountability-primary-evidence-gate-failed {{liberty_restrictions_status_heartbeat_max_accountability_primary_evidence_gate_failed}} --strict --out {{liberty_restrictions_status_heartbeat_window_out}}

parl-validate-liberty-proportionality-seed:
  PYTHONPATH=. python3 scripts/validate_liberty_proportionality_seed.py --seed {{liberty_proportionality_seed}} --out {{liberty_proportionality_validate_out}}

parl-import-liberty-proportionality-seed:
  PYTHONPATH=. python3 scripts/import_liberty_proportionality_seed.py --db {{db_path}} --seed {{liberty_proportionality_seed}} --snapshot-date {{snapshot_date}} --source-id {{liberty_proportionality_source_id}} --out {{liberty_proportionality_import_out}}

parl-report-liberty-proportionality-status:
  PYTHONPATH=. python3 scripts/report_liberty_proportionality_status.py --db {{db_path}} --low-score-threshold {{liberty_proportionality_low_score_threshold}} --target-coverage-min {{liberty_proportionality_target_coverage_min}} --objective-defined-min {{liberty_proportionality_objective_defined_min}} --indicator-defined-min {{liberty_proportionality_indicator_defined_min}} --alternatives-considered-min {{liberty_proportionality_alternatives_min}} --out {{liberty_proportionality_status_out}}

parl-check-liberty-proportionality-gate:
  PYTHONPATH=. python3 scripts/report_liberty_proportionality_status.py --db {{db_path}} --low-score-threshold {{liberty_proportionality_low_score_threshold}} --target-coverage-min {{liberty_proportionality_target_coverage_min}} --objective-defined-min {{liberty_proportionality_objective_defined_min}} --indicator-defined-min {{liberty_proportionality_indicator_defined_min}} --alternatives-considered-min {{liberty_proportionality_alternatives_min}} --enforce-gate --out {{liberty_proportionality_status_out}}

parl-report-liberty-direct-accountability-scores:
  PYTHONPATH=. python3 scripts/report_liberty_direct_accountability_scores.py --db {{db_path}} --top-n {{liberty_direct_accountability_top_n}} --direct-coverage-min {{liberty_direct_accountability_coverage_min}} --direct-primary-evidence-min-pct {{liberty_direct_accountability_primary_evidence_min_pct}} --min-direct-primary-evidence-edges {{liberty_direct_accountability_min_primary_evidence_edges}} --out {{liberty_direct_accountability_scores_out}}

parl-check-liberty-direct-accountability-gate:
  PYTHONPATH=. python3 scripts/report_liberty_direct_accountability_scores.py --db {{db_path}} --top-n {{liberty_direct_accountability_top_n}} --direct-coverage-min {{liberty_direct_accountability_coverage_min}} --direct-primary-evidence-min-pct {{liberty_direct_accountability_primary_evidence_min_pct}} --min-direct-primary-evidence-edges {{liberty_direct_accountability_min_primary_evidence_edges}} --enforce-gate --out {{liberty_direct_accountability_scores_out}}

parl-report-liberty-personal-accountability-scores:
  PYTHONPATH=. python3 scripts/report_liberty_personal_accountability_scores.py --db {{db_path}} --top-n {{liberty_personal_accountability_top_n}} --personal-confidence-min {{liberty_personal_confidence_min}} --personal-max-causal-distance {{liberty_personal_max_distance}} --personal-fragment-coverage-min {{liberty_personal_fragment_coverage_min}} --personal-primary-evidence-min-pct {{liberty_personal_primary_evidence_min_pct}} --min-personal-primary-evidence-edges {{liberty_personal_min_primary_evidence_edges}} --indirect-person-window-min-pct {{liberty_personal_indirect_window_min_pct}} --min-indirect-person-window-edges {{liberty_personal_min_indirect_window_edges}} --indirect-identity-resolution-min-pct {{liberty_personal_indirect_identity_resolution_min_pct}} --min-indirect-identity-resolution-edges {{liberty_personal_min_indirect_identity_resolution_edges}} --indirect-non-manual-alias-resolution-min-pct {{liberty_personal_indirect_non_manual_alias_resolution_min_pct}} --min-indirect-non-manual-alias-resolution-edges {{liberty_personal_min_indirect_non_manual_alias_resolution_edges}} --manual-alias-share-max {{liberty_personal_manual_alias_share_max}} --min-alias-rows-for-manual-share-gate {{liberty_personal_min_alias_rows_for_manual_share_gate}} --official-alias-share-min-pct {{liberty_personal_official_alias_share_min_pct}} --min-alias-rows-for-official-share-gate {{liberty_personal_min_alias_rows_for_official_share_gate}} --official-alias-evidence-min-pct {{liberty_personal_official_alias_evidence_min_pct}} --min-official-alias-rows-for-evidence-gate {{liberty_personal_min_official_alias_rows_for_evidence_gate}} --official-alias-source-record-min-pct {{liberty_personal_official_alias_source_record_min_pct}} --min-official-alias-rows-for-source-record-gate {{liberty_personal_min_official_alias_rows_for_source_record_gate}} --min-persons-scored {{liberty_personal_min_persons_scored}} --out {{liberty_personal_accountability_scores_out}}

parl-check-liberty-personal-accountability-gate:
  PYTHONPATH=. python3 scripts/report_liberty_personal_accountability_scores.py --db {{db_path}} --top-n {{liberty_personal_accountability_top_n}} --personal-confidence-min {{liberty_personal_confidence_min}} --personal-max-causal-distance {{liberty_personal_max_distance}} --personal-fragment-coverage-min {{liberty_personal_fragment_coverage_min}} --personal-primary-evidence-min-pct {{liberty_personal_primary_evidence_min_pct}} --min-personal-primary-evidence-edges {{liberty_personal_min_primary_evidence_edges}} --indirect-person-window-min-pct {{liberty_personal_indirect_window_min_pct}} --min-indirect-person-window-edges {{liberty_personal_min_indirect_window_edges}} --indirect-identity-resolution-min-pct {{liberty_personal_indirect_identity_resolution_min_pct}} --min-indirect-identity-resolution-edges {{liberty_personal_min_indirect_identity_resolution_edges}} --indirect-non-manual-alias-resolution-min-pct {{liberty_personal_indirect_non_manual_alias_resolution_min_pct}} --min-indirect-non-manual-alias-resolution-edges {{liberty_personal_min_indirect_non_manual_alias_resolution_edges}} --manual-alias-share-max {{liberty_personal_manual_alias_share_max}} --min-alias-rows-for-manual-share-gate {{liberty_personal_min_alias_rows_for_manual_share_gate}} --official-alias-share-min-pct {{liberty_personal_official_alias_share_min_pct}} --min-alias-rows-for-official-share-gate {{liberty_personal_min_alias_rows_for_official_share_gate}} --official-alias-evidence-min-pct {{liberty_personal_official_alias_evidence_min_pct}} --min-official-alias-rows-for-evidence-gate {{liberty_personal_min_official_alias_rows_for_evidence_gate}} --official-alias-source-record-min-pct {{liberty_personal_official_alias_source_record_min_pct}} --min-official-alias-rows-for-source-record-gate {{liberty_personal_min_official_alias_rows_for_source_record_gate}} --min-persons-scored {{liberty_personal_min_persons_scored}} --enforce-gate --out {{liberty_personal_accountability_scores_out}}

parl-validate-liberty-person-identity-seed:
  PYTHONPATH=. python3 scripts/validate_liberty_person_identity_resolution_seed.py --seed {{liberty_person_identity_seed}} --out {{liberty_person_identity_validate_out}}

parl-import-liberty-person-identity-seed:
  PYTHONPATH=. python3 scripts/import_liberty_person_identity_resolution_seed.py --db {{db_path}} --seed {{liberty_person_identity_seed}} --snapshot-date {{snapshot_date}} --source-id {{liberty_person_identity_source_id}} --out {{liberty_person_identity_import_out}}

parl-report-liberty-person-identity-resolution-queue:
  PYTHONPATH=. python3 scripts/report_liberty_person_identity_resolution_queue.py --db {{db_path}} --personal-confidence-min {{liberty_personal_confidence_min}} --personal-max-causal-distance {{liberty_personal_max_distance}} --identity-resolution-min-pct {{liberty_person_identity_resolution_min_pct}} --min-indirect-person-edges {{liberty_person_identity_resolution_min_edges}} --non-manual-alias-resolution-min-pct {{liberty_person_identity_non_manual_alias_resolution_min_pct}} --min-non-manual-alias-resolution-edges {{liberty_person_identity_non_manual_alias_resolution_min_edges}} --manual-alias-share-max {{liberty_person_identity_manual_alias_share_max}} --min-alias-rows-for-manual-share-gate {{liberty_person_identity_min_alias_rows_for_manual_share_gate}} --official-alias-share-min-pct {{liberty_person_identity_official_alias_share_min_pct}} --min-alias-rows-for-official-share-gate {{liberty_person_identity_min_alias_rows_for_official_share_gate}} --official-alias-evidence-min-pct {{liberty_person_identity_official_alias_evidence_min_pct}} --min-official-alias-rows-for-evidence-gate {{liberty_person_identity_min_official_alias_rows_for_evidence_gate}} --official-alias-source-record-min-pct {{liberty_person_identity_official_alias_source_record_min_pct}} --min-official-alias-rows-for-source-record-gate {{liberty_person_identity_min_official_alias_rows_for_source_record_gate}} --limit {{liberty_person_identity_resolution_queue_limit}} --queue-csv-out {{liberty_person_identity_resolution_queue_csv_out}} --manual-alias-upgrade-csv-out {{liberty_person_identity_manual_upgrade_queue_csv_out}} --official-alias-evidence-upgrade-csv-out {{liberty_person_identity_official_evidence_upgrade_queue_csv_out}} --official-alias-source-record-upgrade-csv-out {{liberty_person_identity_official_source_record_upgrade_queue_csv_out}} --out {{liberty_person_identity_resolution_queue_out}}

parl-check-liberty-person-identity-resolution-gate:
  PYTHONPATH=. python3 scripts/report_liberty_person_identity_resolution_queue.py --db {{db_path}} --personal-confidence-min {{liberty_personal_confidence_min}} --personal-max-causal-distance {{liberty_personal_max_distance}} --identity-resolution-min-pct {{liberty_person_identity_resolution_min_pct}} --min-indirect-person-edges {{liberty_person_identity_resolution_min_edges}} --non-manual-alias-resolution-min-pct {{liberty_person_identity_non_manual_alias_resolution_min_pct}} --min-non-manual-alias-resolution-edges {{liberty_person_identity_non_manual_alias_resolution_min_edges}} --manual-alias-share-max {{liberty_person_identity_manual_alias_share_max}} --min-alias-rows-for-manual-share-gate {{liberty_person_identity_min_alias_rows_for_manual_share_gate}} --official-alias-share-min-pct {{liberty_person_identity_official_alias_share_min_pct}} --min-alias-rows-for-official-share-gate {{liberty_person_identity_min_alias_rows_for_official_share_gate}} --official-alias-evidence-min-pct {{liberty_person_identity_official_alias_evidence_min_pct}} --min-official-alias-rows-for-evidence-gate {{liberty_person_identity_min_official_alias_rows_for_evidence_gate}} --official-alias-source-record-min-pct {{liberty_person_identity_official_alias_source_record_min_pct}} --min-official-alias-rows-for-source-record-gate {{liberty_person_identity_min_official_alias_rows_for_source_record_gate}} --limit {{liberty_person_identity_resolution_queue_limit}} --queue-csv-out {{liberty_person_identity_resolution_queue_csv_out}} --manual-alias-upgrade-csv-out {{liberty_person_identity_manual_upgrade_queue_csv_out}} --official-alias-evidence-upgrade-csv-out {{liberty_person_identity_official_evidence_upgrade_queue_csv_out}} --official-alias-source-record-upgrade-csv-out {{liberty_person_identity_official_source_record_upgrade_queue_csv_out}} --enforce-gate --out {{liberty_person_identity_resolution_queue_out}}

parl-export-liberty-person-identity-official-upgrade-review-queue:
  PYTHONPATH=. python3 scripts/export_liberty_person_identity_official_upgrade_review_queue.py --db {{db_path}} --seed {{liberty_person_identity_seed}} --personal-confidence-min {{liberty_personal_confidence_min}} --personal-max-causal-distance {{liberty_personal_max_distance}} --limit {{liberty_person_identity_resolution_queue_limit}} --out {{liberty_person_identity_official_upgrade_review_queue_out}} --summary-out {{liberty_person_identity_official_upgrade_review_queue_summary_out}}

parl-export-liberty-person-identity-official-upgrade-review-queue-actionable:
  PYTHONPATH=. python3 scripts/export_liberty_person_identity_official_upgrade_review_queue.py --db {{db_path}} --seed {{liberty_person_identity_seed}} --personal-confidence-min {{liberty_personal_confidence_min}} --personal-max-causal-distance {{liberty_personal_max_distance}} --limit {{liberty_person_identity_resolution_queue_limit}} --only-actionable --out {{liberty_person_identity_official_upgrade_review_queue_actionable_out}} --summary-out {{liberty_person_identity_official_upgrade_review_queue_actionable_summary_out}}

parl-check-liberty-person-identity-official-upgrade-review-queue-actionable-empty:
  PYTHONPATH=. python3 scripts/export_liberty_person_identity_official_upgrade_review_queue.py --db {{db_path}} --seed {{liberty_person_identity_seed}} --personal-confidence-min {{liberty_personal_confidence_min}} --personal-max-causal-distance {{liberty_personal_max_distance}} --limit {{liberty_person_identity_resolution_queue_limit}} --only-actionable --strict-empty-actionable --out {{liberty_person_identity_official_upgrade_review_queue_actionable_out}} --summary-out {{liberty_person_identity_official_upgrade_review_queue_actionable_summary_out}}

parl-report-liberty-person-identity-official-upgrade-review-queue-actionable-heartbeat:
  just parl-export-liberty-person-identity-official-upgrade-review-queue-actionable
  PYTHONPATH=. python3 scripts/report_liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat.py --summary-json {{liberty_person_identity_official_upgrade_review_queue_actionable_summary_out}} --heartbeat-jsonl {{liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_path}} --out {{liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_out}}

parl-check-liberty-person-identity-official-upgrade-review-queue-actionable-heartbeat:
  just parl-export-liberty-person-identity-official-upgrade-review-queue-actionable
  PYTHONPATH=. python3 scripts/report_liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat.py --summary-json {{liberty_person_identity_official_upgrade_review_queue_actionable_summary_out}} --heartbeat-jsonl {{liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_path}} --strict --out {{liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_out}}

parl-check-liberty-person-identity-official-upgrade-review-queue-actionable-heartbeat-window:
  PYTHONPATH=. python3 scripts/report_liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_window.py --heartbeat-jsonl {{liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_path}} --last {{liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_window}} --max-failed {{liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_window_max_failed}} --max-failed-rate-pct {{liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_window_max_failed_rate_pct}} --max-actionable-nonempty-runs {{liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_window_max_actionable_nonempty_runs}} --max-actionable-nonempty-runs-rate-pct {{liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_window_max_actionable_nonempty_runs_rate_pct}} --strict --out {{liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_window_out}}

parl-apply-liberty-person-identity-official-upgrade-reviews:
  PYTHONPATH=. python3 scripts/apply_liberty_person_identity_official_upgrade_reviews.py --seed {{liberty_person_identity_seed}} --in {{liberty_person_identity_official_upgrade_reviews_in}} --db {{db_path}} --seed-out {{liberty_person_identity_seed_review_out}} --out {{liberty_person_identity_official_upgrade_apply_out}}

parl-validate-liberty-enforcement-seed:
  PYTHONPATH=. python3 scripts/validate_liberty_enforcement_seed.py --seed {{liberty_enforcement_seed}} --out {{liberty_enforcement_validate_out}}

parl-import-liberty-enforcement-seed:
  PYTHONPATH=. python3 scripts/import_liberty_enforcement_seed.py --db {{db_path}} --seed {{liberty_enforcement_seed}} --snapshot-date {{snapshot_date}} --source-id {{liberty_enforcement_source_id}} --out {{liberty_enforcement_import_out}}

parl-report-liberty-enforcement-variation-status:
  PYTHONPATH=. python3 scripts/report_liberty_enforcement_variation_status.py --db {{db_path}} --top-n {{liberty_enforcement_top_n}} --sanction-rate-spread-pct-min {{liberty_enforcement_sanction_spread_min}} --annulment-rate-spread-pp-min {{liberty_enforcement_annulment_spread_min}} --delay-spread-days-min {{liberty_enforcement_delay_spread_days_min}} --target-coverage-min {{liberty_enforcement_target_coverage_min}} --multi-territory-coverage-min {{liberty_enforcement_multi_territory_min}} --out {{liberty_enforcement_status_out}}

parl-check-liberty-enforcement-variation-gate:
  PYTHONPATH=. python3 scripts/report_liberty_enforcement_variation_status.py --db {{db_path}} --top-n {{liberty_enforcement_top_n}} --sanction-rate-spread-pct-min {{liberty_enforcement_sanction_spread_min}} --annulment-rate-spread-pp-min {{liberty_enforcement_annulment_spread_min}} --delay-spread-days-min {{liberty_enforcement_delay_spread_days_min}} --target-coverage-min {{liberty_enforcement_target_coverage_min}} --multi-territory-coverage-min {{liberty_enforcement_multi_territory_min}} --enforce-gate --out {{liberty_enforcement_status_out}}

parl-validate-liberty-indirect-accountability-seed:
  PYTHONPATH=. python3 scripts/validate_liberty_indirect_accountability_seed.py --seed {{liberty_indirect_seed}} --out {{liberty_indirect_validate_out}}

parl-import-liberty-indirect-accountability-seed:
  PYTHONPATH=. python3 scripts/import_liberty_indirect_accountability_seed.py --db {{db_path}} --seed {{liberty_indirect_seed}} --snapshot-date {{snapshot_date}} --source-id {{liberty_indirect_source_id}} --out {{liberty_indirect_import_out}}

parl-report-liberty-indirect-accountability-status:
  PYTHONPATH=. python3 scripts/report_liberty_indirect_accountability_status.py --db {{db_path}} --top-n {{liberty_indirect_top_n}} --attributable-confidence-min {{liberty_indirect_confidence_min}} --attributable-max-causal-distance {{liberty_indirect_max_distance}} --attributable-fragment-coverage-min {{liberty_indirect_fragment_coverage_min}} --attributable-person-window-min {{liberty_indirect_person_window_min}} --min-attributable-edges-for-person-window {{liberty_indirect_min_person_window_edges}} --out {{liberty_indirect_status_out}}

parl-check-liberty-indirect-accountability-gate:
  PYTHONPATH=. python3 scripts/report_liberty_indirect_accountability_status.py --db {{db_path}} --top-n {{liberty_indirect_top_n}} --attributable-confidence-min {{liberty_indirect_confidence_min}} --attributable-max-causal-distance {{liberty_indirect_max_distance}} --attributable-fragment-coverage-min {{liberty_indirect_fragment_coverage_min}} --attributable-person-window-min {{liberty_indirect_person_window_min}} --min-attributable-edges-for-person-window {{liberty_indirect_min_person_window_edges}} --enforce-gate --out {{liberty_indirect_status_out}}

parl-validate-liberty-delegated-enforcement-seed:
  PYTHONPATH=. python3 scripts/validate_liberty_delegated_enforcement_seed.py --seed {{liberty_delegated_seed}} --out {{liberty_delegated_validate_out}}

parl-import-liberty-delegated-enforcement-seed:
  PYTHONPATH=. python3 scripts/import_liberty_delegated_enforcement_seed.py --db {{db_path}} --seed {{liberty_delegated_seed}} --snapshot-date {{snapshot_date}} --source-id {{liberty_delegated_source_id}} --out {{liberty_delegated_import_out}}

parl-report-liberty-delegated-enforcement-status:
  PYTHONPATH=. python3 scripts/report_liberty_delegated_enforcement_status.py --db {{db_path}} --top-n {{liberty_delegated_top_n}} --target-fragment-coverage-min {{liberty_delegated_target_coverage_min}} --designated-actor-coverage-min {{liberty_delegated_designated_actor_min}} --enforcement-evidence-coverage-min {{liberty_delegated_enforcement_evidence_min}} --out {{liberty_delegated_status_out}}

parl-check-liberty-delegated-enforcement-gate:
  PYTHONPATH=. python3 scripts/report_liberty_delegated_enforcement_status.py --db {{db_path}} --top-n {{liberty_delegated_top_n}} --target-fragment-coverage-min {{liberty_delegated_target_coverage_min}} --designated-actor-coverage-min {{liberty_delegated_designated_actor_min}} --enforcement-evidence-coverage-min {{liberty_delegated_enforcement_evidence_min}} --enforce-gate --out {{liberty_delegated_status_out}}

parl-report-liberty-delegated-person-window-queue:
  PYTHONPATH=. python3 scripts/report_liberty_delegated_person_window_queue.py --db {{db_path}} --limit {{liberty_delegated_person_queue_limit}} --institution-hint-terms '{{liberty_delegated_person_queue_institution_terms}}' --max-actionable-rows {{liberty_delegated_person_queue_max_actionable_rows}} --queue-csv-out {{liberty_delegated_person_queue_csv_out}} --out {{liberty_delegated_person_queue_out}}

parl-check-liberty-delegated-person-window-queue:
  PYTHONPATH=. python3 scripts/report_liberty_delegated_person_window_queue.py --db {{db_path}} --limit {{liberty_delegated_person_queue_limit}} --institution-hint-terms '{{liberty_delegated_person_queue_institution_terms}}' --max-actionable-rows {{liberty_delegated_person_queue_max_actionable_rows}} --queue-csv-out {{liberty_delegated_person_queue_csv_out}} --strict --out {{liberty_delegated_person_queue_out}}

parl-export-liberty-delegated-person-window-review-queue:
  PYTHONPATH=. python3 scripts/export_liberty_delegated_person_window_review_queue.py --db {{db_path}} --seed {{liberty_delegated_seed}} --limit {{liberty_delegated_review_limit}} --institution-hint-terms '{{liberty_delegated_person_queue_institution_terms}}' --out {{liberty_delegated_review_queue_out}} --summary-out {{liberty_delegated_review_summary_out}}

parl-check-liberty-delegated-person-window-review-queue-actionable-empty:
  PYTHONPATH=. python3 scripts/export_liberty_delegated_person_window_review_queue.py --db {{db_path}} --seed {{liberty_delegated_seed}} --limit {{liberty_delegated_review_limit}} --institution-hint-terms '{{liberty_delegated_person_queue_institution_terms}}' --only-actionable --strict-empty-actionable --out {{liberty_delegated_review_queue_out}} --summary-out {{liberty_delegated_review_summary_out}}

parl-apply-liberty-delegated-person-window-reviews:
  PYTHONPATH=. python3 scripts/apply_liberty_delegated_person_window_reviews.py --seed {{liberty_delegated_seed}} --in {{liberty_delegated_review_in}} --seed-out {{liberty_delegated_review_seed_out}} --out {{liberty_delegated_review_apply_out}}

parl-export-liberty-delegated-person-window-scrape-targets:
  PYTHONPATH=. python3 scripts/export_liberty_delegated_person_window_scrape_targets.py --db {{db_path}} --seed {{liberty_delegated_seed}} --limit {{liberty_delegated_scrape_targets_limit}} --institution-hint-terms '{{liberty_delegated_person_queue_institution_terms}}' --min-priority-score {{liberty_delegated_scrape_targets_min_priority}} --out {{liberty_delegated_scrape_targets_out}} --summary-out {{liberty_delegated_scrape_targets_summary_out}}

parl-check-liberty-delegated-person-window-scrape-targets:
  PYTHONPATH=. python3 scripts/export_liberty_delegated_person_window_scrape_targets.py --db {{db_path}} --seed {{liberty_delegated_seed}} --limit {{liberty_delegated_scrape_targets_limit}} --institution-hint-terms '{{liberty_delegated_person_queue_institution_terms}}' --min-priority-score {{liberty_delegated_scrape_targets_min_priority}} --strict-min-targets {{liberty_delegated_scrape_targets_strict_min_targets}} --out {{liberty_delegated_scrape_targets_out}} --summary-out {{liberty_delegated_scrape_targets_summary_out}}

parl-scrape-liberty-delegated-person-window-boe-candidates:
  PYTHONPATH=. python3 scripts/scrape_liberty_delegated_person_window_boe_candidates.py --targets-csv {{liberty_delegated_boe_candidates_targets_csv}} --top-results-per-target {{liberty_delegated_boe_candidates_top_results}} --timeout {{liberty_delegated_boe_candidates_timeout}} --out {{liberty_delegated_boe_candidates_out}} --summary-out {{liberty_delegated_boe_candidates_summary_out}}

parl-check-liberty-delegated-person-window-boe-candidates:
  PYTHONPATH=. python3 scripts/scrape_liberty_delegated_person_window_boe_candidates.py --targets-csv {{liberty_delegated_boe_candidates_targets_csv}} --top-results-per-target {{liberty_delegated_boe_candidates_top_results}} --timeout {{liberty_delegated_boe_candidates_timeout}} --strict-min-candidates {{liberty_delegated_boe_candidates_strict_min_candidates}} --out {{liberty_delegated_boe_candidates_out}} --summary-out {{liberty_delegated_boe_candidates_summary_out}}

parl-export-liberty-delegated-person-window-review-assist:
  PYTHONPATH=. python3 scripts/export_liberty_delegated_person_window_review_assist_from_boe_candidates.py --review-queue-csv {{liberty_delegated_review_assist_in}} --boe-candidates-csv {{liberty_delegated_review_assist_boe_candidates}} --min-candidate-score {{liberty_delegated_review_assist_min_candidate_score}} --max-candidates-per-link {{liberty_delegated_review_assist_max_candidates_per_link}} --out {{liberty_delegated_review_assist_out}} --summary-out {{liberty_delegated_review_assist_summary_out}}

parl-check-liberty-delegated-person-window-review-assist:
  PYTHONPATH=. python3 scripts/export_liberty_delegated_person_window_review_assist_from_boe_candidates.py --review-queue-csv {{liberty_delegated_review_assist_in}} --boe-candidates-csv {{liberty_delegated_review_assist_boe_candidates}} --min-candidate-score {{liberty_delegated_review_assist_min_candidate_score}} --max-candidates-per-link {{liberty_delegated_review_assist_max_candidates_per_link}} --strict-min-assist-rows {{liberty_delegated_review_assist_strict_min_rows}} --out {{liberty_delegated_review_assist_out}} --summary-out {{liberty_delegated_review_assist_summary_out}}

parl-export-liberty-delegated-person-window-auto-review-decisions:
  PYTHONPATH=. python3 scripts/export_liberty_delegated_person_window_auto_review_decisions.py --review-queue-csv {{liberty_delegated_auto_review_queue_csv}} --review-assist-csv {{liberty_delegated_auto_review_assist_csv}} --min-candidate-score {{liberty_delegated_auto_review_min_candidate_score}} --max-candidates-per-link {{liberty_delegated_auto_review_max_candidates_per_link}} --out {{liberty_delegated_auto_review_out}} --summary-out {{liberty_delegated_auto_review_summary_out}}

parl-check-liberty-delegated-person-window-auto-review-decisions:
  PYTHONPATH=. python3 scripts/export_liberty_delegated_person_window_auto_review_decisions.py --review-queue-csv {{liberty_delegated_auto_review_queue_csv}} --review-assist-csv {{liberty_delegated_auto_review_assist_csv}} --min-candidate-score {{liberty_delegated_auto_review_min_candidate_score}} --max-candidates-per-link {{liberty_delegated_auto_review_max_candidates_per_link}} --strict-min-approved-rows {{liberty_delegated_auto_review_strict_min_approved_rows}} --out {{liberty_delegated_auto_review_out}} --summary-out {{liberty_delegated_auto_review_summary_out}}

parl-export-liberty-delegated-person-window-auto-review-qa-sample:
  PYTHONPATH=. python3 scripts/export_liberty_delegated_person_window_auto_review_qa_sample.py --auto-review-csv {{liberty_delegated_auto_review_out}} --review-assist-csv {{liberty_delegated_auto_review_assist_csv}} --sample-size {{liberty_delegated_auto_review_qa_sample_size}} --out {{liberty_delegated_auto_review_qa_sample_out}} --summary-out {{liberty_delegated_auto_review_qa_summary_out}}

parl-report-liberty-delegated-person-window-auto-review-qa-precision:
  PYTHONPATH=. python3 scripts/report_liberty_delegated_person_window_auto_review_qa_precision.py --qa-csv {{liberty_delegated_auto_review_qa_sample_out}} --decision-scope {{liberty_delegated_auto_review_qa_decision_scope}} --min-reviewed-rows {{liberty_delegated_auto_review_qa_min_reviewed_rows}} --min-precision-pct {{liberty_delegated_auto_review_qa_min_precision_pct}} --out {{liberty_delegated_auto_review_qa_precision_out}}

parl-check-liberty-delegated-person-window-auto-review-qa-precision:
  PYTHONPATH=. python3 scripts/report_liberty_delegated_person_window_auto_review_qa_precision.py --qa-csv {{liberty_delegated_auto_review_qa_sample_out}} --decision-scope {{liberty_delegated_auto_review_qa_decision_scope}} --min-reviewed-rows {{liberty_delegated_auto_review_qa_min_reviewed_rows}} --min-precision-pct {{liberty_delegated_auto_review_qa_min_precision_pct}} --strict --out {{liberty_delegated_auto_review_qa_precision_out}}

parl-report-liberty-delegated-non-nominative-qa-gate:
  PYTHONPATH=. python3 scripts/report_liberty_delegated_non_nominative_qa_gate.py --auto-review-summary {{liberty_delegated_non_nominative_qa_gate_auto_review_summary}} --qa-sample-summary {{liberty_delegated_non_nominative_qa_gate_sample_summary}} --qa-precision-report {{liberty_delegated_non_nominative_qa_gate_precision_report}} --review-note-contains {{liberty_delegated_non_nominative_qa_gate_review_note_contains}} --min-reviewed-rows {{liberty_delegated_non_nominative_qa_gate_min_reviewed_rows}} --min-precision-pct {{liberty_delegated_non_nominative_qa_gate_min_precision_pct}} --out {{liberty_delegated_non_nominative_qa_gate_out}}

parl-check-liberty-delegated-non-nominative-qa-gate:
  PYTHONPATH=. python3 scripts/report_liberty_delegated_non_nominative_qa_gate.py --auto-review-summary {{liberty_delegated_non_nominative_qa_gate_auto_review_summary}} --qa-sample-summary {{liberty_delegated_non_nominative_qa_gate_sample_summary}} --qa-precision-report {{liberty_delegated_non_nominative_qa_gate_precision_report}} --review-note-contains {{liberty_delegated_non_nominative_qa_gate_review_note_contains}} --min-reviewed-rows {{liberty_delegated_non_nominative_qa_gate_min_reviewed_rows}} --min-precision-pct {{liberty_delegated_non_nominative_qa_gate_min_precision_pct}} --strict --out {{liberty_delegated_non_nominative_qa_gate_out}}

parl-export-liberty-delegated-pending-resolution-review-queue:
  PYTHONPATH=. python3 scripts/export_liberty_delegated_pending_resolution_review_queue.py --auto-review-csv {{liberty_delegated_auto_review_out}} --review-assist-csv {{liberty_delegated_auto_review_assist_csv}} --top-candidates-per-link {{liberty_delegated_pending_resolution_top_candidates_per_link}} --out {{liberty_delegated_pending_resolution_queue_out}} --summary-out {{liberty_delegated_pending_resolution_queue_summary_out}}

parl-export-liberty-delegated-alternative-capture-targets:
  PYTHONPATH=. python3 scripts/export_liberty_delegated_alternative_capture_targets.py --pending-resolution-csv {{liberty_delegated_alternative_capture_in}} --max-candidate-doc-targets-per-link {{liberty_delegated_alternative_capture_max_candidate_docs_per_link}} --out {{liberty_delegated_alternative_capture_out}} --summary-out {{liberty_delegated_alternative_capture_summary_out}}

parl-check-liberty-delegated-alternative-capture-targets:
  PYTHONPATH=. python3 scripts/export_liberty_delegated_alternative_capture_targets.py --pending-resolution-csv {{liberty_delegated_alternative_capture_in}} --max-candidate-doc-targets-per-link {{liberty_delegated_alternative_capture_max_candidate_docs_per_link}} --strict-min-targets-per-link {{liberty_delegated_alternative_capture_strict_min_targets_per_link}} --out {{liberty_delegated_alternative_capture_out}} --summary-out {{liberty_delegated_alternative_capture_summary_out}}

parl-scrape-liberty-delegated-alternative-boe-candidates:
  PYTHONPATH=. python3 scripts/scrape_liberty_delegated_alternative_boe_candidates.py --targets-csv {{liberty_delegated_alternative_boe_targets_in}} --top-results-per-query-target {{liberty_delegated_alternative_boe_top_results_per_query_target}} --max-queries-per-query-target {{liberty_delegated_alternative_boe_max_queries_per_query_target}} --timeout {{liberty_delegated_alternative_boe_timeout}} --out {{liberty_delegated_alternative_boe_out}} --summary-out {{liberty_delegated_alternative_boe_summary_out}}

parl-check-liberty-delegated-alternative-boe-candidates:
  PYTHONPATH=. python3 scripts/scrape_liberty_delegated_alternative_boe_candidates.py --targets-csv {{liberty_delegated_alternative_boe_targets_in}} --top-results-per-query-target {{liberty_delegated_alternative_boe_top_results_per_query_target}} --max-queries-per-query-target {{liberty_delegated_alternative_boe_max_queries_per_query_target}} --timeout {{liberty_delegated_alternative_boe_timeout}} --strict-min-candidates {{liberty_delegated_alternative_boe_strict_min_candidates}} --strict-min-links-with-candidates {{liberty_delegated_alternative_boe_strict_min_links_with_candidates}} --out {{liberty_delegated_alternative_boe_out}} --summary-out {{liberty_delegated_alternative_boe_summary_out}}

parl-export-liberty-restrictions-snapshot:
  @set -euo pipefail; \
  prev_arg=""; \
  if [ -n "{{liberty_restrictions_snapshot_prev}}" ]; then prev_arg="--prev-snapshot {{liberty_restrictions_snapshot_prev}}"; fi; \
  docker compose run --rm --build etl "PYTHONPATH=. python3 scripts/export_liberty_restrictions_snapshot.py --db {{db_path}} --snapshot-date {{snapshot_date}} --out {{liberty_restrictions_snapshot_out}} --irlc-parquet-out {{liberty_restrictions_snapshot_irlc_parquet_out}} --accountability-parquet-out {{liberty_restrictions_snapshot_accountability_parquet_out}} --parquet-compression {{liberty_restrictions_snapshot_parquet_compression}} --diff-out {{liberty_restrictions_snapshot_diff_out}} --changelog-jsonl {{liberty_restrictions_snapshot_changelog_jsonl}} --changelog-out {{liberty_restrictions_snapshot_changelog_out}} ${prev_arg}"

parl-publish-liberty-atlas-artifacts:
  @set -euo pipefail; \
  allow_missing_arg=""; \
  gh_pages_arg=""; \
  if [ "{{liberty_atlas_publish_allow_missing}}" = "1" ]; then allow_missing_arg=" --allow-missing"; fi; \
  if [ -n "{{liberty_atlas_publish_gh_pages_out}}" ]; then gh_pages_arg=" --gh-pages-out {{liberty_atlas_publish_gh_pages_out}}"; fi; \
  python3 scripts/publish_liberty_atlas_artifacts.py --snapshot-json {{liberty_atlas_publish_snapshot_json}} --irlc-parquet {{liberty_atlas_publish_irlc_parquet}} --accountability-parquet {{liberty_atlas_publish_accountability_parquet}} --diff-json {{liberty_atlas_publish_diff_json}} --changelog-entry-json {{liberty_atlas_publish_changelog_entry_json}} --changelog-history-jsonl {{liberty_atlas_publish_changelog_history_jsonl}} --snapshot-date {{snapshot_date}} --published-dir {{liberty_atlas_published_dir}} --out {{liberty_atlas_publish_out}}${gh_pages_arg}${allow_missing_arg}

parl-report-liberty-atlas-changelog-continuity:
  python3 scripts/report_liberty_atlas_changelog_continuity.py --changelog-jsonl {{liberty_atlas_publish_changelog_history_jsonl}} --snapshot-date {{snapshot_date}} --release-json {{liberty_atlas_release_latest_json}} --out {{liberty_atlas_changelog_continuity_out}}

parl-check-liberty-atlas-changelog-continuity:
  python3 scripts/report_liberty_atlas_changelog_continuity.py --changelog-jsonl {{liberty_atlas_publish_changelog_history_jsonl}} --snapshot-date {{snapshot_date}} --release-json {{liberty_atlas_release_latest_json}} --strict --out {{liberty_atlas_changelog_continuity_out}}

parl-report-liberty-atlas-release-heartbeat:
  @set -euo pipefail; \
  allow_hf_unavailable_arg=""; \
  expected_snapshot_arg=""; \
  hf_json_arg=""; \
  hf_url_arg=""; \
  hf_repo_arg=""; \
  hf_username_arg=""; \
  if [ "{{liberty_atlas_release_allow_hf_unavailable}}" = "1" ]; then allow_hf_unavailable_arg=" --allow-hf-unavailable"; fi; \
  if [ -n "{{liberty_atlas_release_expected_snapshot_date}}" ]; then expected_snapshot_arg=" --snapshot-date {{liberty_atlas_release_expected_snapshot_date}}"; fi; \
  if [ -n "{{liberty_atlas_release_hf_json}}" ]; then hf_json_arg=" --hf-release-json {{liberty_atlas_release_hf_json}}"; fi; \
  if [ -n "{{liberty_atlas_release_hf_latest_url}}" ]; then hf_url_arg=" --hf-release-json-url {{liberty_atlas_release_hf_latest_url}}"; fi; \
  if [ -n "{{liberty_atlas_release_hf_dataset_repo}}" ]; then hf_repo_arg=" --hf-dataset-repo {{liberty_atlas_release_hf_dataset_repo}}"; fi; \
  if [ -n "{{liberty_atlas_release_hf_username}}" ]; then hf_username_arg=" --hf-username {{liberty_atlas_release_hf_username}}"; fi; \
  python3 scripts/report_liberty_atlas_release_heartbeat.py --published-release-json {{liberty_atlas_release_latest_json}} --gh-pages-release-json {{liberty_atlas_publish_gh_pages_out}} --continuity-json {{liberty_atlas_changelog_continuity_out}} --heartbeat-jsonl {{liberty_atlas_release_heartbeat_path}} --max-snapshot-age-days {{liberty_atlas_release_max_snapshot_age_days}} --hf-timeout {{liberty_atlas_release_hf_timeout}} --strict --out {{liberty_atlas_release_heartbeat_out}}${allow_hf_unavailable_arg}${expected_snapshot_arg}${hf_json_arg}${hf_url_arg}${hf_repo_arg}${hf_username_arg}

parl-check-liberty-atlas-release-heartbeat-window:
  @set -euo pipefail; \
  min_run_at_arg=""; \
  if [ -n "{{liberty_atlas_release_heartbeat_window_min_run_at}}" ]; then min_run_at_arg=" --min-run-at {{liberty_atlas_release_heartbeat_window_min_run_at}}"; fi; \
  python3 scripts/report_liberty_atlas_release_heartbeat_window.py --heartbeat-jsonl {{liberty_atlas_release_heartbeat_path}} --last {{liberty_atlas_release_heartbeat_window}} --max-failed {{liberty_atlas_release_window_max_failed}} --max-degraded {{liberty_atlas_release_window_max_degraded}} --max-stale-alerts {{liberty_atlas_release_window_max_stale_alerts}} --max-drift-alerts {{liberty_atlas_release_window_max_drift_alerts}} --max-hf-unavailable {{liberty_atlas_release_window_max_hf_unavailable}} --strict --out {{liberty_atlas_release_heartbeat_window_out}}${min_run_at_arg}

parl-liberty-restrictions-pipeline:
  just parl-sanction-norms-seed-pipeline
  just parl-validate-liberty-restrictions-seed
  just parl-import-liberty-restrictions-seed
  just parl-report-liberty-restrictions-status
  just parl-report-liberty-restrictions-status-heartbeat
  just parl-check-liberty-restrictions-status-heartbeat-window
  just parl-check-liberty-focus-gate
  just parl-validate-liberty-proportionality-seed
  just parl-import-liberty-proportionality-seed
  just parl-report-liberty-proportionality-status
  just parl-check-liberty-proportionality-gate
  just parl-report-liberty-direct-accountability-scores
  just parl-check-liberty-direct-accountability-gate
  just parl-validate-liberty-enforcement-seed
  just parl-import-liberty-enforcement-seed
  just parl-report-liberty-enforcement-variation-status
  just parl-check-liberty-enforcement-variation-gate
  just parl-validate-liberty-indirect-accountability-seed
  just parl-import-liberty-indirect-accountability-seed
  just parl-report-liberty-indirect-accountability-status
  just parl-check-liberty-indirect-accountability-gate
  just parl-validate-liberty-person-identity-seed
  just parl-import-liberty-person-identity-seed
  just parl-report-liberty-personal-accountability-scores
  just parl-check-liberty-personal-accountability-gate
  just parl-report-liberty-person-identity-resolution-queue
  just parl-check-liberty-person-identity-resolution-gate
  just parl-report-liberty-person-identity-official-upgrade-review-queue-actionable-heartbeat
  just parl-check-liberty-person-identity-official-upgrade-review-queue-actionable-empty
  just parl-check-liberty-person-identity-official-upgrade-review-queue-actionable-heartbeat-window
  just parl-validate-liberty-delegated-enforcement-seed
  just parl-import-liberty-delegated-enforcement-seed
  just parl-report-liberty-delegated-enforcement-status
  just parl-check-liberty-delegated-enforcement-gate
  just parl-check-liberty-delegated-non-nominative-qa-gate
  just parl-export-liberty-restrictions-snapshot
  just parl-publish-liberty-atlas-artifacts
  just parl-check-liberty-atlas-changelog-continuity
  just parl-report-liberty-atlas-release-heartbeat
  just parl-check-liberty-atlas-release-heartbeat-window

parl-test-liberty-restrictions:
  python3 -m unittest tests/test_validate_liberty_restrictions_seed.py tests/test_import_liberty_restrictions_seed.py tests/test_report_liberty_restrictions_status.py tests/test_report_liberty_focus_scope_guard.py tests/test_report_liberty_restrictions_status_heartbeat.py tests/test_report_liberty_restrictions_status_heartbeat_window.py tests/test_validate_liberty_proportionality_seed.py tests/test_import_liberty_proportionality_seed.py tests/test_report_liberty_proportionality_status.py tests/test_report_liberty_direct_accountability_scores.py tests/test_validate_liberty_person_identity_resolution_seed.py tests/test_import_liberty_person_identity_resolution_seed.py tests/test_report_liberty_personal_accountability_scores.py tests/test_report_liberty_person_identity_resolution_queue.py tests/test_export_liberty_person_identity_official_upgrade_review_queue.py tests/test_report_liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat.py tests/test_report_liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_window.py tests/test_apply_liberty_person_identity_official_upgrade_reviews.py tests/test_validate_liberty_enforcement_seed.py tests/test_import_liberty_enforcement_seed.py tests/test_report_liberty_enforcement_variation_status.py tests/test_validate_liberty_indirect_accountability_seed.py tests/test_import_liberty_indirect_accountability_seed.py tests/test_report_liberty_indirect_accountability_status.py tests/test_validate_liberty_delegated_enforcement_seed.py tests/test_import_liberty_delegated_enforcement_seed.py tests/test_report_liberty_delegated_enforcement_status.py tests/test_report_liberty_delegated_person_window_queue.py tests/test_export_liberty_delegated_person_window_review_queue.py tests/test_apply_liberty_delegated_person_window_reviews.py tests/test_export_liberty_delegated_person_window_scrape_targets.py tests/test_scrape_liberty_delegated_person_window_boe_candidates.py tests/test_export_liberty_delegated_person_window_review_assist_from_boe_candidates.py tests/test_export_liberty_delegated_person_window_auto_review_decisions.py tests/test_export_liberty_delegated_person_window_auto_review_qa_sample.py tests/test_report_liberty_delegated_person_window_auto_review_qa_precision.py tests/test_report_liberty_delegated_non_nominative_qa_gate.py tests/test_export_liberty_delegated_alternative_capture_targets.py tests/test_scrape_liberty_delegated_alternative_boe_candidates.py tests/test_export_liberty_restrictions_snapshot.py tests/test_publish_liberty_atlas_artifacts.py tests/test_report_liberty_atlas_changelog_continuity.py tests/test_report_liberty_atlas_release_heartbeat.py tests/test_report_liberty_atlas_release_heartbeat_window.py

parl-programas-pipeline:
  just parl-validate-programas-manifest
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py ingest --db {{db_path}} --source programas_partidos --from-file {{programas_manifest}} --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-declared-stance --db {{db_path}} --source-id programas_partidos --min-auto-confidence {{declared_min_auto_confidence}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-declared-positions --db {{db_path}} --source-id programas_partidos --as-of-date {{snapshot_date}}"
  just parl-programas-status

parl-backfill-combined-positions:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-combined-positions --db {{db_path}} --as-of-date {{snapshot_date}}"

parl-review-queue:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py review-queue --db {{db_path}} --source-id {{declared_source_id}} --status pending --limit {{declared_review_limit}}"

parl-review-resolve evidence_id stance:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py review-decision --db {{db_path}} --source-id {{declared_source_id}} --evidence-ids {{evidence_id}} --status resolved --final-stance {{stance}} --recompute --as-of-date {{snapshot_date}}"

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

parl-quality-report-initiatives:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py quality-report --db {{db_path}} --include-initiatives --initiative-source-ids congreso_iniciativas,senado_iniciativas --initiative-actionable-scope {{initiative_quality_actionable_scope}} --json-out etl/data/published/votaciones-kpis-initiatives-es-{{snapshot_date}}.json"

parl-quality-report-initiatives-enforce:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py quality-report --db {{db_path}} --include-initiatives --initiative-source-ids congreso_iniciativas,senado_iniciativas --initiative-actionable-scope {{initiative_quality_actionable_scope}} --enforce-gate --json-out etl/data/published/votaciones-kpis-initiatives-es-{{snapshot_date}}.json"

parl-quality-report-declared:
  out_arg=""; skip_arg=""; \
  if [ -n "{{declared_quality_out}}" ]; then \
    out_arg=" --json-out {{declared_quality_out}}"; \
  fi; \
  if [ "{{declared_quality_skip_vote_gate}}" = "1" ]; then \
    skip_arg=" --skip-vote-gate"; \
  fi; \
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py quality-report --db {{db_path}} --source-ids {{declared_quality_vote_source_ids}} --include-declared --declared-source-ids {{declared_quality_source_ids}}${skip_arg}${out_arg}"

parl-quality-report-declared-enforce:
  out_arg=""; skip_arg=""; \
  if [ -n "{{declared_quality_out}}" ]; then \
    out_arg=" --json-out {{declared_quality_out}}"; \
  fi; \
  if [ "{{declared_quality_skip_vote_gate}}" = "1" ]; then \
    skip_arg=" --skip-vote-gate"; \
  fi; \
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py quality-report --db {{db_path}} --source-ids {{declared_quality_vote_source_ids}} --include-declared --declared-source-ids {{declared_quality_source_ids}} --enforce-gate${skip_arg}${out_arg}"

parl-quality-report-unmatched:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py quality-report --db {{db_path}} --include-unmatched --unmatched-sample-limit 50"

parl-quality-report-hf:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-member-ids --db {{db_path}} --unmatched-sample-limit 50"
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py link-votes --db {{db_path}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py quality-report --db {{db_path}} --include-initiatives --initiative-source-ids congreso_iniciativas,senado_iniciativas --initiative-actionable-scope {{initiative_quality_actionable_scope}} --json-out etl/data/published/votaciones-kpis-es-{{snapshot_date}}.json"

parl-quality-pipeline:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-member-ids --db {{db_path}} --unmatched-sample-limit 50"
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py link-votes --db {{db_path}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py backfill-topic-analytics --db {{db_path}} --as-of-date {{snapshot_date}} --taxonomy-seed {{topic_taxonomy_seed}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py quality-report --db {{db_path}} --include-initiatives --initiative-source-ids congreso_iniciativas,senado_iniciativas --initiative-actionable-scope {{initiative_quality_actionable_scope}} --enforce-gate --json-out etl/data/published/votaciones-kpis-es-{{snapshot_date}}.json"

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

dev-fixture:
  DB_PATH={{dev_fixture_db_path}} just etl-smoke-e2e

dev-smoke:
  just dev-fixture
  python3 scripts/dev_boot_smoke.py --db "{{dev_fixture_db_path}}" --host {{explorer_host}} --port {{explorer_port}}

dev:
  just dev-fixture
  python3 scripts/dev_boot_smoke.py --db "{{dev_fixture_db_path}}" --host {{explorer_host}} --port {{explorer_port}} --keep-running

dev-clean:
  rm -f "{{dev_fixture_db_path}}"

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

# descargas.interior.gob.es currently serves an incomplete TLS chain from this runtime.
# Keep the bypass explicit, source-scoped, and recorded as tls_verified=false.
etl-extract-infoelectoral-elected-officials:
  docker compose run --rm --build etl "python3 scripts/ingest_infoelectoral_elected_officials.py --db {{db_path}} --snapshot-date {{snapshot_date}} --store-root {{infoelectoral_elected_store_root}} --manifest-root {{infoelectoral_elected_manifest_root}} --report-out {{infoelectoral_elected_report}} --min-free-bytes {{infoelectoral_elected_min_free_bytes}} --timeout {{infoelectoral_timeout}} --insecure-ssl"

# Catalog is safe/offline after infoelectoral_descargas has populated the DB.
etl-infoelectoral-candidates-enqueue:
  docker compose run --rm --build etl "python3 scripts/ingest_infoelectoral_candidates.py --db {{db_path}} --pipeline-id {{infoelectoral_candidate_pipeline_id}} --report-out {{infoelectoral_candidate_report}} enqueue --snapshot-date {{snapshot_date}}"

# Raw candidate archives contain DNI/birth fields. Keep the CAS restricted and ignored.
# Workers are horizontally repeatable through atomic SQLite leases; each run stays bounded.
etl-infoelectoral-candidates-work:
  docker compose run --rm --build etl "local_arg=''; if [ -n '{{infoelectoral_candidate_local_archive_dir}}' ]; then local_arg='--local-archive-dir {{infoelectoral_candidate_local_archive_dir}}'; fi; python3 scripts/ingest_infoelectoral_candidates.py --db {{db_path}} --pipeline-id {{infoelectoral_candidate_pipeline_id}} --report-out {{infoelectoral_candidate_report}} worker --worker-id infoelectoral-candidate-worker --store-root {{infoelectoral_candidate_store_root}} --timeout {{infoelectoral_timeout}} --max-items {{infoelectoral_candidate_worker_max_items}} --min-free-bytes {{infoelectoral_candidate_min_free_bytes}} $local_arg"

etl-infoelectoral-candidates-report:
  docker compose run --rm --build etl "python3 scripts/ingest_infoelectoral_candidates.py --db {{db_path}} --pipeline-id {{infoelectoral_candidate_pipeline_id}} --report-out {{infoelectoral_candidate_report}} report"

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

gh-pages-next-stop:
  docker rm -f {{gh_pages_next_container}} >/tmp/vota-gh-pages-next-stop.log 2>&1 || true

gh-pages-next:
  @just gh-pages-next-watch

gh-pages-next-watch:
  @just gh-pages-next-stop
  @just gh-pages-next-prime
  docker run --rm \
    -p "{{gh_pages_next_port}}:{{gh_pages_next_port}}" \
    -v "${PWD}:/workspace" \
    -w /workspace/{{gh_pages_next_app_dir}} \
    --name {{gh_pages_next_container}} \
    --volume "{{gh_pages_next_node_modules_volume}}:/workspace/{{gh_pages_next_app_dir}}/node_modules" \
    --volume "{{gh_pages_next_next_dir_volume}}:/workspace/{{gh_pages_next_app_dir}}/.next" \
    {{gh_pages_next_docker_image}} \
    sh -lc 'set -eu; \
      clear_mount_dir() { \
        target="$1"; \
        mkdir -p "$target"; \
        find "$target" -mindepth 1 -maxdepth 1 -exec rm -rf {} +; \
      }; \
      hash_file() { \
        md5sum "$1" | tr -s " " | cut -d " " -f 1; \
      }; \
      DEPS_SUM_FILE="node_modules/.deps-sum"; \
      if [ -f "package-lock.json" ]; then \
        DEPS_SUM="$(hash_file package-lock.json)"; \
        if [ ! -d node_modules ] || [ ! -f "$DEPS_SUM_FILE" ] || [ "$DEPS_SUM" != "$(cat "$DEPS_SUM_FILE")" ]; then \
          clear_mount_dir node_modules; \
          clear_mount_dir .next; \
          npm ci --no-audit --no-fund; \
          printf "%s" "$DEPS_SUM" > "$DEPS_SUM_FILE"; \
        fi; \
      else \
        DEPS_SUM="$(hash_file package.json)"; \
        if [ ! -d node_modules ] || [ ! -f "$DEPS_SUM_FILE" ] || [ "$DEPS_SUM" != "$(cat "$DEPS_SUM_FILE")" ]; then \
          clear_mount_dir node_modules; \
          clear_mount_dir .next; \
          npm install --no-audit --no-fund; \
          printf "%s" "$DEPS_SUM" > "$DEPS_SUM_FILE"; \
        fi; \
      fi; \
      npm run dev -- --hostname 0.0.0.0 --port {{gh_pages_next_port}}'

accountability-dossiers-next-prime:
  mkdir -p "{{gh_pages_dir}}/accountability-dossiers/data"
  mkdir -p "{{gh_pages_dir}}/accountability-evidence/data"
  mkdir -p "{{gh_pages_next_app_dir}}/public/accountability-dossiers/data"
  mkdir -p "{{gh_pages_next_app_dir}}/public/accountability-evidence/data"
  set -e; \
  accountability_db="{{db_path}}"; \
  if [ -n "{{accountability_ledger_db_path}}" ]; then accountability_db="{{accountability_ledger_db_path}}"; fi; \
  if [ "{{gh_pages_next_prime_export}}" = "1" ]; then \
    python3 scripts/export_accountability_dossier_snapshot.py \
      --db "$accountability_db" \
      --snapshot-date "{{snapshot_date}}" \
      --out "{{gh_pages_dir}}/accountability-dossiers/data/dossiers.json" \
      --latest-out "{{gh_pages_next_app_dir}}/public/accountability-dossiers/data/dossiers.json" \
      --max-issues-per-actor "{{accountability_dossiers_max_issues_per_actor}}" \
      --max-actors-per-issue "{{accountability_dossiers_max_actors_per_issue}}"; \
    python3 scripts/export_accountability_ledger_snapshot.py \
      --db "$accountability_db" \
      --snapshot-date "{{snapshot_date}}" \
      --out "{{gh_pages_dir}}/accountability-dossiers/data/ledger.json" \
      --latest-out "{{gh_pages_next_app_dir}}/public/accountability-dossiers/data/ledger.json" \
      --max-entries-per-issue "{{accountability_ledger_max_entries_per_issue}}" \
      --max-sample-entries-per-actor "{{accountability_ledger_max_sample_entries_per_actor}}"; \
    python3 scripts/export_accountability_evidence_api_snapshot.py \
      --dossiers "{{gh_pages_dir}}/accountability-dossiers/data/dossiers.json" \
      --ledger "{{gh_pages_dir}}/accountability-dossiers/data/ledger.json" \
      --snapshot-date "{{snapshot_date}}" \
      --out "{{gh_pages_dir}}/accountability-evidence/data/evidence-api.json" \
      --latest-out "{{gh_pages_next_app_dir}}/public/accountability-evidence/data/evidence-api.json"; \
  else \
    if [ -f "etl/data/published/accountability-dossiers-latest.json" ]; then \
      cp -f "etl/data/published/accountability-dossiers-latest.json" "{{gh_pages_dir}}/accountability-dossiers/data/dossiers.json"; \
      cp -f "etl/data/published/accountability-dossiers-latest.json" "{{gh_pages_next_app_dir}}/public/accountability-dossiers/data/dossiers.json"; \
    elif [ ! -f "{{gh_pages_next_app_dir}}/public/accountability-dossiers/data/dossiers.json" ]; then \
      printf '%s\n' '{"meta":{"schema_version":"accountability_dossier_snapshot_v1","generated_at":"dev-local-stub","snapshot_date":"{{snapshot_date}}"},"snapshot_date":"{{snapshot_date}}","coverage":{"entries_total":0,"actors_total":0,"actors_exported":0,"actors_truncated":false,"issues_total":0,"issues_exported":0,"issues_truncated":false,"issue_actor_edges_total":0,"entries_with_person_id":0,"entries_with_party_id":0,"entries_with_parliamentary_group_id":0,"entries_with_mandate_id":0,"entries_with_institution_id":0,"entries_with_org_unit_id":0,"entries_with_position_id":0,"entries_by_role":{},"entries_by_kind":{},"entries_by_actor_kind":{}},"actors":[],"issues":[]}' > "{{gh_pages_next_app_dir}}/public/accountability-dossiers/data/dossiers.json"; \
      cp -f "{{gh_pages_next_app_dir}}/public/accountability-dossiers/data/dossiers.json" "{{gh_pages_dir}}/accountability-dossiers/data/dossiers.json"; \
    else \
      cp -f "{{gh_pages_next_app_dir}}/public/accountability-dossiers/data/dossiers.json" "{{gh_pages_dir}}/accountability-dossiers/data/dossiers.json"; \
    fi; \
    if [ -f "etl/data/published/accountability-ledger-latest.json" ]; then \
      cp -f "etl/data/published/accountability-ledger-latest.json" "{{gh_pages_dir}}/accountability-dossiers/data/ledger.json"; \
      cp -f "etl/data/published/accountability-ledger-latest.json" "{{gh_pages_next_app_dir}}/public/accountability-dossiers/data/ledger.json"; \
    elif [ ! -f "{{gh_pages_next_app_dir}}/public/accountability-dossiers/data/ledger.json" ]; then \
      printf '%s\n' '{"meta":{"schema_version":"accountability_ledger_snapshot_v1","generated_at":"dev-local-stub","snapshot_date":"{{snapshot_date}}","issue_id":""},"snapshot_date":"{{snapshot_date}}","coverage":{"issues_total":0,"entries_total":0,"entries_exported":0,"entries_truncated":false,"issues_with_truncated_entries":0,"actors_total":0,"entries_with_resolved_actor_id":0,"entries_with_person_id":0,"entries_with_party_id":0,"entries_with_parliamentary_group_id":0,"entries_with_mandate_id":0,"entries_with_institution_id":0,"entries_with_org_unit_id":0,"entries_with_position_id":0,"entries_by_role":{},"entries_by_kind":{},"entries_by_actor_kind":{}},"actors":[],"issues":[]}' > "{{gh_pages_next_app_dir}}/public/accountability-dossiers/data/ledger.json"; \
      cp -f "{{gh_pages_next_app_dir}}/public/accountability-dossiers/data/ledger.json" "{{gh_pages_dir}}/accountability-dossiers/data/ledger.json"; \
    else \
      cp -f "{{gh_pages_next_app_dir}}/public/accountability-dossiers/data/ledger.json" "{{gh_pages_dir}}/accountability-dossiers/data/ledger.json"; \
    fi; \
    if [ -f "etl/data/published/accountability-evidence-api-latest.json" ]; then \
      cp -f "etl/data/published/accountability-evidence-api-latest.json" "{{gh_pages_dir}}/accountability-evidence/data/evidence-api.json"; \
      cp -f "etl/data/published/accountability-evidence-api-latest.json" "{{gh_pages_next_app_dir}}/public/accountability-evidence/data/evidence-api.json"; \
    elif [ ! -f "{{gh_pages_next_app_dir}}/public/accountability-evidence/data/evidence-api.json" ]; then \
      printf '%s\n' '{"meta":{"schema_version":"accountability_evidence_api_v1","generated_at":"dev-local-stub","snapshot_date":"{{snapshot_date}}"},"snapshot_date":"{{snapshot_date}}","coverage":{"source_entries_total":0,"source_actors_total":0,"source_issues_total":0,"question_templates_total":0,"actor_answers_total":0,"issue_answers_total":0,"actor_issue_refs_total":0,"issue_clusters_total":0,"issue_cluster_links_total":0,"issue_cluster_review_items_total":0,"issue_cluster_review_status_counts":{},"fallback_issue_cluster_answers_total":0,"gap_answers_total":0,"qa_answers_total":0,"qa_answers_with_self_route_total":0,"evidence_samples_total":0,"answer_status_counts":{},"gap_answer_status_counts":{},"qa_answer_status_counts":{}},"question_templates":[],"actor_answers":[],"issue_answers":[],"actor_issue_refs":[],"issue_clusters":[],"issue_cluster_review_queue":[],"gap_answers":[],"qa_answers":[],"indexes":{"actor_answer_by_key":{},"issue_answer_by_id":{},"issue_cluster_by_id":{},"issue_clusters_by_issue_id":{},"issue_cluster_review_by_id":{},"gap_answer_by_dimension":{},"qa_answer_by_id":{},"qa_route_by_id":{}}}' > "{{gh_pages_next_app_dir}}/public/accountability-evidence/data/evidence-api.json"; \
      cp -f "{{gh_pages_next_app_dir}}/public/accountability-evidence/data/evidence-api.json" "{{gh_pages_dir}}/accountability-evidence/data/evidence-api.json"; \
    else \
      cp -f "{{gh_pages_next_app_dir}}/public/accountability-evidence/data/evidence-api.json" "{{gh_pages_dir}}/accountability-evidence/data/evidence-api.json"; \
    fi; \
  fi

gh-pages-next-prime:
  mkdir -p "{{gh_pages_dir}}"/parliamentary-accountability/data
  mkdir -p "{{gh_pages_next_app_dir}}/public/parliamentary-accountability/data"
  mkdir -p "{{gh_pages_dir}}"/accountability-dossiers/data
  mkdir -p "{{gh_pages_next_app_dir}}/public/accountability-dossiers/data"
  mkdir -p "{{gh_pages_dir}}"/responsibility-explainer/data
  mkdir -p "{{gh_pages_next_app_dir}}/public/responsibility-explainer/data"
  mkdir -p "{{gh_pages_dir}}"/people/data
  mkdir -p "{{gh_pages_next_app_dir}}/public/people/data"
  mkdir -p "{{gh_pages_dir}}"/initiative-lifecycle/data
  mkdir -p "{{gh_pages_next_app_dir}}/public/initiative-lifecycle/data"
  mkdir -p "{{gh_pages_dir}}"/political-positions/data
  mkdir -p "{{gh_pages_next_app_dir}}/public/political-positions/data"
  mkdir -p "{{gh_pages_dir}}"/elections-behavior/data
  mkdir -p "{{gh_pages_next_app_dir}}"/public/elections-behavior/data
  mkdir -p "{{gh_pages_dir}}"/elecciones/andalucia-2026/data
  mkdir -p "{{gh_pages_next_app_dir}}"/public/elecciones/andalucia-2026/data
  mkdir -p "{{gh_pages_dir}}"/legal-sanctions/data
  mkdir -p "{{gh_pages_next_app_dir}}"/public/legal-sanctions/data
  mkdir -p "{{gh_pages_dir}}"/policy-outcomes/data
  mkdir -p "{{gh_pages_next_app_dir}}"/public/policy-outcomes/data
  if [ "{{gh_pages_next_prime_export}}" = "1" ]; then \
    python3 scripts/export_parliamentary_accountability_snapshot.py \
      --db "{{db_path}}" \
      --out "{{gh_pages_dir}}/parliamentary-accountability/data/accountability.json"; \
  elif [ ! -f "{{gh_pages_dir}}/parliamentary-accountability/data/accountability.json" ]; then \
    printf '%s\n' \
      '{"meta":{"generated_at":"dev-local-stub","total_events":0},"parties":[],"discipline":{"members":[],"parties":[],"parties_by_legislature":[],"attendance_by_member_context":[],"attendance_by_party_context":[]},"outcomes":{"summary":{"passed":0,"failed":0,"tied":0,"no_signal":0},"critical_by_margin":[]},"coalitions":{"pairs":[],"issue_coalitions":[]}}' \
      > "{{gh_pages_dir}}/parliamentary-accountability/data/accountability.json"; \
  fi
  if [ "{{gh_pages_next_prime_export}}" = "1" ]; then \
    python3 scripts/export_initiative_lifecycle_snapshot.py \
      --db "{{db_path}}" \
      --out "{{gh_pages_dir}}/initiative-lifecycle/data/lifecycle.json" \
      --max-initiatives 200 \
      --max-votes-per-initiative 80 \
      --min-committee-sample 4; \
  elif [ ! -f "{{gh_pages_dir}}/initiative-lifecycle/data/lifecycle.json" ]; then \
    printf '%s\n' \
      '{"meta":{"generated_at":"dev-local-stub","total_initiatives":0,"linked_initiatives":0,"unlinked_initiatives":0,"total_vote_links":0},"filters":{"source_ids":[],"committees":[],"legislatures":[],"status_buckets":[],"link_methods":[]},"initiative_overview":{"linked_initiatives":0,"unlinked_initiatives":0,"confidence_distribution":{"high":0,"medium":0,"low":0,"none":0},"global_confidence":{"high":0,"medium":0,"low":0,"none":0},"link_methods":{}}, "bottlenecks":{"committee_by_throughput":[]}, "initiatives":[]}' \
      > "{{gh_pages_dir}}/initiative-lifecycle/data/lifecycle.json"; \
  fi
  if [ "{{gh_pages_next_prime_export}}" = "1" ]; then \
    mkdir -p "{{gh_pages_dir}}/people/data"; \
    if [ "{{gh_pages_reuse_people_exports}}" = "1" ] && \
      python3 scripts/check_static_snapshot_date.py --path "{{gh_pages_dir}}/people/data/profiles.json" --snapshot-date "{{snapshot_date}}" >/dev/null 2>&1 && \
      python3 scripts/check_static_snapshot_date.py --path "{{gh_pages_dir}}/people/data/xray.json" --snapshot-date "{{snapshot_date}}" >/dev/null 2>&1; then \
      echo "Reusing existing people exports for snapshot {{snapshot_date}}"; \
    else \
      python3 scripts/export_people_profiles_snapshot.py \
        --db "{{db_path}}" \
        --out "{{gh_pages_dir}}/people/data/profiles.json" \
        --snapshot-date "{{snapshot_date}}"; \
      python3 scripts/export_people_xray_snapshot.py \
        --db "{{db_path}}" \
        --out "{{gh_pages_dir}}/people/data/xray.json" \
        --snapshot-date "{{snapshot_date}}"; \
    fi; \
    python3 scripts/export_political_positions_snapshot.py \
      --db "{{db_path}}" \
      --out "{{gh_pages_dir}}/political-positions/data/stances.json" \
      --snapshot-date "{{snapshot_date}}"; \
    python3 scripts/export_elections_behavior_snapshot.py \
      --db "{{db_path}}" \
      --out "{{gh_pages_dir}}/elections-behavior/data/elections-behavior.json" \
      --window-days 365 \
      --min-directional-votes 18; \
    python3 scripts/export_andalucia_2026_accountability_snapshot.py \
      --db "{{db_path}}" \
      --out "{{gh_pages_dir}}/elecciones/andalucia-2026/data/accountability.json" \
      --published-out "etl/data/published/andalucia-2026-accountability.json" \
      --timeout "{{infoelectoral_timeout}}" \
      --refresh-outcome-series; \
    python3 scripts/run_andalucia_2026_delivery_evidence_hunts.py \
      --snapshot "{{gh_pages_dir}}/elecciones/andalucia-2026/data/accountability.json" \
      --out "etl/data/published/andalucia-2026-delivery-evidence-hunt-results.json" \
      --public-out "{{gh_pages_dir}}/elecciones/andalucia-2026/data/delivery-evidence-hunt-results.json" \
      --max-targets "{{andalucia_delivery_hunt_max_targets}}" \
      --rows-per-query "{{andalucia_delivery_hunt_rows_per_query}}" \
      --timeout "{{andalucia_delivery_hunt_timeout}}"; \
    python3 scripts/generate_andalucia_2026_delivery_review_drafts.py \
      --hunt-results "etl/data/published/andalucia-2026-delivery-evidence-hunt-results.json" \
      --out "etl/data/published/andalucia-2026-delivery-evidence-review-drafts.json" \
      --public-out "{{gh_pages_dir}}/elecciones/andalucia-2026/data/delivery-evidence-review-drafts.json"; \
    python3 scripts/export_legal_sanctions_snapshot.py \
      --db "{{db_path}}" \
      --out "{{gh_pages_dir}}/legal-sanctions/data/legal-sanctions.json"; \
    python3 scripts/export_policy_outcomes_snapshot.py \
      --db "{{db_path}}" \
      --out "{{gh_pages_dir}}/policy-outcomes/data/policy-outcomes.json"; \
  fi
  if [ ! -f "{{gh_pages_dir}}/people/data/xray.json" ]; then \
    printf '%s\n' \
      '{"meta":{"generated_at":"dev-local-stub","snapshot_date":"{{snapshot_date}}","source_snapshot":"{{snapshot_date}}","top_members":24,"include_party_proxies":0,"group_count":{"party":0,"institution":0,"ambito":0,"territorio":0,"cargo":0}},"kinds":["party","institution","ambito","territorio","cargo"],"groups":{"party":[],"institution":[],"ambito":[],"territorio":[],"cargo":[]}, "group_index":{"party":{},"institution":{},"ambito":{},"territorio":{},"cargo":{}}}' \
      > "{{gh_pages_dir}}/people/data/xray.json"; \
  fi
  if [ ! -f "{{gh_pages_dir}}/legal-sanctions/data/legal-sanctions.json" ]; then \
    printf '%s\n' \
      '{"generated_at":"dev-local-stub","snapshot_date":"{{snapshot_date}}","schema_version":"legal_sanctions_snapshot_v1","meta":{"norm_nodes":0,"lineage_edges":0,"infraction_type_count":0,"infraction_mappings":0,"volume_rows":0,"kpi_rows":0,"municipal_rows":0},"filters":{"source_ids":[],"relation_types":[],"infraction_type_ids":[],"kpi_ids":[],"periods":[]},"legal_graph":{"nodes":[],"edges":[],"node_count":0,"edge_count":0,"relation_types":[],"nodes_with_fragments":0},"infraction_network":{"infraction_types":[],"mappings":[]},"sanction_volume_monitoring":{"series":[],"source_totals":[],"sources":[],"periods":[]},"procedural_kpi_drift":[],"municipal_monitoring":{"summary":{"total_ordinances":0,"normalized_ordinances":0,"identified_ordinances":0,"blocked_ordinances":0,"status_counts":[]},"city_summary":[],"ordinance_rows":[]},"responsibility_summary":{"roles":[],"top_actors":[],"rows_with_primary_evidence":0,"rows_total":0},"liberty_restriction_monitoring":{"enabled":false,"rows":0}}' \
      > "{{gh_pages_dir}}/legal-sanctions/data/legal-sanctions.json"; \
  fi
  if [ ! -f "{{gh_pages_dir}}/policy-outcomes/data/policy-outcomes.json" ]; then \
    printf '%s\n' \
      '{"meta":{"generated_at":"dev-local-stub","snapshot_date":"{{snapshot_date}}","generated_by":"gh-pages-next-prime","filters":{}}, "coverage":{"indicator_series_total":0,"indicator_points_total":0,"interventions_total":0,"intervention_events_total":0,"causal_estimates_total":0,"policy_events_total":0,"series_loaded":0,"events_loaded":0,"events_in_association":0,"associations_total":0,"series_in_association":0,"series_by_source":{},"series_coverage_by_point_count":{"min_points_included":0,"max_points_included":0}}, "series":[],"policy_events":[],"associations":[],"limitations":{"interventions_available":false,"intervention_events_available":false,"causal_estimates_available":false,"description":["Stub temporal: sin snapshot generado en modo local sin export"],"method_note":"Correlación no implica causalidad."},"filters":{"series_source_ids":[],"event_source_ids":[],"domains":[]}}' \
      > "{{gh_pages_dir}}/policy-outcomes/data/policy-outcomes.json"; \
  fi
  @just accountability-dossiers-next-prime
  @just responsibility-explainer-next-prime
  if [ -f "{{gh_pages_dir}}/parliamentary-accountability/data/accountability.json" ]; then \
    cp -f "{{gh_pages_dir}}/parliamentary-accountability/data/accountability.json" \
      "{{gh_pages_next_app_dir}}/public/parliamentary-accountability/data/accountability.json"; \
  fi
  if [ -f "{{gh_pages_dir}}/initiative-lifecycle/data/lifecycle.json" ]; then \
    cp -f "{{gh_pages_dir}}/initiative-lifecycle/data/lifecycle.json" \
      "{{gh_pages_next_app_dir}}/public/initiative-lifecycle/data/lifecycle.json"; \
  fi
  if [ -f "{{gh_pages_dir}}/people/data/profiles.json" ]; then \
    for src in "{{gh_pages_dir}}"/people/data/*.json; do \
      [ -f "$src" ] || continue; \
      cp -f "$src" "{{gh_pages_next_app_dir}}/public/people/data/"; \
    done; \
  fi
  if [ -f "{{gh_pages_dir}}/political-positions/data/stances.json" ]; then \
    cp -f "{{gh_pages_dir}}/political-positions/data/stances.json" \
      "{{gh_pages_next_app_dir}}/public/political-positions/data/stances.json"; \
    if [ -f "{{gh_pages_dir}}/political-positions/data/person-default-rows.json" ]; then \
      cp -f "{{gh_pages_dir}}/political-positions/data/person-default-rows.json" \
        "{{gh_pages_next_app_dir}}/public/political-positions/data/person-default-rows.json"; \
    fi; \
    if [ -f "{{gh_pages_dir}}/political-positions/data/person-search-index.json" ]; then \
      cp -f "{{gh_pages_dir}}/political-positions/data/person-search-index.json" \
        "{{gh_pages_next_app_dir}}/public/political-positions/data/person-search-index.json"; \
    fi; \
    if [ -f "{{gh_pages_dir}}/political-positions/data/topic-search-index.json" ]; then \
      cp -f "{{gh_pages_dir}}/political-positions/data/topic-search-index.json" \
        "{{gh_pages_next_app_dir}}/public/political-positions/data/topic-search-index.json"; \
    fi; \
    if [ -d "{{gh_pages_dir}}/political-positions/data/person-sort-previews" ]; then \
      rm -rf "{{gh_pages_next_app_dir}}/public/political-positions/data/person-sort-previews"; \
      cp -R "{{gh_pages_dir}}/political-positions/data/person-sort-previews" \
        "{{gh_pages_next_app_dir}}/public/political-positions/data/person-sort-previews"; \
    fi; \
    for src in "{{gh_pages_dir}}"/political-positions/data/*-trajectories.json; do \
      [ -f "$src" ] || continue; \
      cp -f "$src" "{{gh_pages_next_app_dir}}/public/political-positions/data/"; \
    done; \
    if [ -d "{{gh_pages_dir}}/political-positions/data/person-trajectory-chunks" ]; then \
      rm -rf "{{gh_pages_next_app_dir}}/public/political-positions/data/person-trajectory-chunks"; \
      cp -R "{{gh_pages_dir}}/political-positions/data/person-trajectory-chunks" \
        "{{gh_pages_next_app_dir}}/public/political-positions/data/person-trajectory-chunks"; \
    fi; \
    if [ -d "{{gh_pages_dir}}/political-positions/data/person-details" ]; then \
      rm -rf "{{gh_pages_next_app_dir}}/public/political-positions/data/person-details"; \
      cp -R "{{gh_pages_dir}}/political-positions/data/person-details" \
        "{{gh_pages_next_app_dir}}/public/political-positions/data/person-details"; \
    fi; \
    if [ -d "{{gh_pages_dir}}/political-positions/data/topic-person-rows" ]; then \
      rm -rf "{{gh_pages_next_app_dir}}/public/political-positions/data/topic-person-rows"; \
      cp -R "{{gh_pages_dir}}/political-positions/data/topic-person-rows" \
        "{{gh_pages_next_app_dir}}/public/political-positions/data/topic-person-rows"; \
    fi; \
  fi
  if [ -f "{{gh_pages_dir}}/elections-behavior/data/elections-behavior.json" ]; then \
    cp -f "{{gh_pages_dir}}/elections-behavior/data/elections-behavior.json" \
      "{{gh_pages_next_app_dir}}/public/elections-behavior/data/elections-behavior.json"; \
  fi
  if [ -f "{{gh_pages_dir}}/legal-sanctions/data/legal-sanctions.json" ]; then \
    cp -f "{{gh_pages_dir}}/legal-sanctions/data/legal-sanctions.json" \
      "{{gh_pages_next_app_dir}}/public/legal-sanctions/data/legal-sanctions.json"; \
  fi
  if [ -f "{{gh_pages_dir}}/policy-outcomes/data/policy-outcomes.json" ]; then \
    cp -f "{{gh_pages_dir}}/policy-outcomes/data/policy-outcomes.json" \
      "{{gh_pages_next_app_dir}}/public/policy-outcomes/data/policy-outcomes.json"; \
  fi
  if [ -d "{{gh_pages_dir}}/legacy" ]; then \
    mkdir -p "{{gh_pages_next_app_dir}}/public"; \
    cp -R "{{gh_pages_dir}}"/legacy "{{gh_pages_next_app_dir}}/public/" || true; \
    cp -R "{{gh_pages_dir}}"/parliamentary-accountability "{{gh_pages_next_app_dir}}/public/" 2>/dev/null || true; \
  fi
  @just vote-explainer-next-prime

responsibility-explainer-next-prime:
  mkdir -p "{{gh_pages_dir}}/responsibility-explainer/data"
  mkdir -p "{{gh_pages_next_app_dir}}/public/responsibility-explainer/data"
  set -e; \
  responsibility_explainer_db="{{db_path}}"; \
  if [ -n "{{initiative_measures_db_path}}" ]; then \
    responsibility_explainer_db="{{initiative_measures_db_path}}"; \
  fi; \
  responsibility_tmp_dir=""; \
  responsibility_tmp_db=""; \
  cleanup() { \
    if [ -n "$responsibility_tmp_dir" ]; then \
      rm -rf "$responsibility_tmp_dir"; \
    fi; \
  }; \
  trap cleanup EXIT; \
  if [ "{{gh_pages_next_prime_export}}" = "1" ]; then \
    if [ -f "$responsibility_explainer_db" ] && [ ! -w "$responsibility_explainer_db" ]; then \
      responsibility_tmp_dir="$(mktemp -d)"; \
      responsibility_tmp_db="$responsibility_tmp_dir/responsibility-explainer.db"; \
      cp "$responsibility_explainer_db" "$responsibility_tmp_db"; \
      chmod u+w "$responsibility_tmp_db"; \
      responsibility_explainer_db="$responsibility_tmp_db"; \
    fi; \
    python3 scripts/import_responsibility_explainer_seed.py \
      --db "$responsibility_explainer_db" \
      --seed "{{responsibility_explainer_seed_path}}" \
      --snapshot-date "{{snapshot_date}}"; \
    python3 scripts/apply_responsibility_ledger_reviews.py \
      --db "$responsibility_explainer_db" \
      --in-dir "{{responsibility_explainer_reviewed_ledger_dir}}"; \
    python3 scripts/export_responsibility_explainer_snapshot.py \
      --db "$responsibility_explainer_db" \
      --out-dir "{{gh_pages_dir}}/responsibility-explainer/data"; \
  elif [ ! -f "{{gh_pages_dir}}/responsibility-explainer/data/manifest.json" ]; then \
    printf '%s\n' \
      '{"meta":{"generated_at":"dev-local-stub","snapshot_date":"{{snapshot_date}}","schema_version":"responsibility_explainer_manifest_v1","snapshot_db":"stub","total_cases":0},"cases":[]}' \
      > "{{gh_pages_dir}}/responsibility-explainer/data/manifest.json"; \
  fi
  if [ -f "{{gh_pages_dir}}/responsibility-explainer/data/manifest.json" ]; then \
    find "{{gh_pages_next_app_dir}}/public/responsibility-explainer/data" -mindepth 1 -maxdepth 1 -type f -name '*.json' -delete; \
    cp -R "{{gh_pages_dir}}/responsibility-explainer/data/." "{{gh_pages_next_app_dir}}/public/responsibility-explainer/data/"; \
  fi

vote-explainer-next-prime:
  mkdir -p "{{gh_pages_dir}}/explorer-votaciones/data"
  mkdir -p "{{gh_pages_dir}}/vote-explainer/data"
  mkdir -p "{{gh_pages_next_app_dir}}/public/vote-explainer/data"
  python3 scripts/export_explorer_votaciones_snapshot.py \
    --db "{{db_path}}" \
    --limit {{vote_explainer_limit}} \
    --out "{{gh_pages_dir}}/explorer-votaciones/data/votes-preview.json"
  set -e; \
  tmp_vote_dir=$(mktemp -d); \
  cleanup() { rm -rf "$tmp_vote_dir"; }; \
  trap cleanup EXIT; \
  python3 scripts/export_vote_explainer_snapshot.py \
    --source-json "{{gh_pages_dir}}/explorer-votaciones/data/votes-preview.json" \
    --out-dir "$tmp_vote_dir" \
    --snapshot-as-of-date "{{snapshot_date}}"; \
  VOTE_EXPLAINER_ALLOW_EMPTY="{{vote_explainer_allow_empty}}" python3 -c 'import json, os, pathlib, sys; manifest=pathlib.Path("'"$tmp_vote_dir"'")/"manifest.json"; votes=len(json.loads(manifest.read_text()).get("votes", [])); print(f"vote explainer manifest votes={votes}"); sys.exit(0 if votes or os.environ.get("VOTE_EXPLAINER_ALLOW_EMPTY") == "1" else 1)'; \
  find "{{gh_pages_dir}}/vote-explainer/data" -mindepth 1 -maxdepth 1 -type f -name '*.json' -delete; \
  cp -R "$tmp_vote_dir/." "{{gh_pages_dir}}/vote-explainer/data/"; \
  find "{{gh_pages_next_app_dir}}/public/vote-explainer/data" -mindepth 1 -maxdepth 1 -type f -name '*.json' -delete; \
  cp -R "$tmp_vote_dir/." "{{gh_pages_next_app_dir}}/public/vote-explainer/data/"

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

explorer-datasette:
  python3 scripts/run_datasette_explorer.py --db "{{db_path}}" --host {{explorer_host}} --port 8011

cloudflare-pages-build:
  python3 scripts/build_citizen_tailwind_md3_css.py --tokens "{{citizen_tailwind_md3_tokens}}" --out "{{citizen_tailwind_md3_css}}"
  GH_PAGES_NEXT_PRIME_EXPORT=0 just accountability-dossiers-next-prime
  mkdir -p /tmp/vclc-npm-cache /tmp/vclc-npm-logs
  if [ ! -f "{{gh_pages_next_app_dir}}/node_modules/next/dist/bin/next" ]; then \
    npm --prefix "{{gh_pages_next_app_dir}}" --cache /tmp/vclc-npm-cache --logs-dir /tmp/vclc-npm-logs ci --no-audit --no-fund; \
  else \
    echo "Reusing existing {{gh_pages_next_app_dir}}/node_modules"; \
  fi
  cd "{{gh_pages_next_app_dir}}" && NEXT_PUBLIC_BASE_PATH="{{gh_pages_next_base_path}}" node node_modules/next/dist/bin/next build --webpack
  python3 scripts/check_next_export_notfound_payloads.py --path "{{gh_pages_next_out_dir}}"
  just cloudflare-pages-size-check
  just privacy-check-public-artifacts
  @echo "Build Cloudflare Pages listo en {{gh_pages_next_out_dir}}"

cloudflare-pages-size-check:
  set -e; \
  oversized="$(find "{{gh_pages_next_out_dir}}" -type f -size +{{cloudflare_pages_max_file_bytes}}c -print)"; \
  if [ -n "$oversized" ]; then \
    echo "ERROR: Cloudflare Pages file size limit exceeded (> {{cloudflare_pages_max_file_bytes}} bytes):" >&2; \
    printf '%s\n' "$oversized" | while IFS= read -r file; do wc -c "$file" >&2; done; \
    exit 1; \
  fi; \
  echo "OK Cloudflare Pages file size budget: no files over {{cloudflare_pages_max_file_bytes}} bytes"

explorer-gh-pages-build:
  @echo "DEPRECATED: explorer-gh-pages-build está desactivado como flujo de publicación. Usa just cloudflare-pages-build."
  @just cloudflare-pages-build

cloudflare-pages-refresh-data:
  rm -rf {{gh_pages_dir}}/_next {{gh_pages_dir}}/legacy {{gh_pages_dir}}/explorer {{gh_pages_dir}}/graph {{gh_pages_dir}}/explorer-politico {{gh_pages_dir}}/explorer-temas {{gh_pages_dir}}/explorer-votaciones {{gh_pages_dir}}/explorer-sources {{gh_pages_dir}}/vote-explainer {{gh_pages_dir}}/responsibility-explainer {{gh_pages_dir}}/citizen {{gh_pages_dir}}/parliamentary-accountability {{gh_pages_dir}}/accountability-dossiers {{gh_pages_dir}}/initiative-lifecycle {{gh_pages_dir}}/political-positions {{gh_pages_dir}}/elections-behavior {{gh_pages_dir}}/elecciones {{gh_pages_dir}}/calendario-electoral {{gh_pages_dir}}/people {{gh_pages_dir}}/legal-sanctions {{gh_pages_dir}}/policy-outcomes {{gh_pages_dir}}/index.html {{gh_pages_dir}}/404.html
  mkdir -p \
    {{gh_pages_dir}}/citizen {{gh_pages_dir}}/citizen/data \
    {{gh_pages_dir}}/graph {{gh_pages_dir}}/graph/data \
    {{gh_pages_dir}}/explorer-politico {{gh_pages_dir}}/explorer-politico/data \
    {{gh_pages_dir}}/explorer-sources {{gh_pages_dir}}/explorer-sources/data \
    {{gh_pages_dir}}/explorer-temas {{gh_pages_dir}}/explorer-temas/data \
    {{gh_pages_dir}}/explorer-votaciones {{gh_pages_dir}}/explorer-votaciones/data \
    {{gh_pages_dir}}/vote-explainer {{gh_pages_dir}}/vote-explainer/data \
    {{gh_pages_dir}}/responsibility-explainer {{gh_pages_dir}}/responsibility-explainer/data \
    {{gh_pages_dir}}/parliamentary-accountability {{gh_pages_dir}}/parliamentary-accountability/data \
    {{gh_pages_dir}}/accountability-dossiers {{gh_pages_dir}}/accountability-dossiers/data \
    {{gh_pages_dir}}/initiative-lifecycle {{gh_pages_dir}}/initiative-lifecycle/data \
    {{gh_pages_dir}}/political-positions {{gh_pages_dir}}/political-positions/data \
    {{gh_pages_dir}}/elections-behavior {{gh_pages_dir}}/elections-behavior/data \
    {{gh_pages_dir}}/elecciones {{gh_pages_dir}}/elecciones/andalucia-2026 {{gh_pages_dir}}/elecciones/andalucia-2026/data \
    {{gh_pages_dir}}/calendario-electoral {{gh_pages_dir}}/calendario-electoral/data \
    {{gh_pages_dir}}/people {{gh_pages_dir}}/people/data \
    {{gh_pages_dir}}/legal-sanctions {{gh_pages_dir}}/legal-sanctions/data \
    {{gh_pages_dir}}/policy-outcomes {{gh_pages_dir}}/policy-outcomes/data \
    {{gh_pages_dir}}/legacy {{gh_pages_dir}}/legacy/citizen {{gh_pages_dir}}/legacy/citizen/data \
    {{gh_pages_dir}}/legacy/graph {{gh_pages_dir}}/legacy/graph/data \
    {{gh_pages_dir}}/legacy/explorer {{gh_pages_dir}}/legacy/explorer/data \
    {{gh_pages_dir}}/legacy/explorer-sources {{gh_pages_dir}}/legacy/explorer-sources/data \
    {{gh_pages_dir}}/legacy/explorer-temas {{gh_pages_dir}}/legacy/explorer-temas/data \
    {{gh_pages_dir}}/legacy/explorer-votaciones {{gh_pages_dir}}/legacy/explorer-votaciones/data \
    {{gh_pages_dir}}/legacy/explorer-politico {{gh_pages_dir}}/legacy/explorer-politico/data
  python3 scripts/build_citizen_tailwind_md3_css.py --tokens "{{citizen_tailwind_md3_tokens}}" --out "{{citizen_tailwind_md3_css}}"
  mkdir -p /tmp/vclc-npm-cache /tmp/vclc-npm-logs
  if [ ! -f "{{gh_pages_next_app_dir}}/node_modules/next/dist/bin/next" ]; then \
    npm --prefix "{{gh_pages_next_app_dir}}" --cache /tmp/vclc-npm-cache --logs-dir /tmp/vclc-npm-logs ci --no-audit --no-fund; \
  else \
    echo "Reusing existing {{gh_pages_next_app_dir}}/node_modules"; \
  fi
  @just responsibility-explainer-next-prime
  @just accountability-dossiers-next-prime
  @just vote-explainer-next-prime
  cd "{{gh_pages_next_app_dir}}" && NEXT_PUBLIC_BASE_PATH="{{gh_pages_next_base_path}}" node node_modules/next/dist/bin/next build --webpack
  python3 scripts/check_next_export_notfound_payloads.py --path "{{gh_pages_next_out_dir}}"
  just cloudflare-pages-size-check
  cp -R "{{gh_pages_next_out_dir}}"/. "{{gh_pages_dir}}"/
  touch "{{gh_pages_dir}}/.nojekyll"
  cp -R ui/citizen/. {{gh_pages_dir}}/legacy/citizen/
  cp ui/graph/index.html {{gh_pages_dir}}/legacy/graph/index.html
  cp ui/graph/explorer.html {{gh_pages_dir}}/legacy/explorer/index.html
  cp ui/graph/explorer-sources.html {{gh_pages_dir}}/legacy/explorer-sources/index.html
  cp ui/graph/explorer-temas.html {{gh_pages_dir}}/legacy/explorer-temas/index.html
  cp ui/graph/explorer-votaciones.html {{gh_pages_dir}}/legacy/explorer-votaciones/index.html
  cp ui/graph/explorer-sports.html {{gh_pages_dir}}/legacy/explorer-politico/index.html
  cp ui/gh-pages-next/public/legacy/index.html {{gh_pages_dir}}/legacy/index.html
  cp ui/citizen/tailwind_md3.tokens.json {{gh_pages_dir}}/citizen/data/tailwind_md3.tokens.json
  cp ui/citizen/concerns_v1.json {{gh_pages_dir}}/citizen/data/concerns_v1.json
  python3 scripts/validate_citizen_concerns.py \
    --path "{{gh_pages_dir}}/citizen/data/concerns_v1.json"
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
  accountability_db="{{db_path}}"; \
  if [ -n "{{parliamentary_accountability_db_path}}" ]; then \
    accountability_db="{{parliamentary_accountability_db_path}}"; \
  fi; \
  extra_accountability_args=""; \
  if [ -n "{{initiative_measures_db_path}}" ]; then \
    extra_accountability_args="--initiative-measures-db {{initiative_measures_db_path}}"; \
  fi; \
  python3 scripts/export_parliamentary_accountability_snapshot.py \
    --db "$accountability_db" \
    $extra_accountability_args \
    --out "{{gh_pages_dir}}/parliamentary-accountability/data/accountability.json" \
    --max-rows-events 700 \
    --min-shared-events 12 \
    --min-events-per-party 12 \
    --min-events-topic-pairs 8
  python3 scripts/export_initiative_lifecycle_snapshot.py \
    --db "{{db_path}}" \
    --out "{{gh_pages_dir}}/initiative-lifecycle/data/lifecycle.json" \
    --min-committee-sample 6
  python3 scripts/export_political_positions_snapshot.py \
    --db "{{db_path}}" \
    --out "{{gh_pages_dir}}/political-positions/data/stances.json" \
    --topic-set-id 1 \
    --snapshot-date "{{snapshot_date}}"
  python3 scripts/export_elections_behavior_snapshot.py \
    --db "{{db_path}}" \
    --out "{{gh_pages_dir}}/elections-behavior/data/elections-behavior.json" \
    --window-days 365 \
    --min-directional-votes 18
  python3 scripts/export_andalucia_2026_accountability_snapshot.py \
    --db "{{db_path}}" \
    --out "{{gh_pages_dir}}/elecciones/andalucia-2026/data/accountability.json" \
    --published-out "etl/data/published/andalucia-2026-accountability.json" \
    --timeout "{{infoelectoral_timeout}}" \
    --refresh-outcome-series
  python3 scripts/run_andalucia_2026_delivery_evidence_hunts.py \
    --snapshot "{{gh_pages_dir}}/elecciones/andalucia-2026/data/accountability.json" \
    --out "etl/data/published/andalucia-2026-delivery-evidence-hunt-results.json" \
    --public-out "{{gh_pages_dir}}/elecciones/andalucia-2026/data/delivery-evidence-hunt-results.json" \
    --max-targets "{{andalucia_delivery_hunt_max_targets}}" \
    --rows-per-query "{{andalucia_delivery_hunt_rows_per_query}}" \
    --timeout "{{andalucia_delivery_hunt_timeout}}"
  python3 scripts/generate_andalucia_2026_delivery_review_drafts.py \
    --hunt-results "etl/data/published/andalucia-2026-delivery-evidence-hunt-results.json" \
    --out "etl/data/published/andalucia-2026-delivery-evidence-review-drafts.json" \
    --public-out "{{gh_pages_dir}}/elecciones/andalucia-2026/data/delivery-evidence-review-drafts.json"
  python3 scripts/generar_proximas_elecciones_espana.py \
    --today "{{snapshot_date}}" \
    --timeout "{{infoelectoral_timeout}}" \
    --json-out "etl/data/published/proximas-elecciones-espana.json" \
    --public-json-out "{{gh_pages_dir}}/calendario-electoral/data/election-calendar.json"
  python3 scripts/export_legal_sanctions_snapshot.py \
    --db "{{db_path}}" \
    --out "{{gh_pages_dir}}/legal-sanctions/data/legal-sanctions.json"
  python3 scripts/export_policy_outcomes_snapshot.py \
    --db "{{db_path}}" \
    --out "{{gh_pages_dir}}/policy-outcomes/data/policy-outcomes.json" \
    --snapshot-date "{{snapshot_date}}"
  set -e; if [ "{{gh_pages_reuse_people_exports}}" = "1" ] && \
    python3 scripts/check_static_snapshot_date.py --path "{{gh_pages_dir}}/people/data/profiles.json" --snapshot-date "{{snapshot_date}}" >/dev/null 2>&1 && \
    python3 scripts/check_static_snapshot_date.py --path "{{gh_pages_dir}}/people/data/xray.json" --snapshot-date "{{snapshot_date}}" >/dev/null 2>&1; then \
    echo "Reusing existing people exports for snapshot {{snapshot_date}}"; \
  else \
    python3 scripts/export_people_profiles_snapshot.py \
      --db "{{db_path}}" \
      --out "{{gh_pages_dir}}/people/data/profiles.json" \
      --snapshot-date {{snapshot_date}}; \
    python3 scripts/export_people_xray_snapshot.py \
      --db "{{db_path}}" \
      --out "{{gh_pages_dir}}/people/data/xray.json" \
      --snapshot-date {{snapshot_date}}; \
  fi
  python3 scripts/export_explorer_sources_snapshot.py \
    --db "{{db_path}}" \
    --out "{{gh_pages_dir}}/explorer-sources/data/status.json"
  python3 scripts/export_source_catalog_snapshot.py \
    --db "{{db_path}}" \
    --snapshot-date "{{snapshot_date}}" \
    --out "{{gh_pages_dir}}/explorer-sources/data/catalog.json" \
    --published-out "etl/data/published/source-catalog-{{snapshot_date}}.json" \
    --latest-out "etl/data/published/source-catalog-latest.json"
  python3 scripts/export_source_scrape_queue_snapshot.py \
    --db "{{db_path}}" \
    --snapshot-date "{{snapshot_date}}" \
    --out "{{gh_pages_dir}}/explorer-sources/data/scrape-queue.json" \
    --published-out "etl/data/published/source-scrape-queue-{{snapshot_date}}.json" \
    --latest-out "etl/data/published/source-scrape-queue-latest.json"
  python3 scripts/export_explorer_temas_snapshot.py \
    --db "{{db_path}}" \
    --out "{{gh_pages_dir}}/explorer-temas/data/temas-preview.json"
  set -e; \
  citizen_db="{{db_path}}"; \
  if [ -n "{{citizen_db_path}}" ]; then \
    citizen_db="{{citizen_db_path}}"; \
  fi; \
  citizen_fallback_auto="$(mktemp)"; \
  citizen_fallback_votes="$(mktemp)"; \
  citizen_fallback_declared="$(mktemp)"; \
  cleanup() { rm -f "$citizen_fallback_auto" "$citizen_fallback_votes" "$citizen_fallback_declared"; }; \
  trap cleanup EXIT; \
  git show HEAD:ui/gh-pages-next/public/citizen/data/citizen.json > "$citizen_fallback_auto" 2>/dev/null || true; \
  git show HEAD:ui/gh-pages-next/public/citizen/data/citizen_votes.json > "$citizen_fallback_votes" 2>/dev/null || true; \
  git show HEAD:ui/gh-pages-next/public/citizen/data/citizen_declared.json > "$citizen_fallback_declared" 2>/dev/null || true; \
  python3 scripts/export_citizen_snapshot.py \
    --db "$citizen_db" \
    --out "{{gh_pages_dir}}/citizen/data/citizen.json" \
    --topic-set-id 1 \
    --computed-method auto \
    --fallback-snapshot "$citizen_fallback_auto" \
    --max-bytes 5000000; \
  python3 scripts/export_citizen_snapshot.py \
    --db "$citizen_db" \
    --out "{{gh_pages_dir}}/citizen/data/citizen_votes.json" \
    --topic-set-id 1 \
    --computed-method votes \
    --fallback-snapshot "$citizen_fallback_votes" \
    --max-bytes 5000000; \
  python3 scripts/export_citizen_snapshot.py \
    --db "$citizen_db" \
    --out "{{gh_pages_dir}}/citizen/data/citizen_declared.json" \
    --topic-set-id 1 \
    --computed-method declared \
    --fallback-snapshot "$citizen_fallback_declared" \
    --max-bytes 5000000
  cp -R "{{gh_pages_dir}}/citizen/data/." "{{gh_pages_dir}}/legacy/citizen/data/"
  cp -R "{{gh_pages_dir}}/graph/data/." "{{gh_pages_dir}}/legacy/graph/data/"
  cp -R "{{gh_pages_dir}}/explorer-temas/data/." "{{gh_pages_dir}}/legacy/graph/data/"
  cp -R "{{gh_pages_dir}}/explorer-votaciones/data/." "{{gh_pages_dir}}/legacy/graph/data/"
  cp -R "{{gh_pages_dir}}/explorer-sources/data/." "{{gh_pages_dir}}/legacy/graph/data/"
  cp -R "{{gh_pages_dir}}/explorer-politico/data/." "{{gh_pages_dir}}/legacy/graph/data/"
  cp -R "{{gh_pages_dir}}/explorer-temas/data/." "{{gh_pages_dir}}/legacy/explorer-temas/data/"
  cp -R "{{gh_pages_dir}}/explorer-votaciones/data/." "{{gh_pages_dir}}/legacy/explorer-votaciones/data/"
  cp -R "{{gh_pages_dir}}/explorer-sources/data/." "{{gh_pages_dir}}/legacy/explorer-sources/data/"
  cp -R "{{gh_pages_dir}}/explorer-politico/data/." "{{gh_pages_dir}}/legacy/explorer-politico/data/"
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
  python3 scripts/report_citizen_concern_pack_quality.py \
    --snapshot "{{gh_pages_dir}}/citizen/data/citizen.json" \
    --concerns-config "{{gh_pages_dir}}/citizen/data/concerns_v1.json" \
    --out "{{gh_pages_dir}}/citizen/data/concern_pack_quality.json"
  python3 scripts/report_citizen_concern_pack_quality.py \
    --snapshot "{{gh_pages_dir}}/citizen/data/citizen_votes.json" \
    --concerns-config "{{gh_pages_dir}}/citizen/data/concerns_v1.json" \
    --out "{{gh_pages_dir}}/citizen/data/concern_pack_quality_votes.json"
  python3 scripts/report_citizen_concern_pack_quality.py \
    --snapshot "{{gh_pages_dir}}/citizen/data/citizen_declared.json" \
    --concerns-config "{{gh_pages_dir}}/citizen/data/concerns_v1.json" \
    --out "{{gh_pages_dir}}/citizen/data/concern_pack_quality_declared.json"
  cp "{{gh_pages_dir}}/citizen/data/concern_pack_quality.json" "{{gh_pages_dir}}/legacy/citizen/data/concern_pack_quality.json"
  mkdir -p "{{gh_pages_next_app_dir}}/public/legacy/citizen" "{{gh_pages_next_app_dir}}/public/legacy/citizen/data"
  cp -R ui/citizen/. "{{gh_pages_next_app_dir}}/public/legacy/citizen/"
  cp -R "{{gh_pages_dir}}/citizen/data/." "{{gh_pages_next_app_dir}}/public/legacy/citizen/data/"
  mkdir -p "{{gh_pages_next_app_dir}}/public/legacy/graph" "{{gh_pages_next_app_dir}}/public/legacy/graph/data"
  cp ui/graph/index.html "{{gh_pages_next_app_dir}}/public/legacy/graph/index.html"
  cp -R "{{gh_pages_dir}}/legacy/graph/data/." "{{gh_pages_next_app_dir}}/public/legacy/graph/data/"
  mkdir -p \
    "{{gh_pages_next_app_dir}}/public/legacy/explorer" "{{gh_pages_next_app_dir}}/public/legacy/explorer/data" \
    "{{gh_pages_next_app_dir}}/public/legacy/explorer-sources" "{{gh_pages_next_app_dir}}/public/legacy/explorer-sources/data" \
    "{{gh_pages_next_app_dir}}/public/legacy/explorer-temas" "{{gh_pages_next_app_dir}}/public/legacy/explorer-temas/data" \
    "{{gh_pages_next_app_dir}}/public/legacy/explorer-votaciones" "{{gh_pages_next_app_dir}}/public/legacy/explorer-votaciones/data" \
    "{{gh_pages_next_app_dir}}/public/legacy/explorer-politico" "{{gh_pages_next_app_dir}}/public/legacy/explorer-politico/data"
  cp ui/graph/explorer.html "{{gh_pages_next_app_dir}}/public/legacy/explorer/index.html"
  cp ui/graph/explorer-sources.html "{{gh_pages_next_app_dir}}/public/legacy/explorer-sources/index.html"
  cp ui/graph/explorer-temas.html "{{gh_pages_next_app_dir}}/public/legacy/explorer-temas/index.html"
  cp ui/graph/explorer-votaciones.html "{{gh_pages_next_app_dir}}/public/legacy/explorer-votaciones/index.html"
  cp ui/graph/explorer-sports.html "{{gh_pages_next_app_dir}}/public/legacy/explorer-politico/index.html"
  cp -R "{{gh_pages_dir}}/explorer-temas/data/." "{{gh_pages_next_app_dir}}/public/legacy/explorer-temas/data/"
  cp -R "{{gh_pages_dir}}/explorer-votaciones/data/." "{{gh_pages_next_app_dir}}/public/legacy/explorer-votaciones/data/"
  cp -R "{{gh_pages_dir}}/explorer-sources/data/." "{{gh_pages_next_app_dir}}/public/legacy/explorer-sources/data/"
  cp -R "{{gh_pages_dir}}/explorer-politico/data/." "{{gh_pages_next_app_dir}}/public/legacy/explorer-politico/data/"
  mkdir -p "{{gh_pages_next_app_dir}}/public/legal-sanctions/data"
  cp -f "{{gh_pages_dir}}/legal-sanctions/data/legal-sanctions.json" "{{gh_pages_next_app_dir}}/public/legal-sanctions/data/legal-sanctions.json"
  cp -f "{{gh_pages_dir}}/parliamentary-accountability/data/accountability.json" "{{gh_pages_next_app_dir}}/public/parliamentary-accountability/data/accountability.json"
  cp -f "{{gh_pages_dir}}/initiative-lifecycle/data/lifecycle.json" "{{gh_pages_next_app_dir}}/public/initiative-lifecycle/data/lifecycle.json"
  cp -f "{{gh_pages_dir}}/political-positions/data/stances.json" "{{gh_pages_next_app_dir}}/public/political-positions/data/stances.json"
  if [ -f "{{gh_pages_dir}}/political-positions/data/person-default-rows.json" ]; then \
    cp -f "{{gh_pages_dir}}/political-positions/data/person-default-rows.json" "{{gh_pages_next_app_dir}}/public/political-positions/data/person-default-rows.json"; \
  fi
  if [ -f "{{gh_pages_dir}}/political-positions/data/person-search-index.json" ]; then \
    cp -f "{{gh_pages_dir}}/political-positions/data/person-search-index.json" "{{gh_pages_next_app_dir}}/public/political-positions/data/person-search-index.json"; \
  fi
  if [ -f "{{gh_pages_dir}}/political-positions/data/topic-search-index.json" ]; then \
    cp -f "{{gh_pages_dir}}/political-positions/data/topic-search-index.json" "{{gh_pages_next_app_dir}}/public/political-positions/data/topic-search-index.json"; \
  fi
  if [ -d "{{gh_pages_dir}}/political-positions/data/person-sort-previews" ]; then \
    rm -rf "{{gh_pages_next_app_dir}}/public/political-positions/data/person-sort-previews"; \
    cp -R "{{gh_pages_dir}}/political-positions/data/person-sort-previews" "{{gh_pages_next_app_dir}}/public/political-positions/data/person-sort-previews"; \
  fi
  for src in "{{gh_pages_dir}}"/political-positions/data/*-trajectories.json; do \
    [ -f "$src" ] || continue; \
    cp -f "$src" "{{gh_pages_next_app_dir}}/public/political-positions/data/"; \
  done
  if [ -d "{{gh_pages_dir}}/political-positions/data/person-trajectory-chunks" ]; then \
    rm -rf "{{gh_pages_next_app_dir}}/public/political-positions/data/person-trajectory-chunks"; \
    cp -R "{{gh_pages_dir}}/political-positions/data/person-trajectory-chunks" "{{gh_pages_next_app_dir}}/public/political-positions/data/person-trajectory-chunks"; \
  fi
  if [ -d "{{gh_pages_dir}}/political-positions/data/person-details" ]; then \
    rm -rf "{{gh_pages_next_app_dir}}/public/political-positions/data/person-details"; \
    cp -R "{{gh_pages_dir}}/political-positions/data/person-details" "{{gh_pages_next_app_dir}}/public/political-positions/data/person-details"; \
  fi
  if [ -d "{{gh_pages_dir}}/political-positions/data/topic-person-rows" ]; then \
    rm -rf "{{gh_pages_next_app_dir}}/public/political-positions/data/topic-person-rows"; \
    cp -R "{{gh_pages_dir}}/political-positions/data/topic-person-rows" "{{gh_pages_next_app_dir}}/public/political-positions/data/topic-person-rows"; \
  fi
  cp -f "{{gh_pages_dir}}/elections-behavior/data/elections-behavior.json" "{{gh_pages_next_app_dir}}/public/elections-behavior/data/elections-behavior.json"
  mkdir -p "{{gh_pages_next_app_dir}}/public/elecciones/andalucia-2026/data"
  cp -f "{{gh_pages_dir}}/elecciones/andalucia-2026/data/accountability.json" "{{gh_pages_next_app_dir}}/public/elecciones/andalucia-2026/data/accountability.json"
  cp -f "{{gh_pages_dir}}/elecciones/andalucia-2026/data/delivery-evidence-hunt-results.json" "{{gh_pages_next_app_dir}}/public/elecciones/andalucia-2026/data/delivery-evidence-hunt-results.json"
  cp -f "{{gh_pages_dir}}/elecciones/andalucia-2026/data/delivery-evidence-review-drafts.json" "{{gh_pages_next_app_dir}}/public/elecciones/andalucia-2026/data/delivery-evidence-review-drafts.json"
  mkdir -p "{{gh_pages_next_app_dir}}/public/calendario-electoral/data"
  cp -f "{{gh_pages_dir}}/calendario-electoral/data/election-calendar.json" "{{gh_pages_next_app_dir}}/public/calendario-electoral/data/election-calendar.json"
  cp -f "{{gh_pages_dir}}/policy-outcomes/data/policy-outcomes.json" "{{gh_pages_next_app_dir}}/public/policy-outcomes/data/policy-outcomes.json"
  for rel in citizen/data graph/data explorer-politico/data explorer-sources/data explorer-temas/data explorer-votaciones/data calendario-electoral/data people/data; do \
    rm -rf "{{gh_pages_next_app_dir}}/public/$rel"; \
    mkdir -p "{{gh_pages_next_app_dir}}/public/$rel"; \
    cp -R "{{gh_pages_dir}}/$rel/." "{{gh_pages_next_app_dir}}/public/$rel/"; \
  done
  cp docs/ideal_sources_say_do.json "{{gh_pages_dir}}/explorer-sources/data/ideal.json"
  cp docs/ideal_sources_say_do.json "{{gh_pages_dir}}/legacy/graph/data/ideal.json"
  cp docs/ideal_sources_say_do.json "{{gh_pages_next_app_dir}}/public/explorer-sources/data/ideal.json"
  cp docs/ideal_sources_say_do.json "{{gh_pages_next_app_dir}}/public/legacy/graph/data/ideal.json"
  cd "{{gh_pages_next_app_dir}}" && NEXT_PUBLIC_BASE_PATH="{{gh_pages_next_base_path}}" node node_modules/next/dist/bin/next build --webpack
  python3 scripts/check_next_export_notfound_payloads.py --path "{{gh_pages_next_out_dir}}"
  just cloudflare-pages-size-check
  just privacy-check-public-artifacts
  @echo "Build Cloudflare Pages listo en {{gh_pages_next_out_dir}}"

privacy-check-public-artifacts:
  just real-data-only-check
  python3 scripts/check_public_privacy_leaks.py --path "{{gh_pages_next_out_dir}}" --path "{{gh_pages_dir}}" --path etl/data/published --path "{{gh_pages_next_app_dir}}/public"

repo-hygiene-check:
  python3 scripts/check_repo_root_hygiene.py

citizen-test-preset-codec:
  node --test tests/test_citizen_preset_codec.js tests/test_citizen_preset_recovery_ui_contract.js tests/test_report_citizen_preset_fixture_contract.js tests/test_report_citizen_preset_codec_parity.js tests/test_report_citizen_preset_codec_sync_state.js tests/test_report_citizen_preset_contract_bundle.js tests/test_report_citizen_preset_contract_bundle_history.js tests/test_report_citizen_preset_contract_bundle_history_window.js tests/test_report_citizen_preset_contract_bundle_history_compaction.js tests/test_report_citizen_preset_contract_bundle_history_slo.js tests/test_report_citizen_preset_contract_bundle_history_slo_digest.js tests/test_report_citizen_preset_contract_bundle_history_slo_digest_heartbeat.js tests/test_report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_window.js tests/test_report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction.js tests/test_report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window.js tests/test_report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest.js tests/test_report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat.js tests/test_report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_window.js tests/test_report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_compaction.js tests/test_report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.js

citizen-test-onboarding-funnel:
  node --test tests/test_citizen_onboarding_funnel.js tests/test_citizen_onboarding_ui_contract.js

citizen-test-first-answer-accelerator:
  node --test tests/test_citizen_first_answer_accelerator.js tests/test_citizen_first_answer_ui_contract.js

citizen-test-unknown-explainability:
  node --test tests/test_citizen_unknown_explainability.js tests/test_citizen_unknown_explainability_ui_contract.js

citizen-test-evidence-trust-panel:
  node --test tests/test_citizen_evidence_trust_panel.js tests/test_citizen_evidence_trust_panel_ui_contract.js

citizen-test-cross-method-stability:
  node --test tests/test_citizen_cross_method_stability.js tests/test_citizen_cross_method_stability_ui_contract.js

citizen-test-coherence-drilldown:
  node --test tests/test_citizen_coherence_drilldown_ui_contract.js tests/test_explorer_temas_coherence_drilldown_url_contract.js
  python3 -m unittest tests/test_graph_ui_server_coherence.py

citizen-test-accessibility-readability:
  node --test tests/test_citizen_accessibility_readability_ui_contract.js

citizen-test-explainability-copy:
  node --test tests/test_citizen_explainability_copy_ui_contract.js
  python3 -m unittest tests/test_report_citizen_explainability_copy.py

citizen-test-explainability-outcomes:
  node --test tests/test_citizen_explainability_outcomes_ui_contract.js
  python3 -m unittest tests/test_report_citizen_explainability_outcomes.py

citizen-test-explainability-outcomes-heartbeat:
  python3 -m unittest tests/test_report_citizen_explainability_outcomes_heartbeat.py tests/test_report_citizen_explainability_outcomes_heartbeat_window.py

citizen-test-coherence-drilldown-outcomes:
  python3 -m unittest tests/test_report_citizen_coherence_drilldown_outcomes.py tests/test_report_citizen_coherence_drilldown_outcomes_heartbeat.py tests/test_report_citizen_coherence_drilldown_outcomes_heartbeat_window.py tests/test_report_citizen_coherence_drilldown_outcomes_heartbeat_compaction.py tests/test_report_citizen_coherence_drilldown_outcomes_heartbeat_compaction_window.py

citizen-test-product-kpis-heartbeat:
  python3 -m unittest tests/test_report_citizen_product_kpis_heartbeat.py tests/test_report_citizen_product_kpis_heartbeat_window.py tests/test_report_citizen_product_kpis_heartbeat_compaction.py tests/test_report_citizen_product_kpis_heartbeat_compaction_window.py

citizen-test-mobile-performance:
  node --test tests/test_citizen_mobile_performance_ui_contract.js
  python3 -m unittest tests/test_report_citizen_mobile_performance_budget.py

citizen-test-mobile-observability:
  node --test tests/test_citizen_mobile_observability_ui_contract.js
  python3 -m unittest tests/test_report_citizen_mobile_observability.py

citizen-test-mobile-observability-heartbeat:
  python3 -m unittest tests/test_report_citizen_mobile_observability_heartbeat.py tests/test_report_citizen_mobile_observability_heartbeat_window.py tests/test_report_citizen_mobile_observability_heartbeat_compaction.py tests/test_report_citizen_mobile_observability_heartbeat_compaction_window.py

citizen-test-tailwind-md3:
  node --test tests/test_citizen_tailwind_md3_ui_contract.js
  python3 -m unittest tests/test_build_citizen_tailwind_md3_css.py tests/test_report_citizen_tailwind_md3_contract.py tests/test_report_citizen_tailwind_md3_visual_drift_digest.py tests/test_report_citizen_tailwind_md3_visual_drift_digest_heartbeat.py tests/test_report_citizen_tailwind_md3_visual_drift_digest_heartbeat_window.py tests/test_report_citizen_tailwind_md3_visual_drift_digest_heartbeat_compaction.py tests/test_report_citizen_tailwind_md3_visual_drift_digest_heartbeat_compaction_window.py tests/test_graph_ui_server_citizen_assets.py

citizen-test-concern-pack-quality:
  node --test tests/test_citizen_concern_pack_quality_ui_contract.js
  python3 -m unittest tests/test_report_citizen_concern_pack_quality.py

citizen-test-concern-pack-outcomes:
  node --test tests/test_citizen_concern_pack_outcomes_ui_contract.js
  python3 -m unittest tests/test_report_citizen_concern_pack_outcomes.py

citizen-test-concern-pack-outcomes-heartbeat:
  python3 -m unittest tests/test_report_citizen_concern_pack_outcomes_heartbeat.py tests/test_report_citizen_concern_pack_outcomes_heartbeat_window.py tests/test_report_citizen_concern_pack_outcomes_heartbeat_compaction.py tests/test_report_citizen_concern_pack_outcomes_heartbeat_compaction_window.py

citizen-test-trust-action-nudges:
  node --test tests/test_citizen_trust_action_nudges.js tests/test_citizen_trust_action_nudges_ui_contract.js
  python3 -m unittest tests/test_report_citizen_trust_action_nudges.py

citizen-test-trust-action-nudges-heartbeat:
  python3 -m unittest tests/test_report_citizen_trust_action_nudges_heartbeat.py tests/test_report_citizen_trust_action_nudges_heartbeat_window.py tests/test_report_citizen_trust_action_nudges_heartbeat_compaction.py tests/test_report_citizen_trust_action_nudges_heartbeat_compaction_window.py

citizen-test-release-hardening:
  node --test tests/test_report_citizen_release_hardening.js

citizen-test-release-trace-digest:
  node --test tests/test_report_citizen_release_trace_digest.js

citizen-test-release-trace-heartbeat:
  python3 -m unittest tests/test_report_citizen_release_trace_digest_heartbeat.py tests/test_report_citizen_release_trace_digest_heartbeat_window.py tests/test_report_citizen_release_trace_digest_heartbeat_compaction.py tests/test_report_citizen_release_trace_digest_heartbeat_compaction_window.py

citizen-release-regression-suite:
  just citizen-test-preset-codec
  just citizen-test-tailwind-md3
  just citizen-test-accessibility-readability
  just citizen-test-explainability-copy
  just citizen-test-explainability-outcomes
  just citizen-test-explainability-outcomes-heartbeat
  just citizen-test-product-kpis-heartbeat
  just citizen-test-mobile-observability-heartbeat
  just citizen-test-release-trace-digest
  just citizen-test-release-trace-heartbeat
  just citizen-test-evidence-trust-panel
  just citizen-test-cross-method-stability
  just citizen-test-coherence-drilldown
  just citizen-test-coherence-drilldown-outcomes
  just citizen-test-mobile-performance
  just citizen-test-mobile-observability
  just citizen-test-mobile-observability-heartbeat
  just citizen-test-first-answer-accelerator
  just citizen-test-unknown-explainability
  just citizen-test-concern-pack-quality
  just citizen-test-concern-pack-outcomes
  just citizen-test-concern-pack-outcomes-heartbeat
  just citizen-test-trust-action-nudges
  just citizen-test-trust-action-nudges-heartbeat

citizen-report-product-kpis:
  events_arg=""; \
  if [ -n "{{citizen_product_kpi_events}}" ]; then events_arg="--telemetry-events-jsonl {{citizen_product_kpi_events}}"; fi; \
  summary_arg=""; \
  if [ -n "{{citizen_product_kpi_summary}}" ]; then summary_arg="--telemetry-json {{citizen_product_kpi_summary}}"; fi; \
  out_arg=""; \
  if [ -n "{{citizen_product_kpi_out}}" ]; then out_arg="--out {{citizen_product_kpi_out}}"; fi; \
  python3 scripts/report_citizen_product_kpis.py --snapshot "{{citizen_product_kpi_snapshot}}" --max-unknown-rate "{{citizen_product_kpi_max_unknown_rate}}" --max-time-to-first-answer-seconds "{{citizen_product_kpi_max_tfa_seconds}}" --min-drilldown-click-rate "{{citizen_product_kpi_min_drilldown_rate}}" ${summary_arg} ${events_arg} ${out_arg}

citizen-check-product-kpis:
  events_arg=""; \
  if [ -n "{{citizen_product_kpi_events}}" ]; then events_arg="--telemetry-events-jsonl {{citizen_product_kpi_events}}"; fi; \
  summary_arg=""; \
  if [ -n "{{citizen_product_kpi_summary}}" ]; then summary_arg="--telemetry-json {{citizen_product_kpi_summary}}"; fi; \
  out_arg=""; \
  if [ -n "{{citizen_product_kpi_out}}" ]; then out_arg="--out {{citizen_product_kpi_out}}"; fi; \
  python3 scripts/report_citizen_product_kpis.py --snapshot "{{citizen_product_kpi_snapshot}}" --max-unknown-rate "{{citizen_product_kpi_max_unknown_rate}}" --max-time-to-first-answer-seconds "{{citizen_product_kpi_max_tfa_seconds}}" --min-drilldown-click-rate "{{citizen_product_kpi_min_drilldown_rate}}" --strict ${summary_arg} ${events_arg} ${out_arg}

citizen-check-product-kpis-complete:
  events_arg=""; \
  if [ -n "{{citizen_product_kpi_events}}" ]; then events_arg="--telemetry-events-jsonl {{citizen_product_kpi_events}}"; fi; \
  summary_arg=""; \
  if [ -n "{{citizen_product_kpi_summary}}" ]; then summary_arg="--telemetry-json {{citizen_product_kpi_summary}}"; fi; \
  out_arg=""; \
  if [ -n "{{citizen_product_kpi_out}}" ]; then out_arg="--out {{citizen_product_kpi_out}}"; fi; \
  python3 scripts/report_citizen_product_kpis.py --snapshot "{{citizen_product_kpi_snapshot}}" --max-unknown-rate "{{citizen_product_kpi_max_unknown_rate}}" --max-time-to-first-answer-seconds "{{citizen_product_kpi_max_tfa_seconds}}" --min-drilldown-click-rate "{{citizen_product_kpi_min_drilldown_rate}}" --strict --strict-require-complete ${summary_arg} ${events_arg} ${out_arg}

citizen-report-product-kpis-heartbeat:
  events_arg=""; \
  if [ -n "{{citizen_product_kpi_heartbeat_events}}" ]; then events_arg="--telemetry-events-jsonl {{citizen_product_kpi_heartbeat_events}}"; fi; \
  summary_arg=""; \
  if [ -n "{{citizen_product_kpi_heartbeat_summary}}" ]; then summary_arg="--telemetry-json {{citizen_product_kpi_heartbeat_summary}}"; fi; \
  python3 scripts/report_citizen_product_kpis.py --snapshot "{{citizen_product_kpi_snapshot}}" --max-unknown-rate "{{citizen_product_kpi_max_unknown_rate}}" --max-time-to-first-answer-seconds "{{citizen_product_kpi_max_tfa_seconds}}" --min-drilldown-click-rate "{{citizen_product_kpi_min_drilldown_rate}}" ${summary_arg} ${events_arg} --out "{{citizen_product_kpi_heartbeat_digest}}"
  out_arg=""; \
  if [ -n "{{citizen_product_kpi_heartbeat_out}}" ]; then out_arg="--out {{citizen_product_kpi_heartbeat_out}}"; fi; \
  python3 scripts/report_citizen_product_kpis_heartbeat.py --digest-json "{{citizen_product_kpi_heartbeat_digest}}" --heartbeat-jsonl "{{citizen_product_kpi_heartbeat_path}}" ${out_arg}

citizen-check-product-kpis-heartbeat:
  events_arg=""; \
  if [ -n "{{citizen_product_kpi_heartbeat_events}}" ]; then events_arg="--telemetry-events-jsonl {{citizen_product_kpi_heartbeat_events}}"; fi; \
  summary_arg=""; \
  if [ -n "{{citizen_product_kpi_heartbeat_summary}}" ]; then summary_arg="--telemetry-json {{citizen_product_kpi_heartbeat_summary}}"; fi; \
  python3 scripts/report_citizen_product_kpis.py --snapshot "{{citizen_product_kpi_snapshot}}" --max-unknown-rate "{{citizen_product_kpi_max_unknown_rate}}" --max-time-to-first-answer-seconds "{{citizen_product_kpi_max_tfa_seconds}}" --min-drilldown-click-rate "{{citizen_product_kpi_min_drilldown_rate}}" --strict --strict-require-complete ${summary_arg} ${events_arg} --out "{{citizen_product_kpi_heartbeat_digest}}"
  out_arg=""; \
  if [ -n "{{citizen_product_kpi_heartbeat_out}}" ]; then out_arg="--out {{citizen_product_kpi_heartbeat_out}}"; fi; \
  python3 scripts/report_citizen_product_kpis_heartbeat.py --digest-json "{{citizen_product_kpi_heartbeat_digest}}" --heartbeat-jsonl "{{citizen_product_kpi_heartbeat_path}}" --strict ${out_arg}

citizen-report-product-kpis-heartbeat-window:
  out_arg=""; \
  if [ -n "{{citizen_product_kpi_heartbeat_window_out}}" ]; then out_arg="--out {{citizen_product_kpi_heartbeat_window_out}}"; fi; \
  python3 scripts/report_citizen_product_kpis_heartbeat_window.py --heartbeat-jsonl "{{citizen_product_kpi_heartbeat_path}}" --last "{{citizen_product_kpi_heartbeat_window_last}}" --max-failed "{{citizen_product_kpi_heartbeat_window_max_failed}}" --max-failed-rate-pct "{{citizen_product_kpi_heartbeat_window_max_failed_rate_pct}}" --max-degraded "{{citizen_product_kpi_heartbeat_window_max_degraded}}" --max-degraded-rate-pct "{{citizen_product_kpi_heartbeat_window_max_degraded_rate_pct}}" --max-contract-incomplete "{{citizen_product_kpi_heartbeat_window_max_contract_incomplete}}" --max-contract-incomplete-rate-pct "{{citizen_product_kpi_heartbeat_window_max_contract_incomplete_rate_pct}}" --max-unknown-rate-violations "{{citizen_product_kpi_heartbeat_window_max_unknown_rate_violations}}" --max-unknown-rate-violation-rate-pct "{{citizen_product_kpi_heartbeat_window_max_unknown_rate_violation_rate_pct}}" --max-tfa-violations "{{citizen_product_kpi_heartbeat_window_max_tfa_violations}}" --max-tfa-violation-rate-pct "{{citizen_product_kpi_heartbeat_window_max_tfa_violation_rate_pct}}" --max-drilldown-violations "{{citizen_product_kpi_heartbeat_window_max_drilldown_violations}}" --max-drilldown-violation-rate-pct "{{citizen_product_kpi_heartbeat_window_max_drilldown_violation_rate_pct}}" ${out_arg}

citizen-check-product-kpis-heartbeat-window:
  out_arg=""; \
  if [ -n "{{citizen_product_kpi_heartbeat_window_out}}" ]; then out_arg="--out {{citizen_product_kpi_heartbeat_window_out}}"; fi; \
  python3 scripts/report_citizen_product_kpis_heartbeat_window.py --heartbeat-jsonl "{{citizen_product_kpi_heartbeat_path}}" --last "{{citizen_product_kpi_heartbeat_window_last}}" --max-failed "{{citizen_product_kpi_heartbeat_window_max_failed}}" --max-failed-rate-pct "{{citizen_product_kpi_heartbeat_window_max_failed_rate_pct}}" --max-degraded "{{citizen_product_kpi_heartbeat_window_max_degraded}}" --max-degraded-rate-pct "{{citizen_product_kpi_heartbeat_window_max_degraded_rate_pct}}" --max-contract-incomplete "{{citizen_product_kpi_heartbeat_window_max_contract_incomplete}}" --max-contract-incomplete-rate-pct "{{citizen_product_kpi_heartbeat_window_max_contract_incomplete_rate_pct}}" --max-unknown-rate-violations "{{citizen_product_kpi_heartbeat_window_max_unknown_rate_violations}}" --max-unknown-rate-violation-rate-pct "{{citizen_product_kpi_heartbeat_window_max_unknown_rate_violation_rate_pct}}" --max-tfa-violations "{{citizen_product_kpi_heartbeat_window_max_tfa_violations}}" --max-tfa-violation-rate-pct "{{citizen_product_kpi_heartbeat_window_max_tfa_violation_rate_pct}}" --max-drilldown-violations "{{citizen_product_kpi_heartbeat_window_max_drilldown_violations}}" --max-drilldown-violation-rate-pct "{{citizen_product_kpi_heartbeat_window_max_drilldown_violation_rate_pct}}" --strict ${out_arg}

citizen-report-product-kpis-heartbeat-compact:
  out_arg=""; \
  if [ -n "{{citizen_product_kpi_heartbeat_compact_out}}" ]; then out_arg="--out {{citizen_product_kpi_heartbeat_compact_out}}"; fi; \
  python3 scripts/report_citizen_product_kpis_heartbeat_compaction.py --heartbeat-jsonl "{{citizen_product_kpi_heartbeat_path}}" --compacted-jsonl "{{citizen_product_kpi_heartbeat_compact_path}}" --keep-recent "{{citizen_product_kpi_heartbeat_compact_recent}}" --keep-mid-span "{{citizen_product_kpi_heartbeat_compact_mid_span}}" --keep-mid-every "{{citizen_product_kpi_heartbeat_compact_mid_every}}" --keep-old-every "{{citizen_product_kpi_heartbeat_compact_old_every}}" --min-raw-for-dropped-check "{{citizen_product_kpi_heartbeat_compact_min_raw}}" ${out_arg}

citizen-check-product-kpis-heartbeat-compact:
  out_arg=""; \
  if [ -n "{{citizen_product_kpi_heartbeat_compact_out}}" ]; then out_arg="--out {{citizen_product_kpi_heartbeat_compact_out}}"; fi; \
  python3 scripts/report_citizen_product_kpis_heartbeat_compaction.py --heartbeat-jsonl "{{citizen_product_kpi_heartbeat_path}}" --compacted-jsonl "{{citizen_product_kpi_heartbeat_compact_path}}" --keep-recent "{{citizen_product_kpi_heartbeat_compact_recent}}" --keep-mid-span "{{citizen_product_kpi_heartbeat_compact_mid_span}}" --keep-mid-every "{{citizen_product_kpi_heartbeat_compact_mid_every}}" --keep-old-every "{{citizen_product_kpi_heartbeat_compact_old_every}}" --min-raw-for-dropped-check "{{citizen_product_kpi_heartbeat_compact_min_raw}}" --strict ${out_arg}

citizen-report-product-kpis-heartbeat-compact-window:
  out_arg=""; \
  if [ -n "{{citizen_product_kpi_heartbeat_compact_window_out}}" ]; then out_arg="--out {{citizen_product_kpi_heartbeat_compact_window_out}}"; fi; \
  python3 scripts/report_citizen_product_kpis_heartbeat_compaction_window.py --heartbeat-jsonl "{{citizen_product_kpi_heartbeat_path}}" --compacted-jsonl "{{citizen_product_kpi_heartbeat_compact_path}}" --last "{{citizen_product_kpi_heartbeat_compact_window_last}}" ${out_arg}

citizen-check-product-kpis-heartbeat-compact-window:
  out_arg=""; \
  if [ -n "{{citizen_product_kpi_heartbeat_compact_window_out}}" ]; then out_arg="--out {{citizen_product_kpi_heartbeat_compact_window_out}}"; fi; \
  python3 scripts/report_citizen_product_kpis_heartbeat_compaction_window.py --heartbeat-jsonl "{{citizen_product_kpi_heartbeat_path}}" --compacted-jsonl "{{citizen_product_kpi_heartbeat_compact_path}}" --last "{{citizen_product_kpi_heartbeat_compact_window_last}}" --strict ${out_arg}

citizen-report-mobile-performance-budget:
  out_arg=""; \
  if [ -n "{{citizen_mobile_perf_out}}" ]; then out_arg="--out {{citizen_mobile_perf_out}}"; fi; \
  python3 scripts/report_citizen_mobile_performance_budget.py --ui-html "{{citizen_mobile_perf_ui_html}}" --ui-assets "{{citizen_mobile_perf_ui_assets}}" --snapshot "{{citizen_mobile_perf_snapshot}}" --max-ui-html-bytes "{{citizen_mobile_perf_max_ui_html_bytes}}" --max-ui-assets-total-bytes "{{citizen_mobile_perf_max_ui_assets_total_bytes}}" --max-snapshot-bytes "{{citizen_mobile_perf_max_snapshot_bytes}}" ${out_arg}

citizen-check-mobile-performance-budget:
  out_arg=""; \
  if [ -n "{{citizen_mobile_perf_out}}" ]; then out_arg="--out {{citizen_mobile_perf_out}}"; fi; \
  python3 scripts/report_citizen_mobile_performance_budget.py --ui-html "{{citizen_mobile_perf_ui_html}}" --ui-assets "{{citizen_mobile_perf_ui_assets}}" --snapshot "{{citizen_mobile_perf_snapshot}}" --max-ui-html-bytes "{{citizen_mobile_perf_max_ui_html_bytes}}" --max-ui-assets-total-bytes "{{citizen_mobile_perf_max_ui_assets_total_bytes}}" --max-snapshot-bytes "{{citizen_mobile_perf_max_snapshot_bytes}}" --strict ${out_arg}

citizen-report-mobile-observability:
  events_arg=""; \
  if [ -n "{{citizen_mobile_obs_events}}" ]; then events_arg="--telemetry-events-jsonl {{citizen_mobile_obs_events}}"; fi; \
  summary_arg=""; \
  if [ -n "{{citizen_mobile_obs_summary}}" ]; then summary_arg="--telemetry-json {{citizen_mobile_obs_summary}}"; fi; \
  out_arg=""; \
  if [ -n "{{citizen_mobile_obs_out}}" ]; then out_arg="--out {{citizen_mobile_obs_out}}"; fi; \
  python3 scripts/report_citizen_mobile_observability.py --min-samples "{{citizen_mobile_obs_min_samples}}" --max-input-to-render-p50-ms "{{citizen_mobile_obs_max_p50_ms}}" --max-input-to-render-p90-ms "{{citizen_mobile_obs_max_p90_ms}}" ${summary_arg} ${events_arg} ${out_arg}

citizen-check-mobile-observability:
  events_arg=""; \
  if [ -n "{{citizen_mobile_obs_events}}" ]; then events_arg="--telemetry-events-jsonl {{citizen_mobile_obs_events}}"; fi; \
  summary_arg=""; \
  if [ -n "{{citizen_mobile_obs_summary}}" ]; then summary_arg="--telemetry-json {{citizen_mobile_obs_summary}}"; fi; \
  out_arg=""; \
  if [ -n "{{citizen_mobile_obs_out}}" ]; then out_arg="--out {{citizen_mobile_obs_out}}"; fi; \
  python3 scripts/report_citizen_mobile_observability.py --min-samples "{{citizen_mobile_obs_min_samples}}" --max-input-to-render-p50-ms "{{citizen_mobile_obs_max_p50_ms}}" --max-input-to-render-p90-ms "{{citizen_mobile_obs_max_p90_ms}}" --strict --strict-require-complete ${summary_arg} ${events_arg} ${out_arg}

citizen-report-mobile-observability-heartbeat:
  out_arg=""; \
  if [ -n "{{citizen_mobile_obs_heartbeat_out}}" ]; then out_arg="--out {{citizen_mobile_obs_heartbeat_out}}"; fi; \
  python3 scripts/report_citizen_mobile_observability_heartbeat.py --observability-json "{{citizen_mobile_obs_heartbeat_digest}}" --heartbeat-jsonl "{{citizen_mobile_obs_heartbeat_path}}" ${out_arg}

citizen-check-mobile-observability-heartbeat:
  out_arg=""; \
  if [ -n "{{citizen_mobile_obs_heartbeat_out}}" ]; then out_arg="--out {{citizen_mobile_obs_heartbeat_out}}"; fi; \
  python3 scripts/report_citizen_mobile_observability_heartbeat.py --observability-json "{{citizen_mobile_obs_heartbeat_digest}}" --heartbeat-jsonl "{{citizen_mobile_obs_heartbeat_path}}" --strict ${out_arg}

citizen-report-mobile-observability-heartbeat-window:
  out_arg=""; \
  if [ -n "{{citizen_mobile_obs_heartbeat_window_out}}" ]; then out_arg="--out {{citizen_mobile_obs_heartbeat_window_out}}"; fi; \
  python3 scripts/report_citizen_mobile_observability_heartbeat_window.py --heartbeat-jsonl "{{citizen_mobile_obs_heartbeat_path}}" --last "{{citizen_mobile_obs_heartbeat_window_last}}" --max-failed "{{citizen_mobile_obs_heartbeat_window_max_failed}}" --max-failed-rate-pct "{{citizen_mobile_obs_heartbeat_window_max_failed_rate_pct}}" --max-degraded "{{citizen_mobile_obs_heartbeat_window_max_degraded}}" --max-degraded-rate-pct "{{citizen_mobile_obs_heartbeat_window_max_degraded_rate_pct}}" --max-p90-threshold-violations "{{citizen_mobile_obs_heartbeat_window_max_p90_threshold_violations}}" --max-p90-threshold-violation-rate-pct "{{citizen_mobile_obs_heartbeat_window_max_p90_threshold_violation_rate_pct}}" ${out_arg}

citizen-check-mobile-observability-heartbeat-window:
  out_arg=""; \
  if [ -n "{{citizen_mobile_obs_heartbeat_window_out}}" ]; then out_arg="--out {{citizen_mobile_obs_heartbeat_window_out}}"; fi; \
  python3 scripts/report_citizen_mobile_observability_heartbeat_window.py --heartbeat-jsonl "{{citizen_mobile_obs_heartbeat_path}}" --last "{{citizen_mobile_obs_heartbeat_window_last}}" --max-failed "{{citizen_mobile_obs_heartbeat_window_max_failed}}" --max-failed-rate-pct "{{citizen_mobile_obs_heartbeat_window_max_failed_rate_pct}}" --max-degraded "{{citizen_mobile_obs_heartbeat_window_max_degraded}}" --max-degraded-rate-pct "{{citizen_mobile_obs_heartbeat_window_max_degraded_rate_pct}}" --max-p90-threshold-violations "{{citizen_mobile_obs_heartbeat_window_max_p90_threshold_violations}}" --max-p90-threshold-violation-rate-pct "{{citizen_mobile_obs_heartbeat_window_max_p90_threshold_violation_rate_pct}}" --strict ${out_arg}

citizen-report-mobile-observability-heartbeat-compact:
  out_arg=""; \
  if [ -n "{{citizen_mobile_obs_heartbeat_compact_out}}" ]; then out_arg="--out {{citizen_mobile_obs_heartbeat_compact_out}}"; fi; \
  python3 scripts/report_citizen_mobile_observability_heartbeat_compaction.py --heartbeat-jsonl "{{citizen_mobile_obs_heartbeat_path}}" --compacted-jsonl "{{citizen_mobile_obs_heartbeat_compact_path}}" --keep-recent "{{citizen_mobile_obs_heartbeat_compact_recent}}" --keep-mid-span "{{citizen_mobile_obs_heartbeat_compact_mid_span}}" --keep-mid-every "{{citizen_mobile_obs_heartbeat_compact_mid_every}}" --keep-old-every "{{citizen_mobile_obs_heartbeat_compact_old_every}}" --min-raw-for-dropped-check "{{citizen_mobile_obs_heartbeat_compact_min_raw}}" ${out_arg}

citizen-check-mobile-observability-heartbeat-compact:
  out_arg=""; \
  if [ -n "{{citizen_mobile_obs_heartbeat_compact_out}}" ]; then out_arg="--out {{citizen_mobile_obs_heartbeat_compact_out}}"; fi; \
  python3 scripts/report_citizen_mobile_observability_heartbeat_compaction.py --heartbeat-jsonl "{{citizen_mobile_obs_heartbeat_path}}" --compacted-jsonl "{{citizen_mobile_obs_heartbeat_compact_path}}" --keep-recent "{{citizen_mobile_obs_heartbeat_compact_recent}}" --keep-mid-span "{{citizen_mobile_obs_heartbeat_compact_mid_span}}" --keep-mid-every "{{citizen_mobile_obs_heartbeat_compact_mid_every}}" --keep-old-every "{{citizen_mobile_obs_heartbeat_compact_old_every}}" --min-raw-for-dropped-check "{{citizen_mobile_obs_heartbeat_compact_min_raw}}" --strict ${out_arg}

citizen-report-mobile-observability-heartbeat-compact-window:
  out_arg=""; \
  if [ -n "{{citizen_mobile_obs_heartbeat_compact_window_out}}" ]; then out_arg="--out {{citizen_mobile_obs_heartbeat_compact_window_out}}"; fi; \
  python3 scripts/report_citizen_mobile_observability_heartbeat_compaction_window.py --heartbeat-jsonl "{{citizen_mobile_obs_heartbeat_path}}" --compacted-jsonl "{{citizen_mobile_obs_heartbeat_compact_path}}" --last "{{citizen_mobile_obs_heartbeat_compact_window_last}}" ${out_arg}

citizen-check-mobile-observability-heartbeat-compact-window:
  out_arg=""; \
  if [ -n "{{citizen_mobile_obs_heartbeat_compact_window_out}}" ]; then out_arg="--out {{citizen_mobile_obs_heartbeat_compact_window_out}}"; fi; \
  python3 scripts/report_citizen_mobile_observability_heartbeat_compaction_window.py --heartbeat-jsonl "{{citizen_mobile_obs_heartbeat_path}}" --compacted-jsonl "{{citizen_mobile_obs_heartbeat_compact_path}}" --last "{{citizen_mobile_obs_heartbeat_compact_window_last}}" --strict ${out_arg}

citizen-build-tailwind-md3:
  python3 scripts/build_citizen_tailwind_md3_css.py --tokens "{{citizen_tailwind_md3_tokens}}" --out "{{citizen_tailwind_md3_css}}"

citizen-check-tailwind-md3-sync:
  python3 scripts/build_citizen_tailwind_md3_css.py --tokens "{{citizen_tailwind_md3_tokens}}" --out "{{citizen_tailwind_md3_css}}" --check

citizen-report-tailwind-md3:
  out_arg=""; \
  if [ -n "{{citizen_tailwind_md3_out}}" ]; then out_arg="--out {{citizen_tailwind_md3_out}}"; fi; \
  python3 scripts/report_citizen_tailwind_md3_contract.py --tokens "{{citizen_tailwind_md3_tokens}}" --generated-css "{{citizen_tailwind_md3_css}}" --ui-html "{{citizen_mobile_perf_ui_html}}" --max-generated-css-bytes "{{citizen_tailwind_md3_max_css_bytes}}" --min-md3-card-markers "{{citizen_tailwind_md3_min_card_markers}}" --min-md3-chip-markers "{{citizen_tailwind_md3_min_chip_markers}}" --min-md3-button-markers "{{citizen_tailwind_md3_min_button_markers}}" --min-md3-tab-markers "{{citizen_tailwind_md3_min_tab_markers}}" ${out_arg}

citizen-check-tailwind-md3:
  out_arg=""; \
  if [ -n "{{citizen_tailwind_md3_out}}" ]; then out_arg="--out {{citizen_tailwind_md3_out}}"; fi; \
  python3 scripts/report_citizen_tailwind_md3_contract.py --tokens "{{citizen_tailwind_md3_tokens}}" --generated-css "{{citizen_tailwind_md3_css}}" --ui-html "{{citizen_mobile_perf_ui_html}}" --max-generated-css-bytes "{{citizen_tailwind_md3_max_css_bytes}}" --min-md3-card-markers "{{citizen_tailwind_md3_min_card_markers}}" --min-md3-chip-markers "{{citizen_tailwind_md3_min_chip_markers}}" --min-md3-button-markers "{{citizen_tailwind_md3_min_button_markers}}" --min-md3-tab-markers "{{citizen_tailwind_md3_min_tab_markers}}" --strict ${out_arg}

citizen-report-tailwind-md3-drift-digest:
  python3 scripts/report_citizen_tailwind_md3_contract.py --tokens "{{citizen_tailwind_md3_tokens}}" --generated-css "{{citizen_tailwind_md3_css}}" --ui-html "{{citizen_mobile_perf_ui_html}}" --max-generated-css-bytes "{{citizen_tailwind_md3_max_css_bytes}}" --min-md3-card-markers "{{citizen_tailwind_md3_min_card_markers}}" --min-md3-chip-markers "{{citizen_tailwind_md3_min_chip_markers}}" --min-md3-button-markers "{{citizen_tailwind_md3_min_button_markers}}" --min-md3-tab-markers "{{citizen_tailwind_md3_min_tab_markers}}" --out "{{citizen_tailwind_md3_drift_contract}}"
  out_arg=""; \
  if [ -n "{{citizen_tailwind_md3_drift_out}}" ]; then out_arg="--out {{citizen_tailwind_md3_drift_out}}"; fi; \
  python3 scripts/report_citizen_tailwind_md3_visual_drift_digest.py --tailwind-contract-json "{{citizen_tailwind_md3_drift_contract}}" --source-tokens "{{citizen_tailwind_md3_tokens}}" --source-css "{{citizen_tailwind_md3_css}}" --source-ui-html "{{citizen_mobile_perf_ui_html}}" --published-tokens "{{citizen_tailwind_md3_drift_published_tokens}}" --published-data-tokens "{{citizen_tailwind_md3_drift_published_data_tokens}}" --published-css "{{citizen_tailwind_md3_drift_published_css}}" --published-ui-html "{{citizen_tailwind_md3_drift_published_ui_html}}" ${out_arg}

citizen-check-tailwind-md3-drift-digest:
  python3 scripts/report_citizen_tailwind_md3_contract.py --tokens "{{citizen_tailwind_md3_tokens}}" --generated-css "{{citizen_tailwind_md3_css}}" --ui-html "{{citizen_mobile_perf_ui_html}}" --max-generated-css-bytes "{{citizen_tailwind_md3_max_css_bytes}}" --min-md3-card-markers "{{citizen_tailwind_md3_min_card_markers}}" --min-md3-chip-markers "{{citizen_tailwind_md3_min_chip_markers}}" --min-md3-button-markers "{{citizen_tailwind_md3_min_button_markers}}" --min-md3-tab-markers "{{citizen_tailwind_md3_min_tab_markers}}" --strict --out "{{citizen_tailwind_md3_drift_contract}}"
  out_arg=""; \
  if [ -n "{{citizen_tailwind_md3_drift_out}}" ]; then out_arg="--out {{citizen_tailwind_md3_drift_out}}"; fi; \
  python3 scripts/report_citizen_tailwind_md3_visual_drift_digest.py --tailwind-contract-json "{{citizen_tailwind_md3_drift_contract}}" --source-tokens "{{citizen_tailwind_md3_tokens}}" --source-css "{{citizen_tailwind_md3_css}}" --source-ui-html "{{citizen_mobile_perf_ui_html}}" --published-tokens "{{citizen_tailwind_md3_drift_published_tokens}}" --published-data-tokens "{{citizen_tailwind_md3_drift_published_data_tokens}}" --published-css "{{citizen_tailwind_md3_drift_published_css}}" --published-ui-html "{{citizen_tailwind_md3_drift_published_ui_html}}" --strict --strict-require-complete ${out_arg}

citizen-report-tailwind-md3-drift-heartbeat:
  out_arg=""; \
  if [ -n "{{citizen_tailwind_md3_drift_heartbeat_out}}" ]; then out_arg="--out {{citizen_tailwind_md3_drift_heartbeat_out}}"; fi; \
  python3 scripts/report_citizen_tailwind_md3_visual_drift_digest_heartbeat.py --digest-json "{{citizen_tailwind_md3_drift_out}}" --heartbeat-jsonl "{{citizen_tailwind_md3_drift_heartbeat_path}}" ${out_arg}

citizen-check-tailwind-md3-drift-heartbeat:
  out_arg=""; \
  if [ -n "{{citizen_tailwind_md3_drift_heartbeat_out}}" ]; then out_arg="--out {{citizen_tailwind_md3_drift_heartbeat_out}}"; fi; \
  python3 scripts/report_citizen_tailwind_md3_visual_drift_digest_heartbeat.py --digest-json "{{citizen_tailwind_md3_drift_out}}" --heartbeat-jsonl "{{citizen_tailwind_md3_drift_heartbeat_path}}" --strict ${out_arg}

citizen-report-tailwind-md3-drift-heartbeat-window:
  out_arg=""; \
  if [ -n "{{citizen_tailwind_md3_drift_heartbeat_window_out}}" ]; then out_arg="--out {{citizen_tailwind_md3_drift_heartbeat_window_out}}"; fi; \
  python3 scripts/report_citizen_tailwind_md3_visual_drift_digest_heartbeat_window.py --heartbeat-jsonl "{{citizen_tailwind_md3_drift_heartbeat_path}}" --last "{{citizen_tailwind_md3_drift_heartbeat_window_last}}" --max-failed "{{citizen_tailwind_md3_drift_heartbeat_window_max_failed}}" --max-failed-rate-pct "{{citizen_tailwind_md3_drift_heartbeat_window_max_failed_rate_pct}}" --max-degraded "{{citizen_tailwind_md3_drift_heartbeat_window_max_degraded}}" --max-degraded-rate-pct "{{citizen_tailwind_md3_drift_heartbeat_window_max_degraded_rate_pct}}" --max-parity-mismatch "{{citizen_tailwind_md3_drift_heartbeat_window_max_parity_mismatch}}" --max-parity-mismatch-rate-pct "{{citizen_tailwind_md3_drift_heartbeat_window_max_parity_mismatch_rate_pct}}" --max-tokens-parity-mismatch "{{citizen_tailwind_md3_drift_heartbeat_window_max_tokens_parity_mismatch}}" --max-tokens-data-parity-mismatch "{{citizen_tailwind_md3_drift_heartbeat_window_max_tokens_data_parity_mismatch}}" --max-css-parity-mismatch "{{citizen_tailwind_md3_drift_heartbeat_window_max_css_parity_mismatch}}" --max-ui-html-parity-mismatch "{{citizen_tailwind_md3_drift_heartbeat_window_max_ui_html_parity_mismatch}}" --max-marker-mismatch "{{citizen_tailwind_md3_drift_heartbeat_window_max_marker_mismatch}}" ${out_arg}

citizen-check-tailwind-md3-drift-heartbeat-window:
  out_arg=""; \
  if [ -n "{{citizen_tailwind_md3_drift_heartbeat_window_out}}" ]; then out_arg="--out {{citizen_tailwind_md3_drift_heartbeat_window_out}}"; fi; \
  python3 scripts/report_citizen_tailwind_md3_visual_drift_digest_heartbeat_window.py --heartbeat-jsonl "{{citizen_tailwind_md3_drift_heartbeat_path}}" --last "{{citizen_tailwind_md3_drift_heartbeat_window_last}}" --max-failed "{{citizen_tailwind_md3_drift_heartbeat_window_max_failed}}" --max-failed-rate-pct "{{citizen_tailwind_md3_drift_heartbeat_window_max_failed_rate_pct}}" --max-degraded "{{citizen_tailwind_md3_drift_heartbeat_window_max_degraded}}" --max-degraded-rate-pct "{{citizen_tailwind_md3_drift_heartbeat_window_max_degraded_rate_pct}}" --max-parity-mismatch "{{citizen_tailwind_md3_drift_heartbeat_window_max_parity_mismatch}}" --max-parity-mismatch-rate-pct "{{citizen_tailwind_md3_drift_heartbeat_window_max_parity_mismatch_rate_pct}}" --max-tokens-parity-mismatch "{{citizen_tailwind_md3_drift_heartbeat_window_max_tokens_parity_mismatch}}" --max-tokens-data-parity-mismatch "{{citizen_tailwind_md3_drift_heartbeat_window_max_tokens_data_parity_mismatch}}" --max-css-parity-mismatch "{{citizen_tailwind_md3_drift_heartbeat_window_max_css_parity_mismatch}}" --max-ui-html-parity-mismatch "{{citizen_tailwind_md3_drift_heartbeat_window_max_ui_html_parity_mismatch}}" --max-marker-mismatch "{{citizen_tailwind_md3_drift_heartbeat_window_max_marker_mismatch}}" --strict ${out_arg}

citizen-report-tailwind-md3-drift-heartbeat-compact:
  out_arg=""; \
  if [ -n "{{citizen_tailwind_md3_drift_heartbeat_compact_out}}" ]; then out_arg="--out {{citizen_tailwind_md3_drift_heartbeat_compact_out}}"; fi; \
  python3 scripts/report_citizen_tailwind_md3_visual_drift_digest_heartbeat_compaction.py --heartbeat-jsonl "{{citizen_tailwind_md3_drift_heartbeat_path}}" --compacted-jsonl "{{citizen_tailwind_md3_drift_heartbeat_compact_path}}" --keep-recent "{{citizen_tailwind_md3_drift_heartbeat_compact_recent}}" --keep-mid-span "{{citizen_tailwind_md3_drift_heartbeat_compact_mid_span}}" --keep-mid-every "{{citizen_tailwind_md3_drift_heartbeat_compact_mid_every}}" --keep-old-every "{{citizen_tailwind_md3_drift_heartbeat_compact_old_every}}" --min-raw-for-dropped-check "{{citizen_tailwind_md3_drift_heartbeat_compact_min_raw}}" ${out_arg}

citizen-check-tailwind-md3-drift-heartbeat-compact:
  out_arg=""; \
  if [ -n "{{citizen_tailwind_md3_drift_heartbeat_compact_out}}" ]; then out_arg="--out {{citizen_tailwind_md3_drift_heartbeat_compact_out}}"; fi; \
  python3 scripts/report_citizen_tailwind_md3_visual_drift_digest_heartbeat_compaction.py --heartbeat-jsonl "{{citizen_tailwind_md3_drift_heartbeat_path}}" --compacted-jsonl "{{citizen_tailwind_md3_drift_heartbeat_compact_path}}" --keep-recent "{{citizen_tailwind_md3_drift_heartbeat_compact_recent}}" --keep-mid-span "{{citizen_tailwind_md3_drift_heartbeat_compact_mid_span}}" --keep-mid-every "{{citizen_tailwind_md3_drift_heartbeat_compact_mid_every}}" --keep-old-every "{{citizen_tailwind_md3_drift_heartbeat_compact_old_every}}" --min-raw-for-dropped-check "{{citizen_tailwind_md3_drift_heartbeat_compact_min_raw}}" --strict ${out_arg}

citizen-report-tailwind-md3-drift-heartbeat-compact-window:
  out_arg=""; \
  if [ -n "{{citizen_tailwind_md3_drift_heartbeat_compact_window_out}}" ]; then out_arg="--out {{citizen_tailwind_md3_drift_heartbeat_compact_window_out}}"; fi; \
  python3 scripts/report_citizen_tailwind_md3_visual_drift_digest_heartbeat_compaction_window.py --heartbeat-jsonl "{{citizen_tailwind_md3_drift_heartbeat_path}}" --compacted-jsonl "{{citizen_tailwind_md3_drift_heartbeat_compact_path}}" --last "{{citizen_tailwind_md3_drift_heartbeat_compact_window_last}}" ${out_arg}

citizen-check-tailwind-md3-drift-heartbeat-compact-window:
  out_arg=""; \
  if [ -n "{{citizen_tailwind_md3_drift_heartbeat_compact_window_out}}" ]; then out_arg="--out {{citizen_tailwind_md3_drift_heartbeat_compact_window_out}}"; fi; \
  python3 scripts/report_citizen_tailwind_md3_visual_drift_digest_heartbeat_compaction_window.py --heartbeat-jsonl "{{citizen_tailwind_md3_drift_heartbeat_path}}" --compacted-jsonl "{{citizen_tailwind_md3_drift_heartbeat_compact_path}}" --last "{{citizen_tailwind_md3_drift_heartbeat_compact_window_last}}" --strict ${out_arg}

citizen-report-concern-pack-quality:
  out_arg=""; \
  if [ -n "{{citizen_pack_quality_out}}" ]; then out_arg="--out {{citizen_pack_quality_out}}"; fi; \
  python3 scripts/report_citizen_concern_pack_quality.py --snapshot "{{citizen_pack_quality_snapshot}}" --concerns-config "{{citizen_pack_quality_concerns}}" --min-topics-per-pack "{{citizen_pack_quality_min_topics_per_pack}}" --min-clear-cells-pct "{{citizen_pack_quality_min_clear_cells_pct}}" --max-unknown-cells-pct "{{citizen_pack_quality_max_unknown_cells_pct}}" --min-confidence-avg-signal "{{citizen_pack_quality_min_confidence_avg_signal}}" --min-high-stakes-share "{{citizen_pack_quality_min_high_stakes_share}}" --max-weak-packs "{{citizen_pack_quality_max_weak_packs}}" ${out_arg}

citizen-check-concern-pack-quality:
  out_arg=""; \
  if [ -n "{{citizen_pack_quality_out}}" ]; then out_arg="--out {{citizen_pack_quality_out}}"; fi; \
  python3 scripts/report_citizen_concern_pack_quality.py --snapshot "{{citizen_pack_quality_snapshot}}" --concerns-config "{{citizen_pack_quality_concerns}}" --min-topics-per-pack "{{citizen_pack_quality_min_topics_per_pack}}" --min-clear-cells-pct "{{citizen_pack_quality_min_clear_cells_pct}}" --max-unknown-cells-pct "{{citizen_pack_quality_max_unknown_cells_pct}}" --min-confidence-avg-signal "{{citizen_pack_quality_min_confidence_avg_signal}}" --min-high-stakes-share "{{citizen_pack_quality_min_high_stakes_share}}" --max-weak-packs "{{citizen_pack_quality_max_weak_packs}}" --strict ${out_arg}

citizen-report-concern-pack-outcomes:
  quality_arg=""; \
  if [ -n "{{citizen_pack_outcome_quality}}" ]; then quality_arg="--concern-pack-quality-json {{citizen_pack_outcome_quality}}"; fi; \
  out_arg=""; \
  if [ -n "{{citizen_pack_outcome_out}}" ]; then out_arg="--out {{citizen_pack_outcome_out}}"; fi; \
  python3 scripts/report_citizen_concern_pack_outcomes.py --events-jsonl "{{citizen_pack_outcome_events}}" --min-pack-select-events "{{citizen_pack_outcome_min_pack_select_events}}" --min-weak-pack-select-sessions "{{citizen_pack_outcome_min_weak_pack_select_sessions}}" --min-weak-pack-followthrough-rate "{{citizen_pack_outcome_min_weak_pack_followthrough_rate}}" --max-unknown-pack-select-share "{{citizen_pack_outcome_max_unknown_pack_select_share}}" ${quality_arg} ${out_arg}

citizen-check-concern-pack-outcomes:
  quality_arg=""; \
  if [ -n "{{citizen_pack_outcome_quality}}" ]; then quality_arg="--concern-pack-quality-json {{citizen_pack_outcome_quality}}"; fi; \
  out_arg=""; \
  if [ -n "{{citizen_pack_outcome_out}}" ]; then out_arg="--out {{citizen_pack_outcome_out}}"; fi; \
  python3 scripts/report_citizen_concern_pack_outcomes.py --events-jsonl "{{citizen_pack_outcome_events}}" --min-pack-select-events "{{citizen_pack_outcome_min_pack_select_events}}" --min-weak-pack-select-sessions "{{citizen_pack_outcome_min_weak_pack_select_sessions}}" --min-weak-pack-followthrough-rate "{{citizen_pack_outcome_min_weak_pack_followthrough_rate}}" --max-unknown-pack-select-share "{{citizen_pack_outcome_max_unknown_pack_select_share}}" --strict --strict-require-complete ${quality_arg} ${out_arg}

citizen-report-concern-pack-outcomes-heartbeat:
  out_arg=""; \
  if [ -n "{{citizen_pack_outcome_heartbeat_out}}" ]; then out_arg="--out {{citizen_pack_outcome_heartbeat_out}}"; fi; \
  python3 scripts/report_citizen_concern_pack_outcomes_heartbeat.py --digest-json "{{citizen_pack_outcome_heartbeat_digest}}" --heartbeat-jsonl "{{citizen_pack_outcome_heartbeat_path}}" ${out_arg}

citizen-check-concern-pack-outcomes-heartbeat:
  out_arg=""; \
  if [ -n "{{citizen_pack_outcome_heartbeat_out}}" ]; then out_arg="--out {{citizen_pack_outcome_heartbeat_out}}"; fi; \
  python3 scripts/report_citizen_concern_pack_outcomes_heartbeat.py --digest-json "{{citizen_pack_outcome_heartbeat_digest}}" --heartbeat-jsonl "{{citizen_pack_outcome_heartbeat_path}}" --strict ${out_arg}

citizen-report-concern-pack-outcomes-heartbeat-window:
  out_arg=""; \
  if [ -n "{{citizen_pack_outcome_heartbeat_window_out}}" ]; then out_arg="--out {{citizen_pack_outcome_heartbeat_window_out}}"; fi; \
  python3 scripts/report_citizen_concern_pack_outcomes_heartbeat_window.py --heartbeat-jsonl "{{citizen_pack_outcome_heartbeat_path}}" --last "{{citizen_pack_outcome_heartbeat_window_last}}" --max-failed "{{citizen_pack_outcome_heartbeat_window_max_failed}}" --max-failed-rate-pct "{{citizen_pack_outcome_heartbeat_window_max_failed_rate_pct}}" --max-degraded "{{citizen_pack_outcome_heartbeat_window_max_degraded}}" --max-degraded-rate-pct "{{citizen_pack_outcome_heartbeat_window_max_degraded_rate_pct}}" --max-contract-incomplete "{{citizen_pack_outcome_heartbeat_window_max_contract_incomplete}}" --max-contract-incomplete-rate-pct "{{citizen_pack_outcome_heartbeat_window_max_contract_incomplete_rate_pct}}" --max-weak-pack-followthrough-violations "{{citizen_pack_outcome_heartbeat_window_max_weak_pack_followthrough_violations}}" --max-weak-pack-followthrough-violation-rate-pct "{{citizen_pack_outcome_heartbeat_window_max_weak_pack_followthrough_violation_rate_pct}}" --max-unknown-pack-select-share-violations "{{citizen_pack_outcome_heartbeat_window_max_unknown_pack_select_share_violations}}" --max-unknown-pack-select-share-violation-rate-pct "{{citizen_pack_outcome_heartbeat_window_max_unknown_pack_select_share_violation_rate_pct}}" ${out_arg}

citizen-check-concern-pack-outcomes-heartbeat-window:
  out_arg=""; \
  if [ -n "{{citizen_pack_outcome_heartbeat_window_out}}" ]; then out_arg="--out {{citizen_pack_outcome_heartbeat_window_out}}"; fi; \
  python3 scripts/report_citizen_concern_pack_outcomes_heartbeat_window.py --heartbeat-jsonl "{{citizen_pack_outcome_heartbeat_path}}" --last "{{citizen_pack_outcome_heartbeat_window_last}}" --max-failed "{{citizen_pack_outcome_heartbeat_window_max_failed}}" --max-failed-rate-pct "{{citizen_pack_outcome_heartbeat_window_max_failed_rate_pct}}" --max-degraded "{{citizen_pack_outcome_heartbeat_window_max_degraded}}" --max-degraded-rate-pct "{{citizen_pack_outcome_heartbeat_window_max_degraded_rate_pct}}" --max-contract-incomplete "{{citizen_pack_outcome_heartbeat_window_max_contract_incomplete}}" --max-contract-incomplete-rate-pct "{{citizen_pack_outcome_heartbeat_window_max_contract_incomplete_rate_pct}}" --max-weak-pack-followthrough-violations "{{citizen_pack_outcome_heartbeat_window_max_weak_pack_followthrough_violations}}" --max-weak-pack-followthrough-violation-rate-pct "{{citizen_pack_outcome_heartbeat_window_max_weak_pack_followthrough_violation_rate_pct}}" --max-unknown-pack-select-share-violations "{{citizen_pack_outcome_heartbeat_window_max_unknown_pack_select_share_violations}}" --max-unknown-pack-select-share-violation-rate-pct "{{citizen_pack_outcome_heartbeat_window_max_unknown_pack_select_share_violation_rate_pct}}" --strict ${out_arg}

citizen-report-concern-pack-outcomes-heartbeat-compact:
  out_arg=""; \
  if [ -n "{{citizen_pack_outcome_heartbeat_compact_out}}" ]; then out_arg="--out {{citizen_pack_outcome_heartbeat_compact_out}}"; fi; \
  python3 scripts/report_citizen_concern_pack_outcomes_heartbeat_compaction.py --heartbeat-jsonl "{{citizen_pack_outcome_heartbeat_path}}" --compacted-jsonl "{{citizen_pack_outcome_heartbeat_compact_path}}" --keep-recent "{{citizen_pack_outcome_heartbeat_compact_recent}}" --keep-mid-span "{{citizen_pack_outcome_heartbeat_compact_mid_span}}" --keep-mid-every "{{citizen_pack_outcome_heartbeat_compact_mid_every}}" --keep-old-every "{{citizen_pack_outcome_heartbeat_compact_old_every}}" --min-raw-for-dropped-check "{{citizen_pack_outcome_heartbeat_compact_min_raw}}" ${out_arg}

citizen-check-concern-pack-outcomes-heartbeat-compact:
  out_arg=""; \
  if [ -n "{{citizen_pack_outcome_heartbeat_compact_out}}" ]; then out_arg="--out {{citizen_pack_outcome_heartbeat_compact_out}}"; fi; \
  python3 scripts/report_citizen_concern_pack_outcomes_heartbeat_compaction.py --heartbeat-jsonl "{{citizen_pack_outcome_heartbeat_path}}" --compacted-jsonl "{{citizen_pack_outcome_heartbeat_compact_path}}" --keep-recent "{{citizen_pack_outcome_heartbeat_compact_recent}}" --keep-mid-span "{{citizen_pack_outcome_heartbeat_compact_mid_span}}" --keep-mid-every "{{citizen_pack_outcome_heartbeat_compact_mid_every}}" --keep-old-every "{{citizen_pack_outcome_heartbeat_compact_old_every}}" --min-raw-for-dropped-check "{{citizen_pack_outcome_heartbeat_compact_min_raw}}" --strict ${out_arg}

citizen-report-concern-pack-outcomes-heartbeat-compact-window:
  out_arg=""; \
  if [ -n "{{citizen_pack_outcome_heartbeat_compact_window_out}}" ]; then out_arg="--out {{citizen_pack_outcome_heartbeat_compact_window_out}}"; fi; \
  python3 scripts/report_citizen_concern_pack_outcomes_heartbeat_compaction_window.py --heartbeat-jsonl "{{citizen_pack_outcome_heartbeat_path}}" --compacted-jsonl "{{citizen_pack_outcome_heartbeat_compact_path}}" --last "{{citizen_pack_outcome_heartbeat_compact_window_last}}" ${out_arg}

citizen-check-concern-pack-outcomes-heartbeat-compact-window:
  out_arg=""; \
  if [ -n "{{citizen_pack_outcome_heartbeat_compact_window_out}}" ]; then out_arg="--out {{citizen_pack_outcome_heartbeat_compact_window_out}}"; fi; \
  python3 scripts/report_citizen_concern_pack_outcomes_heartbeat_compaction_window.py --heartbeat-jsonl "{{citizen_pack_outcome_heartbeat_path}}" --compacted-jsonl "{{citizen_pack_outcome_heartbeat_compact_path}}" --last "{{citizen_pack_outcome_heartbeat_compact_window_last}}" --strict ${out_arg}

citizen-report-trust-action-nudges:
  out_arg=""; \
  if [ -n "{{citizen_trust_action_nudge_out}}" ]; then out_arg="--out {{citizen_trust_action_nudge_out}}"; fi; \
  python3 scripts/report_citizen_trust_action_nudges.py --events-jsonl "{{citizen_trust_action_nudge_events}}" --min-nudge-shown-events "{{citizen_trust_action_nudge_min_shown_events}}" --min-nudge-shown-sessions "{{citizen_trust_action_nudge_min_shown_sessions}}" --min-nudge-clickthrough-rate "{{citizen_trust_action_nudge_min_clickthrough_rate}}" ${out_arg}

citizen-check-trust-action-nudges:
  out_arg=""; \
  if [ -n "{{citizen_trust_action_nudge_out}}" ]; then out_arg="--out {{citizen_trust_action_nudge_out}}"; fi; \
  python3 scripts/report_citizen_trust_action_nudges.py --events-jsonl "{{citizen_trust_action_nudge_events}}" --min-nudge-shown-events "{{citizen_trust_action_nudge_min_shown_events}}" --min-nudge-shown-sessions "{{citizen_trust_action_nudge_min_shown_sessions}}" --min-nudge-clickthrough-rate "{{citizen_trust_action_nudge_min_clickthrough_rate}}" --strict --strict-require-complete ${out_arg}

citizen-report-trust-action-nudges-heartbeat:
  out_arg=""; \
  if [ -n "{{citizen_trust_action_nudge_heartbeat_out}}" ]; then out_arg="--out {{citizen_trust_action_nudge_heartbeat_out}}"; fi; \
  python3 scripts/report_citizen_trust_action_nudges_heartbeat.py --digest-json "{{citizen_trust_action_nudge_heartbeat_digest}}" --heartbeat-jsonl "{{citizen_trust_action_nudge_heartbeat_path}}" ${out_arg}

citizen-check-trust-action-nudges-heartbeat:
  out_arg=""; \
  if [ -n "{{citizen_trust_action_nudge_heartbeat_out}}" ]; then out_arg="--out {{citizen_trust_action_nudge_heartbeat_out}}"; fi; \
  python3 scripts/report_citizen_trust_action_nudges_heartbeat.py --digest-json "{{citizen_trust_action_nudge_heartbeat_digest}}" --heartbeat-jsonl "{{citizen_trust_action_nudge_heartbeat_path}}" --strict ${out_arg}

citizen-report-trust-action-nudges-heartbeat-window:
  out_arg=""; \
  if [ -n "{{citizen_trust_action_nudge_heartbeat_window_out}}" ]; then out_arg="--out {{citizen_trust_action_nudge_heartbeat_window_out}}"; fi; \
  python3 scripts/report_citizen_trust_action_nudges_heartbeat_window.py --heartbeat-jsonl "{{citizen_trust_action_nudge_heartbeat_path}}" --last "{{citizen_trust_action_nudge_heartbeat_window_last}}" --max-failed "{{citizen_trust_action_nudge_heartbeat_window_max_failed}}" --max-failed-rate-pct "{{citizen_trust_action_nudge_heartbeat_window_max_failed_rate_pct}}" --max-degraded "{{citizen_trust_action_nudge_heartbeat_window_max_degraded}}" --max-degraded-rate-pct "{{citizen_trust_action_nudge_heartbeat_window_max_degraded_rate_pct}}" --max-contract-incomplete "{{citizen_trust_action_nudge_heartbeat_window_max_contract_incomplete}}" --max-contract-incomplete-rate-pct "{{citizen_trust_action_nudge_heartbeat_window_max_contract_incomplete_rate_pct}}" --max-nudge-clickthrough-violations "{{citizen_trust_action_nudge_heartbeat_window_max_nudge_clickthrough_violations}}" --max-nudge-clickthrough-violation-rate-pct "{{citizen_trust_action_nudge_heartbeat_window_max_nudge_clickthrough_violation_rate_pct}}" ${out_arg}

citizen-check-trust-action-nudges-heartbeat-window:
  out_arg=""; \
  if [ -n "{{citizen_trust_action_nudge_heartbeat_window_out}}" ]; then out_arg="--out {{citizen_trust_action_nudge_heartbeat_window_out}}"; fi; \
  python3 scripts/report_citizen_trust_action_nudges_heartbeat_window.py --heartbeat-jsonl "{{citizen_trust_action_nudge_heartbeat_path}}" --last "{{citizen_trust_action_nudge_heartbeat_window_last}}" --max-failed "{{citizen_trust_action_nudge_heartbeat_window_max_failed}}" --max-failed-rate-pct "{{citizen_trust_action_nudge_heartbeat_window_max_failed_rate_pct}}" --max-degraded "{{citizen_trust_action_nudge_heartbeat_window_max_degraded}}" --max-degraded-rate-pct "{{citizen_trust_action_nudge_heartbeat_window_max_degraded_rate_pct}}" --max-contract-incomplete "{{citizen_trust_action_nudge_heartbeat_window_max_contract_incomplete}}" --max-contract-incomplete-rate-pct "{{citizen_trust_action_nudge_heartbeat_window_max_contract_incomplete_rate_pct}}" --max-nudge-clickthrough-violations "{{citizen_trust_action_nudge_heartbeat_window_max_nudge_clickthrough_violations}}" --max-nudge-clickthrough-violation-rate-pct "{{citizen_trust_action_nudge_heartbeat_window_max_nudge_clickthrough_violation_rate_pct}}" --strict ${out_arg}

citizen-report-trust-action-nudges-heartbeat-compact:
  out_arg=""; \
  if [ -n "{{citizen_trust_action_nudge_heartbeat_compact_out}}" ]; then out_arg="--out {{citizen_trust_action_nudge_heartbeat_compact_out}}"; fi; \
  python3 scripts/report_citizen_trust_action_nudges_heartbeat_compaction.py --heartbeat-jsonl "{{citizen_trust_action_nudge_heartbeat_path}}" --compacted-jsonl "{{citizen_trust_action_nudge_heartbeat_compact_path}}" --keep-recent "{{citizen_trust_action_nudge_heartbeat_compact_recent}}" --keep-mid-span "{{citizen_trust_action_nudge_heartbeat_compact_mid_span}}" --keep-mid-every "{{citizen_trust_action_nudge_heartbeat_compact_mid_every}}" --keep-old-every "{{citizen_trust_action_nudge_heartbeat_compact_old_every}}" --min-raw-for-dropped-check "{{citizen_trust_action_nudge_heartbeat_compact_min_raw}}" ${out_arg}

citizen-check-trust-action-nudges-heartbeat-compact:
  out_arg=""; \
  if [ -n "{{citizen_trust_action_nudge_heartbeat_compact_out}}" ]; then out_arg="--out {{citizen_trust_action_nudge_heartbeat_compact_out}}"; fi; \
  python3 scripts/report_citizen_trust_action_nudges_heartbeat_compaction.py --heartbeat-jsonl "{{citizen_trust_action_nudge_heartbeat_path}}" --compacted-jsonl "{{citizen_trust_action_nudge_heartbeat_compact_path}}" --keep-recent "{{citizen_trust_action_nudge_heartbeat_compact_recent}}" --keep-mid-span "{{citizen_trust_action_nudge_heartbeat_compact_mid_span}}" --keep-mid-every "{{citizen_trust_action_nudge_heartbeat_compact_mid_every}}" --keep-old-every "{{citizen_trust_action_nudge_heartbeat_compact_old_every}}" --min-raw-for-dropped-check "{{citizen_trust_action_nudge_heartbeat_compact_min_raw}}" --strict ${out_arg}

citizen-report-trust-action-nudges-heartbeat-compact-window:
  out_arg=""; \
  if [ -n "{{citizen_trust_action_nudge_heartbeat_compact_window_out}}" ]; then out_arg="--out {{citizen_trust_action_nudge_heartbeat_compact_window_out}}"; fi; \
  python3 scripts/report_citizen_trust_action_nudges_heartbeat_compaction_window.py --heartbeat-jsonl "{{citizen_trust_action_nudge_heartbeat_path}}" --compacted-jsonl "{{citizen_trust_action_nudge_heartbeat_compact_path}}" --last "{{citizen_trust_action_nudge_heartbeat_compact_window_last}}" ${out_arg}

citizen-check-trust-action-nudges-heartbeat-compact-window:
  out_arg=""; \
  if [ -n "{{citizen_trust_action_nudge_heartbeat_compact_window_out}}" ]; then out_arg="--out {{citizen_trust_action_nudge_heartbeat_compact_window_out}}"; fi; \
  python3 scripts/report_citizen_trust_action_nudges_heartbeat_compaction_window.py --heartbeat-jsonl "{{citizen_trust_action_nudge_heartbeat_path}}" --compacted-jsonl "{{citizen_trust_action_nudge_heartbeat_compact_path}}" --last "{{citizen_trust_action_nudge_heartbeat_compact_window_last}}" --strict ${out_arg}

citizen-report-explainability-copy:
  out_arg=""; \
  if [ -n "{{citizen_explainability_copy_out}}" ]; then out_arg="--out {{citizen_explainability_copy_out}}"; fi; \
  python3 scripts/report_citizen_explainability_copy.py --ui-html "{{citizen_explainability_copy_ui_html}}" --min-glossary-terms "{{citizen_explainability_copy_min_terms}}" --max-definition-words "{{citizen_explainability_copy_max_definition_words}}" --max-copy-sentence-words "{{citizen_explainability_copy_max_copy_sentence_words}}" --forbidden-jargon "{{citizen_explainability_copy_forbidden_jargon}}" ${out_arg}

citizen-check-explainability-copy:
  out_arg=""; \
  if [ -n "{{citizen_explainability_copy_out}}" ]; then out_arg="--out {{citizen_explainability_copy_out}}"; fi; \
  python3 scripts/report_citizen_explainability_copy.py --ui-html "{{citizen_explainability_copy_ui_html}}" --min-glossary-terms "{{citizen_explainability_copy_min_terms}}" --max-definition-words "{{citizen_explainability_copy_max_definition_words}}" --max-copy-sentence-words "{{citizen_explainability_copy_max_copy_sentence_words}}" --forbidden-jargon "{{citizen_explainability_copy_forbidden_jargon}}" --strict --strict-require-complete ${out_arg}

citizen-report-explainability-outcomes:
  out_arg=""; \
  if [ -n "{{citizen_explainability_outcome_out}}" ]; then out_arg="--out {{citizen_explainability_outcome_out}}"; fi; \
  python3 scripts/report_citizen_explainability_outcomes.py --events-jsonl "{{citizen_explainability_outcome_events}}" --min-glossary-interaction-events "{{citizen_explainability_outcome_min_glossary_interaction_events}}" --min-help-copy-interaction-events "{{citizen_explainability_outcome_min_help_copy_interaction_events}}" --min-adoption-sessions "{{citizen_explainability_outcome_min_adoption_sessions}}" --min-adoption-completeness-rate "{{citizen_explainability_outcome_min_adoption_completeness_rate}}" ${out_arg}

citizen-check-explainability-outcomes:
  out_arg=""; \
  if [ -n "{{citizen_explainability_outcome_out}}" ]; then out_arg="--out {{citizen_explainability_outcome_out}}"; fi; \
  python3 scripts/report_citizen_explainability_outcomes.py --events-jsonl "{{citizen_explainability_outcome_events}}" --min-glossary-interaction-events "{{citizen_explainability_outcome_min_glossary_interaction_events}}" --min-help-copy-interaction-events "{{citizen_explainability_outcome_min_help_copy_interaction_events}}" --min-adoption-sessions "{{citizen_explainability_outcome_min_adoption_sessions}}" --min-adoption-completeness-rate "{{citizen_explainability_outcome_min_adoption_completeness_rate}}" --strict --strict-require-complete ${out_arg}

citizen-report-explainability-outcomes-heartbeat:
  out_arg=""; \
  if [ -n "{{citizen_explainability_outcome_heartbeat_out}}" ]; then out_arg="--out {{citizen_explainability_outcome_heartbeat_out}}"; fi; \
  python3 scripts/report_citizen_explainability_outcomes_heartbeat.py --digest-json "{{citizen_explainability_outcome_heartbeat_digest}}" --heartbeat-jsonl "{{citizen_explainability_outcome_heartbeat_path}}" ${out_arg}

citizen-check-explainability-outcomes-heartbeat:
  out_arg=""; \
  if [ -n "{{citizen_explainability_outcome_heartbeat_out}}" ]; then out_arg="--out {{citizen_explainability_outcome_heartbeat_out}}"; fi; \
  python3 scripts/report_citizen_explainability_outcomes_heartbeat.py --digest-json "{{citizen_explainability_outcome_heartbeat_digest}}" --heartbeat-jsonl "{{citizen_explainability_outcome_heartbeat_path}}" --strict ${out_arg}

citizen-report-explainability-outcomes-heartbeat-window:
  out_arg=""; \
  if [ -n "{{citizen_explainability_outcome_heartbeat_window_out}}" ]; then out_arg="--out {{citizen_explainability_outcome_heartbeat_window_out}}"; fi; \
  python3 scripts/report_citizen_explainability_outcomes_heartbeat_window.py --heartbeat-jsonl "{{citizen_explainability_outcome_heartbeat_path}}" --last "{{citizen_explainability_outcome_heartbeat_window_last}}" --max-failed "{{citizen_explainability_outcome_heartbeat_window_max_failed}}" --max-failed-rate-pct "{{citizen_explainability_outcome_heartbeat_window_max_failed_rate_pct}}" --max-degraded "{{citizen_explainability_outcome_heartbeat_window_max_degraded}}" --max-degraded-rate-pct "{{citizen_explainability_outcome_heartbeat_window_max_degraded_rate_pct}}" --max-contract-incomplete "{{citizen_explainability_outcome_heartbeat_window_max_contract_incomplete}}" --max-contract-incomplete-rate-pct "{{citizen_explainability_outcome_heartbeat_window_max_contract_incomplete_rate_pct}}" ${out_arg}

citizen-check-explainability-outcomes-heartbeat-window:
  out_arg=""; \
  if [ -n "{{citizen_explainability_outcome_heartbeat_window_out}}" ]; then out_arg="--out {{citizen_explainability_outcome_heartbeat_window_out}}"; fi; \
  python3 scripts/report_citizen_explainability_outcomes_heartbeat_window.py --heartbeat-jsonl "{{citizen_explainability_outcome_heartbeat_path}}" --last "{{citizen_explainability_outcome_heartbeat_window_last}}" --max-failed "{{citizen_explainability_outcome_heartbeat_window_max_failed}}" --max-failed-rate-pct "{{citizen_explainability_outcome_heartbeat_window_max_failed_rate_pct}}" --max-degraded "{{citizen_explainability_outcome_heartbeat_window_max_degraded}}" --max-degraded-rate-pct "{{citizen_explainability_outcome_heartbeat_window_max_degraded_rate_pct}}" --max-contract-incomplete "{{citizen_explainability_outcome_heartbeat_window_max_contract_incomplete}}" --max-contract-incomplete-rate-pct "{{citizen_explainability_outcome_heartbeat_window_max_contract_incomplete_rate_pct}}" --strict ${out_arg}

citizen-report-coherence-drilldown-outcomes:
  out_arg=""; \
  if [ -n "{{citizen_coherence_outcome_out}}" ]; then out_arg="--out {{citizen_coherence_outcome_out}}"; fi; \
  python3 scripts/report_citizen_coherence_drilldown_outcomes.py --events-jsonl "{{citizen_coherence_outcome_events}}" --min-drilldown-click-events "{{citizen_coherence_outcome_min_drilldown_click_events}}" --min-replay-attempt-events "{{citizen_coherence_outcome_min_replay_attempt_events}}" --min-replay-success-rate "{{citizen_coherence_outcome_min_replay_success_rate}}" --min-contract-complete-click-rate "{{citizen_coherence_outcome_min_contract_complete_click_rate}}" --max-replay-failure-rate "{{citizen_coherence_outcome_max_replay_failure_rate}}" ${out_arg}

citizen-check-coherence-drilldown-outcomes:
  out_arg=""; \
  if [ -n "{{citizen_coherence_outcome_out}}" ]; then out_arg="--out {{citizen_coherence_outcome_out}}"; fi; \
  python3 scripts/report_citizen_coherence_drilldown_outcomes.py --events-jsonl "{{citizen_coherence_outcome_events}}" --min-drilldown-click-events "{{citizen_coherence_outcome_min_drilldown_click_events}}" --min-replay-attempt-events "{{citizen_coherence_outcome_min_replay_attempt_events}}" --min-replay-success-rate "{{citizen_coherence_outcome_min_replay_success_rate}}" --min-contract-complete-click-rate "{{citizen_coherence_outcome_min_contract_complete_click_rate}}" --max-replay-failure-rate "{{citizen_coherence_outcome_max_replay_failure_rate}}" --strict --strict-require-complete ${out_arg}

citizen-report-coherence-drilldown-outcomes-heartbeat:
  out_arg=""; \
  if [ -n "{{citizen_coherence_outcome_heartbeat_out}}" ]; then out_arg="--out {{citizen_coherence_outcome_heartbeat_out}}"; fi; \
  python3 scripts/report_citizen_coherence_drilldown_outcomes_heartbeat.py --digest-json "{{citizen_coherence_outcome_heartbeat_digest}}" --heartbeat-jsonl "{{citizen_coherence_outcome_heartbeat_path}}" ${out_arg}

citizen-check-coherence-drilldown-outcomes-heartbeat:
  out_arg=""; \
  if [ -n "{{citizen_coherence_outcome_heartbeat_out}}" ]; then out_arg="--out {{citizen_coherence_outcome_heartbeat_out}}"; fi; \
  python3 scripts/report_citizen_coherence_drilldown_outcomes_heartbeat.py --digest-json "{{citizen_coherence_outcome_heartbeat_digest}}" --heartbeat-jsonl "{{citizen_coherence_outcome_heartbeat_path}}" --strict ${out_arg}

citizen-report-coherence-drilldown-outcomes-heartbeat-window:
  out_arg=""; \
  if [ -n "{{citizen_coherence_outcome_heartbeat_window_out}}" ]; then out_arg="--out {{citizen_coherence_outcome_heartbeat_window_out}}"; fi; \
  python3 scripts/report_citizen_coherence_drilldown_outcomes_heartbeat_window.py --heartbeat-jsonl "{{citizen_coherence_outcome_heartbeat_path}}" --last "{{citizen_coherence_outcome_heartbeat_window_last}}" --max-failed "{{citizen_coherence_outcome_heartbeat_window_max_failed}}" --max-failed-rate-pct "{{citizen_coherence_outcome_heartbeat_window_max_failed_rate_pct}}" --max-degraded "{{citizen_coherence_outcome_heartbeat_window_max_degraded}}" --max-degraded-rate-pct "{{citizen_coherence_outcome_heartbeat_window_max_degraded_rate_pct}}" --max-contract-incomplete "{{citizen_coherence_outcome_heartbeat_window_max_contract_incomplete}}" --max-contract-incomplete-rate-pct "{{citizen_coherence_outcome_heartbeat_window_max_contract_incomplete_rate_pct}}" --max-replay-success-rate-violations "{{citizen_coherence_outcome_heartbeat_window_max_replay_success_rate_violations}}" --max-replay-success-rate-violation-rate-pct "{{citizen_coherence_outcome_heartbeat_window_max_replay_success_rate_violation_rate_pct}}" --max-contract-click-rate-violations "{{citizen_coherence_outcome_heartbeat_window_max_contract_click_rate_violations}}" --max-contract-click-rate-violation-rate-pct "{{citizen_coherence_outcome_heartbeat_window_max_contract_click_rate_violation_rate_pct}}" --max-replay-failure-rate-violations "{{citizen_coherence_outcome_heartbeat_window_max_replay_failure_rate_violations}}" --max-replay-failure-rate-violation-rate-pct "{{citizen_coherence_outcome_heartbeat_window_max_replay_failure_rate_violation_rate_pct}}" ${out_arg}

citizen-check-coherence-drilldown-outcomes-heartbeat-window:
  out_arg=""; \
  if [ -n "{{citizen_coherence_outcome_heartbeat_window_out}}" ]; then out_arg="--out {{citizen_coherence_outcome_heartbeat_window_out}}"; fi; \
  python3 scripts/report_citizen_coherence_drilldown_outcomes_heartbeat_window.py --heartbeat-jsonl "{{citizen_coherence_outcome_heartbeat_path}}" --last "{{citizen_coherence_outcome_heartbeat_window_last}}" --max-failed "{{citizen_coherence_outcome_heartbeat_window_max_failed}}" --max-failed-rate-pct "{{citizen_coherence_outcome_heartbeat_window_max_failed_rate_pct}}" --max-degraded "{{citizen_coherence_outcome_heartbeat_window_max_degraded}}" --max-degraded-rate-pct "{{citizen_coherence_outcome_heartbeat_window_max_degraded_rate_pct}}" --max-contract-incomplete "{{citizen_coherence_outcome_heartbeat_window_max_contract_incomplete}}" --max-contract-incomplete-rate-pct "{{citizen_coherence_outcome_heartbeat_window_max_contract_incomplete_rate_pct}}" --max-replay-success-rate-violations "{{citizen_coherence_outcome_heartbeat_window_max_replay_success_rate_violations}}" --max-replay-success-rate-violation-rate-pct "{{citizen_coherence_outcome_heartbeat_window_max_replay_success_rate_violation_rate_pct}}" --max-contract-click-rate-violations "{{citizen_coherence_outcome_heartbeat_window_max_contract_click_rate_violations}}" --max-contract-click-rate-violation-rate-pct "{{citizen_coherence_outcome_heartbeat_window_max_contract_click_rate_violation_rate_pct}}" --max-replay-failure-rate-violations "{{citizen_coherence_outcome_heartbeat_window_max_replay_failure_rate_violations}}" --max-replay-failure-rate-violation-rate-pct "{{citizen_coherence_outcome_heartbeat_window_max_replay_failure_rate_violation_rate_pct}}" --strict ${out_arg}

citizen-report-coherence-drilldown-outcomes-heartbeat-compact:
  out_arg=""; \
  if [ -n "{{citizen_coherence_outcome_heartbeat_compact_out}}" ]; then out_arg="--out {{citizen_coherence_outcome_heartbeat_compact_out}}"; fi; \
  python3 scripts/report_citizen_coherence_drilldown_outcomes_heartbeat_compaction.py --heartbeat-jsonl "{{citizen_coherence_outcome_heartbeat_path}}" --compacted-jsonl "{{citizen_coherence_outcome_heartbeat_compact_path}}" --keep-recent "{{citizen_coherence_outcome_heartbeat_compact_recent}}" --keep-mid-span "{{citizen_coherence_outcome_heartbeat_compact_mid_span}}" --keep-mid-every "{{citizen_coherence_outcome_heartbeat_compact_mid_every}}" --keep-old-every "{{citizen_coherence_outcome_heartbeat_compact_old_every}}" --min-raw-for-dropped-check "{{citizen_coherence_outcome_heartbeat_compact_min_raw}}" ${out_arg}

citizen-check-coherence-drilldown-outcomes-heartbeat-compact:
  out_arg=""; \
  if [ -n "{{citizen_coherence_outcome_heartbeat_compact_out}}" ]; then out_arg="--out {{citizen_coherence_outcome_heartbeat_compact_out}}"; fi; \
  python3 scripts/report_citizen_coherence_drilldown_outcomes_heartbeat_compaction.py --heartbeat-jsonl "{{citizen_coherence_outcome_heartbeat_path}}" --compacted-jsonl "{{citizen_coherence_outcome_heartbeat_compact_path}}" --keep-recent "{{citizen_coherence_outcome_heartbeat_compact_recent}}" --keep-mid-span "{{citizen_coherence_outcome_heartbeat_compact_mid_span}}" --keep-mid-every "{{citizen_coherence_outcome_heartbeat_compact_mid_every}}" --keep-old-every "{{citizen_coherence_outcome_heartbeat_compact_old_every}}" --min-raw-for-dropped-check "{{citizen_coherence_outcome_heartbeat_compact_min_raw}}" --strict ${out_arg}

citizen-report-coherence-drilldown-outcomes-heartbeat-compact-window:
  out_arg=""; \
  if [ -n "{{citizen_coherence_outcome_heartbeat_compact_window_out}}" ]; then out_arg="--out {{citizen_coherence_outcome_heartbeat_compact_window_out}}"; fi; \
  python3 scripts/report_citizen_coherence_drilldown_outcomes_heartbeat_compaction_window.py --heartbeat-jsonl "{{citizen_coherence_outcome_heartbeat_path}}" --compacted-jsonl "{{citizen_coherence_outcome_heartbeat_compact_path}}" --last "{{citizen_coherence_outcome_heartbeat_compact_window_last}}" ${out_arg}

citizen-check-coherence-drilldown-outcomes-heartbeat-compact-window:
  out_arg=""; \
  if [ -n "{{citizen_coherence_outcome_heartbeat_compact_window_out}}" ]; then out_arg="--out {{citizen_coherence_outcome_heartbeat_compact_window_out}}"; fi; \
  python3 scripts/report_citizen_coherence_drilldown_outcomes_heartbeat_compaction_window.py --heartbeat-jsonl "{{citizen_coherence_outcome_heartbeat_path}}" --compacted-jsonl "{{citizen_coherence_outcome_heartbeat_compact_path}}" --last "{{citizen_coherence_outcome_heartbeat_compact_window_last}}" --strict ${out_arg}

citizen-report-release-hardening:
  out_arg=""; \
  if [ -n "{{citizen_release_out}}" ]; then out_arg="--json-out {{citizen_release_out}}"; fi; \
  node scripts/report_citizen_release_hardening.js --source-root "{{citizen_release_source_root}}" --published-root "{{citizen_release_published_root}}" --snapshot "{{citizen_release_snapshot}}" --concerns "{{citizen_release_concerns}}" --assets "{{citizen_release_assets}}" --max-snapshot-bytes "{{citizen_release_max_snapshot_bytes}}" ${out_arg}

citizen-check-release-hardening:
  out_arg=""; \
  if [ -n "{{citizen_release_out}}" ]; then out_arg="--json-out {{citizen_release_out}}"; fi; \
  node scripts/report_citizen_release_hardening.js --source-root "{{citizen_release_source_root}}" --published-root "{{citizen_release_published_root}}" --snapshot "{{citizen_release_snapshot}}" --concerns "{{citizen_release_concerns}}" --assets "{{citizen_release_assets}}" --max-snapshot-bytes "{{citizen_release_max_snapshot_bytes}}" --strict ${out_arg}

citizen-report-release-trace-digest:
  out_arg=""; \
  if [ -n "{{citizen_release_trace_out}}" ]; then out_arg="--json-out {{citizen_release_trace_out}}"; fi; \
  node scripts/report_citizen_release_trace_digest.js --release-hardening-json "{{citizen_release_trace_source}}" --max-age-minutes "{{citizen_release_trace_max_age_minutes}}" ${out_arg}

citizen-check-release-trace-digest:
  out_arg=""; \
  if [ -n "{{citizen_release_trace_out}}" ]; then out_arg="--json-out {{citizen_release_trace_out}}"; fi; \
  node scripts/report_citizen_release_trace_digest.js --release-hardening-json "{{citizen_release_trace_source}}" --max-age-minutes "{{citizen_release_trace_max_age_minutes}}" --strict --strict-require-complete ${out_arg}

citizen-report-release-trace-heartbeat:
  out_arg=""; \
  if [ -n "{{citizen_release_trace_heartbeat_out}}" ]; then out_arg="--out {{citizen_release_trace_heartbeat_out}}"; fi; \
  python3 scripts/report_citizen_release_trace_digest_heartbeat.py --digest-json "{{citizen_release_trace_heartbeat_digest}}" --heartbeat-jsonl "{{citizen_release_trace_heartbeat_path}}" ${out_arg}

citizen-check-release-trace-heartbeat:
  out_arg=""; \
  if [ -n "{{citizen_release_trace_heartbeat_out}}" ]; then out_arg="--out {{citizen_release_trace_heartbeat_out}}"; fi; \
  python3 scripts/report_citizen_release_trace_digest_heartbeat.py --digest-json "{{citizen_release_trace_heartbeat_digest}}" --heartbeat-jsonl "{{citizen_release_trace_heartbeat_path}}" --strict ${out_arg}

citizen-report-release-trace-heartbeat-window:
  out_arg=""; \
  if [ -n "{{citizen_release_trace_heartbeat_window_out}}" ]; then out_arg="--out {{citizen_release_trace_heartbeat_window_out}}"; fi; \
  python3 scripts/report_citizen_release_trace_digest_heartbeat_window.py --heartbeat-jsonl "{{citizen_release_trace_heartbeat_path}}" --last "{{citizen_release_trace_heartbeat_window_last}}" --max-failed "{{citizen_release_trace_heartbeat_window_max_failed}}" --max-failed-rate-pct "{{citizen_release_trace_heartbeat_window_max_failed_rate_pct}}" --max-degraded "{{citizen_release_trace_heartbeat_window_max_degraded}}" --max-degraded-rate-pct "{{citizen_release_trace_heartbeat_window_max_degraded_rate_pct}}" --max-stale "{{citizen_release_trace_heartbeat_window_max_stale}}" --max-stale-rate-pct "{{citizen_release_trace_heartbeat_window_max_stale_rate_pct}}" ${out_arg}

citizen-check-release-trace-heartbeat-window:
  out_arg=""; \
  if [ -n "{{citizen_release_trace_heartbeat_window_out}}" ]; then out_arg="--out {{citizen_release_trace_heartbeat_window_out}}"; fi; \
  python3 scripts/report_citizen_release_trace_digest_heartbeat_window.py --heartbeat-jsonl "{{citizen_release_trace_heartbeat_path}}" --last "{{citizen_release_trace_heartbeat_window_last}}" --max-failed "{{citizen_release_trace_heartbeat_window_max_failed}}" --max-failed-rate-pct "{{citizen_release_trace_heartbeat_window_max_failed_rate_pct}}" --max-degraded "{{citizen_release_trace_heartbeat_window_max_degraded}}" --max-degraded-rate-pct "{{citizen_release_trace_heartbeat_window_max_degraded_rate_pct}}" --max-stale "{{citizen_release_trace_heartbeat_window_max_stale}}" --max-stale-rate-pct "{{citizen_release_trace_heartbeat_window_max_stale_rate_pct}}" --strict ${out_arg}

citizen-report-release-trace-heartbeat-compact:
  out_arg=""; \
  if [ -n "{{citizen_release_trace_heartbeat_compact_out}}" ]; then out_arg="--out {{citizen_release_trace_heartbeat_compact_out}}"; fi; \
  python3 scripts/report_citizen_release_trace_digest_heartbeat_compaction.py --heartbeat-jsonl "{{citizen_release_trace_heartbeat_path}}" --compacted-jsonl "{{citizen_release_trace_heartbeat_compact_path}}" --keep-recent "{{citizen_release_trace_heartbeat_compact_recent}}" --keep-mid-span "{{citizen_release_trace_heartbeat_compact_mid_span}}" --keep-mid-every "{{citizen_release_trace_heartbeat_compact_mid_every}}" --keep-old-every "{{citizen_release_trace_heartbeat_compact_old_every}}" --min-raw-for-dropped-check "{{citizen_release_trace_heartbeat_compact_min_raw}}" ${out_arg}

citizen-check-release-trace-heartbeat-compact:
  out_arg=""; \
  if [ -n "{{citizen_release_trace_heartbeat_compact_out}}" ]; then out_arg="--out {{citizen_release_trace_heartbeat_compact_out}}"; fi; \
  python3 scripts/report_citizen_release_trace_digest_heartbeat_compaction.py --heartbeat-jsonl "{{citizen_release_trace_heartbeat_path}}" --compacted-jsonl "{{citizen_release_trace_heartbeat_compact_path}}" --keep-recent "{{citizen_release_trace_heartbeat_compact_recent}}" --keep-mid-span "{{citizen_release_trace_heartbeat_compact_mid_span}}" --keep-mid-every "{{citizen_release_trace_heartbeat_compact_mid_every}}" --keep-old-every "{{citizen_release_trace_heartbeat_compact_old_every}}" --min-raw-for-dropped-check "{{citizen_release_trace_heartbeat_compact_min_raw}}" --strict ${out_arg}

citizen-report-release-trace-heartbeat-compact-window:
  out_arg=""; \
  if [ -n "{{citizen_release_trace_heartbeat_compact_window_out}}" ]; then out_arg="--out {{citizen_release_trace_heartbeat_compact_window_out}}"; fi; \
  python3 scripts/report_citizen_release_trace_digest_heartbeat_compaction_window.py --heartbeat-jsonl "{{citizen_release_trace_heartbeat_path}}" --compacted-jsonl "{{citizen_release_trace_heartbeat_compact_path}}" --last "{{citizen_release_trace_heartbeat_compact_window_last}}" ${out_arg}

citizen-check-release-trace-heartbeat-compact-window:
  out_arg=""; \
  if [ -n "{{citizen_release_trace_heartbeat_compact_window_out}}" ]; then out_arg="--out {{citizen_release_trace_heartbeat_compact_window_out}}"; fi; \
  python3 scripts/report_citizen_release_trace_digest_heartbeat_compaction_window.py --heartbeat-jsonl "{{citizen_release_trace_heartbeat_path}}" --compacted-jsonl "{{citizen_release_trace_heartbeat_compact_path}}" --last "{{citizen_release_trace_heartbeat_compact_window_last}}" --strict ${out_arg}

citizen-report-preset-contract:
  out_arg=""; \
  if [ -n "{{citizen_preset_contract_out}}" ]; then out_arg="--json-out {{citizen_preset_contract_out}}"; fi; \
  node scripts/report_citizen_preset_fixture_contract.js --fixture "{{citizen_preset_contract_fixture}}" --strict ${out_arg}

citizen-report-preset-codec-parity:
  out_arg=""; \
  if [ -n "{{citizen_preset_parity_out}}" ]; then out_arg="--json-out {{citizen_preset_parity_out}}"; fi; \
  node scripts/report_citizen_preset_codec_parity.js --source "{{citizen_preset_parity_source}}" --published "{{citizen_preset_parity_published}}" --strict ${out_arg}

citizen-report-preset-codec-sync:
  out_arg=""; \
  if [ -n "{{citizen_preset_sync_out}}" ]; then out_arg="--json-out {{citizen_preset_sync_out}}"; fi; \
  node scripts/report_citizen_preset_codec_sync_state.js --source "{{citizen_preset_sync_source}}" --published "{{citizen_preset_sync_published}}" --strict ${out_arg}

citizen-report-preset-contract-bundle:
  out_arg=""; \
  if [ -n "{{citizen_preset_bundle_out}}" ]; then out_arg="--json-out {{citizen_preset_bundle_out}}"; fi; \
  node scripts/report_citizen_preset_contract_bundle.js --fixture "{{citizen_preset_contract_fixture}}" --source "{{citizen_preset_parity_source}}" --published "{{citizen_preset_parity_published}}" --strict ${out_arg}

citizen-report-preset-contract-bundle-history:
  test -n "{{citizen_preset_bundle_out}}" || (echo "Set CITIZEN_PRESET_BUNDLE_OUT=<bundle_json_path> before running history report" && exit 2); \
  out_arg=""; \
  if [ -n "{{citizen_preset_bundle_history_out}}" ]; then out_arg="--json-out {{citizen_preset_bundle_history_out}}"; fi; \
  node scripts/report_citizen_preset_contract_bundle_history.js --bundle-json "{{citizen_preset_bundle_out}}" --history-jsonl "{{citizen_preset_bundle_history_path}}" --strict ${out_arg}

citizen-report-preset-contract-bundle-history-window:
  out_arg=""; \
  if [ -n "{{citizen_preset_bundle_history_window_out}}" ]; then out_arg="--json-out {{citizen_preset_bundle_history_window_out}}"; fi; \
  node scripts/report_citizen_preset_contract_bundle_history_window.js --history-jsonl "{{citizen_preset_bundle_history_path}}" --last "{{citizen_preset_bundle_history_window}}" --strict ${out_arg}

citizen-report-preset-contract-bundle-history-compact:
  out_arg=""; \
  if [ -n "{{citizen_preset_bundle_history_compact_out}}" ]; then out_arg="--json-out {{citizen_preset_bundle_history_compact_out}}"; fi; \
  compact_arg=""; \
  if [ -n "{{citizen_preset_bundle_history_compact_path}}" ]; then compact_arg="--compacted-jsonl {{citizen_preset_bundle_history_compact_path}}"; fi; \
  node scripts/report_citizen_preset_contract_bundle_history_compaction.js --history-jsonl "{{citizen_preset_bundle_history_path}}" --keep-recent "{{citizen_preset_bundle_history_compact_recent}}" --keep-mid-span "{{citizen_preset_bundle_history_compact_mid_span}}" --keep-mid-every "{{citizen_preset_bundle_history_compact_mid_every}}" --keep-old-every "{{citizen_preset_bundle_history_compact_old_every}}" --min-raw-for-dropped-check "{{citizen_preset_bundle_history_compact_min_raw}}" --strict ${compact_arg} ${out_arg}

citizen-report-preset-contract-bundle-history-slo:
  out_arg=""; \
  if [ -n "{{citizen_preset_bundle_history_slo_out}}" ]; then out_arg="--json-out {{citizen_preset_bundle_history_slo_out}}"; fi; \
  node scripts/report_citizen_preset_contract_bundle_history_slo.js --history-jsonl "{{citizen_preset_bundle_history_path}}" --last "{{citizen_preset_bundle_history_slo_window}}" --max-regressions "{{citizen_preset_bundle_history_slo_max_regressions}}" --max-regression-rate-pct "{{citizen_preset_bundle_history_slo_max_regression_rate_pct}}" --min-green-streak "{{citizen_preset_bundle_history_slo_min_green_streak}}" --strict ${out_arg}

citizen-report-preset-contract-bundle-history-slo-digest:
  test -n "{{citizen_preset_bundle_history_slo_out}}" || (echo "Set CITIZEN_PRESET_BUNDLE_HISTORY_SLO_OUT=<slo_json_path> before running slo digest" && exit 2); \
  out_arg=""; \
  if [ -n "{{citizen_preset_bundle_history_slo_digest_out}}" ]; then out_arg="--json-out {{citizen_preset_bundle_history_slo_digest_out}}"; fi; \
  node scripts/report_citizen_preset_contract_bundle_history_slo_digest.js --slo-json "{{citizen_preset_bundle_history_slo_out}}" --strict ${out_arg}

citizen-report-preset-contract-bundle-history-slo-digest-heartbeat:
  test -n "{{citizen_preset_bundle_history_slo_digest_out}}" || (echo "Set CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_OUT=<slo_digest_json_path> before running slo digest heartbeat" && exit 2); \
  out_arg=""; \
  if [ -n "{{citizen_preset_bundle_history_slo_digest_heartbeat_out}}" ]; then out_arg="--json-out {{citizen_preset_bundle_history_slo_digest_heartbeat_out}}"; fi; \
  node scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat.js --digest-json "{{citizen_preset_bundle_history_slo_digest_out}}" --heartbeat-jsonl "{{citizen_preset_bundle_history_slo_digest_heartbeat_path}}" --strict ${out_arg}

citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-window:
  out_arg=""; \
  if [ -n "{{citizen_preset_bundle_history_slo_digest_heartbeat_window_out}}" ]; then out_arg="--json-out {{citizen_preset_bundle_history_slo_digest_heartbeat_window_out}}"; fi; \
  node scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_window.js --heartbeat-jsonl "{{citizen_preset_bundle_history_slo_digest_heartbeat_path}}" --last "{{citizen_preset_bundle_history_slo_digest_heartbeat_window}}" --max-failed "{{citizen_preset_bundle_history_slo_digest_heartbeat_max_failed}}" --max-failed-rate-pct "{{citizen_preset_bundle_history_slo_digest_heartbeat_max_failed_rate_pct}}" --strict ${out_arg}

citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact:
  out_arg=""; \
  if [ -n "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_out}}" ]; then out_arg="--json-out {{citizen_preset_bundle_history_slo_digest_heartbeat_compact_out}}"; fi; \
  compact_arg=""; \
  if [ -n "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_path}}" ]; then compact_arg="--compacted-jsonl {{citizen_preset_bundle_history_slo_digest_heartbeat_compact_path}}"; fi; \
  node scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction.js --heartbeat-jsonl "{{citizen_preset_bundle_history_slo_digest_heartbeat_path}}" --keep-recent "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_recent}}" --keep-mid-span "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_mid_span}}" --keep-mid-every "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_mid_every}}" --keep-old-every "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_old_every}}" --min-raw-for-dropped-check "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_min_raw}}" --strict ${compact_arg} ${out_arg}

citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window:
  out_arg=""; \
  if [ -n "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_out}}" ]; then out_arg="--json-out {{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_out}}"; fi; \
  node scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window.js --heartbeat-jsonl "{{citizen_preset_bundle_history_slo_digest_heartbeat_path}}" --compacted-jsonl "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_path}}" --last "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window}}" --strict ${out_arg}

citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest:
  test -n "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_out}}" || (echo "Set CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_OUT=<compaction_window_json_path> before running compact-window digest" && exit 2); \
  out_arg=""; \
  if [ -n "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_out}}" ]; then out_arg="--json-out {{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_out}}"; fi; \
  node scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest.js --compaction-window-json "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_out}}" --strict ${out_arg}

citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest-heartbeat:
  test -n "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_out}}" || (echo "Set CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_OUT=<compact_window_digest_json_path> before running compact-window digest heartbeat" && exit 2); \
  out_arg=""; \
  if [ -n "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_out}}" ]; then out_arg="--json-out {{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_out}}"; fi; \
  node scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat.js --digest-json "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_out}}" --heartbeat-jsonl "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_path}}" --strict ${out_arg}

citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest-heartbeat-window:
  out_arg=""; \
  if [ -n "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_window_out}}" ]; then out_arg="--json-out {{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_window_out}}"; fi; \
  node scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_window.js --heartbeat-jsonl "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_path}}" --last "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_window}}" --max-failed "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_max_failed}}" --max-failed-rate-pct "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_max_failed_rate_pct}}" --max-degraded "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_max_degraded}}" --max-degraded-rate-pct "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_max_degraded_rate_pct}}" --strict ${out_arg}

citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest-heartbeat-compact:
  out_arg=""; \
  if [ -n "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_compact_out}}" ]; then out_arg="--json-out {{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_compact_out}}"; fi; \
  compact_arg=""; \
  if [ -n "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_compact_path}}" ]; then compact_arg="--compacted-jsonl {{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_compact_path}}"; fi; \
  node scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_compaction.js --heartbeat-jsonl "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_path}}" --keep-recent "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_compact_recent}}" --keep-mid-span "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_compact_mid_span}}" --keep-mid-every "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_compact_mid_every}}" --keep-old-every "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_compact_old_every}}" --min-raw-for-dropped-check "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_compact_min_raw}}" --strict ${compact_arg} ${out_arg}

citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest-heartbeat-compact-window:
  out_arg=""; \
  if [ -n "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_compact_window_out}}" ]; then out_arg="--json-out {{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_compact_window_out}}"; fi; \
  node scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.js --heartbeat-jsonl "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_path}}" --compacted-jsonl "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_compact_path}}" --last "{{citizen_preset_bundle_history_slo_digest_heartbeat_compact_window_digest_heartbeat_compact_window}}" --strict ${out_arg}

cloudflare-pages-deploy:
  @just cloudflare-pages-build
  cd "{{gh_pages_next_app_dir}}" && npx wrangler pages deploy out --project-name "{{cloudflare_pages_project}}"

votaconlachola-gh-pages-publish:
  set -e; \
  test -d "{{gh_pages_next_out_dir}}" || (echo "Missing {{gh_pages_next_out_dir}}; run just cloudflare-pages-refresh-data first" >&2; exit 2); \
  tmpdir="$(mktemp -d)"; \
  cleanup() { git worktree remove --force "$tmpdir" >/dev/null 2>&1 || rm -rf "$tmpdir"; }; \
  trap cleanup EXIT; \
  git fetch "{{gh_pages_remote}}" "{{gh_pages_branch}}"; \
  git worktree add --detach "$tmpdir" FETCH_HEAD; \
  rsync -a --delete --exclude .git "{{gh_pages_next_out_dir}}"/ "$tmpdir"/; \
  touch "$tmpdir/.nojekyll"; \
  git -C "$tmpdir" add -A; \
  if git -C "$tmpdir" diff --cached --quiet; then \
    echo "No gh-pages changes to publish"; \
  else \
    git -C "$tmpdir" config user.name "${GIT_AUTHOR_NAME:-vclc-publisher}"; \
    git -C "$tmpdir" config user.email "${GIT_AUTHOR_EMAIL:-actions@users.noreply.github.com}"; \
    git -C "$tmpdir" commit -m "Publish static site snapshot {{snapshot_date}}"; \
    git -C "$tmpdir" push "{{gh_pages_remote}}" HEAD:"{{gh_pages_branch}}"; \
  fi

explorer-gh-pages-publish:
  @just votaconlachola-gh-pages-publish

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
