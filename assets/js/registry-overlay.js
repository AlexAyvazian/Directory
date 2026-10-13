/* Add official county registry information without deleting or replacing historical research. */
(function () {
  "use strict";
  const atlas = window.ATLAS_DATA;
  if (!atlas || !Array.isArray(atlas.jurisdictions)) return;
  const sources = window.COUNTY_REGISTRY_SOURCES || [];
  const seeds = window.COUNTY_REGISTRY_SEEDS || [];
  const snapshots = (window.COUNTY_REGISTRY_SNAPSHOT || {}).sources || {};
  const norm = s => String(s || "").toLowerCase().replace(/\b(county|city and borough|census area|borough|parish|city)\b/g,"").replace(/[^a-z0-9]/g,"");
  const geo = (state,county) => state + ":" + norm(county);
  const byGeo = new Map(atlas.jurisdictions.map(j => [geo(j.abbr,j.county),j]));
  const stateName = new Map(atlas.states.map(s => [s.abbr,s.name]));
  const ensure = (state,county) => {
    const j = byGeo.get(geo(state,county));
    // Only attach to known roster jurisdictions. Never invent counties.
    return j || null;
  };
  const attachContact = (j,c,isLive) => {
    if (!c.name || !c.title) return false;
    const unique = x => norm(x.name || x.value) + ":" + norm(x.title || x.label);
    const key = unique(c);
    const seed = {
      name:c.name, title:c.title, agency:c.department || "County government",
      email:isLive ? (c.email || "") : "",
      phone:c.phone || "", sourceUrl:c.sourceUrl || "",
      sourceName:isLive?"Official county directory (refreshed)":"Official county directory lead (recheck pending)",
      sourceChecked:isLive?(c.checkedAt || ""):"",
      sourceStatus:isLive?"official-registry-snapshot":"legacy-directory-lead-needs-recheck",
      emailType:isLive&&c.email?"published on staff entry":""
    };
    j.seeds = j.seeds || [];
    const ix = j.seeds.findIndex(x=> unique(x) === key);
    if (ix >= 0) {
      if(isLive) j.seeds[ix] = {...j.seeds[ix],...seed};
      else return false;
    } else j.seeds.push(seed);
    j.contacts = j.contacts || [];
    if (!j.contacts.some(x => norm(x.value) === norm(c.name) && norm(x.label).includes(norm(c.title)))) {
      j.contacts.push({label:(isLive?"Official directory":"Registry research lead")+" · "+c.title,value:c.name});
    }
    return true;
  };
  for (const s of sources) {
    const j = ensure(s.state,s.county);
    if(!j)continue;
    j.registrySources=j.registrySources||[];
    if(!j.registrySources.some(x=>x.url===s.url))j.registrySources.push({url:s.url,department:s.department,id:s.id});
  }
  let leadCount=0,liveCount=0,listedEmails=0;
  for (const c of seeds) {
    const j = ensure(c.state,c.county);
    if(j && attachContact(j,c,false))leadCount++;
  }
  for (const item of Object.values(snapshots)) {
    const j=ensure(item.state,item.county);
    if(!j)continue;
    j.registryCheckedAt=item.checkedAt||null;
    j.registryLastError=item.lastError||null;
    for(const c of item.contacts||[]) {
      if(attachContact(j,{...c,checkedAt:item.checkedAt},true)) {
        liveCount++;
        if(c.email)listedEmails++;
      }
    }
  }
  for(const state of atlas.states){
    state.count = atlas.jurisdictions.filter(j=>j.abbr===state.abbr && j.contacts && j.contacts.length).length;
  }
  window.ATLAS_REGISTRY_METRICS={configuredSources:sources.length,legacyStaffLeads:leadCount,liveContacts:liveCount,publishedEmails:listedEmails};
})();
