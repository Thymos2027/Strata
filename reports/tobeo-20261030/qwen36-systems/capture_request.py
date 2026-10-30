"""One unchanged-engine request, with identical NVTX instrumentation in both modes."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

import psutil
from common import (OUT, BASE, BUILD, FIXTURES, MODEL, REVISION, Eng, protocol, environment,
                    arguments, layout, check_identity, digest, save, stamp, api)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', action='store_true')
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--case', choices=['r0-l1024', 'r0-l16384'])
    parser.add_argument('--chunk', type=int, choices=[2048, 4096], default=2048)
    parser.add_argument('--profiler', action='store_true')
    args = parser.parse_args()
    from torch.cuda.nvtx import range_push, range_pop
    if args.probe:
        range_push('preflight-range')
        time.sleep(0.05)
        range_pop()
        print('NVTX preflight complete', flush=True)
        return
    if not args.case:
        parser.error('--case is required')
    directory = args.directory.resolve()
    tag = f'c{args.chunk}-{args.case}-' + ('trace' if args.profiler else 'plain')
    destination = directory / (tag + '.json')
    if destination.exists():
        raise RuntimeError('Request evidence exists; do not overwrite')
    ref = check_identity()
    if api('/health').get('loaded'):
        raise RuntimeError('Daily model still loaded')
    for name in list(os.environ):
        if name.upper().startswith(('STRATA_', 'DS4_')):
            del os.environ[name]
    os.environ.update(environment())
    record = {'tag': tag, 'started': stamp(), 'passed': False, 'profiler': args.profiler,
              'chunk': args.chunk, 'case': args.case, 'revision': REVISION,
              'binaries': ref['binaries'], 'sampling': protocol.KEYS,
              'configuration': arguments(args.chunk), 'script_sha256': digest(__file__)}
    engine = None
    log = directory / (tag + '.engine.log')
    try:
        print('Loading', tag, flush=True)
        engine = Eng(str(BUILD / 'strata-q36.exe'), arguments(args.chunk), env=environment(), log=str(log))
        record.update(engine_pid=engine.p.pid, load_s=engine.load_s, ready=engine.ready)
        warm_ids = json.loads((FIXTURES / 'r1-l1024.ids.json').read_text())
        record['warmup'] = protocol.measured_request(engine, warm_ids, 64)
        ids = json.loads((FIXTURES / (args.case + '.ids.json')).read_text())
        record['prompt_tokens'] = len(ids)
        record['prompt_sha256'] = protocol.tokens_hash(ids)
        record['fixture_sha256'] = digest(FIXTURES / (args.case + '.ids.json'))
        output = []
        process = psutil.Process(engine.p.pid)
        before = process.cpu_times()
        range_push('request')
        try:
            range_push('prefill-to-first-token')
            try:
                started = time.perf_counter()
                first = None
                engine.send('GEN 64 ' + protocol.KEYS + ' ' + ','.join(map(str, ids)))
                while True:
                    line = engine.line(300)
                    if line is None or line.startswith('ERR'):
                        raise RuntimeError('Engine failed: ' + str(line))
                    if line.startswith('T '):
                        if first is None:
                            first = time.perf_counter()
                            range_pop()
                            range_push('decode-after-first-token')
                        output.append(int(line.split()[1]))
                    elif line.startswith('DONE '):
                        done = line
                        break
            finally:
                range_pop()
        finally:
            range_pop()
        ended = time.perf_counter()
        after = process.cpu_times()
        fields = done.split()
        record.update(done=done, output_ids=output, output_sha256=protocol.tokens_hash(output),
                      prompt_ms=float(fields[3]), decode_ms=float(fields[4]),
                      client_ttft_s=first-started if first else None, client_total_s=ended-started,
                      process_cpu_s=after.user+after.system-before.user-before.system,
                      process_rss_bytes=process.memory_info().rss)
        record['validation'] = {'counts': len(output) == int(fields[1]) == 64 and int(fields[2]) == len(ids),
                                'fresh': int(fields[8]) == 0 and int(fields[14]) == len(ids),
                                'mtp_off': int(fields[6]) == int(fields[7]) == 0, 'finish': fields[5] == 'length'}
        if args.profiler:
            plain = json.loads((directory / tag.replace('-trace', '-plain')).with_suffix('.json').read_text(encoding='utf-8'))
            record['validation']['same_chunk_plain_output'] = plain['passed'] and output == plain['output_ids']
        if args.chunk == 2048:
            expected = next(row['output_sha256'] for row in ref['repeatability'] if row['case'] == args.case)
            record['validation']['baseline_output'] = record['output_sha256'] == expected
        if not all(record['validation'].values()):
            raise RuntimeError('Request validation failed: ' + repr(record['validation']))
        record['passed'] = True
    except BaseException as exc:
        record['error'] = repr(exc)
        raise
    finally:
        if engine:
            engine.close()
            if engine.p.poll() is None:
                engine.p.kill()
                engine.p.wait(timeout=30)
            record['engine_exit_code'] = engine.p.returncode
        if log.exists():
            record['layout'] = layout(log)
            actual = record['layout']
            if (actual['chunks'] != [args.chunk] or len(actual['slots']) != 1 or not actual['slot_replacements']
                    or any(actual['slot_replacements']) or record.get('engine_exit_code') != 0):
                record['passed'] = False
                record['layout_error'] = 'Actual layout/exit differs from protocol'
        record['finished'] = stamp()
        save(destination, record)
        print(json.dumps({'tag': tag, 'passed': record['passed'], 'layout': record.get('layout')}), flush=True)
    if not record['passed']:
        raise RuntimeError('Request not accepted')


if __name__ == '__main__':
    main()
