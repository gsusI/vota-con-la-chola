import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {validateQuota, parseReceipt, run} from '../scripts/run_spending_import_batch.mjs';

const now = Date.parse('2026-09-07T21:00:00Z');
const quota = {account_id:'account', plan:'free', source:'cloudflare-account-usage',
  observed_at:'2026-09-07T20:59:00Z', daily_limit:100000, rows_written:78000};
test('quota includes reserve, freshness, day and account checks', () => {
  validateQuota(quota, 'account', 20000, now);
  for (const change of [{rows_written:78001}, {rows_written:-1}, {plan:'paid'},
    {account_id:'other'}, {observed_at:'2026-09-07T20:54:59Z'},
    {observed_at:'2026-09-07T21:00:01Z'}, {source:'email'}]) {
    assert.throws(() => validateQuota({...quota, ...change}, 'account', 20000, now));
  }
  assert.throws(() => validateQuota({...quota, observed_at:'2026-09-07T23:59:59Z'},
    'account', 20000, Date.parse('2026-09-08T00:00:01Z')));
});
test('only a successful import bookmark with actual writes confirms completion', () => {
  const good = {success:true, finalBookmark:'bookmark', meta:{rows_written:100, rows_read:2,size_after:1000}};
  assert.equal(parseReceipt(JSON.stringify([good])).rows_written, 100);
  for (const response of [[], [good,good], [{...good,success:false}],
    [{...good,finalBookmark:''}], [{...good,meta:{}}]]) {
    assert.throws(() => parseReceipt(JSON.stringify(response)));
  }
  assert.throws(() => parseReceipt('connection lost'));
});
test('dry run is read-only; checksum, pending state and active target fail closed', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(),'spending-runner-test-'));
  try {
    const sql = 'SELECT 1;\n';
    const hash = createHash('sha256').update(sql).digest('hex');
    const manifest = {schema_version:'spending_import_plan_v2',date_quality_passed:true,version:'version',
      batches:[{path:'batch-0000.sql',bytes:Buffer.byteLength(sql),sha256:hash,write_budget:20000}]};
    const config = {account_id:'account',d1_databases:[{database_name:'vclc-spending-national-test',
      database_id:'c0229128-382b-4a12-9d52-845683ea41d3'}]};
    const write = (name,value) => fs.writeFileSync(path.join(root,name), JSON.stringify(value));
    fs.writeFileSync(path.join(root,'batch-0000.sql'),sql);
    write('manifest.json',manifest); write('config.json',config);
    write('quota.json',{...quota,observed_at:new Date().toISOString()});
    const args = [root,path.join(root,'config.json'),path.join(root,'ledger'),path.join(root,'quota.json'),'--dry-run'];
    assert.equal(run(args).index,0);
    assert.equal(fs.existsSync(path.join(root,'ledger')),false);
    fs.writeFileSync(path.join(root,'batch-0000.sql'),sql+'SELECT 2;');
    assert.throws(() => run(args), /checksum/);
    fs.writeFileSync(path.join(root,'batch-0000.sql'),sql);
    config.d1_databases[0].database_id='b6fa6c34-bcd8-47ed-8e71-9672ed9234f8';
    write('config.json',config);
    assert.throws(() => run(args), /Active database/);
    config.d1_databases[0].database_id='c0229128-382b-4a12-9d52-845683ea41d3';
    write('config.json',config);
    fs.mkdirSync(path.join(root,'ledger'));
    fs.writeFileSync(path.join(root,'ledger','ledger.json'),JSON.stringify({
      account_id:'account',database_id:config.d1_databases[0].database_id, version:'version',
      manifest_sha256:createHash('sha256').update(fs.readFileSync(path.join(root,'manifest.json'))).digest('hex'),
      completed:[],pending:{index:0}}));
    assert.throws(() => run(args), /Uncertain previous attempt/);
  } finally { fs.rmSync(root,{recursive:true,force:true}); }
});
