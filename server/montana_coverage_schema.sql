-- Montana public-sector outreach research: normalized contact and checklist staging tables.
-- Existing national atlas schema and legacy contacts are not altered.
CREATE TABLE IF NOT EXISTS montana_public_contacts (
  contact_key text PRIMARY KEY,
  county text NOT NULL,
  organization text NOT NULL,
  category text NOT NULL,
  person_name text NOT NULL DEFAULT '',
  job_title text NOT NULL DEFAULT '',
  email text NOT NULL DEFAULT '',
  phone text NOT NULL DEFAULT '',
  source_url text NOT NULL DEFAULT '',
  notes text NOT NULL DEFAULT '',
  source_batch text NOT NULL,
  original_record jsonb NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS montana_public_contacts_county_idx ON montana_public_contacts(county);
CREATE INDEX IF NOT EXISTS montana_public_contacts_category_idx ON montana_public_contacts(category);
CREATE TABLE IF NOT EXISTS montana_county_coverage (
  county text NOT NULL,
  category text NOT NULL,
  status text NOT NULL,
  recorded_contacts integer NOT NULL DEFAULT 0,
  known_agencies text NOT NULL DEFAULT '',
  source_examples text NOT NULL DEFAULT '',
  research_notes text NOT NULL DEFAULT '',
  last_updated text NOT NULL DEFAULT '',
  source_batch text NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (county, category)
);
CREATE INDEX IF NOT EXISTS montana_county_coverage_status_idx ON montana_county_coverage(status);
CREATE TABLE IF NOT EXISTS montana_research_snapshots (
  snapshot_id text PRIMARY KEY,
  raw_directory jsonb NOT NULL,
  raw_tracker jsonb NOT NULL,
  imported_at timestamptz NOT NULL DEFAULT now()
);
