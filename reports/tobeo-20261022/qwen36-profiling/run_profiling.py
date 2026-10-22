"""Preflight Nsight, capture four requests, and restore the original local service.

All report files are local and ignored. Does not change the engine or driver.
Preflight runs without unloading the daily model. Requires a functioning Windows
Nsight CLI session; see README for any measured permission limitation.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

OUT = Path(__file__).resolve().parent
SCRIPT_DIR = OUT
sys.path.insert(0, str(OUT.parent / 'qwen36-context-curve'))
import run_curve as baseline


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2))


def command(nsys, tag, extra):
    return [str(nsys), 'profile', '--trace=cuda,nvtx', '--sample=none', '--cpuctxsw=none',
            '--cuda-graph-trace=node', '--kill=false', '--output=' + str(OUT / tag),
            sys.executable, str(SCRIPT_DIR / 'capture_request.py'), *extra]


def run(nsys, tag, extra):
    if any((OUT / (tag + suffix)).exists() for suffix in ('.nsys-rep', '.json', '.invocation.json', '.console.log')):
        raise RuntimeError('Existing evidence for ' + tag + '; use a new archive')
    cmd = command(nsys, tag, extra)
    env = dict(os.environ, NSYS_NVTX_PROFILER_REGISTER_ONLY='0', STRATA_PROFILE_OUT=str(OUT))
    with (OUT / (tag + '.console.log')).open('w') as log:
        p = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, timeout=600)
    record = {'command': cmd, 'exit_code': p.returncode,
              'report_exists': (OUT / (tag + '.nsys-rep')).exists()}
    save(tag + '.invocation.json', record)
    print(tag, record['exit_code'], 'report:', record['report_exists'], flush=True)
    if p.returncode or not record['report_exists']:
        raise RuntimeError('Nsight did not produce a report; inspect ' + tag + '.console.log')
    if not tag.startswith('preflight'):
        result = json.loads((OUT / (tag + '.json')).read_text())
        if not result.get('validation_passed'):
            raise RuntimeError('Capture request validation did not pass: ' + tag)


def main():
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument('--preflight-only', action='store_true')
    parser.add_argument('--preflight-tag', default='preflight')
    parser.add_argument('--archive-dir', default='cuda133-process')
    parser.add_argument('--tool-manifest', default='nsight-installed-13.3.1.json')
    args = parser.parse_args()
    if not re.fullmatch(r'preflight(?:-[0-9]+)?', args.preflight_tag):
        parser.error('--preflight-tag must be preflight or preflight-N')
    OUT = SCRIPT_DIR / args.archive_dir
    OUT.mkdir(parents=True, exist_ok=True)
    installed = json.loads((SCRIPT_DIR / args.tool_manifest).read_text())
    candidates = list(Path(installed['destination']).rglob('nsys.exe'))
    if len(candidates) != 1:
        raise RuntimeError(f'Expected one CLI, got {candidates}')
    nsys = candidates[0]
    tag = args.preflight_tag
    previous = OUT / (tag + '.invocation.json')
    if previous.exists():
        record = json.loads(previous.read_text())
        if (record['exit_code'] != 0 or not (OUT / (tag + '.nsys-rep')).exists()
                or record['command'] != command(nsys, tag, ['--probe'])):
            raise RuntimeError('Preserve previous preflight evidence; retry using --preflight-tag preflight-2')
        print('Reusing successful preflight:', tag, flush=True)
    else:
        run(nsys, tag, ['--probe'])
    if args.preflight_only:
        return
    state = {'health_before': baseline.request('/health')}
    unloaded = False
    try:
        state['unload'] = baseline.request('/unload?wait=30', post=True)
        if state['unload'].get('status') not in ('unloaded', 'not loaded'):
            raise RuntimeError('Daily model did not unload')
        unloaded = True
        for mtp in (0, 2):
            for case in ('r0-l1024', 'r0-l16384'):
                run(nsys, case + '-mtp' + str(mtp), ['--case', case, '--mtp', str(mtp), '--cap', '64'])
    finally:
        try:
            if unloaded and state['health_before'].get('loaded'):
                state['load'] = baseline.request('/load', post=True)
                state['health_after'] = baseline.request('/health')
                if not state['health_after'].get('loaded'):
                    raise RuntimeError('Original service failed to restore')
        except BaseException as exc:
            state['restore_error'] = repr(exc)
            raise
        finally:
            save('service-transition.json', state)


if __name__ == '__main__':
    main()
