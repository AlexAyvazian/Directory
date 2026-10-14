/* GovDir office detail presentation. Same county FIPS as the existing U.S. map.
   Source: https://www.govdir.com — offices and official pages remain attributed.
   No key or personal credentials in the browser. */
(function(){
 'use strict';
 const CACHE=new Map();
 const esc=v=>String(v==null?'':v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
 const url=v=>{try{const u=new URL(String(v));return /^https?:$/.test(u.protocol)?u.href:null;}catch{return null;}};
 const link=(href,label)=>{const u=url(href);return u?'<a href="'+esc(u)+'" target="_blank" rel="noopener noreferrer">'+esc(label)+'</a>':'';};
 const text=(value)=>value?'<span>'+esc(value)+'</span>':'';
 const safeEmail=value=>/^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$/.test(String(value||''))?String(value):null;
 function officeCard(o){
  const bits=[];
  if(o.person?.name)bits.push('<div class="govdirPerson"><strong>'+esc(o.person.name)+'</strong>'+(o.person.title?' · '+esc(o.person.title):'')+'</div>');
  if(o.email&&safeEmail(o.email))bits.push('<div>'+link('mailto:'+o.email,o.email)+'</div>');
  if(o.phone)bits.push('<div><a href="tel:'+esc(String(o.phone).replace(/[^0-9+]/g,''))+'">'+esc(o.phone)+'</a></div>');
  if(o.address)bits.push('<div>'+esc(o.address)+'</div>');
  if(o.url)bits.push('<div>'+link(o.url,'Official office website ↗')+'</div>');
  if(o.person?.source_url)bits.push('<div>'+link(o.person.source_url,'Officeholder source ↗')+'</div>');
  if(o.verified_at||o.verified_status)bits.push('<small>Link '+esc(o.verified_status||'status not provided')+(o.verified_at?' · checked '+esc(o.verified_at):'')+'</small>');
  return '<article class="govdirOffice"><div class="govdirOfficeTitle">'+esc(o.name||'Government office')+'</div>'+(o.kind?'<div class="govdirKind">'+esc(o.kind.replace(/[_-]+/g,' '))+'</div>':'')+bits.join('')+'</article>';
 }
 function resourceCard(r){
  if(!url(r.url))return '';
  return '<div class="govdirResource"><div>'+link(r.url,r.name||'Official resource ↗')+'</div>'+
    (r.description?'<div class="govdirResourceDesc">'+esc(r.description)+'</div>':'')+
    '<small>'+esc(r.publisher||'Source not specified')+(r.official===false?' · Not marked official':'')+(r.verified_at?' · checked '+esc(r.verified_at):'')+'</small></div>';
 }
 function show(target,data){
  const offices=Array.isArray(data.offices)?data.offices:[];
  const resources=Array.isArray(data.resources)?data.resources:[];
  const page=data.jurisdiction?.page_url||'https://www.govdir.com';
  target.innerHTML='<section class="govdirSection" aria-label="Government offices from GovDir">'+
    '<div class="govdirHeading"><strong>Government offices</strong><span>'+offices.length+' offices · '+resources.length+' resources</span></div>'+
    '<div class="govdirAttribution">Via '+link('https://www.govdir.com','GovDir')+' · public government-office directory'+(data.as_of?' · as of '+esc(data.as_of.slice(0,10)):'')+'</div>'+
    (offices.length?'<div class="govdirOffices">'+offices.map(officeCard).join('')+'</div>':'<p class="govdirEmpty">No office details published for this county in GovDir yet.</p>')+
    (resources.length?'<details class="govdirResources"><summary>Official resource links ('+resources.length+')</summary><div>'+resources.map(resourceCard).join('')+'</div></details>':'')+
    '<div class="govdirFooter">'+link(page,'Open GovDir county listing ↗')+'</div>'+
   '</section>';
 }
 async function read(fips){
  const previous=CACHE.get(fips);if(previous&&previous.expires>Date.now())return previous.promise;
  const promise=fetch('/api/govdir/county/'+encodeURIComponent(fips),{headers:{Accept:'application/json'}}).then(async response=>{
   const data=await response.json().catch(()=>({}));
   if(!response.ok)throw new Error(data.error||'Official office directory currently unavailable.');
   return data;
  }).catch(e=>{CACHE.delete(fips);throw e;});
  CACHE.set(fips,{promise,expires:Date.now()+900000});return promise;
 }
 function mount(target,fips){
  if(!target||!/^\d{5}$/.test(String(fips||'')))return;
  target.innerHTML='<section class="govdirSection"><div class="govdirHeading"><strong>Government offices</strong></div><p class="govdirEmpty" role="status">Loading official office directory…</p></section>';
  read(fips).then(data=>{if(target.isConnected)show(target,data);}).catch(e=>{
   if(!target.isConnected)return;
   target.innerHTML='<section class="govdirSection"><div class="govdirHeading"><strong>Government offices</strong></div><p class="govdirEmpty" role="status">'+esc(e.message)+'</p><button class="govdirRetry" type="button">Retry office directory</button></section>';
   target.querySelector('.govdirRetry')?.addEventListener('click',()=>mount(target,fips));
  });
 }
 window.GovDirUI={mount};
})();
