export function shouldShowPersonTrajectoryChunkSummary(summary) {
  if (!summary || typeof summary !== "object") {
    return false;
  }
  const scanMode = String(summary.scanMode || "").trim();
  return scanMode !== "default_rows" && scanMode !== "sort_preview" && scanMode !== "topic_preview";
}
