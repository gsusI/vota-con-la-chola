import http from 'node:http';
import {Worker} from 'node:worker_threads';
let worker, ready=false, active=null;
function startWorker(){
 worker=new Worker(new URL('./worker.mjs',import.meta.url),{resourceLimits:{maxOldGenerationSizeMb:256}});
 worker.on('message',message=>{
  if(message.ready){ready=true;return;}
  if(!active)return;
  clearTimeout(active.timer);
  active.response.writeHead(message.status,message.headers);
  active.response.end(message.body);
  active=null;
 });
 worker.on('error',()=>{});
 worker.on('exit',()=>{
  ready=false;
  if(active){clearTimeout(active.timer);active.response.writeHead(503,{'Retry-After':'5'});active.response.end();active=null;}
  setTimeout(startWorker,1000).unref();
 });
}
startWorker();
const server=http.createServer((req,res)=>{
 if(req.url==='/healthz'||req.url==='/readyz'){
  res.writeHead(ready?200:503,{'Content-Type':'application/json','Cache-Control':'no-store'});
  res.end(JSON.stringify({ready}));return;
 }
 if(!ready||active){res.writeHead(503,{'Retry-After':'1','Access-Control-Allow-Origin':'*'});res.end();return;}
 if(req.url.length>4096){res.writeHead(414);res.end();return;}
 if(!['GET','OPTIONS'].includes(req.method)){res.writeHead(405,{'Allow':'GET, OPTIONS'});res.end();return;}
 active={response:res,timer:setTimeout(()=>worker.terminate(),5000)};
 worker.postMessage({url:'http://spending.internal'+req.url,method:req.method});
});
server.maxConnections=32;
server.headersTimeout=5000;
server.requestTimeout=10000;
server.keepAliveTimeout=2000;
server.listen(Number(process.env.PORT||8080),'0.0.0.0');
process.on('SIGTERM',()=>server.close(()=>process.exit(0)));
