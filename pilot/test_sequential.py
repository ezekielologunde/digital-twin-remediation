import subprocess
import unittest
from sequential_probes import collect


class SequentialTests(unittest.TestCase):
    def test_stops_after_first_failure_and_marks_rest_unknown(self):
        calls=[]
        def docker(args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args, 1, '', 'unavailable')
        ids={'home-timeline-redis':'r','user-mongodb':'m','nginx-thrift':'n'}
        result=collect(docker,ids,1,2,'marker',early_stop=True)
        self.assertEqual(len(calls),1)
        self.assertFalse(result['timeline_redis']['verified'])
        self.assertIsNone(result['timeline_mongo']['verified'])
        self.assertFalse(result['post_storage']['executed'])

    def test_full_mode_runs_all_checks_after_failure(self):
        calls=[]
        def docker(args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args, 1, '', 'unavailable')
        ids={'home-timeline-redis':'r','user-mongodb':'m','nginx-thrift':'n'}
        result=collect(docker,ids,1,2,'marker')
        self.assertEqual(len(calls),3)
        self.assertTrue(all(v['executed'] for v in result.values()))

    def test_approval_requires_all_record_checks_and_preserves_large_ids(self):
        from sequential_probes import policies
        import json
        post='1640442405943160832'
        responses=[post+'\n',json.dumps({'ids':['NumberLong("'+post+'")']}),
                   json.dumps([{'post_id':post,'text':'marker','creator':'1'}])]
        calls=[]
        def docker(args, **kwargs):
            value=responses[len(calls)]
            calls.append(args)
            return subprocess.CompletedProcess(args,0,value,'')
        result=collect(docker,{'home-timeline-redis':'r','user-mongodb':'m','nginx-thrift':'n'},1,post,'marker',early_stop=True)
        self.assertEqual(len(calls),3)
        self.assertEqual(policies('verified_readback',result)['direct_dependencies']['decision'],'approve')

    def test_mongo_failure_stops_before_rpc_and_abstains(self):
        from sequential_probes import policies
        responses=['2\n','{"ids":[]}']; calls=[]
        def docker(args, **kwargs):
            value=responses[len(calls)];calls.append(args)
            return subprocess.CompletedProcess(args,0,value,'')
        result=collect(docker,{'home-timeline-redis':'r','user-mongodb':'m','nginx-thrift':'n'},1,2,'marker',early_stop=True)
        self.assertEqual(len(calls),2)
        self.assertIsNone(result['post_storage']['verified'])
        self.assertEqual(policies('verified_readback',result)['direct_dependencies']['decision'],'abstain')

if __name__=='__main__':unittest.main()
