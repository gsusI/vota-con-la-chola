function normalizeFilterText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
}

function toInt(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function resolveExactTopicFilterSelection(topics, rawValue) {
  const needle = normalizeFilterText(rawValue);
  if (!needle || !Array.isArray(topics)) {
    return null;
  }

  for (const topic of topics) {
    const topicId = toInt(topic?.topic_id || topic?.topicId);
    if (!topicId) {
      continue;
    }
    const label = String(topic?.label || topic?.topic_label || "").trim();
    const key = String(topic?.key || topic?.topic_key || "").trim();
    if (needle === normalizeFilterText(label) || needle === normalizeFilterText(key)) {
      return {
        topicId,
        label,
        key,
      };
    }
  }

  return null;
}

export function topicFilterMatches({
  rawFilter,
  resolvedTopic,
  topicId,
  topicKey,
  topicLabel,
}) {
  const needle = normalizeFilterText(rawFilter);
  if (!needle) {
    return true;
  }

  if (resolvedTopic?.topicId) {
    return toInt(topicId) === toInt(resolvedTopic.topicId);
  }

  const key = normalizeFilterText(topicKey);
  const label = normalizeFilterText(topicLabel);
  return Boolean(
    (key && key.includes(needle))
    || (label && label.includes(needle))
  );
}
