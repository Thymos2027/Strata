import json,time,threading,hashlib,statistics,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
import calibrate as C
import strata_tokenizer as ST
from serve.server import StrataEngine,with_component_engine,child_env
OUT=Path(__file__).resolve().parent
cfg=with_component_engine(json.loads((OUT/'original-config.json').read_text(encoding='utf-8')))
tpath=Path(cfg['tokenizer']);v=json.loads((tpath/'vocab.json').read_text(encoding='utf-8'));tokens=[None]*len(v)
for t,i in v.items():tokens[i]=t
tok=ST.Tokenizer(tokens,(tpath/'merges.txt').read_text(encoding='utf-8').split('\n'),json.loads((tpath/'token_type.json').read_text(encoding='utf-8')))
texts=[('code','Write a Python implementation of an LRU cache with get and put, explain its complexity, and give two tests.'),('story','Write a detailed story about a lighthouse keeper who receives a letter from the future. Keep writing until the story reaches its conclusion.'),('chinese','请写一篇详细的中文文章，解释 CPU、GPU、内存和 SSD 如何协作运行混合专家大模型，并举出具体例子。')]
ids=[(name,C.chat_ids(tok,text)) for name,text in texts]
warm=C.chat_ids(tok,'Explain how a refrigerator moves heat from inside to outside.')
results={'method':'three alternating fresh-engine pairs; --expert-cache 4000 fixes a byte budget, resolved by this pack to 4302 actual slots in both arms; warm-up 96 tokens; three prompts at 256 max tokens, greedy; timings exclude model loading','prompts':texts,'pairs':[]}
def sample(e,name,ids,max_new=256,tune=None):
    sampling={'temperature':0,'strata_checkpoint':False}
    if tune:sampling['strata_tune']=tune
    out=[t for t in e.generate(ids,max_new,sampling,threading.Event()) if t is not None]
    last=dict(e.last or {})
    ms=last.get('decode_ms') or 0
    return {'name':name,'prompt_tokens':len(ids),'output_tokens':len(out),'decode_tok_s':len(out)*1000/ms if ms else 0,'timings':last,'output_sha256':hashlib.sha256(json.dumps(out).encode()).hexdigest(),'output_ids':out}
for rnd in range(3):
    pair={}
    order=['default','p-cores'] if rnd%2==0 else ['p-cores','default']
    for mode in order:
        args=C.with_arg(C.engine_args(cfg),'--expert-cache','4000')
        if mode=='p-cores':args=C.with_arg(args,'--pool-affinity','p-cores')
        print(f'PAIR {rnd+1}: starting {mode}, cache argument 4000 (4302 actual slots with this pack)',flush=True)
        e=StrataEngine(cfg['exe'],args,cwd=cfg.get('cwd'),log=str(OUT/f'confirm-{rnd+1}-{mode}.log'),env=child_env(cfg))
        try:
            sample(e,'warm-up',warm,96)
            rows=[sample(e,name,prompt) for name,prompt in ids]
            pair[mode]={'engine_info':dict(e.info),'rows':rows}
            print(mode,[(x['name'],round(x['decode_tok_s'],2),x['output_tokens']) for x in rows],flush=True)
        finally:e.close()
    results['pairs'].append(pair)
    (OUT/'affinity-confirmation.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    gains=[pair['p-cores']['rows'][i]['decode_tok_s']/pair['default']['rows'][i]['decode_tok_s']-1 for i in range(len(ids))]
    print('PAIR GAINS', [round(g*100,2) for g in gains],flush=True)
summary={}
for i,(name,_) in enumerate(ids):
    base=[p['default']['rows'][i]['decode_tok_s'] for p in results['pairs']]
    alt=[p['p-cores']['rows'][i]['decode_tok_s'] for p in results['pairs']]
    summary[name]={'default':base,'p-cores':alt,'median_ratio':statistics.median(alt)/statistics.median(base),'same_tokens_per_pair':[p['default']['rows'][i]['output_sha256']==p['p-cores']['rows'][i]['output_sha256'] for p in results['pairs']]}
results['summary']=summary
(OUT/'affinity-confirmation.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print('SUMMARY',json.dumps(summary,ensure_ascii=False),flush=True)
