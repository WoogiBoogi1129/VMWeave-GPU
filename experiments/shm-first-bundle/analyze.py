"""Independent per-session aggregation; raw samples are never repetitions."""
import csv,gzip,statistics,math
from common import *

def quantile(xs,p):
    a=sorted(xs);return a[int((len(a)-1)*p)]
rows=[]
for run in sorted((OUT/'runs').glob('sf-*')):
    if not (run/'execution.json').exists() or not (run/'variant.json').exists():continue
    execution=json.loads((run/'execution.json').read_text())
    if execution['exit_code']:continue
    results=execution['results'];variant=json.loads((run/'variant.json').read_text())
    events=[json.loads(l) for l in (run/'stdout.jsonl').read_text().splitlines() if l.startswith('{')]
    for path in sorted(run.glob('*.csv.gz')):
        label=path.name.removeprefix(run.name+'-').removesuffix('.csv.gz');mode,size=label.rsplit('-',1)
        with gzip.open(path,'rt') as f:samples=list(csv.DictReader(f))
        result=next(r for r in results if r['mode']==mode and r['bytes']==int(size))
        assert len(samples)==result['completed'] and result['status']=='PASS' and not result['mismatches']
        assert all(int(r['sample'])==i for i,r in enumerate(samples))
        fields=[('h2d','first_seconds'),('d2h','second_seconds')] if mode=='copy' else [(mode,'first_seconds' if mode=='query' else 'second_seconds')]
        for metric,field in fields:
            values=[float(r[field])*1e6 for r in samples]
            assert values and all(math.isfinite(x) and x>0 for x in values)
            rows.append({'run':run.name,'variant':run.name.split('-')[-1],'metric':metric+('-'+size if mode=='copy' else ''),
                         'count':len(values),'mean_us':statistics.mean(values),'p50_us':quantile(values,.5),
                         'p95_us':quantile(values,.95),'p99_us':quantile(values,.99) if len(values)>=10000 else None})
summary={}
for variant in ['base','wait','copy','both']:
    selected=[r for r in rows if r['variant']==variant and r['run'].startswith('sf-r')]
    summary[variant]={}
    for metric in sorted({r['metric'] for r in selected}):
        group=[r for r in selected if r['metric']==metric];v=[r['mean_us'] for r in group]
        summary[variant][metric]={'repeats':len(v),'mean_us':statistics.mean(v),'sd_us':statistics.stdev(v) if len(v)>1 else None,
                                 'mean_p95_us':statistics.mean(r['p95_us'] for r in group)}
save(OUT/'summary.json',{'rows':rows,'summary':summary,'complete':all(len(summary[v])==8 and all(x['repeats']==5 for x in summary[v].values()) for v in summary)})
for v in summary:
    print(v,{m:round(r['mean_us'],2) for m,r in summary[v].items()})
for r in rows:
    if 'pilot' in r['run']:print(r['run'],r['metric'],round(r['mean_us'],2))
