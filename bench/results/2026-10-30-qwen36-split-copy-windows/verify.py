"""Offline consistency check written after measurement; never runs a model."""
import csv,hashlib,json,re
from pathlib import Path
from statistics import median

P=Path(__file__).resolve().parent


def read(name):return json.loads((P/name).read_text(encoding='utf-8'))
def token_hash(ids):return hashlib.sha256(json.dumps(ids,separators=(',',':')).encode()).hexdigest()


def main():
    for name,info in read('manifest.json').items():
        data=(P/name).read_bytes()
        assert len(data)==info['bytes'] and hashlib.sha256(data).hexdigest()==info['sha256'],name
    r=read('results.json');stats=read('statistics.json');trace=read('trace-summary.json')
    assert r['passed'] and len(r['numeric'])==6 and len(r['rows'])==24 and len(r['pairs'])==10
    for case,fixture in r['fixtures'].items():
        ids=read(case+'.ids.json');assert len(ids)==fixture['tokens'] and token_hash(ids)==fixture['sha256']
    for case in ['r0-l1024','r0-l16384']:
        numeric=[x for x in r['numeric'] if x['case']==case]
        assert {x['arm'] for x in numeric}=={'baseline','off','on'}
        assert len({x['sha256'] for x in numeric})==1
        assert all(x['finite'] and x['bytes']==64*248320*4 and x['exit_code']==0 for x in numeric)
        reference=next(x['output_ids'] for x in r['rows'] if x['case']==case and x['pair'] is None)
        assert all(x['output_ids']==reference for x in numeric)
        for row in [x for x in r['rows'] if x['case']==case]:
            assert row['passed'] and row['exit_code']==0 and row['generated_tokens']==64
            assert row['output_ids']==reference and token_hash(row['output_ids'])==row['output_sha256']
            assert row['draft_accepted']==row['draft_offered']==row['reused_tokens']==0
            assert row['fresh_tokens']==row['prompt_tokens']==r['fixtures'][case]['tokens']
            assert row['layout']['slots']==[63] and row['layout']['chunks']==[2048] and not any(row['layout']['slot_replacements'])
            text=(P/'logs'/(row['tag']+'.engine.log')).read_text(encoding='utf-8')
            assert 'prompt experts on MMQ (int8)' in text
            timed=re.findall(r'prompt (\d+) tokens = 0 reused \+ \d+ read in (\d+) ms.*?, (\d+) generated in (\d+) ms.*?drafts accepted (\d+) of (\d+)',text)
            assert len(timed)==2
            pt,pm,gt,dm,accepted,offered=map(int,timed[-1])
            assert pt==row['prompt_tokens'] and gt==64 and accepted==offered==0
            assert abs(pm-row['prompt_ms'])<=1 and abs(dm-row['decode_ms'])<=1
    csvrows=list(csv.DictReader((P/'pairs.csv').open(encoding='utf-8')))
    assert len(csvrows)==10
    for pair in r['pairs']:
        rows={x['arm']:x for x in r['rows'] if x['case']==pair['case'] and x['pair']==pair['pair']}
        a,b=rows['off'],rows['on']
        values={'prefill':a['prompt_ms']/b['prompt_ms'],'decode':a['decode_ms']/b['decode_ms'],
                'total':(a['prompt_ms']+a['decode_ms'])/(b['prompt_ms']+b['decode_ms'])}
        csvrow=next(x for x in csvrows if x['case']==pair['case'] and int(x['pair'])==pair['pair'])
        for metric,value in values.items():assert value==pair[metric+'_ratio']==float(csvrow[metric+'_ratio'])
    for case in stats:
        for metric in ['prefill','decode','total']:
            values=[x[metric+'_ratio'] for x in r['pairs'] if x['case']==case]
            assert stats[case][metric]=={'ratio_median':median(values),'range':[min(values),max(values)],'B_faster':sum(v>1 for v in values)}
    assert all(trace['checks'].values())
    a,b=trace['reports'];assert a['output_sha256']==b['output_sha256']
    assert max(a['copy_bytes_by_stream']['HtoD'].values())==max(b['copy_bytes_by_stream']['HtoD'].values())+max(b['copy_bytes_by_stream']['DtoD'].values())
    failed=read('failed-attempt.json');assert not failed['passed'] and failed['formal_rows']==[]
    print('PASS: hashes; three inputs; six numeric summaries; 24 outputs/layouts/logs; ten pairs; trace byte conservation; excluded failed attempt')


if __name__=='__main__':main()
