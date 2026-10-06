"""Verify the pinned source and prepare a manually audited, scoped witness."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
source=HERE/'dependency-audit'/'UserTimelineHandler.h'
raw=source.read_bytes()
tree=json.loads((ROOT/'data'/'DeathStarBench-tree.json').read_text())
path='socialNetwork/src/UserTimelineService/UserTimelineHandler.h'
entry=next(e for e in tree['tree'] if e['path']==path)
blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
assert blob==entry['sha']
lines=raw.decode().splitlines()
calls=[i+1 for i,l in enumerate(lines) if 'post_client->ReadPosts(' in l]
assert len(calls)==1
witness={'source_commit':tree['sha'],'source_path':path,'source_git_blob':blob,
         'source_sha256':hashlib.sha256(raw).hexdigest(),
         'url':f"https://github.com/delimitrou/DeathStarBench/blob/{tree['sha']}/{path}",
         'read_posts_call_line':calls[0],
         'supported_edges':[['user-timeline-service','post-storage-service']],
         'method':'Manual operation-level source audit corroborating a runtime-observed edge, not automatic discovery or independent ground truth.',
         'scope':'Nonempty valid-range read-user-timeline; only the explicitly audited service edge is added.',
         'limitations':['Container binary provenance is not verified against this source commit.',
                        'Redis and conditional MongoDB calls exist; the witness is not a complete dependency model.',
                        'The audit is motivated by previously observed pilot errors, not a blinded discovery.']}
(HERE/'dependency-audit'/'witness.json').write_text(json.dumps(witness,indent=2))
print(json.dumps(witness,indent=2))
