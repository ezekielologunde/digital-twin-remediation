import unittest
from validity_twin import decide

class DecisionContracts(unittest.TestCase):
    def test_known_failed_dependency_rejects(self):
        self.assertEqual(decide([('user-timeline-service','post-storage-service')],{'post-storage-service':False},0)['decision'],'reject')
    def test_unknown_dependency_abstains(self):
        self.assertEqual(decide([('user-timeline-service','missing')],{},0)['decision'],'abstain')
    def test_age_gate_uses_observed_age(self):
        self.assertEqual(decide([],{},2,max_age_s=1)['decision'],'abstain')
    def test_missing_edge_exposes_closed_world_assumption(self):
        # A known blind spot of this baseline, not a desirable safety property.
        self.assertEqual(decide([],{'post-storage-service':False},0)['decision'],'approve')
    def test_cycles_terminate(self):
        self.assertEqual(decide([('user-timeline-service','a'),('a','user-timeline-service')],{'a':True},0)['decision'],'approve')

if __name__=='__main__':unittest.main()
