"""Offline review of one existing ETL; never records a trace or changes serving."""
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone,timedelta
import csv,hashlib,json,os,re,subprocess,traceback,xml.etree.ElementTree as E
P=Path(__file__).resolve().parent
REPO=P.parents[2]
OLD=REPO/'reports/tobeo-20261031/qwen36-wpr-queue-probe'
TR=Path(os.environ['SystemRoot'])/'System32/tracerpt.exe'
S={'started':datetime.now(timezone(timedelta(hours=8))).isoformat(),'pid':os.getpid(),'state':'running','passed':False,'new_GPU_capture':False,'queue_attribution_ready':False,'root_cause_confirmed':False}
def stamp():return datetime.now(timezone(timedelta(hours=8))).isoformat()
def save(p,v):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2,ensure_ascii=False),encoding='utf-8');t.replace(p)
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def state(phase,**kw):
 S.update(phase=phase,updated=stamp(),**kw);save(P/'background-status.json',S);print(phase,flush=True)
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def integer(v):
 v=str(v).strip()
 try:return int(v,16 if v.lower().startswith('0x') else 10)
 except ValueError:return None
def records(path):
 data=[];header={};events=0
 local=lambda x:x.tag.rsplit('}',1)[-1]
 for _,e in E.iterparse(path,events=['end']):
  if local(e)!='Event':continue
  events+=1;parts=list(e.iter())
  payload={x.attrib.get('Name'):(x.text or '').strip() for x in parts if local(x)=='Data' and x.attrib.get('Name')}
  if 'PerfFreq' in payload:header={k:payload[k] for k in ['PerfFreq','StartTime','BootTime','TimerResolution'] if k in payload}
  pr=next((x for x in parts if local(x)=='Provider'),None)
  if pr is not None and pr.attrib.get('Name')=='Microsoft-Windows-DxgKrnl':
   vals={local(x):(x.text or '').strip() for x in parts if local(x) in ['EventID','Task','Opcode']}
   if vals.get('Task') in ['Process','Device','Context','QueuePacket','DmaPacket']:
    ex=next((x for x in parts if local(x)=='Execution'),None);tc=next((x for x in parts if local(x)=='TimeCreated'),None)
    data.append({'index':events,'id':integer(vals.get('EventID','')),'task':vals.get('Task'),'opcode':vals.get('Opcode'),
     'pid':integer(ex.attrib.get('ProcessID','')) if ex is not None else None,'tid':integer(ex.attrib.get('ThreadID','')) if ex is not None else None,
     'time':dict(tc.attrib) if tc is not None else {},'payload':payload})
  e.clear()
 return data,header,events

def main():
 state('verify-original-17-files')
 m=load(OLD/'evidence-manifest.json');s=load(OLD/'summary.json');r=load(OLD/'results.json')
 assert s['passed'] and sha(OLD/'evidence-manifest.json')==s['manifest_sha256'] and len(m)==17
 assert all(sha(OLD/n)==h for n,h in m.items())
 loss=(OLD/'trace-summary.txt').read_text(encoding='utf-8',errors='replace');match=re.search(r'Total Events\s+Lost\s+(\d+)',loss);assert match
 lost=int(match[1]);assert lost==0
 state('export-existing-ETL-raw-timestamps')
 command=[str(TR),str(OLD/'probe.etl'),'-rts','-o',str(P/'events-raw.xml'),'-of','XML','-y']
 with (P/'raw-export.log').open('wb') as f:code=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,timeout=240).returncode
 assert code==0
 state('parse-existing-normal-and-raw-XML')
 normal,header,events=records(OLD/'events.xml');raw,rawheader,raw_events=records(P/'events-raw.xml')
 def signature(x):return (x['id'],x['pid'],x['tid'],tuple(sorted(x['payload'].items())))
 assert events==raw_events==s['decoded_events'] and len(normal)==len(raw)
 assert [signature(x) for x in normal]==[signature(x) for x in raw],'Raw/default event sequence differs'
 for n,a in zip(normal,raw):n['raw_time']=a['time'];n['qpc']=next((v for v in [integer(t) for t in a['time'].values()] if v is not None),None)
 target=s['probe_pid'];freq=integer(header.get('PerfFreq','0'));assert freq and freq>0
 begin=r['probe_begin_perf_counter_ns']*freq//1000000000;end=r['probe_end_perf_counter_ns']*freq//1000000000
 direct_process=[x for x in normal if x['task']=='Process' and integer(x['payload'].get('ProcessId',''))==target and x['id'] in [471,473]]
 clock_ok=bool(direct_process) and all(x['qpc'] is not None and begin<=x['qpc']<=end for x in direct_process)
 clock={'ready':clock_ok,'frequency':freq,'expected_probe_begin_ticks':begin,'expected_probe_end_ticks':end,'process_event_times':[{'id':x['id'],'normal':x['time'],'raw':x['raw_time'],'raw_numeric':x['qpc']} for x in direct_process],
  'normal_export_offset_note':'Do not repair +07:59 by assumption; raw timestamp must match Windows perf_counter/QPC bounds.'}
 save(P/'clock-review.json',clock)
 state('associate-process-device-context-and-packets')
 devices={x['payload']['hDevice'] for x in normal if x['task']=='Device' and x['id'] in [27,29] and integer(x['payload'].get('hProcessId',''))==target}
 contexts=[]
 for x in normal:
  if x['task']!='Context' or x['id'] not in [30,32] or x['payload'].get('hDevice') not in devices:continue
  c=x['payload']['hContext'];stops=[y['index'] for y in normal if y['task']=='Context' and y['id']==31 and y['payload'].get('hContext')==c and y['index']>=x['index']]
  contexts.append({'name':'context-'+str(len(contexts)+1),'handle':c,'device':x['payload']['hDevice'],'node':x['payload'].get('NodeOrdinal'),
   'begin_index':x['index'],'end_index':min(stops) if stops else events+1})
 def owner(x):
  handles={x['payload'].get('hContext'),x['payload'].get('hQueuePacketContext')}-{None,'0x0'}
  found=[c['name'] for c in contexts if c['handle'] in handles and c['begin_index']<=x['index']<=c['end_index']]
  return found[0] if len(found)==1 else None
 queues=defaultdict(list);dma=defaultdict(list);counts=Counter()
 for x in normal:
  if x['task'] not in ['QueuePacket','DmaPacket']:continue
  o=owner(x)
  if not o:continue
  counts[str(x['id'])]+=1;x['owner']=o
  seq=integer(x['payload'].get('SubmitSequence' if x['task']=='QueuePacket' else 'ulQueueSubmitSequence',''))
  if seq is None:continue
  (queues if x['task']=='QueuePacket' else dma)[(o,seq)].append(x)
 ledger=[];unmatched=[]
 for key,qs in queues.items():
  submit=[x for x in qs if x['id']==178]
  if not submit:continue
  ends=[x for x in qs if x['id']==180];ds=[x for x in dma.get(key,[]) if x['id']==175];de=[x for x in dma.get(key,[]) if x['id']==176]
  if not(len(submit)==len(ends)==len(ds)==len(de)==1):
   unmatched.append({'context':key[0],'sequence':key[1],'submit':len(submit),'queue_end':len(ends),'dma_start':len(ds),'dma_stop':len(de)});continue
  a,b,c,d=submit[0],ds[0],de[0],ends[0]
  times=[z['qpc'] for z in [a,b,c,d]]
  if not clock_ok or any(t is None for t in times) or times!=sorted(times):
   unmatched.append({'context':key[0],'sequence':key[1],'reason':'clock/order not validated','raw_times':times});continue
  submission=b['payload'].get('uliSubmissionId');completion=c['payload'].get('uliCompletionId')
  if submission!=completion:
   unmatched.append({'context':key[0],'sequence':key[1],'reason':'DMA IDs differ','submission':submission,'completion':completion});continue
  ledger.append({'context':key[0],'submit_sequence':key[1],'queue_submit_qpc':times[0],'dma_start_qpc':times[1],'dma_stop_qpc':times[2],'queue_end_qpc':times[3],
   'submit_to_dma_start_us':(times[1]-times[0])*1000000/freq,'dma_start_to_stop_us':(times[2]-times[1])*1000000/freq,'dma_id':submission})
 if ledger:
  with (P/'packet-ledger.csv').open('w',newline='',encoding='utf-8') as f:
   w=csv.DictWriter(f,fieldnames=list(ledger[0]));w.writeheader();w.writerows(ledger)
 details={'target_pid':target,'devices':sorted(devices),'contexts':contexts,'owned_event_counts':dict(counts),'render_submit_keys':sum(any(x['id']==178 for x in qs) for qs in queues.values()),
  'complete_unique_chains':len(ledger),'unmatched_render_keys':unmatched,'clock_alignment_ready':clock_ok,
  'limits':['queue/DMA timestamps are recorded system events, not CUDA kernel entry times','synchronization packet types244/245 excluded from render178 chain checks','fragmented/ambiguous chains not forced into a single duration']}
 save(P/'packet-review.json',details)
 ready=bool(ledger) and not unmatched and clock_ok and lost==0
 summary={'passed':True,'verified_at':stamp(),'new_GPU_capture':False,'root_cause_confirmed':False,'clock_alignment_ready':clock_ok,
  'packet_mapping_ready':ready,'queue_attribution_ready':False,'attribution_review_required':True,'target_pid':target,'device_count':len(devices),'context_count':len(contexts),
  'complete_unique_packet_chains':len(ledger),'unmatched_render_keys':len(unmatched),'owned_event_counts':dict(counts),'events_lost':lost,
  'original_manifest_sha256':s['manifest_sha256'],'limits':details['limits']}
 files={q.relative_to(P).as_posix():sha(q) for q in sorted(P.rglob('*')) if q.is_file() and '__pycache__' not in q.parts and not q.name.startswith('background') and q.name not in ['summary.json','README.md','evidence-manifest.json']}
 save(P/'evidence-manifest.json',files);summary.update(evidence_files=len(files),manifest_sha256=sha(P/'evidence-manifest.json'));save(P/'summary.json',summary)
 state('offline-review-complete',state='complete',passed=True,finished=stamp(),clock_alignment_ready=clock_ok,packet_mapping_ready=ready)
if __name__=='__main__':
 if (P/'background-status.json').exists():raise SystemExit('Refusing to overwrite review output')
 try:main()
 except BaseException as e:traceback.print_exc();state('failed',state='failed',passed=False,error=repr(e),finished=stamp());raise
