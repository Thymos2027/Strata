"""Run existing upstream independent correctness oracles, restoring the daily model."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from build_candidate import OUT,BUILD,REVISION
BASE=OUT.parents[1]/'tobeo-20261022/qwen36-context-curve'
sys.path.insert(0,str(BASE));import run_curve as baseline


def main():
    if (OUT/'validation-summary.json').exists():raise RuntimeError('Validation evidence exists')
    build=json.loads((OUT/'build-summary.json').read_text())
    if not build.get('passed') or baseline.digest(BUILD/'strata-q36.exe')!=build['exe_sha256']:
        raise RuntimeError('Candidate build provenance failed')
    env=dict(os.environ)
    env['PATH']=os.pathsep.join([str(baseline.CUDA/'bin/x64'),str(baseline.CUDA/'bin'),str(BUILD),env.get('PATH','')])
    report={'revision':REVISION,'exe_sha256':build['exe_sha256'],'tests':[],'passed':False,
            'started_at':datetime.now(timezone(timedelta(hours=8))).isoformat(),
            'scope':'Existing upstream CUDA numeric tests and CPU model-layout test only; no HIP/SYCL or real-model long-context claim'}
    state={'health_before':baseline.request('/health')};unloaded=False
    try:
        state['unload']=baseline.request('/unload?wait=30',post=True)
        if state['unload'].get('status') not in ('unloaded','not loaded'):raise RuntimeError('Unload failed')
        unloaded=True
        with (OUT/'validation.log').open('w',encoding='utf-8') as log:
            for name in ['model_family_test','q36_attn_parity','q36_f16_parity']:
                command=[str(BUILD/(name+'.exe'))];started=time.monotonic()
                result=subprocess.run(command,env=env,capture_output=True,text=True,timeout=300)
                log.write(name+'\n'+result.stdout+'\n'+result.stderr+'\n');log.flush()
                report['tests'].append({'name':name,'command':command,'exit_code':result.returncode,
                                        'wall_s':time.monotonic()-started,'stdout':result.stdout,'stderr':result.stderr})
                print(name,result.returncode,result.stdout[-180:],flush=True)
                if result.returncode:raise RuntimeError('Oracle failed: '+name)
        report['passed']=True
    finally:
        previous=signal.signal(signal.SIGINT,signal.SIG_IGN)
        try:
            if unloaded and state['health_before'].get('loaded'):
                state['load']=baseline.request('/load',post=True);state['health_after']=baseline.request('/health')
                if not state['health_after'].get('loaded'):raise RuntimeError('Daily model restore failed')
        finally:
            report['finished_at']=datetime.now(timezone(timedelta(hours=8))).isoformat()
            (OUT/'validation-summary.json').write_text(json.dumps(report,indent=2))
            (OUT/'validation-service.json').write_text(json.dumps(state,indent=2))
            signal.signal(signal.SIGINT,previous)


if __name__=='__main__':main()
