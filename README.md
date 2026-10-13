# County Employee Intelligence Atlas

Occu-Med outreach intelligence for county HR, personnel, risk/benefits, procurement and administrative contacts —
the two existing County Employee Intelligence apps combined into **one application with two views**:

| View | Built from | What it does |
|---|---|---|
| **Map** | `county-employee-intelligence-map-TRUE-MAP.html` | Real U.S. map → click a state → real county boundaries. Hover/click counties for contacts. Role filter recolors counties. Jump-to search. Selected county offers **Open in Directory**. |
| **Directory** | `county-employee-intelligence-map-OLD-DESIGN-RESTORED.html` | Glass-styled state tabs, county chips, contact cards, drawer, search / role filter / sort. No map. |

A **Map | Directory** switch in the top bar shows one view at a time. Both share one dataset and one selection
(state + county): pick a county on the map and the Directory opens on that county's records; switch back and the map
still has the state and county selected. The selection is also kept in the URL hash (`#map/AL/r1`, `#directory/AL`).

## Run it
No build step, no server needed — open `index.html` in a browser (everything, including the map boundaries, is bundled
locally and works offline). Or serve the folder: `python3 -m http.server`.

## Data (nothing sampled or invented)
* **923 Part 1 contact records** — exactly the records embedded in both original HTML files (verified identical to each other and to the app). Never modified.
* **564 more counties from the Part 2 leadership extract** (`extracted_county_leadership_names_and_notes.txt`, from your `Directory` repo): GA, KS, IA, IN, MT, LA, CA, MA, HI, MN, MI, NC, WV and others. It only fills counties with no Part 1 record;
  where a county has both (8: TX, WA, WI), Part 2 is shown alongside as "Part 2 · …" rows. Repeated sections for the same county are merged.
* **17 source-listed seed contacts** (`County_Workforce_Atlas_Seed_Contacts.csv`: name, title, email, phone, source URL) attached to their counties (DeKalb, Gwinnett, Cobb GA; Fresno CA; Van Zandt TX).
  Total with contacts: **1,488** across **46** states.
* **3,144-county master roster** — `County_HR_Contact_Miner_Master_No_Confidence.xlsx` (`Counties_Master` sheet). It supplies official county names,
  the full jurisdiction list and research status, and is the home for researched fields (emails, phones, HR page, notes). Those fields are empty in the
  current file; when populated they appear automatically in cards, the drawer and the map popover.
* The Directory's **All tracked counties** option lists roster counties that have no contacts yet ("contacts pending").

Reconciliation notes
* Connecticut: the contact records are for cities/towns, the roster uses the 2022 planning regions and the map boundaries are the legacy counties.
  City records are shown on the legacy county they sit in (Bridgeport/Danbury/Greenwich/Stamford → Fairfield, Hartford → Hartford, New Haven/Waterbury → New Haven).
* DC: the four department records attach to the District of Columbia on the map.
* Baltimore, St. Louis, Fairfax, Franklin, Richmond, Roanoke exist as both a county and an independent city; contact records attach to the county.
* Alaska's Chugach and Copper River census areas (2019) have no boundary in the bundled atlas, so they appear in the Directory roster but not on the map.

## Updating the data
Edit the files in `data/source/` (records JSON, Part 2 text, seed CSV, spreadsheet), then run `python3 scripts/build_data.py` (needs `openpyxl`) to regenerate `assets/js/atlas-data.js`.

## Layout
```
index.html                 shell: nav + two views
assets/css/atlas.css       shell + navigation
assets/css/map.css         Map styles (original TRUE-MAP CSS, scoped to #view-map)
assets/css/directory.css   Directory styles (original OLD-DESIGN CSS, scoped to #view-dir)
assets/js/app.js           shared state, Map view, Directory view
assets/js/atlas-data.js    generated dataset
assets/vendor/             d3 7.9, topojson-client 3.1, us-atlas 3.0.1 (ISC)
data/source/               your original files + extracted records
```
