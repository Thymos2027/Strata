"""Build a tiny CUDA probe, then request one real hardware metric without a model switch."""
import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

OUT = Path(__file__).resolve().parent


def build(destination=OUT):
    python_root = Path(sys.executable).parent
    os.environ['PATH'] = os.pathsep.join([str(python_root/'Scripts'),str(python_root/'Library/bin'),
                                        os.environ.get('PATH','')])
    spec = importlib.util.spec_from_file_location('native_build',OUT.parent/'windows-native-baseline/build_native.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    env,_,_ = helper.compiler_environment()
    exe = destination/'counter_probe.exe'
    command = [str(helper.CUDA/'bin/nvcc.exe'),'-O2','-arch=sm_120','--cudart=static',
               str(OUT/'counter_probe.cu'),'-o',str(exe)]
    with (destination/'probe-build.log').open('w') as log:
        subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,cwd=destination)
    subprocess.run([str(exe)],env=env,check=True)
    return exe,env


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-only',action='store_true')
    parser.add_argument('--tag',default='counter-probe')
    parser.add_argument('--output-dir',type=Path,default=OUT)
    args = parser.parse_args()
    if not args.tag.replace('-','').isalnum():
        parser.error('--tag must contain only letters, numbers and hyphens')
    destination = args.output_dir.resolve()
    destination.mkdir(parents=True,exist_ok=True)
    output = destination/args.tag
    if not args.build_only and any(destination.glob(args.tag+'.*')):
        parser.error('Evidence exists; use a new --tag instead of overwriting')
    elevated = bool(ctypes.windll.shell32.IsUserAnAdmin())
    print('Probe process administrator: '+str(elevated),flush=True)
    exe,env = build(destination)
    if args.build_only:
        return
    installed = json.loads((OUT/'compute-installed.json').read_text())
    snapshot = destination/(args.tag+'.exe')
    shutil.copy2(exe,snapshot)
    command = [installed['command'],'--target-processes','all','--kernel-name','counter_probe',
               '--launch-count','1','--metrics','sm__cycles_elapsed.avg','--clock-control','none',
               '--cache-control','none','--export',str(output),str(snapshot)]
    env['CUDA_VISIBLE_DEVICES'] = '0'
    with (destination/(args.tag+'.console.log')).open('w') as log:
        result = subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=120)
    log = (destination/(args.tag+'.console.log')).read_text(errors='replace')
    status = {'tag':args.tag,'timestamp_utc':datetime.now(timezone.utc).isoformat(),
              'process_is_admin':elevated,'python_executable':sys.executable,
              'tool_version':installed['version'], 'tool_archive_sha256':installed['sha256'],
              'probe_exe_sha256':hashlib.sha256(snapshot.read_bytes()).hexdigest(),
              'command':command,'exit_code':result.returncode,
              'permission_denied':'ERR_NVGPUCTRPERM' in log,
              'report_exists':output.with_suffix('.ncu-rep').exists(),
              'log':log, 'clock_control':'none','cache_control':'none'}
    (destination/(args.tag+'.status.json')).write_text(json.dumps(status,indent=2))
    (destination/'counter-status.json').write_text(json.dumps(status,indent=2))
    print(json.dumps(status,indent=2))
    if result.returncode or status['permission_denied'] or not status['report_exists']:
        raise SystemExit('Hardware-counter preflight did not pass; daily model was not unloaded')


if __name__ == '__main__':
    main()
