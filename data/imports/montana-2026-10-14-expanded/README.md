# Montana public-sector research — 2026-10-14 expanded snapshot

This batch contains **350 public contact/agency records**, spanning all **56 Montana counties** plus seven statewide records, and **1,176 county-by-category coverage rows** (56 counties × 21 agency categories).

## Source files

- `contacts-and-progress.json`: complete 350-record contact snapshot and evolving tracker state, including research notes and agency inventory.
- `coverage-checklist.csv`: 1,176 county/category statuses, contacts counted, source examples and notes.
- `newly-researched-contacts.csv`: later-stage contact additions with verification notes.
- `standalone-directory.html`: self-contained interactive directory and editable offline checklist.

## Neon synchronization

Database: `DIRECTORY_DATABASE` (Neon project `icy-cherry-72017945`), database `neondb`.

The versioned schema is `server/montana_coverage_schema.sql`.

| Table | Expected count | Function |
| --- | ---: | --- |
| `montana_public_contacts` | 350 | Original public contact records (includes 7 statewide records) |
| `montana_county_coverage` | 1,176 | Granular checklist for 56 counties × 21 categories |
| `montana_research_snapshots` | 1 | Full JSON source snapshot and tracker for recovery |
| `directory_contacts` | 283 *new* | New records inserted into the live application directory |

The 283 live app records correspond to this batch under `import_id='montana-2026-10-14-expanded'`. **67 contacts were already in the app and were not duplicated**. Existing nationwide data remains untouched.

Montana's mapping for `directory_jurisdictions` uses `Anaconda–Deer Lodge → Deer Lodge`, `Butte–Silver Bow → Silver Bow`, and `Lewis & Clark → Lewis and Clark`. Statewide contacts use `level='state'` and no county jurisdiction ID.

**Important:** The offline HTML's local edits do not automatically post back to Neon, and GitHub does not automatically receive new checklist changes. Until a write API with authentication and a synchronization workflow is added, subsequent research should explicitly update Neon and commit a refreshed GitHub snapshot. Do not mark a county 'complete' when it has only a single contact.

## Verification queries

```sql
SELECT count(*) FROM montana_public_contacts;
SELECT count(*) FROM montana_county_coverage;
SELECT count(*) FROM directory_contacts WHERE import_id = 'montana-2026-10-14-expanded';
SELECT status,count(*) FROM montana_county_coverage GROUP BY status;
```
