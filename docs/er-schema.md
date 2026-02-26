# ER Schema (Declarative FK Graph)

Source: `etl/data/staging/politicos-es.db` (default DB used by export/publish scripts).

```mermaid
erDiagram
  sources ||--o{ indicator_observation_records : source_id
  source_records ||--o{ indicator_observation_records : source_record_pk
  indicator_series ||--o{ indicator_points : indicator_series_id
  interventions ||--o{ causal_estimates : intervention_id
  indicator_series ||--o{ causal_estimates : outcome_series_id

  sources ||--o{ infoelectoral_archivos_extraccion : source_id
  source_records ||--o{ infoelectoral_archivos_extraccion : source_record_pk
  infoelectoral_convocatoria_tipos ||--o{ infoelectoral_archivos_extraccion : tipo_convocatoria
  infoelectoral_convocatorias ||--o{ infoelectoral_archivos_extraccion : convocatoria_id

  sources ||--o{ infoelectoral_convocatoria_tipos : source_id
  source_records ||--o{ infoelectoral_convocatoria_tipos : source_record_pk
  sources ||--o{ infoelectoral_convocatorias : source_id
  source_records ||--o{ infoelectoral_convocatorias : source_record_pk
  infoelectoral_convocatoria_tipos ||--o{ infoelectoral_convocatorias : tipo_convocatoria

  sources ||--o{ infoelectoral_proceso_resultados : source_id
  source_records ||--o{ infoelectoral_proceso_resultados : source_record_pk
  infoelectoral_procesos ||--o{ infoelectoral_proceso_resultados : proceso_id

  sources ||--o{ infoelectoral_procesos : source_id
  source_records ||--o{ infoelectoral_procesos : source_record_pk

  sources ||--o{ ingestion_runs : source_id
  admin_levels ||--o{ institutions : admin_level_id
  territories ||--o{ institutions : territory_id

  policy_events ||--o{ intervention_events : policy_event_id
  interventions ||--o{ intervention_events : intervention_id
  admin_levels ||--o{ interventions : admin_level_id
  domains ||--o{ interventions : domain_id
  territories ||--o{ interventions : territory_id

  legal_norm_fragments ||--o{ legal_fragment_responsibilities : fragment_id
  institutions ||--o{ legal_fragment_responsibilities : institution_id
  persons ||--o{ legal_fragment_responsibilities : person_id
  legal_fragment_responsibilities ||--o{ legal_fragment_responsibility_evidence : responsibility_id

  legal_norms ||--o{ legal_norm_fragments : norm_id
  source_records ||--o{ legal_norm_fragments : source_record_pk
  legal_norms ||--o{ legal_norm_lineage_edges : norm_id
  legal_norms ||--o{ legal_norm_lineage_edges : related_norm_id
  sources ||--o{ legal_norms : source_id

  legal_norm_fragments ||--o{ legal_fragment_responsibility_evidence : fragment_id
  sources ||--o{ legal_fragment_responsibility_evidence : source_id
  source_records ||--o{ legal_fragment_responsibility_evidence : source_record_pk

  legal_norm_fragments ||--o{ liberty_delegated_enforcement_links : fragment_id
  liberty_delegated_enforcement_methodologies ||--o{ liberty_delegated_enforcement_links : method_version

  legal_norm_fragments ||--o{ liberty_enforcement_observations : fragment_id
  liberty_enforcement_methodologies ||--o{ liberty_enforcement_observations : method_version

  legal_norm_fragments ||--o{ liberty_indirect_responsibility_edges : fragment_id
  liberty_indirect_methodologies ||--o{ liberty_indirect_responsibility_edges : method_version

  legal_norm_fragments ||--o{ liberty_proportionality_reviews : fragment_id
  liberty_proportionality_methodologies ||--o{ liberty_proportionality_reviews : method_version

  legal_norm_fragments ||--o{ liberty_restriction_assessments : fragment_id
  liberty_irlc_methodologies ||--o{ liberty_restriction_assessments : method_version
  liberty_right_categories ||--o{ liberty_restriction_assessments : right_category_id

  admin_levels ||--o{ mandates : admin_level_id
  roles ||--o{ mandates : role_id
  sources ||--o{ mandates : source_id
  source_records ||--o{ mandates : source_record_pk
  parties ||--o{ mandates : party_id
  institutions ||--o{ mandates : institution_id
  territories ||--o{ mandates : territory_id
  persons ||--o{ mandates : person_id

  sources ||--o{ money_contract_records : source_id
  source_records ||--o{ money_contract_records : source_record_pk
  sources ||--o{ money_subsidy_records : source_id
  source_records ||--o{ money_subsidy_records : source_record_pk

  parl_initiatives ||--o{ parl_initiative_doc_extractions : sample_initiative_id
  sources ||--o{ parl_initiative_doc_extractions : source_id
  source_records ||--o{ parl_initiative_doc_extractions : source_record_pk

  parl_initiatives ||--o{ parl_initiative_documents : initiative_id
  source_records ||--o{ parl_initiative_documents : source_record_pk

  parl_initiatives ||--o{ parl_vote_event_initiatives : initiative_id
  parl_vote_events ||--o{ parl_vote_event_initiatives : vote_event_id
  sources ||--o{ parl_vote_events : source_id
  source_records ||--o{ parl_vote_events : source_record_pk

  persons ||--o{ parl_vote_member_votes : person_id
  parl_vote_events ||--o{ parl_vote_member_votes : vote_event_id

  sources ||--o{ parties : source_id
  parties ||--o{ party_aliases : party_id

  persons ||--o{ person_identifiers : person_id
  source_records ||--o{ person_name_aliases : source_record_pk
  sources ||--o{ person_name_aliases : source_id
  persons ||--o{ person_name_aliases : person_id

  territories ||--o{ persons : territory_id
  genders ||--o{ persons : gender_id

  domains ||--o{ policy_axes : domain_id
  policy_axes ||--o{ policy_event_axis_scores : policy_axis_id
  policy_events ||--o{ policy_event_axis_scores : policy_event_id
  admin_levels ||--o{ policy_events : admin_level_id
  domains ||--o{ policy_events : domain_id
  institutions ||--o{ policy_events : institution_id
  policy_instruments ||--o{ policy_events : policy_instrument_id
  sources ||--o{ policy_events : source_id

  ingestion_runs ||--o{ raw_fetches : run_id
  sources ||--o{ raw_fetches : source_id
  ingestion_runs ||--o{ run_fetches : run_id
  sources ||--o{ run_fetches : source_id

  legal_norm_fragments ||--o{ sanction_infraction_type_mappings : fragment_id
  legal_norms ||--o{ sanction_infraction_type_mappings : norm_id
  sanction_infraction_types ||--o{ sanction_infraction_type_mappings : infraction_type_id

  legal_norm_fragments ||--o{ sanction_municipal_ordinance_fragments : mapped_fragment_id
  legal_norms ||--o{ sanction_municipal_ordinance_fragments : mapped_norm_id
  sanction_municipal_ordinances ||--o{ sanction_municipal_ordinance_fragments : ordinance_id

  legal_norms ||--o{ sanction_norm_catalog : norm_id
  sanction_norm_catalog ||--o{ sanction_norm_fragment_links : norm_id
  legal_norm_fragments ||--o{ sanction_norm_fragment_links : fragment_id

  sanction_procedural_kpi_definitions ||--o{ sanction_procedural_metrics : kpi_id
  territories ||--o{ sanction_procedural_metrics : territory_id
  sanction_volume_sources ||--o{ sanction_procedural_metrics : sanction_source_id

  sanction_volume_sources ||--o{ sanction_volume_observations : sanction_source_id
  sanction_infraction_types ||--o{ sanction_volume_observations : infraction_type_id
  legal_norm_fragments ||--o{ sanction_volume_observations : fragment_id
  legal_norms ||--o{ sanction_volume_observations : norm_id

  sources ||--o{ source_records : source_id
  source_records ||--o{ source_records : source_record_pk
  territories ||--o{ territories : parent_territory_id

  sources ||--o{ text_documents : source_id
  source_records ||--o{ text_documents : source_record_pk

  admin_levels ||--o{ topic_evidence : admin_level_id
  topics ||--o{ topic_evidence : topic_id
  topic_sets ||--o{ topic_evidence : topic_set_id
  persons ||--o{ topic_evidence : person_id
  parl_initiatives ||--o{ topic_evidence : initiative_id
  parl_vote_events ||--o{ topic_evidence : vote_event_id
  institutions ||--o{ topic_evidence : institution_id
  mandates ||--o{ topic_evidence : mandate_id
  topic_evidence ||--o{ topic_evidence_reviews : evidence_id
  sources ||--o{ topic_evidence : source_id
  source_records ||--o{ topic_evidence : source_record_pk

  topics ||--o{ topic_positions : topic_id
  topic_sets ||--o{ topic_positions : topic_set_id
  persons ||--o{ topic_positions : person_id
  mandates ||--o{ topic_positions : mandate_id
  institutions ||--o{ topic_positions : institution_id
  admin_levels ||--o{ topic_positions : admin_level_id
  territories ||--o{ topic_positions : territory_id

  topics ||--o{ topic_set_topics : topic_id
  topic_sets ||--o{ topic_set_topics : topic_set_id

  topics ||--o{ topics : parent_topic_id
  admin_levels ||--o{ topic_sets : admin_level_id
  institutions ||--o{ topic_sets : institution_id
  territories ||--o{ topic_sets : territory_id
  domains ||--o{ topic_sets : domain_id
