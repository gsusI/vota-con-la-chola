#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { gunzipSync } from 'node:zlib';
import { createHash } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import { classifyDecisionDates, validDateRepresentation } from './spending_date_quality.mjs';
const root = process.cwd();
const output = process.argv[2];
const planOnly = process.argv.includes('--plan-only');
const publicRootArg = process.argv.find(arg => arg.startsWith('--public-root='));
for (const arg of process.argv.slice(3)) if (arg !== '--plan-only' && !arg.startsWith('--public-root=')) throw new Error('Unknown build argument');
if (!output) throw new Error('Usage: node scripts/build_spending_backend.mjs OUTPUT_DIRECTORY');
fs.mkdirSync(output, { recursive: true });
const publicRoot = publicRootArg ? path.resolve(publicRootArg.slice('--public-root='.length)) : path.join(root, 'ui/gh-pages-next/public/spending/launch');
const release = JSON.parse(fs.readFileSync(path.join(publicRoot, 'latest.json')));
const releaseRoot=path.join(publicRoot,release.release);
const compressed=release.file_encodings?.['awards.json']==='gzip'||fs.existsSync(path.join(releaseRoot,'awards.json.gz'));
const parts=release.file_parts?.['awards.json']||[{path:compressed?'awards.json.gz':'awards.json'}];
const bytes=Buffer.concat(parts.map(part=>{
 const file=path.resolve(releaseRoot,part.path);
 if(!file.startsWith(path.resolve(releaseRoot)+path.sep))throw new Error('Transport path escapes release');
 const chunk=fs.readFileSync(file);
 if(part.bytes!==undefined&&chunk.length!==part.bytes)throw new Error('Transport part size mismatch');
 if(part.sha256&&createHash('sha256').update(chunk).digest('hex')!==part.sha256)throw new Error('Transport part checksum mismatch');
 return chunk;
}));
const original = JSON.parse(compressed?gunzipSync(bytes):bytes);
const rows = classifyDecisionDates(original);
if (rows.length !== release.rows || rows.reduce((s,r) => s+r.amount_cents,0) !== release.amount_cents) throw new Error('Corpus parity failed');
const unresolvedDates = rows.filter(row=>row.decision_date_status==='unresolved');
if(!rows.every(validDateRepresentation))throw new Error('Invalid date representation');
fs.writeFileSync(path.join(output,'date-quality.json'),JSON.stringify({
 schema_version:'spending_date_quality_v2',passed:true,unresolved_count:unresolvedDates.length,
 policy:'Unresolved dates retain their literal source and use null for date filtering; no year is invented.',
 unresolved:unresolvedDates.map(({award_key,decision_date,decision_date_source,contract_id})=>({award_key,decision_date,decision_date_source,contract_id}))},null,2)+'\n');
const normal = s => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
const quote = v => typeof v === 'number' ? String(v) : "'" + String(v).replaceAll("'", "''") + "'";
const sql = [
 'CREATE TABLE awards(id INTEGER PRIMARY KEY, amount_cents INTEGER NOT NULL, title_search TEXT NOT NULL, payload TEXT NOT NULL);',
 'CREATE TABLE entities(kind TEXT NOT NULL, name TEXT NOT NULL, search TEXT NOT NULL, ids TEXT NOT NULL, PRIMARY KEY(kind,name)) WITHOUT ROWID;',
 'CREATE TABLE metadata(id INTEGER PRIMARY KEY, payload TEXT NOT NULL);',
];
const groups = new Map();
const terms = new Map();
function indexText(kind,text,id) {
 const grams=new Set();
 for(let i=0;i<text.length-1;i++)grams.add(text.slice(i,i+2));
 for(const term of grams){const key=kind+"\0"+term;if(!terms.has(key))terms.set(key,{kind,term,ids:[]});terms.get(key).ids.push(id);}
}
const days = [];
let cumulativeAmount = 0;
rows.forEach((row, i) => {
 const r = {...row, decision_date_source: row.decision_date_source || row.decision_date};
 sql.push(`INSERT INTO awards VALUES(${[i+1,r.amount_cents,normal(r.title+' '+r.contract_id),JSON.stringify(r)].map(quote).join(',')});`);
 indexText('awards',normal(r.title+' '+r.contract_id),i+1);
 cumulativeAmount += r.amount_cents;
 if (r.decision_date === null) {}
 else if (days.at(-1)?.date !== r.decision_date) days.push({date:r.decision_date, first:i+1, last:i+1, amountBefore:cumulativeAmount-r.amount_cents, amountThrough:cumulativeAmount});
 else Object.assign(days.at(-1),{last:i+1,amountThrough:cumulativeAmount});
 for(const kind of ['authority','supplier']) {
  const k = kind+'\0'+r[kind];
  if(!groups.has(k)) groups.set(k,{kind,name:r[kind],ids:[]});
  groups.get(k).ids.push(i+1);
 }
});
for(const g of groups.values()) {sql.push(`INSERT INTO entities VALUES(${[g.kind,g.name,normal(g.name),JSON.stringify(g.ids)].map(quote).join(',')});`);indexText(g.kind,normal(g.name),g.name);}
const searchSql=['CREATE TABLE search_terms(kind TEXT NOT NULL, term TEXT NOT NULL, entries INTEGER NOT NULL, ids TEXT NOT NULL, PRIMARY KEY(kind,term)) WITHOUT ROWID;'];
for(const t of terms.values()){
 const ids=JSON.stringify(t.ids);
 if(Buffer.byteLength(ids)>1_900_000) throw new Error('Search posting exceeds D1 row budget');
 searchSql.push(`INSERT INTO search_terms VALUES(${[t.kind,t.term,t.ids.length,''].map(quote).join(',')});`);
 for(let start=0;start<ids.length;start+=10000)searchSql.push(`UPDATE search_terms SET ids=ids || ${quote(ids.slice(start,start+10000))} WHERE kind=${quote(t.kind)} AND term=${quote(t.term)};`);
}
sql.push(...searchSql);
if(!planOnly) fs.writeFileSync(path.join(output,'search-import.sql'),searchSql.join('\n'));
const version = createHash('sha256').update(release.release).update(bytes).update(JSON.stringify(days)).update('decision-dates-v2').digest('hex');
const metadata = {version, release:release.release, rows:rows.length, amount_cents:cumulativeAmount, date_min:days[0]?.date??null, date_max:days.at(-1)?.date??null, undated:{count:unresolvedDates.length,first:rows.length-unresolvedDates.length+1,amount_cents:unresolvedDates.reduce((s,r)=>s+r.amount_cents,0)}, days, csv_keys:[...Object.keys(rows[0]).filter(k=>k!=='decision_date_source'),'decision_date_source']};
const metaText=JSON.stringify(metadata);
sql.push("INSERT INTO metadata VALUES(1,'');");
for(let start=0;start<metaText.length;start+=20000) sql.push(`UPDATE metadata SET payload=payload || ${quote(metaText.slice(start,start+20000))} WHERE id=1;`);
const maxStatementBytes=sql.reduce((max,s)=>Math.max(max,Buffer.byteLength(s)),0);
if(maxStatementBytes>95000) throw new Error('D1 statement limit; reduce publication slice');
const estimatedWrites=rows.length+groups.size+searchSql.length+20;
if(estimatedWrites>90000 && !planOnly) throw new Error('Daily import budget exceeded; use --plan-only to measure a bounded import before scheduling');
if(!planOnly) fs.writeFileSync(path.join(output,'import.sql'),sql.join('\n'));
const dbPath=path.join(output,'verify.db');
if(fs.existsSync(dbPath)) fs.unlinkSync(dbPath);
const db=new DatabaseSync(dbPath);
db.exec('BEGIN;'+sql.join('\n')+'COMMIT;');
db.close();
const databaseBytes=fs.statSync(dbPath).size;
if(databaseBytes>450_000_000 && !planOnly) throw new Error('Free database storage budget exceeded');
fs.writeFileSync(path.join(output,'metadata.json'),JSON.stringify(metadata));
fs.writeFileSync(path.join(output,'release.json'),JSON.stringify({version,release:release.release,rows:rows.length,amount_cents:cumulativeAmount,date_min:metadata.date_min,date_max:metadata.date_max,undated:metadata.undated}));
if(!planOnly) fs.copyFileSync(path.join(output,'release.json'),path.join(root,'infra/cloudflare/spending-api/src/release.json'));
const report={version,plan_only:planOnly,date_quality_passed:true,unresolved_dates:unresolvedDates.length,fits_single_day_import:estimatedWrites<=90000,fits_database_budget:databaseBytes<=450_000_000,rows:rows.length,amount_cents:cumulativeAmount,entities:groups.size,search_terms:terms.size,search_writes:searchSql.length,days:days.length,estimated_writes:estimatedWrites,database_bytes:databaseBytes,max_statement_bytes:maxStatementBytes,sql_bytes:Buffer.byteLength(sql.join('\n'))};
fs.writeFileSync(path.join(output,'build-report.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report));
