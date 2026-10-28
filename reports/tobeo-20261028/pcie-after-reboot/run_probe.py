"""Re-run the exact October 24 executable, without rebuilding or changing settings."""
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT))
from serve.telemetry import _Nvml

exe = ROOT / 'reports/tobeo-20261024/pcie-root-cause/transfer_probe.exe'
nv = _Nvml()
samples = []
started = datetime.now(timezone(timedelta(hours=8))).isoformat()
with (OUT / 'transfer.log').open('w') as log:
    p = subprocess.Popen([str(exe)], stdout=log, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 60
    try:
        while p.poll() is None:
            if time.monotonic() > deadline:
                raise TimeoutError('Probe exceeded 60 seconds')
            samples.append({'time': datetime.now(timezone(timedelta(hours=8))).isoformat(),
                            'nvml': nv.read() if nv.ok() else None})
            time.sleep(.025)
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()
result = {'started_at': started, 'exe': str(exe),
          'exe_sha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
          'exit_code': p.returncode, 'samples': samples,
          'output': (OUT / 'transfer.log').read_text(), 'settings_changed': False}
(OUT / 'transfer-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(result['output'])
print('exit_code', p.returncode)
print('sampled_generations', sorted({x['nvml'].get('pcie_gen') for x in samples if x['nvml']}))
sys.exit(p.returncode)
