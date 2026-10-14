"""Batch 2 regression tests: real source records, no missing counties or duplicates."""
import csv
import json
import unittest
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
STORE = BASE / "data/registries/research-batch.json"
ATLAS = BASE / "assets/js/atlas-data.js"
ARCHIVE = BASE / "data/imports/claude-26-states-batch2-2026-10-13"
def read_csv(name):
    with (ARCHIVE/name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))
def n(v):
    return "".join(x for x in str(v or "").lower() if x.isalnum())

class BatchTwoIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store=json.loads(STORE.read_text(encoding="utf-8"))
        js=ATLAS.read_text(encoding="utf-8")
        cls.atlas=json.loads(js.split("window.ATLAS_DATA=",1)[1].rsplit(";",1)[0])
    def test_original_batch_exports_preserved(self):
        expected={"county_contacts.csv":758,"county_registry_sources.csv":356,
                  "county_research_coverage.csv":1578,"county_changes.csv":569}
        for filename,count in expected.items():
            with self.subTest(filename=filename):
                self.assertEqual(len(read_csv(filename)),count)
    def test_second_batch_complete(self):
        s=self.store
        self.assertEqual(len(s["coverage"]),1578)
        self.assertEqual(len(s["changes"]),569)
        self.assertEqual(len(s["sources"]),351)
        self.assertEqual(len(s["contacts"]),772)
        self.assertEqual(sum(bool(c["name"]) for c in s["contacts"]),568)
        self.assertEqual(sum(bool(c["name"] and c["email"]) for c in s["contacts"]),228)
        self.assertEqual(sum(c["research_status"]!="not_yet_researched" for c in s["coverage"]),293)
    def test_no_duplicate_named_contact_keys(self):
        keys=[(x["state"],x["fips"],n(x["name"]),n(x["title"]),n(x["department"]))
              for x in self.store["contacts"] if x["contactType"]=="person"]
        self.assertEqual(len(keys),len(set(keys)))
    def test_all_contacts_resolve_to_atlas(self):
        byfips={x["fips"] for x in self.atlas["jurisdictions"] if x.get("fips")}
        byname={(x["abbr"],n(x["county"])) for x in self.atlas["jurisdictions"]}
        for x in self.store["contacts"]:
            with self.subTest(state=x["state"],county=x["county"],name=x["name"]):
                self.assertTrue(x["fips"] in byfips or (x["state"],n(x["county"])) in byname)
    def test_distinct_same_named_jurisdictions_preserved(self):
        entries={(x["state"],x["county"],x["fips"]) for x in self.store["coverage"]}
        self.assertIn(("MD","Baltimore","24005"),entries)
        self.assertIn(("MD","Baltimore","24510"),entries)
        self.assertIn(("VA","Richmond","51760"),entries)
        self.assertIn(("VA","Richmond","51159"),entries)
        self.assertIn(("DC","Human Resources","11001"),entries)
    def test_historical_emails_not_presented_as_current(self):
        for x in self.store["contacts"]:
            if x["verificationStatus"]=="historical_lead_requiring_verification":
                self.assertFalse(x["email"])
    def test_department_mailboxes_not_people(self):
        for x in self.store["contacts"]:
            if x["contactType"]=="department":
                self.assertFalse(x["name"])
if __name__=="__main__":unittest.main()
