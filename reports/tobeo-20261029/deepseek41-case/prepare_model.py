"""Verify the pinned download and apply setup.py's unmodified IST-DAS pack recipe."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
source = ROOT / 'reports/tobeo-20261028/deepseek41-community/download-manifest.json'
manifest = json.loads(source.read_text(encoding='utf-8'))
checks = []
for f in manifest['files']:
    p = Path(f['destination'])
    t = time.monotonic()
    with p.open('rb') as h:
        sha = hashlib.file_digest(h, 'sha256').hexdigest()
    checks.append({'path': str(p), 'size': p.stat().st_size, 'mtime_ns': p.stat().st_mtime_ns,
                   'sha256': sha, 'passed': sha == f['sha256'] and p.stat().st_size == f['size'],
                   'seconds': time.monotonic() - t})
    (OUT / 'model-verification.json').write_text(json.dumps(checks, indent=2))
    print(p.name, checks[-1]['passed'], flush=True)
    assert checks[-1]['passed']
spec = importlib.util.spec_from_file_location('case_setup', ROOT / 'setup.py')
S = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = S
spec.loader.exec_module(S)
files = manifest['files']
folder = Path(files[2]['destination']).parent
pack = folder / 'maya-ds4'
assert not pack.exists(), 'Retain and inspect an existing pack; do not overwrite'
cmd = S.dsv41_pack_cmd(folder, [f['name'] for f in files[2:6]], Path(files[6]['destination']),
                        Path(files[0]['destination']), Path(files[1]['destination']), pack)
(OUT / 'pack-command.json').write_text(json.dumps(cmd, indent=2))
subprocess.run(cmd, check=True, cwd=ROOT)
shutil.copyfile(ROOT / 'data/dsv41/profile-2.25.bin', pack / 'expert-profile.bin')
checks = []
for p in sorted(pack.rglob('*')):
    if p.is_file():
        checks.append({'path': str(p), 'size': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
(OUT / 'pack-files.json').write_text(json.dumps(checks, indent=2))
print('PACK READY', pack, flush=True)
