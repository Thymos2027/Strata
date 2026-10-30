"""Analyze only new traces; interval union and host API time are kept distinct."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import sqlite3
import statistics

from common import OUT, BASE, SOURCE, BUILD, FIXTURES, NSYS, digest, save, stamp, check_identity, protocol


def merge(intervals):
    result = []
    for start, end in sorted(intervals):
        if end <= start:
            continue
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(end, result[-1][1]))
        else:
            result.append((start, end))
    return result


def duration(intervals):
    return sum(end-start for start, end in merge(intervals))


def intersect(left, right):
    left, right = merge(left), merge(right)
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        start, end = max(left[i][0], right[j][0]), min(left[i][1], right[j][1])
        if end > start:
            result.append((start, end))
        if left[i][1] < right[j][1]:
            i += 1
        else:
            j += 1
    return result


def pid(global_id):
    return (global_id // 0x1000000) % 0x1000000 if global_id is not None else None


def activity(database, table, start, end, engine_pid, name=None):
    columns = {row[1] for row in database.execute('pragma table_info(' + table + ')')}
    if not columns:
        return []
    extra = ',s.value as name' if name else ''
    join = ' join StringIds s on s.id=e.' + name if name else ''
    query = 'select e.*' + extra + ' from ' + table + ' e' + join + ' where e.start<? and e.end>?'
    result = []
    for raw in database.execute(query, (end, start)):
        row = dict(raw)
        if pid(row.get('globalPid', row.get('globalTid'))) != engine_pid:
            continue
        row['crosses_client_boundary'] = row['start'] < start or row['end'] > end
        row['start'], row['end'] = max(start, row['start']), min(end, row['end'])
        result.append(row)
    return result


def spans(rows):
    return [(row['start'], row['end']) for row in rows]


def statistics_by_name(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row['name']].append(row)
    result = []
    for name, group in groups.items():
        times = [row['end']-row['start'] for row in group]
        result.append({'name': name, 'calls': len(group), 'sum_ms': sum(times)/1e6,
                       'union_ms': duration(spans(group))/1e6, 'mean_us': statistics.mean(times)/1e3,
                       'median_us': statistics.median(times)/1e3})
    return sorted(result, key=lambda row: row['sum_ms'], reverse=True)


def phase(database, name, engine_pid):
    windows = database.execute('select start,end from NVTX_EVENTS where text=?', (name,)).fetchall()
    if len(windows) != 1 or windows[0]['end'] is None:
        raise RuntimeError('Missing or unclosed NVTX window ' + name)
    start, end = windows[0]
    assert end > start
    kernels = activity(database, 'CUPTI_ACTIVITY_KIND_KERNEL', start, end, engine_pid, 'shortName')
    copies = activity(database, 'CUPTI_ACTIVITY_KIND_MEMCPY', start, end, engine_pid)
    memsets = activity(database, 'CUPTI_ACTIVITY_KIND_MEMSET', start, end, engine_pid)
    apis = activity(database, 'CUPTI_ACTIVITY_KIND_RUNTIME', start, end, engine_pid, 'nameId')
    assert kernels and apis, 'Missing actual engine activity'
    gpu = merge(spans(kernels+copies+memsets))
    gaps = []
    cursor = start
    for a, b in gpu:
        if a > cursor:
            gaps.append((cursor, a))
        cursor = max(cursor, b)
    if cursor < end:
        gaps.append((cursor, end))
    attention = [row for row in kernels if 'k_attn_part' in row['name']]
    sync = [row for row in apis if 'Synchronize' in row['name']]
    copy_types = {row['id']: row['label'] for row in database.execute('select * from ENUM_CUDA_MEMCPY_OPER')}
    by_copy = defaultdict(list)
    for row in copies:
        by_copy[copy_types.get(row['copyKind'], str(row['copyKind']))].append(row)
    wall = end-start
    assert duration(gpu)+duration(gaps) == wall
    assert 0 <= duration(spans(attention)) <= duration(gpu) <= wall
    assert duration(intersect(spans(sync), gaps)) <= min(duration(spans(sync)), duration(gaps))
    attention_fraction = duration(spans(attention))/wall
    info = {'phase': name, 'window_ms': wall/1e6, 'kernel_count': len(kernels),
            'kernel_union_ms': duration(spans(kernels))/1e6,
            'copy_union_ms': duration(spans(copies))/1e6,
            'kernel_copy_overlap_ms': (duration(spans(kernels))+duration(spans(copies))-duration(spans(kernels+copies)))/1e6,
            'gpu_union_ms': duration(gpu)/1e6, 'gpu_union_fraction': duration(gpu)/wall,
            'gpu_uncovered_ms': duration(gaps)/1e6,
            'attention_part_union_ms': duration(spans(attention))/1e6,
            'attention_part_wall_fraction': attention_fraction,
            'ideal_serial_all_attention_removed_speedup': 1/(1-attention_fraction) if attention_fraction < 1 else None,
            'runtime_api_union_ms': duration(spans(apis))/1e6,
            'synchronize_api_union_ms': duration(spans(sync))/1e6,
            'synchronize_gpu_gap_intersection_ms': duration(intersect(spans(sync), gaps))/1e6,
            'gpu_gap_outside_runtime_api_ms': (duration(gaps)-duration(intersect(spans(apis), gaps)))/1e6,
            'top_kernels': statistics_by_name(kernels)[:12],
            'attention_part_kernels': statistics_by_name(attention),
            'runtime_apis': statistics_by_name(apis)[:12],
            'copies': {key: {'records_intersecting_window': len(values),
                             'bytes_in_intersecting_records': sum(row['bytes'] for row in values),
                             'records_crossing_client_boundary': sum(row['crosses_client_boundary'] for row in values),
                             'union_ms': duration(spans(values))/1e6} for key, values in by_copy.items()},
            'cuda_graph_launch_calls': sum('cudaGraphLaunch' in row['name'] for row in apis),
            'graph_node_kernels': sum(row.get('graphNodeId') is not None for row in kernels)}
    if name == 'decode-after-first-token':
        assert attention
    return info, {'start': start, 'end': end, 'kernels': kernels, 'copies': copies, 'sync': sync,
                  'other_apis': [row for row in apis if 'Synchronize' not in row['name']]}


def analyze_cell(directory, cell):
    tag = cell['tag']
    plain = json.loads((directory / (tag+'-plain.json')).read_text(encoding='utf-8'))
    trace = json.loads((directory / (tag+'-trace.json')).read_text(encoding='utf-8'))
    assert plain['passed'] and trace['passed'] and all(trace['validation'].values())
    assert plain['output_ids'] == trace['output_ids'] and len(trace['output_ids']) == 64
    assert protocol.tokens_hash(trace['output_ids']) == trace['output_sha256']
    fixture = FIXTURES / (trace['case'] + '.ids.json')
    assert digest(fixture) == trace['fixture_sha256']
    assert protocol.tokens_hash(json.loads(fixture.read_text())) == trace['prompt_sha256']
    for request in [plain, trace]:
        assert request['layout']['chunks'] == [cell['chunk']]
        assert request['layout']['slots'] == cell['actual_slots']
        assert request['layout']['slot_replacements'] and not any(request['layout']['slot_replacements'])
        assert request['engine_exit_code'] == 0
    database = sqlite3.connect(directory / (tag+'-trace.sqlite'))
    database.row_factory = sqlite3.Row
    phases = []
    raw_decode = None
    try:
        all_pids = {pid(row[0]) for row in database.execute('select distinct globalPid from CUPTI_ACTIVITY_KIND_KERNEL')}
        assert all_pids == {trace['engine_pid']}, 'GPU activity must come from the measured engine only'
        for name in ['request', 'prefill-to-first-token', 'decode-after-first-token']:
            info, raw = phase(database, name, trace['engine_pid'])
            phases.append(info)
            if name == 'decode-after-first-token':
                raw_decode = raw
        diagnostics = [dict(row) for row in database.execute('select * from DIAGNOSTIC_EVENT')]
        warnings = [row for row in diagnostics if row['severity'] >= 2]
        loss = [row for row in diagnostics if row['severity'] == 3 or any(
                word in row['text'].lower() for word in ['events lost', 'dropped', 'overflow'])]
        fallback = [row for row in warnings if 'not supported by this build' in row['text']]
        engine_cuda = [row for row in warnings if pid(row['globalPid']) == trace['engine_pid'] and 'CUDA' in row['text']]
        tables = {row[0] for row in database.execute("select name from sqlite_master where type='table'")}
        cpu_samples = database.execute('select count(*) from COMPOSITE_EVENTS').fetchone()[0] if 'COMPOSITE_EVENTS' in tables else 0
    finally:
        database.close()
    return {'tag': tag, 'chunk': cell['chunk'], 'case': cell['case'], 'actual_slots': cell['actual_slots'],
            'prompt_tokens': trace['prompt_tokens'], 'output_sha256': trace['output_sha256'],
            'same_chunk_output_identical': True,
            'plain': {key: plain[key] for key in ['prompt_ms','decode_ms','client_ttft_s','client_total_s','process_cpu_s']},
            'profiled': {key: trace[key] for key in ['prompt_ms','decode_ms','client_ttft_s','client_total_s','process_cpu_s']},
            'trace_to_plain_prompt_ratio': cell['trace_to_plain_prompt_ratio'],
            'trace_to_plain_decode_ratio': cell['trace_to_plain_decode_ratio'],
            'phases': phases, 'diagnostic_warnings': warnings, 'loss_or_error': loss,
            'driver_fallback': fallback, 'engine_cuda_warnings': engine_cuda,
            'cpu_sampling_records': cpu_samples}, raw_decode


def plot(data):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.patches import Patch
    fig, axes = plt.subplots(4, 1, figsize=(14, 12))
    colors = {'attention': '#e67e22', 'native kernels': '#2563eb', 'other kernels': '#8c98a8',
              'copy': '#16856b', 'host sync API': '#b13a73', 'other host API': '#7b61a8'}
    for axis, (info, raw) in zip(axes, data):
        left, right = raw['start']+200_000_000, min(raw['end'], raw['start']+500_000_000)
        assert right > left
        streams = sorted({row['streamId'] for row in raw['kernels']+raw['copies'] if row['start'] < right and row['end'] > left})
        tracks = {stream: index+2 for index, stream in enumerate(streams)}
        groups = defaultdict(list)
        for row in raw['kernels']+raw['copies']:
            if row['end'] <= left or row['start'] >= right:
                continue
            category = 'copy' if 'copyKind' in row else 'attention' if 'k_attn_' in row['name'] else 'native kernels' if row['name'].startswith('native_') else 'other kernels'
            y = tracks[row['streamId']]
            groups[category].append([((max(left,row['start'])-left)/1e6,y),((min(right,row['end'])-left)/1e6,y)])
        for key, y, rows in [('host sync API',0,raw['sync']),('other host API',1,raw['other_apis'])]:
            for row in rows:
                if row['start'] < right and row['end'] > left:
                    groups[key].append([((max(left,row['start'])-left)/1e6,y),((min(right,row['end'])-left)/1e6,y)])
        for category, segments in groups.items():
            axis.add_collection(LineCollection(segments, colors=colors[category], linewidths=6))
        axis.set_yticks(range(len(streams)+2), ['Host sync APIs','Other host APIs']+[f'GPU stream {stream}' for stream in streams])
        axis.set_ylim(-.7,len(streams)+1.7)
        axis.invert_yaxis()
        axis.set_xlim(0,(right-left)/1e6)
        axis.set_title(info['tag']+f" | {info['actual_slots'][0]} GPU expert slots/layer", fontsize=10)
        axis.set_xlabel('Time (ms), 200 ms after client received first token')
        axis.grid(axis='x',alpha=.2)
    fig.legend(handles=[Patch(color=color,label=name) for name,color in colors.items()],loc='upper center',ncol=3,bbox_to_anchor=(.5,.96))
    fig.suptitle('Qwen3.6 | RTX 5060 Ti | CUDA/NVTX traces | Host API spans are not CPU work samples', y=.995)
    fig.tight_layout(rect=(0,0,1,.91))
    plt.rcParams['svg.fonttype'] = 'none'
    fig.savefig(OUT / 'timelines.png', dpi=170)
    fig.savefig(OUT / 'timelines.svg')
    path = OUT / 'timelines.svg'
    path.write_text('\n'.join(line.rstrip() for line in path.read_text(encoding='utf-8').splitlines())+'\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', default='capture-01')
    args = parser.parse_args()
    directory = OUT / args.run_id
    record = json.loads((directory / 'results.json').read_text(encoding='utf-8'))
    assert record['passed'] and record['finished'] and not record['restore_errors'] and len(record['cells']) == 4
    assert record['health_after']['loaded'] and record['daily_config_sha256_before'] == record['daily_config_sha256_after']
    assert all(command['exit_code'] == 0 for command in record['commands'])
    assert record['plan_sha256'] == digest(OUT / 'experiment-plan.md')
    for name, expected in record['scripts'].items():
        assert digest(OUT / name) == expected
    check_identity()
    assert digest(NSYS) == record['nsys']['sha256']
    data = [analyze_cell(directory, cell) for cell in record['cells']]
    checks = {'four_traces': len(data) == 4, 'all_same_chunk_outputs': all(info['same_chunk_output_identical'] for info,_ in data),
              'no_driver_fallback': all(not info['driver_fallback'] for info,_ in data),
              'no_engine_cuda_warnings': all(not info['engine_cuda_warnings'] for info,_ in data),
              'no_explicit_loss_or_error': all(not info['loss_or_error'] for info,_ in data),
              'original_service_restored': True}
    summary = {'date': '2026-10-30', 'verified_at': stamp(), 'run_id': args.run_id, 'revision': record['revision'],
               'binaries': record['binaries'], 'hardware': record['hardware'],
               'bandwidth': {name: record[name]['h2d_GBps'] for name in ['bandwidth-before','bandwidth-after']},
               'nsys_version': record['nsys']['nsys-version']['output'],
               'sampling_environment': record['nsys']['nsys-environment']['output'],
               'checks': checks, 'passed': all(checks.values()), 'reports': [info for info,_ in data],
               'service_restored_at': record['finished'], 'daily_config_unchanged': True,
               'limits': ['one control and one trace per cell, no performance statistics',
                          'client-observed NVTX phase boundaries, clipped intersecting records',
                          'no CPU samples/scheduling/internal expert markers; gaps are not CPU expert time',
                          'automatic expert placement frozen; chunk changes placement too',
                          'no complete bottleneck attribution, Compute counters, kernel optimization or quality claim']}
    save(OUT / 'summary.json', summary)
    csv_rows = []
    for info, _ in data:
        for phase_info in info['phases']:
            csv_rows.append({**{key: info[key] for key in ['tag','chunk','prompt_tokens']},
                             'slots': info['actual_slots'][0],
                             **{key:value for key,value in phase_info.items() if not isinstance(value,(dict,list))}})
    with (OUT / 'phase-results.csv').open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=list(csv_rows[0]))
        writer.writeheader()
        writer.writerows(csv_rows)
    plot(data)
    # Raw reports remain local; this manifest binds them to the small summary.
    files = {path.relative_to(OUT).as_posix(): digest(path) for path in sorted(OUT.rglob('*'))
             if path.is_file() and '__pycache__' not in path.parts and path.name not in ['summary.json','evidence-manifest.json','README.md','bottleneck-notes.md']}
    save(OUT / 'evidence-manifest.json', files)
    summary['local_evidence_files'] = len(files)
    summary['evidence_manifest_sha256'] = digest(OUT / 'evidence-manifest.json')
    save(OUT / 'summary.json', summary)
    print(json.dumps({'checks': checks, 'reports': len(data), 'evidence_files': len(files)}), flush=True)
    if not summary['passed']:
        raise RuntimeError('Trace completeness checks failed; keep results as incomplete')


if __name__ == '__main__':
    main()
