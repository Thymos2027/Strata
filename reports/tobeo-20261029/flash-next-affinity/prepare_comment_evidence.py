"""Package existing measurements for a comment; does not run models or publish."""
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
DEST=ROOT/'performance-04/comment-evidence'
DEST.mkdir(exist_ok=True)
r=json.loads((ROOT/'performance-04/results.json').read_text(encoding='utf-8'))
s=json.loads((ROOT/'summary.json').read_text(encoding='utf-8'))
assert r['passed'] and r['finished'] and len(r['rows'])==45
assert all(x['identical'] and x['draft_counts_identical'] and x['protocol_passed'] for x in r['rows'])
assert len(r['download_quiet_checks'])==31 and all(x['no_downloader'] and x['unchanged'] for x in r['download_quiet_checks'])


def scrub(text):
    return text.replace('D:\\Models\\Strata','<MODEL_ROOT>').replace('E:\\Coder\\LLM\\Strata','<REPO_ROOT>')


def put(name,text):
    path=DEST/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(text.encode('utf-8'))


for name in ['summary.json','paired-results.csv','workloads.json']:
    (DEST/name).write_bytes((ROOT/name).read_bytes())
for path in sorted((ROOT/'performance-04').glob('round-*.log')):
    put('logs/'+path.name,scrub(path.read_text(encoding='utf-8')))
args=r['arms'][0]['args'][:]
args[args.index('--pool-affinity')+1]='<all|p-cores|measure>'
put('config.json',json.dumps({'engine_sha256':r['fingerprints'][r['resolved_config']['exe']]['sha256'],
    'arguments': [scrub(x) for x in args],
    'environment':{'STRATA_PREFILL_CPU_SHARE':'0','STRATA_ROUTE_TAIL_SKIP':'0',
                   'CUDA_VISIBLE_DEVICES':'0','CUDA_MODULE_LOADING':'EAGER'},
    'environment_note':'Other STRATA_* variables cleared; the DLL directory was supplied through child_env.',
    'paths':'Placeholders replace local roots. File identities are in summary.json.',
    'model_revision':'Not recorded; exact local file hashes are supplied instead.',
    'replay':'This bundle is archived evidence, not a portable GPU runner.'},indent=2))
put('README.md', '''# Flash-Next IQ3_S CPU-affinity validation on Windows

Measured 2026-10-29, 17:21-17:51 Asia/Shanghai. Independent evidence for
[Strata #1912](https://github.com/Niko1221/Strata/pull/1912), not a proposed patch or a standard-protocol submission.

i7-12700 (8P/4E), RTX 5060 Ti 16 GB, 128 GB DDR4, Windows 11, driver 610.88.
Official engine 0.1.52, BUILD f-027-rel/a42cc3d7df70, CUDA 13.0;
exe SHA-256 dbd0f9b692e9790cd8a25b383a265fab4ccf424a98e6ebc533c6e00dc58628bc.
Existing Qwen3.8-Flash-Next GSQ-RCO IQ3_S native pack, PLE, MTP and expert profile.
Exact files/hashes: [summary.json](summary.json). Model revision was not recorded.

## Method

Five restart rounds, all/P/measure each round: APM, PMA, MAP, MPA, AMP.
Three synthetic inputs (code 1025, English 4097, Chinese 1025 tokens), each with
256 generated tokens. Input order rotates by round and is identical within a round.
Each of 15 new processes receives the same 96-output-token warm-up, excluded from timing.
All 45 requests match the gate's complete output IDs and offered/accepted draft counts.
Three modes also pass six deterministic tasks each (18/18); this is not broad quality evaluation.
The gate ran with downloads active; gate times are not performance evidence.

Controlled settings: actual cache 3107 slots/6092 MiB (budget argument 2400),
64K context cap, INT8 KV/32K resident, prefill 1024, spec4/min-p0,
lookup/suffix off, fixed PCIe fraction .55, adaptation/conversation cache off,
prompt CPU share and route-tail skipping off. Greedy, neutral penalties.
[config.json](config.json) records the arguments/environment; [workloads.json](workloads.json) contains exact inputs/IDs.
Worker defaults are part of the policy: all 11, P 7, plus host.
Post-warm-up Windows snapshots confirmed the expected worker single-core masks;
host core 0 was logged, not continuously verified during generation.

The downloader was stopped for the entire formal matrix. All 31 before/after-arm
and final checks found no downloader and unchanged files/checkpoints.
Pinned HtoD: 24.846733 before, 24.853699 GB/s after (0.0280% drift).

## Results

Primary metric: native prefill + decode milliseconds, not HTTP TTFT.
Ratios are computed within each round before taking their median. Greater than 1 means P is faster.

| Input | Median all/P ratio (range, five pairs) | P faster |
| --- | --- | --- |
| Code | 1.0019 (0.9916-1.1431) | 4/5 |
| English | 0.9996 (0.9549-1.0461) | 2/5 |
| Chinese | 1.0016 (0.9637-1.0932) | 3/5 |

All samples: [paired-results.csv](paired-results.csv), [per-request JSON](summary.json),
[15 sanitized engine logs](logs). No slow sample was removed.
Observed within-manual-mode relative ranges in total cost are about 4.9-12.8%.
The prospective condition (same direction in all five pairs, exceeding observed
within-mode variation) was not met. No stable selection loss was demonstrated.

Measure selected P four times, all once. Microbenchmark all/P milliseconds:
9.71/10.09, 9.70/9.01, 9.57/8.53, 9.98/8.93, 9.27/10.27.
These decisions follow the existing 10% P preference. The final round's manual
all was faster on code/Chinese and P faster on English; neither mode won every input.

Paired P/all process CPU-time medians: .6848/.7114/.6786 for code/English/Chinese
(P lower in 5/5 each), about 29-32% less accumulated CPU time. This is not energy
measurement, a critical-path attribution, or a fixed-worker-count comparison.

## Failed attempts and limits

Preparation failed on component-root resolution, unsupported native spec0,
insufficient VRAM at a larger cache, and a Windows pause-status assertion.
No formal timing from those attempts is included. A thread-count diagnostic launch
was blocked by automatic review and was not used by the formal controller.
An earlier matrix's 15 requests were excluded in full after another session resumed
downloads at 17:09:36-17:09:59. Another three-request matrix failed a sustained
quiet comparison; the differing fields were not saved, so its cause is unresolved.
Both remain excluded; only performance-04 is represented here.

One hardware configuration, controlled policies, three synthetic requests, five rounds.
Not daily defaults, a standardized benchmark, API/concurrency, other contexts/CPUs/backends,
broad quality equivalence, a new optimization, or evidence to change a default.
No continuous temperature/clock capture or soft/hard page-fault classification.
Daily service and original config were restored, and downloads restarted afterward.

This compact bundle was prepared after measurement for a discussion comment.
Local controller/helper/plan hashes are retained in the JSON as provenance, but their
private lab dependencies and full resource samples are not a portable replay package.
The offline verifier was added after measurement and does not validate a GPU rerun.
''')
put('verify.py', '''"""Offline evidence consistency check; written after measurement. No GPU run."""
import csv,hashlib,json,re
from pathlib import Path
from statistics import median
p=Path(__file__).resolve().parent
for name,info in json.loads((p/'manifest.json').read_text(encoding='utf-8')).items():
    assert hashlib.sha256((p/name).read_bytes()).hexdigest()==info['sha256'],name
s=json.loads((p/'summary.json').read_text(encoding='utf-8'));assert s['passed'] and len(s['rows'])==45
rows=s['rows'];pairs=list(csv.DictReader((p/'paired-results.csv').open()))
assert len(pairs)==15
for x in rows:
    assert x['protocol_passed'] and x['identical'] and x['draft_counts_identical']
    assert len(x['output_ids'])==256 and x['timings']['drafts_offered']>0
    assert hashlib.sha256(json.dumps(x['output_ids'],separators=(',',':')).encode()).hexdigest()==x['output_sha256']
for a in s['arms']:
    text=(p/'logs'/(a['tag']+'.log')).read_text(encoding='utf-8')
    assert 'expert cache 3107 slots' in text and '--ple-io ram chosen' in text
    timed=re.findall(r'prompt (\\d+) tokens = 0 reused \\+ \\d+ read in (\\d+) ms.*?, (\\d+) generated in (\\d+) ms.*?drafts accepted (\\d+) of (\\d+)',text)[1:]
    selected=[x for x in rows if x['tag']==a['tag']];assert len(timed)==len(selected)==3
    for logged,x in zip(timed,selected):
        pt,pm,gt,dm,accepted,offered=map(int,logged);t=x['timings']
        assert pt==x['prompt_tokens'] and gt==256 and abs(pm-t['prompt_ms'])<=1 and abs(dm-t['decode_ms'])<=1
        assert accepted==t['drafts_accepted'] and offered==t['drafts_offered']
for name in ['code','english','chinese']:
    ratios=[]
    for n in range(5):
        a={x['mode']:x for x in rows if x['name']==name and x['round']==n}
        v=a['all']['request_ms']/a['p-cores']['request_ms'];ratios.append(v)
        pair=next(x for x in pairs if x['workload']==name and int(x['round'])==n)
        assert abs(float(pair['request_ms_all_over_P'])-v)<1e-12
    assert abs(median(ratios)-s['summaries'][name]['request_ms']['paired_all_over_P']['median'])<1e-12
print('PASS: artifact hashes, 45 output identities, 15 logs, and 15 primary paired ratios')
''')
files=[p for p in DEST.rglob('*') if p.is_file() and p.name!='manifest.json']
for path in files:
    text=path.read_text(encoding='utf-8')
    assert not re.search(r'(?<![A-Za-z])[A-Za-z]:[\\/]|\\Users\\|192\.168\.',text),path.name
manifest={p.relative_to(DEST).as_posix():{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in files}
put('manifest.json',json.dumps(manifest,indent=2))
payload=[{'path':'bench/results/2026-10-29-affinity-i7-12700/'+p.relative_to(DEST).as_posix(),
          'mode':'100644','type':'blob','content':p.read_bytes().decode('utf-8')} for p in DEST.rglob('*') if p.is_file()]
(DEST.parent/'tree-payload.json').write_text(json.dumps(payload),encoding='utf-8')
print(json.dumps({'files':len(payload),'bytes':sum(len(x['content'].encode()) for x in payload),'destination':str(DEST)}))
