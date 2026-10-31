"""Pinned new baseline and shared read-only helpers; no inference at import."""
from pathlib import Path
from types import SimpleNamespace
import importlib.util,json,os,re,sys,subprocess
OUT=Path(__file__).resolve().parent
REPO=OUT.parents[2]
ROOT=REPO/'build-native-baseline'
REVISION='870aedd9e1ebe1c91f94da93b59af17729f6c5c0'
BASE=REPO/'reports/tobeo-20261030/qwen36-baseline-870aedd9'
BASE_SOURCE=ROOT/'src-main-870aedd9'
BASE_BUILD=ROOT/'build-main-870aedd9-cuda132-sm120'
SOURCE=ROOT/'src-job-submit-870aedd9'
BUILD=ROOT/'build-job-submit-870aedd9-cuda132-sm120'
sys.path.insert(0,str(BASE))
import run_pipeline as baseline
sys.path.insert(0,str(REPO/'reports/tobeo-20261030/qwen36-systems'))
from validate_baseline import audit_processes
legacy=baseline.host
digest,save,stamp=baseline.digest,baseline.save,baseline.stamp

def check_identity():
 s=json.loads((BASE/'summary.json').read_text(encoding='utf-8'));assert s['passed'] and s['revision']==REVISION
 baseline.identity()
 m=json.loads((BASE/'evidence-manifest.json').read_text(encoding='utf-8'));assert digest(BASE/'evidence-manifest.json')==s['manifest_sha256']
 assert all(digest(BASE/n)==h for n,h in m.items())
 assert all(digest(BASE_BUILD/n)==h for n,h in s['binaries'].items())
 return s

def compiler():
 home=Path(sys.executable).parent
 os.environ['PATH']=os.pathsep.join([str(home/'Scripts'),str(home/'Library/bin'),os.environ['PATH']])
 return baseline.old.helper('reports/tobeo-20261022/windows-native-baseline/build_native.py','compiler_submit_870').compiler_environment()

def arguments(arm):
 assert arm=='off'
 return list(baseline.ARGS)

def conflicts():
 return [p for p in audit_processes() if any(x in (p['name'] or '').lower() for x in ['nsys','ncu','nvcc','ninja']) or any(Path(a).name.lower().startswith('download') or Path(a).name.lower() in ['mtp_fetch.py','strata-pack.exe'] for a in p['cmdline'] or [])]

def bandwidth(directory,label):
 exe=REPO/'reports/tobeo-20261024/pcie-root-cause/transfer_probe.exe'
 r=subprocess.run([str(exe)],env=baseline.env(),capture_output=True,text=True,timeout=90)
 (directory/(label+'.log')).write_text(r.stdout+'\n'+r.stderr,encoding='utf-8')
 match=re.search(r'"test":"pinned_H2D"[^\n]*"event_GBps":([0-9.]+)',r.stdout)
 row={'exit_code':r.returncode,'h2d_GBps':float(match.group(1)) if match else None,'exe_sha256':digest(exe)}
 assert r.returncode==0 and row['h2d_GBps'] is not None and row['h2d_GBps']>=15,row
 return row

def environment():
 e=baseline.env();e['NSYS_NVTX_PROFILER_REGISTER_ONLY']='0';return e

new_harness=baseline.old.helper('build-native-baseline/src-main-870aedd9/tools/qwen35/q36_harness.py','harness_submit_870')
host=SimpleNamespace(REPO=REPO,BASE=BASE,CUDA=baseline.CUDA,MODEL=baseline.MODEL,NSYS=legacy.NSYS,CONFIG=legacy.CONFIG,
 FIXTURES=legacy.FIXTURES,api=legacy.api,protocol=legacy.protocol,Eng=new_harness.Eng,layout=legacy.layout,
 environment=environment,bandwidth=bandwidth,check_identity=check_identity)
