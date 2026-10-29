"""Validate the pinned native build and restore the daily service in finally."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import urllib.request

import psutil
from build_baseline import (OUT, REPO, ROOT, REVISION, SOURCE, BUILD, CUDA, MODEL,
                            MODEL_SHA, digest, git, helper, runtime_env, save, stamp)

DAILY = 'http://127.0.0.1:8080'
CONFIG = REPO / 'strata-iq3_s.json'
FIXTURES = REPO / 'reports/tobeo-20261022/qwen36-context-curve'


def api(path, post=False):
    request = urllib.request.Request(DAILY + path, data=b'{}' if post else None,
                                    headers={'Content-Type': 'application/json', 'Origin': DAILY})
    with urllib.request.urlopen(request, timeout=900 if post else 15) as response:
        return json.load(response)


def audit_processes():
    rows = []
    for process in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            name = (process.info['name'] or '').lower()
            if any(word in name for word in ['python', 'strata', 'curl', 'nsys', 'ncu', 'nvcc', 'ninja']):
                rows.append(process.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', default='validation-01')
    args = parser.parse_args()
    if not re.fullmatch(r'validation-[0-9]+', args.run_id):
        parser.error('Expected validation-NN')
    run = OUT / args.run_id
    run.mkdir(exist_ok=False)
    record = {'started': stamp(), 'phase': 'preflight', 'passed': False, 'rows': [], 'arms': [],
              'revision': REVISION, 'profiler': False, 'restore_errors': [],
              'script_sha256': digest(__file__), 'plan_sha256': digest(OUT / 'experiment-plan.md')}
    persist = lambda: save(run / 'results.json', record)
    unloaded = False
    gate = None
    try:
        persist()
        build = json.loads((OUT / 'build-results.json').read_text(encoding='utf-8'))
        if not build['passed']:
            raise RuntimeError('Build not accepted')
        record['build_results_sha256'] = digest(OUT / 'build-results.json')
        for name, expected in build['binaries'].items():
            if digest(BUILD / name) != expected:
                raise RuntimeError('Binary fingerprint changed: ' + name)
        if git('rev-parse', 'HEAD', cwd=SOURCE) != REVISION or git('status', '--porcelain', '--untracked-files=no', cwd=SOURCE):
            raise RuntimeError('Source identity changed')
        record['model_sha256'] = digest(MODEL)
        if record['model_sha256'] != MODEL_SHA:
            raise RuntimeError('Model fingerprint changed')
        # Eng merges its environment with os.environ, so remove inherited research switches here too.
        for name in list(os.environ):
            if name.upper().startswith(('STRATA_', 'DS4_')):
                del os.environ[name]
        os.environ.update(runtime_env())
        sys.path.insert(0, str(FIXTURES))
        protocol = helper('reports/tobeo-20261022/qwen36-context-curve/run_curve.py', 'baseline_protocol')
        record['protocol_helper_sha256'] = digest(FIXTURES / 'run_curve.py')
        sys.path.insert(0, str(SOURCE / 'tools/qwen35'))
        from q36_harness import Eng
        from windows_telemetry import Telemetry, thread_affinities
        record['harness_sha256'] = digest(SOURCE / 'tools/qwen35/q36_harness.py')
        record['daily_config_sha256_before'] = digest(CONFIG)
        record['health_before'] = api('/health')
        record['processes_before'] = audit_processes()
        conflicts = []
        for item in record['processes_before']:
            words = [Path(arg).name.lower() for arg in item['cmdline'] or []]
            if any(w.startswith('download') and w.endswith('.py') for w in words) or any(
                    word in (item['name'] or '').lower() for word in ['nsys', 'ncu', 'nvcc', 'ninja']):
                conflicts.append(item)
        record['conflicting_jobs'] = conflicts
        if conflicts:
            raise RuntimeError('Other download/build/profiling jobs are active')
        record['hardware'] = subprocess.check_output([
            'nvidia-smi', '--query-gpu=name,uuid,driver_version,memory.total,memory.used,utilization.gpu,pstate',
            '--format=csv,noheader'], text=True).strip()
        record['machine'] = {'platform': sys.platform, 'python': sys.version, 'cpu_logical': psutil.cpu_count(),
                             'memory_total': psutil.virtual_memory().total}
        record['phase'] = 'unloading-daily-model'
        persist()
        record['unload'] = api('/unload?wait=30', True)
        if record['unload'].get('status') not in ['unloaded', 'not loaded']:
            raise RuntimeError('Daily engine busy; could not unload')
        unloaded = True
        persist()
        # Do not contend with an unrelated engine after unloading the known service.
        leftovers = [p for p in audit_processes() if (p['name'] or '').lower() in ['strata.exe', 'strata-q36.exe']]
        if leftovers:
            record['unexpected_engines'] = leftovers
            raise RuntimeError('Unexpected engine still running')

        def bandwidth(label):
            exe = REPO / 'reports/tobeo-20261024/pcie-root-cause/transfer_probe.exe'
            result = subprocess.run([str(exe)], env=runtime_env(), capture_output=True, text=True, timeout=90)
            (run / (label + '.log')).write_text(result.stdout + '\n' + result.stderr, encoding='utf-8')
            match = re.search(r'"test":"pinned_H2D"[^\n]*"event_GBps":([0-9.]+)', result.stdout)
            row = {'exit_code': result.returncode, 'h2d_GBps': float(match.group(1)) if match else None,
                   'exe_sha256': digest(exe)}
            record[label] = row
            persist()
            if result.returncode or row['h2d_GBps'] is None or row['h2d_GBps'] < 15:
                raise RuntimeError('HtoD control failed')

        bandwidth('bandwidth-before')
        record['phase'] = 'fixed-layout-correctness'
        persist()
        fixed = run / 'fixed'
        fixed.mkdir()
        matrix_path = 'reports/tobeo-20261021/qwen36-source-baseline/run_correctness.py'
        matrix = helper(matrix_path, 'baseline_correctness')
        record['correctness_helper_sha256'] = digest(REPO / matrix_path)
        matrix.OUT, matrix.ROOT = fixed, ROOT
        matrix.REVISION, matrix.SOURCE, matrix.BUILD, matrix.CUDA = REVISION, SOURCE, BUILD, CUDA
        matrix.MODEL = MODEL.as_posix()
        matrix.ENVIRONMENT = 'Windows native; MSVC 19.42; CUDA 13.2; sm_120; pinned 46c152a1'

        def native_run(command, name, env, timeout=1200):
            nonlocal gate
            print('GATE', name, flush=True)
            started = time.monotonic()
            with (fixed / (name + '.console.log')).open('w', encoding='utf-8') as log:
                gate = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT,
                                        creationflags=subprocess.CREATE_NO_WINDOW)
                try:
                    code = gate.wait(timeout=timeout)
                except BaseException:
                    subprocess.run(['taskkill', '/PID', str(gate.pid), '/T', '/F'], capture_output=True)
                    raise
            return {'name': name, 'command': command, 'exit_code': code, 'seconds': time.monotonic() - started}

        matrix.run = native_run
        code = matrix.main()
        record['fixed_correctness'] = json.loads((fixed / 'correctness-summary.json').read_text())
        persist()
        if code or not record['fixed_correctness'].get('passed'):
            raise RuntimeError('Fixed-layout gate failed')
        record['phase'] = 'repeatability'
        cases = ['r1-l1024', 'r0-l1024', 'r0-l16384']
        ids = {}
        record['fixtures'] = {}
        for case in cases:
            path = FIXTURES / (case + '.ids.json')
            ids[case] = json.loads(path.read_text())
            save(run / (case + '.ids.json'), ids[case])
            record['fixtures'][case] = {'tokens': len(ids[case]), 'tokens_sha256': protocol.tokens_hash(ids[case]),
                                        'source_file_sha256': digest(path), 'archived_file_sha256': digest(run / (case + '.ids.json'))}
        record['configuration'] = {
            'max_context': 32768, 'prefill': 2048, 'workers': 7, 'mtp': 0, 'expert_budget': 'automatic',
            'fixed_slots': True, 'sampling': protocol.KEYS, 'output_cap': 64, 'warmup_case': 'r1-l1024',
            'environment': {k: v for k, v in runtime_env().items() if k.startswith('STRATA_') or k.startswith('CUDA_')}}
        reference = {}
        expected_slots = None
        for repeat in range(2):
            label = f'repeat-{repeat + 1}'
            print('START', label, flush=True)
            env = runtime_env()
            env['STRATA_Q36_FIXED_SLOTS'] = '1'
            arguments = ['--native', str(MODEL), '--max-context', '32768', '--prefill', '2048', '--pool-workers', '7', '--mtp', '0']
            arm = {'label': label, 'args': arguments, 'started': stamp(), 'log': label + '.engine.log'}
            record['arms'].append(arm)
            persist()
            engine = telemetry = None
            try:
                engine = Eng(str(BUILD / 'strata-q36.exe'), arguments, env=env, log=str(run / arm['log']))
                arm.update(pid=engine.p.pid, load_s=engine.load_s, ready=engine.ready, info=engine.info,
                           thread_affinities=thread_affinities(engine.p.pid))
                arm['warmup'] = protocol.measured_request(engine, ids['r1-l1024'], 64)
                telemetry = Telemetry(engine.p.pid)
                for case in cases[1:]:
                    telemetry.begin()
                    try:
                        row = protocol.measured_request(engine, ids[case], 64)
                    finally:
                        resources = telemetry.end()
                    row.update(label=label, case=case, resources=resources)
                    row['protocol_passed'] = row['reused_tokens'] == row['draft_offered'] == 0 and row['generated_tokens'] == 64 and row['finish'] == 'length'
                    if repeat == 0:
                        reference[case] = row['output_ids']
                    row['matches_first_repeat'] = row['output_ids'] == reference[case]
                    record['rows'].append(row)
                    persist()
                    if not row['protocol_passed'] or not row['matches_first_repeat']:
                        raise RuntimeError('Repeatability/count/freshness failed')
            finally:
                if telemetry:
                    telemetry.close()
                if engine:
                    engine.close()
                    if engine.p.poll() is None:
                        engine.p.kill()
                        engine.p.wait(timeout=30)
                    arm['exit_code'] = engine.p.returncode
                text = (run / arm['log']).read_text(errors='replace') if (run / arm['log']).exists() else ''
                arm['slots'] = [int(n) for n in re.findall(r'hybrid experts: (\d+) of 256 per layer', text)]
                arm['chunks'] = [int(n) for n in re.findall(r'context 32768 cells, prompt chunk (\d+)', text)]
                arm['slot_replacements'] = [int(n) for n in re.findall(r'(\d+) slot replacements', text)]
                arm['placement_lines'] = [line for line in text.splitlines() if any(s in line for s in ['hybrid experts:', 'packed Q8', 'K-quant', 'Graph', 'graph', 'prompt chunk'])]
                arm['finished'] = stamp()
                persist()
            if arm.get('exit_code') != 0 or len(arm['slots']) != 1 or arm['chunks'] != [2048]:
                raise RuntimeError('Unexpected exit or layout')
            if not arm['slot_replacements'] or any(arm['slot_replacements']):
                raise RuntimeError('Frozen layout replacement gate failed')
            if expected_slots is None:
                expected_slots = arm['slots']
            if arm['slots'] != expected_slots:
                raise RuntimeError('Placement changed between repeats')
        bandwidth('bandwidth-after')
        record['tracked_changes_after'] = git('status', '--porcelain', '--untracked-files=no', cwd=SOURCE)
        if record['tracked_changes_after'] or any(digest(BUILD / name) != sha for name, sha in build['binaries'].items()):
            raise RuntimeError('Source or binary changed during validation')
        record['phase'] = 'complete'
        record['passed'] = True
    except BaseException as exc:
        record['error'] = repr(exc)
        record['phase'] = 'failed'
        persist()
        raise
    finally:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            if gate and gate.poll() is None:
                subprocess.run(['taskkill', '/PID', str(gate.pid), '/T', '/F'], capture_output=True)
            for child in psutil.Process().children(recursive=True):
                try:
                    if Path(child.exe()).resolve() == (BUILD / 'strata-q36.exe').resolve():
                        child.kill()
                        child.wait(timeout=30)
                except psutil.NoSuchProcess:
                    pass
            if unloaded and record['health_before'].get('loaded'):
                record['daily_restore'] = api('/load', True)
                record['health_after'] = api('/health')
                if not record['health_after'].get('loaded') or record['health_after'].get('model') != record['health_before'].get('model'):
                    raise RuntimeError('Daily service did not restore original model')
        except BaseException as exc:
            record['restore_errors'].append(repr(exc))
        if 'daily_config_sha256_before' in record:
            record['daily_config_sha256_after'] = digest(CONFIG)
            if record['daily_config_sha256_before'] != record['daily_config_sha256_after']:
                record['restore_errors'].append('Daily config changed')
        if record['restore_errors']:
            record['passed'] = False
        record['finished'] = stamp()
        persist()
        print(json.dumps({k: record.get(k) for k in ['phase', 'passed', 'restore_errors', 'finished']}), flush=True)


if __name__ == '__main__':
    main()
