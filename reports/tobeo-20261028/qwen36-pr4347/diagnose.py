"""Separate packed-layout math from changed CPU/GPU expert residency. Not a speed test."""
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
sys.path.insert(0,str(ARMS['main']['source']/'tools/qwen35'))
from q36_harness import Eng
DIR=OUT/'diagnosis-01'
DIR.mkdir(exist_ok=False)
prior=json.loads((OUT/'execution-02/results.json').read_text())
report={'started':stamp(),'passed':False,'purpose':'numerical diagnosis, no speed comparison',
        'source_changes':False,'fixed_layout':{},'teacher_forced':{},'history_divergence':[]}
for case in ['r0-l1024','r0-l16384']:
    rows={r['keep_packed']:r for r in prior['rows'] if r.get('pair')==0 and r['case']==case}
    k,d=rows[True]['output_ids'],rows[False]['output_ids']
    report['history_divergence'].append({'case':case,'first_different_index':next(i for i,(x,y) in enumerate(zip(k,d)) if x!=y)})

def save():
    (DIR/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')

def environment(name,packed='1',keep=False):
    env={k:v for k,v in os.environ.items() if not k.startswith('STRATA_')}
    env.update(STRATA_MMQ_KQ='1',STRATA_Q8_PACKED=packed,STRATA_Q36_FIXED_SLOTS='1',
               CUDA_VISIBLE_DEVICES='0',CUDA_MODULE_LOADING='EAGER')
    if keep:env['STRATA_Q36_KEEP_PACKED']='1'
    cuda=ROOT/'toolchains/cuda-13.2.0'
    env['PATH']=os.pathsep.join([str(cuda/'bin/x64'),str(cuda/'bin'),str(ARMS[name]['build']),env.get('PATH','')])
    return env

state={'health_before':protocol.request('/health')};unloaded=False
save()
try:
    state['unload']=protocol.request('/unload?wait=30',post=True)
    if state['unload'].get('status') not in ('unloaded','not loaded'):raise RuntimeError('Daily engine busy')
    unloaded=True
    args=['--native',str(MODEL),'--max-context','32768','--prefill','2048','--pool-workers','7','--mtp','0',
          '--expert-slots','63','--expert-vram','10']
    warm=json.loads((BASE/'r1-l1024.ids.json').read_text())
    for packed in ['1','0']:
        print('Fixed63 packed='+packed,flush=True)
        engine=None;rows={};report['fixed_layout'][packed]=rows
        try:
            engine=Eng(str(ARMS['main']['build']/'strata-q36.exe'),args,env=environment('main',packed),log=str(DIR/f'fixed63-packed{packed}.log'))
            protocol.measured_request(engine,warm,64)
            for case in ['r0-l1024','r0-l16384']:
                ids=json.loads((BASE/(case+'.ids.json')).read_text())
                rows[case]=protocol.measured_request(engine,ids,256)
                save()
        finally:
            if engine:engine.close()
    report['fixed_packed_identity']={case:report['fixed_layout']['1'][case]['output_ids']==report['fixed_layout']['0'][case]['output_ids']
                                     for case in ['r0-l1024','r0-l16384']}
    save()
    ids=json.loads((BASE/'r0-l1024.ids.json').read_text())
    reference=next(r for r in prior['rows'] if r.get('pair')==0 and r['case']=='r0-l1024' and r['keep_packed'])['output_ids'][:96]
    cli=['--native',str(MODEL),'--max-context','32768','--prefill','2048','--pool-workers','7','--mtp','0',
         '--tokens',','.join(map(str,ids)),'--force',','.join(map(str,reference))]
    for keep in [True,False]:
        name='keep' if keep else 'drop';print('Teacher-forced '+name,flush=True)
        command=[str(ARMS['pr4347']['build']/'strata-q36.exe'),*cli,'--dump-full-logits',str(DIR/(name+'.f32'))]
        with (DIR/(name+'.log')).open('w',encoding='utf-8') as log:
            p=subprocess.Popen(command,env=environment('pr4347',keep=keep),stdout=log,stderr=subprocess.STDOUT)
            try:code=p.wait(timeout=900)
            except BaseException:p.kill();p.wait();raise
        if code:raise RuntimeError('Teacher-forced engine failed')
        size=(DIR/(name+'.f32')).stat().st_size
        report['teacher_forced'][name]={'exit_code':code,'rows':len(reference)+1,'bytes':size}
        if size!=(len(reference)+1)*248320*4:raise RuntimeError('Unexpected full logits dimensions')
        save()
    p=np.memmap(DIR/'keep.f32',dtype=np.float32,mode='r').reshape(-1,248320)
    q=np.memmap(DIR/'drop.f32',dtype=np.float32,mode='r').reshape(-1,248320)
    kl=[];max_abs=[];sq=[];top=[];finite=True
    for start in range(0,len(p),8):
        x=np.array(p[start:start+8],dtype=np.float64);y=np.array(q[start:start+8],dtype=np.float64)
        finite=finite and bool(np.isfinite(x).all() and np.isfinite(y).all())
        diff=x-y;max_abs.extend(np.max(np.abs(diff),axis=1).tolist());sq.extend(np.mean(diff*diff,axis=1).tolist())
        top.extend((np.argmax(x,axis=1)==np.argmax(y,axis=1)).tolist())
        lp=x-np.max(x,axis=1,keepdims=True);lp-=np.log(np.exp(lp).sum(axis=1,keepdims=True))
        lq=y-np.max(y,axis=1,keepdims=True);lq-=np.log(np.exp(lq).sum(axis=1,keepdims=True))
        kl.extend(np.sum(np.exp(lp)*(lp-lq),axis=1).tolist())
    report['teacher_forced_metrics']={'rows':len(p),'finite':finite,'top1_equal':sum(top),
        'mean_kl_keep_to_drop':float(np.mean(kl)),'max_kl_keep_to_drop':max(kl),
        'max_absolute_logit_error':max(max_abs),'rms_logit_error':float(np.sqrt(np.mean(sq))),
        'top1_differing_rows':[i for i,v in enumerate(top) if not v],'kl_by_row':kl}
    report['passed']=finite and all(report['fixed_packed_identity'].values())
except BaseException as exc:
    report['error']=repr(exc);save();raise
finally:
    if unloaded and state['health_before'].get('loaded'):
        try:
            state['load']=protocol.request('/load',post=True);state['health_after']=protocol.request('/health')
            if not state['health_after'].get('loaded'):raise RuntimeError('Daily service failed to restore')
        except BaseException as exc:state['restore_error']=repr(exc);report['passed']=False;raise
    report['service_transition']=state;report['finished']=stamp();save()
