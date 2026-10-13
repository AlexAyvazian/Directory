#!/usr/bin/env python3
"""Parallel public website discovery for county government staff/HR directories.

Run AFTER discover_my_half.py. Does not alter contacts automatically: real names,
email addresses, and official source links are surfaced for review/import.
Respects robots.txt, URL scope, and previous known-good snapshots.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import datetime as dt
import html.parser
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from pathlib import Path
from scripts.refresh_registries import extract_contacts

ROOT=Path(__file__).resolve().parents[1]
DISCOVERY=ROOT/"data"/"discovery"
INPUT=DISCOVERY/"my_half_domain_candidates.json"
OUTPUT=DISCOVERY/"my_half_staff_page_leads.json"
HEADERS={"User-Agent":"OccuMedCountyRegistryResearch/1.0 (+public county staff directory audit)","Accept":"text/html,text/plain"}
ROLE=re.compile(r"(staff.?directory|employee.?directory|human.?resources|employee.?services|personnel|employee.?benefits|employee.?health|occupational.?health|employee.?wellness|risk.?management|safety|procurement|purchasing|contracts?|department.?directory)",re.I)
EXCLUDE=re.compile(r"(careers?|job.?opening|vacanc|employment.?application|apply.?now|public.?records|bid.?opening|rss|pdf$|social.?media)",re.I)
SITE_TIMEOUT=9
MAX_BYTES=750_000

def normalize_host(h):
    h=(h or "").lower().removeprefix("www.")
    return h

def safe_same_site(url,base):
    parsed=urllib.parse.urlsplit(url)
    baseparsed=urllib.parse.urlsplit(base)
    return (parsed.scheme=="https" and normalize_host(parsed.hostname)==normalize_host(baseparsed.hostname)
            and not parsed.username and not parsed.password and parsed.port in (None,443)
            and not re.search(r"(?i)\.(zip|tar|gz|exe|dmg|mp4|jpg|jpeg|png|gif|pdf)(?:$|\?)",parsed.path))

class Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links=[]
        self.href=None
        self.label=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a" and self.href is None:
            self.href=dict(attrs).get("href")
            self.label=[]
    def handle_data(self,data):
        if self.href is not None:self.label.append(data)
    def handle_endtag(self,tag):
        if tag=="a" and self.href is not None:
            self.links.append((self.href," ".join(" ".join(self.label).split())))
            self.href=None
            self.label=[]

def find_links(html,base):
    finder=Links()
    finder.feed(html)
    links=[]
    for href,label in finder.links:
        url=urllib.parse.urljoin(base,href or "")
        if not safe_same_site(url,base):continue
        if EXCLUDE.search(url+" "+label):continue
        score=0
        s=(label+" "+url).lower()
        if re.search(r"(staff.?directory|employee.?directory|department.?directory)",s):score=95
        elif re.search(r"(human.?resources|employee.?services|personnel|employee.?health)",s):score=80
        elif re.search(r"(employee.?benefits|occupational.?health|employee.?wellness|risk.?management|procurement|purchasing)",s):score=70
        elif ROLE.search(s):score=50
        if score==0:continue
        if "/directory" in url.lower():score+=10
        if url.rstrip("/") == base.rstrip("/"):continue
        links.append({"url":url,"label":label or urllib.parse.urlsplit(url).path,"score":score})
    best={}
    for x in links:
        url=x["url"].split("#")[0]
        if url not in best or x["score"]>best[url]["score"]:best[url]={**x,"url":url}
    return sorted(best.values(),key=lambda x:-x["score"])

def get(url,base):
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=SITE_TIMEOUT) as r:
        if not safe_same_site(r.geturl(),base):raise PermissionError("Cross-host redirect; review manually")
        contents=r.read(MAX_BYTES+1)
        if len(contents)>MAX_BYTES:raise ValueError("Page exceeds safe size")
        typ=r.headers.get("Content-Type","")
        if "html" not in typ.lower() and "text/" not in typ.lower():raise ValueError("Non-HTML page")
        return contents.decode(r.headers.get_content_charset() or "utf-8",errors="replace")

def check_robots(base):
    url=base.rstrip("/")+"/robots.txt"
    try:
        req=urllib.request.Request(url,headers=HEADERS)
        with urllib.request.urlopen(req,timeout=SITE_TIMEOUT) as r:
            if not safe_same_site(r.geturl(),base):raise PermissionError("robots.txt cross-host redirect")
            data=r.read(200_001)
            if len(data)>200_000:raise PermissionError("robots.txt too large")
            parser=urllib.robotparser.RobotFileParser()
            parser.parse(data.decode("utf-8",errors="replace").splitlines())
            return parser
    except urllib.error.HTTPError as err:
        if err.code in (404,410):
            parser=urllib.robotparser.RobotFileParser()
            parser.parse([])
            return parser
        raise PermissionError("robots.txt inaccessible; skip") from err
    except Exception as e:
        raise PermissionError("robots.txt cannot be checked; skip") from e

def scan_site(item):
    base="https://"+item["domain"]
    result={"state":item["state"],"county":item["county"],"fips":item.get("fips",""),
            "domain":item["domain"],"registry":item["registry"],"checkedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
            "status":"not_checked","pages":[],"contacts":[]}
    try:
        robots=check_robots(base)
        if not robots.can_fetch(HEADERS["User-Agent"].split("/")[0],base+"/"):
            raise PermissionError("robots.txt disallows homepage")
        home=get(base+"/",base)
        choices=find_links(home,base)
        if not choices:
            result["status"]="no_hr_or_directory_links_on_homepage"
            return result
        for link in choices[:3]:
            if not robots.can_fetch(HEADERS["User-Agent"].split("/")[0],link["url"]):
                continue
            try:
                page=get(link["url"],base)
                # Only report pages that actually returned successfully.
                rec={**link,"status":"live-page","contactCount":0}
                if re.search(r"(directory|human resources|personnel|staff|benefits|risk|purchas|procure)",page,re.I):
                    matches=extract_contacts(page,{"url":link["url"],"department":link["label"] or "County government"})
                    rec["contactCount"]=len(matches)
                    for c in matches:
                        c["sourceUrl"]=link["url"]
                        c["verificationStatus"]="extracted-from-live-county-page"
                        result["contacts"].append(c)
                result["pages"].append(rec)
            except (urllib.error.URLError,ValueError,PermissionError,TimeoutError):
                continue
        result["status"]="pages_found" if result["pages"] else "links_found_not_accessible"
    except Exception as e:
        result["status"]="blocked_or_unavailable"
        result["error"]=type(e).__name__+": "+str(e)[:180]
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",type=Path,default=INPUT)
    ap.add_argument("--out",type=Path,default=OUTPUT)
    ap.add_argument("--workers",type=int,default=20)
    ap.add_argument("--max-sites",type=int,default=0)
    args=ap.parse_args()
    if not args.input.exists():
        # First deployment can start from the precomputed GSA leads while CISA refresh runs.
        args.input=DISCOVERY/"gsa_my_half_domain_candidates.json"
    data=json.loads(args.input.read_text(encoding="utf-8"))
    # One site per jurisdiction on first pass. Prefer current CISA .gov registrations.
    items=[]
    if "results" in data:
        for row in data["results"]:
            choices=sorted(row["domains"],key=lambda d:0 if d["registry"].startswith("CISA") else 1)
            if choices:items.append(choices[0])
    else:
        for row in data.get("sites",[]):
            items.append({"state":row["state"],"county":row["county"],"fips":row.get("fips",""),
                          "domain":row["domain"],"registry":"GSA county website listing (historical)"})
    if args.max_sites:items=items[:args.max_sites]
    previous=json.loads(args.out.read_text(encoding="utf-8")) if args.out.exists() else {"sites":[]}
    bykey={(x["state"],x.get("fips") or x["county"]):x for x in previous["sites"]}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,min(32,args.workers))) as pool:
        for result in pool.map(scan_site,items):
            key=(result["state"],result.get("fips") or result["county"])
            old=bykey.get(key)
            if result["status"]=="blocked_or_unavailable" and old and old.get("pages"):
                result["pages"]=old["pages"]
                result["contacts"]=old.get("contacts",[])
                result["previousSuccessfulSnapshotRetained"]=True
            bykey[key]=result
            print(result["state"],result["county"],result["status"],len(result["pages"]),len(result["contacts"]),flush=True)
    results=sorted(bykey.values(),key=lambda x:(x["state"],x["county"]))
    payload={"assignedStateCount":25,"scannedSiteCount":len(items),"retainedSiteCount":len(results),
             "sitesWithLiveDirectoryPages":sum(bool(x.get("pages")) for x in results),
             "linksDiscovered":sum(len(x.get("pages",[])) for x in results),
             "sourceLinkedExtractedContacts":sum(len(x.get("contacts",[])) for x in results),
             "createdAt":dt.datetime.now(dt.timezone.utc).isoformat(),"candidatePagesNotValidatedAsIndividualContacts":True,
             "sites":results}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in payload.items() if k!="sites"},indent=2))
if __name__=="__main__":main()
