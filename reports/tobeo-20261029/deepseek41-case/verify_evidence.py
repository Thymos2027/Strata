"""Independently cross-check saved HTTP events, aggregate rows and file identities."""
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
RUN = OUT / 'execution-03'
r = json.loads((RUN / 'results.json').read_text(encoding='utf-8'))
rows = r['functional'] + [r['warmup']] + r['performance'] + r['soak']
assert len({row['name'] for row in rows}) == len(rows)
checks = []
message_alias_notes = []
for row in rows:
    response = json.loads((RUN / f'{row["name"]}.response.json').read_text(encoding='utf-8'))
    content = ''.join(c.get('delta', {}).get('content') or '' for e in response['events'] for c in e.get('choices', []))
    assert content == row['content'] == response['result']['content']
    assert response['result']['usage'] == row['usage']
    assert response['result']['timings'] == row['timings']
    assert response['result']['finish'] == row['finish']
    actual_messages = response['request']['messages']
    if actual_messages != row['messages']:
        # The runner appended follow-up turns to two shared Python lists after the
        # first response had already been archived. Do not rewrite either artifact.
        assert row['name'] in ('gate-multiturn-a', 'gate-tools')
        assert len(actual_messages) == 1
        assert len(row['messages']) == (3 if row['name'] == 'gate-multiturn-a' else 4)
        assert actual_messages == row['messages'][:1]
        assert actual_messages == response['result']['messages']
        message_alias_notes.append({'name': row['name'], 'actual_request_messages': len(actual_messages),
                                    'aggregate_messages': len(row['messages']),
                                    'authoritative_input': f"{row['name']}.response.json request.messages",
                                    'reason': 'Aggregate list contains subsequently appended follow-up messages; raw request retained unchanged.'})
    finishes = [c['finish_reason'] for e in response['events'] for c in e.get('choices', []) if c.get('finish_reason')]
    assert finishes == [row['finish']]
    usages = [e['usage'] for e in response['events'] if e.get('usage')]
    assert usages[-1] == row['usage']
    assert row['usage']['total_tokens'] == row['usage']['prompt_tokens'] + row['usage']['completion_tokens']
    data = json.loads((RUN / row['resources_file']).read_text(encoding='utf-8'))
    assert data['error'] is None and len(data['samples']) >= 2
    assert all(b['monotonic_s'] >= a['monotonic_s'] for a, b in zip(data['samples'], data['samples'][1:]))
    checks.append({'name': row['name'], 'passed': True})
assert len(r['performance']) == 6
assert all(row['usage']['completion_tokens'] == 256 and row['finish'] == 'length' for row in r['performance'])
assert len(r['loads']) == 2 and all(row.get('load_seconds') for row in r['loads'])
assert r['soak_elapsed_s'] >= 1800
assert r['passed'] and r['restore_errors'] == [] and r['health_after']['loaded']
assert r['daily_config_sha256_after'] == r['daily_config_sha256_before']
assert hashlib.sha256((OUT / 'run_case.py').read_bytes()).hexdigest() == r['controller_sha256']
assert hashlib.sha256((OUT / 'experiment-plan.md').read_bytes()).hexdigest() == r['protocol_sha256']
fingerprints = []
for path in sorted(RUN.rglob('*')):
    if path.is_file() and not path.name.endswith('.tmp'):
        with path.open('rb') as h:
            sha = hashlib.file_digest(h, 'sha256').hexdigest()
        fingerprints.append({'path': str(path.relative_to(RUN)), 'bytes': path.stat().st_size, 'sha256': sha})
result = {'passed': True, 'checked_http_requests': len(rows), 'requests': checks,
          'aggregate_message_alias_notes': message_alias_notes,
          'evidence_files': fingerprints, 'limits': 'Offline consistency check; no new inference or model quality claim.'}
(OUT / 'evidence-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'passed': True, 'http_requests': len(rows), 'fingerprinted_files': len(fingerprints)}))
