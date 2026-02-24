# Database Inventory And Schemas

- Generated at (UTC): `2026-02-24 15:37:52Z`
- Total DB files found: `141`
- Unique schema signatures: `22`
- Canonical runtime DB: `etl/data/staging/politicos-es.db`
- Canonical schema id: `030bd477d6eda00e`
- Canonical table count: `75`

Canonical schema source-of-truth:
- `etl/load/sqlite_schema.sql`

## Schema Families

| schema_id | files | tables | views | category_mix | sample | missing_vs_canonical | extra_vs_canonical |
|---|---:|---:|---:|---|---|---:|---:|
| `dc489727e96af0a1` | 38 | 14 | 0 | platform_sqlite_variant | `etl/data/staging/_inspect.db` | 61 | 0 |
| `4e9dac07ac526f31` | 24 | 7 | 0 | browser_profile_first_party_sets | `etl/data/raw/manual/_tmp_galicia_click_profile/first_party_sets.db` | 75 | 7 |
| `54f7dc72f40bfd5f` | 23 | 2 | 0 | browser_profile_heavy_ad_intervention_opt_out | `etl/data/raw/manual/galicia_deputado_profiles_20260212T141413Z/profile/Default/heavy_ad_intervention_opt_out.db` | 75 | 2 |
| `c4e3f6856e09a14b` | 15 | 71 | 0 | platform_sqlite_variant, sprint_fixture_or_evidence_db | `docs/etl/sprints/AI-OPS-132/exports/liberty_representativity_20260223T203640Z.db` | 4 | 0 |
| `fd43263fb254f6bb` | 12 | 72 | 0 | platform_sqlite_variant | `tmp/ai_ops_150_contract.db` | 3 | 0 |
| `4315a0f56dd07075` | 9 | 8 | 0 | platform_sqlite_variant | `etl/data/staging/politicos-es.ci-gate-local.db` | 67 | 0 |
| `9540053a905bf7c2` | 2 | 52 | 0 | platform_sqlite_variant | `etl/data/staging/politicos-es.aiops115.20260223T173448Z.db` | 23 | 0 |
| `80a90ef042466929` | 2 | 29 | 0 | platform_sqlite_variant | `etl/data/staging/politicos-es.fresh.recovered.20260214_1705.db` | 46 | 0 |
| `8479f1303c9a3bb8` | 2 | 21 | 0 | platform_sqlite_variant | `etl/data/staging/parl-quality-smoke.db` | 54 | 0 |
| `57284d24516fe4de` | 2 | 0 | 0 | empty_placeholder | `politicos-es.db` | 75 | 0 |
| `030bd477d6eda00e` | 1 | 75 | 0 | platform_sqlite_variant | `etl/data/staging/politicos-es.db` | 0 | 0 |
| `71f4436a39ecd79c` | 1 | 74 | 0 | sprint_fixture_or_evidence_db | `docs/etl/sprints/AI-OPS-189/evidence/sanction_procedural_official_review_raw_packets_cycle_fixture_20260224T114814Z.db` | 1 | 0 |
| `642161a632336f6a` | 1 | 69 | 0 | platform_sqlite_variant | `etl/data/staging/politicos-es.aiops120.db` | 6 | 0 |
| `332a2a1eb23146bb` | 1 | 65 | 0 | platform_sqlite_variant | `etl/data/staging/politicos-es.aiops119.db` | 10 | 0 |
| `8efa489f714a957b` | 1 | 63 | 0 | platform_sqlite_variant | `etl/data/staging/politicos-es.aiops118.db` | 12 | 0 |
| `eeeceea44a97a592` | 1 | 60 | 0 | platform_sqlite_variant | `etl/data/staging/politicos-es.aiops117.db` | 15 | 0 |
| `acd27ce46df459ed` | 1 | 58 | 0 | platform_sqlite_variant | `etl/data/staging/politicos-es.aiops116.20260223T174656Z.db` | 17 | 0 |
| `9f69e4335f9bd10f` | 1 | 41 | 0 | platform_sqlite_variant | `etl/data/staging/moncloa-aiops04-matrix-20260216.db` | 34 | 0 |
| `25015d0743ebc215` | 1 | 29 | 0 | platform_sqlite_variant | `etl/data/staging/politicos-es.e2e19.db` | 46 | 0 |
| `841b2d9125c2a0f1` | 1 | 28 | 0 | platform_sqlite_variant | `etl/data/staging/politicos-es.fresh.db` | 47 | 0 |
| `684d4480fba83bef` | 1 | 24 | 0 | platform_sqlite_variant | `etl/data/staging/politicos-es.recovered.db` | 51 | 0 |
| `d2795c882362e315` | 1 | 4 | 0 | sprint_fixture_or_evidence_db | `docs/etl/sprints/AI-OPS-62/evidence/initdoc_actionable_contract.db` | 71 | 0 |

## Canonical Table List

Schema id `030bd477d6eda00e` from `etl/data/staging/politicos-es.db`.

- `admin_levels`
- `causal_estimates`
- `document_fetches`
- `domains`
- `genders`
- `indicator_observation_records`
- `indicator_points`
- `indicator_series`
- `infoelectoral_archivos_extraccion`
- `infoelectoral_convocatoria_tipos`
- `infoelectoral_convocatorias`
- `infoelectoral_proceso_resultados`
- `infoelectoral_procesos`
- `ingestion_runs`
- `institutions`
- `intervention_events`
- `interventions`
- `legal_fragment_responsibilities`
- `legal_fragment_responsibility_evidence`
- `legal_norm_fragments`
- `legal_norm_lineage_edges`
- `legal_norms`
- `liberty_delegated_enforcement_links`
- `liberty_delegated_enforcement_methodologies`
- `liberty_enforcement_methodologies`
- `liberty_enforcement_observations`
- `liberty_indirect_methodologies`
- `liberty_indirect_responsibility_edges`
- `liberty_irlc_methodologies`
- `liberty_proportionality_methodologies`
- `liberty_proportionality_reviews`
- `liberty_restriction_assessments`
- `liberty_right_categories`
- `lost_and_found`
- `mandates`
- `money_contract_records`
- `money_subsidy_records`
- `parl_initiative_doc_extractions`
- `parl_initiative_documents`
- `parl_initiatives`
- `parl_vote_event_initiatives`
- `parl_vote_events`
- `parl_vote_member_votes`
- `parties`
- `party_aliases`
- `person_identifiers`
- `person_name_aliases`
- `persons`
- `policy_axes`
- `policy_event_axis_scores`
- `policy_events`
- `policy_instruments`
- `raw_fetches`
- `roles`
- `run_fetches`
- `sanction_infraction_type_mappings`
- `sanction_infraction_types`
- `sanction_municipal_ordinance_fragments`
- `sanction_municipal_ordinances`
- `sanction_norm_catalog`
- `sanction_norm_fragment_links`
- `sanction_procedural_kpi_definitions`
- `sanction_procedural_metrics`
- `sanction_volume_observations`
- `sanction_volume_sources`
- `source_records`
- `sources`
- `territories`
- `text_documents`
- `topic_evidence`
- `topic_evidence_reviews`
- `topic_positions`
- `topic_set_topics`
- `topic_sets`
- `topics`

## Detailed Schemas By Family

### `dc489727e96af0a1`

- Files: `38`
- Tables: `14`
- Views: `0`
- Category mix: `platform_sqlite_variant`
- Sample: `etl/data/staging/_inspect.db`
- Missing vs canonical: `61`
- Extra vs canonical: `0`

Tables:
- `admin_levels`
- `genders`
- `ingestion_runs`
- `institutions`
- `mandates`
- `parties`
- `party_aliases`
- `person_identifiers`
- `persons`
- `raw_fetches`
- `roles`
- `source_records`
- `sources`
- `territories`

Missing tables vs canonical:
- `causal_estimates`
- `document_fetches`
- `domains`
- `indicator_observation_records`
- `indicator_points`
- `indicator_series`
- `infoelectoral_archivos_extraccion`
- `infoelectoral_convocatoria_tipos`
- `infoelectoral_convocatorias`
- `infoelectoral_proceso_resultados`
- `infoelectoral_procesos`
- `intervention_events`
- `interventions`
- `legal_fragment_responsibilities`
- `legal_fragment_responsibility_evidence`
- `legal_norm_fragments`
- `legal_norm_lineage_edges`
- `legal_norms`
- `liberty_delegated_enforcement_links`
- `liberty_delegated_enforcement_methodologies`
- `liberty_enforcement_methodologies`
- `liberty_enforcement_observations`
- `liberty_indirect_methodologies`
- `liberty_indirect_responsibility_edges`
- `liberty_irlc_methodologies`
- `liberty_proportionality_methodologies`
- `liberty_proportionality_reviews`
- `liberty_restriction_assessments`
- `liberty_right_categories`
- `lost_and_found`
- `money_contract_records`
- `money_subsidy_records`
- `parl_initiative_doc_extractions`
- `parl_initiative_documents`
- `parl_initiatives`
- `parl_vote_event_initiatives`
- `parl_vote_events`
- `parl_vote_member_votes`
- `person_name_aliases`
- `policy_axes`
- `policy_event_axis_scores`
- `policy_events`
- `policy_instruments`
- `run_fetches`
- `sanction_infraction_type_mappings`
- `sanction_infraction_types`
- `sanction_municipal_ordinance_fragments`
- `sanction_municipal_ordinances`
- `sanction_norm_catalog`
- `sanction_norm_fragment_links`
- `sanction_procedural_kpi_definitions`
- `sanction_procedural_metrics`
- `sanction_volume_observations`
- `sanction_volume_sources`
- `text_documents`
- `topic_evidence`
- `topic_evidence_reviews`
- `topic_positions`
- `topic_set_topics`
- `topic_sets`
- `topics`

Files in this family:
- `etl/data/staging/_inspect.db`
- `etl/data/staging/politicos-es.and-pv.db`
- `etl/data/staging/politicos-es.aragoncheck.db`
- `etl/data/staging/politicos-es.aragonfix.db`
- `etl/data/staging/politicos-es.asamblea-madrid-20260212.db`
- `etl/data/staging/politicos-es.asamblea-madrid-occup-uniq-20260212.db`
- `etl/data/staging/politicos-es.asamblea-madrid-ocup-20260212.db`
- `etl/data/staging/politicos-es.asamblea-madrid-ocup-uniq-20260212.db`
- `etl/data/staging/politicos-es.asambleaex-20260212.db`
- `etl/data/staging/politicos-es.cantabria-20260212.db`
- `etl/data/staging/politicos-es.cat.db`
- `etl/data/staging/politicos-es.ccyl-20260212.db`
- `etl/data/staging/politicos-es.ceuta.db`
- `etl/data/staging/politicos-es.cortes-clm-20260212.db`
- `etl/data/staging/politicos-es.cv.db`
- `etl/data/staging/politicos-es.e2e-postfix-20260212.db`
- `etl/data/staging/politicos-es.e2e10.db`
- `etl/data/staging/politicos-es.e2e11.db`
- `etl/data/staging/politicos-es.e2e12.db`
- `etl/data/staging/politicos-es.e2e16.db`
- `etl/data/staging/politicos-es.e2e17.db`
- `etl/data/staging/politicos-es.e2e18.db`
- `etl/data/staging/politicos-es.e2e6.db`
- `etl/data/staging/politicos-es.e2e7.db`
- `etl/data/staging/politicos-es.e2e9.db`
- `etl/data/staging/politicos-es.full-20260212.db`
- `etl/data/staging/politicos-es.html-guard-20260212.db`
- `etl/data/staging/politicos-es.jgpa-20260212.db`
- `etl/data/staging/politicos-es.larioja-20260212.db`
- `etl/data/staging/politicos-es.municipal-strict-20260212.db`
- `etl/data/staging/politicos-es.murcia-20260212.db`
- `etl/data/staging/politicos-es.norm-samples.db`
- `etl/data/staging/politicos-es.norm-test.db`
- `etl/data/staging/politicos-es.parcan-20260212.db`
- `etl/data/staging/politicos-es.parlamentib-20260212.db`
- `etl/data/staging/politicos-es.refactor-e2e.db`
- `etl/data/staging/politicos-es.refactor-e2e2.db`
- `etl/data/staging/politicos-es.thresholds-smoke.db`

### `4e9dac07ac526f31`

- Files: `24`
- Tables: `7`
- Views: `0`
- Category mix: `browser_profile_first_party_sets`
- Sample: `etl/data/raw/manual/_tmp_galicia_click_profile/first_party_sets.db`
- Missing vs canonical: `75`
- Extra vs canonical: `7`

Tables:
- `browser_context_sets_version`
- `browser_context_sites_to_clear`
- `browser_contexts_cleared`
- `manual_configurations`
- `meta`
- `policy_configurations`
- `public_sets`

Missing tables vs canonical:
- `admin_levels`
- `causal_estimates`
- `document_fetches`
- `domains`
- `genders`
- `indicator_observation_records`
- `indicator_points`
- `indicator_series`
- `infoelectoral_archivos_extraccion`
- `infoelectoral_convocatoria_tipos`
- `infoelectoral_convocatorias`
- `infoelectoral_proceso_resultados`
- `infoelectoral_procesos`
- `ingestion_runs`
- `institutions`
- `intervention_events`
- `interventions`
- `legal_fragment_responsibilities`
- `legal_fragment_responsibility_evidence`
- `legal_norm_fragments`
- `legal_norm_lineage_edges`
- `legal_norms`
- `liberty_delegated_enforcement_links`
- `liberty_delegated_enforcement_methodologies`
- `liberty_enforcement_methodologies`
- `liberty_enforcement_observations`
- `liberty_indirect_methodologies`
- `liberty_indirect_responsibility_edges`
- `liberty_irlc_methodologies`
- `liberty_proportionality_methodologies`
- `liberty_proportionality_reviews`
- `liberty_restriction_assessments`
- `liberty_right_categories`
- `lost_and_found`
- `mandates`
- `money_contract_records`
- `money_subsidy_records`
- `parl_initiative_doc_extractions`
- `parl_initiative_documents`
- `parl_initiatives`
- `parl_vote_event_initiatives`
- `parl_vote_events`
- `parl_vote_member_votes`
- `parties`
- `party_aliases`
- `person_identifiers`
- `person_name_aliases`
- `persons`
- `policy_axes`
- `policy_event_axis_scores`
- `policy_events`
- `policy_instruments`
- `raw_fetches`
- `roles`
- `run_fetches`
- `sanction_infraction_type_mappings`
- `sanction_infraction_types`
- `sanction_municipal_ordinance_fragments`
- `sanction_municipal_ordinances`
- `sanction_norm_catalog`
- `sanction_norm_fragment_links`
- `sanction_procedural_kpi_definitions`
- `sanction_procedural_metrics`
- `sanction_volume_observations`
- `sanction_volume_sources`
- `source_records`
- `sources`
- `territories`
- `text_documents`
- `topic_evidence`
- `topic_evidence_reviews`
- `topic_positions`
- `topic_set_topics`
- `topic_sets`
- `topics`

Extra tables vs canonical:
- `browser_context_sets_version`
- `browser_context_sites_to_clear`
- `browser_contexts_cleared`
- `manual_configurations`
- `meta`
- `policy_configurations`
- `public_sets`

Files in this family:
- `etl/data/raw/manual/_tmp_galicia_click_profile/first_party_sets.db`
- `etl/data/raw/manual/galicia_deputado_profiles_20260212T141413Z/profile/first_party_sets.db`
- `etl/data/raw/manual/galicia_deputado_profiles_20260212T141929Z/profile/first_party_sets.db`
- `etl/data/raw/manual/galicia_deputados_20260212T132244Z_profile/first_party_sets.db`
- `etl/data/raw/manual/galicia_profile_alt_domain_20260212T141822Z_profile/first_party_sets.db`
- `etl/data/raw/manual/galicia_profile_test_20260212T141513Z_profile/first_party_sets.db`
- `etl/data/raw/manual/navarra_list_now_20260212T143859Z_profile/first_party_sets.db`
- `etl/data/raw/manual/navarra_list_refresh_20260212T143616Z_profile/first_party_sets.db`
- `etl/data/raw/manual/navarra_parlamentarios_20260212T131325Z_profile/first_party_sets.db`
- `etl/data/raw/manual/navarra_parlamentarios_20260212T131640Z_profile/first_party_sets.db`
- `etl/data/raw/manual/navarra_parlamentarios_20260212T131918Z_profile/first_party_sets.db`
- `etl/data/raw/manual/navarra_persona_profiles_20260212T141107Z/profile/first_party_sets.db`
- `etl/data/raw/manual/navarra_persona_profiles_20260212T141237Z/profile/first_party_sets.db`
- `etl/data/raw/manual/navarra_persona_profiles_20260212T143152Z/profile/first_party_sets.db`
- `etl/data/raw/manual/navarra_persona_profiles_20260212T143318Z/profile/first_party_sets.db`
- `etl/data/raw/manual/navarra_persona_profiles_20260212T144021Z/profile/first_party_sets.db`
- `etl/data/raw/manual/navarra_persona_profiles_20260212T144217Z/profile/first_party_sets.db`
- `etl/data/raw/manual/navarra_persona_profiles_20260212T144356Z/profile/first_party_sets.db`
- `etl/data/raw/manual/navarra_persona_profiles_slow_20260212T144448Z/profile/first_party_sets.db`
- `etl/data/raw/manual/navarra_persona_test2_20260212T144619Z_profile/first_party_sets.db`
- `etl/data/raw/manual/navarra_persona_test_20260212T142934Z_profile/first_party_sets.db`
- `etl/data/raw/manual/senado_iniciativas_cookie_seed_20260218T083457Z_profile/first_party_sets.db`
- `etl/data/raw/manual/senado_iniciativas_cookie_seed_refresh_20260218T201301Z_profile/first_party_sets.db`
- `etl/data/raw/manual/senado_votaciones_ses/.headful-profile/first_party_sets.db`

### `54f7dc72f40bfd5f`

- Files: `23`
- Tables: `2`
- Views: `0`
- Category mix: `browser_profile_heavy_ad_intervention_opt_out`
- Sample: `etl/data/raw/manual/galicia_deputado_profiles_20260212T141413Z/profile/Default/heavy_ad_intervention_opt_out.db`
- Missing vs canonical: `75`
- Extra vs canonical: `2`

Tables:
- `enabled_previews_v1`
- `previews_v1`

Missing tables vs canonical:
- `admin_levels`
- `causal_estimates`
- `document_fetches`
- `domains`
- `genders`
- `indicator_observation_records`
- `indicator_points`
- `indicator_series`
- `infoelectoral_archivos_extraccion`
- `infoelectoral_convocatoria_tipos`
- `infoelectoral_convocatorias`
- `infoelectoral_proceso_resultados`
- `infoelectoral_procesos`
- `ingestion_runs`
- `institutions`
- `intervention_events`
- `interventions`
- `legal_fragment_responsibilities`
- `legal_fragment_responsibility_evidence`
- `legal_norm_fragments`
- `legal_norm_lineage_edges`
- `legal_norms`
- `liberty_delegated_enforcement_links`
- `liberty_delegated_enforcement_methodologies`
- `liberty_enforcement_methodologies`
- `liberty_enforcement_observations`
- `liberty_indirect_methodologies`
- `liberty_indirect_responsibility_edges`
- `liberty_irlc_methodologies`
- `liberty_proportionality_methodologies`
- `liberty_proportionality_reviews`
- `liberty_restriction_assessments`
- `liberty_right_categories`
- `lost_and_found`
- `mandates`
- `money_contract_records`
- `money_subsidy_records`
- `parl_initiative_doc_extractions`
- `parl_initiative_documents`
- `parl_initiatives`
- `parl_vote_event_initiatives`
- `parl_vote_events`
- `parl_vote_member_votes`
- `parties`
- `party_aliases`
- `person_identifiers`
- `person_name_aliases`
- `persons`
- `policy_axes`
- `policy_event_axis_scores`
- `policy_events`
- `policy_instruments`
- `raw_fetches`
- `roles`
- `run_fetches`
- `sanction_infraction_type_mappings`
- `sanction_infraction_types`
- `sanction_municipal_ordinance_fragments`
- `sanction_municipal_ordinances`
- `sanction_norm_catalog`
- `sanction_norm_fragment_links`
- `sanction_procedural_kpi_definitions`
- `sanction_procedural_metrics`
- `sanction_volume_observations`
- `sanction_volume_sources`
- `source_records`
- `sources`
- `territories`
- `text_documents`
- `topic_evidence`
- `topic_evidence_reviews`
- `topic_positions`
- `topic_set_topics`
- `topic_sets`
- `topics`

Extra tables vs canonical:
- `enabled_previews_v1`
- `previews_v1`

Files in this family:
- `etl/data/raw/manual/galicia_deputado_profiles_20260212T141413Z/profile/Default/heavy_ad_intervention_opt_out.db`
- `etl/data/raw/manual/galicia_deputado_profiles_20260212T141929Z/profile/Default/heavy_ad_intervention_opt_out.db`
- `etl/data/raw/manual/galicia_deputados_20260212T132244Z_profile/Default/heavy_ad_intervention_opt_out.db`
- `etl/data/raw/manual/galicia_profile_alt_domain_20260212T141822Z_profile/Default/heavy_ad_intervention_opt_out.db`
- `etl/data/raw/manual/galicia_profile_test_20260212T141513Z_profile/Default/heavy_ad_intervention_opt_out.db`
- `etl/data/raw/manual/navarra_list_now_20260212T143859Z_profile/Default/heavy_ad_intervention_opt_out.db`
- `etl/data/raw/manual/navarra_list_refresh_20260212T143616Z_profile/Default/heavy_ad_intervention_opt_out.db`
- `etl/data/raw/manual/navarra_parlamentarios_20260212T131325Z_profile/Default/heavy_ad_intervention_opt_out.db`
- `etl/data/raw/manual/navarra_parlamentarios_20260212T131640Z_profile/Default/heavy_ad_intervention_opt_out.db`
- `etl/data/raw/manual/navarra_parlamentarios_20260212T131918Z_profile/Default/heavy_ad_intervention_opt_out.db`
- `etl/data/raw/manual/navarra_persona_profiles_20260212T141107Z/profile/Default/heavy_ad_intervention_opt_out.db`
- `etl/data/raw/manual/navarra_persona_profiles_20260212T141237Z/profile/Default/heavy_ad_intervention_opt_out.db`
- `etl/data/raw/manual/navarra_persona_profiles_20260212T143152Z/profile/Default/heavy_ad_intervention_opt_out.db`
- `etl/data/raw/manual/navarra_persona_profiles_20260212T143318Z/profile/Default/heavy_ad_intervention_opt_out.db`
- `etl/data/raw/manual/navarra_persona_profiles_20260212T144021Z/profile/Default/heavy_ad_intervention_opt_out.db`
- `etl/data/raw/manual/navarra_persona_profiles_20260212T144217Z/profile/Default/heavy_ad_intervention_opt_out.db`
- `etl/data/raw/manual/navarra_persona_profiles_20260212T144356Z/profile/Default/heavy_ad_intervention_opt_out.db`
- `etl/data/raw/manual/navarra_persona_profiles_slow_20260212T144448Z/profile/Default/heavy_ad_intervention_opt_out.db`
- `etl/data/raw/manual/navarra_persona_test2_20260212T144619Z_profile/Default/heavy_ad_intervention_opt_out.db`
- `etl/data/raw/manual/navarra_persona_test_20260212T142934Z_profile/Default/heavy_ad_intervention_opt_out.db`
- `etl/data/raw/manual/senado_iniciativas_cookie_seed_20260218T083457Z_profile/Default/heavy_ad_intervention_opt_out.db`
- `etl/data/raw/manual/senado_iniciativas_cookie_seed_refresh_20260218T201301Z_profile/Default/heavy_ad_intervention_opt_out.db`
- `etl/data/raw/manual/senado_votaciones_ses/.headful-profile/Default/heavy_ad_intervention_opt_out.db`

### `c4e3f6856e09a14b`

- Files: `15`
- Tables: `71`
- Views: `0`
- Category mix: `platform_sqlite_variant, sprint_fixture_or_evidence_db`
- Sample: `docs/etl/sprints/AI-OPS-132/exports/liberty_representativity_20260223T203640Z.db`
- Missing vs canonical: `4`
- Extra vs canonical: `0`

Tables:
- `admin_levels`
- `causal_estimates`
- `document_fetches`
- `domains`
- `genders`
- `indicator_observation_records`
- `indicator_points`
- `indicator_series`
- `infoelectoral_archivos_extraccion`
- `infoelectoral_convocatoria_tipos`
- `infoelectoral_convocatorias`
- `infoelectoral_proceso_resultados`
- `infoelectoral_procesos`
- `ingestion_runs`
- `institutions`
- `intervention_events`
- `interventions`
- `legal_fragment_responsibilities`
- `legal_norm_fragments`
- `legal_norms`
- `liberty_delegated_enforcement_links`
- `liberty_delegated_enforcement_methodologies`
- `liberty_enforcement_methodologies`
- `liberty_enforcement_observations`
- `liberty_indirect_methodologies`
- `liberty_indirect_responsibility_edges`
- `liberty_irlc_methodologies`
- `liberty_proportionality_methodologies`
- `liberty_proportionality_reviews`
- `liberty_restriction_assessments`
- `liberty_right_categories`
- `mandates`
- `money_contract_records`
- `money_subsidy_records`
- `parl_initiative_doc_extractions`
- `parl_initiative_documents`
- `parl_initiatives`
- `parl_vote_event_initiatives`
- `parl_vote_events`
- `parl_vote_member_votes`
- `parties`
- `party_aliases`
- `person_identifiers`
- `persons`
- `policy_axes`
- `policy_event_axis_scores`
- `policy_events`
- `policy_instruments`
- `raw_fetches`
- `roles`
- `run_fetches`
- `sanction_infraction_type_mappings`
- `sanction_infraction_types`
- `sanction_municipal_ordinance_fragments`
- `sanction_municipal_ordinances`
- `sanction_norm_catalog`
- `sanction_norm_fragment_links`
- `sanction_procedural_kpi_definitions`
- `sanction_procedural_metrics`
- `sanction_volume_observations`
- `sanction_volume_sources`
- `source_records`
- `sources`
- `territories`
- `text_documents`
- `topic_evidence`
- `topic_evidence_reviews`
- `topic_positions`
- `topic_set_topics`
- `topic_sets`
- `topics`

Missing tables vs canonical:
- `legal_fragment_responsibility_evidence`
- `legal_norm_lineage_edges`
- `lost_and_found`
- `person_name_aliases`

Files in this family:
- `docs/etl/sprints/AI-OPS-132/exports/liberty_representativity_20260223T203640Z.db`
- `etl/data/staging/politicos-es.ai_ops_135.db`
- `etl/data/staging/politicos-es.ai_ops_136.db`
- `etl/data/staging/politicos-es.ai_ops_137.db`
- `etl/data/staging/politicos-es.ai_ops_138.db`
- `etl/data/staging/politicos-es.aiops121.db`
- `etl/data/staging/politicos-es.aiops122.db`
- `etl/data/staging/politicos-es.aiops123.db`
- `etl/data/staging/politicos-es.aiops129.db`
- `etl/data/staging/politicos-es.liberty-focus-ci-smoke.db`
- `tmp/ai_ops_139.db`
- `tmp/ai_ops_140.db`
- `tmp/aiops130/liberty_map_20260223T202028Z.db`
- `tmp/aiops131/liberty_heartbeat_20260223T202651Z.db`
- `tmp/liberty_person_identity_queue_20260223T215635Z.db`

### `fd43263fb254f6bb`

- Files: `12`
- Tables: `72`
- Views: `0`
- Category mix: `platform_sqlite_variant`
- Sample: `tmp/ai_ops_150_contract.db`
- Missing vs canonical: `3`
- Extra vs canonical: `0`

Tables:
- `admin_levels`
- `causal_estimates`
- `document_fetches`
- `domains`
- `genders`
- `indicator_observation_records`
- `indicator_points`
- `indicator_series`
- `infoelectoral_archivos_extraccion`
- `infoelectoral_convocatoria_tipos`
- `infoelectoral_convocatorias`
- `infoelectoral_proceso_resultados`
- `infoelectoral_procesos`
- `ingestion_runs`
- `institutions`
- `intervention_events`
- `interventions`
- `legal_fragment_responsibilities`
- `legal_norm_fragments`
- `legal_norms`
- `liberty_delegated_enforcement_links`
- `liberty_delegated_enforcement_methodologies`
- `liberty_enforcement_methodologies`
- `liberty_enforcement_observations`
- `liberty_indirect_methodologies`
- `liberty_indirect_responsibility_edges`
- `liberty_irlc_methodologies`
- `liberty_proportionality_methodologies`
- `liberty_proportionality_reviews`
- `liberty_restriction_assessments`
- `liberty_right_categories`
- `mandates`
- `money_contract_records`
- `money_subsidy_records`
- `parl_initiative_doc_extractions`
- `parl_initiative_documents`
- `parl_initiatives`
- `parl_vote_event_initiatives`
- `parl_vote_events`
- `parl_vote_member_votes`
- `parties`
- `party_aliases`
- `person_identifiers`
- `person_name_aliases`
- `persons`
- `policy_axes`
- `policy_event_axis_scores`
- `policy_events`
- `policy_instruments`
- `raw_fetches`
- `roles`
- `run_fetches`
- `sanction_infraction_type_mappings`
- `sanction_infraction_types`
- `sanction_municipal_ordinance_fragments`
- `sanction_municipal_ordinances`
- `sanction_norm_catalog`
- `sanction_norm_fragment_links`
- `sanction_procedural_kpi_definitions`
- `sanction_procedural_metrics`
- `sanction_volume_observations`
- `sanction_volume_sources`
- `source_records`
- `sources`
- `territories`
- `text_documents`
- `topic_evidence`
- `topic_evidence_reviews`
- `topic_positions`
- `topic_set_topics`
- `topic_sets`
- `topics`

Missing tables vs canonical:
- `legal_fragment_responsibility_evidence`
- `legal_norm_lineage_edges`
- `lost_and_found`

Files in this family:
- `tmp/ai_ops_150_contract.db`
- `tmp/liberty_person_identity_apply_20260223T220708Z.db`
- `tmp/liberty_person_identity_official_evidence_20260223T224358Z.db`
- `tmp/liberty_person_identity_official_evidence_contract_20260223T224358Z.db`
- `tmp/liberty_person_identity_official_share_20260223T225159Z.db`
- `tmp/liberty_person_identity_official_share_contract_20260223T225159Z.db`
- `tmp/liberty_person_identity_provenance_20260223T221925Z.db`
- `tmp/liberty_person_identity_provenance_upgrade_20260223T222707Z.db`
- `tmp/liberty_person_identity_source_guard_20260223T223309Z.db`
- `tmp/liberty_person_identity_source_guard_contract_20260223T223309Z.db`
- `tmp/liberty_person_identity_source_record_20260223T230526Z.db`
- `tmp/liberty_person_identity_source_record_contract_20260223T230526Z.db`

### `4315a0f56dd07075`

- Files: `9`
- Tables: `8`
- Views: `0`
- Category mix: `platform_sqlite_variant`
- Sample: `etl/data/staging/politicos-es.ci-gate-local.db`
- Missing vs canonical: `67`
- Extra vs canonical: `0`

Tables:
- `ingestion_runs`
- `institutions`
- `mandates`
- `parties`
- `person_identifiers`
- `persons`
- `raw_fetches`
- `sources`

Missing tables vs canonical:
- `admin_levels`
- `causal_estimates`
- `document_fetches`
- `domains`
- `genders`
- `indicator_observation_records`
- `indicator_points`
- `indicator_series`
- `infoelectoral_archivos_extraccion`
- `infoelectoral_convocatoria_tipos`
- `infoelectoral_convocatorias`
- `infoelectoral_proceso_resultados`
- `infoelectoral_procesos`
- `intervention_events`
- `interventions`
- `legal_fragment_responsibilities`
- `legal_fragment_responsibility_evidence`
- `legal_norm_fragments`
- `legal_norm_lineage_edges`
- `legal_norms`
- `liberty_delegated_enforcement_links`
- `liberty_delegated_enforcement_methodologies`
- `liberty_enforcement_methodologies`
- `liberty_enforcement_observations`
- `liberty_indirect_methodologies`
- `liberty_indirect_responsibility_edges`
- `liberty_irlc_methodologies`
- `liberty_proportionality_methodologies`
- `liberty_proportionality_reviews`
- `liberty_restriction_assessments`
- `liberty_right_categories`
- `lost_and_found`
- `money_contract_records`
- `money_subsidy_records`
- `parl_initiative_doc_extractions`
- `parl_initiative_documents`
- `parl_initiatives`
- `parl_vote_event_initiatives`
- `parl_vote_events`
- `parl_vote_member_votes`
- `party_aliases`
- `person_name_aliases`
- `policy_axes`
- `policy_event_axis_scores`
- `policy_events`
- `policy_instruments`
- `roles`
- `run_fetches`
- `sanction_infraction_type_mappings`
- `sanction_infraction_types`
- `sanction_municipal_ordinance_fragments`
- `sanction_municipal_ordinances`
- `sanction_norm_catalog`
- `sanction_norm_fragment_links`
- `sanction_procedural_kpi_definitions`
- `sanction_procedural_metrics`
- `sanction_volume_observations`
- `sanction_volume_sources`
- `source_records`
- `territories`
- `text_documents`
- `topic_evidence`
- `topic_evidence_reviews`
- `topic_positions`
- `topic_set_topics`
- `topic_sets`
- `topics`

Files in this family:
- `etl/data/staging/politicos-es.ci-gate-local.db`
- `etl/data/staging/politicos-es.clean.db`
- `etl/data/staging/politicos-es.e2e-20260212.db`
- `etl/data/staging/politicos-es.just-e2e-20260212.db`
- `etl/data/staging/politicos-es.senado-fix-all.db`
- `etl/data/staging/politicos-es.senado-fix-v2.db`
- `etl/data/staging/politicos-es.senado-fix.db`
- `etl/data/staging/politicos-es.strict-check.db`
- `etl/data/staging/politicos-es.tracker-check-20260212.db`

### `9540053a905bf7c2`

- Files: `2`
- Tables: `52`
- Views: `0`
- Category mix: `platform_sqlite_variant`
- Sample: `etl/data/staging/politicos-es.aiops115.20260223T173448Z.db`
- Missing vs canonical: `23`
- Extra vs canonical: `0`

Tables:
- `admin_levels`
- `causal_estimates`
- `document_fetches`
- `domains`
- `genders`
- `indicator_observation_records`
- `indicator_points`
- `indicator_series`
- `infoelectoral_archivos_extraccion`
- `infoelectoral_convocatoria_tipos`
- `infoelectoral_convocatorias`
- `infoelectoral_proceso_resultados`
- `infoelectoral_procesos`
- `ingestion_runs`
- `institutions`
- `intervention_events`
- `interventions`
- `legal_fragment_responsibilities`
- `legal_norm_fragments`
- `legal_norms`
- `mandates`
- `money_contract_records`
- `money_subsidy_records`
- `parl_initiative_doc_extractions`
- `parl_initiative_documents`
- `parl_initiatives`
- `parl_vote_event_initiatives`
- `parl_vote_events`
- `parl_vote_member_votes`
- `parties`
- `party_aliases`
- `person_identifiers`
- `persons`
- `policy_axes`
- `policy_event_axis_scores`
- `policy_events`
- `policy_instruments`
- `raw_fetches`
- `roles`
- `run_fetches`
- `sanction_norm_catalog`
- `sanction_norm_fragment_links`
- `source_records`
- `sources`
- `territories`
- `text_documents`
- `topic_evidence`
- `topic_evidence_reviews`
- `topic_positions`
- `topic_set_topics`
- `topic_sets`
- `topics`

Missing tables vs canonical:
- `legal_fragment_responsibility_evidence`
- `legal_norm_lineage_edges`
- `liberty_delegated_enforcement_links`
- `liberty_delegated_enforcement_methodologies`
- `liberty_enforcement_methodologies`
- `liberty_enforcement_observations`
- `liberty_indirect_methodologies`
- `liberty_indirect_responsibility_edges`
- `liberty_irlc_methodologies`
- `liberty_proportionality_methodologies`
- `liberty_proportionality_reviews`
- `liberty_restriction_assessments`
- `liberty_right_categories`
- `lost_and_found`
- `person_name_aliases`
- `sanction_infraction_type_mappings`
- `sanction_infraction_types`
- `sanction_municipal_ordinance_fragments`
- `sanction_municipal_ordinances`
- `sanction_procedural_kpi_definitions`
- `sanction_procedural_metrics`
- `sanction_volume_observations`
- `sanction_volume_sources`

Files in this family:
- `etl/data/staging/politicos-es.aiops115.20260223T173448Z.db`
- `etl/data/staging/politicos-es.aiops115.justpipeline.20260223T173646Z.db`

### `80a90ef042466929`

- Files: `2`
- Tables: `29`
- Views: `0`
- Category mix: `platform_sqlite_variant`
- Sample: `etl/data/staging/politicos-es.fresh.recovered.20260214_1705.db`
- Missing vs canonical: `46`
- Extra vs canonical: `0`

Tables:
- `admin_levels`
- `genders`
- `infoelectoral_archivos_extraccion`
- `infoelectoral_convocatoria_tipos`
- `infoelectoral_convocatorias`
- `infoelectoral_proceso_resultados`
- `infoelectoral_procesos`
- `ingestion_runs`
- `institutions`
- `lost_and_found`
- `mandates`
- `parl_initiatives`
- `parl_vote_event_initiatives`
- `parl_vote_events`
- `parl_vote_member_votes`
- `parties`
- `party_aliases`
- `person_identifiers`
- `persons`
- `raw_fetches`
- `roles`
- `source_records`
- `sources`
- `territories`
- `topic_evidence`
- `topic_positions`
- `topic_set_topics`
- `topic_sets`
- `topics`

Missing tables vs canonical:
- `causal_estimates`
- `document_fetches`
- `domains`
- `indicator_observation_records`
- `indicator_points`
- `indicator_series`
- `intervention_events`
- `interventions`
- `legal_fragment_responsibilities`
- `legal_fragment_responsibility_evidence`
- `legal_norm_fragments`
- `legal_norm_lineage_edges`
- `legal_norms`
- `liberty_delegated_enforcement_links`
- `liberty_delegated_enforcement_methodologies`
- `liberty_enforcement_methodologies`
- `liberty_enforcement_observations`
- `liberty_indirect_methodologies`
- `liberty_indirect_responsibility_edges`
- `liberty_irlc_methodologies`
- `liberty_proportionality_methodologies`
- `liberty_proportionality_reviews`
- `liberty_restriction_assessments`
- `liberty_right_categories`
- `money_contract_records`
- `money_subsidy_records`
- `parl_initiative_doc_extractions`
- `parl_initiative_documents`
- `person_name_aliases`
- `policy_axes`
- `policy_event_axis_scores`
- `policy_events`
- `policy_instruments`
- `run_fetches`
- `sanction_infraction_type_mappings`
- `sanction_infraction_types`
- `sanction_municipal_ordinance_fragments`
- `sanction_municipal_ordinances`
- `sanction_norm_catalog`
- `sanction_norm_fragment_links`
- `sanction_procedural_kpi_definitions`
- `sanction_procedural_metrics`
- `sanction_volume_observations`
- `sanction_volume_sources`
- `text_documents`
- `topic_evidence_reviews`

Files in this family:
- `etl/data/staging/politicos-es.fresh.recovered.20260214_1705.db`
- `etl/data/staging/politicos-es.fresh.work.20260214_1710.db`

### `8479f1303c9a3bb8`

- Files: `2`
- Tables: `21`
- Views: `0`
- Category mix: `platform_sqlite_variant`
- Sample: `etl/data/staging/parl-quality-smoke.db`
- Missing vs canonical: `54`
- Extra vs canonical: `0`

Tables:
- `admin_levels`
- `genders`
- `infoelectoral_archivos_extraccion`
- `infoelectoral_convocatoria_tipos`
- `infoelectoral_convocatorias`
- `ingestion_runs`
- `institutions`
- `mandates`
- `parl_initiatives`
- `parl_vote_event_initiatives`
- `parl_vote_events`
- `parl_vote_member_votes`
- `parties`
- `party_aliases`
- `person_identifiers`
- `persons`
- `raw_fetches`
- `roles`
- `source_records`
- `sources`
- `territories`

Missing tables vs canonical:
- `causal_estimates`
- `document_fetches`
- `domains`
- `indicator_observation_records`
- `indicator_points`
- `indicator_series`
- `infoelectoral_proceso_resultados`
- `infoelectoral_procesos`
- `intervention_events`
- `interventions`
- `legal_fragment_responsibilities`
- `legal_fragment_responsibility_evidence`
- `legal_norm_fragments`
- `legal_norm_lineage_edges`
- `legal_norms`
- `liberty_delegated_enforcement_links`
- `liberty_delegated_enforcement_methodologies`
- `liberty_enforcement_methodologies`
- `liberty_enforcement_observations`
- `liberty_indirect_methodologies`
- `liberty_indirect_responsibility_edges`
- `liberty_irlc_methodologies`
- `liberty_proportionality_methodologies`
- `liberty_proportionality_reviews`
- `liberty_restriction_assessments`
- `liberty_right_categories`
- `lost_and_found`
- `money_contract_records`
- `money_subsidy_records`
- `parl_initiative_doc_extractions`
- `parl_initiative_documents`
- `person_name_aliases`
- `policy_axes`
- `policy_event_axis_scores`
- `policy_events`
- `policy_instruments`
- `run_fetches`
- `sanction_infraction_type_mappings`
- `sanction_infraction_types`
- `sanction_municipal_ordinance_fragments`
- `sanction_municipal_ordinances`
- `sanction_norm_catalog`
- `sanction_norm_fragment_links`
- `sanction_procedural_kpi_definitions`
- `sanction_procedural_metrics`
- `sanction_volume_observations`
- `sanction_volume_sources`
- `text_documents`
- `topic_evidence`
- `topic_evidence_reviews`
- `topic_positions`
- `topic_set_topics`
- `topic_sets`
- `topics`

Files in this family:
- `etl/data/staging/parl-quality-smoke.db`
- `etl/data/staging/parl-quick.db`

### `57284d24516fe4de`

- Files: `2`
- Tables: `0`
- Views: `0`
- Category mix: `empty_placeholder`
- Sample: `politicos-es.db`
- Missing vs canonical: `75`
- Extra vs canonical: `0`

Tables:
- _(none)_

Missing tables vs canonical:
- `admin_levels`
- `causal_estimates`
- `document_fetches`
- `domains`
- `genders`
- `indicator_observation_records`
- `indicator_points`
- `indicator_series`
- `infoelectoral_archivos_extraccion`
- `infoelectoral_convocatoria_tipos`
- `infoelectoral_convocatorias`
- `infoelectoral_proceso_resultados`
- `infoelectoral_procesos`
- `ingestion_runs`
- `institutions`
- `intervention_events`
- `interventions`
- `legal_fragment_responsibilities`
- `legal_fragment_responsibility_evidence`
- `legal_norm_fragments`
- `legal_norm_lineage_edges`
- `legal_norms`
- `liberty_delegated_enforcement_links`
- `liberty_delegated_enforcement_methodologies`
- `liberty_enforcement_methodologies`
- `liberty_enforcement_observations`
- `liberty_indirect_methodologies`
- `liberty_indirect_responsibility_edges`
- `liberty_irlc_methodologies`
- `liberty_proportionality_methodologies`
- `liberty_proportionality_reviews`
- `liberty_restriction_assessments`
- `liberty_right_categories`
- `lost_and_found`
- `mandates`
- `money_contract_records`
- `money_subsidy_records`
- `parl_initiative_doc_extractions`
- `parl_initiative_documents`
- `parl_initiatives`
- `parl_vote_event_initiatives`
- `parl_vote_events`
- `parl_vote_member_votes`
- `parties`
- `party_aliases`
- `person_identifiers`
- `person_name_aliases`
- `persons`
- `policy_axes`
- `policy_event_axis_scores`
- `policy_events`
- `policy_instruments`
- `raw_fetches`
- `roles`
- `run_fetches`
- `sanction_infraction_type_mappings`
- `sanction_infraction_types`
- `sanction_municipal_ordinance_fragments`
- `sanction_municipal_ordinances`
- `sanction_norm_catalog`
- `sanction_norm_fragment_links`
- `sanction_procedural_kpi_definitions`
- `sanction_procedural_metrics`
- `sanction_volume_observations`
- `sanction_volume_sources`
- `source_records`
- `sources`
- `territories`
- `text_documents`
- `topic_evidence`
- `topic_evidence_reviews`
- `topic_positions`
- `topic_set_topics`
- `topic_sets`
- `topics`

Files in this family:
- `politicos-es.db`
- `politicos-es.e2e19.db`

### `030bd477d6eda00e`

- Files: `1`
- Tables: `75`
- Views: `0`
- Category mix: `platform_sqlite_variant`
- Sample: `etl/data/staging/politicos-es.db`
- Missing vs canonical: `0`
- Extra vs canonical: `0`

Tables:
- `admin_levels`
- `causal_estimates`
- `document_fetches`
- `domains`
- `genders`
- `indicator_observation_records`
- `indicator_points`
- `indicator_series`
- `infoelectoral_archivos_extraccion`
- `infoelectoral_convocatoria_tipos`
- `infoelectoral_convocatorias`
- `infoelectoral_proceso_resultados`
- `infoelectoral_procesos`
- `ingestion_runs`
- `institutions`
- `intervention_events`
- `interventions`
- `legal_fragment_responsibilities`
- `legal_fragment_responsibility_evidence`
- `legal_norm_fragments`
- `legal_norm_lineage_edges`
- `legal_norms`
- `liberty_delegated_enforcement_links`
- `liberty_delegated_enforcement_methodologies`
- `liberty_enforcement_methodologies`
- `liberty_enforcement_observations`
- `liberty_indirect_methodologies`
- `liberty_indirect_responsibility_edges`
- `liberty_irlc_methodologies`
- `liberty_proportionality_methodologies`
- `liberty_proportionality_reviews`
- `liberty_restriction_assessments`
- `liberty_right_categories`
- `lost_and_found`
- `mandates`
- `money_contract_records`
- `money_subsidy_records`
- `parl_initiative_doc_extractions`
- `parl_initiative_documents`
- `parl_initiatives`
- `parl_vote_event_initiatives`
- `parl_vote_events`
- `parl_vote_member_votes`
- `parties`
- `party_aliases`
- `person_identifiers`
- `person_name_aliases`
- `persons`
- `policy_axes`
- `policy_event_axis_scores`
- `policy_events`
- `policy_instruments`
- `raw_fetches`
- `roles`
- `run_fetches`
- `sanction_infraction_type_mappings`
- `sanction_infraction_types`
- `sanction_municipal_ordinance_fragments`
- `sanction_municipal_ordinances`
- `sanction_norm_catalog`
- `sanction_norm_fragment_links`
- `sanction_procedural_kpi_definitions`
- `sanction_procedural_metrics`
- `sanction_volume_observations`
- `sanction_volume_sources`
- `source_records`
- `sources`
- `territories`
- `text_documents`
- `topic_evidence`
- `topic_evidence_reviews`
- `topic_positions`
- `topic_set_topics`
- `topic_sets`
- `topics`

Files in this family:
- `etl/data/staging/politicos-es.db`

### `71f4436a39ecd79c`

- Files: `1`
- Tables: `74`
- Views: `0`
- Category mix: `sprint_fixture_or_evidence_db`
- Sample: `docs/etl/sprints/AI-OPS-189/evidence/sanction_procedural_official_review_raw_packets_cycle_fixture_20260224T114814Z.db`
- Missing vs canonical: `1`
- Extra vs canonical: `0`

Tables:
- `admin_levels`
- `causal_estimates`
- `document_fetches`
- `domains`
- `genders`
- `indicator_observation_records`
- `indicator_points`
- `indicator_series`
- `infoelectoral_archivos_extraccion`
- `infoelectoral_convocatoria_tipos`
- `infoelectoral_convocatorias`
- `infoelectoral_proceso_resultados`
- `infoelectoral_procesos`
- `ingestion_runs`
- `institutions`
- `intervention_events`
- `interventions`
- `legal_fragment_responsibilities`
- `legal_fragment_responsibility_evidence`
- `legal_norm_fragments`
- `legal_norm_lineage_edges`
- `legal_norms`
- `liberty_delegated_enforcement_links`
- `liberty_delegated_enforcement_methodologies`
- `liberty_enforcement_methodologies`
- `liberty_enforcement_observations`
- `liberty_indirect_methodologies`
- `liberty_indirect_responsibility_edges`
- `liberty_irlc_methodologies`
- `liberty_proportionality_methodologies`
- `liberty_proportionality_reviews`
- `liberty_restriction_assessments`
- `liberty_right_categories`
- `mandates`
- `money_contract_records`
- `money_subsidy_records`
- `parl_initiative_doc_extractions`
- `parl_initiative_documents`
- `parl_initiatives`
- `parl_vote_event_initiatives`
- `parl_vote_events`
- `parl_vote_member_votes`
- `parties`
- `party_aliases`
- `person_identifiers`
- `person_name_aliases`
- `persons`
- `policy_axes`
- `policy_event_axis_scores`
- `policy_events`
- `policy_instruments`
- `raw_fetches`
- `roles`
- `run_fetches`
- `sanction_infraction_type_mappings`
- `sanction_infraction_types`
- `sanction_municipal_ordinance_fragments`
- `sanction_municipal_ordinances`
- `sanction_norm_catalog`
- `sanction_norm_fragment_links`
- `sanction_procedural_kpi_definitions`
- `sanction_procedural_metrics`
- `sanction_volume_observations`
- `sanction_volume_sources`
- `source_records`
- `sources`
- `territories`
- `text_documents`
- `topic_evidence`
- `topic_evidence_reviews`
- `topic_positions`
- `topic_set_topics`
- `topic_sets`
- `topics`

Missing tables vs canonical:
- `lost_and_found`

Files in this family:
- `docs/etl/sprints/AI-OPS-189/evidence/sanction_procedural_official_review_raw_packets_cycle_fixture_20260224T114814Z.db`

### `642161a632336f6a`

- Files: `1`
- Tables: `69`
- Views: `0`
- Category mix: `platform_sqlite_variant`
- Sample: `etl/data/staging/politicos-es.aiops120.db`
- Missing vs canonical: `6`
- Extra vs canonical: `0`

Tables:
- `admin_levels`
- `causal_estimates`
- `document_fetches`
- `domains`
- `genders`
- `indicator_observation_records`
- `indicator_points`
- `indicator_series`
- `infoelectoral_archivos_extraccion`
- `infoelectoral_convocatoria_tipos`
- `infoelectoral_convocatorias`
- `infoelectoral_proceso_resultados`
- `infoelectoral_procesos`
- `ingestion_runs`
- `institutions`
- `intervention_events`
- `interventions`
- `legal_fragment_responsibilities`
- `legal_norm_fragments`
- `legal_norms`
- `liberty_enforcement_methodologies`
- `liberty_enforcement_observations`
- `liberty_indirect_methodologies`
- `liberty_indirect_responsibility_edges`
- `liberty_irlc_methodologies`
- `liberty_proportionality_methodologies`
- `liberty_proportionality_reviews`
- `liberty_restriction_assessments`
- `liberty_right_categories`
- `mandates`
- `money_contract_records`
- `money_subsidy_records`
- `parl_initiative_doc_extractions`
- `parl_initiative_documents`
- `parl_initiatives`
- `parl_vote_event_initiatives`
- `parl_vote_events`
- `parl_vote_member_votes`
- `parties`
- `party_aliases`
- `person_identifiers`
- `persons`
- `policy_axes`
- `policy_event_axis_scores`
- `policy_events`
- `policy_instruments`
- `raw_fetches`
- `roles`
- `run_fetches`
- `sanction_infraction_type_mappings`
- `sanction_infraction_types`
- `sanction_municipal_ordinance_fragments`
- `sanction_municipal_ordinances`
- `sanction_norm_catalog`
- `sanction_norm_fragment_links`
- `sanction_procedural_kpi_definitions`
- `sanction_procedural_metrics`
- `sanction_volume_observations`
- `sanction_volume_sources`
- `source_records`
- `sources`
- `territories`
- `text_documents`
- `topic_evidence`
- `topic_evidence_reviews`
- `topic_positions`
- `topic_set_topics`
- `topic_sets`
- `topics`

Missing tables vs canonical:
- `legal_fragment_responsibility_evidence`
- `legal_norm_lineage_edges`
- `liberty_delegated_enforcement_links`
- `liberty_delegated_enforcement_methodologies`
- `lost_and_found`
- `person_name_aliases`

Files in this family:
- `etl/data/staging/politicos-es.aiops120.db`

### `332a2a1eb23146bb`

- Files: `1`
- Tables: `65`
- Views: `0`
- Category mix: `platform_sqlite_variant`
- Sample: `etl/data/staging/politicos-es.aiops119.db`
- Missing vs canonical: `10`
- Extra vs canonical: `0`

Tables:
- `admin_levels`
- `causal_estimates`
- `document_fetches`
- `domains`
- `genders`
- `indicator_observation_records`
- `indicator_points`
- `indicator_series`
- `infoelectoral_archivos_extraccion`
- `infoelectoral_convocatoria_tipos`
- `infoelectoral_convocatorias`
- `infoelectoral_proceso_resultados`
- `infoelectoral_procesos`
- `ingestion_runs`
- `institutions`
- `intervention_events`
- `interventions`
- `legal_fragment_responsibilities`
- `legal_norm_fragments`
- `legal_norms`
- `liberty_irlc_methodologies`
- `liberty_proportionality_methodologies`
- `liberty_proportionality_reviews`
- `liberty_restriction_assessments`
- `liberty_right_categories`
- `mandates`
- `money_contract_records`
- `money_subsidy_records`
- `parl_initiative_doc_extractions`
- `parl_initiative_documents`
- `parl_initiatives`
- `parl_vote_event_initiatives`
- `parl_vote_events`
- `parl_vote_member_votes`
- `parties`
- `party_aliases`
- `person_identifiers`
- `persons`
- `policy_axes`
- `policy_event_axis_scores`
- `policy_events`
- `policy_instruments`
- `raw_fetches`
- `roles`
- `run_fetches`
- `sanction_infraction_type_mappings`
- `sanction_infraction_types`
- `sanction_municipal_ordinance_fragments`
- `sanction_municipal_ordinances`
- `sanction_norm_catalog`
- `sanction_norm_fragment_links`
- `sanction_procedural_kpi_definitions`
- `sanction_procedural_metrics`
- `sanction_volume_observations`
- `sanction_volume_sources`
- `source_records`
- `sources`
- `territories`
- `text_documents`
- `topic_evidence`
- `topic_evidence_reviews`
- `topic_positions`
- `topic_set_topics`
- `topic_sets`
- `topics`

Missing tables vs canonical:
- `legal_fragment_responsibility_evidence`
- `legal_norm_lineage_edges`
- `liberty_delegated_enforcement_links`
- `liberty_delegated_enforcement_methodologies`
- `liberty_enforcement_methodologies`
- `liberty_enforcement_observations`
- `liberty_indirect_methodologies`
- `liberty_indirect_responsibility_edges`
- `lost_and_found`
- `person_name_aliases`

Files in this family:
- `etl/data/staging/politicos-es.aiops119.db`

### `8efa489f714a957b`

- Files: `1`
- Tables: `63`
- Views: `0`
- Category mix: `platform_sqlite_variant`
- Sample: `etl/data/staging/politicos-es.aiops118.db`
- Missing vs canonical: `12`
- Extra vs canonical: `0`

Tables:
- `admin_levels`
- `causal_estimates`
- `document_fetches`
- `domains`
- `genders`
- `indicator_observation_records`
- `indicator_points`
- `indicator_series`
- `infoelectoral_archivos_extraccion`
- `infoelectoral_convocatoria_tipos`
- `infoelectoral_convocatorias`
- `infoelectoral_proceso_resultados`
- `infoelectoral_procesos`
- `ingestion_runs`
- `institutions`
- `intervention_events`
- `interventions`
- `legal_fragment_responsibilities`
- `legal_norm_fragments`
- `legal_norms`
- `liberty_irlc_methodologies`
- `liberty_restriction_assessments`
- `liberty_right_categories`
- `mandates`
- `money_contract_records`
- `money_subsidy_records`
- `parl_initiative_doc_extractions`
- `parl_initiative_documents`
- `parl_initiatives`
- `parl_vote_event_initiatives`
- `parl_vote_events`
- `parl_vote_member_votes`
- `parties`
- `party_aliases`
- `person_identifiers`
- `persons`
- `policy_axes`
- `policy_event_axis_scores`
- `policy_events`
- `policy_instruments`
- `raw_fetches`
- `roles`
- `run_fetches`
- `sanction_infraction_type_mappings`
- `sanction_infraction_types`
- `sanction_municipal_ordinance_fragments`
- `sanction_municipal_ordinances`
- `sanction_norm_catalog`
- `sanction_norm_fragment_links`
- `sanction_procedural_kpi_definitions`
- `sanction_procedural_metrics`
- `sanction_volume_observations`
- `sanction_volume_sources`
- `source_records`
- `sources`
- `territories`
- `text_documents`
- `topic_evidence`
- `topic_evidence_reviews`
- `topic_positions`
- `topic_set_topics`
- `topic_sets`
- `topics`

Missing tables vs canonical:
- `legal_fragment_responsibility_evidence`
- `legal_norm_lineage_edges`
- `liberty_delegated_enforcement_links`
- `liberty_delegated_enforcement_methodologies`
- `liberty_enforcement_methodologies`
- `liberty_enforcement_observations`
- `liberty_indirect_methodologies`
- `liberty_indirect_responsibility_edges`
- `liberty_proportionality_methodologies`
- `liberty_proportionality_reviews`
- `lost_and_found`
- `person_name_aliases`

Files in this family:
- `etl/data/staging/politicos-es.aiops118.db`

### `eeeceea44a97a592`

- Files: `1`
- Tables: `60`
- Views: `0`
- Category mix: `platform_sqlite_variant`
- Sample: `etl/data/staging/politicos-es.aiops117.db`
- Missing vs canonical: `15`
- Extra vs canonical: `0`

Tables:
- `admin_levels`
- `causal_estimates`
- `document_fetches`
- `domains`
- `genders`
- `indicator_observation_records`
- `indicator_points`
- `indicator_series`
- `infoelectoral_archivos_extraccion`
- `infoelectoral_convocatoria_tipos`
- `infoelectoral_convocatorias`
- `infoelectoral_proceso_resultados`
- `infoelectoral_procesos`
- `ingestion_runs`
- `institutions`
- `intervention_events`
- `interventions`
- `legal_fragment_responsibilities`
- `legal_norm_fragments`
- `legal_norms`
- `mandates`
- `money_contract_records`
- `money_subsidy_records`
- `parl_initiative_doc_extractions`
- `parl_initiative_documents`
- `parl_initiatives`
- `parl_vote_event_initiatives`
- `parl_vote_events`
- `parl_vote_member_votes`
- `parties`
- `party_aliases`
- `person_identifiers`
- `persons`
- `policy_axes`
- `policy_event_axis_scores`
- `policy_events`
- `policy_instruments`
- `raw_fetches`
- `roles`
- `run_fetches`
- `sanction_infraction_type_mappings`
- `sanction_infraction_types`
- `sanction_municipal_ordinance_fragments`
- `sanction_municipal_ordinances`
- `sanction_norm_catalog`
- `sanction_norm_fragment_links`
- `sanction_procedural_kpi_definitions`
- `sanction_procedural_metrics`
- `sanction_volume_observations`
- `sanction_volume_sources`
- `source_records`
- `sources`
- `territories`
- `text_documents`
- `topic_evidence`
- `topic_evidence_reviews`
- `topic_positions`
- `topic_set_topics`
- `topic_sets`
- `topics`

Missing tables vs canonical:
- `legal_fragment_responsibility_evidence`
- `legal_norm_lineage_edges`
- `liberty_delegated_enforcement_links`
- `liberty_delegated_enforcement_methodologies`
- `liberty_enforcement_methodologies`
- `liberty_enforcement_observations`
- `liberty_indirect_methodologies`
- `liberty_indirect_responsibility_edges`
- `liberty_irlc_methodologies`
- `liberty_proportionality_methodologies`
- `liberty_proportionality_reviews`
- `liberty_restriction_assessments`
- `liberty_right_categories`
- `lost_and_found`
- `person_name_aliases`

Files in this family:
- `etl/data/staging/politicos-es.aiops117.db`

### `acd27ce46df459ed`

- Files: `1`
- Tables: `58`
- Views: `0`
- Category mix: `platform_sqlite_variant`
- Sample: `etl/data/staging/politicos-es.aiops116.20260223T174656Z.db`
- Missing vs canonical: `17`
- Extra vs canonical: `0`

Tables:
- `admin_levels`
- `causal_estimates`
- `document_fetches`
- `domains`
- `genders`
- `indicator_observation_records`
- `indicator_points`
- `indicator_series`
- `infoelectoral_archivos_extraccion`
- `infoelectoral_convocatoria_tipos`
- `infoelectoral_convocatorias`
- `infoelectoral_proceso_resultados`
- `infoelectoral_procesos`
- `ingestion_runs`
- `institutions`
- `intervention_events`
- `interventions`
- `legal_fragment_responsibilities`
- `legal_norm_fragments`
- `legal_norms`
- `mandates`
- `money_contract_records`
- `money_subsidy_records`
- `parl_initiative_doc_extractions`
- `parl_initiative_documents`
- `parl_initiatives`
- `parl_vote_event_initiatives`
- `parl_vote_events`
- `parl_vote_member_votes`
- `parties`
- `party_aliases`
- `person_identifiers`
- `persons`
- `policy_axes`
- `policy_event_axis_scores`
- `policy_events`
- `policy_instruments`
- `raw_fetches`
- `roles`
- `run_fetches`
- `sanction_infraction_type_mappings`
- `sanction_infraction_types`
- `sanction_norm_catalog`
- `sanction_norm_fragment_links`
- `sanction_procedural_kpi_definitions`
- `sanction_procedural_metrics`
- `sanction_volume_observations`
- `sanction_volume_sources`
- `source_records`
- `sources`
- `territories`
- `text_documents`
- `topic_evidence`
- `topic_evidence_reviews`
- `topic_positions`
- `topic_set_topics`
- `topic_sets`
- `topics`

Missing tables vs canonical:
- `legal_fragment_responsibility_evidence`
- `legal_norm_lineage_edges`
- `liberty_delegated_enforcement_links`
- `liberty_delegated_enforcement_methodologies`
- `liberty_enforcement_methodologies`
- `liberty_enforcement_observations`
- `liberty_indirect_methodologies`
- `liberty_indirect_responsibility_edges`
- `liberty_irlc_methodologies`
- `liberty_proportionality_methodologies`
- `liberty_proportionality_reviews`
- `liberty_restriction_assessments`
- `liberty_right_categories`
- `lost_and_found`
- `person_name_aliases`
- `sanction_municipal_ordinance_fragments`
- `sanction_municipal_ordinances`

Files in this family:
- `etl/data/staging/politicos-es.aiops116.20260223T174656Z.db`

### `9f69e4335f9bd10f`

- Files: `1`
- Tables: `41`
- Views: `0`
- Category mix: `platform_sqlite_variant`
- Sample: `etl/data/staging/moncloa-aiops04-matrix-20260216.db`
- Missing vs canonical: `34`
- Extra vs canonical: `0`

Tables:
- `admin_levels`
- `causal_estimates`
- `domains`
- `genders`
- `indicator_points`
- `indicator_series`
- `infoelectoral_archivos_extraccion`
- `infoelectoral_convocatoria_tipos`
- `infoelectoral_convocatorias`
- `infoelectoral_proceso_resultados`
- `infoelectoral_procesos`
- `ingestion_runs`
- `institutions`
- `intervention_events`
- `interventions`
- `mandates`
- `parl_initiatives`
- `parl_vote_event_initiatives`
- `parl_vote_events`
- `parl_vote_member_votes`
- `parties`
- `party_aliases`
- `person_identifiers`
- `persons`
- `policy_axes`
- `policy_event_axis_scores`
- `policy_events`
- `policy_instruments`
- `raw_fetches`
- `roles`
- `run_fetches`
- `source_records`
- `sources`
- `territories`
- `text_documents`
- `topic_evidence`
- `topic_evidence_reviews`
- `topic_positions`
- `topic_set_topics`
- `topic_sets`
- `topics`

Missing tables vs canonical:
- `document_fetches`
- `indicator_observation_records`
- `legal_fragment_responsibilities`
- `legal_fragment_responsibility_evidence`
- `legal_norm_fragments`
- `legal_norm_lineage_edges`
- `legal_norms`
- `liberty_delegated_enforcement_links`
- `liberty_delegated_enforcement_methodologies`
- `liberty_enforcement_methodologies`
- `liberty_enforcement_observations`
- `liberty_indirect_methodologies`
- `liberty_indirect_responsibility_edges`
- `liberty_irlc_methodologies`
- `liberty_proportionality_methodologies`
- `liberty_proportionality_reviews`
- `liberty_restriction_assessments`
- `liberty_right_categories`
- `lost_and_found`
- `money_contract_records`
- `money_subsidy_records`
- `parl_initiative_doc_extractions`
- `parl_initiative_documents`
- `person_name_aliases`
- `sanction_infraction_type_mappings`
- `sanction_infraction_types`
- `sanction_municipal_ordinance_fragments`
- `sanction_municipal_ordinances`
- `sanction_norm_catalog`
- `sanction_norm_fragment_links`
- `sanction_procedural_kpi_definitions`
- `sanction_procedural_metrics`
- `sanction_volume_observations`
- `sanction_volume_sources`

Files in this family:
- `etl/data/staging/moncloa-aiops04-matrix-20260216.db`

### `25015d0743ebc215`

- Files: `1`
- Tables: `29`
- Views: `0`
- Category mix: `platform_sqlite_variant`
- Sample: `etl/data/staging/politicos-es.e2e19.db`
- Missing vs canonical: `46`
- Extra vs canonical: `0`

Tables:
- `admin_levels`
- `genders`
- `infoelectoral_archivos_extraccion`
- `infoelectoral_convocatoria_tipos`
- `infoelectoral_convocatorias`
- `infoelectoral_proceso_resultados`
- `infoelectoral_procesos`
- `ingestion_runs`
- `institutions`
- `mandates`
- `parl_initiatives`
- `parl_vote_event_initiatives`
- `parl_vote_events`
- `parl_vote_member_votes`
- `parties`
- `party_aliases`
- `person_identifiers`
- `persons`
- `raw_fetches`
- `roles`
- `run_fetches`
- `source_records`
- `sources`
- `territories`
- `topic_evidence`
- `topic_positions`
- `topic_set_topics`
- `topic_sets`
- `topics`

Missing tables vs canonical:
- `causal_estimates`
- `document_fetches`
- `domains`
- `indicator_observation_records`
- `indicator_points`
- `indicator_series`
- `intervention_events`
- `interventions`
- `legal_fragment_responsibilities`
- `legal_fragment_responsibility_evidence`
- `legal_norm_fragments`
- `legal_norm_lineage_edges`
- `legal_norms`
- `liberty_delegated_enforcement_links`
- `liberty_delegated_enforcement_methodologies`
- `liberty_enforcement_methodologies`
- `liberty_enforcement_observations`
- `liberty_indirect_methodologies`
- `liberty_indirect_responsibility_edges`
- `liberty_irlc_methodologies`
- `liberty_proportionality_methodologies`
- `liberty_proportionality_reviews`
- `liberty_restriction_assessments`
- `liberty_right_categories`
- `lost_and_found`
- `money_contract_records`
- `money_subsidy_records`
- `parl_initiative_doc_extractions`
- `parl_initiative_documents`
- `person_name_aliases`
- `policy_axes`
- `policy_event_axis_scores`
- `policy_events`
- `policy_instruments`
- `sanction_infraction_type_mappings`
- `sanction_infraction_types`
- `sanction_municipal_ordinance_fragments`
- `sanction_municipal_ordinances`
- `sanction_norm_catalog`
- `sanction_norm_fragment_links`
- `sanction_procedural_kpi_definitions`
- `sanction_procedural_metrics`
- `sanction_volume_observations`
- `sanction_volume_sources`
- `text_documents`
- `topic_evidence_reviews`

Files in this family:
- `etl/data/staging/politicos-es.e2e19.db`

### `841b2d9125c2a0f1`

- Files: `1`
- Tables: `28`
- Views: `0`
- Category mix: `platform_sqlite_variant`
- Sample: `etl/data/staging/politicos-es.fresh.db`
- Missing vs canonical: `47`
- Extra vs canonical: `0`

Tables:
- `admin_levels`
- `genders`
- `infoelectoral_archivos_extraccion`
- `infoelectoral_convocatoria_tipos`
- `infoelectoral_convocatorias`
- `infoelectoral_proceso_resultados`
- `infoelectoral_procesos`
- `ingestion_runs`
- `institutions`
- `mandates`
- `parl_initiatives`
- `parl_vote_event_initiatives`
- `parl_vote_events`
- `parl_vote_member_votes`
- `parties`
- `party_aliases`
- `person_identifiers`
- `persons`
- `raw_fetches`
- `roles`
- `source_records`
- `sources`
- `territories`
- `topic_evidence`
- `topic_positions`
- `topic_set_topics`
- `topic_sets`
- `topics`

Missing tables vs canonical:
- `causal_estimates`
- `document_fetches`
- `domains`
- `indicator_observation_records`
- `indicator_points`
- `indicator_series`
- `intervention_events`
- `interventions`
- `legal_fragment_responsibilities`
- `legal_fragment_responsibility_evidence`
- `legal_norm_fragments`
- `legal_norm_lineage_edges`
- `legal_norms`
- `liberty_delegated_enforcement_links`
- `liberty_delegated_enforcement_methodologies`
- `liberty_enforcement_methodologies`
- `liberty_enforcement_observations`
- `liberty_indirect_methodologies`
- `liberty_indirect_responsibility_edges`
- `liberty_irlc_methodologies`
- `liberty_proportionality_methodologies`
- `liberty_proportionality_reviews`
- `liberty_restriction_assessments`
- `liberty_right_categories`
- `lost_and_found`
- `money_contract_records`
- `money_subsidy_records`
- `parl_initiative_doc_extractions`
- `parl_initiative_documents`
- `person_name_aliases`
- `policy_axes`
- `policy_event_axis_scores`
- `policy_events`
- `policy_instruments`
- `run_fetches`
- `sanction_infraction_type_mappings`
- `sanction_infraction_types`
- `sanction_municipal_ordinance_fragments`
- `sanction_municipal_ordinances`
- `sanction_norm_catalog`
- `sanction_norm_fragment_links`
- `sanction_procedural_kpi_definitions`
- `sanction_procedural_metrics`
- `sanction_volume_observations`
- `sanction_volume_sources`
- `text_documents`
- `topic_evidence_reviews`

Files in this family:
- `etl/data/staging/politicos-es.fresh.db`

### `684d4480fba83bef`

- Files: `1`
- Tables: `24`
- Views: `0`
- Category mix: `platform_sqlite_variant`
- Sample: `etl/data/staging/politicos-es.recovered.db`
- Missing vs canonical: `51`
- Extra vs canonical: `0`

Tables:
- `admin_levels`
- `genders`
- `infoelectoral_archivos_extraccion`
- `infoelectoral_convocatoria_tipos`
- `infoelectoral_convocatorias`
- `infoelectoral_proceso_resultados`
- `infoelectoral_procesos`
- `ingestion_runs`
- `institutions`
- `lost_and_found`
- `mandates`
- `parl_initiatives`
- `parl_vote_event_initiatives`
- `parl_vote_events`
- `parl_vote_member_votes`
- `parties`
- `party_aliases`
- `person_identifiers`
- `persons`
- `raw_fetches`
- `roles`
- `source_records`
- `sources`
- `territories`

Missing tables vs canonical:
- `causal_estimates`
- `document_fetches`
- `domains`
- `indicator_observation_records`
- `indicator_points`
- `indicator_series`
- `intervention_events`
- `interventions`
- `legal_fragment_responsibilities`
- `legal_fragment_responsibility_evidence`
- `legal_norm_fragments`
- `legal_norm_lineage_edges`
- `legal_norms`
- `liberty_delegated_enforcement_links`
- `liberty_delegated_enforcement_methodologies`
- `liberty_enforcement_methodologies`
- `liberty_enforcement_observations`
- `liberty_indirect_methodologies`
- `liberty_indirect_responsibility_edges`
- `liberty_irlc_methodologies`
- `liberty_proportionality_methodologies`
- `liberty_proportionality_reviews`
- `liberty_restriction_assessments`
- `liberty_right_categories`
- `money_contract_records`
- `money_subsidy_records`
- `parl_initiative_doc_extractions`
- `parl_initiative_documents`
- `person_name_aliases`
- `policy_axes`
- `policy_event_axis_scores`
- `policy_events`
- `policy_instruments`
- `run_fetches`
- `sanction_infraction_type_mappings`
- `sanction_infraction_types`
- `sanction_municipal_ordinance_fragments`
- `sanction_municipal_ordinances`
- `sanction_norm_catalog`
- `sanction_norm_fragment_links`
- `sanction_procedural_kpi_definitions`
- `sanction_procedural_metrics`
- `sanction_volume_observations`
- `sanction_volume_sources`
- `text_documents`
- `topic_evidence`
- `topic_evidence_reviews`
- `topic_positions`
- `topic_set_topics`
- `topic_sets`
- `topics`

Files in this family:
- `etl/data/staging/politicos-es.recovered.db`

### `d2795c882362e315`

- Files: `1`
- Tables: `4`
- Views: `0`
- Category mix: `sprint_fixture_or_evidence_db`
- Sample: `docs/etl/sprints/AI-OPS-62/evidence/initdoc_actionable_contract.db`
- Missing vs canonical: `71`
- Extra vs canonical: `0`

Tables:
- `document_fetches`
- `parl_initiative_documents`
- `parl_initiatives`
- `text_documents`

Missing tables vs canonical:
- `admin_levels`
- `causal_estimates`
- `domains`
- `genders`
- `indicator_observation_records`
- `indicator_points`
- `indicator_series`
- `infoelectoral_archivos_extraccion`
- `infoelectoral_convocatoria_tipos`
- `infoelectoral_convocatorias`
- `infoelectoral_proceso_resultados`
- `infoelectoral_procesos`
- `ingestion_runs`
- `institutions`
- `intervention_events`
- `interventions`
- `legal_fragment_responsibilities`
- `legal_fragment_responsibility_evidence`
- `legal_norm_fragments`
- `legal_norm_lineage_edges`
- `legal_norms`
- `liberty_delegated_enforcement_links`
- `liberty_delegated_enforcement_methodologies`
- `liberty_enforcement_methodologies`
- `liberty_enforcement_observations`
- `liberty_indirect_methodologies`
- `liberty_indirect_responsibility_edges`
- `liberty_irlc_methodologies`
- `liberty_proportionality_methodologies`
- `liberty_proportionality_reviews`
- `liberty_restriction_assessments`
- `liberty_right_categories`
- `lost_and_found`
- `mandates`
- `money_contract_records`
- `money_subsidy_records`
- `parl_initiative_doc_extractions`
- `parl_vote_event_initiatives`
- `parl_vote_events`
- `parl_vote_member_votes`
- `parties`
- `party_aliases`
- `person_identifiers`
- `person_name_aliases`
- `persons`
- `policy_axes`
- `policy_event_axis_scores`
- `policy_events`
- `policy_instruments`
- `raw_fetches`
- `roles`
- `run_fetches`
- `sanction_infraction_type_mappings`
- `sanction_infraction_types`
- `sanction_municipal_ordinance_fragments`
- `sanction_municipal_ordinances`
- `sanction_norm_catalog`
- `sanction_norm_fragment_links`
- `sanction_procedural_kpi_definitions`
- `sanction_procedural_metrics`
- `sanction_volume_observations`
- `sanction_volume_sources`
- `source_records`
- `sources`
- `territories`
- `topic_evidence`
- `topic_evidence_reviews`
- `topic_positions`
- `topic_set_topics`
- `topic_sets`
- `topics`

Files in this family:
- `docs/etl/sprints/AI-OPS-62/evidence/initdoc_actionable_contract.db`

## Per-File Index

| file | size | schema_id | tables | views | category |
|---|---:|---|---:|---:|---|
| `docs/etl/sprints/AI-OPS-132/exports/liberty_representativity_20260223T203640Z.db` | 1.2 MB | `c4e3f6856e09a14b` | 71 | 0 | sprint_fixture_or_evidence_db |
| `docs/etl/sprints/AI-OPS-189/evidence/sanction_procedural_official_review_raw_packets_cycle_fixture_20260224T114814Z.db` | 1.2 MB | `71f4436a39ecd79c` | 74 | 0 | sprint_fixture_or_evidence_db |
| `docs/etl/sprints/AI-OPS-62/evidence/initdoc_actionable_contract.db` | 28.0 KB | `d2795c882362e315` | 4 | 0 | sprint_fixture_or_evidence_db |
| `etl/data/raw/manual/_tmp_galicia_click_profile/first_party_sets.db` | 48.0 KB | `4e9dac07ac526f31` | 7 | 0 | browser_profile_first_party_sets |
| `etl/data/raw/manual/galicia_deputado_profiles_20260212T141413Z/profile/Default/heavy_ad_intervention_opt_out.db` | 16.0 KB | `54f7dc72f40bfd5f` | 2 | 0 | browser_profile_heavy_ad_intervention_opt_out |
| `etl/data/raw/manual/galicia_deputado_profiles_20260212T141413Z/profile/first_party_sets.db` | 48.0 KB | `4e9dac07ac526f31` | 7 | 0 | browser_profile_first_party_sets |
| `etl/data/raw/manual/galicia_deputado_profiles_20260212T141929Z/profile/Default/heavy_ad_intervention_opt_out.db` | 16.0 KB | `54f7dc72f40bfd5f` | 2 | 0 | browser_profile_heavy_ad_intervention_opt_out |
| `etl/data/raw/manual/galicia_deputado_profiles_20260212T141929Z/profile/first_party_sets.db` | 48.0 KB | `4e9dac07ac526f31` | 7 | 0 | browser_profile_first_party_sets |
| `etl/data/raw/manual/galicia_deputados_20260212T132244Z_profile/Default/heavy_ad_intervention_opt_out.db` | 16.0 KB | `54f7dc72f40bfd5f` | 2 | 0 | browser_profile_heavy_ad_intervention_opt_out |
| `etl/data/raw/manual/galicia_deputados_20260212T132244Z_profile/first_party_sets.db` | 48.0 KB | `4e9dac07ac526f31` | 7 | 0 | browser_profile_first_party_sets |
| `etl/data/raw/manual/galicia_profile_alt_domain_20260212T141822Z_profile/Default/heavy_ad_intervention_opt_out.db` | 16.0 KB | `54f7dc72f40bfd5f` | 2 | 0 | browser_profile_heavy_ad_intervention_opt_out |
| `etl/data/raw/manual/galicia_profile_alt_domain_20260212T141822Z_profile/first_party_sets.db` | 48.0 KB | `4e9dac07ac526f31` | 7 | 0 | browser_profile_first_party_sets |
| `etl/data/raw/manual/galicia_profile_test_20260212T141513Z_profile/Default/heavy_ad_intervention_opt_out.db` | 16.0 KB | `54f7dc72f40bfd5f` | 2 | 0 | browser_profile_heavy_ad_intervention_opt_out |
| `etl/data/raw/manual/galicia_profile_test_20260212T141513Z_profile/first_party_sets.db` | 48.0 KB | `4e9dac07ac526f31` | 7 | 0 | browser_profile_first_party_sets |
| `etl/data/raw/manual/navarra_list_now_20260212T143859Z_profile/Default/heavy_ad_intervention_opt_out.db` | 16.0 KB | `54f7dc72f40bfd5f` | 2 | 0 | browser_profile_heavy_ad_intervention_opt_out |
| `etl/data/raw/manual/navarra_list_now_20260212T143859Z_profile/first_party_sets.db` | 48.0 KB | `4e9dac07ac526f31` | 7 | 0 | browser_profile_first_party_sets |
| `etl/data/raw/manual/navarra_list_refresh_20260212T143616Z_profile/Default/heavy_ad_intervention_opt_out.db` | 16.0 KB | `54f7dc72f40bfd5f` | 2 | 0 | browser_profile_heavy_ad_intervention_opt_out |
| `etl/data/raw/manual/navarra_list_refresh_20260212T143616Z_profile/first_party_sets.db` | 48.0 KB | `4e9dac07ac526f31` | 7 | 0 | browser_profile_first_party_sets |
| `etl/data/raw/manual/navarra_parlamentarios_20260212T131325Z_profile/Default/heavy_ad_intervention_opt_out.db` | 16.0 KB | `54f7dc72f40bfd5f` | 2 | 0 | browser_profile_heavy_ad_intervention_opt_out |
| `etl/data/raw/manual/navarra_parlamentarios_20260212T131325Z_profile/first_party_sets.db` | 48.0 KB | `4e9dac07ac526f31` | 7 | 0 | browser_profile_first_party_sets |
| `etl/data/raw/manual/navarra_parlamentarios_20260212T131640Z_profile/Default/heavy_ad_intervention_opt_out.db` | 16.0 KB | `54f7dc72f40bfd5f` | 2 | 0 | browser_profile_heavy_ad_intervention_opt_out |
| `etl/data/raw/manual/navarra_parlamentarios_20260212T131640Z_profile/first_party_sets.db` | 48.0 KB | `4e9dac07ac526f31` | 7 | 0 | browser_profile_first_party_sets |
| `etl/data/raw/manual/navarra_parlamentarios_20260212T131918Z_profile/Default/heavy_ad_intervention_opt_out.db` | 16.0 KB | `54f7dc72f40bfd5f` | 2 | 0 | browser_profile_heavy_ad_intervention_opt_out |
| `etl/data/raw/manual/navarra_parlamentarios_20260212T131918Z_profile/first_party_sets.db` | 48.0 KB | `4e9dac07ac526f31` | 7 | 0 | browser_profile_first_party_sets |
| `etl/data/raw/manual/navarra_persona_profiles_20260212T141107Z/profile/Default/heavy_ad_intervention_opt_out.db` | 16.0 KB | `54f7dc72f40bfd5f` | 2 | 0 | browser_profile_heavy_ad_intervention_opt_out |
| `etl/data/raw/manual/navarra_persona_profiles_20260212T141107Z/profile/first_party_sets.db` | 48.0 KB | `4e9dac07ac526f31` | 7 | 0 | browser_profile_first_party_sets |
| `etl/data/raw/manual/navarra_persona_profiles_20260212T141237Z/profile/Default/heavy_ad_intervention_opt_out.db` | 16.0 KB | `54f7dc72f40bfd5f` | 2 | 0 | browser_profile_heavy_ad_intervention_opt_out |
| `etl/data/raw/manual/navarra_persona_profiles_20260212T141237Z/profile/first_party_sets.db` | 48.0 KB | `4e9dac07ac526f31` | 7 | 0 | browser_profile_first_party_sets |
| `etl/data/raw/manual/navarra_persona_profiles_20260212T143152Z/profile/Default/heavy_ad_intervention_opt_out.db` | 16.0 KB | `54f7dc72f40bfd5f` | 2 | 0 | browser_profile_heavy_ad_intervention_opt_out |
| `etl/data/raw/manual/navarra_persona_profiles_20260212T143152Z/profile/first_party_sets.db` | 48.0 KB | `4e9dac07ac526f31` | 7 | 0 | browser_profile_first_party_sets |
| `etl/data/raw/manual/navarra_persona_profiles_20260212T143318Z/profile/Default/heavy_ad_intervention_opt_out.db` | 16.0 KB | `54f7dc72f40bfd5f` | 2 | 0 | browser_profile_heavy_ad_intervention_opt_out |
| `etl/data/raw/manual/navarra_persona_profiles_20260212T143318Z/profile/first_party_sets.db` | 48.0 KB | `4e9dac07ac526f31` | 7 | 0 | browser_profile_first_party_sets |
| `etl/data/raw/manual/navarra_persona_profiles_20260212T144021Z/profile/Default/heavy_ad_intervention_opt_out.db` | 16.0 KB | `54f7dc72f40bfd5f` | 2 | 0 | browser_profile_heavy_ad_intervention_opt_out |
| `etl/data/raw/manual/navarra_persona_profiles_20260212T144021Z/profile/first_party_sets.db` | 48.0 KB | `4e9dac07ac526f31` | 7 | 0 | browser_profile_first_party_sets |
| `etl/data/raw/manual/navarra_persona_profiles_20260212T144217Z/profile/Default/heavy_ad_intervention_opt_out.db` | 16.0 KB | `54f7dc72f40bfd5f` | 2 | 0 | browser_profile_heavy_ad_intervention_opt_out |
| `etl/data/raw/manual/navarra_persona_profiles_20260212T144217Z/profile/first_party_sets.db` | 48.0 KB | `4e9dac07ac526f31` | 7 | 0 | browser_profile_first_party_sets |
| `etl/data/raw/manual/navarra_persona_profiles_20260212T144356Z/profile/Default/heavy_ad_intervention_opt_out.db` | 16.0 KB | `54f7dc72f40bfd5f` | 2 | 0 | browser_profile_heavy_ad_intervention_opt_out |
| `etl/data/raw/manual/navarra_persona_profiles_20260212T144356Z/profile/first_party_sets.db` | 48.0 KB | `4e9dac07ac526f31` | 7 | 0 | browser_profile_first_party_sets |
| `etl/data/raw/manual/navarra_persona_profiles_slow_20260212T144448Z/profile/Default/heavy_ad_intervention_opt_out.db` | 16.0 KB | `54f7dc72f40bfd5f` | 2 | 0 | browser_profile_heavy_ad_intervention_opt_out |
| `etl/data/raw/manual/navarra_persona_profiles_slow_20260212T144448Z/profile/first_party_sets.db` | 48.0 KB | `4e9dac07ac526f31` | 7 | 0 | browser_profile_first_party_sets |
| `etl/data/raw/manual/navarra_persona_test2_20260212T144619Z_profile/Default/heavy_ad_intervention_opt_out.db` | 16.0 KB | `54f7dc72f40bfd5f` | 2 | 0 | browser_profile_heavy_ad_intervention_opt_out |
| `etl/data/raw/manual/navarra_persona_test2_20260212T144619Z_profile/first_party_sets.db` | 48.0 KB | `4e9dac07ac526f31` | 7 | 0 | browser_profile_first_party_sets |
| `etl/data/raw/manual/navarra_persona_test_20260212T142934Z_profile/Default/heavy_ad_intervention_opt_out.db` | 16.0 KB | `54f7dc72f40bfd5f` | 2 | 0 | browser_profile_heavy_ad_intervention_opt_out |
| `etl/data/raw/manual/navarra_persona_test_20260212T142934Z_profile/first_party_sets.db` | 48.0 KB | `4e9dac07ac526f31` | 7 | 0 | browser_profile_first_party_sets |
| `etl/data/raw/manual/senado_iniciativas_cookie_seed_20260218T083457Z_profile/Default/heavy_ad_intervention_opt_out.db` | 16.0 KB | `54f7dc72f40bfd5f` | 2 | 0 | browser_profile_heavy_ad_intervention_opt_out |
| `etl/data/raw/manual/senado_iniciativas_cookie_seed_20260218T083457Z_profile/first_party_sets.db` | 48.0 KB | `4e9dac07ac526f31` | 7 | 0 | browser_profile_first_party_sets |
| `etl/data/raw/manual/senado_iniciativas_cookie_seed_refresh_20260218T201301Z_profile/Default/heavy_ad_intervention_opt_out.db` | 16.0 KB | `54f7dc72f40bfd5f` | 2 | 0 | browser_profile_heavy_ad_intervention_opt_out |
| `etl/data/raw/manual/senado_iniciativas_cookie_seed_refresh_20260218T201301Z_profile/first_party_sets.db` | 48.0 KB | `4e9dac07ac526f31` | 7 | 0 | browser_profile_first_party_sets |
| `etl/data/raw/manual/senado_votaciones_ses/.headful-profile/Default/heavy_ad_intervention_opt_out.db` | 16.0 KB | `54f7dc72f40bfd5f` | 2 | 0 | browser_profile_heavy_ad_intervention_opt_out |
| `etl/data/raw/manual/senado_votaciones_ses/.headful-profile/first_party_sets.db` | 48.0 KB | `4e9dac07ac526f31` | 7 | 0 | browser_profile_first_party_sets |
| `etl/data/staging/_inspect.db` | 188.0 KB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/moncloa-aiops04-matrix-20260216.db` | 692.0 KB | `9f69e4335f9bd10f` | 41 | 0 | platform_sqlite_variant |
| `etl/data/staging/parl-quality-smoke.db` | 672.0 KB | `8479f1303c9a3bb8` | 21 | 0 | platform_sqlite_variant |
| `etl/data/staging/parl-quick.db` | 688.0 KB | `8479f1303c9a3bb8` | 21 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.ai_ops_135.db` | 1.3 MB | `c4e3f6856e09a14b` | 71 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.ai_ops_136.db` | 1.3 MB | `c4e3f6856e09a14b` | 71 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.ai_ops_137.db` | 1.3 MB | `c4e3f6856e09a14b` | 71 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.ai_ops_138.db` | 1.3 MB | `c4e3f6856e09a14b` | 71 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.aiops115.20260223T173448Z.db` | 912.0 KB | `9540053a905bf7c2` | 52 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.aiops115.justpipeline.20260223T173646Z.db` | 912.0 KB | `9540053a905bf7c2` | 52 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.aiops116.20260223T174656Z.db` | 1.0 MB | `acd27ce46df459ed` | 58 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.aiops117.db` | 1.1 MB | `eeeceea44a97a592` | 60 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.aiops118.db` | 1.1 MB | `8efa489f714a957b` | 63 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.aiops119.db` | 1.1 MB | `332a2a1eb23146bb` | 65 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.aiops120.db` | 1.2 MB | `642161a632336f6a` | 69 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.aiops121.db` | 1.3 MB | `c4e3f6856e09a14b` | 71 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.aiops122.db` | 1.2 MB | `c4e3f6856e09a14b` | 71 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.aiops123.db` | 1.2 MB | `c4e3f6856e09a14b` | 71 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.aiops129.db` | 1.2 MB | `c4e3f6856e09a14b` | 71 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.and-pv.db` | 504.0 KB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.aragoncheck.db` | 284.0 KB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.aragonfix.db` | 296.0 KB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.asamblea-madrid-20260212.db` | 1.9 MB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.asamblea-madrid-occup-uniq-20260212.db` | 188.0 KB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.asamblea-madrid-ocup-20260212.db` | 13.1 MB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.asamblea-madrid-ocup-uniq-20260212.db` | 13.8 MB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.asambleaex-20260212.db` | 288.0 KB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.cantabria-20260212.db` | 240.0 KB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.cat.db` | 484.0 KB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.ccyl-20260212.db` | 328.0 KB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.ceuta.db` | 232.0 KB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.ci-gate-local.db` | 620.0 KB | `4315a0f56dd07075` | 8 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.clean.db` | 88.0 KB | `4315a0f56dd07075` | 8 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.cortes-clm-20260212.db` | 252.0 KB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.cv.db` | 396.0 KB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.db` | 3.2 GB | `030bd477d6eda00e` | 75 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.e2e-20260212.db` | 620.0 KB | `4315a0f56dd07075` | 8 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.e2e-postfix-20260212.db` | 21.4 MB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.e2e10.db` | 130.8 MB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.e2e11.db` | 131.0 MB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.e2e12.db` | 131.1 MB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.e2e16.db` | 131.5 MB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.e2e17.db` | 131.7 MB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.e2e18.db` | 1.1 MB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.e2e19.db` | 302.7 MB | `25015d0743ebc215` | 29 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.e2e6.db` | 130.3 MB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.e2e7.db` | 130.5 MB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.e2e9.db` | 130.8 MB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.fresh.db` | 873.6 MB | `841b2d9125c2a0f1` | 28 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.fresh.recovered.20260214_1705.db` | 437.8 MB | `80a90ef042466929` | 29 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.fresh.work.20260214_1710.db` | 439.6 MB | `80a90ef042466929` | 29 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.full-20260212.db` | 114.2 MB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.html-guard-20260212.db` | 188.0 KB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.jgpa-20260212.db` | 236.0 KB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.just-e2e-20260212.db` | 620.0 KB | `4315a0f56dd07075` | 8 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.larioja-20260212.db` | 236.0 KB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.liberty-focus-ci-smoke.db` | 1.2 MB | `c4e3f6856e09a14b` | 71 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.municipal-strict-20260212.db` | 112.8 MB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.murcia-20260212.db` | 272.0 KB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.norm-samples.db` | 188.0 KB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.norm-test.db` | 188.0 KB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.parcan-20260212.db` | 324.0 KB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.parlamentib-20260212.db` | 284.0 KB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.recovered.db` | 1.4 GB | `684d4480fba83bef` | 24 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.refactor-e2e.db` | 114.4 MB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.refactor-e2e2.db` | 128.3 MB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.senado-fix-all.db` | 67.1 MB | `4315a0f56dd07075` | 8 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.senado-fix-v2.db` | 356.0 KB | `4315a0f56dd07075` | 8 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.senado-fix.db` | 352.0 KB | `4315a0f56dd07075` | 8 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.strict-check.db` | 88.0 KB | `4315a0f56dd07075` | 8 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.thresholds-smoke.db` | 128.3 MB | `dc489727e96af0a1` | 14 | 0 | platform_sqlite_variant |
| `etl/data/staging/politicos-es.tracker-check-20260212.db` | 620.0 KB | `4315a0f56dd07075` | 8 | 0 | platform_sqlite_variant |
| `politicos-es.db` | 0 B | `57284d24516fe4de` | 0 | 0 | empty_placeholder |
| `politicos-es.e2e19.db` | 0 B | `57284d24516fe4de` | 0 | 0 | empty_placeholder |
| `tmp/ai_ops_139.db` | 1.3 MB | `c4e3f6856e09a14b` | 71 | 0 | platform_sqlite_variant |
| `tmp/ai_ops_140.db` | 1.3 MB | `c4e3f6856e09a14b` | 71 | 0 | platform_sqlite_variant |
| `tmp/ai_ops_150_contract.db` | 1.3 MB | `fd43263fb254f6bb` | 72 | 0 | platform_sqlite_variant |
| `tmp/aiops130/liberty_map_20260223T202028Z.db` | 1.2 MB | `c4e3f6856e09a14b` | 71 | 0 | platform_sqlite_variant |
| `tmp/aiops131/liberty_heartbeat_20260223T202651Z.db` | 1.2 MB | `c4e3f6856e09a14b` | 71 | 0 | platform_sqlite_variant |
| `tmp/liberty_person_identity_apply_20260223T220708Z.db` | 1.3 MB | `fd43263fb254f6bb` | 72 | 0 | platform_sqlite_variant |
| `tmp/liberty_person_identity_official_evidence_20260223T224358Z.db` | 1.3 MB | `fd43263fb254f6bb` | 72 | 0 | platform_sqlite_variant |
| `tmp/liberty_person_identity_official_evidence_contract_20260223T224358Z.db` | 1.3 MB | `fd43263fb254f6bb` | 72 | 0 | platform_sqlite_variant |
| `tmp/liberty_person_identity_official_share_20260223T225159Z.db` | 1.3 MB | `fd43263fb254f6bb` | 72 | 0 | platform_sqlite_variant |
| `tmp/liberty_person_identity_official_share_contract_20260223T225159Z.db` | 1.3 MB | `fd43263fb254f6bb` | 72 | 0 | platform_sqlite_variant |
| `tmp/liberty_person_identity_provenance_20260223T221925Z.db` | 1.3 MB | `fd43263fb254f6bb` | 72 | 0 | platform_sqlite_variant |
| `tmp/liberty_person_identity_provenance_upgrade_20260223T222707Z.db` | 1.3 MB | `fd43263fb254f6bb` | 72 | 0 | platform_sqlite_variant |
| `tmp/liberty_person_identity_queue_20260223T215635Z.db` | 1.3 MB | `c4e3f6856e09a14b` | 71 | 0 | platform_sqlite_variant |
| `tmp/liberty_person_identity_source_guard_20260223T223309Z.db` | 1.3 MB | `fd43263fb254f6bb` | 72 | 0 | platform_sqlite_variant |
| `tmp/liberty_person_identity_source_guard_contract_20260223T223309Z.db` | 1.2 MB | `fd43263fb254f6bb` | 72 | 0 | platform_sqlite_variant |
| `tmp/liberty_person_identity_source_record_20260223T230526Z.db` | 1.3 MB | `fd43263fb254f6bb` | 72 | 0 | platform_sqlite_variant |
| `tmp/liberty_person_identity_source_record_contract_20260223T230526Z.db` | 1.3 MB | `fd43263fb254f6bb` | 72 | 0 | platform_sqlite_variant |
