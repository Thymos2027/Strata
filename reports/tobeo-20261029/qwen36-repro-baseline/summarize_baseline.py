"""Recheck archived evidence without sending any new model requests."""
import argparse
import json
from pathlib import Path
import re
import sys

from build_baseline import OUT, REPO, SOURCE, BUILD, REVISION, digest, git, save, stamp


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', default='validation-01')
    args = parser.parse_args()
    if not re.fullmatch(r'validation-[0-9]+', args.run_id):
        parser.error('Expected validation-NN')
    run = OUT / args.run_id
    record = json.loads((run / 'results.json').read_text(encoding='utf-8'))
    build = json.loads((OUT / 'build-results.json').read_text(encoding='utf-8'))
    assert build['passed'] and record['passed'] and record['finished'] and record['phase'] == 'complete'
    assert digest(OUT / 'build-results.json') == record['build_results_sha256']
    assert record['script_sha256'] == digest(OUT / 'validate_baseline.py')
    assert record['protocol_helper_sha256'] == digest(REPO / 'reports/tobeo-20261022/qwen36-context-curve/run_curve.py')
    assert record['correctness_helper_sha256'] == digest(REPO / 'reports/tobeo-20261021/qwen36-source-baseline/run_correctness.py')
    assert build['compiler_helper_sha256'] == digest(REPO / 'reports/tobeo-20261022/windows-native-baseline/build_native.py')
    assert record['harness_sha256'] == digest(SOURCE / 'tools/qwen35/q36_harness.py')
    if 'finalizer_sha256' in build:
        assert build['finalizer_sha256'] == digest(OUT / 'build_baseline.py')
        assert build['script_sha256'] == digest(OUT / 'build-attempt-02.py')
    else:
        assert build['script_sha256'] == digest(OUT / 'build_baseline.py')
    assert build['plan_sha256'] == record['plan_sha256'] == digest(OUT / 'experiment-plan.md')
    assert all(row['exit_code'] == 0 for row in build['commands'])
    assert len(build['commands']) == 4
    ctest = (OUT / 'build-2.log').read_text(encoding='utf-8', errors='replace')
    assert '100% tests passed, 0 tests failed out of 17' in ctest
    assert 'no work to do' in (OUT / 'build-3.log').read_text()
    assert git('rev-parse', 'HEAD', cwd=SOURCE) == REVISION
    assert not git('status', '--porcelain', '--untracked-files=no', cwd=SOURCE)
    for name, sha in build['binaries'].items():
        assert digest(BUILD / name) == sha
    for name, sha in build['build_files'].items():
        assert digest(BUILD / name) == sha
    assert digest(OUT / 'ggml-files.json') == build['ggml']['files_manifest_sha256']
    ggml = Path(build['ggml']['source'])
    dependency_files = json.loads((OUT / 'ggml-files.json').read_text())
    assert all(digest(ggml / name) == sha for name, sha in dependency_files.items())
    fixed = record['fixed_correctness']
    assert fixed['prompts_sha256'] == digest(SOURCE / 'tools/qwen35/parity_prompts.ids')
    assert fixed['passed'] and fixed['verify_completed'] and not fixed['verify_mismatch_lines']
    assert len(fixed['runs']) == 4 and len(fixed['comparisons']) == 3
    names = ['old-nograph-mtp0', 'verify-nograph-mtp0', 'graph-mtp0', 'graph-mtp2']
    groups = [json.loads((run / 'fixed' / (name + '.json')).read_text())['tokens'] for name in names]
    assert all(len(tokens) == 10 for tokens in groups) and all(tokens == groups[0] for tokens in groups[1:])
    mtp_text = (run / 'fixed/graph-mtp2.console.log').read_text(errors='replace')
    mtp_done = re.findall(r'DONE \d+ \d+ [0-9.]+ [0-9.]+ \w+ (\d+) (\d+)', mtp_text)
    assert len(mtp_done) == 10 and sum(int(offered) for _, offered in mtp_done) > 0
    for name in names:
        log = (run / 'fixed' / (name + '.engine.log')).read_text(errors='replace')
        assert re.findall(r'hybrid experts: (\d+) of 256 per layer', log) == ['64']
        replacements = re.findall(r'(\d+) slot replacements', log)
        assert replacements and not any(int(n) for n in replacements)
    verify_text = (run / 'fixed/verify-nograph-mtp0.engine.log').read_text(errors='replace')
    counts = re.findall(r'VERIFY: (\d+) comparisons, (\d+) mismatches', verify_text)
    assert counts and all(int(n) > 0 and int(bad) == 0 for n, bad in counts)
    bandwidths = {}
    for name in ['bandwidth-before', 'bandwidth-after']:
        lines = (run / (name + '.log')).read_text().splitlines()
        raw = next(json.loads(line) for line in lines if '"test":"pinned_H2D"' in line)
        assert raw['event_GBps'] == record[name]['h2d_GBps'] >= 15 and record[name]['exit_code'] == 0
        bandwidths[name] = record[name]['h2d_GBps']
    assert len(record['rows']) == 4 and len(record['arms']) == 2
    sys.path.insert(0, str(REPO / 'reports/tobeo-20261022/qwen36-context-curve'))
    import run_curve as protocol
    for case, fixture in record['fixtures'].items():
        path = run / (case + '.ids.json')
        assert digest(path) == fixture['archived_file_sha256']
        ids = json.loads(path.read_text())
        assert len(ids) == fixture['tokens'] and protocol.tokens_hash(ids) == fixture['tokens_sha256']
    for row in record['rows']:
        assert row['protocol_passed'] and row['matches_first_repeat']
        assert len(row['output_ids']) == row['generated_tokens'] == 64
        assert protocol.tokens_hash(row['output_ids']) == row['output_sha256']
        assert row['draft_offered'] == row['reused_tokens'] == 0
    for case in ['r0-l1024', 'r0-l16384']:
        rows = [row for row in record['rows'] if row['case'] == case]
        assert len(rows) == 2 and rows[0]['output_ids'] == rows[1]['output_ids']
    for arm in record['arms']:
        text = (run / arm['log']).read_text(errors='replace')
        slots = [int(n) for n in re.findall(r'hybrid experts: (\d+) of 256 per layer', text)]
        assert slots == arm['slots'] == record['arms'][0]['slots']
        assert arm['chunks'] == [2048] and arm['exit_code'] == 0
        assert arm['slot_replacements'] and not any(arm['slot_replacements'])
        assert 'strata_kq.dll' in text and 'prompt experts on MMQ' in text
        assert arm['warmup']['generated_tokens'] == 64
    assert not record['restore_errors'] and record['health_after']['loaded']
    assert record['health_after']['model'] == record['health_before']['model']
    assert record['daily_config_sha256_before'] == record['daily_config_sha256_after']
    machine = json.loads((OUT / 'environment.json').read_text(encoding='utf-8-sig'))
    summary = {
        'date': '2026-10-29', 'verified_at': stamp(), 'passed': True, 'revision': REVISION,
        'engine_version': build['engine_version'], 'gpu': record['hardware'].split(',')[0],
        'machine': machine, 'source_tree': build['source_tree'],
        'toolchain_versions': {k: v for k, v in build['toolchain'].items() if k.endswith('_version')},
        'model': {k: v for k, v in build['model'].items() if k != 'path'},
        'ggml_revision': build['ggml']['revision'], 'ggml_archive_sha256': build['ggml']['sha256'],
        'ggml_files': len(dependency_files), 'binaries': build['binaries'],
        'selected_host_tests_passed': 17, 'full_ctest': False, 'source_clean': True,
        'verify_comparisons': sum(int(n) for n, _ in counts), 'verify_mismatches': 0,
        'mtp2_drafts_accepted': sum(int(accepted) for accepted, _ in mtp_done),
        'mtp2_drafts_offered': sum(int(offered) for _, offered in mtp_done),
        'parity_prompts_per_arm': [len(group) for group in groups],
        'reference_token_lengths': [len(tokens) for tokens in groups[0]],
        'configuration': record['configuration'], 'actual_slots': record['arms'][0]['slots'],
        'repeatability': [{k: row[k] for k in ['label', 'case', 'prompt_tokens', 'generated_tokens', 'output_sha256', 'matches_first_repeat']} for row in record['rows']],
        'bandwidth': bandwidths, 'daily_model_restored': record['health_after']['model'],
        'daily_config_unchanged': True, 'restore_errors': [], 'validation_finished': record['finished'],
        'run_id': args.run_id, 'profiler': False,
        'limits': ['Windows/CUDA only', 'hybrid graphs disabled', 'frozen expert placement',
                   'no optimization speed claim', 'no normal-condition profiling or bottleneck conclusion',
                   'no full quality, concurrency, long-run or HTTP evaluation', 'no bit-identical rebuild claim'],
    }
    # The local manifest preserves raw evidence; the small summary is suitable for the repo.
    files = {p.relative_to(OUT).as_posix(): digest(p) for p in sorted(OUT.rglob('*'))
             if p.is_file() and '__pycache__' not in p.parts and p.name not in ['summary.json', 'evidence-manifest.json', 'README.md']}
    save(OUT / 'evidence-manifest.json', files)
    summary['local_evidence_files'] = len(files)
    summary['evidence_manifest_sha256'] = digest(OUT / 'evidence-manifest.json')
    save(OUT / 'summary.json', summary)
    print(json.dumps({'passed': True, 'evidence_files': len(files), 'verify_comparisons': summary['verify_comparisons'],
                      'actual_slots': summary['actual_slots'], 'bandwidth': bandwidths}), flush=True)


if __name__ == '__main__':
    main()
