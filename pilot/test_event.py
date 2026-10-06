import unittest
from event_policy import decide

class EventTests(unittest.TestCase):
    def check(self,events,now=1):
        return decide({'r':{'verified':True}},events,{'dep'},10,{'dep':True},11,now)[0]
    def test_relevant_transition_invalidates_only_delivered_channel(self):
        e={'Type':'container','Actor':{'ID':'dep'},'Action':'kill','timeNano':12}
        r=self.check([e])
        self.assertEqual(r['events_available']['decision'],'abstain')
        self.assertEqual(r['events_delayed']['decision'],'approve')
        self.assertEqual(self.check([e],12)['events_delayed']['decision'],'abstain')
    def test_unrelated_old_and_exec_events_do_not_invalidate(self):
        events=[{'Type':'container','Actor':{'ID':i},'Action':a,'timeNano':t}
                for i,a,t in [('other','stop',12),('dep','stop',9),('dep','exec_die',13)]]
        self.assertEqual(self.check(events)['events_available']['decision'],'approve')
    def test_functional_failure_is_never_overridden(self):
        r,_=decide({'r':{'verified':False}},[],{'dep'},10,{'dep':True},11,1)
        self.assertTrue(all(v['decision']=='abstain' for v in r.values()))

if __name__=='__main__':unittest.main()
