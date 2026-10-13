# Parallel County Registry Research — Split Assignments

Two agents own separate states, so research can proceed concurrently without collisions.

**ChatGPT assigned (25 states):** AL, AR, AZ, CA, CT, DE, IA, KY, LA, MN, MO, MT, NC, ND, NV, OH, OK, OR, PA, RI, TX, UT, VT, WA, WY.

**Claude assigned (26 states/jurisdictions):** AK, CO, DC, FL, GA, HI, ID, IL, IN, KS, MA, MD, ME, MI, MS, NE, NH, NJ, NM, NY, SC, SD, TN, VA, WI, WV.

These states balance the Atlas's 3,155 current per-state `rosterCount` figures (1,577 vs 1,578). The original workbook's 3,144-row count differs by 11; do not conflate these figures or discard rows.

## Faster discovery

`scripts/discover_my_half.py` consumes [CISA .gov registration data](https://github.com/cisagov/dotgov-data) and [GSA non-.gov county listings](https://github.com/GSA/govt-urls). It only processes the ChatGPT-assigned states. The output `data/discovery/my_half_domain_candidates.json` maps domain registrations to county records using state and county name.

The precomputed `data/discovery/gsa_my_half_domain_candidates.json` contains 157 historical GSA-listed county-domain candidates. **These are website/domain leads, not verified live HR directories or employee contacts.** GSA records may be stale.

The job runs when the workflow is added to main and then once daily. It does not modify `data/registries/research-batch.json`, existing county employee records, or either visual design.

Security emails in CISA registration data are deliberately ignored; they are not public HR/procurement employee contacts. Domain matches with ambiguous jurisdiction or county agency type are excluded.

Only promote a source into `data/registries/sources.json` after confirming that the target is a live official staff or departmental directory and automatic access is permitted. Blocked pages remain manual-review items.
