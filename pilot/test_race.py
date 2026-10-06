import json
import subprocess
import unittest
from race_probes import collect

class RaceTests(unittest.TestCase):
    def test_hook_occurs_after_result_and_before_next_command(self):
        events=[]
        replies=['2\n','{"ids":["2"]}',json.dumps([{'post_id':'2','text':'m','creator':'1'}])]
        def docker(args,**kwargs):
            i=sum(e[0]=='command' for e in events)
            events.append(('command',i))
            return subprocess.CompletedProcess(args,0,replies[i],'')
        def hook(name,result):
            self.assertTrue(result['verified'])
            self.assertLessEqual(result['started_monotonic'],result['completed_monotonic'])
            events.append(('hook',name))
        result=collect(docker,{'home-timeline-redis':'r','user-mongodb':'m','nginx-thrift':'n'},1,2,'m',after_probe=hook)
        self.assertEqual([e[0] for e in events],['command','hook']*3)
        self.assertTrue(all(v['verified'] for v in result.values()))

    def test_hook_exception_prevents_remaining_checks(self):
        calls=[]
        def docker(args,**kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args,0,'2\n','')
        def hook(name,result):raise RuntimeError('Injection failed')
        with self.assertRaises(RuntimeError):
            collect(docker,{'home-timeline-redis':'r','user-mongodb':'m','nginx-thrift':'n'},1,2,'m',after_probe=hook)
        self.assertEqual(len(calls),1)

if __name__=='__main__':unittest.main()
