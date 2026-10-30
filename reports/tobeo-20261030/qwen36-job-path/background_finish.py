"""Detached final verification only; no inference, source build or service changes."""
from pathlib import Path
import json,traceback
from datetime import datetime,timezone,timedelta
import finalize
P=Path(__file__).resolve().parent

def now():return datetime.now(timezone(timedelta(hours=8))).isoformat()
def write(value):
 q=P/'background-status.json';tmp=q.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8');tmp.replace(q)

r={'started':now(),'state':'running','operation':'final hash, numerical and wall-ledger verification','GPU_capture_complete':True,'daily_service_restored_at':'2026-10-30T13:32:02.149333+08:00'}
write(r)
try:
 finalize.main()
 s=json.loads((P/'summary.json').read_text(encoding='utf-8'))
 assert s['passed']
 r.update(state='complete',passed=True,summary='summary.json',evidence_files=s['evidence_files'])
except BaseException as e:
 r.update(state='failed',passed=False,error=repr(e));traceback.print_exc()
finally:
 r['finished']=now();write(r)
