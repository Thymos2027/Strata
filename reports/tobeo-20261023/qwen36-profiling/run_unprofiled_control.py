"""Same-day no-profiler control before interpreting the CPU profiling slowdown."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import signal
import sys

OUT=Path(__file__).resolve().parent
BASE=OUT.parents[1]/'tobeo-20261022/qwen36-context-curve'
sys.path.insert(0,str(BASE));import run_curve as baseline
sys.path.insert(0,str(baseline.SOURCE/'tools/qwen35'));from q36_harness import Eng


def main():
    directory=OUT/'unprofiled-control-01'
    if directory.exists():raise RuntimeError('Existing evidence')
    if baseline.digest(baseline.EXE)!=baseline.EXPECTED_EXE:raise RuntimeError('Binary changed')
    directory.mkdir()
    env={k:v for k,v in os.environ.items() if not k.startswith('STRATA_')};env.update(baseline.ENV)
    env['PATH']=os.pathsep.join([str(baseline.CUDA/'bin/x64'),str(baseline.CUDA/'bin'),str(baseline.BUILD),env.get('PATH','')])
    state={'started_at':datetime.now(timezone(timedelta(hours=8))).isoformat(),'health_before':baseline.request('/health')}
    engine=None;unloaded=False;result={'profiler':False,'exe_sha256':baseline.EXPECTED_EXE,'rows':[]}
    try:
        state['unload']=baseline.request('/unload?wait=30',post=True)
        if state['unload'].get('status') not in ('unloaded','not loaded'):raise RuntimeError('Unload failed')
        unloaded=True
        engine=Eng(str(baseline.EXE),['--native',str(baseline.MODEL),'--max-context','32768','--prefill','512',
                   '--pool-workers','7','--expert-vram','10.0','--expert-slots','64','--mtp','0'],env=env,log=str(directory/'engine.log'))
        for case in ['r1-l1024','r0-l1024']:
            ids=json.loads((BASE/(case+'.ids.json')).read_text());row=baseline.measured_request(engine,ids,cap=64)
            row['case']=case;result['rows'].append(row)
            print(case,'prompt_ms',row['prompt_ms'],'decode_tok_s',row['decode_tok_s'],flush=True)
        reference=json.loads((BASE/'results.json').read_text())['rows']
        ref=next(r for r in reference if r['case']=='r0-l1024' and r['mtp']==0)
        result['validation_passed']=result['rows'][-1]['output_ids']==ref['output_ids'][:64]
    finally:
        previous=signal.signal(signal.SIGINT,signal.SIG_IGN)
        try:
            if engine:engine.close()
            if unloaded and state['health_before'].get('loaded'):
                state['load']=baseline.request('/load',post=True);state['health_after']=baseline.request('/health')
        finally:
            state['finished_at']=datetime.now(timezone(timedelta(hours=8))).isoformat()
            (directory/'results.json').write_text(json.dumps(result,indent=2))
            (directory/'service-transition.json').write_text(json.dumps(state,indent=2))
            signal.signal(signal.SIGINT,previous)


if __name__=='__main__':main()
