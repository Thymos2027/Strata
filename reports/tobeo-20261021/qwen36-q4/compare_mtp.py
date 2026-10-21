"""Three alternating fresh-engine pairs; fixed 32K context, 7 workers, expert budget.

Decode timings exclude loading and prefill. This is a speed/identity experiment,
not a model quality evaluation. No HTTP server is needed during this comparison.
"""
import hashlib
import json
import statistics
import sys
import threading
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))
import calibrate as C
import strata_tokenizer as ST
from serve.server import StrataEngine, child_env, with_component_engine


def main():
    cfg = with_component_engine(json.loads((OUT / 'baseline-config.json').read_text(encoding='utf-8')))
    tok = ST.Tokenizer.from_gguf(cfg['args'][1])
    prompts = [
        ('code', 'Write a Python implementation of an LRU cache with get and put, explain its complexity, and give two tests.'),
        ('chinese', '请写一篇详细的中文文章，解释 CPU、GPU、内存和 SSD 如何协作运行混合专家大模型，并举出具体例子。')]
    ids = [(name, C.chat_ids(tok, text)) for name, text in prompts]
    warm = C.chat_ids(tok, 'Explain how a refrigerator moves heat from inside to outside.')
    report = {'method': __doc__, 'prompts': prompts, 'pairs': []}
    def sample(e, name, prompt, n=256):
        output = [t for t in e.generate(prompt, n, {'temperature': 0, 'strata_checkpoint': False}, threading.Event()) if t is not None]
        timing = dict(e.last or {})
        ms = timing.get('decode_ms', 0)
        return {'name': name, 'output_tokens': len(output), 'tok_s': len(output) * 1000 / ms if ms else 0,
                'timings': timing, 'sha256': hashlib.sha256(json.dumps(output).encode()).hexdigest(),
                'output_ids': output, 'text': tok.decode(output)}
    for pair_index in range(3):
        pair = {}
        for mtp in ([0, 2] if pair_index % 2 == 0 else [2, 0]):
            print(f'PAIR {pair_index+1}: MTP {mtp}', flush=True)
            e = StrataEngine(cfg['exe'], C.with_arg(C.engine_args(cfg), '--mtp', str(mtp)),
                             cwd=cfg.get('cwd'), env=child_env(cfg),
                             log=str(OUT / f'mtp-{pair_index+1}-{mtp}.log'))
            try:
                sample(e, 'warmup', warm, 64)
                rows = [sample(e, name, prompt) for name, prompt in ids]
                pair[str(mtp)] = {'info': dict(e.info), 'rows': rows}
                if pair_index == 0 and mtp == 2:
                    quality = [sample(e, 'arithmetic', C.chat_ids(tok, '17+25 等于多少？只输出数字。'), 32),
                               sample(e, 'chinese_smoke', C.chat_ids(tok, '请用一句中文说明你已经正常运行。'), 96)]
                    report['functional_checks'] = quality
                    report['functional_pass'] = {
                        'arithmetic': quality[0]['text'].removesuffix('<|im_end|>').strip() == '42',
                        'chinese': any('\u4e00' <= c <= '\u9fff' for c in quality[1]['text'])}
                print(json.dumps({'mtp': mtp, 'rates': [round(r['tok_s'], 2) for r in rows]}, ensure_ascii=False), flush=True)
            finally:
                e.close()
        report['pairs'].append(pair)
        (OUT / 'mtp-comparison.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    report['summary'] = {}
    for i, (name, _) in enumerate(prompts):
        off = [p['0']['rows'][i]['tok_s'] for p in report['pairs']]
        on = [p['2']['rows'][i]['tok_s'] for p in report['pairs']]
        report['summary'][name] = {'mtp0': off, 'mtp2': on,
            'median_ratio': statistics.median(on) / statistics.median(off),
            'paired_gains': [b/a-1 for a,b in zip(off,on)],
            'same_output': [p['0']['rows'][i]['sha256'] == p['2']['rows'][i]['sha256'] for p in report['pairs']]}
    (OUT / 'mtp-comparison.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report['summary'], ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
