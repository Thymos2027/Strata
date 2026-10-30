"""Build an isolated trace-only revision; preserve original binaries and computation."""
import json,os,re,shutil,subprocess,sys,time
from pathlib import Path
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT.parent/'qwen36-copy3905'))
from build_slice import compiler
from run_validation import host,BASE_BUILD,BASE_SOURCE,ROOT,REVISION,digest,save,stamp
SOURCE=ROOT/'src-job-complete2-46c152a1'
BUILD=ROOT/'build-job-complete-46c152a1-cuda132-sm120'
NVTX=host.NSYS.parent/'nvtx/include'


def main():
    assert not (OUT/'build-complete.json').exists() and not SOURCE.exists() and not BUILD.exists()
    r={'started':stamp(),'passed':False,'revision':REVISION,'commands':[],
       'script_sha256':digest(__file__),'plan_sha256':digest(OUT/'completion-plan.md')}
    persist=lambda:save(OUT/'build-complete.json',r)
    persist()
    try:
        base=host.check_identity();r['baseline_binaries']=base['binaries']
        subprocess.run(['git','worktree','add','--detach',str(SOURCE),REVISION],check=True)
        shutil.copyfile(OUT/'job_trace.hpp',SOURCE/'include/strata/core/job_trace.hpp')
        engine=SOURCE/'src/qwen35/q36_engine.cu';pool=SOURCE/'src/kernels/cpu/pool.cpp'
        e=engine.read_text(encoding='utf-8');p=pool.read_text(encoding='utf-8')
        def replace(text,old,new):
            assert text.count(old)==1,old
            return text.replace(old,new)
        e=replace(e,'#include "strata/core/family_layout.hpp"','#include "strata/core/family_layout.hpp"\n#include "strata/core/job_trace.hpp"')
        e=replace(e,'    void forward(int T, int64_t p0, int heads, bool graph_mode, bool verify) {',
                  '    void forward(int T, int64_t p0, int heads, bool graph_mode, bool verify) {\n        strata_job_trace::Span jt_forward("JT forward id=%llu T=%d pos=%lld", (unsigned long long) strata_job_trace::next_forward(), T, (long long) p0);')
        e=replace(e,'    void moe_hybrid_gpu(const Layer& L, size_t li, int T) {',
                  '    void moe_hybrid_gpu(const Layer& L, size_t li, int T) {\n        strata_job_trace::Span jt_gpu("JT gpu moe=%llu f=%llu li=%zu T=%d", (unsigned long long) strata_job_trace::next_moe(), (unsigned long long) strata_job_trace::forward_id, li, T);')
        e=replace(e,'    void moe_hybrid_cpu(size_t li, int T) {',
                  '    void moe_hybrid_cpu(size_t li, int T) {\n        strata_job_trace::Span jt_cpu("JT cpu moe=%llu f=%llu li=%zu T=%d", (unsigned long long) strata_job_trace::moe_id, (unsigned long long) strata_job_trace::forward_id, li, T);')
        old='        while (cudaEventQuery(ev_route) == cudaErrorNotReady) {\n        }'
        e=replace(e,old,'        { strata_job_trace::Span jt_route("JT route moe=%llu", (unsigned long long) strata_job_trace::moe_id);\n'+old+'\n        }')
        e=replace(e,'        pool->run_split_multi_native(H.fmt, jobs.data(), (int) jobs.size());',
                  '        { strata_job_trace::Span jt_pool("JT pool moe=%llu experts=%zu miss=%d", (unsigned long long) strata_job_trace::moe_id, jobs.size(), n_miss);\n        pool->run_split_multi_native(H.fmt, jobs.data(), (int) jobs.size());\n        }')
        old='            const int32_t one = nx;\n            E.process(&one, 1, [](int64_t) {});\n            ss.live.push_back(nx);\n            fix.clear();\n            if (!smp.needs_logits()) nx = E.greedy();'
        e=replace(e,old,'            { strata_job_trace::Span jt_token("JT token pos=%lld output=%lld", (long long) E.pos, (long long) produced);\n'+old+'\n            }')
        p=replace(p,'#include "strata/core/progress.hpp"','#include "strata/core/progress.hpp"\n#include "strata/core/job_trace.hpp"')
        p=replace(p,'    publish();\n    return e;', '    strata_job_trace::mark("JT publish epoch=%u", e);\n    publish();\n    return e;')
        p=replace(p,'        const uint32_t i = (uint32_t) ci;',
                  '        const uint32_t i = (uint32_t) ci;\n        strata_job_trace::Span jt_job("JT job epoch=%u mode=%d task=%u who=%d", epoch, mode_, i, id);')
        p=replace(p,'        if (sliced) {\n            NodeSync& ns = nsync_[(size_t) s];\n            const uint32_t t',
                  '        jt_job.finish(); // observation ends before the original done release\n        if (sliced) {\n            NodeSync& ns = nsync_[(size_t) s];\n            const uint32_t t')
        p=replace(p,'void ExpertPool::run_phase(int mode, int n_tasks) {\n    wait_parked("before a phase");',
                  'void ExpertPool::run_phase(int mode, int n_tasks) {\n    const uint32_t jt_epoch = epoch_.load(std::memory_order_relaxed) + 1;\n    strata_job_trace::Span jt_phase("JT phase epoch=%u mode=%d tasks=%d rows=%lld per=%lld sliced=%d", jt_epoch, mode, n_tasks, (long long) mrows_, (long long) (mode >= 5 && nfmt_ ? (mode == 5 ? nfmt_->n_ff : nfmt_->n_embd) : 0), numa_n_);\n    { strata_job_trace::Span jt_park("JT park_before epoch=%u", jt_epoch);\n    wait_parked("before a phase");\n    }')
        p=replace(p,'    if (host_works_) drain(-1, host_scratch_, e);\n    wait_done(n_tasks);\n    wait_parked("after a phase");',
                  '    if (host_works_) { strata_job_trace::Span jt_host("JT host_drain epoch=%u", e); drain(-1, host_scratch_, e); }\n    { strata_job_trace::Span jt_wait("JT wait_done epoch=%u", e); wait_done(n_tasks); }\n    { strata_job_trace::Span jt_park("JT park_after epoch=%u", e); wait_parked("after a phase"); }')
        drain_begin=p.index('void ExpertPool::drain('); drain_end=p.index('void ExpertPool::run_phase(',drain_begin)
        prefix,drain,suffix=p[:drain_begin],p[drain_begin:drain_end],p[drain_end:]
        drain=replace(drain,'            done_.fetch_add(1, std::memory_order_release);',
                  '            if (strata_job_trace::enabled()) {\n                const uint32_t jt_ordinal = done_.fetch_add(1, std::memory_order_release) + 1;\n                strata_job_trace::mark("JT done epoch=%u mode=%d task=%u who=%d ordinal=%u", epoch, mode_, i, id, jt_ordinal);\n            } else {\n                done_.fetch_add(1, std::memory_order_release);\n            }')
        p=prefix+drain+suffix
        engine.write_text(e,encoding='utf-8');pool.write_text(p,encoding='utf-8')
        patch=subprocess.check_output(['git','-C',str(SOURCE),'diff','--','src/qwen35/q36_engine.cu','src/kernels/cpu/pool.cpp'])
        (OUT/'diagnostic-complete.patch').write_bytes(patch)
        r['source_hashes']={x:digest(SOURCE/x) for x in ['src/qwen35/q36_engine.cu','src/kernels/cpu/pool.cpp','include/strata/core/job_trace.hpp']}
        r['nvtx_headers']={x.relative_to(NVTX).as_posix():digest(x) for x in NVTX.rglob('*.h')}
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
