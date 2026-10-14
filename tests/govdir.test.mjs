import test from 'node:test';
import assert from 'node:assert/strict';
import {fetchGovDirCounty, GovDirError} from '../server/govdir.mjs';

test('GovDir combines all county office and resource pages without duplicate records', async () => {
 const seen=[];
 const fakeFetch=async url => {
  const u=new URL(url); seen.push(u);
  const later=u.searchParams.has('cursor');
  return new Response(JSON.stringify({
   data:{
    jurisdiction:{name:'Gallatin County',jurisdiction_id:'county:30031',state:'MT'},
    offices:later?[{office_id:'second',name:'Roads',url:'https://county.gov/roads'},{office_id:'first',name:'Duplicate'}]:[{office_id:'first',name:'Clerk',email:'clerk@county.gov',person:{name:'County Clerk'}}],
    resources:later?[{resource_id:'resource2',name:'Official Roads Page',url:'https://county.gov/roads'}]:[{resource_id:'resource1',name:'Official GIS Page',url:'https://county.gov/gis'}],
    next_cursor:later?null:'next-token'
   },as_of:'2026-10-14',sources:[],notices:[]
  }),{status:200,headers:{'Content-Type':'application/json'}});
 };
 const out=await fetchGovDirCounty('30031',{fetchImpl:fakeFetch});
 assert.equal(out.offices.length,2);
 assert.equal(out.resources.length,2);
 assert.equal(out.jurisdiction.name,'Gallatin County');
 assert.equal(out.offices[0].person.name,'County Clerk');
 assert.equal(seen[0].pathname,'/v1/places/county:30031');
 assert.equal(seen[0].searchParams.get('limit'),'50');
 assert.equal(seen[1].searchParams.get('cursor'),'next-token');
});

test('GovDir rejects invalid FIPS without making a request', async () => {
 await assert.rejects(()=>fetchGovDirCounty('../admin',{fetchImpl:async()=>{throw Error('never call');}}),e=>e instanceof GovDirError && e.status===400);
});

test('GovDir surfaces rate limits instead of inventing offices', async () => {
 await assert.rejects(()=>fetchGovDirCounty('30031',{fetchImpl:async()=>new Response(JSON.stringify({detail:'Too many requests'}),{status:429,headers:{'Retry-After':'60'}})}),e=>e instanceof GovDirError && e.status===429 && e.retryAfter==='60');
});

test('GovDir does not silently treat partial pagination as complete',async ()=>{
 await assert.rejects(()=>fetchGovDirCounty('30031',{maxPages:1,fetchImpl:async()=>new Response(JSON.stringify({data:{offices:[],resources:[],next_cursor:'another-page'}}),{status:200})}),e=>e instanceof GovDirError && e.status===502);
});
