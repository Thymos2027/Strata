"""Small local API probe; synthetic text only, no restart or config changes.

This is a functional cache probe, not a performance benchmark. The server's
existing cache state can affect it. Results include rendered-prefix reuse counts,
not proof of any particular cache implementation's correctness.
"""
import json
import time
import urllib.request
from pathlib import Path
from uuid import uuid4

BASE = 'http://127.0.0.1:8080'


def main():
    with urllib.request.urlopen(BASE + '/v1/models', timeout=10) as r:
        model = json.load(r)['data'][0]['id']
    tag = uuid4().hex
    document = '\n'.join(f'Component {i}: validates the request and records status {i % 17}.' for i in range(180))
    initial = [{'role': 'user', 'content': f'Cache probe {tag}\n{document}\nReply with OK.'}]
    alternate = [{'role': 'user', 'content': f'Different conversation {tag}: reply with HELLO.'}]
    rows = []
    for name, messages in [('initial', initial), ('repeat', initial), ('other', alternate), ('return', initial)]:
        payload = {'model': model, 'messages': messages, 'temperature': 0, 'max_tokens': 16,
                   'chat_template_kwargs': {'enable_thinking': False}}
        req = urllib.request.Request(BASE + '/v1/chat/completions', data=json.dumps(payload).encode(),
                                     headers={'Content-Type': 'application/json'})
        start = time.monotonic()
        with urllib.request.urlopen(req, timeout=180) as r:
            response = json.load(r)
        rows.append({'case': name, 'elapsed_s': time.monotonic() - start, 'response': response})
        print(json.dumps({'case': name, 'usage': response.get('usage'), 'timings': response.get('timings')}, ensure_ascii=False), flush=True)
    Path(__file__).with_name('prefix-reuse-probe.json').write_text(
        json.dumps({'method': __doc__, 'rows': rows}, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
