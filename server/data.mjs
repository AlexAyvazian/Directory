export function composeAtlas(metadata, jurisdictions, contacts) {
 const atlas = structuredClone(metadata);
 atlas.jurisdictions = jurisdictions.map(j => structuredClone(j));
 const byId = new Map(atlas.jurisdictions.map(j => [j.id,j]));
 const agencies = new Map();
 for (const c of contacts) {
  if (c.kind === 'review' || c.kind === 'vacancy') continue;
  let j;
  if (c.level === 'state') {
   const key = `${c.state}:${c.agency}`;
   j=agencies.get(key);
   if (!j) { j={id:`state-${c.state}-${encodeURIComponent(c.agency)}`,abbr:c.state,county:c.agency,full:c.agency,level:'state',fips:null,contacts:[],seeds:[],src:'database'}; agencies.set(key,j);atlas.jurisdictions.push(j); }
  } else j=byId.get(c.jurisdiction_id);
  if (!j) throw new Error(`Contact jurisdiction missing: ${c.id}`);
  j.contacts ||= [];
  const label=[c.department,c.title].filter(Boolean).join(' · ');
  const value=[c.name,c.email,c.phone].filter(Boolean).join(' · ');
  if (!j.contacts.some(x=>x.label===label && x.value===value)) j.contacts.push({label,value});
  j.seeds ||= [];
  j.seeds.push({name:c.name || c.title,title:c.name ? c.title : '',agency:c.agency,department:c.department,email:c.email,phone:c.phone,sourceUrl:c.data.sourceUrl || '',sourceName:'Uploaded directory snapshot',sourceStatus:'uploaded-source-snapshot',sourceFile:c.data.evidence.map(e=>e.file+' · '+e.location).join('; ')});
 }
 for(const s of atlas.states){const js=atlas.jurisdictions.filter(j=>j.abbr===s.abbr);s.count=js.filter(j=>j.contacts?.length && j.level!=='state').length;s.stateAgencyCount=js.filter(j=>j.level==='state').length;}
 atlas.database={provider:'Neon',contactCount:contacts.length,stateContactCount:contacts.filter(c=>c.level==='state').length,reviewCount:contacts.filter(c=>c.kind==='review').length};
 return atlas;
}
