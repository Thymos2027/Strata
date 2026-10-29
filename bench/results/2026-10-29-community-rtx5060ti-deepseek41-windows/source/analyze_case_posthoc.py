"""Offline summary of actual case responses, resources, and restoration checks."""
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path
import statistics as stats

OUT = Path(__file__).resolve().parent
RUN = OUT / 'execution-03'
record = json.loads((RUN / 'results.json').read_text(encoding='utf-8'))


def span(values):
    values = [v for v in values if v is not None]
    return {'n': len(values), 'median': stats.median(values), 'min': min(values), 'max': max(values)} if values else None


def resources(filename):
    data = json.loads((RUN / filename).read_text(encoding='utf-8'))
    samples = data['samples']
    fields = ['rss_bytes', 'private_bytes', 'card_vram_used_bytes', 'system_committed_bytes',
              'system_commit_limit_bytes', 'system_pages_input_s', 'system_page_reads_s']
    result = {key + '_max': max(s[key] for s in samples if s.get(key) is not None) for key in fields}
    result['system_available_bytes_min'] = min(s['system_available_bytes'] for s in samples)
    for field in ['process_read_bytes', 'process_write_bytes', 'system_disk_read_bytes',
                  'system_disk_write_bytes', 'process_page_faults']:
        result[field + '_delta'] = samples[-1][field] - samples[0][field]
    result['samples'] = len(samples)
    result['error'] = data.get('error')
    return result


def summarize(rows):
    return {'requests': len(rows), 'prompt_tokens': span([r['usage']['prompt_tokens'] for r in rows]),
            'completion_tokens': span([r['usage']['completion_tokens'] for r in rows]),
            'first_content_s': span([r['first_content_s'] for r in rows]),
            'elapsed_s': span([r['elapsed_s'] for r in rows]),
            'prompt_ms': span([r['timings']['prompt_ms'] for r in rows]),
            'prompt_tok_s': span([r['timings']['prompt_per_second'] for r in rows]),
            'decode_ms': span([r['timings']['predicted_ms'] for r in rows]),
            'decode_tok_s': span([r['timings']['predicted_per_second'] for r in rows]),
            'cache_n': span([r['timings']['cache_n'] for r in rows]),
            'finish': dict((v, sum(r['finish'] == v for r in rows)) for v in sorted({r['finish'] for r in rows}))}


summary = {'phase': record['phase'], 'passed': record['passed'], 'error': record.get('error'),
           'started': record['started'], 'finished': record.get('finished'), 'engine': record['engine'],
           'loads': [], 'functional': [], 'performance': {}, 'soak': {}, 'resource_scope':
           '0.5-second sampled engine process RAM/private/I/O; whole GPU VRAM; system commit/paging/disk I/O. Page faults are not hard faults.'}
for row in record['loads']:
    result = {key: row.get(key) for key in ['tag', 'load_seconds', 'ready_at', 'health', 'engine_pid']}
    if row.get('resources_file'):
        result['resources'] = resources(row['resources_file'])
    summary['loads'].append(result)
for row in record['functional']:
    summary['functional'].append({key: row.get(key) for key in ['name', 'task_passed', 'protocol_passed', 'content', 'tool_calls', 'usage', 'timings', 'elapsed_s']})
for target in (1024, 4096):
    rows = [r for r in record['performance'] if r['target_tokens'] == target]
    if rows:
        summary['performance'][str(target)] = summarize(rows)

groups = defaultdict(list)
for row in record['soak']:
    groups[f"{row['target_tokens']}-{'zh' if row['index'] % 4 < 2 else 'en'}"].append(row)
summary['soak']['requests'] = len(record['soak'])
summary['soak']['elapsed_s'] = record.get('soak_elapsed_s')
summary['soak']['groups'] = {}
for key, rows in groups.items():
    n = max(1, len(rows) // 3)
    summary['soak']['groups'][key] = {'overall': summarize(rows), 'first_third': summarize(rows[:n]),
                                    'last_third': summarize(rows[-n:]),
                                    'last_first_elapsed_ratio': stats.median(r['elapsed_s'] for r in rows[-n:]) / stats.median(r['elapsed_s'] for r in rows[:n]),
                                    'last_first_decode_speed_ratio': stats.median(r['timings']['predicted_per_second'] for r in rows[-n:]) / stats.median(r['timings']['predicted_per_second'] for r in rows[:n])}

all_resources = []
for row in record['functional'] + record['performance'] + record['soak']:
    if row.get('resources_file'):
        value = resources(row['resources_file']); value['name'] = row['name']; all_resources.append(value)
summary['request_resources'] = all_resources
summary['restoration'] = {key: record.get(key) for key in ['daily_config_sha256_before', 'daily_config_sha256_after', 'health_after', 'restore_errors']}
checks = {'controller_sha_matches': hashlib.sha256((OUT / 'run_case.py').read_bytes()).hexdigest() == record['controller_sha256'],
          'protocol_sha_matches': hashlib.sha256((OUT / 'experiment-plan.md').read_bytes()).hexdigest() == record['protocol_sha256'],
          'six_performance_requests': len(record['performance']) == 6,
          'functional_passed': record.get('functional_passed') is True,
          'all_requests_have_protocol_finish_usage_timings': all(r.get('protocol_passed') and r.get('usage') and r.get('timings') for r in record['functional'] + record['performance'] + record['soak']),
          'soak_at_least_1800_s': (record.get('soak_elapsed_s') or 0) >= 1800,
          'daily_config_unchanged': record.get('daily_config_sha256_before') == record.get('daily_config_sha256_after'),
          'daily_loaded': bool(record.get('health_after', {}).get('loaded')),
          'no_restore_errors': record.get('restore_errors') == [],
          'no_resource_sampling_errors': all(x['error'] is None for x in all_resources)}
summary['checks'] = checks
summary['offline_checks_passed'] = all(checks.values())
(OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
rows = record['performance'] + record['soak']
with (OUT / 'requests.csv').open('w', newline='', encoding='utf-8-sig') as h:
    writer = csv.DictWriter(h, fieldnames=['name', 'target_tokens', 'prompt_tokens', 'completion_tokens', 'finish', 'first_content_s', 'elapsed_s', 'prompt_ms', 'prompt_tok_s', 'decode_ms', 'decode_tok_s', 'cache_n'])
    writer.writeheader()
    for r in rows:
        t = r['timings']
        writer.writerow({'name': r['name'], 'target_tokens': r['target_tokens'], **{k: r[k] for k in ['finish', 'first_content_s', 'elapsed_s']},
                         'prompt_tokens': r['usage']['prompt_tokens'], 'completion_tokens': r['usage']['completion_tokens'],
                         'prompt_ms': t['prompt_ms'], 'prompt_tok_s': t['prompt_per_second'], 'decode_ms': t['predicted_ms'],
                         'decode_tok_s': t['predicted_per_second'], 'cache_n': t['cache_n']})
print(json.dumps({'phase': summary['phase'], 'checks': checks, 'performance': summary['performance'],
                  'soak_requests': len(record['soak'])}, ensure_ascii=False, indent=2))
