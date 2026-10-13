#!/usr/bin/env python3
"""Refresh official county staff registries, retaining last-good snapshots on failures."""
from __future__ import annotations
import argparse
import datetime as dt
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "registries"
SNAPSHOT = DATA / "current.json"
JS = ROOT / "assets" / "js" / "registry-data.js"
EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE = re.compile(r"(?<!\d)(?:\+1[. -]?)?\(?\d{3}\)?[. -]\d{3}[. -]\d{4}(?:\s*(?:ext\.?|x)\s*\d+)?", re.I)
ROLE = re.compile(r"\b(human resources|hr|personnel|benefit|wellness|occupational|employee services|employee relations|employee health|employment|hiring|onboarding|recruit|talent|purchas|procure|contract|vendor|risk|safety|workforce|county administrator|county manager|finance)\b", re.I)
EXCLUDE = re.compile(r"workers.?comp(?:ensation)?|claims specialist|claims adjust", re.I)
PERSONAL = re.compile(r"@(gmail|yahoo|hotmail|aol|outlook|icloud|protonmail|live)\.", re.I)
def clean(t): return " ".join(str(t or "").replace("\xa0", " ").split()).strip(" :|•")
def official_url(source):
    p = urllib.parse.urlsplit(source.get("url", ""))
    host = (p.hostname or "").lower()
    return p.scheme == "https" and bool(re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", host)) and not (
        host.endswith((".local", ".localhost", ".internal", ".test")) or re.match(r"^\d", host)
    ) and not p.username and not p.password and source.get("state") and source.get("county")
def visible_email(el):
    candidates = []
    for anchor in el.select('a[href^="mailto:"]'):
        candidates += EMAIL.findall(urllib.parse.unquote(anchor.get("href", "")))
    candidates += EMAIL.findall(el.get_text(" ", strip=True))
    return next((s for s in candidates if not PERSONAL.search(s)), "")
def name_ok(name):
    words = name.split()
    return 2 <= len(words) <= 6 and len(name) <= 85 and all(
        w.casefold() not in {"department","directory","staff","contacts","email","physical","address","office"} for w in words
    )
def extract_contacts(html, source):
    """Only collect emails explicitly present in an individual staff row/card."""
    soup = BeautifulSoup(html, "html.parser")
    for n in soup.select("script,style,nav,footer,header,form"): n.decompose()
    root = soup.select_one("main") or soup.select_one("#content") or soup.body or soup
    contacts = []
    dept = clean(source.get("department", "County staff"))
    def add(name, title, el, phone="", profile=""):
        name, title = clean(name), clean(title)
        if not name_ok(name) or not title or EXCLUDE.search(title): return
        if not ROLE.search(title + " " + dept): return
        email = visible_email(el)
        contacts.append({
            "name": name, "title": title, "department": dept, "email": email,
            "phone": phone, "profileUrl": profile, "sourceUrl": source["url"],
            "verificationStatus": "observed-on-official-directory"
        })
    for table in root.select("table"):
        headers = [clean(x.get_text(" ", strip=True)).lower() for x in table.select("tr:first-child th")]
        if not any("name" in h for h in headers) or not any("title" in h or "position" in h for h in headers): continue
        ni = next(i for i,h in enumerate(headers) if "name" in h)
        ti = next(i for i,h in enumerate(headers) if "title" in h or "position" in h)
        for tr in table.select("tr"):
            cells = tr.find_all("td", recursive=False)
            if len(cells) <= max(ni, ti): continue
            txt = clean(tr.get_text(" ", strip=True))
            pm = PHONE.search(txt)
            a = cells[ni].find("a", href=True)
            url = urllib.parse.urljoin(source["url"], a["href"]) if a and not a["href"].startswith("javascript:") else ""
            add(cells[ni].get_text(" ",strip=True), cells[ti].get_text(" ",strip=True), tr, pm.group() if pm else "", url)
    for li in root.find_all("li"):
        if len(li.find_all("li")) > 2: continue
        ps = [clean(p.get_text(" ", strip=True)) for p in li.find_all("p", recursive=False)]
        title = next((p for p in ps if 3 < len(p) < 130 and ROLE.search(p)), "")
        if not title: continue
        name = ""; profile = ""
        for a in li.find_all("a",href=True):
            cand = clean(a.get_text(" ",strip=True))
            if name_ok(cand) and not ROLE.search(cand):
                name = cand
                if a["href"].startswith(("/", "http")): profile = urllib.parse.urljoin(source["url"], a["href"])
                break
        if not name:
            for txt in li.find_all(string=True, recursive=False):
                cand = clean(txt)
                if name_ok(cand) and not ROLE.search(cand):
                    name = cand; break
        if not name: continue
        pm = PHONE.search(clean(li.get_text(" ",strip=True)))
        add(name, title, li, pm.group() if pm else "", profile)
    for el in root.select(".staff-card,.staff-member,.employee-card,.contact-card,article.person"):
        n, t = el.select_one("h3,h4,.name,.staff-name"), el.select_one(".title,.position,.job-title")
        if n and t:
            pm = PHONE.search(clean(el.get_text(" ", strip=True)))
            add(n.get_text(" ",strip=True), t.get_text(" ",strip=True), el, pm.group() if pm else "")
    out, seen = [], set()
    for c in contacts:
        key = (c["name"].casefold(), c["title"].casefold())
        if key not in seen: out.append(c); seen.add(key)
    return out
def fetch(source, timeout=25):
    if not official_url(source): raise ValueError("Unapproved county directory URL")
    request = urllib.request.Request(source["url"], headers={"User-Agent": "CountyDirectorySync/1.0 (public staff directory freshness)", "Accept": "text/html"})
    with urllib.request.urlopen(request, timeout=timeout) as r:
        orig, dest = urllib.parse.urlsplit(source["url"]), urllib.parse.urlsplit(r.geturl())
        if dest.scheme != "https" or dest.hostname != orig.hostname: raise ValueError("Unsafe cross-host redirect")
        data = r.read(2_000_001)
        if len(data)>2_000_000: raise ValueError("Directory page exceeds 2 MB")
        return data.decode(r.headers.get_content_charset() or "utf-8", "replace")
def reconcile(previous, source, current, error, now):
    prior = previous.get(source["id"], {})
    item = dict(prior)
    item.update({k: source[k] for k in ("id","state","county","department","url")})
    item["lastAttemptAt"] = now
    if error or not current:
        item["lastError"] = str(error or "No contacts extracted; previous data preserved")
        item.setdefault("contacts", [])
        return item
    old = item.get("contacts", [])
    if len(old)>=4 and len(current)<len(old)*.65:
        item["lastError"] = f"Suspicious partial result ({len(current)}/{len(old)}); previous data preserved"
        return item
    item.update({"contacts":current,"checkedAt":now,"lastError":None})
    return item
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--state",default="")
    p.add_argument("--limit",type=int,default=0)
    args=p.parse_args()
    sources=json.loads((DATA/"sources.json").read_text(encoding="utf-8"))
    selected=[x for x in sources if not args.state or x["state"]==args.state.upper()]
    if args.limit: selected=selected[:args.limit]
    snapshot=json.loads(SNAPSHOT.read_text(encoding="utf-8")) if SNAPSHOT.exists() else {"sources":{}}
    entries=snapshot.setdefault("sources",{})
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    counts={"checked":0,"updated":0,"errors":0}
    for source in selected:
        try:
            contacts=extract_contacts(fetch(source),source)
            error=None if contacts else "No eligible employee rows found"
        except Exception as exc:
            contacts=None; error=f"{type(exc).__name__}: {exc}"
        before=entries.get(source["id"],{}).get("contacts",[])
        entries[source["id"]]=reconcile(entries,source,contacts,error,now)
        counts["checked"]+=1
        if entries[source["id"]].get("lastError"): counts["errors"]+=1
        elif before!=entries[source["id"]].get("contacts",[]): counts["updated"]+=1
        print(source["state"],source["county"],len(entries[source["id"]].get("contacts",[])),entries[source["id"]].get("lastError") or "ok",flush=True)
        time.sleep(.8)
    snapshot["lastAttemptAt"]=now
    if counts["updated"]:snapshot["lastSuccessfulRefreshAt"]=now
    DATA.mkdir(parents=True,exist_ok=True)
    SNAPSHOT.write_text(json.dumps(snapshot,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    JS.parent.mkdir(parents=True,exist_ok=True)
    JS.write_text("window.COUNTY_REGISTRY_SNAPSHOT="+json.dumps(snapshot,separators=(",",":"),ensure_ascii=False)+";\n",encoding="utf-8")
    print(json.dumps(counts))
if __name__=="__main__":main()
