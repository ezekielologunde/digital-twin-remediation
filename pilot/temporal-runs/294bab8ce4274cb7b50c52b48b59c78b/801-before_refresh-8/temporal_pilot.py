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
from sequential_probes import collect
from temporal_policy import decisions

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

def run_arm(batch, seed, arm, previous_volumes, diagnostic=None, delay_s=4):
    project = f'dtrem-time-{batch.name[:8]}-{seed}-{diagnostic}-{delay_s}'
    out = batch / f'{seed}-{diagnostic}-{delay_s}'
    out.mkdir()
    for filename in ('probe.py', 'temporal_pilot.py', 'sequential_probes.py', 'temporal_policy.py', 'dependency_twin.py', 'validity_twin.py', 'image-lock.json', 'observed-call-graph.json'):
        shutil.copyfile(HERE / filename, out / filename)
    shutil.copytree(HERE/'dependency-audit',out/'dependency-audit')
    config = json.loads((HERE / 'compose.locked.json').read_text())
    config['name'] = project
    for name, net in config['networks'].items():
        net['name'] = project + '-' + name
    for name, service in config['services'].items():
        service['labels']['research.stage'] = 'temporal-dependency-probes'
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
                'fault': 'stop user-timeline-service', 'horizon_s': 8, 'poll_interval_s': 0.5, 'backend_condition': diagnostic, 'delay_s':delay_s, 'read_stop': read_stop,
                'candidate_action':'docker start verified target container ID only; no Compose dependency startup'}
    (out / 'scenario.json').write_text(json.dumps(scenario, indent=2))
    summary = {'project': project, 'seed': seed, 'arm': arm, 'backend_condition': diagnostic, 'delay_s':delay_s, 'status': 'PENDING',
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
        cached_end=time.perf_counter()
        timings={'cached_end':cached_end}
        def inject():
            timings['fault_command_start']=time.perf_counter()
            compose('stop','--timeout','2','user-timeline-redis')
            state=json.loads(docker(['inspect',helper_ids['user-timeline-redis']]).stdout)[0]
            if state['State']['Running']:raise RuntimeError('Redis stop was not effective')
            timings['fault_verified_stopped']=time.perf_counter()
            log({'kind':'fault_boundary',**timings})
        if diagnostic=='before_refresh':inject()
        timings['refresh_start']=time.perf_counter()
        refresh=collect(docker,helper_ids,user_id,known_post_id,markers[-1])
        timings['refresh_end']=time.perf_counter()
        log({'kind':'temporal_refresh','results':refresh,'timings':dict(timings)})
        if diagnostic=='after_refresh':inject()
        elif diagnostic not in ('none','before_refresh'):raise ValueError('Unknown condition')
        deadline=timings['refresh_end']+delay_s
        time.sleep(max(0,deadline-time.perf_counter()))
        timings['last_check_start']=time.perf_counter()
        if timings['last_check_start']-deadline>0.5:
            raise RuntimeError('Scheduled delay boundary exceeded by over 0.5 seconds')
        last=collect(docker,helper_ids,user_id,known_post_id,markers[-1])
        timings['last_check_end']=time.perf_counter()
        predictions=decisions(direct_baseline,refresh,last)
        summary['temporal_evidence']={'cached':direct_baseline,'refresh':refresh,'last':last}
        summary['timings']=timings
        summary['predictions']=predictions
        pred={'predictions':predictions,'evidence':summary['temporal_evidence'],'timings':dict(timings)}
        (out/'predictions-before-action.json').write_text(json.dumps(pred,indent=2))
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
        if summary['post_action_states']['user-timeline-redis'] != (diagnostic=='none'):
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
        print(json.dumps({k:v for k,v in summary.items() if k not in ('outcome_observations','volume_names','predictions','direct_baseline','post_action_states') }),flush=True)
    return summary

def main():
    batch=HERE/'temporal-runs'/uuid.uuid4().hex
    batch.mkdir(parents=True)
    plan=[(801,c,d) for c in ('none','before_refresh','after_refresh') for d in (4,8)]
    random.Random(20261010).shuffle(plan)
    (batch/'plan.json').write_text(json.dumps({'arms':plan,'development_only':True,'horizon_s':8,
        'action':'docker start verified target container ID only',
        'design':'Three Redis fault placements crossed with two minimum refresh-end to last-check-start delays, six fresh instances. All evidence policies share each action outcome.',
        'policies':['cached','refresh_before_wait','last_moment_refresh'],
        'boundary':'Faults are scheduled before or after middle refresh, never after final refresh. This does not establish atomic verification. Actual timestamps are required; more than 0.5s delay overshoot stops batch.'},indent=2))
    for name in ('temporal_pilot.py','sequential_probes.py','temporal_policy.py','dependency_twin.py','validity_twin.py','Temporal verification design.md'):
        shutil.copyfile(HERE/name,batch/name)
    print('Batch '+str(batch),flush=True)
    volumes,results=set(),[]
    for seed,condition,delay in plan:
        if (batch/'STOP_AFTER_ARM').exists():break
        row=run_arm(batch,seed,'start',volumes,diagnostic=condition,delay_s=delay)
        results.append(row);volumes.update(row.get('volume_names',[]))
        (batch/'summary.json').write_text(json.dumps(results,indent=2))
        if row['status']!='COMPLETE' or row.get('cleanup_returncode')!=0:break
    return 0 if len(results)==6 and all(r['status']=='COMPLETE' and r.get('cleanup_returncode')==0 for r in results) else 2

if __name__=='__main__':raise SystemExit(main())
