"""Continue the declared matrix using execution-04's passed immutable gates."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime,timedelta,timezone
import psutil

OUT=Path(__file__).resolve().parent;REPO=OUT.parents[2]
sys.path.insert(0,str(REPO));sys.path.insert(0,str(REPO/'tools'))
import calibrate as C
from serve.server import StrataEngine,child_env
sys.path.insert(0,str(REPO/'reports/tobeo-20261022/qwen36-context-curve'))
from windows_telemetry import Telemetry,thread_affinities

source=OUT/'run_experiment.py'
tree=ast.parse(source.read_text(encoding='utf-8'))
names={'stamp','digest','save','request','arguments','environment','resume_downloads','bandwidth','sample','parse_placement','run_arm'}
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
assert len(nodes)==len(names)
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),globals())
prior=json.loads((OUT/'execution-04/results.json').read_text(encoding='utf-8'))
assert prior['gate_passed'] and prior.get('finished') and not prior.get('restore_errors')
assert len(prior['gate'])==3 and all(len(v['rows'])==3 and len(v['tasks'])==6 for v in prior['gate'].values())
assert all(row['identical'] and row['draft_counts_identical'] and row['protocol_passed'] for arm in prior['gate'].values() for row in arm['rows'])
assert all(row['task_passed'] for arm in prior['gate'].values() for row in arm['tasks'])
cfg=prior['resolved_config']
data=json.loads((OUT/'workloads.json').read_text(encoding='utf-8'))
assert digest(OUT/'workloads.json')==prior['workloads_sha256']
workloads=data['performance'];warm=data['warmup_ids']
expected={row['name']:row['output_ids'] for row in prior['gate']['all']['rows']}
expected_drafts={row['name']:(row['timings']['drafts_offered'],row['timings']['drafts_accepted']) for row in prior['gate']['all']['rows']}
slots=(prior['fixed_cache']['slots'],prior['fixed_cache']['mib']);active=None;unloaded=False
RUN=OUT/'performance-04';RUN.mkdir(exist_ok=False)
record={'started':stamp(),'phase':'preparing','passed':False,'arms':[],'rows':[],
        'fingerprints':prior['fingerprints'],'fixed_cache':prior['fixed_cache'],'resolved_config':cfg,
        'fingerprint_reuse_from':'execution-03 hashes and execution-04 stat checks',
        'gate_reference_sha256':digest(OUT/'execution-04/results.json'),'gate_passed':True,'gate':prior['gate'],
        'downloads_suspended':[],'service_transition':{},'plan_sha256':digest(OUT/'experiment-plan.md'),
        'runner_sha256':digest(__file__),'helpers_sha256':digest(source),'workloads_sha256':prior['workloads_sha256'],
        'daily_config_sha256_before':digest(REPO/'strata-iq3_s.json')}


def download_roots():
    roots={}
    for p in psutil.process_iter(['name','cmdline']):
        if 'python' in (p.info['name'] or '').lower() and any(Path(a).name in ['download_deepseek.py','download_deepseek_fresh.py'] for a in (p.info['cmdline'] or [])):
            roots[p.pid]=p
    return roots


def checkpoint_state():
    manifest=json.loads((REPO/'reports/tobeo-20261028/deepseek41-community/download-manifest.json').read_text(encoding='utf-8'))
    snapshot={}
    for item in manifest['files']:
        for suffix in ['','.part','.part.chunks']:
            path=Path(item['destination']+suffix)
            if path.exists():
                stat=path.stat();snapshot[str(path)]={'bytes':stat.st_size,'mtime_ns':stat.st_mtime_ns}
                if suffix=='.part.chunks':snapshot[str(path)]['sha256']=digest(path)
    return snapshot


def stop_downloads():
    roots=download_roots();assert roots,'Expected the existing resumable downloader'
    primary=[p for p in roots.values() if p.ppid() not in roots]
    assert len(primary)==1
    p=primary[0]
    record['download_restart']={'args':p.cmdline(),'cwd':p.cwd()}
    record['downloads_stopped']=[];save()
    targets=dict(roots)
    try:
        for p in roots.values():p.suspend()
        for p in roots.values():
            for child in p.children(recursive=True):
                if child.name().lower() in ['python.exe','curl.exe']:targets[child.pid]=child
        for p in targets.values():
            try:
                item={'pid':p.pid,'created':p.create_time(),'name':p.name()}
                p.terminate();record['downloads_stopped'].append(item);save()
            except psutil.NoSuchProcess:pass
        gone,alive=psutil.wait_procs(list(targets.values()),timeout=15)
        assert not alive,'Downloader did not exit'
    finally:
        # Do not leave a partially stopped tree suspended if termination itself failed.
        for p in targets.values():
            try:p.resume()
            except psutil.NoSuchProcess:pass
    time.sleep(5)
    assert not download_roots()
    record['download_checkpoint_baseline']=checkpoint_state();record['download_pause_at']=stamp();save()


def resume_downloads():
    launch=record.get('download_restart')
    if not launch:return
    roots=download_roots()
    if roots:
        record['download_restarted']={'already_running':list(roots)};save();return
    logs=REPO/'reports/tobeo-20261028/deepseek41-community'
    stdout=logs/'download-v5.stdout.log';stderr=logs/'download-v5.stderr.log'
    with stdout.open('ab') as out,stderr.open('ab') as err:
        child=subprocess.Popen(launch['args'],cwd=launch['cwd'],stdout=out,stderr=err,
                               creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    time.sleep(1);assert child.poll() is None,'Downloader restart exited'
    record['download_restarted']={'pid':child.pid,'created':psutil.Process(child.pid).create_time(),
                                  'stdout':str(stdout),'stderr':str(stderr)};save()


def assert_downloads_quiet(stage):
    roots=download_roots();now=checkpoint_state()
    check={'stage':stage,'at':stamp(),'no_downloader':not roots,
           'unchanged':now==record['download_checkpoint_baseline']}
    if roots or not check['unchanged']:check.update(active_pids=list(roots),checkpoint_now=now)
    record.setdefault('download_quiet_checks',[]).append(check);save()
    assert check['unchanged'] and check['no_downloader'],'Downloader activity during formal window: '+stage


save()
try:
    for path,info in record['fingerprints'].items():
        p=Path(path);stat=p.stat();assert stat.st_size==info['bytes'] and stat.st_mtime_ns==info['mtime_ns']
    assert digest(cfg['exe'])==record['fingerprints'][cfg['exe']]['sha256']
    state=record['service_transition'];state['health_before']=request('/health')
    state['unload']=request('/unload?wait=30',True);assert state['unload'].get('status') in ['unloaded','not loaded']
    unloaded=True;save();stop_downloads();before=bandwidth('bandwidth-before')
    record['phase']='benchmark';save()
    for n,order in enumerate([['all','p-cores','measure'],['p-cores','measure','all'],['measure','all','p-cores'],['measure','p-cores','all'],['all','measure','p-cores']]):
        tasks=workloads[n%3:]+workloads[:n%3]
        for mode in order:
            tag=f'round-{n}-{mode}'
            assert_downloads_quiet('before-'+tag)
            run_arm(tag,mode,True,n,tasks)
            assert_downloads_quiet('after-'+tag)
    after=bandwidth('bandwidth-after');record['bandwidth_relative_drift']=abs(after/before-1)
    assert record['bandwidth_relative_drift']<=.15
    assert_downloads_quiet('after-bandwidth')
    record['passed']=True;record['phase']='complete';save()
except BaseException as exc:record['phase']='failed';record['error']=repr(exc);save();raise
finally:
    errors=[]
    try:resume_downloads()
    except BaseException as exc:errors.append(repr(exc))
    try:
        state=record['service_transition']
        if unloaded and state['health_before'].get('loaded'):
            state['load']=request('/load',True);state['health_after']=request('/health');assert state['health_after']['loaded']
        record['daily_config_sha256_after']=digest(REPO/'strata-iq3_s.json')
        assert record['daily_config_sha256_after']==record['daily_config_sha256_before']
    except BaseException as exc:errors.append(repr(exc))
    if errors:record['passed']=False;record['restore_errors']=errors
    record['finished']=stamp();save()
    if errors:raise RuntimeError(str(errors))
