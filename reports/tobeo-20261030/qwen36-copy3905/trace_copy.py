"""Conditional two-trace follow-up; refuses to run without the completed signal."""
import argparse,json,os,signal,subprocess,sys,time
from pathlib import Path
import psutil
from run_validation import OUT,BASE,BUILD,host,environment,arguments,digest,save,stamp,audit_processes


def worker(arm,directory):
    from torch.cuda.nvtx import range_push,range_pop
    expected=json.loads((OUT/'execution-02/results.json').read_text(encoding='utf-8'))
    reference=next(r for r in expected['rows'] if r['case']=='r0-l16384' and r['pair'] is None)['output_ids']
    ids=json.loads((host.FIXTURES/'r0-l16384.ids.json').read_text())
    warm=json.loads((host.FIXTURES/'r1-l1024.ids.json').read_text())
    assert not host.api('/health')['loaded']
    record={'arm':arm,'started':stamp(),'passed':False,'args':arguments(arm),'output_ids':[],
            'script_sha256':digest(__file__),'prompt_sha256':host.protocol.tokens_hash(ids)}
    engine=None;log=directory/(arm+'.engine.log')
    try:
        for name in list(os.environ):
            if name.upper().startswith(('STRATA_','DS4_')):del os.environ[name]
        os.environ.update(environment(arm))
        engine=host.Eng(str(BUILD/'strata-q36.exe'),arguments(arm),env=environment(arm),log=str(log))
        assert 'prompt experts on MMQ (int8)' in log.read_text(encoding='utf-8',errors='replace')
        record.update(engine_pid=engine.p.pid,load_s=engine.load_s,warmup=host.protocol.measured_request(engine,warm,64))
        range_push('request')
        try:
            range_push('prefill-to-first-token')
            try:
                start=time.perf_counter();first=None
                engine.send('GEN 64 '+host.protocol.KEYS+' '+','.join(map(str,ids)))
                while True:
                    line=engine.line(300)
                    if line is None or line.startswith('ERR'):raise RuntimeError('Engine failed: '+str(line))
                    if line.startswith('T '):
                        if first is None:
                            first=time.perf_counter();range_pop();range_push('decode-after-first-token')
                        record['output_ids'].append(int(line.split()[1]))
                    elif line.startswith('DONE '):done=line;break
            finally:range_pop()
        finally:range_pop()
        f=done.split()
        record.update(done=done,prompt_ms=float(f[3]),decode_ms=float(f[4]),client_ttft_s=first-start,
                      client_total_s=time.perf_counter()-start,output_sha256=host.protocol.tokens_hash(record['output_ids']))
        assert record['output_ids']==reference and len(reference)==int(f[1])==64
        assert int(f[2])==int(f[14])==len(ids) and int(f[8])==int(f[7])==0 and f[5]=='length'
        record['passed']=True
    except BaseException as exc:record['error']=repr(exc);raise
    finally:
        if engine:
            engine.close()
            if engine.p.poll() is None:engine.p.kill();engine.p.wait(timeout=30)
            record['exit_code']=engine.p.returncode
        if log.exists():
            record['layout']=host.layout(log)
            if record['layout']['slots']!=[63] or record['layout']['chunks']!=[2048] or not record['layout']['slot_replacements'] or any(record['layout']['slot_replacements']) or record.get('exit_code')!=0:record['passed']=False
        record['finished']=stamp();save(directory/(arm+'.json'),record)
    if not record['passed']:raise RuntimeError('Trace worker gate failed')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--worker',choices=['off','on']);parser.add_argument('--directory',type=Path)
    a=parser.parse_args()
    if a.worker:
        assert a.directory;worker(a.worker,a.directory);return
    prior=json.loads((OUT/'execution-02/results.json').read_text(encoding='utf-8'))
    assert prior['passed'] and prior['finished'] and prior['trace_required'] and not prior['restore_errors']
    directory=OUT/'traces-01';directory.mkdir(exist_ok=False)
    record={'started':stamp(),'passed':False,'phase':'preflight','commands':[],'restore_errors':[],
            'performance_evidence_sha256':digest(OUT/'execution-02/results.json'),'script_sha256':digest(__file__)}
    persist=lambda:save(directory/'results.json',record)
    unloaded=False;active=None;persist()
    try:
        host.check_identity()
        b=json.loads((OUT/'build-results.json').read_text(encoding='utf-8'))
        assert all(digest(BUILD/name)==sha for name,sha in b['binaries'].items())
        # Same byte-identical CLI as the successful earlier 10-30 preflight; actual model reports are checked anew.
        preflight=json.loads((OUT.parent/'qwen36-systems/capture-01/results.json').read_text(encoding='utf-8'))
        assert preflight['passed'] and digest(host.NSYS)==preflight['nsys']['sha256']
        record['nsys_sha256']=digest(host.NSYS)
        conflicts=[p for p in audit_processes() if any(term in (p['name'] or '').lower() for term in ['nsys','ncu','nvcc','ninja']) or any(Path(arg).name.lower().startswith('download') and Path(arg).suffix=='.py' for arg in p['cmdline'] or [])]
        assert not conflicts
        record['health_before']=host.api('/health');record['config_sha256_before']=digest(host.CONFIG)
        record['unload']=host.api('/unload?wait=30',True)
        assert record['unload'].get('status') in ['unloaded','not loaded'];unloaded=True
        assert not [p for p in audit_processes() if (p['name'] or '').lower() in ['strata.exe','strata-q36.exe']]
        record['bandwidth-before']=host.bandwidth(directory,'bandwidth-before');persist()
        for arm in ['off','on']:
            cmd=[str(host.NSYS),'profile','--trace=cuda,nvtx','--sample=none','--cpuctxsw=none','--cuda-graph-trace=node',
                 '--kill=false','--wait=all','--output='+str(directory/arm),sys.executable,str(Path(__file__).resolve()),'--worker',arm,'--directory',str(directory)]
            export=[str(host.NSYS),'export','--type=sqlite','--output='+str(directory/(arm+'.sqlite')),str(directory/(arm+'.nsys-rep'))]
            for kind,command in [('capture',cmd),('export',export)]:
                print('TRACE',arm,kind,flush=True)
                row={'arm':arm,'kind':kind,'command':command};record['commands'].append(row);persist()
                with (directory/(arm+'-'+kind+'.console.log')).open('w',encoding='utf-8') as log:
                    active=subprocess.Popen(command,env=environment(arm),stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                    try:code=active.wait(timeout=600)
                    except BaseException:
                        subprocess.run(['taskkill','/PID',str(active.pid),'/T','/F'],capture_output=True);raise
                row['exit_code']=code;persist()
                assert code==0
                if kind=='capture':assert json.loads((directory/(arm+'.json')).read_text(encoding='utf-8'))['passed']
        record['bandwidth-after']=host.bandwidth(directory,'bandwidth-after')
        record['passed']=True;record['phase']='complete'
    except BaseException as exc:record['error']=repr(exc);record['phase']='failed';persist();raise
    finally:
        signal.signal(signal.SIGINT,signal.SIG_IGN)
        try:
            if active and active.poll() is None:subprocess.run(['taskkill','/PID',str(active.pid),'/T','/F'],capture_output=True)
            for p in psutil.Process().children(recursive=True):
                try:
                    if Path(p.exe()).resolve()==(BUILD/'strata-q36.exe').resolve():p.kill();p.wait(timeout=30)
                except psutil.NoSuchProcess:pass
            if unloaded and record['health_before'].get('loaded'):
                record['restore']=host.api('/load',True);record['health_after']=host.api('/health')
                assert record['health_after']['loaded'] and record['health_after']['model']==record['health_before']['model']
        except BaseException as exc:record['restore_errors'].append(repr(exc))
        if 'config_sha256_before' in record:
            record['config_sha256_after']=digest(host.CONFIG)
            if record['config_sha256_before']!=record['config_sha256_after']:record['restore_errors'].append('Daily config changed')
        if record['restore_errors']:record['passed']=False
        record['finished']=stamp();persist()
        print(json.dumps({k:record.get(k) for k in ['passed','phase','finished','restore_errors']}),flush=True)


if __name__=='__main__':main()
