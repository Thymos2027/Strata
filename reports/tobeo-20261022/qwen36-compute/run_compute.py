"""Check real counter access, collect two isolated kernels, restore the daily model.

Use --dry-run to inspect exact commands without unloading the model. Counter
collection defaults to application replay with flushed caches; clocks remain uncontrolled.
These reports are diagnostic data, not ordinary end-to-end performance samples.
"""
import argparse
import atexit
import csv
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
sys.path.insert(0,str(OUT.parent/'qwen36-context-curve'))
import run_curve as baseline

SECTIONS = ['LaunchStats','SpeedOfLight','MemoryWorkloadAnalysis','MemoryWorkloadAnalysis_Tables',
            'SchedulerStats','WarpStateStats','Occupancy']
SMOKE_METRICS = ['gpu__time_duration.sum','dram__bytes_op_read.sum','dram__bytes_op_write.sum']
SHANGHAI = timezone(timedelta(hours=8),'Asia/Shanghai')


def archive_root(started):
    return OUT.parents[1]/('tobeo-'+started.astimezone(SHANGHAI).strftime('%Y%m%d'))/'qwen36-compute'


def finish_timing(run_dir,timing):
    if 'finished_at' not in timing:
        timing['finished_at'] = datetime.now(SHANGHAI).isoformat()
        (run_dir/'timing.json').write_text(json.dumps(timing,indent=2))


def evidence_exists(run_id,root=OUT):
    return (root/run_id).exists() or any(root.glob('counter-probe-'+run_id+'.*'))


def next_run_id(prefix='mtp0-application-smoke',root=OUT):
    number = 1
    while evidence_exists(f'{prefix}-{number:02d}',root):
        number += 1
    return f'{prefix}-{number:02d}'


def wait_for_capture(process, directory, timeout):
    started = time.monotonic()
    while True:
        elapsed = time.monotonic()-started
        remaining = timeout-elapsed
        if remaining <= 0:
            raise subprocess.TimeoutExpired(process.args,timeout)
        try:
            return process.wait(timeout=min(30,remaining))
        except subprocess.TimeoutExpired:
            lines = (directory/'capture.log').read_text(errors='replace').splitlines()
            latest = next((line for line in reversed(lines) if line.strip()),'(waiting for child output)')
            print(f'[{directory.name}] {time.monotonic()-started:.0f}/{timeout}s: {latest}',flush=True)


def command(ncu,selection,case,directory,replay_mode='application',scope='smoke'):
    cmd = [ncu,'--target-processes','all','--kernel-name-base','function',
           '--kernel-name',selection['kernel_name'],'--launch-skip',str(selection['launch_skip']),
           '--launch-count','1','--replay-mode',replay_mode,'--cache-control','all','--clock-control','none',
           '--export',str(directory/'attention')]
    if replay_mode == 'application':
        cmd.extend(['--app-replay-match','grid','--app-replay-mode','strict'])
    if scope == 'smoke':
        cmd.extend(['--metrics',','.join(SMOKE_METRICS)])
    else:
        for section in SECTIONS:
            cmd.extend(['--section',section])
    return cmd+[sys.executable,str(OUT.parent/'qwen36-profiling/capture_request.py'),
                '--case',case,'--mtp','0','--cap','64']


def validate_export(raw_csv,selected,scope):
    lines = raw_csv.splitlines()
    start = next(i for i,line in enumerate(lines) if line.startswith('"ID"') or line.startswith('ID,'))
    # This CLI exports one wide row per kernel, preceded by a units row.
    exported = list(csv.DictReader(io.StringIO('\n'.join(lines[start:]))))
    units = next((r for r in exported if not r.get('ID','')), {})
    rows = [r for r in exported if r.get('ID','').isdigit()]
    if len(rows) != 1 or 'k_attn_part' not in rows[0].get('Kernel Name',''):
        raise RuntimeError('Expected exactly one target kernel in the raw export')
    row = rows[0]
    for label,prefix in [('Grid Size','grid'),('Block Size','block')]:
        shape = tuple(map(int,re.findall(r'\d+',row[label])))
        expected = tuple(selected[prefix+axis] for axis in 'XYZ')
        if shape != expected:
            raise RuntimeError(f'Unexpected {label}: {shape}; expected {expected}')
    if float(row.get('gpu__time_duration.sum','nan').replace(',','')) <= 0:
        raise RuntimeError('Nonpositive kernel duration; report is not a valid measurement')
    import math
    for metric in SMOKE_METRICS:
        value = float(row.get(metric,'nan').replace(',',''))
        if not math.isfinite(value) or value < 0:
            raise RuntimeError('Missing/invalid hardware metric: '+metric)
    return {'one_kernel':True,'shape_matches':True,'scope':scope,
            'metrics':{k:row[k] for k in SMOKE_METRICS},
            'metric_units':{k:units.get(k,'unknown') for k in SMOKE_METRICS},
            'note':'Smoke metrics do not establish L2, stalls or occupancy; full sections require further review.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--run-id',help='Optional fresh evidence ID; otherwise choose the next unused ID')
    parser.add_argument('--capture-timeout',type=int,default=3600,
                        help='Maximum seconds per context capture, including load and warm-up (default: 3600)')
    parser.add_argument('--replay-mode',choices=['application','kernel'],default='application')
    parser.add_argument('--scope',choices=['smoke','full'],default='smoke')
    parser.add_argument('--case',choices=['r0-l1024','r0-l16384','both'],default='r0-l1024')
    args = parser.parse_args()
    started = datetime.now(SHANGHAI)
    run_root = archive_root(started)
    if args.capture_timeout <= 0:
        parser.error('--capture-timeout must be positive')
    args.run_id = args.run_id or next_run_id('mtp0-'+args.replay_mode+'-'+args.scope,run_root)
    if not re.fullmatch(r'[a-zA-Z0-9-]+',args.run_id):
        parser.error('--run-id must contain letters, numbers and hyphens')
    if evidence_exists(args.run_id,run_root):
        parser.error('Evidence exists for '+args.run_id+'; omit --run-id to choose a fresh ID')
    installed = json.loads((OUT/'compute-installed.json').read_text())
    selection = json.loads((OUT/'kernel-selection.json').read_text())
    run_dir = run_root/args.run_id
    plans = [{'case':c['case'],'expected_shape':c['selected'],
              'command':command(installed['command'],selection,c['case'],run_dir/c['case'],args.replay_mode,args.scope)}
             for c in selection['cases'] if args.case == 'both' or c['case'] == args.case]
    if args.dry_run:
        print(json.dumps({'run_directory':str(run_dir),'capture_timeout_s':args.capture_timeout,
                          'plans':plans},indent=2)); return
    # Reserve the attempt before the probe. Failed preflights are attempts too.
    run_root.mkdir(parents=True,exist_ok=True)
    if not (run_root/'.gitignore').exists():
        (run_root/'.gitignore').write_text('*\n!.gitignore\n!*.md\n!summary.json\n')
    run_dir.mkdir()
    timing = {'started_at':started.isoformat(),'timezone':'Asia/Shanghai',
              'archive_date':started.strftime('%Y-%m-%d'),'script_directory':str(OUT)}
    (run_dir/'timing.json').write_text(json.dumps(timing,indent=2))
    atexit.register(finish_timing,run_dir,timing)
    (run_dir/'plan.json').write_text(json.dumps(plans,indent=2))
    (run_dir/'settings.json').write_text(json.dumps({'capture_timeout_s':args.capture_timeout,
        'replay_mode':args.replay_mode,'scope':args.scope,'case':args.case},indent=2))
    print('Run ID: '+args.run_id+'; evidence: '+str(run_dir),flush=True)
    # Do this before any service change. A successful CUDA application alone is
    # insufficient: the probe must actually collect a hardware metric.
    probe_tag = 'counter-probe-'+args.run_id
    probe = subprocess.run([sys.executable,str(OUT/'probe_counters.py'),'--tag',probe_tag,
                            '--output-dir',str(run_root)])
    if probe.returncode:
        timing['finished_at'] = datetime.now(SHANGHAI).isoformat()
        (run_dir/'timing.json').write_text(json.dumps(timing,indent=2))
        raise SystemExit('Counter preflight failed; inspect '+str(run_root/(probe_tag+'.status.json'))+
                         ' and its console log. Daily model was not unloaded.')
    status = json.loads((run_root/(probe_tag+'.status.json')).read_text())
    if status['permission_denied'] or not status['report_exists'] or status['exit_code']:
        raise RuntimeError('Hardware counters are unavailable')
    if baseline.digest(baseline.EXE) != baseline.EXPECTED_EXE:
        raise RuntimeError('Baseline binary changed')
    state = {'health_before':baseline.request('/health')}
    unloaded = False
    try:
        state['unload'] = baseline.request('/unload?wait=30',post=True)
        if state['unload'].get('status') not in ('unloaded','not loaded'):
            raise RuntimeError('Daily model did not release VRAM')
        unloaded = True
        for plan in plans:
            directory = run_dir/plan['case']
            directory.mkdir()
            env = dict(os.environ,STRATA_PROFILE_OUT=str(directory),STRATA_PROFILE_REPLAY=args.replay_mode)
            print('Starting '+plan['case']+f'; timeout {args.capture_timeout}s; log: '+
                  str(directory/'capture.log'),flush=True)
            with (directory/'capture.log').open('w') as log:
                process = subprocess.Popen(plan['command'],env=env,stdout=log,stderr=subprocess.STDOUT)
                try:
                    exit_code = wait_for_capture(process,directory,args.capture_timeout)
                except BaseException as exc:
                    (directory/'failure.json').write_text(json.dumps({'error':repr(exc),
                        'capture_timeout_s':args.capture_timeout},indent=2))
                    if process.poll() is None:
                        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True)
                        process.wait(timeout=30)
                    raise
            if exit_code:
                lines = (directory/'capture.log').read_text(errors='replace').splitlines()
                errors = [line for line in lines if '==ERROR==' in line]
                failure = {'exit_code':exit_code,'errors':errors,'report_accepted':False}
                (directory/'failure.json').write_text(json.dumps(failure,indent=2))
                raise RuntimeError('NCU failed: '+plan['case']+'; '+('; '.join(errors[-3:]) or 'inspect capture.log'))
            evidence_paths = [p/(plan['case']+'-mtp0.json') for p in sorted(directory.glob('pass-*')) if p.is_dir()] if args.replay_mode == 'application' else [directory/(plan['case']+'-mtp0.json')]
            if not evidence_paths or any(not p.exists() or not json.loads(p.read_text()).get('validation_passed') for p in evidence_paths):
                raise RuntimeError('Missing or failed per-pass output/protocol validation')
            report = directory/'attention.ncu-rep'
            if not report.exists():
                raise RuntimeError('NCU report missing')
            exported = subprocess.run([installed['command'],'--import',str(report),'--page','raw','--csv',
                                       '--print-units','base'],
                                      capture_output=True,text=True,check=True)
            (directory/'metrics.csv').write_text(exported.stdout,encoding='utf-8')
            (directory/'export.stderr.log').write_text(exported.stderr,encoding='utf-8')
            checked = validate_export(exported.stdout,plan['expected_shape'],args.scope)
            checked['validated_application_passes'] = len(evidence_paths)
            (directory/'export-check.json').write_text(json.dumps(checked,indent=2))
            print('Collected:',plan['case'],flush=True)
    finally:
        # A second console interrupt must not abort the service restoration.
        previous_sigint = signal.signal(signal.SIGINT,signal.SIG_IGN)
        try:
            if unloaded and state['health_before'].get('loaded'):
                print('Restoring daily model; please wait for the health check.',flush=True)
                state['load'] = baseline.request('/load',post=True)
                state['health_after'] = baseline.request('/health')
                if not state['health_after'].get('loaded'):
                    raise RuntimeError('Daily model failed to restore')
        except BaseException as exc:
            state['restore_error'] = repr(exc); raise
        finally:
            try:
                (run_dir/'service-transition.json').write_text(json.dumps(state,indent=2))
                timing['finished_at'] = datetime.now(SHANGHAI).isoformat()
                (run_dir/'timing.json').write_text(json.dumps(timing,indent=2))
            finally:
                signal.signal(signal.SIGINT,previous_sigint)


if __name__ == '__main__':
    main()
