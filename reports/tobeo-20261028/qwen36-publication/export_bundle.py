"""Export observed data/fixtures to an isolated report branch; no GPU work."""
import ast
import hashlib
import json
from pathlib import Path
import random
import re
import shutil
import sys

REPO=Path(__file__).resolve().parents[3]
LAB=REPO/'reports/tobeo-20261028'
DEST=REPO.parent/'Strata-contrib-q36-tradeoffs/bench/results/2026-10-28-community-rtx-5060-ti-qwen36-hybrid'
DEST.mkdir(parents=True,exist_ok=True)
CURVE=REPO/'reports/tobeo-20261022/qwen36-context-curve'


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


for folder,files in {
    'pr4335':('summary.json','pairs.csv'),
    'pr4347':('fixed-history-summary.json','fixed-history-pairs.csv','validation-next-summary.json','summary.json'),
}.items():
    source=LAB/('qwen36-'+folder)
    for filename in files:
        target=DEST/'data'/folder/filename;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source/filename,target)

fixtures={}
for case in ['r0-l1024','r0-l16384']:
    spec={}
    for suffix in ['tokens','forced']:
        src=LAB/'qwen36-pr4347/validation-next/run-01'/(case+'.'+suffix)
        dst=DEST/'fixtures'/(case+'.'+suffix);dst.parent.mkdir(exist_ok=True)
        shutil.copyfile(src,dst);spec[suffix+'_file_sha256']=sha(dst)
    shutil.copyfile(CURVE/(case+'.prompt.txt'),DEST/'fixtures'/(case+'.prompt.txt'))
    ids=read(CURVE/(case+'.ids.json'))
    assert ids==[int(x) for x in (DEST/'fixtures'/(case+'.tokens')).read_text().split(',')]
    spec.update(prompt_tokens=len(ids),prompt_text_sha256=sha(DEST/'fixtures'/(case+'.prompt.txt')))
    fixtures[case]=spec

# Materialize every task input, including retrieval inputs that were previously generated locally.
sys.path.insert(0,str(REPO/'build-native-baseline/src-main-5e8a4cca/tools'))
from strata_tokenizer import Tokenizer
tok=Tokenizer.from_gguf(Path(r'D:\Models\Qwen\Qwen3.6-35B-A3B-MTP-GGUF\Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf'))
tree=ast.parse((CURVE/'run_curve.py').read_text(encoding='utf-8'))
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='ledger')
scope={'random':random};exec(compile(ast.Module(body=[node],type_ignores=[]),'recorded-ledger','exec'),scope)
body=tok.encode(scope['ledger'](20261029))
def chat(name,text):return f'<|im_start|>user\nCASE_{name}\n{text}<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'
tasks=read(LAB/'qwen36-pr4347/validation-next/run-01/task-manifest.json')
for task in tasks:
    if task['name'].startswith('retrieval-'):
        length=int(task['name'].split('-')[1])
        prefix='The unique access code is NOVA-731. Remember it while reading this unrelated synthetic ledger.\n'
        suffix='\nReturn only JSON with the field "code" equal to the unique access code stated at the beginning.'
        excerpt=body[:length-len(tok.encode(chat(task['name'],prefix+suffix),parse_special=True))]
        while '\ufffd' in tok.decode(excerpt):excerpt=excerpt[:-1]
        prompt=chat(task['name'],prefix+tok.decode(excerpt)+suffix)
    else:prompt=chat(task['name'],task['text'])
    ids=tok.encode(prompt,parse_special=True)
    assert hashlib.sha256(json.dumps(ids,separators=(',',':')).encode()).hexdigest()==task['input_sha256']
    task.update(prompt=prompt,input_ids=ids)
write(DEST/'fixtures/tasks.json',tasks)
for case in fixtures:
    ids=[int(x) for x in (DEST/'fixtures'/(case+'.tokens')).read_text().split(',')]
    assert tok.encode((DEST/'fixtures'/(case+'.prompt.txt')).read_text(encoding='utf-8'),parse_special=True)==ids
write(DEST/'fixtures/manifest.json',fixtures)

# Preserve per-run output IDs, and original scoring failures corrected for transport EOS.
for pr,rawfile,target in [
    ('pr4335','execution-01/results.json','recorded-runs.json'),
    ('pr4347','fixed-history-01/results.json','recorded-runs.json'),
    ('pr4347','validation-next/run-01/results-rescored.json','recorded-task-runs.json')]:
    raw=read(LAB/('qwen36-'+pr)/rawfile)
    allowed=['started','finished','numeric','numeric_passed','task_passed','tasks','runs','rows','controls','scoring_correction']
    # Fixed-history record has no local-path-bearing per-run fields; filter top-level lifecycle/PIDs.
    write(DEST/'data'/pr/target,{k:raw[k] for k in allowed if k in raw})
initial=read(LAB/'qwen36-pr4347/execution-02/results.json')
write(DEST/'data/pr4347/identity-failure.json',{
    'started':initial['started'],'finished':initial['finished'],'error':initial['error'],
    'pair_checks':initial['pair_checks'],
    'rows':[{k:v for k,v in row.items() if k not in ['resources','process_cpu_s','prompt_progress']}
            for row in initial['rows']],
    'note':'Original free-generation protocol stopped after pair0; not a valid speed comparison. Later fixed-history results use a separate protocol.'})

# Only measured engine output; redact paths, not timings or tokens.
sources={
    'pr4335':[(LAB/'qwen36-pr4335/execution-01','*.log')],
    'pr4347':[(LAB/'qwen36-pr4347/fixed-history-01','*.log'),
              (LAB/'qwen36-pr4347/validation-next/run-01','*.log')]}
for pr,entries in sources.items():
    for source,pattern in entries:
        for file in source.glob(pattern):
            if not file.is_file():continue
            text=file.read_text(encoding='utf-8',errors='replace')
            text=re.sub(r'[A-Za-z]:[\\/][^\r\n]*', '<local path redacted>', text)
            # A path may precede diagnostic details on the same line; original numerical evidence is in JSON.
            path=DEST/'logs'/pr/source.name/file.name;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(text,encoding='utf-8')

# Archive the executed driver source with its original hash. Generic model paths are parameterized only in this export.
provenance=[]
for source in [LAB/'qwen36-pr4335/run_validation.py',LAB/'qwen36-pr4347/benchmark_fixed_history.py',
               LAB/'qwen36-pr4347/validate_next.py',LAB/'qwen36-pr4347/build_pair.py',CURVE/'run_curve.py']:
    text=source.read_text(encoding='utf-8')
    text=re.sub(r'^MODEL\s*=\s*Path\([^\n]*$', 'MODEL = Path(os.environ["STRATA_REPORT_MODEL"])',text,flags=re.M)
    path=DEST/'historical-drivers'/source.parent.name/source.name;path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text,encoding='utf-8')
    provenance.append({'source':source.relative_to(REPO).as_posix(),'original_sha256':sha(source),
                       'export':path.relative_to(DEST).as_posix(),'export_sha256':sha(path),
                       'change':'Model path parameterized if present; archival drivers retain historical lab dependencies.'})
for folder,filenames in {'qwen36-pr4335':['experiment-plan.md'],
                         'qwen36-pr4347':['experiment-plan.md','validation-next-plan.md','fixed-history-plan.md']}.items():
    for filename in filenames:
        target=DEST/'historical-plans'/folder/filename;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(LAB/folder/filename,target)
write(DEST/'provenance.json',{'historical_drivers':provenance,'measurement_dates':['2026-10-28','2026-10-29'],
                            'model_revision':'not recorded; exact GGUF size and SHA-256 recorded',
                            'replay_scripts':'Added after measurement; not claimed as the original executed driver.'})
shutil.copyfile(LAB/'qwen36-pr4335/file_entry.cpp',DEST/'file_entry.cpp')
print('Exported',sum(1 for p in DEST.rglob('*') if p.is_file()),'files; all synthetic prompt/task token hashes verified')
