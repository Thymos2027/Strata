"""Bounded local validation; promote only after gates, restore on failure."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
from datetime import datetime, timezone, timedelta

import psutil

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
CFG = ROOT / 'strata-iq3_s.json'
PYTHON = Path(r'D:\Program Files\Anaconda\python.exe')
EXE = Path(r'D:\Models\Strata\components\engine\0.1.52-windows-x86_64-cuda-cuda13\strata.exe')
PLAN = ROOT / 'reports/INFERENCE_RESEARCH_PLAN.md'
CHECK = '完成 Flash-Next IQ3_S 本机原生262K上下文有界验收及日常服务切换'
STATE = {'status': 'starting', 'pid': os.getpid(), 'validation_scope': 'startup, short generation, near-limit three-needle retrieval, cached continuation, production smoke'}
ACTIVE = None
GUARD_STOP = threading.Event()
GUARD_ERROR = None

def stamp():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()

def save(name, obj):
    p = OUT / name
    temp = p.with_suffix(p.suffix + '.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(p)

def stage(label, **fields):
    STATE.update(status=label, updated_at=stamp(), **fields)
    save('status.json', STATE)
    print(stamp(), label, fields, flush=True)

def api(port, path, body=None, timeout=20):
    base = f'http://127.0.0.1:{port}'
    req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json', 'Origin': base})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

def kill_tree(pid):
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        parent.kill()
        for child in reversed(children):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        psutil.wait_procs(children + [parent], timeout=30)
    except psutil.NoSuchProcess:
        pass

def launch(config, port, label):
    global ACTIVE
    env = dict(os.environ, PYTHONUTF8='1', STRATA_COMPONENTS_DIR=r'D:\Models\Strata\components')
    with (OUT / (label + '.stdout.log')).open('wb') as stdout, (OUT / (label + '.stderr.log')).open('wb') as stderr:
        p = subprocess.Popen([str(PYTHON), '-u', '-m', 'serve.server', '--engine', 'strata', '--config', str(config), '--port', str(port)],
                             cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                             creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
    ACTIVE = p
    stage(label + '_loading', server_pid=p.pid)
    deadline = time.monotonic() + 1200
    while time.monotonic() < deadline:
        if GUARD_ERROR:
            raise RuntimeError(GUARD_ERROR)
        if p.poll() is not None:
            raise RuntimeError(f'{label} exited: {p.returncode}')
        try:
            h = api(port, '/health', timeout=3)
            if h.get('loaded') and h.get('status') == 'ok':
                return p, h
        except Exception:
            pass
        time.sleep(3)
    raise TimeoutError(label + ' startup exceeded 20 minutes')

def memory_guard():
    global GUARD_ERROR
    low = 0
    with (OUT / 'memory.jsonl.log').open('a', encoding='utf-8') as f:
        while not GUARD_STOP.wait(5):
            vm = psutil.virtual_memory()
            # Windows commit headroom, distinct from pagefile free space.
            import ctypes
            class Mem(ctypes.Structure):
                _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [(x, ctypes.c_ulonglong) for x in ('total_phys', 'avail_phys', 'total_commit', 'avail_commit', 'total_virtual', 'avail_virtual', 'avail_ext')]
            mem = Mem(); mem.length = ctypes.sizeof(Mem)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem)):
                GUARD_ERROR = 'Cannot read Windows memory guard'
                if ACTIVE and ACTIVE.poll() is None:
                    kill_tree(ACTIVE.pid)
                return
            f.write(json.dumps({'time': stamp(), 'available_ram': vm.available, 'available_commit': mem.avail_commit, 'server_pid': ACTIVE.pid if ACTIVE else None}) + '\n'); f.flush()
            low = low + 1 if vm.available < 3 * 2**30 or mem.avail_commit < 2 * 2**30 else 0
            if low >= 3:
                GUARD_ERROR = 'RAM below 3 GiB or commit headroom below 2 GiB for three samples'
                if ACTIVE and ACTIVE.poll() is None:
                    kill_tree(ACTIVE.pid)
                return

def complete(port, messages, name, max_tokens=128):
    stage('testing_' + name)
    started = time.monotonic()
    body = {'model': 'qwen3.8-flash-next-iq3_s', 'messages': messages, 'temperature': 0, 'seed': 42,
            'max_tokens': max_tokens, 'reasoning_effort': 'none', 'chat_template_kwargs': {'enable_thinking': False}, 'stream': False}
    result = api(port, '/v1/chat/completions', body, timeout=7200)
    save(name + '.response.json', {'elapsed_s': time.monotonic() - started, 'response': result})
    metrics = api(port, '/metrics')
    save(name + '.metrics.json', metrics)
    text = result['choices'][0]['message'].get('content') or ''
    if not text.strip() or any(t in text.lower() for t in ('nan', 'infinity')):
        raise RuntimeError(name + ' produced empty or non-finite output')
    return text, result, metrics

def main():
    global ACTIVE, GUARD_ERROR
    original = CFG.read_bytes()
    original_hash = hashlib.sha256(original).hexdigest()
    (OUT / 'config-original.json').write_bytes(original)
    old = json.loads(original)
    candidate = copy.deepcopy(old)
    candidate['args'][candidate['args'].index('--max-context') + 1] = '262144'
    candidate['exe'] = str(EXE)
    candidate['port'] = 18080
    candidate['log'] = str(OUT / 'test-engine.log')
    save('config-test.json', candidate)
    before = api(8080, '/metrics')
    save('before.metrics.json', before)
    save('before.health.json', api(8080, '/health'))
    if before['live']['state'] != 'idle' or before['live'].get('queued'):
        raise RuntimeError('Daily service is busy; no process stopped and no configuration changed')
    owners = {c.pid for c in psutil.net_connections(kind='tcp') if c.status == 'LISTEN' and c.laddr.port == 8080}
    if owners != {5032}:
        raise RuntimeError(f'Unexpected 8080 owner {owners}; no process stopped')
    cmd = psutil.Process(5032).cmdline()
    if 'serve.server' not in cmd or str(CFG) not in cmd:
        raise RuntimeError('Daily service identity mismatch')
    stage('stopping_64k', original_config_sha256=original_hash)
    kill_tree(5032)
    if psutil.pid_exists(23680):
        try:
            if 'serve.server' in psutil.Process(23680).cmdline():
                kill_tree(23680)
        except psutil.NoSuchProcess:
            pass
    time.sleep(5)
    changed = False
    try:
        threading.Thread(target=memory_guard, daemon=True).start()
        _, health = launch(OUT / 'config-test.json', 18080, 'test-server')
        save('test.health.json', health)
        if health['max_context'] != 262144:
            raise RuntimeError('Effective context is not 262144')
        text, _, _ = complete(18080, [{'role': 'user', 'content': 'Reply with exactly READY.'}], 'short', 32)
        if 'READY' not in text:
            raise RuntimeError('Short generation gate failed: ' + text)
        stage('preparing_near_limit_prompt')
        # Count with the actual server tokenizer; final OpenAI usage is also verified.
        unit = 'Background record: amber cedar river stone. This ordinary filler contains no access codes.\n'
        needles = ('PINE-739251', 'LAKE-482963', 'DUNE-615847')
        def make(n):
            return ('Synthetic context test. Memorize the following three labeled access codes.\n'
                    + 'EARLY_CODE: ' + needles[0] + '\n' + unit * (n // 2)
                    + '\nMIDDLE_CODE: ' + needles[1] + '\n' + unit * (n - n // 2)
                    + '\nLATE_CODE: ' + needles[2]
                    + '\nReturn EARLY_CODE, MIDDLE_CODE and LATE_CODE exactly, one per line. No explanation.')
        lo, hi = 1, 40000
        while lo < hi:
            mid = (lo + hi + 1) // 2
            count = api(18080, '/v1/messages/count_tokens', {'model': old['model_name'], 'max_tokens': 128,
                        'thinking': {'type': 'disabled'}, 'messages': [{'role': 'user', 'content': make(mid)}]}, timeout=120)['input_tokens']
            if count <= 261600:
                lo = mid
            else:
                hi = mid - 1
        prompt = make(lo)
        save('long-prompt.json', {'messages': [{'role': 'user', 'content': prompt}], 'sha256': hashlib.sha256(prompt.encode()).hexdigest()})
        messages = [{'role': 'user', 'content': prompt}]
        text, response, metrics = complete(18080, messages, 'near-limit', 128)
        used = response['usage']['prompt_tokens']
        if not 260000 <= used <= 261850 or not all(n in text for n in needles):
            raise RuntimeError(f'Near-limit gate failed: prompt_tokens={used}, answer={text!r}')
        messages += [{'role': 'assistant', 'content': text}, {'role': 'user', 'content': 'Repeat just MIDDLE_CODE, no other text.'}]
        text, response, metrics = complete(18080, messages, 'continuation', 64)
        if needles[1] not in text:
            raise RuntimeError('Continuation retrieval failed')
        recent = metrics['requests'][0]
        if recent.get('reused', 0) < 250000:
            raise RuntimeError('Long-prefix reuse gate failed')
        if GUARD_ERROR:
            raise RuntimeError(GUARD_ERROR)
        stage('validation_passed', long_prompt_tokens=used)
        kill_tree(ACTIVE.pid); ACTIVE = None
        time.sleep(5)
        if CFG.read_bytes() != original:
            raise RuntimeError('Daily configuration changed externally; refusing to overwrite')
        promoted = copy.deepcopy(old)
        promoted['args'][promoted['args'].index('--max-context') + 1] = '262144'
        temp = CFG.with_suffix('.json.262k.tmp')
        temp.write_text(json.dumps(promoted, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temp.replace(CFG); changed = True
        _, health = launch(CFG, 8080, 'production-server')
        if health.get('max_context') != 262144:
            raise RuntimeError('Production context mismatch')
        text, _, metrics = complete(8080, [{'role': 'user', 'content': 'Reply with exactly READY.'}], 'production-smoke', 32)
        if 'READY' not in text:
            raise RuntimeError('Production smoke failed')
        if GUARD_ERROR:
            raise RuntimeError(GUARD_ERROR)
        save('production.health.json', api(8080, '/health'))
        stage('passed_and_serving_262k', service='http://127.0.0.1:8080', server_pid=ACTIVE.pid)
        with (OUT / 'README.md').open('a', encoding='utf-8') as f:
            f.write(f'\n完成时间：{stamp()}。全部有界门槛通过，长请求实际输入 {used} tokens；原配置已仅将上下文改为262144，8080已通过重启后短请求验收。证据：status.json、near-limit.response.json、continuation.metrics.json、production.health.json及各阶段日志。未进行通用长文质量评测或持续压力测试。\n')
        plan = PLAN.read_text(encoding='utf-8')
        plan = plan.replace('- [ ] ' + CHECK, '- [x] ' + CHECK)
        plan += f'\n262K验收完成记录（{stamp()}）：见[tobeo-20261103/flashnext-262k/README.md](tobeo-20261103/flashnext-262k/README.md)，仅启动、{used}token检索、续聊缓存及8080短请求范围。\n'
        PLAN.write_text(plan, encoding='utf-8')
    except Exception:
        error = traceback.format_exc()
        print(error, flush=True)
        stage('failed_restoring_64k', error=error)
        GUARD_STOP.set()
        if ACTIVE:
            kill_tree(ACTIVE.pid); ACTIVE = None
        if changed:
            if json.loads(CFG.read_bytes()) == promoted:
                CFG.write_bytes(original)
            else:
                raise RuntimeError('External config edit after promotion; refusing to overwrite during recovery')
        GUARD_ERROR = None
        _, health = launch(CFG, 8080, 'restored-server')
        if health.get('max_context') != 65536 or not health.get('loaded'):
            raise RuntimeError('64K restoration verification failed')
        save('restored.health.json', health)
        stage('failed_restored_64k', error=error, server_pid=ACTIVE.pid)
        with (OUT / 'README.md').open('a', encoding='utf-8') as f:
            f.write(f'\n{stamp()}：262K验收未通过，已恢复64K；失败原因见status.json，恢复证据restored.health.json。研究计划项目保持未完成。\n')
        return 1
    finally:
        GUARD_STOP.set()
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        stage('workflow_error', error=traceback.format_exc())
        raise
