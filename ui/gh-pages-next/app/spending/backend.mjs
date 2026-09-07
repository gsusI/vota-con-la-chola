export const SPENDING_API = 'https://api.votaconlachola.org';
export function queryUrl(path, filters = {}) {
 const url=new URL(path,SPENDING_API);
 for(const [key,value] of Object.entries(filters)) if(value!=='' && value!==undefined && value!==null) url.searchParams.set(key,String(value));
 return url.href;
}
export async function searchOptions(kind, q, signal, version) {
 if(q.length===1) return [];
 const response=await fetch(queryUrl('/v1/options',{kind,q,version}),{signal});
 if(!response.ok) throw new Error('No se pudieron consultar las opciones.');
 return (await response.json()).values;
}
