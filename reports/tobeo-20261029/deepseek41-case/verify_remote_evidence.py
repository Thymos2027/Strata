"""Read every published Git blob and compare it with the reviewed local package."""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess

OUT=Path(__file__).resolve().parent
publication=json.loads((OUT/'evidence-publication.json').read_text())
repo=publication['repository'];commit=publication['commit']


def api(path):
    return json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/{path}']))


tree=api(f'git/trees/{publication["tree"]}?recursive=1')
assert not tree.get('truncated')
actual={x['path']:x['sha'] for x in tree['tree'] if x['type']=='blob' and x['path'].startswith(publication['directory']+'/')}
expected={x['path']:x['git_blob_sha'] for x in publication['files']}
assert actual==expected


def verify(file):
    blob=api('git/blobs/'+file['git_blob_sha'])
    data=base64.b64decode(blob['content'])
    assert len(data)==file['bytes'] and hashlib.sha256(data).hexdigest()==file['sha256'],file['path']
    return {'path':file['path'],'bytes':len(data),'sha256':file['sha256'],'passed':True}


with ThreadPoolExecutor(max_workers=3) as pool:
    files=list(pool.map(verify,publication['files']))
result={'passed':True,'repository':repo,'commit':commit,'directory':publication['directory'],
        'files':files,'file_count':len(files),'total_bytes':sum(f['bytes'] for f in files)}
(OUT/'remote-evidence-verification.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:result[k] for k in ['passed','commit','file_count','total_bytes']}))
