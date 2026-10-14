-- Nationwide coordinated public government directory crawl queue.
-- Additive: never alters existing contacts, coverage or historical source records.
CREATE TABLE IF NOT EXISTS directory_crawl_jobs (
  job_key text PRIMARY KEY,
  wave text NOT NULL,
  state text NOT NULL,
  owner text NOT NULL CHECK (owner IN ('claude','gpt')),
  lane text NOT NULL CHECK (lane IN ('county_government','municipal_and_district')),
  family text NOT NULL,
  target_functions text[] NOT NULL,
  jurisdiction_count integer NOT NULL DEFAULT 0,
  zero_live_jurisdictions integer NOT NULL DEFAULT 0,
  priority integer NOT NULL DEFAULT 0,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','discovering','crawling','extracted','reviewing','imported','blocked','needs_account','retry','done')),
  source_url text,
  crawl_id text,
  discovered_urls integer NOT NULL DEFAULT 0,
  scraped_pages integer NOT NULL DEFAULT 0,
  candidate_records integer NOT NULL DEFAULT 0,
  imported_records integer NOT NULL DEFAULT 0,
  error_note text,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (wave,state,lane,family)
);
CREATE INDEX IF NOT EXISTS directory_crawl_queue_next ON directory_crawl_jobs(owner,status,priority DESC,state);
CREATE TABLE IF NOT EXISTS directory_crawl_sources (
  source_key text PRIMARY KEY,
  job_key text NOT NULL REFERENCES directory_crawl_jobs(job_key),
  url text NOT NULL,
  source_kind text NOT NULL,
  site_owner text NOT NULL DEFAULT '',
  employer_type text NOT NULL,
  status text NOT NULL DEFAULT 'discovered',
  page_count integer NOT NULL DEFAULT 0,
  crawl_id text,
  observed_at timestamptz DEFAULT now(),
  notes text NOT NULL DEFAULT '',
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS directory_crawl_sources_job ON directory_crawl_sources(job_key,status);
