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
    project = f'dtrem-aligned-{batch.name[:8]}-{seed}-{diagnostic}'
    out = batch / f'{seed}-{diagnostic}'
    out.mkdir()
    for filename in ('probe.py', 'aligned_event_pilot.py', 'race_probes.py', 'aligned_event_policy.py', 'dependency_twin.py', 'validity_twin.py', 'image-lock.json', 'observed-call-graph.json'):
        shutil.copyfile(HERE / filename, out / filename)
    shutil.copytree(HERE/'dependency-audit',out/'dependency-audit')
    config = json.loads((HERE / 'compose.locked.json').read_text())
    config['name'] = project
    for name, net in config['networks'].items():
        net['name'] = project + '-' + name
    for name, service in config['services'].items():
        service['labels']['research.stage'] = 'aligned-event-comparison'
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
        def history():
            until=time.time_ns()
            text_until=f'{until//1000000000}.{until%1000000000:09d}'
            start=time.perf_counter()
            raw=docker(['events','--since',str(until//1000000000-120),'--until',text_until,
                '--filter','label=com.docker.compose.project='+project,'--format','{{json .}}'],timeout=15)
            return [json.loads(line) for line in raw.stdout.splitlines() if line.strip()],time.perf_counter()-start
        anchor,anchor_duration=history()
        if not anchor:raise RuntimeError('No daemon-event cursor available')
        cursor=max(int(e.get('timeNano',0)) for e in anchor)
        timings={'final_start':time.perf_counter()}
        evidence=collect(docker,helper_ids,user_id,known_post_id,markers[-1])
        timings['final_end']=time.perf_counter()
        if diagnostic=='redis_stop':compose('stop','--timeout','2','user-timeline-redis')
        elif diagnostic=='unrelated_stop':compose('stop','--timeout','2','media-service')
        elif diagnostic=='storage_suspend':
            docker(['kill','--signal=SIGSTOP',helper_ids['post-storage-service']])
            status=docker(['exec',helper_ids['post-storage-service'],'cat','/proc/1/status']).stdout
            if 'T' not in next(x for x in status.splitlines() if x.startswith('State:')).split(':',1)[1]:
                raise RuntimeError('Storage process not suspended')
        elif diagnostic!='none':raise ValueError('Unknown condition')
        daemon_events,query_duration=history()
        received=time.perf_counter()
        dependency_names=('user-timeline-redis','user-timeline-mongodb','post-storage-service')
        dependency_ids={helper_ids[k] for k in dependency_names}
        observed=json.loads(docker(['inspect',*sorted(dependency_ids)]).stdout)
        running={v['Id']:v['State']['Running'] for v in observed}
        late_start=time.perf_counter()
        late=collect(docker,helper_ids,user_id,known_post_id,markers[-1])
        late_duration=time.perf_counter()-late_start
        policy_time=time.perf_counter()
        predictions,changes=decide(evidence,daemon_events,dependency_ids,cursor,running,received+10,policy_time,late)
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
        if summary['post_action_states']['user-timeline-redis'] != (diagnostic!='redis_stop'):
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
    batch=HERE/'aligned-event-runs'/uuid.uuid4().hex
    batch.mkdir(parents=True)
    plan=[(seed,c) for seed in (1101,1102) for c in ('none','unrelated_stop','redis_stop','storage_suspend')]
    random.Random(20261013).shuffle(plan)
    (batch/'plan.json').write_text(json.dumps({'arms':plan,'development_only':True,'horizon_s':8,
        'policies':['final_checks','fresh_running_state','events_available','events_delayed','events_silently_dropped','late_functional_recheck'],
        'design':'Eight new fresh instances add functional rechecking after the fault, alongside event observations. Event query precedes late probes; all decisions are shadow-scored on shared outcomes. No policy latency advantage or held-out claim.'},indent=2))
    for name in ('aligned_event_pilot.py','aligned_event_policy.py','race_probes.py','dependency_twin.py','validity_twin.py','Aligned event comparison design.md'):
        shutil.copyfile(HERE/name,batch/name)
    print('Batch '+str(batch),flush=True)
    volumes,results=set(),[]
    for seed,condition in plan:
        if (batch/'STOP_AFTER_ARM').exists():break
        row=run_arm(batch,seed,'start',volumes,diagnostic=condition)
        results.append(row);volumes.update(row.get('volume_names',[]))
        (batch/'summary.json').write_text(json.dumps(results,indent=2))
        if row['status']!='COMPLETE' or row.get('cleanup_returncode')!=0:break
    return 0 if len(results)==8 and all(r['status']=='COMPLETE' and r.get('cleanup_returncode')==0 for r in results) else 2

if __name__=='__main__':raise SystemExit(main())
