import http from 'node:http';
import {Worker} from 'node:worker_threads';
let worker, ready=false, active=null;
const queue=[];
function unavailable(response,message='El servicio está ocupado. Vuelve a intentarlo.'){
 if(response.destroyed)return;
 response.writeHead(503,{'Content-Type':'application/json','Retry-After':'1','Access-Control-Allow-Origin':'*','Cache-Control':'no-store'});
 response.end(JSON.stringify({error:message}));
}
function dispatch(){
 if(!ready||active)return;
 let next;
 while((next=queue.shift())){
  clearTimeout(next.waitTimer);
  if(next.response.destroyed)continue;
  active={...next,timer:setTimeout(()=>worker.terminate(),5000)};
  worker.postMessage(next.request);return;
 }
}
function startWorker(){
 worker=new Worker(new URL('./worker.mjs',import.meta.url),{resourceLimits:{maxOldGenerationSizeMb:256}});
 worker.on('message',message=>{
  if(message.ready){ready=true;dispatch();return;}
  if(!active)return;
  clearTimeout(active.timer);
  if(!active.response.destroyed){active.response.writeHead(message.status,message.headers);active.response.end(message.body);}
  active=null;dispatch();
 });
 worker.on('error',()=>{});
 worker.on('exit',()=>{
  ready=false;
  if(active){clearTimeout(active.timer);unavailable(active.response);active=null;}
  for(const item of queue.splice(0)){clearTimeout(item.waitTimer);unavailable(item.response);}
  setTimeout(startWorker,1000).unref();
 });
}
startWorker();
const server=http.createServer((req,res)=>{
 if(req.url==='/healthz'||req.url==='/readyz'){
  res.writeHead(ready?200:503,{'Content-Type':'application/json','Cache-Control':'no-store'});
  res.end(JSON.stringify({ready}));return;
 }
 if(req.url.length>4096){res.writeHead(414);res.end();return;}
 if(!['GET','OPTIONS'].includes(req.method)){res.writeHead(405,{'Allow':'GET, OPTIONS'});res.end();return;}
 if(!ready||queue.length>=8){unavailable(res);return;}
 const item={response:res,request:{url:'http://spending.internal'+req.url,method:req.method}};
 item.waitTimer=setTimeout(()=>{
  const index=queue.indexOf(item);
  if(index>=0){queue.splice(index,1);unavailable(res);}
 },5000);
 queue.push(item);dispatch();
});
server.maxConnections=32;
server.headersTimeout=5000;
server.requestTimeout=10000;
server.keepAliveTimeout=2000;
server.listen(Number(process.env.PORT||8080),process.env.HOST||'0.0.0.0');
process.on('SIGTERM',()=>server.close(()=>process.exit(0)));
