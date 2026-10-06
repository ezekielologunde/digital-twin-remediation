"""Resolve already-pulled image references to immutable digests before measurement."""
from pathlib import Path
from datetime import datetime, timezone
import json
import subprocess

HERE = Path(__file__).resolve().parent
if __name__ == '__main__':
    config = json.loads((HERE / 'compose.pilot.json').read_text())
    images = {}
    for reference in sorted({s['image'] for s in config['services'].values()}):
        info = json.loads(subprocess.check_output(['docker', 'image', 'inspect', reference], text=True))[0]
        digests = info.get('RepoDigests', [])
        if len(digests) != 1:
            raise RuntimeError(f'Review ambiguous/missing digest for {reference}: {digests}')
        if info['Os'] != 'linux' or info['Architecture'] != 'amd64':
            raise RuntimeError('Unexpected image platform: ' + reference)
        images[reference] = {'digest': digests[0], 'image_id': info['Id'],
                             'platform': info['Os'] + '/' + info['Architecture']}
    for service in config['services'].values():
        service['image'] = images[service['image']]['digest']
    (HERE / 'compose.locked.json').write_text(json.dumps(config, indent=2))
    manifest = {'locked_utc': datetime.now(timezone.utc).isoformat(), 'images': images}
    (HERE / 'image-lock.json').write_text(json.dumps(manifest, indent=2))
    audit_path = HERE / 'configuration-audit.json'
    if audit_path.exists():
        audit = json.loads(audit_path.read_text())
        audit['image_digest_lock'] = 'RESOLVED: image-lock.json and compose.locked.json'
        audit_path.write_text(json.dumps(audit, indent=2))
    print(json.dumps(manifest, indent=2))
