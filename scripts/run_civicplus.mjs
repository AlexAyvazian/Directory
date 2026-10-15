// Concurrent HTTP/extraction workers feed a single incremental transactional writer.
import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import {createHash, randomUUID} from 'node:crypto';
import path from 'node:path';
import pg from 'pg';
import {initialize, counts, registerInventory, importReport} from './import_civicplus.mjs';

async function main() {
  const args = process.argv.slice(2);
  const option = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
  if (!process.env.DIRECTORY_DATABASE) throw new Error('DIRECTORY_DATABASE is not configured; no production import is possible');
  const inventoryPath = option('--inventory', 'data/civicplus/supplied-inventory.json');
  const output = option('--output');
  if (!output) throw new Error('--output is required');
  await mkdir(output, {recursive: true});
  const inventory = JSON.parse(await readFile(inventoryPath, 'utf8'));
  const mappingPath = option('--mapping');
  const mappings = mappingPath ? JSON.parse(await readFile(mappingPath, 'utf8')) : {};
  const client = new pg.Client({connectionString: process.env.DIRECTORY_DATABASE, connectionTimeoutMillis: 15000});
  await client.connect();
  let child;
  try {
    await initialize(client);
    const before = await counts(client);
    const runId = randomUUID();
    await client.query('INSERT INTO directory_civicplus_runs(run_id,metrics) VALUES($1,$2)', [runId, {before}]);
    const registered = await registerInventory(client, inventory);
    const crawlArgs = ['scripts/crawl_civicplus.py', '--inventory', inventoryPath, '--output', output];
    for (const name of ['--workers', '--per-host', '--delay', '--attempts', '--timeout']) {
      if (args.includes(name)) crawlArgs.push(name, option(name));
    }
    child = spawn(option('--python', 'python3'), crawlArgs, {stdio: ['ignore', 'pipe', 'inherit']});
    const exit = new Promise(resolve => {
      child.once('error', error => resolve({error}));
      child.once('exit', (code, signal) => resolve({code, signal}));
    });
    const metrics = {inserted: 0, updated: 0, duplicates: 0, rejected: 0, failed: 0, new_emails: 0, email_conflicts: 0, reasons: {}, batches: []};
    let sourcesProcessed = 0;
    const lines = createInterface({input: child.stdout});
    for await (const line of lines) {
      const event = JSON.parse(line);
      if (!event.source_key) continue;
      const folder = createHash('sha256').update(event.source_key).digest('hex').slice(0, 20);
      const result = JSON.parse(await readFile(path.join(output, folder, 'result.json'), 'utf8'));
      const batch = await importReport(client, inventory, {results: [result]}, mappings, output);
      for (const key of ['inserted', 'updated', 'duplicates', 'rejected', 'failed', 'new_emails', 'email_conflicts']) metrics[key] += batch[key];
      for (const [key, value] of Object.entries(batch.reasons)) metrics.reasons[key] = (metrics.reasons[key] || 0) + value;
      metrics.batches.push(...batch.batches);
      sourcesProcessed++;
      const progress = {source_key: event.source_key, crawl_status: event.status, inserted: batch.inserted, updated: batch.updated,
        duplicates: batch.duplicates, rejected: batch.rejected, failed: batch.failed};
      console.log(JSON.stringify(progress));
      await client.query('UPDATE directory_civicplus_runs SET metrics=$2 WHERE run_id=$1', [runId, {before, sources_processed: sourcesProcessed, ...metrics}]);
    }
    const outcome = await exit;
    if (outcome.error) throw outcome.error;
    const after = await counts(client);
    const summary = {run_id: runId, target_host: new URL(process.env.DIRECTORY_DATABASE).hostname,
      registered_sources: registered, sources_processed: sourcesProcessed, crawler_exit_code: outcome.code,
      before, ...metrics, after};
    await client.query('UPDATE directory_civicplus_runs SET finished_at=now(),metrics=$2 WHERE run_id=$1', [runId, summary]);
    await writeFile(path.join(output, 'database-report.json'), JSON.stringify(summary, null, 2) + '\n');
    console.log(JSON.stringify(summary, null, 2));
    if (outcome.code !== 0 || sourcesProcessed !== inventory.sources.length || metrics.failed || metrics.rejected) process.exitCode = 2;
  } finally {
    if (child && child.exitCode === null) child.kill('SIGTERM');
    await client.end();
  }
}

main().catch(error => { console.error(error.code || error.message.replace(/postgres(?:ql)?:\/\/\S+/g, '[database]')); process.exitCode = 1; });
