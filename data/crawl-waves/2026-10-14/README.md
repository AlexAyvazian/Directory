# 2026-10-14 nationwide government-directory crawl wave

**Live source of truth:** Neon `DIRECTORY_DATABASE` → `neondb`.
**App code:** `Occumed79/Directory`.
**Ownership:** county government → Claude; municipal governments + independent/special districts → GPT.
**State coverage:** all 50 states; DC tracked separately as a district, not five invented counties.
**Jobs:** 50 states × 2 owners × 5 functional families = **500 crawl-queue rows** in `directory_crawl_jobs` (250 Claude / 250 GPT).

## The division of work: no duplicate employer research

| Responsibility | CLAUDE | GPT |
|---|---|---|
| County employee directories | **Own** | No; look up only to disambiguate employer identity |
| County associations and county-admin rosters | **Own** | No |
| City/town/village government employee directories | No | **Own** |
| Municipal leagues and municipal HR/public works/fire/police affiliations | No | **Own** |
| Independent special districts, water/sewer & sanitation authorities | No | **Own** |
| Fire protection, EMS districts, sheriff vs municipal police | County Sheriff/County-run only | Municipal police/fire, independent districts & joint authorities |
| Parks / housing / transit / utilities | County-operated only | City-operated and separately incorporated agencies |
| Overlapping regional state sources | County sections/records only | City/special district sections/records only |
| Exports & imports | Write `data/crawl-waves/2026-10-14/claude/` | Write `data/crawl-waves/2026-10-14/gpt/` |
| Shared database | Stage source evidence, promote verified relevant rows | Same; import IDs must be owner/source-batch unique |

**Never re-label city workers as county employees.** County FIPS maps geography, not employer identity. Name + county alone is never sufficient to deduplicate an employer or a person.

### Target families

1. **workforce** — HR, Risk Management, workers' compensation and leave, benefits, occupational health and safety.
2. **public_safety** — fire, police/sheriff, EMS, emergency management and communications.
3. **utilities** — water, sewer, public utility, sanitation, solid waste, roads/public works.
4. **community** — parks/recreation, housing authorities and related independent boards.
5. **governance** — purchasing/procurement, legal/counsel and contract administration.

Prioritize **named decision-makers or functional owners**, then direct published work email, published phone, and department mailbox as fallback. Elected officials and unrelated human-services caseworkers are NOT proxies for these department functions.

### Collection protocol (both agents)

- **Discover at scale:** state association inventories, municipal-league/utility/fire/housing directories, agency/authority registries, statewide lists and public government datasets; register exact official URLs.
- **Map URLs:** list department and employee profile links for one association or government site first, then batch-scrape *mapped relevant pages*. Never blindly fetch every news, agenda, election or public-information page.
- **Extract:** record `state`, `county`, five-digit county `fips`, `employer_name`, `employer_type` (county|municipality|special_district|regional_authority|state_agency), `agency`, `department`, `name`, `job_title`, `email`, `phone`, `source_url`, `source_checked_at`, `source_status`, and a short `evidence_excerpt`.
- **Source status:** `official_current`, `official_date_unconfirmed`, `association_supplemental`, `historical_reverify`, `email_mismatch_review`, `department_only`, `blocked` or `not_found`. Do not describe inaccessible sites as researched.
- **Personal email attribution:** only attach an email to a named individual when the *same source* explicitly associates them. Cloudflare-decoded but ambiguous, broken mailto, unrelated inbox and email forms are **not** personal email proof.
- **Raw first, live after review:** preserve scraped source and candidate records separately. Check duplicates against Neon by employer identity + department + name + published email; never overwrite a stronger existing source. Promote only accurately sourced relevant contacts to `directory_contacts`.
- **Coverage:** `lead_found_partial` identifies a genuine lead; never declare a county or category complete just because one representative was found. A complete category requires an inventory of actual agencies/districts in the county or an explicitly scoped employer only.
- **Respect public access, robots policies, rate limits and published API licensing.** Never attempt credential bypass or restricted affiliate member directories.

## What exists vs. what is actively crawling

**Completed infrastructure:**
- `server/crawl_queue_schema.sql` defines the persistent work queue and source log.
- Neon queue seeded with **500 pending/discovery/crawl work packages** (only started packages are marked active).
- `nc-carteret-official-municipal-directories.json`: **144 mapped municipal employee-profile URLs** across Beaufort and Newport, both in Carteret County NC.
- Context.dev batch `batch_d8b3fda2ea98f918aeacb66647e2094f` submitted for those **144 URLs**, targeting HR/fire/police/parks/water/sewer/public works/administration/finance. It is a **scrape job**; submissions are not verified contacts.
- Early Context.dev URL-filter pilot batches `batch_6b9f29abcefcbfbfc6dda7e53de76089` (League City TX) and `batch_ecc5aa9bbb62d44110fbc9cee263a449` (Beaufort NC) each returned only **one page**, not a mega-crawl. They are test artifacts; don't call them large successes.
- Firecrawl crawl launches hit 402/429 quota limits; **no Firecrawl page collection succeeded**.
- Context.dev API currently limited concurrent batches; submissions beyond its limit may need queuing, another authorized provider, or additional account capacity.

**NOT yet completed:** automated ingestion of the 144-page batch; broad cross-state contact extraction and verification; full directory completion; a frontend progress display. The 500 work packages are an assigned queue, **not 500 running crawlers**.

## Lane handoff

Claude can begin immediately from Neon queue:
```sql
SELECT job_key, state, family, target_functions, jurisdiction_count, zero_live_jurisdictions, priority
FROM directory_crawl_jobs
WHERE owner='claude' AND status='pending'
ORDER BY priority DESC, state, family;
```

GPT lane:
```sql
SELECT job_key, state, family, target_functions, jurisdiction_count, zero_live_jurisdictions, priority
FROM directory_crawl_jobs
WHERE owner='gpt' AND status='pending'
ORDER BY priority DESC, state, family;
```

Priority states from the **live** zero-contact count include TX, KY, MO, KS, NC, IA, IL, NE, OH, IN and MN. For Claude, the 42 GA counties with no promoted target records remain explicitly high-priority, plus earlier state/county directories. For GPT, target municipalities and independently operated districts in large gaps, beginning TX and NC.

Use a distinct crawl run batch ID, keep logs/results in the database, and set a job to `imported` only after source-level records land in Neon. Confirm import counts with a follow-up SQL query.

## Success metrics

Count only: (a) new named **priority-department** employees with personally associated published email; (b) named owners with official phones; (c) agency-specific office channels separately; (d) newly enumerated distinct government employers; (e) targeted category checks moved from not researched to partially researched *with evidence*. Show blocked/historical/conflicting as a separate backlog.

The quality gate is more important than gross contact volume. This is a nationwide discovery and research process, not a promise that one batch can certify every local-government employee roster.

## Execution reconciliation — NC Carteret municipal employee crawl

The first actual **mapped URL batch completed successfully**:
- Context.dev `batch_d8b3fda2ea98f918aeacb66647e2094f` returned **144/144 successful pages** (84 Town of Beaufort; 60 Town of Newport). Unlike the two pilot attempts, this fetched each individual employee-profile URL.
- Full original profile text and structured records are preserved in `nc-carteret-144-crawled-profiles.json` and stored in Neon `public_sector_research_contacts`, batch `nc-carteret-144-profile-crawl-2026-10-14`.
- A strict filter retained **29 relevant municipal department leaders/operational supervisors**, stored in `nc-carteret-reviewed-operational-leads.json` and Neon `directory_contacts` under import `nc-carteret-municipal-2026-10-14`. Source organizations are correctly listed as **Town of Beaufort** and **Town of Newport**; Carteret County is only the geographic county (FIPS 37031).
- Selected contacts: 4 police command, 8 fire command/leadership, 6 utility/water/wastewater supervisors, 3 public works managers, 3 HR staff, 2 parks/recreation leaders and 3 town administration leaders.
- **Only 1 direct published email** among all 144 scraped profiles. **139 profiles displayed email web forms** (including those selected); web forms are explicitly retained as links and never misrepresented as direct email addresses.
- Neon has **15** Carteret target-function checklist rows from this batch: 6 partial category leads, 9 not researched. No employer or county considered complete.
- Queue reconciled: 4 NC functional jobs marked **imported** (not `done`), government-legal/procurement remains pending; only the utilities entry counts the shared 144 scraped pages to avoid quadruple-counting.
- **Total live contacts now 5,999**, subject to later additions from other agents.

The Context.dev site crawl pilot URL regex matched only the starting page; mapped URL batch extraction solved this. Firecrawl API still returned 402/429 at launch and was not used for the successful 144-page batch. Future batches should map employee-profile URLs and scrape those listed pages, not assume the crawler will traverse a blocked or unusual directory interface.

**Automation still needed:** An ongoing ingestion worker/review UI so completed external crawl batches can be normalized and inserted without manual synchronization; this first batch was reconciled through direct connectors and verified by SQL.

## Execution reconciliation — TX municipal HR association source

The public `https://tmhra.org/leadership/` page lists the current Texas Municipal Human Resources Association board/leadership, with 14 named profiles from 14 municipality employers. This page is **public**; the members-only full TMHRA directory was **not** accessed.

- Committed source snapshot: `texas-municipal-hr-board.json` (**14** names/roles/phone/email as published).
- Research archive: Neon `public_sector_research_contacts`, batch `tx-municipal-hr-board-2026-10-14`, **14** rows.
- After quality filtering: **12** relevant named workforce officials promoted to app directory, **11** with association-published work emails, across **10 geographic county records**. The real employer city is retained separately from county.
- **Two held for review:** LaShon Gros is currently shown as an Assistant City Manager rather than a dedicated HR director; Lindsey Cox has a San Marcos role with an apparent New Braunfels email and inconsistent title in the same source. Neither was promoted as a verified municipal HR personal address.
- Association data is labeled `association_published_named_professional_email`, **not independently confirmed current by each employer**. Each relevant TX county has an explicitly partial HR category record; broader TX municipal coverage remains open.
- Neon queue `nationwide-2026-10-14-v1:TX:municipal_and_district:workforce` is `imported`, **not done**.

**Combined execution to date:** 144 mapped NC employee profile pages extracted, 29 curated municipal operational contacts, 14 TX association source profiles staged, 12 relevant TX officials promoted. These are initial source-bounded results, not a comprehensive 500-job national crawl.
