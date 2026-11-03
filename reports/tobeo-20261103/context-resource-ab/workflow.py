"""ABBA restart comparison using the same server/environment, restore 262K."""
import importlib.util
import json
import os
from pathlib import Path
import statistics
import subprocess
import threading
import time
import traceback
import urllib.request

import psutil

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
CFG = ROOT / 'strata-iq3_s.json'
spec = importlib.util.spec_from_file_location('helpers', OUT.parent / 'flashnext-262k/workflow.py')
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
h.OUT = OUT
h.STATE['validation_scope'] = 'ABBA restart resource comparison: unloaded, loaded idle, identical short request; restore 262K'
urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))
CHECK = '完成64K与262K上下文重启资源ABBA对照并恢复262K服务'
original = CFG.read_bytes()
results = []
stopped = False

def snapshot(port=None):
    vm = psutil.virtual_memory()
    import ctypes
    class Mem(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [(x, ctypes.c_ulonglong) for x in ('total_phys','avail_phys','total_commit','avail_commit','total_virtual','avail_virtual','avail_ext')]
    mm = Mem(); mm.length = ctypes.sizeof(Mem)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mm)):
        raise RuntimeError('Windows memory counters unavailable')
    row = {'time': h.stamp(), 'ram_used': vm.total-vm.available, 'ram_available': vm.available,
           'commit_used': mm.total_commit-mm.avail_commit, 'commit_limit': mm.total_commit,
           'cpu_percent': psutil.cpu_percent(interval=None)}
    smi = subprocess.run(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu,power.draw','--format=csv,noheader,nounits'],
                         capture_output=True,text=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
    smi.check_returncode()
    gpu = [float(x.strip()) for x in smi.stdout.strip().splitlines()[0].split(',')]
    row.update(gpu_used=gpu[0]*2**20, gpu_total=gpu[1]*2**20, gpu_util=gpu[2], gpu_power_w=gpu[3])
    if port:
        m=h.api(port,'/metrics',timeout=15)
        if m['live']['state'] != 'idle' or m['live'].get('queued'):
            raise RuntimeError('Unexpected request during idle sampling')
        row['metrics']=m
        parent=psutil.Process(h.ACTIVE.pid)
        row['processes']=[{'pid':p.pid,'name':p.name(),'memory':p.memory_info()._asdict()} for p in [parent]+parent.children(recursive=True)]
        engine=[p for p in row['processes'] if p['name'].lower()=='strata.exe']
        if len(engine)!=1: raise RuntimeError('Expected exactly one test engine')
        row['engine_rss']=engine[0]['memory']['rss']
        row['engine_private']=engine[0]['memory'].get('private')
    return row

def phase(label, port=None):
    h.stage(label)
    time.sleep(10)
    rows=[]
    for _ in range(5):
        if h.GUARD_ERROR: raise RuntimeError(h.GUARD_ERROR)
        rows.append(snapshot(port))
        time.sleep(2)
    out={'samples':rows,'median':{k:statistics.median(r[k] for r in rows) for k in ('ram_used','ram_available','commit_used','gpu_used','cpu_percent','gpu_util','gpu_power_w')},'gpu_process_counters':None}
    if port:
        for k in ('engine_rss','engine_private'):
            out['median'][k]=statistics.median(r[k] for r in rows)
        pid=[p['pid'] for p in rows[-1]['processes'] if p['name'].lower()=='strata.exe'][0]
        script=f"Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUProcessMemory | Where-Object {{$_.Name -match '^pid_{pid}_'}} | Select-Object Name,DedicatedUsage,SharedUsage,TotalCommitted | ConvertTo-Json -Compress"
        proc=subprocess.run(['powershell','-NoProfile','-Command',script],capture_output=True,text=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
        out['gpu_process_counter_exit']=proc.returncode
        out['gpu_process_counters']=proc.stdout.strip()
        out['gpu_process_counter_stderr']=proc.stderr.strip()
    h.save(label+'.json',out)
    return out

def short(port,name):
    text,_,_=h.complete(port,[{'role':'user','content':'Reply with exactly READY.'}],name,32)
    if text.strip()!='READY': raise RuntimeError('Short request gate failed: '+repr(text))

def main():
    global stopped
    m=h.api(8080,'/metrics')
    h.save('original.metrics.json',m)
    if m['live']['state']!='idle' or m['live'].get('queued'):
        raise RuntimeError('Current service busy; leaving it unchanged')
    if m['engine']['max_context']!=262144:
        raise RuntimeError('Expected existing 262K service')
    owners={c.pid for c in psutil.net_connections(kind='tcp') if c.status=='LISTEN' and c.laddr.port==8080}
    if len(owners)!=1: raise RuntimeError('Unexpected listener ownership')
    owner=psutil.Process(owners.pop())
    if 'serve.server' not in owner.cmdline() or str(CFG) not in owner.cmdline():
        raise RuntimeError('Server identity mismatch')
    if any(c.status=='LISTEN' and c.laddr.port==18080 for c in psutil.net_connections(kind='tcp')):
        raise RuntimeError('Test port occupied')
    h.save('config-original.json',json.loads(original))
    h.stage('stopping_original_262k',original_server_pid=owner.pid)
    stopped=True
    h.kill_tree(owner.pid)
    threading.Thread(target=h.memory_guard,daemon=True).start()
    failure=None
    try:
        for index,context in enumerate((65536,262144,262144,65536),1):
            label=f'round-{index}-{context}'
            baseline=phase(label+'-unloaded')
            cfg=json.loads(original)
            cfg['exe']=str(h.EXE)
            cfg['args'][cfg['args'].index('--max-context')+1]=str(context)
            cfg['port']=18080
            cfg['log']=str(OUT/(label+'-engine.log'))
            h.save(label+'-config.json',cfg)
            _,health=h.launch(OUT/(label+'-config.json'),18080,label)
            if health['max_context']!=context: raise RuntimeError('Effective context mismatch')
            idle=phase(label+'-loaded-idle',18080)
            short(18080,label+'-short')
            warm=phase(label+'-after-short',18080)
            result={'round':index,'context':context,'baseline':baseline['median'],'loaded_idle':idle['median'],'after_short':warm['median'],
                    'engine_info':warm['samples'][-1]['metrics']['engine']}
            result['delta_loaded']={k:idle['median'][k]-baseline['median'][k] for k in ('ram_used','commit_used','gpu_used')}
            result['delta_after_short']={k:warm['median'][k]-baseline['median'][k] for k in ('ram_used','commit_used','gpu_used')}
            results.append(result);h.save('round-results.json',results)
            h.kill_tree(h.ACTIVE.pid);h.ACTIVE=None
        summary={'rounds':results,'scope':'ABBA, original automatic allocation policies, no allocator-level attribution','context_medians':{}}
        for context in (65536,262144):
            rr=[r for r in results if r['context']==context]
            summary['context_medians'][str(context)]={phase:{k:statistics.median(r[phase][k] for r in rr) for k in rr[0][phase]} for phase in ('baseline','loaded_idle','after_short','delta_loaded','delta_after_short')}
        a,b=(summary['context_medians'][str(c)] for c in (65536,262144))
        summary['262k_minus_64k']={phase:{k:b[phase][k]-a[phase][k] for k in a[phase]} for phase in a}
        h.save('summary.json',summary)
    except Exception:
        failure=traceback.format_exc()
        h.stage('comparison_failed_restoring',error=failure)
    finally:
        h.GUARD_STOP.set()
        if h.ACTIVE:
            h.kill_tree(h.ACTIVE.pid);h.ACTIVE=None
        if CFG.read_bytes()!=original:
            raise RuntimeError('Original configuration edited externally; refusing automatic recovery with unknown configuration')
        h.GUARD_ERROR=None
        time.sleep(5)
        _,health=h.launch(CFG,8080,'restored-262k')
        if health['max_context']!=262144: raise RuntimeError('Restored context mismatch')
        short(8080,'restored-smoke')
        h.save('restored.health.json',h.api(8080,'/health'))
        h.stage('comparison_failed_restored_262k' if failure else 'comparison_complete_restored_262k',error=failure,rounds_completed=len(results),restored_server_pid=h.ACTIVE.pid)
        with (OUT/'README.md').open('a',encoding='utf8') as f:
            f.write(f'\n{h.stamp()}：完成{len(results)}轮，已恢复262K并通过短请求验收。状态见status.json；'+('比较失败，原因见状态文件。' if failure else '四轮比较完成，见summary.json；结果尚待人工复核。')+'\n')
    return 1 if failure else 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception:
        h.stage('workflow_error',error=traceback.format_exc(),rounds_completed=len(results))
        raise
