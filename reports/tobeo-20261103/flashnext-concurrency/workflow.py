"""Bounded 1/2/4-slot local experiment; restore daily service in finally."""
import concurrent.futures
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import statistics
import subprocess
import threading
import time
import traceback
import urllib.request

import psutil

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
CFG = ROOT / 'strata-iq3_s.json'
spec = importlib.util.spec_from_file_location('helpers', OUT.parent / 'flashnext-262k/workflow.py')
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
h.OUT = OUT
h.STATE['validation_scope'] = '126-request bounded concurrency matrix; streaming latency, throughput, resources; restore original 262K'
urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))
WAVES = []
STOP = threading.Event()
DEADLINE = time.monotonic() + 5400


def check():
    if h.GUARD_ERROR:
        raise RuntimeError(h.GUARD_ERROR)
    if time.monotonic() > DEADLINE:
        raise TimeoutError('Experiment exceeded 90-minute bound')


def resources():
    with (OUT / 'resources.jsonl').open('a', encoding='utf8') as f:
        while not STOP.wait(2):
            try:
                check()
                vm = psutil.virtual_memory()
                row = {'time': h.stamp(), 'stage': h.STATE['status'],
                       'ram_available': vm.available, 'ram_used': vm.total-vm.available,
                       'cpu_percent': psutil.cpu_percent()}
                if h.ACTIVE and h.ACTIVE.poll() is None:
                    pp = psutil.Process(h.ACTIVE.pid)
                    row['processes'] = [{'pid': p.pid, 'name': p.name(), 'memory': p.memory_info()._asdict()}
                                        for p in [pp] + pp.children(recursive=True)]
                    try:
                        m = h.api(18080, '/metrics', timeout=2)
                        row['live'] = m.get('live')
                        row['slots'] = m.get('slots')
                        row['hardware'] = m.get('hardware')
                    except Exception as e:
                        row['metrics_error'] = repr(e)
                f.write(json.dumps(row, ensure_ascii=False)+'\n'); f.flush()
            except psutil.NoSuchProcess:
                continue
            except Exception:
                h.GUARD_ERROR = traceback.format_exc()
                if h.ACTIVE:
                    h.kill_tree(h.ACTIVE.pid)
                return


def prompt(key, repeats):
    return (f'{key}\nRead these background records before completing the task.\n'
            + 'Record: amber cedar river stone; the archive contains routine weather observations.\n' * repeats
            + '\nTask: Write integers from 1 to 1000 in ascending order, separated by spaces. '
              'Start immediately with 1, omit explanations, and continue until the output limit.')


def prepare():
    workloads = []
    for target in (1024, 8192):
        lo, hi = 1, 1200
        while lo < hi:
            mid = (lo+hi)//2
            n = h.api(8080, '/v1/messages/count_tokens', {'model': 'qwen3.8-flash-next-iq3_s',
                      'thinking': {'type': 'disabled'}, 'messages': [{'role': 'user', 'content': prompt('CASE-1-1-1', mid)}]}, timeout=30)['input_tokens']
            if n < target:
                lo = mid+1
            else:
                hi = mid
        for c in (1, 2, 4):
            for r in (1, 2, 3):
                for i in range(c):
                    key = f'CASE-{target}-{c}-{r}-{i}'
                    text = prompt(key, lo)
                    workloads.append({'target': target, 'concurrency': c, 'round': r, 'index': i,
                                      'key': key, 'messages': [{'role': 'user', 'content': text}],
                                      'sha256': hashlib.sha256(text.encode()).hexdigest()})
    h.save('workloads.json', workloads)
    return workloads


def request(item, name, barrier=None, max_tokens=256):
    body = {'model': 'qwen3.8-flash-next-iq3_s', 'messages': item['messages'], 'temperature': 0,
            'seed': 42, 'max_tokens': max_tokens, 'reasoning_effort': 'none',
            'chat_template_kwargs': {'enable_thinking': False}, 'stream': True,
            'stream_options': {'include_usage': True}}
    h.save(name+'.request.json', body)
    if barrier:
        barrier.wait(timeout=30)
    started = time.perf_counter()
    row = {'name': name, 'item': {k: v for k, v in item.items() if k != 'messages'},
           'started_monotonic': started, 'started_at': h.stamp(), 'events': [], 'usage': None,
           'finish_reason': None, 'text': '', 'error': None, 'ttft_s': None}
    try:
        req = urllib.request.Request('http://127.0.0.1:18080/v1/chat/completions',
                                     data=json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json'})
        done = False
        with urllib.request.urlopen(req, timeout=900) as response:
            for raw in response:
                check()
                elapsed = time.perf_counter()-started
                if elapsed > 900:
                    raise TimeoutError('Request exceeded 15-minute bound')
                line = raw.decode('utf8').strip()
                if not line.startswith('data:'):
                    continue
                data = line[5:].strip()
                if data == '[DONE]':
                    done = True
                    break
                chunk = json.loads(data)
                if 'error' in chunk:
                    raise RuntimeError(str(chunk['error']))
                if chunk.get('usage'):
                    row['usage'] = chunk['usage']
                if chunk.get('timings'):
                    row['timings'] = chunk['timings']
                for choice in chunk.get('choices', []):
                    delta = choice.get('delta', {})
                    text = delta.get('content') or delta.get('reasoning_content') or ''
                    if text:
                        if row['ttft_s'] is None:
                            row['ttft_s'] = elapsed
                        row['text'] += text
                        row['events'].append({'elapsed_s': elapsed, 'text': text})
                    if choice.get('finish_reason'):
                        row['finish_reason'] = choice['finish_reason']
        if not done or not row['usage'] or not row['text'].strip() or not row['finish_reason']:
            raise RuntimeError('Incomplete or empty stream')
        if not 1 <= row['usage']['completion_tokens'] <= max_tokens:
            raise RuntimeError('Invalid output token count')
        if max_tokens == 256 and abs(row['usage']['prompt_tokens']-item['target']) > 64:
            raise RuntimeError('Prompt length outside target tolerance')
        times = [e['elapsed_s'] for e in row['events']]
        row['chunk_gaps_s'] = [b-a for a, b in zip(times, times[1:])]
    except Exception:
        row['error'] = traceback.format_exc()
    finally:
        row['ended_monotonic'] = time.perf_counter()
        row['elapsed_s'] = row['ended_monotonic']-started
        h.save(name+'.result.json', row)
    return row


def wave(p, c, r, target, items):
    check()
    name = f'p{p}-c{c}-t{target}-r{r}'
    h.stage('running_'+name, waves_completed=len(WAVES), requests_completed=sum(len(w['requests']) for w in WAVES))
    before = h.api(18080, '/metrics')
    if before['live']['state'] != 'idle' or before['live'].get('queued'):
        raise RuntimeError('Unexpected request before wave')
    barrier = threading.Barrier(c)
    with concurrent.futures.ThreadPoolExecutor(max_workers=c) as pool:
        futures = [pool.submit(request, item, name+f'-i{i}', barrier) for i, item in enumerate(items)]
        rows = [f.result() for f in futures]
    elapsed = max(x['ended_monotonic'] for x in rows)-min(x['started_monotonic'] for x in rows)
    tokens = sum((x['usage'] or {}).get('completion_tokens', 0) for x in rows)
    result = {'name': name, 'parallel': p, 'concurrency': c, 'target': target, 'round': r,
              'wall_s': elapsed, 'output_tokens': tokens, 'output_tok_s': tokens/elapsed,
              'request_start_spread_s': max(x['started_monotonic'] for x in rows)-min(x['started_monotonic'] for x in rows),
              'requests': rows, 'metrics_before': before, 'metrics_after': h.api(18080, '/metrics')}
    WAVES.append(result)
    h.save(name+'.wave.json', result)
    h.save('waves.json', WAVES)
    if any(x['error'] for x in rows):
        raise RuntimeError('Request failure in '+name)
    check()


def summarize():
    cells = []
    for p in (1, 2, 4):
        for c in (1, 2, 4):
            for t in (1024, 8192):
                ww = [w for w in WAVES if (w['parallel'], w['concurrency'], w['target']) == (p,c,t)]
                rr = [r for w in ww for r in w['requests']]
                if not ww:
                    continue
                cell = {'parallel': p, 'concurrency': c, 'target': t, 'waves': len(ww),
                        'requests': len(rr), 'errors': sum(bool(r['error']) for r in rr)}
                for name, values in [('output_tok_s', [w['output_tok_s'] for w in ww]),
                                     ('ttft_s', [r['ttft_s'] for r in rr if r['ttft_s'] is not None]),
                                     ('latency_s', [r['elapsed_s'] for r in rr])]:
                    if values:
                        cell[name] = {'median': statistics.median(values), 'min': min(values), 'max': max(values)}
                cell['cached_input_tokens'] = sum((r['usage'] or {}).get('prompt_tokens_details', {}).get('cached_tokens',0) for r in rr)
                cell['early_stop_requests'] = sum(r['finish_reason'] != 'length' for r in rr)
                cells.append(cell)
    h.save('summary.json', {'cells': cells, 'waves': len(WAVES), 'scope': h.STATE['validation_scope'],
                           'review_required': True, 'notes': ['Chunk intervals are not individual token intervals.',
                           'Auto allocation and engine-selected MTP behavior may differ by parallel mode.',
                           'Inspect cached tokens and promotion before interpreting prefill comparisons.',
                           'One startup per arm; three waves are within-process repetitions, not independent restarts.']})


def smoke(port, label):
    text, _, _ = h.complete(port, [{'role': 'user', 'content': 'Reply with exactly READY.'}], label, 32)
    if text.strip() != 'READY':
        raise RuntimeError('Restoration smoke failed: '+repr(text))


def main():
    original = CFG.read_bytes()
    cfg = json.loads(original)
    h.save('config-original.json', cfg)
    h.stage('preflight', original_config_sha256=hashlib.sha256(original).hexdigest())
    h.save('provenance.json', {'time': h.stamp(), 'engine': str(h.EXE),
           'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
           'git_status': subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True),
           'engine_sha256': hashlib.file_digest(h.EXE.open('rb'), 'sha256').hexdigest(),
           'original_engine_info': h.api(8080, '/metrics')['engine']})
    if any(a in cfg['args'] for a in ('--batch', '--slots')):
        raise RuntimeError('Unexpected explicit batch argument')
    if any(c.status == 'LISTEN' and c.laddr.port == 18080 for c in psutil.net_connections(kind='tcp')):
        raise RuntimeError('Test port occupied')
    workloads = prepare()
    before = h.api(8080, '/metrics')
    h.save('original.metrics.json', before)
    if before['live']['state'] != 'idle' or before['live'].get('queued'):
        raise RuntimeError('Daily service busy; no service stopped')
    if before['engine']['max_context'] != 262144:
        raise RuntimeError('Expected existing 262K service')
    owners = {c.pid for c in psutil.net_connections(kind='tcp') if c.status=='LISTEN' and c.laddr.port==8080}
    if len(owners) != 1:
        raise RuntimeError('Unexpected listener ownership')
    owner = psutil.Process(owners.pop())
    if 'serve.server' not in owner.cmdline() or str(CFG) not in owner.cmdline():
        raise RuntimeError('Daily server identity mismatch')
    failure = None
    try:
        h.stage('stopping_daily_service', original_server_pid=owner.pid)
        h.kill_tree(owner.pid)
        threading.Thread(target=h.memory_guard, daemon=True).start()
        monitor = threading.Thread(target=resources, daemon=True); monitor.start()
        for p in (1, 2, 4):
            check()
            time.sleep(5)
            test = json.loads(original)
            test.update(exe=str(h.EXE), port=18080, parallel=p, log=str(OUT/f'p{p}-engine.log'))
            h.save(f'p{p}-config.json', test)
            _, health = h.launch(OUT/f'p{p}-config.json', 18080, f'p{p}-server')
            metrics = h.api(18080, '/metrics')
            h.save(f'p{p}-loaded.json', {'health': health, 'metrics': metrics})
            actual = int(metrics['engine'].get('batch_slots') or 0)
            if (p == 1 and actual > 1) or (p > 1 and actual != p):
                raise RuntimeError(f'Parallel slots mismatch: requested {p}, actual {actual or 1}')
            if health['max_context'] != 262144:
                raise RuntimeError('Effective context changed')
            warm = request({'messages': [{'role':'user','content':'WARMUP: Write integers from 1 to 1000, separated by spaces. Continue until the output limit.'}]}, f'p{p}-warmup', max_tokens=96)
            if warm['error']:
                raise RuntimeError(warm['error'])
            # Rotate concurrency order across rounds to reduce fixed-order effects.
            for r, order in enumerate(((1,2,4), (2,4,1), (4,1,2)), 1):
                for t in ((1024,8192) if r % 2 else (8192,1024)):
                    for c in order:
                        items = [x for x in workloads if (x['target'],x['concurrency'],x['round']) == (t,c,r)]
                        wave(p,c,r,t,items)
            h.kill_tree(h.ACTIVE.pid); h.ACTIVE = None
        h.stage('matrix_complete_restoring', waves_completed=len(WAVES))
    except Exception:
        failure = traceback.format_exc()
        h.stage('experiment_failed_restoring', error=failure)
    finally:
        STOP.set(); h.GUARD_STOP.set()
        if 'monitor' in locals():
            monitor.join(timeout=10)
        if h.ACTIVE:
            h.kill_tree(h.ACTIVE.pid); h.ACTIVE = None
        if CFG.read_bytes() != original:
            raise RuntimeError('Original config edited externally; refusing unknown recovery config')
        h.GUARD_ERROR = None
        time.sleep(5)
        _, health = h.launch(CFG, 8080, 'restored-262k')
        if health['max_context'] != 262144:
            raise RuntimeError('Restored context mismatch')
        smoke(8080, 'restored-smoke')
        h.save('restored.health.json', h.api(8080, '/health'))
        h.save('restored.metrics.json', h.api(8080, '/metrics'))
        summarize()
        h.stage('experiment_failed_restored_262k' if failure else 'matrix_complete_restored_262k',
                error=failure, waves_completed=len(WAVES), requests_completed=sum(len(w['requests']) for w in WAVES),
                restored_server_pid=h.ACTIVE.pid, review_required=True)
        with (OUT/'README.md').open('a', encoding='utf8') as f:
            f.write(f'\n{h.stamp()}：后台流程结束，完成{len(WAVES)}/54波；原262K服务恢复并通过短请求。'
                    + ('实验失败，详见status.json。' if failure else '矩阵完成，待人工复核。')+'\n')
    return 1 if failure else 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        h.stage('workflow_error', error=traceback.format_exc(), waves_completed=len(WAVES))
        raise
