CREATE TABLE IF NOT EXISTS directory_metadata (key text PRIMARY KEY, data jsonb NOT NULL);
CREATE TABLE IF NOT EXISTS directory_jurisdictions (id text PRIMARY KEY, state text NOT NULL, county text NOT NULL, fips text, data jsonb NOT NULL);
CREATE INDEX IF NOT EXISTS directory_jurisdictions_state ON directory_jurisdictions(state);
CREATE TABLE IF NOT EXISTS directory_imports (id text PRIMARY KEY, imported_at timestamptz NOT NULL DEFAULT now(), data jsonb NOT NULL);
CREATE TABLE IF NOT EXISTS directory_contacts (id text PRIMARY KEY, import_id text REFERENCES directory_imports(id), state text NOT NULL, jurisdiction_id text REFERENCES directory_jurisdictions(id), level text NOT NULL CHECK(level IN ('county','state')), agency text NOT NULL, department text NOT NULL DEFAULT '', name text NOT NULL DEFAULT '', title text NOT NULL DEFAULT '', email text NOT NULL DEFAULT '', phone text NOT NULL DEFAULT '', kind text NOT NULL, data jsonb NOT NULL, CHECK ((level='state' AND jurisdiction_id IS NULL) OR (level='county' AND jurisdiction_id IS NOT NULL)));
CREATE INDEX IF NOT EXISTS directory_contacts_scope ON directory_contacts(state,level,jurisdiction_id);
CREATE TABLE IF NOT EXISTS directory_source_records (id text PRIMARY KEY, import_id text REFERENCES directory_imports(id), filename text NOT NULL, location text NOT NULL, data jsonb NOT NULL);
