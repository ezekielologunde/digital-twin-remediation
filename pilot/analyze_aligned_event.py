"""Audit immutable event inputs and shadow-policy outcomes."""
import argparse
import hashlib
import json
from pathlib import Path
from aligned_event_policy import decide

def validate_snapshot(row,folder):
    pred=json.loads((folder/'predictions-before-action.json').read_text())
    assert pred['event_inputs']==row['event_inputs'],'Event input changed after sealing'
    assert pred['evidence']==row['final_evidence'] and pred['predictions']==row['predictions']
    return pred

def analyze(batch):
    rows=json.loads((batch/'summary.json').read_text());plan=json.loads((batch/'plan.json').read_text())
    assert len(rows)==len(plan['arms'])==8
    assert [[r['seed'],r['backend_condition']] for r in rows]==plan['arms']
    volumes=set();details=[]
    for r in rows:
        folder=batch/f"{r['seed']}-{r['backend_condition']}"
        assert r==json.loads((folder/'summary.json').read_text())
        assert r['status']=='COMPLETE' and r['cleanup_returncode']==0
        assert r['fresh_volume_ids'] and r['empty_before_initialization'] and r['baseline_markers_verified']==3
        for name,key in [('ledger.jsonl','ledger_sha256'),('scenario.json','scenario_sha256'),('compose.json','compose_sha256')]:
            assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==r[key]
        for name in ('aligned_event_pilot.py','aligned_event_policy.py','race_probes.py','dependency_twin.py','validity_twin.py'):
            assert (folder/name).read_bytes()==(batch/name).read_bytes()
        ev=[json.loads(line) for line in (folder/'ledger.jsonl').read_text().splitlines()]
        seal=next(i for i,e in enumerate(ev) if e['kind']=='predictions_sealed')
        action=next(i for i,e in enumerate(ev) if e['kind']=='docker' and e['args']==['start',r['target_container_id']])
        assert seal<action and ev[action]['returncode']==0
        assert seal<next(i for i,e in enumerate(ev) if e['kind']=='outcome')
        raw=(folder/'predictions-before-action.json').read_bytes()
        assert hashlib.sha256(raw).hexdigest()==ev[seal]['sha256']
        pred=validate_snapshot(r,folder);x=r['event_inputs']
        expected_keys={'timeline_redis','timeline_mongo','post_storage'}
        assert set(r['final_evidence'])==set(x['late_evidence'])==expected_keys
        late_calls=[e for e in ev[:seal] if e['kind']=='docker' and e['args'][0]=='exec'][-3:]
        assert len(late_calls)==3
        for e,k in zip(late_calls,('timeline_redis','timeline_mongo','post_storage')):
            assert e['returncode']==x['late_evidence'][k]['returncode']
        queries=[(i,e) for i,e in enumerate(ev) if e['kind']=='docker' and e['args'][0]=='events']
        assert len(queries)==2 and queries[-1][0]<seal
        actual=[json.loads(line) for line in queries[-1][1]['stdout'].splitlines() if line.strip()]
        anchor=[json.loads(line) for line in queries[0][1]['stdout'].splitlines() if line.strip()]
        assert actual==x['events'] and max(int(e.get('timeNano',0)) for e in anchor)==x['cursor']
        computed,changes=decide(r['final_evidence'],x['events'],set(x['dependency_ids']),x['cursor'],x['running'],x['delayed_available_at'],x['decision_time'],x['late_evidence'])
        assert computed==r['predictions'] and changes==x['matched_changes']
        assert x['decision_time']<x['delayed_available_at']
        assert pred['timings']=={k:v for k,v in r['timings'].items() if k!='action_decision'}
        obs=r['outcome_observations']
        contract=len(obs)>=2 and all(o['classification']=='verified_readback' and o['elapsed_s']<=8 for o in obs[-2:]) and not any(o['classification']=='creator_mismatch' for o in obs)
        assert contract==r['contract_met']
        assert r['post_action_states']['user-timeline-redis']==(r['backend_condition']!='redis_stop')
        assert r['post_action_states']['user-timeline-mongodb']
        assert not volumes.intersection(r['volume_names']);volumes.update(r['volume_names'])
        details.append({'seed':r['seed'],'condition':r['backend_condition'],'decisions':r['predictions'],
            'contract_met':contract,'matched_events':[e['Action'] for e in changes],
            'late_probe_ms':1000*x['late_duration_s'],'event_query_ms':1000*x['query_duration_s']})
    metrics=[]
    for policy in plan['policies']:
        approved=[r for r in rows if r['predictions'][policy]['decision']=='approve']
        metrics.append({'policy':policy,'approvals':len(approved),'incorrect_approvals':sum(not r['contract_met'] for r in approved),
            'correct_approvals':sum(r['contract_met'] for r in approved),
            'unnecessary_abstentions':sum(r['contract_met'] and r['predictions'][policy]['decision']=='abstain' for r in rows)})
    result={'batch':batch.name,'live_trials':8,'integrity_verified':True,'distinct_volume_ids':len(volumes),'metrics':metrics,'details':details,
        'limits':'Actual daemon history, simulated channel delay/drop, shared outcomes and interventions, no reliable live event stream or natural loss estimate. Known post-verification faults, two account blocks, no deployed gate or held-out evaluation.'}
    (batch/'analysis.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    lines=['# Lifecycle-event invalidation results','','Development study, 5 October 2026. Eight fresh trials, one outcome per instance shared by six shadow policies. Functional rechecking was also performed after the fault, following the event query. Actual Docker lifecycle records were queried; ten-second withholding and silent dropping are simulated channel transformations.','',
        '| Policy | Approvals | Incorrect approvals | Correct approvals | Recoverable cases rejected |','|---|---:|---:|---:|---:|']
    for m in metrics:lines.append(f"| {m['policy']} | {m['approvals']} | {m['incorrect_approvals']} | {m['correct_approvals']} | {m['unnecessary_abstentions']} |")
    lines+=['','| Block | Condition | Matched lifecycle changes | Recovery contract | Query duration (ms) |','|---|---|---|---|---:|']
    for r in details:lines.append(f"| {r['seed']} | {r['condition']} | {', '.join(r['matched_events']) or 'none'} | {r['contract_met']} | {r['event_query_ms']:.1f} |")
    lines+=['','Query time is measured common overhead, not a policy-specific latency comparison. Docker history retains only the last 256 records; absence of a matching event does not certify completeness. Silent loss is not detectable merely from an empty event set. All changes precede observation; a later change could invalidate these decisions too.','',
        'The earlier eight-trial event-visibility batch lacked a post-fault functional-recheck baseline; it remains a development diagnostic and is not pooled here. An earlier two-arm batch was excluded because a list-name collision let subsequent ledger entries mutate the saved event inputs. Its raw files and deviation report are retained. This corrected batch verifies exact equality between sealed and final event inputs, replays decisions from the raw daemon-query receipts and audits prediction-before-action ordering.','',result['limits']]
    (batch/'Results.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('batch',type=Path)
    print(json.dumps(analyze(p.parse_args().batch),indent=2))
