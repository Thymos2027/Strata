"""Bind actual capture, analyses, source identities and final service state."""
import csv,json,sys
from pathlib import Path
from capture import OUT,host,BASE_BUILD,BUILD,digest,save,stamp,audit_processes


def main():
    r=json.loads((OUT/'capture-01/results.json').read_text(encoding='utf-8'))
    cpu=json.loads((OUT/'cpu-summary.json').read_text(encoding='utf-8'))
    mechanism=json.loads((OUT/'mechanism-summary.json').read_text(encoding='utf-8'))
    b=json.loads((OUT.parent/'qwen36-copy3905/build-results.json').read_text(encoding='utf-8'))
    assert r['passed'] and r['finished'] and not r['restore_errors']
    assert r['script_sha256']==digest(OUT/'capture.py') and r['plan_sha256']==digest(OUT/'experiment-plan.md')
    host.check_identity()
    assert all(digest(Path(name))==value for name,value in r['binaries'].items())
    candidate=host.SOURCE.parent/'src-copy3905-af08278c/src/qwen35/q36_engine.cu'
    assert digest(candidate)==b['engine_file_sha256']
    assert digest(host.MODEL)==b['model']['sha256']
    for cell in cpu['cells']:
        assert cell['periodic_leaf_samples']==r[cell['tag']+'-cpu']['periodic_samples']
        assert cell['unresolved_engine_samples']==0 and len(cell['pool_worker_tids'])==7
        assert sum(cell['leaf_classes'].values())==cell['periodic_leaf_samples']
    rows=list(csv.DictReader((OUT/'mechanism-stages.csv').open(encoding='utf-8')))
    assert len(rows)==320 and mechanism['all_320_dependency_chains_checked']
    assert all(int(x['A_HtoD_bytes'])==int(x['B_HtoD_bytes'])+int(x['B_DtoD_bytes']) for x in rows)
    health=host.api('/health');assert health['loaded'] and health['model']==r['health_before']['model']
    assert digest(host.CONFIG)==r['config_sha256_before']==r['config_sha256_after']
    assert not [p for p in audit_processes() if (p['name'] or '').lower() in ['strata-q36.exe','nsys.exe','nsys-launcher.exe','nvcc.exe','ninja.exe']]
    summary={'date':'2026-10-30','verified_at':stamp(),'passed':True,'baseline_revision':b['baseline'],
             'slice_commit':b['slice_commit'],'source_unchanged':True,'model':b['model'],
             'binaries':{label:{name:digest(folder/name) for name in ['strata-q36.exe','strata_kq.dll','strata-q36.pdb']} for label,folder in [('baseline',BASE_BUILD),('copy_candidate',BUILD)]},
             'cpu_preflight':r['cpu_preflight'],'measured_requests':6,'cpu_traces':3,
             'periodic_leaf_samples':{x['tag']:x['periodic_leaf_samples'] for x in cpu['cells']},
             'per_stage_conservation_and_dependencies':320,'bandwidth':{k:r[k]['h2d_GBps'] for k in ['bandwidth-before','bandwidth-after']},
             'service_restored_at':r['finished'],'health':health,'daily_config_unchanged':True,'restore_errors':[],
             'cpu_ip_and_scheduling_complete':True,'full_causal_critical_path_complete':False,
             'additional_evidence_published':False,'new_engine_build':False,'default_changed':False,
             'limits':cpu['limits']+mechanism['limits']}
    files={p.relative_to(OUT).as_posix():digest(p) for p in sorted(OUT.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name not in ['summary.json','README.md','evidence-manifest.json']}
    save(OUT/'evidence-manifest.json',files)
    summary['evidence_files']=len(files);summary['manifest_sha256']=digest(OUT/'evidence-manifest.json')
    save(OUT/'summary.json',summary)
    print(json.dumps({k:summary[k] for k in ['passed','measured_requests','cpu_traces','periodic_leaf_samples','evidence_files','service_restored_at','full_causal_critical_path_complete']}),flush=True)


if __name__=='__main__':main()
