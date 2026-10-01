"""Non-overlapping Pod cgroup CPU, with explicit system-specific roles."""
from common import *
import statistics
samples=[json.loads(l) for l in (OUT/'monitoring/cpu.jsonl').read_text().splitlines()]
rows=[]
for run in sorted((OUT/'runs').glob('sc-*')):
 if not (run/'execution.json').exists():continue
 identity=json.loads((run/'identity.json').read_text());offset=identity['clock_offset'];system=identity['path']
 roles=['cell','launcher','manager'] if system=='T' else ['worker','launcher']
 for line in (run/'stdout.jsonl').read_text().splitlines():
  if not line.startswith('{'):continue
  e=json.loads(line)
  if e['event']=='CONDITION':condition=e['mode']+'-'+str(e['bytes'])
  if e['event']=='MEASUREMENT_START':start=e['utc']-offset
  if e['event']!='MEASUREMENT_END':continue
  end=e['utc']-offset;parts={}
  for role in roles:
   points=sorted((x['utc'],p['cpu']['usage_usec']) for x in samples if x['run_id']==run.name and start<=x['utc']<=end for p in x['pods'] if p['role']==role)
   if len(points)<2:continue
   duration=points[-1][0]-points[0][0];delta=points[-1][1]-points[0][1];assert delta>=0
   parts[role]={'cores':delta/1e6/duration,'coverage':duration/(end-start),'samples':len(points)}
  total=sum(p['cores'] for p in parts.values()) if len(parts)==len(roles) else None
  rate=e['completed']/e['elapsed']
  rows.append({'run':run.name,'system':system,'condition':condition,'parts':parts,'total_cores':total,'cpu_us_iteration':total/rate*1e6 if total is not None else None,'iterations_s':rate})
summary={}
for system in ['T','S']:
 summary[system]={};selected=[r for r in rows if r['system']==system and r['run'].startswith('sc-r') and r['total_cores'] is not None]
 for condition in sorted({r['condition'] for r in selected}):
  group=[r for r in selected if r['condition']==condition]
  summary[system][condition]={'repeats':len(group),'cores':statistics.mean(r['total_cores'] for r in group),'cpu_us_iteration':statistics.mean(r['cpu_us_iteration'] for r in group),'min_coverage':min(x['coverage'] for r in group for x in r['parts'].values())}
save(OUT/'cpu-summary.json',{'rows':rows,'summary':summary,'scope':'T=launcher (includes Guest client manager)+cell (RPC/MPS/node manager)+isolated cluster manager/Mongo; S=launcher+Worker. Shared Kubernetes/monitoring infrastructure excluded; host CPU provided separately. Copy iteration includes both directions.'})
print(json.dumps(summary,indent=2))
