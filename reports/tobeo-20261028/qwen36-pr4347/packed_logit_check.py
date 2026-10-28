"""Same binary, same 63 resident slots, same forced history: packed on/off logits."""
import json
import os
from pathlib import Path
import subprocess
import sys
import numpy as np
from build_pair import ARMS,MODEL,OUT,REPO,ROOT,stamp
BASE=REPO/'reports/tobeo-20261022/qwen36-context-curve'
sys.path.insert(0,str(BASE))
import run_curve as protocol
DIR=OUT/'packed-logits-01';DIR.mkdir(exist_ok=False)
prior=json.loads((OUT/'execution-02/results.json').read_text())
ids=json.loads((BASE/'r0-l1024.ids.json').read_text())
forced=next(r for r in prior['rows'] if r.get('pair')==0 and r['case']=='r0-l1024' and r['keep_packed'])['output_ids'][:96]
report={'started':stamp(),'passed':False,'rows':97,'vocab':248320,'fixed_slots':63,
        'source':ARMS['main']['revision'],'forced_ids':forced,'runs':[]}
def save():(DIR/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
state={'health_before':protocol.request('/health')};unloaded=False;save()
try:
    state['unload']=protocol.request('/unload?wait=30',post=True)
    if state['unload'].get('status') not in ('unloaded','not loaded'):raise RuntimeError('Daily engine busy')
    unloaded=True
    for packed in ['1','0']:
        print('Full logits fixed63 packed='+packed,flush=True)
        env={k:v for k,v in os.environ.items() if not k.startswith('STRATA_')}
        env.update(STRATA_Q36_FIXED_SLOTS='1',STRATA_MMQ_KQ='1',STRATA_Q8_PACKED=packed,
                   CUDA_MODULE_LOADING='EAGER',CUDA_VISIBLE_DEVICES='0')
        cuda=ROOT/'toolchains/cuda-13.2.0'
        env['PATH']=os.pathsep.join([str(cuda/'bin/x64'),str(cuda/'bin'),str(ARMS['main']['build']),env.get('PATH','')])
        command=[str(ARMS['main']['build']/'strata-q36.exe'),'--native',str(MODEL),
                 '--max-context','32768','--prefill','2048','--pool-workers','7','--mtp','0',
                 '--expert-slots','63','--expert-vram','10','--tokens',','.join(map(str,ids)),
                 '--force',','.join(map(str,forced)),'--dump-full-logits',str(DIR/(packed+'.f32'))]
        with (DIR/(packed+'.log')).open('w',encoding='utf-8') as log:
            p=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT)
            try:code=p.wait(timeout=900)
            except BaseException:p.kill();p.wait();raise
        size=(DIR/(packed+'.f32')).stat().st_size
        report['runs'].append({'packed':packed,'exit_code':code,'bytes':size});save()
        if code or size!=97*248320*4:raise RuntimeError('Full logits run failed or dimensions wrong')
    x=np.memmap(DIR/'1.f32',dtype=np.float32,mode='r').reshape(97,248320)
    y=np.memmap(DIR/'0.f32',dtype=np.float32,mode='r').reshape(97,248320)
    report['bitwise_identical']=bool(np.array_equal(x.view(np.uint32),y.view(np.uint32)))
    report['finite']=bool(np.isfinite(x).all() and np.isfinite(y).all())
    report['max_absolute_error']=float(np.max(np.abs(x-y)))
    report['top1_equal']=int(np.sum(np.argmax(x,axis=1)==np.argmax(y,axis=1)))
    report['passed']=report['bitwise_identical'] and report['finite']
except BaseException as exc:report['error']=repr(exc);save();raise
finally:
    try:
        if unloaded and state['health_before'].get('loaded'):
            state['load']=protocol.request('/load',post=True);state['health_after']=protocol.request('/health')
            if not state['health_after'].get('loaded'):raise RuntimeError('Daily model did not restore')
    except BaseException as exc:state['restore_error']=repr(exc);report['passed']=False;raise
    finally:report['service_transition']=state;report['finished']=stamp();save()
