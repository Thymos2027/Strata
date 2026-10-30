"""Export verified existing evidence; no GPU work or network writes."""
from pathlib import Path
import json,hashlib,gzip,zipfile,re,csv,io,shutil
P=Path(__file__).resolve().parent
D=P/'publication-evidence-02'
ROOT=P.parents[2]
CPU=P.parent/'qwen36-cpu-mechanism'
JOB=P.parent/'qwen36-job-path'
PREFIX='bench/results/2026-10-30-qwen36-cpu-copy-job-followup'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def scrub(s):
 # Paths below are provenance placeholders, never replacement of measured values.
 for a,b in [(str(ROOT),'<REPO_ROOT>'),('D:/Models','<MODEL_ROOT>'),('D:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools','<VS_BUILDTOOLS>'),('D:/Program Files/Anaconda','<PYTHON_ENV>'),('C:/Users/tobeo','<USER_HOME>')]:
  forward=a.replace(chr(92),'/')
  for v in sorted([forward,forward.replace('/',chr(92)),forward.replace('/',chr(92)*2)],key=len,reverse=True):s=s.replace(v,b)
 return s

def main():
 assert not D.exists()
 provenance={}
 for key,r in [('cpu',CPU),('job',JOB)]:
  s=load(r/'summary.json');m=load(r/'evidence-manifest.json')
  assert s['passed'] and sha(r/'evidence-manifest.json')==s['manifest_sha256']
  for n,h in m.items():assert sha(r/n)==h,(key,n)
  provenance[key]={'local_raw_manifest_sha256':s['manifest_sha256'],'local_raw_files':len(m)}
 D.mkdir();a=D/'archive';a.mkdir()
 def put(n,s):
  q=a/n;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(scrub(s),encoding='utf-8')
 def cp(r,n,target=None):
  q=r/n
  if q.suffix=='.png':shutil.copyfile(q,a/(target or n))
  else:put(target or n,q.read_text(encoding='utf-8'))
 for n in ['summary.json','cpu-summary.json','mechanism-summary.json','mechanism-stages.csv','experiment-plan.md','analyze_cpu.py','analyze_mechanism.py','timeline.png']:cp(CPU,n,'cpu/'+n)
 for n in ['summary.json','critical-path.json','token-ledger.csv','experiment-plan.md','completion-plan.md','job_trace.hpp','diagnostic-complete.patch','analyze_complete.py','build-complete.json','timeline.png']:cp(JOB,n,'job/'+n)
 # Keep every phase, including the 80 prefill-tail phases, in a compact download.
 q=a/'job/phase-ledger.csv.gz';q.write_bytes(gzip.compress((JOB/'phase-ledger.csv').read_bytes(),mtime=0))
 for r,key,cap in [(CPU,'cpu','capture-01'),(JOB,'job','capture-02')]:
  cp(r,cap+'/results.json',key+'/capture-results.json')
  for q in sorted((r/cap).glob('*.log')):
   if q.stat().st_size:cp(r,str(q.relative_to(r)),key+'/logs/'+q.name)
 for n in ['build-complete-2.log','build-complete-3.log']:cp(JOB,n,'job/logs/'+n)
 fixtures=ROOT/'reports/tobeo-20261022/qwen36-context-curve'
 for name in ['r0-l1024','r0-l16384','r1-l1024']:
  for suffix in ['.ids.json','.prompt.txt']:cp(fixtures,name+suffix,'inputs/'+name+suffix)
 put('provenance.json',json.dumps({'baseline':'46c152a1310f77cd2f0ce2c7cd213962df14fe83','copy_slice':'af08278c15e857345dad95805dda7256a559dcfa',
   'original_public_evidence_commit':'7c0247c72d3e57df40e2dd8b9be415ec90046f98','export_script_sha256':sha(Path(__file__)),
   'original_evidence':provenance,'note':'Exported after measurement; text paths sanitized. Original historical summary publication flags retain their measurement-time values; see top-level publication record for current status. Raw traces, all-task CSV, full logits and binaries stay local.'},indent=2))
 verifier=P/'verify_archive.py';cp(P,verifier.name)
 # Review all text for credentials/private paths before creating the upload set.
 for q in a.rglob('*'):
  if not q.is_file() or q.suffix in ['.png','.gz']:continue
  s=q.read_text(encoding='utf-8')
  assert not re.search(r'(?i)(?:github_pat_|gh[pousr]_)[A-Za-z0-9_]{20,}',s),q
  assert not re.search(r'(?<![A-Za-z])[A-Za-z]:[\\/]',s),q
 manifest={str(q.relative_to(a)).replace('\\','/'):sha(q) for q in sorted(a.rglob('*')) if q.is_file()}
 put('file-sha256.json',json.dumps(manifest,indent=2))
 import subprocess,sys
 subprocess.run([sys.executable,str(a/'verify_archive.py'),str(a)],check=True)
 with zipfile.ZipFile(D/'evidence.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for q in sorted(a.rglob('*')):
   if q.is_file():z.write(q,q.relative_to(a).as_posix())
 for r,n,target in [(CPU,'cpu-summary.json','cpu-summary.json'),(CPU,'mechanism-summary.json','mechanism-summary.json'),(CPU,'mechanism-stages.csv','mechanism-stages.csv'),(JOB,'critical-path.json','critical-path.json'),(JOB,'token-ledger.csv','token-ledger.csv')]:
  (D/target).write_text(scrub((r/n).read_text(encoding='utf-8')),encoding='utf-8')
 shutil.copyfile(a/'file-sha256.json',D/'archive-file-sha256.json')
 shutil.copyfile(a/'verify_archive.py',D/'verify_archive.py')
 (D/'README.md').write_text((P/'public-report.md').read_text(encoding='utf-8'),encoding='utf-8')
 files=[q for q in sorted(D.iterdir()) if q.is_file()]
 spec=[{'path':PREFIX+'/'+q.name,'name':q.name,'bytes':q.stat().st_size,'sha256':sha(q),'binary':q.suffix=='.zip'} for q in files]
 (P/'upload-spec.json').write_text(json.dumps(spec,indent=2),encoding='utf-8')
 print(json.dumps({'passed':True,'archive_files':len(manifest)+1,'upload_files':len(spec),'bytes':sum(x['bytes'] for x in spec)}))
if __name__=='__main__':main()
