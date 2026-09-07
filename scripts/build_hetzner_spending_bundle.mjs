#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {DatabaseSync} from 'node:sqlite';
const [database,output]=process.argv.slice(2);
if(!database||!output||fs.existsSync(output))throw Error('Usage: build_hetzner_spending_bundle.mjs VERIFIED_DB NEW_OUTPUT');
const db=new DatabaseSync(database,{readOnly:true});
const metadata=JSON.parse(db.prepare('SELECT payload FROM metadata WHERE id=1').get().payload);
const totals=db.prepare('SELECT COUNT(*) rows, SUM(amount_cents) amount_cents FROM awards').get();
if(totals.rows!==metadata.rows||totals.amount_cents!==metadata.amount_cents)throw Error('Database parity failed');
if(db.prepare("SELECT COUNT(*) n FROM awards WHERE json_extract(payload,'$.decision_date') IS NULL OR json_extract(payload,'$.decision_date') < '1900-01-01'").get().n)throw Error('API handling for unresolved dates must be finished before publishing this candidate');
if(db.prepare('PRAGMA quick_check').get().quick_check!=='ok')throw Error('SQLite integrity failed');
db.close();
fs.mkdirSync(output,{recursive:true});
for(const name of ['server.mjs','worker.mjs'])fs.copyFileSync(path.join('infra/hetzner/spending-api',name),path.join(output,name));
fs.copyFileSync('infra/cloudflare/spending-api/src/index.mjs',path.join(output,'index.mjs'));
fs.copyFileSync(database,path.join(output,'awards.db'));
const release=Object.fromEntries(['version','release','rows','amount_cents','date_min','date_max'].map(key=>[key,metadata[key]]));
fs.writeFileSync(path.join(output,'release.json'),JSON.stringify(release));
let sums='';
for(const name of ['server.mjs','worker.mjs','index.mjs','release.json','awards.db']){
 const hash=createHash('sha256');
 for await(const chunk of fs.createReadStream(path.join(output,name)))hash.update(chunk);
 sums+=hash.digest('hex')+'  '+name+'\n';
}
fs.writeFileSync(path.join(output,'SHA256SUMS'),sums);
const identity=createHash('sha256').update(sums).digest('hex');
fs.writeFileSync(path.join(output,'bundle.sha256'),identity+'\n');
console.log(JSON.stringify({bundle:identity,version:metadata.version,rows:metadata.rows,amount_cents:metadata.amount_cents}));
