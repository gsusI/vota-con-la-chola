import { readPublicJson } from '../static-snapshot.mjs';
import LaunchExplorer from './launch-explorer';

export const metadata = {
  title: '¿A quién se adjudicó? | Vota Con La Chola',
  description: 'Explora la cohorte completa de resultados de adjudicación PLACSP de enero de 2025, abre su fuente y reproduce tres consultas con datos descargables.',
};

export default function SpendingPage() {
  const release = readPublicJson('spending/launch/latest.json', null);
  if (!release) throw new Error('Missing validated PLACSP launch');
  const base = `spending/launch/${release.release}`;
  const rows = readPublicJson(`${base}/awards.json`, null);
  const audit = readPublicJson(`${base}/audit.json`, null);
  if (!rows || rows.length !== release.rows || rows.reduce((sum, row) => sum + row.amount_cents, 0) !== release.amount_cents) {
    throw new Error('PLACSP launch row/amount mismatch');
  }
  return <LaunchExplorer audit={audit} release={release} />;
}
