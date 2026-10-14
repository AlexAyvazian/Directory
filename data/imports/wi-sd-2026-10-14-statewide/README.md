# WI + SD statewide public-sector research (2026-10-14)

Batch added to `Occumed79/Directory` and Neon `DIRECTORY_DATABASE`. Work is separate from Claude's SC/NM research.

## Files
- `wi-access-provider.json`: 175 original WI human-services rows, 158 deduplicated source records.
- `wi-mco-mailboxes.json`: 73 WI DHS designated agency notification endpoints. Two are multi-county regional bodies, not assigned to individual county employers.
- `sd-auditors.json`: official South Dakota Secretary of State roster of 66 county auditors with 66 emails.
- `wi-department-leadership.json`: 32 WI county leadership entries, including HR, finance, legal, safety/emergency, roads and sheriff.

## Neon verification
| Import ID | App records | With emails |
| --- | ---: | ---: |
| wi-human-services-2026-10-14 | 155 | 154 |
| wi-mco-2026-10-14 | 68 | 68 |
| sd-auditors-2026-10-14 | 66 | 66 |
| wi-department-leadership-2026-10-14 | 31 | 27 |
| **Total** | **320** | **315** |

All **72 WI** and **66 SD** counties are represented by at least one lead. The research table retains 329 source records.

Living checklist: **2,208 categories** (138 counties × 16 categories); **149 partial**, **2,059 not researched**, **zero counties complete**. Services not directly researched remain open, including HR, risk, workers compensation, water, fire, police, parks, utilities, housing, sanitation, legal and procurement.

## Provenance and cautions
Each database record retains its official source link. DCF Access and provider entries are human-services contacts, not implied HR officers. A DHS designated MCO contact address is recorded as a department endpoint, not automatically assigned to a person. South Dakota auditors are administration/finance leads, not automatically risk or benefits owners.

Three WI DCF entries were held for review (one vacancy, two apparent email/name mismatches in Richland County). Dodge County Parks director's displayed email conflicts with the sheriff's, so that source entry is held for review rather than attributed as a valid personal address.

Refer to the four committed JSON files for exact URLs, email status, department responsibility and source rows. Future research should upsert additional category-specific leads without certifying county completion.
