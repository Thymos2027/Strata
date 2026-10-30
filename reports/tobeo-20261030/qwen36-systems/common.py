"""Pinned identities shared by the new driver and its captured child."""
from pathlib import Path
import json
import re
import subprocess
import sys
import urllib.request

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[2]
BASE = REPO / 'reports/tobeo-20261029/qwen36-repro-baseline'
sys.path.insert(0, str(BASE))
from build_baseline import REVISION, SOURCE, BUILD, CUDA, MODEL, MODEL_SHA, digest, save, stamp, runtime_env, git

FIXTURES = REPO / 'reports/tobeo-20261022/qwen36-context-curve'
sys.path.insert(0, str(FIXTURES))
import run_curve as protocol
sys.path.insert(0, str(SOURCE / 'tools/qwen35'))
from q36_harness import Eng

NSYS_MANIFEST = REPO / 'reports/tobeo-20261022/qwen36-profiling/nsight-installed-13.3.1.json'
NSYS = next(Path(json.loads(NSYS_MANIFEST.read_text(encoding='utf-8'))['destination']).rglob('nsys.exe'))
CONFIG = REPO / 'strata-iq3_s.json'
DAILY = 'http://127.0.0.1:8080'


def api(path, post=False):
    request = urllib.request.Request(DAILY + path, data=b'{}' if post else None,
                                    headers={'Content-Type': 'application/json', 'Origin': DAILY})
    with urllib.request.urlopen(request, timeout=900 if post else 15) as response:
        return json.load(response)


def environment():
    env = runtime_env()
    env['STRATA_Q36_FIXED_SLOTS'] = '1'
    env['NSYS_NVTX_PROFILER_REGISTER_ONLY'] = '0'
    return env


def arguments(chunk):
    return ['--native', str(MODEL), '--max-context', '32768', '--prefill', str(chunk),
            '--pool-workers', '7', '--mtp', '0']


def layout(log):
    text = Path(log).read_text(encoding='utf-8', errors='replace')
    return {'slots': [int(n) for n in re.findall(r'hybrid experts: (\d+) of 256 per layer', text)],
            'chunks': [int(n) for n in re.findall(r'context 32768 cells, prompt chunk (\d+)', text)],
            'slot_replacements': [int(n) for n in re.findall(r'(\d+) slot replacements', text)],
            'placement_lines': [line for line in text.splitlines() if any(s in line for s in
                                ['hybrid experts:', 'packed Q8', 'prompt chunk', 'K-quant', 'Graph', 'graph'])]}


def check_identity():
    ref = json.loads((BASE / 'summary.json').read_text(encoding='utf-8'))
    if not ref['passed'] or git('rev-parse', 'HEAD', cwd=SOURCE) != REVISION:
        raise RuntimeError('Pinned source identity changed')
    if git('status', '--porcelain', '--untracked-files=no', cwd=SOURCE):
        raise RuntimeError('Pinned source has tracked changes')
    for name, expected in ref['binaries'].items():
        if digest(BUILD / name) != expected:
            raise RuntimeError('Binary changed: ' + name)
    return ref


def bandwidth(directory, label):
    exe = REPO / 'reports/tobeo-20261024/pcie-root-cause/transfer_probe.exe'
    result = subprocess.run([str(exe)], env=environment(), capture_output=True, text=True, timeout=90)
    (directory / (label + '.log')).write_text(result.stdout + '\n' + result.stderr, encoding='utf-8')
    match = re.search(r'"test":"pinned_H2D"[^\n]*"event_GBps":([0-9.]+)', result.stdout)
    row = {'exit_code': result.returncode, 'h2d_GBps': float(match.group(1)) if match else None,
           'exe_sha256': digest(exe)}
    if result.returncode or row['h2d_GBps'] is None or row['h2d_GBps'] < 15:
        raise RuntimeError('HtoD control failed: ' + repr(row))
    return row
