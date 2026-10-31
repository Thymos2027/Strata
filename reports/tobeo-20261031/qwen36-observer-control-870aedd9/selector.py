"""Common CUDA-only selector; validate against independent native scopes before off traces."""
from pathlib import Path
import csv,json,sqlite3,statistics
from collections import defaultdict

def select(path,record,case):
 db=sqlite3.connect('file:'+Path(path).resolve().as_posix()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
 try:
  scopes=db.execute("select start,end from NVTX_EVENTS where text='request'").fetchall();assert len(scopes)==1
  lo,hi=scopes[0];pid=record['engine_pid']
  # CUPTI globalPid/globalTid encode process in the high bits.
  gpu=[]
  for table,kind in [('CUPTI_ACTIVITY_KIND_KERNEL','kernel'),('CUPTI_ACTIVITY_KIND_MEMCPY','copy'),('CUPTI_ACTIVITY_KIND_MEMSET','set')]:
   join=' join StringIds s on s.id=g.shortName' if kind=='kernel' else ''
   extra=',s.value as name' if kind=='kernel' else ''
   for x in db.execute('select g.*'+extra+' from '+table+' g'+join+' where g.start>=? and g.start<?',(lo,hi)):
    x=dict(x)
    if ((x['globalPid']>>24)&0xffffff)==pid:x.update(kind=kind);gpu.append(x)
  kernels=sorted([x for x in gpu if x['kind']=='kernel' and x['name']=='native_gu_kernel'],key=lambda x:x['start'])
  expected=2520 if case=='r0-l1024' else 2560;assert len(kernels)==expected,(case,len(kernels))
  selected=kernels[-2520:];assert len({x['streamId'] for x in selected})==1
  names={x[0] for x in db.execute("select id from StringIds where value like '%LaunchKernel%'")};assert names
  apis={}
  for x in db.execute('select * from CUPTI_ACTIVITY_KIND_RUNTIME where nameId in ('+','.join(map(str,names))+') and start>=? and start<?',(lo,hi)):
   x=dict(x)
   if ((x['globalTid']>>24)&0xffffff)==pid:
    assert x['correlationId'] not in apis
    apis[x['correlationId']]=x
  streams=defaultdict(list)
  for x in gpu:streams[x['streamId']].append(x)
  previous={}
  for stream,ops in streams.items():
   ops.sort(key=lambda x:(x['start'],x['end']))
   for i,x in enumerate(ops):previous[(stream,x['start'],x['end'],x['correlationId'])]=ops[i-1] if i else None
  rows=[]
  shape_keys=['gridX','gridY','gridZ','blockX','blockY','blockZ','staticSharedMemory','dynamicSharedMemory']
  for i,x in enumerate(selected):
   a=apis[x['correlationId']];prev=previous[(x['streamId'],x['start'],x['end'],x['correlationId'])];assert prev is not None
   signed_gap=x['start']-prev['end'];assert signed_gap>=-10000
   rows.append({'case':case,'iteration':i//40+1,'layer':i%40,'correlation_id':x['correlationId'],'stream':x['streamId'],
    'GPU_start_ns':x['start'],'GPU_end_ns':x['end'],'API_start_ns':a['start'],'API_end_ns':a['end'],'previous_GPU_end_ns':prev['end'],
    'API_end_to_GPU_start_ns':x['start']-a['end'],'visible_gap_ns':max(0,signed_gap),'signed_visible_gap_ns':signed_gap,
    **{k:x[k] for k in shape_keys}})
  native_count=db.execute("select count(*) from NVTX_EVENTS where text like 'JT %' and ((globalTid >> 24) & 16777215)=? and start>=? and start<?",(pid,lo,hi)).fetchone()[0]
  def stat(values):
   v=sorted(values);n=len(v)
   return {'min_ns':v[0],'median_ns':statistics.median(v),'p95_ns':v[int(.95*(n-1))],'max_ns':v[-1],'sum_ns':sum(v),'negative_count':sum(x<0 for x in v)}
  metrics={'selected_kernels':len(rows),'prefill_tail_excluded':expected-2520,'native_NVTX_events':native_count,
   'API_end_to_GPU_start':stat([r['API_end_to_GPU_start_ns'] for r in rows]),'visible_gap':stat([r['visible_gap_ns'] for r in rows]),
   'timestamp_overlap_within_10us_count':sum(r['signed_visible_gap_ns']<0 for r in rows)}
  return rows,metrics
 finally:db.close()

def validate_previous(root):
 verified=[]
 for rep in [1,2]:
  directory=Path(root)/('capture-'+str(rep).zfill(2))
  for case in ['r0-l1024','r0-l16384']:
   tag=case+'-on-trace';record=json.loads((directory/(tag+'.json')).read_text(encoding='utf-8'))
   rows,metrics=select(directory/(tag+'.sqlite'),record,case)
   native=list(csv.DictReader((directory/(case+'-CPU-GPU-dependencies.csv')).open(encoding='utf-8')))
   assert len(rows)==len(native)==2520
   assert [(x['GPU_start_ns'],x['API_end_ns']) for x in rows]==[(int(x['GPU_half_start_ns']),int(x['GPU_half_API_exit_ns'])) for x in native]
   assert all(x['layer']==int(y['layer']) for x,y in zip(rows,native))
   verified.append({'round':rep,'case':case,'matched_native_layers':len(rows),'metrics':metrics})
 return verified
