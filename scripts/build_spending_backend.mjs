#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { gunzipSync } from 'node:zlib';
import { createHash } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import { normalizeDecisionDates } from '../ui/gh-pages-next/app/spending/decision-dates.mjs';
const root = process.cwd();
const output = process.argv[2];
if (!output) throw new Error('Usage: node scripts/build_spending_backend.mjs OUTPUT_DIRECTORY');
fs.mkdirSync(output, { recursive: true });
const publicRoot = path.join(root, 'ui/gh-pages-next/public/spending/launch');
const release = JSON.parse(fs.readFileSync(path.join(publicRoot, 'latest.json')));
const bytes = fs.readFileSync(path.join(publicRoot, release.release, 'awards.json.gz'));
const original = JSON.parse(gunzipSync(bytes));
const rows = normalizeDecisionDates(original);
if (rows.length !== release.rows || rows.reduce((s,r) => s+r.amount_cents,0) !== release.amount_cents) throw new Error('Corpus parity failed');
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
 if (days.at(-1)?.date !== r.decision_date) days.push({date:r.decision_date, first:i+1, last:i+1, amountBefore:cumulativeAmount-r.amount_cents, amountThrough:cumulativeAmount});
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
fs.writeFileSync(path.join(output,'search-import.sql'),searchSql.join('\n'));
const version = createHash('sha256').update(bytes).update(JSON.stringify(days)).update('decision-dates-v1').digest('hex');
const metadata = {version, release:release.release, rows:rows.length, amount_cents:cumulativeAmount, date_min:days[0].date, date_max:days.at(-1).date, days, csv_keys:[...Object.keys(rows[0]).filter(k=>k!=='decision_date_source'),'decision_date_source']};
const metaText=JSON.stringify(metadata);
sql.push("INSERT INTO metadata VALUES(1,'');");
for(let start=0;start<metaText.length;start+=20000) sql.push(`UPDATE metadata SET payload=payload || ${quote(metaText.slice(start,start+20000))} WHERE id=1;`);
const maxStatementBytes=Math.max(...sql.map(s=>Buffer.byteLength(s)));
if(maxStatementBytes>95000) throw new Error('D1 statement limit; reduce publication slice');
const estimatedWrites=rows.length+groups.size+searchSql.length+20;
if(estimatedWrites>90000) throw new Error('Daily import budget exceeded; schedule a bounded incremental import');
fs.writeFileSync(path.join(output,'import.sql'),sql.join('\n'));
const dbPath=path.join(output,'verify.db');
if(fs.existsSync(dbPath)) fs.unlinkSync(dbPath);
const db=new DatabaseSync(dbPath);
db.exec('BEGIN;'+sql.join('\n')+'COMMIT;');
db.close();
const databaseBytes=fs.statSync(dbPath).size;
if(databaseBytes>450_000_000) throw new Error('Free database storage budget exceeded');
fs.writeFileSync(path.join(output,'metadata.json'),JSON.stringify(metadata));
fs.writeFileSync(path.join(root,'infra/cloudflare/spending-api/src/release.json'),JSON.stringify({version,release:release.release,rows:rows.length,amount_cents:cumulativeAmount,date_min:metadata.date_min,date_max:metadata.date_max}));
const report={version,rows:rows.length,amount_cents:cumulativeAmount,entities:groups.size,search_terms:terms.size,search_writes:searchSql.length,days:days.length,estimated_writes:estimatedWrites,database_bytes:databaseBytes,max_statement_bytes:maxStatementBytes,sql_bytes:Buffer.byteLength(sql.join('\n'))};
fs.writeFileSync(path.join(output,'build-report.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report));
