"""Compile bounded copy diagnostic and sample PCIe generation while it is active."""
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OUT=Path(__file__).resolve().parent


def main():
    started=datetime.now(timezone(timedelta(hours=8)))
    root=OUT.parents[1]/('tobeo-'+started.strftime('%Y%m%d'))/'qwen36-profiling'
    number=1
    while (root/f'pcie-diagnostic-{number:02d}').exists():number+=1
    directory=root/f'pcie-diagnostic-{number:02d}'
    directory.mkdir(parents=True)
    if not (root/'.gitignore').exists():
        (root/'.gitignore').write_text('*\n!.gitignore\n!*.md\n!*.py\n!*.cu\n!summary.json\n!environment-summary.json\n')
    python=Path(sys.executable).parent
    os.environ['PATH']=os.pathsep.join([str(python/'Scripts'),str(python/'Library/bin'),os.environ['PATH']])
    helper_path=OUT.parents[1]/'tobeo-20261022/windows-native-baseline/build_native.py'
    spec=importlib.util.spec_from_file_location('build',helper_path);helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    env,_,_=helper.compiler_environment();exe=directory/'pcie_probe.exe'
    command=[str(helper.CUDA/'bin/nvcc.exe'),'-O2','-arch=sm_120','--cudart=static',str(OUT/'pcie_probe.cu'),'-o',str(exe)]
    with (directory/'build.log').open('w') as log:subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    query=['nvidia-smi','--query-gpu=timestamp,pcie.link.gen.gpucurrent,pcie.link.gen.gpumax,pcie.link.gen.hostmax,pcie.link.width.current,pstate,clocks.current.graphics,clocks.current.memory,temperature.gpu,power.draw',
           '--format=csv,noheader,nounits']
    samples=[]
    started=started.isoformat()
    with (directory/'probe.log').open('w') as log:
        process=subprocess.Popen([str(exe)],env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            deadline=time.monotonic()+90
            while process.poll() is None:
                if time.monotonic()>deadline:raise TimeoutError('Copy diagnostic exceeded 90 seconds')
                row=subprocess.run(query,capture_output=True,text=True,timeout=10)
                samples.append({'csv':row.stdout.strip(),'exit_code':row.returncode})
                time.sleep(.5)
        finally:
            if process.poll() is None:process.kill();process.wait(timeout=30)
    text=(directory/'probe.log').read_text();print(text)
    result={'started_at':started,'command':[str(exe)],'exe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),
            'exit_code':process.returncode,'link_samples':samples,'probe_output':text,
            'system_settings_changed':False,'scope':'One bounded pinned HtoD diagnostic, no model unload or clock/link setting changes'}
    (directory/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(samples[-4:],indent=2))
    if process.returncode:raise RuntimeError('Copy diagnostic failed')


if __name__=='__main__':main()
