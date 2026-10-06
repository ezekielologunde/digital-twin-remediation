"""Single-service measurement feasibility check, not a causal gate experiment.

Stops and restarts ONLY the labeled dtrem-pilot user-timeline-service container.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re
import subprocess
import time
import uuid
from probe import request, classify_read
from urllib.parse import urlsplit, parse_qs

HERE = Path(__file__).resolve().parent
SERVICE = 'user-timeline-service'
CONTAINER = 'dtrem-pilot-user-timeline-service-1'

def main(baseline):
    if not re.fullmatch('[0-9a-f]{32}', baseline):
        raise ValueError('Expected a baseline run ID')
    source = HERE / 'runs' / baseline
    summary = json.loads((source / 'summary.json').read_text())
    raw = (source / 'ledger.jsonl').read_bytes()
    if not summary.get('all_readbacks_verified') or hashlib.sha256(raw).hexdigest() != summary['ledger_sha256']:
        raise ValueError('Requires a successful, integrity-checked baseline')
    ledger = [json.loads(line) for line in raw.decode().splitlines()]
    marker = [x for x in ledger if x['phase'] == 'compose'][-1]['marker']
    read_path = [x for x in ledger if x['phase'] == 'readback'][-1]['path']
    user_id = parse_qs(urlsplit(read_path).query)['user_id'][0]
    info = json.loads(subprocess.check_output(['docker', 'inspect', CONTAINER], text=True))[0]
    labels = info['Config']['Labels']
    if (labels.get('com.docker.compose.project') != 'dtrem-pilot' or
            labels.get('research.project') != 'digital-twin-remediation' or
            labels.get('com.docker.compose.service') != SERVICE or not info['State']['Running']):
        raise RuntimeError('Target identity or running state not verified')
    out = HERE / 'recovery-runs' / uuid.uuid4().hex
    out.mkdir(parents=True)
    records = []
    def save(row):
        records.append(row)
        with (out / 'ledger.jsonl').open('a') as f:
            f.write(json.dumps(row) + '\n')
    def read(phase):
        result = request('http://127.0.0.1:18880', read_path, timeout=1)
        state = classify_read(result['status'], result['body'], marker, user_id)
        save({'phase': phase, 'classification': state, **result})
        return state
    def action(verb):
        start = time.perf_counter()
        args = ['docker', 'compose', '-f', str(HERE / 'compose.locked.json'), verb]
        if verb == 'stop':
            args += ['--timeout', '2']
        args += [SERVICE]
        proc = subprocess.run(args, capture_output=True, text=True, timeout=40)
        save({'phase': 'action', 'verb': verb, 'container_id': info['Id'],
              'utc': datetime.now(timezone.utc).isoformat(), 'duration_s': time.perf_counter()-start,
              'returncode': proc.returncode, 'stdout': proc.stdout, 'stderr': proc.stderr})
        proc.check_returncode()
    if read('before') != 'verified_readback':
        raise RuntimeError('Fresh pre-action readback failed; no service stopped')
    stop_attempted = False
    restarted = False
    try:
        stop_attempted = True
        action('stop')
        during = [read('stopped') for _ in range(3)]
        action('start')
        restarted = True
        recovery_start = time.perf_counter()
        recovered = False
        while time.perf_counter() - recovery_start < 30:
            if read('after_start') == 'verified_readback':
                recovered = True
                break
            time.sleep(0.2)
        elapsed = time.perf_counter() - recovery_start
        result = {'baseline_run': baseline, 'service': SERVICE,
                  'interruption_observed': all(s != 'verified_readback' for s in during),
                  'stopped_read_classifications': during,
                  'same_marker_recovered': recovered,
                  'first_verified_read_after_start_command_s': elapsed if recovered else None,
                  'claim_boundary': 'One stop/start feasibility check, no randomized control or gate comparison'}
        result['ledger_sha256'] = hashlib.sha256((out / 'ledger.jsonl').read_bytes()).hexdigest()
        (out / 'summary.json').write_text(json.dumps(result, indent=2))
        print(json.dumps({'output': str(out), **result}, indent=2))
        return 0 if recovered and result['interruption_observed'] else 2
    finally:
        if stop_attempted and not restarted:
            action('start')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline-run', required=True)
    raise SystemExit(main(parser.parse_args().baseline_run))
