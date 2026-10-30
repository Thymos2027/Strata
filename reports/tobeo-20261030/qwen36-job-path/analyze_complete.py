"""Validate every task/phase/token and build measured fork/join path ledgers."""
import bisect,csv,json,re,sqlite3,sys
from collections import Counter,defaultdict
from pathlib import Path
from build_complete import OUT,host,digest,save,stamp
sys.path.insert(0,str(OUT.parent/'qwen36-systems'))
from analyze_systems import merge,duration,intersect,pid

EPS=10000 # ns: classification ambiguity band, not a timestamp correction


def ns(row):return row['end']-row['start']
def spans(rows):return [(x['start'],x['end']) for x in rows]
def inside(a,b):return b['start']<=a['start'] and a['end']<=b['end']
def csvfile(path,rows):
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def case(directory,name):
    trace=json.loads((directory/(name+'-on-trace.json')).read_text(encoding='utf-8'));assert trace['passed']
    path=directory/(name+'-on-trace.sqlite')
    db=sqlite3.connect('file:'+path.as_posix()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    request=db.execute("select start,end from NVTX_EVENTS where text='request'").fetchall();assert len(request)==1
    req0,req1=request[0]
    pids={pid(x[0]) for x in db.execute('select distinct globalPid from CUPTI_ACTIVITY_KIND_KERNEL')};assert pids=={trace['engine_pid']}
    rows=db.execute('select start,end,globalTid,text from NVTX_EVENTS where start>=? and start<? and text like \'JT %\' order by start',(req0,req1))
    kinds=defaultdict(list)
    for raw in rows:
        r=dict(raw);assert pid(r['globalTid'])==trace['engine_pid']
        r.update({k:int(v) for k,v in re.findall(r'([A-Za-z_]+)=(-?\d+)',r['text'])})
        r['kind']=r['text'].split()[1]
        if r['kind'] not in ['publish','done']:assert r['end'] is not None and r['end']>=r['start']
        kinds[r['kind']].append(r)
    tokens=kinds['token'];assert len(tokens)==63
    assert set(done_epoch['epoch'] for done_epoch in kinds['done'])==set(x['epoch'] for x in kinds['phase'])
    count=1025 if name=='r0-l1024' else 16385
    assert [x['pos'] for x in tokens]==list(range(count,count+63))
    assert [x['output'] for x in tokens]==list(range(1,64))
    assert len({x['globalTid'] for x in tokens})==1
    main=tokens[0]['globalTid']
    assert all(tokens[i]['end']<=tokens[i+1]['start'] for i in range(62))
    # API correlation maps only submissions/sync, excluding millions of query calls.
    api_names={x['id']:x['value'] for x in db.execute("select id,value from StringIds where value like '%LaunchKernel%' or value like '%Memcpy%' or value like '%Memset%' or value like '%StreamSynchronize%' or value like '%GraphLaunch%' or value like '%StreamWaitEvent%'")}
    apis={x['correlationId']:dict(x) for x in db.execute('select * from CUPTI_ACTIVITY_KIND_RUNTIME where nameId in ('+','.join(map(str,api_names))+') and start>=? and start<?',(req0,req1)) if pid(x['globalTid'])==trace['engine_pid']}
    gpu=[]
    for table,kind in [('CUPTI_ACTIVITY_KIND_KERNEL','kernel'),('CUPTI_ACTIVITY_KIND_MEMCPY','copy'),('CUPTI_ACTIVITY_KIND_MEMSET','set')]:
        extra=',s.value as name' if kind=='kernel' else ''
        join=' join StringIds s on s.id=g.shortName' if kind=='kernel' else ''
        for raw in db.execute('select g.*'+extra+' from '+table+' g'+join+' where g.start<? and g.end>?',(req1,req0)):
            r=dict(raw)
            if pid(r['globalPid'])!=trace['engine_pid']:continue
            r['kind']=kind;r['uid']=len(gpu);r['api']=apis.get(r['correlationId'])
            gpu.append(r)
    by_stream=defaultdict(list)
    for x in gpu:by_stream[x['streamId']].append(x)
    previous={}
    for stream,ops in by_stream.items():
        ops.sort(key=lambda x:(x['start'],x['end']))
        for i,x in enumerate(ops):previous[x['uid']]=ops[i-1] if i else None
    submissions=sorted([x for x in gpu if x['api']],key=lambda x:x['api']['start'])
    submission_starts=[x['api']['start'] for x in submissions]
    def submitted(scope,kind=None):
        a=bisect.bisect_left(submission_starts,scope['start']);b=bisect.bisect_right(submission_starts,scope['end'])
        return [x for x in submissions[a:b] if kind is None or x['kind']==kind]
    # Native scopes are on the main thread; workers share epoch, not time nesting.
    cpus=kinds['cpu'];cpu_starts=[x['start'] for x in cpus]
    phases=kinds['phase'];phase_by_epoch={x['epoch']:x for x in phases};assert len(phase_by_epoch)==len(phases)
    jobs=defaultdict(list)
    for x in kinds['job']:jobs[x['epoch']].append(x)
    marks={x['epoch']:x for x in kinds['publish']}
    done=defaultdict(list)
    for x in kinds['done']:done[x['epoch']].append(x)
    hostparts={k:{x['epoch']:x for x in kinds[k]} for k in ['park_before','host_drain','wait_done','park_after']}
    phase_rows=[];phase_info={};who_tids=defaultdict(set);raw_jobs=[]
    for phase in phases:
        epoch=phase['epoch'];js=jobs[epoch];n=phase['tasks'];R=phase['rows'];per=phase['per']
        assert phase['mode'] in [5,6] and phase['sliced']==0 and per>0 and R%per==0
        assert len(js)==n and sorted(x['task'] for x in js)==list(range(n))
        mark=marks[epoch];assert phase['start']<=mark['start']<=phase['end']
        before=hostparts['park_before'][epoch];hd=hostparts['host_drain'][epoch];wd=hostparts['wait_done'][epoch];pa=hostparts['park_after'][epoch]
        assert all(inside(x,phase) for x in [before,hd,wd,pa])
        assert before['end']<=mark['start']<=hd['start']<=hd['end']<=wd['start']<=wd['end']<=pa['start']
        completions=done[epoch]
        assert len(completions)==n and sorted(x['ordinal'] for x in completions)==list(range(1,n+1))
        assert sorted(x['task'] for x in completions)==list(range(n))
        completed={x['task']:x for x in completions}
        by_who=defaultdict(list)
        for job in js:
            assert job['mode']==phase['mode'] and mark['start']<=job['start']<=job['end']<=phase['end']
            assert -1<=job['who']<=6
            if job['who']==-1:assert inside(job,hd) and job['globalTid']==main
            completion=completed[job['task']]
            assert completion['who']==job['who'] and completion['mode']==job['mode'] and completion['globalTid']==job['globalTid']
            assert job['end']<=completion['start']<=phase['end']
            who_tids[job['who']].add(job['globalTid']);by_who[job['who']].append(job)
            g0=R*job['task']//n;g1=R*(job['task']+1)//n;assert g1>g0
            raw_jobs.append({'case':name,'epoch':epoch,'mode':phase['mode'],'task':job['task'],'who':job['who'],
                             'tid':job['globalTid']%16777216,'completion_ordinal':completion['ordinal'],'completion_marker_ns':completion['start'],'row_begin':g0,'row_end':g1,'start_ns':job['start'],'end_ns':job['end']})
        bounds=[(R*i//n,R*(i+1)//n) for i in range(n)]
        assert bounds[0][0]==0 and bounds[-1][1]==R and all(bounds[i][1]==bounds[i+1][0] for i in range(n-1))
        for chain in by_who.values():
            chain.sort(key=lambda x:x['start']);assert all(a['end']<=b['start'] for a,b in zip(chain,chain[1:]))
        terminal=max(completions,key=lambda x:x['ordinal']);last=next(x for x in js if x['task']==terminal['task'])
        last_body=max(js,key=lambda x:x['end']);chain=by_who[last['who']]
        assert chain[-1]['task']==last['task'] and max(x['end'] for x in js)<=terminal['start']
        pre=mark['start']-phase['start'];body=sum(ns(x) for x in chain)
        queue=terminal['start']-mark['start']-body;tail=phase['end']-terminal['start']
        startup=chain[0]['start']-mark['start'];between=sum(b['start']-a['end'] for a,b in zip(chain,chain[1:]))
        publication_gap=terminal['start']-last['end']
        assert startup+between+publication_gap==queue
        assert pre>=0 and queue>=0 and tail>=0 and pre+body+queue+tail==ns(phase)
        tail_done=duration(intersect([(terminal['start'],phase['end'])],spans([wd])))
        tail_park=duration(intersect([(terminal['start'],phase['end'])],spans([pa])))
        idx=bisect.bisect_right(cpu_starts,phase['start'])-1;assert idx>=0
        cpu=cpus[idx];assert inside(phase,cpu)
        row={'case':name,'moe':cpu['moe'],'forward':cpu['f'],'layer':cpu['li'],'epoch':epoch,'mode':phase['mode'],
             'tasks':n,'rows':R,'rows_per_expert':per,'experts':R//per,'start_ns':phase['start'],'end_ns':phase['end'],
             'wall_ns':ns(phase),'pre_publish_ns':pre,'critical_who':last['who'],'last_completion_task':last['task'],
             'critical_chain_job_body_ns':body,'critical_chain_handoff_and_queue_ns':queue,'phase_tail_ns':tail,
             'critical_chain_startup_ns':startup,'critical_chain_between_jobs_ns':between,'last_completion_publication_gap_ns':publication_gap,
             'last_release_task':last['task'],'last_release_ordinal':terminal['ordinal'],'last_body_proxy_task':last_body['task'],
             'last_release_differs_from_last_body':int(last['task']!=last_body['task']),
             'other_marker_after_last_release_ns':max(x['start'] for x in completions)-terminal['start'],
             'critical_chain_task_ids':';'.join(str(x['task']) for x in chain),
             'tail_wait_done_ns':tail_done,'tail_park_ns':tail_park,'tail_other_ns':tail-tail_done-tail_park,
             'host_wait_done_wall_ns':ns(wd),'host_park_before_wall_ns':ns(before),'host_park_after_wall_ns':ns(pa),
             'host_drain_wall_ns':ns(hd),
             'near_last_jobs_1us':sum(last_body['end']-x['end']<=1000 for x in js)}
        phase_rows.append(row);phase_info[epoch]=row
    assert set(jobs)==set(phase_by_epoch) and all(len(x)==1 for x in who_tids.values())
    assert set(who_tids)==set(range(-1,7))
    by_moe=defaultdict(list)
    for row in phase_rows:by_moe[row['moe']].append(row)
    gpu_moes={x['moe']:x for x in kinds['gpu']};pools={x['moe']:x for x in kinds['pool']};routes={x['moe']:x for x in kinds['route']}
    token_rows=[];moe_details=[];plot_raw=[]
    for token in tokens:
        cs=[x for x in cpus if inside(x,token)];gs=[gpu_moes[x['moe']] for x in cs]
        assert len(cs)==40 and sorted(x['li'] for x in cs)==list(range(40))
        fw=[x for x in kinds['forward'] if inside(x,token)];assert len(fw)==1 and fw[0]['T']==1 and fw[0]['pos']==token['pos']
        assert all(x['f']==fw[0]['id'] and x['T']==1 and x['globalTid']==main for x in cs+gs)
        assert all(inside(g,token) for g in gs)
        rs=[routes[x['moe']] for x in cs];assert all(inside(r,c) for r,c in zip(rs,cs))
        prs=[x for c in cs for x in by_moe[c['moe']]]
        late=[];classes=Counter();max_clock_error=0;dispatch=[]
        for c,g in zip(cs,gs):
            assert g['end']<=c['start']
            ps=sorted(by_moe[c['moe']],key=lambda x:x['start_ns'])
            if c['moe'] in pools:
                pool=pools[c['moe']];assert inside(pool,c) and len(ps)==2 and [x['mode'] for x in ps]==[5,6]
                assert all(x['experts']==pool['experts'] for x in ps)
                assert ps[0]['end_ns']<=ps[1]['start_ns']
                upload=[x for x in submitted(c,'copy') if x['copyKind']==1 and x['api']['start']>=pool['end']]
                merge_k=[x for x in submitted(c,'kernel') if 'k_merge_cpu' in x.get('name','')]
                assert len(upload)==2 and len(merge_k)==1
                assert len({x['streamId'] for x in upload+merge_k})==1
                merge_skew=max(0,max(x['end'] for x in upload)-merge_k[0]['start']);assert merge_skew<=EPS
                first=min(upload,key=lambda x:x['api']['start']);pred=previous[first['uid']];assert pred
                submit=first['api'];delta=submit['start']-pred['end']
                if delta>EPS:
                    category='host_submission_later';late.append((pred['end'],min(submit['start'],first['start'])))
                elif pred['end']>submit['end']+EPS:category='GPU_predecessor_later'
                else:category='within_10us_ambiguity'
                classes[category]+=1
                route_copies=[x for x in submitted(g,'copy') if x['copyKind']==2];assert len(route_copies)==2
                route_end=max(x['end'] for x in route_copies);clock_error=max(0,route_end-routes[c['moe']]['end'])
                max_clock_error=max(max_clock_error,clock_error);assert clock_error<=EPS
                half_kernels=submitted(g,'kernel');assert half_kernels
                early=min(half_kernels,key=lambda x:x['api']['start']);early_previous=previous[early['uid']];assert early_previous
                assert early['api']['end']<=pool['start']
                visible_gap=(early_previous['end'],early['start'])
                assert visible_gap[1]>=visible_gap[0]-EPS
                visible_gap=[visible_gap] if visible_gap[1]>visible_gap[0] else []
                dispatch_row={'first_GPU_half_kernel':early['name'],'GPU_half_API_exit_ns':early['api']['end'],
                              'GPU_half_predecessor_end_ns':early_previous['end'],'GPU_half_start_ns':early['start'],
                              'pool_start_ns':pool['start'],'pool_end_ns':pool['end'],
                              'GPU_half_start_after_pool':int(early['start']>=pool['end']),
                              'GPU_half_submit_to_start_ns':max(0,early['start']-early['api']['end']),
                              'GPU_half_visible_gap_ns':duration(visible_gap),
                              'GPU_half_gap_overlap_pool_ns':duration(intersect(visible_gap,spans([pool])))}
                dispatch.append(dispatch_row)
                moe_details.append({'case':name,'token_pos':token['pos'],'moe':c['moe'],'layer':c['li'],
                                    'GU_epoch':ps[0]['epoch'],'DOWN_epoch':ps[1]['epoch'],'miss':pool['miss'],'experts':pool['experts'],
                                    'producer_gate':category,'GPU_predecessor_end_ns':pred['end'],'CPU_upload_API_start_ns':submit['start'],
                                    'CPU_upload_API_end_ns':submit['end'],'upload_GPU_start_ns':first['start'],'merge_GPU_end_ns':merge_k[0]['end'],
                                    'route_data_end_ns':route_end,'route_wait_end_ns':routes[c['moe']]['end'],'merge_timestamp_skew_ns':merge_skew,
                                    **dispatch_row})
            else:assert not ps
        route_ns=sum(ns(x) for x in rs);phase_ns=sum(x['wall_ns'] for x in prs)
        gpu_submit=sum(ns(x) for x in gs);cpu_ns=sum(ns(x) for x in cs)
        moe_other=cpu_ns-route_ns-phase_ns;token_other=ns(token)-cpu_ns-gpu_submit
        assert moe_other>=0 and token_other>=0
        pre=sum(x['pre_publish_ns'] for x in prs);body=sum(x['critical_chain_job_body_ns'] for x in prs)
        queue=sum(x['critical_chain_handoff_and_queue_ns'] for x in prs);tail=sum(x['phase_tail_ns'] for x in prs)
        assert gpu_submit+route_ns+pre+body+queue+tail+moe_other+token_other==ns(token)
        ops=[x for x in gpu if x['start']<token['end'] and x['end']>token['start']]
        native_sync_apis=[x for x in apis.values() if token['start']<=x['start']<token['end'] and any(k in api_names[x['nameId']] for k in ['GraphLaunch','StreamWaitEvent'])]
        assert not native_sync_apis,'Graph/cross-stream dependency needs separate analysis'
        assert len({x['streamId'] for x in ops})==1
        active=merge([(max(token['start'],x['start']),min(token['end'],x['end'])) for x in ops])
        late=merge([(max(token['start'],a),min(token['end'],b)) for a,b in late if b>a])
        row={'case':name,'pos':token['pos'],'output':token['output'],'start_ns':token['start'],'end_ns':token['end'],
             'wall_ns':ns(token),'gpu_submit_ns':gpu_submit,'route_wait_ns':route_ns,'phase_pre_publish_ns':pre,
             'critical_branch_job_body_ns':body,'critical_branch_queue_handoff_ns':queue,'phase_tail_ns':tail,
             'CPU_moe_other_ns':moe_other,'token_other_ns':token_other,'gpu_union_ns':duration(active),
             'gpu_uncovered_ns':ns(token)-duration(active),'host_late_interval_union_ns':duration(late),
             'host_late_overlap_gpu_ns':duration(intersect(late,active)),
             'host_submission_later':classes['host_submission_later'],'GPU_predecessor_later':classes['GPU_predecessor_later'],
             'within_10us_ambiguity':classes['within_10us_ambiguity'],'max_route_clock_error_ns':max_clock_error}
        row.update({key:sum(x[key] for x in dispatch) for key in ['GPU_half_start_after_pool','GPU_half_submit_to_start_ns',
                    'GPU_half_visible_gap_ns','GPU_half_gap_overlap_pool_ns']})
        token_rows.append(row);plot_raw.append({'token':token,'cpus':cs,'routes':rs,'phases':prs,'jobs':[x for c in cs for p in by_moe[c['moe']] for x in jobs[p['epoch']]],'gpu':ops})
    selected_moes={c['moe'] for x in plot_raw for c in x['cpus']}
    selected_phase_rows=[x for x in phase_rows if x['moe'] in selected_moes]
    selected_epochs={x['epoch'] for x in selected_phase_rows}
    selected_jobs_count=sum(x['epoch'] in selected_epochs for x in raw_jobs)
    for row in phase_rows:row['scope']='decode' if row['moe'] in selected_moes else 'prefill_tail'
    # Retain all jobs and dependency details locally, not only the terminal branch.
    csvfile(directory/(name+'-all-jobs.csv'),raw_jobs);csvfile(directory/(name+'-CPU-GPU-dependencies.csv'),moe_details)
    diagnostics=[dict(x) for x in db.execute('select * from DIAGNOSTIC_EVENT')]
    errors=[x for x in diagnostics if x['severity']==3 or any(k in x['text'].lower() for k in ['events lost','dropped','overflow','not supported by this build'])]
    assert not errors,errors
    assert not any('CUDA' in x['text'] for x in diagnostics if x['severity']>=2 and pid(x['globalPid'])==trace['engine_pid'])
    db.close()
    totals={key:sum(x[key] for x in token_rows) for key in ['wall_ns','gpu_submit_ns','route_wait_ns','phase_pre_publish_ns',
             'critical_branch_job_body_ns','critical_branch_queue_handoff_ns','phase_tail_ns','CPU_moe_other_ns','token_other_ns',
             'gpu_union_ns','gpu_uncovered_ns','host_late_interval_union_ns','host_late_overlap_gpu_ns','host_submission_later','GPU_predecessor_later','within_10us_ambiguity',
             'GPU_half_start_after_pool','GPU_half_submit_to_start_ns','GPU_half_visible_gap_ns','GPU_half_gap_overlap_pool_ns']}
    envelope=tokens[-1]['end']-tokens[0]['start'];between_tokens=envelope-sum(ns(x) for x in tokens)
    assert between_tokens>=0
    result={'case':name,'tokens':len(tokens),'MoE_layers':len(selected_moes),'phases':len(selected_phase_rows),'tasks':selected_jobs_count,
            'all_request_phases':len(phase_rows),'all_request_tasks':len(raw_jobs),
            'GPU_half_first_kernel_names':dict(Counter(x['first_GPU_half_kernel'] for x in moe_details)),
            'native_iteration_envelope_ns':envelope,'between_token_control_ns':between_tokens,
            'all_completion_ordinals_unique_and_tasks_matched':True,
            'last_release_differs_from_last_body_phases':sum(x['last_release_differs_from_last_body'] for x in selected_phase_rows),
            'host_wait_done_wall_ns':sum(x['host_wait_done_wall_ns'] for x in selected_phase_rows),
            'host_park_before_wall_ns':sum(x['host_park_before_wall_ns'] for x in selected_phase_rows),
            'host_park_after_wall_ns':sum(x['host_park_after_wall_ns'] for x in selected_phase_rows),
            'all_task_ids_unique_and_rows_covered':True,'all_token_ledgers_close':True,'all_phase_fork_joins_close':True,
            'observed_last_body_who_counts':dict(Counter(x['critical_who'] for x in selected_phase_rows)),
            'phase_last_body_ambiguous_1us':sum(x['near_last_jobs_1us']>1 for x in selected_phase_rows),
            'totals':totals,'diagnostic_warnings':[x for x in diagnostics if x['severity']>=2],
            'sqlite_sha256':digest(path),'classification_ambiguity_ns':EPS}
    return result,phase_rows,token_rows,plot_raw


def main():
    directory=OUT/'capture-02';r=json.loads((directory/'results.json').read_text(encoding='utf-8'))
    assert r['passed'] and not r['restore_errors'] and r['script_sha256']==digest(OUT/'capture_complete.py')
    cells=[case(directory,name) for name in ['r0-l1024','r0-l16384']]
    csvfile(OUT/'phase-ledger.csv',[x for c in cells for x in c[1]])
    csvfile(OUT/'token-ledger.csv',[x for c in cells for x in c[2]])
    save(OUT/'critical-path.json',{'verified_at':stamp(),'scope':'all task completion ordinals validated; 63 native decode token iterations per fixed workload; observed timing, not pure CPU cycles or counterfactual speedup',
        'cases':[c[0] for c in cells],'limits':['last completion identity is exact from atomic modification order; its timestamp is bounded by body-end and post-release marker',
        'task wall spans can contain OS preemption; no CPU sampling in this trace',
        'GPU operation timestamps and API submission bounds used; event device completion not fabricated',
        'GPU-predecessor-later is completion order, not proof that GPU was continuously busy',
        'n=1 instrumented requests; uninstrumented latency attribution not claimed']})
    # Plot/raw data is recreated from source traces, not a second GPU experiment.
    plot(cells)
    print(json.dumps([c[0] for c in cells]),flush=True)


def plot(cells):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(15,8),layout='constrained')
    for ax,cell in zip(axes,cells):
        raw=cell[3][len(cell[3])//2];tok=raw['token'];origin=tok['start']
        # One layer, selected by position rather than fastest/slowest duration.
        cpu=raw['cpus'][20];lo=cpu['start']-100000;hi=cpu['end']+100000
        def bars(rows,y,color):
            spans=[((max(x['start'],lo)-origin)/1e6,(min(x['end'],hi)-max(x['start'],lo))/1e6) for x in rows if x['start']<hi and x['end']>lo]
            if spans:ax.broken_barh(spans,(y-.3,.6),facecolors=color)
        bars(raw['gpu'],0,'#0072b2');bars([cpu],1,'#dddddd')
        phases=[x for x in raw['phases'] if x['moe']==cpu['moe']]
        for phase in phases:
            x=(phase['start_ns']-origin)/1e6;w=phase['wall_ns']/1e6
            ax.broken_barh([(x,w)],(.7,.6),facecolors='#e69f00' if phase['mode']==5 else '#cc79a7')
            js=[x for x in raw['jobs'] if x['epoch']==phase['epoch']]
            for who in range(-1,7):bars([j for j in js if j['who']==who],who+3,'#d55e00' if who==phase['critical_who'] else '#009e73')
            last=next(j for j in js if j['task']==phase['last_release_task'])
            marker=last['end']+phase['last_completion_publication_gap_ns']
            ax.plot([(last['end']-origin)/1e6,(marker-origin)/1e6],[last['who']+3]*2,color='#d55e00',linestyle='--',linewidth=1)
            ax.scatter([(marker-origin)/1e6],[last['who']+3],marker='|',color='#d55e00',s=40)
        ax.set_xlim((lo-origin)/1e6,(hi-origin)/1e6);ax.set_ylim(10,-.7)
        ax.set_yticks(range(10),['GPU','host phase','host tasks',*[f'worker {i}' for i in range(7)]])
        ax.set_title(cell[0]['case']+' | middle token, layer20 | green: task wall spans; phase GU orange / DOWN purple')
        ax.set_xlabel('ms from native token iteration start');ax.grid(axis='x',alpha=.2)
    fig.suptitle('Observed task/phase fork-join | task wall includes preemption and instrumentation')
    fig.savefig(OUT/'timeline.png',dpi=140);plt.close(fig)


if __name__=='__main__':main()
