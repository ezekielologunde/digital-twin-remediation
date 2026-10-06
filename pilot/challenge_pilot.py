"""Frozen functional-probe challenge with randomized observed-graph masks.

Creates and tears down only uniquely named dtrem-chal-* projects from the locked config.
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
from challenge_twin import compare

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

def run_arm(batch, seed, arm, previous_volumes, diagnostic=None, removed_edges=None):
    project = f'dtrem-chal-{batch.name[:8]}-{seed}-{diagnostic}-{arm}'
    out = batch / f'{seed}-{diagnostic}-{arm}'
    out.mkdir()
    for filename in ('probe.py', 'challenge_pilot.py', 'challenge_twin.py', 'dependency_twin.py', 'validity_twin.py', 'image-lock.json', 'observed-call-graph.json'):
        shutil.copyfile(HERE / filename, out / filename)
    shutil.copytree(HERE/'dependency-audit',out/'dependency-audit')
    config = json.loads((HERE / 'compose.locked.json').read_text())
    config['name'] = project
    for name, net in config['networks'].items():
        net['name'] = project + '-' + name
    for name, service in config['services'].items():
        service['labels']['research.stage'] = 'functional-challenge'
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
    path = '/wrk2-api/user-timeline/read?' + urlencode({'user_id': user_id, 'start': 0, 'stop': 100})
    scenario = {'seed': seed, 'user_id': user_id, 'username': username, 'markers': markers,
                'fault': 'stop user-timeline-service', 'horizon_s': 8, 'poll_interval_s': 0.5, 'backend_condition': diagnostic}
    (out / 'scenario.json').write_text(json.dumps(scenario, indent=2))
    summary = {'project': project, 'seed': seed, 'arm': arm, 'backend_condition': diagnostic, 'status': 'PENDING',
               'scenario_sha256': digest(out / 'scenario.json'), 'compose_sha256': digest(config_file)}
    (out/'edge-mask.json').write_text(json.dumps(removed_edges,indent=2))
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
        compose('stop', '--timeout', '2', SERVICE)
        fault = call('fault_read', path)
        summary['fault_detected'] = classify_read(fault['status'],fault['body'],markers[-1],user_id) != 'verified_readback'
        if not summary['fault_detected']:
            raise RuntimeError('Fault did not interrupt the read')
        target_id = next(c['Id'] for c in info if c['Config']['Labels']['com.docker.compose.service'] == SERVICE)
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
        old=snapshot()
        storage_id=next(c['Id'] for c in info if c['Config']['Labels']['com.docker.compose.service']=='post-storage-service')
        if diagnostic=='process_suspended':
            docker(['kill','--signal=SIGSTOP',storage_id])
            status=docker(['exec',storage_id,'cat','/proc/1/status']).stdout
            state_line=next(x for x in status.splitlines() if x.startswith('State:'))
            if 'T' not in state_line.split(':',1)[1]:
                raise RuntimeError('Storage PID 1 not stopped by signal')
        elif diagnostic=='network_disconnected':
            docker(['network','disconnect',config['networks']['default']['name'],storage_id])
            state=json.loads(docker(['inspect',storage_id]).stdout)[0]
            if config['networks']['default']['name'] in state['NetworkSettings']['Networks']:
                raise RuntimeError('Storage still connected to project network')
        elif diagnostic=='timeline_redis_down':
            compose('stop','--timeout','2','user-timeline-redis')
        elif diagnostic!='up':
            raise ValueError('Unrecognized challenge condition')
        # Deliberate age manipulation; same minimum delay in both backend conditions.
        time.sleep(max(0,2-(time.perf_counter()-old['sampled_monotonic'])))
        functional=call('functional_probe_before_action',probe_path,timeout=1)
        functional_classification=classify_read(functional['status'],functional['body'],markers[-1],user_id)
        summary['functional_probe']={'classification':functional_classification,'elapsed_ms':functional['elapsed_ms']}
        fresh=snapshot()
        revalidated=snapshot()
        now=time.perf_counter()
        for sample in (old,fresh,revalidated):
            sample['age_s']=now-sample['sampled_monotonic']
        graph=json.loads((out/'observed-call-graph.json').read_text())
        witness=json.loads((out/'dependency-audit'/'witness.json').read_text())
        if digest(out/'dependency-audit'/'UserTimelineHandler.h')!=witness['source_sha256']:
            raise RuntimeError('Witness source hash mismatch')
        predictions=compare(graph,removed_edges,revalidated,witness,functional_classification)
        (out/'predictions-before-action.json').write_text(json.dumps({'old':old,'fresh':fresh,'revalidated':revalidated,'predictions':predictions,'removed_edges':removed_edges,'functional_probe':summary['functional_probe']},indent=2))
        log({'kind':'predictions_sealed','sha256':digest(out/'predictions-before-action.json')})
        summary['predictions']=predictions
        decision = time.perf_counter()
        observations = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(compose, 'start', SERVICE) if arm == 'start' else None
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
        print(json.dumps({k:v for k,v in summary.items() if k not in ('outcome_observations','volume_names','predictions') }),flush=True)
    return summary

def main():
    batch=HERE/'challenge-runs'/uuid.uuid4().hex
    batch.mkdir(parents=True)
    plan=[(seed,condition,arm) for seed in (401,402,403) for condition in ('up','process_suspended','network_disconnected','timeline_redis_down') for arm in ('start',)]
    random.Random(20261007).shuffle(plan)
    edges=[(e['source'],e['target']) for e in json.loads((HERE/'observed-call-graph.json').read_text())['edges']]
    mask_rng=random.Random(17761007)
    masks={f'{seed}-{condition}':mask_rng.sample(edges,3) for seed,condition,arm in plan}
    (batch/'plan.json').write_text(json.dumps({'arms':plan,'development_only':True,'horizon_s':8,'min_stale_age_s':2,'matched_approval_count':6,'selection_salt':'challenge-v1-fixed-before-outcomes','edge_masks':masks,'removed_edge_count':3,'reference_edge_count':len(edges),'functional_probe_timeout_s':1,'comparison':'Uniform label-blind thinning among eligible approvals, exact combinatorial risk distribution at six approvals. Also report a fixed SHA256-ranked subset. No forced approvals when fewer than six eligible.','contract':'Last two scheduled readbacks verified within 8 seconds and no observed creator mismatch. Recovery validity only, not collateral safety.','design':'Twelve fresh start interventions, three seed blocks and four conditions. Three of thirteen observed edges sampled without replacement per trial. Same live outcome shared by three frozen shadow policies. Functional probe uses alternate home-timeline route; not full target-path validation.'},indent=2))
    print('Batch '+str(batch),flush=True)
    shutil.copyfile(Path(__file__),batch/'challenge_pilot.py')
    for name in ('challenge_twin.py','dependency_twin.py','validity_twin.py','analyze_challenge.py','analyze_dependency.py'):
        shutil.copyfile(HERE/name,batch/name)
    shutil.copytree(HERE/'dependency-audit',batch/'dependency-audit')
    volumes,results=set(),[]
    for seed,condition,arm in plan:
        row=run_arm(batch,seed,arm,volumes,diagnostic=condition,removed_edges=masks[f'{seed}-{condition}'])
        results.append(row);volumes.update(row.get('volume_names',[]))
        (batch/'summary.json').write_text(json.dumps(results,indent=2))
        if row['status']!='COMPLETE' or row.get('cleanup_returncode')!=0:break
    return 0 if len(results)==12 and all(r['status']=='COMPLETE' and r.get('cleanup_returncode')==0 for r in results) else 2

if __name__=='__main__':raise SystemExit(main())
