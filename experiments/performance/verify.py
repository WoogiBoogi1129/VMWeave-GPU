"""Independent bundle checks; completion is distinct from enforcement success."""
import json,sys
from pathlib import Path
from analyze import samples
root=Path(sys.argv[1]);details=[];errors=[]
for run in sorted((root/'runs').iterdir()):
 if not run.name.startswith('perf-') or not (run/'cleanup.json').exists():continue
 try:
  execution=json.loads((run/'execution.json').read_text());cleanup=json.loads((run/'cleanup.json').read_text());identity=json.loads((run/'identity.json').read_text())
  assert execution['exit_code']==0 and cleanup['released']
  if (run/'failure.json').exists():raise AssertionError('failure marker present')
  events=[]
  for line in (run/'stdout.jsonl').read_text().splitlines():
   try:events.append(json.loads(line))
   except ValueError:pass
  begins=[r for r in events if r.get('event')=='MEASUREMENT_START'];ends=[r for r in events if r.get('event')=='MEASUREMENT_END']
  assert len(begins)==len(ends)==len(execution['results'])
  max_clock_error=max(abs((b['utc']-a['utc'])-b['elapsed']) for a,b in zip(begins,ends))
  assert max_clock_error<.05,('wall-clock discontinuity',max_clock_error)
  checked=0
  for r in execution['results']:
   assert r['status']=='PASS' and r['mismatches']==0 and r['checked_elements']>0
   suffix=r['phase'] if 'phase' in r else r['mode']+'-'+str(r['bytes'])
   data=samples(run/(run.name+'-'+suffix+'.csv.gz'));assert len(data)==r['completed']
   assert (data[:,0]==range(len(data))).all()
   if 'phase' in r:assert (data[:,1]>0).all() and (data[:,2]>0).all()
   else:assert (data[:,1]>=0).all() and (data[:,2]>=0).all()
   checked+=r['checked_elements']
  if identity['path']=='S':
   channel=json.loads((run/'channel-released.json').read_text());assert channel['status']['phase']=='Released' and channel['metadata']['uid']==identity['channel_uid']
  if identity['path'] in ['N','S']:
   runtime=json.loads((run/'runtime-libraries.json').read_text())
   assert runtime and all(r['environment']['GPU_CORE_UTILIZATION_POLICY']=='FORCE' and r['environment']['CUDA_DEVICE_SM_LIMIT']==str(identity['cap']) for r in runtime)
  details.append({'run':run.name,'windows':len(begins),'verified_output_elements':checked,'max_clock_error_seconds':max_clock_error,'status':'PASS'})
 except Exception as e:errors.append({'run':run.name,'error':str(e)})
counts={p:sum(x['run'].startswith('perf-'+p+'-') for x in details) for p in ['o','c','d']}
complete=counts=={'o':15,'c':20,'d':40} and not errors
report={'status':'PASS' if not errors else 'FAIL','campaign_complete':complete,'valid_runs':counts,'expected_runs':{'o':15,'c':20,'d':40},'details':details,'errors':errors,'meaning':'Checks execution, sample counts, output verification, clock continuity and normal release. This is not a verdict that HAMi limits were enforced.'}
(root/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='details'},indent=2))
if errors:raise SystemExit(1)
