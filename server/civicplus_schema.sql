-- Additive intake/evidence. Existing contact rows, constraints and research stay intact.
CREATE TABLE IF NOT EXISTS directory_civicplus_records (
  record_key text PRIMARY KEY,
  source_key text NOT NULL REFERENCES directory_crawl_sources(source_key),
  profile_key text NOT NULL,
  status text NOT NULL DEFAULT 'pending',
  contact_id text REFERENCES directory_contacts(id),
  reason text NOT NULL DEFAULT '',
  data jsonb NOT NULL,
  first_seen timestamptz NOT NULL DEFAULT now(),
  last_seen timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS directory_civicplus_pending ON directory_civicplus_records(status, source_key);
CREATE TABLE IF NOT EXISTS directory_civicplus_runs (
  run_id text PRIMARY KEY,
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  metrics jsonb NOT NULL DEFAULT '{}'::jsonb
);
