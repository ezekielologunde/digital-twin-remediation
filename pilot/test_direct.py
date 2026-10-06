import json
import unittest
from types import SimpleNamespace
from direct_probes import collect,policies

class DirectChecks(unittest.TestCase):
    def test_unknown_obligation_abstains(self):
        d={k:{'verified':True} for k in ('timeline_redis','timeline_mongo','post_storage')}
        d['timeline_mongo']['verified']=False
        p=policies('verified_readback',d)
        self.assertEqual(p['alternate_plus_redis']['decision'],'approve')
        self.assertEqual(p['direct_dependencies']['decision'],'abstain')
    def test_large_ids_are_not_rounded_and_semantics_match(self):
        pid='8197683483884212225'
        def run(args,**kw):
            if 'redis-cli' in args:raw=pid+'\n'
            elif 'mongo' in args:raw=json.dumps({'ids':['NumberLong("'+pid+'")']})
            else:raw=json.dumps([{'post_id':pid,'text':'known','creator':'123'}])
            return SimpleNamespace(returncode=0,stdout=raw)
        d=collect(run,{'home-timeline-redis':'a','user-mongodb':'b','nginx-thrift':'c'},123,pid,'known')
        self.assertTrue(all(v['verified'] for v in d.values()))
    def test_successful_exit_with_wrong_record_is_not_verified(self):
        def run(args,**kw):return SimpleNamespace(returncode=0,stdout='{}')
        d=collect(run,{'home-timeline-redis':'a','user-mongodb':'b','nginx-thrift':'c'},123,'456','known')
        self.assertFalse(any(v['verified'] for v in d.values()))

if __name__=='__main__':unittest.main()
