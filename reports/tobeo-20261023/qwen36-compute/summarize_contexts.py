"""Summarize only completed, validated smoke reports; retain original per-run evidence."""
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def main():
    records=[]
    for run,case in [('mtp0-application-smoke-01','r0-l1024'),('mtp0-application-smoke-02','r0-l16384')]:
        directory=ROOT/run
        state=json.loads((directory/'service-transition.json').read_text())
        if not state.get('health_after',{}).get('loaded'):
            raise RuntimeError('Service restoration not verified: '+run)
        folder=directory/case
        path=folder/('metrics-base.csv' if (folder/'metrics-base.csv').exists() else 'metrics.csv')
        rows=list(csv.DictReader(path.open(encoding='utf-8')))
        units=next(r for r in rows if not r['ID'])
        kernels=[r for r in rows if r['ID'].isdigit()]
        if len(kernels)!=1:raise RuntimeError('Expected exactly one kernel')
        row=kernels[0]
        for metric,unit in [('gpu__time_duration.sum','ns'),('dram__bytes_op_read.sum','byte'),('dram__bytes_op_write.sum','byte')]:
            if units[metric]!=unit:raise RuntimeError('Re-export base units before summarizing')
        passes=sorted(folder.glob('pass-*/'+case+'-mtp0.json'))
        if not passes:raise RuntimeError('No validated application pass')
        evidence=[json.loads(p.read_text()) for p in passes]
        if not all(p.get('validation_passed') and p['same_output_as_phase_b'] for p in evidence):
            raise RuntimeError('Output validation failed')
        checked=json.loads((folder/'export-check.json').read_text())
        if not checked.get('shape_matches'):raise RuntimeError('Shape validation missing')
        record={'run':run,'case':case,'prompt_tokens':1025 if case=='r0-l1024' else 16385,
                'mtp':0,'cache_control':'all','replay_mode':'application','passes':len(passes),
                'grid':row['Grid Size'],'block':row['Block Size'],
                'duration_us':float(row['gpu__time_duration.sum'].replace(',',''))/1000,
                'dram_read_bytes':int(row['dram__bytes_op_read.sum'].replace(',','')),
                'dram_write_bytes':int(row['dram__bytes_op_write.sum'].replace(',','')),
                'device_l2_bytes':int(row['device__attribute_l2_cache_size'].replace(',','')),
                'generated_tokens':evidence[0]['generated_tokens'],'same_output_as_phase_b':True,
                'output_sha256':evidence[0]['output_sha256'],'prompt_sha256':evidence[0]['prompt_ids_sha256'],
                'exe_sha256':evidence[0]['exe_sha256'],'source_revision':evidence[0]['source_revision'],
                'report_sha256':hashlib.sha256((folder/'attention.ncu-rep').read_bytes()).hexdigest(),
                'daily_model_restored':True}
        records.append(record)
    summary={'date':'2026-10-23','timezone':'Asia/Shanghai','scope':'Two contexts, one selected invocation each; cold-cache diagnostics, not throughput',
             'records':records,'ratios_16k_over_1k':{
                 'duration':records[1]['duration_us']/records[0]['duration_us'],
                 'dram_read':records[1]['dram_read_bytes']/records[0]['dram_read_bytes']},
             'limits':'No repetition distribution or proof of DRAM saturation. L2/L1/occupancy and CPU analysis are separate.'}
    (ROOT/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
