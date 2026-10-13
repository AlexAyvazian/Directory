import unittest
from scripts.scan_my_half_staff_pages import Links,find_links,safe_same_site,scan_site

class WebsiteScanningTests(unittest.TestCase):
    def test_url_scope_blocks_cross_host(self):
        self.assertFalse(safe_same_site("https://evil.example/path","https://countyalameda.gov"))
        self.assertFalse(safe_same_site("http://countyalameda.gov/hr","https://countyalameda.gov"))
        self.assertTrue(safe_same_site("https://www.countyalameda.gov/hr","https://countyalameda.gov"))
    def test_directory_links_from_homepage(self):
        page="""<html><body><a href="/departments/human-resources">Human Resources</a>
        <a href="/jobs">Job openings</a><a href="/staff-directory">Employee Directory</a>
        <a href="https://other.gov/staff">External directory</a></body></html>"""
        links=find_links(page,"https://county.gov/")
        self.assertEqual(len(links),2)
        self.assertEqual(links[0]["url"],"https://county.gov/staff-directory")
    def test_does_not_guess_missing_directory(self):
        links=find_links("<a href='/parks'>Parks</a>","https://county.gov/")
        self.assertEqual(links,[])
    def test_pdf_links_not_staff_pages(self):
        self.assertFalse(safe_same_site("https://county.gov/uploads/phonebook.pdf","https://county.gov/"))
    def test_no_live_data_claim_from_raw_candidate(self):
        links=find_links('<a href="/departments/human-resources">Contact HR</a>',"https://county.gov/")
        self.assertEqual(links[0]["label"],"Contact HR")
        self.assertNotIn("email",links[0])
if __name__=="__main__":unittest.main()
