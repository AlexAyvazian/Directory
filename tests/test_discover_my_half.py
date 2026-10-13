import unittest
from scripts.discover_my_half import match_cisa, match_gsa, merge, OWNER, STATE_NAMES
import scripts.discover_my_half as d

class DomainDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.roster=[
            {"id":"r1","abbr":"CA","county":"Alameda","full":"Alameda County","fips":"06001"},
            {"id":"r2","abbr":"TX","county":"Clay","full":"Clay County","fips":"48077"},
            {"id":"r3","abbr":"TX","county":"Clayton","full":"Clayton County","fips":"48078"},
            {"id":"r4","abbr":"GA","county":"Gwinnett","full":"Gwinnett County","fips":"13135"}
        ]
        d.STATE_NAMES={"california":"CA","texas":"TX","georgia":"GA"}
    def test_exact_county_domain(self):
        rows=[{"Domain name":"alamedacounty.gov","Domain type":"County","Organization name":"Alameda County Government","Suborganization name":"","State":"CA"}]
        matched=match_cisa(rows,self.roster)
        self.assertEqual(matched["r1"][0]["domain"],"alamedacounty.gov")
    def test_different_state_not_contaminated(self):
        rows=[{"Domain name":"gwinnettcountyga.gov","Domain type":"County","Organization name":"Gwinnett County","State":"GA"}]
        self.assertFalse(match_cisa(rows,self.roster))
    def test_ignore_county_sheriff(self):
        rows=[{"Domain name":"alamedasheriff.gov","Domain type":"County","Organization name":"Alameda County Sheriff","State":"CA"}]
        self.assertFalse(match_cisa(rows,self.roster))
    def test_no_similar_county_name_collision(self):
        self.assertFalse(d.is_relevant_county_site("Clayton County Government","claytoncounty.gov","Clay"))
    def test_gsa_non_gov_and_state(self):
        row={"Domain":"acgov.org","Level of Government":"County Government","Location":"California","Note":"Alameda County CA -- Note added 2013","Status":"accepted term"}
        matched=match_gsa([row],self.roster)
        self.assertIn("r1",matched)
    def test_one_jurisdiction_one_domain_set(self):
        cand={"r1":[{"domain":"alamedacounty.gov"}]}
        merged=merge(cand,cand,self.roster)
        self.assertEqual(len(merged),1)
        self.assertEqual(len(merged[0]["domains"]),1)
if __name__=="__main__":unittest.main()
