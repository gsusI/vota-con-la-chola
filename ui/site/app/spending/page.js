import { readPublicJson } from '../static-snapshot.mjs';
import LaunchExplorer from './launch-explorer';
import { classifyDecisionDates } from './decision-dates.mjs';
import fs from 'node:fs';
import path from 'node:path';
import { gunzipSync } from 'node:zlib';

export const metadata = {
  title: '¿A quién se adjudicó? | Vota Con La Chola',
  description: 'Explora todo el histórico disponible de adjudicaciones PLACSP, abre su fuente y reproduce tres consultas con datos descargables.',
};

export default function SpendingPage() {
  const release = readPublicJson('spending/launch/latest.json', null);
  if (!release) throw new Error('Missing validated PLACSP launch');
  const base = `spending/launch/${release.release}`;
  function readHistoryJson(name) {
    const compressed = release.file_encodings?.[name] === 'gzip';
    const parts = release.file_parts?.[name] || [{ path: name + (compressed ? '.gz' : '') }];
    const bytes = Buffer.concat(parts.map((part) => fs.readFileSync(path.join(process.cwd(), 'public', base, part.path))));
    return JSON.parse((compressed ? gunzipSync(bytes) : bytes).toString('utf8'));
  }
  const apiRelease = JSON.parse(fs.readFileSync(path.join(process.cwd(), '../../infra/cloudflare/spending-api/src/release.json')));
  if (apiRelease.release !== release.release || apiRelease.rows !== release.rows || apiRelease.amount_cents !== release.amount_cents) throw new Error('Frontend/API release mismatch');
  const rows = readHistoryJson('awards.json');
  const audit = readHistoryJson('audit.json');
  if (!rows || rows.length !== release.rows || rows.reduce((sum, row) => sum + row.amount_cents, 0) !== release.amount_cents) {
    throw new Error('PLACSP launch row/amount mismatch');
  }
  const normalized = classifyDecisionDates(rows);
  const dated = normalized.filter((row) => row.decision_date !== null);
  const correctedAudit = { ...audit, decision_date_min: dated[0]?.decision_date ?? '1900-01-01', decision_date_max: dated.at(-1)?.decision_date ?? '9999-12-31', date_corrections: normalized.filter((row) => row.decision_date_status === 'corrected').length, unresolved_dates: normalized.length - dated.length };
  return <LaunchExplorer audit={correctedAudit} release={release} apiVersion={apiRelease.version} />;
}
