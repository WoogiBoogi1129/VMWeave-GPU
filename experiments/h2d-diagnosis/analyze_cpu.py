from common import *
import statistics
from evidence_io import read_text
samples=[json.loads(l) for l in read_text(OUT/'monitoring/cpu.jsonl').splitlines()]
data=json.loads((OUT/'analysis.json').read_text());rows=[]
for row in data['rows']:
 run=row['run'];identity=json.loads((OUT/'runs'/run/'identity.json').read_text());offset=identity['clock_offset'];start=row['utc_start']-offset;end=row['utc_end']-offset
 roles=['cell','launcher','manager'] if row['path']=='T' else ['worker','launcher'];parts={}
 for role in roles:
  p=sorted((s['utc'],v['cpu']['usage_usec'],v['memory_bytes']) for s in samples if s['run_id']==run and start<=s['utc']<=end for v in s['pods'] if v['role']==role)
  if len(p)<2:continue
  duration=p[-1][0]-p[0][0];delta=p[-1][1]-p[0][1];assert delta>=0
  parts[role]={'cores':delta/1e6/duration,'coverage':duration/(end-start),'samples':len(p),'peak_memory_bytes':max(x[2] for x in p)}
 total=sum(p['cores'] for p in parts.values()) if len(parts)==len(roles) else None
 rows.append({'run':run,'mode':row['mode'],'bytes':row['bytes'],'parts':parts,'cores':total,'cpu_us_iteration':total/row['rate']*1e6 if total else None})
save(OUT/'cpu-analysis.json',{'rows':rows,'scope':'Non-overlapping Pod cgroups; T=launcher+cell+manager, S=launcher+Worker. Copy iteration includes both H2D and D2H unless mode=h2d. 1-second approximate clock-aligned observations.'})
