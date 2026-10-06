"""Create a scoped feasibility configuration from Compose's normalized upstream file."""
from pathlib import Path
import json
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
UPSTREAM = ROOT / 'testbed/DeathStarBench/socialNetwork/docker-compose.yml'

def build():
    result = subprocess.run(['docker', 'compose', '-f', str(UPSTREAM), 'config', '--format', 'json'],
                            capture_output=True, text=True, check=True)
    config = json.loads(result.stdout)
    config['name'] = 'dtrem-pilot'
    for name, service in config['services'].items():
        service.pop('ports', None)
        service['restart'] = 'no'
        service['cpus'] = 1.0
        service['mem_limit'] = '512m'
        service['labels'] = {'research.project': 'digital-twin-remediation',
                             'research.stage': 'feasibility-not-confirmatory'}
        for mount in service.get('volumes', []):
            if mount['type'] != 'bind':
                raise ValueError('Review non-bind mount before launch')
            path = Path(mount['source']).resolve()
            if not path.is_relative_to(ROOT / 'testbed') or not path.exists():
                raise ValueError('Missing or out-of-scope mount: ' + str(path))
            mount['read_only'] = True
            mount.pop('bind', None)
    config['services']['nginx-thrift']['ports'] = [
        {'target': 8080, 'published': '18880', 'host_ip': '127.0.0.1', 'protocol': 'tcp'}]
    config['services']['jaeger-agent']['ports'] = [
        {'target': 16686, 'published': '18686', 'host_ip': '127.0.0.1', 'protocol': 'tcp'}]
    # Legacy benchmark clients send compact Thrift over UDP/6831.
    # The first pulled latest image exposed no matching UDP listener.
    config['services']['jaeger-agent']['image'] = 'jaegertracing/all-in-one:1.54.0'
    config['networks'] = {'default': {'name': 'dtrem-pilot-net', 'internal': True},
                          'ingress': {'name': 'dtrem-pilot-ingress'}}
    # Docker does not publish ports on an internal-only network in this runtime.
    # Only the two localhost-facing gateways join the additional bridge.
    for name in ('nginx-thrift', 'jaeger-agent'):
        config['services'][name]['networks'] = {'default': None, 'ingress': None}
    (HERE / 'compose.pilot.json').write_text(json.dumps(config, indent=2))
    report = {'stage': 'configuration-only', 'services': len(config['services']),
              'images': sorted({s['image'] for s in config['services'].values()}),
              'ports': ['127.0.0.1:18880', '127.0.0.1:18686'],
              'resource_caps': '1 CPU and 512 MiB per service; pilot setting, not upstream default',
              'image_digest_lock': 'PENDING: resolve and record before any measurement',
              'call_graph': 'PENDING: Compose depends_on is not the service call graph'}
    (HERE / 'configuration-audit.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    build()
