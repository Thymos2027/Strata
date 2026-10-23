"""Clip GPU activity and engine CPU scheduling/samples to the same decode window."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sqlite3
import sys

SCRIPT = Path(__file__).resolve().parent
sys.path.insert(0,str(SCRIPT.parents[1]/'tobeo-20261022/qwen36-profiling'))
from analyze_traces import duration, merge, rows


def intersect(left,right):
    a,b = merge(left),merge(right)
    i=j=0
    result=[]
    while i<len(a) and j<len(b):
        start,end=max(a[i][0],b[j][0]),min(a[i][1],b[j][1])
        if end>start:
            result.append((start,end))
        if a[i][1]<b[j][1]: i+=1
        else: j+=1
    return result


def analyze(database):
    connection=sqlite3.connect(database)
    connection.row_factory=sqlite3.Row
    tables={r[0] for r in connection.execute("select name from sqlite_master where type='table'")}
    ranges=connection.execute("select start,end from NVTX_EVENTS where text='decode-after-first-token'").fetchall()
    if len(ranges)!=1 or ranges[0]['end'] is None:
        raise RuntimeError('Expected one complete decode range')
    start,end=ranges[0]
    kernels=rows(connection,'CUPTI_ACTIVITY_KIND_KERNEL',start,end,'shortName')
    copies=rows(connection,'CUPTI_ACTIVITY_KIND_MEMCPY',start,end)
    sets=rows(connection,'CUPTI_ACTIVITY_KIND_MEMSET',start,end)
    pids={r['globalPid'] for r in kernels}
    if len(pids)!=1:
        raise RuntimeError('Expected one engine process with GPU activity')
    global_pid=pids.pop()
    gpu=merge([(r['start'],r['end']) for r in kernels+copies+sets])
    gaps=[]
    cursor=start
    for a,b in gpu:
        if a>cursor:gaps.append((cursor,a))
        cursor=max(cursor,b)
    if cursor<end:gaps.append((cursor,end))
    samples=[]
    if 'COMPOSITE_EVENTS' in tables:
        samples=[dict(r) for r in connection.execute('select * from COMPOSITE_EVENTS where start>=? and start<? and globalTid>=? and globalTid<? and cpuCycles=1',
                                                    (start,end,global_pid,global_pid+0x1000000))]
    per_thread=Counter(r['globalTid'] for r in samples)
    scheduling=defaultdict(list)
    if 'SCHED_EVENTS' in tables:
        for row in connection.execute('select * from SCHED_EVENTS where start<? and globalTid>=? and globalTid<? order by globalTid,start',
                                      (end,global_pid,global_pid+0x1000000)):
            scheduling[row['globalTid']].append(dict(row))
    running={}
    for tid,events in scheduling.items():
        spans=[]
        for index,event in enumerate(events):
            finish=events[index+1]['start'] if index+1<len(events) else end
            if event['isSchedIn'] and finish>start and event['start']<end:
                spans.append((max(start,event['start']),min(end,finish)))
        if spans:running[tid]=merge(spans)
    names={}
    if 'ThreadNames' in tables:
        names={r[0]:r[1] for r in connection.execute('select t.globalTid,s.value from ThreadNames t join StringIds s on s.id=t.nameId')}
    threads=[]
    for tid in set(running)|set(per_thread):
        spans=running.get(tid,[])
        threads.append({'tid':tid%0x1000000,'global_tid':tid,'name':names.get(tid),
                        'periodic_samples':per_thread[tid],'on_cpu_ms':duration(spans)/1e6,
                        'on_cpu_during_gpu_gaps_ms':duration(intersect(spans,gaps))/1e6})
    threads.sort(key=lambda r:r['on_cpu_ms'],reverse=True)
    diagnostics=[dict(r) for r in connection.execute('select * from DIAGNOSTIC_EVENT')] if 'DIAGNOSTIC_EVENT' in tables else []
    evidence=json.loads(database.with_suffix('.json').read_text())
    if not evidence.get('validation_passed'):
        raise RuntimeError('Output validation did not pass')
    info={'tag':database.stem,'engine_pid':(global_pid//0x1000000)%0x1000000,
          'window_ms':(end-start)/1e6,'gpu_activity_ms':duration(gpu)/1e6,
          'gpu_uncovered_ms':duration(gaps)/1e6,'engine_periodic_samples':len(samples),
          'engine_threads_with_samples':len(per_thread),'engine_threads':threads,
          'engine_on_cpu_union_ms':duration([span for spans in running.values() for span in spans])/1e6,
          'gpu_gaps_with_engine_on_cpu_ms':duration(intersect([span for spans in running.values() for span in spans],gaps))/1e6,
          'cpu_sampling_present':bool(samples),'cpu_scheduling_present':bool(running),
          'attention_union_ms':duration([(r['start'],r['end']) for r in kernels if 'k_attn_part' in r['name']])/1e6,
          'output_validation':evidence['validation'],'tables':sorted(tables),
          'diagnostic_warnings':[r for r in diagnostics if r['severity']>=2],
          'explicit_loss_or_error':[r for r in diagnostics if r['severity']==3 or any(x in r['text'].lower() for x in ['events lost','dropped','overflow'])],
          'limit':'CPU on-CPU overlap is not critical-path attribution; symbols and wait reasons require separate inspection.'}
    module_path=database.with_suffix('.modules.json')
    if module_path.exists() and 'SAMPLING_CALLCHAINS' in tables:
        from resolve_symbols import Resolver
        mapping=json.loads(module_path.read_text())
        if mapping['pid']!=info['engine_pid']:raise RuntimeError('Recorded module PID mismatch')
        image=next(r for r in mapping['modules'] if Path(r['path']).name.lower()=='strata-q36.exe')
        resolver=Resolver(image['path'],image['base'],image['size'])
        hotspots=Counter();locations=Counter();image_samples=unresolved=0;cache={}
        try:
            query='''select cc.originalIP from COMPOSITE_EVENTS e join SAMPLING_CALLCHAINS cc on cc.id=e.id
                     where e.start>=? and e.start<? and e.globalTid>=? and e.globalTid<?
                     and e.cpuCycles=1 and cc.stackDepth=0'''
            for row in connection.execute(query,(start,end,global_pid,global_pid+0x1000000)):
                ip=row[0]
                if not image['base']<=ip<image['base']+image['size']:continue
                image_samples+=1
                if ip not in cache:cache[ip]=resolver.lookup(ip)
                symbol=cache[ip]
                if symbol and symbol['name']:
                    hotspots[symbol['name']]+=1
                    if 'source_line' in symbol:locations[(symbol['name'],symbol['source_file'],symbol['source_line'])]+=1
                else:unresolved+=1
        finally:resolver.close()
        info['engine_image_leaf_samples']=image_samples
        info['unresolved_engine_image_leaf_samples']=unresolved
        info['cpu_leaf_hotspots']=[{'function':name,'periodic_samples':count,
                                  'fraction_of_all_engine_samples':count/len(samples) if samples else 0}
                                 for name,count in hotspots.most_common(20)]
        info['cpu_leaf_locations']=[{'function':key[0],'file':key[1],'line':key[2],'periodic_samples':count}
                                    for key,count in locations.most_common(30)]
        info['symbolization']='Local matching PDB via DbgHelp, using recorded module bases; only periodic leaf PCs, not context-switch stacks.'
    connection.close()
    return info,{'start':start,'end':end,'gpu':gpu,'running':running,'threads':threads}


def plot(raw,output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    fig,axes=plt.subplots(len(raw),1,figsize=(14,4.8*len(raw)),squeeze=False)
    for axis,(info,data) in zip(axes.flat,raw):
        left=data['start']+200_000_000
        right=min(data['end'],left+300_000_000)
        groups=[('GPU activity',data['gpu'])]+[(str(r['tid'])+(' '+r['name'] if r['name'] else ''),data['running'].get(r['global_tid'],[])) for r in data['threads'][:8]]
        for y,(label,intervals) in enumerate(groups):
            spans=[(((max(a,left)-left)/1e6,y),((min(b,right)-left)/1e6,y)) for a,b in intervals if a<right and b>left]
            axis.add_collection(LineCollection(spans,colors='#2563eb' if y==0 else '#169977',linewidths=7))
        axis.set_xlim(0,(right-left)/1e6);axis.set_ylim(-.6,len(groups)-.4)
        axis.set_yticks(range(len(groups)),[r[0] for r in groups]);axis.invert_yaxis()
        axis.set_title(info['tag']+' | 300 ms excerpt after first-token + 200 ms')
        axis.set_xlabel('Time in excerpt (ms)');axis.set_ylabel('Engine thread ID / GPU');axis.grid(axis='x',alpha=.2)
    fig.suptitle('Native Qwen3.6 | CPU pilot | transfer slowdown observed in same session; includes profiler threads')
    fig.tight_layout(rect=(0,0,1,.92))
    plt.rcParams['svg.fonttype']='none'
    fig.savefig(output/'cpu-gpu-timeline.svg');fig.savefig(output/'cpu-gpu-timeline.png',dpi=160)
    svg=output/'cpu-gpu-timeline.svg'
    svg.write_text('\n'.join(r.rstrip() for r in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('archive',type=Path);args=parser.parse_args()
    data=[analyze(args.archive/(case+'-mtp0.sqlite')) for case in ['r0-l1024','r0-l16384']]
    summary={'reports':[r[0] for r in data],
             'checks':{'all_outputs_valid':all(all(r[0]['output_validation'].values()) for r in data),
                       'all_have_engine_samples':all(r[0]['cpu_sampling_present'] for r in data),
                       'all_have_engine_scheduling':all(r[0]['cpu_scheduling_present'] for r in data),
                       'no_explicit_loss_or_error':all(not r[0]['explicit_loss_or_error'] for r in data)}}
    (SCRIPT/'summary.json').write_text(json.dumps(summary,indent=2))
    plot(data,SCRIPT)
    print(json.dumps([{k:r[0][k] for k in ['tag','window_ms','gpu_activity_ms','gpu_uncovered_ms','engine_periodic_samples','cpu_scheduling_present']} for r in data],indent=2))


if __name__=='__main__':main()
