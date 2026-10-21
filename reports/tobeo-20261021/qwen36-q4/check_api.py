"""Verify explicit greedy HTTP configuration, then stop only this test server."""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
env = dict(os.environ, PYTHONUTF8='1', STRATA_COMPONENTS_DIR=r'D:\Models\Strata\components',
           PYTHONPATH=str(ROOT / '.venv/Lib/site-packages') + os.pathsep + str(ROOT))
with (OUT / 'api-server.stdout.log').open('w', encoding='utf-8') as stdout, \
        (OUT / 'api-server.stderr.log').open('w', encoding='utf-8') as stderr:
    p = subprocess.Popen([sys._base_executable, '-u', '-m', 'serve.server', '--engine', 'strata',
                          '--config', str(ROOT / 'strata-qwen36-q4.json'), '--port', '8081'],
                         cwd=ROOT, env=env, stdout=stdout, stderr=stderr,
                         creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        deadline = time.monotonic() + 180
        while True:
            if p.poll() is not None:
                raise RuntimeError(f'Test server exited {p.returncode}')
            try:
                with urllib.request.urlopen('http://127.0.0.1:8081/health', timeout=2) as r:
                    health = json.load(r)
                if health.get('loaded'):
                    break
            except OSError:
                pass
            if time.monotonic() > deadline:
                raise TimeoutError('Test server not ready')
            time.sleep(1)
        payload = {'model': 'qwen3.6-35b-a3b-ud-q4_k_xl', 'messages': [{'role': 'user',
            'content': '请用中文解释 CPU 与 GPU 如何协作运行混合专家模型，分三点说明。'}],
            'max_tokens': 192, 'chat_template_kwargs': {'enable_thinking': False}}
        request = urllib.request.Request('http://127.0.0.1:8081/v1/chat/completions',
                                        data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=120) as r:
            response = json.load(r)
        assert response['choices'][0]['message'].get('content'), response
        (OUT / 'api-verification.json').write_text(json.dumps({'health': health, 'response': response},
                                                             ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(response.get('timings'), ensure_ascii=False), flush=True)
    finally:
        p.terminate()
        p.wait(timeout=30)
