// Normalize truncated source years while retaining the literal date for audit.
export function normalizeDecisionDate(row) {
  const source = row.decision_date_source ?? row.decision_date;
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(source);
  if (!match) return row;
  const year = Number(match[1]);
  let corrected = year;
  if (year > 0 && year < 100) {
    const captureYear = Number((row.source_snapshot_date || row.entry_updated_at || '').slice(0, 4));
    if (!Number.isInteger(captureYear) || captureYear < 1900) return row;
    corrected = Math.floor(captureYear / 100) * 100 + year;
    if (corrected > captureYear) corrected -= 100;
  } else if (source === '0204-12-03' && row.contract_id === 'Compra derivada SDA 02/2023-1290') {
    corrected = 2024;
  } else if (source === '0205-06-26' && row.contract_id === '82/24-C') {
    corrected = 2025;
  }
  if (corrected === year) return row;
  const decision_date = `${corrected}-${match[2]}-${match[3]}`;
  const parsed = new Date(`${decision_date}T12:00:00Z`);
  if (Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== decision_date) return row;
  return { ...row, decision_date, decision_date_source: source };
}

export function normalizeDecisionDates(rows) {
  return rows.map(normalizeDecisionDate).sort((a, b) => a.decision_date.localeCompare(b.decision_date)
    || a.source_record_id.localeCompare(b.source_record_id) || a.money_fact_id.localeCompare(b.money_fact_id));
}
