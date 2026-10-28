"""Publish small, path-free summaries from actual recorded results, never from plans."""
import csv
import argparse
import json
from pathlib import Path
import statistics as st

OUT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--run-id',default='execution-02');args=parser.parse_args()
result=json.loads((OUT/args.run_id/'results.json').read_text(encoding='utf-8'))
build=json.loads((OUT/'build-summary.json').read_text(encoding='utf-8'))
summary={'started':result['started'],'finished':result.get('finished'),'phase':result['phase'],
         'passed':result['passed'],'error':result.get('error'),
         'main_revision':build['main'],'candidate_revision':build['candidate'],'candidate_author':build['author'],
         'model':{k:v for k,v in build['model'].items() if k!='path'},
         'binaries':{name:r.get('binaries') for name,r in build['arms'].items()},
         'build_passed':build['passed'],'configuration':result['configuration'],
         'gate_passed':result['gate'].get('passed'),
         'fixed_main_passed':result['gate'].get('fixed_main',{}).get('passed'),
         'pair_output_checks':result.get('pair_checks',[]),'cases':{},
         'bandwidth_before':result.get('bandwidth-before'),'bandwidth_after':result.get('bandwidth-after'),
         'service_restored':result.get('service_transition',{}).get('health_after',{}).get('loaded'),
         'download_resumption':result.get('download_resumption',[]),
         'limits':['one synthetic ledger workload','MTP0 performance only','no profiler or kernel timing',
                   'no long soak, concurrent serving, HIP/SYCL build or hardware test']}
rows=[r for r in result['rows'] if r.get('pair') is not None]
eligible=bool(result['passed'] and len(rows)==20 and len(result.get('pair_checks',[]))==10
              and all(x['identical'] for x in result['pair_checks']))
summary['performance_claim_allowed']=eligible
small=[]
for r in rows:
    small.append({k:r[k] for k in ['pair','case','keep_packed','prompt_tokens','generated_tokens','reused_tokens',
         'fresh_tokens','prompt_ms','decode_ms','decode_ms_per_token','decode_tok_s','client_ttft_s','client_total_s',
         'output_sha256','input_sha256','protocol_passed','process_cpu_s']})
if small:
    with (OUT/'paired-requests.csv').open('w',encoding='utf-8',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=list(small[0]));writer.writeheader();writer.writerows(small)
for case in sorted({r['case'] for r in rows}):
    selected=[r for r in rows if r['case']==case]
    pairs=[]
    for pair in sorted({r['pair'] for r in selected}):
        arms={r['keep_packed']:r for r in selected if r['pair']==pair}
        if set(arms)!={False,True}:continue
        keep,drop=arms[True],arms[False]
        pairs.append({'pair':pair,'keep_tok_s':keep['decode_tok_s'],'drop_tok_s':drop['decode_tok_s'],
                      'speed_ratio':drop['decode_tok_s']/keep['decode_tok_s'],
                      'decode_ms_saved':keep['decode_ms']-drop['decode_ms'],
                      'identical':keep['output_sha256']==drop['output_sha256']})
    def spread(values):return {'median':st.median(values),'min':min(values),'max':max(values)} if values else None
    summary['cases'][case]={'complete_pairs':len(pairs),'pairs':pairs,
        'keep_tok_s':spread([p['keep_tok_s'] for p in pairs]),
        'drop_tok_s':spread([p['drop_tok_s'] for p in pairs]),
        'paired_speed_ratio':spread([p['speed_ratio'] for p in pairs]) if eligible else None,
        'positive_pairs':sum(p['speed_ratio']>1 for p in pairs) if eligible else None}
    if not eligible:
        for row in pairs:
            row.pop('speed_ratio',None)
            row.pop('decode_ms_saved',None)
summary['placements']=[{'tag':a['tag'],'given_back':a.get('given_back'),
                         'slots_per_layer':a.get('slots_per_layer'),
                         'placement_lines':a.get('placement_lines')} for a in result['arms']]
diagnostic=OUT/'diagnosis-01/results.json'
if diagnostic.exists():
    d=json.loads(diagnostic.read_text(encoding='utf-8'))
    summary['diagnosis']={k:d.get(k) for k in ['started','finished','passed','error','history_divergence',
                                             'fixed_packed_identity','teacher_forced_metrics']}
    forced=next(r for r in result['rows'] if r.get('pair')==0 and r['case']=='r0-l1024' and r['keep_packed'])['output_ids'][:96]
    summary['diagnosis']['forced_ids']=forced
    summary['diagnosis']['service_restored']=d.get('service_transition',{}).get('health_after',{}).get('loaded')
packed_check=OUT/'packed-logits-01/results.json'
if packed_check.exists():
    d=json.loads(packed_check.read_text(encoding='utf-8'))
    summary['packed_logits']={k:d.get(k) for k in ['started','finished','passed','error','rows','vocab',
        'fixed_slots','source','bitwise_identical','finite','max_absolute_error','top1_equal']}
    summary['packed_logits']['service_restored']=d.get('service_transition',{}).get('health_after',{}).get('loaded')
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:summary[k] for k in ['phase','passed','error','build_passed','gate_passed','cases']},ensure_ascii=False,indent=2))
