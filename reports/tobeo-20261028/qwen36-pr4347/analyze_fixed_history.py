"""Export all ten pairs and a bounded fixed-history performance summary."""
import csv
import hashlib
import json
from pathlib import Path
from statistics import median
from build_pair import MAIN, CANDIDATE

OUT=Path(__file__).resolve().parent
RUN=OUT/'fixed-history-01'
r=json.loads((RUN/'results.json').read_text(encoding='utf-8'))
assert r.get('finished') and r['phase']=='complete' and r['passed'], 'No valid completed experiment'
assert len(r['rows'])==20 and all(row['passed'] for row in r['rows'])
assert r['service_transition']['health_after']['loaded']
assert r['daily_config_sha256_before']==r['daily_config_sha256_after']
assert all(row.get('resumed') or row.get('exited') for row in r['download_resumption'])


def spread(values):
    return {'median':median(values),'min':min(values),'max':max(values)}


pairs=[];cases={}
for case in r['fixtures']:
    for pair in range(5):
        group={row['arm']:row for row in r['rows'] if row['pair']==pair and row['case']==case}
        assert set(group)=={'A','B'}
        row={'case':case,'pair':pair,'order':'AB' if pair%2==0 else 'BA'}
        for metric in ['prefill_ms','generation_ms','request_ms']:
            row['A_'+metric]=group['A'][metric];row['B_'+metric]=group['B'][metric]
            row[metric+'_A_over_B']=group['A'][metric]/group['B'][metric]
        pairs.append(row)
    selected=[p for p in pairs if p['case']==case]
    metrics={}
    for metric in ['prefill_ms','generation_ms','request_ms']:
        ratios=[p[metric+'_A_over_B'] for p in selected]
        metrics[metric]={'A':spread([p['A_'+metric] for p in selected]),
                         'B':spread([p['B_'+metric] for p in selected]),
                         'paired_A_over_B':spread(ratios),
                         'B_faster_pairs':sum(v>1 for v in ratios),
                         'B_slower_pairs':sum(v<1 for v in ratios)}
    cases[case]={'pairs':5,'metrics':metrics}

with (OUT/'fixed-history-pairs.csv').open('w',newline='',encoding='utf-8') as f:
    writer=csv.DictWriter(f,fieldnames=list(pairs[0]));writer.writeheader();writer.writerows(pairs)

summary={
    'started':r['started'],'finished':r['finished'],'passed':r['passed'],
    'main':MAIN,'candidate':CANDIDATE,'plan':'fixed-history-plan.md',
    'plan_sha256':r['plan_sha256'],'runner_sha256':r['script_sha256'],
    'validation_sha256':r['validation_sha256'],'adapter_sha256':r['adapter_sha256'],
    'hardware':'RTX 5060 Ti 16GB, i7-12700, 128GB DDR4, Windows, driver610.88',
    'configuration':{'context':32768,'prefill_chunk':2048,'pool_workers':7,'mtp':0,
                     'fixed_residency':True,'automatic_initial_budget':True,
                     'A':'KEEP_PACKED=1, 63 GPU experts/layer','B':'default drop packed, 89 GPU experts/layer',
                     'warmup':'engine built-in one chunk and one decode step, new process per request',
                     'forced_history_tokens':96,'argmax_evaluations':97,'decode_forward_steps':96,
                     'full_logit_dump':False},
    'timing_scope':'Native CLI prefill + generation; excludes load/warmup/HTTP; generation includes final output-ID printing. Not standard decode throughput or free generation.',
    'fixtures':{case:{'prompt_tokens':v['prompt_tokens'],
                      'tokens_file_sha256':v['tokens_file_sha256'],
                      'forced_file_sha256':v['forced_file_sha256'],
                      'forced_tokens':[int(x) for x in (RUN/(case+'.forced')).read_text().split(',')]}
                for case,v in r['fixtures'].items()},
    'cases':cases,'pairs':pairs,
    'runs':[{k:v for k,v in row.items() if k!='output_ids'} | {
        'output_ids_sha256':hashlib.sha256(','.join(map(str,row['output_ids'])).encode()).hexdigest()}
            for row in r['rows']],
    'bandwidth_before':r['bandwidth-before'],'bandwidth_after':r['bandwidth-after'],
    'bandwidth_relative_drift':r['bandwidth_relative_drift'],
    'download_processes_paused':len(r['downloads_suspended']),
    'downloads_restored':all(row.get('resumed') or row.get('exited') for row in r['download_resumption']),
    'daily_service_restored_loaded':r['service_transition']['health_after']['loaded'],
    'daily_config_unchanged':r['daily_config_sha256_before']==r['daily_config_sha256_after'],
    'limitations':['Synthetic ledger and 96-token teacher-forced history.',
                   'Frozen residency; no dynamic cache or broad quality claim.',
                   'Five pairs per input, no significance inference.',
                   'No cross-backend, concurrent serving or profiling validation.'],
}
(OUT/'fixed-history-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'cases':cases,'bandwidth_before':r['bandwidth-before'],
                  'bandwidth_after':r['bandwidth-after']},indent=2))
