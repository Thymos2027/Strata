"""Verify raw evidence and retain all pairs, including losses and gate stops."""
import argparse,csv,json,statistics,sqlite3,sys
from collections import defaultdict
from pathlib import Path
import numpy as np
from build_slice import OUT,BASE_BUILD,BUILD,SOURCE,digest,save,stamp


def trace_evidence():
    directory=OUT/'traces-01'
    path=directory/'results.json'
    if not path.exists():return None
    record=json.loads(path.read_text(encoding='utf-8'))
    assert record['passed'] and record['finished'] and not record['restore_errors']
    assert record['health_after']['loaded'] and record['config_sha256_before']==record['config_sha256_after']
    assert record['script_sha256']==digest(OUT/'trace_copy.py')
    assert record['performance_evidence_sha256']==digest(OUT/'execution-02/results.json')
    sys.path.insert(0,str(OUT.parent/'qwen36-systems'))
    from analyze_systems import phase,pid
    rows=[]
    for arm in ['off','on']:
        measured=json.loads((directory/(arm+'.json')).read_text(encoding='utf-8'))
        assert measured['passed'] and measured['script_sha256']==record['script_sha256']
        db=sqlite3.connect(directory/(arm+'.sqlite'));db.row_factory=sqlite3.Row
        try:
            assert {pid(x[0]) for x in db.execute('select distinct globalPid from CUPTI_ACTIVITY_KIND_KERNEL')}=={measured['engine_pid']}
            for name in ['request','prefill-to-first-token','decode-after-first-token']:
                windows=db.execute('select start,end from NVTX_EVENTS where text=?',(name,)).fetchall()
                assert len(windows)==1 and windows[0]['end'] is not None
            info,raw=phase(db,'prefill-to-first-token',measured['engine_pid'])
            decode,_=phase(db,'decode-after-first-token',measured['engine_pid'])
            kinds={row['name']:row['id'] for row in db.execute('select * from ENUM_CUDA_MEMCPY_OPER')}
            host_kind,device_kind=kinds['CUDA_MEMCPY_KIND_HTOD'],kinds['CUDA_MEMCPY_KIND_DTOD']
            h2d=info['copies']['Host-to-Device']['bytes_in_intersecting_records']
            d2d=info['copies'].get('Device-to-Device',{}).get('bytes_in_intersecting_records',0)
            stream_bytes={}
            for kind,label in [(host_kind,'HtoD'),(device_kind,'DtoD')]:
                totals=defaultdict(int)
                for row in raw['copies']:
                    if row['copyKind']==kind:totals[row['streamId']]+=row['bytes']
                stream_bytes[label]=dict(sorted(totals.items()))
            diagnostics=[dict(row) for row in db.execute('select * from DIAGNOSTIC_EVENT')]
            warnings=[row for row in diagnostics if row['severity']>=2]
            errors=[row for row in diagnostics if row['severity']==3 or any(w in row['text'].lower() for w in ['events lost','dropped','overflow'])]
            engine_cuda=[row for row in warnings if pid(row['globalPid'])==measured['engine_pid'] and 'CUDA' in row['text']]
            assert not errors and not engine_cuda and not any('not supported by this build' in row['text'] for row in warnings)
            rows.append({'arm':arm,'prefill':info,'decode':decode,'HtoD_bytes':h2d,'DtoD_bytes':d2d,
                         'copy_bytes_by_stream':stream_bytes,
                         'output_sha256':measured['output_sha256'],'diagnostic_warnings':warnings})
        finally:db.close()
    a,b=rows
    # Check bulk staging streams; small activation/input copies can share the compute stream.
    hb,db=b['copy_bytes_by_stream']['HtoD'],b['copy_bytes_by_stream']['DtoD']
    hs,ds=max(hb,key=hb.get),max(db,key=db.get)
    checks={'same_output':a['output_sha256']==b['output_sha256'],
            'HtoD_reduced':b['HtoD_bytes']<a['HtoD_bytes']*.95,
            'DtoD_added':b['DtoD_bytes']>a['DtoD_bytes']+2**30,
            'total_copy_bytes_close':abs((b['HtoD_bytes']+b['DtoD_bytes'])/(a['HtoD_bytes']+a['DtoD_bytes'])-1)<.01,
            'bulk_staging_copy_bytes_equal':max(a['copy_bytes_by_stream']['HtoD'].values())==hb[hs]+db[ds],
            'bulk_DtoD_on_own_stream':hs!=ds and hb[hs]>.9*b['HtoD_bytes'] and db[ds]>.9*b['DtoD_bytes']}
    assert all(checks.values()),checks
    return {'checks':checks,'reports':rows,'service_restored_at':record['finished'],
            'bandwidth':{k:record[k]['h2d_GBps'] for k in ['bandwidth-before','bandwidth-after']}}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run-id',default='execution-02');a=parser.parse_args()
    run=OUT/a.run_id
    r=json.loads((run/'results.json').read_text(encoding='utf-8'))
    b=json.loads((OUT/'build-results.json').read_text(encoding='utf-8'))
    assert b['passed'] and r['finished'] and not r['restore_errors']
    assert r['health_after']['loaded'] and r['daily_config_sha256_before']==r['daily_config_sha256_after']
    assert r['script_sha256']==digest(OUT/'run_validation.py')
    assert b.get('metadata_fix_script_sha256',b['script_sha256'])==digest(OUT/'build_slice.py')
    if 'metadata_fix_script_sha256' in b:assert b['script_sha256']==digest(OUT/'build-script-01.snapshot')
    assert r['plan_sha256']==b['plan_sha256']==digest(OUT/'experiment-plan.md')
    assert r['build_results_sha256']==digest(OUT/'build-results.json')
    assert digest(OUT/'candidate.patch')==b['candidate_patch_sha256']
    assert digest(SOURCE/'src/qwen35/q36_engine.cu')==b['engine_file_sha256']
    assert all(digest(BASE_BUILD/name)==sha for name,sha in b['baseline_binaries_before'].items())
    assert all(digest(BUILD/name)==sha for name,sha in b['binaries'].items())
    assert '100% tests passed, 0 tests failed out of 17' in (OUT/'build-2.log').read_text(encoding='utf-8',errors='replace')
    assert 'no work to do' in (OUT/'build-3.log').read_text(encoding='utf-8',errors='replace')
    for arm in b['adapters'].values():
        assert digest(arm['exe'])==arm['sha256']
        assert digest(Path(arm['exe']).parent/'strata_kq.dll')==arm['dll_sha256']
        assert all(digest(p)==sha for p,sha in arm['libraries'].items())
    numeric=[]
    for row in r['numeric']:
        path=run/(row['case']+'-'+row['arm']+'.f32')
        item={key:row[key] for key in ['case','arm','exit_code','layout']}
        if path.exists():
            data=np.memmap(path,dtype=np.float32,mode='r')
            item.update(bytes=path.stat().st_size,sha256=digest(path),finite=bool(np.isfinite(data).all()))
            if 'sha256' in row:assert item['sha256']==row['sha256']
        numeric.append(item)
    pairs=r.get('pairs',[])
    verified_pairs=[]
    for pair in pairs:
        a=next(row for row in r['rows'] if row.get('pair')==pair['pair'] and row['case']==pair['case'] and row['arm']=='off')
        z=next(row for row in r['rows'] if row.get('pair')==pair['pair'] and row['case']==pair['case'] and row['arm']=='on')
        assert a['passed'] and z['passed'] and a['output_ids']==z['output_ids']
        assert pair['prefill_ratio']==a['prompt_ms']/z['prompt_ms']
        assert pair['decode_ratio']==a['decode_ms']/z['decode_ms']
        assert pair['total_ratio']==(a['prompt_ms']+a['decode_ms'])/(z['prompt_ms']+z['decode_ms'])
        verified_pairs.append(pair)
    if r['passed']:
        assert len(numeric)==6 and len(verified_pairs)==10 and len(r['rows'])==24
        for case in ['r0-l1024','r0-l16384']:
            rows=[row for row in numeric if row['case']==case]
            assert all(row['bytes']==64*248320*4 and row['finite'] for row in rows)
            assert len({row['sha256'] for row in rows})==1
    stats={}
    for case in ['r0-l1024','r0-l16384']:
        rows=[pair for pair in verified_pairs if pair['case']==case]
        if not rows:continue
        stats[case]={'pairs':len(rows)}
        for metric,field in [('prefill','prefill_ratio'),('decode','decode_ratio'),('total','total_ratio')]:
            values=[row[field] for row in rows]
            stats[case][metric]={'ratio_median':statistics.median(values),'range':[min(values),max(values)],'B_faster':sum(v>1 for v in values)}
    summary={'date':'2026-10-30','verified_at':stamp(),'evidence_verified':True,'execution_passed':r['passed'],
             'revision':b['baseline'],'slice_commit':b['slice_commit'],'author':'xyehya','pull_request':3905,
             'candidate_patch_sha256':b['candidate_patch_sha256'],'selected_host_tests':17,
             'numeric':numeric,'free_generation_gate_rows':sum(row['pair'] is None and bool(row.get('passed')) for row in r['rows']),
             'formal_requests':sum(row['pair'] is not None for row in r['rows']),
             'statistics':stats,'signals':r.get('signals'),'trace_required':r.get('trace_required'),
             'bandwidth':{key:r[key]['h2d_GBps'] for key in ['bandwidth-before','bandwidth-after'] if key in r},
             'service_restored_at':r['finished'],'daily_config_unchanged':True,'restore_errors':[],
             'error':r.get('error'),'default_changed':False,
             'limits':['attributed slice, not the complete PR3905','one Windows/CUDA machine and pinned Q4 model',
                       'fixed 63-slot placement, chunk2048, MTP0, 64 output tokens',
                       'no HIP/SYCL build, full quality, dynamic placement or long-run claim']}
    if verified_pairs:
        with (OUT/'pairs.csv').open('w',newline='',encoding='utf-8') as file:
            writer=csv.DictWriter(file,fieldnames=list(verified_pairs[0]));writer.writeheader();writer.writerows(verified_pairs)
    trace=trace_evidence()
    summary['trace_evidence']=trace
    summary['experiment_complete']=bool(r['passed'] and (not r.get('trace_required') or trace))
    failed_path=OUT/'execution-01/results.json'
    if failed_path.exists() and run.name!='execution-01':
        failed=json.loads(failed_path.read_text(encoding='utf-8'))
        assert not failed['passed'] and failed['health_after']['loaded'] and not failed['restore_errors'] and not failed['rows']
        summary['initial_attempt']={'reason':'adapter DLL not adjacent; native prompt fallback failed output gate',
                                    'formal_requests':0,'restored_at':failed['finished']}
    save(OUT/'summary.json',summary)
    snapshot=json.loads((OUT/'upstream-snapshot.json').read_text(encoding='utf-8'))
    public={'date':snapshot['date'],'queries':[{'kind':q['kind'],'query':q['query'],
            'matches':[{'title':x['title'],'url':x['url']} for x in q['response'].get('issues',[])]} for q in snapshot['queries']],
            'pulls':{number:{'title':p['metadata']['title'],'state':p['metadata']['state'],'merged_at':p['metadata']['merged_at'],
                             'head':p['metadata']['head']['sha'],'base':p['metadata']['base']['sha'],'author':p['metadata']['user']['login'],
                             'comments':len(p['comments'])} for number,p in snapshot['pulls'].items()}}
    save(OUT/'upstream-summary.json',public)
    files={p.relative_to(OUT).as_posix():digest(p) for p in sorted(OUT.rglob('*')) if p.is_file() and '__pycache__' not in p.parts
           and p.name not in ['summary.json','README.md','evidence-manifest.json']}
    save(OUT/'evidence-manifest.json',files)
    summary['local_evidence_files']=len(files);summary['manifest_sha256']=digest(OUT/'evidence-manifest.json')
    save(OUT/'summary.json',summary)
    print(json.dumps({'execution_passed':r['passed'],'statistics':stats,'trace_required':r.get('trace_required'),'evidence_files':len(files)}),flush=True)


if __name__=='__main__':main()
