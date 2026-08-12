import { readPublicJson } from "../../../static-snapshot.mjs";
import { withBasePath } from "../../../path-utils.mjs";

function formatInt(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return "0";
  }
  return Math.trunc(parsed).toLocaleString("es-ES");
}

function formatMoneyEur(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return "";
  }
  return parsed.toLocaleString("es-ES", {
    currency: "EUR",
    maximumFractionDigits: 0,
    style: "currency",
  });
}

function formatEvidenceUnitValue(value, unit) {
  const text = value ? String(value) : "";
  if (!text) {
    return "";
  }
  const unitText = unit ? String(unit) : "";
  if (unitText.toUpperCase() === "PORCENTAJE") {
    return text.endsWith("%") ? text : `${text}%`;
  }
  return [text, unitText].filter(Boolean).join(" ");
}

function formatExecutionEvidenceValue(row) {
  const amountLabel = formatMoneyEur(row?.amount_eur);
  if (amountLabel) {
    return amountLabel;
  }
  const outcomeValue = row?.outcome_latest_value_format || row?.outcome_value_format || row?.outcome_latest_value || row?.outcome_value || "";
  const outcomeYear = row?.outcome_latest_year || row?.outcome_year || "";
  const outcomeLabel = formatEvidenceUnitValue(outcomeValue, row?.indicator_unit);
  if (outcomeLabel) {
    return [outcomeYear, outcomeLabel].filter(Boolean).join(": ");
  }
  const indicatorPrevision = row?.indicator_prevision ? String(row.indicator_prevision) : "";
  const indicatorUnit = row?.indicator_unit ? String(row.indicator_unit) : "";
  return formatEvidenceUnitValue(indicatorPrevision, indicatorUnit);
}

function executionEvidenceSourceLabel(source) {
  const kind = source?.source_kind ? String(source.source_kind) : "";
  const format = source?.format ? String(source.format).toLowerCase() : "";
  if (kind === "official_procurement_open_data" || kind === "official_outcome_series_json") {
    return "JSON";
  }
  if (format.includes("json")) return "JSON";
  if (format.includes("xlsx")) return "XLSX";
  if (format.includes("xls")) return "XLS";
  return source?.format || "Fuente";
}

function matchLabel(value) {
  if (value === "unique_exact") return "actor enlazado";
  if (value === "disambiguated_by_andalucia_mandate") return "actor enlazado por mandato andaluz";
  if (value === "ambiguous_exact") return "nombre ambiguo";
  if (value === "not_matched") return "sin actor enlazado";
  return value || "sin dato";
}

function assessmentLabel(value) {
  if (value === "candidate_list_plus_actor_backbone") return "candidatura + actor";
  if (value === "candidate_list_only") return "solo candidatura";
  return value || "sin valorar";
}

function laneLabel(value) {
  if (value === "declared_measures_extracted") return "medidas declaradas";
  if (value === "official_impact_review_partially_reviewed") return "impacto parcial";
  if (value === "official_vote_review_queue") return "cola voto-impacto";
  if (value === "official_impact_review_queue") return "cola de impacto";
  if (value === "official_fragments_extracted") return "fragmentos oficiales";
  if (value === "official_records_collected") return "registros oficiales";
  if (value === "official_initiatives_collected") return "iniciativas oficiales";
  if (value === "official_voting_documents_collected") return "votos oficiales";
  if (value === "official_vote_counts_extracted") return "conteos de voto";
  if (value === "raw_sources_collected") return "fuentes brutas";
  if (value === "raw_sources_unverified") return "sin verificar";
  if (value === "missing_connector") return "falta scraper";
  if (value === "partial_source") return "fuente parcial";
  if (value === "queue_only") return "solo lead";
  return value || "pendiente";
}

function programStatusLabel(value) {
  if (value === "program_text_ready") return "programa con texto";
  if (value === "program_source_unverified") return "programa sin verificar";
  if (value === "missing_program_source") return "sin programa";
  return value || "sin dato";
}

function verificationLabel(value) {
  if (value === "verified_by_text") return "texto verificado";
  if (value === "fetched_unverified") return "texto sin verificar";
  if (value === "missing_text") return "sin texto";
  return value || "sin dato";
}

function officialityLabel(value) {
  if (value === "party_domain") return "dominio partido";
  if (value === "campaign_domain") return "dominio campaña";
  if (value === "party_affiliated_domain") return "dominio afín";
  if (value === "press_hosted_copy") return "copia en prensa";
  return value || "sin fuente";
}

function accountabilityStatusLabel(value) {
  if (value === "linked_accountability_evidence") return "historial enlazado";
  if (value === "missing_in_current_ledger") return "sin historial en ledger";
  if (value === "not_matchable") return "sin actor enlazable";
  return value || "sin historial";
}

function roleLabel(value) {
  const labels = {
    voted_for: "a favor",
    voted_against: "en contra",
    abstained: "abstención",
    unknown: "sin voto claro",
    appointed: "nombró",
    dismissed: "cesó",
    approved: "aprobó",
    proposed: "propuso",
    published: "publicó",
    contracted: "contrató",
    subsidized: "subvencionó",
    current_owner: "competente",
  };
  return labels[value] || value || "rol";
}

function topicLabel(value) {
  const labels = {
    sanidad: "Sanidad",
    vivienda: "Vivienda",
    educacion: "Educación",
    empleo: "Empleo",
    campo_agua: "Campo y agua",
    fiscalidad: "Fiscalidad",
    cultura_patrimonio: "Cultura y patrimonio",
    seguridad_libertades: "Seguridad y libertades",
    energia_clima: "Energía y clima",
    transparencia_corrupcion: "Transparencia y corrupción",
    sin_tema: "Sin tema",
  };
  return labels[value] || value || "sin bloque";
}

function actionLabel(value) {
  const labels = {
    aprobar: "aprobar",
    blindar: "blindar",
    crear: "crear",
    defender: "defender",
    derogar: "derogar",
    desarrollar: "desarrollar",
    dotar: "dotar",
    eliminar: "eliminar",
    establecer: "establecer",
    exigir: "exigir",
    facilitar: "facilitar",
    financiar: "financiar",
    garantizar: "garantizar",
    implantar: "implantar",
    impulsar: "impulsar",
    incrementar: "incrementar",
    mejorar: "mejorar",
    modernizar: "modernizar",
    potenciar: "potenciar",
    prohibir: "prohibir",
    promover: "promover",
    recuperar: "recuperar",
    reducir: "reducir",
    reforzar: "reforzar",
    regular: "regular",
  };
  return labels[value] || value || "medida";
}

function bojaActionLabel(value) {
  const labels = {
    modifica_norma: "modifica norma",
    deroga_norma: "deroga norma",
    aprueba_ley: "aprueba ley",
    aprueba_plan_estrategia: "aprueba plan",
    convoca_ayuda: "convoca ayuda",
    regula: "regula",
    estructura_organica: "estructura orgánica",
    official_normative_reference: "referencia oficial",
  };
  return labels[value] || value || "referencia oficial";
}

function impactReviewStatusLabel(value) {
  if (value === "needs_human_review") return "pendiente revisión";
  if (value === "reviewed_legal_change_only") return "cambio legal revisado";
  if (value === "legal_change_documented_outcome_pending") return "cambio legal sin outcome";
  if (value === "official_publisher_observed") return "publicador oficial observado";
  if (value === "unreviewed") return "sin revisar";
  if (value === "rule_triaged_needs_review") return "triaje automático";
  if (value === "actor_not_attributed") return "actor sin atribuir";
  if (value === "unknown") return "dirección desconocida";
  if (value === "needs_vote_actor_outcome_link") return "pendiente voto/resultado";
  return value || "sin revisar";
}

function responsibilityStatusLabel(value) {
  if (value === "traceable_program_votes_and_ledger") return "programa + voto + historial";
  if (value === "traceable_program_and_votes") return "programa + voto";
  if (value === "partial_traceability") return "traza parcial";
  if (value === "identity_only") return "solo identidad/lista";
  if (value === "traceable_candidate_votes_and_ledger") return "voto + historial";
  if (value === "traceable_candidate_votes") return "voto nominal";
  if (value === "traceable_candidate_identity") return "identidad oficial";
  if (value === "blocked_identity") return "identidad bloqueada";
  return value || "sin señal";
}

function responsibilityGapLabel(value) {
  if (value === "ready_for_issue_review") return "listo para revisar issue";
  if (value === "missing_verified_program") return "falta programa verificado";
  if (value === "missing_parliament_vote_record") return "falta voto parlamentario";
  if (value === "missing_reviewed_vote_signal") return "falta voto revisado";
  if (value === "missing_party_group_initiatives") return "falta iniciativa de grupo";
  if (value === "missing_accountability_ledger_link") return "falta historial enlazado";
  if (value === "missing_official_candidate_match") return "falta match candidatura";
  if (value === "missing_person_id_match") return "falta person_id";
  if (value === "missing_verified_party_program_measures") return "falta programa del partido";
  if (value === "missing_nominal_parliament_vote_record") return "falta voto nominal";
  return value || "hueco sin clasificar";
}

function issuePacketStatusLabel(value) {
  if (value === "program_vote_boja_reviewed") return "programa + voto + BOJA";
  if (value === "program_vote_reviewed") return "programa + voto";
  if (value === "program_boja_reviewed") return "programa + BOJA";
  if (value === "vote_boja_reviewed") return "voto + BOJA";
  if (value === "program_only") return "solo programa";
  if (value === "reviewed_vote_only") return "solo voto revisado";
  if (value === "reviewed_boja_only") return "solo BOJA";
  return value || "sin señal";
}

function issuePacketGapLabel(value) {
  if (value === "missing_program_measure") return "falta programa";
  if (value === "missing_reviewed_vote_signal") return "falta voto revisado";
  if (value === "missing_reviewed_boja_legal_change") return "falta BOJA revisado";
  if (value === "missing_citizen_direction") return "falta dirección ciudadana";
  if (value === "missing_responsible_actor") return "falta actor responsable";
  if (value === "missing_execution_responsible_actor") return "falta actor ejecución/BOJA";
  if (value === "missing_execution_owner") return "falta ejecutor";
  if (value === "missing_budget_execution") return "falta presupuesto/ejecución";
  if (value === "missing_outcomes") return "faltan resultados";
  return value || "hueco pendiente";
}

function issueReviewStatusLabel(value) {
  if (value === "reviewed_issue_direction_and_actor_partial") return "dirección + actor parcial";
  if (value === "reviewed_issue_vote_boja_direction_and_actor_partial") return "voto + BOJA + actor parcial";
  if (value === "reviewed_issue_vote_direction_and_actor_partial") return "voto + actor parcial";
  if (value === "reviewed_issue_direction_actor_and_execution_owner_partial") return "dirección + actor + ejecutor";
  if (value === "reviewed_issue_direction_actor_execution_owner_and_budget_allocation_partial") {
    return "dirección + actor + ejecutor + partida";
  }
  if (value === "reviewed_issue_direction_actor_execution_owner_budget_and_contract_partial") {
    return "dirección + actor + ejecutor + contrato";
  }
  return value ? String(value).replaceAll("_", " ") : "sin revisión";
}

function issueDirectionStatusLabel(value) {
  if (value === "legal_direction_documented_outcome_pending") return "dirección legal documentada";
  if (value === "direction_partially_reviewed_outcome_pending") return "dirección parcial";
  return value ? String(value).replaceAll("_", " ") : "sin dirección";
}

function issueActorStatusLabel(value) {
  if (value === "legislative_and_publisher_actor_observed_execution_owner_pending") return "actor legislativo/publicador";
  if (value === "legislative_publisher_and_execution_actor_observed_budget_pending") return "actor + ejecutor observado";
  if (value === "responsible_actor_partially_observed") return "actor parcial";
  return value ? String(value).replaceAll("_", " ") : "sin actor";
}

function issueExecutionOwnerStatusLabel(value) {
  if (value === "execution_owner_linked_budget_amount_pending") return "ejecutor observado";
  if (value === "execution_owner_partially_observed") return "ejecutor parcial";
  return value ? String(value).replaceAll("_", " ") : "sin ejecutor";
}

function issueExecutionStatusLabel(value) {
  if (value === "budget_execution_not_linked") return "ejecución no enlazada";
  if (value === "budget_allocation_linked_execution_pending") return "partida enlazada";
  if (value === "budget_allocation_and_contract_award_linked_outcome_pending") return "partida + contrato";
  if (value === "budget_execution_linked") return "ejecución enlazada";
  return value ? String(value).replaceAll("_", " ") : "sin ejecución";
}

function issueOutcomeStatusLabel(value) {
  if (value === "outcome_not_linked") return "outcome no enlazado";
  if (value === "outcome_linked") return "outcome enlazado";
  return value ? String(value).replaceAll("_", " ") : "sin outcome";
}

function issueLimitationLabel(value) {
  if (value === "budget_allocation_not_execution") return "partida no es ejecución";
  if (value === "contract_award_not_final_delivery") return "contrato no es entrega";
  if (value === "contract_award_not_outcome") return "contrato no es outcome";
  if (value === "aid_ceiling_not_executed_payment") return "techo de ayuda no es pago";
  if (value === "beneficiaries_not_linked") return "faltan beneficiarios";
  if (value === "reviewed_vote_not_boja_promulgation") return "voto no es BOJA";
  if (value === "decree_law_validation_vote_not_execution") return "voto no es ejecución";
  if (value === "legal_publication_and_validation_not_execution") return "BOJA/convalidación no es ejecución";
  if (value === "budget_execution_not_linked") return "falta presupuesto/ejecución";
  if (value === "implementation_owner_not_linked") return "falta unidad ejecutora";
  if (value === "service_or_cultural_outcomes_not_linked") return "faltan outcomes culturales";
  if (value === "service_or_environment_outcomes_not_linked") return "faltan outcomes servicio/medioambiente";
  if (value === "storm_damage_outcomes_not_linked") return "faltan outcomes por borrascas";
  if (value === "causal_impact_not_claimed") return "sin causalidad";
  if (value === "merit_blame_not_scored") return "sin mérito/culpa";
  return issuePacketGapLabel(value);
}

function executionEvidenceStatusLabel(value) {
  if (value === "head_200_verified") return "fuente verificada";
  if (value === "reviewed_budget_contract_indicator_rows_no_execution_or_outcome_claim") return "revisado sin outcome";
  if (value === "reviewed_budget_contract_indicator_baseline_rows_no_post_change_outcome_claim") return "baseline sin impacto";
  if (value === "reviewed_budget_indicator_rows_no_execution_or_outcome_claim") return "revisado sin outcome";
  if (value === "reviewed_contract_indicator_rows_no_outcome_claim") return "contrato + indicador";
  if (value === "reviewed_budget_contract_rows_execution_and_outcome_pending") return "presupuesto + contrato";
  if (value === "reviewed_contract_rows_outcome_pending") return "contrato revisado";
  if (value === "reviewed_budget_plan_rows_execution_pending") return "presupuesto revisado";
  if (value === "reviewed_observed_outcome_baseline_rows_post_change_pending") return "baseline observado";
  if (value === "reviewed_indicator_target_rows_outcome_pending") return "indicador revisado";
  if (value === "reviewed_execution_evidence_rows_no_execution_or_outcome_claim") return "revisado sin outcome";
  if (value === "reviewed_budget_plan_linked_execution_pending") return "plan, no ejecución";
  if (value === "reviewed_contract_award_linked_outcome_pending") return "contrato, no outcome";
  if (value === "reviewed_indicator_target_linked_observed_outcome_pending") return "objetivo, no outcome";
  if (value === "reviewed_observed_outcome_baseline_post_change_pending") return "baseline, no impacto";
  if (value === "official_budget_contract_indicator_review_no_merit_or_blame") return "sin mérito/culpa";
  if (value === "official_budget_indicator_review_no_merit_or_blame") return "sin mérito/culpa";
  if (value === "official_observed_outcome_baseline_no_merit_or_blame") return "sin mérito/culpa";
  if (value === "budget_plan") return "presupuesto";
  if (value === "contract_award") return "contrato";
  if (value === "grant_award") return "subvención";
  if (value === "treasury_payment_aggregate") return "pago agregado";
  if (value === "indicator_target") return "objetivo indicador";
  if (value === "observed_outcome_series") return "outcome observado";
  if (value === "official_series_baseline_waiting_for_post_change_data") return "baseline oficial, espera post-2026";
  if (value === "post_change_outcome_candidate_needs_causality_review") return "post-2026 candidato, revisar causalidad";
  if (value === "source_declared_but_rows_missing") return "fuente declarada sin filas";
  if (value === "official_candidate_rows_need_review") return "filas oficiales para revisar";
  if (value === "official_row_candidate_needs_review") return "candidata, no veredicto";
  if (value === "official_source_candidates_ready") return "fuentes oficiales candidatas";
  if (value === "get_200_verified") return "GET 200 verificado";
  if (value === "head_200_verified") return "HEAD 200 verificado";
  return value ? String(value).replaceAll("_", " ") : "pendiente";
}

function readinessClassificationLabel(value) {
  if (value === "responsibility_execution_and_baseline_reviewed_no_post_change_causality") {
    return "responsabilidad + ejecución + baseline";
  }
  if (value === "responsibility_execution_and_indicator_targets_reviewed_outcome_pending") {
    return "responsabilidad + objetivos";
  }
  if (value === "responsibility_and_execution_reviewed_outcome_pending") return "responsabilidad + ejecución";
  if (value === "responsibility_observed_execution_outcome_pending") return "responsabilidad observada";
  if (value === "legal_direction_and_actor_reviewed_execution_pending") return "dirección + actor";
  if (value === "program_with_primary_legal_signal_needs_review") return "programa + señal primaria";
  if (value === "program_with_execution_source_queue") return "programa + cola ejecución";
  if (value === "program_only_needs_primary_evidence") return "solo programa";
  if (value === "publishable_merit_blame_ready") return "listo para valorar";
  if (value === "insufficient_evidence") return "evidencia insuficiente";
  return value ? String(value).replaceAll("_", " ") : "sin clasificar";
}

function readinessBlockerLabel(value, fallback = "") {
  if (value === "program_measure_missing") return "falta programa";
  if (value === "reviewed_vote_missing") return "falta voto revisado";
  if (value === "reviewed_boja_missing") return "falta BOJA revisado";
  if (value === "citizen_direction_missing") return "falta dirección";
  if (value === "responsible_actor_missing") return "falta actor";
  if (value === "execution_source_plan_missing") return "falta plan ejecución";
  if (value === "budget_or_execution_review_missing") return "falta revisar dinero";
  if (value === "delivery_or_beneficiary_missing") return "falta entrega/beneficiario";
  if (value === "observed_outcome_missing") return "falta outcome";
  if (value === "post_change_outcome_missing") return "falta outcome posterior";
  if (value === "causal_link_missing") return "falta causalidad";
  if (value === "merit_blame_review_missing") return "falta revisión mérito/culpa";
  return fallback || (value ? String(value).replaceAll("_", " ") : "sin bloqueo");
}

function postChangeOutcomeStatusLabel(value) {
  if (value === "post_change_observed_needs_review") return "post-2026 listo para revisar";
  if (value === "waiting_for_post_change_period") return "esperando dato post-2026";
  if (value === "series_rows_missing") return "serie sin filas";
  if (value === "not_collected") return "no ingerido";
  return value ? String(value).replaceAll("_", " ") : "sin estado";
}

function legalEffectLabel(value, fallback) {
  const labels = {
    law_final_approval_vote_passed: "aprobación final de ley",
    law_final_approval_vote_rejected: "rechazo final de ley",
    bill_consideration_vote_passed: "toma en consideración aprobada",
    bill_consideration_vote_rejected: "toma en consideración rechazada",
    bill_amendment_vote_passed: "enmienda aprobada",
    bill_amendment_vote_rejected: "enmienda rechazada",
    legislative_bill_vote_passed: "voto legislativo aprobado",
    legislative_bill_vote_rejected: "voto legislativo rechazado",
    decree_law_validation_vote_passed: "decreto-ley convalidado",
    decree_law_validation_vote_not_passed_or_derogation_supported: "decreto-ley no convalidado",
    nonbinding_resolution_vote_passed: "resolución no vinculante aprobada",
    nonbinding_resolution_vote_rejected: "resolución no vinculante rechazada",
    motion_resolution_vote_passed: "moción aprobada",
    motion_resolution_vote_rejected: "moción rechazada",
    parliament_work_body_creation_vote_passed: "órgano de trabajo aprobado",
    parliament_work_body_creation_vote_rejected: "órgano de trabajo rechazado",
    unclassified_vote: "voto sin clasificar",
  };
  return fallback || labels[value] || String(value || "efecto pendiente").replaceAll("_", " ");
}

function legalEffectConfidenceLabel(value) {
  if (value === "high") return "confianza alta";
  if (value === "medium") return "confianza media";
  if (value === "unknown") return "sin confianza";
  return value || "sin confianza";
}

function topicSourceLabel(value) {
  if (value === "official_initiative") return "tema expediente";
  if (value === "vote_title_keyword_triage") return "tema por título";
  if (value === "no_topic_signal") return "sin tema";
  return value || "sin fuente";
}

function parliamentProponentKindLabel(value) {
  if (value === "executive_government") return "Consejo de Gobierno";
  if (value === "parliamentary_group") return "grupo parlamentario";
  if (value === "popular_initiative_promoters") return "iniciativa popular";
  if (value === "oversight_body") return "órgano de control";
  if (value === "parliament_officer") return "órgano parlamentario";
  return value || "otro proponente";
}

function voteMajorityLabel(value) {
  if (value === "si") return "mayoría sí";
  if (value === "no") return "mayoría no";
  if (value === "tie_or_no_signal") return "sin mayoría clara";
  return value || "sin dato";
}

function votePositionLabel(value) {
  if (value === "si") return "sí";
  if (value === "no") return "no";
  if (value === "abstenciones") return "abstención";
  if (value === "blancos") return "blanco";
  if (value === "absent") return "ausente";
  if (value === "ausente") return "ausente";
  if (value === "mixed") return "dividido";
  return value || "sin dato";
}

function reviewedVoteEffectOutcomeLabel(value) {
  if (value === "approved_by_majority_yes") return "aprobada por mayoría sí";
  if (value === "decree_law_validated_by_majority_yes") return "decreto-ley convalidado";
  if (value === "rejected_by_majority_no") return "rechazada por mayoría no";
  return value ? String(value).replaceAll("_", " ") : "resultado revisado";
}

function accountabilityClaimKindLabel(value) {
  if (value === "party_legislative_vote_observation") return "partido · voto";
  if (value === "candidate_legislative_vote_observation") return "candidato · voto";
  return value ? String(value).replaceAll("_", " ") : "claim";
}

function accountabilityClaimRelationLabel(value) {
  if (value === "with_reviewed_outcome") return "con resultado";
  if (value === "against_reviewed_outcome") return "contra resultado";
  if (value === "abstained_on_reviewed_outcome") return "abstención";
  if (value === "blank_vote_observed") return "voto blanco";
  if (value === "observed_other") return "otro";
  return value ? String(value).replaceAll("_", " ") : "sin relación";
}

function accountabilityClaimStatusLabel(value) {
  if (value === "published_observed_responsibility_no_merit_or_blame") return "responsabilidad observada";
  if (value === "no_public_claims") return "sin claims";
  return value ? String(value).replaceAll("_", " ") : "sin estado";
}

function personHref(personId) {
  return personId ? withBasePath(`/people/?person_id=${personId}`) : "";
}

function sourceLink(href, label) {
  if (!href) return null;
  return (
    <a className="andalucia-election-source-link" href={href} target="_blank" rel="noreferrer">
      {label}
    </a>
  );
}

function ProgramSourcePills({ sources }) {
  if (!Array.isArray(sources) || !sources.length) {
    return <p className="andalucia-election-program-source-list__empty">Sin programa localizado en este corte.</p>;
  }
  return (
    <ul className="andalucia-election-program-source-list">
      {sources.map((source) => (
        <li className="andalucia-election-program-source-list__item" key={source.source_id}>
          <a className="andalucia-election-program-source-list__link" href={source.url} target="_blank" rel="noreferrer">
            {source.title || "Programa"}
          </a>
          <span className="andalucia-election-program-source-list__meta">
            {verificationLabel(source.verification_status)} · {officialityLabel(source.officiality)}
          </span>
        </li>
      ))}
    </ul>
  );
}

function ProgramMeasureMiniList({ measures }) {
  if (!Array.isArray(measures) || !measures.length) {
    return null;
  }
  return (
    <ul className="andalucia-election-program-measure-mini-list">
      {measures.slice(0, 4).map((measure) => (
        <li className="andalucia-election-program-measure-mini-list__item" key={measure.measure_id}>
          <span className="andalucia-election-program-measure-mini-list__topic">
            {topicLabel(measure.topic_id)}
          </span>
          <span className="andalucia-election-program-measure-mini-list__excerpt">
            {measure.evidence_excerpt}
          </span>
        </li>
      ))}
    </ul>
  );
}

function AccountabilityEvidenceSummary({ evidence }) {
  const row = evidence || {};
  if (row.status !== "linked_accountability_evidence") {
    return (
      <div className="andalucia-election-evidence-summary andalucia-election-evidence-summary--empty">
        <strong className="andalucia-election-evidence-summary__title">Historial scrapeado</strong>
        <p className="andalucia-election-evidence-summary__copy">
          {accountabilityStatusLabel(row.status)}. Falta enlazar este actor electoral a entradas del ledger publicado.
        </p>
      </div>
    );
  }
  const roles = Array.isArray(row.role_counts) ? row.role_counts : [];
  const samples = Array.isArray(row.evidence_samples) ? row.evidence_samples : [];
  return (
    <div className="andalucia-election-evidence-summary">
      <div className="andalucia-election-evidence-summary__head">
        <strong className="andalucia-election-evidence-summary__title">Historial scrapeado</strong>
        <span className="andalucia-election-evidence-summary__status">
          {accountabilityStatusLabel(row.status)}
        </span>
      </div>
      <dl className="andalucia-election-evidence-summary__facts">
        <div className="andalucia-election-evidence-summary__fact">
          <dt>Entradas</dt>
          <dd>{formatInt(row.entries_total)}</dd>
        </div>
        <div className="andalucia-election-evidence-summary__fact">
          <dt>Bloques</dt>
          <dd>{formatInt(row.issues_total)}</dd>
        </div>
        <div className="andalucia-election-evidence-summary__fact">
          <dt>Confianza</dt>
          <dd>{row.confidence_level || "sin dato"}</dd>
        </div>
      </dl>
      {roles.length ? (
        <div className="andalucia-election-evidence-summary__roles">
          {roles.slice(0, 4).map((role) => (
            <span className="andalucia-election-evidence-summary__role" key={`${row.actor_key}-${role.key}`}>
              {roleLabel(role.key)}: {formatInt(role.count)}
            </span>
          ))}
        </div>
      ) : null}
      {samples.length ? (
        <ul className="andalucia-election-evidence-sample-list">
          {samples.slice(0, 2).map((sample) => (
            <li className="andalucia-election-evidence-sample-list__item" key={sample.entry_id}>
              <span className="andalucia-election-evidence-sample-list__date">{sample.event_date || "sin fecha"}</span>
              <span className="andalucia-election-evidence-sample-list__quote">
                {roleLabel(sample.accountability_role)} · {sample.evidence_quote || sample.title || sample.issue_label}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
      {row.dossier_route ? (
        <a className="andalucia-election-source-link" href={withBasePath(row.dossier_route)}>
          Dossier
        </a>
      ) : null}
      {row.match_note ? <p className="andalucia-election-evidence-summary__note">{row.match_note}</p> : null}
    </div>
  );
}

function CandidateMandates({ candidate }) {
  const mandates = Array.isArray(candidate.mandates_sample) ? candidate.mandates_sample : [];
  if (!mandates.length) {
    return <p className="andalucia-election-candidate-card__gap">Sin mandatos enlazados en este corte.</p>;
  }
  return (
    <ul className="andalucia-election-mandate-list">
      {mandates.map((mandate, index) => (
        <li className="andalucia-election-mandate-list__item" key={`${candidate.focus_id}-${index}`}>
          <span className="andalucia-election-mandate-list__role">{mandate.role_title || "Cargo"}</span>
          <span className="andalucia-election-mandate-list__institution">{mandate.institution_name || "Institución"}</span>
          <span className="andalucia-election-mandate-list__source">{mandate.source_id || "fuente"}</span>
        </li>
      ))}
    </ul>
  );
}

function CandidateParliamentVoteSummary({ summary }) {
  const row = summary || {};
  const samples = Array.isArray(row.sample_votes) ? row.sample_votes : [];
  if (!Number(row.vote_events_total || 0)) {
    return null;
  }
  return (
    <div className="andalucia-election-candidate-vote-summary">
      <div className="andalucia-election-candidate-vote-summary__head">
        <strong className="andalucia-election-candidate-vote-summary__title">Voto nominal Parlamento</strong>
        <span className="andalucia-election-candidate-vote-summary__status">
          sin interpretar
        </span>
      </div>
      <dl className="andalucia-election-candidate-vote-summary__facts">
        <div className="andalucia-election-candidate-vote-summary__fact">
          <dt>Sí</dt>
          <dd>{formatInt(row.si)}</dd>
        </div>
        <div className="andalucia-election-candidate-vote-summary__fact">
          <dt>No</dt>
          <dd>{formatInt(row.no)}</dd>
        </div>
        <div className="andalucia-election-candidate-vote-summary__fact">
          <dt>Abs.</dt>
          <dd>{formatInt(row.abstenciones)}</dd>
        </div>
        <div className="andalucia-election-candidate-vote-summary__fact">
          <dt>Aus.</dt>
          <dd>{formatInt(row.ausente)}</dd>
        </div>
      </dl>
      <ul className="andalucia-election-candidate-vote-sample-list">
        {samples.slice(0, 3).map((sample) => (
          <li className="andalucia-election-candidate-vote-sample-list__item" key={sample.vote_member_id}>
            <span className="andalucia-election-candidate-vote-sample-list__position">
              {votePositionLabel(sample.vote_position)}
            </span>
            <span className="andalucia-election-candidate-vote-sample-list__text">
              {sample.numexp || sample.title || "votación sin expediente"}
            </span>
            {sourceLink(sample.source_url, "PDF")}
          </li>
        ))}
      </ul>
      <p className="andalucia-election-candidate-vote-summary__note">
        Conteo nominal oficial. Falta revisar efecto legal e impacto antes de valorar mérito o responsabilidad.
      </p>
    </div>
  );
}

function ReviewedLegislativeSignalSummary({ summary, sampleLimit = 3 }) {
  const row = summary || {};
  const reviewedTotal = Number(row.reviewed_vote_events_total || 0);
  const samples = Array.isArray(row.sample_items)
    ? row.sample_items
    : Array.isArray(row.sample_votes)
      ? row.sample_votes
      : [];
  const abstainedOrOtherTotal =
    Number(row.abstained_approved_effect_total || 0) +
    Number(row.abstained_rejected_effect_total || 0) +
    Number(row.observed_other || 0);
  if (!reviewedTotal) {
    return null;
  }
  return (
    <div className="andalucia-election-reviewed-legislative-summary">
      <div className="andalucia-election-reviewed-legislative-summary__head">
        <strong className="andalucia-election-reviewed-legislative-summary__title">
          Señales legislativas revisadas
        </strong>
        <span className="andalucia-election-reviewed-legislative-summary__status">
          {formatInt(reviewedTotal)} votos
        </span>
      </div>
      <dl className="andalucia-election-reviewed-legislative-summary__facts">
        <div className="andalucia-election-reviewed-legislative-summary__fact">
          <dt>Apoya aprobado</dt>
          <dd>{formatInt(row.supported_approved_effect_total)}</dd>
        </div>
        <div className="andalucia-election-reviewed-legislative-summary__fact">
          <dt>Frena aprobado</dt>
          <dd>{formatInt(row.opposed_approved_effect_total)}</dd>
        </div>
        <div className="andalucia-election-reviewed-legislative-summary__fact">
          <dt>Apoya rechazo</dt>
          <dd>{formatInt(row.supported_rejected_effect_total)}</dd>
        </div>
        <div className="andalucia-election-reviewed-legislative-summary__fact">
          <dt>Frena rechazo</dt>
          <dd>{formatInt(row.opposed_rejected_effect_total)}</dd>
        </div>
        <div className="andalucia-election-reviewed-legislative-summary__fact">
          <dt>Abst./otro</dt>
          <dd>{formatInt(abstainedOrOtherTotal)}</dd>
        </div>
      </dl>
      <ul className="andalucia-election-reviewed-legislative-sample-list">
        {samples.slice(0, sampleLimit).map((sample, index) => {
          const position = sample.party_position || sample.vote_position || "";
          const sampleKey = sample.vote_member_id || sample.review_item_id || `${sample.vote_event_id}-${index}`;
          return (
            <li className="andalucia-election-reviewed-legislative-sample-list__item" key={sampleKey}>
              <span className="andalucia-election-reviewed-legislative-sample-list__position">
                {votePositionLabel(position)}
              </span>
              <span className="andalucia-election-reviewed-legislative-sample-list__text">
                {sample.reviewed_issue_label || sample.numexp || sample.title || "votación revisada"}
              </span>
              <span className="andalucia-election-reviewed-legislative-sample-list__outcome">
                {reviewedVoteEffectOutcomeLabel(sample.effect_outcome)}
              </span>
              {sourceLink(sample.source_url, "PDF")}
            </li>
          );
        })}
      </ul>
      <p className="andalucia-election-reviewed-legislative-summary__note">
        Resultado oficial revisado. No convierte voto en mérito, culpa ni impacto ciudadano sin revisar ejecución y
        resultados.
      </p>
    </div>
  );
}

function FocusCandidateCard({ candidate }) {
  const href = personHref(candidate.person_id);
  return (
    <article className="andalucia-election-candidate-card">
      <div className="andalucia-election-candidate-card__head">
        <p className="andalucia-election-candidate-card__party">{candidate.party_acronym}</p>
        <h3 className="andalucia-election-candidate-card__name">
          {candidate.official_person_name || candidate.person_name}
        </h3>
      </div>
      <dl className="andalucia-election-candidate-card__facts">
        <div className="andalucia-election-candidate-card__fact">
          <dt>Provincia</dt>
          <dd>{candidate.province || "sin dato"}</dd>
        </div>
        <div className="andalucia-election-candidate-card__fact">
          <dt>Lista</dt>
          <dd>{candidate.list_position ? `#${candidate.list_position}` : "sin dato"}</dd>
        </div>
        <div className="andalucia-election-candidate-card__fact">
          <dt>Actor</dt>
          <dd>{matchLabel(candidate.person_match_status)}</dd>
        </div>
        <div className="andalucia-election-candidate-card__fact">
          <dt>Mandatos</dt>
          <dd>{formatInt(candidate.mandate_count || 0)}</dd>
        </div>
      </dl>
      <div className="andalucia-election-candidate-card__status">
        <strong className="andalucia-election-candidate-card__status-title">Mérito/culpa</strong>
        <p className="andalucia-election-candidate-card__status-copy">
          No publicado todavía. Identidad oficial sí; valoración exige evidencia por issue, acto, fecha y fuente primaria.
        </p>
      </div>
      <div className="andalucia-election-candidate-card__program">
        <strong className="andalucia-election-candidate-card__program-title">Programa</strong>
        <span className="andalucia-election-candidate-card__program-status">
          {programStatusLabel(candidate.program_source_status)} · {formatInt(candidate.program_measures_total)} medidas
        </span>
        <ProgramSourcePills sources={candidate.program_sources} />
        <ProgramMeasureMiniList measures={candidate.program_measure_samples} />
      </div>
      <AccountabilityEvidenceSummary evidence={candidate.accountability_evidence} />
      <CandidateParliamentVoteSummary summary={candidate.parliament_vote_summary} />
      <ReviewedLegislativeSignalSummary summary={candidate.reviewed_legislative_impact_summary} sampleLimit={3} />
      <CandidateMandates candidate={candidate} />
      <div className="andalucia-election-candidate-card__links">
        {href ? (
          <a className="andalucia-election-source-link" href={href}>
            Perfil
          </a>
        ) : null}
        {sourceLink(candidate.source_url, "Candidatura oficial")}
      </div>
    </article>
  );
}

function PartyRow({ party }) {
  return (
    <details className="andalucia-election-party-row">
      <summary className="andalucia-election-party-row__summary">
        <span className="andalucia-election-party-row__name">{party.party_acronym}</span>
        <span className="andalucia-election-party-row__metric">{formatInt(party.candidate_lists_total)} listas</span>
        <span className="andalucia-election-party-row__metric">{formatInt(party.titular_candidates_total)} titulares</span>
        <span className="andalucia-election-party-row__metric">{formatInt(party.matched_candidates_total)} actores</span>
        <span className="andalucia-election-party-row__metric">
          {formatInt(party.program_verified_sources_total)} programas
        </span>
        <span className="andalucia-election-party-row__metric">
          {formatInt(party.program_measures_total)} medidas
        </span>
        <span className="andalucia-election-party-row__metric">
          {formatInt((party.reviewed_legislative_impact_summary || {}).reviewed_vote_events_total)} señales
        </span>
        <span className="andalucia-election-party-row__status">{assessmentLabel(party.assessment_status)}</span>
      </summary>
      <div className="andalucia-election-party-row__body">
        <p className="andalucia-election-party-row__variant">
          {party.list_name_variants.join(" / ")}
        </p>
        <div className="andalucia-election-party-row__program">
          <span className="andalucia-election-party-row__program-status">
            {programStatusLabel(party.program_source_status)}
          </span>
          <ProgramSourcePills sources={party.program_sources} />
          <ProgramMeasureMiniList measures={party.program_measure_samples} />
        </div>
        <AccountabilityEvidenceSummary evidence={party.accountability_evidence} />
        <ReviewedLegislativeSignalSummary summary={party.reviewed_legislative_impact_summary} sampleLimit={3} />
        <div className="andalucia-election-lead-list">
          {party.lead_candidates.map((lead) => (
            <div className="andalucia-election-lead-list__item" key={`${party.party_key}-${lead.province}`}>
              <span className="andalucia-election-lead-list__province">{lead.province}</span>
              <span className="andalucia-election-lead-list__name">{lead.person_name}</span>
              <span className="andalucia-election-lead-list__status">{matchLabel(lead.person_match_status)}</span>
            </div>
          ))}
        </div>
      </div>
    </details>
  );
}

function ReviewedLegislativePartyCard({ summary }) {
  return (
    <article className="andalucia-election-reviewed-legislative-party-card">
      <div className="andalucia-election-reviewed-legislative-party-card__head">
        <p className="andalucia-election-reviewed-legislative-party-card__party">
          {summary.party_acronym || summary.party_key}
        </p>
        <span className="andalucia-election-reviewed-legislative-party-card__claim">
          sin mérito/culpa
        </span>
      </div>
      <ReviewedLegislativeSignalSummary summary={summary} sampleLimit={2} />
    </article>
  );
}

function ReviewedLegislativeCandidateComparison({ summaries }) {
  const rows = Array.isArray(summaries)
    ? summaries
      .filter((row) => Number(row.reviewed_vote_events_total || 0) > 0)
      .slice(0, 12)
    : [];
  if (!rows.length) {
    return null;
  }
  return (
    <div className="andalucia-election-reviewed-candidate-comparison">
      <div className="andalucia-election-reviewed-candidate-comparison__head">
        <strong className="andalucia-election-reviewed-candidate-comparison__title">
          Candidatos con señal nominal revisada
        </strong>
        <span className="andalucia-election-reviewed-candidate-comparison__status">
          {formatInt(rows.length)} visibles
        </span>
      </div>
      <div className="andalucia-election-reviewed-candidate-comparison__table-wrap">
        <table className="andalucia-election-reviewed-candidate-table">
          <thead className="andalucia-election-reviewed-candidate-table__head">
            <tr className="andalucia-election-reviewed-candidate-table__row">
              <th className="andalucia-election-reviewed-candidate-table__header" scope="col">Candidato</th>
              <th className="andalucia-election-reviewed-candidate-table__header" scope="col">Partido</th>
              <th className="andalucia-election-reviewed-candidate-table__header" scope="col">Votos</th>
              <th className="andalucia-election-reviewed-candidate-table__header" scope="col">Con resultado</th>
              <th className="andalucia-election-reviewed-candidate-table__header" scope="col">Contra</th>
              <th className="andalucia-election-reviewed-candidate-table__header" scope="col">Abs.</th>
              <th className="andalucia-election-reviewed-candidate-table__header" scope="col">Muestra</th>
            </tr>
          </thead>
          <tbody className="andalucia-election-reviewed-candidate-table__body">
            {rows.map((row) => {
              const sample = Array.isArray(row.sample_votes) ? row.sample_votes[0] || {} : {};
              const href = personHref(row.person_id);
              return (
                <tr className="andalucia-election-reviewed-candidate-table__row" key={row.candidate_id}>
                  <td className="andalucia-election-reviewed-candidate-table__cell andalucia-election-reviewed-candidate-table__cell--candidate">
                    {href ? (
                      <a className="andalucia-election-reviewed-candidate-table__candidate-link" href={href}>
                        {row.person_name}
                      </a>
                    ) : (
                      <span className="andalucia-election-reviewed-candidate-table__candidate-name">
                        {row.person_name}
                      </span>
                    )}
                    <span className="andalucia-election-reviewed-candidate-table__candidate-meta">
                      {row.province || "sin provincia"} · #{row.list_position || "?"}
                    </span>
                  </td>
                  <td className="andalucia-election-reviewed-candidate-table__cell">
                    <span className="andalucia-election-reviewed-candidate-table__party">
                      {row.party_acronym || row.party_key}
                    </span>
                  </td>
                  <td className="andalucia-election-reviewed-candidate-table__cell">
                    {formatInt(row.reviewed_vote_events_total)}
                  </td>
                  <td className="andalucia-election-reviewed-candidate-table__cell">
                    {formatInt(row.voted_with_reviewed_outcome_total)}
                  </td>
                  <td className="andalucia-election-reviewed-candidate-table__cell">
                    {formatInt(row.voted_against_reviewed_outcome_total)}
                  </td>
                  <td className="andalucia-election-reviewed-candidate-table__cell">
                    {formatInt(row.abstained_on_reviewed_outcome_total)}
                  </td>
                  <td className="andalucia-election-reviewed-candidate-table__cell andalucia-election-reviewed-candidate-table__cell--sample">
                    <span className="andalucia-election-reviewed-candidate-table__sample-position">
                      {votePositionLabel(sample.vote_position)}
                    </span>
                    <span className="andalucia-election-reviewed-candidate-table__sample-text">
                      {sample.reviewed_issue_label || sample.numexp || "voto revisado"}
                    </span>
                    {sourceLink(sample.source_url, "PDF")}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="andalucia-election-reviewed-candidate-comparison__note">
        Tabla nominal sobre resultados oficiales revisados. No ordena por mérito, culpa ni impacto ciudadano.
      </p>
    </div>
  );
}

function ResponsibilityPartyMatrix({ profiles }) {
  const rows = Array.isArray(profiles) ? profiles.slice(0, 10) : [];
  if (!rows.length) {
    return null;
  }
  return (
    <div className="andalucia-election-responsibility-matrix">
      <div className="andalucia-election-responsibility-matrix__head">
        <strong className="andalucia-election-responsibility-matrix__title">Partidos: trazabilidad disponible</strong>
        <span className="andalucia-election-responsibility-matrix__status">
          {formatInt(rows.length)} visibles
        </span>
      </div>
      <div className="andalucia-election-responsibility-matrix__table-wrap">
        <table className="andalucia-election-responsibility-table">
          <thead className="andalucia-election-responsibility-table__head">
            <tr className="andalucia-election-responsibility-table__row">
              <th className="andalucia-election-responsibility-table__header" scope="col">Partido</th>
              <th className="andalucia-election-responsibility-table__header" scope="col">Estado</th>
              <th className="andalucia-election-responsibility-table__header" scope="col">Programa</th>
              <th className="andalucia-election-responsibility-table__header" scope="col">Parlamento</th>
              <th className="andalucia-election-responsibility-table__header" scope="col">Revisado</th>
              <th className="andalucia-election-responsibility-table__header" scope="col">Historial</th>
              <th className="andalucia-election-responsibility-table__header" scope="col">Hueco</th>
            </tr>
          </thead>
          <tbody className="andalucia-election-responsibility-table__body">
            {rows.map((row) => (
              <tr className="andalucia-election-responsibility-table__row" key={row.party_key}>
                <td className="andalucia-election-responsibility-table__cell">
                  <span className="andalucia-election-responsibility-table__party">
                    {row.party_acronym || row.party_key}
                  </span>
                </td>
                <td className="andalucia-election-responsibility-table__cell">
                  {responsibilityStatusLabel(row.status)}
                </td>
                <td className="andalucia-election-responsibility-table__cell">
                  {formatInt(row.declared_program_measures_total)} medidas
                </td>
                <td className="andalucia-election-responsibility-table__cell">
                  {formatInt(row.parliament_vote_events_total)} votos · {formatInt(row.official_group_initiatives_total)} iniciativas
                </td>
                <td className="andalucia-election-responsibility-table__cell">
                  {formatInt(row.reviewed_vote_events_total)} votos · {formatInt(row.candidate_reviewed_vote_profiles_total)} candidatos
                </td>
                <td className="andalucia-election-responsibility-table__cell">
                  {accountabilityStatusLabel(row.accountability_evidence_status)} · {formatInt(row.accountability_entries_total)}
                </td>
                <td className="andalucia-election-responsibility-table__cell">
                  {responsibilityGapLabel(row.primary_gap)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="andalucia-election-responsibility-matrix__note">
        Matriz de evidencia, no ranking moral. Cuenta fuentes primarias listas para revisar responsabilidad por issue.
      </p>
    </div>
  );
}

function ResponsibilityCandidateMatrix({ profiles }) {
  const rows = Array.isArray(profiles) ? profiles : [];
  if (!rows.length) {
    return null;
  }
  return (
    <div className="andalucia-election-responsibility-matrix">
      <div className="andalucia-election-responsibility-matrix__head">
        <strong className="andalucia-election-responsibility-matrix__title">Candidatos foco: atribución posible</strong>
        <span className="andalucia-election-responsibility-matrix__status">
          {formatInt(rows.length)} perfiles
        </span>
      </div>
      <div className="andalucia-election-responsibility-matrix__table-wrap">
        <table className="andalucia-election-responsibility-table">
          <thead className="andalucia-election-responsibility-table__head">
            <tr className="andalucia-election-responsibility-table__row">
              <th className="andalucia-election-responsibility-table__header" scope="col">Candidato</th>
              <th className="andalucia-election-responsibility-table__header" scope="col">Partido</th>
              <th className="andalucia-election-responsibility-table__header" scope="col">Estado</th>
              <th className="andalucia-election-responsibility-table__header" scope="col">Mandatos</th>
              <th className="andalucia-election-responsibility-table__header" scope="col">Voto</th>
              <th className="andalucia-election-responsibility-table__header" scope="col">Historial</th>
              <th className="andalucia-election-responsibility-table__header" scope="col">Hueco</th>
            </tr>
          </thead>
          <tbody className="andalucia-election-responsibility-table__body">
            {rows.map((row) => {
              const href = personHref(row.person_id);
              return (
                <tr className="andalucia-election-responsibility-table__row" key={row.focus_id || row.candidate_id}>
                  <td className="andalucia-election-responsibility-table__cell andalucia-election-responsibility-table__cell--candidate">
                    {href ? (
                      <a className="andalucia-election-responsibility-table__candidate-link" href={href}>
                        {row.person_name}
                      </a>
                    ) : (
                      <span className="andalucia-election-responsibility-table__candidate-name">
                        {row.person_name}
                      </span>
                    )}
                    <span className="andalucia-election-responsibility-table__candidate-meta">
                      {row.province || "sin provincia"} · #{row.list_position || "?"}
                    </span>
                  </td>
                  <td className="andalucia-election-responsibility-table__cell">
                    <span className="andalucia-election-responsibility-table__party">
                      {row.party_acronym || row.party_key}
                    </span>
                  </td>
                  <td className="andalucia-election-responsibility-table__cell">
                    {responsibilityStatusLabel(row.status)}
                  </td>
                  <td className="andalucia-election-responsibility-table__cell">
                    {formatInt(row.mandate_count)}
                  </td>
                  <td className="andalucia-election-responsibility-table__cell">
                    {formatInt(row.reviewed_vote_events_total)} revisados / {formatInt(row.parliament_vote_events_total)} nominales
                  </td>
                  <td className="andalucia-election-responsibility-table__cell">
                    {accountabilityStatusLabel(row.accountability_evidence_status)} · {formatInt(row.accountability_entries_total)}
                  </td>
                  <td className="andalucia-election-responsibility-table__cell">
                    {responsibilityGapLabel(row.primary_gap)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="andalucia-election-responsibility-matrix__note">
        Solo perfiles foco. La atribución personal requiere voto nominal, cargo enlazado y fuente primaria por issue.
      </p>
    </div>
  );
}

function ResponsibilityComparisonSection({ comparison }) {
  const partyProfiles = Array.isArray(comparison?.party_profiles) ? comparison.party_profiles : [];
  const candidateProfiles = Array.isArray(comparison?.focus_candidate_profiles)
    ? comparison.focus_candidate_profiles
    : [];
  if (!partyProfiles.length && !candidateProfiles.length) {
    return null;
  }
  return (
    <section className="andalucia-election-section andalucia-election-responsibility-comparison" aria-labelledby="andalucia-responsibility-comparison-title">
      <div className="andalucia-election-section__head">
        <p className="andalucia-election-section__eyebrow">Responsabilidad verificable</p>
        <h2 className="andalucia-election-section__title" id="andalucia-responsibility-comparison-title">
          Qué se puede atribuir con evidencia hoy
        </h2>
        <p className="andalucia-election-section__summary">
          Cruza candidatura, programa, Parlamento, votos revisados e historial publicado. El hueco visible marca qué
          falta antes de convertirlo en mérito, culpa o impacto.
        </p>
      </div>
      <div className="andalucia-election-responsibility-comparison__grid">
        <ResponsibilityPartyMatrix profiles={partyProfiles} />
        <ResponsibilityCandidateMatrix profiles={candidateProfiles} />
      </div>
    </section>
  );
}

function PublishedAccountabilityClaimCard({ claim }) {
  const evidence = Array.isArray(claim.evidence) ? claim.evidence : [];
  const actorHref = claim.actor_kind === "candidate" ? personHref(claim.person_id) : "";
  return (
    <article className="andalucia-election-accountability-claim-card">
      <div className="andalucia-election-accountability-claim-card__head">
        <div className="andalucia-election-accountability-claim-card__actor-block">
          <p className="andalucia-election-accountability-claim-card__kind">
            {accountabilityClaimKindLabel(claim.claim_kind)}
          </p>
          <h3 className="andalucia-election-accountability-claim-card__actor">
            {actorHref ? (
              <a className="andalucia-election-accountability-claim-card__actor-link" href={actorHref}>
                {claim.actor_label || claim.actor_key}
              </a>
            ) : (
              claim.actor_label || claim.actor_key
            )}
          </h3>
        </div>
        <span className="andalucia-election-accountability-claim-card__status">
          {accountabilityClaimStatusLabel(claim.claim_status)}
        </span>
      </div>
      <p className="andalucia-election-accountability-claim-card__statement">
        {claim.statement}
      </p>
      <dl className="andalucia-election-accountability-claim-card__facts">
        <div className="andalucia-election-accountability-claim-card__fact">
          <dt>Bloque</dt>
          <dd>{claim.topic_label || topicLabel(claim.topic_id)}</dd>
        </div>
        <div className="andalucia-election-accountability-claim-card__fact">
          <dt>Posición</dt>
          <dd>{votePositionLabel(claim.vote_position)}</dd>
        </div>
        <div className="andalucia-election-accountability-claim-card__fact">
          <dt>Resultado</dt>
          <dd>{accountabilityClaimRelationLabel(claim.relation_to_outcome)}</dd>
        </div>
        <div className="andalucia-election-accountability-claim-card__fact">
          <dt>Fecha</dt>
          <dd>{claim.date || "sin fecha"}</dd>
        </div>
      </dl>
      {evidence.length ? (
        <ul className="andalucia-election-accountability-claim-evidence-list">
          {evidence.slice(0, 2).map((row, index) => (
            <li className="andalucia-election-accountability-claim-evidence-list__item" key={`${claim.claim_id}-evidence-${index}`}>
              <span className="andalucia-election-accountability-claim-evidence-list__source">
                {row.source_kind || "fuente oficial"}
              </span>
              <span className="andalucia-election-accountability-claim-evidence-list__quote">
                {row.evidence_excerpt || row.source_locator}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
      <div className="andalucia-election-accountability-claim-card__links">
        {sourceLink(claim.source_url, "PDF voto")}
        {sourceLink(claim.initiative_source_url, "Expediente")}
      </div>
      <p className="andalucia-election-accountability-claim-card__limitation">
        {claim.limitation}
      </p>
    </article>
  );
}

function PublishedAccountabilityClaimsSection({ claimsReport }) {
  const claims = Array.isArray(claimsReport?.claims) ? claimsReport.claims : [];
  if (!claims.length) {
    return null;
  }
  return (
    <section className="andalucia-election-section andalucia-election-accountability-claim-section" aria-labelledby="andalucia-accountability-claims-title">
      <div className="andalucia-election-section__head">
        <p className="andalucia-election-section__eyebrow">Claims con fuente primaria</p>
        <h2 className="andalucia-election-section__title" id="andalucia-accountability-claims-title">
          Responsabilidad legislativa observada
        </h2>
        <p className="andalucia-election-section__summary">
          Claims publicados solo cuando hay revisión estructurada del resultado oficial. Comparan actor, tema, voto y
          resultado; mérito, culpa e impacto ciudadano siguen cerrados.
        </p>
      </div>
      <div className="andalucia-election-accountability-claim-section__metrics">
        <div className="andalucia-election-accountability-claim-section__metric">
          <span className="andalucia-election-accountability-claim-section__metric-label">Claims</span>
          <strong className="andalucia-election-accountability-claim-section__metric-value">
            {formatInt(claimsReport.claims_total || claims.length)}
          </strong>
        </div>
        <div className="andalucia-election-accountability-claim-section__metric">
          <span className="andalucia-election-accountability-claim-section__metric-label">Partidos</span>
          <strong className="andalucia-election-accountability-claim-section__metric-value">
            {formatInt(claimsReport.party_claims_total)}
          </strong>
        </div>
        <div className="andalucia-election-accountability-claim-section__metric">
          <span className="andalucia-election-accountability-claim-section__metric-label">Candidatos</span>
          <strong className="andalucia-election-accountability-claim-section__metric-value">
            {formatInt(claimsReport.candidate_claims_total)}
          </strong>
        </div>
      </div>
      <div className="andalucia-election-accountability-claim-card-grid">
        {claims.slice(0, 8).map((claim) => (
          <PublishedAccountabilityClaimCard claim={claim} key={claim.claim_id} />
        ))}
      </div>
    </section>
  );
}

function IssueReviewCard({ review }) {
  const evidenceRefs = Array.isArray(review.evidence_refs) ? review.evidence_refs : [];
  const executionRefs = Array.isArray(review.execution_refs) ? review.execution_refs : [];
  const budgetRefs = Array.isArray(review.budget_refs) ? review.budget_refs : [];
  const limitations = Array.isArray(review.open_limitations) ? review.open_limitations : [];
  return (
    <article className="andalucia-election-issue-review-card">
      <div className="andalucia-election-issue-review-card__head">
        <div className="andalucia-election-issue-review-card__title-block">
          <p className="andalucia-election-issue-review-card__eyebrow">Revisión por issue</p>
          <h3 className="andalucia-election-issue-review-card__title">
            {review.topic_label || topicLabel(review.topic_id)}
          </h3>
        </div>
        <span className="andalucia-election-issue-review-card__status">
          {issueReviewStatusLabel(review.review_status)}
        </span>
      </div>
      <p className="andalucia-election-issue-review-card__summary">
        {review.review_summary}
      </p>
      <dl className="andalucia-election-issue-review-card__facts">
        <div className="andalucia-election-issue-review-card__fact">
          <dt>Dirección</dt>
          <dd>{issueDirectionStatusLabel(review.citizen_direction_status)}</dd>
        </div>
        <div className="andalucia-election-issue-review-card__fact">
          <dt>Actor</dt>
          <dd>{issueActorStatusLabel(review.responsible_actor_status)}</dd>
        </div>
        <div className="andalucia-election-issue-review-card__fact">
          <dt>Ejecutor</dt>
          <dd>{issueExecutionOwnerStatusLabel(review.execution_owner_status)}</dd>
        </div>
        <div className="andalucia-election-issue-review-card__fact">
          <dt>Ejecución</dt>
          <dd>{issueExecutionStatusLabel(review.budget_execution_status)}</dd>
        </div>
        <div className="andalucia-election-issue-review-card__fact">
          <dt>Outcome</dt>
          <dd>{issueOutcomeStatusLabel(review.outcome_status)}</dd>
        </div>
      </dl>
      <p className="andalucia-election-issue-review-card__direction">
        {review.citizen_direction_label}
      </p>
      <p className="andalucia-election-issue-review-card__actor">
        {review.responsible_actor_label}
      </p>
      {review.execution_owner_label ? (
        <p className="andalucia-election-issue-review-card__execution">
          {review.execution_owner_label}
        </p>
      ) : null}
      {review.budget_execution_label ? (
        <p className="andalucia-election-issue-review-card__budget">
          {review.budget_execution_label}
        </p>
      ) : null}
      {evidenceRefs.length ? (
        <ul className="andalucia-election-issue-review-evidence-list">
          {evidenceRefs.slice(0, 3).map((row, index) => (
            <li className="andalucia-election-issue-review-evidence-list__item" key={`${review.review_id}-evidence-${index}`}>
              <span className="andalucia-election-issue-review-evidence-list__source">
                {row.source_kind || "fuente"}
              </span>
              <span className="andalucia-election-issue-review-evidence-list__quote">
                {row.evidence_excerpt || row.source_locator}
              </span>
              {sourceLink(row.source_url, "Fuente")}
            </li>
          ))}
        </ul>
      ) : null}
      {executionRefs.length ? (
        <ul className="andalucia-election-issue-review-evidence-list andalucia-election-issue-review-execution-list">
          {executionRefs.slice(0, 2).map((row, index) => (
            <li className="andalucia-election-issue-review-evidence-list__item andalucia-election-issue-review-execution-list__item" key={`${review.review_id}-execution-${index}`}>
              <span className="andalucia-election-issue-review-evidence-list__source andalucia-election-issue-review-execution-list__source">
                {row.source_kind || "ejecución"}
              </span>
              <span className="andalucia-election-issue-review-evidence-list__quote andalucia-election-issue-review-execution-list__quote">
                {row.evidence_excerpt || row.source_locator}
              </span>
              {sourceLink(row.source_url, "Fuente")}
            </li>
          ))}
        </ul>
      ) : null}
      {budgetRefs.length ? (
        <ul className="andalucia-election-issue-review-budget-list">
          {budgetRefs.slice(0, 2).map((row, index) => {
            const amountLabel = formatMoneyEur(row.amount_eur);
            return (
              <li className="andalucia-election-issue-review-budget-list__item" key={`${review.review_id}-budget-${index}`}>
                <div className="andalucia-election-issue-review-budget-list__body">
                  <span className="andalucia-election-issue-review-budget-list__title">
                    {row.budget_project || row.evidence_excerpt || row.source_locator}
                  </span>
                  <span className="andalucia-election-issue-review-budget-list__context">
                    {[row.program_code, row.program_name, row.org_section].filter(Boolean).join(" / ")}
                  </span>
                </div>
                <div className="andalucia-election-issue-review-budget-list__facts">
                  {amountLabel ? (
                    <span className="andalucia-election-issue-review-budget-list__amount">
                      {amountLabel}
                    </span>
                  ) : null}
                  <span className="andalucia-election-issue-review-budget-list__status">
                    {issueExecutionStatusLabel(review.budget_execution_status)}
                  </span>
                  <span className="andalucia-election-issue-review-budget-list__locator">
                    {row.source_locator}
                  </span>
                  {sourceLink(row.source_url, row.source_kind === "official_boja_text" ? "PDF" : "XLSX")}
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}
      {limitations.length ? (
        <div className="andalucia-election-issue-review-limitation-list">
          {limitations.slice(0, 5).map((limitation) => (
            <span className="andalucia-election-issue-review-limitation-list__item" key={`${review.review_id}-${limitation}`}>
              {issueLimitationLabel(limitation)}
            </span>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function IssueReviewsSection({ reviewsReport }) {
  const reviews = Array.isArray(reviewsReport?.reviews) ? reviewsReport.reviews : [];
  if (!reviews.length) {
    return null;
  }
  return (
    <section className="andalucia-election-section andalucia-election-issue-review-section" aria-labelledby="andalucia-issue-reviews-title">
      <div className="andalucia-election-section__head">
        <p className="andalucia-election-section__eyebrow">Impacto por issue</p>
        <h2 className="andalucia-election-section__title" id="andalucia-issue-reviews-title">
          Dirección y responsabilidad todavía sin scoring
        </h2>
        <p className="andalucia-election-section__summary">
          Revisión estructurada de bloques que ya tienen evidencia cruzada. Documenta dirección legal y actores
          observados; separa ejecutor, presupuesto, outcomes y mérito/culpa.
        </p>
      </div>
      <div className="andalucia-election-issue-review-section__metrics">
        <div className="andalucia-election-issue-review-section__metric">
          <span className="andalucia-election-issue-review-section__metric-label">Issues revisados</span>
          <strong className="andalucia-election-issue-review-section__metric-value">
            {formatInt(reviewsReport.applied_reviews_total || reviews.length)}
          </strong>
        </div>
        <div className="andalucia-election-issue-review-section__metric">
          <span className="andalucia-election-issue-review-section__metric-label">Dirección</span>
          <strong className="andalucia-election-issue-review-section__metric-value">
            {formatInt(reviews.filter((review) => review.citizen_direction_status).length)}
          </strong>
        </div>
        <div className="andalucia-election-issue-review-section__metric">
          <span className="andalucia-election-issue-review-section__metric-label">Ejecutor</span>
          <strong className="andalucia-election-issue-review-section__metric-value">
            {formatInt(reviews.filter((review) => review.execution_owner_status).length)}
          </strong>
        </div>
        <div className="andalucia-election-issue-review-section__metric">
          <span className="andalucia-election-issue-review-section__metric-label">Partida</span>
          <strong className="andalucia-election-issue-review-section__metric-value">
            {formatInt(reviews.filter((review) => Array.isArray(review.budget_refs) && review.budget_refs.length).length)}
          </strong>
        </div>
        <div className="andalucia-election-issue-review-section__metric">
          <span className="andalucia-election-issue-review-section__metric-label">Merit/culpa</span>
          <strong className="andalucia-election-issue-review-section__metric-value">0</strong>
        </div>
      </div>
      <div className="andalucia-election-issue-review-card-grid">
        {reviews.map((review) => (
          <IssueReviewCard review={review} key={review.review_id || review.topic_id} />
        ))}
      </div>
    </section>
  );
}

function ExecutionEvidenceQueueCard({ item }) {
  const sources = Array.isArray(item.source_candidates) ? item.source_candidates : [];
  const candidateRows = Array.isArray(item.official_candidate_rows) ? item.official_candidate_rows : [];
  const reviewedRows = Array.isArray(item.reviewed_evidence_rows) ? item.reviewed_evidence_rows : [];
  const searchTerms = Array.isArray(item.search_terms) ? item.search_terms : [];
  return (
    <article className="andalucia-election-execution-evidence-card">
      <div className="andalucia-election-execution-evidence-card__head">
        <div className="andalucia-election-execution-evidence-card__title-block">
          <p className="andalucia-election-execution-evidence-card__eyebrow">
            {item.evidence_need || issuePacketGapLabel(item.gap_id)}
          </p>
          <h3 className="andalucia-election-execution-evidence-card__title">
            {item.topic_label || topicLabel(item.topic_id)}
          </h3>
        </div>
        <span className="andalucia-election-execution-evidence-card__status">
          {executionEvidenceStatusLabel(item.status)}
        </span>
      </div>
      <p className="andalucia-election-execution-evidence-card__question">
        {item.review_question}
      </p>
      <p className="andalucia-election-execution-evidence-card__resolution">
        {item.expected_resolution}
      </p>
      <div className="andalucia-election-execution-evidence-card__meta">
        <span className="andalucia-election-execution-evidence-card__meta-item">
          {issuePacketStatusLabel(item.current_packet_status)}
        </span>
        <span className="andalucia-election-execution-evidence-card__meta-item">
          {issueReviewStatusLabel(item.issue_review_status)}
        </span>
      </div>
      {searchTerms.length ? (
        <div className="andalucia-election-execution-evidence-term-list">
          {searchTerms.slice(0, 8).map((term) => (
            <span className="andalucia-election-execution-evidence-term-list__item" key={`${item.queue_item_id}-${term}`}>
              {term}
            </span>
          ))}
        </div>
      ) : null}
      {reviewedRows.length ? (
        <div className="andalucia-election-execution-evidence-review-panel">
          <div className="andalucia-election-execution-evidence-review-panel__head">
            <span className="andalucia-election-execution-evidence-review-panel__label">
              Filas revisadas
            </span>
            <strong className="andalucia-election-execution-evidence-review-panel__count">
              {formatInt(item.reviewed_evidence_rows_total || reviewedRows.length)}
            </strong>
          </div>
          <ul className="andalucia-election-execution-evidence-review-list">
            {reviewedRows.slice(0, 6).map((row) => {
              const valueLabel = formatExecutionEvidenceValue(row);
              const primaryLabel =
                row.reviewed_label || row.summary || row.budget_project || row.contract_object || row.indicator_name || row.program_name;
              const contextLabel = [
                row.program_code && row.program_name ? `${row.program_code} ${row.program_name}` : row.program_name,
                row.contract_reference,
                row.contracting_body,
                row.place,
                row.outcome_territory,
                row.outcome_periodicity,
                row.org_section,
              ]
                .filter(Boolean)
                .join(" / ");
              return (
                <li className="andalucia-election-execution-evidence-review-list__item" key={row.review_item_id || row.candidate_row_id || row.source_locator}>
                  <div className="andalucia-election-execution-evidence-review-list__body">
                    <span className="andalucia-election-execution-evidence-review-list__title">
                      {primaryLabel || "Fila oficial revisada"}
                    </span>
                    {contextLabel ? (
                      <span className="andalucia-election-execution-evidence-review-list__context">
                        {contextLabel}
                      </span>
                    ) : null}
                    {row.review_summary ? (
                      <p className="andalucia-election-execution-evidence-review-list__summary">
                        {row.review_summary}
                      </p>
                    ) : null}
                  </div>
                  <div className="andalucia-election-execution-evidence-review-list__facts">
                    {valueLabel ? (
                      <span className="andalucia-election-execution-evidence-review-list__value">
                        {valueLabel}
                      </span>
                    ) : null}
                    <span className="andalucia-election-execution-evidence-review-list__locator">
                      {row.source_locator}
                    </span>
                    <span className="andalucia-election-execution-evidence-review-list__status">
                      {executionEvidenceStatusLabel(row.review_status)}
                    </span>
                    <span className="andalucia-election-execution-evidence-review-list__claim">
                      {executionEvidenceStatusLabel(row.claim_status)}
                    </span>
                    {sourceLink(row.source_url, executionEvidenceSourceLabel(row))}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
      {candidateRows.length ? (
        <div className="andalucia-election-execution-evidence-candidate-panel">
          <div className="andalucia-election-execution-evidence-candidate-panel__head">
            <span className="andalucia-election-execution-evidence-candidate-panel__label">
              Filas oficiales candidatas
            </span>
            <strong className="andalucia-election-execution-evidence-candidate-panel__count">
              {formatInt(item.official_candidate_rows_total || candidateRows.length)}
            </strong>
          </div>
          <ul className="andalucia-election-execution-evidence-candidate-list">
            {candidateRows.slice(0, 6).map((row) => {
              const valueLabel = formatExecutionEvidenceValue(row);
              const primaryLabel =
                row.summary || row.budget_project || row.indicator_name || row.contract_object || row.activity_name || row.program_name;
              const contextLabel = [
                row.program_code && row.program_name ? `${row.program_code} ${row.program_name}` : row.program_name,
                row.contract_reference,
                row.contracting_body,
                row.place,
                row.outcome_territory,
                row.outcome_periodicity,
                row.org_section,
                row.policy_area,
              ]
                .filter(Boolean)
                .join(" / ");
              return (
                <li className="andalucia-election-execution-evidence-candidate-list__item" key={row.candidate_row_id || row.source_locator}>
                  <div className="andalucia-election-execution-evidence-candidate-list__body">
                    <span className="andalucia-election-execution-evidence-candidate-list__title">
                      {primaryLabel || "Fila oficial candidata"}
                    </span>
                    {contextLabel ? (
                      <span className="andalucia-election-execution-evidence-candidate-list__context">
                        {contextLabel}
                      </span>
                    ) : null}
                  </div>
                  <div className="andalucia-election-execution-evidence-candidate-list__facts">
                    {valueLabel ? (
                      <span className="andalucia-election-execution-evidence-candidate-list__amount">
                        {valueLabel}
                      </span>
                    ) : null}
                    <span className="andalucia-election-execution-evidence-candidate-list__locator">
                      {row.source_locator}
                    </span>
                    <span className="andalucia-election-execution-evidence-candidate-list__status">
                      {executionEvidenceStatusLabel(row.match_status)}
                    </span>
                    {sourceLink(row.source_url, executionEvidenceSourceLabel(row))}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
      {sources.length ? (
        <ul className="andalucia-election-execution-evidence-source-list">
          {sources.map((source) => (
            <li className="andalucia-election-execution-evidence-source-list__item" key={source.source_id}>
              <div className="andalucia-election-execution-evidence-source-list__body">
                <span className="andalucia-election-execution-evidence-source-list__name">
                  {source.name || source.source_id}
                </span>
                <span className="andalucia-election-execution-evidence-source-list__hint">
                  {source.filter_hint}
                </span>
                {Number(source.official_candidate_rows_total || 0) > 0 ? (
                  <span className="andalucia-election-execution-evidence-source-list__count">
                    {formatInt(source.official_candidate_rows_total)} filas candidatas
                  </span>
                ) : null}
              </div>
              <div className="andalucia-election-execution-evidence-source-list__links">
                <span className="andalucia-election-execution-evidence-source-list__status">
                  {executionEvidenceStatusLabel(source.status)}
                </span>
                {sourceLink(source.source_url || source.landing_url, executionEvidenceSourceLabel(source))}
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}

function ExecutionEvidenceQueueSection({ queueReport, csvHref }) {
  const queue = Array.isArray(queueReport?.queue) ? queueReport.queue : [];
  if (!queue.length) {
    return null;
  }
  return (
    <section className="andalucia-election-section andalucia-election-execution-evidence-section" aria-labelledby="andalucia-execution-evidence-title">
      <div className="andalucia-election-section__head">
        <p className="andalucia-election-section__eyebrow">Ejecución y dinero</p>
        <h2 className="andalucia-election-section__title" id="andalucia-execution-evidence-title">
          Lo que falta para pasar de ley a impacto
        </h2>
        <p className="andalucia-election-section__summary">
          Cola de fuentes oficiales ya localizadas para resolver unidad ejecutora, presupuesto, contratos,
          subvenciones e indicadores. Sigue sin publicar mérito o culpa.
        </p>
        {sourceLink(csvHref, "CSV ejecución")}
      </div>
      <div className="andalucia-election-execution-evidence-section__metrics">
        <div className="andalucia-election-execution-evidence-section__metric">
          <span className="andalucia-election-execution-evidence-section__metric-label">Ítems cola</span>
          <strong className="andalucia-election-execution-evidence-section__metric-value">
            {formatInt(queueReport.queue_total || queue.length)}
          </strong>
        </div>
        <div className="andalucia-election-execution-evidence-section__metric">
          <span className="andalucia-election-execution-evidence-section__metric-label">Temas</span>
          <strong className="andalucia-election-execution-evidence-section__metric-value">
            {formatInt(queueReport.topics_total)}
          </strong>
        </div>
        <div className="andalucia-election-execution-evidence-section__metric">
          <span className="andalucia-election-execution-evidence-section__metric-label">Fuentes verificadas</span>
          <strong className="andalucia-election-execution-evidence-section__metric-value">
            {formatInt(queueReport.verified_source_candidates_total)}
          </strong>
        </div>
        <div className="andalucia-election-execution-evidence-section__metric">
          <span className="andalucia-election-execution-evidence-section__metric-label">Filas oficiales</span>
          <strong className="andalucia-election-execution-evidence-section__metric-value">
            {formatInt(queueReport.official_candidate_rows_total)}
          </strong>
        </div>
        <div className="andalucia-election-execution-evidence-section__metric">
          <span className="andalucia-election-execution-evidence-section__metric-label">Contratos candidatos</span>
          <strong className="andalucia-election-execution-evidence-section__metric-value">
            {formatInt(queueReport.contract_candidate_rows_total)}
          </strong>
        </div>
        <div className="andalucia-election-execution-evidence-section__metric">
          <span className="andalucia-election-execution-evidence-section__metric-label">Contratos revisados</span>
          <strong className="andalucia-election-execution-evidence-section__metric-value">
            {formatInt(queueReport.reviewed_contract_rows_total)}
          </strong>
        </div>
        <div className="andalucia-election-execution-evidence-section__metric">
          <span className="andalucia-election-execution-evidence-section__metric-label">Filas revisadas</span>
          <strong className="andalucia-election-execution-evidence-section__metric-value">
            {formatInt(queueReport.reviewed_evidence_rows_total)}
          </strong>
        </div>
      </div>
      <div className="andalucia-election-execution-evidence-card-grid">
        {queue.map((item) => (
          <ExecutionEvidenceQueueCard item={item} key={item.queue_item_id} />
        ))}
      </div>
    </section>
  );
}

function indexDeliveryHuntResultsByTopic(deliveryHuntResults) {
  const rows = Array.isArray(deliveryHuntResults?.targets) ? deliveryHuntResults.targets : [];
  const byTopic = new Map();
  for (const row of rows) {
    const topicId = row.topic_id || "";
    if (!topicId) {
      continue;
    }
    if (!byTopic.has(topicId)) {
      byTopic.set(topicId, []);
    }
    byTopic.get(topicId).push(row);
  }
  return byTopic;
}

function deliveryHuntResultSummary(rows) {
  const resultRows = Array.isArray(rows) ? rows : [];
  return resultRows.reduce(
    (acc, row) => {
      acc.targetsTotal += 1;
      if (row.status !== "manual_search_landing_ready") {
        acc.executedTotal += 1;
      }
      acc.candidatesTotal += Number(row.result_candidates_total || 0);
      acc.machineReadableTotal += Number(row.result_candidates_machine_readable_total || 0);
      return acc;
    },
    { targetsTotal: 0, executedTotal: 0, candidatesTotal: 0, machineReadableTotal: 0 },
  );
}

function deliveryHuntCandidateSamples(rows, limit = 2) {
  return (Array.isArray(rows) ? rows : [])
    .flatMap((row) =>
      (Array.isArray(row.result_candidates) ? row.result_candidates : []).map((candidate) => ({
        ...candidate,
        targetRunId: row.target_run_id,
        targetRegistry: row.registry,
      })),
    )
    .slice(0, limit);
}

function ReadinessIssueCard({ issue, deliveryHuntResultTargets = [] }) {
  const blockers = Array.isArray(issue.blockers) ? issue.blockers : [];
  const kindCounts = Array.isArray(issue.reviewed_execution_evidence_kind_counts)
    ? issue.reviewed_execution_evidence_kind_counts
    : [];
  const deliveryHunts = Array.isArray(issue.delivery_evidence_hunts) ? issue.delivery_evidence_hunts : [];
  const deliveryTargets = deliveryHunts
    .flatMap((hunt) => (Array.isArray(hunt.search_targets) ? hunt.search_targets : []))
    .slice(0, 3);
  const huntResultSummary = deliveryHuntResultSummary(deliveryHuntResultTargets);
  const huntResultCandidates = deliveryHuntCandidateSamples(deliveryHuntResultTargets, 2);
  const nextAction = issue.next_action || {};
  return (
    <article className="andalucia-election-readiness-card">
      <div className="andalucia-election-readiness-card__head">
        <div className="andalucia-election-readiness-card__title-block">
          <p className="andalucia-election-readiness-card__eyebrow">Clasificador automático</p>
          <h3 className="andalucia-election-readiness-card__title">
            {issue.topic_label || topicLabel(issue.topic_id)}
          </h3>
        </div>
        <span className="andalucia-election-readiness-card__status">
          {readinessClassificationLabel(issue.classification)}
        </span>
      </div>
      <dl className="andalucia-election-readiness-card__facts">
        <div className="andalucia-election-readiness-card__fact">
          <dt>Claims obs.</dt>
          <dd>{formatInt(issue.observed_responsibility_claims_total)}</dd>
        </div>
        <div className="andalucia-election-readiness-card__fact">
          <dt>Votos</dt>
          <dd>{formatInt(issue.reviewed_vote_items_total)}</dd>
        </div>
        <div className="andalucia-election-readiness-card__fact">
          <dt>BOJA</dt>
          <dd>{formatInt(issue.reviewed_boja_legal_changes_total)}</dd>
        </div>
        <div className="andalucia-election-readiness-card__fact">
          <dt>Ejecución</dt>
          <dd>{formatInt(issue.reviewed_execution_evidence_rows_total)}</dd>
        </div>
        <div className="andalucia-election-readiness-card__fact">
          <dt>Post outcome</dt>
          <dd>{formatInt(issue.post_change_outcome_rows_total)}</dd>
        </div>
      </dl>
      <p className="andalucia-election-readiness-card__blocker">
        {issue.primary_blocker_label || readinessBlockerLabel(issue.primary_blocker)}
      </p>
      {kindCounts.length ? (
        <div className="andalucia-election-readiness-kind-list">
          {kindCounts.slice(0, 5).map((row) => (
            <span className="andalucia-election-readiness-kind-list__item" key={`${issue.topic_id}-${row.key}`}>
              {executionEvidenceStatusLabel(row.key)}: {formatInt(row.count)}
            </span>
          ))}
        </div>
      ) : null}
      <div className="andalucia-election-readiness-blocker-list">
        {blockers.slice(0, 5).map((blocker) => (
          <span className="andalucia-election-readiness-blocker-list__item" key={`${issue.topic_id}-${blocker}`}>
            {readinessBlockerLabel(blocker)}
          </span>
        ))}
      </div>
      {nextAction.action_id ? (
        <div className="andalucia-election-readiness-next-action">
          <span className="andalucia-election-readiness-next-action__label">
            {nextAction.label || readinessBlockerLabel(nextAction.blocker_id)}
          </span>
          <span className="andalucia-election-readiness-next-action__description">
            {nextAction.description}
          </span>
          <code className="andalucia-election-readiness-next-action__command">
            {nextAction.automation_command}
          </code>
          {deliveryHunts.length ? (
            <div className="andalucia-election-readiness-delivery-hunt">
              <span className="andalucia-election-readiness-delivery-hunt__label">
                {formatInt(deliveryHunts.length)} pistas oficiales · {formatInt(issue.delivery_evidence_search_targets_total)} búsquedas
              </span>
              {huntResultSummary.targetsTotal ? (
                <div className="andalucia-election-readiness-delivery-hunt__run-summary">
                  <span className="andalucia-election-readiness-delivery-hunt__run-stat">
                    Ejecutadas {formatInt(huntResultSummary.executedTotal)}
                  </span>
                  <span className="andalucia-election-readiness-delivery-hunt__run-stat">
                    Resultados {formatInt(huntResultSummary.candidatesTotal)}
                  </span>
                  <span className="andalucia-election-readiness-delivery-hunt__run-stat">
                    Descargables {formatInt(huntResultSummary.machineReadableTotal)}
                  </span>
                </div>
              ) : null}
              {huntResultCandidates.length ? (
                <div className="andalucia-election-readiness-delivery-hunt__result-list">
                  {huntResultCandidates.map((candidate) => (
                    <a
                      className="andalucia-election-readiness-delivery-hunt__result-link"
                      href={candidate.url}
                      key={`${candidate.targetRunId}-${candidate.candidate_id}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <span className="andalucia-election-readiness-delivery-hunt__result-registry">
                        {candidate.targetRegistry}
                      </span>
                      <span className="andalucia-election-readiness-delivery-hunt__result-title">
                        {candidate.title || candidate.package_name || "resultado oficial"}
                      </span>
                    </a>
                  ))}
                </div>
              ) : null}
              <div className="andalucia-election-readiness-delivery-hunt__target-list">
                {deliveryTargets.map((target) => (
                  <a
                    className="andalucia-election-readiness-delivery-hunt__target-link"
                    href={target.url}
                    key={target.target_id}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <span className="andalucia-election-readiness-delivery-hunt__target-registry">
                      {target.registry}
                    </span>
                    <span className="andalucia-election-readiness-delivery-hunt__target-query">
                      {target.query}
                    </span>
                  </a>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

function AccountabilityReadinessSection({ readinessReport, deliveryHuntResults, deliveryReviewDrafts }) {
  const issues = Array.isArray(readinessReport?.issues) ? readinessReport.issues : [];
  const blockerCounts = Array.isArray(readinessReport?.primary_blocker_counts)
    ? readinessReport.primary_blocker_counts
    : [];
  const huntResultSummary = deliveryHuntResults?.summary || {};
  const deliveryReviewSummary = deliveryReviewDrafts || {};
  const huntResultsByTopic = indexDeliveryHuntResultsByTopic(deliveryHuntResults);
  if (!issues.length) {
    return null;
  }
  return (
    <section className="andalucia-election-section andalucia-election-readiness-section" aria-labelledby="andalucia-readiness-title">
      <div className="andalucia-election-section__head">
        <p className="andalucia-election-section__eyebrow">Automatización de scoring</p>
        <h2 className="andalucia-election-section__title" id="andalucia-readiness-title">
          Por qué todavía no hay mérito/culpa
        </h2>
        <p className="andalucia-election-section__summary">
          Clasificador generado en cada export. Marca el bloqueo exacto por issue y la siguiente acción automatizable
          antes de permitir una valoración pública.
        </p>
      </div>
      <div className="andalucia-election-readiness-section__metrics">
        <div className="andalucia-election-readiness-section__metric">
          <span className="andalucia-election-readiness-section__metric-label">Issues</span>
          <strong className="andalucia-election-readiness-section__metric-value">
            {formatInt(readinessReport.topics_total || issues.length)}
          </strong>
        </div>
        <div className="andalucia-election-readiness-section__metric">
          <span className="andalucia-election-readiness-section__metric-label">Resp. observada</span>
          <strong className="andalucia-election-readiness-section__metric-value">
            {formatInt(readinessReport.topics_with_observed_responsibility_total)}
          </strong>
        </div>
        <div className="andalucia-election-readiness-section__metric">
          <span className="andalucia-election-readiness-section__metric-label">Ejecución</span>
          <strong className="andalucia-election-readiness-section__metric-value">
            {formatInt(readinessReport.topics_with_execution_evidence_total)}
          </strong>
        </div>
        <div className="andalucia-election-readiness-section__metric">
          <span className="andalucia-election-readiness-section__metric-label">Baseline outcome</span>
          <strong className="andalucia-election-readiness-section__metric-value">
            {formatInt(readinessReport.topics_with_observed_outcome_baseline_total)}
          </strong>
        </div>
        <div className="andalucia-election-readiness-section__metric andalucia-election-readiness-section__metric--warning">
          <span className="andalucia-election-readiness-section__metric-label">Valorables</span>
          <strong className="andalucia-election-readiness-section__metric-value">
            {formatInt(readinessReport.publishable_merit_blame_topics_total)}
          </strong>
        </div>
        <div className="andalucia-election-readiness-section__metric">
          <span className="andalucia-election-readiness-section__metric-label">Auto-hunts</span>
          <strong className="andalucia-election-readiness-section__metric-value">
            {formatInt(readinessReport.delivery_evidence_hunts_total)}
          </strong>
        </div>
        <div className="andalucia-election-readiness-section__metric">
          <span className="andalucia-election-readiness-section__metric-label">Hunts ejecutadas</span>
          <strong className="andalucia-election-readiness-section__metric-value">
            {formatInt(huntResultSummary.targets_executed_total)}
          </strong>
        </div>
        <div className="andalucia-election-readiness-section__metric">
          <span className="andalucia-election-readiness-section__metric-label">Resultados oficiales</span>
          <strong className="andalucia-election-readiness-section__metric-value">
            {formatInt(huntResultSummary.result_candidates_total)}
          </strong>
        </div>
        <div className="andalucia-election-readiness-section__metric">
          <span className="andalucia-election-readiness-section__metric-label">Confirmadas</span>
          <strong className="andalucia-election-readiness-section__metric-value">
            {formatInt(deliveryReviewSummary.confirmations_total)}
          </strong>
        </div>
        <div className="andalucia-election-readiness-section__metric">
          <span className="andalucia-election-readiness-section__metric-label">Drafts revisión</span>
          <strong className="andalucia-election-readiness-section__metric-value">
            {formatInt(deliveryReviewSummary.drafts_total)}
          </strong>
        </div>
      </div>
      {blockerCounts.length ? (
        <div className="andalucia-election-readiness-blocker-summary" aria-label="Bloqueos principales">
          {blockerCounts.slice(0, 5).map((row) => (
            <span className="andalucia-election-readiness-blocker-summary__item" key={row.key}>
              {readinessBlockerLabel(row.key, row.label)}: {formatInt(row.count)}
            </span>
          ))}
        </div>
      ) : null}
      <div className="andalucia-election-readiness-card-grid">
        {issues.slice(0, 8).map((issue) => (
          <ReadinessIssueCard
            issue={issue}
            deliveryHuntResultTargets={huntResultsByTopic.get(issue.topic_id) || []}
            key={issue.topic_id}
          />
        ))}
      </div>
    </section>
  );
}

function PostChangeOutcomeMonitorCard({ series }) {
  const latestValue = formatEvidenceUnitValue(
    series.latest_value_format || series.latest_value,
    series.indicator_unit,
  );
  const baselineValue = formatEvidenceUnitValue(
    series.baseline_value_format || series.baseline_value,
    series.indicator_unit,
  );
  return (
    <article className="andalucia-election-outcome-monitor-card">
      <div className="andalucia-election-outcome-monitor-card__head">
        <div className="andalucia-election-outcome-monitor-card__title-block">
          <p className="andalucia-election-outcome-monitor-card__eyebrow">
            {series.topic_label || topicLabel(series.topic_id)}
          </p>
          <h3 className="andalucia-election-outcome-monitor-card__title">
            {series.indicator_name || series.source_name || series.source_id}
          </h3>
        </div>
        <span className="andalucia-election-outcome-monitor-card__status">
          {postChangeOutcomeStatusLabel(series.post_change_status)}
        </span>
      </div>
      <dl className="andalucia-election-outcome-monitor-card__facts">
        <div className="andalucia-election-outcome-monitor-card__fact">
          <dt>Baseline</dt>
          <dd>
            {[series.baseline_year, baselineValue].filter(Boolean).join(" · ") || "sin dato"}
          </dd>
        </div>
        <div className="andalucia-election-outcome-monitor-card__fact">
          <dt>Último</dt>
          <dd>
            {[series.latest_year, latestValue].filter(Boolean).join(" · ") || "sin dato"}
          </dd>
        </div>
        <div className="andalucia-election-outcome-monitor-card__fact">
          <dt>Próxima revisión</dt>
          <dd>{series.next_post_change_check_year || series.post_change_min_year || "pendiente"}</dd>
        </div>
        <div className="andalucia-election-outcome-monitor-card__fact">
          <dt>Post-change</dt>
          <dd>{formatInt(series.post_change_rows_total)}</dd>
        </div>
      </dl>
      <div className="andalucia-election-outcome-monitor-card__meta">
        <span className="andalucia-election-outcome-monitor-card__periodicity">
          {series.outcome_periodicity || "periodicidad pendiente"}
        </span>
        <span className="andalucia-election-outcome-monitor-card__territory">
          {series.outcome_territory || "territorio pendiente"}
        </span>
      </div>
      <p className="andalucia-election-outcome-monitor-card__note">
        {executionEvidenceStatusLabel(series.interpretation_status)}
      </p>
      <div className="andalucia-election-outcome-monitor-card__links">
        {sourceLink(series.source_url || series.landing_url, "Fuente IECA")}
      </div>
    </article>
  );
}

function PostChangeOutcomeMonitorSection({ monitor }) {
  const series = Array.isArray(monitor?.series) ? monitor.series : [];
  if (!series.length) {
    return null;
  }
  return (
    <section className="andalucia-election-section andalucia-election-outcome-monitor-section" aria-labelledby="andalucia-outcome-monitor-title">
      <div className="andalucia-election-section__head">
        <p className="andalucia-election-section__eyebrow">Monitor automático de outcomes</p>
        <h2 className="andalucia-election-section__title" id="andalucia-outcome-monitor-title">
          Cuándo podremos valorar impacto real
        </h2>
        <p className="andalucia-election-section__summary">
          Cada export lee series oficiales IECA y marca si ya existe dato posterior a 2026. Si aparece, pasa a
          revisión causal antes de cualquier mérito o culpa.
        </p>
      </div>
      <div className="andalucia-election-outcome-monitor-section__metrics">
        <div className="andalucia-election-outcome-monitor-section__metric">
          <span className="andalucia-election-outcome-monitor-section__metric-label">Series</span>
          <strong className="andalucia-election-outcome-monitor-section__metric-value">
            {formatInt(monitor.series_total || series.length)}
          </strong>
        </div>
        <div className="andalucia-election-outcome-monitor-section__metric">
          <span className="andalucia-election-outcome-monitor-section__metric-label">Esperando</span>
          <strong className="andalucia-election-outcome-monitor-section__metric-value">
            {formatInt(monitor.waiting_series_total)}
          </strong>
        </div>
        <div className="andalucia-election-outcome-monitor-section__metric andalucia-election-outcome-monitor-section__metric--warning">
          <span className="andalucia-election-outcome-monitor-section__metric-label">Listas revisar</span>
          <strong className="andalucia-election-outcome-monitor-section__metric-value">
            {formatInt(monitor.post_change_candidate_series_total)}
          </strong>
        </div>
        <div className="andalucia-election-outcome-monitor-section__metric">
          <span className="andalucia-election-outcome-monitor-section__metric-label">Próxima ventana</span>
          <strong className="andalucia-election-outcome-monitor-section__metric-value">
            {monitor.next_post_change_check_year || monitor.post_change_min_year || "2026"}
          </strong>
        </div>
      </div>
      <div className="andalucia-election-outcome-monitor-card-grid">
        {series.slice(0, 8).map((row) => (
          <PostChangeOutcomeMonitorCard series={row} key={row.series_id} />
        ))}
      </div>
    </section>
  );
}

function IssueAccountabilityPacketCard({ packet }) {
  const partyProfiles = Array.isArray(packet.party_profiles) ? packet.party_profiles : [];
  const observedActorProfiles = Array.isArray(packet.observed_responsibility_actor_profiles)
    ? packet.observed_responsibility_actor_profiles
    : [];
  const observedClaimSamples = Array.isArray(packet.observed_responsibility_claim_samples)
    ? packet.observed_responsibility_claim_samples
    : [];
  const gaps = Array.isArray(packet.open_gaps) ? packet.open_gaps : [];
  const voteSamples = Array.isArray(packet.reviewed_vote_samples) ? packet.reviewed_vote_samples : [];
  const bojaSamples = Array.isArray(packet.reviewed_boja_samples) ? packet.reviewed_boja_samples : [];
  return (
    <article className="andalucia-election-issue-packet-card">
      <div className="andalucia-election-issue-packet-card__head">
        <div className="andalucia-election-issue-packet-card__title-block">
          <p className="andalucia-election-issue-packet-card__eyebrow">Bloque ciudadano</p>
          <h3 className="andalucia-election-issue-packet-card__title">
            {packet.topic_label || topicLabel(packet.topic_id)}
          </h3>
        </div>
        <span className="andalucia-election-issue-packet-card__status">
          {issuePacketStatusLabel(packet.status)}
        </span>
      </div>
      <dl className="andalucia-election-issue-packet-card__facts">
        <div className="andalucia-election-issue-packet-card__fact">
          <dt>Programa</dt>
          <dd>{formatInt(packet.program_measures_total)}</dd>
        </div>
        <div className="andalucia-election-issue-packet-card__fact">
          <dt>Partidos</dt>
          <dd>{formatInt(packet.program_parties_total)}</dd>
        </div>
        <div className="andalucia-election-issue-packet-card__fact">
          <dt>Votos</dt>
          <dd>{formatInt(packet.reviewed_vote_items_total)}</dd>
        </div>
        <div className="andalucia-election-issue-packet-card__fact">
          <dt>BOJA</dt>
          <dd>{formatInt(packet.reviewed_boja_legal_changes_total)}</dd>
        </div>
        <div className="andalucia-election-issue-packet-card__fact">
          <dt>Claims</dt>
          <dd>{formatInt(packet.observed_responsibility_claims_total)}</dd>
        </div>
      </dl>
      {observedActorProfiles.length ? (
        <div className="andalucia-election-issue-packet-observed-actor-list" aria-label={`Responsabilidad observada en ${packet.topic_label}`}>
          {observedActorProfiles.slice(0, 5).map((profile) => (
            <span className="andalucia-election-issue-packet-observed-actor-list__item" key={`${packet.topic_id}-observed-${profile.actor_kind}-${profile.actor_key}`}>
              {profile.actor_label || profile.actor_key}: {formatInt(profile.with_reviewed_outcome_total)} con ·{" "}
              {formatInt(profile.against_reviewed_outcome_total)} contra
            </span>
          ))}
        </div>
      ) : null}
      {partyProfiles.length ? (
        <div className="andalucia-election-issue-packet-party-list" aria-label={`Partidos en ${packet.topic_label}`}>
          {partyProfiles.slice(0, 5).map((profile) => (
            <span className="andalucia-election-issue-packet-party-list__item" key={`${packet.topic_id}-${profile.party_key}`}>
              {profile.party_label || profile.party_key}: {formatInt(profile.reviewed_vote_events_total)} votos ·{" "}
              {formatInt(profile.program_measures_total)} medidas
            </span>
          ))}
        </div>
      ) : null}
      {voteSamples.length || bojaSamples.length ? (
        <ul className="andalucia-election-issue-packet-sample-list">
          {voteSamples.slice(0, 2).map((sample) => (
            <li className="andalucia-election-issue-packet-sample-list__item" key={sample.review_item_id}>
              <span className="andalucia-election-issue-packet-sample-list__kind">Voto</span>
              <span className="andalucia-election-issue-packet-sample-list__text">
                {sample.reviewed_issue_label || sample.numexp || sample.title}
              </span>
              {sourceLink(sample.source_url, "PDF")}
            </li>
          ))}
          {observedClaimSamples.slice(0, 2).map((sample) => (
            <li className="andalucia-election-issue-packet-sample-list__item" key={sample.claim_id}>
              <span className="andalucia-election-issue-packet-sample-list__kind">Resp.</span>
              <span className="andalucia-election-issue-packet-sample-list__text">
                {sample.actor_label || sample.actor_key}: {accountabilityClaimRelationLabel(sample.relation_to_outcome)}
              </span>
              {sourceLink(sample.source_url, "PDF")}
            </li>
          ))}
          {bojaSamples.slice(0, 2).map((sample) => (
            <li className="andalucia-election-issue-packet-sample-list__item" key={sample.review_item_id}>
              <span className="andalucia-election-issue-packet-sample-list__kind">BOJA</span>
              <span className="andalucia-election-issue-packet-sample-list__text">
                {sample.reviewed_legal_change_label || sample.action_kind || sample.boja_id}
              </span>
              {sourceLink(sample.source_url, "PDF")}
            </li>
          ))}
        </ul>
      ) : null}
      <div className="andalucia-election-issue-packet-gap-list">
        {gaps.slice(0, 5).map((gap) => (
          <span className="andalucia-election-issue-packet-gap-list__item" key={`${packet.topic_id}-${gap}`}>
            {issuePacketGapLabel(gap)}
          </span>
        ))}
      </div>
    </article>
  );
}

function IssueAccountabilityPacketsSection({ packetsReport }) {
  const packets = Array.isArray(packetsReport?.packets) ? packetsReport.packets : [];
  if (!packets.length) {
    return null;
  }
  return (
    <section className="andalucia-election-section andalucia-election-issue-packet-section" aria-labelledby="andalucia-issue-packets-title">
      <div className="andalucia-election-section__head">
        <p className="andalucia-election-section__eyebrow">Promesa · voto · BOJA</p>
        <h2 className="andalucia-election-section__title" id="andalucia-issue-packets-title">
          Bloques listos para revisión por issue
        </h2>
        <p className="andalucia-election-section__summary">
          Paquetes por bloque ciudadano. Combinan promesas declaradas, votos revisados y cambios BOJA revisados; los
          huecos muestran qué falta antes de publicar responsabilidad.
        </p>
      </div>
      <div className="andalucia-election-issue-packet-section__metrics">
        <div className="andalucia-election-issue-packet-section__metric">
          <span className="andalucia-election-issue-packet-section__metric-label">Bloques</span>
          <strong className="andalucia-election-issue-packet-section__metric-value">
            {formatInt(packetsReport.packets_total || packets.length)}
          </strong>
        </div>
        <div className="andalucia-election-issue-packet-section__metric">
          <span className="andalucia-election-issue-packet-section__metric-label">Con voto</span>
          <strong className="andalucia-election-issue-packet-section__metric-value">
            {formatInt(packetsReport.packets_with_reviewed_vote_total)}
          </strong>
        </div>
        <div className="andalucia-election-issue-packet-section__metric">
          <span className="andalucia-election-issue-packet-section__metric-label">Con BOJA</span>
          <strong className="andalucia-election-issue-packet-section__metric-value">
            {formatInt(packetsReport.packets_with_reviewed_boja_total)}
          </strong>
        </div>
        <div className="andalucia-election-issue-packet-section__metric">
          <span className="andalucia-election-issue-packet-section__metric-label">Con claims</span>
          <strong className="andalucia-election-issue-packet-section__metric-value">
            {formatInt(packetsReport.packets_with_observed_responsibility_total)}
          </strong>
        </div>
      </div>
      <div className="andalucia-election-issue-packet-card-grid">
        {packets.map((packet) => (
          <IssueAccountabilityPacketCard packet={packet} key={packet.topic_id} />
        ))}
      </div>
    </section>
  );
}

function ProgramSourceCard({ source }) {
  const topicHits = source.topic_hits || {};
  const topTopics = Array.isArray(source.top_topics)
    ? source.top_topics
    : Object.entries(topicHits)
      .map(([topic, hits]) => ({ topic, hits }))
      .sort((a, b) => Number(b.hits || 0) - Number(a.hits || 0))
      .slice(0, 5);
  const headings = Array.isArray(source.heading_sample) ? source.heading_sample : [];
  return (
    <article className="andalucia-election-program-card">
      <div className="andalucia-election-program-card__head">
        <p className="andalucia-election-program-card__party">{source.party_acronym || source.party_key}</p>
        <h3 className="andalucia-election-program-card__title">{source.title || "Programa electoral"}</h3>
      </div>
      <dl className="andalucia-election-program-card__facts">
        <div className="andalucia-election-program-card__fact">
          <dt>Verificación</dt>
          <dd>{verificationLabel(source.verification_status)}</dd>
        </div>
        <div className="andalucia-election-program-card__fact">
          <dt>Fuente</dt>
          <dd>{officialityLabel(source.officiality)}</dd>
        </div>
        <div className="andalucia-election-program-card__fact">
          <dt>Páginas</dt>
          <dd>{formatInt(source.page_count)}</dd>
        </div>
        <div className="andalucia-election-program-card__fact">
          <dt>Texto</dt>
          <dd>{formatInt(source.text_chars)} chars</dd>
        </div>
        <div className="andalucia-election-program-card__fact">
          <dt>Medidas</dt>
          <dd>{formatInt(source.measures_total)}</dd>
        </div>
      </dl>
      <div className="andalucia-election-program-card__topics">
        {topTopics.length ? (
          topTopics.map((topic) => (
            <span className="andalucia-election-program-card__topic" key={`${source.source_id}-${topic.topic}`}>
              {topic.topic}: {formatInt(topic.hits)}
            </span>
          ))
        ) : (
          <span className="andalucia-election-program-card__topic">sin términos detectados</span>
        )}
      </div>
      {headings.length ? (
        <ul className="andalucia-election-program-card__heading-list">
          {headings.slice(0, 4).map((heading) => (
            <li className="andalucia-election-program-card__heading-item" key={`${source.source_id}-${heading}`}>
              {heading}
            </li>
          ))}
        </ul>
      ) : null}
      <div className="andalucia-election-program-card__links">
        {sourceLink(source.url, "PDF")}
        {sourceLink(source.page_url, "Página fuente")}
      </div>
    </article>
  );
}

function ProgramMeasureCard({ measure }) {
  const locator = measure.source_locator || {};
  return (
    <article className="andalucia-election-measure-card">
      <div className="andalucia-election-measure-card__head">
        <span className="andalucia-election-measure-card__party">{measure.party_acronym}</span>
        <span className="andalucia-election-measure-card__action">{actionLabel(measure.action_kind)}</span>
      </div>
      <p className="andalucia-election-measure-card__excerpt">{measure.evidence_excerpt}</p>
      <div className="andalucia-election-measure-card__meta">
        <span className="andalucia-election-measure-card__locator">
          p.{formatInt(locator.pdf_page)} · línea {formatInt(locator.text_line)}
        </span>
        <span className="andalucia-election-measure-card__tier">{measure.evidence_tier}</span>
      </div>
      <div className="andalucia-election-measure-card__links">
        {sourceLink(measure.source_url, "PDF")}
        {sourceLink(measure.source_page_url, "Fuente")}
      </div>
    </article>
  );
}

function ProgramMeasureTopicCard({ topic, measures }) {
  const topicMeasures = measures.filter((measure) => measure.topic_id === topic.topic_id);
  return (
    <article className="andalucia-election-measure-topic-card">
      <div className="andalucia-election-measure-topic-card__head">
        <p className="andalucia-election-measure-topic-card__eyebrow">Bloque programático</p>
        <h3 className="andalucia-election-measure-topic-card__title">
          {topic.topic_label || topicLabel(topic.topic_id)}
        </h3>
        <span className="andalucia-election-measure-topic-card__count">
          {formatInt(topic.measures_total)} medidas · {formatInt(topic.parties_total)} partidos
        </span>
      </div>
      <div className="andalucia-election-measure-card-list">
        {topicMeasures.slice(0, 8).map((measure) => (
          <ProgramMeasureCard measure={measure} key={measure.measure_id} />
        ))}
      </div>
    </article>
  );
}

function BojaNormTopicCard({ topic }) {
  const records = Array.isArray(topic.records) ? topic.records : [];
  return (
    <article className="andalucia-election-boja-topic-card">
      <div className="andalucia-election-boja-topic-card__head">
        <p className="andalucia-election-boja-topic-card__eyebrow">BOJA · {topic.query}</p>
        <h3 className="andalucia-election-boja-topic-card__title">
          {topicLabel(topic.topic_id) || topic.topic_label}
        </h3>
        <span className="andalucia-election-boja-topic-card__count">
          {formatInt(topic.records_total)} muestras · {formatInt(topic.fragments_total)} fragmentos ·{" "}
          {formatInt(topic.total_hits)} hits API
        </span>
      </div>
      <ul className="andalucia-election-boja-record-list">
        {records.slice(0, 4).map((record) => {
          const fragments = Array.isArray(record.fragments) ? record.fragments : [];
          return (
            <li className="andalucia-election-boja-record-list__item" key={`${topic.topic_id}-${record.boja_id}`}>
              <div className="andalucia-election-boja-record-list__meta">
                <span className="andalucia-election-boja-record-list__date">{record.date || "sin fecha"}</span>
                <span className="andalucia-election-boja-record-list__type">{record.type || "BOJA"}</span>
                <span className="andalucia-election-boja-record-list__action">
                  {bojaActionLabel(record.action_kind)}
                </span>
              </div>
              <p className="andalucia-election-boja-record-list__summary">
                {record.evidence_excerpt || record.summary}
              </p>
              {fragments.length ? (
                <ul className="andalucia-election-boja-fragment-list">
                  {fragments.slice(0, 2).map((fragment) => (
                    <li className="andalucia-election-boja-fragment-list__item" key={fragment.fragment_id}>
                      <span className="andalucia-election-boja-fragment-list__action">
                        {bojaActionLabel(fragment.action_kind)}
                      </span>
                      <span className="andalucia-election-boja-fragment-list__excerpt">
                        {fragment.evidence_excerpt}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : null}
              <span className="andalucia-election-boja-record-list__organisation">
                {record.organisation || "Junta de Andalucía"}
              </span>
              <div className="andalucia-election-boja-record-list__links">
                {sourceLink(record.source_url, "PDF BOJA")}
              </div>
            </li>
          );
        })}
      </ul>
    </article>
  );
}

function BojaImpactReviewCard({ item }) {
  const questions = Array.isArray(item.review_questions) ? item.review_questions : [];
  return (
    <article className="andalucia-election-impact-review-card">
      <div className="andalucia-election-impact-review-card__head">
        {item.priority_rank ? (
          <span className="andalucia-election-impact-review-card__rank">
            #{formatInt(item.priority_rank)}
          </span>
        ) : null}
        <span className="andalucia-election-impact-review-card__topic">{topicLabel(item.topic_id)}</span>
        <span className="andalucia-election-impact-review-card__action">
          {bojaActionLabel(item.action_kind)}
        </span>
      </div>
      <p className="andalucia-election-impact-review-card__excerpt">{item.evidence_excerpt}</p>
      <dl className="andalucia-election-impact-review-card__status-list">
        <div className="andalucia-election-impact-review-card__status-item">
          <dt className="andalucia-election-impact-review-card__status-label">Impacto</dt>
          <dd className="andalucia-election-impact-review-card__status-value">
            {impactReviewStatusLabel(item.impact_status)}
          </dd>
        </div>
        <div className="andalucia-election-impact-review-card__status-item">
          <dt className="andalucia-election-impact-review-card__status-label">Actor</dt>
          <dd className="andalucia-election-impact-review-card__status-value">
            {impactReviewStatusLabel(item.responsibility_status)}
          </dd>
        </div>
        <div className="andalucia-election-impact-review-card__status-item">
          <dt className="andalucia-election-impact-review-card__status-label">Dirección</dt>
          <dd className="andalucia-election-impact-review-card__status-value">
            {impactReviewStatusLabel(item.candidate_direction)}
          </dd>
        </div>
      </dl>
      <p className="andalucia-election-impact-review-card__hint">{item.review_hint}</p>
      {item.review_batch_id ? (
        <p className="andalucia-election-impact-review-card__batch">
          {item.review_batch_id} · prioridad {formatInt(item.priority_score)}
        </p>
      ) : null}
      <ul className="andalucia-election-impact-review-question-list">
        {questions.slice(0, 4).map((question) => {
          const questionId = question.question_id || question.question || question;
          const questionText = question.question || question;
          return (
            <li className="andalucia-election-impact-review-question-list__item" key={questionId}>
              <span className="andalucia-election-impact-review-question-list__text">
                {questionText}
              </span>
            </li>
          );
        })}
      </ul>
      <div className="andalucia-election-impact-review-card__links">
        {sourceLink(item.source_url, "PDF BOJA")}
        {sourceLink(item.detail_url, "Detalle API")}
      </div>
    </article>
  );
}

function BojaImpactReviewBatchCard({ batch }) {
  const topicCounts = Array.isArray(batch.topic_counts) ? batch.topic_counts : [];
  const actionCounts = Array.isArray(batch.action_counts) ? batch.action_counts : [];
  const items = Array.isArray(batch.items) ? batch.items : [];
  return (
    <article className="andalucia-election-review-batch-card">
      <div className="andalucia-election-review-batch-card__head">
        <span className="andalucia-election-review-batch-card__id">{batch.batch_id}</span>
        <span className="andalucia-election-review-batch-card__status">
          {impactReviewStatusLabel(batch.review_status)}
        </span>
      </div>
      <dl className="andalucia-election-review-batch-card__facts">
        <div className="andalucia-election-review-batch-card__fact">
          <dt>Items</dt>
          <dd>{formatInt(batch.items_total)}</dd>
        </div>
        <div className="andalucia-election-review-batch-card__fact">
          <dt>Rango</dt>
          <dd>
            {formatInt(batch.priority_rank_from)}-{formatInt(batch.priority_rank_to)}
          </dd>
        </div>
      </dl>
      <div className="andalucia-election-review-batch-card__count-groups">
        <div className="andalucia-election-review-batch-card__count-group">
          <span className="andalucia-election-review-batch-card__count-label">Bloques</span>
          <ul className="andalucia-election-review-batch-count-list">
            {topicCounts.slice(0, 4).map((row) => (
              <li className="andalucia-election-review-batch-count-list__item" key={row.key}>
                <span className="andalucia-election-review-batch-count-list__label">{row.label}</span>
                <span className="andalucia-election-review-batch-count-list__value">{formatInt(row.count)}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="andalucia-election-review-batch-card__count-group">
          <span className="andalucia-election-review-batch-card__count-label">Acciones</span>
          <ul className="andalucia-election-review-batch-count-list">
            {actionCounts.slice(0, 4).map((row) => (
              <li className="andalucia-election-review-batch-count-list__item" key={row.key}>
                <span className="andalucia-election-review-batch-count-list__label">{bojaActionLabel(row.key)}</span>
                <span className="andalucia-election-review-batch-count-list__value">{formatInt(row.count)}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <ol className="andalucia-election-review-batch-item-list">
        {items.slice(0, 3).map((item) => (
          <li className="andalucia-election-review-batch-item-list__item" key={item.review_item_id}>
            <span className="andalucia-election-review-batch-item-list__rank">
              #{formatInt(item.priority_rank)}
            </span>
            <span className="andalucia-election-review-batch-item-list__text">{item.evidence_excerpt}</span>
          </li>
        ))}
      </ol>
    </article>
  );
}

function ParliamentProponentCard({ row }) {
  return (
    <article className="andalucia-election-parliament-proponent-card">
      <span className="andalucia-election-parliament-proponent-card__count">{formatInt(row.count)}</span>
      <h3 className="andalucia-election-parliament-proponent-card__label">{row.label}</h3>
    </article>
  );
}

function ParliamentInitiativeCard({ initiative }) {
  const partyKeys = Array.isArray(initiative.proponent_party_keys) ? initiative.proponent_party_keys : [];
  return (
    <article className="andalucia-election-parliament-initiative-card">
      <div className="andalucia-election-parliament-initiative-card__head">
        <span className="andalucia-election-parliament-initiative-card__type">
          {initiative.type_label || initiative.type_code || "iniciativa"}
        </span>
        <span className="andalucia-election-parliament-initiative-card__date">
          {initiative.created_at || "sin fecha"}
        </span>
      </div>
      <h3 className="andalucia-election-parliament-initiative-card__title">
        {initiative.numexp || "expediente sin número"}
      </h3>
      <p className="andalucia-election-parliament-initiative-card__excerpt">
        {initiative.evidence_excerpt}
      </p>
      <dl className="andalucia-election-parliament-initiative-card__facts">
        <div className="andalucia-election-parliament-initiative-card__fact">
          <dt>Proponente</dt>
          <dd>{initiative.proponent || "sin dato"}</dd>
        </div>
        <div className="andalucia-election-parliament-initiative-card__fact">
          <dt>Tipo actor</dt>
          <dd>{parliamentProponentKindLabel(initiative.proponent_kind)}</dd>
        </div>
        <div className="andalucia-election-parliament-initiative-card__fact">
          <dt>Bloque</dt>
          <dd>{topicLabel(initiative.topic_id)}</dd>
        </div>
        <div className="andalucia-election-parliament-initiative-card__fact">
          <dt>Grupo explícito</dt>
          <dd>{partyKeys.length ? partyKeys.join(", ") : "sin grupo partidista explícito"}</dd>
        </div>
      </dl>
      <div className="andalucia-election-parliament-initiative-card__links">
        {sourceLink(initiative.source_url, "Expediente oficial")}
      </div>
    </article>
  );
}

function ParliamentVotingDocumentList({ documents }) {
  if (!Array.isArray(documents) || !documents.length) {
    return null;
  }
  return (
    <ul className="andalucia-election-parliament-vote-document-list">
      {documents.slice(0, 4).map((document) => (
        <li className="andalucia-election-parliament-vote-document-list__item" key={document.document_id}>
          <span className="andalucia-election-parliament-vote-document-list__date">
            {document.date || "sin fecha"}
          </span>
          {sourceLink(document.source_url, document.label || "Documento voto")}
        </li>
      ))}
    </ul>
  );
}

function ParliamentPartyVoteSummaryCard({ row }) {
  return (
    <article className="andalucia-election-parliament-party-vote-card">
      <div className="andalucia-election-parliament-party-vote-card__head">
        <h3 className="andalucia-election-parliament-party-vote-card__party">
          {row.party_label || row.party_acronym}
        </h3>
        <span className="andalucia-election-parliament-party-vote-card__count">
          {formatInt(row.vote_events_total)} votos
        </span>
      </div>
      <dl className="andalucia-election-parliament-party-vote-card__totals">
        <div className="andalucia-election-parliament-party-vote-card__total">
          <dt>Sí</dt>
          <dd>{formatInt(row.si)}</dd>
        </div>
        <div className="andalucia-election-parliament-party-vote-card__total">
          <dt>No</dt>
          <dd>{formatInt(row.no)}</dd>
        </div>
        <div className="andalucia-election-parliament-party-vote-card__total">
          <dt>Abs.</dt>
          <dd>{formatInt(row.abstenciones)}</dd>
        </div>
      </dl>
    </article>
  );
}

function ParliamentPartyTopicVoteCard({ row }) {
  const dominantCounts = Array.isArray(row.dominant_position_counts) ? row.dominant_position_counts : [];
  return (
    <article className="andalucia-election-parliament-party-topic-vote-card">
      <div className="andalucia-election-parliament-party-topic-vote-card__head">
        <h3 className="andalucia-election-parliament-party-topic-vote-card__party">
          {row.party_label || row.party_acronym}
        </h3>
        <span className="andalucia-election-parliament-party-topic-vote-card__topic">
          {topicLabel(row.topic_id)}
        </span>
        <span className="andalucia-election-parliament-party-topic-vote-card__count">
          {formatInt(row.vote_events_total)} votos enlazados
        </span>
      </div>
      <dl className="andalucia-election-parliament-party-topic-vote-card__totals">
        <div className="andalucia-election-parliament-party-topic-vote-card__total">
          <dt>Sí</dt>
          <dd>{formatInt(row.si)}</dd>
        </div>
        <div className="andalucia-election-parliament-party-topic-vote-card__total">
          <dt>No</dt>
          <dd>{formatInt(row.no)}</dd>
        </div>
        <div className="andalucia-election-parliament-party-topic-vote-card__total">
          <dt>Abs.</dt>
          <dd>{formatInt(row.abstenciones)}</dd>
        </div>
      </dl>
      <ul className="andalucia-election-parliament-party-topic-position-list">
        {dominantCounts.slice(0, 3).map((item) => (
          <li className="andalucia-election-parliament-party-topic-position-list__item" key={item.key}>
            <span className="andalucia-election-parliament-party-topic-position-list__label">
              {votePositionLabel(item.key)}
            </span>
            <span className="andalucia-election-parliament-party-topic-position-list__count">
              {formatInt(item.count)}
            </span>
          </li>
        ))}
      </ul>
      <p className="andalucia-election-parliament-party-topic-vote-card__note">
        Conteo por bloque enlazado a expediente oficial. No mide impacto ni mérito.
      </p>
    </article>
  );
}

function ParliamentLegalEffectSummaryCard({ row }) {
  const typeCounts = Array.isArray(row.initiative_type_counts) ? row.initiative_type_counts : [];
  const topicCounts = Array.isArray(row.topic_counts) ? row.topic_counts : [];
  const confidenceCounts = Array.isArray(row.confidence_counts) ? row.confidence_counts : [];
  return (
    <article className="andalucia-election-parliament-legal-effect-card">
      <div className="andalucia-election-parliament-legal-effect-card__head">
        <h3 className="andalucia-election-parliament-legal-effect-card__title">
          {legalEffectLabel(row.legal_effect_kind, row.legal_effect_label)}
        </h3>
        <span className="andalucia-election-parliament-legal-effect-card__count">
          {formatInt(row.vote_events_total)} votos
        </span>
      </div>
      <ul className="andalucia-election-parliament-legal-effect-tag-list">
        {typeCounts.slice(0, 3).map((item) => (
          <li className="andalucia-election-parliament-legal-effect-tag-list__item" key={item.key}>
            {item.label} · {formatInt(item.count)}
          </li>
        ))}
        {topicCounts.slice(0, 3).map((item) => (
          <li className="andalucia-election-parliament-legal-effect-tag-list__item" key={item.key}>
            {item.label} · {formatInt(item.count)}
          </li>
        ))}
        {confidenceCounts.slice(0, 1).map((item) => (
          <li className="andalucia-election-parliament-legal-effect-tag-list__item" key={item.key}>
            {legalEffectConfidenceLabel(item.key)} · {formatInt(item.count)}
          </li>
        ))}
      </ul>
      <p className="andalucia-election-parliament-legal-effect-card__note">
        Triaje por regla. No es impacto ciudadano ni mérito.
      </p>
    </article>
  );
}

function ParliamentVoteEventCard({ event }) {
  const partyVotes = Array.isArray(event.party_vote_totals) ? event.party_vote_totals : [];
  const matchedInitiative = event.initiative_match_status === "matched_official_initiative";
  const hasVoteContext = matchedInitiative || event.legal_effect_kind || event.topic_id || event.initiative_type_code;
  return (
    <article className="andalucia-election-parliament-vote-event-card">
      <div className="andalucia-election-parliament-vote-event-card__head">
        <span className="andalucia-election-parliament-vote-event-card__date">{event.date || "sin fecha"}</span>
        <span className="andalucia-election-parliament-vote-event-card__number">
          Voto {event.vote_number || "sin número"}
        </span>
        <span className="andalucia-election-parliament-vote-event-card__majority">
          {voteMajorityLabel(event.majority_side)}
        </span>
      </div>
      <h3 className="andalucia-election-parliament-vote-event-card__title">
        {event.numexp || "sin expediente enlazado"}
      </h3>
      <p className="andalucia-election-parliament-vote-event-card__summary">
        {event.title || "Votación sin título parseado"}
      </p>
      {hasVoteContext ? (
        <div className="andalucia-election-parliament-vote-event-card__context">
          <span className="andalucia-election-parliament-vote-event-card__type">
            {event.initiative_type_label || event.initiative_type_code || "expediente oficial"}
          </span>
          <span className="andalucia-election-parliament-vote-event-card__topic">
            {topicLabel(event.topic_id || event.initiative_topic_id)}
          </span>
          <span className="andalucia-election-parliament-vote-event-card__match">
            {matchedInitiative ? "expediente enlazado" : "tipo por expediente"}
          </span>
          <span className="andalucia-election-parliament-vote-event-card__effect">
            {legalEffectLabel(event.legal_effect_kind, event.legal_effect_label)}
          </span>
          <span className="andalucia-election-parliament-vote-event-card__topic-source">
            {topicSourceLabel(event.topic_source)}
          </span>
        </div>
      ) : null}
      <dl className="andalucia-election-parliament-vote-event-card__totals">
        <div className="andalucia-election-parliament-vote-event-card__total">
          <dt>Sí</dt>
          <dd>{formatInt(event.total_si)}</dd>
        </div>
        <div className="andalucia-election-parliament-vote-event-card__total">
          <dt>No</dt>
          <dd>{formatInt(event.total_no)}</dd>
        </div>
        <div className="andalucia-election-parliament-vote-event-card__total">
          <dt>Abs.</dt>
          <dd>{formatInt(event.total_abstenciones)}</dd>
        </div>
        <div className="andalucia-election-parliament-vote-event-card__total">
          <dt>Blancos</dt>
          <dd>{formatInt(event.total_blancos)}</dd>
        </div>
      </dl>
      <ul className="andalucia-election-parliament-vote-party-list">
        {partyVotes.slice(0, 5).map((row) => (
          <li className="andalucia-election-parliament-vote-party-list__item" key={row.party_key}>
            <span className="andalucia-election-parliament-vote-party-list__party">{row.party_acronym}</span>
            <span className="andalucia-election-parliament-vote-party-list__position">
              {votePositionLabel(row.dominant_position)}
            </span>
            <span className="andalucia-election-parliament-vote-party-list__count">Sí {formatInt(row.si)}</span>
            <span className="andalucia-election-parliament-vote-party-list__count">No {formatInt(row.no)}</span>
            <span className="andalucia-election-parliament-vote-party-list__count">
              Abs. {formatInt(row.abstenciones)}
            </span>
          </li>
        ))}
      </ul>
      <div className="andalucia-election-parliament-vote-event-card__links">
        {sourceLink(event.initiative_source_url, "Expediente")}
        {sourceLink(event.source_url, "PDF voto")}
      </div>
    </article>
  );
}

function ParliamentVoteReviewBatchCard({ batch }) {
  const topicCounts = Array.isArray(batch.topic_counts) ? batch.topic_counts : [];
  const typeCounts = Array.isArray(batch.initiative_type_counts) ? batch.initiative_type_counts : [];
  const items = Array.isArray(batch.items) ? batch.items : [];
  return (
    <article className="andalucia-election-parliament-review-batch-card andalucia-election-review-batch-card">
      <div className="andalucia-election-parliament-review-batch-card__head andalucia-election-review-batch-card__head">
        <span className="andalucia-election-parliament-review-batch-card__id andalucia-election-review-batch-card__id">
          {batch.batch_id}
        </span>
        <span className="andalucia-election-parliament-review-batch-card__status andalucia-election-review-batch-card__status">
          {impactReviewStatusLabel(batch.review_status)}
        </span>
      </div>
      <dl className="andalucia-election-parliament-review-batch-card__facts andalucia-election-review-batch-card__facts">
        <div className="andalucia-election-parliament-review-batch-card__fact andalucia-election-review-batch-card__fact">
          <dt>Votos</dt>
          <dd>{formatInt(batch.items_total)}</dd>
        </div>
        <div className="andalucia-election-parliament-review-batch-card__fact andalucia-election-review-batch-card__fact">
          <dt>Rango</dt>
          <dd>
            {formatInt(batch.priority_rank_from)}-{formatInt(batch.priority_rank_to)}
          </dd>
        </div>
      </dl>
      <div className="andalucia-election-parliament-review-batch-card__count-groups andalucia-election-review-batch-card__count-groups">
        <div className="andalucia-election-parliament-review-batch-card__count-group andalucia-election-review-batch-card__count-group">
          <span className="andalucia-election-parliament-review-batch-card__count-label andalucia-election-review-batch-card__count-label">
            Bloques
          </span>
          <ul className="andalucia-election-parliament-review-batch-count-list andalucia-election-review-batch-count-list">
            {topicCounts.slice(0, 4).map((row) => (
              <li className="andalucia-election-parliament-review-batch-count-list__item andalucia-election-review-batch-count-list__item" key={row.key}>
                <span className="andalucia-election-parliament-review-batch-count-list__label andalucia-election-review-batch-count-list__label">
                  {row.label}
                </span>
                <span className="andalucia-election-parliament-review-batch-count-list__value andalucia-election-review-batch-count-list__value">
                  {formatInt(row.count)}
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div className="andalucia-election-parliament-review-batch-card__count-group andalucia-election-review-batch-card__count-group">
          <span className="andalucia-election-parliament-review-batch-card__count-label andalucia-election-review-batch-card__count-label">
            Tipos
          </span>
          <ul className="andalucia-election-parliament-review-batch-count-list andalucia-election-review-batch-count-list">
            {typeCounts.slice(0, 4).map((row) => (
              <li className="andalucia-election-parliament-review-batch-count-list__item andalucia-election-review-batch-count-list__item" key={row.key}>
                <span className="andalucia-election-parliament-review-batch-count-list__label andalucia-election-review-batch-count-list__label">
                  {row.label}
                </span>
                <span className="andalucia-election-parliament-review-batch-count-list__value andalucia-election-review-batch-count-list__value">
                  {formatInt(row.count)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <ol className="andalucia-election-parliament-review-batch-item-list andalucia-election-review-batch-item-list">
        {items.slice(0, 3).map((item) => (
          <li className="andalucia-election-parliament-review-batch-item-list__item andalucia-election-review-batch-item-list__item" key={item.review_item_id}>
            <span className="andalucia-election-parliament-review-batch-item-list__rank andalucia-election-review-batch-item-list__rank">
              #{formatInt(item.priority_rank)}
            </span>
            <span className="andalucia-election-parliament-review-batch-item-list__text andalucia-election-review-batch-item-list__text">
              {item.numexp || item.title || "voto sin expediente"}
            </span>
          </li>
        ))}
      </ol>
    </article>
  );
}

function ParliamentVoteReviewCard({ item }) {
  const partyVotes = Array.isArray(item.party_vote_totals) ? item.party_vote_totals : [];
  const questions = Array.isArray(item.review_questions) ? item.review_questions : [];
  return (
    <article className="andalucia-election-parliament-vote-review-card andalucia-election-impact-review-card">
      <div className="andalucia-election-parliament-vote-review-card__head andalucia-election-impact-review-card__head">
        <span className="andalucia-election-parliament-vote-review-card__rank andalucia-election-impact-review-card__rank">
          #{formatInt(item.priority_rank)}
        </span>
        <span className="andalucia-election-parliament-vote-review-card__topic andalucia-election-impact-review-card__topic">
          {topicLabel(item.topic_id)}
        </span>
        <span className="andalucia-election-parliament-vote-review-card__type andalucia-election-impact-review-card__action">
          {item.initiative_type_label || item.initiative_type_code || "voto"}
        </span>
        <span className="andalucia-election-parliament-vote-review-card__majority andalucia-election-parliament-vote-event-card__majority">
          {voteMajorityLabel(item.majority_side)}
        </span>
      </div>
      <h3 className="andalucia-election-parliament-vote-review-card__title">
        {item.numexp || "sin expediente enlazado"}
      </h3>
      <p className="andalucia-election-parliament-vote-review-card__excerpt andalucia-election-impact-review-card__excerpt">
        {item.title || "Votación sin título parseado"}
      </p>
      <dl className="andalucia-election-parliament-vote-review-card__status-list andalucia-election-impact-review-card__status-list">
        <div className="andalucia-election-parliament-vote-review-card__status-item andalucia-election-impact-review-card__status-item">
          <dt className="andalucia-election-parliament-vote-review-card__status-label andalucia-election-impact-review-card__status-label">
            Efecto
          </dt>
          <dd className="andalucia-election-parliament-vote-review-card__status-value andalucia-election-impact-review-card__status-value">
            <span className="andalucia-election-parliament-vote-review-card__effect-label">
              {legalEffectLabel(item.legal_effect_kind, item.legal_effect_label)}
            </span>
            <span className="andalucia-election-parliament-vote-review-card__effect-status">
              {impactReviewStatusLabel(item.legal_effect_status)} · {legalEffectConfidenceLabel(item.legal_effect_confidence)}
            </span>
          </dd>
        </div>
        <div className="andalucia-election-parliament-vote-review-card__status-item andalucia-election-impact-review-card__status-item">
          <dt className="andalucia-election-parliament-vote-review-card__status-label andalucia-election-impact-review-card__status-label">
            Actor
          </dt>
          <dd className="andalucia-election-parliament-vote-review-card__status-value andalucia-election-impact-review-card__status-value">
            {impactReviewStatusLabel(item.responsibility_status)}
          </dd>
        </div>
        <div className="andalucia-election-parliament-vote-review-card__status-item andalucia-election-impact-review-card__status-item">
          <dt className="andalucia-election-parliament-vote-review-card__status-label andalucia-election-impact-review-card__status-label">
            Impacto
          </dt>
          <dd className="andalucia-election-parliament-vote-review-card__status-value andalucia-election-impact-review-card__status-value">
            {impactReviewStatusLabel(item.impact_status)}
          </dd>
        </div>
      </dl>
      <ul className="andalucia-election-parliament-vote-review-party-list andalucia-election-parliament-vote-party-list">
        {partyVotes.slice(0, 5).map((row) => (
          <li className="andalucia-election-parliament-vote-review-party-list__item andalucia-election-parliament-vote-party-list__item" key={row.party_key}>
            <span className="andalucia-election-parliament-vote-review-party-list__party andalucia-election-parliament-vote-party-list__party">
              {row.party_acronym}
            </span>
            <span className="andalucia-election-parliament-vote-review-party-list__position andalucia-election-parliament-vote-party-list__position">
              {votePositionLabel(row.dominant_position)}
            </span>
            <span className="andalucia-election-parliament-vote-review-party-list__count andalucia-election-parliament-vote-party-list__count">
              Sí {formatInt(row.si)}
            </span>
            <span className="andalucia-election-parliament-vote-review-party-list__count andalucia-election-parliament-vote-party-list__count">
              No {formatInt(row.no)}
            </span>
          </li>
        ))}
      </ul>
      <p className="andalucia-election-parliament-vote-review-card__hint andalucia-election-impact-review-card__hint">
        {item.review_hint}
      </p>
      <ol className="andalucia-election-parliament-vote-review-question-list andalucia-election-impact-review-question-list">
        {questions.slice(0, 4).map((question) => (
          <li className="andalucia-election-parliament-vote-review-question-list__item andalucia-election-impact-review-question-list__item" key={question.question_id}>
            <span className="andalucia-election-parliament-vote-review-question-list__text andalucia-election-impact-review-question-list__text">
              {question.question}
            </span>
          </li>
        ))}
      </ol>
      <div className="andalucia-election-parliament-vote-review-card__links andalucia-election-impact-review-card__links">
        {sourceLink(item.initiative_source_url, "Expediente")}
        {sourceLink(item.source_url, "PDF voto")}
      </div>
      <span className="andalucia-election-parliament-vote-review-card__batch andalucia-election-impact-review-card__batch">
        {item.review_batch_id}
      </span>
    </article>
  );
}

function ReviewedBojaImpactList({ items }) {
  const rows = Array.isArray(items) ? items.filter((item) => item.review_status) : [];
  if (!rows.length) {
    return null;
  }
  return (
    <div className="andalucia-election-reviewed-boja-impact">
      <div className="andalucia-election-reviewed-boja-impact__head">
        <strong className="andalucia-election-reviewed-boja-impact__title">
          Cambios BOJA revisados
        </strong>
        <span className="andalucia-election-reviewed-boja-impact__status">
          {formatInt(rows.length)} sin mérito/culpa
        </span>
      </div>
      <div className="andalucia-election-reviewed-boja-impact__grid">
        {rows.slice(0, 6).map((item) => (
          <article className="andalucia-election-reviewed-boja-impact-card" key={item.review_item_id}>
            <div className="andalucia-election-reviewed-boja-impact-card__head">
              <span className="andalucia-election-reviewed-boja-impact-card__topic">
                {topicLabel(item.topic_id)}
              </span>
              <span className="andalucia-election-reviewed-boja-impact-card__action">
                {bojaActionLabel(item.action_kind)}
              </span>
            </div>
            <h3 className="andalucia-election-reviewed-boja-impact-card__title">
              {item.reviewed_legal_change_label || "Cambio legal revisado"}
            </h3>
            <p className="andalucia-election-reviewed-boja-impact-card__summary">
              {item.review_summary || item.evidence_excerpt}
            </p>
            <dl className="andalucia-election-reviewed-boja-impact-card__facts">
              <div className="andalucia-election-reviewed-boja-impact-card__fact">
                <dt>Impacto</dt>
                <dd>{impactReviewStatusLabel(item.impact_status)}</dd>
              </div>
              <div className="andalucia-election-reviewed-boja-impact-card__fact">
                <dt>Actor</dt>
                <dd>{impactReviewStatusLabel(item.responsibility_status)}</dd>
              </div>
              <div className="andalucia-election-reviewed-boja-impact-card__fact">
                <dt>Dirección</dt>
                <dd>{impactReviewStatusLabel(item.candidate_direction)}</dd>
              </div>
            </dl>
            <p className="andalucia-election-reviewed-boja-impact-card__excerpt">
              {item.evidence_excerpt}
            </p>
            <div className="andalucia-election-reviewed-boja-impact-card__links">
              {sourceLink(item.source_url, "PDF BOJA")}
            </div>
          </article>
        ))}
      </div>
      <p className="andalucia-election-reviewed-boja-impact__note">
        Revisión solo de cambio legal oficial. Quedan pendientes dirección ciudadana, ejecución, dinero y resultados.
      </p>
    </div>
  );
}

function CandidateList({ list, candidatesByList }) {
  const rows = candidatesByList.get(list.list_id) || [];
  return (
    <details className="andalucia-election-list-row">
      <summary className="andalucia-election-list-row__summary">
        <span className="andalucia-election-list-row__party">{list.party_acronym}</span>
        <span className="andalucia-election-list-row__province">{list.province}</span>
        <span className="andalucia-election-list-row__count">{formatInt(rows.length)} candidatos</span>
      </summary>
      <ol className="andalucia-election-candidate-list">
        {rows.map((candidate) => (
          <li className="andalucia-election-candidate-list__item" key={candidate.candidate_id}>
            <span className="andalucia-election-candidate-list__position">
              {candidate.candidate_type === "suplente" ? "S" : candidate.list_position}
            </span>
            <span className="andalucia-election-candidate-list__name">{candidate.person_name}</span>
            <span className="andalucia-election-candidate-list__status">
              {matchLabel(candidate.person_match_status)}
            </span>
            <span className="andalucia-election-candidate-list__evidence-status">
              {accountabilityStatusLabel(candidate.accountability_evidence_status)}
            </span>
          </li>
        ))}
      </ol>
    </details>
  );
}

export default function Andalucia2026ElectionPage() {
  const payload = readPublicJson("elecciones/andalucia-2026/data/accountability.json", {});
  const deliveryHuntResults = readPublicJson(
    "elecciones/andalucia-2026/data/delivery-evidence-hunt-results.json",
    {},
  );
  const deliveryReviewDrafts = readPublicJson(
    "elecciones/andalucia-2026/data/delivery-evidence-review-drafts.json",
    {},
  );
  const coverage = payload.coverage || {};
  const election = payload.election || {};
  const source = Array.isArray(payload.sources) ? payload.sources[0] || {} : {};
  const parties = Array.isArray(payload.parties) ? payload.parties : [];
  const focusCandidates = Array.isArray(payload.focus_candidates) ? payload.focus_candidates : [];
  const lists = Array.isArray(payload.candidate_lists) ? payload.candidate_lists : [];
  const candidates = Array.isArray(payload.candidates) ? payload.candidates : [];
  const lanes = Array.isArray(payload.evidence_lanes) ? payload.evidence_lanes : [];
  const programSources = Array.isArray(payload.program_sources?.sources) ? payload.program_sources.sources : [];
  const programMeasures = Array.isArray(payload.program_sources?.measures) ? payload.program_sources.measures : [];
  const programMeasureTopics = Array.isArray(payload.program_sources?.measures_by_topic)
    ? payload.program_sources.measures_by_topic
    : [];
  const parliamentActivity = payload.parliament_activity || {};
  const parliamentInitiatives = Array.isArray(parliamentActivity.legislative_initiatives)
    ? parliamentActivity.legislative_initiatives
    : [];
  const parliamentProponents = Array.isArray(parliamentActivity.legislative_initiatives_by_proponent)
    ? parliamentActivity.legislative_initiatives_by_proponent
    : [];
  const parliamentVotingDocuments = Array.isArray(parliamentActivity.voting_documents)
    ? parliamentActivity.voting_documents
    : [];
  const parliamentVoteEvents = Array.isArray(parliamentActivity.vote_events) ? parliamentActivity.vote_events : [];
  const parliamentPartyVoteSummaries = Array.isArray(parliamentActivity.vote_events_by_party_position)
    ? parliamentActivity.vote_events_by_party_position
    : [];
  const parliamentPartyTopicVoteSummaries = Array.isArray(parliamentActivity.vote_events_by_party_topic)
    ? parliamentActivity.vote_events_by_party_topic
    : [];
  const parliamentLegalEffectSummaries = Array.isArray(parliamentActivity.vote_events_by_legal_effect)
    ? parliamentActivity.vote_events_by_legal_effect
    : [];
  const parliamentReviewedPartyVoteSummaries = Array.isArray(parliamentActivity.reviewed_vote_events_by_party)
    ? parliamentActivity.reviewed_vote_events_by_party
    : [];
  const parliamentReviewedCandidateVoteSummaries = Array.isArray(parliamentActivity.reviewed_candidate_vote_summaries)
    ? parliamentActivity.reviewed_candidate_vote_summaries
    : [];
  const parliamentVoteReviewQueue = Array.isArray(parliamentActivity.vote_impact_review_queue)
    ? parliamentActivity.vote_impact_review_queue
    : [];
  const responsibilityComparison = payload.responsibility_comparison || {};
  const issueAccountabilityPackets = payload.issue_accountability_packets || {};
  const issueAccountabilityReviews = payload.issue_accountability_reviews || {};
  const issueExecutionEvidenceQueue = payload.issue_execution_evidence_queue || {};
  const accountabilityReadiness = payload.accountability_readiness || {};
  const postChangeOutcomeMonitor = payload.post_change_outcome_monitor || {};
  const publishedAccountabilityClaims = payload.published_accountability_claims || {};
  const parliamentVoteReviewPacket = parliamentActivity.vote_impact_review_packet || {};
  const parliamentVoteReviewBatches = Array.isArray(parliamentVoteReviewPacket.batches)
    ? parliamentVoteReviewPacket.batches
    : [];
  const bojaNorms = payload.boja_norms || {};
  const bojaTopics = Array.isArray(bojaNorms.topics) ? bojaNorms.topics : [];
  const bojaImpactReviewQueue = Array.isArray(bojaNorms.impact_review_queue)
    ? bojaNorms.impact_review_queue
    : [];
  const bojaReviewedImpactItems = Array.isArray(bojaNorms.reviewed_impact_items)
    ? bojaNorms.reviewed_impact_items
    : [];
  const bojaImpactReviewPacket = bojaNorms.impact_review_packet || {};
  const bojaImpactReviewBatches = Array.isArray(bojaImpactReviewPacket.batches)
    ? bojaImpactReviewPacket.batches
    : [];
  const bojaImpactReviewQueueCsvHref = withBasePath(
    "/elecciones/andalucia-2026/data/boja-impact-review-queue.csv"
  );
  const parliamentVoteReviewQueueCsvHref = withBasePath(
    "/elecciones/andalucia-2026/data/parliament-vote-impact-review-queue.csv"
  );
  const executionEvidenceQueueCsvHref = withBasePath(
    "/elecciones/andalucia-2026/data/execution-evidence-queue.csv"
  );
  const candidatesByList = new Map();
  for (const candidate of candidates) {
    if (!candidatesByList.has(candidate.list_id)) {
      candidatesByList.set(candidate.list_id, []);
    }
    candidatesByList.get(candidate.list_id).push(candidate);
  }

  return (
    <main className="andalucia-election-page">
      <section className="andalucia-election-hero" aria-labelledby="andalucia-election-title">
        <div className="andalucia-election-hero__copy">
          <p className="andalucia-election-hero__eyebrow">Elecciones autonómicas · Andalucía</p>
          <h1 className="andalucia-election-hero__title" id="andalucia-election-title">
            Andalucía 2026: partidos, candidatos y evidencia
          </h1>
          <p className="andalucia-election-hero__summary">
            Primera superficie dedicada: candidaturas oficiales completas, programas 2026, historial scrapeado cuando
            hay enlace conservador y primeras señales de voto legislativo revisadas sin atribuir méritos, culpa o
            impacto real.
          </p>
          <div className="andalucia-election-hero__links">
            {sourceLink(source.url, "PDF oficial JEC")}
            {sourceLink(source.boja_url, "PDF BOJA")}
            {sourceLink(source.page_url, "Página electoral")}
          </div>
        </div>
        <dl className="andalucia-election-hero__facts">
          <div className="andalucia-election-hero__fact">
            <dt>Votación</dt>
            <dd>{election.date || "sin fecha"}</dd>
          </div>
          <div className="andalucia-election-hero__fact">
            <dt>Escaños</dt>
            <dd>{formatInt(election.seats || 0)}</dd>
          </div>
          <div className="andalucia-election-hero__fact">
            <dt>Estado</dt>
            <dd>{election.status || "sin dato"}</dd>
          </div>
        </dl>
      </section>

      <section className="andalucia-election-metrics" aria-label="Cobertura del corte">
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Provincias</span>
          <strong className="andalucia-election-metric__value">{formatInt(coverage.provinces_total)}</strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Listas</span>
          <strong className="andalucia-election-metric__value">{formatInt(coverage.candidate_lists_total)}</strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Partidos</span>
          <strong className="andalucia-election-metric__value">{formatInt(coverage.distinct_party_keys_total)}</strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Candidatos</span>
          <strong className="andalucia-election-metric__value">
            {formatInt((coverage.titular_candidates_total || 0) + (coverage.suplente_candidates_total || 0))}
          </strong>
        </div>
        <div className="andalucia-election-metric andalucia-election-metric--warning">
          <span className="andalucia-election-metric__label">Valoraciones publicadas</span>
          <strong className="andalucia-election-metric__value">
            {formatInt(coverage.published_merit_blame_claims_total)}
          </strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Claims responsabilidad</span>
          <strong className="andalucia-election-metric__value">
            {formatInt(coverage.published_accountability_claims_total)}
          </strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Issues revisados</span>
          <strong className="andalucia-election-metric__value">
            {formatInt(coverage.issue_accountability_reviewed_issues_total)}
          </strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Ejecutor enlazado</span>
          <strong className="andalucia-election-metric__value">
            {formatInt(coverage.issue_accountability_execution_owner_reviewed_total)}
          </strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Programas texto</span>
          <strong className="andalucia-election-metric__value">
            {formatInt(coverage.program_sources_text_extracted_total)}
          </strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Programas verificados</span>
          <strong className="andalucia-election-metric__value">
            {formatInt(coverage.program_sources_verified_total)}
          </strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Medidas declaradas</span>
          <strong className="andalucia-election-metric__value">
            {formatInt(coverage.program_measures_total)}
          </strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Iniciativas Parlamento</span>
          <strong className="andalucia-election-metric__value">
            {formatInt(coverage.parliament_andalucia_legislative_initiatives_total)}
          </strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Docs voto Pleno</span>
          <strong className="andalucia-election-metric__value">
            {formatInt(coverage.parliament_andalucia_voting_documents_total)}
          </strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Votaciones extraídas</span>
          <strong className="andalucia-election-metric__value">
            {formatInt(coverage.parliament_andalucia_parsed_vote_events_total)}
          </strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Votos con expediente</span>
          <strong className="andalucia-election-metric__value">
            {formatInt(coverage.parliament_andalucia_vote_events_with_official_initiative_total)}
          </strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Triaje efecto legal</span>
          <strong className="andalucia-election-metric__value">
            {formatInt(coverage.parliament_andalucia_vote_events_with_legal_effect_triage_total)}
          </strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Cola votos impacto</span>
          <strong className="andalucia-election-metric__value">
            {formatInt(coverage.parliament_andalucia_vote_impact_review_items_total)}
          </strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Votos revisados</span>
          <strong className="andalucia-election-metric__value">
            {formatInt(coverage.parliament_andalucia_reviewed_vote_items_total)}
          </strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Candidatos con señales</span>
          <strong className="andalucia-election-metric__value">
            {formatInt(coverage.parliament_andalucia_reviewed_candidate_vote_summaries_total)}
          </strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Perfiles responsabilidad</span>
          <strong className="andalucia-election-metric__value">
            {formatInt(coverage.responsibility_party_profiles_total)}
          </strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Bloques issue</span>
          <strong className="andalucia-election-metric__value">
            {formatInt(coverage.issue_accountability_packets_total)}
          </strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Issue con voto</span>
          <strong className="andalucia-election-metric__value">
            {formatInt(coverage.issue_accountability_packets_with_reviewed_vote_total)}
          </strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Focos atribuibles</span>
          <strong className="andalucia-election-metric__value">
            {formatInt(coverage.responsibility_focus_candidate_profiles_total)}
          </strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Candidatos con voto nominal</span>
          <strong className="andalucia-election-metric__value">
            {formatInt(coverage.parliament_andalucia_candidates_with_member_votes_total)}
          </strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Candidatos con historial</span>
          <strong className="andalucia-election-metric__value">
            {formatInt(coverage.candidates_with_accountability_evidence_total)}
          </strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Registros BOJA</span>
          <strong className="andalucia-election-metric__value">
            {formatInt(coverage.boja_norms_records_total)}
          </strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Fragmentos BOJA</span>
          <strong className="andalucia-election-metric__value">
            {formatInt(coverage.boja_norms_fragments_total)}
          </strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Cola impacto BOJA</span>
          <strong className="andalucia-election-metric__value">
            {formatInt(coverage.boja_norms_impact_review_items_total)}
          </strong>
        </div>
        <div className="andalucia-election-metric">
          <span className="andalucia-election-metric__label">Lotes revisión BOJA</span>
          <strong className="andalucia-election-metric__value">
            {formatInt(coverage.boja_norms_impact_review_batches_total)}
          </strong>
        </div>
      </section>

      <AccountabilityReadinessSection
        readinessReport={accountabilityReadiness}
        deliveryHuntResults={deliveryHuntResults}
        deliveryReviewDrafts={deliveryReviewDrafts}
      />

      <PostChangeOutcomeMonitorSection monitor={postChangeOutcomeMonitor} />

      <ResponsibilityComparisonSection comparison={responsibilityComparison} />

      <PublishedAccountabilityClaimsSection claimsReport={publishedAccountabilityClaims} />

      <IssueReviewsSection reviewsReport={issueAccountabilityReviews} />

      <ExecutionEvidenceQueueSection
        queueReport={issueExecutionEvidenceQueue}
        csvHref={executionEvidenceQueueCsvHref}
      />

      <IssueAccountabilityPacketsSection packetsReport={issueAccountabilityPackets} />

      <section className="andalucia-election-section" aria-labelledby="andalucia-reviewed-comparison-title">
        <div className="andalucia-election-section__head">
          <p className="andalucia-election-section__eyebrow">Comparador revisado</p>
          <h2 className="andalucia-election-section__title" id="andalucia-reviewed-comparison-title">
            Señal legislativa por partido y candidato
          </h2>
          <p className="andalucia-election-section__summary">
            Primer lote con resultado oficial revisado. Compara posiciones observadas, no impacto ciudadano ni
            valoración moral.
          </p>
        </div>
        {parliamentReviewedPartyVoteSummaries.length ? (
          <div className="andalucia-election-reviewed-legislative-party-grid">
            {parliamentReviewedPartyVoteSummaries.slice(0, 5).map((summary) => (
              <ReviewedLegislativePartyCard summary={summary} key={summary.party_key} />
            ))}
          </div>
        ) : null}
        <ReviewedLegislativeCandidateComparison summaries={parliamentReviewedCandidateVoteSummaries} />
      </section>

      <section className="andalucia-election-section" aria-labelledby="andalucia-focus-title">
        <div className="andalucia-election-section__head">
          <p className="andalucia-election-section__eyebrow">Candidatos foco</p>
          <h2 className="andalucia-election-section__title" id="andalucia-focus-title">
            Primeros perfiles a auditar
          </h2>
          <p className="andalucia-election-section__summary">
            En este corte se muestra identidad oficial, programa e historial publicado cuando hay enlace conservador.
            Nada de ranking moral sin datos primarios.
          </p>
        </div>
        <div className="andalucia-election-candidate-grid">
          {focusCandidates.map((candidate) => (
            <FocusCandidateCard candidate={candidate} key={candidate.focus_id} />
          ))}
        </div>
      </section>

      <section className="andalucia-election-section" aria-labelledby="andalucia-parties-title">
        <div className="andalucia-election-section__head">
          <p className="andalucia-election-section__eyebrow">Partidos</p>
          <h2 className="andalucia-election-section__title" id="andalucia-parties-title">
            Listas proclamadas y backbone actual
          </h2>
        </div>
        <div className="andalucia-election-party-table">
          {parties.map((party) => (
            <PartyRow party={party} key={party.party_key} />
          ))}
        </div>
      </section>

      <section className="andalucia-election-section" aria-labelledby="andalucia-programs-title">
        <div className="andalucia-election-section__head">
          <p className="andalucia-election-section__eyebrow">Programas 2026</p>
          <h2 className="andalucia-election-section__title" id="andalucia-programs-title">
            Fuentes declarativas listas para extracción
          </h2>
          <p className="andalucia-election-section__summary">
            Estos documentos aún no son conclusiones. Son texto bruto verificable para extraer medidas, agrupar por
            bloques y cruzar después con BOJA, votos, presupuestos y resultados.
          </p>
        </div>
        <div className="andalucia-election-program-grid">
          {programSources.map((source) => (
            <ProgramSourceCard source={source} key={source.source_id} />
          ))}
        </div>
      </section>

      <section className="andalucia-election-section" aria-labelledby="andalucia-measures-title">
        <div className="andalucia-election-section__head">
          <p className="andalucia-election-section__eyebrow">Medidas declaradas</p>
          <h2 className="andalucia-election-section__title" id="andalucia-measures-title">
            Qué dicen que harán, separado por bloque
          </h2>
          <p className="andalucia-election-section__summary">
            Extracción automática conservadora desde programas. Sirve como promesa trazable; impacto, dirección y
            responsabilidad quedan pendientes de revisión y cruce con fuentes primarias.
          </p>
        </div>
        <div className="andalucia-election-measure-topic-grid">
          {programMeasureTopics.map((topic) => (
            <ProgramMeasureTopicCard
              measures={programMeasures}
              topic={topic}
              key={topic.topic_id}
            />
          ))}
        </div>
      </section>

      <section className="andalucia-election-section" aria-labelledby="andalucia-parliament-title">
        <div className="andalucia-election-section__head">
          <p className="andalucia-election-section__eyebrow">Parlamento 2022-2026</p>
          <h2 className="andalucia-election-section__title" id="andalucia-parliament-title">
            Qué entró, qué se votó y qué falta revisar
          </h2>
          <p className="andalucia-election-section__summary">
            Índice oficial de actividad legislativa de la XII legislatura. Muestra proponentes y expedientes
            trazables, conteos brutos por grupo y el primer lote de resultados de votación revisados. Responsabilidad,
            mérito e impacto quedan pendientes hasta revisar ejecución y resultados.
          </p>
        </div>
        <div className="andalucia-election-parliament-legal-effect-grid">
          {parliamentLegalEffectSummaries.slice(0, 8).map((row) => (
            <ParliamentLegalEffectSummaryCard row={row} key={row.legal_effect_kind} />
          ))}
        </div>
        <div className="andalucia-election-parliament-party-vote-grid">
          {parliamentPartyVoteSummaries.slice(0, 5).map((row) => (
            <ParliamentPartyVoteSummaryCard row={row} key={row.party_key} />
          ))}
        </div>
        <div className="andalucia-election-parliament-party-topic-vote-grid">
          {parliamentPartyTopicVoteSummaries.slice(0, 10).map((row) => (
            <ParliamentPartyTopicVoteCard row={row} key={`${row.party_key}-${row.topic_id}`} />
          ))}
        </div>
        <div className="andalucia-election-parliament-vote-event-grid">
          {parliamentVoteEvents.slice(0, 6).map((event) => (
            <ParliamentVoteEventCard event={event} key={event.vote_event_id} />
          ))}
        </div>
        <div className="andalucia-election-parliament-proponent-grid">
          {parliamentProponents.slice(0, 6).map((row) => (
            <ParliamentProponentCard row={row} key={row.key} />
          ))}
        </div>
        <div className="andalucia-election-parliament-initiative-grid">
          {parliamentInitiatives.slice(0, 9).map((initiative) => (
            <ParliamentInitiativeCard initiative={initiative} key={initiative.initiative_id} />
          ))}
        </div>
        <div className="andalucia-election-parliament-vote-document-block">
          <h3 className="andalucia-election-parliament-vote-document-block__title">
            Últimos documentos de voto publicados
          </h3>
          <ParliamentVotingDocumentList documents={parliamentVotingDocuments} />
        </div>
      </section>

      <section className="andalucia-election-section" aria-labelledby="andalucia-parliament-vote-review-title">
        <div className="andalucia-election-section__head">
          <p className="andalucia-election-section__eyebrow">Cola voto-impacto</p>
          <h2 className="andalucia-election-section__title" id="andalucia-parliament-vote-review-title">
            Votaciones que faltan revisar antes de atribuir responsabilidad
          </h2>
          <p className="andalucia-election-section__summary">
            Cada votación oficial queda separada en efecto legal, actor responsable, dirección ciudadana e impacto.
            Los lotes ordenan revisión; no son ranking ni valoración política.
          </p>
          <div className="andalucia-election-section__links">
            {sourceLink(parliamentVoteReviewQueueCsvHref, "CSV revisión votos")}
          </div>
        </div>
        {parliamentVoteReviewBatches.length ? (
          <div className="andalucia-election-parliament-review-batch-grid andalucia-election-review-batch-grid">
            {parliamentVoteReviewBatches.slice(0, 3).map((batch) => (
              <ParliamentVoteReviewBatchCard batch={batch} key={batch.batch_id} />
            ))}
          </div>
        ) : null}
        <div className="andalucia-election-parliament-vote-review-grid andalucia-election-impact-review-grid">
          {parliamentVoteReviewQueue.slice(0, 12).map((item) => (
            <ParliamentVoteReviewCard item={item} key={item.review_item_id} />
          ))}
        </div>
      </section>

      <section className="andalucia-election-section" aria-labelledby="andalucia-boja-title">
        <div className="andalucia-election-section__head">
          <p className="andalucia-election-section__eyebrow">BOJA 2022-2026</p>
          <h2 className="andalucia-election-section__title" id="andalucia-boja-title">
            Qué se publicó oficialmente durante la legislatura
          </h2>
          <p className="andalucia-election-section__summary">
            Primer scraper oficial por bloques: registros BOJA de disposiciones generales y fragmentos de detalle. Son
            evidencia primaria para revisar dirección legal, pero todavía no resumen impacto ni atribuyen culpa.
          </p>
        </div>
        <div className="andalucia-election-boja-topic-grid">
          {bojaTopics.filter((topic) => Number(topic.records_total || 0) > 0).map((topic) => (
            <BojaNormTopicCard topic={topic} key={topic.topic_id} />
          ))}
        </div>
        <ReviewedBojaImpactList items={bojaReviewedImpactItems} />
      </section>

      <section className="andalucia-election-section" aria-labelledby="andalucia-impact-review-title">
        <div className="andalucia-election-section__head">
          <p className="andalucia-election-section__eyebrow">Cola BOJA</p>
          <h2 className="andalucia-election-section__title" id="andalucia-impact-review-title">
            Impacto legal pendiente de revisión
          </h2>
          <p className="andalucia-election-section__summary">
            Cada fragmento oficial queda separado en preguntas de dirección, actor responsable, ejecución e impacto.
            Los lotes ordenan revisión humana; la cola aún no atribuye mérito, culpa ni resultado.
          </p>
          <div className="andalucia-election-section__links">
            {sourceLink(bojaImpactReviewQueueCsvHref, "CSV revisión BOJA")}
          </div>
        </div>
        {bojaImpactReviewBatches.length ? (
          <div className="andalucia-election-review-batch-grid">
            {bojaImpactReviewBatches.slice(0, 3).map((batch) => (
              <BojaImpactReviewBatchCard batch={batch} key={batch.batch_id} />
            ))}
          </div>
        ) : null}
        <div className="andalucia-election-impact-review-grid">
          {bojaImpactReviewQueue.slice(0, 12).map((item) => (
            <BojaImpactReviewCard item={item} key={item.review_item_id} />
          ))}
        </div>
      </section>

      <section className="andalucia-election-section" aria-labelledby="andalucia-lanes-title">
        <div className="andalucia-election-section__head">
          <p className="andalucia-election-section__eyebrow">Qué falta para culpas y méritos</p>
          <h2 className="andalucia-election-section__title" id="andalucia-lanes-title">
            Scrapers y capas necesarias
          </h2>
        </div>
        <div className="andalucia-election-lane-grid">
          {lanes.map((lane) => (
            <article className="andalucia-election-lane-card" key={lane.lane_id}>
              <span className="andalucia-election-lane-card__status">{laneLabel(lane.status)}</span>
              <h3 className="andalucia-election-lane-card__title">{lane.label}</h3>
              <p className="andalucia-election-lane-card__need">{lane.needed_for}</p>
              <p className="andalucia-election-lane-card__action">{lane.next_action}</p>
              <span className="andalucia-election-lane-card__tier">{lane.evidence_tier}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="andalucia-election-section" aria-labelledby="andalucia-full-list-title">
        <div className="andalucia-election-section__head">
          <p className="andalucia-election-section__eyebrow">Censo de candidatura</p>
          <h2 className="andalucia-election-section__title" id="andalucia-full-list-title">
            Todas las listas y candidatos
          </h2>
        </div>
        <div className="andalucia-election-full-list">
          {lists.map((list) => (
            <CandidateList candidatesByList={candidatesByList} list={list} key={list.list_id} />
          ))}
        </div>
      </section>

      <section className="andalucia-election-method" aria-label="Método">
        <p className="andalucia-election-method__text">{payload.method?.claim_rule}</p>
        <p className="andalucia-election-method__text">{payload.method?.law_change_rule}</p>
        <p className="andalucia-election-method__text">{payload.method?.press_rule}</p>
      </section>
    </main>
  );
}
