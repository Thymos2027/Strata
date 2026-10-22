"""Select matched k_attn_part launch ordinals from the validated Systems traces."""
import hashlib
import json
from pathlib import Path
import sqlite3

OUT = Path(__file__).resolve().parent
TRACES = OUT.parent/'qwen36-profiling/cuda133-process'
BASE = OUT.parent/'qwen36-context-curve'


def main():
    cases = []
    for case in ('r0-l1024','r0-l16384'):
        tag = case+'-mtp0'
        connection = sqlite3.connect(TRACES/(tag+'.sqlite'))
        request_start = connection.execute("select start from NVTX_EVENTS where text='request'").fetchone()[0]
        start,end = connection.execute("select start,end from NVTX_EVENTS where text='decode-after-first-token'").fetchone()
        columns = ['start','end','gridX','gridY','gridZ','blockX','blockY','blockZ','registersPerThread']
        kernels = [dict(zip(columns,row)) for row in connection.execute(
            'select '+','.join('k.'+c for c in columns)+
            ' from CUPTI_ACTIVITY_KIND_KERNEL k join StringIds s on s.id=k.shortName'
            ' where s.value=? order by k.start',('k_attn_part',))]
        threshold_index = next(i for i,r in enumerate(kernels) if r['start'] >= start+200_000_000)
        cases.append({'case':case, 'tag':tag,'kernels':kernels,'threshold_index':threshold_index,
                      'decode_start_ns':start,'decode_end_ns':end,
                      'first_measured_request_ordinal':next(i for i,r in enumerate(kernels) if r['start']>=request_start)})
        connection.close()
    # Use the same filtered ordinal for both contexts. Round forward to a group
    # boundary; each main forward has ten full-attention layer launches here.
    skip = ((max(c['threshold_index'] for c in cases)+9)//10)*10
    result = {'method':'same zero-based filtered launch ordinal, at least 200 ms inside both decode ranges',
              'kernel_name':'k_attn_part','kernel_name_base':'function','mtp':0,
              'launch_skip':skip,'launch_count':1,'cases':[]}
    reference = json.loads((BASE/'results.json').read_text())
    for c in cases:
        row = c['kernels'][skip]
        if not c['decode_start_ns']+200_000_000 <= row['start'] < row['end'] <= c['decode_end_ns']:
            raise RuntimeError('Selection is outside steady decode: '+c['case'])
        if [row[x] for x in ('gridY','gridZ','blockX','blockY','blockZ')] != [16,1,256,1,1]:
            raise RuntimeError('Unexpected single-query launch shape')
        ref = next(r for r in reference['rows'] if r['case']==c['case'] and r['mtp']==0)
        with (TRACES/(c['tag']+'.nsys-rep')).open('rb') as file:
            report_hash = hashlib.file_digest(file,'sha256').hexdigest()
        result['cases'].append({k:v for k,v in c.items() if k not in ('kernels','threshold_index')} |
            {'selected':row,'prompt_ids_sha256':ref['prompt_ids_sha256'],
             'reference_report_sha256':report_hash,'matching_kernel_count':len(c['kernels'])})
    if len({c['first_measured_request_ordinal'] for c in result['cases']}) != 1:
        raise RuntimeError('Warm-up launch count differs between contexts')
    (OUT/'kernel-selection.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
