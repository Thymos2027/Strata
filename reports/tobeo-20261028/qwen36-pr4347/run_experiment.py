"""Current-main correctness, PR4347 policy gate, then five paired measurements.

Keeps downloads running during functional gates; suspends only this machine's
DeepSeek downloader during performance measurement and resumes it in finally.
"""
import argparse
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import psutil
from build_pair import ARMS, MODEL, OUT, REPO, ROOT, digest, stamp

CUDA=ROOT/'toolchains/cuda-13.2.0'
OLD_CURVE=REPO/'reports/tobeo-20261022/qwen36-context-curve'
sys.path.insert(0,str(OLD_CURVE))
import run_curve as protocol
from windows_telemetry import Telemetry, thread_affinities
sys.path.insert(0,str(ARMS['main']['source']/'tools/qwen35'))
from q36_harness import Eng

parser=argparse.ArgumentParser()
parser.add_argument('--stage',choices=['all','gate','benchmark'],default='all')
parser.add_argument('--wait-build',action='store_true')
parser.add_argument('--run-id',default='execution-02')
a=parser.parse_args()
if not re.fullmatch(r'execution-[0-9]+',a.run_id):parser.error('Use execution-NN as run ID')
RUN=OUT/a.run_id
if RUN.exists():raise RuntimeError('Evidence directory exists; inspect before retry')
RUN.mkdir()
record={'started':stamp(),'phase':'waiting-build','passed':False,'stage':a.stage,
        'configuration':{'context':32768,'prefill':2048,'workers':7,'mtp':0,
                         'expert_budget':'automatic','sampling':protocol.KEYS},
        'gate':{},'arms':[],'rows':[],'downloads_suspended':[]}

def save():
    temporary=RUN/'results.tmp'
    temporary.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(RUN/'results.json')

def env_for(name,keep=False,extra=None):
    env={k:v for k,v in os.environ.items() if not k.startswith('STRATA_')}
    env.update(STRATA_MMQ_KQ='1',STRATA_Q8_PACKED='1',CUDA_VISIBLE_DEVICES='0',CUDA_MODULE_LOADING='EAGER')
    if keep:env['STRATA_Q36_KEEP_PACKED']='1'
    env.update(extra or {})
    env['PATH']=os.pathsep.join([str(CUDA/'bin/x64'),str(CUDA/'bin'),str(ARMS[name]['build']),env.get('PATH','')])
    return env

def native_run(command,name,env,timeout=1200):
    env=dict(env)
    env['PATH']=os.pathsep.join([str(CUDA/'bin/x64'),str(CUDA/'bin'),str(ARMS['main']['build']),env.get('PATH','')])
    t=time.monotonic()
    with (RUN/'fixed'/(name+'.console.log')).open('w',encoding='utf-8') as log:
        p=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        try:code=p.wait(timeout=timeout)
        except BaseException:
            subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True);raise
    return {'name':name,'command':command,'exit_code':code,'seconds':time.monotonic()-t}

def fixed_gate():
    directory=RUN/'fixed';directory.mkdir()
    path=REPO/'reports/tobeo-20261021/qwen36-source-baseline/run_correctness.py'
    spec=importlib.util.spec_from_file_location('current_fixed_gate',path)
    matrix=importlib.util.module_from_spec(spec);spec.loader.exec_module(matrix)
    matrix.OUT=directory;matrix.ROOT=ROOT
    matrix.REVISION=ARMS['main']['revision'];matrix.SOURCE=ARMS['main']['source']
    # q36_solo_gate uses POSIX shlex on --args, including on Windows.
    matrix.BUILD=ARMS['main']['build'];matrix.CUDA=CUDA;matrix.MODEL=MODEL.as_posix()
    matrix.ENVIRONMENT='Windows native; MSVC 19.42; CUDA 13.2; sm_120; current v0.2.7'
    matrix.run=native_run
    # The gate matrix starts each child from a clean engine environment.
    for key in list(os.environ):
        if key.startswith('STRATA_'):os.environ.pop(key)
    os.environ['STRATA_MMQ_KQ']='1';os.environ['STRATA_Q8_PACKED']='1'
    code=matrix.main()
    result=json.loads((directory/'correctness-summary.json').read_text())
    record['gate']['fixed_main']=result;save()
    if code or not result.get('passed'):raise RuntimeError('Current main fixed-layout correctness failed')

def workloads():
    return {case:json.loads((OLD_CURVE/(case+'.ids.json')).read_text())
            for case in ['r0-l1024','r0-l16384','r1-l1024']}

def run_arm(tag,name,keep,cases,cap,ids,pair=None):
    exe=ARMS[name]['build']/'strata-q36.exe'
    args=['--native',str(MODEL),'--max-context','32768','--prefill','2048','--pool-workers','7','--mtp','0']
    arm={'tag':tag,'source':name,'keep_packed':keep,'pair':pair,'args':args,'profiler':False,
         'environment':{k:v for k,v in env_for(name,keep).items() if k.startswith('STRATA_') or k in ['CUDA_VISIBLE_DEVICES','CUDA_MODULE_LOADING']},
         'log':str(RUN/(tag+'.engine.log'))}
    record['arms'].append(arm);save()
    print('START '+tag,flush=True)
    engine=telemetry=None;rows=[]
    try:
        engine=Eng(str(exe),args,env=env_for(name,keep),log=arm['log'])
        arm.update(pid=engine.p.pid,load_s=engine.load_s,info=engine.info,
                   thread_affinities=thread_affinities(engine.p.pid))
        arm['warmup']=protocol.measured_request(engine,ids['r1-l1024'],64)
        telemetry=Telemetry(engine.p.pid)
        for case in cases:
            telemetry.begin()
            before=psutil.Process(engine.p.pid).cpu_times()
            try:row=protocol.measured_request(engine,ids[case],cap)
            finally:resources=telemetry.end()
            after=psutil.Process(engine.p.pid).cpu_times()
            row.update(tag=tag,pair=pair,case=case,source=name,keep_packed=keep,
                       input_sha256=protocol.tokens_hash(ids[case]),resources=resources,
                       process_cpu_s=(after.user+after.system)-(before.user+before.system))
            row['protocol_passed']=row['reused_tokens']==0 and row['draft_offered']==0 and row['generated_tokens']==cap and row['finish']=='length'
            record['rows'].append(row);rows.append(row);save()
            print(json.dumps({k:row[k] for k in ['tag','case','generated_tokens','decode_tok_s','protocol_passed']}),flush=True)
            if not row['protocol_passed']:raise RuntimeError('Fresh/count/MTP protocol gate failed')
    finally:
        if telemetry:telemetry.close()
        if engine:
            engine.close()
            if engine.p.poll() is None:
                engine.p.kill();engine.p.wait(timeout=30)
            arm['engine_exit_code']=engine.p.returncode
        if Path(arm['log']).exists():
            log=Path(arm['log']).read_text(errors='replace')
            arm['placement_lines']=[line for line in log.splitlines() if any(key in line for key in ['hybrid experts:','given back','packed Q8','Graph','graph','slot replacements','context 32768'])]
            arm['given_back']=any('given back to the expert slots' in line for line in log.splitlines())
            arm['slots_per_layer']=[int(x) for x in re.findall(r'hybrid experts: (\d+) of 256',log)]
        save()
    if engine and engine.p.returncode:raise RuntimeError('Engine exited nonzero')
    if name=='pr4347' and not keep and not arm.get('given_back'):
        raise RuntimeError('Candidate policy did not trigger; no performance claim')
    return rows

def policy_gate(ids):
    cases=['r0-l1024','r0-l16384']
    groups={}
    for tag,name,keep in [('gate-main','main',False),('gate-keep','pr4347',True),('gate-drop','pr4347',False)]:
        groups[tag]=run_arm(tag,name,keep,cases,64,ids)
    checks=[]
    for i,case in enumerate(cases):
        ref=groups['gate-main'][i]['output_ids']
        checks.append({'case':case,'main_vs_candidate_keep':ref==groups['gate-keep'][i]['output_ids'],
                       'main_vs_candidate_drop':ref==groups['gate-drop'][i]['output_ids']})
    record['gate']['policy']=checks
    passed=all(c['main_vs_candidate_keep'] and c['main_vs_candidate_drop'] for c in checks)
    record['gate']['passed']=passed;save()
    if not passed:raise RuntimeError('Token identity gate differed; numerical diagnosis required before performance claims')

def suspend_downloads():
    suspended=[]
    for p in psutil.process_iter(['name','cmdline','create_time']):
        if p.pid==os.getpid() or 'python' not in (p.info['name'] or '').lower():continue
        if not any(Path(arg).name=='download_deepseek.py' for arg in (p.info['cmdline'] or [])):continue
        if p.status()==psutil.STATUS_STOPPED:raise RuntimeError('Downloader already suspended outside this run')
        p.suspend();suspended.append({'pid':p.pid,'created':p.create_time()})
    record['downloads_suspended']=suspended;record['download_pause_at']=stamp();save()
    time.sleep(5)

def resume_downloads():
    rows=[]
    for item in record['downloads_suspended']:
        try:
            p=psutil.Process(item['pid'])
            if p.create_time()!=item['created']:raise RuntimeError('PID reused')
            p.resume();rows.append({'pid':p.pid,'resumed':True})
        except psutil.NoSuchProcess:rows.append({'pid':item['pid'],'exited':True})
        except Exception as exc:rows.append({'pid':item['pid'],'error':repr(exc)})
    record['download_resumption']=rows;record['download_resume_at']=stamp();save()

def bandwidth_control(name):
    exe=REPO/'reports/tobeo-20261024/pcie-root-cause/transfer_probe.exe'
    run=subprocess.run([str(exe)],env=env_for('main'),capture_output=True,text=True,timeout=90)
    (RUN/(name+'.log')).write_text(run.stdout+'\n'+run.stderr,encoding='utf-8')
    match=re.search(r'"test":"pinned_H2D"[^\n]*"event_GBps":([0-9.]+)',run.stdout)
    row={'exit_code':run.returncode,'h2d_GBps':float(match.group(1)) if match else None}
    record[name]=row;save()
    if run.returncode or row['h2d_GBps'] is None or row['h2d_GBps']<15:
        raise RuntimeError('Transfer control outside restored environment')

def benchmark(ids):
    suspend_downloads()
    bandwidth_control('bandwidth-before')
    for pair in range(5):
        order=[True,False] if pair%2==0 else [False,True]
        cases=['r0-l1024','r0-l16384'] if pair%2==0 else ['r0-l16384','r0-l1024']
        results={}
        for keep in order:
            tag=f'pair-{pair}-'+('keep' if keep else 'drop')
            results[keep]=run_arm(tag,'pr4347',keep,cases,256,ids,pair)
        checks=[{'pair':pair,'case':case,'identical':next(r for r in results[True] if r['case']==case)['output_ids']==next(r for r in results[False] if r['case']==case)['output_ids']} for case in cases]
        record.setdefault('pair_checks',[]).extend(checks);save()
        if not all(c['identical'] for c in checks):raise RuntimeError('Paired output differs; stop and diagnose')
    bandwidth_control('bandwidth-after')

state={'health_before':None};unloaded=False
save()
try:
    deadline=time.monotonic()+2400
    while True:
        build=json.loads((OUT/'build-summary.json').read_text())
        if build.get('passed'):break
        if build.get('error'):raise RuntimeError('Build failed: '+build['error'])
        if not a.wait_build or time.monotonic()>deadline:raise RuntimeError('Build not ready')
        time.sleep(5)
    record['build']=build
    for name,arm in ARMS.items():
        if digest(arm['build']/'strata-q36.exe')!=build['arms'][name]['binaries']['strata-q36.exe']:
            raise RuntimeError('Binary provenance changed')
    state['health_before']=protocol.request('/health')
    record['phase']='releasing-daily-model';save()
    state['unload']=protocol.request('/unload?wait=30',post=True)
    if state['unload'].get('status') not in ('unloaded','not loaded'):raise RuntimeError('Daily engine busy')
    unloaded=True
    record['phase']='correctness';save()
    fixed_gate()
    ids=workloads()
    policy_gate(ids)
    if a.stage in ('all','benchmark'):
        record['phase']='benchmark';save();benchmark(ids)
    record['phase']='complete';record['passed']=True
except BaseException as exc:
    record['error']=repr(exc);record['phase']='failed';save();raise
finally:
    previous=signal.signal(signal.SIGINT,signal.SIG_IGN)
    try:
        targets={str((arm['build']/'strata-q36.exe').resolve()).lower() for arm in ARMS.values()}
        for child in psutil.Process().children(recursive=True):
            try:
                if child.exe().lower() in targets:child.kill();child.wait(timeout=30)
            except psutil.NoSuchProcess:pass
        if unloaded and state['health_before'].get('loaded'):
            state['load']=protocol.request('/load',post=True)
            state['health_after']=protocol.request('/health')
            if not state['health_after'].get('loaded'):raise RuntimeError('Daily model did not restore')
    except BaseException as exc:
        state['restore_error']=repr(exc);record['passed']=False;raise
    finally:
        resume_downloads()
        record['service_transition']=state;record['finished']=stamp();save()
        signal.signal(signal.SIGINT,previous)
