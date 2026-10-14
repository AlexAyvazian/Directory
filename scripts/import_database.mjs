import {gunzipSync} from 'node:zlib';
import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
import pg from 'pg';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=fileURLToPath(new URL('../',import.meta.url));
const read=p=>readFile(path.join(root,p),'utf8');
const win={};const ctx=vm.createContext({window:win});
for(const f of ['atlas-data','registry-sources','registry-seeds','registry-data','registry-research','fl-association-contacts','registry-overlay'])vm.runInContext(await read(`assets/js/${f}.js`),ctx);
const atlas=win.ATLAS_DATA;
const norm=s=>s.toLowerCase().replace(/\b(county|city and borough|census area|borough|parish|city)\b/g,'').replace(/[^a-z0-9]/g,'');
const byCounty=new Map(atlas.jurisdictions.filter(j=>j.abbr==='MT').map(j=>[norm(j.county),j.id]));
const dir='data/imports/montana-2026-10-13/';
const contacts=JSON.parse(gunzipSync(await readFile(path.join(root,dir+'contacts.json.gz'))));
for(const c of contacts){c.jurisdiction_id=c.level==='county'?byCounty.get(norm(c.county)):null;if(c.level==='county'&&!c.jurisdiction_id)throw new Error(`Unknown Montana county: ${c.county}`);}
const raw=JSON.parse(gunzipSync(await readFile(path.join(root,dir+'raw-sources.json.gz'))));
const coverage=JSON.parse(await read(dir+'coverage.json'));
const client=new pg.Client({connectionString:process.env.DIRECTORY_DATABASE});
await client.connect();
try{
 await client.query('BEGIN');await client.query(await read('server/schema.sql'));
 const metadata={...atlas};delete metadata.jurisdictions;
 await client.query("INSERT INTO directory_metadata VALUES ('atlas',$1) ON CONFLICT(key) DO NOTHING",[metadata]);
 await client.query(`INSERT INTO directory_jurisdictions SELECT x->>'id',x->>'abbr',x->>'county',nullif(x->>'fips',''),x FROM jsonb_array_elements($1::jsonb) x ON CONFLICT(id) DO NOTHING`,[JSON.stringify(atlas.jurisdictions)]);
 await client.query('INSERT INTO directory_imports(id,data) VALUES($1,$2) ON CONFLICT(id) DO NOTHING',['montana-2026-10-13',{coverage,contacts:contacts.length}]);
 await client.query(`INSERT INTO directory_contacts SELECT x->>'id','montana-2026-10-13',x->>'state',x->>'jurisdiction_id',x->>'level',x->>'agency',x->>'department',x->>'name',x->>'title',x->>'email',x->>'phone',x->>'kind',x FROM jsonb_array_elements($1::jsonb) x ON CONFLICT(id) DO NOTHING`,[JSON.stringify(contacts)]);
 const sourceRows=raw.map(r=>({...r,id:crypto.createHash('sha256').update(JSON.stringify(r)).digest('hex')}));
 await client.query(`INSERT INTO directory_source_records SELECT x->>'id','montana-2026-10-13',x->>'file',x->>'location',x->'data' FROM jsonb_array_elements($1::jsonb) x ON CONFLICT(id) DO NOTHING`,[JSON.stringify(sourceRows)]);
 await client.query('COMMIT');console.log(JSON.stringify({contacts:contacts.length,rawRecords:raw.length,jurisdictions:atlas.jurisdictions.length}));
}catch(e){await client.query('ROLLBACK');throw e;}finally{await client.end();}
