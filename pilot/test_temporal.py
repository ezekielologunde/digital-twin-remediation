import unittest
from temporal_policy import KEYS, decisions

class TemporalTests(unittest.TestCase):
    def test_change_invalidates_only_later_evidence(self):
        good={k:{'verified':True} for k in KEYS}
        bad={k:{'verified':k!='timeline_redis'} for k in KEYS}
        result=decisions(good,good,bad)
        self.assertEqual(result['cached']['decision'],'approve')
        self.assertEqual(result['refresh_before_wait']['decision'],'approve')
        self.assertEqual(result['last_moment_refresh']['decision'],'abstain')

    def test_unknown_is_not_success(self):
        unknown={k:{'verified':None} for k in KEYS}
        self.assertTrue(all(v['decision']=='abstain' for v in decisions(unknown,unknown,unknown).values()))

if __name__=='__main__':unittest.main()
