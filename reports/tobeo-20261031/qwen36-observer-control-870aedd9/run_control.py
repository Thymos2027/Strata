"""Detached observer ablation; reuse the same binary and preserve earlier evidence."""
from pathlib import Path
import argparse,csv,json,os,shutil,signal,sqlite3,subprocess,sys,traceback
P=Path(__file__).resolve().parent
PREVIOUS=P.parent/'qwen36-gpu-submit-870aedd9'
sys.path.insert(0,str(PREVIOUS))
import context as ctx
import capture as previous_capture
from selector import select,validate_previous
REPO=ctx.REPO
save,stamp,digest=ctx.save,ctx.stamp,ctx.digest
S={}
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def state(phase,**kw):
 S.update(phase=phase,updated=stamp(),**kw);save(P/'background-status.json',S);print(phase,flush=True)
def csvfile(path,rows):
 with path.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def raw_run(command,log,arm='off',timeout=900):
 with log.open('w',encoding='utf-8') as f:
  job=subprocess.Popen(command,env=previous_capture.environment(arm),cwd=REPO,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
  try:code=job.wait(timeout=timeout)
  except BaseException:
   subprocess.run(['taskkill','/PID',str(job.pid),'/T','/F'],capture_output=True);raise
 assert code==0,('command failed',code,str(log))
def profile(directory,tag,command,arm):
 raw_run([str(ctx.host.NSYS),'profile','--trace=cuda,nvtx','--sample=none','--cpuctxsw=none','--cuda-graph-trace=node','--kill=false','--wait=all','--output='+str(directory/tag),*command],directory/(tag+'-capture.log'),arm)
 raw_run([str(ctx.host.NSYS),'export','--type=sqlite','--output='+str(directory/(tag+'.sqlite')),str(directory/(tag+'.nsys-rep'))],directory/(tag+'-export.log'),arm)
def check_previous():
 ctx.check_identity();s=load(PREVIOUS/'summary.json');assert s['passed']
 m=load(PREVIOUS/'evidence-manifest.json');assert digest(PREVIOUS/'evidence-manifest.json')==s['manifest_sha256']
 assert all(digest(PREVIOUS/n)==h for n,h in m.items())
 b=load(PREVIOUS/'build-complete.json');assert b['passed'] and b['revision']==ctx.REVISION
 assert all(digest(ctx.SOURCE/n)==h for n,h in b['source_hashes'].items()) and all(digest(ctx.BUILD/n)==h for n,h in b['binaries'].items())
 return b

def session(rep):
 directory=P/('capture-'+str(rep).zfill(2));directory.mkdir(exist_ok=False)
 r={'started':stamp(),'passed':False,'round':rep,'rows':[],'trace_analysis':[],'restore_errors':[],
    'controller_sha256':digest(__file__),'worker_helper_sha256':digest(PREVIOUS/'capture.py'),'plan_sha256':digest(P/'experiment-plan.md')}
 persist=lambda:save(directory/'results.json',r)
 unloaded=False;persist()
 try:
  check_previous();assert not ctx.conflicts()
  r['health_before']=ctx.host.api('/health');r['config_before']=digest(ctx.host.CONFIG);persist()
  state('round-'+str(rep)+'-unload')
  unloaded=True;r['unload']=ctx.host.api('/unload?wait=30',True);assert r['unload'].get('status') in ['unloaded','not loaded']
  assert not [x for x in ctx.audit_processes() if (x['name'] or '').lower() in ['strata.exe','strata-q36.exe']]
  r['bandwidth-before']=ctx.bandwidth(directory,'bandwidth-before');persist()
  cases=['r0-l1024','r0-l16384'] if rep==1 else ['r0-l16384','r0-l1024']
  order=[('off','plain'),('on','plain'),('off','trace'),('on','trace')] if rep==1 else [('on','trace'),('off','trace'),('on','plain'),('off','plain')]
  r['schedule']=[{'case':c,'arm':a,'mode':m} for c in cases for a,m in order];persist()
  for case in cases:
   for arm,mode in order:
    tag=case+'-'+arm+'-'+mode;state('round-'+str(rep)+'-'+tag)
    cmd=[sys.executable,'-u',str(Path(__file__).resolve()),'--worker','--directory',str(directory),'--arm',arm,'--case',case,'--tag',tag]
    if mode=='trace':cmd+=['--profiler'];profile(directory,tag,cmd,arm)
    else:raw_run(cmd,directory/(tag+'.console.log'),arm)
    x=load(directory/(tag+'.json'));assert x['passed'] and x['exit_code']==0
    r['rows'].append({'tag':tag,'case':case,'arm':arm,'mode':mode,'prompt_ms':x['prompt_ms'],'decode_ms':x['decode_ms'],'output_sha256':x['output_sha256']});persist()
    if mode=='trace':
     rows,metrics=select(directory/(tag+'.sqlite'),x,case)
     assert (metrics['native_NVTX_events']==0 if arm=='off' else metrics['native_NVTX_events']>10000)
     with sqlite3.connect('file:'+(directory/(tag+'.sqlite')).as_posix()+'?mode=ro',uri=True) as db:
      metrics['diagnostic_warnings']=[dict(zip([d[0] for d in cur.description],v)) for cur in [db.execute('select * from DIAGNOSTIC_EVENT where severity>=2')] for v in cur.fetchall()]
     metrics.update(round=rep,case=case,arm=arm,sqlite_sha256=digest(directory/(tag+'.sqlite')),selector_sha256=digest(P/'selector.py'))
     csvfile(P/('kernel-ledger-'+str(rep)+'-'+case+'-'+arm+'.csv'),rows)
     save(P/('common-metrics-'+str(rep)+'-'+case+'-'+arm+'.json'),metrics);r['trace_analysis'].append(metrics);persist()
  # Enforce per-layer grid/block/shared-memory equality across off/on in this pair.
  for case in cases:
   a=list(csv.DictReader((P/('kernel-ledger-'+str(rep)+'-'+case+'-off.csv')).open()))
   b=list(csv.DictReader((P/('kernel-ledger-'+str(rep)+'-'+case+'-on.csv')).open()))
   keys=['iteration','layer','gridX','gridY','gridZ','blockX','blockY','blockZ','staticSharedMemory','dynamicSharedMemory']
   assert len(a)==len(b)==2520 and all(all(x[k]==y[k] for k in keys) for x,y in zip(a,b)),('GPU shape/ordering differs',case)
  r['bandwidth-after']=ctx.bandwidth(directory,'bandwidth-after');assert abs(r['bandwidth-after']['h2d_GBps']/r['bandwidth-before']['h2d_GBps']-1)<=.1
  r['passed']=True
 except BaseException as e:r['error']=repr(e);raise
 finally:
  signal.signal(signal.SIGINT,signal.SIG_IGN);state('round-'+str(rep)+'-restore')
  try:
   import psutil
   for child in psutil.Process().children(recursive=True):
    try:
     if Path(child.exe()).resolve()==(ctx.BUILD/'strata-q36.exe').resolve():child.kill();child.wait(timeout=30)
    except psutil.NoSuchProcess:pass
   if unloaded and r['health_before']['loaded']:
    if not ctx.host.api('/health')['loaded']:r['restore']=ctx.host.api('/load',True)
    r['health_after']=ctx.host.api('/health');assert r['health_after']['loaded'] and r['health_after']['model']==r['health_before']['model']
   if 'config_before' in r:r['config_after']=digest(ctx.host.CONFIG);assert r['config_before']==r['config_after']
  except BaseException as e:r['restore_errors'].append(repr(e));r['passed']=False
  r['finished']=stamp();persist()
 assert r['passed'] and not r['restore_errors']
 return r

def finalize(results,identities):
 state('final-verification')
 check_previous();assert all(digest(P/n)==h for n,h in identities.items())
 reference=load(ctx.BASE/'validation-01/results.json');pairs=[]
 for r in results:
  q=P/('capture-'+str(r['round']).zfill(2));assert r['passed'] and not r['restore_errors'] and len(r['rows'])==8 and len(r['trace_analysis'])==4
  for row in r['rows']:
   x=load(q/(row['tag']+'.json'));expected=next(y['output_ids'] for y in reference['rows'] if y['case']==row['case'] and y['repeat']==1)
   assert x['output_ids']==expected and x['layout']['slots']==[63] and x['layout']['chunks']==[2048] and x['layout']['slot_replacements'] and not any(x['layout']['slot_replacements'])
  for case in ['r0-l1024','r0-l16384']:
   off=next(x for x in r['trace_analysis'] if x['case']==case and x['arm']=='off');on=next(x for x in r['trace_analysis'] if x['case']==case and x['arm']=='on')
   assert off['selected_kernels']==on['selected_kernels']==2520
   rows={x['arm']+'-'+x['mode']:x for x in r['rows'] if x['case']==case}
   pairs.append({'round':r['round'],'case':case,'off':off,'on':on,'median_API_delay_on_over_off':on['API_end_to_GPU_start']['median_ns']/off['API_end_to_GPU_start']['median_ns'] if off['API_end_to_GPU_start']['median_ns'] else None,
    'decode_ms':{k:v['decode_ms'] for k,v in rows.items()},'on_over_off_trace_decode':rows['on-trace']['decode_ms']/rows['off-trace']['decode_ms'],
    'trace_over_plain_decode':{arm:rows[arm+'-trace']['decode_ms']/rows[arm+'-plain']['decode_ms'] for arm in ['off','on']}})
 assert len({r['config_after'] for r in results})==1 and digest(ctx.host.CONFIG)==results[0]['config_after']
 health=ctx.host.api('/health');assert health['loaded'] and health['model']==results[-1]['health_before']['model']
 summary={'passed':True,'verified_at':stamp(),'revision':ctx.REVISION,'same_diagnostic_binary':True,'new_engine_build':False,'new_numeric_dumps':0,'reused_numeric_gates':4,'selected_tests_reused':19,
 'measured_requests':16,'traces':8,'pairs':pairs,'service_restored_at':[r['finished'] for r in results],'bandwidth':[{n:r[n] for n in ['bandwidth-before','bandwidth-after']} for r in results],
 'daily_config_sha256':results[0]['config_after'],'current_health':{n:health[n] for n in ['status','model','loaded']},'root_cause_confirmed':False,'new_evidence_published':False,'default_changed':False,
 'limits':['off has no native pool boundaries; no off after-pool proportion claimed','all trace arms use CUDA profiler; unprofiled GPU-start timing unknown','n=2 processes per input/arm; layer samples not independent experiments','no driver submission timestamps, system stacks, stream/flush optimization or default change']}
 files={q.relative_to(P).as_posix():digest(q) for q in sorted(P.rglob('*')) if q.is_file() and '__pycache__' not in q.parts and not q.name.startswith('background') and q.name not in ['summary.json','README.md','evidence-manifest.json']}
 save(P/'evidence-manifest.json',files);summary.update(evidence_files=len(files),manifest_sha256=digest(P/'evidence-manifest.json'));save(P/'summary.json',summary)
 state('complete',state='complete',passed=True,finished=stamp(),service_restored=True)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--worker',action='store_true');parser.add_argument('--directory',type=Path);parser.add_argument('--arm',choices=['off','on']);parser.add_argument('--case');parser.add_argument('--tag');parser.add_argument('--profiler',action='store_true');a=parser.parse_args()
 if a.worker:previous_capture.worker(a);return
 assert not (P/'background-status.json').exists()
 S.update(started=stamp(),pid=os.getpid(),state='running',passed=False,revision=ctx.REVISION,root_cause_confirmed=False);state('preflight')
 try:
  check_previous();assert not ctx.conflicts()
  assert shutil.disk_usage(REPO).free>=8*1024**3,'Insufficient free disk for observer traces'
  save(P/'hardware.json',{'measured_at':stamp(),'gpu':subprocess.check_output(['nvidia-smi','--query-gpu=name,driver_version,memory.total','--format=csv,noheader'],text=True).strip(),'nsys_exe_sha256':digest(ctx.host.NSYS),'previous_manifest_sha256':digest(PREVIOUS/'evidence-manifest.json'),'worker_helper_sha256':digest(PREVIOUS/'capture.py')})
  state('model-identity');assert digest(ctx.host.MODEL)==load(ctx.BASE/'summary.json')['model']['sha256']
  v=load(P/'selector-validation.json');assert v['passed'] and v['selector_sha256']==digest(P/'selector.py')
  identities={q.name:digest(q) for q in P.iterdir() if q.suffix in ['.py','.md'] and q.name!='README.md'}
  save(P/'launch-identities.json',identities)
  profile(P,'probe',[str(PREVIOUS/'probe-complete.exe')],'on')
  with sqlite3.connect('file:'+(P/'probe.sqlite').as_posix()+'?mode=ro',uri=True) as db:
   assert db.execute("select count(*) from NVTX_EVENTS where text='JT probe' and end>start").fetchone()[0]>=1
  results=[session(rep) for rep in [1,2]]
  finalize(results,identities)
 except BaseException as e:traceback.print_exc();state('failed',state='failed',passed=False,error=repr(e),finished=stamp());raise
if __name__=='__main__':main()
