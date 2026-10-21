import json, time, threading, subprocess, urllib.request
from pathlib import Path

out = Path(__file__).parent
def get(path):
    with urllib.request.urlopen('http://127.0.0.1:8080'+path, timeout=120) as r:
        return json.load(r)
def resources():
    command = "$os=Get-CimInstance Win32_OperatingSystem; $cpu=Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter \"Name='_Total'\"; $procs=Get-Process python*,strata* -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,WorkingSet64,PrivateMemorySize64,CPU; [pscustomobject]@{total_ram_kib=$os.TotalVisibleMemorySize;free_ram_kib=$os.FreePhysicalMemory;total_commit_limit_kib=$os.TotalVirtualMemorySize;free_commit_kib=$os.FreeVirtualMemory;cpu_percent=$cpu.PercentProcessorTime;processes=@($procs)} | ConvertTo-Json -Depth 4 -Compress"
    p = subprocess.run(['powershell','-NoProfile','-Command',command], capture_output=True, text=True, check=True)
    return json.loads(p.stdout)

result={'health':get('/health'),'status':get('/v1/status'),'idle':resources(),'gpu_samples':[]}
done=threading.Event()
def sample():
    while not done.is_set():
        p=subprocess.run(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu,power.draw,temperature.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True)
        result['gpu_samples'].append({'elapsed_s':round(time.monotonic()-start,2),'csv':p.stdout.strip()})
        done.wait(0.8)
def sample_host():
    done.wait(2)
    if not done.is_set():result['during_generation']=resources()
payload={'model':'qwen3.8-flash-next-iq3_s','messages':[{'role':'user','content':'请用中文解释 CPU、GPU、内存和 SSD 如何协作运行混合专家大模型，并说明日常使用应如何观察资源占用。'}],'temperature':0,'max_tokens':512,'stream':False}
start=time.monotonic()
t=threading.Thread(target=sample);h=threading.Thread(target=sample_host)
t.start();h.start()
try:
    req=urllib.request.Request('http://127.0.0.1:8080/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=180) as r:result['response']=json.load(r)
    result['elapsed_s']=time.monotonic()-start
finally:
    done.set();t.join();h.join()
result['after']=resources()
(out/'final-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
