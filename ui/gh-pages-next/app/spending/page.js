import { readPublicJson } from '../static-snapshot.mjs';
import LaunchExplorer from './launch-explorer';
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
  const rows = readHistoryJson('awards.json');
  const audit = readHistoryJson('audit.json');
  if (!rows || rows.length !== release.rows || rows.reduce((sum, row) => sum + row.amount_cents, 0) !== release.amount_cents) {
    throw new Error('PLACSP launch row/amount mismatch');
  }
  return <LaunchExplorer audit={audit} release={release} />;
}
