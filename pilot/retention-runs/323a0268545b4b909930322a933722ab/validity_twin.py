"""Deterministic reachability/state baseline, not a learned or calibrated twin."""
def decide(edges, states, age_s, max_age_s=None):
    if max_age_s is not None and age_s > max_age_s:
        return {'decision':'abstain','reason':'stale_observation'}
    # Operation scope: read-user-timeline. Exclude unrelated nginx routes.
    required={'user-timeline-service'}
    pending=list(required)
    while pending:
        node=pending.pop()
        for source,target in edges:
            if source==node and target not in required:
                required.add(target);pending.append(target)
    after=dict(states)
    after['user-timeline-service']=True  # Candidate action: start this service.
    unknown=sorted(n for n in required if n not in after)
    unavailable=sorted(n for n in required if n in after and not after[n])
    if unknown:
        return {'decision':'abstain','reason':'unobserved_required_state','required':sorted(required),'unknown':unknown}
    return {'decision':'reject' if unavailable else 'approve',
            'reason':'required_dependency_down' if unavailable else 'required_nodes_predicted_running',
            'required':sorted(required),'unavailable':unavailable}

def compare_views(graph, old, fresh, revalidated):
    reference=[(x['source'],x['target']) for x in graph['edges']]
    selected=('user-timeline-service','post-storage-service')
    if selected not in reference:
        raise ValueError('Chosen diagnostic dependency absent from observed graph')
    masked=[e for e in reference if e!=selected]
    rows=[]
    for age_name,snapshot in [('fresh',fresh),('stale',old)]:
        for graph_name,edges in [('reference',reference),('masked',masked)]:
            rows.append({'view':age_name+'_'+graph_name,
                'observation_age_s':snapshot['age_s'],
                'baseline':decide(edges,snapshot['states'],snapshot['age_s']),
                'age_gate':decide(edges,snapshot['states'],snapshot['age_s'],max_age_s=1),
                'revalidation':decide(edges,revalidated['states'],revalidated['age_s'])})
    return rows
