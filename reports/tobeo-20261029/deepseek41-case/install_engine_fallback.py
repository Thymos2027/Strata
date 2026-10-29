"""Curl transport fallback; signed package verification remains mandatory."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path.cwd()))
from strata_control import dsv41_engine, engine_component as ec
OUT = Path(__file__).resolve().parent
pkg = json.loads((OUT / 'selected-package.json').read_text())
archive = OUT / pkg['url']
cmd = ['curl.exe', '-L', '--fail', '--retry', '12', '--retry-all-errors', '--retry-delay', '5',
       '--connect-timeout', '20', '--max-time', '1800', '--speed-time', '60', '--speed-limit', '4096',
       '-C', '-', '-o', str(archive), 'https://github.com/Niko1221/Strata/releases/latest/download/' + pkg['url']]
subprocess.run(cmd, check=True)
with archive.open('rb') as f:
    sha = hashlib.file_digest(f, 'sha256').hexdigest()
assert archive.stat().st_size == pkg['size'] and sha == pkg['sha256']
exe = dsv41_engine.install_package(Path('D:/Models/Strata/engine-dsv41'), archive)
assert exe
assert hashlib.sha256((exe.parent / ec.MANIFEST).read_bytes()).hexdigest() == pkg['manifest_sha256']
result = {'exe': str(exe), 'sha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
          'archive_sha256': sha, 'build': json.loads((exe.parent / 'BUILD.json').read_text()),
          'signed_package_and_all_files_verified': True, 'manifest_matches_signed_feed': True}
(OUT / 'engine.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2), flush=True)
