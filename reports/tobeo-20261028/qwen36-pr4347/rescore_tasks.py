"""Score archived raw answers after removing the protocol's final EOS marker.

No model rerun or answer rewrite. Keep the original results.json and judgments.
"""
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
RUN = OUT / 'validation-next/run-01'


def main():
    report = json.loads((RUN / 'results.json').read_text(encoding='utf-8'))
    assert report['phase'] == 'complete' and report.get('finished'), 'Wait for restoration'
    manifest = {t['name']: t for t in json.loads((RUN / 'task-manifest.json').read_text(encoding='utf-8'))}
    source = ast.parse((OUT / 'validate_next.py').read_text(encoding='utf-8'))
    judge_node = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == 'judge')
    namespace = dict(re=re, subprocess=subprocess, sys=sys, OUT=OUT, json=json)
    exec(compile(ast.Module(body=[judge_node], type_ignores=[]), 'archived-task-judge', 'exec'), namespace)
    stripped = 0
    for rows in report['tasks'].values():
        for row in rows:
            if row['output'].endswith('<|im_end|>'):
                assert row['output_ids'][-1] == 248046 and row['finish'] == 'stop'
                stripped += 1
            row['original_judgment'] = row['judgment']
            row['judgment'] = namespace['judge'](manifest[row['name']], row['output'])
    report['scoring_correction'] = {
        'reason': 'GEN emits EOS token 248046 before reporting stop; tokenizer renders it as <|im_end|>.',
        'method': 'Remove exactly this terminal protocol marker before judging; retain all raw answers and original judgments.',
        'answers_normalized': stripped,
        'original': 'results.json',
    }
    report['task_passed'] = len(report['tasks']) == 4 and all(
        len(rows) == 12 and all(r['judgment']['passed'] for r in rows)
        for rows in report['tasks'].values())
    report['passed'] = report['numeric_passed'] and report['task_passed'] and report['service_transition']['health_after']['loaded']
    (RUN / 'results-rescored.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'arms': {
        name: {'passed': sum(r['judgment']['passed'] for r in rows),
               'failures': [r['name'] for r in rows if not r['judgment']['passed']]}
        for name, rows in report['tasks'].items()}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
