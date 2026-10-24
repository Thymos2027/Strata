"""Build a bounded directional copy probe and sample NVML during it."""
import importlib.util
import json
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
sys.path.insert(0,str(ROOT))
from serve.telemetry import _Nvml
spec=importlib.util.spec_from_file_location('build',ROOT/'reports/tobeo-20261022/windows-native-baseline/build_native.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
env,_,_=helper.compiler_environment()
exe=OUT/'transfer_probe.exe'
with (OUT/'build.log').open('w') as log:
 subprocess.run([str(helper.CUDA/'bin/nvcc.exe'),'-O2','-arch=sm_120','--cudart=static',str(OUT/'transfer_probe.cu'),'-o',str(exe)],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
nv=_Nvml(); samples=[]
start=datetime.now(timezone(timedelta(hours=8))).isoformat()
with (OUT/'transfer.log').open('w') as log:
 p=subprocess.Popen([str(exe)],env=env,stdout=log,stderr=subprocess.STDOUT)
 deadline=time.monotonic()+60
 try:
  while p.poll() is None:
   if time.monotonic()>deadline:raise TimeoutError('copy diagnostic exceeded 60s')
   samples.append({'time':datetime.now(timezone(timedelta(hours=8))).isoformat(),'nvml':nv.read() if nv.ok() else None})
   time.sleep(.25)
 finally:
  if p.poll() is None:p.kill();p.wait()
result={'started_at':start,'exit_code':p.returncode,'samples':samples,'output':(OUT/'transfer.log').read_text(),'model_unloaded':True,'settings_changed':False}
(OUT/'transfer-result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(result['output']);print('exit_code',p.returncode)
if p.returncode:sys.exit(p.returncode)
