"""Capture unchanged-engine CPU stacks/context switches plus CUDA, then restore service."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

SCRIPT = Path(__file__).resolve().parent
REPORTS = SCRIPT.parents[1]
PREVIOUS = REPORTS/'tobeo-20261022/qwen36-profiling'
sys.path.insert(0,str(PREVIOUS.parent/'qwen36-context-curve'))
import run_curve as baseline

ZONE = timezone(timedelta(hours=8),'Asia/Shanghai')


def command(nsys,directory,tag,arguments):
    return [str(nsys),'profile','--trace=cuda,nvtx','--sample=process-tree',
            '--cpuctxsw=process-tree','--sampling-frequency=500','--backtrace=none',
            '--resolve-symbols=false','--retain-etw-files=true',
            '--cuda-graph-trace=node','--kill=false','--output='+str(directory/tag),
            sys.executable,str(PREVIOUS/'capture_request.py'),*arguments]


def capture(nsys,directory,tag,arguments):
    cmd = command(nsys,directory,tag,arguments)
    env = dict(os.environ,NSYS_NVTX_PROFILER_REGISTER_ONLY='0',STRATA_PROFILE_OUT=str(directory))
    env['_NT_SYMBOL_PATH'] = str(baseline.BUILD)
    env['STRATA_PROFILE_CPU_MODULES'] = str(SCRIPT/'capture_modules.py')
    env.pop('STRATA_PROFILE_REPLAY',None)
    with (directory/(tag+'.console.log')).open('w') as log:
        process = subprocess.Popen(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            code = process.wait(timeout=900)
        except BaseException:
            if process.poll() is None:
                subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True)
                process.wait(timeout=30)
            raise
    record = {'command':cmd,'exit_code':code,'report_exists':(directory/(tag+'.nsys-rep')).exists()}
    (directory/(tag+'.invocation.json')).write_text(json.dumps(record,indent=2))
    if code or not record['report_exists']:
        raise RuntimeError('CPU profiling failed; inspect '+str(directory/(tag+'.console.log')))
    if tag != 'preflight':
        evidence = json.loads((directory/(tag+'.json')).read_text())
        if not evidence.get('validation_passed'):
            raise RuntimeError('Output validation failed: '+tag)
    print('Captured: '+tag,flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--preflight-only',action='store_true')
    args = parser.parse_args()
    started = datetime.now(ZONE)
    root = REPORTS/('tobeo-'+started.strftime('%Y%m%d'))/'qwen36-profiling'
    number = 1
    while (root/f'cpu-sampling-{number:02d}').exists():
        number += 1
    directory = root/f'cpu-sampling-{number:02d}'
    installed = json.loads((PREVIOUS/'nsight-installed-13.3.1.json').read_text())
    candidates = list(Path(installed['destination']).rglob('nsys.exe'))
    if len(candidates) != 1:
        raise RuntimeError('Expected one matching Nsight CLI')
    nsys = candidates[0]
    if args.dry_run:
        print(json.dumps({'directory':str(directory),'command':command(nsys,directory,'preflight',['--probe'])},indent=2))
        return
    directory.mkdir(parents=True)
    if not (root/'.gitignore').exists():
        (root/'.gitignore').write_text('*\n!.gitignore\n!*.md\n!*.py\n!summary.json\n')
    print('CPU profile archive: '+str(directory),flush=True)
    capture(nsys,directory,'preflight',['--probe'])
    if args.preflight_only:
        return
    state = {'started_at':started.isoformat(),'health_before':baseline.request('/health'),
             'sampling_hz':500,'source_revision':baseline.REVISION,'exe_sha256':baseline.EXPECTED_EXE}
    unloaded = False
    try:
        state['unload'] = baseline.request('/unload?wait=30',post=True)
        if state['unload'].get('status') not in ('unloaded','not loaded'):
            raise RuntimeError('Daily model did not unload')
        unloaded = True
        for case in ['r0-l1024','r0-l16384']:
            tag = case+'-mtp0'
            capture(nsys,directory,tag,['--case',case,'--mtp','0','--cap','64'])
            if case=='r0-l1024':
                measured=json.loads((directory/(tag+'.json')).read_text())
                reference=json.loads((baseline.OUT/'results.json').read_text())['rows']
                ref=next(r for r in reference if r['case']==case and r['mtp']==0)
                if float(measured['done'].split()[3])>3*ref['prompt_ms']:
                    raise RuntimeError('Prompt time differs by >3x historical reference; run a same-day no-profiler control before attribution')
            with (directory/(tag+'.export.log')).open('w') as log:
                subprocess.run([str(nsys),'export','--type=sqlite','--output='+str(directory/(tag+'.sqlite')),
                                str(directory/(tag+'.nsys-rep'))],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
            print('Exported: '+tag,flush=True)
    finally:
        previous = signal.signal(signal.SIGINT,signal.SIG_IGN)
        try:
            if unloaded and state['health_before'].get('loaded'):
                print('Restoring daily model',flush=True)
                state['load'] = baseline.request('/load',post=True)
                state['health_after'] = baseline.request('/health')
                if not state['health_after'].get('loaded'):
                    raise RuntimeError('Daily model failed to restore')
        except BaseException as exc:
            state['restore_error'] = repr(exc)
            raise
        finally:
            state['finished_at'] = datetime.now(ZONE).isoformat()
            (directory/'service-transition.json').write_text(json.dumps(state,indent=2))
            signal.signal(signal.SIGINT,previous)


if __name__ == '__main__':
    main()
