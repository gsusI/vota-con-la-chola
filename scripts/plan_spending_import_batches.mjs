#!/usr/bin/env node
// Export a verified local candidate as ordered, checksum-bound D1 import batches.
// This tool performs no network calls and never updates the active release.
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {DatabaseSync} from 'node:sqlite';
import {validDateRepresentation} from './spending_date_quality.mjs';
const [database,output]=process.argv.slice(2);
if(!database||!output)throw new Error('Usage: node scripts/plan_spending_import_batches.mjs VERIFY_DB NEW_OUTPUT');
if(fs.existsSync(output))throw new Error('Output must be new; import plans are immutable');
const db=new DatabaseSync(database,{readOnly:true});
const metadata=JSON.parse(db.prepare('SELECT payload FROM metadata WHERE id=1').get().payload);
if(db.prepare('SELECT COUNT(*) n FROM awards').get().n!==metadata.rows)throw new Error('Candidate count mismatch');
if(db.prepare('SELECT SUM(amount_cents) n FROM awards').get().n!==metadata.amount_cents)throw new Error('Candidate amount mismatch');
for(const {payload} of db.prepare('SELECT payload FROM awards').iterate()){
 if(!validDateRepresentation(JSON.parse(payload)))throw new Error('Invalid decision-date representation');
}
const tables=['awards','entities','search_terms','metadata'];
const quote=value=>value===null?'NULL':typeof value==='number'?String(value):"'"+String(value).replaceAll("'","''")+"'";
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
fs.mkdirSync(output,{recursive:true});
const batches=[];let statements=[],cost=0;
const flush=()=>{
 if(!statements.length)return;
 const name=`batch-${String(batches.length).padStart(4,'0')}.sql`;
 const guard=[`CREATE TABLE IF NOT EXISTS _import_plan(version TEXT PRIMARY KEY CHECK(version=${quote(metadata.version)}));`, `INSERT INTO _import_plan VALUES(${quote(metadata.version)}) ON CONFLICT(version) DO NOTHING;`];
 const bytes=Buffer.from([...guard,...statements].join('\n')+'\n');
 fs.writeFileSync(path.join(output,name),bytes);
 batches.push({path:name,sha256:hash(bytes),bytes:bytes.length,statements:statements.length+2,write_budget:cost+4});
 statements=[];cost=0;
};
const append=statement=>{
 if(Buffer.byteLength(statement)>95000)throw new Error('Statement exceeds D1 budget');
 if(cost+2>19996)flush();
 statements.push(statement);cost+=2;
};
for(const table of tables){
 const schema=db.prepare("SELECT sql FROM sqlite_master WHERE type='table' AND name=?").get(table)?.sql;
 if(!schema)throw new Error(`Missing table ${table}`);
 append(schema.replace(/^CREATE TABLE /,'CREATE TABLE IF NOT EXISTS ')+';');
 // Chunk long posting lists and metadata without changing their reconstructed content.
 const columns=db.prepare(`PRAGMA table_info(${table})`).all();
 const keys=columns.filter(c=>c.pk).sort((a,b)=>a.pk-b.pk).map(c=>c.name);
 for(const row of db.prepare(`SELECT * FROM ${table} ORDER BY ${keys.join(',')}`).iterate()){
  const long=columns.filter(c=>typeof row[c.name]==='string'&&row[c.name].length>10000).map(c=>c.name);
  append(`INSERT OR IGNORE INTO ${table} VALUES(${columns.map(c=>quote(long.includes(c.name)?'':row[c.name])).join(',')});`);
  for(const column of long){
   // SQLite length() counts Unicode code points, not JavaScript UTF-16 units.
   const characters=Array.from(row[column]);
   for(let i=0;i<characters.length;i+=10000){
    const chunk=characters.slice(i,i+10000).join('');
    append(`UPDATE ${table} SET ${column}=${column} || ${quote(chunk)} WHERE ${keys.map(k=>`${k}=${quote(row[k])}`).join(' AND ')} AND length(${column})=${i};`);
   }
  }
 }
}
flush();db.close();
fs.writeFileSync(path.join(output,'manifest.json'),JSON.stringify({schema_version:'spending_import_plan_v2',date_quality_passed:true,version:metadata.version,rows:metadata.rows,amount_cents:metadata.amount_cents,batches,write_budget:batches.reduce((s,b)=>s+b.write_budget,0),requirements:['Use a new empty candidate database, never the active database.','Check remaining account-wide daily writes before each batch; budgets include a two-writes-per-statement allowance for this schema, not a provider guarantee.','Apply in order and record confirmed batch checksum and actual rows_written.','Batches are idempotent for the same candidate: inserts ignore existing keys, append chunks check completed Unicode length, and a database CHECK guard rejects a different candidate. Reconcile actual quota use before retries.','Do not promote until all batches and independent count, amount and query checks pass.']},null,2)+'\n');
console.log(JSON.stringify({batches:batches.length,write_budget:batches.reduce((s,b)=>s+b.write_budget,0),rows:metadata.rows}));
