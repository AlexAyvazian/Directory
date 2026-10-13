#!/usr/bin/env python3
"""Reconcile the three source datasets into assets/js/atlas-data.js.

Sources (all in data/source/):
  records_from_html.json  - the 923 contact records embedded in both original HTML apps (identical in both)  [src "p1"]
  extracted_county_leadership_names_and_notes.txt - Part 2 leadership extract (594 counties); used for counties with no Part 1 record  [src "p2"]
  County_Workforce_Atlas_Seed_Contacts.csv - source-listed contacts with email/phone/source URL, attached to their county as "seeds"
  County_HR_Contact_Miner_Master_No_Confidence.xlsx - 3,144-row county roster (Counties_Master sheet)
Geometry:  assets/vendor/us-atlas-counties-albers-10m.js (used only to attach FIPS codes for the map)

Usage: python3 scripts/build_data.py
"""
import json, re, os, csv, openpyxl
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'data', 'source')

STATE_FIPS = {"AL":"01","AK":"02","AZ":"04","AR":"05","CA":"06","CO":"08","CT":"09","DE":"10","DC":"11","FL":"12","GA":"13","HI":"15","ID":"16","IL":"17","IN":"18","IA":"19","KS":"20","KY":"21","LA":"22","ME":"23","MD":"24","MA":"25","MI":"26","MN":"27","MS":"28","MO":"29","MT":"30","NE":"31","NV":"32","NH":"33","NJ":"34","NM":"35","NY":"36","NC":"37","ND":"38","OH":"39","OK":"40","OR":"41","PA":"42","RI":"44","SC":"45","SD":"46","TN":"47","TX":"48","UT":"49","VT":"50","VA":"51","WA":"53","WV":"54","WI":"55","WY":"56"}

# Connecticut: the contact records are for cities/towns, the spreadsheet uses the 2022 planning regions, and the
# boundary file uses the legacy counties. City records are attached to the legacy county they sit in so they show on the map.
CT_CITY_TO_COUNTY_FIPS = {"Bridgeport":"09001","Danbury":"09001","Greenwich":"09001","Stamford":"09001",
                          "Hartford":"09003","New Haven":"09009","Waterbury":"09009"}
DC_FIPS = "11001"

def norm(n):
    n = n.lower().replace('saint ', 'st ').replace('st. ', 'st ').replace('ste. ', 'ste ')
    n = re.sub(r'\b(county|parish|borough|census area|municipality|city and borough|city)\b', '', n)
    return re.sub(r'[^a-z0-9]', '', n)

def is_city_type(full):
    return bool(re.search(r'\bcity\b', full or '', re.I)) and not re.search(r'city and borough|carson city', full or '', re.I)

records = json.load(open(os.path.join(SRC, 'records_from_html.json')))
STATE_NAME = {x['abbr']: x['name'] for x in records['states']}
atlas_js = open(os.path.join(ROOT, 'assets/vendor/us-atlas-counties-albers-10m.js')).read()
atlas = json.loads(atlas_js[atlas_js.index('{'):atlas_js.rindex('}') + 1])
atl = {}
for g in atlas['objects']['counties']['geometries']:
    atl.setdefault(g['id'][:2], {}).setdefault(norm(g['properties']['name']), []).append(g['id'])

wb = openpyxl.load_workbook(os.path.join(SRC, 'County_HR_Contact_Miner_Master_No_Confidence.xlsx'), read_only=True)
rows = list(wb['Counties_Master'].iter_rows(values_only=True))
hdr = rows[0]
xrows = [dict(zip(hdr, r)) for r in rows[1:]]

def pick(fips_list, full):
    if len(fips_list) == 1: return fips_list[0]
    want_city = is_city_type(full)
    c = [f for f in fips_list if (int(f[2:]) >= 500) == want_city]
    return c[0] if c else fips_list[0]

EXTRA = [('phone','best_contact_phone'),('email','best_contact_email'),('name','best_contact_name'),('title','best_contact_title'),
         ('site','official_site'),('hrUrl','best_hr_page_url'),('backupName','backup_contact_name'),('backupTitle','backup_contact_title'),
         ('backupEmail','backup_contact_email'),('hrEmail','general_hr_email'),('procEmail','procurement_email'),
         ('sourceUrl','source_url'),('notes','notes'),('checked','last_checked')]

J = []          # jurisdictions
by_key = {}     # (abbr, norm, cityType) -> jurisdiction
used_fips = set()
for r in xrows:
    ab = r['state_id']; full = r['county_full'] or r['county']
    cand = atl.get(STATE_FIPS[ab], {}).get(norm(r['county']))
    fips = pick(cand, full) if cand else None
    if fips in used_fips:       # never attach the same boundary to two roster rows
        fips = None
    if fips: used_fips.add(fips)
    j = {'id': 'r' + str(r['record_id']), 'abbr': ab, 'county': r['county'], 'full': full, 'fips': fips, 'status': r['search_status'] or 'Not Started'}
    for k, col in EXTRA:
        v = r.get(col)
        if v not in (None, ''): j[k] = str(v)
    J.append(j)
    by_key[(ab, norm(r['county']), is_city_type(full))] = j

unmatched = []
for rec in records['records']:
    ab = rec['abbr']; nm = norm(rec['county'])
    j = by_key.get((ab, nm, False)) or by_key.get((ab, nm, True))
    if j and 'contacts' not in j:
        j['contacts'] = rec['contacts']; j['recCounty'] = rec['county']; j['stateName'] = rec['state']
    else:
        fips = CT_CITY_TO_COUNTY_FIPS.get(rec['county']) if ab == 'CT' else (DC_FIPS if ab == 'DC' else None)
        unmatched.append(rec['county'])
        J.append({'id': 'x-%s-%s' % (ab.lower(), re.sub(r'[^a-z0-9]+', '-', rec['county'].lower())), 'abbr': ab,
                  'county': rec['county'], 'full': rec['county'], 'fips': fips, 'status': 'Imported',
                  'contacts': rec['contacts'], 'recCounty': rec['county'], 'stateName': rec['state'], 'extra': 1})

for j in J:
    if j.get('contacts'): j['src'] = 'p1'
p1 = sum(1 for j in J if j.get('contacts'))
assert p1 == len(records['records']), (p1, len(records['records']))

# ---- Part 2 extract: only fills counties that have no Part 1 record (Part 1 is never overwritten) ----
def parse_part2():
    blocks, cur = [], None
    for ln in open(os.path.join(SRC, 'extracted_county_leadership_names_and_notes.txt'), encoding='utf-8').read().split('\n')[2:]:
        m = re.match(r'^(.+?) \(([A-Z]{2})\)\s*$', ln)
        if m and not ln.startswith(' '):
            cur = {'name': m.group(1), 'abbr': m.group(2), 'f': {}}; blocks.append(cur); continue
        if cur and ln.startswith(' ') and ':' in ln:
            k, v = ln.strip().split(':', 1); cur['f'][k.strip()] = v.strip()
    return blocks
LABELS = [('HR Director', 'HR / Personnel'), ('Risk Manager', 'Risk / Benefits / Safety'), ('Procurement/Purchasing', 'Procurement / Purchasing'),
          ('Name', 'Primary Contact'), ('Title/Notes', 'Title / Role')]
p2_added, p2_supplement, p2_unmatched = 0, 0, []
p2_by_county = {}
for b in parse_part2():          # a county can appear in several sections of the extract -> merge, de-duplicated
    nm = norm(b['name']); j = by_key.get((b['abbr'], nm, False)) or by_key.get((b['abbr'], nm, True))
    if not j: p2_unmatched.append((b['abbr'], b['name'])); continue
    lst = p2_by_county.setdefault(j['id'], (j, []))[1]
    for k, lab in LABELS:
        if b['f'].get(k) and {'label': lab, 'value': b['f'][k]} not in lst: lst.append({'label': lab, 'value': b['f'][k]})
    if b['f'].get('Source section'):
        note = {'label': 'Notes', 'value': 'Part 2 extract · ' + b['f']['Source section']}
        if note not in lst: lst.append(note)
for j, cs in p2_by_county.values():
    if j.get('contacts'):        # Part 1 record exists: keep it untouched, carry Part 2 alongside it
        j['p2'] = cs; p2_supplement += 1
    else:
        j['contacts'] = cs; j['recCounty'] = j['county']; j['stateName'] = STATE_NAME[j['abbr']]; j['src'] = 'p2'; p2_added += 1

# ---- seed contacts (CSV) ----
seeds = 0
for row in csv.DictReader(open(os.path.join(SRC, 'County_Workforce_Atlas_Seed_Contacts.csv'), encoding='utf-8-sig')):
    for c in re.split(r'\s*[;,]\s*', row['counties']):
        j = by_key.get((row['state'], norm(c), False)) or by_key.get((row['state'], norm(c), True))
        if not j: print('seed county not found', row['state'], c); continue
        j.setdefault('seeds', []).append({k: row[k] for k in ('name', 'title', 'agency', 'focus', 'email', 'emailType', 'phone', 'sourceUrl', 'sourceName', 'sourceChecked', 'sourceStatus') if row.get(k)}); seeds += 1
        if not j.get('contacts'):
            j['contacts'] = [{'label': 'Primary Contact', 'value': row['name']}, {'label': 'Title / Role', 'value': row['title']}]
            j['recCounty'] = j['county']; j['stateName'] = STATE_NAME[row['state']]; j['src'] = 'seed'

placed = sum(1 for j in J if j.get('contacts'))
print('part1', p1, '| part2 added', p2_added, '| part2 supplements to Part 1 counties', p2_supplement, '| part2 unmatched', p2_unmatched, '| seeds', seeds)

counts = {}; roster_counts = {}
for j in J:
    roster_counts[j['abbr']] = roster_counts.get(j['abbr'], 0) + 1
states = []
def s_orig_count(ab): return next(x['count'] for x in records['states'] if x['abbr'] == ab)
for s in records['states']:
    s = dict(s); s['fips'] = STATE_FIPS[s['abbr']]; s['rosterCount'] = roster_counts.get(s['abbr'], 0)
    s['p1'] = sum(1 for j in J if j['abbr'] == s['abbr'] and j.get('src') == 'p1'); s['count'] = sum(1 for j in J if j['abbr'] == s['abbr'] and j.get('contacts'))
    assert s['p1'] == s_orig_count(s['abbr']), s
    states.append(s)

out = {'states': states, 'jurisdictions': J, 'built': '2026-10-13'}
js = '/* Generated by scripts/build_data.py - do not edit by hand. */\nwindow.ATLAS_DATA=' + json.dumps(out, separators=(',', ':'), ensure_ascii=False) + ';\n'
open(os.path.join(ROOT, 'assets/js/atlas-data.js'), 'w').write(js)
print('jurisdictions', len(J), '| with contacts', placed, '| record-only extras', unmatched)
print('with map fips', sum(1 for j in J if j['fips']), '| roster rows without boundary', [(j['abbr'], j['county']) for j in J if not j['fips']][:30])
