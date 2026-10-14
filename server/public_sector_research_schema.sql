-- Multi-state government directory research intake, additive only.
CREATE TABLE IF NOT EXISTS public_sector_research_contacts (
 record_id text PRIMARY KEY, batch_id text NOT NULL, state text NOT NULL, county text NOT NULL,
 jurisdiction_id text, agency text, department text, person_name text, job_title text,
 email text, phone text, kind text, original_level text, source_url text, checked_at text,
 email_status text, notes text, raw_record jsonb NOT NULL, imported_at timestamptz DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public_sector_research_coverage (
 record_id text PRIMARY KEY, batch_id text NOT NULL, state text NOT NULL, county text NOT NULL,
 department_or_function text, responsible_organization text, directory_url text, status text,
 staff_profiles_examined text, contacts_found text, emails_found text,
 remaining_gap text, next_action text, raw_record jsonb NOT NULL, imported_at timestamptz DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public_sector_research_sources (
 record_id text PRIMARY KEY, batch_id text NOT NULL, state text NOT NULL, county text NOT NULL,
 url text, description text, platform text, access_status text, checked_at text,
 raw_record jsonb NOT NULL, imported_at timestamptz DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public_sector_research_snapshots (
 batch_id text PRIMARY KEY, source_folder text NOT NULL, contact_count integer NOT NULL,
 coverage_count integer NOT NULL, source_count integer NOT NULL,
 import_notes text, imported_at timestamptz DEFAULT now()
);
