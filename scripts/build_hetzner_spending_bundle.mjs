#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {DatabaseSync} from 'node:sqlite';
import {validDateRepresentation} from './spending_date_quality.mjs';
const [database,output]=process.argv.slice(2);
if(!database||!output||fs.existsSync(output))throw Error('Usage: build_hetzner_spending_bundle.mjs VERIFIED_DB NEW_OUTPUT');
const db=new DatabaseSync(database,{readOnly:true});
const metadata=JSON.parse(db.prepare('SELECT payload FROM metadata WHERE id=1').get().payload);
const totals=db.prepare('SELECT COUNT(*) rows, SUM(amount_cents) amount_cents FROM awards').get();
if(totals.rows!==metadata.rows||totals.amount_cents!==metadata.amount_cents)throw Error('Database parity failed');
let undatedCount=0,undatedAmount=0;
for(const record of db.prepare('SELECT id,payload,amount_cents FROM awards ORDER BY id').iterate()){
 const row=JSON.parse(record.payload);
 if(!validDateRepresentation(row))throw Error('Invalid decision date representation');
 if(row.decision_date===null){
  undatedCount++;undatedAmount+=record.amount_cents;
  if(record.id!==(metadata.undated?.first??-1)+undatedCount-1)throw Error('Unresolved date ordering failed');
 }
}
if(undatedCount&&metadata.undated.first!==metadata.rows-undatedCount+1)throw Error('Unresolved dates must form the final contiguous range');
if(undatedCount!==(metadata.undated?.count??0)||undatedAmount!==(metadata.undated?.amount_cents??0))throw Error('Unresolved date metadata parity failed');
if(db.prepare('PRAGMA quick_check').get().quick_check!=='ok')throw Error('SQLite integrity failed');
db.close();
fs.mkdirSync(output,{recursive:true});
for(const name of ['server.mjs','worker.mjs'])fs.copyFileSync(path.join('infra/hetzner/spending-api',name),path.join(output,name));
fs.copyFileSync('infra/cloudflare/spending-api/src/index.mjs',path.join(output,'index.mjs'));
fs.copyFileSync(database,path.join(output,'awards.db'));
const release=Object.fromEntries(['version','release','rows','amount_cents','date_min','date_max','undated'].map(key=>[key,metadata[key]]));
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
