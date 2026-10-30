"""Seal static evidence after detached verification exits; exclude changing runtime logs."""
import hashlib,json,traceback
from pathlib import Path
from datetime import datetime,timezone,timedelta
P=Path(__file__).resolve().parent

def sha(path):
 with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(path,value):
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8');tmp.replace(path)
def runtime(path):return path.name.startswith('background-')

status=json.loads((P/'background-status.json').read_text(encoding='utf-8'))
try:
 assert status['state']=='complete' and status['passed']
 summary=json.loads((P/'summary.json').read_text(encoding='utf-8'));assert summary['passed']
 old=json.loads((P/'evidence-manifest.json').read_text(encoding='utf-8'))
 for name,value in old.items():
  if not runtime(Path(name)):assert sha(P/name)==value,name
 files={q.relative_to(P).as_posix():sha(q) for q in sorted(P.rglob('*')) if q.is_file() and '__pycache__' not in q.parts and not runtime(q) and q.name not in ['summary.json','README.md','evidence-manifest.json']}
 save(P/'evidence-manifest.json',files)
 summary['manifest_sha256']=sha(P/'evidence-manifest.json');summary['evidence_files']=len(files)
 summary['manifest_runtime_files_excluded']=True;save(P/'summary.json',summary)
 status.update(state='complete',passed=True,evidence_files=len(files),static_manifest_sealed=True)
except BaseException as e:
 status.update(state='failed',passed=False,seal_error=repr(e));traceback.print_exc()
finally:
 status['finished']=datetime.now(timezone(timedelta(hours=8))).isoformat();save(P/'background-status.json',status)
