"""Publish compact observed evidence, including a partial/failed gate if needed."""
import csv
import hashlib
import json
from pathlib import Path
from statistics import median

OUT=Path(__file__).resolve().parent
RUN=OUT/'execution-01'
r=json.loads((RUN/'results.json').read_text(encoding='utf-8'))
assert r.get('finished'),'Do not summarize before restoration finishes'
build=json.loads((OUT/'build-summary.json').read_text(encoding='utf-8'))
pairs=[];cases={}


def spread(values):return {'median':median(values),'min':min(values),'max':max(values)}


for case in r['fixtures']:
    for pair in range(5):
        arms={v['requested_chunk']:v for v in r['rows'] if v['case']==case and v['pair']==pair and v.get('passed')}
        if set(arms)!={2048,4096}:continue
        row={'case':case,'pair':pair,'order':'2048/4096' if pair%2==0 else '4096/2048'}
        for metric in ['prefill_ms','generation_ms','request_ms']:
            row['c2048_'+metric]=arms[2048][metric];row['c4096_'+metric]=arms[4096][metric]
            row[metric+'_2048_over_4096']=arms[2048][metric]/arms[4096][metric]
        pairs.append(row)
    selected=[v for v in pairs if v['case']==case]
    if selected:
        cases[case]={'pairs':len(selected),'metrics':{metric:{
            'c2048':spread([v['c2048_'+metric] for v in selected]),
            'c4096':spread([v['c4096_'+metric] for v in selected]),
            'paired_2048_over_4096':spread([v[metric+'_2048_over_4096'] for v in selected]),
            'c4096_faster_pairs':sum(v[metric+'_2048_over_4096']>1 for v in selected)}
            for metric in ['prefill_ms','generation_ms','request_ms']}}
if pairs:
    with (OUT/'pairs.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(pairs[0]));writer.writeheader();writer.writerows(pairs)

summary={
    'started':r['started'],'finished':r['finished'],'passed':r['passed'],'phase':r['phase'],
    'error':r.get('error'),'main_revision':build['main'],'candidate_revision':r.get('source_revision'),
    'implementation_author':'rynwang','pr':'https://github.com/Niko1221/Strata/pull/4335',
    'plan_sha256':r.get('plan_sha256'),'runner_sha256':r.get('runner_sha256'),
    'helper_sha256':r.get('helper_sha256'),'binaries':r.get('binaries'),
    'build_passed':build['passed'],
    'build_commands_exit_codes':[v['exit_code'] for v in build['arms']['pr4335']['commands']],
    'model':{'bytes':build['model']['bytes'],'sha256':build['model']['sha256']},
    'scope':'Windows/CUDA13.2 sm120, RTX5060Ti16GB/i7-12700/128GB DDR4, context32768/workers7/MTP0/FP32 KV/packed on/fixed residency; no PR4347.',
    'auto_chunk':r.get('auto_chunk'),'slots':r['expected_slots'],
    'fixtures':{case:{**v,'forced_tokens':[int(t) for t in (RUN/(case+'.forced')).read_text().split(',')]}
                for case,v in r['fixtures'].items()},
    'numeric':r['numeric'],'numeric_passed':r.get('numeric_passed',False),
    'numeric_runs':[{k:v for k,v in row.items() if k!='output_ids'} for row in r['runs']],
    'task_passed':r.get('task_passed',False),
    'tasks':{chunk:[{k:v for k,v in row.items() if k!='output_ids'} for row in rows]
             for chunk,rows in r['tasks'].items()},
    'cases':cases,'pairs':pairs,
    'performance_valid':bool(r['passed'] and len(r['rows'])==20 and len(pairs)==10),
    'performance_runs':[{k:v for k,v in row.items() if k!='output_ids'}|{
        'output_sha256':hashlib.sha256(','.join(map(str,row.get('output_ids',[]))).encode()).hexdigest()}
        for row in r['rows']],
    'bandwidth_before':r.get('bandwidth-before'),'bandwidth_after':r.get('bandwidth-after'),
    'bandwidth_relative_drift':r.get('bandwidth_relative_drift'),
    'download_processes_suspended':len(r['downloads_suspended']),
    'downloads_restored':all(v.get('resumed') or v.get('exited') for v in r.get('download_resumption',[])),
    'daily_loaded_after':r['service_transition'].get('health_after',{}).get('loaded'),
    'daily_config_unchanged':r.get('daily_config_sha256_before')==r.get('daily_config_sha256_after'),
    'restore_errors':r.get('restore_errors',[]),
    'limits':['Same-chunk bitwise equality and 24 small tasks are not broad quality equivalence.',
              'Fixed residency, synthetic ledger, 96 teacher-forced tokens and 97 argmax evaluations.',
              'Native timing excludes load/warmup/HTTP; generation includes final ID printing.',
              'No dynamic cache, concurrent serving, long stability, cross-backend or per-request clock/temperature trace.'],
}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:summary[k] for k in ['passed','phase','error','auto_chunk','slots','numeric_passed','task_passed','cases']},indent=2))
