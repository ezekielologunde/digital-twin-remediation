import unittest
from aligned_event_policy import decide

class AlignedEventTests(unittest.TestCase):
    def test_late_failure_does_not_inherit_stale_success(self):
        p,_=decide({'r':{'verified':True}},[],{'dep'},10,{'dep':True},11,1,{'r':{'verified':False}})
        self.assertEqual(p['final_checks']['decision'],'approve')
        self.assertEqual(p['events_available']['decision'],'approve')
        self.assertEqual(p['late_functional_recheck']['decision'],'abstain')
    def test_successful_late_check_is_distinct_from_conservative_event_rejection(self):
        e={'Type':'container','Actor':{'ID':'dep'},'Action':'restart','timeNano':12}
        p,_=decide({'r':{'verified':True}},[e],{'dep'},10,{'dep':True},11,1,{'r':{'verified':True}})
        self.assertEqual(p['events_available']['decision'],'abstain')
        self.assertEqual(p['late_functional_recheck']['decision'],'approve')

if __name__=='__main__':unittest.main()
