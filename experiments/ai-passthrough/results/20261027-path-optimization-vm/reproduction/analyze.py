import json,math,statistics,itertools,csv
from pathlib import Path
O=Path('experiments/ai-passthrough/results/20261027-path-optimization-vm')
MODES=['flyt','control','candidate'];WORK=['nw','lu','srad','sc'];ROUNDS=range(1,6)
raw={};rows=[]
for w in WORK:
 for mode in MODES:
  values=[]
  for r in ROUNDS:
   d=json.loads((O/'formal'/f'r{r}'/mode/w/'result.json').read_text());assert d['correct']
   samples=[s['seconds'] for s in d['samples'] if not s['warmup']]
   assert len(samples)==(1 if w=='sc' else 3)
   values.append(statistics.median(samples))
  raw[w,mode]=values
  rows.append({'workload':w,'mode':mode,'independent_VMs':5,'session_medians_s':values,'median_s':statistics.median(values),'mean_s':statistics.mean(values)})
def ratio_ci(a,b):
 logs=[math.log(x/y) for x,y in zip(a,b)]
 boot=sorted(math.exp(statistics.mean(logs[i] for i in indices)) for indices in itertools.product(range(5),repeat=5))
 return {'ratio':math.exp(statistics.mean(logs)),'ci95':[boot[int(.025*(len(boot)-1))],boot[int(.975*(len(boot)-1))]],'round_ratios':[math.exp(x) for x in logs]}
comparisons=[]
for w in WORK:
 comparisons.append({'workload':w,'candidate_vs_flyt':ratio_ci(raw[w,'candidate'],raw[w,'flyt']),'candidate_vs_control':ratio_ci(raw[w,'candidate'],raw[w,'control'])})
aggregate={mode:[math.exp(statistics.mean(math.log(raw[w,mode][r]) for w in WORK)) for r in range(5)] for mode in MODES}
overall=ratio_ci(aggregate['candidate'],aggregate['flyt'])
micro={};micro_api={};micro_cpu={}
for mode in MODES:
 for r in ROUNDS:
  d=json.loads((O/'micro'/f'r{r}'/mode/'result.json').read_text());assert d['status']=='PASS'
  for cell in d['rows']:
   assert cell['correct'];key=(cell['operation'],cell['bytes'],mode)
   micro.setdefault(key,[]).append(statistics.median(s['completion_ns'] for s in cell['samples'] if not s['warmup']))
   micro_api.setdefault(key,[]).append(statistics.median(s['api_ns'] for s in cell['samples'] if not s['warmup']))
   micro_cpu.setdefault(key,[]).append(statistics.median(s['caller_cpu_ns'] for s in cell['samples'] if not s['warmup']))
micro_rows=[]
for op,n in sorted({(op,n) for op,n,mode in micro}):
 row={'operation':op,'bytes':n,'session_medians_ms':{mode:[x/1e6 for x in micro[op,n,mode]] for mode in MODES},'median_ms':{mode:statistics.median(micro[op,n,mode])/1e6 for mode in MODES},'candidate_vs_flyt':ratio_ci(micro[op,n,'candidate'],micro[op,n,'flyt']),'candidate_vs_control':ratio_ci(micro[op,n,'candidate'],micro[op,n,'control'])}
 row['api_return_median_ms']={mode:statistics.median(micro_api[op,n,mode])/1e6 for mode in MODES}
 row['caller_cpu_median_ms']={mode:statistics.median(micro_cpu[op,n,mode])/1e6 for mode in MODES}
 row['effective_GB_per_s_including_completion']={mode:n/(row['median_ms'][mode]*1e6) for mode in MODES}
 micro_rows.append(row)
critical_regression=any(r['operation'] in ('H2D','D2H') and r['candidate_vs_flyt']['ci95'][0]>1.05 for r in micro_rows)
performance_pass=overall['ci95'][1]<1 and all(c['candidate_vs_flyt']['ci95'][1]<=1.05 for c in comparisons) and not critical_regression
result={'status':'PERFORMANCE_GATE_PASS_REQUIRES_REMAINING_QUALIFICATION' if performance_pass else 'DO_NOT_PROMOTE', 'overall_candidate_vs_flyt':overall,'overall_candidate_vs_control':ratio_ci(aggregate['candidate'],aggregate['control']), 'workloads':comparisons,'raw_workload_summary':rows,'critical_H2D_D2H_regression':critical_regression,'independent_VM_conditions':15,'formal_samples':150,'confidence':'paired VM-round percentile bootstrap, exact 5^5 resamples; n=5 limits precision; descriptive micro CIs not adjusted for multiplicity'}
(O/'comparison.json').write_text(json.dumps(result,indent=2)+'\n');(O/'micro-comparison.json').write_text(json.dumps(micro_rows,indent=2)+'\n')
with open(O/'workloads.csv','w') as f:
 writer=csv.writer(f);writer.writerow(['workload','flyt_median_s','control_median_s','candidate_median_s','candidate_flyt_ratio','CI95_lower','CI95_upper'])
 for c in comparisons:
  w=c['workload'];q=c['candidate_vs_flyt'];writer.writerow([w,*[statistics.median(raw[w,m]) for m in MODES],q['ratio'],*q['ci95']])
print(json.dumps(result,indent=2))
