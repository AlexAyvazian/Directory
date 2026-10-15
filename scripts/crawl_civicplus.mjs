import pg from 'pg';
import { createHash } from 'node:crypto';

const connectionString = process.env.DIRECTORY_DATABASE || process.env.DATABASE_URL;
if (!connectionString) throw new Error('Set DIRECTORY_DATABASE or DATABASE_URL');
const db = new pg.Pool({ connectionString, max: 2, connectionTimeoutMillis: 12000 });
const IMPORT = 'civicplus-crawler-2026';
const MAX_SITES = Math.min(250, Math.max(1, Number(process.env.MAX_SITES || 40)));
const SEARCHES = Math.min(50, Math.max(0, Number(process.env.MAX_SEARCHES || 12)));
const DELAY = Math.max(1500, Number(process.env.REQUEST_DELAY_MS || 2500));
const STATES = 'AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split(' ');
const pause = n => new Promise(resolve => setTimeout(resolve, n));
const hash = x => createHash('sha256').update(String(x)).digest('hex').slice(0,32);
const norm = x => String(x || '').toLowerCase().replace(/[^a-z0-9]/g, '');
const decode = x => String(x || '').replace(/&#x([a-f0-9]+);/gi, (_, n) => String.fromCodePoint(parseInt(n, 16))).replace(/&#([0-9]+);/g, (_, n) => String.fromCodePoint(Number(n))).replace(/&amp;/gi, '&').replace(/&nbsp;/gi, ' ').replace(/&quot;/gi, '"').replace(/&apos;|&#39;/gi, "'");
const clean = x => decode(String(x || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ')).trim();
const emailOK = x => /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i.test(x);
const urlOK = x => { try { const u = new URL(x); return /^https?:$/.test(u.protocol) && /^\/m\/directory\/?$/i.test(u.pathname) && !/localhost|127\.0\.0\.1/i.test(u.hostname); } catch { return false; } };

async function request(url, accept = 'text/html') {
  const abort = new AbortController();
  const timeout = setTimeout(() => abort.abort(), 20000);
  try {
    const response = await fetch(url, { signal: abort.signal, headers: { 'User-Agent': 'OccuMedDirectory/1.0 (+public directory indexing; limited requests)', 'Accept': accept } });
    return response;
  } finally { clearTimeout(timeout); }
}

async function robotsAllowed(url) {
  const u = new URL(url);
  try {
    const response = await request(u.origin + '/robots.txt', 'text/plain');
    if (response.status === 404 || response.status === 410) return true;
    if (!response.ok) return false;
    const rules = (await response.text()).split(/\r?\n/);
    let applicable = false, disallowed = [];
    for (const line of rules) {
      const m = line.replace(/#.*$/, '').match(/^\s*(user-agent|disallow)\s*:\s*(.*)/i);
      if (!m) continue;
      if (m[1].toLowerCase() === 'user-agent') applicable = m[2].trim() === '*';
      if (applicable && m[1].toLowerCase() === 'disallow' && m[2].trim()) disallowed.push(m[2].trim().split('*')[0]);
    }
    return !disallowed.some(path => path && u.pathname.startsWith(path));
  } catch { return false; }
}

function cards(html) {
  const markers = [...html.matchAll(/<li\b[^>]*class=["'][^"']*\blist-group-item\b[^"']*["'][^>]*>/gi)];
  const result = [];
  for (let i = 0; i < markers.length; i++) {
    const block = html.slice(markers[i].index, markers[i+1]?.index ?? html.length);
    const find = regex => clean(block.match(regex)?.[1] || '');
    const name = find(/<a\b[^>]*class=["'][^"']*\bfw-bold\b[^"']*["'][^>]*>([\s\S]*?)<\/a>/i);
    if (!name || name.length > 130) continue;
    const title = find(/<div\b[^>]*class=["'][^"']*\bd-sm-block\b[^"']*["'][^>]*>([\s\S]*?)<\/div>/i);
    const department = find(/<ul\b[^>]*class=["'][^"']*\bdepartments\b[^"']*["'][^>]*>[\s\S]*?<a\b[^>]*>([\s\S]*?)<\/a>/i);
    const email = decode(block.match(/href=["']mailto:([^"']+)/i)?.[1] || '').split('?')[0].trim();
    const phone = decode(block.match(/href=["']tel:([^"']+)/i)?.[1] || '').replace(/,$/, '').trim();
    result.push({ name, title, department, email: emailOK(email) ? email : '', phone });
  }
  return result;
}

async function findSites() {
  const row = await db.query("SELECT COALESCE((data->>'offset')::int,0) AS n FROM directory_imports WHERE id=$1", [IMPORT]);
  const offset = Number(row.rows[0]?.n || 0);
  let found = new Set();
  for (let i = 0; i < SEARCHES; i++) {
    const state = STATES[(offset + i) % STATES.length];
    const query = '"Staff Directory" "CivicEngage" "County" "' + state + '" inurl:m/directory';
    const url = 'https://www.bing.com/search?format=rss&q=' + encodeURIComponent(query);
    try {
      const response = await request(url, 'application/rss+xml');
      if (response.ok) {
        const feed = await response.text();
        for (const hit of feed.matchAll(/<link>(https?:\/\/[^<]+)<\/link>/g)) {
          const candidate = decode(hit[1]);
          if (urlOK(candidate)) found.add(candidate);
        }
      }
    } catch (e) { console.warn('Search skipped', state, e.message); }
    await pause(500);
  }
  for (const url of found) {
    await db.query('INSERT INTO directory_source_records(id,import_id,filename,location,data) VALUES($1,$2,$3,$4,$5) ON CONFLICT(id) DO NOTHING',
      ['cp-site-' + hash(url.toLowerCase()), IMPORT, 'search-discovered-directory', new URL(url).hostname, { url, format: 'modern', source: 'public search index' }]);
  }
  await db.query('UPDATE directory_imports SET data=data||$2::jsonb WHERE id=$1',
    [IMPORT, JSON.stringify({ offset: (offset + SEARCHES) % STATES.length, lastSearch: new Date().toISOString(), searchHits: found.size })]);
  return found.size;
}

async function writePerson(j, url, person) {
  const record = { ...person, state: j.state, county: j.county, jurisdictionId: j.id, siteUrl: url,
    verifiedAs: 'Published in county staff directory; current position and email deliverability unverified',
    seenAt: new Date().toISOString() };
  await db.query('INSERT INTO directory_source_records(id,import_id,filename,location,data) VALUES($1,$2,$3,$4,$5) ON CONFLICT(id) DO UPDATE SET data=EXCLUDED.data',
    ['cp-card-' + hash(j.id + '|' + norm(person.name) + '|' + norm(person.department)), IMPORT, 'civicengage-staff-card', j.county, record]);
  const existing = await db.query('SELECT id FROM directory_contacts WHERE jurisdiction_id=$1 AND lower(name)=lower($2) ORDER BY id LIMIT 1', [j.id, person.name]);
  if (existing.rows.length) {
    await db.query("UPDATE directory_contacts SET email=CASE WHEN email='' THEN $2 ELSE email END, phone=CASE WHEN phone='' THEN $3 ELSE phone END, data=data||$4::jsonb WHERE id=$1",
      [existing.rows[0].id, person.email, person.phone, JSON.stringify({ civicplusSource: url, lastObserved: record.seenAt })]);
    return 'enriched';
  }
  if (!/[\p{L}].+\s+[\p{L}]/u.test(person.name)) return 'source_only';
  await db.query('INSERT INTO directory_contacts(id,import_id,state,jurisdiction_id,level,agency,department,name,title,email,phone,kind,data) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13) ON CONFLICT(id) DO NOTHING',
    ['cp-person-' + hash(j.id + '|' + norm(person.name)), IMPORT, j.state, j.id, 'county', 'County of ' + j.county, person.department || 'County Staff',
      person.name, person.title, person.email, person.phone, 'person', record]);
  return 'added';
}

async function main() {
  await db.query('INSERT INTO directory_imports(id,data) VALUES($1,$2) ON CONFLICT(id) DO NOTHING',
    [IMPORT, { purpose: 'CivicEngage public government directory discovery and contact extraction' }]);
  const discovered = await findSites();
  const counties = (await db.query('SELECT id,state,county FROM directory_jurisdictions')).rows;
  const rows = await db.query("SELECT DISTINCT data->>'url' AS url FROM directory_source_records WHERE data->>'url' ILIKE '%/m/directory%'");
  const sites = rows.rows.map(r => r.url).filter(urlOK);
  let checked = 0, completed = 0, failed = 0, staff = 0, added = 0;
  for (const url of sites) {
    if (checked >= MAX_SITES) break;
    const statusID = 'cp-run-' + hash(url.toLowerCase());
    const prior = await db.query('SELECT data FROM directory_source_records WHERE id=$1', [statusID]);
    const priorData = prior.rows[0]?.data;
    if (priorData?.status === 'complete' && Date.now() - Date.parse(priorData.at) < 30*86400000) continue;
    checked++;
    let status = 'failed', count = 0;
    try {
      if (!await robotsAllowed(url)) throw Error('robots.txt does not permit a fetch');
      const response = await request(url);
      if (!response.ok) throw Error('HTTP ' + response.status);
      const html = await response.text();
      const title = clean(html.match(/<title[^>]*>([\s\S]*?)<\/title>/i)?.[1] || '');
      const match = title.match(/Staff Directory\s*[•|-]\s*(.+?)\s+County,\s*([A-Z]{2})\s*[•|-]\s*CivicEngage/i);
      if (!match) throw Error('Could not verify county and state');
      const matches = counties.filter(c => c.state === match[2] && norm(c.county) === norm(match[1]));
      if (matches.length !== 1) throw Error('County identity ambiguous');
      const people = cards(html);
      if (!people.length) throw Error('Directory returned no contact cards');
      for (const person of people) { if (await writePerson(matches[0], url, person) === 'added') added++; }
      count = people.length; staff += count; completed++; status = 'complete';
    } catch (e) { failed++; console.warn(url, e.message); }
    await db.query('INSERT INTO directory_source_records(id,import_id,filename,location,data) VALUES($1,$2,$3,$4,$5) ON CONFLICT(id) DO UPDATE SET data=EXCLUDED.data',
      [statusID, IMPORT, 'civicplus-crawl-status', new URL(url).hostname, { url, status, count, at: new Date().toISOString() }]);
    console.log(JSON.stringify({ url, status, people: count }));
    await pause(DELAY);
  }
  console.log(JSON.stringify({ complete: true, discovered, checked, completed, failed, staff, added }));
}
try { await main(); } finally { await db.end(); }
