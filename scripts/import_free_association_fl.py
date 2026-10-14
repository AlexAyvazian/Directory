#!/usr/bin/env python3
"""Free public Florida county association directory importer.

Uses only publicly visible directory pages and their published work contacts.
Never guesses emails or equates a trade-association listing to confirmation
from an individual county's official website. Existing Atlas records stay intact.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import re
import time
import urllib.parse
import urllib.request
import urllib.robotparser
from pathlib import Path
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/"data/discovery/fl_association_staff.json"
BROWSER_JS=ROOT/"assets/js/fl-association-contacts.js"
BASE="https://www.fl-counties.com"
GROUPS={
    "Human Resources/Personnel":"157253",
    "Purchasing & Acquisition":"157259",
    "Risk Management":"157260",
}
AGENT="OccuMedPublicCountyDirectoryResearch/1.0"
PERSON=re.compile(r"^[A-Z][A-Za-zÀ-ÿ'’.\- ]+,\s*[A-Z][A-Za-zÀ-ÿ'’.\- ]+(?:,\s*(?:Jr\.?|Sr\.?|III|II))?$")
COUNTY=re.compile(r"^([A-Za-z][A-Za-z .'\-]+)\s+County$",re.I)
PHONE=re.compile(r"(?<!\d)(?:\+1[-. ]?)?\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}(?:\s*(?:x|ext\.?)\s*\d+)?",re.I)
EMAIL=re.compile(r"(?<![\w.])([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})(?![\w.])")
ROLE=re.compile(r"human resources|\bHR\b|personnel|staffing|employee benefits|risk|safety|purchas|procure|contract|vendor|occupational|wellness|county administrator|county manager",re.I)
EXCLUDE=re.compile(r"workers.?comp(?:ensation)?|claims adjuster|claim specialist",re.I)
PERSONAL=re.compile(r"@(gmail|yahoo|hotmail|aol|outlook|icloud|protonmail|live)\.",re.I)

def web_page(group,page):
    params={"group":GROUPS[group]}
    if page>1:params["cpage"]=str(page)
    return BASE+"/directory-results/?"+urllib.parse.urlencode(params)

def robot_policy():
    robots=BASE+"/robots.txt"
    req=urllib.request.Request(robots,headers={"User-Agent":AGENT})
    with urllib.request.urlopen(req,timeout=18) as r:
        if urllib.parse.urlsplit(r.url).hostname not in {"fl-counties.com","www.fl-counties.com"}:
            raise PermissionError("Robots URL redirected to a different host")
        body=r.read(100_001)
        if len(body)>100_000:raise PermissionError("Robots policy unexpectedly large")
    p=urllib.robotparser.RobotFileParser()
    p.parse(body.decode("utf-8",errors="replace").splitlines())
    return p

def download(url,robots):
    if not robots.can_fetch(AGENT,url):raise PermissionError("Site robots.txt disallows "+url)
    req=urllib.request.Request(url,headers={"User-Agent":AGENT,"Accept":"text/html"})
    with urllib.request.urlopen(req,timeout=22) as r:
        dest=urllib.parse.urlsplit(r.url)
        if dest.scheme!="https" or dest.hostname not in {"fl-counties.com","www.fl-counties.com"}:
            raise PermissionError("Unexpected cross-domain redirect")
        html=r.read(1_500_001)
        if len(html)>1_500_000:raise ValueError("Directory page unexpectedly large")
    return html.decode("utf-8",errors="replace")

def parse_directory_page(html,source_url,group):
    soup=BeautifulSoup(html,"html.parser")
    for bad in soup.select("script,style,nav,footer,header"):
        bad.decompose()
    # Parse only the public search results, not association officers or navigation.
    lines=[re.sub(r"\s+"," ",s).strip() for s in soup.get_text("\n").splitlines()]
    lines=[s for s in lines if s]
    pos=next((i for i,s in enumerate(lines) if s.startswith("Search Results for")),None)
    if pos is None:return []
    lines=lines[pos+1:]
    spans=[i for i,s in enumerate(lines) if PERSON.fullmatch(s) and len(s)<85]
    results=[]
    for z,i in enumerate(spans):
        end=spans[z+1] if z+1<len(spans) else min(len(lines),i+35)
        part=lines[i:end][:35]
        if len(part)<3:continue
        # Association directory pages format an employee as Surname, Given / Role / County.
        county_ix=next((k for k,line in enumerate(part[1:15],1) if COUNTY.fullmatch(line)),None)
        if county_ix is None:continue
        title=" ".join(part[1:county_ix]).strip()
        if not title or len(title)>150 or not ROLE.search(title) or EXCLUDE.search(title):continue
        county=COUNTY.fullmatch(part[county_ix]).group(1).strip()
        last,first=part[0].split(",",1)
        name=(first.strip()+" "+last.strip()).strip()
        remainder=" ".join(part[county_ix+1:])
        phones=PHONE.findall(remainder)
        emails=[x for x in EMAIL.findall(remainder) if not PERSONAL.search(x)]
        results.append({
            "state":"FL","county":county,"name":name,"title":title,
            "department":group,
            "email":emails[0] if emails else "","phone":phones[0] if phones else "",
            "sourceUrl":source_url,
            "verificationStatus":"public-state-association-directory-needs-county-confirmation",
            "contactType":"person",
            "observedAt":dt.datetime.now(dt.timezone.utc).date().isoformat()
        })
    # Remove accidental duplicates from overlapping page HTML.
    dedup={}
    for x in results:
        key=(x["county"].lower(),x["name"].lower(),x["title"].lower(),x["sourceUrl"])
        dedup[key]=x
    return list(dedup.values())

def collect(fetch,groups=GROUPS,limit=12,delay=2):
    total=[]
    for group in groups:
        seen_pages=set()
        for page in range(1,limit+1):
            url=web_page(group,page)
            html=fetch(url)
            entries=parse_directory_page(html,url,group)
            if not entries:break
            key=tuple(sorted((x["county"],x["name"],x["title"]) for x in entries))
            if key in seen_pages:break
            seen_pages.add(key)
            total.extend(entries)
            print(f"{group} page={page}: {len(entries)} staff",flush=True)
            if delay:time.sleep(delay)
    unique={}
    for x in total:
        key=(x["state"],x["county"].lower(),x["name"].lower(),x["title"].lower())
        if key not in unique or (x["email"] and not unique[key]["email"]):
            unique[key]=x
    return sorted(unique.values(),key=lambda x:(x["county"],x["department"],x["name"]))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--max-pages",type=int,default=12)
    ap.add_argument("--delay",type=float,default=2.0)
    args=ap.parse_args()
    # Preserve last-known-good output if scraping is prohibited or fails.
    robots=robot_policy()
    contacts=collect(lambda url:download(url,robots),limit=min(args.max_pages,25),delay=max(args.delay,1))
    if not contacts:
        raise RuntimeError("No Florida association directory contacts parsed: old files retained")
    previous={}
    if OUTPUT.exists():
        try:previous=json.loads(OUTPUT.read_text(encoding="utf-8"))
        except (ValueError,OSError):pass
    all_rows={(x["county"].lower(),x["name"].lower(),x["title"].lower()):x
              for x in previous.get("contacts",[])}
    for x in contacts:
        key=(x["county"].lower(),x["name"].lower(),x["title"].lower())
        old=all_rows.get(key)
        if old and old.get("email") and not x["email"]:
            x["email"]=old["email"]
            x["verificationStatus"]="association-previously-published-email-needs-recheck"
        all_rows[key]=x
    result={"publisher":"Florida Association of Counties","publisherUrl":BASE,
            "sourceType":"public-state-county-association-directory",
            "countyConfirmed":False,"groups":GROUPS,"dateChecked":dt.datetime.now(dt.timezone.utc).isoformat(),
            "contacts":sorted(all_rows.values(),key=lambda x:(x["county"],x["name"],x["title"]))}
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    BROWSER_JS.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    BROWSER_JS.write_text("window.COUNTY_FREE_ASSOCIATION_CONTACTS="+json.dumps(result,ensure_ascii=False,separators=(",",":"))+";\n",encoding="utf-8")
    print(json.dumps({"people":len(result["contacts"]),"withPublishedEmails":sum(bool(x["email"]) for x in result["contacts"]),
                      "counties":len({x["county"] for x in result["contacts"]})},indent=2))

if __name__=="__main__":main()
