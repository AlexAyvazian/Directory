import unittest
from scripts.refresh_registries import extract_contacts, reconcile
class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.source={"id":"ga-test","state":"GA","county":"Example","department":"Human Resources","url":"https://example.gov/m/directory"}
    def test_staff_record_does_not_guess_emails(self):
        html="<main><ul><li>Jane Example<p>Human Resources Director</p><p>555-111-2222</p></li></ul></main>"
        people=extract_contacts(html,self.source)
        self.assertEqual(people[0]["name"],"Jane Example")
        self.assertEqual(people[0]["email"],"")
    def test_email_only_from_staff_row(self):
        html='<main><p>contact@county.gov</p><ul><li>Jane Example<p>Human Resources Director</p><a href="mailto:jane@county.gov">Email</a></li></ul></main>'
        people=extract_contacts(html,self.source)
        self.assertEqual(people[0]["email"],"jane@county.gov")
    def test_cross_row_email_not_assigned(self):
        html='<main><p>hr@county.gov</p><ul><li>Jane Example<p>Human Resources Director</p></li></ul></main>'
        self.assertEqual(extract_contacts(html,self.source)[0]["email"],"")
    def test_broken_page_keeps_previous_staff(self):
        previous={"contacts":[{"name":"Jane Example","email":"jane@county.gov"}]}
        value=reconcile(previous,self.source,[],"Temporary outage","2026-10-13")
        self.assertEqual(value["contacts"],previous["contacts"])
    def test_partial_result_does_not_erase_staff(self):
        previous={"contacts":[{"name":f"Person {i}"} for i in range(8)]}
        new=[{"name":"Person 0"}]
        value=reconcile(previous,self.source,new,None,"2026-10-13")
        self.assertEqual(len(value["contacts"]),8)
if __name__=="__main__":unittest.main()
