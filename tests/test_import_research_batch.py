import unittest
from scripts.import_research_batch import contact, source, merge_batch, general

class BatchImportTests(unittest.TestCase):
    def test_basic_sourced_person(self):
        row={"state_abbr":"GA","county_name":"Fayette","county_fips":"13113","contact_name":"Jane Example",
             "job_title":"HR Director","email":"jane@fayettecountyga.gov","phone":"770-555-1212",
             "department":"Human Resources","source_url":"https://www.fayettecountyga.gov/hr"}
        c=contact(row)
        self.assertEqual(c["state"],"GA")
        self.assertEqual(c["fips"],"13113")
        self.assertEqual(c["email"],"jane@fayettecountyga.gov")
        self.assertEqual(c["contactType"],"person")
    def test_unsourced_email_not_published(self):
        c=contact({"state":"IN","county":"Hamilton","name":"Jane Example",
                   "title":"HR Director","email":"jane@hamiltoncounty.in.gov"})
        self.assertEqual(c["email"],"")
    def test_missing_fips_is_empty(self):
        self.assertEqual(general({"state":"GA","county":"Fulton"})["fips"],"")
    def test_department_mailbox_is_not_an_employee(self):
        c=contact({"state":"IN","county":"Monroe","department":"Employee Services",
                   "email":"hr@co.monroe.in.us","record_type":"department",
                   "source_url":"https://www.in.gov/counties/monroe/"})
        self.assertEqual(c["name"],"")
        self.assertEqual(c["contactType"],"department")
    def test_repeated_batch_is_idempotent(self):
        r={"state":"GA","county":"Fayette","name":"Jane Example","title":"HR Director",
           "source_url":"https://www.fayettecountyga.gov/hr","email":"jane@fayettecountyga.gov"}
        one,_=merge_batch({},{"contacts":[r]})
        two,stats=merge_batch(one,{"contacts":[r]})
        self.assertEqual(len(two["contacts"]),1)
        self.assertEqual(stats["contacts"]["added"],0)
    def test_conflict_keeps_previous_email(self):
        prev={"state":"GA","county":"Fayette","name":"Jane Example","title":"HR Director",
           "source_url":"https://www.fayettecountyga.gov/hr","email":"first@fayettecountyga.gov"}
        newer={**prev,"email":"second@fayettecountyga.gov"}
        one,_=merge_batch({},{"contacts":[prev]})
        two,_=merge_batch(one,{"contacts":[newer]})
        self.assertEqual(two["contacts"][0]["email"],"first@fayettecountyga.gov")
        self.assertEqual(len(two["conflicts"]),1)
    def test_keep_department_phone_without_email(self):
        c=contact({"state":"GA","county":"Hall","department":"Human Resources",
                   "job_title":"Human Resources department line","phone":"770-531-6712",
                   "source_url":"https://www.hallcounty.org/309/Human-Resources"})
        self.assertIsNotNone(c)
        self.assertEqual(c["contactType"],"department")
        self.assertEqual(c["phone"],"770-531-6712")
    def test_hold_unconfirmed_obfuscated_email(self):
        c=contact({"state":"GA","county":"Pickens","contact_name":"Paula Peace",
                   "job_title":"HR Director","email":"ppeace@pickenscountyga.gov",
                   "verification_status":"email_from_obfuscated_link_verify",
                   "source_url":"https://www.pickenscountyga.gov/directory.aspx"})
        self.assertEqual(c["email"],"")
    def test_shared_hr_inbox_not_personal_email(self):
        c=contact({"state":"GA","county":"DeKalb","contact_name":"Rogelio Blackman",
                   "job_title":"Policy Manager","email":"hrpolicydivision@dekalbcountyga.gov",
                   "source_url":"https://dekalbcountyga.gov/departments/human-resources"})
        self.assertEqual(c["name"],"Rogelio Blackman")
        self.assertEqual(c["email"],"")
    def test_new_unresearched_placeholder_does_not_erase_researched_county(self):
        existing={"coverage":[{"state":"GA","county":"Fayette","fips":"13113",
                  "research_status":"officially_verified_staff_extracted","number_of_contacts":"8"}]}
        incoming={"coverage":[{"state_abbr":"GA","county_name":"Fayette","county_fips":"13113",
                 "research_status":"not_yet_researched","number_of_contacts":"0"}]}
        merged,_=merge_batch(existing,incoming)
        self.assertEqual(merged["coverage"][0]["research_status"],"officially_verified_staff_extracted")
        self.assertEqual(merged["coverage"][0]["number_of_contacts"],"8")
    def test_county_source_link(self):
        s=source({"state_abbr":"GA","county_name":"Fayette","directory_url":"https://www.fayettecountyga.gov/hr"})
        self.assertTrue(s["url"].startswith("https://"))
    def test_web_search_result_not_county_directory(self):
        self.assertIsNone(source({"state":"GA","county":"Fayette","directory_url":"https://google.com/search?q=fayette"}))
if __name__=="__main__":unittest.main()
