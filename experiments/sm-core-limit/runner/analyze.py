"""Summarize observed utilization; do not infer enforcement from config alone."""
import json, statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
EVIDENCE=ROOT/'experiments/sm-core-limit/evidence'
rows=[]
for result in sorted(EVIDENCE.glob('**/result.json')):
    p=result.parent
    if 'limit-validation-20261015' in p.parts:continue  # Separate repeated campaign; analyze_limits.py.
    if not (p/'gpu.csv').exists():continue
    r=json.loads(result.read_text())
    samples=[[float(v) for v in line.split(',')] for line in (p/'gpu.csv').read_text().splitlines()]
    entry={'run':str(p.relative_to(EVIDENCE)),**r}
    entry['window_statistics']={}
    for start in [32,120]:
        util=[x[1] for x in samples if x[0]>=start]
        if util:
            entry['window_statistics'][str(start)]={
                'samples':len(util),'mean':statistics.mean(util),
                'stdev':statistics.pstdev(util),'min':min(util),'max':max(util),
                'fraction_ge_95':sum(v>=95 for v in util)/len(util)}
    if r['limit']<100:
        entry['mean_within_proposed_5pp']=abs(r['device_util_mean']-r['limit'])<=5
    rows.append(entry)
gates={variant:('DO_NOT_ROLL_OUT' if any(r.get('variant')==variant and r.get('mean_within_proposed_5pp') is False for r in rows) else 'MORE_VALIDATION_REQUIRED')
       for variant in ['patched','idle-reset']}
out={'scope':'One repetition per condition; exploratory gate, not completed release qualification.',
     'gate':gates['idle-reset'],'candidate_gates':gates,
     'runs':rows}
(EVIDENCE/'analysis.json').write_text(json.dumps(out,indent=2)+'\n')
for r in rows:
    print(r['run'], 'mean=',round(r['device_util_mean'],2),'launches/s=',round(r['launches_per_second'],2),
          'after120=',round(r['window_statistics'].get('120',{}).get('mean',0),2))
print(out['gate'])
