"""Fixed-coverage descriptive analysis, including exact random-thinning distribution."""
import hashlib
import json
import math
import sys
from pathlib import Path

POLICIES=('state_refresh','source_repair_refresh','source_repair_operational')

def thinning_distribution(n,errors,k):
    if k>n: return None
    return {str(e):math.comb(errors,e)*math.comb(n-errors,k-e)/math.comb(n,k)
            for e in range(max(0,k-(n-errors)),min(errors,k)+1)}

def analyze(batch_id):
    assert len(batch_id)==32 and all(c in '0123456789abcdef' for c in batch_id)
    batch=Path(__file__).resolve().parent/'dependency-runs'/batch_id
    plan=json.loads((batch/'plan.json').read_text())
    rows=json.loads((batch/'summary.json').read_text())
    assert len(rows)==len(plan['arms'])==12, 'Incomplete batch: retain evidence, do not score as complete'
    volumes=set()
    integrity=[]
    for r in rows:
        assert r['status']=='COMPLETE' and r['cleanup_returncode']==0
        out=batch/f"{r['seed']}-{r['backend_condition']}-{r['arm']}"
        raw=(out/'ledger.jsonl').read_bytes()
        assert hashlib.sha256(raw).hexdigest()==r['ledger_sha256']
        records=[json.loads(l) for l in raw.decode().splitlines()]
        seal=next(i for i,e in enumerate(records) if e['kind']=='predictions_sealed')
        assert seal<next(i for i,e in enumerate(records) if e['kind']=='outcome')
        pred=(out/'predictions-before-action.json').read_bytes()
        assert hashlib.sha256(pred).hexdigest()==records[seal]['sha256']
        assert json.loads(pred)['predictions']==r['predictions']
        current=set(r['volume_names'])
        assert current and not current & volumes
        volumes.update(current)
        assert r['fresh_volume_ids'] and r['empty_before_initialization']
        for filename in ('dependency_pilot.py','dependency_twin.py','validity_twin.py'):
            assert (out/filename).read_bytes()==(batch/filename).read_bytes()
        witness=json.loads((out/'dependency-audit'/'witness.json').read_text())
        assert hashlib.sha256((out/'dependency-audit'/'UserTimelineHandler.h').read_bytes()).hexdigest()==witness['source_sha256']
        assert (out/'dependency-audit'/'witness.json').read_bytes()==(batch/'dependency-audit'/'witness.json').read_bytes()
        integrity.append({'seed':r['seed'],'condition':r['backend_condition'],'verified':True})
    k=plan['matched_approval_count']
    def rank(r):
        key=f"{plan['selection_salt']}:{r['seed']}:{r['backend_condition']}"
        return hashlib.sha256(key.encode()).hexdigest()
    metrics=[]
    for policy in POLICIES:
        eligible=[r for r in rows if r['predictions'][policy]['decision']=='approve']
        errors=sum(not r['contract_met'] for r in eligible)
        chosen=sorted(eligible,key=rank)[:k] if len(eligible)>=k else []
        metrics.append({'policy':policy,'opportunities':len(rows),'eligible':len(eligible),
                        'eligible_false_approvals':errors,'fixed_k':k,
                        'matched_comparison_feasible':len(eligible)>=k,
                        'expected_false_approvals_uniform_thinning':k*errors/len(eligible) if len(eligible)>=k else None,
                        'false_approval_count_distribution':thinning_distribution(len(eligible),errors,k),
                        'fixed_rank_false_approvals':sum(not r['contract_met'] for r in chosen) if chosen else None,
                        'fixed_rank_selected':[{'seed':r['seed'],'condition':r['backend_condition']} for r in chosen]})
    report={'batch':batch_id,'recorded_arms':len(rows),'contract_met':sum(r['contract_met'] for r in rows),
            'integrity':integrity,'distinct_volume_ids':len(volumes),'metrics':metrics,
            'interpretation':'Exact thinning distribution is conditional on this cohort, not a confidence interval or population estimate.'}
    (batch/'analysis.json').write_text(json.dumps(report,indent=2))
    lines=['# Source-corroborated dependency diagnostic','',
        'Development experiment, 4 October 2026. Twelve new start-action outcomes across three seed blocks and four fault conditions. The source audit and analysis rules were fixed before this batch, after seeing the earlier diagnostic. This is not a confirmatory or blinded-discovery study.','',
        '| Seed | Additional fault | Recovery contract met | First verified read |',
        '|---|---|---|---|']
    for r in rows:
        t=r['first_verified_read_from_decision_s']
        lines.append(f"| {r['seed']} | {r['backend_condition']} | {r['contract_met']} | {str(round(t,3))+' s' if t is not None else 'Not observed'} |")
    lines+=['',
        'Every intervention starts the previously stopped timeline service. Additional faults are none (up), stopped storage (down), paused storage (paused), or stopped media service (unrelated_down). The recovery contract is the last two scheduled reads verified within eight seconds and no observed creator mismatch. Controls from the prior batch are not pooled as candidate-action outcomes.','',
        '| Policy | Eligible approvals | Incorrect among eligible | Matched approvals | Expected incorrect after uniform thinning | Incorrect in fixed-rank subset |',
        '|---|---|---|---|---|---|']
    for m in metrics:
        lines.append(f"| {m['policy']} | {m['eligible']} / 12 | {m['eligible_false_approvals']} | {k if m['matched_comparison_feasible'] else 'Infeasible'} | {m['expected_false_approvals_uniform_thinning']} | {m['fixed_rank_false_approvals']} |")
    lines+=['',
        'State refresh uses the deliberately masked graph and Running telemetry. Source repair adds only the source-corroborated timeline-to-storage edge. Operational repair additionally requires each dependency to be running, not paused and not restarting. These are explicit ablations; a benefit from pause detection must not be attributed to graph repair alone. All policies use the same pre-action refreshed snapshot.','',
        'Matched coverage is six approvals out of twelve opportunities. Uniform thinning selects six eligible actions without outcome labels; analysis.json contains its exact hypergeometric distribution. Its expected error count is an analytical expectation over subsets, not six additional live experiments. The fixed SHA256-ranked subset is a reproducible secondary realization. Neither is a population confidence interval. A policy with fewer than six eligible actions is marked infeasible, never forced to approve rejected actions.','',
        'Predictions were saved before actions, source/model snapshots matched, ledgers and prediction seals verified, and fresh storage identifiers were disjoint. Policies are shadow-scored on shared outcomes. No production gate was deployed; policy latency, collateral harm and security authorization were not evaluated.','',
        'The pinned source is a distinct evidence modality, not independent ground truth. It corroborates a runtime-observed edge, but the container binary is not proven to match that commit. Redis and conditional MongoDB dependencies remain outside the repaired service graph. The selected omission and pause-aware veto are motivated by earlier findings; this small experiment cannot establish novelty, general safety, random-missingness robustness or the interaction hypothesis.','',
        'Next research gate: validate binary/source provenance, expand operation-level dependency coverage, include running-but-unresponsive and network faults, randomize missing edges and delay levels, and freeze held-out scenarios before evaluation. Compare against functional health probes so the proposed method must outperform a practical simple baseline.']
    (batch/'Results.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':analyze(sys.argv[1])
