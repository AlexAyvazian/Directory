# Claude research intake — nine counties — 2026-10-14

**Source batch:** `claude-nine-counties-2026-10-14`
**Neon:** `DIRECTORY_DATABASE`, database `neondb`

## Inputs (unchanged research content)

- `contacts.json` and `contacts.csv` — two representations of the same 310 contact records; do **not** import both as separate contacts.
- `coverage_checklist.csv` — 89 county/department research checkpoints, including work still needed.
- `directory_sources.csv` — 100 source records, including inaccessible sources and supplemental associations.

The source batch spans Anoka and Dakota (MN); Clay, Greene and Jackson (MO); Ward, Burleigh, Grand Forks and Cass (ND).

Of the 310 source records, 237 have `kind=person`, 66 `kind=department`, and 7 `kind=board_member`. **153 rows contain emails**, including shared departmental addresses; this is not a count of 153 personal emails.

## Database tables / reconciliation

- `public_sector_research_contacts` — **310** immutable source rows, including `email_status`, `original_level`, original agency, phone, full notes, URL, and complete `raw_record`.
- `public_sector_research_coverage` — **89** rows, including the source `status`, `remaining_gap`, and `next_action`. These are checkpoints, not completed-county certifications.
- `public_sector_research_sources` — **100** source records, with `access_status`.
- `public_sector_research_snapshots` — one batch manifest.
- `directory_contacts` — **300** app-facing records for this batch; exact source records are retrievable in the research tables.

There are **11** historical, undated, conflicted, or suspicious-email entries held in source/review tables instead of displaying them as current people:

- Greene purchasing contacts from an undated flyer;
- Greene facilities names from an undated newsletter;
- Burleigh's conflicting finance titles;
- Cass's historical finance-page entry;
- Greene's mismatched decoded `vbell@` email.

One Jackson county counselor record had a named official and a **shared office mailbox** in a single source row. The app-facing import separates it into a department mailbox entry and a named official with no assigned personal email. This explains 300 display records from 299 promoted source rows.

**Independent-agency ownership is preserved:** rows for special districts, park boards, detention centers, housing authorities, health zones and other non-county employers carry their original `level`, their actual `agency`, and an agency-prefixed department label in the app-facing directory. Geographic county is only their directory location.

## Open work

- Anoka (MN): directory robots restrictions.
- Dakota (MN): shared mailboxes are **not** personal department-head addresses.
- Grand Forks (ND): county staff emails are often form-only; contact completeness is partial.
- Ward and Cass (ND): water boards not yet researched.
- Grand Forks (ND): parks contact gap.
- Jackson and Greene (MO): additional department pages / blocked access.
- Greene (MO) purchasing and Burleigh (ND) finance: unresolved title/source conflicts.

The original Claude research remains the source of these statements. This import does **not** independently certify contact accuracy.

## SQL verification

```sql
SELECT COUNT(*) FROM public_sector_research_contacts WHERE batch_id='claude-nine-counties-2026-10-14'; -- 310
SELECT COUNT(*) FROM public_sector_research_coverage WHERE batch_id='claude-nine-counties-2026-10-14'; -- 89
SELECT COUNT(*) FROM public_sector_research_sources WHERE batch_id='claude-nine-counties-2026-10-14'; -- 100
SELECT COUNT(*) FROM directory_contacts WHERE import_id='claude-nine-counties-2026-10-14'; -- 300
```

**Synchronization:** This is a completed one-time GitHub + Neon import. Research/checklist updates are not yet automatically bidirectionally synced from the browser to Neon or GitHub.
