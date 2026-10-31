"""Detached two-round reproduction; stops on failed gates and never publishes."""
from pathlib import Path
import csv,json,os,shutil,subprocess,sys,time,traceback
from context import OUT,REPO,BASE,BASE_BUILD,BUILD,SOURCE,REVISION,host,check_identity,conflicts,digest,save,stamp
P=OUT
S={'started':stamp(),'pid':os.getpid(),'state':'running','phase':'preflight','passed':False,'revision':REVISION,'root_cause_confirmed':False}
def state(phase,**kw):
 S.update(phase=phase,updated=stamp(),**kw);save(P/'background-status.json',S);print(phase,flush=True)
def run(args,phase):
 state(phase)
 result=subprocess.run([sys.executable,'-u',str(P/args[0]),*args[1:]],cwd=REPO)
 if result.returncode:raise RuntimeError(phase+' failed with exit '+str(result.returncode))
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def finalize(identities):
 state('final-file-and-ledger-verification')
 assert all(digest(P/n)==h for n,h in identities.items()),'Controller source changed during run'
 b=load(P/'build-complete.json');assert b['passed'] and b['revision']==REVISION and b['plan_sha256']==digest(P/'completion-plan.md')
 assert b['script_sha256']==digest(P/'build_complete.py')
 assert all(digest(BUILD/n)==h for n,h in b['binaries'].items()) and all(digest(SOURCE/n)==h for n,h in b['source_hashes'].items())
 assert digest(Path(b['adapter']['exe']).parent/'strata_kq.dll')==digest(BUILD/'strata_kq.dll')
 assert digest(b['adapter']['exe'])==b['adapter']['sha256']
 assert '0 tests failed out of 19' in (P/'build-complete-2.log').read_text(encoding='utf-8')
 assert 'no work to do' in (P/'build-complete-3.log').read_text(encoding='utf-8')
 observations=[];paths=[];configs=[]
 reference=load(BASE/'validation-01/results.json')
 for rep in [1,2]:
  q=P/('capture-'+str(rep).zfill(2));r=load(q/'results.json')
  assert r['passed'] and not r['restore_errors'] and r['finished']
  assert r['script_sha256']==digest(P/'capture.py') and r['plan_sha256']==digest(P/'completion-plan.md')
  assert r['build_results_sha256']==digest(P/'build-complete.json') and len(r['requests'])==8
  assert len(r['numeric'])==4
  for n in r['numeric']:
   d=P/'capture-01'/('numeric-'+n['case']+'-'+n['arm']+'.f32')
   original=next(x for x in reference['numeric'] if x['case']==n['case'])
   assert n['finite'] and d.stat().st_size==n['bytes']==64*248320*4 and digest(d)==n['sha256']==original['sha256']
  assert r['config_sha256_before']==r['config_sha256_after'] and r['health_after']['loaded'] and r['health_after']['model']==r['health_before']['model']
  configs.append(r['config_sha256_after'])
  percase={}
  for case in ['r0-l1024','r0-l16384']:
   cells={}
   for arm in ['baseline','off','on','trace']:
    tag=case+'-'+('on-trace' if arm=='trace' else arm+'-plain');x=load(q/(tag+'.json'))
    expected=next(a['output_ids'] for a in reference['rows'] if a['case']==case and a['repeat']==1)
    assert x['passed'] and x['exit_code']==0 and x['output_ids']==expected and len(x['output_ids'])==64
    assert x['layout']['slots']==[63] and x['layout']['chunks']==[2048] and x['layout']['slot_replacements'] and not any(x['layout']['slot_replacements'])
    cells[arm]={n:x[n] for n in ['prompt_ms','decode_ms','output_sha256']}
   cells['ratios']={label:{n:cells[a][n]/cells[z][n] for n in ['prompt_ms','decode_ms']} for label,a,z in [('off_over_baseline','off','baseline'),('marks_on_over_off','on','off'),('trace_over_marks_on','trace','on')]}
   percase[case]=cells
  observations.append({'round':rep,'cases':percase,'bandwidth':{n:r[n] for n in ['bandwidth-before','bandwidth-after']},'service_restored_at':r['finished']})
  results=load(P/('critical-path-'+str(rep).zfill(2)+'.json'))
  for c in results['cases']:
   assert c['all_completion_ordinals_unique_and_tasks_matched'] and c['all_task_ids_unique_and_rows_covered'] and c['all_token_ledgers_close'] and c['all_phase_fork_joins_close']
  phases=list(csv.DictReader((P/('phase-ledger-'+str(rep).zfill(2)+'.csv')).open(encoding='utf-8')))
  tokens=list(csv.DictReader((P/('token-ledger-'+str(rep).zfill(2)+'.csv')).open(encoding='utf-8')))
  assert len(tokens)==126 and len(phases)==sum(c['all_request_phases'] for c in results['cases'])
  for x in phases:
   assert int(x['last_release_ordinal'])==int(x['tasks'])
   assert sum(int(x[n]) for n in ['pre_publish_ns','critical_chain_job_body_ns','critical_chain_handoff_and_queue_ns','phase_tail_ns'])==int(x['wall_ns'])
  for x in tokens:assert sum(int(x[n]) for n in ['gpu_submit_ns','route_wait_ns','phase_pre_publish_ns','critical_branch_job_body_ns','critical_branch_queue_handoff_ns','phase_tail_ns','CPU_moe_other_ns','token_other_ns'])==int(x['wall_ns'])
  paths.append({'round':rep,'results':results})
 assert len(set(configs))==1 and digest(host.CONFIG)==configs[0]
 check_identity()
 for name in ['qwen36-copy3905','qwen36-cpu-mechanism','qwen36-job-path']:
  root=REPO/'reports/tobeo-20261030'/name
  assert all(digest(root/n)==h for n,h in load(root/'evidence-manifest.json').items()),name
 health=host.api('/health');assert health['loaded'] and health['model']==r['health_before']['model']
 assert not [p for p in conflicts() if p['pid']!=os.getpid()]
 findings={}
 for case in ['r0-l1024','r0-l16384']:
  cases=[next(c for c in x['results']['cases'] if c['case']==case) for x in paths]
  findings[case]={'late_GPU_start_layers':[c['totals']['GPU_half_start_after_pool'] for c in cases],
   'MoE_layers_per_trace':[c['MoE_layers'] for c in cases],
   'late_start_observed_in_both_traces':all(c['totals']['GPU_half_start_after_pool']>0 for c in cases)}
 summary={'passed':True,'verified_at':stamp(),'revision':REVISION,'selected_tests':19,'rounds':2,'new_numeric_dumps':4,'measured_requests':16,'traces':4,
  'observations':observations,'paths':paths,'findings':findings,'root_cause_confirmed':False,'new_evidence_published':False,'default_changed':False,
  'current_health':{n:health[n] for n in ['status','model','loaded']},'daily_config_sha256':configs[0],
  'limits':['two repeats per cell; trace/marks perturbation reported, not isolated causal driver proof','baseline plain has no native pool boundaries; uninstrumented late-start occurrence not directly measured','no CPU sampling/kernel stacks; internal driver submission unknown','no optimization arm, counterfactual gain, default change or cross-backend validation']}
 files={p.relative_to(P).as_posix():digest(p) for p in sorted(P.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and not p.name.startswith('background') and p.name not in ['summary.json','README.md','evidence-manifest.json']}
 save(P/'evidence-manifest.json',files);summary.update(evidence_files=len(files),manifest_sha256=digest(P/'evidence-manifest.json'));save(P/'summary.json',summary)
 state('complete',state='complete',passed=True,finished=stamp(),service_restored=True)

def main():
 assert not (P/'background-status.json').exists()
 state('preflight')
 try:
  assert not SOURCE.exists() and not BUILD.exists() and not (P/'capture-01').exists() and not (P/'capture-02').exists()
  check_identity();assert not conflicts(),'Another GPU/build/download/conversion job is active'
  assert shutil.disk_usage(REPO).free>=8*1024**3,'Insufficient free disk for diagnostic build and traces'
  state('model-identity')
  assert digest(host.MODEL)==load(BASE/'summary.json')['model']['sha256']
  assert subprocess.check_output(['git','-C',str(REPO/'build-native-baseline/src-main-870aedd9'),'rev-parse','HEAD'],text=True).strip()==REVISION
  identities={p.name:digest(p) for p in P.iterdir() if p.suffix in ['.py','.hpp','.md'] and p.name!='README.md'}
  save(P/'launch-identities.json',identities)
  hardware=subprocess.check_output(['nvidia-smi','--query-gpu=name,driver_version,memory.total','--format=csv,noheader'],text=True)
  save(P/'hardware.json',{'measured_at':stamp(),'gpu':hardware.strip()})
  run(['build_complete.py'],'diagnostic-build-and-19-tests')
  for rep in [1,2]:
   run(['capture.py','--round',str(rep)],'capture-round-'+str(rep))
   run(['analyze.py','--round',str(rep)],'analyze-round-'+str(rep))
  finalize(identities)
 except BaseException as e:
  traceback.print_exc();state('failed',state='failed',passed=False,error=repr(e),finished=stamp());raise
if __name__=='__main__':main()
