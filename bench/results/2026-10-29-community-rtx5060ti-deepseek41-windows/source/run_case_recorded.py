"""Run the local DeepSeek case, preserve every response, and restore the daily service."""
import argparse
import ast
import ctypes
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

import psutil

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tools/dsv41'))
sys.path.insert(0, str(ROOT / '<LOCAL_TELEMETRY_SOURCE>'))
from smoke import tokenizer
from windows_telemetry import Telemetry
from strata_control.dsv41_engine import start_env

RUN = OUT / 'execution-01'
ZONE = timezone(timedelta(hours=8))
BASE = 'http://127.0.0.1:8081'
DAILY = 'http://127.0.0.1:8080'
PACK = Path('<PACK_DIR>')
record = {'phase': 'preparing', 'passed': False, 'loads': [], 'functional': [], 'performance': [], 'soak': []}
server = None
unloaded = False
handles = []
engine_pid = None


class PerformanceInfo(ctypes.Structure):
    _fields_ = [('cb', ctypes.c_ulong)] + [(name, ctypes.c_size_t) for name in (
        'CommitTotal', 'CommitLimit', 'CommitPeak', 'PhysicalTotal', 'PhysicalAvailable',
        'SystemCache', 'KernelTotal', 'KernelPaged', 'KernelNonpaged', 'PageSize')] + [
        ('HandleCount', ctypes.c_ulong), ('ProcessCount', ctypes.c_ulong), ('ThreadCount', ctypes.c_ulong)]


def commit_status():
    info = PerformanceInfo(); info.cb = ctypes.sizeof(info)
    if not ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(info), info.cb):
        raise ctypes.WinError()
    return {'committed_bytes': info.CommitTotal * info.PageSize,
            'limit_bytes': info.CommitLimit * info.PageSize,
            'available_ram_bytes': info.PhysicalAvailable * info.PageSize}


def stamp():
    return datetime.now(ZONE).isoformat()


def digest(path):
    with Path(path).open('rb') as h:
        return hashlib.file_digest(h, 'sha256').hexdigest()


def write(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def save():
    record['updated'] = stamp()
    write(RUN / 'results.json', record)


def api(path, data=None, base=BASE, timeout=20):
    headers = {'Content-Type': 'application/json', 'Origin': base}
    req = urllib.request.Request(base + path, data=json.dumps(data).encode() if data is not None else None, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


class Resources(Telemetry):
    def __init__(self, pid):
        super().__init__(pid)
        for name, path in [('system_committed_bytes', r'\Memory\Committed Bytes'),
                           ('system_commit_limit_bytes', r'\Memory\Commit Limit')]:
            counter = ctypes.c_void_p()
            code = self.pdh.PdhAddEnglishCounterW(self.query, path, 0, ctypes.byref(counter))
            if code:
                raise RuntimeError(f'PDH {name}: {code}')
            self.counters[name] = counter

    def sample(self):
        row = super().sample()
        io = self.process.io_counters()
        disk = psutil.disk_io_counters()
        row.update(process_read_bytes=io.read_bytes, process_write_bytes=io.write_bytes,
                   system_disk_read_bytes=disk.read_bytes, system_disk_write_bytes=disk.write_bytes,
                   timestamp=stamp())
        return row


def engine_children():
    if server is None:
        return []
    try:
        return [p for p in psutil.Process(server.pid).children(recursive=True) if p.name().lower() == 'strata-dsv41.exe']
    except psutil.NoSuchProcess:
        return []


def stop_server():
    global server, engine_pid
    if server is not None:
        try:
            parent = psutil.Process(server.pid)
            children = parent.children(recursive=True)
            for p in reversed(children):
                try:
                    p.terminate()
                except psutil.NoSuchProcess:
                    pass
            try:
                parent.terminate()
            except psutil.NoSuchProcess:
                pass
            psutil.wait_procs(children + [parent], timeout=20)
            for p in children + [parent]:
                if p.is_running():
                    p.kill()
        except psutil.NoSuchProcess:
            pass
        server = None
        engine_pid = None


def start_server(tag):
    global server, engine_pid
    row = {'tag': tag, 'started': stamp()}
    record['loads'].append(row); save()
    env = start_env(record['config']['exe'])
    env['PYTHONUTF8'] = '1'
    env['STRATA_COMPONENTS_DIR'] = '<MODEL_DATA>/components'
    env['CUDA_VISIBLE_DEVICES'] = '0'
    for suffix in ('stdout', 'stderr'):
        handles.append((RUN / f'{tag}.{suffix}.log').open('w', encoding='utf-8'))
    cmd = [sys.executable, '-u', '-m', 'serve.server', '--engine', 'strata', '--config', str(RUN / 'config.json'),
           '--host', '127.0.0.1', '--port', '8081', '--offline']
    row['command'] = cmd
    start = time.monotonic()
    server = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=handles[-2], stderr=handles[-1],
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    row['server_pid'] = server.pid
    sampler = None
    try:
        while time.monotonic() - start < 1800:
            if server.poll() is not None:
                raise RuntimeError(f'Server exited while loading: {server.returncode}')
            children = engine_children()
            if children and sampler is None:
                engine_pid = children[0].pid
                row['engine_pid'] = engine_pid
                sampler = Resources(engine_pid); sampler.begin()
            try:
                health = api('/health', timeout=2)
                if health.get('loaded'):
                    row.update(load_seconds=time.monotonic() - start, health=health, ready_at=stamp())
                    row['metrics'] = api('/metrics')
                    assert health['max_context'] == 8192 and not health['images']
                    print(stamp(), 'READY', tag, row['load_seconds'], flush=True)
                    return
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                pass
            time.sleep(2)
        raise TimeoutError('Load exceeded 1800s')
    finally:
        if sampler:
            try:
                resources = sampler.end()
                write(RUN / f'{tag}.resources.json', resources)
                row['resources_file'] = f'{tag}.resources.json'
                row['rss_peak_bytes'] = resources['rss_peak_bytes']
                row['resource_error'] = resources['error']
            finally:
                sampler.close()
        save()


def ask(name, messages, cap=128, tools=None):
    row = {'name': name, 'started': stamp(), 'messages': messages, 'output_budget': cap}
    payload = {'model': 'deepseek-v4.1-flash', 'messages': messages, 'temperature': 0, 'top_p': 1,
               'max_tokens': cap, 'stream': True, 'stream_options': {'include_usage': True},
               'chat_template_kwargs': {'enable_thinking': False}, 'strata_checkpoint': False, 'seed': 0}
    if tools:
        payload.update(tools=tools, tool_choice='required')
        row['tools'] = tools
    req = urllib.request.Request(BASE + '/v1/chat/completions', data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    sampler = Resources(engine_pid); sampler.begin()
    first = None; first_event = None; chunks = []; content = ''; reasoning = ''; calls = {}
    start = time.perf_counter()
    timed_out = threading.Event()

    def deadline():
        timed_out.set()
        for p in engine_children():
            p.terminate()

    watchdog = threading.Timer(1200, deadline); watchdog.daemon = True; watchdog.start()
    try:
        with urllib.request.urlopen(req, timeout=900) as response:
            for line in response:
                line = line.decode('utf-8').strip()
                if not line.startswith('data:'):
                    continue
                value = line[5:].strip()
                if value == '[DONE]':
                    break
                event = json.loads(value)
                if 'error' in event:
                    raise RuntimeError(event['error'])
                chunks.append(event)
                if first_event is None:
                    first_event = time.perf_counter() - start
                if event.get('usage'):
                    row['usage'] = event['usage']
                if event.get('timings'):
                    row['timings'] = event['timings']
                for choice in event.get('choices', []):
                    delta = choice.get('delta', {})
                    text = delta.get('content') or ''
                    if text and first is None:
                        first = time.perf_counter() - start
                    content += text
                    reasoning += delta.get('reasoning_content') or ''
                    for call in delta.get('tool_calls', []):
                        target = calls.setdefault(call['index'], {'id': '', 'name': '', 'arguments': ''})
                        target['id'] = call.get('id', target['id'])
                        target['name'] += call.get('function', {}).get('name', '')
                        target['arguments'] += call.get('function', {}).get('arguments', '')
                    if choice.get('finish_reason'):
                        row['finish'] = choice['finish_reason']
        row.update(elapsed_s=time.perf_counter() - start, first_content_s=first, first_event_s=first_event,
                   content=content, reasoning=reasoning, tool_calls=list(calls.values()), finished=stamp())
        assert not timed_out.is_set() and row.get('finish') in ('stop', 'length', 'tool_calls'), 'Request incomplete'
        assert row.get('usage') and row.get('timings'), 'Missing token counts or engine timings'
        row['protocol_passed'] = True
        return row
    finally:
        watchdog.cancel()
        row['content'] = content
        try:
            resources = sampler.end()
            write(RUN / f'{name}.resources.json', resources)
            row['resources_file'] = f'{name}.resources.json'
            row['resources_summary'] = {k: v for k, v in resources.items() if k != 'samples'}
        finally:
            sampler.close()
        write(RUN / f'{name}.response.json', {'request': payload, 'result': row, 'events': chunks})
        print(stamp(), name, row.get('usage'), row.get('elapsed_s'), content[:100].replace('\n', ' '), flush=True)


def user(text):
    return [{'role': 'user', 'content': text}]


def check_code(text):
    if '```' in text:
        match = re.search(r'```(?:python)?\s*\n(.*?)```', text, re.S)
        if not match:
            return False
        text = match[1]
    try:
        tree = ast.parse(text)
        forbidden = (ast.Import, ast.ImportFrom, ast.Call, ast.Attribute, ast.For, ast.While, ast.With,
                     ast.Global, ast.Nonlocal, ast.ClassDef, ast.Lambda)
        if any(isinstance(n, forbidden) for n in ast.walk(tree)):
            return False
        space = {}
        exec(compile(tree, '<generated-absdiff>', 'exec'), {'__builtins__': {}}, space)
        return all(space['absdiff'](*args) == value for args, value in [((3, 8), 5), ((8, 3), 5), ((-4, -4), 0), ((-3, 7), 10)])
    except Exception:
        return False


def functional():
    tasks = [('paris', 'What is the capital of France? Answer in one short sentence.', lambda t: 'paris' in t.lower()),
             ('english', 'Reply with exactly this word and nothing else: READY', lambda t: t.strip() == 'READY'),
             ('chinese', '请只回复这六个字，不要解释：本地推理可用', lambda t: t.strip() == '本地推理可用'),
             ('json', 'Compute 17 + 25. Reply only with valid JSON using the key result and the numeric answer.',
              lambda t: json.loads(t) == {'result': 42}),
             ('code', 'Write only a Python function absdiff(a, b) that returns the absolute difference of two integers. Use subtraction and an if statement, no imports or function calls.', check_code)]
    for name, prompt, judge in tasks:
        row = ask('gate-' + name, user(prompt), 160)
        try:
            row['task_passed'] = bool(judge(row['content']))
        except Exception:
            row['task_passed'] = False
        record['functional'].append(row); save()
        assert row['task_passed'], f'Functional task failed: {name}'
    messages = user('Remember this synthetic marker: ORBIT-472. Reply only OK.')
    first = ask('gate-multiturn-a', messages, 32)
    messages += [{'role': 'assistant', 'content': first['content']}, {'role': 'user', 'content': 'What was the marker? Reply only with the marker.'}]
    second = ask('gate-multiturn-b', messages, 32)
    second['task_passed'] = second['content'].strip() == 'ORBIT-472'
    record['functional'] += [first, second]; save()
    assert second['task_passed'], 'Multiturn marker failed'
    tools = [{'type': 'function', 'function': {'name': 'add', 'description': 'Add two integers.',
              'parameters': {'type': 'object', 'properties': {'a': {'type': 'integer'}, 'b': {'type': 'integer'}},
                             'required': ['a', 'b'], 'additionalProperties': False}}}]
    messages = user('Use the add tool to calculate 17 plus 25.')
    row = ask('gate-tools', messages, 160, tools)
    calls = row['tool_calls']
    row['task_passed'] = len(calls) == 1 and calls[0]['name'] == 'add' and json.loads(calls[0]['arguments']) == {'a': 17, 'b': 25}
    record['functional'].append(row); save()
    assert row['task_passed'], 'API tool call failed'
    call = calls[0]
    messages += [{'role': 'assistant', 'content': None, 'tool_calls': [{'id': call['id'], 'type': 'function',
                   'function': {'name': call['name'], 'arguments': call['arguments']}}]},
                 {'role': 'tool', 'tool_call_id': call['id'], 'content': '{"result":42}'},
                 {'role': 'user', 'content': 'Reply only with the numeric result.'}]
    row = ask('gate-tool-result', messages, 48)
    row['task_passed'] = row['content'].strip() == '42'
    record['functional'].append(row); save()
    assert row['task_passed'], 'Tool result response failed'


def main():
    global unloaded, RUN
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', default='execution-03')
    parser.add_argument('--ssd-cache', type=float, default=64)
    parser.add_argument('--reserve-mib', type=int, default=1536)
    options = parser.parse_args()
    RUN = OUT / options.run
    RUN.mkdir(exist_ok=False)
    record['started'] = stamp()
    record['controller_sha256'] = digest(__file__)
    record['protocol_sha256'] = digest(OUT / 'experiment-plan.md')
    record['source_revision'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    engine = json.loads((OUT / 'engine.json').read_text())
    assert digest(engine['exe']) == engine['sha256']
    assert json.loads((OUT / 'pack-info-result.json').read_text())['passed']
    record['engine'] = engine
    record['daily_config_sha256_before'] = digest(ROOT / 'strata-iq3_s.json')
    (RUN / 'daily-config-backup.json').write_bytes((ROOT / 'strata-iq3_s.json').read_bytes())
    record['health_before'] = api('/health', base=DAILY)
    record['hardware'] = {'cpu': 'i7-12700', 'ram': psutil.virtual_memory()._asdict(),
                          'gpu': subprocess.check_output(['nvidia-smi', '--query-gpu=name,driver_version,memory.total', '--format=csv,noheader'], text=True).strip()}
    cfg = {'exe': engine['exe'], 'args': ['--pack', str(PACK), '--max-context', '8192', '--eos', '1',
            '--vision', 'off', '--dspark', 'auto', '--dspark-conf', '0.65', '--experts', '6', '--gpus', '0',
            '--ssd-cache', str(options.ssd_cache), '--reserve-mib', str(options.reserve_mib)],
            'cwd': str(ROOT), 'tokenizer': str(PACK / 'tokenizer'), 'arch': 'deepseek41',
            'model_name': 'deepseek-v4.1-flash', 'log': str(RUN / 'engine.log'),
            'engine_ready_s': 1800, 'host': '127.0.0.1', 'port': 8081}
    record['config'] = cfg; write(RUN / 'config.json', cfg)
    record['commit_before'] = commit_status()
    tok = tokenizer(PACK)
    workloads = []
    for target in (1024, 4096):
        prefix = 'Read the following synthetic records. Then write a detailed numbered review of validation, ownership, errors, and recovery in at least 500 words.\n'
        body = ''.join(f'Record {i}: request={i*17+3}; budget={i%19+1}; operation=restore; verify ownership and bounds.\n' for i in range(1000))
        ids = tok.encode(prefix + body, parse_special=True)[:target]
        text = tok.decode(ids)
        workloads.append({'target_tokens': target, 'text': text, 'body_ids': ids})
    write(RUN / 'workloads.json', workloads)
    save()
    guard_stop = threading.Event()

    def memory_guard():
        while not guard_stop.wait(0.5):
            try:
                status = commit_status()
                if server is not None and (status['committed_bytes'] > 0.94 * status['limit_bytes'] or status['available_ram_bytes'] < 4 * 1024**3):
                    write(RUN / 'memory-guard-trigger.json', {'timestamp': stamp(), **status})
                    for p in engine_children():
                        p.terminate()
                    return
            except Exception as exc:
                write(RUN / 'memory-guard-error.json', {'error': repr(exc)})
                return

    guard = threading.Thread(target=memory_guard, daemon=True); guard.start()
    try:
        record['unload'] = api('/unload?wait=30', {}, base=DAILY, timeout=600)
        assert record['unload'].get('status') in ('unloaded', 'not loaded')
        unloaded = True
        assert not api('/health', base=DAILY)['loaded']
        assert not any(p.info['name'].lower() == 'strata-dsv41.exe' for p in psutil.process_iter(['name']) if p.info['name'])
        record['phase'] = 'first-load'; save()
        start_server('first-load')
        record['phase'] = 'functional'; save(); functional()
        record['functional_passed'] = True
        record['phase'] = 'second-load'; save()
        stop_server(); time.sleep(3); start_server('second-load')
        warm = ask('warmup', user('Explain why checking array bounds prevents errors. Use one sentence.'), 64)
        record['warmup'] = warm; save()
        record['phase'] = 'performance'; save()
        for round_no in range(3):
            order = workloads if round_no % 2 == 0 else list(reversed(workloads))
            for work in order:
                name = f'performance-{round_no}-{work["target_tokens"]}'
                messages = user(f'Independent run {round_no}, length {work["target_tokens"]}.\n' + work['text'])
                row = ask(name, messages, 256)
                row.update(round=round_no, target_tokens=work['target_tokens'])
                record['performance'].append(row); save()
        record['performance_passed'] = len(record['performance']) == 6
        record['phase'] = 'soak'; record['soak_started'] = stamp(); save()
        start = time.monotonic(); index = 0
        while time.monotonic() - start < 1800:
            work = workloads[index % 2]
            messages = user(f'连续请求编号 {index}。请用中文逐项解释以下合成记录的校验与恢复风险。\n' + work['text']) if index % 4 < 2 else user(f'Continuous request {index}.\n' + work['text'])
            row = ask(f'soak-{index:03d}', messages, 256)
            row.update(index=index, target_tokens=work['target_tokens'])
            record['soak'].append(row); save(); index += 1
        record['soak_elapsed_s'] = time.monotonic() - start
        record['soak_finished'] = stamp()
        record['final_health'] = api('/health')
        record['final_metrics'] = api('/metrics?requests=all')
        record['passed'] = True; record['phase'] = 'complete'; save()
    except BaseException as exc:
        record['phase'] = 'failed'; record['error'] = repr(exc); save()
        raise
    finally:
        guard_stop.set()
        stop_server()
        for h in handles:
            h.close()
        errors = []
        if unloaded and record['health_before'].get('loaded'):
            try:
                record['daily_restore'] = api('/load', {}, base=DAILY, timeout=900)
                record['health_after'] = api('/health', base=DAILY)
                assert record['health_after']['loaded']
            except BaseException as exc:
                errors.append(repr(exc))
        record['daily_config_sha256_after'] = digest(ROOT / 'strata-iq3_s.json')
        if record['daily_config_sha256_after'] != record['daily_config_sha256_before']:
            errors.append('Daily configuration changed')
        record['restore_errors'] = errors
        if errors:
            record['passed'] = False
        record['finished'] = stamp(); save()


if __name__ == '__main__':
    main()
