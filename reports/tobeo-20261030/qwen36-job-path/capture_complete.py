"""Gate trace-only instrumentation, observe overhead, capture jobs, restore service."""
import argparse,json,os,signal,sqlite3,subprocess,sys,time
from pathlib import Path
import numpy as np
import psutil
from build_complete import OUT,SOURCE,BUILD,host,BASE_BUILD,digest,save,stamp
sys.path.insert(0,str(OUT.parent/'qwen36-copy3905'))
from run_validation import arguments,audit_processes


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
            if name.upper().startswith(('STRATA_','DS4_')):del os.environ[name]
        os.environ.update(environment(a.arm))
        exe=(BASE_BUILD if a.arm=='baseline' else BUILD)/'strata-q36.exe'
        engine=host.Eng(str(exe),args(),env=environment(a.arm),log=str(log));record['engine_pid']=engine.p.pid
        assert 'prompt experts on MMQ (int8)' in log.read_text(encoding='utf-8')
        record['warmup']=host.protocol.measured_request(engine,json.loads((host.FIXTURES/'r1-l1024.ids.json').read_text()),64)
        ids=json.loads((host.FIXTURES/(a.case+'.ids.json')).read_text())
        refs=json.loads((OUT.parent/'qwen36-copy3905/execution-02/results.json').read_text(encoding='utf-8'))
        expected=next(x['output_ids'] for x in refs['rows'] if x['case']==a.case and x['pair'] is None)
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
    parser=argparse.ArgumentParser();parser.add_argument('--worker',action='store_true');parser.add_argument('--directory',type=Path)
    parser.add_argument('--arm',choices=['baseline','off','on']);parser.add_argument('--case');parser.add_argument('--tag');parser.add_argument('--profiler',action='store_true')
    a=parser.parse_args()
    if a.worker:worker(a);return
    directory=OUT/'capture-02';directory.mkdir(exist_ok=False)
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
        conflicts=[p for p in audit_processes() if any(x in (p['name'] or '').lower() for x in ['nsys','ncu','nvcc','ninja']) or any(Path(x).name.startswith('download') for x in p['cmdline'] or [])]
        assert not conflicts,conflicts
        profile([str(OUT/'probe-complete.exe')],'preflight')
        with sqlite3.connect(directory/'preflight.sqlite') as db:
            rows=db.execute("select text,start,end from NVTX_EVENTS where text like 'JT probe%'").fetchall()
        assert any(x[0]=='JT probe' and x[2] and x[2]>x[1] for x in rows) and any(x[0]=='JT probe_mark' for x in rows)
        r['nvtx_probe']=rows;r['health_before']=host.api('/health');r['config_sha256_before']=digest(host.CONFIG)
        r['unload']=host.api('/unload?wait=30',True);assert r['unload'].get('status') in ['unloaded','not loaded'];unloaded=True
        assert not [p for p in audit_processes() if (p['name'] or '').lower() in ['strata.exe','strata-q36.exe']]
        r['bandwidth-before']=host.bandwidth(directory,'bandwidth-before');r['phase']='numeric';persist()
        reference=json.loads((OUT.parent/'qwen36-copy3905/execution-02/results.json').read_text(encoding='utf-8'))
        for case in ['r0-l1024','r0-l16384']:
            expected=next(x for x in reference['numeric'] if x['case']==case and x['arm']=='baseline')
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
                layout=host.layout(directory/(tag+'.console.log'));assert layout['slots']==[63] and layout['chunks']==[2048] and not any(layout['slot_replacements'])
                r['numeric'].append({'case':case,'arm':arm,'sha256':digest(dump),'bytes':dump.stat().st_size,'finite':True});persist()
        r['phase']='observations';persist()
        for case in ['r0-l1024','r0-l16384']:
            for arm in ['baseline','off','on']:
                tag=case+'-'+arm+'-plain';run([sys.executable,str(Path(__file__).resolve()),'--worker','--directory',str(directory),'--arm',arm,'--case',case,'--tag',tag],tag,arm)
                row=json.loads((directory/(tag+'.json')).read_text(encoding='utf-8'));assert row['passed'];r['requests'].append(tag);persist()
            tag=case+'-on-trace'
            profile([sys.executable,str(Path(__file__).resolve()),'--worker','--directory',str(directory),'--arm','on','--case',case,'--tag',tag,'--profiler'],tag)
            row=json.loads((directory/(tag+'.json')).read_text(encoding='utf-8'));assert row['passed']
            with sqlite3.connect(directory/(tag+'.sqlite')) as db:
                count=db.execute("select count(*) from NVTX_EVENTS where text like 'JT job%'").fetchone()[0]
            assert count>10000,count
            r['requests'].append(tag);persist()
        r['bandwidth-after']=host.bandwidth(directory,'bandwidth-after');host.check_identity()
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
                    if Path(child.exe()).resolve() in {(BUILD/'strata-q36.exe').resolve(),(BASE_BUILD/'strata-q36.exe').resolve()}:child.kill();child.wait(timeout=30)
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
