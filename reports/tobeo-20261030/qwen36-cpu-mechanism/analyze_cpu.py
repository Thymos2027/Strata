"""Same-window periodic leaf PCs and scheduling; never turn parallel CPU time into latency."""
import bisect,json,sqlite3,sys
from collections import Counter,defaultdict
from pathlib import Path

OUT=Path(__file__).resolve().parent
from capture import host,digest,save,stamp,pid
from analyze_systems import merge,duration,intersect
from resolve_symbols import Resolver


def classify(symbol,module):
    name=(symbol or {}).get('name','');file=(symbol or {}).get('source_file','');line=(symbol or {}).get('source_line',0)
    if module.lower()=='strata-q36.exe':
        if 'ExpertPool::worker' in name and file=='pool.cpp' and 1000<=line<=1028:return 'pool_idle_wait_loop'
        if any(x in name for x in ['vec_dot','native_gu_rows','native_down_rows','quantize_row','native_quant']):return 'CPU_arithmetic_or_quantization'
        if 'cudaEventQuery' in name:return 'CUDA_event_query'
        if 'ExpertPool::' in name:return 'pool_control_or_join'
        return 'other_engine_code' if symbol else 'unresolved_engine_code'
    m=module.lower()
    if any(x in m for x in ['injection','cupti','nsight']):return 'profiler_module'
    if any(x in m for x in ['nvcuda','cudart','nvwgf','nvldumdx']):return 'CUDA_driver_module'
    if module:return 'other_module'
    return 'unmapped'


def cell(directory,tag):
    record=json.loads((directory/(tag+'-trace.json')).read_text(encoding='utf-8'))
    plain=json.loads((directory/(tag+'-plain.json')).read_text(encoding='utf-8'))
    assert record['passed'] and plain['passed'] and record['output_ids']==plain['output_ids']
    mapping=json.loads((directory/(tag+'-trace.modules.json')).read_text(encoding='utf-8'))
    assert mapping['pid']==record['engine_pid']
    image=next(x for x in mapping['modules'] if Path(x['path']).name.lower()=='strata-q36.exe')
    resolver=Resolver(image['path'],image['base'],image['size']);symbols={}
    db=sqlite3.connect('file:'+(directory/(tag+'-trace.sqlite')).as_posix()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    windows=db.execute("select start,end from NVTX_EVENTS where text='decode-after-first-token'").fetchall();assert len(windows)==1
    start,end=windows[0];assert end>start
    gpu=[];global_pid=None
    for table in ['CUPTI_ACTIVITY_KIND_KERNEL','CUPTI_ACTIVITY_KIND_MEMCPY','CUPTI_ACTIVITY_KIND_MEMSET']:
        for x in db.execute('select start,end,globalPid from '+table+' where start<? and end>?',(end,start)):
            if pid(x['globalPid'])!=record['engine_pid']:continue
            if table=='CUPTI_ACTIVITY_KIND_KERNEL':global_pid=x['globalPid']
            gpu.append((max(start,x['start']),min(end,x['end'])))
    assert global_pid is not None
    gpu=merge(gpu);gaps=[];cursor=start
    for a,b in gpu:
        if a>cursor:gaps.append((cursor,a))
        cursor=max(cursor,b)
    if cursor<end:gaps.append((cursor,end))
    assert duration(gpu)+duration(gaps)==end-start
    sched=defaultdict(list)
    for row in db.execute('select start,globalTid,isSchedIn from SCHED_EVENTS where globalTid>=? and globalTid<? and start<? order by globalTid,start',(global_pid,global_pid+0x1000000,end)):
        sched[row['globalTid']].append(dict(row))
    running={}
    for tid,events in sched.items():
        intervals=[]
        for i,e in enumerate(events):
            finish=events[i+1]['start'] if i+1<len(events) else end
            if e['isSchedIn'] and finish>start:intervals.append((max(start,e['start']),min(end,finish)))
        if intervals:running[tid]=merge(intervals)
    points=[];hotspots=Counter();locations=Counter();classes=Counter();modules=Counter();per_thread=defaultdict(Counter)
    gap_classes=Counter();unresolved=0;engine_samples=0
    gap_starts=[x[0] for x in gaps]
    query='''select e.start,e.globalTid,cc.originalIP from COMPOSITE_EVENTS e join SAMPLING_CALLCHAINS cc on cc.id=e.id
             where e.start>=? and e.start<? and e.globalTid>=? and e.globalTid<? and e.cpuCycles=1 and cc.stackDepth=0'''
    try:
        for row in db.execute(query,(start,end,global_pid,global_pid+0x1000000)):
            time,tid,ip=row;module=next((x for x in mapping['modules'] if x['base']<=ip<x['base']+x['size']),None)
            module_name=Path(module['path']).name if module else ''
            symbol=None
            if module_name.lower()=='strata-q36.exe':
                engine_samples+=1
                if ip not in symbols:symbols[ip]=resolver.lookup(ip)
                symbol=symbols[ip]
                if not symbol:unresolved+=1
            category='kernel_address_unresolved' if ip<0 else classify(symbol,module_name)
            classes[category]+=1;modules[module_name or ('<kernel address>' if ip<0 else '<unmapped>')]+=1;per_thread[tid][category]+=1
            if symbol:
                hotspots[symbol['name']]+=1
                locations[(symbol['name'],symbol.get('source_file',''),symbol.get('source_line',0))]+=1
            index=bisect.bisect_right(gap_starts,time)-1
            in_gap=index>=0 and time<gaps[index][1]
            if in_gap:gap_classes[category]+=1
            points.append({'time':time,'tid':tid,'category':category})
    finally:resolver.close()
    assert len(points)>=50 and running and engine_samples and unresolved==0,(len(points),len(running),engine_samples,unresolved)
    diagnostics=[dict(x) for x in db.execute('select * from DIAGNOSTIC_EVENT')]
    errors=[x for x in diagnostics if x['severity']==3 or any(k in x['text'].lower() for k in ['events lost','dropped','overflow','not supported by this build'])]
    assert not errors,errors
    threads=[]
    for tid in set(running)|set(per_thread):
        spans=running.get(tid,[])
        threads.append({'tid':tid%0x1000000,'global_tid':tid,'on_cpu_ms':duration(spans)/1e6,
                        'on_cpu_during_gpu_gaps_ms':duration(intersect(spans,gaps))/1e6,
                        'periodic_samples':sum(per_thread[tid].values()),'leaf_classes':dict(per_thread[tid])})
    threads.sort(key=lambda x:x['on_cpu_ms'],reverse=True)
    query_names={x[0] for x in db.execute("select id from StringIds where value like 'cudaEventQuery%'")}
    query_spans=[];query_status=Counter();query_threads=Counter()
    if query_names:
        for row in db.execute('select start,end,globalTid,returnValue from CUPTI_ACTIVITY_KIND_RUNTIME where nameId in ('+','.join(map(str,query_names))+') and start<? and end>?',(end,start)):
            if pid(row['globalTid'])==record['engine_pid']:
                query_spans.append((max(start,row['start']),min(end,row['end'])));query_status[row['returnValue']]+=1;query_threads[row['globalTid']]+=1
    db.close()
    all_running=merge([x for v in running.values() for x in v])
    summary={'tag':tag,'engine_pid':record['engine_pid'],'window_ms':(end-start)/1e6,'gpu_union_ms':duration(gpu)/1e6,
             'gpu_uncovered_ms':duration(gaps)/1e6,'engine_on_cpu_union_ms':duration(all_running)/1e6,
             'gpu_gaps_with_engine_on_cpu_ms':duration(intersect(all_running,gaps))/1e6,
             'periodic_leaf_samples':len(points),'engine_image_samples':engine_samples,'unresolved_engine_samples':unresolved,
             'leaf_classes':dict(classes),'leaf_classes_during_gpu_gaps':dict(gap_classes),'leaf_modules':dict(modules),
             'top_engine_functions':[{'function':k,'samples':v} for k,v in hotspots.most_common(20)],
             'top_engine_lines':[{'function':k[0],'file':k[1],'line':k[2],'samples':v} for k,v in locations.most_common(30)],
             'threads':threads,'diagnostic_warnings':[x for x in diagnostics if x['severity']>=2],
             'cudaEventQuery':{'calls':sum(query_status.values()),'return_values':dict(query_status),
                               'call_threads':{str(t%0x1000000):v for t,v in query_threads.items()},
                               'return_value_limit':'Raw serialized field; event readiness is not inferred from this field.',
                               'API_union_ms':duration(query_spans)/1e6,'API_during_gpu_gaps_ms':duration(intersect(query_spans,gaps))/1e6},
             'profile_to_plain_ratios':{'prefill':record['prompt_ms']/plain['prompt_ms'],'decode':record['decode_ms']/plain['decode_ms']},
             'plain':{k:plain[k] for k in ['prompt_ms','decode_ms','process_cpu_s']},
             'profiled':{k:record[k] for k in ['prompt_ms','decode_ms','process_cpu_s']}}
    main=max(query_threads,key=query_threads.get)
    workers=[t['global_tid'] for t in threads if t['leaf_classes'].get('pool_idle_wait_loop',0)>20]
    assert len(workers)==7,(tag,workers)
    summary['cuda_submission_thread']=main%0x1000000;summary['pool_worker_tids']=[t%0x1000000 for t in workers]
    return summary,{'start':start,'end':end,'gpu':gpu,'gaps':gaps,'running':running,'points':points,'threads':threads,'display_tids':[main,*workers]}


def plot(cells):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    fig,axes=plt.subplots(len(cells),1,figsize=(14,3.4*len(cells)),layout='constrained')
    colors={'pool_idle_wait_loop':'#e69f00','CPU_arithmetic_or_quantization':'#d55e00','CUDA_driver_module':'#7b3294','profiler_module':'#666666'}
    for ax,(info,raw) in zip(axes,cells):
        origin=raw['start'];left,right=200,500
        def bars(spans,y,color):
            visible=[((max(a,origin+left*1e6)-origin)/1e6,(min(b,origin+right*1e6)-max(a,origin+left*1e6))/1e6) for a,b in spans if a<origin+right*1e6 and b>origin+left*1e6]
            if visible:ax.broken_barh(visible,(y-.28,.56),facecolors=color)
        bars(raw['gpu'],0,'#0072b2');labels=['GPU union']
        for y,tid in enumerate(raw['display_tids'],1):
            bars(raw['running'].get(tid,[]),y,'#a9d9b9')
            for category,color in {**colors,'other':'#333333'}.items():
                pts=[(x['time']-origin)/1e6 for x in raw['points'] if x['tid']==tid and left<=(x['time']-origin)/1e6<=right and (x['category']==category if category!='other' else x['category'] not in colors)]
                ax.scatter(pts,[y]*len(pts),s=6,color=color,zorder=3)
            labels.append(('host ' if y==1 else 'worker ')+str(tid%0x1000000))
        ax.set_yticks(range(len(labels)),labels);ax.set_xlim(left,right);ax.set_ylim(len(labels)-.4,-.6)
        ax.set_title(info['tag']);ax.set_xlabel('ms after first token received');ax.grid(axis='x',alpha=.2)
    fig.legend(handles=[Patch(color='#a9d9b9',label='scheduled on CPU (includes spin)'),*[Patch(color=c,label=k) for k,c in colors.items()]],loc='outside lower center',ncols=3,fontsize=8)
    fig.suptitle('Fixed Qwen3.6 binaries | points: sampled leaf PC | CPU overlap is not critical-path time')
    fig.savefig(OUT/'timeline.png',dpi=140);plt.close(fig)


def main():
    directory=OUT/'capture-01';r=json.loads((directory/'results.json').read_text(encoding='utf-8'))
    assert r['passed'] and r['finished'] and not r['restore_errors']
    assert r['script_sha256']==digest(OUT/'capture.py') and r['plan_sha256']==digest(OUT/'experiment-plan.md')
    cells=[cell(directory,tag) for tag in ['baseline-r0-l1024','baseline-r0-l16384','on-r0-l16384']]
    save(OUT/'cpu-summary.json',{'verified_at':stamp(),'cells':[x[0] for x in cells],
         'limits':['500Hz leaf IP, not full stacks','one trace per cell; injected threads remain in denominator',
                   'CPU-on-CPU includes idle spin; parallel per-thread durations are not elapsed time',
                   'no direct CPU expert job markers; not a complete causal critical path']})
    plot(cells)
    print(json.dumps([{k:x[0][k] for k in ['tag','window_ms','periodic_leaf_samples','leaf_classes','gpu_uncovered_ms','gpu_gaps_with_engine_on_cpu_ms','profile_to_plain_ratios']} for x in cells]))


if __name__=='__main__':main()
