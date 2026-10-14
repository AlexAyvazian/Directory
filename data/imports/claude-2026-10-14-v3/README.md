# 2026-10-14 Claude 26-state directory reconciliation

## Source snapshots — immutable

Uploaded user-provided exports saved verbatim in this folder:

| GitHub file | CSV records | Notes |
| --- | ---: | --- |
| `county_contacts.csv` | 4,661 | 4,158 named rows; 1,760 records containing an email |
| `county_registry_sources.csv` | 2,134 | Source provenance, platform, department, access status |
| `county_research_coverage.csv` | 1,578 | County/source level statuses, **NOT** full department coverage |
| `county_changes.csv` | 4,158 | Source delta/event log, archived (not falsely applied as replacements) |
| `target-gapfill-9-jurisdictions.json` | 27 | Additional current target-department leads in nine originally empty jurisdiction locations |
| `remaining_15_priority_gaps.csv` | 15 | Open Georgia counties requiring named target-department contact research |

The original four exports remain intact. They are not overwritten by the post-import updated coverage statuses.

## Actual Neon reconciliation (project icy-cherry-72017945, neondb)

- **4,661** source contacts retained as raw, provenance-preserving rows in `public_sector_research_contacts`, under batch `claude-statewide-v3-2026-10-14`; **0 unresolved FIPS mappings**. This includes all **786** source rows labeled `historical_lead_requiring_verification` and other peripheral contacts, without pretending they are current.
- **2,134** original source records saved in `public_sector_research_sources`, plus **11** unique official government URLs for the targeted gap-fill; the original access status and source URL are preserved.
- **1,578** source-level county snapshots retained in `public_sector_research_coverage` as statuses beginning `source_snapshot:`. These snapshots remain historical point-in-time baselines, not county research completion.
- **1,924** category-relevant contact rows promoted to `directory_contacts`, with **718** email-bearing rows, **1,729** named people, across **731** jurisdiction records. Breakdown: **792** labeled `officially_listed_by_source`; **937** as `association_supplemental_reverify`; **195** department-only contacts.
- **27** additional directly researched target-department contacts promoted to `directory_contacts` under `target-gapfill-2026-10-14` (**13** published email rows) and a separate 9-jurisdiction status-update batch created.
- The app-facing `directory_contacts` table has **5,948** rows after both imports; existing records were not overwritten.

**Contact source labels reflect the user-supplied CSV's classification.** They do not imply every source and historical job title was independently reverified in this turn. Department/shared inboxes remain independent records when not personally attributed; `county` / `jurisdiction_id` reflect geography or source organization, not that a city employee works for a county.

## Target department checklist

15 target functions tracked: Human Resources; Risk Management; Workers Compensation & Leave; Water / Sewer Districts; Fire Departments & Districts; Police & Sheriff; Public Safety & EMS; Parks & Recreation; Housing Authorities; Public Utilities; Sanitation & Solid Waste; Legal & Counsel; Procurement & Purchasing; Public Works & Roads; Occupational Health & Employee Safety.

- Original WI, SD and ID per-category tracking batches remain untouched. Their other local municipal/special district gaps are not automatically marked complete.
- For the other **1,391 source jurisdictions** (not including DC pseudo-jurisdictions), there are **20,865 active FIPS-disambiguated category checkpoints**: **1,884 partial leads** and **18,981 not researched**. Zero declared complete.
- Five pairs in source CSV have **identical names but distinct FIPS**: Baltimore City vs Baltimore County (MD), and Fairfax, Franklin, Richmond, Roanoke city vs county (VA). The 75 ambiguous name-only checklist rows are marked `ambiguous_name_superseded_by_fips_tasks`, and 150 replacement category records explicitly identify the 10 distinct FIPS jurisdictions. **Never group city/county by name alone.**
- DC's specialized functional pseudo-locations were not used to invent five DC *counties*. DC source records and actual people remain in the import.

## Newly filled initial gaps (9 of 24, PARTIAL leads only)

- **Georgia:** Stephens (HR, fire, 911/EMS, public works, parks, sheriff), Sumter (Risk/Safety office), Thomas (Purchasing), Walton (HR, employee benefits, leave), Union (Purchasing and Fire office channels), Upson (HR Coordinator).
- **Massachusetts:** Nantucket Town & County (named HR director, HR office, Procurement mailbox).
- **New Hampshire:** Hillsborough County (HR Manager, senior generalist and HR assistant; official office number).
- **Virginia:** Charlotte County (Public Safety director).
- Source evidence and exact titles are retained in `target-gapfill-9-jurisdictions.json` and the imported `data` JSONB for each contact.
- **15 still-empty jurisdictions**, all GA: Stewart, Talbot, Taliaferro, Tattnall, Taylor, Towns, Treutlen, Turner, Twiggs, Warren, Webster, Wheeler, Wilcox, Wilkes, Wilkinson. See CSV in this folder. Search snippets can identify tentative leads, but unverified snippets alone were not used to declare these complete.

## Decisions / cautions

- None of the existing stronger contacts was changed or deleted. Import uses original evidence and deduplication; untouched conflicting records remain as separate source snapshots.
- Old clerk/sheriff lists, public-benefits caseworkers, and other nonpriority county personnel are **archived**. Only target-role relevant source entries were promoted to the live directory.
- Some previously recorded source contacts are old or phone-only. Check the `qualityTier`, `sourceStatus`, `sourceUrl`, and source date before outreach. A published office email is **not** proof that a particular staff member owns it.
- A category marked `lead_found_partial` means some evidence exists, **not** that all municipalities, districts, departments, personnel or public offices were reviewed.
- The website/browser view was not independently tested after the Neon merge; database row counts and batch boundaries were queried directly.

## Neon verification SQL

```sql
SELECT import_id, count(*), count(*) FILTER (WHERE email <> '') AS email_rows
FROM directory_contacts
WHERE import_id IN ('claude-statewide-v3-2026-10-14','target-gapfill-2026-10-14')
GROUP BY import_id;

SELECT batch_id, status, count(*)
FROM public_sector_research_coverage
WHERE batch_id IN ('claude-target-checklist-2026-10-14','claude-jurisdiction-disambiguation-2026-10-14')
GROUP BY batch_id,status;
```

## Follow-up — final 15 source-empty Georgia counties (2026-10-14)

All 15 previously source-empty Georgia jurisdictions now have at least one **directly published local emergency-management contact** in the app-facing directory. See:

- `georgia-last-15-emergency-contacts.json` — **15 official GEMA county contact entries**, each with published email and phone; entered as **agency/department contact channels**, not automatically asserted as personally owned mailboxes.
- `georgia-last-15-named-operational-staff.json` — **7 additional named county staff** from first-party county staff/appointed-officials directories (Stewart, Talbot, Twiggs), including emergency management, parks, roads, sheriff, legal counsel and administrative purchasing oversight. No personal email address inferred for contact-form profiles.
- Both snapshots have their own `directory_imports` ids: `ga-last15-emergency-2026-10-14` and `ga-last15-named-2026-10-14`.

**Verified database result:** 22 app-facing records total (15 agency email endpoints plus 7 named people). These span the original 15 source-empty counties. All 20 affected category tasks in the existing `claude-target-checklist-2026-10-14` batch are marked **lead_found_partial**, never complete. Eighteen unique source/county URLs were logged.

**Separate live-directory finding:** The Neon app still has **42 additional GA counties with zero app-facing contact records**, even though each has at least one archived Claude research row. These are not the original 15; they result from excluding nonpriority/historical source records from the main app. They are listed with exact county FIPS in `georgia-remaining-42-live-directory-gaps.csv`. Do not declare Georgia completely covered until actual named HR/Risk/WC/Fire/Water/etc. owner contacts are researched and imported for them.

Additional contacts here are from `gema.georgia.gov`, `talbotcountyga.org`, `stewartcountyga.gov`, and `twiggscounty.us`. In particular, the Talbot county directory uses forms for individual staff emails; GEMA's public emergency management address is retained separately rather than automatically assigned to a specific person's personal inbox.
