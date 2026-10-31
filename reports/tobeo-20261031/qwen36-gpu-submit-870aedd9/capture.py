"""Gate trace-only instrumentation, observe overhead, capture jobs, restore service."""
import argparse,json,os,re,signal,sqlite3,subprocess,sys,time
from pathlib import Path
import numpy as np
import psutil
from build_complete import OUT,SOURCE,BUILD,host,BASE_BUILD,digest,save,stamp
from context import arguments,audit_processes,BASE,conflicts


def environment(arm):
    env=host.environment();env['PATH']=os.pathsep.join([str(BASE_BUILD if arm=='baseline' else BUILD),env['PATH']])
    if arm=='on':env['STRATA_Q36_JOB_TRACE']='1'
    else:env.pop('STRATA_Q36_JOB_TRACE',None)
    return env


def args():return arguments('off')


def worker(a):
    from torch.cuda.nvtx import range_push,range_pop
    record={'started':stamp(),'passed':False,'arm':a.arm,'case':a.case,'profiler':a.profiler,
            'script_sha256':digest(__file__),'args':args(),'output_ids':[]}
    engine=None;log=a.directory/(a.tag+'.engine.log')
    try:
        assert not host.api('/health')['loaded']
        for name in list(os.environ):
            if name.upper().startswith(('STRATA_','DS4_')) or name.upper() in ['CUDA_LAUNCH_BLOCKING','CUDA_DEVICE_MAX_CONNECTIONS','CUDA_FORCE_PTX_JIT']:del os.environ[name]
        os.environ.update(environment(a.arm))
        exe=(BASE_BUILD if a.arm=='baseline' else BUILD)/'strata-q36.exe'
        engine=host.Eng(str(exe),args(),env=environment(a.arm),log=str(log));record['engine_pid']=engine.p.pid
        assert 'prompt experts on MMQ (int8)' in log.read_text(encoding='utf-8')
        record['warmup']=host.protocol.measured_request(engine,json.loads((host.FIXTURES/'r1-l1024.ids.json').read_text()),64)
        assert record['warmup']['generated_tokens']==64 and record['warmup']['draft_offered']==record['warmup']['reused_tokens']==0
        ids=json.loads((host.FIXTURES/(a.case+'.ids.json')).read_text())
        refs=json.loads((BASE/'validation-01/results.json').read_text(encoding='utf-8'))
        expected=next(x['output_ids'] for x in refs['rows'] if x['case']==a.case and x['repeat']==1)
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
        f=done.split()
        record.update(done=done,prompt_ms=float(f[3]),decode_ms=float(f[4]),client_ttft_s=first-start,
                      client_total_s=time.perf_counter()-start,output_sha256=host.protocol.tokens_hash(record['output_ids']))
        assert record['output_ids']==expected and len(expected)==int(f[1])==64
        assert int(f[2])==int(f[14])==len(ids) and int(f[6])==int(f[7])==int(f[8])==0 and f[5]=='length'
        record['passed']=True
    except BaseException as exc:record['error']=repr(exc);raise
    finally:
        if engine:
            engine.close()
            if engine.p.poll() is None:engine.p.kill();engine.p.wait(timeout=30)
            record['exit_code']=engine.p.returncode
        if log.exists():
            record['layout']=host.layout(log);layout=record['layout']
            if layout['slots']!=[63] or layout['chunks']!=[2048] or not layout['slot_replacements'] or any(layout['slot_replacements']) or record.get('exit_code')!=0:record['passed']=False
        record['finished']=stamp();save(a.directory/(a.tag+'.json'),record)
    if not record['passed']:raise RuntimeError('Request gate failed')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--round',type=int,choices=[1,2],default=1);parser.add_argument('--worker',action='store_true');parser.add_argument('--directory',type=Path)
    parser.add_argument('--arm',choices=['baseline','off','on']);parser.add_argument('--case');parser.add_argument('--tag');parser.add_argument('--profiler',action='store_true')
    a=parser.parse_args()
    if a.worker:worker(a);return
    directory=OUT/('capture-'+str(a.round).zfill(2));directory.mkdir(exist_ok=False)
    r={'started':stamp(),'passed':False,'phase':'preflight','commands':[],'numeric':[],'requests':[],
       'restore_errors':[],'script_sha256':digest(__file__),'plan_sha256':digest(OUT/'completion-plan.md')}
    persist=lambda:save(directory/'results.json',r)
    unloaded=False;active=None;persist()

    def run(command,name,arm='on',cwd=None):
        nonlocal active
        print(name,flush=True);row={'name':name,'command':command};r['commands'].append(row);persist()
        with (directory/(name+'.console.log')).open('w',encoding='utf-8') as f:
            active=subprocess.Popen(command,env=environment(arm),cwd=cwd,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            try:code=active.wait(timeout=900)
            except BaseException:
                subprocess.run(['taskkill','/PID',str(active.pid),'/T','/F'],capture_output=True);raise
        row['exit_code']=code;persist();assert code==0,name

    def profile(command,tag):
        run([str(host.NSYS),'profile','--trace=cuda,nvtx','--sample=none','--cpuctxsw=none','--cuda-graph-trace=node',
             '--kill=false','--wait=all','--output='+str(directory/tag),*command],tag+'-capture')
        run([str(host.NSYS),'export','--type=sqlite','--output='+str(directory/(tag+'.sqlite')),str(directory/(tag+'.nsys-rep'))],tag+'-export')

    try:
        b=json.loads((OUT/'build-complete.json').read_text(encoding='utf-8'));assert b['passed']
        r['build_results_sha256']=digest(OUT/'build-complete.json')
        host.check_identity();assert all(digest(BUILD/k)==v for k,v in b['binaries'].items())
        assert all(digest(SOURCE/k)==v for k,v in b['source_hashes'].items())
        other_jobs=conflicts();assert not other_jobs,other_jobs
        profile([str(OUT/'probe-complete.exe')],'preflight')
        with sqlite3.connect(directory/'preflight.sqlite') as db:
            rows=db.execute("select text,start,end from NVTX_EVENTS where text like 'JT probe%'").fetchall()
        assert any(x[0]=='JT probe' and x[2] and x[2]>x[1] for x in rows) and any(x[0]=='JT probe_mark' for x in rows)
        r['nvtx_probe']=rows;r['health_before']=host.api('/health');r['config_sha256_before']=digest(host.CONFIG)
        unloaded=True;r['unload']=host.api('/unload?wait=30',True);assert r['unload'].get('status') in ['unloaded','not loaded']
        assert not [p for p in audit_processes() if (p['name'] or '').lower() in ['strata.exe','strata-q36.exe']]
        r['bandwidth-before']=host.bandwidth(directory,'bandwidth-before');r['phase']='numeric';persist()
        reference=json.loads((BASE/'validation-01/results.json').read_text(encoding='utf-8'))
        if a.round==1:
            for case in ['r0-l1024','r0-l16384']:
                expected=next(x for x in reference['numeric'] if x['case']==case)
                ids=json.loads((host.FIXTURES/(case+'.ids.json')).read_text())
                tok=directory/(case+'.tokens');force=directory/(case+'.forced')
                tok.write_text(','.join(map(str,ids)),encoding='ascii');force.write_text(','.join(map(str,expected['output_ids'][:63])),encoding='ascii')
                for arm in ['off','on']:
                    tag='numeric-'+case+'-'+arm;dump=directory/(tag+'.f32')
                    run([b['adapter']['exe'],*args(),'--tokens-file',str(tok),'--force-file',str(force),'--dump-full-logits',str(dump)],tag,arm)
                    text=(directory/(tag+'.console.log')).read_text(encoding='utf-8')
                    assert 'prompt experts on MMQ (int8)' in text
                    assert dump.stat().st_size==expected['bytes'] and digest(dump)==expected['sha256']
                    assert np.isfinite(np.memmap(dump,dtype=np.float32,mode='r')).all()
                    layout=host.layout(directory/(tag+'.console.log'));assert layout['slots']==[63] and layout['chunks']==[2048] and layout['slot_replacements'] and not any(layout['slot_replacements'])
                    gen=re.search(r'^gen: ([0-9 ]+)$',text,re.M);assert gen and [int(n) for n in gen[1].split()]==expected['output_ids']
                    r['numeric'].append({'case':case,'arm':arm,'sha256':digest(dump),'bytes':dump.stat().st_size,'finite':True});persist()
        else:
            first=OUT/'capture-01';prior=json.loads((first/'results.json').read_text(encoding='utf-8'))
            assert prior['passed'] and not prior['restore_errors'] and prior['build_results_sha256']==r['build_results_sha256'] and len(prior['numeric'])==4
            for x in prior['numeric']:assert digest(first/('numeric-'+x['case']+'-'+x['arm']+'.f32'))==x['sha256']
            r['numeric']=prior['numeric'];r['numeric_reused_from']='capture-01/results.json';persist()
        r['phase']='observations';persist()
        cases=['r0-l1024','r0-l16384'] if a.round==1 else ['r0-l16384','r0-l1024']
        order=['baseline','off','on','trace'] if a.round==1 else ['trace','on','off','baseline']
        r['observation_order']=[{'case':c,'arm':arm} for c in cases for arm in order];persist()
        for case in cases:
            for arm in order:
                if arm=='trace':
                    tag=case+'-on-trace'
                    profile([sys.executable,str(Path(__file__).resolve()),'--worker','--directory',str(directory),'--arm','on','--case',case,'--tag',tag,'--profiler'],tag)
                    with sqlite3.connect(directory/(tag+'.sqlite')) as db:count=db.execute("select count(*) from NVTX_EVENTS where text like 'JT job%'").fetchone()[0]
                    assert count>10000,count
                else:
                    tag=case+'-'+arm+'-plain'
                    run([sys.executable,str(Path(__file__).resolve()),'--worker','--directory',str(directory),'--arm',arm,'--case',case,'--tag',tag],tag,arm)
                row=json.loads((directory/(tag+'.json')).read_text(encoding='utf-8'));assert row['passed'];r['requests'].append(tag);persist()
        r['bandwidth-after']=host.bandwidth(directory,'bandwidth-after');assert abs(r['bandwidth-after']['h2d_GBps']/r['bandwidth-before']['h2d_GBps']-1)<=.1;host.check_identity()
        assert all(digest(SOURCE/k)==v for k,v in b['source_hashes'].items())
        assert all(digest(BUILD/k)==v for k,v in b['binaries'].items())
        r['passed']=True;r['phase']='complete'
    except BaseException as exc:r['error']=repr(exc);r['phase']='failed';persist();raise
    finally:
        signal.signal(signal.SIGINT,signal.SIG_IGN)
        try:
            if active and active.poll() is None:subprocess.run(['taskkill','/PID',str(active.pid),'/T','/F'],capture_output=True)
            for child in psutil.Process().children(recursive=True):
                try:
                    if Path(child.exe()).resolve() in {(BUILD/'strata-q36.exe').resolve(),(BASE_BUILD/'strata-q36.exe').resolve(),Path(b['adapter']['exe']).resolve()}:child.kill();child.wait(timeout=30)
                except psutil.NoSuchProcess:pass
            if unloaded and r['health_before'].get('loaded'):
                if not host.api('/health')['loaded']:r['restore']=host.api('/load',True)
                r['health_after']=host.api('/health')
                assert r['health_after']['loaded'] and r['health_after']['model']==r['health_before']['model']
        except BaseException as exc:r['restore_errors'].append(repr(exc))
        if 'config_sha256_before' in r:
            r['config_sha256_after']=digest(host.CONFIG)
            if r['config_sha256_after']!=r['config_sha256_before']:r['restore_errors'].append('Daily config changed')
        if r['restore_errors']:r['passed']=False
        r['finished']=stamp();persist();print(json.dumps({k:r.get(k) for k in ['passed','phase','error','restore_errors','finished']}),flush=True)


if __name__=='__main__':main()
