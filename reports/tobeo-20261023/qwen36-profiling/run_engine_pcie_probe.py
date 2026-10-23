"""Reproduce the frozen engine's exact 256-MiB, four-burst PCIe probe without loading weights."""
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

SCRIPT=Path(__file__).resolve().parent


def main():
    zone=timezone(timedelta(hours=8));started=datetime.now(zone)
    root=SCRIPT.parents[1]/('tobeo-'+started.strftime('%Y%m%d'))/'qwen36-profiling'
    number=1
    while (root/f'pcie-engine-probe-{number:02d}').exists():number+=1
    directory=root/f'pcie-engine-probe-{number:02d}';directory.mkdir(parents=True)
    python=Path(sys.executable).parent
    os.environ['PATH']=os.pathsep.join([str(python/'Scripts'),str(python/'Library/bin'),os.environ['PATH']])
    spec=importlib.util.spec_from_file_location('native_build',SCRIPT.parents[1]/'tobeo-20261022/windows-native-baseline/build_native.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    env,_,_=helper.compiler_environment()
    original=(helper.SOURCE/'src/program/generate.cpp').read_text(encoding='utf-8-sig')
    start=original.index('double probe_pcie_h2d_gbps(');end=original.index('    return bw;\n}',start)+len('    return bw;\n}')
    function=original[start:end]
    prefix='#include <cuda_runtime.h>\n#include <string>\n#include <cstdio>\n#include <cstring>\n#include <chrono>\n#include <algorithm>\nusing Clock=std::chrono::steady_clock;\nstatic double g_last_h2d_gbps=0;\n'
    suffix='\nint main(){std::string s;double v=probe_pcie_h2d_gbps(&s);std::printf("best_GBps=%.9f bursts=%s\\n",v,s.c_str());return v>0?0:1;}\n'
    source=directory/'engine_probe.cu';source.write_text(prefix+function+suffix,encoding='utf-8')
    exe=directory/'engine_probe.exe'
    with (directory/'build.log').open('w') as log:
        subprocess.run([str(helper.CUDA/'bin/nvcc.exe'),'-O2','-arch=sm_120','--cudart=static',str(source),'-o',str(exe)],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    sys.path.insert(0,str(SCRIPT.parents[1]/'tobeo-20261022/qwen36-context-curve'));import run_curve as baseline
    state={'health_before':baseline.request('/health')};unloaded=False
    record={'started_at':started.isoformat(),'source_revision':helper.REVISION,
            'extracted_function_sha256':hashlib.sha256(function.encode()).hexdigest(),
            'exe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'method':'Unchanged frozen engine function: 256 MiB, warm-up, four event-timed bursts, best value'}
    try:
        state['unload']=baseline.request('/unload?wait=30',post=True)
        if state['unload'].get('status') not in ('unloaded','not loaded'):raise RuntimeError('Unload failed')
        unloaded=True
        result=subprocess.run([str(exe)],env=env,capture_output=True,text=True,timeout=60)
        record.update(exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr)
        print(result.stdout,flush=True)
        if result.returncode:raise RuntimeError('Engine PCIe probe failed')
    finally:
        if unloaded and state['health_before'].get('loaded'):
            state['load']=baseline.request('/load',post=True);state['health_after']=baseline.request('/health')
        record['finished_at']=datetime.now(zone).isoformat()
        (directory/'result.json').write_text(json.dumps(record,indent=2));(directory/'service-transition.json').write_text(json.dumps(state,indent=2))


if __name__=='__main__':main()
