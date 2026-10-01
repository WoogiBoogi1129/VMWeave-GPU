"""Summarize device telemetry over exact measurement windows, not VM lifetime."""
from common import *
import math, statistics

rows=[]
for run in sorted((OUT/'runs').glob('sc-r*')):
 if not (run/'telemetry.json').exists():continue
 identity=json.loads((run/'identity.json').read_text())
 telemetry=json.loads((run/'telemetry.json').read_text())
 for line in (run/'stdout.jsonl').read_text().splitlines():
  if not line.startswith('{'):continue
  e=json.loads(line)
  if e['event']=='CONDITION':condition=e['mode']+'-'+str(e['bytes'])
  if e['event']=='MEASUREMENT_START':start=e['utc']-identity['clock_offset']
  if e['event']!='MEASUREMENT_END':continue
  end=e['utc']-identity['clock_offset'];metrics={}
  for key in ['gpu_util','gpu_memory','gpu_power','gpu_clock','gpu_temperature']:
   series=[x for x in telemetry[key]['data']['result'] if x['metric'].get('UUID')==GPU]
   assert len(series)==1,(run.name,key)
   points=[(float(t),float(v)) for t,v in series[0]['values'] if start<=float(t)<=end and math.isfinite(float(v))]
   assert points,(run.name,key)
   values=[v for t,v in points]
   metrics[key]={'mean':statistics.mean(values),'min':min(values),'max':max(values),'query_points':len(points),'span_coverage':(points[-1][0]-points[0][0])/(end-start)}
  rows.append({'run':run.name,'system':identity['path'],'condition':condition,'start':start,'end':end,'metrics':metrics})
summary={}
for system in ['T','S']:
 summary[system]={}
 for condition in sorted({r['condition'] for r in rows}):
  group=[r for r in rows if r['system']==system and r['condition']==condition]
  if not group:continue
  summary[system][condition]={'repeats':len(group),'metrics':{key:{'mean':statistics.mean(r['metrics'][key]['mean'] for r in group),'sd':statistics.stdev(r['metrics'][key]['mean'] for r in group) if len(group)>1 else None,'min':min(r['metrics'][key]['min'] for r in group),'max':max(r['metrics'][key]['max'] for r in group)} for key in group[0]['metrics']}}
save(OUT/'gpu-summary.json',{'rows':rows,'summary':summary,'scope':'DCGM whole-device observations for the recorded GPU UUID during measurement windows only. Prometheus 1-second query points may repeat exporter samples; these are not independent repetitions or proof of per-VM quota enforcement.'})
print('GPU telemetry windows:',len(rows))
