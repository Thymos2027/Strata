"""Offline consistency checks only. No inference, network calls or model access."""
import ast
import hashlib
import json
from pathlib import Path
import re
import statistics

ROOT = Path(__file__).resolve().parent
requests = [json.loads(line) for line in (ROOT/'http-requests.jsonl').read_text(encoding='utf-8').splitlines()]
assert len(requests) == 52 and len({r['name'] for r in requests}) == 52
for r in requests:
    row = r['response']
    content = ''.join(c.get('delta',{}).get('content') or '' for event in r['events'] for c in event.get('choices',[]))
    assert content == row['content']
    assert [e['usage'] for e in r['events'] if e.get('usage')][-1] == row['usage']
    assert [e['timings'] for e in r['events'] if e.get('timings')][-1] == row['timings']
    assert [c['finish_reason'] for e in r['events'] for c in e.get('choices',[]) if c.get('finish_reason')] == [row['finish']]
    assert row['protocol_passed'] and row['usage']['total_tokens'] == row['usage']['prompt_tokens'] + row['usage']['completion_tokens']
    if r['name'] in ('gate-multiturn-a','gate-tools'):
        assert len(r['request']['messages']) == 1
pattern = r'prompt (\d+) tokens = (\d+) reused \+ (\d+) read in ([\d.]+) ms .*?, (\d+) generated in ([\d.]+) ms'
lines = re.findall(pattern,(ROOT/'logs/64GB-engine.log').read_text(encoding='utf-8'))
assert len(lines) == len(requests)
for native, r in zip(lines,requests):
    prompt,reused,read,pp,generated,decode = map(float,native)
    row=r['response']; timing=row['timings']
    assert prompt == row['usage']['prompt_tokens'] and generated == row['usage']['completion_tokens']
    assert reused == timing['cache_n'] and read == timing['prompt_n']
    assert abs(pp-timing['prompt_ms']) <= 1 and abs(decode-timing['predicted_ms']) <= 1
s=json.loads((ROOT/'summary.json').read_text(encoding='utf-8'))
for target in (1024,4096):
    rows=[r['response'] for r in requests if r['name'].startswith('performance-') and r['name'].endswith(str(target))]
    assert len(rows)==3 and all(r['usage']['completion_tokens']==256 and r['finish']=='length' for r in rows)
    assert statistics.median(r['elapsed_s'] for r in rows)==s['performance'][str(target)]['elapsed_s']['median']
assert len([r for r in requests if r['phase']=='soak'])==36 and s['soak']['elapsed_s']>=1800
samples=[json.loads(line) for line in (ROOT/'resources.jsonl').read_text(encoding='utf-8').splitlines()]
assert len(samples)==4384
for p in (ROOT/'source').glob('*.py'):
    ast.parse(p.read_text(encoding='utf-8'))
for p in ROOT.rglob('*'):
    if p.is_file() and p.suffix not in ('.png',):
        text=p.read_text(encoding='utf-8-sig')
        assert not re.search(r'(?i)(?:(?<![A-Za-z0-9])[A-Z]:[\\/]|gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,})',text),p.name
manifest=ROOT/'SHA256.json'
if manifest.exists():
    for r in json.loads(manifest.read_text(encoding='utf-8')):
        p=ROOT/r['path']
        assert p.stat().st_size==r['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256']
print(json.dumps({'passed':True,'http_requests':len(requests),'native_timing_lines':len(lines),'resource_samples':len(samples)}))
