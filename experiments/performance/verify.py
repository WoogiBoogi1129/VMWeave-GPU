"""Independent bundle checks; completion is distinct from enforcement success."""
import json,sys
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from analyze import samples
root=Path(sys.argv[1]);details=[];errors=[]
protocol=json.loads((root/'protocol.json').read_text())
presence={}
for line in (root/'monitoring/pmon.txt').read_text().splitlines():
 cols=line.split()
 if len(cols)<5 or not cols[3].isdigit():continue
 try:
  utc=datetime.strptime(cols[0]+' '+cols[1],'%Y%m%d %H:%M:%S').replace(tzinfo=ZoneInfo('Asia/Seoul')).timestamp()
  presence.setdefault(int(cols[3]),[]).append(utc)
 except ValueError:continue
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
  assert len(begins)==(7 if run.name.startswith('perf-o-') else 2 if run.name.startswith('perf-c-') else 1)
  max_clock_error=max(abs((b['utc']-a['utc'])-b['elapsed']) for a,b in zip(begins,ends))
  assert max_clock_error<.05,('wall-clock discontinuity',max_clock_error)
  runtime=json.loads((run/'runtime-libraries.json').read_text());allowed={r['pid'] for r in runtime}
  if run.name.startswith('perf-d-'):
   other=run.parent/(run.name[:-1]+('b' if run.name.endswith('-a') else 'a'))
   allowed.update(r['pid'] for r in json.loads((other/'runtime-libraries.json').read_text()))
  offset=identity.get('clock_offset',0)
  # pmon timestamps have one-second precision; exclude only the boundary seconds.
  observed={pid for pid,times in presence.items() if any(a['utc']-offset+1<t<b['utc']-offset-1 for a,b in zip(begins,ends) for t in times)}
  assert observed, 'No process-presence evidence in measurement windows'
  assert not observed-allowed,('unrelated GPU processes observed',sorted(observed-allowed))
  checked=0
  for r in execution['results']:
   assert r['status']=='PASS' and r['mismatches']==0 and r['checked_elements']>0
   assert r['checked_elements']==r['bytes']//4
   if 'phase' in r:
    assert r['reps']==protocol['load']['iterations'] and r['bytes']==protocol['load']['bytes']
    if r['phase']=='fixed':assert r['completed']==protocol['load']['fixed_count']
    elif run.name.startswith('perf-c-'):assert abs(r['elapsed_s']-protocol['load']['timed_s'])<.25
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
  details.append({'run':run.name,'path':identity['path'],'cap':identity['cap'],'windows':len(begins),'verified_output_elements':checked,'max_clock_error_seconds':max_clock_error,'observed_gpu_pids':sorted(observed),'status':'PASS'})
 except Exception as e:errors.append({'run':run.name,'error':str(e)})
pair_checks=[]
for file in sorted((root/'pairs').glob('*.json')) if (root/'pairs').exists() else []:
 if file.name.endswith('-failure.json'):errors.append({'pair':file.stem,'error':'failure marker present'});continue
 pair=json.loads(file.read_text());a=root/'runs'/pair['a'];b=root/'runs'/pair['b']
 if not all((d/'cleanup.json').exists() for d in [a,b]):continue
 try:
  ai=json.loads((a/'identity.json').read_text());bi=json.loads((b/'identity.json').read_text())
  assert (ai['cap'],bi['cap'])==(pair['cap_a'],pair['cap_b']), 'Pair labels differ from actual VM policies'
  ar=json.loads((a/'execution.json').read_text())['results'][0];br=json.loads((b/'execution.json').read_text())['results'][0]
  astart=ar['utc_start']-ai['clock_offset'];bstart=br['utc_start']-bi['clock_offset']
  assert abs(astart-pair['scheduled_start_host_utc'])<.25
  assert abs(bstart-astart-60)<.25
  assert abs(ar['elapsed_s']-240)<.25 and abs(br['elapsed_s']-120)<.25
  events=[json.loads(l) for l in (b/'stdout.jsonl').read_text().splitlines() if l.startswith('{')]
  hold_end=next(e['utc'] for e in events if e.get('event')=='IDLE_HOLD_END')-bi['clock_offset']
  assert hold_end>=astart+239.75
  assert ai['worker_uid']!=bi['worker_uid'] and ai['launcher_uid']!=bi['launcher_uid']
  pair_checks.append({'pair':pair['name'],'condition':[pair['cap_a'],pair['cap_b'],pair['always_active_slot']],'start_delay_s':bstart-astart,'b_context_held_until_a_s':hold_end-astart,'status':'PASS'})
 except Exception as e:errors.append({'pair':pair['name'],'error':str(e)})
counts={p:sum(x['run'].startswith('perf-'+p+'-') for x in details) for p in ['o','c','d']}
coverage={
 'overhead':dict(Counter(x['path'] for x in details if x['run'].startswith('perf-o-'))),
 'single':dict(Counter(str(x['cap']) for x in details if x['run'].startswith('perf-c-'))),
 'shared':dict(Counter('/'.join(map(str,x['condition'])) for x in pair_checks))}
expected_coverage={'overhead':{p:5 for p in 'NTS'},'single':{str(c):5 for c in protocol['caps']},'shared':{'/'.join(map(str,c)):5 for c in protocol['shared']['conditions']}}
for stage,actual in coverage.items():
 expected=expected_coverage[stage]
 if any(k not in expected or n>expected[k] for k,n in actual.items()) or (sum(actual.values())==sum(expected.values()) and actual!=expected):
  errors.append({'stage':stage,'error':'Independent-repeat coverage differs from protocol','actual':actual,'expected':expected})
interruptions=json.loads((root/'interruptions.json').read_text()) if (root/'interruptions.json').exists() else []
unresolved=[r.name for r in (root/'runs').iterdir() if r.name.startswith('perf-') and not (r/'interruption.json').exists() and not ((r/'execution.json').exists() and (r/'cleanup.json').exists())]
complete=counts=={'o':15,'c':20,'d':40} and len(pair_checks)==20 and not errors and not unresolved
report={'status':'PASS' if not errors else 'FAIL','campaign_complete':complete,'valid_runs':counts,'expected_runs':{'o':15,'c':20,'d':40},'validated_pairs':len(pair_checks),'repeat_coverage':coverage,'details':details,'pair_checks':pair_checks,'errors':errors,'meaning':'Checks execution, sample counts, output verification, clock continuity, shared start timing (250 ms tolerance on corrected timestamps), B context hold through A end, repeat coverage, and normal release. This is not a verdict that HAMi limits were enforced.'}
report.update(interrupted_attempts=interruptions,unresolved_runs=unresolved)
(root/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='details'},indent=2))
if errors:raise SystemExit(1)
