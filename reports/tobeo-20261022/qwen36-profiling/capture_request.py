"""Run one phase-B request with NVTX ranges; launched by Nsight, not standalone.

Torch supplies only its installed CPU-side NVTX binding. The model runs in the
unchanged native Strata child process. No torch tensor or CUDA context is created.
The decode range starts after the first token reaches the protocol client, so its
boundary is a client observation, not an exact engine/kernel phase boundary.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

SCRIPT_DIR = Path(__file__).resolve().parent
OUT = Path(os.environ.get('STRATA_PROFILE_OUT', SCRIPT_DIR))
BASE = SCRIPT_DIR.parent / 'qwen36-context-curve'
sys.path.insert(0, str(BASE))
import run_curve as baseline


def replay_directory(root):
    index = 1
    while True:
        directory = root / f'pass-{index:04d}'
        try:
            directory.mkdir()
            return directory
        except FileExistsError:
            index += 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', action='store_true')
    parser.add_argument('--case', choices=['r0-l1024', 'r0-l16384'])
    parser.add_argument('--mtp', type=int, choices=[0, 2], default=0)
    parser.add_argument('--cap', type=int, choices=[64, 256], default=256)
    args = parser.parse_args()
    from torch.cuda.nvtx import range_push, range_pop
    if args.probe:
        range_push('request')
        range_push('decode-after-first-token')
        time.sleep(0.05)
        range_pop()
        range_pop()
        print('NVTX probe finished', flush=True)
        return
    if not args.case:
        parser.error('--case is required for model capture')
    global OUT
    if os.environ.get('STRATA_PROFILE_REPLAY') == 'application':
        # ncu reruns this controller for every application replay pass.
        # Preserve every pass separately; never reuse an earlier validation.
        OUT = replay_directory(OUT)
        print('Application replay evidence: '+str(OUT),flush=True)
    if baseline.request('/health').get('loaded'):
        raise RuntimeError('Release the daily model through run_profiling.py before capture')
    if baseline.digest(baseline.EXE) != baseline.EXPECTED_EXE:
        raise RuntimeError('Baseline binary hash changed')
    sys.path.insert(0, str(baseline.SOURCE / 'tools/qwen35'))
    from q36_harness import Eng
    tag = args.case + '-mtp' + str(args.mtp)
    result_path = OUT / (tag + '.json')
    if result_path.exists():
        raise RuntimeError('Capture evidence exists; use a new archive instead of overwriting')
    env = {k: v for k, v in os.environ.items() if not k.startswith('STRATA_')}
    env.update(baseline.ENV)
    env['PATH'] = os.pathsep.join([str(baseline.CUDA / 'bin/x64'), str(baseline.CUDA / 'bin'),
                                   str(baseline.BUILD), env.get('PATH', '')])
    engine = None
    try:
        print('Stage: loading native engine',flush=True)
        engine = Eng(str(baseline.EXE), ['--native', str(baseline.MODEL), '--max-context', '32768',
                     '--prefill', '512', '--pool-workers', '7', '--expert-vram', '10.0',
                     '--expert-slots', '64', '--mtp', str(args.mtp)], env=env,
                     log=str(OUT / (tag + '.engine.log')))
        print(f'Stage: engine ready ({engine.load_s:.1f}s); warming up 64 tokens',flush=True)
        if os.environ.get('STRATA_PROFILE_CPU_MODULES'):
            import importlib.util
            spec = importlib.util.spec_from_file_location('cpu_modules',os.environ['STRATA_PROFILE_CPU_MODULES'])
            helper = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(helper)
            (OUT/(tag+'.modules.json')).write_text(json.dumps({'pid':engine.p.pid,'modules':helper.modules(engine.p.pid)},indent=2))
        warm_ids = json.loads((BASE / 'r1-l1024.ids.json').read_text())
        warmup = baseline.measured_request(engine, warm_ids, cap=64)
        print('Stage: warm-up complete; starting measured request '+tag,flush=True)
        ids = json.loads((BASE / (args.case + '.ids.json')).read_text())
        output = []
        range_push('request')
        try:
            range_push('prefill-to-first-token')
            try:
                started = time.perf_counter()
                first = None
                engine.send('GEN ' + str(args.cap) + ' ' + baseline.KEYS + ' ' + ','.join(map(str, ids)))
                while True:
                    line = engine.line(300)
                    if line is None or line.startswith('ERR'):
                        raise RuntimeError(f'Engine failed: {line}')
                    if line.startswith('T '):
                        if first is None:
                            first = time.perf_counter()
                            range_pop()
                            range_push('decode-after-first-token')
                        output.append(int(line.split()[1]))
                        if len(output) == 1 or len(output) % 16 == 0:
                            print(f'Stage: measured request {len(output)}/{args.cap} tokens',flush=True)
                    elif line.startswith('DONE '):
                        done = line
                        break
            finally:
                range_pop()
            ended = time.perf_counter()
        finally:
            range_pop()
        fields = done.split()
        refs = json.loads((BASE / 'results.json').read_text())
        ref = next(r for r in refs['rows'] if r['case'] == args.case and r['mtp'] == args.mtp)
        result = {'case': args.case, 'mtp': args.mtp, 'profiler': True, 'done': done,
                  'source_revision': baseline.REVISION, 'exe_sha256': baseline.EXPECTED_EXE,
                  'sampling_protocol': baseline.KEYS,
                  'output_ids': output, 'output_sha256': baseline.tokens_hash(output),
                  'prompt_ids_sha256': baseline.tokens_hash(ids), 'warmup': warmup,
                  'client_ttft_s': first - started if first else None,
                  'client_total_s': ended - started, 'load_s': engine.load_s,
                  'generated_tokens': len(output), 'reference_prefix_tokens': args.cap,
                  'same_output_as_phase_b': output == ref['output_ids'][:args.cap]}
        result['validation'] = {
            'counts': len(output) == int(fields[1]) == args.cap and int(fields[2]) == len(ids),
            'fresh': int(fields[8]) == 0 and int(fields[14]) == len(ids),
            'mtp': (int(fields[7]) > 0) == (args.mtp == 2),
            'finish_length': fields[5] == 'length',
            'baseline_prefix': result['same_output_as_phase_b']}
        result['validation']['input_hash'] = result['prompt_ids_sha256'] == ref['prompt_ids_sha256']
        result['validation_passed'] = all(result['validation'].values())
        result_path.write_text(json.dumps(result, indent=2))
        if not result['validation_passed']:
            raise RuntimeError('Capture validation failed: ' + str(result['validation']))
        print('Capture request complete:', tag, flush=True)
    finally:
        if engine:
            engine.close()


if __name__ == '__main__':
    main()
