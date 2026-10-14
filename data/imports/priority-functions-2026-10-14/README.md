# Priority department research — Wisconsin & South Dakota (2026-10-14)

**Purpose:** Research exactly the employer departments requested: Human Resources, Risk Management, workers' compensation and leave, water/sewer districts, fire, police/sheriff, public safety/EMS, parks, housing, utilities, sanitation/solid waste, legal/counsel, procurement and related Public Works. Government human-services leads and county auditors alone do not qualify those categories.

## Source files and app results
All five snapshots in this folder are stored in **Occumed79/Directory** and imported to Neon **DIRECTORY_DATABASE/neondb**, `directory_contacts.import_id='priority-functions-2026-10-14'`.

| File | App records | Scope |
| --- | ---: | --- |
| `sd-risk-management.json` | 50 | 48 state agency risk representatives, state Risk office mailbox and Risk Director; **not** county HR/Risk contacts. |
| `wi-state-procurement.json` | 62 | State agency purchasing / contracting contacts with published phones, generally no direct emails. |
| `municipal-fire-water-public-works-and-risk.json` | 10 | Tea fire leadership; Johnson Creek water, sewer, public works; Waunakee roads; WI state Risk/WC offices. |
| `wi-brown-county-2026-directory.json` | 16 | Brown County 2026-27 Risk, HR, Benefits, Sheriff, Emergency Management, Public Safety Communications, Parks, Legal, Procurement, Highway and Solid Waste staff. |
| `wi-sd-county-and-city-hr-procurement-utilities-parks.json` | 21 | Custer HR; Sturgis city HR; Kenosha and Calumet procurement; Harrisburg city water, wastewater, parks and roads. |
| **TOTAL** | **159** | **28** records with published emails; the remainder have names and phones or state/department contact information. |

State breakdown: **69 SD** (50 statewide agencies, 19 geographic county records) and **90 WI** (64 statewide agencies, 26 geographic county records). Contacts for municipalities are attributed to the actual municipal employer, not falsely presented as county government employees.

## Checklist progress
The previously created 2,208-row Wisconsin/South Dakota county/category checklist is being maintained in `public_sector_research_coverage`. As of import verification:
- **170** category checkpoints have a partial lead, including prior imports;
- **2,038** category checkpoints remain unresearched;
- **0** entire counties are declared complete.

State-level Risk and Procurement rosters are **not** counted as county-level category completion. Having three City of Tea fire chiefs in Lincoln County, for instance, does not complete research of other fire districts. Published official department inboxes are not assigned to named people without evidence. Brown County HR manager Kara Navin and benefits manager Luke Newton are named separately from `BC_Human_Resources@browncountywi.gov`.

## Verification and limitations
- Every contact has a recorded source URL and source status. Twelve particularly important sources are also logged in `public_sector_research_sources`.
- Historical or ambiguous information is not silently fixed or extrapolated.
- The WI procurement roster did not yield valid purchasing contacts for **10 agency rows** through the strict name/phone extractor; those remain unprocessed, not deemed absent.
- SD risk contacts generally list **names and phone numbers**; do not invent individual emails.
- Independent municipalities are geographically indexed by county but retain their actual employer names.
- Brown County's directory is labeled **2026–27**; its department ownership descriptions are used to identify Risk vs. HR vs. Procurement responsibilities.
- Workers' Compensation contacts from state agencies do not establish county-level work-comp ownership.
- Not all departments are represented in this batch. Unfinished categories include municipal and rural fire districts, independent water/sewer utilities, housing authorities, and further HR/Risk/Legal/Procurement contacts.

## Verify in Neon
```sql
SELECT state,level,count(*) FROM directory_contacts WHERE import_id='priority-functions-2026-10-14' GROUP BY state,level;
SELECT count(*) FROM directory_contacts WHERE import_id='priority-functions-2026-10-14'; -- 159
SELECT state,status,count(*) FROM public_sector_research_coverage
 WHERE batch_id IN('wi-human-services-2026-10-14','sd-auditors-2026-10-14')
 GROUP BY state,status;
```

## Highest-yield directory discovered for next pass
**South Dakota Municipal League:** Its published 2026 access prospectus states a **$100 / year** directory account for a searchable list of individual municipal employees. It can filter by **department, employer, title/position**, and displays **title, email, phone, address**. This is particularly promising for city Fire, Police, HR, Public Works, utilities and procurement research.

Official prospectus: https://cdn.ymaws.com/sdmunicipalleague.org/resource/resmgr/services/non-municipal-opportunities.pdf

**Do not assume API access or bulk export rights.** No account was purchased or accessed. A research source was logged in Neon with `paid access required` status.

Additional research leads logged in Neon: Wisconsin PSC annual utility/sanitary district filings, Wisconsin DWD Workers Compensation directory, Wisconsin State Fire Chiefs Association listserv. None of these is counted as a verified named department contact until extracted and checked.
