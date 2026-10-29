"""Build a bounded, sanitized evidence directory; never writes to GitHub."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
PUB = OUT / 'publication'
REL = Path('bench/results/2026-10-29-community-rtx5060ti-deepseek41-windows')
DEST = PUB / REL
DEST.mkdir(parents=True, exist_ok=True)
R = OUT / 'execution-03'
record = json.loads((R / 'results.json').read_text(encoding='utf-8'))
summary = json.loads((OUT / 'summary.json').read_text(encoding='utf-8'))
assert record['passed'] and summary['offline_checks_passed']


def sanitize(text):
    replacements = [
        (str(R), '<RUN_DIR>'),
        (str(OUT / 'execution-01'), '<AUTO_RUN_DIR>'),
        (str(OUT / 'execution-02'), '<80GB_RUN_DIR>'),
        ('D:/Models/Strata/deepseek-v4.1-flash-IST-DAS-2.25bpw/maya-ds4', '<PACK_DIR>'),
        ('D:/Models/Strata/engine-dsv41/0.1.52-windows-x86_64-cuda-cuda13', '<ENGINE_DIR>'),
        ('D:/Models/Strata', '<MODEL_DATA>'),
        (str(ROOT), '<CHECKOUT>'),
        ('reports/tobeo-20261022/qwen36-context-curve', '<LOCAL_TELEMETRY_SOURCE>'),
        ('reports/tobeo-20261029/deepseek41-case', '<LOCAL_CASE_SOURCE>'),
    ]
    for before, after in replacements:
        for variant in (before, before.replace('\\', '/'), before.replace('/', '\\')):
            text = text.replace(variant, after)
    return text


def clean(obj):
    if isinstance(obj, str):
        return sanitize(obj)
    if isinstance(obj, list):
        return [clean(x) for x in obj]
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    return obj


def dump(path, obj):
    target = DEST / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(clean(obj), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def textfile(path, text):
    target = DEST / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(sanitize(text), encoding='utf-8')


xml = ET.parse(OUT / 'execution-01/resource-exhaustion-event.xml').getroot()
find = lambda tag: next(e.text for e in xml.iter() if e.tag.split('}')[-1] == tag)
event = {'provider': 'Microsoft-Windows-Resource-Exhaustion-Detector', 'event_id': 2004,
         'timestamp_utc': '2026-10-29T11:23:30.8339925Z',
         'system_commit_limit_bytes': int(find('SystemCommitLimit')),
         'system_commit_charge_bytes': int(find('SystemCommitCharge')),
         'processes_total_commit_charge_bytes': int(find('ProcessCommitCharge')),
         'physical_memory_size_bytes': int(find('PhysicalMemorySize')),
         'reported_physical_memory_usage_bytes': int(find('PhysicalMemoryUsage')),
         'deepseek_process_commit_charge_bytes': 118554161152,
         'deepseek_process': 'strata-dsv41.exe',
         'scope': 'Selected numeric fields from the original Windows event XML; machine, user, IDs and unrelated process details omitted.'}
assert event['system_commit_limit_bytes'] == 145729966080
assert event['system_commit_charge_bytes'] == 145636839424
dump('failure-event-2004.json', event)
dump('environment.json', {'measurement_date': '2026-10-29', 'os': 'Windows 11 10.0.26200',
     'cpu': 'Intel i7-12700, 12 physical / 20 logical cores, DDR4',
     'ram_bytes': 137140031488, 'gpu': record['hardware']['gpu'], 'model_disk': 'ZHITAI TiPro9000 4TB NVMe',
     'python': '3.12.7', 'source_checkout_commit': record['source_revision'],
     'engine': record['engine'], 'pagefile_postflight': {'initial_mib': 4096, 'maximum_mib': 8192,
     'allocated_after_recovery_mib': 4096, 'automatic_managed': False,
     'note': 'Read-only postflight query. Failure event commit limit was 145.730 GB; later runs had a 141.435 GB limit. Do not assume a fixed 4GB allocation throughout.'}})
manifest = json.loads((ROOT / 'reports/tobeo-20261028/deepseek41-community/download-manifest.json').read_text(encoding='utf-8'))
dump('model-files.json', [{k: f[k] for k in ['name', 'repo', 'revision', 'source', 'size', 'sha256']} for f in manifest['files']])
dump('configurations.json', [{'name': 'automatic', 'args': json.loads((OUT/'execution-01/results.json').read_text(encoding='utf-8'))['config']['args']},
     {'name': '80GB', 'args': json.loads((OUT/'execution-02/results.json').read_text(encoding='utf-8'))['config']['args']},
     {'name': '64GB', 'args': record['config']['args']}])
dump('summary.json', {k: v for k, v in summary.items() if k != 'restoration'})
dump('failure-80GB-guard.json', json.loads((OUT/'execution-02/memory-guard-trigger.json').read_text(encoding='utf-8')))
for run, name in [('execution-01', 'automatic'), ('execution-02', '80GB'), ('execution-03', '64GB')]:
    textfile(f'logs/{name}-engine.log', (OUT/run/'engine.log').read_text(encoding='utf-8'))

# Actual per-request archives are authoritative: do not export the mutated messages
# on two aggregate functional rows. Include native HTTP events and original text.
rows = record['functional'] + [record['warmup']] + record['performance'] + record['soak']
requests = []
resource_rows = []
for row in rows:
    response = json.loads((R/f"{row['name']}.response.json").read_text(encoding='utf-8'))
    result = response['result']
    assert result['content'] == row['content'] and result['usage'] == row['usage']
    requests.append(clean({'name': row['name'], 'phase': 'soak' if row['name'].startswith('soak') else
                     'performance' if row['name'].startswith('performance') else 'warmup' if row['name']=='warmup' else 'functional',
                     'request': response['request'], 'response': {k: result.get(k) for k in
                     ['started','finished','usage','timings','finish','first_content_s','first_event_s','elapsed_s','content','reasoning','tool_calls','protocol_passed']},
                     'task_passed': row.get('task_passed'), 'source': f"{row['name']}.response.json", 'events': response['events']}))
    data = json.loads((R/row['resources_file']).read_text(encoding='utf-8'))
    for sample in data['samples']:
        resource_rows.append({'request': row['name'], **sample})
textfile('http-requests.jsonl', ''.join(json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n' for x in requests))
textfile('resources.jsonl', ''.join(json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n' for x in resource_rows))
dump('aggregate-input-notes.json', json.loads((OUT/'evidence-verification.json').read_text(encoding='utf-8'))['aggregate_message_alias_notes'])
shutil.copyfile(OUT/'requests.csv', DEST/'requests.csv')
for name in ('case-results.png','case-results.svg'):
    shutil.copyfile(OUT/name, DEST/name)

source_files = {'source/run_case_recorded.py': OUT/'run_case.py',
                'source/windows_telemetry_recorded.py': ROOT/'reports/tobeo-20261022/qwen36-context-curve/windows_telemetry.py',
                'source/analyze_case_posthoc.py': OUT/'analyze_case.py',
                'source/plot_case_posthoc.py': OUT/'plot_case.py'}
hashes = []
for target, original in source_files.items():
    raw = original.read_bytes()
    textfile(target, raw.decode('utf-8'))
    hashes.append({'published_path': target, 'original_sha256': hashlib.sha256(raw).hexdigest(),
                   'published_sha256': hashlib.sha256((DEST/target).read_bytes()).hexdigest(),
                   'change': 'Only local paths replaced with explicit placeholders; archived source, not a portable GPU runner.'})
assert hashes[0]['original_sha256'] == record['controller_sha256']
dump('source-fingerprints.json', hashes)
textfile('protocol-recorded.md', (OUT/'experiment-plan.md').read_text(encoding='utf-8'))

# Reject paths, identifiers or credentials before any remote mutation.
for path in DEST.rglob('*'):
    if path.is_file() and path.suffix not in ('.png',):
        text = path.read_text(encoding='utf-8-sig')
        assert not re.search(r'(?i)(?:(?<![A-Za-z0-9])[A-Z]:[\\/]|tobeo|lofapeepeebo|S-1-5-18|gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,})', text), f'Private material in {path.name}'
dump('packaging-status.json', {'prepared': True, 'http_requests': len(requests), 'resource_samples':len(resource_rows),
     'all_requests_complete': all(x['response']['protocol_passed'] for x in requests),
     'notes': 'Public evidence derived after the measured runs. Original raw files retained locally; no new GPU measurement.'})
print(json.dumps({'folder':str(DEST),'files':len([p for p in DEST.rglob('*') if p.is_file()]),
                  'bytes':sum(p.stat().st_size for p in DEST.rglob('*') if p.is_file()), 'requests':len(requests),
                  'samples':len(resource_rows)},indent=2))
