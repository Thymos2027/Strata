"""Bounded ABBA of the dedicated DeepSeek Windows Engram-direct switch."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import threading
import time

OUT=Path(__file__).resolve().parent
CASE=OUT.parent
spec=importlib.util.spec_from_file_location('recorded_case_helpers',CASE/'run_case.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
RUN=OUT/'ab-01';RUN.mkdir(exist_ok=False)
M.RUN=RUN
M.record={'phase':'preparing','passed':False,'started':M.stamp(),'loads':[],'arms':[],
          'controller_sha256':M.digest(__file__),'protocol_sha256':M.digest(OUT/'experiment-plan.md'),
          'helper_sha256':M.digest(CASE/'run_case.py')}
r=M.record
cfg=json.loads((CASE/'execution-03/config.json').read_text(encoding='utf-8'))
assert M.digest(cfg['exe'])==json.loads((CASE/'engine.json').read_text())['sha256']
cfg['args'] += ['--verbose']
os.environ.update(DS4_ENGRAM_CACHE_MB='256',STRATA_DS4_SLOT_KEEP='0',STRATA_DS4_AUTO_PIN='0',STRATA_DS4_REUSE='0')
for name in ('DS4_EG_CHECK','DS4_ENGRAM_THREADS'):
    os.environ.pop(name,None)
tasks=[]
for n in (1024,4096):
    actual=json.loads((CASE/'execution-03'/f'performance-0-{n}.response.json').read_text(encoding='utf-8'))
    tasks.append({'target_tokens':n,'messages':actual['request']['messages']})
r['tasks']=tasks
r['daily_config_sha256_before']=M.digest(M.ROOT/'strata-iq3_s.json')
r['health_before']=M.api('/health',base=M.DAILY)
M.save()
unloaded=False;stop=threading.Event()


def guard():
    while not stop.wait(.5):
        try:
            s=M.commit_status()
            if M.server is not None and (s['committed_bytes']>.94*s['limit_bytes'] or s['available_ram_bytes']<4*1024**3):
                M.write(RUN/'memory-guard-trigger.json',{'time':M.stamp(),**s})
                for p in M.engine_children():p.terminate()
                return
        except Exception as e:
            M.write(RUN/'memory-guard-error.json',{'error':repr(e)});return


thread=threading.Thread(target=guard,daemon=True);thread.start()
expected={};placement=None
try:
    r['unload']=M.api('/unload?wait=30',{},base=M.DAILY,timeout=600)
    assert r['unload'].get('status') in ('unloaded','not loaded')
    unloaded=True
    for tag,mode in [('A1',0),('B1',1),('B2',1),('A2',0)]:
        os.environ['DS4_EG_DIRECT']=str(mode)
        current=copy.deepcopy(cfg);current['log']=str(RUN/(tag+'-engine.log'))
        r['config']=current;M.write(RUN/'config.json',current)
        arm={'tag':tag,'direct':mode,'rows':[],'started':M.stamp()}
        r['arms'].append(arm);r['phase']='loading-'+tag;M.save()
        M.start_server(tag)
        log=Path(current['log']).read_text(encoding='utf-8')
        arm['unmapped_engram_logged']='its Engram rows read unbuffered' in log
        assert arm['unmapped_engram_logged']==bool(mode),'Direct switch path not confirmed'
        gpu=re.findall(r'experts [\d.]+ GB \((\d+) of 15360 in VRAM\)',log)
        store=re.findall(r'RAM store: up to (\d+) slots',log)
        arm['placement']={'gpu_experts':int(gpu[-1]),'ram_slots':int(store[-1])}
        if placement is None:placement=arm['placement']
        assert arm['placement']==placement,'Placement changed: no equivalent comparison'
        arm['warmup']=M.ask(tag+'-warmup',M.user('Reply with exactly READY.'),16)
        assert arm['warmup']['content'].strip()=='READY'
        arm['idle_commit']=M.commit_status();M.save()
        r['phase']='requests-'+tag;M.save()
        for task in tasks:
            row=M.ask(tag+'-'+str(task['target_tokens']),task['messages'],64)
            row['target_tokens']=task['target_tokens']
            row['fresh']=row['timings']['cache_n']==0
            identity=(row['content'],row['reasoning'],row['usage']['completion_tokens'],row['finish'])
            key=task['target_tokens']
            if key not in expected:expected[key]=identity
            row['matches_A1']=identity==expected[key]
            arm['rows'].append(row);M.save()
            assert row['fresh'] and row['matches_A1'],'Output/freshness gate failed'
        arm['finished']=M.stamp();M.save()
        arm['unload']=M.api('/unload?wait=30',{},timeout=600)
        M.stop_server();M.save();time.sleep(2)
    r['passed']=True;r['phase']='complete';M.save()
except BaseException as exc:
    r['error']=repr(exc);r['phase']='failed';M.save();raise
finally:
    stop.set();M.stop_server()
    for h in M.handles:h.close()
    errors=[]
    if unloaded and r['health_before'].get('loaded'):
        try:
            r['daily_restore']=M.api('/load',{},base=M.DAILY,timeout=900)
            r['health_after']=M.api('/health',base=M.DAILY)
            assert r['health_after']['loaded']
        except BaseException as exc:errors.append(repr(exc))
    r['daily_config_sha256_after']=M.digest(M.ROOT/'strata-iq3_s.json')
    if r['daily_config_sha256_before']!=r['daily_config_sha256_after']:errors.append('Daily config changed')
    r['restore_errors']=errors
    if errors:r['passed']=False
    r['finished']=M.stamp();M.save()
