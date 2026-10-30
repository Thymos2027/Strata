"""Offline integrity and wall-ledger checks; not a GPU rerun or raw-trace reanalysis."""
from pathlib import Path
import hashlib,json,gzip,csv,io,sys
p=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parent
m=json.loads((p/'file-sha256.json').read_text())
for n,h in m.items():assert hashlib.sha256((p/n).read_bytes()).hexdigest()==h,n
cpu=json.loads((p/'cpu/summary.json').read_text());job=json.loads((p/'job/summary.json').read_text());mech=json.loads((p/'cpu/mechanism-summary.json').read_text())
assert cpu['passed'] and job['passed'] and mech['all_320_stages_byte_conserved'] and mech['all_320_dependency_chains_checked']
phases=list(csv.DictReader(io.StringIO(gzip.decompress((p/'job/phase-ledger.csv.gz').read_bytes()).decode('utf-8'))))
tokens=list(csv.DictReader((p/'job/token-ledger.csv').open()))
assert len(phases)==10160 and len(tokens)==126 and sum(int(x['tasks']) for x in phases)==243840
for x in phases:
 assert int(x['last_release_ordinal'])==int(x['tasks'])
 assert sum(int(x[k]) for k in ['pre_publish_ns','critical_chain_job_body_ns','critical_chain_handoff_and_queue_ns','phase_tail_ns'])==int(x['wall_ns'])
for x in tokens:
 assert sum(int(x[k]) for k in ['gpu_submit_ns','route_wait_ns','phase_pre_publish_ns','critical_branch_job_body_ns','critical_branch_queue_handoff_ns','phase_tail_ns','CPU_moe_other_ns','token_other_ns'])==int(x['wall_ns'])
print(json.dumps({'passed':True,'files':len(m),'phases':len(phases),'tasks':243840,'tokens':len(tokens)}))
