# CivicPlus source inventory and execution

`supplied-inventory.json` preserves all **217 submitted URLs**, grouped into **206 exact hosts**. It includes directory entry routes without treating mobile paths lacking `eid`/`did` as employee profiles. Apex and `www` hosts remain separate discoveries until observed redirects establish identity; independent organizations are not merged by vendor. No jurisdiction or employee is invented from a hostname.

`execution-2026-10-15.json` records the executed concurrent pass: **206 attempted sources, zero fetched directory pages, zero fetched profiles, zero extracted or production-imported contacts, 206 requiring retry**. All attempts were denied by proxy or HTTP 403. A representative Bing discovery query was also denied by the proxy. Nationwide live discovery and extraction could not proceed. This is a blocked run, not a completion claim.

The cloud machine has no production `DIRECTORY_DATABASE` binding. Historical production counts (21,722 contacts; 15,968 with email) have **not** been independently verified. The isolated local development database had 2,829 contacts and 1,941 emails both before and after queue registration. All 206 sources were registered locally and marked retry, and a repeat registration added no duplicates. Local queue records are not Neon records. Environment settings contain draft network additions and a requirement for a secure `DIRECTORY_DATABASE` binding; they must be applied before retrying production operations.

## Execution

From the repository root, with Node >=22 and Python 3.12:

```sh
npm ci
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r scripts/requirements-civicplus.txt
```

Use the existing platform-provided database binding; never put a database credential in the command line, source control, or reports. The scripts do not silently fall back to the local database. `DIRECTORY_DATABASE` must be present in the process environment, and the destination must support PostgreSQL connections. An HTTPS proxy secret placeholder cannot substitute for a raw PostgreSQL connection string.

Register the entire source inventory without crawling or importing contacts:

```sh
node scripts/import_civicplus.mjs
```

Run concurrent discovery/extraction and stream each finished source to the incremental database writer:

```sh
node scripts/run_civicplus.mjs --output /workspace/civicplus-runs/current \
  --python /workspace/.venvs/directory/bin/python \
  --mapping /workspace/civicplus-source-mappings.json
```

There is no default page limit. The crawler uses 24 global request slots, at most two per host, connection reuse, a minimum host interval, three attempts for transient failures, and exponential backoff. It respects robots rules, HTTP 429 and Retry-After. Long waits, access denials, failed pages, hash mismatches, unparsed profiles, forms, and JavaScript navigation leave sources retrying or awaiting review. It does not bypass restrictions or label a homepage fetch complete. Browser rendering is not implemented; rendering-dependent pages remain explicitly unresolved. Publicly published mailto and Cloudflare-encoded email are parsed; email patterns and contact forms never become inferred addresses.

The source mapping file is keyed by `source_key`, with `state`, `level`, `agency`, `verified_source_url`, and, for counties, an existing `jurisdiction_id`. Populate it from official source evidence and an actual database jurisdiction lookup. Missing or inconsistent mappings are staged for review. The checked-in contact schema permits only `county`/`state`; municipalities and districts are staged with `municipal_or_district_schema_mapping_required` rather than mislabeled. Inspect the live production constraints before implementing a compatible broader jurisdiction migration. This crawler does not claim to have completed that migration.

To crawl independently of the database or retry selected hosts:

```sh
python scripts/crawl_civicplus.py --output /workspace/civicplus-runs/current
python scripts/crawl_civicplus.py --output /workspace/civicplus-runs/current --host accgov.com
node scripts/import_civicplus.mjs --report /workspace/civicplus-runs/current/report.json \
  --mapping /workspace/civicplus-source-mappings.json
```

Successful evidence files are hash-checked and reused on resume with their original verification timestamps; failed URLs are retried. `profiles_fetched` counts requests made in the current run, while `profiles_processed` includes cached profiles. Each result preserves submitted URLs, directory/profile provenance, publication timestamps, and raw HTML hashes. Restrict output directories to trusted operators; they contain the same public professional details as the source pages.

## Data integrity and coverage

`server/civicplus_schema.sql` adds staging/evidence and run metrics without changing existing contacts or schema constraints. Queue registration preserves submitted URL evidence. Source/profile IDs are deterministic across desktop/mobile forms; redirected final hosts and verified identity checks prevent repeat imports. Imports serialize this family of writers and commit batches of at most 250 records. Existing nonblank emails, names, titles and phones are preserved, evidence is merged, and changed employee identity is quarantined. Multiple possible existing matches require review. Each contact batch records before/after database counts, and inserted, enriched, duplicate, rejected, failed and email-conflict counts are separate. The runner persists progress after each completed source.

Only sources with a drained frontier, reconciled profile results, no fetch/extraction issues, and fully accepted imports become `done`. Listing-only contacts without independently linked profiles remain dependent on the site's published navigation. Dynamic filters/postbacks require review. No approach here guarantees discovery of staff the site does not expose through readable links; sources that need browser coverage remain unresolved.

`report.json` and `database-report.json` are machine-readable execution reports. Exit code 2 means unresolved source coverage, rejected records, or failed imports; it is not a fully successful scrape. Missing database access exits 1. The production database totals must be read by the importer after the binding and network access are usable. New directories beyond the supplied inventory have not yet been discovered or verified because search/network access is blocked.

## Tests

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/civicplus.test.mjs
```

The Node PostgreSQL integration test is skipped without `CIVICPLUS_TEST_DATABASE`. To execute it, provide an **isolated local** PostgreSQL database in that variable and select the Python interpreter with `CIVICPLUS_PYTHON` if needed. It creates/drops only its own random test schema. Tests cover live local HTTP traversal, pagination, concurrency, retries, robots restrictions, evidence reuse/tampering, database staging, idempotency, preservation, rollback, and the complete HTTP-to-database pipeline. Synthetic fixtures never enter production.
