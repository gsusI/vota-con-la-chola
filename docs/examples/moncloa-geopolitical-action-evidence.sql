-- Real official path: actor -> foreign-policy action -> procedural stage -> evidence.
-- This query does not claim signature, ratification, entry into force,
-- implementation, alignment, influence, or outcome.
SELECT
  actor.source_label AS actor,
  actor.actor_role,
  action.action_date,
  action.action_kind,
  action.action_status,
  action.procedure_stage,
  action.instrument_name,
  action.binding_state,
  action.entry_into_force_state,
  action.implementation_state,
  action.outcome_state,
  evidence.exact_quote,
  evidence.source_url,
  evidence.content_sha256
FROM geopolitical_action_actors AS actor
JOIN geopolitical_actions AS action
  ON action.geopolitical_action_id = actor.geopolitical_action_id
JOIN geopolitical_action_evidence AS evidence
  ON evidence.geopolitical_action_id = action.geopolitical_action_id
WHERE actor.actor_role IN (
  'acting_state',
  'counterparty_state',
  'counterparty_organization'
)
ORDER BY action.action_date, actor.actor_ordinal;
