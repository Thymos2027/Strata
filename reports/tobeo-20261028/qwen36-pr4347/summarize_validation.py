"""Export small, reproducible results without machine paths or full-logit dumps."""
import json
from pathlib import Path
from build_pair import MAIN, CANDIDATE, digest

OUT = Path(__file__).resolve().parent
RUN = OUT / 'validation-next/run-01'
r = json.loads((RUN / 'results-rescored.json').read_text(encoding='utf-8'))
adapter = json.loads((OUT / 'validation-next/adapter-build.json').read_text(encoding='utf-8'))
manifest = json.loads((RUN / 'task-manifest.json').read_text(encoding='utf-8'))
summary = {
    'started': r['started'], 'finished': r['finished'], 'passed': r['passed'],
    'main': MAIN, 'candidate': CANDIDATE,
    'scope': 'Windows CUDA sm_120, Qwen3.6 UD-Q4_K_XL, fixed residency, context32768/chunk2048/workers7/MTP0/greedy/FP32 KV',
    'arms': {'A': 'candidate packed on, KEEP_PACKED=1, auto63',
             'B': 'candidate packed on, default drop, auto89',
             'C': 'main packed off, explicit63', 'D': 'main packed off, explicit89'},
    'model_sha256_previously_verified': '55983c5a75a1ab969824077b3bb3de4146e82a9234072b48ad4e8f92ad3fe9f1',
    'file_adapter': {
        'engine_sources_modified': adapter['engine_sources_modified'],
        'arms': {k: {'sha256': v['sha256'], 'original_exe_unchanged': v['original_exe_unchanged'],
                     'libraries_sha256': {Path(p).name: sha for p, sha in v['libraries'].items()}}
                 for k, v in adapter['arms'].items()},
        'archived_original_logit_check': r['adapter_check'],
    },
    'controls': r['controls'], 'numeric': r['numeric'],
    'numeric_runs': [{k: v for k, v in row.items()} for row in r['runs']],
    'numeric_passed': r['numeric_passed'], 'task_passed': r['task_passed'],
    'task_manifest': manifest,
    'tasks': {k: [{'name': row['name'], 'prompt_tokens': row['prompt_tokens'],
                  'output': row['output'], 'generated_tokens': row['generated_tokens'],
                  'finish': row['finish'], 'reused_tokens': row['reused_tokens'],
                  'judgment': row['judgment']} for row in rows] for k, rows in r['tasks'].items()},
    'scoring_correction': r['scoring_correction'],
    'downloads_paused': r['downloads_paused'],
    'daily_service_restored_loaded': r['service_transition']['health_after']['loaded'],
    'performance_claim': None,
    'limits': ['12 tasks per arm is a small regression suite, not broad quality equivalence.',
               'Fixed residency does not validate dynamic cache histories.',
               'No new performance pairing, profiling, concurrency or other backends.'],
    'scripts_sha256': {p.name: digest(p) for p in OUT.iterdir() if p.suffix in ('.py', '.cpp')},
}
(OUT / 'validation-next-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'passed': summary['passed'], 'tasks': {
    k: sum(t['judgment']['passed'] for t in rows) for k, rows in summary['tasks'].items()}}))
