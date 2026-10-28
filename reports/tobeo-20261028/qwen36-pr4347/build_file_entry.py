"""Link a file-argv adapter against existing engine libraries; never rebuild kernels."""
import hashlib,importlib.util,json,os,re,shutil,subprocess,sys
from pathlib import Path
from build_pair import ARMS,OUT,REPO,ROOT,digest,stamp
DIR=OUT/'validation-next';DIR.mkdir(exist_ok=True)
if (DIR/'adapter-build.json').exists():
    if json.loads((DIR/'adapter-build.json').read_text())['passed']:raise RuntimeError('Adapter already built')
    index=1
    while (DIR/f'adapter-build-attempt-{index}.json').exists():index+=1
    (DIR/'adapter-build.json').rename(DIR/f'adapter-build-attempt-{index}.json')
    for name in ARMS:
        path=DIR/(name+'.build.log')
        if path.exists():path.rename(DIR/f'{name}.build-attempt-{index}.log')
spec=importlib.util.spec_from_file_location('native_tools',REPO/'reports/tobeo-20261022/windows-native-baseline/build_native.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
python=Path(sys.executable).parent
os.environ['PATH']=os.pathsep.join([str(python/'Scripts'),str(python/'Library/bin'),os.environ['PATH']])
env,cmake,vs=helper.compiler_environment();cl=shutil.which('cl.exe',path=env['PATH']);link=shutil.which('link.exe',path=env['PATH'])
report={'started':stamp(),'engine_sources_modified':False,'arms':{},'passed':False}
try:
    for name,arm in ARMS.items():
        build,src=arm['build'],arm['source']
        text=(build/'build.ninja').read_text(encoding='utf-8')
        block=text.split('build strata-q36.exe:',1)[1].split('\n\n',1)[0]
        libraries=re.search(r'^  LINK_LIBRARIES = (.*)$',block,re.M).group(1).split()
        obj=DIR/(name+'.obj');exe=build/'strata-q36-file.exe'
        original=digest(build/'strata-q36.exe')
        pinned={str((build/Path(x)).resolve()):digest(build/Path(x)) for x in libraries if Path(x).suffix=='.lib' and (build/Path(x)).exists()}
        commands=[
            [cl,'/nologo','/c','/O2','/EHsc','/std:c++20','/MD','/I'+str(src/'include'),str(OUT/'file_entry.cpp'),'/Fo'+str(obj)],
            [link,'/nologo','/OUT:'+str(exe),'/MACHINE:X64','/INCREMENTAL:NO','/SUBSYSTEM:CONSOLE',
             '/OPT:REF','/OPT:ICF','/LIBPATH:'+str(helper.CUDA/'lib/x64'),
             '/MANIFEST:EMBED','/MANIFESTINPUT:'+str(src/'cmake/strata-utf8.manifest'),str(obj),*libraries]
        ]
        with (DIR/(name+'.build.log')).open('w',encoding='utf-8') as log:
            for command in commands:
                run=subprocess.run(command,cwd=build,env=env,stdout=log,stderr=subprocess.STDOUT)
                if run.returncode:raise RuntimeError('Adapter build failed: '+name)
        assert digest(build/'strata-q36.exe')==original
        assert all(digest(path)==sha for path,sha in pinned.items())
        report['arms'][name]={'exe':str(exe),'sha256':digest(exe),'original_exe_unchanged':True,'libraries':pinned}
    report['passed']=True
except BaseException as exc:report['error']=repr(exc);raise
finally:
    report['finished']=stamp();(DIR/'adapter-build.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
