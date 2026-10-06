"""Frozen comparison of alternate-route and direct dependency witnesses."""
import hashlib
import json
import sys
from pathlib import Path
from analyze_dependency import thinning_distribution

POLICIES=('alternate_route','alternate_plus_redis','direct_dependencies')

def analyze(batch_id):
    assert len(batch_id)==32 and all(c in '0123456789abcdef' for c in batch_id)
    batch=Path(__file__).resolve().parent/'direct-runs'/batch_id
    plan=json.loads((batch/'plan.json').read_text())
    rows=json.loads((batch/'summary.json').read_text())
    assert len(rows)==len(plan['arms'])==18, 'Incomplete batch retained, not scored as a completed experiment'
    volumes=set()
    for r in rows:
        assert r['status']=='COMPLETE' and r['cleanup_returncode']==0
        out=batch/f"{r['seed']}-{r['backend_condition']}-{r['arm']}"
        raw=(out/'ledger.jsonl').read_bytes()
        assert hashlib.sha256(raw).hexdigest()==r['ledger_sha256']
        events=[json.loads(l) for l in raw.decode().splitlines()]
        sealed=next(i for i,e in enumerate(events) if e['kind']=='predictions_sealed')
        action=next(i for i,e in enumerate(events) if e['kind']=='docker' and e['args']==['start',r['target_container_id']])
        assert sealed<action and events[action]['returncode']==0
        assert sealed<next(i for i,e in enumerate(events) if e['kind']=='outcome')
        pred_raw=(out/'predictions-before-action.json').read_bytes()
        assert hashlib.sha256(pred_raw).hexdigest()==events[sealed]['sha256']
        pred=json.loads(pred_raw)
        assert pred['predictions']==r['predictions'] and pred['direct_probes']==r['direct_probes']
        s=pred['revalidated']['states'];condition=r['backend_condition']
        assert not s['user-timeline-service'] and s['post-storage-service']
        assert s['user-timeline-redis']==(condition!='timeline_redis_down')
        assert s['user-timeline-mongodb']==(condition not in ('timeline_mongo_down','mongo_down_short'))
        assert s['media-service']==(condition!='unrelated_down')
        assert r['post_action_states']['user-timeline-mongodb']==s['user-timeline-mongodb']
        assert r['post_action_states']['user-timeline-redis']==s['user-timeline-redis']
        scenario=json.loads((out/'scenario.json').read_text())
        assert scenario['read_stop']==(3 if condition=='mongo_down_short' else 100)
        assert r['functional_baseline_verified'] and all(p['verified'] for p in r['direct_baseline'].values())
        assert r['fresh_volume_ids'] and r['empty_before_initialization']
        current=set(r['volume_names']);assert current and not current & volumes;volumes.update(current)
        for name in ('direct_pilot.py','direct_probes.py','dependency_twin.py','validity_twin.py'):
            assert (out/name).read_bytes()==(batch/name).read_bytes()
        witness=json.loads((out/'dependency-audit'/'startup-witness.json').read_text())
        assert hashlib.sha256((out/'dependency-audit'/'UserTimelineService.cpp').read_bytes()).hexdigest()==witness['sha256']
    k=plan['matched_approval_count']
    def rank(r):
        return hashlib.sha256(f"{plan['selection_salt']}:{r['seed']}:{r['backend_condition']}".encode()).hexdigest()
    metrics=[]
    for policy in POLICIES:
        eligible=[r for r in rows if r['predictions'][policy]['decision']=='approve']
        errors=sum(not r['contract_met'] for r in eligible)
        selected=sorted(eligible,key=rank)[:k] if len(eligible)>=k else []
        metrics.append({'policy':policy,'eligible':len(eligible),'false_approvals':errors,'matched_k':k,
                        'matched_feasible':len(eligible)>=k,
                        'expected_false_approvals':k*errors/len(eligible) if len(eligible)>=k else None,
                        'thinning_distribution':thinning_distribution(len(eligible),errors,k),
                        'fixed_rank_false_approvals':sum(not r['contract_met'] for r in selected) if selected else None,
                        'selected':[{'seed':r['seed'],'condition':r['backend_condition']} for r in selected]})
    report={'batch':batch_id,'arms':18,'contract_met':sum(r['contract_met'] for r in rows),
            'integrity_verified':True,'distinct_volume_ids':len(volumes),'metrics':metrics,
            'boundary':'Hand-specified verification obligations; descriptive cohort comparison, not a novel method or general safety result.'}
    (batch/'analysis.json').write_text(json.dumps(report,indent=2))
    lines=['# Direct dependency verification results','',
        'Development experiment, 4 October 2026. Eighteen fresh start-action trials across three account-ID blocks and six conditions. Rules, source evidence and analysis were frozen before this batch, after prior diagnostics. All three policies share outcomes and the same probing interventions.','',
        '| Block | Additional condition | Alternate route | Redis | MongoDB | Post RPC | Recovery contract |',
        '|---|---|---|---|---|---|---|']
    for r in rows:
        d=r['direct_probes']
        lines.append(f"| {r['seed']} | {r['backend_condition']} | {r['functional_probe']['classification']=='verified_readback'} | {d['timeline_redis']['verified']} | {d['timeline_mongo']['verified']} | {d['post_storage']['verified']} | {r['contract_met']} |")
    lines+=['',
        'Every candidate starts the stopped timeline service. Up and unrelated_down are no-additional-fault and stopped-media conditions. Other conditions suspend storage PID 1, stop timeline Redis, stop timeline MongoDB with read range 0..100, or stop MongoDB with short read range 0..3. Each baseline has three verified posts. Recovery requires the last two scheduled target reads within eight seconds to verify content and creator, with no observed creator mismatch.','',
        '| Policy | Eligible approvals | Incorrect approvals | Expected incorrect at six approvals | Fixed-ranked subset incorrect |',
        '|---|---|---|---|---|']
    for m in metrics:
        lines.append(f"| {m['policy']} | {m['eligible']} / 18 | {m['false_approvals']} | {m['expected_false_approvals'] if m['matched_feasible'] else 'Infeasible'} | {m['fixed_rank_false_approvals']} |")
    lines+=['',
        'The equal-coverage budget is six of eighteen opportunities (33.3 percent), not the 50 percent budget of the previous twelve-trial cohort. Uniform thinning and its exact error-count distribution are conditional on this cohort. Fixed-ranked subsets are secondary. Policies with fewer than six eligible approvals are infeasible; none is forced to approve. Differences across cohorts cannot be interpreted as controlled effect sizes.',
        '',
        'The alternate-route policy verifies a known post through the follower home timeline. Its Redis extension additionally checks a known post ID in the target timeline Redis sorted set. The direct policy requires that Redis record, a MongoDB timeline record containing the known post ID, and a successful direct ReadPosts RPC returning the exact ID, content and author. Unverified results cause abstention. These are manually specified baselines, not an automatic dependency-discovery algorithm.',
        '',
        'Startup matters: the pinned UserTimelineService source retries MongoDB index creation before serving requests. A short cached read therefore does not by itself justify dropping the MongoDB obligation for a start action. Startup source hash was checked against the pinned repository tree, but source-to-binary correspondence remains unverified. The MongoDB read probe is not a test of index-write permissions or a full simulation of startup.',
        '',
        'Probes originate from existing peer containers on the project network, not the stopped target namespace. They read existing synthetic records and may warm caches or affect connections. Every trial receives all probes in the fixed order: alternate route, Redis, MongoDB, post RPC. Therefore no probe-versus-no-probe effect is isolated. The action horizon begins after probing; per-probe elapsed times, including Docker client startup for direct checks, are saved in summary.json. Those times are not a production verifier-overhead estimate.',
        '',
        'Ledger hashes, prediction seals, model snapshots, state manipulations, read ranges and fresh storage identifiers verified. Repeated account IDs are not diverse stochastic workloads. No collateral-safety result, staleness interaction, randomized missing-edge effect or statistically generalizable reliability claim follows. The previous setup failures adapting the Lua client are retained outside this experiment.',
        '',
        'Research decision: compare any future proposed verifier against this stronger direct baseline. Further evaluation must include credential or configuration faults, target-specific network views, probe staleness, workload changes and independent fault selection. A zero-error cohort would not establish completeness of these obligations or novelty of manually adding checks.']
    (batch/'Results.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':analyze(sys.argv[1])
