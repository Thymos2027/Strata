"""Full-logit gates and five alternating pairs for the attributed copy slice."""
import argparse,json,os,re,signal,subprocess,sys,time
from pathlib import Path
import numpy as np
import psutil
from build_slice import OUT,REPO,BASE,ROOT,REVISION,BASE_BUILD,BASE_SOURCE,BUILD,SOURCE,MODEL,digest,save,stamp

sys.path.insert(0,str(OUT.parent/'qwen36-systems'))
import common as host
from validate_baseline import audit_processes


def environment(arm):
    env=host.environment()
    build=BASE_BUILD if arm=='baseline' else BUILD
    env['PATH']=os.pathsep.join([str(build),env['PATH']])
    return env


def arguments(arm):
    return [*host.arguments(2048),'--expert-slots','63',*(['--split-stage-copy'] if arm=='on' else [])]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run-id',default='execution-02');a=parser.parse_args()
    if not re.fullmatch(r'execution-[0-9]+',a.run_id):parser.error('Expected execution-NN')
    run=OUT/a.run_id;run.mkdir(exist_ok=False)
    record={'started':stamp(),'passed':False,'phase':'preflight','rows':[],'numeric':[],
            'restore_errors':[],'script_sha256':digest(__file__),'plan_sha256':digest(OUT/'experiment-plan.md')}
    persist=lambda:save(run/'results.json',record)
    unloaded=False
    active=None
    persist()
    try:
        build=json.loads((OUT/'build-results.json').read_text(encoding='utf-8'))
        assert build['passed']
        record['build_results_sha256']=digest(OUT/'build-results.json')
        ref=host.check_identity()
        assert digest(SOURCE/'src/qwen35/q36_engine.cu')==build['engine_file_sha256']
        assert all(digest(BUILD/name)==sha for name,sha in build['binaries'].items())
        record['daily_config_sha256_before']=digest(host.CONFIG)
        record['health_before']=host.api('/health')
        record['processes_before']=audit_processes()
        conflicts=[]
        for p in record['processes_before']:
            words=[Path(arg).name.lower() for arg in p['cmdline'] or []]
            if any(w.startswith('download') and w.endswith('.py') for w in words) or any(
                term in (p['name'] or '').lower() for term in ['nsys','ncu','nvcc','ninja']):conflicts.append(p)
        assert not conflicts,'Other research/download jobs active'
        for name in list(os.environ):
            if name.upper().startswith(('STRATA_','DS4_')):del os.environ[name]
        os.environ.update(environment('off'))
        record['unload']=host.api('/unload?wait=30',True)
        assert record['unload'].get('status') in ['unloaded','not loaded']
        unloaded=True
        assert not [p for p in audit_processes() if (p['name'] or '').lower() in ['strata.exe','strata-q36.exe']]
        record['bandwidth-before']=host.bandwidth(run,'bandwidth-before');persist()
        previous=json.loads((BASE/'validation-01/results.json').read_text(encoding='utf-8'))
        expected={case:next(r['output_ids'] for r in previous['rows'] if r['case']==case) for case in ['r0-l1024','r0-l16384']}
        ids={case:json.loads((host.FIXTURES/(case+'.ids.json')).read_text()) for case in [*expected,'r1-l1024']}
        record['fixtures']={case:{'tokens':len(t),'sha256':host.protocol.tokens_hash(t)} for case,t in ids.items()}
        record['phase']='numeric';persist()
        for case in expected:
            tokenfile=run/(case+'.tokens');forcefile=run/(case+'.forced')
            tokenfile.write_text(','.join(map(str,ids[case])),encoding='ascii')
            forcefile.write_text(','.join(map(str,expected[case][:63])),encoding='ascii')
            dumps=[]
            for arm in ['baseline','off','on']:
                tag=case+'-'+arm;dump=run/(tag+'.f32');log=run/(tag+'.log')
                adapter=build['adapters']['baseline' if arm=='baseline' else 'candidate']
                assert digest(adapter['exe'])==adapter['sha256']
                assert digest(Path(adapter['exe']).parent/'strata_kq.dll')==adapter['dll_sha256']
                command=[adapter['exe'],*arguments(arm),'--tokens-file',str(tokenfile),'--force-file',str(forcefile),'--dump-full-logits',str(dump)]
                print('NUMERIC',tag,flush=True)
                with log.open('w',encoding='utf-8') as output:
                    active=subprocess.Popen(command,env=environment(arm),stdout=output,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                    try:code=active.wait(timeout=900)
                    except BaseException:
                        subprocess.run(['taskkill','/PID',str(active.pid),'/T','/F'],capture_output=True);raise
                text=log.read_text(encoding='utf-8',errors='replace')
                assert 'prompt experts on MMQ (int8)' in text and 'not found next to the engine' not in text
                match=re.search(r'^gen: ([0-9 ]+)$',text,re.M)
                output_ids=[int(n) for n in match[1].split()] if match else []
                actual=host.layout(log)
                row={'case':case,'arm':arm,'exit_code':code,'output_ids':output_ids,'layout':actual,'command':command}
                record['numeric'].append(row);persist()
                assert code==0 and output_ids==expected[case]
                assert actual['slots']==[63] and actual['chunks']==[2048] and actual['slot_replacements'] and not any(actual['slot_replacements'])
                assert dump.stat().st_size==64*248320*4
                data=np.memmap(dump,dtype=np.float32,mode='r').reshape(64,248320)
                assert np.isfinite(data).all()
                row.update(bytes=dump.stat().st_size,sha256=digest(dump),finite=True)
                dumps.append(row['sha256']);persist()
            assert len(set(dumps))==1,'Full logits differ; do not start timing'
        record['numeric_passed']=True;persist()

        def request(arm,case,tag,pair=None):
            exe=BUILD/'strata-q36.exe'
            engine=None
            row={'tag':tag,'arm':arm,'case':case,'pair':pair,'args':arguments(arm)}
            print('REQUEST',tag,flush=True)
            try:
                engine=host.Eng(str(exe),arguments(arm),env=environment(arm),log=str(run/(tag+'.engine.log')))
                assert 'prompt experts on MMQ (int8)' in (run/(tag+'.engine.log')).read_text(encoding='utf-8',errors='replace')
                row['engine_pid']=engine.p.pid
                row['load_s']=engine.load_s
                row['warmup']=host.protocol.measured_request(engine,ids['r1-l1024'],64)
                before=psutil.Process(engine.p.pid).cpu_times()
                row.update(host.protocol.measured_request(engine,ids[case],64))
                after=psutil.Process(engine.p.pid).cpu_times()
                row['process_cpu_s']=after.user+after.system-before.user-before.system
                row['output_matches_reference']=row['output_ids']==expected[case]
            finally:
                if engine:
                    engine.close()
                    if engine.p.poll() is None:engine.p.kill();engine.p.wait(timeout=30)
                    row['exit_code']=engine.p.returncode
                row['layout']=host.layout(run/(tag+'.engine.log'))
                record['rows'].append(row);persist()
            actual=row['layout']
            row['passed']=(row.get('exit_code')==0 and row.get('output_matches_reference') and row['reused_tokens']==row['draft_offered']==0 and row['generated_tokens']==64 and row['finish']=='length'
                           and actual['slots']==[63] and actual['chunks']==[2048] and actual['slot_replacements'] and not any(actual['slot_replacements']))
            persist()
            if not row['passed']:raise RuntimeError('Free-generation/layout gate failed')
            return row

        record['phase']='free-generation-gates';persist()
        for case in expected:
            for arm in ['off','on']:request(arm,case,'gate-'+case+'-'+arm)
        record['phase']='paired-performance';persist()
        pairs=[]
        for pair in range(5):
            cases=list(expected) if pair%2==0 else list(reversed(expected))
            for case in cases:
                arms=['off','on'] if pair%2==0 else ['on','off']
                results={arm:request(arm,case,f'pair-{pair}-{case}-{arm}',pair) for arm in arms}
                a,b=results['off'],results['on']
                pairs.append({'pair':pair,'case':case,'prefill_A_ms':a['prompt_ms'],'prefill_B_ms':b['prompt_ms'],
                              'decode_A_ms':a['decode_ms'],'decode_B_ms':b['decode_ms'],
                              'prefill_ratio':a['prompt_ms']/b['prompt_ms'],
                              'decode_ratio':a['decode_ms']/b['decode_ms'],
                              'total_ratio':(a['prompt_ms']+a['decode_ms'])/(b['prompt_ms']+b['decode_ms'])})
                record['pairs']=pairs;persist()
        import statistics
        record['signals']={case:{'prefill_ratio_median':statistics.median(r['prefill_ratio'] for r in pairs if r['case']==case),
                                 'B_prefill_faster':sum(r['prefill_ratio']>1 for r in pairs if r['case']==case)} for case in expected}
        record['trace_required']=any(r['prefill_ratio_median']>1.03 and r['B_prefill_faster']>=4 for r in record['signals'].values())
        record['bandwidth-after']=host.bandwidth(run,'bandwidth-after')
        host.check_identity()
        assert digest(SOURCE/'src/qwen35/q36_engine.cu')==build['engine_file_sha256']
        record['passed']=True;record['phase']='complete'
    except BaseException as exc:record['error']=repr(exc);record['phase']='failed';persist();raise
    finally:
        signal.signal(signal.SIGINT,signal.SIG_IGN)
        try:
            if active and active.poll() is None:subprocess.run(['taskkill','/PID',str(active.pid),'/T','/F'],capture_output=True)
            targets={str((BUILD/'strata-q36.exe').resolve()).lower(),str((OUT/'candidate-file.exe').resolve()).lower(),str((OUT/'baseline-file.exe').resolve()).lower()}
            for child in psutil.Process().children(recursive=True):
                try:
                    if child.exe().lower() in targets:child.kill();child.wait(timeout=30)
                except psutil.NoSuchProcess:pass
            if unloaded and record['health_before'].get('loaded'):
                record['restore']=host.api('/load',True);record['health_after']=host.api('/health')
                assert record['health_after'].get('loaded') and record['health_after']['model']==record['health_before']['model']
        except BaseException as exc:record['restore_errors'].append(repr(exc))
        if 'daily_config_sha256_before' in record:
            record['daily_config_sha256_after']=digest(host.CONFIG)
            if record['daily_config_sha256_after']!=record['daily_config_sha256_before']:record['restore_errors'].append('Daily config changed')
        if record['restore_errors']:record['passed']=False
        record['finished']=stamp();persist()
        print(json.dumps({k:record.get(k) for k in ['passed','phase','trace_required','restore_errors','finished']}),flush=True)


if __name__=='__main__':main()
