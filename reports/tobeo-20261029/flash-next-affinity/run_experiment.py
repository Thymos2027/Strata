"""Existing affinity policies: functional gates then five controlled restart rounds."""
from datetime import datetime,timedelta,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import urllib.request
import psutil

OUT=Path(__file__).resolve().parent;REPO=OUT.parents[2]
sys.path.insert(0,str(REPO));sys.path.insert(0,str(REPO/'tools'))
import calibrate as C
import strata_tokenizer as ST
from serve.server import StrataEngine,with_component_engine,child_env
sys.path.insert(0,str(REPO/'reports/tobeo-20261022/qwen36-context-curve'))
from windows_telemetry import Telemetry,thread_affinities

RUN=OUT/'execution-04';RUN.mkdir(exist_ok=False)
os.environ['STRATA_COMPONENTS_DIR']=r'D:\Models\Strata\components'
cfg=with_component_engine(json.loads((REPO/'strata-iq3_s.json').read_text(encoding='utf-8')))
record={'started':None,'phase':'fingerprinting','passed':False,'arms':[],'rows':[],
        'gate':{},'fingerprints':{},'downloads_suspended':[],'service_transition':{}}
expected={};expected_drafts={};slots=None;active=None;unloaded=False


def stamp():return datetime.now(timezone(timedelta(hours=8))).isoformat()
def digest(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save():
    temp=RUN/'results.tmp';temp.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(RUN/'results.json')
def request(path,post=False):
    url='http://127.0.0.1:8080'
    req=urllib.request.Request(url+path,data=b'{}' if post else None,headers={'Origin':url,'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=600 if post else 10) as r:return json.load(r)


def arguments(mode):
    a=C.engine_args(cfg)
    changes={'--pool-affinity':mode,'--pool-workers':None,'--expert-cache':'2400','--prefill':'1024',
             '--spec':'4','--spec-min-p':'0','--lookup-chain':'0','--suffix-draft':'0',
             '--pcie-frac':'0.55','--adapt-every':'0','--adapt-swaps':'0','--conversation-cache-mib':'0'}
    for flag,value in changes.items():a=C.with_arg(a,flag,value)
    return a


def environment():
    e={k:v for k,v in child_env(cfg).items() if not k.startswith('STRATA_')}
    e.update(STRATA_PREFILL_CPU_SHARE='0',STRATA_ROUTE_TAIL_SKIP='0',
             CUDA_VISIBLE_DEVICES='0',CUDA_MODULE_LOADING='EAGER')
    return e


def suspend_downloads():
    # The current fresh-range downloader owns curl workers: pause the whole owned tree.
    candidates={}
    for p in psutil.process_iter(['name','cmdline']):
        if 'python' not in (p.info['name'] or '').lower():continue
        if any(Path(a).name in ['download_deepseek.py','download_deepseek_fresh.py'] for a in (p.info['cmdline'] or [])):
            candidates[p.pid]=p
    for p in candidates.values():
        if p.status()==psutil.STATUS_STOPPED:raise RuntimeError('Downloader already stopped externally')
        item={'pid':p.pid,'created':p.create_time(),'name':p.name()};p.suspend();record['downloads_suspended'].append(item);save()
    descendants={}
    for p in candidates.values():
        for child in p.children(recursive=True):
            if child.pid not in candidates:descendants[child.pid]=child
    for p in descendants.values():
        try:
            item={'pid':p.pid,'created':p.create_time(),'name':p.name()};p.suspend();record['downloads_suspended'].append(item);save()
        except psutil.NoSuchProcess:continue
    for row in record['downloads_suspended']:
        p=psutil.Process(row['pid']);assert p.create_time()==row['created'] and p.status()==psutil.STATUS_STOPPED
    record['download_pause_at']=stamp();save();time.sleep(5)


def resume_downloads():
    rows=[]
    for item in reversed(record['downloads_suspended']):
        try:
            p=psutil.Process(item['pid']);assert p.create_time()==item['created'],'PID reused'
            p.resume();rows.append({'pid':p.pid,'resumed':p.status()!=psutil.STATUS_STOPPED})
        except psutil.NoSuchProcess:rows.append({'pid':item['pid'],'exited':True})
        except BaseException as exc:rows.append({'pid':item['pid'],'error':repr(exc)})
    record['download_resumption']=rows;save()
    assert all(row.get('resumed') or row.get('exited') for row in rows),'Download tree restore failed'


def bandwidth(label):
    probe=REPO/'reports/tobeo-20261024/pcie-root-cause/transfer_probe.exe'
    env=environment();cuda=REPO/'build-native-baseline/toolchains/cuda-13.2.0'
    env['PATH']=os.pathsep.join([str(cuda/'bin/x64'),str(cuda/'bin'),env['PATH']])
    r=subprocess.run([str(probe)],env=env,capture_output=True,text=True,timeout=90)
    (RUN/(label+'.log')).write_text(r.stdout+'\n'+r.stderr,encoding='utf-8')
    match=re.search(r'"test":"pinned_H2D"[^\n]*"event_GBps":([0-9.]+)',r.stdout)
    value=float(match[1]) if match else None
    record[label]={'exit_code':r.returncode,'h2d_GBps':value};save()
    assert r.returncode==0 and value is not None and value>=15,'HtoD gate failed'
    return value


def sample(e,name,ids,cap,formal=False):
    first=None;out=[];telemetry=None
    proc=psutil.Process(e.proc.pid);before=proc.cpu_times()
    cpu_before={t.id:t.user_time+t.system_time for t in proc.threads()}
    if formal:telemetry=Telemetry(e.proc.pid);telemetry.begin()
    start=time.perf_counter()
    try:
        params={'temperature':0,'top_p':1,'top_k':0,'min_p':0,'presence_penalty':0,
                'frequency_penalty':0,'repetition_penalty':1,'strata_checkpoint':False,'seed':0}
        for token in e.generate(ids,cap,params,threading.Event()):
            if token is not None:
                if first is None:first=time.perf_counter()-start
                out.append(token)
        elapsed=time.perf_counter()-start;timing=dict(e.last or {})
    finally:
        resources=telemetry.end() if telemetry else None
        if telemetry:telemetry.close()
    after=proc.cpu_times();threads=proc.threads()
    row={'name':name,'prompt_tokens':len(ids),'output_ids':out,'output_sha256':hashlib.sha256(json.dumps(out,separators=(',',':')).encode()).hexdigest(),
         'timings':timing,'client_first_token_s':first,'client_total_s':elapsed,
         'process_cpu_s':after.user+after.system-before.user-before.system,
         'thread_cpu_s':{str(t.id):t.user_time+t.system_time-cpu_before.get(t.id,0) for t in threads},'resources':resources}
    row['request_ms']=timing['prompt_ms']+timing['decode_ms']
    row['protocol_passed']=(timing.get('reused')==0 and timing.get('drafts_offered',-1)>=0 and
                            timing.get('file_blobs',0)==0 and timing.get('prompt_tokens')==len(ids) and len(out)==timing.get('generated'))
    return row


def parse_placement(log):
    text=log.read_text(encoding='utf-8',errors='replace')
    mode=re.findall(r'pool workers: (\d+), affinity: ([a-z-]+)',text)
    choice=re.findall(r'all \((\d+) workers\) ([\d.]+) ms, p-cores \((\d+) workers\) ([\d.]+) ms .* -> ([a-z-]+)',text)
    if not mode:
        workers=re.findall(r'CPU workers on logical processors[^\n]*\((\d+) workers',text)
        if workers and ('--pool-affinity all' in text or (choice and choice[-1][4]=='all')):
            mode=[(workers[-1],'all')]
    return {'pool_lines':[s for s in text.splitlines() if any(k in s for k in ['pool workers:','pool workers on logical','host thread on','pool-affinity measure:'])],
            'actual_mode':mode[-1][1] if mode else None,'actual_workers':int(mode[-1][0]) if mode else None,
            'measurement':({'all_workers':int(choice[-1][0]),'all_ms':float(choice[-1][1]),
                            'p_workers':int(choice[-1][2]),'p_ms':float(choice[-1][3]),'selected':choice[-1][4]} if choice else None)}


def run_arm(tag,mode,formal=False,round_no=None,order=None):
    global active,slots
    assert digest(cfg['exe'])==record['fingerprints'][cfg['exe']]['sha256']
    arm={'tag':tag,'mode':mode,'formal':formal,'round':round_no,'args':arguments(mode),'started':stamp()}
    record['arms'].append(arm);save();print('START '+tag,flush=True)
    log=RUN/(tag+'.log');e=None
    try:
        start=time.monotonic();e=StrataEngine(cfg['exe'],arguments(mode),cwd=str(REPO),log=str(log),env=environment());active=e
        arm.update(load_seconds=time.monotonic()-start,info=dict(e.info),**parse_placement(log))
        info=e.info
        assert info.get('version')=='0.1.52' and int(info.get('context',0))==65536 and str(info.get('kv'))=='int8'
        assert int(info.get('spec',-1))==4 and int(info.get('conversation_cache_mib',-1))==0
        assert int(info.get('lookup',-1))==0 and int(info.get('vram_free_mib',0))>=512,'Drafting/memory headroom gate failed'
        current=(int(info['expert_slots']),int(info['expert_cache_mib']))
        if slots is None:slots=current;record['fixed_cache']={'slots':current[0],'mib':current[1]}
        assert current==slots,'Actual expert budget changed'
        if mode=='measure':assert arm['measurement'] and arm['actual_mode']==arm['measurement']['selected']
        else:assert arm['actual_mode']==mode
        arm['warmup']=sample(e,'warmup',warm,96)
        assert arm['warmup']['protocol_passed']
        arm['thread_affinities']=thread_affinities(e.proc.pid);save()
        rows=[]
        for task in order or workloads:
            row=sample(e,task['name'],task['ids'],256,formal)
            row.update(tag=tag,mode=mode,round=round_no)
            row['length_passed']=len(row['output_ids'])==256 and row['timings']['finish']=='length'
            if task['name'] not in expected:expected[task['name']]=row['output_ids']
            row['identical']=row['output_ids']==expected[task['name']]
            drafts=(row['timings']['drafts_offered'],row['timings']['drafts_accepted'])
            assert drafts[0]>0,'MTP did not execute'
            if task['name'] not in expected_drafts:expected_drafts[task['name']]=drafts
            row['draft_counts_identical']=drafts==expected_drafts[task['name']]
            rows.append(row)
            if formal:record['rows'].append(row)
            else:record['gate'].setdefault(mode,{'rows':[],'tasks':[]})['rows'].append(row)
            save();print(tag,task['name'],row['protocol_passed'],row['identical'],flush=True)
            assert row['protocol_passed'] and row['length_passed'] and row['identical'] and row['draft_counts_identical'],'Token identity/draft counts/protocol gate failed'
        if not formal:
            for task in checks:
                row=sample(e,task['name'],task['ids'],task.get('cap',64));text=tok.decode(row['output_ids']).removesuffix('<|im_end|>').strip()
                passed=False
                if task['kind']=='json':
                    try:passed=json.loads(text)==task['expected']
                    except ValueError:pass
                elif task['kind']=='literal':passed=text==task['expected']
                else:
                    result=subprocess.run([sys.executable,str(REPO/'reports/tobeo-20261028/qwen36-pr4347/judge_code.py')],
                        input=json.dumps({'text':text,'inputs':[[3,8],[8,3],[-4,-4]],'expected':[5,5,0]}),capture_output=True,text=True,timeout=3)
                    passed=result.returncode==0 and json.loads(result.stdout)['passed']
                row.update(output=text,task_passed=bool(passed and row['protocol_passed']))
                record['gate'][mode]['tasks'].append(row);save()
                assert row['task_passed'],'Deterministic task check failed: '+task['name']
    finally:
        if e:
            process=e.proc;e.close()
            if process and process.poll() is None:process.kill();process.wait(timeout=30)
        active=None;arm['finished']=stamp()
        if log.exists():arm.update(parse_placement(log))
        save()


record['started']=stamp();save()
try:
    record['daily_config_sha256_before']=digest(REPO/'strata-iq3_s.json')
    record['plan_sha256']=digest(OUT/'experiment-plan.md');record['runner_sha256']=digest(__file__)
    record['resolved_config']=cfg;save()
    fingerprint=[Path(cfg['exe'])]
    for flag in ['--native','--ple-gguf','--expert-profile']:
        a=cfg['args'];fingerprint.append(Path(a[a.index(flag)+1]))
    pack=Path(cfg['args'][cfg['args'].index('--pack')+1]);fingerprint.extend(p for p in pack.rglob('*') if p.is_file())
    mtp=Path(cfg['args'][cfg['args'].index('--mtp')+1]);fingerprint.extend(p for p in mtp.rglob('*') if p.is_file())
    previous=json.loads((OUT/'execution-03/results.json').read_text(encoding='utf-8'))['fingerprints']
    record['fingerprint_reuse_from']='execution-03 (full hashes; only reused when size/mtime unchanged)'
    for path in fingerprint:
        key=str(path)
        if key in record['fingerprints']:continue
        record['fingerprinting']=path.name;save()
        stat=path.stat();cached=previous.get(key)
        sha=cached['sha256'] if cached and cached['bytes']==stat.st_size and cached['mtime_ns']==stat.st_mtime_ns else digest(path)
        record['fingerprints'][key]={'bytes':stat.st_size,'mtime_ns':stat.st_mtime_ns,'sha256':sha};save()
    tpath=Path(cfg['tokenizer']);v=json.loads((tpath/'vocab.json').read_text(encoding='utf-8'));tokens=[None]*len(v)
    for token,i in v.items():tokens[i]=token
    tok=ST.Tokenizer(tokens,(tpath/'merges.txt').read_text(encoding='utf-8').split('\n'),json.loads((tpath/'token_type.json').read_text(encoding='utf-8')))
    warm=C.chat_ids(tok,'AFFINITY_WARMUP: Explain in detail how a refrigerator moves heat. Keep writing for at least 500 words.')
    workloads=[]
    for name,target,request_text in [
        ('code',1024,'Write a detailed Python LRU cache implementation, complexity analysis, cancellation and concurrency discussion, plus tests. Use at least 800 words.'),
        ('english',4096,'Write a detailed English technical review of the synthetic ledger: ownership, cancellation, fairness and bounds. Use at least 800 words.'),
        ('chinese',1024,'请用至少1500字详细解释CPU、GPU、内存和SSD怎样协作运行混合专家模型，结合下面的合成记录举例，并讨论缓存和任务调度。')]:
        prefix=f'AFFINITY_{name.upper()}\n{request_text}\nSynthetic fictional ledger follows:\n'
        body=''.join(f'Record {i}: request={i*17+3}, budget={i%19+1}, operation=restore; verify ownership and bounds. 合成记录，不是真实测量。\n' for i in range(250))
        tail='\nNow provide the requested detailed answer, not just record numbers.'
        n=len(C.chat_ids(tok,prefix+tail));ids_body=tok.encode(body)[:target-n]
        while '\ufffd' in tok.decode(ids_body):ids_body=ids_body[:-1]
        prompt=prefix+tok.decode(ids_body)+tail;ids=C.chat_ids(tok,prompt)
        workloads.append({'name':name,'text':prompt,'ids':ids,'actual_tokens':len(ids)})
    checks=[{'name':'sum','text':'Calculate 13+29. Return only JSON {"value": integer}.','kind':'json','expected':{'value':42}},
            {'name':'product','text':'Calculate 7*8. Return only JSON {"value": integer}.','kind':'json','expected':{'value':56}},
            {'name':'chinese-literal','text':'请只输出：缓存命中。不要标点或解释。','kind':'literal','expected':'缓存命中'},
            {'name':'chinese-json','text':'只返回JSON对象，字段“原因”的值是“容量不足”，没有其他字段。','kind':'json','expected':{'原因':'容量不足'}},
            {'name':'english-literal','text':'Output exactly READY and nothing else.','kind':'literal','expected':'READY'},
            {'name':'absdiff','text':'Write only one pure Python function solve(a, b) returning the absolute difference. No imports or explanation.','kind':'code','cap':128}]
    for task in checks:task['ids']=C.chat_ids(tok,'CHECK_'+task['name']+'\n'+task['text'])
    (OUT/'workloads.json').write_text(json.dumps({'warmup_ids':warm,'performance':workloads,'checks':checks},ensure_ascii=False,indent=2),encoding='utf-8')
    record['workloads_sha256']=digest(OUT/'workloads.json')
    state=record['service_transition'];state['health_before']=request('/health')
    state['unload']=request('/unload?wait=30',True);assert state['unload'].get('status') in ['unloaded','not loaded']
    unloaded=True;record['phase']='functional-gates';save()
    for mode in ['all','p-cores','measure']:run_arm('gate-'+mode,mode)
    record['gate_passed']=True;save();suspend_downloads();before=bandwidth('bandwidth-before')
    record['phase']='benchmark';save()
    for n,order in enumerate([['all','p-cores','measure'],['p-cores','measure','all'],['measure','all','p-cores'],['measure','p-cores','all'],['all','measure','p-cores']]):
        tasks=workloads[n%3:]+workloads[:n%3]
        for mode in order:run_arm(f'round-{n}-{mode}',mode,True,n,tasks)
    after=bandwidth('bandwidth-after');record['bandwidth_relative_drift']=abs(after/before-1)
    assert record['bandwidth_relative_drift']<=0.15
    record['passed']=True;record['phase']='complete';save()
except BaseException as exc:record['phase']='failed';record['error']=repr(exc);save();raise
finally:
    errors=[]
    try:resume_downloads()
    except BaseException as exc:errors.append(repr(exc))
    try:
        state=record['service_transition']
        if unloaded and state['health_before'].get('loaded'):
            state['load']=request('/load',True);state['health_after']=request('/health');assert state['health_after']['loaded']
        record['daily_config_sha256_after']=digest(REPO/'strata-iq3_s.json')
        assert record['daily_config_sha256_after']==record['daily_config_sha256_before']
    except BaseException as exc:errors.append(repr(exc))
    if errors:record['restore_errors']=errors;record['passed']=False
    record['finished']=stamp();save()
    if errors:raise RuntimeError(str(errors))
