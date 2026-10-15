#!/usr/bin/env python3
"""Bounded concurrent, resumable public directory traversal. No database writes.

Only linked directory pages are followed. A drained frontier alone is not proof of
coverage: failed fetches, unparsed profiles, forms, and rendering dependencies keep
the source in review/retry. Raw HTML and its hash accompany every extracted record.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from datetime import datetime, timezone
import email.utils
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import aiohttp
from bs4 import BeautifulSoup

AGENT = 'DirectoryResearch/1.0 (public government staff directory research)'
PATH = re.compile(r'^/(?:directory\.aspx|m/directory(?:/(?:department|employee))?)/?$', re.I)
EMAIL = re.compile(r'^[A-Z0-9.!#$%&\'*+/=?^_`{|}~-]+@[A-Z0-9.-]+\.[A-Z]{2,}$', re.I)
PHONE = re.compile(r'(?:\+1[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?:\s*(?:ext\.?|x)\s*\d+)?', re.I)


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical_url(url):
    p = urlsplit(url)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        raise ValueError('Unsupported directory URL')
    query = [(k.lower(), v) for k, v in parse_qsl(p.query) if k.lower() not in ('utm_source', 'utm_medium', 'utm_campaign')]
    path = p.path.lower().rstrip('/') or '/'
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), path, urlencode(sorted(query)), ''))


def profile_key(url):
    p = urlsplit(url)
    q = dict(parse_qsl(p.query.lower()))
    eid = q.get('eid')
    return f'employee:{eid}' if eid and eid.isdigit() else None


def allowed_url(url, hosts):
    p = urlsplit(url)
    return p.scheme in ('http', 'https') and not p.username and not p.password and p.hostname in hosts and bool(PATH.match(p.path))


def text(el):
    return re.sub(r'\s+', ' ', el.get_text(' ', strip=True)).strip() if el else ''


def published_emails(root):
    values = []
    for a in root.select('a[href^="mailto:"]'):
        value = a['href'][7:].split('?')[0].strip()
        if EMAIL.fullmatch(value):
            values.append(value)
    for el in root.select('[data-cfemail]'):
        try:
            raw = bytes.fromhex(el['data-cfemail'])
            value = ''.join(chr(n ^ raw[0]) for n in raw[1:])
            if EMAIL.fullmatch(value):
                values.append(value)
        except (ValueError, IndexError):
            pass
    return list(dict.fromkeys(values))


def person_name(name):
    name = re.sub(r'\s+', ' ', name).strip()
    return (3 <= len(name) <= 120 and len(name.split()) >= 2
            and bool(re.search(r'[A-Za-z]', name))
            and not re.search(r'\d|@|directory|department|contact us|staff listing|search|vacant|vacancy|unassigned|'
                              r'human resources|public works|employee benefits|risk management|emergency management|'
                              r'phone|email|director|manager|coordinator|supervisor', name, re.I))


def parse_page(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    title = text(soup.title)
    links = []
    for a in soup.select('a[href]'):
        linked = urljoin(url, a['href'])
        if PATH.match(urlsplit(linked).path):
            links.append(linked)
    records, issues = [], []
    # Header-labelled tables avoid assigning a neighboring person's email/phone.
    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        if not rows:
            continue
        headers = [text(c).lower() for c in rows[0].find_all(['th', 'td'], recursive=False)]
        if not any(h in ('name', 'staff', 'employee') for h in headers):
            continue
        for row in rows[1:]:
            cells = row.find_all(['td', 'th'], recursive=False)
            if len(cells) != len(headers):
                continue
            fields = dict(zip(headers, cells))
            ncell = next((fields[h] for h in ('name', 'staff', 'employee') if h in fields), None)
            name = text(ncell)
            if not person_name(name):
                continue
            profile = next((urljoin(url, a['href']) for a in row.select('a[href]') if profile_key(urljoin(url, a['href']))), None)
            mails = published_emails(row)
            phonecell = next((fields[h] for h in fields if 'phone' in h or 'telephone' in h), None)
            phone = PHONE.search(text(phonecell))
            records.append(dict(name=name, title=text(fields.get('title')), department=text(fields.get('department')), department_phone='',
                                email=mails[0] if len(mails) == 1 else '', phone=phone.group() if phone else '',
                                profile_url=profile, page_url=url, extraction='labelled_table'))
    if profile_key(url):
        root = soup.select_one('.staffDetails, .staffDetail, #staffDetails, [data-role="content"], main, #content') or soup.body or soup
        for el in root.select('nav, footer, header, script, style'):
            el.decompose()
        lines = [re.sub(r'\s+', ' ', line).strip() for line in root.get_text('\n', strip=True).splitlines()]
        def label_value(label):
            for i, line in enumerate(lines):
                m = re.match(rf'^(?:{label})\s*:\s*(.*)$', line, re.I)
                if m:
                    return m[1] or (lines[i + 1] if i + 1 < len(lines) else '')
            return ''
        name = label_value('Name')
        if not name:
            name = next((text(h) for h in root.select('h1, h2, h3') if person_name(text(h))), '')
        job = label_value('Title|Job Title|Position')
        department = label_value('Department')
        mails = published_emails(root)
        phone = label_value('Phone|Telephone|Work Phone')
        phone_match = PHONE.search(phone)
        if person_name(name) and (job or department or mails or phone_match):
            records.append(dict(name=name, title=job, department=department, department_phone=label_value('Department Phone'),
                                email=mails[0] if len(mails) == 1 else '', phone=phone_match.group() if phone_match else '',
                                profile_url=url, page_url=url, extraction='employee_profile'))
        else:
            issues.append('employee_profile_not_extracted')
        if len(mails) > 1:
            issues.append('ambiguous_profile_emails')
    # WebForms postbacks and client-side navigation need rendering; never call them exhausted.
    if soup.select('a[href*="__doPostBack"], a[href^="javascript:"]'):
        issues.append('javascript_navigation_requires_review')
    for form in soup.select('form'):
        if form.select('select, input[type="submit"]'):
            issues.append('directory_filter_form_requires_review')
    return dict(title=title, links=sorted(set(links)), records=records, issues=sorted(set(issues)))


class FetchFailure(Exception):
    def __init__(self, reason, status=None):
        super().__init__(reason)
        self.status = status


class Crawler:
    def __init__(self, output, workers=24, per_host=2, delay=.5, timeout=25, attempts=3):
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.workers, self.per_host, self.delay = workers, per_host, delay
        self.timeout, self.attempts = timeout, attempts
        self.host_locks = defaultdict(asyncio.Lock)
        self.host_limits = defaultdict(lambda: asyncio.Semaphore(per_host))
        self.next_fetch = defaultdict(float)
        self.requests = asyncio.Semaphore(workers)
        self.robots = {}
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(trust_env=True, timeout=aiohttp.ClientTimeout(total=self.timeout),
                                            connector=aiohttp.TCPConnector(limit=self.workers, limit_per_host=self.per_host),
                                            headers={'User-Agent': AGENT})
        return self

    async def __aexit__(self, *args):
        await self.session.close()

    async def fetch(self, url, hosts, robots=False):
        """Manual redirects keep requests within the submitted host and its www alias."""
        current = url
        for _ in range(10):
            host = urlsplit(current).hostname
            if host not in hosts:
                raise FetchFailure('redirect_to_unapproved_host')
            if not robots and current != url:
                await self.check_robots(current, hosts)
            for attempt in range(self.attempts):
                try:
                    async with self.requests, self.host_limits[host]:
                        async with self.host_locks[host]:
                            await asyncio.sleep(max(0, self.next_fetch[host] - time.monotonic()))
                            self.next_fetch[host] = time.monotonic() + self.delay
                        async with self.session.get(current, allow_redirects=False) as response:
                            status = response.status
                            if status in (301, 302, 303, 307, 308):
                                current = urljoin(current, response.headers.get('Location', ''))
                                if not robots and not allowed_url(current, hosts):
                                    raise FetchFailure('redirect_outside_directory', status)
                                break
                            if status in (429, 500, 502, 503, 504) and attempt + 1 < self.attempts:
                                retry = response.headers.get('Retry-After', '')
                                try:
                                    pause = max(0, float(retry))
                                except ValueError:
                                    try:
                                        pause = max(0, email.utils.parsedate_to_datetime(retry).timestamp() - time.time())
                                    except (ValueError, TypeError):
                                        pause = 2 ** attempt
                                # Respect long Retry-After by deferring the source rather than blocking all workers.
                                if pause > 60:
                                    raise FetchFailure('rate_limited_retry_later', status)
                                self.next_fetch[host] = max(self.next_fetch[host], time.monotonic() + pause)
                                continue
                            if robots and status == 404:
                                return current, status, '', b''
                            if status != 200:
                                raise FetchFailure(f'http_{status}', status)
                            chunks, size = [], 0
                            async for chunk in response.content.iter_chunked(65536):
                                size += len(chunk)
                                if size > 10 * 1024 * 1024:
                                    raise FetchFailure('response_too_large')
                                chunks.append(chunk)
                            raw = b''.join(chunks)
                            try:
                                body = raw.decode(response.charset or 'utf-8', errors='replace')
                            except LookupError:
                                body = raw.decode('utf-8', errors='replace')
                            return current, status, body, raw
                except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                    if isinstance(exc, aiohttp.ClientHttpProxyError) and exc.status in (401, 403):
                        raise FetchFailure('proxy_access_denied', exc.status) from None
                    if attempt + 1 == self.attempts:
                        # Never log proxy URL credentials or connection strings.
                        raise FetchFailure(type(exc).__name__, getattr(exc, 'status', None)) from None
                    await asyncio.sleep(2 ** attempt)
            else:
                raise FetchFailure('attempts_exhausted')
        raise FetchFailure('redirect_loop')

    async def check_robots(self, url, hosts):
        p = urlsplit(url)
        origin = f'{p.scheme}://{p.netloc}'
        if origin not in self.robots:
            final, status, body, _ = await self.fetch(origin + '/robots.txt', hosts, robots=True)
            parser = RobotFileParser()
            parser.parse(body.splitlines() if status == 200 else [])
            self.robots[origin] = parser
        parser = self.robots[origin]
        if not parser.can_fetch(AGENT, url):
            raise FetchFailure('robots_disallowed')
        interval = parser.crawl_delay(AGENT) or parser.crawl_delay('*')
        if interval:
            self.next_fetch[p.hostname] = max(self.next_fetch[p.hostname], time.monotonic() + interval)

    async def crawl(self, source):
        key = source['source_key']
        host = source['host']
        # www/apex are candidates only. Sources remain distinct until verified redirects.
        hosts = {host, host[4:] if host.startswith('www.') else 'www.' + host}
        directory = self.output / hashlib.sha256(key.encode()).hexdigest()[:20]
        directory.mkdir(exist_ok=True)
        previous_path = directory / 'result.json'
        previous = json.loads(previous_path.read_text()) if previous_path.exists() else {}
        result = dict(source_key=key, host=host, started_at=now(), status='crawling', pages=[], contacts=[],
                      errors=[], issues=[], discovered_profiles=[], fetched_profiles=[], rejected=0)
        # Successful pages are reusable; failed pages are always retried.
        cached = {p['url']: p for p in previous.get('pages', []) if p.get('status') == 200}
        seen, frontier = set(), set(source['entry_urls'])
        profile_records = {}
        while frontier:
            batch = sorted(frontier)
            frontier.clear()
            for offset in range(0, len(batch), self.per_host):
                targets = []
                for url in batch[offset:offset + self.per_host]:
                    canonical = canonical_url(url)
                    if canonical not in seen:
                        targets.append(url)
                        seen.add(canonical)
                async def one(url):
                    try:
                        await self.check_robots(url, hosts)
                        old = cached.get(url)
                        from_cache = False
                        if old and (directory / old['file']).exists():
                            raw = (directory / old['file']).read_bytes()
                            if hashlib.sha256(raw).hexdigest() != old['sha256']:
                                raise FetchFailure('cached_evidence_hash_mismatch')
                            final, status, html = old['final_url'], 200, raw.decode('utf-8', errors='replace')
                            checked_at = old['checked_at']
                            from_cache = True
                        else:
                            final, status, html, raw = await self.fetch(url, hosts)
                            checked_at = now()
                        if final != url:
                            await self.check_robots(final, hosts)
                        parsed = parse_page(raw, final)
                        sha = hashlib.sha256(raw).hexdigest()
                        filename = sha + '.html'
                        (directory / filename).write_bytes(raw)
                        page = dict(url=url, final_url=final, status=status, checked_at=checked_at,
                                    file=filename, sha256=sha, title=parsed['title'], from_cache=from_cache)
                        return page, parsed
                    except FetchFailure as exc:
                        return dict(url=url, status=exc.status, error=str(exc)), None
                responses = await asyncio.gather(*(one(u) for u in targets))
                for page, parsed in responses:
                    result['pages'].append(page)
                    if parsed is None:
                        result['errors'].append(page)
                        continue
                    seen.add(canonical_url(page['final_url']))
                    result['issues'].extend(dict(url=page['final_url'], reason=i) for i in parsed['issues'])
                    pid = profile_key(page['final_url'])
                    if pid:
                        result['fetched_profiles'].append(pid)
                    for link in parsed['links']:
                        if allowed_url(link, hosts):
                            if profile_key(link):
                                result['discovered_profiles'].append(profile_key(link))
                            if canonical_url(link) not in seen:
                                frontier.add(link)
                    for record in parsed['records']:
                        record.update(source_key=key, verified_at=page['checked_at'], source_status='official_published',
                                      evidence_sha256=page['sha256'], evidence_file=str(directory.relative_to(self.output) / page['file']))
                        identity = profile_key(record['profile_url'] or '') or f"listing:{record['name'].casefold()}:{record['department'].casefold()}"
                        old = profile_records.get(identity)
                        if old is None or record['extraction'] == 'employee_profile':
                            if old:
                                for field in ('title', 'department', 'email', 'phone', 'department_phone'):
                                    record[field] = record.get(field) or old.get(field, '')
                                extra = list(old.get('additional_evidence', []))
                                if old['evidence_sha256'] != record['evidence_sha256']:
                                    extra.append({k: old[k] for k in ('page_url', 'verified_at', 'evidence_file', 'evidence_sha256')})
                                record['additional_evidence'] = extra
                            profile_records[identity] = record
                # Checkpoint the completed batch. A cancelled run cannot look complete.
                result['contacts'] = list(profile_records.values())
                result['updated_at'] = now()
                temp = directory / 'result.tmp'
                temp.write_text(json.dumps(result, indent=2) + '\n')
                temp.replace(previous_path)
        result['discovered_profiles'] = sorted(set(result['discovered_profiles']))
        result['fetched_profiles'] = sorted(set(result['fetched_profiles']))
        parsed_ids = {profile_key(c['profile_url'] or '') for c in result['contacts']}
        missing = set(result['discovered_profiles']) - set(result['fetched_profiles'])
        unparsed = set(result['fetched_profiles']) - parsed_ids
        result['unprocessed_profiles'] = sorted(missing | unparsed)
        if result['errors'] or missing:
            result['status'] = 'retry'
        elif result['issues'] or unparsed or not result['contacts']:
            result['status'] = 'review'
        else:
            result['status'] = 'extracted'
        result['finished_at'] = now()
        previous_path.write_text(json.dumps(result, indent=2) + '\n')
        return result


async def run(args):
    inventory = json.loads(Path(args.inventory).read_text())
    sources = inventory['sources']
    if args.host:
        sources = [s for s in sources if s['host'] in args.host]
    queue = asyncio.Queue()
    for source in sources:
        queue.put_nowait(source)
    results = []
    async with Crawler(args.output, args.workers, args.per_host, args.delay, args.timeout, args.attempts) as crawler:
        async def worker():
            while not queue.empty():
                source = queue.get_nowait()
                try:
                    result = await crawler.crawl(source)
                    results.append(result)
                    print(json.dumps(dict(source_key=result['source_key'], host=result['host'], status=result['status'], pages=len(result['pages']), contacts=len(result['contacts']))), flush=True)
                finally:
                    queue.task_done()
        await asyncio.gather(*(worker() for _ in range(min(args.workers, len(sources)))))
    report = dict(started_sources=len(sources), sources_with_pages=sum(any(p.get('status') == 200 for p in r['pages']) for r in results),
                  profiles_fetched=sum(sum(p.get('status') == 200 and not p.get('from_cache') and bool(profile_key(p.get('final_url', '')))
                                          for p in r['pages']) for r in results),
                  profiles_processed=sum(len(r['fetched_profiles']) for r in results), contacts_extracted=sum(len(r['contacts']) for r in results),
                  retry=sum(r['status'] == 'retry' for r in results), review=sum(r['status'] == 'review' for r in results),
                  extracted=sum(r['status'] == 'extracted' for r in results), results=results)
    Path(args.output, 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'results'}))
    return 2 if report['retry'] or report['review'] else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', default='data/civicplus/supplied-inventory.json')
    parser.add_argument('--output', required=True)
    parser.add_argument('--host', action='append')
    parser.add_argument('--workers', type=int, default=24)
    parser.add_argument('--per-host', type=int, default=2)
    parser.add_argument('--delay', type=float, default=.5)
    parser.add_argument('--timeout', type=float, default=25)
    parser.add_argument('--attempts', type=int, default=3)
    args = parser.parse_args()
    if min(args.workers, args.per_host, args.attempts) < 1 or args.delay < 0 or args.timeout <= 0:
        parser.error('Invalid concurrency, retry, delay or timeout')
    return asyncio.run(run(args))


if __name__ == '__main__':
    raise SystemExit(main())
