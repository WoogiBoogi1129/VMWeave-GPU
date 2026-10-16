"""Summarize paired throughput ratios and CPU counter samples; never fill missing runs."""
import json,math,statistics,csv
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'results/20261016'
if '--equal-budget' in __import__('sys').argv:R=R/'equal-budget'
runs=[]
for p in sorted(R.glob('b*-*/**/result.json')):
 r=json.loads(p.read_text());group=p.parent.parent.name;block,mode=group.split('-',1)
 r.update(block=int(block[1:]),backend=mode,condition=p.parent.name)
 samples=[json.loads(l) for l in (p.parent/'host-cpu.jsonl').read_text().splitlines()]
 samples=[x for x in samples if 'processes' in x and r['start_utc']<=x['utc']<=r['end_utc']]
 if len(samples)>=2:
  first,last=samples[0],samples[-1];counters={};by={}
  for sample in samples:
   for v in sample['processes']:
    key=(v['pid'],v['start_ticks']);q=counters.setdefault(key,{'pod_uid':v['pod_uid'],'first':v['cpu_seconds'],'last':v['cpu_seconds']});q['last']=v['cpu_seconds']
  for q in counters.values():by[q['pod_uid']]=by.get(q['pod_uid'],0)+max(0,q['last']-q['first'])
  duration=last['utc']-first['utc'];r['host_cpu_sampled_seconds']=duration;r['host_cpu_average_cores']=sum(by.values())/duration;r['host_cpu_seconds_per_sample']=r['host_cpu_average_cores']/r['samples_per_second'];r['host_cpu_by_pod_seconds']=by
 gpu=[]
 with (p.parent/'gpu.csv').open() as f:
  for row in csv.DictReader(f):
   try:
    row={k:float(v) for k,v in row.items()}
    if r['start_utc']<=row['utc']<=r['end_utc']:gpu.append(row)
   except (ValueError,TypeError):pass
 r['gpu_samples']=len(gpu)
 if gpu:r['gpu_means']={k:statistics.mean(x[k] for x in gpu) for k in gpu[0] if k!='utc'}
 runs.append(r)
summary=[]
for condition in sorted({r['condition'] for r in runs}):
 pairs=[]
 for block in range(1,6):
  xs={r['backend']:r for r in runs if r['condition']==condition and r['block']==block}
  if xs.keys()>={'vmweave','passthrough'}:pairs.append({'block':block,'ratio':xs['vmweave']['samples_per_second']/xs['passthrough']['samples_per_second']})
 row={'condition':condition,'pairs':pairs,'n':len(pairs)}
 if pairs:
  logs=[math.log(x['ratio']) for x in pairs];gm=math.exp(statistics.mean(logs));row['paired_geomean_ratio']=gm
  if len(logs)>=2:
   t={2:12.706,3:4.303,4:3.182,5:2.776}[len(logs)];half=t*statistics.stdev(logs)/math.sqrt(len(logs));row['ratio_95ci']=[math.exp(statistics.mean(logs)-half),math.exp(statistics.mean(logs)+half)]
  row['backends']={mode:{'mean_samples_per_second':statistics.mean(v),'sd_samples_per_second':statistics.stdev(v) if len(v)>1 else None,'n':len(v)} for mode in ['vmweave','passthrough'] if (v:=[r['samples_per_second'] for r in runs if r['condition']==condition and r['backend']==mode])}
 summary.append(row)
(R/'summary.json').write_text(json.dumps({'runs':runs,'conditions':summary,'ci_method':'Student t interval on paired log throughput ratios; no normality assurance with n=5'},indent=2)+'\n')
print(json.dumps(summary,indent=2))
