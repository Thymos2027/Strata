"""Export existing evidence for the authorized comment; no GPU run or publishing."""
import hashlib,json,re,shutil
from pathlib import Path

OUT=Path(__file__).resolve().parent
REPO=OUT.parents[2]
DEST=OUT/'publication-evidence'
PREFIX='bench/results/2026-10-30-qwen36-split-copy-windows'


def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    summary=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
    manifest=json.loads((OUT/'evidence-manifest.json').read_text(encoding='utf-8'))
    assert summary['experiment_complete'] and digest(OUT/'evidence-manifest.json')==summary['manifest_sha256']
    assert all(digest(OUT/name)==value for name,value in manifest.items())
    r=json.loads((OUT/'execution-02/results.json').read_text(encoding='utf-8'))
    b=json.loads((OUT/'build-results.json').read_text(encoding='utf-8'))
    failed=json.loads((OUT/'execution-01/results.json').read_text(encoding='utf-8'))
    trace=json.loads((OUT/'traces-01/results.json').read_text(encoding='utf-8'))
    assert r['passed'] and b['passed'] and trace['passed'] and not failed['passed']
    DEST.mkdir(exist_ok=False)
    roots=[(str(REPO),'<REPO_ROOT>'),
           ('D:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools','<VS_BUILDTOOLS>'),
           ('D:/Program Files/Anaconda','<PYTHON_ENV>'),
           ('D:/Models/Qwen/Qwen3.6-35B-A3B-MTP-GGUF/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf','<MODEL_FILE>')]
    replacements=[]
    for root,label in roots:
        forward=root.replace('\\','/');back=forward.replace('/','\\')
        replacements.extend((variant,label) for variant in [forward,back,back.replace('\\','\\\\')])
    replacements.sort(key=lambda item:len(item[0]),reverse=True)

    def scrub(value):
        if isinstance(value,str):
            for root,label in replacements:value=value.replace(root,label)
            return value
        if isinstance(value,list):return [scrub(x) for x in value]
        if isinstance(value,dict):return {scrub(k):scrub(v) for k,v in value.items()}
        return value

    def put(name,text):
        p=DEST/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(scrub(text).encode('utf-8'))

    def save(name,value):put(name,json.dumps(scrub(value),indent=2,ensure_ascii=False)+'\n')

    save('results.json',{k:r[k] for k in ['started','finished','passed','fixtures','numeric','rows','pairs','signals','bandwidth-before','bandwidth-after']})
    save('trace-summary.json',summary['trace_evidence'])
    save('statistics.json',summary['statistics'])
    save('provenance.json',{'baseline':b['baseline'],'slice_commit':b['slice_commit'],'author':b['author'],
         'model':b['model'],'candidate_binaries':b['binaries'],'baseline_binaries':b['baseline_binaries_before'],
         'patch_sha256':b['candidate_patch_sha256'],'candidate_source_sha256':b['engine_file_sha256'],
         'adapters':{k:{n:v[n] for n in ['sha256','dll_sha256']} for k,v in b['adapters'].items()},
         'local_controller_sha256':r['script_sha256'],'prewritten_plan_sha256':r['plan_sha256'],
         'original_build_script_sha256':b['script_sha256'],'adapter_deployment_fix_script_sha256':b['metadata_fix_script_sha256'],
         'local_raw_manifest_sha256':summary['manifest_sha256'],'local_raw_files':summary['local_evidence_files'],
         'archive_note':'Exported after measurement. Absolute paths replaced with placeholders; original raw files remain local.'})
    save('commands.json',{'note':'Commands actually recorded, with path placeholders; no additional GPU rerun performed.',
         'build':b['commands'],'numeric':[x['command'] for x in r['numeric']],
         'free_generation':[{'tag':x['tag'],'args':x['args']} for x in r['rows']],
         'trace':trace['commands']})
    save('failed-attempt.json',{'phase':failed['phase'],'passed':failed['passed'],'error':failed.get('error'),
         'numeric':failed['numeric'],'formal_rows':failed['rows'],'finished':failed['finished'],
         'reason':'Auxiliary entry had no adjacent strata_kq.dll; native grouped fallback failed baseline output gate. No formal timings used.'})
    for name in ['candidate.patch','pairs.csv']:shutil.copyfile(OUT/name,DEST/name)
    fixtures=REPO/'reports/tobeo-20261022/qwen36-context-curve'
    for case in r['fixtures']:
        for suffix in ['.ids.json','.prompt.txt']:shutil.copyfile(fixtures/(case+suffix),DEST/(case+suffix))
    for path in sorted((OUT/'execution-02').glob('*.log')):put('logs/'+path.name,path.read_text(encoding='utf-8'))
    for path in sorted((OUT/'execution-01').glob('*.log')):put('failed-logs/'+path.name,path.read_text(encoding='utf-8'))
    for name in ['build-2.log','build-3.log']:put('logs/'+name,(OUT/name).read_text(encoding='utf-8'))
    for arm in ['off','on']:put('logs/trace-'+arm+'.engine.log',(OUT/'traces-01'/(arm+'.engine.log')).read_text(encoding='utf-8'))
    for row in r['numeric']:
        path=OUT/'execution-02'/(row['case']+'-'+row['arm']+'.f32')
        assert path.stat().st_size==row['bytes'] and digest(path)==row['sha256']
    draft=(OUT/'upstream-comment-draft.md').read_text(encoding='utf-8')
    report=draft.replace('Local draft only; not posted. This tests the original author\'s existing implementation and proposes no duplicate patch.',
         'Measured 2026-10-30, Asia/Shanghai. Independent evidence for [Strata PR3905](https://github.com/Niko1221/Strata/pull/3905); this tests the original author\'s implementation and proposes no duplicate patch.')
    report=report[:report.index('Local evidence:')]+'''## Evidence and exact workload

[All 24 free-generation requests and six numeric checks](results.json), [all ten pairs](pairs.csv),
[statistics](statistics.json), [trace analysis](trace-summary.json), [source patch](candidate.patch),
[file/build identities](provenance.json), [recorded commands with path placeholders](commands.json),
[logs](logs), and [the excluded first attempt](failed-attempt.json).

Three synthetic inputs are included as *.prompt.txt and exact *.ids.json: r0-l1024 and
r0-l16384 are measured; r1-l1024 is the common 64-output-token warmup. Input hashes
use SHA256 of compact JSON token arrays. Each request is sent on the native engine protocol:

```text
GEN 64 temperature=0 top_p=1 top_k=20 min_p=0 penalty_present=0 penalty_freq=0 penalty_repeat=1 penalty_last_n=0 seed=0 <comma-separated input IDs>
```

The original baseline's 64 generated IDs (included in the gate rows) supply the first
63 tokens of identical forced history for each full-logit check. Each f32 file is
64 x 248320 float32, 63569920 bytes; hashes are archived in results.json. Full dumps,
NSight reports/SQLite and binary files stay local and are not included here.

The prospective continuation rule was median paired prefill A/B >1.03 and B faster in
at least 4/5 pairs at either length. Both lengths met it; only then were two 16K traces
captured. The three client NVTX windows are request, prefill-to-first-token and
decode-after-first-token; they are client boundaries, not exact GPU step boundaries.
The trace JSON retains all role-specific warnings. No CPU sampling was available.

`python verify.py` checks this archive offline: hashes, input/output IDs, numeric hash
agreement, gate/formal layouts, native log timings, paired ratios and trace byte accounting.
This verifier and evidence exporter were written **after** measurement and were not GPU
rerun tools. Original lab controllers have private toolchain/helper dependencies and are
identified by hashes, not presented as a portable runner. Path placeholders replace only
local roots; source patch and exact token files are unchanged. No additional measurements
were made while preparing this bundle. This is not an approved standard benchmark or a
full PR3905/cross-backend validation. Daily service/config was restored after both stages.
'''
    put('README.md',report)
    shutil.copyfile(OUT/'verify_publication.py',DEST/'verify.py')
    files=sorted(p for p in DEST.rglob('*') if p.is_file())
    for path in files:
        text=path.read_text(encoding='utf-8')
        assert not re.search(r'(?<![A-Za-z])[A-Za-z]:[\\/]|\\Users\\|(?:192\.168\.|100\.\d+\.\d+\.\d+)|github_pat_|gh[pousr]_[A-Za-z0-9]{20,}|BEGIN .*PRIVATE KEY',text),path.name
    save('manifest.json',{p.relative_to(DEST).as_posix():{'bytes':p.stat().st_size,'sha256':digest(p)} for p in files})
    payload=[{'path':PREFIX+'/'+p.relative_to(DEST).as_posix(),'mode':'100644','type':'blob','content':p.read_bytes().decode('utf-8')} for p in sorted(DEST.rglob('*')) if p.is_file()]
    (OUT/'publication-tree.json').write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'files':len(payload),'bytes':sum(len(x['content'].encode('utf-8')) for x in payload),'destination':str(DEST)}))


if __name__=='__main__':main()
