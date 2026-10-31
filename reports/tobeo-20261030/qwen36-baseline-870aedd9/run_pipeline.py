"""Detached, fail-closed build/numeric/layout validation. No root-cause experiment."""
from pathlib import Path
import csv,hashlib,importlib.util,json,os,re,shutil,signal,subprocess,sys,tarfile,time,traceback
import numpy as np
import psutil
P=Path(__file__).resolve().parent
REPO=P.parents[2]
OLD=REPO/'reports/tobeo-20261029/qwen36-repro-baseline'
sys.path.insert(0,str(OLD))
import build_baseline as old
sys.path.insert(0,str(P.parent/'qwen36-systems'))
import common as host
from validate_baseline import audit_processes
REV='870aedd9e1ebe1c91f94da93b59af17729f6c5c0'
ROOT=REPO/'build-native-baseline'
SOURCE=ROOT/'src-main-870aedd9'
BUILD=ROOT/'build-main-870aedd9-cuda132-sm120'
DEPS=ROOT/'deps-main-870aedd9'
RUN=P/'validation-01'
CUDA=old.CUDA
MODEL=old.MODEL
stamp,digest,save=old.stamp,old.digest,old.save
STATE={'started':stamp(),'pid':os.getpid(),'state':'running','phase':'preflight','passed':False,'revision':REV,'root_cause_investigation_started':False}
def state(phase,**kw):
 STATE.update(phase=phase,updated=stamp(),**kw);save(P/'background-status.json',STATE);print(phase,flush=True)
def git(*a,cwd=SOURCE):return subprocess.check_output(['git','-C',str(cwd),*a],text=True).strip()
def identity():
 assert git('rev-parse','HEAD')==REV and not git('status','--porcelain','--untracked-files=no')
def env():
 e={k:v for k,v in os.environ.items() if not k.upper().startswith(('STRATA_','DS4_')) and k.upper() not in ['CUDA_LAUNCH_BLOCKING','CUDA_DEVICE_MAX_CONNECTIONS','CUDA_FORCE_PTX_JIT']}
 e.update(STRATA_MMQ_KQ='1',STRATA_Q8_PACKED='1',STRATA_Q36_FIXED_SLOTS='1',CUDA_VISIBLE_DEVICES='0',CUDA_MODULE_LOADING='EAGER')
 e['PATH']=os.pathsep.join([str(BUILD),str(CUDA/'bin/x64'),str(CUDA/'bin'),e.get('PATH','')]);return e
ARGS=['--native',str(MODEL),'--max-context','32768','--prefill','2048','--pool-workers','7','--mtp','0','--expert-slots','63']
def layout(log):
 x=host.layout(log);t=log.read_text(encoding='utf-8',errors='replace')
 assert x['slots']==[63] and x['chunks']==[2048] and x['slot_replacements'] and not any(x['slot_replacements'])
 assert 'prompt experts on MMQ (int8)' in t and 'not found next to the engine' not in t
 return x

def build():
 assert not BUILD.exists() and not DEPS.exists() and not (P/'build-results.json').exists()
 identity();host.check_identity()
 b={'started':stamp(),'passed':False,'revision':REV,'commands':[],'script_sha256':digest(__file__),'plan_sha256':digest(P/'experiment-plan.md')}
 persist=lambda:save(P/'build-results.json',b)
 persist()
 try:
  state('dependency-and-model-fingerprints')
  archive=ROOT/('llama-'+old.GGML_REVISION+'.tar.gz');assert digest(archive)==old.GGML_SHA
  DEPS.mkdir()
  with tarfile.open(archive) as t:t.extractall(DEPS,filter='data')
  ggml=DEPS/('llama.cpp-'+old.GGML_REVISION)
  files={q.relative_to(ggml).as_posix():digest(q) for q in sorted(ggml.rglob('*')) if q.is_file()};save(P/'ggml-files.json',files)
  b['ggml']={'revision':old.GGML_REVISION,'archive_sha256':old.GGML_SHA,'file_count':len(files),'source':str(ggml),'manifest_sha256':digest(P/'ggml-files.json')}
  assert MODEL.stat().st_size==22853663008 and digest(MODEL)==old.MODEL_SHA
  b['model']={'bytes':MODEL.stat().st_size,'sha256':old.MODEL_SHA}
  native=old.helper('reports/tobeo-20261022/windows-native-baseline/build_native.py','compiler_870')
  py=Path(sys.executable).parent;os.environ['PATH']=os.pathsep.join([str(py/'Scripts'),str(py/'Library/bin'),os.environ['PATH']])
  compiler_env,cmake,vs=native.compiler_environment();compiler_env={k:v for k,v in compiler_env.items() if not k.upper().startswith(('STRATA_','DS4_'))}
  prior=json.loads((OLD/'build-results.json').read_text(encoding='utf-8'))
  tests=[*prior['tests'],'auto_cache_test','window_limits_test'];assert len(tests)==len(set(tests))==19
  b['tests']=tests;b['source_tree']=git('rev-parse','HEAD^{tree}');b['toolchain']={k:prior['toolchain'][k] for k in ['vs','cl','cmake','ninja','cuda','python']};b['current_vs']=vs
  for n,c in {'cl':[shutil.which('cl.exe',path=compiler_env['PATH'])], 'cmake':[cmake,'--version'], 'ninja':[shutil.which('ninja.exe',path=compiler_env['PATH']),'--version'], 'nvcc':[str(CUDA/'bin/nvcc.exe'),'--version']}.items():
   v=subprocess.run(c,env=compiler_env,capture_output=True);raw=v.stdout+v.stderr;(P/(n+'-version.log')).write_bytes(raw);b['toolchain'][n+'_version']=raw.decode('utf-8',errors='replace')
  oldggml=prior['ggml']['source']
  for i,row in enumerate(prior['commands']):
   command=[]
   for word in row['command']:
    for a,z in [(prior['source'],str(SOURCE)),(prior['build'],str(BUILD)),(oldggml,str(ggml))]:
     word=word.replace(a,z).replace(a.replace(chr(92),'/'),z.replace(chr(92),'/'))
    command.append(word)
   if i==1:
    at=command.index('--parallel');command[at:at]=['auto_cache_test','window_limits_test']
   if i==3:command+=['auto_cache_test','window_limits_test']
   if i==2:command[-1]='^('+'|'.join(tests)+')$'
   b['commands'].append({'command':command});persist();state('build-command-'+str(i));start=time.monotonic()
   with (P/('build-'+str(i)+'.log')).open('w',encoding='utf-8') as f:
    code=subprocess.run(command,env=compiler_env,stdout=f,stderr=subprocess.STDOUT,timeout=3600).returncode
   b['commands'][-1].update(exit_code=code,seconds=time.monotonic()-start);persist();assert code==0
  assert '0 tests failed out of 19' in (P/'build-2.log').read_text(encoding='utf-8')
  assert 'no work to do' in (P/'build-3.log').read_text(encoding='utf-8')
  adapter=REPO/'reports/tobeo-20261028/qwen36-pr4347/file_entry.cpp'
  block=(BUILD/'build.ninja').read_text(encoding='utf-8').split('build strata-q36.exe:',1)[1].split(chr(10)*2,1)[0]
  libs=re.search(r'^  LINK_LIBRARIES = (.*)$',block,re.M).group(1).split()
  d=P/'adapter';d.mkdir();shutil.copy2(BUILD/'strata_kq.dll',d/'strata_kq.dll')
  cl=shutil.which('cl.exe',path=compiler_env['PATH']);link=shutil.which('link.exe',path=compiler_env['PATH'])
  cmds=[[cl,'/nologo','/c','/O2','/EHsc','/std:c++20','/MD','/I'+str(SOURCE/'include'),str(adapter),'/Fo'+str(d/'entry.obj')],
   [link,'/nologo','/OUT:'+str(d/'strata-q36-file.exe'),'/MACHINE:X64','/INCREMENTAL:NO','/SUBSYSTEM:CONSOLE','/OPT:REF','/OPT:ICF','/LIBPATH:'+str(CUDA/'lib/x64'),'/MANIFEST:EMBED','/MANIFESTINPUT:'+str(SOURCE/'cmake/strata-utf8.manifest'),str(d/'entry.obj'),*libs]]
  with (P/'adapter-build.log').open('w',encoding='utf-8') as f:
   for c in cmds:subprocess.run(c,cwd=BUILD,env=compiler_env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
  b['adapter']={'exe':str(d/'strata-q36-file.exe'),'sha256':digest(d/'strata-q36-file.exe'),'dll_sha256':digest(d/'strata_kq.dll'),'source_sha256':digest(adapter),'commands':cmds}
  b['binaries']={n:digest(BUILD/n) for n in ['strata-q36.exe','strata_kq.dll','strata-q36.pdb']}
  b['engine_version']=re.search(r'project\(strata VERSION ([0-9.]+)',(SOURCE/'CMakeLists.txt').read_text(encoding='utf-8')).group(1)
  assert b['engine_version']=='0.1.54'
  assert all(digest(ggml/n)==h for n,h in files.items()),'Dependency source changed during build'
  identity();host.check_identity();b['passed']=True
 except BaseException as e:b['error']=repr(e);raise
 finally:b['finished']=stamp();persist()
 return b

def validate(b):
 RUN.mkdir(exist_ok=False)
 r={'started':stamp(),'passed':False,'phase':'preflight','numeric':[],'rows':[],'restore_errors':[],
    'script_sha256':digest(__file__),'plan_sha256':digest(P/'experiment-plan.md'),'build_results_sha256':digest(P/'build-results.json'),'args':ARGS,
    'harness_sha256':digest(SOURCE/'tools/qwen35/q36_harness.py'),'protocol_sha256':digest(host.FIXTURES/'run_curve.py')}
 persist=lambda:save(RUN/'results.json',r)
 attempted=False;active=None
 persist()
 try:
  identity();assert all(digest(BUILD/n)==h for n,h in b['binaries'].items())
  for k in list(os.environ):
   if k.upper().startswith(('STRATA_','DS4_')) or k.upper() in ['CUDA_LAUNCH_BLOCKING','CUDA_DEVICE_MAX_CONNECTIONS','CUDA_FORCE_PTX_JIT']:del os.environ[k]
  os.environ.update(env())
  conflicts=[x for x in audit_processes() if any(z in (x['name'] or '').lower() for z in ['nsys','ncu','nvcc','ninja']) or any(Path(a).name.lower().startswith('download') for a in x['cmdline'] or [])]
  assert not conflicts,'Other research/download processes are active'
  r['config_sha256_before']=digest(host.CONFIG);r['health_before']=host.api('/health');persist()
  r['phase']='unload';state('unloading-daily-service');attempted=True;r['unload']=host.api('/unload?wait=30',True)
  assert r['unload'].get('status') in ['unloaded','not loaded']
  assert not [x for x in audit_processes() if (x['name'] or '').lower() in ['strata.exe','strata-q36.exe']]
  r['bandwidth-before']=host.bandwidth(RUN,'bandwidth-before')
  reference=json.loads((P.parent/'qwen36-copy3905/execution-02/results.json').read_text(encoding='utf-8'))
  cases=['r0-l1024','r0-l16384'];ids={n:json.loads((host.FIXTURES/(n+'.ids.json')).read_text()) for n in [*cases,'r1-l1024']}
  expected={n:next(x['output_ids'] for x in reference['rows'] if x['case']==n and x['pair'] is None) for n in cases}
  r['fixtures']={n:{'tokens':len(a),'sha256':host.protocol.tokens_hash(a)} for n,a in ids.items()}
  r['numeric_reference_results_sha256']=digest(P.parent/'qwen36-copy3905/execution-02/results.json')
  r['phase']='numeric';persist();state('full-logit-numeric-gates')
  for n in cases:
   tokens=RUN/(n+'.tokens');forced=RUN/(n+'.forced');dump=RUN/(n+'.f32');log=RUN/(n+'.numeric.log')
   tokens.write_text(','.join(map(str,ids[n])),encoding='ascii');forced.write_text(','.join(map(str,expected[n][:63])),encoding='ascii')
   command=[b['adapter']['exe'],*ARGS,'--tokens-file',str(tokens),'--force-file',str(forced),'--dump-full-logits',str(dump)]
   row={'case':n,'command':command};r['numeric'].append(row);persist()
   with log.open('w',encoding='utf-8') as f:
    active=subprocess.Popen(command,env=env(),stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    row['exit_code']=active.wait(timeout=900)
   assert row['exit_code']==0;row['layout']=layout(log)
   t=log.read_text(encoding='utf-8');m=re.search(r'^gen: ([0-9 ]+)$',t,re.M);row['output_ids']=[int(x) for x in m[1].split()] if m else []
   row['bytes']=dump.stat().st_size;assert row['bytes']==64*248320*4
   a=np.memmap(dump,dtype=np.float32,mode='r');row['finite']=bool(np.isfinite(a).all());del a
   row['sha256']=digest(dump);ref=next(x for x in reference['numeric'] if x['case']==n and x['arm']=='baseline')
   row['bitwise_matches_reference']=row['sha256']==ref['sha256'];persist()
   assert row['finite'] and row['bitwise_matches_reference'] and row['output_ids']==expected[n],'Numeric identity failed; preserve and stop'
  nh=old.helper('build-native-baseline/src-main-870aedd9/tools/qwen35/q36_harness.py','harness_870')
  r['phase']='repeatability';persist();state('four-fresh-process-output-layout-gates')
  for repeat in range(2):
   for n in (cases if repeat==0 else list(reversed(cases))):
    tag='repeat-'+str(repeat+1)+'-'+n;log=RUN/(tag+'.engine.log');engine=None
    row={'case':n,'repeat':repeat+1,'tag':tag};r['rows'].append(row);persist()
    try:
     engine=nh.Eng(str(BUILD/'strata-q36.exe'),ARGS,env=env(),log=str(log));row['pid']=engine.p.pid;row['ready']=engine.ready
     row['warmup']=host.protocol.measured_request(engine,ids['r1-l1024'],64)
     assert row['warmup']['generated_tokens']==64 and row['warmup']['draft_offered']==row['warmup']['reused_tokens']==0
     row.update(host.protocol.measured_request(engine,ids[n],64))
    finally:
     if engine:
      engine.close()
      if engine.p.poll() is None:engine.p.kill();engine.p.wait(timeout=30)
      row['exit_code']=engine.p.returncode
     persist()
    row['layout']=layout(log)
    row['passed']=row['exit_code']==0 and row['output_ids']==expected[n] and row['generated_tokens']==64 and row['finish']=='length' and row['reused_tokens']==row['draft_offered']==0
    persist();assert row['passed']
  r['bandwidth-after']=host.bandwidth(RUN,'bandwidth-after');assert abs(r['bandwidth-after']['h2d_GBps']/r['bandwidth-before']['h2d_GBps']-1)<=.1
  identity();host.check_identity();assert all(digest(BUILD/n)==h for n,h in b['binaries'].items())
  r['passed']=True;r['phase']='complete'
 except BaseException as e:r['error']=repr(e);r['phase']='failed';raise
 finally:
  signal.signal(signal.SIGINT,signal.SIG_IGN);state('restoring-daily-service')
  try:
   if active and active.poll() is None:subprocess.run(['taskkill','/PID',str(active.pid),'/T','/F'],capture_output=True)
   for child in psutil.Process().children(recursive=True):
    try:
     if Path(child.exe()).resolve() in [(BUILD/'strata-q36.exe').resolve(),Path(b['adapter']['exe']).resolve()]:child.kill();child.wait(timeout=30)
    except psutil.NoSuchProcess:pass
   if attempted and r['health_before']['loaded']:
    if not host.api('/health')['loaded']:r['restore']=host.api('/load',True)
    r['health_after']=host.api('/health');assert r['health_after']['loaded'] and r['health_after']['model']==r['health_before']['model']
   r['config_sha256_after']=digest(host.CONFIG);assert r['config_sha256_after']==r['config_sha256_before']
  except BaseException as e:r['restore_errors'].append(repr(e));r['passed']=False
  r['finished']=stamp();persist()
 assert r['passed'] and not r['restore_errors']
 return r

def main():
 assert not (P/'background-status.json').exists() and not RUN.exists()
 state('preflight')
 try:
  b=build();r=validate(b);state('sealing-static-evidence')
  assert len(r['numeric'])==2 and len(r['rows'])==4 and all(x['passed'] for x in r['rows'])
  m={q.relative_to(P).as_posix():digest(q) for q in sorted(P.rglob('*')) if q.is_file() and '__pycache__' not in q.parts and not q.name.startswith('background') and q.name not in ['summary.json','README.md','evidence-manifest.json']}
  save(P/'evidence-manifest.json',m)
  save(P/'summary.json',{'passed':True,'verified_at':stamp(),'revision':REV,'engine_version':b['engine_version'],'selected_tests':len(b['tests']),'numeric_dumps':r['numeric'],'requests':r['rows'],
   'bandwidth':{n:r[n] for n in ['bandwidth-before','bandwidth-after']},'service_restored_at':r['finished'],'restore_errors':r['restore_errors'],'source_unchanged':True,'model':b['model'],'binaries':b['binaries'],
   'baseline_ready':True,'root_cause_investigation_complete':False,'manifest_sha256':digest(P/'evidence-manifest.json'),'evidence_files':len(m)})
  state('baseline-ready',state='baseline_ready',passed=True,finished=stamp(),service_restored=True)
 except BaseException as e:
  traceback.print_exc();state('failed',state='failed',passed=False,error=repr(e),finished=stamp());raise
if __name__=='__main__':main()
