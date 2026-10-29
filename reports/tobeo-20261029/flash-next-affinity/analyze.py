"""Summarize only observed affinity policy runs; never turn partial gates into speed claims."""
import csv
import hashlib
import json
from pathlib import Path
from statistics import median

OUT=Path(__file__).resolve().parent
r=json.loads((OUT/'performance-04/results.json').read_text(encoding='utf-8'))
assert r.get('finished'),'Wait for service/download restoration'


def spread(x):return {'median':median(x),'min':min(x),'max':max(x)}


def file_label(filename):
    path=Path(filename);args=r['resolved_config']['args']
    for flag,label in [('--pack','pack'),('--mtp','mtp')]:
        root=Path(args[args.index(flag)+1])
        if path.is_relative_to(root):return label+'/'+path.relative_to(root).as_posix()
    if path==Path(r['resolved_config']['exe']):return 'engine/'+path.name
    return path.name


paired=[];summaries={}
if r['passed']:
    assert len(r['rows'])==45 and len([a for a in r['arms'] if a['formal']])==15
    for name in ['code','english','chinese']:
        for n in range(5):
            rows={v['mode']:v for v in r['rows'] if v['name']==name and v['round']==n}
            assert set(rows)=={'all','p-cores','measure'}
            row={'workload':name,'round':n}
            for metric in ['request_ms','decode_ms','prompt_ms']:
                values={mode:(v[metric] if metric=='request_ms' else v['timings'][metric]) for mode,v in rows.items()}
                for mode,value in values.items():row[mode+'_'+metric]=value
                row[metric+'_all_over_P']=values['all']/values['p-cores']
                row[metric+'_all_over_measure']=values['all']/values['measure']
                row[metric+'_P_over_measure']=values['p-cores']/values['measure']
            arm=next(a for a in r['arms'] if a['formal'] and a['round']==n and a['mode']=='measure')
            row['measure_selected']=arm['actual_mode'];paired.append(row)
        selected=[v for v in paired if v['workload']==name];summary={}
        for metric in ['request_ms','decode_ms','prompt_ms']:
            modes={mode:spread([v[mode+'_'+metric] for v in selected]) for mode in ['all','p-cores','measure']}
            ratios=spread([v[metric+'_all_over_P'] for v in selected])
            drift=max((modes[mode]['max']-modes[mode]['min'])/modes[mode]['median'] for mode in ['all','p-cores'])
            summary[metric]={'modes':modes,'paired_all_over_P':ratios,
                             'P_faster_pairs':sum(v[metric+'_all_over_P']>1 for v in selected),
                             'paired_all_over_measure':spread([v[metric+'_all_over_measure'] for v in selected]),
                             'paired_P_over_measure':spread([v[metric+'_P_over_measure'] for v in selected]),
                             'largest_observed_mode_relative_range':drift}
        cpu_modes={mode:spread([v['process_cpu_s'] for v in r['rows'] if v['name']==name and v['mode']==mode]) for mode in ['all','p-cores','measure']}
        cpu_ratios=[]
        for n in range(5):
            rows={v['mode']:v for v in r['rows'] if v['name']==name and v['round']==n}
            cpu_ratios.append(rows['p-cores']['process_cpu_s']/rows['all']['process_cpu_s'])
        summary['process_cpu_s']={'modes':cpu_modes,'paired_P_over_all':spread(cpu_ratios),
                                 'P_lower_CPU_pairs':sum(v<1 for v in cpu_ratios)}
        summaries[name]=summary
    with (OUT/'paired-results.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(paired[0]));writer.writeheader();writer.writerows(paired)


def public_row(v):
    t=v['timings'];resources=v.get('resources') or {}
    return {'name':v['name'],'mode':v.get('mode'),'round':v.get('round'),'tag':v.get('tag'),
            'prompt_tokens':v['prompt_tokens'],'output_tokens':len(v['output_ids']),
            'output_sha256':v['output_sha256'],'output_ids':v['output_ids'],'timings':t,
            'request_ms':v['request_ms'],'client_first_token_s':v['client_first_token_s'],
            'client_total_s':v['client_total_s'],'process_cpu_s':v['process_cpu_s'],
            'protocol_passed':v['protocol_passed'],'identical':v.get('identical'),'draft_counts_identical':v.get('draft_counts_identical'),
            'task_passed':v.get('task_passed'),'output':v.get('output'),
            'resources':{k:value for k,value in resources.items() if k!='samples'}}


summary={'started':r['started'],'finished':r['finished'],'passed':r['passed'],'phase':r['phase'],
         'analyzer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
         'error':r.get('error'),'plan_sha256':r.get('plan_sha256'),'runner_sha256':r.get('runner_sha256'),
         'workloads_sha256':r.get('workloads_sha256'),'helpers_sha256':r.get('helpers_sha256'),
         'gate_reference_sha256':r.get('gate_reference_sha256'),'engine_version':'0.1.52',
         'file_fingerprints':{file_label(p):v for p,v in r['fingerprints'].items()},'fingerprint_reuse_from':r.get('fingerprint_reuse_from'),
         'fixed_cache':r.get('fixed_cache'),'gate_passed':r.get('gate_passed',False),
         'gate':{mode:{key:[public_row(v) for v in rows] for key,rows in block.items()} for mode,block in r['gate'].items()},
         'arms':[{k:v for k,v in arm.items() if k not in ['args','thread_affinities','warmup']} for arm in r['arms']],
         'rows':[public_row(v) for v in r['rows']],'summaries':summaries,'paired':paired,
         'bandwidth_before':r.get('bandwidth-before'),'bandwidth_after':r.get('bandwidth-after'),
         'bandwidth_relative_drift':r.get('bandwidth_relative_drift'),
         'download_processes_suspended':len(r['downloads_suspended']),
         'download_processes_stopped':len(r.get('downloads_stopped',[])),
         'download_quiet_checks':r.get('download_quiet_checks',[]),
         'downloads_restored':bool(r.get('download_restarted')) if r.get('downloads_stopped') else bool(r.get('download_resumption')) and all(x.get('resumed') or x.get('exited') for x in r.get('download_resumption',[])),
         'daily_restored_loaded':r['service_transition'].get('health_after',{}).get('loaded'),
         'daily_config_unchanged':r.get('daily_config_sha256_before')==r.get('daily_config_sha256_after'),
         'restore_errors':r.get('restore_errors',[]),
         'limits':['Controlled spec4/min-p0/lookup0/suffix0/pcie0.55/cache2400/prefill1024/conversation0, not daily defaults.',
                   'Prompt CPU share and route-tail skipping disabled; default worker counts remain policy-dependent.',
                   'Five restart rounds do not prove general selection correctness or a critical-path cause.',
                   'Windows/CUDA/single hardware and native protocol only; no upstream publication this round.']}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'passed':summary['passed'],'phase':summary['phase'],'error':summary['error'],
                  'fixed_cache':summary['fixed_cache'],'summaries':summaries},ensure_ascii=False,indent=2))
