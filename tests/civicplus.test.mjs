import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, writeFile, readFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {createHash, randomUUID} from 'node:crypto';
import pg from 'pg';
import http from 'node:http';
import {spawn} from 'node:child_process';
import {profileIdentity, validateRecord, initialize, registerInventory, importReport, counts} from '../scripts/import_civicplus.mjs';

test('Desktop/mobile route identity and validation reject fabricated/incomplete source records', () => {
  assert.equal(profileIdentity({profile_url: 'https://example.gov/Directory.aspx?EID=12'}),
    profileIdentity({profile_url: 'https://example.gov/m/directory/employee?eid=12'}));
  assert.equal(validateRecord({name: 'Vacant Position'}), 'invalid_person_name');
  assert.equal(validateRecord({name: 'Fixture Person', email: 'Email Form'}), 'invalid_email');
});

const database = process.env.CIVICPLUS_TEST_DATABASE;
test('PostgreSQL: inventory, idempotency, enrichment, quarantine, evidence and rollback', {skip: !database}, async t => {
  assert(['localhost', '127.0.0.1'].includes(new URL(database).hostname), 'Integration test requires an isolated local database');
  const client = new pg.Client({connectionString: database});
  await client.connect();
  const schema = 'civicplus_test_' + randomUUID().replaceAll('-', '');
  const dir = await mkdtemp(path.join(tmpdir(), 'civicplus-evidence-'));
  try {
    await client.query(`CREATE SCHEMA ${schema}`);
    await client.query(`SET search_path TO ${schema}`);
    await client.query(await readFile(new URL('../server/schema.sql', import.meta.url), 'utf8'));
    await initialize(client);
    await client.query("INSERT INTO directory_jurisdictions VALUES('fixture-county','MT','Fixture County','30001','{}')");
    const source = {source_key: 'civicplus:example.gov', host: 'example.gov', discovery_method: 'test_fixture',
      submitted_urls: ['https://example.gov/Directory.aspx', 'https://example.gov/m/directory'], entry_urls: ['https://example.gov/Directory.aspx']};
    const inventory = {sources: [source]};
    await registerInventory(client, inventory);
    await registerInventory(client, inventory);
    assert.equal((await client.query('SELECT count(*)::int AS n FROM directory_crawl_sources')).rows[0].n, 1);
    assert.equal((await client.query('SELECT evidence FROM directory_crawl_sources')).rows[0].evidence.submitted_urls.length, 2);
    const evidence = '<main>TEST FIXTURE ONLY: Fixture Person, Director, fixture@example.gov</main>';
    await writeFile(path.join(dir, 'evidence.html'), evidence);
    const record = {name: 'Fixture Person', title: 'Director', department: 'Safety', email: 'fixture@example.gov', phone: '555-123-4567',
      source_status: 'official_published', evidence_sha256: createHash('sha256').update(evidence).digest('hex'), evidence_file: 'evidence.html',
      verified_at: new Date().toISOString(), profile_url: 'https://example.gov/Directory.aspx?EID=1', page_url: 'https://example.gov/Directory.aspx?EID=1'};
    const result = {source_key: source.source_key, status: 'extracted', contacts: [record], pages: [{status: 200}],
      discovered_profiles: ['employee:1'], fetched_profiles: ['employee:1'], unprocessed_profiles: [], errors: [], issues: []};
    const report = {results: [result]};
    const mappings = {[source.source_key]: {state: 'MT', level: 'county', jurisdiction_id: 'fixture-county', agency: 'Fixture County',
      verified_source_url: 'https://example.gov/Directory.aspx'}};
    await t.test('Unmapped records are staged without guessing geography', async () => {
      const metrics = await importReport(client, inventory, report, {}, dir);
      assert.equal(metrics.rejected, 1);
      assert.equal((await counts(client)).contacts, 0);
      assert.equal((await client.query('SELECT status FROM directory_crawl_sources')).rows[0].status, 'reviewing');
    });
    await t.test('Verified mapped records are inserted once across desktop/mobile forms', async () => {
      const first = await importReport(client, inventory, report, mappings, dir);
      assert.equal(first.inserted, 1); assert.equal(first.new_emails, 1);
      record.profile_url = 'https://example.gov/m/directory/employee?eid=1';
      const second = await importReport(client, inventory, report, mappings, dir);
      assert.equal(second.inserted, 0); assert.equal(second.duplicates, 1); assert.equal(second.new_emails, 0);
      assert.deepEqual(await counts(client), {contacts: 1, with_email: 1});
      assert.equal((await client.query('SELECT status FROM directory_crawl_sources')).rows[0].status, 'done');
    });
    await t.test('Richer manually reviewed fields and evidence survive enrichment', async () => {
      await client.query("UPDATE directory_contacts SET title='Reviewed Title',phone='',data=data || '{\"reviewed\":true}'::jsonb");
      record.title = 'New title'; record.email = '';
      const enriched = await importReport(client, inventory, report, mappings, dir);
      assert.equal(enriched.updated, 1); assert.equal(enriched.new_emails, 0);
      const {rows: [contact]} = await client.query('SELECT * FROM directory_contacts');
      assert.equal(contact.title, 'Reviewed Title'); assert.equal(contact.email, 'fixture@example.gov');
      assert.equal(contact.phone, '555-123-4567'); assert.equal(contact.data.reviewed, true);
      assert.equal(contact.data.evidence.length, 1);
    });
    await t.test('Unresolved municipality never becomes a fake county/state contact', async () => {
      const municipalMapping = {[source.source_key]: {...mappings[source.source_key], level: 'municipal'}};
      const metrics = await importReport(client, inventory, report, municipalMapping, dir);
      assert.equal(metrics.rejected, 1);
      assert.equal(metrics.reasons.municipal_or_district_schema_mapping_required, 1);
      assert.equal((await counts(client)).contacts, 1);
    });
    await t.test('Evidence tampering blocks import', async () => {
      await writeFile(path.join(dir, 'evidence.html'), 'tampered');
      const metrics = await importReport(client, inventory, report, mappings, dir);
      assert.equal(metrics.reasons.evidence_hash_mismatch, 1);
      await writeFile(path.join(dir, 'evidence.html'), evidence);
    });
    await t.test('A reused profile ID cannot enrich a different employee', async () => {
      const oldName = record.name;
      record.name = 'Replacement Employee';
      const metrics = await importReport(client, inventory, report, mappings, dir);
      assert.equal(metrics.reasons.source_identity_changed, 1);
      assert.equal(metrics.updated, 0);
      assert.equal((await client.query('SELECT name FROM directory_contacts')).rows[0].name, oldName);
      record.name = oldName;
    });
    await t.test('A failed batch rolls back writes and counters, leaves source incomplete', async () => {
      await client.query(`CREATE FUNCTION reject_fixture() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'test failure'; END $$`);
      await client.query('CREATE TRIGGER fail_fixture BEFORE UPDATE ON directory_contacts FOR EACH ROW EXECUTE FUNCTION reject_fixture()');
      const metrics = await importReport(client, inventory, report, mappings, dir);
      assert.equal(metrics.failed, 1); assert.equal(metrics.inserted, 0); assert.equal(metrics.duplicates, 0);
      assert.equal((await client.query('SELECT status FROM directory_crawl_sources')).rows[0].status, 'reviewing');
      assert.deepEqual(await counts(client), {contacts: 1, with_email: 1});
      await client.query('DROP TRIGGER fail_fixture ON directory_contacts');
    });
    await t.test('The runner streams real HTTP extraction through the transactional writer', async () => {
      const server = http.createServer((req, res) => {
        res.writeHead(200, {'Content-Type': 'text/html'});
        if (req.url === '/robots.txt') return res.end('User-agent: *\nAllow: /\n');
        if (req.url === '/Directory.aspx') return res.end('<a href="/m/directory/employee?eid=2">Profile</a>');
        res.end('<main><h2>Integration Employee</h2><p>Title: Clerk</p><a href="mailto:integration@example.test">Email</a></main>');
      });
      await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
      try {
        const url = `http://127.0.0.1:${server.address().port}/Directory.aspx`;
        const source = {source_key: 'civicplus:127.0.0.1', host: '127.0.0.1', discovery_method: 'test_fixture', submitted_urls: [url], entry_urls: [url]};
        const invPath = path.join(dir, 'inventory.json'), mapPath = path.join(dir, 'mapping.json');
        await writeFile(invPath, JSON.stringify({sources: [source]}));
        await writeFile(mapPath, JSON.stringify({[source.source_key]: {...mappings['civicplus:example.gov'], verified_source_url: url}}));
        const child = spawn(process.execPath, ['scripts/run_civicplus.mjs', '--inventory', invPath, '--mapping', mapPath,
          '--output', path.join(dir, 'run'), '--python', process.env.CIVICPLUS_PYTHON || 'python3', '--delay', '0'],
        {env: {...process.env, DIRECTORY_DATABASE: database, PGOPTIONS: `-c search_path=${schema}`, NO_PROXY: '127.0.0.1,localhost'}, stdio: ['ignore', 'pipe', 'pipe']});
        let out = '', err = '';
        child.stdout.on('data', data => out += data); child.stderr.on('data', data => err += data);
        const status = await new Promise((resolve, reject) => { child.on('error', reject); child.on('exit', resolve); });
        assert.equal(status, 0, out + '\n' + err);
        const summary = JSON.parse(await readFile(path.join(dir, 'run/database-report.json'), 'utf8'));
        assert.equal(summary.inserted, 1); assert.equal(summary.new_emails, 1); assert.equal(summary.sources_processed, 1);
        assert.deepEqual(await counts(client), {contacts: 2, with_email: 2});
      } finally { await new Promise(resolve => server.close(resolve)); }
    });
  } finally {
    await client.query('SET search_path TO public');
    await client.query(`DROP SCHEMA ${schema} CASCADE`);
    await client.end();
    await rm(dir, {recursive: true, force: true});
  }
});
