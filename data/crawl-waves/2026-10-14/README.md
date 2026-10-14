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
