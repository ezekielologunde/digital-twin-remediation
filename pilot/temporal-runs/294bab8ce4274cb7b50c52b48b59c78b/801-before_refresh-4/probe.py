"""Low-rate, independent transaction ledger for the LOCAL benchmark only.

HTTP success is not treated as verified persistence. No faults or repairs are injected.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone

def classify_read(status, body, marker, user_id):
    if status != 200:
        return 'unresolved_read_error'
    try:
        rows = json.loads(body)
    except (ValueError, TypeError):
        return 'unresolved_invalid_json'
    if rows == {}:  # Lua cjson may encode an empty table as an object.
        rows = []
    if not isinstance(rows, list):
        return 'unresolved_invalid_schema'
    for row in rows:
        if not isinstance(row, dict):
            return 'unresolved_invalid_schema'
        if row.get('text') == marker:
            creator = row.get('creator')
            if not isinstance(creator, dict):
                return 'unresolved_invalid_schema'
            if str(creator.get('user_id')) != str(user_id):
                return 'creator_mismatch'
            return 'verified_readback'
    return 'not_observed'

def request(base, path, data=None, timeout=5):
    start = time.perf_counter_ns()
    req = urllib.request.Request(base + path,
        data=urllib.parse.urlencode(data).encode() if data is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status, body = response.status, response.read(1_000_000).decode('utf-8')
        error = None
    except urllib.error.HTTPError as exc:
        status, body, error = exc.code, exc.read(1_000_000).decode('utf-8', errors='replace'), str(exc)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        status, body, error = None, '', str(exc)
    return {'utc': datetime.now(timezone.utc).isoformat(), 'path': path,
            'status': status, 'body': body, 'error': error,
            'elapsed_ms': (time.perf_counter_ns() - start) / 1_000_000}

def run(args):
    parsed = urllib.parse.urlsplit(args.base_url)
    if parsed.hostname not in ('127.0.0.1', 'localhost') or parsed.scheme != 'http':
        raise ValueError('This pilot probe only targets local HTTP')
    if not 1 <= args.transactions <= 100 or not 0 < args.horizon <= 30:
        raise ValueError('Pilot limits: 1-100 transactions, horizon <=30 seconds')
    run_id = uuid.uuid4().hex
    user_id = int(run_id[:10], 16)
    username = 'pilot_' + run_id[:12]
    out = Path(args.output) / run_id
    out.mkdir(parents=True, exist_ok=False)
    for artifact in ('image-lock.json', 'compose.locked.json'):
        source = Path(__file__).parent / artifact
        if source.exists():
            shutil.copyfile(source, out / artifact)
    shutil.copyfile(Path(__file__), out / 'probe-source.py')
    def log(row):
        with (out / 'ledger.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row) + '\n')
    register = request(args.base_url, '/wrk2-api/user/register', {
        'first_name': 'Synthetic', 'last_name': 'Pilot', 'username': username,
        'password': 'local-synthetic-account', 'user_id': user_id})
    log({'phase': 'register', **register})
    setup_ok = register['status'] == 200 and register['body'].strip() == 'Success!'
    if setup_ok:
        follower = request(args.base_url, '/wrk2-api/user/register', {
            'first_name': 'Synthetic', 'last_name': 'Follower', 'username': username + '_f',
            'password': 'local-synthetic-account', 'user_id': user_id + 1})
        log({'phase': 'register_follower', **follower})
        follow = request(args.base_url, '/wrk2-api/user/follow', {
            'user_id': user_id + 1, 'followee_id': user_id})
        log({'phase': 'follow', **follow})
        setup_ok = all(x['status'] == 200 and x['body'].strip() == 'Success!'
                       for x in (follower, follow))
    if not setup_ok:
        summary = {'status': 'SETUP_FAILED', 'run_id': run_id, 'transactions': 0,
                   'reason': 'Synthetic account/graph setup not acknowledged; no baseline claimed'}
    else:
        outcomes = []
        for i in range(args.transactions):
            time.sleep(0.1)
            marker = f'dtrem_{run_id}_{i}'
            write = request(args.base_url, '/wrk2-api/post/compose', {
                'user_id': user_id, 'username': username, 'post_type': 0, 'text': marker})
            log({'phase': 'compose', 'transaction': i, 'marker': marker, **write})
            acknowledged = write['status'] == 200 and write['body'].strip() == 'Successfully upload post'
            if not acknowledged:
                outcomes.append('write_not_acknowledged')
                continue
            deadline = time.monotonic() + args.horizon
            outcome = 'not_observed'
            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                read = request(args.base_url, '/wrk2-api/user-timeline/read?' +
                    urllib.parse.urlencode({'user_id': user_id, 'start': 0, 'stop': 100}),
                    timeout=min(5, remaining))
                outcome = classify_read(read['status'], read['body'], marker, user_id)
                log({'phase': 'readback', 'transaction': i, 'classification': outcome, **read})
                if outcome in ('verified_readback', 'creator_mismatch'):
                    break
                time.sleep(min(0.2, max(0, deadline - time.monotonic())))
            outcomes.append(outcome)
        counts = {name: outcomes.count(name) for name in sorted(set(outcomes))}
        summary = {'status': 'BASELINE_PROBE_COMPLETE', 'run_id': run_id,
                   'transactions': len(outcomes), 'outcomes': counts,
                   'all_readbacks_verified': all(x == 'verified_readback' for x in outcomes),
                   'claim_boundary': 'Single low-rate probe; no durability, authentication, recovery or gate-efficacy claim'}
    summary['ledger_sha256'] = hashlib.sha256((out / 'ledger.jsonl').read_bytes()).hexdigest()
    (out / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps({'output': str(out), **summary}, indent=2))
    return 0 if summary.get('all_readbacks_verified') else 2

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:18880')
    parser.add_argument('--transactions', type=int, default=10)
    parser.add_argument('--horizon', type=float, default=5)
    parser.add_argument('--output', default=str(Path(__file__).parent / 'runs'))
    raise SystemExit(run(parser.parse_args()))
