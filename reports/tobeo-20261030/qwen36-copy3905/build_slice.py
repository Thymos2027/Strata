"""Build only the original author's copy slice on the pinned baseline."""
import json, os, re, shutil, subprocess, sys, time
from pathlib import Path

OUT=Path(__file__).resolve().parent
REPO=OUT.parents[2]
BASE=REPO/'reports/tobeo-20261029/qwen36-repro-baseline'
sys.path.insert(0,str(BASE))
from build_baseline import ROOT,REVISION,BUILD as BASE_BUILD,SOURCE as BASE_SOURCE,CUDA,MODEL,MODEL_SHA,digest,save,stamp,helper,git
SOURCE=ROOT/'src-copy3905-af08278c'
BUILD=ROOT/'build-copy3905-af08278c-cuda132-sm120'
SLICE='af08278c15e857345dad95805dda7256a559dcfa'


def compiler():
    home=Path(sys.executable).parent
    os.environ['PATH']=os.pathsep.join([str(home/'Scripts'),str(home/'Library/bin'),os.environ['PATH']])
    return helper('reports/tobeo-20261022/windows-native-baseline/build_native.py','native_compiler').compiler_environment()


def main():
    destination=OUT/'build-results.json'
    if destination.exists() or SOURCE.exists() or BUILD.exists():raise RuntimeError('Do not overwrite existing build evidence')
    record={'started':stamp(),'passed':False,'baseline':REVISION,'slice_commit':SLICE,
            'source':str(SOURCE),'build':str(BUILD),'author':'xyehya','commands':[],
            'script_sha256':digest(__file__),'plan_sha256':digest(OUT/'experiment-plan.md')}
    persist=lambda:save(destination,record)
    persist()
    try:
        baseline=json.loads((BASE/'build-results.json').read_text(encoding='utf-8'))
        assert baseline['passed']
        record['baseline_binaries_before']={name:digest(BASE_BUILD/name) for name in baseline['binaries']}
        assert record['baseline_binaries_before']==baseline['binaries']
        assert git('diff','--name-only',REVISION,'upstream/main','--','src/qwen35','tools/qwen35')==''
        record['upstream_at_prepare']=git('rev-parse','upstream/main')
        subprocess.run(['git','worktree','add','--detach',str(SOURCE),REVISION],check=True)
        snapshot=json.loads((OUT/'upstream-snapshot.json').read_text(encoding='utf-8'))
        patch=next(f['patch'] for f in snapshot['commit']['files'] if f['filename']=='src/qwen35/q36_engine.cu')
        hunks=re.split(r'(?=^@@ )',patch,flags=re.M)
        hunks=[h for h in hunks if h.startswith('@@ ')][:4]
        assert len(hunks)==4
        first='diff --git a/src/qwen35/q36_engine.cu b/src/qwen35/q36_engine.cu\n--- a/src/qwen35/q36_engine.cu\n+++ b/src/qwen35/q36_engine.cu\n'+''.join(h if h.endswith('\n') else h+'\n' for h in hunks)
        (OUT/'author-copy-hunks.patch').write_text(first,encoding='utf-8')
        subprocess.run(['git','-C',str(SOURCE),'apply','--check',str(OUT/'author-copy-hunks.patch')],check=True)
        subprocess.run(['git','-C',str(SOURCE),'apply',str(OUT/'author-copy-hunks.patch')],check=True)
        path=SOURCE/'src/qwen35/q36_engine.cu'
        text=path.read_text(encoding='utf-8')
        replacements=[
            ('bool serve_mode = false, graph = true, vision = false, batch_mtp = false;',
             'bool serve_mode = false, graph = true, vision = false, batch_mtp = false, split_stage_copy = false;'),
            ('else if (a == "--no-graph") graph = false;',
             'else if (a == "--no-graph") graph = false;\n        else if (a == "--split-stage-copy") split_stage_copy = true;'),
            ('    Engine E;','    Engine E;\n    E.split_copy = split_stage_copy;'),
            ('[--chunk 512] [--no-graph]','[--chunk 512] [--no-graph] [--split-stage-copy]')]
        for old,new in replacements:
            assert text.count(old)==1,old
            text=text.replace(old,new)
        path.write_text(text,encoding='utf-8')
        changes=git('diff','--name-only',cwd=SOURCE)
        assert changes=='src/qwen35/q36_engine.cu'
        diff=subprocess.check_output(['git','-C',str(SOURCE),'diff','--','src/qwen35/q36_engine.cu'])
        (OUT/'candidate.patch').write_bytes(diff)
        record.update(candidate_patch_sha256=digest(OUT/'candidate.patch'),engine_file_sha256=digest(path),
                      original_hunks_sha256=digest(OUT/'author-copy-hunks.patch'))
        record['model']={'bytes':MODEL.stat().st_size,'sha256':digest(MODEL)}
        assert record['model']['sha256']==MODEL_SHA
        env,cmake,vs=compiler()
        env={k:v for k,v in env.items() if not k.startswith(('STRATA_','DS4_'))}
        commands=[]
        for old in baseline['commands']:
            commands.append([part.replace(str(BASE_SOURCE),str(SOURCE)).replace(BASE_SOURCE.as_posix(),SOURCE.as_posix()).replace(str(BASE_BUILD),str(BUILD)).replace(BASE_BUILD.as_posix(),BUILD.as_posix()) for part in old['command']])
        for i,command in enumerate(commands):
            print('BUILD',i,flush=True)
            start=time.monotonic()
            with (OUT/f'build-{i}.log').open('w',encoding='utf-8') as log:
                result=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT)
            record['commands'].append({'command':command,'exit_code':result.returncode,'seconds':time.monotonic()-start})
            persist()
            if result.returncode:raise RuntimeError('Build/check failed '+str(i))
        record['binaries']={name:digest(BUILD/name) for name in baseline['binaries']}
        record['baseline_binaries_after']={name:digest(BASE_BUILD/name) for name in baseline['binaries']}
        assert record['baseline_binaries_after']==record['baseline_binaries_before']
        assert digest(path)==record['engine_file_sha256']
        # A file-argv adapter is linked against each set of existing, unchanged libraries.
        cl=shutil.which('cl.exe',path=env['PATH']);link=shutil.which('link.exe',path=env['PATH'])
        adapter=REPO/'reports/tobeo-20261028/qwen36-pr4347/file_entry.cpp'
        record['adapter_source_sha256']=digest(adapter);record['adapters']={}
        for name,build,src in [('baseline',BASE_BUILD,BASE_SOURCE),('candidate',BUILD,SOURCE)]:
            block=(build/'build.ninja').read_text(encoding='utf-8').split('build strata-q36.exe:',1)[1].split('\n\n',1)[0]
            libraries=re.search(r'^  LINK_LIBRARIES = (.*)$',block,re.M).group(1).split()
            pinned={str((build/Path(x)).resolve()):digest(build/Path(x)) for x in libraries if Path(x).suffix=='.lib' and (build/Path(x)).exists()}
            adapter_dir=OUT/('adapter-'+name);adapter_dir.mkdir(exist_ok=False)
            obj=OUT/(name+'.obj');exe=adapter_dir/'strata-q36-file.exe'
            shutil.copy2(build/'strata_kq.dll',adapter_dir/'strata_kq.dll')
            cmds=[[cl,'/nologo','/c','/O2','/EHsc','/std:c++20','/MD','/I'+str(src/'include'),str(adapter),'/Fo'+str(obj)],
                  [link,'/nologo','/OUT:'+str(exe),'/MACHINE:X64','/INCREMENTAL:NO','/SUBSYSTEM:CONSOLE','/OPT:REF','/OPT:ICF',
                   '/LIBPATH:'+str(CUDA/'lib/x64'),'/MANIFEST:EMBED','/MANIFESTINPUT:'+str(src/'cmake/strata-utf8.manifest'),str(obj),*libraries]]
            with (OUT/(name+'-adapter.log')).open('w',encoding='utf-8') as log:
                for command in cmds:
                    result=subprocess.run(command,cwd=build,env=env,stdout=log,stderr=subprocess.STDOUT)
                    if result.returncode:raise RuntimeError('Adapter link failed '+name)
            assert all(digest(path)==sha for path,sha in pinned.items())
            record['adapters'][name]={'exe':str(exe),'sha256':digest(exe),'libraries':pinned,'commands':cmds,
                                      'dll_sha256':digest(adapter_dir/'strata_kq.dll')}
        record['passed']=True
    except BaseException as exc:record['error']=repr(exc);raise
    finally:record['finished']=stamp();persist()


if __name__=='__main__':main()
