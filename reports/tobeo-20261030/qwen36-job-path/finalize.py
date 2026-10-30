"""Verify completed ordinal-based job paths and keep original experiments immutable."""
import csv,json,sys
from pathlib import Path
import numpy as np
from build_complete import OUT,SOURCE,BUILD,host,digest,save,stamp,BASE_BUILD
from run_validation import audit_processes


def main():
    r=json.loads((OUT/'capture-02/results.json').read_text(encoding='utf-8'))
    b=json.loads((OUT/'build-complete.json').read_text(encoding='utf-8'))
    paths=json.loads((OUT/'critical-path.json').read_text(encoding='utf-8'))
    assert b['passed'] and r['passed'] and r['finished'] and not r['restore_errors']
    assert r['script_sha256']==digest(OUT/'capture_complete.py')
    assert r['plan_sha256']==b['plan_sha256']==digest(OUT/'completion-plan.md')
    assert r['build_results_sha256']==digest(OUT/'build-complete.json')
    assert '100% tests passed, 0 tests failed out of 17' in (OUT/'build-complete-2.log').read_text(encoding='utf-8')
    assert 'no work to do' in (OUT/'build-complete-3.log').read_text(encoding='utf-8')
    assert all(digest(SOURCE/k)==v for k,v in b['source_hashes'].items())
    assert all(digest(BUILD/k)==v for k,v in b['binaries'].items())
    assert len(r['numeric'])==4 and len(r['requests'])==8
    original=json.loads((OUT.parent/'qwen36-copy3905/execution-02/results.json').read_text(encoding='utf-8'))
    for row in r['numeric']:
        file=OUT/'capture-02'/('numeric-'+row['case']+'-'+row['arm']+'.f32')
        reference=next(x for x in original['numeric'] if x['case']==row['case'] and x['arm']=='baseline')
        assert file.stat().st_size==row['bytes']==64*248320*4
        assert digest(file)==row['sha256']==reference['sha256']
        assert np.isfinite(np.memmap(file,dtype=np.float32,mode='r')).all()
    observations={}
    for name in ['r0-l1024','r0-l16384']:
        observations[name]={}
        for arm in ['baseline','off','on','trace']:
            tag=name+'-'+('on-trace' if arm=='trace' else arm+'-plain')
            row=json.loads((OUT/'capture-02'/(tag+'.json')).read_text(encoding='utf-8'))
            reference=next(x for x in original['rows'] if x['case']==name and x['pair'] is None)
            assert row['passed'] and row['exit_code']==0 and row['output_ids']==reference['output_ids']
            assert row['layout']['slots']==[63] and row['layout']['chunks']==[2048] and not any(row['layout']['slot_replacements'])
            observations[name][arm]={k:row[k] for k in ['prompt_ms','decode_ms','output_sha256']}
        for mode,a,z in [('build_off_over_baseline','off','baseline'),('marks_on_over_off','on','off'),('trace_over_marks_on','trace','on')]:
            observations[name][mode]={m:observations[name][a][m]/observations[name][z][m] for m in ['prompt_ms','decode_ms']}
    phases=list(csv.DictReader((OUT/'phase-ledger.csv').open(encoding='utf-8')))
    tokens=list(csv.DictReader((OUT/'token-ledger.csv').open(encoding='utf-8')))
    assert len(tokens)==126 and len(phases)==sum(x['all_request_phases'] for x in paths['cases'])
    for phase in phases:
        assert int(phase['last_release_ordinal'])==int(phase['tasks'])
        assert sum(int(phase[k]) for k in ['pre_publish_ns','critical_chain_job_body_ns','critical_chain_handoff_and_queue_ns','phase_tail_ns'])==int(phase['wall_ns'])
        assert sum(int(phase[k]) for k in ['critical_chain_startup_ns','critical_chain_between_jobs_ns','last_completion_publication_gap_ns'])==int(phase['critical_chain_handoff_and_queue_ns'])
    for token in tokens:
        assert sum(int(token[k]) for k in ['gpu_submit_ns','route_wait_ns','phase_pre_publish_ns','critical_branch_job_body_ns','critical_branch_queue_handoff_ns','phase_tail_ns','CPU_moe_other_ns','token_other_ns'])==int(token['wall_ns'])
    assert all(c['all_completion_ordinals_unique_and_tasks_matched'] and c['all_phase_fork_joins_close'] and c['all_token_ledgers_close'] for c in paths['cases'])
    # Both v1 and the original fixed baseline remain intact after the completion refinement.
    from build_diag import SOURCE as FIRST_SOURCE,BUILD as FIRST_BUILD
    first=json.loads((OUT/'build-results.json').read_text(encoding='utf-8'))
    assert all(digest(FIRST_SOURCE/k)==v for k,v in first['source_hashes'].items())
    assert all(digest(FIRST_BUILD/k)==v for k,v in first['binaries'].items())
    for dirname in ['qwen36-copy3905','qwen36-cpu-mechanism']:
        root=OUT.parent/dirname;manifest=json.loads((root/'evidence-manifest.json').read_text(encoding='utf-8'))
        assert all(digest(root/k)==v for k,v in manifest.items())
    host.check_identity()
    old_model=json.loads((OUT.parent/'qwen36-copy3905/build-results.json').read_text(encoding='utf-8'))['model']
    assert digest(host.MODEL)==old_model['sha256']
    health=host.api('/health');assert health['loaded'] and health['model']==r['health_before']['model']
    assert digest(host.CONFIG)==r['config_sha256_before']==r['config_sha256_after']
    assert not [p for p in audit_processes() if (p['name'] or '').lower() in ['strata-q36.exe','nsys.exe','nsys-launcher.exe','nvcc.exe','ninja.exe']]
    summary={'date':'2026-10-30','verified_at':stamp(),'passed':True,'base_revision':'46c152a1310f77cd2f0ce2c7cd213962df14fe83',
             'controlled_job_dependency_path_complete':True,'phase_and_token_wall_ledgers_complete':True,
             'uninstrumented_whole_system_root_cause_complete':False,'source_instrumentation_only':True,
             'cases':paths['cases'],'observations':observations,'new_complete_numeric_dumps':4,'new_complete_measured_requests':8,
             'diagnostic_build_selected_tests':17,'original_baseline_and_first_diagnostic_unchanged':True,
             'model':old_model,'diagnostic_source_hashes':b['source_hashes'],'diagnostic_binaries':b['binaries'],
             'bandwidth':{k:r[k]['h2d_GBps'] for k in ['bandwidth-before','bandwidth-after']},
             'service_restored_at':r['finished'],'health':health,'daily_config_unchanged':True,'restore_errors':[],
             'new_evidence_published':False,'default_changed':False,'limits':paths['limits']}
    files={p.relative_to(OUT).as_posix():digest(p) for p in sorted(OUT.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name not in ['summary.json','README.md','evidence-manifest.json']}
    save(OUT/'evidence-manifest.json',files)
    summary['evidence_files']=len(files);summary['manifest_sha256']=digest(OUT/'evidence-manifest.json')
    save(OUT/'summary.json',summary)
    print(json.dumps({k:summary[k] for k in ['passed','controlled_job_dependency_path_complete','new_complete_measured_requests','evidence_files','service_restored_at']}),flush=True)


if __name__=='__main__':main()
