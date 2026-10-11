import assert from 'node:assert/strict';
import path from 'node:path';
import fs from 'node:fs';
import {spawn} from 'node:child_process';
const bundle=path.resolve(process.argv[2]);
const child=spawn(process.execPath,[path.join(bundle,'server.mjs')],{env:{...process.env,HOST:'127.0.0.1',PORT:'18087',DB_PATH:path.join(bundle,'awards.db')},stdio:['ignore','ignore','inherit']});
const base='http://127.0.0.1:18087';
try{
 let ready=false;
 for(let i=0;i<50;i++){
  if(child.exitCode!==null)throw Error('Test server exited');
  try{ready=(await fetch(base+'/readyz')).ok;}catch{}
  if(ready)break;
  await new Promise(resolve=>setTimeout(resolve,100));
 }
 assert.ok(ready);
 const routes=['/v1/awards?limit=12','/v1/options?kind=authority','/v1/options?kind=supplier'];
 const initial=await Promise.all(routes.map(async route=>{const r=await fetch(base+route);assert.equal(r.status,200);return r.json();}));
 assert.equal(initial[0].count,JSON.parse(fs.readFileSync(path.join(bundle,'release.json'))).rows);
 assert.ok(Array.isArray(initial[1].values)&&Array.isArray(initial[2].values));
 const burst=await Promise.all(Array.from({length:20},async()=>{const r=await fetch(base+'/v1/awards?limit=200');assert.ok([200,503].includes(r.status));const body=await r.json();assert.ok(r.ok?Array.isArray(body.rows):typeof body.error==='string');return r.status;}));
 assert.equal((await fetch(base+'/readyz')).status,200);
 console.log(JSON.stringify({initial_parallel_requests:'3/3 passed',burst_200:burst.filter(x=>x===200).length,burst_503:burst.filter(x=>x===503).length,all_responses_valid_json:true,ready_after_burst:true}));
}finally{if(child.exitCode===null)child.kill('SIGTERM');}
