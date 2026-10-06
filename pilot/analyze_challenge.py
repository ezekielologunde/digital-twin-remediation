"""Frozen descriptive analysis of new-fault and random-edge-mask challenge."""
import hashlib
import json
import sys
from pathlib import Path
from analyze_dependency import thinning_distribution

POLICIES=('random_graph_state','source_operational','alternate_route_probe')

def analyze(batch_id):
    assert len(batch_id)==32 and all(c in '0123456789abcdef' for c in batch_id)
    batch=Path(__file__).resolve().parent/'challenge-runs'/batch_id
    plan=json.loads((batch/'plan.json').read_text())
    rows=json.loads((batch/'summary.json').read_text())
    assert len(rows)==len(plan['arms'])==12, 'Incomplete batch; preserve failures, do not claim full evaluation'
    volumes=set()
    critical_masks=0
    for r in rows:
        assert r['status']=='COMPLETE' and r['cleanup_returncode']==0
        out=batch/f"{r['seed']}-{r['backend_condition']}-{r['arm']}"
        raw=(out/'ledger.jsonl').read_bytes()
        assert hashlib.sha256(raw).hexdigest()==r['ledger_sha256']
        events=[json.loads(l) for l in raw.decode().splitlines()]
        sealed=next(i for i,e in enumerate(events) if e['kind']=='predictions_sealed')
        action=next(i for i,e in enumerate(events) if e['kind']=='docker' and e['args'][-2:]==['start','user-timeline-service'])
        assert sealed<action and events[action]['returncode']==0
        assert sealed<next(i for i,e in enumerate(events) if e['kind']=='outcome')
        pred_raw=(out/'predictions-before-action.json').read_bytes()
        assert hashlib.sha256(pred_raw).hexdigest()==events[sealed]['sha256']
        pred=json.loads(pred_raw)
        assert pred['predictions']==r['predictions']
        assert pred['functional_probe']==r['functional_probe']
        mask=json.loads((out/'edge-mask.json').read_text())
        assert mask==plan['edge_masks'][f"{r['seed']}-{r['backend_condition']}"]==pred['removed_edges']
        assert len(set(map(tuple,mask)))==3
        critical_masks+=['user-timeline-service','post-storage-service'] in mask
        assert not pred['revalidated']['states']['user-timeline-service']
        assert pred['revalidated']['states']['post-storage-service']
        assert pred['revalidated']['operational_states']['post-storage-service']
        assert pred['revalidated']['states']['user-timeline-redis']==(r['backend_condition']!='timeline_redis_down')
        assert r['functional_baseline_verified'] and r['empty_before_initialization'] and r['fresh_volume_ids']
        current=set(r['volume_names'])
        assert current and not current & volumes
        volumes.update(current)
        for filename in ('challenge_pilot.py','challenge_twin.py','dependency_twin.py','validity_twin.py'):
            assert (out/filename).read_bytes()==(batch/filename).read_bytes()
        witness=json.loads((out/'dependency-audit'/'witness.json').read_text())
        assert hashlib.sha256((out/'dependency-audit'/'UserTimelineHandler.h').read_bytes()).hexdigest()==witness['source_sha256']
    k=plan['matched_approval_count']
    def rank(r):
        return hashlib.sha256(f"{plan['selection_salt']}:{r['seed']}:{r['backend_condition']}".encode()).hexdigest()
    metrics=[]
    for policy in POLICIES:
        eligible=[r for r in rows if r['predictions'][policy]['decision']=='approve']
        errors=sum(not r['contract_met'] for r in eligible)
        chosen=sorted(eligible,key=rank)[:k] if len(eligible)>=k else []
        strata=[]
        for condition in sorted({r['backend_condition'] for r in rows}):
            group=[r for r in rows if r['backend_condition']==condition]
            approved=[r for r in group if r['predictions'][policy]['decision']=='approve']
            strata.append({'condition':condition,'opportunities':len(group),'approvals':len(approved),
                           'false_approvals':sum(not r['contract_met'] for r in approved)})
        metrics.append({'policy':policy,'eligible':len(eligible),'false_approvals':errors,
                        'matched_k':k,'matched_feasible':len(eligible)>=k,
                        'expected_false_approvals':k*errors/len(eligible) if len(eligible)>=k else None,
                        'thinning_distribution':thinning_distribution(len(eligible),errors,k),
                        'fixed_rank_false_approvals':sum(not r['contract_met'] for r in chosen) if chosen else None,
                        'selected':[{'seed':r['seed'],'condition':r['backend_condition']} for r in chosen],
                        'by_condition':strata})
    report={'batch':batch_id,'arms':len(rows),'contract_met':sum(r['contract_met'] for r in rows),
            'critical_edge_masked_trials':critical_masks,'distinct_volume_ids':len(volumes),
            'integrity_verified':True,'metrics':metrics,
            'interpretation':'New scenarios for this implementation, not an independently blinded or confirmatory held-out benchmark. Exact thinning conditional on this cohort.'}
    (batch/'analysis.json').write_text(json.dumps(report,indent=2))
    lines=['# Functional-probe and new-fault challenge','',
        'Development study, 4 October 2026. Twelve fresh start-action trials; three account-ID blocks and four fault conditions. Policies, masks, selection salt and analysis were saved before this batch. Faults were new to the previous live batches, but chosen with knowledge of baseline weaknesses. This is not an independently blinded evaluation.','',
        '| Block | Additional fault | Alternate-route probe | Probe time (ms) | Target recovery by contract |',
        '|---|---|---|---|---|']
    for r in rows:
        lines.append(f"| {r['seed']} | {r['backend_condition']} | {r['functional_probe']['classification']} | {r['functional_probe']['elapsed_ms']:.1f} | {r['contract_met']} |")
    lines+=['',
        'The target timeline service is stopped in every trial; the candidate action starts it. Additional conditions are none, SIGSTOP to storage PID 1, disconnection of storage from its project network, and stopped timeline Redis. Target recovery requires the last two scheduled reads to verify known content and creator within eight seconds, with no observed creator mismatch. A failed contract means no qualifying recovery within the horizon, not permanent data loss.','',
        '| Policy | Eligible approvals | Incorrect approvals | Expected incorrect at six approvals | Fixed-ranked subset incorrect |',
        '|---|---|---|---|---|']
    for m in metrics:
        lines.append(f"| {m['policy']} | {m['eligible']} / 12 | {m['false_approvals']} | {m['expected_false_approvals'] if m['matched_feasible'] else 'Infeasible'} | {m['fixed_rank_false_approvals']} |")
    lines+=['',
        'The primary matched comparison uniformly thins eligible actions to six approvals. Expected incorrect counts and exact subset distributions are conditional calculations on this cohort, not additional trials or population confidence intervals. Fixed SHA256-ranked selections are secondary. A policy with insufficient approvals is infeasible rather than forced to approve.','',
        '| Policy | Fault condition | Approved | Incorrect |',
        '|---|---|---|---|']
    for m in metrics:
        for g in m['by_condition']:
            lines.append(f"| {m['policy']} | {g['condition']} | {g['approvals']} / {g['opportunities']} | {g['false_approvals']} |")
    lines+=['',
        f"Three of thirteen observed edges were sampled without replacement in each trial (23.1 percent, not exactly 20 percent). The timeline-to-storage edge was removed in {critical_masks} of twelve trials. Masks were not resampled to force an effect. The observed graph omits datastore edges, so random masking cannot evaluate dependencies absent from the starting graph. One masked view per live outcome cannot isolate the causal contribution of masking versus the new fault mix.",
        '',
        'The functional comparator reads the follower home timeline and checks known post content and author through an alternate route, after verifying that route at baseline. It abstains on any unverified response. It does not directly test the stopped target or certify the entire target path. Source repair and Running/not-Paused/not-Restarting checks are the previous simple baseline. SIGSTOP process state and network attachment are manipulation checks, not inputs to that frozen policy.',
        '',
        'All trials execute the functional probe before action, including those shadow-scored for state policies. The probe can warm caches or alter connection state. Its request latency is reported, but the eight-second action horizon begins afterwards. No probe-versus-no-probe control, end-to-end workflow benefit, or production policy latency claim is available.',
        '',
        'Source/model snapshots, prediction seals, action receipts, mask records and ledgers verified; storage identifiers disjoint. Three account-ID blocks are repetitions of the same small workload, not diverse workload distributions. Policies share twelve action outcomes. No p-values, power claim, novelty claim or safety guarantee follows. Source-to-binary correspondence remains unverified, and no collateral-harm contract is evaluated.',
        '',
        'Next decision: use these counterexamples to define operation-specific verification obligations, then benchmark any proposed verifier against stronger direct dependency probes under independent fault selection and workload shifts. A publishable contribution must go beyond adding checks for the faults already seen.']
    (batch/'Results.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':analyze(sys.argv[1])
