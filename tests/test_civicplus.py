import asyncio
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from aiohttp import web

from scripts.crawl_civicplus import Crawler, canonical_url, parse_page, profile_key


class DirectoryParsingTests(unittest.TestCase):
    def test_equivalent_profile_routes_share_employee_identity(self):
        self.assertEqual(profile_key('https://example.gov/Directory.aspx?EID=42'),
                         profile_key('https://example.gov/m/directory/employee?eid=42'))
        self.assertEqual(canonical_url('https://example.gov/Directory.aspx?EID=42#staff'),
                         'https://example.gov/directory.aspx?eid=42')
        self.assertIsNone(profile_key('https://example.gov/m/directory/employee'))

    def test_table_rows_do_not_borrow_other_employees_details(self):
        html = '''<table><tr><th>Name</th><th>Title</th><th>Email</th><th>Phone</th></tr>
        <tr><td><a href="/Directory.aspx?EID=1">Test Person</a></td><td>Director</td>
        <td><a href="mailto:staff@example.gov">Email</a></td><td>555-123-4567</td></tr>
        <tr><td>Other Person</td><td>Clerk</td><td><a href="/contact">Email form</a></td><td></td></tr></table>'''
        parsed = parse_page(html, 'https://example.gov/Directory.aspx')
        self.assertEqual(len(parsed['records']), 2)
        self.assertEqual(parsed['records'][0]['email'], 'staff@example.gov')
        self.assertEqual(parsed['records'][1]['email'], '')
        self.assertEqual(parsed['records'][1]['phone'], '')

    def test_profile_keeps_published_fields_without_guessing_email(self):
        html = '''<main><h2>Example Employee</h2><p>Title: Safety Officer</p>
        <p>Department: Public Works</p><p>Phone: 555-123-4567 ext. 9</p>
        <a href="/FormCenter/Email">Email Example</a></main>'''
        parsed = parse_page(html, 'https://example.gov/m/directory/employee?eid=8')
        self.assertEqual(parsed['records'][0]['title'], 'Safety Officer')
        self.assertEqual(parsed['records'][0]['department'], 'Public Works')
        self.assertEqual(parsed['records'][0]['email'], '')
        self.assertEqual(parsed['records'][0]['phone'], '555-123-4567 ext. 9')

    def test_empty_profile_and_postback_require_review(self):
        parsed = parse_page('<main><h2>Staff Directory</h2><a href="javascript:__doPostBack()">Next</a></main>',
                            'https://example.gov/Directory.aspx?EID=9')
        self.assertEqual(parsed['records'], [])
        self.assertIn('employee_profile_not_extracted', parsed['issues'])
        self.assertIn('javascript_navigation_requires_review', parsed['issues'])


class TraversalTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.calls, self.active, self.peak = [], 0, 0
        self.fail_profile = False
        self.block_robots = False
        self.rate_limit_once = False
        @web.middleware
        async def track_parallelism(request, handler):
            self.active += 1
            self.peak = max(self.peak, self.active)
            try:
                await asyncio.sleep(.01)
                return await handler(request)
            finally:
                self.active -= 1
        self.app = web.Application(middlewares=[track_parallelism])
        self.app.router.add_get('/{tail:.*}', self.serve)
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, '127.0.0.1', 0)
        await self.site.start()
        self.base = 'http://127.0.0.1:' + str(self.site._server.sockets[0].getsockname()[1])
        self.source = dict(source_key='fixture:127.0.0.1', host='127.0.0.1', submitted_urls=[self.base + '/Directory.aspx'],
                           entry_urls=[self.base + '/Directory.aspx'])

    async def asyncTearDown(self):
        await self.runner.cleanup()
        self.temp.cleanup()

    async def serve(self, request):
        self.calls.append(request.path_qs)
        if request.path == '/robots.txt':
            return web.Response(text='User-agent: *\nDisallow: /\n' if self.block_robots else 'User-agent: *\nAllow: /\n')
        if request.path.lower() == '/directory.aspx':
            return web.Response(text='''<a href="/m/directory/department?did=1">HR</a><a href="/m/directory/department?did=2">Works</a>
            <table><tr><th>Name</th><th>Email</th></tr><tr><td><a href="/m/directory/employee?eid=1">Fixture Employee A</a></td>
            <td><a href="mailto:fixture@example.test">Email</a></td></tr></table>''')
        if request.path.endswith('department'):
            if request.query.get('page') == '2':
                return web.Response(text='<a href="/m/directory/employee?eid=3">Third employee</a>')
            page = '<a href="/m/directory/employee?eid=1">First employee</a><a href="/m/directory/employee?eid=2">Second employee</a>'
            return web.Response(text=page + '<a href="/m/directory/department?did=1&page=2">Next</a>')
        if request.path.endswith('employee'):
            if self.fail_profile and request.query.get('eid') == '2':
                return web.Response(status=503)
            if self.rate_limit_once:
                self.rate_limit_once = False
                return web.Response(status=429, headers={'Retry-After': '0'})
            return web.Response(text=f'<main><h2>Fixture Employee {"ABC"[int(request.query["eid"])-1]}</h2><p>Title: Director</p></main>')
        return web.Response(status=404)

    async def crawl(self, attempts=1):
        async with Crawler(self.temp.name, workers=6, per_host=2, delay=0, attempts=attempts) as crawler:
            return await crawler.crawl(self.source)

    async def test_traverses_all_departments_pagination_profiles_and_reuses_evidence(self):
        result = await self.crawl()
        self.assertEqual(result['status'], 'extracted')
        self.assertEqual(len(result['contacts']), 3)
        self.assertEqual(result['discovered_profiles'], ['employee:1', 'employee:2', 'employee:3'])
        person = next(c for c in result['contacts'] if c['name'] == 'Fixture Employee A')
        self.assertEqual(person['email'], 'fixture@example.test')
        self.assertEqual(len(person['additional_evidence']), 1)
        self.assertLessEqual(self.peak, 2)
        self.assertGreaterEqual(self.peak, 2)
        for record in result['contacts']:
            self.assertEqual(hashlib.sha256(Path(self.temp.name, record['evidence_file']).read_bytes()).hexdigest(), record['evidence_sha256'])
        first_calls = len(self.calls)
        repeated = await self.crawl()
        self.assertEqual(repeated['contacts'], result['contacts'])
        self.assertTrue(all(p == '/robots.txt' for p in self.calls[first_calls:]))

    async def test_profile_failure_stays_retry_and_is_retried_next_run(self):
        self.fail_profile = True
        result = await self.crawl()
        self.assertEqual(result['status'], 'retry')
        self.assertEqual(result['unprocessed_profiles'], ['employee:2'])
        self.fail_profile = False
        result = await self.crawl()
        self.assertEqual(result['status'], 'extracted')
        self.assertEqual(len(result['contacts']), 3)

    async def test_robots_restriction_never_fetches_directory(self):
        self.block_robots = True
        result = await self.crawl()
        self.assertEqual(result['status'], 'retry')
        self.assertEqual(result['contacts'], [])
        self.assertEqual(self.calls, ['/robots.txt'])

    async def test_explicit_rate_limit_retries_then_reconciles_profiles(self):
        self.rate_limit_once = True
        result = await self.crawl(attempts=2)
        self.assertEqual(result['status'], 'extracted')
        self.assertEqual(len(result['fetched_profiles']), 3)


if __name__ == '__main__':
    unittest.main()
