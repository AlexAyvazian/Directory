import unittest
from scripts.import_free_association_fl import parse_directory_page,collect,GROUPS,PERSON

BASE="https://www.fl-counties.com/directory-results/?group=157253"
SAMPLE="""<html><head></head><body><main><h1>Directory Results</h1>
<p>Search Results for: Human Resources/Personnel</p>
<div><h3>Austin, Judy</h3><p>HR Director</p><p>Jackson County</p>
<p>2864 Madison St. Marianna, FL 32448</p><p>(850) 482-9633</p>
<p><a href="mailto:austinj@jacksoncountyfl.gov">austinj@jacksoncountyfl.gov</a></p></div>
<div><h3>Baber, Doug</h3><p>Director of Human Resources and Risk Manager</p>
<p>St. Lucie County</p><p>(772) 462-4056</p><p>baberd@stlucieco.org</p></div>
<div><h3>Burns, Randy</h3><p>Claims Adjuster - Workers' Compensation</p>
<p>Escambia County</p><p>(850) 595-4918</p></div>
<p>Page 1 of 1</p></main></body></html>"""

class FreeAssociationTests(unittest.TestCase):
    def test_published_name_title_phone_email_and_county(self):
        entries=parse_directory_page(SAMPLE,BASE,"Human Resources/Personnel")
        self.assertEqual(len(entries),2,entries)
        judy=next(x for x in entries if x["name"]=="Judy Austin")
        self.assertEqual(judy["county"],"Jackson")
        self.assertEqual(judy["email"],"austinj@jacksoncountyfl.gov")
        self.assertEqual(judy["phone"],"(850) 482-9633")
        self.assertEqual(judy["sourceUrl"],BASE)
        self.assertIn("needs-county-confirmation",judy["verificationStatus"])
    def test_excludes_claims_related_job(self):
        entries=parse_directory_page(SAMPLE,BASE,"Human Resources/Personnel")
        self.assertFalse(any(x["name"]=="Randy Burns" for x in entries))
    def test_does_not_guess_missing_email(self):
        src=SAMPLE.replace("baberd@stlucieco.org","")
        entries=parse_directory_page(src,BASE,"Human Resources/Personnel")
        person=next(x for x in entries if x["name"]=="Doug Baber")
        self.assertEqual(person["email"],"")
    def test_ignores_unrelated_navigation(self):
        self.assertEqual(parse_directory_page("<h1>Directory Results</h1><p>Austin, Judy</p><p>HR Director</p>",BASE,"Human Resources/Personnel"),[])
    def test_stops_on_repeated_page(self):
        # The site might return page 1 for all page parameters; do not loop forever.
        found=collect(lambda url:SAMPLE,groups={"Human Resources/Personnel":"157253"},limit=10,delay=0)
        self.assertEqual(len(found),2)
    def test_exact_group_codes(self):
        self.assertEqual(GROUPS["Human Resources/Personnel"],"157253")
        self.assertEqual(GROUPS["Purchasing & Acquisition"],"157259")
        self.assertEqual(GROUPS["Risk Management"],"157260")
if __name__=="__main__":unittest.main()
