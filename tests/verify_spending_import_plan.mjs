#!/usr/bin/env node
// Replay an entire real candidate import and compare every row with its source.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {DatabaseSync} from 'node:sqlite';
const [sourcePath,planRoot,replayPath]=process.argv.slice(2);
if(!sourcePath||!planRoot||!replayPath)throw new Error('Usage: node tests/verify_spending_import_plan.mjs SOURCE_DB PLAN_ROOT NEW_REPLAY_DB');
assert(!fs.existsSync(replayPath),'Replay target must be new');
const manifest=JSON.parse(fs.readFileSync(path.join(planRoot,'manifest.json')));
const replay=new DatabaseSync(replayPath);
for(const batch of manifest.batches){
 const bytes=fs.readFileSync(path.join(planRoot,batch.path));
 assert.equal(bytes.length,batch.bytes);
 assert.equal(createHash('sha256').update(bytes).digest('hex'),batch.sha256);
 assert(batch.write_budget<=20000);
 replay.exec('BEGIN;'+bytes.toString()+'COMMIT;');
 replay.exec('BEGIN;'+bytes.toString()+'COMMIT;'); // retry after an uncertain successful response
}
const source=new DatabaseSync(sourcePath,{readOnly:true});
const fingerprints=db=>{
 const result={};
 for(const table of ['awards','entities','search_terms','metadata']){
  const keys=db.prepare(`PRAGMA table_info(${table})`).all().filter(c=>c.pk).sort((a,b)=>a.pk-b.pk).map(c=>c.name);
  const digest=createHash('sha256');let rows=0;
  for(const row of db.prepare(`SELECT * FROM ${table} ORDER BY ${keys.join(',')}`).iterate()){digest.update(JSON.stringify(row)+'\n');rows++;}
  result[table]={rows,sha256:digest.digest('hex')};
 }
 return result;
};
const expected=fingerprints(source),actual=fingerprints(replay);
assert.deepEqual(actual,expected);
assert.equal(actual.awards.rows,manifest.rows);
assert.equal(replay.prepare('SELECT SUM(amount_cents) n FROM awards').get().n,manifest.amount_cents);
console.log(JSON.stringify({ok:true,batches:manifest.batches.length,tables:actual}));
assert.throws(()=>replay.exec("INSERT INTO _import_plan VALUES('wrong-candidate') ON CONFLICT(version) DO NOTHING;"),/CHECK/);
source.close();replay.close();
