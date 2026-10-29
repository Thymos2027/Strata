"""Export scientific plots of the measured case; no interpolation across workloads."""
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import statistics

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parent
RUN = OUT / 'execution-03'
r = json.loads((RUN / 'results.json').read_text(encoding='utf-8'))
assert r['passed'] and r.get('restore_errors') == []
fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
colors = {1024: '#2266aa', 4096: '#d47422'}
for index, target in enumerate((1024, 4096)):
    rows = [row for row in r['performance'] if row['target_tokens'] == target]
    for ax, key in ((axes[0, 0], 'first_content_s'), (axes[0, 1], 'elapsed_s')):
        values = [row[key] for row in rows]
        ax.scatter([index - .06, index, index + .06], values, color=colors[target], zorder=3)
        ax.hlines(statistics.median(values), index - .2, index + .2, color=colors[target], linewidth=2)
        ax.set_xticks([0, 1], ['1K input', '4K input'])
        ax.set_ylabel('Seconds'); ax.grid(axis='y', alpha=.25)
axes[0, 0].set_title('First content event: three requests per length')
axes[0, 1].set_title('Complete HTTP request: 256-token budget')
start = datetime.fromisoformat(r['soak_started'])
groups = defaultdict(list)
for row in r['soak']:
    language = 'zh' if row['index'] % 4 < 2 else 'en'
    groups[(row['target_tokens'], language)].append(row)
for (target, language), rows in groups.items():
    minutes = [(datetime.fromisoformat(row['started']) - start).total_seconds() / 60 for row in rows]
    axes[1, 0].plot(minutes, [row['timings']['predicted_per_second'] for row in rows],
                    marker='o' if language == 'en' else 's', linestyle='-' if language == 'en' else '--',
                    color=colors[target], markersize=3, label=f'{target} body tokens, {language}')
axes[1, 0].set(xlabel='Minutes since continuous requests began', ylabel='Engine decode tokens/s',
                 title='Continuous requests: compare within each series')
axes[1, 0].legend(fontsize=8); axes[1, 0].grid(alpha=.25)
samples = []
for row in r['soak']:
    samples += json.loads((RUN / row['resources_file']).read_text(encoding='utf-8'))['samples']
times = [(datetime.fromisoformat(s['timestamp']) - start).total_seconds() / 60 for s in samples]
for field, label in [('rss_bytes', 'Engine RSS'), ('private_bytes', 'Engine private'),
                     ('system_committed_bytes', 'System commit'), ('system_commit_limit_bytes', 'Commit limit')]:
    axes[1, 1].plot(times, [s[field] / 1024**3 if s.get(field) else float('nan') for s in samples],
                    linewidth=1, label=label)
axes[1, 1].set(xlabel='Minutes since continuous requests began', ylabel='GiB',
                 title='0.5-second RAM/commit samples')
axes[1, 1].legend(fontsize=8); axes[1, 1].grid(alpha=.25)
fig.suptitle('DeepSeek V4.1 Flash IST-DAS 2.25bpw | Windows / RTX 5060 Ti 16GB / 128GB RAM\n'
             '8K context, six experts, 64GB RAM store, 1536MiB VRAM reserve; custom case, not standard benchmark', fontsize=11)
fig.savefig(OUT / 'case-results.png', dpi=160)
fig.savefig(OUT / 'case-results.svg')
plt.close(fig)
