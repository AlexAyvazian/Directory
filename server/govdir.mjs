// Official office-directory data from GovDir (https://www.govdir.com).
// GovDir's public v1 API needs no key. Avoid exposing future credentials in browser code.
const BASE = 'https://api.govdir.com/v1/places/';
export class GovDirError extends Error {
 constructor(message,status=502,retryAfter=null){super(message);this.name='GovDirError';this.status=status;this.retryAfter=retryAfter;}
}
export async function fetchGovDirCounty(fips,{fetchImpl=fetch,maxPages=8}={}) {
 if (!/^\d{5}$/.test(fips)) throw new GovDirError('A valid five-digit county FIPS is required.',400);
 const result={provider:'GovDir',jurisdiction:null,chain:[],offices:[],resources:[],functions:[],sources:[],notices:[],as_of:null,partial:false};
 const seenOffices=new Set(),seenResources=new Set(),seenFunctions=new Set(),seenCursor=new Set();
 let cursor=null;
 for(let page=0;page<maxPages;page++){
  const url=new URL(BASE+'county:'+fips);
  url.searchParams.set('limit','50');
  if(cursor)url.searchParams.set('cursor',cursor);
  let response;
  try { response=await fetchImpl(url,{headers:{Accept:'application/json'},signal:AbortSignal.timeout(12000)}); }
  catch(e){throw new GovDirError('GovDir could not be reached; please retry.',503);}
  if(!response.ok){
   const status=response.status;
   if(status===404)throw new GovDirError('GovDir has no listing for this county yet.',404);
   if(status===429)throw new GovDirError('GovDir has reached its public request limit. Try again later.',429,response.headers.get('Retry-After'));
   throw new GovDirError('GovDir is temporarily unavailable.',status>=500?503:502);
  }
  let payload;
  try { payload=await response.json(); } catch {throw new GovDirError('GovDir returned invalid JSON.',502);}
  if(!payload || !payload.data || typeof payload.data!=='object')throw new GovDirError('GovDir returned an unexpected directory response.',502);
  const d=payload.data;
  result.jurisdiction ||= d.jurisdiction || null;
  if(!result.chain.length&&Array.isArray(d.chain))result.chain=d.chain;
  result.as_of=payload.as_of||result.as_of;
  for(const entry of Array.isArray(d.offices)?d.offices:[]){
    const key=entry.office_id||[entry.name,entry.url].join('|');
    if(!seenOffices.has(key)){seenOffices.add(key);result.offices.push(entry);}
  }
  for(const entry of Array.isArray(d.resources)?d.resources:[]){
    const key=entry.resource_id||[entry.name,entry.url].join('|');
    if(!seenResources.has(key)){seenResources.add(key);result.resources.push(entry);}
  }
  for(const entry of Array.isArray(d.functions)?d.functions:[]){
    const key=entry.function_id||[entry.topic,entry.office_id,entry.jurisdiction_id].join('|');
    if(!seenFunctions.has(key)){seenFunctions.add(key);result.functions.push(entry);}
  }
  if(Array.isArray(payload.sources))result.sources.push(...payload.sources);
  if(Array.isArray(payload.notices))result.notices.push(...payload.notices);
  if(!d.next_cursor)return result;
  if(typeof d.next_cursor!=='string'||seenCursor.has(d.next_cursor))throw new GovDirError('GovDir returned invalid pagination.',502);
  seenCursor.add(d.next_cursor);cursor=d.next_cursor;
 }
 throw new GovDirError('GovDir returned additional pages beyond the supported limit. The listing is not complete.',502);
}
