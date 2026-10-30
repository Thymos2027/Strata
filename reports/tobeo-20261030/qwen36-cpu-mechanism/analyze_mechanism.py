"""Read original copy traces; verify API/event dependencies and per-stage byte conservation."""
import bisect,csv,ctypes,json,sqlite3,sys
from collections import Counter,defaultdict
from pathlib import Path

OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT.parent/'qwen36-systems'))
from common import digest,save,stamp
from analyze_systems import duration,intersect,pid,spans


def arm(name):
    root=OUT.parent/'qwen36-copy3905';directory=root/'traces-01'
    expected=json.loads((root/'evidence-manifest.json').read_text(encoding='utf-8'))
    path=directory/(name+'.sqlite');assert digest(path)==expected['traces-01/'+path.name]
    worker=json.loads((directory/(name+'.json')).read_text(encoding='utf-8'));target=worker['engine_pid'];assert worker['passed']
    db=sqlite3.connect('file:'+path.as_posix()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    start,end=db.execute("select start,end from NVTX_EVENTS where text='prefill-to-first-token'").fetchone()
    rt_names={x['id']:x['value'] for x in db.execute("select id,value from StringIds where value like 'cudaEventRecord%' or value like 'cudaStreamWaitEvent%' or value like 'cudaMemcpyAsync%'")}
    ids=','.join(str(x) for x in rt_names)
    runtime={x['correlationId']:dict(x) for x in db.execute('select * from CUPTI_ACTIVITY_KIND_RUNTIME where nameId in ('+ids+')') if pid(x['globalTid'])==target}
    events=[dict(x) for x in db.execute('select * from CUPTI_ACTIVITY_KIND_CUDA_EVENT') if pid(x['globalPid'])==target]
    for x in events:x['api']=runtime[x['correlationId']]
    event_map={(x['eventId'],x['eventSyncId']):x for x in events}
    waits=[dict(x) for x in db.execute('select * from CUPTI_ACTIVITY_KIND_SYNCHRONIZATION where syncType=2 and eventId!=4294967295') if pid(x['globalPid'])==target]
    for x in waits:x['api']=runtime[x['correlationId']]
    copies=[dict(x) for x in db.execute('select * from CUPTI_ACTIVITY_KIND_MEMCPY where start<? and end>?',(end,start)) if pid(x['globalPid'])==target]
    large=[x for x in copies if x['bytes']>=1024*1024 and x['streamId'] in [14,15]]
    for x in large:x['api']=runtime[x['correlationId']]
    assert all(x['api']['returnValue']==0 for x in events+waits+large)
    copy_events=sorted([x for x in events if x['streamId']==14],key=lambda x:x['api']['start'])
    all_copy_starts=[x['api']['start'] for x in copy_events]
    selected=[x for x in copy_events if start<=x['api']['start']<end]
    by_wait=defaultdict(list)
    for x in waits:by_wait[(x['eventId'],x['eventSyncId'])].append(x)
    stages=[]
    for index,event in enumerate(selected):
        position=bisect.bisect_left(all_copy_starts,event['api']['start'])
        lower=copy_events[position-1]['api']['end'] if position else 0
        upper=event['api']['start']
        host=[x for x in large if x['streamId']==14 and lower<x['api']['start']<upper]
        assert len(host)==1 and host[0]['copyKind']==1
        consumed=[x for x in by_wait[(event['eventId'],event['eventSyncId'])] if x['streamId']==13]
        assert len(consumed)==1 and consumed[0]['api']['start']>=event['api']['end']
        cwait=[x for x in waits if x['streamId']==14 and lower<x['api']['start']<upper]
        used=[x for x in cwait if event_map[(x['eventId'],x['eventSyncId'])]['streamId']==13]
        assert len(used)==1
        assert used[0]['api']['end']<=host[0]['api']['start']
        device=[];d_event=None
        if name=='on':
            joins=[x for x in cwait if event_map[(x['eventId'],x['eventSyncId'])]['streamId']==15]
            assert len(joins)==1
            d_event=event_map[(joins[0]['eventId'],joins[0]['eventSyncId'])]
            assert d_event['api']['end']<=joins[0]['api']['start'] and joins[0]['api']['end']<=upper
            dprev=max([x['api']['end'] for x in events if x['streamId']==15 and x['api']['start']<d_event['api']['start']],default=0)
            device=[x for x in large if x['streamId']==15 and dprev<x['api']['start']<d_event['api']['start']]
            assert len(device)==1 and device[0]['copyKind']==8
            dused=[x for x in by_wait[(used[0]['eventId'],used[0]['eventSyncId'])] if x['streamId']==15 and dprev<x['api']['start']<d_event['api']['start']]
            assert len(dused)==1 and dused[0]['api']['end']<=device[0]['api']['start']
            assert device[0]['api']['end']<=d_event['api']['start']
        stages.append({'stage':index,'buffer_event_id':event['eventId'],'copy_event_sync_id':event['eventSyncId'],
                       'used_event_id':used[0]['eventId'],'used_event_sync_id':used[0]['eventSyncId'],
                       'HtoD_bytes':sum(x['bytes'] for x in host),'DtoD_bytes':sum(x['bytes'] for x in device),
                       'HtoD_start_ms':(host[0]['start']-start)/1e6,'HtoD_end_ms':(host[0]['end']-start)/1e6,
                       'DtoD_start_ms':(device[0]['start']-start)/1e6 if device else None,
                       'DtoD_end_ms':(device[0]['end']-start)/1e6 if device else None,
                       'copy_record_device_timestamp':event['timestamp'],
                       'host_copy_api_correlation':host[0]['correlationId'],
                       'copy_record_api_correlation':event['correlationId'],
                       'compute_wait_api_correlation':consumed[0]['correlationId'],
                       'host_used_wait_api_correlation':used[0]['correlationId'],
                       'd2d_event_id':d_event['eventId'] if d_event else None,
                       'd2d_event_sync_id':d_event['eventSyncId'] if d_event else None,
                       'device_copy_api_correlation':device[0]['correlationId'] if device else None,
                       'device_used_wait_api_correlation':dused[0]['correlationId'] if device else None,
                       'host_d2d_join_api_correlation':joins[0]['correlationId'] if device else None})
    assert len(stages)==320
    ids=sorted({x['buffer_event_id'] for x in stages});assert len(ids)==2
    assert all(x['buffer_event_id']==ids[i%2] for i,x in enumerate(stages))
    streams=[dict(x) for x in db.execute('select * from TARGET_INFO_CUDA_STREAM') if x['processId']==target and x['streamId'] in [13,14,15]]
    for x in streams:x['priority_signed']=ctypes.c_int32(x['priority']).value
    h=spans([x for x in large if x['copyKind']==1]);d=spans([x for x in large if x['copyKind']==8])
    kernels=[dict(x) for x in db.execute('select start,end,globalPid from CUPTI_ACTIVITY_KIND_KERNEL where start<? and end>?',(end,start)) if pid(x['globalPid'])==target]
    overlap={'HtoD_DtoD_ms':duration(intersect(h,d))/1e6,'DtoD_kernel_ms':duration(intersect(d,spans(kernels)))/1e6,
             'HtoD_ms':duration(h)/1e6,'DtoD_ms':duration(d)/1e6}
    db.close()
    return {'arm':name,'sqlite_sha256':digest(path),'stages':len(stages),'buffer_copy_event_ids':ids,
            'stream_metadata':streams,'overlap':overlap,'all_copy_device_timestamps_zero':all(x['copy_record_device_timestamp']==0 for x in stages),
            'dependency_scope':'CPU enqueue/eventSyncId linkage; not measured GPU event completion times'},stages


def main():
    a,aa=arm('off');b,bb=arm('on');rows=[]
    for x,y in zip(aa,bb):
        assert x['stage']==y['stage'] and x['HtoD_bytes']==y['HtoD_bytes']+y['DtoD_bytes']
        assert y['DtoD_bytes']*256==x['HtoD_bytes']*63 and y['HtoD_bytes']*256==x['HtoD_bytes']*193
        rows.append({'stage':x['stage'],'buffer':x['stage']%2,'A_HtoD_bytes':x['HtoD_bytes'],
                     'A_copy_event_id':x['buffer_event_id'],'A_copy_event_sync_id':x['copy_event_sync_id'],
                     **{'B_'+k:v for k,v in y.items() if k!='stage'}})
    with (OUT/'mechanism-stages.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    save(OUT/'mechanism-summary.json',{'verified_at':stamp(),'all_320_stages_byte_conserved':True,
         'resident_fraction_exact':'63/256','all_320_dependency_chains_checked':True,'arms':[a,b],
         'limits':['no third arm; priority and independent-stream benefits not isolated',
                   'CUDA event device completion timestamps are zero; no GPU wait duration claim',
                   'not a byte dump of staging memory; no new timing sample']})
    print(json.dumps({'stages':len(rows),'byte_conserved':True,'dependencies_checked':True,'streams':b['stream_metadata'],'overlap':b['overlap']}))


if __name__=='__main__':main()
