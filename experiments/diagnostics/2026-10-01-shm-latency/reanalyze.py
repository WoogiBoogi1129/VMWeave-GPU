"""Read-only decomposition of the original kernel launch+sync samples."""
import csv
import gzip
import hashlib
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ORIGINAL = ROOT / 'experiments/evidence/results/2026-09-30-performance'
rows = []
for path in sorted((ORIGINAL / 'runs').glob('perf-o-r[1-5]-*/**/*-kernel-1048576.csv.gz')):
    with gzip.open(path, 'rt') as stream:
        samples = list(csv.DictReader(stream))
    launch = [float(s['first_seconds']) * 1e6 for s in samples]
    total = [float(s['second_seconds']) * 1e6 for s in samples]
    assert all(t >= l >= 0 for l, t in zip(launch, total))
    rows.append(dict(run=path.parent.name, path=str(path.relative_to(ROOT)),
                     sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                     count=len(samples), launch_us=statistics.mean(launch),
                     sync_us=statistics.mean(t-l for l, t in zip(launch, total)),
                     total_us=statistics.mean(total)))
summary = {}
for route in ['n', 't', 's']:
    group = [r for r in rows if r['run'].endswith('-' + route)]
    assert len(group) == 5
    summary[route] = {key: dict(mean=statistics.mean(r[key] for r in group),
                               sd=statistics.stdev(r[key] for r in group))
                      for key in ['launch_us', 'sync_us', 'total_us']}
result = dict(scope='Original samples reanalysis; no new VM/GPU execution. '
                    'sync is host-observed API wait, not isolated GPU execution time.',
              runs=rows, summary=summary)
(HERE / 'results/kernel-decomposition.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(summary, indent=2))
