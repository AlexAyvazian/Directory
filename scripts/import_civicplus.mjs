import {readFile} from 'node:fs/promises';
import {createHash, randomUUID} from 'node:crypto';
import {pathToFileURL, fileURLToPath} from 'node:url';
import path from 'node:path';
import pg from 'pg';

const root = fileURLToPath(new URL('../', import.meta.url));
const hash = value => createHash('sha256').update(value).digest('hex');
const normalize = value => (value || '').normalize('NFKC').toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
export function profileIdentity(record) {
  if (record.profile_url) {
    const url = new URL(record.profile_url);
    const id = [...url.searchParams].find(([k]) => k.toLowerCase() === 'eid')?.[1];
    if (id && /^\d+$/.test(id)) return `employee:${id}`;
  }
  return `listing:${normalize(record.name)}:${normalize(record.department)}`;
}

export function validateRecord(record) {
  if (!record.name || record.name.trim().split(/\s+/).length < 2 || /\d|@|directory|vacant|vacancy/i.test(record.name)) return 'invalid_person_name';
  if (!record.title && !record.department && !record.email && !record.phone) return 'no_professional_fields';
  if (record.email && !/^[^\s@<>]+@[^\s@<>]+\.[A-Za-z]{2,}$/.test(record.email)) return 'invalid_email';
  if (record.source_status !== 'official_published') return 'unverified_source';
  if (!/^\w{64}$/.test(record.evidence_sha256 || '') || !record.evidence_file) return 'missing_evidence';
  if (!Number.isFinite(Date.parse(record.verified_at))) return 'missing_verification_time';
  try {
    if (!['http:', 'https:'].includes(new URL(record.page_url).protocol)) return 'invalid_page_url';
  } catch { return 'invalid_page_url'; }
  return null;
}

export async function counts(client) {
  const {rows: [row]} = await client.query(`SELECT count(*)::int AS contacts,
    count(*) FILTER (WHERE btrim(email) <> '')::int AS with_email FROM directory_contacts`);
  return row;
}

export async function initialize(client) {
  // The core schema must already exist. Do not initialize an empty production atlas.
  await client.query('SELECT id, state, jurisdiction_id, level, data FROM directory_contacts LIMIT 0');
  await client.query(await readFile(path.join(root, 'server/crawl_queue_schema.sql'), 'utf8'));
  await client.query(await readFile(path.join(root, 'server/civicplus_schema.sql'), 'utf8'));
}

export async function registerInventory(client, inventory) {
  const unique = new Set();
  for (const source of inventory.sources) {
    if (unique.has(source.source_key)) throw new Error('Duplicate source key in inventory');
    unique.add(source.source_key);
    const job = 'civicplus:' + hash(source.source_key).slice(0, 24);
    const evidence = {discovery_method: source.discovery_method, submitted_urls: source.submitted_urls, entry_urls: source.entry_urls};
    await client.query(`INSERT INTO directory_crawl_jobs
      (job_key,wave,state,owner,lane,family,target_functions,source_url,evidence)
      VALUES($1,'civicplus-nationwide','US','gpt','municipal_and_district',$2,$3,$4,$5)
      ON CONFLICT(job_key) DO NOTHING`, [job, source.source_key, ['all_published_professional_contacts'], source.entry_urls[0], evidence]);
    await client.query(`INSERT INTO directory_crawl_sources
      (source_key,job_key,url,source_kind,site_owner,employer_type,evidence)
      VALUES($1,$2,$3,'civicplus_directory',$4,'government_unresolved',$5)
      ON CONFLICT(source_key) DO UPDATE SET
        evidence=directory_crawl_sources.evidence || jsonb_build_object('inventory',$5::jsonb)`,
    [source.source_key, job, source.entry_urls[0], source.host, evidence]);
  }
  return unique.size;
}

async function resolveMapping(client, mapping) {
  if (!mapping) return {reason: 'jurisdiction_mapping_required'};
  if (!mapping.verified_source_url || !mapping.agency || !/^[A-Z]{2}$/.test(mapping.state || '')) return {reason: 'verified_mapping_required'};
  if (mapping.level !== 'county' && mapping.level !== 'state') return {reason: 'municipal_or_district_schema_mapping_required'};
  if (mapping.level === 'county') {
    const {rows} = await client.query('SELECT id,state FROM directory_jurisdictions WHERE id=$1', [mapping.jurisdiction_id]);
    if (rows.length !== 1 || rows[0].state !== mapping.state) return {reason: 'jurisdiction_state_mismatch'};
  } else if (mapping.jurisdiction_id) return {reason: 'state_contact_cannot_have_county'};
  return {mapping};
}

async function verifyEvidence(record, output) {
  const resolved = path.resolve(output, record.evidence_file);
  if (!resolved.startsWith(path.resolve(output) + path.sep)) return 'evidence_outside_crawl_directory';
  try {
    if (hash(await readFile(resolved)) !== record.evidence_sha256) return 'evidence_hash_mismatch';
  } catch { return 'evidence_file_missing'; }
  return null;
}

async function saveRecord(client, record, source, mappingResult, metrics, output) {
  const profile = profileIdentity(record);
  // Redirected final host unifies apex/www and desktop/mobile source identities.
  const verifiedHost = new URL(record.page_url).hostname.toLowerCase();
  const sourceHost = source.host.toLowerCase();
  const alias = h => h.replace(/^www\./, '');
  const hostMismatch = alias(verifiedHost) !== alias(sourceHost);
  const identity = verifiedHost + ':' + profile;
  const recordKey = 'cp:' + hash(identity);
  const reason = validateRecord(record) || (hostMismatch ? 'source_host_mismatch' : null)
    || await verifyEvidence(record, output) || (await Promise.all((record.additional_evidence || []).map(e => verifyEvidence(e, output)))).find(Boolean) || mappingResult.reason;
  await client.query(`INSERT INTO directory_civicplus_records(record_key,source_key,profile_key,status,reason,data)
    VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT(record_key) DO UPDATE SET last_seen=now(),
    data=directory_civicplus_records.data || EXCLUDED.data,
    status=CASE WHEN directory_civicplus_records.status='imported' THEN 'imported' ELSE EXCLUDED.status END,
    reason=CASE WHEN directory_civicplus_records.status='imported' THEN directory_civicplus_records.reason ELSE EXCLUDED.reason END`,
  [recordKey, source.source_key, profile, reason ? 'review' : 'validated', reason || '', record]);
  if (reason) { metrics.rejected++; metrics.reasons[reason] = (metrics.reasons[reason] || 0) + 1; return; }
  const mapping = mappingResult.mapping;
  const {rows: staged} = await client.query('SELECT contact_id FROM directory_civicplus_records WHERE record_key=$1', [recordKey]);
  const contactId = staged[0].contact_id || 'civicplus-' + hash(identity);
  let {rows: existing} = await client.query('SELECT * FROM directory_contacts WHERE id=$1 FOR UPDATE', [contactId]);
  // A shared mailbox alone never establishes employee identity. Match full name,
  // employer, state/scope AND a published email or phone, or exact profile provenance.
  if (!existing.length) {
    const {rows} = await client.query(`SELECT * FROM directory_contacts WHERE state=$1 AND level=$2
      AND jurisdiction_id IS NOT DISTINCT FROM $3 AND lower(btrim(name))=lower(btrim($4))
      AND lower(btrim(agency))=lower(btrim($5)) AND
      ((email<>'' AND lower(email)=lower($6)) OR (phone<>'' AND phone=$7) OR data->>'sourceUrl'=$8)
      FOR UPDATE`, [mapping.state, mapping.level, mapping.jurisdiction_id || null, record.name, mapping.agency, record.email, record.phone, record.profile_url || record.page_url]);
    if (rows.length > 1) {
      metrics.rejected++; metrics.reasons.ambiguous_existing_identity = (metrics.reasons.ambiguous_existing_identity || 0) + 1;
      await client.query("UPDATE directory_civicplus_records SET status='review',reason='ambiguous_existing_identity' WHERE record_key=$1", [recordKey]);
      return;
    }
    existing = rows;
  }
  if (existing.length && normalize(existing[0].name) !== normalize(record.name)) {
    metrics.rejected++;
    metrics.reasons.source_identity_changed = (metrics.reasons.source_identity_changed || 0) + 1;
    await client.query("UPDATE directory_civicplus_records SET status='review',reason='source_identity_changed' WHERE record_key=$1", [recordKey]);
    return;
  }
  const evidence = {file: record.evidence_file, location: record.page_url, sha256: record.evidence_sha256,
    verifiedAt: record.verified_at, profileUrl: record.profile_url, parentDirectoryUrl: source.entry_urls[0]};
  const allEvidence = [evidence, ...(record.additional_evidence || []).map(e => ({file: e.evidence_file, location: e.page_url,
    sha256: e.evidence_sha256, verifiedAt: e.verified_at}))];
  const data = {sourceUrl: record.profile_url || record.page_url, sourceName: 'Official government directory',
    sourceStatus: 'official_published', verifiedAt: record.verified_at, profileUrl: record.profile_url,
    parentDirectoryUrl: source.entry_urls[0], originalSubmittedUrls: source.submitted_urls,
    evidence: allEvidence, publishedContact: record, civicplus: {sourceKey: source.source_key, profileKey: profile}};
  let actualId;
  if (existing.length) {
    const old = existing[0]; actualId = old.id;
    const changed = ['title', 'department', 'email', 'phone'].some(k => !old[k] && record[k]);
    if (old.email && record.email && old.email.toLowerCase() !== record.email.toLowerCase()) metrics.email_conflicts++;
    const priorEvidence = Array.isArray(old.data.evidence) ? old.data.evidence : [];
    const mergedEvidence = [...priorEvidence];
    for (const item of allEvidence) {
      if (!mergedEvidence.some(e => e.sha256 === item.sha256 && e.location === item.location)) mergedEvidence.push(item);
    }
    const mergedData = {...data, ...old.data, evidence: mergedEvidence,
      civicplusSources: [...new Set([...(Array.isArray(old.data.civicplusSources) ? old.data.civicplusSources : []), recordKey])]};
    await client.query(`UPDATE directory_contacts SET
      title=CASE WHEN title='' THEN $2 ELSE title END, department=CASE WHEN department='' THEN $3 ELSE department END,
      email=CASE WHEN email='' THEN $4 ELSE email END, phone=CASE WHEN phone='' THEN $5 ELSE phone END, data=$6 WHERE id=$1`,
    [actualId, record.title, record.department, record.email, record.phone, mergedData]);
    metrics[changed ? 'updated' : 'duplicates']++;
    if (!old.email && record.email) metrics.new_emails++;
  } else {
    actualId = contactId;
    await client.query(`INSERT INTO directory_contacts
      (id,import_id,state,jurisdiction_id,level,agency,department,name,title,email,phone,kind,data)
      VALUES($1,'civicplus-public-directories',$2,$3,$4,$5,$6,$7,$8,$9,$10,'person',$11)`,
    [actualId, mapping.state, mapping.jurisdiction_id || null, mapping.level, mapping.agency,
      record.department, record.name, record.title, record.email, record.phone, data]);
    metrics.inserted++;
    if (record.email) metrics.new_emails++;
  }
  await client.query("UPDATE directory_civicplus_records SET status='imported',contact_id=$2,reason='' WHERE record_key=$1", [recordKey, actualId]);
}

export async function importReport(client, inventory, report, mappings = {}, output = '.') {
  const metrics = {inserted: 0, updated: 0, duplicates: 0, rejected: 0, failed: 0, new_emails: 0, email_conflicts: 0, reasons: {}, batches: []};
  const sources = new Map(inventory.sources.map(s => [s.source_key, s]));
  await client.query(`INSERT INTO directory_imports(id,data) VALUES('civicplus-public-directories',$1) ON CONFLICT(id) DO NOTHING`, [{source: 'Public official government employee directories'}]);
  for (const result of report.results) {
    const source = sources.get(result.source_key);
    if (!source) throw new Error('Crawl result is not registered in supplied inventory');
    const mappingResult = await resolveMapping(client, mappings[source.source_key]);
    let sourceRejected = 0, sourceFailed = 0, sourceImported = 0;
    for (let offset = 0; offset < result.contacts.length; offset += 250) {
      const before = await counts(client);
      const checkpoint = structuredClone(metrics);
      await client.query('BEGIN');
      // Serialize this import family, including dedupe against older import batches.
      await client.query("SELECT pg_advisory_xact_lock(hashtext('directory-civicplus-import'))");
      try {
        for (const record of result.contacts.slice(offset, offset + 250)) await saveRecord(client, record, source, mappingResult, metrics, output);
        await client.query('COMMIT');
      } catch (error) {
        await client.query('ROLLBACK');
        Object.assign(metrics, checkpoint);
        const failed = result.contacts.slice(offset, offset + 250).length;
        metrics.failed += failed; sourceFailed += failed;
        metrics.reasons['database_' + (error.code || 'error')] = (metrics.reasons['database_' + (error.code || 'error')] || 0) + failed;
      }
      sourceRejected += metrics.rejected - checkpoint.rejected;
      sourceImported += metrics.inserted + metrics.updated + metrics.duplicates - checkpoint.inserted - checkpoint.updated - checkpoint.duplicates;
      metrics.batches.push({source_key: source.source_key, before, after: await counts(client)});
    }
    const processed = new Set(result.fetched_profiles);
    const reconciled = result.discovered_profiles.every(id => processed.has(id))
      && !(result.unprocessed_profiles || []).length && !result.errors.length && !result.issues.length;
    const complete = result.status === 'extracted' && reconciled && !sourceRejected && !sourceFailed && sourceImported > 0;
    const status = complete ? 'done' : result.status === 'retry' ? 'retry' : 'reviewing';
    const evidence = {crawlStatus: result.status, startedAt: result.started_at, finishedAt: result.finished_at,
      discoveredProfiles: result.discovered_profiles, fetchedProfiles: result.fetched_profiles,
      unprocessedProfiles: result.unprocessed_profiles, errors: result.errors, issues: result.issues,
      pages: result.pages, importedRecords: sourceImported, rejectedRecords: sourceRejected, failedRecords: sourceFailed};
    await client.query(`UPDATE directory_crawl_sources SET status=$2,page_count=$3,observed_at=now(),
      evidence=evidence || jsonb_build_object('latestCrawl',$4::jsonb) WHERE source_key=$1`,
    [source.source_key, status, result.pages.filter(p => p.status === 200).length, evidence]);
    await client.query(`UPDATE directory_crawl_jobs SET status=$2,scraped_pages=$3,candidate_records=$4,
      imported_records=$5,discovered_urls=$6,evidence=evidence || jsonb_build_object('latestCrawl',$7::jsonb),updated_at=now()
      WHERE job_key=(SELECT job_key FROM directory_crawl_sources WHERE source_key=$1)`,
    [source.source_key, status, result.pages.filter(p => p.status === 200).length, result.contacts.length, sourceImported,
      result.discovered_profiles.length, evidence]);
  }
  return metrics;
}

async function main() {
  const args = process.argv.slice(2);
  const option = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
  if (!process.env.DIRECTORY_DATABASE) throw new Error('DIRECTORY_DATABASE is not configured; no production import is possible');
  const inventory = JSON.parse(await readFile(option('--inventory', 'data/civicplus/supplied-inventory.json'), 'utf8'));
  const reportPath = option('--report');
  const mappingPath = option('--mapping');
  const mappings = mappingPath ? JSON.parse(await readFile(mappingPath, 'utf8')) : {};
  const client = new pg.Client({connectionString: process.env.DIRECTORY_DATABASE, connectionTimeoutMillis: 15000});
  const runId = randomUUID();
  await client.connect();
  try {
    await initialize(client);
    const before = await counts(client);
    await client.query('INSERT INTO directory_civicplus_runs(run_id,metrics) VALUES($1,$2)', [runId, {before}]);
    const registered = await registerInventory(client, inventory);
    const metrics = reportPath ? await importReport(client, inventory, JSON.parse(await readFile(reportPath, 'utf8')), mappings, path.dirname(reportPath)) : {};
    const summary = {run_id: runId, target_host: new URL(process.env.DIRECTORY_DATABASE).hostname,
      registered_sources: registered, before, ...metrics, after: await counts(client)};
    await client.query('UPDATE directory_civicplus_runs SET finished_at=now(),metrics=$2 WHERE run_id=$1', [runId, summary]);
    console.log(JSON.stringify(summary, null, 2));
    if (metrics.failed || metrics.rejected) process.exitCode = 2;
  } finally { await client.end(); }
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  main().catch(error => { console.error(error.code || error.message.replace(/postgres(?:ql)?:\/\/\S+/g, '[database]')); process.exitCode = 1; });
}
