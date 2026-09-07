import {parentPort} from 'node:worker_threads';
import {DatabaseSync} from 'node:sqlite';
import {respond} from './index.mjs';
import release from './release.json' with {type:'json'};
const db=new DatabaseSync(process.env.DB_PATH||'/data/awards.db',{readOnly:true});
db.exec('PRAGMA query_only=ON; PRAGMA cache_size=-16384; PRAGMA temp_store=MEMORY;');
const meta=JSON.parse(db.prepare('SELECT payload FROM metadata WHERE id=1').get().payload);
if(meta.version!==release.version||meta.rows!==release.rows||meta.amount_cents!==release.amount_cents)throw Error('Release mismatch');
const env={DB:{prepare(sql){return {args:[],bind(...args){this.args=args;return this;},async first(){return db.prepare(sql).get(...this.args);},async all(){return {results:db.prepare(sql).all(...this.args),meta:{rows_read:0}};}};},batch(stmts){return Promise.all(stmts.map(s=>s.all()));}}};
parentPort.on('message',async request=>{
 try{
  const response=await respond(new Request(request.url,{method:request.method}),env);
  parentPort.postMessage({status:response.status,headers:Object.fromEntries(response.headers),body:await response.text()});
 }catch{parentPort.postMessage({status:503,headers:{'Retry-After':'5'},body:''});}
});
parentPort.postMessage({ready:true});
