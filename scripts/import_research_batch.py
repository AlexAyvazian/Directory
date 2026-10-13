#!/usr/bin/env python3
"""Import Claude's county_contacts/registry_sources/coverage/changes CSV or JSON batch.

Usage:
    python scripts/import_research_batch.py /path/to/export-folder

Source-linked professional county contacts are appended without overwriting prior
records. A record without a source URL can be retained as a research lead, but
its email is excluded from the public atlas until an official source is attached.
"""
import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "data/registries/research-batch.json"
OUTPUT = ROOT / "assets/js/registry-research.js"
FILES = {
    "contacts": "county_contacts",
    "sources": "county_registry_sources",
    "coverage": "county_research_coverage",
    "changes": "county_changes",
}
EMAIL = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.I)
STATES = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split())

def val(row, *aliases):
    lowered = {str(k).strip().lower():v for k,v in row.items()}
    for k in aliases:
        v = lowered.get(k.lower())
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""

def url_ok(url):
    if not url: return False
    p = urlparse(url)
    h = (p.hostname or "").lower()
    if p.scheme != "https" or not h or "." not in h or p.username or p.password: return False
    if h.endswith((".test", ".local", ".internal")): return False
    if any(h == x or h.endswith("."+x) for x in ("google.com","bing.com","linkedin.com","facebook.com","yahoo.com","duckduckgo.com")): return False
    return True

def norm(text):
    return re.sub(r"[^a-z0-9]", "", str(text or "").lower().replace(" county","").replace(" parish",""))

def read_rows(directory, base):
    path = next((directory / (base + ext) for ext in (".csv",".json") if (directory / (base + ext)).exists()), None)
    if not path: return None
    if path.suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as fh:
            return list(csv.DictReader(fh))
    data=json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data,dict):
        data=next((data[k] for k in ("contacts","sources","coverage","changes","records","data") if isinstance(data.get(k),list)),[])
    if not isinstance(data,list): raise ValueError(f"{path}: expected rows array")
    return data

def general(row):
    state=val(row,"state_abbr","state_id","state").upper()
    county=val(row,"county_name","county","county_full")
    if state not in STATES or not county: return None
    fips=val(row,"county_fips","fips","county_geoid","geoid")
    if fips and fips.isdigit(): fips=fips.zfill(5)
    else: fips=""
    return {"state":state,"county":county,"fips":fips}

def contact(row):
    g=general(row)
    if not g: return None
    name=val(row,"contact_name","name","full_name")
    title=val(row,"job_title","title","position")
    dept=val(row,"department","agency")
    # Group/department mailboxes must not masquerade as individual employees.
    mailtype=val(row,"contact_type","email_type","record_type").lower()
    mailbox=mailtype in ("general","department","department mailbox","shared","general inbox","inbox") or not name
    source=val(row,"source_url","directory_url","official_directory_url","profile_url")
    profile=val(row,"profile_url","staff_url")
    email=val(row,"email","work_email","official_email").strip()
    safe_source=source if url_ok(source) else ""
    if email and (not EMAIL.fullmatch(email) or not safe_source): email=""
    if not (name or email) or not (title or dept): return None
    status=val(row,"verification_status","status") or "research-source-linked"
    return {**g,"name":name if not mailbox else "", "title":title,
            "department":dept,"email":email,"phone":val(row,"phone","telephone","work_phone"),
            "profileUrl":profile if url_ok(profile) else "",
            "sourceUrl":safe_source, "verificationStatus":status,
            "contactType":"department" if mailbox else "person",
            "lastVerified":val(row,"last_verified","date_checked","checked_at"),
            "notes":val(row,"notes")}

def source(row):
    g=general(row)
    if not g: return None
    url=val(row,"directory_url","official_directory_url","url","source_url")
    if not url_ok(url): return None
    return {**g,"url":url,"department":val(row,"department") or "County government",
            "directoryType":val(row,"directory_type"),"platform":val(row,"platform"),
            "status":val(row,"access_status","research_status"),
            "lastChecked":val(row,"last_checked","date_checked")}

def passthrough(row):
    g=general(row)
    return {**g, **{k:str(v or "") for k,v in row.items() if k not in ("state","state_abbr","state_id","county","county_name","county_full","fips","county_fips")}} if g else None

def record_key(kind,row):
    geo=(row["state"],norm(row["county"]))
    if kind=="contacts":
        return (*geo, row["contactType"],norm(row["name"]),norm(row["title"]),norm(row["department"]))
    if kind=="sources": return (*geo,row["url"])
    if kind=="coverage": return geo
    return (*geo, norm(row.get("contact_name")), row.get("change_type"), row.get("previous_value"),row.get("current_value"))

def merge_batch(store, incoming):
    updated={k:list(store.get(k,[])) for k in FILES}
    stats={}
    for kind,rows in incoming.items():
        if rows is None: continue
        convert={"contacts":contact,"sources":source,"coverage":passthrough,"changes":passthrough}[kind]
        lookup={record_key(kind,r):i for i,r in enumerate(updated[kind])}
        added=refreshed=rejected=0
        for raw in rows:
            if not isinstance(raw,dict): rejected+=1; continue
            row=convert(raw)
            if row is None: rejected+=1; continue
            key=record_key(kind,row)
            if key in lookup:
                previous=updated[kind][lookup[key]]
                # Prioritize richer, recent source info; do not delete existing fields on blank input.
                update={k:v for k,v in row.items() if v not in ("",None)}
                if kind=="contacts" and previous.get("email") and not row.get("email"):
                    update.pop("email",None)
                new={**previous,**update}
                if new!=previous: updated[kind][lookup[key]]=new;refreshed+=1
            else:
                lookup[key]=len(updated[kind]);updated[kind].append(row);added+=1
        stats[kind]={"added":added,"updated":refreshed,"rejected":rejected}
    updated["importedAt"]=dt.datetime.now(dt.timezone.utc).isoformat()
    return updated,stats

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("folder",type=Path,help="Folder containing county_contacts.csv etc")
    args=cli.parse_args()
    previous=json.loads(STORE.read_text(encoding="utf-8")) if STORE.exists() else {}
    incoming={k:read_rows(args.folder,base) for k,base in FILES.items()}
    if not any(x is not None for x in incoming.values()):
        raise SystemExit("No expected county_contacts / county_registry_sources / county_research_coverage / county_changes files found")
    merged,stats=merge_batch(previous,incoming)
    STORE.parent.mkdir(parents=True,exist_ok=True)
    STORE.write_text(json.dumps(merged,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text("window.COUNTY_REGISTRY_RESEARCH="+json.dumps(merged,ensure_ascii=False,separators=(",",":"))+";\n",encoding="utf-8")
    print(json.dumps(stats,indent=2))
    print("Total:",json.dumps({k:len(merged[k]) for k in FILES}))
if __name__=="__main__":main()
