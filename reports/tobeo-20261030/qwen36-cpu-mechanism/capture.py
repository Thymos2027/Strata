"""Fixed-binary CPU sampling pilot, with same-day controls and service restoration."""
import argparse,ctypes,json,os,signal,sqlite3,subprocess,sys,time
from pathlib import Path
import psutil

OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT.parent/'qwen36-copy3905'))
from run_validation import host,environment,arguments,audit_processes,BASE_BUILD,BUILD,digest,save,stamp
sys.path.insert(0,str(OUT.parents[1]/'tobeo-20261023/qwen36-profiling'))
from capture_modules import modules


def pid(value):return (value//0x1000000)%0x1000000


def worker(a):
    from torch.cuda.nvtx import range_push,range_pop
    if a.probe:
        range_push('cpu-preflight');end=time.perf_counter()+2;count=0
        while time.perf_counter()<end:count=(count+1)%100000003
        range_pop();save(a.directory/'probe.json',{'pid':os.getpid(),'iterations':count});return
    exe=(BASE_BUILD if a.arm=='baseline' else BUILD)/'strata-q36.exe'
    record={'started':stamp(),'passed':False,'arm':a.arm,'case':a.case,'profiler':a.profiler,
            'script_sha256':digest(__file__),'args':arguments(a.arm),'output_ids':[]}
    engine=None;tag=a.tag;log=a.directory/(tag+'.engine.log')
    try:
        assert not host.api('/health')['loaded']
        for name in list(os.environ):
            if name.upper().startswith(('STRATA_','DS4_')):del os.environ[name]
        os.environ.update(environment(a.arm))
        engine=host.Eng(str(exe),arguments(a.arm),env=environment(a.arm),log=str(log))
        assert 'prompt experts on MMQ (int8)' in log.read_text(encoding='utf-8')
        record.update(engine_pid=engine.p.pid,load_s=engine.load_s)
        warm=json.loads((host.FIXTURES/'r1-l1024.ids.json').read_text())
        record['warmup']=host.protocol.measured_request(engine,warm,64)
        mapping={'pid':engine.p.pid,'modules':modules(engine.p.pid)}
        save(a.directory/(tag+'.modules.json'),mapping)
        ids=json.loads((host.FIXTURES/(a.case+'.ids.json')).read_text())
        reference=json.loads((OUT.parent/'qwen36-copy3905/execution-02/results.json').read_text(encoding='utf-8'))
        expected=next(x['output_ids'] for x in reference['rows'] if x['case']==a.case and x['pair'] is None)
        record['prompt_sha256']=host.protocol.tokens_hash(ids)
        process=psutil.Process(engine.p.pid);before=process.cpu_times()
        range_push('request')
        try:
            range_push('prefill-to-first-token')
            try:
                start=time.perf_counter();first=None
                engine.send('GEN 64 '+host.protocol.KEYS+' '+','.join(map(str,ids)))
                while True:
                    line=engine.line(300)
                    if line is None or line.startswith('ERR'):raise RuntimeError(str(line))
                    if line.startswith('T '):
                        if first is None:first=time.perf_counter();range_pop();range_push('decode-after-first-token')
                        record['output_ids'].append(int(line.split()[1]))
                    elif line.startswith('DONE '):done=line;break
            finally:range_pop()
        finally:range_pop()
        after=process.cpu_times();f=done.split()
        record.update(done=done,prompt_ms=float(f[3]),decode_ms=float(f[4]),client_ttft_s=first-start,
                      client_total_s=time.perf_counter()-start,process_cpu_s=after.user+after.system-before.user-before.system,
                      output_sha256=host.protocol.tokens_hash(record['output_ids']))
        assert record['output_ids']==expected and len(expected)==int(f[1])==64
        assert int(f[2])==int(f[14])==len(ids) and int(f[6])==int(f[7])==int(f[8])==0 and f[5]=='length'
        record['passed']=True
    except BaseException as exc:record['error']=repr(exc);raise
    finally:
        if engine:
            engine.close()
            if engine.p.poll() is None:engine.p.kill();engine.p.wait(timeout=30)
            record['engine_exit_code']=engine.p.returncode
        if log.exists():
            record['layout']=host.layout(log);layout=record['layout']
            if layout['slots']!=[63] or layout['chunks']!=[2048] or not layout['slot_replacements'] or any(layout['slot_replacements']) or record.get('engine_exit_code')!=0:record['passed']=False
        record['finished']=stamp();save(a.directory/(tag+'.json'),record)
    if not record['passed']:raise RuntimeError('Request gate failed')


def cpu_check(path,target,window=None):
    with sqlite3.connect(path) as db:
        clauses='((globalTid/16777216)%16777216)=?';values=[target]
        if window:clauses+=' and start>=? and start<?';values+=list(window)
        samples=db.execute('select count(*) from COMPOSITE_EVENTS where cpuCycles=1 and '+clauses,values).fetchone()[0]
        scheduled=db.execute('select count(*) from SCHED_EVENTS where '+clauses,values).fetchone()[0]
        assert samples>=50 and scheduled>0,(samples,scheduled)
        return {'periodic_samples':samples,'scheduling_events':scheduled}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--worker',action='store_true');parser.add_argument('--probe',action='store_true')
    parser.add_argument('--directory',type=Path);parser.add_argument('--arm',choices=['baseline','on']);parser.add_argument('--case')
    parser.add_argument('--tag');parser.add_argument('--profiler',action='store_true');a=parser.parse_args()
    if a.worker:worker(a);return
    directory=OUT/'capture-01';directory.mkdir(exist_ok=False)
    r={'started':stamp(),'passed':False,'phase':'preflight','restore_errors':[],'commands':[],
       'script_sha256':digest(__file__),'plan_sha256':digest(OUT/'experiment-plan.md')}
    persist=lambda:save(directory/'results.json',r)
    active=None;unloaded=False;persist()

    def run(command,name,arm='baseline'):
        nonlocal active
        print(name,flush=True);row={'name':name,'command':command};r['commands'].append(row);persist()
        with (directory/(name+'.console.log')).open('w',encoding='utf-8') as f:
            active=subprocess.Popen(command,env=environment(arm),stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            try:code=active.wait(timeout=900)
            except BaseException:
                subprocess.run(['taskkill','/PID',str(active.pid),'/T','/F'],capture_output=True);raise
        row['exit_code']=code;persist();assert code==0,name

    def profile(worker_args,tag,arm='baseline'):
        run([str(host.NSYS),'profile','--trace=cuda,nvtx','--sample=process-tree','--cpuctxsw=process-tree',
             '--sampling-frequency=500','--backtrace=none','--resolve-symbols=false','--cuda-graph-trace=node',
             '--kill=false','--wait=all','--output='+str(directory/tag),sys.executable,str(Path(__file__).resolve()),
             '--worker','--directory',str(directory),*worker_args],tag+'-capture',arm)
        run([str(host.NSYS),'export','--type=sqlite','--output='+str(directory/(tag+'.sqlite')),str(directory/(tag+'.nsys-rep'))],tag+'-export',arm)

    try:
        assert ctypes.windll.shell32.IsUserAnAdmin()
        p=subprocess.run([str(host.NSYS),'status','--environment'],capture_output=True,text=True)
        r['nsys_environment']=p.stdout+p.stderr;r['nsys_sha256']=digest(host.NSYS)
        assert 'Sampling Environment: OK' in p.stdout
        host.check_identity()
        b=json.loads((OUT.parent/'qwen36-copy3905/build-results.json').read_text(encoding='utf-8'))
        assert all(digest(BUILD/name)==sha for name,sha in b['binaries'].items())
        r['binaries']={str(folder/name):digest(folder/name) for folder in [BASE_BUILD,BUILD] for name in ['strata-q36.exe','strata_kq.dll','strata-q36.pdb']}
        conflicts=[p for p in audit_processes() if any(x in (p['name'] or '').lower() for x in ['nsys','ncu','nvcc','ninja']) or any(Path(x).name.startswith('download') for x in p['cmdline'] or [])]
        assert not conflicts,conflicts
        profile(['--probe'],'preflight')
        probe=json.loads((directory/'probe.json').read_text());r['cpu_preflight']=cpu_check(directory/'preflight.sqlite',probe['pid']);persist()
        r['health_before']=host.api('/health');r['config_sha256_before']=digest(host.CONFIG)
        r['unload']=host.api('/unload?wait=30',True)
        assert r['unload'].get('status') in ['unloaded','not loaded'];unloaded=True
        assert not [p for p in audit_processes() if (p['name'] or '').lower() in ['strata.exe','strata-q36.exe']]
        r['bandwidth-before']=host.bandwidth(directory,'bandwidth-before');r['phase']='gpu-capture';persist()
        for arm,case in [('baseline','r0-l1024'),('baseline','r0-l16384'),('on','r0-l16384')]:
            tag=arm+'-'+case;args=['--arm',arm,'--case',case]
            run([sys.executable,str(Path(__file__).resolve()),'--worker','--directory',str(directory),'--tag',tag+'-plain',*args],tag+'-plain',arm)
            assert json.loads((directory/(tag+'-plain.json')).read_text())['passed']
            profile([*args,'--tag',tag+'-trace','--profiler'],tag+'-trace',arm)
            record=json.loads((directory/(tag+'-trace.json')).read_text(encoding='utf-8'));assert record['passed']
            with sqlite3.connect(directory/(tag+'-trace.sqlite')) as db:
                windows=db.execute("select start,end from NVTX_EVENTS where text='decode-after-first-token'").fetchall()
            assert len(windows)==1 and windows[0][1] is not None
            r[tag+'-cpu']=cpu_check(directory/(tag+'-trace.sqlite'),record['engine_pid'],windows[0]);persist()
        r['bandwidth-after']=host.bandwidth(directory,'bandwidth-after');host.check_identity()
        assert all(digest(Path(path))==sha for path,sha in r['binaries'].items())
        r['passed']=True;r['phase']='complete'
    except BaseException as exc:r['error']=repr(exc);r['phase']='failed';persist();raise
    finally:
        signal.signal(signal.SIGINT,signal.SIG_IGN)
        try:
            if active and active.poll() is None:subprocess.run(['taskkill','/PID',str(active.pid),'/T','/F'],capture_output=True)
            for child in psutil.Process().children(recursive=True):
                try:
                    if Path(child.exe()).resolve() in {(BASE_BUILD/'strata-q36.exe').resolve(),(BUILD/'strata-q36.exe').resolve()}:child.kill();child.wait(timeout=30)
                except psutil.NoSuchProcess:pass
            if unloaded and r['health_before'].get('loaded'):
                r['restore']=host.api('/load',True);r['health_after']=host.api('/health')
                assert r['health_after']['loaded'] and r['health_after']['model']==r['health_before']['model']
        except BaseException as exc:r['restore_errors'].append(repr(exc))
        if 'config_sha256_before' in r:
            r['config_sha256_after']=digest(host.CONFIG)
            if r['config_sha256_after']!=r['config_sha256_before']:r['restore_errors'].append('Daily config changed')
        if r['restore_errors']:r['passed']=False
        r['finished']=stamp();persist();print(json.dumps({k:r.get(k) for k in ['passed','phase','error','restore_errors','finished']}),flush=True)


if __name__=='__main__':main()
