"""Detached native Strata operator probe. Does not implement multi-session prefill."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import threading
import time
import traceback
import urllib.request

import psutil

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BUILD = ROOT/'build-native-baseline/build-main-870aedd9-cuda132-sm120'
SOURCE = ROOT/'build-native-baseline/src-main-870aedd9'
CUDA = ROOT/'build-native-baseline/toolchains/cuda-13.2.0'
MODEL = Path(r'D:\Models\Qwen\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf')
sys.path.insert(0,str(ROOT/'tools'))
from gguf_reader import GGUFFile
spec=importlib.util.spec_from_file_location('service_helpers',ROOT/'reports/tobeo-20261103/flashnext-262k/workflow.py')
h=importlib.util.module_from_spec(spec); spec.loader.exec_module(h); h.OUT=OUT
h.STATE['validation_scope']='Real quantized weight GEMM grouping probe only; full segmented prefill not implemented or tested'
urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))
RESULTS=[]
ENV=None
CMD_FLAGS=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP

def digest(p):
    with Path(p).open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

def run(cmd,label,timeout):
    h.stage(label)
    with (OUT/(label+'.stdout.log')).open('wb') as out,(OUT/(label+'.stderr.log')).open('wb') as err:
        proc=subprocess.Popen(cmd,cwd=OUT,env=ENV,stdout=out,stderr=err,stdin=subprocess.DEVNULL,creationflags=CMD_FLAGS)
        h.ACTIVE=proc
        try:
            rc=proc.wait(timeout=timeout)
        except BaseException:
            h.kill_tree(proc.pid); raise
        finally:
            h.ACTIVE=None
    if h.GUARD_ERROR: raise RuntimeError(h.GUARD_ERROR)
    if rc: raise RuntimeError(f'{label} exited {rc}; inspect logs')

def compile_probe():
    global ENV
    spec=importlib.util.spec_from_file_location('compiler_helper',ROOT/'reports/tobeo-20261022/windows-native-baseline/build_native.py')
    helper=importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    # compiler_environment only: no old source extraction or build workflow.
    ENV,_,vs=helper.compiler_environment()
    ENV={k:v for k,v in ENV.items() if not k.upper().startswith(('STRATA_','DS4_'))
         and k.upper() not in ('CUDA_LAUNCH_BLOCKING','CUDA_FORCE_PTX_JIT','CUDA_DEVICE_MAX_CONNECTIONS')}
    ENV['PATH']=os.pathsep.join([str(BUILD),str(CUDA/'bin'),str(CUDA/'bin/x64'),ENV['PATH']])
    ENV.update(CUDA_MODULE_LOADING='EAGER',CUDA_VISIBLE_DEVICES='0',PYTHONUTF8='1')
    libraries=[BUILD/n for n in ('strata_prefill.lib','strata_engine.lib','strata_kernels.lib','strata_core.lib',
               'strata_kernels_cpu.lib','strata_mmq.lib','strata_mmq_w4a4.lib')]
    libraries += [BUILD/'ggml/src/ggml-cpu.lib',BUILD/'ggml/src/ggml-base.lib']
    if not all(p.exists() for p in libraries): raise RuntimeError('Required native build libraries missing')
    cmd=[str(CUDA/'bin/nvcc.exe'),'-std=c++17','-O3','-arch=sm_120','-Xcompiler','/MD',
         '-I'+str(SOURCE/'include'),str(OUT/'probe.cu'),'-o',str(OUT/'probe.exe'),
         *map(str,libraries),'-L'+str(CUDA/'lib/x64'),'-lcublas','-lcublasLt','-lcuda']
    h.save('build-command.json',{'command':cmd,'vs':vs,'source_include':str(SOURCE),
           'library_build_revision':'870aedd9e1ebe1c91f94da93b59af17729f6c5c0',
           'library_engine_version':'0.1.54','daily_engine_version_expected':'0.1.52',
           'libraries':{str(p):digest(p) for p in libraries},'probe_sha256':digest(OUT/'probe.cu'),
           'header_sha256':digest(SOURCE/'include/strata/prefill/gemm.hpp')})
    run(cmd,'build',1200)
    h.save('build-result.json',{'passed':True,'executable_sha256':digest(OUT/'probe.exe')})

def extract():
    h.stage('extracting_real_weight_matrices')
    gg=GGUFFile(MODEL)
    names=['blk.0.attn_qkv.weight','blk.0.attn_gate.weight','blk.0.ffn_gate_exps.weight','blk.0.ffn_down_exps.weight']
    selected=[]
    with MODEL.open('rb') as src:
        for name in names:
            t=next(t for t in gg.tensors if t.name==name)
            k,n=t.shape[:2]; total=t.expected_bytes()
            per=total//(t.shape[2] if len(t.shape)==3 else 1)
            src.seek(gg.data_start+t.offset)
            data=src.read(per)
            if len(data)!=per: raise RuntimeError('Incomplete weight extraction')
            p=OUT/(name+'.bin'); p.write_bytes(data)
            selected.append({'name':name,'file':str(p),'K':k,'N':n,'type_id':t.type_id,'type_name':t.type_name,
                             'bytes':per,'sha256':digest(p),'expert_index':0 if len(t.shape)==3 else None,
                             'source_offset':gg.data_start+t.offset})
    h.save('weights.json',{'source':str(MODEL),'source_bytes':MODEL.stat().st_size,'selected':selected,
                         'full_model_hash_recomputed':False})
    return selected

def gpu_snapshot():
    smi=subprocess.run(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu,power.draw',
                        '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
    smi.check_returncode()
    vals=[float(x.strip()) for x in smi.stdout.strip().splitlines()[0].split(',')]
    return dict(zip(('used_mib','total_mib','util_pct','power_w'),vals))

def samples(stop):
    with (OUT/'resources.jsonl').open('a',encoding='utf8') as f:
        while not stop.wait(3):
            try:
                vm=psutil.virtual_memory()
                f.write(json.dumps({'time':h.stamp(),'stage':h.STATE['status'],'ram_available':vm.available,
                                    'gpu':gpu_snapshot()})+'\n'); f.flush()
            except Exception as e:
                f.write(json.dumps({'time':h.stamp(),'sampling_error':repr(e)})+'\n'); f.flush()

def analyze_log(label,weight,rows,batch):
    lines=(OUT/(label+'.stdout.log')).read_text().splitlines()
    check=[l for l in lines if l.startswith('CHECK,')]
    pairs=[l.split(',') for l in lines if l.startswith('PAIR,')]
    if len(check)!=1 or len(pairs)!=10: raise RuntimeError('Incomplete native probe output')
    for mode in ('resident','streamed'):
        pp=[p for p in pairs if p[1]==mode]
        if len(pp)!=5: raise RuntimeError('Missing timing pairs')
        ratios=[float(p[5]) for p in pp]
        result={'weight':weight['name'],'type':weight['type_name'],'rows_per_request':rows,'batch':batch,
                'mode':mode,'correctness_line':check[0],
                'pairs':[{'pair':int(p[2]),'separate_ms':float(p[3]),'packed_ms':float(p[4]),'ratio':float(p[5]),
                          'separate_transfer_bytes':int(p[6]),'packed_transfer_bytes':int(p[7])} for p in pp],
                'ratio_median':statistics.median(ratios),'ratio_min':min(ratios),'ratio_max':max(ratios),
                'packed_faster_pairs':sum(v>1 for v in ratios)}
        RESULTS.append(result)
    h.save('summary.json',{'operator_cases':RESULTS,'full_prefill_tested':False,
                          'scope':h.STATE['validation_scope'],'review_required':True})

def main():
    h.stage('preparing_operator_probe')
    h.save('repository.json',{'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                              'time':h.stamp(),'workflow_sha256':digest(__file__)})
    compile_probe()
    weights=extract()
    original=h.CFG.read_bytes()
    # Only stop a positively identified, idle daily server. If absent, keep it absent.
    listeners={c.pid for c in psutil.net_connections(kind='tcp') if c.status=='LISTEN' and c.laddr.port==8080}
    owner=None
    if listeners:
        if len(listeners)!=1: raise RuntimeError('Ambiguous 8080 owner')
        owner=psutil.Process(listeners.pop())
        if 'serve.server' not in owner.cmdline() or str(h.CFG) not in owner.cmdline(): raise RuntimeError('Unknown 8080 owner')
        m=h.api(8080,'/metrics'); h.save('original.metrics.json',m)
        if m['live']['state']!='idle' or m['live'].get('queued'): raise RuntimeError('Daily service busy; leaving it intact')
    h.save('original-service-state.json',{'running':owner is not None,'config_sha256':hashlib.sha256(original).hexdigest()})
    failure=None
    stop=threading.Event()
    try:
        if owner:
            h.stage('stopping_idle_daily_service',daily_pid=owner.pid); h.kill_tree(owner.pid); time.sleep(5)
        gpu=gpu_snapshot(); h.save('before-gpu.json',gpu)
        if gpu['total_mib']-gpu['used_mib']<2048 or gpu['util_pct']>10:
            raise RuntimeError('Insufficient idle GPU headroom; refusing contaminated GPU timing')
        threading.Thread(target=h.memory_guard,daemon=True).start()
        sampler=threading.Thread(target=samples,args=(stop,),daemon=True); sampler.start()
        for wi,weight in enumerate(weights):
            for rows in (64,256,1024):
                for batch in (2,4):
                    if h.GUARD_ERROR: raise RuntimeError(h.GUARD_ERROR)
                    label=f'w{wi}-rows{rows}-batch{batch}'
                    run([str(OUT/'probe.exe'),weight['file'],str(weight['type_id']),str(weight['N']),
                         str(weight['K']),str(rows),str(batch)],label,180)
                    analyze_log(label,weight,rows,batch)
        h.stage('operator_probe_complete',operator_cases=len(RESULTS))
    except Exception:
        failure=traceback.format_exc()
        h.stage('operator_probe_failed',error=failure,guard_error=h.GUARD_ERROR)
    finally:
        stop.set(); h.GUARD_STOP.set()
        if 'sampler' in locals(): sampler.join(timeout=20)
        if h.ACTIVE: h.kill_tree(h.ACTIVE.pid); h.ACTIVE=None
        if owner:
            if h.CFG.read_bytes()!=original: raise RuntimeError('External config edit; cannot safely restore automatically')
            h.GUARD_ERROR=None
            _,health=h.launch(h.CFG,8080,'restored-daily')
            h.complete(8080,[{'role':'user','content':'Reply with exactly READY.'}],'restored-smoke',32)
            h.save('restored.health.json',health)
        h.stage('operator_probe_failed' if failure else 'operator_probe_complete_pending_review',
                error=failure,operator_cases=len(RESULTS),daily_was_running=owner is not None,
                daily_restored=owner is not None,full_prefill_tested=False,review_required=True)
    return 1 if failure else 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception:
        h.stage('workflow_error',error=traceback.format_exc(),full_prefill_tested=False)
        raise
