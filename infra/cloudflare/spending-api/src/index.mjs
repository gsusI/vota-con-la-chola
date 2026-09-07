import release from './release.json' with { type: 'json' };

const normalize = (s) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
const headers = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Expose-Headers': 'X-Next-Cursor, X-Data-Version, X-Rows-Read', 'X-Content-Type-Options': 'nosniff' };
const json = (data, status=200, extra={}) => new Response(JSON.stringify(data), {status, headers:{...headers,'Content-Type':'application/json; charset=utf-8',...extra}});
let metadata;
let metadataBinding;

function validDate(value) {
 const d=new Date(`${value}T12:00:00Z`);
 return /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(d.getTime()) && d.toISOString().slice(0,10)===value;
}
export function parseQuery(url) {
 const p=url.searchParams;
 for(const key of p.keys()) if(!['authority','supplier','start','end','q','after','limit','kind','version'].includes(key) || p.getAll(key).length!==1) throw new Error('Parámetro no válido.');
 const f={authority:p.get('authority')||'',supplier:p.get('supplier')||'',start:p.get('start')||release.date_min,end:p.get('end')||release.date_max,q:(p.get('q')||'').trim(),after:Number(p.get('after')||0),limit:Number(p.get('limit')||12)};
 if(!validDate(f.start)||!validDate(f.end)||f.start>f.end) throw new Error('Rango de fechas no válido.');
 if(!Number.isSafeInteger(f.after)||f.after<0||f.after>release.rows||!Number.isInteger(f.limit)||f.limit<1||f.limit>200) throw new Error('Paginación no válida.');
 if(f.authority.length>1000||f.supplier.length>1000||f.q.length>80||(f.q.length>0&&f.q.length<2)) throw new Error('La búsqueda debe tener entre 2 y 80 caracteres.');
 if(p.has('version')&&p.get('version')!==release.version) throw new Error('La versión de datos ha cambiado. Recarga la página.');
 return f;
}
function grams(text) {const t=normalize(text),out=new Set();for(let i=0;i<t.length-1;i++)out.add(t.slice(i,i+2));return [...out];}
function postingQuery(q) {return `SELECT ids FROM search_terms WHERE kind=? AND term IN (${grams(q).map(()=>'?').join(',')}) ORDER BY entries LIMIT 1`;}
export function queryPlan(f, meta) {
 const first=meta.days.find(d=>d.date>=f.start);
 const last=meta.days.findLast(d=>d.date<=f.end);
 const lo=first?.first??meta.rows+1, hi=last?.last??0;
 const clauses=['id BETWEEN ? AND ?'], bindings=[lo,hi];
 for(const kind of ['authority','supplier']) if(f[kind]) {
  clauses.push('id IN (SELECT value FROM json_each((SELECT ids FROM entities WHERE kind=? AND name=?)))');
  bindings.push(kind,f[kind]);
 }
 if(f.q) {clauses.push(`id IN (SELECT value FROM json_each((${postingQuery(f.q)}))) AND instr(title_search, ?) > 0`);bindings.push('awards',...grams(f.q),normalize(f.q));}
 return {where:clauses.join(' AND '),bindings,summary:lo>hi?{count:0,amount_cents:0}:{count:hi-lo+1,amount_cents:last.amountThrough-first.amountBefore}};
}
export function csvValue(value) {
 let text=String(value??'');
 if(typeof value==='string' && /^[=+@\t\r-]/.test(text)) text="'"+text;
 return '"'+text.replaceAll('"','""')+'"';
}
async function getMetadata(env) {
 if(metadata && metadataBinding===env.DB) return metadata;
 const row=await env.DB.prepare('SELECT payload FROM metadata WHERE id=1').first();
 const result=JSON.parse(row.payload);
 if(result.version!==release.version||result.rows!==release.rows||result.amount_cents!==release.amount_cents) throw new Error('Data parity failed');
 metadata=result;metadataBinding=env.DB;return result;
}
export async function respond(request, env, ctx={waitUntil:()=>{}}) {
 if(request.method==='OPTIONS') return new Response(null,{status:204,headers:{...headers,'Access-Control-Allow-Methods':'GET, OPTIONS'}});
 if(request.method!=='GET') return json({error:'Método no permitido.'},405,{'Allow':'GET, OPTIONS'});
 const url=new URL(request.url);
 if(!['/v1/status','/v1/options','/v1/awards','/v1/export'].includes(url.pathname)) return json({error:'Ruta no encontrada.'},404);
 let f;
 try {f=parseQuery(url);} catch(e) {return json({error:e.message},400);}
 if(url.pathname==='/v1/options' && !['authority','supplier'].includes(url.searchParams.get('kind'))) return json({error:'Tipo de filtro no válido.'},400);
 const canonical=new URL(url.origin+url.pathname);
 for(const [key,value] of Object.entries(f)) canonical.searchParams.set(key,String(value));
 if(url.pathname==='/v1/options') canonical.searchParams.set('kind',url.searchParams.get('kind'));
 canonical.searchParams.set('version',release.version+'-search-v1');
 const key=new Request(canonical);
 const cache=globalThis.caches?.default;
 if(cache) {const cached=await cache.match(key);if(cached)return cached;}
 try {
  const meta=await getMetadata(env);
  let response,reads=0;
  if(url.pathname==='/v1/status') response=json(release);
  else if(url.pathname==='/v1/options') {
   const kind=url.searchParams.get('kind');
   const result=f.q ? await env.DB.prepare(`SELECT name FROM entities WHERE kind=? AND name IN (SELECT value FROM json_each((${postingQuery(f.q)}))) AND instr(search,?)>0 ORDER BY name LIMIT 30`).bind(kind,kind,...grams(f.q),normalize(f.q)).all() : await env.DB.prepare('SELECT name FROM entities WHERE kind=? ORDER BY name LIMIT 30').bind(kind).all();
   reads=result.meta?.rows_read||0;
   response=json({values:result.results.map(r=>r.name),version:release.version});
  } else {
   const plan=queryPlan(f,meta), exporting=url.pathname==='/v1/export';
   const statements=[env.DB.prepare(`SELECT id,payload FROM awards WHERE ${plan.where} AND id>? ORDER BY id LIMIT ?`).bind(...plan.bindings,f.after,f.limit+1)];
   const needsCount=!exporting && (f.authority||f.supplier||f.q);
   if(needsCount) statements.push(env.DB.prepare(`SELECT COUNT(*) AS count, COALESCE(SUM(amount_cents),0) AS amount_cents FROM awards WHERE ${plan.where}`).bind(...plan.bindings));
   const result=await env.DB.batch(statements);
   reads=result.reduce((s,r)=>s+(r.meta?.rows_read||0),0);
   const records=result[0].results, more=records.length>f.limit, shown=records.slice(0,f.limit);
   const rows=shown.map(r=>JSON.parse(r.payload));
   const next=more?shown.at(-1).id:null;
   if(exporting) {
    const lines=[];
    if(f.after===0)lines.push(meta.csv_keys.map(csvValue).join(','));
    for(const row of rows)lines.push(meta.csv_keys.map(k=>csvValue(row[k])).join(','));
    response=new Response(lines.join('\r\n')+(lines.length?'\r\n':''),{headers:{...headers,'Content-Type':'text/csv; charset=utf-8','Content-Disposition':'attachment; filename="placsp-resultados.csv"','X-Next-Cursor':next===null?'':String(next)}});
   } else response=json({rows,...(needsCount?result[1].results[0]:plan.summary),next_cursor:next,version:release.version});
  }
  response.headers.set('Cache-Control','public, max-age=3600, s-maxage=86400');
  response.headers.set('X-Data-Version',release.version);
  response.headers.set('X-Rows-Read',String(reads));
  if(cache)ctx.waitUntil(cache.put(key,response.clone()));
  return response;
 } catch {
  return json({error:'El servicio de consulta no está disponible temporalmente. Puede haberse agotado la cuota gratuita. Puedes descargar los datos fuente o volver a intentarlo más tarde.'},503,{'Retry-After':'3600','Cache-Control':'no-store'});
 }
}
export default {fetch:respond};
