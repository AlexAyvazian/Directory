#!/usr/bin/env python3
"""Bulk match official county government domains to MY 25 Atlas states.

Never treats .gov domain security contacts as county employee contacts.
Never writes into existing contact datasets. Registrations != working websites.

Examples:
  python scripts/discover_my_half.py
  python scripts/discover_my_half.py --cisa sample.csv --gsa sample.csv
"""
from __future__ import annotations
import argparse
import csv
import io
import json
import re
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "discovery"
ATLAS = ROOT / "assets" / "js" / "atlas-data.js"
CISA_URL = "https://raw.githubusercontent.com/cisagov/dotgov-data/main/current-full.csv"
GSA_URL = "https://raw.githubusercontent.com/GSA/govt-urls/main/5_govt_urls_county_only.csv"
OWNER = frozenset("AL AR AZ CA CT DE IA KY LA MN MO MT NC ND NV OH OK OR PA RI TX UT VT WA WY".split())
STOP = re.compile(r"\b(sheriff|police|court|judicial|assessor|tax|school|library|health department|health district|fire|hospital|coroner|election|recorder|registrar|constable|jail|district attorney|probate|911|emergency|water authority|public utilities|clerk of court|appraiser|treasurer)\b", re.I)
STATE_NAMES = {}
def norm(n):
    n = str(n or "").lower().replace("saint ","st ").replace("st. ","st ")
    n = re.sub(r"\b(county|parish|borough|city|and|of|municipality|government)\b", " ", n)
    return re.sub(r"[^a-z0-9]", "", n)
def display_key(n):
    return re.sub(r"[^a-z0-9]", "", str(n or "").lower())
def parse_csv(body):
    return list(csv.DictReader(io.StringIO(body.lstrip("\ufeff"))))
def fetch(url):
    request=urllib.request.Request(url,headers={"User-Agent":"OccuMedCountyDomainResearch/1.0","Accept":"text/csv"})
    with urllib.request.urlopen(request,timeout=65) as res:
        buf=res.read(5_000_001)
        if len(buf)>5_000_000:raise ValueError("CSV exceeds 5MB limit")
        return buf.decode("utf-8-sig")
def load_atlas(path=ATLAS):
    t=path.read_text(encoding="utf-8")
    start=t.index("window.ATLAS_DATA=")+len("window.ATLAS_DATA=")
    d=json.loads(t[start:t.rfind(";")])
    global STATE_NAMES
    STATE_NAMES={s["name"].lower():s["abbr"] for s in d["states"]}
    return [j for j in d["jurisdictions"] if j["abbr"] in OWNER]
def is_relevant_county_site(org,domain,county):
    name=norm(county)
    org_clean=norm(org)
    host=display_key(domain.split(".")[0])
    if not name: return False
    # Require exact county identifier in the organisation or domain; avoid similar city names.
    name_in_org=name in org_clean and (
        re.search(r"\b(county|parish|borough|municipality)\b",org,re.I)
        or display_key(org).startswith("countyof")
    )
    name_in_host=(host in {name,name+"county",name+"parish",name+"co"} or
                  host.startswith(name+"county") or host.startswith(name+"parish"))
    return bool(name_in_org or name_in_host)
def match_cisa(rows, jurisdictions):
    matched=defaultdict(list)
    bystate=defaultdict(list)
    for j in jurisdictions:bystate[j["abbr"]].append(j)
    for row in rows:
        if row.get("Domain type","").strip().lower()!="county":continue
        state=row.get("State","").strip().upper()
        if state not in OWNER:continue
        org=row.get("Organization name","").strip()
        sub=row.get("Suborganization name","").strip()
        domain=row.get("Domain name","").strip().lower()
        if not domain.endswith(".gov") or STOP.search(org+" "+sub):continue
        candidates=[j for j in bystate[state] if is_relevant_county_site(org,domain,j["county"])]
        if len(candidates)!=1:continue
        j=candidates[0]
        matched[j["id"]].append({
            "domain":domain,"url":"https://"+domain,
            "registry":"CISA .gov domain registration",
            "registrySource":CISA_URL,
            "status":"registered-domain-not-confirmed-as-live-staff-site",
            "organization":org,"state":state,"county":j["county"],"fips":j.get("fips") or ""
        })
    return matched
def match_gsa(rows,jurisdictions):
    matched=defaultdict(list)
    bystate=defaultdict(list)
    for j in jurisdictions:bystate[j["abbr"]].append(j)
    for row in rows:
        st=STATE_NAMES.get(row.get("Location","").strip().lower())
        if st not in OWNER:continue
        if "county" not in row.get("Level of Government","").lower():continue
        domain=row.get("Domain","").lower().strip()
        if not domain or domain.endswith(".gov") or not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}",domain):continue
        comment=row.get("Note","").split("--")[0].strip()
        if STOP.search(comment):continue
        candidates=[j for j in bystate[st] if
            is_relevant_county_site(comment,domain,j["county"])]
        if len(candidates)!=1:continue
        j=candidates[0]
        matched[j["id"]].append({
            "domain":domain,"url":"https://"+domain,
            "registry":"GSA non-.gov county domain directory",
            "registrySource":GSA_URL,
            "status":"historical-domain-listing-not-confirmed-as-live-staff-site",
            "organization":comment,"state":st,"county":j["county"],
            "fips":j.get("fips") or "","gsaStatus":row.get("Status","")
        })
    return matched
def merge(cisa,gsa,jurisdictions):
    output=[]; used=set()
    for j in jurisdictions:
        candidates=[]
        for row in (cisa.get(j["id"],[])+gsa.get(j["id"],[])):
            if row["domain"] in {x["domain"] for x in candidates}:continue
            candidates.append(row)
        if candidates:
            output.append({"state":j["abbr"],"county":j["county"],"full":j.get("full",""),
                           "fips":j.get("fips") or "","jurisdictionId":j["id"],
                           "domains":candidates})
        used.add(j["id"])
    return output
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--cisa",type=Path)
    ap.add_argument("--gsa",type=Path)
    ap.add_argument("--out",type=Path,default=DATA/"my_half_domain_candidates.json")
    args=ap.parse_args()
    counties=load_atlas()
    cisa=parse_csv(args.cisa.read_text(encoding="utf-8-sig") if args.cisa else fetch(CISA_URL))
    gsa=parse_csv(args.gsa.read_text(encoding="utf-8-sig") if args.gsa else fetch(GSA_URL))
    matched=merge(match_cisa(cisa,counties),match_gsa(gsa,counties),counties)
    payload={"assignedStates":sorted(OWNER),"jurisdictionsInAtlas":len(counties),
             "matchedJurisdictions":len(matched),"domainCount":sum(len(x["domains"]) for x in matched),
             "unmatchedJurisdictions":len(counties)-len(matched),
             "governmentDomainNotStaffVerified":True,
             "sources":[CISA_URL,GSA_URL],"results":matched}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in payload.items() if k not in ("sources","results")},indent=2))
if __name__=="__main__":main()
