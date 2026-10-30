"""Same-day unprofiled controls and four pinned-engine CUDA/NVTX traces."""
import argparse
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time

import psutil
from common import (OUT, BASE, BUILD, MODEL, MODEL_SHA, NSYS, NSYS_MANIFEST, CONFIG,
                    REVISION, api, check_identity, digest, save, stamp, environment, bandwidth, git)
from validate_baseline import audit_processes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', default='capture-01')
    args = parser.parse_args()
    import re
    if not re.fullmatch(r'capture-[0-9]+', args.run_id):
        parser.error('Expected capture-NN')
    directory = OUT / args.run_id
    directory.mkdir(exist_ok=False)
    record = {'started': stamp(), 'passed': False, 'phase': 'preflight', 'revision': REVISION,
              'commands': [], 'cells': [], 'restore_errors': [],
              'scripts': {name: digest(OUT / name) for name in ['common.py', 'capture_request.py', 'run_systems.py']},
              'plan_sha256': digest(OUT / 'experiment-plan.md')}
    persist = lambda: save(directory / 'results.json', record)
    unloaded = False
    active = None
    persist()

    def execute(command, label, timeout=600):
        nonlocal active
        print('RUN', label, flush=True)
        row = {'label': label, 'command': command, 'started': stamp()}
        record['commands'].append(row)
        persist()
        started = time.monotonic()
        with (directory / (label + '.console.log')).open('w', encoding='utf-8') as log:
            active = subprocess.Popen(command, env=environment(), stdout=log, stderr=subprocess.STDOUT,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                code = active.wait(timeout=timeout)
            except BaseException:
                subprocess.run(['taskkill', '/PID', str(active.pid), '/T', '/F'], capture_output=True)
                raise
        row.update(exit_code=code, seconds=time.monotonic()-started, finished=stamp())
        persist()
        if code:
            raise RuntimeError(label + ' failed; inspect retained log')

    def profile_command(tag, extra):
        return [str(NSYS), 'profile', '--trace=cuda,nvtx', '--sample=none', '--cpuctxsw=none',
                '--cuda-graph-trace=node', '--kill=false', '--wait=all', '--output=' + str(directory / tag),
                sys.executable, str(OUT / 'capture_request.py'), '--directory', str(directory), *extra]

    def export(tag):
        if not (directory / (tag + '.nsys-rep')).exists():
            raise RuntimeError('Nsight report missing')
        execute([str(NSYS), 'export', '--type=sqlite', '--output=' + str(directory / (tag + '.sqlite')),
                 str(directory / (tag + '.nsys-rep'))], tag + '-export', 300)

    try:
        ref = check_identity()
        record['baseline_summary_sha256'] = digest(BASE / 'summary.json')
        record['binaries'] = ref['binaries']
        record['nsys'] = {'exe': str(NSYS), 'sha256': digest(NSYS), 'manifest_sha256': digest(NSYS_MANIFEST)}
        for label, command in [('nsys-version', [str(NSYS), '--version']),
                               ('nsys-environment', [str(NSYS), 'status', '--environment'])]:
            result = subprocess.run(command, capture_output=True)
            (directory / (label + '.log')).write_bytes(result.stdout + result.stderr)
            record['nsys'][label] = {'exit_code': result.returncode,
                                    'output': (result.stdout + result.stderr).decode('utf-8', errors='replace')}
        execute(profile_command('preflight', ['--probe']), 'preflight')
        export('preflight')
        with sqlite3.connect(directory / 'preflight.sqlite') as database:
            ranges = database.execute("select start,end from NVTX_EVENTS where text='preflight-range'").fetchall()
            if len(ranges) != 1 or ranges[0][1] is None:
                raise RuntimeError('NVTX preflight range missing or unclosed')
        record['nvtx_preflight_passed'] = True
        record['model_sha256'] = digest(MODEL)
        if record['model_sha256'] != MODEL_SHA:
            raise RuntimeError('Model checksum changed')
        record['daily_config_sha256_before'] = digest(CONFIG)
        record['health_before'] = api('/health')
        record['processes_before'] = audit_processes()
        conflicts = []
        for item in record['processes_before']:
            words = [Path(arg).name.lower() for arg in item['cmdline'] or []]
            if any(w.startswith('download') and w.endswith('.py') for w in words) or any(
                    term in (item['name'] or '').lower() for term in ['nsys', 'ncu', 'nvcc', 'ninja']):
                conflicts.append(item)
        record['conflicting_jobs'] = conflicts
        if conflicts:
            raise RuntimeError('Other download/build/profiling jobs active')
        record['hardware'] = subprocess.check_output(['nvidia-smi', '--query-gpu=name,driver_version,memory.total,memory.used,utilization.gpu,pstate',
                                                       '--format=csv,noheader'], text=True).strip()
        record['phase'] = 'releasing-daily-model'
        persist()
        record['unload'] = api('/unload?wait=30', True)
        if record['unload'].get('status') not in ['unloaded', 'not loaded']:
            raise RuntimeError('Daily model busy')
        unloaded = True
        leftovers = [p for p in audit_processes() if (p['name'] or '').lower() in ['strata.exe', 'strata-q36.exe']]
        if leftovers:
            record['unexpected_engines'] = leftovers
            raise RuntimeError('Unexpected engine still running')
        record['bandwidth-before'] = bandwidth(directory, 'bandwidth-before')
        persist()
        for chunk in [2048, 4096]:
            for case in ['r0-l1024', 'r0-l16384']:
                tag = f'c{chunk}-{case}'
                record['phase'] = tag
                cell = {'chunk': chunk, 'case': case, 'tag': tag}
                record['cells'].append(cell)
                persist()
                extra = ['--case', case, '--chunk', str(chunk)]
                execute([sys.executable, str(OUT / 'capture_request.py'), '--directory', str(directory), *extra], tag + '-plain')
                plain = json.loads((directory / (tag + '-plain.json')).read_text(encoding='utf-8'))
                if not plain['passed']:
                    raise RuntimeError('Unprofiled reference invalid')
                cell['plain_passed'] = True
                execute(profile_command(tag + '-trace', [*extra, '--profiler']), tag + '-trace')
                trace = json.loads((directory / (tag + '-trace.json')).read_text(encoding='utf-8'))
                if not trace['passed'] or trace['layout']['slots'] != plain['layout']['slots']:
                    raise RuntimeError('Capture identity/layout invalid')
                cell.update(trace_passed=True, actual_slots=trace['layout']['slots'],
                            trace_to_plain_prompt_ratio=trace['prompt_ms']/plain['prompt_ms'],
                            trace_to_plain_decode_ratio=trace['decode_ms']/plain['decode_ms'])
                persist()
                if max(cell['trace_to_plain_prompt_ratio'], cell['trace_to_plain_decode_ratio']) > 3:
                    record['bandwidth-on-timing-stop'] = bandwidth(directory, 'bandwidth-on-timing-stop')
                    raise RuntimeError('Profiler time >3x same-day control; stop and diagnose')
                export(tag + '-trace')
        record['bandwidth-after'] = bandwidth(directory, 'bandwidth-after')
        check_identity()
        record['phase'] = 'complete'
        record['passed'] = True
    except BaseException as exc:
        record['phase'] = 'failed'
        record['error'] = repr(exc)
        persist()
        raise
    finally:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            if active and active.poll() is None:
                subprocess.run(['taskkill', '/PID', str(active.pid), '/T', '/F'], capture_output=True)
            for child in psutil.Process().children(recursive=True):
                try:
                    if Path(child.exe()).resolve() == (BUILD / 'strata-q36.exe').resolve():
                        child.kill()
                        child.wait(timeout=30)
                except psutil.NoSuchProcess:
                    pass
            if unloaded and record['health_before'].get('loaded'):
                print('Restoring daily service', flush=True)
                record['restore'] = api('/load', True)
                record['health_after'] = api('/health')
                if not record['health_after'].get('loaded') or record['health_after']['model'] != record['health_before']['model']:
                    raise RuntimeError('Daily model restore failed')
        except BaseException as exc:
            record['restore_errors'].append(repr(exc))
        if 'daily_config_sha256_before' in record:
            record['daily_config_sha256_after'] = digest(CONFIG)
            if record['daily_config_sha256_after'] != record['daily_config_sha256_before']:
                record['restore_errors'].append('Daily config changed')
        if record['restore_errors']:
            record['passed'] = False
        record['finished'] = stamp()
        persist()
        print(json.dumps({k: record.get(k) for k in ['phase', 'passed', 'restore_errors', 'finished']}), flush=True)


if __name__ == '__main__':
    main()
