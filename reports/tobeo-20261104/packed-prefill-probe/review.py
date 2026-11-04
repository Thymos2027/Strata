"""Read-only evidence audit followed by local review metadata update."""
import json
import math
from pathlib import Path
from datetime import datetime, timezone, timedelta

OUT=Path(__file__).resolve().parent
summary=json.loads((OUT/'summary.json').read_text())
rr=summary['operator_cases']
assert len(rr)==48
checks=[]
for p in sorted(OUT.glob('w*-rows*-batch*.stdout.log')):
    lines=p.read_text().splitlines()
    cc=[s.split(',') for s in lines if s.startswith('CHECK,')]
    pp=[s.split(',') for s in lines if s.startswith('PAIR,')]
    assert len(cc)==1 and len(pp)==10
    c=cc[0]; nrmse,maxerr,maxref=map(float,c[5:8])
    assert all(math.isfinite(x) for x in (nrmse,maxerr,maxref))
    assert nrmse<=.002 and maxerr<=.01+.002*maxref
    checks.append({'file':p.name,'nrmse':nrmse,'max_abs_error':maxerr})
assert len(checks)==24
for r in rr:
    assert len(r['pairs'])==5
    assert all(p['separate_ms']>0 and p['packed_ms']>0 and p['ratio']>0 for p in r['pairs'])
    assert sorted(p['pair'] for p in r['pairs'])==[1,2,3,4,5]
    for p in r['pairs']:
        if r['mode']=='resident':
            assert p['separate_transfer_bytes']==p['packed_transfer_bytes']==0
        else:
            assert p['separate_transfer_bytes']==p['packed_transfer_bytes']*r['batch']
review={'reviewed_at':datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'checks_passed':True,'correctness_cases':len(checks),'timing_cases':len(rr),
        'timing_pairs':sum(len(r['pairs']) for r in rr),
        'all_sampled_outputs_equal':all(c['max_abs_error']==0 for c in checks),
        'all_cases_packed_faster_in_all_five_pairs':all(r['packed_faster_pairs']==5 for r in rr),
        'minimum_case_median_ratio':min(r['ratio_median'] for r in rr),
        'maximum_case_median_ratio':max(r['ratio_median'] for r in rr),
        'full_prefill_tested':False,'production_grouped_moe_kernel_tested':False,
        'independent_restart_repetitions':False,'checks':checks}
(OUT/'review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding='utf8')
summary.update(review_required=False,review_evidence='review.json; REVIEW.md')
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
state=json.loads((OUT/'status.json').read_text())
state.update(review_required=False,reviewed_at=review['reviewed_at'],status='operator_probe_reviewed_full_prefill_pending')
(OUT/'status.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in review.items() if k!='checks'},ensure_ascii=False,indent=2))
