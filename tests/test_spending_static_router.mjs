import assert from 'node:assert/strict';
import router from '../infra/cloudflare/votaconlachola-worker/src/index.js';

// Minimal in-memory stand-in for an R2 bucket binding.
function fakeBucket(objects) {
 const reads=[];
 const meta=(key,body)=>({key,size:body.length,httpEtag:`"etag-${key}"`,writeHttpMetadata(h){h.set('content-type','application/octet-stream');h.set('cache-control','private');}});
 return {reads,
  async head(key){reads.push(['head',key]);return key in objects?meta(key,objects[key]):null;},
  async get(key,opts={}){reads.push(['get',key]);
   if(!(key in objects))return null;
   const body=objects[key];const m=meta(key,body);
   const h=opts.onlyIf;
   if(h&&h.get&&h.get('if-none-match')===m.httpEtag)return m;
   const r=opts.range&&opts.range.get&&opts.range.get('range');
   if(r){const [s,e]=r.replace('bytes=','').split('-').map(Number);return {...m,range:{offset:s,length:e-s+1},body:body.slice(s,e+1)};}
   return {...m,body};}};
}
const env={SITE:fakeBucket({
 'site/citizen/index.html':'<h1>citizen</h1>',
 'site/spending/launch/example.xml':'<x/>',
 'site/404.html':'<h1>missing</h1>',
 [`site/policy-outcomes/evidence/${'a'.repeat(64)}/manifest.json`]:'{}',
 'site/data/table.parquet':'0123456789',
})};
const get=(path,init)=>router.fetch(new Request(`https://votaconlachola.org${path}`,init),env,{waitUntil(){}});

const page=await get('/citizen/');
assert.equal(page.status,200);assert.equal(await page.text(),'<h1>citizen</h1>');
assert.equal(page.headers.get('content-type'),'text/html; charset=utf-8');
assert.equal(page.headers.get('cache-control'),'public, max-age=300, stale-while-revalidate=86400');
assert.equal(page.headers.get('x-vclc-origin'),'r2');
assert.equal(page.headers.get('x-content-type-options'),'nosniff');
assert.equal(page.headers.get('etag'),'"etag-site/citizen/index.html"');

const source=await get('/spending/launch/example.xml');
assert.equal(source.headers.get('content-type'),'application/xml; charset=utf-8');assert.equal(await source.text(),'<x/>');

const pinned=await get(`/policy-outcomes/evidence/${'a'.repeat(64)}/manifest.json`);
assert.equal(pinned.headers.get('cache-control'),'public, max-age=31536000, immutable');

const missing=await get('/nope.json');
assert.equal(missing.status,404);assert.equal(await missing.text(),'<h1>missing</h1>');assert.equal(missing.headers.get('cache-control'),'no-store');

const partial=await get('/data/table.parquet',{headers:{range:'bytes=2-5'}});
assert.equal(partial.status,206);assert.equal(partial.headers.get('content-range'),'bytes 2-5/10');assert.equal(await partial.text(),'2345');

const notModified=await get('/citizen/',{headers:{'if-none-match':'"etag-site/citizen/index.html"'}});
assert.equal(notModified.status,304);

const head=await get('/data/table.parquet',{method:'HEAD'});
assert.equal(head.status,200);assert.equal(head.headers.get('content-length'),'10');

assert.equal((await get('/a%2F..%2Fsecret.txt')).status,400);

const redirect=await get('/vota-con-la-chola/spending');
assert.equal(redirect.status,308);assert.equal(redirect.headers.get('Location'),'https://votaconlachola.org/spending/');
assert.equal((await get('/',{method:'POST'})).status,405);

const unbound=await router.fetch(new Request('https://votaconlachola.org/citizen/'),{},{});
assert.equal(unbound.status,503);assert.equal(unbound.headers.get('cache-control'),'no-store');

assert.ok(!env.SITE.reads.some(([,key])=>!key.startsWith('site/')),'every read stays under site/');
console.log('PASS: R2 origin paths, redirects, evidence MIME, ranges, conditionals and non-cacheable failures');
