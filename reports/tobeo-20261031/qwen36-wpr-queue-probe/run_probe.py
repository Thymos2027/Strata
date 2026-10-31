"""One bounded ETW tool probe. No model matrix and no CUDA profiler."""
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone,timedelta
import ctypes,hashlib,json,os,re,shutil,subprocess,sys,time,traceback,xml.etree.ElementTree as ET
P=Path(__file__).resolve().parent
REPO=P.parents[2]
sys.path.insert(0,str(P.parent/'qwen36-gpu-submit-870aedd9'))
import context as ctx
save,stamp,digest=ctx.save,ctx.stamp,ctx.digest
WPR=Path(os.environ['SystemRoot'])/'System32/wpr.exe'
TR=Path(os.environ['SystemRoot'])/'System32/tracerpt.exe'
PROBE=REPO/'reports/tobeo-20261024/pcie-root-cause/transfer_probe.exe'
INSTANCE='StrataQueueProbe'+str(os.getpid())
S={'started':stamp(),'pid':os.getpid(),'state':'running','passed':False,'queue_attribution_ready':False,'root_cause_confirmed':False,'wpr_instance':INSTANCE}
def state(phase,**kw):
 S.update(phase=phase,updated=stamp(),**kw);save(P/'background-status.json',S);print(phase,flush=True)
def cmd(args,name,timeout=90,check=True):
 with (P/(name+'.log')).open('wb') as f:
  r=subprocess.run([str(x) for x in args],stdout=f,stderr=subprocess.STDOUT,timeout=timeout,env=ctx.environment())
 text=(P/(name+'.log')).read_text(encoding='utf-8',errors='replace')
 if check:assert r.returncode==0,(name,r.returncode)
 return {'command':[str(x) for x in args],'exit_code':r.returncode,'text':text}
def wpr(args,name,**kw):return cmd([WPR,*args,'-instancename',INSTANCE],name,**kw)
def parse_xml(path,pid):
 providers=Counter();types=Counter();target=Counter();fields=defaultdict(set);samples=defaultdict(list);events=0
 def local(tag):return tag.rsplit('}',1)[-1]
 for _,elem in ET.iterparse(path,events=['end']):
  if local(elem.tag)!='Event':continue
  events+=1;parts=list(elem.iter());pr=next((x for x in parts if local(x.tag)=='Provider'),None)
  provider=pr.attrib.get('Name',pr.attrib.get('Guid','unknown')) if pr is not None else 'unknown'
  providers[provider]+=1
  values={local(x.tag):(x.text or '').strip() for x in parts if local(x.tag) in ['EventID','Task','Opcode']}
  key=provider+'|'+values.get('EventID','')+'|'+values.get('Task','')+'|'+values.get('Opcode','');types[key]+=1
  payload={x.attrib.get('Name',''):(x.text or '').strip() for x in parts if local(x.tag)=='Data' and x.attrib.get('Name')}
  fields[provider].update(payload)
  ex=next((x for x in parts if local(x.tag)=='Execution'),None)
  candidates=[]
  if ex is not None:candidates.append(ex.attrib.get('ProcessID',''))
  candidates += [v for k,v in payload.items() if k.lower() in ['processid','process_id','pid','owningprocessid','clientprocessid']]
  matched=False
  for v in candidates:
   try:
    if int(v,16 if v.lower().startswith('0x') else 10)==pid:matched=True
   except (ValueError,AttributeError):pass
  if matched:target[provider]+=1
  gpu='dxg' in provider.lower()
  if len(samples[provider])<(12 if gpu else 2) or (matched and len(samples[provider])<24):
   samples[provider].append({'type':values,'execution':dict(ex.attrib) if ex is not None else {},'payload':payload,'direct_PID_match':matched})
  elem.clear()
 assert events>0,'No Event elements decoded'
 return {'decoded_events':events,'providers':dict(providers),'event_types':dict(types),'payload_fields':{k:sorted(v) for k,v in fields.items()},'direct_target_PID_candidates':dict(target),'samples':dict(samples),'semantic_review_required':True}

def main():
 assert not (P/'background-status.json').exists();state('preflight')
 r={'started':stamp(),'passed':False,'commands':[],'restore_errors':[],'script_sha256':digest(__file__),'plan_sha256':digest(P/'experiment-plan.md'),'probe_sha256':digest(PROBE),'instance':INSTANCE}
 save(P/'results.json',r);started=False;start_attempted=False;unloaded=False;stopped=False
 try:
  assert ctypes.windll.shell32.IsUserAnAdmin(),'Administrator required'
  assert shutil.disk_usage(REPO).free>=4*1024**3
  assert r['probe_sha256']=='712995e1d2d12b0806eb621edc2c653b59b45a106118de7c5bfac577bf4972a8'
  assert not ctx.conflicts()
  status=cmd([WPR,'-status'],'global-status-before');r['commands'].append(status);assert 'not recording' in status['text'].lower(),'An existing WPR recording is active; do not interfere'
  own_before=wpr(['-status'],'instance-status-before');r['commands'].append(own_before);assert 'not recording' in own_before['text'].lower()
  details=cmd([WPR,'-profiledetails','GPU.Light','-filemode'],'profile-details');assert 'GPU.Light.File' in details['text'];r['commands'].append(details)
  r['health_before']=ctx.host.api('/health');r['config_before']=digest(ctx.host.CONFIG)
  state('unloading-daily-service');unloaded=True;r['unload']=ctx.host.api('/unload?wait=30',True);assert r['unload'].get('status') in ['unloaded','not loaded']
  assert not [x for x in ctx.audit_processes() if (x['name'] or '').lower() in ['strata.exe','strata-q36.exe']]
  temp=P/'temp';temp.mkdir();state('recording-short-GPU-probe')
  start_attempted=True
  r['commands'].append(wpr(['-start','GPU.Light','-filemode','-recordtempto',str(temp)],'wpr-start'));started=True
  r['probe_begin_UTC']=stamp();r['probe_begin_perf_counter_ns']=time.perf_counter_ns()
  with (P/'probe.log').open('wb') as f:
   active=subprocess.Popen([str(PROBE)],env=ctx.environment(),stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
   r['probe_pid']=active.pid;save(P/'results.json',r)
   try:r['probe_exit_code']=active.wait(timeout=30)
   except BaseException:active.kill();active.wait(timeout=10);raise
  r['probe_end_perf_counter_ns']=time.perf_counter_ns();r['probe_end_UTC']=stamp();assert r['probe_exit_code']==0
  r['commands'].append(wpr(['-status','collectors','-details'],'wpr-status-during'))
  state('stopping-owned-WPR-session')
  r['commands'].append(wpr(['-stop',str(P/'probe.etl'),'-skipPdbGen'],'wpr-stop',timeout=120));stopped=True
  r['etl_bytes']=(P/'probe.etl').stat().st_size;assert r['etl_bytes']>0
 except BaseException as e:r['error']=repr(e);raise
 finally:
  state('restore-service-and-recording-state')
  try:
   # Never cancel a global/default session; query only our unique instance.
   own=wpr(['-status'],'instance-status-final',check=False);r['commands'].append(own)
   if start_attempted and not stopped and 'in progress' in own['text'].lower():
    r['commands'].append(wpr(['-cancel'],'wpr-cancel-owned'))
   if started and stopped:assert 'not recording' in own['text'].lower()
  except BaseException as e:r['restore_errors'].append('WPR cleanup: '+repr(e))
  try:
   if unloaded and r['health_before']['loaded']:
    if not ctx.host.api('/health')['loaded']:r['restore']=ctx.host.api('/load',True)
    r['health_after']=ctx.host.api('/health');assert r['health_after']['loaded'] and r['health_after']['model']==r['health_before']['model']
   if 'config_before' in r:r['config_after']=digest(ctx.host.CONFIG);assert r['config_after']==r['config_before']
  except BaseException as e:r['restore_errors'].append(repr(e))
  r['service_restored_at']=stamp();save(P/'results.json',r)
 assert not r['restore_errors'] and stopped
 state('exporting-ETL-with-system-tracerpt')
 r['commands'].append(cmd([TR,str(P/'probe.etl'),'-o',str(P/'events.xml'),'-of','XML','-summary',str(P/'trace-summary.txt'),'-y'],'tracerpt-export',timeout=180))
 state('checking-provider-and-PID-candidates')
 analysis=parse_xml(P/'events.xml',r['probe_pid']);save(P/'event-inventory.json',analysis)
 assert digest(PROBE)==r['probe_sha256'] and digest(P/'experiment-plan.md')==r['plan_sha256'] and digest(__file__)==r['script_sha256']
 r.update(passed=True,finished=stamp(),queue_attribution_ready=False);save(P/'results.json',r)
 files={q.relative_to(P).as_posix():digest(q) for q in sorted(P.rglob('*')) if q.is_file() and '__pycache__' not in q.parts and not q.name.startswith('background') and q.name not in ['summary.json','README.md','evidence-manifest.json']}
 save(P/'evidence-manifest.json',files)
 summary={'passed':True,'verified_at':stamp(),'probe_recording_passed':True,'queue_attribution_ready':False,'semantic_review_required':True,'root_cause_confirmed':False,
 'probe_pid':r['probe_pid'],'probe_exit_code':r['probe_exit_code'],'probe_duration_s':(r['probe_end_perf_counter_ns']-r['probe_begin_perf_counter_ns'])/1e9,
 'etl_bytes':r['etl_bytes'],'decoded_events':analysis['decoded_events'],'providers':analysis['providers'],'direct_target_PID_candidates':analysis['direct_target_PID_candidates'],
 'service_restored_at':r['service_restored_at'],'restore_errors':r['restore_errors'],'evidence_files':len(files),'manifest_sha256':digest(P/'evidence-manifest.json'),
 'limits':['short transfer/compute probe, not model capture','provider/PID presence does not establish queue semantics or clock alignment','lost-event and context/queue fields require review','no CUDA kernel-level launch delay or driver root-cause claim','raw system ETL/XML remain local']}
 save(P/'summary.json',summary);state('probe-complete-awaiting-semantic-review',state='complete',passed=True,finished=stamp(),service_restored=True)
if __name__=='__main__':
 if (P/'background-status.json').exists():raise SystemExit('Refusing to overwrite an existing probe run')
 try:main()
 except BaseException as e:traceback.print_exc();state('failed',state='failed',passed=False,error=repr(e),finished=stamp());raise
