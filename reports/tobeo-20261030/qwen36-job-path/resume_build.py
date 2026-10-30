"""Resume the prepared, hash-checked v2 source after pre-compilation path repair."""
from build_complete import *


def main():
    r=json.loads((OUT/'build-complete-prep-02.json').read_text(encoding='utf-8'))
    assert r['passed'] is False and r['commands']==[] and r['error'].startswith('FileNotFoundError')
    assert not BUILD.exists() and not (OUT/'build-complete.json').exists()
    assert all(digest(SOURCE/k)==v for k,v in r['source_hashes'].items())
    r['preparation_script_sha256']=r['script_sha256']
    r['previous_preparation_failure']='build-complete-prep-02.json'
    r['script_sha256']=digest(__file__);r['started']=stamp();r.pop('error');r.pop('finished')
    persist=lambda:save(OUT/'build-complete.json',r)
    persist()
    try:
        env,_,_=compiler();env={k:v for k,v in env.items() if not k.startswith(('STRATA_','DS4_'))}
        baseline=json.loads((host.BASE/'build-results.json').read_text(encoding='utf-8'))
        for i,item in enumerate(baseline['commands']):
            command=[x.replace(str(BASE_SOURCE),str(SOURCE)).replace(BASE_SOURCE.as_posix(),SOURCE.as_posix()).replace(str(BASE_BUILD),str(BUILD)).replace(BASE_BUILD.as_posix(),BUILD.as_posix()) for x in item['command']]
            if i==0:command += ['-DCMAKE_CXX_FLAGS=/I'+NVTX.as_posix(),'-DCMAKE_CUDA_FLAGS=-I'+NVTX.as_posix()]
            print('BUILD',i,flush=True);row={'command':command};r['commands'].append(row);persist();start=time.monotonic()
            with (OUT/f'build-complete-{i}.log').open('w',encoding='utf-8') as f:
                result=subprocess.run(command,env=env,stdout=f,stderr=subprocess.STDOUT)
            row.update(exit_code=result.returncode,seconds=time.monotonic()-start);persist();assert result.returncode==0
        r['binaries']={x:digest(BUILD/x) for x in ['strata-q36.exe','strata_kq.dll','strata-q36.pdb']}
        # Same file-argument adapter as earlier, with the matching DLL next to it.
        adapter=host.REPO/'reports/tobeo-20261028/qwen36-pr4347/file_entry.cpp'
        block=(BUILD/'build.ninja').read_text(encoding='utf-8').split('build strata-q36.exe:',1)[1].split('\n\n',1)[0]
        libraries=re.search(r'^  LINK_LIBRARIES = (.*)$',block,re.M).group(1).split()
        directory=OUT/'adapter-complete';directory.mkdir();shutil.copy2(BUILD/'strata_kq.dll',directory/'strata_kq.dll')
        cl=shutil.which('cl.exe',path=env['PATH']);link=shutil.which('link.exe',path=env['PATH'])
        cmds=[[cl,'/nologo','/c','/O2','/EHsc','/std:c++20','/MD','/I'+str(SOURCE/'include'),str(adapter),'/Fo'+str(OUT/'adapter-complete.obj')],
              [link,'/nologo','/OUT:'+str(directory/'strata-q36-file.exe'),'/MACHINE:X64','/INCREMENTAL:NO','/SUBSYSTEM:CONSOLE','/OPT:REF','/OPT:ICF',
               '/LIBPATH:'+str(host.CUDA/'lib/x64'),'/MANIFEST:EMBED','/MANIFESTINPUT:'+str(SOURCE/'cmake/strata-utf8.manifest'),str(OUT/'adapter-complete.obj'),*libraries]]
        with (OUT/'adapter-complete.log').open('w',encoding='utf-8') as f:
            for command in cmds:subprocess.run(command,cwd=BUILD,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
        r['adapter']={'exe':str(directory/'strata-q36-file.exe'),'sha256':digest(directory/'strata-q36-file.exe'),'commands':cmds}
        # Native CPU-only header/injection smoke probe, no model.
        probe=OUT/'probe-complete.cpp';probe.write_text('#include "strata/core/job_trace.hpp"\nint main(){strata_job_trace::Span s("JT probe");strata_job_trace::mark("JT probe_mark");return 0;}\n',encoding='utf-8')
        with (OUT/'probe-complete-build.log').open('w',encoding='utf-8') as f:
            subprocess.run([cl,'/nologo','/O2','/EHsc','/std:c++20','/I'+str(SOURCE/'include'),'/I'+str(NVTX),str(probe),'/Fe'+str(OUT/'probe-complete.exe'),'/Fo'+str(OUT/'probe-complete.obj')],env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
        host.check_identity();r['passed']=True
    except BaseException as exc:r['error']=repr(exc);raise
    finally:r['finished']=stamp();persist();print(json.dumps({k:r.get(k) for k in ['passed','error','finished']}),flush=True)


if __name__=='__main__':main()
