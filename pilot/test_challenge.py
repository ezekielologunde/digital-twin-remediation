import unittest
from challenge_twin import compare

class ChallengeChecks(unittest.TestCase):
    def setUp(self):
        self.graph={'edges':[{'source':'user-timeline-service','target':'post-storage-service'}]}
        self.snapshot={'states':{'post-storage-service':True},'operational_states':{'post-storage-service':True},'age_s':0}
        self.witness={'supported_edges':[['user-timeline-service','post-storage-service']]}
    def test_unobserved_functional_result_is_abstention(self):
        out=compare(self.graph,[],self.snapshot,self.witness,'unresolved_read_error')
        self.assertEqual(out['alternate_route_probe']['decision'],'abstain')
        self.assertEqual(out['source_operational']['decision'],'approve')
    def test_invalid_mask_is_not_silently_accepted(self):
        with self.assertRaises(ValueError):
            compare(self.graph,[['fake','edge']],self.snapshot,self.witness,'verified_readback')
    def test_repair_uses_witness_and_observed_state(self):
        self.snapshot['operational_states']['post-storage-service']=False
        out=compare(self.graph,self.witness['supported_edges'],self.snapshot,self.witness,'verified_readback')
        self.assertEqual(out['random_graph_state']['decision'],'approve')
        self.assertEqual(out['source_operational']['decision'],'reject')

if __name__=='__main__':unittest.main()
