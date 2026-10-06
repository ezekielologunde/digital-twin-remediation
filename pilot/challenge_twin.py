"""Frozen diagnostic policies; no scenario labels or action outcomes as inputs."""
from validity_twin import decide

def compare(graph, removed, snapshot, witness, functional_classification):
    original={(e['source'],e['target']) for e in graph['edges']}
    masked=set(map(tuple,removed))
    if not masked <= original:
        raise ValueError('Mask contains unknown edges')
    edges=sorted(original-masked)
    repaired=sorted(set(edges)|set(map(tuple,witness['supported_edges'])))
    return {
        'random_graph_state':decide(edges,snapshot['states'],snapshot['age_s']),
        'source_operational':decide(repaired,snapshot['operational_states'],snapshot['age_s']),
        'alternate_route_probe':{
            'decision':'approve' if functional_classification=='verified_readback' else 'abstain',
            'reason':functional_classification}}
