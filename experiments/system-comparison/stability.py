"""Describe within-window completion-rate changes using actual progress ticks."""
from common import *
rows=[]
for run in sorted((OUT/'runs').glob('sc-r*')):
 if not (run/'execution.json').exists():continue
 condition=None;points=[]
 for line in (run/'stdout.jsonl').read_text().splitlines():
  if not line.startswith('{'):continue
  e=json.loads(line)
  if e['event']=='CONDITION':condition=e['mode']+'-'+str(e['bytes'])
  if e['event']=='MEASUREMENT_START':points=[(0.,0)]
  if e['event']=='TICK':points.append((e['elapsed'],e['completed']))
  if e['event']!='MEASUREMENT_END':continue
  points.append((e['elapsed'],e['completed']))
  early=[x for x in points if x[0]<=15];late=[x for x in points if x[0]>=e['elapsed']-15]
  def rate(p):
   assert len(p)>1;return (p[-1][1]-p[0][1])/(p[-1][0]-p[0][0])
  first,last=rate(early),rate(late)
  rows.append({'run':run.name,'condition':condition,'first_rate_s':first,'last_rate_s':last,'last_over_first':last/first,'first_interval':early,'last_interval':late})
save(OUT/'stability.json',{'rows':rows,'method':'First and last approximately 15 seconds using recorded elapsed/count ticks, with actual endpoint durations. Descriptive only; no sample trimming or restarts. All 60 seconds remain in main statistics.'})
print('Recorded',len(rows),'window stability summaries')
