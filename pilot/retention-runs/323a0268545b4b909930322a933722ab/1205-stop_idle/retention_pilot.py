"""Action-scoped direct dependency probe comparison.

Creates and tears down only uniquely named dtrem-direct-* projects from the locked config.
"""
from pathlib import Path
from datetime import datetime, timezone
import concurrent.futures
import hashlib
import json
import random
import shutil
import socket
import subprocess
import time
import uuid
from urllib.parse import urlencode
from probe import request, classify_read
from dependency_twin import operational_states
from race_probes import collect
from aligned_event_policy import decide
from retention_witness import Witness


HERE = Path(__file__).resolve().parent
BASE = 'http://127.0.0.1:19980'
SERVICE = 'user-timeline-service'

def empty_timeline(status, body):
    if status != 200:
        return False
    try:
        return json.loads(body) in ([], {})
    except (ValueError, TypeError):
        return False

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run_arm(batch, seed, arm, previous_volumes, diagnostic=None):
    project = f'dtrem-retention-{batch.name[:8]}-{seed}-{diagnostic}'
    out = batch / f'{seed}-{diagnostic}'
    out.mkdir()
    for filename in ('probe.py', 'retention_pilot.py', 'retention_witness.py', 'race_probes.py', 'aligned_event_policy.py', 'dependency_twin.py', 'validity_twin.py', 'image-lock.json', 'observed-call-graph.json'):
        shutil.copyfile(HERE / filename, out / filename)
    shutil.copytree(HERE/'dependency-audit',out/'dependency-audit')
    config = json.loads((HERE / 'compose.locked.json').read_text())
    config['name'] = project
    for name, net in config['networks'].items():
        net['name'] = project + '-' + name
    for name, service in config['services'].items():
        service['labels']['research.stage'] = 'event-retention'
        for port in service.get('ports', []):
            port['published'] = '19980' if name == 'nginx-thrift' else '19986'
    config_file = out / 'compose.json'
    config_file.write_text(json.dumps(config, indent=2))
    events = []
    def log(row):
        row['recorded_utc'] = datetime.now(timezone.utc).isoformat()
        events.append(row)
        with (out / 'ledger.jsonl').open('a', encoding='utf-8') as f:
            f.write(json.dumps(row) + '\n')
    def docker(args, check=True, timeout=90):
        start = time.perf_counter()
        proc = subprocess.run(['docker', *args], capture_output=True, text=True, timeout=timeout)
        log({'kind': 'docker', 'args': args, 'duration_s': time.perf_counter()-start,
             'returncode': proc.returncode, 'stdout': proc.stdout, 'stderr': proc.stderr})
        if check:
            proc.check_returncode()
        return proc
    def compose(*args, **kwargs):
        return docker(['compose', '-p', project, '-f', str(config_file), *args], **kwargs)
    def call(phase, path, data=None, timeout=1):
        value = request(BASE, path, data, timeout=timeout)
        log({'kind': 'http', 'phase': phase, **value})
        return value
    # Both arms of a seed use the same account IDs, graph and post text.
    user_id = 8_000_000 + seed * 2
    username = f'paired_{seed}'
    markers = [f'paired_seed_{seed}_post_{i}' for i in range(3)]
    read_stop=3 if diagnostic=='mongo_down_short' else 100
    path = '/wrk2-api/user-timeline/read?' + urlencode({'user_id': user_id, 'start': 0, 'stop': read_stop})
    scenario = {'seed': seed, 'user_id': user_id, 'username': username, 'markers': markers,
                'fault': 'stop user-timeline-service', 'horizon_s': 8, 'poll_interval_s': 0.5, 'backend_condition': diagnostic, 'read_stop': read_stop,
                'candidate_action':'docker start verified target container ID only; no Compose dependency startup'}
    (out / 'scenario.json').write_text(json.dumps(scenario, indent=2))
    summary = {'project': project, 'seed': seed, 'arm': arm, 'backend_condition': diagnostic, 'status': 'PENDING',
               'scenario_sha256': digest(out / 'scenario.json'), 'compose_sha256': digest(config_file)}
    launch_attempted = False
    witness = None
    try:
        for port in (19980, 19986):
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', port))
        existing = docker(['ps', '-aq', '--filter', f'label=com.docker.compose.project={project}'])
        if existing.stdout.strip():
            raise RuntimeError('Unique project already exists; refusing to overwrite')
        launch_attempted = True
        compose('up', '-d', '--pull', 'never')
        ids = compose('ps', '-aq').stdout.split()
        info = json.loads(docker(['inspect', *ids]).stdout)
        if len(info) != len(config['services']):
            raise RuntimeError('Container set does not match configuration')
        if any(c['Config']['Labels'].get('research.project') != 'digital-twin-remediation' or
               c['Config']['Labels'].get('com.docker.compose.project') != project for c in info):
            raise RuntimeError('Project identity mismatch')
        volumes = {m['Name'] for c in info for m in c['Mounts'] if m['Type'] == 'volume'}
        summary['volume_names'] = sorted(volumes)
        summary['fresh_volume_ids'] = bool(volumes) and not bool(volumes & previous_volumes)
        if not summary['fresh_volume_ids']:
            raise RuntimeError('Missing/new-volume check failed')
        deadline = time.monotonic() + 45
        while True:
            pre = call('pre_initialization_empty_check', path)
            if pre['status'] == 200:
                if not empty_timeline(pre['status'], pre['body']):
                    raise RuntimeError('Unexpected prior timeline content')
                break
            if time.monotonic() >= deadline:
                raise RuntimeError('Readiness deadline exceeded')
            time.sleep(1)
        summary['empty_before_initialization'] = True
        for uid, name in [(user_id, username), (user_id+1, username+'_f')]:
            row = call('register', '/wrk2-api/user/register', {'first_name':'Synthetic',
                'last_name':'Pair', 'username':name, 'password':'local-synthetic-account','user_id':uid}, timeout=5)
            if row['status'] != 200 or row['body'].strip() != 'Success!':
                raise RuntimeError('Registration failed')
        row = call('follow', '/wrk2-api/user/follow', {'user_id':user_id+1,'followee_id':user_id}, timeout=5)
        if row['status'] != 200 or row['body'].strip() != 'Success!':
            raise RuntimeError('Follow setup failed')
        for marker in markers:
            row = call('baseline_write', '/wrk2-api/post/compose', {
                'user_id':user_id,'username':username,'post_type':0,'text':marker}, timeout=5)
            if row['status'] != 200 or row['body'].strip() != 'Successfully upload post':
                raise RuntimeError('Baseline write not acknowledged')
        baseline = call('baseline_read', path, timeout=5)
        if any(classify_read(baseline['status'],baseline['body'],m,user_id) != 'verified_readback' for m in markers):
            raise RuntimeError('Baseline marker check failed')
        summary['baseline_markers_verified'] = len(markers)
        selected_post=next(p for p in json.loads(baseline['body']) if p['text']==markers[-1])
        known_post_id=selected_post['post_id']
        helper_ids={c['Config']['Labels']['com.docker.compose.service']:c['Id'] for c in info}
        compose('stop', '--timeout', '2', SERVICE)
        fault = call('fault_read', path)
        summary['fault_detected'] = classify_read(fault['status'],fault['body'],markers[-1],user_id) != 'verified_readback'
        if not summary['fault_detected']:
            raise RuntimeError('Fault did not interrupt the read')
        target_id = next(c['Id'] for c in info if c['Config']['Labels']['com.docker.compose.service'] == SERVICE)
        summary['target_container_id']=target_id
        stopped = json.loads(docker(['inspect', target_id]).stdout)[0]
        if stopped['State']['Running']:
            raise RuntimeError('Target not stopped at decision boundary')
        def snapshot():
            items=json.loads(docker(['inspect',*ids]).stdout)
            return {'sampled_monotonic':time.perf_counter(),
                    'sampled_utc':datetime.now(timezone.utc).isoformat(),
                    'operational_states':operational_states(items),
                    'states':{c['Config']['Labels']['com.docker.compose.service']:c['State']['Running'] for c in items}}
        probe_path='/wrk2-api/home-timeline/read?'+urlencode({'user_id':user_id+1,'start':0,'stop':100})
        probe_baseline=call('functional_baseline',probe_path,timeout=3)
        if classify_read(probe_baseline['status'],probe_baseline['body'],markers[-1],user_id)!='verified_readback':
            raise RuntimeError('Alternate-route functional baseline failed')
        summary['functional_baseline_verified']=True
        direct_baseline=collect(docker,helper_ids,user_id,known_post_id,markers[-1])
        summary['direct_baseline']=direct_baseline
        if not all(x['verified'] for x in direct_baseline.values()):
            raise RuntimeError('Direct dependency baseline failed')
        history_start=int(time.time())-1
        def history():
            until=time.time_ns()
            text_until=f'{until//1000000000}.{until%1000000000:09d}'
            start=time.perf_counter()
            raw=docker(['events','--since',str(history_start),'--until',text_until,
                '--filter','label=com.docker.compose.project='+project,'--format','{{json .}}'],timeout=15)
            return [json.loads(line) for line in raw.stdout.splitlines() if line.strip()],time.perf_counter()-start
        anchor,anchor_duration=history()
        if not anchor:raise RuntimeError('No daemon-event cursor available')
        cursor=max(int(e.get('timeNano',0)) for e in anchor)
        timings={'final_start':time.perf_counter()}
        evidence=collect(docker,helper_ids,user_id,known_post_id,markers[-1])
        timings['final_end']=time.perf_counter()
        if not all(v['verified'] for v in evidence.values()):
            raise RuntimeError('Initial final checks did not all pass')
        witness=Witness(project,out/'witness.jsonl')
        noise=helper_ids['media-service']
        time.sleep(.5)
        docker(['rename',noise,project+'-witness-ready'])
        witness.wait(noise,'rename')
        faulted=diagnostic.startswith('stop_')
        churn=diagnostic.endswith('_churn')
        stop_record=None
        if faulted:
            docker(['stop','--time','2',helper_ids['user-timeline-redis']])
            stop_record=witness.wait(helper_ids['user-timeline-redis'],'stop')
        timings['intervention_start']=time.perf_counter()
        if churn:
            for _ in range(100):docker(['exec',noise,'true'])
        docker(['rename',noise,project+'-witness-finished'])
        witness.wait(noise,'rename')
        timings['intervention_end']=time.perf_counter()
        order='events_first' if seed%2 else 'functional_first'
        def late_check():
            timings['late_start']=time.perf_counter()
            value=collect(docker,helper_ids,user_id,known_post_id,markers[-1])
            timings['late_end']=time.perf_counter()
            return value
        def query():
            timings['query_start']=time.perf_counter()
            value,duration=history()
            timings['query_end']=time.perf_counter()
            return value,duration
        if order=='events_first':
            daemon_events,query_duration=query();late=late_check()
        else:
            late=late_check();daemon_events,query_duration=query()
        received=timings['query_end']
        late_duration=timings['late_end']-timings['late_start']
        dependency_names=('user-timeline-redis','user-timeline-mongodb','post-storage-service')
        dependency_ids={helper_ids[k] for k in dependency_names}
        timings['state_start']=time.perf_counter()
        observed=json.loads(docker(['inspect',*sorted(dependency_ids)]).stdout)
        timings['state_end']=time.perf_counter()
        running={v['Id']:v['State']['Running'] for v in observed}
        retained=any(e.get('Action')=='stop' and e.get('Actor',{}).get('ID')==helper_ids['user-timeline-redis'] and int(e.get('timeNano',0))>cursor for e in daemon_events)
        summary['retention']={'faulted':faulted,'churn':churn,'churn_exec_calls':100 if churn else 0,
            'order':order,'stop_witness':stop_record,'stop_retained':retained,'query_records':len(daemon_events),
            'eviction_verified':bool(stop_record) and not retained,'history_start':history_start}
        policy_time=time.perf_counter()
        predictions,changes=decide(evidence,daemon_events,dependency_ids,cursor,running,received+10,policy_time,late)
        predictions={k:v for k,v in predictions.items() if k in ('final_checks','fresh_running_state','events_available','late_functional_recheck')}
        summary['final_evidence']=evidence
        summary['timings']=timings
        summary['predictions']=predictions
        summary['event_inputs']={'events':daemon_events,'cursor':cursor,'dependency_ids':sorted(dependency_ids),
            'running':running,'delayed_available_at':received+10,'decision_time':policy_time,
            'late_evidence':late,'late_duration_s':late_duration,'query_duration_s':query_duration,'anchor_duration_s':anchor_duration,'matched_changes':changes}
        (out/'predictions-before-action.json').write_text(json.dumps({'predictions':predictions,
            'evidence':evidence,'event_inputs':summary['event_inputs'],'timings':dict(timings)},indent=2))
        log({'kind':'predictions_sealed','sha256':digest(out/'predictions-before-action.json')})
        decision = time.perf_counter()
        timings['action_decision']=decision
        log({'kind':'action_decision','monotonic':decision})
        observations = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(docker, ['start',target_id]) if arm == 'start' else None
            next_poll = decision
            while time.perf_counter() - decision < scenario['horizon_s']:
                time.sleep(max(0, next_poll - time.perf_counter()))
                remaining = scenario['horizon_s']-(time.perf_counter()-decision)
                if remaining <= 0:
                    break
                row = call('outcome_read', path, timeout=min(1,remaining))
                result = {'elapsed_s':time.perf_counter()-decision,
                          'classification':classify_read(row['status'],row['body'],markers[-1],user_id)}
                observations.append(result)
                log({'kind':'outcome',**result})
                next_poll = max(next_poll+0.5,time.perf_counter())
            if future:
                future.result()
        summary['post_action_states']=snapshot()['states']
        if summary['post_action_states']['user-timeline-mongodb'] != True:
            raise RuntimeError('MongoDB action-scope check failed')
        if summary['post_action_states']['user-timeline-redis'] != (not faulted):
            raise RuntimeError('Redis action-scope check failed')
        successes = [x['elapsed_s'] for x in observations if x['classification']=='verified_readback' and x['elapsed_s']<=8]
        summary.update(status='COMPLETE', recovered_by_8s=bool(successes),
                       first_verified_read_from_decision_s=min(successes) if successes else None,
                       outcome_observations=observations,
                       contract_met=(len(observations)>=2 and all(x['classification']=='verified_readback' and x['elapsed_s']<=8 for x in observations[-2:]) and not any(x['classification']=='creator_mismatch' for x in observations)),
                       note='Development-only false-recovery-approval diagnostic; predictions shadow-scored, actions not gated')
    except Exception as exc:
        summary.update(status='FAILED',error=str(exc))
    finally:
        if witness:
            witness.close()
            summary['witness_sha256']=digest(out/'witness.jsonl')
        # Destroy only this run's disposable application state, never the original pilot.
        if launch_attempted:
            try:
                ids = compose('ps','-aq').stdout.split()
                if ids:
                    info = json.loads(docker(['inspect',*ids]).stdout)
                    if any(c['Config']['Labels'].get('com.docker.compose.project') != project or
                           c['Config']['Labels'].get('research.project') != 'digital-twin-remediation' for c in info):
                        raise RuntimeError('Refusing cleanup of unverified containers')
                cleanup = compose('down','--volumes','--timeout','2',check=False)
                summary['cleanup_returncode'] = cleanup.returncode
            except Exception as exc:
                summary['cleanup_error'] = str(exc)
        summary['ledger_sha256'] = digest(out / 'ledger.jsonl') if (out/'ledger.jsonl').exists() else None
        (out / 'summary.json').write_text(json.dumps(summary,indent=2))
        print(json.dumps({k:v for k,v in summary.items() if k not in ('outcome_observations','volume_names','predictions','direct_baseline','post_action_states','event_inputs','final_evidence') }),flush=True)
    return summary

def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--batch',required=True);args=parser.parse_args()
    batch=HERE/'retention-runs'/args.batch
    plan=json.loads((batch/'plan.json').read_text())
    for name,h in plan['source_sha256'].items():
        if digest(HERE/name)!=h:raise RuntimeError('Frozen source changed: '+name)
    volumes=set();results=[]
    if (batch/'summary.json').exists():raise RuntimeError('Refusing to overwrite a started batch')
    for seed,condition in plan['arms']:
        if (batch/'STOP_AFTER_ARM').exists():break
        row=run_arm(batch,seed,'start',volumes,diagnostic=condition)
        results.append(row);volumes.update(row.get('volume_names',[]))
        (batch/'summary.json').write_text(json.dumps(results,indent=2))
        if row['status']!='COMPLETE' or row.get('cleanup_returncode')!=0:break
    return 0 if len(results)==len(plan['arms']) and all(r['status']=='COMPLETE' for r in results) else 2

if __name__=='__main__':raise SystemExit(main())
