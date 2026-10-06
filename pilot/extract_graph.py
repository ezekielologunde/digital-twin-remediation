"""Export observed cross-service parent/child edges; never assert completeness."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import urllib.parse
import urllib.request

HERE = Path(__file__).resolve().parent
if __name__ == '__main__':
    url = 'http://127.0.0.1:18686/api/traces?' + urllib.parse.urlencode({
        'service': 'nginx-web-server', 'limit': 100, 'lookback': '1h'})
    raw = urllib.request.urlopen(url, timeout=10).read()
    (HERE / 'trace-snapshot.json').write_bytes(raw)
    data = json.loads(raw)
    if data.get('errors'):
        raise RuntimeError(data['errors'])
    traces = data.get('data') or []
    edges = Counter()
    nodes = set()
    missing_parents = 0
    for trace in traces:
        spans = {s['spanID']: s for s in trace['spans']}
        processes = trace['processes']
        for span in spans.values():
            child = processes[span['processID']]['serviceName']
            nodes.add(child)
            for ref in span.get('references', []):
                if ref['refType'] != 'CHILD_OF':
                    continue
                parent = spans.get(ref['spanID'])
                if parent is None:
                    missing_parents += 1
                    continue
                source = processes[parent['processID']]['serviceName']
                if source != child:
                    edges[source, child] += 1
    report = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'query_url': url,
              'trace_count': len(traces), 'nodes': sorted(nodes),
              'edges': [{'source': s, 'target': t, 'observed_parent_links': n}
                        for (s, t), n in sorted(edges.items())],
              'missing_parent_references': missing_parents,
              'source_sha256': hashlib.sha256(raw).hexdigest(),
              'complete_graph': False,
              'limitations': 'Sampled traces and a capped query over a limited workload; absent edges are not disproven. Datastore dependencies may be uninstrumented.'}
    (HERE / 'observed-call-graph.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != 'edges'}, indent=2))
    print('Observed edges:', len(edges))
