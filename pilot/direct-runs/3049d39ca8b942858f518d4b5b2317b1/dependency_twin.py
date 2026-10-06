"""Source-corroborated graph repair and operational-state ablation."""
from validity_twin import decide

def compare_views(graph, old, fresh, revalidated, witness):
    reference=[(e['source'],e['target']) for e in graph['edges']]
    supported=[tuple(e) for e in witness['supported_edges']]
    selected=('user-timeline-service','post-storage-service')
    if selected not in supported or selected not in reference:
        raise ValueError('Diagnostic edge lacks required corroboration')
    masked=[e for e in reference if e!=selected]
    repaired=sorted(set(masked+supported))
    return {
        'state_refresh':decide(masked,revalidated['states'],revalidated['age_s']),
        'source_repair_refresh':decide(repaired,revalidated['states'],revalidated['age_s']),
        'source_repair_operational':decide(repaired,revalidated['operational_states'],revalidated['age_s']),
        'stale_masked':decide(masked,old['states'],old['age_s']),
        'fresh_reference':decide(reference,fresh['states'],fresh['age_s'])}

def operational_states(items):
    # This is a stronger proxy, not a semantic health test.
    return {c['Config']['Labels']['com.docker.compose.service']:
            bool(c['State']['Running'] and not c['State']['Paused'] and not c['State']['Restarting'])
            for c in items}
