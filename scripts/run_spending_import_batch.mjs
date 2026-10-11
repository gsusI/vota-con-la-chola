#!/usr/bin/env node
// One candidate batch per invocation. Never promotes a Worker or retries a request.
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {pathToFileURL} from 'node:url';

const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const requireThat = (condition, message) => { if (!condition) throw new Error(message); };

export function validateQuota(quota, account, budget, now = Date.now()) {
  const observed = Date.parse(quota.observed_at);
  requireThat(quota.account_id === account && quota.plan === 'free', 'Account or free plan mismatch');
  requireThat(quota.source === 'cloudflare-account-usage', 'Account-wide usage evidence required');
  requireThat(Number.isFinite(observed) && observed <= now && now - observed <= 300000,
    'Quota observation must be at most five minutes old');
  requireThat(new Date(observed).toISOString().slice(0,10) === new Date(now).toISOString().slice(0,10),
    'Quota observation belongs to a different UTC day');
  requireThat(quota.daily_limit === 100000 && Number.isSafeInteger(quota.rows_written)
    && quota.rows_written >= 0 && quota.rows_written <= quota.daily_limit, 'Invalid write usage');
  requireThat(quota.daily_limit - quota.rows_written >= budget + 2000,
    'Insufficient daily writes including 2,000-row reserve');
}

export function parseReceipt(stdout) {
  const response = JSON.parse(stdout);
  requireThat(Array.isArray(response) && response.length === 1 && response[0].success === true,
    'Import completion not confirmed');
  const result = response[0];
  requireThat(Number.isSafeInteger(result.meta?.rows_written) && result.meta.rows_written >= 0,
    'Missing actual rows_written');
  requireThat(typeof result.finalBookmark === 'string' && result.finalBookmark.length > 0,
    'Missing import completion bookmark');
  return {rows_written: result.meta.rows_written, rows_read: result.meta.rows_read,
    size_after: result.meta.size_after, bookmark: result.finalBookmark};
}

export function run(argv) {
  const [planDirectory, configFile, ledgerDirectory, quotaFile, mode] = argv;
  requireThat(argv.length === 5 && ['--dry-run', '--execute'].includes(mode),
    'Usage: run_spending_import_batch.mjs PLAN CANDIDATE_JSON LEDGER QUOTA_JSON --dry-run|--execute');
  const config = read(configFile); // Plain JSON is also a valid Wrangler JSONC configuration.
  requireThat(!config.main && !config.routes && !config.route && !config.name,
    'Configuration must be D1-only, with no Worker deployment settings');
  requireThat(config.d1_databases?.length === 1, 'Exactly one candidate database required');
  const target = config.d1_databases[0];
  requireThat(target.database_name?.startsWith('vclc-spending-national-')
    && target.database_id !== 'b6fa6c34-bcd8-47ed-8e71-9672ed9234f8', 'Active database forbidden');
  requireThat(/^[a-f0-9-]{36}$/.test(target.database_id), 'Invalid database UUID');
  const manifestBytes = fs.readFileSync(path.join(planDirectory, 'manifest.json'));
  const manifest = JSON.parse(manifestBytes);
  requireThat(manifest.schema_version === 'spending_import_plan_v2', 'Idempotent v2 plan required');
  requireThat(manifest.date_quality_passed === true, 'Candidate date-quality gate has not passed');
  const identity = {manifest_sha256: sha(manifestBytes), version: manifest.version,
    database_id: target.database_id, account_id: config.account_id};
  const ledgerFile = path.join(ledgerDirectory, 'ledger.json');
  const ledger = fs.existsSync(ledgerFile) ? read(ledgerFile) : {...identity, completed: []};
  for (const [key,value] of Object.entries(identity)) requireThat(ledger[key] === value, 'Ledger target or plan mismatch');
  requireThat(!ledger.pending, 'Uncertain previous attempt: reconcile remote completion and quota before continuing');
  requireThat(!ledger.halted, 'Import halted after exceeding the write allowance; review budgets before continuing');
  for (const [index, receipt] of ledger.completed.entries()) {
    requireThat(receipt.index === index && receipt.sha256 === manifest.batches[index]?.sha256,
      'Ledger batch sequence mismatch');
  }
  const index = ledger.completed.length;
  const batch = manifest.batches[index];
  requireThat(batch, 'All batches already recorded; perform independent remote verification before promotion');
  requireThat(/^batch-\d{4}\.sql$/.test(batch.path), 'Invalid batch path');
  const sqlFile = path.resolve(planDirectory, batch.path);
  const bytes = fs.readFileSync(sqlFile);
  requireThat(bytes.length === batch.bytes && sha(bytes) === batch.sha256, 'Batch checksum mismatch');
  requireThat(Number.isSafeInteger(batch.write_budget) && batch.write_budget > 0
    && batch.write_budget <= 20000, 'Invalid batch budget');
  const quota = read(quotaFile);
  validateQuota(quota, config.account_id, batch.write_budget);
  const previous = ledger.completed.at(-1);
  requireThat(!previous || Date.parse(quota.observed_at) > Date.parse(previous.finished_at),
    'Refresh account-wide quota after the previous batch');
  const summary = {...identity, index, batch: batch.path, write_budget: batch.write_budget, mode};
  if (mode === '--dry-run') return summary;
  fs.mkdirSync(ledgerDirectory, {recursive: true});
  const lockFile = path.join(ledgerDirectory, 'import.lock');
  const lock = fs.openSync(lockFile, 'wx');
  const save = () => {
    fs.writeFileSync(ledgerFile + '.tmp', JSON.stringify(ledger, null, 2) + '\n');
    fs.renameSync(ledgerFile + '.tmp', ledgerFile);
  };
  try {
    // Recheck under lock: another invocation may have completed since our initial read.
    if (fs.existsSync(ledgerFile)) requireThat(JSON.stringify(read(ledgerFile)) === JSON.stringify(ledger),
      'Ledger changed while preparing batch');
    ledger.pending = {index, sha256: batch.sha256, started_at: new Date().toISOString(),
      quota_observed_at: quota.observed_at, rows_written_before: quota.rows_written};
    save();
    const result = spawnSync('wrangler', ['d1', 'execute', target.database_name, '--remote',
      '--config', path.resolve(configFile), '--file', sqlFile, '--yes', '--json'],
    {encoding: 'utf8', maxBuffer: 8 * 1024 * 1024,
      env: {...process.env, CLOUDFLARE_LOAD_DEV_VARS_FROM_DOT_ENV: 'false'}});
    // Never persist raw CLI errors: they may contain local paths or credential-bearing URLs.
    requireThat(!result.error && result.status === 0, 'Wrangler did not confirm completion; pending attempt retained');
    const receipt = parseReceipt(result.stdout);
    ledger.completed.push({index, sha256: batch.sha256, ...receipt, finished_at: new Date().toISOString()});
    delete ledger.pending;
    if (receipt.rows_written > batch.write_budget) ledger.halted = 'write_budget_exceeded';
    save();
    requireThat(receipt.rows_written <= batch.write_budget,
      'Actual writes exceeded allowance; receipt saved, review future batch budgets');
    return {...summary, receipt};
  } finally {
    fs.closeSync(lock);
    fs.unlinkSync(lockFile);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  try { console.log(JSON.stringify(run(process.argv.slice(2)), null, 2)); }
  catch (error) { console.error(error.message); process.exitCode = 1; }
}
