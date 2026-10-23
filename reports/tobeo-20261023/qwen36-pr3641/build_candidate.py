"""Build upstream PR #3641 unchanged; this is hardware validation, not our kernel patch."""
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

OUT=Path(__file__).resolve().parent
REPO=OUT.parents[2]
ROOT=REPO/'build-native-baseline'
REVISION='f3f2136f194bdc42d07961bef0ce66b2811f58cb'
SOURCE=ROOT/'src-pr3641-f3f2136f'
BUILD=ROOT/'build-pr3641-f3f2136f-cuda132-sm120'
TOOLS=OUT.parents[1]/'tobeo-20261022/windows-native-baseline/build_native.py'
ZONE=timezone(timedelta(hours=8),'Asia/Shanghai')


def main():
    if (OUT/'build-summary.json').exists():
        raise RuntimeError('Build evidence already exists; inspect before retry')
    revision=subprocess.check_output(['git','-C',str(SOURCE),'rev-parse','HEAD'],text=True).strip()
    changes=subprocess.check_output(['git','-C',str(SOURCE),'status','--porcelain','--untracked-files=no'],text=True)
    if revision!=REVISION or changes:
        raise RuntimeError('Expected unchanged upstream PR worktree')
    python=Path(sys.executable).parent
    os.environ['PATH']=os.pathsep.join([str(python/'Scripts'),str(python/'Library/bin'),os.environ['PATH']])
    spec=importlib.util.spec_from_file_location('native_build',TOOLS)
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    env,cmake,vs=helper.compiler_environment()
    cl=shutil.which('cl.exe',path=env['PATH'])
    if not cl:raise RuntimeError('MSVC missing')
    commands=[
        [cmake,'-S',str(SOURCE),'-B',str(BUILD),'-G','Ninja','-DCMAKE_BUILD_TYPE=Release',
         '-DSTRATA_ENABLE_CUDA=ON','-DCMAKE_CUDA_ARCHITECTURES=120',
         '-DCUDAToolkit_ROOT='+helper.CUDA.as_posix(),'-DCMAKE_CUDA_COMPILER='+(helper.CUDA/'bin/nvcc.exe').as_posix(),
         '-DCMAKE_C_COMPILER='+Path(cl).as_posix(),'-DCMAKE_CXX_COMPILER='+Path(cl).as_posix(),
         '-DCMAKE_CUDA_HOST_COMPILER='+Path(cl).as_posix(),
         '-DSTRATA_GGML_DIR='+(helper.SOURCE/'third_party/llama.cpp').as_posix(),
         '-DSTRATA_BUILD_TESTS=ON','-DCMAKE_EXPORT_COMPILE_COMMANDS=ON'],
        [cmake,'--build',str(BUILD),'--target','strata-q36','strata_kq','q36_attn_parity','q36_f16_parity','model_family_test','--parallel','8']]
    record={'upstream_pr':3641,'revision':REVISION,'source_unchanged':True,'source':str(SOURCE),
            'build':str(BUILD),'cuda':str(helper.CUDA),'ggml_revision':helper.GGML_REVISION,
            'started_at':datetime.now(ZONE).isoformat(),'commands':[],'passed':False}
    try:
        with (OUT/'build.log').open('w',encoding='utf-8') as log:
            for command in commands:
                print('RUN '+subprocess.list2cmdline(command),flush=True)
                start=time.monotonic()
                code=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT).returncode
                log.flush()
                record['commands'].append({'command':command,'exit_code':code,'wall_s':time.monotonic()-start})
                if code:raise RuntimeError('Build failed; inspect build.log')
        record['passed']=True
        record['exe_sha256']=hashlib.sha256((BUILD/'strata-q36.exe').read_bytes()).hexdigest()
        record['post_build_source_changes']=subprocess.check_output(
            ['git','-C',str(SOURCE),'status','--porcelain','--untracked-files=no'],text=True)
        if record['post_build_source_changes']:
            record['passed']=False
            raise RuntimeError('Build modified tracked upstream sources; inspect before validation')
    finally:
        record['finished_at']=datetime.now(ZONE).isoformat()
        (OUT/'build-summary.json').write_text(json.dumps(record,indent=2))


if __name__=='__main__':main()
