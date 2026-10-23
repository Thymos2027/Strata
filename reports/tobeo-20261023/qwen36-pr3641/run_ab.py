"""Same-binary FP32 GQA off/on validation of upstream PR #3641. No profiler."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import psutil

OUT=Path(__file__).resolve().parent
BASE=OUT.parents[1]/'tobeo-20261022/qwen36-context-curve'
sys.path.insert(0,str(BASE))
import run_curve as baseline
from windows_telemetry import Telemetry,thread_affinities
from build_candidate import SOURCE,BUILD,REVISION
sys.path.insert(0,str(SOURCE/'tools/qwen35'))
from q36_harness import Eng
ZONE=timezone(timedelta(hours=8),'Asia/Shanghai')


def save(directory,report):
    (directory/'results.json').write_text(json.dumps(report,indent=2))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['gate','benchmark'],default='gate')
    parser.add_argument('--pairs',type=int,default=5)
    parser.add_argument('--case',choices=['r0-l1024','r0-l16384','both'],default='both')
    args=parser.parse_args()
    if not 1<=args.pairs<=10:parser.error('--pairs must be between 1 and 10')
    if args.mode=='benchmark' and args.pairs<5:parser.error('The research plan requires at least five alternating pairs')
    if args.mode=='benchmark' and args.case!='both':parser.error('Full paired benchmark requires both contexts')
    link=subprocess.check_output(['nvidia-smi','--query-gpu=pcie.link.gen.gpucurrent,pcie.link.gen.gpumax,pcie.link.gen.hostmax,pcie.link.width.current',
                                  '--format=csv,noheader,nounits'],text=True).strip()
    if args.mode=='benchmark' and int(link.split(',')[1])<5:
        raise RuntimeError('PCIe capability is below the established Gen5 baseline; restore and recheck the link before performance claims')
    directory=OUT/(args.mode+('-'+args.case if args.case!='both' else ''))
    if directory.exists():raise RuntimeError('Evidence exists; inspect before retry')
    build=json.loads((OUT/'build-summary.json').read_text())
    exe=BUILD/'strata-q36.exe'
    if not build['passed'] or baseline.digest(exe)!=build['exe_sha256']:
        raise RuntimeError('Candidate build provenance did not pass')
    if args.mode=='benchmark':
        gate=json.loads((OUT/'gate/results.json').read_text())
        if not gate.get('passed') or gate['exe_sha256']!=build['exe_sha256']:
            raise RuntimeError('Run correctness gate before performance pairs')
    directory.mkdir()
    report={'upstream_pr':3641,'revision':REVISION,'exe_sha256':build['exe_sha256'],
            'mode':args.mode,'profiler':False,'kv_dtype':'FP32','expert_slots':64,'pool_workers':7,
            'sampling_protocol':baseline.KEYS,'started_at':datetime.now(ZONE).isoformat(),
            'pairs_requested':args.pairs if args.mode=='benchmark' else 1,'rows':[],'arms':[],'passed':False}
    report['case_scope']=args.case;report['pcie_snapshot_csv']=link
    references=json.loads((BASE/'results.json').read_text())['rows']
    state={'health_before':baseline.request('/health')}
    unloaded=False
    cap=64 if args.mode=='gate' else 256
    try:
        state['unload']=baseline.request('/unload?wait=30',post=True)
        if state['unload'].get('status') not in ('unloaded','not loaded'):
            raise RuntimeError('Daily model did not unload')
        unloaded=True
        for pair in range(report['pairs_requested']):
            order=[0,1] if pair%2==0 else [1,0]
            cases=['r0-l1024','r0-l16384'] if pair%2==0 else ['r0-l16384','r0-l1024']
            if args.case!='both':cases=[args.case]
            for gqa in order:
                tag=f'p{pair}-gqa{gqa}'
                env={k:v for k,v in os.environ.items() if not k.startswith('STRATA_')}
                env.update(baseline.ENV);env['STRATA_Q36_GQA']=str(gqa)
                env['PATH']=os.pathsep.join([str(baseline.CUDA/'bin/x64'),str(baseline.CUDA/'bin'),str(BUILD),env.get('PATH','')])
                common=['--native',str(baseline.MODEL),'--max-context','32768','--prefill','512',
                        '--pool-workers','7','--expert-vram','10.0','--expert-slots','64','--mtp','0']
                engine=telemetry=None
                arm={'pair':pair,'gqa':gqa,'order':order,'arguments':common,'environment':dict(baseline.ENV,STRATA_Q36_GQA=str(gqa))}
                report['arms'].append(arm)
                try:
                    print('Starting '+args.mode+' '+tag,flush=True)
                    engine=Eng(str(exe),common,env=env,log=str(directory/(tag+'.engine.log')))
                    telemetry=Telemetry(engine.p.pid)
                    arm['load_s']=engine.load_s;arm['engine_info']=engine.info
                    arm['thread_affinities']=thread_affinities(engine.p.pid)
                    warm=json.loads((BASE/'r1-l1024.ids.json').read_text())
                    arm['warmup']=baseline.measured_request(engine,warm,cap=64)
                    for case in cases:
                        ids=json.loads((BASE/(case+'.ids.json')).read_text())
                        ref=next(r for r in references if r['case']==case and r['mtp']==0)
                        row={'pair':pair,'gqa':gqa,'case':case,'prompt_ids_sha256':baseline.tokens_hash(ids),'status':'running'}
                        report['rows'].append(row)
                        telemetry.begin()
                        try:
                            row.update(baseline.measured_request(engine,ids,cap=cap))
                        finally:row['resources']=telemetry.end()
                        row['validation']={'fresh':row['reused_tokens']==0,'counts':row['generated_tokens']==cap,
                            'finish_length':row['finish']=='length','mtp_off':row['draft_offered']==0,
                            'input_hash':row['prompt_ids_sha256']==ref['prompt_ids_sha256'],
                            'same_reference_prefix':row['output_ids']==ref['output_ids'][:cap]}
                        row['status']='ok' if all(row['validation'].values()) else 'failed'
                        save(directory,report)
                        print(json.dumps({k:row[k] for k in ['pair','gqa','case','decode_tok_s','status']}),flush=True)
                        if row['status']!='ok':
                            raise RuntimeError('Strict token/protocol gate did not pass; numerical analysis needed before performance claims')
                finally:
                    if telemetry:telemetry.close()
                    if engine:
                        engine.close()
                        if engine.p.poll() is None:subprocess.run(['taskkill','/PID',str(engine.p.pid),'/T','/F'],capture_output=True)
                    save(directory,report)
        report['passed']=True
    finally:
        previous=signal.signal(signal.SIGINT,signal.SIG_IGN)
        try:
            # Also covers an Eng constructor that launched a child but failed before READY.
            for child in psutil.Process().children(recursive=True):
                try:
                    if Path(child.exe()).resolve()==exe.resolve():
                        child.kill();child.wait(timeout=30)
                except psutil.NoSuchProcess:
                    pass
            if unloaded and state['health_before'].get('loaded'):
                state['load']=baseline.request('/load',post=True)
                state['health_after']=baseline.request('/health')
                if not state['health_after'].get('loaded'):raise RuntimeError('Daily model failed to restore')
        except BaseException as exc:
            state['restore_error']=repr(exc);raise
        finally:
            report['finished_at']=datetime.now(ZONE).isoformat();save(directory,report)
            (directory/'service-transition.json').write_text(json.dumps(state,indent=2))
            signal.signal(signal.SIGINT,previous)


if __name__=='__main__':main()
