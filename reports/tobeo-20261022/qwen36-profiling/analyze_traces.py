"""Analyze clipped decode intervals, preserving diagnostics and overlap semantics.

Expects nsys export --type sqlite outputs in cuda133-process/. Does not infer that GPU
gaps are CPU expert time, or that summed kernel durations are a critical path.
"""
from collections import defaultdict
import json
from pathlib import Path
import sqlite3
import statistics

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Patch

OUT = Path(__file__).resolve().parent / 'cuda133-process'


def merge(intervals):
    merged = []
    for a, b in sorted(intervals):
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    return merged


def duration(intervals):
    return sum(b-a for a, b in merge(intervals))


def rows(connection, table, start, end, name_column=None):
    names = {r[1] for r in connection.execute('pragma table_info(' + table + ')')}
    if not names:
        return []
    join = ' join StringIds s on s.id=e.' + name_column if name_column else ''
    extra = ',s.value as name' if name_column else ''
    query = 'select e.*' + extra + ' from ' + table + ' e' + join + ' where e.start<? and e.end>?'
    result = []
    for row in connection.execute(query, (end, start)):
        r = dict(row)
        r['start'], r['end'] = max(start, r['start']), min(end, r['end'])
        result.append(r)
    return result


def analyze(tag):
    evidence = json.loads((OUT / (tag + '.json')).read_text())
    baseline = json.loads((OUT.parent.parent / 'qwen36-context-curve/results.json').read_text())
    ref = next(r for r in baseline['rows'] if r['case'] == evidence['case'] and r['mtp'] == evidence['mtp'])
    if (not evidence.get('validation_passed') or evidence['prompt_ids_sha256'] != ref['prompt_ids_sha256']
            or evidence['output_ids'] != ref['output_ids'][:evidence['generated_tokens']]):
        raise RuntimeError('Input/output or protocol validation failed: ' + tag)
    connection = sqlite3.connect(OUT / (tag + '.sqlite'))
    connection.row_factory = sqlite3.Row
    ranges = connection.execute("select start,end from NVTX_EVENTS where text='decode-after-first-token'").fetchall()
    if len(ranges) != 1 or ranges[0]['end'] is None:
        raise RuntimeError('Expected one complete decode NVTX range: ' + tag)
    start, end = ranges[0]
    kernels = rows(connection, 'CUPTI_ACTIVITY_KIND_KERNEL', start, end, 'shortName')
    copies = rows(connection, 'CUPTI_ACTIVITY_KIND_MEMCPY', start, end)
    sets = rows(connection, 'CUPTI_ACTIVITY_KIND_MEMSET', start, end)
    apis = rows(connection, 'CUPTI_ACTIVITY_KIND_RUNTIME', start, end, 'nameId')
    by_name = defaultdict(list)
    for r in kernels:
        by_name[r['name']].append(r)
    top = []
    for name, values in by_name.items():
        times = [r['end'] - r['start'] for r in values]
        top.append({'name': name, 'calls_intersecting_window': len(values), 'sum_ms': sum(times)/1e6,
                    'mean_us': statistics.mean(times)/1000, 'median_us': statistics.median(times)/1000,
                    'union_ms': duration([(r['start'],r['end']) for r in values])/1e6})
    top.sort(key=lambda r: r['sum_ms'], reverse=True)
    api_totals = defaultdict(lambda: [0, 0])
    for r in apis:
        api_totals[r['name']][0] += 1
        api_totals[r['name']][1] += r['end'] - r['start']
    kernel_intervals = [(r['start'], r['end']) for r in kernels]
    copy_intervals = [(r['start'], r['end']) for r in copies]
    set_intervals = [(r['start'], r['end']) for r in sets]
    kernel_ns, copy_ns = duration(kernel_intervals), duration(copy_intervals)
    all_ns = duration(kernel_intervals + copy_intervals + set_intervals)
    attention = [(r['start'],r['end']) for r in kernels if 'k_attn_part' in r['name']]
    diagnostics = [dict(r) for r in connection.execute('select * from DIAGNOSTIC_EVENT')]
    warnings = [r for r in diagnostics if r['severity'] >= 2]
    info = {'tag': tag, 'window_ms': (end-start)/1e6,
            'prompt_ids_sha256': evidence['prompt_ids_sha256'], 'output_sha256': evidence['output_sha256'],
            'source_revision': evidence['source_revision'], 'exe_sha256': evidence['exe_sha256'],
            'capture_validation': evidence['validation'],
            'request_subsequent_output_tokens': evidence['generated_tokens']-1,
            'kernel_count': len(kernels), 'copy_count': len(copies), 'memset_count': len(sets),
            'graph_node_kernel_count': sum(r['graphNodeId'] is not None for r in kernels),
            'kernel_process_ids': sorted({r['globalPid'] for r in kernels}),
            'kernel_union_ms': kernel_ns/1e6, 'copy_union_ms': copy_ns/1e6,
            'kernel_copy_overlap_ms': (kernel_ns + copy_ns - duration(kernel_intervals+copy_intervals))/1e6,
            'gpu_activity_union_ms': all_ns/1e6, 'gpu_uncovered_ms': ((end-start)-all_ns)/1e6,
            'attention_part_union_ms': duration(attention)/1e6,
            'attention_part_wall_fraction': duration(attention)/(end-start),
            'top_kernels': top,
            'runtime_apis': sorted([{'name': k, 'calls': v[0], 'sum_ms': v[1]/1e6}
                                    for k,v in api_totals.items()], key=lambda r:r['sum_ms'], reverse=True),
            'cuda_graph_launch_calls': sum(v[0] for k,v in api_totals.items() if 'cudaGraphLaunch' in k),
            'diagnostic_warnings': warnings,
            'driver_compatibility_warnings': [r for r in warnings if 'not supported by this build' in r['text']],
            'explicit_loss_or_error_diagnostics': [r for r in diagnostics if r['severity'] == 3 or
                    any(word in r['text'].lower() for word in ('dropped', 'overflow', 'events lost'))],
            'same_output_as_phase_b_prefix': evidence['same_output_as_phase_b']}
    info['engine_cuda_diagnostic_warnings'] = [r for r in warnings
        if r['globalPid'] in info['kernel_process_ids'] and 'CUDA' in r['text']]
    assert kernels and attention and info['same_output_as_phase_b_prefix']
    connection.close()
    return info, (start, end, kernels, copies)


def plot_timelines(data):
    fig, axes = plt.subplots(4, 1, figsize=(14, 10))
    colors = {'attention': '#e67e22', 'native_*': '#2563eb', 'other': '#8c98a8', 'copy': '#16856b'}
    for axis, (info, raw) in zip(axes, data):
        start, end, kernels, copies = raw
        # Same fixed 300 ms excerpt, 200 ms after the client-observed decode start.
        left, right = start + 200_000_000, min(end, start + 500_000_000)
        if right <= left:
            raise RuntimeError('Decode window too short for excerpt')
        streams = sorted({r['streamId'] for r in kernels+copies if r['start']<right and r['end']>left})
        positions = {stream: i for i,stream in enumerate(streams)}
        groups = defaultdict(list)
        for r in kernels+copies:
            if r['end'] <= left or r['start'] >= right:
                continue
            name = r.get('name', '')
            category = ('copy' if 'copyKind' in r else 'attention' if 'k_attn_' in name
                        else 'native_*' if name.startswith('native_') else 'other')
            y = positions[r['streamId']]
            groups[category].append([((max(left,r['start'])-left)/1e6, y),
                                      ((min(right,r['end'])-left)/1e6, y)])
        for category, segments in groups.items():
            axis.add_collection(LineCollection(segments, colors=colors[category], linewidths=7))
        axis.set_xlim(0, (right-left)/1e6)
        axis.set_ylim(-0.7,len(streams)-0.3)
        axis.set_yticks(list(range(len(streams))), [str(s) for s in streams])
        axis.set_ylabel('GPU stream')
        axis.set_title(info['tag'] + ' | 300 ms excerpt, starting 200 ms after client first-token boundary', fontsize=10)
        axis.set_xlabel('Time in excerpt (ms)')
        axis.grid(axis='x', alpha=0.2)
    fig.legend(handles=[Patch(color=c,label=k) for k,c in colors.items()], loc='upper center', ncol=4,
               bbox_to_anchor=(0.5,0.955))
    fig.suptitle('Native Qwen3.6 | RTX 5060 Ti | CUDA tracing | CPU work is not shown', y=0.995)
    fig.tight_layout(rect=(0,0,1,0.92))
    plt.rcParams['svg.fonttype'] = 'none'
    fig.savefig(OUT / 'decode-timelines.png',dpi=180)
    fig.savefig(OUT / 'decode-timelines.svg')
    p=OUT/'decode-timelines.svg'
    p.write_text('\n'.join(s.rstrip() for s in p.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')


def main():
    data = [analyze(case+'-mtp'+str(mtp)) for mtp in (0,2) for case in ('r0-l1024','r0-l16384')]
    installed = json.loads((OUT.parent/'nsight-installed-13.3.1.json').read_text())
    summary = {'reports': [r[0] for r in data],
               'nsight_archive_sha256': installed['sha256'], 'nsight_version': installed['version'],
               'checks': {
                   'four_reports': len(data) == 4,
                   'all_input_output_protocol_checks': all(all(info['capture_validation'].values()) for info,_ in data),
                   'all_have_engine_gpu_activity': all(len(info['kernel_process_ids']) == 1 for info,_ in data),
                   'no_driver_fallback': all(not info['driver_compatibility_warnings'] for info,_ in data),
                   'no_engine_cuda_warnings': all(not info['engine_cuda_diagnostic_warnings'] for info,_ in data),
                   'no_explicit_loss_or_error_diagnostics': all(not info['explicit_loss_or_error_diagnostics'] for info,_ in data)},
               'notes': 'All intervals clipped to client decode NVTX range; union is not critical-path attribution.'}
    (OUT/'trace-summary.json').write_text(json.dumps(summary,indent=2))
    plot_timelines(data)
    print(json.dumps([{k:v for k,v in info.items() if k not in ('top_kernels','runtime_apis','diagnostic_warnings')}
                      for info,_ in data],indent=2))


if __name__ == '__main__':
    main()
