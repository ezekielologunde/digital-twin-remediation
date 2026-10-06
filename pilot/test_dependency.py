import unittest
from analyze_dependency import thinning_distribution
from dependency_twin import compare_views, operational_states

class DependencyChecks(unittest.TestCase):
    def test_paused_running_container_is_not_operational(self):
        items=[{'Config':{'Labels':{'com.docker.compose.service':'x'}},
                'State':{'Running':True,'Paused':True,'Restarting':False}}]
        self.assertFalse(operational_states(items)['x'])
    def test_source_repair_and_pause_check_are_separate(self):
        graph={'edges':[{'source':'user-timeline-service','target':'post-storage-service'}]}
        snap={'states':{'post-storage-service':True},'operational_states':{'post-storage-service':False},'age_s':0}
        witness={'supported_edges':[['user-timeline-service','post-storage-service']]}
        result=compare_views(graph,snap,snap,snap,witness)
        self.assertEqual(result['source_repair_refresh']['decision'],'approve')
        self.assertEqual(result['source_repair_operational']['decision'],'reject')
    def test_thinning_has_exact_small_distribution(self):
        d=thinning_distribution(4,2,2)
        self.assertAlmostEqual(d['0'],1/6)
        self.assertAlmostEqual(d['1'],4/6)
        self.assertAlmostEqual(d['2'],1/6)
    def test_insufficient_coverage_is_not_forced(self):
        self.assertIsNone(thinning_distribution(3,1,6))

if __name__=='__main__':unittest.main()
