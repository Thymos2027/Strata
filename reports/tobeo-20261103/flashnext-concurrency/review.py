"""Offline consistency audit plus read-only current health check; no GPU workload."""
import collections
import hashlib
import json
from pathlib import Path
import urllib.request
from datetime import datetime, timezone, timedelta

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
def read(name):
    return json.loads((OUT/name).read_text(encoding='utf8'))

waves = read('waves.json')
rows = [json.loads(p.read_text(encoding='utf8')) for p in OUT.glob('p*-c*-i*.result.json')]
passed = [r for r in rows if not r['error']]
failed = [r for r in rows if r['error']]
assert len(waves) == 38 and len(rows) == 91 and len(passed) == 87 and len(failed) == 4
assert sum(len(w['requests']) for w in waves) == len(passed)
assert all(r['usage']['completion_tokens'] == 256 and r['finish_reason'] == 'length' for r in passed)
assert all(r['usage']['prompt_tokens_details']['cached_tokens'] == 0 for r in passed)
assert all(abs(r['usage']['prompt_tokens']-r['item']['target']) <= 64 for r in passed)
matched = collections.defaultdict(list)
for r in passed:
    matched[r['item']['key']].append(r['item']['sha256'])
assert all(len(set(hashes)) == 1 for hashes in matched.values())
assert all(r['name'].startswith('p4-c4-t1024-r1-') for r in failed)
mem = [json.loads(line) for line in (OUT/'memory.jsonl.log').read_text().splitlines()]
samples = [json.loads(line) for line in (OUT/'resources.jsonl').read_text().splitlines()]
tail = mem[-3:]
assert all(r['available_commit'] < 2*2**30 for r in tail)
assert all(r['available_ram'] > 3*2**30 for r in tail)
state = read('status.json')
sha = hashlib.sha256((ROOT/'strata-iq3_s.json').read_bytes()).hexdigest()
assert sha == state['original_config_sha256']
assert read('restored-smoke.response.json')['response']['choices'][0]['message']['content'].strip() == 'READY'
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
health = json.load(opener.open('http://127.0.0.1:8080/health', timeout=10))
assert health['loaded'] and health['max_context'] == 262144
report = {'reviewed_at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
          'attempted_requests': len(rows), 'successful_requests': len(passed), 'failed_requests': len(failed),
          'successful_waves': len(waves), 'failed_wave': 'p4-c4-t1024-r1',
          'not_attempted_requests': 126-len(rows), 'all_successful_output_tokens': 256,
          'all_successful_cached_tokens': 0, 'prompt_tokens': sorted({r['usage']['prompt_tokens'] for r in passed}),
          'minimum_available_ram_gib': min(r['available_ram'] for r in mem)/2**30,
          'minimum_available_commit_gib': min(r['available_commit'] for r in mem)/2**30,
          'peak_sampled_gpu_gib': max(r.get('hardware',{}).get('gpu_mem_used',0) for r in samples)/2**30,
          'last_three_memory_guard_samples': tail, 'config_sha256_unchanged': sha, 'live_health': health,
          'parallel_arms': {str(p): {'actual_slots': read(f'p{p}-loaded.json')['metrics']['engine'].get('batch_slots',1),
                            'expert_slots': read(f'p{p}-loaded.json')['metrics']['engine']['expert_slots']}
                            for p in (1,2,4)},
          'draft_tokens_by_arm_concurrency': {}, 'checks_passed': True}
for p in (1,2,4):
    for c in (1,2,4):
        rr = [r for w in waves if w['parallel']==p and w['concurrency']==c for r in w['requests']]
        if rr:
            report['draft_tokens_by_arm_concurrency'][f'p{p}-c{c}'] = {
                'requests':len(rr), 'offered':sum(r.get('timings',{}).get('draft_n',0) for r in rr),
                'accepted':sum(r.get('timings',{}).get('draft_n_accepted',0) for r in rr)}
(OUT/'review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
state.update(review_required=False, reviewed_at=report['reviewed_at'], requests_attempted=91,
             requests_failed=4, requests_not_attempted=35,
             stop_cause='Memory guard: commit headroom below 2 GiB for three consecutive 5-second samples; connection errors followed process termination',
             review_evidence='review.json; REVIEW.md')
(OUT/'status.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False,indent=2))
