# Priority local government directory research — 14 October 2026

Scope: Human Resources, employee benefits, Risk Management, workplace Safety, Workers' Compensation & Leave, Water/Sewer, Fire, Police, Public Safety, Parks, Housing, Public Utilities, Sanitation, Legal, Procurement, Public Works. **Do not** treat unrelated county auditors or social services as target contacts.

This round used Keenable live page extraction, Keenable SELECT broad semantic source discovery, Parallel Search, and Agentic Search by Liner to identify primary government source material.

## Verified import batches in Neon (`DIRECTORY_DATABASE`, database `neondb`)

| Batch | Public directory records | Email entries | Named people | Jurisdiction locations |
|---|---:|---:|---:|---:|
| `priority-directories-2026-10-14-b` | 51 | 43 | 45 | 8 WI/ID counties |
| `idaho-ioem-2026-10-14` | 44 | 44 | 44 | all 44 Idaho counties |
| `idaho-operational-2026-10-14` | 11 | 9 | 10 | 3 Idaho counties |
| **TOTAL new** | **106** | **96** | **99** | Various overlapping locations |

Each directory record has a source URL and data evidence link to committed JSON. GIS county linkage is geographic only: City of Green Bay, Idaho Falls, Kuna, Dover, Nampa, Caldwell, Bonners Ferry and Rexburg are municipal employers, **not county employees**.

### GitHub source snapshots

- `data/imports/priority-directories-2026-10-14-b/contacts.json` contains named contacts and departmental inboxes from Dane County WI, Oneida County WI, Calumet County WI, Green Bay WI, Idaho Falls ID and Association of Idaho Public Works Professionals.
- `data/imports/idaho-priority-2026-10-14/emergency-management-44-counties.json` contains 44 entries matching the complete Idaho county roster, provided by Idaho Office of Emergency Management.
- `data/imports/idaho-priority-2026-10-14/local-hr-water-utilities-legal.json` has City of Kuna public works / water / sewer, Valley County HR, and City of Dover water/sewer/legal contacts.

### Official source examples

- https://admin.danecounty.gov/contact — named Risk Manager, Safety Coordinator, Purchasing Manager and purchasing agents, with separately published direct emails.
- https://admin.danecounty.gov/risk-management — workers' compensation intake is handled by county Risk Management, with outside nurse line and insurer involved; separate office coordination not inferred.
- https://greenbaywi.gov/m/directory/department?did=10 — HR Director, HR/benefits/occupational-health, Risk Manager and Safety Coordinator, published personal mailboxes and departmental inboxes.
- https://www.oneidacountywi.gov/departments/es/ — HR director plus employee services, with officially stated workers compensation and safety responsibilities.
- https://www.co.calumet.wi.us/557/Human-Resources — county HR staff and departmental inbox; worker compensation explicitly an HR responsibility.
- https://www.idahofallsidaho.gov/m/directory/department?did=35 — water/wastewater, sanitation, public works director, streets and engineering.
- https://www.idahofallsidaho.gov/m/directory/department?did=84 — fire operations, training and battalion chiefs.
- https://idahocities.org/page/AIPWP — named association Public Works officials from multiple municipal employers.
- https://ioem.idaho.gov/county-and-tribal-emergency-managers-contact/ — 44 county emergency-management contacts and separate tribal sovereign government entries. Only county rows imported in this batch.
- https://kunacity.id.gov/m/directory/department?did=14 — municipal public works and water/wastewater staff.
- https://co.valley.id.us/departments/HumanResources/news/category/80 — director and county payroll specialist.
- https://cityofdover.id.gov/city-government/city-officers-staff — city water/sewer employees, maintenance, outside legal counsel.

## Idaho tracking and gaps

`public_sector_research_coverage`: **44 counties × 16 targeted categories = 704 rows**, consisting of **58 partial** and **646 not researched** (0 complete). All 44 have an Emergency Management contact from the statewide roster, but **Public Safety & EMS category remains partial**; this does not identify Police, Fire or EMS district leadership.

Wisconsin's pre-existing 1,152-row checklist was enriched with this batch where precise roles were found; Workers Compensation & Leave in Dane, Oneida, Calumet is marked *responsibility identified, no dedicated WC/leave decision-maker verified*. No county was marked complete.

**Conflicts and caution:**
- Idaho Falls Public Works head differs between the statewide professional association roster and the current Idaho Falls municipal directory; only the more direct city staff listing was used for the current person. The generic Public Works email stays an office inbox.
- Oneida County directory had a mismatched visible vs mailto address for a different employee; that ambiguous employee-email pair was **not imported**.
- Several Idaho Falls emails are Cloudflare-obfuscated on the directory and were decoded only when valid; corrupted/inconsistent strings were excluded, leaving named staff without attributed individual email when uncertain.
- Some Idaho emergency-management entries show generic or agency-domain addresses. Those 44 are **published roster contact addresses**, not necessarily individually owned inboxes.
- City of Dover attorney is outside counsel, not a municipal employee; labeled accordingly.
- Staff for only one municipality in a county does not complete any district/agency census.

## Verify

```sql
SELECT import_id, count(*) AS records, count(*) FILTER(WHERE email<>'') AS with_email
FROM directory_contacts
WHERE import_id IN ('priority-directories-2026-10-14-b','idaho-ioem-2026-10-14','idaho-operational-2026-10-14')
GROUP BY import_id;

SELECT status,count(*) FROM public_sector_research_coverage
WHERE batch_id='id-priority-checklist-2026-10-14'
GROUP BY status;
```

One-time data has been committed to GitHub and written to Neon; browser-side future research status edits do not automatically synchronize back to GitHub.
