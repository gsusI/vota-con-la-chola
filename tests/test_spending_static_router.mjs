import assert from 'node:assert/strict';
import router from '../infra/cloudflare/votaconlachola-worker/src/index.js';
let seen;
const savedFetch=globalThis.fetch;
try {
 globalThis.fetch=async(url)=>{seen=String(url);return new Response('busy',{status:429});};
 const error=await router.fetch(new Request('https://votaconlachola.org/citizen/'));
 assert.equal(seen,'https://raw.githubusercontent.com/gsusI/vota-con-la-chola/gh-pages/citizen/index.html');
 assert.equal(error.status,429);assert.equal(error.headers.get('Cache-Control'),'no-store');
 globalThis.fetch=async(url)=>{seen=String(url);return new Response('source',{headers:{'Content-Type':'application/octet-stream'}});};
 const source=await router.fetch(new Request('https://votaconlachola.org/spending/launch/example.xml'));
 assert.equal(source.headers.get('Content-Type'),'application/xml; charset=utf-8');assert.equal(await source.text(),'source');
 const redirect=await router.fetch(new Request('https://votaconlachola.org/vota-con-la-chola/spending'));
 assert.equal(redirect.status,308);assert.equal(redirect.headers.get('Location'),'https://votaconlachola.org/spending/');
 assert.equal((await router.fetch(new Request('https://votaconlachola.org/',{method:'POST'}))).status,405);
 console.log('PASS: existing proxy paths, redirects, evidence MIME and non-cacheable failures');
}finally {globalThis.fetch=savedFetch;}
