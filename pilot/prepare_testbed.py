"""Download the pinned upstream runtime inputs; never launch services."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'testbed' / 'DeathStarBench'
tree = json.loads((ROOT / 'data/DeathStarBench-tree.json').read_text())
prefixes = ['socialNetwork/config/', 'socialNetwork/nginx-web-server/',
            'socialNetwork/gen-lua/', 'socialNetwork/docker/openresty-thrift/lua-thrift/',
            'socialNetwork/media-frontend/']
exact = {'LICENSE', 'README.md', 'socialNetwork/README.md', 'socialNetwork/docker-compose.yml'}
selected = [x for x in tree['tree'] if x['type'] == 'blob' and
            (x['path'] in exact or any(x['path'].startswith(p) for p in prefixes))]

def fetch(item):
    if item['mode'] not in ('100644', '100755'):
        raise ValueError('Unexpected file mode: ' + item['path'])
    path = DEST / item['path']
    url = f"https://raw.githubusercontent.com/delimitrou/DeathStarBench/{tree['sha']}/{item['path']}"
    raw = path.read_bytes() if path.exists() else urllib.request.urlopen(url, timeout=30).read()
    blob_hash = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    if blob_hash != item['sha']:
        raise ValueError('Git blob hash mismatch: ' + item['path'])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {'path': item['path'], 'url': url, 'git_blob_sha1': blob_hash,
            'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}

if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=6) as pool:
        files = list(pool.map(fetch, selected))
    manifest = {'commit': tree['sha'], 'scope': 'runtime mount files, not a full source checkout',
                'files': files}
    (ROOT / 'pilot/upstream-manifest.json').write_text(json.dumps(manifest, indent=2))
    print(json.dumps({'verified_files': len(files), 'bytes': sum(x['bytes'] for x in files),
                      'destination': str(DEST)}, indent=2))
