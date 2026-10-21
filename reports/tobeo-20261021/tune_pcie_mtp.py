import sys,json,statistics,threading,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
import calibrate as C
import strata_tokenizer as ST
from serve.server import StrataEngine,with_component_engine,child_env
cfg=with_component_engine(json.loads((OUT/'original-config.json').read_text(encoding='utf-8')))
vp=Path(cfg['tokenizer']);v=json.loads((vp/'vocab.json').read_text(encoding='utf-8'));tokens=[None]*len(v)
for t,i in v.items():tokens[i]=t
tok=ST.Tokenizer(tokens,(vp/'merges.txt').read_text(encoding='utf-8').split('\n'),json.loads((vp/'token_type.json').read_text(encoding='utf-8')))
texts=[('code','Write a Python implementation of an LRU cache with get and put, explain its complexity, and give two tests.'),('chinese','请写一篇详细的中文文章，解释 CPU、GPU、内存和 SSD 如何协作运行混合专家大模型，并举出具体例子。')]
ids=[(n,C.chat_ids(tok,t)) for n,t in texts]
report={'prompts':texts,'affinity':'p-cores','max_new_screen':128,'rounds':3,'screen':{},'confirmation':[]}
def save(): (OUT/'pcie-mtp-tuning.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
def evaluate(e,pcie='auto',mp=0.5,n=128):
    tune={'spec_min_p':mp}
    if pcie!='auto':tune['pcie_frac']=pcie
    rows=[]
    for name,prompt in ids:
        ts=[t for t in e.generate(prompt,n,{'temperature':0,'strata_checkpoint':False,'strata_tune':tune},threading.Event()) if t is not None]
        last=dict(e.last or {});ms=last.get('decode_ms') or 0
        if len(ts)<9 or ms<=0:raise RuntimeError('invalid sample: '+str(last))
        rows.append({'prompt':name,'tokens':len(ts),'rate':len(ts)*1000/ms,'last':last,'output_sha256':hashlib.sha256(json.dumps(ts).encode()).hexdigest()})
    return {'pcie':pcie,'spec_min_p':mp,'rows':rows,'score':statistics.geometric_mean(x['rate'] for x in rows)}
args=C.with_arg(C.engine_args(cfg),'--pool-affinity','p-cores')
e=StrataEngine(cfg['exe'],args,cwd=cfg.get('cwd'),log=str(OUT/'pcie-mtp-engine.log'),env=child_env(cfg))
try:
    report['engine_info']=dict(e.info)
    for _ in range(2):evaluate(e,n=96)
    vals=['auto',0.0,0.3,0.55,1.0];pcie={str(v):[] for v in vals}
    for rnd in range(3):
        for val in (vals if rnd%2==0 else vals[::-1]):
            row=evaluate(e,pcie=val);pcie[str(val)].append(row);print('PCIE',rnd+1,val,round(row['score'],2),flush=True)
            report['screen']['pcie']=pcie;save()
    best=max(vals,key=lambda v:statistics.median(x['score'] for x in pcie[str(v)]))
    if statistics.median(x['score'] for x in pcie[str(best)])<statistics.median(x['score'] for x in pcie['auto'])*1.03:best='auto'
    floors=[0.3,0.5,0.7];minp={str(v):[] for v in floors}
    for rnd in range(3):
        for floor in (floors if rnd%2==0 else floors[::-1]):
            row=evaluate(e,pcie=best,mp=floor);minp[str(floor)].append(row);print('MINP',rnd+1,floor,round(row['score'],2),flush=True)
            report['screen']['min_p']=minp;save()
    floor=max(floors,key=lambda v:statistics.median(x['score'] for x in minp[str(v)]))
    if statistics.median(x['score'] for x in minp[str(floor)])<statistics.median(x['score'] for x in minp['0.5'])*1.03:floor=0.5
    report['candidate']={'pcie':best,'spec_min_p':floor};save()
    if best!='auto' or floor!=0.5:
        for rnd in range(3):
            pair={}
            for mode in (['default','candidate'] if rnd%2==0 else ['candidate','default']):
                pair[mode]=evaluate(e,pcie=best if mode=='candidate' else 'auto',mp=floor if mode=='candidate' else 0.5,n=256)
            report['confirmation'].append(pair);save()
            print('CONFIRM',rnd+1,round(pair['default']['score'],2),round(pair['candidate']['score'],2),flush=True)
        gains=[p['candidate']['score']/p['default']['score']-1 for p in report['confirmation']]
        accepted=min(gains)>0 and statistics.median(gains)>0.03
    else:gains=[];accepted=False
    report['accepted']=accepted;report['paired_gains']=gains;save()
    print('TUNE_RESULT',json.dumps({'candidate':report['candidate'],'accepted':accepted,'paired_gains':gains}),flush=True)
finally:e.close()
