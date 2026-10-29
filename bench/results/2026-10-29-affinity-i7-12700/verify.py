"""Offline evidence consistency check; written after measurement. No GPU run."""
import csv,hashlib,json,re
from pathlib import Path
from statistics import median
p=Path(__file__).resolve().parent
for name,info in json.loads((p/'manifest.json').read_text(encoding='utf-8')).items():
    assert hashlib.sha256((p/name).read_bytes()).hexdigest()==info['sha256'],name
s=json.loads((p/'summary.json').read_text(encoding='utf-8'));assert s['passed'] and len(s['rows'])==45
rows=s['rows'];pairs=list(csv.DictReader((p/'paired-results.csv').open()))
assert len(pairs)==15
for x in rows:
    assert x['protocol_passed'] and x['identical'] and x['draft_counts_identical']
    assert len(x['output_ids'])==256 and x['timings']['drafts_offered']>0
    assert hashlib.sha256(json.dumps(x['output_ids'],separators=(',',':')).encode()).hexdigest()==x['output_sha256']
for a in s['arms']:
    text=(p/'logs'/(a['tag']+'.log')).read_text(encoding='utf-8')
    assert 'expert cache 3107 slots' in text and '--ple-io ram chosen' in text
    timed=re.findall(r'prompt (\d+) tokens = 0 reused \+ \d+ read in (\d+) ms.*?, (\d+) generated in (\d+) ms.*?drafts accepted (\d+) of (\d+)',text)[1:]
    selected=[x for x in rows if x['tag']==a['tag']];assert len(timed)==len(selected)==3
    for logged,x in zip(timed,selected):
        pt,pm,gt,dm,accepted,offered=map(int,logged);t=x['timings']
        assert pt==x['prompt_tokens'] and gt==256 and abs(pm-t['prompt_ms'])<=1 and abs(dm-t['decode_ms'])<=1
        assert accepted==t['drafts_accepted'] and offered==t['drafts_offered']
for name in ['code','english','chinese']:
    ratios=[]
    for n in range(5):
        a={x['mode']:x for x in rows if x['name']==name and x['round']==n}
        v=a['all']['request_ms']/a['p-cores']['request_ms'];ratios.append(v)
        pair=next(x for x in pairs if x['workload']==name and int(x['round'])==n)
        assert abs(float(pair['request_ms_all_over_P'])-v)<1e-12
    assert abs(median(ratios)-s['summaries'][name]['request_ms']['paired_all_over_P']['median'])<1e-12
print('PASS: artifact hashes, 45 output identities, 15 logs, and 15 primary paired ratios')
